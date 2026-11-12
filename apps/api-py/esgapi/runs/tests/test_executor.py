# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실행기(`runs.execute`)를 진짜 DB 로 잰다. 업무 층: 저장소는 가짜, 흐름은 시험 안의 가짜, 태스크는
**함수를 직접 부른다**.

가짜 흐름 `probe.three@1`(단계 셋): extract(단계 파일 하나) → judge(항목마다 체크포인트 — 이어 돌기) →
report(결과 꼴 둘 · 출력 파일 하나). 단계의 동작은 Script 의 손잡이로 바꾼다(실패·소프트 제한·마감·LLM 호출).
흐름과 끼움은 시험의 레지스트리에 단다(tasks.REGISTRY·tasks.BINDINGS 를 바꿔 끼움 — 프로세스의 것을 물들이지 않는다).
★ 브로커도 워커도 없다. 「다시 넣기」는 가짜 self 의 retry 가 받는다.
★ 무효 조건: 이 층은 연결이 하나다(주인 역할, 테스트마다 되돌린다). 트랜잭션의 커밋·두 워커의 경합은 재지 않는다.
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import contextlib
import hashlib
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any, cast

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.core.management import call_command
from django.db import OperationalError, transaction

from esgapi.config.env import BrokerSettings, JobSettings, LlmSettings
from esgapi.core.flows import binding as flow_ports  # G2c2: 둘째 꼴 RunFactsBinding
from esgapi.core.flows.binding import BindingRegistry, DocumentInput, RunContext
from esgapi.core.flows.registry import FlowRegistry, make_flow
from esgapi.core.flows.types import Carried, FlowStep, OutputFile, StepContext, StepOutput
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.errors import LiveSetupError
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.setup import build_client
from esgapi.core.llm.sink_db import DbSink
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Tags
from esgapi.core.models import DocumentRow, LlmCallLogRow
from esgapi.core.resources import queue as hooks
from esgapi.core.resources.ports.storage import GetResult, StorageDenied, StorageUnavailable
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs import context, tasks
from esgapi.runs.calc.errors import RUN_ERROR_MESSAGES
from esgapi.runs.calc.keys import file_key
from esgapi.runs.models import RunFileRow, RunResultRow, RunRow, RunStepRow
from esgapi.runs.service.selectors import runs as selectors
from esgapi.runs.service.services import runs as services
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7 (synthetic bytes for the runner)"
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
SOFT_S = 240  # 마감 = 시도 시작 + 240 − 60
LATE = 10_000.0  # 마감을 확실히 지난 monotonic 값의 몫


@dataclass
class Script:
    """가짜 흐름의 손잡이와 기록."""

    total: int = 4  # judge 의 항목 수
    on_extract: Callable[[], None] | None = None
    before_item: Callable[[int, "ProbeAdapters"], None] | None = None  # judge 의 항목 i 를 하기 전
    repeat_resume: bool = False  # judge 가 받은 부분을 같은 done 으로 다시 체크포인트한다(진행 아님 — F4)
    big_result: bool = False
    checkpoint_calls: int = 0  # judge 가 ctx.checkpoint 를 부른 수(시험 전체)
    items_done: list[int] = field(default_factory=list[int])
    resumed: list[Mapping[str, object] | None] = field(default_factory=list[Mapping[str, object] | None])
    finished_steps: list[str] = field(default_factory=list[str])
    llm_results: list[str] = field(default_factory=list[str])
    carried_keys: list[list[str]] = field(default_factory=list[list[str]])  # judge 가 받은 extract.data 의 열쇠 차례


@dataclass(frozen=True)
class ProbeInputs:
    document: DocumentInput
    options: dict[str, object]


@dataclass(frozen=True)
class ProbeAdapters:
    script: Script
    ctx: RunContext


def extract(inputs: ProbeInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    if adapters.script.on_extract is not None:
        adapters.script.on_extract()
    adapters.script.finished_steps.append("extract")
    return StepOutput(
        data={"size": len(inputs.document.content), "name": inputs.document.file_name},
        files=(OutputFile(name="pages.json", media_type="application/json", content=b"[1, 2]"),),
    )


def judge(inputs: ProbeInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    script = adapters.script
    script.resumed.append(ctx.resume)
    script.carried_keys.append(list(carried["extract"].data))
    kept = [] if ctx.resume is None else cast("list[object]", ctx.resume["items"])
    items = [int(str(i)) for i in kept]
    start = len(items)
    if script.repeat_resume and ctx.resume is not None:
        script.checkpoint_calls += 1
        ctx.checkpoint(ctx.resume, done=start, total=script.total)  # 들어온 부분을 같은 done 으로
    for i in range(start, script.total):
        if script.before_item is not None:
            script.before_item(i, adapters)
        items.append(i)
        script.items_done.append(i)
        script.checkpoint_calls += 1
        # 이어 도는 단계(F3 — 발주서의 꼴 그대로): 사건 쪽의 Exception 은 삼키고 다음 항목으로 간다
        try:  # noqa: SIM105
            ctx.checkpoint({"items": items}, done=i + 1, total=script.total)
        except Exception:  # noqa: S110
            pass
    script.finished_steps.append("judge")
    return StepOutput(data={"items": items, "from": carried["extract"].data["size"]})


def report(inputs: ProbeInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    items = carried["judge"].data["items"]
    count = len(items) if isinstance(items, list) else -1
    body: dict[str, object] = {"schemaVersion": "probe.result@1", "count": count}
    if adapters.script.big_result:
        body["padding"] = "가" * (3 * 1024 * 1024)  # UTF-8 3바이트 × 3Mi = 9MiB > 8MiB
    adapters.script.finished_steps.append("report")
    return StepOutput(
        data={"results": [body, {"schemaVersion": "probe.extra@1", "note": "둘째 꼴"}]},
        files=(OutputFile(name="report.bin", media_type="application/octet-stream", content=b"REPORT-BYTES"),),
    )


FLOW = make_flow(
    module="probe",
    id="probe.three@1",
    input_shape="probe.document@1",
    inputs=ProbeInputs,
    adapters=ProbeAdapters,
    result_shapes=("probe.result@1", "probe.extra@1"),
    output_files=("report.bin",),
    steps=(
        FlowStep(name="extract", run=extract),
        FlowStep(name="judge", run=judge),
        FlowStep(name="report", run=report),
    ),
)


class ProbeBinding:
    def __init__(self, script: Script) -> None:
        self.script = script
        self.contexts: list[RunContext] = []

    def check_options(self, options: Mapping[str, object]) -> None:
        return None

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> object:
        return ProbeInputs(document=document, options=dict(options))

    def adapters(self, ctx: RunContext) -> object:
        self.contexts.append(ctx)
        return ProbeAdapters(script=self.script, ctx=ctx)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {"flow": FLOW.id}


class RetryAsked(Exception):
    """가짜 retry 가 돌려주는 것(태스크가 `raise self.retry(…)` 로 던진다)."""


@dataclass
class World:
    storage: FakeStorage
    company_id: int
    other_company_id: int
    script: Script
    binding: ProbeBinding
    now: datetime = NOW
    mono: float = 0.0
    retries: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    sink: Any = field(default_factory=MemorySink)

    def retry(self, **kwargs: Any) -> RetryAsked:
        self.retries.append(kwargs)
        return RetryAsked()


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    script = Script()
    made = World(FakeStorage(), *companies, script=script, binding=ProbeBinding(script))
    plug_storage(monkeypatch, made.storage, max_upload_bytes=1000)
    flows = FlowRegistry()
    flows.register(FLOW)
    bindings = BindingRegistry()
    bindings.register(FLOW.id, made.binding)
    monkeypatch.setattr(tasks, "REGISTRY", flows)
    monkeypatch.setattr(tasks, "BINDINGS", bindings)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "clock", lambda: made.now)
    monkeypatch.setattr(tasks, "monotonic", lambda: made.mono)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: SOFT_S)
    monkeypatch.setattr(context, "call_sink", lambda: made.sink)
    return made


def new_run(world: World, *, flow_id: str = FLOW.id, company_id: int | None = None) -> int:
    """문서(저장소에 바이트)와 실행(queued)·단계 셋(pending)을 만든다. 실행 만들기(③)의 꼴을 손으로."""
    company = world.company_id if company_id is None else company_id
    key = f"companies/{company}/documents/probe-{len(world.storage.objects)}/original"
    etag = world.storage.put(key, PDF)
    document = DocumentRow.for_company(company).create(
        company_id=company,
        uploaded_by="1",
        file_name="지은 문서.pdf",
        storage_key=key,
        size_bytes=len(PDF),
        etag=etag,
        status="uploaded",
    )
    run = RunRow.for_company(company).create(
        company_id=company,
        document_id=document.pk,
        module="probe",
        flow_id=flow_id,
        options={"pages": "1-3"},
        versions={"flow": flow_id},
        status="queued",
        created_by_user_id=7,
    )
    for position, name in enumerate(FLOW.steps):
        RunStepRow.for_company(company).create(
            company_id=company, run_id=run.pk, name=name, position=position, status="pending"
        )
    return run.pk


def execute(world: World, run_id: int, *, company_id: int | None = None) -> None:
    """태스크를 한 번 부른다. 다시 넣기를 청하면(RetryAsked) 삼킨다 — world.retries 에 쌓인다."""
    company = world.company_id if company_id is None else company_id
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(world, company_id=str(company), run_id=str(run_id))


def row(world: World, run_id: int) -> RunRow:
    found = RunRow.for_company(world.company_id).filter(pk=run_id).first()
    assert found is not None
    return found


def steps(world: World, run_id: int) -> dict[str, RunStepRow]:
    return {s.name: s for s in RunStepRow.for_company(world.company_id).filter(run_id=run_id)}


def late_at(world: World, index: int) -> Callable[[int, ProbeAdapters], None]:
    """judge 의 항목 index 를 하기 전에 시계를 마감 뒤로 민다(그 항목의 체크포인트가 그 시도의 마지막이 된다)."""

    def hook(i: int, _: ProbeAdapters) -> None:
        if i == index:
            world.mono += LATE

    return hook


# ── 끝까지 ────────────────────────────────────────────────────────────


def test_a_run_goes_to_done_with_steps_results_and_files(world: World) -> None:
    run_id = new_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.attempts, run.stalled_attempts, run.failed_step, run.error_code) == (
        "done",
        1,
        0,
        None,
        None,
    )
    assert run.started_at == NOW and run.finished_at == NOW and run.lease_expires_at is None
    by_name = steps(world, run_id)
    assert [by_name[n].status for n in FLOW.steps] == ["done", "done", "done"]
    assert by_name["extract"].data == {"size": len(PDF), "name": "지은 문서.pdf"}  # data 는 JSON 왕복값
    assert by_name["judge"].data == {"items": [0, 1, 2, 3], "from": len(PDF)}
    assert (by_name["judge"].done, by_name["judge"].total) == (4, 4)
    results = list(RunResultRow.for_company(world.company_id).filter(run_id=run_id).order_by("position"))
    assert [(r.position, r.schema_version) for r in results] == [(0, "probe.result@1"), (1, "probe.extra@1")]
    assert results[0].body == {"schemaVersion": "probe.result@1", "count": 4}
    files = {(f.step, f.name): f for f in RunFileRow.for_company(world.company_id).filter(run_id=run_id)}
    assert set(files) == {("extract", "pages.json"), ("report", "report.bin"), (None, "report.bin")}
    output = files[(None, "report.bin")]
    assert output.storage_key == f"runs/{world.company_id}/{run_id}/out/report.bin"
    assert world.storage.objects[output.storage_key][0] == b"REPORT-BYTES"
    assert output.sha256 == hashlib.sha256(b"REPORT-BYTES").hexdigest() and output.size_bytes == 12
    assert world.storage.media_types[output.storage_key] == "application/octet-stream"
    assert world.retries == []
    (ctx,) = world.binding.contexts
    assert (ctx.company_id, ctx.run_id, ctx.module, ctx.flow_id, ctx.attempt) == (
        world.company_id,
        run_id,
        "probe",
        FLOW.id,
        1,
    )


