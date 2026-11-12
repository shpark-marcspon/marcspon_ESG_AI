"""Scope 1·2 입력 표 다섯과 선택 행 칸 셋의 DB 제약(밴드 S12a ① — migrations/0003_entries · S12a-2 ① — 0004_entry_
periods_factors). 업무 층, 주인 역할 연결.

거절마다 됨의 짝을 둔다(제약이 너무 넓어 모든 행을 막는 것도 잡는다). 회사·풀 자료는 entries_support 로 짓는다
(organization models import 0). 이름·값은 지어낸 것이다(실제 계수 0).
앱 역할의 권한 집합은 tests/security/test_owner.py 가 앱 역할로 잰다 — 여기서는 카탈로그로 한 번 더 본다.
"""

from decimal import Decimal
from typing import Any

import psycopg
import pytest
from django.db import DataError, IntegrityError, connection, transaction
from django.utils import timezone

from esgapi.core.isolation.grants import APP_ROLE
from esgapi.core.isolation.managers import UnscopedQueryError
from esgapi.inventory.models import (
    CompanyIndexSelection,
    InventoryCustomFactor,
    InventoryEntryHistory,
    InventoryEntryPeriod,
    InventoryEntryRow,
    InventoryEntryValue,
)
from esgapi.inventory.tests.entries_support import Place, custom_factor, entry_row, place
from esgapi.inventory.tests.ghg_pool_support import activity
from esgapi.inventory.tests.index_selection_support import pool_leaf

pytestmark = pytest.mark.django_db


def refused(constraint: str, make: Any) -> None:
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        make()


def sqlstate_of(make: Any) -> str | None:
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        make()
    cause = caught.value.__cause__
    assert isinstance(cause, psycopg.Error)
    return cause.sqlstate


@pytest.fixture
def places(companies: tuple[int, int]) -> tuple[Place, Place]:
    """회사 A·B 에 같은 꼴의 입력 자리 하나씩(풀 잎은 공통 하나)."""
    a, b = companies
    leaf = pool_leaf(activity(), "가 보일러")
    return place(a, leaf), place(b, leaf, site_name="나 공장")


def value(row: InventoryEntryRow, slot: str = "2025-01", **fields: Any) -> InventoryEntryValue:
    return InventoryEntryValue.for_company(row.company_id).create(row_id=row.pk, slot=slot, **fields)


def history(row: InventoryEntryRow, **fields: Any) -> InventoryEntryHistory:
    values: dict[str, Any] = {"kind": "value", "slot": "2025-01", "unit": "kg", "actor_kind": "service"} | fields
    return InventoryEntryHistory.for_company(row.company_id).create(row_id=row.pk, **values)


# ── 선택 행 칸 셋(메모·잠금) ─────────────────────────────────────────


def test_a_selection_starts_with_an_empty_memo_and_no_lock(places: tuple[Place, Place]) -> None:
    a, _ = places
    row = CompanyIndexSelection.for_company(a.company_id).get(pk=a.selection_id)
    assert (row.memo, row.locked_at, row.locked_by_user_id) == ("", None, None)


def test_the_lock_time_and_the_locker_go_together(places: tuple[Place, Place]) -> None:
    a, _ = places
    selection = CompanyIndexSelection.for_company(a.company_id).filter(pk=a.selection_id)
    refused("inventory_selections_lock_pair", lambda: selection.update(locked_at=timezone.now()))
    refused("inventory_selections_lock_pair", lambda: selection.update(locked_by_user_id=7))
    assert selection.update(locked_at=timezone.now(), locked_by_user_id=7) == 1  # 짝: 둘이 같이면 된다
    assert selection.update(locked_at=None, locked_by_user_id=None) == 1  # 짝: 같이 풀면 된다


# ── inventory_entry_rows ─────────────────────────────────────────────


def test_a_facility_has_one_alive_row_per_selection(places: tuple[Place, Place]) -> None:
    a, _ = places
    first = entry_row(a)
    refused("inventory_entry_rows_unique_alive", lambda: entry_row(a))
    InventoryEntryRow.for_company(a.company_id).filter(pk=first.pk).update(deleted_at=timezone.now())
    entry_row(a)  # 짝: 지운 행 뒤에는 새 행
    assert InventoryEntryRow.for_company(a.company_id).count() == 2


@pytest.mark.parametrize("target", ["selection", "site_facility"])
def test_a_row_cannot_point_at_another_companys_selection_or_facility(places: tuple[Place, Place], target: str) -> None:
    a, b = places
    other = {"selection": {"selection_id": b.selection_id}, "site_facility": {"site_facility_id": b.facility_id}}

    def make() -> InventoryEntryRow:
        fields = {"selection_id": a.selection_id, "site_facility_id": a.facility_id} | other[target]
        return InventoryEntryRow.for_company(a.company_id).create(unit="kg", **fields)

    assert sqlstate_of(make) == "23503"  # inventory_entry_rows_<칸>_same_company_fk
    assert entry_row(a).company_id == a.company_id  # 짝: 제 회사의 선택·자산/시설
    assert InventoryEntryRow.unscoped.filter(company_id=a.company_id).count() == 1


