#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR="$(mktemp -d /tmp/team-kit-test.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "=== 1. 测试 Team Context：init_team.py 初始化空团队目录 ==="
python3 "$ROOT_DIR/context/scripts/init_team.py" --data "$TMP_DIR/data" --team-name "测试小组"
test -f "$TMP_DIR/data/platforms.json"
test -f "$TMP_DIR/data/code-graph.json"
test -f "$TMP_DIR/data/pitfalls.md"
test -d "$TMP_DIR/data/inbox/scan"
test -d "$TMP_DIR/data/history"

echo "=== 2. 测试 Team Context：构造多提交 Git 仓并运行 scan_repo.py ==="
SAMPLE_REPO="$TMP_DIR/mock-repo"
mkdir -p "$SAMPLE_REPO/Sources/Chat" "$SAMPLE_REPO/Sources/Net" "$SAMPLE_REPO/BFF/Router"
git init "$SAMPLE_REPO" >/dev/null
git -C "$SAMPLE_REPO" config user.name "Alice"
git -C "$SAMPLE_REPO" config user.email "alice@example.com"

cat > "$SAMPLE_REPO/Sources/Net/Client.swift" <<'EOF'
import Foundation
struct NetClient {}
EOF
cat > "$SAMPLE_REPO/Sources/Chat/ChatVC.swift" <<'EOF'
import Net
struct ChatVC {}
EOF
cat > "$SAMPLE_REPO/BFF/Router/chat.ts" <<'EOF'
import { Net } from "../Net"
export const route = "/chat";
EOF
git -C "$SAMPLE_REPO" add .
git -C "$SAMPLE_REPO" commit -m "feat: initial modules" >/dev/null

git -C "$SAMPLE_REPO" config user.name "Bob"
git -C "$SAMPLE_REPO" config user.email "bob@example.com"
echo "// update" >> "$SAMPLE_REPO/Sources/Chat/ChatVC.swift"
echo "// update" >> "$SAMPLE_REPO/Sources/Net/Client.swift"
git -C "$SAMPLE_REPO" add .
git -C "$SAMPLE_REPO" commit -m "fix: chat streaming crash" >/dev/null

python3 "$ROOT_DIR/context/scripts/scan_repo.py" \
  --repo "$SAMPLE_REPO" \
  --out "$TMP_DIR/data/inbox/scan" \
  --repo-web-url "https://git.example.com/mock/repo"

test -f "$TMP_DIR/data/inbox/scan/scan-summary.json"
test -f "$TMP_DIR/data/inbox/scan/code-graph.draft.json"
test -f "$TMP_DIR/data/inbox/scan/scan-report.md"

python3 - "$TMP_DIR/data/inbox/scan/scan-summary.json" "$TMP_DIR/data/inbox/scan/code-graph.draft.json" <<'PY'
import json, sys
summary = json.load(open(sys.argv[1], encoding="utf-8"))
graph = json.load(open(sys.argv[2], encoding="utf-8"))
assert summary["commit_count"] == 2, summary
assert len(summary["hot_files"]) >= 3, summary
assert len(summary["co_changes"]) >= 1, summary
assert len(summary["risk_commits"]) >= 1, summary
assert len(graph["nodes"]) >= 3, graph
assert len(graph["edges"]) >= 1, graph
PY

echo "=== 3. 测试 Team Context：build_portal.py（交互站 + 静态 MD + JS 语法校验） ==="
python3 "$ROOT_DIR/context/scripts/build_portal.py" \
  --data "$ROOT_DIR/context/examples/sample-team" \
  --out "$TMP_DIR/portal.html" \
  --export-md "$TMP_DIR/handbook.md"

test -f "$TMP_DIR/portal.html"
test -f "$TMP_DIR/handbook.md"

python3 - "$TMP_DIR/portal.html" "$TMP_DIR/portal_js_check.js" <<'PY'
import re, sys
html_txt = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"<script>(.*)</script>", html_txt, re.S)
assert m, "未找到 Context 内联 script"
open(sys.argv[2], "w", encoding="utf-8").write(m.group(1))
PY

if command -v node >/dev/null 2>&1; then
  node --check "$TMP_DIR/portal_js_check.js"
  echo "Team Context JS 语法校验通过 (node --check)"
fi

