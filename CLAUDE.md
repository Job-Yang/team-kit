# CLAUDE.md

请直接阅读并严格遵循根目录的 [AGENTS.md](./AGENTS.md)。

快速检查清单：
- 在企业内网使用前，先确认已解除个人 `github.com` 远端（`git remote -v`）。
- 全部动作使用 `context/scripts/` 与 `radar/scripts/` 下的 Python 标准库脚本（无需安装三方包）。
- 机器梳理出的 Context 草稿统一先写进 `inbox/`，必须经过用户确认后再写入正式目录。
- 每次修改团队数据后，执行 `python3 context/scripts/check_safety.py --data <数据目录>` 检查敏感信息与过期条目，再刷新网页产出。
