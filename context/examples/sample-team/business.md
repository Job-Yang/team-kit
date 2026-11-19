---
updated: 2026-11-19
review_cycle: 60d
---

# 星辰移动研发组 · 业务全景与主流程

> 本样例为虚构演示数据，展示 Team Context 在真实研发团队中如何精简记录业务主线。

## 团队业务定位

- **核心产品**：面向消费端用户的 AI 智能生活助手客户端（覆盖 iOS 原生、动态卡片容器与 BFF 全栈中间层）。
- **核心场景**：日常智能对话、拍照识别解析、个性化推荐服务闭环与智能硬件数据同步。

## 一条典型对话请求的流转路径

1. **端侧入口**：用户在 `iOS/ChatUI/ChatInputViewController.swift` 发送问题或图片，调用 `Client/NetworkAuth` 建立 SSE 长连接。
2. **全栈网关**：请求进入 `BFF/ChatRouter`，拼接最近 10 轮历史上下文并注入统一 `X-Trace-Id`。
3. **编排与合规**：`Agent/Orchestrator` 调度模型与工具生成结构化卡片，回包**必须**经过 `BFF/ComplianceFilter` 做合规复核与兜底拼装后才允许下发。
4. **端侧流式上屏**：`iOS/StreamRenderer` 每 60ms 合并渲染一帧增量 Markdown 与动态卡片，并由 `Data/EvalTracker` 上报首字耗时。
5. **完整需求主文档**：`https://docs.example.com/star-team/product-roadmap`
