"""Gemini 어댑터, 키 가리기, 호출 간격 조절. 순수 층. esg-lab 의 test/gemini.test.ts(11건)를 옮긴 것이다.

실제 공급사로 가는 호출은 없다. SDK 클라이언트 자리에 가짜를 넣는다. 응답과 예외는 진짜 SDK 의 타입으로 만든다.
토큰 수와 응답 본문은 전부 가상(synthetic) 값이다.
"""

import socket
from typing import Any

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from esgapi.core.llm.providers.gemini import GeminiProvider, create_gemini_client
from esgapi.core.llm.providers.redact import redact_keys
from esgapi.core.llm.schema import strip_unsupported_schema_keys
from esgapi.core.llm.throttle import throttled
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
    Truncated,
    Usage,
)

SCHEMA: dict[str, object] = {"type": "object", "properties": {}, "additionalProperties": False}
REQUEST = ProviderRequest(
    api_model_id="model-synthetic",
    system=(SystemSegment(text="용어집", cache=True), SystemSegment(text="오늘의 메모", cache=False)),
    user=(PdfPart(base64="UERG", filename="report.pdf"), TextPart(text="표를 뽑아 줘")),
    max_output_tokens=2000,
    json_schema=JsonSchemaSpec(name="table", schema=SCHEMA),
)
PLAIN = ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10)
OPTIONS = InvokeOptions(timeout_ms=30_000)


def gemini_response(**overrides: Any) -> genai_types.GenerateContentResponse:
    parts = [{"text": "생각 (synthetic)", "thought": True}, {"text": '{"ok":'}, {"text": "true}"}]
    body: dict[str, Any] = {
        "modelVersion": "model-synthetic-001",
        "candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": parts}}],
        "usageMetadata": {
            "promptTokenCount": 500,
            "cachedContentTokenCount": 300,
            "candidatesTokenCount": 7,
            "thoughtsTokenCount": 5,
            "totalTokenCount": 512,
        },
    }
    merged = {**body, **overrides}
    return genai_types.GenerateContentResponse.model_validate({k: v for k, v in merged.items() if v is not None})


class FakeGeminiModels:
    def __init__(self, reply: genai_types.GenerateContentResponse | Exception) -> None:
        self._reply = reply
        self.seen: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> genai_types.GenerateContentResponse:
        self.seen.append(kwargs)
        if isinstance(self._reply, Exception):
            raise self._reply
        return self._reply


class FakeGemini:
    def __init__(self, reply: genai_types.GenerateContentResponse | Exception) -> None:
        self.models = FakeGeminiModels(reply)


def run(reply: genai_types.GenerateContentResponse | Exception) -> ProviderResponse:
    return GeminiProvider(FakeGemini(reply)).invoke(REQUEST, OPTIONS)


def finished(reason: str) -> genai_types.GenerateContentResponse:
    candidate = {"finishReason": reason, "content": {"role": "model", "parts": [{"text": "1, 2, 3"}]}}
    return gemini_response(candidates=[candidate])


def api_error(status: int, message: str) -> genai_errors.APIError:
    return genai_errors.APIError(status, {"error": {"code": status, "message": message}})


# ── Gemini 어댑터 ──


def test_request_system_instruction_joined_pdf_as_inline_data_schema_as_response_json_schema() -> None:
    assert GeminiProvider().build_request(REQUEST) == {
        "model": "model-synthetic",
        "contents": [
            {
                "role": "user",
                "parts": [{"inlineData": {"mimeType": "application/pdf", "data": "UERG"}}, {"text": "표를 뽑아 줘"}],
            }
        ],
        "config": {
            "maxOutputTokens": 2000,
            "systemInstruction": "용어집\n\n오늘의 메모",
            "responseMimeType": "application/json",
            "responseJsonSchema": SCHEMA,
        },
    }


def test_request_omits_fields_without_instruction_and_schema() -> None:
    assert GeminiProvider().build_request(PLAIN) == {
        "model": "m",
        "contents": [{"role": "user", "parts": [{"text": "q"}]}],
        "config": {"maxOutputTokens": 10},
    }


