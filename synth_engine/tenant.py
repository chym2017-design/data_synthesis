"""用户与工作空间隔离。

网页登录由 Nginx Basic Auth 完成。本模块只接受 Nginx 覆盖写入的
``X-Authenticated-User``，并把用户名映射到服务器上的独立工作空间。
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import threading
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import HTTPException, Request


APP_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(os.getenv("SYNTH_DATA_ROOT", APP_ROOT / "data"))
WORKSPACES_ROOT = Path(os.getenv("SYNTH_WORKSPACES_ROOT", APP_ROOT / "workspaces"))
USERS_DB = Path(os.getenv("SYNTH_USERS_DB", DATA_ROOT / "users.db"))
DEFAULT_CONFIGS_DIR = APP_ROOT / "configs"
DEFAULT_TEMPLATES_DIR = APP_ROOT / "synth_engine" / "templates"
DEFAULT_RESOURCES_DIR = APP_ROOT / "synth_engine" / "resources"

USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,31}$")
_db_lock = threading.RLock()


@dataclass(frozen=True)
class WorkspaceContext:
    username: str
    workspace_id: str
    root: Path

    @property
    def configs_dir(self) -> Path:
        return self.root / "configs"

    @property
    def templates_dir(self) -> Path:
        return self.root / "templates"

    @property
    def resources_dir(self) -> Path:
        return self.root / "resources"

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"


_current_workspace: ContextVar[Optional[WorkspaceContext]] = ContextVar(
    "current_workspace", default=None
)


def _connect() -> sqlite3.Connection:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(USERS_DB), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def init_tenant_store() -> None:
    WORKSPACES_ROOT.mkdir(parents=True, exist_ok=True)
    with _db_lock, _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def validate_username(username: str) -> str:
    username = (username or "").strip()
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("用户名必须为 2-32 位字母、数字、点、下划线或短横线")
    return username


def _seed_workspace(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    configs_dir = root / "configs"
    templates_dir = root / "templates"
    resources_dir = root / "resources"
    runs_dir = root / "runs"

    if DEFAULT_CONFIGS_DIR.exists() and not configs_dir.exists():
        shutil.copytree(
            DEFAULT_CONFIGS_DIR,
            configs_dir,
            ignore=shutil.ignore_patterns("system_limits.yaml"),
        )
    else:
        configs_dir.mkdir(parents=True, exist_ok=True)

    if DEFAULT_TEMPLATES_DIR.exists() and not templates_dir.exists():
        shutil.copytree(
            DEFAULT_TEMPLATES_DIR,
            templates_dir,
            ignore=shutil.ignore_patterns("*.py", "*.pyc", "__pycache__"),
        )
    else:
        templates_dir.mkdir(parents=True, exist_ok=True)

    if DEFAULT_RESOURCES_DIR.exists() and not resources_dir.exists():
        shutil.copytree(DEFAULT_RESOURCES_DIR, resources_dir)
    else:
        resources_dir.mkdir(parents=True, exist_ok=True)

    (runs_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (runs_dir / "qc_results").mkdir(parents=True, exist_ok=True)


def create_user(username: str) -> WorkspaceContext:
    init_tenant_store()
    username = validate_username(username)
    with _db_lock, _connect() as conn:
        existing = conn.execute(
            "SELECT username, workspace_id, active FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if existing:
            ctx = workspace_for_user(username, require_active=False)
            assert ctx is not None
            _seed_workspace(ctx.root)
            return ctx

        workspace_id = f"{username}-{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO users(username, workspace_id, active) VALUES (?, ?, 1)",
            (username, workspace_id),
        )

    ctx = WorkspaceContext(username, workspace_id, WORKSPACES_ROOT / workspace_id)
    try:
        _seed_workspace(ctx.root)
    except Exception:
        with _db_lock, _connect() as conn:
            conn.execute("DELETE FROM users WHERE username = ?", (username,))
        raise
    return ctx


def migrate_workspace_names() -> List[Dict[str, str]]:
    """把旧 UUID 目录改成“用户名-短标识”，保留全部文件和用户映射。"""
    init_tenant_store()
    migrated: List[Dict[str, str]] = []
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            "SELECT username, workspace_id FROM users ORDER BY username"
        ).fetchall()
        for row in rows:
            username = row["username"]
            old_id = row["workspace_id"]
            if old_id.startswith(f"{username}-"):
                continue
            suffix = re.sub(r"[^a-zA-Z0-9]", "", old_id)[:8] or uuid.uuid4().hex[:8]
            new_id = f"{username}-{suffix}"
            old_root = WORKSPACES_ROOT / old_id
            new_root = WORKSPACES_ROOT / new_id
            if new_root.exists():
                raise RuntimeError(f"目标工作空间已存在: {new_root}")
            moved = False
            if old_root.exists():
                old_root.rename(new_root)
                moved = True
            try:
                conn.execute(
                    "UPDATE users SET workspace_id = ? WHERE username = ? AND workspace_id = ?",
                    (new_id, username, old_id),
                )
                conn.commit()
            except Exception:
                if moved and new_root.exists() and not old_root.exists():
                    new_root.rename(old_root)
                raise
            migrated.append({"username": username, "old": old_id, "new": new_id})
    return migrated


def workspace_for_user(
    username: str, *, require_active: bool = True
) -> Optional[WorkspaceContext]:
    init_tenant_store()
    with _db_lock, _connect() as conn:
        row = conn.execute(
            "SELECT username, workspace_id, active FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row or (require_active and not row["active"]):
        return None
    return WorkspaceContext(
        row["username"], row["workspace_id"], WORKSPACES_ROOT / row["workspace_id"]
    )


def set_user_active(username: str, active: bool) -> bool:
    init_tenant_store()
    username = validate_username(username)
    with _db_lock, _connect() as conn:
        cur = conn.execute(
            "UPDATE users SET active = ? WHERE username = ?",
            (1 if active else 0, username),
        )
        return cur.rowcount > 0


def list_users() -> List[Dict[str, object]]:
    init_tenant_store()
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            "SELECT username, workspace_id, active, created_at FROM users ORDER BY username"
        ).fetchall()
    return [dict(row) for row in rows]


def bind_request_workspace(request: Request):
    username = (request.headers.get("X-Authenticated-User") or "").strip()
    dev_user = os.getenv("SYNTH_DEV_USER", "").strip()
    client_host = request.client.host if request.client else ""
    if not username and dev_user and client_host in {"127.0.0.1", "::1", "testclient"}:
        username = dev_user
    if not username:
        raise HTTPException(status_code=401, detail="缺少已认证用户信息")
    try:
        validate_username(username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ctx = workspace_for_user(username)
    if ctx is None:
        raise HTTPException(
            status_code=403,
            detail="账号已通过网页密码验证，但尚未由管理员分配工作空间",
        )
    _seed_workspace(ctx.root)
    return _current_workspace.set(ctx)


def reset_request_workspace(token) -> None:
    _current_workspace.reset(token)


def current_workspace() -> WorkspaceContext:
    ctx = _current_workspace.get()
    if ctx is None:
        raise HTTPException(status_code=401, detail="当前请求没有工作空间")
    return ctx
