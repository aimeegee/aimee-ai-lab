#!/usr/bin/env bash
# Listing ideas is read-only.
source "$(dirname "$0")/lib.sh"

sb=$(make_sandbox idea-photo)
before=$(git -C "$sb" rev-list --count main)
out=$(run_lead "$sb" "我有哪些 idea")

assert_contains "$out" "照片"
[ "$(git -C "$sb" rev-list --count main)" = "$before" ] || fail "列出 idea 不应产生提交"
