#!/usr/bin/env bash
# 밴드 GC3 의 §4 자기검증(발주서 band-handoffs/GC3-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-GC3.sh                 전부
#   apps/api-py/scripts/section4-GC3.sh --step 1,3,6    일부(번호는 발주서 §4 의 번호)
#
# 환경 변수:
#   GC3_BASE   기준 커밋(기본: 착수 때 적은 b10dc74…)
#   GC3_OUT    산출물 자리(기본: 워크트리 곁의 GC3.out). 산출물은 $GC3_OUT/section4/ 아래
#   GC3_FORBIDDEN_WORDS_FILE  기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt — 이 파일만 연다)
# 컨테이너를 띄우지 않는다. 전량 scripts/verify.sh 와 apps/web/scripts/verify.sh 는 돌리지 않는다(--fast 만).
# 4 의 TS 두 줄(pnpm -r typecheck·test)은 빨개도 된다 — 빨간 파일이 전부 apps/web/src/greenwash/ 아래면(선결 6).
# 6 은 generated 를 제자리에서 다시 뽑는다(gen-ts-types.sh — openapi-typescript 를 pnpm dlx 로 받는다).
# macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${GC3_BASE:-b10dc74f35c80a96779543c42095897c33ebf7fc}"
OUT="${GC3_OUT:-$SIDE/GC3.out}"
WORDS="${GC3_FORBIDDEN_WORDS_FILE:-$SIDE/G1a.out/forbidden-words.txt}"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
S4="$OUT/section4"
mkdir -p "$S4"
api() { (cd "$API_PY" && uv run --frozen "$@"); }
pyt() { # pyt <로그 이름> <pytest 인자…>
  local log="$S4/$1.log"; shift
  api pytest -q -rfE -p no:cacheprovider "$@" > "$log" 2>&1
  local e=$?
  grep -E '^FAILED|^ERROR|passed|failed|error' "$log" | tail -5 | sed 's/^/    /'
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

G='apps/api-py/esgapi/greenwash'
ALLOWED="^($G/flows/(shapes|review_shapes|compare_shapes|terms_shapes)\\.py|$G/flows/wire\\.py|$G/flows/colab\\.py|$G/flows/(xlsx|compare)\\.py|$G/service/apis/greenwash\\.py|$G/tests/.*\\.py|$G/tests/data/flow-shapes/.*|$G/tests/data/contract-examples/.*|apps/api-py/generated/(openapi\\.json|api\\.d\\.ts|api\\.d\\.ts\\.source-sha256)|apps/api-py/scripts/g1a_compare\\.py|apps/api-py/scripts/planted-breaks-GR1\\.sh|apps/api-py/scripts/(section4|planted-breaks)-GC3\\.sh|README\\.md)\$"

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse HEAD), 산출물 $S4"

if want 1; then
  changed_files > "$S4/changed-files.txt"
  outside=$(grep -Ev "$ALLOWED" "$S4/changed-files.txt")
  n=$(grep -c . "$S4/changed-files.txt")
  echo "    바뀐 파일 $n, 허용 밖 $( [ -n "$outside" ] && echo "$outside" | grep -c . || echo 0)"
  sed 's/^/    · /' "$S4/changed-files.txt"
  [ -n "$outside" ] && echo "$outside" | sed 's/^/    밖: /'
  report 1 "허용 경로" "$([ -z "$outside" ] && echo 0 || echo 1)"
fi

if want 2; then
  ZERO="$G/calc $G/tests/data/golden $G/tests/data/gw1-ast-sha256.txt $G/api.py $G/apps.py $G/prompts"
  for f in result adapters gw1 pdfium_locate textnorm registration; do ZERO="$ZERO $G/flows/$f.py"; done
  for m in core config user organization inventory reference reconcile; do ZERO="$ZERO apps/api-py/esgapi/$m"; done
  ZERO="$ZERO apps/web apps/api-py/tests apps/api-py/pyproject.toml apps/api-py/uv.lock apps/api-py/.importlinter services"
  for s in planted-breaks-G1a planted-breaks-G1d planted-breaks-GL1 section4-G1a section4-GR1 section4-GL1; do
    ZERO="$ZERO apps/api-py/scripts/$s.sh"
  done
  ZERO="$ZERO apps/api-py/scripts/archive scripts"
  echo "$ZERO" | tr ' ' '\n' | grep . > "$S4/zero-paths.txt"
  # shellcheck disable=SC2086
  zero=$(cd "$ROOT" && git diff "$BASE" --stat -- $ZERO | tail -1)
  # shellcheck disable=SC2086
  untracked=$(cd "$ROOT" && git ls-files -o --exclude-standard -- $ZERO | grep -c .)
  echo "    0줄 자리 $(grep -c . "$S4/zero-paths.txt")개 — diff: ${zero:-(없음)} / 새 파일 $untracked"
  # greenwash.py 는 docstring 안의 칸 이름 글자만: docstring 을 뺀 AST 가 기준과 같다
  api python - "$ROOT" "$BASE" > "$S4/routes-ast.txt" 2>&1 <<'PY'
