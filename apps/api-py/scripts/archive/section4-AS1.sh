#!/usr/bin/env bash
# 밴드 AS1(MARC-TICK-212: 모듈 공통 AI 설정 꼴 — 프롬프트·모델 설정 꼴·받기 검사·모델 설정 sha)의 §4 자기검증(발주서
# band-handoffs/AS1-order.md §4). 틀은 section4-G2c3.sh 그대로다. 순수 층이라 컨테이너를 띄우지 않는다.
#   사용: apps/api-py/scripts/section4-AS1.sh [--step <n>]
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 전량은 감독 몫). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 AS1.out — 심은 파손에도 AS1_OUT 으로 넘긴다), AS1_FORBIDDEN(실재
#   기업명 낱말 파일, 기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
C="$E/core"
OUT="${S4_OUT:-$ROOT/../AS1.out}"
FORBIDDEN="${AS1_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준> b8773ec 에서 잰 수: 순수 = pytest esgapi/core -m "not django_db" 1162. 이 밴드가 더한 것 167(꼴 34 · 규칙 133 — A1 차례 시험 포함).
BASE_PURE=1162
EXPECT_PURE=1329
# 「다」 계약 source 줄: <기준> 47 → 48(esgapi.core.contracts 한 줄).
BASE_PURE_LINES=47
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    *) echo "사용: $0 [--step <n>]" >&2; exit 2 ;;
  esac
done
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 AS1 §4 · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…>
  local n="$1" what="$2" start; shift 2
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then return 0; fi
  echo "── [$n] $what"
  start=$(date +%s)
  "$@"
  local code=$?
  echo "[$n] $what EXIT=$code $(( $(date +%s) - start ))s"
  [ "$code" -eq 0 ] || FAILS=$((FAILS + 1))
}

changed() {  # <기준> 이후 바뀐 파일 + 새 파일(뿌리 기준 경로)
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-1 — 닫힌 목록(+ calc/__init__.py 머리 글 한 줄 — 감독 9a 허락, 보고 ⑤ #4)
ALLOWED="^$C/contracts/(__init__|ai_setting_shapes)\.py\$
^$C/calc/(__init__|ai_settings)\.py\$
^$C/tests/contracts/(__init__|test_ai_setting_shapes)\.py\$
^$C/tests/calc/test_ai_settings\.py\$
^$C/tests/data/ai-setting/[^/]+\.schema\.json\$
^$C/tests/data/ai-setting-examples/[^/]+\.json\$
^$C/__init__\.py\$
^$A/\.importlinter\$
^$A/scripts/(section4|planted-breaks)-AS1\.sh\$"

s1() {
  local all outside pattern
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  [ "$outside" -eq 0 ]
}

# §1-1 「0줄」
ZERO="$E/greenwash $E/dataverify $E/translation $E/runs $E/inventory $E/reference $E/user $E/organization $C/llm
$C/flows $C/permissions.py $E/config $A/generated apps/web $A/pyproject.toml $A/uv.lock $A/tests/security
$A/tests_integration $A/scripts/test-layout-allow.txt"

s2() {
  local missing=0 p n bad
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u)"
  # 마이그레이션: 어느 앱이든 새 파일 0
  bad="$(printf '%s\n%s\n' "$bad" "$(changed | grep '/migrations/')" | grep .)"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -z "$bad" ] && [ "$missing" -eq 0 ]
}

pure_lines() {  # <importlinter 글> → 「다」 source 줄 수
  awk '/contract:pure-modules/{f=1} f&&/^source_modules/{s=1;next} s&&/^forbidden_modules/{exit} s&&/^    esgapi/{n++} END{print n+0}'
}

