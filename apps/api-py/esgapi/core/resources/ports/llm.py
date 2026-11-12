"""포트: LLM 공급사. 구현은 core/resources/llm.py 의 make(name) 이 고른다(mock · openai · anthropic · gemini).
임베딩 공급사(EmbeddingProvider)는 make_embedding(name) 이 고른다(mock · openai).

모듈은 이 포트를 직접 부르지 않는다. 호출 층(esgapi.core.llm 의 LlmClient)이 경로의 모델 순회, 스키마 재시도,
예산 상한, 호출 기록을 얹어 부른다.
"""

from typing import Protocol

from esgapi.core.llm.embedding_types import EmbeddingProviderRequest, EmbeddingProviderResponse
from esgapi.core.llm.types import InvokeOptions, ProviderRequest, ProviderResponse


class Provider(Protocol):
    @property
    def name(self) -> str:
        """공급사 이름. 모델 설정 파일의 `provider` 값과 맞춘다."""
        ...

    def build_request(self, request: ProviderRequest) -> object:
        """네트워크 없이 공급사 고유 요청 본문만 조립한다. JSON 으로 낼 수 있는 값이다. dry-run 과 단위 테스트가
        쓴다.
        """
        ...

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        """공급사를 한 번 부른다. 실패를 던지지 않고 `ProviderResponse` 의 갈래로 돌려준다."""
        ...


class EmbeddingProvider(Protocol):
    """임베딩 공급사. 호출 층(esgapi.core.llm.embedding 의 EmbeddingClient)이 묶음 나누기, 예산 상한, 호출 기록을
    얹어 부른다.
    """

    @property
    def name(self) -> str:
        """공급사 이름. 모델 설정 파일의 `provider` 값과 맞춘다."""
        ...

    def build_request(self, request: EmbeddingProviderRequest) -> object:
        """네트워크 없이 공급사 고유 요청 본문만 조립한다. dry-run 과 단위 테스트가 쓴다."""
        ...

    def embed(self, request: EmbeddingProviderRequest, options: InvokeOptions) -> EmbeddingProviderResponse:
        """묶음 하나를 한 번 부른다. 실패를 던지지 않고 `EmbeddingProviderResponse` 의 갈래로 돌려준다."""
        ...
