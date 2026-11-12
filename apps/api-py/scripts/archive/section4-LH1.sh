#!/usr/bin/env bash
# 밴드 LH1 의 §4 자기검증(발주서 band-handoffs/LH1-order.md §4 — RX1a 의 section4-RX1a.sh 꼴). 줄마다 [n] … EXIT= 를 찍고
# 끝 줄 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-LH1.sh [--commit 1|2] [--with-containers] [--planted] [--msg <파일>] [--step 1,2,…]
#     --commit n          경계(기본 2). 1 이면 ① 의 허용 경로로 보고 7(live 셸 — ② 의 S12 가 필요)을 뺀다
#     --with-containers   8 업무 층 전부(test-business.sh esgapi)·보안 층
#     --planted           9 심은 파손(PLANTED=<잡음>/<경계 ① 13 · ② 17>)
#     --msg <파일>        10 커밋 메시지 초안의 트레일러
# 단계: 1 허용 경로·0줄·C0 표 밖 지운 줄·generated 0·dataverify 한 줄 · 2 lint-imports 둘 · 3 core·config·runs 순수(N1) ·
#   4 모듈 순수 전부 · 5 시험 자리·pyright·ruff · 6 금지 글 · 7 live 셸 · 8 업무·보안 · 9 심은 파손 · 10 트레일러 ·
#   11 scripts/verify.sh --fast.
# 환경 변수: S4_OUT(기본 워크트리 곁의 LH1.out) · LH1_BASE(기본 1b7484bc).
# 컨테이너는 띄우지 않는다(compose esg-app-lh1 의 postgres 가 떠 있어야 한다 — 8·9). 공급사를 부르지 않는다: 모든 pytest
# 는 발주서의 ENVX(키 변수 다섯·LLM_RUN_MODE 를 지운 환경). 7 만 LLM_RUN_MODE=live 를 일부러 둔다(키는 없음).
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${LH1_BASE:-1b7484bc}"
OUT="${S4_OUT:-$SIDE/LH1.out}"
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

HELPER="$S4/lh1_helper.py"
cat > "$HELPER" <<'PY'
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT, BASE, COMMIT, CMD, ARGS = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5:]
P = r"^apps/api-py/"
E = P + r"esgapi/"
DV = "apps/api-py/esgapi/dataverify/tests/flows/test_colab_156.py"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def changed() -> set[str]:
    return set(git("diff", "--name-only", BASE).split()) | set(git("ls-files", "--others", "--exclude-standard").split())


