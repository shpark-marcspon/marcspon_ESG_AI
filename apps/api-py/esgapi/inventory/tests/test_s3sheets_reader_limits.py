"""xlsx 읽개의 거절과 상한: 망가진·악의의 바이트에도 예외나 폭주 없이 갈래(`ReaderProblem`)로 답한다. 순수 층.

상한의 값은 어림이다. 여기서는 상수를 작게 바꿔 「넘으면 그 갈래로 답한다」만 잰다. 큰 파일의 시간·메모리는 재지 않는다.
"""

import warnings
import zipfile
from io import BytesIO

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from esgapi.inventory.tests.s3sheets_support import (
    DOC_REL_NS,
    MAIN_NS,
    PKG_REL_NS,
    WORKSHEET_TYPE,
    XML_HEAD,
    MiB,
    number,
    padded,
    shared_strings_xml,
    sheet_xml,
    text,
    xlsx_from_parts,
    xlsx_parts,
    zip_bytes,
)
from esgapi.inventory.tools import xlsx_reader
from esgapi.inventory.tools.scope3_sheets.grid import FormulaCell, SharedFormula, Sheet, TextCell, Validation, Workbook
from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook

SHEET = "xl/worksheets/sheet1.xml"
WORKBOOK = "xl/workbook.xml"
RELS = "xl/_rels/workbook.xml.rels"
STRINGS = "xl/sharedStrings.xml"
ONE_CELL = '<row r="1"><c r="A1"><v>9</v></c></row>'


def parts_of(rows: str = ONE_CELL, strings: list[str] | None = None) -> dict[str, bytes]:
    return xlsx_from_parts({"가상": sheet_xml(rows)}, None if strings is None else shared_strings_xml(strings))


def refused(data: bytes) -> ReaderProblem:
    result = read_workbook(data)
    assert isinstance(result, ReaderProblem), "읽혔다(거절되어야 한다)"
    return result


def refused_rows(rows: str, strings: list[str] | None = None) -> ReaderProblem:
    return refused(zip_bytes(parts_of(rows, strings)))


def test_empty_bytes_are_refused() -> None:
    assert refused(b"").kind == "empty"


def test_bytes_that_are_not_a_zip_are_refused() -> None:
    assert refused(b"PK\x03\x04 not really").kind == "not_a_zip"
    assert refused(b"<html>").kind == "not_a_zip"


def test_more_bytes_than_the_limit_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    data = zip_bytes(parts_of())
    monkeypatch.setattr(xlsx_reader, "MAX_BYTES", len(data) - 1)
    assert refused(data).kind == "too_many_bytes"


def test_the_default_byte_limit_stays_ten_mib_and_a_caller_may_pass_another() -> None:
    """기본(계수 책·다른 부름)은 10MiB 그대로, 온실가스 올리기만 `max_bytes=GHG_UPLOAD_MAX_BYTES`(20MB — ENT-593)."""
    assert xlsx_reader.MAX_BYTES == 10_485_760
    assert xlsx_reader.GHG_UPLOAD_MAX_BYTES == 20_971_520
    data = padded(zip_bytes(parts_of()), 10 * MiB + 1)
    assert refused(data).kind == "too_many_bytes"
    assert isinstance(read_workbook(data, max_bytes=xlsx_reader.GHG_UPLOAD_MAX_BYTES), Workbook)
    assert isinstance(read_workbook(padded(zip_bytes(parts_of()), 10 * MiB)), Workbook)  # 상한 그대로는 읽는다


def test_a_passed_byte_limit_is_exact() -> None:
    data = zip_bytes(parts_of())
    assert isinstance(read_workbook(data, max_bytes=len(data)), Workbook)
    result = read_workbook(data, max_bytes=len(data) - 1)
    assert isinstance(result, ReaderProblem) and result.kind == "too_many_bytes"


def test_more_entries_than_the_limit_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(xlsx_reader, "MAX_ENTRIES", 2)
    assert refused(zip_bytes(parts_of())).kind == "too_many_entries"


