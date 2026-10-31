# 照片清理工具

- 阶段: 实现
- 分支: project/photo-cleanup
- 代码位置: projects/photo-cleanup/
- 最后更新: 2026-10-31

## 交付节点
- [ ] M1: 预览版——生成报告，标出完全重复、相似组、短视频、截图，不动任何文件
- [ ] M2: 执行版——删除完全重复副本、可疑项移到「待复查」、生成操作记录并支持还原
- [ ] M3: 复用版——参数化 + agent 能直接读懂调用的接口（如 Claude Code skill），明年直接用

## 已完成
- requirements.md 定稿，Aimee 已确认（见 decisions.md 的 D-006~D-009）

## 进行中
- 拆 M1 任务，派 Engineer

## 阻塞

## 待 Aimee 决定

## 备注
- 实验/验收目录：~/Documents/Photos/2025（Aimee 提供，真实数据）
- 照片格式：HEIC 和 JPG 都要支持
- M4（反馈学习，按误判调整阈值）暂不排期：先做 M1~M3，操作记录里顺手记判断用的具体数值（D-010），用 ~/Documents/Photos/2025 做第一次测试，Aimee review 反馈后再设计 M4
