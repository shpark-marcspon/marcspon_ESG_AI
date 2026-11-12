"""dataclass → JSON dict. 실패의 열두 갈래가 TS 와 같은 키로 나가는가. 순수 층.

성공한 행과 집계의 꼴은 골든(test_golden.py)이 통째로 잰다. 골든에 나오지 않는 실패 갈래는 여기서 본다.
"""

from typing import Any, get_args

import pytest

from esgapi.inventory.engines.scope12.engine_1.provenance import Cited, Definition, Synthetic
from esgapi.inventory.engines.scope12.engine_1.serialize import failure_to_dict, provenance_to_dict, step_to_dict
from esgapi.inventory.engines.scope12.engine_1.types import (
    CalorificBasisMismatch,
    FactorAmbiguous,
    FactorIncomplete,
    FactorKindMismatch,
    FactorNotFound,
    Failure,
    GwpSetAmbiguous,
    GwpSetNotFound,
    GwpValueMissing,
    InvalidActivity,
    InvalidReferenceValue,
    Step,
    UnitConversion,
    UnitConversionAmbiguous,
    UnitConversionNotFound,
)

# 키의 이름과 순서는 esg-lab `ts/ghg-calc/src/types.ts` 의 Failure 와 calc.ts·units.ts 가 객체를 만드는 순서다.
FAILURES: list[tuple[Failure, dict[str, Any]]] = [
    (
        InvalidActivity(field="amount", value="-1", reason="음수 사용량"),
        {"kind": "invalid_activity", "field": "amount", "value": "-1", "reason": "음수 사용량"},
    ),
    (FactorNotFound(criteria={"factorId": "x"}), {"kind": "factor_not_found", "criteria": {"factorId": "x"}}),
    (
        FactorAmbiguous(criteria={"factorId": "x"}, candidate_ids=("x", "x")),
        {"kind": "factor_ambiguous", "criteria": {"factorId": "x"}, "candidateIds": ["x", "x"]},
    ),
    (
        FactorKindMismatch(factor_id="e", expected="combustion", actual="purchased_energy"),
        {"kind": "factor_kind_mismatch", "factorId": "e", "expected": "combustion", "actual": "purchased_energy"},
    ),
    (
        FactorIncomplete(factor_id="f", reason="CH4 배출계수가 없다"),
        {"kind": "factor_incomplete", "factorId": "f", "reason": "CH4 배출계수가 없다"},
    ),
    (
        InvalidReferenceValue(where="factors[f].calorific.value", value="35,2"),
        {"kind": "invalid_reference_value", "where": "factors[f].calorific.value", "value": "35,2"},
    ),
    (
        CalorificBasisMismatch(factor_id="f", required="net", actual="gross"),
        {"kind": "calorific_basis_mismatch", "factorId": "f", "required": "net", "actual": "gross"},
    ),
    (
        UnitConversionNotFound(from_unit="kg", to_unit="L", context="c"),
        {"kind": "unit_conversion_not_found", "from": "kg", "to": "L", "context": "c"},
    ),
    (
        UnitConversionAmbiguous(from_unit="a", to_unit="b", factors=("2", "3")),
        {"kind": "unit_conversion_ambiguous", "from": "a", "to": "b", "factors": ["2", "3"]},
    ),
    (GwpSetNotFound(gwp_set_id="AR4"), {"kind": "gwp_set_not_found", "gwpSetId": "AR4"}),
    (GwpSetAmbiguous(gwp_set_id="AR4"), {"kind": "gwp_set_ambiguous", "gwpSetId": "AR4"}),
    (
        GwpValueMissing(gwp_set_id="p", gas="N2O"),
        {"kind": "gwp_value_missing", "gwpSetId": "p", "gas": "N2O"},
    ),
]


@pytest.mark.parametrize(("failure", "expected"), FAILURES, ids=[f.kind for f, _ in FAILURES])
def test_failure_to_dict(failure: Failure, expected: dict[str, Any]) -> None:
    actual = failure_to_dict(failure)
    assert actual == expected
    assert list(actual) == list(expected)  # 키의 순서


def test_all_twelve_failure_kinds_are_covered() -> None:
    assert len(get_args(Failure)) == 12
    assert {type(failure) for failure, _ in FAILURES} == set(get_args(Failure))


def test_optional_keys_are_left_out_not_null() -> None:
    """선택 칸은 없으면 키가 없다(null 로 내보내지 않는다)."""
    cited = Cited(title="t", url="https://example.invalid/", checked_on="2026-10-01")
    assert provenance_to_dict(cited) == {
        "kind": "cited",
        "title": "t",
        "url": "https://example.invalid/",
        "checkedOn": "2026-10-01",
    }
    with_locator = Cited(title="t", url="https://example.invalid/", checked_on="2026-10-01", locator="표 1", note="n")
    assert list(provenance_to_dict(with_locator)) == ["kind", "title", "url", "checkedOn", "locator", "note"]
    assert provenance_to_dict(Synthetic(note="n")) == {"kind": "synthetic", "note": "n"}

    plain = Step(label="에너지량", formula="1 L × 2 MJ/L", result="2", unit="MJ")
    assert step_to_dict(plain) == {"label": "에너지량", "formula": "1 L × 2 MJ/L", "result": "2", "unit": "MJ"}
    conversion = UnitConversion(from_unit="L", to_unit="kL", factor="0.001", source=Definition(note="SI"))
    converted = Step(label="단위 환산", formula="f", result="1", unit="kL", conversion=conversion)
    assert step_to_dict(converted)["conversion"] == {
        "from": "L",
        "to": "kL",
        "factor": "0.001",
        "source": {"kind": "definition", "note": "SI"},
    }
