#!/usr/bin/env bash
# 밴드 GC4 의 §4 자기검증(발주서 band-handoffs/GC4-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-GC4.sh                 전부
#   apps/api-py/scripts/section4-GC4.sh --step 1,2,3    일부(번호는 발주서 §4 의 번호, 8b 는 8b)
#
# 환경 변수:
#   GC4_BASE   기준 커밋(기본: 착수 때 적은 dd7d8e6…)
#   GC4_OUT    산출물 자리(기본: 워크트리 곁의 GC4.out). 산출물은 $GC4_OUT/section4/ 아래
#   GC4_FORBIDDEN_WORDS_FILE  기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt — 이 파일만 연다)
# 컨테이너를 띄우지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). macOS 의 /bin/bash 3.2 에서 돈다.
# 6 은 gen-ts-types.sh 를 다시 돌린다(pnpm dlx openapi-typescript@7.13.0 — 네트워크와 node/pnpm PATH 가 필요하다).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${GC4_BASE:-dd7d8e6b58be8ad85a06f458e55015877fcca4f0}"
OUT="${GC4_OUT:-$SIDE/GC4.out}"
WORDS="${GC4_FORBIDDEN_WORDS_FILE:-$SIDE/G1a.out/forbidden-words.txt}"
S4="$OUT/section4"
E="apps/api-py/esgapi/greenwash"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
mkdir -p "$S4"
api() { (cd "$API_PY" && uv run --frozen "$@"); }

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

ALLOWED='^(apps/api-py/esgapi/greenwash/service/apis/greenwash\.py|apps/api-py/esgapi/greenwash/api\.py|apps/api-py/esgapi/greenwash/flows/review_shapes\.py|apps/api-py/esgapi/greenwash/tests/test_contracts_gc2\.py|apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)|apps/api-py/scripts/(section4|planted-breaks)-GC4\.sh|README\.md)$'

# §1-2 의 0줄 목록(git pathspec). 그린워싱은 고칠 넷만 뺀다.
ZERO=(
  "$E" ":(exclude)$E/service/apis/greenwash.py" ":(exclude)$E/api.py" ":(exclude)$E/flows/review_shapes.py"
  ":(exclude)$E/tests/test_contracts_gc2.py"
  apps/api-py/esgapi/core apps/api-py/esgapi/config apps/api-py/esgapi/user apps/api-py/esgapi/organization
  apps/api-py/esgapi/inventory apps/api-py/esgapi/reference apps/api-py/esgapi/reconcile
  apps/api-py/tests apps/api-py/pyproject.toml apps/api-py/uv.lock apps/api-py/.importlinter
  services apps/web scripts
  apps/api-py/scripts ":(exclude)apps/api-py/scripts/section4-GC4.sh" ":(exclude)apps/api-py/scripts/planted-breaks-GC4.sh"
)

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse HEAD), 산출물 $S4"

if want 1; then
  changed_files > "$S4/changed-files.txt"
  outside=$(grep -Ev "$ALLOWED" "$S4/changed-files.txt")
  n=$(grep -c . "$S4/changed-files.txt")
  echo "    바뀐 파일 $n, 허용 밖 $( [ -n "$outside" ] && echo "$outside" | grep -c . || echo 0)"
  [ -n "$outside" ] && echo "$outside" | sed 's/^/    밖: /'
  report 1 "허용 경로" "$([ -z "$outside" ] && echo 0 || echo 1)"
fi

if want 2; then
  zero=$(git -C "$ROOT" diff "$BASE" --stat -- "${ZERO[@]}" | tail -1)
  untracked=$(git -C "$ROOT" ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)
  deleted=$(git -C "$ROOT" diff --numstat "$BASE" -- "$E/tests/test_contracts_gc2.py" | awk '{s += $2} END {print s + 0}')
  echo "    diff: ${zero:-(없음)} / 새 파일 $untracked / test_contracts_gc2.py 의 지운 줄 $deleted"
  report 2 "0줄 목록(§1-2)" "$([ -z "$zero" ] && [ "$untracked" = 0 ] && [ "$deleted" = 0 ] && echo 0 || echo 1)"
fi

