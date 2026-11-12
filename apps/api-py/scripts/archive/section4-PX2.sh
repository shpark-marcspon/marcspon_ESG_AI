#!/usr/bin/env bash
# 밴드 PX2 의 §4 자기검증(발주서 band-handoffs/PX2-order.md §4 — docparse 안: PDF 한 번 열기·표/읽는 차례 최악 비용·사본
# 예외 걷기). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-PX2.sh                  전부
#   apps/api-py/scripts/section4-PX2.sh --step 1,3       일부(번호는 발주서 §4 의 번호)
#   apps/api-py/scripts/section4-PX2.sh --after-commit   전부 + git status --porcelain 0
#
# 환경 변수:
#   PX2_BASE  기준 커밋(기본: 워크트리를 만들 때의 main e646b27)
#   PX2_OUT   산출물 자리(기본: 워크트리 곁의 PX2.out). 산출물은 $PX2_OUT/section4/ 아래
# 컨테이너를 띄우지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다). grep -E 에 \s 를 쓰지 않는다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
BASE="${PX2_BASE:-e646b27}"
OUT="${PX2_OUT:-$(cd "$ROOT/.." && pwd)/PX2.out}"
S4="$OUT/section4"
mkdir -p "$S4"
NODE_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
PARSER="services/parser"

STEPS="all"
AFTER=0
case "${1:-}" in
  --step) STEPS=",${2:?--step 뒤에 번호},"
    ;;
  --after-commit) AFTER=1
    ;;
esac
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

all0() { # 인자가 전부 0 이면 0
  for x in "$@"; do [ "$x" = 0 ] || { echo 1; return; }; done
  echo 0
}

# 파서 도구 한 번: <로그 이름> <명령…>. 끝 줄을 찍고 종료 코드를 돌려준다.
parser_run() {
  local name="$1"
  shift
  (cd "$ROOT" && uv run --project "$PARSER" --frozen "$@") > "$S4/$name.log" 2>&1
  local e=$?
  echo "    $name: $(tail -1 "$S4/$name.log")"
  return $e
}

# ── 1. 파서 시험 ──
if want 1; then
  parser_run pytest pytest -q -p no:cacheprovider "$PARSER"
  report 1 "uv run --project services/parser --frozen pytest -q services/parser" "$?"
fi

# ── 2. 파서 린트·포맷·타입(이제 docparse 포함 — 포맷 제외·린트 규칙 끔이 없고 pyright include 에 docparse) ──
if want 2; then
  parser_run ruff-check ruff check "$PARSER"
  a=$?
  parser_run ruff-format ruff format --check "$PARSER"
  b=$?
  parser_run pyright pyright -p "$PARSER"
  c=$?
  # 사본이던 때의 예외가 걷혔는가: 포맷 exclude 0, "docparse/**" per-file 0, pyright include 에 docparse
  toml="$ROOT/$PARSER/pyproject.toml"
  d=0
  grep -q '^\[tool\.ruff\.format\]' "$toml" && { echo "    [tool.ruff.format] 가 남았다"; d=1; }
  grep -q '^"docparse/\*\*"' "$toml" && { echo "    \"docparse/**\" per-file 예외가 남았다"; d=1; }
  grep -qE '^include = \[.*"docparse"' "$toml" || { echo "    pyright include 에 docparse 가 없다"; d=1; }
  report 2 "parser ruff check·format --check·pyright(docparse 포함)" "$(all0 $a $b $c $d)"
fi

# ── 3. PB1 대조 (a) 14 passed ──
if want 3; then
  parser_run baseline pytest -q -p no:cacheprovider "$PARSER/tests/test_baseline.py"
  e=$?
  tail -1 "$S4/baseline.log" | grep -qE '^14 passed' || e=1
  report 3 "PB1 대조 (a) test_baseline.py 14 passed" "$e"
fi

# ── 4. 심은 파손: planted.py(⑦ 23·⑧ 24~27 과 app.py 의 것) 빨강·지문 같음, PB1 의 심은 파손(포맷이 자리를 옮김) ──
if want 4; then
  (cd "$ROOT" && uv run --project "$PARSER" --frozen python "$PARSER/scripts/planted.py" \
    7 8 9 10 11 14 15 16 17 18 19 20 21 22 23 24 25 26 27) > "$S4/planted.log" 2>&1
  a=$?
  grep -E "^── |EXIT=|^══" "$S4/planted.log" | sed 's/^/    /'
  PB1_OUT="$OUT/pb1" "$ROOT/$PARSER/scripts/planted-breaks-PB1.sh" > "$S4/planted-pb1.log" 2>&1
  b=$?
  grep -E "^(PLANTED|FINGERPRINT)=" "$S4/planted-pb1.log" | sed 's/^/    PB1 /'
  report 4 "심은 파손(두 번 열기·표 칸/괘선 상한 끔·읽는 차례 재귀·위첨자 전부 훑기 + app.py 의 것) 빨강·지문 같음·PB1 심은 파손" \
    "$(all0 $a $b)"
