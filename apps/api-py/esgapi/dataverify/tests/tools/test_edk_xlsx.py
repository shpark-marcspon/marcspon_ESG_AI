"""EDK 인벤토리 엑셀 읽개(tools/edk_xlsx.py — 밴드 DVX1 §3 ①, 순수): 지금 양식 파일은 data(대상 테마만)·셈, 거절
갈래마다 kind·엑셀 행·열 번호·해요체 글(칸 값 0), 공격 파일은 상한 안에서 unsafe_xlsx, 어떤 바이트도 예외 0. xlsx 는
전부 메모리에서 지은 지어낸 것이다(tests/tools/edk_xlsx_support.py — 가상 기업·가상 값).

★ 방어 시험(「공격」 절부터)은 translation/tests/tools/test_glossary_xlsx.py(밴드 TR3a)를 옮겨 적은 것이다(양식·정상
읽기 시험 빼고 전부 — 대응표는 band-reports/DVX1.md). 바꾼 것은 지은 파일(EDK 머리 14열)·읽은 값의 꼴·거절 갈래
이름·요소 예산 값(500,000)뿐이다."""

import datetime
import io
import json
import time
import tracemalloc
import xml.parsers.expat
import zipfile
from collections.abc import Generator, Mapping
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import TypeAdapter

from esgapi.dataverify.contracts.shapes import DataverifyInput
from esgapi.dataverify.engines.colab_156.inputs import split_themes
from esgapi.dataverify.flows.colab_156 import _scope  # pyright: ignore[reportPrivateUsage]
from esgapi.dataverify.tests.tools import edk_xlsx_support as s
from esgapi.dataverify.tools import edk_xlsx
from esgapi.dataverify.tools.edk_xlsx import (
    MAX_BYTES,
    MAX_CELL_CHARS,
    MAX_ITEMS,
    MAX_SCANNED_ROWS,
    MAX_XML_DEPTH,
    MAX_XML_ELEMENTS,
    MAX_XML_SPAN,
    OPTIONS_MAX_OCTETS,
    EdkRead,
    EdkRejected,
    read_edk,
)

PAD = "docProps/pad.xml"
"""openpyxl 이 열지 않지만 이름이 .xml 이라 훑기 대상인 항목(경계 시험의 채움 자리)."""
ENV: Final = "환경"
OTHER_THEMES: Final = ("가상사회", "가상지배구조", "가상경제", "가상기타")
"""지어낸 다른 테마 이름 넷 — 응답 어디에도 나오면 안 된다."""
SECRET: Final = "가상기밀항목명"


def outcome(data: bytes) -> EdkRead:
    result = read_edk(data)
    assert isinstance(result, EdkRead), result
    return result


def read(data: bytes) -> tuple[dict[str, Any], ...]:
    """환경 항목들(파일 차례)."""
    return tuple(outcome(data).data[ENV])


def refused(data: bytes) -> EdkRejected:
    result = read_edk(data)
    assert isinstance(result, EdkRejected), result
    return result