def test_an_entry_over_the_declared_size_limit_is_refused_before_reading(monkeypatch: pytest.MonkeyPatch) -> None:
    parts = parts_of()
    parts["xl/media/big.bin"] = b"0" * 5000  # 읽지 않는 항목이어도 선언된 크기로 거른다
    monkeypatch.setattr(xlsx_reader, "MAX_ENTRY_BYTES", 4999)
    problem = refused(zip_bytes(parts))
    assert (problem.kind, problem.where) == ("entry_too_large", "xl/media/big.bin")


def test_opened_entries_over_the_total_limit_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    parts = parts_of()
    opened = sum(len(parts[name]) for name in (WORKBOOK, RELS, SHEET))
    monkeypatch.setattr(xlsx_reader, "MAX_OPENED_BYTES", opened - 1)
    assert refused(zip_bytes(parts)).kind == "opened_entries_too_large"
    monkeypatch.setattr(xlsx_reader, "MAX_OPENED_BYTES", opened)
    assert isinstance(read_workbook(zip_bytes(parts)), Workbook)


def test_two_entries_with_the_same_name_are_refused() -> None:
    """zipfile 은 같은 이름이 둘이면 조용히 뒤의 것을 준다. 무엇을 읽었는지 말할 수 없으므로 거절한다."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in parts_of().items():
            archive.writestr(name, data)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # zipfile 의 「Duplicate name」 경고(이 표본을 짓는 자리만)
            archive.writestr(SHEET, sheet_xml('<row r="1"><c r="A1"><v>8</v></c></row>'))
    problem = refused(buffer.getvalue())
    assert (problem.kind, problem.where) == ("duplicate_entry", SHEET)


def test_an_encrypted_entry_is_refused() -> None:
    data = bytearray(zip_bytes(parts_of()))
    position = data.find(b"PK\x01\x02")
    while position != -1:  # 가운데 목록의 항목마다 「암호」 깃발을 세운다
        data[position + 8] |= 0x1
        position = data.find(b"PK\x01\x02", position + 4)
    assert refused(bytes(data)).kind == "encrypted_entry"


def test_a_zip_without_the_workbook_part_is_refused() -> None:
    parts = parts_of()
    del parts[WORKBOOK]
    problem = refused(zip_bytes(parts))
    assert (problem.kind, problem.where) == ("missing_entry", WORKBOOK)


def test_a_sheet_the_relationship_points_at_but_is_not_there_is_refused() -> None:
    parts = parts_of()
    del parts[SHEET]
    problem = refused(zip_bytes(parts))
    assert (problem.kind, problem.where) == ("missing_entry", SHEET)


def test_broken_xml_is_refused() -> None:
    parts = parts_of()
    parts[SHEET] = parts[SHEET][:-20]
    problem = refused(zip_bytes(parts))
    assert (problem.kind, problem.where) == ("broken_xml", SHEET)


def test_xml_with_another_root_is_refused() -> None:
    parts = parts_of()
    parts[SHEET] = f'{XML_HEAD}<chartsheet xmlns="{MAIN_NS}"/>'.encode()
    assert refused(zip_bytes(parts)).kind == "unexpected_xml"


DOCTYPE_SHEET = (
    '<!DOCTYPE worksheet [<!ENTITY nine "9">]>'
    f'<worksheet xmlns="{MAIN_NS}"><sheetData><row r="1"><c r="A1"><v>&nine;</v></c></row></sheetData></worksheet>'
)


def test_a_doctype_is_refused_utf8() -> None:
    parts = parts_of()
    parts[SHEET] = ('<?xml version="1.0" encoding="UTF-8"?>' + DOCTYPE_SHEET).encode("utf-8")
    problem = refused(zip_bytes(parts))
    assert (problem.kind, problem.where) == ("doctype", SHEET)


def test_a_doctype_is_refused_utf16() -> None:
    """바이트에서 `<!DOCTYPE` 를 찾는 방어는 UTF-16 에 뚫린다. 파서의 갈고리는 인코딩과 무관하게 걸린다."""
    parts = parts_of()
    parts[SHEET] = ('<?xml version="1.0" encoding="UTF-16"?>' + DOCTYPE_SHEET).encode("utf-16")
    assert b"<!DOCTYPE" not in parts[SHEET]
    problem = refused(zip_bytes(parts))
    assert (problem.kind, problem.where) == ("doctype", SHEET)


def test_entity_expansion_ends_as_a_branch_with_nothing_expanded() -> None:
    entities = '<!ENTITY a0 "9999999999">' + "".join(f'<!ENTITY a{i} "{f"&a{i - 1};" * 10}">' for i in range(1, 10))
    parts = parts_of()
    parts[STRINGS] = (
        f'<?xml version="1.0"?><!DOCTYPE sst [{entities}]><sst xmlns="{MAIN_NS}"><si><t>&a9;</t></si></sst>'
    ).encode()
    problem = refused(zip_bytes(parts))
    assert problem.kind in ("doctype", "broken_xml")
    assert problem.where == STRINGS
    assert len(problem.detail) < 200  # 풀린 글자가 실려 나오지 않는다


@pytest.mark.parametrize(
    "relation",
    [
        f'<Relationship Id="rId1" Type="{WORKSHEET_TYPE}" Target="https://e.invalid/s.xml" TargetMode="External"/>',
        f'<Relationship Id="rId1" Type="{WORKSHEET_TYPE}" Target="../xl/worksheets/sheet1.xml"/>',
        f'<Relationship Id="rId1" Type="{WORKSHEET_TYPE}"/>',
        f'<Relationship Id="rId9" Type="{WORKSHEET_TYPE}" Target="worksheets/sheet1.xml"/>',
        f'<Relationship Id="rId1" Type="{WORKSHEET_TYPE}" Target="worksheets\\sheet1.xml"/>',
        f'<Relationship Id="rId1" Type="{WORKSHEET_TYPE}" Target="c:worksheets/sheet1.xml"/>',
    ],
    ids=["external", "parent", "no-target", "no-such-id", "backslash", "colon"],
)
def test_a_relationship_that_is_not_a_relative_path_under_xl_is_refused(relation: str) -> None:
    parts = parts_of()
    parts[RELS] = f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">{relation}</Relationships>'.encode()
    problem = refused(zip_bytes(parts))
    assert (problem.kind, problem.where) == ("bad_relationship", RELS)


def with_target(target: str) -> bytes:
    parts = parts_of()
    relation = f'<Relationship Id="rId1" Type="{WORKSHEET_TYPE}" Target="{target}"/>'
    parts[RELS] = f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">{relation}</Relationships>'.encode()
    return zip_bytes(parts)


@pytest.mark.parametrize(
    "target",
    [
        "/docProps/app.xml",
        "//xl/worksheets/sheet1.xml",
        "/",
        "/xl/",
        "/xl//worksheets/sheet1.xml",
        "/xl/../docProps/core.xml",
        "/../xl/worksheets/sheet1.xml",
        "/_rels/.rels",
        "/XL/worksheets/sheet1.xml",
    ],
    ids=["docprops", "two-slashes", "root", "xl-folder", "empty-piece", "xl-parent", "root-parent", "rels", "upper-xl"],
)
def test_an_absolute_target_outside_the_xl_part_names_is_refused(target: str) -> None:
    """OPC 절대 part 이름은 `/xl/…` 만 받는다(openpyxl 의 꼴). 그 밖은 시트로 읽히지 않는다."""
    problem = refused(with_target(target))
    assert (problem.kind, problem.where) == ("bad_relationship", RELS)


def test_an_external_relationship_is_refused_even_with_an_absolute_xl_target() -> None:
    """바깥(External) 검사는 Target 꼴보다 먼저다: `/xl/…` 꼴이어도 바깥이면 거절(경계 1 검증 권고)."""
    parts = parts_of()
    relation = (
        f'<Relationship Id="rId1" Type="{WORKSHEET_TYPE}" Target="/xl/worksheets/sheet1.xml" TargetMode="External"/>'
    )
    parts[RELS] = f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">{relation}</Relationships>'.encode()
    problem = refused(zip_bytes(parts))
    assert (problem.kind, problem.where) == ("bad_relationship", RELS)
    assert "External" in problem.detail


def test_a_percent_encoded_target_is_not_decoded() -> None:
    """`%2e%2e` 를 풀지 않는다: 그 글자 그대로 zip 이름이 되어 없는 항목으로 끝난다."""
    problem = refused(with_target("/xl/%2e%2e/worksheets/sheet1.xml"))
    assert (problem.kind, problem.where) == ("missing_entry", "xl/%2e%2e/worksheets/sheet1.xml")


@pytest.mark.parametrize(
    "cell",
    [
        '<c r="A1" t="b"><v>2</v></c>',
        '<c r="A1" t="b"><v/></c>',
        '<c r="A1" t="b"><v>TRUE</v></c>',
        '<c r="A1" t="e"><v>#N/A</v></c>',
        '<c r="A1" t="d"><v>2026-10-13</v></c>',
        '<c r="A1" t="가상"><v>1</v></c>',
    ],
    ids=["b", "b-empty", "b-word", "e", "d", "unknown"],
)
def test_cell_types_the_reader_does_not_read_are_refused_not_skipped(cell: str) -> None:
    problem = refused_rows(f'<row r="1">{cell}</row>')
    assert (problem.kind, problem.where) == ("unsupported_cell_type", f"{SHEET}!A1")


def test_an_inline_string_with_a_formula_or_a_stored_value_is_refused() -> None:
    with_formula = refused_rows('<row r="1"><c r="A1" t="inlineStr"><f>B1</f><is><t>가상</t></is></c></row>')
    assert (with_formula.kind, with_formula.where) == ("unsupported_formula", f"{SHEET}!A1")
    with_value = refused_rows('<row r="1"><c r="A1" t="inlineStr"><is><t>가상</t></is><v>9</v></c></row>')
    assert (with_value.kind, with_value.where) == ("unexpected_xml", f"{SHEET}!A1")


@pytest.mark.parametrize("kind", ["array", "dataTable"])
def test_array_and_table_formulas_are_refused(kind: str) -> None:
    problem = refused_rows(f'<row r="1"><c r="A1"><f t="{kind}" ref="A1:A2">B1:B2*9</f><v>9</v></c></row>')
    assert (problem.kind, problem.where) == ("unsupported_formula", f"{SHEET}!A1")


@pytest.mark.parametrize(
    "cell", ["<c><v>9</v></c>", '<c r="a1"><v>9</v></c>', '<c r="$A$1"><v>9</v></c>', '<c r="1"/>']
)
def test_a_cell_without_a_proper_address_is_refused(cell: str) -> None:
    problem = refused_rows(f'<row r="1">{cell}</row>')
    assert (problem.kind, problem.where) == ("bad_cell_address", SHEET)


def test_two_cells_at_the_same_address_are_refused() -> None:
    problem = refused_rows('<row r="1"><c r="A1"><v>9</v></c><c r="A1"><v>8</v></c></row>')
    assert (problem.kind, problem.where) == ("duplicate_cell", f"{SHEET}!A1")


@pytest.mark.parametrize("index", ["1", "-1", "0.0", "가", "", " 0"])
def test_a_shared_string_index_out_of_range_or_not_an_integer_is_refused(index: str) -> None:
    problem = refused_rows(f'<row r="1"><c r="A1" t="s"><v>{index}</v></c></row>', ["<t>가상</t>"])
    assert (problem.kind, problem.where) == ("bad_shared_string", f"{SHEET}!A1")


@pytest.mark.parametrize(
    "digits",
    [
        "1_000",
        "１２",
        " 12 ",
        "12 ",
        "Infinity",
        "-inf",
        "nan",
        "+1",
        "1,000",
        "0x10",
        "1e",
        ".5",
        "5.",
        "",
        "1e400",
        "1e-300",
    ],
)
def test_number_text_outside_the_grammar_is_refused(digits: str) -> None:
    """float() 는 `1_000`·` 12 `·`Infinity`·전각 숫자를 받는다. 문법을 먼저 본다.

    `1e400` 은 무한대, `1e-300` 은 풀면 302자다(문법에는 맞고 그 뒤에서 걸린다).
    """
    problem = refused_rows(f'<row r="1"><c r="A1"><v>{digits}</v></c></row>')
    assert (problem.kind, problem.where) == ("bad_number", f"{SHEET}!A1")


def test_an_empty_stored_number_outside_a_formula_is_refused_also_self_closed() -> None:
    """빈 `<v/>` 가 값 없음으로 읽히는 것은 수식 칸뿐이다(openpyxl 이 셈하지 않고 쓴 꼴)."""
    for cell in ('<c r="A1"><v/></c>', '<c r="A1" t="n"><v></v></c>'):
        problem = refused_rows(f'<row r="1">{cell}</row>')
        assert (problem.kind, problem.where) == ("bad_number", f"{SHEET}!A1")


def test_an_empty_stored_shared_string_index_is_refused_even_in_a_formula() -> None:
    """빈 수식 값을 없음으로 받는 것은 t 없음·`t="n"` 만이다 — `t="s"` 수식 칸의 빈 `<v/>` 는 번호가 아니다
    (경계 1 검증 B1)."""
    for cell in ('<c r="A1" t="s"><f>B1</f><v/></c>', '<c r="A1" t="s"><f>B1</f><v></v></c>'):
        problem = refused_rows(f'<row r="1">{cell}</row>', ["<t>가상</t>"])
        assert (problem.kind, problem.where) == ("bad_shared_string", f"{SHEET}!A1")


def test_a_number_longer_than_the_decimal_limit_is_refused() -> None:
    assert refused_rows(f'<row r="1"><c r="A1"><v>{"9" * 65}</v></c></row>').kind == "bad_number"
    assert isinstance(read_workbook(zip_bytes(parts_of(f'<row r="1"><c r="A1"><v>{"9" * 64}</v></c></row>'))), Workbook)


@pytest.mark.parametrize(
    "rows",
    [
        '<row r="1"><c r="A1"><f t="shared" si="0"/><v>9</v></c></row>',
        '<row r="1"><c r="A1"><f t="shared" si="0">B1</f><v>9</v></c></row>',
        '<row r="1"><c r="A1"><f t="shared" si="가">B1</f><v>9</v></c></row>',
        '<row r="1"><c r="A1"><f t="shared" ref="A1:A2" si="0">B1</f></c>'
        '<c r="B1"><f t="shared" ref="B1" si="0">C1</f></c></row>',
    ],
    ids=["follower-without-master", "master-without-ref", "si-not-a-number", "two-masters"],
)
def test_a_broken_shared_formula_group_is_refused(rows: str) -> None:
    assert refused_rows(rows).kind == "bad_shared_formula"


def test_a_plain_formula_without_text_is_refused() -> None:
    assert refused_rows('<row r="1"><c r="A1"><f/><v>9</v></c></row>').kind == "unsupported_formula"


def test_more_sheets_cells_or_shared_strings_than_the_limits_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    two_sheets = zip_bytes(xlsx_from_parts({"가": sheet_xml(ONE_CELL), "나": sheet_xml(ONE_CELL)}))
    three_cells = zip_bytes(parts_of('<row r="1"><c r="A1"><v>9</v></c><c r="B1"><v>9</v></c><c r="C1" s="1"/></row>'))
    two_strings = zip_bytes(parts_of(ONE_CELL, ["<t>가상</t>", "<t>가상</t>"]))
    for data in (two_sheets, three_cells, two_strings):
        assert isinstance(read_workbook(data), Workbook)
    monkeypatch.setattr(xlsx_reader, "MAX_SHEETS", 1)
    monkeypatch.setattr(xlsx_reader, "MAX_CELLS", 2)
    monkeypatch.setattr(xlsx_reader, "MAX_SHARED_STRINGS", 1)
    assert refused(two_sheets).kind == "too_many_sheets"
    assert refused(three_cells).kind == "too_many_cells"
    assert refused(two_strings).kind == "too_many_shared_strings"


def test_the_cell_limit_counts_the_whole_workbook_not_each_sheet(monkeypatch: pytest.MonkeyPatch) -> None:
    two_cells = '<row r="1"><c r="A1"><v>9</v></c><c r="B1"><v>9</v></c></row>'
    data = zip_bytes(xlsx_from_parts({"가": sheet_xml(two_cells), "나": sheet_xml(two_cells)}))
    monkeypatch.setattr(xlsx_reader, "MAX_CELLS", 4)
    assert isinstance(read_workbook(data), Workbook)
    monkeypatch.setattr(xlsx_reader, "MAX_CELLS", 3)  # 시트마다는 2칸이지만 통째로는 4칸이다
    assert refused(data).kind == "too_many_cells"


@pytest.mark.parametrize("method", [zipfile.ZIP_LZMA, zipfile.ZIP_BZIP2], ids=["lzma", "bzip2"])
def test_entries_compressed_with_anything_but_stored_or_deflated_are_refused(method: int) -> None:
    """LZMA·BZIP2 는 망가진 자료에서 읽개가 이름으로 적지 않은 예외를 낸다. 읽기 전에 압축 방식으로 거른다."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", method) as archive:
        for name, data in parts_of().items():
            archive.writestr(name, data)
    assert refused(buffer.getvalue()).kind == "unsupported_compression"
    broken = bytearray(buffer.getvalue())
    for position in range(60, 120):  # 첫 항목의 자료를 망가뜨려도 예외가 아니라 같은 갈래다
        broken[position] ^= 0xFF
    assert isinstance(read_workbook(bytes(broken)), ReaderProblem)
    stored = BytesIO()
    with zipfile.ZipFile(stored, "w", zipfile.ZIP_STORED) as archive:
        for name, data in parts_of().items():
            archive.writestr(name, data)
    assert isinstance(read_workbook(stored.getvalue()), Workbook)