if want 3; then
  : > "$S4/ast.txt"
  bad=0
  for f in "$E/service/apis/greenwash.py" "$E/flows/review_shapes.py" "$E/api.py"; do
    git -C "$ROOT" show "$BASE:$f" > "$S4/ast-base.py"
    r=$(api python - "$S4/ast-base.py" "$ROOT/$f" <<'PY'
import ast
import sys


def strip(path: str) -> str:
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:]
    return ast.dump(tree, include_attributes=False)


print("same" if strip(sys.argv[1]) == strip(sys.argv[2]) else "DIFF")
PY
)
    echo "$f $r" >> "$S4/ast.txt"
    echo "    $f: docstring 뺀 AST $r"
    [ "$r" = "same" ] || bad=$((bad + 1))
  done
  rm -f "$S4/ast-base.py"
  report 3 "동작 0줄(docstring 뺀 AST)" "$([ "$bad" = 0 ] && echo 0 || echo 1)"
fi

if want 4; then
  api python - "$ROOT" > "$S4/legacy.txt" 2>&1 <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
old = ("review_locked", "not_confirmed", "run_not_done", "no_report", "no_review")
bare = re.compile(rf"(?<!legacyCode )(?<!legacyCode `)\b(?:{'|'.join(old)})\b")
readme = (root / "README.md").read_text(encoding="utf-8")
start = readme.index("### 그린워싱 (greenwash)")
end = readme.index("\n### ", start + 1)
texts = {
    "greenwash.py": ((root / "apps/api-py/esgapi/greenwash/service/apis/greenwash.py").read_text(encoding="utf-8"),
                     [c.upper() for c in old]),
    "review_shapes.py": ((root / "apps/api-py/esgapi/greenwash/flows/review_shapes.py").read_text(encoding="utf-8"),
                         ["REVIEW_LOCKED", "RUN_NOT_DONE", "NO_REVIEW"]),
    "README(그린워싱 단락)": (readme[start:end], ["REVIEW_LOCKED"]),
}
fail = 0
for name, (text, upper) in texts.items():
    found = bare.findall(text)
    legacy = len(re.findall(rf"legacyCode `?(?:{'|'.join(old)})\b", text))
    missing = [u for u in upper if f"`{u}`(legacyCode `{u.lower()}`)" not in text]  # 짝을 지어 한 번은
    counts = " ".join(f"{u}={text.count(f'`{u}`')}" for u in upper)
    print(f"    {name}: 맨 옛 글자 {len(found)} {found or ''} · legacyCode 뒤 {legacy} · 대문자 {counts} · 빠짐 {missing or 0}")
    fail += bool(found) or bool(missing)
print(f"RESULT={fail}")
PY
  grep -v '^RESULT=' "$S4/legacy.txt"
  report 4 "옛 글자 셈" "$(grep -q '^RESULT=0$' "$S4/legacy.txt" && echo 0 || echo 1)"
fi

if want 5; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  gates=$(grep '^GATES=' "$S4/check-gates.log" | tail -1)
  echo "    $last / $gates (종료 $e)"
  report 5 "verify.sh --fast · check-gates" "$([ "$last" = "VERIFY_FAST=PASS" ] && [ "$e" = 0 ] && echo 0 || echo 1)"
fi

