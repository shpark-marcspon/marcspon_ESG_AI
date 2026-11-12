"""D0~D3 거리 길(코랩 `get_distance_km` `:1665` 과 그 아래 — distance.py).

D1 의 기대값 출처: geopy 2.5.0 휠(`geopy-2.5.0-py3-none-any.whl`, sha256 `8ad8cc22…51aa`) + geographiclib 2.1,
2026-10-20 실측 — 휠을 설치하지 않고 `PYTHONPATH` 로 올려 진짜 `geopy.distance.geodesic(a, b).km` 를 부르고
`float.hex` 로 떴다(밴드 보고 `band-reports/S3C-b2a.md`). README 쌍은 https://github.com/geopy/geopy 의 README 예
(Newport, RI → Cleveland, OH — `.miles` 538.390445368 도 같았다). 나머지 넷은 좌표만 고른 점이다. 넷째·다섯째는
`Geodesic.WGS84`(m) ÷ 1000 과 끝자리가 갈리는 쌍이다(P1 이 문다).
"""

import ast
from pathlib import Path

import pandas as pd
import pytest

from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import ProviderError, ProviderRequest
from esgapi.inventory.engines.scope3.colab_157.distance import (
    AIRPORT_PROMPT,
    CITY_NAME_PROMPT,
    DISTANCE_ROAD_PROMPT,
    DISTANCE_STRAIGHT_PROMPT,
    Distance,
    DistanceRun,
    geodesic_km,
    get_distance_km,
    infer_distance,
    looks_like_airport,
    validate_distance_km,
)
from esgapi.inventory.engines.scope3.colab_157.ports import Coordinates, NoGeocoder, NotFound
from esgapi.inventory.tests.engines.scope3.colab_157.support import FakeGeocoder, llm_context
from esgapi.inventory.tests.engines.scope3.colab_157.test_purity import FOLDER
from esgapi.inventory.tests.scope3_llm_support import user_text

# ── D0 ──


def test_geographiclib_is_imported_only_by_distance_py() -> None:
    users: list[str] = []
    for path in sorted(FOLDER.parent.parent.parent.parent.rglob("*.py")):  # esgapi/ 전부
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            if any(n == "geographiclib" or n.startswith("geographiclib.") for n in names):
                users.append(str(path.relative_to(FOLDER)))
    assert users == ["distance.py"]
    assert Path(FOLDER / "distance.py").read_text(encoding="utf-8").splitlines()[0].startswith("# pyright: ")


# ── D1 ──

GEOPY_KM = [
    ((41.49008, -71.312796), (41.499498, -81.695391), "0x1.b13a4ba026b44p+9"),
    ((41.49008, -71.312796), (41.49008, -71.312796), "0x0.0p+0"),
    ((0.0, 0.0), (0.5, 179.7), "0x1.37a0827a95d03p+14"),
    ((-60.5, -120.0), (-45.0, 20.0), "0x1.e51da5321258ep+12"),
    ((-60.5, -179.8), (-30.0, 179.7), "0x1.a7bbed69ada46p+11"),
]


@pytest.mark.parametrize(("a", "b", "expected"), GEOPY_KM)
def test_geodesic_km_is_bit_equal_to_geopy(a: tuple[float, float], b: tuple[float, float], expected: str) -> None:
    assert geodesic_km(a[0], a[1], b[0], b[1]) == float.fromhex(expected)


# ── D2 ──


def failed() -> ProviderError:
    return ProviderError(status=None, retryable=False, message="가상: 실패")


def run_of(mock: MockProvider, geocoder: FakeGeocoder | None = None) -> DistanceRun:
    return DistanceRun(geocoder if geocoder is not None else FakeGeocoder(), llm_context(mock))


def prompts(mock: MockProvider) -> list[str]:
    return [user_text(c).splitlines()[0] for c in mock.calls]


GA = Coordinates(9.9, 99.9)
DA = Coordinates(9.99, 99.99)