fi

# ── 5. 허용 경로 밖 diff 0·verify.sh 는 :342 주석 줄뿐·회사 이름 줄 같음·uv.lock diff 0 ──
P="$PARSER"
ALLOWED="^($P/docparse/.*|$P/(app\.py|test_app\.py|pyproject\.toml|README\.md|scripts/planted\.py)|$P/tests/.*|apps/api-py/scripts/section4-PX2\.sh|scripts/verify\.sh)$"
NAMES='코스맥스|cosmax|삼성|samsung'
if want 5; then
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(wc -l < "$S4/outside.txt" | tr -d ' ')
  # tests/baseline/ 는 산출을 일부러 바꿀 때만 고친다(이 밴드는 0)
  fixed=$(grep -c "^$P/tests/baseline/" "$S4/changed.txt")
  # verify.sh: 지운 줄 하나·더한 줄 하나, 둘 다 342 줄의 주석
  git -C "$ROOT" diff -U0 "$BASE" -- scripts/verify.sh > "$S4/verify-sh.diff"
  minus=$(grep -c '^-[^-]' "$S4/verify-sh.diff")
  plus=$(grep -c '^+[^+]' "$S4/verify-sh.diff")
  comments=$(grep -cE '^[-+]# ' "$S4/verify-sh.diff")
  hunk=$(grep -c '^@@ -342 +342 @@' "$S4/verify-sh.diff")
  vs=$([ "$minus$plus$comments$hunk" = 1121 ] && echo 0 || echo 1)
  # 회사 이름 줄: 기준에서 그 이름이 든 파일마다, 그 줄들(글자 그대로·차례대로)이 지금과 같다
  git -C "$ROOT" grep -l -i -E "$NAMES" "$BASE" -- . | sed "s/^$BASE://" > "$S4/name-files.txt"
  nf=$(wc -l < "$S4/name-files.txt" | tr -d ' ')
  names=0
  while read -r f; do
    git -C "$ROOT" grep -h -i -E "$NAMES" "$BASE" -- "$f" > "$S4/names.before"
    (cd "$ROOT" && grep -i -E "$NAMES" "$f") > "$S4/names.after"
    cmp -s "$S4/names.before" "$S4/names.after" || { echo "    회사 이름 줄이 다르다: $f"; names=$((names + 1)); }
  done < "$S4/name-files.txt"
  lock=$(git -C "$ROOT" diff "$BASE" -- "$P/uv.lock" | wc -l | tr -d ' ')
  echo "    바뀐 파일 $(wc -l < "$S4/changed.txt" | tr -d ' '), 밖 $n, tests/baseline $fixed," \
    "verify.sh -$minus +$plus(주석 $comments, :342 $hunk), 회사 이름 파일 $nf 중 다름 $names, uv.lock diff $lock 줄"
  cat "$S4/outside.txt"
  report 5 "허용 경로 밖 diff 0·verify.sh 는 :342 주석 줄뿐·회사 이름 줄 같음·uv.lock diff 0" \
    "$([ "$n$fixed$vs$names$lock" = 00000 ] && echo 0 || echo 1)"
fi

# ── 6. generated 다시 뽑아 cmp 같음 ──
if want 6; then
  G="$API_PY/generated"
  mkdir -p "$S4/generated-before"
  cp "$G/openapi.json" "$G/api.d.ts" "$G/api.d.ts.source-sha256" "$S4/generated-before/"
  (cd "$API_PY" && PATH="$NODE_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen.log" 2>&1
  e=$?
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    cmp -s "$S4/generated-before/$f" "$G/$f" || { echo "    $f 다름"; e=1; }
  done
  report 6 "generated 재생성 cmp 같음" "$e"
fi

# ── 7. 빠른 게이트 ──
if want 7; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  echo "    $(tail -1 "$S4/verify-fast.log")"
  report 7 "verify.sh --fast" "$(tail -1 "$S4/verify-fast.log" | grep -q '^VERIFY_FAST=PASS$' && echo 0 || echo 1)"
fi

# ── 8. 게이트 자기 검사 ──
if want 8; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  echo "    $(tail -1 "$S4/check-gates.log")"
  report 8 "check-gates.sh" "$e"
fi

if [ "$AFTER" = 1 ]; then
  git -C "$ROOT" status --porcelain > "$S4/status.txt"
  n=$(wc -l < "$S4/status.txt" | tr -d ' ')
  cat "$S4/status.txt"
  report 9 "커밋 뒤 git status --porcelain 0" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
