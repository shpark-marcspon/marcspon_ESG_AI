"""키 가림(redact_keys)이 지나는 자리마다의 회귀(밴드 LH1 S5 — MARC-ISSUE-306 m4). 순수 층.

자리: 공급사 셋의 오류 옮기기(openai·anthropic `_map_error`, gemini 의 APIError 갈래·그 밖 갈래), 호출 층이 어댑터의
예외를 받는 자리(`client._invoke`), 임베딩 호출 길의 같은 자리(`embedding._invoke`). 자리마다 가짜 키 둘(`sk-` 꼴·`AIza`
꼴)을 실은 예외를 넣고, 결과 글에 원문이 없고 가린 표시가 있음을 본다 — 가림을 하나 지우면 그 자리의 시험이 빨개진다.
★ 키는 지어낸 글자다(`…-synthetic`). 공급사로 가는 호출은 없다(가짜 SDK 객체).
"""

from pathlib import Path

import anthropic
import openai
import pytest
from google.genai import errors as genai_errors

from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.embedding import EmbeddingClient, EmbedProviderFailed, EmbedRequest
from esgapi.core.llm.embedding_types import EmbeddingProviderRequest, EmbeddingProviderResponse
from esgapi.core.llm.providers.anthropic import AnthropicProvider
from esgapi.core.llm.providers.gemini import GeminiProvider
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import InvokeOptions, ProviderError, ProviderFailed, ProviderRequest, ProviderResponse
from esgapi.core.tests.llm_support import TAGS, harness
from esgapi.core.tests.test_llm_adapters import OPTIONS, REQUEST, FakeAnthropic, FakeOpenAI, http_response
from esgapi.core.tests.test_llm_gemini import FakeGemini

SK = "sk-LH1-synthetic"
AIZA = "AIzaLH1-synthetic"
LEAK = f"공급사 글: key={SK} other={AIZA}"


def assert_redacted(message: str) -> None:
    assert SK not in message and AIZA not in message
    assert "sk-[가림]" in message and "AIza[가림]" in message


def error_message(result: ProviderResponse) -> str:
    assert isinstance(result, ProviderError)
    return result.message


@pytest.mark.parametrize("status", [401, 429], ids=["not-retryable", "retryable"])
def test_openai_map_error(status: int) -> None:
    error = openai.APIStatusError(LEAK, response=http_response(status), body=None)
    assert_redacted(error_message(OpenAIProvider(FakeOpenAI(error)).invoke(REQUEST, OPTIONS)))


@pytest.mark.parametrize("status", [401, 529], ids=["not-retryable", "retryable"])
def test_anthropic_map_error(status: int) -> None:
    error = anthropic.APIStatusError(LEAK, response=http_response(status), body=None)
    assert_redacted(error_message(AnthropicProvider(FakeAnthropic(error)).invoke(REQUEST, OPTIONS)))


def test_gemini_map_error_api_error() -> None:
    error = genai_errors.APIError(400, {"error": {"code": 400, "message": LEAK}})
    assert_redacted(error_message(GeminiProvider(FakeGemini(error)).invoke(REQUEST, OPTIONS)))


def test_gemini_map_error_other_exception() -> None:
    assert_redacted(error_message(GeminiProvider(FakeGemini(RuntimeError(LEAK))).invoke(REQUEST, OPTIONS)))


class RaisingProvider(MockProvider):
    """어댑터 약속(던지지 않음)을 어기는 공급사 — 호출 층의 `_invoke` 가 받는다."""

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        raise RuntimeError(LEAK)


def test_client_invoke(prompt_root: Path) -> None:
    h = harness(prompt_root, providers={"mock": RaisingProvider()})
    result = h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS))
    assert isinstance(result, ProviderFailed)
    assert_redacted(result.message)
    assert all(SK not in str(record.to_json()) for record in h.log.records)


class RaisingEmbedding:
    name = "mock"

    def build_request(self, request: EmbeddingProviderRequest) -> dict[str, object]:
        return {"model": request.api_model_id}

    def embed(self, request: EmbeddingProviderRequest, options: InvokeOptions) -> EmbeddingProviderResponse:
        raise RuntimeError(LEAK)


def test_embedding_invoke() -> None:
    config = load_config(default_config_sources(synthetic=True))
    limits: list[BudgetLimit] = []
    client = EmbeddingClient(config=config, providers={"mock": RaisingEmbedding()}, log=MemorySink(), limits=limits)
    result = client.embed(EmbedRequest(inputs=["지어낸 글"], route="mock-gw1", tags=TAGS))
    assert isinstance(result, EmbedProviderFailed)
    assert_redacted(result.message)
