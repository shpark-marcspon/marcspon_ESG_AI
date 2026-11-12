"""흐름을 돌린다: 단계를 차례로, 또는 단계 k 부터(앞 단계는 부르지 않는다) 이어서.

    run = run_flow(FLOW, inputs, adapters)                                          # 처음부터
    run = run_flow(FLOW, inputs, adapters, start_at="judge", carried=saved)         # 단계 judge 부터
    run = run_flow(FLOW, inputs, adapters, start_at="judge", carried=saved, resume=partial)   # judge 안에서 이어서

규칙:
  - 단계의 data 는 JSON 으로 한 번 왕복한 값으로 뒤 단계·사건·FlowStepFailed.completed·FlowRun.steps 에 간다
    (끝까지 한 번 돈 실행과 저장된 체크포인트에서 이어 돈 실행이 같은 값을 보게).
    넘겨받은 carried·resume 도 왕복해 받는다.
  - 단계가 실패하면(단계의 예외, 산출물·끝 산출물 검사의 FlowOutputError) step_failed 뒤 언제나 FlowStepFailed.
  - 사건 받는 쪽이 낸 예외는 그대로 올린다(실행기의 잘못을 삼키지 않는다).
  - core 가 결과에서 읽는 키는 schemaVersion 하나다. 결과의 안은 그 모듈의 결과 꼴이 검사한다.
  - 끝 결과 검사 훅(flow.result_checks)이 던지면 마지막 단계의 실패다(FlowOutputError 로 감싼다).

펼침 단계(RM1a — 직렬, 한 시도 안에서 계획 차례로):
  ① plan → 꼴 검사(열쇠 꼴·겹침·max_segments, 구획 입력 JSON 왕복). 0개면 allow_empty 대로(빈 목록 / SegmentsEmpty)
  ② segment_events.segments_planned(열쇠 목록)
  ③ 구획마다: segments_done 에 있으면 그 값(run 0회·구획 사건 0) · 없으면 segment_started → run → 산출 검사(JSON 왕복·
     SEGMENT_DATA_MAX_OCTETS) → segment_finished. run 의 예외나 산출 검사의 FlowOutputError 만 segment_failed 로 가고
     받는 쪽이 돌려준 code 가 그 구획의 errorCode 다. fail_run 이면 첫 실패에서 남은 구획을 부르지 않고 SegmentsFailed.
     구획이 끝날 때마다 step_progress(끝난 구획 수, 계획 수, {}).
  ④ 단계 data = {"segments": [{"key", "keySha256", "status", "data", "errorCode"}]}(계획 차례). 합이
     FANOUT_DATA_MAX_OCTETS 를 넘으면 단계 실패.
  구획 사건 받는 쪽의 예외는 그대로 올린다(SegmentPlanMismatch·잠깐 오류의 다시 던짐 포함 — 단계가 삼켜도).
  단 받는 쪽이 SegmentFatal 을 던지면(RM1b 635-1 — 실행의 치명 실패) 단계 실패로 접는다: step_failed 뒤
  FlowStepFailed(펼침 단계)의 __cause__ = 원래 예외.
  ④ 의 합 검사는 항목을 더할 때마다 한다(RM1b 635-2 — 넘는 자리에서 단계 실패, 뒤 구획 run 0회).
  ⑤ 맡김(RM1b — run_flow(dispatch=…), 키워드 전용. None 이면 위 직렬 그대로): ② 뒤 fail_run 이고 끝난 구획에 실패가
     있으면 SegmentsFailed(계획 차례 첫 실패) · 끝나지 않은 구획이 있으면 dispatch.dispatch(계획 차례의 열쇠 — 돌아오지
     않는다. 돌아오면 단계 실패) · 다 끝났으면 ④ 로 모은다. 맡김이면 구획 run 0회.
  구획 하나·계획 하나를 밖에서 부르는 길: run_segment·plan_segments(공개 — 직렬과 같은 검사).
"""

import json
from collections.abc import Callable, Mapping
from typing import Any, cast

