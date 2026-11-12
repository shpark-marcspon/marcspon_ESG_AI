"""S5 회사별 자동매칭 폴백(코랩 `_fill_missing_from_company_mapping` `:6326-6370`): 빈 칸(NaN·""·"none")만 채운다.

칸 값은 openpyxl(`data_only=True`)의 꼴: 수식 칸은 저장된 값, 수 칸은 xml 글자에 `.` 가 있으면 float(`"9.0"`), 없으면
int(`"9"`). 매핑에 안 걸린 빈 칸은 코랩 `df.loc[blank, col] = filled[blank]` 그대로 NaN 이 된다.
"""

import math
from collections.abc import Mapping

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.company_mapping import fill_missing_from_company_mapping
from esgapi.inventory.engines.scope3.colab_157.pdcompat import legacy_strings
from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, formula, sheet, sheet_cells, workbook
from esgapi.inventory.tools.scope3_sheets.grid import Cell, Sheet, Workbook

MAPPING = "회사별_폐기물매핑"
DETAIL, TARGET = "상세폐기물명", "폐기물 종류"
MAPPING_ROWS: dict[int, list[Value]] = {
    1: ["회사", "상세명", "값"],
    2: ["가상회사A", "가상 상세1", "가상폐지"],
    3: ["가상회사B", "가상 상세1", "가상다른"],
    4: ["가상회사A", "가상 상세2", 9.0],
    5: ["가상회사A", "가상 상세3", 9],
    6: ["가상회사A", "가상 상세4"],
    7: ["가상회사A", "가상 상세5"],
}
MAPPING_EXTRA: Mapping[str, Cell] = {"C6": formula("가상수식값"), "C7": formula(None)}


def template(company: Value = "가상회사A", mapping: bool = True) -> Workbook:
    sheets: list[Sheet] = [sheet("기업정보", {7: [None, None, company]})]
    if mapping:
        sheets.append(sheet_cells(MAPPING, MAPPING_ROWS, MAPPING_EXTRA))
    return workbook(*sheets)


def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            DETAIL: [
                "가상 상세1",
                " 가상 상세2 ",
                "가상 상세3",
                "가상 상세4",
                "가상 상세1",
                "가상 상세9",
                "가상 상세5",
            ],
            TARGET: [math.nan, "", "None", None, "가상기존", "", math.nan],
        },
        dtype=object,
    )


def test_only_blank_cells_are_filled() -> None:
    with legacy_strings():
        got = fill_missing_from_company_mapping(frame(), template(), MAPPING, DETAIL, [TARGET, "가상없는열"])
        values: list[object] = got.frame[TARGET].tolist()
    assert values[:5] == ["가상폐지", "9.0", "9", "가상수식값", "가상기존"]  # 4번 줄은 비지 않아 그대로
    assert all(isinstance(v, float) and math.isnan(v) for v in values[5:])  # 매핑에 없는 빈 칸·저장값 없는 수식은 NaN
    assert got.filled == frozenset({0, 1, 2, 3})


def test_the_input_frame_is_not_changed() -> None:
    original = frame()
    with legacy_strings():
        fill_missing_from_company_mapping(original, template(), MAPPING, DETAIL, [TARGET])
    assert original[TARGET].tolist()[4] == "가상기존"
    assert pd.isna(original[TARGET].tolist()[0])


def unchanged(book: Workbook, mapping_sheet: str = MAPPING) -> None:
    original = frame()
    with legacy_strings():
        got = fill_missing_from_company_mapping(original, book, mapping_sheet, DETAIL, [TARGET])
    assert got.frame is original
    assert got.filled == frozenset()


def test_a_missing_mapping_sheet_leaves_the_frame() -> None:
    unchanged(template(mapping=False))
    unchanged(template(), "회사별_교통수단매핑")


def test_another_or_blank_company_leaves_the_frame() -> None:
    unchanged(template("가상회사Z"))
    unchanged(template(None))
    unchanged(template("  "))


def test_a_filled_column_or_missing_columns_skip_the_mapping() -> None:
    full = pd.DataFrame({DETAIL: ["가상 상세1"], TARGET: ["가상기존"]}, dtype=object)
    with legacy_strings():
        got = fill_missing_from_company_mapping(full, template(), MAPPING, DETAIL, [TARGET])
        assert got.frame is full
        no_detail = fill_missing_from_company_mapping(frame(), template(), MAPPING, "가상상세", [TARGET])
        assert no_detail.filled == frozenset()
