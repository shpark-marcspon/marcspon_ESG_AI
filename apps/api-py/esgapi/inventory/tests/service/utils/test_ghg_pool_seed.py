"""씨앗의 순수 조립(밴드 K1b-2a ④ — service/utils/ghg_pool.py 의 seed_factor)과 씨앗 파일의 꼴. 순수 층.

낱줄은 지어낸 것이다(id·값 모두 — 실제 계수 0). 환산 값·GWP 는 파일(unit-conversions.json·gwp-sets.json)에서 읽어 견준다
(시험에 그 숫자를 적지 않는다). 단위 규칙(감독 보정 B4): 분모가 다르면 건너뜀 · 질량 접두만 다르면 kg 로 ·
kgC·CO2e 안 씀.
"""

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from esgapi.inventory.service.utils.ghg_pool import (
    NAME_MAX,
    SOURCE_MAX,
    SeedFactor,
    SeedRecord,
    SeedSkip,
    seed_factor,
)

DATA = Path(__file__).resolve().parents[3] / "data"
CONVERSIONS = json.loads((DATA / "unit-conversions.json").read_text())["unitConversions"]
MASS_TO_KG = {row["from"]: row["factor"] for row in CONVERSIONS if row["to"] == "kg"}
GWP = {"CO2": "1", "CH4": "2", "N2O": "3"}  # 지어낸 세트(뻔한 가짜)


def record(record_id: str, value: str | None, numerator: str, denominator: str, gas: str) -> SeedRecord:
    return SeedRecord(id=record_id, value_raw=value, unit_numerator=numerator, unit_denominator=denominator, gas=gas)


FUEL = {
    "f:co2": record("f:co2", "1,234.5", "kgCO2", "TJ", "CO2"),
    "f:ch4": record("f:ch4", "2.5", "kgCH4", "TJ", "CH4"),
    "f:n2o": record("f:n2o", "0.25", "kgN2O", "TJ", "N2O"),
    "f:ncv": record("f:ncv", "12.34", "MJ", "N㎥", "none"),
    "e:co2": record("e:co2", "0.5", "t CO2", "MWh", "CO2"),
    "e:ch4": record("e:ch4", "0.125", "kg CH4", "MWh", "CH4"),
    "e:n2o": record("e:n2o", "0.75", "kg N2O", "MWh", "N2O"),
    "x:co2-per-kl": record("x:co2-per-kl", "1", "kgCO2", "kL", "CO2"),
    "x:carbon": record("x:carbon", "1", "kgC", "TJ", "C"),
    "x:co2e": record("x:co2e", "1", "t CO2-eq", "MWh", "CO2e"),
    "x:empty": record("x:empty", None, "kgCH4", "TJ", "CH4"),
}


def spec(**fields: Any) -> dict[str, Any]:
    return {
        "key": "k",
        "name": "계수 가",
        "source": "지어낸 출처",
        "baseYear": 2024,
        "tier": 2,
        "countryCode": "KR",
        "industryCode": "other",
        "gases": {"CO2": "f:co2", "CH4": "f:ch4", "N2O": "f:n2o"},
        **fields,
    }


def build(given: dict[str, Any], unit: tuple[str, str] = ("volume", "Nm3")) -> SeedFactor | SeedSkip:
    return seed_factor(given, leaf_key="leaf", input_unit=unit, records=FUEL, gwp=GWP, mass_to_kg=MASS_TO_KG)


def test_a_fuel_group_takes_value_raw_with_the_ncv_and_kg_per_tj() -> None:
    built = build(spec(ncv="f:ncv"))
    assert isinstance(built, SeedFactor)
    assert built.seed_key == "leaf#k"
    assert built.record_ids == ("f:co2", "f:ch4", "f:n2o", "f:ncv")
    draft = built.draft
    assert [(g.gas, g.enabled, g.factor, g.gwp) for g in draft.gases] == [
        ("CO2", True, "1234.5", "1"),  # 쉼표 걷음
        ("CH4", True, "2.5", "2"),
        ("N2O", True, "0.25", "3"),
    ]
    assert (draft.factor_unit, draft.ncv_enabled, draft.ncv, draft.ncv_unit) == (
        "kg/TJ",
        True,
        "12.34",
        ("energy", "MJ"),
    )
    assert draft.input_unit == ("volume", "Nm3")  # 낱줄 표기 N㎥ → Nm3(R6)


