"""Scope 1·2 엑셀 내려받기 둘의 몸(밴드 S12b-1 ② — service/actions/scope12_excel.py). 업무 층, 주인 역할 연결.

풀은 ghg_pool_support 로(뿌리 이름 「Scope 1」·「Scope 2」 — 거름이 뿌리 이름 글자를 본다), 사업장은
index_selection_support.site 로, 값은 entries actions 로 넣는다(organization models import 0). 이름·값은 지어낸 것이다.

손셈(지어낸 계수 — ghg_pool_support.draft: 투입 kg · 순발열량 끔 · CO2 1.5 · GWP 1 · kg/kg):
  잎 A · 사업장 가(월): 1월 1000 · 2월 1000 · 4월 500 kg → 1분기 2000 kg = 3 t · 2분기 500 kg = 0.75 t · 행 3.75 t
  잎 A · 사업장 나(분기): 1분기 400 kg → 0.6 t
  잎 B · 사업장 가(연): 2025 100 kg · 직접입력 CO2 2 kg/kg → 0.2 t(행 계수가 선택 판 1.5 를 이김 — 판단 C)
"""

import io
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from esgapi.inventory.models import CompanyIndexSelection, GhgIndexNode, InventoryEntryRow, InventoryYear
from esgapi.inventory.service.actions import entries
from esgapi.inventory.service.actions import scope12_excel as actions
from esgapi.inventory.service.actions.dashboard import scope12_dashboard
from esgapi.inventory.service.utils.entries import Actor, IndexDetail, RowInput, SlotInput
from esgapi.inventory.service.utils.ghg_pool import DEFAULT_EMISSION_UNIT, GasDraft, Invalid, NotFound
from esgapi.inventory.tests.entries_support import select_leaf
from esgapi.inventory.tests.ghg_pool_support import draft, node
from esgapi.inventory.tests.index_selection_support import YEAR, Leaf, pool_leaf, site
from esgapi.inventory.tools import scope12_xlsx

pytestmark = pytest.mark.django_db

CUSTOMER = Actor("service", 11)
OPERATOR = Actor("admin", 12)
Q1, Q2 = 0, 1


class World:
    """회사 하나의 해 YEAR: 잎 A(Scope 1)·B(Scope 2)·C(숨김), 사업장 가(A·B)·나(A)·다(A, 꺼짐)."""

    def __init__(self, company_id: int, a: Leaf, b: Leaf, c: Leaf, *, prefix: str = "가상") -> None:
        self.company_id = company_id
        self.year_id = InventoryYear.for_company(company_id).create(year=YEAR).pk
        self.a, self.b = a, b
        for leaf in (a, b):
            select_leaf(company_id, self.year_id, leaf)
        select_leaf(company_id, self.year_id, c, hidden=True)
        self.ga = site(company_id, a.code_id, b.code_id, c.code_id, name=f"{prefix} 가")
        self.na = site(company_id, a.code_id, name=f"{prefix} 나")
        self.da = site(company_id, a.code_id, name=f"{prefix} 다", inventory=False)

    def save(self, leaf: Leaf, site_id: int, *values: tuple[str, str], na: bool = False) -> IndexDetail:
        detail = entries.index_detail(self.company_id, YEAR, leaf.id)
        assert isinstance(detail, IndexDetail), detail
        (block,) = [block for block in detail.sites if block.site_id == site_id]
        existing = {row.site_facility_id: row.id for row in block.rows}
        rows = [
            RowInput(
                site_facility_id=facility.id,
                unit="kg",
                na=na,
                values=tuple(SlotInput(slot, amount) for slot, amount in values),
                row_id=existing.get(facility.id),
            )
            for facility in block.facilities
        ]
        found = entries.save_rows(self.company_id, YEAR, leaf.id, site_id, rows, CUSTOMER)
        assert isinstance(found, IndexDetail), found
        return found

    def period(self, leaf: Leaf, site_id: int, period: str) -> None:
        found = entries.set_period(self.company_id, YEAR, leaf.id, site_id, period, CUSTOMER)
        assert isinstance(found, IndexDetail), found


@pytest.fixture
def leaves() -> tuple[Leaf, Leaf, Leaf]:
    one = node("activity", "가상 활동 1", node("source_type", "가상 유형 1", node("scope", "Scope 1")))
    two = node("activity", "가상 활동 2", node("source_type", "가상 유형 2", node("scope", "Scope 2")))
    return pool_leaf(one, "가상 보일러"), pool_leaf(two, "가상 수전"), pool_leaf(one, "가상 숨김 버너")


