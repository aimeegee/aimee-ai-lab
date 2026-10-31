# 花名册

| 角色 | 执行者 | 默认模型 | 角色文件 |
|---|---|---|---|
| Lead | claude | session | `team/lead.md` |
| PO/BA | claude | opus | `team/roles/po-ba.md` |
| Engineer | claude | sonnet | `team/roles/engineer.md` |
| Tester | claude | sonnet | `team/roles/tester.md` |

- **执行者**:谁来扮演这个角色。目前只有 `claude`(通过 Agent 工具派 subagent)。以后可以换成 `codex` 等,角色文件不用改,只需在 `team/lead.md` 的「派活」一节补充对应的调用方式
- **默认模型**:`opus` / `sonnet` / `haiku`,或 `session`(用当前 session 的模型)。lead 可以按任务难度临时上调或下调
