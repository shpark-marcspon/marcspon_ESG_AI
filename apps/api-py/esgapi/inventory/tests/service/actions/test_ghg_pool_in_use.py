"""풀 쪽 사용 중 판정(밴드 K1b-2b ④ — sid:MARC-ISSUE-432, 발주서 §2-6·3-5). 업무 층.

어느 회사든 고른 잎·잡은 계수는 운영 관리자가 지우거나 잎의 코드·단위를 바꾸면 409 in_use(InUse — 풀 id 만).
툴팁·기본 바꾸기·쓰이는 계수 고치기(새 판)는 된다(감독 판단 8). 숨긴 선택도 쓰는 것, 삭제 표시한 선택은 아니다.
회사·사업장은 conftest `companies` 와 organization services 로, 선택은 actions 로 짓는다. 이름·값은 지어낸 것이다.
"""

from datetime import date

import pytest

from esgapi.inventory.models import CompanyIndexSelection
from esgapi.inventory.service.actions import ghg_pool as actions
from esgapi.inventory.service.actions import index_selection as selection_actions
from esgapi.inventory.service.utils.ghg_pool import FacilityView, FactorView, InUse
from esgapi.inventory.service.utils.index_selection import SaveResult
from esgapi.inventory.tests.ghg_pool_support import ADMIN, code, draft, factor
from esgapi.inventory.tests.index_selection_support import YEAR, Leaf, site, two_leaves

pytestmark = pytest.mark.django_db

ON = date(2026, 10, 29)


def choose(company_id: int, *leaves: Leaf) -> None:
    saved = selection_actions.save_selections(company_id, YEAR, [leaf.id for leaf in leaves], on=ON)
    assert isinstance(saved, SaveResult) and saved.selected == len(leaves), saved


def save_leaf(
    leaf: Leaf,
    *,
    facility_code_id: int | None = None,
    unit: tuple[str, str] = ("mass", "kg"),
    tooltip: str = "",
    default_factor_id: int | None = None,
) -> object:
    return actions.save_facility(
        actor_kind=ADMIN,
        node_id=leaf.id,
        facility_code_id=leaf.code_id if facility_code_id is None else facility_code_id,
        unit=unit,
        tooltip=tooltip,
        default_factor_id=default_factor_id,
    )


@pytest.fixture
def chosen(companies: tuple[int, int]) -> tuple[Leaf, Leaf]:
    """B 가 잎 하나(boiler)를 골랐다. 다른 잎(burner)은 아무도 안 골랐다."""
    _, b = companies
    boiler, burner = two_leaves()
    site(b, boiler.code_id, burner.code_id)
    choose(b, boiler)
    return boiler, burner


def test_a_chosen_leafs_code_or_unit_cannot_change(chosen: tuple[Leaf, Leaf]) -> None:
    boiler, burner = chosen
    assert save_leaf(boiler, facility_code_id=code("다른 코드")) == InUse(frozenset({boiler.id}))
    assert save_leaf(boiler, unit=("mass", "t")) == InUse(frozenset({boiler.id}))
    assert isinstance(save_leaf(burner, unit=("mass", "t")), FacilityView)  # 짝: 아무도 안 고른 잎은 바뀐다


def test_a_chosen_leafs_tooltip_and_default_can_change(chosen: tuple[Leaf, Leaf]) -> None:
    boiler, _ = chosen
    tooltip = save_leaf(boiler, tooltip="지어낸 도움말")
    assert isinstance(tooltip, FacilityView) and tooltip.tooltip == "지어낸 도움말"
    other = factor(boiler.id, name="둘째 계수")
    switched = save_leaf(boiler, default_factor_id=other.id)
    assert isinstance(switched, FacilityView)
    assert [summary.is_default for summary in switched.factors if summary.id == other.id] == [True]


def test_a_chosen_leaf_or_a_pinned_factor_cannot_be_deleted(chosen: tuple[Leaf, Leaf]) -> None:
    boiler, burner = chosen
    assert boiler.factor_id is not None and burner.factor_id is not None
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[boiler.id]) == InUse(frozenset({boiler.id}))
    assert actions.delete_factors(actor_kind=ADMIN, ids=[boiler.factor_id]) == InUse(frozenset({boiler.factor_id}))
    assert actions.delete_factors(actor_kind=ADMIN, ids=[burner.factor_id]) == 1  # 짝: 안 잡힌 계수는 지운다
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[burner.id]) == 1


def test_deleting_a_leaf_checks_its_factors_too(chosen: tuple[Leaf, Leaf]) -> None:
    """L3: 잎 지우기는 그 잎의 계수가 잡혔는지도 본다(노드 판정을 비워도 계수 판정이 막는다)."""
    boiler, _ = chosen
    assert boiler.factor_id is not None
    found = actions.delete_nodes(actor_kind=ADMIN, ids=[boiler.id], nodes_in_use=lambda ids: frozenset())
    assert found == InUse(frozenset({boiler.factor_id}))


def test_editing_a_pinned_factor_makes_a_new_version(chosen: tuple[Leaf, Leaf]) -> None:
    boiler, _ = chosen
    assert boiler.factor_id is not None
    edited = actions.save_factor(actor_kind=ADMIN, factor_id=boiler.factor_id, draft=draft(name="고친 계수"))
    assert isinstance(edited, FactorView) and edited.version == 2


def test_a_hidden_choice_is_in_use_and_a_deleted_one_is_not(companies: tuple[int, int]) -> None:
    a, _ = companies
    boiler, burner = two_leaves()
    site(a, boiler.code_id, burner.code_id)
    choose(a, boiler, burner)
    hidden = selection_actions.save_selections(
        a, YEAR, [burner.id], on=ON, with_data=lambda company_id, year_id, ids: frozenset(ids)
    )
    assert hidden == SaveResult(selected=1, hidden_with_data=1)  # boiler 숨김
    choose(a)  # burner 뺌 → 삭제 표시(boiler 는 이미 숨김)
    rows = {
        row.facility_node_id: (row.hidden, row.deleted_at is not None) for row in CompanyIndexSelection.for_company(a)
    }
    assert rows == {boiler.id: (True, False), burner.id: (False, True)}  # 분모
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[boiler.id]) == InUse(frozenset({boiler.id}))
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[burner.id]) == 1
