"""Scope 3 시트 테스트의 지은 표본. **값은 전부 지어낸 것이다.** 파일은 없다(테스트가 그때그때 코드로 짓는다).

- 꼴(시트 이름, 머리글 줄, 머리글의 글자, 정의된 이름)은 받은 두 파일의 것 그대로다
  (`factor_layout.py`·`dropdowns.py` 의 자료).
- 계수는 전부 `9.` 로 시작하는 지어낸 수, 항목 이름·표준코드·사전의 낱말은 전부 `가상` 으로 시작하는 지어낸 글자다
  (`test_s3sheets_samples.py` 가 표본 전체에서 지킨다). 단위 표기(kg, L, kWh …)만 진짜 표기를 쓴다.
- 행 수와 어긋남의 수는 발주서(밴드 S3a)의 대조표와 같게 지었다: 계수 행 403, 숫자 값 칸 591, `-` 8, 수식 칸 654,
  정의된 이름의 길이 17·14·5·7·27·33·14·16·4·2·2, K1~K15 의 수. 「원본에서 그 수가 나온다」는 여기서 재지지 않는다
  (그것은 게이트 밖의 원본 대조 `s3sheets_probe.py` 가 잰다).

두 가지로 짓는다: (A) `Workbook` 값(`sample_factor_book`·`sample_template`), (B) 그 값을 xlsx 바이트로(`to_xlsx`).
읽개 테스트는 손으로 적은 XML 조각도 쓴다(`xlsx_from_parts`·`sheet_xml`).
"""

import io
import random
import zipfile
from collections.abc import Mapping
from dataclasses import replace
from xml.sax.saxutils import escape, quoteattr

from esgapi.inventory.tools.scope3_sheets.dropdowns import (
    C12_HEADERS,
    C12_OFFSET_FORMULAS,
    C12_SHEET,
    DROPDOWN_SHEET,
    MAPPING_HEADERS,
    MAPPING_SHEET,
    MAPPING_SUMMARY_HEADERS,
    TRAVEL_CODE_HEADERS,
)
from esgapi.inventory.tools.scope3_sheets.factor_layout import FACTOR_SHEETS, INDEX_SHEET, FactorSheetShape
from esgapi.inventory.tools.scope3_sheets.grid import (
    Cell,
    CellAddress,
    DefinedName,
    FormulaCell,
    NumberCell,
    SharedFormula,
    Sheet,
    TextCell,
    Validation,
    Workbook,
    parse_address,
)

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
WORKSHEET_TYPE = f"{DOC_REL_NS}/worksheet"
XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

# 템플릿의 카테고리 시트 이름(꼴). 차례는 받은 파일의 것이다. C10 이 없다.
CATEGORY_SHEETS = (
    "C1_구매품서비스",
    "C2_자본재",
    "C3_연료에너지",
    "C4-1_운송거리",
    "C4-2_운송금액",
    "C5_사업장폐기물",
    "C6-1_출장거리",
    "C6-2_출장비",
    "C7_임직원통근",
    "C8-1_에너지사용량 아는 경우",
    "C8-2_면적",
    "C8-3_인원",
    "C9-1_운송거리",
    "C9-2_운송금액",
    "C11_판매제품사용",
    "C12_판매제품폐기",
    "C13-1_에너지사용량 아는경우",
    "C13-2_면적",
    "C13-3_인원",
    "C14_프랜차이즈",
    "C15_투자",
)

