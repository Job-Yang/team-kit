#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR="$(mktemp -d /tmp/team-context-test.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "=== 1. 测试 init_team.py 初始化空团队目录 ==="
python3 "$ROOT_DIR/scripts/init_team.py" --data "$TMP_DIR/data" --team-name "测试小组"
test -f "$TMP_DIR/data/platforms.json"
test -f "$TMP_DIR/data/code-graph.json"
test -f "$TMP_DIR/data/pitfalls.md"
test -d "$TMP_DIR/data/inbox/scan"
test -d "$TMP_DIR/data/history"

echo "=== 2. 构造临时多提交 Git 仓库并测试 scan_repo.py ==="
SAMPLE_REPO="$TMP_DIR/mock-repo"
mkdir -p "$SAMPLE_REPO/Sources/Chat" "$SAMPLE_REPO/Sources/Net" "$SAMPLE_REPO/BFF/Router"
git -C "$TMP_DIR" init "$SAMPLE_REPO" >/dev/null
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

python3 "$ROOT_DIR/scripts/scan_repo.py" \
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

echo "=== 3. 测试 build_portal.py（HTML 交互站 + 静态 MD 兜底 + JS 语法校验） ==="
python3 "$ROOT_DIR/scripts/build_portal.py" \
  --data "$ROOT_DIR/examples/sample-team" \
  --out "$TMP_DIR/portal.html" \
  --export-md "$TMP_DIR/handbook.md"

test -f "$TMP_DIR/portal.html"
test -f "$TMP_DIR/handbook.md"

python3 - "$TMP_DIR/portal.html" "$TMP_DIR/js_check.js" <<'PY'
import re, sys
html_txt = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"<script>(.*)</script>", html_txt, re.S)
assert m, "未找到内联 script"
open(sys.argv[2], "w", encoding="utf-8").write(m.group(1))
PY

if command -v node >/dev/null 2>&1; then
  node --check "$TMP_DIR/js_check.js"
  echo "JS 语法校验通过 (node --check)"
fi

echo "=== 4. 测试 sync_ai_rules.py（三种规则格式 + 按任务上下文抽取） ==="
python3 "$ROOT_DIR/scripts/sync_ai_rules.py" --data "$ROOT_DIR/examples/sample-team" --mode rules --format agents --target "$TMP_DIR/AGENTS.md"
python3 "$ROOT_DIR/scripts/sync_ai_rules.py" --data "$ROOT_DIR/examples/sample-team" --mode rules --format claude --target "$TMP_DIR/CLAUDE.md"
python3 "$ROOT_DIR/scripts/sync_ai_rules.py" --data "$ROOT_DIR/examples/sample-team" --mode rules --format cursor --target "$TMP_DIR/.cursor/rules/team.mdc"
python3 "$ROOT_DIR/scripts/sync_ai_rules.py" --data "$ROOT_DIR/examples/sample-team" --mode context --task debug --target "$TMP_DIR/debug-context.md"

grep -q "BFF/ComplianceFilter" "$TMP_DIR/AGENTS.md"
grep -q "alwaysApply: true" "$TMP_DIR/.cursor/rules/team.mdc"
grep -q "trace.example.com/star-bff" "$TMP_DIR/debug-context.md"

echo "=== 5. 测试 check_safety.py 正反用例（正常=0 / 过期=2 / 泄密或主观评价=3） ==="
python3 "$ROOT_DIR/scripts/check_safety.py" --data "$ROOT_DIR/examples/sample-team" --no-remote-check

cp -R "$ROOT_DIR/examples/sample-team" "$TMP_DIR/bad-secret"
echo "OPENAI_KEY = sk-testAbCdEfGhIjKlMnOpQrStUvWxYz" >> "$TMP_DIR/bad-secret/pitfalls.md"
set +e
python3 "$ROOT_DIR/scripts/check_safety.py" --data "$TMP_DIR/bad-secret" --no-remote-check
RC_SECRET=$?
set -e
test "$RC_SECRET" -eq 3

cp -R "$ROOT_DIR/examples/sample-team" "$TMP_DIR/bad-owner"
echo "| 测试 | 模块 | 张三（不靠谱） | 李四 |" >> "$TMP_DIR/bad-owner/owners.md"
set +e
python3 "$ROOT_DIR/scripts/check_safety.py" --data "$TMP_DIR/bad-owner" --no-remote-check
RC_OWNER=$?
set -e
test "$RC_OWNER" -eq 3

cp -R "$ROOT_DIR/examples/sample-team" "$TMP_DIR/stale-data"
python3 - "$TMP_DIR/stale-data/pitfalls.md" <<'PY'
import sys
p = sys.argv[1]
txt = open(p, encoding="utf-8").read().replace("2026-11-19", "2020-01-01")
open(p, "w", encoding="utf-8").write(txt)
PY
set +e
python3 "$ROOT_DIR/scripts/check_safety.py" --data "$TMP_DIR/stale-data" --no-remote-check
RC_STALE=$?
set -e
test "$RC_STALE" -eq 2

echo "✅ 所有自动化自测通过！"
