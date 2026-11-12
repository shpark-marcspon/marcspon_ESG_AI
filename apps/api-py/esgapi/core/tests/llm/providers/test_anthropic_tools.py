"""Anthropic 어댑터는 도구 칸을 싣지 않는다(밴드 TL1 `MARC-TICK-180` 의 T12 어댑터 몫). 순수 층.

호출 층을 거치지 않고 포트를 직접 부르는 길에서 tools·turns·system_placement 가 조용히 빠지지 않게: 조립은
LlmConfigError, 호출은 재시도 불가 공급사 오류이고 SDK 를 부르지 않는다. 값은 전부 가상(synthetic)이다.
"""

from dataclasses import replace

import pytest

from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.providers.anthropic import AnthropicProvider
from esgapi.core.llm.types import FunctionCall, FunctionTool, ProviderError, ProviderRequest, TextPart
from esgapi.core.tests.test_llm_adapters import OPTIONS, FakeAnthropic, anthropic_message

PLAIN = ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10)
TOOL_FIELDS = {
    "tools": replace(PLAIN, tools=(FunctionTool(name="t", description="d", parameters={}),)),
    "turns": replace(PLAIN, turns=(FunctionCall(call_id="call_1", name="t", arguments="{}"),)),
    "system_placement": replace(PLAIN, system_placement="input_message"),
}


@pytest.mark.parametrize("field", list(TOOL_FIELDS))
def test_tool_fields_are_refused_not_dropped(field: str) -> None:
    request = TOOL_FIELDS[field]
    with pytest.raises(LlmConfigError, match="도구 칸"):
        AnthropicProvider().build_request(request)
    fake = FakeAnthropic(anthropic_message())
    response = AnthropicProvider(fake).invoke(request, OPTIONS)
    assert isinstance(response, ProviderError)
    assert response.retryable is False
    assert fake.messages.seen == []
