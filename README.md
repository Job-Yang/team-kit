# Team Context

面向研发团队与 AI 协同的通用工作台工具包：把分散在平台、代码库和老员工脑子里的团队常识整理进纯文本目录，一边生成**给人看的可交互 HTML 团队网站**，另一边生成**给 AI 编程工具看的团队背景与代码红线**。

- **零第三方依赖**：全部脚本只使用 Python 3 标准库与原生 `git` 命令，生成的 HTML 网站为单文件自包含（无外部 CDN），断网和内网开发机直接可用。
- **工具与数据物理隔离**：`scripts/`、`templates/` 与说明文档可跨公司带走；公司团队的真实数据放在 `data/` 下，默认已被 `.gitignore` 忽略。
- **完整设计方案**：请看 [docs/design.md](./docs/design.md)（写给人看，可直接同步到个人网站）。

## 进新公司第一步（安全防误推）

拉下本仓库后，进入公司内网环境第一件事先解除个人 GitHub 远端绑定，再绑定公司内网 Git 仓库，防止以后误将团队数据推送到公网：

```bash
git clone https://github.com/Job-Yang/team-context.git
cd team-context
git remote remove origin
# 如需托管到公司内网：git remote add origin <公司内网仓库地址>
```

## 零配置先看效果

仓库内置了一个虚构团队样例（`examples/sample-team/`），直接运行两条命令即可体验生成的交互网页：

```bash
python3 scripts/build_portal.py --data examples/sample-team --out /tmp/sample-portal.html --export-md /tmp/sample-handbook.md
open /tmp/sample-portal.html
```

## 日常 4 条常用命令

```bash
# 1. 初始化当前团队的数据目录（生成 7 份模板 + data/inbox/ 草稿区）
python3 scripts/init_team.py --data data --team-name "我的新团队"

# 2. 只读扫描业务代码仓，提取热改文件、高频耦合、回滚记录与代码关系草稿（写入 data/inbox/）
python3 scripts/scan_repo.py --repo /path/to/your-project --out data/inbox/scan

# 3. 编译可交互 HTML 团队网站（附带导出静态汇总 Markdown 兜底）
python3 scripts/build_portal.py --data data --out dist/index.html --export-md dist/team-handbook.md

# 4. 同步团队代码红线到业务仓库的 AI 规则文件，并按任务抽取精简上下文
python3 scripts/sync_ai_rules.py --data data --mode rules --format agents --target /path/to/your-project/AGENTS.md
python3 scripts/sync_ai_rules.py --data data --mode context --task debug

# 5. 提交前安全与过期检查（拦住密钥/隐私/主观评价，标出超期与死链）
python3 scripts/check_safety.py --data data
```

## 目录结构

```text
team-context/
├── README.md                 # 当前文件：极简操作说明
├── AGENTS.md                 # AI 执行手册（任何 AI 进仓后先读这里）
├── CLAUDE.md                 # Claude Code 入口（指向 AGENTS.md）
├── SKILL.md                  # 兼容 Agent Skills 生态的标准入口
├── docs/                     # 给人看的完整设计方案与结构图
├── scripts/                  # 零依赖通用 Python 工具脚本
├── templates/                # 7 类团队资产空白模板
├── examples/sample-team/     # 完整虚构演示样例
├── tests/                    # 端到端自动化自测脚本
└── data/                     # 团队真实资产目录（默认不提交到公网）
```

## AI 编程助手怎么接手

把任何 AI 编程工具（Cursor、Claude Code、Codex、TRAE 或公司内网 AI IDE）指向本目录，直接告诉它：**“先读 `AGENTS.md`，帮我初始化当前团队的 Team Context 并扫描我们的业务仓库。”**

## License

MIT