def test_a_row_keeps_its_emission_digits(places: tuple[Place, Place]) -> None:
    a, _ = places
    row = entry_row(a, emission=Decimal("123456789012345678.123456789012"), emission_problem=None)
    row.refresh_from_db()
    assert row.emission == Decimal("123456789012345678.123456789012")  # Decimal(30,12) 그대로


# ── inventory_entry_values ───────────────────────────────────────────


def test_a_slot_is_written_once_per_row(places: tuple[Place, Place]) -> None:
    a, _ = places
    row = entry_row(a)
    value(row)
    refused("inventory_entry_values_unique", lambda: value(row))
    value(row, "2025-02")  # 짝: 다른 칸
    assert InventoryEntryValue.for_company(a.company_id).filter(row_id=row.pk).count() == 2


def test_an_amount_below_zero_is_refused(places: tuple[Place, Place]) -> None:
    a, _ = places
    row = entry_row(a)
    refused("inventory_entry_values_amount_nonneg", lambda: value(row, amount=Decimal("-0.000001")))
    assert value(row, amount=Decimal(0)).amount == 0  # 짝: 0 은 된다
    assert value(row, "2025-02", amount=None).amount is None  # 짝: 빈 칸


@pytest.mark.parametrize(
    "slot", ["2025-00", "2025-13", "2025-1", "25-01", "2025/01", "２０２５-01", "2025-Q0", "2025-Q5", "2025-q1", "202"]
)
def test_a_slot_out_of_form_is_refused(places: tuple[Place, Place], slot: str) -> None:
    a, _ = places
    row = entry_row(a)
    refused("inventory_entry_values_slot_format", lambda: value(row, slot))


@pytest.mark.parametrize("slot", ["2025-01", "2025-09", "2025-10", "2025-12", "2025-Q1", "2025-Q4", "2025"])
def test_a_slot_in_form_is_taken(places: tuple[Place, Place], slot: str) -> None:
    a, _ = places
    assert value(entry_row(a), slot).slot == slot


def test_a_value_cannot_point_at_another_companys_row(places: tuple[Place, Place]) -> None:
    a, b = places
    others = entry_row(b)
    code = sqlstate_of(lambda: InventoryEntryValue.for_company(a.company_id).create(row_id=others.pk, slot="2025-01"))
    assert code == "23503"  # inventory_entry_values_row_id_same_company_fk
    assert value(entry_row(a)).company_id == a.company_id  # 짝


# ── inventory_entry_history ──────────────────────────────────────────


@pytest.mark.parametrize("kind", ["value", "na_on", "na_off", "unit", "period"])
def test_a_history_kind_in_the_list_is_taken(places: tuple[Place, Place], kind: str) -> None:
    a, _ = places
    assert history(entry_row(a), kind=kind).kind == kind


def test_a_history_kind_out_of_the_list_is_refused(places: tuple[Place, Place]) -> None:
    a, _ = places
    row = entry_row(a)
    refused("inventory_entry_history_kind_check", lambda: history(row, kind="restore"))


def test_a_history_line_cannot_point_at_another_companys_row(places: tuple[Place, Place]) -> None:
    a, b = places
    others = entry_row(b)
    code = sqlstate_of(
        lambda: InventoryEntryHistory.for_company(a.company_id).create(
            row_id=others.pk, kind="value", unit="kg", actor_kind="service"
        )
    )
    assert code == "23503"  # inventory_entry_history_row_id_same_company_fk
    assert history(entry_row(a)).company_id == a.company_id  # 짝


def test_a_history_line_has_no_updated_at() -> None:
    assert "updated_at" not in {field.name for field in InventoryEntryHistory._meta.get_fields()}


# ── 매니저와 권한 ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "model",
    [InventoryEntryRow, InventoryEntryValue, InventoryEntryHistory, InventoryEntryPeriod, InventoryCustomFactor],
)
def test_the_default_manager_refuses_without_a_company(
    model: type[
        InventoryEntryRow | InventoryEntryValue | InventoryEntryHistory | InventoryEntryPeriod | InventoryCustomFactor
    ],
) -> None:
    with pytest.raises(UnscopedQueryError):
        model.objects.all()


