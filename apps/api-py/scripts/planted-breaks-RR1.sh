#!/usr/bin/env bash
# 밴드 RR1(MARC-TICK-145)의 심은 파손 일곱(발주서 §3 의 P1~P7): 하나씩 심고, 그것을 잡아야 하는 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-RR1.sh        마지막 줄 PLANTED=<잡은 수>/7
# 심기 전의 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다).
# 끝에서 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 「잡음」의 기준: 시험이 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 필수 시험**이 전부 FAILED 줄에 있다.
# 같이 빨개지기를 기대하는 시험(P4·P7 의 「같이 빨강」)은 「같이:」 줄로 적기만 하고 잡음의 기준에 넣지 않는다.
# 업무 층(T2·T3)은 compose 의 Postgres 가 떠 있어야 한다(apps/api-py/scripts/test-business.sh). 앱·워커 컨테이너 0.
# 옛 판 이름은 글자를 이어 붙여 심는다(저장소의 옛 판 글자 검사가 이 파일에 걸리지 않게).
# 네트워크 0, 실제 LLM 호출 0. macOS 의 /bin/bash 3.2 에서 돈다.
set -u
cd "$(dirname "$0")/../../.."

A=apps/api-py
I="$A/esgapi/inventory"
SHAPES="$I/flows/shapes.py"
ROUTE="$I/service/schemas/inventory.py"
FLOW="$I/flows/scope12.py"
T=esgapi/inventory/tests
PURE="$T/test_route_shapes.py $T/test_flow_shapes.py $T/test_flows.py $T/flows/test_shapes.py esgapi/config/tests/test_api_contract.py"
BUSINESS="$T/test_route_bodies.py $T/test_route_shapes.py"

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES="$SHAPES $ROUTE $FLOW"
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
edit() { # <파일> <있던 글자> <바꿀 글자>   글자가 정확히 한 번 있어야 한다(아니면 종료 3)
  python3 -I - "$@" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
count = text.count(old)
if count != 1:
    sys.exit(f"심을 자리가 {count}곳이다: {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}
# shellcheck disable=SC2086  # 시험 목록을 낱말로 나눈다
tests() { # 순수 층과 업무 층을 다 돌린다. 종료 코드는 둘 가운데 0 이 아닌 것
  local pure business
  (cd "$A" && uv run --frozen pytest -q -rf -p no:cacheprovider -m "not django_db and not security" $PURE); pure=$?
  "$A/scripts/test-business.sh" -rf -p no:cacheprovider $BUSINESS; business=$?
  [ "$pure" -eq 0 ] && return "$business"
  return "$pure"
}
# <번호와 설명> <로그 파일> <종료 코드> <같이 빨강 기대(쉼표, 없으면 -)> <FAILED 줄에 있어야 하는 시험 이름…>
judge() {
  local name="$1" file="$2" code="$3" also="$4" caught=0 wanted
  shift 4
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|[0-9]+ (passed|failed)|^FAILED' "$file" | sed 's/^/    /' | cut -c1-220 | head -14
  [ "$code" -ne 0 ] || caught=1
  for wanted in "$@"; do
    grep -q "^FAILED .*$wanted" "$file" || { caught=1; echo "    (FAILED 줄에 없다: $wanted)"; }
  done
  if [ "$also" != "-" ]; then
    for wanted in $(echo "$also" | tr ',' ' '); do
      if grep -q "^FAILED .*$wanted" "$file"; then echo "    같이: $wanted 빨강"; else echo "    같이: $wanted 초록"; fi
    done
  fi
  if [ "$caught" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  restore_files
}
run() { # <번호> <설명> <같이 빨강 기대> <필수 시험 이름…>   심은 뒤에 부른다
  local number="$1" what="$2" also="$3" code
  shift 3
  tests > "$log/$number.txt" 2>&1; code=$?
  judge "$number. $what" "$log/$number.txt" "$code" "$also" "$@"
}

edit "$SHAPES" '{"kind": Literal["unit_conversion_not_found"], "from": str, "to": str, "context": str}' \
  '{"from": str, "to": str, "kind": Literal["unit_conversion_not_found"], "context": str}' || exit 3
edit "$SHAPES" '{"kind": Literal["unit_conversion_ambiguous"], "from": str, "to": str, "factors": list[str]}' \
  '{"from": str, "to": str, "kind": Literal["unit_conversion_ambiguous"], "factors": list[str]}' || exit 3
run P1 "실패 둘을 다시 from·to·kind 차례로" - \
  'test_every_reachable_failure_body_is_the_serializer_bytes\[unit_conversion_not_found\]' \
  'test_every_reachable_failure_body_is_the_serializer_bytes\[unit_conversion_ambiguous\]' \
  'test_the_json_schema_is_pinned\[scope12'

edit "$SHAPES" '    calorific: Tier
    co2: Tier
    nonCo2: Tier
    oxidation: Tier | None' '    calorific: int
    co2: int
    nonCo2: int
    oxidation: int | None' || exit 3
run P2 "산정등급을 int 로" - test_a_tier_outside_one_to_four_is_rejected test_committed_openapi_matches_the_code

edit "$ROUTE" '    llm: shapes.LlmFailureJson' '    llm: Scope3LlmFailureOut' || exit 3
edit "$ROUTE" 'class Scope3GroupClassifiedOut(Schema):' 'class Scope3LlmFailureOut(Schema):
    kind: str
    detail: str


class Scope3GroupClassifiedOut(Schema):' || exit 3
run P3 "쌍둥이 하나(Scope3LlmFailureOut)를 되살려 llm 에 씀" - \
  test_the_routes_use_the_result_shapes_themselves test_the_route_file_declares_only_requests_and_route_only_shapes

edit "$SHAPES" '@with_config(FORBID)
class RowOkJson(TypedDict):' '@with_config(ConfigDict(extra="ignore"))
class RowOkJson(TypedDict):' || exit 3
run P4 "RowOkJson 의 FORBID 를 extra=ignore 로" \
  'test_the_json_schema_is_pinned\[scope12,test_a_missing_or_extra_key_is_rejected,test_committed_openapi_matches_the_code' \
  test_an_unknown_key_in_an_ok_row_is_500_and_not_leaked

edit "$SHAPES" '@with_config(FORBID)
class EnergyJson(TypedDict):
    value: str
    unit: str
' '@with_config(FORBID)
class Item(TypedDict):
    value: str
    unit: str


EnergyJson = Item
' || exit 3
# 이름만 그린워싱 components 의 것(Item)으로 — 참조는 옛 이름으로 살려 둔다(NameError 로 먼저 깨지지 않게)
run P5 "응답에 닿는 TypedDict 하나(EnergyJson)의 이름을 Item 으로" - test_no_two_shapes_share_a_components_name

edit "$SHAPES" '    co2e: Annotated[str, Field(description="반올림하지 않은 정확한 값 (tCO2eq)")]' '    co2e: str' || exit 3
run P6 "RowOkJson.co2e 의 설명을 지움" - test_the_descriptions_kept_their_letters

edit "$FLOW" 'RESULT_SHAPE: Final = "scope12.result@2"' 'RESULT_SHAPE: Final = "scope12.result@" + "1"' || exit 3
# T6 은 RESULT_SHAPES 를 보므로 초록 그대로가 기대
run P7 "흐름의 판을 옛 판으로" \
  'test_the_version_is_two_and_the_old_one_is_gone,test_a_tier_outside_one_to_four_is_rejected,test_the_result_is_the_body_with_schema_version_first' \
  test_scope12_flow_equals_the_calc_path test_every_registered_shape_is_pinned

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