@pytest.fixture
def world(companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]) -> World:
    return World(companies[0], *leaves)


@pytest.fixture
def filled(world: World) -> World:
    """손셈의 값(머리 주석)을 넣은 world."""
    world.save(world.a, world.ga, (f"{YEAR}-01", "1000"), (f"{YEAR}-02", "1000"), (f"{YEAR}-04", "500"))
    world.period(world.a, world.na, "quarter")
    world.save(world.a, world.na, (f"{YEAR}-Q1", "400"))
    world.period(world.b, world.ga, "year")
    saved = world.save(world.b, world.ga, (f"{YEAR}", "100"))
    (row,) = saved.sites[0].rows
    custom = draft(name="가상 직접 계수", gases=(GasDraft("CO2", enabled=True, factor="2", gwp="1"),))
    changed = entries.set_row_factor(
        world.company_id, YEAR, world.b.id, row.id, factor_id=None, custom=custom, reason="가상 사유", actor=OPERATOR
    )
    assert isinstance(changed, IndexDetail), changed
    assert entries.set_memo(world.company_id, YEAR, world.a.id, "가상 메모") == "가상 메모"
    return world


def _book(found: object) -> list[Worksheet]:
    assert isinstance(found, actions.Download), found
    return list(load_workbook(io.BytesIO(found.content)).worksheets)


def _rows(sheet: Worksheet, first: int = 2) -> list[list[object]]:
    return [[cell.value for cell in row] for row in sheet.iter_rows(min_row=first)]


def _template(world: World, scope: str | None = None, site_id: int | None = None) -> object:
    return actions.template(world.company_id, YEAR, scope, site_id)


def _export(world: World, scope: str | None = None) -> object:
    return actions.export(world.company_id, YEAR, scope)


# ── 양식 ───────────────────────────────────────────────────────────


def test_template_lines_are_leaves_times_their_site_blocks(filled: World) -> None:
    sheets = _book(_template(filled))
    assert [sheet.title for sheet in sheets] == list(scope12_xlsx.TEMPLATE_SHEETS)
    for sheet in sheets:
        lines = [row[:8] for row in _rows(sheet)]
        assert lines == [
            [filled.a.id, "Scope 1", "가상 유형 1", "가상 활동 1", "가상 보일러", "가상 가", "월", "kg"],
            [None, None, None, None, None, "가상 나", "분기", "kg"],  # 같은 잎의 둘째 줄 — A~E 병합
            [filled.b.id, "Scope 2", "가상 유형 2", "가상 활동 2", "가상 수전", "가상 가", "년도", "kg"],
        ]  # 숨긴 잎 C·꺼진 사업장 다 0 · 잎 코드 자산/시설이 없는 사업장(나 × B) 0
        assert all(value is None for row in _rows(sheet) for value in row[8:])  # 값 칸 빔


def test_template_carries_a_locked_leaf(filled: World) -> None:
    assert isinstance(entries.lock_index(filled.company_id, YEAR, filled.b.id, CUSTOMER), IndexDetail)
    assert [row[0] for row in _rows(_book(_template(filled))[0])] == [filled.a.id, None, filled.b.id]


def test_template_filters_scope_and_site(filled: World) -> None:
    one = _rows(_book(_template(filled, "1"))[0])
    assert [(row[1], row[5]) for row in one] == [("Scope 1", "가상 가"), (None, "가상 나")]
    two = _rows(_book(_template(filled, "2"))[0])
    assert [(row[1], row[5]) for row in two] == [("Scope 2", "가상 가")]
    na = _rows(_book(_template(filled, None, filled.na))[0])
    assert [(row[1], row[5]) for row in na] == [("Scope 1", "가상 나")]


def test_template_file_names(filled: World) -> None:
    whole = _template(filled)
    part = _template(filled, "1", filled.na)
    assert isinstance(whole, actions.Download) and isinstance(part, actions.Download)
    assert whole.file_name.startswith(f"{YEAR}_") and whole.file_name.endswith(
        "_온실가스 인벤토리_데이터_일괄업로드_양식.xlsx"
    )
    assert part.file_name.endswith("_가상 나_온실가스 인벤토리_scope 1 데이터_일괄업로드_양식.xlsx")