ALLOWED_1 = [
    E + r"core/llm/providers/(openai|anthropic|gemini)\.py$",
    E + r"core/llm/(retry|client|types|setup|embedding)\.py$",
    E + r"config/env\.py$",
    E + r"core/tests/test_llm_(adapters|retry|command|client)\.py$",
    E + r"core/tests/llm/test_(sdk_retries|dry_run_worst)\.py$",
    E + r"core/tests/llm/providers/",
    E + r"core/tests/llm/test_client_bytes_unchanged\.py$",  # 감독 e5 10-28 「C0 물을 거리 1 (가)」
    E + r"config/tests/test_env\.py$",
    E + r"runs/tests/test_context_live\.py$",
    E + r"dataverify/tests/flows/test_colab_156\.py$",
    # ② 의 스크립트 둘은 ① 동안 추적 밖(커밋하지 않음)으로 쓰인다
    P + r"scripts/(section4|planted-breaks)-LH1\.sh$",
]
ALLOWED_2 = [
    E + r"core/flows/binding\.py$",
    E + r"runs/context\.py$",
    E + r"runs/service/actions/runs\.py$",
    E + r"runs/calc/idempotency\.py$",
    E + r"config/settings/test_(business|security)\.py$",
    E + r"runs/tests/test_executor\.py$",
    E + r"runs/tests/test_context_sum\.py$",
    E + r"runs/tests/service/apis/test_runs_surrogate\.py$",
    E + r"runs/tests/calc/",
]
ZERO = [
    E + r"(greenwash|translation|materiality|inventory|reconcile|reference)/",
    E + r"dataverify/(?!tests/flows/test_colab_156\.py$)",
    E + r"core/llm/(log|sink_db|cost|config|prompts|throttle|embedding_types|errors|schema)\.py$",
    E + r"core/llm/purity\.importlinter$", E + r"core/resources/",
    E + r"runs/(tasks|models)\.py$", E + r"(\w+/)?migrations/", E + r"\w+/service/apis/",
    P + r"tests/support/", r"(^|/)conftest\.py$", P + r"\.importlinter$",
    r"^scripts/verify\.sh$", P + r"scripts/planted-breaks\.sh$", r"^infra/", r"^compose\.yaml$", r"^docs/",
    r"(^|/)README\.md$", P + r"generated/", r"^apps/web/", P + r"(pyproject\.toml|uv\.lock)$", E + r"config/api\.py$",
    r"/schemas?(\.py$|/)",
]
# 시험 파일에서 지워도 되는 줄(C0 표 + 감독 「C0 통과」 — 보고 「C0 줄 표」). 그 밖 시험 파일의 ^- 는 0.
MINUS_OK = {
    "apps/api-py/esgapi/core/tests/llm/test_client_bytes_unchanged.py": {
        "from typing import Any",
        '            out[f"dry_run.{name}"] = sha256_json(client.dry_run(call).to_json())',
    },
    "apps/api-py/esgapi/core/tests/test_llm_adapters.py": {
        "from esgapi.core.llm.providers.openai import OpenAIProvider, create_openai_client",
        "    # SDK 의 자체 재시도 기본값(2회)을 그대로 둔다. retry.py 가 이 값에 기대어 openai·anthropic 을 다시 부르지 않는다.",
        "    assert (made_openai.max_retries, made_anthropic.max_retries) == (2, 2)",
    },
    "apps/api-py/esgapi/core/tests/test_llm_retry.py": {
        "def test_default_retries_only_gemini_twice_from_one_second_doubling_capped_at_sixty() -> None:",
        '    assert {"gemini": RetryPolicy(max_retries=2, base_delay_ms=1_000, max_delay_ms=60_000)} == DEFAULT_PROVIDER_RETRY',
        "def test_by_default_only_gemini_is_retried_by_the_call_layer(prompt_root: Path) -> None:",
        '    """모의 공급사와, SDK 가 스스로 다시 부르는 openai·anthropic 은 호출 층이 다시 부르지 않는다."""',
        '        provider = MockProvider(name).enqueue(ProviderError(status=429, retryable=True, message="한도"))',
        '        provider.enqueue_text("ok")',
        "        assert len(provider.calls) == 1",
    },
    DV: {
        '    assert unknown["perStage"]["review"]["maxProviderCalls"] == 36  # openai 는 같은 모델 재시도가 없다',
    },
    "apps/api-py/esgapi/runs/tests/test_context_live.py": {
        "  오류 갈래   (Q6 — BASE 그대로를 박는다) 429 두 번 뒤 200 · 429 계속 · 500 · 401 · 시간 초과 × 대화·임베딩",
        "★ SDK 의 재시도(max_retries 기본 2)는 그대로 둔다. 기다림은 가짜 응답의 retry-after-ms(1ms)로 짧게, 시간 초과는 SDK 의",
        "  물러섬(약 0.4~1.5초)을 그대로 탄다.",
        "# ── 오류 갈래(Q6 — BASE 그대로) ─────────────────────────────────────────",
        '    ("reply", "kind", "error_status", "retryable", "requests"),',
        '        pytest.param(status(429, times=2), "success", None, None, 3, id="429-twice-then-200"),',
        '        pytest.param(status(429), "provider_error", 429, True, 3, id="429-always"),',
        '        pytest.param(status(500), "provider_error", 500, True, 3, id="500-always"),',
        '        pytest.param(status(401), "provider_error", 401, False, 1, id="401"),',
        '        pytest.param(timeout, "timeout", None, None, 3, id="timeout"),',
        '    """대화의 실패는 결과 갈래로 돌아온다(단계가 정함 — 이 흐름은 계속해 done). 기록 줄 하나, SDK 재시도는 요청 수."""',
        "    (line,) = lines(world, run_id)",
        "    assert (line.result_kind, line.error_status) == (kind, error_status)",
        '    assert line.cost_usd == (Decimal(str(CHAT_USD)) if kind == "success" else None)',
    },
    "apps/api-py/esgapi/runs/tests/test_executor.py": {
        "    assert (ctx.company_id, ctx.run_id, ctx.module, ctx.flow_id, ctx.attempt, ctx.dry_run) == (",
        "        False,",
    },
}

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
    numstat = git("diff", "--numstat", BASE, "--", DV).split()[:2]
    dv_diff = git("diff", BASE, "--", DV).encode()
    dv_ok = numstat == ["1", "1"]
    print(f"  바뀐 파일 {len(files)} · outside={len(outside)} {outside}")
    print(f"  0줄 경로 {zero} · generated {[f for f in files if '/generated/' in f]}")
    print(f"  C0 밖 지운 줄 {len(bad_minus)}")
    for line in bad_minus:
        print(f"    {line}")
    print(f"  dataverify numstat={numstat} diff_sha256_16={hashlib.sha256(dv_diff).hexdigest()[:16]}")
    sys.exit(0 if not outside and not zero and not bad_minus and dv_ok else 1)

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
        "Ticket: MARC-TICK-355",
        "Concerns: MARC-ISSUE-306",
        "Constraint: 공급사로 나간 HTTP 요청은 전부 기록 한 줄과 상한 확인을 지난다 — SDK 재시도 0(MARC-ENT-262)",
        "Directive: openai·anthropic SDK 의 max_retries 를 0 밖으로 올리지 않는다 — 재시도는 retry.py 표로",
        "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
    ]
    need += ["Concerns: MARC-ISSUE-167"] if COMMIT == 1 else ["Concerns: MARC-ISSUE-340"]
    wrong = ["Concerns: MARC-ISSUE-340"] if COMMIT == 1 else ["Concerns: MARC-ISSUE-167"]
    missing = [n for n in need if n not in text]
    extra = [n for n in wrong if n in text]
    print(f"  빠진 트레일러 {missing} · 그 경계 밖 {extra}")
    sys.exit(0 if not missing and not extra else 1)

