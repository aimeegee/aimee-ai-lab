#!/usr/bin/env bash
# Aimee's answer is logged as her decision and distilled into a reusable preference.
source "$(dirname "$0")/lib.sh"

sb=$(make_sandbox project-demo)
run_lead "$sb" "demo 的付费 OCR 问题:不用付费的,用免费开源方案。我一般都倾向先用免费的。这次只记录决定,先不用继续推进。" >/dev/null

assert_file_contains "$sb/decisions.md" "OCR"
assert_file_contains "$sb/decisions.md" "决定者: Aimee"
assert_file_contains "$sb/boss-preferences.md" "^### P-[0-9]{3}"
grep -A20 "待 Aimee 决定" "$sb/projects/demo/STATUS.md" | grep -q "OCR" && fail "已决定的事应从「待 Aimee 决定」移除"
git -C "$(remote_of "$sb")" show main:decisions.md | grep -q "OCR" || fail "决策未 push 到 main"
