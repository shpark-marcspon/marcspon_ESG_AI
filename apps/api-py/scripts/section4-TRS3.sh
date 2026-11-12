#!/usr/bin/env bash
# 밴드 TRS3(MARC-TICK-377: 영문번역 PDF 서버 길 — 묶음 줄 흐름 종류·layout@1 읽기 경로·실패 쪽만 다시의 흐름 거름, 결정
# MARC-ENT-471 ③)의 §4 자기검증(발주서 band-handoffs/TRS3-order.md §2·§4 — section4-TRD2.sh 꼴).
#   사용: apps/api-py/scripts/section4-TRS3.sh [--with-containers] [--planted] [--msg <파일>] [--step <n>]
#   --with-containers 면 단계 6(업무·보안 — 이 워크트리의 compose postgres 하나, 웹 e2e 한 벌)을 돈다 — 안 주면 「안 돌림」
#   (EXIT=1 로 센다). --planted 면 단계 7(planted-breaks-TRS3.sh --commit 3). --msg 면 단계 10(커밋 메시지 초안의 트레일러).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env 키 지움).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 TRS3.out/s4), TRS3_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
T="$E/translation"
W=apps/web
WS="$W/src/entities/translation"
OUT="${S4_OUT:-$ROOT/../TRS3.out/s4}"
FORBIDDEN="${TRS3_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
unset OPENAI_API_KEY LLM_OPENAI_API_KEY LLM_ANTHROPIC_API_KEY LLM_GEMINI_API_KEY ANTHROPIC_API_KEY
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0; PLANTED=0; MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:-}"; shift 2 ;;
    *) echo "사용: $0 [--with-containers] [--planted] [--msg <파일>] [--step <n>]" >&2; exit 2 ;;
  esac
done
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 TRS3 §4 · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

not_run() {  # <n> <설명> <까닭>
  if [ -n "$ONLY" ] && [ "$ONLY" != "$1" ]; then return 0; fi
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}

