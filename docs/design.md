# aimee-ai-lab 设计文档

日期:2026-10-31
状态:草稿,待 Aimee 审批

## 1. 意图

Aimee 想要一个「虚拟团队」:她只跟一个人(team lead)对话,lead 像人类团队的负责人一样,带着 PO/BA、Engineer、Tester 把她的想法做成 project。她的角色是老板:提想法、在关键处拍板、随时问进展。

她在工作中已经用 Claude Code 搭过类似的团队(这里是重写,不能复用代码)。那个版本好用的地方:只需开一个 session,不需要很多细节对话。不好的地方:
- lead 需要她决定的事太多
- 不知道怎么接入其他 AI(ChatGPT、Codex 等)和她的账号(GitHub、Google Drive、银行等)

## 2. 目标、非目标、反目标

**目标**
- 在任意 Claude Code session 里,用一个命令就能找 lead;不找时就是普通 Claude 对话
- Aimee 随口说一个想法,lead 记下来不开工;她说「开始做」时才转成正式 project
- 一个 project 从需求到交付由团队自主推进,Aimee 只在必须上报的事项上被打扰
- lead 从 Aimee 每次的选择里学习偏好,随时间推移问得越来越少
- 每个自主决定都有记录:有哪些选项、选了什么、为什么
- 任何时候、任何 session 里问「进展怎么样」都能得到准确回答(靠 repo 里的文件,不靠对话记忆)
- 角色、规则、模型配置集中在 repo 里,改一处即生效

**非目标(这一版不做)**
- 不接入非 Claude 的 AI(但设计上留口子,见 §8)
- 不接入银行、Google Drive 等私人账号(原则见 §9,具体接入以后按需做)
- 不单独设 Writer/文档角色(文字工作分给现有角色,见 §4)
- 不做 Web UI、仪表盘、定时任务
- 不负责 project 产物的部署和运行环境(那是每个 project 自己的需求)
- 不改 Aimee 其他已有的 repo(如 `3D-Print`);团队只在 `aimee-ai-lab` 和团队自己新建的 repo 里工作

**反目标(技术上能跑,但出现这些就算失败)**
- lead 动不动就来问 Aimee,跟工作版本一样烦
- 要开多个 session、或需要 Aimee 写很长很细的指令才能推进
- 团队在没问的情况下做了五类必须上报的事(§6)
- 改一个角色需要改好几个地方
- 任何密钥、token 进入 repo

## 3. 使用方式(Aimee 视角)

| Aimee 说 | lead 做什么 |
|---|---|
| `/lead 记一下,我想做个 XX` 或「跟 lead 说记个 idea」 | 写入 `ideas.md`:原话、日期、一两句理解。不追问、不开工 |
| `/lead 我有哪些 idea` | 列出 `ideas.md` |
| `/lead 开始做 XX` | 把 idea 转成 project(或直接新建),进入 §5 流程 |
| `/lead 进展怎么样` / `/lead XX 做到哪了` | 读各 project 的状态文件,汇报阶段、完成了什么、卡在哪、待 Aimee 决定的事 |
| `/lead 最近替我做了哪些决定` | 汇总 `decisions.md` 近期条目 |
| 回答 lead 提的问题 | 记入 `decisions.md`,提炼偏好写入 `boss-preferences.md`,继续推进 |

- 同一个 idea 后来又有补充,追加到原条目下,不新开一条
- 在 `aimee-ai-lab` 目录里直接开 session 时,默认就是 lead,不需要打 `/lead`

## 4. 角色

| 角色 | 负责 | 不做 | 默认模型 |
|---|---|---|---|
| **Lead** | 对接 Aimee;管 ideas;开 project;派活;跟进度;自主决策并记录;整理必须上报的问题 | 不写产品代码 | 当前 session 的模型 |
| **PO/BA** | 把想法变成需求文档:目标、范围、验收标准、待确认问题;面向最终用户的措辞(如 bot 回复模板、语气) | 不定技术方案 | Opus |
| **Engineer** | 技术设计与实现;写该 project 的技术文档/README;可多个并行做不同任务 | 不改需求;需求不清时退回 lead,不自己猜 | Sonnet,复杂任务由 lead 升为 Opus |
| **Tester** | 按验收标准写测试、实际运行、报告通过/不通过及证据 | 不修 bug,问题交回 lead 转给 Engineer | Sonnet |

文字工作的归属:需求和用户可见措辞 → PO/BA;技术文档 → Engineer;进度和决策记录 → Lead。以后如果有以文字为主要产出的 project(博客、报告),再加 Writer 角色。