from esgapi.core.flows.types import (
    FANOUT_DATA_MAX_OCTETS,
    NO_EVENTS,
    NO_SEGMENT_EVENTS,
    SEGMENT_DATA_MAX_OCTETS,
    Carried,
    FanoutStep,
    Flow,
    FlowEvents,
    FlowInputError,
    FlowOutput,
    FlowOutputError,
    FlowRun,
    FlowStepFailed,
    OutputFile,
    Segment,
    SegmentDispatch,
    SegmentEnded,
    SegmentEvents,
    SegmentFailure,
    SegmentFatal,
    SegmentKey,
    SegmentOutput,
    SegmentPlanMismatch,
    SegmentsEmpty,
    SegmentsFailed,
    StepContext,
    StepOutput,
    segment_key_fields,
    segment_key_problem,
    segment_key_sha256,
)


def _round_trip(what: str, value: Mapping[str, object]) -> dict[str, object]:
    """json.dumps → json.loads 를 한 번 거친 값. 안 되면(Decimal·bytes·set·NaN·튜플 열쇠) FlowOutputError."""
    try:
        back: object = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as err:
        raise FlowOutputError(f"{what} 이 JSON 으로 왕복하지 않는다: {err}") from err
    if not isinstance(back, dict):
        raise FlowOutputError(f"{what} 이 JSON 객체가 아니다")
    return cast("dict[str, object]", back)


def _unique_files(what: str, files: tuple[OutputFile, ...]) -> None:
    names = [f.name for f in files]
    if len(set(names)) != len(names):
        raise FlowOutputError(f"{what} 의 파일 이름이 겹친다: {names}")


def _snapshot(output: StepOutput) -> StepOutput:
    """왕복한 다른 객체(files 의 바이트는 그대로). 단계에 넘기는 carried·체크포인트는 늘 새 스냅샷이다 —
    단계가 넘겨받은 산출물을 제자리에서 고쳐도 run_flow 가 쥔 것(FlowRun.steps·completed)은 물들지 않는다."""
    return StepOutput(data=_round_trip("산출물", output.data), files=output.files)


def _not_step_outputs(carried: Mapping[str, object]) -> list[str]:
    """꼴은 StepOutput 이라 적혔어도 실행기가 저장소에서 꺼낸 값일 수 있다."""
    return [name for name, value in carried.items() if not isinstance(value, StepOutput)]


def _final_results(flow: Flow, last: StepOutput) -> tuple[dict[str, object], ...]:
    """끝 산출물 검사: data 는 {"results": [...]} 하나뿐, 결과마다 선언한 schemaVersion(같은 꼴 한 번, 주 꼴 꼭),
    파일은 선언한 output_files 안."""
    if set(last.data) != {"results"}:
        raise FlowOutputError(f"마지막 단계의 data 는 results 하나뿐이어야 한다: {sorted(last.data)}")
    results = last.data["results"]
    if not isinstance(results, list):
        raise FlowOutputError("results 가 목록이 아니다")
    out: list[dict[str, object]] = []
    seen: list[object] = []
    for item in cast("list[object]", results):
        if not isinstance(item, dict):
            raise FlowOutputError("결과가 JSON 객체가 아니다")
        result = cast("dict[str, object]", item)
        shape = result.get("schemaVersion")
        if shape not in flow.result_shapes:
            raise FlowOutputError(f"결과의 schemaVersion {shape!r} 이 선언한 결과 꼴 {flow.result_shapes} 밖이다")
        if shape in seen:
            raise FlowOutputError(f"결과 꼴 {shape} 이 두 번 나왔다")
        seen.append(shape)
        out.append(result)
    if flow.result_shapes[0] not in seen:
        raise FlowOutputError(f"주 결과 꼴 {flow.result_shapes[0]} 이 없다")
    unknown = [f.name for f in last.files if f.name not in flow.output_files]
    if unknown:
        raise FlowOutputError(f"선언하지 않은 출력 파일: {unknown}")
    return tuple(out)


def _octets(value: object) -> int:
    """jsonb 를 글로 적은 크기의 어림(json 기본 구분자 — runs/service/services/runs.py 의 _too_large 꼴)."""
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _no_checkpoint(partial: Mapping[str, object], done: int, total: int) -> None:
    raise FlowOutputError("구획 안에서는 체크포인트를 남기지 않는다(그 구획의 실패)")


