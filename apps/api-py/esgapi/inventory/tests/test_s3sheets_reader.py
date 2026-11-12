"""xlsx 읽개(`tools/xlsx_reader.py`)가 읽는 것. 순수 층(메모리 안에서 지은 바이트. 파일·소켓 없음)."""

from esgapi.inventory.tests.s3sheets_support import (
    sample_factor_book,
    sample_template,
    shared_strings_xml,
    sheet_xml,
    to_xlsx,
    workbook_xml,
    xlsx_from_parts,
    zip_bytes,
)
from esgapi.inventory.tools.scope3_sheets.grid import (
    DefinedName,
    FormulaCell,
    NumberCell,
    SharedFormula,
    TextCell,
    Validation,
    Workbook,
)
from esgapi.inventory.tools.xlsx_reader import read_workbook


def read(rows: str, strings: list[str] | None = None, after: str = "") -> Workbook:
    shared = None if strings is None else shared_strings_xml(strings)
    result = read_workbook(zip_bytes(xlsx_from_parts({"가상": sheet_xml(rows, after)}, shared)))
    assert isinstance(result, Workbook), result
    return result


def test_what_is_read_equals_the_value_it_was_written_from() -> None:
    """(B) 바이트로 적은 표본을 읽으면 (A) 값과 같다. 두 표본 다."""
    for sample in (sample_factor_book(), sample_template()):
        assert read_workbook(to_xlsx(sample)) == sample


def test_rich_text_runs_are_joined() -> None:
    book = read(
        '<row r="1"><c r="A1" t="s"><v>0</v></c></row>', ["<r><t>가상</t></r><r><rPr><b/></rPr><t>이름</t></r>"]
    )
    assert book.sheets[0].cells == {"A1": TextCell("가상이름")}


def test_phonetic_text_is_not_appended() -> None:
    item = '<t>가상이름</t><rPh sb="0" eb="2"><t>후리가나</t></rPh><phoneticPr fontId="1"/>'
    book = read('<row r="1"><c r="A1" t="s"><v>0</v></c></row>', [item])
    assert book.sheets[0].cells == {"A1": TextCell("가상이름")}


def test_leading_and_trailing_spaces_are_kept() -> None:
    book = read('<row r="1"><c r="A1" t="s"><v>0</v></c></row>', ['<t xml:space="preserve"> 가상 이름  </t>'])
    assert book.sheets[0].cells == {"A1": TextCell(" 가상 이름  ")}


def test_an_integer_shaped_number_is_kept_as_written() -> None:
    book = read('<row r="1"><c r="A1"><v>9</v></c><c r="B1" t="n"><v>-907</v></c></row>')
    assert book.sheets[0].cells == {"A1": NumberCell("9", "9"), "B1": NumberCell("-907", "-907")}


def test_the_decimal_is_the_shortest_round_trip_form() -> None:
    """파일 속 글자는 그대로, decimal 은 같은 배정밀도 수의 가장 짧은 표기(지수 없이). 지어낸 수다."""
    book = read(
        '<row r="1"><c r="A1"><v>9.0001000000000001</v></c><c r="B1"><v>9.0001E-2</v></c>'
        '<c r="C1"><v>9.5E+3</v></c><c r="D1"><v>-9.25e-7</v></c></row>'
    )
    assert book.sheets[0].cells == {
        "A1": NumberCell("9.0001000000000001", "9.0001"),
        "B1": NumberCell("9.0001E-2", "0.090001"),
        "C1": NumberCell("9.5E+3", "9500.0"),
        "D1": NumberCell("-9.25e-7", "-0.000000925"),
    }


def test_shared_formula_followers_carry_no_formula_text() -> None:
    """으뜸 칸은 식 글자와 ref, 딸린 칸은 formula None 이고 으뜸 칸의 주소를 가리키며 저장된 값이 있다."""
    book = read(
        '<row r="4"><c r="F4"><v>9.1</v></c><c r="I4"><f t="shared" ref="I4:I6" si="0">F4/9.9</f><v>9.11</v></c></row>'
        '<row r="5"><c r="I5"><f t="shared" si="0"/><v>9.12</v></c></row>'
        '<row r="6"><c r="I6"><f t="shared" si="0"></f><v>9.13</v></c></row>'
        '<row r="7"><c r="I7"><f>SUM(I4:I6)</f><v>9.14</v></c></row>'
    )
    shared = SharedFormula(0, "I4", "I4:I6")
    cells = book.sheets[0].cells
    assert cells["I4"] == FormulaCell("F4/9.9", shared, NumberCell("9.11", "9.11"))
    assert cells["I5"] == FormulaCell(None, shared, NumberCell("9.12", "9.12"))
    assert cells["I6"] == FormulaCell(None, shared, NumberCell("9.13", "9.13"))
    assert cells["I7"] == FormulaCell("SUM(I4:I6)", None, NumberCell("9.14", "9.14"))
    formulas = [cell for cell in cells.values() if isinstance(cell, FormulaCell)]
    assert len(formulas) == 4  # 으뜸 1 + 딸린 2 + 공유 아닌 것 1
    assert sum(1 for cell in formulas if cell.formula is None) == 2


