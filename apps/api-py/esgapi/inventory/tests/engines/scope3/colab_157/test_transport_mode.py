"""D3·D4·D5·무게 — 거리기반 운송의 찾기·추정·환산·맵(transport.py, 시트 셈은 경계 ②).

운송수단: `infer_transport_mode`(`:7699`) → 템플릿 표시명 → 붙잡은 옛 판(`:1153`)+`:7667` 정규화 → AI → road.
운송 계수 맵: `refresh_transport_ef_map`(`:6611`, 부름 `:7780`) — 기본 다섯 위에 다시 읽은 운송 시트의 코드를 덮는다.
"""

import math
from typing import Any

import pandas as pd
import pytest

from esgapi.core.llm.providers.mock import MockProvider
from esgapi.inventory.engines.scope3.colab_157.factor_book import (
    INITIAL_HEADER_ROWS,
    TRANSPORT_SHEET,
    FactorSheetRead,
    read_factor_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.transport import (
    TRANSPORT_MODE_PROMPT,
    TransportEfMap,
    TransportMode,
    TransportModeCache,
    WeightConversion,
    infer_transport_mode,
    normalize_transport_code,
    normalize_transport_code_6582,
    refresh_transport_ef_map,
    weight_to_kg,
)
from esgapi.inventory.engines.scope3.colab_157.units import UnitFactorCache
from esgapi.inventory.tests.engines.scope3.colab_157.support import llm_context, sheet, workbook
from esgapi.inventory.tests.engines.scope3.colab_157.test_distance import RETRY, SYS, sent

DEFAULTS = {"road": 0.12, "parcel": 0.18, "rail": 0.03, "sea": 0.015, "air": 0.6}


def row(**cells: object) -> "pd.Series[Any]":
    return pd.Series(cells, dtype=object)


def mode_of(r: "pd.Series[Any]", mock: MockProvider | None = None) -> TransportMode:
    return infer_transport_mode(llm_context(mock or MockProvider()), TransportModeCache(), r)


# ── D4 운송수단 ──


@pytest.mark.parametrize(
    ("cells", "expected"),
    [
        ({"운송수단": "가상 트럭"}, TransportMode("road", "template_alias")),
        ({"운송수단": "가상 벌크선"}, TransportMode("sea_bulk", "template_alias")),  # 「선박」 보다 「벌크」 가 먼저
        ({"자재명": "가상 항공 부속"}, TransportMode("air", "template_alias")),
        ({"운송수단": "가상 cargo"}, TransportMode("air", "column")),  # 옛 판 AIR 「cargo」
        ({"운송수단": "가상 KTX 화물"}, TransportMode("rail", "template_alias")),
        ({"비고": "가상 퀵"}, TransportMode("parcel", "keyword")),
        ({"거래처명": "가상 해운"}, TransportMode("sea", "keyword")),  # 보강 낱말 :6577 — 거래처명은 새 판 fields 밖
        ({"출발지": "가상 공항", "도착지": "가상시"}, TransportMode("air", "geo")),
        ({"출발지": "가상항", "도착지": "가상시"}, TransportMode("sea", "geo")),
        ({"출발지": "가상창고", "도착지": "가상시"}, TransportMode("road", "geo")),
    ],
)
def test_template_alias_then_the_old_rules(cells: dict[str, object], expected: TransportMode) -> None:
    mock = MockProvider()
    assert mode_of(row(**cells), mock) == expected
    assert mock.calls == []


def test_two_normalizers() -> None:
    assert normalize_transport_code_6582("가상 화물") == "road"
    assert normalize_transport_code("가상 화물") == "road"  # 템플릿 표시명에 안 걸림 → 옛 판
    assert normalize_transport_code("inland_water") == "inland_water"  # 템플릿 표시명(밑줄을 지움)
    assert normalize_transport_code_6582("inland_water") == "inland_water"  # 옛 판은 낱말 없음 → 글 그대로
    assert normalize_transport_code("Sea") == "sea"
    assert normalize_transport_code("가상") == "가상"
    assert normalize_transport_code("nan") == "nan"
    assert normalize_transport_code(math.nan) is None and normalize_transport_code("  ") is None


def test_the_ai_gets_the_joined_text_with_the_direction_word() -> None:
    """R10: 표준화가 「운송구분」 을 늘 넣으니 규칙이 못 찾으면 늘 AI — 글에 「입고」 가 든다(fields 차례)."""
    mock = MockProvider().enqueue_text('{"mode": "rail"}')
    r = row(자재명="가상부속 세트", 운송구분="입고", 운송수단="가상수레")
    assert mode_of(r, mock) == TransportMode("rail", "ai")
    text = "가상수레 입고 가상부속 세트"
    expected = (  # 읽기판 :7689-7693 의 f-문자열(첫 줄이 길어 이어 붙임)
        "다음은 화물 운송 관련 텍스트(운송수단/적요/거래처명 등)이며, "
        "규칙 기반 키워드로는 운송수단을 판별하지 못했다.\n"
        f"텍스트: {text}\n\n"
        "아래 표준 코드 중 가장 적절한 것 하나를 선택하라: road, parcel, rail, sea, air, sea_bulk, inland_water\n"
        'JSON으로만 답하라: {"mode": "<code>"}'
    )
    assert [sent(c) for c in mock.calls] == [(SYS, expected, 40)]
    assert TRANSPORT_MODE_PROMPT == "inventory/scope3-colab-transport-mode@1"


def test_an_ai_failure_is_cached_and_falls_back_to_road() -> None:
    mock = MockProvider().enqueue_text('{"mode": "가상"}')
    context, cache = llm_context(mock), TransportModeCache()
    r = row(자재명="가상부속", 운송구분="출고")
    assert infer_transport_mode(context, cache, r) == TransportMode("road", "fallback")
    assert infer_transport_mode(context, cache, r) == TransportMode("road", "fallback")
    assert len(mock.calls) == 1 and cache.modes == {"출고 가상부속": None}

    mock = MockProvider()  # 세 번 다 실패 → None
    assert infer_transport_mode(llm_context(mock), TransportModeCache(), r) == TransportMode("road", "fallback")
    assert [sent(c)[1].endswith(RETRY) for c in mock.calls] == [False, True, True]


def test_no_text_is_road_without_a_call() -> None:
    mock = MockProvider()
    assert mode_of(row(운송수단=math.nan, 출발지="가상시"), mock) == TransportMode("road", "fallback")
    assert mock.calls == []


def test_a_non_dict_ai_answer_raises() -> None:
    mock = MockProvider().enqueue_text("[9]")
    with pytest.raises(AttributeError):
        mode_of(row(자재명="가상부속"), mock)


# ── 무게(코랩 :6486) ──


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (9, "ton", WeightConversion(9000.0, "rule")),
        ("9,500", "kg", WeightConversion(9500.0, "rule")),
        (9, "g", WeightConversion(9 * 0.001, "rule")),
        (9, "LB", WeightConversion(9 * 0.45359237, "rule")),  # b1 표의 0.453592 와 다름
        (9, "", WeightConversion(9.0, "rule")),
        (9, math.nan, WeightConversion(9.0, "rule")),
        (9, "metric ton", WeightConversion(9000.0, "rule")),  # 공백을 지운 뒤 다시 붙임
        (9, "가상 톤", WeightConversion(9000.0, "rule")),
        (9, "가상kg", WeightConversion(9.0, "rule")),
        (9, "가상gram", WeightConversion(9 * 0.001, "rule")),
    ],
)
def test_weight_rules(value: object, unit: object, expected: WeightConversion) -> None:
    mock = MockProvider()
    assert weight_to_kg(llm_context(mock), UnitFactorCache(), value, unit) == expected
    assert mock.calls == []


