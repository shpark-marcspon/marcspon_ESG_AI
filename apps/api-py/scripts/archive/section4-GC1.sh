#!/usr/bin/env bash
# 밴드 GC1 의 §4 자기검증(발주서 band-handoffs/GC1-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-GC1.sh                전부
#   apps/api-py/scripts/section4-GC1.sh --step 1,2     일부(번호는 발주서 §4 의 번호, 8 은 이 스크립트가 더한 것)
#
# 환경 변수:
#   GC1_BASE     기준 커밋(기본: G1a 의 C0 bf8d2f2…)
#   GC1_OUT      산출물 자리(기본: 워크트리 곁의 GC1.out). 산출물은 $GC1_OUT/section4/ 아래
#   GC1_WORDS    기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt). 낱말을 찍지 않는다
# macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
BASE="${GC1_BASE:-bf8d2f282286f0706ddd141143e17a65934e29a3}"
OUT="${GC1_OUT:-$(cd "$ROOT/.." && pwd)/GC1.out}"
WORDS="${GC1_WORDS:-$(cd "$ROOT/.." && pwd)/G1a.out/forbidden-words.txt}"
S4="$OUT/section4"
mkdir -p "$S4"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"

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

P='apps/api-py'
G="$P/esgapi/greenwash"
# 닫힌 목록(발주서 §1-2). 예시·고정 스키마의 자리는 감독 결정(2026-10-15 밤)으로 계약 이름의 한 단 아래 폴더다.
ALLOWED="^($G/flows/compare_shapes\.py|$G/flows/review_shapes\.py|$G/api\.py|$G/service/__init__\.py|$G/service/apis/__init__\.py|$G/service/apis/greenwash\.py|$G/tests/test_contracts_gc1\.py|$G/tests/test_contracts_gc1_business\.py|$G/tests/data/flow-shapes/compare/greenwash\.compare@1\.schema\.json|$G/tests/data/flow-shapes/review/greenwash\.review@1\.schema\.json|$G/tests/data/contract-examples/compare/compare-.*\.json|$G/tests/data/contract-examples/review/review-.*\.json|$P/scripts/section4-GC1\.sh|$P/scripts/planted-breaks-GC1\.sh|$P/esgapi/config/api\.py|$P/esgapi/config/tests/test_api_contract\.py|$P/esgapi/config/tests/test_request_schemas_reject_bool\.py|$P/esgapi/core/permissions\.py|$P/esgapi/core/tests/test_permissions\.py|$P/esgapi/core/tests/test_permissions_wiring\.py|$P/generated/openapi\.json|$P/generated/api\.d\.ts|$P/generated/api\.d\.ts\.source-sha256)$"
CORE_THREE="^$P/esgapi/core/(permissions\.py|tests/test_permissions\.py|tests/test_permissions_wiring\.py)$"

# ── 1. 허용 경로 ──
if want 1; then
  changed_files > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(wc -l < "$S4/outside.txt" | tr -d ' ')
  echo "    바뀐 파일 $(wc -l < "$S4/changed.txt" | tr -d ' '), outside $n"
  cat "$S4/outside.txt"
  report 1 "허용 경로" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

# ── 2. 0줄 목록과 공유 파일의 줄 ──
if want 2; then
  ok=0
  # G1a 의 파일(기준 커밋에 있던 greenwash 아래 전부), core 의 세 파일 밖, 보안 표, 의존성, importlinter, web
  g1a=$(git -C "$ROOT" ls-tree -r --name-only "$BASE" -- "$G")
  n=$(git -C "$ROOT" diff --name-only "$BASE" -- $g1a | wc -l | tr -d ' ')
  echo "    G1a 의 파일 $(echo "$g1a" | wc -l | tr -d ' ')개 가운데 바뀐 것 $n"
  [ "$n" = 0 ] || ok=1
  core=$(changed_files | grep "^$P/esgapi/core/" | grep -Ev "$CORE_THREE" | wc -l | tr -d ' ')
  echo "    core 의 세 파일 밖 바뀐 것 $core"
  [ "$core" = 0 ] || ok=1
  other=$(changed_files | grep -E "^($P/tests/security/test_tenant_paths\.py|$P/pyproject\.toml|$P/uv\.lock|$P/\.importlinter|apps/web/.*)$" | wc -l | tr -d ' ')
  echo "    test_tenant_paths·pyproject·uv.lock·.importlinter·apps/web 바뀐 것 $other"
  [ "$other" = 0 ] || ok=1
  # core 세 파일: 지운 줄 0
  for f in $P/esgapi/core/permissions.py $P/esgapi/core/tests/test_permissions.py $P/esgapi/core/tests/test_permissions_wiring.py; do
    del=$(git -C "$ROOT" diff --numstat "$BASE" -- "$f" | awk '{print $2}')
    add=$(git -C "$ROOT" diff --numstat "$BASE" -- "$f" | awk '{print $1}')
    echo "    $f: +${add:-0} -${del:-0}"
    [ "${del:-0}" = 0 ] || ok=1
  done
  # config/api.py: 더한 줄 둘(import, add_router)뿐
  git -C "$ROOT" diff -U0 "$BASE" -- "$P/esgapi/config/api.py" | grep '^[-+][^-+]' > "$S4/config-api.diff"
  expected='+from esgapi.greenwash.api import router as greenwash_router
