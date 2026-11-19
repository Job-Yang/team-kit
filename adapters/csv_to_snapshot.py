#!/usr/bin/env python3
"""通用适配器：将看板导出的标准 CSV（节点指标表 / 每日趋势表）增量合并到 Team Radar snapshot.json。

节点表 CSV 常用列（按 id 对齐并增量更新，不存在则新增）：
  id,title,stage,owner,col,row,uv,pv,conv_rate,conv_delta,stay_sec,p90_ms,crash_rate,drop3_rate,api_err_rate,backtrack_rate,rage_click_rate,ai_correct_rate,stream_abort_rate

时间线表 CSV 常用列（按 date 排序替换 timeline 序列）：
  date,biz_conv,tech_p90_ms,crash_rate
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
from pathlib import Path


def _num(val: str | None, default: float = 0.0, as_int: bool = False) -> float | int:
    if val is None or not str(val).strip():
        return int(default) if as_int else float(default)
    s = str(val).strip().rstrip("%")
    num = float(s)
    return int(round(num)) if as_int else num


def _load_or_init(path: Path, product_name: str) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "meta": {"schema_version": "1.0", "source_adapter": "csv_to_snapshot"},
        "product_name": product_name,
        "window": f"CSV 导入 · 截至 {datetime.date.today().isoformat()}",
        "updated": datetime.date.today().isoformat(),
        "status_lights": [],
        "flow": {"nodes": [], "edges": []},
        "timeline": {"dates": [], "biz_conv": [], "tech_p90_ms": [], "crash_rate": [], "changes": []},
        "engineering": {"subteams": [], "rework_files": [], "time_sinks": []},
    }


def merge_nodes_csv(snap: dict, csv_path: Path) -> int:
    flow = snap.setdefault("flow", {})
    nodes: list[dict] = flow.setdefault("nodes", [])
    by_id = {n["id"]: n for n in nodes if isinstance(n, dict) and n.get("id")}
    updated_count = 0

    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            nid = (row.get("id") or "").strip()
            if not nid:
                continue
            node = by_id.get(nid)
            if node is None:
                node = {
                    "id": nid,
                    "title": (row.get("title") or nid).strip(),
                    "stage": (row.get("stage") or "业务步骤").strip(),
                    "owner": (row.get("owner") or "待明确").strip(),
                    "col": int(_num(row.get("col"), default=idx, as_int=True)),
                    "row": int(_num(row.get("row"), default=0, as_int=True)),
                    "biz": {},
                    "tech": {},
                    "frustration": {},
                    "slices": {},
                    "elements": [],
                }
                nodes.append(node)
                by_id[nid] = node
            else:
                for txt_key in ("title", "stage", "owner"):
                    if (row.get(txt_key) or "").strip():
                        node[txt_key] = row[txt_key].strip()
                if (row.get("col") or "").strip():
                    node["col"] = int(_num(row["col"], as_int=True))
                if (row.get("row") or "").strip():
                    node["row"] = int(_num(row["row"], as_int=True))

            biz = node.setdefault("biz", {})
            for k, is_int in (("uv", True), ("pv", True), ("conv_rate", False), ("conv_delta", False), ("stay_sec", False)):
                if (row.get(k) or "").strip():
                    biz[k] = _num(row[k], as_int=is_int)

            tech = node.setdefault("tech", {})
            for k, is_int in (("p90_ms", True), ("crash_rate", False), ("drop3_rate", False), ("api_err_rate", False), ("fallback_rate", False)):
                if (row.get(k) or "").strip():
                    tech[k] = _num(row[k], as_int=is_int)

            frus = node.setdefault("frustration", {})
            for k in ("backtrack_rate", "rage_click_rate", "ai_correct_rate", "stream_abort_rate"):
                if (row.get(k) or "").strip():
                    frus[k] = _num(row[k], as_int=False)

            updated_count += 1
    return updated_count


def merge_timeline_csv(snap: dict, csv_path: Path) -> int:
    rows: list[dict] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = (row.get("date") or "").strip()
            if not d:
                continue
            rows.append(row)

    tl = snap.setdefault("timeline", {})
    tl["dates"] = [r["date"].strip() for r in rows]
    tl["biz_conv"] = [_num(r.get("biz_conv")) for r in rows]
    tl["tech_p90_ms"] = [_num(r.get("tech_p90_ms"), as_int=True) for r in rows]
    tl["crash_rate"] = [_num(r.get("crash_rate")) for r in rows]
    tl.setdefault("changes", [])
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="将节点/时间线 CSV 导表合并写入 Team Radar snapshot.json")
    parser.add_argument("--snapshot", required=True, help="目标 snapshot.json 路径")
    parser.add_argument("--nodes-csv", default="", help="可选：页面节点指标 CSV 路径")
    parser.add_argument("--timeline-csv", default="", help="可选：每日转化与耗时 CSV 路径")
    parser.add_argument("--product-name", default="研发团队", help="若快照新建时的默认产品名")
    args = parser.parse_args()

    if not args.nodes_csv and not args.timeline_csv:
        print("[错误] 至少需提供 --nodes-csv 或 --timeline-csv 之一", file=sys.stderr)
        return 1

    snap_path = Path(args.snapshot)
    snap = _load_or_init(snap_path, args.product_name)
    actions: list[str] = []

    if args.nodes_csv:
        nc = Path(args.nodes_csv)
        if not nc.is_file():
            print(f"[错误] 节点 CSV 不存在: {nc}", file=sys.stderr)
            return 1
        cnt = merge_nodes_csv(snap, nc)
        actions.append(f"更新节点 {cnt} 个")

    if args.timeline_csv:
        tc = Path(args.timeline_csv)
        if not tc.is_file():
            print(f"[错误] 时间线 CSV 不存在: {tc}", file=sys.stderr)
            return 1
        cnt = merge_timeline_csv(snap, tc)
        actions.append(f"更新时间线 {cnt} 天")

    snap["updated"] = datetime.date.today().isoformat()
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CSV 合并完成（{'，'.join(actions)}）-> {snap_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