class _EventsError:
    """사건 받는 쪽이 낸 예외를 쥔다 — 단계가 삼켜도 run_flow 가 그대로 올린다."""

    def __init__(self) -> None:
        self.error: Exception | None = None

    def call[**P, T](self, deliver: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return deliver(*args, **kwargs)
        except Exception as err:
            self.error = err
            raise


def _planned(step: FanoutStep[Any, Any], segments: object) -> tuple[Segment, ...]:
    """plan 의 반환 검사: 구획 목록, 열쇠 꼴, 겹침, 상한, 입력의 JSON 왕복(왕복한 입력을 실은 새 구획)."""
    if not isinstance(segments, tuple | list):
        raise FlowOutputError(
            f"펼침 단계 {step.name} 의 plan 이 구획 목록을 돌려주지 않았다: {type(segments).__name__}"
        )
    items = cast("tuple[object, ...] | list[object]", segments)
    if len(items) > step.max_segments:
        raise FlowOutputError(f"펼침 단계 {step.name} 의 구획이 {len(items)}개 — 상한 {step.max_segments} 을 넘는다")
    out: list[Segment] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Segment):
            raise FlowOutputError(f"펼침 단계 {step.name} 의 계획에 Segment 가 아닌 값: {type(item).__name__}")
        problem = segment_key_problem(item.key)
        if problem is not None:
            raise FlowOutputError(f"펼침 단계 {step.name}: {problem}")
        sha = segment_key_sha256(item.key)
        if sha in seen:
            raise FlowOutputError(f"펼침 단계 {step.name} 의 구획 열쇠가 겹친다(span {item.key.span!r})")
        seen.add(sha)
        out.append(Segment(key=item.key, input=_round_trip(f"구획 {item.key.span!r} 의 입력", item.input)))
    return tuple(out)


def _fanout_of(flow: Flow, step_name: str) -> FanoutStep[Any, Any]:
    step = flow.fanouts.get(step_name)
    if step is None:
        raise FlowInputError(f"흐름 {flow.id} 에 펼침 단계 {step_name!r} 이 없다")
    return step


def _view(carried: Carried) -> dict[str, StepOutput]:
    wrong = _not_step_outputs(carried)
    if wrong:
        raise FlowInputError(f"넘겨받은 산출물이 StepOutput 이 아니다: {wrong}")
    return {name: _snapshot(output) for name, output in carried.items()}


def _plan_of(step: FanoutStep[Any, Any], inputs: object, view: Carried) -> tuple[Segment, ...]:
    """plan → 꼴 검사. 0개이고 allow_empty=False 면 SegmentsEmpty."""
    segments = _planned(step, step.plan(inputs, view))
    # 계획 0개: allow_empty=False 면 단계 실패(segments_empty). 이어 도는 시도에서 계획이 n → 0 으로 바뀌어도 이 갈래가
    # 먼저 난다(segments_mismatch 가 아니다 — 저장된 계획과 견주는 segments_planned 앞이다)
    if not segments and not step.allow_empty:
        raise SegmentsEmpty(f"펼침 단계 {step.name} 의 계획이 구획 0개다")
    return segments


def _segment_data(
    step: FanoutStep[Any, Any], inputs: object, adapters: object, view: Carried, segment: Segment
) -> dict[str, object]:
    """구획 하나의 run 과 산출 검사(SegmentOutput 꼴·JSON 왕복·SEGMENT_DATA_MAX_OCTETS). 실패는 던진다."""
    ctx = StepContext(resume=None, on_checkpoint=_no_checkpoint)
    produced = cast("object", step.run(inputs, adapters, view, segment, ctx))
    if not isinstance(produced, SegmentOutput):
        raise FlowOutputError(f"구획 {segment.key.span!r} 의 산출이 SegmentOutput 이 아니다")
    data = _round_trip(f"구획 {segment.key.span!r} 의 data", produced.data)
    if _octets(data) > SEGMENT_DATA_MAX_OCTETS:
        raise FlowOutputError(f"구획 {segment.key.span!r} 의 data 가 {SEGMENT_DATA_MAX_OCTETS}바이트를 넘는다")
    return data


def plan_segments(flow: Flow, step_name: str, inputs: object, carried: Carried) -> tuple[Segment, ...]:
    """펼침 단계의 계획(RM1b — 구획 쪽지가 잡은 sha 의 구획을 얻는다). run_flow 의 직렬 펼침과 같은 검사·같은 값
    (carried 는 JSON 왕복한 스냅샷으로 plan 에 간다). 0개이고 allow_empty=False 면 SegmentsEmpty, 꼴이 틀리면
    FlowOutputError. 입력의 꼴이 틀리거나 없는 펼침 단계면 FlowInputError."""
    if not isinstance(inputs, flow.inputs):
        raise FlowInputError(f"흐름 {flow.id} 의 입력이 {flow.inputs.__name__} 가 아니다: {type(inputs).__name__}")
    return _plan_of(_fanout_of(flow, step_name), inputs, _view(carried))