def test_completed_text_without_thoughts_uncached_input_output_plus_thinking_and_model_id() -> None:
    fake = FakeGemini(gemini_response())
    assert GeminiProvider(fake).invoke(REQUEST, OPTIONS) == Completed(
        text='{"ok":true}',
        usage=Usage(input_tokens=200, output_tokens=12, cache_read_tokens=300, cache_write_tokens=0, thinking_tokens=5),
        model_id="model-synthetic-001",
    )


def test_sdk_receives_typed_arguments_decoded_bytes_and_the_timeout() -> None:
    """뜻이 바뀐 것: esg-lab 은 중단 신호만 걸고 마감 시간을 싣지 않았다. 동기 호출은 신호가 없어
    http_options.timeout 으로 건다.

    SDK 에 넘어가는 값을 SDK 자신의 타입으로 다시 읽어, 어댑터가 쓴 칸 이름이 설치된 SDK 와 맞는지도 잰다.
    """
    fake = FakeGemini(gemini_response())
    GeminiProvider(fake).invoke(REQUEST, OPTIONS)
    (sent,) = fake.models.seen
    assert set(sent) == {"model", "contents", "config"}
    assert sent["model"] == "model-synthetic"
    (content,) = sent["contents"]
    assert isinstance(content, genai_types.Content)
    assert content.role == "user"
    assert content.parts is not None
    pdf, text = content.parts
    # 파이썬 SDK 는 첨부를 바이트로 받는다. base64 글자 "UERG" 를 풀면 b"PDF" 다.
    assert pdf.inline_data == genai_types.Blob(mime_type="application/pdf", data=b"PDF")
    assert text.text == "표를 뽑아 줘"
    config = sent["config"]
    assert isinstance(config, genai_types.GenerateContentConfig)
    assert config.model_dump(exclude_none=True) == {
        "max_output_tokens": 2000,
        "system_instruction": "용어집\n\n오늘의 메모",
        "response_mime_type": "application/json",
        "response_json_schema": SCHEMA,
        "http_options": {"timeout": 30_000},
    }


def test_missing_cache_field_counts_as_zero_cache_read() -> None:
    usage = {"promptTokenCount": 40, "candidatesTokenCount": 3, "totalTokenCount": 43}
    result = run(gemini_response(usageMetadata=usage))
    assert isinstance(result, Completed)
    # 공급사가 생각 토큰 필드를 보내지 않으면 0 으로 지어내지 않고 남기지 않는다.
    assert result.usage == Usage(input_tokens=40, output_tokens=3, cache_read_tokens=0, cache_write_tokens=0)
    assert "thinkingTokens" not in result.usage.to_json()


def test_response_cut_at_output_limit_is_truncated() -> None:
    result = run(finished("MAX_TOKENS"))
    assert isinstance(result, Truncated)
    assert (result.text, result.usage.output_tokens) == ("1, 2, 3", 12)


def test_blocked_output_and_input_are_refusal_other_endings_are_error() -> None:
    for reason in ("SAFETY", "RECITATION"):
        blocked = run(finished(reason))
        assert isinstance(blocked, Refusal)
        assert blocked.category == reason
    input_blocked = run(gemini_response(candidates=None, promptFeedback={"blockReason": "PROHIBITED_CONTENT"}))
    assert isinstance(input_blocked, Refusal)
    assert (input_blocked.category, input_blocked.text) == ("PROHIBITED_CONTENT", "")
    # 입력이 막힌 응답에 usage 가 없어도 오류가 아니라 거부다.
    no_usage = run(gemini_response(candidates=None, usageMetadata=None, promptFeedback={"blockReason": "SAFETY"}))
    assert isinstance(no_usage, Refusal)
    assert (no_usage.category, no_usage.usage.input_tokens, no_usage.usage.output_tokens) == ("SAFETY", 0, 0)
    for odd in (
        gemini_response(candidates=[]),
        finished("MALFORMED_FUNCTION_CALL"),
        gemini_response(usageMetadata=None),
    ):
        result = run(odd)
        assert isinstance(result, ProviderError)
        assert result.retryable is False


