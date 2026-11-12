# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실행 경로 넷(runs/service/apis/runs.py)의 몸을 진짜 DB 로 잰다. 업무 층: 저장소는 가짜, 흐름·끼움은 시험 안의 가짜를
시험의 레지스트리에 단다(actions.REGISTRY·actions.BINDINGS 를 바꿔 끼움 — 프로세스의 것을 물들이지 않는다).

재는 것: 만들기의 검사 차례와 갈래(201·400·404·409·422 — 거절은 행 0), 이어 돌기(X1b-2b), 단계 행(선언 차례
pending), 커밋 뒤 쪽지 하나, 판 묶음, 목록(새 것 먼저·거르기 셋·쪽·남의 회사 0), 단건(단계·resultShapes·files),
내려받기(출력 파일만), 감사 줄 — **core_audit_events 의 행을 센다**(record_event 는 던지지 않으므로 반환값으로는
조용한 거절을 못 잡는다).
★ 무효 조건: 연결이 하나다(주인 역할, 테스트마다 되돌린다). 앱 역할의 경계는 보안 층
  tests/security/test_runs.py 가 잰다.
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import connection, transaction
from django.test import Client

from esgapi.core.flows.binding import (
    DOCUMENTLESS_OPTIONS_MAX_OCTETS,
    BindingRegistry,
    DocumentInput,
    RunContext,
    RunOptionsRejected,
)
from esgapi.core.flows.registry import FlowRegistry, make_flow
from esgapi.core.flows.types import Carried, FlowStep, StepContext, StepOutput
from esgapi.core.models import AuditEventRow, DocumentRow
from esgapi.core.resources import queue as hooks
from esgapi.core.resources.ports.storage import StorageDenied, StorageUnavailable
from esgapi.core.service.services import audit
from esgapi.core.service.services import documents as documents_services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.calc.keys import file_key
from esgapi.runs.models import RUN_OPTIONS_MAX_OCTETS, RunFileRow, RunResultRow, RunRow, RunStepRow
from esgapi.runs.service.actions import runs as actions
from esgapi.runs.service.schemas.runs import RunIn
from esgapi.runs.service.selectors.runs import FileRef, StepFound, step_output
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

STARTED = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
FINISHED = datetime(2026, 10, 19, 9, 5, tzinfo=UTC)


@dataclass(frozen=True)
class ProbeInputs:
    document: DocumentInput


@dataclass(frozen=True)
class ProbeAdapters:
    ctx: RunContext


def _step(inputs: ProbeInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"results": []})


def _flow(module: str, flow_id: str, steps: tuple[str, ...]) -> Any:
    return make_flow(
        module=module,
        id=flow_id,
        input_shape="probe.document@1",
        inputs=ProbeInputs,
        adapters=ProbeAdapters,
        result_shapes=("probe.result@1",),
        output_files=(),
        steps=tuple(FlowStep(name=name, run=_step) for name in steps),
    )


PROBE = _flow("probe", "probe.three@1", ("extract", "judge", "report"))
PROBE_TWO = _flow("probe", "probe.two@1", ("first", "second"))
UNBOUND = _flow("probe", "probe.unbound@1", ("only",))  # 흐름은 있으나 끼움이 없다
OTHER = _flow("other", "other.one@1", ("only",))  # 남의 모듈의 흐름


class ProbeBinding:
    def check_options(self, options: Mapping[str, object]) -> None:
        if options.get("pages") == "bad":
            raise RunOptionsRejected("쪽 범위를 읽을 수 없다")

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> object:
        return ProbeInputs(document=document)

    def adapters(self, ctx: RunContext) -> object:
        return ProbeAdapters(ctx=ctx)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {"terms": "probe-terms@2", "flow": "끼움이 덮으려는 값"}


@dataclass
class World:
    company_a: int
    company_b: int
    storage: FakeStorage
    sent: list[dict[str, Any]]


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    flows = FlowRegistry()
    for flow in (PROBE, PROBE_TWO, UNBOUND, OTHER):
        flows.register(flow)
    flows.set_default("probe", PROBE.id)
    bindings = BindingRegistry()
    bindings.register(PROBE.id, ProbeBinding())
    bindings.register(PROBE_TWO.id, ProbeBinding())
    bindings.register(OTHER.id, ProbeBinding())
    monkeypatch.setattr(actions, "REGISTRY", flows)
    monkeypatch.setattr(actions, "BINDINGS", bindings)
    sent: list[dict[str, Any]] = []

    def spy(**kwargs: Any) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(hooks, "enqueue_run", spy)
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1000)
    return World(*companies, storage=storage, sent=sent)


def document(company_id: int, *, status: str = "uploaded", name: str = "지은 보고서.pdf") -> int:
    row = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="1",
        file_name=name,
        storage_key=f"companies/{company_id}/documents/{name}-{DocumentRow.unscoped.count()}/original",
        size_bytes=10,
        status=status,
    )
    return row.pk


def create(client: Client, body: dict[str, Any]) -> Any:
    return client.post("/api/runs", data=body, content_type="application/json")


