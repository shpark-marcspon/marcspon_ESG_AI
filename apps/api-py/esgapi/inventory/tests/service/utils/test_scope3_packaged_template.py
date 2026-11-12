"""패키지 양식(data/scope3/scope3-template-v2.2.xlsx — 받은 양식 v2.2 에서 지은 사본, 밴드 S3V1 · MARC-ENT-641)의 꼴.

꼴·집합·같음만 단언한다. 회사 이름 칸은 「예시기업」 하나뿐이어야 한다(MARC-ENT-655 — 받은 양식의 실재 기업명은
이 저장소 어디에도 글자로 두지 않는다). 운송·출장 Spend 드롭다운은 패키지 책의 지출 시트에 있는 이름만(641).
"""

import io
import re
import zipfile
from functools import cache

from esgapi.inventory.engines.scope3.colab_157 import factor_book as fb
from esgapi.inventory.engines.scope3.colab_157.spend import lookup_transport_spend_ef, lookup_travel_spend_ef
from esgapi.inventory.flows.binding_157 import FileMissing
from esgapi.inventory.service.utils import scope3_files
from esgapi.inventory.tools.scope3_sheets.grid import (
    FormulaCell,
    Sheet,
    SheetRange,
    TextCell,
    Workbook,
    expand_range,
    parse_sheet_range,
)
from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook

EXAMPLE = "예시기업"
SHEET_COUNT = 26
DEFINED_NAMES = {
    "DD_APPLIED_COMPANY",
    "DD_ENERGY",
    "DD_ENERGY_UNIT",
    "DD_PURCHASE_GROUP",
    "DD_TRANSPORT_DISTANCE",
    "DD_TRANSPORT_SPEND",
    "DD_TRANSPORT_WEIGHT_UNIT",
    "DD_TRAVEL_DISTANCE",
    "DD_TRAVEL_SPEND",
    "DD_WASTE_C5_TYPE",
    "DD_WASTE_METHOD",
    "DD_WASTE_UNIT",
}
COMPANY_COLUMNS = (("기업정보", "C", 7, 7), ("기업정보", "E", 2, 50))
MAPPING_SHEETS = ("회사별_폐기물매핑", "회사별_교통수단매핑")
APPLIED = (("C5_사업장폐기물", "C14"), ("C6-1_출장거리", "C14"), ("C7_임직원통근", "C15"))
"""「*적용 기업명」 칸(=기업정보!$C$7) — 저장 값도 「예시기업」."""


def packaged(port: scope3_files.PackagedXlsx) -> bytes:
    content = port.read()
    assert not isinstance(content, FileMissing)
    return content


@cache
def template() -> Workbook:
    found = read_workbook(packaged(scope3_files.TEMPLATE))
    assert not isinstance(found, ReaderProblem)
    return found


@cache
def book() -> Workbook:
    found = read_workbook(packaged(scope3_files.FACTOR_BOOK))
    assert not isinstance(found, ReaderProblem)
    return found


def sheet(name: str) -> Sheet:
    return next(s for s in template().sheets if s.name == name)


def text(cell: object) -> str | None:
    if isinstance(cell, TextCell):
        return cell.text
    if isinstance(cell, FormulaCell) and isinstance(cell.cached, TextCell):
        return cell.cached.text
    return None


def dropdown(name: str) -> list[str]:
    refers = next(d.refers_to for d in template().defined_names if d.name == name)
    found = parse_sheet_range(refers)
    assert isinstance(found, SheetRange), refers
    cells = expand_range(found.cells)
    assert isinstance(cells, tuple)
    values = [text(sheet(found.sheet).cells.get(a)) for a in cells]
    assert all(v is not None for v in values), (name, values)  # 빈 칸 항목 없음
    return [v for v in values if v is not None]


def part(name: str) -> str:
    with zipfile.ZipFile(io.BytesIO(packaged(scope3_files.TEMPLATE))) as archive:
        return archive.read(name).decode()


def test_the_template_has_the_v22_sheets_and_names() -> None:
    assert len(template().sheets) == SHEET_COUNT
    assert template().sheets[0].name == "기업정보"
    assert [s.name for s in template().sheets[-2:]] == list(MAPPING_SHEETS)
    assert {d.name for d in template().defined_names} == DEFINED_NAMES


def test_the_person_cells_are_empty() -> None:
    assert re.findall(r"<cp:lastModifiedBy>([^<]*)</cp:lastModifiedBy>", part("docProps/core.xml")) == [""]
    assert re.findall(r'<x15ac:absPath url="([^"]*)"', part("xl/workbook.xml")) == [""]


def spend_names(sheet_name: str) -> set[str]:
    frame = fb.read_factor_sheet(book(), sheet_name).frame
    column = next(c for c in frame.columns if "한국어 품목명" in c)
    return {str(v).strip() for v in frame[column].dropna()}


def test_the_transport_spend_dropdown_is_the_book_names() -> None:
    """MARC-ENT-641: 운송 Spend 드롭다운 = 패키지 책 운송_Spend 의 이름(빠짐·남음 0, 빈 칸 항목 0).
    엔진이 줄마다 계수를 찾는다."""
    names = dropdown("DD_TRANSPORT_SPEND")
    assert len(names) == len(set(names))
    assert set(names) == spend_names("운송_Spend")
    db = fb.read_factor_sheet(book(), "운송_Spend").frame
    for name in names:
        hit = lookup_transport_spend_ef(db, 2025, name)
        assert hit is not None and hit.ef is not None, name


def test_the_travel_spend_dropdown_is_the_book_names() -> None:
    names = dropdown("DD_TRAVEL_SPEND")
    assert len(names) == len(set(names))
    assert set(names) == spend_names("출장_Spend")
    db = fb.read_factor_sheet(book(), "출장_Spend").frame
    for name in names:
        hit = lookup_travel_spend_ef(db, 2025, name)
        assert hit is not None and hit.ef is not None, name


def column_texts(sheet_name: str, column: str, first: int, last: int) -> set[str]:
    cells = sheet(sheet_name).cells
    values = (text(cells.get(f"{column}{row}")) for row in range(first, last + 1))
    return {v for v in values if v}


def test_the_company_cells_are_the_example_only() -> None:
    """MARC-ENT-655 (가): 회사 이름 칸(기업정보 C7·E 열, 회사별_* A·E 열, 적용 기업명 저장 값)은 「예시기업」 하나뿐.
    매핑 줄은 남았다(예시 줄이 INDEX 로 읽음)."""
    for sheet_name, column, first, last in COMPANY_COLUMNS:
        assert column_texts(sheet_name, column, first, last) == {EXAMPLE}, (sheet_name, column)
    for name in MAPPING_SHEETS:
        assert column_texts(name, "A", 2, 50) == {EXAMPLE}, name
        assert column_texts(name, "E", 2, 50) == {EXAMPLE}, name
        assert len([r for r in range(2, 51) if text(sheet(name).cells.get(f"A{r}"))]) > 1, name
    for name, address in APPLIED:
        cell = sheet(name).cells.get(address)
        assert isinstance(cell, FormulaCell) and cell.formula == "기업정보!$C$7", (name, address)
        assert text(cell) == EXAMPLE, (name, address)