def test_weight_ai_factor_and_the_failure_is_one() -> None:
    mock = MockProvider().enqueue_text('{"factor": 9.5}')
    cache = UnitFactorCache()
    assert weight_to_kg(llm_context(mock), cache, 9, "가상팔레트") == WeightConversion(9 * 9.5, "ai")
    assert "입력 단위: 가상팔레트\n목표(기준) 단위: kg" in sent(mock.calls[0])[1]
    assert cache.factors == {("가상팔레트", "kg", ""): 9.5}
    mock = MockProvider()  # JSON 셋·단순 둘 실패 → 1배
    got = weight_to_kg(llm_context(mock), UnitFactorCache(), 9, "가상상자")
    assert got == WeightConversion(9.0, "ai_failed") and len(mock.calls) == 5


def test_no_weight_value_is_none() -> None:
    assert weight_to_kg(llm_context(MockProvider()), UnitFactorCache(), math.nan, "ton") is None
    assert weight_to_kg(llm_context(MockProvider()), UnitFactorCache(), "가상", "ton") is None


# ── D5 운송 계수 맵 ──


def transport_read(frame: pd.DataFrame) -> FactorSheetRead:
    return FactorSheetRead(TRANSPORT_SHEET, frame, "reloaded", 1)


EF = "배출계수\n(kgCO2eq/ton·km)"


