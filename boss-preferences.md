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