echo "=== 4. 测试 Team Context：sync_ai_rules.py（三种规则格式 + 按任务上下文抽取） ==="
python3 "$ROOT_DIR/context/scripts/sync_ai_rules.py" --data "$ROOT_DIR/context/examples/sample-team" --mode rules --format agents --target "$TMP_DIR/AGENTS.md"
python3 "$ROOT_DIR/context/scripts/sync_ai_rules.py" --data "$ROOT_DIR/context/examples/sample-team" --mode rules --format claude --target "$TMP_DIR/CLAUDE.md"
python3 "$ROOT_DIR/context/scripts/sync_ai_rules.py" --data "$ROOT_DIR/context/examples/sample-team" --mode rules --format cursor --target "$TMP_DIR/.cursor/rules/team.mdc"
python3 "$ROOT_DIR/context/scripts/sync_ai_rules.py" --data "$ROOT_DIR/context/examples/sample-team" --mode context --task debug --target "$TMP_DIR/debug-context.md"

grep -q "BFF/ComplianceFilter" "$TMP_DIR/AGENTS.md"
grep -q "alwaysApply: true" "$TMP_DIR/.cursor/rules/team.mdc"
grep -q "trace.example.com/star-bff" "$TMP_DIR/debug-context.md"

echo "=== 5. 测试 Team Context：check_safety.py 正反用例 ==="
python3 "$ROOT_DIR/context/scripts/check_safety.py" --data "$ROOT_DIR/context/examples/sample-team" --no-remote-check

cp -R "$ROOT_DIR/context/examples/sample-team" "$TMP_DIR/bad-secret"
echo "OPENAI_KEY = sk-testAbCdEfGhIjKlMnOpQrStUvWxYz" >> "$TMP_DIR/bad-secret/pitfalls.md"
set +e
python3 "$ROOT_DIR/context/scripts/check_safety.py" --data "$TMP_DIR/bad-secret" --no-remote-check
RC_SECRET=$?
set -e
test "$RC_SECRET" -eq 3

cp -R "$ROOT_DIR/context/examples/sample-team" "$TMP_DIR/bad-owner"
echo "| 测试 | 模块 | 张三（不靠谱） | 李四 |" >> "$TMP_DIR/bad-owner/owners.md"
set +e
python3 "$ROOT_DIR/context/scripts/check_safety.py" --data "$TMP_DIR/bad-owner" --no-remote-check
RC_OWNER=$?
set -e
test "$RC_OWNER" -eq 3

cp -R "$ROOT_DIR/context/examples/sample-team" "$TMP_DIR/stale-data"
python3 - "$TMP_DIR/stale-data/pitfalls.md" <<'PY'
import sys
p = sys.argv[1]
txt = open(p, encoding="utf-8").read().replace("2026-11-19", "2020-01-01")
open(p, "w", encoding="utf-8").write(txt)
PY
set +e
python3 "$ROOT_DIR/context/scripts/check_safety.py" --data "$TMP_DIR/stale-data" --no-remote-check
RC_STALE=$?
set -e
test "$RC_STALE" -eq 2

echo "=== 6. 测试 Team Radar：Demo 编译 + 导包 + Context 联动 + JS 与文案校验 ==="
python3 "$ROOT_DIR/radar/scripts/validate_snapshot.py" --input "$ROOT_DIR/radar/examples/demo-radar.json"
python3 "$ROOT_DIR/radar/scripts/build_radar.py" \
  --input "$ROOT_DIR/radar/examples/demo-radar.json" \
  --out "$TMP_DIR/radar.html" \
  --tokens-out "$TMP_DIR/tokens.json"

test -f "$TMP_DIR/radar.html"
test -f "$TMP_DIR/tokens.json"

FINDINGS_OUT="$(python3 "$ROOT_DIR/radar/scripts/build_radar.py" --input "$ROOT_DIR/radar/examples/demo-radar.json" --list-findings)"
test "$(printf "%s\n" "$FINDINGS_OUT" | wc -l | tr -d ' ')" -eq 4

PROMPT_PLAIN="$(python3 "$ROOT_DIR/radar/scripts/build_radar.py" --input "$ROOT_DIR/radar/examples/demo-radar.json" --export-prompt f_page_capture_tech)"
printf "%s" "$PROMPT_PLAIN" | grep -q "## 5. 请优先从这 3 步切入代码和日志排查"

