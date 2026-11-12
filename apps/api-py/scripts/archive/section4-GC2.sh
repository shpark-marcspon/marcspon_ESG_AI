#!/usr/bin/env bash
# 밴드 GC2 의 §4 자기검증(발주서 band-handoffs/GC2-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-GC2.sh                전부
#   apps/api-py/scripts/section4-GC2.sh --step 1,3     일부(번호는 발주서 §4 의 번호)
#
# 환경 변수:
#   GC2_BASE     기준 커밋(기본: 착수 때 적은 55e5611…)
#   GC2_OUT      산출물 자리(기본: 워크트리 곁의 GC2.out). 산출물은 $GC2_OUT/section4/ 아래
#   GC2_WORDS    기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt). 낱말을 찍지 않는다
# 컨테이너를 띄우지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
BASE="${GC2_BASE:-55e56114a9bc8ffd54c304b10487b08c973aa5da}"
OUT="${GC2_OUT:-$(cd "$ROOT/.." && pwd)/GC2.out}"
WORDS="${GC2_WORDS:-$(cd "$ROOT/.." && pwd)/G1a.out/forbidden-words.txt}"
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
# 닫힌 목록(발주서 §1-2).
ALLOWED="^($G/flows/review_shapes\.py|$G/flows/shapes\.py|$G/flows/terms_shapes\.py|$G/service/apis/greenwash\.py|$G/tests/test_contracts_gc1\.py|$G/tests/test_contracts_gc2\.py|$G/tests/flows/test_shapes\.py|$G/tests/data/flow-shapes/greenwash\.result@1\.schema\.json|$G/tests/data/flow-shapes/review/greenwash\.review@1\.schema\.json|$G/tests/data/flow-shapes/terms/.*\.json|$G/tests/data/contract-examples/review/review-(pending|in-review|confirmed)\.json|$P/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)|$P/scripts/(section4|planted-breaks)-GC2\.sh|$P/esgapi/config/tests/test_api_contract\.py|$P/esgapi/core/permissions\.py|$P/esgapi/core/tests/test_permissions\.py|$P/esgapi/core/tests/test_permissions_wiring\.py|$P/tests/security/test_tenant_paths\.py|$P/tests/security/test_login\.py)$"

# ── 1. 허용 경로 ──
if want 1; then
  changed_files > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(wc -l < "$S4/outside.txt" | tr -d ' ')
  echo "    바뀐 파일 $(wc -l < "$S4/changed.txt" | tr -d ' '), outside $n"
  cat "$S4/outside.txt"
  report 1 "허용 경로" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

# ── 2. 0줄 목록 ──
if want 2; then
  zero="$G/calc $G/flows/colab.py $G/flows/adapters.py $G/flows/pdfium_locate.py $G/flows/xlsx.py $G/flows/result.py $G/flows/gw1.py $G/flows/registration.py $G/flows/compare_shapes.py $G/tests/data/golden $G/tests/data/contract-examples/compare $P/pyproject.toml $P/uv.lock $P/.importlinter $P/esgapi/config/api.py $P/esgapi/config/tests/test_request_schemas_reject_bool.py apps/web README.md"
  # shellcheck disable=SC2086
  n=$( { git -C "$ROOT" diff --name-only "$BASE" -- $zero; git -C "$ROOT" ls-files -o --exclude-standard --full-name -- $zero; } | sort -u | tee "$S4/zero-hits.txt" | wc -l | tr -d ' ')
  results=$( { git -C "$ROOT" diff --name-only "$BASE" -- "$G/tests/data/contract-examples"; git -C "$ROOT" ls-files -o --exclude-standard --full-name -- "$G/tests/data/contract-examples"; } | grep -c '/contract-examples/result-.*\.json$')
  core=$(changed_files | grep "^$P/esgapi/core/" | grep -Ev "^$P/esgapi/core/(permissions\.py|tests/test_permissions\.py|tests/test_permissions_wiring\.py)$" | wc -l | tr -d ' ')
  echo "    0줄 목록 바뀐 것 $n, result-*.json 바뀐 것 $results, core 의 세 파일 밖 바뀐 것 $core"
  cat "$S4/zero-hits.txt"
  report 2 "0줄 목록" "$([ "$n$results$core" = 000 ] && echo 0 || echo 1)"
fi

