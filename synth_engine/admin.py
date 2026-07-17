"""由 ECS 管理员调用的用户/工作空间管理命令。"""

from __future__ import annotations

import argparse
import json

from synth_engine.tenant import (
    create_user,
    list_users,
    migrate_workspace_names,
    set_user_active,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Synth Engine 用户工作空间管理")
    sub = parser.add_subparsers(dest="command", required=True)
    create_parser = sub.add_parser("create", help="创建用户映射和独立工作空间")
    create_parser.add_argument("username")
    sub.add_parser("list", help="列出用户及工作空间")
    sub.add_parser("migrate-names", help="把旧 UUID 工作空间迁移为用户名开头的名称")
    for name in ("enable", "disable"):
        item = sub.add_parser(name, help=f"{name} 用户")
        item.add_argument("username")

    args = parser.parse_args()
    if args.command == "create":
        ctx = create_user(args.username)
        print(json.dumps({
            "username": ctx.username,
            "workspace_id": ctx.workspace_id,
            "workspace": str(ctx.root),
        }, ensure_ascii=False))
        return 0
    if args.command == "list":
        print(json.dumps(list_users(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "migrate-names":
        print(json.dumps(migrate_workspace_names(), ensure_ascii=False, indent=2))
        return 0
    active = args.command == "enable"
    if not set_user_active(args.username, active):
        parser.error("用户不存在")
    print(f"{args.username}: {'enabled' if active else 'disabled'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
