# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Celery 소프트 시간 제한을 호출 층이 삼키지 않는다(밴드 LH2 S8·S10 — MARC-ISSUE-411 S3). 순수 층.

  S8  시험용 같은 이름 클래스와 진짜 celery.exceptions.SoftTimeLimitExceeded 둘로: 어댑터 넷(openai 날 예외·anthropic
      send 의 APIConnectionError(…) from 제한·anthropic 스트림 중간·gemini·openai 임베딩 — 진짜 SDK + 가짜 HTTP 또는
      가짜 SDK)·client._invoke·embedding._invoke·도구 실행 자리 → 그 예외가 그대로 올라온다. 같은 모델 재시도 0·대체
      모델 0, 그 시도의 timeout 줄 하나(어림 포함 — Q8)
  S10 회귀  원인 없는 APIConnectionError 는 BASE 처럼 재시도 가능(Q7 가) · 이름이 다른 예외는 BASE 처럼 공급사 오류
★ core 는 celery 를 import 하지 않는다(이름으로 가른다) — 이 시험만 진짜 예외를 가져와 같이 잰다.
★ 네트워크 0: 뿌리 conftest 의 blocked_network 를 끝에 비었는지 본다. 키는 지어낸 글자다.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import anthropic
import httpx
import httpx2
import openai
import pytest
from celery.exceptions import SoftTimeLimitExceeded as CelerySoftLimit
from google import genai
from google.genai import types as genai_types

from esgapi.core.llm.client import CallRequest, ToolCallRequest
from esgapi.core.llm.embedding import EmbeddingClient, EmbedRequest
from esgapi.core.llm.embedding_types import EmbeddingProviderRequest
from esgapi.core.llm.errors import soft_deadline_in
from esgapi.core.llm.providers.anthropic import AnthropicProvider
from esgapi.core.llm.providers.gemini import GeminiProvider
from esgapi.core.llm.providers.mock import MockEmbeddingProvider, MockProvider
from esgapi.core.llm.providers.openai import OpenAIEmbeddingProvider, OpenAIProvider
from esgapi.core.llm.retry import DEFAULT_PROVIDER_RETRY
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import FunctionTool, InvokeOptions, ProviderError, ProviderRequest, TextPart
from esgapi.core.resources.ports.llm import Provider
from esgapi.core.tests.llm_support import TAGS, harness, synthetic_config, write_prompts


class SoftTimeLimitExceeded(Exception):
    """시험용: 진짜 것과 이름만 같은 클래스."""


class TimeLimitExceeded(Exception):
    """이름이 다른 예외(S10) — 공급사 오류로 삼켜져야 한다."""


KINDS = [pytest.param(SoftTimeLimitExceeded, id="same-name"), pytest.param(CelerySoftLimit, id="celery")]
OPTIONS = InvokeOptions(timeout_ms=10_000)
PLAIN = ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10)
EMBED = EmbeddingProviderRequest(api_model_id="e", inputs=("x",), dimensions=3)
RETRY = {"mock": DEFAULT_PROVIDER_RETRY["openai"], "mock-b": DEFAULT_PROVIDER_RETRY["openai"]}


@pytest.fixture
def prompts(tmp_path: Path) -> Path:
    return write_prompts(tmp_path)


def raising(error: BaseException) -> Callable[..., Any]:
    def handler(*_: object, **__: object) -> Any:
        raise error

    return handler


# ── 판별 ──


@pytest.mark.parametrize("kind", KINDS)
def test_s8_the_name_is_found_on_the_error_and_down_its_chain(kind: type[Exception]) -> None:
    deadline = kind("합성")
    assert soft_deadline_in(deadline) is deadline
    wrapped = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://provider.invalid"))
    wrapped.__cause__ = deadline
    assert soft_deadline_in(wrapped) is deadline
    outer = RuntimeError("겉")
    outer.__context__ = wrapped
    assert soft_deadline_in(outer) is deadline