# ── 3. 공유 파일 여섯: 허락한 줄뿐(지운 줄·더한 줄을 글자 그대로 견준다) ──
if want 3; then
  ok=0
  check_shared() { # check_shared <파일> <기대 파일>
    git -C "$ROOT" diff -U0 "$BASE" -- "$1" | grep -E '^[-+]' | grep -Ev '^(\+\+\+|---) ' > "$S4/shared-$(basename "$1").diff"
    if diff -u "$2" "$S4/shared-$(basename "$1").diff" > "$S4/shared-$(basename "$1").cmp"; then
      echo "    $1: 허락한 줄뿐(+$(grep -c '^+' "$2") -$(grep -c '^-' "$2"))"
    else
      echo "    $1: 허락 밖 줄"; sed 's/^/      /' "$S4/shared-$(basename "$1").cmp"; ok=1
    fi
  }
  cat > "$S4/want-test_api_contract.py" <<'EOF'
+    ("get", "/greenwash/runs/{run_id}/report"): "greenwash_report_get",
+    ("get", "/greenwash/terms/default"): "greenwash_terms_default",
-    """operationId 서른다섯이 표와 글자까지 같다. ninja 가 모듈 경로로 지은 이름(`esgapi_…`)은 0 이다."""
+    """operationId 서른일곱이 표와 글자까지 같다. ninja 가 모듈 경로로 지은 이름(`esgapi_…`)은 0 이다."""
-    assert len(found) == 35
-    assert len(set(found.values())) == 35
+    assert len(found) == 37
+    assert len(set(found.values())) == 37
-    assert (len(operations), len(with_body)) == (35, 16)
+    assert (len(operations), len(with_body)) == (37, 16)
-    """501 을 선언한 것은 새 여섯과 그린워싱 넷과 문서 만들기(두 칸에 값이 있을 때)뿐이다. 기존 열일곱의 나머지 꼴은
+    """501 을 선언한 것은 새 여섯과 그린워싱 다섯과 문서 만들기(두 칸에 값이 있을 때)뿐이다. 기존 열일곱의 나머지 꼴은
-    assert len(GREENWASH_CONTRACT_OPERATIONS) == 4
-    assert with_501 == NEW_OPERATIONS | GREENWASH_CONTRACT_OPERATIONS | {("post", "/documents")}
+    assert len(GREENWASH_CONTRACT_OPERATIONS) == 6
+    assert with_501 == (
+        NEW_OPERATIONS
+        | (GREENWASH_CONTRACT_OPERATIONS - {("get", "/greenwash/terms/default")})
+        | {("post", "/documents")}
+    )
EOF
  cat > "$S4/want-permissions.py" <<'EOF'
+    "greenwash_report_get": CUSTOMER,
+    "greenwash_terms_default": CUSTOMER,
EOF
  cat > "$S4/want-test_permissions.py" <<'EOF'
-# 권한 표를 글자로 한 번 더 적은 것(사용자 결정 2026-10-15 14:46 — 역할 둘). 회사 경로의 동작 23 은 고객사 사용자.
+# 권한 표를 글자로 한 번 더 적은 것(사용자 결정 2026-10-15 14:46 — 역할 둘). 회사 경로의 동작 25 는 고객사 사용자.
+    "greenwash_report_get",
+    "greenwash_terms_default",
-    assert len(NEEDS) == 28  # 분모: 회사 23 · 자기 2 · 운영 관리자 3(K2c)
+    assert len(NEEDS) == 30  # 분모: 회사 25 · 자기 2 · 운영 관리자 3(K2c)
-    assert len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 26  # 분모: 막힌 수
+    assert len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 28  # 분모: 막힌 수
EOF
  cat > "$S4/want-test_permissions_wiring.py" <<'EOF'
+    # 그린워싱 계약 보탬(밴드 GC2): 보고서 내려받기는 몸이 501, 기본 단어 목록은 200(둘 다 「400·401·403·405 아님」).
+    "greenwash_report_get": ("GET", "/greenwash/runs/1/report", None),
+    "greenwash_terms_default": ("GET", "/greenwash/terms/default", None),
EOF
  cat > "$S4/want-test_tenant_paths.py" <<'EOF'
