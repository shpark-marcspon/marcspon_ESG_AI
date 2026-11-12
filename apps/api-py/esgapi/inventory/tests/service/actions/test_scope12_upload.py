"""Scope 1·2 일괄 올리기의 몸(밴드 S12b-2 ② — service/actions/scope12_upload.py). 업무 층, 주인 역할 연결.

파일은 S12b-1 양식(`scope12_excel.template`)에 openpyxl 로 값을 넣어 짓는다. 이름·값은 지어낸 것이다.
손셈(ghg_pool_support.draft: 투입 kg · CO2 1.5 · GWP 1 · kg/kg): 1월 1000 kg → 1.5 tCO2-eq.

뒤쪽 경합 시험은 test_entries_race.py 꼴이다: 스레드 둘이 각자의 연결·트랜잭션에서 부르고, 사건(Event)으로 겹치는 자리를
만든다. ★ 무효 조건: 스레드 둘 + 연결 둘로 만든 경합이다(gunicorn 일꾼 둘의 요청이 아니다).
"""

import io
import threading
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection, connections, transaction
from django.test.utils import CaptureQueriesContext
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from esgapi.inventory.models import (
    CompanyIndexSelection,
    InventoryEntryHistory,
    InventoryEntryRow,
    InventoryEntryValue,
    InventoryYear,
)
from esgapi.inventory.service.actions import entries, scope12_excel
from esgapi.inventory.service.actions import scope12_upload as actions
from esgapi.inventory.service.selectors import entries as entry_selectors
from esgapi.inventory.service.selectors.entries import facilities_in_use
from esgapi.inventory.service.utils.entries import Actor, IndexDetail, Locked, RowInput, RowView, SlotInput
from esgapi.inventory.service.utils.ghg_pool import Invalid, NotFound
from esgapi.inventory.tests.entries_support import select_leaf
from esgapi.inventory.tests.ghg_pool_support import activity
from esgapi.inventory.tests.index_selection_support import YEAR, Leaf, pool_leaf, site
from esgapi.inventory.tools.scope12_upload import FORMULA, NOT_TEMPLATE, NOT_XLSX, SAME_LINE, UploadCell, UploadLine
from esgapi.organization.service.actions import branches as branch_actions
from esgapi.organization.service.services.branches import FacilityRow, InUse, save_facilities

pytestmark = pytest.mark.django_db

CUSTOMER = Actor("service", 11)
JAN, FEB = f"{YEAR}-01", f"{YEAR}-02"
GRACE = 2  # test_entries_race.py 와 같은 뜻: 먼저 간 쪽이 다른 쪽을 기다리는 초(잠금이 있으면 그대로 지나간다)

Fill = tuple[Leaf, str, str, str, object]  # 잎 · 사업장 이름 · 시트 · 칸 머리 · 값


class World:
    """회사 하나의 해 YEAR: 잎 A·B, 사업장 가(A·B)·나(A)."""

    def __init__(self, company_id: int, a: Leaf, b: Leaf) -> None:
        self.company_id = company_id
        self.year_id = InventoryYear.for_company(company_id).create(year=YEAR).pk
        self.a, self.b = a, b
        select_leaf(company_id, self.year_id, a)
        select_leaf(company_id, self.year_id, b)
        self.ga = site(company_id, a.code_id, b.code_id, name="가상 가")
        self.na = site(company_id, a.code_id, name="가상 나")

    def template(self) -> bytes:
        found = scope12_excel.template(self.company_id, YEAR, None, None)
        assert isinstance(found, scope12_excel.Download), found
        return found.content

    def block(self, leaf: Leaf, site_id: int) -> tuple[int, RowView | None]:
        """그 블록의 자산/시설 id 와 행."""
        detail = entries.index_detail(self.company_id, YEAR, leaf.id)
        assert isinstance(detail, IndexDetail), detail
        (block,) = [block for block in detail.sites if block.site_id == site_id]
        facility = block.facilities[0].id
        return facility, next((row for row in block.rows if row.site_facility_id == facility), None)

    def save(self, leaf: Leaf, site_id: int, *values: SlotInput, na: bool = False, unit: str = "kg") -> IndexDetail:
        facility, before = self.block(leaf, site_id)
        row = RowInput(facility, unit, na, values, before.id if before is not None else None)
        found = entries.save_rows(self.company_id, YEAR, leaf.id, site_id, [row], CUSTOMER)
        assert isinstance(found, IndexDetail), found
        return found

    def upload(self, data: bytes) -> object:
        return actions.upload(self.company_id, YEAR, data, CUSTOMER)

    def done(self, data: bytes) -> actions.UploadDone:
        found = self.upload(data)
        assert isinstance(found, actions.UploadDone), found
        return found

    def refused(self, data: bytes) -> dict[str, str]:
        found = self.upload(data)
        assert isinstance(found, Invalid), found
        return dict(found.fields)

    def amounts(self, leaf: Leaf, site_id: int) -> dict[str, Decimal | None]:
        _, row = self.block(leaf, site_id)
        return {} if row is None else {value.slot: value.amount for value in row.values}


