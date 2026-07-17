"""从单一配置文件加载系统级任务限制。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "system_limits.yaml"


@dataclass(frozen=True)
class TaskItemLimits:
    synthesis: int
    qc_pre: int
    qc_post: int


@dataclass(frozen=True)
class ModelParallelismLimits:
    default: int
    max: int


@dataclass(frozen=True)
class SystemLimits:
    task_items: TaskItemLimits
    model_parallelism: ModelParallelismLimits
    max_concurrent_tasks: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_items": {
                "synthesis": self.task_items.synthesis,
                "qc_pre": self.task_items.qc_pre,
                "qc_post": self.task_items.qc_post,
            },
            "model_parallelism": {
                "default": self.model_parallelism.default,
                "max": self.model_parallelism.max,
            },
            "max_concurrent_tasks": self.max_concurrent_tasks,
        }


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} 必须是大于等于 1 的整数")
    return value


def load_system_limits(config_path: Path | str | None = None) -> SystemLimits:
    """加载并严格校验系统限制配置。"""
    path = Path(config_path or os.getenv("SYNTH_LIMITS_CONFIG") or DEFAULT_CONFIG_PATH)
    if not path.is_file():
        raise RuntimeError(f"系统限制配置文件不存在: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)
    if not isinstance(raw, Mapping):
        raise ValueError(f"系统限制配置必须是 YAML 对象: {path}")

    task_items = raw.get("task_items")
    parallelism = raw.get("model_parallelism")
    if not isinstance(task_items, Mapping):
        raise ValueError("task_items 必须是 YAML 对象")
    if not isinstance(parallelism, Mapping):
        raise ValueError("model_parallelism 必须是 YAML 对象")

    limits = SystemLimits(
        task_items=TaskItemLimits(
            synthesis=_positive_int(task_items.get("synthesis"), "task_items.synthesis"),
            qc_pre=_positive_int(task_items.get("qc_pre"), "task_items.qc_pre"),
            qc_post=_positive_int(task_items.get("qc_post"), "task_items.qc_post"),
        ),
        model_parallelism=ModelParallelismLimits(
            default=_positive_int(parallelism.get("default"), "model_parallelism.default"),
            max=_positive_int(parallelism.get("max"), "model_parallelism.max"),
        ),
        max_concurrent_tasks=_positive_int(
            raw.get("max_concurrent_tasks"), "max_concurrent_tasks"
        ),
    )
    if limits.model_parallelism.default > limits.model_parallelism.max:
        raise ValueError("model_parallelism.default 不能大于 model_parallelism.max")
    return limits


# 服务启动时读取一次。修改 YAML 后重启服务即可让前后端同时使用新值。
LIMITS = load_system_limits()
