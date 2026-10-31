#!/usr/bin/env bash
# "Start X" where X matches no existing idea creates a new project instead of reusing another idea.
source "$(dirname "$0")/lib.sh"

sb=$(make_sandbox idea-photo)
run_lead "$sb" "开始做一个把播客转成文字稿的工具。需求整理完、问题列给我之后就停,不要等我回答。" >/dev/null

slug=$(ls "$sb/projects" | grep -v '^\.' | head -1)
[ -n "$slug" ] || fail "没有新建 project"
assert_file_contains "$sb/projects/$slug/requirements.md" "播客"
grep -A1 "^## photo-organizer" "$sb/ideas.md" | grep -q "状态: 未开始" || fail "photo-organizer 不应被改动"
