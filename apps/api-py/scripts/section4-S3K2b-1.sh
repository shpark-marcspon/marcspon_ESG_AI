#!/usr/bin/env bash
# 밴드 S3K2b-1(MARC-TICK-487: Scope 3 줄 덧판 첫 판)의 §4 자기검증(발주서 band-handoffs/S3K2b-1-order.md §4).
#   사용: apps/api-py/scripts/section4-S3K2b-1.sh --commit <1|2> [--step <n>]
# 단계마다 verify.lock 이 있으면 exit 3, 없으면 「lock 없음 확인 <시각>」 → 명령을 로그 파일로 돌리고 그 명령의 종료 코드를
# 「[n] EXIT=」로 적는다(tail 로 가리지 않는다 — tail 은 로그에 따로). 끝 줄 SECTION4_FAIL=<n>.
# 이 워크트리의 compose postgres(+ 마감 판은 storage)가 떠 있어야 한다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# AI 공급사 호출 0(env -u 키). <기준> = S4_BASE, 기본 e9c6abec.
set -euo pipefail
cd "$(dirname "$0")/../../.."
W="$(pwd)"
A=apps/api-py
E="$A/esgapi"
I="$E/inventory"
C="$E/core"
S="$A/tests/security"
LOCK="/Users/leedongeon/Desktop/marcspon/esg-app/.git/verify.lock"
OUT="${S4_OUT:-$W/../S3K2b-1.out/s4}"
BASE="${S4_BASE:-e9c6abec}"
export LC_ALL=C
NOKEY=(env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY)

COMMIT=""; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    *) echo "사용: $0 --commit <1|2> [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2) ;; *) echo "--commit <1|2> 이 필요하다" >&2; exit 2 ;; esac
mkdir -p "$OUT"
echo "── 밴드 S3K2b-1 §4 · 경계 $COMMIT · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…>
  local n="$1" what="$2" start code log
  shift 2
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then return 0; fi
  [ ! -e "$LOCK" ] || { echo "verify.lock 있음 — [$n] 앞에서 멈춤"; exit 3; }
  echo "── [$n] $what · lock 없음 확인 $(date +%H:%M:%S)"
  log="$OUT/step-$n.log"
  start=$(date +%s)
  # 서브셸 안에서 set -e 를 다시 켠다 — `|| code=$?` 꼴은 단계 안 중간 실패를 가린다(검증 ① B1)
  set +e
  ( set -euo pipefail; "$@" ) > "$log" 2>&1
  code=$?
  set -e
  [ "$code" -ne 3 ] || { echo "verify.lock 있음 — [$n] 안에서 멈춤"; exit 3; }
  tail -"${S4_TAIL:-6}" "$log" | sed 's/^/  /'
  echo "[$n] EXIT=$code $(( $(date +%s) - start ))s $what"
  [ "$code" -eq 0 ] || FAILS=$((FAILS + 1))
}

