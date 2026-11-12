"""구매 전력: 계수 표의 전력배출계수 낱줄을 조립 조건대로 골라 엔진의 구매 에너지 계수 한 건으로 묶는다.

순수 함수다. 수치를 만들지 않는다(값은 전부 낱줄의 value_raw 에서 온다).

어느 계수를 쓸지(지침 별표 6 <표-69> 인지 온실가스종합정보센터(GIR) 공표 값인지, 어느 판·기간·발전단/소비단·
산정기준인지, 기체별 값인지 CO2 환산 값인지)는 전부 조립 조건이다. 기본값이 없고, 빠지면 조립하지 않는다
(고객 답 대기: MARC-ISSUE-20 의 15·17번).
지침 Tier 2 문장의 단서(「센터에서 확인하여 지침에 수록된 경우 그 값을 적용」)로 GIR 값이 표-69 를 대신하는지는
코드가 판단하지 않는다.

TS 원본의 `electricityComparison`(같은 사용량을 선택지마다 엔진으로 계산한 비교 표)은 옮기지 않았다:
계산 엔진(`inventory.engines.scope12.engine_1`)을 불러야 하는데 이 모듈은 엔진에 기대지 않는다.
"""

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

from esgapi.reference.calc.assemble import SOURCE_IDS
from esgapi.reference.calc.types import (
    Assembled,
    AssemblyMapping,
    AssemblyResult,
    FactorRecord,
    Failed,
    Json,
    Ok,
    fail,
    text_of,
)
from esgapi.reference.calc.value_raw import read_value_raw

# GIR 공표 판 → 계수 표의 출처 id.
GIR_EDITIONS: Final[dict[int, str]] = {2024: "gir-2024", 2025: "gir-2025"}

# 산정기준 입력 → 낱줄의 conditions.산정기준
# (esg-lab `py/factors/loaders/kr_gir.py` 의 BASIS_2006, BASIS_1996 과 같은 글자).
_METHODOLOGY: Final = {
    "ipcc_2006": "’06 IPCC 지침",
    "ipcc_1996_legacy": "’96 IPCC 지침 및 기존 에너지수급통계 (기존 공표 산정기준)",
}
_BOUNDARY: Final = {"generation": "발전단", "consumption": "소비단"}

# GIR 공표의 CO2 환산 계수에 들어 있는 GWP (공표문 주석의 글. 값이 아니라 어느 평가보고서인가).
# 2025 공고 주석 1)의 *: 「‘06 IPCC 지침 기준 계수는 IPCC 5차 평가보고서(AR5), ’96 IPCC 지침 기준 계수는
# IPCC 2차 평가보고서(AR2)의 GWP 적용」. 2024 공고 주석 1)은 「GWP 를 적용하여 합산한 계수」 라고만 쓴다.
_CO2E_GWP: Final[dict[str, dict[str, str]]] = {
    "gir-2025": {
        "ipcc_2006": "IPCC 5차 평가보고서(AR5) GWP (GIR 2025 공고 전력배출계수 표 주석 1)의 *)",
        "ipcc_1996_legacy": "IPCC 2차 평가보고서(AR2) GWP (GIR 2025 공고 전력배출계수 표 주석 1)의 *)",
    },
    "gir-2024": {
        "ipcc_2006": (
            "공표문에 적혀 있지 않다 (GIR 2024 공고 주석 1)은 "
            "「지구온난화지수(GWP)를 적용하여 합산한 계수」 라고만 쓴다)"
        ),
        "ipcc_1996_legacy": "공표문에 적혀 있지 않다",
    },
}

# 표-69 의 자리와 규칙(지침 원문 위치. 값이 아니다).
TABLE69: Final = {
    "sourceId": SOURCE_IDS["oxidation"],  # 별표 6 (kr-ets-byl06)
    "category": "외부에서 공급된 전기 사용",
    "rule": (
        "별표 6 「39. 외부에서 공급된 전기 사용」 5. 매개변수별 관리기준 ② 배출계수 Tier 2: 전력배출계수는 <표-69> 의 "
        "3개년도('14∼'16년) 평균값을 적용한다. 향후 한국전력거래소에서 제공하는 전력배출계수를 "
        "온실가스종합정보센터에서 확인하여 지침에 수록된 경우 그 값을 적용한다."
    ),
}

