#!/usr/bin/env bash
# A follow-up thought on an existing idea is appended to that entry, not filed as a new one.
source "$(dirname "$0")/lib.sh"

sb=$(make_sandbox idea-photo)
run_lead "$sb" "照片整理那个想法补充一下:要能按人脸分类" >/dev/null

[ "$(grep -c '^## ' "$sb/ideas.md")" = 1 ] || fail "应追加到原条目而不是新建"
assert_file_contains "$sb/ideas.md" "^  - $(date +%F): \".*人脸"
git -C "$(remote_of "$sb")" show main:ideas.md | grep -q "人脸" || fail "补充未 push 到 main"
