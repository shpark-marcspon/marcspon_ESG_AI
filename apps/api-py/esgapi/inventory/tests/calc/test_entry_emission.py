"""입력 행 배출량 셈(calc/entry_emission.py — 밴드 S12a ①, 결정 MARC-ENT-463)의 순수 시험. DB 0.

손셈 값은 지어낸 검사 값이다(실제 계수 0). 환산은 패키지의 unit-conversions.json(정의값)을 그대로 넘긴다.
"""

import ast
import inspect
from decimal import Context, Decimal

import pytest

from esgapi.inventory.calc import entry_emission
from esgapi.inventory.calc.entry_emission import (
    EMISSION_OUT_OF_RANGE,
    FACTOR_UNIT_INVALID,
    UNIT_CONVERSION_MISSING,
    Gas,
    Version,
    emission,
)
from esgapi.inventory.data_loader import read_data
from esgapi.inventory.service.utils.entries import conversions_of

CONVERSIONS = conversions_of(read_data("unit-conversions.json")["unitConversions"])  # type: ignore[arg-type]

# 순발열량 켬: 투입 L · ncv 30 MJ/L · 계수 kg/TJ · CO2 70000×1 + CH4 3×25 = 70075 (지어낸 값)
WITH_NCV = Version(
    input_unit="L",
    ncv=Decimal(30),
    ncv_unit="MJ",
    factor_unit="kg/TJ",
    gases=(Gas(Decimal(70000), Decimal(1)), Gas(Decimal(3), Decimal(25))),
)
# 순발열량 끔: 투입 t · 계수 kg/t · CO2 2×1 (지어낸 값)
WITHOUT_NCV = Version(input_unit="t", ncv=None, ncv_unit=None, factor_unit="kg/t", gases=(Gas(Decimal(2), Decimal(1)),))


def test_with_ncv_the_hand_sum() -> None:
    # 2 kL → 2000 L → ×30 = 60000 MJ → 0.06 TJ → ×70075 = 4204.5 kg → 4.2045 t
    assert emission(Decimal(2), "kL", WITH_NCV, CONVERSIONS) == Decimal("4.204500000000")


def test_without_ncv_the_hand_sum() -> None:
    # 500 kg → 0.5 t → ×2 = 1 kg → 0.001 t
    assert emission(Decimal(500), "kg", WITHOUT_NCV, CONVERSIONS) == Decimal("0.001000000000")


def test_a_tonne_numerator_needs_no_mass_step() -> None:
    # 분자 t: 같은 입력, 계수 단위만 t/t · CO2 0.002 → 0.5 t × 0.002 = 0.001 t(kg → t 쌍을 안 거침)
    version = Version("t", None, None, "t/t", (Gas(Decimal("0.002"), Decimal(1)),))
    assert emission(Decimal(500), "kg", version, CONVERSIONS) == Decimal("0.001000000000")


def test_a_factor_unit_in_tonnes_follows_the_letters() -> None:
    """MARC-ENT-474 (나) 자리: 판의 factor_unit 이 t/TJ 면 셈은 그 글자를 따른다 — 같은 수의 계수면 1000 배, 같은 뜻의
    계수(1/1000 로 적은 것)면 같은 결과(kg/TJ 판과 견줌)."""
    kilo = emission(Decimal(2), "kL", WITH_NCV, CONVERSIONS)
    same_numbers = Version("L", Decimal(30), "MJ", "t/TJ", WITH_NCV.gases)
    same_meaning = Version(
        "L", Decimal(30), "MJ", "t/TJ", (Gas(Decimal(70), Decimal(1)), Gas(Decimal("0.003"), Decimal(25)))
    )
    assert isinstance(kilo, Decimal)
    assert emission(Decimal(2), "kL", same_numbers, CONVERSIONS) == kilo * 1000
    assert emission(Decimal(2), "kL", same_meaning, CONVERSIONS) == kilo


