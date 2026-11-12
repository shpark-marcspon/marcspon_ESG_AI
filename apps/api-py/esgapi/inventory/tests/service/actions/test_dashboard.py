"""Scope 1·2 대시보드의 조립(service/actions/dashboard.py — 밴드 S12a-3 ①). 업무 층, 주인 역할 연결.

대시보드 뿌리 합 == 리스트(list_rows)의 그 해 Scope 값(같은 재료) · 꺼진 사업장·지운 행·숨긴/지운 선택·다른 해 행은 셈
0 · 주기 바꿈·계수 바꿈 뒤 값 · 해 없음 · 켠 사업장 행 없음 · 문제 행 → complete 거짓. 풀은 운영 관리자 actions 로,
사업장은 organization services 로 짓는다(organization models import 0). 이름·값은 지어낸 것이다(실제 회사·계수 0).

손셈(지어낸 행 배출량을 직접 넣음 — 셈은 S12a 시험 몫):
  범위 가 = 가 공장(잎1 1.5 · 잎2 2.25) + 나 공장(잎1 0.25) = 4 · 범위 나 = 가 공장(잎3 0.5) · 합계 4.5
"""

from dataclasses import dataclass
from decimal import Decimal

import pytest

from esgapi.inventory.models import CompanyIndexSelection, InventoryEntryRow, InventoryYear
from esgapi.inventory.service.actions import dashboard as actions
from esgapi.inventory.service.actions import entries as entry_actions
from esgapi.inventory.service.actions import scope3_state as scope3_actions
from esgapi.inventory.service.utils.dashboard import Dashboard
from esgapi.inventory.service.utils.entries import Actor, IndexDetail, RowInput, RowList, SlotInput
from esgapi.inventory.service.utils.ghg_pool import GasDraft
from esgapi.inventory.tests.ghg_pool_support import activity, factor
from esgapi.inventory.tests.index_selection_support import YEAR, Leaf, current_version, pool_leaf, site
from esgapi.inventory.tests.service.actions.test_scope3_state import done_body, failed, plant, processed
from esgapi.organization.service.selectors.branches import facilities_of
from esgapi.organization.service.services.branches import set_inventory

pytestmark = pytest.mark.django_db

CUSTOMER = Actor("service", 11)
OPERATOR = Actor("admin", 12)


@dataclass(frozen=True)
class World:
    """한 회사의 그 해: 잎 셋(잎1·잎2 = 범위 가/유형 가, 잎3 = 범위 나/유형 나)·선택 셋·사업장 둘."""

    company_id: int
    year_id: int
    leaves: tuple[Leaf, Leaf, Leaf]
    selections: dict[int, int]  # 잎 id → 선택 id
    sites: tuple[int, int]
    facilities: dict[tuple[int, int], int]  # (사업장 id, 잎 id) → 자산/시설 id


@pytest.fixture
def leaves() -> tuple[Leaf, Leaf, Leaf]:
    first = activity("가")
    second = activity("나")
    return pool_leaf(first, "가 보일러"), pool_leaf(first, "나 버너"), pool_leaf(second, "다 히터")


def world(
    company_id: int, leaves: tuple[Leaf, Leaf, Leaf], *, year: int = YEAR, sites: tuple[int, int] | None = None
) -> World:
    year_id = InventoryYear.for_company(company_id).create(year=year).pk
    selections = {
        leaf.id: CompanyIndexSelection.for_company(company_id)
        .create(inventory_year_id=year_id, facility_node_id=leaf.id, factor_version_id=current_version(leaf.id))
        .pk
        for leaf in leaves
    }
    codes = [leaf.code_id for leaf in leaves]
    if sites is None:
        sites = (site(company_id, *codes, name="가 공장"), site(company_id, *codes, name="나 공장"))
    by_code = {leaf.code_id: leaf.id for leaf in leaves}
    facilities = {
        (site_id, by_code[facility.facility_code_id]): facility.id
        for site_id in sites
        for facility in facilities_of(company_id, site_id)
    }
    return World(company_id, year_id, leaves, selections, sites, facilities)


