#!/usr/bin/env bash
# Aimee merged the last milestone's PR herself; on "继续" the lead notices and closes the project
# instead of waiting for a review that already happened.
source "$(dirname "$0")/lib.sh"

sb=$(make_sandbox project-review)
git -C "$sb" worktree add -q .worktrees/demo -b project/demo
echo 'echo "Hello!"' >"$sb/.worktrees/demo/projects/demo/greet.sh"
git -C "$sb/.worktrees/demo" add projects/demo/greet.sh
git -C "$sb/.worktrees/demo" -c user.name=smoke -c user.email=smoke@example.com commit -qm "demo: M1"
git -C "$sb/.worktrees/demo" push -q -u origin project/demo

other="$sb/../other"
git clone -q "$(remote_of "$sb")" "$other"
git -C "$other" -c user.name=smoke -c user.email=smoke@example.com merge -q --no-ff origin/project/demo -m "Merge PR: demo M1"
git -C "$other" push -q origin main

run_lead "$sb" "继续" >/dev/null

git -C "$(remote_of "$sb")" show main:projects/demo/STATUS.md | grep -q "阶段: 完成" || fail "PR 已被合并,STATUS 应变为 完成"