def test_both_found_is_geodesic_times_the_road_factor() -> None:
    mock = MockProvider().enqueue_text(" Synthetic Ga \n").enqueue_text("Synthetic Da")
    geo = FakeGeocoder({"Synthetic Ga, KR": GA, "Synthetic Da, KR": DA})
    got = get_distance_km(run_of(mock, geo), "가상시가", "가상시다")
    assert got == Distance(geodesic_km(9.9, 99.9, 9.99, 99.99) * 1.3, "geocode")
    assert geo.queries == ["Synthetic Ga, KR", "Synthetic Da, KR"]
    assert len(mock.calls) == 2


def test_one_not_found_goes_to_the_ai_straight_distance_and_both_are_asked() -> None:
    mock = MockProvider().enqueue_text("Synthetic Ga").enqueue_text("Synthetic Da")
    mock.enqueue_text('{"distance_km": 92}')
    geo = FakeGeocoder({"Synthetic Da, KR": DA})
    got = get_distance_km(run_of(mock, geo), "가상시가", "가상시다")
    assert got == Distance(92 * 1.3, "ai_straight")
    assert geo.queries == ["Synthetic Ga, KR", "Synthetic Da, KR"]
    # AI 직선은 정규화 앞의 원문으로 묻는다(코랩 :1690)
    assert "출발지: 가상시가\n도착지: 가상시다\n국가 힌트: KR" in user_text(mock.calls[2])


def test_straight_over_the_cap_goes_to_the_ai_road_distance() -> None:
    mock = MockProvider().enqueue_text("A").enqueue_text("B").enqueue_text('{"distance_km": 901}')
    mock.enqueue_text('{"distance_km": 99}')
    got = get_distance_km(run_of(mock), "가상시라", "가상시마")
    assert got == Distance(99.0, "ai_road")  # 901 × 1.3 > 800
    assert "운송수단: 도로(트럭)" in user_text(mock.calls[3])


def test_straight_none_goes_to_the_ai_road_and_none_when_that_fails() -> None:
    mock = MockProvider().enqueue_text("A").enqueue_text("B")
    for _ in range(3):
        mock.enqueue_text("가상 설명")
    mock.enqueue_text('{"distance_km": 999}')  # 실거리도 800 넘음 → None
    assert get_distance_km(run_of(mock), "가상시라", "가상시마") == Distance(None, "none")
    assert len(mock.calls) == 6


@pytest.mark.parametrize(
    ("km", "mode", "hint", "expected"),
    [
        (800, "road", "KR", 800.0),
        (800.5, "road", "KR", None),
        (800.5, "parcel", "KR", None),
        (999.9, "rail", "KR", 999.9),
        (1000.5, "rail", "KR", None),
        (2999.0, "sea", "KR", 2999.0),
        (3000.5, "air", "KR", None),
        (90000.0, "road", "가상국", 90000.0),
        (9000.0, "sea_bulk", "KR", 9000.0),
        (0, "road", "KR", None),
        (-9.0, "road", "가상국", None),
        ("9,999", "road", "가상국", 9999.0),
        ("가상", "road", "KR", None),
    ],
)
def test_validate_distance_caps_only_kr(km: object, mode: str, hint: str, expected: float | None) -> None:
    assert validate_distance_km(km, mode, hint) == expected


def test_a_foreign_country_has_no_kr_suffix_and_no_cap() -> None:
    mock = MockProvider().enqueue_text("Synthetic Ra").enqueue_text("Synthetic Ma")
    mock.enqueue_text('{"distance_km": 901}')
    geo = FakeGeocoder()
    got = get_distance_km(run_of(mock, geo), "가상시라", "가상시마", "road", "가상국")
    assert got == Distance(901 * 1.3, "ai_straight")
    assert geo.queries == ["Synthetic Ra", "Synthetic Ma"]