# 계수 표의 단위 분자 → (질량 단위, 기체). 표에 없는 표기는 실패다.
_MASS_UNITS: Final[dict[str, tuple[str, str]]] = {
    "tCO2": ("t", "CO2"),
    "kgCH4": ("kg", "CH4"),
    "kgN2O": ("kg", "N2O"),
    "t CO2": ("t", "CO2"),
    "kg CH4": ("kg", "CH4"),
    "kg N2O": ("kg", "N2O"),
    "t CO2-eq": ("t", "CO2e"),
    "t CO2eq": ("t", "CO2e"),
}

# 공표문이 적는 두 자리 연도(‘23년). 숫자로 바꾸지 않고 글자로 견준다. 따옴표는 표마다 다르다(‘ ’ ').
_SINGLE_YEAR = re.compile(r"[‘’']([0-9]{2})년")
_AVERAGE = re.compile(r"[‘’']([0-9]{2})-[‘’']([0-9]{2})년 평균")

_NOT_STATED: Final = ("not_stated",)


def _period_of(record: FactorRecord) -> tuple[str, ...] | None:
    """낱줄의 conditions.기간 → 기간. 기간 조건이 없으면 not_stated. 읽을 수 없으면 None."""
    raw = record.conditions.get("기간")
    if raw is None:
        return _NOT_STATED
    single = _SINGLE_YEAR.fullmatch(raw)
    if single is not None:
        return ("single_year", single.group(1))
    average = _AVERAGE.fullmatch(raw)
    if average is not None:
        return ("three_year_average", average.group(1), average.group(2))
    return None


def _yy(year: int) -> str:
    """입력 연도(2000~2099, 검사됨) → 두 자리 글자."""
    return str(year)[2:]


def _wanted_period(period: Mapping[str, Any]) -> tuple[str, ...]:
    if period["kind"] == "single_year":
        return ("single_year", _yy(period["year"]))
    if period["kind"] == "three_year_average":
        return ("three_year_average", _yy(period["from"]), _yy(period["to"]))
    return _NOT_STATED


def _period_text(period: Mapping[str, Any]) -> str:
    if period["kind"] == "single_year":
        return f"{period['year']}"
    if period["kind"] == "three_year_average":
        return f"{period['from']}-{period['to']}평균"
    return "기간표시없음"


def _is_year(value: object) -> bool:
    return type(value) is int and 2000 <= value <= 2099


