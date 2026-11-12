#!/usr/bin/env bash
# 밴드 PX 의 §4 자기검증(발주서 band-handoffs/PX-order.md §4 — 파서 정본 이전·옛 JSON 갈래·D4). 줄마다 EXIT= 를 찍고 끝에
# SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-PX.sh                  전부
#   apps/api-py/scripts/section4-PX.sh --step 1,3       일부(번호는 발주서 §4 의 번호, 11 은 덧붙인 api-py 시험)
#   apps/api-py/scripts/section4-PX.sh --after-commit   전부 + git status --porcelain 0
#
# 환경 변수:
#   PX_BASE   기준 커밋(기본: 워크트리를 만들 때의 main 9d9c110)
#   PX_OUT    산출물 자리(기본: 워크트리 곁의 PX.out). 산출물은 $PX_OUT/section4/ 아래
# 컨테이너를 띄우지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다). grep -E 에 \s 를 쓰지 않는다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
BASE="${PX_BASE:-9d9c110}"
OUT="${PX_OUT:-$(cd "$ROOT/.." && pwd)/PX.out}"
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

# ── 2. 파서 린트·포맷·타입(뿌리 verify.sh 의 넷과 같은 꼴) ──
if want 2; then
  parser_run ruff-check ruff check "$PARSER"
  a=$?
  parser_run ruff-format ruff format --check "$PARSER"
  b=$?
  parser_run pyright pyright -p "$PARSER"
  c=$?
  report 2 "parser ruff check·format --check·pyright" "$(all0 $a $b $c)"
fi

