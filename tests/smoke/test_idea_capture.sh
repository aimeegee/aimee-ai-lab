#!/usr/bin/env bash
# A new idea is recorded and pushed to main, without starting a project.
source "$(dirname "$0")/lib.sh"

sb=$(make_sandbox)
run_lead "$sb" "记一下,我想做个自动整理手机照片的工具,还没想好细节" >/dev/null

assert_file_contains "$sb/ideas.md" "照片"
assert_file_contains "$sb/ideas.md" "状态: 未开始"
assert_file_contains "$sb/ideas.md" "记录: $(date +%F)"
[ -z "$(ls "$sb/projects")" ] || fail "不应创建 project"
git -C "$(remote_of "$sb")" show main:ideas.md | grep -q "照片" || fail "未 push 到 main"