def run_segment(
    flow: Flow, step_name: str, inputs: object, adapters: object, carried: Carried, segment: Segment
) -> SegmentOutput:
    """구획 하나를 돈다(RM1b — 구획 쪽지). 직렬 펼침이 구획마다 하는 것과 같다: 문맥(resume None·체크포인트는
    FlowOutputError)·산출 꼴·JSON 왕복·SEGMENT_DATA_MAX_OCTETS. 실패는 던진다(사건 0 — 기록은 부른 쪽의 일)."""
    if not isinstance(inputs, flow.inputs):
        raise FlowInputError(f"흐름 {flow.id} 의 입력이 {flow.inputs.__name__} 가 아니다: {type(inputs).__name__}")
    if not isinstance(adapters, flow.adapters):
        raise FlowInputError(
            f"흐름 {flow.id} 의 어댑터가 {flow.adapters.__name__} 가 아니다: {type(adapters).__name__}"
        )
    step = _fanout_of(flow, step_name)
    return SegmentOutput(data=_segment_data(step, inputs, adapters, _view(carried), segment))


# 펼침 단계 data {"segments": [e1, e2, …]} 를 json 기본 구분자로 적은 크기 = 껍데기 + 항목 합 + 항목 사이 ", "
_FANOUT_SHELL_OCTETS = len(json.dumps({"segments": []}).encode("utf-8"))
_ITEM_SEPARATOR_OCTETS = len(", ")


class _FanoutSize:
    """펼침 단계 data 의 크기를 항목을 더할 때마다 잰다(635-2 — 넘는 자리에서 단계 실패). 끝 검사와 같은 값."""

    def __init__(self, step: str) -> None:
        self.step = step
        self.octets = _FANOUT_SHELL_OCTETS
        self.items = 0

    def add(self, entry: dict[str, object]) -> None:
        self.octets += _octets(entry) + (_ITEM_SEPARATOR_OCTETS if self.items else 0)
        self.items += 1
        if self.octets > FANOUT_DATA_MAX_OCTETS:
            raise FlowOutputError(f"펼침 단계 {self.step} 의 data 가 {FANOUT_DATA_MAX_OCTETS}바이트를 넘는다")


def _fanout(
    flow: Flow,
    step: FanoutStep[Any, Any],
    inputs: object,
    adapters: object,
    view: Carried,
    *,
    events: FlowEvents,
    segment_events: SegmentEvents,
    ended: Mapping[str, SegmentEnded],
    caught: _EventsError,
    dispatch: SegmentDispatch | None,
) -> StepOutput:
    """펼침 단계 하나를 직렬로 돈다(머리말 ①~④), 또는 끝나지 않은 구획을 dispatch 에 맡긴다(⑤).
    받는 쪽의 예외는 caught 에 쥐고 다시 던진다."""
    flow_id, name = flow.id, step.name
    segments = _plan_of(step, inputs, view)
    keys = tuple(segment.key for segment in segments)
    caught.call(segment_events.segments_planned, flow_id, name, keys)
    shas = [segment_key_sha256(key) for key in keys]
    stray = set(ended) - set(shas)
    if stray:
        caught.error = SegmentPlanMismatch(f"펼침 단계 {step.name} 의 끝난 구획 {len(stray)}개가 이 계획에 없다")
        raise caught.error
    if dispatch is not None:
        _dispatch(step, segments, shas, ended=ended, caught=caught, dispatch=dispatch, flow_id=flow_id)
    total = len(segments)
    finished = sum(1 for sha in shas if sha in ended)
    entries: list[dict[str, object]] = []
    size = _FanoutSize(step.name)
    for segment, sha in zip(segments, shas, strict=True):
        got = ended.get(sha)
        if got is None:
            key = segment.key
            caught.call(segment_events.segment_started, flow_id, name, key)
            try:
                data = _segment_data(step, inputs, adapters, view, segment)
                if caught.error is not None:  # 구획이 받는 쪽의 예외를 삼켰다
                    raise caught.error
            except Exception as err:
                if caught.error is not None:
                    raise caught.error from None
                got = SegmentFailure(error_code=caught.call(segment_events.segment_failed, flow_id, name, key, err))
            else:
                got = SegmentOutput(data=data)
                sent = SegmentOutput(data=_round_trip("구획 산출", data))
                caught.call(segment_events.segment_finished, flow_id, name, key, sent)
            finished += 1
            caught.call(events.step_progress, flow_id, name, finished, total, {})
        if isinstance(got, SegmentFailure) and step.on_failure == "fail_run":
            raise SegmentsFailed(f"펼침 단계 {step.name} 의 구획 {segment.key.span!r} 이 실패했다: {got.error_code}")
        entry = _entry(segment.key, sha, got)
        size.add(entry)
        entries.append(entry)
    data_out: dict[str, object] = {"segments": entries}
    if _octets(data_out) > FANOUT_DATA_MAX_OCTETS:
        raise FlowOutputError(f"펼침 단계 {step.name} 의 data 가 {FANOUT_DATA_MAX_OCTETS}바이트를 넘는다")
    return StepOutput(data=data_out)


