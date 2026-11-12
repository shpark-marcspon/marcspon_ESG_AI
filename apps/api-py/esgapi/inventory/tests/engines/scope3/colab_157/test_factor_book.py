"""S4 보고연도: 구매_USEPA 의 원화 계수 열을 보고연도로 고른다(2023·2024·2025).

비어 있는 원화 열은 USD ÷ 머리글 환율로 채운다.
"""

import pytest

from esgapi.inventory.engines.scope3.colab_157.factor_book import (
    SpendDbKeptInitial,
    SpendDbReloaded,
    initial_spend_db,
    load_purchase_usepa_as_krw_spend_db,
    reload_spend_db,
)
from esgapi.inventory.engines.scope3.colab_157.pdcompat import legacy_strings
from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, sheet, workbook

HEAD: list[Value] = ["품목군", "상세 카테고리", "한국어 매핑 키워드", "NAICS 코드", "NAICS Title", "EF (kgCO2e/USD)"]
KRW = [
    "EF (kgCO2e/KRW)\n2023년말 기준\n(9,200 KRW/USD)",
    "EF (kgCO2e/KRW)\n2024년말 기준\n(9,300 KRW/USD)",
    "EF (kgCO2e/KRW)\n2025년말 기준\n(9,400 KRW/USD)",
]
ROWS: dict[int, list[Value]] = {
    1: ["가상 구매 계수 표"],
    3: [*HEAD, *KRW],
    4: ["가상군", "가상세부", "가상", 9001, "Virtual Paper Mills", 0.94, 9.23e-05, None, 9.25e-05],
    5: ["가상군", "가상세부", "가상", 9002, "Virtual Office Supplies", 0.93, 9.33e-05, None, 9.35e-05],
}
RELOAD_ROWS: dict[int, list[Value]] = {3: HEAD, 4: ["가상군", "가상세부", "가상", 9001, "Virtual Paper Mills", 0.94]}
SAMPLES = (sheet("구매_USEPA", ROWS), sheet("구매_USEPA", RELOAD_ROWS))  # test_samples 가 본다


@pytest.mark.parametrize(("year", "column", "first_ef"), [(2023, 0, 9.23e-05), (2025, 2, 9.25e-05)])
def test_the_report_year_picks_its_krw_column(year: int, column: int, first_ef: float) -> None:
    with legacy_strings():
        db = load_purchase_usepa_as_krw_spend_db(workbook(sheet("구매_USEPA", ROWS)), year)
    assert db.ef_col == KRW[column]
    assert db.frame["ef"].tolist()[0] == first_ef
    assert db.names == ("Virtual Paper Mills", "Virtual Office Supplies")


def test_an_empty_krw_column_is_filled_from_usd_over_the_header_rate() -> None:
    """2024 열은 비어 있다(재계산 안 된 수식) → USD ÷ 9,300."""
    with legacy_strings():
        db = load_purchase_usepa_as_krw_spend_db(workbook(sheet("구매_USEPA", ROWS)), 2024)
    assert db.ef_col == KRW[1]
    assert db.frame["ef"].tolist() == [0.94 / 9300.0, 0.93 / 9300.0]


def test_a_year_without_its_column_takes_the_latest_year() -> None:
    with legacy_strings():
        db = load_purchase_usepa_as_krw_spend_db(workbook(sheet("구매_USEPA", ROWS)), 2022)
    assert db.ef_col == KRW[2]


def test_reload_failure_keeps_the_initial_db() -> None:
    with legacy_strings():
        b = workbook(sheet("구매_USEPA", RELOAD_ROWS))
        initial = initial_spend_db(b)
        choice = reload_spend_db(b, 2025, initial)
    assert isinstance(choice, SpendDbKeptInitial)
    assert "기계산 컬럼" in choice.reason
    assert initial.ef_col == "EF (kgCO2e/USD)"  # 원화 열이 없으면 셀 9 는 USD 를 쓴다
    with legacy_strings():
        assert isinstance(reload_spend_db(workbook(sheet("구매_USEPA", ROWS)), 2025, initial), SpendDbReloaded)
