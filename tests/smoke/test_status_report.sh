#!/usr/bin/env bash
# Progress questions are answered from STATUS.md, including what waits on Aimee.
source "$(dirname "$0")/lib.sh"

sb=$(make_sandbox project-demo)
before=$(git -C "$sb" rev-list --count main)
out=$(run_lead "$sb" "进展怎么样")

assert_contains "$out" "[Dd]emo"
assert_contains "$out" "OCR"
[ "$(git -C "$sb" rev-list --count main)" = "$before" ] || fail "汇报进展不应产生提交"