def lying_zip(declared: int, real: int) -> bytes:
    """시트 항목의 선언된(풀린) 크기를 속인 zip: 실제로는 real 바이트로 풀리는데 가운데 목록은 declared 라고 적는다."""
    parts = parts_of()
    filler = b" " * (real - len(parts[SHEET]))
    parts[SHEET] = parts[SHEET].replace(b"</worksheet>", filler + b"</worksheet>")
    assert len(parts[SHEET]) == real
    data = bytearray(zip_bytes(parts))
    position = data.find(b"PK\x01\x02")
    patched = 0
    while position != -1:
        if int.from_bytes(data[position + 24 : position + 28], "little") == real:
            data[position + 24 : position + 28] = declared.to_bytes(4, "little")
            patched += 1
        position = data.find(b"PK\x01\x02", position + 4)
    assert patched == 1
    return bytes(data)


def test_an_entry_that_inflates_past_its_declared_size_is_refused_without_inflating_it_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """선언을 속인 항목: 읽개는 선언된 크기 + 1 바이트까지만 풀어 달라고 한다(끝까지 푼 뒤에 자르지 않는다)."""
    asked: list[int | None] = []
    returned: list[int] = []
    real_read = zipfile.ZipExtFile.read

    def recording_read(self: zipfile.ZipExtFile, n: int | None = -1) -> bytes:
        asked.append(n)
        data = real_read(self, n)
        returned.append(len(data))
        return data

    monkeypatch.setattr(zipfile.ZipExtFile, "read", recording_read)
    declared, real = 1_000, 3_000_000
    problem = refused(lying_zip(declared, real))
    assert (problem.kind, problem.where) == ("unreadable_entry", SHEET)
    assert asked and all(n is not None and n >= 0 for n in asked)  # 「끝까지」(-1·None)를 청하지 않는다
    assert max(returned) <= max(declared + 1, max(len(part) for part in parts_of().values()) + 1)
    # 정직한 zip 은 그대로 읽힌다. 청한 길이는 늘 선언 + 1 이다.
    asked.clear()
    honest = parts_of()
    assert isinstance(read_workbook(zip_bytes(honest)), Workbook)
    assert sorted(n for n in asked if n is not None) == sorted(len(part) + 1 for part in honest.values())