def test_a_follower_written_before_its_master_still_points_at_it() -> None:
    book = read(
        '<row r="1"><c r="B1"><f t="shared" si="3"/><v>9.1</v></c></row>'
        '<row r="2"><c r="B2"><f t="shared" ref="B1:B2" si="3">A2*9</f><v>9.2</v></c></row>'
    )
    assert book.sheets[0].cells["B1"] == FormulaCell(None, SharedFormula(3, "B2", "B1:B2"), NumberCell("9.1", "9.1"))


def test_an_empty_stored_string_is_an_empty_text_not_none() -> None:
    """t="str" 이고 <v> 가 빈 수식 칸: 저장된 값은 빈 글자다. <v> 가 아예 없으면 None."""
    book = read(
        '<row r="15"><c r="F15" t="str"><f t="shared" ref="F15:F16" si="0">(D15+E15)*C15/100</f><v></v></c></row>'
        '<row r="16"><c r="F16" t="str"><f t="shared" si="0"/><v/></c><c r="G16"><f>A1</f></c></row>'
    )
    shared = SharedFormula(0, "F15", "F15:F16")
    assert book.sheets[0].cells == {
        "F15": FormulaCell("(D15+E15)*C15/100", shared, TextCell("")),
        "F16": FormulaCell(None, shared, TextCell("")),
        "G16": FormulaCell("A1", None, None),
    }


def test_a_cell_with_only_a_style_is_not_in_the_sheet() -> None:
    book = read('<row r="1"><c r="A1" s="3"/><c r="B1" t="str"><v>가상</v></c></row>')
    assert book.sheets[0].cells == {"B1": TextCell("가상")}


def test_merges_validations_and_defined_names_are_carried_as_written() -> None:
    after = (
        '<mergeCells count="2"><mergeCell ref="A1:I1"/><mergeCell ref="A19:I19"/></mergeCells>'
        '<dataValidations count="3">'
        '<dataValidation type="list" allowBlank="1" sqref="D21:D220"><formula1>DD_ENERGY</formula1></dataValidation>'
        '<dataValidation type="decimal" sqref="J22:M122"><formula1>0</formula1><formula2>100</formula2>'
        "</dataValidation>"
        '<dataValidation sqref="A1"/>'
        "</dataValidations>"
    )
    parts = xlsx_from_parts({"가상": sheet_xml("", after)})
    names = (DefinedName("DD_ENERGY", "가상!$B$3:$B$16"),)
    parts["xl/workbook.xml"] = workbook_xml(["가상"], names)
    book = read_workbook(zip_bytes(parts))
    assert isinstance(book, Workbook)
    assert book.defined_names == names
    assert book.sheets[0].merges == ("A1:I1", "A19:I19")
    assert book.sheets[0].validations == (
        Validation("list", "D21:D220", "DD_ENERGY", None),
        Validation("decimal", "J22:M122", "0", "100"),
        Validation("", "A1", None, None),
    )


def test_sheets_come_in_workbook_order_not_zip_order() -> None:
    sheets = {name: sheet_xml(f'<row r="1"><c r="A1"><v>{9 + i}</v></c></row>') for i, name in enumerate("가나다")}
    parts = xlsx_from_parts(sheets)
    # 표본은 zip 안에 시트를 거꾸로 넣는다(3, 2, 1).
    assert next(name for name in parts if "worksheets" in name).endswith("sheet3.xml")
    book = read_workbook(zip_bytes(parts))
    assert isinstance(book, Workbook)
    assert [sheet.name for sheet in book.sheets] == ["가", "나", "다"]
    assert [sheet.cells["A1"] for sheet in book.sheets] == [NumberCell(str(9 + i), str(9 + i)) for i in range(3)]


def test_a_workbook_without_shared_strings_reads_as_long_as_no_cell_needs_them() -> None:
    assert read('<row r="1"><c r="A1"><v>9</v></c></row>').sheets[0].cells == {"A1": NumberCell("9", "9")}


