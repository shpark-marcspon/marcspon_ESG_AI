"""결과 꼴 둘(contracts/shapes.py): 고정 스키마 파일과 글자까지 같고, 실제 결과와 모든 갈래가 그 꼴에 맞으며,
칸을 빼거나 더하면 빨갛다. 갈래 목록은 엔진의 타입에서 뽑는다(손으로 적은 목록과 견주지 않는다).
"""

import copy
import json
from dataclasses import fields
from pathlib import Path
from typing import cast, get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from esgapi.inventory.contracts import shapes
from esgapi.inventory.engines.scope3.llm_first_1 import calc as s3calc
from esgapi.inventory.engines.scope3.llm_first_1 import pipeline as s3
from esgapi.inventory.engines.scope3.llm_first_1.llm_steps import Classification, LlmFailure
from esgapi.inventory.engines.scope3.llm_first_1.memory import MemoryEntry
from esgapi.inventory.engines.scope3.llm_first_1.ranking import CandidateEvidence, LexicalEvidence
from esgapi.inventory.engines.scope3.llm_first_1.serialize import calc_to_dict, decision_to_dict, trace_to_dict
from esgapi.inventory.engines.scope3.llm_first_1.types import FactorPick
from esgapi.inventory.engines.scope12.engine_1 import types as s12
from esgapi.inventory.engines.scope12.engine_1.serialize import failure_to_dict
from esgapi.inventory.flows import registration
from esgapi.inventory.tests.flows.test_scope3_colab_157 import colab_flow_result
from esgapi.inventory.tests.scope3_catalog_support import load_catalog, load_examples
from esgapi.inventory.tests.scope3_llm_support import harness
from esgapi.inventory.tests.test_flows import scope3_flow_result, scope3_harness, scope12_run
from esgapi.inventory.tests.test_golden import PURE_GOLDENS
from esgapi.inventory.tests.test_scope3_golden_full import CONFIGS

PINNED = Path(__file__).resolve().parent / "data" / "flow-shapes"


def pinned_text(shape: str) -> str:
    return json.dumps(shapes.RESULT_SHAPES[shape].json_schema(), ensure_ascii=False, indent=2) + "\n"


@pytest.mark.parametrize("shape", ["scope12.result@2", "scope3.llm-first.result@2", "scope3.colab.result@1"])
def test_the_json_schema_is_pinned(shape: str) -> None:
    assert pinned_text(shape) == (PINNED / f"{shape}.schema.json").read_text(encoding="utf-8")


def check(result: dict[str, object]) -> None:
    shapes.RESULT_SHAPES[cast("str", result["schemaVersion"])].validate_python(result, strict=True)


def flow_result(case: str) -> dict[str, object]:
    """case: 골든 파일 이름(Scope 1·2 의 8벌) · scope3:<설정>(넷) · rejected:<까닭>(둘) · colab:<갈래>(셋)."""
    for golden, activity, which, by in PURE_GOLDENS:
        if case == golden:
            return scope12_run(activity, which, by)[0]
    for name, shortlister, size, exclude, adjusted in CONFIGS:
        if case == f"scope3:{name}":
            rows = [example.row for example in load_examples()]
            return scope3_flow_result(scope3_harness(shortlister, size, exclude, adjusted).options, rows)
    first = load_examples()[0].row
    if case == "rejected:duplicate_row_id":
        return scope3_flow_result(scope3_harness(*CONFIGS[0][1:]).options, [first, first])
    if case.startswith("colab:"):
        return colab_flow_result(case)
    assert case == "rejected:invalid_adjustments"
    bad = s3calc.CurrencyAdjustment("KRW", "USD", 2022, "1e-3", synthetic=True, source=None)
    return scope3_flow_result(harness(load_catalog(), heuristic=True, adjustments=(bad,)).options, [first])


CASES = [
    *(g[0] for g in PURE_GOLDENS),
    *(f"scope3:{c[0]}" for c in CONFIGS),
    "rejected:duplicate_row_id",
    "rejected:invalid_adjustments",
    "colab:done",
    "colab:rejected",
    "colab:activity",
]


@pytest.mark.parametrize("case", CASES)
def test_flow_results_fit_their_shape(case: str) -> None:
    check(flow_result(case))