def test_an_entry_that_inflates_to_less_than_declared_is_refused() -> None:
    assert refused(lying_zip(3_000_100, 3_000_000)).kind == "unreadable_entry"


def test_two_sheets_with_one_name_or_one_part_are_refused() -> None:
    parts = xlsx_from_parts({"가": sheet_xml(ONE_CELL), "나": sheet_xml(ONE_CELL)})
    same_name = dict(parts)
    same_name[WORKBOOK] = parts[WORKBOOK].replace("나".encode(), "가".encode())
    assert refused(zip_bytes(same_name)).kind == "unexpected_xml"
    same_part = dict(parts)
    same_part[RELS] = parts[RELS].replace(b"sheet2.xml", b"sheet1.xml")
    assert refused(zip_bytes(same_part)).kind == "bad_relationship"
    # 상대 꼴과 절대 꼴이 같은 항목을 가리켜도 같은 항목이다(푼 뒤의 이름으로 견준다)
    relative_and_absolute = dict(parts)
    relative_and_absolute[RELS] = parts[RELS].replace(b'"worksheets/sheet2.xml"', b'"/xl/worksheets/sheet1.xml"')
    assert relative_and_absolute[RELS] != parts[RELS]
    problem = refused(zip_bytes(relative_and_absolute))
    assert (problem.kind, problem.where, problem.detail) == ("bad_relationship", RELS, "두 시트가 같은 항목을 가리킨다")