def test_s8_a_chain_loop_or_other_names_find_nothing() -> None:
    a, b = RuntimeError("a"), RuntimeError("b")
    a.__cause__, b.__cause__ = b, a
    assert soft_deadline_in(a) is None
    assert soft_deadline_in(TimeLimitExceeded("합성")) is None


# ── 어댑터 넷(진짜 SDK + 가짜 HTTP, gemini 는 진짜 SDK 에 가짜 httpx 클라이언트) ──


def openai_sdk(error: BaseException, retries: int = 0) -> openai.OpenAI:
    transport = httpx.MockTransport(raising(error))
    return openai.OpenAI(
        api_key="openai-key-synthetic",
        max_retries=retries,
        http_client=httpx.Client(transport=transport),  # pyright: ignore[reportArgumentType]
    )


def anthropic_sdk(handler: Callable[..., Any]) -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key="anthropic-key-synthetic",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )


class Midway(httpx2.SyncByteStream):
    def __init__(self, error: BaseException) -> None:
        self._error = error

    def __iter__(self) -> Any:
        yield (
            b"event: message_start\n"
            b'data: {"type":"message_start","message":{"id":"msg_synthetic","type":"message","role":"assistant",'
            b'"model":"claude-synthetic","content":[],"stop_reason":null,"stop_sequence":null,'
            b'"usage":{"input_tokens":1,"output_tokens":1}}}\n\n'
        )
        raise self._error


def adapters(error: BaseException) -> dict[str, Callable[[], object]]:
    gemini_client = genai.Client(
        api_key="gemini-key-synthetic",
        vertexai=False,
        http_options=genai_types.HttpOptions(httpx_client=httpx.Client(transport=httpx.MockTransport(raising(error)))),
    )

    def midway(_: object) -> Any:
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=Midway(error))

    return {
        "openai": lambda: OpenAIProvider(openai_sdk(error)).invoke(PLAIN, OPTIONS),  # pyright: ignore[reportArgumentType]
        "anthropic-send": lambda: AnthropicProvider(anthropic_sdk(raising(error))).invoke(PLAIN, OPTIONS),  # pyright: ignore[reportArgumentType]
        "anthropic-stream": lambda: AnthropicProvider(anthropic_sdk(midway)).invoke(PLAIN, OPTIONS),  # pyright: ignore[reportArgumentType]
        "gemini": lambda: GeminiProvider(gemini_client).invoke(PLAIN, OPTIONS),  # pyright: ignore[reportArgumentType]
        "openai-embedding": lambda: OpenAIEmbeddingProvider(openai_sdk(error, retries=2)).embed(EMBED, OPTIONS),  # pyright: ignore[reportArgumentType]
    }


ADAPTERS = ["openai", "anthropic-send", "anthropic-stream", "gemini", "openai-embedding"]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("adapter", ADAPTERS)
def test_s8_each_adapter_raises_the_soft_limit_instead_of_an_error_value(
    blocked_network: list[object], kind: type[Exception], adapter: str
) -> None:
    deadline = kind("합성 소프트 제한")
    with pytest.raises(kind) as raised:
        adapters(deadline)[adapter]()
    assert raised.value is deadline
    assert blocked_network == []


@pytest.mark.parametrize("kind", KINDS)
def test_s8_anthropic_send_soft_limit_is_not_retried_or_handed_to_the_fallback(
    prompts: Path, blocked_network: list[object], kind: type[Exception]
) -> None:
    """BASE 는 send 중의 제한이 APIConnectionError(재시도 가능)로 싸여 같은 모델 둘·대체 모델로 갔다(★c)."""
    sent: list[object] = []

    def handler(request: object) -> Any:
        sent.append(request)
        raise kind("합성")

    fallback = MockProvider("mock-b")
    providers: dict[str, Provider] = {"mock": AnthropicProvider(anthropic_sdk(handler)), "mock-b": fallback}  # pyright: ignore[reportArgumentType]
    h = harness(prompts, providers=providers, provider_retry=RETRY)
    with pytest.raises(kind):
        h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock-with-fallback", tags=TAGS))
    assert (len(sent), fallback.calls, h.sleeps) == (1, [], [])
    (record,) = h.log.records
    assert (record.result_kind, record.model, record.cost_usd) == ("timeout", "mock-synthetic", None)
    assert record.cost_bound_usd is not None and record.cost_bound_usd > 0
    assert blocked_network == []


