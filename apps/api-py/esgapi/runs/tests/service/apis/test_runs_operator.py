# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""운영 관리자(kind admin, 회사 없음)의 실행 경로 넷을 진짜 DB 로 잰다(결정 MARC-ENT-374·380, 밴드 OP1 Q3·OP2). 업무 층.

운영 관리자는 작업 회사에서 core/permissions.py 의 OPERATOR_RUN_MODULES 넷(그린워싱·영문번역·데이터 검증·중대성평가)의
실행만 다룬다:
    만들기      그 넷이 아니면 403 forbidden — 회사를 고르기 전(행 0·감사 0)
    목록        질의 module 이 없으면 그 넷 전부, 그 밖의 모듈을 고르면 빈 쪽
    하나·파일   그 넷이 아닌 실행이면 404(남의 것과 같다)
여기서 잰 것은 넷 가운데 둘(그린워싱·영문번역 — 가짜 흐름이 그 둘뿐)과 그 밖(inventory)이다. 데이터 검증·중대성평가는
각 모듈의 tests 가 잰다. 그리고 운영 관리자가 만든 그린워싱·영문번역 실행이 실행기로 끝까지 돈다(발주서 OP1 ★E·OP2 ★E′).
분모: 고객사 사용자(쿠키 세션)는 세 모듈을 다 본다.

★ 작업 회사는 core/auth/bearer.py 의 포트를 회사 A 로 바꿔 끼운다(runs 는 user·organization 을 import 하지 못한다 —
  계약 차. 진짜 고르기 operator_work_company 는 user/tests 와 보안 층이 잰다). 운영 관리자의 access 는 core 의 토큰
  함수로 낸다(인증은 DB 를 읽지 않는다 — 사용자 행이 없어도 된다).
★ 흐름·끼움은 시험 안의 가짜를 시험의 레지스트리에 단다(actions·tasks 의 REGISTRY·BINDINGS 를 바꿔 끼움). 그린워싱
  몫은 module "greenwash" 의, 영문번역 몫은 module "translation" 의 가짜 흐름이다 — 진짜 흐름은 각 모듈의
  tests/flows 가 잰다.
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import contextlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import get_resolver

from esgapi.config.env import JobSettings
from esgapi.core.auth import bearer as bearer_module
from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.conf import app_config, now
from esgapi.core.flows.binding import BindingRegistry, DocumentInput, RunContext
from esgapi.core.flows.registry import FlowRegistry, make_flow
from esgapi.core.flows.types import Carried, FlowStep, OutputFile, StepContext, StepOutput
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.models import AuditEventRow, DocumentRow
from esgapi.core.resources import queue as hooks
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs import context, tasks
from esgapi.runs.models import RunRow
from esgapi.runs.service.actions import runs as actions
from tests.support.http import bearer, login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

OPERATOR_ID = 9001  # 운영 관리자의 사용자 id(토큰의 sub — 인증은 사용자 행을 읽지 않는다)
NOW = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)


@dataclass(frozen=True)
class ProbeInputs:
    document: DocumentInput


@dataclass(frozen=True)
class ProbeAdapters:
    ctx: RunContext