def _dispatch(
    step: FanoutStep[Any, Any],
    segments: tuple[Segment, ...],
    shas: list[str],
    *,
    ended: Mapping[str, SegmentEnded],
    caught: _EventsError,
    dispatch: SegmentDispatch,
    flow_id: str,
) -> None:
    """맡김 갈래(RM1b ⑤): fail_run 이고 끝난 것에 실패가 있으면 SegmentsFailed(계획 차례 첫 실패) · 끝나지 않은 것이
    있으면 dispatch(돌아오지 않는다 — 돌아오면 FlowOutputError) · 다 끝났으면 돌아가 모은다(구획 run 0회)."""
    if step.on_failure == "fail_run":
        for segment, sha in zip(segments, shas, strict=True):
            got = ended.get(sha)
            if isinstance(got, SegmentFailure):
                raise SegmentsFailed(
                    f"펼침 단계 {step.name} 의 구획 {segment.key.span!r} 이 실패했다: {got.error_code}"
                )
    pending = tuple(segment.key for segment, sha in zip(segments, shas, strict=True) if sha not in ended)
    if not pending:
        return
    returned: object = caught.call(dispatch.dispatch, flow_id, step.name, pending)
    raise FlowOutputError(f"구획 맡김(dispatch)이 돌아왔다(돌아오지 않아야 한다): {type(returned).__name__}")


def _entry(key: SegmentKey, sha: str, got: SegmentEnded) -> dict[str, object]:
    return {
        "key": segment_key_fields(key),
        "keySha256": sha,
        "status": "done" if isinstance(got, SegmentOutput) else "failed",
        "data": got.data if isinstance(got, SegmentOutput) else None,
        "errorCode": got.error_code if isinstance(got, SegmentFailure) else None,
    }


class _Progress:
    """한 단계 안의 checkpoint 를 받는다: 마지막 부분 산출물, 사건 받는 쪽이 낸 예외."""

    def __init__(self, flow_id: str, step: str, events: FlowEvents) -> None:
        self.flow_id = flow_id
        self.step = step
        self.events = events
        self.partial: dict[str, object] | None = None
        self.events_error: Exception | None = None

    def __call__(self, partial: Mapping[str, object], done: int, total: int) -> None:
        kept = _round_trip(f"단계 {self.step} 의 부분 산출물", partial)
        self.partial = kept
        try:
            self.events.step_progress(self.flow_id, self.step, done, total, kept)
        except Exception as err:
            self.events_error = err  # 단계가 삼켜도 run_flow 가 그대로 올린다
            raise


