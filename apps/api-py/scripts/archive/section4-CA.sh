#!/usr/bin/env bash
# 밴드 CA 의 §4 자기검증(발주서 band-handoffs/CA-order.md §4 + 덧붙임 2 CA-order-2.md — 인증 ㉠ Bearer 통일, K2b).
# 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-CA.sh                  전부
#   apps/api-py/scripts/section4-CA.sh --step 1,3       일부(번호는 발주서 §4 의 번호)
#   apps/api-py/scripts/section4-CA.sh --after-commit   전부 + git status --porcelain 0
#
# 환경 변수:
#   CA_BASE   기준 커밋(기본: 워크트리를 만들 때의 main 97cda96)
#   CA_OUT    산출물 자리(기본: 워크트리 곁의 CA.out). 산출물은 $CA_OUT/section4/ 아래
# DB 를 쓰는 단계(1~6, 13)는 이 워크트리의 compose(.env 의 COMPOSE_PROJECT_NAME)의 postgres 가 떠 있어야 한다 —
# 띄우고 내리는 일은 부르는 쪽(러너의 컨테이너 규칙)이 한다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
BASE="${CA_BASE:-97cda96}"
OUT="${CA_OUT:-$(cd "$ROOT/.." && pwd)/CA.out}"
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

both() { # 둘 다 0 이면 0
  [ "$1" = 0 ] && [ "$2" = 0 ] && echo 0 || echo 1
}

U="esgapi/user/tests/service"

# ── 1. 회사 경로가 Bearer 를 받는다(두 길의 격리) ──
if want 1; then
  run_tests two-ways security tests/security/test_tenant_paths.py -k "bearer or session"
  report 1 "회사 경로 두 길(via session·bearer) — 남의 행 0" "$?"
fi

# ── 2. 운영 관리자 Bearer → 회사 경로 401 company_required ──
if want 2; then
  run_tests company-required-p pure esgapi/core/tests/auth/test_bearer.py -k "company_auth or company_bearer"
  p=$?
  run_tests company-required-b business "$U/apis/test_login.py" -k company_required
  b=$?
  run_tests company-required-s security tests/security/test_tenant_paths.py tests/security/test_login.py \
    -k "operator_bearer"
  report 2 "운영 관리자 Bearer → 회사 동작 24 401 company_required(행 0)" "$( [ "$p$b$?" = 000 ] && echo 0 || echo 1)"
fi

# ── 3. 옛 교환 쿠키는 그대로, 틀린 Bearer 는 쿠키로 넘어가지 않고 444 ──
if want 3; then
  run_tests bad-bearer security tests/security/test_tenant_paths.py -k "bad_bearer or session"
  report 3 "옛 교환 쿠키 읽힘·틀린 Bearer 444(쿠키로 안 넘어감)" "$?"
fi

# ── 4. is_initial → 403 password_change_required ──
if want 4; then
  run_tests initial-p pure esgapi/core/tests/auth/test_bearer.py -k initial
  p=$?
  run_tests initial-s security tests/security/test_login.py -k initial_user_reaches_only
  report 4 "is_initial 403 password_change_required(Bearer 로 회사 동작 24·사용자 관리 셋)" "$(both "$p" "$?")"
fi

# ── 5. D3 교환이 비활성 사용자를 거절 ──
if want 5; then
  run_tests d3 business "$U/apis/test_user.py" "$U/services/test_user.py" -k "inactive"
  report 5 "D3 교환의 is_active" "$?"
fi

# ── 6. D5 EDK 행과 비밀번호 행 ──
if want 6; then
  run_tests d5 business "$U/apis/test_user.py" "$U/apis/test_users.py" "$U/actions/test_password.py" \
    -k "password_user or exchange_user"
  report 6 "D5 교환이 비밀번호 행을 덮지 않음·EDK 행 초기화 거절" "$?"
fi

# ── 7. D9 감사 extra 가 JSON 글자에 ──
if want 7; then
  run_tests d9-p pure esgapi/core/tests/test_observability_jsonlog.py esgapi/core/tests/test_observability_middleware.py \
    -k "audit or user_id"
  p=$?
  run_tests d9-b business "$U/services/test_login.py" -k real_audit_note
  report 7 "D9 JSON 포매터의 글자(감사 extra·접근 줄 user_id)" "$(both "$p" "$?")"
fi

