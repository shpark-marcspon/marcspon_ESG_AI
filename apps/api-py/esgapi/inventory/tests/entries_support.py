"""Scope 1·2 입력 시험이 같이 쓰는 도우미(밴드 S12a·S12a-2). 이름·값은 지어낸 것이다(실제 회사·계수 0).

풀은 ghg_pool_support·index_selection_support 로, 사업장·자산/시설은 organization 의 services·selectors 로 짓는다
(organization models import 0 — 계약 나). 회사 둘은 뿌리 conftest 의 `companies`.
"""

from dataclasses import dataclass
from typing import Any

from esgapi.inventory.models import CompanyIndexSelection, InventoryCustomFactor, InventoryEntryRow, InventoryYear
from esgapi.inventory.service.utils.ghg_pool import GASES
from esgapi.inventory.tests.index_selection_support import YEAR, Leaf, current_version, site
from esgapi.organization.service.selectors.branches import facilities_of


@dataclass(frozen=True)
class Place:
    """한 회사의 입력 자리: 해·선택(잎 하나)·사업장·그 잎 코드의 자산/시설 하나."""

    company_id: int
    year_id: int
    selection_id: int
    node_id: int
    version_id: int
    site_id: int
    facility_id: int


def place(company_id: int, leaf: Leaf, *, year: int = YEAR, site_name: str = "가 공장") -> Place:
    """그 회사에 해·선택(잡은 판 = 잎 기본 계수의 지금 판)·사업장(자산/시설 하나)을 짓는다."""
    year_id = InventoryYear.for_company(company_id).create(year=year).pk
    version_id = current_version(leaf.id)
    selection_id = (
        CompanyIndexSelection.for_company(company_id)
        .create(inventory_year_id=year_id, facility_node_id=leaf.id, factor_version_id=version_id)
        .pk
    )
    site_id = site(company_id, leaf.code_id, name=site_name)
    (facility,) = facilities_of(company_id, site_id)
    return Place(company_id, year_id, selection_id, leaf.id, version_id, site_id, facility.id)


def entry_row(where: Place, **fields: Any) -> InventoryEntryRow:
    """그 자리의 입력 행 하나(단위 기본 kg — 잎 단위)."""
    values: dict[str, Any] = {"unit": "kg"} | fields
    return InventoryEntryRow.for_company(where.company_id).create(
        selection_id=where.selection_id, site_facility_id=where.facility_id, **values
    )


def custom_factor(company_id: int, **fields: Any) -> InventoryCustomFactor:
    """그 회사의 직접입력 계수 하나(지어낸 값 — kg/kL, CO2 하나만 켬)."""
    gases: list[dict[str, object]] = [
        {
            "gas": gas,
            "enabled": gas == "CO2",
            "factor": "2" if gas == "CO2" else None,
            "gwp": "1" if gas == "CO2" else None,
        }
        for gas in GASES
    ]
    values: dict[str, Any] = {
        "name": "가 직접 계수",
        "source": "지어낸 출처",
        "base_year": 2024,
        "tier": 1,
        "country_code": "KR",
        "industry_code": "energy_industries",
        "input_unit_kind": "volume",
        "input_unit": "kL",
        "factor_unit": "kg/kL",
        "gases": gases,
        "actor_kind": "admin",
        "actor_user_id": 1,
    } | fields
    return InventoryCustomFactor.for_company(company_id).create(**values)


def select_leaf(company_id: int, year_id: int, leaf: Leaf, *, hidden: bool = False) -> int:
    """(S12b-1) 이미 있는 해에 잎 하나를 더 고른다(잡은 판 = 잎 기본 계수의 지금 판). 선택 id."""
    return (
        CompanyIndexSelection.for_company(company_id)
        .create(
            inventory_year_id=year_id,
            facility_node_id=leaf.id,
            factor_version_id=current_version(leaf.id),
            hidden=hidden,
        )
        .pk
    )
