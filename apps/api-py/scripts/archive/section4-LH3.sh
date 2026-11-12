#!/usr/bin/env bash
# 밴드 LH3 의 §4 자기검증(발주서 band-handoffs/LH3-order.md §4 — section4-LH2.sh 꼴). 줄마다 [n] … EXIT= 를 찍고
# 끝 줄 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-LH3.sh [--commit 1|2] [--with-containers] [--planted] [--msg <파일>] [--step 1,2,…]
#     --commit n          경계(기본 2). 1 이면 ① 의 허용 경로로 본다
#     --with-containers   8 업무 층 전부(test-business.sh esgapi)·보안 층
#     --planted           9 심은 파손(PLANTED=<잡음>/<경계 ① 8 · ② 17>)
#     --msg <파일>        10 커밋 메시지 초안의 트레일러
# 단계: 1 허용 경로·0줄·C0 표 밖 지운 줄·generated 0·runs/context.py·types.py 는 독스트링 안만·받아들임 문장 grep ·
#   2 lint-imports 둘·core/llm 의 celery·billiard import 0 · 3 core·config·runs 순수(N1) · 4 모듈 순수 전부 ·
#   5 시험 자리·pyright·ruff · 6 금지 글 · 7 test_client_bytes_unchanged · 8 업무·보안 · 9 심은 파손 · 10 트레일러 ·
#   11 scripts/verify.sh --fast.
# 환경 변수: S4_OUT(기본 워크트리 곁의 LH3.out) · LH3_BASE(기본 989cc43f).
# 컨테이너는 띄우지 않는다(compose esg-app-lh3 의 postgres 가 떠 있어야 한다 — 8·9). 공급사를 부르지 않는다: 모든 pytest
# 는 발주서의 ENVX(키 변수 다섯·LLM_RUN_MODE 를 지운 환경).
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${LH3_BASE:-989cc43f}"
OUT="${S4_OUT:-$SIDE/LH3.out}"
S4="$OUT/section4"
FORBIDDEN="$SIDE/G1a.out/forbidden-words.txt"
mkdir -p "$S4"
ENVX="env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY -u LLM_RUN_MODE"
api() { (cd "$API_PY" && $ENVX uv run --frozen "$@"); }

COMMIT=2
WITH_CONTAINERS=""
PLANTED=""
MSG=""
STEPS="all"
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:?--commit 뒤에 1|2}"; shift 2 ;;
    --with-containers) WITH_CONTAINERS=1; shift ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:?--msg 뒤에 파일}"; shift 2 ;;
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { echo "[$1] $2 EXIT=$3"; [ "$3" = "0" ] || FAIL=$((FAIL + 1)); }

echo "BASE=$BASE HEAD=$(git -C "$ROOT" rev-parse HEAD) COMMIT=$COMMIT"

HELPER="$S4/lh3_helper.py"
cat > "$HELPER" <<'PY'
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT, BASE, COMMIT, CMD, ARGS = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5:]
P = r"^apps/api-py/"
E = P + r"esgapi/"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def changed() -> set[str]:
    return set(git("diff", "--name-only", BASE).split()) | set(git("ls-files", "--others", "--exclude-standard").split())


