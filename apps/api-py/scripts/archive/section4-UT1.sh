#!/usr/bin/env bash
# 밴드 UT1 의 §4 자기검증(발주서 band-handoffs/UT1-order.md §4 — Scope 3 결과를 tCO2eq 로, 계수는 kg 그대로).
# 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-UT1.sh                  전부(10 은 UT1_FULL=1 일 때만)
#   apps/api-py/scripts/section4-UT1.sh --step 1,3       일부(번호는 발주서 §4 의 번호)
#   apps/api-py/scripts/section4-UT1.sh --after-commit   1~9 + git status --porcelain 0
#
# 환경 변수:
#   UT1_BASE   기준 커밋(기본: 워크트리를 만들 때의 main 11a9ecc)
#   UT1_OUT    산출물 자리(기본: 워크트리 곁의 UT1.out). 산출물은 $UT1_OUT/section4/ 아래
#   UT1_FULL   1 이면 10(전량 scripts/verify.sh)을 돈다. 러너는 돌리지 않는다(감독·테스트 감독이 돈다) — 그때는
#              「안 돌림」 줄만 찍고 실패로 세지 않는다.
# 컨테이너는 쓰지 않는다(이 밴드는 순수 층뿐). generated/ 를 제자리에 다시 쓰지 않는다(gen-ts-types.sh 를 돌리지 않는다).
# 6 의 api.d.ts 는 pnpm dlx openapi-typescript@7.13.0 — 네트워크와 node/pnpm PATH 가 필요하다(못 지으면 그 줄만 적는다).
# 이 파일과 planted-breaks-UT1.sh 는 옛 이름의 글자를 담으므로 4 의 grep 에서 뺀다.
# 실제 LLM 호출 0, API 키를 읽지 않는다. macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${UT1_BASE:-11a9ecc}"
OUT="${UT1_OUT:-$SIDE/UT1.out}"
S4="$OUT/section4"
mkdir -p "$S4"
NODE_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
A="apps/api-py"
E="$A/esgapi"
I="$E/inventory"
OLD_A="emissions""KgCo2e"
OLD_B="emissions""_kg_co2e"
OLD_C="Emissions""kgco2E"

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

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse --short HEAD), 산출물 $S4"

# ── 1. 빠른 게이트 ──
if want 1; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  echo "    $last"
  report 1 "verify.sh --fast" "$([ "$last" = "VERIFY_FAST=PASS" ] && echo 0 || echo 1)"
fi

# ── 2. inventory 순수 층 시험(Scope 3·결과 꼴·흐름·골든 G1). DB 를 쓰는 test_scope3_api 는 업무 층이라 -m 으로 뺀다 ──
if want 2; then
  (cd "$API_PY" && PYTHONPYCACHEPREFIX="$S4/pycache" uv run --frozen pytest -q -p no:cacheprovider \
    -m "not django_db and not security" \
    esgapi/inventory/tests/test_scope3_*.py esgapi/inventory/tests/test_flow_shapes.py \
    esgapi/inventory/tests/test_flows.py esgapi/inventory/tests/calc/scope3) > "$S4/inventory-tests.log" 2>&1
  e=$?
  golden=$(git -C "$ROOT" diff --name-only "$BASE" -- "$I/tests/data/scope3/golden" "$I/tests/make-golden.sh" | grep -c .)
  echo "    $(tail -1 "$S4/inventory-tests.log") (종료 $e) · 골든 G1 diff $golden"
  report 2 "inventory 순수 층 시험·골든 G1 손대지 않음" "$([ "$e$golden" = 00 ] && echo 0 || echo 1)"
fi

# ── 3. 심은 파손 여덟: 빨강, 되돌린 뒤 지문 같음 ──
if want 3; then
  (cd "$ROOT" && "$A/scripts/planted-breaks-UT1.sh") > "$S4/planted.log" 2>&1
  e=$?
  cat "$S4/planted.log"
  last=$(tail -1 "$S4/planted.log")
  report 3 "심은 파손 PLANTED=8/8·지문 같음" "$([ "$e" = 0 ] && [ "$last" = "PLANTED=8/8" ] && echo 0 || echo 1)"
fi

