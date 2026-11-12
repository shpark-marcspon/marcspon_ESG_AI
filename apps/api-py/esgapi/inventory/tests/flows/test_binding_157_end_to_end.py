# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 코랩 흐름(scope3.colab@157)을 진짜 DB 의 문서 길·실행 만들기·실행기로 한 바퀴 잰다(밴드 S3K1 §2-2, 업무 층).

    올림      POST /documents → 저장소 → confirm(xlsx 도 PDF 문서 길을 지난다 — C0 ★I) → POST /runs 201
    끝까지    실행기 한 번(모의 공급사) → done · 결과 한 행 scope3.colab.result@1 · 같은 입력을 run_flow 에 바로
              넣은 StepOutput.data 와 JSON sha 같음 · 거리 시트는 NoGeocoder 라 AI 직선거리 갈래
    운영 관리자  OPERATOR_RUN_MODULES 의 inventory.scope3 — 작업 회사에 만들고 끝까지(469-4 「대신하기」 꼴)
    거절      reportYear 빠짐·1989·올해+1·true → 400 invalid_options · 계수 책 없음(포트)·스위치 꺼짐 → 400 · 모두 행 0
    실패      계수 책이 ReaderProblem → failed · error_code internal(★J)
    멈춤(S3K3) 키 없음(openai 를 모의로 바꾸지 않음) → failed·setup_error · live 의 작은 실행 상한 → failed·step_error ·
              공급사 401 → failed·step_error 뒤 고쳐 resumeFromRunId → 실패 단계부터 done · 데이터 탓 시트 예외는 done
    기본      flowId 없이 → scope3.colab@157
★ 공급사: context.build_client 의 make 를 갈아 openai 에 대본 심은 모의 공급사(dataverify test_runs_dataverify 꼴 —
  실제 공급사·키·네트워크 0). ★ 계수 책: apps.py 가 꽂은 포트(scope3_files.PackagedXlsx.read)를 지어낸 책 바이트로 갈아
  끼운다 — 저장소의 받은 책은 읽지 않는다. 템플릿·책·답은 전부 지어낸 것이다(colab_157 support·test_purchase 의 것).
