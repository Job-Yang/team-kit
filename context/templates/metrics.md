---
updated: {{TODAY}}
review_cycle: 60d
---

# {{TEAM_NAME}} · 数据指标、埋点与评测

## 核心指标与看板入口

| 指标名称 | 看什么（业务/技术） | 看板直达链接 | 核心数据表 / 埋点事件 |
| --- | --- | --- | --- |
| 日活 / 核心转化率 | 业务指标 | `https://bi.internal.example.com/core` | `dws_team_core_di` |
| 首屏耗时 / 崩溃率 | 技术稳定性 | `https://apm.internal.example.com/perf` | `client_perf_fmp` |

## 异常或坏例归因顺位

1. 先查客户端埋点上报与参数是否缺失；
2. 再查网络与网关状态码及流式中断记录；
3. 最后核对下游服务端或模型评测集表现。
