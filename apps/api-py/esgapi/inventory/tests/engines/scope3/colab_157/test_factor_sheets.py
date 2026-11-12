"""S1 계수 시트 셋의 두 단 읽기: 첫 읽기(`_load_ef_sheet(…, header_row=2)` `:338`·`:346-347`) → 자동 머리글 다시 읽기
(`_ef_auto_header_row` `:7154` · `_ef_reload_sheet_auto` `:7173` — 비지 않으면 갈음, `:7218`·`:7224`·`:7227`).

머리글 점수 = 값 있는 칸 수 + 낱말마다 20, 처음 가장 큰 줄. 아래 표는 제목 줄과 머리글 줄의 칸 수가 같아
**낱말 몫(20)만** 머리글 줄을 가른다.
"""

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.factor_book import (
    TRANSPORT_SPEND_SHEET,
    TRAVEL_SPEND_SHEET,
    WASTE_C5_SHEET,
    ef_auto_header_row,
    read_factor_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.pdcompat import legacy_strings
from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, formula, sheet, sheet_cells, workbook

WASTE_HEAD: list[Value] = ["폐기물 종류", "처리방법", "배출계수 (kgCO2eq/kg)"]
# 1행 제목(칸 셋) · 2행 머리글(칸 셋 + 낱말 둘) · 3행부터 값(칸 셋). 첫 읽기 header_row=2 는 3행을 머리글로 본다.
WASTE_ROWS: dict[int, list[Value]] = {
    1: ["가상 폐기물 계수 표", "가상 설명", "가상 비고"],
    2: WASTE_HEAD,
    3: ["가상폐지", "소각", 9.1],
    4: ["가상폐목", "매립", 9.2],
}
# 머리글 낱말이 맨 끝 줄에 있어 다시 읽기가 빈다 → 첫 읽기(3행 머리글)를 그대로.
TAIL_ROWS: dict[int, list[Value]] = {
    3: ["가상종류", "가상방법", "가상계수"],
    4: ["가상폐지", "소각", 9.1],
    5: ["처리방법", "배출계수", "가상"],
}
KRW_2025 = "EF (kgCO2e/KRW)\n2025년말 기준\n(9,400 KRW/USD)"
SPEND_HEAD: list[Value] = ["운송 구분", "NAICS 코드", "NAICS Title", "EF (kgCO2e/USD)", KRW_2025]
SPEND_ROWS: dict[int, list[Value]] = {
    1: ["가상 운송 지출 계수 표"],
    3: SPEND_HEAD,
    4: ["가상도로", 9001, "Virtual Trucking", 9.4],
    5: ["가상해상", 9002, "Virtual Deep Sea", 9.3],
}


def test_the_auto_header_row_is_decided_by_the_keyword_points() -> None:
    with legacy_strings():
        book = workbook(sheet(WASTE_C5_SHEET, WASTE_ROWS))
        assert ef_auto_header_row(book, WASTE_C5_SHEET, ["처리방법", "배출계수"]) == 1
        assert ef_auto_header_row(book, WASTE_C5_SHEET, []) == 0  # 낱말 없이는 동점 — 처음 줄(제목)
        got = read_factor_sheet(book, WASTE_C5_SHEET)
    assert (got.sheet, got.how, got.header) == (WASTE_C5_SHEET, "reloaded", 1)
    assert got.header != 2
    assert got.frame.columns.tolist() == WASTE_HEAD
    assert got.frame.to_dict("records") == [
        {"폐기물 종류": "가상폐지", "처리방법": "소각", "배출계수 (kgCO2eq/kg)": 9.1},
        {"폐기물 종류": "가상폐목", "처리방법": "매립", "배출계수 (kgCO2eq/kg)": 9.2},
    ]


def test_an_empty_reload_keeps_the_initial_read() -> None:
    with legacy_strings():
        book = workbook(sheet(WASTE_C5_SHEET, TAIL_ROWS))
        assert ef_auto_header_row(book, WASTE_C5_SHEET, ["처리방법", "배출계수"]) == 4
        got = read_factor_sheet(book, WASTE_C5_SHEET)
    assert (got.how, got.header) == ("kept_initial", 2)
    assert got.frame.columns.tolist() == ["가상종류", "가상방법", "가상계수"]
    assert got.frame.to_dict("records") == [  # 「가상」 이 섞여 수로 못 바꾼 열은 글 그대로(`_to_numeric_ignore`)
        {"가상종류": "가상폐지", "가상방법": "소각", "가상계수": "9.1"},
        {"가상종류": "처리방법", "가상방법": "배출계수", "가상계수": "가상"},
    ]


def test_a_missing_sheet_is_empty() -> None:
    with legacy_strings():
        got = read_factor_sheet(workbook(sheet("가상시트", WASTE_ROWS)), TRAVEL_SPEND_SHEET)
        assert ef_auto_header_row(workbook(), TRAVEL_SPEND_SHEET, ["EF"]) is None
    assert (got.sheet, got.how, got.header) == (TRAVEL_SPEND_SHEET, "empty", None)
    assert got.frame.empty


def test_a_krw_formula_column_without_cached_values_is_usd_over_the_header_rate() -> None:
    """원화 열의 칸이 전부 저장된 값 없는 수식 → USD ÷ 9,400(머리글 안 환율).

    코랩 `_fix_cached_krw_ef_columns`(`:283`).
    """
    book = workbook(sheet_cells(TRANSPORT_SPEND_SHEET, SPEND_ROWS, {"E4": formula(None), "E5": formula(None)}))
    with legacy_strings():
        got = read_factor_sheet(book, TRANSPORT_SPEND_SHEET)
    assert (got.how, got.header) == ("reloaded", 2)
    assert got.frame[KRW_2025].tolist() == [9.4 / 9400.0, 9.3 / 9400.0]
    assert got.frame["NAICS 코드"].tolist() == [9001, 9002]


def test_a_krw_formula_column_with_a_cached_value_is_kept() -> None:
    book = workbook(sheet_cells(TRANSPORT_SPEND_SHEET, SPEND_ROWS, {"E4": formula(9.5e-05), "E5": formula(None)}))
    with legacy_strings():
        got = read_factor_sheet(book, TRANSPORT_SPEND_SHEET)
    values = got.frame[KRW_2025].tolist()
    assert values[0] == 9.5e-05
    assert pd.isna(values[1])