+api.add_router("/greenwash", greenwash_router, auth=session_cookie)'
  if [ "$(cat "$S4/config-api.diff")" = "$expected" ]; then echo "    config/api.py: 두 줄 더하기뿐"; else echo "    config/api.py: 허락 밖 줄"; cat "$S4/config-api.diff"; ok=1; fi
  # test_api_contract.py: 허락한 줄뿐(OPERATION_IDS 넷, MODULE_PREFIXES 하나, 숫자 셋 자리)
  git -C "$ROOT" diff -U0 "$BASE" -- "$P/esgapi/config/tests/test_api_contract.py" | grep '^[-+][^-+]' > "$S4/contract.diff"
  bad=$(grep -Ev '^\+    \("(get|put)", "/greenwash/[^"]*"\): "greenwash_[a-z_]+",$|^\+    "/greenwash/",$|^[-+]    """operationId (열일곱이|스물하나가) 표와 글자까지 같다\. ninja 가 모듈 경로로 지은 이름\(`esgapi_…`\)은 0 이다\."""$|^[-+]    assert len\(found\) == [0-9]+$|^[-+]    assert len\(set\(found\.values\(\)\)\) == [0-9]+$|^[-+]    assert \(len\(operations\), len\(with_body\)\) == \([0-9]+, [0-9]+\)$' "$S4/contract.diff" | wc -l | tr -d ' ')
  ops=$(grep -Ec '^\+    \("(get|put)", "/greenwash/' "$S4/contract.diff")
  minus=$(grep -c '^-' "$S4/contract.diff")
  echo "    test_api_contract.py: 허락 밖 줄 $bad, 더한 operationId $ops, 지운 줄 $minus(숫자 자리 넷이어야)"
  [ "$bad" = 0 ] && [ "$ops" = 4 ] && [ "$minus" = 4 ] || ok=1
  # test_request_schemas_reject_bool.py: BODY_OPERATIONS·REQUEST_MODELS 두 숫자만(백엔드 허락, MARC-TICK-95 노트 2026-10-15 밤)
  git -C "$ROOT" diff -U0 "$BASE" -- "$P/esgapi/config/tests/test_request_schemas_reject_bool.py" | grep -E '^[-+][^-+]' > "$S4/reject-bool.diff"
  expected_bool='-BODY_OPERATIONS = 8
-REQUEST_MODELS = 17
+BODY_OPERATIONS = 9
+REQUEST_MODELS = 18'
  if [ "$(cat "$S4/reject-bool.diff")" = "$expected_bool" ]; then
    echo "    test_request_schemas_reject_bool.py: 두 숫자뿐"
  else
    echo "    test_request_schemas_reject_bool.py: 허락 밖 줄"; cat "$S4/reject-bool.diff"; ok=1
  fi
  report 2 "0줄 목록과 공유 파일의 허락한 줄" "$ok"
fi

# ── 3. 빠른 게이트 ──
if want 3; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  e=$?
  tail -1 "$S4/verify-fast.log"
  grep -E 'EXIT=|Contracts:|passed|failed' "$S4/verify-fast.log" | sed 's/^/    /' | head -60
  report 3 "verify.sh --fast" "$([ "$e" = 0 ] && tail -1 "$S4/verify-fast.log" | grep -q 'VERIFY_FAST=PASS' && echo 0 || echo 1)"
fi

