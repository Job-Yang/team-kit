# CLAUDE.md

请直接阅读并严格遵循根目录的 [AGENTS.md](./AGENTS.md)。

快速检查清单：
- 在企业内网使用前，先确认已解除个人 `github.com` 远端（`git remote -v`）。
- 全部动作使用 `scripts/` 下的 Python 标准库脚本（无需安装任何三方包）。
- 机器梳理出的草稿统一先写进 `data/inbox/`，必须经过用户确认后再写入 `data/` 正式文件。
- 每次修改 `data/` 后，执行 `python3 scripts/check_safety.py --data data` 检查敏感信息与过期条目，再运行 `python3 scripts/build_portal.py --data data --out dist/index.html` 刷新网页。