def test_a_step_failure_keeps_the_steps_before_and_names_the_step(world: World) -> None:
    def broken(i: int, _: ProbeAdapters) -> None:
        if i == 2:
            raise ValueError("문서 글이 섞일 수 있는 원문 — 표에 싣지 않는다")

    world.script.before_item = broken
    run_id = new_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.failed_step, run.error_code) == ("failed", "judge", "step_error")
    assert run.error_message == RUN_ERROR_MESSAGES["step_error"]
    assert run.finished_at == NOW
    by_name = steps(world, run_id)
    assert [by_name[n].status for n in FLOW.steps] == ["done", "failed", "pending"]
    assert by_name["judge"].partial == {"items": [0, 1]}  # 실패 앞의 체크포인트 둘
    assert world.retries == []
    assert not RunResultRow.for_company(world.company_id).filter(run_id=run_id).exists()


@pytest.mark.parametrize(
    ("cause", "code"),
    [
        (LiveSetupError("키가 없다"), "setup_error"),  # 키 없는 서버 — 표 안
        (ValueError("다른 실패"), "step_error"),  # 분모: 같은 자리의 표 밖 실패
    ],
    ids=["live-setup", "other"],
)
def test_a_missing_ai_setup_in_a_step_ends_in_setup_error_on_that_step(
    world: World, cause: Exception, code: str
) -> None:
    def broken(i: int, _: ProbeAdapters) -> None:
        if i == 1:
            raise cause

    world.script.before_item = broken
    run_id = new_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.failed_step, run.error_code, run.attempts) == ("failed", "judge", code, 1)
    assert run.error_message == RUN_ERROR_MESSAGES[code]
    assert world.retries == []


# ── 협조 마감·소프트 제한·잠깐 오류 ───────────────────────────────────


def test_past_the_deadline_the_attempt_yields_and_the_next_resumes_from_the_partial(world: World) -> None:
    world.script.total = 6
    world.script.before_item = late_at(world, 2)  # 항목 2 를 하기 전에 마감이 지난다 → 체크포인트 3 이 마지막
    run_id = new_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.failed_step, run.lease_expires_at) == ("queued", None, None)
    judge_row = steps(world, run_id)["judge"]
    assert (judge_row.status, judge_row.done, judge_row.partial) == ("running", 3, {"items": [0, 1, 2]})
    # 마감을 넘긴 체크포인트가 그 시도의 마지막이다: 그 뒤 체크포인트 부름·항목 진행·단계 끝남 0 (F3 — P19 의 업무 반쪽)
    assert world.script.checkpoint_calls == 3
    assert world.script.items_done == [0, 1, 2]
    assert world.script.finished_steps == ["extract"]
    assert world.retries == [{"countdown": 5, "max_retries": None}]
    assert run.stalled_attempts == 0  # 진행이 있었다

    world.script.before_item = None
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.attempts, run.stalled_attempts) == ("done", 2, 0)
    assert world.script.resumed[-1] == {"items": [0, 1, 2]}  # 분모: 단계가 부분을 실제로 받았다(P8)
    assert world.script.items_done == [0, 1, 2, 3, 4, 5]
    assert steps(world, run_id)["judge"].data == {"items": [0, 1, 2, 3, 4, 5], "from": len(PDF)}
    assert world.storage.put_calls.count(f"runs/{world.company_id}/{run_id}/steps/extract/pages.json") == 1


def test_a_resumed_attempt_gets_the_carried_data_in_the_written_key_order(world: World) -> None:
    """extract 의 data {"size", "name"} 는 jsonb 라면 {"name", "size"} 로 늘어선다(같은 길이 — 바이트 차례).
    시도가 접혀 다음 시도가 DB 에서 carried 를 읽어도 한 번에 돈 것과 같은 차례다(X1b-2b ㉔)."""
    world.script.before_item = late_at(world, 1)
    run_id = new_run(world)
    execute(world, run_id)
    assert row(world, run_id).status == "queued"
    world.script.before_item = None
    execute(world, run_id)
    assert row(world, run_id).status == "done"
    # 첫 시도는 메모리의 산출, 둘째 시도는 DB 의 단계 행에서 읽은 carried(분모: 둘째가 실제로 DB 를 거쳤다)
    assert world.script.finished_steps.count("extract") == 1
    assert world.script.carried_keys == [["size", "name"], ["size", "name"]]
    assert list(steps(world, run_id)["extract"].data or {}) == ["size", "name"]


def test_started_at_is_the_first_claim_only(world: World) -> None:
    world.script.before_item = late_at(world, 1)
    run_id = new_run(world)
    execute(world, run_id)
    world.script.before_item = None
    world.now = NOW + timedelta(minutes=5)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.attempts, run.started_at, run.finished_at) == ("done", 2, NOW, NOW + timedelta(minutes=5))


def test_a_soft_limit_raised_by_a_step_defers(world: World) -> None:
    def slow(i: int, _: ProbeAdapters) -> None:
        if i == 1:
            raise SoftTimeLimitExceeded()

    world.script.before_item = slow
    run_id = new_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.failed_step, run.error_code) == ("queued", None, None)
    assert steps(world, run_id)["judge"].status == "running"  # 단계 행 failed 는 끝내기 RunFailed 만 쓴다
    assert len(world.retries) == 1


