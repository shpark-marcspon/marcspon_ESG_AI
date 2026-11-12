#!/usr/bin/env bash
# 밴드 XC 의 심은 파손 여덟(P1~P8. 발주서 §3-3 이 정본): 하나씩 심고, 그것을 잡아야 하는 테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-XC.sh --pure         P1~P6 (순수 층만, 컨테이너 없이). 마지막 줄 PLANTED=<잡은 수>/6
#         apps/api-py/scripts/planted-breaks-XC.sh --containers   P7·P8 (compose 의 postgres 가 떠 있어야 한다). PLANTED=<잡은 수>/2
# 0번은 심지 않고 돌린다: 겨냥한 테스트가 전부 초록이어야 한다(처음부터 빨간 것을 「잡았다」고 세지 않게).
# 심기 전의 파일을 저장소 밖 임시 폴더(mktemp -d)에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도
# trap 이 되돌린다). 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를
# 내지 않고 종료 1.
# ★ 그래도 파일을 잃었으면(kill -9 등으로 trap 이 못 돌았으면) 그 파일만 `git show HEAD:<경로> > <경로>` 로 되찾는다
#   (커밋 전이면 커밋 안 된 판이 사라지므로 trap 의 사본($keep)을 먼저 본다).
# 「잡음」의 기준: 테스트가 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다.
#   「초록」으로 적은 것은 PASSED 줄에 있어야 한다. 심는 글자가 지금 파일에 정확히 한 번 있지 않으면 심지 못한 것이다(종료 3).
# 업무 층은 심은 것마다 그 테스트 파일만 겨냥해 돌린다(test-business.sh <파일>). AI 공급사 호출 0. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-}"
case "$MODE" in --pure | --containers) ;; *) echo "사용: $0 --pure|--containers" >&2; exit 2 ;; esac
export PYTHONDONTWRITEBYTECODE=1

A=apps/api-py
E="$A/esgapi"
CONFIG="$E/config/api.py"
RUNS="$E/core/service/apis/runs.py"
RUN_SCHEMAS="$E/core/service/schemas/runs.py"
PERMISSIONS="$E/core/permissions.py"
DOCUMENTS="$E/core/service/apis/documents.py"
T_CONTRACT=esgapi/config/tests/test_api_contract.py
T_PERM=esgapi/core/tests/test_permissions.py
T_DOCS=esgapi/core/tests/test_documents_api.py
T_RUNS=esgapi/core/tests/service/apis/test_runs.py

keep="$(mktemp -d)"
log="$(mktemp -d)"
FILES=("$CONFIG" "$RUNS" "$RUN_SCHEMAS" "$PERMISSIONS" "$DOCUMENTS")
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "파일이 없다: $f" >&2; exit 2; }
  cp "$f" "$keep/$(echo "$f" | tr / _)"
done
sums() { shasum -a 256 "${FILES[@]}" 2>&1; }
sums > "$keep/.sums-before"
git status --porcelain > "$keep/.status-before"
restore_files() { for f in "${FILES[@]}"; do cp "$keep/$(echo "$f" | tr / _)" "$f"; done; }
trap 'restore_files' EXIT INT TERM

total=0; ok=0
edit() { # <파일> <있던 글자> <바꿀 글자>
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심을 자리가 {text.count(old)}곳이다(1곳이어야 한다): {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}
pure_tests() { (cd "$A" && PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run --frozen pytest -q -rfp -p no:cacheprovider -m "not django_db and not security" "$@"); }
business_tests() { "$A/scripts/test-business.sh" -rfp -p no:cacheprovider "$@"; }
# <번호와 설명> <로그 파일> <종료 코드> <red:이름|green:이름 …>
judge() {
  local name="$1" file="$2" code="$3" missed=0 want kind
  shift 3
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|^FAILED|^ERROR' "$file" | sed 's/^/    /' | cut -c1-230 | head -8
  [ "$code" -ne 0 ] || missed=1
  for want in "$@"; do
    kind="${want%%:*}"; want="${want#*:}"
    case "$kind" in
      red) grep '^FAILED ' "$file" | grep -q -F "$want" || { missed=1; echo "    (FAILED 줄에 없다: $want)"; } ;;
      green) grep '^PASSED ' "$file" | grep -q -F "$want" || { missed=1; echo "    (PASSED 줄에 없다: $want)"; } ;;
    esac
  done
  if [ "$missed" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  restore_files
}
zero() { # <로그> <코드>  심지 않은 판이 초록이어야 한다
  if [ "$2" != 0 ] || tail -1 "$1" | grep -q -E 'failed|error'; then
    echo "0. 심지 않았는데 빨갛다 → ★ 멈춘다" >&2; tail -20 "$1" >&2; exit 1
  fi
  echo "0. 심지 않음 → 초록 ($(tail -1 "$1"))"
}

ADD_RUNS='api.add_router("/runs", runs_router, auth=session_cookie)'

