#!/usr/bin/env bash
# 밴드 RR1 의 §4 자기검증(발주서 band-handoffs/RR1-order.md §4 — 응답 꼴을 결과 꼴 TypedDict 하나에서).
# 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-RR1.sh                  1~9(10 은 RR1_FULL=1 일 때만)
#   apps/api-py/scripts/section4-RR1.sh --step 1,3       일부(번호는 발주서 §4 의 번호)
#   apps/api-py/scripts/section4-RR1.sh --after-commit   1~9 + git status --porcelain 0
#
# 환경 변수:
#   RR1_BASE   기준 커밋(기본: 워크트리를 만들 때의 main 4338571)
#   RR1_C1     커밋 ①(기본 fde8b0f) — bodies-before 를 뜬 HEAD
#   RR1_OUT    산출물 자리(기본: 워크트리 곁의 RR1.out). bodies-before/ 가 거기 있어야 한다(커밋 ① 직후에 뜬 것)
#   RR1_FULL   1 이면 10(전량 scripts/verify.sh)을 돈다. 러너는 돌리지 않는다(감독이 돈다).
# 업무 층(2·8)은 compose 의 Postgres 가 떠 있어야 한다(apps/api-py/scripts/test-business.sh). 앱·워커 컨테이너 0.
# generated/ 를 제자리에 다시 쓰지 않는다(6 은 산출물 자리에 뽑아 견준다). 6 의 api.d.ts 는
# pnpm dlx openapi-typescript@7.13.0 — 네트워크와 node/pnpm PATH 가 필요하다(못 지으면 그 줄만 적는다).
# 옛 판 글자는 이어 붙여 적는다(4 의 검사가 이 파일에 걸리지 않게).
# 실제 LLM 호출 0, API 키를 읽지 않는다. macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${RR1_BASE:-4338571}"
C1="${RR1_C1:-fde8b0f}"
OUT="${RR1_OUT:-$SIDE/RR1.out}"
S4="$OUT/section4"
mkdir -p "$S4"
NODE_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
A="apps/api-py"
E="$A/esgapi"
I="$E/inventory"
OLD="scope12.result@""1"

STEPS="all"
AFTER=0
case "${1:-}" in
  --step) STEPS=",${2:?--step 뒤에 번호}," ;;
  --after-commit) AFTER=1 ;;
  "") ;;
  *) echo "사용: $0 [--step 1,2,… | --after-commit]"; exit 2 ;;
esac
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

echo "기준 $BASE, 커밋 ① $C1, HEAD $(git -C "$ROOT" rev-parse --short HEAD), 산출물 $S4"

# ── 1. 빠른 게이트 ──
if want 1; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  echo "    $last"
  report 1 "verify.sh --fast" "$([ "$last" = "VERIFY_FAST=PASS" ] && echo 0 || echo 1)"
fi

# ── 2. inventory 시험 전부(순수 층 + 업무 층)와 계약 시험 ──
if want 2; then
  (cd "$API_PY" && PYTHONPYCACHEPREFIX="$S4/pycache" uv run --frozen pytest -q -p no:cacheprovider -n 4 \
    -m "not django_db and not security" esgapi/inventory/tests esgapi/config/tests/test_api_contract.py) \
    > "$S4/pure-tests.log" 2>&1
  pe=$?
  "$API_PY/scripts/test-business.sh" -p no:cacheprovider esgapi/inventory/tests > "$S4/business-tests.log" 2>&1
  be=$?
  echo "    순수 층: $(tail -1 "$S4/pure-tests.log") (종료 $pe)"
  echo "    업무 층: $(tail -1 "$S4/business-tests.log") (종료 $be)"
  report 2 "inventory 시험 전부·계약 시험" "$([ "$pe$be" = 00 ] && echo 0 || echo 1)"
fi