def test_template_refusals(filled: World, companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]) -> None:
    other = World(companies[1], *leaves, prefix="남의")
    assert _template(filled, None, other.ga) == NotFound()  # 남의 회사 사업장
    assert _template(filled, None, filled.da) == NotFound()  # 꺼진 사업장
    assert _template(filled, "2", filled.na) == NotFound()  # 채울 줄 0
    assert actions.template(filled.company_id, YEAR + 1, None, None) == NotFound()  # 해 없음
    assert _template(filled, "3") == Invalid({"scope": actions.BAD_TEMPLATE_SCOPE})
    assert _template(filled, "all") == Invalid({"scope": actions.BAD_TEMPLATE_SCOPE})


def test_template_without_visible_selection_is_not_found(world: World) -> None:
    CompanyIndexSelection.for_company(world.company_id).update(hidden=True)
    assert _template(world) == NotFound()
    assert _export(world) == NotFound()


# ── 데이터 ─────────────────────────────────────────────────────────


def _totals(world: World, leaf: Leaf) -> dict[int, Decimal | None]:
    detail = entries.index_detail(world.company_id, YEAR, leaf.id)
    assert isinstance(detail, IndexDetail)
    return {line.site_id: line.values[YEAR] for line in detail.totals.by_site}


def test_export_summary_matches_the_detail_totals(filled: World) -> None:
    summary = _book(_export(filled))[0]
    assert summary.title == "온실가스 배출량"
    a, b = _totals(filled, filled.a), _totals(filled, filled.b)
    assert (a[filled.ga], a[filled.na], b[filled.ga]) == (Decimal("3.75"), Decimal("0.6"), Decimal("0.2"))
    assert _rows(summary) == [
        ["총계", DEFAULT_EMISSION_UNIT[1], 4.35, 0.2, 4.55],
        ["가상 가", DEFAULT_EMISSION_UNIT[1], 3.75, 0.2, 3.95],
        ["가상 나", DEFAULT_EMISSION_UNIT[1], 0.6, None, 0.6],
    ]  # 꺼진 사업장 다 0


def _float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def test_export_yearly_is_the_list(filled: World) -> None:
    yearly = _book(_export(filled))[1]
    listed = entries.list_rows(filled.company_id, YEAR)
    assert not isinstance(listed, Invalid)
    want = [
        [
            row.node_id,
            *row.path,
            "tCO2-eq",
            *[_float(row.values[y]) for y in listed.years],
        ]
        for group in listed.scopes
        for row in group.rows
    ]
    assert [line[:9] for line in _rows(yearly)] == want
    assert [line[9:] for line in _rows(yearly)] == [["가상 메모", None], [None, None]]


def test_export_detail_quarter_and_month(filled: World) -> None:
    sheets = _book(_export(filled))
    quarter, month, year = sheets[3], sheets[4], sheets[2]
    q = _rows(quarter, 3)
    layout = scope12_xlsx.detail_layout("quarter")
    first = layout.emission_first - 1
    # 잎 A 머리 줄 · 가(월 행 → 분기 칸 = 세 달 합) · 나(분기 행)
    assert q[1][5:7] == ["가상 가", "0호기"]
    assert q[1][first : first + 5] == [3, 0.75, None, None, 3.75]  # 손셈 · 총계 = 저장 셈
    assert q[1][layout.input_first - 1 : layout.input_first + 4] == [2000, 500, None, None, 2500]
    assert q[2][first : first + 5] == [0.6, None, None, None, 0.6]
    assert q[0][first : first + 5] == [3.6, 0.75, None, None, 4.35]  # 잎 머리 = 행 합
    m = _rows(month, 3)
    month_first = scope12_xlsx.detail_layout("month").emission_first - 1
    assert m[1][month_first : month_first + 4] == [1.5, 1.5, None, 0.75]
    assert m[2][month_first : month_first + 12] == [None] * 12  # 분기 행의 월 칸 빔
    b_row = m[4]  # 잎 B 머리(3) 다음 줄 — 연 행: 월 칸 빔 · 총계만
    assert b_row[month_first : month_first + 13] == [*([None] * 12), 0.2]
    y = _rows(year, 3)
    year_first = scope12_xlsx.detail_layout("year").emission_first - 1
    assert [row[year_first] for row in y] == [4.35, 3.75, 0.6, 0.2, 0.2]  # 년도 시트 Y 칸 = 저장 셈


