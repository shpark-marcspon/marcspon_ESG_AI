#!/usr/bin/env bash
# 밴드 GTE1 의 §4 자기검증(발주서 band-handoffs/GTE1-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-GTE1.sh                 전부
#   apps/api-py/scripts/section4-GTE1.sh --step 2,4      일부(번호는 발주서 §4 의 번호)
#
# 환경 변수:
#   GTE1_BASE   기준 커밋(기본: 발주서의 5cd8d78…)
#   GTE1_OUT    산출물 자리(기본: 워크트리 곁의 GTE1.out). 산출물은 $GTE1_OUT/section4/ 아래
#   GTE1_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(있으면 6 이 $BASE..HEAD 의 메시지와 함께 본다)
#   GTE1_FORBIDDEN_WORDS_FILE  기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt — 이 파일만 연다)
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${GTE1_BASE:-5cd8d780ac010427d4a014850a265697b1a04116}"
OUT="${GTE1_OUT:-$SIDE/GTE1.out}"
WORDS="${GTE1_FORBIDDEN_WORDS_FILE:-$SIDE/G1a.out/forbidden-words.txt}"
S4="$OUT/section4"
ADAPTERS="apps/api-py/esgapi/greenwash/flows/adapters.py"
T="esgapi/greenwash/tests/flows"
# 새 시험 (a)(b)(c). (c) 는 경로 셋으로 매개변수화돼 있어 모두 6 개가 돈다.
NEW_TESTS="$T/test_adapters.py::test_contrast_b_through_core_llm_is_the_same
$T/test_bridge_temperature.py::test_the_default_route_is_gpt41_mini_alone_in_the_real_config
$T/test_bridge_temperature.py::test_the_default_bridge_sends_float_zero_temperature_to_gpt41_mini
$T/test_bridge_temperature.py::test_a_route_with_a_model_that_refuses_temperature_fails_before_the_provider"
NEW_COUNT=6
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
mkdir -p "$S4"
# 키를 환경에 두고 돌리지 않는다(발주서 §1-7)
api() { (cd "$API_PY" && env -u OPENAI_API_KEY uv run --frozen "$@"); }

STEPS="all"
if [ "${1:-}" = "--step" ]; then
  STEPS=",${2:?--step 뒤에 번호},"
fi
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

changed_files() {
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u
}

# 이 밴드가 들인 글: 추적 파일은 기준 대비 더한 줄, 새 파일은 전부. 줄마다 「경로<TAB>글」.
added_lines() {
  git -C "$ROOT" diff -U0 "$BASE" | awk '
    /^\+\+\+ / { f = substr($0, 7); next }
    /^\+/ { print f "\t" substr($0, 2) }'
  git -C "$ROOT" ls-files -o --exclude-standard --full-name | while IFS= read -r f; do
    [ -f "$ROOT/$f" ] && awk -v f="$f" '{ print f "\t" $0 }' "$ROOT/$f"
  done
}

# §1 의 닫힌 목록(동작은 adapters.py 하나, 시험 둘, 이 밴드의 스크립트 둘)
ALLOWED='^(apps/api-py/esgapi/greenwash/flows/adapters\.py|apps/api-py/esgapi/greenwash/tests/flows/test_(adapters|bridge_temperature)\.py|apps/api-py/scripts/(section4|planted-breaks)-GTE1\.sh)$'

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse HEAD), 산출물 $S4"

if want 1; then
  api pytest -q -p no:cacheprovider esgapi/greenwash > "$S4/pytest-greenwash.log" 2>&1
  e=$?
  tail -1 "$S4/pytest-greenwash.log" | sed 's/^/    /'
  report 1 "greenwash 시험 전부" "$e"
fi

if want 2; then
  # shellcheck disable=SC2086
  api pytest -q -p no:cacheprovider -rA $NEW_TESTS > "$S4/pytest-new.log" 2>&1
  e=$?
  passed=$(grep -c '^PASSED ' "$S4/pytest-new.log")
  tail -1 "$S4/pytest-new.log" | sed 's/^/    /'
  echo "    이름으로 돈 새 시험 PASSED $passed / $NEW_COUNT"
  report 2 "새 시험 (a)(b)(c)" "$([ "$e" = 0 ] && [ "$passed" = "$NEW_COUNT" ] && echo 0 || echo 1)"
fi

if want 3; then
  changed_files > "$S4/changed-files.txt"
  outside=$(grep -Ev "$ALLOWED" "$S4/changed-files.txt")
  n=$(grep -c . "$S4/changed-files.txt")
  echo "    바뀐 파일 $n, 허용 밖 $( [ -n "$outside" ] && echo "$outside" | grep -c . || echo 0)"
  sed 's/^/    바뀜: /' "$S4/changed-files.txt"
  [ -n "$outside" ] && echo "$outside" | sed 's/^/    밖: /'
  report 3 "바뀐 경로가 §1-6 안" "$([ -z "$outside" ] && echo 0 || echo 1)"
fi

