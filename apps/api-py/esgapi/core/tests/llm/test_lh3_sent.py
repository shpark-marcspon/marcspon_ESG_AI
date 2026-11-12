# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
"""요청을 만들다(조립) 던진 오류는 나가지 않은 요청이다(밴드 LH3 T3 — MARC-ISSUE-413 I2). 순수 층.

  T3  어댑터 넷(openai·openai 임베딩·anthropic·gemini — 진짜 SDK + 가짜 HTTP)의 조립이 던짐 → `sent is False`,
      status·retryable·message 는 BASE 값(_map_error 의 마지막 갈래 그대로), SDK 부름(HTTP) 0 · 호출 층의 줄
      `cost_bound_usd` None(BASE 는 나간 상태 없는 오류로 보고 어림을 실었다 — 대조) · 조립 중의 소프트 제한은 그대로
      올라옴 · SDK 부름의 오류는 BASE 처럼 `sent=True`
★ 조립 함수(build_request·_sdk_arguments)를 시험 안에서만 던지게 바꾼다. 네트워크 0 — blocked_network 가 빈다.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import anthropic
import httpx
import httpx2
import openai
import pytest
from celery.exceptions import SoftTimeLimitExceeded
from google import genai
from google.genai import types as genai_types

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.embedding_types import EmbeddingProviderRequest
from esgapi.core.llm.providers.anthropic import AnthropicProvider
from esgapi.core.llm.providers.gemini import GeminiProvider
from esgapi.core.llm.providers.openai import OpenAIEmbeddingProvider, OpenAIProvider
from esgapi.core.llm.types import InvokeOptions, ProviderError, ProviderRequest, TextPart
from esgapi.core.tests.llm_support import TAGS, harness, write_prompts

OPTIONS = InvokeOptions(timeout_ms=10_000)
PLAIN = ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10)
EMBED = EmbeddingProviderRequest(api_model_id="e", inputs=("x",), dimensions=3)
ASSEMBLY = "조립 합성 오류"


class Seen:
    """가짜 HTTP 가 받은 요청 수(SDK 부름이 공급사로 나가려 했는가)."""

    def __init__(self) -> None:
        self.count = 0

    def refuse(self, status: int) -> Callable[[Any], Any]:
        def handler(request: Any) -> Any:
            self.count += 1
            module = httpx2 if isinstance(request, httpx2.Request) else httpx
            return module.Response(status, json={"error": {"message": "합성 거절"}})

        return handler


def openai_provider(seen: Seen, status: int = 400) -> OpenAIProvider:
    sdk = openai.OpenAI(
        api_key="openai-key-synthetic",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(seen.refuse(status))),  # pyright: ignore[reportArgumentType]
    )
    return OpenAIProvider(sdk)  # pyright: ignore[reportArgumentType]


def embedding_provider(seen: Seen, status: int = 400) -> OpenAIEmbeddingProvider:
    sdk = openai.OpenAI(
        api_key="openai-key-synthetic",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(seen.refuse(status))),  # pyright: ignore[reportArgumentType]
    )
    return OpenAIEmbeddingProvider(sdk)  # pyright: ignore[reportArgumentType]


def anthropic_provider(seen: Seen, status: int = 400) -> AnthropicProvider:
    sdk = anthropic.Anthropic(
        api_key="anthropic-key-synthetic",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(seen.refuse(status))),
    )
    return AnthropicProvider(sdk)  # pyright: ignore[reportArgumentType]


def gemini_provider(seen: Seen, status: int = 400) -> GeminiProvider:
    sdk = genai.Client(
        api_key="gemini-key-synthetic",
        vertexai=False,
        http_options=genai_types.HttpOptions(
            httpx_client=httpx.Client(transport=httpx.MockTransport(seen.refuse(status)))
        ),
    )
    return GeminiProvider(sdk)  # pyright: ignore[reportArgumentType]


def raising(error: BaseException) -> Callable[..., Any]:
    def handler(*_: object, **__: object) -> Any:
        raise error

    return handler


def broken(adapter: str, seen: Seen, error: BaseException) -> Callable[[], object]:
    """조립이 `error` 를 던지는 어댑터를 부르는 함수."""
    if adapter == "openai":
        provider = openai_provider(seen)
        provider.build_request = raising(error)  # pyright: ignore[reportAttributeAccessIssue]
        return lambda: provider.invoke(PLAIN, OPTIONS)
    if adapter == "openai-embedding":
        embedder = embedding_provider(seen)
        embedder.build_request = raising(error)  # pyright: ignore[reportAttributeAccessIssue]
        return lambda: embedder.embed(EMBED, OPTIONS)
    if adapter == "anthropic":
        claude = anthropic_provider(seen)
        claude.build_request = raising(error)  # pyright: ignore[reportAttributeAccessIssue]
        return lambda: claude.invoke(PLAIN, OPTIONS)
    gemini = gemini_provider(seen)
    gemini._sdk_arguments = raising(error)  # pyright: ignore[reportAttributeAccessIssue]
    return lambda: gemini.invoke(PLAIN, OPTIONS)


ADAPTERS = ["openai", "openai-embedding", "anthropic", "gemini"]


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_t3_an_assembly_error_is_not_sent_and_keeps_the_base_values(
    blocked_network: list[object], adapter: str
) -> None:
    seen = Seen()
    result = broken(adapter, seen, RuntimeError(ASSEMBLY))()
    assert isinstance(result, ProviderError)
    # BASE 값: _map_error 의 마지막 갈래(상태 없음·재시도 불가·글 그대로)
    assert (result.status, result.retryable, result.message, result.retry_after_ms) == (None, False, ASSEMBLY, None)
    assert result.sent is False
    assert seen.count == 0
    assert blocked_network == []


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_t3_a_soft_limit_during_assembly_is_raised_as_is(blocked_network: list[object], adapter: str) -> None:
    seen = Seen()
    deadline = SoftTimeLimitExceeded("합성 소프트 제한")
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        broken(adapter, seen, deadline)()
    assert raised.value is deadline
    assert seen.count == 0
    assert blocked_network == []


def calls(adapter: str, seen: Seen, status: int) -> Callable[[], object]:
    if adapter == "openai":
        return lambda: openai_provider(seen, status).invoke(PLAIN, OPTIONS)
    if adapter == "openai-embedding":
        return lambda: embedding_provider(seen, status).embed(EMBED, OPTIONS)
    if adapter == "anthropic":
        return lambda: anthropic_provider(seen, status).invoke(PLAIN, OPTIONS)
    return lambda: gemini_provider(seen, status).invoke(PLAIN, OPTIONS)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_t3_an_error_from_the_sdk_call_stays_sent_like_base(blocked_network: list[object], adapter: str) -> None:
    seen = Seen()
    result = calls(adapter, seen, 400)()
    assert isinstance(result, ProviderError)
    assert (result.status, result.sent) == (400, True)
    assert seen.count == 1
    assert blocked_network == []


def test_t3_the_client_line_of_an_assembly_error_has_no_bound(tmp_path: Path, blocked_network: list[object]) -> None:
    seen = Seen()
    provider = openai_provider(seen)
    provider.build_request = raising(RuntimeError(ASSEMBLY))  # pyright: ignore[reportAttributeAccessIssue]
    h = harness(write_prompts(tmp_path), providers={"mock": provider})
    result = h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS))
    assert result.kind == "provider_error"
    (record,) = h.log.records
    assert (record.result_kind, record.cost_usd, record.cost_bound_usd) == ("provider_error", None, None)
    assert seen.count == 0
    assert blocked_network == []