# 정의된 이름 → (드롭다운 시트의 열, 길이). 파일에 적힌 차례다.
NAMED_LISTS = {
    "DD_ENERGY": ("B", 14),
    "DD_ENERGY_UNIT": ("C", 5),
    "DD_PURCHASE_GROUP": ("A", 17),
    "DD_TRANSPORT_DISTANCE": ("D", 7),
    "DD_TRANSPORT_SPEND": ("E", 27),
    "DD_TRANSPORT_WEIGHT_UNIT": ("K", 2),
    "DD_TRAVEL_DISTANCE": ("F", 33),
    "DD_TRAVEL_SPEND": ("G", 14),
    "DD_WASTE_C5_TYPE": ("H", 16),
    "DD_WASTE_METHOD": ("I", 4),
    "DD_WASTE_UNIT": ("J", 2),
}
# 유효성이 가리키는 이름마다의 수(합 32). 받은 템플릿에서 센 것.
VALIDATION_NAME_COUNTS = {
    "DD_PURCHASE_GROUP": 2,
    "DD_ENERGY": 9,
    "DD_ENERGY_UNIT": 9,
    "DD_TRANSPORT_DISTANCE": 2,
    "DD_TRANSPORT_WEIGHT_UNIT": 2,
    "DD_TRANSPORT_SPEND": 2,
    "DD_WASTE_C5_TYPE": 1,
    "DD_WASTE_UNIT": 1,
    "DD_WASTE_METHOD": 1,
    "DD_TRAVEL_DISTANCE": 2,
    "DD_TRAVEL_SPEND": 1,
}
# 카테고리 시트마다의 유효성 수(C12 는 5, C15 는 2 — 따로 짓는다).
VALIDATIONS_PER_SHEET = (1, 1, 2, 2, 1, 3, 1, 1, 1, 2, 2, 2, 2, 1, 2, 0, 2, 2, 2, 2, 0)
# 매핑검토 사전의 묶음과 줄 수(합 120).
MAPPING_GROUPS = (
    ("purchase_group", 17),
    ("capital_group", 15),
    ("energy", 21),
    ("transport_distance", 8),
    ("transport_spend", 12),
    ("travel_distance", 16),
    ("travel_spend", 9),
    ("waste_c5", 6),
    ("unit", 16),
)

# ── 지어낸 이름들 ──────────────────────────────────────────────────────────
ENERGY = [f"가상에너지{i:02d}" for i in range(1, 15)]
ENERGY_UNITS = ["kWh", "Nm³", "kg", "L", "GJ"]
WEIGHT_UNITS = ["kg", "ton"]
PURCHASE = [f"가상품목군{i:02d}" for i in range(1, 18)]
BOOK_ONLY_PURCHASE = [f"가상책품목군{i:02d}" for i in range(1, 4)]
TRANSPORT_DISTANCE = [f"가상운송수단{i:02d}" for i in range(1, 8)]
TRANSPORT_SPEND = [f"가상운송항목{i:02d}" for i in range(1, 28)]
TRAVEL_DISTANCE = [f"가상교통수단{i:02d}" for i in range(1, 34)]
TRAVEL_CODES = [f"가상코드{i:02d}" for i in range(1, 34)]
TRAVEL_SPEND = [f"가상출장항목{i:02d}" for i in range(1, 15)]
WASTE_TYPES = [f"가상폐기물종류{i:02d}" for i in range(1, 17)]
WASTE_METHODS = [f"가상처리방법{i:02d}" for i in range(1, 5)]
C12_CODES = [f"가상소분류-{i:02d}" for i in range(1, 71)]
C12_NAMES = [f"가상폐기물명{i:02d}" for i in range(1, 71)]
# 에너지 14줄의 단위(책의 `에너지` D)와 에너지_C3 12줄의 단위.
# 앞 여섯 이름이 두 시트에 다 있고 그 가운데 둘의 단위가 다르다.
ENERGY_SHEET_UNITS = ["L", "L", "kg", "Nm³", "kWh", "kg", "kg", "kg", "Nm³", "L", "kg", "Nm³", "kWh", "TJ"]
ENERGY_C3_UNITS = ["kg", "kg", "kg", "Nm³", "kWh", "kg", "kWh", "Nm³", "kg", "GJ", "GJ", "kg"]


def text(value: str) -> TextCell:
    return TextCell(value)


def number(value: str) -> NumberCell:
    """파일 속 글자와 가장 짧은 표기가 같은 수만 짓는다(끝자리가 0 이 아닌 짧은 소수, 정수)."""
    return NumberCell(value, value)