def test_air_keeps_airports_and_iata_and_asks_the_airport_ai_otherwise() -> None:
    mock = MockProvider().enqueue_text('{"airport_name": "Synthetic Ja Airport", "iata": ""}')
    for name in ("Synthetic Airport Ga", "Synthetic Ja Airport"):
        mock.enqueue_text(name)
    mock.enqueue_text('{"distance_km": 93}')
    got = get_distance_km(run_of(mock), "가상공항가", "가상시자", "air", "KR")
    assert got == Distance(93 * 1.09, "ai_straight+airport")
    assert prompts(mock)[0].startswith("아래 지역에서")
    assert "지역: 가상시자\n국가 힌트: KR" in user_text(mock.calls[0])
    assert "출발지: 가상공항가\n도착지: Synthetic Ja Airport" in user_text(mock.calls[3])

    mock = MockProvider().enqueue_text("Synthetic Zzq").enqueue_text("Synthetic Zzr")
    mock.enqueue_text('{"distance_km": 94}')
    assert get_distance_km(run_of(mock), "ZZQ", "zzr", "air", "KR") == Distance(94 * 1.09, "ai_straight")
    assert looks_like_airport("가상 terminal") and not looks_like_airport("ZZQQ") and not looks_like_airport("")


def test_an_airport_ai_without_a_name_keeps_the_place() -> None:
    mock = MockProvider().enqueue_text('{"airport_name": "", "iata": "ZZQ"}').enqueue_text("[]")
    for name in ("A", "B"):
        mock.enqueue_text(name)
    mock.enqueue_text('{"distance_km": 95}')
    got = get_distance_km(run_of(mock), "가상시자", "가상시차", "air", "KR")
    assert got == Distance(95 * 1.09, "ai_straight")
    assert "출발지: 가상시자\n도착지: 가상시차" in user_text(mock.calls[4])


def test_a_failed_city_name_is_not_cached_and_the_destination_is_not_asked() -> None:
    mock = MockProvider().enqueue(failed()).enqueue_text('{"distance_km": 92}')
    mock.enqueue_text("Synthetic Ga").enqueue_text("Synthetic Da")
    run = run_of(mock)
    assert get_distance_km(run, "가상시가", "가상시다") == Distance(92 * 1.3, "ai_straight")
    assert len(mock.calls) == 2  # 출발 정규화(실패) → AI 직선. 도착 정규화 0
    # 같은 줄을 다시: 도시 정규화를 다시 부른다(실패는 캐시 안 됨). AI 직선은 캐시에서
    assert get_distance_km(run, "가상시가", "가상시다", "road", "KR") == Distance(92 * 1.3, "ai_straight")
    assert len(mock.calls) == 4
    assert run.cities == {"가상시가": "Synthetic Ga", "가상시다": "Synthetic Da"}


class RaisingGeocoder:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def geocode(self, query: str) -> Coordinates | NotFound:
        self.queries.append(query)
        raise RuntimeError("가상 지오코더 오류")


def test_a_geocoder_error_is_swallowed_and_not_cached() -> None:
    mock = MockProvider().enqueue_text("A").enqueue_text("B").enqueue_text('{"distance_km": 92}')
    geo = RaisingGeocoder()
    run = DistanceRun(geo, llm_context(mock))
    assert get_distance_km(run, "가상시가", "가상시다") == Distance(92 * 1.3, "ai_straight")
    assert geo.queries == ["A, KR"]  # 앞에서 예외 → 뒤는 안 부름
    assert get_distance_km(run, "가상시가", "가상시다") == Distance(92 * 1.3, "ai_straight")
    assert geo.queries == ["A, KR", "A, KR"] and run.geocodes == {}


def test_not_found_and_ai_answers_are_cached() -> None:
    mock = MockProvider().enqueue_text("A").enqueue_text("B").enqueue_text('{"distance_km": 92}')
    geo = FakeGeocoder()
    run = run_of(mock, geo)
    for _ in range(2):
        assert get_distance_km(run, "가상시가", "가상시다") == Distance(92 * 1.3, "ai_straight")
    assert geo.queries == ["A, KR", "B, KR"] and len(mock.calls) == 3


