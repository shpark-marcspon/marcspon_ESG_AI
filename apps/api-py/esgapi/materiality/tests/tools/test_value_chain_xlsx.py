"""가치사슬 엑셀 읽개(tools/value_chain_xlsx.py — IRW2 §2-1, 순수): 정상 파일은 행 목록, 거절 갈래마다 kind·데이터 행
번호·칸·해요체 글(칸 값 0), 공격 파일은 상한 안에서 unsafe_xlsx, 어떤 바이트도 예외 0, 마크스폰 템플릿 꼴(시트 이름·머리
찾기·병합·물려받기·건너뜀 — 발주서 Q4). xlsx 는 전부 메모리에서 지은 지어낸 것이다(tests/tools/value_chain_support.py).

★ 방어 시험은 translation/tests/tools/test_glossary_xlsx.py(밴드 TR3a)를 옮겨 적은 것이다(양식 시험 셋 빼고 전부 —
대응표는 band-reports/IRW2.md). 바꾼 것은 지은 파일(열 다섯)·읽은 값의 꼴·거절 갈래 이름뿐이다."""

import io
import time
import tracemalloc
import xml.parsers.expat
import zipfile
from collections.abc import Generator, Mapping
from typing import Any, Final

import pytest

from esgapi.materiality.tests.tools import value_chain_support as s
from esgapi.materiality.tools import value_chain_xlsx
from esgapi.materiality.tools.value_chain_xlsx import (
    MAX_DATA_ROWS,
    MAX_MERGES,
    MAX_SCANNED_ROWS,
    MAX_XML_DEPTH,
    MAX_XML_ELEMENTS,
    MAX_XML_SPAN,
    ValueChainRead,
    ValueChainRejected,
    read_value_chain,
)

PAD = "docProps/pad.xml"
"""openpyxl 이 열지 않지만 이름이 .xml 이라 훑기 대상인 항목(경계 시험의 채움 자리)."""

Row = tuple[str, str, str, str, str]
FIRST: Final[Row] = ("가상부문", "가상 시공 사업", "업스트림", "가상협력사", "자재 조달")
SECOND: Final[Row] = ("가상부문둘", "가상 유지보수 사업", "다운스트림", "가상고객", "점검")
NOT_XLSX: Final = "엑셀(.xlsx) 파일이 아니에요 — 가치사슬 표가 든 엑셀 파일을 올려 주세요."
BAD_HEADER: Final = (
    "열 이름 「사업 부문」「사업 내용」「밸류체인」「이해관계자」「관련 비즈니스 활동」을 차례대로 찾지 못했어요."
)


def read(data: bytes) -> tuple[Row, ...]:
    result = read_value_chain(data)
    assert isinstance(result, ValueChainRead), result
    return result.rows


def refused(data: bytes) -> ValueChainRejected:
    result = read_value_chain(data)
    assert isinstance(result, ValueChainRejected), result
    return result


def base() -> bytes:
    return s.table([FIRST, SECOND])


