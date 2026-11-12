"""용어집 엑셀 읽개·양식(tools/glossary_xlsx.py — 밴드 TR3a §3-1-4·§3-1-5, 순수): 정상 파일은 짝 목록, 거절 갈래마다
kind·행 번호·해요체 글(칸 값 0), 공격 파일은 상한 안에서 unsafe_xlsx, 어떤 바이트도 예외 0. xlsx 는 전부 메모리에서
지은 지어낸 것이다(tests/tools/glossary_support.py)."""

import datetime as dt
import io
import time
import tracemalloc
import xml.parsers.expat
import zipfile
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Final

import pytest

from esgapi.translation.tests.tools import glossary_support as s
from esgapi.translation.tools import glossary_xlsx
from esgapi.translation.tools.glossary_xlsx import (
    MAX_PAIRS,
    MAX_SCANNED_ROWS,
    MAX_XML_DEPTH,
    MAX_XML_ELEMENTS,
    MAX_XML_SPAN,
    GlossaryRead,
    GlossaryRejected,
    read_glossary,
    template,
)

PAD = "docProps/pad.xml"
"""openpyxl 이 열지 않지만 이름이 .xml 이라 훑기 대상인 항목(경계 시험의 채움 자리)."""


def read(data: bytes) -> tuple[tuple[str, str], ...]:
    result = read_glossary(data)
    assert isinstance(result, GlossaryRead), result
    return result.pairs


def refused(data: bytes) -> GlossaryRejected:
    result = read_glossary(data)
    assert isinstance(result, GlossaryRejected), result
    return result


def base() -> bytes:
    return s.glossary([("가상설비", "Virtual Facility"), ("가상사업장", "Virtual Site")])


# ── 정상 ──


def test_rows_are_read_in_order_with_blank_rows_skipped_text_stripped_and_column_c_ignored() -> None:
    data = s.book(
        [
            ["  가상설비 ", " Virtual Facility  ", "C 열은 읽지 않는다"],
            [None, None],
            ["", "   "],
            ["가상사업장", "Virtual Site", 2030],
        ],
        header=(" 한국어 ", "영문 "),
    )
    assert read(data) == (("가상설비", "Virtual Facility"), ("가상사업장", "Virtual Site"))


def test_five_hundred_pairs_at_the_char_limits_are_read() -> None:
    pairs = s.synthetic_pairs(MAX_PAIRS, ko_chars=glossary_xlsx.MAX_KO_CHARS, en_chars=glossary_xlsx.MAX_EN_CHARS)
    assert read(s.glossary(pairs)) == tuple(pairs)


def test_only_the_first_sheet_is_read() -> None:
    assert read(s.book([["가상", "virtual"]], sheets=3)) == (("가상", "virtual"),)


def with_binary_parts(data: bytes) -> bytes:
    """Excel 이 흔히 싣는 바이너리 파트 셋(그림 PNG·프린터 설정·미리보기 그림)과 그 Default 꼴."""
    types = s.entries(data)[s.CONTENT_TYPES].replace(
        b"</Types>",
        b'<Default Extension="png" ContentType="image/png"/>'
        b'<Default Extension="bin" '
        b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.printerSettings"/>'
        b'<Default Extension="jpeg" ContentType="image/jpeg"/></Types>',
    )
    return s.rezip(
        data,
        replace={s.CONTENT_TYPES: types},
        add={
            "xl/media/image1.png": b"\x89PNG\r\n\x1a\n" + bytes(range(256)),
            "xl/printerSettings/printerSettings1.bin": b"\x00\x01virtual printer\xff\xfe",
            "docProps/thumbnail.jpeg": b"\xff\xd8\xff\xe0" + bytes(64),
        },
    )


def test_binary_parts_are_not_scanned_and_the_file_is_read() -> None:
    """훑기 대상은 이름 .xml·.rels ∪ xml 꼴뿐 — 바이너리 머리를 expat 에 넣으면 ExpatError 다(8b 의 짝)."""
    assert read(with_binary_parts(base())) == (("가상설비", "Virtual Facility"), ("가상사업장", "Virtual Site"))


def test_a_doctype_in_an_odd_name_overridden_as_xml_is_refused() -> None:
    """이름은 .bin 이지만 Override 로 xml 꼴인 파트 — 이름만 보면 놓친다(8 의 짝)."""
    types = s.entries(base())[s.CONTENT_TYPES].replace(
        b"</Types>", b'<Override PartName="/xl/a.bin" ContentType="application/xml"/></Types>'
    )
    data = s.rezip(
        base(), replace={s.CONTENT_TYPES: types}, add={"xl/a.bin": s.with_doctype(b'<?xml version="1.0"?><a/>')}
    )
    assert refused(data).kind == "unsafe_xlsx"
    honest = s.rezip(base(), replace={s.CONTENT_TYPES: types}, add={"xl/a.bin": b'<?xml version="1.0"?><a/>'})
    assert len(read(honest)) == 2


# ── 거절 갈래 ──


