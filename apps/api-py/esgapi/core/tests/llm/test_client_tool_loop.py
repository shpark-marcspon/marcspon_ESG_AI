"""도구 호출 고리 `LlmClient.call_tools`(밴드 TL1 `MARC-TICK-180` 의 T5 뒷몫·T7~T13). 순수 층, 모의 공급사만.

도구 이름·인자·결과·URL·토큰 수는 전부 가상(synthetic) 값이다(업무 도구의 이름·스키마는 core 가 모른다).
비용: 모의 모델(mock-synthetic)에서 `USAGE_SYNTHETIC` 한 번이 정확히 0.0001 USD 다.
"""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import CallRequest, ToolCallRequest
from esgapi.core.llm.config import HostedToolPricing
from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.log import MISSING
from esgapi.core.llm.retry import RetryPolicy
from esgapi.core.llm.types import (
    BudgetExceeded,
    CutOff,
    FunctionCall,
    FunctionTool,
    ProviderError,
    ProviderFailed,
    ProviderResponse,
    ProviderTimeout,
    Refusal,
    Refused,
    Scope,
    TimedOut,
    ToolExecutorRaised,
    ToolLoopDone,
    ToolLoopFailed,
    ToolLoopPartial,
    ToolLoopResult,
    ToolOutput,
    ToolStep,
    Truncated,
    UrlCitation,
    WebSearchTool,
)
from esgapi.core.tests.llm.test_temperature import config_with_route
from esgapi.core.tests.llm_support import TAGS, USAGE_SYNTHETIC, Harness, config_with, harness

PARAMS: dict[str, object] = {"type": "object", "properties": {"x": {"type": "number"}}}
TOOLS = (
    FunctionTool(name="tool_a", description="가상 도구 a", parameters=PARAMS),
    FunctionTool(name="tool_b", description="가상 도구 b", parameters=PARAMS),
)
REQUEST = ToolCallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS, tools=TOOLS, max_steps=4)
HOSTED = HostedToolPricing(web_search_per_call=0.01)


class Recorder:
    """실행 함수. 받은 (이름, 인자)를 적고, 둘을 이은 결과 글자를 돌려준다."""

    def __init__(self) -> None:
        self.seen: list[tuple[str, str]] = []

    def __call__(self, name: str, arguments: str) -> str:
        self.seen.append((name, arguments))
        return f"out:{name}:{arguments}"


def run(h: Harness, request: ToolCallRequest = REQUEST) -> tuple[ToolLoopResult, Recorder]:
    execute = Recorder()
    return h.client.call_tools(request, execute), execute


# ── T7 끝남 ──


