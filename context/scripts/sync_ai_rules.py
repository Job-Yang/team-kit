#!/usr/bin/env python3
"""同步团队代码红线到业务仓规则文件，或按当前任务抽取精简上下文包。"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tc_common as C

TASK_FILES: dict[str, list[str]] = {
    "feature": ["business.md", "standards.md", "pitfalls.md", "code-graph.json"],
    "debug": ["platforms.json", "pitfalls.md", "owners.md", "code-graph.json"],
    "metrics": ["metrics.md", "business.md", "owners.md"],
    "review": ["standards.md", "pitfalls.md"],
}


def read_clean_md(path: Path) -> tuple[dict[str, str], str]:
    if not path.is_file():
        return {}, ""
    return C.parse_frontmatter(path.read_text(encoding="utf-8"))


def build_rules_text(data_dir: Path, fmt: str) -> str:
    """生成给 AI 编程工具消费的团队红线规则文件。"""
    _, standards_body = read_clean_md(data_dir / "standards.md")
    _, pitfalls_body = read_clean_md(data_dir / "pitfalls.md")
    _, business_body = read_clean_md(data_dir / "business.md")

    platforms_cmds: list[str] = []
    p_file = data_dir / "platforms.json"
    if p_file.is_file():
        try:
            pdata = json.loads(p_file.read_text(encoding="utf-8"))
            for item in pdata.get("items", []):
                if item.get("command"):
                    platforms_cmds.append(f"- **{item.get('name', '')}**：`{item['command']}`")
        except Exception:
            pass

    team_name = "当前团队"
    if p_file.is_file():
        try:
            team_name = json.loads(p_file.read_text(encoding="utf-8")).get("team_name", team_name)
        except Exception:
            pass

    lines: list[str] = []
    if fmt == "cursor":
        lines.extend(
            [
                "---",
                f"description: {team_name} 工程标准与代码红线（由 Team Context 自动同步）",
                "alwaysApply: true",
                "---",
                "",
            ]
        )

    lines.extend(
        [
            f"# {team_name} · AI 写代码红线与基础约定",
            "",
            f"> 由 Team Context 自动生成（日期：{datetime.date.today().isoformat()}）。请勿直接手工修改本文件，有新经验请更新团队 `data/` 后重新同步。",
            "",
        ]
    )
    if business_body.strip():
        summary_lines = [ln for ln in business_body.strip().splitlines()[:12] if ln.strip()]
        lines.extend(["## 团队业务背景速览", "", *summary_lines, ""])

    if standards_body.strip():
        lines.extend(["## 编码规范与禁止越过的边界", "", standards_body.strip(), ""])

    if pitfalls_body.strip():
        lines.extend(["## 历史大坑与绝不能误删的代码", "", pitfalls_body.strip(), ""])

    if platforms_cmds:
        lines.extend(["## 常用研发命令速查", "", *platforms_cmds[:10], ""])

    return "\n".join(lines).rstrip() + "\n"


def build_task_context(data_dir: Path, task: str) -> str:
    """按任务类型抽取最相关的几份团队上下文。"""
    files = TASK_FILES.get(task, TASK_FILES["feature"])
    chunks = [
        f"# 当前任务上下文包（场景：{task}）",
        "",
        "以下内容来自团队 Team Context，请作为当前改码或排查时的真实约束与线索：",
        "",
    ]
    for fname in files:
        fpath = data_dir / fname
        if not fpath.is_file():
            continue
        if fname.endswith(".json"):
            try:
                obj = json.loads(fpath.read_text(encoding="utf-8"))
            except Exception:
                continue
            if fname == "code-graph.json":
                chunks.append("## 模块分布与活跃负责人")
                for n in obj.get("nodes", [])[:15]:
                    owners = "、".join(n.get("owners", [])) or "未标注"
                    chunks.append(
                        f"- `{n.get('label', n.get('id'))}`（{n.get('group', '')}，负责：{owners}）：{n.get('summary', '')}"
                    )
                chunks.append("")
            elif fname == "platforms.json":
                chunks.append("## 常用排查与环境入口")
                for item in obj.get("items", [])[:12]:
                    line = f"- **{item.get('name', '')}**（{item.get('category', '')}）"
                    if item.get("command"):
                        line += f" · 命令：`{item['command']}`"
                    if item.get("url"):
                        line += f" · 入口：{item['url']}"
                    chunks.append(line)
                chunks.append("")
        else:
            meta, body = read_clean_md(fpath)
            stale_note = ""
            if meta.get("updated") and meta.get("review_cycle"):
                f_info = C.check_freshness(meta["updated"], meta["review_cycle"])
                if f_info["status"] == "expired":
                    stale_note = f"（注意：此文件已超核对周期，上次更新 {meta['updated']}）"
            chunks.append(f"## 来自 `{fname}` {stale_note}".strip())
            chunks.append("")
            chunks.append(body.strip())
            chunks.append("")

    return "\n".join(chunks).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="同步团队代码红线到 AI 规则或按任务生成精简上下文")
    parser.add_argument("--data", default="data", help="团队数据目录（默认 data）")
    parser.add_argument("--mode", choices=["rules", "context"], default="rules", help="rules=生成规则文件；context=按任务抽取上下文")
    parser.add_argument("--format", choices=["agents", "claude", "cursor"], default="agents", help="rules 模式输出格式")
    parser.add_argument("--task", choices=["feature", "debug", "metrics", "review"], default="feature", help="context 模式任务类型")
    parser.add_argument("--target", default="", help="输出文件路径（留空则打印到标准输出）")
    args = parser.parse_args()

    data_dir = Path(args.data)
    if not data_dir.is_dir():
        print(f"[错误] 数据目录不存在: {data_dir}", file=sys.stderr)
        return 1

    output = build_rules_text(data_dir, args.format) if args.mode == "rules" else build_task_context(data_dir, args.task)

    if args.target:
        target = Path(args.target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
        print(f"已写入 {args.mode} 输出: {target.resolve()}")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