changed() {  # 기준 이후 바뀐 파일(스테이징·작업 트리) + 새 파일
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

ALLOWED="^$I/models\.py\$
^$I/apps\.py\$
^$I/(README\.md|__init__\.py)\$
^$I/migrations/0006_scope3_row_edits\.py\$
^$I/service/(selectors|services|actions|schemas|apis|utils)/scope3_edits\.py\$
^$I/service/(utils|selectors|actions|schemas|apis)/scope3_state\.py\$
^$I/service/actions/dashboard\.py\$
^$I/service/apis/inventory\.py\$
^$I/tests/
^$C/permissions\.py\$
^$C/tests/(test_permissions|test_permissions_wiring|test_transaction_rules|test_selector_scope)\.py\$
^$C/tests/isolation/(test_static_rules|test_managers)\.py\$
^$E/config/tests/(test_api_contract|test_api_errors|test_api_times|test_request_schemas_reject_bool)\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$S/(test_tenant_paths|test_login|test_operator_company|test_migrations|test_owner|test_scope3_edits)\.py\$
^$A/scripts/(section4|planted-breaks)-S3K2b-1\.sh\$"

# 1-2 0줄 — 풀어 쓴 경로 하나의 배열. 경로마다 ls-files 가 비지 않음을 먼저 본다.
P=(
  "$I/engines" "$I/contracts" "$I/flows" "$I/prompts" "$I/tools"
  "$I/service/actions/scope3_runs.py" "$I/service/apis/scope3_runs.py"
  "$C/flows" "$E/runs" apps/web
  "$A/.importlinter" "$A/pyproject.toml" "$A/uv.lock" "$E/config/api.py" "$E/config/apps_list.py"
)
s1() {
  local all outside pattern p first lines apps
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | grep . | paste -sd'|' -)"
  echo "$all"
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c . || true)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/★ 밖: /'
  echo "바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  for p in "${P[@]}"; do
    first="$(git -C "$W" ls-files "$p" | head -1)"
    [ -n "$first" ] || { echo "★ 없는 자리: $p"; return 1; }
  done
  lines="$(git -C "$W" diff --cached "$BASE" -- "${P[@]}" | wc -l | tr -d ' ')"
  lines=$((lines + $(git -C "$W" diff "$BASE" -- "${P[@]}" | wc -l | tr -d ' ')))
  apps="$(git -C "$W" diff --numstat "$BASE" -- "$I/apps.py" | cut -f1,2)"
  echo "1-2 diff 줄 $lines · apps.py numstat '$apps'"
  [ "$outside" -eq 0 ] && [ "$lines" -eq 0 ] && [ "$apps" = "$(printf '1\t0')" ]
}

s2() {
  uv run --directory "$A" --frozen lint-imports | tail -2
  uv run --directory "$A" --frozen ruff check . -q
  uv run --directory "$A" --frozen ruff format --check . -q
  uv run --directory "$A" --frozen pyright | tail -1
}

s3() {
  (cd "$A" && "${NOKEY[@]}" uv run --frozen pytest -q -p no:cacheprovider -m "not django_db" -n 2 \
    esgapi/inventory esgapi/core esgapi/config esgapi/runs)
}

s4() {
  (cd "$A" && "${NOKEY[@]}" scripts/test-business.sh -n 2 -p no:cacheprovider esgapi/inventory esgapi/runs esgapi/core esgapi/config)
  [ ! -e "$LOCK" ] || { echo "verify.lock 있음 — 보안 층 앞에서 멈춤"; exit 3; }
  (cd "$A" && "${NOKEY[@]}" scripts/test-security.sh -p no:cacheprovider -rs)
}

