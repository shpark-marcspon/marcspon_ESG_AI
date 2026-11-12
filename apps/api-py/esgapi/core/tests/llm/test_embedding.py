"""임베딩 호출 길(embedding.py): 모의 벡터, 묶음, 기록 줄, 실패 갈래, 상한, dry-run, 흐름이 받는 포트.

공급사는 모의(MockEmbeddingProvider)뿐이다. 가상 모델의 수(차원·한도·단가)는 설정에서 읽는다.
"""

import hashlib
import json
import math
from collections.abc import Sequence

import pytest

from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.config import default_config_sources, load_config, resolve_embedding_route
from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.embedding import (
    EMBEDDING_PROMPT_ID,
    ClientEmbeddingPort,
    EmbedBudgetExceeded,
    Embedded,
    EmbeddingClient,
    EmbeddingFailed,
    EmbeddingPort,
    EmbedProviderFailed,
    EmbedRequest,
    EmbedTimedOut,
)
from esgapi.core.llm.embedding_types import EmbeddingProviderRequest, EmbeddingVectors
from esgapi.core.llm.errors import LiveSetupError, LlmConfigError
from esgapi.core.llm.log import CallRecord, json_line
from esgapi.core.llm.providers.mock import MockEmbeddingProvider, mock_vector
from esgapi.core.llm.providers.openai import OpenAIEmbeddingProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import InvokeOptions, ProviderError, Scope, Tags
from esgapi.core.resources.llm import make_embedding

CONFIG = load_config(default_config_sources(synthetic=True))
ROUTE = "mock-gw1"
MODEL = resolve_embedding_route(CONFIG, ROUTE)
TAGS = Tags(tenant="t-1", module="greenwash")
TEN = [f"조각 {i} 의 글" for i in range(10)]

# esg-lab GW1(py/greenwash/ports.py 의 MockEmbedding, 차원 256)으로 낸 기준(발주서 §0-5, 2026-10-15 확인).
GW1_DIM = 256
GW1_INPUTS = ["", "a", "탄소중립 2050", "Scope 1·2 배출량은 전년 대비 12% 줄었다."]
GW1_SHA256 = "9fc8ce77752e2155e70d391b64d5fbfdc57b41d724887597412cc5a52b75626f"

# 채팅 줄(optional 칸 없음)의 to_json 열쇠 차례. 기준 log.py 의 것을 글자로 박는다.
CHAT_KEYS = [
    "ts",
    "callId",
    "attempt",
    "provider",
    "model",
    "apiModelId",
    "responseModelId",
    "promptId",
    "promptVersion",
    "templateHash",
    "requestHash",
    "inputTokens",
    "outputTokens",
    "cacheReadTokens",
    "cacheWriteTokens",
    "costUsd",
    "durationMs",
    "resultKind",
    "tenant",
    "module",
    "warnings",
]


def make_client(
    provider: MockEmbeddingProvider | None = None, *, limits: Sequence[BudgetLimit] = ()
) -> tuple[EmbeddingClient, MockEmbeddingProvider, MemorySink]:
    provider = provider or MockEmbeddingProvider()
    sink = MemorySink()
    client = EmbeddingClient(config=CONFIG, providers={"mock": provider}, log=sink, limits=limits)
    return client, provider, sink


