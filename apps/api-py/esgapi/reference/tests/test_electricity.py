"""구매 전력 조립. 순수 층: 패키지의 자료 사본(지침 560 + GIR 공표 40)에서 낱줄을 고른다.

TS 원본 `ts/factor-assembly/test/electricity.test.ts` 의 17개 가운데 **엔진으로 계산하는 부분을 뺀 것**이다:
  옮긴 것 14            지침 표-69 셋, GIR 공표 값 다섯, 입력 누락과 틀린 입력 여섯
  일부만 옮긴 것 1      「비교 표」: 선택지 21개가 다 조립되고 쓰인 낱줄이 43개라는 것까지. 엔진 결과(co2e)는 뺐다
  옮기지 않은 것 2      「엔진으로 계산」 둘(CO2e 계수에 GWP 를 곱하지 않는다 / 기체별 계수에 GWP 를 곱한다)
  줄 하나 뺀 것         첫 테스트의 `validateTables({factors: [factor]})`(엔진의 표 검사)
뺀 까닭: 계산 엔진(지금 inventory.engines)은 다른 밴드(PY4)가 같은 시각에 옮기고 있고, 이 모듈은 엔진에 기대지 않는다.
기대하는 낱줄 id 와 값 표기는 esg-lab 이 원문에서 2026-10-03 에 대조한 것이다: 지침 별표 6 PDF 274쪽 <표-69>,
GIR 2025 공고(HWPX) 전력배출계수 표와 주석 2) 표, GIR 2024 공고(PDF) 1쪽.
"""

from dataclasses import replace
from typing import Any

from esgapi.reference.calc import AssemblyResult, assemble_purchased_electricity_factor, electricity_options
from esgapi.reference.calc.types import Json
from esgapi.reference.tests.helpers import ALL_RECORDS, MAPPING, by_id, failure_of, subset, value_of

TABLE69: Json = {"energyType": "electricity", "source": "guideline_table69", "gasForm": "per_gas"}


def gir(gas_form: str = "per_gas", **over: Any) -> Json:
    base: Json = {
        "edition": 2025,
        "period": {"kind": "single_year", "year": 2023},
        "boundary": "consumption",
        "methodology": "ipcc_2006",
    }
    return {"energyType": "electricity", "source": "gir_published", "gasForm": gas_form, "gir": {**base, **over}}


def assemble(request: object) -> AssemblyResult:
    return assemble_purchased_electricity_factor(request, ALL_RECORDS, MAPPING)


def ids(result: AssemblyResult) -> list[str]:
    return [p["recordId"] for p in value_of(result).evidence["parameters"]]


AVERAGE: Json = {"kind": "three_year_average", "from": 2021, "to": 2023}
NOT_STATED: Json = {"kind": "not_stated"}

# 실패의 reason 글자(운영 코드 electricity.py 의 글 그대로. 실패는 칸 전부를 == 로 견준다).
PERIOD_REASON = (
    "{kind: single_year, year} / {kind: three_year_average, from, to (3개년)} / {kind: not_stated} 중 하나다 "
    "(연도는 2000~2099 의 네 자리 정수)"
)
GAS_FORM_REASON = (
    "per_gas(CO2·CH4·N2O 셋, GWP 는 계산할 때 곱한다) 또는 co2e(공표된 CO2 환산 값 하나, GWP 를 다시 곱하지 "
    "않는다) 중 하나다. 둘을 섞지 않는다"
)
EDITION_REASON = "계수 표에 있는 공표 판은 2024, 2025 이다"
BOUNDARY_REASON = "generation(발전단) 또는 consumption(소비단)"


def failed(request: object) -> Json:
    return failure_of(assemble(request))


def not_found(gas: str, period: str, *, source: str = "gir-2025", methodology: str = "’06 IPCC 지침") -> Json:
    """GIR 공표 값의 record_not_found: criteria 에 고른 조건(기준·산정기준·기간의 글자)이 전부 실린다."""
    return {
        "kind": "record_not_found",
        "parameter": gas,
        "criteria": {
            "source": source,
            "record_type": "emission_factor",
            "gas": gas,
            "gas_basis": "co2e" if gas == "CO2e" else "gas_mass",
            "기준": "소비단",
            "산정기준": methodology,
            "기간": period,
        },
    }


