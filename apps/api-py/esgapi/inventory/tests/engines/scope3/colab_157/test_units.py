"""무게 단위 → kg(코랩 `convert_to_base_unit(…, "weight")` `:3997`)와 AI 배수(`_ai_unit_conversion_factor` `:3809`).

규칙표 `_WEIGHT_TO_KG`(`:3683`) → JSON 프롬프트 셋 → 단순 프롬프트 둘 → None(1:1 통과). lru_cache 는 None 도 기억하고
예외(답이 dict 가 아닌 JSON 의 `.get`)는 기억하지 않는다.
"""

import pytest

from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import ProviderError
from esgapi.inventory.engines.scope3.colab_157.units import UnitConversion, UnitFactorCache, convert_weight_to_kg
from esgapi.inventory.tests.engines.scope3.colab_157.support import llm_context
from esgapi.inventory.tests.scope3_llm_support import user_text


def failed() -> ProviderError:
    return ProviderError(status=None, retryable=False, message="가상: 실패")


@pytest.mark.parametrize(
    ("unit", "ratio"),
    [("ton", 1000.0), ("g", 0.001), (" KG ", 1.0), ("Metric-Ton", None), ("톤", 1000.0), ("lbs", 0.453592)],
)
def test_the_rule_table(unit: str, ratio: float | None) -> None:
    mock = MockProvider()
    got = convert_weight_to_kg(llm_context(mock), UnitFactorCache(), 9.5, unit)
    if ratio is None:  # 「metric-ton」 → normalize 가 「metricton」 — 표에 없다(AI 로, 여기서는 실패)
        assert (got.via, len(mock.calls)) == ("none", 5)
        return
    assert got == UnitConversion(9.5 * ratio, "kg", ratio, unit, "rule")
    assert mock.calls == []


def test_metric_ton_with_a_space_goes_to_the_ai() -> None:
    """표의 「metric ton」 키는 `normalize_unit` 이 공백을 지워 닿지 않는다(코랩 그대로) — AI 에 원문 그대로 묻는다."""
    mock = MockProvider().enqueue_text('{"factor": 950}')
    got = convert_weight_to_kg(llm_context(mock), UnitFactorCache(), 9.5, "metric ton")
    assert got == UnitConversion(9.5 * 950, "kg", 950.0, "metric ton", "ai")
    assert "입력 단위: metric ton\n" in user_text(mock.calls[0])


def test_an_empty_unit_goes_to_the_ai_with_an_empty_unit_raw() -> None:
    mock = MockProvider().enqueue_text('```json\n{"factor": "9.25"}\n```')
    got = convert_weight_to_kg(llm_context(mock), UnitFactorCache(), 9.5, "")
    assert got == UnitConversion(9.5 * 9.25, "kg", 9.25, "", "ai")
    assert "입력 단위: \n" in user_text(mock.calls[0])


def test_no_value_passes_through_without_calling() -> None:
    mock = MockProvider()
    assert convert_weight_to_kg(llm_context(mock), UnitFactorCache(), None, "가상단위") == UnitConversion(
        None, "가상단위", 1.0, "가상단위", "none"
    )
    assert mock.calls == []


def test_json_fails_three_times_then_the_simple_prompt_gives_a_number() -> None:
    mock = MockProvider().enqueue(failed()).enqueue_text("가상").enqueue_text("{}").enqueue_text("약 9,250.5 배")
    got = convert_weight_to_kg(llm_context(mock), UnitFactorCache(), 9.5, "가상단위")
    assert got == UnitConversion(9.5 * 9250.5, "kg", 9250.5, "가상단위", "ai")
    assert [c.max_output_tokens for c in mock.calls] == [80, 80, 80, 30]


def test_a_non_positive_json_factor_falls_to_the_simple_prompt() -> None:
    """JSON 의 0 은 단순 프롬프트로. 단순 답 「-9.5」 는 빈 글이 아니라 다시 묻지 않고, 음수라 None(코랩 그대로)."""
    mock = MockProvider().enqueue_text('{"factor": 0}').enqueue_text("-9.5").enqueue_text("9e-3")
    got = convert_weight_to_kg(llm_context(mock), UnitFactorCache(), 9.5, "가상단위")
    assert (got.ratio, got.via) == (1.0, "none")
    assert (len(mock.calls), mock.pending) == (2, 1)
    mock = MockProvider().enqueue_text('{"factor": -9}').enqueue_text("9e-3")
    assert convert_weight_to_kg(llm_context(mock), UnitFactorCache(), 9.5, "가상단위").ratio == 9e-3


def test_all_fail_passes_the_value_through_as_none() -> None:
    mock = MockProvider()
    got = convert_weight_to_kg(llm_context(mock), UnitFactorCache(), 9.5, "가상단위")
    assert got == UnitConversion(9.5, "가상단위", 1.0, "가상단위", "none")
    assert len(mock.calls) == 5


def test_the_cache_remembers_a_failure() -> None:
    """lru_cache 꼴: 같은 단위의 둘째 줄은 공급사를 다시 부르지 않는다(None 도 기억)."""
    mock = MockProvider()
    context, cache = llm_context(mock), UnitFactorCache()
    first = convert_weight_to_kg(context, cache, 9.5, "가상단위")
    second = convert_weight_to_kg(context, cache, 9.25, "가상단위")
    assert (first.via, second.via) == ("none", "none")
    assert len(mock.calls) == 5  # 첫 줄의 JSON 셋 + 단순 둘뿐
    assert cache.factors == {("가상단위", "kg", ""): None}


def test_the_cache_remembers_a_success() -> None:
    mock = MockProvider().enqueue_text('{"factor": 9.5}')
    context, cache = llm_context(mock), UnitFactorCache()
    convert_weight_to_kg(context, cache, 9.5, "가상단위")
    assert convert_weight_to_kg(context, cache, 9.25, "가상단위").value == 9.25 * 9.5
    assert len(mock.calls) == 1


def test_a_non_dict_json_raises_and_is_not_cached() -> None:
    """`[9]` 는 JSON 으로 읽혀 코랩 `parsed.get` 이 AttributeError — lru_cache 는 예외를 기억하지 않는다."""
    mock = MockProvider().enqueue_text("[9]").enqueue_text('{"factor": 9.5}')
    context, cache = llm_context(mock), UnitFactorCache()
    with pytest.raises(AttributeError):
        convert_weight_to_kg(context, cache, 9.5, "가상단위")
    assert cache.factors == {}
    assert convert_weight_to_kg(context, cache, 9.5, "가상단위").ratio == 9.5
    assert len(mock.calls) == 2
