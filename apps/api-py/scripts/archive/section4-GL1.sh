#!/usr/bin/env bash
# 밴드 GL1 의 §4 자기검증(발주서 band-handoffs/GL1-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-GL1.sh                 전부
#   apps/api-py/scripts/section4-GL1.sh --step 1,2,3    일부(번호는 발주서 §4 의 번호)
#
# 환경 변수:
#   GL1_BASE   기준 커밋(기본: 착수 때 적은 4fa89fd…)
#   GL1_OUT    산출물 자리(기본: 워크트리 곁의 GL1.out). 산출물은 $GL1_OUT/section4/ 아래
#   GL1_FORBIDDEN_WORDS_FILE  기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt — 이 파일만 연다)
# 컨테이너를 띄우지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${GL1_BASE:-4fa89fdbcf1d133ae08260c5f570a9a21e4ce526}"
OUT="${GL1_OUT:-$SIDE/GL1.out}"
WORDS="${GL1_FORBIDDEN_WORDS_FILE:-$SIDE/G1a.out/forbidden-words.txt}"
S4="$OUT/section4"
E="apps/api-py/esgapi/greenwash"
mkdir -p "$S4"
api() { (cd "$API_PY" && uv run --frozen "$@"); }
pyt() { # pyt <로그 이름> <pytest 인자…>
  local log="$S4/$1.log"; shift
  api pytest -q -rfE -p no:cacheprovider "$@" > "$log" 2>&1
  local e=$?
  grep -E '^FAILED|^ERROR|passed|failed|error' "$log" | tail -5 | sed 's/^/    /'
  return $e
}

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

# 바뀐 파일(커밋된 것 + 작업 트리 + 새 파일), 저장소 뿌리 기준 경로. 지워진 파일도 든다.
changed_files() {
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u
}

ALLOWED='^(apps/api-py/esgapi/greenwash/calc/checker\.py|apps/api-py/esgapi/greenwash/flows/colab\.py|apps/api-py/esgapi/greenwash/__init__\.py|apps/api-py/esgapi/greenwash/tests/test_copy_ast\.py|apps/api-py/esgapi/greenwash/tests/data/gw1-ast-sha256\.txt|apps/api-py/esgapi/greenwash/tests/calc/test_checker_resume\.py|apps/api-py/scripts/g1a_compare\.py|apps/api-py/scripts/planted-breaks-G1a\.sh|apps/api-py/scripts/(section4|planted-breaks)-GL1\.sh|README\.md)$'

# §1-2 의 0줄 목록(git pathspec). checker.py·colab.py·gw1-ast-sha256.txt 는 뺀다.
ZERO=(
  "$E/calc" ":(exclude)$E/calc/checker.py"
  "$E/flows" ":(exclude)$E/flows/colab.py"
  "$E/tests/flows" "$E/tests/calc/test_checker.py"
  "$E/tests/data" ":(exclude)$E/tests/data/gw1-ast-sha256.txt"
  "$E/service" "$E/api.py" "$E/apps.py"
  apps/api-py/generated
  apps/api-py/esgapi/core apps/api-py/esgapi/config apps/api-py/esgapi/user apps/api-py/esgapi/organization
  apps/api-py/esgapi/inventory apps/api-py/esgapi/reference apps/api-py/esgapi/reconcile
  apps/api-py/tests apps/api-py/pyproject.toml apps/api-py/uv.lock apps/api-py/.importlinter
  services/parser apps/web
  apps/api-py/scripts/planted-breaks-G1c.sh apps/api-py/scripts/planted-breaks-G1d.sh
  ":(glob)apps/api-py/scripts/section4-G1*.sh"
)

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse HEAD), 산출물 $S4"

if want 1; then
  changed_files > "$S4/changed-files.txt"
  outside=$(grep -Ev "$ALLOWED" "$S4/changed-files.txt")
  n=$(grep -c . "$S4/changed-files.txt")
  echo "    바뀐 파일 $n, 허용 밖 $( [ -n "$outside" ] && echo "$outside" | grep -c . || echo 0)"
  [ -n "$outside" ] && echo "$outside" | sed 's/^/    밖: /'
  report 1 "허용 경로" "$([ -z "$outside" ] && echo 0 || echo 1)"
fi

if want 2; then
  zero=$(git -C "$ROOT" diff "$BASE" --stat -- "${ZERO[@]}" | tail -1)
  untracked=$(git -C "$ROOT" ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)
  echo "    diff: ${zero:-(없음)} / 새 파일 $untracked"
  report 2 "0줄 목록(§1-2)" "$([ -z "$zero" ] && [ "$untracked" = 0 ] && echo 0 || echo 1)"
fi

if want 3; then
  loops=$(cd "$ROOT" && grep -rn "for idx, page_no in enumerate(pages_norm" "$E" --include='*.py' | grep -v "^$E/tests/")
  n=$(printf '%s' "$loops" | grep -c .)
  analyze=$(grep -c "analyze_page" "$ROOT/$E/flows/colab.py")
  printf '%s\n' "$loops" | sed 's/^/    /'
  echo "    루프 $n 곳(테스트 밖), colab.py 의 analyze_page $analyze"
  ok=1
  [ "$n" = 1 ] && case "$loops" in "$E/calc/checker.py:"*) ok=0 ;; esac
  [ "$analyze" = 0 ] || ok=1
  report 3 "스캔 루프 하나" "$ok"
fi