if want 6; then
  G="apps/api-py/generated"
  before=$(cd "$ROOT" && shasum -a 256 "$G/openapi.json" "$G/api.d.ts" "$G/api.d.ts.source-sha256")
  (cd "$API_PY" && PATH="$NODE_PATH_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen-ts-types.log" 2>&1
  ge=$?
  after=$(cd "$ROOT" && shasum -a 256 "$G/openapi.json" "$G/api.d.ts" "$G/api.d.ts.source-sha256")
  same=$([ "$before" = "$after" ] && echo 0 || echo 1)
  committed=$(git -C "$ROOT" diff --quiet -- "$G" && echo 0 || echo "1(커밋 전이면 1 이 맞다)")
  dts=$(git -C "$ROOT" diff -U0 "$BASE" -- "$G/api.d.ts" | grep -E '^[+-]' | grep -vE '^(\+\+\+|---) ')
  dts_n=$(printf '%s\n' "$dts" | grep -c .)
  dts_code=$(printf '%s\n' "$dts" | grep -vE '^[+-][[:space:]]*(\*|/\*\*)' | grep -c .)
  git -C "$ROOT" show "$BASE:$G/openapi.json" > "$S4/openapi-base.json"
  oj=$(api python - "$S4/openapi-base.json" "$ROOT/$G/openapi.json" <<'PY'
import json
import sys


def strip(node, changed, path=""):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "description" and isinstance(v, str):
                out[k] = "<desc>"
                changed.setdefault(path, v)
            else:
                out[k] = strip(v, changed, f"{path}/{k}")
        return out
    if isinstance(node, list):
        return [strip(v, changed, f"{path}/{i}") for i, v in enumerate(node)]
    return node


a, b = {}, {}
base = strip(json.load(open(sys.argv[1], encoding="utf-8")), a)
now = strip(json.load(open(sys.argv[2], encoding="utf-8")), b)
diff = sorted(p for p in set(a) | set(b) if a.get(p) != b.get(p))
print(("same" if base == now else "DIFF") + f" {len(diff)} " + " ".join(diff))
PY
)
  rm -f "$S4/openapi-base.json"
  echo "    다시 뽑기 종료 $ge · 다시 뽑은 것 = 작업 트리 $([ "$same" = 0 ] && echo 같다 || echo 다르다) · git diff(작업 트리↔색인) $committed"
  echo "    기준 대비 api.d.ts 바뀐 줄 $dts_n, 그중 주석 밖 $dts_code · openapi.json description 뺀 JSON $oj"
  ok=1
  [ "$ge" = 0 ] && [ "$same" = 0 ] && [ "$dts_code" = 0 ] && case "$oj" in same*) ok=0 ;; esac
  report 6 "generated(다시 뽑은 것과 같다, 주석·description 만)" "$ok"
fi

if want 7; then
  rm -f "$S4/netlog.txt"
  (cd "$API_PY" && G1A_NET_LOG="$S4/netlog.txt" uv run --frozen pytest -q -rfE -p no:cacheprovider \
    -p esgapi.greenwash.tests.netcount \
    esgapi/greenwash esgapi/core/tests/test_exceptions.py esgapi/config/tests/test_api_contract.py) > "$S4/pytest.log" 2>&1
  e=$?
  grep -E '^FAILED|^ERROR|passed|failed|error' "$S4/pytest.log" | tail -5 | sed 's/^/    /'
  report 7 "pytest greenwash·test_exceptions·test_api_contract" "$e"
fi

if want 8; then
  (cd "$API_PY" && GC4_OUT="$OUT" scripts/planted-breaks-GC4.sh) > "$S4/planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/planted.log" | sed 's/^/    /'
  report 8 "GC4 심은 파손" "$([ "$e" = 0 ] && grep -q '^PLANTED=5/5$' "$S4/planted.log" && grep -q '^FINGERPRINT=same' "$S4/planted.log" && echo 0 || echo 1)"
fi

if want 8b; then
  # 기준 커밋의 greenwash.py·review_shapes.py 를 잠시 써 넣고 새 시험을 돌린 뒤 원본 바이트로 되쓴다.
  mkdir -p "$S4/base-run"
  git -C "$ROOT" show "$BASE:$E/service/apis/greenwash.py" > "$S4/base-run/greenwash.py"
  git -C "$ROOT" show "$BASE:$E/flows/review_shapes.py" > "$S4/base-run/review_shapes.py"
  (cd "$API_PY" && uv run --frozen python - "$S4/base-run" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

d = Path(sys.argv[1])
G = Path("esgapi/greenwash")
swap = {G / "service/apis/greenwash.py": d / "greenwash.py", G / "flows/review_shapes.py": d / "review_shapes.py"}
start = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in swap}
held = {p: p.read_bytes() for p in swap}
T = "esgapi/greenwash/tests/test_contracts_gc2.py"
tests = [f"{T}::test_openapi_names_the_conflict_codes_in_e2_form",
         f"{T}::test_the_review_shape_header_names_the_conflict_codes_in_e2_form"]
