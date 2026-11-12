"""흐름의 선언과 레지스트리(core/flows/registry.py). 업무 모듈을 import 하지 않는다(계약 가) — 가짜 흐름만."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import pytest

from esgapi.core.flows.registry import MODULE_ID, VERSIONED_ID, FlowRegistry, make_flow
from esgapi.core.flows.types import Carried, Flow, FlowRegistryError, FlowStep, StepContext, StepOutput


@dataclass(frozen=True, slots=True, kw_only=True)
class RowsInputs:
    rows: Sequence[Mapping[str, object]]


@dataclass(frozen=True, slots=True, kw_only=True)
class RowsAdapters:
    llm: object
    catalog: object
    memory: object


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkbookInputs:
    """코랩 꼴: 워크북 파일 하나의 바이트 + 시트 이름 → 행들."""

    workbook: bytes
    sheets: Mapping[str, Sequence[Mapping[str, object]]]


@dataclass(frozen=True, slots=True, kw_only=True)
class ColabAdapters:
    factor_book: object
    llm: object
    geocoder: object
    company_mapping: object


class NotADataclass:
    pass


def _rows_step(inputs: RowsInputs, adapters: RowsAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"results": [{"schemaVersion": "scope3.llm-first.result@1"}]})


def _workbook_step(inputs: WorkbookInputs, adapters: ColabAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"results": [{"schemaVersion": "scope3.colab.result@1"}]})


def rows_flow(id: str = "scope3.llm-first@1", module: str = "inventory.scope3") -> Flow:
    return make_flow(
        module=module,
        id=id,
        input_shape="scope3.input@1",
        inputs=RowsInputs,
        adapters=RowsAdapters,
        result_shapes=("scope3.llm-first.result@1",),
        steps=(FlowStep(name="pipeline", run=_rows_step),),
    )


def colab_flow() -> Flow:
    return make_flow(
        module="inventory.scope3",
        id="scope3.colab@157",
        input_shape="scope3.colab-workbook@1",
        inputs=WorkbookInputs,
        adapters=ColabAdapters,
        result_shapes=("scope3.colab.result@1", "scope3.colab.biogenic@1"),
        output_files=("scope3-filled.xlsx",),
        steps=(FlowStep(name="fill", run=_workbook_step),),
    )


@pytest.mark.parametrize(
    "value",
    [
        "scope12.engine@1",
        "scope3.colab@157",
        "greenwash.colab@E0",
        "scope3.colab.result@1",
        "scope3.llm-first.result@1",
    ],
)
def test_versioned_ids(value: str) -> None:
    assert VERSIONED_ID.fullmatch(value) is not None


@pytest.mark.parametrize(
    "value",
    [
        "scope12.engine",
        "Scope12.engine@1",
        "scope12@1",
        "scope12.engine@",
        "scope12.engine@1.0",
        "scope12..engine@1",
    ],
)
def test_versioned_ids_refused(value: str) -> None:
    assert VERSIONED_ID.fullmatch(value) is None
    with pytest.raises(FlowRegistryError):
        rows_flow(id=value)


def test_module_ids() -> None:
    for good in ("greenwash", "inventory.scope3"):
        assert MODULE_ID.fullmatch(good) is not None
    for bad in ("Inventory", "inventory.", ".scope3", "inventory.Scope3"):
        assert MODULE_ID.fullmatch(bad) is None
        with pytest.raises(FlowRegistryError):
            rows_flow(module=bad)


def test_flow_id_starts_with_the_module_tail() -> None:
    with pytest.raises(FlowRegistryError, match="첫 마디"):
        rows_flow(id="scope12.x@1", module="inventory.scope3")
    flow = rows_flow(id="greenwash.colab@E0", module="greenwash")
    assert (flow.module, flow.id) == ("greenwash", "greenwash.colab@E0")


def test_the_same_flow_id_twice_is_an_error() -> None:
    registry = FlowRegistry()
    first = rows_flow()
    registry.register(first)
    with pytest.raises(FlowRegistryError, match="이미 있다"):
        registry.register(first)
    with pytest.raises(FlowRegistryError, match="이미 있다"):
        registry.register(rows_flow())
    assert registry.get("scope3.llm-first@1") is first
    assert registry.flows_of("inventory.scope3") == (first,)


def test_flows_with_different_shapes_in_one_module() -> None:
    registry = FlowRegistry()
    a, b, c = rows_flow(), colab_flow(), rows_flow(id="scope3.llm-first@2")
    for flow in (a, b, c):
        registry.register(flow)
    assert registry.flows_of("inventory.scope3") == (a, b, c)
    assert registry.modules() == ("inventory.scope3",)
    assert a.adapter_names == ("llm", "catalog", "memory")
    assert b.adapter_names == ("factor_book", "llm", "geocoder", "company_mapping")
    assert b.input_shape == "scope3.colab-workbook@1"
    assert b.result_shapes == ("scope3.colab.result@1", "scope3.colab.biogenic@1")
    assert b.output_files == ("scope3-filled.xlsx",)
    assert a.result_shapes == c.result_shapes == ("scope3.llm-first.result@1",)
    assert a.output_files == c.output_files == ()
    assert (a.inputs, b.inputs) == (RowsInputs, WorkbookInputs)


def _declare(**overrides: object) -> Flow:
    given: dict[str, object] = {
        "module": "greenwash",
        "id": "greenwash.colab@E0",
        "input_shape": "greenwash.document@1",
        "inputs": RowsInputs,
        "adapters": RowsAdapters,
        "result_shapes": ("greenwash.result@1",),
        "output_files": ("greenwash-report.xlsx",),
        "steps": (FlowStep(name="extract", run=_rows_step), FlowStep(name="judge", run=_rows_step)),
    }
    given.update(overrides)
    # 일부러 틀린 꼴(dataclass 아님·인스턴스)도 넣는다 — 거절을 잰다. 그래서 꼴을 Any 로 연다
    return make_flow(**cast("dict[str, Any]", given))


@pytest.mark.parametrize(
    ("what", "overrides"),
    [
        ("단계 0개", {"steps": ()}),
        ("단계 이름 겹침", {"steps": (FlowStep(name="judge", run=_rows_step), FlowStep(name="judge", run=_rows_step))}),
        ("단계 이름 꼴", {"steps": (FlowStep(name="Judge", run=_rows_step),)}),
        ("결과 꼴 0개", {"result_shapes": ()}),
        ("결과 꼴 겹침", {"result_shapes": ("greenwash.result@1", "greenwash.result@1")}),
        ("결과 꼴 이름 꼴", {"result_shapes": ("greenwash.result",)}),
        ("입력 꼴 이름 꼴", {"input_shape": "greenwash.document"}),
        ("출력 파일 이름 겹침", {"output_files": ("a.xlsx", "a.xlsx")}),
        ("어댑터가 dataclass 아님", {"adapters": NotADataclass}),
        ("입력이 dataclass 아님", {"inputs": NotADataclass}),
        ("입력이 dataclass 의 인스턴스", {"inputs": RowsInputs(rows=())}),
    ],
)
def test_declarations_are_checked(what: str, overrides: dict[str, object]) -> None:
    with pytest.raises(FlowRegistryError):
        _declare(**overrides)


def test_a_valid_declaration_passes() -> None:
    flow = _declare()
    assert flow.steps == ("extract", "judge")
    assert flow.optional_adapters == ()


def test_defaults() -> None:
    registry = FlowRegistry()
    one, two = rows_flow(), rows_flow(id="scope3.llm-first@2")
    other = rows_flow(id="greenwash.colab@E0", module="greenwash")
    for flow in (one, two, other):
        registry.register(flow)
    assert registry.modules_without_default() == ("inventory.scope3", "greenwash")
    with pytest.raises(FlowRegistryError, match="기본 흐름이 없다"):
        registry.default_of("inventory.scope3")
    with pytest.raises(FlowRegistryError, match="없다"):
        registry.set_default("inventory.scope3", "scope3.nothing@1")
    with pytest.raises(FlowRegistryError, match="모듈 greenwash 의 것"):
        registry.set_default("inventory.scope3", "greenwash.colab@E0")
    registry.set_default("inventory.scope3", one.id)
    assert registry.default_of("inventory.scope3") is one
    assert registry.modules_without_default() == ("greenwash",)
    registry.set_default("inventory.scope3", two.id)
    assert registry.default_of("inventory.scope3") is two
    registry.set_default("greenwash", other.id)
    assert registry.defaults() == {"inventory.scope3": "scope3.llm-first@2", "greenwash": "greenwash.colab@E0"}
    assert registry.modules_without_default() == ()
