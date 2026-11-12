# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""거리 길 — 코랩 셀 11·12·13·15 의 `normalize_city`(`:1044`)·`_cached_geocode`(`:1072`)·`estimate_straight_distance`
(`:1214`)·`validate_distance_km`(`:1238`)·`_ai_estimate_distance_km`(`:1577`)·`_ai_estimate_straight_km`(`:1595`)·
`_looks_like_airport`(`:1618`)·`_ai_nearest_airport`(`:1629`)·`_resolve_air_location`(`:1652`)·`get_distance_km`(`:1665`)·
`infer_distance`(`:1709`). C4-1·C9-1(S3C-b2a)이 쓰고 C6-1·C7(S3C-b2b)이 그대로 부른다.

- 직선거리는 geopy `geodesic(...).km`(`:1229`)의 자리다. geopy 2.5.0 은 WGS-84 를 km 단위 타원체
  `(6378.137, 1/298.257223563)` 로 들고 `Geodesic(a, f).Inverse(..., Geodesic.DISTANCE)["s12"]` 를 낸다(휠 원문
  `geopy/distance.py` 의 `ELLIPSOIDS`·`geodesic.measure`, 2026-10-20 읽음). 같은 꼴을 geographiclib 로 부른다
  (`MARC-ENT-363`). geopy `Point` 의 좌표 정규화는 옮기지 않았다(「코랩과 다른 자리」).
- **geographiclib 를 import 하는 곳은 이 파일 하나다**(`geodesic_km` — 밖으로는 float 만). 그 패키지에 타입 정보가 없어
  첫 줄의 파일 단위 pyright 설정을 둔다(감독 처분 2026-10-20, 선례 `greenwash/tools/pdfium_locate.py`).
- 코랩의 `@lru_cache` 다섯(도시·지오코더·AI 직선·AI 실거리·공항)은 실행 하나의 `DistanceRun` 캐시다. **None 도
  기억하고 예외는 기억하지 않는다.** 열쇠는 코랩 인자 그대로.
- 도시 정규화는 코랩이 `client.messages.create` 를 바로 부른다(재시도·system 없음, `max_tokens=20`, `.strip()`). 부름
  실패는 예외라 `estimate_straight_distance` 의 맨 `except:` 가 삼키고(None) 캐시되지 않는다. 지오코더 예외도 같다.
- AI 셋의 `parsed.get` 은 `json_get` 이다 — dict 아닌 JSON 답은 AttributeError 로 밖에 나간다(`get_distance_km` 에는 try
  가 없어 그 시트가 실패한다 — 코랩 `[error]`).
- 보정계수·국내 상한은 코랩 값이다(constants.py 머리 — 출처 확인 안 함).
- 거리마다 그 길(via)을 함께 낸다(산정 출처 — 값은 바꾸지 않는다): `input` · `geocode` · `ai_straight` · `ai_road` ·
  `none`, 공항 AI 로 바꾼 지점이 있으면 끝에 `+airport`.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Final

import pandas as pd
from geographiclib.geodesic import Geodesic

from esgapi.inventory.engines.scope3.colab_157.constants import (
    AIRPORT_TEXT_HINTS,
    DISTANCE_MODE_FACTOR,
    DISTANCE_MODE_LABEL,
)
from esgapi.inventory.engines.scope3.colab_157.llm import (
    LlmContext,
    LlmText,
    call_claude_json,
    call_text,
    json_get,
    reraises,
)
from esgapi.inventory.engines.scope3.colab_157.ports import Coordinates, Geocoder, NotFound
from esgapi.inventory.engines.scope3.colab_157.purchase import to_float

CITY_NAME_PROMPT: Final = "inventory/scope3-colab-city-name@1"
DISTANCE_STRAIGHT_PROMPT: Final = "inventory/scope3-colab-distance-straight@1"
DISTANCE_ROAD_PROMPT: Final = "inventory/scope3-colab-distance-road@1"
AIRPORT_PROMPT: Final = "inventory/scope3-colab-airport@1"

# geopy 2.5.0 `ELLIPSOIDS["WGS-84"]` 의 장반경(km)·편평률 — `geodesic.measure` 가 `Geodesic(ELLIPSOID[0], ELLIPSOID[2])`
WGS84_A_KM: Final = 6378.137
WGS84_F: Final = 1 / 298.257223563
_GEOD: Final = Geodesic(WGS84_A_KM, WGS84_F)


def geodesic_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """geopy `geodesic((lat1, lon1), (lat2, lon2)).km` 의 자리(km 타원체라 `s12` 가 곧 km)."""
    return float(_GEOD.Inverse(lat1, lon1, lat2, lon2, Geodesic.DISTANCE)["s12"])


