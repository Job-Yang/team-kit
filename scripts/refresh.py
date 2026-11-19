#!/usr/bin/env python3
"""一键刷新入口：读取平台登记清单 sources.json，串联扫描代码仓、运行适配器、校验安全与编译输出。"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _run_py(script_rel: str, cmd_args: list[str], allow_rc2: bool = False) -> int:
    script_path = (ROOT_DIR / script_rel).resolve()
    if ROOT_DIR not in script_path.parents and script_path != ROOT_DIR:
        raise RuntimeError(f"安全限制：拒绝执行仓库外脚本 {script_rel}")
    if not script_path.is_file():
        raise FileNotFoundError(f"脚本不存在: {script_path}")

    cmd = [sys.executable, str(script_path), *cmd_args]
    proc = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if proc.returncode == 0 or (allow_rc2 and proc.returncode == 2):
        return proc.returncode
    raise RuntimeError(f"命令失败 (exit={proc.returncode}): {' '.join(cmd)}")


def _resolve_repo_path(raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else (ROOT_DIR / p).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="按 sources.json 一键刷新 Team Context 与 Team Radar")
    parser.add_argument("--sources", default="data/sources.json", help="平台与数据源清单路径（默认 data/sources.json）")
    parser.add_argument("--skip-scan", action="store_true", help="跳过 Git 仓库扫描步骤（加快日常报表刷新）")
    parser.add_argument("--no-remote-check", action="store_true", help="跳过 github.com 远端防漏检查（仅测试时使用）")
    args = parser.parse_args()

    src_path = _resolve_repo_path(args.sources)
    if not src_path.is_file():
        print(
            f"[错误] 找不到平台清单 {src_path}；请先复制 sources.example.json 到 data/sources.json 并按实际环境修改。",
            file=sys.stderr,
        )
        return 1

    cfg = json.loads(src_path.read_text(encoding="utf-8"))
    team_name = cfg.get("team_name", "我的研发团队")

    # 1. Context 流水线
    ctx_cfg = cfg.get("context") or {}
    ctx_data_dir = ctx_cfg.get("data_dir", "context/data")
    if ctx_cfg.get("enabled", False):
        print("=== [1/2] 刷新 Team Context ===")
        ctx_abs = _resolve_repo_path(ctx_data_dir)
        if not ctx_abs.is_dir():
            _run_py("context/scripts/init_team.py", ["--data", str(ctx_abs), "--team-name", str(team_name)])

        repos = ctx_cfg.get("repos") or []
        if repos and not args.skip_scan:
            scan_args: list[str] = []
            for r in repos:
                rpath = r.get("path") if isinstance(r, dict) else str(r)
                wurl = r.get("web_url", "") if isinstance(r, dict) else ""
                if rpath:
                    scan_args.extend(["--repo", str(_resolve_repo_path(rpath))])
                    scan_args.extend(["--repo-web-url", wurl])
            if scan_args:
                scan_args.extend(["--days", str(ctx_cfg.get("scan_days", 90)), "--out", str(ctx_abs / "inbox" / "scan")])
                _run_py("context/scripts/scan_repo.py", scan_args)

        safety_args = ["--data", str(ctx_abs), "--repo-root", str(ROOT_DIR)]
        if args.no_remote_check:
            safety_args.append("--no-remote-check")
        _run_py("context/scripts/check_safety.py", safety_args, allow_rc2=True)

        portal_args = ["--data", str(ctx_abs), "--out", str(_resolve_repo_path(ctx_cfg.get("out_html", "dist/context.html")))]
        if ctx_cfg.get("out_md"):
            portal_args.extend(["--export-md", str(_resolve_repo_path(ctx_cfg["out_md"]))])
        _run_py("context/scripts/build_portal.py", portal_args)

    # 2. Radar 流水线
    rad_cfg = cfg.get("radar") or {}
    if rad_cfg.get("enabled", False):
        print("=== [2/2] 刷新 Team Radar ===")
        merged_rel = rad_cfg.get("merged_snapshot", "radar/data/snapshot.merged.json")
        merged_abs = _resolve_repo_path(merged_rel)
        merged_abs.parent.mkdir(parents=True, exist_ok=True)

        base_rel = rad_cfg.get("base_snapshot", "")
        if base_rel:
            base_abs = _resolve_repo_path(base_rel)
            if not base_abs.is_file():
                raise FileNotFoundError(f"base_snapshot 不存在: {base_abs}")
            shutil.copy2(base_abs, merged_abs)

        for ad in rad_cfg.get("adapters") or []:
            if ad.get("enabled", True) is False:
                continue
            script_rel = ad.get("script", "")
            raw_args = [str(x) for x in (ad.get("args") or [])]
            print(f"  -> 运行适配器: {ad.get('name', script_rel)}")
            _run_py(script_rel, ["--snapshot", str(merged_abs), *raw_args])

        _run_py("radar/scripts/validate_snapshot.py", ["--input", str(merged_abs)])

        safety_snap_args = ["--snapshot", str(merged_abs), "--repo-root", str(ROOT_DIR)]
        if args.no_remote_check:
            safety_snap_args.append("--no-remote-check")
        _run_py("context/scripts/check_safety.py", safety_snap_args, allow_rc2=True)

        build_args = [
            "--input",
            str(merged_abs),
            "--out",
            str(_resolve_repo_path(rad_cfg.get("out_html", "dist/radar.html"))),
            "--tokens-out",
            str(_resolve_repo_path(rad_cfg.get("out_tokens", "dist/tokens.json"))),
        ]
        if rad_cfg.get("link_context", True):
            ctx_abs = _resolve_repo_path(ctx_data_dir)
            if ctx_abs.is_dir():
                build_args.extend(["--context-dir", str(ctx_abs)])
        _run_py("radar/scripts/build_radar.py", build_args)

    print("✅ Team Kit 一键刷新完成！")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        sys.exit(1)