# ── 4. 옛 이름 0, 남을 것(㉯) 그대로 ──
# ㉯ 만 담은 파일(기준에서 kg 이름 줄이 있고 ㉮ 줄이 없는 apps/api-py 의 파일) — 기준과 diff 0
KEEP_ONLY="
$A/esgapi/inventory/calc/scope3_sheets/factor_layout.py
$A/esgapi/inventory/data/factors.kr-ets-sample.json
$A/esgapi/inventory/tests/data/golden
$A/esgapi/inventory/tests/data/handcalc-assembly.json
$A/esgapi/inventory/tests/data/handcalc-cases.json
$A/esgapi/inventory/tests/s3sheets_support.py
$A/esgapi/inventory/tests/test_calc.py
$A/esgapi/inventory/tests/test_s3sheets_factors.py
$A/esgapi/inventory/tests/test_s3sheets_samples.py
$A/esgapi/reference
apps/web
README.md
"
MIXED="$I/calc/scope3/calc.py $I/tests/test_flow_shapes.py"
if want 4; then
  git -C "$ROOT" grep -n -e "$OLD_A" -e "$OLD_B" -e "$OLD_C" -- . ':!apps/web' \
    ":!$A/scripts/section4-UT1.sh" ":!$A/scripts/planted-breaks-UT1.sh" > "$S4/old-names.txt"
  old=$(grep -c . "$S4/old-names.txt")
  # shellcheck disable=SC2086  # 경로 목록을 낱말로 나눈다
  git -C "$ROOT" diff --stat "$BASE" -- $KEEP_ONLY > "$S4/keep-only.diff"
  keep=$(grep -c . "$S4/keep-only.diff")
  # 섞인 두 파일: 기준의 kg 이름 줄에서 ㉮ 줄을 뺀 것이 지금 줄 글자 목록에 모두 있다
  : > "$S4/mixed-missing.txt"; : > "$S4/mixed-new.txt"
  for f in $MIXED; do
    git -C "$ROOT" grep -h -i -e kgco2 -e kg_co2 -e KgCo2 "$BASE" -- "$f" \
      | grep -v -e "$OLD_A" -e "$OLD_B" -e "$OLD_C" | sort -u > "$S4/mixed-base.txt"
    git -C "$ROOT" grep -h -i -e kgco2 -e kg_co2 -e KgCo2 -- "$f" | sort -u > "$S4/mixed-now.txt"
    comm -23 "$S4/mixed-base.txt" "$S4/mixed-now.txt" | sed "s|^|$f: |" >> "$S4/mixed-missing.txt"
    comm -13 "$S4/mixed-base.txt" "$S4/mixed-now.txt" | sed "s|^|$f: |" >> "$S4/mixed-new.txt"
  done
  missing=$(grep -c . "$S4/mixed-missing.txt")
  before=$(git -C "$ROOT" grep -n -i -e kgco2 -e kg_co2 -e KgCo2 "$BASE" | grep -c .)
  after=$(git -C "$ROOT" grep -n -i -e kgco2 -e kg_co2 -e KgCo2 -- . \
    ":!$A/scripts/section4-UT1.sh" ":!$A/scripts/planted-breaks-UT1.sh" | grep -c .)
  web=$(git -C "$ROOT" grep -n -i -e kgco2 -e kg_co2 -e KgCo2 -- apps/web | grep -c .)
  readme=$(git -C "$ROOT" grep -n -i -e kgco2 -e kg_co2 -e KgCo2 -- README.md | grep -c .)
  echo "    옛 이름 $old · ㉯ 파일 diff $keep 줄 · 섞인 파일의 ㉯ 빠짐 $missing · 새로 는 줄 $(grep -c . "$S4/mixed-new.txt")"
  echo "    kg 이름 줄 전 $before → 뒤 $after(두 스크립트 뺌) · apps/web $web · README $readme"
  sed 's/^/    옛 이름: /' "$S4/old-names.txt"
  sed 's/^/    ㉯ diff: /' "$S4/keep-only.diff"
  sed 's/^/    ㉯ 빠짐: /' "$S4/mixed-missing.txt"
  sed 's/^/    새 줄: /' "$S4/mixed-new.txt"
  report 4 "옛 이름 0·㉯ 그대로" "$([ "$old$keep$missing" = 000 ] && echo 0 || echo 1)"
fi

