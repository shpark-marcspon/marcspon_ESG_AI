"""T2 에너지 단위 환산 — 코랩 `convert_energy_unit`(`:3846`)·AI 배수(`_ai_unit_conversion_factor` `:3809`, lru_cache
`:3808`)·발열량 다리(`_bridge_convert_via_lhv` `:9146`). 발열량·배수는 코랩 상수(`ENERGY_BASE_UNIT` `:3723` 등)다.
"""

import math
from typing import cast

import pytest

from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import ProviderError
from esgapi.inventory.engines.scope3.colab_157.energy import (
    EnergyConversion,
    bridge_convert_via_lhv,
    bridge_unit_norm,
    convert_energy_unit,
    detect_energy_name,
    fix_convert_to_ef_unit,
    patch_convert_energy_to_ef_unit,
)
from esgapi.inventory.engines.scope3.colab_157.units import UnitFactorCache, convert_weight_to_kg
from esgapi.inventory.tests.engines.scope3.colab_157.support import llm_context
from esgapi.inventory.tests.scope3_llm_support import user_text


def convert(value: float | None, unit: str, name: str, mock: MockProvider | None = None) -> EnergyConversion:
    return convert_energy_unit(llm_context(mock or MockProvider()), UnitFactorCache(), value, unit, name)


def failed() -> ProviderError:
    return ProviderError(status=None, retryable=False, message="가상: 실패")


@pytest.mark.parametrize(
    ("raw", "std"),
    [
        ("경유", "경유"),
        ("LPG", "액화석유가스(LPG)"),  # 정확 별칭이 「도시가스(LPG)」 의 부분 별칭보다 먼저(`:3778` 패치)
        ("도시가스", "도시가스(LNG)"),
        ("도시가스(LNG)", "도시가스(LNG)"),
        ("천연가스(LNG)", "천연가스(LNG)"),
        ("가상 보일러 등유", "보일러 등유"),
        ("가상연료", "가상연료"),
    ],
)
def test_detect_energy_name(raw: str, std: str) -> None:
    assert detect_energy_name(raw) == std


def test_the_same_unit_passes_through_without_a_note() -> None:
    assert convert(9.5, "L", "경유") == EnergyConversion(9.5, "L", "", "same")
    assert convert(9.5, " kwh ", "전력") == EnergyConversion(9.5, "kWh", "", "same")


def test_mwh_to_kwh_is_1000_by_the_rule_table() -> None:
    assert convert(9.2, "MWh", "전력") == EnergyConversion(9200.0, "kWh", "MWh→kWh (×1000)", "rule")


def test_gcal_to_gj_for_steam() -> None:
    got = convert(9.0, "Gcal", "스팀")
    assert (got.value, got.unit, got.note, got.via) == (9.0 * 4.1868, "GJ", "Gcal→GJ (×4.1868)", "rule")


def test_kwh_of_diesel_goes_through_its_heating_value() -> None:
    """연료(기준 L)를 kWh 로 적으면 MJ 를 거쳐 ÷ 순발열량 35.3."""
    got = convert(100.0, "kWh", "경유")
    assert got == EnergyConversion(100.0 * 3.6 / 35.3, "L", "kWh→L (발열량 환산: ×0.101983)", "lhv")


def test_same_family_mass_and_volume_and_gas_units() -> None:
    assert convert(9.0, "ton", "천연가스(LNG)") == EnergyConversion(9000.0, "kg", "ton→kg (×1000.0)", "rule")
    assert convert(9.0, "kL", "경유") == EnergyConversion(9000.0, "L", "kL→L (×1000.0)", "rule")
    assert convert(9.0, "m³", "도시가스") == EnergyConversion(9.0, "Nm³", "m³→Nm³ (×1.0)", "rule")


def test_an_unknown_energy_keeps_the_value() -> None:
    assert convert(9.0, "가상단위", "가상연료") == EnergyConversion(9.0, "가상단위", "", "none")
    assert convert(None, "kWh", "전력") == EnergyConversion(None, "kWh", "", "none")


def test_an_unknown_unit_asks_the_ai_with_the_energy_name_as_context() -> None:
    mock = MockProvider().enqueue_text('{"factor": 9.9}')
    got = convert(99.0, "가상와트", "전력", mock)
    assert got == EnergyConversion(99.0 * 9.9, "kWh", "가상와트→kWh (AI 판단: ×9.9)", "ai")
    prompt = user_text(mock.calls[0])
    assert prompt.startswith("단위 환산 배수를 추정하라.\n입력 단위: 가상와트\n목표(기준) 단위: kWh\n맥락: 전력\n")


def test_the_same_unit_base_and_context_asks_once_per_run() -> None:
    """따를 표 5: C3 3번과 C8-1 3번(같은 단위·기준·맥락)은 한 번 — 캐시는 C5 무게 배수와 같은 것(실행 하나)."""
    mock = MockProvider().enqueue_text('{"factor": 9.9}').enqueue_text('{"factor": 9.8}')
    context, cache = llm_context(mock), UnitFactorCache()
    first = convert_energy_unit(context, cache, 99.0, "가상와트", "전력")
    again = convert_energy_unit(context, cache, 91.0, "가상와트", "전력")
    assert (first.value, again.value, len(mock.calls)) == (99.0 * 9.9, 91.0 * 9.9, 1)
    other_context = convert_energy_unit(context, cache, 91.0, "가상와트", "전기")  # 맥락이 다르면 새 열쇠
    assert (other_context.value, len(mock.calls)) == (91.0 * 9.8, 2)
    assert set(cache.factors) == {("가상와트", "kWh", "전력"), ("가상와트", "kWh", "전기")}


