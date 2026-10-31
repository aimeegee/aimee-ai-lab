#!/usr/bin/env bash
# Starting a project from an idea: branch + worktree, STATUS/requirements on main, questions for Aimee.
source "$(dirname "$0")/lib.sh"

sb=$(make_sandbox idea-photo)
out=$(run_lead "$sb" "开始做照片整理那个 idea。需求整理完、问题列给我之后就停,不要等我回答。")

slug=$(ls "$sb/projects" | grep -v '^\.' | head -1)
[[ "$slug" =~ ^[a-z0-9-]+$ ]] || fail "slug 不合法: '$slug'"
assert_file_contains "$sb/projects/$slug/STATUS.md" "阶段: 等待确认需求"
assert_file_contains "$sb/projects/$slug/requirements.md" "AC-1"
assert_file_contains "$sb/projects/$slug/requirements.md" "待确认问题"
assert_file_contains "$sb/ideas.md" "已转为 project: projects/$slug"
remote=$(remote_of "$sb")
git -C "$remote" rev-parse -q --verify "refs/heads/project/$slug" >/dev/null || fail "分支 project/$slug 未 push"
git -C "$sb" worktree list | grep -q "\.worktrees/$slug" || fail "worktree 未创建"
git -C "$remote" show "main:projects/$slug/STATUS.md" >/dev/null 2>&1 || fail "STATUS 应在 main 上"
git -C "$remote" show "main:projects/$slug/requirements.md" >/dev/null 2>&1 || fail "requirements 应在 main 上"
assert_contains "$out" "[?？]"