def row_of(sheet: Worksheet, leaf: Leaf, site_name: str) -> int:
    """그 시트에서 (잎, 사업장) 줄(A 는 병합이라 위 값을 잇는다)."""
    node: object = None
    for row in range(2, sheet.max_row + 1):
        node = sheet.cell(row=row, column=1).value or node
        if node == leaf.id and sheet.cell(row=row, column=6).value == site_name:
            return row
    raise AssertionError((leaf.id, site_name))


def column_of(sheet: Worksheet, label: str) -> int:
    return next(column for column in range(1, sheet.max_column + 1) if sheet.cell(row=1, column=column).value == label)


def put(sheet: Worksheet, row: int, column: int, value: object) -> None:
    sheet.cell(row=row, column=column).value = value  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]


def filled(template: bytes, *fills: Fill) -> bytes:
    book = load_workbook(io.BytesIO(template))
    for leaf, site_name, sheet_name, label, value in fills:
        sheet = book[sheet_name]
        put(sheet, row_of(sheet, leaf, site_name), column_of(sheet, label), value)
    saved = io.BytesIO()
    book.save(saved)
    return saved.getvalue()


def address(template: bytes, leaf: Leaf, site_name: str, sheet_name: str, label: str | None = None) -> str:
    """오류 주소(`<시트>!<칸>`). label 이 없으면 줄의 A 칸."""
    sheet = load_workbook(io.BytesIO(template))[sheet_name]
    row = row_of(sheet, leaf, site_name)
    cell = sheet.cell(row=row, column=column_of(sheet, label) if label else 1)
    return f"{sheet_name}!{cell.coordinate}"


def state(company_id: int) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], int]:
    """(행, 값, 히스토리 수) — 0 씀을 재는 사진. 값·행의 updated_at 까지."""
    rows = InventoryEntryRow.for_company(company_id).order_by("id")
    values = InventoryEntryValue.for_company(company_id).order_by("id")
    return (
        list(rows.values_list("id", "unit", "na", "emission", "updated_at")),
        list(values.values_list("id", "slot", "amount", "estimated", "updated_at")),
        InventoryEntryHistory.for_company(company_id).count(),
    )


def history(company_id: int, kind: str) -> list[tuple[str | None, str | None, str | None]]:
    lines = InventoryEntryHistory.for_company(company_id).filter(kind=kind).order_by("id")
    return list(lines.values_list("slot", "before", "after"))


@pytest.fixture
def leaves() -> tuple[Leaf, Leaf]:
    parent = activity()
    return pool_leaf(parent, "가상 보일러"), pool_leaf(parent, "가상 버너")


@pytest.fixture
def world(companies: tuple[int, int], leaves: tuple[Leaf, Leaf]) -> World:
    return World(companies[0], *leaves)


# ── 채움 ──


def test_a_new_row_gets_value_emission_and_history(world: World) -> None:
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 1000))
    assert world.done(data) == actions.UploadDone(added=1, filled=1, unchanged=0, unresolved=0)
    _, row = world.block(world.a, world.ga)
    assert row is not None
    assert (row.unit, row.na, row.emission) == ("kg", False, Decimal("1.5"))
    assert world.amounts(world.a, world.ga)[JAN] == Decimal(1000)
    assert history(world.company_id, "value") == [(JAN, None, "1000")]


def test_empty_cells_of_an_existing_row_are_filled_and_the_rest_stays(world: World) -> None:
    world.save(world.a, world.ga, SlotInput(JAN, "1000"))
    data = filled(world.template(), (world.a, "가상 가", "월", "2월", 500))
    assert world.done(data) == actions.UploadDone(added=0, filled=1, unchanged=0, unresolved=0)
    amounts = world.amounts(world.a, world.ga)
    assert (amounts[JAN], amounts[FEB]) == (Decimal(1000), Decimal(500))


def test_every_period_sheet_writes_its_own_slot(world: World) -> None:
    entries.set_period(world.company_id, YEAR, world.a.id, world.na, "quarter", CUSTOMER)
    entries.set_period(world.company_id, YEAR, world.b.id, world.ga, "year", CUSTOMER)
    data = filled(
        world.template(),
        (world.a, "가상 나", "분기", "2분기", 3),
        (world.b, "가상 가", "년도", f"{YEAR}년", 4),
    )
    assert world.done(data).filled == 2
    assert world.amounts(world.a, world.na)[f"{YEAR}-Q2"] == Decimal(3)
    assert world.amounts(world.b, world.ga)[str(YEAR)] == Decimal(4)


def test_a_template_with_no_values_writes_nothing(world: World) -> None:
    before = state(world.company_id)
    assert world.done(world.template()) == actions.UploadDone(0, 0, 0, 0)
    assert state(world.company_id) == before


def test_the_same_file_twice_writes_nothing_the_second_time(world: World) -> None:
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 1000), (world.a, "가상 나", "월", "3월", 2))
    assert world.done(data) == actions.UploadDone(added=2, filled=2, unchanged=0, unresolved=0)
    before = state(world.company_id)
    assert world.done(data) == actions.UploadDone(added=0, filled=0, unchanged=2, unresolved=0)
    assert state(world.company_id) == before