def _factor(sheet: int, row: int, column: int) -> NumberCell:
    return number(f"9.{sheet}{row:03d}{column}")


def _shape(name: str) -> FactorSheetShape:
    return next(shape for shape in FACTOR_SHEETS if shape.name == name)


def _headed(shape: FactorSheetShape, titles: int) -> dict[str, Cell]:
    """제목 줄(A 열, 지어낸 글) · 묶음 머리글 · 머리글 줄."""
    cells: dict[str, Cell] = {f"A{row}": text(f"가상 제목 {shape.name} {row}") for row in range(1, titles + 1)}
    cells.update({address: text(header) for address, header in shape.group_headers})
    cells.update({f"{column.letter}{shape.header_row}": text(column.header) for column in shape.columns})
    return cells


def _labels(cells: dict[str, Cell], row: int, letters: str, tag: str) -> None:
    for letter in letters:
        cells[f"{letter}{row}"] = text(f"가상{tag}{letter}{row}")


def _shared(cells: dict[str, Cell], letters: str, first: int, last: int, block: int, sheet: int, prefix: str) -> None:
    """원화 열 셋의 공유 수식: 묶음(block 줄)마다 으뜸 칸 하나, 나머지는 식 글자 없는 딸린 칸."""
    index = 0
    for start in range(first, last + 1, block):
        end = min(start + block - 1, last)
        for position, letter in enumerate(letters, start=1):
            shared = SharedFormula(index, f"{letter}{start}", f"{letter}{start}:{letter}{end}")
            index += 1
            for row in range(start, end + 1):
                formula = f"{prefix}F{start}/9.{position}" if row == start else None
                cells[f"{letter}{row}"] = FormulaCell(formula, shared, _factor(sheet, row, position + 4))


