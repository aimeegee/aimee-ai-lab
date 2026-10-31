#!/usr/bin/env bash
# Static check of team/roster.md and the role files it points to.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROSTER="$ROOT/team/roster.md"

fail() { echo "FAIL: $*" >&2; exit 1; }
[ -f "$ROSTER" ] || fail "缺少 team/roster.md"

trim() { local s="${1//\`/}"; s="${s#"${s%%[![:space:]]*}"}"; echo "${s%"${s##*[![:space:]]}"}"; }

rows=$(grep -E '^\|' "$ROSTER" | grep -vE '^\|[[:space:]]*角色[[:space:]]*\|' | grep -vE '^\|[[:space:]:-]+\|')
[ "$(printf '%s\n' "$rows" | grep -c .)" = 4 ] || fail "花名册应恰好 4 行"

# macOS ships bash 3.2, which has no associative arrays.
expected_model() {
  case "$1" in
    Lead) echo session ;; PO/BA) echo opus ;; Engineer) echo sonnet ;; Tester) echo sonnet ;;
    *) echo "" ;;
  esac
}
while IFS='|' read -r _ role executor model file _; do
  role=$(trim "$role"); executor=$(trim "$executor"); model=$(trim "$model"); file=$(trim "$file")
  want=$(expected_model "$role")
  [ -n "$want" ] || fail "未知角色: $role"
  [ "$executor" = claude ] || fail "$role 执行者应为 claude,实际 $executor"
  [[ "$model" =~ ^(opus|sonnet|haiku|session)$ ]] || fail "$role 模型不合法: $model"
  [ "$model" = "$want" ] || fail "$role 默认模型应为 $want,实际 $model"
  [ -f "$ROOT/$file" ] || fail "$role 角色文件不存在: $file"
  if [ "$role" != Lead ]; then
    for h in "## 职责" "## 不做" "## 回报格式"; do
      grep -q "^$h" "$ROOT/$file" || fail "$file 缺少 $h"
    done
  fi
done <<<"$rows"

# Roles that run things must stop at the must-ask categories and report them.
for f in team/roles/engineer.md team/roles/tester.md; do
  [ "$(grep -c "五类必问" "$ROOT/$f")" -ge 2 ] || fail "$f 应在「不做」和「回报格式」里都提到五类必问"
done
echo PASS