+    # 그린워싱 계약 보탬(밴드 GC2): 보고서 내려받기는 몸이 501, 기본 단어 목록은 테넌트 행을 읽지 않는 공용 값.
+    ("GET", "/greenwash/runs/{run_id}/report"): "contract_only",
+    ("GET", "/greenwash/terms/default"): "reference",
-    assert (len(OPERATIONS), len(AUTHENTICATED)) == (35, 28)
+    assert (len(OPERATIONS), len(AUTHENTICATED)) == (37, 30)
EOF
  cat > "$S4/want-test_login.py" <<'EOF'
-    assert len(authenticated) == 28  # 분모: test_tenant_paths 의 표와 같은 수
+    assert len(authenticated) == 30  # 분모: test_tenant_paths 의 표와 같은 수
-    assert len(closed) == 26
-    # 회사 경로 23 은 쿠키만 본다(401 no_session). 사용자 관리 셋(K2c)은 Bearer 라 permitted 가 먼저 막는다(c-0-3).
+    assert len(closed) == 28
+    # 회사 경로 25 는 쿠키만 본다(401 no_session). 사용자 관리 셋(K2c)은 Bearer 라 permitted 가 먼저 막는다(c-0-3).
EOF
  check_shared "$P/esgapi/config/tests/test_api_contract.py" "$S4/want-test_api_contract.py"
  check_shared "$P/esgapi/core/permissions.py" "$S4/want-permissions.py"
  check_shared "$P/esgapi/core/tests/test_permissions.py" "$S4/want-test_permissions.py"
  check_shared "$P/esgapi/core/tests/test_permissions_wiring.py" "$S4/want-test_permissions_wiring.py"
  check_shared "$P/tests/security/test_tenant_paths.py" "$S4/want-test_tenant_paths.py"
  check_shared "$P/tests/security/test_login.py" "$S4/want-test_login.py"
  # GC1 테스트: 지운 줄은 :451 의 견줌 한 줄뿐
  git -C "$ROOT" diff -U0 "$BASE" -- "$G/tests/test_contracts_gc1.py" | grep -E '^-[^-]' > "$S4/gc1-minus.diff"
  if [ "$(cat "$S4/gc1-minus.diff")" = '-    assert {key: op["operationId"] for key, op in operations.items() if key[1].startswith("/greenwash")} == ROUTES' ]; then
    echo "    test_contracts_gc1.py: 지운 줄은 :451 견줌 하나"
  else
    echo "    test_contracts_gc1.py: 지운 줄이 다르다"; cat "$S4/gc1-minus.diff"; ok=1
  fi
  # shapes.py: 칸·타입 줄(들여쓰기 4 의 `이름: 타입`)이 바뀌지 않았다 — docstring·description 글자만
  git -C "$ROOT" diff -U0 "$BASE" -- "$G/flows/shapes.py" | grep -E '^[-+][^-+]' > "$S4/shapes.diff"
  fields=$(grep -Ec '^[-+]    [A-Za-z_]+: ' "$S4/shapes.diff")
  echo "    flows/shapes.py: 바뀐 줄 $(wc -l < "$S4/shapes.diff" | tr -d ' '), 그 가운데 칸 줄 $fields"
  [ "$fields" = 0 ] || ok=1
  # result@1 고정 스키마: 기준 커밋과 description 을 뺀 나머지(칸·타입·required·제약)가 같고, description 만 다르다
  git -C "$ROOT" show "$BASE:$G/tests/data/flow-shapes/greenwash.result@1.schema.json" > "$S4/result-base.schema.json"
  (cd "$API_PY" && uv run --frozen python - "$S4/result-base.schema.json" "esgapi/greenwash/tests/data/flow-shapes/greenwash.result@1.schema.json") <<'PY' > "$S4/result-shape.txt" 2>&1
import json, sys
def strip(node):
    if isinstance(node, dict):
        return {k: strip(v) for k, v in node.items() if k != "description"}
    if isinstance(node, list):
        return [strip(v) for v in node]
    return node
