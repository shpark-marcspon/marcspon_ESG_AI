"""S2 읽기 대조: 같은 지어낸 xlsx 바이트를 `pd.read_excel`(openpyxl)과 우리 읽개 + `frames.read_frame` 으로 읽어 같다.

**시험만 `io` 를 쓴다**(엔진은 xlsx 를 열지 않는다 — 처분 ⑤). 견줌은 `pdcompat.legacy_strings()` 안의 `pd.read_excel`
의 길 (`ExcelFile.parse` — `pandas_frame` 주석)과 한다: pandas 3.0.6 의 글 열 `str` 이 아니라 코랩이 돈 2.x 의
`object` 를 내는 문맥이다(frames.py 머리). 이 시험은 pandas 판 고르기에 닿는다(개정 1 B2·개정 2): 경우에 **글 칸의 빈
칸**(가운데·끝)을 넣고, 두 frame 에 코랩 꼴 `astype(str)` 을 `colab_str` 로 건 결과가 같고 빈 칸이 `'nan'` 임을
단언한다(xlsx 의 빈 칸은 `'None'` 이 되지 않는다 — critic 2 B1. `'None'` 은 파이썬 `None` 이 든 object Series 뿐이고
S8 이 본다).
"""

import io
from collections.abc import Mapping, Sequence

import pandas as pd
import pytest

from esgapi.inventory.engines.scope3.colab_157.frames import read_frame
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_str, legacy_strings
from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, sheet, workbook, xlsx_bytes
from esgapi.inventory.tests.s3sheets_support import number, text
from esgapi.inventory.tools.scope3_sheets.grid import FormulaCell, Sheet, Workbook
from esgapi.inventory.tools.xlsx_reader import read_workbook

C1_ROWS: dict[int, list[Value]] = {
    2: ["카테고리 1 가상 안내", None, None],
    4: [
        "*국가",
        "*사업장",
        "*품목군",
        "*상세 품목명/서비스명",
        "거래처명(선택)",
        "연간 입력",
        "월별 지출금액",
        None,
        "비고(선택)",
    ],
    5: [None, None, None, None, None, "연간지출금액(원)", "1월", "2월", None],
    6: ["가상국", "가상사업장", "사무용품", "가상 A4 용지", None, 9100000, None, None, "NA"],
    7: ["가상국", "가상사업장", None, "가상 노트북", "가상상사", None, 9.5, 9000, None],
    9: ["가상국", None, "가상군", "가상 토너", None, 9.25, None, None, "None"],
}
USEPA_ROWS: dict[int, list[Value]] = {
    1: ["가상 구매 계수 표"],
    3: [
        "품목군",
        "상세 카테고리",
        "한국어 매핑 키워드",
        "NAICS 코드",
        "NAICS Title",
        "EF (kgCO2e/USD)",
        "EF (kgCO2e/KRW) 2025년말 기준 (9,400 KRW/USD)",
    ],
    4: ["가상군", "가상세부", "가상키워드, 가상", 9001, "Virtual Paper Mills", 0.9, 0.00009],
    5: ["가상군", None, None, "9002", "Virtual Office Supplies", 9.1, None],
    6: [None, None, None, None, None, None, None],
    7: ["가상군2", "가상세부2", "가상", 9003, None, 9.0, "가상"],
}


def formula_sheet() -> Sheet:
    base = sheet("F", {1: ["가", "나"], 2: [9, 9.5]})
    cells = dict(base.cells)
    cells["A3"] = FormulaCell("A2*2", None, number("99"))
    cells["B3"] = FormulaCell("B2*2", None, None)  # 저장된 값 없음 → NaN
    cells["C3"] = FormulaCell('"가"&"나"', None, text("가나"))
    return Sheet("F", cells, ("A1:B1",), ())


