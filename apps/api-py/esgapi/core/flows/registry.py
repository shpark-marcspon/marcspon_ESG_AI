"""흐름의 선언(make_flow)과 레지스트리. core 는 업무 모듈을 모른다 — 모듈이 자기 AppConfig.ready() 에서 단다.

    FLOW = make_flow(module="greenwash", id="greenwash.colab@E0", input_shape="greenwash.document@1",
                     inputs=GreenwashInputs, adapters=GreenwashAdapters, result_shapes=("greenwash.result@1",),
                     output_files=("greenwash-report.xlsx",), steps=(FlowStep(name="extract", run=…), …))
    REGISTRY.register(FLOW)
    REGISTRY.set_default("greenwash", FLOW.id)

이름: 모듈 id 는 점으로 이은 소문자 마디(MODULE_ID), 흐름 id·입력 꼴 id·결과 꼴 id 는 <이름>@<판>(VERSIONED_ID —
이름은 마디 둘 이상, 판은 비교하지 않는 표지). 흐름 id 의 첫 마디 = 모듈 id 의 끝 마디. 꼴을 바꾸면 새 판이다.
저장·큐·재시도 정책과 기본 흐름의 어드민 표는 여기 없다(실행기의 일).

펼침 단계(FanoutStep — RM1a)는 첫·끝 단계가 될 수 없다(앞 장벽 = 문서 전체 문맥, 뒤 모음 장벽 = 끝 산출물 규칙이
장벽에만 있다). 펼침 여럿은 된다. 펼침의 plan·run 도 run_step 처럼 입력·어댑터의 꼴을 본다(감싼 것이 Flow.fanouts).
"""

import re
from dataclasses import fields, is_dataclass, replace
from inspect import isclass
from typing import Any, Final, cast

from esgapi.core.flows.types import (
    MAX_SEGMENTS_CEILING,
    Carried,
    FanoutStep,
    Flow,
    FlowInputError,
    FlowRegistryError,
    FlowStep,
    ResultCheck,
    Segment,
    SegmentOutput,
    StepContext,
    StepKind,
    StepOutput,
)

MODULE_ID: Final = re.compile(r"[a-z][a-z0-9]*(\.[a-z][a-z0-9-]*)*")
VERSIONED_ID: Final = re.compile(r"[a-z][a-z0-9]*(\.[a-z][a-z0-9-]*)+@[A-Za-z0-9]+")
STEP_NAME: Final = re.compile(r"[a-z][a-z0-9_]*")


def _check(pattern: re.Pattern[str], what: str, value: str) -> None:
    if pattern.fullmatch(value) is None:
        raise FlowRegistryError(f"{what} 의 꼴이 틀렸다: {value!r}")


def _unique(what: str, values: tuple[str, ...]) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise FlowRegistryError(f"{what} 이 겹친다: {value!r}")
        seen.add(value)


def _check_fanout(flow_id: str, step: FanoutStep[Any, Any]) -> None:
    """펼침 선언의 칸 범위(기본값이 없어 칸은 늘 있다 — 값을 본다)."""
    where = f"흐름 {flow_id} 의 펼침 단계 {step.name}"
    if not callable(step.plan) or not callable(step.run):
        raise FlowRegistryError(f"{where} 의 plan·run 이 함수가 아니다")
    if step.on_failure not in ("fail_run", "pass_to_gather"):
        raise FlowRegistryError(f"{where} 의 on_failure 가 fail_run·pass_to_gather 가 아니다: {step.on_failure!r}")
    if not isinstance(step.allow_empty, bool):  # pyright: ignore[reportUnnecessaryIsInstance]  (선언 밖 값을 막는다)
        raise FlowRegistryError(f"{where} 의 allow_empty 가 bool 이 아니다: {step.allow_empty!r}")
    count = step.max_segments
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_SEGMENTS_CEILING:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise FlowRegistryError(f"{where} 의 max_segments 는 1~{MAX_SEGMENTS_CEILING} 정수여야 한다: {count!r}")


