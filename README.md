# Team Kit

面向研发团队的零依赖通用工具集，由两个独立模块组成：

- [`context/`](./context/README.md)（Team Context）：把散落在平台、代码库和老员工脑子里的常识攒到一处，编译**给人看的交互团队网站**和**给 AI 用的背景与代码红线**。
- [`radar/`](./radar/README.md)（Team Radar）：用同一份轻量数据快照驱动**发现问题可视化看板**（总览、页面转化与仿真手机元素透视、上线变动对照、交付效率），并把问题拆成 **3 步排查清单与 AI 上下文包**。

两大原则始终不变：
1. **零第三方依赖**：全部脚本仅依赖 Python 3 标准库与原生 `git`，输出的 HTML 均为单文件离线可用（无外部 CDN）。
2. **工具与数据物理隔离**：`context/scripts/`、`radar/scripts/` 与文档可跨公司带走；公司真实数据一律留在 `data/`（默认被 `.gitignore` 忽略）。

## 进新公司第一步（防误推公网）

进入公司内网后，先解除个人 GitHub 远端绑定，再绑定内网 Git 仓：

```bash
git clone https://github.com/Job-Yang/team-kit.git
cd team-kit
git remote remove origin
# 如需托管到公司内网：git remote add origin <公司内网仓库地址>
```

## 零配置先看两个模块的演示效果

```bash
# 1. 体验 Team Context 团队工作台
python3 context/scripts/build_portal.py \
  --data context/examples/sample-team \
  --out dist/context-demo.html \
  --export-md dist/context-handbook.md

# 2. 体验 Team Radar 问题发现雷达（含仿真手机元素透视与 AI 排查抽屉）
python3 radar/scripts/build_radar.py \
  --input radar/examples/demo-radar.json \
  --out dist/radar-demo.html \
  --tokens-out dist/tokens.json

open dist/radar-demo.html
```

## 两个模块的常见协同方式

- 先用 `context/` 摸清代码地图、模块分工与常见避坑；
- 再用 `radar/` 定期汇总页面转化、崩溃耗时、上线变动与返工数据；
- 编译 `radar/` 时加 `--context-dir context/data`，会自动把匹配到的模块负责人、热改记录与历史避坑附进 AI 排查包；不加 `--context-dir` 时 `radar/` 也能完全独立运行。

## 目录结构

```text
team-kit/
├── README.md                 # 当前文件：工具集总览与快速入口
├── AGENTS.md                 # AI 执行手册（任何 AI 进仓后先读这里）
├── CLAUDE.md                 # Claude Code 入口（指向 AGENTS.md）
├── SKILL.md                  # 兼容 Agent Skills 生态的标准入口
├── context/                  # 模块 1：Team Context（脚本 / 模板 / 演示样例）
├── radar/                    # 模块 2：Team Radar（编译器 / 演示快照 / 说明）
├── docs/                     # 给人看的完整设计方案与高清结构图
│   ├── team-context.md
│   └── team-radar.md
├── tests/                    # 覆盖两个模块的自动化自测脚本
└── data/                     # 团队真实数据目录（默认不提交到公网）
```

## 详细设计文档

- [Team Context 设计方案](./docs/team-context.md)
- [Team Radar 设计方案](./docs/team-radar.md)

## AI 编程助手怎么接手

把任意 AI 编程工具（Cursor、Claude Code、Codex、TRAE 或公司内网 AI IDE）指向本目录：
**“先读 `AGENTS.md`，帮我初始化当前团队的工作台并生成 Demo 雷达看效果。”**

## License

MIT
