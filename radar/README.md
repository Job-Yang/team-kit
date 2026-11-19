# Team Radar（`radar/`）

基于统一数据快照生成**离线可交互的问题发现看板**（总览、页面转化与仿真手机元素透视、上线变动对照、交付效率），并把异常提炼为 3 步核查清单与可带走的 AI 排查上下文包。

## 快速体验 Demo

```bash
python3 radar/scripts/build_radar.py \
  --input radar/examples/demo-radar.json \
  --out dist/radar-demo.html \
  --tokens-out dist/tokens.json

open dist/radar-demo.html
```

## 常用命令行用法

```bash
# 查看自动提炼的所有重点问题 ID
python3 radar/scripts/build_radar.py --input radar/examples/demo-radar.json --list-findings

# 导出单条问题的 AI 排查上下文包（可直接粘贴进 AI IDE）
python3 radar/scripts/build_radar.py --input radar/examples/demo-radar.json --export-prompt f_page_capture_tech

# 可选：联动 Team Context 数据目录，为 AI 排查包自动补充负责人与避坑背景
python3 radar/scripts/build_radar.py \
  --input radar/examples/demo-radar.json \
  --context-dir context/examples/sample-team \
  --out dist/radar-demo.html \
  --tokens-out dist/tokens.json
```

## 三档渐进取数（统一输出标准快照 JSON）

| 档位 | 数据来源 | 适用阶段 | 是否需要改前端 |
| --- | --- | --- | --- |
| 第一档 | 手工导表或 CSV 转 JSON | 进组第 1 周快速起盘 | 不需要 |
| 第二档 | 本地只读脚本定时汇总 Git 与报表 | 日常周巡检 | 不需要 |
| 第三档 | 内部看板 / APM / MCP 只读插件 | 长期自动日巡检 | 不需要 |

完整设计方案见 [../docs/team-radar.md](../docs/team-radar.md)。
