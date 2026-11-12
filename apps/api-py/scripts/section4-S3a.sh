#!/usr/bin/env bash
# 밴드 S3a(MARC-TICK-66: Scope 3 의 xlsx 읽개 · 계수 책 적재기 · 드롭다운 · 어긋남 검사)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-S3a.sh     줄마다 EXIT=<종료 코드>. 전부 0 이어야 한다(하나라도 아니면 스크립트가 1 로 끝난다)
# 컨테이너 층이 없다 — docker 를 부르지 않는다. AI 공급사 호출 0. 전량 scripts/verify.sh 는 돌리지 않는다(감독이 병합 뒤 main 에서).
# 원본 대조(esgapi/inventory/tests/s3sheets_probe.py)는 여기 없다: 원본 xlsx 가 저장소 밖이라 같은 경로를 보장하지 못한다.
# bash 전용.
set -u
cd "$(dirname "$0")/../../.."
B=c553816   # 기준 커밋(발주서 §1-1)
export B
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 가 Node 22 를 쓴다
LOG="${TMPDIR:-/tmp}/s3a-fast.log"
export LOG

run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
FAILS=0

# 이 밴드가 바꾼 파일(기준과의 차이 + 추적 안 된 새 파일).
changed() { { git diff --name-only "$B"; git ls-files -o --exclude-standard; } | sort -u; }
export -f changed
READER=apps/api-py/esgapi/inventory/xlsx_reader.py
SHEETS=apps/api-py/esgapi/inventory/calc/scope3_sheets
export READER SHEETS

# 1. 빠른 게이트. 끝 줄 VERIFY_FAST=PASS. 순수 건수 = 기준 1,329 + 새 건수.
run 'scripts/verify.sh --fast > "$LOG" 2>&1; code=$?; grep -E "passed|^VERIFY" "$LOG" | tail -3; grep -q "^VERIFY_FAST=PASS" "$LOG" && exit $code; exit 1'
# 2. 새 테스트만(건수를 보고에 적는다).
run '(cd apps/api-py && uv run --frozen pytest -q -m "not django_db and not security" esgapi/inventory/tests/test_s3sheets_*.py) 2>&1 | tail -2; exit ${PIPESTATUS[0]}'
# 3. 계약 넷. .importlinter 는 0줄인 채.
run '(cd apps/api-py && uv run --frozen lint-imports) 2>&1 | tail -8; exit ${PIPESTATUS[0]}'
# 4. 건드리면 안 되는 자리가 기준과 같다.
run 'git diff --quiet "$B" -- apps/api-py/.importlinter apps/api-py/pyproject.toml apps/api-py/uv.lock apps/api-py/generated apps/api-py/esgapi/inventory/calc/scope3 apps/api-py/esgapi/inventory/calc/tables.py apps/api-py/esgapi/inventory/api.py apps/api-py/esgapi/inventory/services.py apps/api-py/esgapi/inventory/schemas.py apps/api-py/esgapi/inventory/data apps/api-py/esgapi/inventory/data_loader.py apps/api-py/esgapi/reference apps/api-py/esgapi/core apps/api-py/esgapi/config apps/web compose.yaml scripts infra'
# 5. 자료 파일 0(표본은 테스트가 그때그때 짓는다).
run 'test -z "$(changed | grep -i -E "\.(xlsx|xlsm|xls|csv|zip)$")"'
# 6. 새 의존성 0.
run 'test -z "$(grep -rnE "^[[:space:]]*(import|from)[[:space:]]+(openpyxl|pandas|xlrd|python_calamine|defusedxml|lxml)" apps/api-py/esgapi apps/api-py/scripts)"'
# 7. xlsx 를 여는 제품 파일은 하나.
run 'test "$(grep -rlE "^[[:space:]]*(import|from)[[:space:]]+(zipfile|xml)" apps/api-py/esgapi --include="*.py" | grep -v "/tests/" | sort | tr "\n" " ")" = "$READER "'
# 8. 규칙 끄기는 S314 뿐(까닭을 괄호에).
run 'test "$(grep -rnE "noqa|type: ignore|pyright: ignore" "$READER" "$SHEETS" | grep -vc "xlsx_reader.py:.*noqa: S314 (")" = 0'
# 9. XML 을 파싱하는 자리는 하나.
run 'test "$(grep -c "noqa: S314 (" "$READER")" = 1'
# 10. 풀어 쓰지 않고, 무엇이든 삼키지 않는다.
run 'test -z "$(grep -nE "extractall|\.extract\(|except Exception|except BaseException|except:" "$READER")"'
# 11. S3b 의 것은 없다.
run 'test -z "$(ls "$SHEETS" | grep -E "^template")"'
# 12. 있는 글은 더하기만(지운 줄 0).
run 'test "$(git diff "$B" -- README.md apps/api-py/esgapi/inventory/__init__.py | grep -c "^-[^-]")" = 0'
# 13. tests 아래(표본·probe)는 이미지에 안 실린다.
run 'apps/api-py/scripts/check-wheel.sh'
# 14. 심은 파손. 마지막 줄 PLANTED=25/25.
run 'apps/api-py/scripts/planted-breaks-S3a.sh 2>&1 | grep -E "→|되돌림|^PLANTED|★"; exit ${PIPESTATUS[0]}'
# 15. 허용 경로 밖 0.
run 'out="$(changed | grep -v -E "^(apps/api-py/esgapi/inventory/calc/scope3_sheets/[a-z_]+\.py|apps/api-py/esgapi/inventory/xlsx_reader\.py|apps/api-py/esgapi/inventory/__init__\.py|apps/api-py/esgapi/inventory/tests/(test_s3sheets_[a-z0-9_]+|s3sheets_support|s3sheets_probe)\.py|apps/api-py/scripts/(section4|planted-breaks)-S3a\.sh|README\.md)$")"; echo "허용 경로 밖에서 바뀐 파일: $(printf "%s" "$out" | grep -c .)"; printf "%s\n" "$out"; test -z "$out"'

echo
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