@pytest.mark.parametrize(
    ("data", "kind", "row", "message"),
    [
        (b"", "not_xlsx", None, "엑셀(.xlsx) 파일이 아니에요 — 용어집 양식에 채워 올려 주세요."),
        (b"{}", "not_xlsx", None, "엑셀(.xlsx) 파일이 아니에요 — 용어집 양식에 채워 올려 주세요."),
        (
            s.book([["가상", "virtual"]], header=("국문", "영문")),
            "bad_header",
            1,
            "1행의 머리가 「한국어」「영문」이 아니에요 — 양식을 그대로 써 주세요.",
        ),
        (
            s.book([], header=None),
            "bad_header",
            1,
            "1행의 머리가 「한국어」「영문」이 아니에요 — 양식을 그대로 써 주세요.",
        ),
        (s.book([["가상", "virtual"], [None, "only english"]]), "empty_cell", 3, "3행의 한국어 칸이 비어 있어요."),
        (s.book([["가상", "  "]]), "empty_cell", 2, "2행의 영문 칸이 비어 있어요."),
        (
            s.book([list(pair) for pair in s.synthetic_pairs(10)] + [["가상목표", 2030]]),
            "not_text",
            12,
            "12행의 영문 칸이 글자가 아니에요 — 셀 서식을 텍스트로 바꿔 주세요.",
        ),
        (
            s.book([[True, "virtual"]]),
            "not_text",
            2,
            "2행의 한국어 칸이 글자가 아니에요 — 셀 서식을 텍스트로 바꿔 주세요.",
        ),
        (s.book([["가" * 31, "virtual"]]), "too_long", 2, "2행의 한국어 칸이 너무 길어요 — 30자까지예요."),
        (s.book([["가상", "v" * 101]]), "too_long", 2, "2행의 영문 칸이 너무 길어요 — 100자까지예요."),
        (
            s.book([["가상", "virtual"], ["다른", "other"], [" 가상 ", "virtual again"]]),
            "duplicate_ko",
            4,
            "4행의 한국어가 2행과 같아요 — 한 번만 적어 주세요.",
        ),
        (s.book([]), "no_rows", None, "용어가 없어요 — 2행부터 「한국어」「영문」 짝을 적어 주세요."),
        (
            s.glossary(s.synthetic_pairs(MAX_PAIRS + 1)),
            "too_many_rows",
            502,
            "용어가 너무 많아요 — 파일 하나에 500개까지예요.",
        ),
    ],
    ids=[
        "empty",
        "json",
        "header",
        "empty_sheet",
        "ko_empty",
        "en_blank",
        "number",
        "bool",
        "ko_long",
        "en_long",
        "duplicate",
        "no_rows",
        "501",
    ],
)
def test_each_rejection_has_its_kind_row_and_sentence(data: bytes, kind: str, row: int | None, message: str) -> None:
    rejection = refused(data)
    assert (rejection.kind, rejection.row, rejection.message) == (kind, row, message)


def test_a_date_cell_is_not_text() -> None:
    import datetime

    assert refused(s.book([["가상", datetime.date(2030, 1, 1)]])).kind == "not_text"


def test_a_formula_without_a_stored_value_is_an_empty_cell() -> None:
    """data_only — openpyxl 이 지은 수식 칸에는 계산된 값이 없다(None)."""
    rejection = refused(s.book([["가상", '=A2&"x"']]))
    assert (rejection.kind, rejection.row) == ("empty_cell", 2)


def test_rejection_messages_never_carry_cell_values() -> None:
    secret = "가상기밀용어"
    for data in (
        s.book([[secret, "v" * 101]]),
        s.book([[secret, "x"], [secret, "y"]]),
        s.book([[secret, None]]),
        s.book([[secret, 7]]),
    ):
        assert secret not in refused(data).message


def test_too_large_bytes_are_refused_before_opening() -> None:
    rejection = refused(b"PK" + b"\0" * glossary_xlsx.MAX_BYTES)
    assert (rejection.kind, rejection.row) == ("too_large", None)
    assert rejection.message == "파일이 너무 커요 — 1MB 이하로 올려 주세요."


# ── 공격(상한 안에서 거절) ──


def test_not_a_zip_and_a_zip_without_content_types_are_not_xlsx() -> None:
    assert refused(b"PK\x03\x04 virtual").kind == "not_xlsx"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("a.txt", "virtual")
    assert refused(out.getvalue()).kind == "not_xlsx"


def test_too_many_entries_are_unsafe() -> None:
    extra = {f"docProps/x{i}.bin": b"" for i in range(glossary_xlsx.MAX_ENTRIES)}
    assert refused(s.rezip(base(), add=extra)).kind == "unsafe_xlsx"


def test_an_entry_or_the_declared_sum_over_the_limit_is_unsafe() -> None:
    one = s.rezip(base(), add={"xl/media/big.bin": b"\0" * (glossary_xlsx.MAX_ENTRY_BYTES + 1)})
    assert refused(one).kind == "unsafe_xlsx"
    under = b"\0" * (glossary_xlsx.MAX_ENTRY_BYTES - 1024)
    many = s.rezip(base(), add={"xl/media/a.bin": under, "xl/media/b.bin": under, "xl/media/c.bin": under})
    assert refused(many).kind == "unsafe_xlsx"


def central_directory_patched(data: bytes, name: bytes, offset: int, value: bytes) -> bytes:
    """가운데 목록에서 이름이 name 인 항목 머리의 offset 바이트를 value 로(test_docx_reader 꼴)."""
    out = bytearray(data)
    position = out.find(b"PK\x01\x02")
    while position != -1:
        length = int.from_bytes(out[position + 28 : position + 30], "little")
        if bytes(out[position + 46 : position + 46 + length]) == name:
            out[position + offset : position + offset + len(value)] = value
            return bytes(out)
        position = out.find(b"PK\x01\x02", position + 4)
    raise AssertionError(name)


