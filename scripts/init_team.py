#!/usr/bin/env python3
"""初始化当前团队的 data/ 与 data/inbox/ 目录结构（默认绝不覆盖已有文件）。"""

import argparse
import datetime
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATES = ROOT_DIR / "templates"


def init_team(
    data_dir: Path, team_name: str, templates_dir: Path, force: bool = False
) -> dict[str, list[str]]:
    """复制标准模板到 data_dir，返回创建与跳过文件清单。"""
    if not templates_dir.is_dir():
        raise FileNotFoundError(f"模板目录不存在: {templates_dir}")

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "inbox" / "scan").mkdir(parents=True, exist_ok=True)
    (data_dir / "history").mkdir(parents=True, exist_ok=True)

    today = datetime.date.today().isoformat()
    created: list[str] = []
    skipped: list[str] = []

    for src in sorted(templates_dir.iterdir()):
        if not src.is_file():
            continue
        dst = data_dir / src.name
        if dst.exists() and not force:
            skipped.append(src.name)
            continue
        if src.suffix.lower() in {".md", ".json", ".txt"}:
            content = src.read_text(encoding="utf-8")
            content = content.replace("{{TEAM_NAME}}", team_name)
            content = content.replace("{{TODAY}}", today)
            dst.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(src, dst)
        created.append(src.name)

    return {"created": created, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化团队 Team Context 数据目录")
    parser.add_argument("--data", default="data", help="目标数据目录路径（默认：data）")
    parser.add_argument("--team-name", default="我的研发团队", help="团队显示名称")
    parser.add_argument(
        "--templates",
        default=str(DEFAULT_TEMPLATES),
        help="模板目录路径（默认使用仓库内 templates/）",
    )
    parser.add_argument("--force", action="store_true", help="覆盖已存在的同名文件")
    args = parser.parse_args()

    try:
        res = init_team(
            Path(args.data), args.team_name, Path(args.templates), force=args.force
        )
    except Exception as exc:
        print(f"[错误] 初始化失败: {exc}", file=sys.stderr)
        return 1

    print(f"已初始化团队目录: {Path(args.data).resolve()}")
    print(f"  新建文件 ({len(res['created'])}): {', '.join(res['created']) or '无'}")
    print(f"  跳过已存在 ({len(res['skipped'])}): {', '.join(res['skipped']) or '无'}")
    print("  下一步：运行 scan_repo.py 扫描业务仓库，草稿将自动进入 data/inbox/scan/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