def test_a_ton_prefix_is_brought_to_kg_with_the_conversion_file() -> None:
    built = build(spec(gases={"CO2": "e:co2", "CH4": "e:ch4", "N2O": "e:n2o"}), unit=("electricity", "MWh"))
    assert isinstance(built, SeedFactor)
    co2 = built.draft.gases[0]
    assert Decimal(co2.factor or "") == Decimal("0.5") * Decimal(MASS_TO_KG["t"])  # 파일 값만 곱한다
    assert built.draft.gases[1].factor == "0.125"  # kg 는 그대로
    assert (built.draft.factor_unit, built.draft.ncv_enabled) == ("kg/MWh", False)


@pytest.mark.parametrize(("gases", "why"), [
    ({"CO2": "x:co2-per-kl", "CH4": "f:ch4", "N2O": "f:n2o"}, "분모가 다르다"),
    ({"CO2": "x:carbon", "CH4": "f:ch4", "N2O": "f:n2o"}, "꼴이 아니다"),  # kgC/TJ 는 쓰지 않는다
    ({"CO2": "x:co2e", "CH4": "e:ch4", "N2O": "e:n2o"}, "꼴이 아니다"),  # CO2e 는 쓰지 않는다
    ({"CO2": "f:co2", "CH4": "x:empty", "N2O": "f:n2o"}, "값이 없거나"),
    ({"CO2": "f:co2", "CH4": "no:such", "N2O": "f:n2o"}, "적재본에 없는 낱줄: no:such"),
    ({"CO2": "f:co2", "CH4": "f:ch4"}, "셋이 아니다"),
])  # fmt: skip
def test_a_group_out_of_rule_is_skipped_with_its_reason(gases: dict[str, str], why: str) -> None:
    built = build(spec(gases=gases))
    assert isinstance(built, SeedSkip) and why in built.reason, built


def test_an_ncv_whose_unit_does_not_match_the_input_is_skipped() -> None:
    built = build(spec(ncv="f:ncv"), unit=("mass", "kg"))
    assert isinstance(built, SeedSkip) and "투입 단위" in built.reason


def test_a_missing_gwp_gas_and_a_bad_draft_are_skipped() -> None:
    no_n2o = seed_factor(
        spec(), leaf_key="leaf", input_unit=("volume", "L"), records=FUEL, gwp={"CO2": "1", "CH4": "2"},
        mass_to_kg=MASS_TO_KG,
    )  # fmt: skip
    assert isinstance(no_n2o, SeedSkip) and "GWP" in no_n2o.reason
    bad = build(spec(baseYear=None))
    assert isinstance(bad, SeedSkip) and "baseYear" in bad.reason


def test_a_group_whose_denominator_kind_does_not_match_is_skipped_by_the_check() -> None:
    """K1b-2u: 씨앗도 check_factor 의 단위 종류 정합을 지난다 — 순발열량 없이 kg/TJ 를 부피 투입에 걸면 건너뜀."""
    built = build(spec(), unit=("volume", "Nm3"))
    assert isinstance(built, SeedSkip), built
    assert built.reason.startswith("검사에 걸렸다: ") and "factorUnit" in built.reason
    kept = build(spec(), unit=("energy", "GJ"))  # 같은 묶음을 에너지 투입에 걸면(분모 TJ — 같은 종류) 그대로
    assert isinstance(kept, SeedFactor) and kept.draft.factor_unit == "kg/TJ"


# ── 실제 씨앗 파일의 꼴(값 칸 0 — 수치를 지어내지 않는다) ─────────────


PLAN = json.loads((DATA / "ghg-pool-seed.json").read_text())


def leaves() -> list[tuple[str, dict[str, Any]]]:
    return [
        (f"{scope['key']}/{kind['key']}/{act['key']}/{leaf['code']}", leaf)
        for scope in PLAN["tree"]
        for kind in scope["children"]
        for act in kind["children"]
        for leaf in act["facilities"]
    ]


def test_the_seed_file_has_no_value_fields_and_only_ids_names_and_units() -> None:
    allowed_numbers = {"baseYear", "tier"}  # 판 글자에서 온 해·등급(baseYearBasis 에 근거 글자)
    numbers: set[str] = set()

    def walk(node: object, key: str | None = None) -> None:
        if isinstance(node, dict):
            for name, value in cast("dict[str, object]", node).items():
                assert name not in {"value", "value_raw", "factor", "gwp", "ncvValue"}, name
                walk(value, name)
        elif isinstance(node, list):
            for item in cast("list[object]", node):
                walk(item, key)
        elif isinstance(node, int | float) and not isinstance(node, bool):
            numbers.add(key or "")

    walk(PLAN)
    assert numbers == allowed_numbers