def sample_factor_book() -> Workbook:
    sheets: list[Sheet] = []

    index: dict[str, Cell] = {"B2": text("가상 안내 1"), "B3": text("가상 안내 2")}
    index[f"{INDEX_SHEET.template_column}{INDEX_SHEET.header_row}"] = text(INDEX_SHEET.template_header)
    index[f"{INDEX_SHEET.book_column}{INDEX_SHEET.header_row}"] = text(INDEX_SHEET.book_header)
    book_tabs = [shape.name for shape in FACTOR_SHEETS]
    for offset, tab in enumerate(CATEGORY_SHEETS):
        index[f"B{6 + offset}"] = text(tab)
        index[f"C{6 + offset}"] = text(book_tabs[offset % len(book_tabs)])
    index["C26"] = text("가상 안내 (시트 이름이 아닌 글)")
    sheets.append(Sheet(INDEX_SHEET.name, index, (), ()))

    energy = _headed(_shape("에너지"), 2)
    energy_names = [*ENERGY[:13], "가상에너지책01"]
    for offset in range(14):
        row = 5 + offset
        _labels(energy, row, "AB", "구분")
        energy[f"C{row}"] = text(energy_names[offset])
        energy[f"D{row}"] = text(ENERGY_SHEET_UNITS[offset])
        for position, letter in enumerate("EFGHI", start=1):
            dash = offset >= 12 and letter != "I"
            energy[f"{letter}{row}"] = text("-") if dash else _factor(1, row, position)
    energy["J17"] = text("가상 머리글 없는 열의 글")
    energy["A19"] = text("가상 출처 각주")
    sheets.append(Sheet("에너지", energy, ("A19:I19", "A1:I1"), ()))

    energy_c3 = _headed(_shape("에너지_C3"), 2)
    c3_names = [*ENERGY[:6], *(f"가상에너지C3_{i:02d}" for i in range(1, 7))]
    for offset in range(12):
        row = 4 + offset
        energy_c3[f"A{row}"] = number(f"9{offset + 1:02d}")  # 수로 든 이름표(No.)
        energy_c3[f"B{row}"] = text(c3_names[offset])
        energy_c3[f"C{row}"] = text(ENERGY_C3_UNITS[offset])
        energy_c3[f"D{row}"] = _factor(2, row, 1)
        energy_c3[f"E{row}"] = text(f"가상 출처 {row}")
    sheets.append(Sheet("에너지_C3", energy_c3, ("A1:L1",), ()))

    transport = _headed(_shape("운송"), 1)
    for offset in range(6):
        row = 3 + offset
        _labels(transport, row, "ABD", "운송")
        transport[f"C{row}"] = text(TRANSPORT_DISTANCE[offset])
        transport[f"E{row}"] = _factor(3, row, 1)
        if offset in (0, 1, 3):
            transport[f"F{row}"] = text(f"가상 비고 {row}")
    sheets.append(Sheet("운송", transport, ("A1:F1",), ()))

    travel = _headed(_shape("출장_통근"), 1)
    for offset in range(11):
        row = 3 + offset
        _labels(travel, row, "ABCEG", "출장")
        travel[f"D{row}"] = text(TRAVEL_CODES[offset])
        travel[f"F{row}"] = _factor(4, row, 1)
    sheets.append(Sheet("출장_통근", travel, ("A1:G1",), ()))

    waste = _headed(_shape("폐기물_C5"), 1)
    pairs = [(kind, method) for kind in WASTE_TYPES[:15] for method in WASTE_METHODS]
    pairs.insert(7, pairs[6])  # 10·11행이 같은 짝
    pairs.insert(28, pairs[27])  # 31·32행이 같은 짝
    for offset, (kind, method) in enumerate(pairs):
        row = 4 + offset
        waste[f"A{row}"] = text(kind)
        waste[f"B{row}"] = text(method)
        _labels(waste, row, "DE" if row == 65 else "CDE", "폐기물")
        waste[f"F{row}"] = _factor(5, row, 1)
    for offset, method in enumerate(WASTE_METHODS[:3]):  # 빈 줄(66) 뒤의 줄 셋. 열여섯째 종류는 여기에만 있다
        row = 67 + offset
        waste[f"A{row}"] = text(WASTE_TYPES[15])
        waste[f"B{row}"] = text(method)
        _labels(waste, row, "CDE", "폐기물")
        waste[f"F{row}"] = _factor(5, row, 1)
    sheets.append(Sheet("폐기물_C5", waste, ("A1:G1",), ()))

    waste12 = _headed(_shape("폐기물_C12"), 1)
    for offset in range(70):
        row = 3 + offset
        _labels(waste12, row, "ABE", "분류")
        waste12[f"C{row}"] = text(C12_CODES[offset])
        waste12[f"D{row}"] = text(C12_NAMES[offset])
        for position, letter in enumerate("FGH", start=1):
            waste12[f"{letter}{row}"] = _factor(6, row, position)
    for offset, letter in enumerate("FGH"):  # 빈 줄(73) 뒤의 줄 셋. B·C 가 비고 값 열 하나만 찼다
        row = 74 + offset
        _labels(waste12, row, "ADE", "평균")
        waste12[f"{letter}{row}"] = _factor(6, row, offset + 1)
    sheets.append(Sheet("폐기물_C12", waste12, ("A1:H1",), ()))

    purchase = _headed(_shape("구매_USEPA"), 1)
    groups = [*PURCHASE[:14], *BOOK_ONLY_PURCHASE]
    numeric_code_rows = {14, *range(78, 88)}  # 코드가 수로 든 줄 11
    for offset in range(190):
        row = 4 + offset
        purchase[f"A{row}"] = text(groups[offset % 17])
        _labels(purchase, row, "BCEH", "구매")
        purchase[f"D{row}"] = number(f"9{row:05d}") if row in numeric_code_rows else text(f"가상산업코드{row}")
        purchase[f"F{row}"] = _factor(7, row, 1)
        purchase[f"G{row}"] = text("kgCO2eq/USD")
    _shared(purchase, "IJK", 4, 193, 32, 7, "")
    sheets.append(Sheet("구매_USEPA", purchase, ("A1:H1",), ()))

    for sheet_number, (name, items, count) in enumerate(
        (("운송_Spend", TRANSPORT_SPEND, 17), ("출장_Spend", TRAVEL_SPEND, 11)), start=8
    ):
        spend = _headed(_shape(name), 2)
        for offset in range(count):
            row = 4 + offset
            _labels(spend, row, "ABCE", "지출")
            spend[f"D{row}"] = text(items[offset])
            spend[f"F{row}"] = _factor(sheet_number, row, 1)
            if offset % 4 == 0:
                spend[f"G{row}"] = text(f"가상 비고 {row}")
        _shared(spend, "HIJ", 4, 3 + count, count, sheet_number, "$")
        sheets.append(Sheet(name, spend, ("A2:G2", "A1:G1"), ()))

    power = _headed(_shape("전력_국가별"), 1)
    for offset in range(4):
        row = 3 + offset
        _labels(power, row, "ABFGIJKL", "전력")
        power[f"C{row}"] = number("9.90031") if offset == 0 else _factor(9, row, 1)
        power[f"D{row}"] = text("kgCO2eq/kWh")
        power[f"E{row}"] = text("가상 연도") if offset == 0 else number(f"9{row:03d}")
    power["H4"] = text("가상 발표일")
    sheets.append(Sheet("전력_국가별", power, (), ()))
    return Workbook(tuple(sheets), ())


