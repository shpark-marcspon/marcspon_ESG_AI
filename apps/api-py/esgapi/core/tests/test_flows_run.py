"""흐름 실행(core/flows/run.py): 단계의 차례, 단계 k 부터 이어 돌기, 단계 안에서 이어 돌기, 사건, 끝 산출물 검사.

업무 모듈을 import 하지 않는다(계약 가). 가짜 흐름 둘: 단계 하나 흐름과 그린워싱 꼴 흐름(문서 하나 입력 · 단계 여섯
extract → index → judge → wordcount → locate → report · 위치 없는 항목 · 엑셀 출력 파일 하나). 이름은 예다 —
진짜 그린워싱 흐름은 그 트랙이 짓는다. 어댑터는 전부 가짜이고 부른 횟수를 센다(실제 LLM 0).
"""

import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import cast

import pytest

from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import (
    Carried,
    Flow,
    FlowInputError,
    FlowOutputError,
    FlowStep,
    FlowStepFailed,
    OutputFile,
    StepContext,
    StepOutput,
)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ── 사건을 받아 적는 가짜 ─────────────────────────────────────────────


class Recorder:
    def __init__(self) -> None:
        self.seen: list[tuple[object, ...]] = []

    def step_started(self, flow_id: str, step: str) -> None:
        self.seen.append(("started", step))

    def step_finished(self, flow_id: str, step: str, output: StepOutput) -> None:
        self.seen.append(("finished", step, output))

    def step_failed(self, flow_id: str, step: str, reason: str) -> None:
        self.seen.append(("failed", step, reason))

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        self.seen.append(("progress", step, done, total))

    def kinds(self) -> list[tuple[object, object]]:
        return [(e[0], e[1]) for e in self.seen]

    def finished(self) -> dict[str, StepOutput]:
        return {cast("str", e[1]): cast("StepOutput", e[2]) for e in self.seen if e[0] == "finished"}


# ── 단계 하나 흐름 ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True, kw_only=True)
class OneInputs:
    data: dict[str, object]
    files: tuple[OutputFile, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class OneAdapters:
    calls: list[str] = field(default_factory=list[str])


def _give_back(inputs: OneInputs, adapters: OneAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    adapters.calls.append("only")
    return StepOutput(data=inputs.data, files=inputs.files)


ONE: Flow = make_flow(
    module="x.one",
    id="one.flow@1",
    input_shape="one.input@1",
    inputs=OneInputs,
    adapters=OneAdapters,
    result_shapes=("one.result@1", "one.extra@1"),
    output_files=("out.xlsx",),
    steps=(FlowStep(name="only", run=_give_back),),
)


def test_a_one_step_flow() -> None:
    events = Recorder()
    run = run_flow(
        ONE, OneInputs(data={"results": [{"schemaVersion": "one.result@1", "n": 1}]}), OneAdapters(), events=events
    )
    assert events.kinds() == [("started", "only"), ("finished", "only")]
    assert run.output.results == ({"schemaVersion": "one.result@1", "n": 1},)
    assert run.output.files == ()
    assert list(run.steps) == ["only"]


# ── 그린워싱 꼴 흐름 (가짜) ────────────────────────────────────────────


@dataclass(frozen=True, slots=True, kw_only=True)
class GreenwashOptions:
    dry_run: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class GreenwashInputs:
    content: bytes
    media_type: str
    options: GreenwashOptions = GreenwashOptions()


class FakePdfText:
    """글자 추출: 바이트 → 쪽마다의 글. 문서의 쪽은 줄로 가른다."""

    def __init__(self) -> None:
        self.calls = 0

    def pages(self, content: bytes) -> list[str]:
        self.calls += 1
        return content.decode().split("\n")


class FakeCoordinates:
    """좌표: 글자 추출과 따로. 쪽 셋째마다 못 찾는다(None)."""

    def __init__(self) -> None:
        self.calls = 0

    def find(self, page: int, phrase: str) -> dict[str, object] | None:
        self.calls += 1
        return None if page % 3 == 0 else {"page": page, "x": 10 * page, "y": 20}


class FakeEmbedding:
    """임베딩 포트의 자리(백엔드 L1 이 짓기 전). 글 → 벡터 둘."""

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, text: str) -> tuple[float, float]:
        self.calls += 1
        return (float(len(text)), 0.5)


class FakeLlm:
    """판정: 쪽마다 한 번. fail_on 쪽에서 예외. 「친환경」이 든 쪽에서 그 낱말을 문구로 낸다."""

    def __init__(self, fail_on: int | None = None) -> None:
        self.fail_on = fail_on
        self.pages: list[int] = []

    def judge(self, page: int, text: str) -> str | None:
        if page == self.fail_on:
            raise RuntimeError(f"쪽 {page} 에서 공급사가 끊겼다")
        self.pages.append(page)
        return "친환경" if "친환경" in text else None


class FakeTokens:
    def count(self, text: str) -> int:
        return len(text.split())


@dataclass(frozen=True, slots=True, kw_only=True)
class GreenwashAdapters:
    llm: FakeLlm
    pdf_text: FakePdfText
    coordinates: FakeCoordinates
    embedding: FakeEmbedding
    tokens: FakeTokens | None = None


def _saw(carried: Carried) -> list[str]:
    return sorted(carried)


def _pages(carried: Carried) -> list[str]:
    return cast("list[str]", carried["extract"].data["pages"])


def _extract(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"saw": _saw(carried), "pages": adapters.pdf_text.pages(inputs.content)})


