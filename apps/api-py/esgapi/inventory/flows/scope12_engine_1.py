"""흐름 scope12.engine@1: Scope 1·2 엔진을 감싼다. 단계 하나(calculate). 엔진 본문은 고치지 않는다.

지금 경로(service/services/inventory.py 의 calc_rows)와 같은 길이다: calculate_raw → aggregate → output_to_dict.
다른 것은 둘 — 결과의 첫 키 schemaVersion, 그리고 표를 고르고 검사하는 일과 행 수 상한은 흐름 밖(어댑터·입력을
짓는 쪽)이라는 것.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import Carried, Flow, FlowStep, StepContext, StepOutput
from esgapi.inventory.engines.scope12.engine_1.aggregate import GroupKey, aggregate
from esgapi.inventory.engines.scope12.engine_1.calc import calculate_raw
from esgapi.inventory.engines.scope12.engine_1.serialize import output_to_dict
from esgapi.inventory.engines.scope12.engine_1.types import CalcOptions, ReferenceTables

RESULT_SHAPE: Final = "scope12.result@2"


@dataclass(frozen=True, slots=True, kw_only=True)
class Scope12Inputs:
    """rows 는 파일에서 온 날 행(검사 전). 꼴이 틀린 행은 결과의 invalid_activity 로 돌아온다."""

    rows: Sequence[Mapping[str, object]]
    gwp_set_id: str
    group_by: tuple[GroupKey, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Scope12Adapters:
    """tables 는 검사된 기준정보 표(패키지 표든 받은 표든 — 고르고 검사하는 것은 짓는 쪽)."""

    tables: ReferenceTables


def _calculate(inputs: Scope12Inputs, adapters: Scope12Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    rows = calculate_raw([dict(r) for r in inputs.rows], adapters.tables, CalcOptions(gwp_set_id=inputs.gwp_set_id))
    out = output_to_dict(gwp_set_id=inputs.gwp_set_id, rows=rows, aggregation=aggregate(rows, inputs.group_by))
    return StepOutput(data={"results": [{"schemaVersion": RESULT_SHAPE, **out}]})


FLOW: Final[Flow] = make_flow(
    module="inventory.scope12",
    id="scope12.engine@1",
    input_shape="scope12.input@1",
    inputs=Scope12Inputs,
    adapters=Scope12Adapters,
    result_shapes=(RESULT_SHAPE,),
    steps=(FlowStep(name="calculate", run=_calculate),),
)
