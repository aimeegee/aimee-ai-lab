#!/usr/bin/env bash
# install.sh links the /lead skill into ~/.claude/skills and is safe to run twice.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail() { echo "FAIL: $*" >&2; exit 1; }

home=$(mktemp -d)
HOME="$home" bash "$ROOT/scripts/install.sh" >/dev/null || fail "第一次安装失败"
HOME="$home" bash "$ROOT/scripts/install.sh" >/dev/null || fail "第二次安装失败"

link="$home/.claude/skills/lead"
[ -L "$link" ] || fail "$link 不是 symlink"
[ "$(readlink "$link")" = "$ROOT/skill/lead" ] || fail "symlink 指向 $(readlink "$link")"
[ -r "$link/SKILL.md" ] || fail "SKILL.md 不可读"
echo PASS
