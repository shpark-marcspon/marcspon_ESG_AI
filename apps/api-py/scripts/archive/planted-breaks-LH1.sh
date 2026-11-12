#!/usr/bin/env bash
# 밴드 LH1 의 심은 파손(발주서 band-handoffs/LH1-order.md §3-1 — P1~P9·P12~P19, 분모 17). LV1 의 꼴 그대로: 하나씩 심고
# 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다.
# INT·TERM 도 되쓰기를 지난다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-LH1.sh <1|2> [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 시험(이름 — 매개 변수 갈래는 하나라도)이 전부 FAILED·ERROR 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다).
# PLANTED 는 P 단위로 센다 — 경계 ① 은 P1~P9·P12·P13·P18·P19(13), 경계 ② 는 그에 P14~P17(17).
# 업무 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 끝에 심은 파일의 sha256 이 시작과 같은지(cmp), git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: S4_OUT(기본: 워크트리 곁의 LH1.out)/planted-<경계>/. 공급사를 부르지 않는다(키 변수·LLM_RUN_MODE 를 지운 채 —
# 발주서 ENVX). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${S4_OUT:-$(cd "$ROOT/.." && pwd)/LH1.out}"
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
OPENAI = Path(LLM + "providers/openai.py")
ANTHROPIC = Path(LLM + "providers/anthropic.py")
GEMINI = Path(LLM + "providers/gemini.py")
CLIENT = Path(LLM + "client.py")
EMBEDDING = Path(LLM + "embedding.py")
RETRY = Path(LLM + "retry.py")
ENV = Path("esgapi/config/env.py")
CTX = Path("esgapi/runs/context.py")
SETTINGS = Path("esgapi/config/settings/test_business.py")
ACTIONS = Path("esgapi/runs/service/actions/runs.py")
IDEMPOTENCY = Path("esgapi/runs/calc/idempotency.py")

T_SDK = "esgapi/core/tests/llm/test_sdk_retries.py"
T_REDACT = "esgapi/core/tests/llm/providers/test_redact_paths.py"
T_WORST = "esgapi/core/tests/llm/test_dry_run_worst.py"
T_ADAPTERS = "esgapi/core/tests/test_llm_adapters.py"
T_RETRY = "esgapi/core/tests/test_llm_retry.py"
T_ENV = "esgapi/config/tests/test_env.py"
T_LIVE = "esgapi/runs/tests/test_context_live.py"
T_SUM = "esgapi/runs/tests/test_context_sum.py"
T_SURR = "esgapi/runs/tests/service/apis/test_runs_surrogate.py"
SDK_TEST = Path(T_SDK)

CHAT_LIVE = T_LIVE + "::test_chat_failures_are_recorded_and_left_to_the_module"
SDK0 = T_SDK + "::test_chat_clients_turn_sdk_retries_off_and_embedding_keeps_two"

PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rfE", "-p", "no:cacheprovider"], True)

