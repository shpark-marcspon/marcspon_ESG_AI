"""Anthropic·OpenAI 어댑터: 요청 조립과 응답 해석. 순수 층. esg-lab 의 test/adapters.test.ts(13건)를 옮긴 것이다.

실제 공급사로 가는 호출은 없다. SDK 클라이언트 자리에 가짜를 넣는다. 응답과 예외는 **진짜 SDK 의 타입**으로 만든다
(어댑터가 읽는 칸 이름이 설치된 SDK 와 맞는지도 같이 재려고). 토큰 수와 응답 본문은 전부 가상(synthetic) 값이다.
"""

from typing import Any

import anthropic
import httpx2
import openai
import pytest
from anthropic.types import Message
from openai.types.responses import Response, ResponseUsage
from openai.types.responses.response_usage import InputTokensDetails

from esgapi.core.llm.providers.anthropic import AnthropicProvider, AnthropicStream, create_anthropic_client
from esgapi.core.llm.providers.openai import OpenAIProvider, create_openai_client, create_openai_embedding_client
from esgapi.core.llm.types import (
    Completed,
    InvokeOptions,
    JsonSchemaSpec,
    PdfPart,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeout,
    Refusal,
    SystemSegment,
    TextPart,
    Usage,
)

SCHEMA: dict[str, object] = {"type": "object", "properties": {}, "additionalProperties": False}
REQUEST = ProviderRequest(
    api_model_id="model-synthetic",
    system=(
        SystemSegment(text="용어집", cache=True),
        SystemSegment(text="지침", cache=True),
        SystemSegment(text="오늘의 메모", cache=False),
    ),
    user=(PdfPart(base64="UERG", filename="report.pdf"), TextPart(text="표를 뽑아 줘")),
    max_output_tokens=2000,
    json_schema=JsonSchemaSpec(name="table", schema=SCHEMA),
)
PLAIN = ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10)
OPTIONS = InvokeOptions(timeout_ms=1000)
HTTP_REQUEST = httpx2.Request("POST", "https://provider.invalid/v1")


def http_response(status: int) -> httpx2.Response:
    return httpx2.Response(status, request=HTTP_REQUEST)


# ── Anthropic ──


def anthropic_message(**overrides: Any) -> Message:
    body: dict[str, Any] = {
        "id": "msg_synthetic",
        "type": "message",
        "role": "assistant",
        "model": "model-synthetic",
        "content": [{"type": "text", "text": '{"ok":true}', "citations": None}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 11,
            "output_tokens": 7,
            "cache_read_input_tokens": 300,
            "cache_creation_input_tokens": 40,
        },
    }
    return Message.model_validate({**body, **overrides})


class FakeAnthropicStream:
    """`with client.messages.stream(...) as stream:` 의 자리. 들어갈 때 심어 둔 예외를 던진다."""

    def __init__(self, reply: Message | Exception) -> None:
        self._reply = reply

    def __enter__(self) -> AnthropicStream:
        if isinstance(self._reply, Exception):
            raise self._reply
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get_final_message(self) -> Message:
        assert isinstance(self._reply, Message)
        return self._reply


class FakeAnthropicMessages:
    def __init__(self, reply: Message | Exception) -> None:
        self._reply = reply
        self.seen: list[dict[str, Any]] = []

    def stream(self, **kwargs: Any) -> FakeAnthropicStream:
        self.seen.append(kwargs)
        return FakeAnthropicStream(self._reply)


class FakeAnthropic:
    def __init__(self, reply: Message | Exception) -> None:
        self.messages = FakeAnthropicMessages(reply)


def run_anthropic(reply: Message | Exception) -> ProviderResponse:
    return AnthropicProvider(FakeAnthropic(reply)).invoke(REQUEST, OPTIONS)


def test_anthropic_request_cache_mark_on_last_cached_segment_pdf_before_text_schema_in_output_config() -> None:
    assert AnthropicProvider().build_request(REQUEST) == {
        "model": "model-synthetic",
        "max_tokens": 2000,
        "system": [
            {"type": "text", "text": "용어집"},
            {"type": "text", "text": "지침", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "오늘의 메모"},
        ],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "UERG"}},
                    {"type": "text", "text": "표를 뽑아 줘"},
                ],
            }
        ],
        "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
    }