mkdir -p "$TMP_DIR/ctx-match"
cp -R "$ROOT_DIR/context/examples/sample-team/." "$TMP_DIR/ctx-match/"
cat >> "$TMP_DIR/ctx-match/owners.md" <<'EOF'
| 拍照采集与端侧多媒体 | `Sources/Capture`、`Config/Remote` | 林深 | 陆远 |
EOF
PROMPT_CTX="$(python3 "$ROOT_DIR/radar/scripts/build_radar.py" --input "$ROOT_DIR/radar/examples/demo-radar.json" --context-dir "$TMP_DIR/ctx-match" --export-prompt f_page_capture_tech)"
printf "%s" "$PROMPT_CTX" | grep -q "## 6. 来自 Team Context 的补充背景"
printf "%s" "$PROMPT_CTX" | grep -q "Sources/Capture"

python3 - "$TMP_DIR/radar.html" "$ROOT_DIR/radar/examples/demo-radar.json" "$TMP_DIR/radar_js_check.js" <<'PY'
import json, re, sys

html_txt = open(sys.argv[1], encoding="utf-8").read()
demo_txt = open(sys.argv[2], encoding="utf-8").read()
m = re.search(r"<script>(.*)</script>", html_txt, re.S)
assert m, "未找到 Radar 内联 script"
open(sys.argv[3], "w", encoding="utf-8").write(m.group(1))

banned = ["\u5eb7\u5c0f\u52a9", "\u626b\u836f", "\u836f\u7bb1", "\u836f\u76d2", "\u95ee\u8bca", "\u5951\u7ea6", "\u63a2\u9488", "\u75c5\u7076", "\u95e8\u7981", "\u53cc\u9608\u503c", "\u9632\u566a\u97f3"]
for bad in banned:
    assert bad not in html_txt, f"Radar HTML 残留禁用词: {bad}"
    assert bad not in demo_txt, f"Demo JSON 残留禁用词: {bad}"
PY

if command -v node >/dev/null 2>&1; then
  node --check "$TMP_DIR/radar_js_check.js"
  echo "Team Radar JS 语法校验通过 (node --check)"
fi

echo "=== 7. 测试多仓 scan_repo、快照校验反例与 --snapshot 安全拦截 ==="
SECOND_REPO="$TMP_DIR/mock-bff"
mkdir -p "$SECOND_REPO/BFF/Order"
git init "$SECOND_REPO" >/dev/null
git -C "$SECOND_REPO" config user.name "Carol"
git -C "$SECOND_REPO" config user.email "carol@example.com"
cat > "$SECOND_REPO/BFF/Order/submit.ts" <<'EOF'
export const ok = true;
EOF
git -C "$SECOND_REPO" add .
git -C "$SECOND_REPO" commit -m "feat: bff submit" >/dev/null

python3 "$ROOT_DIR/context/scripts/scan_repo.py" \
  --repo "$SAMPLE_REPO" \
  --repo "$SECOND_REPO" \
  --repo-web-url "https://git.example.com/mock/app" \
  --repo-web-url "https://git.example.com/mock/bff" \
  --out "$TMP_DIR/multi-scan"
python3 - "$TMP_DIR/multi-scan/code-graph.draft.json" <<'PY'
import json, sys
g = json.load(open(sys.argv[1], encoding="utf-8"))
ids = [n["id"] for n in g["nodes"]]
assert any(x.startswith("mock-repo/") for x in ids), ids
assert any(x.startswith("mock-bff/") for x in ids), ids
PY

cat > "$TMP_DIR/bad-snapshot.json" <<'EOF'
{
  "product_name": "坏样例",
  "flow": {
    "nodes": [{"id": "n1", "title": "首页", "col": 0, "row": 0}],
    "edges": [{"from": "n1", "to": "missing_node"}]
  },
  "timeline": {"dates": ["11-01", "11-02"], "biz_conv": [50], "tech_p90_ms": [200]}
}
EOF
set +e
python3 "$ROOT_DIR/radar/scripts/validate_snapshot.py" --input "$TMP_DIR/bad-snapshot.json"
RC_BAD_SNAP=$?
set -e
test "$RC_BAD_SNAP" -eq 1

cp "$ROOT_DIR/radar/examples/demo-radar.json" "$TMP_DIR/leak-snap.json"
echo '{"secret":"sk-testAbCdEfGhIjKlMnOpQrStUvWxYz"}' >> "$TMP_DIR/leak-snap.json"
set +e
python3 "$ROOT_DIR/context/scripts/check_safety.py" --snapshot "$TMP_DIR/leak-snap.json" --no-remote-check
RC_LEAK_SNAP=$?
set -e
test "$RC_LEAK_SNAP" -eq 3

