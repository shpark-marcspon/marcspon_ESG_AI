"""온실가스 풀의 순수 도움말(밴드 K1b-2a ① — service/utils/ghg_pool.py). 순수 층(DB·경로·권한 0).

선택 목록이 원천 파일(단위 환산표·reference 대응표·낱줄)과 어긋나면 빨갛다. 검사 규칙은 칸마다 거절 하나와 됨의 짝.
숫자는 지어낸 것이다(실제 계수·GWP 0).
"""

import ast
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from esgapi.inventory.service.utils import ghg_pool
from esgapi.inventory.service.utils.ghg_pool import (
    COUNTRIES,
    GASES,
    INDUSTRIES,
    UNITS,
    FactorDraft,
    FactorValues,
    GasDraft,
    check_factor,
    decimal_text,
    default_factor_unit,
    is_factor_unit,
    parent_level,
    parse_decimal,
    unit_kind,
)

ESGAPI = Path(__file__).resolve().parents[4]


def draft(**fields: object) -> FactorDraft:
    base = FactorDraft(
        name=" 계수 가 ",
        source="지어낸 출처",
        base_year=2024,
        tier=1,
        country_code="KR",
        industry_code="other",
        input_unit=("volume", "L"),
        emission_unit=None,
        ncv_enabled=False,
        ncv=None,
        ncv_unit=None,
        factor_unit=None,
        gases=(GasDraft("CO2", enabled=True, factor="1.25", gwp="1"),),
        note="",
    )
    return replace(base, **fields)  # type: ignore[arg-type]


def errors_of(made: FactorDraft) -> dict[str, str]:
    result = check_factor(made)
    assert isinstance(result, dict), result
    return result


# ── 목록 ─────────────────────────────────────────────────────────────


def test_the_gases_are_seven_in_the_fixed_order() -> None:
    assert GASES == ("CO2", "CH4", "N2O", "HFCs", "PFCs", "SF6", "NF3")


def test_the_units_are_exactly_the_names_in_the_conversion_table() -> None:
    table = json.loads((ESGAPI / "inventory/data/unit-conversions.json").read_text())["unitConversions"]
    in_file = {row["from"] for row in table} | {row["to"] for row in table}
    listed = [unit for units in UNITS.values() for unit in units]
    assert len(listed) == len(set(listed)) == len(in_file) == 14  # 분모: 새 단위 0, 겹침 0
    assert set(listed) == in_file


def test_the_industries_are_the_mapping_sectors_and_other() -> None:
    mapping = json.loads((ESGAPI / "reference/data/mappings.kr-ets.json").read_text())
    assert list(INDUSTRIES) == [(sector["key"], sector["label"]) for sector in mapping["sectors"]] + [("other", "기타")]


def test_the_countries_are_the_regions_of_the_records() -> None:
    lines = (ESGAPI / "reference/data/factors.kr.jsonl").read_text().splitlines()
    regions = {json.loads(line)["region"] for line in lines}
    assert {code for code, _ in COUNTRIES} == regions == {"GLOBAL", "KR"}


def test_parent_levels_step_down_one() -> None:
    assert [parent_level(level) for level in ghg_pool.LEVELS] == [None, "scope", "source_type", "activity"]
    with pytest.raises(ValueError):
        parent_level("planet")


def test_the_default_factor_unit_follows_the_ncv_toggle() -> None:
    assert default_factor_unit(True, "L") == "kg/TJ"
    assert default_factor_unit(False, "L") == "kg/L"
    assert default_factor_unit(False, "MWh") == "kg/MWh"


def test_a_factor_unit_is_mass_over_a_listed_unit() -> None:
    assert [is_factor_unit(text) for text in ("kg/TJ", "t/MWh", "g/Nm3")] == [True, True, True]
    assert [is_factor_unit(text) for text in ("kg", "kg/", "lb/TJ", "kg/bbl", "kg/TJ/L")] == [False] * 5