def put(here: World, site_index: int, leaf_index: int, emission: str | None, **fields: object) -> InventoryEntryRow:
    leaf = here.leaves[leaf_index]
    site_id = here.sites[site_index]
    return InventoryEntryRow.for_company(here.company_id).create(
        selection_id=here.selections[leaf.id],
        site_facility_id=here.facilities[(site_id, leaf.id)],
        unit="kg",
        emission=None if emission is None else Decimal(emission),
        **fields,
    )


def filled(companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]) -> World:
    here = world(companies[0], leaves)
    put(here, 0, 0, "1.5")
    put(here, 0, 1, "2.25")
    put(here, 1, 0, "0.25")
    put(here, 0, 2, "0.5")
    return here


def board(here: World, year: int = YEAR) -> Dashboard:
    return actions.scope12_dashboard(here.company_id, year)


def listed(here: World, year: int = YEAR) -> dict[str, Decimal | None]:
    found = entry_actions.list_rows(here.company_id, year)
    assert isinstance(found, RowList), found
    return {scope.scope_name: scope.values[year] for scope in found.scopes}


def sums(found: Dashboard) -> dict[str, Decimal | None]:
    return {scope.scope_name: scope.value for scope in found.scopes}


def test_root_sums_equal_the_list_and_the_hand_calc(
    companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]
) -> None:
    here = filled(companies, leaves)
    found = board(here)
    assert found.configured and found.complete and found.decimals == 2
    assert sums(found) == listed(here) == {"범위 가": Decimal(4), "범위 나": Decimal("0.5")}
    assert found.scope12 == Decimal("4.5")
    assert [(s.site_name, s.values) for s in found.by_site] == [
        ("가 공장", ((found.scopes[0].scope_id, Decimal("3.75")), (found.scopes[1].scope_id, Decimal("0.5")))),
        ("나 공장", ((found.scopes[0].scope_id, Decimal("0.25")), (found.scopes[1].scope_id, None))),
    ]
    (top,) = found.scopes[0].top_sources
    assert (top.name, top.value, top.share) == ("유형 가", Decimal(4), Decimal("100.0"))


def test_off_sites_deleted_rows_hidden_or_deleted_selections_and_other_years_count_zero(
    companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]
) -> None:
    here = filled(companies, leaves)
    before = board(here)
    put(here, 0, 0, "100", deleted_at="2025-01-01T00:00:00Z")  # 지운 행
    old = world(here.company_id, leaves, year=YEAR - 1, sites=here.sites)  # 다른 해(같은 회사·사업장)
    put(old, 0, 0, "200")
    assert board(here).scopes == before.scopes and board(here).scope12 == Decimal("4.5")
    set_inventory(here.company_id, [here.sites[1]], enabled=False)  # 나 공장 끔 → 0.25 빠짐
    off = board(here)
    assert sums(off) == listed(here) == {"범위 가": Decimal("3.75"), "범위 나": Decimal("0.5")}
    assert [s.site_id for s in off.by_site] == [here.sites[0]]  # 켠 사업장 전부(꺼진 나 공장 빠짐)
    selections = CompanyIndexSelection.for_company(here.company_id)
    selections.filter(pk=here.selections[leaves[1].id]).update(hidden=True)  # 잎2 숨김 → 2.25 빠짐
    assert sums(board(here)) == listed(here) == {"범위 가": Decimal("1.5"), "범위 나": Decimal("0.5")}
    selections.filter(pk=here.selections[leaves[2].id]).update(deleted_at="2025-01-01T00:00:00Z")  # 잎3 지움
    found = board(here)
    assert sums(found) == listed(here) == {"범위 가": Decimal("1.5")}
    assert found.scope12 == Decimal("1.5")


