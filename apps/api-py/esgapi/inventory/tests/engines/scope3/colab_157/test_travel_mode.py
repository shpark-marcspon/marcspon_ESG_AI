"""이동수단 정규화(코랩 `normalize_travel_mode` `:8534` 마지막 판).

차례: 앞 표 → `detect_travel_mode_rule`(`:1384`) → AI → car.

AI(`_ai_normalize_travel_mode` `:8523`)는 정규화 글로 부르고 lru_cache 는 None 도 기억한다.
"""

import math

import pytest

from esgapi.core.llm.providers.mock import MockProvider
from esgapi.inventory.engines.scope3.colab_157.travel_mode import (
    TravelMode,
    TravelModeCache,
    detect_travel_mode_rule,
    normalize_travel_mode,
)
from esgapi.inventory.tests.engines.scope3.colab_157.support import llm_context
from esgapi.inventory.tests.scope3_llm_support import user_text


@pytest.mark.parametrize(
    ("raw", "mode"),
    [
        ("가상 KTX", "train"),
        ("가상 호텔", "lodging"),
        ("가상 렌터카", "rental_car"),  # 「car」 보다 앞
        ("가상 버스 택시", "taxi"),  # 표 차례: 택시가 버스보다 앞
        ("가상 국내선 항공", "flight"),
        ("가상 자가용", "car"),
        ("가상 전기차", "train"),  # 「전기차」 ⊃ 「기차」 — 코랩 그대로
    ],
)
def test_the_fix_table_comes_first(raw: str, mode: str) -> None:
    mock = MockProvider()
    assert normalize_travel_mode(llm_context(mock), TravelModeCache(), raw) == TravelMode(mode, "rule_fix")
    assert mock.calls == []


@pytest.mark.parametrize(
    ("raw", "mode"),
    [("가상 셔틀", "bus"), ("가상 EV", "car_ev"), ("가상 오토바이", "motorcycle"), ("가상 페리", "ferry")],
)
def test_the_detect_rule_catches_what_the_fix_table_does_not(raw: str, mode: str) -> None:
    mock = MockProvider()
    assert normalize_travel_mode(llm_context(mock), TravelModeCache(), raw) == TravelMode(mode, "rule")
    assert mock.calls == []


def test_detect_rule_keeps_the_colab_order() -> None:
    assert detect_travel_mode_rule("가상 비즈니스 항공 장거리") == "flight_long_biz"
    assert detect_travel_mode_rule("가상 코치 버스") == "coach"
    assert detect_travel_mode_rule(None) == "unknown"
    assert detect_travel_mode_rule("nan") == "unknown"


def test_the_ai_answer_is_normalized_with_fix_norm() -> None:
    """AI 는 정규화 글(「가상무엇」)로 묻고, 답 「 Flight! 」 는 `_fix_norm` 으로 「flight」."""
    mock = MockProvider().enqueue_text('{"mode": " Flight! "}')
    got = normalize_travel_mode(llm_context(mock), TravelModeCache(), "가상 무엇")
    assert got == TravelMode("flight", "ai")
    assert "입력값: 가상무엇\n" in user_text(mock.calls[0])


def test_an_answer_outside_the_six_falls_to_car() -> None:
    mock = MockProvider().enqueue_text('{"mode": "plane"}')
    assert normalize_travel_mode(llm_context(mock), TravelModeCache(), "가상 무엇") == TravelMode("car", "default_car")
    assert len(mock.calls) == 1


@pytest.mark.parametrize("raw", ["", "  ", None, math.nan, "-·-"])
def test_empty_is_car_without_calling_the_ai(raw: object) -> None:
    mock = MockProvider()
    assert normalize_travel_mode(llm_context(mock), TravelModeCache(), raw) == TravelMode("car", "default_car")
    assert mock.calls == []


def test_an_ai_failure_is_cached() -> None:
    """같은 정규화 글의 둘째 줄(「가상-무엇」 → 「가상무엇」)은 공급사를 다시 부르지 않는다(None 도 기억)."""
    mock = MockProvider()
    context, cache = llm_context(mock), TravelModeCache()
    first = normalize_travel_mode(context, cache, "가상 무엇")
    second = normalize_travel_mode(context, cache, "가상-무엇")
    assert first == second == TravelMode("car", "default_car")
    assert len(mock.calls) == 3  # 첫 줄의 JSON 셋뿐
    assert cache.modes == {"가상무엇": None}


def test_a_non_dict_json_raises_and_is_not_cached() -> None:
    mock = MockProvider().enqueue_text('"bus"')
    context, cache = llm_context(mock), TravelModeCache()
    with pytest.raises(AttributeError):
        normalize_travel_mode(context, cache, "가상 무엇")
    assert cache.modes == {}
