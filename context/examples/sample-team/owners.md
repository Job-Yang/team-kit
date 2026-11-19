---
updated: 2026-11-19
review_cycle: 60d
---

# 星辰移动研发组 · 找人地图与工作分工

> 提示：本文件仅记录模块责任边界、平台权限接口人与跨职能对接人，严禁记录对同事能力的任何主观评价。

## 模块与日常平台接口人

| 模块或平台 | 负责范围 | 首选对接人 | 备份接口人 |
| --- | --- | --- | --- |
| 客户端对话主链路与流畅度 | `iOS/ChatUI`、`iOS/StreamRenderer`、APM 性能 | 林深 | 陆远 |
| 拍照预处理与跨端 Bridge | `iOS/MediaCapture`、`Client/Bridge` | 陆远 | 陈默 |
| 全栈 BFF 与合规拦截 | `BFF/ChatRouter`、`BFF/ComplianceFilter`、日志链 | 顾言 | 林深 |
| 多智能体编排与模型调用 | `Agent/Orchestrator`、模型版本发布 | 沈星 | 顾言 |
| 埋点规范、AB 实验与看板 | `Data/EvalTracker`、实验开关与核心指标表 | 苏夏 | 周舟 |
| 仓库权限、发版窗口与入职答疑 | CI/CD 流水线、权限申请与需求排期 | 周舟 | 陈默 |
