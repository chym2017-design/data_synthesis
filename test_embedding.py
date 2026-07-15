"""
Embedding 模型调用测试脚本

独立命令行工具，不嵌入页面。读取 configs/embedding_config.yaml 获取 embedding 配置，
测试文本向量化和余弦相似度计算。

用法:
    python test_embedding.py                                 # 使用内置默认文本测试
    python test_embedding.py --text "测试文本"                  # 单文本向量化
    python test_embedding.py --texts "文本A" "文本B" "文本C"    # 多文本，输出相似度矩阵
    python test_embedding.py --pair "文本A" "文本B"             # 两文本，输出余弦相似度
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "configs" / "embedding_config.yaml"

sys.path.insert(0, str(SCRIPT_DIR))
from synth_engine.llm.embedding import get_embedding, compute_cosine_similarity_matrix, cosine_similarity


DEFAULT_TEXTS = [
    "我想查一下银行卡余额",
    "帮我看看账户里还有多少钱",
    "怎么申请信用卡副卡",
    "我的理财收益有多少",
]


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return config


def main():
    parser = argparse.ArgumentParser(description="Embedding 模型调用测试")
    parser.add_argument("--text", type=str, default="", help="单个测试文本，输出向量维度与前几维")
    parser.add_argument("--texts", type=str, nargs="+", help="多个测试文本，输出两两余弦相似度矩阵")
    parser.add_argument("--pair", type=str, nargs=2, help="两个文本，输出余弦相似度")
    parser.add_argument("--timeout", type=int, default=60, help="超时时间（秒）")
    args = parser.parse_args()

    config = load_config()
    url = config.get("url", "")
    api_key = config.get("api_key", "")
    model = config.get("model", "")
    if not url or not api_key or not model:
        print("[错误] 请检查 configs/embedding_config.yaml (model/url/api_key)")
        sys.exit(1)


    print(f"\n{'='*80}")
    print(f"Embedding 模型: {model}")
    print(f"API 地址: {url}")
    print(f"{'='*80}\n")

    if args.text:
        t0 = time.perf_counter()
        emb = get_embedding(args.text, base_url=url, api_key=api_key, model=model, timeout=args.timeout)
        elapsed = time.perf_counter() - t0
        if emb is None:
            print("[失败] 获取 embedding 失败")
            sys.exit(1)
        print(f"输入文本: {args.text}")
        print(f"向量维度: {len(emb)}")
        print(f"耗时: {elapsed:.3f}s")
        print(f"前 10 维: {emb[:10]}")
        print(f"范数(L2): {np.linalg.norm(emb):.6f}")

    elif args.pair:
        print("计算两文本余弦相似度...")
        emb_a = get_embedding(args.pair[0], base_url=url, api_key=api_key, model=model, timeout=args.timeout)
        emb_b = get_embedding(args.pair[1], base_url=url, api_key=api_key, model=model, timeout=args.timeout)
        if emb_a is None or emb_b is None:
            print("[失败] 获取 embedding 失败")
            sys.exit(1)
        sim = cosine_similarity(emb_a, emb_b)
        print(f"  [A] {args.pair[0]}")
        print(f"  [B] {args.pair[1]}")
        print(f"  维度: {len(emb_a)}")
        print(f"  余弦相似度: {sim:.6f}")

    else:
        texts = args.texts if args.texts else DEFAULT_TEXTS
        if args.texts:
            mode = "自定义"
        else:
            mode = "默认"
        print(f"使用{mode}文本 ({len(texts)} 条):")
        for i, t in enumerate(texts):
            print(f"  [{i}] {t}")

        t0 = time.perf_counter()
        embeddings = []
        for i, t in enumerate(texts):
            emb = get_embedding(t, base_url=url, api_key=api_key, model=model, timeout=args.timeout)
            embeddings.append(emb)
            status = "OK" if emb is not None else "FAIL"
            dim = len(emb) if emb is not None else 0
            print(f"  [{i}] {status} dim={dim}")
        total_elapsed = time.perf_counter() - t0

        if any(e is None for e in embeddings):
            print("\n[警告] 部分 embedding 获取失败，相似度矩阵用零向量填充")

        dim = len(embeddings[0]) if embeddings[0] is not None else 0
        print(f"\n{'='*80}")
        print(f"结果汇总")
        print(f"{'='*80}")
        print(f"  总文本数: {len(texts)}")
        print(f"  向量维度: {dim}")
        print(f"  总耗时: {total_elapsed:.3f}s")
        print(f"  平均耗时: {total_elapsed / len(texts):.3f}s/条")

        sim_matrix = compute_cosine_similarity_matrix(embeddings)
        print(f"\n余弦相似度矩阵 (i→j):")
        header = "        " + "".join(f"  [{i}]   " for i in range(len(texts)))
        print(header)
        for i in range(len(texts)):
            row = f"  [{i}]  " + "  ".join(f"{sim_matrix[i][j]:.4f}" for j in range(len(texts)))
            print(row)

    print(f"\n{'='*80}")
    print("测试完成")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
