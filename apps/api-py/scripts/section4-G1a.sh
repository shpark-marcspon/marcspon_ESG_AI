#!/usr/bin/env bash
# 밴드 G1a 의 §4 자기검증(발주서 band-handoffs/G1a-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-G1a.sh                 전부
#   apps/api-py/scripts/section4-G1a.sh --step 1,19,20  일부(번호는 발주서 §4 의 번호)
#
# 환경 변수:
#   G1A_BASE   기준 커밋(기본: 착수 때 적은 efc5e3b…)
#   G1A_OUT    산출물 자리(기본: 워크트리 곁의 G1a.out). 산출물은 $G1A_OUT/section4/ 아래
#   G1A_PRIVATE_ENV  기업명 낱말 목록·공개 보고서 자리를 적은 파일(기본: $G1A_OUT/private.env, 추적 밖)
#   G1A_LAB    esg-lab 뿌리(기본: 저장소 곁의 esg-lab). 읽기만 하고 `uv run --frozen --group greenwash` 로만 돌린다
#   G1A_HELPERS 대조의 도움 코드 자리(기본: 워크트리 곁의 G1a.out — 추적 밖). gw1-driver/make_golden.py(esg-lab 쪽)·
#              flow-driver/run_flow.py(흐름 쪽). G1A_OUT 을 다른 자리로 돌려도 도움 코드·private.env 는 여기서 찾는다
# 공개 보고서의 dry-run 대조는 여기에 없다($G1A_OUT/public-dryrun.sh).
# macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
BASE="${G1A_BASE:-efc5e3bc0374e783c7403c1971f8865f851cfa15}"
HELPERS="${G1A_HELPERS:-$(cd "$ROOT/.." && pwd)/G1a.out}"
OUT="${G1A_OUT:-$HELPERS}"
PRIVATE_ENV="${G1A_PRIVATE_ENV:-$HELPERS/private.env}"
S4="$OUT/section4"
mkdir -p "$S4"
LAB="${G1A_LAB:-}"
if [ -z "$LAB" ]; then
  for cand in "$ROOT/../esg-lab" "$ROOT/../../esg-lab"; do
    if [ -d "$cand/py/greenwash" ]; then LAB="$(cd "$cand" && pwd)"; break; fi
  done
fi
GW="$LAB/py/greenwash"
for h in "$HELPERS/gw1-driver/make_golden.py" "$HELPERS/flow-driver/run_flow.py"; do
  [ -f "$h" ] || echo "!! 도움 코드가 없다: $h (G1A_HELPERS 로 자리를 준다) — 대조 줄 12·14·16 이 빨개진다"
done
gw1() { (cd "$LAB/py" && PYTHONPATH=. uv run --frozen --group greenwash python "$@"); }
api() { (cd "$API_PY" && uv run --frozen "$@"); }
# pytest 를 돌려 출력을 남기고, 끝 줄과 FAILED 줄을 찍는다. 종료 코드를 돌려준다.
pyt() { # pyt <로그 이름> <pytest 인자…>
  local log="$S4/$1.log"; shift
  api pytest -q -rf -p no:cacheprovider "$@" > "$log" 2>&1
  local e=$?
  grep -E '^FAILED|passed|failed|error' "$log" | tail -5 | sed 's/^/    /'
  return $e
}

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

ALLOWED='^(apps/api-py/esgapi/greenwash/__init__\.py|apps/api-py/esgapi/greenwash/apps\.py|apps/api-py/esgapi/greenwash/calc/.*\.py|apps/api-py/esgapi/greenwash/flows/.*\.py|apps/api-py/esgapi/greenwash/prompts/.*|apps/api-py/esgapi/greenwash/tests/.*|apps/api-py/scripts/section4-G1a\.sh|apps/api-py/scripts/planted-breaks-G1a\.sh|apps/api-py/scripts/g1a_compare\.py|apps/api-py/esgapi/config/apps_list\.py|apps/api-py/esgapi/config/tests/test_settings\.py|apps/api-py/\.importlinter|apps/api-py/esgapi/inventory/tests/test_flows\.py)$'

# ── 가. 바닥 ──
if want 1; then
  changed_files > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(wc -l < "$S4/outside.txt" | tr -d ' ')
  echo "    바뀐 파일 $(wc -l < "$S4/changed.txt" | tr -d ' '), outside $n"
  cat "$S4/outside.txt"
  report 1 "허용 경로" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

