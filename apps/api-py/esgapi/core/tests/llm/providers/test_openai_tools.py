"""OpenAI 어댑터의 도구 칸(밴드 TL1 `MARC-TICK-180` 의 T2·T3): 조립과 해석. 순수 층.

실제 공급사로 가는 호출은 없다. 응답은 설치된 SDK 의 `Response.model_validate` 로 지은 가짜이고,
도구 이름·인자·글·URL 은
전부 가상(synthetic) 값이다(업무 도구의 이름·스키마는 core 가 모른다).
"""

from dataclasses import replace
from typing import Any, cast

from openai.types.responses import Response

from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.types import (
    AssistantText,
    Completed,
    FunctionCall,
    FunctionTool,
    ProviderRequest,
    Refusal,
    SystemSegment,
    TextPart,
    ToolCallsRequested,
    ToolOutput,
    Truncated,
    UrlCitation,
    WebSearchTool,
)
from esgapi.core.tests.test_llm_adapters import OPENAI_USAGE, OPTIONS, FakeOpenAI, openai_response

PARAMS: dict[str, object] = {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]}
TOOLS = tuple(FunctionTool(name=f"tool_{n}", description=f"가상 도구 {n}", parameters=PARAMS) for n in range(8))
BASE = ProviderRequest(
    api_model_id="model-synthetic",
    system=(SystemSegment(text="지침", cache=True), SystemSegment(text="메모", cache=False)),
    user=(TextPart(text="검토해 줘"),),
    max_output_tokens=500,
)


def with_tools(**fields: Any) -> ProviderRequest:
    return replace(BASE, **fields)


def keys_named(value: object, name: str) -> list[object]:
    """중첩된 dict·list 어디든 `name` 열쇠의 값."""
    found: list[object] = []
    if isinstance(value, dict):
        for key, inner in cast("dict[object, object]", value).items():
            if key == name:
                found.append(inner)
            found.extend(keys_named(inner, name))
    elif isinstance(value, list):
        for inner in cast("list[object]", value):
            found.extend(keys_named(inner, name))
    return found


# ── T2 조립 ──


def test_eight_function_tools_and_the_three_loop_fields_are_carried_in_order() -> None:
    params = OpenAIProvider().build_request(
        with_tools(tools=TOOLS, tool_choice="auto", parallel_tool_calls=False, temperature=0.1)
    )
    assert params["tools"] == [
        {"type": "function", "name": f"tool_{n}", "description": f"가상 도구 {n}", "parameters": PARAMS}
        for n in range(8)
    ]
    assert params["tool_choice"] == "auto"
    assert params["parallel_tool_calls"] is False
    assert params["temperature"] == 0.1
    assert params["store"] is False
    assert params["instructions"] == "지침\n\n메모"
    # 열쇠는 이것뿐이다: 앞 응답을 잇는 열쇠(공급사 보관)와 max_tool_calls 는 없다.
    assert set(params) == {
        "model",
        "max_output_tokens",
        "input",
        "store",
        "instructions",
        "temperature",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
    }


def test_strict_is_carried_only_when_given() -> None:
    strict = FunctionTool(name="s", description="d", parameters=PARAMS, strict=True)
    loose = FunctionTool(name="l", description="d", parameters=PARAMS, strict=False)
    params = OpenAIProvider().build_request(with_tools(tools=(TOOLS[0], strict, loose)))
    assert params["tools"] == [
        {"type": "function", "name": "tool_0", "description": "가상 도구 0", "parameters": PARAMS},
        {"type": "function", "name": "s", "description": "d", "parameters": PARAMS, "strict": True},
        {"type": "function", "name": "l", "description": "d", "parameters": PARAMS, "strict": False},
    ]


def test_web_search_alone_and_its_per_response_call_cap() -> None:
    params = OpenAIProvider().build_request(
        with_tools(tools=(WebSearchTool(search_context_size="medium"),), max_hosted_calls=3)
    )
    assert params["tools"] == [{"type": "web_search", "search_context_size": "medium"}]
    assert params["max_tool_calls"] == 3


def test_input_message_placement_moves_system_to_the_front_of_input_and_drops_instructions() -> None:
    params = OpenAIProvider().build_request(with_tools(tools=TOOLS[:1], system_placement="input_message"))
    assert "instructions" not in params
    assert params["input"] == [
        {"role": "system", "content": "지침\n\n메모"},
        {"role": "user", "content": [{"type": "input_text", "text": "검토해 줘"}]},
    ]


def test_turns_are_replayed_after_the_user_message_in_output_order_without_provider_item_ids() -> None:
    turns = (
        AssistantText(text="먼저 찾아본다"),
        FunctionCall(call_id="call_a", name="tool_0", arguments='{"x":1}'),
        FunctionCall(call_id="call_b", name="tool_1", arguments='{"x":2}'),
        ToolOutput(call_id="call_a", output='{"value":1}'),
        ToolOutput(call_id="call_b", output='{"value":2}'),
    )
    params = OpenAIProvider().build_request(with_tools(tools=TOOLS[:2], turns=turns))
    assert params["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "검토해 줘"}]},
        {"role": "assistant", "content": "먼저 찾아본다"},
        {"type": "function_call", "call_id": "call_a", "name": "tool_0", "arguments": '{"x":1}'},
        {"type": "function_call", "call_id": "call_b", "name": "tool_1", "arguments": '{"x":2}'},
        {"type": "function_call_output", "call_id": "call_a", "output": '{"value":1}'},
        {"type": "function_call_output", "call_id": "call_b", "output": '{"value":2}'},
    ]
    # 공급사 항목 id(fc_…·msg_…)는 어디에도 싣지 않는다(store:false 라 보관되지 않았다 — MARC-ENT-301).
    assert keys_named(params, "id") == []
    assert params["store"] is False
    # 앞 응답을 잇는 열쇠(공급사 보관)는 없다: 열쇠는 이것뿐이다.
    assert set(params) == {"model", "max_output_tokens", "input", "store", "instructions", "tools"}