def make_flow[I, A](
    *,
    module: str,
    id: str,
    input_shape: str,
    inputs: type[I],
    adapters: type[A],
    result_shapes: tuple[str, ...],
    steps: tuple[FlowStep[I, A] | FanoutStep[I, A], ...],
    output_files: tuple[str, ...] = (),
    result_checks: tuple[ResultCheck, ...] = (),
) -> Flow:
    """흐름 하나를 선언한다. 이름과 선언을 검사하고(틀리면 FlowRegistryError), 단계 입구를 감싼다."""
    _check(MODULE_ID, "모듈 id", module)
    _check(VERSIONED_ID, "흐름 id", id)
    _check(VERSIONED_ID, "입력 꼴 id", input_shape)
    if id.split("@", 1)[0].split(".", 1)[0] != module.rsplit(".", 1)[-1]:
        raise FlowRegistryError(f"흐름 id {id} 의 첫 마디가 모듈 id {module} 의 끝 마디가 아니다")
    if not steps:
        raise FlowRegistryError(f"흐름 {id} 에 단계가 없다")
    names = tuple(step.name for step in steps)
    for name in names:
        _check(STEP_NAME, "단계 이름", name)
    _unique("단계 이름", names)
    if not result_shapes:
        raise FlowRegistryError(f"흐름 {id} 에 결과 꼴이 없다")
    for shape in result_shapes:
        _check(VERSIONED_ID, "결과 꼴 id", shape)
    _unique("결과 꼴 id", result_shapes)
    _unique("출력 파일 이름", output_files)
    kinds: tuple[StepKind, ...] = tuple("fanout" if isinstance(step, FanoutStep) else "barrier" for step in steps)
    for position, step in enumerate(steps):
        if not isinstance(step, FanoutStep):
            continue
        if position in (0, len(steps) - 1):
            raise FlowRegistryError(f"흐름 {id} 의 펼침 단계 {step.name} 이 첫·끝 단계다(앞뒤에 장벽이 있어야 한다)")
        _check_fanout(id, step)
    for check in result_checks:
        if not callable(check):
            raise FlowRegistryError(f"흐름 {id} 의 result_checks 에 함수가 아닌 값이 있다: {check!r}")
    for what, given in (("입력", inputs), ("어댑터", adapters)):
        if not (isclass(given) and is_dataclass(given)):
            raise FlowRegistryError(f"흐름 {id} 의 {what} 꼴이 dataclass 가 아니다: {given!r}")
    if not is_dataclass(adapters):  # 위에서 봤다. pyright 가 fields() 의 인자로 좁히게 한 번 더
        raise FlowRegistryError(f"흐름 {id} 의 어댑터 꼴이 dataclass 가 아니다: {adapters!r}")
    adapter_fields = fields(adapters)
    table = {step.name: step.run for step in steps if isinstance(step, FlowStep)}

    def checked_inputs(given_inputs: object) -> I:
        if not isinstance(given_inputs, inputs):
            raise FlowInputError(f"흐름 {id} 의 입력이 {inputs.__name__} 가 아니다: {type(given_inputs).__name__}")
        return given_inputs

    def checked_adapters(given_adapters: object) -> A:
        if not isinstance(given_adapters, adapters):
            raise FlowInputError(
                f"흐름 {id} 의 어댑터가 {adapters.__name__} 가 아니다: {type(given_adapters).__name__}"
            )
        return given_adapters

    def run_step(
        name: str, given_inputs: object, given_adapters: object, carried: Carried, ctx: StepContext
    ) -> StepOutput:
        if name not in table:
            raise FlowInputError(f"흐름 {id} 의 {name!r} 은 장벽 단계가 아니다(펼침 단계는 run_flow 가 돌린다)")
        return table[name](checked_inputs(given_inputs), checked_adapters(given_adapters), carried, ctx)

    def guarded(step: FanoutStep[I, A]) -> FanoutStep[Any, Any]:
        plan, run = step.plan, step.run

        def guarded_plan(given_inputs: object, carried: Carried) -> tuple[Segment, ...]:
            return plan(checked_inputs(given_inputs), carried)

        def guarded_run(
            given_inputs: object, given_adapters: object, carried: Carried, segment: Segment, ctx: StepContext
        ) -> SegmentOutput:
            return run(checked_inputs(given_inputs), checked_adapters(given_adapters), carried, segment, ctx)

        erased = cast("FanoutStep[Any, Any]", step)  # 꼴 인자를 지운 같은 선언(감싼 함수를 끼우려고)
        return replace(erased, plan=guarded_plan, run=guarded_run)

    fanouts = {step.name: guarded(step) for step in steps if isinstance(step, FanoutStep)}

    return Flow(
        module=module,
        id=id,
        input_shape=input_shape,
        result_shapes=result_shapes,
        output_files=output_files,
        inputs=inputs,
        adapters=adapters,
        adapter_names=tuple(f.name for f in adapter_fields),
        optional_adapters=tuple(f.name for f in adapter_fields if f.default is None),
        steps=names,
        step_kinds=kinds,
        result_checks=result_checks,
        run_step=run_step,
        fanouts=fanouts,
    )


