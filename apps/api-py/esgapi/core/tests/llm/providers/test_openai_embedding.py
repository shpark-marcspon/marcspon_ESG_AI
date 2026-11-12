"""OpenAI 임베딩 어댑터(providers/openai.py)와 세우기(setup.build_embedding_client).

실호출 0: 가짜 SDK 클라이언트로 재고, 진짜 SDK 클라이언트는 소켓 문지기(뿌리 conftest.py 의 blocked_network) 아래에서만
부른다. 키는 전부 가상(sk-synthetic…)이고, 환경 변수에 가상 키를 심어 두고도 그것을 읽지 않음을 잰다.
"""

import socket
from typing import Any

import httpx2
import openai
import pytest
from openai.types import CreateEmbeddingResponse, Embedding

from esgapi.config.env import LlmSettings
from esgapi.core.llm.config import default_config_sources, load_config, resolve_embedding_route
from esgapi.core.llm.embedding import Embedded, EmbeddingClient, EmbedRequest
from esgapi.core.llm.embedding_types import EmbeddingProviderRequest, EmbeddingVectors
from esgapi.core.llm.errors import LiveSetupError
from esgapi.core.llm.providers.openai import OpenAIEmbeddingProvider, create_openai_embedding_client
from esgapi.core.llm.setup import build_embedding_client
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import InvokeOptions, ProviderError, ProviderTimeout, Tags

REQUEST = EmbeddingProviderRequest(api_model_id="text-embedding-synthetic", inputs=("첫째", "둘째"), dimensions=3)
OPTIONS = InvokeOptions(timeout_ms=1500)
HTTP_REQUEST = httpx2.Request("POST", "https://provider.invalid/v1")
ENV_KEY = "sk-from-environment-synthetic"
TAGS = Tags(tenant="t-1", module="greenwash")


class FakeEmbeddings:
    def __init__(self, reply: CreateEmbeddingResponse | Exception) -> None:
        self._reply = reply
        self.kwargs: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> CreateEmbeddingResponse:
        self.kwargs.append(kwargs)
        if isinstance(self._reply, Exception):
            raise self._reply
        return self._reply


class FakeOpenAIEmbeddings:
    def __init__(self, reply: CreateEmbeddingResponse | Exception) -> None:
        self.embeddings = FakeEmbeddings(reply)


def answer() -> CreateEmbeddingResponse:
    """index 가 1, 0 차례인 답(가상 수)."""
    return CreateEmbeddingResponse.model_validate(
        {
            "object": "list",
            "model": "text-embedding-synthetic-2026",
            "data": [
                {"object": "embedding", "index": 1, "embedding": [0.0, 1.0, 0.0]},
                {"object": "embedding", "index": 0, "embedding": [1.0, 0.0, 0.0]},
            ],
            "usage": {"prompt_tokens": 7, "total_tokens": 7},
        }
    )


def http_response(status: int) -> httpx2.Response:
    return httpx2.Response(status, request=HTTP_REQUEST)


# 20. 요청 꼴


def test_the_request_asks_for_floats_and_does_not_send_dimensions() -> None:
    assert OpenAIEmbeddingProvider().build_request(REQUEST) == {
        "model": "text-embedding-synthetic",
        "input": ["첫째", "둘째"],
        "encoding_format": "float",
    }


# 21. 답 풀기


def test_vectors_follow_the_index_and_tokens_and_model_come_from_the_answer() -> None:
    fake = FakeOpenAIEmbeddings(answer())

    result = OpenAIEmbeddingProvider(fake).embed(REQUEST, OPTIONS)

    assert result == EmbeddingVectors(
        vectors=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)), input_tokens=7, model_id="text-embedding-synthetic-2026"
    )
    assert fake.embeddings.kwargs == [{**OpenAIEmbeddingProvider().build_request(REQUEST), "timeout": 1.5}]


# 21-2. usage 가 없는 답, index 가 겹치거나 빠진 답


def test_an_answer_without_usage_reports_no_tokens_and_is_recorded_without_cost() -> None:
    config = load_config(default_config_sources(synthetic=False))
    model = resolve_embedding_route(config, "light-openai")
    vector = [0.0] * model.dimensions
    no_usage = CreateEmbeddingResponse.model_construct(
        object="list",
        model="text-embedding-synthetic-2026",
        data=[Embedding(object="embedding", index=0, embedding=vector)],
    )
    adapter = OpenAIEmbeddingProvider(FakeOpenAIEmbeddings(no_usage))
    assert adapter.embed(REQUEST, OPTIONS) == EmbeddingVectors(
        vectors=(tuple(vector),), input_tokens=None, model_id="text-embedding-synthetic-2026"
    )

    sink = MemorySink()
    client = EmbeddingClient(config=config, providers={"openai": adapter}, log=sink)
    result = client.embed(EmbedRequest(inputs=["가"], route="light-openai", tags=TAGS))

    assert isinstance(result, Embedded)
    (record,) = sink.records
    assert record.result_kind == "success"
    assert (record.input_tokens, record.output_tokens, record.cost_usd) == (None, None, None)
    assert record.cost_bound_usd is not None and record.cost_bound_usd > 0  # LH3 Q6 — 손셈은 test_lh3_bounds.py
    assert result.meta.attempts[0].usage is None
    assert result.meta.total_cost_usd == 0