def test_db_codes_are_normalized_and_laid_over_the_defaults() -> None:
    frame = pd.DataFrame(
        {
            "운송수단": ["가상", "가상", "가상", "가상", "가상"],
            "표준코드": ["road", "sea_bulk", math.nan, "Truck", "가상코드"],
            EF: [0.0911, 0.0916, 0.0919, 0.0999, "가상"],
        }
    )
    got = refresh_transport_ef_map(transport_read(frame))
    assert got.factors == {**DEFAULTS, "road": 0.0999, "sea_bulk": 0.0916, "nan": 0.0919}
    assert got.origins == {
        "road": "db", "parcel": "default", "rail": "default", "sea": "default", "air": "default",
        "sea_bulk": "db", "nan": "db",
    }  # fmt: skip
    assert got.column == EF


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame(),
        pd.DataFrame({"코드": ["road"], EF: [0.0911]}),
        pd.DataFrame({"표준코드": ["road"], "EF": [0.09]}),
    ],
)
def test_an_empty_db_or_missing_columns_is_the_defaults(frame: pd.DataFrame) -> None:
    got = refresh_transport_ef_map(transport_read(frame))
    assert got == TransportEfMap(DEFAULTS, dict.fromkeys(DEFAULTS, "default"), None)


def test_the_first_read_header_row_is_per_sheet() -> None:
    """운송 첫 읽기는 header_row=1(:330). 자동 머리글이 마지막 줄을 고르면(데이터 없음) 첫 읽기를 쓴다."""
    assert INITIAL_HEADER_ROWS == {"폐기물_C5": 2, "운송_Spend": 2, "출장_Spend": 2, "운송": 1, "출장_통근": 1}
    rows = {
        1: ["가상 운송 계수표"],
        2: ["운송수단", "표준코드", EF],
        3: ["가상트럭", "road", 0.0911],
        4: ["표준코드 배출계수", "가상", "가상", "가상", "가상"],
    }
    read = read_factor_sheet(workbook(sheet(TRANSPORT_SHEET, rows)), TRANSPORT_SHEET)
    assert (read.how, read.header) == ("kept_initial", 1)
    assert refresh_transport_ef_map(read).factors["road"] == 0.0911


def test_the_map_uses_the_reloaded_sheet_not_the_first_read() -> None:
    """첫 읽기(둘째 줄 머리글)와 다시 읽기(자동 — 셋째 줄)의 열이 다르다. 맵은 다시 읽은 쪽(셀 25 뒤 :7780)."""
    rows = {
        1: ["가상 운송 계수표"],
        2: ["가상메모", None, "표준코드(옛)", "배출계수(옛)"],
        3: ["운송수단", "표준코드", EF, "비고"],
        4: ["가상트럭", "road", 0.0911, "가상"],
    }
    read = read_factor_sheet(workbook(sheet(TRANSPORT_SHEET, rows)), TRANSPORT_SHEET)
    assert (read.how, read.header) == ("reloaded", 2)
    got = refresh_transport_ef_map(read)
    assert got.factors["road"] == 0.0911 and got.origins["road"] == "db"
