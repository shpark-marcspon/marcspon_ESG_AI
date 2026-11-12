"""공급사가 실행한 도구의 건당 요금(밴드 TL1 `MARC-TICK-180` 의 T6). 순수 층. 단가는 가상(synthetic) 값이다."""

from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from esgapi.core.llm.client import CallRequest, ToolCallRequest
from esgapi.core.llm.config import HostedToolPricing, Pricing
from esgapi.core.llm.cost import compute_cost_usd, round_usd
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.types import (
    CutOff,
    FunctionTool,
    Refusal,
    Refused,
    ToolLoopFailed,
    Truncated,
    Usage,
    WebSearchTool,
)
from esgapi.core.tests.llm.providers.test_openai_tools import BASE, TEXT, message, web_search_call
from esgapi.core.tests.llm_support import TAGS, USAGE_SYNTHETIC, config_with, harness
from esgapi.core.tests.test_llm_adapters import OPTIONS, FakeOpenAI, openai_response

PRICE = Pricing(input=1.0, output=2.0, cache_write=1.25, cache_read=0.1)
HOSTED = HostedToolPricing(web_search_per_call=0.01)


def test_tokens_plus_calls_times_the_per_call_rate_rounded_like_the_rest() -> None:
    # 60×1 + 20×2 = 100 → 0.0001, 건당 0.01 × 3 = 0.03
    assert compute_cost_usd(USAGE_SYNTHETIC, PRICE, 3, HOSTED) == 0.0301
    third = HostedToolPricing(web_search_per_call=1 / 3)
    assert compute_cost_usd(USAGE_SYNTHETIC, PRICE, 1, third) == round_usd(0.0001 + 1 / 3)


@given(
    inp=st.integers(min_value=0, max_value=10_000_000),
    out=st.integers(min_value=0, max_value=1_000_000),
    read=st.integers(min_value=0, max_value=1_000_000),
)
def test_zero_hosted_calls_cost_exactly_what_the_two_argument_form_costs(inp: int, out: int, read: int) -> None:
    usage = Usage(input_tokens=inp, output_tokens=out, cache_read_tokens=read, cache_write_tokens=0)
    plain = compute_cost_usd(usage, PRICE)
    assert compute_cost_usd(usage, PRICE, 0, HOSTED) == plain
    assert compute_cost_usd(usage, PRICE, 0, None) == plain


def test_a_completed_answer_with_web_search_calls_is_charged_per_call_in_the_record(prompt_root: Path) -> None:
    h = harness(prompt_root, config=config_with(hosted_tool_pricing=HOSTED))
    h.mock.enqueue_text("답", USAGE_SYNTHETIC, hosted_calls=2)
    h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS))
    (record,) = h.log.records
    assert record.cost_usd == 0.0201


# ── 잘림·거부도 이미 돈 검색은 과금된다(밴드 QC2 `MARC-TICK-420`, `MARC-ISSUE-349`) ──
# 모의 모델에서 `USAGE_SYNTHETIC` 한 번은 0.0001 USD, 건당 0.01 — 완료와 같은 셈이다.

PLAIN = CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS)


def test_a_truncated_answer_still_charges_its_web_search_calls(prompt_root: Path) -> None:
    h = harness(prompt_root, config=config_with(hosted_tool_pricing=HOSTED))
    h.mock.enqueue(Truncated(text="잘린", usage=USAGE_SYNTHETIC, hosted_calls=2))
    result = h.client.call(PLAIN)
    assert isinstance(result, CutOff)
    (record,) = h.log.records
    assert record.cost_usd == 0.0201
    assert result.meta.total_cost_usd == 0.0201


def test_a_refused_answer_still_charges_its_web_search_calls(prompt_root: Path) -> None:
    h = harness(prompt_root, config=config_with(hosted_tool_pricing=HOSTED))
    h.mock.enqueue(Refusal(text="못 한다", category="content_filter", usage=USAGE_SYNTHETIC, hosted_calls=1))
    result = h.client.call(PLAIN)
    assert isinstance(result, Refused)
    (record,) = h.log.records
    assert record.cost_usd == 0.0101
    assert result.meta.total_cost_usd == 0.0101


def test_a_loop_cut_off_on_its_second_step_keeps_that_steps_searches_in_the_total(prompt_root: Path) -> None:
    h = harness(prompt_root, config=config_with(hosted_tool_pricing=HOSTED))
    h.mock.enqueue_tool_calls([("tool_a", "{}")], usage=USAGE_SYNTHETIC, hosted_calls=1)
    h.mock.enqueue(Truncated(text="잘린", usage=USAGE_SYNTHETIC, hosted_calls=1))
    tool = FunctionTool(name="tool_a", description="가상 도구 a", parameters={"type": "object", "properties": {}})
    request = ToolCallRequest(
        prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS, tools=(tool, WebSearchTool()), max_steps=4
    )

    result = h.client.call_tools(request, lambda name, arguments: "out")

    assert isinstance(result, ToolLoopFailed)
    assert isinstance(result.failure, CutOff)
    assert [step.hosted_calls for step in result.steps] == [1]
    assert [record.cost_usd for record in h.log.records] == [0.0101, 0.0101]
    assert result.meta.total_cost_usd == 0.0202


def test_the_openai_adapter_counts_searches_on_an_incomplete_and_a_refused_response() -> None:
    cut = OpenAIProvider(
        FakeOpenAI(
            openai_response(
                status="incomplete",
                incomplete_details={"reason": "max_output_tokens"},
                output=[web_search_call("ws_1"), web_search_call("ws_2"), message({**TEXT, "text": "잘린"})],
            )
        )
    ).invoke(BASE, OPTIONS)
    assert isinstance(cut, Truncated)
    assert cut.hosted_calls == 2
    filtered = OpenAIProvider(
        FakeOpenAI(
            openai_response(
                status="incomplete",
                incomplete_details={"reason": "content_filter"},
                output=[web_search_call("ws_1"), message({**TEXT, "text": "걸린"})],
            )
        )
    ).invoke(BASE, OPTIONS)
    assert isinstance(filtered, Refusal)
    assert filtered.hosted_calls == 1
    refused = OpenAIProvider(
        FakeOpenAI(
            openai_response(output=[web_search_call("ws_1"), message({"type": "refusal", "refusal": "못 한다"})])
        )
    ).invoke(BASE, OPTIONS)
    assert isinstance(refused, Refusal)
    assert refused.hosted_calls == 1


def test_a_truncated_or_refused_answer_without_searches_costs_what_it_did_before(prompt_root: Path) -> None:
    h = harness(prompt_root, config=config_with(hosted_tool_pricing=HOSTED))
    h.mock.enqueue(Truncated(text="잘린", usage=USAGE_SYNTHETIC))
    h.mock.enqueue(Refusal(text="못 한다", category=None, usage=USAGE_SYNTHETIC))
    h.client.call(PLAIN)
    h.client.call(PLAIN)
    assert [record.cost_usd for record in h.log.records] == [0.0001, 0.0001]
