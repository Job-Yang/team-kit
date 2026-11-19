# 平台接入与功能扩展指南（`EXTENDING.md`）

本文档同时写给人与 AI 编程助手：进了新公司或新团队，当需要**把内部各平台的数据（代码仓、BI 看板、APM 崩溃监控、AB 实验、发布单、文档库、MCP 工具）接进 `team-kit`**，或者给仓库**扩展新模块**时，严格按本规范执行，不要各自乱建一次性脚本。

---

## 一、给 AI 的 5 步平台接线标准流程（SOP）

只要用户给你一批公司内部平台信息（地址、导表 CSV、内部 CLI、OpenAPI 或 MCP），按以下 5 步接进仓库：

1. **先确认公网隔离**：检查 `git remote -v`，确保带有真实数据的 `data/`、`context/data/`、`radar/data/`、`adapters/local/` 没有连向个人 `github.com`。
2. **集中登记到 `data/sources.json` 和 `context/data/platforms.json`**：
   - 把 `sources.example.json` 复制到 `data/sources.json`（已被 `.gitignore` 忽略）。
   - 多代码仓路径写进 `context.repos`；外部平台入口写进 `platforms` 和 `context/data/platforms.json` 供团队导航卡片直接点击。
3. **写适配脚本（严格区分公私位置）**：
   - 通用、不含任何公司信息的脚本（例如通用 CSV/Git 读取）：放在 `adapters/`。
   - 只要涉及公司域名、内部 CLI、内网接口、MCP 或专有格式：**全部写进 `adapters/local/<平台名>.py`**（已被 `.gitignore` 忽略），从 [`adapters/local_template.py`](./adapters/local_template.py) 复制改写。
   - **禁止**为了迁就某家公司的接口去魔改 `radar/scripts/build_radar.py` 或 `context/scripts/build_portal.py`。
4. **只改自己那一块并做双校验**：
   - 每个适配器只读写自己负责的 `snapshot.json` 区块（见下表），不要覆盖其它适配器写入的字段。
   - 跑快照结构校验：`python3 radar/scripts/validate_snapshot.py --input radar/data/snapshot.merged.json`。
   - 跑安全检查：`python3 context/scripts/check_safety.py --data context/data --snapshot radar/data/snapshot.merged.json`。
5. **登记进 `radar.adapters` 并跑一键刷新**：
   - 把新适配器加入 `data/sources.json` 的 `radar.adapters` 数组。
   - 执行 `python3 scripts/refresh.py --sources data/sources.json`（日常只刷新报表可加 `--skip-scan`），验证 Context 与 Radar 两个 HTML 都能一次性无报错生成。

---

## 二、`snapshot.json` 区块归属分工（防互相覆盖）

多个适配器串行合并写入同一份 `radar/data/snapshot.merged.json` 时，按下面归属修改，避免互相踩数据：

| 平台或数据来源 | 应该写进 `snapshot.json` 的哪个区块 | 注意事项 |
| --- | --- | --- |
| BI / 埋点平台（流量与页面元素） | `flow.nodes[].biz`、`flow.nodes[].elements`、`flow.edges`、`timeline.biz_conv` | 节点按 `id` 对齐，保留 `elements` 与 `slices` |
| APM / 崩溃与性能监控 | `flow.nodes[].tech`、`flow.nodes[].slices`、`timeline.tech_p90_ms`、`timeline.crash_rate` | 按版本、高中低机型聚合，禁止写单设备隐私 |
| 前端卡点与 AI 坏例统计 | `flow.nodes[].frustration`（退回/连点/AI 改错/半路关闭） | 与 `flow.nodes[].elements[].issue_rate` 保持一致 |
| 发布系统 / AB 实验 / 远程配置 / Prompt 平台 | `timeline.changes` | 每条标明 `date`、`type`、`title`、`owner`、`focus_node`、`impact` |
| Git 代码仓热修与返工统计 | `engineering.rework_files` | 可直接启用内置通用适配器 `adapters/git_rework.py` |
| 需求排期与工时耗时 | `engineering.subteams`、`engineering.time_sinks` | 小组级按期率，禁止个人考核字段 |
| 业务阈值微调（可选） | `thresholds` | 需要按业务收紧或放宽告警线时覆盖（如 `crash_danger`、`p90_danger_ms`、`on_time_min`） |

---

## 三、给 `team-kit` 扩展新模块（第 3 个及以上独立模块）的标准

如果以后确定要加新的工程效能能力（例如本地评测回归 `eval/` 或周报助手），先确保和 `context/`、`radar/` 解决的是不同问题，再遵守这 5 条准则：

1. **平级独立目录**：建在仓库根目录 `<module>/` 下（含 `scripts/`、`examples/`、`README.md`），不侵入已有模块源码。
2. **零三方依赖**：脚本保持仅依赖 Python 3 标准库与原生 `git`（或可选读取其它模块的输出 JSON）。
3. **公私彻底隔离**：新模块用到的真实公司数据、中间产物全部落进各自 `<module>/data/` 或根 `data/`，并在 `.gitignore` 声明屏蔽。
4. **进一键刷新与自测**：提供结构清晰的 CLI 入口，并在 `tests/run_selftest.sh` 增补自动验证阶段。
5. **同步两张说明书**：在根目录 [`README.md`](./README.md) 与 [`AGENTS.md`](./AGENTS.md) 登记模块职责与命令示例，确保 AI 进门就能看懂全貌。
