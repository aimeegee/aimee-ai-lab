# Aimee 的偏好

<!--
条目格式:
  ### P-NNN <一句话偏好>
  - 来源: D-NNN
  - 适用: <什么场景下参考>
-->

### P-001 Aimee 偏好通过和 agent 对话来触发本地工具/脚本，而不是自己记命令行或读使用文档
- 来源: projects/photo-cleanup/decisions.md 的 D-005
- 适用: 要交付给 Aimee 日常自己用的脚本/工具类 project，默认设计成 agent 能直接读懂并调用的接口（必要时封装成 Claude Code skill），而不是只给一份命令行使用文档

### P-002 PR 少开、但每个都要是测过的 working 状态；批准靠口头说，不走 GitHub review
- 来源: 顶层 decisions.md 的 D-002
- 适用: 所有 project 的 PR 流程。默认把多个交付节点攒到一起开一个 PR（除非 Aimee 要求提前看某个节点）；开 PR 前必须先实际跑过功能、确认是 working 的，不能是半成品；Aimee 在聊天里口头说"批准"/"可以 merge" 即可执行 `gh pr merge`，不用等她在 GitHub 上 review（因为 PR 是用她自己的 token 开的，她没法 review 自己的 PR）
