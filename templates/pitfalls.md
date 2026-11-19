---
updated: {{TODAY}}
review_cycle: 60d
---

# {{TEAM_NAME}} · 避坑指南与历史决定

> 说明：踩完坑或做完重要技术取舍后，直接口述经过让 AI 生成 5 到 10 行草稿放进 `data/inbox/`，确认后补入这里。

## 高频踩坑卡片示例（请替换为团队真实记录）

### [示例] 某模块看似冗余的兜底判断不能删除

- **涉及模块**：`Client/Network/RetryGuard`（附代码行号）
- **当年背景**：早期某系统版本弱网下会重复触发回调，导致重复下单或状态错乱。
- **绝不能做的事**：不要因为静态代码扫描提示冗余就顺手删掉幂等锁。
- **复盘原链接**：`https://docs.internal.example.com/postmortem-example`
