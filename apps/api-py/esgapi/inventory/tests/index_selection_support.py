"""고객사 인덱스 선택 시험이 같이 쓰는 도우미(밴드 K1b-2b). 이름·값은 지어낸 것이다(실제 회사·계수 0).

풀은 ghg_pool_support 로(운영 관리자 kind), 회사의 사업장·자산/시설은 organization 의 services 로 짓는다
(organization models import 0 — 계약 나). 회사 둘은 뿌리 conftest 의 `companies`.
"""

from dataclasses import dataclass

from esgapi.inventory.models import GhgFactorVersion
from esgapi.inventory.service.actions import ghg_pool as pool_actions
from esgapi.inventory.service.selectors.entries import facilities_in_use
from esgapi.inventory.service.utils.ghg_pool import FacilityView, FactorView
from esgapi.inventory.tests.ghg_pool_support import ADMIN, activity, code, draft, factor
from esgapi.organization.service.services.branches import FacilityRow, insert_site_row, save_facilities
from esgapi.organization.service.utils.entities import Branch

YEAR = 2025


@dataclass(frozen=True)
class Leaf:
    id: int
    code_id: int
    factor_id: int | None


def pool_leaf(parent_id: int, code_name: str, *, with_factor: bool = True) -> Leaf:
    """풀 잎 하나(코드 새로) — with_factor 면 기본 계수 하나까지."""
    code_id = code(code_name)
    made = pool_actions.create_facility(
        actor_kind=ADMIN, parent_id=parent_id, facility_code_id=code_id, unit=("mass", "kg"), tooltip=""
    )
    assert isinstance(made, FacilityView), made
    factor_id = factor(made.id).id if with_factor else None
    return Leaf(id=made.id, code_id=code_id, factor_id=factor_id)


def two_leaves() -> tuple[Leaf, Leaf]:
    """활동 하나 아래 잎 둘(둘 다 기본 계수 있음)."""
    parent = activity()
    return pool_leaf(parent, "가 보일러"), pool_leaf(parent, "나 버너")


def site(company_id: int, *codes: int, name: str = "가 공장", inventory: bool = True) -> int:
    """그 회사의 사업장 하나와 코드마다 자산/시설 한 줄."""
    made = insert_site_row(company_id, name=name, inventory_enabled=inventory)
    assert isinstance(made, Branch), made
    rows = [FacilityRow(facility_code_id=code_id, detail_name=f"{index}호기") for index, code_id in enumerate(codes)]
    assert save_facilities(company_id, made.id, rows=rows, facilities_in_use=facilities_in_use) is None
    return made.id


def current_version(node_id: int) -> int:
    """잎의 기본 계수(삭제 안 된 것)의 가장 새 판 id(DB 에서 — 시험의 기대값)."""
    row = (
        GhgFactorVersion.objects.filter(
            factor__facility_node_id=node_id, factor__is_default=True, factor__deleted_at__isnull=True
        )
        .order_by("-version")
        .first()
    )
    assert row is not None, node_id
    return row.pk


def edit_factor(factor_id: int, name: str) -> FactorView:
    """풀에서 계수를 고친다(새 판)."""
    made = pool_actions.save_factor(actor_kind=ADMIN, factor_id=factor_id, draft=draft(name=name))
    assert isinstance(made, FactorView), made
    return made