def rows_given(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """edk_xlsx._rows 가 내준 행 수(머리 행 포함 — 곧 마지막으로 내준 행의 엑셀 번호)를 세는 감싸개. 벽시계 대신 일의
    양으로 「멈춘 자리 너머를 읽지 않음」을 잰다(DV8 — 부하 때 1초 문턱이 빨갛던 MARC-ISSUE-557)."""
    given = [0]
    real = edk_xlsx._rows  # pyright: ignore[reportPrivateUsage]

    def counted(data: bytes) -> Generator[tuple[object, ...]]:
        rows = real(data)
        try:
            for row in rows:
                given[0] += 1
                yield row
        finally:
            rows.close()

    monkeypatch.setattr(edk_xlsx, "_rows", counted)
    return given


def openpyxl_opened(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """edk_xlsx.load_workbook 을 부른 횟수를 세는 감싸개(진짜를 그대로 부른다). 깊은 시트가 훑기(_scan)에서 거절돼
    openpyxl 에 닿지 않음을 벽시계 대신 일의 양으로 잰다(DV8)."""
    opened = [0]
    real = edk_xlsx.load_workbook

    def counted(*args: Any, **kwargs: Any) -> Any:
        opened[0] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(edk_xlsx, "load_workbook", counted)
    return opened


def base() -> bytes:
    return s.book([s.row(1, ENV, "가상 직접 배출량", [100, 110, 120]), s.row(2, ENV, "가상 간접 배출량", [5, 6, 7])])


def company_rows() -> list[list[object]]:
    """가상 기업 하나의 지금 양식 꼴: 테마 다섯(환경 + 지어낸 넷), ID 는 int·정수 float 섞음, 입력 방식 숫자·계산식·
    Yes/No, 빈 행 수백(가운데·끝), 메모 빈 칸, 「공시」 열 있음."""
    rows: list[list[object]] = [
        s.row(90001.0, ENV, "가상 직접 배출량", [1200.0, 1150, 1100.5], memo="가상 메모"),
        s.row(90002, ENV, "가상 재생에너지 사용", ["Yes", "No", None], method="Yes/No", unit=None, key="N"),
        s.row(90003, OTHER_THEMES[0], "가상 임직원 수", [10, 11, 12]),
    ]
    rows += [[None] * 14 for _ in range(300)]  # pyright: ignore[reportAssignmentType]
    rows += [
        s.row(90004.0, ENV, "가상 용수 사용량", ["=I5*2", 3.25, 0], method="계산식"),
        s.row(90005, OTHER_THEMES[1], "가상 이사회 수", [1, 2, 3]),
        s.row(90006, OTHER_THEMES[2], "가상 매출", [4, 5, 6]),
        s.row(90007, OTHER_THEMES[3], "가상 기부", [7, 8, 9]),
        s.row(90008, OTHER_THEMES[0], "가상 교육 시간", [1, 1, 1]),
    ]
    rows += [[None] * 14 for _ in range(200)]  # pyright: ignore[reportAssignmentType]
    return rows


def company_book() -> bytes:
    return s.book(company_rows())


# ── 정상: 지금 양식 꼴(가상 기업) ──


def test_the_company_book_keeps_only_the_target_theme_and_counts_the_rest() -> None:
    result = outcome(company_book())
    assert list(result.data) == [ENV]
    assert (result.item_count, result.skipped_themes, result.skipped_items) == (3, 4, 5)
    assert (result.years, result.skipped_empty_rows, result.ignored_columns) == (("2022", "2023", "2024"), 500, 1)
    dumped = json.dumps(result.data, ensure_ascii=False)
    assert [theme for theme in OTHER_THEMES if theme in dumped] == []
    assert "가상 공시" not in dumped  # 「공시」 열은 싣지 않는다


def test_an_item_has_the_eleven_keys_in_order_and_normalised_values() -> None:
    first, second, third = read(company_book())
    assert list(first) == [
        "ID",
        "테마",
        "항목",
        "대분류",
        "중분류",
        "소분류",
        "입력 방식",
        "단위",
        "values",
        "핵심데이터",
        "메모",
    ]
    assert first == {
        "ID": 90001,
        "테마": ENV,
        "항목": "가상 직접 배출량",
        "대분류": "가상대분류",
        "중분류": "가상중분류",
        "소분류": "가상소분류",
        "입력 방식": "숫자",
        "단위": "tCO2eq",
        "values": {"2022": 1200, "2023": 1150, "2024": 1100.5},
        "핵심데이터": "Y",
        "메모": "가상 메모",
    }
    assert type(first["ID"]) is int and type(first["values"]["2022"]) is int  # 정수 float → int
    assert second["values"] == {"2022": "Yes", "2023": "No", "2024": None}  # 글자 그대로 · 빈 칸도 열쇠
    assert (second["단위"], second["메모"], second["핵심데이터"]) == (None, None, "N")
    assert third["ID"] == 90004 and third["values"] == {"2022": None, "2023": 3.25, "2024": 0}  # 값 없는 수식 = None


def test_an_integral_float_written_in_the_file_is_read_as_int() -> None:
    """openpyxl 은 90001.0 을 `90001` 로 적는다 — 다른 프로그램이 적는 `<v>90001.0</v>` 꼴을 시트에 바로 넣어 잰다."""
    data = company_book()
    sheet = s.entries(data)[s.SHEET]
    assert b"<v>90001</v>" in sheet and b"<v>1200</v>" in sheet
    sheet = sheet.replace(b"<v>90001</v>", b"<v>90001.0</v>").replace(b"<v>1200</v>", b"<v>1200.0</v>")
    first = read(s.rezip(data, replace={s.SHEET: sheet}))[0]
    values: Any = first["values"]
    assert (first["ID"], values["2022"]) == (90001, 1200)
    assert type(first["ID"]) is int and type(values["2022"]) is int


def test_strings_are_kept_as_given_without_strip() -> None:
    (item,) = read(s.book([s.row(" 7 ", ENV, "  가상 항목 ", [" 1,234 ", "Yes ", None])]))
    assert (item["ID"], item["항목"], item["values"]["2022"], item["values"]["2023"]) == (
        " 7 ",
        "  가상 항목 ",
        " 1,234 ",
        "Yes ",
    )


def test_the_header_is_found_by_name_whatever_the_order_and_spaces() -> None:
    plain = outcome(company_book())
    order = [13, 0, 11, 2, 1, 10, 3, 4, 12, 5, 6, 7, 8, 9]
    head = s.header()
    shuffled_head = [f"  {head[i]} " for i in order]
    rows = company_rows()
    data = s.book([[r[i] for i in order] for r in rows], head=shuffled_head)
    assert outcome(data) == plain
    assert list(read(data)[0]) == list(read(company_book())[0])  # 열쇠 차례도 같다


@pytest.mark.parametrize(
    "years", [("2022", "2023", "2024"), ("2023", "2024", "2025"), ("2021", "2022", "2023", "2024")]
)
def test_year_columns_are_keyed_by_the_header_without_the_suffix(years: tuple[str, ...]) -> None:
    values = list(range(len(years)))
    data = s.book([s.row(1, ENV, "가상", values)], head=s.header(years))
    result = outcome(data)
    assert result.years == years
    assert result.data[ENV][0]["values"] == dict(zip(years, values, strict=True))


def test_year_columns_out_of_order_are_keyed_in_ascending_order() -> None:
    head = s.header(("2024", "2022", "2023"))
    result = outcome(s.book([s.row(1, ENV, "가상", [24, 22, 23])], head=head))
    assert result.years == ("2022", "2023", "2024")
    values: Any = result.data[ENV][0]["values"]
    assert list(values.items()) == [("2022", 22), ("2023", 23), ("2024", 24)]


def test_a_year_header_written_as_a_number_is_a_year_column() -> None:
    """머리 칸을 수(2023)로 적어도 연도 열이다(1002~9999 의 정수만 — 그 밖의 수 머리는 읽지 않는 열). R2."""
    head: list[object] = list(s.header(("2022", "2023", "2024")))
    head[9] = 2023
    head[10] = 2024
    result = outcome(s.book([s.row(1, ENV, "가상", [22, 23, 24])], head=head))
    assert result.years == ("2022", "2023", "2024")
    assert result.data[ENV][0]["values"] == {"2022": 22, "2023": 23, "2024": 24}
    for odd in (1001, 10000, 2023.5, True):
        head = list(s.header(("2022", "2023", "2024")))
        head[10] = odd
        result = outcome(s.book([s.row(1, ENV, "가상", [22, 23, 24])], head=head))
        assert (result.years, result.ignored_columns) == (("2022", "2023"), 2), odd


def test_a_number_year_header_and_the_same_year_as_text_overlap() -> None:
    head: list[object] = list(s.header(("2022", "2023", "2024")))
    head[10] = 2022
    rejection = refused(s.book([s.row(1, ENV, "가상", [1, 2, 3])], head=head))
    assert (rejection.kind, rejection.row, rejection.column) == ("bad_header", 1, 11)


def test_an_integral_float_beyond_two_to_the_53_stays_a_float() -> None:
    """2**53 을 넘는 정수 float 는 정확한 정수가 아니다 — 받은 float 그대로(R1). 시트 XML 에 <v> 를 바로 적는다."""
    data = s.book([s.row(1, ENV, "가상", [7, 8, 9])])
    sheet = s.entries(data)[s.SHEET]
    assert b"<v>7</v>" in sheet and b"<v>8</v>" in sheet and b"<v>9</v>" in sheet
    sheet = (
        sheet.replace(b"<v>7</v>", b"<v>9007199254740992.0</v>")
        .replace(b"<v>8</v>", b"<v>9007199254740991.0</v>")
        .replace(b"<v>9</v>", b"<v>-1e300</v>")
    )
    values: Any = read(s.rezip(data, replace={s.SHEET: sheet}))[0]["values"]
    assert values == {"2022": 9007199254740992.0, "2023": 9007199254740991, "2024": -1e300}
    assert (type(values["2022"]), type(values["2023"]), type(values["2024"])) == (float, int, float)


def test_a_theme_with_spaces_is_grouped_by_the_stripped_name() -> None:
    """테마는 앞뒤 공백을 뗀 글로 묶는다(가지 리뷰 N1) — 항목의 테마 칸 값은 받은 그대로."""
    result = outcome(
        s.book(
            [
                s.row(1, "환경 ", "가상 하나", [1, 2, 3]),
                s.row(2, " 환경", "가상 둘", [4, 5, 6]),
                s.row(3, ENV, "셋", [7, 8, 9]),
            ]
        )
    )
    assert list(result.data) == [ENV]
    assert [item["테마"] for item in result.data[ENV]] == ["환경 ", " 환경", ENV]
    assert (result.skipped_themes, result.skipped_items) == (0, 0)


def test_a_row_with_values_only_in_unread_columns_is_an_empty_row() -> None:
    """빈 행은 읽는 열(머리에서 찾은 열)만으로 가른다(가지 리뷰 N2) — 「공시」·머리 없는 열에만 값이 있으면 빈 행."""
    only_disclosure: list[object] = [None] * 14
    only_disclosure[12] = "가상 공시"
    beyond: list[object] = [None] * 16
    beyond[15] = "머리 없는 열"
    result = outcome(s.book([s.row(1, ENV, "가상", [1, 2, 3]), only_disclosure, beyond]))
    assert (result.item_count, result.skipped_empty_rows) == (1, 2)


def amplified(text: str, rows: int, *, theme: str = ENV) -> bytes:
    """공유 문자열 하나(text)를 행마다 읽는 글자 칸 아홉(항목·분류 셋·입력 방식·단위·연도 둘·메모)이 가리키는 xlsx —
    가지 리뷰 B1 의 꼴(작은 파일이 큰 응답을 짓는다). 시트·sharedStrings 를 손으로 적는다(openpyxl 은 글을 칸마다
    따로 적는다)."""
    head = [
        "ID",
        "테마",
        "항목",
        "대분류",
        "중분류",
        "소분류",
        "입력 방식",
        "단위",
        "2023년",
        "2024년",
        "메모",
        "핵심데이터",
    ]
    strings = [*head, theme, "Y", text]
    theme_at, flag_at, text_at = len(head), len(head) + 1, len(head) + 2

    def cell(column: int, row: int, value: str) -> str:
        return f'<c r="{chr(65 + column)}{row}" t="s"><v>{value}</v></c>'

    lines = ['<row r="1">' + "".join(cell(c, 1, str(c)) for c in range(len(head))) + "</row>"]
    for r in range(2, rows + 2):
        cells = [f'<c r="A{r}"><v>{r}</v></c>', cell(1, r, str(theme_at))]
        cells += [cell(c, r, str(text_at)) for c in range(2, 11)]
        cells.append(cell(11, r, str(flag_at)))
        lines.append(f'<row r="{r}">' + "".join(cells) + "</row>")
    declaration = '<?xml version="1.0" encoding="UTF-8"?>'
    sheet = f'{declaration}<worksheet xmlns="{s.NS}"><sheetData>{"".join(lines)}</sheetData></worksheet>'
    sst = (
        f'{declaration}<sst xmlns="{s.NS}" count="{len(strings)}" uniqueCount="{len(strings)}">'
        + "".join(f"<si><t>{each}</t></si>" for each in strings)
        + "</sst>"
    )
    base = s.book([["가상"]])
    items = s.entries(base)
    types = items[s.CONTENT_TYPES].replace(
        b"</Types>",
        b'<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.'
        b'spreadsheetml.sharedStrings+xml"/></Types>',
    )
    rels = items["xl/_rels/workbook.xml.rels"].replace(
        b"</Relationships>",
        b'<Relationship Id="rIdS" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        b'sharedStrings" Target="sharedStrings.xml"/></Relationships>',
    )
    return s.rezip(
        base,
        replace={s.SHEET: sheet.encode(), s.CONTENT_TYPES: types, "xl/_rels/workbook.xml.rels": rels},
        add={s.STRINGS: sst.encode()},
    )


def test_one_long_shared_string_behind_many_cells_is_a_long_cell_at_the_first_long_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """작은 파일이 큰 응답을 짓는 꼴(B1a): 칸 글자가 MAX_CELL_CHARS 를 넘으면 그 칸에서 long_cell(행·열 번호, 값 0).
    일의 양으로 잼(DV8): 시트의 MAX_ITEMS 행 중 첫 긴 칸의 행(2)까지만 읽는다."""
    text = "A" * 500_000
    data = amplified(text, MAX_ITEMS)
    assert len(data) < MAX_BYTES
    given = rows_given(monkeypatch)
    rejection = refused(data)
    assert given[0] == 2  # 머리 + 첫 데이터 행 — 그 너머는 읽지 않음
    assert (rejection.kind, rejection.row, rejection.column) == ("long_cell", 2, 3)
    assert rejection.message == "2행 3열 칸의 글이 너무 길어요 — 2,000자 안으로 줄여 주세요."
    assert "AAAA" not in rejection.message


def test_the_cell_length_limit_is_inclusive() -> None:
    (item,) = read(s.book([s.row(1, ENV, "가" * MAX_CELL_CHARS, [1, 2, 3])]))
    assert len(item["항목"]) == MAX_CELL_CHARS
    rejection = refused(s.book([s.row(1, ENV, "가" * (MAX_CELL_CHARS + 1), [1, 2, 3])]))
    assert (rejection.kind, rejection.row, rejection.column) == ("long_cell", 2, 3)


def test_short_strings_reused_over_the_options_limit_stop_as_converted_too_large_at_that_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """칸마다 상한 안이어도 실을 글자·수 합이 옵션 상한을 넘으면 모으는 자리에서 멈춘다(B1b).
    일의 양으로 잼(DV8): 넘긴 그 행까지만 읽는다."""
    text = "B" * MAX_CELL_CHARS
    data = amplified(text, MAX_ITEMS)
    given = rows_given(monkeypatch)
    rejection = refused(data)
    per_item = 9 * MAX_CELL_CHARS
    assert given[0] == 2 + OPTIONS_MAX_OCTETS // per_item < MAX_ITEMS  # 넘긴 행 너머는 읽지 않음
    assert rejection.kind == "converted_too_large" and rejection.column is None
    assert rejection.row == 2 + OPTIONS_MAX_OCTETS // per_item  # 넘긴 그 행(엑셀 번호)
    assert rejection.message == "읽은 항목이 너무 많아 한 번에 검증할 수 없어요 — 환경 테마 줄을 나눠 올려 주세요."


def test_the_options_budget_counts_only_the_target_theme() -> None:
    """뺄 테마의 글은 싣지 않으니 세지 않는다 — 다른 테마가 커도 환경이 작으면 읽힌다."""
    big_other = [s.row(i, OTHER_THEMES[0], "C" * MAX_CELL_CHARS, ["C" * MAX_CELL_CHARS] * 3) for i in range(100)]
    result = outcome(s.book([s.row(1, ENV, "가상", [1, 2, 3]), *big_other]))
    assert (result.item_count, result.skipped_items) == (1, 100)
    # 환경 행이 큰 다른 테마 행 뒤에 와도 같다(다른 테마 글을 합에 더하고 검사만 환경 행에서 하는 꼴을 잡는다
    # — 검증 권고 1)
    result = outcome(s.book([*big_other, s.row(1, ENV, "가상", [1, 2, 3])]))
    assert (result.item_count, result.skipped_items) == (1, 100)


def test_the_options_limit_is_the_flow_and_web_limit() -> None:
    """OPTIONS_MAX_OCTETS 는 흐름의 옵션 상한(core/flows/binding.py)·웹 model/options.ts 와 같은 값(B1b)."""
    root = Path(__file__).resolve().parents[5]
    binding = (root / "api-py/esgapi/core/flows/binding.py").read_text(encoding="utf-8")
    web = (root / "web/src/entities/dataverify/model/options.ts").read_text(encoding="utf-8")
    assert OPTIONS_MAX_OCTETS == 256 * 1024
    assert 'register_documentless("dataverify.colab@156", DataverifyBinding(), max_options_bytes=256 * 1024)' in binding
    assert "export const OPTIONS_MAX_OCTETS = 256 * 1024;" in web


def test_only_the_first_sheet_is_read() -> None:
    assert len(read(s.book([s.row(1, ENV, "가상", [1, 2, 3])], sheets=3, title="가상 첫 시트"))) == 1


def test_the_result_is_a_strict_input_with_a_company() -> None:
    data = outcome(company_book()).data
    company = {
        "name": "가상기업",
        "sasbIndustry": "가상 산업",
        "materialTopics": ["가상 토픽"],
        "reportingYear": "2024",
    }
    checked = TypeAdapter(DataverifyInput).validate_python(
        {"schemaVersion": "dataverify.input@1", "company": company, "data": data}, strict=True
    )
    assert checked["data"] == data


def test_the_flow_scope_equals_that_of_the_same_content_as_json() -> None:
    """흐름은 split_themes 로 거른 뒤 _scope 를 센다(flows/colab_156.py) — 엑셀 길(대상 테마만)과 같은 내용의 JSON
    길(테마 다섯 그대로)이 같은 셈이다."""
    from_xlsx = outcome(company_book()).data
    as_json = json.loads(json.dumps({**from_xlsx, **{t: [{"테마": t}] for t in OTHER_THEMES}}, ensure_ascii=False))
    assert _scope(split_themes(from_xlsx)) == _scope(split_themes(as_json))
    assert _scope(split_themes(from_xlsx)) == {
        "themes": [ENV],
        "itemCount": 3,
        "keyItemCount": 2,
        "years": ["2022", "2023", "2024"],
    }


def test_the_limits_count_items_before_the_theme_filter() -> None:
    rows = [s.row(1, ENV, "가상", [1, 2, 3])] + [s.row(i, OTHER_THEMES[0], "가상", [1, 2, 3]) for i in range(MAX_ITEMS)]
    rejection = refused(s.book(rows))
    assert (rejection.kind, rejection.row, rejection.column) == ("too_many_rows", MAX_ITEMS + 2, None)
    assert outcome(s.book(rows[:MAX_ITEMS])).skipped_items == MAX_ITEMS - 1  # 분모: 상한 그대로는 받는다
    assert MAX_ITEMS == 2_000


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
    assert read(with_binary_parts(base())) == read(base())


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
    ("data", "kind", "row", "column", "message"),
    [
        (b"", "not_xlsx", None, None, "엑셀 파일을 열지 못했어요 — EDK 인벤토리 양식을 .xlsx 로 저장해 올려 주세요."),
        (b"{}", "not_xlsx", None, None, "엑셀 파일을 열지 못했어요 — EDK 인벤토리 양식을 .xlsx 로 저장해 올려 주세요."),
        (
            s.book([s.row(1, ENV, "가상", [1, 2, 3])], head=[h for h in s.header() if h != "단위"]),
            "bad_header",
            1,
            None,
            "1행에서 EDK 인벤토리 양식의 열 이름을 찾지 못했어요 — 첫 행을 고치지 말고 올려 주세요.",
        ),
        (
            s.book([], head=()),
            "bad_header",
            1,
            None,
            "1행에서 EDK 인벤토리 양식의 열 이름을 찾지 못했어요 — 첫 행을 고치지 말고 올려 주세요.",
        ),
        (
            s.book([[*s.row(1, ENV, "가상", [1, 2, 3]), "가상"]], head=[*s.header(), " 테마 "]),
            "bad_header",
            1,
            15,
            "1행에서 EDK 인벤토리 양식의 열 이름을 찾지 못했어요 — 첫 행을 고치지 말고 올려 주세요.",
        ),
        (
            s.book([s.row(1, ENV, "가상", [1, 2, 3, 4])], head=s.header(("2022", "2023", "2024", "2023"))),
            "bad_header",
            1,
            12,
            "1행에서 EDK 인벤토리 양식의 열 이름을 찾지 못했어요 — 첫 행을 고치지 말고 올려 주세요.",
        ),
        (
            s.book([s.row(1, ENV, "가상", [])], head=s.header(())),
            "bad_header",
            1,
            None,
            "1행에서 EDK 인벤토리 양식의 열 이름을 찾지 못했어요 — 첫 행을 고치지 말고 올려 주세요.",
        ),
        (
            s.book([s.header(), s.row(1, ENV, "가상", [1, 2, 3])], head=["가상 표 제목"]),
            "bad_header",
            1,
            None,
            "1행에서 EDK 인벤토리 양식의 열 이름을 찾지 못했어요 — 첫 행을 고치지 말고 올려 주세요.",
        ),
        (
            s.book([s.row(1, ENV, "가상", [1, 2, 3]), s.row(2, ENV, "가상", [1, True, 3])]),
            "bad_cell",
            3,
            10,
            "3행 10열에 날짜나 참/거짓 칸이 있어요 — 숫자나 글자로 바꿔 주세요.",
        ),
        (
            s.book([s.row(1, ENV, "가상", [1, 2, datetime.date(2024, 1, 1)])]),
            "bad_cell",
            2,
            11,
            "2행 11열에 날짜나 참/거짓 칸이 있어요 — 숫자나 글자로 바꿔 주세요.",
        ),
        (
            s.book([s.row(1, ENV, "가상", [1, 2, 3]), s.row(2, None, "가상", [1, 2, 3])]),
            "no_theme",
            3,
            2,
            "3행의 테마 칸이 비어 있어요.",
        ),
        (s.book([s.row(1, 7, "가상", [1, 2, 3])]), "no_theme", 2, 2, "2행의 테마 칸이 비어 있어요."),
        (s.book([s.row(1, "  ", "가상", [1, 2, 3])]), "no_theme", 2, 2, "2행의 테마 칸이 비어 있어요."),
        (s.book([[None] * 14] * 5), "no_rows", None, None, "항목이 하나도 없어요 — 2행부터 항목을 채워 올려 주세요."),
        (
            s.book([s.row(1, OTHER_THEMES[0], "가상", [1, 2, 3])]),
            "no_target_theme",
            None,
            None,
            "검증하는 테마의 항목이 없어요 — 환경 테마 줄이 든 파일을 올려 주세요.",
        ),
        (
            s.book([s.row(i, ENV, "가상", [1, 2, 3]) for i in range(MAX_ITEMS + 1)]),
            "too_many_rows",
            MAX_ITEMS + 2,
            None,
            "항목이 너무 많아요 — 파일 하나에 2,000개까지예요.",
        ),
    ],
    ids=[
        "empty",
        "json",
        "missing",
        "empty_sheet",
        "duplicate_column",
        "duplicate_year",
        "no_year",
        "header_in_row_2",
        "bool",
        "date",
        "theme_empty",
        "theme_number",
        "theme_blank",
        "no_rows",
        "no_target_theme",
        "2001",
    ],
)
def test_each_rejection_has_its_kind_row_column_and_sentence(
    data: bytes, kind: str, row: int | None, column: int | None, message: str
) -> None:
    rejection = refused(data)
    assert (rejection.kind, rejection.row, rejection.column, rejection.message) == (kind, row, column, message)


def test_a_datetime_or_time_cell_is_a_bad_cell_and_the_same_in_an_ignored_column_is_not() -> None:
    for value in (datetime.datetime(2024, 1, 1, 9, 0), datetime.time(9, 0)):
        assert refused(s.book([s.row(1, ENV, "가상", [1, value, 3])])).kind == "bad_cell"
    (item,) = read(s.book([s.row(1, ENV, "가상", [1, 2, 3], disclosure=datetime.date(2024, 1, 1))]))
    assert "공시" not in item  # 분모: 읽지 않는 열의 날짜는 지난다


def test_a_number_that_is_not_finite_is_a_bad_cell() -> None:
    """openpyxl 은 `1E999` 를 float inf 로 읽는다 — JSON 에 실을 수 없어 거절한다."""
    sheet = s.entries(base())[s.SHEET].replace(b"<v>110</v>", b"<v>1E999</v>")
    assert b"1E999" in sheet
    rejection = refused(s.rezip(base(), replace={s.SHEET: sheet}))
    assert (rejection.kind, rejection.row, rejection.column) == ("bad_cell", 2, 10)


def test_rejection_messages_never_carry_cell_values() -> None:
    for data in (
        s.book([s.row(1, ENV, SECRET, [1, True, 3])]),
        s.book([s.row(1, None, SECRET, [1, 2, 3])]),
        s.book([s.row(1, SECRET, SECRET, [1, 2, 3])]),
        s.book([s.row(1, ENV, SECRET, [1, 2, 3])], head=[*s.header(), "ID"]),
        s.book([s.row(i, ENV, SECRET, [1, 2, 3]) for i in range(MAX_ITEMS + 1)]),
    ):
        assert SECRET not in refused(data).message


def test_too_large_bytes_are_refused_before_opening() -> None:
    rejection = refused(b"PK" + b"\0" * edk_xlsx.MAX_BYTES)
    assert (rejection.kind, rejection.row) == ("too_large", None)
    assert rejection.message == "파일이 너무 커요 — 1MB 이하로 올려 주세요."


def test_the_byte_limit_is_not_above_the_central_directory_limit_of_zip_guard() -> None:
    """zip_guard(translation/tools/zip_guard.py)를 부르지 않는 까닭: 가운데 목록은 본문보다 클 수 없고 본문 상한이 그
    상한 이하다(감독 cd·플랫폼-서버 e7 처분 (가)). 두 소스를 글로 읽어 값을 견준다(import 0)."""
    import ast
    from pathlib import Path

    root = Path(edk_xlsx.__file__).resolve().parents[2]
    guard = ast.parse((root / "translation" / "tools" / "zip_guard.py").read_text(encoding="utf-8"))
    (value,) = [
        node.value
        for node in guard.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "MAX_CENTRAL_DIRECTORY"
        and node.value is not None
    ]
    assert isinstance(value, ast.BinOp) and isinstance(
        value.op, ast.Mult
    )  # 지금 꼴 `1024 * 1024` — 바뀌면 여기를 고친다
    assert isinstance(value.left, ast.Constant) and isinstance(value.right, ast.Constant)
    left, right = value.left.value, value.right.value
    assert isinstance(left, int) and isinstance(right, int)
    assert left * right >= edk_xlsx.MAX_BYTES


# ── 공격(상한 안에서 거절) — test_glossary_xlsx.py 에서 옮김 ──


def test_not_a_zip_and_a_zip_without_content_types_are_not_xlsx() -> None:
    assert refused(b"PK\x03\x04 virtual").kind == "not_xlsx"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("a.txt", "virtual")
    assert refused(out.getvalue()).kind == "not_xlsx"


def test_too_many_entries_are_unsafe() -> None:
    extra = {f"docProps/x{i}.bin": b"" for i in range(edk_xlsx.MAX_ENTRIES)}
    assert refused(s.rezip(base(), add=extra)).kind == "unsafe_xlsx"


def test_an_entry_or_the_declared_sum_over_the_limit_is_unsafe() -> None:
    one = s.rezip(base(), add={"xl/media/big.bin": b"\0" * (edk_xlsx.MAX_ENTRY_BYTES + 1)})
    assert refused(one).kind == "unsafe_xlsx"
    under = b"\0" * (edk_xlsx.MAX_ENTRY_BYTES - 1024)
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
    assert MAX_XML_ELEMENTS == 500_000


def test_the_nesting_depth_is_capped() -> None:
    assert len(read(nested(MAX_XML_DEPTH))) == 2
    assert refused(nested(MAX_XML_DEPTH + 1)).kind == "unsafe_xlsx"
    assert MAX_XML_DEPTH == 64


def test_a_million_deep_sheet_is_refused_before_openpyxl(monkeypatch: pytest.MonkeyPatch) -> None:
    """★B: 뿌리에서 멈추는 훑기로는 openpyxl 에 가 2.4초·RSS +592MB 였던 파일(12KB).
    일의 양으로 잼(DV8): 훑기에서 거절, load_workbook 0회(분모 — 정상 파일은 1회)."""
    opened = openpyxl_opened(monkeypatch)
    assert len(read(base())) == 2
    assert opened[0] == 1
    data = s.rezip(base(), replace={s.SHEET: s.deep_sheet(1_000_000)})
    assert refused(data).kind == "unsafe_xlsx"
    assert opened[0] == 1


def test_a_cell_far_down_stops_at_the_scanned_row_limit() -> None:
    """read_only 는 빈 행 번호마다 빈 행을 내준다 — 1,048,576행 칸 하나도 MAX_SCANNED_ROWS 에서 멈춘다."""
    rejection = refused(s.rezip(base(), replace={s.SHEET: s.far_row_sheet(1_048_576)}))
    assert (rejection.kind, rejection.row) == ("too_many_scanned_rows", None)


def test_ten_thousand_and_one_blank_rows_are_refused_and_ten_thousand_are_read() -> None:
    far = refused(s.rezip(base(), replace={s.SHEET: s.far_row_sheet(MAX_SCANNED_ROWS + 1)}))
    assert far.kind == "too_many_scanned_rows"
    near = refused(s.rezip(base(), replace={s.SHEET: s.far_row_sheet(MAX_SCANNED_ROWS)}))
    assert (near.kind, near.row) == ("no_theme", MAX_SCANNED_ROWS)  # 10,000행째까지 훑었다


def test_the_workbook_is_closed_even_when_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []
    real = edk_xlsx.load_workbook

    def tracking(*args: object, **kwargs: object) -> object:
        workbook = real(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        original = workbook.close

        def close() -> None:
            closed.append(True)
            original()

        workbook.close = close  # pyright: ignore[reportAttributeAccessIssue]
        return workbook

    monkeypatch.setattr(edk_xlsx, "load_workbook", tracking)
    refused(s.book([s.row(1, None, "가상", [1, 2, 3])]))
    read(base())
    assert closed == [True, True]


def test_a_memory_error_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def out_of_memory(*_: object, **__: object) -> object:
        raise MemoryError

    monkeypatch.setattr(edk_xlsx, "load_workbook", out_of_memory)
    with pytest.raises(MemoryError):
        read_edk(base())


def test_no_corrupted_byte_raises() -> None:
    """어떤 바이트를 받아도 예외가 아니라 갈래다(test_docx_reader 꼴 — 자리마다 비트를 뒤집는다)."""
    data = with_binary_parts(base())
    for position in range(0, len(data), max(1, len(data) // 300)):
        broken = bytearray(data)
        broken[position] ^= 1 << (position % 8)
        assert isinstance(read_edk(bytes(broken)), EdkRead | EdkRejected)
    assert isinstance(read_edk(data[: len(data) // 2]), EdkRejected)


# ── 검증 B1: openpyxl 은 파트를 관계의 Target 으로 연다 ──

SHEET_DAT = "xl/worksheets/sheet1.dat"


def test_a_sheet_moved_to_an_odd_name_without_override_is_still_read() -> None:
    """분모: openpyxl 은 이름·꼴이 xml 이 아닌 시트도 워크북 rels 의 Target 으로 연다(그래서 훑어야 한다)."""
    assert len(read(s.moved(base(), s.SHEET, SHEET_DAT))) == 2


def test_a_doctype_or_a_deep_sheet_moved_to_an_odd_name_is_unsafe(monkeypatch: pytest.MonkeyPatch) -> None:
    """깊은 시트는 훑기에서 거절 — 일의 양으로 잼(DV8): load_workbook 0회(분모 — 옮긴 정상 시트는 1회)."""
    opened = openpyxl_opened(monkeypatch)
    assert len(read(s.moved(base(), s.SHEET, SHEET_DAT))) == 2
    assert opened[0] == 1
    sheet = s.entries(base())[s.SHEET]
    assert refused(s.moved(base(), s.SHEET, SHEET_DAT, content=s.with_doctype(sheet))).kind == "unsafe_xlsx"
    assert refused(s.moved(base(), s.SHEET, SHEET_DAT, content=s.deep_sheet(1_000_000))).kind == "unsafe_xlsx"
    assert opened[0] == 1


def test_styles_moved_to_an_odd_name_with_a_doctype_is_unsafe() -> None:
    styles = s.entries(base())["xl/styles.xml"]
    data = s.moved(base(), "xl/styles.xml", "xl/styles.dat", content=s.with_doctype(styles))
    assert refused(data).kind == "unsafe_xlsx"


def test_a_sheet_whose_relationship_type_lies_as_an_image_is_still_scanned(monkeypatch: pytest.MonkeyPatch) -> None:
    """짝(감독 63): Type 만 image 로 속이면 바이너리 관계로 빠질 듯하지만 openpyxl 은 시트를 r:id 로 찾고 Type 을 보지
    않아 그대로 연다(실측 — 분모). 워크북 rels 는 Type 과 상관없이 훑으므로 공격 시트는 거절, openpyxl 앞에서.
    일의 양으로 잼(DV8): 깊은 시트에 load_workbook 0회(분모 — 속인 정상 시트는 1회)."""
    opened = openpyxl_opened(monkeypatch)
    sheet = s.entries(base())[s.SHEET]
    assert len(read(s.moved(base(), s.SHEET, SHEET_DAT, rel_type=s.IMAGE_TYPE))) == 2
    assert opened[0] == 1
    lie = s.moved(base(), s.SHEET, SHEET_DAT, content=s.with_doctype(sheet), rel_type=s.IMAGE_TYPE)
    assert refused(lie).kind == "unsafe_xlsx"
    deep = s.moved(base(), s.SHEET, SHEET_DAT, content=s.deep_sheet(1_000_000), rel_type=s.IMAGE_TYPE)
    assert refused(deep).kind == "unsafe_xlsx"
    assert opened[0] == 1


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
def test_a_utf16_part_with_a_doctype_or_deep_nesting_is_unsafe(codec: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """UTF-16(BOM · BOM 없는 LE `<\\x00` · BOM 없는 BE `\\x00<`)도 XML 로 보고 expat 이 읽는다. 이름이 .dat 여도.
    깊은 시트는 항목 크기 상한(MAX_ENTRY_BYTES)에서 거절 — openpyxl 0회(DV8 — 분모: 정직한 UTF-16 시트는 1회)."""
    opened = openpyxl_opened(monkeypatch)

    def utf16(text: str) -> bytes:
        return text.encode(codec)

    honest = s.entries(base())[s.SHEET].decode().replace('encoding="UTF-8"', 'encoding="UTF-16"')
    assert len(read(s.rezip(base(), replace={s.SHEET: utf16(honest)}))) == 2  # 짝: 정직한 UTF-16 시트는 읽힌다
    assert opened[0] == 1
    doctype = s.with_doctype(b'<?xml version="1.0" encoding="UTF-16"?><a/>').decode()
    assert refused(s.rezip(base(), add={"evil.dat": utf16(doctype)})).kind == "unsafe_xlsx"
    deep = s.deep_sheet(1_000_000).decode().replace('encoding="UTF-8"', 'encoding="UTF-16"')
    sheet = s.moved(base(), s.SHEET, SHEET_DAT, content=utf16(deep))
    assert refused(sheet).kind == "unsafe_xlsx"
    assert opened[0] == 1


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


LARGEST_ATTRIBUTE_LIST = 466_012
"""압축해 MAX_BYTES(1MiB) 안에 드는 가장 많은 속성(이름 a0…, 이 시험의 base() 로 DVX1 러너 실측 — glossary 는
466,137). 표지 간격 상한 없이 handler 에서 세면 이 사전만으로 0.66초·tracemalloc 106MB·RSS +180MB 였다."""


def huge_attribute_list(attributes: int) -> bytes:
    attrs = b"".join(b' a%d=""' % i for i in range(attributes))
    return s.rezip(base(), add={PAD: b"<x" + attrs + b"/>"})


def test_one_element_with_the_largest_attribute_list_is_refused_before_its_dict_is_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """가지 리뷰 처분(속성 셈) + 표지 간격 상한: 사전을 짓기 전에 거절해 메모리가 늘지 않는다. 벽시계 문턱은 뺐다(DV8
    — 부하 때 빨강). 막으려는 것은 tracemalloc 정점과 훑기에서의 거절(load_workbook 0회, 분모 정상 파일 1회)이 잰다."""
    opened = openpyxl_opened(monkeypatch)
    assert len(read(base())) == 2
    assert opened[0] == 1
    data = huge_attribute_list(LARGEST_ATTRIBUTE_LIST)
    assert len(data) <= 1024 * 1024  # 분모: 바이트 상한 안 — 훑기까지 간다
    tracemalloc.start()
    try:
        assert refused(data).kind == "unsafe_xlsx"
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 60 * 1024 * 1024, peak  # 사전을 지었다면 100MB 를 넘는다
    assert opened[0] == 1  # 훑기(_scan)에서 거절 — openpyxl 에 닿지 않음


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
    data = padded_nodes(NODE_UNITS[kind], 1_000_000)  # 7MB 안(항목 크기 상한 아래 — 예산으로 거절)
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
    one = s.book([s.row(1, ENV, "가상 직접 배출량", [100, 110, 120])])
    items = s.entries(one)
    sheet = items[s.SHEET]
    at = sheet.index(b">") + 1
    note = '<!-- 가상 메모 --><?mso-application progid="Excel.Sheet"?>'.encode()
    noted = sheet[:at] + note + sheet[at:]
    assert read(s.rezip(one, replace={s.SHEET: noted})) == read(one)


def test_the_span_of_the_last_short_chunk_is_measured_to_the_end_of_the_data() -> None:
    """사소(가지 리뷰): 마지막 조각은 짧다 — 먹인 끝을 조각 크기로 올려 세면 상한 안의 간격을 넘었다고 본다. 마지막
    이벤트(자리 4 의 주석)에서 끝까지가 MAX_XML_SPAN − 2 인 항목(길이는 상한 + 2)은 받고, 끝을 MAX_XML_SPAN 너머로
    늘리면 거절."""
    head = b"<a/><!---->"
    inside = s.rezip(base(), add={PAD: head + b" " * (MAX_XML_SPAN + 2 - len(head))})
    assert len(read(inside)) == 2
    outside = s.rezip(base(), add={PAD: head + b" " * (MAX_XML_SPAN + 5)})
    assert refused(outside).kind == "unsafe_xlsx"


def test_an_external_target_named_part_is_scanned(monkeypatch: pytest.MonkeyPatch) -> None:
    """검증 B2: 시트 관계를 TargetMode External·Target="evil.dat" 로 바꾸고 뿌리에 evil.dat 를 두면 openpyxl 은 그
    이름으로 연다 — 내용으로 고르므로 이미 훑었다. 일의 양으로 잼(DV8): 둘 다 load_workbook 0회(분모 — 정상 파일
    1회)."""
    opened = openpyxl_opened(monkeypatch)
    assert len(read(base())) == 2
    assert opened[0] == 1
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
        assert refused(out.getvalue()).kind == "unsafe_xlsx"
    assert opened[0] == 1


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
    real = edk_xlsx.load_workbook

    def counting(*args: object, **kwargs: object) -> object:
        calls.append(args)
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(edk_xlsx, "load_workbook", counting)
    return calls


def test_two_entries_with_the_same_name_are_unsafe(monkeypatch: pytest.MonkeyPatch) -> None:
    """같은 이름이 둘이면 zipfile 은 조용히 뒤의 것을 준다 — 무엇을 읽었는지 말할 수 없으므로 거절."""
    out = io.BytesIO()
    with pytest.warns(UserWarning, match="Duplicate name"), zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in s.entries(base()).items():
            archive.writestr(name, content)
        archive.writestr(s.SHEET, s.entries(s.book([s.row(9, ENV, "가상둘째", [1, 2, 3])]))[s.SHEET])
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


# ── 양식(template·workbook — 발주서 2-1b) ──


def test_the_template_is_the_same_bytes_every_time_and_reads_as_its_one_example() -> None:
    first = edk_xlsx.template(2025)
    time.sleep(1.1)  # zip 항목 시각은 2초 단위 — 시각을 고정하지 않으면 다음 판에서 바뀐다
    assert edk_xlsx.template(2025) == first
    assert edk_xlsx.template(2024) != first
    result = outcome(first)
    assert (result.item_count, result.skipped_themes, result.years) == (1, 0, ("2023", "2024", "2025"))
    (item,) = result.data[ENV]
    assert (item["테마"], item["핵심데이터"], item["values"]) == (ENV, "Y", {"2023": 1200, "2024": 1150, "2025": 1100})


def test_the_template_has_the_data_sheet_with_fourteen_headers_and_a_guide_sheet() -> None:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(edk_xlsx.template(2025)))
    data, guide = workbook.worksheets
    assert (data.title, guide.title) == ("인벤토리 데이터", "작성 안내")
    assert [c.value for c in data[1]] == s.header(("2023", "2024", "2025"))
    assert data.max_row == 2
    notes = "\n".join(str(r[0].value) for r in guide.iter_rows())
    assert "1MB" in notes and "2,000" in notes and "환경" in notes
    assert "6. 칸 하나의 글은 2,000자 안으로 적어 주세요." in notes  # 가지 리뷰 B1a 의 상한(디자인 74 권고)
    with zipfile.ZipFile(io.BytesIO(edk_xlsx.template(2025))) as archive:
        assert {i.date_time for i in archive.infolist()} == {edk_xlsx.TEMPLATE_DATE}
        assert b"1980-01-01T00:00:00Z" in archive.read("docProps/core.xml")


def test_a_filled_template_is_read_with_its_rows() -> None:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(edk_xlsx.template(2024)))
    workbook.worksheets[0].append(s.row("가상-2", ENV, "가상 폐기물", [1, 2, 3], key="N"))
    workbook.worksheets[0].append(s.row("가상-3", OTHER_THEMES[0], "가상 인원", [4, 5, 6]))
    out = io.BytesIO()
    workbook.save(out)
    result = outcome(out.getvalue())
    assert [i["ID"] for i in result.data[ENV]] == [1, "가상-2"]
    assert (result.skipped_themes, result.skipped_items) == (1, 1)


def test_header_row_matches_the_support_header() -> None:
    """도구의 머리(header_row)와 시험의 머리(s.header)는 따로 적었다 — 같아야 한다."""
    for years in ((), ("2024",), ("2022", "2023", "2024")):
        assert list(edk_xlsx.header_row(years)) == s.header(years)
