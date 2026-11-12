#!/usr/bin/env bash
# 밴드 S3K2a(MARC-TICK-472: Scope 3 연도 상태 · 카테고리 잠금(핀) · 대시보드 Scope 3 칸)의 §4 자기검증
# (발주서 band-handoffs/S3K2a-order.md §4). 틀은 section4-S12b-1.sh(줄여서).
#   사용: apps/api-py/scripts/section4-S3K2a.sh --commit <1|2> [--with-containers] [--step <n>]
#   --with-containers 면 [6] 업무·보안 층 · [7] 심은 고장을 돈다(이 워크트리의 compose postgres 가 떠 있어야 한다).
#   안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
#   .git/verify.lock 이 있으면 시험을 돌리는 단계([5]~[8]·[10]) 앞에서 없어질 때까지 기다린다(runner-common §5).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = S4_BASE 또는 git merge-base main HEAD.
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. pipefail — `… | tail` 이 앞 명령의 실패를 가리지 않게
#   (검증 ① B1).
set -u
set -o pipefail
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
I="$E/inventory"
C="$E/core"
S="$A/tests/security"
OUT="${S4_OUT:-$ROOT/../S3K2a.out/s4}"
export LC_ALL=C
NOKEY="env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY"

COMMIT=""; ONLY=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <1|2> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2) ;; *) echo "--commit <1|2> 이 필요하다" >&2; exit 2 ;; esac
LOCK="$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"
BASE="${S4_BASE:-$(git merge-base main HEAD)}"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 S3K2a §4 · 경계 $COMMIT · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

wait_lock() {
  local waited=0
  while [ -e "$LOCK" ]; do
    [ "$waited" = 0 ] && echo "  verify.lock 있음 — 기다림"
    sleep 20
    waited=$((waited + 20))
  done
  echo "  lock 없음 확인 $(date +%H:%M:%S)$([ "$waited" = 0 ] || echo " (${waited}s 기다림)")"
}

not_run() {  # <n> <설명> <까닭>
  if [ -n "$ONLY" ] && [ "$ONLY" != "$1" ]; then return 0; fi
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}

changed() {  # <기준> 이후 바뀐 파일 + 새 파일(뿌리 기준 경로)
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-1 수정 허용(닫힌 목록 — 경계마다 누적). apps.py 는 감독 허락 한 줄(carrier 까닭 주석 — C0 Q-b).
ALLOWED_1="^$I/models\.py\$
^$I/apps\.py\$
^$I/migrations/0005_scope3_categories\.py\$
^$I/service/(selectors|services|actions|schemas|apis|utils)/scope3_state\.py\$
^$I/service/apis/inventory\.py\$
^$I/tests/test_route_shapes\.py\$
^$I/tests/test_migrations_0005\.py\$
^$I/tests/service/(utils|actions|apis)/test_scope3_state(_race)?\.py\$
^$C/permissions\.py\$
^$C/tests/(test_permissions|test_permissions_wiring|test_transaction_rules|test_selector_scope)\.py\$
^$C/tests/isolation/(test_static_rules|test_managers)\.py\$
^$E/config/tests/(test_api_contract|test_api_errors|test_api_times)\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$S/(test_tenant_paths|test_login|test_operator_company|test_migrations|test_entries|test_scope3_state)\.py\$
^$A/scripts/(section4|planted-breaks)-S3K2a\.sh\$"
ALLOWED_2="^$I/service/(actions|schemas|apis|utils)/dashboard\.py\$
^$I/tests/service/(actions|apis|utils)/test_dashboard\.py\$
^$I/(README\.md|__init__\.py)\$"
ALLOWED="$ALLOWED_1"
[ "$COMMIT" -ge 2 ] && ALLOWED="$ALLOWED
$ALLOWED_2"

s1() {
  local all outside pattern
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | grep . | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  [ "$outside" -eq 0 ]
}

# §4-1: 1-2 0줄 — 경로가 실재하는지 먼저(> 0), 그다음 diff 0. apps.py 는 1-1 예외 한 줄이라 여기서는 numstat 1 0 을 본다.
ZERO="$I/engines $I/contracts $I/flows $I/prompts $I/tools $C/flows $E/runs apps/web $A/.importlinter $A/pyproject.toml
$A/uv.lock $E/config/api.py $E/config/apps_list.py"
s2() {
  local missing=0 p n bad apps
  for p in $ZERO; do
    n="$(git ls-files -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ 없는 자리: $p"; missing=$((missing + 1)); }
    echo "  $p $(git ls-files -- "$p" | head -1)"
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u | grep .)"
  # shellcheck disable=SC2086
  echo "  ls-files $(git ls-files -- $ZERO | wc -l | tr -d ' ') · diff 줄 $(git diff "$BASE" -- $ZERO | wc -l | tr -d ' ')"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  apps="$(git diff --numstat "$BASE" -- "$I/apps.py" | cut -f1,2)"
  echo "  apps.py numstat '${apps:-0 0}'(감독 허락 한 줄 — 1 0 또는 빔)"
  [ -z "$bad" ] && [ "$missing" -eq 0 ] && { [ -z "$apps" ] || [ "$apps" = "$(printf '1\t0')" ]; }
}