if want 2; then
  n=$(git -C "$ROOT" diff "$BASE" -- apps/api-py/pyproject.toml apps/api-py/uv.lock apps/api-py/esgapi/core generated | wc -l | tr -d ' ')
  u=$(git -C "$ROOT" ls-files -o --exclude-standard --full-name -- apps/api-py/esgapi/core generated | wc -l | tr -d ' ')
  echo "    pyproject·uv.lock·core·generated diff 줄 $n, 새 파일 $u"
  report 2 "0줄 파일" "$([ "$n$u" = 00 ] && echo 0 || echo 1)"
fi

if want 3; then
  f=apps/api-py/esgapi/inventory/tests/test_flows.py
  git -C "$ROOT" diff -U0 "$BASE" -- "$f" > "$S4/test_flows.diff"
  minus=$(grep -c '^-[^-]' "$S4/test_flows.diff")
  plus=$(grep -c '^+[^+]' "$S4/test_flows.diff")
  hunks=$(grep '^@@' "$S4/test_flows.diff" | tr '\n' ' ')
  echo "    - $minus 줄, + $plus 줄, 덩이: ${hunks:-없음}"
  ok=1
  if [ "$minus$plus" = 00 ]; then ok=0; echo "    (아직 고치지 않음)"; fi
  nh=$(grep -c '^@@' "$S4/test_flows.diff")
  if [ "$minus$plus" = 11 ] && [ "$nh" = 1 ] && case "$hunks" in "@@ -37 +37 @@"*) true ;; *) false ;; esac; then ok=0; fi
  report 3 "inventory test_flows.py 37줄 한 줄" "$ok"
fi

if want 4; then
  api python -I -c '
import importlib.metadata as m, json
names = ["pypdf", "langchain-text-splitters", "langchain-core", "numpy", "tiktoken", "jsonschema", "openpyxl"]
print(json.dumps({n: m.version(n) for n in names}))' > "$S4/versions-app.json"
  python3 - "$S4/versions-app.json" "$LAB/py/uv.lock" <<'PY' > "$S4/versions.txt"
import json, sys, tomllib
app = json.load(open(sys.argv[1]))
d0 = {"pypdf": "6.20.1", "langchain-text-splitters": "1.1.3", "langchain-core": "1.6.10", "numpy": "2.5.4",
      "tiktoken": "0.14.0", "jsonschema": "4.26.0", "openpyxl": "3.1.5"}
lab = {p["name"]: p["version"] for p in tomllib.load(open(sys.argv[2], "rb"))["package"]}
bad = 0
for n, v in d0.items():
    ok = app.get(n) == v and (lab.get(n) == v or n in ("jsonschema", "openpyxl") and n not in lab)
    bad += not ok
    print(f"    {n}: app {app.get(n)} · D0 {v} · esg-lab {lab.get(n)} {'같음' if ok else 'DIFF'}")
print(f"VERSIONS_DIFF={bad}")
PY
  cat "$S4/versions.txt"
  report 4 "의존성 판(D0 = esg-lab)" "$(grep -q 'VERSIONS_DIFF=0' "$S4/versions.txt" && echo 0 || echo 1)"
fi