def test_anthropic_request_omits_fields_without_cache_mark_and_schema() -> None:
    assert AnthropicProvider().build_request(PLAIN) == {
        "model": "m",
        "max_tokens": 10,
        "messages": [{"role": "user", "content": [{"type": "text", "text": "q"}]}],
    }


def test_anthropic_completed_response_and_usage() -> None:
    fake = FakeAnthropic(anthropic_message())
    response = AnthropicProvider(fake).invoke(REQUEST, OPTIONS)
    assert response == Completed(
        text='{"ok":true}',
        usage=Usage(input_tokens=11, output_tokens=7, cache_read_tokens=300, cache_write_tokens=40),
        model_id="model-synthetic",
    )
    # 조립한 본문이 그대로 SDK 로 가고, 시간 제한은 초 단위로 실린다(1000ms → 1초). 그 밖의 인자는 없다.
    assert fake.messages.seen == [{**AnthropicProvider().build_request(REQUEST), "timeout": 1.0}]


@pytest.mark.parametrize(
    ("stop_reason", "kind"),
    [
        ("max_tokens", "truncated"),
        ("model_context_window_exceeded", "truncated"),
        ("refusal", "refusal"),
        ("tool_use", "error"),
        (None, "error"),
    ],
)
def test_anthropic_stop_reason_maps_to_kind(stop_reason: str | None, kind: str) -> None:
    assert run_anthropic(anthropic_message(stop_reason=stop_reason)).kind == kind


def test_anthropic_refusal_category_comes_from_stop_details() -> None:
    details = {"type": "refusal", "category": "cyber", "explanation": None}
    refused = run_anthropic(anthropic_message(stop_reason="refusal", stop_details=details))
    assert isinstance(refused, Refusal)
    assert refused.category == "cyber"
    bare = run_anthropic(anthropic_message(stop_reason="refusal"))
    assert isinstance(bare, Refusal)
    assert bare.category is None


def test_anthropic_unreported_cache_tokens_stay_none() -> None:
    response = run_anthropic(anthropic_message(usage={"input_tokens": 11, "output_tokens": 7}))
    assert isinstance(response, Completed)
    assert (response.usage.cache_read_tokens, response.usage.cache_write_tokens) == (None, None)


def test_anthropic_sdk_exceptions_map_to_error_and_timeout() -> None:
    """뜻이 바뀐 것: 동기 이식이라 「호출 층이 중단시킨다」(APIUserAbortError)가 없다. SDK 의 시간 초과 예외가
    timeout 갈래다.
    """
    assert isinstance(run_anthropic(anthropic.APITimeoutError(request=HTTP_REQUEST)), ProviderTimeout)
    assert run_anthropic(anthropic.APIConnectionError(message="끊김", request=HTTP_REQUEST)) == ProviderError(
        status=None, retryable=True, message="끊김", error_kind="connection"
    )
    limited = run_anthropic(anthropic.RateLimitError("한도", response=http_response(429), body=None))
    assert limited == ProviderError(status=429, retryable=True, message="한도", error_kind="rate_limited")
    overloaded = run_anthropic(anthropic.APIStatusError("과부하", response=http_response(529), body=None))
    assert overloaded == ProviderError(status=529, retryable=True, message="과부하", error_kind="overloaded")
    bad = run_anthropic(anthropic.BadRequestError("잘못된 요청", response=http_response(400), body=None))
    assert bad == ProviderError(status=400, retryable=False, message="잘못된 요청")
    assert run_anthropic(RuntimeError("알 수 없음")) == ProviderError(
        status=None, retryable=False, message="알 수 없음"
    )


def test_anthropic_without_client_returns_error_and_does_not_call() -> None:
    response = AnthropicProvider().invoke(REQUEST, OPTIONS)
    assert isinstance(response, ProviderError)
    assert response.retryable is False


# ── OpenAI ──

OPENAI_USAGE: dict[str, Any] = {
    "input_tokens": 500,
    "input_tokens_details": {"cached_tokens": 300, "cache_write_tokens": 40},
    "output_tokens": 7,
    "output_tokens_details": {"reasoning_tokens": 0},
    "total_tokens": 507,
}


