#!/usr/bin/env bash
# When another session already pushed to main, the lead rebases instead of losing either change.
source "$(dirname "$0")/lib.sh"

sb=$(make_sandbox)
other="$sb/../other"
git clone -q "$(remote_of "$sb")" "$other"
echo "remote-change" >>"$other/README.md"
git -C "$other" -c user.name=smoke -c user.email=smoke@example.com commit -qam "remote change"
git -C "$other" push -q origin main

run_lead "$sb" "记一下,我想做个自动整理手机照片的工具,还没想好细节" >/dev/null

remote=$(remote_of "$sb")
git -C "$remote" show main:README.md | grep -q "remote-change" || fail "另一方的改动丢了"
git -C "$remote" show main:ideas.md | grep -q "照片" || fail "idea 未 push 到 main"