def test_none_answers_of_the_three_distance_ais_are_cached() -> None:
    """코랩 `@lru_cache`(`:1576`·`:1594`·`:1628`)는 None 도 기억한다 — 같은 줄을 다시 부르면 AI 부름 0(검증 B1)."""
    mock = MockProvider().enqueue_text("A").enqueue_text("B")
    for _ in range(6):
        mock.enqueue_text("가상 설명")  # AI 직선 셋·AI 실거리 셋 다 못 읽음 → 둘 다 None
    run = run_of(mock)
    for _ in range(2):
        assert get_distance_km(run, "가상시라", "가상시마") == Distance(None, "none")
    assert len(mock.calls) == 8
    assert run.straight == {("가상시라", "가상시마", "KR"): None}
    assert run.road == {("가상시라", "가상시마", "road", "KR"): None}

    mock = MockProvider().enqueue_text('{"airport_name": "", "iata": ""}').enqueue_text("{}")
    mock.enqueue_text("A").enqueue_text("B").enqueue_text('{"distance_km": 92}')
    run = run_of(mock)
    for _ in range(2):
        assert get_distance_km(run, "가상시자", "가상시차", "air", "KR") == Distance(92 * 1.09, "ai_straight")
    assert len(mock.calls) == 5
    assert run.airports == {("가상시자", "KR"): None, ("가상시차", "KR"): None}


def test_a_non_dict_json_answer_raises() -> None:
    mock = MockProvider().enqueue_text("A").enqueue_text("B").enqueue_text("[9]")
    with pytest.raises(AttributeError):
        get_distance_km(run_of(mock), "가상시가", "가상시다")


def test_empty_places_return_none_without_calls() -> None:
    mock = MockProvider()
    assert get_distance_km(run_of(mock), "가상시가", float("nan")) == Distance(None, "none")
    assert get_distance_km(run_of(mock), " ", "가상시다") == Distance(None, "none")
    assert mock.calls == []


def test_infer_distance_takes_a_valid_input_and_the_row_country() -> None:
    mock = MockProvider()
    row = pd.Series({"운송거리(km)": "99", "국가": "가상국", "출발지": "가상시가", "도착지": "가상시다"}, dtype=object)
    assert infer_distance(run_of(mock), row, "road") == Distance(99.0, "input")
    over = pd.Series({"운송거리(km)": 900.0, "출발지": "가상시가", "도착지": "가상시다"}, dtype=object)
    mock = MockProvider().enqueue_text("A").enqueue_text("B").enqueue_text('{"distance_km": 92}')
    assert infer_distance(run_of(mock), over, "road") == Distance(92 * 1.3, "ai_straight")  # 900 > 800 → 다시 구함
    assert infer_distance(run_of(MockProvider()), pd.Series({"출발지": "가상"}, dtype=object), "road") == Distance(
        None, "none"
    )


def test_no_geocoder_never_finds() -> None:
    assert NoGeocoder().geocode("Synthetic Ga, KR") == NotFound("Synthetic Ga, KR")


# ── D3 프롬프트 글자(코랩 f-문자열 글자 그대로 — 읽기판 :1046-1056 · :1583-1589 · :1602-1607 · :1637-1644) ──


def colab_city(city: str) -> str:
    return f"""
    다음 도시를 영어 도시명으로 변환하라.

    {city}

    예
    서울 → Seoul
    부산 → Busan

    영어 도시명만 출력
    """


def colab_road(origin: str, dest: str, mode_label: str, country_hint: str) -> str:
    return f"""두 지점 간 실제 이동 거리를 편도 기준 km로 추정하라.
출발지: {origin}
도착지: {dest}
운송수단: {mode_label}
국가 힌트: {country_hint}

JSON으로만 답하라: {{"distance_km": <숫자>}}"""


