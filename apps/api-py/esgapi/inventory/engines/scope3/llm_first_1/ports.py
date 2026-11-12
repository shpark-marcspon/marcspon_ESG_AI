"""순수 층이 바깥(계수 표, 생성 모델)에 기대는 자리. esg-lab `ts/scope3/src/domain/ports.ts` 에서 옮겼다.

구현은 이 폴더 밖에 있다: 계수는 업무 층이 `reference` 의 selector 에서 읽어 `catalog.ListFactorCatalog` 로 넘기고,
생성 모델은 `esgapi.core.llm` 의 `LlmClient` 가 그대로 맞는다. 추리기의 포트(`Shortlister`)는 `shortlister.py` 에 있다.
옮기지 않은 것: `QueryEmbedder`·`FactorVectorIndex`(임베딩 갈래).
"""

from typing import Protocol

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.types import LlmResult
from esgapi.inventory.engines.scope3.llm_first_1.types import CandidateQuery, Factor


class FactorCatalog(Protocol):
    """계수 카탈로그의 읽기 포트. 파이프라인이 실제로 부르는 것만 있다."""

    def get(self, factor_id: str) -> Factor | None:
        """후보가 될 수 있는 계수만 돌려준다. 후보가 아닌 낱줄의 id 와 없는 id 는 None."""
        ...

    def candidates(self, query: CandidateQuery) -> list[Factor]:
        """조건에 맞는 후보(표의 순서). 빈 목록은 「조건에 맞는 계수가 없다」는 뜻이고 읽기 실패는 예외다."""
        ...


class LlmGateway(Protocol):
    """생성 모델 호출 포트. 파이프라인이 쓰는 것은 `call` 하나다. 동기다(`core.llm` 이 동기다)."""

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]: ...
