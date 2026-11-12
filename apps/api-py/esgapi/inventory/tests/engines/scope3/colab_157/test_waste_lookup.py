"""폐기물(C5) 계수 찾기(코랩 `lookup_waste_ef` `:653`)·처리방법(`_normalize_treatment` `:645`)·생물기원(`:362-416`).

평균값은 코랩 `WASTE_AVG_EF`(`:353`)·`BIOGENIC_WASTE_FCF`(`:362`)의 값이다(코랩 값 — 원천 미확인, constants.py).
"""

import pandas as pd
import pytest

from esgapi.inventory.engines.scope3.colab_157.factor_book import WASTE_C5_SHEET, read_factor_sheet
from esgapi.inventory.engines.scope3.colab_157.pdcompat import legacy_strings
from esgapi.inventory.engines.scope3.colab_157.waste import (
    BiogenicSplit,
    WasteFactor,
    biogenic_fossil_split,
    biogenic_group_from_name,
    lookup_waste_ef,
    normalize_treatment,
)
from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, sheet, workbook

AVG_LANDFILL, AVG_INCINERATION, AVG_RECYCLING = 0.175965929, 1.176142131, 0.029390317  # 코랩 :353
WASTE_ROWS: dict[int, list[Value]] = {
    1: ["가상 폐기물 계수 표"],
    3: ["폐기물 종류", "처리방법", "키워드", "배출계수 (kgCO2eq/kg)"],
    4: ["가상폐지", "소각", "가상종이", 9.1],
    5: ["가상폐지", "매립", None, 9.2],
    6: ["가상 폐플라스틱 혼합", "소각", "가상비닐, 가상봉투", 9.3],
    7: ["가상폐목", "재활용", None, 9.4],
    8: ["가상폐콘크리트", "기타", None, 9.5],
}


def waste_db() -> pd.DataFrame:
    return read_factor_sheet(workbook(sheet(WASTE_C5_SHEET, WASTE_ROWS)), WASTE_C5_SHEET).frame


@pytest.mark.parametrize(
    ("name", "treatment", "expected"),
    [
        ("가상폐지", "소각", WasteFactor(9.1, "exact")),
        (" 가상폐지 ", "Landfill", WasteFactor(9.2, "exact")),
        ("가상 폐플라스틱", "incineration", WasteFactor(9.3, "partial")),
        ("가상비닐 묶음", "소각", WasteFactor(9.3, "keyword")),
        ("가상폐목", "소각", WasteFactor(9.4, "any_treatment")),  # 소각 줄에 없고 처리방법 무시로 재활용 줄
        ("가상폐콘크리트", "기타", WasteFactor(9.5, "exact")),  # 「기타」 별칭(:633 PATCH)
        ("가상 무엇", "매립", WasteFactor(AVG_LANDFILL, "treatment_average")),
        ("가상 무엇", "재활용", WasteFactor(AVG_RECYCLING, "treatment_average")),
        ("가상 무엇", "", WasteFactor(AVG_INCINERATION, "treatment_average")),  # 처리방법 없음 → 소각 평균
        ("가상 무엇", "가상처리", WasteFactor(AVG_INCINERATION, "treatment_average")),  # 별칭 없음 → 소각 평균
        ("가상 무엇", "기타", WasteFactor(None, None)),  # 평균 표에 「기타」 가 없다
    ],
)
def test_lookup_waste_ef(name: str, treatment: str, expected: WasteFactor) -> None:
    with legacy_strings():
        assert lookup_waste_ef(waste_db(), name, treatment) == expected


def test_an_empty_db_is_the_treatment_average() -> None:
    with legacy_strings():
        assert lookup_waste_ef(pd.DataFrame(), "가상폐지", "recycle") == WasteFactor(AVG_RECYCLING, "treatment_average")
        assert lookup_waste_ef(pd.DataFrame(), "가상폐지", "") == WasteFactor(AVG_INCINERATION, "treatment_average")
        assert lookup_waste_ef(pd.DataFrame(), "가상폐지", "etc") == WasteFactor(None, None)


@pytest.mark.parametrize(
    ("raw", "std"),
    [
        ("매립", "매립"),
        ("Landfill", "매립"),
        ("INC", "소각"),
        ("가상 소각 처리", "소각"),
        ("Recycle", "재활용"),
        ("기타", "기타"),
        ("Other", "기타"),
        ("etc", "기타"),
        ("가상", None),
        (None, None),
    ],
)
def test_normalize_treatment(raw: object, std: str | None) -> None:
    assert normalize_treatment(raw) == std


@pytest.mark.parametrize(
    ("name", "group"),
    [
        ("가상 음식물 쓰레기", "음식물류"),
        ("가상 폐지", "폐지류"),
        ("가상 골판지", "폐지류"),
        ("가상 팔레트", "폐목재류"),
        ("가상 폐플라스틱", None),
        (None, None),
        ("nan", None),
    ],
)
def test_biogenic_group_from_name(name: object, group: str | None) -> None:
    assert biogenic_group_from_name(name) == group


def test_food_incineration_is_all_biogenic() -> None:
    """FCF 0 → 생물기원 = 소각 × 1, 화석기원 = 전체 − 소각."""
    got = biogenic_fossil_split(9.75, 9.5, "음식물류")
    assert got == BiogenicSplit(9.75 - 9.5, 9.5, 0.0, "음식물류 소각: 생물기원 100% / 화석기원 0%")


def test_paper_incineration_keeps_one_percent_fossil() -> None:
    got = biogenic_fossil_split(9.5, 9.25, "폐지류")
    assert got == BiogenicSplit(9.5 - 9.25 * (1 - 0.01), 9.25 * (1 - 0.01), 0.01, got.note)
    assert got.note == "폐지류 소각: 생물기원 99% / 화석기원 1%"
    assert got.colab_columns() == {
        "화석기원 CO2e(tCO2e)": got.fossil,
        "생물기원 CO2e(tCO2e)": got.biogenic,
        "화석탄소비율(FCF)": 0.01,
        "바이오매스 구분": "폐지류 소각: 생물기원 99% / 화석기원 1%",
    }


@pytest.mark.parametrize("incineration", [0.0, None])
def test_no_incineration_is_not_applicable(incineration: float | None) -> None:
    """매립 등 소각 몫이 없으면(0·None) 생물기원 대상 그룹이어도 「해당없음」 — 전체가 화석기원."""
    for group in ("폐지류", "음식물류"):
        assert biogenic_fossil_split(9.5, incineration, group) == BiogenicSplit(9.5, 0.0, None, "해당없음")


def test_a_group_outside_the_table_or_no_total() -> None:
    assert biogenic_fossil_split(9.5, 9.5, None) == BiogenicSplit(9.5, 0.0, None, "해당없음")
    assert biogenic_fossil_split(9.5, 9.5, "가상류") == BiogenicSplit(9.5, 0.0, None, "해당없음")
    assert biogenic_fossil_split(None, 9.5, "폐지류") == BiogenicSplit(None, None, None, None)