# 1-5 셈 줄: numstat 과 「-」 줄 원문(수·같은 줄 주석만이어야 — 사람이 표와 견준다). permissions.py 는 sha16 도.
COUNTS=(
  "$C/tests/test_permissions.py" "$C/tests/test_permissions_wiring.py" "$C/tests/test_transaction_rules.py"
  "$C/tests/test_selector_scope.py" "$C/tests/isolation/test_static_rules.py" "$C/tests/isolation/test_managers.py"
  "$E/config/tests/test_api_contract.py" "$E/config/tests/test_api_errors.py" "$E/config/tests/test_api_times.py"
  "$E/config/tests/test_request_schemas_reject_bool.py" "$I/tests/test_route_shapes.py" "$S/test_tenant_paths.py"
  "$S/test_login.py" "$S/test_operator_company.py" "$S/test_migrations.py" "$S/test_owner.py"
)
s5() {
  git diff --numstat "$BASE" -- "${COUNTS[@]}" "$C/permissions.py" "$A/generated" | sed 's/^/numstat /'
  echo "permissions.py sha16 $(git diff "$BASE" -- "$C/permissions.py" | shasum -a 256 | cut -c1-16)"
  git diff -U0 "$BASE" -- "${COUNTS[@]}" "$C/permissions.py" | grep -E '^(\+\+\+ |-[^-])' || true
  # 「그대로」 줄: 값이 그대로 있어야 한다
  grep -q 'assert len(OPERATOR_OPERATIONS) == 65' "$S/test_operator_company.py"
  grep -q 'assert len(OPERATOR_COMPANY_OPERATIONS) == 3' "$S/test_tenant_paths.py"
  grep -q 'assert len(of_kind("scope3_state_paths")) == 3' "$S/test_tenant_paths.py"
  grep -q 'assert len(of_kind("entry_paths")) == 16' "$S/test_tenant_paths.py"
  [ "$(git diff "$BASE" -- "$S/test_entries.py" "$S/test_same_company_foreign_keys.py" | wc -l | tr -d ' ')" = 0 ]
  # 「-」 줄은 셈 줄·주석만(표 밖 「-」 0). CONSTRUCTOR_ALLOWED 한 줄은 플랫폼-서버 7a 허락(bulk_create)
  local minus
  minus="$(git diff -U0 "$BASE" -- "${COUNTS[@]}" | grep -E '^-[^-]' | grep -v -E '== *\(?[0-9]|^-[A-Z_]+ = [0-9]+|for operation in with_scope3_state|assert reached ==|^-CONSTRUCTOR_ALLOWED' | grep -c . || true)"
  echo "표 밖 - 줄 $minus"
  [ "$minus" -eq 0 ]
}

s6() {
  (cd "$A" && scripts/planted-breaks-S3K2b-1.sh --commit "$COMMIT")
}

# §3 실행 길 바이트: 지어낸 템플릿 둘 × 같은 모의 답의 run_flow 결과 JSON sha(section4-S3K2a.sh [8] 꼴).
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
s7() {
  local got want
  got="$(cd "$A" && "${NOKEY[@]}" uv run --frozen python -c "$GOLDEN_PY" | tail -2)"
  want="$(cat "$W/../S3K2b-1.out/golden-base.txt")"
  echo "지금 $got"
  echo "BASE $want"
  [ -n "$want" ]
  [ "$got" = "$want" ]
  (cd "$A" && "${NOKEY[@]}" scripts/test-business.sh -p no:cacheprovider \
    esgapi/inventory/tests/service/apis/test_scope3_edits.py::test_the_result_get_stays_the_original_after_an_exclusion)
}

s8() {  # 위생: 더한 줄에 키 꼴·받은 자료 자리 0, 새 xlsx 0. 이 스크립트 둘과 generated 는 뺀다.
  local added hits xlsx
  added="$(git diff "$BASE" -- . ':!apps/api-py/generated' \
    ':!apps/api-py/scripts/section4-S3K2b-1.sh' ':!apps/api-py/scripts/planted-breaks-S3K2b-1.sh' | grep -E '^\+[^+]' || true)"
  hits="$(echo "$added" | grep -E -c 'sk-[A-Za-z0-9]{16}|AKIA[0-9A-Z]{12}|received/|BEGIN (RSA|PRIVATE)' || true)"
  xlsx="$(changed | grep -c '\.xlsx$' || true)"
  echo "키·받은 자료 꼴 $hits · 새 xlsx $xlsx"
  [ "$hits" -eq 0 ] && [ "$xlsx" -eq 0 ]
}

s9() {
  scripts/verify.sh --fast
}

step 1 "바뀐 경로 ⊆ 1-1 · 1-2 diff 0 · apps.py 1 0" s1
step 2 "lint-imports·ruff·pyright" s2
step 3 "순수 층(보안 층 뺌)" s3
step 4 "업무·보안 층" s4
step 5 "1-5 셈 줄·「그대로」·표 밖 - 0" s5
S4_TAIL=14 step 6 "심은 고장" s6
step 7 "실행 길·결과 GET 바이트" s7
step 8 "위생" s8
step 9 "scripts/verify.sh --fast" s9
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
