---
name: team-context
description: 研发团队共享的 AI 上下文与一站式工作台工具包。用于初始化新团队知识底座、只读扫描代码仓生成结构草稿、拆解吸收旧新人文档、编译可交互 HTML 团队网站、同步团队代码红线到 AI 编程工具，以及进行提交前敏感信息与过期检查。
---

# Team Context Skill

本技能入口直接委托给根目录的 [AGENTS.md](./AGENTS.md) 执行。

- 初始化团队数据目录：`python3 scripts/init_team.py --data data --team-name "<团队名>"`
- 扫描目标代码仓：`python3 scripts/scan_repo.py --repo <仓库路径> --out data/inbox/scan`
- 编译可交互 HTML 团队网站：`python3 scripts/build_portal.py --data data --out dist/index.html`
- 同步 AI 红线或按任务抽取背景：`python3 scripts/sync_ai_rules.py --data data ...`
- 提交前安全与保鲜检查：`python3 scripts/check_safety.py --data data`

详细步骤、草稿确认规则与五类严禁入库红线见 [AGENTS.md](./AGENTS.md)。
