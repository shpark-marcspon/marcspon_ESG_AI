#!/usr/bin/env bash
# 밴드 GT1 의 §4 자기검증(발주서 band-handoffs/GT1-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-GT1.sh                 전부
#   apps/api-py/scripts/section4-GT1.sh --step 3,4,5    일부(번호는 발주서 §4 의 번호)
#
# 환경 변수:
#   GT1_BASE   기준 커밋(기본: 착수 때 적은 e646b27…)
#   GT1_OUT    산출물 자리(기본: 워크트리 곁의 GT1.out). 산출물은 $GT1_OUT/section4/ 아래
#   GT1_NODEIDS_BEFORE  기준에서 뽑은 노드 id 목록(기본: $GT1_OUT/nodeids-before.txt — 발주서 §2-1 이 착수 때 뽑음)
#   GT1_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(있으면 10 이 $BASE..HEAD 의 메시지와 함께 본다)
#   GT1_FORBIDDEN_WORDS_FILE  기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt — 이 파일만 연다)
# 컨테이너를 띄우지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${GT1_BASE:-e646b27496832b5d3fe94d30d1c6be471606064f}"
OUT="${GT1_OUT:-$SIDE/GT1.out}"
BEFORE="${GT1_NODEIDS_BEFORE:-$OUT/nodeids-before.txt}"
WORDS="${GT1_FORBIDDEN_WORDS_FILE:-$SIDE/G1a.out/forbidden-words.txt}"
S4="$OUT/section4"
E="apps/api-py/esgapi/greenwash"
T="$E/tests"
OLD1="$T/test_contracts_gc1.py"
OLD2="$T/test_contracts_gc2.py"
NEW1="$T/test_contracts_shapes_paths.py"
NEW2="$T/test_contracts_review_report_terms.py"
CONTRACT="apps/api-py/esgapi/config/tests/test_api_contract.py"
NODES=87
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
mkdir -p "$S4"
api() { (cd "$API_PY" && uv run --frozen "$@"); }

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

# 바뀐 파일(커밋된 것 + 작업 트리 + 새 파일), 저장소 뿌리 기준 경로. 지워진 파일(옮김의 옛 자리)도 든다.
changed_files() {
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-2 의 닫힌 목록
ALLOWED='^(apps/api-py/esgapi/greenwash/tests/test_contracts_(gc1|gc2|shapes_paths|review_report_terms)\.py|apps/api-py/esgapi/config/tests/test_api_contract\.py|apps/api-py/scripts/(section4|planted-breaks)-GT1\.sh)$'

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse HEAD), 산출물 $S4"

if want 1; then
  changed_files > "$S4/changed-files.txt"
  outside=$(grep -Ev "$ALLOWED" "$S4/changed-files.txt")
  n=$(grep -c . "$S4/changed-files.txt")
  echo "    바뀐 파일 $n, 허용 밖 $( [ -n "$outside" ] && echo "$outside" | grep -c . || echo 0)"
  [ -n "$outside" ] && echo "$outside" | sed 's/^/    밖: /'
  # test_api_contract.py 는 한 줄만(지운 줄 1·더한 줄 1)
  cn=$(git -C "$ROOT" diff --numstat "$BASE" -- "$CONTRACT" | awk '{print $1 "+" $2 "-"}')
  echo "    $CONTRACT: ${cn:-0+0-}"
  # 옮김의 옛 자리가 작업 트리에 남아 있으면(추적 밖 사본 포함) 빨강
  left=0
  for f in "$OLD1" "$OLD2"; do
    if [ -e "$ROOT/$f" ]; then echo "    옛 자리가 남아 있다: $f"; left=$((left + 1)); fi
  done
  ok=1
  [ -z "$outside" ] && [ "$cn" = "1+1-" ] && [ "$left" = 0 ] && ok=0
  report 1 "허용 경로" "$ok"
fi