def bad_period(value: str) -> Json:
    return {"kind": "invalid_input", "field": "gir.period", "value": value, "reason": PERIOD_REASON}


# ── 지침 별표 6 <표-69> ────────────────────────────────────────────────


def test_table_69_bundles_three_rows_and_records_that_the_source_was_an_input() -> None:
    done = value_of(assemble(TABLE69))
    assert subset(
        done.factor,
        {
            "kind": "purchased_energy",
            "energyType": "electricity",
            "perUnit": "MWh",
            "version": "환경부고시 제2025-64호 (2025-04-11 시행)",
            "emissionFactors": [
                {"gas": "CO2", "value": "0.4567", "massUnit": "t"},
                {"gas": "CH4", "value": "0.0036", "massUnit": "kg"},
                {"gas": "N2O", "value": "0.0085", "massUnit": "kg"},
            ],
        },
    )
    assert "year" not in done.factor
    assert [[p["recordId"], p["valueRaw"], p["unit"]] for p in done.evidence["parameters"]] == [
        ["kr-ets-byl06:elec:t69:CO2", "0.4567", "tCO2/MWh"],
        ["kr-ets-byl06:elec:t69:CH4", "0.0036", "kgCH4/MWh"],
        ["kr-ets-byl06:elec:t69:N2O", "0.0085", "kgN2O/MWh"],
    ]
    assert subset(done.evidence["sourceChoice"], {"value": "guideline_table69", "basis": "input"})
    assert "<표-69>" in done.evidence["rule"]
    assert done.factor["source"]["kind"] == "cited"
    assert "조립 조건(입력)" in done.factor["source"]["note"]


def test_table_69_has_no_co2e_value() -> None:
    """표-69 에는 CO2 환산 값이 없어 co2e 를 고르면 실패한다(기체별 값을 더해 만들지 않는다).

    표-69 의 criteria 에는 GIR 의 조건(기준·산정기준·기간)이 없다.
    """
    assert failed({**TABLE69, "gasForm": "co2e"}) == {
        "kind": "record_not_found",
        "parameter": "CO2e",
        "criteria": {"source": "kr-ets-byl06", "record_type": "emission_factor", "gas": "CO2e", "gas_basis": "co2e"},
    }


def test_table_69_takes_no_edition_period_or_boundary() -> None:
    """받은 gir 은 JSON 표기 그대로(빈칸 없음, 한글 그대로) value 에 실린다."""
    reason = "표-69 에는 공표 판·기간 선택·발전단/소비단·산정기준 구분이 없다. gir 은 GIR 공표 값을 고를 때만 준다"
    assert failed({**TABLE69, "gir": {"edition": 2025}}) == {
        "kind": "invalid_input",
        "field": "gir",
        "value": '{"edition":2025}',
        "reason": reason,
    }
    assert failed({**TABLE69, "gir": {"edition": 2025, "메모": "가"}}) == {
        "kind": "invalid_input",
        "field": "gir",
        "value": '{"edition":2025,"메모":"가"}',
        "reason": reason,
    }


# ── GIR 공표 값 ────────────────────────────────────────────────────────


def test_gir_2025_single_year_consumption_per_gas_and_co2e() -> None:
    """2025 공표, 2023년 단년, 소비단, ’06 IPCC 의 기체별 값과 CO2 환산 값."""
    assert ids(assemble(gir())) == ["gir-2025:main:r7", "gir-2025:main:r8", "gir-2025:main:r9"]
    co2e = value_of(assemble(gir("co2e")))
    assert co2e.factor["emissionFactors"] == [{"gas": "CO2e", "value": "0.4173", "massUnit": "t"}]
    assert co2e.factor["year"] == 2023
    assert subset(
        co2e.evidence["parameters"][0], {"recordId": "gir-2025:main:r6", "valueRaw": "0.4173", "unit": "t CO2-eq/MWh"}
    )
    # CO2e 계수에 이미 든 GWP 가 근거와 출처에 남는다(’06 기준은 AR5, ’96 기준은 AR2, 2024 공고는 적혀 있지 않다)
    assert "AR5" in co2e.evidence["co2eGwp"]
    assert "GWP 가 이미 들어 있다" in co2e.factor["source"]["note"]
    assert "AR2" in value_of(assemble(gir("co2e", methodology="ipcc_1996_legacy"))).evidence["co2eGwp"]
    assert "적혀 있지 않다" in value_of(assemble(gir("co2e", edition=2024, period=NOT_STATED))).evidence["co2eGwp"]
    assert value_of(assemble(gir())).evidence["co2eGwp"] is None
    assert value_of(assemble(TABLE69)).evidence["co2eGwp"] is None