def test_a_problem_row_makes_it_incomplete(companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]) -> None:
    here = filled(companies, leaves)
    put(here, 1, 2, None)  # 빈 행은 문제 아님
    assert board(here).complete
    put(here, 1, 1, None, emission_problem="factor_incomplete")
    found = board(here)
    assert not found.complete
    assert sums(found) == listed(here)  # 문제 행(값 None)은 합에 0


def test_a_problem_row_of_an_off_site_does_not_count(
    companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]
) -> None:
    here = filled(companies, leaves)
    put(here, 1, 1, None, emission_problem="factor_incomplete")
    set_inventory(here.company_id, [here.sites[1]], enabled=False)
    assert board(here).complete


def test_no_year_is_unconfigured(companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]) -> None:
    here = filled(companies, leaves)
    found = board(here, YEAR + 1)
    assert (found.configured, found.scopes, found.scope12, found.complete, found.decimals) == (False, (), None, True, 2)
    assert [(s.site_name, s.values) for s in found.by_site] == [("가 공장", ()), ("나 공장", ())]


def test_a_year_with_only_hidden_selections_is_unconfigured(
    companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]
) -> None:
    here = filled(companies, leaves)
    CompanyIndexSelection.for_company(here.company_id).update(hidden=True)
    assert not board(here).configured


def test_no_row_on_the_enabled_sites_gives_none(companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]) -> None:
    here = world(companies[0], leaves)
    found = board(here)
    assert found.configured and found.complete
    assert [(s.scope_name, s.value, s.top_sources) for s in found.scopes] == [
        ("범위 가", None, ()),
        ("범위 나", None, ()),
    ]
    assert found.scope12 is None
    assert [v for s in found.by_site for _, v in s.values] == [None, None, None, None]


def test_another_companys_rows_never_count(companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]) -> None:
    here = filled(companies, leaves)
    there = world(companies[1], leaves)
    put(there, 0, 0, "1000")
    found = board(here)
    assert found.scope12 == Decimal("4.5")
    assert {s.site_id for s in found.by_site} == set(here.sites)
    assert board(there).scope12 == Decimal(1000)


def slot_row(here: World, *values: tuple[str, str], row_id: int | None = None) -> RowInput:
    leaf = here.leaves[0]
    return RowInput(
        site_facility_id=here.facilities[(here.sites[0], leaf.id)],
        unit="kg",
        na=False,
        values=tuple(SlotInput(slot, amount, False) for slot, amount in values),
        row_id=row_id,
    )


def test_a_period_change_and_a_factor_change_follow_the_rows_emission(
    companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]
) -> None:
    """주기 바꿈 뒤 옛 칸은 셈 0(행 emission 이 새 주기) · 계수 바꿈 뒤 새 emission(지어낸 계수 1.5 → 3)."""
    here = world(companies[0], leaves)
    leaf, site_id = here.leaves[0], here.sites[0]
    saved = entry_actions.save_rows(
        here.company_id, YEAR, leaf.id, site_id, [slot_row(here, (f"{YEAR}-01", "1000"))], CUSTOMER
    )
    assert isinstance(saved, IndexDetail), saved
    assert sums(board(here))["범위 가"] == Decimal("1.5") == listed(here)["범위 가"]  # 1000 kg × 1.5 = 1.5 t
    moved = entry_actions.set_period(here.company_id, YEAR, leaf.id, site_id, "quarter", CUSTOMER)
    assert isinstance(moved, IndexDetail), moved
    assert sums(board(here))["범위 가"] is None and listed(here)["범위 가"] is None  # 월 칸은 셈에서 빠짐
    (block,) = [b for b in moved.sites if b.site_id == site_id]
    (line,) = block.rows
    again = entry_actions.save_rows(
        here.company_id, YEAR, leaf.id, site_id, [slot_row(here, (f"{YEAR}-Q1", "2000"), row_id=line.id)], CUSTOMER
    )
    assert isinstance(again, IndexDetail), again
    assert sums(board(here))["범위 가"] == Decimal(3) == listed(here)["범위 가"]
    other = factor(leaf.id, name="계수 나", gases=(GasDraft("CO2", enabled=True, factor="3", gwp="1"),))
    changed = entry_actions.set_row_factor(
        here.company_id, YEAR, leaf.id, line.id, factor_id=other.id, custom=None, reason="지어낸 사유", actor=OPERATOR
    )
    assert isinstance(changed, IndexDetail), changed
    assert sums(board(here))["범위 가"] == Decimal(6) == listed(here)["범위 가"]  # 2000 kg × 3 = 6 t