# ── 5. 나누는 자리 하나: 호출 수, 더한 코드 줄(주석·docstring 제외)의 금지 글자 ──
if want 5; then
  git -C "$ROOT" diff -U0 "$BASE" -- "$E" ":(exclude,glob)$E/**/tests/**" > "$S4/product.diff"
  (cd "$ROOT" && python3 -I - "$S4/product.diff" "$I/calc/scope3/calc.py" "$I/calc/scope3/serialize.py" \
    "$I/flows/scope3.py" <<'PY'
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

diff_path, calc_py, serialize_py, scope3_py = sys.argv[1:5]


def added_lines(diff: str) -> dict[str, set[int]]:
    """diff -U0 에서 파일마다 더한 줄 번호."""
    out: dict[str, set[int]] = {}
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
            if current is not None:
                out.setdefault(current, set())
        elif line.startswith("@@") and current is not None:
            m = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", line)
            assert m, line
            start, count = int(m.group(1)), int(m.group(2) or "1")
            out[current].update(range(start, start + count))
    return out


def code_text(path: str) -> dict[int, str]:
    """줄 번호 → 주석·docstring 을 뺀 코드 글자(파이썬 파일만)."""
    source = Path(path).read_text(encoding="utf-8")
    doc_lines: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            doc_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    lines: dict[int, list[str]] = {}
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            continue
        for n in range(tok.start[0], tok.end[0] + 1):
            if n not in doc_lines:
                lines.setdefault(n, []).append(tok.string)
    return {n: " ".join(parts) for n, parts in lines.items()}


added = added_lines(Path(diff_path).read_text(encoding="utf-8"))
fail = 0

tree = ast.parse(Path(calc_py).read_text(encoding="utf-8"))
calls = [
    node.lineno
    for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "conversion_factor"
    and [a.value for a in node.args if isinstance(a, ast.Constant)] == ["kg", "tonne"]
]
print(f"    calc.py 의 conversion_factor(\"kg\", \"tonne\") 호출 {len(calls)}개(줄 {calls})")
fail += len(calls) != 2

FORBIDDEN = re.compile(r"0\.001|1000|Decimal\(|round|/")
for path, numbers in sorted(added.items()):
    if not path.endswith(".py"):
        print(f"    더한 줄(파이썬 아님, 건너뜀): {path}")
        continue
    code = code_text(path)
    hits = [(n, code[n]) for n in sorted(numbers) if n in code and FORBIDDEN.search(code[n])]
    print(f"    {path}: 더한 줄 {len(numbers)}, 그 코드 줄의 0.001·1000·Decimal(·round·/ 걸림 {len(hits)}")
    for n, text in hits:
        print(f"      {n}: {text}")
    fail += len(hits)

for path in (serialize_py, scope3_py):
    code = code_text(path)
    hits = [(n, code[n]) for n in sorted(added.get(path, set())) if n in code and re.search(r"\bmul\b|0\.001", code[n])]
    print(f"    {path}: 더한 코드 줄의 mul·0.001 걸림 {len(hits)}")
    for n, text in hits:
        print(f"      {n}: {text}")
    fail += len(hits)
sys.exit(1 if fail else 0)
PY
  ) > "$S4/one-place.log" 2>&1
  e=$?
  cat "$S4/one-place.log"
  report 5 "나누는 자리 하나(호출 2·금지 글자 0)" "$e"
fi

# ── 6. generated 같음(제자리에 다시 쓰지 않는다) ──
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
  git -C "$ROOT" diff --quiet "$BASE" -- "$G"; bd=$?
  echo "    export 종료 $xe · openapi cmp $oc · sha256 같음 $([ "$sc" = 0 ] && echo 예 || echo 아니오) · $dts · 작업 트리 diff $wd · 기준 대비 diff $bd"
  report 6 "generated 같음" "$([ "$xe$oc$sc$dc$wd$bd" = 000000 ] && echo 0 || echo 1)"
fi

# ── 7. 합산 자리 확인 줄(확3) ──
if want 7; then
  {
    echo "aggregate.py 의 scope3 글자:"
    git -C "$ROOT" grep -n scope3 -- "$I/calc/aggregate.py"
    echo "Scope 3 calc 를 들이는 제품 모듈(시험 밖):"
    git -C "$ROOT" grep -l -e 'calc.scope3.calc' -e 'calc\.scope3 import' -- "$E" ":(exclude,glob)$E/**/tests/**"
    echo "calculate_row·Computed 를 쓰는 제품 모듈(시험 밖):"
    git -C "$ROOT" grep -l -E 'calculate_row|Computed\b' -- "$E" ":(exclude,glob)$E/**/tests/**"
  } > "$S4/sum-site.txt"
  sed 's/^/    /' "$S4/sum-site.txt"
  agg=$(git -C "$ROOT" grep -n scope3 -- "$I/calc/aggregate.py" | grep -c .)
  # 두 결과(Scope 1·2 의 RowOk/Totals 와 Scope 3 의 Computed)를 같이 들이는 제품 모듈 — 꼴 정의(shapes.py)는 합산이 아니다
  both=$(git -C "$ROOT" grep -l -E 'Computed\b' -- "$E" ":(exclude,glob)$E/**/tests/**" \
    | xargs grep -l -E '\bRowOk\b|\bTotals\b' 2>/dev/null | grep -c .)
  echo "    aggregate.py 의 scope3 $agg · Computed 와 RowOk/Totals 를 같이 쓰는 제품 모듈 $both(분모: esgapi 의 시험 밖 .py)"
  report 7 "합산 자리 없음" "$([ "$agg$both" = 00 ] && echo 0 || echo 1)"