def test_generation_boundary_and_three_year_average_are_other_rows() -> None:
    assert ids(assemble(gir(boundary="generation"))) == ["gir-2025:main:r3", "gir-2025:main:r4", "gir-2025:main:r5"]
    assert ids(assemble(gir("co2e", period=AVERAGE))) == ["gir-2025:main:r14"]
    assert "year" not in value_of(assemble(gir(period=AVERAGE))).factor


def test_gir_2025_legacy_methodology_rows_come_from_the_footnote_table() -> None:
    """2025 공표의 기존 산정기준(’96 IPCC) 값은 주석 2) 표의 낱줄이다."""
    legacy = "ipcc_1996_legacy"
    assert ids(assemble(gir(methodology=legacy))) == ["gir-2025:alt:r3c3", "gir-2025:alt:r3c4", "gir-2025:alt:r3c5"]
    # 주석 표는 3년 평균의 따옴표가 본표와 다르다(‘21-’23 / ‘21-‘23). 둘 다 같은 기간으로 읽는다.
    assert ids(assemble(gir("co2e", methodology=legacy, period=AVERAGE))) == ["gir-2025:alt:r5c2"]


def test_gir_2024_has_no_period_in_its_table() -> None:
    """2024 공표는 표에 기간이 없어 not_stated 로만 고른다."""
    assert ids(assemble(gir("co2e", edition=2024, period=NOT_STATED, boundary="generation"))) == ["gir-2024:main:r2"]
    assert failed(gir(edition=2024, period={"kind": "single_year", "year": 2022})) == not_found(
        "CO2", "2022", source="gir-2024"
    )
    assert failed(gir(period=NOT_STATED)) == not_found("CO2", "기간표시없음")
    # 2024 공표의 기존 산정기준 표는 적재되지 않았다(단위가 표 안에 없다. esg-lab 밴드 C)
    legacy = "’96 IPCC 지침 및 기존 에너지수급통계 (기존 공표 산정기준)"
    assert failed(gir(edition=2024, period=NOT_STATED, methodology="ipcc_1996_legacy")) == not_found(
        "CO2", "기간표시없음", source="gir-2024", methodology=legacy
    )


def test_a_missing_year_is_not_replaced_by_a_near_one() -> None:
    """없는 해의 값은 가까운 해로 대신하지 않는다. criteria 의 기간은 기간 셋마다 그 글자다."""
    assert failed(gir(period={"kind": "single_year", "year": 2024})) == not_found("CO2", "2024")
    assert failed(gir(edition=2024, period=AVERAGE)) == not_found("CO2", "2021-2023평균", source="gir-2024")
    assert failed(gir("co2e", period=NOT_STATED)) == not_found("CO2e", "기간표시없음")


# ── 입력 누락과 틀린 입력 (기본값이 없다) ──────────────────────────────


def test_a_missing_source_is_not_filled_in() -> None:
    """출처가 빠지면 표-69 로도 GIR 로도 채우지 않는다."""
    assert failed({"energyType": "electricity", "gasForm": "per_gas"}) == {
        "kind": "missing_input",
        "field": "source",
        "reason": "전력배출계수의 출처(지침 표-69 / GIR 공표)를 정하지 않았다. 기본값이 없다 (MARC-ISSUE-20 15·17번)",
    }