# ── T3 해석 ──

TEXT: dict[str, Any] = {"type": "output_text", "text": "결과", "annotations": []}


def message(*parts: dict[str, Any], item_id: str = "msg_1") -> dict[str, Any]:
    return {"type": "message", "id": item_id, "role": "assistant", "status": "completed", "content": list(parts)}


def function_call(call_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "type": "function_call",
        "id": f"fc_{call_id}",
        "call_id": call_id,
        "name": name,
        "arguments": arguments,
        "status": "completed",
    }


def web_search_call(item_id: str) -> dict[str, Any]:
    return {"type": "web_search_call", "id": item_id, "status": "completed", "action": {"type": "search", "query": "q"}}


def citation(n: int) -> dict[str, Any]:
    return {
        "type": "url_citation",
        "start_index": n,
        "end_index": n + 2,
        "title": f"출처 {n}",
        "url": f"https://example.invalid/{n}",
    }


def parse(response: Response) -> object:
    return OpenAIProvider(FakeOpenAI(response)).invoke(BASE, OPTIONS)


def test_two_function_calls_keep_their_order() -> None:
    reply = parse(
        openai_response(output=[function_call("call_a", "tool_0", '{"x":1}'), function_call("call_b", "tool_1", "{}")])
    )
    assert isinstance(reply, ToolCallsRequested)
    assert reply.output == (
        FunctionCall(call_id="call_a", name="tool_0", arguments='{"x":1}'),
        FunctionCall(call_id="call_b", name="tool_1", arguments="{}"),
    )
    assert reply.calls == reply.output
    assert reply.text == ""
    assert reply.model_id == "model-synthetic-snapshot"
    assert reply.usage.output_tokens == OPENAI_USAGE["output_tokens"]


def test_text_call_text_keeps_the_output_order() -> None:
    reply = parse(
        openai_response(
            output=[
                message({**TEXT, "text": "앞"}, item_id="msg_a"),
                function_call("call_a", "tool_0", "{}"),
                message({**TEXT, "text": "뒤"}, item_id="msg_b"),
            ]
        )
    )
    assert isinstance(reply, ToolCallsRequested)
    assert reply.output == (
        AssistantText(text="앞"),
        FunctionCall(call_id="call_a", name="tool_0", arguments="{}"),
        AssistantText(text="뒤"),
    )
    assert reply.text == "앞뒤"


def test_web_search_calls_are_counted_and_url_citations_kept_in_order() -> None:
    annotated = {**TEXT, "annotations": [citation(0), citation(4), citation(0)]}
    reply = parse(openai_response(output=[web_search_call("ws_1"), web_search_call("ws_2"), message(annotated)]))
    assert isinstance(reply, Completed)
    assert reply == Completed(
        text="결과",
        usage=reply.usage,
        model_id="model-synthetic-snapshot",
        citations=(
            UrlCitation(url="https://example.invalid/0", title="출처 0", start_index=0, end_index=2),
            UrlCitation(url="https://example.invalid/4", title="출처 4", start_index=4, end_index=6),
            UrlCitation(url="https://example.invalid/0", title="출처 0", start_index=0, end_index=2),
        ),
        hosted_calls=2,
    )


def test_refusal_and_incomplete_win_over_function_calls() -> None:
    refused = parse(
        openai_response(
            output=[message({"type": "refusal", "refusal": "못 한다"}), function_call("call_a", "tool_0", "{}")]
        )
    )
    assert isinstance(refused, Refusal)
    assert refused.text == "못 한다"
    cut = parse(
        openai_response(
            status="incomplete",
            incomplete_details={"reason": "max_output_tokens"},
            output=[message({**TEXT, "text": "잘린"}), function_call("call_a", "tool_0", "{")],
        )
    )
    assert isinstance(cut, Truncated)
    assert cut.text == "잘린"


def test_a_plain_message_is_still_completed_with_no_citations_and_no_hosted_calls() -> None:
    reply = parse(openai_response(output=[message(TEXT)]))
    assert isinstance(reply, Completed)
    assert reply.citations == ()
    assert reply.hosted_calls == 0


def test_function_calls_mixed_with_web_search_are_tool_calls_that_still_count_the_searches() -> None:
    # 한 응답에 web_search 와 함수 호출이 섞이면 함수 호출이 남은 답이다: 검색 건수는 그 답에 실려 비용에 든다.
    annotated = {**TEXT, "text": "찾는 중", "annotations": [citation(0)]}
    reply = parse(
        openai_response(
            output=[
                web_search_call("ws_1"),
                message(annotated),
                web_search_call("ws_2"),
                function_call("call_a", "tool_0", "{}"),
            ]
        )
    )
    assert isinstance(reply, ToolCallsRequested)
    assert reply.output == (
        AssistantText(text="찾는 중"),
        FunctionCall(call_id="call_a", name="tool_0", arguments="{}"),
    )
    assert reply.hosted_calls == 2