class CityNameFailed(Exception):
    """도시 정규화 부름이 실패했다(코랩 `client.messages.create` 의 예외 자리)."""


@dataclass
class DistanceRun:
    """실행 하나의 거리 상태: 지오코더 + 코랩 lru_cache 다섯(None 까지, 예외는 안 기억)."""

    geocoder: Geocoder
    llm: LlmContext
    cities: dict[str, str] = field(default_factory=dict[str, str])
    geocodes: dict[str, Coordinates | NotFound] = field(default_factory=dict[str, Coordinates | NotFound])
    straight: dict[tuple[str, str, str], float | None] = field(default_factory=dict[tuple[str, str, str], float | None])
    road: dict[tuple[str, str, str, str], float | None] = field(
        default_factory=dict[tuple[str, str, str, str], float | None]
    )
    airports: dict[tuple[str, str], str | None] = field(default_factory=dict[tuple[str, str], str | None])


@dataclass(frozen=True)
class Distance:
    """거리 하나와 그 길. `km` 가 None 이면 via 는 `none`."""

    km: float | None
    via: str


def safe_text2(x: object) -> str:
    """코랩 `_safe_text2`(`:1090`)."""
    if x is None:
        return ""
    if isinstance(x, float) and pd.isnull(x):
        return ""
    s = str(x).strip()
    return "" if s.lower() == "nan" else s


def contains_any(text: object, keywords: list[str]) -> bool:
    """코랩 `_contains_any`(`:1109`)."""
    lowered = safe_text2(text).lower()
    return any(k.lower() in lowered for k in keywords)


def normalize_city(run: DistanceRun, city: str) -> str:
    """코랩 `normalize_city`(`:1044`) + lru_cache. 실패는 `CityNameFailed`(캐시 안 함)."""
    if city in run.cities:
        return run.cities[city]
    outcome = call_text(run.llm, CITY_NAME_PROMPT, {"city": city}, 20)
    if not isinstance(outcome, LlmText):
        raise CityNameFailed(outcome.reason)
    name = outcome.text.strip()
    run.cities[city] = name
    return name


def cached_geocode(run: DistanceRun, query: str) -> Coordinates | NotFound:
    """코랩 `_cached_geocode`(`:1072`): 지오코더 결과(못 찾음 포함) 캐시. 예외는 그대로 나간다(캐시 안 함)."""
    if query in run.geocodes:
        return run.geocodes[query]
    found = run.geocoder.geocode(query)
    run.geocodes[query] = found
    return found


def estimate_straight_distance(run: DistanceRun, origin: str, dest: str, country_hint: str | None) -> float | None:
    """코랩 `estimate_straight_distance`(`:1214-1235`). 맨 `except: pass` 는 Exception 으로 받는다."""
    try:  # 코랩 `except: pass`
        if not origin or not dest:
            return None
        origin = normalize_city(run, origin)
        dest = normalize_city(run, dest)
        q_origin = f"{origin}, {country_hint}" if country_hint else origin
        q_dest = f"{dest}, {country_hint}" if country_hint else dest
        o = cached_geocode(run, q_origin)
        d = cached_geocode(run, q_dest)
        if isinstance(o, Coordinates) and isinstance(d, Coordinates):
            return geodesic_km(o.latitude, o.longitude, d.latitude, d.longitude)
    except Exception as error:
        if reraises(run.llm, error):
            raise
    return None


def validate_distance_km(distance_km: object, mode: str = "road", country_hint: str = "KR") -> float | None:
    """코랩 `validate_distance_km`(`:1238-1259`): 국내(KR)일 때만 상한, ≤0 은 None."""
    value = to_float(distance_km)
    if value is None:
        return None
    if country_hint == "KR":
        if mode in ["road", "parcel"] and value > 800:
            return None
        if mode == "rail" and value > 1000:
            return None
        if mode == "sea" and value > 3000:
            return None
        if mode == "air" and value > 3000:
            return None
    if value <= 0:
        return None
    return value


def ai_estimate_distance_km(run: DistanceRun, origin: str, dest: str, mode: str, country_hint: str) -> float | None:
    """코랩 `_ai_estimate_distance_km`(`:1577-1592`, `max_tokens=60`) + lru_cache."""
    key = (origin, dest, mode, country_hint)
    if key in run.road:
        return run.road[key]
    variables = {
        "origin": origin,
        "dest": dest,
        "mode_label": DISTANCE_MODE_LABEL.get(mode, mode),
        "country_hint": country_hint,
    }
    parsed = call_claude_json(run.llm, DISTANCE_ROAD_PROMPT, variables, 60)
    d = to_float(json_get(parsed, "distance_km")) if parsed else None
    value = validate_distance_km(d, mode=mode, country_hint=country_hint)
    run.road[key] = value
    return value


