#!/usr/bin/env python3
"""Team Radar 编译器（仅依赖 Python 3 标准库）：
1. 读取标准快照 JSON，交叉分析业务转化、稳定性、AI 识别效果与研发返工，提炼最该先处理的重点事项；
2. 可选读取 `--context-dir`（Team Context 数据目录），自动补充匹配到的模块负责人、代码热区与避坑背景；
3. 生成结构化 AI 排查上下文包（支持抽屉内一键复制与 CLI `--export-prompt` 导出）；
4. 导出实际 design tokens，生成深碳精密仪器风（支持切换暖骨白高反差模式）、4 个独立 Tab（含仿真手机元素级透视）的离线单文件看板。
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "examples" / "demo-radar.json"

DESIGN_TOKENS: dict = {
    "locale": {"lang": "zh-CN"},
    "color": {
        "bg": "#090B0E",
        "surface": "#12151C",
        "surface_alt": "#171B24",
        "surface_inset": "#0C0E13",
        "surface_muted": "#1D222D",
        "border": "#232936",
        "border_strong": "#343E52",
        "text": "#EEF2F6",
        "text_muted": "#95A1B2",
        "text_faint": "#788598",
        "accent": "#10B981",
        "accent_strong": "#059669",
        "accent_soft": "#0F2922",
        "accent_border": "#1A5240",
        "on_accent": "#041E16",
        "signal": "#F97316",
        "signal_soft": "#2D180C",
        "signal_border": "#6B3414",
        "danger": "#FB7185",
        "danger_soft": "#2F141D",
        "danger_border": "#682436",
        "warn": "#FBBF24",
        "warn_soft": "#2C220D",
        "warn_border": "#5E4819",
        "info": "#38BDF8",
        "info_soft": "#102736",
        "info_border": "#1E4B68",
        "slate": "#CBD5E1",
        "slate_soft": "#1C222E",
        "slate_border": "#323C4E",
        "hero_bg": "#141820",
        "hero_text": "#F8FAFC",
        "hero_muted": "#9AA6B8",
        "light_bg": "#F2EFE9",
        "light_surface": "#FFFFFF",
        "light_surface_alt": "#EBE6DC",
        "light_surface_inset": "#F7F5F0",
        "light_surface_muted": "#E3DDD2",
        "light_border": "#D8D1C4",
        "light_border_strong": "#BEB5A5",
        "light_text": "#14171D",
        "light_text_muted": "#505662",
        "light_text_faint": "#6E7582",
        "light_accent": "#0F5C46",
        "light_accent_strong": "#0B4635",
        "light_accent_soft": "#E4F1EC",
        "light_accent_border": "#A8D0C2",
        "light_on_accent": "#FFFFFF",
        "light_signal": "#C85A32",
        "light_signal_soft": "#FAEDE7",
        "light_signal_border": "#E6B9A6",
        "light_danger": "#BE123C",
        "light_danger_soft": "#FCECEF",
        "light_danger_border": "#F3B5C1",
        "light_warn": "#B45309",
        "light_warn_soft": "#FDF4E3",
        "light_warn_border": "#EED097",
        "light_info": "#0E6BA8",
        "light_info_soft": "#E6F2FA",
        "light_info_border": "#AED1E9",
        "light_slate": "#334155",
        "light_slate_soft": "#EAE6DD",
        "light_slate_border": "#CFC8BA",
        "light_hero_bg": "#14171D",
        "light_hero_text": "#F8FAFC",
        "light_hero_muted": "#A6B0BF",
    },
    "typography": {
        "latin_heading": "'SF Pro Display', 'Segoe UI'",
        "latin_body": "'SF Pro Text', 'Segoe UI'",
        "cjk_sans": "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans SC', 'Source Han Sans SC'",
        "mono_font": "'SF Mono', ui-monospace, Menlo, Consolas, 'PingFang SC', monospace",
        "heading_cjk": "sans",
        "weight_regular": 400,
        "weight_medium": 500,
        "weight_bold": 700,
        "scale": {"xs": 12, "sm": 13, "base": 14, "md": 16, "lg": 18, "xl": 20, "2xl": 26, "3xl": 32},
        "line_height": {"ui": 1.5714, "body": 1.65, "heading": 1.35, "display": 1.2},
        "letter_spacing": {"cjk": "0", "latin_display": "-0.01em"},
        "numerals": {"data": "tabular-nums"},
    },
    "radius": {"none": 0, "xs": 4, "sm": 6, "md": 8, "lg": 12, "xl": 16, "2xl": 20, "full": 999},
    "spacing": {
        "1": 4,
        "1_5": 6,
        "2": 8,
        "2_5": 10,
        "3": 12,
        "3_5": 14,
        "4": 16,
        "5": 20,
        "6": 24,
        "7": 28,
        "8": 32,
        "10": 40,
        "12": 48,
    },
    "motion": {
        "duration_fast": 140,
        "duration_base": 220,
        "duration_spring": 380,
        "duration_drawer": 420,
    },
}


def _load_context_bundle(context_dir: Path | None) -> dict:
    """读取可选 Team Context 目录（owners.md / pitfalls.md / code-graph.json），缺失时安静返回空结构。"""
    bundle = {"owners": [], "pitfalls": [], "graph_nodes": []}
    if not context_dir or not context_dir.is_dir():
        return bundle

    owners_file = context_dir / "owners.md"
    if owners_file.is_file():
        for raw in owners_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("|") or line.startswith("| ---") or "负责范围" in line:
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 3:
                bundle["owners"].append(
                    {
                        "scope": cells[0],
                        "modules": cells[1],
                        "primary": cells[2],
                        "backup": cells[3] if len(cells) > 3 else "",
                    }
                )

    pitfalls_file = context_dir / "pitfalls.md"
    if pitfalls_file.is_file():
        cur_title = ""
        cur_lines: list[str] = []
        for raw in pitfalls_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line.startswith("### "):
                if cur_title:
                    bundle["pitfalls"].append({"title": cur_title, "text": "\n".join(cur_lines)})
                cur_title = line[4:].strip()
                cur_lines = []
            elif cur_title and line:
                cur_lines.append(line)
        if cur_title:
            bundle["pitfalls"].append({"title": cur_title, "text": "\n".join(cur_lines)})

    graph_file = context_dir / "code-graph.json"
    if graph_file.is_file():
        try:
            graph = json.loads(graph_file.read_text(encoding="utf-8"))
            bundle["graph_nodes"] = graph.get("nodes", [])
        except Exception:
            pass

    return bundle


def _match_context_notes(context_bundle: dict, owner: str, suspect_files: list[str]) -> list[str]:
    """按模块负责人和可疑文件路径关键词，从 Team Context 抽取最相关的 1~4 条补充背景。"""
    if not any(context_bundle.values()):
        return []

    tokens: set[str] = set()
    for fp in suspect_files:
        p = Path(fp)
        if p.stem:
            tokens.add(p.stem.lower())
        for part in p.parts:
            if len(part) >= 3 and "." not in part and part.lower() not in {"sources", "prompts", "config", "remote", "bff"}:
                tokens.add(part.lower())
    for chunk in owner.replace("&", " ").replace("、", " ").replace("组", " ").split():
        if len(chunk) >= 2:
            tokens.add(chunk.lower())

    notes: list[str] = []
    for row in context_bundle.get("owners", []):
        hay = (row["scope"] + " " + row["modules"]).lower()
        if any(tok in hay for tok in tokens):
            bk = f"（备：{row['backup']}）" if row["backup"] else ""
            notes.append(f"模块对接人：{row['scope']} -> 首选 {row['primary']}{bk}，涉及 {row['modules']}")

    for gn in context_bundle.get("graph_nodes", []):
        gid = str(gn.get("id", ""))
        hay = (gid + " " + str(gn.get("label", "")) + " " + str(gn.get("summary", ""))).lower()
        if any(tok in hay for tok in tokens):
            owners_str = "、".join(gn.get("owners", []))
            notes.append(
                f"代码热区 `{gid}`（近90天改 {gn.get('hot_changes', 0)} 次，维护：{owners_str or '待明确'}）：{gn.get('summary', '')}"
            )

    for pf in context_bundle.get("pitfalls", []):
        hay = (pf["title"] + " " + pf["text"]).lower()
        if any(tok in hay for tok in tokens):
            notes.append(f"历史避坑：{pf['title']}")

    # 去重保序，最多附带 4 条以免撑爆提示词
    return list(dict.fromkeys(notes))[:4]


def _collect_slice_lines(node: dict) -> list[str]:
    lines: list[str] = []
    for dim, rows in (node.get("slices") or {}).items():
        summary = " / ".join(
            f"{r['label']}({r['biz']:.1f}%, {r['tech_ms']}ms, 崩溃{r['crash']:.2f}%)"
            for r in rows
        )
        lines.append(f"- {dim}：{summary}")
    return lines


def _pick_element_id(node: dict, fallback: str = "") -> str:
    elements = node.get("elements") or []
    for st in ("danger", "warn"):
        for el in elements:
            if el.get("status") == st and el.get("id"):
                return el["id"]
    if elements and elements[0].get("id"):
        return elements[0]["id"]
    return fallback


def _build_ai_prompt(
    data: dict,
    finding_id: str,
    severity: str,
    tag: str,
    title: str,
    fact: str,
    suspect: str,
    action: str,
    node: dict | None,
    steps: list[str],
    rel_changes: list[dict],
    suspect_files: list[str],
    context_notes: list[str] | None = None,
) -> str:
    product = data.get("product_name", "目标应用")
    window = data.get("window", "近期窗口")
    lines = [
        f"请帮我继续排查以下产品与工程链路异常（来源：Team Radar `{finding_id}`）：",
        "",
        "## 1. 异常结论与影响",
        f"- 产品与窗口：{product} ｜ {window}",
        f"- 严重度与分类：[{severity}] {tag}",
        f"- 核心判断：{title}",
        f"- 数据事实：{fact}",
        f"- 关联原因线索：{suspect}",
        f"- 业务侧初判建议：{action}",
    ]
    if node:
        lines.extend(
            [
                "",
                f"## 2. 聚焦页面：{node.get('title', '')}（归属：{node.get('owner', '待明确')}）",
                *_collect_slice_lines(node),
            ]
        )
        if node.get("log_hints"):
            lines.append(f"- 推荐日志过滤条件：{node['log_hints']}")
    if rel_changes:
        lines.extend(["", "## 3. 同期线上改动"])
        for c in rel_changes:
            lines.append(
                f"- [{c.get('date', '')}] {c.get('type', '')}｜{c.get('title', '')}（{c.get('owner', '')}）-> {c.get('impact', '')}"
            )
    if suspect_files:
        lines.extend(["", "## 4. 重点代码与配置文件入口"])
        for fp in suspect_files:
            lines.append(f"- `{fp}`")
    lines.extend(["", "## 5. 请优先从这 3 步切入代码和日志排查"])
    for idx, step in enumerate(steps, 1):
        lines.append(f"{idx}. {step}")
    if context_notes:
        lines.extend(["", "## 6. 来自 Team Context 的补充背景"])
        for item in context_notes:
            lines.append(f"- {item}")
    return "\n".join(lines)


def derive_findings(data: dict, context_bundle: dict | None = None) -> list[dict]:
    """交叉分析业务转化、稳定性、AI 效果与交付指标，生成大白话重点结论与 AI 排查包。"""
    context_bundle = context_bundle or {}
    findings: list[dict] = []
    nodes = data.get("flow", {}).get("nodes", [])
    changes = data.get("timeline", {}).get("changes", [])
    eng = data.get("engineering", {})
    rework_files = eng.get("rework_files", [])

    for node in nodes:
        nid = node["id"]
        title = node["title"]
        biz = node.get("biz", {})
        tech = node.get("tech", {})
        frus = node.get("frustration", {})
        slices = node.get("slices", {})
        rel_files = list(node.get("related_files", []))

        gray_drop_note = ""
        ver_slice = slices.get("新老版本") or []
        if len(ver_slice) >= 2:
            diff_v = ver_slice[0]["biz"] - ver_slice[1]["biz"]
            if diff_v <= -10:
                gray_drop_note = (
                    f"{ver_slice[0]['label']} 转化 {ver_slice[0]['biz']:.1f}%（"
                    f"较 {ver_slice[1]['label']} 掉 {abs(diff_v):.1f}%），"
                    f"崩溃 {ver_slice[0]['crash']:.2f}%。"
                )

        # 规则 1：P0 灰度崩溃与高耗时直接拉低转化
        if tech.get("crash_rate", 0) >= 0.25 or (
            biz.get("conv_delta", 0) <= -5 and tech.get("p90_ms", 0) >= 1200
        ):
            rel_changes = [
                c for c in changes if c.get("focus_node") == nid or "灰度" in c.get("type", "") or "配置" in c.get("type", "")
            ]
            cfg_file = next((f for f in rel_files if "Config" in f or f.endswith(".json")), "")
            code_file = next((f for f in rel_files if f != cfg_file), "")
            hot_matches = [r["file"] for r in rework_files if any(k in r["file"] for k in ("Capture", "Media", "Camera"))]
            suspect_files = list(dict.fromkeys(rel_files + hot_matches))

            low_mem = next((r for r in (slices.get("高中低机型") or []) if "低" in r.get("label", "")), None)
            low_mem_crash = f"（崩溃 {low_mem['crash']:.2f}%）" if low_mem else ""
            ver_label = ver_slice[0]["label"] if ver_slice else "灰度版本"
            diff_badge = f"灰度转化 {ver_slice[0]['biz'] - ver_slice[1]['biz']:.1f}%" if len(ver_slice) >= 2 else f"崩溃 {tech.get('crash_rate', 0):.2f}%"

            steps = [
                f"按 `{ver_label}` + `低端内存机` 过滤崩溃栈，确认解码或渲染内存峰值出现在哪一步。",
                f"检查 `{cfg_file or '远程配置文件'}` 近期参数调整，对比调整前后的内存水位与 P90 耗时。",
                f"核查 `{Path(code_file).name if code_file else '端侧核心模块'}` 缓存释放与队列调度逻辑，确认是否存在内存未及时回收。",
            ]
            fid = f"f_{nid}_tech"
            sev = "P0"
            tag = "灰度崩溃卡住转化"
            ftitle = f"{title} 崩溃和耗时暴涨，直接拉低转化"
            fact = (
                f"P90 耗时达 {tech.get('p90_ms')}ms，崩溃率 {tech.get('crash_rate'):.2f}%，"
                f"步骤转化同步下跌 {abs(biz.get('conv_delta', 0)):.1f}%。{gray_drop_note}"
            )
            suspect = "关联改动：" + (
                "；".join(f"{c['date']} {c['type']}「{c['title']}」" for c in rel_changes[:2])
                if rel_changes
                else "端侧内存占用上升与灰度包改动"
            )
            action = f"建议先暂停 {ver_label} 扩量，回滚可疑远程配置开关，并在低端机核查内存峰值。"
            summary_one_line = f"灰度包叠加参数改动使低端机内存溢出{low_mem_crash}，建议暂停放量并回滚相关配置。"
            ctx_notes = _match_context_notes(context_bundle, node.get("owner", ""), suspect_files)
            findings.append(
                {
                    "id": fid,
                    "severity": sev,
                    "tag": tag,
                    "focus_tab": "flow",
                    "node_id": nid,
                    "element_id": _pick_element_id(node),
                    "mode": "tech",
                    "title": ftitle,
                    "impact_badge": diff_badge,
                    "summary_one_line": summary_one_line,
                    "fact": fact,
                    "suspect": suspect,
                    "action": action,
                    "score": 100,
                    "investigation": {
                        "steps": steps,
                        "suspect_files": suspect_files,
                        "related_changes": rel_changes,
                        "log_hints": node.get("log_hints", ""),
                        "ai_prompt": _build_ai_prompt(
                            data, fid, sev, tag, ftitle, fact, suspect, action, node, steps, rel_changes, suspect_files, ctx_notes
                        ),
                    },
                }
            )

        # 规则 2：P1 流程繁琐或弹窗阻断导致大量退回
        elif (frus.get("backtrack_rate", 0) >= 20 or frus.get("rage_click_rate", 0) >= 8) and tech.get("crash_rate", 0) < 0.1:
            rel_changes = [c for c in changes if c.get("focus_node") == nid or "实验" in c.get("type", "") or "AB" in c.get("type", "")]
            hot_matches = [r["file"] for r in rework_files if any(k in r["file"] for k in ("Submit", "Confirm"))]
            suspect_files = list(dict.fromkeys(rel_files + hot_matches))
            short_files = " 与 ".join(f"`{Path(fp).name}`" for fp in suspect_files[:2]) or "相关前后端处理文件"
            steps = [
                f"按会话串联上一跳到 `{title}` 的轨迹，拆分单条操作与连续操作各自退回占比。",
                f"对照近期弹窗或拦截实验与对照组停留时长（当前均长 {biz.get('stay_sec', 0):.1f}s），定位阻断节点。",
                f"检查 {short_files}，评估将逐条确认合并为批量一次确认的前后端改造成本。",
            ]
            fid = f"f_{nid}_ux"
            sev = "P1"
            tag = "弹窗打断退回"
            ftitle = f"{title} 接口零异常，但近四成用户中途退回"
            fact = (
                f"接口报错仅 {tech.get('api_err_rate', 0):.2f}%、P90 {tech.get('p90_ms')}ms 正常，"
                f"但中途退回率达 {frus.get('backtrack_rate'):.1f}%，连点异常 {frus.get('rage_click_rate'):.1f}%，"
                f"转化跌 {abs(biz.get('conv_delta', 0)):.1f}%。"
            )
            suspect = "用户连续操作时被强弹窗和繁琐确认流程打断，被迫反复退回或中途放弃。"
            action = "拿此页面数据与产品对齐：验证“批量一次确认”方案，并关闭强阻断弹窗实验。"
            summary_one_line = f"强弹窗实验打断连续操作节奏，退回率达 {frus.get('backtrack_rate'):.1f}%，建议改为一次确认并撤弹窗。"
            impact_badge = f"退回率 {frus.get('backtrack_rate'):.1f}%"
            ctx_notes = _match_context_notes(context_bundle, node.get("owner", ""), suspect_files)
            findings.append(
                {
                    "id": fid,
                    "severity": sev,
                    "tag": tag,
                    "focus_tab": "flow",
                    "node_id": nid,
                    "element_id": _pick_element_id(node),
                    "mode": "frustration",
                    "title": ftitle,
                    "impact_badge": impact_badge,
                    "summary_one_line": summary_one_line,
                    "fact": fact,
                    "suspect": suspect,
                    "action": action,
                    "score": 82,
                    "investigation": {
                        "steps": steps,
                        "suspect_files": suspect_files,
                        "related_changes": rel_changes,
                        "log_hints": node.get("log_hints", ""),
                        "ai_prompt": _build_ai_prompt(
                            data, fid, sev, tag, ftitle, fact, suspect, action, node, steps, rel_changes, suspect_files, ctx_notes
                        ),
                    },
                }
            )

        # 规则 3：P1 AI 识别手改或半路取消率升高
        if frus.get("ai_correct_rate", 0) >= 12 or frus.get("stream_abort_rate", 0) >= 15:
            rel_changes = [c for c in changes if c.get("focus_node") == nid or "Prompt" in c.get("type", "")]
            hot_matches = [r["file"] for r in rework_files if any(k in r["file"] for k in ("Prompt", "Stream", "parse"))]
            suspect_files = list(dict.fromkeys(rel_files + hot_matches))
            prompt_file = next((f for f in suspect_files if "Prompt" in f or f.endswith((".yaml", ".yml"))), "Prompts/版本文件")
            stream_file = next((f for f in suspect_files if "Stream" in f), "流式渲染组件")
            steps = [
                f"抽样 50 条 `{title}` 用户手动修改记录，统计是“字段错位”“漏识别”还是“理解偏差”。",
                f"比对 `{prompt_file}` 与上一版的输出结构约束，确认多目标场景下字段边界是否清晰。",
                f"检查首包等待（P90 {tech.get('p90_ms')}ms）与 `{Path(stream_file).name}` 重排抖动是否推高 {frus.get('stream_abort_rate', 0):.1f}% 的半路取消率。",
            ]
            fid = f"f_{nid}_ai"
            sev = "P1"
            tag = "AI 识别易错"
            ftitle = f"{title} 零崩溃零报错，但手改率与取消率双升"
            fact = (
                f"识别后用户手动改错率 {frus.get('ai_correct_rate'):.1f}%，"
                f"流式半路关闭/重发率 {frus.get('stream_abort_rate'):.1f}%（常规告警无感知）。"
            )
            suspect = "关联近期 Prompt 版本更新：多目标同框时关键字段配对错位增多，叠加流式等待偏长。"
            action = "抽样 50 条手改样本做聚类比对，必要时针对多目标场景回切上一版 Prompt 策略。"
            summary_one_line = (
                f"识别手改率达 {frus.get('ai_correct_rate'):.1f}%、半路取消 {frus.get('stream_abort_rate'):.1f}%，常规接口告警看不住。"
            )
            impact_badge = f"手改率 {frus.get('ai_correct_rate'):.1f}%"
            ctx_notes = _match_context_notes(context_bundle, node.get("owner", ""), suspect_files)
            findings.append(
                {
                    "id": fid,
                    "severity": sev,
                    "tag": tag,
                    "focus_tab": "flow",
                    "node_id": nid,
                    "element_id": _pick_element_id(node),
                    "mode": "frustration",
                    "title": ftitle,
                    "impact_badge": impact_badge,
                    "summary_one_line": summary_one_line,
                    "fact": fact,
                    "suspect": suspect,
                    "action": action,
                    "score": 78,
                    "investigation": {
                        "steps": steps,
                        "suspect_files": suspect_files,
                        "related_changes": rel_changes,
                        "log_hints": node.get("log_hints", ""),
                        "ai_prompt": _build_ai_prompt(
                            data, fid, sev, tag, ftitle, fact, suspect, action, node, steps, rel_changes, suspect_files, ctx_notes
                        ),
                    },
                }
            )

    # 规则 4：P2 研发按期率跌破警戒且高频返工/等待耗时大
    alert_teams = [t for t in eng.get("subteams", []) if t.get("on_time_rate", 100) < 85 and t.get("mom_delta", 0) <= -15]
    hot_rework = [r for r in rework_files if r.get("rework_7d", 0) >= 4]
    total_waste = sum(x.get("waste_pd_month", 0) for x in eng.get("time_sinks", []))
    if alert_teams or hot_rework:
        team_desc = "、".join(f"{t['name']}({t['on_time_rate']}%)" for t in alert_teams)
        file_desc = "、".join(f"{Path(r['file']).name}({r['rework_7d']}次)" for r in hot_rework[:2])
        suspect_files = list(dict.fromkeys(r["file"] for r in hot_rework))
        first_node = findings[0]["node_id"] if findings else (nodes[0]["id"] if nodes else "")
        first_el = findings[0]["element_id"] if findings else ""
        focus_node = next((n for n in nodes if n["id"] == first_node), None)
        lead_team = alert_teams[0] if alert_teams else None

        steps = [
            f"核查近 7 天反复修改的文件（{file_desc or '核心热修文件'}）提交历史，确认打回主因属于内存/兼容还是需求变动。",
            "检查集成构建预编译缓存配置改动，优先恢复缓存命中率以压低每日等待耗时。",
            "把群里高频重复答疑的口径问题整理进团队文档或内置脚本说明，减少反复人工解答。",
        ]
        fid = "f_eng_rework"
        sev = "P2"
        tag = "返工与等待耗时"
        ftitle = f"{(lead_team['name'] if lead_team else '部分小组')}按期率下滑，返工与排队月耗 {total_waste:.1f} 人天"
        fact = (
            f"明显下滑小组：{team_desc or '无'}；近 7 天反复修改文件：{file_desc or '无'}；"
            f"编译排队、手工回归与重复答疑每月约耗 {total_waste:.1f} 个人天。"
        )
        suspect = "关键模块缺少发版前自动校验基线，加上核心流式与提交文件变动频繁仍靠人工回归。"
        action = "给高频返工文件补发版前自动检查脚本，把重复答疑口径沉淀进团队共享目录。"
        summary_one_line = (
            f"{(lead_team['name'] + '按期率跌至 ' + str(lead_team['on_time_rate']) + '%（环比 ' + str(lead_team['mom_delta']) + '%），') if lead_team else ''}"
            f"等待与返工每月多耗 {total_waste:.1f} 人天。"
        )
        impact_badge = f"月耗 {total_waste:.1f} 人天"
        ctx_notes = _match_context_notes(context_bundle, lead_team["name"] if lead_team else "", suspect_files)
        findings.append(
            {
                "id": fid,
                "severity": sev,
                "tag": tag,
                "focus_tab": "delivery",
                "node_id": first_node,
                "element_id": first_el,
                "mode": "all",
                "title": ftitle,
                "impact_badge": impact_badge,
                "summary_one_line": summary_one_line,
                "fact": fact,
                "suspect": suspect,
                "action": action,
                "score": 65,
                "investigation": {
                    "steps": steps,
                    "suspect_files": suspect_files,
                    "related_changes": changes[:2],
                    "log_hints": "统计 Git commit revert/hotfix 记录与集成编译耗时分位",
                    "ai_prompt": _build_ai_prompt(
                        data, fid, sev, tag, ftitle, fact, suspect, action, focus_node, steps, changes[:2], suspect_files, ctx_notes
                    ),
                },
            }
        )

    findings.sort(key=lambda x: x["score"], reverse=True)
    return findings


def build_root_color_vars(tokens: dict) -> str:
    """将 DESIGN_TOKENS['color'] 生成成 --color-* CSS 变量，保证与 tokens.json 一致无漂移。"""
    lines = []
    for k, v in tokens["color"].items():
        css_name = "--color-" + k.replace("_", "-")
        lines.append(f"    {css_name}: {v};")
    return "\n".join(lines)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__TITLE__ · 团队雷达</title>
<style>
  :root {
__COLOR_VARS__
    --font-sans: 'SF Pro Text', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans SC', 'Source Han Sans SC', sans-serif;
    --font-display: 'SF Pro Display', 'SF Pro Text', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans SC', 'Source Han Sans SC', sans-serif;
    --font-mono: 'SF Mono', ui-monospace, Menlo, Consolas, 'PingFang SC', monospace;

    --spring-snappy: linear(
      0, 0.0677, 0.2181, 0.3941, 0.5621, 0.7053, 0.8177, 0.8999,
      0.9559, 0.9912, 1.011, 1.02, 1.023, 1.021, 1.018, 1.014,
      1.01, 1.007, 1.004, 1.002, 1
    );
    --spring-smooth: linear(
      0, 0.0539, 0.1705, 0.3058, 0.437, 0.5536, 0.6521, 0.7325,
      0.7965, 0.8466, 0.8852, 0.9147, 0.9369, 0.9536, 0.966,
      0.9751, 0.9819, 0.9869, 0.9905, 0.9931, 1
    );
    --ease-out: cubic-bezier(0.22, 1, 0.36, 1);

    /* 默认态：Obsidian Precision 深碳精密雷达仪器台 */
    --ui-bg: var(--color-bg);
    --ui-surface: var(--color-surface);
    --ui-surface-alt: var(--color-surface-alt);
    --ui-surface-inset: var(--color-surface-inset);
    --ui-surface-muted: var(--color-surface-muted);
    --ui-border: var(--color-border);
    --ui-border-strong: var(--color-border-strong);
    --ui-text: var(--color-text);
    --ui-text-muted: var(--color-text-muted);
    --ui-text-faint: var(--color-text-faint);
    --ui-accent: var(--color-accent);
    --ui-accent-strong: var(--color-accent-strong);
    --ui-accent-soft: var(--color-accent-soft);
    --ui-accent-border: var(--color-accent-border);
    --ui-on-accent: var(--color-on-accent);
    --ui-signal: var(--color-signal);
    --ui-signal-soft: var(--color-signal-soft);
    --ui-signal-border: var(--color-signal-border);
    --ui-danger: var(--color-danger);
    --ui-danger-soft: var(--color-danger-soft);
    --ui-danger-border: var(--color-danger-border);
    --ui-warn: var(--color-warn);
    --ui-warn-soft: var(--color-warn-soft);
    --ui-warn-border: var(--color-warn-border);
    --ui-info: var(--color-info);
    --ui-info-soft: var(--color-info-soft);
    --ui-info-border: var(--color-info-border);
    --ui-slate: var(--color-slate);
    --ui-slate-soft: var(--color-slate-soft);
    --ui-slate-border: var(--color-slate-border);
    --ui-hero-bg: var(--color-hero-bg);
    --ui-hero-text: var(--color-hero-text);
    --ui-hero-muted: var(--color-hero-muted);

    --mx: 50%;
    --my: 0%;
    --ui-glow-top: rgba(16, 185, 129, 0.10);
    --ui-glow-side: rgba(249, 115, 22, 0.06);
    --ui-sheen: rgba(249, 115, 22, 0.14);
    --ui-dot: rgba(238, 242, 246, 0.08);
    --ui-panel-shadow: 0 20px 44px -20px rgba(0, 0, 0, 0.65);
    --ui-node-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
    --ui-node-focus: 0 0 0 2px rgba(16, 185, 129, 0.50), 0 12px 28px -12px rgba(16, 185, 129, 0.35);
    --ui-inset-top: rgba(255, 255, 255, 0.08);
    --ui-backdrop: rgba(4, 6, 9, 0.68);
  }

  /* 切换态：Kinetic Bento 暖骨白高反差展厅模式 */
  html[data-theme="light"] {
    --ui-bg: var(--color-light-bg);
    --ui-surface: var(--color-light-surface);
    --ui-surface-alt: var(--color-light-surface-alt);
    --ui-surface-inset: var(--color-light-surface-inset);
    --ui-surface-muted: var(--color-light-surface-muted);
    --ui-border: var(--color-light-border);
    --ui-border-strong: var(--color-light-border-strong);
    --ui-text: var(--color-light-text);
    --ui-text-muted: var(--color-light-text-muted);
    --ui-text-faint: var(--color-light-text-faint);
    --ui-accent: var(--color-light-accent);
    --ui-accent-strong: var(--color-light-accent-strong);
    --ui-accent-soft: var(--color-light-accent-soft);
    --ui-accent-border: var(--color-light-accent-border);
    --ui-on-accent: var(--color-light-on-accent);
    --ui-signal: var(--color-light-signal);
    --ui-signal-soft: var(--color-light-signal-soft);
    --ui-signal-border: var(--color-light-signal-border);
    --ui-danger: var(--color-light-danger);
    --ui-danger-soft: var(--color-light-danger-soft);
    --ui-danger-border: var(--color-light-danger-border);
    --ui-warn: var(--color-light-warn);
    --ui-warn-soft: var(--color-light-warn-soft);
    --ui-warn-border: var(--color-light-warn-border);
    --ui-info: var(--color-light-info);
    --ui-info-soft: var(--color-light-info-soft);
    --ui-info-border: var(--color-light-info-border);
    --ui-slate: var(--color-light-slate);
    --ui-slate-soft: var(--color-light-slate-soft);
    --ui-slate-border: var(--color-light-slate-border);
    --ui-hero-bg: var(--color-light-hero-bg);
    --ui-hero-text: var(--color-light-hero-text);
    --ui-hero-muted: var(--color-light-hero-muted);

    --ui-glow-top: rgba(15, 92, 70, 0.08);
    --ui-glow-side: rgba(200, 90, 50, 0.06);
    --ui-sheen: rgba(200, 90, 50, 0.20);
    --ui-dot: rgba(20, 23, 29, 0.10);
    --ui-panel-shadow: 0 1px 2px rgba(20, 23, 29, 0.05), 0 14px 30px -18px rgba(20, 23, 29, 0.12);
    --ui-node-shadow: 0 2px 6px rgba(20, 23, 29, 0.06);
    --ui-node-focus: 0 0 0 2px rgba(15, 92, 70, 0.40), 0 8px 20px -10px rgba(15, 92, 70, 0.25);
    --ui-inset-top: rgba(255, 255, 255, 0.90);
    --ui-backdrop: rgba(20, 23, 29, 0.42);
  }

  * { box-sizing: border-box; }
  html:lang(zh) { text-autospace: normal; }

  html, body {
    margin: 0;
    min-height: 100%;
    overflow-x: hidden;
    background:
      radial-gradient(ellipse 64% 38% at 18% 0%, var(--ui-glow-top), transparent 70%),
      radial-gradient(ellipse 46% 36% at 88% 100%, var(--ui-glow-side), transparent 68%),
      var(--ui-bg);
    color: var(--ui-text);
    font-family: var(--font-sans);
    font-size: 14px;
    line-height: 1.5714;
    letter-spacing: 0;
    -webkit-font-smoothing: antialiased;
    transition: background-color 220ms var(--ease-out), color 180ms var(--ease-out);
  }

  button, input, textarea {
    font-family: var(--font-sans);
    font-size: inherit;
    line-height: inherit;
    color: inherit;
    letter-spacing: 0;
  }

  button { cursor: pointer; }
  button:focus-visible, [tabindex="0"]:focus-visible {
    outline: 2px solid var(--ui-accent);
    outline-offset: 2px;
  }

  .mono, code {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }

  .shell {
    max-width: 1440px;
    margin: 0 auto;
    padding: 16px 24px 28px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  @media (max-width: 720px) {
    .shell { padding: 12px 12px 24px; gap: 12px; }
  }

  /* 顶部极简单行指挥栏 */
  .cmd-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    padding: 0 0 12px;
    border-bottom: 1px solid var(--ui-border);
  }

  .brand-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .brand-mark {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: var(--ui-surface-alt);
    border: 1px solid var(--ui-border-strong);
    color: var(--ui-accent);
    display: grid;
    place-items: center;
    flex: none;
    box-shadow: inset 0 1px 0 var(--ui-inset-top);
  }

  .brand-copy h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 18px;
    font-weight: 700;
    line-height: 1.3;
    color: var(--ui-text);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .live-dot {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: var(--ui-accent);
    box-shadow: 0 0 0 3px var(--ui-accent-soft);
    display: inline-block;
  }

  .brand-sub {
    margin: 0;
    font-size: 12px;
    color: var(--ui-text-faint);
  }

  .cmd-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  /* 物理滑动分段器 */
  .seg-shell {
    position: relative;
    display: inline-flex;
    align-items: center;
    padding: 4px;
    border-radius: 12px;
    background: var(--ui-surface-inset);
    border: 1px solid var(--ui-border);
    gap: 0;
  }

  .seg-indicator {
    position: absolute;
    top: 4px;
    left: 4px;
    height: calc(100% - 8px);
    width: 0;
    border-radius: 8px;
    background: var(--ui-surface-alt);
    border: 1px solid var(--ui-border-strong);
    box-shadow: inset 0 1px 0 var(--ui-inset-top);
    transition: transform 380ms var(--spring-snappy), width 260ms var(--ease-out);
    pointer-events: none;
  }

  .seg-btn {
    position: relative;
    z-index: 1;
    border: 0;
    background: transparent;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    color: var(--ui-text-muted);
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    transition: color 140ms var(--ease-out), transform 140ms var(--ease-out);
  }
  .seg-btn:hover { color: var(--ui-text); }
  .seg-btn:active { transform: scale(0.97); }
  .seg-btn[aria-pressed="true"], .seg-btn[aria-selected="true"] {
    color: var(--ui-text);
    font-weight: 600;
  }

  @media (max-width: 980px) {
    .main-tabs { width: 100%; flex-wrap: wrap; }
    .main-tabs .seg-indicator { display: none; }
    .main-tabs .seg-btn[aria-selected="true"] {
      background: var(--ui-surface-alt);
      border: 1px solid var(--ui-border-strong);
    }
  }
  @media (max-width: 720px) {
    .mode-seg { flex-wrap: wrap; }
    .mode-seg .seg-indicator { display: none; }
    .mode-seg .seg-btn[aria-pressed="true"] {
      background: var(--ui-surface-alt);
      border: 1px solid var(--ui-border-strong);
    }
  }

  .theme-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 8px;
    border: 1px solid var(--ui-border);
    background: var(--ui-surface);
    color: var(--ui-text);
    font-size: 13px;
    font-weight: 500;
    box-shadow: inset 0 1px 0 var(--ui-inset-top);
    transition: background-color 140ms var(--ease-out), border-color 140ms var(--ease-out), transform 140ms var(--ease-out);
  }
  .theme-toggle:hover { border-color: var(--ui-border-strong); background: var(--ui-surface-alt); }
  .theme-toggle:active { transform: scale(0.97); }

  .ai-launch-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px 6px 12px;
    border-radius: 8px;
    border: 1px solid var(--ui-accent);
    background: var(--ui-accent);
    color: var(--ui-on-accent);
    font-size: 13px;
    font-weight: 700;
    box-shadow: inset 0 1px 0 var(--ui-inset-top);
    transition: background-color 140ms var(--ease-out), transform 140ms var(--ease-out);
  }
  .ai-launch-btn:hover { background: var(--ui-accent-strong); }
  .ai-launch-btn:active { transform: scale(0.97); }

  /* Tab 页签显隐与 Blur-Replace */
  @keyframes blur-replace-in {
    from { opacity: 0.72; filter: blur(3px); transform: translateY(4px); }
    to { opacity: 1; filter: blur(0); transform: translateY(0); }
  }
  .tab-pane { display: none; flex-direction: column; gap: 16px; }
  .tab-pane.active {
    display: flex;
    animation: blur-replace-in 220ms var(--ease-out) both;
  }

  /* 通用面板 */
  .stage-panel {
    background: var(--ui-surface);
    border: 1px solid var(--ui-border);
    border-radius: 16px;
    padding: 16px 20px;
    box-shadow: var(--ui-panel-shadow), inset 0 1px 0 var(--ui-inset-top);
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 12px;
  }
  .panel-head h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 16px;
    font-weight: 700;
    line-height: 1.35;
    color: var(--ui-text);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .panel-sub { margin: 2px 0 0; font-size: 12px; color: var(--ui-text-faint); }

  .pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
  }
  .pill.danger { background: var(--ui-danger-soft); color: var(--ui-danger); border: 1px solid var(--ui-danger-border); }
  .pill.signal { background: var(--ui-signal-soft); color: var(--ui-signal); border: 1px solid var(--ui-signal-border); }
  .pill.warn { background: var(--ui-warn-soft); color: var(--ui-warn); border: 1px solid var(--ui-warn-border); }
  .pill.ok { background: var(--ui-accent-soft); color: var(--ui-accent); border: 1px solid var(--ui-accent-border); }
  .pill.info { background: var(--ui-info-soft); color: var(--ui-info); border: 1px solid var(--ui-info-border); }
  .pill.slate { background: var(--ui-slate-soft); color: var(--ui-slate); border: 1px solid var(--ui-slate-border); }

  .link-btn {
    border: 0;
    background: transparent;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--ui-accent);
    display: inline-flex;
    align-items: center;
    gap: 4px;
    transition: background-color 140ms var(--ease-out);
  }
  .link-btn:hover { background: var(--ui-accent-soft); }

  /* Tab 1: 非对称 4 格便当战情条 */
  .bento-strip {
    display: grid;
    grid-template-columns: 1.35fr 1fr 1fr 1fr;
    gap: 12px;
  }
  @media (max-width: 1100px) { .bento-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @media (max-width: 600px) { .bento-strip { grid-template-columns: 1fr; } }

  .bento-cell {
    position: relative;
    overflow: hidden;
    background: var(--ui-surface);
    border: 1px solid var(--ui-border);
    border-radius: 16px;
    padding: 14px 16px;
    text-align: left;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 6px;
    min-width: 0;
    box-shadow: var(--ui-panel-shadow), inset 0 1px 0 var(--ui-inset-top);
    transition: transform 140ms var(--ease-out), border-color 140ms var(--ease-out);
  }
  .bento-cell:hover { transform: translateY(-2px); border-color: var(--ui-border-strong); }
  .bento-cell:active { transform: scale(0.98); }

  .bento-cell.bento-hero {
    background-color: var(--ui-hero-bg);
    background-image: radial-gradient(circle 220px at var(--mx) var(--my), var(--ui-sheen), transparent 72%);
    border-color: var(--ui-signal-border);
    color: var(--ui-hero-text);
  }
  .bento-hero .bento-title { color: var(--ui-hero-muted); }
  .bento-hero .bento-metric-label { color: var(--ui-hero-muted); }
  .bento-hero .bento-summary { color: var(--ui-hero-muted); }
  .bento-hero .bento-num { color: var(--ui-signal); font-size: 32px; }

  .bento-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .bento-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--ui-text-muted);
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .dot-badge {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: var(--ui-accent);
    flex: none;
  }
  .level-danger .dot-badge { background: var(--ui-signal); }
  .level-warn .dot-badge { background: var(--ui-warn); }

  .bento-metric-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
    flex-wrap: wrap;
  }
  .bento-num {
    font-family: var(--font-display);
    font-variant-numeric: tabular-nums;
    font-size: 26px;
    font-weight: 700;
    line-height: 1.15;
    color: var(--ui-text);
  }
  .level-warn .bento-num { color: var(--ui-warn); }
  .bento-metric-label { font-size: 12px; color: var(--ui-text-faint); }
  .bento-summary { margin: 0; font-size: 12px; color: var(--ui-text-muted); line-height: 1.45; }

  /* Tab 1: 60 / 40 齐平双栏 */
  .overview-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.48fr) minmax(320px, 1fr);
    gap: 16px;
    align-items: start;
  }
  @media (max-width: 1060px) { .overview-grid { grid-template-columns: 1fr; } }

  .right-pulse-stack { display: flex; flex-direction: column; gap: 16px; }
  .brief-queue { display: flex; flex-direction: column; }
  .brief-item {
    padding: 12px 0;
    border-bottom: 1px solid var(--ui-border);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .brief-item:first-child { padding-top: 2px; }
  .brief-item:last-child { border-bottom: 0; padding-bottom: 2px; }

  .brief-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
  }
  .brief-badges { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .brief-btns { display: flex; align-items: center; gap: 6px; }
  .brief-title { margin: 0; font-size: 14px; font-weight: 700; color: var(--ui-text); line-height: 1.4; }
  .brief-summary { margin: 0; font-size: 13px; color: var(--ui-text-muted); line-height: 1.5; }

  .sev-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 700;
    font-family: var(--font-mono);
  }
  .sev-badge.P0 { background: var(--ui-signal); color: var(--ui-on-accent); }
  .sev-badge.P1 { background: var(--ui-warn); color: var(--ui-on-accent); }
  .sev-badge.P2 { background: var(--ui-slate-soft); color: var(--ui-slate); border: 1px solid var(--ui-slate-border); }

  .btn-ghost {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: 8px;
    border: 1px solid var(--ui-border);
    background: var(--ui-surface-alt);
    color: var(--ui-text);
    font-size: 12px;
    font-weight: 600;
    transition: background-color 140ms var(--ease-out), border-color 140ms var(--ease-out), transform 140ms var(--ease-out);
  }
  .btn-ghost:hover { background: var(--ui-surface-muted); border-color: var(--ui-border-strong); }
  .btn-ghost:active { transform: scale(0.97); }

  .btn-ai-inline {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: 8px;
    border: 1px solid var(--ui-accent-border);
    background: var(--ui-accent-soft);
    color: var(--ui-accent);
    font-size: 12px;
    font-weight: 600;
    transition: background-color 140ms var(--ease-out), transform 140ms var(--ease-out);
  }
  .btn-ai-inline:hover { background: var(--ui-surface-muted); }
  .btn-ai-inline:active { transform: scale(0.97); }

  .mini-chart-box {
    background: var(--ui-surface-inset);
    border: 1px solid var(--ui-border);
    border-radius: 12px;
    padding: 8px 10px;
  }
  .mini-svg { width: 100%; height: auto; display: block; overflow: visible; }
  .mini-chart-foot {
    margin-top: 8px;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    font-size: 12px;
    color: var(--ui-text-muted);
  }

  .pulse-sinks { display: flex; flex-direction: column; gap: 10px; }
  .sink-row-top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 4px; }
  .sink-row-name { font-size: 13px; font-weight: 600; color: var(--ui-text); }
  .sink-row-pd { font-family: var(--font-mono); font-size: 12px; font-weight: 700; color: var(--ui-signal); }
  .sink-row-detail { font-size: 12px; color: var(--ui-text-muted); margin-top: 4px; }

  .alert-banner {
    margin-top: 12px;
    padding: 8px 12px;
    border-radius: 8px;
    background: var(--ui-danger-soft);
    border: 1px solid var(--ui-danger-border);
    color: var(--ui-danger);
    font-size: 12px;
    font-weight: 600;
  }

  /* Tab 2: 页面转化（左流向与人群 + 右仿真手机元素级透视） */
  .flow-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
  }

  .flow-split-workspace {
    display: grid;
    grid-template-columns: minmax(0, 1.32fr) minmax(470px, 540px);
    gap: 16px;
    align-items: start;
  }
  @media (max-width: 1200px) { .flow-split-workspace { grid-template-columns: 1fr; } }

  .flow-stage {
    position: relative;
    background-color: var(--ui-surface-inset);
    background-image: radial-gradient(circle, var(--ui-dot) 1px, transparent 1px);
    background-size: 16px 16px;
    border: 1px solid var(--ui-border);
    border-radius: 12px;
    padding: 10px;
    overflow-x: auto;
    overflow-y: hidden;
  }
  .flow-stage-sizer { position: relative; margin: 0 auto; }
  .flow-canvas {
    position: relative;
    width: 976px;
    height: 410px;
    transform-origin: top left;
  }
  .flow-svg {
    position: absolute;
    inset: 0;
    width: 976px;
    height: 410px;
    z-index: 3;
    pointer-events: none;
  }

  @keyframes flow-dash {
    to { stroke-dashoffset: -16; }
  }
  .flow-edge-active {
    stroke-dasharray: 6, 4;
    animation: flow-dash 680ms linear infinite;
  }

  .flow-node {
    position: absolute;
    z-index: 2;
    width: 176px;
    min-height: 112px;
    background: var(--ui-surface);
    border: 1px solid var(--ui-border);
    border-top-width: 3px;
    border-radius: 12px;
    padding: 8px 10px;
    text-align: left;
    box-shadow: var(--ui-node-shadow);
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: transform 140ms var(--ease-out), border-color 140ms var(--ease-out), box-shadow 180ms var(--ease-out), opacity 180ms var(--ease-out);
  }
  .flow-node:hover { transform: translateY(-2px); border-color: var(--ui-border-strong); }
  .flow-node:active { transform: scale(0.98); }
  .flow-node.status-danger { border-top-color: var(--ui-signal); }
  .flow-node.status-warn { border-top-color: var(--ui-warn); }
  .flow-node.status-ok { border-top-color: var(--ui-accent); }
  .flow-node.selected { border-color: var(--ui-accent); box-shadow: var(--ui-node-focus); }
  .flow-node.dimmed { opacity: 0.72; }

  .node-top { display: flex; align-items: center; justify-content: space-between; gap: 4px; font-size: 12px; color: var(--ui-text-faint); }
  .node-status-tag { font-size: 12px; font-weight: 600; }
  .node-status-tag.danger { color: var(--ui-signal); }
  .node-status-tag.warn { color: var(--ui-warn); }
  .node-status-tag.ok { color: var(--ui-accent); }
  .node-title { font-size: 13px; font-weight: 700; line-height: 1.3; color: var(--ui-text); }

  .node-metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
  .metric-kv { background: var(--ui-surface-alt); border-radius: 6px; padding: 4px 6px; }
  .metric-kv .k { display: block; font-size: 12px; color: var(--ui-text-faint); line-height: 1.2; }
  .metric-kv .v {
    display: block;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 12px;
    font-weight: 700;
    color: var(--ui-text);
    line-height: 1.3;
  }
  .metric-kv .v.v-bad { color: var(--ui-signal); }
  .metric-kv .v.v-warn { color: var(--ui-warn); }
  .metric-kv .v.v-ok { color: var(--ui-accent); }

  /* 人群对比 3 列 */
  .drilldown-band { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--ui-border); }
  .drilldown-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
  @media (max-width: 780px) { .drilldown-grid { grid-template-columns: 1fr; } }

  .slice-col {
    background: var(--ui-surface-inset);
    border: 1px solid var(--ui-border);
    border-radius: 12px;
    padding: 10px 12px;
  }
  .slice-col h3 { margin: 0 0 8px; font-size: 12px; font-weight: 600; color: var(--ui-text-muted); }
  .slice-row { margin-bottom: 8px; }
  .slice-row:last-child { margin-bottom: 0; }
  .slice-label {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 6px;
    font-size: 12px;
    margin-bottom: 4px;
    color: var(--ui-text);
  }
  .slice-val {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 12px;
    color: var(--ui-text-muted);
    white-space: nowrap;
  }

  .bar-track {
    height: 8px;
    background: var(--ui-surface-muted);
    border-radius: 999px;
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    border-radius: 999px;
    background: var(--ui-info);
    transition: width 320ms var(--ease-out);
  }
  .bar-fill.bad { background: var(--ui-signal); }
  .bar-fill.ok { background: var(--ui-accent); }

  /* 右侧仿真手机 + 元素透视面板 */
  .sim-split {
    display: grid;
    grid-template-columns: 236px minmax(0, 1fr);
    gap: 14px;
    align-items: start;
  }
  @media (max-width: 560px) { .sim-split { grid-template-columns: 1fr; } }

  .phone-shell {
    background: var(--ui-surface-inset);
    border: 1px solid var(--ui-border-strong);
    border-radius: 20px;
    padding: 8px;
    box-shadow: var(--ui-panel-shadow), inset 0 1px 0 var(--ui-inset-top);
  }
  .phone-screen {
    background: var(--ui-surface-alt);
    border: 1px solid var(--ui-border);
    border-radius: 12px;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 416px;
  }
  .phone-statusbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 2px 4px 6px;
    border-bottom: 1px solid var(--ui-border);
    font-size: 12px;
    color: var(--ui-text-muted);
  }
  .phone-notch {
    width: 48px;
    height: 6px;
    border-radius: 999px;
    background: var(--ui-border-strong);
  }
  .phone-app-title {
    font-size: 12px;
    font-weight: 700;
    color: var(--ui-text);
    text-align: center;
    padding: 2px 0;
  }

  .phone-el-btn {
    width: 100%;
    text-align: left;
    border: 1px solid var(--ui-border);
    background: var(--ui-surface);
    border-radius: 8px;
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: transform 140ms var(--ease-out), border-color 140ms var(--ease-out), box-shadow 140ms var(--ease-out);
  }
  .phone-el-btn:hover { border-color: var(--ui-border-strong); transform: translateY(-1px); }
  .phone-el-btn:active { transform: scale(0.98); }

  .phone-el-btn.kind-hero {
    min-height: 88px;
    justify-content: space-between;
    background: var(--ui-hero-bg);
    color: var(--ui-hero-text);
  }
  .phone-el-btn.kind-hero .el-kind-tag { color: var(--ui-hero-muted); }

  .phone-el-btn.kind-modal {
    border-style: dashed;
    border-width: 2px;
    background: var(--ui-danger-soft);
  }
  .phone-el-btn.kind-action {
    background: var(--ui-surface-muted);
  }
  .phone-el-btn.status-danger { border-color: var(--ui-signal); }
  .phone-el-btn.status-warn { border-color: var(--ui-warn); }
  .phone-el-btn.status-ok { border-color: var(--ui-accent-border); }
  .phone-el-btn[aria-pressed="true"] {
    box-shadow: var(--ui-node-focus);
    border-color: var(--ui-accent);
  }

  .el-top-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
  }
  .el-kind-tag { font-size: 12px; color: var(--ui-text-faint); }
  .el-name { font-size: 12px; font-weight: 700; line-height: 1.35; }
  .el-metric-badge {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 12px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 6px;
    white-space: nowrap;
  }
  .el-metric-badge.danger { background: var(--ui-signal-soft); color: var(--ui-signal); }
  .el-metric-badge.warn { background: var(--ui-warn-soft); color: var(--ui-warn); }
  .el-metric-badge.ok { background: var(--ui-accent-soft); color: var(--ui-accent); }

  /* 右侧选中元素明细面板 */
  .el-detail-col { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
  .el-chips-row { display: flex; flex-wrap: wrap; gap: 6px; }
  .el-chip-btn {
    border: 1px solid var(--ui-border);
    background: var(--ui-surface-inset);
    color: var(--ui-text-muted);
    padding: 4px 8px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    transition: background-color 140ms var(--ease-out), border-color 140ms var(--ease-out), color 140ms var(--ease-out);
  }
  .el-chip-btn[aria-selected="true"] {
    background: var(--ui-accent-soft);
    border-color: var(--ui-accent);
    color: var(--ui-accent);
  }

  .el-detail-card {
    background: var(--ui-surface-inset);
    border: 1px solid var(--ui-border);
    border-radius: 12px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .el-detail-title { margin: 0; font-size: 14px; font-weight: 700; color: var(--ui-text); }
  .el-kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .el-kpi-box {
    background: var(--ui-surface);
    border: 1px solid var(--ui-border);
    border-radius: 8px;
    padding: 8px 10px;
  }
  .el-kpi-label { font-size: 12px; color: var(--ui-text-faint); display: block; }
  .el-kpi-val {
    font-family: var(--font-display);
    font-variant-numeric: tabular-nums;
    font-size: 18px;
    font-weight: 700;
    color: var(--ui-text);
  }
  .el-kpi-val.bad { color: var(--ui-signal); }
  .el-kpi-val.ok { color: var(--ui-accent); }

  .el-meta-rows { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--ui-text-muted); }
  .el-note-box {
    padding: 8px 10px;
    border-radius: 8px;
    background: var(--ui-surface);
    border-left: 3px solid var(--ui-accent);
    font-size: 12px;
    color: var(--ui-text);
    line-height: 1.5;
  }
  .el-note-box.danger { border-left-color: var(--ui-signal); }
  .el-note-box.warn { border-left-color: var(--ui-warn); }

  /* Tab 3: 上线变动 */
  .timeline-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.5fr) minmax(300px, 1fr);
    gap: 16px;
    align-items: start;
  }
  @media (max-width: 960px) { .timeline-grid { grid-template-columns: 1fr; } }

  .filter-bar { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .filter-chip {
    border: 1px solid var(--ui-border);
    background: var(--ui-surface-inset);
    color: var(--ui-text-muted);
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    transition: background-color 140ms var(--ease-out), border-color 140ms var(--ease-out), color 140ms var(--ease-out);
  }
  .filter-chip:hover { color: var(--ui-text); border-color: var(--ui-border-strong); }
  .filter-chip[aria-pressed="true"] {
    background: var(--ui-accent);
    border-color: var(--ui-accent);
    color: var(--ui-on-accent);
  }

  .timeline-chart-box {
    position: relative;
    background: var(--ui-surface-inset);
    border: 1px solid var(--ui-border);
    border-radius: 12px;
    padding: 12px;
  }
  .timeline-svg { width: 100%; height: auto; display: block; overflow: visible; }
  .chart-tooltip {
    position: absolute;
    top: 8px;
    left: 66px;
    max-width: 248px;
    padding: 6px 10px;
    border-radius: 8px;
    background: var(--ui-text);
    color: var(--ui-bg);
    font-size: 12px;
    line-height: 1.4;
    pointer-events: none;
    opacity: 0;
    transform: translateY(-4px);
    transition: opacity 140ms var(--ease-out), transform 140ms var(--ease-out);
  }
  .chart-tooltip[data-show="true"] { opacity: 1; transform: translateY(0); }

  .timeline-legend { display: flex; align-items: center; flex-wrap: wrap; gap: 16px; margin-top: 10px; font-size: 12px; color: var(--ui-text-muted); }
  .legend-item { display: inline-flex; align-items: center; gap: 6px; }
  .legend-swatch { width: 14px; height: 4px; border-radius: 4px; display: inline-block; }
  .legend-swatch.conv { background: var(--ui-info); }
  .legend-swatch.ms { background: var(--ui-signal); }
  .legend-swatch.chg { background: var(--ui-warn); }

  .change-list {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--ui-border);
    border-radius: 12px;
    overflow: hidden;
    background: var(--ui-surface-inset);
  }
  .change-row {
    width: 100%;
    border-bottom: 1px solid var(--ui-border);
    border-left: 3px solid transparent;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: background-color 140ms var(--ease-out), border-color 140ms var(--ease-out);
  }
  .change-row:last-child { border-bottom: 0; }
  .change-row:hover { background: var(--ui-surface-alt); }
  .change-row.highlight { background: var(--ui-accent-soft); border-left-color: var(--ui-accent); }
  .change-select-btn {
    border: 0;
    background: transparent;
    padding: 0;
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 100%;
  }
  .change-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 12px; color: var(--ui-text-faint); }
  .change-title { font-size: 13px; font-weight: 700; color: var(--ui-text); }
  .change-impact { font-size: 12px; color: var(--ui-text-muted); }
  .change-foot { display: flex; justify-content: flex-end; margin-top: 2px; }

  /* Tab 4: 交付效率 */
  .bento-strip.cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  @media (max-width: 900px) { .bento-strip.cols-3 { grid-template-columns: 1fr; } }

  .ledger-wrap { overflow-x: auto; border: 1px solid var(--ui-border); border-radius: 12px; }
  table.eng-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  table.eng-table th, table.eng-table td {
    border-bottom: 1px solid var(--ui-border);
    padding: 10px 12px;
    text-align: left;
    vertical-align: middle;
  }
  table.eng-table tr:last-child td { border-bottom: 0; }
  table.eng-table th {
    background: var(--ui-surface-inset);
    font-size: 12px;
    font-weight: 600;
    color: var(--ui-text-muted);
    white-space: nowrap;
  }
  table.eng-table td.num, table.eng-table th.num {
    text-align: right;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .eng-split { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }
  @media (max-width: 960px) { .eng-split { grid-template-columns: 1fr; } }

  .sink-list {
    border: 1px solid var(--ui-border);
    border-radius: 12px;
    padding: 14px 16px;
    background: var(--ui-surface-inset);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .code-chip {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    background: var(--ui-surface-inset);
    border: 1px solid var(--ui-border);
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ui-text);
    overflow-wrap: break-word;
  }
  .inline-code {
    display: inline-block;
    padding: 0 4px;
    border-radius: 4px;
    background: var(--ui-surface);
    border: 1px solid var(--ui-border);
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ui-accent);
  }

  .page-foot {
    padding: 6px 4px 0;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    font-size: 12px;
    color: var(--ui-text-faint);
  }

  /* 右侧滑入 AI 排查抽屉 */
  .drawer-backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
    background: var(--ui-backdrop);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    opacity: 0;
    pointer-events: none;
    transition: opacity 220ms var(--ease-out);
  }
  .drawer-backdrop[data-open="true"] { opacity: 1; pointer-events: auto; }

  .ai-drawer {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    z-index: 50;
    width: 540px;
    max-width: 100vw;
    background: var(--ui-surface);
    border-left: 1px solid var(--ui-border-strong);
    box-shadow: var(--ui-panel-shadow);
    display: flex;
    flex-direction: column;
    transform: translateX(100%);
    opacity: 0.9;
    transition: transform 420ms var(--spring-smooth), opacity 180ms var(--ease-out);
  }
  .ai-drawer[data-open="true"] { transform: translateX(0); opacity: 1; }

  .drawer-head { padding: 16px 20px; border-bottom: 1px solid var(--ui-border); display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .drawer-head-left { display: flex; align-items: center; gap: 10px; }
  .drawer-head h2 { margin: 0; font-size: 16px; font-weight: 700; color: var(--ui-text); }

  .drawer-close {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    border: 1px solid var(--ui-border);
    background: var(--ui-surface-alt);
    color: var(--ui-text);
    display: grid;
    place-items: center;
    position: relative;
    transition: background-color 140ms var(--ease-out), transform 140ms var(--ease-out);
  }
  .drawer-close::after { content: ""; position: absolute; inset: -6px; }
  .drawer-close:hover { background: var(--ui-surface-muted); }
  .drawer-close:active { transform: scale(0.95); }

  .drawer-switcher {
    padding: 10px 20px;
    border-bottom: 1px solid var(--ui-border);
    background: var(--ui-surface-inset);
    display: flex;
    gap: 8px;
    overflow-x: auto;
  }
  .switch-chip {
    border: 1px solid var(--ui-border);
    background: var(--ui-surface);
    color: var(--ui-text-muted);
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
    transition: background-color 140ms var(--ease-out), border-color 140ms var(--ease-out), color 140ms var(--ease-out);
  }
  .switch-chip[aria-selected="true"] { background: var(--ui-accent); border-color: var(--ui-accent); color: var(--ui-on-accent); }

  .drawer-body { padding: 16px 20px 24px; overflow-y: auto; flex: 1 1 auto; display: flex; flex-direction: column; gap: 16px; }
  .drawer-sec-title { margin: 0 0 8px; font-size: 13px; font-weight: 700; color: var(--ui-text); }

  .step-checklist { display: flex; flex-direction: column; gap: 8px; }
  .step-check-btn {
    width: 100%;
    text-align: left;
    border: 1px solid var(--ui-border);
    background: var(--ui-surface-inset);
    border-radius: 12px;
    padding: 10px 12px;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    font-size: 13px;
    color: var(--ui-text);
    transition: background-color 140ms var(--ease-out), border-color 140ms var(--ease-out);
  }
  .step-check-btn:hover { border-color: var(--ui-border-strong); }
  .step-check-btn[aria-checked="true"] { background: var(--ui-accent-soft); border-color: var(--ui-accent-border); }
  .step-check-box {
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 1px solid var(--ui-border-strong);
    background: var(--ui-surface);
    display: grid;
    place-items: center;
    flex: none;
    margin-top: 2px;
    color: var(--ui-on-accent);
    transition: background-color 140ms var(--ease-out), border-color 140ms var(--ease-out);
  }
  .step-check-btn[aria-checked="true"] .step-check-box { background: var(--ui-accent); border-color: var(--ui-accent); }
  .check-path { stroke-dasharray: 24; stroke-dashoffset: 24; transition: stroke-dashoffset 220ms var(--ease-out); }
  .step-check-btn[aria-checked="true"] .check-path { stroke-dashoffset: 0; }

  .files-wrap { display: flex; flex-wrap: wrap; gap: 8px; }
  .prompt-box {
    margin: 0;
    padding: 12px;
    border-radius: 12px;
    border: 1px solid var(--ui-border);
    background: var(--ui-surface-inset);
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.55;
    color: var(--ui-text);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 220px;
    overflow-y: auto;
  }

  .drawer-foot { padding: 14px 20px; border-top: 1px solid var(--ui-border); background: var(--ui-surface); display: flex; flex-direction: column; gap: 8px; }
  .btn-copy-primary {
    width: 100%;
    border: 0;
    border-radius: 12px;
    padding: 10px 16px;
    background: var(--ui-accent);
    color: var(--ui-on-accent);
    font-size: 14px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: background-color 140ms var(--ease-out), transform 140ms var(--ease-out);
  }
  .btn-copy-primary:hover { background: var(--ui-accent-strong); }
  .btn-copy-primary:active { transform: scale(0.98); }

  .cli-hint { font-size: 12px; color: var(--ui-text-faint); text-align: center; }

  .toast-pill {
    position: fixed;
    left: 50%;
    bottom: 24px;
    z-index: 60;
    transform: translate(-50%, 16px);
    opacity: 0;
    pointer-events: none;
    padding: 10px 16px;
    border-radius: 999px;
    background: var(--ui-text);
    color: var(--ui-bg);
    font-size: 13px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    box-shadow: var(--ui-panel-shadow);
    transition: transform 280ms var(--spring-snappy), opacity 180ms var(--ease-out);
  }
  .toast-pill[data-show="true"] { opacity: 1; transform: translate(-50%, 0); }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }
</style>
</head>
<body>
<div class="shell">
  <!-- 顶部极简单行指挥栏 -->
  <header class="cmd-bar">
    <div class="brand-wrap">
      <div class="brand-mark" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
          <path d="M12 12l5-5" />
          <circle cx="12" cy="12" r="2" fill="currentColor" />
        </svg>
      </div>
      <div class="brand-copy">
        <h1><span class="live-dot" aria-hidden="true"></span><span id="app-title">示例 App · 团队雷达</span></h1>
        <p class="brand-sub" id="app-window"></p>
      </div>
    </div>

    <nav class="seg-shell main-tabs" id="main-tabs" role="tablist" aria-label="功能分区切换">
      <div class="seg-indicator" aria-hidden="true"></div>
      <button type="button" class="seg-btn" role="tab" data-tab="overview" aria-selected="true">总览</button>
      <button type="button" class="seg-btn" role="tab" data-tab="flow" aria-selected="false">页面转化</button>
      <button type="button" class="seg-btn" role="tab" data-tab="changes" aria-selected="false">上线变动</button>
      <button type="button" class="seg-btn" role="tab" data-tab="delivery" aria-selected="false">交付效率</button>
    </nav>

    <div class="cmd-actions">
      <button type="button" class="theme-toggle" id="theme-toggle" aria-label="切换暗色仪器与暖骨白展厅主题">
        <span id="theme-icon" aria-hidden="true"></span>
        <span id="theme-label">暖骨白模式</span>
      </button>
      <button type="button" class="ai-launch-btn" id="open-ai-top" data-action="open-ai-top">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3z" />
        </svg>
        <span>AI 排查</span>
      </button>
    </div>
  </header>

  <!-- Tab 1: 总览（主屏一屏抓大盘重点，左右齐平） -->
  <section class="tab-pane active" id="tab-overview" role="tabpanel" aria-label="总览">
    <div class="bento-strip" id="bento-strip" aria-label="关键告警指标"></div>

    <div class="overview-grid">
      <div class="stage-panel">
        <div class="panel-head">
          <div>
            <h2>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 9v4M12 17h.01" />
                <path d="M10.3 3.9L2.4 17.5A1.8 1.8 0 0 0 4 20h16a1.8 1.8 0 0 0 1.6-2.5L13.7 3.9a2 2 0 0 0-3.4 0z" />
              </svg>
              <span>最该先处理的 4 件事</span>
            </h2>
            <p class="panel-sub">按影响大小和紧急程度排序，点击右侧可直接透视对应页面元素或看 AI 排查思路</p>
          </div>
          <span class="pill ok" id="finding-count"></span>
        </div>
        <div class="brief-queue" id="brief-queue"></div>
      </div>

      <div class="right-pulse-stack">
        <div class="stage-panel">
          <div class="panel-head">
            <h2>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M3 17l6-6 4 4 8-8" />
                <path d="M17 7h4v4" />
              </svg>
              <span>近 7 天转化与耗时</span>
            </h2>
            <button type="button" class="link-btn" data-goto-tab="changes">看变动明细 -&gt;</button>
          </div>
          <div class="mini-chart-box">
            <svg class="mini-svg" id="mini-timeline-svg" viewBox="0 0 440 132"></svg>
          </div>
          <div class="mini-chart-foot" id="mini-timeline-foot"></div>
        </div>

        <div class="stage-panel">
          <div class="panel-head">
            <h2>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 7v5l3 3" />
              </svg>
              <span>团队耗时最多的事</span>
            </h2>
            <button type="button" class="link-btn" data-goto-tab="delivery">看交付效率 -&gt;</button>
          </div>
          <div class="pulse-sinks" id="overview-sinks"></div>
          <div class="alert-banner" id="overview-team-alert"></div>
        </div>
      </div>
    </div>
  </section>

  <!-- Tab 2: 页面转化（左全链路流向+人群对比 / 右仿真手机元素级透视） -->
  <section class="tab-pane" id="tab-flow" role="tabpanel" aria-label="页面转化">
    <div class="flow-topbar">
      <div class="seg-shell mode-seg" id="mode-switch" role="group" aria-label="查看指标维度">
        <div class="seg-indicator" aria-hidden="true"></div>
        <button type="button" class="seg-btn" data-mode="all" aria-pressed="true">全部看</button>
        <button type="button" class="seg-btn" data-mode="biz" aria-pressed="false">看转化</button>
        <button type="button" class="seg-btn" data-mode="tech" aria-pressed="false">看崩溃卡顿</button>
        <button type="button" class="seg-btn" data-mode="frustration" aria-pressed="false">看卡壳和改错</button>
      </div>

      <div class="seg-shell" id="caliber-switch" role="group" aria-label="流量统计口径">
        <div class="seg-indicator" aria-hidden="true"></div>
        <button type="button" class="seg-btn" data-caliber="uv" aria-pressed="true">按人数(UV)</button>
        <button type="button" class="seg-btn" data-caliber="pv" aria-pressed="false">按次数(PV)</button>
      </div>
    </div>

    <div class="flow-split-workspace">
      <div class="stage-panel">
        <div class="panel-head">
          <div>
            <h2>全链路页面流向</h2>
            <p class="panel-sub">点任意页面，右侧仿真手机实时切到该页并标出每个按钮的点击与报错</p>
          </div>
        </div>

        <div class="flow-stage" id="flow-stage">
          <div class="flow-stage-sizer" id="flow-stage-sizer">
            <div class="flow-canvas" id="flow-canvas">
              <div id="flow-nodes"></div>
              <svg class="flow-svg" id="flow-svg" viewBox="0 0 976 410"></svg>
            </div>
          </div>
        </div>

        <div class="drilldown-band" id="drilldown-box"></div>
      </div>

      <div class="stage-panel">
        <div class="panel-head">
          <div>
            <h2 id="sim-page-title">仿真页面 · 元素级透视</h2>
            <p class="panel-sub" id="sim-page-sub">点击手机屏幕内的按钮、卡片或弹窗，右侧直接看曝光、CTR 与代码位置</p>
          </div>
          <div id="sim-head-actions"></div>
        </div>

        <div class="sim-split">
          <div class="phone-shell">
            <div class="phone-screen" id="phone-screen"></div>
          </div>
          <div class="el-detail-col" id="el-detail-col"></div>
        </div>
      </div>
    </div>
  </section>

  <!-- Tab 3: 上线变动 -->
  <section class="tab-pane" id="tab-changes" role="tabpanel" aria-label="上线变动">
    <div class="stage-panel">
      <div class="panel-head">
        <div>
          <h2>上线变动与指标对照</h2>
          <p class="panel-sub">看清哪天发版或改了配置后指标掉下来；点右侧改动可锁定当天数据或直接去看对应页面</p>
        </div>
        <div class="filter-bar" id="change-filter-bar" role="group" aria-label="按变动类型筛选"></div>
      </div>

      <div class="timeline-grid">
        <div>
          <div class="timeline-chart-box">
            <svg class="timeline-svg" id="timeline-svg" viewBox="0 0 720 276"></svg>
            <div class="chart-tooltip" id="chart-tooltip" role="status"></div>
          </div>
          <div class="timeline-legend">
            <span class="legend-item"><span class="legend-swatch conv"></span><span>核心提交转化率 (%) · 左轴</span></span>
            <span class="legend-item"><span class="legend-swatch ms"></span><span>采集页 P90 耗时 (ms) · 右轴</span></span>
            <span class="legend-item"><span class="legend-swatch chg"></span><span>线上变动标记线</span></span>
          </div>
        </div>
        <div class="change-list" id="change-list"></div>
      </div>
    </div>
  </section>

  <!-- Tab 4: 交付效率 -->
  <section class="tab-pane" id="tab-delivery" role="tabpanel" aria-label="交付效率">
    <div class="bento-strip cols-3" id="delivery-strip" aria-label="效率关键数字"></div>

    <div class="stage-panel">
      <div class="panel-head">
        <div>
          <h2>各小组按期上线情况</h2>
          <p class="panel-sub">按期率不到 85% 且比上月跌超 15% 时标红提醒，避免日常小波动误报</p>
        </div>
      </div>
      <div class="ledger-wrap">
        <table class="eng-table" id="subteams-table"></table>
      </div>
    </div>

    <div class="eng-split">
      <div class="stage-panel">
        <div class="panel-head">
          <div>
            <h2>发版后反复修改的文件</h2>
            <p class="panel-sub">近 7 天上线后频繁热修的代码与配置</p>
          </div>
          <button type="button" class="btn-ai-inline" id="delivery-ai-btn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3z"/></svg>
            <span>AI 排查返工</span>
          </button>
        </div>
        <div class="ledger-wrap">
          <table class="eng-table" id="rework-table"></table>
        </div>
      </div>

      <div class="stage-panel">
        <div class="panel-head">
          <div>
            <h2>团队耗时最多的 3 件事</h2>
            <p class="panel-sub">把编译排队、手工回归和重复答疑折算成人天，方便排期提效</p>
          </div>
        </div>
        <div class="sink-list" id="sinks-list"></div>
      </div>
    </div>
  </section>

  <footer class="page-foot">
    <span id="foot-note"></span>
    <span id="foot-updated"></span>
  </footer>
</div>

<!-- 右侧滑入 AI 排查抽屉 -->
<div class="drawer-backdrop" id="drawer-backdrop" data-open="false" aria-hidden="true"></div>
<aside class="ai-drawer" id="ai-drawer" data-open="false" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
  <div class="drawer-head">
    <div class="drawer-head-left">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3z" />
      </svg>
      <h2 id="drawer-title">AI 辅助排查思路</h2>
    </div>
    <button type="button" class="drawer-close" id="drawer-close" aria-label="关闭排查抽屉">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round">
        <path d="M6 6l12 12M18 6L6 18" />
      </svg>
    </button>
  </div>
  <div class="drawer-switcher" id="drawer-switcher" role="tablist" aria-label="切换问题"></div>
  <div class="drawer-body" id="drawer-body"></div>
  <div class="drawer-foot">
    <button type="button" class="btn-copy-primary" id="copy-prompt-btn">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="9" y="9" width="11" height="11" rx="2" />
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
      </svg>
      <span>一键复制 AI 排查上下文包</span>
    </button>
    <div class="cli-hint mono" id="drawer-cli-hint"></div>
  </div>
</aside>

<div class="toast-pill" id="toast-pill" role="status" aria-live="polite" data-show="false">
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M5 12l5 5L20 7" />
  </svg>
  <span id="toast-text">已复制到剪贴板</span>
</div>

<script>
const RADAR_DATA = __RADAR_DATA__;
const FIRST_FINDING = (RADAR_DATA.findings && RADAR_DATA.findings[0]) || null;
const FIRST_NODE = (RADAR_DATA.flow && RADAR_DATA.flow.nodes && RADAR_DATA.flow.nodes[0]) || null;

const state = {
  theme: "dark",
  activeTab: "overview",
  caliber: "uv",
  mode: "all",
  selectedNodeId: (FIRST_FINDING && FIRST_FINDING.node_id) || (FIRST_NODE && FIRST_NODE.id) || "",
  selectedElementId: (FIRST_FINDING && FIRST_FINDING.element_id) || "",
  selectedFindingId: (FIRST_FINDING && FIRST_FINDING.id) || null,
  selectedDayIdx: Math.max(0, ((RADAR_DATA.timeline && RADAR_DATA.timeline.dates) || []).length - 3),
  changeFilter: "全部",
  drawerOpen: false,
  drawerFindingId: (FIRST_FINDING && FIRST_FINDING.id) || null,
  checkedSteps: {},
  lastFocusEl: null
};

const CANVAS_W = 976;
const CANVAS_H = 410;
const NODE_W = 176;
const NODE_H = 112;
const COL_X = [10, 270, 530, 790];
const ROW_Y = [10, 144, 278];

let toastTimer = null;

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "\\"":"&quot;"}[c]));
}

function fmtNum(n) {
  if (n >= 10000) return (n / 10000).toFixed(1) + "w";
  return String(n);
}

function fmtPathBreaks(fp) {
  return esc(fp).replace(/\\//g, "/<wbr>");
}

function showToast(text) {
  const pill = document.getElementById("toast-pill");
  document.getElementById("toast-text").textContent = text;
  pill.setAttribute("data-show", "true");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { pill.setAttribute("data-show", "false"); }, 2400);
}

function copyTextSafe(text, okMsg) {
  const fallback = () => {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      showToast(okMsg);
    } catch {
      showToast("复制失败，请手动选中文本框复制");
    } finally {
      document.body.removeChild(ta);
    }
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => showToast(okMsg)).catch(fallback);
  } else {
    fallback();
  }
}

function syncSegIndicator(groupEl) {
  if (!groupEl) return;
  const indicator = groupEl.querySelector(".seg-indicator");
  const active = groupEl.querySelector(".seg-btn[aria-pressed='true'], .seg-btn[aria-selected='true']");
  if (!indicator || !active) return;
  if (window.getComputedStyle(indicator).display === "none") return;
  indicator.style.width = active.offsetWidth + "px";
  indicator.style.transform = "translateX(" + (active.offsetLeft - 4) + "px)";
}

function syncAllSegIndicators() {
  document.querySelectorAll(".seg-shell").forEach(syncSegIndicator);
}

function updateThemeButton() {
  const isLight = state.theme === "light";
  document.documentElement.setAttribute("data-theme", state.theme);
  document.getElementById("theme-label").textContent = isLight ? "暗色仪器" : "暖骨白模式";
  document.getElementById("theme-icon").innerHTML = isLight
    ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
    : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
}

function defaultElementForNode(nodeId) {
  const node = (RADAR_DATA.flow.nodes || []).find(n => n.id === nodeId);
  if (!node || !node.elements || !node.elements.length) return null;
  const bad = node.elements.find(e => e.status === "danger") || node.elements.find(e => e.status === "warn") || node.elements[0];
  return bad.id;
}

function switchTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll("#main-tabs .seg-btn").forEach(b => {
    b.setAttribute("aria-selected", String(b.getAttribute("data-tab") === tabName));
  });
  document.querySelectorAll(".tab-pane").forEach(p => {
    p.classList.toggle("active", p.id === "tab-" + tabName);
  });
  requestAnimationFrame(() => {
    syncAllSegIndicators();
    if (tabName === "flow") {
      renderFlow(true);
      renderDrilldown();
      renderSimulator();
    } else if (tabName === "changes") {
      renderTimeline(true);
    } else if (tabName === "overview") {
      renderMiniTimeline();
    }
  });
}

function nodeStatus(node) {
  const t = node.tech || {};
  const b = node.biz || {};
  const f = node.frustration || {};
  if (t.crash_rate >= 0.25 || (b.conv_delta <= -5 && t.p90_ms >= 1200)) return "danger";
  if (b.conv_delta <= -5 || f.backtrack_rate >= 20 || f.ai_correct_rate >= 12 || f.rage_click_rate >= 8) return "warn";
  return "ok";
}

function updateFlowScale() {
  const stage = document.getElementById("flow-stage");
  const sizer = document.getElementById("flow-stage-sizer");
  const canvas = document.getElementById("flow-canvas");
  if (!stage || !sizer || !canvas || stage.clientWidth === 0) return;
  const avail = Math.max(240, stage.clientWidth - 20);
  const scale = window.innerWidth < 680 ? 0.62 : Math.min(1, avail / CANVAS_W);
  sizer.style.width = Math.round(CANVAS_W * scale) + "px";
  sizer.style.height = Math.round(CANVAS_H * scale) + "px";
  canvas.style.transform = "scale(" + scale.toFixed(4) + ")";
}

/* ---------- Tab 1: 总览 ---------- */

function renderBentoSignals() {
  const wrap = document.getElementById("bento-strip");
  wrap.innerHTML = (RADAR_DATA.status_lights || []).map((l, idx) => {
    const isHero = idx === 0;
    const tagTxt = l.level === "danger" ? "建议阻断" : (l.level === "warn" ? "偏高需查" : "正常");
    const pillCls = l.level === "danger" ? "signal" : (l.level === "warn" ? "warn" : "ok");
    return '<button type="button" class="bento-cell level-' + esc(l.level) + (isHero ? ' bento-hero' : '') + '" data-tab-target="' + esc(l.focus_tab || "flow") + '" data-node="' + esc(l.focus_node) + '" data-mode="' + esc(l.focus_mode) + '">' +
      '<div class="bento-head"><span class="bento-title"><span class="dot-badge" aria-hidden="true"></span>' + esc(l.label) + '</span>' +
      '<span class="pill ' + pillCls + '">' + tagTxt + '</span></div>' +
      '<div class="bento-metric-row"><span class="bento-num">' + esc(l.metric || "") + '</span><span class="bento-metric-label">' + esc(l.metric_label || "") + '</span></div>' +
      '<p class="bento-summary">' + esc(l.summary) + '</p></button>';
  }).join("");

  wrap.querySelectorAll(".bento-cell").forEach(el => {
    el.addEventListener("click", () => {
      const targetTab = el.getAttribute("data-tab-target") || "flow";
      state.selectedNodeId = el.getAttribute("data-node");
      state.selectedElementId = defaultElementForNode(state.selectedNodeId);
      setMode(el.getAttribute("data-mode"));
      switchTab(targetTab);
    });
  });

  const hero = wrap.querySelector(".bento-hero");
  if (hero) {
    hero.addEventListener("pointermove", e => {
      const r = hero.getBoundingClientRect();
      const x = Math.round(((e.clientX - r.left) / Math.max(1, r.width)) * 100);
      const y = Math.round(((e.clientY - r.top) / Math.max(1, r.height)) * 100);
      hero.style.setProperty("--mx", x + "%");
      hero.style.setProperty("--my", y + "%");
    });
    hero.addEventListener("pointerleave", () => {
      hero.style.setProperty("--mx", "50%");
      hero.style.setProperty("--my", "0%");
    });
  }
}

function renderOverviewFindings() {
  const list = RADAR_DATA.findings || [];
  document.getElementById("finding-count").textContent = "重点 " + list.length + " 项";
  const wrap = document.getElementById("brief-queue");
  wrap.innerHTML = list.map(f => {
    const isDelivery = f.focus_tab === "delivery";
    const goLabel = isDelivery ? "看交付效率 ->" : "看页面细节 ->";
    const impactCls = f.severity === "P0" ? "signal" : "warn";
    return '<article class="brief-item">' +
      '<div class="brief-top">' +
      '<div class="brief-badges"><span class="sev-badge ' + esc(f.severity) + '">' + esc(f.severity) + '</span>' +
      '<span class="pill slate">' + esc(f.tag) + '</span>' +
      '<span class="pill ' + impactCls + '">' + esc(f.impact_badge || "") + '</span></div>' +
      '<div class="brief-btns">' +
      '<button type="button" class="btn-ghost" data-go-fid="' + esc(f.id) + '" data-go-tab="' + esc(f.focus_tab || "flow") + '" data-go-node="' + esc(f.node_id) + '" data-go-el="' + esc(f.element_id || "") + '" data-go-mode="' + esc(f.mode) + '">' + goLabel + '</button>' +
      '<button type="button" class="btn-ai-inline" data-action="open-ai" data-fid="' + esc(f.id) + '">AI 排查</button>' +
      '</div></div>' +
      '<h3 class="brief-title">' + esc(f.title) + '</h3>' +
      '<p class="brief-summary">' + esc(f.summary_one_line || f.fact) + '</p>' +
      '</article>';
  }).join("");

  wrap.querySelectorAll("[data-go-tab]").forEach(btn => {
    btn.addEventListener("click", () => {
      state.selectedFindingId = btn.getAttribute("data-go-fid");
      state.selectedNodeId = btn.getAttribute("data-go-node");
      state.selectedElementId = btn.getAttribute("data-go-el") || defaultElementForNode(state.selectedNodeId);
      setMode(btn.getAttribute("data-go-mode"));
      switchTab(btn.getAttribute("data-go-tab"));
    });
  });

  wrap.querySelectorAll("[data-action='open-ai']").forEach(btn => {
    btn.addEventListener("click", () => {
      const fid = btn.getAttribute("data-fid");
      state.selectedFindingId = fid;
      openDrawer(fid, btn);
    });
  });
}

function renderMiniTimeline() {
  const tl = RADAR_DATA.timeline;
  const svg = document.getElementById("mini-timeline-svg");
  const dates = tl.dates || [];
  const W = 440, H = 132, padL = 36, padR = 46, padT = 18, padB = 22;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const xStep = plotW / Math.max(1, dates.length - 1);
  const cx = i => padL + i * xStep;
  const cyC = v => padT + plotH - ((v - 45) / 30) * plotH;
  const cyM = v => padT + plotH - ((v - 800) / 900) * plotH;

  const cs = getComputedStyle(document.documentElement);
  const cGrid = cs.getPropertyValue("--ui-border").trim() || "#232936";
  const cMuted = cs.getPropertyValue("--ui-text-faint").trim() || "#788598";
  const cInfo = cs.getPropertyValue("--ui-info").trim() || "#38BDF8";
  const cSig = cs.getPropertyValue("--ui-signal").trim() || "#F97316";
  const cWarn = cs.getPropertyValue("--ui-warn").trim() || "#FBBF24";
  const cSurf = cs.getPropertyValue("--ui-surface").trim() || "#12151C";

  let out = '<defs><linearGradient id="mini-grad" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0%" stop-color="' + esc(cInfo) + '" stop-opacity="0.22"/>' +
    '<stop offset="100%" stop-color="' + esc(cInfo) + '" stop-opacity="0.01"/></linearGradient></defs>';

  [48, 60, 72].forEach(v => {
    const y = cyC(v);
    out += '<line x1="' + padL + '" y1="' + y + '" x2="' + (W - padR) + '" y2="' + y + '" stroke="' + esc(cGrid) + '" stroke-dasharray="3,3" />';
  });

  const dateIdx = {};
  dates.forEach((d, i) => { dateIdx[d] = i; });
  const drawn = {};
  (tl.changes || []).forEach(c => {
    const i = dateIdx[c.date];
    if (i !== undefined && !drawn[c.date]) {
      drawn[c.date] = true;
      out += '<line x1="' + cx(i) + '" y1="' + padT + '" x2="' + cx(i) + '" y2="' + (H - padB) + '" stroke="' + esc(cWarn) + '" stroke-width="1.2" stroke-dasharray="2,2" />';
    }
  });

  const convPts = tl.biz_conv.map((v, i) => cx(i) + "," + cyC(v));
  const areaPts = convPts.join(" ") + " " + cx(dates.length - 1) + "," + (H - padB) + " " + cx(0) + "," + (H - padB);
  const msPts = tl.tech_p90_ms.map((v, i) => cx(i) + "," + cyM(v)).join(" ");
  out += '<polygon points="' + areaPts + '" fill="url(#mini-grad)" />';
  out += '<polyline fill="none" stroke="' + esc(cInfo) + '" stroke-width="2.2" points="' + convPts.join(" ") + '" />';
  out += '<polyline fill="none" stroke="' + esc(cSig) + '" stroke-width="1.8" stroke-dasharray="4,3" points="' + msPts + '" />';

  dates.forEach((d, i) => {
    out += '<circle cx="' + cx(i) + '" cy="' + cyC(tl.biz_conv[i]) + '" r="3" fill="' + esc(cSurf) + '" stroke="' + esc(cInfo) + '" stroke-width="1.8" />';
    if (i === 0 || i === 3 || i === dates.length - 1) {
      out += '<text x="' + cx(i) + '" y="' + (H - 4) + '" text-anchor="middle" font-size="11" font-family="SF Mono, Menlo, monospace" fill="' + esc(cMuted) + '">' + esc(d) + '</text>';
    }
  });
  out += '<text x="' + (padL - 6) + '" y="' + (cyC(tl.biz_conv[0]) + 4) + '" text-anchor="end" font-size="11" font-family="SF Mono, Menlo, monospace" font-weight="700" fill="' + esc(cInfo) + '">' + tl.biz_conv[0] + '%</text>';
  out += '<text x="' + (W - padR + 6) + '" y="' + (cyC(tl.biz_conv[dates.length - 1]) + 4) + '" text-anchor="start" font-size="11" font-family="SF Mono, Menlo, monospace" font-weight="700" fill="' + esc(cInfo) + '">' + tl.biz_conv[dates.length - 1] + '%</text>';
  out += '<text x="' + (W - padR + 6) + '" y="' + (cyM(tl.tech_p90_ms[dates.length - 1]) + 4) + '" text-anchor="start" font-size="11" font-family="SF Mono, Menlo, monospace" font-weight="700" fill="' + esc(cSig) + '">' + tl.tech_p90_ms[dates.length - 1] + 'ms</text>';

  svg.innerHTML = out;

  const firstC = tl.biz_conv[0], lastC = tl.biz_conv[dates.length - 1];
  const firstM = tl.tech_p90_ms[0], lastM = tl.tech_p90_ms[dates.length - 1];
  document.getElementById("mini-timeline-foot").innerHTML =
    '<span>转化率 <strong class="mono">' + firstC + '% -> ' + lastC + '%</strong></span>' +
    '<span>采集 P90 <strong class="mono">' + firstM + 'ms -> ' + lastM + 'ms</strong>（虚线）</span>';
}

function renderOverviewSinks() {
  const eng = RADAR_DATA.engineering || {};
  const sinks = eng.time_sinks || [];
  const maxPd = Math.max(1, ...sinks.map(s => s.waste_pd_month));
  document.getElementById("overview-sinks").innerHTML = sinks.map(s => {
    const pct = Math.round((s.waste_pd_month / maxPd) * 100);
    return '<div><div class="sink-row-top"><span class="sink-row-name">' + esc(s.item) + '</span>' +
      '<span class="sink-row-pd">' + s.waste_pd_month.toFixed(1) + ' 人天/月</span></div>' +
      '<div class="bar-track"><div class="bar-fill bad" style="width:' + pct + '%"></div></div></div>';
  }).join("");

  const alertTeam = (eng.subteams || []).find(t => t.status === "alert");
  const alertEl = document.getElementById("overview-team-alert");
  if (alertTeam) {
    alertEl.style.display = "block";
    alertEl.textContent = "重点关注：" + alertTeam.name + "按期率跌至 " + alertTeam.on_time_rate + "%（比上月 " + alertTeam.mom_delta + "%）";
  } else {
    alertEl.style.display = "none";
  }
}

/* ---------- Tab 2: 页面转化（流向 + 人群 + 仿真手机元素透视） ---------- */

function renderFlow(animate) {
  const nodes = RADAR_DATA.flow.nodes;
  const edges = RADAR_DATA.flow.edges;
  const nodePos = {};
  const connected = {};
  nodes.forEach(n => {
    nodePos[n.id] = { x: COL_X[n.col] || 10, y: ROW_Y[n.row] || 10, w: NODE_W, h: NODE_H };
  });
  edges.forEach(e => {
    if (e.from === state.selectedNodeId || e.to === state.selectedNodeId) {
      connected[e.from] = true;
      connected[e.to] = true;
    }
  });
  connected[state.selectedNodeId] = true;

  const nodesWrap = document.getElementById("flow-nodes");
  if (animate) {
    nodesWrap.classList.remove("blur-enter");
    void nodesWrap.offsetWidth;
    nodesWrap.classList.add("blur-enter");
  }

  nodesWrap.innerHTML = nodes.map(n => {
    const pos = nodePos[n.id];
    const st = nodeStatus(n);
    const sel = n.id === state.selectedNodeId ? "selected" : (connected[n.id] ? "" : "dimmed");
    const b = n.biz, t = n.tech, f = n.frustration;
    const vol = state.caliber === "uv" ? fmtNum(b.uv) + " 人" : fmtNum(b.pv) + " 次";

    let kvs = [];
    if (state.mode === "biz") {
      kvs = [
        ["规模", vol, ""],
        ["转化", b.conv_rate.toFixed(1) + "%", b.conv_delta <= -5 ? "v-bad" : "v-ok"],
        ["较基线", (b.conv_delta >= 0 ? "+" : "") + b.conv_delta.toFixed(1) + "%", b.conv_delta <= -5 ? "v-bad" : ""],
        ["停留", b.stay_sec.toFixed(1) + "s", ""]
      ];
    } else if (state.mode === "tech") {
      kvs = [
        ["P90耗时", t.p90_ms + "ms", t.p90_ms >= 1200 ? "v-bad" : ""],
        ["崩溃", t.crash_rate.toFixed(2) + "%", t.crash_rate >= 0.25 ? "v-bad" : "v-ok"],
        ["掉帧", t.drop3_rate.toFixed(1) + "%", t.drop3_rate >= 6 ? "v-warn" : ""],
        ["报错", t.api_err_rate.toFixed(2) + "%", t.api_err_rate >= 1 ? "v-bad" : ""]
      ];
    } else if (state.mode === "frustration") {
      kvs = [
        ["退回", f.backtrack_rate.toFixed(1) + "%", f.backtrack_rate >= 20 ? "v-warn" : ""],
        ["连点", f.rage_click_rate.toFixed(1) + "%", f.rage_click_rate >= 8 ? "v-warn" : ""],
        ["AI改错", f.ai_correct_rate.toFixed(1) + "%", f.ai_correct_rate >= 12 ? "v-bad" : ""],
        ["半路关", f.stream_abort_rate.toFixed(1) + "%", f.stream_abort_rate >= 15 ? "v-warn" : ""]
      ];
    } else {
      kvs = [
        ["转化变", (b.conv_delta >= 0 ? "+" : "") + b.conv_delta.toFixed(1) + "%", b.conv_delta <= -5 ? "v-bad" : "v-ok"],
        ["崩溃", t.crash_rate.toFixed(2) + "%", t.crash_rate >= 0.25 ? "v-bad" : ""],
        ["退回", f.backtrack_rate.toFixed(1) + "%", f.backtrack_rate >= 20 ? "v-warn" : ""],
        ["AI改错", f.ai_correct_rate.toFixed(1) + "%", f.ai_correct_rate >= 12 ? "v-bad" : ""]
      ];
    }

    const kvHtml = kvs.map(([k, v, cls]) =>
      '<div class="metric-kv"><span class="k">' + esc(k) + '</span><span class="v ' + cls + '">' + esc(v) + '</span></div>'
    ).join("");
    const stTxt = st === "danger" ? "高危" : (st === "warn" ? "异常" : "正常");

    return '<button type="button" class="flow-node status-' + st + ' ' + sel + '" data-id="' + esc(n.id) + '" style="left:' + pos.x + 'px;top:' + pos.y + 'px;" aria-pressed="' + (n.id === state.selectedNodeId) + '">' +
      '<div class="node-top"><span>' + esc(n.stage) + '</span><span class="node-status-tag ' + st + '">' + stTxt + '</span></div>' +
      '<div class="node-title">' + esc(n.title) + '</div>' +
      '<div class="node-metrics">' + kvHtml + '</div></button>';
  }).join("");

  nodesWrap.querySelectorAll(".flow-node").forEach(el => {
    const id = el.getAttribute("data-id");
    if (nodePos[id] && el.offsetHeight) {
      nodePos[id].h = el.offsetHeight;
    }
    el.addEventListener("click", () => {
      state.selectedNodeId = id;
      state.selectedElementId = defaultElementForNode(id);
      renderFlow(false);
      renderDrilldown();
      renderSimulator();
    });
  });

  const svg = document.getElementById("flow-svg");
  const cs = getComputedStyle(document.documentElement);
  const cEdge = cs.getPropertyValue("--ui-border-strong").trim() || "#343E52";
  const cBad = cs.getPropertyValue("--ui-signal").trim() || "#F97316";
  const cBadBg = cs.getPropertyValue("--ui-signal-soft").trim() || "#2D180C";
  const cBadBd = cs.getPropertyValue("--ui-signal-border").trim() || "#6B3414";
  const cSurf = cs.getPropertyValue("--ui-surface").trim() || "#12151C";
  const cText = cs.getPropertyValue("--ui-text").trim() || "#EEF2F6";

  let svgHtml = '<defs>' +
    '<marker id="arrow-ok" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,1 L6,3.5 L0,6 Z" fill="' + esc(cEdge) + '"/></marker>' +
    '<marker id="arrow-bad" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,1 L6,3.5 L0,6 Z" fill="' + esc(cBad) + '"/></marker>' +
    '</defs>';

  edges.forEach(e => {
    const a = nodePos[e.from], b = nodePos[e.to];
    if (!a || !b) return;
    let x1, y1, x2, y2;
    if (Math.abs(a.x - b.x) < 10) {
      x1 = a.x + a.w / 2; y1 = a.y + a.h + 3;
      x2 = b.x + b.w / 2; y2 = b.y - 3;
    } else {
      x1 = a.x + a.w; y1 = a.y + a.h / 2;
      x2 = b.x - 3; y2 = b.y + b.h / 2;
    }
    const ctr = state.caliber === "uv" ? e.uv_ctr : e.pv_ctr;
    const delta = state.caliber === "uv" ? e.uv_delta : e.pv_delta;
    const isBad = delta <= -5;
    const isRel = e.from === state.selectedNodeId || e.to === state.selectedNodeId;
    const stroke = isBad ? cBad : cEdge;
    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2;
    const cpx1 = Math.abs(a.x - b.x) < 10 ? x1 : x1 + (x2 - x1) * 0.45;
    const cpy1 = Math.abs(a.x - b.x) < 10 ? y1 + (y2 - y1) * 0.5 : y1;
    const cpx2 = Math.abs(a.x - b.x) < 10 ? x2 : x2 - (x2 - x1) * 0.45;
    const cpy2 = Math.abs(a.x - b.x) < 10 ? y2 - (y2 - y1) * 0.5 : y2;

    svgHtml += '<g opacity="' + (isRel ? "1" : "0.60") + '">' +
      '<path class="' + (isRel ? 'flow-edge-active' : '') + '" d="M' + x1 + ',' + y1 + ' C' + cpx1 + ',' + cpy1 + ' ' + cpx2 + ',' + cpy2 + ' ' + x2 + ',' + y2 + '" fill="none" stroke="' + esc(stroke) + '" stroke-width="' + (isBad ? 2.2 : 1.5) + '" marker-end="url(#' + (isBad ? 'arrow-bad' : 'arrow-ok') + ')" />';
    const badgeText = ctr.toFixed(0) + "% (" + (delta >= 0 ? "+" : "") + delta.toFixed(1) + ")";
    svgHtml += '<g transform="translate(' + midX + ',' + midY + ')">' +
      '<rect x="-37" y="-10" width="74" height="20" rx="5" fill="' + esc(isBad ? cBadBg : cSurf) + '" stroke="' + esc(isBad ? cBadBd : cEdge) + '" />' +
      '<text x="0" y="3.5" text-anchor="middle" font-size="10.5" font-family="SF Mono, Menlo, Consolas, monospace" font-weight="700" fill="' + esc(isBad ? cBad : cText) + '">' + esc(badgeText) + '</text>' +
      '</g></g>';
  });
  svg.innerHTML = svgHtml;

  updateFlowScale();
}

function renderDrilldown() {
  const box = document.getElementById("drilldown-box");
  const node = RADAR_DATA.flow.nodes.find(n => n.id === state.selectedNodeId);
  if (!node) { box.innerHTML = ""; return; }

  const slices = node.slices || {};
  const shortLbl = s => s.replace(/\\(5%\\)/g, "").replace("老用户（连续提交）", "老用户连提").replace("首次使用新客", "首次新客");
  const colsHtml = Object.keys(slices).map(dim => {
    const rows = slices[dim].map(r => {
      const isBad = r.crash >= 0.25 || r.biz < 55;
      const fillCls = isBad ? "bad" : (r.biz >= 70 ? "ok" : "");
      return '<div class="slice-row">' +
        '<div class="slice-label"><span>' + esc(shortLbl(r.label)) + '</span><span class="slice-val">' + r.biz.toFixed(1) + '% · ' + r.tech_ms + 'ms · ' + r.crash.toFixed(2) + '%</span></div>' +
        '<div class="bar-track"><div class="bar-fill ' + fillCls + '" style="width:' + Math.min(100, Math.max(8, r.biz)) + '%"></div></div></div>';
    }).join("");
    return '<div class="slice-col"><h3>' + esc(dim) + '</h3>' + rows + '</div>';
  }).join("");

  box.innerHTML = '<div class="drilldown-grid">' + colsHtml + '</div>';
}

function renderSimulator() {
  const node = RADAR_DATA.flow.nodes.find(n => n.id === state.selectedNodeId);
  if (!node) return;
  const elements = node.elements || [];
  let curEl = elements.find(e => e.id === state.selectedElementId);
  if (!curEl && elements.length) {
    state.selectedElementId = defaultElementForNode(node.id);
    curEl = elements.find(e => e.id === state.selectedElementId) || elements[0];
  }

  document.getElementById("sim-page-title").textContent = "仿真页面：" + node.title;
  document.getElementById("sim-page-sub").textContent = "负责小组：" + (node.owner || "待明确") + " ｜ 点击手机里每个元素查看埋点和代码";

  const matchFinding = (RADAR_DATA.findings || []).find(f => f.node_id === node.id);
  const actionsWrap = document.getElementById("sim-head-actions");
  actionsWrap.innerHTML = matchFinding
    ? '<button type="button" class="btn-ai-inline" data-sim-ai="' + esc(matchFinding.id) + '">' +
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3z"/></svg>' +
      '<span>AI 排查此页</span></button>'
    : '<span class="pill ok">页面表现健康</span>';
  const simAiBtn = actionsWrap.querySelector("[data-sim-ai]");
  if (simAiBtn) {
    simAiBtn.addEventListener("click", () => { openDrawer(simAiBtn.getAttribute("data-sim-ai"), simAiBtn); });
  }

  const kindMap = { header: "顶栏", hero: "主画布", card: "内容卡", modal: "阻断弹窗", action: "主按钮", tabbar: "底栏" };
  const elBadge = e => {
    if (state.mode === "tech") return e.p90_ms + "ms / " + e.err_rate.toFixed(2) + "%";
    if (state.mode === "frustration") return "卡壳 " + e.issue_rate.toFixed(1) + "%";
    return "CTR " + e.ctr.toFixed(1) + "%";
  };

  const screen = document.getElementById("phone-screen");
  screen.innerHTML =
    '<div class="phone-statusbar"><span class="mono">9:41</span><span class="phone-notch" aria-hidden="true"></span><span class="mono">5G</span></div>' +
    '<div class="phone-app-title">' + esc(node.title) + '</div>' +
    elements.map(e => {
      const sel = curEl && curEl.id === e.id;
      return '<button type="button" class="phone-el-btn kind-' + esc(e.kind) + ' status-' + esc(e.status) + '" data-el-id="' + esc(e.id) + '" aria-pressed="' + sel + '">' +
        '<div class="el-top-row"><span class="el-kind-tag">' + esc(kindMap[e.kind] || "模块") + '</span>' +
        '<span class="el-metric-badge ' + esc(e.status) + '">' + esc(elBadge(e)) + '</span></div>' +
        '<div class="el-name">' + esc(e.name) + '</div></button>';
    }).join("");

  screen.querySelectorAll(".phone-el-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      state.selectedElementId = btn.getAttribute("data-el-id");
      renderSimulator();
    });
  });

  const detailCol = document.getElementById("el-detail-col");
  if (!curEl) { detailCol.innerHTML = ""; return; }
  const ratio = state.caliber === "pv" ? 1.55 : 1;
  const expText = fmtNum(Math.round(curEl.exposure * ratio)) + (state.caliber === "pv" ? " 次" : " 人");
  const deltaStr = (curEl.ctr_delta >= 0 ? "+" : "") + curEl.ctr_delta.toFixed(1) + "%";
  const stPill = curEl.status === "danger" ? '<span class="pill signal">重点异常</span>' : (curEl.status === "warn" ? '<span class="pill warn">偏高需看</span>' : '<span class="pill ok">正常</span>');

  const chipsHtml = elements.map((e, i) =>
    '<button type="button" class="el-chip-btn" role="tab" aria-selected="' + (e.id === curEl.id) + '" data-chip-el="' + esc(e.id) + '">' + (i + 1) + '. ' + esc(kindMap[e.kind] || "元素") + '</button>'
  ).join("");

  detailCol.innerHTML =
    '<div class="el-chips-row" role="tablist" aria-label="页面内元素快选">' + chipsHtml + '</div>' +
    '<div class="el-detail-card">' +
    '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;"><h3 class="el-detail-title">' + esc(curEl.name) + '</h3>' + stPill + '</div>' +
    '<div class="el-kpi-grid">' +
    '<div class="el-kpi-box"><span class="el-kpi-label">点击率 CTR</span><div class="el-kpi-val ' + (curEl.ctr_delta <= -5 ? 'bad' : 'ok') + '">' + curEl.ctr.toFixed(1) + '%</div><span class="el-kpi-label">较基线 ' + deltaStr + '</span></div>' +
    '<div class="el-kpi-box"><span class="el-kpi-label">耗时 / 卡壳</span><div class="el-kpi-val ' + (curEl.status === 'danger' ? 'bad' : '') + '">' + curEl.p90_ms + 'ms</div><span class="el-kpi-label">异常卡壳 ' + curEl.issue_rate.toFixed(1) + '%</span></div>' +
    '</div>' +
    '<div class="el-meta-rows">' +
    '<div>曝光量：<strong class="mono">' + esc(expText) + '</strong> ｜ 错误率：<strong class="mono">' + curEl.err_rate.toFixed(2) + '%</strong></div>' +
    '<div>埋点事件：<span class="inline-code">' + esc(curEl.event) + '</span></div>' +
    '<div>代码位置：<button type="button" class="code-chip" data-copy-el-file="' + esc(curEl.code_file) + '" title="点击复制路径">' + fmtPathBreaks(curEl.code_file) + '</button></div>' +
    '</div>' +
    '<div class="el-note-box ' + esc(curEl.status) + '"><strong>分析说明：</strong>' + esc(curEl.note) + '</div>' +
    '</div>';

  detailCol.querySelectorAll("[data-chip-el]").forEach(btn => {
    btn.addEventListener("click", () => {
      state.selectedElementId = btn.getAttribute("data-chip-el");
      renderSimulator();
    });
  });

  const cpBtn = detailCol.querySelector("[data-copy-el-file]");
  if (cpBtn) {
    cpBtn.addEventListener("click", () => {
      const fp = cpBtn.getAttribute("data-copy-el-file");
      copyTextSafe(fp, "已复制代码路径：" + fp);
    });
  }
}

/* ---------- Tab 3: 上线变动 ---------- */

function renderChangeFilters() {
  const changes = RADAR_DATA.timeline.changes || [];
  const types = ["全部", ...Array.from(new Set(changes.map(c => c.type)))];
  const bar = document.getElementById("change-filter-bar");
  bar.innerHTML = types.map(tp =>
    '<button type="button" class="filter-chip" data-ctype="' + esc(tp) + '" aria-pressed="' + (state.changeFilter === tp) + '">' + esc(tp) + '</button>'
  ).join("");
  bar.querySelectorAll(".filter-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      state.changeFilter = btn.getAttribute("data-ctype");
      renderChangeFilters();
      renderTimeline(true);
    });
  });
}

function renderTimeline(showTip) {
  const tl = RADAR_DATA.timeline;
  const svg = document.getElementById("timeline-svg");
  const tooltip = document.getElementById("chart-tooltip");
  const dates = tl.dates;
  const W = 720, H = 276, padL = 56, padR = 78, padT = 32, padB = 34;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const xStep = plotW / Math.max(1, dates.length - 1);

  const convMin = 45, convMax = 75;
  const msMin = 800, msMax = 1700;
  const cx = i => padL + i * xStep;
  const cyConv = v => padT + plotH - ((v - convMin) / (convMax - convMin)) * plotH;
  const cyMs = v => padT + plotH - ((v - msMin) / (msMax - msMin)) * plotH;

  const cs = getComputedStyle(document.documentElement);
  const cGrid = cs.getPropertyValue("--ui-border").trim() || "#232936";
  const cMuted = cs.getPropertyValue("--ui-text-faint").trim() || "#788598";
  const cInfo = cs.getPropertyValue("--ui-info").trim() || "#38BDF8";
  const cSig = cs.getPropertyValue("--ui-signal").trim() || "#F97316";
  const cWarn = cs.getPropertyValue("--ui-warn").trim() || "#FBBF24";
  const cWarnSoft = cs.getPropertyValue("--ui-warn-soft").trim() || "#2C220D";
  const cWarnBd = cs.getPropertyValue("--ui-warn-border").trim() || "#5E4819";
  const cSurf = cs.getPropertyValue("--ui-surface-inset").trim() || "#0C0E13";

  let out = '<defs><linearGradient id="conv-area-grad" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0%" stop-color="' + esc(cInfo) + '" stop-opacity="0.22"/>' +
    '<stop offset="100%" stop-color="' + esc(cInfo) + '" stop-opacity="0.01"/></linearGradient></defs>';

  const yTicksConv = [45, 55, 65, 75];
  const yTicksMs = [800, 1100, 1400, 1700];
  for (let g = 0; g < yTicksConv.length; g++) {
    const y = cyConv(yTicksConv[g]);
    out += '<line x1="' + padL + '" y1="' + y + '" x2="' + (W - padR) + '" y2="' + y + '" stroke="' + esc(cGrid) + '" stroke-dasharray="3,3" />' +
      '<text x="' + (padL - 8) + '" y="' + (y + 4) + '" text-anchor="end" font-size="11" font-family="SF Mono, Menlo, monospace" fill="' + esc(cInfo) + '">' + yTicksConv[g] + '%</text>' +
      '<text x="' + (W - padR + 12) + '" y="' + (y + 4) + '" text-anchor="start" font-size="11" font-family="SF Mono, Menlo, monospace" fill="' + esc(cSig) + '">' + yTicksMs[g] + 'ms</text>';
  }

  dates.forEach((d, i) => {
    const isSel = i === state.selectedDayIdx;
    out += '<text x="' + cx(i) + '" y="' + (H - 10) + '" text-anchor="middle" font-size="12" font-family="SF Mono, Menlo, monospace" font-weight="' + (isSel ? '700' : '500') + '" fill="' + esc(isSel ? cInfo : cMuted) + '">' + esc(d) + '</text>';
  });

  const visibleChanges = tl.changes.filter(c => state.changeFilter === "全部" || c.type === state.changeFilter);
  const dateIdx = {};
  dates.forEach((d, i) => { dateIdx[d] = i; });
  const seenDate = {};
  visibleChanges.forEach(c => {
    const i = dateIdx[c.date];
    if (i === undefined) return;
    seenDate[c.date] = (seenDate[c.date] || 0) + 1;
    const x = cx(i);
    out += '<line x1="' + x + '" y1="' + padT + '" x2="' + x + '" y2="' + (H - padB) + '" stroke="' + esc(cWarn) + '" stroke-width="1.4" stroke-dasharray="3,3" />';
    if (seenDate[c.date] === 1) {
      out += '<rect x="' + (x - 24) + '" y="4" width="48" height="20" rx="6" fill="' + esc(cWarnSoft) + '" stroke="' + esc(cWarnBd) + '" />' +
        '<text x="' + x + '" y="18" text-anchor="middle" font-size="11" font-weight="700" fill="' + esc(cWarn) + '">有改动</text>';
    }
  });

  const selX = cx(state.selectedDayIdx);
  out += '<line x1="' + selX + '" y1="' + padT + '" x2="' + selX + '" y2="' + (H - padB) + '" stroke="' + esc(cInfo) + '" stroke-width="1.5" opacity="0.65" />';

  const convPts = tl.biz_conv.map((v, i) => cx(i) + "," + cyConv(v));
  const areaPts = convPts.join(" ") + " " + cx(dates.length - 1) + "," + (H - padB) + " " + cx(0) + "," + (H - padB);
  const msPts = tl.tech_p90_ms.map((v, i) => cx(i) + "," + cyMs(v)).join(" ");
  out += '<polygon points="' + areaPts + '" fill="url(#conv-area-grad)" />';
  out += '<polyline fill="none" stroke="' + esc(cInfo) + '" stroke-width="2.5" stroke-linejoin="round" points="' + convPts.join(" ") + '" />';
  out += '<polyline fill="none" stroke="' + esc(cSig) + '" stroke-width="2.2" stroke-dasharray="6,4" stroke-linejoin="round" points="' + msPts + '" />';

  tl.biz_conv.forEach((v, i) => {
    const act = i === state.selectedDayIdx;
    const isLast = i === dates.length - 1;
    const tx = isLast ? (cx(i) - 6) : cx(i);
    const anchor = isLast ? "end" : "middle";
    out += '<circle cx="' + cx(i) + '" cy="' + cyConv(v) + '" r="' + (act ? 6 : 4) + '" fill="' + esc(act ? cInfo : cSurf) + '" stroke="' + esc(cInfo) + '" stroke-width="2" />';
    out += '<circle cx="' + cx(i) + '" cy="' + cyMs(tl.tech_p90_ms[i]) + '" r="' + (act ? 5.5 : 3.5) + '" fill="' + esc(act ? cSig : cSurf) + '" stroke="' + esc(cSig) + '" stroke-width="2" />';
    out += '<text x="' + tx + '" y="' + (cyConv(v) - 10) + '" text-anchor="' + anchor + '" font-size="11" font-family="SF Mono, Menlo, monospace" font-weight="700" stroke="' + esc(cSurf) + '" stroke-width="4" paint-order="stroke" fill="' + esc(cInfo) + '">' + v + '%</text>';
  });

  dates.forEach((d, i) => {
    const hw = Math.max(36, xStep * 0.8);
    out += '<rect x="' + (cx(i) - hw / 2) + '" y="' + padT + '" width="' + hw + '" height="' + plotH + '" fill="transparent" data-day-idx="' + i + '" style="cursor:pointer" />';
  });

  svg.innerHTML = out;
  svg.querySelectorAll("[data-day-idx]").forEach(rect => {
    const idx = Number(rect.getAttribute("data-day-idx"));
    rect.addEventListener("mouseenter", () => { state.selectedDayIdx = idx; renderTimeline(true); });
    rect.addEventListener("click", () => { state.selectedDayIdx = idx; renderTimeline(true); });
  });

  const activeDate = dates[state.selectedDayIdx];
  const dayChanges = visibleChanges.filter(c => c.date === activeDate);
  if (showTip && activeDate) {
    const cStr = dayChanges.length ? " ｜ 当日变动：" + dayChanges.map(c => c.type).join("、") : "";
    tooltip.innerHTML = '<strong>' + esc(activeDate) + '</strong> · 转化 <span class="mono">' + tl.biz_conv[state.selectedDayIdx] + '%</span> · P90 <span class="mono">' + tl.tech_p90_ms[state.selectedDayIdx] + 'ms</span> · 崩溃 <span class="mono">' + tl.crash_rate[state.selectedDayIdx].toFixed(2) + '%</span>' + esc(cStr);
    tooltip.setAttribute("data-show", "true");
  } else {
    tooltip.setAttribute("data-show", "false");
  }

  const chWrap = document.getElementById("change-list");
  chWrap.innerHTML = visibleChanges.map((c, idx) => {
    const cls = c.date === activeDate ? "highlight" : "";
    const focusBtn = c.focus_node
      ? '<button type="button" class="link-btn" data-chg-node="' + esc(c.focus_node) + '" data-chg-mode="' + esc(c.focus_mode || "all") + '">去页面转化看影响 -&gt;</button>'
      : "";
    return '<div class="change-row ' + cls + '">' +
      '<button type="button" class="change-select-btn" data-date="' + esc(c.date) + '" data-idx="' + idx + '">' +
      '<div class="change-top"><span class="mono">[' + esc(c.date) + '] ' + esc(c.type) + '</span><span>' + esc(c.owner) + '</span></div>' +
      '<div class="change-title">' + esc(c.title) + '</div>' +
      '<div class="change-impact">' + esc(c.impact) + '</div></button>' +
      (focusBtn ? '<div class="change-foot">' + focusBtn + '</div>' : '') + '</div>';
  }).join("");

  chWrap.querySelectorAll(".change-select-btn").forEach(el => {
    el.addEventListener("click", () => {
      const i = dateIdx[el.getAttribute("data-date")];
      if (i !== undefined) { state.selectedDayIdx = i; renderTimeline(true); }
    });
  });

  chWrap.querySelectorAll("[data-chg-node]").forEach(btn => {
    btn.addEventListener("click", () => {
      state.selectedNodeId = btn.getAttribute("data-chg-node");
      state.selectedElementId = defaultElementForNode(state.selectedNodeId);
      setMode(btn.getAttribute("data-chg-mode"));
      switchTab("flow");
    });
  });
}

/* ---------- Tab 4: 交付效率 ---------- */

function renderSparkBars(vals, status) {
  if (!vals || !vals.length) return "";
  const w = 68, h = 22, bw = 8, gap = 3;
  const minV = 60, maxV = 100;
  const cls = status === "alert" ? "var(--ui-signal)" : (status === "watch" ? "var(--ui-warn)" : "var(--ui-accent)");
  const bars = vals.map((v, i) => {
    const ratio = Math.max(0.15, Math.min(1, (v - minV) / (maxV - minV)));
    const bh = Math.round(ratio * (h - 2));
    const x = i * (bw + gap);
    const y = h - bh;
    const op = i === vals.length - 1 ? "1" : "0.45";
    return '<rect x="' + x + '" y="' + y + '" width="' + bw + '" height="' + bh + '" rx="2" fill="' + cls + '" opacity="' + op + '" />';
  }).join("");
  return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '" aria-hidden="true">' + bars + '</svg>';
}

function renderDelivery() {
  const eng = RADAR_DATA.engineering;
  const totalWaste = (eng.time_sinks || []).reduce((acc, s) => acc + (s.waste_pd_month || 0), 0);
  const alertTeams = (eng.subteams || []).filter(t => t.status === "alert");
  const reworkList = eng.rework_files || [];

  document.getElementById("delivery-strip").innerHTML =
    '<div class="bento-cell level-warn">' +
    '<div class="bento-head"><span class="bento-title"><span class="dot-badge" aria-hidden="true"></span>本月额外耗时</span><span class="pill warn">待优化</span></div>' +
    '<div class="bento-metric-row"><span class="bento-num">' + totalWaste.toFixed(1) + ' 人天</span><span class="bento-metric-label">编译排队 + 手工回归 + 答疑</span></div>' +
    '<p class="bento-summary">把等待和重复答疑省下来，相当于多出近两人月研发时间</p></div>' +

    '<div class="bento-cell level-danger">' +
    '<div class="bento-head"><span class="bento-title"><span class="dot-badge" aria-hidden="true"></span>明显下滑小组</span><span class="pill signal">重点关注</span></div>' +
    '<div class="bento-metric-row"><span class="bento-num" style="color:var(--ui-signal);">' + alertTeams.length + ' 个</span><span class="bento-metric-label">按期率跌破 85% 且环比跌超 15%</span></div>' +
    '<p class="bento-summary">' + esc(alertTeams.map(t => t.name + "（" + t.on_time_rate + "%）").join("、") || "暂无明显下滑小组") + '</p></div>' +

    '<div class="bento-cell level-ok">' +
    '<div class="bento-head"><span class="bento-title"><span class="dot-badge" aria-hidden="true"></span>7 天反复修改文件</span><span class="pill ok">发版热修</span></div>' +
    '<div class="bento-metric-row"><span class="bento-num">' + reworkList.length + ' 个</span><span class="bento-metric-label">修改 3 次及以上的核心文件</span></div>' +
    '<p class="bento-summary">集中在端侧多媒体内存、流式渲染与多目标识别</p></div>';

  document.getElementById("subteams-table").innerHTML =
    '<thead><tr><th>业务小组</th><th>近 6 周趋势</th><th class="num">按期上线率</th><th class="num">比上月</th><th class="num">提测打回</th><th>当前状态</th><th>主要原因</th></tr></thead><tbody>' +
    eng.subteams.map(t => {
      const stPill = t.status === "alert" ? '<span class="pill signal">明显下滑</span>' : (t.status === "watch" ? '<span class="pill warn">需留意</span>' : '<span class="pill ok">稳定</span>');
      const deltaStr = (t.mom_delta >= 0 ? "+" : "") + t.mom_delta + "%";
      return '<tr><td><strong>' + esc(t.name) + '</strong></td><td>' + renderSparkBars(t.trend, t.status) + '</td><td class="num">' + t.on_time_rate + '%</td><td class="num">' + deltaStr + '</td><td class="num">' + t.reopen_count + ' 次</td><td>' + stPill + '</td><td>' + esc(t.note) + '</td></tr>';
    }).join("") + '</tbody>';

  document.getElementById("rework-table").innerHTML =
    '<thead><tr><th style="width:44%;">文件名</th><th class="num">7 天修改</th><th>返工原因</th></tr></thead><tbody>' +
    reworkList.map(r =>
      '<tr><td><span class="code-chip">' + fmtPathBreaks(r.file) + '</span></td><td class="num"><strong>' + r.rework_7d + ' 次</strong></td><td>' + esc(r.reason) + '</td></tr>'
    ).join("") + '</tbody>';

  const maxPd = Math.max(1, ...eng.time_sinks.map(s => s.waste_pd_month));
  document.getElementById("sinks-list").innerHTML = eng.time_sinks.map(s => {
    const pct = Math.round((s.waste_pd_month / maxPd) * 100);
    return '<div><div class="sink-row-top"><span class="sink-row-name">' + esc(s.item) + '</span><span class="sink-row-pd">' + s.waste_pd_month.toFixed(1) + ' 人天/月</span></div>' +
      '<div class="bar-track"><div class="bar-fill bad" style="width:' + pct + '%"></div></div>' +
      '<div class="sink-row-detail">' + esc(s.detail) + '</div></div>';
  }).join("");
}

/* ---------- 右侧 AI 排查抽屉 ---------- */

function renderDrawer() {
  const findings = RADAR_DATA.findings || [];
  const f = findings.find(x => x.id === state.drawerFindingId) || findings[0];
  if (!f) return;

  const chipNames = {
    "f_page_capture_tech": "P0 崩溃卡顿",
    "f_page_confirm_ux": "P1 弹窗退回",
    "f_page_parse_ai": "P1 AI 改错",
    "f_eng_rework": "P2 返工耗时"
  };
  document.getElementById("drawer-switcher").innerHTML = findings.map(item =>
    '<button type="button" class="switch-chip" role="tab" aria-selected="' + (item.id === f.id) + '" data-sw-fid="' + esc(item.id) + '">' +
    esc(chipNames[item.id] || (item.severity + ' ' + item.tag)) + '</button>'
  ).join("");

  document.getElementById("drawer-switcher").querySelectorAll(".switch-chip").forEach(btn => {
    btn.addEventListener("click", () => { state.drawerFindingId = btn.getAttribute("data-sw-fid"); renderDrawer(); });
  });

  const inv = f.investigation || {};
  const steps = inv.steps || [];
  const files = inv.suspect_files || [];
  const checkedMap = state.checkedSteps[f.id] || {};
  const formatStepHtml = txt => esc(txt).replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

  const stepsHtml = steps.map((st, idx) => {
    const done = !!checkedMap[idx];
    return '<button type="button" class="step-check-btn" role="checkbox" aria-checked="' + done + '" data-step-idx="' + idx + '">' +
      '<span class="step-check-box" aria-hidden="true">' +
      '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path class="check-path" d="M3 8.5L6.5 12L13 4.5" /></svg></span>' +
      '<span><strong>第 ' + (idx + 1) + ' 步：</strong>' + formatStepHtml(st) + '</span></button>';
  }).join("");

  const filesHtml = files.length
    ? files.map(fp => '<button type="button" class="btn-ghost mono" data-copy-file="' + esc(fp) + '" title="点击复制文件路径">' + esc(fp) + '</button>').join("")
    : '<span style="font-size:12px;color:var(--ui-text-faint);">暂无关联代码路径</span>';

  document.getElementById("drawer-body").innerHTML =
    '<div><div class="brief-badges" style="margin-bottom:6px;"><span class="sev-badge ' + esc(f.severity) + '">' + esc(f.severity) + '</span>' +
    '<span class="pill slate">' + esc(f.tag) + '</span></div>' +
    '<h3 class="brief-title" style="margin-bottom:4px;">' + esc(f.title) + '</h3>' +
    '<p class="brief-summary">' + esc(f.fact) + '</p></div>' +

    '<div><h4 class="drawer-sec-title">建议先核查的 3 个步骤（点击可标记进度）</h4><div class="step-checklist">' + stepsHtml + '</div></div>' +

    '<div><h4 class="drawer-sec-title">怀疑的代码 / 配置入口（点击复制路径）</h4><div class="files-wrap">' + filesHtml + '</div>' +
    (inv.log_hints ? '<p class="brief-summary" style="margin-top:8px;"><strong>日志过滤提示：</strong>' + esc(inv.log_hints) + '</p>' : '') + '</div>' +

    '<div><h4 class="drawer-sec-title">可带走的 AI 排查上下文包</h4><pre class="prompt-box">' + esc(inv.ai_prompt || "") + '</pre></div>';

  document.getElementById("drawer-cli-hint").textContent =
    "终端导包：python3 radar/scripts/build_radar.py --input radar/examples/demo-radar.json --export-prompt " + f.id;

  document.getElementById("drawer-body").querySelectorAll(".step-check-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.getAttribute("data-step-idx"));
      state.checkedSteps[f.id] = state.checkedSteps[f.id] || {};
      state.checkedSteps[f.id][idx] = !state.checkedSteps[f.id][idx];
      btn.setAttribute("aria-checked", String(state.checkedSteps[f.id][idx]));
    });
  });

  document.getElementById("drawer-body").querySelectorAll("[data-copy-file]").forEach(btn => {
    btn.addEventListener("click", () => {
      copyTextSafe(btn.getAttribute("data-copy-file"), "已复制路径：" + btn.getAttribute("data-copy-file"));
    });
  });
}

function openDrawer(findingId, triggerEl) {
  const findings = RADAR_DATA.findings || [];
  state.drawerFindingId = findingId || state.selectedFindingId || (findings[0] && findings[0].id);
  state.lastFocusEl = triggerEl || document.activeElement;
  state.drawerOpen = true;
  renderDrawer();
  document.getElementById("drawer-backdrop").setAttribute("data-open", "true");
  document.getElementById("drawer-backdrop").setAttribute("aria-hidden", "false");
  document.getElementById("ai-drawer").setAttribute("data-open", "true");
  document.getElementById("drawer-close").focus();
}

function closeDrawer() {
  if (!state.drawerOpen) return;
  state.drawerOpen = false;
  document.getElementById("drawer-backdrop").setAttribute("data-open", "false");
  document.getElementById("drawer-backdrop").setAttribute("aria-hidden", "true");
  document.getElementById("ai-drawer").setAttribute("data-open", "false");
  if (state.lastFocusEl && typeof state.lastFocusEl.focus === "function") {
    state.lastFocusEl.focus();
  }
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll("#mode-switch .seg-btn").forEach(b => {
    b.setAttribute("aria-pressed", String(b.getAttribute("data-mode") === mode));
  });
  syncSegIndicator(document.getElementById("mode-switch"));
  if (state.activeTab === "flow") {
    renderFlow(true);
    renderDrilldown();
    renderSimulator();
  }
}

(function init() {
  document.getElementById("app-title").textContent = RADAR_DATA.product_name + " · 团队雷达";
  document.getElementById("app-window").textContent = RADAR_DATA.window;
  const meta = RADAR_DATA.meta || {};
  document.getElementById("foot-note").textContent = meta.demo_note || "示例数据（Demo）";
  document.getElementById("foot-updated").textContent = "更新日期：" + RADAR_DATA.updated;

  updateThemeButton();
  document.getElementById("theme-toggle").addEventListener("click", () => {
    state.theme = state.theme === "light" ? "dark" : "light";
    updateThemeButton();
    renderMiniTimeline();
    if (state.activeTab === "flow") {
      renderFlow(false);
      renderSimulator();
    }
    if (state.activeTab === "changes") renderTimeline(false);
  });

  document.querySelectorAll("#main-tabs .seg-btn").forEach(b => {
    b.addEventListener("click", () => switchTab(b.getAttribute("data-tab")));
  });
  document.querySelectorAll("[data-goto-tab]").forEach(b => {
    b.addEventListener("click", () => switchTab(b.getAttribute("data-goto-tab")));
  });

  document.getElementById("open-ai-top").addEventListener("click", e => {
    openDrawer(state.selectedFindingId, e.currentTarget);
  });
  document.getElementById("delivery-ai-btn").addEventListener("click", e => {
    openDrawer("f_eng_rework", e.currentTarget);
  });
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  document.getElementById("drawer-backdrop").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeDrawer(); });

  document.getElementById("copy-prompt-btn").addEventListener("click", () => {
    const f = (RADAR_DATA.findings || []).find(x => x.id === state.drawerFindingId);
    const txt = (f && f.investigation && f.investigation.ai_prompt) || "";
    copyTextSafe(txt, "已复制 AI 排查上下文包，可粘贴到 AI IDE / 终端继续追查");
  });

  document.querySelectorAll("#caliber-switch .seg-btn").forEach(b => {
    b.addEventListener("click", () => {
      state.caliber = b.getAttribute("data-caliber");
      document.querySelectorAll("#caliber-switch .seg-btn").forEach(x => {
        x.setAttribute("aria-pressed", String(x === b));
      });
      syncSegIndicator(document.getElementById("caliber-switch"));
      renderFlow(true);
      renderSimulator();
    });
  });

  document.querySelectorAll("#mode-switch .seg-btn").forEach(b => {
    b.addEventListener("click", () => setMode(b.getAttribute("data-mode")));
  });

  renderBentoSignals();
  renderOverviewFindings();
  renderMiniTimeline();
  renderOverviewSinks();
  renderChangeFilters();
  renderTimeline(false);
  renderDelivery();
  renderFlow(false);
  renderDrilldown();
  renderSimulator();

  requestAnimationFrame(() => {
    syncAllSegIndicators();
    updateFlowScale();
  });

  if (typeof ResizeObserver !== "undefined") {
    const ro = new ResizeObserver(() => {
      updateFlowScale();
      syncAllSegIndicators();
    });
    ro.observe(document.getElementById("flow-stage"));
  }
  window.addEventListener("resize", () => {
    updateFlowScale();
    syncAllSegIndicators();
  });
})();
</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Team Radar 单文件交互原型 HTML 与实际 design tokens")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="输入标准快照 JSON 路径")
    parser.add_argument("--context-dir", default="", help="可选：Team Context 数据目录路径，用于补充负责人与历史避坑背景")
    parser.add_argument("--out", default="dist/radar-demo.html", help="输出 HTML 文件路径")
    parser.add_argument("--tokens-out", default="dist/tokens.json", help="输出实际使用的 tokens.json 路径")
    parser.add_argument("--list-findings", action="store_true", help="列出自动提炼的所有问题 ID 与标题")
    parser.add_argument("--export-prompt", default="", help="按问题 ID 导出可直接喂给 AI 的排查上下文包")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.is_file():
        print(f"[错误] 输入数据文件不存在: {in_path}", file=sys.stderr)
        return 1

    ctx_dir = Path(args.context_dir) if args.context_dir else None
    ctx_bundle = _load_context_bundle(ctx_dir)

    data = json.loads(in_path.read_text(encoding="utf-8"))
    data["findings"] = derive_findings(data, ctx_bundle)

    if args.list_findings:
        for f in data["findings"]:
            print(f"{f['id']}\t[{f['severity']}]\t{f['title']}")
        return 0

    if args.export_prompt:
        match = next((f for f in data["findings"] if f["id"] == args.export_prompt), None)
        if not match:
            print(f"[错误] 未找到 ID 为 {args.export_prompt} 的问题", file=sys.stderr)
            return 2
        print(match["investigation"]["ai_prompt"])
        return 0

    safe_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page_html = (
        HTML_TEMPLATE.replace("__COLOR_VARS__", build_root_color_vars(DESIGN_TOKENS))
        .replace("__TITLE__", html.escape(data.get("product_name", "Team Radar")))
        .replace("__RADAR_DATA__", safe_json)
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page_html, encoding="utf-8")

    tokens_path = Path(args.tokens_out)
    tokens_path.parent.mkdir(parents=True, exist_ok=True)
    tokens_path.write_text(json.dumps(DESIGN_TOKENS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"已生成 Team Radar 原型: {out_path.resolve()}")
    print(f"已导出实际 tokens: {tokens_path.resolve()}")
    print(f"  - 提炼重点问题: {len(data['findings'])} 条（P0/P1/P2）")
    print(f"  - 链路节点: {len(data['flow']['nodes'])} 个，连线: {len(data['flow']['edges'])} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
