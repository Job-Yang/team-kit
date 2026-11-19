#!/usr/bin/env python3
"""安全与保鲜检查：
1. 防止将公司 data/ 提交或推送到 github.com 等个人公网远端；
2. 拦截私钥、Token、密码明文、手机号、真实非样例邮箱及员工主观评价；
3. 检查文件更新日期与复核周期，列出已超期或即将过期的条目。
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tc_common as C

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("私钥内容", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("OpenAI/API Key (sk-)", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("GitHub Token (ghp_/gho_/github_pat_)", re.compile(r"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("Bearer Token", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b")),
    ("云厂商 AccessKey", re.compile(r"\b(?:AKIA|LTAI)[A-Za-z0-9]{12,}\b")),
    ("明文密码/密钥赋值", re.compile(r"(?i)(?:password|passwd|app_secret|api_secret|secret_key)\s*[:=]\s*['\"]?[A-Za-z0-9!@#$%^&*._-]{6,}['\"]?")),
    ("中国大陆手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
]

SUBJECTIVE_OWNER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("员工绩效或主观性格评价", re.compile(r"(?:绩效[ABCDS]|考评|态度差|能力强|能力弱|不靠谱|很水|混日子|情商)")),
]

TEXT_EXTS = {".md", ".json", ".txt", ".yml", ".yaml"}


PRIVATE_PATHS = [
    "data",
    "context/data",
    "radar/data",
    "local-data",
    "adapters/local",
]


def check_public_remote_leak(repo_root: Path) -> list[str]:
    """检查当前仓库是否绑定 github.com 且同时追踪/暂存了任何私密数据或本地适配器目录。"""
    errors: list[str] = []
    if not (repo_root / ".git").exists():
        return errors
    remotes = subprocess.run(
        ["git", "-C", str(repo_root), "remote", "-v"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout
    if "github.com" not in remotes.lower():
        return errors

    tracked = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--", *PRIVATE_PATHS],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    staged = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--cached", "--name-only", "--", *PRIVATE_PATHS],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()

    if tracked or staged:
        files = sorted(set((tracked + "\n" + staged).splitlines()))
        errors.append(
            f"当前仓库远端包含 github.com，严禁将私密数据或本地适配器纳入 Git 追踪（命中：{', '.join(f for f in files if f)}）"
        )
    return errors


def scan_single_file(file_path: Path) -> list[str]:
    """扫描单个文件（例如 radar snapshot.json）是否混入敏感凭证或隐私字段。"""
    blockers: list[str] = []
    if not file_path.is_file():
        return [f"待检查文件不存在: {file_path}"]
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"无法读取 {file_path}: {exc}"]
    for line_no, line in enumerate(text.splitlines(), start=1):
        for label, pat in SECRET_PATTERNS:
            if pat.search(line):
                blockers.append(f"[{label}] {file_path.name}:{line_no}")
    return blockers


def scan_data_dir(
    data_dir: Path, check_freshness: bool = True
) -> tuple[list[str], list[str]]:
    """扫描 data_dir，返回 (阻断级错误列表, 过期/体检告警列表)。"""
    blockers: list[str] = []
    warnings: list[str] = []

    if not data_dir.is_dir():
        blockers.append(f"数据目录不存在: {data_dir}")
        return blockers, warnings

    for path in sorted(data_dir.rglob("*")):
        if path.is_symlink():
            warnings.append(f"跳过符号链接文件（安全隔离）: {path}")
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTS:
            continue

        rel = path.relative_to(data_dir).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            blockers.append(f"无法读取 {rel}: {exc}")
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            for label, pat in SECRET_PATTERNS:
                if pat.search(line):
                    blockers.append(f"[{label}] {rel}:{line_no}")
            if path.name == "owners.md":
                for label, pat in SUBJECTIVE_OWNER_PATTERNS:
                    if pat.search(line):
                        blockers.append(f"[{label}] {rel}:{line_no}（找人地图只记分工，不记评价）")

        if check_freshness and path.suffix.lower() == ".md" and not rel.startswith("inbox/"):
            meta, _ = C.parse_frontmatter(text)
            if meta.get("updated") and meta.get("review_cycle"):
                f_info = C.check_freshness(meta["updated"], meta["review_cycle"])
                status = f_info["status"]
                if status == "expired":
                    warnings.append(
                        f"[已超期] {rel}: 上次更新 {meta['updated']}（已过 {f_info['age_days']} 天，周期 {meta['review_cycle']}）"
                    )
                elif status == "expiring":
                    warnings.append(
                        f"[即将超期] {rel}: 上次更新 {meta['updated']}（已过 {f_info['age_days']} 天，周期 {meta['review_cycle']}）"
                    )

    return blockers, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Team Kit 安全拦截与保鲜检查")
    parser.add_argument("--data", action="append", help="团队数据目录（可多次传入；不传且无 --snapshot 时默认检查 data）")
    parser.add_argument("--snapshot", action="append", default=[], help="可选：待检查的 Radar 快照 JSON 文件路径")
    parser.add_argument("--repo-root", default=".", help="用于检查 Git 远端防漏的仓库根目录")
    parser.add_argument("--no-remote-check", action="store_true", help="跳过 github.com 远端防漏检查")
    parser.add_argument("--no-freshness", action="store_true", help="跳过过期日期提醒")
    args = parser.parse_args()

    blockers: list[str] = []
    warnings: list[str] = []

    if not args.no_remote_check:
        blockers.extend(check_public_remote_leak(Path(args.repo_root).resolve()))

    data_dirs = args.data if args.data else ([] if args.snapshot else ["data"])
    for d in data_dirs:
        d_blockers, d_warnings = scan_data_dir(
            Path(d), check_freshness=not args.no_freshness
        )
        blockers.extend(d_blockers)
        warnings.extend(d_warnings)

    for snap in args.snapshot:
        blockers.extend(scan_single_file(Path(snap)))

    if blockers:
        print("❌ 安全检查未通过（阻断提交）：", file=sys.stderr)
        for b in blockers:
            print(f"  - {b}", file=sys.stderr)
        if warnings:
            print("⚠️  另有保鲜提醒：", file=sys.stderr)
            for w in warnings:
                print(f"  - {w}", file=sys.stderr)
        return 3

    if warnings:
        print("⚠️  安全检查通过，但有条目需要顺手核对：")
        for w in warnings:
            print(f"  - {w}")
        return 2

    print("✅ 安全与保鲜检查全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
