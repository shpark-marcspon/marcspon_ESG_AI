#!/usr/bin/env bash
# 밴드 CU1 의 §4 자기검증(발주서 band-handoffs/CU1-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-CU1.sh                 전부
#   apps/api-py/scripts/section4-CU1.sh --step 1,3      일부(번호는 발주서 §4 의 번호)
#   apps/api-py/scripts/section4-CU1.sh --after-commit  전부 + 8. git status --porcelain 0줄
#
# 환경 변수:
#   CU1_BASE  기준 커밋(기본: 착수 때의 e646b27)
#   CU1_OUT   산출물 자리(기본: 워크트리 곁의 CU1.out). 산출물은 $CU1_OUT/section4/ 아래
# 4 의 업무·보안 층은 이 워크트리의 compose Postgres 가 떠 있어야 한다(test-business.sh·test-security.sh). 띄우지 않는다.
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
BASE="${CU1_BASE:-e646b27}"
OUT="${CU1_OUT:-$(cd "$ROOT/.." && pwd)/CU1.out}"
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

changed_files() {
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u
}

P='apps/api-py'
E="$P/esgapi"  # 저장소 뿌리 기준(git 경로)

# ── 1. 빠른 게이트 ──
if want 1; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  e=$?
  tail -1 "$S4/verify-fast.log" | sed 's/^/    /'
  report 1 "verify.sh --fast 끝 줄 VERIFY_FAST=PASS" \
    "$([ "$e" = 0 ] && tail -1 "$S4/verify-fast.log" | grep -q '^VERIFY_FAST=PASS$' && echo 0 || echo 1)"
fi

# ── 2. 심은 파손 다섯(발주서 넷 + 검증 F1 하나) 빨강·되돌린 뒤 지문 같음 ──
if want 2; then
  CU1_OUT="$OUT" "$API_PY/scripts/planted-breaks-CU1.sh" > "$S4/planted.log" 2>&1
  e=$?
  sed 's/^/    /' "$S4/planted.log"
  report 2 "심은 파손 PLANTED=5/5·FINGERPRINT=same" \
    "$([ "$e" = 0 ] && grep -q '^PLANTED=5/5$' "$S4/planted.log" && grep -q '^FINGERPRINT=same' "$S4/planted.log" && echo 0 || echo 1)"
fi