def test_an_entry_lying_about_its_size_is_unsafe(monkeypatch: pytest.MonkeyPatch) -> None:
    """선언 10 바이트·실제 1 MiB: 선언 + 1 바이트까지만 청한다."""
    asked: list[int | None] = []
    real_read = zipfile.ZipExtFile.read

    def recording_read(self: zipfile.ZipExtFile, n: int | None = -1) -> bytes:
        asked.append(n)
        return real_read(self, n)

    data = s.rezip(base(), add={"xl/media/lie.bin": b"\0" * (1024 * 1024)})
    data = central_directory_patched(data, b"xl/media/lie.bin", 24, (10).to_bytes(4, "little"))
    monkeypatch.setattr(zipfile.ZipExtFile, "read", recording_read)
    assert refused(data).kind == "unsafe_xlsx"
    assert 11 in asked and None not in asked and -1 not in asked


def test_encrypted_or_odd_compression_entries_are_unsafe() -> None:
    assert refused(central_directory_patched(base(), s.SHEET.encode(), 8, b"\x01\x00")).kind == "unsafe_xlsx"
    assert refused(s.rezip(base(), compression=zipfile.ZIP_BZIP2)).kind == "unsafe_xlsx"
    assert len(read(s.rezip(base(), compression=zipfile.ZIP_STORED))) == 2


@pytest.mark.parametrize(
    "part", [s.SHEET, "xl/workbook.xml", "xl/styles.xml", "xl/_rels/workbook.xml.rels", "_rels/.rels", s.CONTENT_TYPES]
)
def test_a_doctype_in_any_part_openpyxl_opens_is_unsafe(part: str) -> None:
    """openpyxl 이 지은 파일에는 sharedStrings 가 없다(글은 inline) — 그 자리는 아래 엔티티 부풀리기 시험이 더한다."""
    entries = s.entries(base())
    assert refused(s.rezip(base(), replace={part: s.with_doctype(entries[part])})).kind == "unsafe_xlsx"


def test_a_utf16_doctype_is_caught_by_the_parser_not_a_byte_search() -> None:
    text = s.with_doctype(s.entries(base())[s.SHEET]).decode().replace('encoding="UTF-8"', 'encoding="UTF-16"')
    assert refused(s.rezip(base(), replace={s.SHEET: text.encode("utf-16")})).kind == "unsafe_xlsx"


def test_entity_laughs_are_unsafe_before_openpyxl() -> None:
    assert refused(s.rezip(base(), replace={s.STRINGS: s.laughs(9)})).kind == "unsafe_xlsx"


def test_an_unknown_xml_encoding_or_broken_xml_is_unsafe() -> None:
    odd = b'<?xml version="1.0" encoding="x-virtual"?><worksheet/>'
    assert refused(s.rezip(base(), replace={s.SHEET: odd})).kind == "unsafe_xlsx"
    assert refused(s.rezip(base(), replace={s.SHEET: b"<worksheet>"})).kind == "unsafe_xlsx"
    assert refused(s.rezip(base(), replace={s.SHEET: b""})).kind == "not_xlsx"  # XML 로 보이지 않음 → openpyxl 이 거절


def elements_of(data: bytes) -> int:
    """훑기 대상(이 시험의 파일은 이름 .xml·.rels 뿐)의 예산 합 — 요소 하나 + 그 속성 수(이름공간을 풀지 않는
    expat 이라 xmlns 선언도 속성으로 센다 = 도구의 이름공간 선언 셈과 같은 값) + 주석·처리 지시 하나씩."""
    total = 0
    for name, content in s.entries(data).items():
        if name.endswith((".xml", ".rels")):
            parser = xml.parsers.expat.ParserCreate()
            count = [0]

            def on_start(tag: str, attributes: Mapping[str, str], count: list[int] = count) -> None:
                count[0] += 1 + len(attributes)

            def on_node(*_: object, count: list[int] = count) -> None:
                count[0] += 1

            parser.StartElementHandler = on_start
            parser.CommentHandler = on_node
            parser.ProcessingInstructionHandler = on_node
            parser.Parse(content, True)
            total += count[0]
    return total


def padded(elements: int) -> bytes:
    """openpyxl 이 열지 않는 .xml 항목에 빈 요소를 채워 파일 전체 요소 수를 꼭 elements 로."""
    plain = base()
    children = elements - elements_of(plain) - 1
    data = s.rezip(plain, add={PAD: b"<p>" + b"<x/>" * children + b"</p>"})
    assert elements_of(data) == elements
    return data


def nested(depth: int) -> bytes:
    return s.rezip(base(), add={PAD: b"<x>" * depth + b"</x>" * depth})


def test_the_element_sum_of_the_whole_file_is_capped() -> None:
    assert len(read(padded(MAX_XML_ELEMENTS))) == 2
    assert refused(padded(MAX_XML_ELEMENTS + 1)).kind == "unsafe_xlsx"
    assert MAX_XML_ELEMENTS == 100_000


def test_the_nesting_depth_is_capped() -> None:
    assert len(read(nested(MAX_XML_DEPTH))) == 2
    assert refused(nested(MAX_XML_DEPTH + 1)).kind == "unsafe_xlsx"
    assert MAX_XML_DEPTH == 64


def test_a_million_deep_sheet_is_refused_fast() -> None:
    """★B: 뿌리에서 멈추는 훑기로는 openpyxl 에 가 2.4초·RSS +592MB 였던 파일(12KB)."""
    data = s.rezip(base(), replace={s.SHEET: s.deep_sheet(1_000_000)})
    started = time.perf_counter()
    assert refused(data).kind == "unsafe_xlsx"
    assert time.perf_counter() - started < 2.0


