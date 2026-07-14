"""
LLM 并行调用模块

支持多模型负载均衡、线程池并行、自动重试。
"""

import time
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from tqdm import tqdm

from synth_engine.llm.client import run_llm_stream, run_llm_non_stream


def retry_llm_run(run_llm_func, max_retries: int = 5):
    """重试装饰器"""
    def wrapper(query, **config):
        model = config.get("model", "unknown")
        cfg_sleep = config.get("sleep", 0)
        for i in range(max_retries):
            try:
                sleep_sec = 0
                out = run_llm_func(query, **config)
                time.sleep(cfg_sleep)
            except Exception as e:
                sleep_sec = np.random.uniform(1, 5)
                print(f"retry {i}, model={model}, sleep={sleep_sec:.2f}s, reason={e}")
                out = {"err_msg": f"failed, model: {model}"}
            if out.get("status_code") == 200 and not out.get("err_msg"):
                return out
            time.sleep(sleep_sec)
        return out
    return wrapper


def run_llm_para(
    queries: List[str],
    para: int,
    config_lst: List[Dict[str, Any]],
) -> Optional[pd.DataFrame]:
    """
    并行调用多个 LLM，负载均衡（轮询分配模型）。

    Args:
        queries: prompt 列表
        para: 并行度
        config_lst: 模型配置列表

    Returns:
        DataFrame with idx, question, response, model, etc.
    """
    futures = {}
    results = []

    # 过滤非千问模型（避免敏感词拒答）
    filtered_cfg = [c for c in config_lst if "qwen" not in c.get("model", "")]

    with ThreadPoolExecutor(max_workers=para) as exe:
        for i, q in enumerate(queries):
            # 负载均衡
            if "六四" not in q or len(filtered_cfg) == 0:
                cfg = config_lst[i % len(config_lst)]
            else:
                cfg = np.random.choice(filtered_cfg)

            stream = cfg.get("stream", False)
            run_func = run_llm_stream if stream else run_llm_non_stream
            wrapped = retry_llm_run(run_func)
            future = exe.submit(wrapped, q, **cfg)
            futures[future] = i

        for future in tqdm(as_completed(futures), total=len(queries), desc="LLM calls"):
            idx = futures[future]
            out = future.result()
            out["idx"] = idx
            results.append(out)

    if not results:
        return None

    df_out = pd.DataFrame(results).set_index("idx").sort_index()
    return df_out


def run_llm_para_with_assign(
    queries: List[Tuple[str, Dict[str, Any]]],
    para: int,
) -> Optional[pd.DataFrame]:
    """
    并行调用多个 LLM，每个 query 指定一个模型配置。

    Args:
        queries: [(prompt, config), ...]
        para: 并行度
    """
    futures = {}
    results = []

    with ThreadPoolExecutor(max_workers=para) as exe:
        for i, (q, cfg) in enumerate(queries):
            stream = cfg.get("stream", False)
            run_func = run_llm_stream if stream else run_llm_non_stream
            wrapped = retry_llm_run(run_func)
            future = exe.submit(wrapped, q, **cfg)
            futures[future] = i

        for future in tqdm(as_completed(futures), total=len(queries), desc="LLM calls"):
            idx = futures[future]
            out = future.result()
            out["idx"] = idx
            results.append(out)

    if not results:
        return None

    df_out = pd.DataFrame(results).set_index("idx").sort_index()
    return df_out