def test_for_company_opens_only_that_company(places: tuple[Place, Place]) -> None:
    a, b = places
    value(entry_row(a))
    value(entry_row(b))
    assert InventoryEntryValue.unscoped.count() == 2  # 분모: B 의 행도 있다
    assert [row.company_id for row in InventoryEntryRow.for_company(a.company_id)] == [a.company_id]
    assert [row.company_id for row in InventoryEntryValue.for_company(a.company_id)] == [a.company_id]


@pytest.mark.parametrize(
    ("table", "expected"),
    [
        ("inventory_entry_rows", (True, True, True, False)),
        ("inventory_entry_values", (True, True, True, False)),
        ("inventory_entry_history", (True, True, False, False)),  # 고치지 않는 표: UPDATE 도 없다
        ("inventory_entry_periods", (True, True, True, False)),  # S12a-2: 주기는 고치고 지우지 않는다
        ("inventory_custom_factors", (True, True, False, False)),  # S12a-2: 직접입력은 고치지 않는 표(판 표 꼴)
    ],
)
def test_the_app_role_privileges(table: str, expected: tuple[bool, bool, bool, bool]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_table_privilege(%s, %s, 'SELECT'), has_table_privilege(%s, %s, 'INSERT'), "
            "has_table_privilege(%s, %s, 'UPDATE'), has_table_privilege(%s, %s, 'DELETE')",
            [APP_ROLE, table] * 4,
        )
        assert cursor.fetchone() == expected


# ── S12a-2: inventory_entry_periods ──────────────────────────────────


def period(where: Place, value: str = "quarter", **fields: Any) -> InventoryEntryPeriod:
    values: dict[str, Any] = {"selection_id": where.selection_id, "site_id": where.site_id, "period": value} | fields
    return InventoryEntryPeriod.for_company(where.company_id).create(**values)


@pytest.mark.parametrize("value", ["month", "quarter", "year"])
def test_a_period_in_the_list_is_taken(places: tuple[Place, Place], value: str) -> None:
    a, _ = places
    assert period(a, value).period == value


@pytest.mark.parametrize("value", ["week", "Month", "", "half"])
def test_a_period_out_of_the_list_is_refused(places: tuple[Place, Place], value: str) -> None:
    a, _ = places
    refused("inventory_entry_periods_period_check", lambda: period(a, value))


def test_a_block_has_one_period(places: tuple[Place, Place]) -> None:
    a, _ = places
    period(a)
    refused("inventory_entry_periods_unique", lambda: period(a, "year"))
    InventoryEntryPeriod.for_company(a.company_id).filter(selection_id=a.selection_id).update(period="year")  # 짝
    assert InventoryEntryPeriod.for_company(a.company_id).get().period == "year"


@pytest.mark.parametrize("target", ["selection", "site"])
def test_a_period_cannot_point_at_another_companys_selection_or_site(places: tuple[Place, Place], target: str) -> None:
    a, b = places
    other: dict[str, dict[str, Any]] = {"selection": {"selection_id": b.selection_id}, "site": {"site_id": b.site_id}}
    assert sqlstate_of(lambda: period(a, **other[target])) == "23503"  # inventory_entry_periods_<칸>_same_company_fk
    assert period(a).company_id == a.company_id  # 짝: 제 회사의 선택·사업장


# ── S12a-2: inventory_custom_factors ─────────────────────────────────


def test_a_custom_factor_keeps_its_gases_and_has_no_updated_at(places: tuple[Place, Place]) -> None:
    a, _ = places
    made = custom_factor(a.company_id, ncv_enabled=True, ncv=Decimal("2.5"), ncv_unit_kind="energy", ncv_unit="TJ")
    made.refresh_from_db()
    assert [gas["gas"] for gas in made.gases] == ["CO2", "CH4", "N2O", "HFCs", "PFCs", "SF6", "NF3"]
    assert made.gases[0] == {"gas": "CO2", "enabled": True, "factor": "2", "gwp": "1"}
    assert made.ncv == Decimal("2.5")
    assert "updated_at" not in {field.name for field in InventoryCustomFactor._meta.get_fields()}


@pytest.mark.parametrize(
    ("constraint", "fields"),
    [
        ("inventory_custom_factors_tier_check", {"tier": 4}),
        ("inventory_custom_factors_base_year_range", {"base_year": 1989}),
        ("inventory_custom_factors_base_year_range", {"base_year": 2101}),
        ("inventory_custom_factors_ncv_consistent", {"ncv_enabled": True}),
        ("inventory_custom_factors_ncv_consistent", {"ncv": Decimal(1), "ncv_unit_kind": "energy", "ncv_unit": "TJ"}),
        (
            "inventory_custom_factors_ncv_positive",
            {"ncv_enabled": True, "ncv": Decimal(0), "ncv_unit_kind": "energy", "ncv_unit": "TJ"},
        ),
    ],
)
def test_a_custom_factor_out_of_form_is_refused(
    places: tuple[Place, Place], constraint: str, fields: dict[str, Any]
) -> None:
    a, _ = places
    refused(constraint, lambda: custom_factor(a.company_id, **fields))
    assert custom_factor(a.company_id, tier=3, base_year=2100).tier == 3  # 짝: 범위 끝은 된다