def test_equal_values_compare_as_numbers(world: World) -> None:
    world.save(world.a, world.ga, SlotInput(JAN, "1.5"))
    before = state(world.company_id)
    assert world.done(filled(world.template(), (world.a, "가상 가", "월", "1월", "1.50"))).unchanged == 1
    assert state(world.company_id) == before


def test_another_value_in_a_filled_cell_is_refused_and_nothing_is_written(world: World) -> None:
    world.save(world.a, world.ga, SlotInput(JAN, "1000"))
    template = world.template()
    data = filled(template, (world.a, "가상 가", "월", "1월", 2000), (world.a, "가상 나", "월", "1월", 5))
    before = state(world.company_id)
    assert world.refused(data) == {address(template, world.a, "가상 가", "월", "1월"): actions.HAS_VALUE}
    assert state(world.company_id) == before  # 틀리지 않은 줄(나)도 0 씀


def test_estimated_flag_of_an_empty_cell_stays_and_new_cells_are_not_estimated(world: World) -> None:
    world.save(world.a, world.ga, SlotInput(JAN, None, estimated=True))
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 7), (world.a, "가상 가", "월", "2월", 8))
    assert world.done(data).filled == 2
    _, row = world.block(world.a, world.ga)
    assert row is not None
    assert {value.slot: value.estimated for value in row.values if value.amount is not None} == {JAN: True, FEB: False}


def test_rows_that_cannot_be_figured_are_counted(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_figure(*_: object) -> tuple[None, str]:
        return None, "가상_문제"

    monkeypatch.setattr(entries, "_figures", no_figure)
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 1), (world.a, "가상 나", "월", "1월", 1))
    assert world.done(data).unresolved == 2


# ── 줄 오류 ──


def test_a_block_with_two_facilities_is_refused(world: World) -> None:
    facility, _ = world.block(world.a, world.na)
    rows = [
        FacilityRow(facility_code_id=world.a.code_id, detail_name="0호기", id=facility),
        FacilityRow(facility_code_id=world.a.code_id, detail_name="1호기"),
    ]
    assert save_facilities(world.company_id, world.na, rows=rows, facilities_in_use=facilities_in_use) is None
    template = world.template()
    data = filled(template, (world.a, "가상 나", "월", "1월", 1))
    assert world.refused(data) == {address(template, world.a, "가상 나", "월"): actions.MANY_FACILITIES}


def test_a_site_without_a_facility_of_that_leaf_is_refused(world: World) -> None:
    """사업장 나에는 잎 B 코드의 자산/시설이 없다(블록도 없다) — 양식의 F 를 그 이름으로 고친 줄."""
    template = world.template()
    book = load_workbook(io.BytesIO(template))
    sheet = book["월"]
    row = row_of(sheet, world.b, "가상 가")
    put(sheet, row, 6, "가상 나")
    put(sheet, row, 9, 1)
    saved = io.BytesIO()
    book.save(saved)
    assert world.refused(saved.getvalue()) == {f"월!A{row}": actions.NO_FACILITY}


def test_a_value_on_another_period_sheet_is_refused(world: World) -> None:
    template = world.template()
    data = filled(template, (world.a, "가상 가", "분기", "1분기", 1))
    assert world.refused(data) == {address(template, world.a, "가상 가", "분기"): "이 사업장은 월 입력이에요"}


def test_a_past_year_cell_is_refused(world: World) -> None:
    entries.set_period(world.company_id, YEAR, world.a.id, world.ga, "year", CUSTOMER)
    template = world.template()
    data = filled(template, (world.a, "가상 가", "년도", f"{YEAR - 1}년", 1))
    assert world.refused(data) == {address(template, world.a, "가상 가", "년도", f"{YEAR - 1}년"): actions.PAST_YEAR}


def test_a_locked_leaf_is_refused(world: World) -> None:
    template = world.template()
    assert isinstance(entries.lock_index(world.company_id, YEAR, world.a.id, CUSTOMER), IndexDetail)
    data = filled(template, (world.a, "가상 가", "월", "1월", 1))
    assert world.refused(data) == {address(template, world.a, "가상 가", "월"): actions.LOCKED_LEAF}


def test_hidden_unselected_and_missing_leaves_get_the_same_words(world: World) -> None:
    template = world.template()
    data = filled(template, (world.b, "가상 가", "월", "1월", 1))
    at = address(template, world.b, "가상 가", "월")
    selection = CompanyIndexSelection.for_company(world.company_id).filter(facility_node_id=world.b.id)
    assert selection.update(hidden=True) == 1
    assert world.refused(data) == {at: actions.NO_LEAF}
    assert selection.update(hidden=False, deleted_at="2030-01-01T00:00:00Z") == 1
    assert world.refused(data) == {at: actions.NO_LEAF}
    book = load_workbook(io.BytesIO(data))
    put(book["월"], int(at.split("!A")[1]), 1, 2_000_000_000)
    saved = io.BytesIO()
    book.save(saved)
    assert world.refused(saved.getvalue()) == {at: actions.NO_LEAF}