def test_each_missing_condition_is_named() -> None:
    """기체별·CO2e 구분, GIR 의 판·기간·발전단/소비단·산정기준이 하나라도 빠지면 실패한다."""
    assert failed({"energyType": "electricity", "source": "guideline_table69"}) == {
        "kind": "missing_input",
        "field": "gasForm",
        "reason": "기체별 값(per_gas)인지 CO2 환산 값(co2e)인지 정하지 않았다 (기본값 없음)",
    }
    assert failed({"energyType": "electricity", "source": "gir_published", "gasForm": "co2e"}) == {
        "kind": "missing_input",
        "field": "gir",
        "reason": "GIR 공표 값의 판·기간·발전단/소비단·산정기준이 없다 (기본값 없음)",
    }
    for field in ["edition", "period", "boundary", "methodology"]:
        request = gir()
        partial = {key: value for key, value in request["gir"].items() if key != field}
        assert failed({**request, "gir": partial}) == {
            "kind": "missing_input",
            "field": f"gir.{field}",
            "reason": "GIR 공표 값을 고르는 조건이 빠졌다 (기본값 없음)",
        }
    assert failed({"source": "guideline_table69", "gasForm": "per_gas"}) == {
        "kind": "missing_input",
        "field": "energyType",
        "reason": "에너지 종류가 없다 (기본값 없음)",
    }


def test_a_request_that_is_not_an_object_is_missing() -> None:
    not_objects: list[object] = [None, [], "electricity"]
    for request in not_objects:
        assert failed(request) == {"kind": "missing_input", "field": "request", "reason": "조립 조건이 없다"}


def test_wrong_values() -> None:
    assert failed({**TABLE69, "energyType": "heat"}) == {
        "kind": "invalid_input",
        "field": "energyType",
        "value": "heat",
        "reason": "구매 전력(electricity)만 조립한다. 열(스팀)은 범위 밖이다",
    }
    assert failed({**TABLE69, "source": "kepco"}) == {
        "kind": "invalid_input",
        "field": "source",
        "value": "kepco",
        "reason": "guideline_table69 또는 gir_published",
    }
    assert failed(gir(edition=2023)) == {
        "kind": "invalid_input",
        "field": "gir.edition",
        "value": "2023",
        "reason": EDITION_REASON,
    }
    assert failed(gir(period={"kind": "three_year_average", "from": 2022, "to": 2023})) == bad_period(
        '{"kind":"three_year_average","from":2022,"to":2023}'
    )
    assert failed(gir(boundary="both")) == {
        "kind": "invalid_input",
        "field": "gir.boundary",
        "value": "both",
        "reason": BOUNDARY_REASON,
    }
    assert failed(gir(methodology="ipcc_2019")) == {
        "kind": "invalid_input",
        "field": "gir.methodology",
        "value": "ipcc_2019",
        "reason": "ipcc_2006 또는 ipcc_1996_legacy",
    }
    assert failed(gir(period="2023")) == {
        "kind": "invalid_input",
        "field": "gir.period",
        "value": "2023",
        "reason": "기간은 객체다",
    }
    # 파이썬에서만 생기는 구멍: True 는 1 과 같고, 목록은 dict 의 키가 못 된다
    assert failed(gir(edition=True)) == {
        "kind": "invalid_input",
        "field": "gir.edition",
        "value": "true",
        "reason": EDITION_REASON,
    }
    assert failed(gir(boundary=["generation"])) == {
        "kind": "invalid_input",
        "field": "gir.boundary",
        "value": '["generation"]',
        "reason": BOUNDARY_REASON,
    }