**按复杂度选模型**:花名册给每个角色默认模型;lead 派活时可按任务难度上调或下调。

## 5. Project 流程

1. **开 project**:lead 新建分支 `project/<name>`,在 `projects/<name>/` 建文件夹和状态文件
2. **需求**:PO/BA 出需求文档。lead 先用 `boss-preferences.md` 和过往决策尽量自行回答 PO/BA 的问题;只有属于 §6 必须上报的,才集中成一条消息问 Aimee
3. **Aimee 确认需求**(需求范围属于必须上报,所以这一步总会有)
4. **实现**:lead 拆任务派给 Engineer
5. **验收**:Tester 按验收标准测;不通过 → 回到 Engineer;通过 → 进入下一步
6. **交付**:工作过程中随时 commit 并 push 到 project 分支。每当到达一个**可用的交付节点**(有一个能用的东西,而不只是做了一部分),lead 开一个 PR 合并到 `main`
7. **汇报**:lead 告诉 Aimee 完成了什么、PR 链接、自主做了哪些决定,请她 review。Aimee 同意后 lead 合并(或 Aimee 自己合并);有修改意见则回到第 4 步
8. 如果还有后续节点,继续在同一个分支上做,重复 4–7;project 全部完成后分支在最后一次合并后删除

**持续运行**:Aimee 确认需求后,lead 在后台一路推进到下一个交付节点的 PR(subagent 后台运行),Aimee 在同一 session 里可以继续聊别的或问进展。每完成一步都更新 `STATUS.md`。如果中途 session 关闭,下次 `/lead` 时 lead 读 `STATUS.md` 从断点继续。subagent 不能再派 subagent,所以每一步都由 lead 驱动。

**分支与 worktree(我的决定)**
- 每个 project 一个分支 `project/<name>`,在自己的 git worktree 里工作。`~/Develop/aimee-ai-lab` 主目录始终停在 `main`,这样多个 project 可以同时进行、互不干扰
- 全团队共用的文件(`ideas.md`、`decisions.md`、`boss-preferences.md`、`team/` 下的规则)不走 project 分支,由 lead 直接 commit 到 `main` 并 push。否则这些文件会在各个 project 分支上分叉,也没法在合并前被别的 session 看到

**代码位置**
- 默认:代码在 `aimee-ai-lab/projects/<name>/`
- **独立 repo**:如果 project 太大,或团队判断它更适合独立存在(例如要单独部署、单独开源、跟其他 project 没有关系),lead 可以在 Aimee 的 GitHub 账号 `aimeegee` 下新建 repo,clone 到 `~/Develop/<name>`,代码放在那边。这属于 lead 可以自主决定的事,记入 `decisions.md` 并在汇报时告诉 Aimee
- 新 repo 默认 **private**;改成 public 属于「对外可见」,必须先问
- 即使代码在独立 repo,`aimee-ai-lab/projects/<name>/` 仍保留 `STATUS.md`、`requirements.md` 和指向那个 repo 的链接,lead 查进展的方式不变
- 已经在 `projects/` 里做到一半的 project 也可以迁出去成为独立 repo,同样记入 `decisions.md`
- 独立 repo 里同样使用分支 + PR 的流程

## 6. 自主权与上报规则

**默认:lead 自主决定,写进 `decisions.md`。**

**必须先问 Aimee 的五类事**(使用中会逐步调整):
1. 改变「做什么」:范围、目标、验收标准
2. 花钱:付费服务、API 订阅
3. 对外可见:例如 bot 首次回复真实用户、发邮件、公开发布
4. 不可逆:删数据、删 repo、force push
5. 碰私人账号:银行、个人 Drive 等

**Decision register(`decisions.md`)**:全 repo 一份,每条包含日期、所属 project、问题、选项、选择、理由、是 lead 自主决定还是 Aimee 决定、是否参考了某条偏好。

**偏好学习(`boss-preferences.md`)**:每当 Aimee 拍板一件事,lead 把背后可复用的偏好提炼出来写进去(例如「偏好简单方案」「能用现成工具就不自己写」)。遇到新决策时先查这份文件;能推断出 Aimee 会怎么选就直接选,并在 register 里注明依据。

**偏好不能越过五类必问事项**:属于上面五类的事永远要问,哪怕偏好已经能推断答案。这时偏好只用来让 lead 带着推荐来问(「按你上次的选择,我建议 A,同意吗?」),让 Aimee 一个字就能回答。

