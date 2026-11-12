#!/usr/bin/env bash
# 밴드 CD 의 §4 자기검증(발주서 band-handoffs/CD-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-CD.sh                 전부
#   apps/api-py/scripts/section4-CD.sh --step 1,3      일부(번호는 발주서 §4 의 번호)
#   apps/api-py/scripts/section4-CD.sh --after-commit  전부 + 10. git status --porcelain 0줄
#
# 환경 변수:
#   CD_BASE   기준 커밋(기본: 착수 때의 97cda96…)
#   CD_OUT    산출물 자리(기본: 워크트리 곁의 CD.out). 산출물은 $CD_OUT/section4/ 아래
# 2·3 의 업무 층(DB) 테스트는 이 워크트리의 compose Postgres 가 떠 있어야 한다(test-business.sh). 띄우지 않는다.
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
BASE="${CD_BASE:-97cda96}"
OUT="${CD_OUT:-$(cd "$ROOT/.." && pwd)/CD.out}"
S4="$OUT/section4"
mkdir -p "$S4"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"

STEPS="all"
AFTER=0
case "${1:-}" in
  --step) STEPS=",${2:?--step 뒤에 번호}," ;;
  --after-commit) AFTER=1 ;;
esac
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

pure() { # pure <로그 이름> <pytest 인자…>   DB 없는 층
  local log="$S4/$1.log"; shift
  (cd "$API_PY" && uv run --frozen pytest -q -p no:cacheprovider -p no:randomly "$@") > "$log" 2>&1
  local e=$?
  echo "    $(tail -1 "$log")"
  return $e
}

business() { # business <로그 이름> <pytest 인자…>   업무 층(compose Postgres)
  local log="$S4/$1.log"; shift
  "$API_PY/scripts/test-business.sh" -p no:cacheprovider -p no:randomly "$@" > "$log" 2>&1
  local e=$?
  echo "    $(tail -1 "$log")"
  return $e
}

changed_files() {
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u
}

P='apps/api-py'
E="$P/esgapi"  # 저장소 뿌리 기준(git 경로)
T='esgapi'     # apps/api-py 기준(pytest 경로)

# ── 1. D2: Scope 3 행 입력의 음수 각 칸 + 0 ──
if want 1; then
  pure d2 "$T/inventory/tests/test_scope3_calc.py" \
    -k "negative_row_numbers or zero_row_numbers or negative_factor_value"
  e=$?
  n=$(grep -Eo '^[0-9]+ passed' "$S4/d2.log" | grep -Eo '^[0-9]+')
  report 1 "D2 음수 거절(quantity·amount·weightKg·distanceKm)·0 계산·계수 음수 그대로 — 셋이어야(${n:-0})" \
    "$([ "$e" = 0 ] && [ "${n:-0}" = 3 ] && echo 0 || echo 1)"
fi

# ── 2. D7: ok→disputed, 빠진 행, 다른 출처 그대로 (+ 기존 import 테스트 전부) ──
if want 2; then
  business d7 "$T/reference/tests/test_import.py"
  e=$?
  n=$(grep -Ec 'test_(an_ok_row_turned_disputed|a_row_missing_from_the_next_file|sources_not_in_the_file)' "$S4/d7.log")
  report 2 "D7 import 의 바뀐·빠진 행(test_import.py 전부, 실패 목록의 D7 세 테스트 $n)" "$e"
fi

# ── 3. D8: 분해 중 예상 밖 예외 → failed·internal (+ 분해 태스크 테스트 전부) ──
if want 3; then
  business d8 "$T/reconcile/tests/test_tasks_parse.py"
  e=$?
  k=$( (cd "$API_PY" && uv run --frozen pytest -q -p no:cacheprovider --collect-only "$T/reconcile/tests/test_tasks_parse.py" 2>/dev/null) | grep -c 'unexpected_exception_fails_the_job')
  report 3 "D8 분해 태스크(test_tasks_parse.py 전부, D8 테스트 수집 $k)" "$([ "$e" = 0 ] && [ "$k" = 1 ] && echo 0 || echo 1)"
fi

# ── 4. 골든·대조 묶음 ──
if want 4; then
  pure golden \
    "$T/reconcile/tests/test_golden_synthetic.py" "$T/reconcile/tests/test_notation.py" "$T/reconcile/tests/test_places.py" \
    "$T/inventory/tests/test_scope3_golden.py" "$T/inventory/tests/test_scope3_golden_full.py" \
    "$T/inventory/tests/test_golden.py" "$T/inventory/tests/test_s3sheets_crosscheck.py" \
    -m "not django_db and not security"
  report 4 "골든·대조(reconcile golden·notation·places, scope3 골든, inventory 골든·s3sheets 대조)" "$?"