# ── 모든 갈래: dataclass 를 직접 지어 serializer 로 옮긴다 ──

FAILURES: list[s12.Failure] = [
    s12.InvalidActivity(field="quantity", value="-1", reason="음수"),
    s12.FactorNotFound(criteria={"fuel": "가상 연료"}),
    s12.FactorAmbiguous(criteria={"fuel": "가상 연료"}, candidate_ids=("f1", "f2")),
    s12.FactorKindMismatch(factor_id="f1", expected="combustion", actual="purchased_energy"),
    s12.FactorIncomplete(factor_id="f1", reason="발열량 없음"),
    s12.InvalidReferenceValue(where="factors[0].calorific.value", value="x"),
    s12.CalorificBasisMismatch(factor_id="f1", required="net", actual="gross"),
    s12.UnitConversionNotFound(from_unit="Nm3", to_unit="TJ", context="발열량"),
    s12.UnitConversionAmbiguous(from_unit="Nm3", to_unit="TJ", factors=("c1", "c2")),
    s12.GwpSetNotFound(gwp_set_id="g"),
    s12.GwpSetAmbiguous(gwp_set_id="g"),
    s12.GwpValueMissing(gwp_set_id="g", gas="N2O"),
]

ADJUSTMENT = s3calc.CurrencyAdjustment(
    "KRW", "USD", 2022, "0.0008", synthetic=False, source=s3calc.AdjustmentSource("https://example.org", "2026-10-15")
)
CALCS: list[s3calc.CalcResult] = [
    s3calc.Computed(
        co2e="1.5",
        factor_id="f1",
        factor_value_raw="0.5",
        factor_unit="kgCO2e/kg",
        activity_amount="3",
        formula="3 × 0.5",
        adjustment=ADJUSTMENT,
        synthetic=True,
    ),
    s3calc.NeedsDistance(factor_id="f1"),
    s3calc.NeedsCurrencyAdjustment(factor_id="f1", currency=None, target_currency="USD", target_price_year=2022),
    s3calc.MissingQuantity(factor_id="f1"),
    s3calc.MissingAmount(factor_id="f1"),
    s3calc.InvalidNumber(factor_id="f1", field="multiplier"),
    s3calc.UnitMismatch(factor_id="f1", row_unit=None, factor_unit="kg"),
    s3calc.UnsupportedFactorUnit(factor_id="f1", factor_unit="m3"),
    s3calc.NotCalculated(reason="판단 없음"),
]

ENTRY = MemoryEntry(
    key="k", category=1, factor_id="f1", confirmed_by="synthetic-reviewer", confirmed_at="2026-10-15", label="가상"
)
CLASSIFIED = Classification(category=1, keywords=("steel",), confidence="high", reason="가상")
OTHER = Classification(category="other", keywords=(), confidence="low", reason="가상")
FAILED = LlmFailure(kind="refusal", detail="가상")
DECISIONS: list[s3.GroupDecision] = [
    s3.Recommended(
        source="llm",
        category=1,
        picks=(FactorPick(factor_id="f1", reason="가상", confidence="medium"),),
        basis=s3.BasisTrace(used="spend", fell_back=True, fallback_reason="unit_mismatch"),
        classification=CLASSIFIED,
        memory_entry=ENTRY,
        candidates=s3.CandidateStats(total=10, shown=5, lexical_matches=3, method="lexical-v2"),
    ),
    s3.MemoryFactorMissing(memory_entry=ENTRY),
    s3.MemoryCategoryMismatch(memory_entry=ENTRY, factor_categories=(2, 4)),
    s3.MemoryFactorExcluded(memory_entry=ENTRY, license_status="disputed"),
    s3.ClassificationFailed(llm=FAILED),
    s3.UnsupportedCategory(classification=OTHER),
    s3.NoCandidates(category=1, classification=CLASSIFIED, physical="no_activity_candidates"),
    s3.NoSuitableFactor(category=1, classification=CLASSIFIED, physical="llm_found_none_suitable"),
    s3.RecommendationFailed(category=1, classification=CLASSIFIED, basis="physical", llm=FAILED),
]


def tag(cls: type, name: str) -> object:
    """갈래 dataclass 의 판별 칸(kind·status)의 기본값."""
    return next(f.default for f in fields(cls) if f.name == name)