env = {**os.environ, "PYTHONPYCACHEPREFIX": str(d / "pycache")}
try:
    for p, src in swap.items():
        p.write_bytes(src.read_bytes())
    done = subprocess.run(["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", *tests],
                          capture_output=True, text=True, check=False, env=env)
finally:
    for p, raw in held.items():
        p.write_bytes(raw)
text = done.stdout + done.stderr
(d / "pytest.log").write_text(text, encoding="utf-8")
reds = [line for line in text.splitlines() if line.startswith("FAILED")]
hit = [t.split("::")[1] for t in tests if any(t.split("::")[1] in line for line in reds)]
same = all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in start.items())
print(f"    기준 글 위에서 종료 {done.returncode}, 빨간 시험 {len(hit)}/{len(tests)} {hit} · 되쓴 뒤 지문 {'same' if same else 'DIFF'}")
sys.exit(0 if done.returncode != 0 and len(hit) == len(tests) and same else 1)
PY
  )
  report 8b "새 시험이 기준 글 위에서 빨갛다" "$?"
fi

# 이 밴드가 들인 글: 기준 커밋에 있던 파일은 더한 줄만(뿌리 README 에는 앞 밴드의 글이 있다), 새 파일은 전부.
added_text() { # added_text <뿌리 기준 경로>
  if git -C "$ROOT" cat-file -e "$BASE:$1" 2>/dev/null; then
    git -C "$ROOT" diff -U0 "$BASE" -- "$1" | grep '^+' | grep -v '^+++'
  else
    cat "$ROOT/$1"
  fi
}

if want 9; then
  hits=0; keys=0; opens=0
  : > "$S4/forbidden-hits.txt"
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록이 없다: $WORDS"; hits=1
  else
    while IFS= read -r f; do
      [ -f "$ROOT/$f" ] || continue
      if added_text "$f" | grep -F -i -q -f "$WORDS"; then echo "$f" >> "$S4/forbidden-hits.txt"; hits=$((hits + 1)); fi
    done < <(changed_files)
  fi
  mhits=0
  msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
  if [ -n "$msgs" ] && [ -f "$WORDS" ] && printf '%s' "$msgs" | grep -F -i -q -f "$WORDS"; then mhits=1; fi
  while IFS= read -r f; do
    [ -f "$ROOT/$f" ] || continue
    if added_text "$f" | grep -E -q 'sk-[A-Za-z0-9_-]{20,}'; then echo "    키 꼴: $f"; keys=$((keys + 1)); fi
    case "$f" in apps/api-py/scripts/section4-GC4.sh) continue ;; esac  # 찾는 글 자체가 든 이 스크립트
    if added_text "$f" | grep -E -q 'manufac-erp|spike/\.env'; then echo "    키 파일 경로: $f"; opens=$((opens + 1)); fi
  done < <(changed_files)
  if [ ! -f "$S4/netlog.txt" ]; then
    (cd "$API_PY" && G1A_NET_LOG="$S4/netlog.txt" uv run --frozen pytest -q -p no:cacheprovider \
      -p esgapi.greenwash.tests.netcount esgapi/greenwash) > "$S4/pytest-net.log" 2>&1
  fi
  tests=$(wc -l < "$S4/netlog.txt" | tr -d ' ')
  blocked=$(awk '{s += $1} END {print s + 0}' "$S4/netlog.txt")
  nmsg=$(git -C "$ROOT" rev-list --count "$BASE..HEAD")
  echo "    낱말 $( [ -f "$WORDS" ] && grep -c . "$WORDS" || echo 0)개로 본 파일 $(changed_files | wc -l | tr -d ' ')(더한 줄·새 파일): 걸린 파일 $hits, 커밋 메시지($nmsg 개, $BASE..HEAD) $mhits"
  echo "    키 꼴 $keys, 키 파일 경로 $opens, 소켓 문지기가 막은 시도 $blocked (테스트 $tests 개에서)"
  cat "$S4/forbidden-hits.txt"
  report 9 "기업명·키·소켓" "$([ "$hits$mhits$keys$opens$blocked" = 00000 ] && [ "$tests" -gt 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