# ── S12a-2: 행의 계수 덮어쓰기 ─────────────────────────────────────────


def test_a_row_takes_a_pool_version_or_a_custom_factor_but_not_both(places: tuple[Place, Place]) -> None:
    a, _ = places
    mine = custom_factor(a.company_id)
    row = entry_row(a)
    rows = InventoryEntryRow.for_company(a.company_id).filter(pk=row.pk)
    refused(
        "inventory_entry_rows_one_factor", lambda: rows.update(factor_version_id=a.version_id, custom_factor_id=mine.pk)
    )
    assert rows.update(factor_version_id=a.version_id) == 1  # 짝: 판 하나
    assert rows.update(factor_version_id=None, custom_factor_id=mine.pk) == 1  # 짝: 직접입력 하나
    assert rows.update(custom_factor_id=None) == 1  # 짝: 둘 다 없음 = 선택의 잡은 판


def test_a_row_cannot_point_at_another_companys_custom_factor(places: tuple[Place, Place]) -> None:
    a, b = places
    others = custom_factor(b.company_id)
    row = entry_row(a)
    rows = InventoryEntryRow.for_company(a.company_id).filter(pk=row.pk)
    assert sqlstate_of(lambda: rows.update(custom_factor_id=others.pk)) == "23503"  # …_custom_factor_id_same_company_fk
    assert rows.update(custom_factor_id=custom_factor(a.company_id).pk) == 1  # 짝


# ── S12a-2: 히스토리의 사유·계수 참조 ─────────────────────────────────


def test_a_factor_line_has_exactly_one_reference_before_and_after(places: tuple[Place, Place]) -> None:
    a, _ = places
    row = entry_row(a)
    mine = custom_factor(a.company_id)
    line = {"kind": "factor", "slot": None, "reason": "지어낸 사유"}
    made = history(row, **line, before_version_id=a.version_id, after_custom_id=mine.pk)  # 짝: 판 → 직접입력
    assert (made.reason, made.before_version_id, made.after_custom_id) == ("지어낸 사유", a.version_id, mine.pk)
    history(row, **line, before_custom_id=mine.pk, after_version_id=a.version_id)  # 짝: 직접입력 → 판
    for fields in (
        {},  # 앞뒤 없음
        {"before_version_id": a.version_id},  # 뒤 없음
        {"after_version_id": a.version_id},  # 앞 없음
        {"before_version_id": a.version_id, "before_custom_id": mine.pk, "after_version_id": a.version_id},  # 앞 둘
        {"before_version_id": a.version_id, "after_version_id": a.version_id, "after_custom_id": mine.pk},  # 뒤 둘
    ):
        refused("inventory_entry_history_factor_refs", lambda fields=fields: history(row, **line, **fields))


@pytest.mark.parametrize("kind", ["value", "na_on", "unit", "period"])
def test_only_a_factor_line_carries_references(places: tuple[Place, Place], kind: str) -> None:
    a, _ = places
    row = entry_row(a)
    refused("inventory_entry_history_factor_refs", lambda: history(row, kind=kind, before_version_id=a.version_id))
    refused(
        "inventory_entry_history_factor_refs",
        lambda: history(row, kind=kind, after_custom_id=custom_factor(a.company_id).pk),
    )
    assert history(row, kind=kind).before_version_id is None  # 짝: 참조 없는 줄


@pytest.mark.parametrize("column", ["before_custom_id", "after_custom_id"])
def test_a_factor_line_cannot_point_at_another_companys_custom_factor(places: tuple[Place, Place], column: str) -> None:
    a, b = places
    row = entry_row(a)
    others = custom_factor(b.company_id)
    other_side = "after_version_id" if column == "before_custom_id" else "before_version_id"
    fields = {"kind": "factor", "slot": None, column: others.pk, other_side: a.version_id}
    assert sqlstate_of(lambda: history(row, **fields)) == "23503"  # inventory_entry_history_<칸>_same_company_fk
    assert history(row, **(fields | {column: custom_factor(a.company_id).pk})).company_id == a.company_id  # 짝


def test_a_reason_is_kept_up_to_500_characters(places: tuple[Place, Place]) -> None:
    a, _ = places
    row = entry_row(a)
    assert len(history(row, kind="period", slot=None, reason="가" * 500).reason or "") == 500
    with pytest.raises(DataError, match="value too long"), transaction.atomic():
        history(row, kind="period", slot=None, reason="가" * 501)
