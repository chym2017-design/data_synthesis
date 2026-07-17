"""
全功能测试脚本

按流程顺序跑通所有模块：LLM测试 → Embedding测试 → 合成前质检 → 数据合成 → 合成后质检

用法:
    python docs/test_all.py                      # 全部测试（合成 5 条样本）
    python docs/test_all.py --samples 10         # 指定合成样本数
    python docs/test_all.py --skip-synthesis     # 跳过合成和后质检，仅测 LLM/Embedding/前质检
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"
LLM_CONFIG_PATH = CONFIGS_DIR / "llm_config.yaml"
EMBEDDING_CONFIG_PATH = CONFIGS_DIR / "embedding_config.yaml"
TEMPLATE_DIR = PROJECT_ROOT / "synth_engine" / "templates" / "bank_intent"
INTENT_FILE = str(TEMPLATE_DIR / "intent.json")
RUNS_DIR = PROJECT_ROOT / "runs"

sys.path.insert(0, str(PROJECT_ROOT))

_results = []
_start_time = None


def _now_str():
    return datetime.now().strftime("%H:%M:%S")


def _elapsed():
    return f"{time.perf_counter() - _start_time:.1f}s"


def _report(stage: str, ok: bool, detail: str = ""):
    status = "✓ 通过" if ok else "✗ 失败"
    _results.append({"stage": stage, "ok": ok, "detail": detail})
    print(f"  [{_elapsed()}] [{_now_str()}] {stage:20s} {status}  {detail}")


def _hdr(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ============================================================
# 1. LLM 测试
# ============================================================
def test_llm_models():
    _hdr("1. LLM 模型可用性")
    from synth_engine.llm.client import run_llm_non_stream

    with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
        configs = yaml.safe_load(f) or []

    all_ok = True
    for cfg in configs:
        model = cfg.get("model", "?")
        try:
            result = run_llm_non_stream(
                question="你好", url=cfg.get("url"), api_key=cfg.get("api_key"),
                model=model, timeout=cfg.get("timeout", 60),
                temperature=cfg.get("temperature", 0.7),
                max_tokens=cfg.get("max_tokens", 512),
            )
            status = result.get("status_code", 0)
            if status == 200 and result.get("response"):
                _report(f"LLM {model}", True, f"status={status}, tokens={result.get('prompt_tokens','?')}/{result.get('completion_tokens','?')}")
            else:
                _report(f"LLM {model}", False, f"status={status}, err={result.get('err_msg','')[:60]}")
                all_ok = False
        except Exception as e:
            _report(f"LLM {model}", False, str(e)[:80])
            all_ok = False
    return all_ok


# ============================================================
# 2. Embedding 测试
# ============================================================
def test_embedding():
    _hdr("2. Embedding 模型可用性")
    from synth_engine.llm.embedding import get_embedding, cosine_similarity

    with open(EMBEDDING_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    url = cfg.get("url", "").replace("/chat/completions", "").replace("/embeddings", "")
    api_key = cfg.get("api_key", "")
    model = cfg.get("model", "")

    texts = ["我想查一下银行卡余额", "帮我看看账户里还有多少钱", "怎么申请信用卡副卡"]

    embeds = []
    for t in texts:
        emb = get_embedding(t, base_url=url, api_key=api_key, model=model)
        embeds.append(emb)

    if any(e is None for e in embeds):
        _report("Embedding", False, "有文本获取 embedding 失败")
        return False

    dim = len(embeds[0])
    sim = cosine_similarity(embeds[0], embeds[1])
    sim_diff = cosine_similarity(embeds[0], embeds[2])

    ok = dim > 0 and sim > 0.8 and sim > sim_diff
    _report("Embedding", ok, f"dim={dim}, 同义相似度={sim:.4f}, 异义相似度={sim_diff:.4f}")
    return ok


# ============================================================
# 3. 合成前质检
# ============================================================
def test_pre_qc():
    _hdr("3. 合成前质检 (意图配置校验)")

    from synth_engine.llm.parallel import run_llm_para
    from synth_engine.llm.embedding import get_embedding, compute_cosine_similarity_matrix

    with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
        llm_configs = yaml.safe_load(f) or []
    with open(EMBEDDING_CONFIG_PATH, "r", encoding="utf-8") as f:
        emb_cfg = yaml.safe_load(f) or {}
    with open(INTENT_FILE, "r", encoding="utf-8") as f:
        intent_data = json.load(f)

    url = emb_cfg.get("url", "").replace("/chat/completions", "").replace("/embeddings", "")
    api_key = emb_cfg.get("api_key", "")
    model = emb_cfg.get("model", "")

    intent = intent_data.get("intent", {})
    menu_items = []
    for menu_name, menu_data in intent.items():
        for sub in menu_data.get("sub_intent", []):
            menu_items.append({
                "menu_name": menu_name,
                "sub_intent_name": sub.get("name", ""),
                "description": sub.get("description", ""),
            })

    total_intents = len(menu_items)

    # 3a. 菜单质检 (只测前 5 个菜单，节省时间)
    sample_items = menu_items[:5]
    from synth_engine.qc.pre_check import MENU_QUALITY_PROMPT

    prompts = [MENU_QUALITY_PROMPT.format(**item) for item in sample_items]
    cfg_with_json = []
    for c in llm_configs:
        cc = c.copy()
        cc["response_format"] = {"type": "json_object"}
        cfg_with_json.append(cc)

    try:
        df_qc = run_llm_para(prompts, 3, cfg_with_json)
    except Exception as e:
        _report("前质检-菜单质量", False, f"LLM调用失败: {e}")
        return False

    if df_qc is None or len(df_qc) == 0:
        _report("前质检-菜单质量", False, "无返回结果")
        return False

    valid_responses = sum(1 for _, r in df_qc.iterrows() if r.get("response", "").strip())
    _report("前质检-菜单质量", valid_responses > 0, f"检测 {len(sample_items)}/{total_intents} 个菜单, LLM响应 {valid_responses} 条")

    # 3b. 相似菜单检测
    embeddings = []
    for item in menu_items:
        emb = get_embedding(item["description"], base_url=url, api_key=api_key, model=model)
        embeddings.append(emb)

    if any(e is None for e in embeddings):
        _report("前质检-相似检测", False, "embedding 获取失败")
        return False

    sim_matrix = compute_cosine_similarity_matrix(embeddings)
    high_sim_pairs = 0
    for i in range(len(menu_items)):
        for j in range(i + 1, len(menu_items)):
            if sim_matrix[i][j] >= 0.7:
                high_sim_pairs += 1

    _report("前质检-相似检测", True, f"共 {total_intents} 个菜单, 相似度>=0.7 的对数: {high_sim_pairs}")
    return True


# ============================================================
# 4. 数据合成
# ============================================================
def test_synthesis(num_samples: int):
    _hdr(f"4. 数据合成 ({num_samples} 条样本)")

    from synth_engine.core.pipeline import SynthesisPipeline
    from synth_engine.core.config import SynthConfigModel

    with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
        llm_configs = yaml.safe_load(f) or []

    run_id = _now_str().replace(":", "").replace(" ", "_")
    run_dir = str(SCRIPT_DIR / "runs" / "outputs" / f"test_{run_id}")

    synth_cfg = SynthConfigModel()

    stage_info = {}

    def status_cb(status):
        stage_info["stage"] = status.stage
        stage_info["current"] = status.current
        stage_info["total"] = status.total
        print(f"    [{status.stage}] {status.message}")

    try:
        pipeline = SynthesisPipeline(
            template_name="bank_intent",
            template_dir=str(TEMPLATE_DIR),
            run_dir=run_dir,
            synth_config=synth_cfg,
            status_callback=status_cb,
        )
        output_path = pipeline.run(
            num_samples=num_samples,
            llm_configs=llm_configs,
            para=3,
        )

        csv_path = Path(run_dir) / "data.csv"
        jsonl_path = Path(run_dir) / "sft.jsonl"

        if csv_path.exists():
            import pandas as pd
            df = pd.read_csv(csv_path)
            row_count = len(df)
            has_query = "query" in df.columns
            _report("合成-导出", True, f"CSV {row_count} 行, JSONL: {'存在' if jsonl_path.exists() else '不存在'}, 含query列: {has_query}")
            return True, run_dir, str(csv_path)
        else:
            _report("合成-导出", False, f"data.csv 未生成, 目录: {run_dir}")
            return False, run_dir, ""
    except Exception as e:
        _report("合成", False, str(e)[:100])
        return False, run_dir, ""


# ============================================================
# 5. 合成后质检
# ============================================================
def test_post_qc(data_file: str, intent_file: str, run_dir: str):
    _hdr("5. 合成后质检")

    from synth_engine.qc.post_check import embedding_similarity_check, llm_qc_with_voting

    with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
        llm_configs = yaml.safe_load(f) or []
    with open(EMBEDDING_CONFIG_PATH, "r", encoding="utf-8") as f:
        emb_cfg = yaml.safe_load(f) or {}
    with open(intent_file, "r", encoding="utf-8") as f:
        intent_config = json.load(f)

    save_dir = str(Path(run_dir).parent.parent / "qc_results" / f"test_{Path(run_dir).name}")
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    all_ok = True

    # 5a. Embedding 相似度检测
    try:
        emb_path = embedding_similarity_check(
            data_file=data_file,
            embedding_config=emb_cfg,
            save_dir=save_dir,
            threshold=0.95,
        )
        import pandas as pd
        df_emb = pd.read_csv(emb_path)
        pairs = len(df_emb)
        _report("后质检-Embedding", True, f"相似样本对: {pairs}")
    except Exception as e:
        _report("后质检-Embedding", False, str(e)[:80])
        all_ok = False

    # 5b. LLM 投票质检
    try:
        llm_results = llm_qc_with_voting(
            data_file=data_file,
            intent_config=intent_config,
            llm_configs=llm_configs,
            save_dir=save_dir,
            para=3,
        )
        summary_path = llm_results.get("summary", "")
        if summary_path and Path(summary_path).exists():
            import pandas as pd
            df_sum = pd.read_csv(summary_path)
            total = len(df_sum)
            overall = int(df_sum["overall_pass"].sum())
            _report("后质检-LLM投票", True, f"样本 {total} 条, 通过 {overall} 条 ({overall/max(total,1)*100:.1f}%)")
        else:
            _report("后质检-LLM投票", False, "summary 文件不存在")
            all_ok = False
    except Exception as e:
        _report("后质检-LLM投票", False, str(e)[:80])
        all_ok = False

    return all_ok


# ============================================================
# Main
# ============================================================
def main():
    global _start_time

    parser = argparse.ArgumentParser(description="全功能测试")
    parser.add_argument("--samples", type=int, default=5, help="合成样本数 (默认 5)")
    parser.add_argument("--skip-synthesis", action="store_true", help="跳过合成和后质检")
    args = parser.parse_args()

    _start_time = time.perf_counter()

    print(f"\n{'#'*70}")
    print(f"#  全功能测试")
    print(f"#  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"#  合成样本数: {args.samples}")
    print(f"{'#'*70}")

    # 1. LLM
    test_llm_models()

    # 2. Embedding
    test_embedding()

    # 3. 合成前质检
    test_pre_qc()

    # 4 & 5. 合成 + 后质检
    if args.skip_synthesis:
        _hdr("跳过合成和后质检")
    else:
        ok, run_dir, csv_path = test_synthesis(args.samples)
        if ok and csv_path:
            test_post_qc(csv_path, INTENT_FILE, run_dir)

    # 汇总
    total = len(_results)
    passed = sum(1 for r in _results if r["ok"])
    print(f"\n{'='*70}")
    print(f"  测试汇总: {passed}/{total} 通过")
    print(f"{'='*70}")
    for r in _results:
        status = "✓" if r["ok"] else "✗"
        print(f"  {status} {r['stage']:24s} {r['detail']}")
    print(f"{'='*70}")
    print(f"  总耗时: {_elapsed()}\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
