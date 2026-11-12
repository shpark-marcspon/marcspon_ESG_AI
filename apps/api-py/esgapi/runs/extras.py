"""실행 기록 줄의 업무 몫 칸(AD-04 「검토」·「AI 설정」 — AD4S)을 채우는 원천의 등록부. 프로세스에 하나(EXTRAS).

왜 등록부인가: runs 는 업무 모듈을 import 하지 않는다(.importlinter 계약 차). 검토 표와 AI 설정 판의 꼴은 업무
모듈의 것이라 각 모듈의 AppConfig.ready() 가 원천 하나를 모듈 id 로 단다(core/flows/binding.py 의 BINDINGS 와 같은
꼴). runs 의 운영 관리자 selector(service/selectors/operator.py)는 이 등록부만 본다. 원천이 없는 모듈의 실행은
두 칸 다 null 이다.

규칙(감독 판단 Q2·Q3, band-handoffs/AD4S-order.md):
  검토     그 모듈 화면이 검토를 보이는 실행(원천의 reviewable_q — 술어는 원천 쪽 하나)에만 검토 행의 상태, 행이 없으면
           pending. 그 밖의 실행은 null. 상태 값은 operator.REVIEW_STATES 셋.
  AI 설정  실행의 versions(만들 때 한 번 적힌 판 묶음)에서 원천이 읽은 (판 id, 판 이름). 기본 판은 id None.
           못 읽으면 None.
회사 경계: 원천의 states·run_ids_in 은 그 회사의 검토 행만 본다(남의 회사 행의 run_id 는 「없음」과 같다).
"""

from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING, Any, Final, Protocol

from django.db.models import Q

if TYPE_CHECKING:
    from django.db.models.query import ValuesQuerySet  # 타입 검사기에만 있는 꼴(django-stubs)


class ExtrasRegistryError(Exception):
    """같은 모듈에 원천을 두 번 달았다."""


class RunExtrasSource(Protocol):
    """한 모듈의 검토·AI 설정 원천. 실행 행(run_runs)의 칸 이름으로 짓는 Q 하나와 회사 범위 읽기 둘, 순수 함수 하나."""

    def reviewable_q(self) -> Q:
        """검토를 보이는 실행의 조건(실행 행 기준 — 결과 표는 related 이름으로). 한 filter() 에 넣는다."""
        ...

    def states(self, company_id: int, run_ids: Collection[int]) -> Mapping[int, str]:
        """그 회사의 검토 행이 있는 실행 id → 상태. 쿼리 하나(run_ids 가 비면 부르지 않는다)."""
        ...

    def run_ids_in(self, company_id: int, states: Collection[str]) -> "ValuesQuerySet[Any, Any]":
        """그 회사에서 검토 상태가 states 안인 실행 id 의 부분 쿼리(values("run_id") — 따로 읽지 않는다)."""
        ...

    def ai_setting(self, versions: Mapping[str, object]) -> tuple[int | None, str] | None:
        """versions 에서 (판 id, 판 이름). 기본 판은 (None, 이름). 꼴이 어긋나면 None. 순수."""
        ...


class ExtrasRegistry:
    """모듈 id → 원천. 프로세스에 하나(EXTRAS). 순수 테스트는 새 것을 짓는다."""

    def __init__(self) -> None:
        self._sources: dict[str, RunExtrasSource] = {}

    def register(self, module: str, source: RunExtrasSource) -> None:
        """같은 모듈에 두 번 달면 ExtrasRegistryError(같은 객체여도 — BINDINGS.register 와 같은 규칙)."""
        if module in self._sources:
            raise ExtrasRegistryError(f"모듈 {module} 의 원천이 이미 있다")
        self._sources[module] = source

    def get(self, module: str) -> RunExtrasSource | None:
        return self._sources.get(module)

    def modules(self) -> tuple[str, ...]:
        """원천이 있는 모듈(단 차례)."""
        return tuple(self._sources)


EXTRAS: Final = ExtrasRegistry()
"""프로세스에 하나. 각 모듈의 AppConfig.ready() 가 흐름을 달 때 같이 단다."""