def _dropdown_columns() -> dict[str, list[str]]:
    return {
        "A": PURCHASE,
        "B": ENERGY,
        "C": ENERGY_UNITS,
        "D": TRANSPORT_DISTANCE,
        "E": TRANSPORT_SPEND,
        "F": TRAVEL_DISTANCE,
        "G": TRAVEL_SPEND,
        "H": WASTE_TYPES,
        "I": WASTE_METHODS,
        "J": WEIGHT_UNITS,
        "K": WEIGHT_UNITS,
    }


def _mapping_new_values(group: str, count: int) -> list[str]:
    """그 묶음의 「DB 기준값」. 드롭다운에 없는 것: transport_spend 9줄, energy 1줄. unit 은 목록마다 3·12·12."""
    if group == "unit":
        return [*(["kWh", "Nm³", "L", "GJ"] * 3)[:11], "kg", "kg", "ton", "ton", "g"]
    targets = {
        "purchase_group": PURCHASE,
        "capital_group": PURCHASE,
        "energy": ENERGY,
        "transport_distance": TRANSPORT_DISTANCE,
        "transport_spend": TRANSPORT_SPEND,
        "travel_distance": TRAVEL_DISTANCE,
        "travel_spend": TRAVEL_SPEND,
        "waste_c5": WASTE_TYPES,
    }[group]
    absent = {"transport_spend": 9, "energy": 1}.get(group, 0)
    values = [targets[i % len(targets)] for i in range(count - absent)]
    return [*values, *(f"가상옛판값{group}{i}" for i in range(absent))]