def error_of(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def run_lines(company_id: int) -> list[AuditEventRow]:
    return list(AuditEventRow.for_company(company_id).filter(action="run"))


# ── 만들기 ────────────────────────────────────────────────────────────


def test_create_makes_a_queued_run_with_pending_steps_and_one_message(
    client: Client, world: World, django_capture_on_commit_callbacks: Any
) -> None:
    login(client)
    doc = document(world.company_a)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = create(client, {"module": "probe", "documentId": doc, "options": {"pages": "1-3"}})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    run = RunRow.for_company(world.company_a).get(pk=body["id"])
    assert (run.document_id, run.module, run.flow_id, run.status, run.attempts, run.purpose) == (
        doc,
        "probe",
        PROBE.id,
        "queued",
        0,
        "service",
    )
    assert run.options == {"pages": "1-3"}
    # 판 묶음: 끼움의 몫 + 흐름 id@판(「flow」 열쇠는 끼움이 덮지 못한다), aiSetting 은 없다
    assert run.versions == {"terms": "probe-terms@2", "flow": PROBE.id}
    assert run.started_at is None and run.finished_at is None and run.resumed_from_run_id is None
    steps = RunStepRow.for_company(world.company_a).filter(run_id=run.pk).order_by("position")
    assert [(s.name, s.position, s.status, s.done, s.data) for s in steps] == [
        ("extract", 0, "pending", None, None),
        ("judge", 1, "pending", None, None),
        ("report", 2, "pending", None, None),
    ]
    assert len(callbacks) == 1
    assert world.sent == [{"company_id": world.company_a, "run_id": run.pk}]
    # 감사 줄 하나(행을 센다)
    lines = run_lines(world.company_a)
    assert [
        (r.actor_kind, r.actor_user_id, r.event, r.result, r.target_kind, r.target_id, r.target_label) for r in lines
    ] == [("service", run.created_by_user_id, "run_created", "success", "run", run.pk, "지은 보고서.pdf")]
    assert run.created_by_user_id >= 1  # 세션의 사람(users.pk)


def test_create_without_flow_id_uses_the_module_default_and_flow_id_picks_another(client: Client, world: World) -> None:
    login(client)
    doc = document(world.company_a)
    default = create(client, {"module": "probe", "documentId": doc})
    picked = create(client, {"module": "probe", "flowId": PROBE_TWO.id, "documentId": doc})
    assert (default.status_code, picked.status_code) == (201, 201)
    flows = {r.pk: r.flow_id for r in RunRow.for_company(world.company_a).all()}
    assert flows == {default.json()["id"]: PROBE.id, picked.json()["id"]: PROBE_TWO.id}
    two = RunStepRow.for_company(world.company_a).filter(run_id=picked.json()["id"]).order_by("position")
    assert [s.name for s in two] == ["first", "second"]


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("missing_document", (404, "NOT_FOUND")),
        ("other_company_document", (404, "NOT_FOUND")),
        ("not_uploaded", (409, "DOCUMENT_NOT_UPLOADED")),
        ("unknown_module", (422, "UNKNOWN_FLOW")),
        ("unknown_flow", (422, "UNKNOWN_FLOW")),
        ("other_module_flow", (422, "UNKNOWN_FLOW")),
        ("no_binding", (422, "FLOW_NOT_RUNNABLE")),
        ("options_rejected", (400, "INVALID_OPTIONS")),
        ("options_too_large", (400, "INVALID_OPTIONS")),
        ("resume_missing", (404, "NOT_FOUND")),
    ],
)
def test_create_refusals_write_nothing(
    client: Client,
    world: World,
    django_capture_on_commit_callbacks: Any,
    case: str,
    expected: tuple[int, str],
) -> None:
    login(client)
    mine = document(world.company_a)
    bodies: dict[str, dict[str, Any]] = {
        "missing_document": {"module": "probe", "documentId": mine + 1000},
        "other_company_document": {"module": "probe", "documentId": document(world.company_b)},
        "not_uploaded": {"module": "probe", "documentId": document(world.company_a, status="awaiting_upload")},
        "unknown_module": {"module": "nothing", "documentId": mine},
        "unknown_flow": {"module": "probe", "flowId": "probe.none@1", "documentId": mine},
        "other_module_flow": {"module": "probe", "flowId": OTHER.id, "documentId": mine},
        "no_binding": {"module": "probe", "flowId": UNBOUND.id, "documentId": mine},
        "options_rejected": {"module": "probe", "documentId": mine, "options": {"pages": "bad"}},
        "options_too_large": {"module": "probe", "documentId": mine, "options": {"x": "a" * RUN_OPTIONS_MAX_OCTETS}},
        "resume_missing": {"module": "probe", "documentId": mine, "resumeFromRunId": 1},
    }
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = create(client, bodies[case])
    assert error_of(response) == expected
    assert (RunRow.unscoped.count(), RunStepRow.unscoped.count()) == (0, 0)
    assert (len(callbacks), world.sent) == (0, [])
    assert AuditEventRow.unscoped.filter(action="run").count() == 0
    if case == "options_rejected":
        assert response.json()["error"]["message"] == "쪽 범위를 읽을 수 없다"  # 끼움의 글 그대로
    # 분모: 같은 세션·같은 회사의 문서로는 만들어진다
    assert create(client, {"module": "probe", "documentId": mine}).status_code == 201


def test_the_create_order_puts_the_document_before_the_flow(client: Client, world: World) -> None:
    """차례(X1b-2b 처분 ⑫): 남의 문서 + 끼움 없는 흐름이면 404(문서가 먼저), 올라오지 않은 문서 + 모르는 모듈이면
    409, resumeFromRunId 가 있어도 문서 거절이 먼저(남의 문서 → 404)."""
    login(client)
    theirs = document(world.company_b)
    pending = document(world.company_a, status="awaiting_upload")
    assert error_of(create(client, {"module": "probe", "flowId": UNBOUND.id, "documentId": theirs})) == (
        404,
        "NOT_FOUND",
    )
    assert error_of(create(client, {"module": "nothing", "documentId": pending})) == (409, "DOCUMENT_NOT_UPLOADED")
    assert error_of(
        create(client, {"module": "probe", "flowId": UNBOUND.id, "documentId": theirs, "resumeFromRunId": 9})
    ) == (404, "NOT_FOUND")