def test_sdk_exceptions_map_to_error_and_timeout_and_keys_are_redacted() -> None:
    """뜻이 바뀐 것: 중단 신호(AbortError)가 없다. HTTP 층의 시간 초과 예외가 timeout 갈래다."""
    assert run(api_error(429, "한도")) == ProviderError(
        status=429, retryable=True, message="한도", error_kind="rate_limited"
    )
    assert run(api_error(503, "과부하")) == ProviderError(
        status=503, retryable=True, message="과부하", error_kind="server_error"
    )
    invalid = run(api_error(400, "API key not valid: AIzaSyntheticSyntheticSynthetic0000"))
    assert invalid == ProviderError(status=400, retryable=False, message="API key not valid: AIza[가림]")
    assert run(api_error(404, "없는 모델")) == ProviderError(status=404, retryable=False, message="없는 모델")
    # SDK 는 HTTP 층의 예외를 감싸지 않는다. 연결 실패는 재시도 가능한 오류, 시간 초과는 timeout 이다.
    assert run(httpx.ConnectError("connect failed")) == ProviderError(
        status=None, retryable=True, message="connect failed", error_kind="connection"
    )
    assert run(httpx.ReadTimeout("timed out")) == ProviderTimeout(message="timed out")
    assert run(RuntimeError("알 수 없음")) == ProviderError(status=None, retryable=False, message="알 수 없음")


def test_error_body_without_a_message_still_gets_redacted() -> None:
    """본문이 JSON 이 아니면 SDK 의 message 가 비고 예외의 글 전체가 문장이 된다. 거기 든 키도 가린다."""
    result = run(genai_errors.APIError(400, "bad key AIzaSyntheticSyntheticSynthetic0000"))
    assert isinstance(result, ProviderError)
    assert "AIzaSynthetic" not in result.message
    assert "AIza[가림]" in result.message


def test_without_client_returns_error_and_does_not_call() -> None:
    result = GeminiProvider().invoke(REQUEST, OPTIONS)
    assert isinstance(result, ProviderError)
    assert result.retryable is False


def test_sdk_client_uses_the_given_key_and_real_client_is_stopped_at_the_socket(
    monkeypatch: pytest.MonkeyPatch, blocked_network: list[object]
) -> None:
    """진짜 SDK 클라이언트로 불러도 소켓에서 막힌다(실호출 0 을 기계로). 그 실패는 재시도 가능한 오류 갈래로
    돌아온다.
    """
    # ★ 막혀 있는지를 네트워크 없이 먼저 본다. 고정물이 꺼져 있으면 진짜 클라이언트를 부르지 않고 여기서 멈춘다
    #   (2026-10-08 심은 파손 7 의 첫 실행에서 이 문지기가 없어 가상 키의 요청이 실제로 나갔다. 보고의 「실호출」 절).
    if getattr(socket.getaddrinfo, "__name__", "") != "blocked_getaddrinfo":
        pytest.fail("소켓이 막혀 있지 않다. 진짜 SDK 클라이언트를 부르지 않고 멈춘다")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-from-environment-synthetic")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    key = "AIzaSyntheticSyntheticSynthetic0000"
    client: Any = create_gemini_client(key)
    assert client._api_client.api_key == key
    assert client._api_client.vertexai is False

    result = GeminiProvider(client).invoke(PLAIN, OPTIONS)

    assert blocked_network, "SDK 가 네트워크로 나가려 하지 않았다: 이 테스트는 아무것도 재지 못했다"
    assert isinstance(result, ProviderError)
    assert (result.status, result.retryable) == (None, True)
    assert key not in result.message


# ── 키 가리기와 스키마 낱말 지우기 ──


