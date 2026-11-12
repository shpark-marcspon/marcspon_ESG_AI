#!/usr/bin/env bash
# 밴드 LV1 의 심은 파손(발주서 band-handoffs/LV1-order.md §3 + critic M1 + MARC-TICK-249 노트의 테스트 73 조건 (가)).
# RC1 의 꼴 그대로: 하나씩 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·
# restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-LV1.sh <1|2> [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 시험(이름 — 매개 변수 갈래는 하나라도)이 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다).
# PLANTED 는 P 단위로 센다 — 경계 ① 은 P1~P10·P13·P14(12), 경계 ② 는 그에 P11·P12(14).
#   P13 = critic M1(live 의 LLM_RUN_MAX_USD 명시 검사 지움) · P14 = 테스트 73 조건 (가)(기본을 live 로)
#   O1  = 관찰(세지 않음): redact_keys 를 무력화해도 ① 7 이 잡는가(발주서 §3 「러너가 하나 더」) — 결과는 보고에
# 업무 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: LV1_OUT(기본: 워크트리 곁의 LV1.out)/planted-<경계>/. 공급사를 부르지 않는다(키 변수 넷을 지운 채). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${LV1_OUT:-$(cd "$ROOT/.." && pwd)/LV1.out}"
case "${1:-}" in 1|2) BOUNDARY="$1"; shift ;; *) echo "첫 인자는 경계(1|2)"; exit 2 ;; esac
mkdir -p "$OUT/planted-$BOUNDARY"
exec env -u OPENAI_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY -u LLM_RUN_MODE \
  -u LLM_RUN_MAX_USD uv run --frozen python - "$OUT/planted-$BOUNDARY" "$BOUNDARY" "$@" <<'PY'
import hashlib
import os
import re
import shutil
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


def swap(old: str, new: str, count: int = 1) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new) if text.count(old) == count else None

    return plant


ENV = Path("esgapi/config/env.py")
CTX = Path("esgapi/runs/context.py")
REDACT = Path("esgapi/core/llm/providers/redact.py")
TENV = "esgapi/core/tests/test_env_llm_run_mode.py"
TCTX = "esgapi/runs/tests/test_context.py"
TLIVE = "esgapi/runs/tests/test_context_live.py"
TSEC = "esgapi/runs/tests/test_live_secrets.py"
TGW = "esgapi/greenwash/tests/flows/test_binding_e0_live_runs.py"
METRICS = "esgapi/user/tests/service/apis/test_run_logs.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
# 설정 읽기만 재는 층(Django 플러그인 없이): P14(기본 live)는 시험 세션의 Django 설정 읽기부터 멈추게 해(기동 실패 —
# 닫힌 쪽) 이름 있는 시험이 FAILED 로 찍히지 않는다. 이 층은 env.py 를 바로 불러 그 시험의 단언으로 빨개짐을 잰다.
NO_DJANGO = ("설정", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:django", "-p", "no:cacheprovider",
                      "-W", "ignore::pytest.PytestConfigWarning"], False)

MODE_PROBLEM = '        problems.append("LLM_RUN_MODE 는 mock, live 가운데 하나여야 한다(빈 값은 mock)")\n'