def test_off_deleted_and_foreign_sites_get_the_same_words(world: World, companies: tuple[int, int]) -> None:
    site(companies[1], world.a.code_id, name="가상 남의 사업장")
    template = world.template()
    data = filled(template, (world.a, "가상 나", "월", "1월", 1))
    at = address(template, world.a, "가상 나", "월")
    assert branch_actions.set_branches_inventory(world.company_id, [world.na], enabled=False) == 1
    off = world.refused(data)
    assert off == {at: actions.NO_SITE}
    assert branch_actions.delete_branches(world.company_id, [world.na]) == 1
    assert world.refused(data) == off
    book = load_workbook(io.BytesIO(data))
    put(book["월"], int(at.split("!A")[1]), 6, "가상 남의 사업장")
    saved = io.BytesIO()
    book.save(saved)
    assert world.refused(saved.getvalue()) == off


def test_the_same_line_twice_through_the_body(world: World) -> None:
    template = world.template()
    book = load_workbook(io.BytesIO(template))
    sheet = book["월"]
    row = row_of(sheet, world.b, "가상 가")
    twin = sheet.max_row + 1
    put(sheet, twin, 1, world.b.id)
    put(sheet, twin, 6, "가상 가")
    put(sheet, twin, 8, "kg")
    put(sheet, row, 9, 1)
    put(sheet, twin, 9, 2)
    saved = io.BytesIO()
    book.save(saved)
    assert world.refused(saved.getvalue()) == {f"월!A{twin}": SAME_LINE}


def test_values_on_an_na_row_are_refused_without_turning_na_off(world: World) -> None:
    world.save(world.a, world.ga, na=True)
    template = world.template()
    before = state(world.company_id)
    data = filled(template, (world.a, "가상 가", "월", "1월", 1))
    assert world.refused(data) == {address(template, world.a, "가상 가", "월"): actions.NA_ROW}
    assert state(world.company_id) == before
    assert history(world.company_id, "na_off") == []


def test_an_existing_row_keeps_its_na_in_what_is_sent() -> None:
    """④ 가 N/A 행을 막으므로 몸으로는 재지 못한다 — 넘기는 값 자체를 잰다(`RowInput.na` 기본값이 na_off 를 쓴다)."""
    line = UploadLine("월", "month", 2, "월!A2", 1, "가상 가", "kg", (UploadCell("1월", "월!I2", "1"),))
    before = RowView(9, 3, "0호기", "kg", True, (), None, None)
    assert actions._row_input(line, 3, before, ()).na is True  # pyright: ignore[reportPrivateUsage]
    assert actions._row_input(line, 3, replace(before, na=False), ()).na is False  # pyright: ignore[reportPrivateUsage]
    assert actions._row_input(line, 3, None, ()).na is False  # pyright: ignore[reportPrivateUsage]


def test_a_row_saved_in_another_unit_is_refused_by_name(world: World) -> None:
    world.save(world.a, world.ga, SlotInput(JAN, "1"), unit="t")
    template = world.template()
    data = filled(template, (world.a, "가상 가", "월", "2월", 1))
    assert world.refused(data) == {address(template, world.a, "가상 가", "월"): "이 행은 t로 넣어요"}


def test_a_new_row_outside_the_unit_options_is_refused(world: World) -> None:
    template = world.template()
    book = load_workbook(io.BytesIO(template))
    sheet = book["월"]
    row = row_of(sheet, world.a, "가상 가")
    put(sheet, row, 8, "kWh")
    put(sheet, row, 9, 1)
    saved = io.BytesIO()
    book.save(saved)
    assert world.refused(saved.getvalue()) == {f"월!A{row}": actions.BAD_NEW_UNIT}


@pytest.mark.parametrize(
    ("value", "why"),
    [
        ("0.1234567", "소수점 아래는 6자리"),
        (-1, "0 이상의 숫자"),
        ("1,000", "0 이상의 숫자"),
        ("1e3", "0 이상의 숫자"),
        ("NaN", "0 이상의 숫자"),
        (True, "0 이상의 숫자"),
    ],
)
def test_amounts_the_screen_refuses_are_refused_by_cell(world: World, value: object, why: str) -> None:
    template = world.template()
    found = world.refused(filled(template, (world.a, "가상 가", "월", "1월", value)))
    assert list(found) == [address(template, world.a, "가상 가", "월", "1월")]
    assert why in next(iter(found.values()))
    assert str(value) not in next(iter(found.values()))  # 받은 칸 값은 글에 없다


def test_a_formula_cell_stops_the_upload(world: World) -> None:
    template = world.template()
    data = filled(template, (world.a, "가상 가", "월", "1월", "=1+1"), (world.a, "가상 가", "월", "2월", 3))
    before = state(world.company_id)
    assert world.refused(data) == {address(template, world.a, "가상 가", "월", "1월"): FORMULA}
    assert state(world.company_id) == before


