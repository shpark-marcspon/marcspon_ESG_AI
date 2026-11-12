#!/usr/bin/env bash
# 밴드 UT1(MARC-TICK-139)의 심은 파손 여덟(발주서 §3 의 P1~P7, P2 는 계산 층·서버 안 둘): 하나씩 심고, 그것을 잡아야
# 하는 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-UT1.sh        마지막 줄 PLANTED=<잡은 수>/8
# 심기 전의 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다).
# 끝에서 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 「잡음」의 기준: 시험이 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 시험**이 FAILED 줄에 있다.
# 옛 결과 이름은 글자를 이어 붙여 심는다(저장소의 옛 이름 grep 이 이 파일에 걸리지 않게).
# 컨테이너 0, 네트워크 0, 실제 LLM 호출 0. 순수 층만 돈다. macOS 의 /bin/bash 3.2 에서 돈다.
set -u
cd "$(dirname "$0")/../../.."

A=apps/api-py
CALC="$A/esgapi/inventory/calc/scope3/calc.py"
SERIALIZE="$A/esgapi/inventory/calc/scope3/serialize.py"
T=esgapi/inventory/tests
T_CALC="$T/test_scope3_calc.py"
T_SHAPES="$T/test_flow_shapes.py"

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES="$CALC $SERIALIZE"
for f in $FILES; do
  [ -f "$f" ] || { echo "파일이 없다: $f" >&2; exit 2; }
  cp "$f" "$keep/$(echo "$f" | tr / _)"
done
sums() { # shellcheck disable=SC2086  # 파일 목록을 낱말로 나눈다
  shasum -a 256 $FILES 2>&1; }
sums > "$keep/.sums-before"
git status --porcelain > "$keep/.status-before"
restore_files() { for f in $FILES; do cp "$keep/$(echo "$f" | tr / _)" "$f"; done; }
trap 'restore_files' EXIT INT TERM

