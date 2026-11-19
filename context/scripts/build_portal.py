#!/usr/bin/env python3
"""将团队 data/ 目录编译为单文件自包含、可交互的 HTML 团队工作台（零外部 CDN），并支持导出静态 Markdown 文档兜底。"""

import argparse
import datetime
import html
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tc_common as C

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__TITLE__ · Team Context 团队工作台</title>
<style>
  :root {
    --bg: #f6f7f9;
    --card: #ffffff;
    --border: #e5e7eb;
    --text: #111827;
    --muted: #6b7280;
    --accent: #2563eb;
    --accent-soft: #eff6ff;
    --warn: #d97706;
    --warn-bg: #fffbeb;
    --danger: #dc2626;
    --danger-bg: #fef2f2;
    --ok: #059669;
    --ok-bg: #ecfdf5;
    --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
  }
  header {
    position: sticky;
    top: 0;
    z-index: 20;
    background: rgba(255, 255, 255, 0.94);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--border);
    padding: 12px 24px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 14px;
    justify-content: space-between;
  }
  .brand { display: flex; align-items: center; gap: 10px; }
  .brand h1 { font-size: 18px; margin: 0; font-weight: 700; }
  .badge {
    font-size: 12px;
    padding: 2px 9px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--muted);
  }
  .badge.warn { background: var(--warn-bg); color: var(--warn); border-color: #fde68a; }
  .badge.ok { background: var(--ok-bg); color: var(--ok); border-color: #a7f3d0; }
  .search-box {
    flex: 1;
    max-width: 380px;
    min-width: 220px;
    position: relative;
  }
  .search-box input {
    width: 100%;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid var(--border);
    font-size: 14px;
    outline: none;
    background: #fff;
  }
  .search-box input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12); }
  .tabs {
    background: #fff;
    border-bottom: 1px solid var(--border);
    padding: 0 24px;
    display: flex;
    gap: 6px;
    overflow-x: auto;
  }
  .tab-btn {
    border: none;
    background: transparent;
    padding: 12px 14px;
    font-size: 14px;
    font-weight: 500;
    color: var(--muted);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    white-space: nowrap;
  }
  .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
  main { max-width: 1280px; margin: 20px auto; padding: 0 24px 48px; }
  .panel { display: none; }
  .panel.active { display: block; }
  .section-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    flex-wrap: wrap;
    gap: 10px;
  }
  .section-head h2 { margin: 0; font-size: 17px; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
    gap: 14px;
    margin-bottom: 24px;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 15px 16px;
    box-shadow: 0 1px 2px rgba(17, 24, 39, 0.04);
  }
  .card-title { font-weight: 600; font-size: 15px; margin: 0 0 6px; display: flex; justify-content: space-between; align-items: center; gap: 8px; }
  .card-desc { font-size: 13px; color: var(--muted); margin: 0 0 10px; }
  .cmd-line {
    background: #f3f4f6;
    border-radius: 6px;
    padding: 6px 8px;
    font-family: var(--mono);
    font-size: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    overflow-x: auto;
  }
  .btn {
    border: 1px solid var(--border);
    background: #fff;
    color: var(--text);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .btn.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
  .btn:hover { opacity: 0.9; }
  .cat-title { font-size: 14px; color: var(--muted); margin: 18px 0 8px; font-weight: 600; }
  .graph-wrap {
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 16px;
    align-items: stretch;
  }
  @media (max-width: 960px) { .graph-wrap { grid-template-columns: 1fr; } }
  .graph-stage {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 10px;
    position: relative;
    height: 580px;
    overflow: hidden;
  }
  .graph-toolbar {
    position: absolute;
    top: 10px;
    left: 10px;
    right: 10px;
    z-index: 5;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    pointer-events: none;
  }
  .graph-toolbar > * { pointer-events: auto; }
  .graph-toolbar select, .graph-toolbar button {
    border: 1px solid var(--border);
    background: rgba(255,255,255,0.95);
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
    cursor: pointer;
  }
  #graph-svg { width: 100%; height: 100%; cursor: grab; user-select: none; }
  #graph-svg:active { cursor: grabbing; }
  .graph-detail {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    overflow-y: auto;
    max-height: 580px;
  }
  .md-doc {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 18px;
  }
  .md-doc h2, .md-doc h3 { margin-top: 18px; margin-bottom: 8px; }
  .md-doc table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
  .md-doc th, .md-doc td { border: 1px solid var(--border); padding: 7px 10px; text-align: left; }
  .md-doc th { background: #f9fafb; }
  .md-doc pre { background: #111827; color: #f9fafb; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 12px; }
  .md-doc code { font-family: var(--mono); background: #f3f4f6; padding: 1px 4px; border-radius: 4px; font-size: 0.9em; }
  .md-doc pre code { background: transparent; padding: 0; color: inherit; }
  .md-doc blockquote { margin: 10px 0; padding: 8px 12px; border-left: 3px solid var(--accent); background: var(--accent-soft); border-radius: 4px; font-size: 13px; }
  .banner-warn { background: var(--warn-bg); border: 1px solid #fde68a; color: #92400e; padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 14px; }
  .banner-danger { background: var(--danger-bg); border: 1px solid #fecaca; color: #991b1b; padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 14px; }
  .tag { display: inline-block; font-size: 11px; padding: 1px 7px; border-radius: 999px; background: #eef2ff; color: #3730a3; margin-right: 4px; }
  .search-hit { border-color: var(--accent) !important; box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2); }
</style>
</head>
<body>
<header>
  <div class="brand">
    <h1 id="team-title">Team Context</h1>
    <span class="badge" id="meta-date"></span>
    <span class="badge ok" id="freshness-badge"></span>
  </div>
  <div class="search-box">
    <input id="global-search" type="search" placeholder="搜索平台、模块、指标、踩坑或负责人..." />
  </div>
</header>
<nav class="tabs" id="tab-bar">
  <button class="tab-btn active" data-tab="platforms">平台与环境</button>
  <button class="tab-btn" data-tab="graph">代码关系图</button>
  <button class="tab-btn" data-tab="business">业务与指标</button>
  <button class="tab-btn" data-tab="standards">代码红线</button>
  <button class="tab-btn" data-tab="pitfalls">避坑与决定</button>
  <button class="tab-btn" data-tab="owners">找人地图</button>
</nav>
<main>
  <div id="search-results-bar" style="display:none;" class="banner-warn"></div>

  <section id="panel-platforms" class="panel active"></section>
  <section id="panel-graph" class="panel">
    <div class="section-head">
      <h2>代码关系图（拖拽节点可调整位置，点击节点查看上下游与跳转入口）</h2>
      <span class="badge" id="graph-stats"></span>
    </div>
    <div class="graph-wrap">
      <div class="graph-stage">
        <div class="graph-toolbar">
          <select id="graph-group-filter"><option value="">全部分组</option></select>
          <button id="graph-reset-btn" type="button">重置视图</button>
        </div>
        <svg id="graph-svg" viewBox="0 0 900 580"></svg>
      </div>
      <div class="graph-detail" id="graph-detail">
        <p style="color:var(--muted);font-size:13px;">点击左侧任意模块节点，查看热改次数、主维护人、上下游依赖和代码仓库跳转地址。</p>
      </div>
    </div>
  </section>
  <section id="panel-business" class="panel"></section>
  <section id="panel-standards" class="panel"></section>
  <section id="panel-pitfalls" class="panel"></section>
  <section id="panel-owners" class="panel"></section>
</main>
<script>
const PORTAL_DATA = __PORTAL_DATA__;

function esc(s) {
  return String(s || "").replace(/[&<>"]/g, function(c) {
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}[c];
  });
}

function renderInline(text) {
  let out = esc(text);
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  out = out.replace(/\\*\\*([^*]+)\\*\\*/g, "<strong>$1</strong>");
  out = out.replace(/\\[([^\\]]+)\\]\\((https?:\\/\\/[^)]+)\\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return out;
}

function mdToHtml(md) {
  const lines = String(md || "").split(/\\r?\\n/);
  let html = [];
  let inCode = false, codeLines = [];
  let inList = false;
  let tableRows = [];

  function flushList() {
    if (inList) { html.push("</ul>"); inList = false; }
  }
  function flushTable() {
    if (!tableRows.length) return;
    let ths = tableRows[0];
    let bodyRows = tableRows.slice(1);
    if (bodyRows.length && bodyRows[0].every(c => /^[:\\-\\s]+$/.test(c))) {
      bodyRows = bodyRows.slice(1);
    }
    let t = "<table><thead><tr>" + ths.map(c => "<th>" + renderInline(c) + "</th>").join("") + "</tr></thead><tbody>";
    bodyRows.forEach(r => {
      t += "<tr>" + r.map(c => "<td>" + renderInline(c) + "</td>").join("") + "</tr>";
    });
    t += "</tbody></table>";
    html.push(t);
    tableRows = [];
  }

  for (let raw of lines) {
    if (raw.trim().startsWith("```")) {
      flushList(); flushTable();
      if (!inCode) { inCode = true; codeLines = []; }
      else { html.push("<pre><code>" + esc(codeLines.join("\\n")) + "</code></pre>"); inCode = false; }
      continue;
    }
    if (inCode) { codeLines.push(raw); continue; }
    let line = raw.trim();
    if (!line) { flushList(); flushTable(); continue; }
    if (line.startsWith("|") && line.endsWith("|")) {
      flushList();
      let cells = line.slice(1, -1).split("|").map(s => s.trim());
      tableRows.push(cells);
      continue;
    } else {
      flushTable();
    }
    let hm = line.match(/^(#{1,4})\\s+(.*)$/);
    if (hm) {
      flushList();
      let lvl = Math.min(4, hm[1].length + 1);
      html.push("<h" + lvl + ">" + renderInline(hm[2]) + "</h" + lvl + ">");
      continue;
    }
    if (line.startsWith(">")) {
      flushList();
      html.push("<blockquote>" + renderInline(line.slice(1).trim()) + "</blockquote>");
      continue;
    }
    if (/^[-*]\\s+/.test(line) || /^\\d+\\.\\s+/.test(line)) {
      if (!inList) { html.push("<ul>"); inList = true; }
      html.push("<li>" + renderInline(line.replace(/^([-*]|\\d+\\.)\\s+/, "")) + "</li>");
      continue;
    }
    flushList();
    html.push("<p>" + renderInline(line) + "</p>");
  }
  flushList(); flushTable();
  if (inCode) html.push("<pre><code>" + esc(codeLines.join("\\n")) + "</code></pre>");
  return html.join("\\n");
}

function copyText(text, btn) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      let old = btn.textContent; btn.textContent = "已复制";
      setTimeout(() => btn.textContent = old, 1200);
    });
  } else {
    let ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    document.execCommand("copy"); document.body.removeChild(ta);
    let old = btn.textContent; btn.textContent = "已复制";
    setTimeout(() => btn.textContent = old, 1200);
  }
}

function renderPlatforms() {
  const wrap = document.getElementById("panel-platforms");
  const p = PORTAL_DATA.platforms || {};
  const items = p.items || [];
  let groups = {};
  items.forEach(it => {
    let cat = it.category || "常用入口";
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(it);
  });
  let out = '<div class="section-head"><h2>研发环境与平台入口（一站直达）</h2></div>';
  if (!items.length) {
    wrap.innerHTML = out + '<div class="card">暂无平台配置，请在 data/platforms.json 中添加。</div>';
    return;
  }
  Object.keys(groups).forEach(cat => {
    out += '<div class="cat-title">' + esc(cat) + '</div><div class="grid">';
    groups[cat].forEach(it => {
      out += '<div class="card searchable" data-search="' + esc((it.name + " " + it.desc + " " + (it.command || "") + " " + cat).toLowerCase()) + '">';
      out += '<div class="card-title"><span>' + esc(it.name) + '</span>';
      if (it.url) out += '<a class="btn primary" href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">打开</a>';
      out += '</div>';
      if (it.desc) out += '<p class="card-desc">' + esc(it.desc) + '</p>';
      if (it.command) {
        out += '<div class="cmd-line"><code>' + esc(it.command) + '</code><button class="btn copy-cmd" data-cmd="' + esc(it.command) + '">复制</button></div>';
      }
      if (it.owner) out += '<p class="card-desc" style="margin-top:8px;margin-bottom:0;">接口人：' + esc(it.owner) + '</p>';
      out += '</div>';
    });
    out += '</div>';
  });
  wrap.innerHTML = out;
  wrap.querySelectorAll(".copy-cmd").forEach(btn => {
    btn.addEventListener("click", () => copyText(btn.getAttribute("data-cmd"), btn));
  });
}

function renderDocPanel(panelId, items, extraBanner) {
  const wrap = document.getElementById(panelId);
  let out = extraBanner || "";
  items.forEach(doc => {
    let cls = doc.freshness && doc.freshness.status === "expired" ? "banner-warn" : "";
    let freshHtml = "";
    if (doc.freshness && (doc.freshness.status === "expired" || doc.freshness.status === "expiring")) {
      freshHtml = '<div class="banner-warn">保鲜提醒：' + esc(doc.file) + ' 上次核对时间为 ' + esc(doc.updated) + '（已过 ' + doc.freshness.age_days + ' 天），顺手改代码时记得检查一眼。</div>';
    }
    out += freshHtml + '<div class="md-doc searchable" data-search="' + esc(doc.raw.toLowerCase()) + '">' + mdToHtml(doc.body) + '</div>';
  });
  wrap.innerHTML = out;
}

function initGraph() {
  const g = PORTAL_DATA.code_graph || {nodes: [], edges: []};
  const nodes = (g.nodes || []).map((n, i) => Object.assign({}, n, { idx: i }));
  const edges = g.edges || [];
  document.getElementById("graph-stats").textContent = nodes.length + " 个模块 · " + edges.length + " 条依赖";

  const svg = document.getElementById("graph-svg");
  const filterSel = document.getElementById("graph-group-filter");
  const groups = Array.from(new Set(nodes.map(n => n.group || "未分组")));
  const palette = ["#2563eb","#059669","#7c3aed","#d97706","#db2777","#0891b2"];
  let groupColor = {};
  groups.forEach((gr, idx) => {
    groupColor[gr] = palette[idx % palette.length];
    let opt = document.createElement("option");
    opt.value = gr; opt.textContent = gr;
    filterSel.appendChild(opt);
  });

  // 环形分组初始布局
  const cx = 450, cy = 290;
  nodes.forEach((n, i) => {
    let angle = (2 * Math.PI * i) / Math.max(1, nodes.length);
    let r = 175 + ((i % 2) * 45);
    n.x = cx + r * Math.cos(angle);
    n.y = cy + r * Math.sin(angle);
  });

  let selectedId = null;
  let scale = 1, panX = 0, panY = 0;

  function draw() {
    const activeGroup = filterSel.value;
    const nodeMap = {};
    nodes.forEach(n => nodeMap[n.id] = n);

    let related = new Set();
    if (selectedId) {
      related.add(selectedId);
      edges.forEach(e => {
        if (e.source === selectedId) related.add(e.target);
        if (e.target === selectedId) related.add(e.source);
      });
    }

    let svgHtml = '<g id="viewport" transform="translate(' + panX + ',' + panY + ') scale(' + scale + ')">';
    svgHtml += '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="18" refY="4" orient="auto"><path d="M0,1 L7,4 L0,7 Z" fill="#9ca3af"/></marker></defs>';

    edges.forEach(e => {
      let a = nodeMap[e.source], b = nodeMap[e.target];
      if (!a || !b) return;
      if (activeGroup && a.group !== activeGroup && b.group !== activeGroup) return;
      let hit = selectedId && (e.source === selectedId || e.target === selectedId);
      let stroke = hit ? "#2563eb" : "#cbd5e1";
      let opacity = selectedId ? (hit ? 1 : 0.18) : 0.85;
      svgHtml += '<line x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y + '" stroke="' + stroke + '" stroke-width="' + (hit ? 2.2 : 1.3) + '" stroke-opacity="' + opacity + '" marker-end="url(#arrow)" />';
    });

    nodes.forEach(n => {
      if (activeGroup && n.group !== activeGroup) return;
      let dimmed = selectedId && !related.has(n.id);
      let color = groupColor[n.group || "未分组"] || "#2563eb";
      let radius = Math.min(26, 13 + Math.sqrt(n.hot_changes || 1) * 1.5);
      let op = dimmed ? 0.25 : 1;
      let stroke = n.id === selectedId ? "#111827" : "#ffffff";
      svgHtml += '<g class="g-node" data-id="' + esc(n.id) + '" style="cursor:pointer;opacity:' + op + '">';
      svgHtml += '<circle cx="' + n.x + '" cy="' + n.y + '" r="' + radius + '" fill="' + color + '" stroke="' + stroke + '" stroke-width="2.5"></circle>';
      svgHtml += '<text x="' + n.x + '" y="' + (n.y + radius + 14) + '" text-anchor="middle" font-size="12" font-weight="600" fill="#1f2937">' + esc(n.label) + '</text>';
      svgHtml += '</g>';
    });
    svgHtml += '</g>';
    svg.innerHTML = svgHtml;

    svg.querySelectorAll(".g-node").forEach(el => {
      let id = el.getAttribute("data-id");
      let dragging = false, moved = false, startX = 0, startY = 0;
      el.addEventListener("mousedown", ev => {
        ev.stopPropagation();
        dragging = true; moved = false;
        startX = ev.clientX; startY = ev.clientY;
        const onMove = mv => {
          if (!dragging) return;
          let dx = (mv.clientX - startX) / scale;
          let dy = (mv.clientY - startY) / scale;
          if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
          startX = mv.clientX; startY = mv.clientY;
          let node = nodeMap[id];
          if (node) { node.x += dx; node.y += dy; draw(); }
        };
        const onUp = () => {
          dragging = false;
          window.removeEventListener("mousemove", onMove);
          window.removeEventListener("mouseup", onUp);
          if (!moved) selectNode(id);
        };
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
      });
    });
  }

  function selectNode(id) {
    selectedId = id;
    draw();
    const n = nodes.find(x => x.id === id);
    if (!n) return;
    const outs = edges.filter(e => e.source === id).map(e => e.target + (e.label ? " (" + e.label + ")" : ""));
    const ins = edges.filter(e => e.target === id).map(e => e.source + (e.label ? " (" + e.label + ")" : ""));
    let html = '<h3 style="margin-top:0;">' + esc(n.label) + '</h3>';
    html += '<p><span class="tag">' + esc(n.group || "模块") + '</span><span class="tag">近周期修改 ' + (n.hot_changes || 0) + ' 次</span></p>';
    html += '<p style="font-size:13px;">' + esc(n.summary || "暂无模块说明") + '</p>';
    html += '<p style="font-size:13px;"><strong>主维护人：</strong>' + esc((n.owners || []).join("、") || "待认领") + '</p>';
    if (n.local_path) html += '<p style="font-size:13px;"><strong>仓库目录：</strong><code>' + esc(n.local_path) + '</code></p>';
    if (n.url) html += '<p><a class="btn primary" href="' + esc(n.url) + '" target="_blank" rel="noopener noreferrer">打开代码仓库对应目录</a></p>';
    html += '<h4 style="margin-bottom:4px;">它调用 / 依赖谁</h4><p style="font-size:12px;color:var(--muted);">' + (outs.length ? outs.map(esc).join("<br/>") : "无记录") + '</p>';
    html += '<h4 style="margin-bottom:4px;">谁依赖它</h4><p style="font-size:12px;color:var(--muted);">' + (ins.length ? ins.map(esc).join("<br/>") : "无记录") + '</p>';
    document.getElementById("graph-detail").innerHTML = html;
  }

  svg.addEventListener("wheel", ev => {
    ev.preventDefault();
    let delta = ev.deltaY < 0 ? 1.1 : 0.9;
    scale = Math.max(0.45, Math.min(2.4, scale * delta));
    draw();
  }, { passive: false });

  svg.addEventListener("mousedown", ev => {
    let sx = ev.clientX, sy = ev.clientY;
    const onMove = mv => {
      panX += mv.clientX - sx; panY += mv.clientY - sy;
      sx = mv.clientX; sy = mv.clientY;
      draw();
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  });

  filterSel.addEventListener("change", draw);
  document.getElementById("graph-reset-btn").addEventListener("click", () => {
    scale = 1; panX = 0; panY = 0; selectedId = null; filterSel.value = ""; draw();
  });
  draw();
}

function initTabsAndSearch() {
  const btns = document.querySelectorAll(".tab-btn");
  btns.forEach(btn => {
    btn.addEventListener("click", () => {
      btns.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("panel-" + btn.getAttribute("data-tab")).classList.add("active");
    });
  });

  const searchInput = document.getElementById("global-search");
  const resBar = document.getElementById("search-results-bar");
  searchInput.addEventListener("input", () => {
    let q = searchInput.value.trim().toLowerCase();
    let hits = 0;
    document.querySelectorAll(".searchable").forEach(el => {
      el.classList.remove("search-hit");
      if (!q) { el.style.display = ""; return; }
      let txt = el.getAttribute("data-search") || "";
      if (txt.includes(q)) { el.style.display = ""; el.classList.add("search-hit"); hits++; }
      else { el.style.display = "none"; }
    });
    if (q) {
      resBar.style.display = "block";
      resBar.textContent = "关键词「" + searchInput.value.trim() + "」在当前各模块共命中 " + hits + " 处（切换顶部标签查看对应页面高亮内容）。";
    } else {
      resBar.style.display = "none";
    }
  });
}

(function bootstrap() {
  document.getElementById("team-title").textContent = (PORTAL_DATA.team_name || "团队") + " · Team Context 工作台";
  document.getElementById("meta-date").textContent = "编译于 " + (PORTAL_DATA.generated_at || "");
  const badge = document.getElementById("freshness-badge");
  const staleCnt = PORTAL_DATA.stale_count || 0;
  if (staleCnt > 0) {
    badge.className = "badge warn";
    badge.textContent = staleCnt + " 份文档需顺手核对";
  } else {
    badge.className = "badge ok";
    badge.textContent = "全部资料保鲜中";
  }

  renderPlatforms();
  initGraph();
  renderDocPanel("panel-business", PORTAL_DATA.business_docs || []);
  renderDocPanel("panel-standards", PORTAL_DATA.standards_docs || [], '<div class="banner-danger"><strong>AI 写代码红线说明</strong>：以下规则通过 sync_ai_rules.py 同步至团队代码仓，所有人使用不同 AI 工具生成代码前须遵守。</div>');
  renderDocPanel("panel-pitfalls", PORTAL_DATA.pitfalls_docs || []);
  renderDocPanel("panel-owners", PORTAL_DATA.owners_docs || [], '<div class="banner-warn">找人地图仅记录模块分工与平台权限接口人，严禁记录对同事能力的任何主观评价。</div>');
  initTabsAndSearch();
})();
</script>
</body>
</html>
"""


def load_md_doc(data_dir: Path, filename: str) -> dict[str, object]:
    p = data_dir / filename
    if not p.is_file():
        return {"file": filename, "updated": "", "freshness": {"status": "unknown"}, "body": f"*暂无 `{filename}`*", "raw": ""}
    raw = p.read_text(encoding="utf-8")
    meta, body = C.parse_frontmatter(raw)
    fresh = C.check_freshness(meta.get("updated", ""), meta.get("review_cycle", ""))
    return {
        "file": filename,
        "updated": meta.get("updated", ""),
        "freshness": fresh,
        "body": body,
        "raw": raw,
    }


def export_markdown_handbook(data_dir: Path, out_md: Path, team_name: str, platforms: dict, graph: dict, docs: dict) -> None:
    """导出纯静态汇总 Markdown 文档作为兜底阅读方式。"""
    lines = [
        f"# {team_name} · 团队工作手册（静态兜底导出）",
        "",
        f"> 生成日期：{datetime.date.today().isoformat()}。交互版代码图与检索请打开 HTML 网站版。",
        "",
        "## 一、研发环境与平台入口",
        "",
        "| 类别 | 名称 | 常用命令 | 负责人 | 地址 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for it in platforms.get("items", []):
        cmd = f"`{it['command']}`" if it.get("command") else "—"
        url = it.get("url") or "—"
        lines.append(f"| {it.get('category', '')} | {it.get('name', '')} | {cmd} | {it.get('owner', '')} | {url} |")

    lines.extend(["", "## 二、核心代码模块清单", "", "| 模块 | 分组 | 热改次数 | 负责人 | 说明 |", "| --- | --- | --- | --- | --- |"])
    for n in graph.get("nodes", []):
        owners = "、".join(n.get("owners", [])) or "待标注"
        lines.append(f"| `{n.get('label', '')}` | {n.get('group', '')} | {n.get('hot_changes', 0)} | {owners} | {n.get('summary', '')} |")

    for title, key in [
        ("三、业务全景与流程", "business.md"),
        ("四、数据指标与评测", "metrics.md"),
        ("五、代码标准与 AI 红线", "standards.md"),
        ("六、避坑指南与历史决定", "pitfalls.md"),
        ("七、找人地图与分工", "owners.md"),
    ]:
        lines.extend(["", f"## {title}", "", str(docs[key]["body"]).strip()])

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="将 Team Context data/ 编译为可交互 HTML 团队网站")
    parser.add_argument("--data", default="data", help="团队数据目录（默认 data）")
    parser.add_argument("--out", default="dist/index.html", help="输出 HTML 路径（默认 dist/index.html）")
    parser.add_argument("--export-md", default="", help="可选：同时导出静态汇总 Markdown 文件路径")
    args = parser.parse_args()

    data_dir = Path(args.data)
    if not data_dir.is_dir():
        print(f"[错误] 数据目录不存在: {data_dir}", file=sys.stderr)
        return 1

    platforms = {"team_name": "团队", "items": []}
    p_file = data_dir / "platforms.json"
    if p_file.is_file():
        platforms = json.loads(p_file.read_text(encoding="utf-8"))

    graph = {"nodes": [], "edges": []}
    g_file = data_dir / "code-graph.json"
    if g_file.is_file():
        graph = json.loads(g_file.read_text(encoding="utf-8"))

    docs = {
        name: load_md_doc(data_dir, name)
        for name in ["business.md", "metrics.md", "standards.md", "pitfalls.md", "owners.md"]
    }
    stale_count = sum(
        1 for d in docs.values() if d["freshness"]["status"] in {"expired", "expiring"}  # type: ignore[index]
    )

    team_name = str(platforms.get("team_name") or "研发团队")
    payload = {
        "team_name": team_name,
        "generated_at": datetime.date.today().isoformat(),
        "stale_count": stale_count,
        "platforms": platforms,
        "code_graph": graph,
        "business_docs": [docs["business.md"], docs["metrics.md"]],
        "standards_docs": [docs["standards.md"]],
        "pitfalls_docs": [docs["pitfalls.md"]],
        "owners_docs": [docs["owners.md"]],
    }

    safe_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    page_html = HTML_TEMPLATE.replace("__TITLE__", html.escape(team_name)).replace("__PORTAL_DATA__", safe_json)

    out_file = Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(page_html, encoding="utf-8")
    print(f"已生成可交互 HTML 工作台: {out_file.resolve()}")

    if args.export_md:
        out_md = Path(args.export_md)
        export_markdown_handbook(data_dir, out_md, team_name, platforms, graph, docs)
        print(f"已同步导出静态汇总文档: {out_md.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