sys.exit(f"모르는 CMD {CMD}")
PY
helper() { (cd "$ROOT" && python3 -I "$HELPER" "$ROOT" "$BASE" "$COMMIT" "$@"); }

if want 1; then
  helper paths > "$S4/1.log" 2>&1; e=$?; cat "$S4/1.log"; report 1 "허용 경로·0줄·C0 밖 지운 줄·dataverify 한 줄" "$e"
fi

if want 2; then
  e=0
  api lint-imports > "$S4/2a.log" 2>&1 || e=1
  api lint-imports --config esgapi/core/llm/purity.importlinter > "$S4/2b.log" 2>&1 || e=1
  a=$(grep "Contracts:" "$S4/2a.log"); b=$(grep "Contracts:" "$S4/2b.log")
  echo "  저장소 $a · 순수 $b"
  case "$a" in *"18 kept, 0 broken"*) ;; *) e=1 ;; esac
  case "$b" in *"1 kept, 0 broken"*) ;; *) e=1 ;; esac
  report 2 "lint-imports(BASE 18·1 그대로)" "$e"
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
  api pyright esgapi/core/llm esgapi/core/flows esgapi/runs esgapi/config esgapi/core/tests > "$S4/5b.log" 2>&1 || e=1; tail -1 "$S4/5b.log"
  api ruff check . > "$S4/5c.log" 2>&1 || e=1; tail -1 "$S4/5c.log"
  api ruff format --check . > "$S4/5d.log" 2>&1 || e=1; tail -1 "$S4/5d.log"
  report 5 "자리·pyright·ruff" "$e"
fi

if want 6; then
  if [ -n "$MSG" ]; then helper secrets "$FORBIDDEN" "$MSG" > "$S4/6.log" 2>&1; else helper secrets "$FORBIDDEN" > "$S4/6.log" 2>&1; fi
  e=$?; cat "$S4/6.log"; report 6 "금지 글·키 꼴·키 파일 이름" "$e"
fi

if want 7 && [ "$COMMIT" -ge 2 ]; then
  # 발주서 §4-7: live 를 일부러 둔 셸(키 없음). 시험 설정이 LLM_RUN_MODE 를 지워 모의로 돈다.
  (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY \
     -u LLM_GEMINI_API_KEY LLM_RUN_MODE=live LLM_RUN_MAX_USD=0.01 uv run --frozen pytest -q -p no:cacheprovider -m "not django_db" \
     esgapi/runs/tests/test_context_sum.py esgapi/core/tests/test_llm_client.py) > "$S4/7.log" 2>&1; e=$?
  echo "  $(tail -1 "$S4/7.log")"
  report 7 "live 셸(키 없음)" "$e"
fi

if want 8; then
  if [ -n "$WITH_CONTAINERS" ]; then
    e=0
    start=$(date +%s)
    (cd "$API_PY" && $ENVX scripts/test-business.sh -p no:cacheprovider -n 2 esgapi) > "$S4/8a.log" 2>&1 || e=1
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
  S4_OUT="$OUT" "$API_PY/scripts/planted-breaks-LH1.sh" "$COMMIT" ${WITH_CONTAINERS:+--with-containers} > "$S4/9.log" 2>&1; e=$?
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
