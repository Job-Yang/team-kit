# 适配器层说明（`adapters/`）

本目录用于承接“把各家公司内部数据接进 Team Radar / Team Context”的读取脚本。为了兼顾 **跨公司可带走** 与 **绝不泄密**，目录分为两层：

- **通用适配器（放当前目录 `adapters/`，可推个人 GitHub）**：不绑定任何公司域名、内网 SDK 或业务名称。
  - `git_rework.py`：只读扫描指定 Git 仓近 N 天高频改动与热修记录，写入 `engineering.rework_files`。
  - `csv_to_snapshot.py`：把标准表头的节点指标 CSV 与每日趋势 CSV 增量合并进 `snapshot.json`。
  - `local_template.py`：公司专属适配器的复制模板，定义统一参数与安全底线。
- **公司专属适配器（放 `adapters/local/`，已被 `.gitignore` 严格忽略）**：进了新公司后，所有调用内部 API、内网 CLI、MCP 或特殊数仓导出格式的脚本一律新建在 `adapters/local/` 下，严禁改写通用 `radar/` 编译器去适配某家公司。

## 所有适配器必须遵守的四条规范

1. **统一命令行入口**：至少接收 `--snapshot <目标snapshot.json路径>` 参数；先读已有快照（若不存在则初始化骨架），再只更新自己负责的那一块字段，保留其它字段不变。
2. **只读写授权环境变量**：所有 Token / Cookie / 认证信息一律通过 `os.environ.get("...")` 读取，绝对不硬编码进脚本或配置文件。
3. **只写聚合统计不写明细**：`snapshot.json` 只存放聚合数（UV/PV、转化率、分位数、次数）与文件路径，严禁写入用户个人身份信息、原始文本明细或个人考核评价。
4. **保持轻量且可独立重跑**：优先用 Python 标准库或本机已有的公司 CLI，失败时输出清晰中文错误到 stderr 并以非零状态码退出，不得损坏原快照文件。
