#!/usr/bin/env bash
# 밴드 MUT1(MARC-TICK-92)의 심은 파손 넷: 변이 시험(MUT0)이 살아남은 변이로 찾은 G1~G4 를 손으로 하나씩 심고,
# 이 밴드의 새 테스트가 그것을 잡는지(빨개지는지) 본다.
#   사용: apps/api-py/scripts/planted-breaks-MUT1.sh        마지막 줄 PLANTED=<잡은 수>/4
# 파손마다: 제품 파일을 저장소 밖 임시 폴더에 베껴 두고 → 한 군데를 고치고 → 새 테스트를 돌리고 → 베껴 둔 것으로
# 되돌린다(git 을 쓰지 않는다. 도중에 죽어도 trap 이 되돌린다). 「잡음」= 종료 ≠ 0 이고 적어 둔 테스트가 FAILED 로 찍힘.
# 끝에서 두 calc 폴더의 `git diff` 가 비었는지, `git status --porcelain` 이 처음과 같은지 잰다.
# 컨테이너 0, 네트워크 0. bash 전용이다.
set -u
cd "$(dirname "$0")/.."

KEEP="$(mktemp -d)"   # 저장소 밖
CURRENT=""            # 지금 심은 파일(되돌릴 것)
restore() { if [ -n "$CURRENT" ]; then cp "$KEEP/original" "$CURRENT"; CURRENT=""; fi; }
trap 'restore; rm -rf "$KEEP"' EXIT INT TERM
CAUGHT=0
TOTAL=0

NEW='uv run --frozen pytest -q -p no:cacheprovider esgapi/core/tests/calc esgapi/inventory/tests/calc'
PRODUCT='esgapi/inventory/calc esgapi/core/calc'

plant() { # <번호> <설명> <파일> <찾을 글자> <바꿀 글자> <기대하는 실패의 글자(grep -E)>
  local n="$1" what="$2" file="$3" find="$4" replace="$5" expect="$6"
  TOTAL=$((TOTAL + 1))
  cp "$file" "$KEEP/original"
  CURRENT="$file"
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
    restore
    echo "PLANT $n: ★ 심지 못했다 — $what"
    return
  fi
  local out status
  out="$(eval "$NEW" 2>&1)"
  status=$?
  restore
  if [ "$status" -ne 0 ] && printf '%s' "$out" | grep -q -E "$expect"; then
    CAUGHT=$((CAUGHT + 1))
    echo "PLANT $n: 잡았다 EXIT=$status — $what"
    printf '%s\n' "$out" | grep -E "^FAILED|^[0-9]+ failed" | head -8 | sed 's/^/    /'
  else
    echo "PLANT $n: ★ 못 잡았다 EXIT=$status — $what"
    printf '%s\n' "$out" | tail -5 | sed 's/^/    /'
  fi
}

echo "── 심기 전: 새 테스트가 원본에서 초록인가"
( eval "$NEW" ) 2>&1 | tail -1
BASE_EXIT=${PIPESTATUS[0]}
echo "clean EXIT=$BASE_EXIT"
if [ "$BASE_EXIT" -ne 0 ]; then
  echo "★ 심기 전부터 빨갛다 — PLANTED 를 내지 않는다"
  exit 1
fi
BEFORE="$(git status --porcelain | shasum | cut -d' ' -f1)"
echo

plant G1 "구매 계수의 기체 구성 검사 and → or (기체 넷이 통과)" \
  esgapi/inventory/calc/calc.py \
  'per_gas = len(listed) == len(GASES) and all(' \
  'per_gas = len(listed) == len(GASES) or all(' \
  'FAILED .*tests/calc/test_calc.py::test_a_purchased_factor_must_list_exactly'

plant G2 "0 을 채우는 가지의 지수 digits - scale → digits + scale" \
  esgapi/core/calc/decimal.py \
  'coef = d.coef * 10 ** (digits - d.scale)' \
  'coef = d.coef * 10 ** (digits + d.scale)' \
  'FAILED .*tests/calc/test_decimal.py::test_a_value_with_fewer_decimals_than_digits_is_padded'

plant G3 "끝의 부호 판정 negative = coef < 0 → None" \
  esgapi/core/calc/decimal.py \
  '    negative = coef < 0
' \
  '    negative = None
' \
  'FAILED .*tests/calc/test_decimal.py::test_a_negative_value_below_one_in_magnitude'

plant G4 "에너지 환산의 실패를 버리고 늘 첫 길의 실패(as_quantity)를 돌려줌" \
  esgapi/inventory/calc/calc.py \
  'return as_quantity if as_energy.failure.kind == "unit_conversion_not_found" else as_energy' \
  'return as_quantity' \
  'FAILED .*tests/calc/test_calc.py::test_an_ambiguous_usage_to_energy_conversion'

echo
echo "── 되돌린 뒤: 제품 파일이 처음 그대로인가, 새 테스트가 다시 초록인가"
AFTER="$(git status --porcelain | shasum | cut -d' ' -f1)"
DIFF="$(git diff --stat -- $PRODUCT)"
[ -z "$DIFF" ] && echo "product git diff --stat: 0" || { echo "★ 제품 파일이 달라졌다"; echo "$DIFF"; }
[ "$BEFORE" = "$AFTER" ] && echo "status unchanged" || echo "★ git status 가 달라졌다"
( eval "$NEW" ) 2>&1 | tail -1
echo "clean EXIT=${PIPESTATUS[0]}"
echo "PLANTED=$CAUGHT/$TOTAL"
[ "$CAUGHT" = "$TOTAL" ] && [ "$BEFORE" = "$AFTER" ] && [ -z "$DIFF" ]
