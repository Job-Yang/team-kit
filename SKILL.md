---
name: team-kit
description: 面向研发团队的零依赖通用工具集，包含 Team Context（团队工作台与 AI 红线）与 Team Radar（问题发现可视化雷达与 AI 排查交接）两个独立模块。用于新团队快速摸底、梳理代码地图、同步 AI 编码边界、可视化发现页面转化与研发效率问题并导出 AI 排查上下文包。
---

# Team Kit Skill

本技能入口直接委托给根目录的 [AGENTS.md](./AGENTS.md) 执行。

- **Team Context（团队上下文工作台）**：
  - `python3 context/scripts/init_team.py --data context/data --team-name "<团队名>"`
  - `python3 context/scripts/scan_repo.py --repo <仓库路径> --out context/data/inbox/scan`
  - `python3 context/scripts/build_portal.py --data context/data --out dist/context.html`
  - `python3 context/scripts/sync_ai_rules.py --data context/data ...`
  - `python3 context/scripts/check_safety.py --data context/data`
- **Team Radar（问题发现可视化与 AI 排查）**：
  - `python3 radar/scripts/build_radar.py --input <快照JSON> [--context-dir context/data] --out dist/radar.html --tokens-out dist/tokens.json`
  - `python3 radar/scripts/build_radar.py --input <快照JSON> --list-findings`
  - `python3 radar/scripts/build_radar.py --input <快照JSON> --export-prompt <finding_id> [--context-dir context/data]`

详细约束、隔离红线与工作流程见 [AGENTS.md](./AGENTS.md)。