def _only(inputs: ProbeInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(
        data={"results": [{"schemaVersion": "probe.result@1", "size": len(inputs.document.content)}]},
        files=(OutputFile(name="out.bin", media_type="application/octet-stream", content=b"OUT-BYTES"),),
    )


def _flow(module: str, flow_id: str) -> Any:
    return make_flow(
        module=module,
        id=flow_id,
        input_shape="probe.document@1",
        inputs=ProbeInputs,
        adapters=ProbeAdapters,
        result_shapes=("probe.result@1",),
        output_files=("out.bin",),
        steps=(FlowStep(name="only", run=_only),),
    )


GREENWASH = _flow("greenwash", "greenwash.probe@1")
TRANSLATION = _flow("translation", "translation.probe@1")
INVENTORY = _flow("inventory", "inventory.probe@1")


@dataclass
class ProbeBinding:
    contexts: list[RunContext] = field(default_factory=list[RunContext])

    def check_options(self, options: Mapping[str, object]) -> None:
        return None

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> object:
        return ProbeInputs(document=document)

    def adapters(self, ctx: RunContext) -> object:
        self.contexts.append(ctx)
        return ProbeAdapters(ctx=ctx)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {}


class RetryAsked(Exception):
    """가짜 retry 가 돌려주는 것."""


@dataclass
class World:
    company_a: int
    company_b: int
    storage: FakeStorage
    binding: ProbeBinding
    ports: list[int] = field(default_factory=list[int])
    retries: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])

    def retry(self, **kwargs: Any) -> RetryAsked:
        self.retries.append(kwargs)
        return RetryAsked()


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    flows = FlowRegistry()
    bindings = BindingRegistry()
    made = World(*companies, storage=FakeStorage(), binding=ProbeBinding())
    for flow in (GREENWASH, TRANSLATION, INVENTORY):
        flows.register(flow)
        flows.set_default(flow.module, flow.id)
        bindings.register(flow.id, made.binding)
    for where in (actions, tasks):
        monkeypatch.setattr(where, "REGISTRY", flows)
        monkeypatch.setattr(where, "BINDINGS", bindings)

    def no_message(**_: object) -> None:
        return None

    monkeypatch.setattr(hooks, "enqueue_run", no_message)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "clock", lambda: NOW)
    monkeypatch.setattr(tasks, "monotonic", lambda: 0.0)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: 240)
    monkeypatch.setattr(context, "call_sink", MemorySink)
    plug_storage(monkeypatch, made.storage, max_upload_bytes=1000)

    def work_company() -> int:  # 작업 회사 = A(진짜 고르기는 user 의 operator_work_company)
        made.ports.append(made.company_a)
        return made.company_a

    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", work_company)
    return made


def operator() -> dict[str, Any]:
    claims = new_access_claims(
        user_id=str(OPERATOR_ID),
        kind="admin",
        level=99,
        company_id=None,
        company_is_active=None,
        is_initial=False,
        jti=uuid4(),
        now=now(),
    )
    return bearer(sign_access(claims, secret=app_config().session_secret))


def document(world: World, company_id: int) -> int:
    content = b"%PDF-1.7 (synthetic bytes for the operator)"
    key = f"companies/{company_id}/documents/op1-{len(world.storage.objects)}/original"
    etag = world.storage.put(key, content)
    row = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="1",
        file_name="지은 보고서.pdf",
        storage_key=key,
        size_bytes=len(content),
        etag=etag,
        status="uploaded",
    )
    return row.pk


def create(client: Client, module: str, document_id: int, **headers: Any) -> Any:
    body = {"module": module, "documentId": document_id}
    return client.post("/api/runs", data=body, content_type="application/json", **headers)


def execute(world: World, run_id: int) -> None:
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(world, company_id=str(world.company_a), run_id=str(run_id))


def customer_run(client: Client, world: World, module: str) -> int:
    """고객사 사용자(쿠키 세션, 회사 A)가 만들고 끝까지 돌린 실행."""
    login(client)
    response = create(client, module, document(world, world.company_a))
    assert response.status_code == 201, response.content.decode()
    run_id: int = response.json()["id"]
    execute(world, run_id)
    return run_id


def run_lines(company_id: int) -> list[tuple[str, int | None, str]]:
    rows = AuditEventRow.for_company(company_id).filter(action="run").order_by("id")
    return [(r.actor_kind, r.actor_user_id, r.event) for r in rows]


# ── 만들기 ────────────────────────────────────────────────────────────


def test_an_operator_may_create_greenwash_and_translation_runs_and_is_refused_before_choosing_a_company(
    client: Client, world: World
) -> None:
    doc = document(world, world.company_a)
    refused = create(client, "inventory", doc, **operator())
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "FORBIDDEN")
    assert world.ports == []  # 회사를 고르기 전에 막았다
    assert RunRow.for_company(world.company_a).count() == 0
    assert run_lines(world.company_a) == []

    made = create(client, "greenwash", doc, **operator())  # 분모: 그린워싱은 만든다
    assert made.status_code == 201, made.content.decode()
    run = RunRow.for_company(world.company_a).get(pk=made.json()["id"])
    assert (run.module, run.flow_id, run.created_by_user_id) == ("greenwash", GREENWASH.id, OPERATOR_ID)
    assert world.ports == [world.company_a]
    assert run_lines(world.company_a) == [("admin", OPERATOR_ID, "run_created")]

    made = create(client, "translation", doc, **operator())  # 영문번역도 만든다(MARC-ENT-380)
    assert made.status_code == 201, made.content.decode()
    run = RunRow.for_company(world.company_a).get(pk=made.json()["id"])
    assert (run.module, run.flow_id, run.created_by_user_id) == ("translation", TRANSLATION.id, OPERATOR_ID)
    assert world.ports == [world.company_a, world.company_a]
    assert run_lines(world.company_a) == [("admin", OPERATOR_ID, "run_created")] * 2
    assert RunRow.for_company(world.company_b).count() == 0


