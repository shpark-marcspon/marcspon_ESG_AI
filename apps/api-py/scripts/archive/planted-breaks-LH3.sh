#!/usr/bin/env bash
# 밴드 LH3 의 심은 파손(발주서 band-handoffs/LH3-order.md §3-1 — P1~P17, 분모 ① 8 · ② 17). LH2 의 꼴 그대로: 하나씩 심고
# 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다.
# INT·TERM 도 되쓰기를 지난다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-LH3.sh <1|2> [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 시험(이름 — 매개 변수 갈래는 하나라도)이 전부 FAILED·ERROR 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다).
# PLANTED 는 P 단위로 센다 — 경계 ① 은 P1~P8(8), 경계 ② 는 17 전부.
# 업무 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 끝에 심은 파일의 sha256 이 시작과 같은지(cmp), git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: S4_OUT(기본: 워크트리 곁의 LH3.out)/planted-<경계>/. 공급사를 부르지 않는다(키 변수·LLM_RUN_MODE 를 지운 채 —
# 발주서 ENVX). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${S4_OUT:-$(cd "$ROOT/.." && pwd)/LH3.out}"
case "${1:-}" in 1|2) BOUNDARY="$1"; shift ;; *) echo "첫 인자는 경계(1|2)"; exit 2 ;; esac
mkdir -p "$OUT/planted-$BOUNDARY"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY \
  -u LLM_RUN_MODE uv run --frozen python - "$OUT/planted-$BOUNDARY" "$BOUNDARY" "$@" <<'PY'
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
BOUNDARY = int(sys.argv[2])
args = sys.argv[3:]
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def interrupted(signum, _frame):  # INT·TERM 도 finally(되쓰기)를 지나게
    raise KeyboardInterrupt(f"signal {signum}")


signal.signal(signal.SIGINT, interrupted)
signal.signal(signal.SIGTERM, interrupted)


def swap(old: str, new: str, count: int = 1) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new) if text.count(old) == count else None

    return plant


LLM = "esgapi/core/llm/"
CLIENT = Path(LLM + "client.py")
EMBEDDING = Path(LLM + "embedding.py")
OPENAI = Path(LLM + "providers/openai.py")
ANTHROPIC = Path(LLM + "providers/anthropic.py")
GEMINI = Path(LLM + "providers/gemini.py")

T_SENT = "esgapi/core/tests/llm/test_lh3_sent.py"
T_SOFTW = "esgapi/core/tests/llm/test_lh3_soft_write.py"
T_RUN = "esgapi/runs/tests/test_context_bound.py"
T_BOUNDS = "esgapi/core/tests/llm/test_lh3_bounds.py"
T_CMD = "esgapi/core/tests/test_llm_command.py"
T_EMB = "esgapi/core/tests/llm/providers/test_openai_embedding.py"
T_BYTES = "esgapi/core/tests/llm/test_client_bytes_unchanged.py"
SETUP = Path(LLM + "setup.py")
CALL = Path("esgapi/core/management/commands/llm_call.py")

T2_CHAT = T_SOFTW + "::test_t2_client_raises_the_soft_limit_even_when_the_line_cannot_be_written"
T2_EMBED = T_SOFTW + "::test_t2_embedding_raises_the_soft_limit_even_when_the_line_cannot_be_written"
T2_RUN = T_RUN + "::test_a_soft_limit_whose_line_cannot_be_written_still_defers_the_run"
T3_BASE = T_SENT + "::test_t3_an_assembly_error_is_not_sent_and_keeps_the_base_values"
T3_LINE = T_SENT + "::test_t3_the_client_line_of_an_assembly_error_has_no_bound"
T4_FEE = T_BOUNDS + "::test_t4_a_failed_web_search_attempt_adds_the_per_call_fee"
T5_REAL = T_CMD + "::test_lh3_a_real_route_only_in_the_models_file_is_judged_live"
T5_MOCK = T_CMD + "::test_lh3_the_mock_route_still_works_with_a_models_file_that_has_none"
T6_BOUND = T_BOUNDS + "::test_t6_a_success_without_tokens_carries_the_conservative_bound"
T6_LIMIT = T_BOUNDS + "::test_t6_two_successes_without_tokens_reach_the_limit_before_the_third"
T6_ADAPTER = T_EMB + "::test_an_answer_without_usage_reports_no_tokens_and_is_recorded_without_cost"
T7_DEAR = T_BOUNDS + "::test_t7_cached_requests_on_a_dearer_write_model_bound_the_cache_at_the_write_rate"
T7_CHEAP = T_BOUNDS + "::test_t7_a_cheaper_write_rate_never_lowers_the_bound"
T7_FAIL = T_BOUNDS + "::test_t7_the_failed_attempt_bound_adds_the_write_premium_on_the_cache_share"
BYTES = T_BYTES + "::test_requests_records_and_dry_runs_without_tools_match_the_baseline_commit"

PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rfE", "-p", "no:cacheprovider"], True)

CHAT_GUARD = '                    except Exception as write_error:\n                        logger.warning("LLM 소프트'
EMBED_GUARD = '                    except Exception as write_error:\n                        logger.warning("임베딩 소프트'
CHAT_LOG = '                        logger.warning("LLM 소프트 제한 뒤 기록 실패 %s", type(write_error).__name__)\n'


def swap(old: str, new: str, count: int = 1) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new) if text.count(old) == count else None

    return plant


# (번호, 경계, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 시험 이름들)])
PLANTS = [
    ("P1", 1, "client soft limit 갈래의 기록 감싸기 지움",
     [(CLIENT, swap(CHAT_GUARD, CHAT_GUARD.replace("except Exception", "except ZeroDivisionError")))],
     [(PURE, [T_SOFTW], {T2_CHAT}), (BUSINESS, [T_RUN], {T2_RUN})]),
    ("P2", 1, "embedding soft limit 갈래의 기록 감싸기 지움",
     [(EMBEDDING, swap(EMBED_GUARD, EMBED_GUARD.replace("except Exception", "except ZeroDivisionError")))],
     [(PURE, [T_SOFTW], {T2_EMBED})]),
    ("P3", 1, "기록 예외를 다시 던짐(client)",
     [(CLIENT, swap(CHAT_LOG, CHAT_LOG + "                        raise\n"))],
     [(PURE, [T_SOFTW], {T2_CHAT})]),
    ("P4", 1, "openai 조립 sent=False 지움",
     [(OPENAI, swap("            return _unsent(error)\n        try:\n            response = self._client.responses",
                    "            return _map_error(error)\n        try:\n            response = self._client.responses"))],
     [(PURE, [T_SENT], {T3_BASE, T3_LINE})]),
    ("P5", 1, "anthropic 조립 sent=False 지움",
     [(ANTHROPIC, swap("            return _unsent(error)\n", "            return _map_error(error)\n"))],
     [(PURE, [T_SENT], {T3_BASE})]),
    ("P6", 1, "gemini 조립 sent=False 지움",
     [(GEMINI, swap("            return _unsent(error)\n", "            return _map_error(error)\n"))],
     [(PURE, [T_SENT], {T3_BASE})]),
    ("P7", 1, "openai 임베딩 조립 sent=False 지움",
     [(OPENAI, swap("            unsent = _unsent(error)\n", "            unsent = _map_error(error)\n"))],
     [(PURE, [T_SENT], {T3_BASE})]),
    ("P8", 1, "조립 오류 message 바꿈(BASE 값)",
     [(OPENAI, swap("    return replace(mapped, sent=False) if isinstance",
                    '    return replace(mapped, sent=False, message="조립") if isinstance'))],
     [(PURE, [T_SENT], {T3_BASE})]),
    ("P9", 2, "web_search 몫 지움",
     [(CLIENT, swap("            searches = 1 if provider_request.max_hosted_calls is None else provider_request.max_hosted_calls\n",
                    "            searches = 0\n"))],
     [(PURE, [T_BOUNDS], {T4_FEE})]),
    ("P10", 2, "(가-2) None 이면 1건 지움(0건)",
     [(CLIENT, swap("searches = 1 if provider_request.max_hosted_calls is None", "searches = 0 if provider_request.max_hosted_calls is None"))],
     [(PURE, [T_BOUNDS], {T4_FEE})]),
    ("P11", 2, "llm_call 판단을 패키지 파일만(BASE)",
     [(CALL, swap("load_config(config_sources(settings, mock=True))",
                  "load_config(config_sources(dataclasses.replace(settings, models_file=None), mock=True))"))],
     [(PURE, [T_CMD], {T5_REAL})]),
    ("P12", 2, "config_sources 의 mock 가상 파일 붙임 지움",
     [(SETUP, swap("    return (*sources, *default_config_sources(synthetic=True)[1:]) if mock else sources\n",
                   "    return sources\n"))],
     [(PURE, [T_CMD], {T5_MOCK})]),
    ("P13", 2, "임베딩 토큰 없음 어림 지움",
     [(EMBEDDING, swap("cost_bound_usd=self._worst_usd(batch, model) if tokens is None else None,", "cost_bound_usd=None,"))],
     [(PURE, [T_BOUNDS, T_EMB], {T6_BOUND, T6_LIMIT, T6_ADAPTER})]),
    ("P14", 2, "dry_run 할증 지움(cost_upper_bound_usd)",
     [(CLIENT, swap("cost_upper_bound_usd=_bound_usd(upper_bound, cached, model.pricing),",
                    "cost_upper_bound_usd=compute_cost_usd(upper_bound, model.pricing),"))],
     [(PURE, [T_BOUNDS, T_BYTES], {T7_DEAR, BYTES})]),
    ("P15", 2, "cache_write > input 견줌 지움(나눔만)",
     [(CLIENT, swap("    return max(plain, compute_cost_usd(split, pricing, hosted_calls, hosted))\n",
                    "    return compute_cost_usd(split, pricing, hosted_calls, hosted)\n"))],
     [(PURE, [T_BOUNDS], {T7_CHEAP})]),
    ("P16", 2, "_worst_once_usd 할증 지움",
     [(CLIENT, swap("return _bound_usd(worst, self._cached_tokens(provider_request), model.pricing, searches, hosted)",
                    "return _bound_usd(worst, 0, model.pricing, searches, hosted)"))],
     [(PURE, [T_BOUNDS], {T7_FAIL})]),
    ("P17", 2, "캐시 몫 두 번 셈(평 입력에서 안 뺌)",
     [(CLIENT, swap("        usage, input_tokens=usage.input_tokens - cached, cache_write_tokens",
                    "        usage, input_tokens=usage.input_tokens, cache_write_tokens"))],
     # failed-attempt 시험은 두 단가의 차이만 봐 두 번 셈이 상쇄된다 — 손셈과 견주는 dry-run 시험이 겨눈다
     [(PURE, [T_BOUNDS], {T7_DEAR})]),
]
PLANTS = [p for p in PLANTS if p[1] <= BOUNDARY and (ONLY is None or p[0] in ONLY)]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    _name, cmd, _ = layer
    # 바이트코드를 쓰지 않고 빈 자리에서만 찾는다(LV1 10-22 실측 — 같은 초·같은 길이로 되돌린 파일의 남은 .pyc).
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache"), "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^(?:FAILED|ERROR) (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


def base(node: str) -> str:
    return node.split("[", 1)[0]


shutil.rmtree(LOGS / "pycache", ignore_errors=True)
files = sorted({f for p in PLANTS for f, _ in p[3]})
start = {f: f.read_bytes() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in p[4]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, failed, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0


def plant_and_check(number: str, what: str, edits, checks) -> bool | None:
    """잡았으면 True, 못 잡았으면 False, 컨테이너가 없어 다 돌리지 못했으면 None."""
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
                return False
            f.write_text(new, encoding="utf-8")
        hit_all, skipped = True, False
        for layer, targets, expected in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                skipped = True
                continue
            code, failed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            red = {base(n) for n in failed}
            hit = code != 0 and expected <= red
            hit_all = hit_all and hit
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {sorted(expected - red)} — {what}")
            for node in sorted(failed):
                print(f"    {node}")
        return None if skipped and hit_all else hit_all
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
try:
    for number, _boundary, what, edits, checks in PLANTS:
        result = plant_and_check(number, what, edits, checks)
        planted += 1
        caught += 1 if result is True else 0
        print(f"{number} => {'잡음' if result else '안 돌림' if result is None else '못 잡음'}")
finally:
    restored = all(f.read_bytes() == data for f, data in start.items())  # cmp
same = restored and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