s3() {
  local before after diffl
  (cd "$A" && uv run --frozen lint-imports 2>&1 | tail -1 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || return 1
  before="$(git show "$BASE:$A/.importlinter" | pure_lines)"
  after="$(pure_lines < "$A/.importlinter")"
  diffl="$(git diff --numstat "$BASE" -- "$A/.importlinter" | awk '{print $1, $2}')"
  echo "  「다」 source 줄 $before → $after · .importlinter 더함·지움 ${diffl:-0 0}"
  [ "$before" = "$BASE_PURE_LINES" ] && [ "$after" = $((BASE_PURE_LINES + 1)) ] && [ "$diffl" = "1 0" ]
}

s4() {
  local log="$OUT/s4-pytest.log" code total
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/core \
    -m "not django_db") > "$log" 2>&1
  code=$?
  total="$(grep -E '^[0-9]+ passed' "$log" | sed -E 's/^([0-9]+) passed.*/\1/')"
  tail -1 "$log" | sed 's/^/  /'
  echo "  기준 $BASE_PURE → 지금 ${total:-?}(기대 $EXPECT_PURE)"
  [ "$code" -eq 0 ] && [ "${total:-0}" -eq "$EXPECT_PURE" ]
}

s5() {  # 계약 0: 다시 뽑은 openapi 가 generated/ 와 바이트 같다
  local d="$OUT/s5-generated" code
  mkdir -p "$d"
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py export_openapi > "$d/openapi.json" 2> "$d/export.err")
  code=$?
  [ "$code" = 0 ] || { tail -3 "$d/export.err"; return "$code"; }
  cmp "$d/openapi.json" "$A/generated/openapi.json"
  code=$?
  echo "  openapi 다시 뽑음 cmp EXIT=$code · generated/ 바뀐 것 $(git diff --name-only "$BASE" -- "$A/generated" | grep -c .)" \
    "· Ai* 구성요소 $(grep -c '"Ai[A-Z][A-Za-z]*": {' "$d/openapi.json")"
  return "$code"
}

s6() {
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py makemigrations --check --dry-run 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s7() {
  local n
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || return 1
  n="$(git diff --name-only "$BASE" -- "$A/scripts/test-layout-allow.txt" | grep -c .)"
  echo "  허용 목록 diff $n"
  [ "$n" = 0 ]
}

s8() {
  local log="$OUT/s8-planted.log"
  AS1_OUT="$OUT" "$A/scripts/planted-breaks-AS1.sh" > "$log" 2>&1
  local code=$?
  grep -E '^\[|^    FAILED|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  [ "$code" -eq 0 ] && [ "$(tail -1 "$log")" = "PLANTED=9/9" ]
}

s9() {
  local log="$OUT/s9-verify-fast.log"
  scripts/verify.sh --fast > "$log" 2>&1
  local code=$?
  tail -1 "$log" | sed 's/^/  /'
  [ "$code" -eq 0 ] && [ "$(tail -1 "$log")" = "VERIFY_FAST=PASS" ]
}

s10() {
  local all keys bin words body msg
  all="$(changed)"
  body="$(for f in $all; do
    if git cat-file -e "$BASE:$f" 2>/dev/null; then git diff "$BASE" -- "$f" | grep -E '^\+' | grep -v -E '^\+\+\+ ';
    elif [ -f "$f" ]; then sed "s|^|+$f:|" "$f"; fi; done)"
  msg="$(git log --format=%B "$BASE..HEAD")"
  keys="$(printf '%s\n%s\n' "$body" "$msg" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-AS1\.sh:" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY=[^[:space:]"$]')"
  bin="$(echo "$all" | grep -c -E '\.(pdf|xlsx|ipynb)$')"
  if [ -f "$FORBIDDEN" ]; then
    words="$(printf '%s\n%s\n' "$body" "$msg" | grep -c -i -F -f "$FORBIDDEN")"
  else
    words="파일 없음"
  fi
  echo "  키 꼴 $keys · pdf/xlsx/ipynb $bin · 실재 기업명(더한 줄·커밋 메시지) $words"
  [ "$keys" -eq 0 ] && [ "$bin" -eq 0 ] && [ "$words" = 0 ]
}

step 1 "바뀐 파일이 §1-1 안" s1
step 2 "0줄 자리·마이그레이션 diff 0" s2
step 3 "lint-imports 전부 KEPT · 「다」 source 47 → 48" s3
step 4 "pytest esgapi/core(순수) 초록, 수" s4
step 5 "generated/ 다시 뽑아 cmp 차이 0" s5
step 6 "makemigrations --check(모든 앱)" s6
step 7 "테스트 자리 검사·허용 목록 diff 0" s7
step 8 "심은 파손 PLANTED=9/9" s8
step 9 "verify.sh --fast" s9
step 10 "키 꼴·바이너리·실재 기업명 0" s10
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