def vectors_of(texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
    return tuple(mock_vector(text, MODEL.dimensions) for text in texts)


def digest(vectors: Sequence[Sequence[float]]) -> str:
    return hashlib.sha256(json.dumps([list(vector) for vector in vectors]).encode()).hexdigest()


# 5. 모의 벡터 = GW1


def test_mock_vectors_are_the_same_as_gw1() -> None:
    assert MODEL.dimensions == GW1_DIM  # 가상 모델의 차원은 GW1 과 같게 두었다(가상 파일의 note)
    vectors = [mock_vector(text, GW1_DIM) for text in GW1_INPUTS]
    assert digest(vectors) == GW1_SHA256
    query = mock_vector("탄소중립 2050", GW1_DIM)
    assert query == vectors[2]
    assert sum(1 for value in vectors[2] if value != 0) == 8
    for vector in vectors:
        assert abs(math.sqrt(sum(value * value for value in vector)) - 1) <= 1e-12

    # 공급사 층(빈 글자도 받는다 — 빈 글자를 거절하는 것은 클라이언트다)에서도 같다.
    answer = MockEmbeddingProvider().embed(
        EmbeddingProviderRequest(api_model_id="m", inputs=tuple(GW1_INPUTS), dimensions=GW1_DIM),
        InvokeOptions(timeout_ms=1000),
    )
    assert isinstance(answer, EmbeddingVectors)
    assert digest(answer.vectors) == GW1_SHA256


# 6·7. 묶음


def test_inputs_are_split_into_batches_in_order_with_one_record_per_batch() -> None:
    client, provider, sink = make_client()

    result = client.embed(EmbedRequest(inputs=TEN, route=ROUTE, tags=TAGS, batch_size=4))

    assert isinstance(result, Embedded)
    assert [len(call.inputs) for call in provider.calls] == [4, 4, 2]
    assert result.vectors == vectors_of(TEN)
    assert [record.embedding_inputs for record in sink.records] == [4, 4, 2]
    assert [record.attempt for record in sink.records] == [0, 1, 2]
    assert {record.call_id for record in sink.records} == {result.meta.call_id}
    assert len(result.meta.attempts) == 3


def test_batch_size_defaults_to_the_model_limit_and_is_checked() -> None:
    client, provider, _ = make_client()
    client.embed(EmbedRequest(inputs=TEN, route=ROUTE, tags=TAGS, batch_size=3))
    assert [len(call.inputs) for call in provider.calls] == [3, 3, 3, 1]

    client, provider, _ = make_client()
    assert MODEL.max_inputs_per_request >= len(TEN)
    client.embed(EmbedRequest(inputs=TEN, route=ROUTE, tags=TAGS))
    assert [len(call.inputs) for call in provider.calls] == [len(TEN)]

    for bad in (MODEL.max_inputs_per_request + 1, 0, -1, True):
        client, provider, sink = make_client()
        with pytest.raises(LlmConfigError, match="batch_size"):
            client.embed(EmbedRequest(inputs=TEN, route=ROUTE, tags=TAGS, batch_size=bad))
        assert (provider.calls, sink.records) == ([], [])


# 8. 빈 입력, 빈 글자, 글자 하나


def test_no_inputs_is_an_empty_success_without_a_call_or_a_record() -> None:
    client, provider, sink = make_client()
    result = client.embed(EmbedRequest(inputs=[], route=ROUTE, tags=TAGS))
    assert isinstance(result, Embedded)
    assert result.vectors == ()
    assert (result.meta.attempts, result.meta.total_cost_usd) == ((), 0)
    assert (provider.calls, sink.records) == ([], [])


@pytest.mark.parametrize(("inputs", "message"), [(["a", ""], "빈 글자"), ("abc", "글자 하나")])
def test_an_empty_text_or_a_bare_string_is_a_config_error(inputs: Sequence[str], message: str) -> None:
    client, provider, sink = make_client()
    with pytest.raises(LlmConfigError, match=message):
        client.embed(EmbedRequest(inputs=inputs, route=ROUTE, tags=TAGS))
    assert (provider.calls, sink.records) == ([], [])


# 9·10. 기록 줄


def test_a_record_line_carries_the_embedding_fields_and_no_input_text() -> None:
    secret = "공시전고객문장XYZ"
    client, _, sink = make_client()
    client.embed(EmbedRequest(inputs=[secret, "둘째"], route=ROUTE, tags=TAGS))
    client.embed(EmbedRequest(inputs=[secret, "둘째"], route=ROUTE, tags=TAGS))
    client.embed(EmbedRequest(inputs=[secret, "셋째"], route=ROUTE, tags=TAGS))
    first, again, other = sink.records

    tokens = len(secret) + len("둘째")
    assert first.prompt_id == EMBEDDING_PROMPT_ID == "embedding"
    assert (first.prompt_version, first.template_hash) == (0, "")
    assert (first.provider, first.model, first.api_model_id) == (MODEL.provider, MODEL.key, MODEL.api_model_id)
    assert first.input_tokens == tokens
    assert first.output_tokens == 0
    assert (first.cache_read_tokens, first.cache_write_tokens) == (None, None)
    assert first.cost_usd == round_usd(tokens * MODEL.pricing.input / 1_000_000)
    assert first.result_kind == "success"
    assert (first.tenant, first.module) == (TAGS.tenant, TAGS.module)
    assert first.warnings == ()
    assert first.body is None
    assert first.embedding_inputs == 2
    assert first.request_hash == again.request_hash
    assert first.request_hash != other.request_hash

    out = first.to_json()
    assert list(out) == [*CHAT_KEYS, "embeddingInputs"]
    assert out["embeddingInputs"] == 2
    assert secret not in json_line(out)


def test_a_chat_record_without_embedding_inputs_keeps_its_keys() -> None:
    record = CallRecord(
        ts="2026-10-15T00:00:00.000Z",
        call_id="c",
        attempt=0,
        provider="p",
        model="m",
        api_model_id="a",
        response_model_id=None,
        prompt_id="core/hello",
        prompt_version=1,
        template_hash="h",
        request_hash="r",
        input_tokens=1,
        output_tokens=1,
        cache_read_tokens=0,
        cache_write_tokens=0,
        cost_usd=0.0,
        duration_ms=1,
        result_kind="success",
        tenant="t",
        module="core",
        warnings=(),
    )
    assert record.embedding_inputs is None
    assert list(record.to_json()) == CHAT_KEYS


# 11. 실패 갈래


def answer_with_mock(request: EmbeddingProviderRequest) -> EmbeddingVectors:
    return EmbeddingVectors(
        vectors=tuple(mock_vector(text, request.dimensions) for text in request.inputs),
        input_tokens=sum(len(text) for text in request.inputs),
    )


def test_a_provider_error_stops_at_that_batch() -> None:
    provider = MockEmbeddingProvider().enqueue(answer_with_mock).enqueue(ProviderError(429, True, "한도 초과"))
    client, _, sink = make_client(provider)

    result = client.embed(EmbedRequest(inputs=TEN, route=ROUTE, tags=TAGS, batch_size=4))

    assert isinstance(result, EmbedProviderFailed)
    assert (result.status, result.retryable) == (429, True)
    assert len(provider.calls) == 2
    assert [record.result_kind for record in sink.records] == ["success", "provider_error"]
    assert sink.records[1].error_status == 429
    assert (sink.records[1].input_tokens, sink.records[1].output_tokens) == (None, None)
    assert len(result.meta.attempts) == 2
    assert result.meta.total_cost_usd == sink.records[0].cost_usd


def test_a_timeout_is_its_own_branch() -> None:
    provider = MockEmbeddingProvider().enqueue(answer_with_mock, delay_ms=1000)
    client, _, sink = make_client(provider)
    result = client.embed(EmbedRequest(inputs=TEN, route=ROUTE, tags=TAGS, timeout_ms=1000))
    assert isinstance(result, EmbedTimedOut)
    assert [record.result_kind for record in sink.records] == ["timeout"]


def test_an_adapter_that_raises_is_a_non_retryable_error_without_the_key() -> None:
    def boom(request: EmbeddingProviderRequest) -> EmbeddingVectors:
        raise RuntimeError("bad key sk-synthetic-key-0000")

    client, _, sink = make_client(MockEmbeddingProvider().enqueue(boom))
    result = client.embed(EmbedRequest(inputs=TEN, route=ROUTE, tags=TAGS))
    assert isinstance(result, EmbedProviderFailed)
    assert (result.status, result.retryable) == (None, False)
    assert "sk-synthetic" not in result.message
    assert "sk-[가림]" in result.message
    assert [record.result_kind for record in sink.records] == ["provider_error"]


# 12. 모양 검사


@pytest.mark.parametrize(
    "shape",
    ["one-vector-short", "dimension-255", "nan", "inf"],
)
def test_a_wrongly_shaped_answer_is_a_provider_error_but_its_cost_is_kept(shape: str) -> None:
    good = vectors_of(["a", "b"])
    vectors = {
        "one-vector-short": good[:1],
        "dimension-255": (good[0], good[1][:-1]),
        "nan": (good[0], (math.nan, *good[1][1:])),
        "inf": (good[0], (math.inf, *good[1][1:])),
    }[shape]
    client, _, sink = make_client(MockEmbeddingProvider().enqueue(EmbeddingVectors(vectors=vectors, input_tokens=7)))

    result = client.embed(EmbedRequest(inputs=["a", "b"], route=ROUTE, tags=TAGS))

    assert isinstance(result, EmbedProviderFailed)
    assert (result.status, result.retryable) == (None, False)
    assert "모양" in result.message
    (record,) = sink.records
    assert record.result_kind == "provider_error"
    assert record.error_status is None
    assert (record.input_tokens, record.output_tokens) == (7, 0)
    assert record.cost_usd == round_usd(7 * MODEL.pricing.input / 1_000_000)
    assert result.meta.total_cost_usd == record.cost_usd


# 13. 상한


def test_the_budget_stops_before_the_next_batch() -> None:
    first_batch = TEN[:4]
    first_cost = round_usd(sum(len(text) for text in first_batch) * MODEL.pricing.input / 1_000_000)
    limit = BudgetLimit(scope=Scope(tenant=TAGS.tenant), limit_usd=first_cost)
    client, provider, sink = make_client(limits=[limit])

    result = client.embed(EmbedRequest(inputs=TEN, route=ROUTE, tags=TAGS, batch_size=4))

    assert isinstance(result, EmbedBudgetExceeded)
    assert (result.limit_usd, result.spent_usd, result.scope) == (first_cost, first_cost, limit.scope)
    assert len(provider.calls) == 1
    last = sink.records[-1]
    assert [record.result_kind for record in sink.records] == ["success", "budget_exceeded"]
    assert (last.provider, last.model, last.api_model_id) == (None, None, None)
    assert last.attempt == 1
    assert len(result.meta.attempts) == 1


# 14. 어댑터 없음


def test_a_model_whose_provider_is_not_registered_is_a_config_error() -> None:
    sink = MemorySink()
    client = EmbeddingClient(config=CONFIG, providers={}, log=sink)
    with pytest.raises(LlmConfigError, match="어댑터가 등록되지 않았다"):
        client.embed(EmbedRequest(inputs=TEN, route=ROUTE, tags=TAGS))
    assert sink.records == []


# 15. dry-run


def test_dry_run_counts_batches_without_calling_or_recording() -> None:
    client, provider, sink = make_client()

    report = client.dry_run(EmbedRequest(inputs=TEN, route=ROUTE, tags=TAGS, batch_size=4))

    assert (report.provider, report.model) == ("mock", MODEL.key)
    assert (report.requests, report.inputs) == (3, 10)
    assert report.input_tokens > 0
    assert report.cost_usd == round_usd(report.input_tokens * MODEL.pricing.input / 1_000_000)
    assert report.request == provider.build_request(
        EmbeddingProviderRequest(api_model_id=MODEL.api_model_id, inputs=tuple(TEN[:4]), dimensions=MODEL.dimensions)
    )
    assert (provider.calls, sink.records) == ([], [])
    assert client.dry_run(EmbedRequest(inputs=[], route=ROUTE, tags=TAGS)).request is None


# 16·17. 흐름이 받는 포트


def test_the_client_port_has_the_gw1_shape() -> None:
    client, _, _ = make_client()
    port: EmbeddingPort = ClientEmbeddingPort(client, route=ROUTE, tags=TAGS, batch_size=4)

    documents = port.embed_documents(TEN)
    query = port.embed_query("탄소중립 2050")

    assert type(documents) is list
    assert all(type(vector) is list for vector in documents)
    assert documents == [list(vector) for vector in vectors_of(TEN)]
    assert type(query) is list
    assert query == port.embed_documents(["탄소중립 2050"])[0]


def test_the_client_port_raises_the_failure_branch() -> None:
    failing = (
        MockEmbeddingProvider().enqueue(ProviderError(500, True, "공급사 오류")).enqueue(ProviderError(500, True, "또"))
    )
    client, _, _ = make_client(failing)
    port = ClientEmbeddingPort(client, route=ROUTE, tags=TAGS)
    with pytest.raises(EmbeddingFailed) as caught:
        port.embed_documents(["a"])
    assert caught.value.result.kind == "provider_error"
    with pytest.raises(EmbeddingFailed) as caught_query:
        port.embed_query("a")
    assert caught_query.value.result.kind == "provider_error"
    assert failing.pending == 0


class CountingPort:
    """X1b 의 기록 래퍼가 설 자리: 포트를 받아 부른 수를 세고 그대로 넘긴다(기록 줄은 쓰지 않는다)."""

    def __init__(self, inner: EmbeddingPort) -> None:
        self.inner = inner
        self.calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return self.inner.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        return self.inner.embed_query(text)


def test_the_port_can_be_wrapped() -> None:
    client, _, sink = make_client()
    bare = ClientEmbeddingPort(client, route=ROUTE, tags=TAGS)
    wrapped: EmbeddingPort = CountingPort(bare)

    assert wrapped.embed_documents(TEN) == bare.embed_documents(TEN)
    assert wrapped.embed_query("질의") == bare.embed_query("질의")
    assert isinstance(wrapped, CountingPort)
    assert wrapped.calls == 2
    assert len(sink.records) == 4  # 기록은 클라이언트만 쓴다(래퍼가 더하지 않는다)


# 18. 임베딩 어댑터 고르기 — 환경에 키가 있어도 읽지 않는다


def test_make_embedding_picks_the_adapter_and_does_not_read_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-environment-synthetic")

    mock = make_embedding("mock")
    assert isinstance(mock, MockEmbeddingProvider)
    assert mock.name == "mock"
    with pytest.raises(LiveSetupError, match="키가 없다"):
        make_embedding("openai")
    with pytest.raises(LiveSetupError, match="키가 없다"):
        make_embedding("openai", api_key="  ")
    with pytest.raises(LiveSetupError, match="임베딩 어댑터가 없다"):
        make_embedding("anthropic", api_key="x")
    assembled = make_embedding("openai", assemble_only=True)
    assert isinstance(assembled, OpenAIEmbeddingProvider)
    result = assembled.embed(
        EmbeddingProviderRequest(api_model_id="m", inputs=("a",), dimensions=3), InvokeOptions(timeout_ms=1000)
    )
    assert isinstance(result, ProviderError)
    assert "주입되지 않았다" in result.message


# 19. DB 싱크가 손대지 않고 받는다(행을 짓기만 한다. DB 에 가지 않는다)


def test_the_db_sink_row_builder_accepts_an_embedding_record() -> None:
    from esgapi.core.llm.sink_db import row_from_record
    from esgapi.core.models import LLM_RESULT_KINDS

    client, _, sink = make_client()
    client.embed(EmbedRequest(inputs=["a", "b"], route=ROUTE, tags=TAGS))
    (record,) = sink.records

    row = row_from_record(record, company_id=1)

    assert row.prompt_id == "embedding"
    assert row.result_kind == "success"
    assert row.result_kind in LLM_RESULT_KINDS
    assert (row.input_tokens, row.output_tokens) == (record.input_tokens, 0)
    assert (row.prompt_version, row.template_hash) == (0, "")