# (번호, 경계, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 시험 이름들)])
PLANTS = [
    ("P1", 1, "create_openai_client 의 max_retries=0 지움",
     [(OPENAI, swap("openai.OpenAI(api_key=api_key, max_retries=CHAT_SDK_MAX_RETRIES)", "openai.OpenAI(api_key=api_key)"))],
     [(PURE, [T_SDK, T_ADAPTERS], {SDK0, T_SDK + "::test_openai_sdk_sends_one_request_on_429",
                                   T_ADAPTERS + "::test_sdk_clients_use_the_given_key_not_the_environment"}),
      (BUSINESS, [T_LIVE], {CHAT_LIVE})]),
    ("P2", 1, "create_anthropic_client 의 max_retries=0 지움",
     [(ANTHROPIC, swap("anthropic.Anthropic(api_key=api_key, max_retries=SDK_MAX_RETRIES)", "anthropic.Anthropic(api_key=api_key)"))],
     [(PURE, [T_SDK], {SDK0, T_SDK + "::test_anthropic_sdk_sends_one_request_on_429"})]),
    ("P3", 1, "openai _map_error 의 redact_keys 지움",
     [(OPENAI, swap("    message = redact_keys(str(error))\n", "    message = str(error)\n"))],
     [(PURE, [T_REDACT], {T_REDACT + "::test_openai_map_error"})]),
    ("P4", 1, "anthropic _map_error 의 redact_keys 지움",
     [(ANTHROPIC, swap("    message = redact_keys(str(error))\n", "    message = str(error)\n"))],
     [(PURE, [T_REDACT], {T_REDACT + "::test_anthropic_map_error"})]),
    ("P5", 1, "gemini _map_error 의 redact_keys 지움(두 갈래)",
     [(GEMINI, swap("redact_keys(error.message or str(error))", "(error.message or str(error))")),
      (GEMINI, swap("    message = redact_keys(str(error))\n", "    message = str(error)\n"))],
     [(PURE, [T_REDACT], {T_REDACT + "::test_gemini_map_error_api_error",
                          T_REDACT + "::test_gemini_map_error_other_exception"})]),
    ("P6", 1, "client._invoke 의 redact_keys 지움",
     [(CLIENT, swap("{redact_keys(str(error))}", "{str(error)}"))],
     [(PURE, [T_REDACT], {T_REDACT + "::test_client_invoke"})]),
    ("P7", 1, "DEFAULT_PROVIDER_RETRY 에서 openai 뺌",
     [(RETRY, swap('    "openai": RetryPolicy(max_retries=2, base_delay_ms=1_000, max_delay_ms=60_000),\n', ""))],
     [(PURE, [T_SDK, T_RETRY], {T_SDK + "::test_the_call_layer_retries_twice_and_logs_every_attempt",
                                T_SDK + "::test_real_openai_sdk_429_twice_then_200_is_three_requests_and_three_lines",
                                T_RETRY + "::test_default_retries_gemini_openai_anthropic_twice_from_one_second_doubling_capped_at_sixty",
                                T_RETRY + "::test_by_default_the_call_layer_retries_gemini_openai_anthropic_but_not_mock"}),
      (BUSINESS, [T_LIVE], {CHAT_LIVE})]),
    ("P8", 1, "openai 의 retry-after 읽기 지움",
     [(OPENAI, swap("        retry_after = retry_after_ms_from_headers(error.response.headers) if retryable else None\n",
                    "        retry_after = None\n"))],
     [(PURE, [T_SDK], {T_SDK + "::test_openai_reads_retry_after_headers",
                       T_SDK + "::test_real_openai_sdk_retry_after_seconds_becomes_the_call_layer_wait"})]),
    ("P9", 1, "live 의 SDK 환경 변수 문제 줄 지움",
     [(ENV, swap("        if sdk_names:\n", "        if False:\n"))],
     [(PURE, [T_ENV], {T_ENV + "::test_live_with_an_sdk_variable_stops_startup_naming_it_without_the_value"})]),
    ("P12", 1, "worst_case_usd 에서 × max_attempts 지움",
     [(CLIENT, swap("worst_case_usd=round_usd(worst_once * max_attempts)", "worst_case_usd=round_usd(worst_once)"))],
     [(PURE, [T_WORST], {T_WORST + "::test_a_schema_request_counts_schema_tokens_and_three_attempts",
                         T_WORST + "::test_the_new_keys_are_in_the_json"})]),
    ("P13", 1, "schema_tokens 를 0 으로",
     [(CLIENT, swap("        max_attempts = 1 if request.schema is None else 1 + request.max_schema_retries\n",
                    "        schema_tokens = 0\n        max_attempts = 1 if request.schema is None else 1 + request.max_schema_retries\n"))],
     [(PURE, [T_WORST], {T_WORST + "::test_a_schema_request_counts_schema_tokens_and_three_attempts",
                         T_WORST + "::test_the_new_keys_are_in_the_json"})]),
    ("P18", 1, "임베딩 _invoke 의 redact_keys 지움",
     [(EMBEDDING, swap("{redact_keys(str(error))}", "{str(error)}"))],
     [(PURE, [T_REDACT], {T_REDACT + "::test_embedding_invoke"})]),
    ("P19", 1, "S1~S4 의 가짜 transport 하나(openai) 뺌",
     [(SDK_TEST, swap("return real(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(server.openai)))",
                      "return real(**kwargs)"))],
     [(PURE, [T_SDK], {T_SDK + "::test_openai_sdk_sends_one_request_on_429"})]),
    ("P14", 2, "seed + attempt → max(seed, attempt)",
     [(CTX, swap("round_usd(self._seed + self._attempt_usd)", "round_usd(max(self._seed, self._attempt_usd))"))],
     [(BUSINESS, [T_SUM], {T_SUM + "::test_the_seed_and_this_attempt_add_up_and_the_sum_blocks_the_next_call"})]),
    ("P15", 2, "시험 설정의 LLM_RUN_MODE pop 지움",
     [(SETTINGS, swap('os.environ.pop("LLM_RUN_MODE", None)', "None"))],
     [(PURE, [T_SUM], {T_SUM + "::test_the_test_settings_stay_mock_in_a_live_shell"})]),
    ("P16", 2, "UnicodeEncodeError 잡기 지움",
     [(ACTIONS, swap("    try:\n        too_large = _options_too_large(options, limit)\n    except UnicodeEncodeError:\n"
                     "        return OptionsRejected(options_unencodable())\n",
                     "    too_large = _options_too_large(options, limit)\n"))],
     [(BUSINESS, [T_SURR], {T_SURR + "::test_a_lone_surrogate_in_options_is_400_with_a_document",
                            T_SURR + "::test_a_lone_surrogate_in_options_is_400_without_a_document"})]),
    ("P17", 2, "idempotency.py 해시를 encode(\"utf-8\") 로",
     [(IDEMPOTENCY, swap('text.encode("utf-8", "surrogatepass")', 'text.encode("utf-8")'))],
     [(BUSINESS, [T_SURR], {T_SURR + "::test_a_lone_surrogate_in_options_is_400_with_a_document",
                            T_SURR + "::test_a_lone_surrogate_in_options_is_400_without_a_document"})]),
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