import ast
import subprocess
import sys
from pathlib import Path

root, base = Path(sys.argv[1]), sys.argv[2]
path = "apps/api-py/esgapi/greenwash/service/apis/greenwash.py"


def bare(text: str) -> str:
    tree = ast.parse(text)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr):
            value = body[0].value  # pyright: ignore
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                body[0] = ast.Pass()
    return ast.dump(tree, include_attributes=False)


old = subprocess.run(["git", "-C", str(root), "show", f"{base}:{path}"], capture_output=True, text=True, check=True).stdout
same = bare(old) == bare((root / path).read_text(encoding="utf-8"))
print(f"greenwash.py: docstring 밖 AST {'같음' if same else 'DIFF'}")
sys.exit(0 if same else 1)
PY
  e=$?
  sed 's/^/    /' "$S4/routes-ast.txt"
  report 2 "0줄 목록(+ greenwash.py 는 docstring 만)" "$([ -z "$zero" ] && [ "$untracked" = 0 ] && [ "$e" = 0 ] && echo 0 || echo 1)"
fi

if want 3; then
  api python - "$API_PY" > "$S4/old-keys.txt" 2>&1 <<'PY'
"""옛 키 69개(59 낱말)를 구조로 센다: 꼴 넷의 TypedDict 필드 키, 예시 JSON 의 객체 키, 고정 스키마·openapi(꼴 넷 모듈의
TypedDict 이름 전부 + GreenwashReviewUpdate)의 properties·required 이름. 설명문·값·예외 키는 셈 밖.
xlsx.py·compare.py 는 결과를 읽는 자리(["…"], "…":) 의 옛 키를 글자로 센다."""
import json
import re
import sys
import typing
from pathlib import Path
from typing import Any

from esgapi.greenwash.flows import compare_shapes, review_shapes, shapes, terms_shapes
from esgapi.greenwash.tests.flows.test_wire import RENAMED

api_py = Path(sys.argv[1])
E = api_py / "esgapi/greenwash"
OLD = {old for pairs in RENAMED.values() for old, _ in pairs}
counts: dict[str, int] = {}
hits: list[str] = []


def note(where: str, keys: list[str]) -> None:
    found = [k for k in keys if k in OLD]
    counts[where] = counts.get(where, 0) + len(found)
    hits.extend(f"{where}: {k}" for k in found)


names: list[str] = []
for module in (shapes, review_shapes, compare_shapes, terms_shapes):
    for name, value in vars(module).items():
        if typing.is_typeddict(value) and value.__module__ == module.__name__:
            names.append(name)
            note("꼴 TypedDict", list(value.__annotations__))


def object_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [*value, *(k for v in value.values() for k in object_keys(v))]
    if isinstance(value, list):
        return [k for v in value for k in object_keys(v)]
    return []


examples = sorted((E / "tests/data/contract-examples").rglob("*.json"))
for path in examples:
    note("예시 JSON", object_keys(json.loads(path.read_text(encoding="utf-8"))))