# ── 8. auth= 차례(Bearer 먼저)와 첫 문장 ──
if want 8; then
  E8="$API_PY/esgapi"
  # 코드 줄만 센다(docstring 의 같은 글자는 뺀다 — 줄머리가 auth= 이거나 api.add_router 인 줄)
  good=$(grep -rhE '^[[:space:]]*(auth=|api\.add_router).*auth=\[company_scoped_auth_or_next, session_cookie\]|^[[:space:]]*auth=\[company_scoped_auth_or_next, session_cookie\]' "$E8" --include='*.py' | wc -l | tr -d ' ')
  bad=$(grep -rn 'auth=\[session_cookie' "$E8" --include='*.py' | wc -l | tr -d ' ')
  ps=$(grep -rn 'permitted_session(' "$E8" --include='*.py' | grep -v '/tests/' | grep -v 'def permitted_session' | wc -l | tr -d ' ')
  echo "    Bearer 먼저 목록 $good(config 셋 + 모듈 경로 9 = 12), 차례 뒤집힘 $bad, permitted_session( 호출 $ps(accounts_me 하나)"
  report 8 "auth= 차례 Bearer 먼저·permitted_session 은 GET /me 하나" "$([ "$good:$bad:$ps" = "12:0:1" ] && echo 0 || echo 1)"
fi

# ── 9. 닫힌 목록 밖 diff 0 ──
P='apps/api-py'
E="$P/esgapi"
# 발주서 §1 + 감독 처분(2026-10-16: tests/support/http.py · inventory/tests/test_api.py · greenwash/service/apis/greenwash.py
# 의 두 줄 · documents.py·runs.py 의 머리말 표 줄) + 덧붙임 2(K2b b-1-2 의 목록 · greenwash 의 첫 문장·444 펼침과 그
# 계약 테스트 둘 · organization 의 selectors·services 와 그 테스트).
ALLOWED="^($E/core/tenancy/(session|middleware)\.py|$E/core/auth/.*|$E/user/.*|$E/core/permissions\.py|$E/core/schemas\.py|$E/core/observability/(middleware|jsonlog)\.py|$E/config/api\.py|$E/core/service/apis/(documents|runs)\.py|$E/organization/service/(apis|selectors|services)/organization\.py|$E/organization/tests/service/(selectors|services)/test_organization\.py|$E/(inventory|reference)/service/apis/(inventory|reference)\.py|$E/greenwash/service/apis/greenwash\.py|$E/greenwash/tests/test_contracts_gc[12]\.py|$E/config/tests/(test_api_contract|test_request_schemas_reject_bool)\.py|$E/core/tests/.*|$E/inventory/tests/test_api\.py|$P/tests/security/.*|$P/tests/support/http\.py|$P/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)|$P/scripts/section4-CA\.sh)$"
if want 9; then
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(wc -l < "$S4/outside.txt" | tr -d ' ')
  mig=$(grep -c "^$E/user/migrations/" "$S4/changed.txt")
  echo "    바뀐 파일 $(wc -l < "$S4/changed.txt" | tr -d ' '), 밖 $n, 마이그레이션 $mig"
  cat "$S4/outside.txt"
  report 9 "닫힌 목록 밖 diff 0·마이그레이션 0" "$([ "$n$mig" = 00 ] && echo 0 || echo 1)"
fi

# ── 10. generated 다시 뽑아 cmp 같음 ──
if want 10; then
  G="$API_PY/generated"
  mkdir -p "$S4/generated-before"
  cp "$G/openapi.json" "$G/api.d.ts" "$G/api.d.ts.source-sha256" "$S4/generated-before/"
  (cd "$API_PY" && PATH="$NODE_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen.log" 2>&1
  e=$?
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    cmp -s "$S4/generated-before/$f" "$G/$f" || { echo "    $f 다름"; e=1; }
  done
  report 10 "generated 재생성 cmp 같음" "$e"
fi

# ── 11. 빠른 게이트 ──
if want 11; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  echo "    $(tail -1 "$S4/verify-fast.log")"
  report 11 "verify.sh --fast" "$(tail -1 "$S4/verify-fast.log" | grep -q '^VERIFY_FAST=PASS$' && echo 0 || echo 1)"
fi

# ── 12. 게이트 자기 검사 ──
if want 12; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  echo "    $(tail -1 "$S4/check-gates.log")"
  report 12 "check-gates.sh" "$e"
fi

# ── 13. 보안 층 전부 ──
if want 13; then
  run_tests security security
  report 13 "보안 층 tests/security" "$?"
fi

if [ "$AFTER" = 1 ]; then
  git -C "$ROOT" status --porcelain > "$S4/status.txt"
  n=$(wc -l < "$S4/status.txt" | tr -d ' ')
  cat "$S4/status.txt"
  report 14 "커밋 뒤 git status --porcelain 0" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
