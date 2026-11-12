#!/usr/bin/env bash
# 심은 파손(밴드 PY8a, MARC-TICK-56 §3): 게이트·순수 층 이동·경로 쪽의 장치를 하나씩 망가뜨리고, 그것을 잡아야 할
# 검사가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-PY8a.sh             열넷 전부(11·12 는 postgres 가 떠 있어야 한다)
#         apps/api-py/scripts/planted-breaks-PY8a.sh --pure      컨테이너 없이 재는 열둘(1~10·13·14)
#         apps/api-py/scripts/planted-breaks-PY8a.sh --containers  업무 층으로 재는 둘(11·12). 이 워크트리의 postgres 가 떠 있을 때
# 파손 하나마다: 파일을 고친다(고칠 자리가 정확히 한 곳이어야 한다) → 검사를 돌린다 → 기대한 빨강이 났는지 본다 →
# 파일을 처음 바이트로 되돌린다(git 을 쓰지 않는다). 끝나면 작업 트리가 처음과 같은지 본다.
# 마지막 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>. 두 번에 나눠 재면 합이 14/14 다.
# 자기 워크트리에서만 돌린다(main 작업 트리에서 심지 않는다). AI 공급사 호출 0.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac

backup="$(mktemp -d)"
planted_file=""
restore() { if [ -n "$planted_file" ]; then cp "$backup/original" "$planted_file"; planted_file=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
tree_state() { { git status --porcelain; git diff | shasum -a 256; git ls-files -o --exclude-standard -z | xargs -0 shasum -a 256; } | shasum -a 256; }
state_before="$(tree_state)"

# <파일> <옛 글> <새 글>: 옛 글이 정확히 한 곳일 때만 바꾼다.
swap() {
  planted_file="$1"
  cp "$1" "$backup/original"
  python3 - "$1" "$2" "$3" <<'PY'
import sys
from pathlib import Path

path, old, new = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
text = path.read_text(encoding="utf-8")
if text.count(old) != 1:
    sys.exit(f"고칠 자리가 {text.count(old)}곳이다: {path}: {old[:60]!r}")
path.write_text(text.replace(old, new), encoding="utf-8")
PY
}

# 검사의 출력에 「▶ 이름 ⇒ EXIT=n」 줄을 덧붙인다(check-gates.sh·verify.sh 의 단계별 결과를 한 줄로 찾으려고).
observe() { ( eval "$1" ) 2>&1 | awk '{ print } /^▶ / { head = $0 } /^EXIT=/ { print head " ⇒ " $0 }'; }

total=0
ok=0
# <번호> <설명> <파일> <옛 글> <새 글> <검사 명령> <빨개졌다는 줄의 정규식>…  (정규식 전부가 출력에 있어야 한다)
plant() {
  local number="$1" name="$2" file="$3" old="$4" new="$5" command="$6"
  shift 6
  total=$((total + 1))
  if ! swap "$file" "$old" "$new"; then
    echo "$number. $name → ★ 심지 못했다"
    restore
    return
  fi
  local out missing=""
  out="$(observe "$command")"
  restore
  for pattern in "$@"; do
    printf '%s\n' "$out" | grep -q -E -- "$pattern" || missing="$missing [$pattern]"
  done
  if [ -z "$missing" ]; then
    ok=$((ok + 1))
    echo "$number. $name → 빨강(기대대로): $*"
  else
    echo "$number. $name → ★ 기대한 빨강이 없다:$missing"
    printf '%s\n' "$out" | tail -15 | sed 's/^/      /'
  fi
}
# 심지 않았을 때 초록인가(빨강이 심은 것 때문이라는 대조). 수에 넣지 않는다.
control() { # <이름> <검사 명령>
  if ( eval "$2" ) > "$backup/control.out" 2>&1; then
    echo "0. 심지 않음: $1 → 초록"
  else
    echo "0. 심지 않음: $1 → ★ 빨강(심기 전부터 빨갛다. 아래 결과를 믿지 않는다)"
    tail -8 "$backup/control.out" | sed 's/^/      /'
    control_failed=1
  fi
}
control_failed=0

GATES='scripts/check-gates.sh'
FAST='scripts/verify.sh --fast'
CONTRACTS='cd apps/api-py && COLUMNS=400 uv run --frozen lint-imports'
# 아래 명령들은 eval 로 돈다. 띄어쓰기가 든 인자(-k 의 식)는 여기서 따옴표째 적는다.
pure_test() { echo "cd apps/api-py && uv run --frozen pytest -q -p no:cacheprovider -rf -m 'not django_db and not security' $*"; }
BUSINESS='apps/api-py/scripts/test-business.sh -p no:cacheprovider -rf'
API_CONTRACT="$(pure_test esgapi/config/tests/test_api_contract.py)"
BOOL_SWEEP="$(pure_test esgapi/config/tests/test_request_schemas_reject_bool.py)"
RECONCILE_PURE="$(pure_test esgapi/reconcile/tests/test_calc_is_pure.py)"
BODY_LIMIT="$BUSINESS esgapi/inventory/tests/test_api.py esgapi/accounts/tests/test_api.py -k 'django_limit or oversized'"
ROW_LIMIT="$BUSINESS esgapi/inventory/tests/test_scope3_api.py -k more_than_1000_rows"
LIMITS="$BUSINESS esgapi/inventory/tests/test_api.py esgapi/accounts/tests/test_api.py esgapi/inventory/tests/test_scope3_api.py -k 'django_limit or oversized or more_than_1000_rows'"

pure_plants() {
  control "check-gates.sh" "$GATES"
  control "verify.sh --fast" "$FAST"
  control "lint-imports" "$CONTRACTS"
  control "계약·훑기·reconcile 순수 테스트" "$(pure_test esgapi/config/tests/test_api_contract.py esgapi/config/tests/test_request_schemas_reject_bool.py esgapi/reconcile/tests/test_calc_is_pure.py)"

  plant 1 "--fast 가 docker compose build 를 건너뛰지 않는다" scripts/verify.sh \
    'container_step docker compose build' 'step docker compose build' \
    "$GATES" '--fast --plan 에 docker 0줄.* ⇒ EXIT=1' '가짜 도구로 돌린 --fast.* ⇒ EXIT=1'

  plant 2 "전량에서 test-security.sh 단계를 뺀다" scripts/verify.sh \
    'container_step apps/api-py/scripts/test-security.sh' ': 보안 층을 뺐다' \
    "$GATES" '전량 − 빠른 = 컨테이너 단계 여덟 ⇒ EXIT=1' '가짜 도구로 돌린 전량.* ⇒ EXIT=1'

  plant 3 "잠금을 끝에서 놓지 않는다(trap 제거)" scripts/verify.sh \
    '  trap release_lock EXIT' '  : trap 을 뺐다' \
    "$GATES" '가짜 도구로 돌린 전량.* ⇒ EXIT=1' '단계가 실패한 전량.* ⇒ EXIT=1' 'SIGINT 뒤 자기 잠금 없음 ⇒ EXIT=1'

  plant 4 "죽은 pid 검사를 뺀다" scripts/verify.sh \
    '    if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
      # 죽은 잠금.' '    if false; then
      # 죽은 잠금.' \
    "$GATES" '죽은 pid 의 잠금 → 치우고 가져감 ⇒ EXIT=1'

  plant 5 "pre-commit 이 스테이징 목록을 안 보고 늘 0" scripts/git-hooks/pre-commit \
    'set -u
root=' 'set -u
exit 0
root=' \
    "$GATES" 'pre-commit \(b\) 린트 위반 → 1 ⇒ EXIT=1' 'pre-commit \(c\) 계약 위반 import → 1 ⇒ EXIT=1' 'pre-commit \(d\) 순수 테스트를 깨는 변경 → 1 ⇒ EXIT=1'

  plant 6 "services/parser/app.py 에 안 쓰는 import" services/parser/app.py \
    'import traceback' 'import traceback
import zipfile' \
    "$FAST" 'ruff check services/parser ⇒ EXIT=1' '^VERIFY_FAST=FAIL$'

  plant 7 "core/calc/decimal.py 에 import django" apps/api-py/esgapi/core/calc/decimal.py \
    'import re
from dataclasses import dataclass' 'import re
from dataclasses import dataclass

import django  # noqa: F401' \
    "$CONTRACTS" '^다\. .* BROKEN'

  plant 8 "reconcile/calc/dec.py 가 inventory.calc 에서 import" apps/api-py/esgapi/reconcile/calc/dec.py \
    'from typing import Literal
' 'from typing import Literal

from esgapi.inventory.calc.types import Scope  # noqa: F401
' \
    "$RECONCILE_PURE" 'FAILED .*test_calc_is_pure.py::test_calc_imports_only_the_allowed_modules'

  plant 9 "TierIn 에서 NotBool 을 뺀다" apps/api-py/esgapi/inventory/schemas.py \
    'TierIn = Annotated[Tier, NotBool]' 'TierIn = Tier' \
    "$BOOL_SWEEP" 'FAILED .*::test_every_integer_field_of_every_request_body_rejects_true' 'CalcTiersIn\.calorific'

  plant 10 "accounts/api.py 의 operation_id 하나를 지운다" apps/api-py/esgapi/accounts/api.py \
    '    operation_id="accounts_me",
' '' \
    "$API_CONTRACT" 'FAILED .*::test_operation_ids_are_the_hand_written_table' 'FAILED .*::test_committed_openapi_matches_the_code'

  plant 13 "api.d.ts.source-sha256 의 한 글자" apps/api-py/generated/api.d.ts.source-sha256 \
    "$(cut -c1-8 apps/api-py/generated/api.d.ts.source-sha256)" "$(cut -c1-7 apps/api-py/generated/api.d.ts.source-sha256 | tr '0-9a-f' '1-9a-f0')z" \
    "$API_CONTRACT" 'FAILED .*::test_committed_types_were_generated_from_the_committed_openapi'

  plant 14 "reference 의 assemble 이 ERROR_RESPONSES 를 펼친다(413 선언 빠짐)" apps/api-py/esgapi/reference/api.py \
    '    response={200: AssembleOut, **BODY_ERROR_RESPONSES},' '    response={200: AssembleOut, **ERROR_RESPONSES},' \
    "$API_CONTRACT" 'FAILED .*::test_an_operation_declares_413_exactly_when_it_takes_a_body' 'FAILED .*::test_committed_openapi_matches_the_code'
}

container_plants() {
  control "본문 상한·행 상한의 업무 층 테스트" "$LIMITS"

  plant 11 "RequestDataTooBig 처리기를 뗀다" apps/api-py/esgapi/config/api.py \
    '@api.exception_handler(RequestDataTooBig)
' '' \
    "$BODY_LIMIT" 'FAILED .*test_api.py::test_a_body_over_the_django_limit_is_413' 'FAILED .*test_api.py::test_an_oversized_exchange_body_is_413_and_nothing_is_echoed'

  plant 12 "classify 의 행 상한 검사를 뺀다" apps/api-py/esgapi/inventory/api.py \
    '    if len(body.rows) > services.SCOPE3_MAX_ROWS:' '    if False:' \
    "$ROW_LIMIT" 'FAILED .*::test_more_than_1000_rows_is_413_before_grouping_and_nothing_is_called'
}

case "$MODE" in
  --pure) pure_plants ;;
  --containers) container_plants ;;
  *) pure_plants; container_plants ;;
esac

if [ "$(tree_state)" = "$state_before" ]; then echo "작업 트리: 처음과 같다"; else echo "★ 작업 트리가 처음과 다르다"; ok=-1; fi
[ "$control_failed" -eq 0 ] || ok=-1
echo "PLANTED=$ok/$total"
[ "$ok" -eq "$total" ]