**权限与依赖**
- 团队要能无人值守地运行命令、装依赖、`git push`,所以在用户级设置里为团队工作放宽权限
- 同时设一份禁止名单,在工具层面拦住不可逆操作:force push、`rm -rf`、删分支、`git reset --hard` 等(具体名单由 builder 定)
- Aimee CLAUDE.md 里「不要未经确认添加新依赖」:在 `aimee-ai-lab` 的 project 里**不适用**,团队可自由加依赖,但每次记入 `decisions.md`;在 Aimee 的其他 repo 里照旧适用

## 7. Repo 结构与全局入口

```
aimee-ai-lab/
  CLAUDE.md               # 在 repo 里开 session 时默认身份为 lead,指向 team/lead.md
  team/
    lead.md               # lead 的行为规则(§3 §5 §6)
    roster.md             # 花名册:角色、执行者(claude/…)、默认模型、角色文件路径
    roles/
      po-ba.md
      engineer.md
      tester.md
  ideas.md
  decisions.md
  boss-preferences.md
  projects/
    <name>/
      STATUS.md           # 阶段、已完成、阻塞、待 Aimee 决定
      requirements.md
      ...                 # 该 project 的代码与文档
  docs/
    design.md             # 本文档
```

**全局入口(不在 repo 里,装在 Aimee 的用户级 Claude 配置中)**
- 一个用户级 skill `lead`(`~/.claude/skills/lead/`):在任何 session 里由 `/lead` 或「跟 lead 说…」触发。它只是个指针:让当前 session 读 `~/Develop/aimee-ai-lab/team/lead.md` 并以 lead 身份行事。所有实质内容留在 repo,有版本记录
- 用户级设置中把 `~/Develop/aimee-ai-lab` 加为允许目录,使任何工作目录下的 session 都能读写它而不反复授权

**派活机制(我的决定)**:角色不用 repo 内的 `.claude/agents/`(那只在 cwd 是该 repo 时加载,与「任何 session 都能用」冲突)。lead 派活时读取 `roster.md` 和对应角色文件,用 Claude Code 的 subagent 工具派出一个通用 subagent:提示词 = 角色文件内容 + 具体任务,模型 = 花名册默认值或 lead 的覆盖值。

## 8. 以后接入其他 AI 的预留

`roster.md` 每个角色有「执行者」字段,这一版全部是 `claude`。以后要让 ChatGPT/Codex 担任某角色时:改该字段为 `codex`(或其他),并在 `lead.md` 里补充「执行者为 codex 时,通过命令行 `codex exec` 派活,传入同样的角色文件 + 任务」。角色文件本身不用改。

## 9. 账号与密钥

- **GitHub**:本机 `gh` 已登录 `aimeegee`,团队可以 pull/push、开 PR、新建 private repo(见 §5)。这一版只接这一个
- **Google Drive 等**:以后通过 Claude Code connector(MCP)接入,接入属于「碰私人账号」,需 Aimee 确认
- **银行**:只读,永远不能动钱。倾向用 Plaid 类聚合服务或定期导出 CSV
- **密钥**:只放 macOS Keychain 或本地 git 忽略的文件;repo 里只记录「需要哪个 key」

## 10. 成功标准

- 在 `~/Develop` 下任意目录开 session,`/lead` 能用,能读写团队 repo
- 记一个 idea 是一句话、几秒钟的事,lead 不追问
- 一个小 project 能从 idea 走到一个等 Aimee review 的 PR,Aimee 只被问需求确认、五类事和 PR review
- `decisions.md` 里能看到 lead 的每个自主决定及理由
- 同类问题(五类必问之外)第二次出现时,lead 参考偏好自行决定而不是再问
- 需求确认后,Aimee 不需要再发消息,团队就能推进到下一个 PR;中间关掉 session 也能接着做
- 多个 project 可以同时进行,各自在自己的分支上
- 团队能自己判断并新建一个 private repo,把 project 放过去
- 团队运行期间不弹权限窗口,而禁止名单里的操作会被拦下

## 11. 留给 builder 的

- 各角色文件、`lead.md` 的具体措辞
- `STATUS.md`、`decisions.md`、`ideas.md`、`boss-preferences.md` 的具体格式
- project 文件夹命名规则
- 多个 Engineer 并行时如何避免在同一 repo 里互相冲突
- lead 自身对 decisions/ideas 等文件的提交和 push 节奏
- 选一个端到端的冒烟测试来验证整套流程