@pytest.mark.parametrize("module", ["greenwash", "translation"])
def test_a_run_created_by_the_operator_runs_to_done(client: Client, world: World, module: str) -> None:
    """발주서 OP1 ★E·OP2 ★E′: 실행기는 주체를 모른다 — 운영 관리자가 만든 실행도 작업 회사의 실행으로 끝까지 돈다."""
    made = create(client, module, document(world, world.company_a), **operator())
    run_id: int = made.json()["id"]
    execute(world, run_id)
    run = RunRow.for_company(world.company_a).get(pk=run_id)
    assert (run.status, run.error_code, run.attempts) == ("done", None, 1)
    (ctx,) = world.binding.contexts
    assert (ctx.company_id, ctx.run_id, ctx.module) == (world.company_a, run_id, module)
    got = client.get(f"/api/runs/{run_id}", **operator()).json()
    assert (got["status"], got["files"], got["resultShapes"]) == ("done", ["out.bin"], ["probe.result@1"])
    file = client.get(f"/api/runs/{run_id}/files/out.bin", **operator())
    assert (file.status_code, file.content) == (200, b"OUT-BYTES")


# ── 목록 ─────────────────────────────────────────────────────────────


def test_the_operator_list_shows_greenwash_and_translation_runs(client: Client, world: World) -> None:
    greenwash = customer_run(client, world, "greenwash")
    inventory = customer_run(client, world, "inventory")
    translation = customer_run(client, world, "translation")
    mine = Client()

    def ids(query: str, **headers: Any) -> tuple[int, list[int]]:
        body = mine.get(f"/api/runs{query}", **headers).json()
        return body["count"], [line["id"] for line in body["results"]]

    assert ids("", **operator()) == (2, [translation, greenwash])  # 질의가 없으면 두 모듈 전부(inventory 빠짐)
    assert ids("?module=greenwash", **operator()) == (1, [greenwash])
    assert ids("?module=translation", **operator()) == (1, [translation])
    assert ids("?module=inventory", **operator()) == (0, [])
    login(mine)  # 분모: 고객사 사용자는 셋 다 본다
    assert ids("") == (3, [translation, inventory, greenwash])
    assert ids("?module=inventory") == (1, [inventory])


# ── 하나·내려받기 ──────────────────────────────────────────────────────


def test_the_operator_gets_404_on_a_run_of_another_module(client: Client, world: World) -> None:
    greenwash = customer_run(client, world, "greenwash")
    inventory = customer_run(client, world, "inventory")
    translation = customer_run(client, world, "translation")
    admin = Client()
    for run_id, expected in ((inventory, 404), (greenwash, 200), (translation, 200)):
        assert admin.get(f"/api/runs/{run_id}", **operator()).status_code == expected, run_id
    refused = admin.get(f"/api/runs/{inventory}", **operator())
    assert refused.json()["error"]["code"] == "NOT_FOUND"
    assert client.get(f"/api/runs/{inventory}").status_code == 200  # 분모: 고객사 사용자는 본다


