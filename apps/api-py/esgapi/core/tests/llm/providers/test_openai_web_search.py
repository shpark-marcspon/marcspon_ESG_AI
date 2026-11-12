"""web_search 의 `user_location`(밴드 IR1b `MARC-TICK-282` 의 71-4): 줄 때만 싣고, 안 주면 바이트가 그대로다. 순수 층.

실제 공급사로 가는 호출은 없다. 꼴은 설치된 SDK 의 `types/responses/web_search_tool_param.py`
(`UserLocation` — `type: Literal["approximate"]`, `country` 두 글자) 와 받은 코랩 셀 8 의 도구 정의
(키 차례 type → country).
"""

import json
from dataclasses import replace

from esgapi.core.llm.log import sha256_json
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.types import (
    ApproximateLocation,
    ProviderRequest,
    SystemSegment,
    TextPart,
    WebSearchTool,
    tool_json,
)

BASE = ProviderRequest(
    api_model_id="model-synthetic",
    system=(SystemSegment(text="지침", cache=False),),
    user=(TextPart(text="가상 질문"),),
    max_output_tokens=500,
    tools=(WebSearchTool(search_context_size="low"),),
)
LOCATED = replace(
    BASE, tools=(WebSearchTool(search_context_size="low", user_location=ApproximateLocation(country="KR")),)
)

# 이 밴드 앞(main 99fa3660)의 중립 꼴 — user_location 이 없을 때 이 글자가 바뀌면 요청 해시가 바뀐다.
NEUTRAL_BEFORE = '[{"type":"web_search","searchContextSize":"low"}]'


def test_the_location_is_carried_after_the_context_size_in_the_sdk_shape() -> None:
    params = OpenAIProvider().build_request(LOCATED)
    assert params["tools"] == [
        {"type": "web_search", "search_context_size": "low", "user_location": {"type": "approximate", "country": "KR"}}
    ]
    tools = params["tools"]
    assert isinstance(tools, list)
    assert json.dumps(tools[0]) == (
        '{"type": "web_search", "search_context_size": "low", '
        '"user_location": {"type": "approximate", "country": "KR"}}'
    )


def test_without_a_location_the_adapter_body_and_the_neutral_body_are_unchanged() -> None:
    params = OpenAIProvider().build_request(BASE)
    assert params["tools"] == [{"type": "web_search", "search_context_size": "low"}]
    assert json.dumps(BASE.to_json()["tools"], ensure_ascii=False, separators=(",", ":")) == NEUTRAL_BEFORE
    assert tool_json(WebSearchTool()) == {"type": "web_search", "searchContextSize": "medium"}


def test_the_location_enters_the_neutral_body_so_the_request_hash_tells_them_apart() -> None:
    assert LOCATED.to_json()["tools"] == [
        {"type": "web_search", "searchContextSize": "low", "userLocation": {"type": "approximate", "country": "KR"}}
    ]
    assert sha256_json(LOCATED.to_json()) != sha256_json(BASE.to_json())
    other = replace(LOCATED, tools=(WebSearchTool(search_context_size="low", user_location=ApproximateLocation("US")),))
    assert sha256_json(other.to_json()) != sha256_json(LOCATED.to_json())
