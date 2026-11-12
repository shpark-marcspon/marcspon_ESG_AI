"""Scope 1·2 입력의 읽기(밴드 S12a ② — service/selectors/entries.py · index_selection.py 의 S12a 몫). 업무 층.

회사 조건(B 의 행은 A 의 읽기에 0) · 「데이터 있음」 = 삭제 안 된 입력 행(값 유무 무관 · 숨긴 선택 포함 — 판단 1) ·
잠금 읽기. 회사·풀 자료는 entries_support 로 짓는다(organization models import 0). 이름·값은 지어낸 것이다.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from esgapi.inventory.models import (
    CompanyIndexSelection,
    InventoryEntryHistory,
    InventoryEntryPeriod,
    InventoryEntryRow,
    InventoryEntryValue,
)
from esgapi.inventory.service.selectors import entries as selectors
from esgapi.inventory.service.selectors import ghg_pool as selectors_pool
from esgapi.inventory.service.selectors import index_selection as selections
from esgapi.inventory.tests.entries_support import Place, custom_factor, entry_row, place
from esgapi.inventory.tests.ghg_pool_support import activity, factor
from esgapi.inventory.tests.index_selection_support import YEAR, pool_leaf

pytestmark = pytest.mark.django_db


def two_places(companies: tuple[int, int]) -> tuple[Place, Place]:
    a, b = companies
    leaf = pool_leaf(activity(), "가 보일러")
    return place(a, leaf), place(b, leaf)


def value(where: Place, row_id: int, slot: str, amount: str | None, *, estimated: bool = False) -> None:
    InventoryEntryValue.for_company(where.company_id).create(
        row_id=row_id, slot=slot, amount=None if amount is None else Decimal(amount), estimated=estimated
    )


def test_rows_of_reads_only_this_company_and_alive_rows(companies: tuple[int, int]) -> None:
    here, there = two_places(companies)
    mine = entry_row(here)
    value(here, mine.pk, f"{YEAR}-01", "1.5")
    gone = entry_row(here, deleted_at=timezone.now())
    other = entry_row(there)
    value(there, other.pk, f"{YEAR}-01", "9")

    found = selectors.rows_of(here.company_id, here.selection_id)
    assert [row.id for row in found] == [mine.pk]  # 지운 행·남의 행 0
    assert found[0].site_id == here.site_id and found[0].site_facility_id == here.facility_id
    assert {slot: v.amount for slot, v in found[0].values.items()} == {f"{YEAR}-01": Decimal("1.5")}
    assert selectors.rows_of(here.company_id, there.selection_id) == []  # 남의 선택 id 로도 0
    assert gone.pk not in selectors.alive_row_ids(here.company_id, here.selection_id, [mine.pk, gone.pk, other.pk])
    assert selectors.alive_row_ids(here.company_id, here.selection_id, [mine.pk, gone.pk, other.pk]) == {mine.pk}


def test_lock_rows_reads_the_site_rows_inside_a_block(companies: tuple[int, int]) -> None:
    here, there = two_places(companies)
    mine = entry_row(here)
    entry_row(there)
    assert [row.id for row in selectors.lock_rows(here.company_id, here.selection_id, here.site_id)] == [mine.pk]
    assert selectors.lock_rows(here.company_id, here.selection_id, there.site_id) == []


def test_history_is_newest_first_and_paged(companies: tuple[int, int]) -> None:
    here, there = two_places(companies)
    row = entry_row(here)
    for after in ("1", "2", "3"):
        InventoryEntryHistory.for_company(here.company_id).create(
            row_id=row.pk, kind="value", slot=f"{YEAR}-01", after=after, unit="kg", actor_kind="service"
        )
    InventoryEntryHistory.for_company(there.company_id).create(
        row_id=entry_row(there).pk, kind="na_on", unit="kg", actor_kind="service"
    )
    count, first = selectors.history_of(here.company_id, row.pk, offset=0, limit=2)
    assert count == 3
    assert [line.after for line in first] == ["3", "2"]
    _, rest = selectors.history_of(here.company_id, row.pk, offset=2, limit=2)
    assert [line.after for line in rest] == ["1"]


def test_year_rows_skip_hidden_and_deleted(companies: tuple[int, int]) -> None:
    here, there = two_places(companies)
    entry_row(here, emission=Decimal("1.25"))
    entry_row(there, emission=Decimal("7"))
    lines = selectors.year_rows(here.company_id, [YEAR - 2, YEAR - 1, YEAR])
    assert [(line.year, line.node_id, line.site_id, line.emission) for line in lines] == [
        (YEAR, here.node_id, here.site_id, Decimal("1.25"))
    ]
    CompanyIndexSelection.for_company(here.company_id).filter(pk=here.selection_id).update(hidden=True)
    assert selectors.year_rows(here.company_id, [YEAR]) == []  # 숨긴 선택은 리스트·합에서 빠진다
    assert selectors.year_rows(here.company_id, [YEAR], node_id=here.node_id + 1000) == []


def test_estimated_lines_and_years(companies: tuple[int, int]) -> None:
    here, there = two_places(companies)
    row = entry_row(here)
    value(here, row.pk, f"{YEAR}-02", "3", estimated=True)
    value(there, entry_row(there).pk, f"{YEAR}-02", "3", estimated=True)
    assert selectors.estimated_lines(here.company_id, here.year_id) == [
        selectors.EstimatedLine(here.node_id, here.site_id, here.selection_id, f"{YEAR}-02")
    ]
    assert selectors.estimated_lines(here.company_id, there.year_id) == []
    assert selectors.years_of(here.company_id) == [(YEAR, True)]
    CompanyIndexSelection.for_company(here.company_id).filter(pk=here.selection_id).update(hidden=True)
    assert selectors.years_of(here.company_id) == [(YEAR, False)]
    assert selectors.decimals_of(here.company_id, here.year_id) == 2


def test_in_use_counts_alive_rows_even_of_hidden_selections(companies: tuple[int, int]) -> None:
    here, there = two_places(companies)
    assert selectors.sites_in_use(here.company_id, [here.site_id]) == frozenset()
    row = entry_row(here)  # 값 0 이어도 「데이터 있음」(판단 1)
    assert selectors.sites_in_use(here.company_id, [here.site_id, there.site_id]) == {here.site_id}
    assert selectors.facilities_in_use(here.company_id, [here.facility_id, there.facility_id]) == {here.facility_id}
    assert selectors.sites_in_use(there.company_id, [here.site_id]) == frozenset()  # 남의 회사 id 0
    CompanyIndexSelection.for_company(here.company_id).filter(pk=here.selection_id).update(hidden=True)
    assert selectors.sites_in_use(here.company_id, [here.site_id]) == {here.site_id}  # 숨겨도 셈
    row.deleted_at = timezone.now()
    row.save(update_fields=["deleted_at"])
    assert selectors.sites_in_use(here.company_id, [here.site_id]) == frozenset()
    assert selectors.facilities_in_use(here.company_id, [here.facility_id]) == frozenset()


def test_selections_with_data_are_leaves_with_alive_rows(companies: tuple[int, int]) -> None:
    here, there = two_places(companies)
    assert selections.selections_with_data(here.company_id, here.year_id, [here.node_id]) == frozenset()
    entry_row(there)
    assert selections.selections_with_data(here.company_id, here.year_id, [here.node_id]) == frozenset()
    row = entry_row(here)
    assert selections.selections_with_data(here.company_id, here.year_id, [here.node_id]) == {here.node_id}
    assert selections.selections_with_data(here.company_id, here.year_id, []) == frozenset()
    row.deleted_at = timezone.now()
    row.save(update_fields=["deleted_at"])
    assert selections.selections_with_data(here.company_id, here.year_id, [here.node_id]) == frozenset()


def test_selection_state_and_lock(companies: tuple[int, int]) -> None:
    here, there = two_places(companies)
    state = selections.selection_of(here.company_id, here.year_id, here.node_id)
    assert state is not None and (state.id, state.memo, state.locked_at) == (here.selection_id, "", None)
    assert selections.selection_of(here.company_id, there.year_id, here.node_id) is None  # 남의 해 id
    locked = selections.lock_selection(here.company_id, here.year_id, here.node_id)
    assert locked == state
    assert selections.selection_states(here.company_id, here.year_id) == {here.node_id: state}
    CompanyIndexSelection.for_company(here.company_id).filter(pk=here.selection_id).update(deleted_at=timezone.now())
    assert selections.lock_selection(here.company_id, here.year_id, here.node_id) is None


# ── S12a-2 ② ────────────────────────────────────────────────────────


def test_row_of_history_line_and_top_line_stay_in_the_company(companies: tuple[int, int]) -> None:
    here, there = two_places(companies)
    mine = entry_row(here)
    theirs = entry_row(there)
    history = InventoryEntryHistory.for_company(here.company_id)
    first = history.create(row_id=mine.pk, kind="value", slot=f"{YEAR}-01", after="1", unit="kg", actor_kind="service")
    second = history.create(row_id=mine.pk, kind="na_on", unit="kg", actor_kind="service", reason="가")
    found = selectors.row_of(here.company_id, here.selection_id, mine.pk)
    assert found is not None and (found.id, found.factor_version_id, found.custom_factor_id) == (mine.pk, None, None)
    assert selectors.row_of(here.company_id, here.selection_id, theirs.pk) is None
    assert selectors.row_of(there.company_id, there.selection_id, mine.pk) is None
    line = selectors.history_line(here.company_id, mine.pk, second.pk)
    assert line is not None and (line.kind, line.reason) == ("na_on", "가")
    assert selectors.history_line(there.company_id, mine.pk, first.pk) is None  # 남의 회사
    assert selectors.history_line(here.company_id, theirs.pk, first.pk) is None  # 남의 행
    assert selectors.top_line_id(here.company_id, mine.pk) == second.pk
    assert selectors.top_line_id(there.company_id, mine.pk) is None


def test_periods_and_custom_factors_stay_in_the_company(companies: tuple[int, int]) -> None:
    here, there = two_places(companies)
    InventoryEntryPeriod.for_company(here.company_id).create(
        selection_id=here.selection_id, site_id=here.site_id, period="year"
    )
    assert selectors.periods_of(here.company_id, [here.selection_id]) == {(here.selection_id, here.site_id): "year"}
    assert selectors.periods_of(there.company_id, [here.selection_id]) == {}
    made = custom_factor(here.company_id)
    found = selectors.custom_of(here.company_id, [made.pk])
    assert found[made.pk].name == "가 직접 계수" and found[made.pk].input_unit == ("volume", "kL")
    assert [(gas.gas, gas.factor) for gas in found[made.pk].gases if gas.enabled] == [("CO2", Decimal(2))]
    assert selectors.custom_of(there.company_id, [made.pk]) == {}


def test_a_pool_factor_used_by_a_row_is_in_use_and_current_version_reads_the_leaf(companies: tuple[int, int]) -> None:
    here, there = two_places(companies)
    other = factor(here.node_id, name="계수 나")
    version_id = selectors_pool.current_version_id(other.id, here.node_id)
    assert version_id is not None
    assert selectors_pool.current_version_id(other.id, here.node_id + 9999) is None  # 다른 잎
    assert selections.factors_in_use([other.id]) == frozenset()
    row = entry_row(there, factor_version_id=version_id)  # 어느 회사든
    assert selections.factors_in_use([other.id]) == {other.id}
    InventoryEntryRow.for_company(there.company_id).filter(pk=row.pk).update(deleted_at=timezone.now())
    assert selections.factors_in_use([other.id]) == frozenset()  # 지운 행은 안 셈