def test_energy_and_weight_factors_share_one_cache_with_distinct_keys() -> None:
    mock = MockProvider().enqueue_text('{"factor": 9.9}').enqueue_text('{"factor": 9.7}')
    context, cache = llm_context(mock), UnitFactorCache()
    convert_energy_unit(context, cache, 1.0, "가상와트", "전력")
    convert_weight_to_kg(context, cache, 1.0, "가상와트")
    assert set(cache.factors) == {("가상와트", "kWh", "전력"), ("가상와트", "kg", "")}


def test_when_the_ai_fails_the_value_is_kept_with_a_retry_note() -> None:
    mock = MockProvider()
    for _ in range(5):
        mock.enqueue(failed())
    got = convert(9.0, "가상와트", "전력", mock)
    assert got == EnergyConversion(
        9.0, "가상와트", "가상와트→kWh (AI 환산 재시도 필요 - 값 미변환, 수동 확인 권장)", "ai_failed"
    )


def test_a_fuel_unit_outside_the_tables_asks_the_ai_for_the_fuel_base() -> None:
    mock = MockProvider().enqueue_text('{"factor": 9.3}')
    got = convert(9.0, "가상드럼", "경유", mock)
    assert got == EnergyConversion(9.0 * 9.3, "L", "가상드럼→L (AI 판단: ×9.3)", "ai")


# ── 발열량 다리(C3 의 대체 매칭) ──


def test_the_lhv_bridge_from_city_gas_nm3_to_natural_gas_kg() -> None:
    """rest C3 4번: 도시가스(LNG) 38.5 MJ/Nm³ → 천연가스(LNG) 49.4 MJ/kg."""
    got = bridge_convert_via_lhv(9300.0, "Nm³", "도시가스", "천연가스(LNG)", "kg")
    note = "Nm³→kg (발열량 환산: 도시가스→천연가스(LNG), ×0.779352)"
    assert got == EnergyConversion(9300.0 * 38.5 / 49.4, "kg", note, "lhv")


@pytest.mark.parametrize(
    ("unit", "to", "to_unit"),
    [("L", "천연가스(LNG)", "kg"), ("Nm³", "천연가스(LNG)", "L"), ("Nm³", "전력", "kWh"), ("Nm³", "가상연료", "kg")],
)
def test_the_lhv_bridge_refuses_mismatched_units_or_missing_heating_values(unit: str, to: str, to_unit: str) -> None:
    assert bridge_convert_via_lhv(9.0, unit, "도시가스", to, to_unit) == EnergyConversion(9.0, unit, "", "none")


# ── 계수 단위로 맞추기(C11·C14 몫 — c1b 가 쓴다) ──


def test_fix_convert_holds_the_value_when_units_still_differ() -> None:
    context, cache = llm_context(MockProvider()), UnitFactorCache()
    held = fix_convert_to_ef_unit(context, cache, 9.0, "L", "경유", "kg")
    assert (held.value, held.unit, held.note) == (None, "L", "[단위 불일치로 산정 보류: L→kg]")
    ok = fix_convert_to_ef_unit(context, cache, 0.92, "MWh", "전력", "kWh")
    assert (ok.value, ok.unit, ok.note) == (920.0, "kWh", "MWh→kWh (×1000)")


def test_patch_convert_keeps_the_conversion_even_when_units_differ() -> None:
    context, cache = llm_context(MockProvider()), UnitFactorCache()
    kept = patch_convert_energy_to_ef_unit(context, cache, "9", "L", "경유", "kg")
    assert (kept.value, kept.unit, kept.note) == (9.0, "L", "")


# ── MARC-ISSUE-395 2·3번(S3C-r1) ──


@pytest.mark.parametrize(
    ("raw", "norm"),
    [(None, ""), ("", ""), (0, ""), (0.0, ""), (False, ""), (math.nan, "nan"), ("kg", "kg"), (" Nm³ ", "nm3")],
    ids=["none", "empty", "zero", "zero-float", "false", "nan", "kg", "nm3"],
)
def test_the_lhv_bridge_unit_norm_is_the_colab_str_u_or_empty(raw: object, norm: str) -> None:
    """코랩 `_u_norm`(`:9154`) `str(u or "")`: 거짓 값(0·0.0·False)도 빈 글자(우리 옛 판은 「0」·「false」)."""
    assert bridge_unit_norm(raw) == norm


def test_a_nan_context_name_and_the_nan_text_give_the_same_conversion_without_asking_the_ai() -> None:
    """395-2(그대로 + 글): `std_name` 이 NaN 이면 코랩은 NaN 객체, 우리는 「nan」 글자를 맥락으로 넘긴다. 두 쪽 다
    `detect_energy_name` 이 기준단위를 못 찾아 값을 그대로 둔다 — AI 배수(프롬프트·캐시)에 닿지 않는다(S3C-r1 2-0 e)."""
    for unit, ef_unit in (("가상단위", "kWh"), ("kWh", "kWh"), ("L", "kg")):
        mock_nan, mock_text = MockProvider(), MockProvider()
        as_nan = fix_convert_to_ef_unit(
            llm_context(mock_nan), UnitFactorCache(), 9.5, unit, cast(str, math.nan), ef_unit
        )
        as_text = fix_convert_to_ef_unit(llm_context(mock_text), UnitFactorCache(), 9.5, unit, "nan", ef_unit)
        assert as_nan == as_text
        assert mock_nan.calls == [] and mock_text.calls == []
    assert detect_energy_name(math.nan) == detect_energy_name("nan") == "nan"
