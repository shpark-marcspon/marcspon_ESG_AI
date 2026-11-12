#!/usr/bin/env bash
# 밴드 TRD2(MARC-TICK-373: 영문번역 PDF 입력 ② — 흐름 translation.pdf@158·결과 translation.layout@1, 결정 MARC-ENT-471)의
# §4 자기검증(발주서 band-handoffs/TRD2-order.md §2·§4 — section4-TRP6.sh 꼴).
#   사용: apps/api-py/scripts/section4-TRD2.sh [--with-containers] [--planted] [--msg <파일>] [--step <n>]
#   --with-containers 면 단계 6(업무 — 이 워크트리의 compose postgres 하나)을 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다).
#   --planted 면 단계 7(planted-breaks-TRD2.sh --commit 3). --msg 면 단계 10(커밋 메시지 초안의 트레일러).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env 키 지움).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 TRD2.out/s4), TRD2_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
T="$E/translation"
P=services/parser
OUT="${S4_OUT:-$ROOT/../TRD2.out/s4}"
FORBIDDEN="${TRD2_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
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
echo "── 밴드 TRD2 §4 · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# §2-1(영문번역 땅)·§2-2(H — services/parser·core 의 허락 줄)·§2-3(D1·D2) 의 닫힌 목록
ALLOWED="^($P/(docparse|tests|scripts)/|$P/README\.md$\
|$E/core/resources/(parser|ports/parser)\.py$|$E/core/tests/(resource_fakes|test_parser_port)\.py$\
|$T/tools/pdf_tags\.py$|$T/tests/tools/test_pdf_tags\.py$\
|$T/flows/(pdf_158|binding_pdf_158|registration|colab_158)\.py$|$T/apps\.py$|$T/contracts/layout_shapes\.py$\
|$T/tests/(flows|contracts)/|$T/tests/data/flow-shapes/translation\.layout@1\.schema\.json$\
|$T/tests/service/actions/test_bundle_carrier\.py$\
|$A/scripts/(section4|planted-breaks)-TRD2\.sh$|$A/tests_integration/test_translation_pdf_flow\.py$)"

s1() {
  local all outside
  all="$(changed)"
  outside="$(echo "$all" | grep -v -E "$ALLOWED" | grep -c .)"
  echo "  바뀐 경로 $(echo "$all" | grep -c .) · OUTSIDE=$outside"
  echo "$all" | grep -v -E "$ALLOWED" | sed 's/^/  ★ /'
  [ "$outside" = 0 ]
}

# §2-1 0줄 목록 + 기존 고정 파일(result@1·input@1·digest@1·options) 바이트 0
ZERO=("$T/engines" "$T/contracts/shapes.py" "$T/contracts/options_shapes.py" "$T/contracts/digest_shapes.py"
  "$T/contracts/wire.py" "$T/outputs" "$T/service" "$T/flows/binding_158.py" "$T/migrations" "$T/models.py"
  "$A/generated" "$A/.importlinter" compose.yaml docker apps/web "$E/runs" "$E/config"
  "$T/tests/data/flow-shapes/translation.result@1.schema.json" "$T/tests/data/flow-shapes/translation.input@1.schema.json"
  "$T/tests/data/flow-shapes/translation.digest@1.schema.json" "$T/tests/data/flow-shapes/options"
  "$T/tests/data/flow-shapes/ai-setting")

s2() {
  local n plus minus
  n="$(git diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)"
  n=$((n + $(git ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)))
  echo "  0줄 목록 바뀐 파일 $n"
  git diff --name-only "$BASE" -- "${ZERO[@]}" | sed 's/^/  ★ /'
  [ "$n" = 0 ] || return 1
  # colab_158.py 는 별칭 두 줄 더하기만(§2-1)
  read -r plus minus _ <<< "$(git diff --numstat "$BASE" -- "$T/flows/colab_158.py")"
  echo "  colab_158.py +${plus:-0}/-${minus:-0}(기대 +2/-0)"
  [ "${plus:-0}" = 2 ] && [ "${minus:-0}" = 0 ]
}