def schema_names(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        props = value.get("properties")
        if isinstance(props, dict):
            found += list(props)
        req = value.get("required")
        if isinstance(req, list):
            found += [r for r in req if isinstance(r, str)]
        for k, v in value.items():
            if k not in ("description", "title"):
                found += schema_names(v)
    elif isinstance(value, list):
        for v in value:
            found += schema_names(v)
    return found


pinned = sorted((E / "tests/data/flow-shapes").rglob("*.schema.json"))
for path in pinned:
    note("고정 스키마", schema_names(json.loads(path.read_text(encoding="utf-8"))))
components = json.loads((api_py / "generated/openapi.json").read_text(encoding="utf-8"))["components"]["schemas"]
picked = [n for n in [*names, "GreenwashReviewUpdate"] if n in components]
missing = [n for n in [*names, "GreenwashReviewUpdate"] if n not in components]
for name in picked:
    note("openapi 구성요소", schema_names(components[name]))

pattern = re.compile(r"""\[\s*["'](\w+)["']\s*\]|["'](\w+)["']\s*:""")
for rel in ("flows/xlsx.py", "flows/compare.py"):
    text = (E / rel).read_text(encoding="utf-8")
    note(f"{rel} 읽는 자리", [a or b for a, b in pattern.findall(text)])

print(f"옛 키 낱말 {len(OLD)}개(쌍 {sum(len(p) for p in RENAMED.values())}) · 꼴 TypedDict {len(names)}개 · 예시 {len(examples)} · "
      f"고정 스키마 {len(pinned)} · openapi 구성요소 {len(picked)}(없음 {missing})")
for where, n in counts.items():
    print(f"{where}: 옛 키 {n}")
for h in hits:
    print("!!", h)
bad = sum(counts.values()) + len(missing)
print(f"OLD_KEYS={bad}")
sys.exit(1 if bad else 0)
PY
  e=$?
  sed 's/^/    /' "$S4/old-keys.txt"
  report 3 "옛 키 0(구조로)" "$e"
fi

if want 4; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  api python - "$S4/verify-fast.log" "$S4/ts-red-files.txt" > "$S4/verify-fast-judge.txt" 2>&1 <<'PY'
"""단계마다 (이름, EXIT). TS 두 줄 밖은 전부 0, TS 의 빨간 파일은 전부 apps/web/src/greenwash/ 아래."""
import re
import sys
from pathlib import Path

log = Path(sys.argv[1]).read_text(encoding="utf-8")
steps = re.findall(r"^▶ (.+?)\n(?:.*\n)*?EXIT=(\d+)$", log, re.M)
TS = ("pnpm -r typecheck", "pnpm -r test")
bad_steps = [(name, code) for name, code in steps if code != "0" and name not in TS]
files = set(re.findall(r"^apps/web typecheck: (\S+?)\(\d+,\d+\): error", log, re.M))
files |= set(re.findall(r"FAIL  (src/\S+?\.tsx?)", log))
files |= set(re.findall(r"❯ (src/\S+?\.tsx?) \(\d+ tests? \| \d+ failed", log))
red = sorted(f"apps/web/{f}" for f in files)
outside = [f for f in red if not f.startswith("apps/web/src/greenwash/")]
ts_codes = {name: code for name, code in steps if name in TS}
ts_red_without_files = any(code != "0" for code in ts_codes.values()) and not red
Path(sys.argv[2]).write_text("".join(f"{f}\n" for f in red), encoding="utf-8")
for name, code in steps:
    print(f"{name} EXIT={code}")
print(f"TS 빨간 파일 {len(red)}: {red}")
print(f"api-py·parser 쪽 빨강 {bad_steps} · greenwash 밖 TS 빨강 {outside} · TS 가 빨간데 파일을 못 읽음 {ts_red_without_files}")
ok = steps and not bad_steps and not outside and not ts_red_without_files
print(f"FAST_JUDGE={'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
PY
  e1=$?
  sed 's/^/    /' "$S4/verify-fast-judge.txt"
  echo "    끝 줄: $(tail -1 "$S4/verify-fast.log")"
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e2=$?
  echo "    check-gates: $(tail -1 "$S4/check-gates.log")"
  report 4 "verify.sh --fast(TS 빨강은 greenwash 아래만) + check-gates" "$([ "$e1$e2" = 00 ] && echo 0 || echo 1)"
fi

if want 5; then
  rm -f "$S4/netlog.txt"
  G1A_NET_LOG="$S4/netlog.txt" pyt pytest-greenwash -p esgapi.greenwash.tests.netcount esgapi/greenwash
  e=$?
  now=$(api pytest -q --collect-only -p no:cacheprovider esgapi/greenwash 2>/dev/null | grep -cE '::')
  added=$(api pytest -q --collect-only -p no:cacheprovider esgapi/greenwash/tests/flows/test_wire.py esgapi/greenwash/tests/test_contracts_gc2.py -k "test_wire or camel_case_mark or old_snake_case_mark" 2>/dev/null | grep -cE '::')
  echo "    모은 테스트 $now · 이 밴드가 더한 것 $added(test_wire + gc2 의 (j)) · 기준 $BASE 의 수(= 지금 - 더한 것, 뺀 테스트 0) $((now - added))"
  report 5 "pytest esgapi/greenwash" "$e"
fi

if want 6; then
  mkdir -p "$S4/pinned"
  (cd "$API_PY" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python - "$API_PY" "$S4/pinned") > "$S4/pinned.txt" 2>&1 <<'PY'
"""고정 스키마 넷을 test_shapes·test_contracts_gc1 의 pinned_text 로 OUT 에 다시 뽑아 저장소와 바이트로 견준다."""
import sys
from pathlib import Path

import django

django.setup()
from esgapi.greenwash.flows import compare_shapes, review_shapes, shapes, terms_shapes  # noqa: E402
from esgapi.greenwash.tests.flows.test_shapes import pinned_text as result_text  # noqa: E402
from esgapi.greenwash.tests.test_contracts_gc1 import pinned_text  # noqa: E402

repo, out = Path(sys.argv[1]) / "esgapi/greenwash/tests/data/flow-shapes", Path(sys.argv[2])
rows = [
    (f"{shapes.SHAPE}.schema.json", result_text(shapes.SHAPE)),
    (f"review/{review_shapes.SHAPE}.schema.json", pinned_text(review_shapes.REVIEW_SHAPES[review_shapes.SHAPE])),
    (f"compare/{compare_shapes.SHAPE}.schema.json", pinned_text(compare_shapes.COMPARE_SHAPES[compare_shapes.SHAPE])),
    (f"terms/{terms_shapes.SHAPE}.schema.json", pinned_text(terms_shapes.TERMS_SHAPES[terms_shapes.SHAPE])),
]
bad = 0
for rel, text in rows:
    target = out / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    same = target.read_bytes() == (repo / rel).read_bytes()
    bad += not same
    print(f"{rel}: {'같음' if same else 'DIFF'}")
print(f"PINNED_DIFF={bad}/{len(rows)}")
sys.exit(1 if bad else 0)
PY
  e1=$?
  sed 's/^/    /' "$S4/pinned.txt"
  terms_diff=$(git -C "$ROOT" diff --stat "$BASE" -- "$G/tests/data/flow-shapes/terms" | tail -1)
  echo "    terms-default 고정 스키마의 기준 대비 diff: ${terms_diff:-(없음)}"
  before=$(cd "$API_PY" && shasum -a 256 generated/openapi.json generated/api.d.ts generated/api.d.ts.source-sha256)
  (cd "$API_PY" && PATH="$NODE_PATH_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen-ts-types.log" 2>&1
  e2=$?
  after=$(cd "$API_PY" && shasum -a 256 generated/openapi.json generated/api.d.ts generated/api.d.ts.source-sha256)
  e3=$([ "$before" = "$after" ] && echo 0 || echo 1)
  echo "    gen-ts-types.sh EXIT=$e2 · 다시 뽑은 generated 셋이 그 전과 $([ "$e3" = 0 ] && echo 같음 || echo DIFF)"
  report 6 "다시 뽑은 것이 같다(고정 스키마 넷 + generated 셋)" "$([ "$e1$e2$e3" = 000 ] && [ -z "$terms_diff" ] && echo 0 || echo 1)"
fi

if want 7; then
  (cd "$API_PY" && G1A_OUT="$OUT/g1a" G1A_BASE="$BASE" scripts/section4-G1a.sh --step 9,11,12,13,14,15,16,17,18) > "$S4/g1a-section4.log" 2>&1
  e=$?
  grep -E '^\[|SAME=|SECTION4_FAIL|PLANTED|FINGERPRINT' "$S4/g1a-section4.log" | sed 's/^/    /'
  report 7 "G1a 자기검증(9,11~18) GC3 바닥에서" "$e"
fi

if want 8; then
  e=0
  for band in G1d GR1 GL1; do
    before=$(git -C "$ROOT" show "$BASE:apps/api-py/scripts/planted-breaks-$band.sh" | grep -cE '^    \([0-9]+, "')
    lower=$(echo "$band" | tr 'A-Z' 'a-z')
    log="$S4/planted-$lower.log"
    (cd "$API_PY" && env G1D_OUT="$OUT/g1d" GR1_OUT="$OUT/gr1" GL1_OUT="$OUT/gl1" "scripts/planted-breaks-$band.sh") > "$log" 2>&1
    be=$?
    got=$(grep '^PLANTED=' "$log" | tail -1)
    fp=$(grep '^FINGERPRINT=' "$log" | tail -1)
    echo "    $band: 기준의 심은 수 $before · 지금 ${got:-(없음)} · ${fp:-(없음)} · 종료 $be"
    if [ "$be" != 0 ] || [ "$got" != "PLANTED=$before/$before" ] || ! echo "$fp" | grep -q '^FINGERPRINT=same'; then e=1; fi
  done
  echo "    G1a 의 것은 7 의 18번이 본다. G1c 의 것은 scripts/archive 에 있어 돌리지 않는다."
  report 8 "앞 밴드 심은 파손(G1d·GR1·GL1)" "$e"
fi

if want 9; then
  (cd "$API_PY" && GC3_OUT="$OUT" GC3_BASE="$BASE" scripts/planted-breaks-GC3.sh) > "$S4/planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/planted.log" | sed 's/^/    /'
  ok=$([ "$e" = 0 ] && grep -q '^PLANTED=5/5' "$S4/planted.log" && grep -q '^FINGERPRINT=same' "$S4/planted.log" && echo 0 || echo 1)
  report 9 "심은 파손" "$ok"
fi

if want 10; then
  hits=0; keys=0; opens=0
  : > "$S4/forbidden-hits.txt"
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록이 없다: $WORDS"; hits=1
  else
    # 기준에 있던 파일은 더한 줄만 본다(README 처럼 기준에 이미 걸린 줄이 있는 공유 파일), 새 파일은 전부.
    while IFS= read -r f; do
      [ -f "$ROOT/$f" ] || continue
      if git -C "$ROOT" cat-file -e "$BASE:$f" 2>/dev/null; then
        added=$(git -C "$ROOT" diff "$BASE" -- "$f" | grep '^+' | grep -v '^+++')
        if [ -n "$added" ] && printf '%s\n' "$added" | grep -F -i -q -f "$WORDS"; then hit=1; else hit=0; fi
        if git -C "$ROOT" show "$BASE:$f" | grep -F -i -q -f "$WORDS"; then echo "    기준에 이미 걸린 파일(더한 줄만 봄): $f"; fi
      else
        if grep -F -i -q -f "$WORDS" "$ROOT/$f"; then hit=1; else hit=0; fi
      fi
      if [ "$hit" = 1 ]; then echo "$f" >> "$S4/forbidden-hits.txt"; hits=$((hits + 1)); fi
    done < <(changed_files)
  fi
  mhits=0
  msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
  if [ -n "$msgs" ] && [ -f "$WORDS" ] && printf '%s' "$msgs" | grep -F -i -q -f "$WORDS"; then mhits=1; fi
  while IFS= read -r f; do
    [ -f "$ROOT/$f" ] || continue
    if grep -E -q 'sk-[A-Za-z0-9_-]{20,}' "$ROOT/$f"; then echo "    키 꼴: $f"; keys=$((keys + 1)); fi
    case "$f" in apps/api-py/scripts/section4-GC3.sh) continue ;; esac  # 찾는 글 자체가 든 이 스크립트
    if grep -E -q 'manufac-erp|spike/\.env' "$ROOT/$f"; then echo "    키 파일 경로: $f"; opens=$((opens + 1)); fi
  done < <(changed_files)
  if [ ! -f "$S4/netlog.txt" ]; then
    G1A_NET_LOG="$S4/netlog.txt" api pytest -q -p no:cacheprovider -p esgapi.greenwash.tests.netcount esgapi/greenwash > "$S4/pytest-net.log" 2>&1
  fi
  tests=$(wc -l < "$S4/netlog.txt" | tr -d ' ')
  blocked=$(awk '{s += $1} END {print s + 0}' "$S4/netlog.txt")
  echo "    낱말 $( [ -f "$WORDS" ] && grep -c . "$WORDS" || echo 0)개로 본 파일 $(changed_files | wc -l | tr -d ' '): 걸린 파일 $hits, 커밋 메시지($BASE..HEAD) $mhits"
  echo "    키 꼴 $keys, 키 파일 경로 $opens, 소켓 문지기가 막은 시도 $blocked (테스트 $tests 개에서)"
  cat "$S4/forbidden-hits.txt"
  report 10 "기업명·키·소켓" "$([ "$hits$mhits$keys$opens$blocked" = 00000 ] && [ "$tests" -gt 0 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