changed() {  # <기준> 뒤 바뀐 경로(추적 diff + 추적 안 된 새 파일)
  { git diff --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §2-1(영문번역 땅·웹 거울)·§2-2(H1~H8)·§2-3(D1~D4·F1) 의 닫힌 목록
ALLOWED="^($T/contracts/(batch_shapes|layout_shapes)\.py$|$T/service/actions/(batches|layout|retry_source)\.py$\
|$T/service/apis/translation\.py$|$T/apps\.py$|$T/tests/\
|$E/core/permissions\.py$|$E/core/tests/(test_permissions|test_permissions_wiring|test_transaction_rules)\.py$\
|$E/config/tests/(test_api_contract|test_api_errors)\.py$|$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$\
|docs/development\.md$|$A/tests/security/(test_tenant_paths|test_login|test_operator_company|test_translation)\.py$\
|$A/scripts/(section4|planted-breaks)-TRS3\.sh$\
|$WS/api/contract/(batch|contract\.test)\.ts$|$WS/model/(batch|adapt\.test)\.ts$|$WS/api/testing\.ts$\
|$W/e2e/translation-server\.ts$)"

s1() {
  local all outside
  all="$(changed)"
  outside="$(echo "$all" | grep -v -E "$ALLOWED" | grep -c .)"
  echo "  바뀐 경로 $(echo "$all" | grep -c .) · OUTSIDE=$outside"
  echo "$all" | grep -v -E "$ALLOWED" | sed 's/^/  ★ /'
  [ "$outside" = 0 ]
}

# F0 + §2-1 「0줄」 + 기존 고정 파일(result@1·digest@1·options) 바이트 0
ZERO=("$T/engines" "$T/flows" "$T/tools" "$T/outputs" "$T/contracts/shapes.py" "$T/contracts/options_shapes.py"
  "$T/contracts/digest_shapes.py" "$T/contracts/wire.py" "$T/contracts/pages_shapes.py" "$T/models.py" "$T/migrations"
  "$E/runs" "$E/greenwash" "$A/.importlinter" "$E/config/api.py" compose.yaml docker services/parser
  "$A/tests/security/conftest.py" "$A/tests/security/seed.py" "$A/conftest.py" "$A/tests/support" "$A/tests_integration"
  "$T/tests/data/flow-shapes/translation.result@1.schema.json" "$T/tests/data/flow-shapes/translation.digest@1.schema.json"
  "$T/tests/data/flow-shapes/options")

s2() {
  local n
  n="$(git diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)"
  n=$((n + $(git ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)))
  echo "  0줄 목록 바뀐 파일 $n"
  git diff --name-only "$BASE" -- "${ZERO[@]}" | sed 's/^/  ★ /'
  [ "$n" = 0 ]
}

s3() {
  (cd "$A" && uv run --frozen lint-imports) > "$OUT/s3-imports.log" 2>&1
  local code=$?
  grep -E "Contracts:" "$OUT/s3-imports.log" | sed 's/^/  /'
  return $code
}

s4() {  # 순수 시험(영문번역·core·config — 직렬: -n 4 에서 test_system_check 가 흔들림, ① 검증 권고) + 웹 계약 시험
  local code=0
  (cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db" esgapi/translation esgapi/core esgapi/config) \
    > "$OUT/s4-pure.log" 2>&1 || code=1
  tail -1 "$OUT/s4-pure.log" | sed 's/^/  pure /'
  (cd "$W" && pnpm exec vitest run src/entities/translation && pnpm exec tsc --noEmit) > "$OUT/s4-web.log" 2>&1 || code=1
  grep -E "Tests +[0-9]" "$OUT/s4-web.log" | tail -1 | sed 's/^/  web /'
  return $code
}

s5() {
  local code=0
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py) > "$OUT/s5-layout.log" 2>&1 || code=1
  tail -1 "$OUT/s5-layout.log" | sed 's/^/  layout /'
  (cd "$A" && uv run --frozen pyright) > "$OUT/s5-pyright.log" 2>&1 || code=1
  tail -1 "$OUT/s5-pyright.log" | sed 's/^/  pyright /'
  (cd "$A" && uv run --frozen ruff check . && uv run --frozen ruff format --check .) > "$OUT/s5-ruff.log" 2>&1 || code=1
  tail -1 "$OUT/s5-ruff.log" | sed 's/^/  ruff /'
  bash -n "$A/scripts/planted-breaks-TRS3.sh" && /bin/bash -n "$A/scripts/section4-TRS3.sh" || code=1
  return $code
}

s6() {  # 업무 층(-n 4) · 보안 층(직렬 — 스크립트가 -n 을 받지 않음) · 웹 e2e 한 벌(영문번역 서버 모의)
  local code=0 port
  (cd "$A" && scripts/test-business.sh -p no:cacheprovider -n 4 esgapi/translation esgapi/runbundle esgapi/runs \
    esgapi/core esgapi/config) > "$OUT/s6-business.log" 2>&1 || code=1
  tail -1 "$OUT/s6-business.log" | sed 's/^/  business /'
  (cd "$A" && scripts/test-security.sh -p no:cacheprovider tests/security) > "$OUT/s6-security.log" 2>&1 || code=1
  tail -1 "$OUT/s6-security.log" | sed 's/^/  security /'
  port="$(sed -n 's/^WEB_PORT=//p' .env | tail -1)"
  (cd "$W" && WEB_TEST_PORT="${port:-15174}" pnpm exec playwright test e2e/translation-server.spec.ts) \
    > "$OUT/s6-e2e.log" 2>&1 || code=1
  grep -E "[0-9]+ (passed|failed)" "$OUT/s6-e2e.log" | tail -2 | sed 's/^/  e2e /'
  return $code
}

s7() {
  (cd "$A" && scripts/planted-breaks-TRS3.sh --commit 3) > "$OUT/s7-planted.log" 2>&1
  local code=$?
  grep -E "^(PLANTED|FINGERPRINT)=" "$OUT/s7-planted.log" | sed 's/^/  /'
  return $code
}

s8() {
  local log
  log="$(scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s8-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

s9() {
  local d="$OUT/s9.diff" n_key n_bin n_name=0
  # 이 스크립트 자신은 무늬를 글자로 싣는다 — 뺀다
  { git diff "$BASE" -- . ":(exclude)$A/scripts/section4-TRS3.sh"
    git ls-files -o --exclude-standard --full-name | grep -v -x "$A/scripts/section4-TRS3.sh" \
      | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|marcspon-openai|spike/\.env')"
  n_bin="$(changed | grep -c -E '\.(xlsx|csv|ipynb|docx|pdf)$')"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴·키 자리 $n_key · .xlsx/.csv/.ipynb/.docx/.pdf $n_bin · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_name" = 0 ]
}

s10() {
  local code=0 t
  [ -f "$MSG" ] || { echo "  ★ 메시지 파일이 없다: $MSG"; return 1; }
  for t in "Ticket: MARC-TICK-377" "Derives-from: MARC-ENT-471" "Concerns: MARC-ISSUE-429" \
    "Constraint: 흐름·엔진 0줄" "Rejected: colab_158 _retry_check 에 흐름 비교" "Co-Authored-By:"; do
    grep -q -F "$t" "$MSG" || { echo "  ★ 없음: $t"; code=1; }
  done
  [ "$code" = 0 ] && echo "  트레일러 다 있음"
  return $code
}

step 1 "바뀐 경로가 §2 안(OUTSIDE=0)" s1
step 2 "F0 — 0줄 목록·기존 고정 파일 diff 0" s2
step 3 "lint-imports 전부 KEPT" s3
step 4 "순수 시험(영문번역·core·config) · 웹 계약 시험·tsc" s4
step 5 "check_test_layout·pyright·ruff·bash -n" s5
if [ "$CONTAINERS" = 1 ]; then step 6 "업무·보안 시험 · e2e translation-server 한 벌" s6
else not_run 6 "업무·보안 시험" "--with-containers 없음"; fi
if [ "$PLANTED" = 1 ]; then step 7 "심은 파손 --commit 3" s7
else not_run 7 "심은 파손" "--planted 없음"; fi
step 8 "뿌리 verify.sh --fast" s8
step 9 "추가 줄의 키 꼴·자료 파일·실재 기업명 0" s9
if [ -n "$MSG" ]; then step 10 "커밋 메시지 트레일러" s10
else not_run 10 "커밋 메시지 트레일러" "--msg 없음"; fi
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