def test_redact_sk_and_aiza_shapes_and_leave_ordinary_words() -> None:
    assert redact_keys("invalid x-api-key sk-ant-api03-synthetic_synthetic") == "invalid x-api-key sk-[가림]"
    assert redact_keys("key=AIzaSyntheticSynthetic_0000-xyz 끝") == "key=AIza[가림] 끝"
    assert redact_keys("AIza 와 risk-free 는 그대로") == "AIza 와 risk-free 는 그대로"
    # esg-lab 의 live.test.ts 에 있던 것.
    partly_masked = "Incorrect API key provided: sk-proj-abc*****xyz1. You can find"
    assert redact_keys(partly_masked) == "Incorrect API key provided: sk-[가림] You can find"
    assert redact_keys("risk-free 문장은 그대로") == "risk-free 문장은 그대로"


def test_strip_only_unsupported_constraints_and_keep_same_named_fields() -> None:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "keywords": {"type": "array", "maxItems": 8, "items": {"type": "string", "minLength": 1, "maxLength": 60}},
            "maximum": {"type": "number", "minimum": 0, "maximum": 10},
            "kind": {"anyOf": [{"const": 1}, {"const": "other"}]},
        },
        "required": ["keywords", "maximum", "kind"],
        "additionalProperties": False,
    }
    assert strip_unsupported_schema_keys(schema) == {
        "type": "object",
        "properties": {
            "keywords": {"type": "array", "items": {"type": "string"}},
            "maximum": {"type": "number"},
            "kind": {"anyOf": [{"const": 1}, {"const": "other"}]},
        },
        "required": ["keywords", "maximum", "kind"],
        "additionalProperties": False,
    }
    # 원본은 바꾸지 않는다.
    assert schema["properties"]["keywords"]["maxItems"] == 8


# ── 호출 간격 조절 ──


class FakeClock:
    def __init__(self, now: float) -> None:
        self.time = now
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.time

    def sleep(self, ms: float) -> None:
        self.sleeps.append(ms)
        self.time += ms


class Inner:
    name = "gemini"

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self.starts: list[float] = []
        self.timeouts: list[float] = []

    def build_request(self, request: ProviderRequest) -> object:
        return "조립된 요청"

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        self.starts.append(self._clock.time)
        self.timeouts.append(options.timeout_ms)
        return Completed(text="ok", usage=Usage(1, 1, 0, 0))


def test_throttle_spaces_starts_by_rpm_and_does_not_call_when_the_wait_exceeds_the_timeout() -> None:
    """뜻이 바뀐 것: 「기다리는 동안 중단되면」이 「기다리면 시간 제한을 넘으면」으로. 그때는 기다리지도 부르지도
    않는다.
    """
    clock = FakeClock(1_000)
    inner = Inner(clock)
    provider = throttled(inner, 10, clock)
    assert provider.name == "gemini"
    assert provider.build_request(REQUEST) == "조립된 요청"
    provider.invoke(REQUEST, OPTIONS)
    provider.invoke(REQUEST, OPTIONS)
    clock.time += 20_000  # 간격보다 오래 쉬었으면 기다리지 않는다
    provider.invoke(REQUEST, OPTIONS)
    assert inner.starts == [1_000, 7_000, 27_000]
    assert clock.sleeps == [6_000]
    # 공급사에는 기다린 만큼 줄어든 시간 제한이 간다.
    assert inner.timeouts == [30_000, 24_000, 30_000]

    # 다음 자리는 6초 뒤인데 시간 제한이 1초다: 기다리지도 부르지도 않고 timeout 으로 답한다. 자리도 잡지 않는다.
    assert isinstance(provider.invoke(REQUEST, InvokeOptions(timeout_ms=1_000)), ProviderTimeout)
    assert len(inner.starts) == 3
    assert clock.sleeps == [6_000]
    provider.invoke(REQUEST, OPTIONS)
    assert inner.starts[-1] == 33_000

    with pytest.raises(ValueError, match="양수"):
        throttled(inner, 0)