# ── 예외가 새지 않는다 ──────────────────────────────────────────────────────
# 예 수: 임의 바이트 300, zip 바이트의 한 자리 바꾸기 300, XML 항목의 한 자리 바꾸기 400.
# 설정: database=None(예시 DB 를 쓰지 않는다), deadline=None, derandomize=True(실행마다 같은 예시).

SMALL = Workbook(
    (
        Sheet(
            "가상",
            {
                "A1": text("가상 이름"),
                "B1": number("9.25"),
                "C1": FormulaCell("B1*9", SharedFormula(0, "C1", "C1:C2"), number("9.5")),
                "C2": FormulaCell(None, SharedFormula(0, "C1", "C1:C2"), TextCell("")),
            },
            ("A1:B1",),
            (Validation("list", "D1:D9", '"g,kg"', None),),
        ),
    ),
    (),
)
SMALL_PARTS = xlsx_parts(SMALL)
SMALL_ZIP = zip_bytes(SMALL_PARTS)
XML_PART_NAMES = sorted(SMALL_PARTS)


@settings(max_examples=300, deadline=None, derandomize=True, database=None)
@given(st.binary(max_size=2000))
def test_no_exception_leaks_for_arbitrary_bytes(data: bytes) -> None:
    assert isinstance(read_workbook(data), (Workbook, ReaderProblem))


