#!/usr/bin/env python3
"""校验 Team Radar 标准快照 JSON（snapshot.json）结构与数据类型。"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

KNOWN_THRESHOLD_KEYS = {
    "crash_danger",
    "p90_danger_ms",
    "conv_drop_warn",
    "version_drop_warn",
    "backtrack_warn",
    "rage_click_warn",
    "ai_correct_warn",
    "stream_abort_warn",
    "drop3_warn",
    "api_err_danger",
    "on_time_min",
    "on_time_mom_drop",
    "rework_hot_count",
}

VALID_ELEMENT_STATUS = {"ok", "warn", "danger"}
VALID_LIGHT_LEVEL = {"ok", "warn", "danger"}


def _is_num(val: object) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def validate_snapshot(data: object) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)。errors 非空代表快照结构存在会导致分析或渲染出错的缺陷。"""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return ["顶层必须是 JSON object（字典结构）"], warnings

    product_name = data.get("product_name")
    if not isinstance(product_name, str) or not product_name.strip():
        errors.append("缺少有效的顶层字符串字段 `product_name`")

    window = data.get("window")
    if not isinstance(window, str) or not window.strip():
        warnings.append("建议填写 `window`（例如：近 7 天 · 对比基线），用于看板顶部说明")

    updated = data.get("updated")
    if not isinstance(updated, str) or not updated.strip():
        warnings.append("建议填写 `updated`（YYYY-MM-DD）")
    else:
        try:
            datetime.date.fromisoformat(updated.strip())
        except ValueError:
            warnings.append(f"`updated` 建议用 YYYY-MM-DD 格式（当前：{updated}）")

    # thresholds 校验
    thresholds = data.get("thresholds")
    if thresholds is not None:
        if not isinstance(thresholds, dict):
            errors.append("`thresholds` 必须是 JSON object")
        else:
            for k, v in thresholds.items():
                if not _is_num(v):
                    errors.append(f"`thresholds.{k}` 必须是数字（当前：{type(v).__name__}）")
                if k not in KNOWN_THRESHOLD_KEYS:
                    warnings.append(f"`thresholds.{k}` 不在已知阈值列表内，请核对拼写")

    # status_lights 校验
    lights = data.get("status_lights")
    if lights is not None:
        if not isinstance(lights, list):
            errors.append("`status_lights` 必须是列表")
        else:
            for idx, item in enumerate(lights):
                if not isinstance(item, dict):
                    errors.append(f"`status_lights[{idx}]` 必须是 object")
                    continue
                if not isinstance(item.get("label"), str) or not item["label"].strip():
                    errors.append(f"`status_lights[{idx}]` 缺少 `label`")
                lvl = item.get("level", "ok")
                if lvl not in VALID_LIGHT_LEVEL:
                    errors.append(f"`status_lights[{idx}].level` 必须是 ok / warn / danger（当前：{lvl}）")

    # flow 校验
    flow = data.get("flow")
    if flow is not None:
        if not isinstance(flow, dict):
            errors.append("`flow` 必须是 object")
        else:
            nodes = flow.get("nodes", [])
            edges = flow.get("edges", [])
            if not isinstance(nodes, list):
                errors.append("`flow.nodes` 必须是列表")
                nodes = []
            if not isinstance(edges, list):
                errors.append("`flow.edges` 必须是列表")
                edges = []

            node_ids: set[str] = set()
            for idx, node in enumerate(nodes):
                if not isinstance(node, dict):
                    errors.append(f"`flow.nodes[{idx}]` 必须是 object")
                    continue
                nid = node.get("id")
                if not isinstance(nid, str) or not nid.strip():
                    errors.append(f"`flow.nodes[{idx}]` 缺少非空 `id`")
                elif nid in node_ids:
                    errors.append(f"`flow.nodes` 存在重复节点 id：`{nid}`")
                else:
                    node_ids.add(nid)

                if not isinstance(node.get("title"), str) or not node["title"].strip():
                    errors.append(f"`flow.nodes[{idx}]` 缺少 `title`")
                for coord in ("col", "row"):
                    cval = node.get(coord)
                    if not isinstance(cval, int) or isinstance(cval, bool) or cval < 0:
                        errors.append(f"`flow.nodes[{idx}].{coord}` 必须是非负整数（当前：{cval}）")

                for el_idx, el in enumerate(node.get("elements") or []):
                    if not isinstance(el, dict):
                        errors.append(f"`flow.nodes[{idx}].elements[{el_idx}]` 必须是 object")
                        continue
                    for req in ("id", "name", "kind"):
                        if not isinstance(el.get(req), str) or not el[req].strip():
                            errors.append(f"`flow.nodes[{idx}].elements[{el_idx}]` 缺少 `{req}`")
                    st = el.get("status", "ok")
                    if st not in VALID_ELEMENT_STATUS:
                        errors.append(
                            f"`flow.nodes[{idx}].elements[{el_idx}].status` 必须是 ok / warn / danger（当前：{st}）"
                        )

            for e_idx, edge in enumerate(edges):
                if not isinstance(edge, dict):
                    errors.append(f"`flow.edges[{e_idx}]` 必须是 object")
                    continue
                src = edge.get("from")
                dst = edge.get("to")
                if src not in node_ids:
                    errors.append(f"`flow.edges[{e_idx}].from` 指向不存在的节点 `{src}`")
                if dst not in node_ids:
                    errors.append(f"`flow.edges[{e_idx}].to` 指向不存在的节点 `{dst}`")

    # timeline 校验
    tl = data.get("timeline")
    if tl is not None:
        if not isinstance(tl, dict):
            errors.append("`timeline` 必须是 object")
        else:
            dates = tl.get("dates", [])
            conv = tl.get("biz_conv", [])
            ms = tl.get("tech_p90_ms", [])
            crash = tl.get("crash_rate", [])
            for key, arr in (("dates", dates), ("biz_conv", conv), ("tech_p90_ms", ms), ("crash_rate", crash)):
                if not isinstance(arr, list):
                    errors.append(f"`timeline.{key}` 必须是列表")
            if all(isinstance(arr, list) for arr in (dates, conv, ms, crash)):
                lengths = {len(dates), len(conv), len(ms)}
                if crash:
                    lengths.add(len(crash))
                if len(lengths) > 1:
                    errors.append(
                        f"`timeline` 各序列长度不一致：dates={len(dates)}, biz_conv={len(conv)}, tech_p90_ms={len(ms)}, crash_rate={len(crash)}"
                    )
                for key, arr in (("biz_conv", conv), ("tech_p90_ms", ms), ("crash_rate", crash)):
                    if not all(_is_num(x) for x in arr):
                        errors.append(f"`timeline.{key}` 包含非数字元素")

    # engineering 校验
    eng = data.get("engineering")
    if eng is not None:
        if not isinstance(eng, dict):
            errors.append("`engineering` 必须是 object")
        else:
            for idx, st in enumerate(eng.get("subteams") or []):
                if not isinstance(st, dict) or not st.get("name"):
                    errors.append(f"`engineering.subteams[{idx}]` 缺少 `name`")
                elif not _is_num(st.get("on_time_rate")):
                    errors.append(f"`engineering.subteams[{idx}].on_time_rate` 必须是数字")
            for idx, rw in enumerate(eng.get("rework_files") or []):
                if not isinstance(rw, dict) or not rw.get("file"):
                    errors.append(f"`engineering.rework_files[{idx}]` 缺少 `file`")
                elif not _is_num(rw.get("rework_7d")):
                    errors.append(f"`engineering.rework_files[{idx}].rework_7d` 必须是数字")
            for idx, sk in enumerate(eng.get("time_sinks") or []):
                if not isinstance(sk, dict) or not sk.get("item"):
                    errors.append(f"`engineering.time_sinks[{idx}]` 缺少 `item`")
                elif not _is_num(sk.get("waste_pd_month")):
                    errors.append(f"`engineering.time_sinks[{idx}].waste_pd_month` 必须是数字")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 Team Radar 标准快照 JSON 结构")
    parser.add_argument("--input", required=True, help="待校验的 snapshot JSON 文件路径")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.is_file():
        print(f"[错误] 快照文件不存在: {in_path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(in_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[错误] JSON 解析失败: {exc}", file=sys.stderr)
        return 1

    errors, warnings = validate_snapshot(data)
    if warnings:
        for w in warnings:
            print(f"⚠️  [提醒] {w}")
    if errors:
        print("❌ 快照结构校验未通过：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"✅ 快照校验通过：{in_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
