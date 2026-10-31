#!/usr/bin/env bash
# Runs every smoke test in sequence. Each one calls `claude -p` and costs tokens.
cd "$(dirname "$0")" || exit 1
passed=0
failed=0
failures=()
for t in test_*.sh; do
  echo "== $t"
  if bash "$t"; then
    echo "   PASS"
    passed=$((passed + 1))
  else
    echo "   FAIL"
    failed=$((failed + 1))
    failures+=("$t")
  fi
done
echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ] || { printf 'failed: %s\n' "${failures[@]}"; exit 1; }