def sample_template() -> Workbook:
    sheets: list[Sheet] = []
    names = [name for name, count in VALIDATION_NAME_COUNTS.items() for _ in range(count)]
    for sheet_name, count in zip(CATEGORY_SHEETS, VALIDATIONS_PER_SHEET, strict=True):
        cells: dict[str, Cell] = {}
        validations = [
            Validation("list", f"{'DEFG'[position]}21:{'DEFG'[position]}220", names.pop(0), None)
            for position in range(count)
        ]
        if sheet_name == C12_SHEET:
            cells.update({f"{letter}1": text(header) for letter, header in C12_HEADERS})
            for offset in range(5):
                cells[f"AA{2 + offset}"] = text(f"가상대분류{offset + 1:02d}")
            for offset, row in enumerate(row for row in range(2, 32) if row != 19):  # 19행은 빈 줄
                cells[f"AC{row}"] = text(f"가상대분류{offset % 5 + 1:02d}")
                cells[f"AD{row}"] = text(f"가상중분류{offset + 1:02d}")
            minor = ["가상고르지않음", *(f"{code} | {name}" for code, name in zip(C12_CODES, C12_NAMES, strict=True))]
            for offset, row in enumerate(row for row in range(2, 74) if row != 19):
                cells[f"AF{row}"] = text(f"가상중분류{offset % 29 + 1:02d}")
                cells[f"AG{row}"] = text(minor[offset])
            validations = [
                Validation("decimal", "J22:M122", "0", "100"),
                Validation("list", "C22:C122", "$AA$2:$AA$6", None),
                Validation("list", "D22:D122", C12_OFFSET_FORMULAS[0], None),
                Validation("list", "E22:E122", C12_OFFSET_FORMULAS[1], None),
                Validation("list", "I22:I122", '"g,kg,ton"', None),
            ]
        if sheet_name == "C15_투자":
            shared = SharedFormula(0, "F15", "F15:F25")
            for row in range(15, 26):  # 저장된 값이 빈 글자인 공유 수식 11칸
                cells[f"F{row}"] = FormulaCell("(D15+E15)*C15/100" if row == 15 else None, shared, TextCell(""))
            validations = [Validation("decimal", "D15:E25", "0", None), Validation("decimal", "C15:C25", "0", "100")]
        sheets.append(Sheet(sheet_name, cells, (), tuple(validations)))

    dropdown: dict[str, Cell] = {"M1": text("가상 상세 매핑 제목"), "A38": text("가상 안내 글")}
    columns = _dropdown_columns()
    for name, (letter, _) in NAMED_LISTS.items():
        dropdown[f"{letter}1"] = text(name)
        dropdown[f"{letter}2"] = text(f"가상 설명 {letter}")
        for offset, item in enumerate(columns[letter]):
            dropdown[f"{letter}{3 + offset}"] = text(item)
    dropdown.update({f"{letter}2": text(header) for letter, header in TRAVEL_CODE_HEADERS})
    for offset in range(33):
        row = 3 + offset
        dropdown[f"M{row}"] = text(TRAVEL_DISTANCE[offset])
        dropdown[f"N{row}"] = text(TRAVEL_CODES[offset])
        dropdown[f"O{row}"] = text(f"가상유형{offset + 1:02d}")
        dropdown[f"P{row}"] = text(f"가상키워드{offset + 1:02d}")
    sheets.append(Sheet(DROPDOWN_SHEET, dropdown, ("M1:P1", "A38:E38"), ()))

    review: dict[str, Cell] = {f"{letter}1": text(header) for letter, header in MAPPING_SUMMARY_HEADERS}
    for row in range(2, 11):
        for letter, _ in MAPPING_SUMMARY_HEADERS:
            review[f"{letter}{row}"] = text(f"가상 요약 {letter}{row}")
    review["A13"] = text("가상 사전 제목")
    review.update({f"{letter}14": text(header) for letter, header in MAPPING_HEADERS})
    row = 15
    for group, count in MAPPING_GROUPS:
        for new in _mapping_new_values(group, count):
            review[f"A{row}"] = text(group)
            review[f"B{row}"] = text(f"가상옛값{row}")
            review[f"C{row}"] = text(new)
            row += 1
    sheets.append(Sheet(MAPPING_SHEET, review, (), ()))

    defined = tuple(
        DefinedName(name, f"{DROPDOWN_SHEET}!${letter}$3:${letter}${2 + length}")
        for name, (letter, length) in NAMED_LISTS.items()
    )
    return Workbook(tuple(sheets), defined)


# ── 표본을 고쳐 쓰는 도구 ──────────────────────────────────────────────────


def with_cell(workbook: Workbook, sheet_name: str, address: str, cell: Cell | None) -> Workbook:
    """칸 하나를 바꾸거나(cell) 지운(None) 새 통합 문서."""
    sheets: list[Sheet] = []
    for sheet in workbook.sheets:
        if sheet.name == sheet_name:
            cells = dict(sheet.cells)
            if cell is None:
                del cells[address]
            else:
                cells[address] = cell
            sheet = replace(sheet, cells=cells)
        sheets.append(sheet)
    assert any(sheet.name == sheet_name for sheet in workbook.sheets), sheet_name
    return replace(workbook, sheets=tuple(sheets))