def test_two_calls_then_text_is_done_with_outputs_replayed_in_call_order(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_tool_calls([("tool_a", '{"x":1}'), ("tool_b", '{"x":2}')], usage=USAGE_SYNTHETIC)
    h.mock.enqueue_text("끝", usage=USAGE_SYNTHETIC)

    result, execute = run(h)

    assert isinstance(result, ToolLoopDone)
    assert result.text == "끝"
    assert result.hosted_calls == 0
    assert execute.seen == [("tool_a", '{"x":1}'), ("tool_b", '{"x":2}')]
    first, second = h.mock.calls
    assert first.tools == TOOLS
    assert first.turns == ()
    calls = (
        FunctionCall(call_id="call_1", name="tool_a", arguments='{"x":1}'),
        FunctionCall(call_id="call_2", name="tool_b", arguments='{"x":2}'),
    )
    outputs = (
        ToolOutput(call_id="call_1", output='out:tool_a:{"x":1}'),
        ToolOutput(call_id="call_2", output='out:tool_b:{"x":2}'),
    )
    # 답의 항목을 출력 차례 그대로, 그 뒤에 결과를 호출과 같은 차례로.
    assert second.turns == (*calls, *outputs)
    assert second.tools == TOOLS
    assert result.steps == (ToolStep(calls=calls, outputs=outputs, hosted_calls=0),)
    # 기록: call_id 하나에 attempt 0,1, 도구 호출을 받은 걸음도 success(상태 칸 없음).
    records = h.log.records
    assert [record.attempt for record in records] == [0, 1]
    assert {record.call_id for record in records} == {result.meta.call_id}
    assert [record.result_kind for record in records] == ["success", "success"]
    assert [record.error_status for record in records] == [MISSING, MISSING]
    assert [attempt.tool_step for attempt in result.meta.attempts] == [1, 2]
    assert result.meta.total_cost_usd == 0.0002


def test_the_system_placement_and_loop_fields_reach_every_step(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_tool_calls([("tool_a", "{}")])
    h.mock.enqueue_text("끝")
    request = replace(
        REQUEST, system_placement="input_message", tool_choice="auto", parallel_tool_calls=False, temperature=0.1
    )

    result, _ = run(h, request)

    assert isinstance(result, ToolLoopDone)
    for sent in h.mock.calls:
        assert sent.system_placement == "input_message"
        assert sent.tool_choice == "auto"
        assert sent.parallel_tool_calls is False
        assert sent.temperature == 0.1


# ── T8 부분 ──


def test_steps_run_out_while_tools_are_still_called_is_partial_after_exactly_max_steps(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_tool_calls([("tool_a", "1")])
    h.mock.enqueue_tool_calls([("tool_b", "2")])
    h.mock.enqueue_tool_calls([("tool_a", "3"), ("tool_b", "4")], text="셋째 답의 글")
    h.mock.enqueue_text("불리지 않는다")

    result, execute = run(h, replace(REQUEST, max_steps=3))

    assert isinstance(result, ToolLoopPartial)
    assert len(h.mock.calls) == 3
    assert h.mock.pending == 1
    assert result.text == "셋째 답의 글"
    assert result.pending == (
        FunctionCall(call_id="call_3", name="tool_a", arguments="3"),
        FunctionCall(call_id="call_4", name="tool_b", arguments="4"),
    )
    assert execute.seen == [("tool_a", "1"), ("tool_b", "2")]
    assert len(result.steps) == 2
    assert [attempt.tool_step for attempt in result.meta.attempts] == [1, 2, 3]


def test_one_step_is_partial_at_once_without_running_the_tools(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_tool_calls([("tool_a", "{}")])

    result, execute = run(h, replace(REQUEST, max_steps=1))

    assert isinstance(result, ToolLoopPartial)
    assert execute.seen == []
    assert result.steps == ()


# ── T9 실패 갈래 ──

FAILURES: dict[str, tuple[ProviderResponse, type]] = {
    "timeout": (ProviderTimeout(message="모의 시간 초과"), TimedOut),
    "provider_error": (ProviderError(status=400, retryable=False, message="모의 잘못된 요청"), ProviderFailed),
    "refusal": (Refusal(text="거부", category=None, usage=USAGE_SYNTHETIC), Refused),
    "truncated": (Truncated(text="잘린 글", usage=USAGE_SYNTHETIC), CutOff),
}


@pytest.mark.parametrize("name", FAILURES)
def test_a_failing_second_step_fails_the_loop_with_the_first_step_kept(prompt_root: Path, name: str) -> None:
    reply, expected = FAILURES[name]
    h = harness(prompt_root)
    h.mock.enqueue_tool_calls([("tool_a", "{}")])
    h.mock.enqueue(reply)

    result, execute = run(h)

    assert isinstance(result, ToolLoopFailed)
    assert isinstance(result.failure, expected)
    assert result.budget_source is None
    assert len(result.steps) == 1
    assert execute.seen == [("tool_a", "{}")]
    assert len(h.mock.calls) == 2


def test_an_executor_exception_fails_the_loop_with_its_class_only(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_tool_calls([("tool_a", "{}"), ("tool_b", "{}")])
    h.mock.enqueue_text("불리지 않는다")

    def execute(name: str, arguments: str) -> str:
        raise ValueError("고객 비밀 123")

    result = h.client.call_tools(REQUEST, execute)

    assert isinstance(result, ToolLoopFailed)
    assert result.failure == ToolExecutorRaised(name="tool_a", error_class="ValueError")
    assert result.steps == ()
    assert len(h.mock.calls) == 1
    assert "고객 비밀" not in repr(result)


# ── T10 재시도는 걸음이 아니다 ──


def test_a_same_model_retry_does_not_use_a_step(prompt_root: Path) -> None:
    h = harness(prompt_root, provider_retry={"mock": RetryPolicy(max_retries=1, base_delay_ms=0, max_delay_ms=0)})
    h.mock.enqueue_tool_calls([("tool_a", "{}")])
    h.mock.enqueue(ProviderError(status=429, retryable=True, message="모의 한도 초과"))
    h.mock.enqueue_text("끝")

    result, _ = run(h, replace(REQUEST, max_steps=2))

    assert isinstance(result, ToolLoopDone)
    assert result.text == "끝"
    records = h.log.records
    assert len(records) == 3
    assert [record.result_kind for record in records] == ["success", "provider_error", "success"]
    assert records[2].provider_retry == 1
    assert [attempt.tool_step for attempt in result.meta.attempts] == [1, 2, 2]


# ── T11 상한 ──


def test_the_budget_guard_is_checked_before_every_step(prompt_root: Path) -> None:
    h = harness(prompt_root, limits=[BudgetLimit(scope=Scope(tenant=TAGS.tenant), limit_usd=0.0001)])
    h.mock.enqueue_tool_calls([("tool_a", "{}")], usage=USAGE_SYNTHETIC)
    h.mock.enqueue_text("불리지 않는다")

    result, _ = run(h)

    assert isinstance(result, ToolLoopFailed)
    assert isinstance(result.failure, BudgetExceeded)
    assert result.budget_source == "guard"
    assert result.failure.limit_usd == 0.0001
    assert len(h.mock.calls) == 1
    assert len(result.steps) == 1
    assert [record.result_kind for record in h.log.records] == ["success", "budget_exceeded"]


def test_the_loop_cost_cap_stops_before_the_step_that_would_pass_it(prompt_root: Path) -> None:
    h = harness(prompt_root)
    for n in range(3):
        h.mock.enqueue_tool_calls([("tool_a", str(n))], usage=USAGE_SYNTHETIC)
    h.mock.enqueue_text("불리지 않는다")

    result, _ = run(h, replace(REQUEST, max_cost_usd=0.0002))

    assert isinstance(result, ToolLoopFailed)
    assert result.budget_source == "loop"
    assert result.failure == BudgetExceeded(
        limit_usd=0.0002, spent_usd=0.0002, scope=Scope(tenant=TAGS.tenant, module=TAGS.module), meta=result.meta
    )
    assert len(h.mock.calls) == 2
    assert len(result.steps) == 2
    records = h.log.records
    assert [record.result_kind for record in records] == ["success", "success", "budget_exceeded"]
    assert records[2].attempt == 2
    assert records[2].model is None


# ── T12 거름(공급사 호출 전) ──

SOL_ONLY = config_with_route("sol-only", ("gpt-6.1-sol",))
REFUSED_ROUTES: dict[str, tuple[str, str]] = {
    "two_models": ("mock-with-fallback", "모델 하나"),
    "anthropic": ("light-anthropic", "TOOL_PROVIDERS"),
    "gemini": ("light-gemini", "TOOL_PROVIDERS"),
    "luna": ("light-openai", "TOOL_MODELS"),
    "mini": ("light-openai-41", "TOOL_MODELS"),
    "sol": ("sol-only", "TOOL_MODELS"),
}


@pytest.mark.parametrize("dry", [False, True], ids=["call_tools", "dry_run_tools"])
@pytest.mark.parametrize("case", REFUSED_ROUTES)
def test_routes_outside_the_tool_lists_are_refused_before_any_provider_call(
    prompt_root: Path, case: str, dry: bool
) -> None:
    route, message = REFUSED_ROUTES[case]
    h = harness(prompt_root, config=SOL_ONLY)
    request = replace(REQUEST, route=route)
    with pytest.raises(LlmConfigError, match=message):
        if dry:
            h.client.dry_run_tools(request)
        else:
            h.client.call_tools(request, Recorder())
    assert h.mock.calls == []
    assert h.mock_b.calls == []
    assert h.log.records == []


BAD_REQUESTS: dict[str, dict[str, Any]] = {
    "zero_steps": {"max_steps": 0},
    "bool_steps": {"max_steps": True},
    "no_tools": {"tools": ()},
    "not_a_tool": {"tools": ({"type": "function", "name": "tool_a"},)},
    "zero_cap": {"max_cost_usd": 0},
    "nan_cap": {"max_cost_usd": float("nan")},
    "zero_hosted": {"max_hosted_calls": 0},
    "tool_choice": {"tool_choice": "any"},
    "placement": {"system_placement": "system"},
}


@pytest.mark.parametrize("case", BAD_REQUESTS)
def test_bad_loop_requests_are_refused_before_any_provider_call(prompt_root: Path, case: str) -> None:
    h = harness(prompt_root)
    with pytest.raises(LlmConfigError):
        h.client.call_tools(replace(REQUEST, **BAD_REQUESTS[case]), Recorder())
    assert h.mock.calls == []


# ── T5 뒷몫: web_search 인데 건당 요금이 없는 모델 ──


@pytest.mark.parametrize("dry", [False, True], ids=["call_tools", "dry_run_tools"])
def test_web_search_on_a_model_without_a_per_call_price_is_refused(prompt_root: Path, dry: bool) -> None:
    h = harness(prompt_root)
    request = replace(REQUEST, tools=(*TOOLS, WebSearchTool()))
    with pytest.raises(LlmConfigError, match="hostedToolPricing"):
        if dry:
            h.client.dry_run_tools(request)
        else:
            h.client.call_tools(request, Recorder())
    assert h.mock.calls == []


# ── T13 web_search ──

CITATIONS = (
    UrlCitation(url="https://example.invalid/a", title="가상 출처 a", start_index=0, end_index=1),
    UrlCitation(url="https://example.invalid/b", title="가상 출처 b", start_index=1, end_index=2),
)


def test_web_search_only_ends_in_one_step_and_its_calls_are_charged(prompt_root: Path) -> None:
    h = harness(prompt_root, config=config_with(hosted_tool_pricing=HOSTED))
    h.mock.enqueue_text("답", usage=USAGE_SYNTHETIC, citations=CITATIONS, hosted_calls=2)

    result, execute = run(h, replace(REQUEST, tools=(WebSearchTool(),), max_hosted_calls=3))

    assert isinstance(result, ToolLoopDone)
    assert result.hosted_calls == 2
    assert result.citations == CITATIONS
    assert result.steps == ()
    assert execute.seen == []
    assert h.mock.calls[0].max_hosted_calls == 3
    (record,) = h.log.records
    assert record.cost_usd == 0.0201
    assert record.warnings == ()
    assert result.meta.total_cost_usd == 0.0201


def test_searches_across_steps_add_up_and_each_step_is_charged(prompt_root: Path) -> None:
    h = harness(prompt_root, config=config_with(hosted_tool_pricing=HOSTED))
    h.mock.enqueue_tool_calls([("tool_a", "{}")], usage=USAGE_SYNTHETIC, hosted_calls=1)
    h.mock.enqueue_text("답", usage=USAGE_SYNTHETIC, hosted_calls=2)

    result, _ = run(h, replace(REQUEST, tools=(*TOOLS, WebSearchTool())))

    assert isinstance(result, ToolLoopDone)
    assert result.hosted_calls == 3
    assert [step.hosted_calls for step in result.steps] == [1]
    assert [record.cost_usd for record in h.log.records] == [0.0101, 0.0201]
    assert [record.warnings for record in h.log.records] == [(), ()]
    assert result.meta.total_cost_usd == 0.0302


def test_the_plain_call_path_carries_no_tool_fields_and_no_tool_step(prompt_root: Path) -> None:
    # 고리와 같은 걸음 코드를 지나도 `call` 은 도구 칸을 싣지 않고 시도에 걸음 번호를 달지 않는다.
    h = harness(prompt_root)
    h.mock.enqueue_text("답")

    result = h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS))

    (sent,) = h.mock.calls
    assert not sent.uses_tools
    assert [attempt.tool_step for attempt in result.meta.attempts] == [None]
