# Team Kit Agent 执行手册

任何 AI 编程助手打开本仓库时，按本手册的顺序与边界执行任务。全部脚本仅依赖 Python 3 标准库与原生 `git`。

## 1. 铁律（先读，绝对不能踩）

1. **只走获批内网环境**：在企业环境中工作时，禁止把团队代码、文档、指标明细或 `data/` 内容发送到外部未授权网络或模型。
2. **草稿先落 `inbox/`，人点确认才进正式区**：扫描结果、旧文档拆解和新增经验全部先写进 `data/inbox/`。没有用户确认、没有挂上代码路径或文档链接前，不得覆盖正式文件。
3. **五类内容严禁写入仓库**：账号密码、密钥与 Token、真实用户隐私样例、未脱敏业务/医疗/金融明细、对同事性格或绩效的主观评价。写完或提交前必须跑 `python3 context/scripts/check_safety.py --data <数据目录>`。
4. **Radar 只做发现、定位与交接**：Team Radar 负责交叉发现异常、指明元素与代码入口、打包 AI 排查上下文，不直接自动修改线上代码或配置。
5. **严禁把 `data/` 推向个人 GitHub**：发现远端 `origin` 指向 `github.com` 时，必须阻止把公司 `data/` 提交或推送上去。

## 2. 模块一：Team Context（`context/`）

核心命令（以仓库根目录执行）：

- 初始化数据目录：`python3 context/scripts/init_team.py --data context/data --team-name "<团队名>"`
- 扫描目标代码仓：`python3 context/scripts/scan_repo.py --repo <仓库路径> --out context/data/inbox/scan`
- 编译交互网站：`python3 context/scripts/build_portal.py --data context/data --out dist/context.html --export-md dist/handbook.md`
- 同步写代码红线：`python3 context/scripts/sync_ai_rules.py --data context/data --mode rules --format agents --target <业务仓>/AGENTS.md`
- 按任务取上下文：`python3 context/scripts/sync_ai_rules.py --data context/data --mode context --task <feature|debug|metrics|review>`
- 安全与过期检查：`python3 context/scripts/check_safety.py --data context/data`

7 类标准资产文件（位于团队内网数据的 `data/` 下）：
- `platforms.json`（日常平台入口）、`code-graph.json`（代码关系与热区）、`business.md`（业务主流程）、`metrics.md`（指标与看板）、`standards.md`（工程红线）、`pitfalls.md`（避坑卡片）、`owners.md`（模块分工）。

## 3. 模块二：Team Radar（`radar/`）

核心命令：

- 编译雷达看板：`python3 radar/scripts/build_radar.py --input radar/examples/demo-radar.json --out dist/radar-demo.html --tokens-out dist/tokens.json`
- 联动 Team Context：`python3 radar/scripts/build_radar.py --input <快照JSON> --context-dir context/data --out dist/radar.html --tokens-out dist/tokens.json`
- 列出提炼重点问题：`python3 radar/scripts/build_radar.py --input <快照JSON> --list-findings`
- 导出 AI 排查包：`python3 radar/scripts/build_radar.py --input <快照JSON> --export-prompt <finding_id> [--context-dir context/data]`

三档接入原则（始终归一化为同一份标准快照 JSON）：
1. **第一档**：先把公司看板 CSV 或人工整理数据转成标准快照 JSON，当天就能跑出看板验证价值。
2. **第二档**：用本地定时只读脚本汇总 `git log` 返工、构建统计和导表指标刷新快照。
3. **第三档**：接公司内部看板 / APM / MCP 只读插件增量补全，不改核心分析与前端模板。

## 4. 新团队冷启动建议顺序

1. 确认远端安全隔离后，先跑一次 `context/` 初始化和代码扫库，把代码地图与避坑框架搭起来。
2. 收集团队最近 7 天的核心转化、灰度崩溃和上线变动（即使只有一张导表），填成标准快照跑出 `radar/` 看板。
3. 当雷达标出具体问题后，在看板点「AI 排查」复制上下文包或用 `--export-prompt` 导出，回到当前 AI IDE 继续查源码和日志。
4. 查明根因并修完后，把这条经验写成 5–10 行草稿补进 `context/data/inbox/`，人确认后转正，形成闭环。