def ai_estimate_straight_km(run: DistanceRun, origin: str, dest: str, country_hint: str) -> float | None:
    """코랩 `_ai_estimate_straight_km`(`:1595-1609`, `max_tokens=60`) + lru_cache. 검증은 부르는 쪽(보정 뒤)."""
    key = (origin, dest, country_hint)
    if key in run.straight:
        return run.straight[key]
    variables = {"origin": origin, "dest": dest, "country_hint": country_hint}
    parsed = call_claude_json(run.llm, DISTANCE_STRAIGHT_PROMPT, variables, 60)
    value = to_float(json_get(parsed, "distance_km")) if parsed else None
    run.straight[key] = value
    return value


def looks_like_airport(text: str) -> bool:
    """코랩 `_looks_like_airport`(`:1618-1626`): 공항 낱말이 들었거나 영문 세 글자(IATA)."""
    t = safe_text2(text)
    if not t:
        return False
    if contains_any(t.lower(), AIRPORT_TEXT_HINTS):
        return True
    return bool(re.fullmatch(r"[A-Za-z]{3}", t.strip()))


def ai_nearest_airport(run: DistanceRun, location: str, country_hint: str) -> str | None:
    """코랩 `_ai_nearest_airport`(`:1629-1649`, `max_tokens=80`) + lru_cache."""
    key = (location, country_hint)
    if key in run.airports:
        return run.airports[key]
    parsed = call_claude_json(run.llm, AIRPORT_PROMPT, {"location": location, "country_hint": country_hint}, 80)
    name: str | None = None
    if parsed:
        name = safe_text2(json_get(parsed, "airport_name")) or None
    run.airports[key] = name
    return name


def resolve_air_location(run: DistanceRun, text: str, country_hint: str) -> tuple[str, bool]:
    """코랩 `_resolve_air_location`(`:1652-1658`). 둘째 값은 공항 AI 의 이름으로 바꿨는지(산정 출처)."""
    text = safe_text2(text)
    if not text or looks_like_airport(text):
        return text, False
    airport = ai_nearest_airport(run, text, country_hint)
    return (airport, True) if airport else (text, False)


def get_distance_km(
    run: DistanceRun, origin: object, dest: object, mode: str = "road", country_hint: str = "KR"
) -> Distance:
    """코랩 `get_distance_km`(`:1665-1703`): (air 면 공항으로) → 직선(지오코더, 실패면 AI) × 보정 → 검증 → AI 실거리."""
    o = safe_text2(origin)
    d = safe_text2(dest)
    if not o or not d:
        return Distance(None, "none")
    airport = False
    if mode == "air":
        o, o_airport = resolve_air_location(run, o, country_hint)
        d, d_airport = resolve_air_location(run, d, country_hint)
        airport = o_airport or d_airport
    suffix = "+airport" if airport else ""
    factor = DISTANCE_MODE_FACTOR.get(mode, 1.0)

    via = "geocode"
    straight = estimate_straight_distance(run, o, d, country_hint if country_hint == "KR" else None)
    if straight is None:
        via = "ai_straight"
        straight = ai_estimate_straight_km(run, o, d, country_hint)
    if straight is not None:
        validated = validate_distance_km(straight * factor, mode=mode, country_hint=country_hint)
        if validated is not None:
            return Distance(validated, via + suffix)

    road = ai_estimate_distance_km(run, o, d, mode, country_hint)
    return Distance(road, "ai_road" + suffix) if road is not None else Distance(None, "none")


def infer_distance(run: DistanceRun, row: "pd.Series[Any]", mode: str) -> Distance:
    """코랩 `infer_distance`(`:1709-1745`): 입력 거리(검증 통과)면 그대로, 아니면 행 국가로 `get_distance_km`."""
    input_distance = to_float(row.get("운송거리(km)"))
    country_hint = safe_text2(row.get("국가")) or "KR"
    if input_distance is not None:
        validated = validate_distance_km(input_distance, mode=mode, country_hint=country_hint)
        if validated is not None:
            return Distance(validated, "input")
    origin = safe_text2(row.get("출발지"))
    dest = safe_text2(row.get("도착지"))
    if not origin or not dest:
        return Distance(None, "none")
    return get_distance_km(run, origin, dest, mode=mode, country_hint=country_hint)