def test_export_detail_factor_cells_follow_the_row_factor(filled: World) -> None:
    quarter = _rows(_book(_export(filled))[3], 3)
    layout = scope12_xlsx.detail_layout("quarter")
    a_row, b_row = quarter[1], quarter[4]
    assert a_row[layout.factor_first - 1 : layout.factor_first + 1] == [1.5, None]  # 선택 판(CO2 1.5)
    assert b_row[layout.factor_first - 1 : layout.factor_first + 1] == [2, None]  # 직접입력(CO2 2)이 이김
    assert b_row[layout.gwp_first - 1] == 1
    assert b_row[layout.tail - 1 :] == ["지어낸 출처", scope12_xlsx.FORMULA_PLAIN]


def test_export_detail_na_and_problem_rows(filled: World) -> None:
    filled.save(filled.a, filled.na, na=True)
    InventoryEntryRow.for_company(filled.company_id).filter(selection__facility_node_id=filled.b.id).update(
        emission=None, emission_problem="unit_conversion_missing"
    )
    quarter = _rows(_book(_export(filled))[3], 3)
    layout = scope12_xlsx.detail_layout("quarter")
    first = layout.emission_first - 1
    assert quarter[2][first : first + 5] == [None, None, None, None, "N/A"]
    assert quarter[4][first : first + 5] == [None, None, None, None, "unit_conversion_missing"]


def test_export_without_rows_is_heads_and_leaf_lines(world: World) -> None:
    sheets = _book(_export(world))
    assert [row[0] for row in _rows(sheets[3], 3)] == [world.a.id, world.b.id]
    assert _rows(sheets[0]) == [
        ["총계", "tCO2-eq", None, None, None],
        ["가상 가", "tCO2-eq", None, None, None],
        ["가상 나", "tCO2-eq", None, None, None],
    ]


def test_export_scope_filter(filled: World) -> None:
    one = _book(_export(filled, "1"))
    assert [cell.value for cell in one[0][1]] == ["사업장명", "단위", "Scope 1"]
    assert [row[1] for row in _rows(one[1])] == ["Scope 1"]
    two = _book(_export(filled, "2"))
    assert [row[1] for row in _rows(two[1])] == ["Scope 2"]
    assert isinstance(_export(filled, "all"), actions.Download)
    assert _export(filled, "3") == Invalid({"scope": actions.BAD_EXPORT_SCOPE})
    found = _export(filled, "2")
    assert isinstance(found, actions.Download)
    assert found.file_name.endswith("_온실가스 인벤토리_지역기반_scope 2 데이터.xlsx")


def test_export_refusals(filled: World) -> None:
    assert actions.export(filled.company_id, YEAR + 1, None) == NotFound()


def test_other_company_rows_and_names_stay_out(
    filled: World, companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]
) -> None:
    other = World(companies[1], *leaves, prefix="남의")
    other.save(other.a, other.ga, (f"{YEAR}-01", "9000"))
    for found in (_template(filled), _export(filled)):
        assert isinstance(found, actions.Download)
        text = repr([_rows(sheet, 1) for sheet in _book(found)])
        assert "남의" not in text and "9000" not in text


def test_same_state_same_bytes_and_no_writes(filled: World) -> None:
    first_template, first_export = _template(filled), _export(filled)
    with CaptureQueriesContext(connection) as queries:
        again_template, again_export = _template(filled), _export(filled)
    assert first_template == again_template and first_export == again_export
    assert len(queries.captured_queries) > 0  # 양성 대조: 질의를 잡았다(검증 R6)
    written = [q["sql"] for q in queries.captured_queries if not q["sql"].lstrip().upper().startswith("SELECT")]
    assert written == []


def test_export_total_is_the_stored_emission_not_the_cell_sum(filled: World) -> None:
    """총계 열 = RowView.emission(저장 셈) 그대로 — 칸 배출량의 합으로 다시 셈하지 않는다(발주서 2-2)."""
    detail = entries.index_detail(filled.company_id, YEAR, filled.a.id)
    assert isinstance(detail, IndexDetail)
    (row,) = next(block for block in detail.sites if block.site_id == filled.ga).rows
    InventoryEntryRow.for_company(filled.company_id).filter(pk=row.id).update(emission=Decimal("9.99"))
    quarter = _rows(_book(_export(filled))[3], 3)
    first = scope12_xlsx.detail_layout("quarter").emission_first - 1
    assert quarter[1][first : first + 5] == [3, 0.75, None, None, 9.99]