def test_problems_are_cut_at_the_limit_and_the_rest_is_counted(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    assert actions.UPLOAD_ERRORS_MAX == 100
    months = [f"{month}월" for month in (1, 2, 3)]
    template = world.template()
    data = filled(template, *((world.a, "가상 가", "월", month, "가상") for month in months))
    monkeypatch.setattr(actions, "UPLOAD_ERRORS_MAX", 3)
    assert actions.MORE not in world.refused(data)
    monkeypatch.setattr(actions, "UPLOAD_ERRORS_MAX", 2)
    found = world.refused(data)
    assert list(found) == [
        address(template, world.a, "가상 가", "월", "1월"),
        address(template, world.a, "가상 가", "월", "2월"),
        actions.MORE,
    ]
    assert "1개" in found[actions.MORE]


def test_problems_come_in_sheet_and_cell_order_whoever_found_them(world: World) -> None:
    """수식 칸은 읽기가, 금액은 판정이 찾는다 — 앞 100개가 어느 것인지는 파일 차례로 정해진다."""
    template = world.template()
    data = filled(template, (world.a, "가상 가", "월", "1월", "가상"), (world.a, "가상 가", "월", "2월", "=1+1"))
    assert list(world.refused(data)) == [
        address(template, world.a, "가상 가", "월", "1월"),
        address(template, world.a, "가상 가", "월", "2월"),
    ]


# ── 파일 · 해 ──


def test_no_year_is_not_found_before_the_file_is_read(world: World) -> None:
    assert isinstance(actions.upload(world.company_id, YEAR + 1, b"", CUSTOMER), NotFound)


def test_a_year_with_no_visible_selection_is_not_found(world: World) -> None:
    data = world.template()
    assert CompanyIndexSelection.for_company(world.company_id).update(hidden=True) == 2
    assert isinstance(world.upload(data), NotFound)


def test_a_year_with_no_visible_selection_is_not_found_even_for_a_wrong_file(world: World) -> None:
    assert world.refused(b"not a workbook") == {actions.FILE: NOT_XLSX}  # 양성 대조: 선택이 있는 해에서는 422
    assert CompanyIndexSelection.for_company(world.company_id).update(hidden=True) == 2
    assert isinstance(world.upload(b""), NotFound)
    assert isinstance(world.upload(b"not a workbook"), NotFound)


def test_file_problems_are_refused_on_the_file_field(world: World) -> None:
    assert world.refused(b"") == {actions.FILE: NOT_XLSX}
    assert world.refused(b"{}") == {actions.FILE: NOT_XLSX}
    other = scope12_excel.template(world.company_id, YEAR, None, None)
    assert isinstance(other, scope12_excel.Download)
    assert actions.upload(world.company_id, YEAR, other.content, CUSTOMER) == actions.UploadDone(0, 0, 0, 0)
    next_year = InventoryYear.for_company(world.company_id).create(year=YEAR + 1).pk
    select_leaf(world.company_id, next_year, world.a)
    found = actions.upload(world.company_id, YEAR + 1, other.content, CUSTOMER)
    assert isinstance(found, Invalid) and found.fields == {actions.FILE: NOT_TEMPLATE}


def audit_rows() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM core_audit_events")
        row = cursor.fetchone()
    assert row is not None
    return int(row[0])


def detail_work(world: World) -> int:
    """World 의 상세 한 번: 사업장 둘 · 시설 셋(가 둘, 나 하나)."""
    return actions.DETAIL_WORK + actions.SITE_WORK * 2 + 3


def test_one_detail_costs_its_sites_and_every_facility_they_hold(world: World) -> None:
    sites = {"가상 가": world.ga, "가상 나": world.na}
    assert actions._detail_work(world.company_id, sites) == detail_work(world)  # pyright: ignore[reportPrivateUsage]
    only_na = {"가상 나": world.na}
    assert actions._detail_work(world.company_id, only_na) == (  # pyright: ignore[reportPrivateUsage]
        actions.DETAIL_WORK + actions.SITE_WORK + 1
    )


def test_the_work_limit_is_inclusive_and_counts_reads_and_writes(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """잎 하나를 읽고 블록 둘을 쓴다 — 상세 셋. 같은 값은 지나고 하나 적으면 파일 오류다."""
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 1), (world.a, "가상 나", "월", "1월", 2))
    before = (state(world.company_id), audit_rows())
    monkeypatch.setattr(actions, "UPLOAD_WORK_MAX", 3 * detail_work(world) - 1)
    assert world.refused(data) == {actions.FILE: actions.TOO_MUCH_WORK}
    assert (state(world.company_id), audit_rows()) == before
    monkeypatch.setattr(actions, "UPLOAD_WORK_MAX", 3 * detail_work(world))
    assert world.done(data).filled == 2


def test_a_file_over_the_limit_for_reading_reads_no_detail(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """잎 둘 = 상세 둘. 하나 적으면 상세를 한 번도 읽지 않고, 같으면 읽은 뒤 쓰기 몫에서 거절된다."""
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 1), (world.b, "가상 가", "월", "1월", 2))
    before = (state(world.company_id), audit_rows())
    real = entries.index_detail
    read: list[int] = []

    def counted(company_id: int, year: int, node_id: int) -> object:
        read.append(node_id)
        return real(company_id, year, node_id)

    monkeypatch.setattr(entries, "index_detail", counted)
    monkeypatch.setattr(actions, "UPLOAD_WORK_MAX", 2 * detail_work(world) - 1)
    assert world.refused(data) == {actions.FILE: actions.TOO_MUCH_WORK}
    assert read == []
    monkeypatch.setattr(actions, "UPLOAD_WORK_MAX", 2 * detail_work(world))
    assert world.refused(data) == {actions.FILE: actions.TOO_MUCH_WORK}
    assert sorted(read) == sorted([world.a.id, world.b.id])
    assert (state(world.company_id), audit_rows()) == before