# (번호, 경계, 설명, [(파일, 심는 함수)], [(경계, 층, 겨눔 시험 파일들, 빨개져야 할 시험 이름들)], 셈에 드는가)
PLANTS = [
    ("P1", 1, "mock 에서도 키를 비우지 않음",
     [(CTX, swap('    if settings.run_mode == "live":\n        return settings\n', "    return settings\n"))],
     [(1, PURE, [TCTX], {TCTX + "::test_in_mock_mode_the_runner_builds_only_mock_clients_even_when_keys_exist"}),
      (1, BUSINESS, [TLIVE], {TLIVE + "::test_mock_carries_no_key_and_no_limit_even_with_keys",
                              TLIVE + "::test_mock_does_not_reach_a_real_route"})], True),
    ("P2", 1, "live 에서도 mock=True",
     [(CTX, swap('mock=settings.run_mode != "live"', "mock=True", count=2))],
     [(1, BUSINESS, [TLIVE], {TLIVE + "::test_live_carries_the_keys_with_one_run_limit_and_no_mock_route"})], True),
    ("P3", 1, "잘못된 모드를 mock 으로 삼킴",
     [(ENV, swap(MODE_PROBLEM, "        pass\n"))],
     [(1, PURE, [TENV], {TENV + "::test_an_unknown_mode_stops_startup_and_names_the_allowed_values_only"})], True),
    ("P4", 1, "live 의 db 싱크 조건 지움",
     [(ENV, swap('        if sink != "db":\n', "        if False:\n"))],
     [(1, PURE, [TENV], {TENV + "::test_live_needs_the_db_sink"})], True),
    ("P5", 1, "live 에 상한을 붙이지 않음",
     [(CTX, swap("        return (BudgetLimit(Scope(), settings.run_max_usd),)\n", "        return ()\n"))],
     [(1, BUSINESS, [TLIVE], {TLIVE + "::test_a_limit_below_one_call_stops_the_second_before_the_provider",
                              TLIVE + "::test_an_earlier_attempt_of_the_same_run_counts_from_the_first_call",
                              TLIVE + "::test_chat_and_embedding_share_one_run_limit",
                              TLIVE + "::test_live_carries_the_keys_with_one_run_limit_and_no_mock_route"})], True),
    ("P6", 1, "시드(그 실행의 앞 시도 DB 합)를 읽지 않음",
     [(CTX, swap("            self._seed = 0.0 if found is None else float(found.cost_usd)\n",
                 "            self._seed = 0.0\n"))],
     [(1, BUSINESS, [TLIVE], {TLIVE + "::test_an_earlier_attempt_of_the_same_run_counts_from_the_first_call"})], True),
    ("P7", 1, "mock 에도 상한",
     [(CTX, swap('        if settings.run_mode != "live":\n            return ()\n', ""))],
     [(1, BUSINESS, [TLIVE], {TLIVE + "::test_mock_carries_no_key_and_no_limit_even_with_keys",
                              TLIVE + "::test_mock_is_not_limited_even_with_a_spent_run"})], True),
    ("P8", 1, "설정 실패 글에 받은 값",
     [(ENV, swap(MODE_PROBLEM, MODE_PROBLEM.replace('(빈 값은 mock)")', '(빈 값은 mock) — 받은 값 " + run_mode)')))],
     [(1, PURE, [TENV], {TENV + "::test_an_unknown_mode_stops_startup_and_names_the_allowed_values_only"}),
      (1, BUSINESS, [TSEC], {TSEC + "::test_settings_failures_repr_and_the_notice_carry_no_key"})], True),
    ("P9", 1, "기동 줄에 키 앞 8자",
     [(ENV, swap(' sink={llm.log_sink}"\n',
                 ' sink={llm.log_sink} key={(llm.openai_api_key or llm.anthropic_api_key or "")[:8]}"\n'))],
     [(1, PURE, [TENV], {TENV + "::test_the_startup_notice_names_the_providers_only"}),
      (1, BUSINESS, [TSEC], {TSEC + "::test_settings_failures_repr_and_the_notice_carry_no_key"})], True),
    ("P10", 1, "RunCallSink.record 가 run_id 를 덮지 않음",
     [(CTX, swap("replace(record, run_id=self._run_id, step=step)", "replace(record, step=step)"))],
     [(1, PURE, [TCTX], {TCTX + "::test_every_record_of_the_run_carries_its_id_whatever_the_tags"}),
      (1, BUSINESS, [TLIVE, TGW], {TLIVE + "::test_live_goes_through_the_fake_http_to_done",
                                   TGW + "::test_a_live_greenwash_run_reaches_done_through_the_fake_http"})], True),
    ("P13", 1, "live 의 LLM_RUN_MAX_USD 명시 검사 지움(critic M1)",
     [(ENV, swap("        if run_max_text is None:\n", "        if False:\n"))],
     [(1, PURE, [TENV], {TENV + "::test_live_needs_an_explicit_run_max_usd"})], True),
    ("P14", 1, "빈 값·없음의 기본을 live 로(테스트 73 조건 (가))",
     [(ENV, swap('    run_mode = optional("LLM_RUN_MODE") or "mock"\n', '    run_mode = optional("LLM_RUN_MODE") or "live"\n'))],
     [(1, NO_DJANGO, [TENV], {TENV + "::test_absent_blank_and_mock_are_mock"})], True),
    ("O1", 1, "관찰: redact_keys 무력화(가림이 마지막 방어인가)",
     [(REDACT, swap('    return _AIZA.sub("AIza[가림]", _SK.sub("sk-[가림]", text))\n', "    return text\n"))],
     [(1, BUSINESS, [TSEC], {TSEC + "::test_a_live_run_whose_provider_echoes_the_key_leaves_no_key"})], False),
]
RUNLOGS = Path("esgapi/user/service/apis/run_logs.py")
AIMOCK = 'aiProviderMock=app_config().llm.run_mode != "live",'
METRICS_MODE = METRICS + "::test_ai_provider_mock_follows_the_servers_run_mode_and_nothing_else_moves"
PLANTS2 = [
    ("P11", 2, "aiProviderMock 늘 true",
     [(RUNLOGS, swap(AIMOCK, "aiProviderMock=True,"))],
     [(2, BUSINESS, [METRICS], {METRICS_MODE})], True),
    ("P12", 2, "aiProviderMock 뒤집음",
     [(RUNLOGS, swap(AIMOCK, 'aiProviderMock=app_config().llm.run_mode == "live",'))],
     [(2, BUSINESS, [METRICS], {METRICS_MODE,
                                METRICS + "::test_metrics_of_an_empty_month_are_zero_and_null",
                                METRICS + "::test_metrics_follow_the_rules_of_disposition_5"})], True),
]
PLANTS = [p for p in PLANTS + PLANTS2 if p[1] <= BOUNDARY and (ONLY is None or p[0] in ONLY)]
PLANTS = [(n, c, w, e, [k for k in checks if k[0] <= BOUNDARY], counted) for n, c, w, e, checks, counted in PLANTS]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    _name, cmd, _ = layer
    # 바이트코드를 쓰지 않고 빈 자리에서만 찾는다: 심고 되돌린 파일이 같은 초·같은 길이면(P14 — mock↔live) 남은 .pyc 가
    # mtime·크기 검사를 지나 심은 판이 다음 실행에 돈다(10-22 실측 — P0 이 빨개짐).
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache"), "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


def base(node: str) -> str:
    return node.split("[", 1)[0]


shutil.rmtree(LOGS / "pycache", ignore_errors=True)
files = sorted({f for p in PLANTS for f, _ in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

# 0번: 아무것도 안 심음 — 겨눈 시험이 초록
zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for _commit, layer, targets, _ in p[4]:
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
        for _commit, layer, targets, expected in checks:
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
                print(f"    FAILED {node}")
        return None if skipped and hit_all else hit_all
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
for number, _commit, what, edits, checks, counted in PLANTS:
    result = plant_and_check(number, what, edits, checks)
    if counted:
        planted += 1
        caught += 1 if result is True else 0
    verdict = "잡음" if result else "안 돌림" if result is None else "못 잡음"
    print(f"{number} => {verdict}{'' if counted else ' (관찰 — 세지 않음)'}")

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
