#!/usr/bin/env bash
# Shared-file commits work while another role has uncommitted edits in the main checkout and
# main is behind origin: the idea lands, the WIP edit is neither lost nor swept into the commit.
source "$(dirname "$0")/lib.sh"

sb=$(make_sandbox project-demo)
echo "# Demo 需求" >"$sb/projects/demo/requirements.md"
git -C "$sb" add projects/demo/requirements.md
git -C "$sb" -c user.name=smoke -c user.email=smoke@example.com commit -qm "requirements"
git -C "$sb" push -q origin main

other="$sb/../other"
git clone -q "$(remote_of "$sb")" "$other"
echo "remote-change" >>"$other/README.md"
git -C "$other" -c user.name=smoke -c user.email=smoke@example.com commit -qam "remote change"
git -C "$other" push -q origin main

echo "WIP by PO/BA" >>"$sb/projects/demo/requirements.md"

run_lead "$sb" "记一下,我想做个自动整理手机照片的工具,还没想好细节" >/dev/null

remote=$(remote_of "$sb")
git -C "$remote" show main:ideas.md | grep -q "照片" || fail "idea 未 push 到 main"
git -C "$remote" show main:README.md | grep -q "remote-change" || fail "另一方的改动丢了"
git -C "$remote" show main:projects/demo/requirements.md | grep -q "WIP by PO/BA" && fail "别人的未完成改动被一起提交了"
grep -q "WIP by PO/BA" "$sb/projects/demo/requirements.md" || fail "别人的未完成改动丢了"
[ ! -d "$sb/.git/rebase-merge" ] && [ ! -d "$sb/.git/rebase-apply" ] || fail "仓库停在 rebase 中间"