def test_every_branch_fits() -> None:
    failure_types = get_args(s12.Failure)
    calc_types = get_args(s3calc.CalcResult.__value__)  # type X = … 는 get_args(X) 가 빈 튜플이다
    decision_types = get_args(s3.GroupDecision.__value__)
    assert (len(failure_types), len(calc_types), len(decision_types)) == (12, 9, 9)
    assert {tag(c, "kind") for c in failure_types} == {f.kind for f in FAILURES}
    assert {tag(c, "status") for c in calc_types} == {c.status for c in CALCS}
    assert {tag(c, "status") for c in decision_types} == {d.status for d in DECISIONS}
    assert len(FAILURES) == 12 and len(CALCS) == 9 and len(DECISIONS) == 9

    failure_shape = TypeAdapter[object](shapes.FailureJson)
    calc_shape = TypeAdapter[object](shapes.CalcJson)
    decision_shape = TypeAdapter[object](shapes.DecisionJson)
    for failure in FAILURES:
        failure_shape.validate_python(json.loads(json.dumps(failure_to_dict(failure))), strict=True)
    for result in [*CALCS, s3calc.NeedsCurrencyAdjustment("f1", "KRW", "USD", 2022)]:
        calc_shape.validate_python(json.loads(json.dumps(calc_to_dict(result))), strict=True)
    for decision in [*DECISIONS, s3.MemoryFactorMissing(memory_entry=MemoryEntry("k", 1, "f1", "r", "t"))]:
        decision_shape.validate_python(json.loads(json.dumps(decision_to_dict(decision))), strict=True)

    trace = s3.ShortlistTrace(
        basis="physical",
        method="lexical-v2",
        total=3,
        shown_ids=("a", "b"),
        evidence=(
            CandidateEvidence(
                id="a", rank=1, lexical=LexicalEvidence(rank=1, score=0.5, matched_terms=("x",)), rrf_score=0.1
            ),
            CandidateEvidence(id="b", rank=2),
        ),
    )
    TypeAdapter(shapes.ShortlistTraceJson).validate_python(json.loads(json.dumps(trace_to_dict(trace))), strict=True)


# ── 칸을 빼거나 더하면 빨갛다 ──


def test_a_missing_or_extra_key_is_rejected() -> None:
    base12, base3 = flow_result(PURE_GOLDENS[0][0]), flow_result(f"scope3:{CONFIGS[0][0]}")
    check(base12)
    check(base3)
    rows = cast("list[dict[str, object]]", base12["rows"])
    assert rows[0]["status"] == "ok"

    s12_shape, s3_shape = "scope12.result@2", "scope3.llm-first.result@2"
    broken: list[tuple[str, dict[str, object]]] = []
    for key in ("schemaVersion", "aggregation", "gwpSetId"):
        broken.append((s12_shape, {k: v for k, v in base12.items() if k != key}))
    for key in ("schemaVersion", "usage", "groups"):
        broken.append((s3_shape, {k: v for k, v in base3.items() if k != key}))
    no_evidence = copy.deepcopy(base12)
    del cast("list[dict[str, object]]", no_evidence["rows"])[0]["evidence"]
    broken.append((s12_shape, no_evidence))
    broken.append((s12_shape, {**base12, "unknown": 1}))
    broken.append((s3_shape, {**base3, "unknown": 1}))
    nested = copy.deepcopy(base12)
    cast("list[dict[str, object]]", nested["rows"])[0]["unknown"] = 1
    broken.append((s12_shape, nested))
    # 지운 옛 판. 그 글자가 상수로 남지 않게 잇는다(section4-RR1.sh 가 상수를 센다)
    broken.append((s12_shape, {**base12, "schemaVersion": "scope12.result@" + "1"}))
    broken.append((s3_shape, {**base3, "schemaVersion": "scope3.result@1"}))
    for shape, item in broken:
        with pytest.raises(ValidationError):
            shapes.RESULT_SHAPES[shape].validate_python(item, strict=True)


def test_every_registered_shape_is_pinned() -> None:
    declared = {shape for flow in registration.FLOWS for shape in flow.result_shapes}
    files = {p.name.removesuffix(".schema.json") for p in PINNED.glob("*.schema.json")}
    assert declared == set(shapes.RESULT_SHAPES) == files
