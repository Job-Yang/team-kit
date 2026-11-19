#!/usr/bin/env python3
"""通用适配器：从本地 Git 仓库自动统计高频改动/热修文件，合并写入 snapshot.json 的 engineering.rework_files。"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

IGNORE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".lock", ".md"}


def _run_git_log(repo: Path, days: int) -> list[tuple[str, str]]:
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "log",
            f"--since={days} days ago",
            "--no-merges",
            "--name-only",
            "--pretty=format:@@@%s",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git log 失败: {repo}")

    commits: list[tuple[str, list[str]]] = []
    cur_subj = ""
    cur_files: list[str] = []
    for raw in proc.stdout.splitlines():
        if raw.startswith("@@@"):
            if cur_subj or cur_files:
                commits.append((cur_subj, cur_files))
            cur_subj = raw[3:].strip()
            cur_files = []
        elif raw.strip():
            cur_files.append(raw.strip())
    if cur_subj or cur_files:
        commits.append((cur_subj, cur_files))

    pairs: list[tuple[str, str]] = []
    for subj, files in commits:
        for fp in set(files):
            pairs.append((fp, subj))
    return pairs


def collect_rework(repos: list[Path], days: int, top: int) -> list[dict]:
    counts: Counter[str] = Counter()
    subjects: defaultdict[str, list[str]] = defaultdict(list)
    multi = len(repos) > 1

    for repo in repos:
        if not (repo / ".git").exists():
            raise FileNotFoundError(f"不是 Git 仓库: {repo}")
        prefix = f"{repo.name}/" if multi else ""
        for fp, subj in _run_git_log(repo, days):
            if Path(fp).suffix.lower() in IGNORE_EXTS:
                continue
            key = prefix + fp
            counts[key] += 1
            if subj and subj not in subjects[key]:
                subjects[key].append(subj)

    rows: list[dict] = []
    for fp, cnt in counts.most_common(top):
        parts = Path(fp).parts
        module = parts[0] if len(parts) <= 1 else f"{parts[0]}/{parts[1]}"
        reason_list = subjects[fp][:2]
        reason = "；".join(reason_list) if reason_list else "近周期连续修改"
        if len(reason) > 70:
            reason = reason[:67] + "..."
        rows.append({"file": fp, "rework_7d": cnt, "module": module, "reason": reason})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="从 Git 历史自动采集高频修改/热修文件并更新 radar snapshot.json")
    parser.add_argument("--snapshot", required=True, help="目标 snapshot.json 路径")
    parser.add_argument("--repo", action="append", required=True, help="目标 Git 仓库路径（支持多次传入）")
    parser.add_argument("--days", type=int, default=7, help="统计天数窗口（默认 7 天）")
    parser.add_argument("--top", type=int, default=6, help="最多保留前多少个文件（默认 6）")
    parser.add_argument("--product-name", default="研发团队", help="若快照新建时的默认产品名")
    args = parser.parse_args()

    repos = [Path(r).resolve() for r in args.repo]
    try:
        rows = collect_rework(repos, args.days, args.top)
    except Exception as exc:
        print(f"[错误] 统计 Git 返工失败: {exc}", file=sys.stderr)
        return 1

    snap_path = Path(args.snapshot)
    if snap_path.is_file():
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
    else:
        snap = {
            "meta": {"schema_version": "1.0", "source_adapter": "git_rework"},
            "product_name": args.product_name,
            "window": f"近 {args.days} 天 Git 提交分析",
            "updated": datetime.date.today().isoformat(),
            "status_lights": [],
            "flow": {"nodes": [], "edges": []},
            "timeline": {"dates": [], "biz_conv": [], "tech_p90_ms": [], "crash_rate": [], "changes": []},
            "engineering": {"subteams": [], "rework_files": [], "time_sinks": []},
        }

    eng = snap.setdefault("engineering", {})
    eng["rework_files"] = rows
    snap["updated"] = datetime.date.today().isoformat()

    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {len(rows)} 条高频改动文件记录 -> {snap_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
