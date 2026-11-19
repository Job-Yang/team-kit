#!/usr/bin/env python3
"""公司专属适配器模板：复制到 adapters/local/<平台名>.py 后按注释修改。

规范约定：
1. 必须接收 `--snapshot <path>` 参数，支持幂等重跑，只更新自己负责的区块；
2. 认证凭据必须从环境变量读取（如 os.environ.get("INTERNAL_API_TOKEN")），禁止硬编码密钥；
3. 只输出聚合指标与文件/链接索引，禁止写入用户隐私样例或未脱敏业务明细。
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path


def load_or_init_snapshot(path: Path, product_name: str = "研发团队") -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "meta": {"schema_version": "1.0", "source_adapter": "local_custom"},
        "product_name": product_name,
        "window": f"截至 {datetime.date.today().isoformat()}",
        "updated": datetime.date.today().isoformat(),
        "status_lights": [],
        "flow": {"nodes": [], "edges": []},
        "timeline": {"dates": [], "biz_conv": [], "tech_p90_ms": [], "crash_rate": [], "changes": []},
        "engineering": {"subteams": [], "rework_files": [], "time_sinks": []},
    }


def fetch_and_merge(snap: dict) -> dict:
    # TODO: 1. 如需认证，只从环境变量读取（不要把 Token 写进代码）
    _token = os.environ.get("INTERNAL_PLATFORM_TOKEN", "")

    # TODO: 2. 调用内部 CLI / 只读 HTTP API / 本地导出文件拉取聚合数据
    # 示例：把拉到的线上发布变更追加或覆盖进 timeline.changes
    # tl = snap.setdefault("timeline", {})
    # tl["changes"] = [...]

    snap["updated"] = datetime.date.today().isoformat()
    meta = snap.setdefault("meta", {})
    meta["last_local_adapter"] = Path(__file__).stem
    return snap


def main() -> int:
    parser = argparse.ArgumentParser(description="公司内部平台快照适配器模板")
    parser.add_argument("--snapshot", required=True, help="待合并写入的 snapshot JSON 路径")
    parser.add_argument("--product-name", default="研发团队", help="快照不存在时的默认产品名")
    args = parser.parse_args()

    snap_path = Path(args.snapshot)
    try:
        snap = load_or_init_snapshot(snap_path, product_name=args.product_name)
        updated = fetch_and_merge(snap)
    except Exception as exc:
        print(f"[错误] 适配器执行失败: {exc}", file=sys.stderr)
        return 1

    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已完成自定义数据合并 -> {snap_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
