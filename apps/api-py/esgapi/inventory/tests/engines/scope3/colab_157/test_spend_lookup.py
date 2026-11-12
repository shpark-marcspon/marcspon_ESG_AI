"""운송·출장 Spend 계수 찾기 — 운송 `lookup_transport_spend_ef`(`:7752` 감쌈 → 옛 판 `:865`), 출장
`_fix_lookup_travel_spend_candidate`(`:8576`). 계수 열은 늦은 묶임의 마지막 판 `_get_spend_ef_col`(`:7979`).

「General Freight Trucking, Local」 같은 NAICS Title 은 공개 분류명이고 계수 값은 지어낸 것이다.
"""

import pandas as pd
import pytest

from esgapi.inventory.engines.scope3.colab_157.factor_book import (
    TRANSPORT_SPEND_SHEET,
    TRAVEL_SPEND_SHEET,
    read_factor_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.pdcompat import legacy_strings
from esgapi.inventory.engines.scope3.colab_157.spend import (
    SpendHit,
    current_spend_ef_unit,
    get_spend_ef_col,
    lookup_transport_spend_ef,
    lookup_travel_spend_ef,
    template_transport_code,
)
from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, sheet, workbook

USD = "EF (kgCO2e/USD)"
KRW_2024 = "EF (kgCO2e/KRW)\n2024년말 기준\n(9,300 KRW/USD)"
KRW_2025 = "EF (kgCO2e/KRW)\n2025년말 기준\n(9,400 KRW/USD)"
GFT = "General Freight Trucking, Local"
T_HEAD: list[Value] = ["운송 구분", "한국어 키워드", "한국어명", "NAICS 코드", "NAICS Title", USD, KRW_2024, KRW_2025]
T_ROWS: dict[int, list[Value]] = {
    1: ["가상 운송 지출 계수 표"],
    3: T_HEAD,
    4: ["가상빈칸", "가상빈", "가상 빈 운송", 9000, "Virtual Empty Freight", 9.0, None, None],  # 2025 원화 칸 없음
    5: ["가상도로", "가상트럭", "가상 도로 화물", 9001, GFT, 9.1, 9.11e-05, 9.12e-05],
    6: ["가상택배", "courier", "가상 소포", 9002, "Virtual Couriers and Express Delivery", 9.2, 9.21e-05, 9.22e-05],
    7: ["가상해상", "가상선적", "가상 해상 운송", 9003, "Virtual Deep Sea Freight", 9.3, 9.31e-05, 9.32e-05],
}


def transport_db(rows: dict[int, list[Value]] = T_ROWS) -> pd.DataFrame:
    return read_factor_sheet(workbook(sheet(TRANSPORT_SPEND_SHEET, rows)), TRANSPORT_SPEND_SHEET).frame


NO_DEFAULT_ROWS = {k: v for k, v in T_ROWS.items() if k != 5}


def transport(text: str, rows: dict[int, list[Value]] = T_ROWS, year: int = 2025) -> SpendHit | None:
    with legacy_strings():
        return lookup_transport_spend_ef(transport_db(rows), year, text)


def test_a_hint_alone_reaches_the_keyword() -> None:
    """「가상 택배」 → parcel → 확장 글의 힌트 「courier」 가 키워드에 걸린다(원문으로는 기본 줄뿐)."""
    assert template_transport_code("가상 택배") == "parcel"
    hit = SpendHit("Virtual Couriers and Express Delivery", 9.22e-05, "9002", "keyword:expanded")
    assert transport("가상 택배") == hit
    assert transport("가상 택배", year=2024) == SpendHit(hit.title, 9.21e-05, "9002", "keyword:expanded")


def test_the_raw_text_is_the_second_try() -> None:
    """「가상 도로」 → road 힌트를 단 확장 글은 어디에도 안 걸리고(기본 줄 없음) 원문이 한국어명에 걸린다."""
    assert transport("가상 도로", NO_DEFAULT_ROWS) is None  # 그 한국어명 줄이 기본 줄이라 뺀 표에는 없다
    rows = {**NO_DEFAULT_ROWS, 5: ["가상도로", "가상트럭", "가상 도로 화물", 9001, "Virtual Road", 9.1, None, 9.12e-05]}
    assert transport("가상 도로", rows) == SpendHit("Virtual Road", 9.12e-05, "9001", "korean_name:raw")


def test_title_and_default_title() -> None:
    assert transport("virtual deep") == SpendHit("Virtual Deep Sea Freight", 9.32e-05, "9003", "title:expanded")
    assert transport("가상 무엇") == SpendHit(GFT, 9.12e-05, None, "default_title:expanded")
    assert transport("가상 무엇", NO_DEFAULT_ROWS) is None


def test_an_empty_query_hits_the_first_row_with_a_factor_by_korean_name() -> None:
    """q="" 는 `"" in 한국어명` 이 참 — 계수 있는 첫 줄(코랩 그대로). 첫 줄은 2025 원화 칸이 비어 건너뛴다."""
    assert transport("") == SpendHit(GFT, 9.12e-05, "9001", "korean_name:expanded")


def test_the_factor_column_is_the_report_year_krw_or_usd() -> None:
    with legacy_strings():
        db = transport_db()
        assert (get_spend_ef_col(db, 2024), current_spend_ef_unit(db, 2024)) == (KRW_2024, "kgCO2e/KRW")
        assert get_spend_ef_col(db, 2023) == KRW_2025  # 그 해 열이 없으면 가장 뒤 연도
        usd_only = db.drop(columns=[KRW_2024, KRW_2025])
        assert (get_spend_ef_col(usd_only, 2025), current_spend_ef_unit(usd_only, 2025)) == (USD, "kgCO2e/USD")
        assert lookup_transport_spend_ef(usd_only, 2025, "가상 택배") == SpendHit(
            "Virtual Couriers and Express Delivery", 9.2, "9002", "keyword:expanded"
        )


# ── 출장 Spend ──

V_HEAD: list[Value] = ["출장 항목", "키워드", "NAICS 코드", "NAICS Title", USD, KRW_2025]
V_ROWS: dict[int, list[Value]] = {
    1: ["가상 출장 지출 계수 표"],
    3: V_HEAD,
    4: ["가상택시", "가상콜", 9101, "Taxi Service", 9.1, 9.1e-05],
    5: ["가상숙소", "가상민박, 가상여관", 9102, "Virtual Lodging Places", 9.2, 9.2e-05],
    6: ["가상식비", "가상민박집", 9104, "Virtual Food Services", 9.4, 9.4e-05],
}
BLANK_ITEM_ROWS = {**V_ROWS, 7: [None, None, 9103, "Virtual Other Travel", 9.3, 9.3e-05]}


def travel(text: str, rows: dict[int, list[Value]] = V_ROWS) -> SpendHit | None:
    with legacy_strings():
        db = read_factor_sheet(workbook(sheet(TRAVEL_SPEND_SHEET, rows)), TRAVEL_SPEND_SHEET).frame
        return lookup_travel_spend_ef(db, 2025, text)


def test_the_manual_table_comes_first() -> None:
    assert travel("가상 택시비") == SpendHit("Taxi Service", 9.1e-05, "9101", "manual")
    # 수동 표의 Title 이 시트에 없으면 점수로 넘어간다(「가상콜」 키워드).
    assert travel("가상 항공 가상콜") == SpendHit("Taxi Service", 9.1e-05, "9101", "scored")


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("가상 민박", "Virtual Lodging Places"),  # 키워드 100+4
        ("가상 민박집", "Virtual Food Services"),  # 100+5 가 100+4 를 이긴다(뒤 줄이어도)
        ("가상식비 virtual lodging places", "Virtual Food Services"),  # 출장 항목 30 > Title 20
        ("virtual lodging places", "Virtual Lodging Places"),  # Title 20
    ],
)
def test_the_scores(text: str, title: str) -> None:
    hit = travel(text)
    assert hit is not None
    assert (hit.title, hit.via) == (title, "scored")


def test_a_blank_item_always_scores_thirty() -> None:
    """「출장 항목」 칸이 빈 줄은 `"" in qn` 이 참이라 늘 30점(코랩 그대로) — 동점이면 먼저 선 줄."""
    assert travel("가상 무엇", BLANK_ITEM_ROWS) == SpendHit("Virtual Other Travel", 9.3e-05, "9103", "scored")
    hit = travel("가상식비", BLANK_ITEM_ROWS)  # 가상식비 30 · 빈 줄 30 → 앞 줄
    assert hit is not None
    assert hit.title == "Virtual Food Services"


def test_no_hit_is_none() -> None:
    assert travel("가상 무엇") is None
    with legacy_strings():
        assert lookup_travel_spend_ef(None, 2025, "가상 택시") is None
        assert lookup_travel_spend_ef(pd.DataFrame(), 2025, "가상 택시") is None
