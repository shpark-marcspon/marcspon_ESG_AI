"""출장·통근 거리(C6-1·C7) — 코랩 셀 22·27 의 마지막 판.

- 표준화: `standardize_c6_dist_sheet`(`:5222`)·`standardize_c7_sheet`(`:5303`). 녹이기 `_melt_monthly_or_annual`
  (`:4858`, b1 `waste.melt_monthly_or_annual`)는 「연간이동횟수」·「연간근무일수」 를 값 열 이름으로 먼저 바꾼 뒤라
  `melt(value_name=…)` 이 ValueError 를 내고 월별 줄을 녹이지 않은 채 연간 줄 **앞**에 둔다(C5 와 같은 꼴) — 월 합은
  시트 고리의 `_sum_monthly`(`:5928`). 월별 열만 있고 연간 열이 없는 템플릿은 녹는다(달마다 한 줄).
- 셈: `calc_business_travel`(`:8661`)·`calc_commute`(`:8679`)·`normalize_commute_mode`(`:8569`)·
  `_fix_contains_roundtrip`(`:8191`), 후처리 `_fix_result_c6`(`:8821`) 의 거리 줄·`_fix_result_c7`(`:8845`) 의
  계산식. 거리 길은 b2a `distance.get_distance_km`(country 기본 KR — 코랩도 넘기지 않는다), 통근 100 km 교차검증은
  `ai_estimate_straight_km`(**원문** 출발·도착 — 앞뒤 공백이 있으면 거리 길 안의 열쇠와 달라 새로 부른다).
- 출장·통근 계수 맵: `_build_travel_ef_map_from_db`(`:438-471`) → `TRAVEL_EF_MAP`(`:473`)은 계수 책 `출장_통근` 의 **첫
  읽기**로 한 번만 짓는다(셀 25 의 다시 읽기 `:7213` 는 맵을 다시 짓지 않는다). `BUS_SUBWAY_AVG_EF`(`:3343`)도 그 맵.
  코드마다 `db|default`, 셈에서 `car_fallback`(C6 `or car` `:8671`)·`bus_subway_avg` 가 더해진다.
- 수치(DEFRA 기본 계수·245·100 km)는 코랩 값이다(constants.py 머리 — 출처 확인 안 함).
- 코랩 결함 후보는 고치지 않는다: C6 의 `flight` 만 air(`flight_short` 따위는 road), 계수 0.0(walk·bicycle·car_ev)이
  `or` 로 car 계수, C7 은 계수 대안 없음, 본 고리 ×2 가 왕복 낱말을 안 봄(activity.py).
"""

from dataclasses import dataclass
from typing import Any, Final, Literal

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.constants import (
    BUS_SUBWAY_FALLBACK,
    COMMUTE_AI_CHECK_KM,
    COMMUTE_DEFAULT_WORKDAYS,
    DISTANCE_MODE_FACTOR,
    ROUNDTRIP_COLUMNS,
    ROUNDTRIP_WORDS,
    TRAVEL_EF_DEFAULTS,
    TRAVEL_EF_FALLBACK_CODE,
)
from esgapi.inventory.engines.scope3.colab_157.distance import (
    DistanceRun,
    ai_estimate_straight_km,
    get_distance_km,
    validate_distance_km,
)
from esgapi.inventory.engines.scope3.colab_157.factor_book import FactorSheetRead
from esgapi.inventory.engines.scope3.colab_157.llm import LlmContext, reraises
from esgapi.inventory.engines.scope3.colab_157.purchase import fix_num, fix_text
from esgapi.inventory.engines.scope3.colab_157.template import normalize_template_columns
from esgapi.inventory.engines.scope3.colab_157.travel_mode import TravelMode, TravelModeCache, normalize_travel_mode
from esgapi.inventory.engines.scope3.colab_157.waste import melt_monthly_or_annual

TRAVEL_EF_UNIT: Final = "kgCO2e/km"  # 계수 책 `출장_통근` 머리글 「EF\n(kgCO2e/km)」
TravelEfVia = Literal["db", "default", "car_fallback", "bus_subway_avg"]


# ── 표준화(코랩 :5222 · :5303) ──


def _strip_stars(df: pd.DataFrame) -> pd.DataFrame:
    rename = {c: str(c).lstrip("*").strip() for c in df.columns if str(c).startswith("*")}
    return df.rename(columns=rename) if rename else df