def test_years_outside_2000_to_2099_are_wrong_and_the_edges_pass_the_check() -> None:
    """연도는 2000~2099 의 int 다(bool 은 아니다). 끝의 해(2000·2099)는 검사를 지나 낱줄이 없어 실패한다."""
    for year in [1999, 2100]:
        assert failed(gir(period={"kind": "single_year", "year": year})) == bad_period(
            f'{{"kind":"single_year","year":{year}}}'
        )
    assert failed(gir(period={"kind": "single_year", "year": True})) == bad_period('{"kind":"single_year","year":true}')
    for year in [2000, 2099]:
        assert failed(gir(period={"kind": "single_year", "year": year})) == not_found("CO2", str(year))
    # 3개년 평균: 두 해의 차가 2 가 아니거나, 앞·뒤 해가 범위 밖
    for start, end in [(2021, 2022), (1999, 2001), (2098, 2100)]:
        period = {"kind": "three_year_average", "from": start, "to": end}
        assert failed(gir(period=period)) == bad_period(f'{{"kind":"three_year_average","from":{start},"to":{end}}}')
    # 모르는 kind 의 value 는 받은 객체의 JSON 표기 그대로(빈칸 없음, 한글 그대로)
    assert failed(gir(period={"kind": "연평균", "메모": ["가", 1]})) == bad_period('{"kind":"연평균","메모":["가",1]}')


def test_mixing_co2e_and_per_gas_fails() -> None:
    """value 는 받은 값의 JSON 표기다(글자도 따옴표째, 빈칸 없음, 한글 그대로)."""
    for gas_form, value in [
        (["co2e", "per_gas"], '["co2e","per_gas"]'),
        ("mixed", '"mixed"'),
        ("CO2e+CH4", '"CO2e+CH4"'),
        ("", '""'),
        ({"형태": "기체별"}, '{"형태":"기체별"}'),
    ]:
        assert failed({**gir(), "gasForm": gas_form}) == {
            "kind": "invalid_input",
            "field": "gasForm",
            "value": value,
            "reason": GAS_FORM_REASON,
        }


def test_two_rows_for_the_same_condition_are_ambiguous() -> None:
    """계수 표에 같은 조건의 낱줄이 둘이면 앞의 것을 집지 않는다."""
    twin = replace(by_id("gir-2025:main:r6"), id="gir-2025:synthetic-dup", synthetic=True)
    result = assemble_purchased_electricity_factor(gir("co2e"), [*ALL_RECORDS, twin], MAPPING)
    assert failure_of(result) == {
        **not_found("CO2e", "2023"),
        "kind": "record_ambiguous",
        "recordIds": ["gir-2025:main:r6", "gir-2025:synthetic-dup"],
    }


def test_an_unreadable_period_fails_before_any_row_is_picked() -> None:
    """기간 표기를 읽을 수 없는 GIR 낱줄이 있으면 고르기 전에 실패한다."""
    base = by_id("gir-2025:main:r6")
    odd = replace(
        base, id="gir-2025:synthetic-odd", conditions={**base.conditions, "기간": "2023 상반기"}, synthetic=True
    )
    result = assemble_purchased_electricity_factor(gir("co2e"), [*ALL_RECORDS, odd], MAPPING)
    assert failure_of(result) == {
        "kind": "record_condition_unknown",
        "recordId": "gir-2025:synthetic-odd",
        "field": "기간",
        "value": "2023 상반기",
    }


# ── 비교할 선택지 (기대값이 아니다) ────────────────────────────────────


def test_all_21_options_assemble_from_43_distinct_rows() -> None:
    """선택지 21개가 다 조립된다. 쓰인 낱줄은 표-69 의 3 + GIR 2025 의 32 + GIR 2024 의 8 = 43 이다.

    TS 의 같은 테스트는 여기에 더해 엔진으로 계산한 값(표-69 줄이 검산 H06 의 기대값과 같다)까지 본다. 그 부분은 뺐다.
    """
    options = electricity_options()
    assert len(options) == 21
    results = [assemble(option) for option in options]
    assert all(result.ok for result in results)
    assert value_of(results[0]).factor["id"] == "electricity:kr-ets-byl06:표-69:2014-2016평균:per_gas"
    used = {record_id for result in results for record_id in ids(result)}
    assert len(used) == 3 + 32 + 8
    # 분모: 사본의 GIR 낱줄은 40 이고 전부 쓰였다. 지침 쪽 전력 낱줄은 표-69 의 셋뿐이다.
    assert len([r for r in ALL_RECORDS if r.source.id.startswith("gir-")]) == 40
    assert len({value_of(result).factor["id"] for result in results}) == 21