def openai_response(**overrides: Any) -> Response:
    message: dict[str, Any] = {
        "type": "message",
        "id": "msg",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": '{"ok":true}', "annotations": []}],
    }
    body: dict[str, Any] = {
        "id": "resp_synthetic",
        "object": "response",
        "created_at": 0,
        "model": "model-synthetic-snapshot",
        "status": "completed",
        "incomplete_details": None,
        "output": [message],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "usage": OPENAI_USAGE,
    }
    return Response.model_validate({**body, **overrides})


class FakeOpenAIResponses:
    def __init__(self, reply: Response | Exception) -> None:
        self._reply = reply
        self.seen: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Response:
        self.seen.append(kwargs)
        if isinstance(self._reply, Exception):
            raise self._reply
        return self._reply


class FakeOpenAI:
    def __init__(self, reply: Response | Exception) -> None:
        self.responses = FakeOpenAIResponses(reply)


def run_openai(reply: Response | Exception) -> ProviderResponse:
    return OpenAIProvider(FakeOpenAI(reply)).invoke(REQUEST, OPTIONS)


def test_openai_request_instructions_joined_pdf_as_input_file_schema_in_text_format() -> None:
    assert OpenAIProvider().build_request(REQUEST) == {
        "model": "model-synthetic",
        "max_output_tokens": 2000,
        "store": False,
        "instructions": "용어집\n\n지침\n\n오늘의 메모",
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_file", "filename": "report.pdf", "file_data": "data:application/pdf;base64,UERG"},
                    {"type": "input_text", "text": "표를 뽑아 줘"},
                ],
            }
        ],
        "text": {"format": {"type": "json_schema", "name": "table", "schema": SCHEMA, "strict": True}},
    }


def test_openai_completed_subtracts_cache_read_and_write_from_input() -> None:
    fake = FakeOpenAI(openai_response())
    response = OpenAIProvider(fake).invoke(REQUEST, OPTIONS)
    assert response == Completed(
        text='{"ok":true}',
        usage=Usage(input_tokens=160, output_tokens=7, cache_read_tokens=300, cache_write_tokens=40, thinking_tokens=0),
        model_id="model-synthetic-snapshot",
    )
    assert fake.responses.seen == [{**OpenAIProvider().build_request(REQUEST), "timeout": 1.0}]


def test_openai_reasoning_tokens_stay_in_output_and_are_also_recorded_only_when_reported() -> None:
    usage = {**OPENAI_USAGE, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}, "output_tokens": 24}
    reasoned = run_openai(openai_response(usage={**usage, "output_tokens_details": {"reasoning_tokens": 17}}))
    assert isinstance(reasoned, Completed)
    assert (reasoned.usage.output_tokens, reasoned.usage.thinking_tokens) == (24, 17)

    # 공급사가 추론 토큰 칸을 보내지 않은 응답. SDK 의 타입은 그 칸을 필수로 적지만 실제 응답은 검증 없이 만들어진다.
    silent_usage = ResponseUsage.model_construct(
        input_tokens=500,
        input_tokens_details=InputTokensDetails(cached_tokens=0, cache_write_tokens=0),
        output_tokens=24,
        total_tokens=524,
    )
    silent = run_openai(openai_response().model_copy(update={"usage": silent_usage}))
    assert isinstance(silent, Completed)
    assert (silent.usage.output_tokens, silent.usage.thinking_tokens) == (24, None)
    assert "thinkingTokens" not in silent.usage.to_json()


def test_openai_tells_refusal_truncation_incomplete_and_missing_usage_apart() -> None:
    refusal_message = {
        "type": "message",
        "id": "m",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "refusal", "refusal": "거절"}],
    }
    refused = run_openai(openai_response(output=[refusal_message]))
    assert isinstance(refused, Refusal)
    assert (refused.text, refused.category) == ("거절", None)
    truncated = run_openai(openai_response(status="incomplete", incomplete_details={"reason": "max_output_tokens"}))
    assert truncated.kind == "truncated"
    filtered = run_openai(openai_response(status="incomplete", incomplete_details={"reason": "content_filter"}))
    assert isinstance(filtered, Refusal)
    assert filtered.category == "content_filter"
    assert run_openai(openai_response(status="failed")).kind == "error"
    assert run_openai(openai_response(usage=None)).kind == "error"