def test_only_chosen_leaves_count_for_reading(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """고르지 않은 잎은 상세를 읽지 않으니 몫이 없다 — 파일 오류가 아니라 그 줄의 오류로 답한다."""
    template = world.template()
    data = filled(template, (world.a, "가상 가", "월", "1월", 1), (world.b, "가상 가", "월", "1월", 2))
    selection = CompanyIndexSelection.for_company(world.company_id).filter(facility_node_id=world.b.id)
    assert selection.update(hidden=True) == 1
    monkeypatch.setattr(actions, "UPLOAD_WORK_MAX", detail_work(world))
    assert world.refused(data) == {address(template, world.b, "가상 가", "월"): actions.NO_LEAF}


def test_lines_with_nothing_to_write_count_only_their_reading(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    world.save(world.a, world.ga, SlotInput(JAN, "1"))
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 1))
    monkeypatch.setattr(actions, "UPLOAD_WORK_MAX", detail_work(world))
    assert world.done(data).unchanged == 1  # 쓸 블록 0 — 같은 파일을 다시 올려도 쓰기 몫이 없다


def test_the_reading_limit_comes_before_line_errors(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """읽기 전 상한은 상세를 안 읽으므로 줄을 판정하지 못한다 — 틀린 줄이 있어도 파일 오류다."""
    world.save(world.a, world.ga, SlotInput(JAN, "1"))
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 2))
    monkeypatch.setattr(actions, "UPLOAD_WORK_MAX", detail_work(world) - 1)
    assert world.refused(data) == {actions.FILE: actions.TOO_MUCH_WORK}


def test_line_errors_come_before_the_writing_limit(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """읽은 뒤에는 줄 오류가 먼저다 — 고칠 칸을 먼저 알려 준다. 쓰기 몫은 넘는 파일이다(상세 둘 > 하나)."""
    world.save(world.a, world.ga, SlotInput(JAN, "1"))
    template = world.template()
    data = filled(template, (world.a, "가상 가", "월", "1월", 2), (world.a, "가상 나", "월", "1월", 3))
    monkeypatch.setattr(actions, "UPLOAD_WORK_MAX", detail_work(world))
    assert world.refused(data) == {address(template, world.a, "가상 가", "월", "1월"): actions.HAS_VALUE}


def test_a_company_with_many_sites_is_stopped_before_anything_is_written(companies: tuple[int, int]) -> None:
    """잎 하나 × 사업장 123: 줄 상한 300 안이고 읽기 몫도 작은데 (1 + 123) × (540 + 17 × 123 + 123) > 340,000 이다."""
    assert (actions.UPLOAD_WORK_MAX, actions.DETAIL_WORK, actions.SITE_WORK) == (340_000, 540, 17)
    company_id = companies[0]
    year_id = InventoryYear.for_company(company_id).create(year=YEAR).pk
    leaf = pool_leaf(activity(), "가상 시설")
    select_leaf(company_id, year_id, leaf)
    for index in range(123):
        site(company_id, leaf.code_id, name=f"가상 사업장 {index}")
    found = scope12_excel.template(company_id, YEAR, None, None)
    assert isinstance(found, scope12_excel.Download)
    book = load_workbook(io.BytesIO(found.content))
    sheet = book["월"]
    for row in range(2, sheet.max_row + 1):
        put(sheet, row, 9, 1)
    saved = io.BytesIO()
    book.save(saved)
    before = (state(company_id), audit_rows())
    assert actions.upload(company_id, YEAR, saved.getvalue(), CUSTOMER) == Invalid(
        {actions.FILE: actions.TOO_MUCH_WORK}
    )
    assert (state(company_id), audit_rows()) == before


def test_a_refused_save_rolls_every_block_back(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """⑤ 의 두 번째 블록이 거절돼도 첫 블록이 남지 않는다."""
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 1), (world.a, "가상 나", "월", "1월", 2))
    real = entries.save_rows
    calls = 0

    def second_refused(*args: Any) -> object:
        nonlocal calls
        calls += 1
        return real(*args) if calls == 1 else NotFound()

    monkeypatch.setattr(entries, "save_rows", second_refused)
    before = state(world.company_id)
    with transaction.atomic():  # 시험의 바깥 블록 안에서 upload 의 되돌림만 잰다
        assert world.refused(data) == {actions.FILE: actions.CHANGED}
    assert calls == 2
    assert state(world.company_id) == before


