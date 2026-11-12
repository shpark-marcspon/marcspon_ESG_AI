"""씨앗 사본의 낱줄 id = 조립기 다시 뽑음(밴드 K1b-2b ⑤ — R7, sid:MARC-ISSUE-430). 순수(DB 0).

inventory/data/ghg-pool-seed.json 의 낱줄 id 는 reference 조립기(assemble_combustion_factor·
assemble_purchased_electricity_factor)를 적재본(reference/data/factors.kr.jsonl·mappings.kr-ets.json)에 돌려 뽑은
사본이다(K1b-2a ④ — 뽑은 스크립트는 저장소 밖에 있었다). 이 시험이 같은 꼴로 다시 뽑아 묶음 수·id 전부가 같고 남는 것이
0 임을 문다 — 적재본이나 조립기가 바뀌면 씨앗을 다시 뽑으라고 빨개진다. 숫자 값은 보지 않는다(id 글자만).

  고정연소   국가 고유 순발열량이 있는 연료 × 부문 넷, Tier 2·발전 아님 → (연료, 부문, CO2·CH4·N2O·순발열량 낱줄 id)
  구매 전력  electricity_options 의 기체별(per_gas) 선택지 → (CO2·CH4·N2O 낱줄 id)
  빠진 연료  어느 부문에서도 조립이 실패한 연료 — 씨앗 $comment·data/README.md 의 일곱(R8)
"""

import json
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from esgapi.reference.calc import AssemblyMapping, FactorRecord, mapping_from_json
from esgapi.reference.calc.assemble import assemble_combustion_factor, national_calorific_fuels
from esgapi.reference.calc.electricity import assemble_purchased_electricity_factor, electricity_options
from esgapi.reference.calc.types import Failed
from esgapi.reference.jsonl import read_records, to_calc

SEED = Path(__file__).resolve().parents[3] / "data" / "ghg-pool-seed.json"
REFERENCE = resources.files("esgapi.reference.data")
TIER2 = {"kind": "explicit", "calorific": 2, "co2": 2, "oxidation": 2}
GASES = ("CO2", "CH4", "N2O")
MISSING = {"원유", "코크스", "부생연료유1호", "부생연료유2호", "도시가스(LPG)", "전기(발전기준)", "전기(소비기준)"}
WRITTEN = (  # R8 의 글(씨앗 $comment 끝·data/README.md 표 아래 — 같은 글)
    "조립기가 실패해 넣지 않은 연료 7 — 원유·코크스(CO2 국가 고유 낱줄 없음), 부생연료유1호·2호·도시가스(LPG)(별표 10 "
    "이름 대응 없음), 전기(발전기준)·전기(소비기준)(연소 아님 — 구매 전력 잎)"
)

Combustion = tuple[str, str, str, str, str, str]  # (연료, 부문, CO2, CH4, N2O, 순발열량)
Electricity = tuple[str, str, str]  # (CO2, CH4, N2O)


@pytest.fixture(scope="module")
def reference() -> tuple[list[FactorRecord], AssemblyMapping, list[str]]:
    with REFERENCE.joinpath("factors.kr.jsonl").open(encoding="utf-8") as lines:
        records = [to_calc(record) for _, record in read_records(lines)]
    body = json.loads(REFERENCE.joinpath("mappings.kr-ets.json").read_text(encoding="utf-8"))
    return records, mapping_from_json(body), [sector["key"] for sector in body["sectors"]]


def drawn(
    records: list[FactorRecord], mapping: AssemblyMapping, sectors: list[str]
) -> tuple[set[Combustion], set[Electricity], set[str]]:
    combustion: set[Combustion] = set()
    assembled: set[str] = set()
    fuels = national_calorific_fuels(records)
    for fuel in fuels:
        for sector in sectors:
            request = {
                "fuel": fuel,
                "combustionType": "stationary",
                "industry": {"sector": sector},
                "tiers": TIER2,
                "powerGeneration": False,
            }
            result = assemble_combustion_factor(request, records, mapping)
            if isinstance(result, Failed):
                continue
            ids = {p["parameter"]: p["recordId"] for p in result.value.evidence["parameters"]}
            combustion.add((fuel, sector, ids["CO2"], ids["CH4"], ids["N2O"], ids["calorific"]))
            assembled.add(fuel)
    electricity: set[Electricity] = set()
    for option in electricity_options():
        if option["gasForm"] != "per_gas":
            continue
        found = assemble_purchased_electricity_factor(option, records, mapping)
        assert not isinstance(found, Failed), option
        by_gas = {p["gas"]: p["recordId"] for p in found.value.evidence["parameters"]}
        electricity.add((by_gas["CO2"], by_gas["CH4"], by_gas["N2O"]))
    return combustion, electricity, set(fuels) - assembled


def seeded() -> tuple[set[Combustion], set[Electricity], int]:
    tree: list[dict[str, Any]] = json.loads(SEED.read_text(encoding="utf-8"))["tree"]
    combustion: set[Combustion] = set()
    electricity: set[Electricity] = set()
    groups = 0
    for scope in tree:
        for kind in scope["children"]:
            for activity in kind["children"]:
                for leaf in activity["facilities"]:
                    for factor in leaf["factors"]:
                        groups += 1
                        gases = tuple(factor["gases"][gas] for gas in GASES)
                        if "ncv" in factor:  # S12S1(MARC-ENT-676): 연료는 배출활동 이름 — 잎 코드는 설비 종류
                            combustion.add((activity["name"], factor["key"], *gases, factor["ncv"]))
                        else:
                            electricity.add((gases[0], gases[1], gases[2]))
    return combustion, electricity, groups


def test_the_seed_ids_are_what_the_assemblers_draw(
    reference: tuple[list[FactorRecord], AssemblyMapping, list[str]],
) -> None:
    combustion, electricity, missing = drawn(*reference)
    seed_combustion, seed_electricity, groups = seeded()
    assert len(combustion) > 0 and len(electricity) == 11  # 분모: 정말 뽑았다(기체별 선택지 11)
    assert seed_combustion == combustion  # 묶음·id 전부 — 남는 것 0
    assert seed_electricity == electricity
    assert groups == len(combustion) + len(electricity)  # 씨앗에 겹친 묶음 0
    assert missing == MISSING  # R8 의 일곱 — 어느 부문에서도 조립이 실패한 연료


def test_the_missing_fuels_are_written_down() -> None:
    """R8: 빠진 연료 일곱과 까닭이 씨앗 $comment 와 data/README.md 에 있다(수치 0)."""
    comment = json.loads(SEED.read_text(encoding="utf-8"))["$comment"]
    readme = (SEED.parent / "README.md").read_text(encoding="utf-8")
    assert WRITTEN in comment
    assert WRITTEN.replace("조립기가 실패해 넣지 않은 연료 7 — ", "") in readme
