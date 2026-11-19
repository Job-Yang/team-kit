#!/usr/bin/env python3
"""Team Context 公共解析与安全校验工具（仅依赖 Python 3 标准库）。"""

import datetime
import os
import re
from pathlib import Path


def safe_resolve_in_dir(base_dir: Path, rel_path: str) -> Path | None:
    """将相对路径安全解析到 base_dir 内，拒绝符号链接逃逸和目录穿越。"""
    if not rel_path or os.path.isabs(rel_path):
        return None
    base_real = base_dir.resolve()
    candidate = base_dir / rel_path
    if candidate.is_symlink():
        return None
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    if resolved == base_real or base_real in resolved.parents:
        return resolved
    return None


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """解析 Markdown 头部 --- ... --- 元数据（仅支持扁平 key: value），返回 (meta, 正文)。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}, text

    meta: dict[str, str] = {}
    for raw in lines[1:end_idx]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, val = stripped.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        meta[key] = val
    body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")
    return meta, body


def parse_cycle_days(review_cycle: str) -> int | None:
    """将 '30d' / '90d' 解析为整数天。"""
    if not review_cycle:
        return None
    m = re.fullmatch(r"(\d+)\s*[dD]", review_cycle.strip())
    if not m:
        return None
    days = int(m.group(1))
    return days if 1 <= days <= 3650 else None


def check_freshness(
    updated: str, review_cycle: str, today: datetime.date | None = None
) -> dict[str, object]:
    """根据 updated (YYYY-MM-DD) 与 review_cycle (Nd) 返回保鲜状态。"""
    if today is None:
        today = datetime.date.today()
    cycle_days = parse_cycle_days(review_cycle)
    if not updated or not cycle_days:
        return {"status": "unknown", "age_days": None, "cycle_days": cycle_days}
    try:
        updated_date = datetime.date.fromisoformat(updated.strip())
    except ValueError:
        return {"status": "unknown", "age_days": None, "cycle_days": cycle_days}

    age_days = (today - updated_date).days
    if age_days > cycle_days:
        status = "expired"
    elif age_days >= int(cycle_days * 0.8):
        status = "expiring"
    else:
        status = "ok"
    return {"status": status, "age_days": age_days, "cycle_days": cycle_days}
