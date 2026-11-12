#!/usr/bin/env bash
# 밴드 IRS2 의 §4 자기검증(발주서 band-handoffs/IRS2-order.md §4 — section4-HD1.sh 꼴). 줄마다 [n] … EXIT= 를 찍고
# 끝 줄 SECTION4_FAIL=<n>.
# 사용(어디서든): apps/api-py/scripts/section4-IRS2.sh [--planted] [--msg <파일>] [--step 1,2,…]
# 단계: 1 허용 경로(OUTSIDE=) · 2 0줄 목록(ZERO_CHANGED=) · 3 기존 시험 −줄 · 4 lint-imports·ruff·pyright(바뀐 파일) ·
#   5 materiality 순수 · 6 업무(materiality 목록 + dc 조건의 runs selector·데이터 검증 목록) · 7 심은 파손 · 8 트레일러 ·
#   9 금지 글(더한 줄 + 메시지) · 10 scripts/verify.sh --fast.
# runs selector 는 dc(플랫폼-서버) 허락(sid:MARC-TICK-397 노트)으로 허용 — BriefRun 의 started_at 한 칸.
# 환경 변수: S4_OUT(기본 워크트리 곁의 IRS2.out) · IRS2_BASE(기본 12ff64c7). compose esg-app-irs2 의 postgres 가 떠
# 있어야 한다(6·7). 공급사를 부르지 않는다(envx). macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${IRS2_BASE:-12ff64c7}"
OUT="${S4_OUT:-$SIDE/IRS2.out}"
S4="$OUT/section4"
FORBIDDEN="$SIDE/G1a.out/forbidden-words.txt"
mkdir -p "$S4"
envx() {
  env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY \
    -u LLM_RUN_MODE "$@"
}
api() { (cd "$API_PY" && envx uv run --frozen "$@"); }