def test_the_seed_file_tree_and_groups_are_the_c0_draft() -> None:
    found = leaves()
    factors = [spec_ for _, leaf in found for spec_ in leaf["factors"]]
    # 분모: 연료 22 의 설비 잎 22 × 부문 4 + 전력 설비 잎 11(C0-seed · S12S1 나무)
    assert (len(found), len(factors)) == (23, 99)
    keys = [f"{key}#{spec_['key']}" for key, leaf in found for spec_ in leaf["factors"]]
    assert len(set(keys)) == len(keys)
    assert PLAN["sources"] == ["gir-2024", "gir-2025", "kr-ets-byl06", "kr-ets-byl10", "kr-ets-byl12"]
    for spec_ in factors:
        assert set(spec_["gases"]) == {"CO2", "CH4", "N2O"}
        ids = [*spec_["gases"].values(), *([spec_["ncv"]] if "ncv" in spec_ else [])]
        assert all(re.fullmatch(r"[a-z0-9-]+:[^\s]+", record_id) for record_id in ids), ids
        assert all(record_id.split(":")[0] in PLAN["sources"] for record_id in ids)
        assert len(spec_["name"]) <= NAME_MAX and len(spec_["source"]) <= SOURCE_MAX
        assert spec_["baseYearBasis"]
    # 기본(첫 줄): 고정연소는 제조업ㆍ건설업, 전력은 GIR 2025 ’06 · 2023 · 소비단(감독 답 4)
    for key, leaf in found:
        first = leaf["factors"][0]["key"]
        assert first == (
            "gir-2025:ipcc_2006:2023:consumption" if key.startswith("scope2") else "manufacturing_construction"
        )


# ── S12S1(결정 MARC-ENT-676): 연료 = 배출활동, 잎 = 설비 종류 · 옛 씨앗 열쇠는 지움 목록에만 ─────────
# 설비 이름은 제품 자료(시연 화면 글)라 시험에 적지 않는다 — 규칙만 문다.


def node_keys() -> set[str]:
    keys: set[str] = set()
    for scope in PLAN["tree"]:
        keys.add(scope["key"])
        for kind in scope["children"]:
            keys.add(f"{scope['key']}/{kind['key']}")
            keys |= {f"{scope['key']}/{kind['key']}/{act['key']}" for act in kind["children"]}
    return keys | {key for key, _ in leaves()}


def test_fuels_sit_on_the_activity_level_and_leaves_are_not_fuels() -> None:
    scope1 = next(scope for scope in PLAN["tree"] if scope["key"] == "scope1")
    # 이동연소·공정·탈루 설비 0(조립기가 고정연소만)
    assert [kind["name"] for kind in scope1["children"]] == ["고정연소"]
    fuels = [act["name"] for act in scope1["children"][0]["children"]]
    assert len(fuels) == len(set(fuels)) == 22  # 분모: 연료마다 활동 하나
    assert all(len(act["facilities"]) == 1 for act in scope1["children"][0]["children"])  # 연료마다 설비 잎 하나(Q2)
    codes = {leaf["code"] for _, leaf in leaves()}
    retired_codes = {key.rsplit("/", 1)[1] for key in PLAN["retired"] if key.count("/") == 3}
    assert codes & set(fuels) == set()  # 잎 코드 ∩ 연료 이름 = ∅
    assert codes & retired_codes == set()  # 새 설비 코드는 옛 씨앗 코드와 겹치지 않는다(지울 코드가 새 잎을 막지 않음)
    assert all(not any(ch.isdigit() for ch in code) for code in codes)  # 호기·대수는 세부시설명 몫 — 코드에 0
    assert len(codes) < len(leaves())  # 설비 종류 코드를 여러 연료가 같이 쓴다(코드 겹침 금지는 부모마다)


def test_the_retired_keys_are_the_old_seed_and_never_reused() -> None:
    retired = PLAN["retired"]
    assert len(retired) == len(set(retired)) == 26  # 분모: 옛 활동 3 + 옛 잎 23(BASE 씨앗 — section4 가 BASE 와 대조)
    assert sum(key.count("/") == 2 for key in retired) == 3
    assert sum(key.count("/") == 3 for key in retired) == 23
    assert set(retired) & node_keys() == set()  # R9: 지운 씨앗 열쇠 아래를 씨앗이 건너뛴다 — 새 열쇠로 다시 쓰지 않음
    kept = {key.rsplit("/", 1)[0] for key in retired if key.count("/") == 2}
    assert kept <= node_keys()  # 옛 활동의 부모(범위·유형)는 새 나무가 살린다
    leaf_parents = {key.rsplit("/", 1)[0] for key in retired if key.count("/") == 3}
    assert leaf_parents - set(retired) <= node_keys()  # 옛 잎의 부모는 지울 옛 활동이거나 살린 활동(전력)
