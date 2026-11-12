"""표본 지킴이: 지은 표본에 진짜 값·이름이 섞이지 않았는가. 순수 층.

계수는 전부 `9.` 로 시작하는 지어낸 수이고, 항목 이름·표준코드·사전의 낱말은 전부 `가상` 으로 시작한다.
진짜 표기를 쓰는 것은 꼴(시트 이름, 머리글)과 단위 표기, 값 자리의 `-` 뿐이다. 분모를 같이 단언한다.
"""

from esgapi.inventory.tests.s3sheets_support import CATEGORY_SHEETS, sample_factor_book, sample_template
from esgapi.inventory.tools.scope3_sheets.dropdowns import read_dropdowns
from esgapi.inventory.tools.scope3_sheets.factor_layout import FACTOR_SHEETS
from esgapi.inventory.tools.scope3_sheets.factors import Placeholder, load_factor_book
from esgapi.inventory.tools.scope3_sheets.grid import FormulaCell, NumberCell, TextCell

UNIT_TEXTS = {"kWh", "Nm³", "kg", "L", "GJ", "TJ", "ton", "g", "kgCO2eq/USD", "kgCO2eq/kWh"}


def test_every_factor_in_the_sample_book_is_a_made_up_number_starting_with_nine() -> None:
    book = load_factor_book(sample_factor_book())
    values = [entry.content for row in book.rows for entry in row.values if isinstance(entry.content, NumberCell)]
    cached = [entry.cached for row in book.rows for entry in row.derived]
    assert (len(values), len(cached)) == (591, 654)  # 분모
    assert [value.xml_text for value in values if not value.xml_text.startswith("9.")] == []
    assert [c for c in cached if not (isinstance(c, NumberCell) and c.xml_text.startswith("9."))] == []
    placeholders = [e.content.text for row in book.rows for e in row.values if isinstance(e.content, Placeholder)]
    assert placeholders == ["-"] * 8


def test_every_name_in_the_sample_book_is_made_up() -> None:
    book = load_factor_book(sample_factor_book())
    unit_columns = {
        (shape.name, column.letter) for shape in FACTOR_SHEETS for column in shape.columns if column.role == "unit"
    }
    names = 0
    units = 0
    for row in book.rows:
        for entry in (*row.labels, *row.extras):
            if (row.sheet, entry.column) in unit_columns:
                assert isinstance(entry.cell, TextCell) and entry.cell.text in UNIT_TEXTS, (row.sheet, row.row)
                units += 1
                continue
            names += 1
            if isinstance(entry.cell, TextCell):
                assert entry.cell.text.startswith("가상"), (row.sheet, row.row, entry.column)
            else:
                assert isinstance(entry.cell, NumberCell) and entry.cell.xml_text.startswith("9"), (row.sheet, row.row)
    assert (names, units) == (2180, 220)  # 분모(이 표본의 것): 이름표 칸 2,179 + 덧붙은 칸 1, 단위 칸 220
    assert [note.content for note in book.notes if not _made_up(note.content)] == []
    title_rows = [note for note in book.titles if note.cell.startswith("A") and note.sheet != "목록"]
    assert len(title_rows) >= 10


def _made_up(cell: object) -> bool:
    return isinstance(cell, TextCell) and cell.text.startswith("가상")


def test_every_item_code_and_word_in_the_sample_template_is_made_up() -> None:
    template = sample_template()
    drops = read_dropdowns(template)
    assert drops.problems == ()
    items = [item.text for named in drops.named_lists if not named.name.endswith("_UNIT") for item in named.items]
    units = [item.text for named in drops.named_lists if named.name.endswith("_UNIT") for item in named.items]
    codes = [text for code in drops.travel_codes for text in (code.display, code.code, code.defra_type, code.keywords)]
    c12 = [item.text for item in drops.c12.major]
    c12 += [text for mapped in (*drops.c12.middle, *drops.c12.minor) for text in (mapped.key, mapped.item)]
    entries = drops.mapping_review.entries
    words = [entry.old for entry in entries] + [entry.new for entry in entries if entry.group != "unit"]
    summary = [text for row in drops.mapping_review.summary for _, text in row.cells]
    assert (len(items), len(units), len(codes), len(c12), len(words), len(summary)) == (132, 9, 132, 205, 224, 45)
    for made_up in (*items, *codes, *c12, *words, *summary):
        assert made_up is not None and made_up.startswith("가상"), made_up
    assert set(units) <= UNIT_TEXTS
    assert {entry.new for entry in entries if entry.group == "unit"} <= UNIT_TEXTS


def test_the_sample_template_has_no_other_cells_than_the_ones_checked_above() -> None:
    """카테고리 시트에는 C12 의 목록과 C15 의 수식 칸뿐이다(입력 줄이 없다 — 행 파서는 다음 밴드의 일)."""
    template = sample_template()
    assert [sheet.name for sheet in template.sheets[:21]] == list(CATEGORY_SHEETS)
    for sheet in template.sheets[:21]:
        if sheet.name == "C12_판매제품폐기":
            assert {address.rstrip("0123456789") for address in sheet.cells} == {"AA", "AC", "AD", "AF", "AG"}
        elif sheet.name == "C15_투자":
            assert all(isinstance(cell, FormulaCell) and cell.cached == TextCell("") for cell in sheet.cells.values())
            assert len(sheet.cells) == 11
        else:
            assert sheet.cells == {}