def test_the_same_unit_needs_no_pair() -> None:
    assert ("L", "L") not in CONVERSIONS  # 분모: 파일에 같은 단위 쌍은 없다
    assert emission(Decimal(1000), "L", WITH_NCV, CONVERSIONS) == Decimal("2.102250000000")


@pytest.mark.parametrize(
    ("row_unit", "version"),
    [
        ("Nm3", WITH_NCV),  # 행 단위 → 투입 단위 쌍 없음(m3 ↔ Nm3 는 일부러 없다)
        ("L", Version("L", Decimal(30), "kWh", "kg/TJ", WITH_NCV.gases)),  # ncv 에너지 → 분모 쌍 없음(kWh → TJ)
        ("kg", Version("kg", None, None, "kg/MWh", WITHOUT_NCV.gases)),  # 투입 → 분모 쌍 없음
        ("t", Version("t", None, None, "lb/t", WITHOUT_NCV.gases)),  # 분자 → t 쌍 없음
    ],
)
def test_a_missing_pair_is_a_problem(row_unit: str, version: Version) -> None:
    assert emission(Decimal(1), row_unit, version, CONVERSIONS) == UNIT_CONVERSION_MISSING


@pytest.mark.parametrize("factor_unit", ["kgTJ", "/TJ", "kg/"])
def test_a_factor_unit_out_of_form_is_a_problem(factor_unit: str) -> None:
    version = Version("t", None, None, factor_unit, WITHOUT_NCV.gases)
    assert emission(Decimal(1), "t", version, CONVERSIONS) == FACTOR_UNIT_INVALID


def test_no_total_is_no_emission() -> None:
    """빈 행·N/A 는 부르는 쪽이 None 을 넘긴다 → None(행 emission NULL)."""
    assert emission(None, "kL", WITH_NCV, CONVERSIONS) is None


def test_the_end_rounds_once_half_up_to_twelve_places() -> None:
    version = Version("t", None, None, "t/t", (Gas(Decimal("0.0000000000005"), Decimal(1)),))
    assert emission(Decimal(1), "t", version, CONVERSIONS) == Decimal("0.000000000001")  # 0.5e-12 → 위로
    version = Version("t", None, None, "t/t", (Gas(Decimal("0.0000000000004999"), Decimal(1)),))
    assert emission(Decimal(1), "t", version, CONVERSIONS) == Decimal("0.000000000000")


def test_long_products_are_not_rounded_in_the_middle() -> None:
    """28자리를 넘는 곱이어도 중간 반올림 0(기본 문맥이면 끝자리가 바뀐다)."""
    version = Version("t", None, None, "t/t", (Gas(Decimal("0.123456789123"), Decimal("1.987654321987")),))
    total = Decimal("987654321098765432.123456")
    exact = Decimal("242359921487975220.896216796891")
    assert emission(total, "t", version, CONVERSIONS) == exact
    product = total * Decimal("0.123456789123") * Decimal("1.987654321987")  # 기본 문맥(28자리)의 곱
    in_default_context = product.quantize(Decimal(10) ** -12, context=Context(prec=60))
    assert in_default_context != exact  # 분모: 기본 문맥(28자리)은 다르게 낸다


def test_an_emission_too_large_for_the_column_is_a_problem() -> None:
    version = Version("t", None, None, "t/t", (Gas(Decimal(10) ** 18, Decimal(1)),))
    assert emission(Decimal(1), "t", version, CONVERSIONS) == EMISSION_OUT_OF_RANGE
    version = Version("t", None, None, "t/t", (Gas(Decimal(10) ** 17, Decimal(9)),))
    assert isinstance(emission(Decimal(1), "t", version, CONVERSIONS), Decimal)  # 짝: 18자리 안


def test_the_calc_does_not_call_the_default_factor_unit() -> None:
    """셈은 판의 글자만 본다 — 계수 단위 기본값(default_factor_unit, MARC-ENT-474)을 부르지 않는다(P7)."""
    tree = ast.parse(inspect.getsource(entry_emission))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    names |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
    assert "default_factor_unit" not in names
    assert "emission" in names or "Version" in names  # 분모: 이름을 실제로 모았다