# ── openpyxl·pandas 가 쓰는 꼴(MARC-ISSUE-241 · S3C-r1) ──


def test_an_absolute_target_under_xl_reads_like_the_relative_one() -> None:
    """openpyxl 은 `Target="/xl/worksheets/sheet1.xml"`(OPC 뿌리 기준 절대 part 이름)로 쓴다."""
    parts = xlsx_from_parts({"가상": sheet_xml('<row r="1"><c r="A1"><v>9</v></c></row>')})
    relative = read_workbook(zip_bytes(parts))
    parts["xl/_rels/workbook.xml.rels"] = parts["xl/_rels/workbook.xml.rels"].replace(
        b'Target="worksheets/', b'Target="/xl/worksheets/'
    )
    assert b'Target="/xl/worksheets/sheet1.xml"' in parts["xl/_rels/workbook.xml.rels"]
    absolute = read_workbook(zip_bytes(parts))
    assert isinstance(absolute, Workbook)
    assert absolute == relative
    assert absolute.sheets[0].cells == {"A1": NumberCell("9", "9")}


def test_inline_strings_read_like_shared_strings() -> None:
    """2-0 a 의 openpyxl 3.1.5 값: 조각을 잇고 `<rPh>` 는 빼고 XML 이스케이프는 풀린다. `<is>` 가 없으면 칸 없음."""
    cells = (
        read(
            '<row r="1">'
            '<c r="A1" t="inlineStr"><is><t>가상 &amp; &lt;글&gt;</t></is></c>'
            '<c r="B1" t="inlineStr"><is><r><t>가</t></r><r><rPr><b/></rPr><t>상</t></r></is></c>'
            '<c r="C1" t="inlineStr"><is><t>가상</t><rPh sb="0" eb="1"><t>카소</t></rPh></is></c>'
            '<c r="D1" t="inlineStr"/>'
            '<c r="E1" t="inlineStr"><is/></c>'
            '<c r="F1" t="inlineStr"><is><t/></is></c>'
            '<c r="G1" t="inlineStr"><is><t xml:space="preserve"> 가상 </t></is></c>'
            "</row>"
        )
        .sheets[0]
        .cells
    )
    assert cells == {
        "A1": TextCell("가상 & <글>"),
        "B1": TextCell("가상"),
        "C1": TextCell("가상"),
        "E1": TextCell(""),
        "F1": TextCell(""),
        "G1": TextCell(" 가상 "),
    }


def test_an_empty_stored_value_of_a_formula_is_no_value() -> None:
    """openpyxl 은 수식 칸을 셈하지 않고 빈 `<v/>` 로 쓴다 — `<v>` 가 없는 칸과 같다.
    `t="str"` 의 빈 값은 빈 글자 그대로."""
    cells = (
        read(
            '<row r="1">'
            '<c r="A1"><v>1</v></c>'
            '<c r="B1"><f>A1*2</f><v></v></c>'
            '<c r="C1"><f>A1*2</f><v/></c>'
            '<c r="D1" t="n"><f>A1*2</f><v></v></c>'
            '<c r="E1"><f t="shared" ref="E1:F1" si="0">A1*2</f><v>2</v></c>'
            '<c r="F1"><f t="shared" si="0"/><v/></c>'
            '<c r="G1" t="str"><f>""</f><v/></c>'
            "</row>"
        )
        .sheets[0]
        .cells
    )
    shared = SharedFormula(0, "E1", "E1:F1")
    assert cells == {
        "A1": NumberCell("1", "1"),
        "B1": FormulaCell("A1*2", None, None),
        "C1": FormulaCell("A1*2", None, None),
        "D1": FormulaCell("A1*2", None, None),
        "E1": FormulaCell("A1*2", shared, NumberCell("2", "2")),
        "F1": FormulaCell(None, shared, None),
        "G1": FormulaCell('""', None, TextCell("")),
    }


def test_booleans_read_as_the_words_excel_shows() -> None:
    """grid 에 참거짓 칸이 없다: `<v>1</v>`·`<v>0</v>` 만 `TRUE`·`FALSE` 글자로(openpyxl·pandas 는 bool)."""
    cells = (
        read(
            '<row r="1"><c r="A1" t="b"><v>1</v></c><c r="B1" t="b"><v>0</v></c>'
            '<c r="C1" t="b"><f>A1</f><v>1</v></c><c r="D1" t="b"/></row>'
        )
        .sheets[0]
        .cells
    )
    assert cells == {
        "A1": TextCell("TRUE"),
        "B1": TextCell("FALSE"),
        "C1": FormulaCell("A1", None, TextCell("TRUE")),
    }