# ── 3. generated/ 다시 뽑아 같음, flow-shapes 고정 스키마·골든 diff 0 ──
if want 3; then
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do git -C "$ROOT" show "$BASE:$P/generated/$f" > "$S4/base-$f"; done
  (cd "$API_PY" && PATH="$NODE_PATH_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen-ts-types.log" 2>&1
  e=$?
  same=0
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$S4/base-$f" "$API_PY/generated/$f"; then echo "    $f: 기준과 같음"; else echo "    $f: 다르다"; same=1; fi
  done
  [ "$e" = 0 ] || echo "    gen-ts-types.sh 실패 — $S4/gen-ts-types.log"
  # 고정 파일: 결과 꼴의 스키마와 시험 자료(골든) 전부 — inventory·reconcile·reference·core 의 tests/data
  n=$(git -C "$ROOT" diff --name-only "$BASE" -- "$P/generated" "$E/inventory/tests/data" "$E/reconcile/tests/data" \
    "$E/reference/tests/data" "$E/core/tests/data" | wc -l | tr -d ' ')
  echo "    고정 스키마·골든(tests/data)·generated 의 커밋 diff: ${n}파일"
  report 3 "generated/ 셋 cmp 같음·flow-shapes·골든 diff 0" "$([ "$e$same$n" = 000 ] && echo 0 || echo 1)"
fi

# ── 4. 업무 층·보안 층 한 번씩(컨테이너) ──
if want 4; then
  "$API_PY/scripts/test-business.sh" -p no:cacheprovider -p no:randomly -n 2 > "$S4/business.log" 2>&1
  b=$?
  echo "    업무 층: $(tail -1 "$S4/business.log")"
  "$API_PY/scripts/test-security.sh" -p no:cacheprovider -p no:randomly > "$S4/security.log" 2>&1
  s=$?
  echo "    보안 층: $(tail -1 "$S4/security.log")"
  report 4 "업무 층·보안 층" "$([ "$b$s" = 00 ] && echo 0 || echo 1)"
fi

# ── 5. 게이트 자기 검사 ──
if want 5; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  tail -1 "$S4/check-gates.log" | sed 's/^/    /'
  report 5 "check-gates.sh" "$e"
fi

# ── 6. 허용 경로 밖 diff 0(§1), 0줄 몫 diff 0 ──
if want 6; then
  ALLOWED="^($E/core/auth/(bearer|tokens)\.py|$E/core/tenancy/session\.py|$E/core/isolation/managers\.py|$E/core/calc/.*"
  ALLOWED="$ALLOWED|$E/core/service/apis/(documents|runs)\.py|$E/user/service/apis/(auth|user)\.py|$E/organization/service/.*"
  ALLOWED="$ALLOWED|$E/inventory/service/.*|$E/inventory/calc/scope3/.*|$E/inventory/calc/(types|serialize)\.py|$E/inventory/flows/.*"
  ALLOWED="$ALLOWED|$E/(core|user|organization|inventory)/tests/.*|$P/scripts/(section4|planted-breaks)-CU1\.sh)$"
  changed_files > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(wc -l < "$S4/outside.txt" | tr -d ' ')
  # 0줄 몫: 그린워싱·xlsx_reader·scope3_sheets·CU2 몫(registry·resources·jsrepr·env.py)·게이트 파일·고정 자료·마이그레이션
  ZERO="^($E/greenwash/|$E/inventory/xlsx_reader\.py|$E/inventory/calc/scope3_sheets/|$E/core/registry\.py|$E/core/resources/"
  ZERO="$ZERO|$E/inventory/calc/jsrepr\.py|$E/config/env\.py|compose\.yaml|docker/|scripts/verify\.sh|scripts/check-gates\.sh"
  ZERO="$ZERO|\.pre-commit|$P/\.importlinter|\.env\.example|$P/generated/|$E/[a-z]+/tests/data/|.*/migrations/|apps/web/|services/)"
  z=$(grep -Ec "$ZERO" "$S4/changed.txt")
  echo "    바뀐 파일 $(wc -l < "$S4/changed.txt" | tr -d ' '), 허용 밖 $n, 0줄 몫 $z"
  sed 's/^/      /' "$S4/outside.txt"
  grep -E "$ZERO" "$S4/changed.txt" | sed 's/^/      0줄 몫: /'
  # 회사 이름 줄: 바뀐 줄(+/-)에 공개 보고서 회사 자료의 자리(prework·received)나 README 가 없다 — 위 허용 경로가 이미 막는다
  report 6 "허용 경로 밖 0·0줄 몫 0" "$([ "$n$z" = 00 ] && echo 0 || echo 1)"
fi

# ── 7. lint-imports 계약 전부 초록, .importlinter diff 0 ──
if want 7; then
  (cd "$API_PY" && uv run --frozen lint-imports) > "$S4/lint-imports.log" 2>&1
  e=$?
  grep -E "Contracts: |kept|broken" "$S4/lint-imports.log" | tail -2 | sed 's/^/    /'
  d=$(git -C "$ROOT" diff --name-only "$BASE" -- "$P/.importlinter" | wc -l | tr -d ' ')
  echo "    .importlinter diff: ${d}파일"
  report 7 "lint-imports 계약 전부 초록·.importlinter diff 0" "$([ "$e$d" = 00 ] && echo 0 || echo 1)"
fi

# ── 8. (커밋 뒤) 작업 트리 깨끗 ──
if [ "$AFTER" = 1 ]; then
  n=$(git -C "$ROOT" status --porcelain | wc -l | tr -d ' ')
  git -C "$ROOT" status --porcelain | sed 's/^/    /'
  report 8 "git status --porcelain 0줄" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