pure() {
  pure_tests "$T_CONTRACT" "$T_PERM" > "$log/0.txt" 2>&1; zero "$log/0.txt" $?

  # P1. /runs 의 라우터를 걸지 않는다.
  edit "$CONFIG" "$ADD_RUNS"$'\n' '' || exit 3
  pure_tests "$T_CONTRACT" > "$log/P1.txt" 2>&1; code=$?
  judge "P1. config/api.py 의 /runs add_router 를 지움" "$log/P1.txt" "$code" red:test_operation_ids_are_the_hand_written_table

  # P2. runs_get 의 operationId 를 바꾼다. test_every_authenticated_operation_is_in_the_table 은 커밋한 generated/ 를
  #     읽으므로 초록으로 남는다(개정 1).
  edit "$RUNS" 'operation_id="runs_get"' 'operation_id="runs_detail"' || exit 3
  pure_tests "$T_CONTRACT" "$T_PERM" > "$log/P2.txt" 2>&1; code=$?
  judge "P2. runs_get → runs_detail" "$log/P2.txt" "$code" red:test_operation_ids_are_the_hand_written_table \
    red:test_each_route_checks_its_own_operation_id_first red:test_committed_openapi_matches_the_code \
    green:test_every_authenticated_operation_is_in_the_table

  # P3. RunOut 에서 failedStep 을 지운다.
  edit "$RUN_SCHEMAS" $'    failedStep: str | None\n' '' || exit 3
  pure_tests "$T_CONTRACT" > "$log/P3.txt" 2>&1; code=$?
  judge "P3. RunOut.failedStep 을 지움" "$log/P3.txt" "$code" red:test_the_run_and_version_operations_are_the_contract_sheet \
    red:test_committed_openapi_matches_the_code

  # P4. /runs 에 세션 인증을 꽂지 않는다.
  edit "$CONFIG" "$ADD_RUNS" 'api.add_router("/runs", runs_router)' || exit 3
  pure_tests "$T_CONTRACT" > "$log/P4.txt" 2>&1; code=$?
  judge "P4. /runs 의 add_router 에서 auth= 를 뺌" "$log/P4.txt" "$code" red:test_the_run_and_version_operations_are_the_contract_sheet

  # P5. 권한 표에서 runs_create 를 지운다.
  edit "$PERMISSIONS" $'    "runs_create": Policy("editor"),\n' '' || exit 3
  pure_tests "$T_PERM" > "$log/P5.txt" 2>&1; code=$?
  judge "P5. permissions.py 의 runs_create 줄을 지움" "$log/P5.txt" "$code" red:test_every_authenticated_operation_is_in_the_table \
    red:test_the_table_is_these_thirty_nine_cells

  # P6. RunIn.flowId 의 무늬를 지운다.
  edit "$RUN_SCHEMAS" 'default=None, pattern=FLOW_ID_PATTERN, description=' 'default=None, description=' || exit 3
  pure_tests "$T_CONTRACT" > "$log/P6.txt" 2>&1; code=$?
  judge "P6. RunIn.flowId 의 pattern 을 지움" "$log/P6.txt" "$code" red:test_the_run_and_version_operations_are_the_contract_sheet
}

containers() {
  business_tests "$T_DOCS" "$T_RUNS" > "$log/0c.txt" 2>&1; zero "$log/0c.txt" $?

  # P7. 문서 만들기의 501 갈래를 지운다(두 칸에 값이 있어도 행을 만든다).
  edit "$DOCUMENTS" $'    if body.reportYear is not None or body.previousDocumentId is not None:\n        return error_response(501, "not_implemented", NOT_IMPLEMENTED)\n' '' || exit 3
  business_tests "$T_DOCS" > "$log/P7.txt" 2>&1; code=$?
  judge "P7. documents_create 의 501 갈래를 지움" "$log/P7.txt" "$code" red:test_a_create_with_report_year_or_previous_is_501_and_writes_nothing

  # P8. runs_get 이 200 {} 을 돌려준다.
  edit "$RUNS" $'    _permitted(request, "runs_get")\n    return error_response(501, "not_implemented", NOT_IMPLEMENTED)\n' $'    _permitted(request, "runs_get")\n    return HttpResponse(b"{}", content_type="application/json")\n' || exit 3
  business_tests "$T_RUNS" > "$log/P8.txt" 2>&1; code=$?
  judge "P8. runs_get 이 200 {} 을 돌려줌" "$log/P8.txt" "$code" "red:test_each_run_operation_is_501_after_auth[runs_get]"
}

case "$MODE" in
  --pure) pure ;;
  --containers) containers ;;
esac

restore_files
trap - EXIT INT TERM
sums > "$keep/.sums-after"
git status --porcelain > "$keep/.status-after"
if ! diff -q "$keep/.sums-before" "$keep/.sums-after" > /dev/null || ! diff -q "$keep/.status-before" "$keep/.status-after" > /dev/null; then
  echo "★ 되돌린 뒤의 파일·상태가 처음과 다르다 — PLANTED 를 내지 않는다 (사본: $keep)"; exit 1
fi
echo "(되돌림: 파일 ${#FILES[@]} 의 sha256 과 git status 가 처음과 같다 · 기록 $log)"
echo "PLANTED=$ok/$total"
[ "$ok" = "$total" ]
