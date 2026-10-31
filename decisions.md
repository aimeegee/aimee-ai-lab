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