if want 2; then
  git -C "$ROOT" diff -M --name-status "$BASE" > "$S4/name-status.txt"
  r1=$(awk -F'\t' -v o="$OLD1" -v n="$NEW1" '$1 ~ /^R/ && $2 == o && $3 == n {print substr($1, 2) + 0}' "$S4/name-status.txt")
  r2=$(awk -F'\t' -v o="$OLD2" -v n="$NEW2" '$1 ~ /^R/ && $2 == o && $3 == n {print substr($1, 2) + 0}' "$S4/name-status.txt")
  echo "    $OLD1 → $NEW1: 유사도 ${r1:-(rename 아님)}%"
  echo "    $OLD2 → $NEW2: 유사도 ${r2:-(rename 아님)}%"
  ok=1
  [ -n "$r1" ] && [ -n "$r2" ] && [ "$r1" -ge 90 ] && [ "$r2" -ge 90 ] && ok=0
  report 2 "옮김(rename 둘, 유사도 90% 이상)" "$ok"
fi

if want 3; then
  : > "$S4/ast.txt"
  bad=0
  for pair in "$OLD1:$NEW1" "$OLD2:$NEW2" "$CONTRACT:$CONTRACT"; do
    old="${pair%%:*}"; new="${pair#*:}"
    git -C "$ROOT" show "$BASE:$old" > "$S4/ast-base.py"
    r=$(api python - "$S4/ast-base.py" "$ROOT/$new" <<'PY'
import ast
import sys


def strip(path: str) -> str:
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:]
    return ast.dump(tree, include_attributes=False)


print("same" if strip(sys.argv[1]) == strip(sys.argv[2]) else "DIFF")
PY
)
    echo "$old → $new $r" >> "$S4/ast.txt"
    echo "    기준 ${old##*/} ↔ 지금 ${new##*/}: docstring 뺀 AST $r"
    [ "$r" = "same" ] || bad=$((bad + 1))
  done
  rm -f "$S4/ast-base.py"
  report 3 "동작 0줄(docstring 뺀 AST)" "$([ "$bad" = 0 ] && echo 0 || echo 1)"
fi

if want 4; then
  git -C "$ROOT" grep -n 'test_contracts_gc[12]' -- ':(exclude)apps/api-py/scripts' > "$S4/old-names.txt"
  old_n=$(grep -c . "$S4/old-names.txt")
  [ "$old_n" = 0 ] || sed 's/^/    옛 이름: /' "$S4/old-names.txt"
  c1=$(grep -c 'test_contracts_shapes_paths\.py' "$ROOT/$CONTRACT")
  c2=$(grep -c 'test_contracts_shapes_paths\.py' "$ROOT/$NEW2")
  c3=$(grep -c 'test_contracts_review_report_terms\.py' "$ROOT/$NEW1")
  echo "    옛 이름(scripts/ 밖, 추적 파일) $old_n · shapes_paths 를 test_api_contract 가 $c1 · review_report_terms 가 $c2 · review_report_terms 를 shapes_paths 가 $c3"
  # 머리말(「정한 것」 3): 첫 줄이 내용 이름으로 시작하고, 밴드 이름은 「…에서 생김」 꼬리 한 번만
  h1=$(head -1 "$ROOT/$NEW1" | grep -c '^"""그린워싱 계약 — ')
  h2=$(head -1 "$ROOT/$NEW2" | grep -c '^"""그린워싱 계약 — ')
  t1=$(grep -c '(GC1 `MARC-TICK-95` 에서 생김)' "$ROOT/$NEW1")
  t2=$(grep -c '(GC2 `MARC-TICK-104` 에서 생김)' "$ROOT/$NEW2")
  ob=$(cat "$ROOT/$NEW1" "$ROOT/$NEW2" | grep -c '밴드 GC[12] 의 계약\|GC1 의 꼴을 따른다')
  echo "    머리말 첫 줄 「그린워싱 계약 —」 ${NEW1##*/} $h1 · ${NEW2##*/} $h2 · 꼬리 GC1 $t1 · GC2 $t2 · 옛 머리말 글 $ob"
  ok=1
  [ "$old_n" = 0 ] && [ "$c1" -ge 1 ] && [ "$c2" -ge 1 ] && [ "$c3" -ge 1 ] \
    && [ "$h1$h2$t1$t2$ob" = 11110 ] && ok=0
  report 4 "옛 이름 0·새 이름 세 쌍" "$ok"