s3() {
  (cd "$A" && uv run --frozen lint-imports) > "$OUT/s3-imports.log" 2>&1
  local code=$?
  grep -E "Contracts:" "$OUT/s3-imports.log" | sed 's/^/  /'
  return $code
}

s4() {  # 순수 시험(영문번역 전부 + core 파서 포트)
  (cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db" \
    esgapi/translation esgapi/core/tests/test_parser_port.py) > "$OUT/s4-pure.log" 2>&1
  local code=$?
  tail -1 "$OUT/s4-pure.log" | sed 's/^/  /'
  return $code
}

s5() {
  local code=0
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py) > "$OUT/s5-layout.log" 2>&1 || code=1
  tail -1 "$OUT/s5-layout.log" | sed 's/^/  layout /'
  (cd "$A" && uv run --frozen pyright esgapi/translation esgapi/core tests_integration/test_translation_pdf_flow.py) \
    > "$OUT/s5-pyright.log" 2>&1 || code=1
  tail -1 "$OUT/s5-pyright.log" | sed 's/^/  pyright /'
  (cd "$A" && uv run --frozen ruff check . && uv run --frozen ruff format --check .) > "$OUT/s5-ruff.log" 2>&1 || code=1
  tail -1 "$OUT/s5-ruff.log" | sed 's/^/  ruff /'
  bash -n "$A/scripts/planted-breaks-TRD2.sh" && /bin/bash -n "$A/scripts/section4-TRD2.sh" || code=1
  return $code
}

s6() {  # 업무 층(django_db — compose postgres)
  (cd "$A" && scripts/test-business.sh -p no:cacheprovider -n 4 esgapi/translation esgapi/runbundle esgapi/runs) \
    > "$OUT/s6-business.log" 2>&1
  local code=$?
  tail -1 "$OUT/s6-business.log" | sed 's/^/  /'
  return $code
}

s7() {
  (cd "$A" && scripts/planted-breaks-TRD2.sh --commit 3) > "$OUT/s7-planted.log" 2>&1
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
  { git diff "$BASE" -- . ":(exclude)$A/scripts/section4-TRD2.sh"
    git ls-files -o --exclude-standard --full-name | grep -v -x "$A/scripts/section4-TRD2.sh" \
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
  for t in "Ticket: MARC-TICK-373" "Concerns: MARC-ISSUE-422" "Derives-from: MARC-ENT-471" \
    "Constraint: 엔진 0줄" "Rejected: 같은 흐름에 input kind 옵션" "Rejected: result@1 에 블록 칸" "Directive:" \
    "Co-Authored-By:"; do
    grep -q -F "$t" "$MSG" || { echo "  ★ 없음: $t"; code=1; }
  done
  [ "$code" = 0 ] && echo "  트레일러 다 있음"
  return $code
}

step 1 "바뀐 경로가 §2 안(OUTSIDE=0)" s1
step 2 "0줄 목록·기존 고정 파일 diff 0 · colab_158.py +2/-0" s2
step 3 "lint-imports 전부 KEPT" s3
step 4 "순수 시험 초록(영문번역 · core 파서 포트)" s4
step 5 "check_test_layout·pyright·ruff·bash -n" s5
if [ "$CONTAINERS" = 1 ]; then step 6 "업무 시험(translation·runbundle·runs)" s6
else not_run 6 "업무 시험" "--with-containers 없음"; fi
if [ "$PLANTED" = 1 ]; then step 7 "심은 파손 --commit 3" s7
else not_run 7 "심은 파손" "--planted 없음"; fi
step 8 "뿌리 verify.sh --fast" s8
step 9 "추가 줄의 키 꼴·자료 파일·실재 기업명 0" s9
if [ -n "$MSG" ]; then step 10 "커밋 메시지 트레일러" s10
else not_run 10 "커밋 메시지 트레일러" "--msg 없음"; fi
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