# ── 4. 이 밴드의 테스트 ──
if want 4; then
  (cd "$API_PY" && uv run --frozen pytest -q -p no:cacheprovider esgapi/greenwash esgapi/config/tests/test_api_contract.py esgapi/core/tests/test_permissions.py) > "$S4/pytest.log" 2>&1
  e=$?
  echo "    $(tail -1 "$S4/pytest.log")"
  report 4 "pytest greenwash + test_api_contract + test_permissions" "$e"
fi

# ── 5. 생성물을 다시 뽑아 바이트가 같다 ──
if want 5; then
  before=$(cd "$API_PY" && shasum -a 256 generated/openapi.json generated/api.d.ts generated/api.d.ts.source-sha256)
  (cd "$API_PY" && PATH="$NODE_PATH_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen-ts-types.log" 2>&1
  e=$?
  after=$(cd "$API_PY" && shasum -a 256 generated/openapi.json generated/api.d.ts generated/api.d.ts.source-sha256)
  echo "$after" | sed 's/^/    /'
  if [ "$e" != 0 ]; then echo "    gen-ts-types.sh 실패(네트워크?) — $S4/gen-ts-types.log"; fi
  report 5 "generated/ 셋을 다시 뽑아도 같은 바이트" "$([ "$e" = 0 ] && [ "$before" = "$after" ] && echo 0 || echo 1)"
fi

# ── 6. 기업명·키 꼴·금지 확장자 ──
if want 6; then
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록 $WORDS 가 없다"
    report 6 "기업명·키 꼴·확장자" 1
  else
    hits=0; keys=0
    : > "$S4/forbidden-hits.txt"
    while IFS= read -r f; do
      [ -f "$ROOT/$f" ] || continue
      if grep -F -i -q -f "$WORDS" "$ROOT/$f"; then echo "$f" >> "$S4/forbidden-hits.txt"; hits=$((hits + 1)); fi
      if grep -E -q 'sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]+|AIza[0-9A-Za-z_-]{30,}' "$ROOT/$f"; then echo "    키 꼴: $f"; keys=$((keys + 1)); fi
      case "$f" in "$P/scripts/section4-GC1.sh") continue ;; esac
      if grep -E -q 'manufac-erp|spike/\.env' "$ROOT/$f"; then echo "    키 파일 경로: $f"; keys=$((keys + 1)); fi
    done < <(changed_files)
    msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
    mhits=0
    if [ -n "$msgs" ] && printf '%s' "$msgs" | grep -F -i -q -f "$WORDS"; then mhits=1; fi
    ext=$(changed_files | grep -Ec '\.(pdf|ipynb|xlsx)$')
    echo "    낱말 $(grep -c . "$WORDS")개로 본 파일 $(changed_files | wc -l | tr -d ' '): 걸린 파일 $hits, 커밋 메시지 $mhits, 키 꼴·키 파일 $keys, .pdf·.ipynb·.xlsx $ext"
    cat "$S4/forbidden-hits.txt"
    report 6 "기업명·키 꼴·확장자" "$([ "$hits$mhits$keys$ext" = 0000 ] && echo 0 || echo 1)"
  fi
fi

# ── 7. 심은 파손 ──
if want 7; then
  GC1_OUT="$OUT" "$API_PY/scripts/planted-breaks-GC1.sh" > "$S4/planted.log" 2>&1
  e=$?
  sed 's/^/    /' "$S4/planted.log"
  report 7 "심은 파손 $(tail -1 "$S4/planted.log")" "$([ "$e" = 0 ] && tail -1 "$S4/planted.log" | grep -q '^PLANTED=14/14$' && echo 0 || echo 1)"
fi

# ── 8. 업무 층 파일의 수집(돌리지 않는다 — DB 가 필요. 감독이 병합 뒤 main 전량에서) ──
if want 8; then
  (cd "$API_PY" && uv run --frozen pytest -q -p no:cacheprovider --collect-only esgapi/core/tests/test_permissions_wiring.py) > "$S4/wiring-collect.log" 2>&1
  e=$?
  gw=$(grep -c 'greenwash_' "$S4/wiring-collect.log")
  echo "    $(tail -1 "$S4/wiring-collect.log"), greenwash 갈래 $gw"
  report 8 "test_permissions_wiring.py 수집(돌리지 않음)" "$([ "$e" = 0 ] && [ "$gw" = 4 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
