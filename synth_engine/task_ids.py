"""生成用户可读且全局唯一的任务 ID。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo


TASK_TYPES = {"quality_bef", "quality_after", "synth"}
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def generate_task_id(
    username: str,
    task_type: str,
    *,
    now: Optional[datetime] = None,
    uuid_hex: Optional[str] = None,
) -> str:
    if task_type not in TASK_TYPES:
        raise ValueError(f"不支持的任务类型: {task_type}")
    current = now or datetime.now(BEIJING_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=BEIJING_TZ)
    else:
        current = current.astimezone(BEIJING_TZ)
    unique = (uuid_hex or uuid.uuid4().hex).replace("-", "").lower()
    if len(unique) != 32 or any(ch not in "0123456789abcdef" for ch in unique):
        raise ValueError("UUID 必须为 32 位十六进制字符串")
    return f"{username}_{task_type}_{current.strftime('%y%m%d%H%M%S')}_{unique}"