fi

# ── 8. 허용 경로 밖 diff 0, 0줄 목록 0 ──
ALLOWED="^($I/calc/scope3/(calc|serialize)\.py|$I/flows/(shapes|scope3)\.py|$I/tests/data/flow-shapes/scope3\.llm-first\.result@[12]\.schema\.json|$I/tests/test_(scope3_calc|scope3_pipeline|flow_shapes|flows|scope3_tonnes)\.py|$A/scripts/(section4|planted-breaks)-UT1\.sh)$"
ZERO="apps/web $A/generated $I/calc/scope3/units.py $I/calc/scope3/catalog.py $I/calc/scope3/types.py
$I/calc/scope3_sheets $E/reference $I/calc/calc.py $I/calc/types.py $I/calc/serialize.py $I/calc/aggregate.py
$I/tests/data/flow-shapes/scope12.result@1.schema.json $I/tests/data/scope3/golden $E/core/calc/decimal.py
$E/core/tests/test_flows_registry.py $E/greenwash
compose.yaml docker scripts/verify.sh scripts/check-gates.sh scripts/git-hooks .importlinter $A/.importlinter
.env.example .dockerignore $A/scripts/check-build-context.sh $A/pyproject.toml $A/uv.lock pnpm-lock.yaml
README.md infra packages"
if want 8; then
  { git -C "$ROOT" diff --name-only --no-renames "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } \
    | sort -u > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(grep -c . "$S4/outside.txt")
  # shellcheck disable=SC2086  # 경로 목록을 낱말로 나눈다
  zero=$(git -C "$ROOT" diff --name-only "$BASE" -- $ZERO | grep -c .)
  # shellcheck disable=SC2086
  zero_new=$(git -C "$ROOT" ls-files -o --exclude-standard -- $ZERO | grep -c .)
  pre=$(grep -c '^\.pre-commit' "$S4/changed.txt")
  echo "    바뀐 파일 $(grep -c . "$S4/changed.txt"), 허용 밖 $n, 0줄 목록 $zero(+새 파일 $zero_new), .pre-commit* $pre"
  sed 's/^/    바뀜: /' "$S4/changed.txt"
  sed 's/^/    밖: /' "$S4/outside.txt"
  report 8 "허용 밖 0·0줄 목록 0" "$([ "$n$zero$zero_new$pre" = 0000 ] && echo 0 || echo 1)"
fi

# ── 9. 게이트 자기 검사 ──
if want 9; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  last=$(tail -1 "$S4/check-gates.log")
  echo "    $last (종료 $e)"
  case "$last" in GATES=PASS|"GATES=PASS "*) gp=0 ;; *) gp=1 ;; esac  # 끝 줄은 「GATES=PASS 55/55」 꼴
  report 9 "check-gates.sh" "$([ "$e$gp" = 00 ] && echo 0 || echo 1)"
fi

# ── 10. 전량 verify(UT1_FULL=1 일 때만 — .git/verify.lock 을 따른다) ──
if want 10 && [ "$AFTER" = 0 ]; then
  if [ "${UT1_FULL:-0}" = 1 ]; then
    (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/verify.sh) > "$S4/verify.log" 2>&1
    last=$(tail -1 "$S4/verify.log")
    echo "    $last"
    report 10 "verify.sh 전량" "$([ "$last" = "VERIFY=PASS" ] && echo 0 || echo 1)"
  else
    echo "[10] verify.sh 전량 안 돌림(UT1_FULL=1 이 아님 — 러너 규칙. 감독·테스트 감독이 돈다)"
  fi
fi

if [ "$AFTER" = 1 ]; then
  porcelain=$(git -C "$ROOT" status --porcelain)
  echo "    git status --porcelain: $(printf '%s' "$porcelain" | grep -c .) 줄"
  printf '%s\n' "$porcelain" | grep . | sed 's/^/    /'
  report after "git status --porcelain 0" "$([ -z "$porcelain" ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