def test_the_operator_gets_404_on_a_file_of_another_modules_run(client: Client, world: World) -> None:
    greenwash = customer_run(client, world, "greenwash")
    inventory = customer_run(client, world, "inventory")
    translation = customer_run(client, world, "translation")
    admin = Client()
    refused = admin.get(f"/api/runs/{inventory}/files/out.bin", **operator())
    assert (refused.status_code, refused.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert admin.get(f"/api/runs/{greenwash}/files/out.bin", **operator()).content == b"OUT-BYTES"
    assert admin.get(f"/api/runs/{translation}/files/out.bin", **operator()).content == b"OUT-BYTES"
    assert client.get(f"/api/runs/{inventory}/files/out.bin").content == b"OUT-BYTES"  # 분모: 고객사 사용자
    downloads = AuditEventRow.for_company(world.company_a).filter(action="download").order_by("id")
    assert [(r.actor_kind, r.target_id) for r in downloads] == [
        ("admin", greenwash),
        ("admin", translation),
        ("service", inventory),
    ]


# ── Idempotency-Key(IK1 — 발주서 §2-7 업무 8: 범위 = (작업 회사, 운영 관리자)) ─────────────────

KEY = "0b0e6c1e-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID


def test_an_operator_key_is_scoped_to_the_work_company(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """같은 운영 관리자가 같은 열쇠·같은 꼴 본문을 작업 회사 A·B 에서 보내면 회사마다 따로 실행이다. 같은 회사에서
    다시 보내면 그 회사의 실행 그대로."""
    doc_a, doc_b = document(world, world.company_a), document(world, world.company_b)
    made_a = create(client, "greenwash", doc_a, **operator(), HTTP_IDEMPOTENCY_KEY=KEY)
    assert made_a.status_code == 201, made_a.content.decode()
    again_a = create(client, "greenwash", doc_a, **operator(), HTTP_IDEMPOTENCY_KEY=KEY)
    assert (again_a.status_code, again_a.json()["id"]) == (201, made_a.json()["id"])

    def company_b() -> int:
        return world.company_b

    monkeypatch.setattr(bearer_module, "_operator_company", company_b)
    made_b = create(client, "greenwash", doc_b, **operator(), HTTP_IDEMPOTENCY_KEY=KEY)
    assert made_b.status_code == 201, made_b.content.decode()
    assert made_b.json()["id"] != made_a.json()["id"]
    assert (RunRow.for_company(world.company_a).count(), RunRow.for_company(world.company_b).count()) == (1, 1)
    assert RunRow.for_company(world.company_b).get(pk=made_b.json()["id"]).created_by_user_id == OPERATOR_ID


def test_an_operator_other_module_is_403_before_the_key_lookup(
    client: Client, world: World, django_assert_num_queries: Any
) -> None:
    """운영 관리자의 다른 모듈 403 은 열쇠(맞는 꼴)가 있어도 열쇠 찾기·회사 고르기 앞이다 — 쿼리 0."""
    doc = document(world, world.company_a)
    with django_assert_num_queries(0):
        refused = create(client, "inventory", doc, **operator(), HTTP_IDEMPOTENCY_KEY=KEY)
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "FORBIDDEN")
    assert world.ports == []
    assert RunRow.unscoped.count() == 0
    # 분모: 그 모듈 몫(그린워싱)은 같은 열쇠로 만들어진다(쿼리가 생긴다)
    assert create(client, "greenwash", doc, **operator(), HTTP_IDEMPOTENCY_KEY=KEY).status_code == 201


# ── launchKey(LK1 — 발주서 §2-9 업무 6: 묶음 범위는 작업 회사마다) ──────────────────────

LAUNCH = "1a2b3c4d-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID


def test_an_operator_launch_key_lands_in_each_work_company(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """같은 운영 관리자가 같은 launchKey 로 작업 회사 A·B 에서 만들면 각 회사에 행 하나씩(같은 값). 묶음 셈이 고른 회사
    안인지는 user 의 test_run_logs_launch.py."""
    doc_a, doc_b = document(world, world.company_a), document(world, world.company_b)
    body = {"module": "greenwash", "documentId": doc_a, "launchKey": LAUNCH}
    made_a = client.post("/api/runs", data=body, content_type="application/json", **operator())
    assert made_a.status_code == 201, made_a.content.decode()

    def company_b() -> int:
        return world.company_b

    monkeypatch.setattr(bearer_module, "_operator_company", company_b)
    body_b = {**body, "documentId": doc_b}
    made_b = client.post("/api/runs", data=body_b, content_type="application/json", **operator())
    assert made_b.status_code == 201, made_b.content.decode()
    a_keys = list(RunRow.for_company(world.company_a).values_list("launch_key", "created_by_user_id"))
    b_keys = list(RunRow.for_company(world.company_b).values_list("launch_key", "created_by_user_id"))
    assert (a_keys, b_keys) == ([(LAUNCH, OPERATOR_ID)], [(LAUNCH, OPERATOR_ID)])