def _compact(value: object) -> str:
    """TS 의 JSON.stringify 와 같은 표기(빈칸 없음, 한글 그대로)."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _check_request(raw: object) -> Ok[Json] | Failed:
    """조립 조건을 가려 받아 깨끗한 꼴로 되적는다. gir 은 표-69 일 때 키 자체가 없다."""
    if not isinstance(raw, Mapping):
        return fail("missing_input", field="request", reason="조립 조건이 없다")
    r = cast(Mapping[str, Any], raw)
    energy_type: object = r.get("energyType")
    if energy_type is None:
        return fail("missing_input", field="energyType", reason="에너지 종류가 없다 (기본값 없음)")
    if energy_type != "electricity":
        return fail(
            "invalid_input",
            field="energyType",
            value=text_of(energy_type),
            reason="구매 전력(electricity)만 조립한다. 열(스팀)은 범위 밖이다",
        )
    source: object = r.get("source")
    if source is None:
        return fail(
            "missing_input",
            field="source",
            reason="전력배출계수의 출처(지침 표-69 / GIR 공표)를 정하지 않았다. 기본값이 없다 (MARC-ISSUE-20 15·17번)",
        )
    if source not in ("guideline_table69", "gir_published"):
        return fail(
            "invalid_input", field="source", value=text_of(source), reason="guideline_table69 또는 gir_published"
        )
    gas_form: object = r.get("gasForm")
    if gas_form is None:
        return fail(
            "missing_input",
            field="gasForm",
            reason="기체별 값(per_gas)인지 CO2 환산 값(co2e)인지 정하지 않았다 (기본값 없음)",
        )
    if not isinstance(gas_form, str) or gas_form not in ("per_gas", "co2e"):
        return fail(
            "invalid_input",
            field="gasForm",
            value=_compact(gas_form),
            reason=(
                "per_gas(CO2·CH4·N2O 셋, GWP 는 계산할 때 곱한다) 또는 co2e(공표된 CO2 환산 값 하나, GWP 를 다시 "
                "곱하지 않는다) 중 하나다. 둘을 섞지 않는다"
            ),
        )
    gir: object = r.get("gir")
    if source == "guideline_table69":
        if gir is not None:
            return fail(
                "invalid_input",
                field="gir",
                value=_compact(gir),
                reason=(
                    "표-69 에는 공표 판·기간 선택·발전단/소비단·산정기준 구분이 없다. "
                    "gir 은 GIR 공표 값을 고를 때만 준다"
                ),
            )
        return Ok({"energyType": "electricity", "source": source, "gasForm": gas_form})
    if not isinstance(gir, Mapping):
        return fail(
            "missing_input", field="gir", reason="GIR 공표 값의 판·기간·발전단/소비단·산정기준이 없다 (기본값 없음)"
        )
    g = cast(Mapping[str, Any], gir)
    for name in ("edition", "period", "boundary", "methodology"):
        if g.get(name) is None:
            return fail("missing_input", field=f"gir.{name}", reason="GIR 공표 값을 고르는 조건이 빠졌다 (기본값 없음)")
    edition: object = g["edition"]
    if not _is_year(edition) or edition not in GIR_EDITIONS:
        return fail(
            "invalid_input",
            field="gir.edition",
            value=text_of(edition),
            reason=f"계수 표에 있는 공표 판은 {', '.join(str(e) for e in GIR_EDITIONS)} 이다",
        )
    boundary: object = g["boundary"]
    if not isinstance(boundary, str) or boundary not in _BOUNDARY:
        return fail(
            "invalid_input",
            field="gir.boundary",
            value=text_of(boundary),
            reason="generation(발전단) 또는 consumption(소비단)",
        )
    methodology: object = g["methodology"]
    if not isinstance(methodology, str) or methodology not in _METHODOLOGY:
        return fail(
            "invalid_input",
            field="gir.methodology",
            value=text_of(methodology),
            reason="ipcc_2006 또는 ipcc_1996_legacy",
        )
    given_period: object = g["period"]
    if not isinstance(given_period, Mapping):
        return fail("invalid_input", field="gir.period", value=text_of(given_period), reason="기간은 객체다")
    p = cast(Mapping[str, Any], given_period)
    period: Json
    if p.get("kind") == "single_year" and _is_year(p.get("year")):
        period = {"kind": "single_year", "year": p["year"]}
    elif (
        p.get("kind") == "three_year_average"
        and _is_year(p.get("from"))
        and _is_year(p.get("to"))
        and p["to"] - p["from"] == 2
    ):
        period = {"kind": "three_year_average", "from": p["from"], "to": p["to"]}
    elif p.get("kind") == "not_stated":
        period = {"kind": "not_stated"}
    else:
        return fail(
            "invalid_input",
            field="gir.period",
            value=_compact(dict(p)),
            reason=(
                "{kind: single_year, year} / {kind: three_year_average, from, to (3개년)} / {kind: not_stated} 중 "
                "하나다 (연도는 2000~2099 의 네 자리 정수)"
            ),
        )
    checked_gir: Json = {"edition": edition, "period": period, "boundary": boundary, "methodology": methodology}
    return Ok({"energyType": "electricity", "source": source, "gasForm": gas_form, "gir": checked_gir})


def assemble_purchased_electricity_factor(
    raw: object, records: Sequence[FactorRecord], mapping: AssemblyMapping
) -> AssemblyResult:
    """구매 전력 계수 한 건을 조립한다. 낱줄은 기체마다 정확히 하나여야 한다(없거나 둘이면 실패).

    request 는 JSON 을 푼 dict 다:
      energyType  "electricity" 만
      source      "guideline_table69" | "gir_published"
      gasForm     "per_gas"(CO2·CH4·N2O 의 질량 계수 셋) | "co2e"(공표된 CO2 환산 계수 하나)
      gir?        source 가 gir_published 일 때만, 그때는 전부 필요하다:
                  {edition: 2024|2025, period: {kind: single_year, year} | {kind: three_year_average, from, to}
                   | {kind: not_stated}, boundary: generation|consumption, methodology: ipcc_2006|ipcc_1996_legacy}
    엔진은 CO2e 계수에 GWP 를 곱하지 않는다. 없는 해의 값을 가까운 해로 대신하지 않는다.
    """
    checked = _check_request(raw)
    if isinstance(checked, Failed):
        return checked
    request = checked.value
    gir: Json | None = request.get("gir")
    gas_form: str = request["gasForm"]
    gases = ["CO2e"] if gas_form == "co2e" else ["CO2", "CH4", "N2O"]
    gas_basis = "co2e" if gas_form == "co2e" else "gas_mass"
    source_id: str = TABLE69["sourceId"] if gir is None else GIR_EDITIONS[gir["edition"]]

    # 후보: 그 출처의 전력배출계수 낱줄.
    # GIR 은 기간을 읽을 수 없는 낱줄이 있으면 고르기 전에 실패한다(추측해 읽지 않는다).
    # 표-69 는 한 행(3개년 평균 '14∼'16)뿐이라 기간을 고르지 않는다.
    pool = [
        r
        for r in records
        if r.source.id == source_id
        and r.record_type == "emission_factor"
        and (
            (len(r.category_path) > 0 and r.category_path[0] == TABLE69["category"])
            if gir is None
            else "전력배출계수" in r.category_path
        )
    ]
    if gir is not None:
        for r in pool:
            if _period_of(r) is None:
                return fail("record_condition_unknown", recordId=r.id, field="기간", value=r.conditions.get("기간", ""))

    parameters: list[Json] = []
    emission_factors: list[Json] = []
    for gas in gases:
        criteria: dict[str, str] = {
            "source": source_id,
            "record_type": "emission_factor",
            "gas": gas,
            "gas_basis": gas_basis,
        }
        if gir is not None:
            criteria["기준"] = _BOUNDARY[gir["boundary"]]
            criteria["산정기준"] = _METHODOLOGY[gir["methodology"]]
            criteria["기간"] = _period_text(gir["period"])
        found = [
            r
            for r in pool
            if r.gas == gas
            and r.gas_basis == gas_basis
            and (
                gir is None
                or (
                    r.conditions.get("기준") == _BOUNDARY[gir["boundary"]]
                    and r.conditions.get("산정기준") == _METHODOLOGY[gir["methodology"]]
                    and _period_of(r) == _wanted_period(gir["period"])
                )
            )
        ]
        if not found:
            return fail("record_not_found", parameter=gas, criteria=criteria)
        if len(found) > 1:
            return fail("record_ambiguous", parameter=gas, criteria=criteria, recordIds=[r.id for r in found])
        record = found[0]
        if gir is None and record.source.version != mapping.guideline.version:
            return fail(
                "guideline_version_mismatch",
                recordId=record.id,
                recordVersion=record.source.version,
                guidelineVersion=mapping.guideline.version,
            )
        if record.value_status != "ok" or record.value_raw is None:
            return fail("record_value_missing", parameter=gas, recordId=record.id, valueStatus=record.value_status)
        value = read_value_raw(record.value_raw)
        if value is None:
            return fail("invalid_value_raw", parameter=gas, recordId=record.id, valueRaw=record.value_raw)
        unit_text = f"{record.unit_numerator}/{record.unit_denominator}"
        unit = _MASS_UNITS.get(record.unit_numerator)
        if unit is None or unit[1] != gas or record.unit_denominator != "MWh":
            return fail("unit_notation_unknown", parameter=gas, recordId=record.id, unit=unit_text)
        emission_factors.append({"gas": gas, "value": value, "massUnit": unit[0]})
        parameters.append(
            {
                "gas": gas,
                "recordId": record.id,
                "sourceId": record.source.id,
                "sourceName": record.source.name,
                "sourceVersion": record.source.version,
                "url": record.source.url,
                "retrieved": record.source.retrieved,
                "fileSha256": record.source.file_sha256,
                "locator": record.source.locator,
                "valueRaw": record.value_raw,
                "value": value,
                "unit": unit_text,
                "conditions": dict(record.conditions),
            }
        )

    first = parameters[0]
    if gir is None:
        variant = f"{TABLE69['sourceId']}:표-69:2014-2016평균:{gas_form}"
    else:
        variant = (
            f"{source_id}:{_BOUNDARY[gir['boundary']]}:{_period_text(gir['period'])}:{gir['methodology']}:{gas_form}"
        )
    co2e_gwp: str | None = None
    if gas_form == "co2e" and gir is not None:
        co2e_gwp = _CO2E_GWP.get(source_id, {}).get(gir["methodology"], "공표문에서 확인하지 않았다")
    gwp_note = (
        ""
        if co2e_gwp is None
        else (
            f" 이 CO2 환산 계수에는 GWP 가 이미 들어 있다: {co2e_gwp}. "
            "엔진은 GWP 를 다시 곱하지 않으므로 계산에 고른 GWP 세트와 다를 수 있다."
        )
    )
    source_note = (
        "지침 별표 6 <표-69> 를 쓴 것은 조립 조건(입력)이다. 같은 문장의 단서(센터가 확인해 지침에 수록한 값)로 "
        "GIR 공표 값이 이를 대신하는지는 판단하지 않았다."
        if gir is None
        else "온실가스종합정보센터(GIR) 공표 값을 쓴 것은 조립 조건(입력)이다. 이 값이 지침 별표 6 Tier 2 문장의 "
        "「센터에서 확인하여 지침에 수록된 경우」 에 해당하는지는 판단하지 않았다."
    )
    cited = ", ".join(f"{p['gas']} {p['valueRaw']} {p['unit']} ← {p['recordId']}" for p in parameters)
    source: Json = {
        "kind": "cited",
        "title": f"{first['sourceName']} ({first['sourceVersion']}): {cited}",
        "url": mapping.guideline.url if gir is None else first["url"],
        "checkedOn": max(p["retrieved"] for p in parameters),
        "locator": " | ".join(f"{p['sourceId']} {p['locator']}" for p in parameters),
        "note": f"계수 조합기가 계수 표의 낱줄에서 조립했다. {source_note}{gwp_note}",
    }
    factor: Json = {
        "kind": "purchased_energy",
        "id": f"electricity:{variant}",
        "version": first["sourceVersion"],
        "source": source,
        "energyType": "electricity",
        "variant": variant,
    }
    if gir is not None and gir["period"]["kind"] == "single_year":
        factor["year"] = gir["period"]["year"]
    factor["perUnit"] = "MWh"
    factor["emissionFactors"] = emission_factors
    evidence: Json = {
        # 조립 조건을 그대로 되적는다. 출처 선택은 입력이다.
        "request": request,
        # co2e 계수에 이미 들어 있는 GWP(공표문이 적은 것). per_gas 이면 None(GWP 는 계산할 때 고른 세트로 곱한다).
        "co2eGwp": co2e_gwp,
        "sourceChoice": {"value": request["source"], "basis": "input", "note": source_note},
        "rule": (
            TABLE69["rule"]
            if gir is None
            else (
                f"{first['sourceName']} ({first['sourceVersion']}) 공표 표에서 입력한 "
                f"판·기간·{_BOUNDARY[gir['boundary']]}·산정기준의 낱줄"
            )
        ),
        "parameters": parameters,
    }
    return Ok(Assembled(factor=factor, evidence=evidence))


def electricity_options() -> list[Json]:
    """비교할 선택지 21개(고객 질문의 근거. 기대값이 아니다).

    표-69, GIR 2025 공표(단년 2023·3년 평균 2021~2023 × 발전단·소비단 × 산정기준 둘), GIR 2024 공표(기간 표시 없음 ×
    발전단·소비단). GIR 은 각각 기체별·CO2e.
    """

    def gir(edition: int, period: Json, boundary: str, methodology: str, gas_form: str) -> Json:
        return {
            "energyType": "electricity",
            "source": "gir_published",
            "gasForm": gas_form,
            "gir": {"edition": edition, "period": dict(period), "boundary": boundary, "methodology": methodology},
        }

    options: list[Json] = [{"energyType": "electricity", "source": "guideline_table69", "gasForm": "per_gas"}]
    periods: list[Json] = [
        {"kind": "single_year", "year": 2023},
        {"kind": "three_year_average", "from": 2021, "to": 2023},
    ]
    for methodology in ("ipcc_2006", "ipcc_1996_legacy"):
        for period in periods:
            for boundary in ("generation", "consumption"):
                for gas_form in ("per_gas", "co2e"):
                    options.append(gir(2025, period, boundary, methodology, gas_form))
    for boundary in ("generation", "consumption"):
        for gas_form in ("per_gas", "co2e"):
            options.append(gir(2024, {"kind": "not_stated"}, boundary, "ipcc_2006", gas_form))
    return options
