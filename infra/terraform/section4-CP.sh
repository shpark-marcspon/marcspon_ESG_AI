#!/usr/bin/env bash
# 밴드 CP 의 §4: terraform compute 를 api-py 기준으로 다시 쓸 때까지 막았는가(MARC-TICK-115).
#
#   infra/terraform/section4-CP.sh                 커밋 전
#   infra/terraform/section4-CP.sh --after-commit  커밋 뒤(+ 작업 트리가 깨끗한가)
#
# 항목마다 EXIT=<종료 코드> 줄을 찍는다. 전부 0 이면 마지막 줄이 EXIT=0 이다.
# 실제 AWS 에 닿지 않는다(bin/tf 는 자격 증명을 넘기지 않는다). 뿌리 scripts/verify.sh 는 --fast 만 돌린다.
# macOS 의 /bin/bash 3.2 에서 돈다.
set -uo pipefail

BASE="fcac871"
after_commit=0
case "${1:-}" in
  "") ;;
  --after-commit) after_commit=1 ;;
  *)
    echo "사용법: $0 [--after-commit]"
    exit 2
    ;;
esac

tf_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$tf_dir/../.." && pwd)"
cd "$repo" || exit 1
overall=0
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

result() {
  # result "<제목>" <코드>
  echo "EXIT=$2  ($1)"
  if [ "$2" -ne 0 ]; then overall=1; fi
}

# ── 1. infra/terraform/verify.sh 전체 ───────────────────────────────────────
echo "── 1. infra/terraform/verify.sh"
infra/terraform/verify.sh >"$tmp/verify.log" 2>&1
code=$?
grep -E '^(── |EXIT=|Failure!|Success!)|\.\.\. fail' "$tmp/verify.log"
result "1. verify.sh 전체" "$code"

# ── 2. 새 run 다섯이 있고 통과 ───────────────────────────────────────────────
# 1 이 init 을 해 두었다(.terraform). test 는 네트워크 없이 돈다.
echo
echo "── 2. compute.tftest.hcl 의 막기 run 다섯"
infra/terraform/bin/tf -chdir=envs/practice test -no-color -filter=tests/compute.tftest.hcl >"$tmp/compute.log" 2>&1
code=$?
grep -E 'run "|Failure!|Success!' "$tmp/compute.log"
for name in compute_block_default_has_no_compute compute_block_rejects_open_cidr \
  compute_block_rejects_missing_certificate compute_block_http_listener_only_redirects \
  compute_block_https_listener_uses_certificate; do
  if ! grep -qE "run \"$name\"\.\.\. pass" "$tmp/compute.log"; then
    echo "통과한 run 이 아니다(없거나 실패): $name"
    code=1
  fi
done
if grep -q 'container_env_names_match_compose' infra/terraform/envs/practice/tests/compute.tftest.hcl; then
  echo "compose 의 TS 서비스를 대조하던 run 이 남아 있다."
  code=1
fi
result "2. 새 run 다섯 통과" "$code"

# ── 3. 0.0.0.0/0 이 envs 의 기본값으로 없다 ──────────────────────────────────
# 테스트(tests/)와 검증 문(validation 의 condition·error_message, description)에만 나와야 한다.
echo
echo "── 3. envs 의 0.0.0.0/0"
code=0
git grep -n "0\.0\.0\.0/0" -- infra/terraform/envs >"$tmp/grep.txt"
cat "$tmp/grep.txt"
odd="$(grep -v '/tests/' "$tmp/grep.txt" | grep -vE ':[[:space:]]*(condition|error_message|description)[[:space:]]*=' || true)"
if [ -n "$odd" ]; then
  echo "테스트·검증 문 밖에 0.0.0.0/0 이 있다:"
  echo "$odd"
  code=1
fi
result "3. 0.0.0.0/0 기본값 없음" "$code"

# ── 4. 허용 경로 밖 diff 0 ──────────────────────────────────────────────────
echo
echo "── 4. 허용 경로 밖 diff (기준 $BASE)"
{
  git diff --name-only "$BASE" --
  git ls-files --others --exclude-standard
} | sort -u >"$tmp/changed.txt"
cat "$tmp/changed.txt"
outside="$(grep -vE '^(infra/terraform/envs/practice/|infra/terraform/modules/compute/|infra/README\.md$|infra/terraform/section4-CP\.sh$)' "$tmp/changed.txt" || true)"
code=0
if [ -n "$outside" ]; then
  echo "허용 경로 밖에서 바뀐 것:"
  echo "$outside"
  code=1
fi
result "4. 허용 경로 밖 diff 0" "$code"

# ── 5. 뿌리 빠른 게이트 ──────────────────────────────────────────────────────
echo
echo "── 5. scripts/verify.sh --fast"
PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast >"$tmp/fast.log" 2>&1
last="$(tail -n 1 "$tmp/fast.log")"
echo "$last"
code=0
if [ "$last" != "VERIFY_FAST=PASS" ]; then
  grep -E 'EXIT=[1-9]' "$tmp/fast.log" | head -20
  code=1
fi
result "5. VERIFY_FAST=PASS" "$code"

# ── 6. (--after-commit) 작업 트리가 깨끗하다 ─────────────────────────────────
if [ "$after_commit" -eq 1 ]; then
  echo
  echo "── 6. git status --porcelain"
  status="$(git status --porcelain)"
  code=0
  if [ -n "$status" ]; then
    echo "$status"
    code=1
  fi
  result "6. git status --porcelain 0" "$code"
fi

echo
echo "EXIT=$overall"
exit "$overall"
