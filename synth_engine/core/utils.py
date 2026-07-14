"""
共享工具函数
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


def weighted_choice(choices: List[Any], weights: Optional[List[float]] = None) -> Any:
    """加权随机选择"""
    if weights is None:
        return np.random.choice(choices)
    return np.random.choice(choices, p=np.array(weights) / sum(weights))


def validate_prob_sum(probs: Dict[str, float], name: str = "probability") -> float:
    """验证概率总和，返回总和"""
    total = sum(probs.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"{name} 总和为 {total:.4f}，应为 1.0")
    return total


def ensure_dir(path: str) -> Path:
    """确保目录存在"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def parse_json_from_response(response: str) -> Optional[Dict]:
    """从 LLM 响应中提取 JSON"""
    try:
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def format_dict_to_yaml(data: Dict[str, Any]) -> str:
    """将字典格式化为 YAML 字符串（用于配置编辑器）"""
    import yaml
    return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)


def parse_yaml_string(yaml_str: str) -> Dict[str, Any]:
    """解析 YAML 字符串为字典"""
    import yaml
    return yaml.safe_load(yaml_str) or {}
