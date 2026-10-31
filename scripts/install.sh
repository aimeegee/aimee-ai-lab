#!/usr/bin/env bash
# Links the global /team skill into ~/.claude/skills. Safe to run repeatedly.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS="$HOME/.claude/skills"
mkdir -p "$SKILLS"
# The skill used to be called /lead; drop that link if it points into this repo.
if [ -L "$SKILLS/lead" ] && [ "$(readlink "$SKILLS/lead")" = "$ROOT/skill/lead" ]; then
  rm "$SKILLS/lead"
fi
ln -sfn "$ROOT/skill/team" "$SKILLS/team"
echo "已安装: $SKILLS/team -> $ROOT/skill/team"