★ 스위치: Config.inventory_scope3_runs_enabled 의 기본은 끔이라(MARC-ISSUE-499) world 가 켠다. 끔은 거절 시험이 잰다.
"""

import contextlib
import dataclasses
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import partial
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import get_resolver

from esgapi.config.env import JobSettings, LlmSettings
from esgapi.core.auth import bearer as bearer_module
from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.conf import app_config, now
from esgapi.core.flows.run import run_flow
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, InvokeOptions, ProviderError, ProviderRequest, ProviderResponse, Tags
from esgapi.core.models import DocumentRow
from esgapi.core.resources import llm as llm_adapters
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.inventory.engines.scope3.colab_157 import pipeline
from esgapi.inventory.engines.scope3.colab_157.ports import NoGeocoder
from esgapi.inventory.flows import binding_157
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.flows.binding_157 import FileMissing
from esgapi.inventory.service.utils import scope3_files
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    sheet,
    transport_distance_sheet,
    transport_ef_sheet,
    workbook,
    xlsx_bytes,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, C1_ROWS, C2_ROWS, replies
from esgapi.inventory.tests.engines.scope3.colab_157.test_transport_sheet import MAIN_LOOP_ROW
from esgapi.inventory.tests.scope3_llm_support import user_text
from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook
from esgapi.runs import context, tasks
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import bearer, login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
OPERATOR_ID = 9157  # 운영 관리자의 사용자 id(토큰의 sub — 인증은 사용자 행을 읽지 않는다)
TEMPLATE = xlsx_bytes(
    workbook(
        sheet("C1_구매품서비스", C1_ROWS),
        sheet("C2_자본재", C2_ROWS),
        transport_distance_sheet("c4-1_운송거리", MAIN_LOOP_ROW),
        sheet("표지", {1: ["가상"]}),
    )
)
BOOK = xlsx_bytes(workbook(sheet("구매_USEPA", BOOK_ROWS), transport_ef_sheet()))
DISTANCE = {  # 차례대로 본다 — 직선거리 물음이 도시 이름을 품으니 먼저
    "출발지: 가상시가\n도착지: 가상시다\n국가 힌트: KR": '{"distance_km": 92}',
    "가상시가": "Synthetic Ga",
    "가상시다": "Synthetic Da",
}


REAL_BUILD_CLIENT = context.build_client  # world 가 갈기 전(모듈을 읽을 때)의 것
TINY_USD = 0.000001
"""실행 상한(S3K3 — 지어낸 SYNTHETIC_USAGE 한 부름의 비용보다 작다: 첫 부름 뒤 누적이 넘는다)."""


class Script(MockProvider):
    """openai 자리의 모의 공급사. 거리 물음은 DISTANCE, 나머지는 구매 시트의 답(test_purchase.replies)."""

    def __init__(self) -> None:
        super().__init__("openai")
        self.purchase = replies()
        self.texts: list[str] = []

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        self.enqueue(self.reply)
        return super().invoke(request, options)

    def reply(self, request: ProviderRequest) -> ProviderResponse:
        text = user_text(request)
        self.texts.append(text)
        answer = next((a for key, a in DISTANCE.items() if key in text), None)
        if answer is not None:
            return Completed(text=answer, usage=SYNTHETIC_USAGE)
        return self.purchase.reply(request)


class RetryAsked(Exception):
    """가짜 retry 가 돌려주는 것."""


@dataclass
class World:
    storage: FakeStorage
    company_a: int
    company_b: int
    book: bytes | FileMissing = BOOK
    mock: Script = field(default_factory=Script)
    sink: MemorySink = field(default_factory=MemorySink)

    def retry(self, **kwargs: Any) -> RetryAsked:
        return RetryAsked()


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int], settings: Any) -> World:
    settings.ESG_CONFIG = dataclasses.replace(settings.ESG_CONFIG, inventory_scope3_runs_enabled=True)
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)
    made = World(storage, *companies)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "monotonic", lambda: 0.0)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: 240)
    monkeypatch.setattr(context, "call_sink", lambda: made.sink)

    def make(name: str, **kwargs: Any) -> Any:
        return made.mock if name == "openai" else llm_adapters.make(name, **kwargs)

    monkeypatch.setattr(context, "build_client", partial(context.build_client, make=make))
    real_read = scope3_files.PackagedXlsx.read

    def read(self: scope3_files.PackagedXlsx) -> bytes | FileMissing:
        return made.book if self.name == scope3_files.FACTOR_BOOK.name else real_read(self)

    monkeypatch.setattr(scope3_files.PackagedXlsx, "read", read)
    return made


@pytest.fixture
def work_company(monkeypatch: pytest.MonkeyPatch, world: World) -> None:
    """운영 관리자의 작업 회사 = A(진짜 고르기는 user 의 operator_work_company — 보안 층이 잰다)."""
    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: world.company_a)


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


def upload(client: Client, world: World, content: bytes = TEMPLATE) -> int:
    """웹의 uploadDocument: POST /documents → (PUT 은 저장소에 바로) → confirm. 문서 id."""
    made = client.post(
        "/api/documents",
        data={"fileName": "가상-scope3.xlsx", "sizeBytes": len(content)},
        content_type="application/json",
    )
    assert made.status_code == 201, made.content.decode()
    document_id: int = made.json()["document"]["id"]
    world.storage.put(DocumentRow.unscoped.get(pk=document_id).storage_key, content)
    confirmed = client.post(f"/api/documents/{document_id}/confirm")
    assert confirmed.status_code == 200, confirmed.content.decode()
    return document_id


def post_run(client: Client, body: Mapping[str, object], **extra: Any) -> Any:
    return client.post("/api/runs", data=dict(body), content_type="application/json", **extra)


def body_of(document_id: int, options: Mapping[str, object], **more: object) -> dict[str, object]:
    return {"module": "inventory.scope3", "documentId": document_id, "options": dict(options), **more}


def execute(world: World, run_id: int) -> None:
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(world, company_id=str(world.company_a), run_id=str(run_id))


def run_of(world: World, run_id: int) -> run_selectors.Run:
    found = run_selectors.find_run(company_id=world.company_a, run_id=run_id)
    assert found is not None
    return found


def run_count(world: World) -> int:
    return run_selectors.run_page(
        company_id=world.company_a, module=None, status=None, document_id=None, limit=100, offset=0
    ).count


def sha(body: object) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def direct(year: int, company_id: int) -> dict[str, Any]:
    """같은 템플릿·책·답을 run_flow 에 바로 — 실행기와 같은 경로(standard-openai-41)·꼬리표(회사 id 글자)."""
    book = read_workbook(BOOK)
    assert not isinstance(book, ReaderProblem)
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": Script()},
        prompts=PackagePromptStore(),
        log=MemorySink(),
    )
    inputs = colab.ColabInputs(
        template=TEMPLATE,
        report_year=year,
        route=binding_157.ROUTE,
        tags=Tags(tenant=str(company_id), module="inventory.scope3"),
    )
    result = run_flow(colab.FLOW, inputs, colab.ColabAdapters(llm=client, factor_book=book, geocoder=NoGeocoder()))
    (only,) = result.output.results
    return only


def done_body(world: World, run_id: int) -> dict[str, Any]:
    run = run_of(world, run_id)
    assert (run.status, run.error_code) == ("done", None), run.error_message
    (only,) = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    assert only.schema_version == "scope3.colab.result@1"
    assert isinstance(only.body, dict)
    return only.body  # pyright: ignore[reportReturnType]


# ── 끝까지 ──


@pytest.mark.parametrize("year", [2025, 2019])
def test_an_uploaded_template_runs_to_done_like_the_flow_run_directly(client: Client, world: World, year: int) -> None:
    login(client)
    document_id = upload(client, world)
    made = post_run(client, body_of(document_id, {"reportYear": year}))
    assert (made.status_code, made.json()["status"]) == (201, "queued"), made.content.decode()
    run_id: int = made.json()["id"]
    run = run_of(world, run_id)
    assert (run.module, run.flow_id, run.document_id, run.options) == (
        "inventory.scope3",
        "scope3.colab@157",
        document_id,
        {"reportYear": year},
    )
    assert run.versions == {"engine": "colab_157", "flow": "scope3.colab@157", "route": "standard-openai-41"}

    execute(world, run_id)
    body = done_body(world, run_id)
    assert (body["schemaVersion"], body["status"]) == ("scope3.colab.result@1", "done")
    assert sha(body) == sha(direct(year, world.company_a))
    assert any("가상시가" in text for text in world.mock.texts)  # 거리 시트가 공급사에 닿았다
    calls = world.sink.records
    assert calls and {c.tenant for c in calls} == {str(world.company_a)}


def test_the_distance_sheet_takes_the_ai_straight_branch_with_no_geocoder(client: Client, world: World) -> None:
    """NoGeocoder 는 늘 못 찾음 — 본 고리는 AI 직선거리(92 km × road 1.3)로 간다(MARC-ENT-167 held)."""
    login(client)
    run_id = post_run(client, body_of(upload(client, world), {"reportYear": 2025})).json()["id"]
    execute(world, run_id)
    rows = [row for s in done_body(world, run_id)["sheets"] for row in s.get("rows") or ()]
    (moved,) = [row["distance"] for row in rows if row.get("distance")]
    assert (moved["via"], moved["km"], moved["departure"], moved["arrival"]) == (
        "ai_straight",
        repr(92 * 1.3),
        "가상시가",
        "가상시다",
    )


def test_without_a_flow_id_the_run_takes_the_colab_flow(client: Client, world: World) -> None:
    login(client)
    made = post_run(client, body_of(upload(client, world), {"reportYear": 2025}))
    assert made.status_code == 201, made.content.decode()
    assert run_of(world, made.json()["id"]).flow_id == "scope3.colab@157"


def test_the_operator_runs_scope3_in_the_work_company(client: Client, world: World, work_company: None) -> None:
    login(client)
    document_id = upload(client, world)  # 고객사 사용자가 올린 문서
    client = Client()  # 쿠키 없는 새 손님 — 운영 관리자는 bearer 만
    made = post_run(client, body_of(document_id, {"reportYear": 2025}), **operator())
    assert made.status_code == 201, made.content.decode()
    run_id: int = made.json()["id"]
    run = run_of(world, run_id)
    assert (run.company_id, run.created_by_user_id, run.module) == (world.company_a, OPERATOR_ID, "inventory.scope3")
    execute(world, run_id)
    assert done_body(world, run_id)["status"] == "done"
    read = client.get(f"/api/runs/{run_id}", **operator())
    assert (read.status_code, read.json()["status"]) == (200, "done")


# ── 거절·실패 ──


@pytest.mark.parametrize(
    "options",
    [{}, {"reportYear": 1989}, {"reportYear": binding_157.today().year + 1}, {"reportYear": True}],
    ids=["missing", "before-1990", "next-year", "true"],
)
def test_a_bad_year_is_400_with_no_row(client: Client, world: World, options: dict[str, object]) -> None:
    login(client)
    document_id = upload(client, world)
    refused = post_run(client, body_of(document_id, options))
    assert refused.status_code == 400, refused.content.decode()
    assert refused.json()["error"]["code"] == "INVALID_OPTIONS"
    assert "reportYear" in refused.json()["error"]["message"]
    assert run_count(world) == 0


def test_a_missing_factor_book_is_400_with_no_row(client: Client, world: World) -> None:
    world.book = FileMissing(scope3_files.FACTOR_BOOK.name)
    login(client)
    refused = post_run(client, body_of(upload(client, world), {"reportYear": 2025}))
    assert (refused.status_code, refused.json()["error"]["code"]) == (400, "INVALID_OPTIONS"), refused.content.decode()
    assert "배출계수 책" in refused.json()["error"]["message"]
    assert run_count(world) == 0


def test_a_switched_off_deployment_refuses_the_run_with_no_row(client: Client, world: World, settings: Any) -> None:
    settings.ESG_CONFIG = dataclasses.replace(settings.ESG_CONFIG, inventory_scope3_runs_enabled=False)
    login(client)
    refused = post_run(client, body_of(upload(client, world), {"reportYear": 2025}))
    assert (refused.status_code, refused.json()["error"]["code"]) == (400, "INVALID_OPTIONS"), refused.content.decode()
    assert "열려 있지 않아요" in refused.json()["error"]["message"]
    assert run_count(world) == 0


def test_an_unreadable_factor_book_fails_the_run_as_internal(client: Client, world: World) -> None:
    """★J: 끼움의 FactorBookUnreadable 은 runs/calc/errors.py 표 밖 — error_code internal, 공급사 호출 0."""
    world.book = b"PK\x03\x04 not a zip"
    login(client)
    run_id = post_run(client, body_of(upload(client, world), {"reportYear": 2025})).json()["id"]
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.error_code) == ("failed", "internal")
    assert run_selectors.run_results(company_id=world.company_a, run_id=run_id) == ()
    assert world.mock.texts == []


# ── 실행을 멈추는 자리(밴드 S3K3 — MARC-ISSUE-521) ──


class Rejecting(Script):
    """거리 물음(c4 단계)에 공급사 거절 401 을 돌려주는 모의(reject 가 참인 동안). 나머지는 Script 그대로."""

    def __init__(self) -> None:
        super().__init__()
        self.reject = True

    def reply(self, request: ProviderRequest) -> ProviderResponse:
        if self.reject and any(key in user_text(request) for key in DISTANCE):
            self.texts.append(user_text(request))
            return ProviderError(status=401, retryable=False, message="가상 거절")
        return super().reply(request)


def failed_run(world: World, run_id: int) -> run_selectors.Run:
    run = run_of(world, run_id)
    assert run.status == "failed", (run.status, run.error_code)
    assert run_selectors.run_results(company_id=world.company_a, run_id=run_id) == ()
    return run


def test_a_deployment_without_the_provider_key_fails_the_run_as_setup_error(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mock 배포본(키 빈 값): openai 를 모의로 바꾸지 않으면 첫 부름에서 LiveSetupError → failed·setup_error
    (BASE: done · LLM 시트 failed). LLM 이 필요 없는 시트의 결과도 함께 없다(결과 0 행)."""
    monkeypatch.setattr(context, "build_client", partial(REAL_BUILD_CLIENT, make=llm_adapters.make))
    login(client)
    run_id = post_run(client, body_of(upload(client, world), {"reportYear": 2025})).json()["id"]
    execute(world, run_id)
    run = failed_run(world, run_id)
    assert (run.error_code, run.failed_step) == ("setup_error", "c1")
    assert run.error_message == "AI 호출 설정이 없어 실행하지 못했다(운영 관리자 확인)"
    read = client.get(f"/api/runs/{run_id}").json()
    assert (read["status"], read["errorCode"]) == ("failed", "setup_error")
    assert client.get(f"/api/inventory/scope3/runs/{run_id}/result").status_code == 409
    assert world.mock.texts == [] and world.sink.records == []