def test_a_soft_limit_inside_the_llm_call_is_reraised_and_the_run_is_deferred(world: World) -> None:
    """soft limit 은 다시 던져져 실행이 미뤄진다(S3, MARC-ISSUE-411): core/llm 이 공급사 오류 값으로 삼키지 않는다
    (LH2 — errors.soft_deadline_in). 주 길은 여전히 협조 마감."""

    def in_llm(i: int, adapters: ProbeAdapters) -> None:
        if i != 0:
            return
        client = adapters.ctx.llm()
        mock = client.provider("mock")
        assert isinstance(mock, MockProvider)

        def times_out(_: object) -> Any:
            raise SoftTimeLimitExceeded()

        mock.enqueue(times_out)
        result = client.call(
            CallRequest(
                prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=Tags(str(world.company_id), "probe")
            )
        )
        world.script.llm_results.append(result.kind)

    world.script.before_item = in_llm
    run_id = new_run(world)
    execute(world, run_id)
    assert world.script.llm_results == []
    assert (row(world, run_id).status, len(world.retries)) == ("queued", 1)  # 단계 밖으로 → RunDeferred


def test_a_database_error_on_the_event_side_defers(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    real = services.step_progress
    calls = {"n": 0}

    def flaky(**kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OperationalError("연결이 끊겼다(지어낸 것)")
        return real(**kwargs)

    monkeypatch.setattr(services, "step_progress", flaky)
    run_id = new_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.failed_step) == ("queued", None)
    assert len(world.retries) == 1


def test_an_unreachable_storage_for_the_output_defers(world: World) -> None:
    world.storage.put_fail_with = StorageUnavailable("가짜 닿지 못함")
    run_id = new_run(world)
    execute(world, run_id)
    assert row(world, run_id).status == "queued"
    assert len(world.retries) == 1


# ── 시도 상한(진행 없는 시도만 센다) ──────────────────────────────────


def test_three_attempts_without_progress_end_in_attempts_exhausted(world: World) -> None:
    def stuck() -> None:
        raise SoftTimeLimitExceeded()

    world.script.on_extract = stuck
    run_id = new_run(world)
    for _ in range(4):
        execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.attempts, run.stalled_attempts) == ("failed", 3, 3)
    assert (run.error_code, run.failed_step) == ("attempts_exhausted", None)
    assert len(world.retries) == 3  # 넷째 쪽지는 잡히지 않고 끝냈다


def test_attempts_with_progress_are_not_counted_and_the_run_finishes(world: World) -> None:
    """진행 있는 시도 넷 뒤 done — attempts 4 가 상한 3 을 넘어도 끝난다(P9 가 문다)."""
    world.script.total = 8
    lates = {1, 3, 5}

    def hook(i: int, _: ProbeAdapters) -> None:
        if i in lates:
            lates.discard(i)
            world.mono += LATE

    world.script.before_item = hook
    run_id = new_run(world)
    for _ in range(4):
        execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.attempts, run.stalled_attempts) == ("done", 4, 0)
    assert len(world.retries) == 3


def lapsed_processing(world: World, run_id: int, *, with_progress: bool) -> None:
    """앞 시도(1)가 잡고 (진행을 남기거나 말고) 끝내기 없이 죽은 꼴을 만든다. 시계를 임대 뒤로 민다."""
    with transaction.atomic():
        claimed = services.claim_run(
            company_id=world.company_id, run_id=run_id, now=world.now, lease_s=SETTINGS.lease_s, max_attempts=3
        )
        assert isinstance(claimed, services.Claimed)
        if with_progress:
            services.step_started(
                company_id=world.company_id, run_id=run_id, attempt=1, step="extract", now=world.now, lease_s=90
            )
            services.step_progress(
                company_id=world.company_id,
                run_id=run_id,
                attempt=1,
                step="extract",
                done=1,
                total=2,
                partial={},
                now=world.now,
                lease_s=90,
            )
    world.now += timedelta(seconds=SETTINGS.lease_s + 1)


def test_a_dead_attempt_without_progress_is_counted_when_taken_over(world: World) -> None:
    run_id = new_run(world)
    lapsed_processing(world, run_id, with_progress=False)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.attempts, run.stalled_attempts) == ("done", 2, 1)


def test_a_dead_attempt_with_progress_is_not_counted_when_taken_over(world: World) -> None:
    """F1: 견줌은 늘리기 앞의 attempts(= 죽은 시도)로 — 늘린 뒤 견주면 늘 +1(P20)."""
    run_id = new_run(world)
    lapsed_processing(world, run_id, with_progress=True)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.attempts, run.stalled_attempts) == ("done", 2, 0)


@pytest.mark.parametrize(("stop_at", "counted"), [(2, 1), (3, 0)], ids=["same-done", "one-more"])
def test_re_checkpointing_the_same_done_is_not_progress(world: World, stop_at: int, counted: int) -> None:
    """F4: 들어온 부분을 같은 done 으로 다시 체크포인트만 한 시도는 진행 0(P22). 분모: done 이 하나 커지면 셈 그대로."""
    world.script.total = 5
    world.script.before_item = late_at(world, 2)
    run_id = new_run(world)
    execute(world, run_id)  # 시도 1: extract 끝 + judge done 3 → 진행 있음
    assert (row(world, run_id).status, row(world, run_id).stalled_attempts) == ("queued", 0)
    with transaction.atomic():  # 저장된 부분을 done 2 로 되돌려 둔다(다음 시도가 같은 done 으로 다시 체크포인트하게)
        RunStepRow.for_company(world.company_id).filter(run_id=run_id, name="judge").update(
            done=2, partial={"items": [0, 1]}
        )

    def stop(i: int, _: ProbeAdapters) -> None:
        if i == stop_at:
            raise SoftTimeLimitExceeded()

    world.script.repeat_resume = True
    world.script.before_item = stop
    execute(world, run_id)  # 시도 2: done 2 다시(진행 아님) → stop_at 이 3 이면 항목 2 의 체크포인트 done 3(진행)
    run = row(world, run_id)
    assert (run.status, run.stalled_attempts) == ("queued", counted)


# ── 울타리·회사·끼움·크기 ─────────────────────────────────────────────


def test_the_same_note_twice_finishes_once(world: World) -> None:
    run_id = new_run(world)
    execute(world, run_id)
    before = row(world, run_id)
    execute(world, run_id)
    after = row(world, run_id)
    assert (after.status, after.attempts, after.updated_at) == ("done", 1, before.updated_at)
    assert RunResultRow.for_company(world.company_id).filter(run_id=run_id).count() == 2
    assert world.script.finished_steps == ["extract", "judge", "report"]  # 두 번째 쪽지는 흐름을 돌리지 않았다


def test_a_late_attempt_writes_nothing_once_another_took_over(world: World) -> None:
    """울타리: 시도 1 이 임대를 넘겨 시도 2 가 이어받은 뒤 늦게 쓰면 Superseded·0행(실행·단계·결과·파일 그대로)."""
    run_id = new_run(world)
    lapsed_processing(world, run_id, with_progress=False)  # 시도 1 이 잡고 임대가 끝났다
    with transaction.atomic():
        taken = services.claim_run(
            company_id=world.company_id, run_id=run_id, now=world.now, lease_s=SETTINGS.lease_s, max_attempts=3
        )
    assert isinstance(taken, services.Claimed) and taken.attempt == 2  # 분모: 시도 2 가 쥐었다(processing)
    before = row(world, run_id)
    late: dict[str, Any] = {"company_id": world.company_id, "run_id": run_id, "attempt": 1, "now": world.now}
    with transaction.atomic():
        progressed = services.step_progress(**late, step="extract", done=9, total=9, partial={"x": 1}, lease_s=90)
        finished_step = services.step_finished(
            **late,
            step="extract",
            data={"late": True},
            files=(
                services.StoredFile(
                    name="late.bin", media_type="x", storage_key="k/late", size_bytes=1, sha256="0" * 64
                ),
            ),
            lease_s=90,
        )
        done = services.finish_run(
            **late, outcome=services.RunDone(results=({"schemaVersion": "probe.result@1"},), files=())
        )
    assert (progressed, finished_step, done) == (services.Superseded(), services.Superseded(), services.Superseded())
    after = row(world, run_id)
    assert (after.status, after.attempts, after.progress_attempt, after.lease_expires_at) == (
        "processing",
        2,
        None,
        before.lease_expires_at,
    )
    extract = steps(world, run_id)["extract"]
    assert (extract.status, extract.done, extract.partial, extract.data) == ("pending", None, None, None)
    assert not RunResultRow.for_company(world.company_id).filter(run_id=run_id).exists()
    assert not RunFileRow.for_company(world.company_id).filter(run_id=run_id).exists()