@pytest.mark.parametrize("indexes", [(0, 0), (0, 2), (1, 2)])
def test_overlapping_or_missing_indexes_are_a_non_retryable_error(indexes: tuple[int, int]) -> None:
    reply = CreateEmbeddingResponse.model_validate(
        {
            "object": "list",
            "model": "text-embedding-synthetic-2026",
            "data": [{"object": "embedding", "index": i, "embedding": [1.0, 0.0, 0.0]} for i in indexes],
            "usage": {"prompt_tokens": 7, "total_tokens": 7},
        }
    )
    result = OpenAIEmbeddingProvider(FakeOpenAIEmbeddings(reply)).embed(REQUEST, OPTIONS)
    assert isinstance(result, ProviderError)
    assert (result.status, result.retryable) == (None, False)
    assert "index" in result.message


# 22. 예외의 매핑


def run(error: Exception) -> object:
    return OpenAIEmbeddingProvider(FakeOpenAIEmbeddings(error)).embed(REQUEST, OPTIONS)


def test_sdk_errors_map_to_the_error_branches_without_keys() -> None:
    assert isinstance(run(openai.APITimeoutError(request=HTTP_REQUEST)), ProviderTimeout)
    assert run(openai.APIConnectionError(message="끊김", request=HTTP_REQUEST)) == ProviderError(
        status=None, retryable=True, message="끊김", error_kind="connection"
    )
    assert run(openai.RateLimitError("한도", response=http_response(429), body=None)) == ProviderError(
        status=429, retryable=True, message="한도", error_kind="rate_limited"
    )
    assert run(openai.InternalServerError("서버", response=http_response(500), body=None)) == ProviderError(
        status=500, retryable=True, message="서버", error_kind="server_error"
    )
    bad = run(openai.BadRequestError("bad key sk-synthetic-key-0000", response=http_response(400), body=None))
    assert isinstance(bad, ProviderError)
    assert (bad.status, bad.retryable) == (400, False)
    assert "sk-synthetic" not in bad.message


# 23. 클라이언트 없음, 빈 키


def test_without_a_client_it_returns_an_error_and_an_empty_key_is_refused() -> None:
    result = OpenAIEmbeddingProvider().embed(REQUEST, OPTIONS)
    assert isinstance(result, ProviderError)
    assert (result.status, result.retryable) == (None, False)
    with pytest.raises(LiveSetupError, match="키가 비었다"):
        create_openai_embedding_client("  ")


# 24. 소켓 문지기 아래의 진짜 SDK 클라이언트


def test_the_real_sdk_client_uses_the_given_key_and_is_stopped_at_the_socket(
    monkeypatch: pytest.MonkeyPatch, blocked_network: list[object]
) -> None:
    """진짜 SDK 클라이언트로 불러도 소켓에서 막힌다(실호출 0 을 기계로). 그 실패는 재시도 가능한 오류 갈래로
    돌아온다.
    """
    # ★ 막혀 있는지를 네트워크 없이 먼저 본다. 고정물이 꺼져 있으면 진짜 클라이언트를 짓지 않고 여기서 멈춘다.
    if getattr(socket.getaddrinfo, "__name__", "") != "blocked_getaddrinfo":
        pytest.fail("소켓이 막혀 있지 않다. 진짜 SDK 클라이언트를 부르지 않고 멈춘다")
    monkeypatch.setenv("OPENAI_API_KEY", ENV_KEY)
    key = "sk-synthetic-embedding-key-0000"
    client: Any = create_openai_embedding_client(key)
    assert client.api_key == key

    result = OpenAIEmbeddingProvider(client).embed(REQUEST, OPTIONS)

    assert blocked_network, "SDK 가 네트워크로 나가려 하지 않았다: 이 테스트는 아무것도 재지 못했다"
    assert isinstance(result, ProviderError)
    assert (result.status, result.retryable) == (None, True)
    assert key not in result.message
    assert ENV_KEY not in result.message


# 25. 세우기


def test_build_embedding_client_with_mock_and_with_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", ENV_KEY)
    sink = MemorySink()
    client = build_embedding_client(LlmSettings(), mock=True, sink=sink)

    result = client.embed(EmbedRequest(inputs=["가", "나", "다"], route="mock-gw1", tags=TAGS, batch_size=2))

    assert isinstance(result, Embedded)
    assert len(result.vectors) == 3
    assert len(sink.records) == len(result.meta.attempts) == 2

    # 환경에 키가 있어도 설정(LlmSettings)에 키가 없으면 SDK 객체를 만들지 않고 멈춘다.
    real = build_embedding_client(LlmSettings(), sink=MemorySink())
    with pytest.raises(LiveSetupError, match="키가 없다"):
        real.embed(EmbedRequest(inputs=["가"], route="light-openai", tags=TAGS))

    dry = build_embedding_client(LlmSettings(), assemble_only=True, sink=MemorySink())
    report = dry.dry_run(EmbedRequest(inputs=["가", "나"], route="light-openai", tags=TAGS))
    assert (report.provider, report.requests, report.inputs) == ("openai", 1, 2)
    real_model = resolve_embedding_route(load_config(default_config_sources(synthetic=False)), "light-openai")
    assert report.request == {"model": real_model.api_model_id, "input": ["가", "나"], "encoding_format": "float"}