def test_a_cell_far_down_stops_at_the_scanned_row_limit() -> None:
    """read_only 는 빈 행 번호마다 빈 행을 내준다 — 1,048,576행 칸 하나도 MAX_SCANNED_ROWS 에서 멈춘다."""
    rejection = refused(s.rezip(base(), replace={s.SHEET: s.far_row_sheet(1_048_576)}))
    assert (rejection.kind, rejection.row) == ("too_many_rows", None)


def test_ten_thousand_and_one_blank_rows_are_refused_and_ten_thousand_are_read() -> None:
    assert refused(s.rezip(base(), replace={s.SHEET: s.far_row_sheet(MAX_SCANNED_ROWS + 1)})).kind == "too_many_rows"
    near = refused(s.rezip(base(), replace={s.SHEET: s.far_row_sheet(MAX_SCANNED_ROWS)}))
    assert (near.kind, near.row) == ("empty_cell", MAX_SCANNED_ROWS)  # 10,000행째까지 훑었다


def test_the_workbook_is_closed_even_when_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []
    real = glossary_xlsx.load_workbook

    def tracking(*args: object, **kwargs: object) -> object:
        workbook = real(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        original = workbook.close

        def close() -> None:
            closed.append(True)
            original()

        workbook.close = close  # pyright: ignore[reportAttributeAccessIssue]
        return workbook

    monkeypatch.setattr(glossary_xlsx, "load_workbook", tracking)
    refused(s.book([["가상", None]]))
    read(base())
    assert closed == [True, True]


def test_a_memory_error_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def out_of_memory(*_: object, **__: object) -> object:
        raise MemoryError

    monkeypatch.setattr(glossary_xlsx, "load_workbook", out_of_memory)
    with pytest.raises(MemoryError):
        read_glossary(base())


def test_no_corrupted_byte_raises() -> None:
    """어떤 바이트를 받아도 예외가 아니라 갈래다(test_docx_reader 꼴 — 자리마다 비트를 뒤집는다)."""
    data = with_binary_parts(base())
    for position in range(0, len(data), max(1, len(data) // 300)):
        broken = bytearray(data)
        broken[position] ^= 1 << (position % 8)
        assert isinstance(read_glossary(bytes(broken)), GlossaryRead | GlossaryRejected)
    assert isinstance(read_glossary(data[: len(data) // 2]), GlossaryRejected)


# ── 양식 ──


def test_the_template_is_the_same_bytes_every_time_and_reads_as_no_rows() -> None:
    first = template()
    time.sleep(1.1)  # zip 항목 시각은 2초 단위 — 시각을 고정하지 않으면 다음 판에서 바뀐다
    second = template()
    assert first == second
    rejection = refused(first)
    assert (rejection.kind, rejection.row) == ("no_rows", None)


def test_the_template_has_one_sheet_with_the_two_headers() -> None:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(template()))
    (sheet,) = workbook.worksheets
    assert sheet.title == "용어집"
    assert [c.value for c in sheet[1]] == ["한국어", "영문"]
    assert sheet.max_row == 1
    assert sheet.column_dimensions["A"].number_format == sheet.column_dimensions["B"].number_format == "@"
    with zipfile.ZipFile(io.BytesIO(template())) as archive:
        assert {i.date_time for i in archive.infolist()} == {glossary_xlsx.TEMPLATE_DATE}
        assert b"1980-01-01T00:00:00Z" in archive.read("docProps/core.xml")


def test_a_filled_template_is_read() -> None:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(template()))
    workbook.active.append(["가상설비", "Virtual Facility"])  # pyright: ignore[reportOptionalMemberAccess]
    out = io.BytesIO()
    workbook.save(out)
    assert read(out.getvalue()) == (("가상설비", "Virtual Facility"),)


# ── 검증 B1: openpyxl 은 파트를 관계의 Target 으로 연다 ──

SHEET_DAT = "xl/worksheets/sheet1.dat"


def test_a_sheet_moved_to_an_odd_name_without_override_is_still_read() -> None:
    """분모: openpyxl 은 이름·꼴이 xml 이 아닌 시트도 워크북 rels 의 Target 으로 연다(그래서 훑어야 한다)."""
    assert len(read(s.moved(base(), s.SHEET, SHEET_DAT))) == 2


def test_a_doctype_or_a_deep_sheet_moved_to_an_odd_name_is_unsafe() -> None:
    sheet = s.entries(base())[s.SHEET]
    assert refused(s.moved(base(), s.SHEET, SHEET_DAT, content=s.with_doctype(sheet))).kind == "unsafe_xlsx"
    started = time.perf_counter()
    assert refused(s.moved(base(), s.SHEET, SHEET_DAT, content=s.deep_sheet(1_000_000))).kind == "unsafe_xlsx"
    assert time.perf_counter() - started < 2.0


def test_styles_moved_to_an_odd_name_with_a_doctype_is_unsafe() -> None:
    styles = s.entries(base())["xl/styles.xml"]
    data = s.moved(base(), "xl/styles.xml", "xl/styles.dat", content=s.with_doctype(styles))
    assert refused(data).kind == "unsafe_xlsx"


def test_a_sheet_whose_relationship_type_lies_as_an_image_is_still_scanned() -> None:
    """짝(감독 63): Type 만 image 로 속이면 바이너리 관계로 빠질 듯하지만 openpyxl 은 시트를 r:id 로 찾고 Type 을 보지
    않아 그대로 연다(실측 — 분모). 워크북 rels 는 Type 과 상관없이 훑으므로 공격 시트는 거절, 2초 안."""
    sheet = s.entries(base())[s.SHEET]
    assert len(read(s.moved(base(), s.SHEET, SHEET_DAT, rel_type=s.IMAGE_TYPE))) == 2
    lie = s.moved(base(), s.SHEET, SHEET_DAT, content=s.with_doctype(sheet), rel_type=s.IMAGE_TYPE)
    assert refused(lie).kind == "unsafe_xlsx"
    started = time.perf_counter()
    deep = s.moved(base(), s.SHEET, SHEET_DAT, content=s.deep_sheet(1_000_000), rel_type=s.IMAGE_TYPE)
    assert refused(deep).kind == "unsafe_xlsx"
    assert time.perf_counter() - started < 2.0


def test_an_image_related_from_a_sheet_is_not_scanned_and_the_file_is_read() -> None:
    """시트 rels 아래의 그림(바이너리 관계 Type)은 훑지 않는다 — 그림 든 정상 xlsx 는 그대로 받는다."""
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{s.IMAGE_TYPE}" Target="../media/image1.png"/></Relationships>'
    ).encode()
    data = s.rezip(
        with_binary_parts(base()),
        add={"xl/worksheets/_rels/sheet1.xml.rels": rels},
    )
    assert len(read(data)) == 2


@pytest.mark.parametrize(
    "head",
    [b"", b"\xef\xbb\xbf", b" \t\r\n", b"\xef\xbb\xbf\n  "],
    ids=["plain", "utf8_bom", "spaces", "bom_and_spaces"],
)
def test_any_part_whose_bytes_look_like_xml_is_scanned_whatever_its_name(head: bytes) -> None:
    """감독 63 처분(검증 B1·B2 뒤): 고르는 기준은 내용이다 — 이름·꼴·관계가 없어도(뿌리의 evil.dat) XML 로 보이면
    훑는다. 앞 공백 뒤의 XML 선언은 expat 이 받지 않으므로(선언은 맨 앞에만) 짝은 선언 없는 글로 잰다."""
    bad = head + s.with_doctype(b"<a/>")
    assert refused(s.rezip(base(), add={"evil.dat": bad})).kind == "unsafe_xlsx"
    assert len(read(s.rezip(base(), add={"evil.dat": head + b"<a/>"}))) == 2


UTF16_CODECS: Final = ("utf-16", "utf-16-le", "utf-16-be")
"""BOM 있음(FF FE) · BOM 없는 LE(`<\\x00`) · BOM 없는 BE(`\\x00<`) — _looks_like_xml 의 UTF-16 갈래 셋."""


@pytest.mark.parametrize("codec", UTF16_CODECS, ids=["bom", "le_no_bom", "be_no_bom"])
def test_a_utf16_part_with_a_doctype_or_deep_nesting_is_unsafe(codec: str) -> None:
    """UTF-16(BOM · BOM 없는 LE `<\\x00` · BOM 없는 BE `\\x00<`)도 XML 로 보고 expat 이 읽는다. 이름이 .dat 여도."""

    def utf16(text: str) -> bytes:
        return text.encode(codec)

    honest = s.entries(base())[s.SHEET].decode().replace('encoding="UTF-8"', 'encoding="UTF-16"')
    assert len(read(s.rezip(base(), replace={s.SHEET: utf16(honest)}))) == 2  # 짝: 정직한 UTF-16 시트는 읽힌다
    doctype = s.with_doctype(b'<?xml version="1.0" encoding="UTF-16"?><a/>').decode()
    assert refused(s.rezip(base(), add={"evil.dat": utf16(doctype)})).kind == "unsafe_xlsx"
    deep = s.deep_sheet(1_000_000).decode().replace('encoding="UTF-8"', 'encoding="UTF-16"')
    sheet = s.moved(base(), s.SHEET, SHEET_DAT, content=utf16(deep))
    started = time.perf_counter()
    assert refused(sheet).kind == "unsafe_xlsx"
    assert time.perf_counter() - started < 2.0


@pytest.mark.parametrize("codec", UTF16_CODECS, ids=["bom", "le_no_bom", "be_no_bom"])
def test_the_nesting_depth_is_capped_in_utf16_under_the_entry_size_limit(codec: str) -> None:
    """검증 R6: 100만 겹 UTF-16 은 항목 크기 상한(8MiB)에서 먼저 거절돼 깊이를 재지 않는다 — 상한 밑 크기로 깊이만
    넘는 판. 경계 짝(64 받음 · 65 거절)과 시트 자리의 100겹."""

    def pad(depth: int) -> bytes:
        data = s.rezip(base(), add={PAD: ("<x>" * depth + "</x>" * depth).encode(codec)})
        assert len(s.entries(data)[PAD]) < 8 * 1024 * 1024
        return data

    assert len(read(pad(MAX_XML_DEPTH))) == 2
    assert refused(pad(MAX_XML_DEPTH + 1)).kind == "unsafe_xlsx"
    deep = s.deep_sheet(100).decode().replace('encoding="UTF-8"', 'encoding="UTF-16"').encode(codec)
    assert refused(s.moved(base(), s.SHEET, SHEET_DAT, content=deep)).kind == "unsafe_xlsx"


# ── 가지 리뷰(10-23): 부록 F 표·앞 공백 뒤 `<` 다섯 꼴·속성 예산·표지 간격 ──

WORKBOOK = "xl/workbook.xml"


def ucs4(text: str, codec: str, *, bom: bytes = b"") -> bytes:
    return bom + text.encode(codec)


@pytest.mark.parametrize(
    ("codec", "bom"),
    [("utf-32-be", b""), ("utf-32-le", b""), ("utf-32-be", b"\x00\x00\xfe\xff"), ("utf-32-le", b"\xff\xfe\x00\x00")],
    ids=["be", "le", "be_bom", "le_bom"],
)
def test_a_ucs4_workbook_with_a_doctype_is_unsafe(codec: str, bom: bytes) -> None:
    """lxml 은 UCS-4 를 부록 F 로 읽어 DOCTYPE 째 연다(가지 리뷰 재현 — 고치기 전 BE 둘은 짝 2 읽음). 정직한 UCS-4 도
    expat 이 못 읽어 거절된다(용어집 양식이 UCS-4 일 까닭이 없다)."""
    workbook = s.entries(base())[WORKBOOK].decode()
    bad = s.rezip(base(), replace={WORKBOOK: ucs4(s.with_doctype(workbook.encode()).decode(), codec, bom=bom)})
    assert refused(bad).kind == "unsafe_xlsx"
    assert refused(s.rezip(base(), replace={WORKBOOK: ucs4(workbook, codec, bom=bom)})).kind == "unsafe_xlsx"
    assert len(read(base())) == 2  # 짝: 정상 파일은 읽힌다


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"], ids=["le", "be"])
def test_a_bomless_utf16_sheet_led_by_spaces_is_scanned(codec: str) -> None:
    """부록 F 표는 첫 네 바이트만 본다 — BOM 없는 UTF-16 앞의 공백(`0A 00 3C 00`)은 표에 없지만 expat(worksheet 의
    iterparse)은 DOCTYPE 째 읽는다(러너 재현 — 고치기 전 짝 2 읽음). 정직한 판은 읽힌다."""
    sheet = s.entries(base())[s.SHEET].decode()
    assert (
        refused(
            s.rezip(base(), replace={s.SHEET: ("\n " + s.with_doctype(sheet.encode()).decode()).encode(codec)})
        ).kind
        == "unsafe_xlsx"
    )
    assert len(read(s.rezip(base(), replace={s.SHEET: ("\n\t " + sheet).encode(codec)}))) == 2


def test_an_ebcdic_part_is_unsafe() -> None:
    """부록 F 의 EBCDIC 머리(`4C 6F A7 94` = `<?xm`) — expat·lxml 모두 못 읽지만 XML 로 보고 거절한다."""
    part = '<?xml version="1.0" encoding="cp500"?><a/>'.encode("cp500")
    assert part.startswith(b"\x4c\x6f\xa7\x94")
    assert refused(s.rezip(base(), add={"evil.dat": part})).kind == "unsafe_xlsx"


def with_attributes(elements: int, per: int) -> bytes:
    """openpyxl 이 열지 않는 .xml 항목에 속성 per 개짜리 빈 요소 elements 개."""
    attrs = b"".join(b' a%d=""' % i for i in range(per))
    return s.rezip(base(), add={PAD: b"<p>" + (b"<x" + attrs + b"/>") * elements + b"</p>"})


def test_attributes_count_in_the_element_budget() -> None:
    """가지 리뷰 처분: 속성 하나를 요소 합에 1로 더한다(같은 예산). 요소만으로는 예산 안인 파일이 속성으로 넘는다."""
    room = MAX_XML_ELEMENTS - elements_of(base()) - 1  # <p> 하나
    fits = with_attributes(room // 3, 2)
    assert elements_of(fits) <= MAX_XML_ELEMENTS
    assert len(read(fits)) == 2
    over = with_attributes(room // 3 + 1, 2)
    assert elements_of(over) > MAX_XML_ELEMENTS
    assert refused(over).kind == "unsafe_xlsx"
    assert room // 3 + 1 < MAX_XML_ELEMENTS // 2  # 분모: 요소 수만으로는 예산의 절반도 안 된다


LARGEST_ATTRIBUTE_LIST = 466_139
"""시각 고정 표본에서 압축해 MAX_BYTES(1MiB) 안에 드는 가장 많은 속성(이름 a0…, 러너 실측 — 풀면 5.0MB). 표지 간격 상한
없이 handler 에서 세면 이 사전만으로 0.66초·tracemalloc 106MB·RSS +180MB 였다."""


def huge_attribute_list(attributes: int) -> bytes:
    attrs = b"".join(b' a%d=""' % i for i in range(attributes))
    return s.rezip(base(), add={PAD: b"<x" + attrs + b"/>"})


def test_one_element_with_the_largest_attribute_list_is_refused_before_its_dict_is_built() -> None:
    """가지 리뷰 처분(속성 셈) + 표지 간격 상한: 사전을 짓기 전에 거절해 메모리가 늘지 않는다."""
    data = huge_attribute_list(LARGEST_ATTRIBUTE_LIST)
    assert len(data) <= 1024 * 1024  # 분모: 바이트 상한 안 — 훑기까지 간다
    tracemalloc.start()
    started = time.perf_counter()
    try:
        assert refused(data).kind == "unsafe_xlsx"
        elapsed = time.perf_counter() - started
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert elapsed < 2.0, elapsed
    assert peak < 60 * 1024 * 1024, peak  # 사전을 지었다면 100MB 를 넘는다


def test_one_attribute_more_than_the_largest_list_is_over_the_byte_limit() -> None:
    """LARGEST_ATTRIBUTE_LIST 가 정말 가장 큰 값이다(낡으면 위 시험이 경계를 재지 않는다)."""
    assert len(huge_attribute_list(LARGEST_ATTRIBUTE_LIST + 1)) > 1024 * 1024


def _built_under(start: dt.datetime, tick: int) -> tuple[bytes, int, int]:
    """벽시계를 갈고 지은 표본 · 가장 큰 속성 표본의 크기 · openpyxl 이 시계를 부른 수. 부를 때마다 tick 초씩 간다."""
    calls = 0

    def now(tz: object = None) -> dt.datetime:
        nonlocal calls
        calls += 1
        return start + dt.timedelta(seconds=tick * calls)

    def wall() -> float:
        return start.timestamp()

    clock = SimpleNamespace(datetime=SimpleNamespace(now=now), timezone=dt.timezone)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("openpyxl.packaging.core.datetime", clock)
        patch.setattr("openpyxl.writer.excel.datetime", clock)
        patch.setattr(time, "time", wall)  # zipfile 의 `writestr(이름, …)` 이 머리에 적는 시각
        return base(), len(huge_attribute_list(LARGEST_ATTRIBUTE_LIST)), calls


def test_the_sample_is_the_same_whatever_the_wall_clock_says() -> None:
    """같은 초 둘(다른 날)과 created≠modified(openpyxl 이 부를 때마다 1초씩 — 부하 아래 초가 넘어간 꼴). 고정 전에는
    이 셋의 크기가 달라 표본이 1MiB 를 몇 바이트 넘었다(MARC-ISSUE-420)."""
    built = [
        _built_under(dt.datetime(2031, 3, 4, 5, 6, 7), 0),
        _built_under(dt.datetime(2034, 9, 10, 11, 12, 13), 0),
        _built_under(dt.datetime(2032, 12, 31, 23, 59, 58), 1),
    ]
    assert len({data for data, _, _ in built}) == 1
    assert len({size for _, size, _ in built}) == 1
    assert all(calls >= 2 for _, _, calls in built)  # 분모: openpyxl 이 정말 이 시계를 본다


def test_a_million_attributes_never_reach_the_parser() -> None:
    """속성 100만 개(가지 리뷰의 예)는 압축해도 1MiB 를 넘어 바이트 상한에서 먼저 멈춘다."""
    assert refused(huge_attribute_list(1_000_000)).kind == "too_large"


def test_a_tag_longer_than_the_span_is_unsafe_and_a_shorter_one_and_long_text_are_read() -> None:
    """표지 간격 상한의 경계: 속성 값 하나가 MAX_XML_SPAN 을 넘는 표지는 거절, 그 절반은 받음. 긴 글은 expat 이 조각으로
    알려 주므로 상한의 두 배여도 받는다(칸 글이 걸리지 않는다)."""
    long_tag = s.rezip(base(), add={PAD: b'<x a="' + b"v" * (MAX_XML_SPAN + 1) + b'"/>'})
    assert refused(long_tag).kind == "unsafe_xlsx"
    half = s.rezip(base(), add={PAD: b'<x a="' + b"v" * (MAX_XML_SPAN // 2) + b'"/>'})
    assert len(read(half)) == 2
    text = s.rezip(base(), add={PAD: b"<p>" + "가".encode() * (MAX_XML_SPAN * 2 // 3) + b"</p>"})
    assert len(read(text)) == 2


NODE_UNITS = {"comment": b"<!---->", "pi": b"<?a?>"}


def padded_nodes(unit: bytes, count: int, *, newline_every: int = 512 * 1024) -> bytes:
    """[Content_Types].xml 의 뿌리 끝 앞에 주석·처리 지시 count 개 — 가지 리뷰 재현 꼴(512KiB 마다 줄바꿈이라 표지 간격
    상한을 비껴간다)."""
    types = s.entries(base())[s.CONTENT_TYPES]
    at = types.rindex(b"</")
    per = newline_every // len(unit)
    body = b"\n".join(unit * min(per, count - i) for i in range(0, count, per))
    return s.rezip(base(), replace={s.CONTENT_TYPES: types[:at] + body + types[at:]})


@pytest.mark.parametrize("kind", sorted(NODE_UNITS))
def test_a_flood_of_comments_or_processing_instructions_is_unsafe(kind: str) -> None:
    """가지 리뷰(10-23): 주석·처리 지시는 lxml 이 노드로 짓는다 — 28KB 업로드가 처리 지시 320만 개·RSS +220MB(주석
    +179MB) 였고 결과는 no_rows 였다. 둘 다 요소 예산에 1씩 세어 거절한다."""
    data = padded_nodes(NODE_UNITS[kind], 1_400_000)
    assert len(data) < 64 * 1024  # 분모: 작은 업로드
    tracemalloc.start()
    try:
        assert refused(data).kind == "unsafe_xlsx"
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 60 * 1024 * 1024, peak


@pytest.mark.parametrize("kind", sorted(NODE_UNITS))
def test_comments_and_processing_instructions_count_in_the_element_budget(kind: str) -> None:
    room = MAX_XML_ELEMENTS - elements_of(base())
    fits = padded_nodes(NODE_UNITS[kind], room)
    assert elements_of(fits) == MAX_XML_ELEMENTS
    assert len(read(fits)) == 2
    assert refused(padded_nodes(NODE_UNITS[kind], room + 1)).kind == "unsafe_xlsx"


def test_a_template_with_a_few_comments_and_processing_instructions_is_read() -> None:
    """정상: 손으로 단 주석·처리 지시 몇 개는 받는다."""
    items = s.entries(s.glossary([("가상설비", "Virtual Facility")]))
    sheet = items[s.SHEET]
    at = sheet.index(b">") + 1
    note = '<!-- 가상 메모 --><?mso-application progid="Excel.Sheet"?>'.encode()
    noted = sheet[:at] + note + sheet[at:]
    assert read(s.rezip(s.glossary([("가상설비", "Virtual Facility")]), replace={s.SHEET: noted})) == (
        ("가상설비", "Virtual Facility"),
    )


def test_the_span_of_the_last_short_chunk_is_measured_to_the_end_of_the_data() -> None:
    """사소(가지 리뷰): 마지막 조각은 짧다 — 먹인 끝을 조각 크기로 올려 세면 상한 안의 간격을 넘었다고 본다. 마지막
    이벤트(자리 4 의 주석)에서 끝까지가 MAX_XML_SPAN − 2 인 항목(길이는 상한 + 2)은 받고, 끝을 MAX_XML_SPAN 너머로
    늘리면 거절."""
    head = b"<a/><!---->"
    inside = s.rezip(base(), add={PAD: head + b" " * (MAX_XML_SPAN + 2 - len(head))})
    assert len(read(inside)) == 2
    outside = s.rezip(base(), add={PAD: head + b" " * (MAX_XML_SPAN + 5)})
    assert refused(outside).kind == "unsafe_xlsx"


def test_an_external_target_named_part_is_scanned() -> None:
    """검증 B2: 시트 관계를 TargetMode External·Target="evil.dat" 로 바꾸고 뿌리에 evil.dat 를 두면 openpyxl 은 그
    이름으로 연다 — 내용으로 고르므로 이미 훑었다."""
    entries = s.entries(base())
    rels = entries[s.WORKBOOK_RELS].replace(
        b'Target="/xl/worksheets/sheet1.xml"', b'Target="evil.dat" TargetMode="External"'
    )
    types = entries[s.CONTENT_TYPES].replace(
        b'<Override PartName="/xl/worksheets/sheet1.xml" '
        b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>',
        b"",
    )
    for evil in (s.with_doctype(entries[s.SHEET]), s.deep_sheet(1_000_000)):
        items = {**entries, s.WORKBOOK_RELS: rels, s.CONTENT_TYPES: types, "evil.dat": evil}
        del items[s.SHEET]
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, part in items.items():
                archive.writestr(name, part)
        started = time.perf_counter()
        assert refused(out.getvalue()).kind == "unsafe_xlsx"
        assert time.perf_counter() - started < 2.0


def test_moved_shared_strings_and_workbook_with_a_doctype_are_unsafe() -> None:
    """검증 p3 원판의 나머지: sharedStrings·워크북을 .dat 로 옮겨도 내용으로 훑는다."""
    entries = s.entries(base())
    workbook = s.rezip(base(), replace={"xl/workbook.xml": s.with_doctype(entries["xl/workbook.xml"])})
    assert refused(workbook).kind == "unsafe_xlsx"
    strings = s.rezip(base(), add={"xl/sharedStrings.dat": s.laughs(9)})
    assert refused(strings).kind == "unsafe_xlsx"


def test_a_sheet_with_an_external_url_hyperlink_is_read() -> None:
    """External 의 보통 꼴(URL 하이퍼링크)은 zip 항목이 아니다 — 정상 파일은 그대로."""
    rels = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
        b'Target="https://example.invalid/virtual" TargetMode="External"/></Relationships>'
    )
    assert len(read(s.rezip(base(), add={"xl/worksheets/_rels/sheet1.xml.rels": rels}))) == 2


# ── 밴드 TRS2(MARC-ISSUE-409 의 영문번역 몫) — 시험 빈틈 둘. 둘 다 openpyxl 에 닿기 전에 거절한다 ──


def openpyxl_calls(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """load_workbook 부름을 센다(던지는 대역은 읽개가 not_xlsx 로 삼킨다 — _WORKBOOK_ERRORS 에 AssertionError)."""
    calls: list[object] = []
    real = glossary_xlsx.load_workbook

    def counting(*args: object, **kwargs: object) -> object:
        calls.append(args)
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(glossary_xlsx, "load_workbook", counting)
    return calls


def test_two_entries_with_the_same_name_are_unsafe(monkeypatch: pytest.MonkeyPatch) -> None:
    """같은 이름이 둘이면 zipfile 은 조용히 뒤의 것을 준다 — 무엇을 읽었는지 말할 수 없으므로 거절."""
    out = io.BytesIO()
    with pytest.warns(UserWarning, match="Duplicate name"), zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in s.entries(base()).items():
            archive.writestr(name, content)
        archive.writestr(s.SHEET, s.entries(s.glossary([("가상둘째", "Virtual Second")]))[s.SHEET])
    calls = openpyxl_calls(monkeypatch)
    assert refused(out.getvalue()).kind == "unsafe_xlsx"
    assert calls == []


@pytest.mark.parametrize(
    "root",
    [
        b'<Typez xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',  # 이름이 다름
        b'<Types xmlns="urn:virtual:not-content-types"/>',  # 이름 공간이 다름
        b"<Types/>",  # 이름 공간 없음
    ],
)
def test_a_content_types_whose_root_is_not_types_is_not_xlsx(root: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    data = s.rezip(base(), replace={s.CONTENT_TYPES: b'<?xml version="1.0" encoding="UTF-8"?>' + root})
    calls = openpyxl_calls(monkeypatch)
    assert refused(data).kind == "not_xlsx"
    assert calls == []