if want 4; then
  git -C "$ROOT" diff -U0 "$BASE" -- "$ADAPTERS" | grep '^+' | grep -v '^+++' | cut -c2- > "$S4/adapters-added.txt"
  temps=$(grep -E 'temperature *=' "$S4/adapters-added.txt")
  ntemp=$(grep -cE 'temperature *=' "$ROOT/$ADAPTERS")
  from_checker=$(grep -cxE ' *temperature=checker_mod\.TEMPERATURE,' "$ROOT/$ADAPTERS")
  # 숫자 리터럴 0 / 0.0 (int·float, bool 아님)의 AST 개수를 기준과 견준다 — 늘었으면 새로 적은 것(docstring 글은 세지 않는다)
  git -C "$ROOT" show "$BASE:$ADAPTERS" > "$S4/adapters-base.py"
  literals=$(api python - "$S4/adapters-base.py" "$ROOT/$ADAPTERS" <<'PY2'
import ast
import sys


def zeros(path: str) -> int:
    tree = ast.parse(open(path, encoding="utf-8").read())
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float) and node.value == 0
    )


print(zeros(sys.argv[2]) - zeros(sys.argv[1]))
PY2
)
  rm -f "$S4/adapters-base.py"
  imports=$(grep -cE '^from esgapi\.greenwash\.calc import checker as checker_mod$' "$S4/adapters-added.txt")
  other_imports=$(grep -E '^(from|import) ' "$S4/adapters-added.txt" | grep -vcE '^from esgapi\.greenwash\.calc import checker as checker_mod$')
  echo "    더한 temperature= 줄: $(echo "$temps" | sed 's/^ *//' | tr '\n' ' ')"
  echo "    파일의 temperature= $ntemp (checker_mod.TEMPERATURE 에서 $from_checker) · 숫자 0 리터럴(기준 대비 AST) $literals · checker import $imports · 다른 새 import $other_imports"
  report 4 "temperature 의 원천이 checker 하나" \
    "$([ "$ntemp" = 1 ] && [ "$from_checker" = 1 ] && [ "$literals" = 0 ] && [ "$imports" = 1 ] && [ "$other_imports" = 0 ] && echo 0 || echo 1)"
fi

if want 5; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" env -u OPENAI_API_KEY scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" env -u OPENAI_API_KEY scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  gates=$(grep '^GATES=' "$S4/check-gates.log" | tail -1)
  echo "    $last / $gates (종료 $e)"
  report 5 "verify.sh --fast · check-gates" "$([ "$last" = "VERIFY_FAST=PASS" ] && [ "$e" = 0 ] && echo 0 || echo 1)"
fi

if want 6; then
  added_lines > "$S4/added-lines.txt"
  nl=$(grep -c . "$S4/added-lines.txt")
  hits=0
  : > "$S4/forbidden-hits.txt"
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록이 없다: $WORDS"; hits=1
  else
    hits=$(cut -f2- "$S4/added-lines.txt" | grep -F -i -c -f "$WORDS")
    [ "$hits" = 0 ] || awk -F'\t' '{print $1}' "$S4/added-lines.txt" | sort -u | while IFS= read -r f; do
      grep -F "$f	" "$S4/added-lines.txt" | cut -f2- | grep -F -i -q -f "$WORDS" && echo "$f" >> "$S4/forbidden-hits.txt"
    done
  fi
  mhits=0
  msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
  draft="${GTE1_COMMIT_MSG_FILE:-}"
  if [ -n "$draft" ]; then
    if [ -f "$draft" ]; then msgs="$msgs
$(cat "$draft")"; else echo "    커밋 메시지 초안이 없다: $draft"; mhits=1; fi
  fi
  if [ -n "$msgs" ] && [ -f "$WORDS" ] && printf '%s' "$msgs" | grep -F -i -q -f "$WORDS"; then mhits=1; fi
  keys=$( { cut -f2- "$S4/added-lines.txt"; printf '%s\n' "$msgs"; } | grep -E -c 'sk-[A-Za-z0-9_-]{20,}')
  # 찾는 글 자체가 든 이 밴드의 두 스크립트는 키 파일 경로 검사에서 뺀다
  opens=$( { grep -vE '^apps/api-py/scripts/(section4|planted-breaks)-GTE1\.sh	' "$S4/added-lines.txt" | cut -f2-; printf '%s\n' "$msgs"; } \
    | grep -E -c 'manufac-erp|spike/\.env|marcspon-openai\.env')
  nmsg=$(git -C "$ROOT" rev-list --count "$BASE..HEAD")
  echo "    낱말 $( [ -f "$WORDS" ] && grep -c . "$WORDS" || echo 0)개로 본 더한 줄 $nl: 걸린 줄 $hits, 커밋 메시지($nmsg 개, $BASE..HEAD${draft:+ + 초안 ${draft##*/}}) $mhits"
  echo "    키 꼴 $keys, 키 파일 경로 $opens"
  sed 's/^/    걸린 파일: /' "$S4/forbidden-hits.txt"
  report 6 "기업명·키" "$([ "$hits$mhits$keys$opens" = 0000 ] && echo 0 || echo 1)"
fi

if want 7; then
  (cd "$API_PY" && GTE1_OUT="$OUT" GTE1_BASE="$BASE" scripts/planted-breaks-GTE1.sh) > "$S4/planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/planted.log" | sed 's/^/    /'
  report 7 "GTE1 심은 파손" "$([ "$e" = 0 ] && grep -q '^PLANTED=3/3$' "$S4/planted.log" && grep -q '^FINGERPRINT=same' "$S4/planted.log" && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