# ── 호출 층의 세 자리 ──


@pytest.mark.parametrize("kind", KINDS)
def test_s8_client_invoke_reraises_and_writes_one_timeout_line(
    prompts: Path, blocked_network: list[object], kind: type[Exception]
) -> None:
    deadline = kind("합성")
    h = harness(prompts, provider_retry=RETRY)
    h.mock.enqueue(raising(deadline))
    with pytest.raises(kind) as raised:
        h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock-with-fallback", tags=TAGS))
    assert raised.value is deadline
    assert (len(h.mock.calls), h.mock_b.calls, h.sleeps) == (1, [], [])
    (record,) = h.log.records
    assert (record.result_kind, record.attempt, record.provider, record.cost_usd) == ("timeout", 0, "mock", None)
    assert record.cost_bound_usd is not None and record.cost_bound_usd > 0
    assert blocked_network == []


@pytest.mark.parametrize("kind", KINDS)
def test_s8_embedding_invoke_reraises_and_writes_one_timeout_line(
    blocked_network: list[object], kind: type[Exception]
) -> None:
    deadline = kind("합성")
    mock = MockEmbeddingProvider()
    mock.enqueue(raising(deadline))
    sink = MemorySink()
    client = EmbeddingClient(config=synthetic_config(), providers={"mock": mock}, log=sink)
    with pytest.raises(kind) as raised:
        client.embed(EmbedRequest(inputs=("합성 하나", "합성 둘"), route="mock-gw1", tags=TAGS, batch_size=1))
    assert raised.value is deadline
    assert len(mock.calls) == 1  # 다음 묶음으로 가지 않았다
    (record,) = sink.records
    assert (record.result_kind, record.provider, record.cost_usd) == ("timeout", "mock", None)
    assert record.cost_bound_usd is not None and record.cost_bound_usd > 0
    assert blocked_network == []


@pytest.mark.parametrize("kind", KINDS)
def test_s8_the_tool_executor_soft_limit_is_not_turned_into_a_failure(prompts: Path, kind: type[Exception]) -> None:
    deadline = kind("합성")
    tool = FunctionTool(name="lookup", description="합성 도구", parameters={"type": "object", "properties": {}})
    h = harness(prompts)
    h.mock.enqueue_tool_calls([("lookup", "{}")])
    request = ToolCallRequest(
        prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS, tools=(tool,), max_steps=3
    )
    with pytest.raises(kind) as raised:
        h.client.call_tools(request, raising(deadline))
    assert raised.value is deadline
    assert len(h.mock.calls) == 1


# ── S10 회귀 ──


def test_s10_a_connection_error_without_a_cause_stays_retryable() -> None:
    class Fake:
        class messages:
            @staticmethod
            def stream(**_: object) -> Any:
                raise anthropic.APIConnectionError(
                    message="끊김", request=httpx2.Request("POST", "https://provider.invalid")
                )

    result = AnthropicProvider(Fake()).invoke(PLAIN, OPTIONS)  # pyright: ignore[reportArgumentType]
    assert result == ProviderError(status=None, retryable=True, message="끊김", error_kind="connection")
    assert isinstance(result, ProviderError) and result.sent is True


def test_s10_another_exception_name_is_still_a_provider_error(prompts: Path) -> None:
    h = harness(prompts, provider_retry={})
    h.mock.enqueue(raising(TimeLimitExceeded("합성")))
    result = h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS))
    assert result.kind == "provider_error"
    for name, client in (("openai", openai_sdk(TimeLimitExceeded("합성"))),):
        answer = OpenAIProvider(client).invoke(PLAIN, OPTIONS)  # pyright: ignore[reportArgumentType]
        assert isinstance(answer, ProviderError) and answer.status is None, name