# 1-5 셈 줄: numstat 과 「-」 줄 원문(수·같은 줄 주석만이어야 — 사람이 표와 견준다). permissions.py 는 sha16 도.
COUNTS="$C/tests/test_permissions.py $C/tests/test_permissions_wiring.py $C/tests/test_transaction_rules.py
$C/tests/test_selector_scope.py $C/tests/isolation/test_static_rules.py $C/tests/isolation/test_managers.py
$E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py $E/config/tests/test_api_times.py
$I/tests/test_route_shapes.py $S/test_tenant_paths.py $S/test_login.py $S/test_operator_company.py $S/test_migrations.py
$S/test_entries.py"
s3() {
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $COUNTS "$C/permissions.py" "$A/generated" | sed 's/^/  numstat /'
  echo "  permissions.py sha16 $(git diff "$BASE" -- "$C/permissions.py" | shasum -a 256 | cut -c1-16)"
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $COUNTS "$C/permissions.py" | grep -E '^(\+\+\+ |-[^-])' | sed 's/^/  /'
  return 0
}

s4() {
  (cd "$A" && uv run --frozen lint-imports 2>&1 | tail -2 && uv run --frozen ruff check . -q && uv run --frozen ruff format --check . -q \
    && uv run --frozen pyright 2>&1 | tail -1)
}

PURE="esgapi/inventory esgapi/core esgapi/config esgapi/runs"
s5() {
  wait_lock
  # shellcheck disable=SC2086
  (cd "$A" && $NOKEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db" $PURE 2>&1 | tail -3)
}

s6() {
  wait_lock
  (cd "$A" && $NOKEY scripts/test-business.sh -n 2 -p no:cacheprovider esgapi/inventory esgapi/runs esgapi/core esgapi/config \
    > "$OUT/business.log" 2>&1; code=$?; tail -2 "$OUT/business.log"; [ "$code" -eq 0 ]) || return 1
  wait_lock
  (cd "$A" && $NOKEY scripts/test-security.sh -p no:cacheprovider > "$OUT/security.log" 2>&1; code=$?
    tail -2 "$OUT/security.log"; [ "$code" -eq 0 ])
}

s7() {
  (cd "$A" && scripts/planted-breaks-S3K2a.sh --commit "$COMMIT" > "$OUT/planted.log" 2>&1; code=$?; cat "$OUT/planted.log"; [ "$code" -eq 0 ])
}

# §3 실행 길 바이트: 지어낸 템플릿 둘 × 같은 모의 답의 run_flow 결과 JSON sha(section4-S3K3.sh 의 [1] 꼴 — 그 재료 그대로).
GOLDEN_PY='
import hashlib, json
from esgapi.core.flows.run import run_flow
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.tests.engines.scope3.colab_157.support import ColabReplies, FakeGeocoder, activity_book, sheet, workbook, xlsx_bytes
from esgapi.inventory.tests.engines.scope3.colab_157.test_pipeline import all_sheets
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, TAGS
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tests.flows import test_scope3_colab_157_resume as R
def sha(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
inputs = colab.ColabInputs(template=xlsx_bytes(workbook(*all_sheets())), report_year=2025, route=ROUTE, tags=TAGS)
adapters = colab.ColabAdapters(llm=mock_client(ColabReplies()), factor_book=activity_book(sheet("구매_USEPA", BOOK_ROWS)), geocoder=FakeGeocoder())
(full,) = run_flow(colab.FLOW, inputs, adapters).output.results
(part,) = run_flow(colab.FLOW, R.inputs_of(R.SHEETS), R.adapters_of(R.Provider())).output.results
print("full21 " + sha(full)[:16]); print("partial " + sha(part)[:16])
'
s8() {
  wait_lock
  local got want
  got="$(cd "$A" && $NOKEY uv run --frozen python -c "$GOLDEN_PY" 2>&1 | tail -2)"
  want="$(cat "$ROOT/../S3K2a.out/golden-base.txt" 2>/dev/null)"
  echo "$got" | sed 's/^/  지금 /'
  echo "$want" | sed 's/^/  BASE /'
  [ -n "$want" ] && [ "$got" = "$want" ]
}

s9() {  # 위생: 더한 줄에 키 꼴·받은 자료 자리 0, 새 xlsx 0
  local added hits
  # 이 스크립트 자신(위생 무늬 글자)과 generated 는 뺀다(검증 ① B3)
  added="$(git diff "$BASE" -- . ':!apps/api-py/generated' ':!apps/api-py/scripts/section4-S3K2a.sh' | grep -E '^\+[^+]')"
  hits="$(echo "$added" | grep -E -c 'sk-[A-Za-z0-9]{16}|AKIA[0-9A-Z]{12}|received/|BEGIN (RSA|PRIVATE)')"
  echo "  키·받은 자료 꼴 $hits · 새 xlsx $(changed | grep -c '\.xlsx$')"
  [ "$hits" -eq 0 ] && [ "$(changed | grep -c '\.xlsx$')" -eq 0 ]
}

s10() {
  wait_lock
  scripts/verify.sh --fast > "$OUT/verify-fast.log" 2>&1
  local code=$?
  tail -1 "$OUT/verify-fast.log"
  return "$code"
}

step 1 "바뀐 경로 ⊆ 1-1(경계 $COMMIT)" s1
step 2 "1-2 0줄(경로 실재 > 0 → diff 0)" s2
step 3 "1-5 셈 줄 numstat·「-」 줄" s3
step 4 "lint-imports·ruff·pyright" s4
step 5 "순수 층(inventory·core·config·runs — 보안 층은 [6])" s5
if [ "$CONTAINERS" = 1 ]; then
  step 6 "업무 층(inventory·runs·core·config)·보안 층 전량" s6
  step 7 "심은 고장" s7
else
  not_run 6 "업무·보안 층" "--with-containers 없음"
  not_run 7 "심은 고장" "--with-containers 없음"
fi
step 8 "실행 길 바이트(흐름 결과 sha16 = BASE)" s8
step 9 "위생" s9
step 10 "scripts/verify.sh --fast" s10
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