def test_a_refused_audit_line_does_not_undo_the_run(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """감사의 DB 오류(꼴 검사를 비켜 CHECK 에 걸리는 값)는 세이브포인트만 되돌린다: 실행은 201·행 있음·감사 0."""
    login(client)
    doc = document(world.company_a)
    real = actions.record_event

    def accept(**_: Any) -> None:
        return None

    monkeypatch.setattr(audit, "check_event", accept)

    def bad_action(**kwargs: Any) -> Any:
        kwargs["action"] = "launch"  # core_audit_events 의 행동 CHECK(아홉) 밖
        return real(**kwargs)

    monkeypatch.setattr(actions, "record_event", bad_action)
    response = create(client, {"module": "probe", "documentId": doc})
    assert response.status_code == 201
    assert RunRow.for_company(world.company_a).filter(pk=response.json()["id"]).exists()
    assert RunStepRow.for_company(world.company_a).filter(run_id=response.json()["id"]).count() == 3
    assert AuditEventRow.unscoped.count() == 0
    # 분모: 바꿔 끼운 것을 되돌리면 줄이 생긴다(위의 0줄은 바꾼 행동 값을 DB 의 CHECK 가 거절한 것이다)
    monkeypatch.setattr(actions, "record_event", real)
    assert create(client, {"module": "probe", "documentId": doc}).status_code == 201
    assert AuditEventRow.unscoped.filter(action="run").count() == 1


# ── 이어서 돌리기(resumeFromRunId — X1b-2b) ─────────────────────────────

PAGES = b"[1, 2] (synthetic step file)"
OLD_VERSIONS: dict[str, object] = {"terms": "probe-terms@1", "flow": PROBE.id}  # 끼움의 지금 판(@2)과 다르다


class StrictBinding(ProbeBinding):
    """그린워싱처럼 빈 옵션을 거절하는 끼움(요청 {} 이 앞 실행의 옵션으로 검사되는지 잰다)."""

    def check_options(self, options: Mapping[str, object]) -> None:
        super().check_options(options)
        if "pages" not in options:
            raise RunOptionsRejected("쪽 범위가 없다")


def strict(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    bindings = BindingRegistry()
    bindings.register(PROBE.id, StrictBinding())
    bindings.register(PROBE_TWO.id, StrictBinding())
    monkeypatch.setattr(actions, "BINDINGS", bindings)


def failed_run(
    world: World,
    doc: int,
    *,
    company_id: int | None = None,
    status: str = "failed",
    options: dict[str, object] | None = None,
    steps: tuple[str, ...] = PROBE.steps,
    resumed_from: int | None = None,
) -> int:
    """앞 실행 하나: extract 는 끝남(data·단계 파일 pages.json — 바이트는 가짜 저장소), judge 는 실패(partial),
    report 는 pending. 주인 역할로 손으로 만든다(실행기의 꼴)."""
    company = world.company_a if company_id is None else company_id
    run = RunRow.for_company(company).create(
        company_id=company,
        document_id=doc,
        module="probe",
        flow_id=PROBE.id,
        options={"pages": "1-3"} if options is None else options,
        versions=OLD_VERSIONS,
        status=status,
        attempts=1,
        created_by_user_id=1,
        started_at=STARTED,
        finished_at=FINISHED if status in ("failed", "done") else None,
        failed_step="judge" if status == "failed" else None,
        error_code="step_error" if status == "failed" else None,
        resumed_from_run_id=resumed_from,
    )
    states = {0: ("done", {"size": 3, "name": "x"}, None), 1: ("failed", None, {"items": [0]})}
    for position, name in enumerate(steps):
        state, data, partial = states.get(position, ("pending", None, None))
        RunStepRow.for_company(company).create(
            company_id=company,
            run_id=run.pk,
            name=name,
            position=position,
            status=state,
            done=1 if state == "done" else None,
            total=1 if state == "done" else None,
            data=data,
            partial=partial,
            started_at=STARTED if state != "pending" else None,
            finished_at=FINISHED if state == "done" else None,
        )
    key = file_key(company_id=company, run_id=run.pk, step=steps[0], name="pages.json")
    world.storage.put(key, PAGES)
    RunFileRow.for_company(company).create(
        company_id=company,
        run_id=run.pk,
        step=steps[0],
        name="pages.json",
        media_type="application/json",
        storage_key=key,
        size_bytes=len(PAGES),
        sha256=hashlib.sha256(PAGES).hexdigest(),
    )
    return run.pk


def snapshot(company_id: int, run_id: int) -> tuple[object, ...]:
    """앞 실행의 행·단계·결과·파일 전부(바뀜 0 을 견준다)."""
    run = RunRow.for_company(company_id).filter(pk=run_id).values().get()
    steps = list(RunStepRow.for_company(company_id).filter(run_id=run_id).order_by("position").values())
    results = list(RunResultRow.for_company(company_id).filter(run_id=run_id).values())
    files = list(RunFileRow.for_company(company_id).filter(run_id=run_id).order_by("id").values())
    return run, steps, results, files


def resume_body(doc: int, previous: int, **extra: object) -> dict[str, Any]:
    return {"module": "probe", "documentId": doc, "resumeFromRunId": previous, **extra}


def test_resume_copies_the_finished_steps_and_files_and_keeps_the_previous_versions_and_options(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """요청 옵션 {} 은 앞 실행의 옵션으로 검사된다(빈 옵션을 거절하는 끼움). versions 는 끼움의 지금 판(@2)이 아니라
    앞 것(@1). 끝난 단계 extract 는 done·data·시각 그대로, 실패한 judge 의 partial 은 옮기지 않는다.
    단계 파일은 새 키(바이트는 실행기가 옮김 — RC1)."""
    strict(world, monkeypatch)
    login(client)
    doc = document(world.company_a)
    previous = failed_run(world, doc)
    before = snapshot(world.company_a, previous)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = create(client, resume_body(doc, previous))
    assert response.status_code == 201, response.content.decode()
    new = response.json()["id"]
    run = RunRow.for_company(world.company_a).get(pk=new)
    assert (run.status, run.resumed_from_run_id, run.flow_id, run.document_id) == ("queued", previous, PROBE.id, doc)
    assert run.options == {"pages": "1-3"}
    assert run.versions == OLD_VERSIONS
    steps = list(RunStepRow.for_company(world.company_a).filter(run_id=new).order_by("position"))
    assert [(s.name, s.status, s.done, s.total, s.data, s.partial) for s in steps] == [
        ("extract", "done", 1, 1, {"size": 3, "name": "x"}, None),
        ("judge", "pending", None, None, None, None),
        ("report", "pending", None, None, None, None),
    ]
    assert (steps[0].started_at, steps[0].finished_at) == (STARTED, FINISHED)
    assert (steps[1].started_at, steps[1].finished_at) == (None, None)
    (copied,) = RunFileRow.for_company(world.company_a).filter(run_id=new)
    assert copied.storage_key == f"runs/{world.company_a}/{new}/steps/extract/pages.json"  # 키 = 새 id
    assert (copied.step, copied.name, copied.media_type, copied.size_bytes, copied.sha256) == (
        "extract",
        "pages.json",
        "application/json",
        len(PAGES),
        hashlib.sha256(PAGES).hexdigest(),
    )
    assert copied.storage_key not in world.storage.objects  # 바이트는 실행기 _plan 이 옮긴다(RC1)
    assert world.storage.put_calls == []
    assert [k for k in world.storage.get_calls if not k.startswith("companies/")] == []  # 문서 밖 get 0
    # 옮긴 단계는 새 실행의 것으로 읽힌다(step_output — 모듈의 입구)
    assert step_output(company_id=world.company_a, run_id=new, step="extract") == StepFound(
        data={"size": 3, "name": "x"},
        files=(FileRef(name="pages.json", media_type="application/json", size_bytes=len(PAGES)),),
    )
    assert len(callbacks) == 1
    assert world.sent == [{"company_id": world.company_a, "run_id": new}]
    assert [(r.event, r.target_id) for r in run_lines(world.company_a)] == [("run_created", new)]
    assert snapshot(world.company_a, previous) == before  # 앞 실행 바뀜 0
    old_key = file_key(company_id=world.company_a, run_id=previous, step="extract", name="pages.json")
    assert world.storage.objects[old_key][0] == PAGES


def test_resume_sends_with_the_new_key_empty_and_no_store_call(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """RC1: 커밋 뒤 갈고리는 쪽지 하나뿐이다 — 보낼 때 새 키는 비었고 저장소 부름은 0(⑬b 의 옮김 → 보내기 차례가
    없다)."""
    login(client)
    doc = document(world.company_a)
    previous = failed_run(world, doc)
    world.storage.get_calls.clear()
    seen: list[tuple[bool, int]] = []

    def spy(**kwargs: Any) -> None:
        key = file_key(company_id=world.company_a, run_id=kwargs["run_id"], step="extract", name="pages.json")
        calls = world.storage.get_calls + world.storage.put_calls + world.storage.head_calls
        seen.append((key in world.storage.objects, len(calls)))

    monkeypatch.setattr(hooks, "enqueue_run", spy)
    with django_capture_on_commit_callbacks(execute=True):
        assert create(client, resume_body(doc, previous)).status_code == 201
    assert seen == [(False, 0)]


def call_create(world: World, *, document_id: int, resume_from: int | None) -> object:
    return actions.create_run(
        company_id=world.company_a,
        actor_kind="service",
        actor_user_id=7,
        module="probe",
        flow_id=None,
        document_id=document_id,
        options={},
        resume_from=resume_from,
        now=FINISHED,
    )


def test_a_rolled_back_block_copies_nothing(world: World, django_capture_on_commit_callbacks: Any) -> None:
    """⑬b(B1): create_run 을 감싼 블록이 되돌려지면 커밋 뒤 갈고리도 버려진다 — 저장소 get·put 0, 쪽지 0, 행 0.
    분모: 되돌리지 않으면 갈고리 하나·쪽지 하나(저장소 put 은 0 — 바이트는 실행기가 옮긴다, RC1)."""
    doc = document(world.company_a)
    previous = failed_run(world, doc)
    runs_before = RunRow.for_company(world.company_a).count()
    world.storage.get_calls.clear()
    with django_capture_on_commit_callbacks(execute=True) as callbacks, transaction.atomic():
        made = call_create(world, document_id=doc, resume_from=previous)
        assert isinstance(made, actions.RunCreated)
        transaction.set_rollback(True)
    assert (world.storage.put_calls, world.storage.get_calls, world.sent, len(callbacks)) == ([], [], [], 0)
    assert RunRow.for_company(world.company_a).count() == runs_before
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        made = call_create(world, document_id=doc, resume_from=previous)
    assert isinstance(made, actions.RunCreated)
    assert (len(callbacks), len(world.sent)) == (1, 1)
    assert world.storage.put_calls == []


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("missing", (404, "NOT_FOUND")),
        ("other_company", (404, "NOT_FOUND")),
        ("other_document", (422, "RESUME_MISMATCH")),
        ("other_flow", (422, "RESUME_MISMATCH")),
        ("other_steps", (422, "RESUME_MISMATCH")),
        ("other_options", (422, "RESUME_MISMATCH")),
        ("queued", (409, "RESUME_NOT_FAILED")),
        ("processing", (409, "RESUME_NOT_FAILED")),
        ("done", (409, "RESUME_NOT_FAILED")),
        ("child_queued", (409, "RESUME_ALREADY")),
        ("child_processing", (409, "RESUME_ALREADY")),
        ("child_done", (409, "RESUME_ALREADY")),
        ("previous_options_rejected", (400, "INVALID_OPTIONS")),
    ],
)
def test_resume_refusals_write_nothing_and_leave_the_previous_run(
    client: Client,
    world: World,
    django_capture_on_commit_callbacks: Any,
    case: str,
    expected: tuple[int, str],
) -> None:
    login(client)
    doc = document(world.company_a)
    other_doc = document(world.company_a, name="다른 보고서.pdf")
    previous = failed_run(world, doc, options={"pages": "bad"} if case == "previous_options_rejected" else None)
    body = resume_body(doc, previous)
    if case == "missing":
        body = resume_body(doc, previous + 1000)
    elif case == "other_company":
        body = resume_body(doc, failed_run(world, document(world.company_b), company_id=world.company_b))
    elif case == "other_document":
        body = resume_body(other_doc, previous)
    elif case == "other_flow":
        body = resume_body(doc, previous, flowId=PROBE_TWO.id)
    elif case == "other_steps":
        body = resume_body(doc, failed_run(world, doc, steps=("extract", "judge", "later")))
    elif case == "other_options":
        body = resume_body(doc, previous, options={"pages": "9"})
    elif case in ("queued", "processing", "done"):
        body = resume_body(doc, failed_run(world, doc, status=case))
    elif case.startswith("child_"):
        failed_run(world, doc, status=case.removeprefix("child_"), resumed_from=previous)
    before = {r: snapshot(company, r) for company, r in rows_of(world)}
    counts = (RunRow.unscoped.count(), RunStepRow.unscoped.count(), RunFileRow.unscoped.count())
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = create(client, body)
    assert error_of(response) == expected
    assert (RunRow.unscoped.count(), RunStepRow.unscoped.count(), RunFileRow.unscoped.count()) == counts
    assert (len(callbacks), world.sent, world.storage.put_calls) == (0, [], [])
    assert AuditEventRow.unscoped.filter(action="run").count() == 0
    assert {r: snapshot(company, r) for company, r in rows_of(world)} == before
    if case.startswith("other_") and case != "other_company":
        assert response.json()["error"]["message"].startswith("앞 실행")  # 어긋난 칸은 message 에만
    # 분모: 같은 세션·같은 문서로 처음부터 만들기는 된다
    assert create(client, {"module": "probe", "documentId": doc}).status_code == 201


def rows_of(world: World) -> list[tuple[int, int]]:
    return [(r.company_id, r.pk) for company in (world.company_a, world.company_b) for r in RunRow.for_company(company)]


def test_a_failed_child_does_not_block_and_a_second_resume_is_refused(
    client: Client, world: World, django_capture_on_commit_callbacks: Any
) -> None:
    """경합의 차례: 같은 앞 실행을 두 번 이어 돌리면 둘째는 409 RESUME_ALREADY(lock_run 이 줄 세운다 — 이 층은 연결이
    하나라 차례로 잰다). 실패한 자식은 막지 않는다."""
    login(client)
    doc = document(world.company_a)
    previous = failed_run(world, doc)
    failed_run(world, doc, status="failed", resumed_from=previous)  # 실패한 자식
    with django_capture_on_commit_callbacks(execute=True):
        first = create(client, resume_body(doc, previous))
    assert first.status_code == 201
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        second = create(client, resume_body(doc, previous))
    assert error_of(second) == (409, "RESUME_ALREADY")
    assert len(callbacks) == 0
    assert RunRow.for_company(world.company_a).filter(resumed_from_run_id=previous).count() == 2


BIG = 48 * 2**20  # 지어낸 큰 단계 파일의 행 크기(바이트는 심지 않는다 — 요청은 읽지 않는다)


def test_resume_creation_never_calls_the_store(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """RC1 ② 9: 이어 돌기 만들기(옮길 파일 1, 행 48 MiB)는 저장소를 한 번도 부르지 않는다 — default_storage 부름 0·
    get·put·head 0·쪽지 하나. (BASE 의 「처음 만들기는 저장소를 읽지 않는다」 분모를 이어 돌기까지 넓힘.)"""
    login(client)
    doc = document(world.company_a)
    previous = failed_run(world, doc)
    RunFileRow.for_company(world.company_a).filter(run_id=previous).update(size_bytes=BIG)
    world.storage.get_calls.clear()
    asked: list[int] = []

    def counted() -> FakeStorage:
        asked.append(1)
        return world.storage

    monkeypatch.setattr(documents_services, "default_storage", counted)
    with django_capture_on_commit_callbacks(execute=True):
        response = create(client, resume_body(doc, previous))
    assert response.status_code == 201
    new = response.json()["id"]
    assert asked == []
    assert (world.storage.get_calls, world.storage.put_calls, world.storage.head_calls) == ([], [], [])
    assert world.sent == [{"company_id": world.company_a, "run_id": new}]
    (row,) = RunFileRow.for_company(world.company_a).filter(run_id=new)
    assert row.size_bytes == BIG


def test_resume_creation_is_201_with_one_message_even_when_the_store_is_down(
    client: Client, world: World, django_capture_on_commit_callbacks: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """RC1 ② 10: 저장소가 닿지 않아도(get·put 다) 만들기는 BASE 와 같은 201 몸·쪽지 하나·옮김 로그 0."""
    login(client)
    doc = document(world.company_a)
    previous = failed_run(world, doc)
    world.storage.fail_with = StorageUnavailable("지어낸 끊김")
    world.storage.put_fail_with = StorageUnavailable("지어낸 쓰기 끊김")
    with caplog.at_level(logging.INFO), django_capture_on_commit_callbacks(execute=True):
        response = create(client, resume_body(doc, previous))
    assert response.status_code == 201
    new = response.json()["id"]
    assert response.json() == {"id": new, "status": "queued"}
    assert world.sent == [{"company_id": world.company_a, "run_id": new}]
    assert [r.getMessage() for r in caplog.records if r.getMessage().startswith("run_resume_copy")] == []


def test_a_resume_from_the_request_to_the_executor_carries_the_bytes(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """RC1 ② 11: 요청으로 이어 돌기를 만들고 실행기를 돌리면 done·새 키 바이트 = 앞 바이트(probe 흐름)·앞 키 그대로."""
    from esgapi.runs import tasks

    def finished(inputs: ProbeInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
        return StepOutput(data={"results": [{"schemaVersion": "probe.result@1"}]})

    # 실행기에는 같은 id·단계의 흐름을 끝 단계만 결과를 내게 달아 끝까지 돌린다(만들기의 등록부는 그대로)
    flows = FlowRegistry()
    flows.register(
        make_flow(
            module="probe",
            id=PROBE.id,
            input_shape="probe.document@1",
            inputs=ProbeInputs,
            adapters=ProbeAdapters,
            result_shapes=("probe.result@1",),
            output_files=(),
            steps=(
                FlowStep(name="extract", run=_step),
                FlowStep(name="judge", run=_step),
                FlowStep(name="report", run=finished),
            ),
        )
    )
    monkeypatch.setattr(tasks, "REGISTRY", flows)
    monkeypatch.setattr(tasks, "BINDINGS", actions.BINDINGS)
    login(client)
    doc = document(world.company_a)
    document_row = DocumentRow.for_company(world.company_a).get(pk=doc)
    world.storage.put(document_row.storage_key, b"%PDF-1.7 (synthetic)")
    previous = failed_run(world, doc)
    with django_capture_on_commit_callbacks(execute=True):
        response = create(client, resume_body(doc, previous))
    assert response.status_code == 201
    new = response.json()["id"]
    new_key = file_key(company_id=world.company_a, run_id=new, step="extract", name="pages.json")
    old_key = file_key(company_id=world.company_a, run_id=previous, step="extract", name="pages.json")
    assert new_key not in world.storage.objects

    class Task:
        def retry(self, **kwargs: Any) -> Exception:
            raise AssertionError(f"다시 넣기를 청하지 않아야 한다: {kwargs}")

    tasks.execute_run(Task(), company_id=str(world.company_a), run_id=str(new))
    run = RunRow.for_company(world.company_a).get(pk=new)
    assert (run.status, run.error_code) == ("done", None)
    assert world.storage.objects[new_key][0] == PAGES
    assert world.storage.objects[old_key][0] == PAGES


# ── 목록 ──────────────────────────────────────────────────────────────


def made_run(company_id: int, doc: int, *, module: str = "probe", status: str = "queued") -> int:
    row = RunRow.for_company(company_id).create(
        company_id=company_id,
        document_id=doc,
        module=module,
        flow_id=PROBE.id if module == "probe" else OTHER.id,
        status=status,
        created_by_user_id=1,
    )
    return row.pk


def test_list_is_newest_first_filtered_paged_and_only_mine(client: Client, world: World) -> None:
    login(client)
    doc, other_doc = document(world.company_a), document(world.company_a, name="다른 보고서.pdf")
    first = made_run(world.company_a, doc)
    second = made_run(world.company_a, other_doc, status="done")
    third = made_run(world.company_a, doc, module="other", status="failed")
    theirs = made_run(world.company_b, document(world.company_b))

    page = client.get("/api/runs").json()
    assert (page["count"], page["isNext"]) == (3, False)
    assert [r["id"] for r in page["results"]] == [third, second, first]  # 같은 시각이면 id 내림
    item = page["results"][0]
    assert set(item) == {"id", "module", "flowId", "documentId", "documentName", "status", "createdAt", "finishedAt"}
    assert (item["module"], item["flowId"], item["documentId"], item["status"]) == ("other", OTHER.id, doc, "failed")
    # 줄마다 그 실행의 문서 이름(X1b-2a — 처분 ⑪)
    assert [r["documentName"] for r in page["results"]] == ["지은 보고서.pdf", "다른 보고서.pdf", "지은 보고서.pdf"]

    def ids(query: str) -> list[int]:
        return [r["id"] for r in client.get(f"/api/runs?{query}").json()["results"]]

    assert ids("module=probe") == [second, first]
    assert ids("status=done") == [second]
    assert ids(f"documentId={doc}") == [third, first]
    assert ids(f"module=probe&documentId={doc}") == [first]
    one = client.get("/api/runs?limit=1&offset=1").json()
    assert (one["count"], one["isNext"], [r["id"] for r in one["results"]]) == (3, True, [second])
    assert theirs not in ids("limit=100")
    # 분모: B 의 세션으로 읽으면 B 의 것 하나
    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    assert [(r["id"], r["documentName"]) for r in other.get("/api/runs").json()["results"]] == [
        (theirs, "지은 보고서.pdf")
    ]


def test_two_requests_without_options_get_their_own_empty_objects() -> None:
    """RunIn.options 의 기본 {} 는 요청마다 새 객체다(pydantic 이 기본값을 복사 — X1b-2a, default_factory 를 걷음)."""
    first = RunIn.model_validate({"module": "probe", "documentId": 1})
    second = RunIn.model_validate({"module": "probe", "documentId": 1})
    assert first.options == second.options == {}
    assert first.options is not second.options
    first.options["pages"] = "1"
    assert second.options == {}
    assert RunIn.model_validate({"module": "probe", "documentId": 1}).options == {}


# ── 단건 ──────────────────────────────────────────────────────────────


def test_get_shows_steps_shapes_and_output_files(client: Client, world: World) -> None:
    login(client)
    doc = document(world.company_a)
    created = create(client, {"module": "probe", "documentId": doc, "options": {"pages": "2"}}).json()["id"]
    fresh = client.get(f"/api/runs/{created}").json()
    assert [(s["step"], s["status"], s["done"], s["total"]) for s in fresh["steps"]] == [
        ("extract", "pending", None, None),
        ("judge", "pending", None, None),
        ("report", "pending", None, None),
    ]
    assert (fresh["status"], fresh["options"], fresh["resultShapes"], fresh["files"]) == (
        "queued",
        {"pages": "2"},
        [],
        [],
    )
    assert (fresh["startedAt"], fresh["finishedAt"], fresh["failedStep"], fresh["resumedFromRunId"]) == (
        None,
        None,
        None,
        None,
    )

    # 실행기가 쓴 꼴을 손으로: 단계 둘 끝남·하나 실패, 결과 둘, 단계 파일 하나·출력 파일 하나
    a = world.company_a
    RunRow.for_company(a).filter(pk=created).update(
        status="failed", failed_step="report", error_code="step_error", error_message="단계가 실패했다"
    )
    RunStepRow.for_company(a).filter(run_id=created, name="judge").update(status="done", done=3, total=4)
    RunResultRow.for_company(a).create(company_id=a, run_id=created, position=1, schema_version="probe.b@1", body={})
    RunResultRow.for_company(a).create(company_id=a, run_id=created, position=0, schema_version="probe.a@1", body={})
    for step, name in (("extract", "pages.json"), (None, "report.bin")):
        RunFileRow.for_company(a).create(
            company_id=a,
            run_id=created,
            step=step,
            name=name,
            media_type="application/octet-stream",
            storage_key=f"runs/{a}/{created}/{step or 'out'}/{name}",
            size_bytes=1,
            sha256="0" * 64,
        )
    seen = client.get(f"/api/runs/{created}").json()
    assert (seen["status"], seen["failedStep"], seen["errorCode"], seen["errorMessage"]) == (
        "failed",
        "report",
        "step_error",
        "단계가 실패했다",
    )
    assert seen["steps"][1] == {"step": "judge", "status": "done", "done": 3, "total": 4, "segments": None}  # RM1b 장벽
    assert seen["resultShapes"] == ["probe.a@1", "probe.b@1"]  # 결과 행의 차례
    assert seen["files"] == ["report.bin"]  # 출력 파일만(단계 산출 파일은 싣지 않는다)


def test_get_of_another_company_or_a_missing_run_is_404(client: Client, world: World) -> None:
    login(client)
    theirs = made_run(world.company_b, document(world.company_b))
    mine = made_run(world.company_a, document(world.company_a))
    assert error_of(client.get(f"/api/runs/{theirs}")) == (404, "NOT_FOUND")
    assert error_of(client.get(f"/api/runs/{mine + theirs + 1}")) == (404, "NOT_FOUND")
    assert client.get(f"/api/runs/{mine}").status_code == 200  # 분모


# ── 내려받기 ──────────────────────────────────────────────────────────


def stored_file(world: World, company_id: int, run_id: int, *, step: str | None, name: str, data: bytes) -> None:
    key = f"runs/{company_id}/{run_id}/{step or 'out'}/{name}"
    world.storage.put(key, data)
    RunFileRow.for_company(company_id).create(
        company_id=company_id,
        run_id=run_id,
        step=step,
        name=name,
        media_type="application/vnd.ms-excel",
        storage_key=key,
        size_bytes=len(data),
        sha256="0" * 64,
    )


def download_lines(company_id: int) -> list[AuditEventRow]:
    return list(AuditEventRow.for_company(company_id).filter(action="download"))


def test_download_gives_the_output_file_bytes_and_one_audit_line(client: Client, world: World) -> None:
    login(client)
    run = made_run(world.company_a, document(world.company_a))
    stored_file(world, world.company_a, run, step=None, name="report.xls", data=b"XLS-BYTES")
    response = client.get(f"/api/runs/{run}/files/report.xls")
    assert response.status_code == 200
    assert response.content == b"XLS-BYTES"
    assert response["Content-Type"] == "application/vnd.ms-excel"
    assert response["Content-Disposition"] == 'attachment; filename="report.xls"'
    lines = download_lines(world.company_a)
    assert [(r.actor_kind, r.event, r.result, r.target_kind, r.target_id, r.target_label) for r in lines] == [
        ("service", "run_file_downloaded", "success", "run", run, "report.xls")
    ]
    assert lines[0].actor_user_id is not None and lines[0].actor_user_id >= 1


def test_download_refuses_step_files_other_companies_and_unknown_names(client: Client, world: World) -> None:
    login(client)
    run = made_run(world.company_a, document(world.company_a))
    stored_file(world, world.company_a, run, step="extract", name="pages.json", data=b"[1]")
    theirs = made_run(world.company_b, document(world.company_b))
    stored_file(world, world.company_b, theirs, step=None, name="report.xls", data=b"THEIRS")
    assert error_of(client.get(f"/api/runs/{run}/files/pages.json")) == (404, "NOT_FOUND")  # 단계 산출 파일
    assert error_of(client.get(f"/api/runs/{theirs}/files/report.xls")) == (404, "NOT_FOUND")  # 남의 회사
    assert error_of(client.get(f"/api/runs/{run}/files/none.xls")) == (404, "NOT_FOUND")
    assert AuditEventRow.unscoped.filter(action="download").count() == 0
    # 분모: 출력 파일이면 내준다
    stored_file(world, world.company_a, run, step=None, name="pages.json", data=b"OUT")
    assert client.get(f"/api/runs/{run}/files/pages.json").content == b"OUT"


def test_download_when_the_store_cannot_be_reached_is_503_without_an_audit_line(client: Client, world: World) -> None:
    login(client)
    run = made_run(world.company_a, document(world.company_a))
    stored_file(world, world.company_a, run, step=None, name="report.xls", data=b"X")
    world.storage.fail_with = StorageUnavailable("닿지 못함(시험)")
    assert client.get(f"/api/runs/{run}/files/report.xls").status_code == 503
    assert AuditEventRow.unscoped.filter(action="download").count() == 0


def test_download_when_the_store_refuses_or_is_missing_is_its_503_without_an_audit_line(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RF1: 바이트 읽기를 runs/service/services/files.py 로 옮겨도 거절·저장소 없음의 code 가 그대로다."""
    login(client)
    run = made_run(world.company_a, document(world.company_a))
    stored_file(world, world.company_a, run, step=None, name="report.xls", data=b"X")
    world.storage.fail_with = StorageDenied("거절(시험)")
    assert error_of(client.get(f"/api/runs/{run}/files/report.xls")) == (503, "STORAGE_DENIED")
    world.storage.fail_with = None
    monkeypatch.setattr(documents_services, "default_storage", lambda: None)
    assert error_of(client.get(f"/api/runs/{run}/files/report.xls")) == (503, "STORAGE_UNCONFIGURED")
    assert AuditEventRow.unscoped.filter(action="download").count() == 0


# ── 문서 없는 흐름(ND1) ───────────────────────────────────────────────

BARE = _flow("probe", "probe.bare@1", ("first", "second"))  # 끼움은 문서 없는 갈래(register_documentless)
KIB = 1024


class BareBinding:
    """문서 없는 끼움(DocumentlessBinding 꼴). 받은 회사를 적는다."""

    def __init__(self) -> None:
        self.companies: list[int] = []

    def check_options(self, options: Mapping[str, object]) -> None:
        if options.get("rows") == "bad":
            raise RunOptionsRejected("행 목록을 읽을 수 없다")

    def inputs(self, options: Mapping[str, object], *, company_id: int) -> object:
        self.companies.append(company_id)
        return dict(options)

    def adapters(self, ctx: RunContext) -> object:
        return ProbeAdapters(ctx=ctx)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {"rules": "bare-rules@1"}


@pytest.fixture
def bare(world: World, monkeypatch: pytest.MonkeyPatch) -> BareBinding:
    """world 의 등록부에 문서 없는 흐름 probe.bare@1(상한 256KiB)을 더 단다. 문서 흐름 셋은 그대로."""
    flows = FlowRegistry()
    for flow in (PROBE, PROBE_TWO, UNBOUND, OTHER, BARE):
        flows.register(flow)
    flows.set_default("probe", PROBE.id)
    binding = BareBinding()
    bindings = BindingRegistry()
    bindings.register(PROBE.id, ProbeBinding())
    bindings.register(PROBE_TWO.id, ProbeBinding())
    bindings.register(OTHER.id, ProbeBinding())
    bindings.register_documentless(BARE.id, binding, max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS)
    monkeypatch.setattr(actions, "REGISTRY", flows)
    monkeypatch.setattr(actions, "BINDINGS", bindings)
    return binding


def bare_body(**extra: Any) -> dict[str, Any]:
    return {"module": "probe", "flowId": BARE.id, "options": {"rows": [1, 2]}, **extra}


def options_of_raw_octets(octets: int, *, quotes: bool = False) -> dict[str, object]:
    """raw JSON(앱 셈 — ensure_ascii=False, 기본 구분자)이 정확히 octets 바이트인 옵션. quotes 면 짧은 「"a"」 값을 많이
    실어 감싼 꼴(OrderedJSONField)이 이스케이프로 커지게 한다(critic B3)."""
    options: dict[str, object] = {}
    if quotes:
        while len(json.dumps(options, ensure_ascii=False).encode()) < octets - 64:
            options[f"k{len(options)}"] = '"a"'
    options["pad"] = ""
    short = octets - len(json.dumps(options, ensure_ascii=False).encode())
    options["pad"] = "x" * short
    assert len(json.dumps(options, ensure_ascii=False).encode()) == octets
    return options


@pytest.mark.parametrize("given", ["absent", "null"])
def test_a_documentless_flow_makes_a_run_without_a_document(
    client: Client, world: World, bare: BareBinding, django_capture_on_commit_callbacks: Any, given: str
) -> None:
    """문서 없는 흐름: documentId 없이(null 도 같음) 201 · 문서 칸 NULL · 단계 둘 pending · 판 묶음 · 쪽지 하나 · 감사
    줄 하나(target_label NULL — 「그때의 이름」이 없다)."""
    login(client)
    body = bare_body() if given == "absent" else bare_body(documentId=None)
    with django_capture_on_commit_callbacks(execute=True):
        response = create(client, body)
    assert response.status_code == 201, response.content.decode()
    run = RunRow.for_company(world.company_a).get(pk=response.json()["id"])
    assert (run.document_id, run.module, run.flow_id, run.status, run.options) == (
        None,
        "probe",
        BARE.id,
        "queued",
        {"rows": [1, 2]},
    )
    assert run.versions == {"rules": "bare-rules@1", "flow": BARE.id}
    steps = RunStepRow.for_company(world.company_a).filter(run_id=run.pk).order_by("position")
    assert [(s.name, s.status) for s in steps] == [("first", "pending"), ("second", "pending")]
    assert world.sent == [{"company_id": world.company_a, "run_id": run.pk}]
    lines = run_lines(world.company_a)
    assert [(r.event, r.target_kind, r.target_id, r.target_label) for r in lines] == [
        ("run_created", "run", run.pk, None)
    ]
    assert world.storage.get_calls == []  # 문서를 읽지 않는다


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("bare_with_my_document", (422, "DOCUMENT_NOT_ACCEPTED")),
        ("bare_with_their_document", (404, "NOT_FOUND")),
        ("bare_with_a_missing_document", (404, "NOT_FOUND")),
        ("document_flow_without_a_document", (422, "DOCUMENT_REQUIRED")),
        ("document_flow_with_null", (422, "DOCUMENT_REQUIRED")),
        ("default_flow_without_a_document", (422, "DOCUMENT_REQUIRED")),
        ("unbound_without_a_document", (422, "FLOW_NOT_RUNNABLE")),
        ("unknown_module_without_a_document", (422, "UNKNOWN_FLOW")),
        ("bare_options_rejected", (400, "INVALID_OPTIONS")),
    ],
)
def test_documentless_refusals_write_nothing(
    client: Client,
    world: World,
    bare: BareBinding,
    django_capture_on_commit_callbacks: Any,
    case: str,
    expected: tuple[int, str],
) -> None:
    login(client)
    mine = document(world.company_a)
    bodies: dict[str, dict[str, Any]] = {
        "bare_with_my_document": bare_body(documentId=mine),
        "bare_with_their_document": bare_body(documentId=document(world.company_b)),
        "bare_with_a_missing_document": bare_body(documentId=mine + 1000),
        "document_flow_without_a_document": {"module": "probe", "flowId": PROBE_TWO.id},
        "document_flow_with_null": {"module": "probe", "flowId": PROBE_TWO.id, "documentId": None},
        "default_flow_without_a_document": {"module": "probe"},
        "unbound_without_a_document": {"module": "probe", "flowId": UNBOUND.id},
        "unknown_module_without_a_document": {"module": "nothing"},
        "bare_options_rejected": bare_body(options={"rows": "bad"}),
    }
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = create(client, bodies[case])
    assert error_of(response) == expected
    assert (RunRow.unscoped.count(), RunStepRow.unscoped.count()) == (0, 0)
    assert (len(callbacks), world.sent) == (0, [])
    assert AuditEventRow.unscoped.filter(action="run").count() == 0
    if case == "document_flow_without_a_document":
        # 앞(ND1 전)은 꼴 오류 422 VALIDATION_ERROR·fields {documentId}·legacyCode invalid_input 였다
        assert response.json()["error"] == {
            "code": "DOCUMENT_REQUIRED",
            "message": "이 흐름은 문서가 있어야 한다(documentId)",
            "fields": None,
            "legacyCode": "document_required",
        }
    if case == "bare_with_my_document":
        assert response.json()["error"]["message"] == "이 흐름은 문서를 받지 않는다(입력은 options)"
    # 분모: 같은 세션으로 문서 없는 흐름은 문서 없이, 문서 흐름은 제 문서로 만들어진다
    assert create(client, bare_body()).status_code == 201
    assert create(client, {"module": "probe", "flowId": PROBE_TWO.id, "documentId": mine}).status_code == 201


def test_the_options_limit_is_per_flow_and_the_app_is_the_only_lock_under_the_db_ceiling(
    client: Client, world: World, bare: BareBinding
) -> None:
    """9f 조건 (다): DB CHECK 가 2 × 256KiB + 64 로 올라 문서 흐름의 16KiB 는 앱 층이 유일한 잠금이다. 문서 흐름에
    16KiB+1 → 400 INVALID_OPTIONS·행 0, 문서 없는 흐름에 그 상한(256KiB)+1 → 400·행 0(글에 그 흐름의 수).
    분모: 각 상한까지는 201, 문서 없는 흐름의 200KiB 도 201(문서 흐름 상한이면 걸렸을 크기)."""
    login(client)
    doc = document(world.company_a)
    document_flow = {"module": "probe", "flowId": PROBE_TWO.id, "documentId": doc}
    over_doc = create(client, {**document_flow, "options": options_of_raw_octets(16 * KIB + 1)})
    assert error_of(over_doc) == (400, "INVALID_OPTIONS")
    assert over_doc.json()["error"]["message"] == f"옵션이 너무 크다(JSON 으로 {16 * KIB}바이트까지)"
    over_bare = create(client, bare_body(options=options_of_raw_octets(256 * KIB + 1)))
    assert error_of(over_bare) == (400, "INVALID_OPTIONS")
    assert over_bare.json()["error"]["message"] == f"옵션이 너무 크다(JSON 으로 {256 * KIB}바이트까지)"
    assert RunRow.unscoped.count() == 0
    made = [
        create(client, {**document_flow, "options": options_of_raw_octets(16 * KIB)}),
        create(client, bare_body(options=options_of_raw_octets(256 * KIB))),
        create(client, bare_body(options=options_of_raw_octets(200 * KIB))),
    ]
    assert [m.status_code for m in made] == [201, 201, 201], [m.content.decode()[:200] for m in made]
    assert RunRow.for_company(world.company_a).count() == 3


def test_quote_heavy_options_under_the_app_limit_fit_the_wrapped_db_ceiling(
    client: Client, world: World, bare: BareBinding
) -> None:
    """critic B3: 감싼 꼴(OrderedJSONField)은 안쪽 따옴표마다 역빗금이 붙어 커진다. 앱 상한 안의 따옴표 많은 옵션은
    DB 상한(0002)에 막히지 않는다(500 이 아니라 201). 분모: 감싼 글자가 정말 앱 상한보다 크다."""
    login(client)
    doc = document(world.company_a)
    document_options = options_of_raw_octets(16 * KIB - 1, quotes=True)
    bare_options = options_of_raw_octets(256 * KIB - 1, quotes=True)
    made = [
        create(client, {"module": "probe", "flowId": PROBE_TWO.id, "documentId": doc, "options": document_options}),
        create(client, bare_body(options=bare_options)),
    ]
    assert [m.status_code for m in made] == [201, 201], [m.content.decode()[:200] for m in made]
    with connection.cursor() as cursor:
        cursor.execute("SELECT octet_length(options::text) FROM run_runs ORDER BY id")
        wrapped = [n for (n,) in cursor.fetchall()]
    assert wrapped[0] > 16 * KIB and wrapped[1] > 256 * KIB  # 분모
    rows = RunRow.for_company(world.company_a).order_by("id")
    assert [list(r.options) for r in rows] == [list(document_options), list(bare_options)]  # 쓴 차례 그대로


def test_a_documentless_run_resumes_from_its_failed_step(
    client: Client, world: World, bare: BareBinding, django_capture_on_commit_callbacks: Any
) -> None:
    """문서 없는 실행의 이어 돌기: 앞 실행(문서 NULL)과 문서가 같다(None == None) — 201, 끝난 첫 단계는 done 으로 옮김,
    판 묶음은 앞 것."""
    login(client)
    first = create(client, bare_body())
    assert first.status_code == 201
    previous = first.json()["id"]
    RunRow.for_company(world.company_a).filter(pk=previous).update(
        status="failed", failed_step="second", error_code="step_error", versions={"rules": "old", "flow": BARE.id}
    )
    RunStepRow.for_company(world.company_a).filter(run_id=previous, name="first").update(
        status="done", data={"rows": 2}, done=1, total=1
    )
    RunStepRow.for_company(world.company_a).filter(run_id=previous, name="second").update(status="failed")
    with django_capture_on_commit_callbacks(execute=True):
        resumed = create(client, bare_body(resumeFromRunId=previous))
    assert resumed.status_code == 201, resumed.content.decode()
    run = RunRow.for_company(world.company_a).get(pk=resumed.json()["id"])
    assert (run.document_id, run.resumed_from_run_id, run.versions) == (
        None,
        previous,
        {"rules": "old", "flow": BARE.id},
    )
    steps = RunStepRow.for_company(world.company_a).filter(run_id=run.pk).order_by("position")
    assert [(s.name, s.status, s.data) for s in steps] == [("first", "done", {"rows": 2}), ("second", "pending", None)]
    # 분모: 문서를 주면 이어 돌기 앞에서 422(문서 없는 흐름)
    doc = document(world.company_a)
    assert error_of(create(client, bare_body(documentId=doc, resumeFromRunId=previous))) == (
        422,
        "DOCUMENT_NOT_ACCEPTED",
    )


def test_a_documentless_run_lists_and_reads_with_null_document_fields(
    client: Client, world: World, bare: BareBinding
) -> None:
    """목록에 한 줄(두 칸 null — 글자 「None」이 아니다), ?documentId= 로 거르면 빠짐, 단건 documentId null.
    분모: 문서 실행은 두 칸이 차 있다."""
    login(client)
    doc = document(world.company_a)
    with_document = create(client, {"module": "probe", "documentId": doc}).json()["id"]
    without = create(client, bare_body()).json()["id"]
    page = client.get("/api/runs").json()
    assert [(r["id"], r["documentId"], r["documentName"]) for r in page["results"]] == [
        (without, None, None),
        (with_document, doc, "지은 보고서.pdf"),
    ]
    assert [r["id"] for r in client.get(f"/api/runs?documentId={doc}").json()["results"]] == [with_document]
    one = client.get(f"/api/runs/{without}")
    assert (one.status_code, one.json()["documentId"], one.json()["options"]) == (200, None, {"rows": [1, 2]})