def colab_straight(origin: str, dest: str, country_hint: str) -> str:
    return f"""두 지점 간 직선거리(대권거리, great-circle distance)를 km로 추정하라.
출발지: {origin}
도착지: {dest}
국가 힌트: {country_hint}

JSON으로만 답하라: {{"distance_km": <숫자>}}"""


def colab_airport(location: str, country_hint: str) -> str:
    return f"""아래 지역에서 국내선/국제선 항공편을 이용한다면 가장 가까운, 실제로 정기 여객노선이 있는
주요 공항의 이름을 알려줘. 단순히 지리적으로 제일 가까운 소형 비행장이 아니라
사람들이 실제로 항공권을 구매해 이용하는 공항을 골라라.

지역: {location}
국가 힌트: {country_hint}

JSON으로만 답하라: {{"airport_name": "<공항 정식 명칭, 국가 포함>", "iata": "<IATA 코드, 모르면 빈 문자열>"}}"""


SYS = "Return only valid JSON, with no other text before or after it."  # :259
RETRY = "\n\n반드시 JSON 객체 하나만 출력하라. 다른 설명/문장은 절대 포함하지 마라."  # :261


def sent(request: ProviderRequest) -> tuple[str, str, int]:
    return ("\n".join(s.text for s in request.system), user_text(request), request.max_output_tokens)


def test_the_four_distance_prompts_match_the_colab() -> None:
    """도시 정규화는 앞뒤 공백만 다르다(core 읽개가 걷는다 — 「코랩과 다른 자리」). JSON 셋은 덧붙임까지."""
    mock = MockProvider().enqueue_text("A").enqueue_text("B")
    for _ in range(6):
        mock.enqueue_text("가상 설명")  # AI 직선 셋·AI 실거리 셋 다 못 읽음
    get_distance_km(run_of(mock), "가상시가", "가상시다", "rail", "가상국")
    city = colab_city("가상시가")
    assert sent(mock.calls[0]) == ("", city.strip(), 20) and city != city.strip()
    straight = colab_straight("가상시가", "가상시다", "가상국")
    road = colab_road("가상시가", "가상시다", "철도", "가상국")
    assert [sent(c) for c in mock.calls[2:]] == [
        (SYS, straight, 60),
        (SYS, straight + RETRY, 60),
        (SYS, straight + RETRY, 60),
        (SYS, road, 60),
        (SYS, road + RETRY, 60),
        (SYS, road + RETRY, 60),
    ]

    airport = colab_airport("가상시자", "KR")
    mock = MockProvider().enqueue_text("가상").enqueue_text("가상").enqueue_text("가상")
    get_distance_km(run_of(mock), "가상시자", "ZZQ", "air", "KR")
    assert [sent(c) for c in mock.calls[:3]] == [
        (SYS, airport, 80),
        (SYS, airport + RETRY, 80),
        (SYS, airport + RETRY, 80),
    ]
    road_label = colab_road("A", "B", "sea_bulk", "KR")  # 표에 없는 mode 는 그대로
    mock = MockProvider().enqueue_text("A").enqueue_text("B").enqueue_text('{"distance_km": 0}')
    mock.enqueue_text('{"distance_km": 9.5}')
    assert get_distance_km(run_of(mock), "A", "B", "sea_bulk", "KR") == Distance(9.5, "ai_road")
    assert sent(mock.calls[3]) == (SYS, road_label, 60)


def test_prompt_ids_are_the_files() -> None:
    assert (CITY_NAME_PROMPT, DISTANCE_STRAIGHT_PROMPT, DISTANCE_ROAD_PROMPT, AIRPORT_PROMPT) == (
        "inventory/scope3-colab-city-name@1",
        "inventory/scope3-colab-distance-straight@1",
        "inventory/scope3-colab-distance-road@1",
        "inventory/scope3-colab-airport@1",
    )
