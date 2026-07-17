"""
LLM 模型调用测试脚本

独立命令行工具，不嵌入页面。读取 configs/llm_config.yaml 获取模型列表，
直接运行测试所有模型，也可指定单个模型。

用法:
    python docs/test_llm.py                                    # 测试所有模型（默认 prompt）
    python docs/test_llm.py --prompt "你好"                      # 自定义 prompt
    python docs/test_llm.py --model qwen-plus                    # 指定单个模型
    python docs/test_llm.py --stream                            # 流式调用
    python docs/test_llm.py --list                              # 列出可用模型
    python docs/test_llm.py --prompt-file prompt.txt --model glm-5  # 从文件读 prompt
"""

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "llm_config.yaml"

sys.path.insert(0, str(PROJECT_ROOT))
from synth_engine.llm.client import run_llm_stream, run_llm_non_stream


def load_configs() -> list:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        configs = yaml.safe_load(f) or []
    return configs


def list_models(configs: list):
    print(f"可用模型 ({len(configs)}):")
    for cfg in configs:
        print(f"  {cfg['model']:<20} url={cfg.get('url', '')[:50]}...")


def test_one(cfg: dict, prompt: str, stream: bool, system_prompt: str) -> dict:
    kwargs = {
        "question": prompt,
        "url": cfg.get("url"),
        "api_key": cfg.get("api_key"),
        "model": cfg.get("model"),
        "timeout": cfg.get("timeout"),
        "stream": stream,
    }
    if system_prompt:
        kwargs["system_prompt"] = system_prompt
    for k in ("temperature", "max_tokens", "enable_thinking"):
        if k in cfg:
            kwargs[k] = cfg[k]

    t0 = time.perf_counter()
    if stream:
        result = run_llm_stream(**kwargs)
    else:
        result = run_llm_non_stream(**kwargs)
    result["_elapsed"] = time.perf_counter() - t0
    return result


def preview(text: str, max_len: int = 200) -> str:
    if not text:
        return "(空)"
    text = text.replace("\n", "\\n")
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def main():
    parser = argparse.ArgumentParser(description="LLM 模型调用测试")
    parser.add_argument("--list", action="store_true", help="列出可用模型")
    parser.add_argument("--model", type=str, default="", help="指定模型名称（默认所有模型）")
    parser.add_argument("--prompt", type=str, default="你好", help="测试 prompt")
    parser.add_argument("--prompt-file", type=str, help="从文件读取 prompt")
    parser.add_argument("--system-prompt", type=str, default="", help="系统提示词")
    parser.add_argument("--stream", action="store_true", help="使用流式调用")
    parser.add_argument("--non-stream", action="store_false", dest="stream", default=True,
                        help="使用非流式调用（默认）")
    parser.add_argument("--timeout", type=int, help="覆盖超时时间")
    args = parser.parse_args()

    configs = load_configs()
    if not configs:
        print("[错误] 未找到 LLM 配置，请检查 configs/llm_config.yaml")
        sys.exit(1)

    if args.list:
        list_models(configs)
        return

    if args.model:
        targets = [c for c in configs if c.get("model") == args.model]
        if not targets:
            print(f"[错误] 未找到模型 '{args.model}'")
            sys.exit(1)
    else:
        targets = configs

    prompt = args.prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    if not prompt:
        print("[错误] 请指定 --prompt 或 --prompt-file")
        sys.exit(1)

    stream_label = "流式" if args.stream else "非流式"
    print(f"\n{'='*80}")
    print(f"测试 Prompt: {preview(prompt, 100)}")
    print(f"调用模式: {stream_label}  |  模型数: {len(targets)}")
    print(f"{'='*80}\n")

    header = f"{'模型':<16} {'状态码':<8} {'耗时(s)':<10} {'Token(p/c)':<16} {'响应预览'}"
    print(header)
    print("-" * 80)

    for cfg in targets:
        if args.timeout:
            cfg = {**cfg, "timeout": args.timeout}
        try:
            result = test_one(cfg, prompt, args.stream, args.system_prompt)
        except Exception as e:
            print(f"{cfg['model']:<16} {'ERROR':<8} {'-':<10} {'-':<16} {str(e)[:60]}")
            continue

        model_name = result.get("model", cfg["model"])
        status = result.get("status_code", "?")
        elapsed = result.get("_elapsed", 0)
        prompt_tokens = result.get("prompt_tokens", "-")
        completion_tokens = result.get("completion_tokens", "-")
        tokens = f"{prompt_tokens}/{completion_tokens}"
        response = result.get("response", "")
        err_msg = result.get("err_msg", "")
        preview_text = err_msg or preview(response, 80)

        print(f"{model_name:<16} {str(status):<8} {elapsed:<10.2f} {tokens:<16} {preview_text}")

    print("-" * 80)


if __name__ == "__main__":
    main()