total=0; ok=0
edit() { # <파일> <있던 글자> <바꿀 글자> [all]   all 이 아니면 글자가 정확히 한 번 있어야 한다(없으면 종료 3)
  python3 -I - "$@" <<'PY'
import sys
path, old, new = sys.argv[1:4]
every = len(sys.argv) > 4 and sys.argv[4] == "all"
text = open(path, encoding="utf-8").read()
count = text.count(old)
if count == 0 or (count != 1 and not every):
    sys.exit(f"심을 자리가 {count}곳이다: {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}
pure_tests() { (cd "$A" && uv run --frozen pytest -q -rf -p no:cacheprovider -m "not django_db and not security" "$@"); }
# <번호와 설명> <로그 파일> <종료 코드> <FAILED 줄에 있어야 하는 시험 이름…>
judge() {
  local name="$1" file="$2" code="$3" caught=0 wanted
  shift 3
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|^FAILED' "$file" | sed 's/^/    /' | cut -c1-220 | head -8
  [ "$code" -ne 0 ] || caught=1
  for wanted in "$@"; do
    grep -q "^FAILED .*$wanted" "$file" || { caught=1; echo "    (FAILED 줄에 없다: $wanted)"; }
  done
  if [ "$caught" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  restore_files
}
run() { # <번호> <설명> <FAILED 줄에 있어야 하는 시험 이름…>   심은 뒤에 부른다
  local number="$1" what="$2" code
  shift 2
  pure_tests "$T_CALC" "$T_SHAPES" > "$log/$number.txt" 2>&1; code=$?
  judge "$number. $what" "$log/$number.txt" "$code" "$@"
}

TONNES_RETURN='return _Amount(mul(kg, multiplier), factor)'
DECIMAL_MODULE='__import__("esgapi.core.calc.decimal", fromlist=["mul"])'

edit "$CALC" "$TONNES_RETURN" 'return _Amount(kg, factor)' || exit 3
run P1 "÷1000 빠짐(톤 함수가 kg 을 그대로)" \
  test_activity_times_factor_is_exact_decimal 'test_tonnes_times_a_thousand_is_the_kg_product\[activity\]'

edit "$CALC" 'tonnes = _to_tonnes(mul(adjusted, value))' 'tonnes = _to_tonnes(_to_tonnes(mul(adjusted, value)).value)' || exit 3
run P2a "두 번 나눔 — 계산 층(지출 갈래만 한 번 더)" \
  'test_tonnes_times_a_thousand_is_the_kg_product\[spend\]' test_synthetic_adjustment_marks_the_result_synthetic

edit "$SERIALIZE" '"co2e": result.co2e,' \
  "\"co2e\": (lambda d: d.format_decimal(d.mul(d.parse_decimal(result.co2e), d.Decimal(1, 3))))($DECIMAL_MODULE)," || exit 3
run P2b "두 번 나눔 — 서버 안(calc_to_dict 가 한 번 더 × 0.001)" test_serializer_and_flow_carry_the_same_tonnes

edit "$SERIALIZE" '"unit": result.unit,' '"unit": result.unit, "emissions" "KgCo2e": result.co2e,' || exit 3
run P3 "옛 이름 남김(calc_to_dict 가 옛 키도 같이 냄)" \
  test_the_computed_keys_are_exactly_the_tonne_shape test_every_branch_fits

edit "$CALC" "$TONNES_RETURN" \
  "return _Amount(parse_decimal($DECIMAL_MODULE.round_decimal(mul(kg, multiplier), 6, \"half_up\")) or kg, factor)" || exit 3
# :63 의 큰 값은 소수 넷째 자리까지라 6자리 반올림에 그대로다 — 작은 값(T1)이 문다
run P4 "반올림 넣음(round_decimal 6자리 half_up)" test_tonnes_keep_every_digit_without_exponent_or_trailing_zeros

edit "$CALC" "$TONNES_RETURN" 'return _Amount(kg, factor)' || exit 3
edit "$CALC" 'co2e=format_decimal(tonnes.value),' \
  'co2e=str(__import__("decimal").Decimal(format_decimal(tonnes.value)) / 1000),' all || exit 3
run P5 "지수 표기(표준 decimal.Decimal(kg) / 1000 의 str)" test_tonnes_keep_every_digit_without_exponent_or_trailing_zeros
# 받은 글자 원문(보고에 싣는다): 0.0000001 kg × 1 을 그 식으로
(cd "$A" && uv run --frozen python -I -c 'import decimal; print("    P5 받은 글자:", str(decimal.Decimal("0.0000001") / 1000))')

edit "$CALC" 'factor = conversion_factor("kg", "tonne")' 'factor = "0.01"' || exit 3
run P6 "환산 계수를 calc.py 에 글자로 0.01" \
  test_activity_times_factor_is_exact_decimal 'test_tonnes_times_a_thousand_is_the_kg_product\[distance\]'

edit "$CALC" 'unit: Literal["tCO2eq"] = "tCO2eq"' 'unit: Literal["tCO2eq"] = "kgCO2e"  # type: ignore[assignment]' || exit 3
# unit 은 실행 중 Literal 검사가 없다 — 빨강은 꼴 검사(ValidationError)에서 나야 한다
run P7 "unit 을 kgCO2e 로" test_the_computed_keys_are_exactly_the_tonne_shape test_the_old_key_unit_or_version_is_rejected \
  test_every_branch_fits

trap - EXIT INT TERM
restore_files
sums > "$keep/.sums-after"
git status --porcelain > "$keep/.status-after"
if ! cmp -s "$keep/.sums-before" "$keep/.sums-after" || ! cmp -s "$keep/.status-before" "$keep/.status-after"; then
  echo "되돌린 뒤 지문이 다르다"
  diff "$keep/.sums-before" "$keep/.sums-after"
  diff "$keep/.status-before" "$keep/.status-after"
  exit 1
fi
echo "되돌린 뒤 지문 같음(sha256 $(echo "$FILES" | wc -w | tr -d ' ')개, git status)"
echo "PLANTED=$ok/$total"