if want 4; then
  (cd "$ROOT" && PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  (cd "$ROOT" && PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  gates=$(grep '^GATES=' "$S4/check-gates.log" | tail -1)
  echo "    $last / $gates (종료 $e)"
  report 4 "verify.sh --fast · check-gates" "$([ "$last" = "VERIFY_FAST=PASS" ] && [ "$e" = 0 ] && echo 0 || echo 1)"
fi

if want 5; then
  rm -f "$S4/netlog.txt"
  G1A_NET_LOG="$S4/netlog.txt" pyt pytest-greenwash -p esgapi.greenwash.tests.netcount esgapi/greenwash
  report 5 "pytest esgapi/greenwash" "$?"
fi

if want 6; then
  api python scripts/check_test_layout.py > "$S4/test-layout.log" 2>&1
  e=$?
  sed 's/^/    /' "$S4/test-layout.log" | head -5
  report 6 "check_test_layout" "$e"
fi

if want 7; then
  (cd "$API_PY" && G1A_OUT="$OUT/g1a" G1A_BASE="$BASE" scripts/section4-G1a.sh --step 9,11,12,13,14,15,16,17,18) > "$S4/g1a-section4.log" 2>&1
  e=$?
  grep -E '^\[|SECTION4_FAIL|SAME=|PLANTED=' "$S4/g1a-section4.log" | sed 's/^/    /'
  report 7 "G1a 자기검증(9,11~18) GL1 바닥에서" "$e"
fi

if want 8; then
  before=$(git -C "$ROOT" show "$BASE:apps/api-py/scripts/planted-breaks-G1c.sh" | grep -cE '^    \([0-9]+,')
  (cd "$API_PY" && G1C_OUT="$OUT/g1c" scripts/planted-breaks-G1c.sh) > "$S4/planted-g1c.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/planted-g1c.log" | sed 's/^/    /'
  got=$(grep '^PLANTED=' "$S4/planted-g1c.log" | tail -1)
  echo "    기준 커밋의 심은 수 $before"
  report 8 "G1c 심은 파손(전과 같은 수)" "$([ "$e" = 0 ] && [ "$got" = "PLANTED=$before/$before" ] && grep -q '^FINGERPRINT=same' "$S4/planted-g1c.log" && echo 0 || echo 1)"
fi

if want 9; then
  (cd "$API_PY" && GL1_OUT="$OUT" scripts/planted-breaks-GL1.sh) > "$S4/planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/planted.log" | sed 's/^/    /'
  report 9 "GL1 심은 파손" "$([ "$e" = 0 ] && grep -q '^PLANTED=4/4$' "$S4/planted.log" && grep -q '^FINGERPRINT=same' "$S4/planted.log" && echo 0 || echo 1)"
fi

# 이 밴드가 들인 글: 기준 커밋에 있던 파일은 더한 줄만(뿌리 README 에는 앞 밴드의 글이 있다), 새 파일은 전부.
added_text() { # added_text <뿌리 기준 경로>
  if git -C "$ROOT" cat-file -e "$BASE:$1" 2>/dev/null; then
    git -C "$ROOT" diff -U0 "$BASE" -- "$1" | grep '^+' | grep -v '^+++'
  else
    cat "$ROOT/$1"
  fi
}

if want 10; then
  hits=0; keys=0; opens=0
  : > "$S4/forbidden-hits.txt"
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록이 없다: $WORDS"; hits=1
  else
    while IFS= read -r f; do
      [ -f "$ROOT/$f" ] || continue
      if added_text "$f" | grep -F -i -q -f "$WORDS"; then echo "$f" >> "$S4/forbidden-hits.txt"; hits=$((hits + 1)); fi
    done < <(changed_files)
  fi
  mhits=0
  msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
  if [ -n "$msgs" ] && [ -f "$WORDS" ] && printf '%s' "$msgs" | grep -F -i -q -f "$WORDS"; then mhits=1; fi
  while IFS= read -r f; do
    [ -f "$ROOT/$f" ] || continue
    if added_text "$f" | grep -E -q 'sk-[A-Za-z0-9_-]{20,}'; then echo "    키 꼴: $f"; keys=$((keys + 1)); fi
    case "$f" in apps/api-py/scripts/section4-GL1.sh) continue ;; esac  # 찾는 글 자체가 든 이 스크립트
    if added_text "$f" | grep -E -q 'manufac-erp|spike/\.env'; then echo "    키 파일 경로: $f"; opens=$((opens + 1)); fi
  done < <(changed_files)
  if [ ! -f "$S4/netlog.txt" ]; then
    G1A_NET_LOG="$S4/netlog.txt" api pytest -q -p no:cacheprovider -p esgapi.greenwash.tests.netcount esgapi/greenwash > "$S4/pytest-net.log" 2>&1
  fi
  tests=$(wc -l < "$S4/netlog.txt" | tr -d ' ')
  blocked=$(awk '{s += $1} END {print s + 0}' "$S4/netlog.txt")
  echo "    낱말 $( [ -f "$WORDS" ] && grep -c . "$WORDS" || echo 0)개로 본 파일 $(changed_files | wc -l | tr -d ' ')(더한 줄·새 파일): 걸린 파일 $hits, 커밋 메시지($BASE..HEAD) $mhits"
  echo "    키 꼴 $keys, 키 파일 경로 $opens, 소켓 문지기가 막은 시도 $blocked (테스트 $tests 개에서)"
  cat "$S4/forbidden-hits.txt"
  report 10 "기업명·키·소켓" "$([ "$hits$mhits$keys$opens$blocked" = 00000 ] && [ "$tests" -gt 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