def test_openai_sdk_exceptions_map_to_error_and_timeout() -> None:
    assert isinstance(run_openai(openai.APITimeoutError(request=HTTP_REQUEST)), ProviderTimeout)
    disconnected = run_openai(openai.APIConnectionError(message="끊김", request=HTTP_REQUEST))
    assert disconnected == ProviderError(status=None, retryable=True, message="끊김", error_kind="connection")
    server = run_openai(openai.InternalServerError("서버", response=http_response(500), body=None))
    assert server == ProviderError(status=500, retryable=True, message="서버", error_kind="server_error")
    limited = run_openai(openai.RateLimitError("한도", response=http_response(429), body=None))
    assert limited == ProviderError(status=429, retryable=True, message="한도", error_kind="rate_limited")
    denied = run_openai(openai.AuthenticationError("인증", response=http_response(401), body=None))
    assert denied == ProviderError(status=401, retryable=False, message="인증")


def test_openai_without_client_returns_error_and_does_not_call() -> None:
    response = OpenAIProvider().invoke(REQUEST, OPTIONS)
    assert isinstance(response, ProviderError)
    assert response.retryable is False


# ── 키가 오류 문장에 남지 않는다 ──

KEY_SK = "sk-proj-synthetic0000aaaa1111"


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_key_in_sdk_error_message_never_reaches_the_result(provider: str) -> None:
    text = f"Incorrect API key provided: {KEY_SK}. You can find your key at"
    if provider == "openai":
        response = run_openai(openai.AuthenticationError(text, response=http_response(401), body=None))
    else:
        response = run_anthropic(anthropic.AuthenticationError(text, response=http_response(401), body=None))
    assert isinstance(response, ProviderError)
    assert KEY_SK not in response.message
    assert response.message == "Incorrect API key provided: sk-[가림] You can find your key at"


# ── SDK 클라이언트는 받은 키만 쓴다 ──


def test_sdk_clients_use_the_given_key_not_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-environment-synthetic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-environment-synthetic")
    made_openai: Any = create_openai_client("sk-given-synthetic")
    made_anthropic: Any = create_anthropic_client("sk-ant-given-synthetic")
    assert made_openai.api_key == "sk-given-synthetic"
    assert made_anthropic.api_key == "sk-ant-given-synthetic"
    # 채팅 SDK 의 자체 재시도는 끈다(0 — 재시도는 호출 층 retry.py 가 시도마다 상한 확인·기록 줄과). 임베딩은 SDK 기본
    # 2 를 명시.
    assert (made_openai.max_retries, made_anthropic.max_retries) == (0, 0)
    made_embedding: Any = create_openai_embedding_client("sk-given-synthetic")
    assert made_embedding.max_retries == 0  # LB1 Q5 — 임베딩도 호출 층이 다시 부른다
    assert (openai.DEFAULT_MAX_RETRIES, anthropic.DEFAULT_MAX_RETRIES) == (2, 2)


# ── 조립한 본문의 열쇠가 설치된 SDK 의 인자 이름과 맞는가 ──


def test_request_bodies_use_only_argument_names_the_installed_sdk_accepts() -> None:
    """가짜 SDK 는 어떤 인자든 받는다. 그래서 진짜 SDK 의 메서드가 그 이름의 인자를 가졌는지 따로 본다(네트워크
    없음).
    """
    import inspect

    real_openai: Any = create_openai_client("sk-given-synthetic")
    real_anthropic: Any = create_anthropic_client("sk-ant-given-synthetic")
    openai_names = set(inspect.signature(real_openai.responses.create).parameters)
    anthropic_names = set(inspect.signature(real_anthropic.messages.stream).parameters)
    assert {*OpenAIProvider().build_request(REQUEST), "timeout"} <= openai_names
    assert {*AnthropicProvider().build_request(REQUEST), "timeout"} <= anthropic_names
    # 견줄 것이 있었는지: 본문의 열쇠가 여섯·다섯이다(스키마와 지침이 다 든 요청).
    assert len(OpenAIProvider().build_request(REQUEST)) == 6
    assert len(AnthropicProvider().build_request(REQUEST)) == 5
