#!/usr/bin/env bash
# 밴드 GR1 의 §4 자기검증(발주서 band-handoffs/GR1-order.md §4). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-GR1.sh                 전부
#   apps/api-py/scripts/section4-GR1.sh --step 1,3,8b   일부(번호는 발주서 §4 의 번호)
#
# 환경 변수:
#   GR1_BASE   기준 커밋(기본: 착수 때 적은 97cda96…)
#   GR1_OUT    산출물 자리(기본: 워크트리 곁의 GR1.out). 산출물은 $GR1_OUT/section4/ 아래
#   GR1_FORBIDDEN_WORDS_FILE  기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt — 이 파일만 연다)
# 컨테이너를 띄우지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${GR1_BASE:-97cda96d48dfe4a65f0f7a3faffe453013318a60}"
OUT="${GR1_OUT:-$SIDE/GR1.out}"
WORDS="${GR1_FORBIDDEN_WORDS_FILE:-$SIDE/G1a.out/forbidden-words.txt}"
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
ALLOWED="^($G/flows/compare\\.py|$G/flows/textnorm\\.py|$G/flows/pdfium_locate\\.py|$G/flows/compare_shapes\\.py|$G/tests/flows/test_compare\\.py|$G/tests/flows/test_textnorm\\.py|$G/tests/flows/compare_pages\\.py|apps/api-py/scripts/(section4|planted-breaks)-GR1\\.sh|apps/api-py/scripts/planted-breaks-G1d\\.sh)\$"

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
  ZERO="$G/calc $G/service $G/api.py $G/apps.py"
  for f in colab adapters xlsx result gw1 registration shapes review_shapes terms_shapes; do ZERO="$ZERO $G/flows/$f.py"; done
  ZERO="$ZERO $G/tests/data $(cd "$ROOT" && ls $G/tests/test_contracts_gc*.py | tr '\n' ' ')"
  ZERO="$ZERO $(git -C "$ROOT" ls-tree -r --name-only "$BASE" -- $G/tests/flows/ | tr '\n' ' ')"
  ZERO="$ZERO apps/api-py/generated"
  for m in core config user organization inventory reference reconcile; do ZERO="$ZERO apps/api-py/esgapi/$m"; done
  ZERO="$ZERO apps/api-py/tests apps/api-py/pyproject.toml apps/api-py/uv.lock apps/api-py/.importlinter apps/web README.md"
  echo "$ZERO" | tr ' ' '\n' | grep . > "$S4/zero-paths.txt"
  # shellcheck disable=SC2086
  zero=$(cd "$ROOT" && git diff "$BASE" --stat -- $ZERO | tail -1)
  # shellcheck disable=SC2086
  untracked=$(cd "$ROOT" && git ls-files -o --exclude-standard -- $ZERO | grep -c .)
  echo "    0줄 자리 $(grep -c . "$S4/zero-paths.txt")개(기존 tests/flows 파일 낱낱 포함) — diff: ${zero:-(없음)} / 새 파일 $untracked"
  report 2 "0줄 목록" "$([ -z "$zero" ] && [ "$untracked" = 0 ] && echo 0 || echo 1)"
fi

if want 3; then
  api python - "$ROOT" "$BASE" > "$S4/moved.txt" 2>&1 <<'PY'
"""옮김만: pdfium_locate 의 지운 줄 = textnorm 에 같은 차례로(옛 주석 한 줄 빼고), 더한 줄 = import 셋 + 새 주석 한 줄.
planted-breaks-G1d 는 파손 3·4 의 파일 자리만. compare_shapes 는 모듈 docstring 안만."""
import re
import subprocess
import sys
from pathlib import Path

root, base = Path(sys.argv[1]), sys.argv[2]
F = "apps/api-py/esgapi/greenwash/flows/"
bad: list[str] = []