class FlowRegistry:
    """흐름 id@판 → 흐름, 모듈 id → 기본 흐름 id. 프로세스에 하나(REGISTRY). 순수 테스트는 새 것을 짓는다."""

    def __init__(self) -> None:
        self._flows: dict[str, Flow] = {}
        self._defaults: dict[str, str] = {}

    def register(self, flow: Flow) -> None:
        """같은 흐름 id@판이 이미 있으면 FlowRegistryError(같은 객체여도 — 두 번 다는 길을 조용히 넘기지 않는다)."""
        if flow.id in self._flows:
            raise FlowRegistryError(f"흐름 {flow.id} 이 이미 있다")
        self._flows[flow.id] = flow

    def get(self, flow_id: str) -> Flow:
        try:
            return self._flows[flow_id]
        except KeyError:
            raise FlowRegistryError(f"흐름 {flow_id} 이 없다") from None

    def modules(self) -> tuple[str, ...]:
        """흐름이 있는 모듈(처음 등록된 차례)."""
        return tuple(dict.fromkeys(flow.module for flow in self._flows.values()))

    def flows_of(self, module: str) -> tuple[Flow, ...]:
        """그 모듈의 흐름(등록 차례)."""
        return tuple(flow for flow in self._flows.values() if flow.module == module)

    def set_default(self, module: str, flow_id: str) -> None:
        """모듈의 기본 흐름을 정한다(바꿀 수 있다). 없는 흐름이나 남의 모듈의 흐름이면 FlowRegistryError."""
        flow = self.get(flow_id)
        if flow.module != module:
            raise FlowRegistryError(
                f"흐름 {flow_id} 은 모듈 {flow.module} 의 것이다(모듈 {module} 의 기본값이 될 수 없다)"
            )
        self._defaults[module] = flow_id

    def default_of(self, module: str) -> Flow:
        try:
            return self._flows[self._defaults[module]]
        except KeyError:
            raise FlowRegistryError(f"모듈 {module} 에 기본 흐름이 없다") from None

    def defaults(self) -> dict[str, str]:
        """모듈 id → 기본 흐름 id(정한 차례)."""
        return dict(self._defaults)

    def modules_without_default(self) -> tuple[str, ...]:
        return tuple(module for module in self.modules() if module not in self._defaults)


REGISTRY: Final = FlowRegistry()
"""프로세스에 하나. 각 모듈의 AppConfig.ready() 가 단다(Django 의 apps.populate 가 프로세스마다 한 번 부른다)."""
