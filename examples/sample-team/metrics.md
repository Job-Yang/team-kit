---
updated: 2026-11-19
review_cycle: 60d
---

# 星辰移动研发组 · 数据指标、埋点与评测

## 核心指标与看板入口

| 指标名称 | 类别 | 看板直达链接 | 核心数据表 / 埋点事件 |
| --- | --- | --- | --- |
| 首字响应耗时（TTFT P90） | 技术性能 | `https://apm.example.com/star-app/ttft` | `client_ai_stream_ttft` |
| 对话卡片交互成功率 | 业务效果 | `https://bi.example.com/star-app/cards` | `dws_star_card_action_di` |
| 流式渲染掉帧率（Drop3） | 客户端流畅度 | `https://apm.example.com/star-app/fps` | `client_scroll_drop3` |
| 线上回答合规拦截触发率 | 安全质量 | `https://bi.example.com/star-app/safety` | `dwd_star_guard_hit_hi` |

## 线上异常或坏例（Badcase）归因顺位

1. **先用 `X-Trace-Id` 区分边界**：拿客户端响应头 `X-Trace-Id` 去日志平台搜一次，先判断是根本没发出去（端侧）、中途断流（网关）、还是回包结构异常（编排/模型）。
2. **卡片不渲染问题**：优先核对 `BFF/ChatRouter` 的卡片类型白名单与端侧最小支持版本号，新版卡片未配最低版本门槛会被老版本端静默丢弃。
3. **首字慢排查**：依次拆开客户端建连耗时、BFF 上下文拉取耗时和下游模型首 Token 耗时，不在同一层瞎猜。