def test_the_module_imports_no_django() -> None:
    tree = ast.parse(Path(ghg_pool.__file__).read_text())
    roots = {
        alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert roots <= {"re", "collections", "dataclasses", "datetime", "decimal", "typing", "esgapi"}


# ── Decimal 글자 ─────────────────────────────────────────────────────


@pytest.mark.parametrize(("value", "text"), [
    (Decimal("1234.500000000000"), "1234.5"),
    (Decimal("1000.000000000000"), "1000"),
    (Decimal("0.010000000000"), "0.01"),
    (Decimal("1E+2"), "100"),
    (Decimal("1E-12"), "0.000000000001"),
    (Decimal("0.000000000000"), "0"),
    (Decimal("12"), "12"),
])  # fmt: skip
def test_decimal_text_has_no_exponent_and_no_trailing_zeros(value: Decimal, text: str) -> None:
    assert decimal_text(value) == text


@pytest.mark.parametrize(
    "text", ["", "1e3", "-1", "+1", "1.", ".5", "1,000", " 1", "1" * 19, "0." + "1" * 13, "NaN", "١٢", "１２", "1.٥"]
)
def test_parse_decimal_refuses_out_of_form(text: str) -> None:
    assert parse_decimal(text) is None


def test_parse_decimal_takes_the_column_range() -> None:
    assert parse_decimal("1" * 18 + "." + "1" * 12) == Decimal("1" * 18 + "." + "1" * 12)
    assert parse_decimal("0") == Decimal("0")


# ── 검사(S20 「확인」) ────────────────────────────────────────────────


def test_a_good_draft_passes_and_fills_the_defaults() -> None:
    result = check_factor(draft())
    assert isinstance(result, FactorValues)
    assert (result.name, result.emission_unit, result.factor_unit, result.ncv) == (
        "계수 가",
        ("mass", "tCO2-eq"),
        "kg/L",
        None,
    )
    assert [gas.gas for gas in result.gases] == list(GASES)  # 빠진 가스는 끈 줄로 채운다
    assert [gas.enabled for gas in result.gases] == [True] + [False] * 6
    assert result.gases[0].factor == Decimal("1.25")


def test_a_given_factor_unit_is_kept() -> None:
    result = check_factor(draft(factor_unit="t/L"))
    assert isinstance(result, FactorValues) and result.factor_unit == "t/L"
    assert errors_of(draft(factor_unit="kg")) == {"factorUnit": "<질량>/<단위> 꼴이다"}


def test_ncv_on_takes_value_and_unit_and_defaults_to_kg_per_tj() -> None:
    result = check_factor(draft(ncv_enabled=True, ncv="12.34", ncv_unit=("energy", "MJ")))
    assert isinstance(result, FactorValues)
    assert (result.ncv, result.ncv_unit, result.factor_unit) == (Decimal("12.34"), ("energy", "MJ"), "kg/TJ")


# ── 단위 종류 정합(K1b-2u M1·M3) ─────────────────────────────────────


def test_unit_kind_names_the_column_of_the_unit_list() -> None:
    assert [unit_kind(unit) for unit in ("kg", "kL", "GJ", "MWh", "tCO2-eq")] == [
        "mass",
        "volume",
        "energy",
        "electricity",
        None,
    ]
    assert all(unit_kind(unit) == kind for kind, units in UNITS.items() for unit in units)


@pytest.mark.parametrize("ncv_unit", [("volume", "L"), ("mass", "kg"), ("electricity", "kWh")])
def test_ncv_on_refuses_an_ncv_unit_outside_energy(ncv_unit: tuple[str, str]) -> None:
    made = draft(ncv_enabled=True, ncv="1.5", ncv_unit=ncv_unit)
    assert errors_of(made) == {"ncvUnit": "순발열량 단위는 에너지(energy) 단위다"}


@pytest.mark.parametrize("factor_unit", ["kg/L", "kg/kg", "kg/MWh"])
def test_ncv_on_refuses_a_factor_unit_not_per_energy(factor_unit: str) -> None:
    made = draft(ncv_enabled=True, ncv="1.5", ncv_unit=("energy", "GJ"), factor_unit=factor_unit)
    assert errors_of(made) == {"factorUnit": "순발열량을 켜면 분모가 에너지(energy) 단위다"}


@pytest.mark.parametrize(("input_unit", "factor_unit"), [
    (("volume", "L"), "kg/kg"),
    (("volume", "L"), "kg/TJ"),
    (("mass", "t"), "kg/Nm3"),
    (("electricity", "MWh"), "t/GJ"),
    (("energy", "GJ"), "kg/kWh"),
])  # fmt: skip
def test_ncv_off_refuses_a_factor_unit_of_another_kind(input_unit: tuple[str, str], factor_unit: str) -> None:
    made = draft(input_unit=input_unit, factor_unit=factor_unit)
    assert errors_of(made) == {"factorUnit": "순발열량을 끄면 분모가 투입량 기준단위와 같은 종류다"}


def test_matching_kinds_pass_with_a_prefix_difference() -> None:
    """같은 종류 안의 접두 차이(TJ ↔ GJ, kL ↔ L)는 거절하지 않는다 — 환산은 S12a."""
    on = check_factor(draft(ncv_enabled=True, ncv="2.5", ncv_unit=("energy", "TJ"), factor_unit="kg/GJ"))
    off = check_factor(draft(input_unit=("volume", "L"), factor_unit="kg/kL"))
    assert isinstance(on, FactorValues) and on.factor_unit == "kg/GJ"
    assert isinstance(off, FactorValues) and off.factor_unit == "kg/kL"


@pytest.mark.parametrize("ncv_enabled", [True, False])
@pytest.mark.parametrize("input_unit", [(kind, unit) for kind, units in UNITS.items() for unit in units])
def test_the_default_factor_unit_always_passes_the_kind_rule(ncv_enabled: bool, input_unit: tuple[str, str]) -> None:
    ncv = {"ncv": "1.5", "ncv_unit": ("energy", "MJ")} if ncv_enabled else {}
    result = check_factor(draft(input_unit=input_unit, ncv_enabled=ncv_enabled, **ncv))
    assert isinstance(result, FactorValues), result
    assert result.factor_unit == default_factor_unit(ncv_enabled, input_unit[1])


@pytest.mark.parametrize(("fields", "field"), [
    ({"name": "   "}, "name"),
    ({"name": "가" * 101}, "name"),
    ({"source": ""}, "source"),
    ({"source": "가" * 201}, "source"),
    ({"base_year": None}, "baseYear"),
    ({"base_year": 1989}, "baseYear"),
    ({"base_year": 2101}, "baseYear"),
    ({"tier": None}, "tier"),
    ({"tier": 4}, "tier"),
    ({"country_code": "JP"}, "countryCode"),
    ({"industry_code": "mining"}, "industryCode"),
    ({"input_unit": None}, "inputUnit"),
    ({"input_unit": ("mass", "L")}, "inputUnit"),
    ({"emission_unit": ("mass", "t")}, "emissionUnit"),
    ({"ncv_enabled": True}, "ncv"),
    ({"ncv_enabled": True, "ncv": "0", "ncv_unit": ("energy", "MJ")}, "ncv"),
    ({"ncv_enabled": True, "ncv": "1"}, "ncvUnit"),
    ({"ncv_enabled": True, "ncv": "1", "ncv_unit": ("energy", "kWh")}, "ncvUnit"),
    ({"ncv": "1"}, "ncv"),
    ({"ncv_unit": ("energy", "MJ")}, "ncv"),
    ({"ncv_enabled": True, "ncv": "1e3", "ncv_unit": ("energy", "MJ")}, "ncv"),
    ({"note": "가" * 1001}, "note"),
    ({"gases": ()}, "gases"),
    ({"gases": (GasDraft("CO2", enabled=False, factor="1", gwp="1"),)}, "gases"),
    ({"gases": (GasDraft("H2O", enabled=True, factor="1", gwp="1"),)}, "gases"),
    ({"gases": (GasDraft("CO2", True, "1", "1"), GasDraft("CO2", True, "1", "1"))}, "gases"),
    ({"gases": (GasDraft("CO2", enabled=True, factor=None, gwp="1"),)}, "gases.CO2.factor"),
    ({"gases": (GasDraft("CO2", enabled=True, factor="0", gwp="1"),)}, "gases.CO2.factor"),
    ({"gases": (GasDraft("CO2", enabled=True, factor="1", gwp=None),)}, "gases.CO2.gwp"),
    ({"gases": (GasDraft("CO2", enabled=True, factor="1", gwp="0"),)}, "gases.CO2.gwp"),
    ({"gases": (GasDraft("CO2", True, "1", "1"), GasDraft("CH4", False, "x", None))}, "gases.CH4.factor"),
])  # fmt: skip
def test_each_rule_refuses_its_field(fields: dict[str, object], field: str) -> None:
    assert field in errors_of(draft(**fields))


def test_name_and_note_limits_are_inclusive() -> None:
    assert isinstance(check_factor(draft(name="가" * 100, source="가" * 200, note="가" * 1000)), FactorValues)


def test_a_disabled_gas_keeps_its_values() -> None:
    gases = (GasDraft("CO2", True, "1", "1"), GasDraft("SF6", False, "3.5", "2"))
    result = check_factor(draft(gases=gases))
    assert isinstance(result, FactorValues)
    sf6 = result.gases[GASES.index("SF6")]
    assert (sf6.enabled, sf6.factor, sf6.gwp) == (False, Decimal("3.5"), Decimal("2"))


def test_the_options_body_lists_the_tables() -> None:
    body = ghg_pool.options()
    assert body["gases"] == list(GASES)
    assert body["defaults"] == {
        "emissionUnit": {"kind": "mass", "unit": "tCO2-eq"},
        "factorUnitWithNcv": "kg/TJ",
        "factorUnitWithoutNcv": "kg/<투입 단위>",
    }
