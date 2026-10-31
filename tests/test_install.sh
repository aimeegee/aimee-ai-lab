#!/usr/bin/env bash
# install.sh links the /team skill into ~/.claude/skills and is safe to run twice.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail() { echo "FAIL: $*" >&2; exit 1; }

home=$(mktemp -d)
# A pre-rename install left a `lead` link pointing into this repo; install.sh should clear it.
mkdir -p "$home/.claude/skills"
ln -s "$ROOT/skill/lead" "$home/.claude/skills/lead"
HOME="$home" bash "$ROOT/scripts/install.sh" >/dev/null || fail "第一次安装失败"
HOME="$home" bash "$ROOT/scripts/install.sh" >/dev/null || fail "第二次安装失败"

link="$home/.claude/skills/team"
[ -L "$link" ] || fail "$link 不是 symlink"
[ "$(readlink "$link")" = "$ROOT/skill/team" ] || fail "symlink 指向 $(readlink "$link")"
[ -r "$link/SKILL.md" ] || fail "SKILL.md 不可读"
grep -q '^name: team$' "$link/SKILL.md" || fail "SKILL.md 的 name 不是 team"
[ ! -e "$home/.claude/skills/lead" ] && [ ! -L "$home/.claude/skills/lead" ] || fail "旧的 lead 链接没有清掉"
echo PASS
