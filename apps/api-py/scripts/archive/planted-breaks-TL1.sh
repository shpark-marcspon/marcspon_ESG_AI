#!/usr/bin/env bash
# 밴드 TL1(MARC-TICK-180) 의 심은 파손(발주서 band-handoffs/TL1-order.md §3-2). 하나씩 심고 겨눈 시험만 돌린 뒤 손으로
# 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-TL1.sh [--boundary 1|2] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 「잡음」= 심은 뒤 pytest 가 0 아닌 종료이고, 빨개져야 할 시험 노드가
# 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 경계 n 에는 커밋 n 까지의 P 만 심는다. 순수 층만(컨테이너 0).
# 심을 때마다 파일이 실제로 바뀌었는지 먼저 보고(심을 자리가 없으면 「못 심음」= 못 잡음으로 센다), 끝에 심은 파일의
# sha256 과 git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 산출물: S4_OUT(기본: 워크트리 곁의 TL1.out)/planted/. 공급사·네트워크·키 0. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${S4_OUT:-$(cd "$ROOT/.." && pwd)/TL1.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY uv run --frozen python -I - "$OUT/planted" "$@" <<'PY'
import hashlib
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
BOUNDARY = 2
ONLY: set[str] | None = None
while args:
    if args[0] == "--boundary" and len(args) > 1 and args[1] in ("1", "2"):
        BOUNDARY, args = int(args[1]), args[2:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


L = Path("esgapi/core/llm")
OPENAI = L / "providers/openai.py"
ANTHROPIC = L / "providers/anthropic.py"
TYPES = L / "types.py"
COST = L / "cost.py"
CLIENT = L / "client.py"
RULES = Path("esgapi/core/tests/test_transaction_rules.py")
T = "esgapi/core/tests/llm/"
T_OPENAI = T + "providers/test_openai_tools.py"
T_BYTES = T + "test_client_bytes_unchanged.py"
T_COST = T + "test_cost_hosted.py"
T_CALL = T + "test_client_tool_calls_in_call.py"
T_ANTH = T + "providers/test_anthropic_tools.py"
T_LOOP = T + "test_client_tool_loop.py"
T_DRY = T + "test_client_dry_run_tools.py"
T_RULES = str(RULES)

# (번호, 경계, 설명, [(파일, 심는 함수)], 겨눔 시험 파일들, 빨개져야 할 노드)
PLANTS = [
    ("P1", 1, "parallel_tool_calls 를 싣지 않음",
     [(OPENAI, swap('        if request.parallel_tool_calls is not None:\n'
                    '            params["parallel_tool_calls"] = request.parallel_tool_calls\n', ""))],
     [T_OPENAI], [T_OPENAI + "::test_eight_function_tools_and_the_three_loop_fields_are_carried_in_order"]),
    ("P5", 1, '"store": False → True',
     [(OPENAI, swap('            "store": False,\n', '            "store": True,\n'))],
     [T_OPENAI], [T_OPENAI + "::test_turns_are_replayed_after_the_user_message_in_output_order_without_provider_item_ids"]),
    ("P6", 1, "to_json 이 빈 tools 를 [] 로 냄",
     [(TYPES, swap('        if self.tools:\n            out["tools"]', '        if True:\n            out["tools"]'))],
     [T_BYTES], [T_BYTES + "::test_requests_records_and_dry_runs_without_tools_match_the_baseline_commit"]),
    ("P8", 1, "건당 요금을 비용에 안 더함",
     [(COST, swap("    return round_usd(micro / _PER_MTOK + hosted_calls * hosted.web_search_per_call)\n",
                  "    return round_usd(micro / _PER_MTOK)\n"))],
     [T_COST], [T_COST + "::test_tokens_plus_calls_times_the_per_call_rate_rounded_like_the_rest",
                T_COST + "::test_a_completed_answer_with_web_search_calls_is_charged_per_call_in_the_record"]),
    ("P9", 1, "url_citation 을 버림",
     [(OPENAI, swap('if note.type == "url_citation"', 'if note.type == "url_citation" and False'))],
     [T_OPENAI], [T_OPENAI + "::test_web_search_calls_are_counted_and_url_citations_kept_in_order"]),
    ("P10", 1, "input_message 인데 instructions 로",
     [(OPENAI, swap('        if request.system and request.system_placement == "instructions":\n',
                    "        if request.system:\n"))],
     [T_OPENAI], [T_OPENAI + "::test_input_message_placement_moves_system_to_the_front_of_input_and_drops_instructions"]),
    ("P12", 1, "anthropic 방어 줄 지움",
     [(ANTHROPIC, swap("        if request.uses_tools:\n            raise LlmConfigError(_NO_TOOLS)\n", "")),
      (ANTHROPIC, swap("        if request.uses_tools:\n            return ProviderError(status=None, retryable=False, message=_NO_TOOLS)\n", ""))],
     [T_ANTH], [T_ANTH + "::test_tool_fields_are_refused_not_dropped[tools]",
                T_ANTH + "::test_tool_fields_are_refused_not_dropped[turns]",
                T_ANTH + "::test_tool_fields_are_refused_not_dropped[system_placement]"]),
    ("P15", 1, "call 이 ToolCallsRequested 를 Success(\"\") 로",
     [(CLIENT, swap("                    case ToolCallsRequested():\n                        failure = ProviderFailed(\n",
                    "                    case ToolCallsRequested():\n"
                    "                        return Success(data=cast(\"T\", response.text), text=response.text, meta=meta())\n"
                    "                        failure = ProviderFailed(\n"))],
     [T_CALL], [T_CALL + "::test_a_tool_call_answer_to_a_plain_call_is_a_non_retryable_provider_error_with_its_cost_kept"]),
    ("P16", 1, "call 의 ToolCallsRequested 갈래에서 usage 를 None 으로",
     [(CLIENT, swap("usage = None if isinstance(response, ProviderError | ProviderTimeout) else response.usage",
                    "usage = None if isinstance(response, ProviderError | ProviderTimeout | ToolCallsRequested) "
                    "else response.usage"))],
     [T_CALL], [T_CALL + "::test_a_tool_call_answer_to_a_plain_call_is_a_non_retryable_provider_error_with_its_cost_kept"]),
    ("P17", 1, "다시 싣는 function_call 에 id 를 실음",
     [(OPENAI, swap('return {"type": "function_call", "call_id": turn.call_id,',
                    'return {"type": "function_call", "id": "fc_" + turn.call_id, "call_id": turn.call_id,'))],
     [T_OPENAI], [T_OPENAI + "::test_turns_are_replayed_after_the_user_message_in_output_order_without_provider_item_ids"]),
]

T_LOOP_EXEC = T_LOOP + "::test_an_executor_exception_fails_the_loop_with_its_class_only"
T_LOOP_T12 = T_LOOP + "::test_routes_outside_the_tool_lists_are_refused_before_any_provider_call"
PLANTS += [
    ("P2", 2, "걸음 조건 >= → > 가 한 걸음 더 부름",
     [(CLIENT, swap("                    if step_no >= request.max_steps:\n",
                    "                    if step_no > request.max_steps:\n"))],
     [T_LOOP], [T_LOOP + "::test_steps_run_out_while_tools_are_still_called_is_partial_after_exactly_max_steps"]),
    ("P3", 2, "걸음이 다했을 때 Partial 대신 Done",
     [(CLIENT, swap("                        return ToolLoopPartial(\n",
                    "                        return ToolLoopDone(  # 심음\n                            citations=(),\n")),
      (CLIENT, swap("                            pending=response.calls,\n", ""))],
     [T_LOOP], [T_LOOP + "::test_steps_run_out_while_tools_are_still_called_is_partial_after_exactly_max_steps",
                T_LOOP + "::test_one_step_is_partial_at_once_without_running_the_tools"]),
    ("P4", 2, "걸음 ≥2 에서 budget.check 를 건너뜀",
     [(CLIENT, swap("            exhausted = self.budget.check(state.tags)\n",
                    "            exhausted = None if (tool_step or 0) >= 2 else self.budget.check(state.tags)\n"))],
     [T_LOOP], [T_LOOP + "::test_the_budget_guard_is_checked_before_every_step"]),
    ("P7", 2, "한 답의 호출 결과 차례를 뒤집음",
     [(CLIENT, swap("                    turns.extend(outputs)\n", "                    turns.extend(reversed(outputs))\n"))],
     [T_LOOP], [T_LOOP + "::test_two_calls_then_text_is_done_with_outputs_replayed_in_call_order"]),
    ("P11", 2, "실행 함수 예외를 {\"error\":…} 글로 삼켜 계속",
     [(CLIENT, swap("                            raised = ToolExecutorRaised(name=tool_call.name, error_class=type(error).__name__)\n"
                    "                            return ToolLoopFailed(failure=raised, steps=tuple(steps), meta=state.meta())\n",
                    "                            output = '{\"error\": \"' + type(error).__name__ + '\"}'\n"))],
     [T_LOOP], [T_LOOP_EXEC]),
    ("P13", 2, "OUTSIDE_CALLS 의 \"call_tools\" 지움",
     [(RULES, swap('        "call_tools",\n', ""))],
     [T_RULES], [T_RULES + "::test_the_checker_catches_what_it_should"]),
    ("P14", 2, "dry-run 걸음 k 위끝에서 (k−1)·maxOut 몫을 뺌",
     [(CLIENT, swap("                    input_tokens=input_tokens + (step - 1) * max_out,\n",
                    "                    input_tokens=input_tokens,\n"))],
     [T_DRY], [T_DRY + "::test_step_bounds_add_the_replayed_outputs_of_earlier_steps",
               T_DRY + "::test_web_search_with_a_per_response_cap_adds_steps_times_cap_times_price",
               T_DRY + "::test_web_search_without_a_cap_leaves_the_call_count_out_and_says_so"]),
    ("P18", 2, "허용 목록 대신 reasoning_output_reserve_tokens 로 거름",
     [(CLIENT, swap('    if model.provider == "openai" and model.api_model_id not in TOOL_MODELS:\n',
                    '    if model.provider == "openai" and model.reasoning_output_reserve_tokens is not None:\n'))],
     [T_LOOP], [T_LOOP_T12 + "[sol-call_tools]", T_LOOP_T12 + "[sol-dry_run_tools]"]),
]

PURE = ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"]


def run(tests: list[str], log: Path) -> tuple[int, str]:
    done = subprocess.run([*PURE, *tests], capture_output=True, text=True, check=False)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def git_status() -> str:
    return subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout


chosen = [p for p in PLANTS if p[1] <= BOUNDARY and (ONLY is None or p[0] in ONLY)]
if not chosen:
    # 고른 P 가 없으면 0/0 으로 지나가지 않는다(셀 것이 없다 = 실패).
    print("★ 고른 P 가 0 — 셀 것이 없다")
    print("PLANTED=0/0")
    sys.exit(1)
files = sorted({path for _, _, _, edits, _, _ in chosen for path, _ in edits})
start_sums = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
start_status = git_status()

targets = sorted({t for *_, tests, _ in chosen for t in tests})
code, text = run(targets, LOGS / "p0.log")
tail = text.strip().splitlines()[-1] if text.strip() else ""
print(f"P0 아무것도 안 심음: EXIT={code} · {tail}")
if code != 0:
    print("★ 0번이 초록이 아니다 — 심은 파손을 셀 수 없다")
    print("PLANTED=0/" + str(len(chosen)))
    print("FINGERPRINT=" + ("same" if git_status() == start_status else "DIFF"))
    sys.exit(1)

caught = 0
for name, _boundary, what, edits, tests, must_fail in chosen:
    originals = {path: path.read_bytes() for path, _ in edits}
    planted = True
    try:
        for path, plant in edits:
            text_now = path.read_text(encoding="utf-8")
            new = plant(text_now)
            if new is None or new == text_now:
                planted = False
                break
            path.write_text(new, encoding="utf-8")
        if not planted:
            print(f"{name} {what}: ★ 못 심음(자리 없음) — 못 잡음으로 센다")
            continue
        code, out = run(tests, LOGS / f"{name}.log")
        failed_nodes = {line.split(" ", 1)[1].split(" - ")[0] for line in out.splitlines() if line.startswith("FAILED ")}
        missing = [node for node in must_fail if node not in failed_nodes]
        extra = sorted(failed_nodes - set(must_fail))
        ok = code != 0 and not missing
        caught += ok
        print(f"{name} {what}: {'잡음' if ok else '★ 못 잡음'} EXIT={code} 빨강 {len(failed_nodes)}"
              + (f" · 안 빨개진 겨눔 {missing}" if missing else "")
              + (f" · 그 밖에 빨강 {len(extra)}" if extra else ""))
    finally:
        for path, data in originals.items():
            path.write_bytes(data)
            if path.read_bytes() != data:
                print(f"★ 되쓰기 실패: {path}")

end_sums = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
same = end_sums == start_sums and git_status() == start_status
print(f"PLANTED={caught}/{len(chosen)}")
print("FINGERPRINT=" + ("same" if same else "DIFF"))
sys.exit(0 if caught == len(chosen) and same else 1)
PY