def test_a_note_with_another_companys_id_touches_nothing(world: World) -> None:
    run_id = new_run(world)
    execute(world, run_id, company_id=world.other_company_id)
    assert (row(world, run_id).status, row(world, run_id).attempts) == ("queued", 0)
    assert world.storage.get_calls == []
    for bad in ("0", "-1", "01", "1.0", ""):
        tasks.execute_run(world, company_id=bad, run_id=str(run_id))
    assert row(world, run_id).attempts == 0


def test_a_flow_without_a_binding_fails_without_running(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tasks, "BINDINGS", BindingRegistry())
    run_id = new_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "flow_not_runnable", None)
    assert world.script.finished_steps == [] and world.storage.get_calls == []


def test_a_result_over_the_size_limit_fails_the_run(world: World) -> None:
    world.script.big_result = True
    run_id = new_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "result_too_large", None)
    assert not RunResultRow.for_company(world.company_id).filter(run_id=run_id).exists()


class Died(BaseException):
    """프로세스가 죽은 셈(태스크가 잡지 않는다)."""


def test_a_run_whose_steps_all_finished_is_assembled_without_running_again(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """앞 시도가 단계를 다 끝내고 끝내기(T2) 없이 죽었다 → 다음 시도는 끝 산출물을 단계 행·파일에서 모은다."""
    run_id = new_run(world)

    def die_before_t2(**_: Any) -> Any:
        raise Died

    with monkeypatch.context() as patch:
        patch.setattr(services, "finish_run", die_before_t2)
        with pytest.raises(Died):
            tasks.execute_run(world, company_id=str(world.company_id), run_id=str(run_id))
    assert [s.status for s in steps(world, run_id).values()] == ["done", "done", "done"]
    assert row(world, run_id).status == "processing"
    world.now += timedelta(seconds=SETTINGS.lease_s + 1)
    ran = list(world.script.finished_steps)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.attempts, run.stalled_attempts) == ("done", 2, 0)  # 시도 1 은 진행을 남겼다
    assert world.script.finished_steps == ran  # 단계를 다시 돌리지 않았다
    results = RunResultRow.for_company(world.company_id).filter(run_id=run_id).order_by("position")
    assert [r.schema_version for r in results] == ["probe.result@1", "probe.extra@1"]
    output = RunFileRow.for_company(world.company_id).filter(run_id=run_id, step__isnull=True).first()
    assert output is not None and world.storage.objects[output.storage_key][0] == b"REPORT-BYTES"


# ── LLM 기록의 run_id(DB 싱크 — P18) ─────────────────────────────────


def test_llm_rows_carry_the_run_id_even_when_the_tags_have_no_run(world: World) -> None:
    world.sink = DbSink()

    def call_once(i: int, adapters: ProbeAdapters) -> None:
        if i != 0:
            return
        client = adapters.ctx.llm()
        mock = client.provider("mock")
        assert isinstance(mock, MockProvider)
        mock.enqueue_text("판정")
        client.call(  # 꼬리표에는 실행 칸이 없다(Tags 는 tenant·module 둘)
            CallRequest(
                prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=Tags(str(world.company_id), "probe")
            )
        )

    world.script.before_item = call_once
    run_id = new_run(world)
    other = new_run(world)
    execute(world, run_id)
    logged = list(LlmCallLogRow.for_company(world.company_id).filter(module="probe"))
    assert len(logged) >= 1  # 분모
    assert {r.run_id for r in logged} == {run_id}
    assert row(world, other).status == "queued"


# ── 단계 이름(AD4D — 실행의 싱크가 커서의 지금 단계를 줄마다 덮어 적는다) ──────────────────


def call_llm(ctx: RunContext, world: World) -> None:
    """이 실행의 클라이언트로 모의 호출 한 번(꼬리표에는 실행·단계 칸이 없다)."""
    client = ctx.llm()
    mock = client.provider("mock")
    assert isinstance(mock, MockProvider)
    mock.enqueue_text("판정")
    client.call(
        CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=Tags(str(world.company_id), "probe"))
    )


def logged_steps(world: World, run_id: int) -> list[str | None]:
    return [
        r.step for r in LlmCallLogRow.for_company(world.company_id).filter(module="probe", run_id=run_id).order_by("id")
    ]


def test_each_llm_row_carries_the_step_it_was_called_in(world: World) -> None:
    world.sink = DbSink()
    world.script.on_extract = lambda: call_llm(world.binding.contexts[-1], world)

    def call_once(i: int, adapters: ProbeAdapters) -> None:
        if i == 0:
            call_llm(adapters.ctx, world)

    world.script.before_item = call_once
    run_id = new_run(world)
    execute(world, run_id)
    assert row(world, run_id).status == "done"
    assert logged_steps(world, run_id) == ["extract", "judge"]  # 줄 둘 — 단계마다 하나
    assert set(logged_steps(world, run_id)) <= set(steps(world, run_id))  # 단계 행의 이름 그대로


def test_a_resumed_attempt_names_the_step_it_starts_from(world: World) -> None:
    """마감에 걸려 접힌 시도 뒤 다음 시도가 judge 부터 이어 돌아도(새 커서) 줄의 단계가 맞다."""
    world.sink = DbSink()
    world.script.total = 6
    world.script.on_extract = lambda: call_llm(world.binding.contexts[-1], world)
    late = late_at(world, 2)

    def call_and_late(i: int, adapters: ProbeAdapters) -> None:
        if i in (0, 4):
            call_llm(adapters.ctx, world)
        late(i, adapters)

    world.script.before_item = call_and_late
    run_id = new_run(world)
    execute(world, run_id)
    assert (row(world, run_id).status, logged_steps(world, run_id)) == ("queued", ["extract", "judge"])
    world.script.before_item = lambda i, adapters: call_llm(adapters.ctx, world) if i == 4 else None
    execute(world, run_id)
    assert row(world, run_id).status == "done"
    assert world.script.finished_steps == ["extract", "judge", "report"]  # 둘째 시도는 judge 부터(extract 다시 0)
    assert logged_steps(world, run_id) == ["extract", "judge", "judge"]


def test_a_failed_step_names_its_rows_and_the_previous_steps_keep_theirs(world: World) -> None:
    world.sink = DbSink()
    world.script.on_extract = lambda: call_llm(world.binding.contexts[-1], world)

    def call_then_fail(i: int, adapters: ProbeAdapters) -> None:
        if i == 0:
            call_llm(adapters.ctx, world)
        if i == 1:
            raise ValueError("지어낸 실패")

    world.script.before_item = call_then_fail
    run_id = new_run(world)
    execute(world, run_id)
    assert (row(world, run_id).status, row(world, run_id).failed_step) == ("failed", "judge")
    assert logged_steps(world, run_id) == ["extract", "judge"]


def test_a_call_outside_a_run_has_no_step(world: World) -> None:
    """실행 밖(동기 계산·관리 명령 — RunCallSink 없음)의 줄은 run_id·step 둘 다 NULL."""
    client = build_client(LlmSettings(), mock=True, sink=DbSink())
    mock = client.provider("mock")
    assert isinstance(mock, MockProvider)
    mock.enqueue_text("판정")
    client.call(
        CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=Tags(str(world.company_id), "probe"))
    )
    (only,) = LlmCallLogRow.for_company(world.company_id).filter(module="probe")
    assert (only.run_id, only.step) == (None, None)


# ── 다시 넣기 명령 ────────────────────────────────────────────────────


BROKER = BrokerSettings(url="sqs://queue:9324", region="r", queue_name="esg-jobs", queue_url="http://queue:9324/0/q")


