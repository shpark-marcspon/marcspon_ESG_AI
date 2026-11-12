#!/usr/bin/env bash
# 밴드 LH2 의 심은 파손(발주서 band-handoffs/LH2-order.md §3-1 — P1~P28, 분모 28 — P27·P28 은 검증 B1·R1). LH1 의 꼴 그대로: 하나씩 심고
# 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다.
# INT·TERM 도 되쓰기를 지난다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-LH2.sh <1|2> [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 시험(이름 — 매개 변수 갈래는 하나라도)이 전부 FAILED·ERROR 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다).
# PLANTED 는 P 단위로 센다 — 경계 ① 은 P1~P4·P23·P24(6), 경계 ② 는 28 전부.
# 업무 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 끝에 심은 파일의 sha256 이 시작과 같은지(cmp), git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: S4_OUT(기본: 워크트리 곁의 LH2.out)/planted-<경계>/. 공급사를 부르지 않는다(키 변수·LLM_RUN_MODE 를 지운 채 —
# 발주서 ENVX). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${S4_OUT:-$(cd "$ROOT/.." && pwd)/LH2.out}"
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
SETUP = Path(LLM + "setup.py")
CALL = Path("esgapi/core/management/commands/llm_call.py")
CLIENT = Path(LLM + "client.py")
EMBEDDING = Path(LLM + "embedding.py")
ERRORS = Path(LLM + "errors.py")
LOG = Path(LLM + "log.py")
OPENAI = Path(LLM + "providers/openai.py")
ANTHROPIC = Path(LLM + "providers/anthropic.py")
GEMINI = Path(LLM + "providers/gemini.py")
CTX = Path("esgapi/runs/context.py")

T_PROC = "esgapi/core/tests/llm/test_process_client.py"
T_CMD = "esgapi/core/tests/test_llm_command.py"
T_BOUND = "esgapi/core/tests/llm/test_cost_bound.py"
T_SOFT = "esgapi/core/tests/llm/test_soft_deadline.py"
T_BYTES = "esgapi/core/tests/llm/test_client_bytes_unchanged.py"
T_RUN = "esgapi/runs/tests/test_context_bound.py"

S1 = T_PROC + "::test_s1_the_process_client_carries_no_key_in_either_run_mode"
S3 = T_PROC + "::test_s3_sdk_variables_in_the_shell_send_nothing"
S4_REFUSED = T_CMD + "::test_real_route_with_an_sdk_variable_is_refused_by_name_before_any_provider"
S4_DRY = T_CMD + "::test_the_same_sdk_variable_does_not_stop_a_dry_run_or_the_mock_route"
S5_CASES = T_BOUND + "::test_s5_failed_attempts_carry_the_worst_once_bound_and_no_ledger_cost"
S5_CAP = T_BOUND + "::test_s5_the_bound_counts_the_output_cap"
S5_SENT = T_BOUND + "::test_s5_requests_that_never_left_say_so"
S5_SSE = T_BOUND + "::test_s5_an_error_event_inside_a_200_stream_is_bounded"
S6 = T_BOUND + "::test_s6_the_bound_is_not_in_the_json_line_or_the_db_row"
S7 = T_BOUND + "::test_s7_an_embedding_timeout_is_bounded_with_the_sdk_retries"
S5_PDF = T_BOUND + "::test_s5_attachment_base64_is_left_out_of_the_bound"
S7_ERR = T_BOUND + "::test_s7_an_embedding_error_is_bounded_only_when_it_may_have_been_billed"
S8_NAME = T_SOFT + "::test_s8_the_name_is_found_on_the_error_and_down_its_chain"
S8_ADAPTERS = T_SOFT + "::test_s8_each_adapter_raises_the_soft_limit_instead_of_an_error_value"
S8_FALLBACK = T_SOFT + "::test_s8_anthropic_send_soft_limit_is_not_retried_or_handed_to_the_fallback"
S8_CLIENT = T_SOFT + "::test_s8_client_invoke_reraises_and_writes_one_timeout_line"
S8_EMBED = T_SOFT + "::test_s8_embedding_invoke_reraises_and_writes_one_timeout_line"
S8_TOOL = T_SOFT + "::test_s8_the_tool_executor_soft_limit_is_not_turned_into_a_failure"
S9_LIVE = T_RUN + "::test_a_soft_limit_inside_a_live_call_defers_the_run"
S9_MOCK = T_RUN + "::test_a_soft_limit_inside_a_mock_call_defers_the_run"
S9_SUM = T_RUN + "::test_two_timeouts_in_one_attempt_count_against_the_run_limit"
BYTES = T_BYTES + "::test_requests_records_and_dry_runs_without_tools_match_the_baseline_commit"

PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rfE", "-p", "no:cacheprovider"], True)

KEYS = "settings = replace(app_config().llm, openai_api_key=None, anthropic_api_key=None, gemini_api_key=None)"
SDK_CHECK = "sdk_names = sdk_env_names(os.environ) if live else []"
RERAISE = "            if (deadline := soft_deadline_in(error)) is not None:\n                raise deadline from None"
NO_RERAISE = "            if False:\n                pass"
OPENAI_CHAT = "self._client.responses.create(**self.build_request(request), timeout=options.timeout_ms / 1000)\n        except Exception as error:\n"
OPENAI_EMBED = "self._client.embeddings.create(**self.build_request(request), timeout=options.timeout_ms / 1000)\n        except Exception as error:\n"
BILLED = "    return response.status is None or 200 <= response.status < 300\n"


def after(anchor: str, old: str, new: str) -> Callable[[str], str | None]:
    """anchor 바로 뒤의 old 하나를 new 로(같은 글이 여러 자리에 있을 때 자리를 고른다)."""

    def plant(text: str) -> str | None:
        return text.replace(anchor + old, anchor + new) if text.count(anchor + old) == 1 else None

    return plant


# (번호, 경계, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 시험 이름들)])
PLANTS = [
    ("P1", 1, "llm_client() 의 키 비우기 지움(BASE 꼴)",
     [(SETUP, swap(KEYS, "settings = app_config().llm"))],
     [(PURE, [T_PROC], {S1, S3})]),
    ("P2", 1, "키 비우기를 openai 만",
     [(SETUP, swap(KEYS, "settings = replace(app_config().llm, openai_api_key=None)"))],
     [(PURE, [T_PROC], {S1, S3})]),
    ("P3", 1, "llm_call 의 SDK 변수 검사 지움",
     [(CALL, swap(SDK_CHECK, "sdk_names: list[str] = []"))],
     [(PURE, [T_CMD], {S4_REFUSED})]),
    ("P4", 1, "llm_call 검사를 dry-run 에도",
     [(CALL, swap(SDK_CHECK, "sdk_names = sdk_env_names(os.environ) if (live or dry_run) else []"))],
     [(PURE, [T_CMD], {S4_DRY})]),
    ("P23", 1, "Q1 을 mock 때만 비움",
     [(SETUP, swap(KEYS, 'settings = app_config().llm if app_config().llm.run_mode == "live" else replace('
                         "app_config().llm, openai_api_key=None, anthropic_api_key=None, gemini_api_key=None)"))],
     [(PURE, [T_PROC], {S1, S3})]),
    ("P24", 1, "Q2 오류 글에 값 실음",
     [(CALL, swap("{', '.join(sdk_names)} ", "{', '.join(n + '=' + os.environ[n] for n in sdk_names)} "))],
     [(PURE, [T_CMD], {S4_REFUSED})]),
    ("P5", 2, "실패 시도 cost_bound_usd 를 None 으로",
     [(CLIENT, swap("if _maybe_billed(response) else None", "if False else None"))],
     [(PURE, [T_BOUND], {S5_CASES, S5_SSE, S6}), (BUSINESS, [T_RUN], {S9_SUM})]),
    ("P6", 2, "RunCallSink.record 가 cost_bound_usd 를 안 더함",
     [(CTX, swap("(record.cost_bound_usd or 0.0)", "0.0"))],
     [(BUSINESS, [T_RUN], {S9_SUM})]),
    ("P7", 2, "상태 있는 오류(429)에도 어림",
     [(CLIENT, swap(BILLED, "    return True\n"))],
     [(PURE, [T_BOUND], {S5_CASES})]),
    ("P8", 2, "어림에서 출력 상한 뺌(입력만)",
     [(CLIENT, after("        worst = Usage(\n            input_tokens=input_tokens,\n",
                     "            output_tokens=provider_request.max_output_tokens,\n", "            output_tokens=0,\n"))],
     [(PURE, [T_BOUND], {S5_CASES, S5_CAP})]),
    ("P9", 2, "to_json 에 새 칸 실음",
     [(LOG, swap('                "costUsd": self.cost_usd,\n',
                 '                "costUsd": self.cost_usd,\n                "costBoundUsd": self.cost_bound_usd,\n'))],
     [(PURE, [T_BOUND, T_BYTES], {S6, BYTES})]),
    ("P10", 2, "임베딩 어림 지움",
     [(EMBEDDING, swap('kind="timeout", duration_ms=duration_ms, cost_bound_usd=self._worst_usd(batch, model)',
                       'kind="timeout", duration_ms=duration_ms, cost_bound_usd=None'))],
     [(PURE, [T_BOUND], {S7})]),
    ("P11", 2, "openai invoke 의 다시 던지기 지움",
     [(OPENAI, after(OPENAI_CHAT, RERAISE, NO_RERAISE))],
     [(PURE, [T_SOFT], {S8_ADAPTERS})]),
    ("P12", 2, "anthropic invoke 의 다시 던지기 지움",
     [(ANTHROPIC, swap(RERAISE + "\n", NO_RERAISE + "\n"))],
     [(PURE, [T_SOFT], {S8_ADAPTERS, S8_FALLBACK})]),
    ("P13", 2, "gemini invoke 의 다시 던지기 지움",
     [(GEMINI, swap(RERAISE, NO_RERAISE))],
     [(PURE, [T_SOFT], {S8_ADAPTERS})]),
    ("P14", 2, "client._invoke 의 다시 던지기 지움",
     [(CLIENT, swap("        if (deadline := soft_deadline_in(error)) is not None:\n            raise deadline from None",
                    "        if False:\n            pass"))],
     [(PURE, [T_SOFT], {S8_CLIENT})]),
    ("P15", 2, "도구 실행 자리의 다시 던지기 지움",
     [(CLIENT, swap("                            if (deadline := soft_deadline_in(error)) is not None:\n"
                    "                                raise deadline from None",
                    "                            if False:\n                                pass"))],
     [(PURE, [T_SOFT], {S8_TOOL})]),
    ("P16", 2, "soft_deadline_in 이 __cause__ 를 안 따라감",
     [(ERRORS, swap("current = current.__cause__ or current.__context__", "current = current.__context__"))],
     [(PURE, [T_SOFT], {S8_NAME})]),
    ("P17", 2, "Q8 의 timeout 줄 쓰기 지움(대화)",
     [(CLIENT, swap("                if soft_deadline_in(error) is not None:\n                    # 나간 요청이",
                    "                if False:\n                    # 나간 요청이"))],
     [(PURE, [T_SOFT], {S8_CLIENT, S8_FALLBACK})]),
    ("P18", 2, "판별 이름 오타(SoftTimeLimitExceed)",
     [(ERRORS, swap('_SOFT_DEADLINE = "SoftTimeLimitExceeded"', '_SOFT_DEADLINE = "SoftTimeLimitExceed"'))],
     [(PURE, [T_SOFT], {S8_NAME, S8_ADAPTERS, S8_CLIENT}), (BUSINESS, [T_RUN], {S9_LIVE, S9_MOCK})]),
    ("P19", 2, "2xx 갈래 어림 지움",
     [(CLIENT, swap(BILLED, "    return response.status is None\n"))],
     [(PURE, [T_BOUND], {S5_CASES, S5_SSE})]),
    ("P20", 2, "임베딩 어댑터의 다시 던지기 지움",
     [(OPENAI, after(OPENAI_EMBED, RERAISE, NO_RERAISE))],
     [(PURE, [T_SOFT], {S8_ADAPTERS})]),
    ("P21", 2, "embedding._invoke 의 다시 던지기 지움",
     [(EMBEDDING, swap("        if (deadline := soft_deadline_in(error)) is not None:\n            raise deadline from None",
                       "        if False:\n            pass"))],
     [(PURE, [T_SOFT], {S8_EMBED})]),
    ("P22", 2, "임베딩 Q8 줄 쓰기 지움",
     [(EMBEDDING, swap("                if soft_deadline_in(error) is not None:\n                    # 나간 요청이",
                       "                if False:\n                    # 나간 요청이"))],
     [(PURE, [T_SOFT], {S8_EMBED})]),
    ("P25", 2, "어댑터 앞 거절에 sent=True",
     [(ANTHROPIC, swap('message="Anthropic 클라이언트가 주입되지 않았다", sent=False',
                       'message="Anthropic 클라이언트가 주입되지 않았다", sent=True'))],
     [(PURE, [T_BOUND], {S5_SENT})]),
    ("P26", 2, "Q5 의 × (1 + 재시도) 지움",
     [(EMBEDDING, swap(" * (1 + EMBEDDING_SDK_MAX_RETRIES))", ")"))],
     [(PURE, [T_BOUND], {S7})]),
    ("P27", 2, "어림에서 첨부 base64 빼기 지움(검증 B1)",
     [(CLIENT, swap('"user": [{k: v for k, v in part.items() if k != "base64"} for part in user]',
                    '"user": [dict(part) for part in user]'))],
     [(PURE, [T_BOUND], {S5_PDF})]),
    ("P28", 2, "임베딩 오류 갈래 어림 지움(검증 R1)",
     [(EMBEDDING, swap("billed = response.sent and (response.status is None or 200 <= response.status < 300)",
                       "billed = False"))],
     [(PURE, [T_BOUND], {S7_ERR})]),
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
