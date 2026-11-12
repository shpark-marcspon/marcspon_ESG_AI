"""모의 공급사의 도구 호출 응답(밴드 TL1 `MARC-TICK-180`, 요구 10). 순수 층. 값은 전부 가상(synthetic)이다."""

from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.types import (
    AssistantText,
    Completed,
    FunctionCall,
    InvokeOptions,
    ProviderRequest,
    TextPart,
    ToolCallsRequested,
    UrlCitation,
)

REQUEST = ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10)
OPTIONS = InvokeOptions(timeout_ms=1000)


def test_tool_call_answers_and_text_answers_come_out_in_the_planted_order_with_deterministic_call_ids() -> None:
    mock = MockProvider()
    cite = UrlCitation(url="https://example.invalid/a", title="a", start_index=0, end_index=1)
    mock.enqueue_tool_calls([("tool_0", '{"x":1}'), ("tool_1", "{}")], text="먼저").enqueue_tool_calls(
        [("tool_0", "{}")], hosted_calls=1
    ).enqueue_text("끝", citations=[cite], hosted_calls=2)

    first, second, last = (mock.invoke(REQUEST, OPTIONS) for _ in range(3))

    assert first == ToolCallsRequested(
        output=(
            AssistantText(text="먼저"),
            FunctionCall(call_id="call_1", name="tool_0", arguments='{"x":1}'),
            FunctionCall(call_id="call_2", name="tool_1", arguments="{}"),
        ),
        usage=SYNTHETIC_USAGE,
    )
    assert second == ToolCallsRequested(
        output=(FunctionCall(call_id="call_3", name="tool_0", arguments="{}"),), usage=SYNTHETIC_USAGE, hosted_calls=1
    )
    assert last == Completed(text="끝", usage=SYNTHETIC_USAGE, citations=(cite,), hosted_calls=2)
    assert mock.pending == 0


def test_build_request_carries_the_tool_fields_through_to_json() -> None:
    body = MockProvider().build_request(
        ProviderRequest(
            api_model_id="m",
            system=(),
            user=(TextPart(text="q"),),
            max_output_tokens=10,
            turns=(FunctionCall(call_id="call_1", name="t", arguments="{}"),),
        )
    )
    assert body == {
        "mock": True,
        "apiModelId": "m",
        "system": [],
        "user": [{"type": "text", "text": "q"}],
        "maxOutputTokens": 10,
        "turns": [{"type": "function_call", "callId": "call_1", "name": "t", "arguments": "{}"}],
    }
