"""Scope 1·2 입력의 쓰기(밴드 S12a ② — service/services/entries.py · index_selection.py 의 set_decimals). 업무 층.

제약 이름으로 가르는 갈래(발주서 2-8): 살아 있는 행 겹침만 RowTaken, 나머지는 다시 던진다(바깥 트랜잭션은 산다).
삭제 표시 · 메모 · 잠금 칸 둘 · 자릿수. 이름·값은 지어낸 것이다.
"""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from esgapi.inventory.models import (
    CompanyIndexSelection,
    InventoryCustomFactor,
    InventoryEntryPeriod,
    InventoryEntryRow,
    InventoryEntryValue,
    InventoryYear,
)
from esgapi.inventory.service.services import entries as services
from esgapi.inventory.service.services import index_selection as year_services
from esgapi.inventory.service.services.ghg_pool import constraint_name
from esgapi.inventory.service.utils.entries import Actor
from esgapi.inventory.service.utils.ghg_pool import GasDraft, check_factor
from esgapi.inventory.tests.entries_support import Place, entry_row, place
from esgapi.inventory.tests.ghg_pool_support import activity, draft
from esgapi.inventory.tests.index_selection_support import YEAR, pool_leaf

pytestmark = pytest.mark.django_db


@pytest.fixture
def here(companies: tuple[int, int]) -> Place:
    return place(companies[0], pool_leaf(activity(), "가 보일러"))


def test_a_second_alive_row_is_row_taken_and_the_outer_block_lives(here: Place) -> None:
    with transaction.atomic():
        made = services.insert_rows(
            here.company_id, here.selection_id, [services.NewRow(here.facility_id, "kg", False)]
        )
        assert isinstance(made, list) and len(made) == 1
        again = services.insert_rows(
            here.company_id, here.selection_id, [services.NewRow(here.facility_id, "kg", False)]
        )
        assert again == services.RowTaken()
        assert InventoryEntryRow.for_company(here.company_id).count() == 1  # 바깥 블록은 산다


def test_other_constraints_raise(here: Place) -> None:
    row = entry_row(here)
    first = services.ValueWrite(row.pk, f"{YEAR}-01", Decimal(1), False)
    services.upsert_values(here.company_id, [first])
    with pytest.raises(IntegrityError, match="inventory_entry_values_unique"), transaction.atomic():
        services.upsert_values(here.company_id, [first])  # 같은 칸 겹침은 lock_selection 이 막는다 — 다시 던짐
    bad = services.ValueWrite(row.pk, f"{YEAR}-13", Decimal(1), False)
    with pytest.raises(IntegrityError, match="inventory_entry_values_slot_format"), transaction.atomic():
        services.upsert_values(here.company_id, [bad])


def test_values_update_in_place(here: Place) -> None:
    row = entry_row(here)
    services.upsert_values(here.company_id, [services.ValueWrite(row.pk, f"{YEAR}-01", Decimal(1), False)])
    (made,) = InventoryEntryValue.for_company(here.company_id).all()
    services.upsert_values(
        here.company_id, [services.ValueWrite(row.pk, f"{YEAR}-01", Decimal("2.5"), True, value_id=made.pk)]
    )
    assert [(v.pk, v.amount, v.estimated) for v in InventoryEntryValue.for_company(here.company_id)] == [
        (made.pk, Decimal("2.5"), True)
    ]


def test_update_rows_and_mark_deleted_skip_deleted_rows(here: Place) -> None:
    row = entry_row(here)
    figures = services.RowFigures(row.pk, "t", True, Decimal("0.5"), None)
    assert services.update_rows(here.company_id, [figures]) == 1
    row.refresh_from_db()
    assert (row.unit, row.na, row.emission) == ("t", True, Decimal("0.5"))
    assert services.mark_rows_deleted(here.company_id, [row.pk]) == 1
    assert services.mark_rows_deleted(here.company_id, [row.pk]) == 0
    assert services.update_rows(here.company_id, [figures]) == 0
    assert services.mark_rows_deleted(here.company_id, []) == 0


def test_memo_and_lock_columns(here: Place) -> None:
    assert services.set_memo(here.company_id, here.selection_id, "지어낸 메모") == 1
    assert services.set_lock(here.company_id, here.selection_id, locked_by_user_id=7) == 1
    row = CompanyIndexSelection.for_company(here.company_id).get(pk=here.selection_id)
    assert (row.memo, row.locked_by_user_id, row.locked_at is not None) == ("지어낸 메모", 7, True)
    assert services.set_lock(here.company_id, here.selection_id, locked_by_user_id=None) == 1
    row.refresh_from_db()
    assert (row.locked_by_user_id, row.locked_at) == (None, None)


def test_writes_name_the_company(companies: tuple[int, int], here: Place) -> None:
    _, b = companies
    assert services.set_memo(b, here.selection_id, "남의 것") == 0
    assert services.set_lock(b, here.selection_id, locked_by_user_id=1) == 0
    assert services.mark_rows_deleted(b, [entry_row(here).pk]) == 0
    assert year_services.set_decimals(b, here.year_id, 3) == 0


def test_set_decimals_changes_only_the_year(here: Place) -> None:
    assert year_services.set_decimals(here.company_id, here.year_id, 3) == 1
    assert InventoryYear.for_company(here.company_id).get(pk=here.year_id).decimals == 3


# ── S12a-2 ② ────────────────────────────────────────────────────────


def test_upsert_period_updates_the_one_row_and_a_second_row_raises(here: Place) -> None:
    services.upsert_period(here.company_id, here.selection_id, here.site_id, "quarter")
    services.upsert_period(here.company_id, here.selection_id, here.site_id, "year")
    assert list(InventoryEntryPeriod.for_company(here.company_id).values_list("period", flat=True)) == ["year"]
    with pytest.raises(IntegrityError) as caught, transaction.atomic():  # 경합의 겹침은 다시 던진다(2-7)
        InventoryEntryPeriod.for_company(here.company_id).create(
            selection_id=here.selection_id, site_id=here.site_id, period="month"
        )
    assert constraint_name(caught.value) == "inventory_entry_periods_unique"


def test_insert_custom_and_set_row_factor(here: Place) -> None:
    checked = check_factor(draft(gases=(GasDraft("CO2", enabled=True, factor="2.50", gwp="1"),)))
    assert not isinstance(checked, dict)
    made = services.insert_custom(here.company_id, checked, Actor("admin", 12))
    custom = InventoryCustomFactor.for_company(here.company_id).get(pk=made)
    assert (custom.input_unit, custom.factor_unit, custom.ncv_enabled, custom.actor_kind) == (
        "kg",
        "kg/kg",
        False,
        "admin",
    )
    assert custom.gases[0] == {"gas": "CO2", "enabled": True, "factor": "2.5", "gwp": "1"}
    row = entry_row(here)
    assert services.set_row_factor(here.company_id, row.pk, version_id=None, custom_id=made) == 1
    assert InventoryEntryRow.for_company(here.company_id).get(pk=row.pk).custom_factor_id == made
    with pytest.raises(IntegrityError), transaction.atomic():  # 판과 직접입력 같이 0(CHECK — 판정이 먼저라 다시 던짐)
        services.set_row_factor(here.company_id, row.pk, version_id=here.version_id, custom_id=made)
