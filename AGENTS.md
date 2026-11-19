# Team Kit Agent 执行手册

任何 AI 编程助手打开本仓库时，按本手册的顺序与边界执行任务。全部核心脚本仅依赖 Python 3 标准库与原生 `git`。

## 1. 铁律（先读，绝对不能踩）

1. **只走获批内网环境**：在企业环境中工作时，禁止把团队代码、文档、指标明细、`data/` 或 `adapters/local/` 内容发送到外部未授权网络或模型。
2. **草稿先落 `inbox/`，人点确认才进正式区**：扫描结果、旧文档拆解和新增经验全部先写进 `context/data/inbox/`。没有用户确认、没有挂上代码路径或文档链接前，不得覆盖正式文件。
3. **五类内容严禁写入仓库与快照**：账号密码、密钥与 Token、真实用户隐私样例、未脱敏业务/医疗/金融明细、对同事性格或绩效的主观评价。写完或提交前必须跑 `python3 context/scripts/check_safety.py --data context/data [--snapshot radar/data/snapshot.merged.json]`。
4. **Radar 只做发现、定位与交接**：Team Radar 负责交叉发现异常、指明元素与代码入口、打包 AI 排查上下文，不直接自动修改线上代码或配置。
5. **严禁把公司数据和专属脚本推向个人 GitHub**：只要远端包含 `github.com`，绝不能提交 `data/`、`context/data/`、`radar/data/`、`adapters/local/` 下的任何文件。

## 2. 模块一：Team Context（`context/`）

核心命令（以仓库根目录执行）：

- 初始化数据目录：`python3 context/scripts/init_team.py --data context/data --team-name "<团队名>"`
- 扫描单仓或多仓：`python3 context/scripts/scan_repo.py --repo <仓1> [--repo <仓2>] --out context/data/inbox/scan`
- 编译交互网站：`python3 context/scripts/build_portal.py --data context/data --out dist/context.html --export-md dist/handbook.md`
- 同步写代码红线：`python3 context/scripts/sync_ai_rules.py --data context/data --mode rules --format agents --target <业务仓>/AGENTS.md`
- 按任务取上下文：`python3 context/scripts/sync_ai_rules.py --data context/data --mode context --task <feature|debug|metrics|review>`
- 安全与过期检查：`python3 context/scripts/check_safety.py --data context/data`

7 类标准资产文件（位于团队内网数据的 `context/data/` 下）：
- `platforms.json`（日常平台入口）、`code-graph.json`（代码关系与热区）、`business.md`（业务主流程）、`metrics.md`（指标与看板）、`standards.md`（工程红线）、`pitfalls.md`（避坑卡片）、`owners.md`（模块分工）。

## 3. 模块二：Team Radar（`radar/`）

快照数据结构与可配置 `thresholds` 以 [`radar/examples/demo-radar.json`](./radar/examples/demo-radar.json) 为准；任何导表或拉数结果必须先过结构校验。

核心命令：

- 校验快照格式：`python3 radar/scripts/validate_snapshot.py --input <快照JSON>`
- 检查快照安全：`python3 context/scripts/check_safety.py --snapshot <快照JSON>`
- 编译雷达看板：`python3 radar/scripts/build_radar.py --input radar/examples/demo-radar.json --out dist/radar-demo.html --tokens-out dist/tokens.json`
- 联动 Team Context：`python3 radar/scripts/build_radar.py --input <快照JSON> --context-dir context/data --out dist/radar.html --tokens-out dist/tokens.json`
- 列出提炼重点问题：`python3 radar/scripts/build_radar.py --input <快照JSON> --list-findings`
- 导出 AI 排查包：`python3 radar/scripts/build_radar.py --input <快照JSON> --export-prompt <finding_id> [--context-dir context/data]`

## 4. 接入新公司各平台与功能扩展（接真实数据时先读）

当用户向你提供新团队的多代码仓、BI 看板、APM 监控、发布单、AB 实验或 MCP 工具并要求“接起来”时，**严格按 [`EXTENDING.md`](./EXTENDING.md) 与 [`adapters/README.md`](./adapters/README.md) 执行**，不要零散乱写一次性脚本：

1. 将 [`sources.example.json`](./sources.example.json) 复制为 `data/sources.json`，统一登记团队代码仓、平台入口与快照路径。
2. 通用 Git 返工统计直接复用 `adapters/git_rework.py`，标准 CSV 导表直接复用 `adapters/csv_to_snapshot.py`。
3. 涉及公司内网接口、CLI 或特殊格式的脚本，一律基于 [`adapters/local_template.py`](./adapters/local_template.py) 在 **`adapters/local/`**（已被 `.gitignore` 忽略）新建，只更新自己负责的快照区块，绝不修改通用 `radar/scripts/build_radar.py`。
4. 把新适配器登记到 `data/sources.json` 后，运行一键串联刷新命令完成拉数、校验、安全检查与双网页输出：
   `python3 scripts/refresh.py --sources data/sources.json`

## 5. 新团队冷启动建议顺序

1. 确认远端安全隔离后，先跑一次 `context/` 初始化和代码扫库，把代码地图与避坑框架搭起来。
2. 收集团队最近 7 天的核心转化、灰度崩溃和上线变动（第一周哪怕只有导表 CSV + `adapters/git_rework.py`），校验后跑出 `radar/` 看板。
3. 当雷达标出具体问题后，在看板点「AI 排查」复制上下文包或用 `--export-prompt` 导出，回到当前 AI IDE 继续查源码和日志。
4. 查明根因并修完后，把这条经验写成 5–10 行草稿补进 `context/data/inbox/`，人确认后转正，形成闭环。
