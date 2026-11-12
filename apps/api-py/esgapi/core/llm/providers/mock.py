"""키 없이 쓰는 모의 공급사. 심어 둔 응답을 순서대로 돌려주고 받은 요청을 기록한다.

임베딩의 모의(MockEmbeddingProvider)는 심어 둔 답이 없으면 결정적 벡터를 짓는다(mock_vector).
"""

import hashlib
import math
from collections import deque
from collections.abc import Callable, Sequence
from typing import Self

from esgapi.core.llm.embedding_types import EmbeddingProviderRequest, EmbeddingProviderResponse, EmbeddingVectors
from esgapi.core.llm.types import (
    AssistantText,
    Completed,
    FunctionCall,
    InvokeOptions,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeout,
    ToolCallsRequested,
    UrlCitation,
    Usage,
)

type MockReply = ProviderResponse | Callable[[ProviderRequest], ProviderResponse]

# `enqueue_text` 가 사용량을 받지 않았을 때 쓰는 가상(synthetic) 사용량. 실제 값이 아니다.
SYNTHETIC_USAGE = Usage(input_tokens=100, output_tokens=20, cache_read_tokens=0, cache_write_tokens=0)


class MockProvider:
    def __init__(self, name: str = "mock") -> None:
        self._name = name
        self.calls: list[ProviderRequest] = []
        self._queue: deque[tuple[MockReply, float]] = deque()
        self._call_seq = 0

    @property
    def name(self) -> str:
        return self._name

    def enqueue(self, reply: MockReply, *, delay_ms: float = 0) -> Self:
        """다음 호출이 받을 응답을 심는다.

        `delay_ms` 는 「이만큼 늦게 답하는 공급사」를 흉내 낸다(시간 초과 시험용). 실제로 기다리지는 않는다:
        호출의 시간 제한보다 길거나 같으면 시간 초과로 답하고, 짧으면 바로 답한다.
        """
        self._queue.append((reply, delay_ms))
        return self

    def enqueue_text(
        self,
        text: str,
        usage: Usage = SYNTHETIC_USAGE,
        *,
        citations: Sequence[UrlCitation] = (),
        hosted_calls: int = 0,
    ) -> Self:
        """글자만 주면 완료 응답으로 심는다. 사용량을 주지 않으면 가상 값이다.

        `citations`·`hosted_calls` 는 공급사가 웹 검색을 실행한 답을 흉내 낸다(도구 호출 고리의 시험용).
        """
        return self.enqueue(Completed(text=text, usage=usage, citations=tuple(citations), hosted_calls=hosted_calls))

    def enqueue_tool_calls(
        self,
        calls: Sequence[tuple[str, str]],
        *,
        text: str = "",
        usage: Usage = SYNTHETIC_USAGE,
        hosted_calls: int = 0,
    ) -> Self:
        """도구 호출 응답을 심는다. `calls` 는 (도구 이름, 인자 JSON 글자)의 차례다.

        `text` 를 주면 호출들 앞의 글이 된다.

        call_id 는 이 모의 공급사에 심은 차례대로 `call_1`, `call_2` … 다(결정적. 응답을 넘어 겹치지 않는다).
        """
        output: list[AssistantText | FunctionCall] = [AssistantText(text=text)] if text else []
        for name, arguments in calls:
            self._call_seq += 1
            output.append(FunctionCall(call_id=f"call_{self._call_seq}", name=name, arguments=arguments))
        return self.enqueue(ToolCallsRequested(output=tuple(output), usage=usage, hosted_calls=hosted_calls))

    @property
    def pending(self) -> int:
        return len(self._queue)

    def build_request(self, request: ProviderRequest) -> object:
        return {"mock": True, **request.to_json()}

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        self.calls.append(request)
        if not self._queue:
            # 심어 둔 응답이 없으면 성공을 지어내지 않고 오류로 돌린다.
            return ProviderError(
                status=None, retryable=False, message=f"모의 공급사 {self._name} 에 심어 둔 응답이 없다"
            )
        reply, delay_ms = self._queue.popleft()
        if delay_ms >= options.timeout_ms:
            return ProviderTimeout(message="모의 공급사: 시간 제한 안에 답하지 않았다")
        return reply(request) if callable(reply) else reply


# ── 임베딩 ──

type MockEmbeddingReply = EmbeddingProviderResponse | Callable[[EmbeddingProviderRequest], EmbeddingProviderResponse]


def mock_vector(text: str, dim: int) -> tuple[float, ...]:
    """글자 둘씩의 해시를 칸에 더해 길이 1 로 맞춘 벡터. 같은 글이면 늘 같은 벡터다. 뜻을 담지 않는다(가상).

    ★ GW1(esg-lab `py/greenwash/ports.py` 의 `MockEmbedding._vector`)과 같은 셈이다 — 바꾸면 테스트의 해시가
      빨갛고, 흐름이 GW1 의 기준선을 이 모의로 다시 내지 못한다. 글자 둘의 sha256 앞 4바이트(big-endian)를 `dim` 으로
      나눈 나머지 칸에, 5번째 바이트가 짝수면 +1 홀수면 -1. 노름이 0 이면 0번 칸을 1 로 둔다.
    """
    vector = [0.0] * dim
    grams = [text[i : i + 2] for i in range(max(1, len(text) - 1))]
    for gram in grams:
        digest = hashlib.sha256(gram.encode("utf-8")).digest()
        vector[int.from_bytes(digest[:4], "big") % dim] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        vector[0] = 1.0
        norm = 1.0
    return tuple(x / norm for x in vector)


class MockEmbeddingProvider:
    """키 없이 쓰는 모의 임베딩 공급사. 받은 요청을 기록한다.

    심어 둔 답이 있으면 그것을 차례로 돌려주고(실패·이상한 모양을 심는 길), 없으면 입력마다 `mock_vector` 로 짓는다
    (채팅의 모의와 달리 늘 답한다). 그때의 `input_tokens` 는 묶음의 글자 수 합이다(가상 — 실제 토큰 수가 아니다).
    """

    def __init__(self, name: str = "mock") -> None:
        self._name = name
        self.calls: list[EmbeddingProviderRequest] = []
        self._queue: deque[tuple[MockEmbeddingReply, float]] = deque()

    @property
    def name(self) -> str:
        return self._name

    def enqueue(self, reply: MockEmbeddingReply, *, delay_ms: float = 0) -> Self:
        """다음 호출이 받을 답을 심는다. `delay_ms` 의 뜻은 MockProvider.enqueue 와 같다(실제로 기다리지 않는다)."""
        self._queue.append((reply, delay_ms))
        return self

    @property
    def pending(self) -> int:
        return len(self._queue)

    def build_request(self, request: EmbeddingProviderRequest) -> object:
        return {"mock": True, **request.to_json()}

    def embed(self, request: EmbeddingProviderRequest, options: InvokeOptions) -> EmbeddingProviderResponse:
        self.calls.append(request)
        if not self._queue:
            return EmbeddingVectors(
                vectors=tuple(mock_vector(text, request.dimensions) for text in request.inputs),
                input_tokens=sum(len(text) for text in request.inputs),
            )
        reply, delay_ms = self._queue.popleft()
        if delay_ms >= options.timeout_ms:
            return ProviderTimeout(message="모의 공급사: 시간 제한 안에 답하지 않았다")
        return reply(request) if callable(reply) else reply
