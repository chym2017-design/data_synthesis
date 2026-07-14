"""
LLM 客户端模块

封装单模型 LLM 调用（stream / non-stream）。
"""

import time
import json
from typing import Any, Dict, Optional

import requests


def run_llm_stream(
    question: str,
    url: str,
    api_key: str,
    system_prompt: Optional[str] = None,
    verbose: bool = False,
    timeout: Optional[int] = None,
    **config: Any,
) -> Dict[str, Any]:
    """流式调用 LLM"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": question})

    data = {"messages": messages, "stream": True, **config}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    t_start = time.perf_counter()
    ttft = None
    full_response = []
    full_reasoning = []
    status_code = 200

    try:
        with requests.post(url=url, headers=headers, json=data, stream=True, timeout=timeout) as response:
            status_code = response.status_code
            if status_code != 200:
                return {
                    "question": question, "response": "", "status_code": status_code,
                    "err_msg": response.text, "model": config.get("model"),
                }

            for chunk in response.iter_lines():
                if chunk:
                    decoded = chunk.decode("utf-8").strip()
                    if decoded.startswith("data: "):
                        json_chunk = decoded[6:]
                        if json_chunk != "[DONE]":
                            try:
                                chunk_data = json.loads(json_chunk)
                                if "choices" in chunk_data:
                                    delta = chunk_data["choices"][0]["delta"]
                                    if delta.get("reasoning_content"):
                                        full_reasoning.append(delta["reasoning_content"])
                                    elif delta.get("content"):
                                        full_reasoning_content = ""
                                        content = delta["content"]
                                        full_response.append(content)
                                        if ttft is None:
                                            ttft = time.perf_counter() - t_start
                            except json.JSONDecodeError:
                                continue
    except Exception as e:
        return {
            "question": question, "response": "", "status_code": 0,
            "err_msg": str(e), "model": config.get("model"),
        }

    t_end = time.perf_counter()
    return {
        "ttft": ttft,
        "question": question,
        "duration": t_end - t_start,
        "model": config.get("model"),
        "response": "".join(full_response),
        "reasoning_content": "".join(full_reasoning),
        "status_code": status_code,
    }


def run_llm_non_stream(
    question: str,
    url: str,
    api_key: str,
    system_prompt: Optional[str] = None,
    timeout: Optional[int] = None,
    verbose: bool = False,
    **config: Any,
) -> Dict[str, Any]:
    """非流式调用 LLM"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": question})

    data = {"messages": messages, **config}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    t_start = time.perf_counter()
    try:
        with requests.post(url=url, headers=headers, json=data, stream=False, timeout=timeout) as response:
            if response.status_code != 200:
                return {
                    "question": question, "response": "", "status_code": response.status_code,
                    "err_msg": response.text, "model": config.get("model"),
                }
            resp_data = response.json()
            t_end = time.perf_counter()
            return {
                "question": question,
                "reasoning_content": resp_data["choices"][0]["message"].get("reasoning_content"),
                "response": resp_data["choices"][0]["message"]["content"],
                "duration": t_end - t_start,
                "prompt_tokens": resp_data.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": resp_data.get("usage", {}).get("completion_tokens", 0),
                "status_code": response.status_code,
                "model": config.get("model"),
            }
    except requests.ReadTimeout:
        return {
            "question": question, "response": "",
            "err_msg": f"timeout = {timeout}", "model": config.get("model"),
        }
    except Exception as e:
        return {
            "question": question, "response": "",
            "err_msg": f"Error: {e}", "model": config.get("model"),
        }
