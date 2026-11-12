#!/usr/bin/env bash
# 심은 파손(발주서 MARC-TICK-50 §3): 코드를 일부러 틀리게 고치고, 테스트·계약이 그것을 잡는지 본다.
#   사용: apps/api-py/esgapi/inventory/tests/planted-breaks-PY4.sh
# 파손마다: 파일을 임시 폴더에 베껴 두고 → 한 군데를 고치고 → 검사를 돌리고 → 베껴 둔 것으로 되돌린다(git 을 쓰지 않는다).
# 검사가 실패해야(종료 코드 ≠ 0) 「잡았다」다. 마지막 줄이 PLANTED=8/8 이어야 한다. 끝나면 작업 트리는 처음 그대로다.
# 컨테이너가 필요 없다(순수 층과 lint-imports 만 돌린다). 속성 테스트는 시간 때문에 뺀다(파손을 잡는 것은 다른 테스트다).
set -u
cd "$(dirname "$0")/../../.."
KEEP="$(mktemp -d)"
trap 'rm -rf "$KEEP"' EXIT
CAUGHT=0
TOTAL=0

PURE='uv run pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi/inventory --ignore=esgapi/inventory/tests/test_property.py'
# 십진 커널은 밴드 PY8a 가 esgapi/core/calc/decimal.py 로 옮겼다. 그 테스트도 core 에 있다.
KERNEL='uv run pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi/core/tests/test_calc_decimal.py'
LINT='uv run lint-imports'

plant() { # <번호> <설명> <파일> <찾을 글자> <바꿀 글자> <검사 명령> <기대하는 실패의 글자(grep -E)>
  local n="$1" what="$2" file="$3" find="$4" replace="$5" check="$6" expect="$7"
  TOTAL=$((TOTAL + 1))
  cp "$file" "$KEEP/original"
  if ! FIND="$find" REPLACE="$replace" python3 - "$file" <<'PY'
import os, sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
find, replace = os.environ["FIND"], os.environ["REPLACE"]
if text.count(find) != 1:
    sys.exit(f"찾을 글자가 {text.count(find)}번 나온다(1번이어야 한다): {find!r}")
open(path, "w", encoding="utf-8").write(text.replace(find, replace))
PY
  then
    cp "$KEEP/original" "$file"
    echo "PLANT $n: ★ 심지 못했다 — $what"
    return
  fi
  local out status
  out="$(eval "$check" 2>&1)"
  status=$?
  cp "$KEEP/original" "$file"
  if [ "$status" -ne 0 ] && printf '%s' "$out" | grep -q -E "$expect"; then
    CAUGHT=$((CAUGHT + 1))
    echo "PLANT $n: 잡았다 (exit=$status) — $what"
    printf '%s\n' "$out" | grep -E "$expect|^[0-9]+ failed|Contracts:|is not allowed to import|BROKEN" | head -6 | sed 's/^/    /'
  else
    echo "PLANT $n: ★ 못 잡았다 (exit=$status) — $what"
    printf '%s\n' "$out" | tail -5 | sed 's/^/    /'
  fi
}

echo "── 심기 전: 깨끗한 트리에서 두 검사가 통과하는가"
( eval "$LINT" ) >/dev/null 2>&1; echo "lint-imports EXIT=$?"
( eval "$PURE" ) 2>&1 | tail -1; echo "pure EXIT=${PIPESTATUS[0]}"
BEFORE="$(git status --porcelain | shasum | cut -d' ' -f1)-$(cat esgapi/inventory/calc/*.py esgapi/inventory/*.py | shasum | cut -d' ' -f1)"
echo

# ── 층 ──
plant 1 "calc/calc.py 에 import django → 계약 다" \
  esgapi/inventory/calc/calc.py \
  'from collections.abc import Sequence' \
  'import django  # noqa: F401
from collections.abc import Sequence' \
  "$LINT" 'esgapi\.inventory\.calc is not allowed to import django'

plant 2 "api.py 가 남의 models 를 직접 import → 계약 나·라" \
  esgapi/inventory/api.py \
  'from esgapi.inventory import services' \
  'from esgapi.accounts.models import TenantRow  # noqa: F401
from esgapi.inventory import services' \
  "$LINT" 'Contracts: 2 kept, 2 broken'

# ── 동작 ──
plant 3 "산화계수를 CH4·N2O 에도 곱한다 → 검산 사례" \
  esgapi/inventory/calc/calc.py \
  'if gas == "CO2" and oxidation is not None:' \
  'if oxidation is not None:' \
  "$PURE" 'FAILED .*test_handcalc.py::test_hand_calculated_case'

plant 4 "이미 환산된 계수(CO2e)에 GWP 를 곱한다 → 구매 전력·열 테스트" \
  esgapi/inventory/calc/calc.py \
  '        gas = _as_gas(ef.gas)
' \
  '        gas = _as_gas(ef.gas) or "CH4"
' \
  "$PURE" 'FAILED .*test_calc.py::test_pre_aggregated_co2e_factor_is_not_multiplied_by_gwp'

plant 5 "반올림 half_up 을 half_even 처럼 → 반올림 표" \
  esgapi/core/calc/decimal.py \
  '            if twice_remainder >= divisor:' \
  '            if twice_remainder > divisor or (twice_remainder == divisor and quotient % 2 == 1):' \
  "$KERNEL" 'FAILED .*test_calc_decimal.py::test_rounding'

plant 6 "단위 환산의 역방향을 허용한다 → unit_conversion_not_found 테스트" \
  esgapi/inventory/calc/units.py \
  'matches = [c for c in table if c.from_unit == from_unit and c.to_unit == to_unit]' \
  'matches = [c for c in table if {c.from_unit, c.to_unit} == {from_unit, to_unit}]' \
  "$PURE" 'FAILED .*test_calc.py::test_the_reverse_direction_is_not_derived'

plant 7 "정규화를 뺀다(1.50 이 1.5 가 되지 않는다) → 문자열 동등 테스트" \
  esgapi/core/calc/decimal.py \
  '    while scale > 0 and coef % 10 == 0:' \
  '    while False:' \
  "$KERNEL" 'FAILED .*test_calc_decimal.py::test_notation_is_normalized'

plant 8 "단계의 conversion 을 「키 없음」 대신 null 로 내보낸다 → 골든" \
  esgapi/inventory/calc/serialize.py \
  '    if step.conversion is not None:
        out["conversion"] = unit_conversion_to_dict(step.conversion)' \
  '    out["conversion"] = None if step.conversion is None else unit_conversion_to_dict(step.conversion)' \
  "$PURE" 'FAILED .*test_golden.py::test_pure_output_equals_the_ts_engine_letter_for_letter'

echo
echo "── 되돌린 뒤: 트리가 처음 그대로인가, 두 검사가 다시 통과하는가"
AFTER="$(git status --porcelain | shasum | cut -d' ' -f1)-$(cat esgapi/inventory/calc/*.py esgapi/inventory/*.py | shasum | cut -d' ' -f1)"
[ "$BEFORE" = "$AFTER" ] && echo "tree unchanged" || echo "★ 트리가 달라졌다"
( eval "$LINT" ) >/dev/null 2>&1; echo "lint-imports EXIT=$?"
( eval "$PURE" ) 2>&1 | tail -1; echo "pure EXIT=${PIPESTATUS[0]}"
echo "PLANTED=$CAUGHT/$TOTAL"
[ "$CAUGHT" = "$TOTAL" ] && [ "$BEFORE" = "$AFTER" ]
