#!/usr/bin/env bash
# 밴드 LH2 의 §4 자기검증(발주서 band-handoffs/LH2-order.md §4 — section4-LH1.sh 꼴). 줄마다 [n] … EXIT= 를 찍고
# 끝 줄 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-LH2.sh [--commit 1|2] [--with-containers] [--planted] [--msg <파일>] [--step 1,2,…]
#     --commit n          경계(기본 2). 1 이면 ① 의 허용 경로로 본다
#     --with-containers   8 업무 층 전부(test-business.sh esgapi)·보안 층
#     --planted           9 심은 파손(PLANTED=<잡음>/<경계 ① 6 · ② 28>)
#     --msg <파일>        10 커밋 메시지 초안의 트레일러
# 단계: 1 허용 경로·0줄·C0 표 밖 지운 줄·generated 0·runs/tasks.py 는 주석만 · 2 lint-imports 둘·core/llm 의 celery·billiard
#   import 0 · 3 core·config·runs 순수(N1) ·
#   4 모듈 순수 전부 · 5 시험 자리·pyright·ruff · 6 금지 글 · 7 live 셸 · 8 업무·보안 · 9 심은 파손 · 10 트레일러 ·
#   11 scripts/verify.sh --fast.
# 환경 변수: S4_OUT(기본 워크트리 곁의 LH2.out) · LH2_BASE(기본 0d893312).
# 컨테이너는 띄우지 않는다(compose esg-app-lh2 의 postgres 가 떠 있어야 한다 — 8·9). 공급사를 부르지 않는다: 모든 pytest
# 는 발주서의 ENVX(키 변수 다섯·LLM_RUN_MODE 를 지운 환경). 7 만 LLM_RUN_MODE=live 를 일부러 둔다(키는 없음).
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${LH2_BASE:-0d893312}"
OUT="${S4_OUT:-$SIDE/LH2.out}"
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

HELPER="$S4/lh2_helper.py"
cat > "$HELPER" <<'PY'
import hashlib
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
    E + r"core/llm/(setup|__init__)\.py$",
    E + r"core/management/commands/llm_call\.py$",
    E + r"core/tests/llm/test_process_client\.py$",
    E + r"core/tests/test_llm_command\.py$",
    # ② 의 스크립트 둘은 ① 동안 추적 밖이다
    P + r"scripts/(section4|planted-breaks)-LH2\.sh$",
]
ALLOWED_2 = [
    E + r"core/llm/(client|embedding|log|errors|types)\.py$",
    E + r"core/llm/providers/(openai|anthropic|gemini)\.py$",
    E + r"runs/(context|tasks)\.py$",
    E + r"config/env\.py$",
    E + r"core/tests/llm/test_(cost_bound|soft_deadline)\.py$",
    E + r"runs/tests/test_context_bound\.py$",
    E + r"core/tests/test_llm_adapters\.py$",
    E + r"core/tests/llm/providers/test_openai_embedding\.py$",
    E + r"runs/tests/test_executor\.py$",  # :425-451 한 시험 — C0 밖, 감독 허락 10-28
]
ZERO = [
    E + r"(greenwash|translation|dataverify|materiality|inventory|reconcile|reference|runbundle)/",
    E + r"core/llm/(budget|cost|config|prompts|throttle|embedding_types|schema|retry|sink_db)\.py$",
    E + r"core/llm/sinks/", E + r"core/llm/purity\.importlinter$", E + r"core/resources/", E + r"core/flows/",
    E + r"config/settings/", E + r"runs/models\.py$", E + r"(\w+/)?migrations/", E + r"\w+/service/apis/",
    P + r"tests/", r"(^|/)conftest\.py$", P + r"\.importlinter$",
    r"^scripts/verify\.sh$", P + r"scripts/planted-breaks\.sh$", r"^infra/", r"^compose\.yaml$", r"^docs/",
    r"(^|/)README\.md$", P + r"generated/", r"^apps/web/", P + r"(pyproject\.toml|uv\.lock)$", E + r"config/api\.py$",
    r"/schemas?(\.py$|/)",
]
# 시험 파일에서 지워도 되는 줄(C0 표 + 감독 「C0 통과」). 그 밖 시험 파일의 ^- 는 0.
MINUS_OK = {
    "apps/api-py/esgapi/core/tests/test_llm_command.py": {"from esgapi.config.env import LlmSettings"},
    # C0 밖 — 감독 허락 10-28(BASE 의 「삼켜진다」 고정 시험 한 개를 S3 의 새값으로)
    "apps/api-py/esgapi/runs/tests/test_executor.py": {
        "def test_a_soft_limit_inside_the_llm_call_is_swallowed_into_a_provider_error(world: World) -> None:",
        '    """위험의 고정: core/llm 의 _invoke 가 `except Exception` 으로 삼켜 공급사 오류 값이 된다',
        '    (그래서 주 길은 협조 마감)."""',
        '    assert world.script.llm_results == ["provider_error"]',
        '    assert row(world, run_id).status == "done"  # 삼켜져 단계가 그대로 이어 갔다',
    },
}
TASKS = "apps/api-py/esgapi/runs/tasks.py"