fi

if want 5; then
  api pytest -q --collect-only -p no:cacheprovider "${NEW1#apps/api-py/}" "${NEW2#apps/api-py/}" 2>&1 \
    | grep '::' > "$S4/nodeids-after.txt"
  n=$(grep -c . "$S4/nodeids-after.txt")
  ok=1
  if [ ! -f "$BEFORE" ]; then
    echo "    기준 노드 id 목록이 없다: $BEFORE"
  else
    nb=$(grep -c . "$BEFORE")
    sed -e 's#test_contracts_gc1\.py#test_contracts_shapes_paths.py#' -e 's#test_contracts_gc2\.py#test_contracts_review_report_terms.py#' \
      "$BEFORE" > "$S4/nodeids-before-renamed.txt"
    if diff "$S4/nodeids-before-renamed.txt" "$S4/nodeids-after.txt" > "$S4/nodeids.diff"; then same=same; else same=DIFF; fi
    echo "    노드 기준 $nb · 지금 $n (기대 $NODES) · 옛 이름을 새 이름으로 바꾼 기준 ↔ 지금: $same"
    [ "$same" = DIFF ] && head -5 "$S4/nodeids.diff" | sed 's/^/    /'
    [ "$nb" = "$NODES" ] && [ "$n" = "$NODES" ] && [ "$same" = same ] && ok=0
  fi
  report 5 "노드 수·노드 id" "$ok"
fi

if want 6; then
  api python scripts/check_test_layout.py --list > "$S4/test-layout.txt" 2>&1
  e=$?
  head -1 "$S4/test-layout.txt" | sed 's/^/    /'
  f1=$(grep -cF -x "  자유  ${NEW1#apps/api-py/}" "$S4/test-layout.txt")
  f2=$(grep -cF -x "  자유  ${NEW2#apps/api-py/}" "$S4/test-layout.txt")
  echo "    종료 $e · ${NEW1##*/} 자유 $f1 · ${NEW2##*/} 자유 $f2"
  report 6 "테스트 자리(check_test_layout)" "$([ "$e" = 0 ] && [ "$f1" = 1 ] && [ "$f2" = 1 ] && echo 0 || echo 1)"
fi

if want 7; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  gates=$(grep '^GATES=' "$S4/check-gates.log" | tail -1)
  echo "    $last / $gates (종료 $e)"
  report 7 "verify.sh --fast · check-gates" "$([ "$last" = "VERIFY_FAST=PASS" ] && [ "$e" = 0 ] && echo 0 || echo 1)"
fi

if want 8; then
  rm -f "$S4/netlog.txt"
  (cd "$API_PY" && G1A_NET_LOG="$S4/netlog.txt" uv run --frozen pytest -q -rfE -p no:cacheprovider \
    -p esgapi.greenwash.tests.netcount esgapi/greenwash esgapi/config/tests/test_api_contract.py) > "$S4/pytest.log" 2>&1
  e=$?
  gw=$(api pytest -q --collect-only -p no:cacheprovider esgapi/greenwash 2>&1 | grep -c '::')
  ct=$(api pytest -q --collect-only -p no:cacheprovider esgapi/config/tests/test_api_contract.py 2>&1 | grep -c '::')
  grep -E '^FAILED|^ERROR|passed|failed|error' "$S4/pytest.log" | tail -5 | sed 's/^/    /'
  echo "    모은 노드: greenwash $gw · test_api_contract $ct"
  report 8 "pytest greenwash·test_api_contract" "$e"
fi

if want 9; then
  (cd "$API_PY" && GT1_OUT="$OUT" GT1_BASE="$BASE" GT1_NODEIDS_BEFORE="$BEFORE" scripts/planted-breaks-GT1.sh) \
    > "$S4/planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/planted.log" | sed 's/^/    /'
  report 9 "GT1 심은 파손" "$([ "$e" = 0 ] && grep -q '^PLANTED=3/3$' "$S4/planted.log" && grep -q '^FINGERPRINT=same' "$S4/planted.log" && echo 0 || echo 1)"