def standardize_c6_dist_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `standardize_c6_dist_sheet`(`:5222-5266`)."""
    df = _strip_stars(normalize_template_columns(df))
    rename: dict[str, str] = {}
    if "교통수단" in df.columns and "이동수단" not in df.columns:
        rename["교통수단"] = "이동수단"
    if "출장주체" in df.columns and "사업장" not in df.columns:
        rename["출장주체"] = "사업장"
    if "편도거리(km)(선택)" in df.columns and "이동거리(km)" not in df.columns:
        rename["편도거리(km)(선택)"] = "이동거리(km)"
    if "연간이동횟수" in df.columns and "이동횟수" not in df.columns:
        rename["연간이동횟수"] = "이동횟수"
    if "비고(선택)" in df.columns:
        rename["비고(선택)"] = "비고"
    if rename:
        df = df.rename(columns=rename)
    if "*출도착지" in df.columns and "출발지" not in df.columns:
        df = df.rename(columns={"*출도착지": "출발지"})
    if "출장수단" not in df.columns and "이동수단" in df.columns:
        df["출장수단"] = df["이동수단"]
    if "출장인원" not in df.columns and "인원수" in df.columns:
        df["출장인원"] = df["인원수"]
    df = melt_monthly_or_annual(df, month_var_name="발생월", value_name="이동횟수", annual_col_hint="연간이동횟수")
    df["구분"] = "출장"
    df["계산방식"] = "Distance"
    return df


def _one_way_km(x: Any) -> float | None:
    """코랩 `:5340-5343` 의 lambda(「편도거리(km)(선택)」 → float)."""
    if pd.isnull(x):
        return None
    return float(str(x).replace(",", "")) if str(x).strip() not in ["", "nan"] else None


def standardize_c7_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `standardize_c7_sheet`(`:5303-5349`). 「계산방식」 열은 없다(갈래 없음)."""
    df = _strip_stars(normalize_template_columns(df))
    rename: dict[str, str] = {}
    if "교통수단" in df.columns and "이동수단" not in df.columns:
        rename["교통수단"] = "이동수단"
    if "편도거리(km)(선택)" in df.columns and "이동거리(km)" not in df.columns:
        rename["편도거리(km)(선택)"] = "이동거리(km)"
    if "연간근무일수" in df.columns and "근무일수" not in df.columns:
        rename["연간근무일수"] = "근무일수"
    if "비고(선택)" in df.columns:
        rename["비고(선택)"] = "비고"
    if rename:
        df = df.rename(columns=rename)
    if "*출도착지" in df.columns and "출발지" not in df.columns:
        df = df.rename(columns={"*출도착지": "출발지"})
    if "교통수단" not in df.columns and "이동수단" in df.columns:
        df["교통수단"] = df["이동수단"]
    if "직원수" not in df.columns and "인원수" in df.columns:
        df["직원수"] = df["인원수"]
    if "평균통근거리(km)" not in df.columns and "이동거리(km)" in df.columns:
        df["평균통근거리(km)"] = df["이동거리(km)"]
    elif "평균통근거리(km)" not in df.columns and "편도거리(km)(선택)" in df.columns:
        df["평균통근거리(km)"] = df["편도거리(km)(선택)"].apply(_one_way_km)
    df = melt_monthly_or_annual(df, month_var_name="발생월", value_name="근무일수", annual_col_hint="연간근무일수")
    df["구분"] = "통근"
    return df


# ── 출장·통근 계수 맵(코랩 :438-475 · :3343) ──


@dataclass(frozen=True)
class TravelEfMap:
    """코랩 전역 `TRAVEL_EF_MAP`(= `BUSINESS_TRAVEL_EF` = `COMMUTE_EF`)과 `BUS_SUBWAY_AVG_EF`. `column` 은 첫 읽기의 EF
    열(db 코드가 하나도 없으면 None)."""

    factors: dict[str, float]
    origins: dict[str, Literal["db", "default"]]
    column: str | None
    bus_subway_avg: float


def build_travel_ef_map(sheet: FactorSheetRead) -> TravelEfMap:
    """코랩 `_build_travel_ef_map_from_db`(`:438-471`): DEFRA 기본 위에 첫 읽기 db 의 (「표준코드」, 「EF」+「kgCO2」)를
    덮는다. db 가 비었거나 열이 없으면 기본만. 코드 칸 NaN 은 `"nan"` 키(코랩 그대로)."""
    factors = dict(TRAVEL_EF_DEFAULTS)
    origins: dict[str, Literal["db", "default"]] = dict.fromkeys(factors, "default")
    column: str | None = None
    db = sheet.frame
    code_col = next((c for c in db.columns if "표준코드" in c), None) if not db.empty else None
    ef_col = next((c for c in db.columns if "EF" in c and "kgCO2" in c), None) if not db.empty else None
    if code_col and ef_col:
        for _, row in db.iterrows():
            code = str(row.get(code_col, "")).strip()
            ef = pd.to_numeric(pd.Series([row.get(ef_col)], dtype=object), errors="coerce").iloc[0]
            if code and pd.notna(ef):
                factors[code] = float(ef)
                origins[code] = "db"
                column = str(ef_col)
    bus, subway = BUS_SUBWAY_FALLBACK
    average = (factors.get("bus", bus) + factors.get("subway", subway)) / 2
    return TravelEfMap(factors, origins, column, average)