fi

# ── 5. 옛 번호 0줄 ──
if want 5; then
  n=$(git -C "$ROOT" grep -n "2073-7114" -- . ":(exclude)$P/scripts/section4-CD.sh" | wc -l | tr -d ' ')
  echo "    git grep 2073-7114: ${n}줄"
  report 5 "git grep 2073-7114 0줄" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

# ── 6. 허용 경로 밖 diff 0 (§1) + 머리말만 고친 셋은 docstring 밖 0 ──
if want 6; then
  ALLOWED="^($E/inventory/calc/scope3/.*|$E/inventory/tests/test_scope3_[a-z_]+\.py|$E/reference/admin/.*|$E/reference/tests/.*|$E/reference/management/commands/import_factors\.py|$E/reconcile/tasks\.py|$E/reconcile/tests/.*|$E/core/service/services/jobs\.py|$E/core/service/selectors/jobs\.py|$E/reconcile/calc/types\.py|$E/config/api\.py|$E/core/service/apis/documents\.py|$E/core/observability/middleware\.py|$P/scripts/section4-CD\.sh)$"
  changed_files > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(wc -l < "$S4/outside.txt" | tr -d ' ')
  mig=$(grep -c '/migrations/' "$S4/changed.txt")
  echo "    바뀐 파일 $(wc -l < "$S4/changed.txt" | tr -d ' '), 허용 밖 $n, 마이그레이션 $mig"
  sed 's/^/      /' "$S4/outside.txt"
  # 머리말(모듈 docstring)만 고쳐도 되는 셋: docstring 을 뺀 AST 가 기준과 같다.
  doc_only=0
  for f in "$E/config/api.py" "$E/core/service/apis/documents.py" "$E/core/observability/middleware.py"; do
    git -C "$ROOT" show "$BASE:$f" > "$S4/base.py"
    (cd "$API_PY" && uv run --frozen python - "$S4/base.py" "$ROOT/$f") <<'PY' > "$S4/doc-only.txt" 2>&1
import ast, sys
def body(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        tree.body = tree.body[1:]
    return ast.dump(tree)
sys.exit(0 if body(sys.argv[1]) == body(sys.argv[2]) else 1)
PY
    if [ $? = 0 ]; then echo "    $f: docstring 밖 0"; else echo "    $f: docstring 밖이 바뀌었다"; doc_only=1; fi
  done
  rm -f "$S4/base.py"
  report 6 "허용 경로 밖 0·마이그레이션 0·머리말 셋은 docstring 만" "$([ "$n$mig$doc_only" = 000 ] && echo 0 || echo 1)"
fi

# ── 7. generated/ 다시 뽑아 같음 ──
if want 7; then
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do git -C "$ROOT" show "$BASE:$P/generated/$f" > "$S4/base-$f"; done
  (cd "$API_PY" && PATH="$NODE_PATH_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen-ts-types.log" 2>&1
  e=$?
  same=0
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$S4/base-$f" "$API_PY/generated/$f"; then echo "    $f: 기준과 같음"; else echo "    $f: 다르다"; same=1; fi
  done
  [ "$e" = 0 ] || echo "    gen-ts-types.sh 실패 — $S4/gen-ts-types.log"
  report 7 "generated/ 셋을 다시 뽑아 기준과 cmp 같음" "$([ "$e$same" = 00 ] && echo 0 || echo 1)"
fi

# ── 8. 빠른 게이트 ──
if want 8; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  e=$?
  tail -1 "$S4/verify-fast.log" | sed 's/^/    /'
  report 8 "verify.sh --fast" "$([ "$e" = 0 ] && tail -1 "$S4/verify-fast.log" | grep -q '^VERIFY_FAST=PASS$' && echo 0 || echo 1)"
fi

# ── 9. 게이트 자기 검사 ──
if want 9; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  tail -1 "$S4/check-gates.log" | sed 's/^/    /'
  report 9 "check-gates.sh" "$e"
fi

# ── 10. (커밋 뒤) 작업 트리 깨끗 ──
if [ "$AFTER" = 1 ]; then
  n=$(git -C "$ROOT" status --porcelain | wc -l | tr -d ' ')
  git -C "$ROOT" status --porcelain | sed 's/^/    /'
  report 10 "git status --porcelain 0줄" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
