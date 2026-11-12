"""Gemini 어댑터는 도구 칸을 싣지 않는다(밴드 TL1 `MARC-TICK-180` 의 T12 어댑터 몫). 순수 층.

호출 층을 거치지 않고 포트를 직접 부르는 길에서 tools·turns·system_placement 가 조용히 빠지지 않게: 조립은
LlmConfigError, 호출은 재시도 불가 공급사 오류이고 SDK 를 부르지 않는다. 값은 전부 가상(synthetic)이다.
"""

import pytest

from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.providers.gemini import GeminiProvider
from esgapi.core.llm.types import ProviderError
from esgapi.core.tests.llm.providers.test_anthropic_tools import TOOL_FIELDS
from esgapi.core.tests.test_llm_adapters import OPTIONS
from esgapi.core.tests.test_llm_gemini import FakeGemini, gemini_response


@pytest.mark.parametrize("field", list(TOOL_FIELDS))
def test_tool_fields_are_refused_not_dropped(field: str) -> None:
    request = TOOL_FIELDS[field]
    with pytest.raises(LlmConfigError, match="도구 칸"):
        GeminiProvider().build_request(request)
    fake = FakeGemini(gemini_response())
    response = GeminiProvider(fake).invoke(request, OPTIONS)
    assert isinstance(response, ProviderError)
    assert response.retryable is False
    assert fake.models.seen == []
