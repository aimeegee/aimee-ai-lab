# aimee-ai-lab

Aimee 的 AI 团队。她只跟 **lead** 对话;lead 带着 PO/BA、Engineer、Tester 把想法做成 project,自主做决定并记录,只在必要时来问她。团队跑在 Claude Code 上,规则全部在这个 repo 里。

设计见 [docs/design.md](docs/design.md)。

## 安装

```bash
bash scripts/install.sh
```

把全局 `/team` skill 链接到 `~/.claude/skills/team`,之后任何 Claude Code session 都能用 `/team`。

另外在用户级 `~/.claude/settings.json` 里:

- `permissions.additionalDirectories` 加入本 repo 的绝对路径,让任何目录下的 session 都能读写团队 repo
- `permissions.deny` 加入与 `.claude/settings.json` 相同的禁止名单(force push、`git reset --hard`、`rm -rf` 等)

repo 内 `.claude/settings.json` 的 `allow` 规则只有在 Claude Code 信任这个文件夹之后才生效:在 repo 里交互式运行一次 `claude` 并接受信任提示即可。

## 用法

| 你说 | lead 做什么 |
|---|---|
| `/team 记一下,我想做个 XX` | 记到 `ideas.md`,不追问、不开工 |
| `/team 我有哪些 idea` | 列出 idea |
| `/team 开始做 XX` | 开 project:建分支和 worktree,PO/BA 写需求,把问题带回给你 |
| `/team 进展怎么样` | 按各 project 的 `STATUS.md` 汇报 |
| `/team 最近替我做了哪些决定` | 汇总 `decisions.md` |
| 回答 lead 的问题 | 记入 `decisions.md`,提炼偏好到 `boss-preferences.md`,继续推进 |

在本 repo 目录里直接开 session 时默认就是 lead,不需要 `/team`。

## 目录

- `team/` — lead 规则、花名册、角色规则、模板
- `ideas.md` / `decisions.md` / `boss-preferences.md` — 共享记录,只在 `main` 上修改
- `projects/<slug>/` — 每个 project 的 `STATUS.md`、`requirements.md` 和代码(代码在 `project/<slug>` 分支上)
- `.worktrees/` — 各 project 分支的工作目录(不进 git)
- `skill/team/` — 全局 `/team` skill 源文件
- `tests/` — 团队行为的测试

## 测试

```bash
bash tests/test_roster.sh
bash tests/test_install.sh
bash tests/smoke/run_all.sh
```

冒烟测试在临时沙箱 repo 里真实调用 `claude -p`(remote 是本地 bare repo,不碰 GitHub),会消耗 token,完整跑一遍要十几分钟。需要命令行版 `claude` 已登录。
