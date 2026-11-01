# Decision register — team 级（跨 project / 不属于单个 project 的决策）

<!--
条目格式(追加在末尾,编号递增):
  ### D-NNN YYYY-MM-DD <问题>
  - 选项: A) … B) …
  - 选择: <选项>
  - 理由: …
  - 决定者: lead | Aimee
  - 依据偏好: P-NNN | 无

属于某个具体 project 的决策记在 projects/<slug>/decisions.md（格式相同，不带 [slug] 前缀）。
这个文件只放团队流程/框架层面、不属于单个 project 的决策。
-->

### D-001 2026-10-31 决策记录方式：全局 decisions.md 还是按 project 分文件
- 选项: A) 继续用一个全局 decisions.md，条目带 [<slug> | team] 前缀区分 B) 项目级决策分流到 projects/<slug>/decisions.md（格式同模板，不带前缀），顶层 decisions.md 只保留团队级（不属于单个 project）的决策
- 选择: B
- 理由: Aimee 提出"decisions.md 最好是 per project 的吧"；这样和已经是 per-project 的 STATUS.md、requirements.md 保持一致，查某个 project 的决策历史更方便；团队级决策仍有地方记录。已将原 D-001~005（均属于 photo-cleanup）迁移到 projects/photo-cleanup/decisions.md
- 决定者: Aimee
- 依据偏好: 无

### D-002 2026-11-01 PR 的开法与批准方式

- 选项: A) 继续每个交付节点都开一个 PR,Aimee 在 GitHub 上 review 后 merge B) 多个交付节点攒到一起开一个 PR 以减少 PR 数量;开 PR 前必须确认功能已实际测试过、是 working 状态;批准方式改为 Aimee 在聊天里口头说批准,而不是 GitHub review
- 选择: B
- 理由: Aimee 指出 PR 是用她自己的 GitHub token 开的,她没法 review 自己开的 PR;同时要求减少 PR 数量,但不能牺牲质量——每个 PR 必须是测过、能跑的,不能是半成品
- 决定者: Aimee
- 依据偏好: 无