# ── 셈(코랩 :8191 · :8569 · :8661 · :8679) ──


def contains_roundtrip(row: "pd.Series[Any]") -> bool:
    """코랩 `_fix_contains_roundtrip`(`:8191-8194`)."""
    t = " ".join(fix_text(row.get(c)) for c in ROUNDTRIP_COLUMNS).lower()
    return any(k in t for k in ROUNDTRIP_WORDS)


def round_trip_factor(row: "pd.Series[Any]") -> int:
    return 1 if contains_roundtrip(row) else 2


def normalize_commute_mode(context: LlmContext, cache: TravelModeCache, mode: object) -> TravelMode:
    """코랩 `normalize_commute_mode`(`:8569-8573`): 렌터카는 car(판단근거는 그대로)."""
    m = normalize_travel_mode(context, cache, mode)
    return TravelMode("car", m.via) if m.value == "rental_car" else m


def _has_bus_and_subway(mode_text: str) -> bool:
    """코랩 `:8706` — 이동수단 글에 버스와 지하철(전철)이 함께."""
    return ("버스" in mode_text or "bus" in mode_text) and (
        "지하철" in mode_text or "subway" in mode_text or "전철" in mode_text
    )


@dataclass(frozen=True)
class TravelCalc:
    """`calc_business_travel`·`calc_commute` 의 (거리, 계수, 배출량)과 그 길.

    `picked` = 거리를 줄의 거리 칸에서 집었는가, `measured` = 거리 길(`get_distance_km`)을 실제로 불렀는가(덧붙임 1 —
    아니면 `geo_mode` 는 None), `distance_via` = 입력이면 `input`, 거리 길이면 그 via(예외·None 이면 `none`), 통근
    100 km 갈음이면 `commute_ai_check`. `people`·`trips`(C6)·`workdays`(C7)·`round_trip` 은 셈에 쓴 값.
    """

    distance_km: float | None
    ef: float | None
    emission_t: float | None
    mode: TravelMode
    ef_via: TravelEfVia | None
    distance_via: str
    geo_mode: str | None
    picked: bool
    measured: bool
    people: float
    trips: float | None
    workdays: float | None
    round_trip: int


def _measure(distances: DistanceRun, row: "pd.Series[Any]", geo_mode: str) -> tuple[float | None, str]:
    found = get_distance_km(distances, row.get("출발지"), row.get("도착지"), mode=geo_mode)
    return found.km, found.via


def calc_business_travel(
    context: LlmContext, modes: TravelModeCache, distances: DistanceRun, ef_map: TravelEfMap, row: "pd.Series[Any]"
) -> TravelCalc:
    """코랩 `calc_business_travel`(`:8661-8676`). 거리 길의 예외는 None(코랩 `except Exception`)."""
    distance = fix_num(row.get("이동거리(km)"))
    people = fix_num(row.get("출장인원") or row.get("인원수")) or 1
    trips = fix_num(row.get("이동횟수")) or 1
    mode = normalize_travel_mode(context, modes, row.get("출장수단") or row.get("이동수단"))
    picked = distance is not None
    via = "input" if picked else "none"
    geo_mode: str | None = None
    if distance is None and fix_text(row.get("출발지")) and fix_text(row.get("도착지")):
        geo_mode = "air" if mode.value == "flight" else "rail" if mode.value == "train" else "road"
        try:
            distance, via = _measure(distances, row, geo_mode)
        except Exception as error:  # 코랩 `except Exception: distance = None`
            if reraises(context, error):
                raise
            distance, via = None, "none"
    ef = ef_map.factors.get(mode.value) or ef_map.factors.get(TRAVEL_EF_FALLBACK_CODE)
    ef_via: TravelEfVia | None
    if ef_map.factors.get(mode.value):
        ef_via = ef_map.origins[mode.value]
    else:
        ef_via = "car_fallback" if ef is not None else None
    factor = round_trip_factor(row)
    emission_t = None
    if distance is not None and ef is not None:
        emission_t = distance * factor * people * trips * ef / 1000.0
    return TravelCalc(
        distance, ef, emission_t, mode, ef_via, via, geo_mode, picked, geo_mode is not None, people, trips, None, factor
    )