echo "=== 8. 测试 adapters（git_rework + csv_to_snapshot）、极端真实数据与 scripts/refresh.py ==="
cat > "$TMP_DIR/nodes.csv" <<'EOF'
id,title,stage,owner,col,row,uv,pv,conv_rate,conv_delta,stay_sec,p90_ms,crash_rate,backtrack_rate,ai_correct_rate
entry,入口页,入口,体验组,0,0,50000,72000,8.5,-1.2,4.1,180,0.01,1.0,0.0
step4,深层结果页,完结,业务组,4,2,12000,15000,92.0,-8.5,15.0,4600,0.90,26.0,16.0
EOF
cat > "$TMP_DIR/timeline.csv" <<'EOF'
date,biz_conv,tech_p90_ms,crash_rate
11-01,8.5,180,0.01
11-02,42.0,1950,0.22
11-03,92.0,4600,0.90
EOF

python3 "$ROOT_DIR/adapters/csv_to_snapshot.py" \
  --snapshot "$TMP_DIR/ext-snap.json" \
  --nodes-csv "$TMP_DIR/nodes.csv" \
  --timeline-csv "$TMP_DIR/timeline.csv" \
  --product-name "宽值域多列测试"

python3 "$ROOT_DIR/adapters/git_rework.py" \
  --snapshot "$TMP_DIR/ext-snap.json" \
  --repo "$SAMPLE_REPO" \
  --repo "$SECOND_REPO" \
  --days 7 \
  --top 5

python3 "$ROOT_DIR/radar/scripts/validate_snapshot.py" --input "$TMP_DIR/ext-snap.json"
python3 "$ROOT_DIR/radar/scripts/build_radar.py" \
  --input "$TMP_DIR/ext-snap.json" \
  --out "$TMP_DIR/ext-radar.html" \
  --tokens-out "$TMP_DIR/ext-tokens.json"

# 极简空模块快照（仅 product_name，无 flow/timeline/engineering）也必须正常编译
cat > "$TMP_DIR/minimal-snap.json" <<'EOF'
{
  "product_name": "最小空态测试",
  "window": "仅基础配置",
  "thresholds": {"crash_danger": 0.5}
}
EOF
python3 "$ROOT_DIR/radar/scripts/validate_snapshot.py" --input "$TMP_DIR/minimal-snap.json"
python3 "$ROOT_DIR/radar/scripts/build_radar.py" \
  --input "$TMP_DIR/minimal-snap.json" \
  --out "$TMP_DIR/minimal-radar.html" \
  --tokens-out "$TMP_DIR/minimal-tokens.json"

# 一键串联 refresh.py 端到端测试
mkdir -p "$TMP_DIR/ref-work/context-data" "$TMP_DIR/ref-work/out"
cp -R "$ROOT_DIR/context/examples/sample-team/." "$TMP_DIR/ref-work/context-data/"
cat > "$TMP_DIR/sources.test.json" <<EOF
{
  "team_name": "端到端联动测试团队",
  "context": {
    "enabled": true,
    "data_dir": "$TMP_DIR/ref-work/context-data",
    "repos": [{"path": "$SAMPLE_REPO", "web_url": "https://git.example.com/mock/app"}],
    "scan_days": 30,
    "out_html": "$TMP_DIR/ref-work/out/context.html",
    "out_md": "$TMP_DIR/ref-work/out/handbook.md"
  },
  "radar": {
    "enabled": true,
    "base_snapshot": "$ROOT_DIR/radar/examples/demo-radar.json",
    "merged_snapshot": "$TMP_DIR/ref-work/merged.json",
    "link_context": true,
    "adapters": [
      {"name": "git-rework", "script": "adapters/git_rework.py", "args": ["--repo", "$SAMPLE_REPO", "--days", "7"]},
      {"name": "csv", "script": "adapters/csv_to_snapshot.py", "args": ["--timeline-csv", "$TMP_DIR/timeline.csv"]}
    ],
    "out_html": "$TMP_DIR/ref-work/out/radar.html",
    "out_tokens": "$TMP_DIR/ref-work/out/tokens.json"
  }
}
EOF
python3 "$ROOT_DIR/scripts/refresh.py" --sources "$TMP_DIR/sources.test.json" --no-remote-check
test -f "$TMP_DIR/ref-work/out/context.html"
test -f "$TMP_DIR/ref-work/out/radar.html"

echo "✅ Team Kit 全模块自动化自测通过！"
