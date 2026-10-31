#!/usr/bin/env bash
# Idea to review-ready branch across two separate sessions (the second resumes from STATUS.md).
source "$(dirname "$0")/lib.sh"

sb=$(make_sandbox)
run_lead "$sb" "开始做:一个 bash 脚本 hello.sh。'./hello.sh 名字' 输出 'Hello, 名字!';没有参数时输出用法并以 1 退出。需求整理完、问题列给我之后就停,不要等我回答。" >/dev/null
slug=$(ls "$sb/projects" | grep -v '^\.' | head -1)
[ -n "$slug" ] || fail "没有新建 project"

run_lead "$sb" "需求确认:所有待确认问题都按你的推荐。继续推进到第一个交付节点。" >/dev/null

wt="$sb/.worktrees/$slug"
script=$(find "$wt" -name hello.sh -not -path '*/.git/*' | head -1)
[ -n "$script" ] || fail "worktree 里没有 hello.sh"
[ "$(bash "$script" Aimee)" = "Hello, Aimee!" ] || fail "'hello.sh Aimee' 输出不对: $(bash "$script" Aimee)"
bash "$script" >/dev/null 2>&1 && fail "无参数应以非 0 退出"
assert_file_contains "$sb/projects/$slug/STATUS.md" "阶段: 等待 review"
remote=$(remote_of "$sb")
git -C "$remote" ls-tree -r "project/$slug" --name-only | grep -Eq '(^|/)hello\.sh$' || fail "代码未 push 到 project 分支"
git -C "$remote" ls-tree -r main --name-only | grep -Eq '(^|/)hello\.sh$' && fail "代码不应进 main"
assert_file_contains "$sb/decisions.md" "^### D-[0-9]{3}"