def diff(path: str) -> tuple[list[str], list[str], list[tuple[int, int, int, int]]]:
    out = subprocess.run(["git", "-C", str(root), "diff", "-U0", base, "--", path], capture_output=True, text=True, check=True).stdout
    minus = [l[1:] for l in out.splitlines() if l.startswith("-") and not l.startswith("---")]
    plus = [l[1:] for l in out.splitlines() if l.startswith("+") and not l.startswith("+++")]
    hunks = [tuple(int(x or 1) for x in m.groups()) for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", out, re.M)]
    return minus, plus, hunks  # type: ignore[return-value]


OLD_COMMENT = "# ── 정규화 (probe.py 의 norm_chars·norm_str·norm_map) ─────────────────────────"
minus, plus, _ = diff(F + "pdfium_locate.py")
removed = [l for l in minus if l.strip()]
added = [l for l in plus if l.strip()]
moved = [l for l in removed if l != OLD_COMMENT]
if removed.count(OLD_COMMENT) != 1:
    bad.append(f"옛 :36 주석을 지운 줄이 {removed.count(OLD_COMMENT)}번")
new_comments = [l for l in added if l.startswith("# ── 정규화 (probe.py 의 norm_map)")]
imports = [l for l in added if l.startswith("from esgapi.greenwash.flows.textnorm import")]
others = [l for l in added if l not in new_comments and l not in imports]
if len(new_comments) != 1 or len(imports) != 3 or others:
    bad.append(f"더한 줄: 새 주석 {len(new_comments)}, import {len(imports)}, 그 밖 {others}")
tn = (root / F / "textnorm.py").read_text(encoding="utf-8").splitlines()
i = 0
for line in tn:
    if i < len(moved) and line == moved[i]:
        i += 1
if i != len(moved):
    bad.append(f"지운 줄 {len(moved)} 가운데 textnorm 에 같은 차례로 든 것 {i}")
tn_body = [l for l in tn if l.strip()]
start = tn_body.index(moved[0]) if moved and moved[0] in tn_body else -1
if tn_body[start:] != moved:
    bad.append("textnorm 의 옮긴 몸(첫 옮긴 줄부터 끝까지, 빈 줄 밖)이 지운 줄과 다르다")
print(f"pdfium_locate: 지운 줄(빈 줄 밖) {len(removed)} = 옮김 {len(moved)} + 옛 주석 1 · 더한 줄 {len(added)} = import {len(imports)} + 새 주석 {len(new_comments)}")
print(f"textnorm: 옮긴 줄 {i}/{len(moved)} 같은 차례, 머리말 뒤 몸이 지운 줄과 같음 {tn_body[start:] == moved}")

minus, plus, _ = diff("apps/api-py/scripts/planted-breaks-G1d.sh")
want_minus = ['    (3, "NFKC 를 뺌", P,', '    (4, "공백 제거를 뺌", P,']
want_plus = [l.replace(" P,", ' F / "textnorm.py",') for l in want_minus]
if (minus, plus) != (want_minus, want_plus):
    bad.append(f"planted-breaks-G1d 의 diff 가 파손 3·4 의 파일 자리만이 아니다: -{minus} +{plus}")
print(f"planted-breaks-G1d: -{len(minus)} +{len(plus)} (파손 3·4 의 P → textnorm.py)")


def docstring_span(text: str) -> tuple[int, int]:
    lines = text.splitlines()
    first = next(n for n, l in enumerate(lines, 1) if l.startswith('"""'))
    last = next(n for n, l in enumerate(lines, 1) if n > first and l.rstrip().endswith('"""'))
    return first, last


path = F + "compare_shapes.py"
old_text = subprocess.run(["git", "-C", str(root), "show", f"{base}:{path}"], capture_output=True, text=True, check=True).stdout
o_span, n_span = docstring_span(old_text), docstring_span((root / path).read_text(encoding="utf-8"))
_, _, hunks = diff(path)
outside = [h for h in hunks if not (o_span[0] < h[0] and h[0] + h[1] - 1 < o_span[1] and n_span[0] < h[2] and h[2] + h[3] - 1 < n_span[1])]
if outside or not hunks:
    bad.append(f"compare_shapes 의 diff 가 모듈 docstring 밖이다: {outside}")
print(f"compare_shapes: 덩이 {len(hunks)}, docstring 옛 {o_span} 새 {n_span}, 밖 {len(outside)}")
for b in bad:
    print("!!", b)
print(f"MOVED_BAD={len(bad)}")
sys.exit(1 if bad else 0)
PY
  e=$?
  sed 's/^/    /' "$S4/moved.txt"
  report 3 "옮김만(pdfium_locate·textnorm·planted-breaks-G1d·compare_shapes)" "$e"
fi

if want 4; then
  (cd "$ROOT" && PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  echo "    $last"
  report 4 "verify.sh --fast" "$([ "$last" = "VERIFY_FAST=PASS" ] && echo 0 || echo 1)"
fi

if want 5; then
  rm -f "$S4/netlog.txt"
  G1A_NET_LOG="$S4/netlog.txt" pyt pytest-greenwash -p esgapi.greenwash.tests.netcount esgapi/greenwash
  report 5 "pytest esgapi/greenwash" "$?"
fi

if want 6; then
  api python - "$API_PY" > "$S4/pinned.txt" 2>&1 <<'PY'
"""compare@1·result@1·review@1 의 고정 스키마를 TypedDict 에서 다시 뽑아 파일과 바이트로 견준다(GC1 의 pinned_text 꼴)."""
import json
import sys
from pathlib import Path

from esgapi.greenwash.flows import compare_shapes, review_shapes, shapes

pinned = Path(sys.argv[1]) / "esgapi/greenwash/tests/data/flow-shapes"
rows = [
    (compare_shapes.COMPARE_SHAPES[compare_shapes.SHAPE], pinned / "compare" / f"{compare_shapes.SHAPE}.schema.json"),
    (shapes.RESULT_SHAPES[shapes.SHAPE], pinned / f"{shapes.SHAPE}.schema.json"),
    (review_shapes.REVIEW_SHAPES[review_shapes.SHAPE], pinned / "review" / f"{review_shapes.SHAPE}.schema.json"),
]
bad = 0
for adapter, path in rows:
    same = path.read_bytes() == (json.dumps(adapter.json_schema(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    bad += not same
    print(f"{path.name}: {'같음' if same else 'DIFF'}")
print(f"PINNED_DIFF={bad}/{len(rows)}")
sys.exit(1 if bad else 0)
PY
  e1=$?
  sed 's/^/    /' "$S4/pinned.txt"
  pyt pinned-tests esgapi/greenwash/tests/test_contracts_gc1.py esgapi/greenwash/tests/test_contracts_gc2.py esgapi/greenwash/tests/flows/test_shapes.py -k "pinned"
  e2=$?
  report 6 "고정 스키마 셋(다시 뽑아 바이트 대조 + GC1·GC2·G1a 의 pinned 테스트)" "$([ "$e1$e2" = 00 ] && echo 0 || echo 1)"
fi

if want 7; then
  api python scripts/check_test_layout.py > "$S4/test-layout.txt" 2>&1
  e=$?
  head -3 "$S4/test-layout.txt" | sed 's/^/    /'
  report 7 "check_test_layout" "$e"
fi

if want 8; then
  (cd "$API_PY" && G1A_OUT="$OUT/g1a" G1A_BASE="$BASE" scripts/section4-G1a.sh --step 9,10,11,13,15,17,18) > "$S4/g1a-section4.log" 2>&1
  e=$?
  grep -E '^\[|SECTION4_FAIL' "$S4/g1a-section4.log" | sed 's/^/    /'
  report 8 "G1a 자기검증(9,10,11,13,15,17,18) GR1 바닥에서" "$e"
fi

if want 8b; then
  (cd "$API_PY" && G1D_OUT="$OUT/g1d" scripts/planted-breaks-G1d.sh) > "$S4/g1d-planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/g1d-planted.log" | sed 's/^/    /'
  ok=$([ "$e" = 0 ] && grep -q '^PLANTED=14/14' "$S4/g1d-planted.log" && grep -q '^FINGERPRINT=same' "$S4/g1d-planted.log" && echo 0 || echo 1)
  report 8b "G1d 심은 파손(정규화를 옮긴 뒤)" "$ok"
fi

if want 9; then
  (cd "$API_PY" && GR1_OUT="$OUT" scripts/planted-breaks-GR1.sh) > "$S4/planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/planted.log" | sed 's/^/    /'
  ok=$([ "$e" = 0 ] && grep -q '^PLANTED=14/14' "$S4/planted.log" && grep -q '^FINGERPRINT=same' "$S4/planted.log" && echo 0 || echo 1)
  report 9 "심은 파손" "$ok"
fi

if want 10; then
  hits=0; keys=0; opens=0
  : > "$S4/forbidden-hits.txt"
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록이 없다: $WORDS"; hits=1
  else
    while IFS= read -r f; do
      [ -f "$ROOT/$f" ] || continue
      if grep -F -i -q -f "$WORDS" "$ROOT/$f"; then echo "$f" >> "$S4/forbidden-hits.txt"; hits=$((hits + 1)); fi
    done < <(changed_files)
  fi
  mhits=0
  msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
  if [ -n "$msgs" ] && [ -f "$WORDS" ] && printf '%s' "$msgs" | grep -F -i -q -f "$WORDS"; then mhits=1; fi
  while IFS= read -r f; do
    [ -f "$ROOT/$f" ] || continue
    if grep -E -q 'sk-[A-Za-z0-9_-]{20,}' "$ROOT/$f"; then echo "    키 꼴: $f"; keys=$((keys + 1)); fi
    case "$f" in apps/api-py/scripts/section4-GR1.sh) continue ;; esac  # 찾는 글 자체가 든 이 스크립트
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