def _index(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    vectors = [adapters.embedding.embed(text) for text in _pages(carried)]
    packed = b"".join(struct.pack("<2d", *v) for v in vectors)
    return StepOutput(
        data={"saw": _saw(carried), "count": len(vectors)},
        files=(OutputFile(name="index.vectors", media_type="application/octet-stream", content=packed),),
    )


def _judge(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    pages = _pages(carried)
    judged = [] if ctx.resume is None else list(cast("list[dict[str, object]]", ctx.resume["pages"]))
    assert len(carried["index"].files[0].content) == 16 * len(pages)  # 넘겨받은 파일의 바이트
    for number in range(len(judged) + 1, len(pages) + 1):
        judged.append({"page": number, "phrase": adapters.llm.judge(number, pages[number - 1])})
        ctx.checkpoint({"pages": judged}, done=number, total=len(pages))
    claims = [j for j in judged if j["phrase"] is not None]
    return StepOutput(data={"saw": _saw(carried), "claims": claims})


def _wordcount(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    pages = _pages(carried)
    tokens = None if adapters.tokens is None else sum(adapters.tokens.count(text) for text in pages)  # 선택 어댑터
    return StepOutput(data={"saw": _saw(carried), "words": sum(len(text.split()) for text in pages), "tokens": tokens})


def _locate(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    claims = cast("list[dict[str, object]]", carried["judge"].data["claims"])
    items = [
        {**claim, "position": adapters.coordinates.find(cast("int", claim["page"]), cast("str", claim["phrase"]))}
        for claim in claims
    ]
    return StepOutput(data={"saw": _saw(carried), "items": items})


def _report(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    items = carried["locate"].data["items"]
    result = {
        "schemaVersion": "greenwash.result@1",
        "dryRun": inputs.options.dry_run,
        "words": carried["wordcount"].data["words"],
        "items": items,
        "report": {"file": "greenwash-report.xlsx"},
    }
    sheet = json.dumps(items, ensure_ascii=False).encode()
    return StepOutput(
        data={"results": [result]},
        files=(OutputFile(name="greenwash-report.xlsx", media_type=XLSX, content=sheet),),
    )


GREENWASH: Flow = make_flow(
    module="greenwash",
    id="greenwash.colab@E0",
    input_shape="greenwash.document@1",
    inputs=GreenwashInputs,
    adapters=GreenwashAdapters,
    result_shapes=("greenwash.result@1",),
    output_files=("greenwash-report.xlsx",),
    steps=(
        FlowStep(name="extract", run=_extract),
        FlowStep(name="index", run=_index),
        FlowStep(name="judge", run=_judge),
        FlowStep(name="wordcount", run=_wordcount),
        FlowStep(name="locate", run=_locate),
        FlowStep(name="report", run=_report),
    ),
)
STEPS = ("extract", "index", "judge", "wordcount", "locate", "report")


def document(pages: int = 6) -> GreenwashInputs:
    text = "\n".join(f"쪽 {n} 우리 제품은 {'친환경' if n % 2 == 0 else '튼튼'} 입니다" for n in range(1, pages + 1))
    return GreenwashInputs(content=text.encode(), media_type="application/pdf", options=GreenwashOptions(dry_run=True))


def adapters(fail_on: int | None = None, tokens: FakeTokens | None = None) -> GreenwashAdapters:
    return GreenwashAdapters(
        llm=FakeLlm(fail_on),
        pdf_text=FakePdfText(),
        coordinates=FakeCoordinates(),
        embedding=FakeEmbedding(),
        tokens=tokens,
    )


def stored(outputs: Mapping[str, StepOutput], *names: str) -> dict[str, StepOutput]:
    """저장소에 두었다 꺼낸 것처럼: data 는 json.dumps → json.loads, files 는 바이트 그대로."""
    return {
        name: StepOutput(data=json.loads(json.dumps(outputs[name].data)), files=outputs[name].files) for name in names
    }


def test_a_greenwash_like_flow() -> None:
    events = Recorder()
    run = run_flow(GREENWASH, document(), adapters(tokens=FakeTokens()), events=events)
    started_finished = [k for k in events.kinds() if k[0] != "progress"]
    assert started_finished == [(kind, step) for step in STEPS for kind in ("started", "finished")]
    assert len(started_finished) == 12
    judge_at = events.kinds().index(("started", "judge"))
    assert events.kinds()[judge_at + 1 : judge_at + 7] == [("progress", "judge")] * 6
    for n, step in enumerate(STEPS):  # 각 단계가 앞 단계 전부를 carried 로 받았다
        assert run.steps[step].data.get("saw", sorted(STEPS[:n])) == sorted(STEPS[:n])
    assert GREENWASH.adapter_names == ("llm", "pdf_text", "coordinates", "embedding", "tokens")
    assert GREENWASH.optional_adapters == ("tokens",)
    assert run.steps["wordcount"].data["tokens"] == 36

    (result,) = run.output.results
    assert next(iter(result)) == "schemaVersion"
    assert result["dryRun"] is True
    assert result["report"] == {"file": "greenwash-report.xlsx"}
    items = cast("list[dict[str, object]]", result["items"])
    assert [i["page"] for i in items] == [2, 4, 6]
    assert [i["position"] for i in items] == [{"page": 2, "x": 20, "y": 20}, {"page": 4, "x": 40, "y": 20}, None]
    assert [f.name for f in run.output.files] == ["greenwash-report.xlsx"]
    assert run.output.files[0].media_type == XLSX
    assert run.steps["index"].files[0].name == "index.vectors"  # 가운데 단계의 파일은 체크포인트로만


def test_an_optional_adapter_can_be_left_out() -> None:
    run = run_flow(GREENWASH, document(), adapters())
    assert run.steps["wordcount"].data["tokens"] is None


def test_resume_from_a_step() -> None:
    events, first = Recorder(), adapters()
    full = run_flow(GREENWASH, document(), first, events=events)
    saved = stored(events.finished(), "extract", "index")

    again = adapters()
    resumed = run_flow(GREENWASH, document(), again, start_at="judge", carried=saved)
    assert (again.pdf_text.calls, again.embedding.calls) == (0, 0)  # extract·index 는 불리지 않았다
    assert again.llm.pages == [1, 2, 3, 4, 5, 6]
    assert resumed.output == full.output
    assert resumed.steps["index"].files == full.steps["index"].files

    short, events = adapters(), Recorder()
    with pytest.raises(FlowInputError, match="모자라다"):
        run_flow(GREENWASH, document(), short, start_at="judge", carried={"extract": saved["extract"]}, events=events)
    assert (short.pdf_text.calls, short.embedding.calls, short.llm.pages, events.seen) == (0, 0, [], [])

    stale = {**saved, "judge": StepOutput(data={"claims": "낡은 것"})}
    rebuilt = adapters()
    assert run_flow(GREENWASH, document(), rebuilt, start_at="judge", carried=stale).output == full.output
    assert rebuilt.llm.pages == [1, 2, 3, 4, 5, 6]  # carried 에 든 judge 는 버리고 다시 지었다

    with pytest.raises(FlowInputError, match="start_at"):
        run_flow(GREENWASH, document(), adapters(), resume={"pages": []})


def test_a_failing_step() -> None:
    events, broken = Recorder(), adapters(fail_on=1)
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(GREENWASH, document(), broken, events=events)
    assert events.kinds() == [
        ("started", "extract"),
        ("finished", "extract"),
        ("started", "index"),
        ("finished", "index"),
        ("started", "judge"),
        ("failed", "judge"),
    ]
    assert events.seen[-1] == ("failed", "judge", "RuntimeError: 쪽 1 에서 공급사가 끊겼다")
    finished = events.finished()
    assert finished["extract"].data["pages"] == _pages(finished)
    assert finished["index"].files[0].name == "index.vectors"
    failed = caught.value
    assert failed.step == "judge"
    assert set(failed.completed) == {"extract", "index"}
    assert failed.completed == finished
    assert failed.partial is None  # checkpoint 를 한 번도 안 불렀다
    assert isinstance(failed.__cause__, RuntimeError)

    fixed = adapters()
    run = run_flow(GREENWASH, document(), fixed, start_at="judge", carried=failed.completed)
    assert (fixed.pdf_text.calls, fixed.embedding.calls) == (0, 0)
    assert run.output == run_flow(GREENWASH, document(), adapters()).output


def test_the_entry_checks_what_it_is_given() -> None:
    probe = OneAdapters()
    cases: list[tuple[object, object, str | None]] = [
        (OneAdapters(), probe, None),  # 입력 꼴이 틀림
        (OneInputs(data={}), OneInputs(data={}), None),  # 어댑터 꼴이 틀림
        (OneInputs(data={}), probe, "nothing"),  # 없는 단계
    ]
    for inputs, given_adapters, start_at in cases:
        events = Recorder()
        with pytest.raises(FlowInputError):
            run_flow(ONE, inputs, given_adapters, start_at=start_at, events=events)
        assert events.seen == []
    assert probe.calls == []  # 단계 함수는 안 불렸다

    for bad in (Decimal("1.5"), b"bytes", float("nan")):
        events = Recorder()
        with pytest.raises(FlowStepFailed) as caught:
            run_flow(
                ONE,
                OneInputs(data={"results": [{"schemaVersion": "one.result@1", "v": bad}]}),
                OneAdapters(),
                events=events,
            )
        assert isinstance(caught.value.__cause__, FlowOutputError)
        assert events.kinds() == [("started", "only"), ("failed", "only")]

    twice = (
        OutputFile(name="out.xlsx", media_type=XLSX, content=b"1"),
        OutputFile(name="out.xlsx", media_type=XLSX, content=b"2"),
    )
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(ONE, OneInputs(data={"results": [{"schemaVersion": "one.result@1"}]}, files=twice), OneAdapters())
    assert isinstance(caught.value.__cause__, FlowOutputError)


def _result(shape: str) -> dict[str, object]:
    return {"schemaVersion": shape}


@pytest.mark.parametrize(
    ("what", "data", "files"),
    [
        ("results 밖 키", {"results": [_result("one.result@1")], "more": 1}, ()),
        ("results 가 목록 아님", {"results": _result("one.result@1")}, ()),
        ("schemaVersion 없음", {"results": [{"n": 1}]}, ()),
        ("선언 밖 꼴", {"results": [_result("one.result@1"), _result("one.other@1")]}, ()),
        ("같은 꼴 둘", {"results": [_result("one.result@1"), _result("one.result@1")]}, ()),
        ("주 꼴 없음", {"results": [_result("one.extra@1")]}, ()),
        (
            "선언 밖 출력 파일",
            {"results": [_result("one.result@1")]},
            (OutputFile(name="other.xlsx", media_type=XLSX, content=b""),),
        ),
    ],
)
def test_the_final_output_is_checked(what: str, data: dict[str, object], files: tuple[OutputFile, ...]) -> None:
    events = Recorder()
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(ONE, OneInputs(data=data, files=files), OneAdapters(), events=events)
    assert isinstance(caught.value.__cause__, FlowOutputError)
    assert events.kinds() == [("started", "only"), ("failed", "only")]


def test_the_primary_shape_alone_is_enough() -> None:
    xlsx = OutputFile(name="out.xlsx", media_type=XLSX, content=b"x")
    run = run_flow(ONE, OneInputs(data={"results": [_result("one.result@1")]}, files=(xlsx,)), OneAdapters())
    assert run.output.results == (_result("one.result@1"),)
    assert run.output.files == (xlsx,)
    both: dict[str, object] = {"results": [_result("one.extra@1"), _result("one.result@1")]}
    assert len(run_flow(ONE, OneInputs(data=both), OneAdapters()).output.results) == 2


class Boom(Exception):
    pass


class RaisingOn(Recorder):
    def __init__(self, kind: str) -> None:
        super().__init__()
        self.kind = kind

    def step_started(self, flow_id: str, step: str) -> None:
        if self.kind == "started":
            raise Boom(self.kind)

    def step_finished(self, flow_id: str, step: str, output: StepOutput) -> None:
        if self.kind == "finished":
            raise Boom(self.kind)

    def step_failed(self, flow_id: str, step: str, reason: str) -> None:
        if self.kind == "failed":
            raise Boom(self.kind)

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        if self.kind == "progress":
            raise Boom(self.kind)


def _swallowing(inputs: OneInputs, adapters: OneAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    try:
        ctx.checkpoint({"n": 1}, done=1, total=1)
    except Exception:  # 단계가 사건의 예외를 삼켜도 run_flow 가 올리는지를 잰다
        adapters.calls.append("swallowed")
    return StepOutput(data=inputs.data)


SWALLOWING: Flow = make_flow(
    module="x.one",
    id="one.swallow@1",
    input_shape="one.input@1",
    inputs=OneInputs,
    adapters=OneAdapters,
    result_shapes=("one.result@1",),
    steps=(FlowStep(name="only", run=_swallowing),),
)


@pytest.mark.parametrize("kind", ["started", "finished", "failed", "progress"])
def test_events_errors_are_not_swallowed(kind: str) -> None:
    good = OneInputs(data={"results": [_result("one.result@1")]})
    with pytest.raises(Boom, match=kind):
        if kind == "failed":
            run_flow(ONE, OneInputs(data={"results": []}), OneAdapters(), events=RaisingOn(kind))
        elif kind == "progress":
            probe = OneAdapters()
            try:
                run_flow(SWALLOWING, good, probe, events=RaisingOn(kind))
            finally:
                assert probe.calls == ["swallowed"]
        else:
            run_flow(ONE, good, OneAdapters(), events=RaisingOn(kind))


def _odd_data(inputs: OneInputs, adapters: OneAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"pair": (1, 2), "byNumber": {1: "a", 2: "b"}})


def _show_what_came(inputs: OneInputs, adapters: OneAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    came = carried["odd"].data
    adapters.calls.append(repr(came))
    return StepOutput(data={"results": [{"schemaVersion": "one.result@1", "came": came}]})


ODD: Flow = make_flow(
    module="x.one",
    id="one.odd@1",
    input_shape="one.input@1",
    inputs=OneInputs,
    adapters=OneAdapters,
    result_shapes=("one.result@1",),
    steps=(FlowStep(name="odd", run=_odd_data), FlowStep(name="show", run=_show_what_came)),
)


def test_step_data_is_what_a_checkpoint_gives_back() -> None:
    events, whole = Recorder(), OneAdapters()
    full = run_flow(ODD, OneInputs(data={}), whole, events=events)
    assert whole.calls == [repr({"pair": [1, 2], "byNumber": {"1": "a", "2": "b"}})]  # 목록·글자 열쇠

    resumed_with = OneAdapters()
    resumed = run_flow(ODD, OneInputs(data={}), resumed_with, start_at="show", carried=stored(events.finished(), "odd"))
    assert resumed_with.calls == whole.calls
    assert resumed.output == full.output
    assert events.finished()["odd"].data == {"pair": [1, 2], "byNumber": {"1": "a", "2": "b"}}  # 사건에도 왕복한 값
    assert full.steps["odd"] == events.finished()["odd"]


def test_resume_inside_a_step() -> None:
    clean = run_flow(GREENWASH, document(40), adapters())

    events, broken = Recorder(), adapters(fail_on=30)
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(GREENWASH, document(40), broken, events=events)
    progress = [e for e in events.seen if e[0] == "progress"]
    assert progress[-1] == ("progress", "judge", 29, 40)
    assert len(progress) == 29
    failed = caught.value
    judged = cast("list[dict[str, object]]", cast("Mapping[str, object]", failed.partial)["pages"])
    assert [j["page"] for j in judged] == list(range(1, 30))
    assert judged == [{"page": n, "phrase": "친환경" if n % 2 == 0 else None} for n in range(1, 30)]

    partial = json.loads(json.dumps(failed.partial))
    again = adapters()
    run = run_flow(
        GREENWASH,
        document(40),
        again,
        start_at="judge",
        carried=stored(failed.completed, "extract", "index"),
        resume=partial,
    )
    assert again.llm.pages == list(range(30, 41))  # 11번, 앞 29쪽은 0번
    assert len(again.llm.pages) == 11
    assert run.output == clean.output


def _bad_checkpoint(inputs: OneInputs, adapters: OneAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    ctx.checkpoint({"n": Decimal("1")}, done=1, total=2)
    return StepOutput(data=inputs.data)


def test_a_checkpoint_that_does_not_round_trip_fails_the_step() -> None:
    flow = make_flow(
        module="x.one",
        id="one.bad@1",
        input_shape="one.input@1",
        inputs=OneInputs,
        adapters=OneAdapters,
        result_shapes=("one.result@1",),
        steps=(FlowStep(name="only", run=_bad_checkpoint),),
    )
    events = Recorder()
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(flow, OneInputs(data={"results": [_result("one.result@1")]}), OneAdapters(), events=events)
    assert isinstance(caught.value.__cause__, FlowOutputError)
    assert caught.value.partial is None
    assert events.kinds() == [("started", "only"), ("failed", "only")]


def test_progress_events() -> None:
    events = Recorder()
    run_flow(GREENWASH, document(5), adapters(), events=events)
    kinds = events.kinds()
    start, end = kinds.index(("started", "judge")), kinds.index(("finished", "judge"))
    progress_at = [n for n, k in enumerate(kinds) if k[0] == "progress"]
    assert progress_at == list(range(start + 1, end))
    assert [(e[2], e[3]) for e in events.seen if e[0] == "progress"] == [(n, 5) for n in range(1, 6)]

    one = Recorder()
    run_flow(ONE, OneInputs(data={"results": [_result("one.result@1")]}), OneAdapters(), events=one)
    assert [k for k in one.kinds() if k[0] == "progress"] == []


def test_a_step_context_is_built_from_resume_alone() -> None:
    """한 장의 글자대로 StepContext(resume=…) 만으로 지어진다 — 단계 함수 하나를 run_flow 없이 부를 수 있다."""
    ctx = StepContext(resume=None)
    ctx.checkpoint({"pages": []}, done=0, total=1)
    probe = OneAdapters()
    out = _give_back(OneInputs(data={"n": 1}), probe, {}, StepContext(resume={"pages": [1]}))
    assert (out.data, probe.calls) == ({"n": 1}, ["only"])


def _first(inputs: OneInputs, adapters: OneAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"x": "처음", "list": [1]})


def _meddling(inputs: OneInputs, adapters: OneAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    came = carried["a"].data
    seen = {"x": came["x"], "list": list(cast("list[int]", came["list"]))}
    came["x"] = "고침"  # 뒤 단계가 넘겨받은 산출물을 제자리에서 고친다
    cast("list[int]", came["list"]).append(2)
    return StepOutput(data={"results": [{"schemaVersion": "one.result@1", "seen": seen}]})


MEDDLING: Flow = make_flow(
    module="x.one",
    id="one.meddle@1",
    input_shape="one.input@1",
    inputs=OneInputs,
    adapters=OneAdapters,
    result_shapes=("one.result@1",),
    steps=(FlowStep(name="a", run=_first), FlowStep(name="b", run=_meddling)),
)


def test_a_later_step_cannot_change_a_checkpoint() -> None:
    events = Recorder()
    full = run_flow(MEDDLING, OneInputs(data={}), OneAdapters(), events=events)
    assert events.finished()["a"].data == {"x": "처음", "list": [1]}  # 체크포인트는 물들지 않았다
    resumed = run_flow(
        MEDDLING, OneInputs(data={}), OneAdapters(), start_at="b", carried=stored(events.finished(), "a")
    )
    assert resumed.output == full.output


def test_carried_must_hold_step_outputs() -> None:
    events, probe = Recorder(), OneAdapters()
    with pytest.raises(FlowInputError, match="StepOutput"):
        run_flow(
            ODD,
            OneInputs(data={}),
            probe,
            start_at="show",
            carried=cast("Carried", {"odd": {"pair": [1, 2]}}),
            events=events,
        )
    assert (events.seen, probe.calls) == ([], [])


def _meddle_then_fail(inputs: OneInputs, adapters: OneAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    carried["a"].data["x"] = "고침"
    raise RuntimeError("고친 뒤 실패")


def test_a_later_step_cannot_change_what_failure_hands_back() -> None:
    flow = make_flow(
        module="x.one",
        id="one.meddle-fail@1",
        input_shape="one.input@1",
        inputs=OneInputs,
        adapters=OneAdapters,
        result_shapes=("one.result@1",),
        steps=(FlowStep(name="a", run=_first), FlowStep(name="b", run=_meddle_then_fail)),
    )
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(flow, OneInputs(data={}), OneAdapters())
    assert caught.value.completed["a"].data == {"x": "처음", "list": [1]}  # 이어 돌기의 재료가 물들지 않았다
    resumed = run_flow(MEDDLING, OneInputs(data={}), OneAdapters(), start_at="b", carried=caught.value.completed)
    assert resumed.output == run_flow(MEDDLING, OneInputs(data={}), OneAdapters()).output


def test_a_later_step_cannot_change_the_run_steps() -> None:
    run = run_flow(MEDDLING, OneInputs(data={}), OneAdapters())
    assert run.steps["a"].data == {"x": "처음", "list": [1]}