def test_emission_unit_text_is_the_pool_default() -> None:  # 검증 R4(②)
    assert DEFAULT_EMISSION_UNIT[1] == scope12_xlsx.EMISSION_UNIT


# ── Scope = 뿌리 노드(대시보드 S12a-3 와 같은 규칙 — 감독 02 D (나)) ─────────────


def test_export_summary_equals_the_dashboard(filled: World) -> None:
    """같은 재료에서 같은 값: 첫 시트 「총계」 줄의 뿌리 열·「Scope 1+2」 = 같은 해 대시보드의 뿌리 합·합계."""
    board = scope12_dashboard(filled.company_id, YEAR)
    summary = _book(_export(filled))[0]
    assert [cell.value for cell in summary[1]][2:] == [*(scope.scope_name for scope in board.scopes), "Scope 1+2"]
    total = _rows(summary)[0]
    assert board.scope12 is not None
    assert total[2:] == [*(_float(scope.value) for scope in board.scopes), float(board.scope12)]
    by_site = {line.site_name: [_float(value) for _, value in line.values] for line in board.by_site}
    for line in _rows(summary)[1:]:
        assert line[2:4] == by_site[str(line[0])]


def test_a_renamed_root_keeps_its_column_and_its_place(filled: World) -> None:
    GhgIndexNode.objects.filter(level="scope", name="Scope 2").update(name="가상 이름 바뀐 범위")
    summary = _book(_export(filled))[0]
    assert [cell.value for cell in summary[1]] == ["사업장명", "단위", "Scope 1", "가상 이름 바뀐 범위", "Scope 1+2"]
    assert _rows(summary)[0][2:] == [4.35, 0.2, 4.55]  # 이름이 바뀌어도 합에서 빠지지 않는다
    two = _book(_export(filled, "2"))
    assert [row[1] for row in _rows(two[1])] == ["가상 이름 바뀐 범위"]  # scope=2 = 트리 차례 둘째 뿌리
    assert [row[1] for row in _rows(_book(_template(filled, "2"))[0])] == ["가상 이름 바뀐 범위"]


def test_scope_n_is_the_nth_root_even_without_selected_leaves(filled: World) -> None:  # 검증 B1(③)
    CompanyIndexSelection.for_company(filled.company_id).filter(facility_node_id=filled.a.id).update(hidden=True)
    found = _export(filled, "1")  # Scope 1 잎이 다 숨음 — 그래도 scope=1 은 Scope 1(빈 시트), Scope 2 가 아니다
    assert isinstance(found, actions.Download)
    assert found.file_name.endswith("_온실가스 인벤토리_scope 1 데이터.xlsx")
    one = _book(found)
    assert [cell.value for cell in one[0][1]] == ["사업장명", "단위", "Scope 1"]
    assert _rows(one[0]) == [["총계", "tCO2-eq", None], ["가상 가", "tCO2-eq", None], ["가상 나", "tCO2-eq", None]]
    assert all(row[0] is None for row in _rows(one[1]))  # 연도별에 잎 줄 0
    assert [_rows(sheet, 3) for sheet in one[2:]] == [[], [], []]  # 상세 셋에 잎 줄 0
    assert "Scope 2" not in {cell for sheet in one for row in _rows(sheet, 1) for cell in row}
    two = _book(_export(filled, "2"))
    assert [cell.value for cell in two[0][1]] == ["사업장명", "단위", "Scope 2"]
    assert [row[1] for row in _rows(two[1])] == ["Scope 2"]
    assert _template(filled, "1") == NotFound()  # 양식은 채울 줄 0 — 지금 관례대로 NotFound
    assert {row[1] for row in _rows(_book(_template(filled, "2"))[0])} == {"Scope 2"}


def test_a_scope_beyond_the_roots_is_not_found(filled: World) -> None:
    GhgIndexNode.objects.filter(level="scope", name="Scope 2").update(deleted_at=timezone.now())
    assert _template(filled, "2") == NotFound()  # 지우지 않은 뿌리가 하나뿐
    assert _export(filled, "2") == NotFound()
    assert isinstance(_export(filled, "1"), actions.Download)