# ── S3K2a ②: Scope 3 칸(연도 상태와 같은 재료 — configured 와 따로) ──


def full(company_id: int, year: int = YEAR) -> actions.Board:
    return actions.board(company_id, year)


def test_scope3_only_counts_even_when_scope12_is_unconfigured(companies: tuple[int, int]) -> None:
    a = companies[0]
    plant(a, done_body(processed(4, "1.5"), processed(11, "2.5"), failed(5)))
    found = full(a)
    assert (found.scope12.configured, found.scope12.scope12) == (False, None)
    assert (found.scope3, found.total) == (Decimal(4), Decimal(4))
    assert [(r.category, r.value, r.share) for r in found.categories] == [
        ("C11", Decimal("2.5"), Decimal("62.5")),
        ("C4", Decimal("1.5"), Decimal("37.5")),
    ]  # C5(failed 만)는 값 없음이라 빠진다
    assert found.categories[0].name == "판매된 제품의 사용"


def test_the_sum_adds_scope12_and_scope3(companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]) -> None:
    here = filled(companies, leaves)  # Scope 1·2 합 4.5
    plant(here.company_id, done_body(processed(1, "0.5")))
    found = full(here.company_id)
    assert (found.scope12.scope12, found.scope3, found.total) == (Decimal("4.5"), Decimal("0.5"), Decimal(5))
    assert [r.share for r in found.categories] == [Decimal("100.0")]  # 분모는 Scope 3 합(1·2·3 합이 아님)


def test_scope12_only_and_nothing_at_all(companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]) -> None:
    here = filled(companies, leaves)
    found = full(here.company_id)
    assert (found.scope3, found.total, found.categories) == (None, Decimal("4.5"), ())
    empty = full(companies[1])
    assert (empty.scope12.scope12, empty.scope3, empty.total, empty.categories) == (None, None, None, ())


def test_the_top_five_drop_null_keep_zero_and_negative_and_tie_by_number(companies: tuple[int, int]) -> None:
    a = companies[0]
    plant(
        a,
        done_body(
            processed(1, "3"),
            processed(2, "3"),
            processed(3, "0"),
            processed(5, "-1"),
            processed(6, "7"),
            processed(7, "2"),
            processed(8, None),
            failed(9),
        ),
    )
    found = full(a)
    assert found.scope3 == Decimal(14)
    assert [(r.category, r.value) for r in found.categories] == [
        ("C6", Decimal(7)),
        ("C1", Decimal(3)),
        ("C2", Decimal(3)),
        ("C7", Decimal(2)),
        ("C3", Decimal(0)),
    ]  # 다섯까지 — C5(-1)는 여섯째, C8(수 0)·C9(failed 만)는 값 없음


def test_a_zero_scope3_total_has_null_shares(companies: tuple[int, int]) -> None:
    a = companies[0]
    plant(a, done_body(processed(1, "2"), processed(2, "-2")))
    found = full(a)
    assert found.scope3 == 0
    assert [r.share for r in found.categories] == [None, None]