def calc_commute(
    context: LlmContext, modes: TravelModeCache, distances: DistanceRun, ef_map: TravelEfMap, row: "pd.Series[Any]"
) -> TravelCalc:
    """코랩 `calc_commute`(`:8679-8714`). 거리 > 100 km 면 AI 직선 × 보정으로 교차검증해 갈음(검증 통과일 때)."""
    employees = fix_num(row.get("직원수") or row.get("인원수")) or 1
    distance = fix_num(row.get("평균통근거리(km)") or row.get("이동거리(km)"))
    workdays = fix_num(row.get("근무일수")) or COMMUTE_DEFAULT_WORKDAYS
    mode = normalize_commute_mode(context, modes, row.get("교통수단") or row.get("이동수단"))
    picked = distance is not None
    via = "input" if picked else "none"
    geo_mode: str | None = None
    if distance is None and fix_text(row.get("출발지")) and fix_text(row.get("도착지")):
        geo_mode = "rail" if mode.value in ["train", "subway"] else "road"
        try:
            distance, via = _measure(distances, row, geo_mode)
            if distance is not None and distance > COMMUTE_AI_CHECK_KM:
                # 코랩은 원문 칸을 그대로 넘긴다 — 글이 아닌 칸(수)은 글로(「코랩과 다른 자리」)
                origin, dest = str(row.get("출발지")), str(row.get("도착지"))
                ai_straight = ai_estimate_straight_km(distances, origin, dest, "KR")
                if ai_straight is not None:
                    ai_distance = validate_distance_km(
                        ai_straight * DISTANCE_MODE_FACTOR.get(geo_mode, 1.0), mode=geo_mode, country_hint="KR"
                    )
                    if ai_distance is not None:
                        distance, via = ai_distance, "commute_ai_check"
        except Exception as error:  # 코랩 `except Exception: distance = None`
            if reraises(context, error):
                raise
            distance, via = None, "none"
    mode_text = fix_text(row.get("교통수단") or row.get("이동수단")).lower()
    ef: float | None
    ef_via: TravelEfVia | None
    if _has_bus_and_subway(mode_text):
        ef, ef_via = ef_map.bus_subway_avg, "bus_subway_avg"
    else:
        ef = ef_map.factors.get(mode.value)
        ef_via = ef_map.origins.get(mode.value)
    factor = round_trip_factor(row)
    emission_t = None
    if distance is not None and ef is not None:
        emission_t = employees * distance * factor * workdays * ef / 1000.0
    return TravelCalc(
        distance, ef, emission_t, mode, ef_via, via, geo_mode, picked, geo_mode is not None, employees, None, workdays,
        factor,
    )  # fmt: skip


# ── 후처리의 거리 줄(코랩 :8821-8836 · :8845-8859) ──


@dataclass(frozen=True)
class C6DistanceFix:
    """`_fix_result_c6` 의 Distance 줄: 파일에서 다시 읽은 거리·계수로 다시 센 값."""

    distance_km: float | None
    ef: float | None
    people: float
    trips: float
    round_trip: int
    emission_t: float | None
    formula: str


def fix_c6_distance(row: "pd.Series[Any]") -> C6DistanceFix:
    """코랩 `_fix_result_c6`(`:8825-8836`)의 Distance 갈래."""
    dist = fix_num(row.get("이동거리(km)"))
    ef = fix_num(row.get("배출계수"))
    people = fix_num(row.get("출장인원") or row.get("인원수")) or 1
    trips = fix_num(row.get("이동횟수")) or 1
    factor = round_trip_factor(row)
    emission_t = dist * factor * people * trips * ef / 1000.0 if dist is not None and ef is not None else None
    formula = (
        "배출량(tCO2e) = 이동거리 × 왕복계수 × 인원수 × 이동횟수 × EF / 1000 = "
        f"{dist:g} × {factor:g} × {people:g} × {trips:g} × {ef:g} / 1000 = {emission_t:g}"
        if emission_t is not None and dist is not None and ef is not None
        else ""
    )
    return C6DistanceFix(dist, ef, people, trips, factor, emission_t, formula)


def commute_formula(calc: TravelCalc) -> str:
    """코랩 `_fix_result_c7`(`:8858`)의 「계산식」."""
    dist, ef, emission_t, workdays = calc.distance_km, calc.ef, calc.emission_t, calc.workdays
    if emission_t is None or dist is None or ef is None or workdays is None:
        return ""
    return (
        "배출량(tCO2e) = 평균통근거리 × 왕복계수 × 근무일수 × 직원수 × EF / 1000 = "
        f"{dist:g} × {calc.round_trip:g} × {workdays:g} × {calc.people:g} × {ef:g} / 1000 = {emission_t:g}"
    )