def test_requeue_runs_sends_lapsed_and_waiting_runs_only(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []

    def spy(**kwargs: Any) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(hooks, "enqueue_run", spy)
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    lapsed = new_run(world)
    lapsed_processing(world, lapsed, with_progress=False)
    done = new_run(world)
    execute(world, done)
    fresh = new_run(world)
    RunRow.for_company(world.company_id).filter(pk=fresh).update(updated_at=world.now)
    monkeypatch.setattr("esgapi.runs.management.commands.requeue_runs.now", lambda: world.now)
    out = StringIO()
    call_command("requeue_runs", "--tenant", str(world.company_id), "--queued-older-than-seconds", "60", stdout=out)
    assert sent == [{"company_id": world.company_id, "run_id": lapsed}]
    assert "고른 수 1 · 넣은 수 1 · 실패한 수 0" in out.getvalue()
    out = StringIO()
    call_command("requeue_runs", "--tenant", str(world.other_company_id), "--dry-run", stdout=out)
    assert "고른 수 0" in out.getvalue()  # 남의 회사 실행은 보이지 않는다


# ── 끼움의 둘째 꼴(RunFactsBinding — G2c2): 받는 끼움·안 받는 끼움 한 쌍(백엔드 c1 허락 조건 (나)) ──


class PlainProbe(ProbeBinding):
    """옛 꼴만(RunBinding). 부른 것을 적는다."""

    def __init__(self, script: Script) -> None:
        super().__init__(script)
        self.called: list[str] = []

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> object:
        self.called.append("inputs")
        return super().inputs(document, options)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        self.called.append("versions")
        return {"probe": "plain"}


class FactsProbe(PlainProbe):
    """둘째 꼴도 갖춘 끼움: 실행의 회사와 박힌 판 묶음을 받는다."""

    def __init__(self, script: Script) -> None:
        super().__init__(script)
        self.facts: list[tuple[str, int, dict[str, object] | None]] = []

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]:
        self.facts.append(("versions_with", company_id, None))
        return {"probe": "facts", "company": company_id}

    def inputs_with(
        self, document: DocumentInput, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> object:
        self.facts.append(("inputs_with", company_id, dict(versions)))
        return ProbeInputs(document=document, options=dict(options))


def _swap_binding(monkeypatch: pytest.MonkeyPatch, binding: ProbeBinding) -> None:
    bindings = BindingRegistry()
    bindings.register(FLOW.id, binding)
    monkeypatch.setattr(tasks, "BINDINGS", bindings)


def test_a_binding_with_the_second_shape_gets_the_company_and_the_run_versions(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts = FactsProbe(world.script)
    assert isinstance(facts, flow_ports.RunFactsBinding)
    _swap_binding(monkeypatch, facts)
    run_id = new_run(world)
    RunRow.for_company(world.company_id).filter(pk=run_id).update(versions={"flow": FLOW.id, "probe": "made"})
    execute(world, run_id)
    assert row(world, run_id).status == "done"
    assert facts.facts == [("inputs_with", world.company_id, {"flow": FLOW.id, "probe": "made"})]
    assert facts.called == []  # 옛 inputs 는 불리지 않는다


def test_a_binding_without_the_second_shape_runs_the_old_way(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    plain = PlainProbe(world.script)
    assert not isinstance(plain, flow_ports.RunFactsBinding)
    _swap_binding(monkeypatch, plain)
    run_id = new_run(world)
    execute(world, run_id)
    assert row(world, run_id).status == "done"
    assert plain.called == ["inputs"]


@pytest.mark.parametrize("shape", ["facts", "plain"])
def test_creating_a_run_takes_the_versions_from_the_right_shape(
    world: World, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    from esgapi.runs.service.actions import runs as actions

    binding: PlainProbe = FactsProbe(world.script) if shape == "facts" else PlainProbe(world.script)
    flows = FlowRegistry()
    flows.register(FLOW)
    bindings = BindingRegistry()
    bindings.register(FLOW.id, binding)
    monkeypatch.setattr(actions, "REGISTRY", flows)
    monkeypatch.setattr(actions, "BINDINGS", bindings)
    document_id = RunRow.for_company(world.company_id).get(pk=new_run(world)).document_id
    created = actions.create_run(
        company_id=world.company_id,
        actor_kind="service",
        actor_user_id=7,
        module="probe",
        flow_id=FLOW.id,
        document_id=document_id,
        options={"pages": "1"},
        resume_from=None,
        now=NOW,
    )
    assert isinstance(created, actions.RunCreated), created
    versions = row(world, created.run.id).versions
    if isinstance(binding, FactsProbe):
        assert versions == {"probe": "facts", "company": world.company_id, "flow": FLOW.id}
        assert [name for name, *_ in binding.facts] == ["versions_with"] and binding.called == []
    else:
        assert versions == {"probe": "plain", "flow": FLOW.id}
        assert binding.called == ["versions"]


# ── 이어서 돌린 실행(X1b-2b): 옮긴 단계는 다시 돌지 않고, 받는 끼움은 앞 실행의 판을 받는다 ──


def resumed_from_failed(
    world: World, monkeypatch: pytest.MonkeyPatch, capture: Any, binding: ProbeBinding
) -> tuple[int, int]:
    """judge 의 항목 2 에서 실패한 실행(extract 는 끝남·단계 파일 하나)을 만들고, 실행 만들기로 이어 돌린 새 실행을
    만든다(커밋 뒤 갈고리 — 쪽지 — 를 실제로 부른다. 바이트는 실행기가 옮긴다). 실행기에는 binding 을 끼운다."""
    from esgapi.runs.service.actions import runs as actions

    def broken(i: int, _: ProbeAdapters) -> None:
        if i == 2:
            raise ValueError("지어낸 실패")

    world.script.before_item = broken
    previous = new_run(world)
    execute(world, previous)
    assert row(world, previous).status == "failed"
    world.script.before_item = None
    flows = FlowRegistry()
    flows.register(FLOW)
    bindings = BindingRegistry()
    bindings.register(FLOW.id, binding)
    monkeypatch.setattr(actions, "REGISTRY", flows)
    monkeypatch.setattr(actions, "BINDINGS", bindings)
    _swap_binding(monkeypatch, binding)

    def ignore(**_: object) -> None:
        return None

    monkeypatch.setattr(hooks, "enqueue_run", ignore)
    with capture(execute=True):
        created = actions.create_run(
            company_id=world.company_id,
            actor_kind="service",
            actor_user_id=7,
            module="probe",
            flow_id=FLOW.id,
            document_id=row(world, previous).document_id,
            options={},
            resume_from=previous,
            now=NOW,
        )
    assert isinstance(created, actions.RunCreated), created
    return previous, created.run.id


def test_a_resumed_run_does_not_run_the_carried_steps_again(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    previous, new = resumed_from_failed(
        world, monkeypatch, django_capture_on_commit_callbacks, ProbeBinding(world.script)
    )
    assert world.script.finished_steps == ["extract"]  # 앞 실행이 돈 것
    execute(world, new)
    run = row(world, new)
    assert (run.status, run.resumed_from_run_id) == ("done", previous)
    assert world.script.finished_steps == ["extract", "judge", "report"]  # 옮긴 extract 부름 0, 실패 단계부터
    assert world.script.resumed[-1] is None  # 실패 단계의 partial 은 옮기지 않았다(처음부터)
    assert world.script.carried_keys[-1] == ["size", "name"]  # DB 에서 읽은 carried(옮긴 data)
    by_name = steps(world, new)
    assert [by_name[n].status for n in FLOW.steps] == ["done", "done", "done"]
    assert by_name["extract"].data == steps(world, previous)["extract"].data
    # 앞 실행은 그대로 failed
    assert row(world, previous).status == "failed"


def test_a_resumed_run_hands_the_previous_versions_to_the_binding(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """받는 끼움(:RunFactsBinding)은 앞 실행의 판 묶음을 받는다 — 끼움의 versions_with 가 지금 다른 값을 내도."""
    facts = FactsProbe(world.script)
    previous, new = resumed_from_failed(world, monkeypatch, django_capture_on_commit_callbacks, facts)
    assert row(world, new).versions == row(world, previous).versions == {"flow": FLOW.id}
    execute(world, new)
    assert row(world, new).status == "done"
    assert facts.facts == [("inputs_with", world.company_id, {"flow": FLOW.id})]  # versions_with 부름 0


# ── 문서 없는 흐름(ND1): 문서를 읽지 않고 옵션·회사로 돈다 ──────────────────


@dataclass(frozen=True)
class BareInputs:
    options: dict[str, object]
    company_id: int


def bare_first(inputs: BareInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    adapters.script.finished_steps.append("first")
    return StepOutput(data={"rows": inputs.options["rows"], "company": inputs.company_id})


def bare_second(inputs: BareInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    if adapters.script.before_item is not None:
        adapters.script.before_item(0, adapters)
    adapters.script.finished_steps.append("second")
    rows = carried["first"].data["rows"]
    count = len(rows) if isinstance(rows, list) else -1
    return StepOutput(data={"results": [{"schemaVersion": "probe.result@1", "count": count}]})


BARE_FLOW = make_flow(
    module="probe",
    id="probe.bare@1",
    input_shape="probe.options@1",
    inputs=BareInputs,
    adapters=ProbeAdapters,
    result_shapes=("probe.result@1",),
    output_files=(),
    steps=(FlowStep(name="first", run=bare_first), FlowStep(name="second", run=bare_second)),
)


class BareProbe:
    """문서 없는 끼움(DocumentlessBinding 꼴). 받은 회사와 부른 것을 적는다."""

    def __init__(self, script: Script) -> None:
        self.script = script
        self.called: list[tuple[str, int]] = []

    def check_options(self, options: Mapping[str, object]) -> None:
        return None

    def inputs(self, options: Mapping[str, object], *, company_id: int) -> object:
        self.called.append(("inputs", company_id))
        return BareInputs(options=dict(options), company_id=company_id)

    def adapters(self, ctx: RunContext) -> object:
        return ProbeAdapters(script=self.script, ctx=ctx)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {"rules": "bare@1"}


class BareFactsProbe(BareProbe):
    """문서 없는 둘째 꼴(DocumentlessFactsBinding). 실행기는 inputs_with 에 실행 행의 versions 를 넘긴다."""

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]:
        return {"rules": "bare@2", "company": company_id}

    def inputs_with(self, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]) -> object:
        self.called.append(("inputs_with", company_id))
        self.script.resumed.append(dict(versions))
        return BareInputs(options=dict(options), company_id=company_id)


def with_bare(monkeypatch: pytest.MonkeyPatch, world: World, binding: BareProbe) -> None:
    """실행기와 실행 만들기의 등록부에 문서 흐름(FLOW)과 문서 없는 흐름(BARE_FLOW)을 같이 단다."""
    from esgapi.runs.service.actions import runs as actions

    flows = FlowRegistry()
    flows.register(FLOW)
    flows.register(BARE_FLOW)
    bindings = BindingRegistry()
    bindings.register(FLOW.id, world.binding)
    bindings.register_documentless(BARE_FLOW.id, binding)
    for where in (tasks, actions):
        monkeypatch.setattr(where, "REGISTRY", flows)
        monkeypatch.setattr(where, "BINDINGS", bindings)


def new_bare_run(world: World, *, flow: Any = BARE_FLOW, company_id: int | None = None) -> int:
    """문서 칸이 NULL 인 실행(queued)과 단계(pending). 주인 역할로 손으로(실행 만들기의 꼴)."""
    company = world.company_id if company_id is None else company_id
    run = RunRow.for_company(company).create(
        company_id=company,
        document_id=None,
        module="probe",
        flow_id=flow.id,
        options={"rows": [3, 1, 2]},
        versions={"rules": "made", "flow": flow.id},
        status="queued",
        created_by_user_id=7,
    )
    for position, name in enumerate(flow.steps):
        RunStepRow.for_company(company).create(
            company_id=company, run_id=run.pk, name=name, position=position, status="pending"
        )
    return run.pk


def test_a_documentless_run_goes_to_done_without_reading_a_document(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """문서 get 0 · inputs 가 행의 options 그대로 · 받은 company_id = 실행의 회사 · 결과 하나."""
    binding = BareProbe(world.script)
    with_bare(monkeypatch, world, binding)
    run_id = new_bare_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.attempts, run.error_code, run.document_id) == ("done", 1, None, None)
    assert world.storage.get_calls == []  # 문서를 읽지 않는다(P8)
    assert binding.called == [("inputs", world.company_id)]  # 회사를 받는다(P22)
    by_name = steps(world, run_id)
    assert by_name["first"].data == {"rows": [3, 1, 2], "company": world.company_id}
    results = list(RunResultRow.for_company(world.company_id).filter(run_id=run_id))
    assert [(r.schema_version, r.body) for r in results] == [
        ("probe.result@1", {"schemaVersion": "probe.result@1", "count": 3})
    ]
    assert world.script.finished_steps == ["first", "second"]


def test_a_document_flow_run_without_a_document_fails_once(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """문서 흐름의 행인데 문서 칸이 비었다(만들기가 막는 것 — 주인 역할로 넣음): failed document_missing · 시도 하나 ·
    다시 넣기 0 · 저장소 0(P9)."""
    with_bare(monkeypatch, world, BareProbe(world.script))
    run_id = new_bare_run(world, flow=FLOW)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.error_code, run.failed_step, run.attempts) == ("failed", "document_missing", None, 1)
    assert world.retries == [] and world.storage.get_calls == []
    assert world.script.finished_steps == []


def test_a_documentless_facts_binding_gets_the_company_and_the_run_versions(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """둘째 꼴은 inputs_with(회사, 행의 versions). 갈래는 사전이 먼저라 문서 꼴 inputs_with 로 부르지 않는다(P20)."""
    binding = BareFactsProbe(world.script)
    assert isinstance(binding, flow_ports.RunFactsBinding)  # 이름만 보면 문서 꼴로도 True — 함정
    with_bare(monkeypatch, world, binding)
    run_id = new_bare_run(world)
    execute(world, run_id)
    assert row(world, run_id).status == "done", row(world, run_id).error_code
    assert binding.called == [("inputs_with", world.company_id)]
    assert world.script.resumed == [{"rules": "made", "flow": BARE_FLOW.id}]


def test_a_failed_documentless_run_resumes_from_its_failed_step(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """둘째 단계에서 실패 → 실행 만들기로 이어 돌림(문서 없이) → 첫 단계는 다시 돌지 않고 done."""
    from esgapi.runs.service.actions import runs as actions

    binding = BareProbe(world.script)
    with_bare(monkeypatch, world, binding)

    def broken(i: int, _: ProbeAdapters) -> None:
        raise ValueError("지어낸 실패")

    world.script.before_item = broken
    previous = new_bare_run(world)
    execute(world, previous)
    assert (row(world, previous).status, row(world, previous).failed_step) == ("failed", "second")
    world.script.before_item = None
    world.script.finished_steps.clear()

    def ignore(**_: object) -> None:
        return None

    monkeypatch.setattr(hooks, "enqueue_run", ignore)
    with django_capture_on_commit_callbacks(execute=True):
        created = actions.create_run(
            company_id=world.company_id,
            actor_kind="service",
            actor_user_id=7,
            module="probe",
            flow_id=BARE_FLOW.id,
            document_id=None,
            options={},
            resume_from=previous,
            now=NOW,
        )
    assert isinstance(created, actions.RunCreated), created
    execute(world, created.run.id)
    assert row(world, created.run.id).status == "done"
    assert world.script.finished_steps == ["second"]  # 첫 단계는 옮겨 왔다
    assert world.storage.get_calls == []


def test_a_documentless_run_without_a_store_fails_storage_unconfigured(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """저장소가 없으면 문서 없는 실행도 failed storage_unconfigured(단계 산출 파일을 쓸 데가 없다 — 검증 R1).
    분모: 저장소가 있으면 done(test_a_documentless_run_goes_to_done_without_reading_a_document)."""
    binding = BareProbe(world.script)
    with_bare(monkeypatch, world, binding)
    plug_storage(monkeypatch, None)
    run_id = new_bare_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.error_code, run.failed_step, run.attempts) == ("failed", "storage_unconfigured", None, 1)
    assert binding.called == [] and world.script.finished_steps == []


# ── 이어 돌기의 바이트 옮김(RC1): 새 키가 비었으면 실행기 _plan 이 앞 실행(사슬)의 키에서 옮겨 쓴다 ─────────
# 요청 갈고리를 거치지 않은 세계를 만든다: 실행 만들기 뒤 새 키를 world.storage.objects 에서 지운다.

BIG = 48 * 2**20  # 지어낸 0 바이트의 큰 단계 파일(그린워싱 index 벡터 꼴)


def pages_key(world: World, run_id: int) -> str:
    return file_key(company_id=world.company_id, run_id=run_id, step="extract", name="pages.json")


def emptied(
    world: World, monkeypatch: pytest.MonkeyPatch, capture: Any, binding: ProbeBinding | None = None
) -> tuple[int, int]:
    """resumed_from_failed 뒤 새 실행의 키를 비우고 저장소의 부름 기록을 지운다(실행기 혼자 옮기는 세계)."""
    previous, new = resumed_from_failed(world, monkeypatch, capture, binding or ProbeBinding(world.script))
    world.storage.objects.pop(pages_key(world, new), None)
    world.storage.get_calls.clear()
    world.storage.put_calls.clear()
    return previous, new


def run_gets(world: World) -> list[str]:
    """문서 키를 뺀 get(실행의 단계 파일 키만)."""
    return [k for k in world.storage.get_calls if k.startswith("runs/")]


def copy_lines(caplog: pytest.LogCaptureFixture) -> list[tuple[str, str]]:
    """실행기의 옮김 로그만(실행 만들기의 갈고리 로그는 뺀다)."""
    return [
        (r.levelname, r.getMessage())
        for r in caplog.records
        if r.name == tasks.__name__ and r.getMessage().startswith("run_resume_copy")
    ]


def failing_get(world: World, monkeypatch: pytest.MonkeyPatch, key: str, result: GetResult) -> None:
    """그 키의 get 만 result 를 돌려주게 감싼다(FakeStorage.fail_with 는 head·get 전부 — 문서 get 이 먼저 걸린다)."""
    real = world.storage.get

    def get(asked: str, *, max_bytes: int) -> GetResult:
        if asked == key:
            world.storage.get_calls.append(asked)
            return result
        return real(asked, max_bytes=max_bytes)

    monkeypatch.setattr(world.storage, "get", get)


def test_an_empty_new_key_is_filled_from_the_previous_run_and_the_run_goes_on(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """① 1: 새 키 없음 → 앞 키 get → 새 키 put(바이트·꼴 같음) → done, 옮긴 단계 extract 를 다시 부르지 않는다."""
    previous, new = emptied(world, monkeypatch, django_capture_on_commit_callbacks)
    with caplog.at_level(logging.INFO, logger=tasks.__name__):
        execute(world, new)
    assert (row(world, new).status, row(world, new).error_code) == ("done", None)
    assert world.script.finished_steps == ["extract", "judge", "report"]  # extract 는 앞 실행이 돈 하나뿐
    assert world.storage.objects[pages_key(world, new)][0] == b"[1, 2]"
    assert world.storage.media_types[pages_key(world, new)] == "application/json"
    assert run_gets(world) == [pages_key(world, new), pages_key(world, previous)]
    assert world.storage.put_calls[0] == pages_key(world, new)
    assert world.storage.objects[pages_key(world, previous)][0] == b"[1, 2]"  # 앞 키 그대로
    assert copy_lines(caplog) == [
        (
            "INFO",
            f"run_resume_copy run_id={new} step=extract name=pages.json from_run={previous} result=copied",
        )
    ]


def test_a_big_step_file_is_carried_by_the_executor(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """① 2: 48 MiB(지어낸 0 바이트)의 단계 파일 — 행의 size_bytes 가 상한이라 그대로 옮겨진다."""
    previous, new = emptied(world, monkeypatch, django_capture_on_commit_callbacks)
    big = bytes(BIG)
    world.storage.put(pages_key(world, previous), big)
    RunFileRow.for_company(world.company_id).filter(run_id__in=(previous, new), step="extract").update(size_bytes=BIG)
    started = time.monotonic()
    execute(world, new)
    took = time.monotonic() - started
    assert row(world, new).status == "done"
    assert len(world.storage.objects[pages_key(world, new)][0]) == BIG
    assert took < 30  # 메모리 안의 가짜라 짧다(실 저장소의 시간은 재지 않는다)


def test_an_unreachable_store_while_carrying_defers_and_the_next_attempt_carries(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """① 3: 앞 키 get 만 닿지 못함 → RunDeferred(queued·다시 넣기·실패 칸 비어 있음·새 키 put 0) → 풀고 다시 → done."""
    previous, new = emptied(world, monkeypatch, django_capture_on_commit_callbacks)
    real = world.storage.get
    failing_get(world, monkeypatch, pages_key(world, previous), StorageUnavailable("지어낸 끊김"))
    execute(world, new)
    run = row(world, new)
    assert (run.status, run.failed_step, run.error_code) == ("queued", None, None)
    assert len(world.retries) == 1
    assert pages_key(world, new) not in world.storage.put_calls
    monkeypatch.setattr(world.storage, "get", real)
    execute(world, new)
    assert row(world, new).status == "done"
    assert world.storage.objects[pages_key(world, new)][0] == b"[1, 2]"


def test_an_unreachable_store_on_the_new_key_put_defers_and_the_next_attempt_carries(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """① 3(put): 새 키 put 이 닿지 못함 → RunDeferred, 새 키는 여전히 빔 → 풀고 다시 → done·새 키 바이트."""
    _, new = emptied(world, monkeypatch, django_capture_on_commit_callbacks)
    world.storage.put_fail_with = StorageUnavailable("지어낸 쓰기 끊김")
    execute(world, new)
    assert (row(world, new).status, row(world, new).error_code, len(world.retries)) == ("queued", None, 1)
    assert world.script.finished_steps == ["extract"]  # 이어 갈 자리(_plan)에서 멈췄다 — 흐름을 돌지 않았다
    assert pages_key(world, new) not in world.storage.objects
    world.storage.put_fail_with = None
    execute(world, new)
    assert row(world, new).status == "done"
    assert world.storage.objects[pages_key(world, new)][0] == b"[1, 2]"


def test_a_refused_put_of_the_new_key_fails_storage_denied(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """① 4: 새 키 put 거절(403) → failed storage_denied(파일 put 거절과 같은 code), 다시 넣기 0."""
    previous, new = emptied(world, monkeypatch, django_capture_on_commit_callbacks)
    world.storage.put_fail_with = StorageDenied("지어낸 쓰기 거절")
    with caplog.at_level(logging.INFO, logger=tasks.__name__):
        execute(world, new)
    run = row(world, new)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "storage_denied", None)
    assert world.retries == []
    assert copy_lines(caplog) == [
        (
            "WARNING",
            f"run_resume_copy run_id={new} step=extract name=pages.json from_run={previous} result=refused",
        )
    ]


def test_a_missing_previous_object_fails_object_missing_like_before(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """① 5: 앞 키에도 없음 → failed object_missing(BASE 와 같은 code·글), put 0."""
    previous, new = emptied(world, monkeypatch, django_capture_on_commit_callbacks)
    del world.storage.objects[pages_key(world, previous)]
    with caplog.at_level(logging.INFO, logger=tasks.__name__):
        execute(world, new)
    run = row(world, new)
    assert (run.status, run.error_code, run.error_message) == (
        "failed",
        "object_missing",
        RUN_ERROR_MESSAGES["object_missing"],
    )
    assert world.storage.put_calls == []
    assert [level for level, _ in copy_lines(caplog)] == ["WARNING"]
    assert copy_lines(caplog)[0][1].endswith(f"from_run={previous} result=missing")


def test_a_previous_object_larger_than_its_row_is_not_carried(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """① 6: 앞 객체가 행의 size_bytes 보다 크면(get max_bytes=size_bytes) object_missing, put 0."""
    previous, new = emptied(world, monkeypatch, django_capture_on_commit_callbacks)
    world.storage.put(pages_key(world, previous), b"[1, 2, 3, 4]")
    execute(world, new)
    assert (row(world, new).status, row(world, new).error_code) == ("failed", "object_missing")
    assert world.storage.put_calls == []


@pytest.mark.parametrize("own", ["too-large", "denied"])
def test_an_own_key_that_is_too_large_or_refused_is_not_overwritten_from_the_chain(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any, own: str
) -> None:
    """RC1 검증 R1(감독 22 필수): 이어 돈 실행의 자기 키 get 이 없음이 아니면(행보다 큼·읽기 거절) BASE 그대로
    object_missing — 사슬로 가지 않아 앞 키 get 0·put 0·자기 키 바이트 그대로(덮어쓰기 0)."""
    previous, new = emptied(world, monkeypatch, django_capture_on_commit_callbacks)
    own_bytes = b"[1, 2, 3, 4]" if own == "too-large" else b"[9, 9]"
    world.storage.put(pages_key(world, new), own_bytes)
    if own == "denied":
        failing_get(world, monkeypatch, pages_key(world, new), StorageDenied("지어낸 읽기 거절"))
    execute(world, new)
    assert (row(world, new).status, row(world, new).error_code) == ("failed", "object_missing")
    assert pages_key(world, previous) not in world.storage.get_calls
    assert world.storage.put_calls == []
    assert world.storage.objects[pages_key(world, new)][0] == own_bytes


def failed_by_hand(world: World, run_id: int) -> None:
    """실행을 judge 에서 실패한 것으로 적는다(실행기를 돌리지 않고 — 그 키는 빈 채로)."""
    RunRow.for_company(world.company_id).filter(pk=run_id).update(
        status="failed", failed_step="judge", error_code="step_error", finished_at=NOW
    )


def resume_of(world: World, previous: int, capture: Any) -> int:
    from esgapi.runs.service.actions import runs as actions

    with capture(execute=True):
        created = actions.create_run(
            company_id=world.company_id,
            actor_kind="service",
            actor_user_id=7,
            module="probe",
            flow_id=FLOW.id,
            document_id=row(world, previous).document_id,
            options={},
            resume_from=previous,
            now=NOW,
        )
    assert isinstance(created, actions.RunCreated), created
    return created.run.id


@pytest.mark.parametrize("first_has_bytes", [True, False], ids=["r1-has-bytes", "r1-empty-too"])
def test_the_chain_is_walked_back_to_the_run_that_has_the_bytes(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
    caplog: pytest.LogCaptureFixture,
    first_has_bytes: bool,
) -> None:
    """① 7: R1(바이트 있음) ← R2(키 빔, _plan 전에 실패) ← R3 → R3 done·바이트는 R1 의 것·R3 키에 put·R2 키는 그대로 빔.
    분모: R1 객체도 없으면 object_missing."""
    first, second = emptied(world, monkeypatch, django_capture_on_commit_callbacks)
    failed_by_hand(world, second)
    third = resume_of(world, second, django_capture_on_commit_callbacks)
    world.storage.objects.pop(pages_key(world, second), None)  # critic m4: ① 의 갈고리가 채웠어도 명시해 비운다
    world.storage.objects.pop(pages_key(world, third), None)
    if not first_has_bytes:
        del world.storage.objects[pages_key(world, first)]
    world.storage.get_calls.clear()
    with caplog.at_level(logging.INFO, logger=tasks.__name__):
        execute(world, third)
    if not first_has_bytes:
        assert (row(world, third).status, row(world, third).error_code) == ("failed", "object_missing")
        assert run_gets(world) == [pages_key(world, n) for n in (third, second, first)]
        return
    assert row(world, third).status == "done"
    assert world.storage.objects[pages_key(world, third)][0] == b"[1, 2]"
    assert pages_key(world, second) not in world.storage.objects  # 앞 실행은 고치지 않는다
    assert run_gets(world)[:3] == [pages_key(world, n) for n in (third, second, first)]
    assert copy_lines(caplog) == [
        ("INFO", f"run_resume_copy run_id={third} step=extract name=pages.json from_run={first} result=copied")
    ]


@pytest.mark.parametrize("points_to", ["itself", "a-later-run"])
def test_a_chain_that_does_not_go_back_stops_at_once(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any, points_to: str
) -> None:
    """① 8: resumed_from_run_id 가 자기(또는 더 큰 id)면 사슬을 걷지 않는다 — 자기 키 get 하나·object_missing.
    find_run 을 세어(상한 10에서 멈춤) 끝없는 걷기를 단언으로 잡는다(pytest-timeout 이 없다)."""
    _, new = emptied(world, monkeypatch, django_capture_on_commit_callbacks)
    target = new if points_to == "itself" else new + 1000
    RunRow.for_company(world.company_id).filter(pk=new).update(resumed_from_run_id=target)
    asked: list[int] = []
    real = selectors.find_run

    def counted(*, company_id: int, run_id: int) -> Any:
        asked.append(run_id)
        if len(asked) > 10:
            raise AssertionError("사슬이 끝나지 않는다")
        return real(company_id=company_id, run_id=run_id)

    monkeypatch.setattr(selectors, "find_run", counted)
    execute(world, new)
    assert (row(world, new).status, row(world, new).error_code) == ("failed", "object_missing")
    assert run_gets(world) == [pages_key(world, new)]
    assert asked == [new]  # 잡기의 자기 조회 하나 — 사슬 조회 0


def test_a_previous_key_outside_the_company_is_never_read(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """① 9(회사 접두 방어 — BASE 의 갈고리 방어를 옮김): 앞 행의 키가 남의 회사 접두면 같은 바이트가 그 키에 있어도
    get 0·put 0·object_missing."""
    previous, new = emptied(world, monkeypatch, django_capture_on_commit_callbacks)
    foreign = f"runs/{world.other_company_id}/1/steps/extract/pages.json"
    world.storage.put(foreign, b"[1, 2]")
    RunFileRow.for_company(world.company_id).filter(run_id=previous).update(storage_key=foreign)
    execute(world, new)
    assert (row(world, new).status, row(world, new).error_code) == ("failed", "object_missing")
    assert foreign not in world.storage.get_calls
    assert world.storage.put_calls == []


def test_a_first_run_with_a_missing_step_object_reads_no_chain(
    world: World, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """① 10: 처음 실행(resumed_from 없음)의 단계 객체가 없으면 BASE 그대로 object_missing — 사슬 읽기 0(find_run 은
    잡기의 자기 조회 하나, run_files 는 _plan 의 하나)·옮김 로그 0.
    (쿼리 셈 대신 selector 부름을 센다 — P8 은 사슬이 비어 쿼리 수를 바꾸지 않는다.)"""
    run_id = new_run(world)
    asked: list[str] = []
    for name in ("find_run", "run_files"):
        real = getattr(selectors, name)

        def spy(*, _real: Any = real, _name: str = name, **kwargs: Any) -> Any:
            asked.append(_name)
            return _real(**kwargs)

        monkeypatch.setattr(selectors, name, spy)
    step_rows = RunStepRow.for_company(world.company_id)
    step_rows.filter(run_id=run_id, name="extract").update(
        status="done", data={"size": 1, "name": "x"}, done=1, total=1
    )
    RunFileRow.for_company(world.company_id).create(
        company_id=world.company_id,
        run_id=run_id,
        step="extract",
        name="pages.json",
        media_type="application/json",
        storage_key=pages_key(world, run_id),
        size_bytes=6,
        sha256=hashlib.sha256(b"[1, 2]").hexdigest(),
    )
    with caplog.at_level(logging.INFO, logger=tasks.__name__):
        execute(world, run_id)
    assert (row(world, run_id).status, row(world, run_id).error_code) == ("failed", "object_missing")
    assert asked == ["find_run", "run_files"]
    assert copy_lines(caplog) == []


def test_a_new_key_already_filled_is_not_carried_again(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """① 11: 새 키가 이미 있으면(① 의 요청 갈고리가 옮긴 뒤) 앞 키 get 0·새 키 put 0 — 두 길 겹침이 무해하다."""
    previous, new = resumed_from_failed(
        world, monkeypatch, django_capture_on_commit_callbacks, ProbeBinding(world.script)
    )
    world.storage.objects[pages_key(world, new)] = world.storage.objects[pages_key(world, previous)]
    world.storage.get_calls.clear()
    world.storage.put_calls.clear()
    execute(world, new)
    assert row(world, new).status == "done"
    assert pages_key(world, previous) not in world.storage.get_calls
    assert pages_key(world, new) not in world.storage.put_calls


def bare_first_with_file(inputs: BareInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    adapters.script.finished_steps.append("first")
    return StepOutput(
        data={"rows": inputs.options["rows"], "company": inputs.company_id},
        files=(OutputFile(name="rows.bin", media_type="application/octet-stream", content=b"ROWS"),),
    )


BARE_FILE_FLOW = make_flow(
    module="probe",
    id="probe.bare-file@1",
    input_shape="probe.options@1",
    inputs=BareInputs,
    adapters=ProbeAdapters,
    result_shapes=("probe.result@1",),
    output_files=(),
    steps=(FlowStep(name="first", run=bare_first_with_file), FlowStep(name="second", run=bare_second)),
)


def test_a_documentless_resumed_run_carries_its_step_file_too(
    world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """① 12: 문서 없는 흐름(ND1)의 이어 돌기도 새 키가 비었으면 앞 키에서 옮겨 done(문서 get 0)."""
    from esgapi.runs.service.actions import runs as actions

    binding = BareProbe(world.script)
    flows = FlowRegistry()
    flows.register(BARE_FILE_FLOW)
    bindings = BindingRegistry()
    bindings.register_documentless(BARE_FILE_FLOW.id, binding)
    for where in (tasks, actions):
        monkeypatch.setattr(where, "REGISTRY", flows)
        monkeypatch.setattr(where, "BINDINGS", bindings)

    def broken(i: int, _: ProbeAdapters) -> None:
        raise ValueError("지어낸 실패")

    world.script.before_item = broken
    previous = new_bare_run(world, flow=BARE_FILE_FLOW)
    execute(world, previous)
    assert (row(world, previous).status, row(world, previous).failed_step) == ("failed", "second")
    world.script.before_item = None
    world.script.finished_steps.clear()

    def ignore(**_: object) -> None:
        return None

    monkeypatch.setattr(hooks, "enqueue_run", ignore)
    with django_capture_on_commit_callbacks(execute=True):
        created = actions.create_run(
            company_id=world.company_id,
            actor_kind="service",
            actor_user_id=7,
            module="probe",
            flow_id=BARE_FILE_FLOW.id,
            document_id=None,
            options={},
            resume_from=previous,
            now=NOW,
        )
    assert isinstance(created, actions.RunCreated), created
    new = created.run.id
    old_key = file_key(company_id=world.company_id, run_id=previous, step="first", name="rows.bin")
    new_key = file_key(company_id=world.company_id, run_id=new, step="first", name="rows.bin")
    world.storage.objects.pop(new_key, None)
    world.storage.get_calls.clear()
    execute(world, new)
    assert row(world, new).status == "done"
    assert world.script.finished_steps == ["second"]
    assert world.storage.get_calls == [new_key, old_key]
    assert world.storage.objects[new_key][0] == b"ROWS"
