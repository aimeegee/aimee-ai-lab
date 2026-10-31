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
- 拆 M1 任务，准备派 Engineer

## 阻塞

## 待 Aimee 决定
1. 要不要加一个"反馈学习"能力（Aimee review 待复查文件夹后，删掉的算判对、留下的算误判，脚本据此调整下次的敏感度）？这会新增一个 M4，且需要先把 M1~M3 跑起来积累真实反馈数据才能做。lead 的建议和具体设计见 Aimee 当前这轮对话里 lead 的回复，待她决定是否现在就定为 M4 还是先用 M1~M3，以后再议

## 备注
- 实验/验收目录：~/Documents/Photos/2025（Aimee 提供，真实数据）
- 照片格式：HEIC 和 JPG 都要支持
