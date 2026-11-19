#!/usr/bin/env python3
"""只读 Git 与代码结构扫描器：提取热改文件、共变文件对、回滚提交、目录作者与代码关系图草稿。"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "Pods",
    ".build",
    "build",
    "dist",
    "DerivedData",
    "__pycache__",
    ".venv",
    "venv",
    "target",
    ".idea",
    ".vscode",
}

CODE_EXTS = {
    ".swift",
    ".m",
    ".mm",
    ".h",
    ".kt",
    ".java",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".go",
    ".rs",
}

IMPORT_PATTERNS = [
    re.compile(r'^\s*import\s+([A-Za-z0-9_./@-]+)'),
    re.compile(r'^\s*from\s+([A-Za-z0-9_.]+)\s+import\s+'),
    re.compile(r'^\s*#import\s+[<"]([^">]+)[">]'),
    re.compile(r'^\s*#include\s+[<"]([^">]+)[">]'),
    re.compile(r'require\(\s*[\'"]([^\'"]+)[\'"]\s*\)'),
]


def run_git(repo: Path, args: list[str]) -> str:
    """只读运行 git 命令，失败抛出 RuntimeError。"""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} 失败")
    return proc.stdout


def parse_commits_with_files(repo: Path, days: int) -> list[dict[str, object]]:
    """一次读取近 N 天提交，返回 [{hash, author, date, subject, files}]。"""
    raw = run_git(
        repo,
        [
            "log",
            f"--since={days} days ago",
            "--no-merges",
            "--name-only",
            "--pretty=format:@@@%H\t%an\t%ad\t%s",
            "--date=short",
        ],
    )
    commits: list[dict[str, object]] = []
    cur: dict[str, object] | None = None
    for line in raw.splitlines():
        if line.startswith("@@@"):
            if cur is not None:
                commits.append(cur)
            parts = line[3:].split("\t", 3)
            h = parts[0] if len(parts) > 0 else ""
            author = parts[1] if len(parts) > 1 else "unknown"
            date = parts[2] if len(parts) > 2 else ""
            subject = parts[3] if len(parts) > 3 else ""
            cur = {
                "hash": h[:8],
                "author": author,
                "date": date,
                "subject": subject,
                "files": [],
            }
        elif line.strip() and cur is not None:
            files = cur["files"]
            assert isinstance(files, list)
            files.append(line.strip())
    if cur is not None:
        commits.append(cur)
    return commits


def get_risk_commits(repo: Path, days: int = 180, limit: int = 40) -> list[dict[str, str]]:
    """检索回滚、紧急修复、缺陷修复记录。"""
    raw = run_git(
        repo,
        [
            "log",
            f"--since={days} days ago",
            "--grep=revert\\|hotfix\\|fix",
            "-i",
            "--pretty=format:%h\t%ad\t%an\t%s",
            "--date=short",
            "-n",
            str(limit),
        ],
    )
    rows: list[dict[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 3)
        rows.append(
            {
                "hash": parts[0] if len(parts) > 0 else "",
                "date": parts[1] if len(parts) > 1 else "",
                "author": parts[2] if len(parts) > 2 else "",
                "subject": parts[3] if len(parts) > 3 else "",
            }
        )
    return rows


def module_bucket(file_path: str) -> str:
    """把文件路径归入模块名（取最多前两级目录）。"""
    parts = Path(file_path).parts
    if len(parts) <= 1:
        return "(根目录)"
    if len(parts) == 2:
        return parts[0]
    return f"{parts[0]}/{parts[1]}"


def scan_module_graph(
    repo: Path,
    hot_counts_by_mod: Counter[str],
    mod_authors: dict[str, Counter[str]],
    repo_web_url: str,
) -> dict[str, object]:
    """扫描目录与轻量 import 依赖，生成可直接在网页中预览的代码关系图草稿。"""
    mod_files: defaultdict[str, list[Path]] = defaultdict(list)
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        rel_root = Path(root).relative_to(repo)
        for fname in files:
            p = Path(root) / fname
            if p.suffix.lower() not in CODE_EXTS:
                continue
            rel_file = (rel_root / fname).as_posix()
            mod = module_bucket(rel_file)
            mod_files[mod].append(p)

    # 限制节点规模在 30 以内，按文件数 + 热改数排序取核心模块
    ranked_mods = sorted(
        mod_files.keys(),
        key=lambda m: (hot_counts_by_mod.get(m, 0) * 3 + len(mod_files[m])),
        reverse=True,
    )[:28]
    ranked_set = set(ranked_mods)

    # 模块短名用于匹配 import
    short_to_mods: defaultdict[str, list[str]] = defaultdict(list)
    for m in ranked_mods:
        short_to_mods[m.split("/")[-1].lower()].append(m)

    edge_counter: Counter[tuple[str, str]] = Counter()
    for mod in ranked_mods:
        for fpath in mod_files[mod][:80]:
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in text.splitlines()[:120]:
                for pat in IMPORT_PATTERNS:
                    m_imp = pat.search(line)
                    if not m_imp:
                        continue
                    token = m_imp.group(1).strip("./")
                    parts = [p.lower() for p in re.split(r"[/.:]", token) if p]
                    for part in parts:
                        for target in short_to_mods.get(part, []):
                            if target != mod and target in ranked_set:
                                edge_counter[(mod, target)] += 1

    nodes: list[dict[str, object]] = []
    for mod in ranked_mods:
        top_owners = [a for a, _ in mod_authors.get(mod, Counter()).most_common(3)]
        top_group = mod.split("/")[0] if "/" in mod else mod
        url = ""
        if repo_web_url:
            clean_base = repo_web_url.rstrip("/")
            sub = "" if mod == "(根目录)" else f"/tree/main/{mod}"
            url = f"{clean_base}{sub}"
        nodes.append(
            {
                "id": mod,
                "label": mod,
                "group": top_group,
                "file_count": len(mod_files[mod]),
                "hot_changes": hot_counts_by_mod.get(mod, 0),
                "owners": top_owners,
                "summary": f"自动扫描模块：{len(mod_files[mod])} 个源码文件，近周期修改 {hot_counts_by_mod.get(mod, 0)} 次（待人工补全职责描述）",
                "url": url,
                "local_path": "" if mod == "(根目录)" else mod,
            }
        )

    edges: list[dict[str, object]] = []
    for (src, dst), weight in edge_counter.most_common(45):
        edges.append({"source": src, "target": dst, "label": f"引用 ({weight})", "weight": weight})

    return {
        "schema": "team-context-code-graph/v1",
        "updated": datetime.date.today().isoformat(),
        "repo_name": repo.name,
        "repo_web_url": repo_web_url,
        "nodes": nodes,
        "edges": edges,
    }


def write_scan_report(
    out_dir: Path,
    repo_label: str,
    days: int,
    summary: dict[str, object],
) -> None:
    """生成给人直接扫读的扫描报告草稿。"""
    lines = [
        "---",
        f"updated: {datetime.date.today().isoformat()}",
        "review_cycle: 30d",
        f"source_repo: {repo_label}",
        "---",
        "",
        f"# 代码库只读扫描草稿：{repo_label}",
        "",
        f"> 统计窗口：近 {days} 天，有效非合并提交 {summary['commit_count']} 次。"
        "本文件为草稿，请核对后将稳定结构合入正式目录。",
        "",
        "## 近 90 天热改文件 Top 20",
        "",
        "| 文件路径 | 修改次数 | 所属模块 |",
        "| --- | --- | --- |",
    ]
    for item in summary["hot_files"][:20]:  # type: ignore[index]
        lines.append(f"| `{item['file']}` | {item['count']} | `{item['module']}` |")

    lines.extend(["", "## 常一起修改的耦合文件对 Top 15", "", "| 文件 A | 文件 B | 共改次数 |", "| --- | --- | --- |"])
    for pair in summary["co_changes"][:15]:  # type: ignore[index]
        lines.append(f"| `{pair['file_a']}` | `{pair['file_b']}` | {pair['count']} |")

    lines.extend(["", "## 模块活跃维护者矩阵", "", "| 模块目录 | 热改总次 | 高频提交者 Top 3 |", "| --- | --- | --- |"])
    for row in summary["dir_owners"][:20]:  # type: ignore[index]
        owners_str = "、".join(f"{o['name']}({o['count']})" for o in row["owners"])
        lines.append(f"| `{row['module']}` | {row['hot_changes']} | {owners_str} |")

    lines.extend(["", "## 回滚与紧急修复提交（近 180 天）", "", "| Commit | 日期 | 提交人 | 说明 |", "| --- | --- | --- | --- |"])
    for rc in summary["risk_commits"][:20]:  # type: ignore[index]
        lines.append(f"| `{rc['hash']}` | {rc['date']} | {rc['author']} | {rc['subject']} |")

    (out_dir / "scan-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="只读扫描一个或多个 Git 代码仓，生成团队结构与热区草稿")
    parser.add_argument("--repo", action="append", required=True, help="目标 Git 代码仓库路径（可多次传入实现跨仓合并）")
    parser.add_argument("--days", type=int, default=90, help="统计最近多少天提交（默认 90）")
    parser.add_argument("--out", default="context/data/inbox/scan", help="草稿输出目录（默认 context/data/inbox/scan）")
    parser.add_argument("--repo-web-url", action="append", default=[], help="可选：代码库网页根地址，按顺序对应 --repo")
    args = parser.parse_args()

    repos = [Path(r).resolve() for r in args.repo]
    for repo in repos:
        if not (repo / ".git").exists():
            print(f"[错误] 目标路径不是 Git 仓库: {repo}", file=sys.stderr)
            return 1

    multi_mode = len(repos) > 1
    file_counter: Counter[str] = Counter()
    co_change_counter: Counter[tuple[str, str]] = Counter()
    mod_hot: Counter[str] = Counter()
    mod_authors: dict[str, Counter[str]] = defaultdict(Counter)
    all_risk_commits: list[dict[str, str]] = []
    merged_nodes: list[dict[str, object]] = []
    merged_edges: list[dict[str, object]] = []
    total_commits = 0

    for idx, repo in enumerate(repos):
        web_url = args.repo_web_url[idx] if idx < len(args.repo_web_url) else ""
        try:
            commits = parse_commits_with_files(repo, args.days)
            risk_commits = get_risk_commits(repo)
        except Exception as exc:
            print(f"[错误] 扫描 Git 历史失败 ({repo.name}): {exc}", file=sys.stderr)
            return 1

        total_commits += len(commits)
        local_mod_hot: Counter[str] = Counter()
        local_mod_authors: dict[str, Counter[str]] = defaultdict(Counter)
        prefix = f"{repo.name}/" if multi_mode else ""

        for c in commits:
            files = sorted(set(c["files"]))  # type: ignore[arg-type]
            author = str(c["author"])
            for f in files:
                mod = module_bucket(f)
                full_f = prefix + f
                full_mod = prefix + mod
                file_counter[full_f] += 1
                mod_hot[full_mod] += 1
                mod_authors[full_mod][author] += 1
                local_mod_hot[mod] += 1
                local_mod_authors[mod][author] += 1
            if 2 <= len(files) <= 30:
                for i in range(len(files)):
                    for j in range(i + 1, len(files)):
                        co_change_counter[(prefix + files[i], prefix + files[j])] += 1

        for rc in risk_commits:
            rc_copy = dict(rc)
            if multi_mode:
                rc_copy["subject"] = f"[{repo.name}] {rc_copy['subject']}"
            all_risk_commits.append(rc_copy)

        sub_graph = scan_module_graph(repo, local_mod_hot, local_mod_authors, web_url)
        for n in sub_graph["nodes"]:  # type: ignore[attr-defined]
            node_copy = dict(n)
            if multi_mode:
                node_copy["id"] = f"{repo.name}/{node_copy['id']}"
                node_copy["label"] = f"{repo.name}/{node_copy['label']}"
                node_copy["group"] = repo.name
            merged_nodes.append(node_copy)
        for e in sub_graph["edges"]:  # type: ignore[attr-defined]
            edge_copy = dict(e)
            if multi_mode:
                edge_copy["source"] = f"{repo.name}/{edge_copy['source']}"
                edge_copy["target"] = f"{repo.name}/{edge_copy['target']}"
            merged_edges.append(edge_copy)

    all_risk_commits.sort(key=lambda x: x.get("date", ""), reverse=True)
    hot_files = [
        {"file": f, "count": cnt, "module": module_bucket(f)}
        for f, cnt in file_counter.most_common(30)
    ]
    co_changes = [
        {"file_a": a, "file_b": b, "count": cnt}
        for (a, b), cnt in co_change_counter.most_common(20)
    ]
    dir_owners = [
        {
            "module": mod,
            "hot_changes": mod_hot[mod],
            "owners": [{"name": n, "count": c} for n, c in mod_authors[mod].most_common(3)],
        }
        for mod, _ in mod_hot.most_common(25)
    ]

    repo_label = " + ".join(r.name for r in repos)
    summary = {
        "repo": str(repos[0]) if not multi_mode else [str(r) for r in repos],
        "repo_name": repo_label,
        "days": args.days,
        "commit_count": total_commits,
        "hot_files": hot_files,
        "co_changes": co_changes,
        "dir_owners": dir_owners,
        "risk_commits": all_risk_commits[:40],
    }
    graph_draft = {
        "schema": "team-context-code-graph/v1",
        "updated": datetime.date.today().isoformat(),
        "repo_name": repo_label,
        "repo_web_url": args.repo_web_url[0] if args.repo_web_url else "",
        "nodes": merged_nodes[:45],
        "edges": merged_edges[:60],
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scan-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "code-graph.draft.json").write_text(
        json.dumps(graph_draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_scan_report(out_dir, repo_label, args.days, summary)

    print(f"扫描完成：{repo_label}（近 {args.days} 天共 {total_commits} 次非合并提交）")
    print(f"  - 热改与耦合摘要: {out_dir / 'scan-summary.json'}")
    print(f"  - 可读扫描报告:   {out_dir / 'scan-report.md'}")
    print(f"  - 代码关系图草稿: {out_dir / 'code-graph.draft.json'}")
    print("提示：请先核对草稿并补齐模块说明，再合入正式 code-graph.json。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