if want 5; then
  n=$(api python -c '
import ast, pathlib
root = pathlib.Path("esgapi/greenwash")
hits = []
for p in sorted(root.rglob("*.py")):
    if "tests" in p.parts:
        continue
    for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
        hits += [f"{p}: {x}" for x in names if x.split(".")[0] in ("jsonschema", "rpds")]
print("\n".join(hits)); print(len(hits))' | tail -1)
  echo "    greenwash(calc·flows·apps)의 jsonschema·rpds import: $n"
  report 5 "rpds-py 판 차이가 닿지 않음" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

# ── 나. 빠른 게이트 ──
if want 6; then
  (cd "$ROOT" && PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  e=$?
  tail -1 "$S4/verify-fast.log"
  grep -E '^▶|Contracts:|errors, |passed|failed' "$S4/verify-fast.log" | sed 's/^/    /' | head -60
  report 6 "verify.sh --fast" "$([ "$e" = 0 ] && tail -1 "$S4/verify-fast.log" | grep -q 'VERIFY_FAST=PASS' && echo 0 || echo 1)"
fi

if want 7; then
  api lint-imports > "$S4/lint-imports.log" 2>&1
  e=$?
  kept=$(grep -E 'Contracts: [0-9]+ kept, 0 broken' "$S4/lint-imports.log")
  base_n=$(git -C "$ROOT" show "$BASE:apps/api-py/.importlinter" | grep -c '^\[importlinter:contract')
  now_n=$(grep -c '^\[importlinter:contract' "$API_PY/.importlinter")
  pure=$(awk '/^\[importlinter:contract:pure-modules\]/{f=1} f&&/^forbidden_modules/{f=0} f' "$API_PY/.importlinter" | grep -c '^    esgapi.greenwash.flows$')
  echo "    $kept · 계약 수 기준 $base_n / 지금 $now_n · 「다」의 esgapi.greenwash.flows $pure"
  report 7 "lint-imports" "$([ "$e" = 0 ] && [ -n "$kept" ] && [ "$base_n" = "$now_n" ] && [ "$pure" = 1 ] && echo 0 || echo 1)"
fi

if want 8; then
  (cd "$API_PY" && scripts/check-wheel.sh) > "$S4/check-wheel.log" 2>&1
  e=$?
  cat "$S4/check-wheel.log" | sed 's/^/    /'
  rm -rf "$S4/wheel"
  (cd "$API_PY" && uv build --wheel -o "$S4/wheel" >/dev/null 2>&1)
  n=$(unzip -Z1 "$S4"/wheel/*.whl | grep -cE '^esgapi/greenwash/prompts/(detect|eval|repair|low-only)/1\.md$')
  echo "    wheel 안의 그린워싱 프롬프트 $n / 4"
  report 8 "wheel" "$([ "$e" = 0 ] && [ "$n" = 4 ] && echo 0 || echo 1)"
fi

# ── 다. Django (컨테이너 없이) ──
if want 9; then
  out=$(cd "$API_PY" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python -c "import django; django.setup(); from esgapi.core.flows.registry import REGISTRY; print(REGISTRY.default_of('greenwash').id)" 2>&1 | tail -1)
  echo "    $out"
  report 9 "django.setup 뒤 기본 흐름" "$([ "$out" = "greenwash.colab@E0" ] && echo 0 || echo 1)"
fi

if want 10; then
  out=$(cd "$API_PY" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py makemigrations --check --dry-run 2>&1 | tail -1)
  echo "    $out"
  report 10 "makemigrations --check" "$([ "$out" = "No changes detected" ] && echo 0 || echo 1)"
fi

# ── 라. 대조 ──
if want 11; then
  api python -W ignore scripts/g1a_compare.py ast "$GW" > "$S4/ast.txt" 2>&1
  e=$?
  sed 's/^/    /' "$S4/ast.txt"
  report 11 "AST 대조(calc 열 파일 ↔ GW1)" "$e"
fi

if want 12; then
  pyt contrast-a esgapi/greenwash/tests/flows/test_colab.py esgapi/greenwash/tests/flows/test_adapters.py -k "contrast_a or no_pages or l1_embedding"
  e1=$?
  if [ "$e1" = 0 ]; then
    echo "    pytest 판: GW1 골든(tests/data/golden/sample-mock.json, sample-none.json)과 같음 — 메시지 해시 12개"
  else
    echo "    pytest 판: 빨강(로그 $S4/contrast-a.log)"
  fi
  # 텍스트 판(OUT): GW1 을 지금 다시 돌려 견준다
  for m in mock-text mock-text-none; do
    gw1 "$HELPERS/gw1-driver/make_golden.py" "$m" "$S4/gw1-$m.json" > "$S4/run-gw1-$m.log" 2>&1 || { e1=1; echo "    $m: GW1 도움 코드 실패(로그 $S4/run-gw1-$m.log)"; }
    api python "$HELPERS/flow-driver/run_flow.py" "$m" "$S4/flow-$m.json" > "$S4/run-flow-$m.log" 2>&1 || { e1=1; echo "    $m: 흐름 도움 코드 실패(로그 $S4/run-flow-$m.log)"; }
    api python scripts/g1a_compare.py mock "$S4/gw1-$m.json" "$S4/flow-$m.json" > "$S4/cmp-$m.txt" 2>&1 || e1=1
    echo "    $m: $(tail -1 "$S4/cmp-$m.txt")"
  done
  # PDF 판(OUT): 표본 PDF 를 esg-lab 쪽에서 짓고, GW1(도움 코드와 CLI)과 흐름(PypdfText)이 같은 PDF 를 읽는다
  gw1 greenwash/tests/build_sample.py "$S4/sample.pdf" >/dev/null 2>&1 || e1=1
  gw1 "$HELPERS/gw1-driver/make_golden.py" mock-pdf "$S4/gw1-mock-pdf.json" "$S4/sample.pdf" >/dev/null 2>&1 || e1=1
  gw1 -m greenwash scan "$S4/sample.pdf" --provider mock --ceo 1 --company 2 --climate 3~4 --out "$S4/gw1-cli-pdf" >/dev/null 2>&1 || e1=1
  api python "$HELPERS/flow-driver/run_flow.py" mock-pdf "$S4/flow-mock-pdf.json" "$S4/sample.pdf" >/dev/null 2>&1 || e1=1
  api python scripts/g1a_compare.py mock "$S4/gw1-mock-pdf.json" "$S4/flow-mock-pdf.json" > "$S4/cmp-mock-pdf.txt" 2>&1 || e1=1
  api python scripts/g1a_compare.py mock "$S4/gw1-cli-pdf/greenwash-result.json" "$S4/flow-mock-pdf.json" > "$S4/cmp-cli-pdf.txt" 2>&1 || e1=1
  echo "    PDF 판(도움 코드): $(tail -1 "$S4/cmp-mock-pdf.txt") · PDF 판(GW1 CLI, 메시지 열은 CLI 에 없음): $(tail -1 "$S4/cmp-cli-pdf.txt")"
  echo "    메시지 해시 열 길이: $(python3 -c "import json; print(len(json.load(open('$S4/flow-mock-pdf.json'))['messages']))") · 빈 조각: $(python3 -c "import json; print(json.load(open('$S4/flow-mock-pdf.json'))['empty_chunks'])")"
  report 12 "대조 A(pytest 판·텍스트 판·PDF 판)" "$e1"
fi

if want 13; then
  pyt contrast-b esgapi/greenwash/tests/flows/test_adapters.py -k "contrast_b or rendering or four_kinds or refuses"
  report 13 "대조 B(core.llm 을 지나서)" "$?"
fi

if want 14; then
  pyt contrast-c esgapi/greenwash/tests/flows/test_colab.py -k "dry_run"
  e=$?
  gw1 "$HELPERS/gw1-driver/make_golden.py" dry-text "$S4/gw1-dry-text.json" >/dev/null 2>&1 || e=1
  api python "$HELPERS/flow-driver/run_flow.py" dry-text "$S4/flow-dry-text.json" >/dev/null 2>&1 || e=1
  api python scripts/g1a_compare.py dryrun "$S4/gw1-dry-text.json" "$S4/flow-dry-text.json" > "$S4/cmp-dry-text.txt" 2>&1 || e=1
  echo "    텍스트 판(지금 다시 돌린 GW1): $(tail -1 "$S4/cmp-dry-text.txt") — 공개 보고서 판은 \$G1A_OUT/public-dryrun.sh"
  report 14 "대조 C(pytest 판)" "$e"
fi

if want 15; then
  pyt contrast-d esgapi/greenwash/tests/flows/test_colab.py -k "contrast_d or progress"
  report 15 "대조 D(이어 돌기)" "$?"
fi

if want 16; then
  gw1 "$HELPERS/gw1-driver/make_golden.py" consts "$S4/gw1-consts.json" >/dev/null 2>&1
  api python - "$S4/gw1-consts.json" > "$S4/consts.txt" 2>&1 <<'PY'
import json, sys
from esgapi.greenwash.calc.ports import EMBEDDING_MODEL
from esgapi.greenwash.calc.prompts import PROMPT_VERSION
from esgapi.greenwash.flows import adapters, colab, result
c = json.load(open(sys.argv[1]))
pairs = [
    ("SCAN_CONFIG", colab.SCAN_CONFIG, c["SCAN_CONFIG"]),
    ("chunk_defaults", result.chunk_defaults(), c["chunk_defaults"]),
    ("CHUNK_ARGS", colab.CHUNK_ARGS, {k: v for k, v in c["chunk_defaults"].items() if k != "separators"}),
    ("MODEL_NAME", colab.MODEL_NAME, c["MODEL_NAME"]),
    ("TEMPERATURE", colab.TEMPERATURE, c["TEMPERATURE"]),
    ("MAX_TOKENS", colab.MAX_TOKENS, c["MAX_TOKENS"]),
    ("MAX_OUTPUT_TOKENS(다리)", adapters.MAX_OUTPUT_TOKENS, c["MAX_TOKENS"]),
    ("PROMPT_VERSION", PROMPT_VERSION, c["PROMPT_VERSION"]),
    ("EMBEDDING_MODEL", EMBEDDING_MODEL, c["EMBEDDING_MODEL"]),
    ("SCAN_CONFIG 에 env 키 없음", "env_keywords_extra" in colab.SCAN_CONFIG or "include_general_env" in colab.SCAN_CONFIG, False),
]
bad = [n for n, a, b in pairs if a != b]
for n, a, b in pairs:
    print(f"    {n}: {'같음' if a == b else f'DIFF 흐름={a!r} GW1={b!r}'}")
print(f"CONSTS_DIFF={len(bad)}/{len(pairs)}")
PY
  cat "$S4/consts.txt"
  report 16 "상수 = GW1" "$(grep -q '^CONSTS_DIFF=0/' "$S4/consts.txt" && echo 0 || echo 1)"
fi

# ── 마. 테스트와 파손 ──
if want 17; then
  rm -f "$S4/netlog.txt"
  G1A_NET_LOG="$S4/netlog.txt" pyt pytest-greenwash -p esgapi.greenwash.tests.netcount esgapi/greenwash
  e1=$?
  pyt pytest-inventory-flows esgapi/inventory/tests/test_flows.py
  e2=$?
  report 17 "pytest greenwash·inventory test_flows" "$([ "$e1$e2" = 00 ] && echo 0 || echo 1)"
fi

if want 18; then
  (cd "$API_PY" && scripts/planted-breaks-G1a.sh) > "$S4/planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/planted.log" | sed 's/^/    /'
  report 18 "심은 파손" "$e"
fi

# ── 바. 경계 ──
if want 19; then
  if [ ! -f "$PRIVATE_ENV" ]; then
    echo "    $PRIVATE_ENV 가 없다"
    report 19 "기업명·공개 보고서 경로" 1
  else
    # shellcheck disable=SC1090
    . "$PRIVATE_ENV"
    words="${G1A_FORBIDDEN_WORDS_FILE:?}"
    reports="${G1A_REPORTS_DIR:?}"
    hits=0
    : > "$S4/forbidden-hits.txt"
    while IFS= read -r f; do
      [ -f "$ROOT/$f" ] || continue
      if grep -F -i -q -f "$words" "$ROOT/$f" || grep -F -q "$reports" "$ROOT/$f"; then
        echo "$f" >> "$S4/forbidden-hits.txt"; hits=$((hits + 1))
      fi
    done < <(changed_files)
    msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
    mhits=0
    if [ -n "$msgs" ]; then
      if printf '%s' "$msgs" | grep -F -i -q -f "$words" || printf '%s' "$msgs" | grep -F -q "$reports"; then mhits=1; fi
    fi
    ext=$(changed_files | grep -Ec '\.(pdf|ipynb|xlsx)$')
    echo "    낱말 $(grep -c . "$words")개로 본 파일 $(changed_files | wc -l | tr -d ' '): 걸린 파일 $hits, 커밋 메시지 $mhits, .pdf·.ipynb·.xlsx $ext"
    cat "$S4/forbidden-hits.txt"
    report 19 "기업명·공개 보고서 경로" "$([ "$hits$mhits$ext" = 000 ] && echo 0 || echo 1)"
  fi
fi

if want 20; then
  keys=0
  opens=0
  while IFS= read -r f; do
    [ -f "$ROOT/$f" ] || continue
    if grep -E -q 'sk-[A-Za-z0-9_-]{20,}' "$ROOT/$f"; then echo "    키 꼴: $f"; keys=$((keys + 1)); fi
    case "$f" in apps/api-py/scripts/section4-G1a.sh) continue ;; esac
    if grep -E -q 'manufac-erp|spike/\.env' "$ROOT/$f"; then echo "    키 파일 경로: $f"; opens=$((opens + 1)); fi
  done < <(changed_files)
  if [ ! -f "$S4/netlog.txt" ]; then
    G1A_NET_LOG="$S4/netlog.txt" api pytest -q -p no:cacheprovider -p esgapi.greenwash.tests.netcount esgapi/greenwash > "$S4/pytest-net.log" 2>&1
  fi
  tests=$(wc -l < "$S4/netlog.txt" | tr -d ' ')
  blocked=$(awk '{s += $1} END {print s + 0}' "$S4/netlog.txt")
  echo "    키 꼴 $keys, 키 파일 경로 $opens, 소켓 문지기가 막은 시도 $blocked (테스트 $tests 개에서)"
  report 20 "키·소켓" "$([ "$keys$opens$blocked" = 000 ] && [ "$tests" -gt 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