ALLOWED_1 = [
    E + r"runs/context\.py$",
    E + r"core/llm/(client|embedding)\.py$",
    E + r"core/llm/providers/(openai|anthropic|gemini)\.py$",
    E + r"core/tests/llm/test_lh3_(sent|soft_write)\.py$",
    E + r"runs/tests/test_context_bound\.py$",
    E + r"core/tests/llm/test_(cost_bound|soft_deadline)\.py$",
    E + r"core/tests/test_llm_adapters\.py$",
    P + r"scripts/(section4|planted-breaks)-LH3\.sh$",
]
ALLOWED_2 = [
    E + r"core/llm/(setup|types)\.py$",
    E + r"core/management/commands/llm_call\.py$",
    E + r"core/tests/llm/test_lh3_bounds\.py$",
    E + r"core/tests/test_llm_command\.py$",
    E + r"core/tests/llm/providers/test_openai_embedding\.py$",
    E + r"core/tests/llm/test_(dry_run_worst|client_dry_run_tools)\.py$",
    E + r"core/tests/test_llm_client\.py$",
    E + r"core/tests/llm/test_client_bytes_unchanged\.py$",  # C0 한 줄 — 감독 dc 10-28 허락
]
ZERO = [
    E + r"(greenwash|translation|dataverify|materiality|inventory|reconcile|reference|runbundle)/",
    E + r"core/llm/(budget|cost|config|prompts|throttle|embedding_types|schema|retry|sink_db|log|errors)\.py$",
    E + r"core/llm/sinks/", E + r"core/llm/providers/(mock|redact)\.py$", E + r"core/llm/data/",
    E + r"core/llm/purity\.importlinter$", E + r"core/resources/", E + r"core/flows/", E + r"core/service/",
    E + r"core/models\.py$", E + r"runs/tasks\.py$", E + r"config/",
    E + r"(\w+/)?migrations/", E + r"\w+/service/apis/",
    P + r"tests/", P + r"tests_integration/", r"(^|/)conftest\.py$", P + r"\.importlinter$",
    r"^scripts/verify\.sh$", P + r"scripts/planted-breaks\.sh$", r"^infra/", r"^compose\.yaml$", r"^docs/",
    r"(^|/)README\.md$", P + r"generated/", r"^apps/web/", P + r"(pyproject\.toml|uv\.lock)$",
    r"/schemas?(\.py$|/)",
]
# 시험 파일에서 지워도 되는 줄(C0 표 + 감독 「C0 통과」). 그 밖 시험 파일의 ^- 는 0. ① 은 더하기만.
MINUS_OK: dict[str, set[str]] = {
    # C0 통과(감독 dc 10-28) — Q8 로 바뀐 dry_run.cached 해시 한 줄
    "apps/api-py/esgapi/core/tests/llm/test_client_bytes_unchanged.py": {
        '    "dry_run.cached": "bdca9f6618309c37a7320105e1d04f842410cb9ecacccd8021fcda292505ad74",',
    },
}
# 바뀐 줄이 독스트링 안뿐이어야 하는 파일
DOC_ONLY = {
    1: ["apps/api-py/esgapi/runs/context.py"],
    2: ["apps/api-py/esgapi/runs/context.py", "apps/api-py/esgapi/core/llm/types.py"],
}
# 받아들임 문장(머리말 grep — 양성 대조: 같은 정규식이 BASE 에는 없어야 한다)
ACCEPT = {
    1: [("apps/api-py/esgapi/runs/context.py", r"셈은 \*\*받아들임\*\*\(LH3 Q1")],
    2: [
        ("apps/api-py/esgapi/runs/context.py", r"셈은 \*\*받아들임\*\*\(LH3 Q1"),
        ("apps/api-py/esgapi/core/llm/client.py", r"받아들임\(LH3 Q7"),
    ],
}


def doc_lines(text: str) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                lines |= set(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return lines


def doc_only(f: str) -> tuple[bool, int]:
    diff = git("diff", "-U0", BASE, "--", f)
    if not diff:
        return True, 0
    base_doc = doc_lines(git("show", f"{BASE}:{f}"))
    new_doc = doc_lines((ROOT / f).read_text(encoding="utf-8"))
    ok, n, old, new = True, 0, 0, 0
    for line in diff.splitlines():
        m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)", line)
        if m:
            old, new = int(m.group(1)), int(m.group(2))
            continue
        if line.startswith(("+++", "---", "diff ", "index ")):
            continue
        if line.startswith("-"):
            ok, n, old = ok and old in base_doc, n + 1, old + 1
        elif line.startswith("+"):
            ok, n, new = ok and new in new_doc, n + 1, new + 1
    return ok, n