fi

# 이 밴드가 들인 글: 추적 파일은 기준 대비 더한 줄(옮김은 -M 으로 잡아 옮긴 몸을 빼고), 새 파일은 전부.
# 줄마다 「경로<TAB>글」.
added_lines() {
  git -C "$ROOT" diff -M -U0 "$BASE" | awk '
    /^\+\+\+ / { f = substr($0, 7); next }
    /^\+/ { print f "\t" substr($0, 2) }'
  git -C "$ROOT" ls-files -o --exclude-standard --full-name | while IFS= read -r f; do
    [ -f "$ROOT/$f" ] && awk -v f="$f" '{ print f "\t" $0 }' "$ROOT/$f"
  done
}

if want 10; then
  added_lines > "$S4/added-lines.txt"
  nl=$(grep -c . "$S4/added-lines.txt")
  hits=0
  : > "$S4/forbidden-hits.txt"
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록이 없다: $WORDS"; hits=1
  else
    cut -f2- "$S4/added-lines.txt" | grep -F -i -c -f "$WORDS" > "$S4/forbidden-count.txt"
    hits=$(cat "$S4/forbidden-count.txt")
    [ "$hits" = 0 ] || awk -F'\t' '{print $1}' "$S4/added-lines.txt" | sort -u | while IFS= read -r f; do
      grep -F "$f	" "$S4/added-lines.txt" | cut -f2- | grep -F -i -q -f "$WORDS" && echo "$f" >> "$S4/forbidden-hits.txt"
    done
  fi
  mhits=0
  msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
  draft="${GT1_COMMIT_MSG_FILE:-}"
  if [ -n "$draft" ]; then
    if [ -f "$draft" ]; then msgs="$msgs
$(cat "$draft")"; else echo "    커밋 메시지 초안이 없다: $draft"; mhits=1; fi
  fi
  if [ -n "$msgs" ] && [ -f "$WORDS" ] && printf '%s' "$msgs" | grep -F -i -q -f "$WORDS"; then mhits=1; fi
  keys=$( { cut -f2- "$S4/added-lines.txt"; printf '%s\n' "$msgs"; } | grep -E -c 'sk-[A-Za-z0-9_-]{20,}')
  # 찾는 글 자체가 든 이 밴드의 두 스크립트는 키 파일 경로 검사에서 뺀다(GC4 꼴)
  opens=$( { grep -vE '^apps/api-py/scripts/(section4|planted-breaks)-GT1\.sh	' "$S4/added-lines.txt" | cut -f2-; printf '%s\n' "$msgs"; } \
    | grep -E -c 'manufac-erp|spike/\.env')
  if [ ! -f "$S4/netlog.txt" ]; then
    (cd "$API_PY" && G1A_NET_LOG="$S4/netlog.txt" uv run --frozen pytest -q -p no:cacheprovider \
      -p esgapi.greenwash.tests.netcount esgapi/greenwash esgapi/config/tests/test_api_contract.py) > "$S4/pytest-net.log" 2>&1
  fi
  tests=$(wc -l < "$S4/netlog.txt" | tr -d ' ')
  blocked=$(awk '{s += $1} END {print s + 0}' "$S4/netlog.txt")
  nmsg=$(git -C "$ROOT" rev-list --count "$BASE..HEAD")
  echo "    낱말 $( [ -f "$WORDS" ] && grep -c . "$WORDS" || echo 0)개로 본 더한 줄 $nl: 걸린 줄 $hits, 커밋 메시지($nmsg 개, $BASE..HEAD${draft:+ + 초안 ${draft##*/}}) $mhits"
  echo "    키 꼴 $keys, 키 파일 경로 $opens, 소켓 문지기가 막은 시도 $blocked (테스트 $tests 개에서)"
  sed 's/^/    걸린 파일: /' "$S4/forbidden-hits.txt"
  report 10 "기업명·키·소켓" "$([ "$hits$mhits$keys$opens$blocked" = 00000 ] && [ "$tests" -gt 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