CASES: Mapping[str, Sheet] = {
    "c1-template": sheet("C1_구매품서비스", C1_ROWS),
    "usepa": sheet("구매_USEPA", USEPA_ROWS),
    "offset-column-b": sheet("B", {2: ["가상", None, 9], 3: [None, "nan", 9.5]}, first_column=2),
    "text-blanks-middle-and-end": sheet(
        "T", {1: ["h1", "h2", "h3"], 2: ["가상a", None, "가상b"], 3: [None, "가상c", None], 4: ["가상d"]}
    ),
    "formula-and-merge": formula_sheet(),
    "numbers-as-text": sheet("N", {1: ["h"], 2: ["9"], 3: ["9.5"], 4: [9]}),
    # 끝 줄들에 빈 글 칸만 있다 — openpyxl 엔진은 끝 빈 줄을 걷는다(P10 이 문다).
    "trailing-empty-text-rows": sheet("E", {1: ["h1", "h2"], 2: ["가상", 9], 3: ["", ""], 4: [""]}),
}
type Read = tuple[int | None, int | None, bool]  # header, nrows, dtype=str
READS: Sequence[Read] = (
    (None, None, False),
    (None, 20, False),
    (None, 2, False),
    (0, None, False),
    (2, None, False),
    (2, None, True),
    (0, None, True),
)


def pandas_frame(data: bytes, name: str, read: Read) -> pd.DataFrame:
    header, nrows, as_text = read
    # `pd.read_excel(io, …)` 은 `ExcelFile(io).parse(…)` 를 부른다(pandas 3.0.6 `io/excel/_base.py`).
    # `read_excel` 의 타입이 스텁에서 덜 풀려(xlrd·pyxlsb 타입) pyright strict 가 막으므로 같은 길을 바로 부른다.
    with legacy_strings(), pd.ExcelFile(io.BytesIO(data), engine="openpyxl") as book:
        if as_text:
            return book.parse(name, header=header, nrows=nrows, dtype=str)
        return book.parse(name, header=header, nrows=nrows)


def ours(case: Sheet, read: Read) -> pd.DataFrame:
    header, nrows, as_text = read
    return read_frame(case, header=header, nrows=nrows, as_text=as_text)


def read_back(data: bytes) -> Sheet:
    book = read_workbook(data)
    assert isinstance(book, Workbook), book
    return book.sheets[0]


@pytest.mark.parametrize("name", list(CASES))
def test_frames_equal_pandas_read_excel(name: str) -> None:
    case = CASES[name]
    data = xlsx_bytes(workbook(case))
    back = read_back(data)
    compared = 0
    for read in READS:
        try:
            want = pandas_frame(data, case.name, read)
        except ValueError:
            with pytest.raises(ValueError):
                ours(back, read)
            continue
        got = ours(back, read)
        assert got.equals(want), (read, got.to_dict("list"), want.to_dict("list"))
        assert list(got.columns) == list(want.columns), read
        assert [str(t) for t in got.dtypes] == [str(t) for t in want.dtypes], read
        for column in got.columns:
            assert colab_str(got[column]).tolist() == colab_str(want[column]).tolist(), (read, column)
        compared += 1
    assert compared >= 5  # 경우마다 적어도 다섯 읽기를 견준다(분모)


def test_the_case_table_covers_the_reads_the_colab_uses() -> None:
    assert len(CASES) == 7
    assert len(READS) == 7


def test_text_blanks_read_as_nan_and_colab_str_makes_them_the_text_nan() -> None:
    """글 칸의 빈 칸(가운데·끝): 두 frame 다 NaN, `colab_str` 뒤 `'nan'`(2.3.3 의 `astype(str)` 과 같은 글자)."""
    case = CASES["text-blanks-middle-and-end"]
    data = xlsx_bytes(workbook(case))
    back = read_back(data)
    for as_text in (False, True):
        want = pandas_frame(data, case.name, (0, None, as_text))
        got = read_frame(back, header=0, as_text=as_text)
        assert colab_str(got["h2"]).tolist() == colab_str(want["h2"]).tolist() == ["nan", "가상c", "nan"]
        assert colab_str(got["h3"]).tolist() == ["가상b", "nan", "nan"]
        assert "None" not in colab_str(got["h1"]).tolist()