if CMD == "paths":
    files = sorted(changed())
    allowed = ALLOWED_1 + (ALLOWED_2 if COMMIT >= 2 else [])
    outside = [f for f in files if not any(re.search(p, f) for p in allowed)]
    zero = [f for f in files if any(re.search(p, f) for p in ZERO)]
    tracked = set(git("ls-files").split())
    bad_minus = []
    for f in files:
        if "/tests/" not in f or f not in tracked:
            continue
        minus = [l[1:] for l in git("diff", BASE, "--", f).splitlines() if l.startswith("-") and not l.startswith("---")]
        bad_minus += [f"{f}: {l}" for l in minus if l not in MINUS_OK.get(f, set())]
    docs = {f: doc_only(f) for f in DOC_ONLY[COMMIT]}
    accept = []
    for f, rx in ACCEPT[COMMIT]:
        now = bool(re.search(rx, (ROOT / f).read_text(encoding="utf-8")))
        before = bool(re.search(rx, git("show", f"{BASE}:{f}")))
        accept.append((f, now, before))
    print(f"  바뀐 파일 {len(files)} · outside={len(outside)} {outside}")
    print(f"  0줄 경로 {zero} · generated {[f for f in files if '/generated/' in f]}")
    print(f"  C0 밖 지운 줄 {len(bad_minus)}")
    for line in bad_minus:
        print(f"    {line}")
    for f, (ok, n) in docs.items():
        print(f"  {f.split('esgapi/')[1]} 바뀐 줄 {n} · 독스트링 안 {ok}")
    for f, now, before in accept:
        print(f"  받아들임 문장 {f.split('esgapi/')[1]} 지금 {now} · BASE {before}(양성 대조 — BASE 는 False)")
    ok = not outside and not zero and not bad_minus and all(o for o, _ in docs.values())
    ok = ok and all(now and not before for _, now, before in accept)
    sys.exit(0 if ok else 1)

if CMD == "secrets":
    words = [w.strip() for w in Path(ARGS[0]).read_text(encoding="utf-8").splitlines() if w.strip()]
    added: list[str] = []
    tracked = set(git("ls-files").split())
    for f in sorted(changed()):
        path = ROOT / f
        if not path.is_file():
            continue
        diff = git("diff", BASE, "--", f) if f in tracked else ""
        added += [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")] if diff else path.read_text(encoding="utf-8").splitlines()
    texts = added + ([Path(ARGS[1]).read_text(encoding="utf-8")] if len(ARGS) > 1 else [])
    keys = sum(bool(re.search(r"sk-[A-Za-z0-9_-]{16,}", t)) for t in texts)
    names = sum(any(w in t for w in words) for t in texts)
    key_paths = ("marcspon-" + "openai", "spike/" + ".env")  # 이 줄 자신이 걸리지 않게 쪼갠 글자
    files = sum(any(k in t for k in key_paths) for t in texts)
    print(f"  key_like={keys} forbidden_word_lines={names} words={len(words)} key_files={files} added_lines={len(added)}")
    sys.exit(0 if keys == 0 and names == 0 and files == 0 and words else 1)

if CMD == "trailers":
    text = Path(ARGS[0]).read_text(encoding="utf-8")
    need = [
        "Ticket: MARC-TICK-365",
        "Concerns: MARC-ISSUE-413",
        "Constraint: 장부 cost_usd 는 실비만 — 어림은 상한 셈 칸과 dry-run 위끝에만(MARC-ENT-262)",
        "Directive: 실행 상한의 어림은 보수 쪽으로만 바꾼다 — 판정이 늦어지는 고침은 감독에게 먼저(MARC-ENT-442)",
        "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
    ]
    if COMMIT >= 2:
        need.append("Concerns: MARC-ISSUE-417")
    missing = [n for n in need if n not in text]
    print(f"  빠진 트레일러 {missing}")
    sys.exit(0 if not missing else 1)

sys.exit(f"모르는 CMD {CMD}")
PY
helper() { (cd "$ROOT" && python3 -I "$HELPER" "$ROOT" "$BASE" "$COMMIT" "$@"); }

if want 1; then
  helper paths > "$S4/1.log" 2>&1; e=$?; cat "$S4/1.log"; report 1 "허용 경로·0줄·C0 밖 지운 줄·독스트링만·받아들임 문장" "$e"
fi

if want 2; then
  e=0
  api lint-imports > "$S4/2a.log" 2>&1 || e=1
  api lint-imports --config esgapi/core/llm/purity.importlinter > "$S4/2b.log" 2>&1 || e=1
  a=$(grep "Contracts:" "$S4/2a.log"); b=$(grep "Contracts:" "$S4/2b.log")
  echo "  저장소 $a · 순수 $b"
  case "$a" in *"18 kept, 0 broken"*) ;; *) e=1 ;; esac
  case "$b" in *"1 kept, 0 broken"*) ;; *) e=1 ;; esac
  n=$(cd "$ROOT" && git grep -nE "^\s*(import celery|from celery)|import billiard|from billiard" -- apps/api-py/esgapi/core/llm | wc -l | tr -d ' ')
  echo "  core/llm 의 celery·billiard import $n"
  [ "$n" = "0" ] || e=1
  # 양성 대조: 같은 정규식이 runs/tasks.py 의 celery import 는 잡는다
  m=$(cd "$ROOT" && git grep -nE "^\s*(import celery|from celery)|import billiard|from billiard" -- apps/api-py/esgapi/runs/tasks.py | wc -l | tr -d ' ')
  echo "  양성 대조(runs/tasks.py) $m"
  [ "$m" -ge 1 ] || e=1
  report 2 "lint-imports(BASE 18·1 그대로)·celery import 0" "$e"