def test_saves_go_in_site_id_order_whatever_the_leaf_order(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """잎 A 는 사업장 나(뒤 id)에만, 잎 B 는 사업장 가(앞 id)에만 쓴다 — 잎 차례로 돌면 사업장 id 가 거꾸로다."""
    assert world.a.id < world.b.id and world.ga < world.na
    data = filled(world.template(), (world.a, "가상 나", "월", "1월", 1), (world.b, "가상 가", "월", "1월", 2))
    real = entries.save_rows
    order: list[int] = []

    def recorded(*args: Any) -> object:
        order.append(args[3])
        return real(*args)

    monkeypatch.setattr(entries, "save_rows", recorded)
    assert world.done(data).filled == 2
    assert order == [world.ga, world.na]


def test_query_count_of_thirty_leaves_three_sites_by_month(companies: tuple[int, int]) -> None:
    """C0-4 의 판(잎 30 × 사업장 3 × 월, 블록 90·칸 1,080). 쿼리 수가 늘면 빨강이다 — 값은 보고의 실측."""
    company_id = companies[0]
    year_id = InventoryYear.for_company(company_id).create(year=YEAR).pk
    parent = activity()
    leaves = [pool_leaf(parent, f"가상 시설 {index}") for index in range(30)]
    for leaf in leaves:
        select_leaf(company_id, year_id, leaf)
    for index in range(3):
        site(company_id, *[leaf.code_id for leaf in leaves], name=f"가상 사업장 {index}")
    found = scope12_excel.template(company_id, YEAR, None, None)
    assert isinstance(found, scope12_excel.Download)
    book = load_workbook(io.BytesIO(found.content))
    sheet = book["월"]
    for row in range(2, sheet.max_row + 1):
        for column in range(9, 21):
            put(sheet, row, column, 12.5)
    saved = io.BytesIO()
    book.save(saved)
    with CaptureQueriesContext(connection) as first:
        done = actions.upload(company_id, YEAR, saved.getvalue(), CUSTOMER)
    assert done == actions.UploadDone(added=90, filled=1080, unchanged=0, unresolved=0)
    with CaptureQueriesContext(connection) as second:
        again = actions.upload(company_id, YEAR, saved.getvalue(), CUSTOMER)
    assert again == actions.UploadDone(added=0, filled=0, unchanged=1080, unresolved=0)
    assert (len(first), len(second)) == (FIRST_QUERIES, SECOND_QUERIES)


FIRST_QUERIES = 6288  # 블록마다 저장 한 번(상세 다시 읽기 포함) — C0-4 의 값 + 일의 양을 재는 사업장 셋
SECOND_QUERIES = 558  # 쓰기 0: 읽기만


# ── 경합(스레드 둘 · 진짜 커밋) ──

race = pytest.mark.django_db(transaction=True)


def run(calls: dict[str, Callable[[], object]], done: dict[str, threading.Event] | None = None) -> dict[str, object]:
    """이름마다 스레드 하나 — 각자 연결·트랜잭션. 끝난 뒤 done[이름] 을 세운다(test_entries_race.py 의 run 꼴)."""
    results: dict[str, object] = {}
    guard = threading.Lock()

    def call(name: str) -> None:
        try:
            with transaction.atomic(durable=True):
                result: object = calls[name]()
        except BaseException as err:  # 스레드 밖으로 넘겨 단언한다(교착 OperationalError 포함)
            result = err
        finally:
            connections.close_all()
        with guard:
            results[name] = result
        if done is not None and name in done:
            done[name].set()

    threads = [threading.Thread(target=call, args=(name,)) for name in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]
    assert not [value for value in results.values() if isinstance(value, BaseException)], results
    return results


def hold_after_judging(monkeypatch: pytest.MonkeyPatch, judged: threading.Event, other: threading.Event) -> None:
    """올리기가 ④ 의 읽기(상세·사업장)를 마친 뒤 judged 를 세우고 other 를 GRACE 초 기다린다."""
    real = actions._details  # pyright: ignore[reportPrivateUsage]

    def wrapped(*args: Any) -> object:
        found = real(*args)
        judged.set()
        other.wait(timeout=GRACE)
        return found

    monkeypatch.setattr(actions, "_details", wrapped)


def hold_save_after_rows(monkeypatch: pytest.MonkeyPatch, saving: threading.Event, other: threading.Event) -> None:
    """화면 저장이 행 잠금을 쥔 뒤 saving 을 세우고 other 를 GRACE 초 기다린다(처음 한 번만 잡는다)."""
    real = entry_selectors.lock_rows
    armed = threading.Lock()

    def wrapped(company_id: int, selection_id: int, site_id: int) -> list[entry_selectors.RowState]:
        found = real(company_id, selection_id, site_id)
        if armed.acquire(blocking=False):
            saving.set()
            other.wait(timeout=GRACE)
        return found

    monkeypatch.setattr(entry_selectors, "lock_rows", wrapped)


@race
def test_a_screen_save_first_leaves_its_value_and_the_upload_writes_nothing(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """같은 빈 칸에 다른 값. 화면 저장이 해를 쥐었다 → 올리기는 lock_year 에 줄 섰다가 값을 보고 거절한다. 해 잠금이
    없으면 올리기가 커밋 전 빈 칸을 읽고 판정을 지나 화면 값을 덮어쓴다."""
    template = world.template()
    data = filled(template, (world.a, "가상 가", "월", "1월", 2))
    saving, finished = threading.Event(), threading.Event()
    hold_save_after_rows(monkeypatch, saving, finished)
    facility, _ = world.block(world.a, world.ga)

    def screen() -> object:
        row = RowInput(facility, "kg", False, (SlotInput(JAN, "1"),))
        return entries.save_rows(world.company_id, YEAR, world.a.id, world.ga, [row], CUSTOMER)

    def uploading() -> object:
        assert saving.wait(timeout=10)
        return world.upload(data)

    results = run({"screen": screen, "upload": uploading}, done={"upload": finished})
    assert isinstance(results["screen"], IndexDetail), results
    assert results["upload"] == Invalid({address(template, world.a, "가상 가", "월", "1월"): actions.HAS_VALUE})
    assert world.amounts(world.a, world.ga)[JAN] == Decimal(1)
    assert history(world.company_id, "value") == [(JAN, None, "1")]


@race
def test_an_upload_first_makes_the_screen_save_wait_behind_it(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """올리기가 해를 쥐고 판정했다 → 화면 저장은 그 뒤에 줄 서 히스토리가 이어진다(올리기 줄 → 화면 줄)."""
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 2))
    judged, saved = threading.Event(), threading.Event()
    hold_after_judging(monkeypatch, judged, saved)
    facility, _ = world.block(world.a, world.ga)

    def screen() -> object:
        assert judged.wait(timeout=10)
        _, before = world.block(world.a, world.ga)
        row = RowInput(facility, "kg", False, (SlotInput(JAN, "1"),), before.id if before is not None else None)
        return entries.save_rows(world.company_id, YEAR, world.a.id, world.ga, [row], CUSTOMER)

    results = run({"upload": lambda: world.upload(data), "screen": screen}, done={"screen": saved})
    assert results["upload"] == actions.UploadDone(added=1, filled=1, unchanged=0, unresolved=0)
    assert isinstance(results["screen"], Invalid), results  # 행 없다고 읽고 보낸 새 행 — 올리기가 세운 행과 겹침


@race
def test_a_lock_between_judging_and_writing_is_locked_and_writes_nothing(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 1), (world.a, "가상 나", "월", "1월", 1))
    judged, locked = threading.Event(), threading.Event()
    hold_after_judging(monkeypatch, judged, locked)

    def lock() -> object:
        assert judged.wait(timeout=10)
        return entries.lock_index(world.company_id, YEAR, world.a.id, CUSTOMER)

    results = run({"upload": lambda: world.upload(data), "lock": lock}, done={"lock": locked})
    assert isinstance(results["lock"], IndexDetail), results
    assert isinstance(results["upload"], Locked), results
    assert state(world.company_id) == ([], [], 0)


