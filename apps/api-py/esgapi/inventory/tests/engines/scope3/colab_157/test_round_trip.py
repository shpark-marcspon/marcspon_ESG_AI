"""S3C-c2 T3 왕복 흉내 — `output_files.reread` 가 실제 쓰기(덤프 쓰개 `write_result_file` = openpyxl `to_excel`)
→ `pd.read_excel(sheet_name=None)` 와 같은 frame(값·dtype)을 내는가. 코랩의 결과 파일은 두 번 왕복한다(`:8882`·
`:9360`). 여덟 판의 코랩 `result.xlsx` 칸 값 대조는 §4 [9](esg-lab 산출이 git 밖이라).
"""

import io
import math

import numpy as np
import pandas as pd
import pytest

from esgapi.inventory.engines.scope3.colab_157.output_files import Cell, OutputFiles, ResultSheet, reread, to_cell
from esgapi.inventory.engines.scope3.colab_157.pdcompat import legacy_strings
from esgapi.inventory.tests.engines.scope3.colab_157.support import c11_sheet, c14_sheet
from esgapi.inventory.tests.engines.scope3.colab_157.test_product_use_sheet import DIESEL_ROW, MWH_ROW, run_on
from esgapi.inventory.tests.scope3colab_dump import write_result_file

# 가장자리 열(이름 → 값). 우리 venv 탐침(보고 2-0 f)의 꼴 전부
EDGES: dict[str, list[Cell]] = {
    "정수로 떨어지는 float": [2.0, 3.0, 4.0],
    "NaN 섞인 정수": [1, None, 3],
    "작은 수": [1e-05, 9.410000000000001e-05, 0.0941],
    "17자리 float": [1.6863299999999999, 2.5, 3.5],
    "큰 정수": [12345678901234567, 1, 2],
    "빈 글": ["", "가상", "가상2"],
    "= 글": ["=가상식", "가상", "가상2"],
    "수·글 섞임": [1, "가상", 2.5],
    "수 꼴 글": ["1", "2", "3"],
    "수 꼴 글 + 글": ["1", "가상", "3"],
    "결측 글자": ["NA", "None", "가상"],
    "오류 글자": ["#N/A", 1, 2],
    "무한": [math.inf, 1.0, 2.0],
    "bool 만": [True, False, True],
    "bool + 빔": [True, None, False],
    "bool + 정수": [True, 1, 2],
    "bool + float": [True, 1.5, 2.5],
    "bool + 글": [True, "가상", "가상2"],
    "참거짓 글": ["True", "FALSE", "true"],
    "참거짓 글 + 빔": ["True", None, "False"],
    "참거짓 글 + 글": ["True", "가상", "False"],
    "bool + 참거짓 글": [True, "True", False],
    "모두 빔": [None, None, None],
}


def written_and_read(sheet: ResultSheet) -> pd.DataFrame:
    # `read_excel(sheet_name=None)` = 시트마다 `ExcelFile.parse`(스텁 타입이 덜 풀려 test_frames.py 와 같은 길)
    with legacy_strings(), pd.ExcelFile(io.BytesIO(write_result_file((sheet,))), engine="openpyxl") as book:
        return book.parse(sheet.name)


def assert_same(sheet: ResultSheet) -> None:
    with legacy_strings():
        ours = reread(sheet.columns, sheet.rows)
    real = written_and_read(sheet)
    assert list(ours.columns) == list(real.columns)
    assert [str(t) for t in ours.dtypes] == [str(t) for t in real.dtypes]
    assert ours.equals(real), (ours, real)


@pytest.mark.parametrize("name", list(EDGES))
def test_one_edge_column_reads_back_like_pandas(name: str) -> None:
    values = EDGES[name]
    sheet = ResultSheet("가상", ("가상 열쇠", name), tuple(("가상", v) for v in values))
    assert_same(sheet)


def test_all_edges_in_one_sheet_read_back_like_pandas() -> None:
    columns = tuple(EDGES)
    rows = tuple(tuple(EDGES[c][i] for c in columns) for i in range(3))
    assert_same(ResultSheet("가상", columns, rows))


def test_a_trailing_empty_row_is_dropped_like_pandas() -> None:
    assert_same(ResultSheet("가상", ("가", "나"), (("가상", 1), (None, None))))


def test_pipeline_result_sheets_read_back_like_pandas() -> None:
    """C11(단위환산비고 조건부 열)·C14(EF매핑점수 수 열)의 실제 결과 시트."""
    result = run_on([c11_sheet("c11_판매제품사용", MWH_ROW, DIESEL_ROW), c14_sheet("c14_프랜차이즈")])
    outputs = result.outputs
    assert isinstance(outputs, OutputFiles)
    assert [s.name for s in outputs.result] == ["C11_판매제품사용", "C14_프랜차이즈"]
    for sheet in outputs.result:
        assert_same(sheet)


def test_to_cell_turns_numpy_scalars_into_python_values() -> None:
    assert [to_cell(v) for v in (np.int64(3), np.float64(2.5), np.bool_(True), np.float64("nan"), "", None)] == [
        3, 2.5, True, None, None, None,
    ]  # fmt: skip
    assert [type(to_cell(v)) for v in (np.int64(3), np.float64(2.5), np.bool_(True))] == [int, float, bool]