def run_flow(
    flow: Flow,
    inputs: object,
    adapters: object,
    *,
    start_at: str | None = None,
    carried: Carried | None = None,
    resume: Mapping[str, object] | None = None,
    events: FlowEvents = NO_EVENTS,
    segment_events: SegmentEvents = NO_SEGMENT_EVENTS,
    segments_done: Mapping[str, Mapping[str, SegmentEnded]] | None = None,
    dispatch: SegmentDispatch | None = None,
) -> FlowRun:
    """흐름을 돌린다. 입구의 잘못은 FlowInputError(단계 0·사건 0), 단계의 실패는 FlowStepFailed.

    segments_done  펼침 단계 이름 → 구획 열쇠 sha → 그 실행 안에서 끝난 구획(done·failed). 장벽 흐름은 쓰지 않는다.
    dispatch       None 이면 펼침을 직렬로 돈다(RM1a). 주면 끝나지 않은 구획을 거기 맡긴다(RM1b — 머리말 ⑤).
    """
    if not isinstance(inputs, flow.inputs):
        raise FlowInputError(f"흐름 {flow.id} 의 입력이 {flow.inputs.__name__} 가 아니다: {type(inputs).__name__}")
    if not isinstance(adapters, flow.adapters):
        raise FlowInputError(
            f"흐름 {flow.id} 의 어댑터가 {flow.adapters.__name__} 가 아니다: {type(adapters).__name__}"
        )
    if start_at is None:
        if resume is not None:
            raise FlowInputError("resume 은 start_at 의 단계에만 간다(start_at 이 없다)")
        first = 0
    elif start_at in flow.steps:
        first = flow.steps.index(start_at)
    else:
        raise FlowInputError(f"흐름 {flow.id} 에 단계 {start_at!r} 이 없다: {flow.steps}")
    given = carried or {}
    wrong = _not_step_outputs(given)
    if wrong:
        raise FlowInputError(f"넘겨받은 산출물이 StepOutput 이 아니다: {wrong}")
    missing = [name for name in flow.steps[:first] if name not in given]
    if missing:
        raise FlowInputError(f"단계 {start_at} 앞 단계의 산출물이 모자라다: {missing}")
    try:
        done: dict[str, StepOutput] = {
            name: StepOutput(
                data=_round_trip(f"넘겨받은 단계 {name} 의 data", given[name].data), files=given[name].files
            )
            for name in flow.steps[:first]
        }
        resumed = None if resume is None else _round_trip("resume", resume)
    except FlowOutputError as err:
        raise FlowInputError(str(err)) from err
    ended_by_step = segments_done or {}
    unknown = [name for name in ended_by_step if name not in flow.fanouts]
    if unknown:
        raise FlowInputError(f"segments_done 의 단계가 펼침 단계가 아니다: {unknown}")

    last = flow.steps[-1]
    results: tuple[dict[str, object], ...] = ()
    for name in flow.steps[first:]:
        events.step_started(flow.id, name)
        progress = _Progress(flow.id, name, events)
        caught = _EventsError()
        ctx = StepContext(resume=resumed if name == start_at else None, on_checkpoint=progress)
        try:
            view = {step: _snapshot(output) for step, output in done.items()}
            fanout = flow.fanouts.get(name)
            if fanout is None:
                out = flow.run_step(name, inputs, adapters, view, ctx)
            else:
                out = _fanout(
                    flow,
                    fanout,
                    inputs,
                    adapters,
                    view,
                    events=events,
                    segment_events=segment_events,
                    ended=ended_by_step.get(name, {}),
                    caught=caught,
                    dispatch=dispatch,
                )
            if progress.events_error is not None:  # 단계가 사건의 예외를 삼켰다
                raise progress.events_error
            _unique_files(f"단계 {name} 의 산출물", out.files)
            kept = StepOutput(data=_round_trip(f"단계 {name} 의 data", out.data), files=out.files)
            if name == last:
                results = _final_results(flow, kept)
                for check in flow.result_checks:
                    try:
                        check(results)
                    except Exception as err:
                        raise FlowOutputError(f"끝 결과 검사가 거절했다: {type(err).__name__}: {err}") from err
        except Exception as err:
            if progress.events_error is not None:
                raise progress.events_error from None
            if isinstance(caught.error, SegmentFatal):  # 635-1: 구획의 치명 실패는 그 단계의 실패로 접는다
                cause = caught.error.cause
                events.step_failed(flow.id, name, f"{type(cause).__name__}: {cause}")
                raise FlowStepFailed(name, completed=dict(done), partial=progress.partial) from cause
            if caught.error is not None:
                raise caught.error from None
            events.step_failed(flow.id, name, f"{type(err).__name__}: {err}")
            raise FlowStepFailed(name, completed=dict(done), partial=progress.partial) from err
        done[name] = kept
        events.step_finished(flow.id, name, _snapshot(kept))
    return FlowRun(steps=done, output=FlowOutput(results=results, files=done[last].files))
