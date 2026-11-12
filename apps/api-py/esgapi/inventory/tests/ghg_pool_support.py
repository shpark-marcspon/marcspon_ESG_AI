"""온실가스 풀 시험이 같이 쓰는 도우미(밴드 K1b-2a). 이름·값은 지어낸 것이다(실제 계수·GWP 0 — 뻔한 가짜 수만).

나무는 services·actions 로 짓는다(운영 관리자 kind 로). 시설 코드는 organization 의 services 로
(남의 models 직접 0 — 계약 나).
"""

from dataclasses import replace

from esgapi.inventory.models import GhgFactor, GhgFactorGas, GhgFactorVersion, GhgIndexNode
from esgapi.inventory.service.actions import ghg_pool as actions
from esgapi.inventory.service.services import ghg_pool as services
from esgapi.inventory.service.utils.ghg_pool import FacilityView, FactorDraft, FactorView, GasDraft, NodeView
from esgapi.organization.service.services.facility_codes import create_code
from esgapi.organization.service.utils.entities import FacilityCodeInfo

ADMIN = "admin"
CUSTOMER = "service"


def code(name: str) -> int:
    made = create_code(actor_kind=ADMIN, name=name)
    assert isinstance(made, FacilityCodeInfo), made
    return made.id


def node(level: str, name: str, parent_id: int | None = None) -> int:
    made = services.create_node(actor_kind=ADMIN, level=level, parent_id=parent_id, name=name)
    assert isinstance(made, NodeView), made
    return made.id


def activity(prefix: str = "가") -> int:
    """범위 → 유형 → 활동 한 줄을 짓고 활동 id 를 돌려준다."""
    scope = node("scope", f"범위 {prefix}")
    kind = node("source_type", f"유형 {prefix}", scope)
    return node("activity", f"활동 {prefix}", kind)


def leaf(parent_id: int, code_name: str, unit: tuple[str, str] = ("mass", "kg")) -> int:
    made = actions.create_facility(
        actor_kind=ADMIN, parent_id=parent_id, facility_code_id=code(code_name), unit=unit, tooltip=""
    )
    assert isinstance(made, FacilityView), made
    return made.id


def draft(**fields: object) -> FactorDraft:
    base = FactorDraft(
        name="계수 가",
        source="지어낸 출처",
        base_year=2024,
        tier=1,
        country_code="KR",
        industry_code="other",
        input_unit=("mass", "kg"),
        emission_unit=None,
        ncv_enabled=False,
        ncv=None,
        ncv_unit=None,
        factor_unit=None,
        gases=(GasDraft("CO2", enabled=True, factor="1.5", gwp="1"),),
        note="",
    )
    return replace(base, **fields)  # type: ignore[arg-type]


def factor(node_id: int, **fields: object) -> FactorView:
    made = actions.create_factor(actor_kind=ADMIN, node_id=node_id, draft=draft(**fields))
    assert isinstance(made, FactorView), made
    return made


def counts() -> tuple[int, int, int, int]:
    """(노드, 계수, 판, 가스) 행 수 — 삭제 표시 포함."""
    return (
        GhgIndexNode.objects.count(),
        GhgFactor.objects.count(),
        GhgFactorVersion.objects.count(),
        GhgFactorGas.objects.count(),
    )
