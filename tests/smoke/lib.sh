# Shared helpers for smoke tests. Each test sources this file.
# Smoke tests drive a real `claude -p` session inside a throwaway sandbox repo
# whose `origin` is a local bare repo, so nothing touches GitHub.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_SUFFIX='(非交互测试:所有 subagent 在前台运行并等待完成后再结束本轮;环境没有 GitHub,需要 gh 的步骤改为把命令打印出来。)'
ALLOWED_TOOLS=(Read Write Edit Glob Grep Agent Task "Bash(git *)" "Bash(mkdir *)" "Bash(ls *)" "Bash(date *)" "Bash(cat *)" "Bash(chmod *)" "Bash(bash *)" "Bash(./*)")

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_file_contains() {
  [ -f "$1" ] || fail "文件不存在: $1"
  grep -Eq -- "$2" "$1" || fail "$1 不包含 /$2/"
}

assert_contains() {
  printf '%s' "$1" | grep -Eq -- "$2" || fail "输出不包含 /$2/"
}

make_sandbox() {
  local root sb
  root="$(mktemp -d "${TMPDIR:-/tmp}/aimee-lab-smoke.XXXXXX")"
  sb="$root/repo"
  # docs/ and tests/ spell out the expected behavior; leaving them in would let
  # the sandboxed lead pass by reading the plan instead of team/ rules.
  rsync -a --exclude .git --exclude .worktrees --exclude .superpowers \
    --exclude /docs --exclude /tests "$REPO_ROOT/" "$sb/"
  if [ -n "${1:-}" ]; then
    rsync -a "$REPO_ROOT/tests/smoke/fixtures/$1/" "$sb/"
  fi
  git init -q --bare -b main "$root/remote.git"
  (
    cd "$sb" &&
      git init -q -b main &&
      git add -A &&
      git -c user.name=smoke -c user.email=smoke@example.com commit -qm "sandbox init" &&
      git remote add origin "$root/remote.git" &&
      git push -q -u origin main
  ) >/dev/null 2>&1 || fail "sandbox 初始化失败"
  echo "$sb"
}

remote_of() {
  echo "$1/../remote.git"
}

run_lead() {
  local sb="$1" prompt="$2"
  (cd "$sb" && claude -p "$prompt

$TEST_SUFFIX" --allowedTools "${ALLOWED_TOOLS[@]}") >"$sb/../out.txt" 2>&1
  if grep -Eq "Failed to authenticate|Invalid API key|Please run /login" "$sb/../out.txt"; then
    fail "claude CLI 未登录,先在终端运行 claude 并 /login"
  fi
  if grep -Eq "hit your .*limit|usage credits" "$sb/../out.txt"; then
    fail "claude 用量上限,不是测试本身失败"
  fi
  cat "$sb/../out.txt"
}
