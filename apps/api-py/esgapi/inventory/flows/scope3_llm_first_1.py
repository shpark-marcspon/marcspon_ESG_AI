"""흐름 scope3.llm-first@1: Scope 3 의 LLM 먼저 파이프라인(run_pipeline)을 감싼다. 단계 하나(pipeline).

파이프라인은 한 함수 안에서 묶음마다 분류 → 후보 → 추천 → 계산을 돈다. 쪼개려면 엔진을 고쳐야 해서 쪼개지 않는다.
PipelineOptions 는 설정과 포트가 섞인 묶음이라 둘로 가른다: 바깥 기술(포트)은 어댑터, 작업마다 정하는 값은 입력.
결과는 새 칸을 짓지 않고 있는 serializer(engines/scope3/llm_first_1/serialize.py)를 조립만 한다 —
새 dict 는 거절의 problems 하나.
행에 입력(품목명 등)을 되싣지 않는다(입력 파일과 rowId 로 잇는다).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import Carried, Flow, FlowStep, StepContext, StepOutput
from esgapi.core.llm.types import Tags
from esgapi.inventory.engines.scope3.llm_first_1.calc import CurrencyAdjustment
from esgapi.inventory.engines.scope3.llm_first_1.memory import MappingMemory
from esgapi.inventory.engines.scope3.llm_first_1.pipeline import (
    DEFAULT_SHORTLIST_SIZE,
    PipelineOptions,
    PipelineRejected,
    run_pipeline,
)
from esgapi.inventory.engines.scope3.llm_first_1.ports import FactorCatalog, LlmGateway
from esgapi.inventory.engines.scope3.llm_first_1.serialize import (
    calc_to_dict,
    decision_to_dict,
    trace_to_dict,
    usage_to_dict,
)
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import Shortlister, default_shortlister
from esgapi.inventory.engines.scope3.llm_first_1.types import InputRow, LicenseStatus

RESULT_SHAPE: Final = "scope3.llm-first.result@2"


@dataclass(frozen=True, slots=True, kw_only=True)
class Scope3Inputs:
    rows: Sequence[InputRow]
    route: str
    tags: Tags
    exclude_license_statuses: tuple[LicenseStatus, ...] = ()
    shortlist_size: int = DEFAULT_SHORTLIST_SIZE
    adjustments: tuple[CurrencyAdjustment, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Scope3Adapters:
    llm: LlmGateway
    catalog: FactorCatalog
    memory: MappingMemory
    shortlister: Shortlister = field(default_factory=default_shortlister)


def _pipeline(inputs: Scope3Inputs, adapters: Scope3Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    options = PipelineOptions(
        client=adapters.llm,
        store=adapters.catalog,
        memory=adapters.memory,
        route=inputs.route,
        tags=inputs.tags,
        exclude_license_statuses=inputs.exclude_license_statuses,
        shortlist_size=inputs.shortlist_size,
        shortlister=adapters.shortlister,
        adjustments=inputs.adjustments,
    )
    result = run_pipeline(inputs.rows, options)
    if isinstance(result, PipelineRejected):
        rejected: dict[str, object] = {
            "schemaVersion": RESULT_SHAPE,
            "status": "rejected",
            "rejected": {
                "kind": result.kind,
                "rowId": result.row_id,
                "problems": [{"index": p.index, "kind": p.kind, "message": p.message} for p in result.problems],
            },
        }
        return StepOutput(data={"results": [rejected]})
    done: dict[str, object] = {
        "schemaVersion": RESULT_SHAPE,
        "status": "done",
        "rows": [{"rowId": r.row.row_id, "groupKey": r.group_key, "calc": calc_to_dict(r.calc)} for r in result.rows],
        "groups": [
            {
                "key": g.key,
                "rowIds": list(g.row_ids),
                "decision": decision_to_dict(g.decision),
                "shortlists": [trace_to_dict(t) for t in g.shortlists],
            }
            for g in result.groups
        ],
        "usage": usage_to_dict(result.usage),
        "shortlist": {"method": result.shortlist.method, "description": result.shortlist.description},
    }
    return StepOutput(data={"results": [done]})


FLOW: Final[Flow] = make_flow(
    module="inventory.scope3",
    id="scope3.llm-first@1",
    input_shape="scope3.input@1",
    inputs=Scope3Inputs,
    adapters=Scope3Adapters,
    result_shapes=(RESULT_SHAPE,),
    steps=(FlowStep(name="pipeline", run=_pipeline),),
)
