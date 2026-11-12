# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실패 시도의 보수 어림 `cost_bound_usd`(밴드 LH2 S5~S7 — MARC-ISSUE-411 S2). 순수 층.

  S5 상한 셈    모의 공급사의 시간 초과 / 상태 없는 오류 / 200 오류 / 429 / 나가지 않은 오류(sent=False) / 성공:
                장부 cost_usd 는 None ×5·실비(BASE 그대로), cost_bound_usd 는 최악·최악·최악·None·None·None
                = 손셈(Q4 식).
                어댑터 앞 거절과 연결 실패의 `.sent` 는 False(직접 단언). anthropic 진짜 SDK + 가짜 HTTP 의 스트림 중간
                error 사건(status 200) → 최악(B2). 도구 고리 걸음 2 의 어림 > 걸음 1(앞 걸음이 실림 — M4)
  S6 바이트     시간 초과 줄의 to_json() 에 새 칸의 열쇠가 없다 · DB 싱크에 넘기는 행 dict 에도 없다
  S7 임베딩     임베딩 시간 초과 → 입력 토큰 어림 × 입력 단가 × (1 + SDK 재시도)
★ 네트워크 0: 뿌리 conftest 의 blocked_network(시도가 있으면 목록에 남는다)를 끝에 비었는지 본다. 키는 지어낸 글자다.
"""

import json
from pathlib import Path
from typing import Any

import anthropic
import httpx
import httpx2
import openai
import pytest

from esgapi.core.llm import sink_db
from esgapi.core.llm.client import CallRequest, ToolCallRequest
from esgapi.core.llm.config import ModelConfig
from esgapi.core.llm.cost import HeuristicTokenEstimator, compute_cost_usd, round_usd
from esgapi.core.llm.embedding import EmbeddingClient, EmbedRequest
from esgapi.core.llm.embedding_types import EmbeddingProviderRequest
from esgapi.core.llm.log import CallRecord
from esgapi.core.llm.providers.anthropic import AnthropicProvider
from esgapi.core.llm.providers.gemini import GeminiProvider
from esgapi.core.llm.providers.mock import MockEmbeddingProvider
from esgapi.core.llm.providers.openai import EMBEDDING_SDK_MAX_RETRIES, OpenAIEmbeddingProvider, OpenAIProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import (
    FunctionTool,
    InvokeOptions,
    PdfPart,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeout,
    TextPart,
    Usage,
)
from esgapi.core.resources.ports.llm import Provider
from esgapi.core.tests.llm_support import TAGS, USAGE_SYNTHETIC, harness, synthetic_config, write_prompts

OPTIONS = InvokeOptions(timeout_ms=10_000)
PLAIN = ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10)


@pytest.fixture
def prompts(tmp_path: Path) -> Path:
    return write_prompts(tmp_path)


def call_request(route: str = "mock") -> CallRequest[str]:
    return CallRequest(prompt="t/plain@1", vars={"question": "합성 질문"}, route=route, tags=TAGS)


def hand_worst(record: CallRecord, model: ModelConfig, body: dict[str, Any]) -> float:
    """Q4 식을 손으로: 요청 JSON(첨부 base64 뺌)의 토큰 어림 + 출력 상한, 그 모델 단가."""
    estimator = HeuristicTokenEstimator(synthetic_config().token_estimate)
    text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    usage = Usage(
        input_tokens=estimator.estimate(text),
        output_tokens=int(body["maxOutputTokens"]),  # pyright: ignore[reportArgumentType]
        cache_read_tokens=0,
        cache_write_tokens=0,
    )
    return compute_cost_usd(usage, model.pricing)


CASES = [
    pytest.param(ProviderTimeout(message="합성 시간 초과"), "timeout", True, id="timeout"),
    pytest.param(ProviderError(status=None, retryable=False, message="합성"), "provider_error", True, id="no-status"),
    pytest.param(ProviderError(status=200, retryable=False, message="합성"), "provider_error", True, id="status-200"),
    pytest.param(ProviderError(status=429, retryable=True, message="합성"), "provider_error", False, id="429"),
    pytest.param(
        ProviderError(status=None, retryable=True, message="합성", sent=False), "provider_error", False, id="not-sent"
    ),
]


@pytest.mark.parametrize(("reply", "kind", "bounded"), CASES)
def test_s5_failed_attempts_carry_the_worst_once_bound_and_no_ledger_cost(
    prompts: Path, blocked_network: list[object], reply: ProviderResponse, kind: str, bounded: bool
) -> None:
    h = harness(prompts, store_bodies=True, provider_retry={})
    h.mock.enqueue(reply)
    result = h.client.call(call_request())
    (record,) = h.log.records
    assert (result.kind, record.result_kind) == ({"timeout": "timeout"}.get(kind, "provider_error"), kind)
    assert record.cost_usd is None
    assert record.body is not None
    model = synthetic_config().models["mock-synthetic"]
    want = hand_worst(record, model, record.body.request) if bounded else None
    assert record.cost_bound_usd == want
    if bounded:
        assert want is not None and want > 0
    assert blocked_network == []


def test_s5_success_keeps_its_ledger_cost_and_no_bound(prompts: Path) -> None:
    h = harness(prompts)
    h.mock.enqueue_text("합성 답", usage=USAGE_SYNTHETIC)
    assert h.client.call(call_request()).kind == "success"
    (record,) = h.log.records
    assert (record.cost_usd, record.cost_bound_usd) == (0.0001, None)


def test_s5_the_bound_counts_the_output_cap(prompts: Path) -> None:
    """출력 상한이 어림에 든다(입력만이면 이 차이가 0 이다 — P8)."""
    small = harness(prompts, store_bodies=True)
    large = harness(prompts, store_bodies=True)
    small.mock.enqueue(ProviderTimeout(message="합성"))
    large.mock.enqueue(ProviderTimeout(message="합성"))
    small.client.call(
        CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS, max_output_tokens=10)
    )
    large.client.call(
        CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS, max_output_tokens=1000)
    )
    (a,), (b,) = small.log.records, large.log.records
    pricing = synthetic_config().models["mock-synthetic"].pricing
    assert a.cost_bound_usd is not None and b.cost_bound_usd is not None
    # 요청 JSON 의 maxOutputTokens 숫자 글자 수 차이(어림 토큰 1 이하)만큼 입력이 다를 수 있다.
    assert round_usd(b.cost_bound_usd - a.cost_bound_usd) >= round_usd(989 * pricing.output / 1_000_000)


def test_s5_requests_that_never_left_say_so() -> None:
    """어댑터 앞 거절(클라이언트 없음·temperature·도구)과 연결부터 실패한 요청은 sent=False(P25)."""
    tool = FunctionTool(name="lookup", description="합성", parameters={"type": "object", "properties": {}})
    refused = [
        OpenAIProvider().invoke(PLAIN, OPTIONS),
        AnthropicProvider().invoke(PLAIN, OPTIONS),
        GeminiProvider().invoke(PLAIN, OPTIONS),
        OpenAIEmbeddingProvider().embed(
            EmbeddingProviderRequest(api_model_id="e", inputs=("x",), dimensions=3), OPTIONS
        ),
    ]

    class Rejecting:
        messages = None

    for request in (
        ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10, temperature=0.5),
        ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10, tools=(tool,)),
    ):
        refused.append(AnthropicProvider(Rejecting()).invoke(request, OPTIONS))  # pyright: ignore[reportArgumentType]
    refused.append(
        GeminiProvider(Rejecting()).invoke(  # pyright: ignore[reportArgumentType]
            ProviderRequest(
                api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10, tools=(tool,)
            ),
            OPTIONS,
        )
    )
    assert all(isinstance(r, ProviderError) and r.sent is False for r in refused), refused


def connect_failed(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("합성 연결 실패", request=request)


def read_failed(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadError("합성 읽기 실패", request=request)


@pytest.mark.parametrize(("handler", "sent"), [(connect_failed, False), (read_failed, True)])
def test_s5_a_connection_that_never_opened_is_not_sent(blocked_network: list[object], handler: Any, sent: bool) -> None:
    transport = httpx.MockTransport(handler)
    client = openai.OpenAI(api_key="openai-key-synthetic", max_retries=0, http_client=httpx.Client(transport=transport))  # pyright: ignore[reportArgumentType]
    result = OpenAIProvider(client).invoke(PLAIN, OPTIONS)  # pyright: ignore[reportArgumentType]
    assert isinstance(result, ProviderError)
    assert (result.status, result.retryable, result.sent) == (None, True, sent)
    assert blocked_network == []


SSE_ERROR = (
    b"event: message_start\n"
    b'data: {"type":"message_start","message":{"id":"msg_synthetic","type":"message","role":"assistant",'
    b'"model":"claude-synthetic","content":[],"stop_reason":null,"stop_sequence":null,'
    b'"usage":{"input_tokens":1,"output_tokens":1}}}\n\n'
    b"event: error\n"
    b'data: {"type":"error","error":{"type":"overloaded_error","message":"synthetic"}}\n\n'
)


def test_s5_an_error_event_inside_a_200_stream_is_bounded(prompts: Path, blocked_network: list[object]) -> None:
    """anthropic 의 스트림 중간 error 사건은 status 200 의 오류다 — 과금됐을 수 있어 어림을 싣는다(B2, P19)."""

    def handler(request: Any) -> Any:
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=SSE_ERROR)

    sdk = anthropic.Anthropic(
        api_key="anthropic-key-synthetic",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    providers: dict[str, Provider] = {"anthropic": AnthropicProvider(sdk)}  # pyright: ignore[reportArgumentType]
    h = harness(prompts, store_bodies=True, providers=providers, provider_retry={})
    result = h.client.call(call_request("light-anthropic"))
    (record,) = h.log.records
    assert (result.kind, record.error_status, record.cost_usd) == ("provider_error", 200, None)
    model = synthetic_config().models["claude-haiku-4-5"]
    assert record.body is not None
    assert record.cost_bound_usd == hand_worst(record, model, record.body.request)
    assert blocked_network == []


def test_s5_a_later_tool_step_is_bounded_higher_than_the_first(prompts: Path) -> None:
    """고리의 걸음 2 는 앞 걸음의 항목(turns)이 요청에 실려 어림이 더 크다(M4)."""
    tool = FunctionTool(name="lookup", description="합성 도구", parameters={"type": "object", "properties": {}})
    request = ToolCallRequest(
        prompt="t/plain@1", vars={"question": "합성"}, route="mock", tags=TAGS, tools=(tool,), max_steps=3
    )
    first = harness(prompts, provider_retry={})
    first.mock.enqueue(ProviderTimeout(message="합성"))
    first.client.call_tools(request, lambda name, arguments: "결과")
    second = harness(prompts, provider_retry={})
    second.mock.enqueue_tool_calls([("lookup", '{"q":"합성 인자 글자"}')])
    second.mock.enqueue(ProviderTimeout(message="합성"))
    second.client.call_tools(request, lambda name, arguments: "합성 도구 결과 글자 " * 20)
    (step1,) = first.log.records
    _, step2 = second.log.records
    assert step1.cost_bound_usd is not None and step2.cost_bound_usd is not None
    assert step2.cost_bound_usd > step1.cost_bound_usd


def test_s6_the_bound_is_not_in_the_json_line_or_the_db_row(prompts: Path) -> None:
    h = harness(prompts)
    h.mock.enqueue(ProviderTimeout(message="합성"))
    h.client.call(call_request())
    (record,) = h.log.records
    assert record.cost_bound_usd is not None
    line = record.to_json()
    assert not any("bound" in key.lower() for key in line)
    assert line["costUsd"] is None
    row = sink_db.row_from_record(record, company_id=1)
    columns = {f.attname for f in row._meta.concrete_fields}  # pyright: ignore[reportPrivateUsage]
    assert "cost_usd" in columns
    assert not any("bound" in name for name in columns)
    assert row.cost_usd is None


def test_s7_an_embedding_timeout_is_bounded_with_the_sdk_retries(blocked_network: list[object]) -> None:
    config = synthetic_config()
    mock = MockEmbeddingProvider()
    mock.enqueue(ProviderTimeout(message="합성"))
    sink = MemorySink()
    client = EmbeddingClient(config=config, providers={"mock": mock}, log=sink)
    texts = ("합성 문장 하나", "synthetic sentence two")
    route = "mock-gw1"  # 가상 임베딩 경로(models.embedding.synthetic.json)
    result = client.embed(EmbedRequest(inputs=texts, route=route, tags=TAGS))
    assert result.kind == "timeout"
    (record,) = sink.records
    model = config.embedding_models[config.embedding_routes[route]]
    estimator = HeuristicTokenEstimator(config.token_estimate)
    tokens = sum(estimator.estimate(text) for text in texts)
    want = round_usd(tokens * model.pricing.input / 1_000_000 * (1 + EMBEDDING_SDK_MAX_RETRIES))
    assert (record.cost_usd, record.cost_bound_usd) == (None, want)
    assert want > 0
    assert blocked_network == []


def test_s5_attachment_base64_is_left_out_of_the_bound(prompts: Path) -> None:
    """첨부(PDF)의 base64 길이는 어림에 들지 않는다(어림 밖 — 머리말 ★, P27). 이름 등 나머지 칸은 든다."""
    bounds: list[float | None] = []
    for data in ("QUJD", "QUJD" * 5000):
        h = harness(prompts, provider_retry={})
        h.mock.enqueue(ProviderTimeout(message="합성"))
        pdf = PdfPart(base64=data, filename="합성.pdf")
        h.client.call(
            CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS, attachments=(pdf,))
        )
        (record,) = h.log.records
        bounds.append(record.cost_bound_usd)
    assert bounds[0] is not None and bounds[0] > 0
    assert bounds[0] == bounds[1]


@pytest.mark.parametrize(
    ("reply", "bounded"),
    [
        pytest.param(ProviderError(status=None, retryable=False, message="합성"), True, id="no-status"),
        pytest.param(ProviderError(status=200, retryable=False, message="합성"), True, id="status-200"),
        pytest.param(ProviderError(status=429, retryable=True, message="합성"), False, id="429"),
        pytest.param(ProviderError(status=None, retryable=True, message="합성", sent=False), False, id="not-sent"),
    ],
)
def test_s7_an_embedding_error_is_bounded_only_when_it_may_have_been_billed(
    blocked_network: list[object], reply: ProviderError, bounded: bool
) -> None:
    """임베딩 오류 갈래(P28): 나간 요청의 상태 없는 오류·2xx 오류만 Q5 식, 429·나가지 않은 오류는 None."""
    config = synthetic_config()
    mock = MockEmbeddingProvider()
    mock.enqueue(reply)
    sink = MemorySink()
    client = EmbeddingClient(config=config, providers={"mock": mock}, log=sink)
    texts = ("합성 문장 하나",)
    assert client.embed(EmbedRequest(inputs=texts, route="mock-gw1", tags=TAGS)).kind == "provider_error"
    (record,) = sink.records
    model = config.embedding_models[config.embedding_routes["mock-gw1"]]
    tokens = HeuristicTokenEstimator(config.token_estimate).estimate(texts[0])
    want = round_usd(tokens * model.pricing.input / 1_000_000 * (1 + EMBEDDING_SDK_MAX_RETRIES))
    assert (record.cost_usd, record.cost_bound_usd) == (None, want if bounded else None)
    assert blocked_network == []