if CMD == "paths":
    files = sorted(changed())
    allowed = ALLOWED_1 + (ALLOWED_2 if COMMIT >= 2 else [])
    outside = [f for f in files if not any(re.search(p, f) for p in allowed)]
    zero = [f for f in files if any(re.search(p, f) for p in ZERO)]
    bad_minus = []
    for f in files:
        if "/tests/" not in f or f not in set(git("ls-files").split()):
            continue
        minus = [l[1:] for l in git("diff", BASE, "--", f).splitlines() if l.startswith("-") and not l.startswith("---")]
        bad_minus += [f"{f}: {l}" for l in minus if l not in MINUS_OK.get(f, set())]
    tasks_lines = [l for l in git("diff", "-U0", BASE, "--", TASKS).splitlines()
                   if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    # 머리말(모듈 독스트링) 안의 글만: 바뀐 줄이 전부 독스트링 들여쓰기 글이어야 한다(코드 0 — M5)
    base_text = git("show", f"{BASE}:{TASKS}")
    doc_end = base_text.index('"""', base_text.index('"""') + 3)
    hunks = re.findall(r"^@@ -(\d+)", git("diff", "-U0", BASE, "--", TASKS), flags=re.M)
    base_doc_lines = base_text[:doc_end].count("\n") + 1
    tasks_ok = all(int(h) <= base_doc_lines for h in hunks)
    print(f"  바뀐 파일 {len(files)} · outside={len(outside)} {outside}")
    print(f"  0줄 경로 {zero} · generated {[f for f in files if '/generated/' in f]}")
    print(f"  C0 밖 지운 줄 {len(bad_minus)}")
    for line in bad_minus:
        print(f"    {line}")
    print(f"  runs/tasks.py 바뀐 줄 {len(tasks_lines)} · 머리말 안 {tasks_ok} (머리말 {base_doc_lines} 줄)")
    sys.exit(0 if not outside and not zero and not bad_minus and tasks_ok else 1)

if CMD == "secrets":
    words = [w.strip() for w in Path(ARGS[0]).read_text(encoding="utf-8").splitlines() if w.strip()]
    added: list[str] = []
    for f in sorted(changed()):
        path = ROOT / f
        if not path.is_file():
            continue
        diff = git("diff", BASE, "--", f) if f in set(git("ls-files").split()) else ""
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
        "Ticket: MARC-TICK-356",
        "Concerns: MARC-ISSUE-411",
        "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
    ]
    one = [
        "Constraint: 공급사 키는 상한이 있는 길(실행기·llm_call --limit-usd)에서만 실린다 — 서버 요청 길 실호출 0(MARC-ENT-262)",
        "Directive: llm_client() 에 키를 다시 싣지 않는다 — 서버 요청 길에서 실호출이 필요하면 상한을 먼저 세운다",
    ]
    two = [
        "Constraint: 장부 cost_usd 는 실비만 — 실패 시도의 어림은 상한 셈 전용 칸",
        "Directive: SoftTimeLimitExceeded 는 호출 층에서 삼키지 않는다",
    ]
    need += one if COMMIT == 1 else two
    wrong = two if COMMIT == 1 else one
    missing = [n for n in need if n not in text]
    extra = [n for n in wrong if n in text]
    print(f"  빠진 트레일러 {missing} · 그 경계 밖 {extra}")
    sys.exit(0 if not missing and not extra else 1)

sys.exit(f"모르는 CMD {CMD}")
PY
helper() { (cd "$ROOT" && python3 -I "$HELPER" "$ROOT" "$BASE" "$COMMIT" "$@"); }

if want 1; then
  helper paths > "$S4/1.log" 2>&1; e=$?; cat "$S4/1.log"; report 1 "허용 경로·0줄·C0 밖 지운 줄·runs/tasks.py 머리말만" "$e"
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
  api pyright esgapi/core/llm esgapi/core/management esgapi/runs esgapi/config esgapi/core/tests > "$S4/5b.log" 2>&1 || e=1; tail -1 "$S4/5b.log"
  api ruff check . > "$S4/5c.log" 2>&1 || e=1; tail -1 "$S4/5c.log"
  api ruff format --check . > "$S4/5d.log" 2>&1 || e=1; tail -1 "$S4/5d.log"
  report 5 "자리·pyright·ruff" "$e"
fi

if want 6; then
  if [ -n "$MSG" ]; then helper secrets "$FORBIDDEN" "$MSG" > "$S4/6.log" 2>&1; else helper secrets "$FORBIDDEN" > "$S4/6.log" 2>&1; fi
  e=$?; cat "$S4/6.log"; report 6 "금지 글·키 꼴·키 파일 이름" "$e"
fi

if want 7; then
  # 발주서 §4-7(m6): live 와 SDK 주소를 일부러 둔 셸(키 없음). 모드 갈래는 이음매로 잰다. 소켓 시도는 시험이 센다.
  (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY \
     -u LLM_GEMINI_API_KEY LLM_RUN_MODE=live OPENAI_BASE_URL=http://127.0.0.1:9 uv run --frozen pytest -q -p no:cacheprovider \
     -m "not django_db" esgapi/core/tests/llm/test_process_client.py esgapi/core/tests/test_llm_command.py) > "$S4/7.log" 2>&1; e=$?
  echo "  $(tail -1 "$S4/7.log")"
  report 7 "live 셸(키 없음)" "$e"
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
  S4_OUT="$OUT" "$API_PY/scripts/planted-breaks-LH2.sh" "$COMMIT" ${WITH_CONTAINERS:+--with-containers} > "$S4/9.log" 2>&1; e=$?
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