@settings(max_examples=300, deadline=None, derandomize=True, database=None)
@given(st.integers(min_value=0, max_value=len(SMALL_ZIP) - 1), st.integers(min_value=0, max_value=255))
def test_no_exception_leaks_when_one_byte_of_a_real_zip_changes(position: int, value: int) -> None:
    data = bytearray(SMALL_ZIP)
    data[position] = value
    assert isinstance(read_workbook(bytes(data)), (Workbook, ReaderProblem))


@settings(max_examples=400, deadline=None, derandomize=True, database=None)
@given(st.sampled_from(XML_PART_NAMES), st.integers(min_value=0, max_value=10_000), st.binary(min_size=0, max_size=3))
def test_no_exception_leaks_when_one_spot_of_an_xml_part_changes(name: str, position: int, piece: bytes) -> None:
    """압축을 풀고 난 XML 이 망가진 경우(zip 의 CRC 는 맞다): 파서와 그 뒤의 읽기가 갈래로 답한다."""
    parts = dict(SMALL_PARTS)
    original = parts[name]
    spot = position % len(original)
    parts[name] = original[:spot] + piece + original[spot + 1 :]
    assert isinstance(read_workbook(zip_bytes(parts)), (Workbook, ReaderProblem))


def test_the_small_workbook_itself_reads_back() -> None:
    assert read_workbook(SMALL_ZIP) == SMALL
    assert DOC_REL_NS in SMALL_PARTS[WORKBOOK].decode()