def test_a_data_error_in_one_sheet_still_finishes_done_with_that_sheet_failed(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = pipeline.process_activity_sheet

    def broken(*args: Any, **kwargs: Any) -> Any:
        if args[3] == "c4_dist":  # (activity, template, sheet, processor.key, category)
            raise ValueError("가상 값 오류")
        return real(*args, **kwargs)

    monkeypatch.setattr(pipeline, "process_activity_sheet", broken)
    login(client)
    run_id = post_run(client, body_of(upload(client, world), {"reportYear": 2025})).json()["id"]
    execute(world, run_id)
    body = done_body(world, run_id)
    statuses = {s["sheet"]: s["status"] for s in body["sheets"]}
    assert statuses["c4-1_운송거리"] == "failed"
    assert statuses["C1_구매품서비스"] == statuses["C2_자본재"] == "processed"
    read = client.get(f"/api/inventory/scope3/runs/{run_id}/result")
    assert read.status_code == 200, read.content.decode()


def test_the_run_budget_stops_the_run_at_the_first_call_over(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """live 의 실행 하나 상한(runs/context.py): 첫 부름의 지어낸 비용이 작은 상한을 넘겨 둘째 부름에서 멈춤 →
    failed·step_error(BASE: done · 남은 줄 빈 값). 공급사 부름 1 번."""
    settings = LlmSettings(openai_api_key="가상-키-아님", log_sink="db", run_mode="live", run_max_usd=TINY_USD)
    monkeypatch.setattr(context, "app_config", lambda: SimpleNamespace(llm=settings))
    login(client)
    run_id = post_run(client, body_of(upload(client, world), {"reportYear": 2025})).json()["id"]
    execute(world, run_id)
    run = failed_run(world, run_id)
    assert (run.error_code, run.failed_step) == ("step_error", "c1")
    assert len(world.mock.texts) == 1
    assert client.get(f"/api/inventory/scope3/runs/{run_id}/result").status_code == 409


def test_after_the_provider_is_fixed_a_resume_redoes_only_the_failed_step(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """401 → failed·step_error(c4). 고친 뒤 resumeFromRunId: 끝난 c1·c2 는 옮기고(공급사 0) c4 부터 → done ·
    흐름 바로 돌린 것과 같은 sha. 실패 단계의 partial 은 옮기지 않는다(runs 의 _carried — c4 는 처음부터)."""
    world.mock = Rejecting()
    login(client)
    document_id = upload(client, world)
    failed_id = post_run(client, body_of(document_id, {"reportYear": 2025})).json()["id"]
    execute(world, failed_id)
    run = failed_run(world, failed_id)
    assert (run.error_code, run.failed_step) == ("step_error", "c4")
    first = {r.step for r in world.sink.records if r.run_id == str(failed_id)}
    assert first == {"c1", "c2", "c4"}  # 앞 실행은 c1·c2 를 실제로 부르고 c4 첫 거리 물음에서 멈춤
    world.mock.reject = False
    made = post_run(client, body_of(document_id, {}, resumeFromRunId=failed_id))
    assert made.status_code == 201, made.content.decode()
    resumed_id: int = made.json()["id"]
    execute(world, resumed_id)
    assert sha(done_body(world, resumed_id)) == sha(direct(2025, world.company_a))
    steps = {r.step for r in world.sink.records if r.run_id == str(resumed_id)}
    assert steps == {"c4"}  # 옮긴 c1·c2 는 공급사 0 · assemble 실제 0