# ── 3. lock: uv 0.7.13 으로 --check, 그리고 기준과의 diff 에서 지운 줄이 pypdf 블록뿐·더한 줄 0 ──
if want 3; then
  (cd "$ROOT/$PARSER" && uvx --from 'uv==0.7.13' uv lock --check) > "$S4/lock-check.log" 2>&1
  a=$?
  echo "    lock --check: $(tail -1 "$S4/lock-check.log")"
  git -C "$ROOT" diff "$BASE" -- "$PARSER/uv.lock" > "$S4/lock.diff"
  added=$(grep -c '^+[^+]' "$S4/lock.diff")
  grep '^-[^-]' "$S4/lock.diff" | sed 's/^-//' > "$S4/lock-removed.txt"
  # 지운 줄(빈 줄 밖)은 이 열이어야 한다(의존성 목록의 두 줄과 [[package]] pypdf 블록 여덟 줄).
  git -C "$ROOT" show "$BASE:$PARSER/uv.lock" | awk '
    /^\[\[package\]\]$/ { block = $0; inblock = 1; next }
    inblock && /^name = "pypdf"$/ { print block; print; keep = 1; inblock = 0; next }
    inblock { inblock = 0 }
    keep && /^$/ { keep = 0; next }
    keep { print; next }
    /\{ name = "pypdf"/ { print }
  ' | sort > "$S4/lock-expected.txt"
  sort "$S4/lock-removed.txt" > "$S4/lock-removed.sorted"
  cmp -s "$S4/lock-expected.txt" "$S4/lock-removed.sorted"
  b=$?
  echo "    지운 줄 $(wc -l < "$S4/lock-removed.txt" | tr -d ' ') (기대 $(wc -l < "$S4/lock-expected.txt" | tr -d ' '), pypdf 블록과 같음=$([ $b = 0 ] && echo 예 || echo 아니오)), 더한 줄 $added"
  report 3 "uv lock --check(0.7.13)·지운 줄은 pypdf 블록뿐·더한 줄 0" "$(all0 $a $b "$added")"
fi

# ── 4. sourceUrl 0줄(시험 글·문서 밖) ──
if want 4; then
  git -C "$ROOT" grep -n "sourceUrl" -- services apps packages \
    ':!*.md' ':!services/parser/test_app.py' ':!services/parser/tests/*' ':!services/parser/scripts/planted.py' \
    ':!apps/api-py/scripts/section4-PX.sh' \
    ':!**/tests/**' ':!**/*.test.ts' \
    > "$S4/sourceurl.txt"
  n=$(wc -l < "$S4/sourceurl.txt" | tr -d ' ')
  echo "    sourceUrl 이 남은 줄 $n"
  cat "$S4/sourceurl.txt"
  report 4 "grep sourceUrl 0줄(services·apps·packages, 시험·문서 밖)" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

# ── 5. 심은 파손: app.py 의 것 전부(PX 가 더한 16~21 포함) 빨강·되돌린 뒤 작업 트리 지문 같음 ──
if want 5; then
  (cd "$ROOT" && uv run --project "$PARSER" --frozen python "$PARSER/scripts/planted.py" 7 8 9 10 11 14 15 16 17 18 19 20 21 22) \
    > "$S4/planted.log" 2>&1
  e=$?
  grep -E "^── |EXIT=|^══" "$S4/planted.log" | sed 's/^/    /'
  report 5 "심은 파손(쪽 상한·줄 상한·parse_failed 500·옛 갈래·시간 상한·검사기 한 번·끊긴 요청의 자리(B8) 등 14) 빨강·지문 같음" "$e"
fi

# ── 6. PB1 대조 (a) ──
if want 6; then
  if git -C "$ROOT" cat-file -e "HEAD:$PARSER/tests/test_baseline.py" 2>/dev/null; then
    parser_run baseline pytest -q -p no:cacheprovider "$PARSER/tests/test_baseline.py"
    report 6 "PB1 대조 (a) 같음" "$?"
  else
    echo "    PB1 없음: $PARSER/tests/test_baseline.py 가 HEAD 에 없다(PB1 이 main 에 들지 않았다)"
    report 6 "PB1 대조 (a) — PB1 없음" 1
  fi
fi

# ── 7. 닫힌 목록 밖 diff 0·값 한 줄 파일의 줄 수·회사 이름 줄 diff 0 ──
P="$PARSER"
A='apps/api-py'
E="$A/esgapi"
# 발주서 §1 ⓐ + 감독 처분(2026-10-16: 시간 차례 — env.py·test_env.py·compose.yaml:55·docker/elasticmq.conf·.env.example:62,
# 기대값 test_celery_conf.py·reconcile/tests/test_parser_setting.py, parser.py 머리말, tests_integration/test_worker_flow.py 주석,
# fix: elasticmq.conf 의 주석 한 줄·services/parser/tests/test_packaging.py 의 「사본」 주석)
# + ⓑ(PB1 뒤) 의 docparse 세 파일.
ALLOWED="^($P/(app\.py|test_app\.py|pyproject\.toml|uv\.lock|README\.md|schemas/README\.md|scripts/planted\.py)|$P/tests/(test_http|conftest|pdfbuild|test_packaging)\.py|$P/docparse/(document|tables_lines|reading_order)\.py|$E/core/resources/parser\.py|$E/core/tests/test_(parser_port|celery_conf)\.py|$E/reconcile/tests/test_parser_setting\.py|$E/config/env\.py|$E/config/tests/test_env\.py|$A/tests_integration/test_worker_flow\.py|$A/scripts/section4-PX\.sh|compose\.yaml|docker/elasticmq\.conf|\.env\.example)$"
NAMES='코스맥스|cosmax|삼성|samsung'
if want 7; then
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(wc -l < "$S4/outside.txt" | tr -d ' ')
  # 게이트 파일과 곁 파일은 값 한 줄씩만, 통합 시험은 주석·설명 글의 120 → 360 만(지운 줄의 120 을 360 으로 바꾸면 더한 줄).
  one=0
  # elasticmq.conf 는 값 줄과 그 위 주석 한 줄(감독 처분 fix), .env.example 은 값 줄과 :95 의 낡은 글(fix2)이라 넷.
  for pair in compose.yaml:2 docker/elasticmq.conf:4 .env.example:4; do
    f="${pair%:*}"
    want_n="${pair##*:}"
    c=$(git -C "$ROOT" diff "$BASE" -- "$f" | grep -c '^[-+][^-+]')
    [ "$c" = "$want_n" ] || { echo "    $f: 바뀐 줄 $c (기대 $want_n)"; one=1; }
  done
  git -C "$ROOT" diff "$BASE" -- "$A/tests_integration/test_worker_flow.py" > "$S4/worker-flow.diff"
  grep '^-[^-]' "$S4/worker-flow.diff" | sed -e 's/^-//' -e 's/120/360/g' > "$S4/worker-flow.expected"
  grep '^+[^+]' "$S4/worker-flow.diff" | sed -e 's/^+//' > "$S4/worker-flow.added"
  cmp -s "$S4/worker-flow.expected" "$S4/worker-flow.added" || { echo "    test_worker_flow.py: 120 → 360 밖의 고침이 있다"; one=1; }
  # 회사 이름 줄: 바뀐 파일 전부의 diff 에서 그 이름이 든 -/+ 줄 0
  # 이 스크립트 자신은 뺀다(이름 정규식을 글로 싣는다).
  names=$(git -C "$ROOT" diff "$BASE" -- . ':!apps/api-py/scripts/section4-PX.sh' | grep '^[-+][^-+]' | grep -ciE "$NAMES")
  gates=$(grep -cE '^(scripts/(verify|check-gates|section4-PD2)\.sh|\.pre-commit.*|docker/parser\.Dockerfile)$' "$S4/changed.txt")
  echo "    바뀐 파일 $(wc -l < "$S4/changed.txt" | tr -d ' '), 밖 $n, 회사 이름 줄 $names, 게이트 파일 $gates, 값 한 줄 어긋남 $one"
  cat "$S4/outside.txt"
  report 7 "닫힌 목록 밖 diff 0·회사 이름 줄 0·게이트 파일 0·compose/conf/.env.example 한 줄" \
    "$([ "$n$names$gates$one" = 0000 ] && echo 0 || echo 1)"
fi

# ── 8. generated 다시 뽑아 cmp 같음 ──
if want 8; then
  G="$API_PY/generated"
  mkdir -p "$S4/generated-before"
  cp "$G/openapi.json" "$G/api.d.ts" "$G/api.d.ts.source-sha256" "$S4/generated-before/"
  (cd "$API_PY" && PATH="$NODE_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen.log" 2>&1
  e=$?
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    cmp -s "$S4/generated-before/$f" "$G/$f" || { echo "    $f 다름"; e=1; }
  done
  report 8 "generated 재생성 cmp 같음" "$e"
fi

# ── 9. 빠른 게이트 ──
if want 9; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  echo "    $(tail -1 "$S4/verify-fast.log")"
  report 9 "verify.sh --fast" "$(tail -1 "$S4/verify-fast.log" | grep -q '^VERIFY_FAST=PASS$' && echo 0 || echo 1)"
fi

# ── 10. 게이트 자기 검사 ──
if want 10; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  echo "    $(tail -1 "$S4/check-gates.log")"
  report 10 "check-gates.sh" "$e"
fi

# ── 11. (덧붙임) api-py 의 바뀐 시험: 시간 차례·파서 클라이언트 갈래·Celery 설정 ──
if want 11; then
  (cd "$API_PY" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" \
    esgapi/config/tests/test_env.py esgapi/core/tests/test_parser_port.py esgapi/core/tests/test_celery_conf.py \
    esgapi/reconcile/tests/test_parser_setting.py) > "$S4/api-py.log" 2>&1
  e=$?
  echo "    api-py: $(tail -1 "$S4/api-py.log")"
  report 11 "api-py 시간 차례(파서 180<210<240<300<330<360)·새 code 갈래" "$e"
fi

if [ "$AFTER" = 1 ]; then
  git -C "$ROOT" status --porcelain > "$S4/status.txt"
  n=$(wc -l < "$S4/status.txt" | tr -d ' ')
  cat "$S4/status.txt"
  report 12 "커밋 뒤 git status --porcelain 0" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
