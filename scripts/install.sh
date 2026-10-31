#!/usr/bin/env bash
# Links the global /lead skill into ~/.claude/skills. Safe to run repeatedly.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HOME/.claude/skills"
ln -sfn "$ROOT/skill/lead" "$HOME/.claude/skills/lead"
echo "已安装: $HOME/.claude/skills/lead -> $ROOT/skill/lead"