def descriptions(node, at=""):
    found = {}
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "description" and isinstance(v, str):
                found[at] = v
            else:
                found |= descriptions(v, f"{at}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found |= descriptions(v, f"{at}/{i}")
    return found
base, now = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
same = strip(base) == strip(now)
b, n = descriptions(base), descriptions(now)
changed = sorted(k for k in b.keys() | n.keys() if b.get(k) != n.get(k))
print(f"description 을 뺀 나머지 같음: {'예' if same else '아니오'}, 바뀐 description {len(changed)}: {', '.join(k or '(맨 위)' for k in changed) or '-'}")
sys.exit(0 if same and changed else 1)
PY
  e=$?
  echo "    result@1 고정 스키마(기준 ↔ 지금): $(cat "$S4/result-shape.txt")"
  [ "$e" = 0 ] || ok=1
  report 3 "공유 파일 여섯의 허락한 줄, GC1 테스트, shapes.py·result@1 칸 0" "$ok"
fi

# ── 4. 빠른 게이트 ──
if want 4; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  e=$?
  tail -1 "$S4/verify-fast.log"
  report 4 "verify.sh --fast" "$([ "$e" = 0 ] && tail -1 "$S4/verify-fast.log" | grep -q 'VERIFY_FAST=PASS' && echo 0 || echo 1)"
fi

# ── 5. 그린워싱 테스트 ──
if want 5; then
  (cd "$API_PY" && uv run --frozen pytest -q -p no:cacheprovider esgapi/greenwash) > "$S4/pytest-greenwash.log" 2>&1
  e=$?
  echo "    $(tail -1 "$S4/pytest-greenwash.log")"
  report 5 "pytest esgapi/greenwash" "$e"
fi

# ── 6. 계약·권한 테스트 ──
if want 6; then
  (cd "$API_PY" && uv run --frozen pytest -q -p no:cacheprovider esgapi/config/tests/test_api_contract.py esgapi/core/tests/test_permissions.py esgapi/config/tests/test_request_schemas_reject_bool.py) > "$S4/pytest-contract.log" 2>&1
  e=$?
  echo "    $(tail -1 "$S4/pytest-contract.log")"
  report 6 "pytest test_api_contract + test_permissions (+ reject_bool 0줄 확인)" "$e"
fi

# ── 7. 업무·보안 층 파일의 수집(돌리지 않는다 — DB 가 필요. 감독이 병합 뒤 main 전량에서) ──
if want 7; then
  (cd "$API_PY" && uv run --frozen pytest -q -p no:cacheprovider --collect-only esgapi/core/tests/test_permissions_wiring.py tests/security/test_tenant_paths.py tests/security/test_login.py) > "$S4/collect.log" 2>&1
  e=$?
  gw=$(grep -c 'test_permissions_wiring.py::test_raising_the_cell_makes_that_route_forbidden\[greenwash_' "$S4/collect.log")
  tp=$(grep -Ec 'test_tenant_paths.py::.*(report|terms)' "$S4/collect.log")
  echo "    $(tail -1 "$S4/collect.log"), wiring 의 greenwash 갈래 $gw(여섯이어야), tenant_paths 의 report·terms 갈래 $tp"
  report 7 "wiring·tenant_paths·login 수집(돌리지 않음)" "$([ "$e" = 0 ] && [ "$gw" = 6 ] && [ "$tp" -ge 1 ] && echo 0 || echo 1)"
fi

# ── 8. 생성물을 다시 뽑아 바이트가 같다 ──
if want 8; then
  before=$(cd "$API_PY" && shasum -a 256 generated/openapi.json generated/api.d.ts generated/api.d.ts.source-sha256)
  (cd "$API_PY" && PATH="$NODE_PATH_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen-ts-types.log" 2>&1
  e=$?
  after=$(cd "$API_PY" && shasum -a 256 generated/openapi.json generated/api.d.ts generated/api.d.ts.source-sha256)
  echo "$after" | sed 's/^/    /'
  if [ "$e" != 0 ]; then echo "    gen-ts-types.sh 실패(네트워크?) — $S4/gen-ts-types.log"; fi
  # 커밋 뒤(HEAD ≠ 기준)라면 git diff --exit-code 로 커밋과도 같아야 한다. 커밋 전에는 「다시 뽑아도 같다」만 본다.
  committed=0
  if [ "$(git -C "$ROOT" rev-parse HEAD)" != "$BASE" ]; then
    git -C "$ROOT" diff --exit-code --quiet HEAD -- "$P/generated" || committed=1
    echo "    git diff --exit-code HEAD -- generated: $([ "$committed" = 0 ] && echo 0 || echo 1)"
  else
    echo "    커밋 전(HEAD = 기준): 커밋과의 견줌은 커밋 뒤에 다시 돈다"
  fi
  report 8 "generated/ 셋을 다시 뽑아도 같은 바이트" "$([ "$e" = 0 ] && [ "$before" = "$after" ] && [ "$committed" = 0 ] && echo 0 || echo 1)"
fi

# ── 9. 심은 파손 ──
if want 9; then
  GC2_OUT="$OUT" "$API_PY/scripts/planted-breaks-GC2.sh" > "$S4/planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^원본' "$S4/planted.log" | sed 's/^/    /'
  report 9 "심은 파손 $(tail -1 "$S4/planted.log")" "$([ "$e" = 0 ] && tail -1 "$S4/planted.log" | grep -q '^PLANTED=11/11$' && echo 0 || echo 1)"
fi

# ── 10. 기업명·키 꼴·금지 확장자 ──
if want 10; then
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록 $WORDS 가 없다"
    report 10 "기업명·키 꼴·확장자" 1
  else
    hits=0; keys=0
    : > "$S4/forbidden-hits.txt"
    # 추적 diff(더한 줄)와 새 파일
    git -C "$ROOT" diff "$BASE" | grep '^+' > "$S4/added-lines.txt"
    for f in $(git -C "$ROOT" ls-files -o --exclude-standard --full-name); do cat "$ROOT/$f" >> "$S4/added-lines.txt"; done
    if grep -F -i -q -f "$WORDS" "$S4/added-lines.txt"; then hits=$(grep -F -i -c -f "$WORDS" "$S4/added-lines.txt"); fi
    # 이 스크립트 자신(검사 정규식이 든다)은 빼고 본다: 추적 diff 와 새 파일을 이 스크립트 없이 다시 모은다
    git -C "$ROOT" diff "$BASE" -- . ":(exclude)$P/scripts/section4-GC2.sh" | grep '^+' > "$S4/added-keys.txt"
    for f in $(git -C "$ROOT" ls-files -o --exclude-standard --full-name); do
      [ "$f" = "$P/scripts/section4-GC2.sh" ] || cat "$ROOT/$f" >> "$S4/added-keys.txt"
    done
    if grep -E -q 'sk-[A-Za-z0-9]|AIza[0-9A-Za-z_-]{30,}' "$S4/added-keys.txt"; then keys=$((keys + 1)); echo "    키 꼴(sk-…)이 있다"; fi
    if grep -E -q 'manufac-erp|spike/\.env' "$S4/added-keys.txt"; then keys=$((keys + 1)); echo "    키 파일 경로가 있다"; fi
    rm -f "$S4/added-keys.txt"
    msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
    mhits=0
    if [ -n "$msgs" ] && printf '%s' "$msgs" | grep -F -i -q -f "$WORDS"; then mhits=1; fi
    ext=$(changed_files | grep -Ec '\.(pdf|ipynb|xlsx)$')
    rm -f "$S4/added-lines.txt"  # 더한 줄의 사본을 남기지 않는다
    echo "    낱말 $(grep -c . "$WORDS")개: 걸린 줄 $hits, 커밋 메시지 $mhits(커밋 $(git -C "$ROOT" rev-list --count "$BASE..HEAD")개), 키 꼴·키 파일 $keys, .pdf·.ipynb·.xlsx $ext"
    report 10 "기업명·키 꼴·확장자" "$([ "$hits$mhits$keys$ext" = 0000 ] && echo 0 || echo 1)"
  fi
fi

# ── 11. G1a·G1c·G1d 의 자기검증 다시(그린워싱 흐름 0줄의 확인) ──
if want 11; then
  mkdir -p "$OUT/g1a"
  (cd "$API_PY" && G1A_OUT="$OUT/g1a" G1A_HELPERS="$OUT/g1a" G1A_BASE="$BASE" scripts/section4-G1a.sh --step 9,10,11,13,15,17,18) > "$S4/g1a.log" 2>&1
  e=$?
  grep -E '^\[|SECTION4_FAIL' "$S4/g1a.log" | sed 's/^/    /'
  report 11 "section4-G1a.sh --step 9,10,11,13,15,17,18" "$([ "$e" = 0 ] && grep -q '^SECTION4_FAIL=0$' "$S4/g1a.log" && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
