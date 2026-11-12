# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""공급사 오류의 이름(밴드 LB1 경계 ① — MARC-ISSUE-672 안 A 의 1). 순수 층.

  S1 이름 표     공급사 × 상태(·본문 코드) → error_kind·retryable — 진짜 SDK(anthropic 1.11.0·openai 3.26.0)
                 + 가짜 HTTP(httpx2·httpx MockTransport). gemini 는 SDK 의 APIError 를 직접 지어 어댑터에 넣는다
                 (test_llm_gemini 꼴).
  S2 크레딧 소진 429(openai 크레딧·지출 코드, anthropic 지출 상한) → retryable False·quota_exhausted. 임베딩도(B3)
  S3 결과 값     ProviderFailed·EmbedProviderFailed 에 error_kind·retry_after_ms. 이름 없는 실패의 result_json 은
                 BASE 열쇠 그대로
  S4 기록 줄     to_json 의 errorKind(있을 때만, errorStatus 바로 뒤) · DB 행 왕복에서 사라짐(Q1 (가))
  S5 위치 인자   ProviderFailed(None, False, "…", META) 가 선다
  S6 스트림 과부하 HTTP 200 의 overloaded_error 사건 → overloaded·재시도 가능·status 200·cost_bound_usd 그대로
★ 네트워크 0: 뿌리 conftest 의 blocked_network 를 끝에 본다. 키·본문은 지어낸 글자다.
"""

from pathlib import Path
from typing import Any

import anthropic
import httpx
import httpx2
import openai
import pytest
from google.genai import errors as genai_errors

from esgapi.core.llm.client import CallRequest, ToolCallRequest
from esgapi.core.llm.embedding import EmbeddingClient, EmbedProviderFailed, EmbedRequest
from esgapi.core.llm.embedding_types import EmbeddingProviderRequest
from esgapi.core.llm.log import MISSING, CallRecord
from esgapi.core.llm.providers.anthropic import AnthropicProvider
from esgapi.core.llm.providers.gemini import GeminiProvider
from esgapi.core.llm.providers.mock import MockEmbeddingProvider
from esgapi.core.llm.providers.openai import OpenAIEmbeddingProvider, OpenAIProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import (
    CallMeta,
    FunctionTool,
    InvokeOptions,
    ProviderError,
    ProviderFailed,
    ProviderRequest,
    TextPart,
    ToolLoopFailed,
    result_json,
)
from esgapi.core.resources.ports.llm import Provider
from esgapi.core.tests.llm_support import TAGS, harness, synthetic_config, write_prompts
from esgapi.core.tests.test_llm_gemini import FakeGemini

OPTIONS = InvokeOptions(timeout_ms=10_000)
PLAIN = ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10)
META = CallMeta(call_id="c", prompt_id="t/plain@1", attempts=(), total_cost_usd=0, warnings=())


@pytest.fixture
def prompts(tmp_path: Path) -> Path:
    return write_prompts(tmp_path)


# ── 가짜 HTTP ─────────────────────────────────────────────────────────

Reply = tuple[int, dict[str, Any] | None]  # (상태, 본문) — 본문 None 이면 연결 실패


def anthropic_body(error_type: str, details: dict[str, str] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"type": error_type, "message": "합성 오류"}
    if details is not None:
        error["details"] = details
    return {"type": "error", "error": error, "request_id": "req_synthetic"}


def openai_body(error_type: str, code: str | None = None) -> dict[str, Any]:
    return {"error": {"message": "합성 오류", "type": error_type, "code": code, "param": None}}


def run_anthropic(reply: Reply) -> ProviderError:
    status, body = reply

    def handler(request: httpx2.Request) -> httpx2.Response:
        if body is None:
            raise httpx2.ConnectError("합성 연결 실패", request=request)
        return httpx2.Response(status, json=body)

    sdk = anthropic.Anthropic(
        api_key="anthropic-key-synthetic",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    result = AnthropicProvider(sdk).invoke(PLAIN, OPTIONS)  # pyright: ignore[reportArgumentType]
    assert isinstance(result, ProviderError), result
    return result


def openai_sdk(reply: Reply) -> openai.OpenAI:
    status, body = reply

    def handler(request: httpx.Request) -> httpx.Response:
        if body is None:
            raise httpx.ConnectError("합성 연결 실패", request=request)
        return httpx.Response(status, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return openai.OpenAI(api_key="openai-key-synthetic", max_retries=0, http_client=client)  # pyright: ignore[reportArgumentType]


def run_openai(reply: Reply) -> ProviderError:
    result = OpenAIProvider(openai_sdk(reply)).invoke(PLAIN, OPTIONS)  # pyright: ignore[reportArgumentType]
    assert isinstance(result, ProviderError), result
    return result


def run_openai_embedding(reply: Reply) -> ProviderError:
    request = EmbeddingProviderRequest(api_model_id="m", inputs=("합성",), dimensions=3)
    result = OpenAIEmbeddingProvider(openai_sdk(reply)).embed(request, OPTIONS)  # pyright: ignore[reportArgumentType]
    assert isinstance(result, ProviderError), result
    return result


def run_gemini(status: int) -> ProviderError:
    error = genai_errors.APIError(status, {"error": {"code": status, "message": "합성 오류"}})
    result = GeminiProvider(FakeGemini(error)).invoke(PLAIN, OPTIONS)
    assert isinstance(result, ProviderError), result
    return result


SPEND_CAP = {"error_code": "enforced_spend_limit_reached"}

# ── S1·S2 이름 표 ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("reply", "kind", "retryable"),
    [
        pytest.param((429, anthropic_body("rate_limit_error")), "rate_limited", True, id="429"),
        pytest.param(
            (429, anthropic_body("rate_limit_error", SPEND_CAP)), "quota_exhausted", False, id="429-spend-cap"
        ),
        pytest.param((529, anthropic_body("overloaded_error")), "overloaded", True, id="529"),
        pytest.param((500, anthropic_body("api_error")), "server_error", True, id="500"),
        pytest.param((402, anthropic_body("billing_error")), "quota_exhausted", False, id="402"),
        pytest.param((400, anthropic_body("invalid_request_error")), "other", False, id="400"),
        pytest.param((0, None), "connection", True, id="connection"),
    ],
)
def test_s1_anthropic_names(blocked_network: list[object], reply: Reply, kind: str, retryable: bool) -> None:
    error = run_anthropic(reply)
    assert (error.error_kind, error.retryable) == (kind, retryable)
    assert error.status == (None if reply[1] is None else reply[0])
    assert blocked_network == []


@pytest.mark.parametrize(
    ("reply", "kind", "retryable"),
    [
        pytest.param((429, openai_body("requests")), "rate_limited", True, id="429-rate"),
        pytest.param((429, openai_body("rate_limit_error", "slow_down")), "rate_limited", True, id="429-slow-down"),
        pytest.param(
            (429, openai_body("insufficient_quota", "credit_balance_exhausted")),
            "quota_exhausted",
            False,
            id="429-credit",
        ),
        pytest.param((429, openai_body("insufficient_quota")), "quota_exhausted", False, id="429-insufficient-quota"),
        pytest.param((429, openai_body("x", "project_spend_limit_exceeded")), "quota_exhausted", False, id="429-spend"),
        pytest.param((500, openai_body("server_error")), "server_error", True, id="500"),
        pytest.param(
            (503, openai_body("service_unavailable_error", "server_is_overloaded")),
            "overloaded",
            True,
            id="503-overloaded",
        ),
        pytest.param((503, openai_body("service_unavailable_error")), "server_error", True, id="503-other"),
        pytest.param((401, openai_body("invalid_request_error", "invalid_api_key")), "other", False, id="401"),
        pytest.param((0, None), "connection", True, id="connection"),
    ],
)
def test_s1_openai_names(blocked_network: list[object], reply: Reply, kind: str, retryable: bool) -> None:
    error = run_openai(reply)
    assert (error.error_kind, error.retryable) == (kind, retryable)
    assert blocked_network == []


@pytest.mark.parametrize(
    ("status", "kind", "retryable"),
    [
        (429, "rate_limited", True),
        (503, "server_error", True),
        (408, "server_error", True),
        (500, "server_error", True),
        (402, "quota_exhausted", False),
        (404, "other", False),
    ],
)
def test_s1_gemini_names(status: int, kind: str, retryable: bool) -> None:
    error = run_gemini(status)
    assert (error.error_kind, error.retryable) == (kind, retryable)


def test_s2_credit_exhausted_is_not_retryable_and_keeps_no_wait(blocked_network: list[object]) -> None:
    """크레딧 소진 429 는 기다려도 안 풀린다 — 재시도 불가, 대기(retry_after_ms)도 싣지 않는다."""
    error = run_openai((429, openai_body("insufficient_quota", "credit_balance_exhausted")))
    assert (error.status, error.retryable, error.error_kind, error.retry_after_ms) == (
        429,
        False,
        "quota_exhausted",
        None,
    )
    assert blocked_network == []


@pytest.mark.parametrize(
    ("reply", "kind", "retryable"),
    [
        pytest.param(
            (429, openai_body("insufficient_quota", "credit_balance_exhausted")), "quota_exhausted", False, id="credit"
        ),
        pytest.param((429, openai_body("requests")), "rate_limited", True, id="rate"),
        pytest.param(
            (503, openai_body("service_unavailable_error", "server_is_overloaded")), "overloaded", True, id="overloaded"
        ),
    ],
)
def test_s2_embedding_credit_exhausted_is_not_retryable(
    blocked_network: list[object], reply: Reply, kind: str, retryable: bool
) -> None:
    """임베딩 길도 같은 이름(감독 답 2 B3 — 크레딧 소진은 실행 층에서 미룸 대신 embedding_failed, 속도·과부하는
    미룸)."""
    error = run_openai_embedding(reply)
    assert (error.error_kind, error.retryable) == (kind, retryable)
    assert blocked_network == []


# ── S3 결과 값 ────────────────────────────────────────────────────────


def test_s3_provider_failed_carries_the_name_and_the_wait(prompts: Path) -> None:
    h = harness(prompts, provider_retry={})
    h.mock.enqueue(ProviderError(429, True, "합성 한도", retry_after_ms=1_500, error_kind="rate_limited"))
    result = h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS))
    assert isinstance(result, ProviderFailed)
    assert (result.error_kind, result.retry_after_ms) == ("rate_limited", 1_500)
    out = result_json(result, None)
    assert list(out) == ["kind", "status", "retryable", "message", "errorKind", "retryAfterMs", "meta"]
    assert (out["errorKind"], out["retryAfterMs"]) == ("rate_limited", 1_500)


def test_s3_a_failed_tool_loop_carries_the_name_and_the_wait(prompts: Path) -> None:
    """도구 고리(call_tools)의 공급사 오류 실패도 같은 칸을 싣는다(client.call_tools 의 ProviderFailed)."""
    h = harness(prompts, provider_retry={})
    h.mock.enqueue(ProviderError(503, True, "합성 과부하", retry_after_ms=2_500, error_kind="overloaded"))
    tool = FunctionTool(name="tool_a", description="가상 도구", parameters={"type": "object", "properties": {}})
    request = ToolCallRequest(
        prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS, tools=(tool,), max_steps=2
    )
    result = h.client.call_tools(request, lambda _name, _arguments: "")
    assert isinstance(result, ToolLoopFailed) and isinstance(result.failure, ProviderFailed)
    assert (result.failure.error_kind, result.failure.retry_after_ms) == ("overloaded", 2_500)


def test_s3_a_nameless_failure_keeps_the_base_json_keys() -> None:
    """모듈이 직접 만든 실패(이름 없음)의 JSON 은 BASE 와 같은 열쇠·차례다."""
    out = result_json(ProviderFailed(status=None, retryable=False, message="합성", meta=META), None)
    assert list(out) == ["kind", "status", "retryable", "message", "meta"]


def test_s3_a_default_named_error_still_reaches_the_result_as_other(prompts: Path) -> None:
    """이름을 주지 않은 공급사 오류는 "other" 로 결과에 실린다(None 은 공급사 오류가 아닌 실패뿐)."""
    h = harness(prompts, provider_retry={})
    h.mock.enqueue(ProviderError(400, False, "합성 거절"))
    result = h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS))
    assert isinstance(result, ProviderFailed)
    assert (result.error_kind, result.retry_after_ms) == ("other", None)


def test_s3_embed_provider_failed_carries_the_name_and_the_wait() -> None:
    provider = MockEmbeddingProvider().enqueue(
        ProviderError(429, True, "합성 한도", retry_after_ms=700, error_kind="rate_limited")
    )
    client = EmbeddingClient(config=synthetic_config(), providers={"mock": provider}, log=MemorySink())
    result = client.embed(EmbedRequest(inputs=("합성",), route="mock-gw1", tags=TAGS))
    assert isinstance(result, EmbedProviderFailed)
    assert (result.error_kind, result.retry_after_ms) == ("rate_limited", 700)


def test_s3_a_bad_shape_embedding_has_no_name() -> None:
    """모양 틀림은 공급사 오류가 아니다 — 이름 None."""
    from esgapi.core.llm.embedding_types import EmbeddingVectors

    provider = MockEmbeddingProvider().enqueue(EmbeddingVectors(vectors=(), input_tokens=1, model_id="m"))
    client = EmbeddingClient(config=synthetic_config(), providers={"mock": provider}, log=MemorySink())
    result = client.embed(EmbedRequest(inputs=("합성",), route="mock-gw1", tags=TAGS))
    assert isinstance(result, EmbedProviderFailed)
    assert (result.error_kind, result.retry_after_ms) == (None, None)


# ── S4 기록 줄 ────────────────────────────────────────────────────────


def record(**overrides: Any) -> CallRecord:
    base: dict[str, Any] = {
        "ts": "2026-11-11T00:00:00.000Z",
        "call_id": "c",
        "attempt": 0,
        "provider": "mock",
        "model": "mock-synthetic",
        "api_model_id": "m",
        "response_model_id": None,
        "prompt_id": "t/plain",
        "prompt_version": 1,
        "template_hash": "h",
        "request_hash": "r",
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
        "cost_usd": None,
        "duration_ms": 1.0,
        "result_kind": "provider_error",
        "tenant": "1",
        "module": "m",
        "warnings": (),
    }
    return CallRecord(**{**base, **overrides})


def test_s4_error_kind_sits_right_after_error_status_only_when_present(prompts: Path) -> None:
    named = record(error_status=429, retry_after_ms=1, error_kind="rate_limited").to_json()
    keys = list(named)
    assert keys[keys.index("errorStatus") + 1] == "errorKind"
    assert named["errorKind"] == "rate_limited"
    assert "errorKind" not in record(error_status=429).to_json()
    assert "errorKind" not in record(result_kind="success", error_status=MISSING).to_json()
    # 호출 층이 공급사 오류 줄에 싣는다.
    h = harness(prompts, provider_retry={})
    h.mock.enqueue(ProviderError(529, True, "합성 과부하", error_kind="overloaded"))
    h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS))
    (line,) = h.log.records
    assert line.error_kind == "overloaded"


def test_s4_embedding_line_carries_the_name() -> None:
    sink = MemorySink()
    provider = MockEmbeddingProvider().enqueue(ProviderError(429, True, "합성", error_kind="rate_limited"))
    EmbeddingClient(config=synthetic_config(), providers={"mock": provider}, log=sink).embed(
        EmbedRequest(inputs=("합성",), route="mock-gw1", tags=TAGS)
    )
    (line,) = sink.records
    assert line.error_kind == "rate_limited"


def test_s4_the_db_row_round_trip_drops_the_name() -> None:
    """Q1 (가): 표에 칸이 없다 — 되살린 줄에는 이름이 없고 error_status 는 남는다(sink_db 머리말의 무효 조건)."""
    from esgapi.core.llm.sink_db import record_from_row, row_from_record

    back = record_from_row(row_from_record(record(error_status=429, error_kind="quota_exhausted"), company_id=1))
    assert (back.error_status, back.error_kind) == (429, None)


# ── S5 위치 인자 ──────────────────────────────────────────────────────


def test_s5_positional_provider_failed_still_builds() -> None:
    failed = ProviderFailed(None, False, "합성", META)
    assert (failed.status, failed.retryable, failed.message, failed.meta) == (None, False, "합성", META)
    assert (failed.kind, failed.error_kind, failed.retry_after_ms) == ("provider_error", None, None)
    error = ProviderError(429, True, "합성")
    assert (error.retry_after_ms, error.error_kind) == (None, "other")


# ── S6 스트림 중 과부하 ──────────────────────────────────────────────

SSE_OVERLOADED = (
    b"event: message_start\n"
    b'data: {"type":"message_start","message":{"id":"msg_synthetic","type":"message","role":"assistant",'
    b'"model":"claude-synthetic","content":[],"stop_reason":null,"stop_sequence":null,'
    b'"usage":{"input_tokens":1,"output_tokens":1}}}\n\n'
    b"event: error\n"
    b'data: {"type":"error","error":{"type":"overloaded_error","message":"synthetic"}}\n\n'
)


def stream_overloaded_sdk() -> anthropic.Anthropic:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=SSE_OVERLOADED)

    return anthropic.Anthropic(
        api_key="anthropic-key-synthetic",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )


def test_s6_an_overloaded_event_in_a_200_stream_is_named_and_retryable(
    prompts: Path, blocked_network: list[object]
) -> None:
    error = AnthropicProvider(stream_overloaded_sdk()).invoke(PLAIN, OPTIONS)  # pyright: ignore[reportArgumentType]
    assert isinstance(error, ProviderError)
    assert (error.status, error.retryable, error.error_kind, error.sent) == (200, True, "overloaded", True)
    # 장부: 과금됐을 수 있는 실패라 어림이 붙는다(test_cost_bound 의 F4 와 같음).
    providers: dict[str, Provider] = {"anthropic": AnthropicProvider(stream_overloaded_sdk())}  # pyright: ignore[reportArgumentType]
    h = harness(prompts, providers=providers, provider_retry={})
    result = h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="light-anthropic", tags=TAGS))
    assert isinstance(result, ProviderFailed)
    assert (result.status, result.retryable, result.error_kind) == (200, True, "overloaded")
    (line,) = h.log.records
    assert (line.error_status, line.error_kind, line.cost_usd) == (200, "overloaded", None)
    assert line.cost_bound_usd is not None and line.cost_bound_usd > 0
    assert blocked_network == []