# ── S12b-2: 병합 수 · XML 깊이 · 요소 수 ──


def test_more_merges_than_the_limit_are_refused_per_sheet(monkeypatch: pytest.MonkeyPatch) -> None:
    merges = '<mergeCells><mergeCell ref="A2:A3"/><mergeCell ref="A4:A5"/></mergeCells>'
    data = zip_bytes(xlsx_from_parts({"가": sheet_xml(ONE_CELL, merges), "나": sheet_xml(ONE_CELL, merges)}))
    monkeypatch.setattr(xlsx_reader, "MAX_MERGES", 2)
    assert isinstance(read_workbook(data), Workbook)  # 시트마다다 — 두 시트 합 넷이어도 지난다
    monkeypatch.setattr(xlsx_reader, "MAX_MERGES", 1)
    assert refused(data).kind == "too_many_merges"


def test_deep_xml_is_refused_while_building_the_tree() -> None:
    deep = sheet_xml(ONE_CELL, "<a>" * 1_000_000 + "</a>" * 1_000_000)
    found = refused(zip_bytes(xlsx_from_parts({"가": deep})))
    assert (found.kind, found.where) == ("xml_too_deep", SHEET)


def test_the_depth_limit_counts_what_is_open_not_what_has_been_seen(monkeypatch: pytest.MonkeyPatch) -> None:
    """뿌리 worksheet · sheetData · row · c · v 다섯이 가장 깊다. 닫힌 요소는 깊이에서 빠진다."""
    data = zip_bytes(parts_of('<row r="1"><c r="A1"><v>9</v></c><c r="B1"><v>9</v></c></row>'))
    monkeypatch.setattr(xlsx_reader, "MAX_XML_DEPTH", 5)
    assert isinstance(read_workbook(data), Workbook)
    monkeypatch.setattr(xlsx_reader, "MAX_XML_DEPTH", 4)
    assert refused(data).kind == "xml_too_deep"