def with_sheet(workbook: Workbook, changed: Sheet) -> Workbook:
    assert any(sheet.name == changed.name for sheet in workbook.sheets), changed.name
    return replace(
        workbook, sheets=tuple(changed if sheet.name == changed.name else sheet for sheet in workbook.sheets)
    )


def sheet_named(workbook: Workbook, name: str) -> Sheet:
    return next(sheet for sheet in workbook.sheets if sheet.name == name)


# ── (B) 값 → xlsx 바이트 ───────────────────────────────────────────────────


def zip_bytes(entries: Mapping[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def workbook_xml(sheet_names: list[str], defined_names: tuple[DefinedName, ...] = ()) -> bytes:
    sheets = "".join(
        f'<sheet name={quoteattr(name)} sheetId="{number_}" r:id="rId{number_}"/>'
        for number_, name in enumerate(sheet_names, start=1)
    )
    names = "".join(
        f"<definedName name={quoteattr(item.name)}>{escape(item.refers_to)}</definedName>" for item in defined_names
    )
    names = f"<definedNames>{names}</definedNames>" if names else ""
    return (
        f'{XML_HEAD}<workbook xmlns="{MAIN_NS}" xmlns:r="{DOC_REL_NS}"><sheets>{sheets}</sheets>{names}</workbook>'
    ).encode()


def rels_xml(count: int, extra: str = "") -> bytes:
    relations = "".join(
        f'<Relationship Id="rId{number_}" Type="{WORKSHEET_TYPE}" Target="worksheets/sheet{number_}.xml"/>'
        for number_ in range(1, count + 1)
    )
    shared = f'<Relationship Id="rIdS" Type="{DOC_REL_NS}/sharedStrings" Target="sharedStrings.xml"/>'
    return f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">{relations}{shared}{extra}</Relationships>'.encode()


def shared_strings_xml(items: list[str]) -> bytes:
    """items 는 <si> 의 안쪽 XML(손으로 적은 조각)이다."""
    body = "".join(f"<si>{item}</si>" for item in items)
    return f'{XML_HEAD}<sst xmlns="{MAIN_NS}" count="{len(items)}" uniqueCount="{len(items)}">{body}</sst>'.encode()


def sheet_xml(rows: str, after: str = "") -> bytes:
    """rows 는 <sheetData> 의 안쪽 XML, after 는 그 뒤의 요소들(병합·유효성)."""
    return f'{XML_HEAD}<worksheet xmlns="{MAIN_NS}"><sheetData>{rows}</sheetData>{after}</worksheet>'.encode()


def xlsx_from_parts(sheets: Mapping[str, bytes], shared: bytes | None = None) -> dict[str, bytes]:
    """시트 이름 → 시트 XML 로 xlsx 의 항목들을 짓는다(zip 으로 묶기 전. 테스트가 항목을 고쳐 쓸 수 있게)."""
    names = list(sheets)
    parts: dict[str, bytes] = {}
    # zip 안의 차례를 시트 차례와 다르게(거꾸로) 둔다. 읽개는 workbook.xml 의 차례를 따라야 한다.
    for number_ in range(len(names), 0, -1):
        parts[f"xl/worksheets/sheet{number_}.xml"] = sheets[names[number_ - 1]]
    if shared is not None:
        parts["xl/sharedStrings.xml"] = shared
    parts["xl/_rels/workbook.xml.rels"] = rels_xml(len(names))
    parts["xl/workbook.xml"] = workbook_xml(names)
    return parts


def _text_element(value: str) -> str:
    space = ' xml:space="preserve"' if value != value.strip() else ""
    return f"<t{space}>{escape(value)}</t>"


def _order(address: str) -> tuple[int, int]:
    parsed = parse_address(address)
    assert isinstance(parsed, CellAddress), address
    return (parsed.row, parsed.column)


def _cell_xml(address: str, cell: Cell, strings: dict[str, int]) -> str:
    if isinstance(cell, TextCell):
        return f'<c r="{address}" t="s"><v>{strings.setdefault(cell.text, len(strings))}</v></c>'
    if isinstance(cell, NumberCell):
        return f'<c r="{address}"><v>{cell.xml_text}</v></c>'
    if cell.shared is None:
        formula = f"<f>{escape(cell.formula or '')}</f>"
    elif cell.formula is not None:
        formula = f'<f t="shared" ref="{cell.shared.ref}" si="{cell.shared.index}">{escape(cell.formula)}</f>'
    else:
        formula = f'<f t="shared" si="{cell.shared.index}"/>'
    if cell.cached is None:
        return f'<c r="{address}">{formula}</c>'
    if isinstance(cell.cached, TextCell):
        return f'<c r="{address}" t="str">{formula}<v>{escape(cell.cached.text)}</v></c>'
    return f'<c r="{address}">{formula}<v>{cell.cached.xml_text}</v></c>'


def _sheet_xml(sheet: Sheet, strings: dict[str, int]) -> bytes:
    rows: dict[int, list[str]] = {}
    for address in sorted(sheet.cells, key=_order):
        rows.setdefault(_order(address)[0], []).append(_cell_xml(address, sheet.cells[address], strings))
    body = "".join(f'<row r="{row}">{"".join(cells)}</row>' for row, cells in rows.items())
    after = ""
    if sheet.merges:
        after += "<mergeCells>" + "".join(f'<mergeCell ref="{ref}"/>' for ref in sheet.merges) + "</mergeCells>"
    if sheet.validations:
        items = ""
        for validation in sheet.validations:
            kind = f" type={quoteattr(validation.kind)}" if validation.kind else ""
            first = "" if validation.formula1 is None else f"<formula1>{escape(validation.formula1)}</formula1>"
            second = "" if validation.formula2 is None else f"<formula2>{escape(validation.formula2)}</formula2>"
            items += f"<dataValidation{kind} sqref={quoteattr(validation.sqref)}>{first}{second}</dataValidation>"
        after += f"<dataValidations>{items}</dataValidations>"
    return sheet_xml(body, after)


def xlsx_parts(workbook: Workbook) -> dict[str, bytes]:
    """`Workbook` 값을 xlsx 의 항목들로. 글자 칸은 공유 문자열로, 수식의 저장된 글자는 t="str" 로 적는다."""
    strings: dict[str, int] = {}
    sheets = {sheet.name: _sheet_xml(sheet, strings) for sheet in workbook.sheets}
    parts = xlsx_from_parts(sheets, shared_strings_xml([_text_element(value) for value in strings]))
    parts["xl/workbook.xml"] = workbook_xml(list(sheets), workbook.defined_names)
    return parts


def to_xlsx(workbook: Workbook) -> bytes:
    return zip_bytes(xlsx_parts(workbook))


MiB = 1024 * 1024


def padded(data: bytes, size: int) -> bytes:
    """xlsx 에 읽지 않는 항목(지어낸 난수 — 압축 안 함, 항목마다 4MiB 안)을 더해 정확히 `size` 바이트로 만든다."""

    def build(pad: int) -> bytes:
        noise, out = random.Random(593), io.BytesIO()  # noqa: S311 — 지어낸 채움(암호 아님)
        with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, "w") as target:
            for entry in source.infolist():
                target.writestr(entry, source.read(entry.filename))
            number = 0
            while pad > 0:
                chunk = min(pad, 4 * MiB)
                target.writestr(f"xl/media/pad{number}.bin", noise.randbytes(chunk), zipfile.ZIP_STORED)
                pad, number = pad - chunk, number + 1
        return out.getvalue()

    first = build(size - len(data))
    made = build(size - len(data) - (len(first) - size))  # zip 머리 바이트만큼 덜 채운다
    assert len(made) == size
    return made
