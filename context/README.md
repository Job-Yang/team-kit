# Team Context（`context/`）

把散落在平台、代码库和老员工脑子里的团队常识整理成轻量纯文本数据，一边生成给人用的可交互 HTML 团队工作台，另一边生成给 AI 用的按需背景与编码红线。

## 快速体验演示样例

```bash
python3 context/scripts/build_portal.py \
  --data context/examples/sample-team \
  --out dist/context-demo.html \
  --export-md dist/context-handbook.md
```

## 标准工作流（全部仅用 Python 3 标准库与原生 git）

1. 初始化数据目录：`python3 context/scripts/init_team.py --data context/data --team-name "<团队名>"`
2. 扫描业务代码仓：`python3 context/scripts/scan_repo.py --repo <仓库路径> --out context/data/inbox/scan`
3. 编译交互网页：`python3 context/scripts/build_portal.py --data context/data --out dist/context.html`
4. 同步代码红线：`python3 context/scripts/sync_ai_rules.py --data context/data --mode rules --format agents --target <业务仓>/AGENTS.md`
5. 提交前安全检查：`python3 context/scripts/check_safety.py --data context/data`

完整设计原理见 [../docs/team-context.md](../docs/team-context.md)。
