"""T1~T4(경계 ①) 출장·통근 거리의 표준화·셈·계수 맵 — `travel.py` 를 바로 부른다(시트 고리·후처리는 test_travel_sheet).

코랩 줄(읽기판): 표준화 `standardize_c6_dist_sheet`(`:5222`)·`standardize_c7_sheet`(`:5303`)·녹이기 `:4858`, 셈
`calc_business_travel`(`:8661`)·`calc_commute`(`:8679`), 계수 맵 `:438-475`·`:3343`. 계수는 support 의 지은 `출장_통근`
(flight 0.921 · train 0.922 · bus 0.923 · car 0.924 · subway 0.926)이고 그 밖의 코드는 코랩 DEFRA 기본값이다.
배출량 손셈은 코랩 식의 차례 그대로 적는다(`거리 × 왕복 × 인원 × 횟수 × EF / 1000`, 통근은
`직원 × 거리 × 왕복 × 일수 × EF / 1000`).
"""

from collections.abc import Mapping
from typing import Any

import pandas as pd
import pytest

from esgapi.inventory.engines.scope3.colab_157.constants import TRAVEL_EF_DEFAULTS
from esgapi.inventory.engines.scope3.colab_157.distance import DistanceRun
from esgapi.inventory.engines.scope3.colab_157.factor_book import TRAVEL_SHEET, read_initial_factor_sheet
from esgapi.inventory.engines.scope3.colab_157.template import read_template_rows
from esgapi.inventory.engines.scope3.colab_157.travel import (
    TravelCalc,
    TravelEfMap,
    build_travel_ef_map,
    calc_business_travel,
    calc_commute,
    fix_c6_distance,
    standardize_c6_dist_sheet,
    standardize_c7_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.travel_mode import TravelModeCache
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    COMMUTE_MAIN,
    COMMUTE_SUB,
    MONTH_NAMES,
    TRAVEL_MAIN,
    FakeGeocoder,
    Value,
    annual,
    commute_sheet,
    llm_context,
    monthly,
    sheet,
    travel_distance_sheet,
    travel_ef_sheet,
    workbook,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_transport_spend import Replies

SUPPORT_MAP = {"flight": 0.921, "train": 0.922, "bus": 0.923, "car": 0.924, "subway": 0.926}


def by_text(answers: Mapping[str, str]) -> Replies:
    return Replies(lambda text: next((a for key, a in answers.items() if key in text), None))


def ef_map() -> TravelEfMap:
    return build_travel_ef_map(read_initial_factor_sheet(workbook(travel_ef_sheet()), TRAVEL_SHEET))


class Ctx:
    """`calc_*` 에 넘길 실행 하나(모의 공급사·가짜 지오코더·이동수단 캐시·지은 계수 맵)."""

    def __init__(self, answers: Mapping[str, str] | None = None) -> None:
        self.mock = by_text(answers or {})
        self.geocoder = FakeGeocoder()
        self.context = llm_context(self.mock)
        self.modes = TravelModeCache()
        self.distances = DistanceRun(self.geocoder, self.context)
        self.map = ef_map()

    def business(self, values: Mapping[str, object]) -> TravelCalc:
        return calc_business_travel(self.context, self.modes, self.distances, self.map, row(values))

    def commute(self, values: Mapping[str, object]) -> TravelCalc:
        return calc_commute(self.context, self.modes, self.distances, self.map, row(values))


def row(values: Mapping[str, object]) -> "pd.Series[Any]":
    return pd.Series(dict(values), dtype=object)


def frame_of(s: Any) -> pd.DataFrame:
    df = read_template_rows(s)
    assert isinstance(df, pd.DataFrame)
    return df


def value(df: pd.DataFrame, i: int, column: str) -> object:
    v = df.iloc[i][column]
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


# ── T1 표준화 ──


def test_c6_1_standardizes_renames_copies_and_keeps_the_monthly_row_unmelted_first() -> None:
    """「연간이동횟수」 → 「이동횟수」 뒤 `melt(value_name="이동횟수")` 이 ValueError — 월별 줄은 한 줄로 앞에, 달 칸
    그대로."""
    rows = [
        annual(["가상국", "가상본부", "가상버스", 9, "가상시사", "가상시아", 99], 9),
        monthly(["가상국", "가상지사", "가상기차", 9.5, "가상시가", "가상시나", None], {3: 9, 7: 9.5}),
    ]
    df = standardize_c6_dist_sheet(frame_of(travel_distance_sheet("c6-1_출장거리", *rows)))
    assert [value(df, i, "이동수단") for i in range(2)] == ["가상기차", "가상버스"]  # 월별이 먼저(R3)
    assert [value(df, i, "출장수단") for i in range(2)] == ["가상기차", "가상버스"]
    assert [value(df, i, "출장인원") for i in range(2)] == [9.5, 9]
    assert [value(df, i, "사업장") for i in range(2)] == ["가상지사", "가상본부"]
    assert [value(df, i, "이동거리(km)") for i in range(2)] == [None, 99]
    assert [value(df, i, "이동횟수") for i in range(2)] == [None, 9]
    assert (value(df, 0, "3월"), value(df, 0, "7월"), value(df, 1, "3월")) == (9, 9.5, None)
    assert "발생월" not in df.columns and {"교통수단", "연간이동횟수", "편도거리(km)(선택)"}.isdisjoint(df.columns)
    assert set(df["계산방식"]) == {"Distance"} and set(df["구분"]) == {"출장"}


def test_c7_standardizes_and_keeps_both_mode_columns_and_the_monthly_row_first() -> None:
    rows = [
        annual(["가상국", "가상사업장A", "가상승용차", 9, None, None, 9.9], 99),
        monthly(["가상국", "가상사업장B", "가상지하철", 9.1, None, None, 9.2], {1: 9, 2: 9.3}),
    ]
    df = standardize_c7_sheet(frame_of(commute_sheet("c7_임직원통근", *rows)))
    assert [value(df, i, "이동수단") for i in range(2)] == ["가상지하철", "가상승용차"]
    assert [value(df, i, "교통수단") for i in range(2)] == ["가상지하철", "가상승용차"]
    assert [value(df, i, "직원수") for i in range(2)] == [9.1, 9]
    assert [value(df, i, "평균통근거리(km)") for i in range(2)] == [9.2, 9.9]
    assert [value(df, i, "근무일수") for i in range(2)] == [None, 99]
    assert (value(df, 0, "1월"), value(df, 0, "2월")) == (9, 9.3)
    assert "계산방식" not in df.columns and set(df["구분"]) == {"통근"}


def test_monthly_only_and_annual_only_templates() -> None:
    """연간 열이 없으면 녹는다(달마다 한 줄 · 발생월), 달 열이 없으면 연간 열 이름만 바뀐다."""
    main: list[Value] = [*TRAVEL_MAIN[:7], "월별 이동횟수", *([None] * 11)]
    sub: list[Value] = [*([None] * 7), *MONTH_NAMES]
    months_only = sheet(
        "c6-1_출장거리",
        {1: ["가상 안내"], 2: main, 3: sub, 4: ["가상국", "가상본부", "가상버스", 9, None, None, 99, 9, None, 9.5]},
    )
    df = standardize_c6_dist_sheet(frame_of(months_only))
    assert [(value(df, i, "발생월"), value(df, i, "이동횟수")) for i in range(len(df))] == [(1, 9), (3, 9.5)]
    annual_only = sheet(
        "c7_임직원통근",
        {
            1: ["가상 안내"],
            2: [*COMMUTE_MAIN[:8]],
            3: [*COMMUTE_SUB[:8]],
            4: ["가상국", "가상사업장", "가상버스", 9, None, None, 9.9, 99],
        },
    )
    df7 = standardize_c7_sheet(frame_of(annual_only))
    assert (len(df7), value(df7, 0, "근무일수")) == (1, 99)


# ── T2 출장 셈(calc_business_travel) ──

AIR = {
    "지역: 가상시자": '{"airport_name": "Synthetic Ja Airport", "iata": ""}',
    "지역: 가상시차": '{"airport_name": "Synthetic Cha Airport", "iata": ""}',
    "출발지: Synthetic Ja Airport\n도착지: Synthetic Cha Airport\n국가 힌트: KR": '{"distance_km": 93}',
    "Synthetic Ja Airport": "Synthetic Ja Airport",
    "Synthetic Cha Airport": "Synthetic Cha Airport",
}
ROAD = {
    "출발지: 가상시가\n도착지: 가상시다\n국가 힌트: KR": '{"distance_km": 92}',
    "가상시가": "Synthetic Ga",
    "가상시다": "Synthetic Da",
}


def trip(
    mode: object, km: object = None, places: tuple[object, object] = ("가상시가", "가상시다"), **extra: object
) -> dict[str, object]:
    return {"출장수단": mode, "이동수단": mode, "출장인원": 9, "이동횟수": 9.5, "이동거리(km)": km,
            "출발지": places[0], "도착지": places[1], **extra}  # fmt: skip


def test_an_input_distance_is_taken_as_is_and_not_measured() -> None:
    ctx = Ctx()
    calc = ctx.business(trip("가상버스", 99))
    assert (calc.distance_km, calc.distance_via, calc.picked, calc.measured, calc.geo_mode) == (
        99,
        "input",
        True,
        False,
        None,
    )
    assert (calc.mode.value, calc.ef, calc.ef_via, calc.round_trip) == ("bus", 0.923, "db", 2)
    assert calc.emission_t == 99 * 2 * 9 * 9.5 * 0.923 / 1000.0
    assert ctx.mock.texts == [] and ctx.geocoder.queries == []


def test_flight_goes_by_air_through_the_airport_ai() -> None:
    ctx = Ctx(AIR)
    calc = ctx.business(trip("가상비행기", None, ("가상시자", "가상시차")))
    assert (calc.mode.value, calc.geo_mode, calc.distance_via) == ("flight", "air", "ai_straight+airport")
    assert calc.distance_km == 93 * 1.09
    assert calc.emission_t == 93 * 1.09 * 2 * 9 * 9.5 * 0.921 / 1000.0
    assert ctx.geocoder.queries == ["Synthetic Ja Airport, KR", "Synthetic Cha Airport, KR"]


def test_a_domestic_flight_is_measured_by_road_and_train_by_rail() -> None:
    """`flight` 만 air — `flight_dom`(국내선) 은 road(결함 후보, P1). `train` 은 rail(보정 1.2)."""
    ctx = Ctx(ROAD)
    dom = ctx.business(trip("가상 국내선"))
    assert (dom.mode.value, dom.geo_mode, dom.distance_km) == ("flight_dom", "road", 92 * 1.3)
    assert (dom.ef, dom.ef_via) == (TRAVEL_EF_DEFAULTS["flight_dom"], "default")
    rail = ctx.business(trip("가상기차"))
    assert (rail.mode.value, rail.geo_mode, rail.distance_km) == ("train", "rail", 92 * 1.2)


def test_a_zero_factor_and_an_unmapped_mode_fall_back_to_car() -> None:
    """`BUSINESS_TRAVEL_EF.get(mode) or .get("car")` — walk 0.0 은 거짓이라 car(결함 후보, P2), 렌터카도 car."""
    ctx = Ctx(ROAD)
    walk = ctx.business(trip("가상 도보", 99))
    assert (walk.mode.value, walk.ef, walk.ef_via) == ("walk", 0.924, "car_fallback")
    rental = ctx.business(trip("가상렌터카"))
    assert (rental.mode.value, rental.ef, rental.ef_via, rental.geo_mode) == (
        "rental_car",
        0.924,
        "car_fallback",
        "road",
    )


def test_a_round_trip_word_makes_the_factor_one_and_missing_people_and_trips_are_one() -> None:
    ctx = Ctx()
    calc = ctx.business({"출장수단": "가상버스", "이동거리(km)": 99, "비고": "가상 왕복 기준"})
    assert (calc.round_trip, calc.people, calc.trips) == (1, 1, 1)
    assert calc.emission_t == 99 * 1 * 1 * 1 * 0.923 / 1000.0


def test_a_distance_error_is_none_and_no_places_is_not_measured() -> None:
    ctx = Ctx({"출발지: 가상시가": '["가상"]', "가상시가": "Synthetic Ga", "가상시다": "Synthetic Da"})
    broken = ctx.business(trip("가상버스"))
    assert (broken.distance_km, broken.distance_via, broken.measured, broken.geo_mode, broken.emission_t) == (
        None, "none", True, "road", None,
    )  # fmt: skip
    nowhere = ctx.business(trip("가상버스", None, (None, None)))
    assert (nowhere.distance_via, nowhere.measured, nowhere.geo_mode) == ("none", False, None)


def test_the_postprocess_recomputes_the_distance_row_from_the_file_values() -> None:
    fix = fix_c6_distance(
        row({"이동거리(km)": 99.0, "배출계수": 0.923, "인원수": 9, "이동횟수": 9.5, "비고": "roundtrip"})
    )
    assert (fix.round_trip, fix.people, fix.emission_t) == (1, 9, 99.0 * 1 * 9 * 9.5 * 0.923 / 1000.0)
    assert fix.formula == (
        "배출량(tCO2e) = 이동거리 × 왕복계수 × 인원수 × 이동횟수 × EF / 1000 = 99 × 1 × 9 × 9.5 × 0.923 / 1000 = "
        f"{fix.emission_t:g}"
    )
    assert fix_c6_distance(row({"이동거리(km)": float("nan"), "배출계수": 0.923})).formula == ""


# ── T3 통근 셈(calc_commute) ──

FAR = {
    "가상시타 \n국가 힌트: KR": '{"distance_km": 94}',
    "출발지: 가상시카\n도착지: 가상시타\n국가 힌트: KR": '{"distance_km": 94}',
    "가상시카": "Synthetic Ka",
    "가상시타": "Synthetic Ta",
}


def commuter(
    mode: object, km: object = None, places: tuple[object, object] = ("가상시카", "가상시타"), **extra: object
) -> dict[str, object]:
    return {"교통수단": mode, "이동수단": mode, "직원수": 9, "근무일수": 99, "평균통근거리(km)": km,
            "출발지": places[0], "도착지": places[1], **extra}  # fmt: skip


def test_an_input_commute_distance_and_the_default_workdays() -> None:
    ctx = Ctx()
    calc = ctx.commute({"교통수단": "가상승용차", "평균통근거리(km)": 9.9})
    assert (calc.distance_via, calc.workdays, calc.people, calc.round_trip) == ("input", 245, 1, 2)
    assert calc.emission_t == 1 * 9.9 * 2 * 245 * 0.924 / 1000.0


def test_over_100_km_is_checked_again_with_the_same_ai_key_and_a_padded_place_asks_again() -> None:
    """직선 94 × 1.3 = 122.2 > 100 → `_ai_estimate_straight_km(원문)` — 열쇠가 거리 길 안의 것과 같으면 새 부름 0."""
    ctx = Ctx(FAR)
    calc = ctx.commute(commuter("가상승용차"))
    assert (calc.distance_km, calc.distance_via, calc.geo_mode) == (94 * 1.3, "commute_ai_check", "road")
    assert sum("국가 힌트: KR" in t for t in ctx.mock.texts) == 1
    padded = Ctx(FAR)
    calc2 = padded.commute(commuter("가상승용차", None, (" 가상시카", "가상시타 ")))
    assert calc2.distance_via == "commute_ai_check"
    straight = [t for t in padded.mock.texts if "국가 힌트: KR" in t]
    assert len(straight) == 2 and "출발지:  가상시카\n도착지: 가상시타 \n" in straight[1]


def test_the_check_starts_just_over_100_km() -> None:
    """77 × 1.3 = 100.1 > 100 → 교차검증(P3 이 101 로 올리면 안 함)."""
    near = {"출발지: 가상시카\n도착지: 가상시타\n국가 힌트: KR": '{"distance_km": 77}', "가상시카": "Synthetic Ka",
            "가상시타": "Synthetic Ta"}  # fmt: skip
    ctx = Ctx(near)
    calc = ctx.commute(commuter("가상승용차"))
    assert (calc.distance_km, calc.distance_via) == (77 * 1.3, "commute_ai_check")


def test_bus_with_subway_averages_and_an_unmapped_mode_has_no_factor() -> None:
    ctx = Ctx()
    mixed = ctx.commute(commuter("가상버스 지하철", 9.9))
    assert (mixed.ef, mixed.ef_via) == ((0.923 + 0.926) / 2, "bus_subway_avg")
    assert mixed.emission_t == 9 * 9.9 * 2 * 99 * ((0.923 + 0.926) / 2) / 1000.0
    hotel = ctx.commute(commuter("가상호텔", 9.9))
    assert (hotel.mode.value, hotel.ef, hotel.ef_via, hotel.emission_t) == ("lodging", None, None, None)


def test_rental_car_is_car_and_a_round_trip_word_is_one() -> None:
    ctx = Ctx()
    calc = ctx.commute(commuter("가상렌터카", 9.9, 비고="가상 return trip"))
    assert (calc.mode.value, calc.mode.via, calc.ef, calc.round_trip) == ("car", "rule_fix", 0.924, 1)
    assert calc.emission_t == 9 * 9.9 * 1 * 99 * 0.924 / 1000.0


def test_train_and_subway_are_measured_by_rail() -> None:
    ctx = Ctx({"출발지: 가상시가\n도착지: 가상시다\n국가 힌트: KR": '{"distance_km": 9}', "가상시가": "Synthetic Ga",
               "가상시다": "Synthetic Da"})  # fmt: skip
    calc = ctx.commute(commuter("가상지하철", None, ("가상시가", "가상시다")))
    assert (calc.geo_mode, calc.distance_km, calc.distance_via) == ("rail", 9 * 1.2, "ai_straight")


# ── T4 계수 맵 ──


def test_the_map_is_the_defaults_overlaid_by_the_first_read() -> None:
    m = ef_map()
    assert {k: m.factors[k] for k in SUPPORT_MAP} == SUPPORT_MAP
    assert {k: v for k, v in m.factors.items() if k not in SUPPORT_MAP} == {
        k: v for k, v in TRAVEL_EF_DEFAULTS.items() if k not in SUPPORT_MAP
    }
    assert (m.origins["car"], m.origins["walk"], m.column) == ("db", "default", "EF\n(kgCO2e/km)")
    assert m.bus_subway_avg == (0.923 + 0.926) / 2
    read = read_initial_factor_sheet(workbook(travel_ef_sheet()), TRAVEL_SHEET)
    assert (read.how, read.header, len(read.frame)) == ("initial", 1, 5)


def test_only_the_first_read_builds_the_map() -> None:
    """둘째 줄이 머리글이 아닌 책: 첫 읽기(header_row=1)에는 「표준코드」 가 없어 기본값만 — 셀 25 의 다시 읽기(머리글
    자동, `:7213`)는 셋째 줄을 찾지만 맵은 다시 짓지 않는다(P5)."""
    book = workbook(
        sheet(
            "출장_통근",
            {1: ["가상 표"], 2: ["가상 메모"], 3: ["이동수단", "표준코드", "EF\n(kgCO2e/km)"], 4: ["가상", "car", 0.9]},
        )
    )
    m = build_travel_ef_map(read_initial_factor_sheet(book, TRAVEL_SHEET))
    assert (m.factors, m.column) == (TRAVEL_EF_DEFAULTS, None)
    assert set(m.origins.values()) == {"default"}


@pytest.mark.parametrize(
    "book",
    [
        workbook(),
        workbook(
            sheet("출장_통근", {1: ["가상 표"], 2: ["이동수단", "코드", "EF\n(kgCO2e/km)"], 3: ["가상", "car", 0.9]})
        ),
    ],
)
def test_no_sheet_or_no_code_column_is_the_defaults(book: Any) -> None:
    m = build_travel_ef_map(read_initial_factor_sheet(book, TRAVEL_SHEET))
    assert m.factors == TRAVEL_EF_DEFAULTS and m.bus_subway_avg == (0.10385 + 0.0278) / 2