def test_a_pinned_category_counts_its_pin(companies: tuple[int, int]) -> None:
    a = companies[0]
    first = plant(a, done_body(processed(4, "1"), processed(5, "2")))
    assert isinstance(scope3_actions.lock(a, YEAR, "C4", first, CUSTOMER), scope3_actions.CategoryState)
    plant(a, done_body(processed(4, "10"), processed(5, "20")))
    found = full(a)
    assert found.scope3 == Decimal(21)  # C4 핀 1 + C5 새 실행 20
    assert [(r.category, r.value) for r in found.categories] == [("C5", Decimal(20)), ("C4", Decimal(1))]


def test_the_scope12_part_is_the_same_object_shape_with_or_without_scope3(
    companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]
) -> None:
    here = filled(companies, leaves)
    before = board(here)
    plant(here.company_id, done_body(processed(4, "9")))
    assert full(here.company_id).scope12 == before == board(here)


def test_a_year_out_of_range_has_no_scope3(companies: tuple[int, int]) -> None:
    found = full(companies[0], 1989)
    assert (found.scope3, found.total, found.categories) == (None, None, ())


# ── DB1(599 e6): Scope 3 빠진 시트 수 — 연도 상태 failedSheets 와 같은 셈 ──


def test_no_scope3_result_has_zero_failed_sheets(companies: tuple[int, int]) -> None:
    a = companies[0]
    assert full(a).scope3_failed_sheets == 0
    plant(a, done_body(processed(4, "1"), processed(5, "2")))  # 실패 시트 없는 결과
    assert full(a).scope3_failed_sheets == 0
    assert full(a, 1989).scope3_failed_sheets == 0  # 해 범위 밖


def test_failed_sheets_add_up_over_categories_and_match_the_year_state(companies: tuple[int, int]) -> None:
    a = companies[0]
    plant(a, done_body(processed(4, "1.5"), failed(4), failed(5), failed(9), processed(11, "2")))
    found = full(a)
    assert found.scope3_failed_sheets == 3
    assert found.scope3 == Decimal("3.5")  # 실패 시트는 합에 들지 않는다
    state = scope3_actions.year_state(a, YEAR)
    assert isinstance(state, scope3_actions.YearState)
    assert found.scope3_failed_sheets == sum(
        line.current.value.failed_sheets for line in state.categories if line.current is not None
    )


def test_a_pinned_category_counts_the_failed_sheets_of_its_pin(companies: tuple[int, int]) -> None:
    a = companies[0]
    first = plant(a, done_body(processed(4, "1"), failed(4), failed(4), processed(5, "2")))
    assert isinstance(scope3_actions.lock(a, YEAR, "C4", first, CUSTOMER), scope3_actions.CategoryState)
    plant(a, done_body(processed(4, "10"), processed(5, "20"), failed(5)))
    found = full(a)
    assert found.scope3_failed_sheets == 3  # C4 핀의 2 + C5 새 실행의 1(C4 새 실행의 0 이 아님)
    state = scope3_actions.year_state(a, YEAR)
    assert isinstance(state, scope3_actions.YearState)
    assert found.scope3_failed_sheets == sum(
        line.current.value.failed_sheets for line in state.categories if line.current is not None
    )


def test_a_year_where_every_scope3_sheet_failed_has_no_total_but_counts_the_sheets(companies: tuple[int, int]) -> None:
    """검증 R1: 합은 없음(None — 화면은 「Scope 3 결과 없음」만)인데 빠진 시트 수는 연도 상태와 같이 센다."""
    a = companies[0]
    plant(a, done_body(failed(4), failed(5), failed(5)))
    found = full(a)
    assert (found.scope3, found.total, found.categories) == (None, None, ())
    assert found.scope3_failed_sheets == 3
    state = scope3_actions.year_state(a, YEAR)
    assert isinstance(state, scope3_actions.YearState)
    assert found.scope3_failed_sheets == sum(
        line.current.value.failed_sheets for line in state.categories if line.current is not None
    )
