# Team Context Agent 执行手册

任何 AI 编程助手打开本仓库时，按本手册的顺序与边界执行任务。所有命令只依赖 Python 3 标准库与原生 `git`。

## 1. 铁律（先读，绝对不能踩）

1. **只走获批内网环境**：在企业环境中工作时，禁止把团队代码、文档或 `data/` 内容发送到外部未授权网络或模型。
2. **草稿先落 `data/inbox/`，人点确认才进 `data/`**：脚本扫描结果、旧文档拆解和新增经验全部先写进 `data/inbox/`。没有用户确认、没有挂上代码路径或文档链接前，不得覆盖 `data/` 下的正式文件。
3. **五类内容严禁写入 `data/`**：账号密码、密钥与 Token、真实用户隐私样例、未脱敏业务/医疗/金融数据、对同事性格或绩效的主观评价。写完或提交前必须跑一次 `python3 scripts/check_safety.py --data data`。
4. **不要搬运长文档原文**：需求评审、数仓长文档和故障复盘保持留在原平台，在 `data/` 里只留精简结论加原链接。
5. **严禁把 `data/` 推向个人 GitHub**：发现远端 `origin` 指向 `github.com` 时，必须阻止把公司 `data/` 提交或推送上去。

## 2. 7 类团队资产与对应文件

| 文件 | 存什么 | 主要读者 |
| --- | --- | --- |
| `data/platforms.json` | 拉库、编译、调试、CI/CD、发布、Crash、远程配置、AB 实验与权限直达入口 | 网页导航 + AI |
| `data/code-graph.json` | 多仓结构、模块调用关系、热改文件、回滚高发区、点击跳转地址 | 网页代码图 + AI |
| `data/business.md` | 团队业务定位、核心页面、主流程请求流转、关键需求链接 | 网页 + AI |
| `data/metrics.md` | 业务与技术指标、常用看板、数仓主表、埋点与 AI 坏例归因方法 | 网页 + AI |
| `data/standards.md` | 编码规范、必须复用的基础组件、跨层禁区、AI 写代码硬红线 | AI 规则同步 + 网页 |
| `data/pitfalls.md` | 不能乱删的兼容/合规代码、历史决定、高频事故踩坑卡片 | 网页 + AI |
| `data/owners.md` | 模块与平台分工、跨职能接口人（只写工作分工，不写个人评价） | 网页 + AI |

## 3. 新团队首次冷启动（按顺序执行）

当用户说“帮我初始化团队上下文 / 开始新团队摸底”时，按这 5 步推进：

1. **检查隔离状态**：确认 `data/` 未被公共远端追踪，执行 `python3 scripts/init_team.py --data data --team-name "<团队名>"` 初始化空模板。
2. **扫描业务代码仓**：对用户指定的业务仓执行 `python3 scripts/scan_repo.py --repo <仓库路径> --out data/inbox/scan`，拿到近 90 天热改文件、共变耦合、回滚提交、目录活跃作者和代码关系图草稿。
3. **吸收存量旧资料**：如果用户提供了历史新人指南、团队介绍或复盘文档，按上述 7 类文件模板做去重拆解，生成带原文档链接的草稿放入 `data/inbox/`，标明哪些地方缺真实数据或链接。
4. **交给人逐项校准**：列出具体的待核对清单（例如：热改目录是否对应主业务、平台链接是否已迁址、哪段旧代码因合规不能删），用户确认后再合并入 `data/` 正式文件，并更新文件头 `updated` 日期。
5. **编译双出口**：
   - 编译交互网页：`python3 scripts/build_portal.py --data data --out dist/index.html --export-md dist/team-handbook.md`
   - 同步代码红线到业务仓：`python3 scripts/sync_ai_rules.py --data data --mode rules --format agents --target <业务仓>/AGENTS.md`
   - 跑安全与体检检查：`python3 scripts/check_safety.py --data data`

## 4. 日常任务协作方式

- **领到开发或排障任务前**：运行 `python3 scripts/sync_ai_rules.py --data data --mode context --task <feature|debug|metrics|review>`，只把当前任务相关域装进上下文，不要整库全读。
- **用户踩完坑或处理完事故时**：听完经过后，自动按 5–10 行标准卡片格式（模块、现象、原因、不能做什么、代码/文档链接）写进 `data/inbox/pitfall-<日期>.md`，请用户确认后再合入 `data/pitfalls.md`，随后重编网页 `build_portal.py`。
- **代码仓结构变化后**：重新运行 `scan_repo.py` 刷新代码关系图草稿，对比差异后更新 `data/code-graph.json`。
