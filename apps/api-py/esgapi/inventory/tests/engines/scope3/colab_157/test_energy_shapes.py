"""T6 결과 꼴의 새 줄(`ColabEnergyRowJson` — 일곱 결과 시트 C3·C8·C11·C12·C13·C14·C15, S3C-c1a 에서 세움).

손으로 지은 표본 일곱(kind 마다 하나)이 계약을 엄격히 지나고(판별 칸으로 새 갈래에 닿음) 뼈대의 키 차례도 맞는다.
c1b 의 넷(product_use·product_eol·franchise·investment)도 여기 표본이 있다 — c1b 가 계약 0줄로 끝날 수 있음의 증거다
(칸 자리는 밴드 보고 「계약 표」). 수는 지어낸 `9.` 꼴, 이름은 `가상…`.
"""

from typing import Any, get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from esgapi.inventory.contracts import shapes
from esgapi.inventory.tests.contracts.test_shapes import Arr, Obj, Union, fits, tag_of, typed

type Row = dict[str, Any]


def amount(value: str | None, unit: str, base: str | None, base_unit: str, note: str | None = None) -> Row:
    return {"value": value, "unit": unit, "baseValue": base, "baseUnit": base_unit, "note": note}


def factor(sheet: str, title: str | None, value: str | None, unit: str) -> Row:
    return {"sheet": sheet, "title": title, "value": value, "unit": unit, "column": None, "code": None}


def energy_row(kind: str, **overrides: object) -> Row:
    row: Row = {
        "rowId": "가상시트!4",
        "kind": kind,
        "month": None,
        "activity": amount("99.0", "가상와트", "980.1", "kWh", "가상와트→kWh (AI 판단: ×9.9)"),
        "factor": factor("에너지", "전력", "0.0941", "kWh"),
        "co2e": "0.09222741",
        "unit": "tCO2eq",
        "formula": "",
        "match": None,
        "allocation": None,
        "biogenic": None,
        "product": None,
        "investment": None,
        "origin": "ai",
        "originSteps": [
            {"step": "unit", "origin": "ai", "via": "ai"},
            {"step": "factor", "origin": "rule", "via": "exact_raw"},
        ],
        "missing": [],
    }
    row.update(overrides)
    return row


SAMPLES: dict[str, Row] = {
    "fuel_energy": energy_row("fuel_energy", factor=factor("에너지_C3", "전력", "0.0951", "kWh")),
    "leased_asset": energy_row(
        "leased_asset",
        match={"type": "exact_raw", "score": "1.0"},
        allocation={"method": "면적배분", "buildingTotal": "18300.0", "areaRatio": "0.1", "personRatio": None},
    ),
    "leased_out_asset": energy_row(
        "leased_out_asset",
        match={"type": "legacy_lookup", "score": None},
        allocation={"method": "인원배분", "buildingTotal": "1930.0", "areaRatio": None, "personRatio": "0.1"},
    ),
    "product_use": energy_row(
        "product_use",
        match={"type": "unit_priority_alias", "score": "0.95"},
        product={"years": "8.0", "totalUsage": "69888.0"},
    ),
    "product_eol": energy_row(
        "product_eol",
        activity=amount("9100.0", "kg", "8190.0", "kg"),
        factor={
            "sheet": "폐기물_C12",
            "title": "가상 폐지 묶음",
            "value": "0.961",
            "unit": "kgCO2eq/kg",
            "column": None,
            "code": "91-02-01",
        },
        biogenic={"fossilCo2e": "0.09", "biogenicCo2e": "0.9", "fcf": "0.01", "note": "폐지류"},
        originSteps=[{"step": "factor", "origin": "rule", "via": "code"}],
        origin="rule",
    ),
    "franchise": energy_row("franchise", match={"type": "exact_raw", "score": "1.0"}, formula="가상 계산식"),
    "investment": energy_row(
        "investment",
        activity=amount("1830.0", "tCO2eq", None, "tCO2eq"),
        factor=None,
        investment={"share": "9.5", "scope1": "910.0", "scope2": "920.0"},
        origin=None,
        originSteps=[],
        missing=["factor"],
    ),
}


def done(rows: list[Row]) -> Row:
    return {
        "schemaVersion": "scope3.colab.result@1",
        "status": "done",
        "reportYear": 2025,
        "factorBook": {
            "sheet": "구매_USEPA",
            "column": None,
            "year": 2025,
            "reload": "reloaded",
            "reloadProblem": None,
        },
        "factorSheets": [],
        "sheets": [{"sheet": "가상시트", "category": "Category3", "status": "processed", "rows": rows}],
        "llmCalls": {},
    }


def test_there_is_one_sample_per_kind() -> None:
    assert tuple(SAMPLES) == get_args(shapes.ColabEnergyKind)


@pytest.mark.parametrize("kind", list(SAMPLES))
def test_each_kind_sample_passes_the_contract_strictly(kind: str) -> None:
    sample = SAMPLES[kind]
    TypeAdapter(shapes.ColabEnergyRowJson).validate_python(sample, strict=True)
    shapes.RESULT_SHAPES["scope3.colab.result@1"].validate_python(done([sample]), strict=True)
    assert fits(sample, typed(shapes.ColabEnergyRowJson)) == []


def test_the_discriminator_routes_energy_kinds_to_the_new_branch() -> None:
    sheet = typed(shapes.ColabProcessedSheetJson)
    assert isinstance(sheet, Obj)
    (rows,) = [field.shape for field in sheet.fields if field.key == "rows"]
    assert isinstance(rows, Arr) and isinstance(rows.item, Union)
    (energy,) = [b for b in rows.item.branches if "fuel_energy" in tag_of(b, "kind")]
    assert tag_of(energy, "kind") == get_args(shapes.ColabEnergyKind)
    # 활동 줄의 칸(treatment·mode·distance)을 달면 엄격 검사가 거절한다(새 갈래로 갔다는 것)
    with pytest.raises(ValidationError):
        shapes.RESULT_SHAPES["scope3.colab.result@1"].validate_python(
            done([energy_row("fuel_energy", treatment=None)]), strict=True
        )


def test_an_unknown_kind_or_a_missing_group_is_refused() -> None:
    adapter = shapes.RESULT_SHAPES["scope3.colab.result@1"]
    with pytest.raises(ValidationError):
        adapter.validate_python(done([energy_row("가상종류")]), strict=True)
    missing = energy_row("leased_asset")
    del missing["allocation"]
    with pytest.raises(ValidationError):
        adapter.validate_python(done([missing]), strict=True)