@race
def test_a_lock_before_the_upload_writes_nothing(world: World) -> None:
    template = world.template()
    data = filled(template, (world.a, "가상 가", "월", "1월", 1))
    locking = threading.Event()

    def lock() -> object:
        found = entries.lock_index(world.company_id, YEAR, world.a.id, CUSTOMER)
        locking.set()
        return found

    def uploading() -> object:
        assert locking.wait(timeout=10)
        return world.upload(data)

    results = run({"lock": lock, "upload": uploading})
    assert isinstance(results["lock"], IndexDetail), results
    assert isinstance(results["upload"], Invalid | Locked), results  # 잠그기의 커밋이 앞서면 줄 오류, 겹치면 409
    assert state(world.company_id) == ([], [], 0)


@race
def test_a_site_turned_off_between_judging_and_writing_is_a_file_problem(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = filled(world.template(), (world.a, "가상 가", "월", "1월", 1), (world.a, "가상 나", "월", "1월", 1))
    judged, off = threading.Event(), threading.Event()
    hold_after_judging(monkeypatch, judged, off)

    def turn_off() -> object:
        assert judged.wait(timeout=10)
        return branch_actions.set_branches_inventory(world.company_id, [world.na], enabled=False)

    results = run({"upload": lambda: world.upload(data), "off": turn_off}, done={"off": off})
    assert results["off"] == 1
    assert results["upload"] == Invalid({actions.FILE: actions.CHANGED})
    assert state(world.company_id) == ([], [], 0)


@race
def test_an_upload_and_a_site_delete_do_not_deadlock(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """잎 A 는 뒤 사업장, 잎 B 는 앞 사업장에 쓴다. 지움은 id 차례로 잠근다. 잎 차례로 돌면 올리기가 뒤 사업장을 쥔 채
    앞 사업장을 기다리고 지움이 앞 사업장을 쥔 채 뒤 사업장을 기다려 40P01 이다."""
    data = filled(world.template(), (world.a, "가상 나", "월", "1월", 1), (world.b, "가상 가", "월", "1월", 2))
    first, tried = threading.Event(), threading.Event()
    real = entries.save_rows
    calls = 0

    def after_first(*args: Any) -> object:
        nonlocal calls
        found = real(*args)
        calls += 1
        if calls == 1:
            first.set()
            tried.wait(timeout=GRACE)
        return found

    monkeypatch.setattr(entries, "save_rows", after_first)

    def delete() -> object:
        assert first.wait(timeout=10)
        return branch_actions.delete_branches(world.company_id, [world.ga, world.na])

    results = run({"upload": lambda: world.upload(data), "delete": delete}, done={"delete": tried})
    assert results["upload"] == actions.UploadDone(added=2, filled=2, unchanged=0, unresolved=0)
    assert results["delete"] == InUse(frozenset({world.ga, world.na}))