def rows_given(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """value_chain_xlsx._rows 가 내준 행 수(1행부터 빈 행 포함 — 곧 마지막으로 내준 행의 엑셀 번호)를 세는 감싸개(진짜를
    그대로 부른다). 벽시계 대신 일의 양으로 「MAX_SCANNED_ROWS 너머를 읽지 않음」을 잰다(IRS4 — DV8 꼴)."""
    given = [0]
    real = value_chain_xlsx._rows  # pyright: ignore[reportPrivateUsage]

    def counted(data: bytes, cut: list[int]) -> Generator[tuple[object, ...]]:
        rows = real(data, cut)
        try:
            for row in rows:
                given[0] += 1
                yield row
        finally:
            rows.close()

    monkeypatch.setattr(value_chain_xlsx, "_rows", counted)
    return given


def blanks_checked(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """value_chain_xlsx._blank 를 부른 횟수(병합 채우기 `_filled` 가 칸마다 한 번 · 표 읽기 `_table` 이 행마다 C~E 를
    짧게)를 세는 감싸개(진짜를 그대로 부른다). 「한 행의 일은 열 수 안」을 벽시계 대신 잰다(IRS4)."""
    checked = [0]
    real = value_chain_xlsx._blank  # pyright: ignore[reportPrivateUsage]

    def counted(value: object) -> bool:
        checked[0] += 1
        return real(value)

    monkeypatch.setattr(value_chain_xlsx, "_blank", counted)
    return checked


def openpyxl_opened(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """value_chain_xlsx.load_workbook 을 부른 횟수를 세는 감싸개(진짜를 그대로 부른다). 깊은 시트가 훑기(_scan)에서
    거절돼 openpyxl 에 닿지 않음을 벽시계 대신 일의 양으로 잰다(IRS4 — DV8 꼴)."""
    opened = [0]
    real = value_chain_xlsx.load_workbook

    def counted(*args: Any, **kwargs: Any) -> Any:
        opened[0] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(value_chain_xlsx, "load_workbook", counted)
    return opened


# ── 정상 ──


def test_rows_are_read_in_order_with_skipped_rows_stripped_text_and_columns_past_the_five_ignored() -> None:
    data = s.book(
        [
            ["  가상부문 ", " 가상 시공 사업  ", " 업스트림", "가상협력사 ", "자재 조달", "F 열은 읽지 않는다"],
            [None, None, None, None, None],
            ["", "   ", " ", "", None],
            ["가상부문둘", "가상 유지보수 사업", "다운스트림", "가상고객", "점검", 2030],
        ],
        header=(" 사업 부문 ", "사업 내용", "밸류체인 ", "이해관계자", " 관련 비즈니스 활동"),
    )
    assert read(data) == (FIRST, SECOND)


def test_a_hundred_rows_at_the_char_limits_are_read() -> None:
    rows = s.synthetic_rows(MAX_DATA_ROWS, chars=value_chain_xlsx.MAX_CHARS)
    assert read(s.table(rows)) == tuple(rows)
    assert (MAX_DATA_ROWS, value_chain_xlsx.MAX_CHARS) == (100, (50, 200, 20, 50, 200))  # 웹 valueChain.ts 와 같은 값


def test_the_first_visible_sheet_is_read_when_no_sheet_is_named_value_chain() -> None:
    assert read(s.book([list(FIRST)], sheets=3)) == (FIRST,)


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
    assert read(with_binary_parts(base())) == (FIRST, SECOND)


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


def rows_then(n: int, last: list[object]) -> bytes:
    """지어낸 행 n 개 뒤에 last 한 행."""
    return s.book([*[list(r) for r in s.synthetic_rows(n)], last])


@pytest.mark.parametrize(
    ("data", "kind", "row", "column", "message"),
    [
        (b"", "not_xlsx", None, None, NOT_XLSX),
        (b"{}", "not_xlsx", None, None, NOT_XLSX),
        (b"business_unit,stage\n", "not_xlsx", None, None, NOT_XLSX),
        (s.book([list(FIRST)], header=("부문", *s.HEADER[1:])), "bad_header", None, None, BAD_HEADER),
        (s.book([list(FIRST)], header=s.HEADER[::-1]), "bad_header", None, None, BAD_HEADER),
        (s.book([], header=None), "bad_header", None, None, BAD_HEADER),
        (
            rows_then(10, ["가상", "가상", "업스트림", "가상", 2030]),
            "not_text",
            11,
            4,
            "11행의 관련 비즈니스 활동 칸이 글자가 아니에요 — 셀 서식을 텍스트로 바꿔 주세요.",
        ),
        (
            s.book([[True, "가상", "업스트림", "가상", "가상"]]),
            "not_text",
            1,
            0,
            "1행의 사업 부문 칸이 글자가 아니에요 — 셀 서식을 텍스트로 바꿔 주세요.",
        ),
        (
            s.book([["가" * 51, "", "업스트림", "", ""]]),
            "too_long",
            1,
            0,
            "1행의 사업 부문 칸이 너무 길어요 — 50자까지예요.",
        ),
        (
            s.book([["", "가" * 201, "업스트림", "", ""]]),
            "too_long",
            1,
            1,
            "1행의 사업 내용 칸이 너무 길어요 — 200자까지예요.",
        ),
        (s.book([["", "", "가" * 21, "", ""]]), "too_long", 1, 2, "1행의 밸류체인 칸이 너무 길어요 — 20자까지예요."),
        (s.book([["", "", "", "가" * 51, ""]]), "too_long", 1, 3, "1행의 이해관계자 칸이 너무 길어요 — 50자까지예요."),
        (
            s.book([["", "", "", "", "가" * 201]]),
            "too_long",
            1,
            4,
            "1행의 관련 비즈니스 활동 칸이 너무 길어요 — 200자까지예요.",
        ),
        (s.book([]), "no_rows", None, None, "활동이 없어요 — 열 이름 아래에 가치사슬 활동을 적어 주세요."),
        (
            s.table(s.synthetic_rows(MAX_DATA_ROWS + 1)),
            "too_many_rows",
            101,
            None,
            "활동이 너무 많아요 — 100행까지 넣을 수 있어요.",
        ),
    ],
    ids=[
        "empty",
        "json",
        "csv",
        "header",
        "header_order",
        "empty_sheet",
        "number",
        "bool",
        "unit_long",
        "description_long",
        "stage_long",
        "stakeholder_long",
        "activity_long",
        "no_rows",
        "101",
    ],
)
def test_each_rejection_has_its_kind_row_column_and_sentence(
    data: bytes, kind: str, row: int | None, column: int | None, message: str
) -> None:
    rejection = refused(data)
    assert (rejection.kind, rejection.row, rejection.column, rejection.message) == (kind, row, column, message)


def test_a_date_cell_is_not_text() -> None:
    import datetime

    rejection = refused(s.book([["가상", datetime.date(2030, 1, 1), "업스트림", "가상", "가상"]]))
    assert (rejection.kind, rejection.row, rejection.column) == ("not_text", 1, 1)


def test_a_formula_without_a_stored_value_is_a_blank_cell() -> None:
    """data_only — openpyxl 이 지은 수식 칸에는 계산된 값이 없다(None). 활동 칸만 수식이면 빈 칸("")."""
    assert read(s.book([["가상", "가상", "업스트림", "가상", '=A2&"x"']])) == (
        ("가상", "가상", "업스트림", "가상", ""),
    )


def test_rejection_messages_never_carry_cell_values() -> None:
    secret = "가상기밀부문"
    for data in (
        s.book([[secret, "가상", "업스트림", "가상", "v" * 201]]),
        s.book([[secret, "가상", "업스트림", "가상", 7]]),
        s.book([[secret, "가상", "업스트림" * 10, "가상", "가상"]]),
        s.book([[secret * 9, "가상", "업스트림", "가상", "가상"]]),  # 그 칸 자체가 길다(54자)
        s.table([(secret, "", "업스트림", "", "")] * (MAX_DATA_ROWS + 1)),
    ):
        assert secret not in refused(data).message


def test_too_large_bytes_are_refused_before_opening() -> None:
    rejection = refused(b"PK" + b"\0" * value_chain_xlsx.MAX_BYTES)
    assert (rejection.kind, rejection.row, rejection.column) == ("too_large", None, None)
    assert rejection.message == "파일이 너무 커요 — 1MB 이하로 올려 주세요."


# ── 행 규칙(발주서 Q4 ③·④ — 두 길 공통, 웹 model/valueChain.ts 와 같은 규칙) ──


def test_a_row_without_a_unit_inherits_the_unit_and_an_empty_description_from_the_row_above() -> None:
    data = s.book(
        [
            ["가상부문", "가상 시공 사업", "업스트림", "가상협력사", "자재 조달"],
            [None, None, "자체운영", "가상임직원", "현장 시공"],
            [None, "따로 적은 내용", "자체운영", "가상지역사회", "안전 관리"],
        ]
    )
    assert read(data) == (
        ("가상부문", "가상 시공 사업", "업스트림", "가상협력사", "자재 조달"),
        ("가상부문", "가상 시공 사업", "자체운영", "가상임직원", "현장 시공"),
        ("가상부문", "따로 적은 내용", "자체운영", "가상지역사회", "안전 관리"),
    )


def test_a_new_unit_with_an_empty_description_keeps_it_empty() -> None:
    """감독 10-28 (나): 사업 부문이 있으면 사업 내용 빔은 "" 그대로 — 앞 부문의 내용을 물려받지 않는다."""
    data = s.book([list(FIRST), ["가상부문둘", None, "다운스트림", "가상고객", "점검"]])
    assert read(data)[1] == ("가상부문둘", "", "다운스트림", "가상고객", "점검")


def test_the_first_data_row_without_a_unit_is_empty() -> None:
    assert read(s.book([[None, None, "업스트림", "가상협력사", "자재 조달"]])) == (
        ("", "", "업스트림", "가상협력사", "자재 조달"),
    )


def test_skipped_rows_are_not_counted_in_the_row_number() -> None:
    """④ 로 건너뛴 행(밸류체인·이해관계자·활동이 다 빔 — 사업 부문만 찬 행 포함)은 데이터 행 번호를 세지 않는다."""
    data = s.book([list(FIRST), ["가상부문만", "가상내용만", None, " ", None], ["", "", "가" * 21, "", ""]])
    rejection = refused(data)
    assert (rejection.kind, rejection.row, rejection.column) == ("too_long", 2, 2)


def test_the_stage_text_is_returned_as_written() -> None:
    """Q3: 서버는 밸류체인 값을 고치지 않는다(코랩 영어 값·틀린 값도 그대로 — 웹이 고른다)."""
    data = s.book([["가상", "", "Own Operations", "", ""], ["가상", "", "중간", "", ""]])
    assert [row[2] for row in read(data)] == ["Own Operations", "중간"]


# ── 마크스폰 템플릿 꼴(발주서 Q4 — 지어낸 내용으로 재현) ──


def test_the_template_like_value_chain_sheet_is_read_with_merges_filled_and_blank_slots_skipped() -> None:
    """시트 셋(셋째 「0. Value Chain 파악」) · 4행 B4:F4 병합 · 5행 B~F 머리 · B6:B9·C6:C9 세로 병합 ·
    10~16행 B·C 병합만. 「ex.)」 예시 행은 거르지 않는다(Q4 ⑤)."""
    assert read(s.template_like()) == (
        ("ex.) 가상건설부문", "가상 시공 사업", "업스트림", "가상협력사", "자재 조달"),
        ("ex.) 가상건설부문", "가상 시공 사업", "자체운영", "가상임직원", "현장 시공"),
        ("ex.) 가상건설부문", "가상 시공 사업", "자체운영", "가상지역사회", "현장 안전 관리"),
        ("ex.) 가상건설부문", "가상 시공 사업", "다운스트림", "가상고객", "준공 후 유지보수"),
    )


def test_the_template_row_number_counts_from_the_row_after_the_header() -> None:
    data = s.template_like([list(FIRST), [None, None, None, None, None], ["", "", "", "", "가" * 201]])
    rejection = refused(data)
    assert (rejection.kind, rejection.row, rejection.column) == ("too_long", 2, 4)


def test_a_value_chain_sheet_name_is_matched_ignoring_case_and_spaces() -> None:
    assert len(read(s.template_like(value_chain_title="가상 VALUECHAIN 표"))) == 4
    assert len(read(s.template_like(value_chain_title="value  chain"))) == 4


def test_a_hidden_value_chain_sheet_is_skipped_for_the_first_visible_sheet() -> None:
    """숨은 「value chain」 시트는 건너뛴다 → 이름 맞는 보이는 시트가 없으니 첫 보이는 시트(「목차」 — 머리 없음)."""
    assert refused(s.template_like(hidden_value_chain=True)).kind == "bad_header"
    assert len(read(s.template_like())) == 4  # 분모: 보이면 읽힌다


def test_without_a_value_chain_name_the_first_visible_sheet_is_read() -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    hidden = workbook.active
    assert hidden is not None
    hidden.title = "가상숨김"
    hidden.append(list(s.HEADER))
    hidden.append(["숨은 시트", "", "업스트림", "", ""])
    hidden.sheet_state = "hidden"
    shown = workbook.create_sheet("가상표")
    shown.append(list(s.HEADER))
    shown.append(list(FIRST))
    out = io.BytesIO()
    workbook.save(out)
    assert read(out.getvalue()) == (FIRST,)


def header_at(row: int, column: int = 1) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for offset, name in enumerate(s.HEADER):
        sheet.cell(row, column + offset, name)
    for offset, value in enumerate(FIRST):
        sheet.cell(row + 1, column + offset, value)
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


def test_the_header_is_found_within_the_top_twenty_rows_at_any_column() -> None:
    assert read(header_at(20, 22)) == (FIRST,)  # V~Z — MAX_HEADER_COL(26) 안
    assert refused(header_at(21)).kind == "bad_header"
    assert refused(header_at(1, 23)).kind == "bad_header"  # W~AA — Z 열 너머


def test_five_names_that_are_not_neighbours_are_not_a_header() -> None:
    data = s.book([list(FIRST)], header=(*s.HEADER[:2], None, *s.HEADER[2:]))
    assert refused(data).kind == "bad_header"


def test_a_merge_fills_its_blank_cells_from_the_top_left() -> None:
    """가로(D2:E2)와 물려받기가 없는 열의 세로(D3:D4 — 이해관계자). 사업 부문·사업 내용의 세로 병합은 물려받기(Q4 ③)와
    결과가 같아 병합 채움을 따로 재지 못한다 — 그래서 이 열들로 잰다."""
    data = s.with_merges(
        s.book(
            [
                ["가상", "가상", "업스트림", "가상공통", None],
                ["", "", "자체운영", "가상세로", "가"],
                ["", "", "", None, "나"],
            ]
        ),
        ["D2:E2", "D3:D4"],
    )
    assert read(data) == (
        ("가상", "가상", "업스트림", "가상공통", "가상공통"),
        ("가상", "가상", "자체운영", "가상세로", "가"),
        ("가상", "가상", "", "가상세로", "나"),
    )


def test_a_merge_starting_at_the_header_row_does_not_fill_data_rows() -> None:
    """머리 행(1행)의 B·D 를 데이터 행으로 내려 건 병합은 열 이름을 데이터로 채우지 않는다(IRW3 — MARC-ISSUE-410 ④).
    데이터 행에서 시작한 병합(E2:E3)은 지금처럼 채운다."""
    data = s.with_merges(
        s.book(
            [
                ["가상A", "", "업스트림", None, "가"],
                ["가상B", "", "자체운영", None, None],
            ]
        ),
        ["B1:B2", "D1:D3", "E2:E3"],
    )
    assert read(data) == (
        ("가상A", "", "업스트림", "", "가"),
        ("가상B", "", "자체운영", "", "가"),
    )


def test_a_merge_from_a_title_above_the_header_does_not_fill_data_rows() -> None:
    """머리 위 행(제목)에서 머리 너머 데이터 행까지 내려오는 병합도 버린다(Q1 (가)). 머리 행 칸은 그대로."""
    data = s.with_merges(
        s.book(
            [
                ["", "", "", "", "가상 제목"],
                list(s.HEADER),
                ["가상", "가상", "업스트림", "가상", None],
            ],
            header=None,
        ),
        ["E1:E3"],
    )
    assert read(data) == (("가상", "가상", "업스트림", "가상", ""),)


def test_a_merge_overlapping_one_from_the_header_row_is_still_unsafe() -> None:
    """머리 행에서 시작한 병합은 채우지만 않을 뿐 겹침 검사에는 남는다(IRW3 검증 1 B1 — B1:B4 와 B3:B4)."""
    rows = [["가상", "", "업스트림", "가", "나"]] * 3
    assert refused(s.with_merges(s.book(rows), ["B1:B4", "B3:B4"])).kind == "unsafe_xlsx"


def test_merges_over_the_limit_or_overlapping_are_unsafe() -> None:
    fits = s.with_merges(base(), [f"H{r}:I{r}" for r in range(1, MAX_MERGES + 1)])
    assert len(read(fits)) == 2
    over = s.with_merges(base(), [f"H{r}:I{r}" for r in range(1, MAX_MERGES + 2)])
    assert refused(over).kind == "unsafe_xlsx"
    overlap = s.with_merges(base(), ["A2:B3", "B3:C4"])
    assert refused(overlap).kind == "unsafe_xlsx"
    assert MAX_MERGES == 1_000


@pytest.mark.parametrize("ref", ["가상", "A2:", "ZZZZ1:A1"])
def test_a_malformed_merge_reference_is_not_xlsx(ref: str) -> None:
    """openpyxl 은 read_only 로도 시트의 mergeCell 을 읽다가 꼴이 아닌 ref 에서 ValueError 를 낸다(실측) → not_xlsx.
    읽개의 `_range` 가 그런 ref 를 건너뛰는 것은 그 앞의 방어다(openpyxl 이 바뀌어도 병합 채움이 예외를 내지 않게)."""
    assert refused(s.with_merges(base(), [ref])).kind == "not_xlsx"


def test_a_merge_over_ten_thousand_rows_does_one_check_per_merged_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    """병합 범위가 1만 행에 걸쳐도 한 행의 일은 열 수 안이다(겹침 거절 — 활성 범위 ≤ 26). 시트는 10,000행째에 칸이 있어
    1만 행을 다 훑는다(검증 m4). 일의 양으로 잼(IRS4): 내준 행 = 상한, 빈 칸 검사 = 병합 칸 수 + 표 읽기 몫."""
    columns = "FGHIJKLMNOPQRSTUVWXYZ"
    sheet = s.with_merges(
        s.rezip(base(), replace={s.SHEET: s.far_row_sheet(MAX_SCANNED_ROWS)}),
        [f"{c}2:{c}{MAX_SCANNED_ROWS}" for c in columns],
    )
    given = rows_given(monkeypatch)
    checked = blanks_checked(monkeypatch)
    assert read(sheet) == (("", "", "업스트림", "", ""),)
    assert given[0] == MAX_SCANNED_ROWS  # 10,000행째까지 내주고 그 너머는 없음
    merged_cells = (MAX_SCANNED_ROWS - 1) * len(columns)  # 2행~10,000행 × 병합 21열 — 칸마다 한 번
    table_part = (MAX_SCANNED_ROWS - 2) * 3 + 1  # 빈 데이터 행은 C·D·E 셋, 10,000행은 C 하나에서 멈춤
    assert checked[0] == merged_cells + table_part


# ── 공격(상한 안에서 거절) ──


def test_not_a_zip_and_a_zip_without_content_types_are_not_xlsx() -> None:
    assert refused(b"PK\x03\x04 virtual").kind == "not_xlsx"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("a.txt", "virtual")
    assert refused(out.getvalue()).kind == "not_xlsx"


def test_too_many_entries_are_unsafe() -> None:
    extra = {f"docProps/x{i}.bin": b"" for i in range(value_chain_xlsx.MAX_ENTRIES)}
    assert refused(s.rezip(base(), add=extra)).kind == "unsafe_xlsx"


def test_an_entry_or_the_declared_sum_over_the_limit_is_unsafe() -> None:
    one = s.rezip(base(), add={"xl/media/big.bin": b"\0" * (value_chain_xlsx.MAX_ENTRY_BYTES + 1)})
    assert refused(one).kind == "unsafe_xlsx"
    under = b"\0" * (value_chain_xlsx.MAX_ENTRY_BYTES - 1024)
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


def test_a_million_deep_sheet_is_refused_before_openpyxl(monkeypatch: pytest.MonkeyPatch) -> None:
    """★B(TR3a): 뿌리에서 멈추는 훑기로는 openpyxl 에 가 2.4초·RSS +592MB 였던 파일(12KB).
    일의 양으로 잼(IRS4): 훑기에서 거절, load_workbook 0회(분모 — 정상 파일은 1회)."""
    opened = openpyxl_opened(monkeypatch)
    assert len(read(base())) == 2
    assert opened[0] == 1
    data = s.rezip(base(), replace={s.SHEET: s.deep_sheet(1_000_000)})
    rejection = refused(data)
    assert opened[0] == 1  # 훑기(_scan)에서 거절 — openpyxl 에 닿지 않음
    assert rejection.kind == "unsafe_xlsx"


def test_a_cell_far_down_stops_at_the_scanned_row_limit() -> None:
    """read_only 는 빈 행 번호마다 빈 행을 내준다 — 1,048,576행 칸 하나도 MAX_SCANNED_ROWS 에서 멈춘다."""
    rejection = refused(s.rezip(base(), replace={s.SHEET: s.far_row_sheet(1_048_576)}))
    assert (rejection.kind, rejection.row, rejection.column) == ("too_many_scanned_rows", None, None)
    assert rejection.message == "빈 행이 너무 많아요 — 표만 남기고 10,000행 안으로 올려 주세요."


def test_ten_thousand_and_one_blank_rows_are_refused_and_ten_thousand_are_read() -> None:
    over = refused(s.rezip(base(), replace={s.SHEET: s.far_row_sheet(MAX_SCANNED_ROWS + 1)}))
    assert over.kind == "too_many_scanned_rows"
    near = read(s.rezip(base(), replace={s.SHEET: s.far_row_sheet(MAX_SCANNED_ROWS)}))
    assert near == (("", "", "업스트림", "", ""),)  # 10,000행째까지 훑었다


def test_the_workbook_is_closed_even_when_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []
    real = value_chain_xlsx.load_workbook

    def tracking(*args: object, **kwargs: object) -> object:
        workbook = real(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        original = workbook.close

        def close() -> None:
            closed.append(True)
            original()

        workbook.close = close  # pyright: ignore[reportAttributeAccessIssue]
        return workbook

    monkeypatch.setattr(value_chain_xlsx, "load_workbook", tracking)
    refused(s.book([["가상", "가상", "업스트림", "가상", 7]]))
    read(base())
    assert closed == [True, True]


def test_a_memory_error_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def out_of_memory(*_: object, **__: object) -> object:
        raise MemoryError

    monkeypatch.setattr(value_chain_xlsx, "load_workbook", out_of_memory)
    with pytest.raises(MemoryError):
        read_value_chain(base())


def test_no_corrupted_byte_raises() -> None:
    """어떤 바이트를 받아도 예외가 아니라 갈래다(test_docx_reader 꼴 — 자리마다 비트를 뒤집는다)."""
    for data in (with_binary_parts(base()), s.template_like()):
        for position in range(0, len(data), max(1, len(data) // 300)):
            broken = bytearray(data)
            broken[position] ^= 1 << (position % 8)
            assert isinstance(read_value_chain(bytes(broken)), ValueChainRead | ValueChainRejected)
        assert isinstance(read_value_chain(data[: len(data) // 2]), ValueChainRejected)


# ── 검증 B1(TR3a): openpyxl 은 파트를 관계의 Target 으로 연다 ──

SHEET_DAT = "xl/worksheets/sheet1.dat"


def test_a_sheet_moved_to_an_odd_name_without_override_is_still_read() -> None:
    """분모: openpyxl 은 이름·꼴이 xml 이 아닌 시트도 워크북 rels 의 Target 으로 연다(그래서 훑어야 한다). 병합을 읽는
    자리도 같은 Target 으로 찾는다."""
    assert len(read(s.moved(base(), s.SHEET, SHEET_DAT))) == 2
    merged = s.with_merges(s.book([["가상", "가상", "업스트림", "가상공통", None]]), ["D2:E2"])
    assert read(s.moved(merged, s.SHEET, SHEET_DAT)) == (("가상", "가상", "업스트림", "가상공통", "가상공통"),)


def test_a_doctype_or_a_deep_sheet_moved_to_an_odd_name_is_unsafe(monkeypatch: pytest.MonkeyPatch) -> None:
    """옮긴 시트도 훑는다 — 일의 양으로 잼(IRS4): DOCTYPE·깊은 시트 모두 load_workbook 0회(분모 — 옮긴 정상 시트는
    1회)."""
    opened = openpyxl_opened(monkeypatch)
    assert len(read(s.moved(base(), s.SHEET, SHEET_DAT))) == 2
    assert opened[0] == 1
    sheet = s.entries(base())[s.SHEET]
    assert refused(s.moved(base(), s.SHEET, SHEET_DAT, content=s.with_doctype(sheet))).kind == "unsafe_xlsx"
    deep = refused(s.moved(base(), s.SHEET, SHEET_DAT, content=s.deep_sheet(1_000_000)))
    assert opened[0] == 1  # 훑기에서 거절 — openpyxl 에 닿지 않음
    assert deep.kind == "unsafe_xlsx"


def test_styles_moved_to_an_odd_name_with_a_doctype_is_unsafe() -> None:
    styles = s.entries(base())["xl/styles.xml"]
    data = s.moved(base(), "xl/styles.xml", "xl/styles.dat", content=s.with_doctype(styles))
    assert refused(data).kind == "unsafe_xlsx"


def test_a_sheet_whose_relationship_type_lies_as_an_image_is_still_scanned(monkeypatch: pytest.MonkeyPatch) -> None:
    """짝(감독 63): Type 만 image 로 속이면 바이너리 관계로 빠질 듯하지만 openpyxl 은 시트를 r:id 로 찾고 Type 을 보지
    않아 그대로 연다(실측 — 분모). 워크북 rels 는 Type 과 상관없이 훑으므로 공격 시트는 거절, openpyxl 앞에서.
    일의 양으로 잼(IRS4): 공격 시트에 load_workbook 0회(분모 — 속인 정상 시트는 1회)."""
    opened = openpyxl_opened(monkeypatch)
    sheet = s.entries(base())[s.SHEET]
    assert len(read(s.moved(base(), s.SHEET, SHEET_DAT, rel_type=s.IMAGE_TYPE))) == 2
    assert opened[0] == 1
    lie = s.moved(base(), s.SHEET, SHEET_DAT, content=s.with_doctype(sheet), rel_type=s.IMAGE_TYPE)
    assert refused(lie).kind == "unsafe_xlsx"
    deep = s.moved(base(), s.SHEET, SHEET_DAT, content=s.deep_sheet(1_000_000), rel_type=s.IMAGE_TYPE)
    rejection = refused(deep)
    assert opened[0] == 1  # 훑기에서 거절 — openpyxl 에 닿지 않음
    assert rejection.kind == "unsafe_xlsx"


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
    """감독 63 처분(TR3a 검증 B1·B2 뒤): 고르는 기준은 내용이다 — 이름·꼴·관계가 없어도(뿌리의 evil.dat) XML 로 보이면
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
    """검증 R6(TR3a): 100만 겹 UTF-16 은 항목 크기 상한(8MiB)에서 먼저 거절돼 깊이를 재지 않는다 — 상한 밑 크기로
    깊이만 넘는 판. 경계 짝(64 받음 · 65 거절)과 시트 자리의 100겹."""

    def pad(depth: int) -> bytes:
        data = s.rezip(base(), add={PAD: ("<x>" * depth + "</x>" * depth).encode(codec)})
        assert len(s.entries(data)[PAD]) < 8 * 1024 * 1024
        return data

    assert len(read(pad(MAX_XML_DEPTH))) == 2
    assert refused(pad(MAX_XML_DEPTH + 1)).kind == "unsafe_xlsx"
    deep = s.deep_sheet(100).decode().replace('encoding="UTF-8"', 'encoding="UTF-16"').encode(codec)
    assert refused(s.moved(base(), s.SHEET, SHEET_DAT, content=deep)).kind == "unsafe_xlsx"


# ── 가지 리뷰(TR3a 10-23): 부록 F 표·앞 공백 뒤 `<` 다섯 꼴·속성 예산·표지 간격 ──

WORKBOOK = "xl/workbook.xml"


def ucs4(text: str, codec: str, *, bom: bytes = b"") -> bytes:
    return bom + text.encode(codec)


@pytest.mark.parametrize(
    ("codec", "bom"),
    [("utf-32-be", b""), ("utf-32-le", b""), ("utf-32-be", b"\x00\x00\xfe\xff"), ("utf-32-le", b"\xff\xfe\x00\x00")],
    ids=["be", "le", "be_bom", "le_bom"],
)
def test_a_ucs4_workbook_with_a_doctype_is_unsafe(codec: str, bom: bytes) -> None:
    """lxml 은 UCS-4 를 부록 F 로 읽어 DOCTYPE 째 연다(TR3a 가지 리뷰 재현). 정직한 UCS-4 도 expat 이 못 읽어
    거절된다."""
    workbook = s.entries(base())[WORKBOOK].decode()
    bad = s.rezip(base(), replace={WORKBOOK: ucs4(s.with_doctype(workbook.encode()).decode(), codec, bom=bom)})
    assert refused(bad).kind == "unsafe_xlsx"
    assert refused(s.rezip(base(), replace={WORKBOOK: ucs4(workbook, codec, bom=bom)})).kind == "unsafe_xlsx"
    assert len(read(base())) == 2  # 짝: 정상 파일은 읽힌다


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"], ids=["le", "be"])
def test_a_bomless_utf16_sheet_led_by_spaces_is_scanned(codec: str) -> None:
    """부록 F 표는 첫 네 바이트만 본다 — BOM 없는 UTF-16 앞의 공백(`0A 00 3C 00`)은 표에 없지만 expat(worksheet 의
    iterparse)은 DOCTYPE 째 읽는다(TR3a 러너 재현). 정직한 판은 읽힌다."""
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
    """TR3a 가지 리뷰 처분: 속성 하나를 요소 합에 1로 더한다(같은 예산). 요소만으로는 예산 안인 파일이 속성으로
    넘는다."""
    room = MAX_XML_ELEMENTS - elements_of(base()) - 1  # <p> 하나
    fits = with_attributes(room // 3, 2)
    assert elements_of(fits) <= MAX_XML_ELEMENTS
    assert len(read(fits)) == 2
    over = with_attributes(room // 3 + 1, 2)
    assert elements_of(over) > MAX_XML_ELEMENTS
    assert refused(over).kind == "unsafe_xlsx"
    assert room // 3 + 1 < MAX_XML_ELEMENTS // 2  # 분모: 요소 수만으로는 예산의 절반도 안 된다


LARGEST_ATTRIBUTE_LIST = 466_067
"""압축해 MAX_BYTES(1MiB) 안에 드는 가장 많은 속성(이름 a0…). TR3a 실측 466,137 — 이 시험의 base() 가 열 다섯이라 zip 이
168 바이트 커서 IRW2 러너가 다시 잼(풀면 약 5.0MB). 표지 간격 상한 없이 handler 에서 세면 이 사전만으로 0.66초·
tracemalloc 106MB·RSS +180MB 였다(TR3a)."""


def huge_attribute_list(attributes: int) -> bytes:
    attrs = b"".join(b' a%d=""' % i for i in range(attributes))
    return s.rezip(base(), add={PAD: b"<x" + attrs + b"/>"})


def test_one_element_with_the_largest_attribute_list_is_refused_before_its_dict_is_built() -> None:
    """TR3a 가지 리뷰 처분(속성 셈) + 표지 간격 상한: 사전을 짓기 전에 거절해 메모리가 늘지 않는다."""
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


def test_a_million_attributes_never_reach_the_parser() -> None:
    """속성 100만 개(TR3a 가지 리뷰의 예)는 압축해도 1MiB 를 넘어 바이트 상한에서 먼저 멈춘다."""
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


def test_a_chosen_sheet_longer_than_the_span_is_read_by_the_merge_reader() -> None:
    """병합을 읽는 expat(_attributes)도 표지 간격을 잰다 — 그래서 handler 마다(글 조각 포함) 자리를 적어야 한다. 적지
    않으면 표지 간격 상한(1MiB)보다 긴 정상 시트(긴 글 조각)가 거절된다. 분모: 시트 XML 이 상한보다 길다."""
    long_text = "가" * 120
    rows = [("가상", long_text[:200], "업스트림", "가상", long_text) for _ in range(MAX_DATA_ROWS)]
    data = s.table(rows)
    assert len(s.entries(data)[s.SHEET]) > 0
    padded_sheet = s.entries(data)[s.SHEET].replace(
        b"</sheetData>", b"</sheetData><extLst>" + "가".encode() * MAX_XML_SPAN + b"</extLst>"
    )
    assert len(padded_sheet) > MAX_XML_SPAN  # 분모: 시트 하나가 표지 간격 상한보다 길다
    assert len(read(s.rezip(data, replace={s.SHEET: padded_sheet}))) == MAX_DATA_ROWS


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
    """TR3a 가지 리뷰(10-23): 주석·처리 지시는 lxml 이 노드로 짓는다 — 28KB 업로드가 처리 지시 320만 개·RSS +220MB(주석
    +179MB) 였다. 둘 다 요소 예산에 1씩 세어 거절한다."""
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


def test_a_table_with_a_few_comments_and_processing_instructions_is_read() -> None:
    """정상: 손으로 단 주석·처리 지시 몇 개는 받는다(병합을 읽는 expat 도)."""
    items = s.entries(s.table([FIRST]))
    sheet = items[s.SHEET]
    at = sheet.index(b">") + 1
    note = '<!-- 가상 메모 --><?mso-application progid="Excel.Sheet"?>'.encode()
    noted = sheet[:at] + note + sheet[at:]
    assert read(s.rezip(s.table([FIRST]), replace={s.SHEET: noted})) == (FIRST,)


def test_the_span_of_the_last_short_chunk_is_measured_to_the_end_of_the_data() -> None:
    """사소(TR3a 가지 리뷰): 마지막 조각은 짧다 — 먹인 끝을 조각 크기로 올려 세면 상한 안의 간격을 넘었다고 본다.
    마지막 이벤트(자리 4 의 주석)에서 끝까지가 MAX_XML_SPAN − 2 인 항목(길이는 상한 + 2)은 받고, 끝을 MAX_XML_SPAN
    너머로 늘리면 거절."""
    head = b"<a/><!---->"
    inside = s.rezip(base(), add={PAD: head + b" " * (MAX_XML_SPAN + 2 - len(head))})
    assert len(read(inside)) == 2
    outside = s.rezip(base(), add={PAD: head + b" " * (MAX_XML_SPAN + 5)})
    assert refused(outside).kind == "unsafe_xlsx"


def test_an_external_target_named_part_is_scanned() -> None:
    """TR3a 검증 B2: 시트 관계를 TargetMode External·Target="evil.dat" 로 바꾸고 뿌리에 evil.dat 를 두면 openpyxl 은
    그 이름으로 연다 — 내용으로 고르므로 이미 훑었다."""
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
    """TR3a 검증 p3 원판의 나머지: sharedStrings·워크북을 .dat 로 옮겨도 내용으로 훑는다."""
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


def test_a_missing_workbook_part_or_relationship_for_the_chosen_sheet_is_not_xlsx() -> None:
    """병합 읽기는 워크북·rels 로 시트를 찾는다 — rels 에 그 시트의 관계가 없으면 not_xlsx(openpyxl 도 못
    연다). 분모: 있으면 읽힌다."""
    entries = s.entries(base())
    no_rel = entries[s.WORKBOOK_RELS].replace(b'Id="rId1"', b'Id="rIdVirtual"')
    assert refused(s.rezip(base(), replace={s.WORKBOOK_RELS: no_rel})).kind == "not_xlsx"
    assert len(read(base())) == 2


# ── 옮긴 방어 가운데 glossary 시험에 짝이 없던 둘(IRW2 러너 — 심은 파손 P2b·P2d 가 겨눈다) ──


def test_a_zip_with_two_entries_of_the_same_name_is_unsafe() -> None:
    """zipfile 은 같은 이름이 둘이면 조용히 뒤의 것을 준다 — 훑은 바이트와 openpyxl 이 여는 바이트가 다를 수 있다."""
    import warnings

    items = s.entries(base())
    out = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # zipfile 의 「Duplicate name」 경고
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, part in items.items():
                archive.writestr(name, part)
            archive.writestr(s.SHEET, items[s.SHEET])
    assert refused(out.getvalue()).kind == "unsafe_xlsx"


@pytest.mark.parametrize(
    "root",
    [(b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"', b"<Types"), (b"Types", b"Typez")],
    ids=["no_namespace", "other_name"],
)
def test_a_content_types_part_whose_root_is_not_the_opc_types_is_not_xlsx(root: tuple[bytes, bytes]) -> None:
    """openpyxl 은 뿌리가 OPC `Types` 가 아닌 [Content_Types].xml 도 연다(IRW2 러너 실측 — 둘 다 시트를 읽음). 그래서
    뿌리 검사가 xlsx 인지를 가른다. 분모: 그대로면 읽힌다."""
    types = s.entries(base())[s.CONTENT_TYPES].replace(*root)
    assert refused(s.rezip(base(), replace={s.CONTENT_TYPES: types})).kind == "not_xlsx"
    assert len(read(base())) == 2


def test_the_merge_reader_refuses_a_doctype_on_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """둘째 겹(검증 m1): 병합 읽기의 expat(`_attributes`)도 `_parser()` 라 DOCTYPE 을 스스로 거절한다 — 앞의 훑기를
    꺼도 워크북의 DOCTYPE 은 unsafe_xlsx. 분모: 훑기를 끈 채 정상 파일은 읽힌다."""

    def no_scan(data: bytes, elements: list[int]) -> None:
        del data, elements

    monkeypatch.setattr(value_chain_xlsx, "_scan", no_scan)
    assert len(read(base())) == 2
    workbook = s.entries(base())["xl/workbook.xml"]
    assert refused(s.rezip(base(), replace={"xl/workbook.xml": s.with_doctype(workbook)})).kind == "unsafe_xlsx"
