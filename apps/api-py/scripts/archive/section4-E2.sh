#!/usr/bin/env bash
# 밴드 E2 의 §4 자기검증(발주서 band-handoffs/E2-order.md §4 — 응답 뼈대를 EDK 꼴로). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-E2.sh                  전부
#   apps/api-py/scripts/section4-E2.sh --step 1,3       일부(번호는 발주서 §4 의 번호, 16·17 은 덧붙인 층 전부)
#   apps/api-py/scripts/section4-E2.sh --after-commit   전부 + git status --porcelain 0
#
# 환경 변수:
#   E2_BASE   기준 커밋(기본: 워크트리를 만들 때의 main b10dc74)
#   E2_OUT    산출물 자리(기본: 워크트리 곁의 E2.out). 산출물은 $E2_OUT/section4/ 아래
# DB 를 쓰는 단계(1·2·4·6, 16·17)는 이 워크트리의 compose(.env 의 COMPOSE_PROJECT_NAME)의 postgres 가 떠 있어야 한다 —
# 띄우고 내리는 일은 부르는 쪽(러너의 컨테이너 규칙)이 한다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
BASE="${E2_BASE:-b10dc74}"
OUT="${E2_OUT:-$(cd "$ROOT/.." && pwd)/E2.out}"
S4="$OUT/section4"
mkdir -p "$S4"
NODE_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"

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

# pytest 한 번: <로그 이름> <층 pure|business|security> <인자…>. 끝 줄을 찍고 종료 코드를 돌려준다.
# 「골라 낸 것이 0 개」(-k 가 아무것도 못 고름)도 실패로 친다(5 = no tests collected).
run_tests() {
  local name="$1" layer="$2"
  shift 2
  case "$layer" in
    pure) (cd "$API_PY" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" "$@") ;;
    business) (cd "$API_PY" && scripts/test-business.sh -p no:cacheprovider "$@") ;;
    security) (cd "$API_PY" && scripts/test-security.sh -p no:cacheprovider "$@") ;;
  esac > "$S4/$name.log" 2>&1
  local e=$?
  echo "    $name: $(tail -1 "$S4/$name.log")"
  return $e
}

all0() { # 인자가 전부 0 이면 0
  for x in "$@"; do [ "$x" = 0 ] || { echo 1; return; }; done
  echo 0
}

C="esgapi/config/tests"
K="esgapi/core/tests"

# ── 1. 오류 꼴 전수(선언 전수 + 실제 요청 표본) ──
if want 1; then
  run_tests shape-p pure "$K/test_exceptions.py" "$C/test_api_errors.py" -k "error_body or 422_and_500 or exceptions or edk_code or four_keys or lowercase or uppercase or schema_says or 405"
  p=$?
  run_tests shape-b business "$C/test_api_errors.py"
  b=$?
  report 1 "오류 꼴 {error:{code,message,fields,legacyCode}} — 선언 전수·표본" "$(all0 $p $b)"
fi

# ── 2. 422·fields(칸 이름 camel·앞머리 뗌, 받은 값 없음) ──
if want 2; then
  run_tests v422-p pure "$C/test_api_errors.py" -k "field_name or malformed or not_json"
  p=$?
  run_tests v422-b business "$C/test_api_errors.py" esgapi/reference/tests/test_api.py -k "nested or both_record_type or bad_queries"
  b=$?
  report 2 "422 VALIDATION_ERROR·fields" "$(all0 $p $b)"
fi

# ── 3. 500 무상세(로그에는 있음)·DB 닿지 못함 503 ──
if want 3; then
  run_tests e500 pure "$C/test_api_errors.py" -k "unexpected or unreachable or outside_ninja or urls_hand"
  report 3 "500 INTERNAL_SERVER_ERROR 무상세(ninja 안·밖)" "$?"
fi

# ── 4. +09:00 전수 ──
if want 4; then
  run_tests kst-p pure "$K/test_schemas.py" "$C/test_api_times.py" -k "seoul or naive or microseconds or serialise or datetime or date_time"
  p=$?
  run_tests kst-b business "$K/test_schemas.py"
  b=$?
  report 4 "시각 칸 전수 +09:00(자정 넘김 포함)" "$(all0 $p $b)"
fi

# ── 5. 444 선언 전수 ──
if want 5; then
  run_tests t444 pure "$C/test_api_errors.py" "$C/test_api_contract.py" -k 444
  report 5 "토큰을 받는 동작 전수가 444 를 선언" "$?"
fi

# ── 6. factors 새·옛 꼴과 recordType ──
if want 6; then
  run_tests factors business esgapi/reference/tests/test_api.py -k "list_shape or record_type"
  report 6 "factors {count,isNext,results} = 옛 넷 · recordType·record_type · 둘 다 422" "$?"
fi

# ── 7. 페이지 꼴 셋(순수) ──
if want 7; then
  run_tests pages pure "$K/test_schemas.py" -k "page or subclass"
  report 7 "LimitOffset·PageNumber·Cursor 꼴" "$?"
fi