# ── 3. 심은 파손 일곱: 빨강, 되돌린 뒤 지문 같음 ──
if want 3; then
  (cd "$ROOT" && "$A/scripts/planted-breaks-RR1.sh") > "$S4/planted.log" 2>&1
  e=$?
  grep -v '^    | ' "$S4/planted.log"
  last=$(tail -1 "$S4/planted.log")
  report 3 "심은 파손 PLANTED=7/7·지문 같음" "$([ "$e" = 0 ] && [ "$last" = "PLANTED=7/7" ] && echo 0 || echo 1)"
fi

# ── 4. 쌍둥이·옛 판·예외 0(코드 줄만) ──
if want 4; then
  (cd "$ROOT" && python3 -I - "$E" "$I/service/schemas/inventory.py" "$I/tests/flows/test_shapes.py" "$OLD" <<'PY'
import ast
import sys
from pathlib import Path

root, route_py, test_shapes_py, old = sys.argv[1:5]
fail = 0

expected = {
    "CalcTiersIn", "CalcRowIn", "CalcIn", "Scope3TransportIn", "Scope3ShortlistRowIn", "Scope3ShortlistIn",
    "Scope3RowIn", "Scope3ClassifyIn",
    "Scope3CandidateOut", "Scope3RejectedOut", "Scope3CatalogOut", "Scope3ShortlistedOut", "Scope3NoCandidatesOut",
    "Scope3GroupClassifiedOut", "Scope3GroupFailedOut", "Scope3ClassifyOut",
}
declared = {n.name for n in ast.walk(ast.parse(Path(route_py).read_text(encoding="utf-8"))) if isinstance(n, ast.ClassDef)}
print(f"    inventory.py 의 클래스 {len(declared)}(기대 16) · 남는 것 {sorted(declared - expected)} · 빠진 것 {sorted(expected - declared)}")
fail += declared != expected


def docstrings(tree: ast.AST) -> set[int]:
    """docstring 자리의 Constant 노드 id."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                out.add(id(first.value))
    return out


hits: list[str] = []
files = sorted(Path(root).rglob("*.py"))
for path in files:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = docstrings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == old and id(node) not in skip:
            hits.append(f"{path}:{node.lineno}")
print(f"    esgapi 의 .py {len(files)} 개에서 옛 판 글자와 같은 문자열 상수(docstring 제외) {len(hits)}")
for hit in hits:
    print(f"      {hit}")
fail += len(hits)

tree = ast.parse(Path(test_shapes_py).read_text(encoding="utf-8"))
names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
names |= {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
gone = sorted(names & {"FROM_TO_FIRST", "kind_first", "typed_as_written", "PAIRS"})
print(f"    test_shapes.py 의 예외 정의 이름 {gone}")
fail += len(gone)
sys.exit(1 if fail else 0)
PY
  ) > "$S4/twins.log" 2>&1
  e=$?
  cat "$S4/twins.log"
  oldfile=$([ -e "$ROOT/$I/tests/data/flow-shapes/$OLD.schema.json" ] && echo 1 || echo 0)
  echo "    옛 판 고정 파일 있음 $oldfile"
  report 4 "쌍둥이 16 뿐·옛 판 상수 0·옛 고정 파일 없음·예외 0" "$([ "$e$oldfile" = 00 ] && echo 0 || echo 1)"
fi

# ── 5. 0줄 경로, 허용 경로 밖 diff 0 ──
ALLOWED="^($I/flows/(shapes|scope12)\.py|$I/service/schemas/inventory\.py|$I/service/apis/inventory\.py|$I/tests/data/flow-shapes/scope12\.result@[12]\.schema\.json|$I/tests/flows/test_shapes\.py|$I/tests/test_(flow_shapes|flows|api|route_shapes|route_bodies)\.py|$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)|$A/scripts/(section4|planted-breaks)-RR1\.sh)$"
ZERO="$I/calc/serialize.py $I/calc/scope3 $I/calc/types.py $I/calc/aggregate.py
$I/tests/data/flow-shapes/scope3.llm-first.result@2.schema.json $I/tests/data/golden $I/tests/data/scope3/golden
$E/greenwash $E/core $E/config $I/tests/test_scope3_api.py apps/web
scripts/verify.sh scripts/check-gates.sh scripts/git-hooks $A/.importlinter .env.example .dockerignore docker
compose.yaml $A/scripts/check-build-context.sh $A/pyproject.toml $A/uv.lock pnpm-lock.yaml"
if want 5; then
  { git -C "$ROOT" diff --name-only --no-renames "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } \
    | sort -u > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(grep -c . "$S4/outside.txt")
  # 닫힌 밴드의 §4·심은 파손 스크립트(RR1 의 것 말고)
  closed=$(git -C "$ROOT" diff --name-only "$BASE" -- "$A/scripts" | grep -E '(section4|planted-breaks)-' | grep -vc -- '-RR1\.sh$')
  # shellcheck disable=SC2086  # 경로 목록을 낱말로 나눈다
  zero=$(git -C "$ROOT" diff --name-only "$BASE" -- $ZERO | grep -c .)
  # shellcheck disable=SC2086
  zero_new=$(git -C "$ROOT" ls-files -o --exclude-standard -- $ZERO | grep -c .)
  echo "    바뀐 파일 $(grep -c . "$S4/changed.txt"), 허용 밖 $n, 0줄 목록 $zero(+새 파일 $zero_new), 닫힌 밴드 스크립트 $closed"
  sed 's/^/    바뀜: /' "$S4/changed.txt"
  sed 's/^/    밖: /' "$S4/outside.txt"
  report 5 "허용 밖 0·0줄 목록 0" "$([ "$n$zero$zero_new$closed" = 0000 ] && echo 0 || echo 1)"
fi

# ── 6. generated 다시 뽑아 같음(제자리에 다시 쓰지 않는다) ──
if want 6; then
  G="$A/generated"
  (cd "$API_PY" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$S4/openapi.json" 2> "$S4/export.log"
  xe=$?
  cmp -s "$S4/openapi.json" "$ROOT/$G/openapi.json"; oc=$?
  sha=$(shasum -a 256 "$S4/openapi.json" | cut -d' ' -f1)
  pinned=$(tr -d '[:space:]' < "$ROOT/$G/api.d.ts.source-sha256" | cut -c1-64)
  sc=$([ "$sha" = "$pinned" ] && echo 0 || echo 1)
  if PATH="$NODE_DIR:$PATH" pnpm dlx openapi-typescript@7.13.0 "$S4/openapi.json" -o "$S4/api.d.ts" \
    > "$S4/openapi-typescript.log" 2>&1; then
    cmp -s "$S4/api.d.ts" "$ROOT/$G/api.d.ts"; dc=$?
    dts="api.d.ts cmp $dc"
  else
    dc=0
    dts="api.d.ts 못 잼(openapi-typescript 실패 — $S4/openapi-typescript.log)"
  fi
  git -C "$ROOT" diff --quiet -- "$G"; wd=$?
  echo "    export 종료 $xe · openapi cmp $oc · sha256 같음 $([ "$sc" = 0 ] && echo 예 || echo 아니오) · $dts · 작업 트리 diff $wd"
  report 6 "generated 다시 뽑아 같음" "$([ "$xe$oc$sc$dc$wd" = 00000 ] && echo 0 || echo 1)"
fi

# ── 7. generated 의 바뀜이 D3 뿐(기준의 openapi.json 과) ──
if want 7; then
  git -C "$ROOT" show "$BASE:$A/generated/openapi.json" > "$S4/openapi.base.json"
  (cd "$ROOT" && python3 -I - "$S4/openapi.base.json" "$A/generated/openapi.json" "$I/tests/test_route_shapes.py" <<'PY'
import ast
import json
import sys
from pathlib import Path

base_path, new_path, test_path = sys.argv[1:4]
base, new = json.loads(Path(base_path).read_text()), json.loads(Path(new_path).read_text())
source = ast.parse(Path(test_path).read_text(encoding="utf-8"))
consts = {
    t.id: ast.literal_eval(n.value)
    for n in source.body
    if isinstance(n, ast.Assign)
    for t in n.targets
    if isinstance(t, ast.Name) and t.id in {"RENAMED", "REQUESTS", "ROUTE_ONLY"}
}
renamed, requests, route_only = consts["RENAMED"], consts["REQUESTS"], consts["ROUTE_ONLY"]
bs, ns = base["components"]["schemas"], new["components"]["schemas"]
fail = 0


def check(ok: bool, text: str) -> None:
    global fail
    print(f"    {'예' if ok else '★ 아니오'}: {text}")
    fail += not ok


def ops(doc: dict) -> dict:
    return {(p, m): o.get("operationId") for p, v in doc["paths"].items() for m, o in v.items()}


def retarget(node: object) -> object:
    """기준의 참조 이름을 새 이름으로 옮긴 것(paths 견주기용)."""
    if isinstance(node, dict):
        return {k: (f"#/components/schemas/{renamed.get(v.rsplit('/', 1)[1], v.rsplit('/', 1)[1])}" if k == "$ref" else retarget(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [retarget(v) for v in node]
    return node


check(list(base["paths"]) == list(new["paths"]), f"paths 키 같음({len(new['paths'])})")
check(ops(base) == ops(new), "operationId 같음")
check(retarget(base["paths"]) == new["paths"], "paths 본문은 참조 이름만 다름")
check(base.get("servers") == new.get("servers"), f"servers 같음 {new.get('servers')}")
check(len(bs) == len(ns) == 161, f"components 총수 {len(bs)} → {len(ns)}(161)")
old_inventory = {n for n in bs if (n.startswith("Calc") or n.startswith("Scope3")) and n.endswith("Out")}
check(len(old_inventory) == 43, f"기준의 inventory 응답 꼴 {len(old_inventory)}(43)")
check(set(bs) - set(ns) == set(renamed), f"사라진 이름 {len(set(bs) - set(ns))} = 바뀐 이름 짝 35 의 앞쪽")
check(set(ns) - set(bs) == set(renamed.values()), f"새 이름 {len(set(ns) - set(bs))} = 짝 35 의 뒤쪽")
new_inventory = set(renamed.values()) | route_only
check(len(new_inventory) == 43 and route_only <= set(ns), f"지금의 inventory 응답 꼴 {len(new_inventory)}(35 + 경로 전용 8)")
check(requests <= set(ns) and all(bs[n] == ns[n] for n in requests), "요청 꼴 8 이름 그대로·바이트 같음")
outside = set(bs) - old_inventory - requests
changed = sorted(n for n in outside if bs[n] != ns.get(n))
check(not changed, f"inventory 밖 components {len(outside)} 바이트 같음 {changed}")


def descriptions(schemas: dict, names: set) -> list:
    found = []
    for name in sorted(names):
        node = schemas[name]
        if "description" in node:
            found.append((name, None, node["description"]))
        for key, sub in node.get("properties", {}).items():
            if "description" in sub:
                found.append((name, key, sub["description"]))
    return found


before, after = descriptions(bs, old_inventory), descriptions(ns, new_inventory)
check(len(before) == 13 and len(after) == 13, f"inventory 응답 꼴의 설명 {len(before)} → {len(after)}(13)")
moved = {(renamed.get(n, n), k): t for n, k, t in before}
now = {(n, k): t for n, k, t in after}
same = [key for key, text in moved.items() if now.get(key) == text]
check(len(same) == 12, f"글자·자리 그대로 {len(same)}(12)")
evidence = moved.get(("CandidateEvidenceJson", None), "")
check(now.get(("Scope3ShortlistedOut", "evidence"), "").startswith(evidence) and evidence != "", "evidence 설명은 Scope3ShortlistedOut.evidence 로 옮고 옛 글자로 시작")
print("    이름 짝 35:")
for old_name, new_name in renamed.items():
    print(f"      {old_name} → {new_name}")
sys.exit(1 if fail else 0)
PY
  ) > "$S4/generated-d3.log" 2>&1
  e=$?
  cat "$S4/generated-d3.log"
  report 7 "generated 의 바뀜이 D3 뿐" "$e"
fi

# ── 8. 본문 바이트 같음(커밋 ① 의 bodies-before ↔ 지금) ──
if want 8; then
  B="$OUT/bodies-before"
  AF="$OUT/bodies-after"
  if [ ! -d "$B" ] || [ ! -f "$B/HEAD" ]; then
    echo "    bodies-before 가 없다($B) — 다시 뜨려면 감독 허락(② 뒤에는 「전」이 될 수 없다)"
    report 8 "본문 바이트 같음" 1
  else
    head_before=$(tr -d '[:space:]' < "$B/HEAD")
    c1_full=$(git -C "$ROOT" rev-parse "$C1")
    rm -rf "$AF"
    RR1_BODIES_DIR="$AF" "$API_PY/scripts/test-business.sh" -p no:cacheprovider \
      esgapi/inventory/tests/test_route_bodies.py > "$S4/bodies-after.log" 2>&1
    te=$?
    git -C "$ROOT" rev-parse HEAD > "$AF/HEAD"
    ls "$B" | grep -v '^HEAD$' > "$S4/bodies-before.names"
    ls "$AF" | grep -v '^HEAD$' > "$S4/bodies-after.names"
    cmp -s "$S4/bodies-before.names" "$S4/bodies-after.names"; ne=$?
    total=0; differ=0; failures=0
    while read -r name; do
      total=$((total + 1))
      case "$name" in calc-failure-*) failures=$((failures + 1)) ;; esac
      cmp -s "$B/$name" "$AF/$name" || { differ=$((differ + 1)); echo "    다름: $name"; }
    done < "$S4/bodies-before.names"
    echo "    T2: $(tail -1 "$S4/bodies-after.log") (종료 $te)"
    echo "    bodies-before HEAD $head_before · 커밋 ① $c1_full · 같음 $([ "$head_before" = "$c1_full" ] && echo 예 || echo 아니오)"
    echo "    파일 이름 집합 같음 $([ "$ne" = 0 ] && echo 예 || echo 아니오) · 파일 $total(실패 갈래 $failures) · cmp 다름 $differ"
    report 8 "본문 바이트 같음" "$([ "$te$ne$differ" = 000 ] && [ "$head_before" = "$c1_full" ] && echo 0 || echo 1)"
  fi
fi

# ── 9. 게이트 자기 검사 ──
if want 9; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  last=$(tail -1 "$S4/check-gates.log")
  echo "    $last (종료 $e)"
  case "$last" in GATES=PASS|"GATES=PASS "*) gp=0 ;; *) gp=1 ;; esac
  report 9 "check-gates.sh" "$([ "$e$gp" = 00 ] && echo 0 || echo 1)"
fi

# ── 10. 전량 verify(RR1_FULL=1 일 때만 — .git/verify.lock 을 따른다) ──
if want 10 && [ "$AFTER" = 0 ]; then
  if [ "${RR1_FULL:-0}" = 1 ]; then
    (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/verify.sh) > "$S4/verify.log" 2>&1
    last=$(tail -1 "$S4/verify.log")
    echo "    $last"
    report 10 "verify.sh 전량" "$([ "$last" = "VERIFY=PASS" ] && echo 0 || echo 1)"
  else
    echo "[10] verify.sh 전량 안 돌림(RR1_FULL=1 이 아님 — 러너 규칙. 감독이 돈다)"
  fi
fi

if [ "$AFTER" = 1 ]; then
  porcelain=$(git -C "$ROOT" status --porcelain)
  echo "    git status --porcelain: $(printf '%s' "$porcelain" | grep -c .) 줄"
  printf '%s\n' "$porcelain" | grep . | sed 's/^/    /'
  report after "git status --porcelain 0" "$([ -z "$porcelain" ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