fi

if want 3; then
  api pytest -q -p no:cacheprovider -m "not django_db" esgapi/core/tests esgapi/config/tests esgapi/runs/tests > "$S4/3.log" 2>&1; e=$?
  echo "  N1=$(tail -1 "$S4/3.log")"
  report 3 "core·config·runs 순수" "$e"
fi

if want 4; then
  api pytest -q -p no:cacheprovider -m "not django_db" esgapi > "$S4/4.log" 2>&1; e=$?
  echo "  $(tail -1 "$S4/4.log")"; grep "^FAILED" "$S4/4.log"
  report 4 "모듈 순수 전부" "$e"
fi

if want 5; then
  e=0
  api python scripts/check_test_layout.py > "$S4/5a.log" 2>&1 || e=1; tail -1 "$S4/5a.log"
  api pyright esgapi/core/llm esgapi/core/management esgapi/core/service esgapi/runs esgapi/core/tests > "$S4/5b.log" 2>&1 || e=1; tail -1 "$S4/5b.log"
  api ruff check . > "$S4/5c.log" 2>&1 || e=1; tail -1 "$S4/5c.log"
  api ruff format --check . > "$S4/5d.log" 2>&1 || e=1; tail -1 "$S4/5d.log"
  report 5 "자리·pyright·ruff" "$e"
fi

if want 6; then
  if [ -n "$MSG" ]; then helper secrets "$FORBIDDEN" "$MSG" > "$S4/6.log" 2>&1; else helper secrets "$FORBIDDEN" > "$S4/6.log" 2>&1; fi
  e=$?; cat "$S4/6.log"; report 6 "금지 글·키 꼴·키 파일 이름" "$e"
fi

if want 7; then
  api pytest -q -p no:cacheprovider esgapi/core/tests/llm/test_client_bytes_unchanged.py > "$S4/7.log" 2>&1; e=$?
  echo "  $(tail -1 "$S4/7.log")"
  report 7 "test_client_bytes_unchanged(★f)" "$e"
fi

if want 8; then
  if [ -n "$WITH_CONTAINERS" ]; then
    e=0
    start=$(date +%s)
    (cd "$API_PY" && $ENVX scripts/test-business.sh -p no:cacheprovider -n 4 esgapi) > "$S4/8a.log" 2>&1 || e=1
    echo "  업무 $(tail -1 "$S4/8a.log") $(( $(date +%s) - start ))s"
    start=$(date +%s)
    (cd "$API_PY" && $ENVX scripts/test-security.sh -p no:cacheprovider) > "$S4/8b.log" 2>&1 || e=1
    echo "  보안 $(tail -1 "$S4/8b.log") $(( $(date +%s) - start ))s"
    report 8 "업무(esgapi 전부)·보안 층" "$e"
  else
    report 8 "업무·보안 층(안 돌림 — --with-containers 없음)" 1
  fi
fi

if want 9 && [ -n "$PLANTED" ]; then
  S4_OUT="$OUT" "$API_PY/scripts/planted-breaks-LH3.sh" "$COMMIT" ${WITH_CONTAINERS:+--with-containers} > "$S4/9.log" 2>&1; e=$?
  grep -E "=> |^P0=|^FINGERPRINT=|^PLANTED=" "$S4/9.log"
  report 9 "심은 파손" "$e"
fi

if want 10 && [ -n "$MSG" ]; then
  helper trailers "$MSG" > "$S4/10.log" 2>&1; e=$?; cat "$S4/10.log"; report 10 "트레일러" "$e"
fi

if want 11; then
  (cd "$ROOT" && $ENVX scripts/verify.sh --fast) > "$S4/11.log" 2>&1; e=$?
  tail -1 "$S4/11.log"
  grep -q "^VERIFY_FAST=PASS" "$S4/11.log" || e=1
  report 11 "verify.sh --fast" "$e"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = "0" ]