# ── 8. 접근 줄 code ──
if want 8; then
  run_tests access pure "$K/test_observability_middleware.py" "$K/test_observability_jsonlog.py" -k "code or twenty_one"
  report 8 "접근 줄 code(대문자 snake 만)" "$?"
fi

# ── 9. 중첩 strict(ISSUE-92) — 파일 하나로 돌려도 초록 ──
if want 9; then
  run_tests strict pure "$C/test_request_schemas_reject_bool.py"
  report 9 "reject_bool 중첩 TypedDict·true·1.0·\"1\"·파일 하나로 초록" "$?"
fi

# ── 10. 심은 파손 전부 빨강 ──
if want 10; then
  (cd "$API_PY" && E2_OUT="$OUT" scripts/planted-breaks-E2.sh) > "$S4/planted.log" 2>&1
  e=$?
  grep -E "^\[|PLANTED|FINGERPRINT" "$S4/planted.log" | sed 's/^/    /'
  report 10 "심은 파손 아홉 전부 빨강" "$e"
fi

# ── 11. generated 다시 뽑아 cmp 같음 ──
if want 11; then
  G="$API_PY/generated"
  mkdir -p "$S4/generated-before"
  cp "$G/openapi.json" "$G/api.d.ts" "$G/api.d.ts.source-sha256" "$S4/generated-before/"
  (cd "$API_PY" && PATH="$NODE_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen.log" 2>&1
  e=$?
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    cmp -s "$S4/generated-before/$f" "$G/$f" || { echo "    $f 다름"; e=1; }
  done
  report 11 "generated 재생성 cmp 같음" "$e"
fi

# ── 12. 웹 타입 검사(생성 타입과 Equal 시험) ──
if want 12; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" pnpm -C apps/web typecheck) > "$S4/web-typecheck.log" 2>&1
  e=$?
  echo "    $(tail -1 "$S4/web-typecheck.log")"
  report 12 "pnpm -C apps/web typecheck" "$e"
fi

# ── 13. 닫힌 목록 밖 diff 0 ──
P='apps/api-py'
E="$P/esgapi"
# 발주서 §1 + 감독 허락(2026-10-16: 그린워싱 계약 테스트 gc1·gc2 의 기대 dict 넷, jsonlog.py·그 테스트, NinjaAPI description,
# 검증 뒤 고침 R1 의 config/urls.py · R3 의 core/calc/guards.py·inventory/service/schemas/inventory.py).
ALLOWED="^($E/core/exceptions\.py|$E/config/(api|urls)\.py|$E/core/schemas\.py|$E/core/service/schemas/(documents|runs)\.py|$E/user/service/schemas/(login|user|users)\.py|$E/reference/service/(apis|schemas)/reference\.py|$E/core/observability/(middleware|jsonlog)\.py|$E/core/calc/guards\.py|$E/inventory/service/schemas/inventory\.py|$E/(config|core|inventory|organization|reference|user)/tests/.*|$E/greenwash/tests/test_contracts_gc[12]\.py|$P/tests/(security|support)/.*|$P/tests_integration/test_(flow|upload_flow)\.py|$P/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)|$P/scripts/(section4|planted-breaks)-E2\.sh)$"
if want 13; then
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(wc -l < "$S4/outside.txt" | tr -d ' ')
  mig=$(grep -c "/migrations/" "$S4/changed.txt")
  web=$(grep -c "^apps/web/" "$S4/changed.txt")
  gw=$(grep "^$E/greenwash/" "$S4/changed.txt" | grep -vc "tests/test_contracts_gc[12]\.py")
  echo "    바뀐 파일 $(wc -l < "$S4/changed.txt" | tr -d ' '), 밖 $n, 마이그레이션 $mig, 웹 $web, 그린워싱(계약 테스트 둘 밖) $gw"
  cat "$S4/outside.txt"
  report 13 "닫힌 목록 밖 diff 0·마이그레이션·웹·그린워싱 몸 0" "$([ "$n$mig$web$gw" = 0000 ] && echo 0 || echo 1)"
fi

# ── 14. 빠른 게이트 ──
if want 14; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  echo "    $(tail -1 "$S4/verify-fast.log")"
  report 14 "verify.sh --fast" "$(tail -1 "$S4/verify-fast.log" | grep -q '^VERIFY_FAST=PASS$' && echo 0 || echo 1)"
fi

# ── 15. 게이트 자기 검사 ──
if want 15; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  echo "    $(tail -1 "$S4/check-gates.log")"
  report 15 "check-gates.sh" "$e"
fi

# ── 16·17. 업무 층·보안 층 전부(덧붙임 — 오류 글자를 읽는 테스트가 고루 퍼져 있다) ──
if want 16; then
  run_tests business-all business -n 4
  report 16 "업무 층 전부" "$?"
fi
if want 17; then
  run_tests security-all security
  report 17 "보안 층 전부" "$?"
fi

if [ "$AFTER" = 1 ]; then
  git -C "$ROOT" status --porcelain > "$S4/status.txt"
  n=$(wc -l < "$S4/status.txt" | tr -d ' ')
  cat "$S4/status.txt"
  report 18 "커밋 뒤 git status --porcelain 0" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
