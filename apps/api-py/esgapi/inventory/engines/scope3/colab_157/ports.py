"""순수 층이 바깥(생성 모델, 지오코더)에 기대는 자리(처분 ⑥).

구현은 이 폴더 밖에 있다: 생성 모델은 `esgapi.core.llm` 의 `LlmClient` 가 그대로 맞는다. 지오코더의 실제 공급원은
정하지 않았다(`MARC-ENT-167`, held) — 시험의 가짜(`tests/engines/scope3/colab_157/support.py`)뿐이다.
`LlmGateway` 는 `engines/scope3/llm_first_1/ports.py` 의 것과 같은 꼴을 **복사**했다(판끼리 import 하지 않는다 —
`MARC-ENT-267`, `.importlinter` 의 `inventory-scope3-versions-apart`).

계수 책은 포트가 아니라 실행 때 받는 값이다(`tools/scope3_sheets/grid.py` 의 `Workbook` — 흐름이 바이트를 읽어 넘긴다).
회사별 매핑은 어댑터가 아니라 입력 템플릿의 시트다(코랩 `:5978-5985`, S3C-b).
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.types import LlmResult


class LlmGateway(Protocol):
    """생성 모델 호출 포트. 엔진이 쓰는 것은 `call` 하나다. 동기다(`core.llm` 이 동기다)."""

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]: ...


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class NotFound:
    """지오코더가 그 글을 찾지 못했다(코랩 `geolocator.geocode(...)` 가 None). 호출 실패는 예외다."""

    query: str
    kind: Literal["not_found"] = "not_found"


class Geocoder(Protocol):
    """지명 → 좌표(코랩 `_cached_geocode` `:1072` 의 자리). S3C-a 에서 부르는 곳은 0 — S3C-b(거리)가 쓴다."""

    def geocode(self, query: str) -> Coordinates | NotFound: ...


class NoGeocoder:
    """「늘 못 찾음」 지오코더(S3C-b2a). 실제 공급원이 정해지기 전(`MARC-ENT-167`, held)의 흐름 어댑터 자리다.

    부르는 쪽(distance.py)은 코랩대로 못 찾으면 AI 직선거리로 간다. 도시 정규화(`normalize_city`)는 지오코더 앞이라
    못 찾아도 두 번 불린다. BINDINGS 에 잇는 것은 X1b 뒤다 — 이 밴드는 클래스와 시험뿐.
    """

    def geocode(self, query: str) -> Coordinates | NotFound:
        return NotFound(query)
