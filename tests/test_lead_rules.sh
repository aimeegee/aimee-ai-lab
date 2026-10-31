#!/usr/bin/env bash
# Static checks on team/lead.md for steps whose order matters.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LEAD="$ROOT/team/lead.md"
fail() { echo "FAIL: $*" >&2; exit 1; }

# gh cannot delete a local branch that a worktree still has checked out.
remove_at=$(grep -bo "git worktree remove" "$LEAD" | head -1 | cut -d: -f1)
delete_at=$(grep -bo -- "--delete-branch" "$LEAD" | head -1 | cut -d: -f1)
[ -n "$remove_at" ] && [ -n "$delete_at" ] || fail "lead.md 缺少 worktree remove 或 --delete-branch"
[ "$remove_at" -lt "$delete_at" ] || fail "应先 git worktree remove 再 gh pr merge --delete-branch"
echo PASS