def test_more_elements_than_the_limit_are_refused_per_entry() -> None:
    flat = sheet_xml(ONE_CELL, "<a/>" * (xlsx_reader.MAX_XML_ELEMENTS + 1))
    found = refused(zip_bytes(xlsx_from_parts({"가": flat})))
    assert (found.kind, found.where) == ("too_many_xml_elements", SHEET)


def test_the_element_limit_counts_each_entry_from_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    one = sheet_xml('<row r="1"><c r="A1"><v>9</v></c></row>')
    data = zip_bytes(xlsx_from_parts({"가": one, "나": one, "다": one}))
    monkeypatch.setattr(xlsx_reader, "MAX_XML_ELEMENTS", 9)  # workbook.xml 이 시트 셋이라 제일 크다
    assert isinstance(read_workbook(data), Workbook)
    monkeypatch.setattr(xlsx_reader, "MAX_XML_ELEMENTS", 4)
    assert refused(data).kind == "too_many_xml_elements"


def test_the_cell_limit_answers_before_the_element_limit() -> None:
    """칸 하나의 c·v·f 셋에 줄까지 들어도 요소 상한이 칸 상한보다 먼저 답하지 않는다(값의 근거)."""
    assert xlsx_reader.MAX_XML_ELEMENTS > xlsx_reader.MAX_CELLS * 4