PLANTED=""
MSG=""
STEPS="all"
while [ $# -gt 0 ]; do
  case "$1" in
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:?--msg 뒤에 파일}"; shift 2 ;;
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
LAST=$(date +%s)
report() {
  now=$(date +%s); echo "[$1] $2 EXIT=$3 $((now - LAST))s"; LAST=$now; [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

echo "BASE=$BASE HEAD=$(git -C "$ROOT" rev-parse HEAD)"

HELPER="$S4/irs2_helper.py"
cat > "$HELPER" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

ROOT, BASE, CMD, ARGS = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4:]
P = r"^apps/api-py/"
E = P + r"esgapi/"
M = E + r"materiality/"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def changed() -> set[str]:
    return set(git("diff", "--name-only", BASE).split()) | set(git("ls-files", "--others", "--exclude-standard").split())


ALLOWED = [  # §1 허용(닫힘) + dc 허락의 runs selector
    M + r"service/actions/runs\.py$",
    M + r"tests/service/apis/test_materiality_runs\.py$",
    P + r"scripts/(section4|planted-breaks)-IRS2\.sh$",
    E + r"runs/service/selectors/runs\.py$",
]
ZERO = [  # §1 0줄(runs 는 selector 파일 밖 전부)
    E + r"runs/(?!service/selectors/runs\.py$)", E + r"core/", M + r"contracts/", E + r"dataverify/",
    r"openapi", r"^packages/.*/generated/", r"^apps/web/", P + r"\.importlinter$",
]
TESTS = [M + r"tests/service/apis/test_materiality_runs\.py$"]

if CMD == "paths":
    found = sorted(changed())
    outside = [f for f in found if not any(re.search(p, f) for p in ALLOWED)]
    zero = [f for f in found if any(re.search(p, f) for p in ZERO)]
    print(f"  바뀐 파일 {found}")
    print(f"  OUTSIDE={len(outside)} {outside}")
    print(f"  ZERO_CHANGED={len(zero)} {zero}")
    numstat = git("diff", "--numstat", BASE, "--", "apps/api-py/esgapi/runs")
    print(f"  runs numstat {numstat.strip()!r}")
    sys.exit(0 if not outside and not zero else 1)

if CMD == "minus":
    bad = []
    for line in git("diff", "--numstat", BASE).splitlines():
        plus, minus, f = line.split("\t")
        if any(re.search(p, f) for p in TESTS) and minus != "0":
            bad.append((f, minus))
    print(f"  기존 시험 −줄 {bad}")
    sys.exit(0 if not bad else 1)

if CMD == "trailers":
    text = Path(ARGS[0]).read_text(encoding="utf-8")
    need = [
        "Ticket: MARC-TICK-397",
        "Concerns: MARC-ISSUE-444",
        "Constraint: 응답 바이트 그대로",
        "Rejected: materiality 안 queryset",
    ]
    missing = [n for n in need if n not in text]
    print(f"  빠진 트레일러 {missing}")
    sys.exit(0 if not missing else 1)

if CMD == "secrets":
    words = [w.strip() for w in Path(ARGS[0]).read_text(encoding="utf-8").splitlines() if w.strip()]
    msg = Path(ARGS[1]) if len(ARGS) > 1 and ARGS[1] else None
    added: list[str] = []
    tracked = set(git("ls-files").split())
    for f in sorted(changed()):
        path = ROOT / f
        if not path.is_file():
            continue
        if f in tracked:
            diff = git("diff", BASE, "--", f)
            added += [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
        else:
            added += path.read_text(encoding="utf-8").splitlines()
    texts = list(added)
    if msg is not None and msg.is_file():
        texts += msg.read_text(encoding="utf-8").splitlines()
    keys = sum(bool(re.search(r"sk-[A-Za-z0-9_-]{16,}", t)) for t in texts)
    paths = sum(bool(re.search(r"marcspon-openai\.env|manufac-erp/spike/\.env", t)) for t in texts)
    names = sum(any(w in t for w in words) for t in texts)
    assert re.search(r"sk-[A-Za-z0-9_-]{16,}", "sk-" + "A" * 20)  # 양성 대조
    print(f"  key_like={keys} key_paths={paths} forbidden_word_lines={names} words={len(words)} lines={len(texts)}")
    sys.exit(0 if keys == paths == names == 0 and words else 1)

sys.exit(f"모르는 CMD {CMD}")
PY
helper() { (cd "$ROOT" && python3 -I "$HELPER" "$ROOT" "$BASE" "$@"); }

if want 1; then
  helper paths > "$S4/1.log" 2>&1; e=$?; cat "$S4/1.log"; report 1 "허용 경로·0줄 목록" "$e"
fi

if want 3; then
  helper minus > "$S4/3.log" 2>&1; e=$?; cat "$S4/3.log"; report 3 "기존 시험 −줄 0" "$e"
fi

if want 4; then
  e=0
  api lint-imports > "$S4/4a.log" 2>&1 || e=1; grep "Contracts:" "$S4/4a.log"
  pyr=$(cd "$ROOT" && { git diff --name-only "$BASE"; git ls-files --others --exclude-standard; } \
    | sed -n 's#^apps/api-py/\(.*\.py\)$#\1#p' | sort -u | while read -r f; do [ -f "$API_PY/$f" ] && echo "$f"; done)
  # shellcheck disable=SC2086
  api pyright $pyr > "$S4/4b.log" 2>&1 || e=1; tail -1 "$S4/4b.log"
  api ruff check esgapi tests scripts > "$S4/4c.log" 2>&1 || e=1; tail -1 "$S4/4c.log"
  api ruff format --check esgapi tests scripts > "$S4/4d.log" 2>&1 || e=1; tail -1 "$S4/4d.log"
  report 4 "lint-imports·pyright(바뀐 파일)·ruff" "$e"
fi

if want 5; then
  api pytest -q -p no:cacheprovider -m "not django_db" esgapi/materiality > "$S4/5.log" 2>&1; e=$?
  echo "  $(tail -1 "$S4/5.log")"
  report 5 "materiality 순수 시험" "$e"
fi

if want 6; then
  (cd "$API_PY" && envx scripts/test-business.sh -p no:cacheprovider -n 4 \
    esgapi/materiality/tests/service/apis/test_materiality_runs.py \
    esgapi/runs/tests/service/selectors/test_runs.py \
    esgapi/dataverify/tests/service/apis/test_dataverify_runs.py) > "$S4/6.log" 2>&1; e=$?
  echo "  $(tail -1 "$S4/6.log")"
  report 6 "업무(materiality 목록·runs selector·데이터 검증 목록)" "$e"
fi

if want 7 && [ -n "$PLANTED" ]; then
  IRS2_OUT="$OUT" "$API_PY/scripts/planted-breaks-IRS2.sh" > "$S4/7.log" 2>&1; e=$?
  grep -E "=> |^P0=|^EXTRA=|^FINGERPRINT=|^PLANTED=" "$S4/7.log"
  report 7 "심은 파손(분모 5 + X1)" "$e"
fi

if want 8 && [ -n "$MSG" ]; then
  helper trailers "$MSG" > "$S4/8.log" 2>&1; e=$?; cat "$S4/8.log"; report 8 "트레일러" "$e"
fi

if want 9; then
  helper secrets "$FORBIDDEN" "$MSG" > "$S4/9.log" 2>&1; e=$?; cat "$S4/9.log"
  report 9 "금지 글·키 꼴·키 경로" "$e"
fi

if want 10; then
  (cd "$ROOT" && envx scripts/verify.sh --fast) > "$S4/10.log" 2>&1; e=$?
  tail -1 "$S4/10.log"
  grep -q "^VERIFY_FAST=PASS" "$S4/10.log" || e=1
  report 10 "verify.sh --fast" "$e"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = "0" ]
