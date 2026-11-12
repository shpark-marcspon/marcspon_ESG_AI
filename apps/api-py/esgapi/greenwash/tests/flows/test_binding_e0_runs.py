# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""끼움 GreenwashBinding 을 진짜 DB 의 실행 만들기·실행기로 잰다(밴드 G1b §3-2-7~10). 업무 층: 저장소는 가짜, 태스크는
**함수를 직접 부른다**(runs/tests/test_executor.py 의 꼴).

    3-2-7   전역 BINDINGS 의 끼움 · POST /runs greenwash 201 · 판 묶음 · 옵션 거절 400 의 문장
    3-2-8   실행기 끝까지: 새 BindingRegistry 에 모의 경로 끼움(GreenwashBinding(chat_route="mock",
            embedding_route="mock-gw1")) + context.build_client 를 대본 심은 MockProvider 를 내는 partial 로 →
            done, 결과 = 같은 입력의 흐름, 출력 파일 엑셀 하나, 호출 기록의 run_id·tenant. 대본 없는 모의의 끝 모양
    3-2-9   이어 돌기: judge 둘째 쪽 뒤 마감으로 시도를 접고 다시 돈 결과 == 한 번에 돈 결과(추가 단어 든 옵션)
    3-2-10  글자 층 없는 PDF → failed · extract · no_text_layer

★ 실행·결과 행은 runs 의 selectors 로 읽는다(그린워싱 시험은 runs.models 를 import 하지 않는다 — 계약 나).
★ 대본 3-2-8·9 의 쪽 글은 표본(sample_text)이다: colab_e0.PDF_TEXT 를 표본 읽개로 바꿔 끼운다(시험 안만). 문서 bytes 는
  b"synthetic-sample"(골든과 같은 sha256). 3-2-10 은 진짜 읽개(pypdf)와 pdfbuild 로 지은 빈 PDF.
★ 실제 공급사·키·네트워크 0. 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import contextlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import Any

import pytest
from django.test import Client

from esgapi.config.env import JobSettings
from esgapi.core.calc.ai_settings import defaults, model_settings_sha256
from esgapi.core.flows.binding import BINDINGS, BindingRegistry, DocumentInput
from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.models import DocumentRow
from esgapi.core.resources import llm as llm_adapters
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.greenwash.engines.e0.ports import ScriptedChat
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import registration
from esgapi.greenwash.flows.binding_e0 import GreenwashBinding
from esgapi.greenwash.tests import pdfbuild
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.flows.settings_store import DefaultOnlyStore
from esgapi.greenwash.tests.flows.support import REAL_MODELS
from esgapi.runs import context, tasks
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.services import runs as run_services
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

MINIMAL: dict[str, Any] = {"parts": {"ceo": [1], "company": [2], "climate": [3, 4]}}
SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
SOFT_S = 240
LATE = 10_000.0
DEFAULT_MODEL_SHA = model_settings_sha256(defaults(REAL_MODELS.config(), REAL_MODELS.steps()))
"""기본 판 실행의 versions.modelSettingsSha256(AS2b — 실행 만들기의 원천 RunModelSource 와 같은 실제 설정)."""


class RetryAsked(Exception):
    """가짜 retry 가 돌려주는 것."""


@dataclass
class World:
    storage: FakeStorage
    company_a: int
    company_b: int
    mock: MockProvider
    sink: MemorySink = field(default_factory=MemorySink)
    mono: float = 0.0
    retries: list[dict[str, Any]] = field(default_factory=lambda: [])
    after_progress: Callable[[str, int], None] | None = None

    def retry(self, **kwargs: Any) -> RetryAsked:
        self.retries.append(kwargs)
        return RetryAsked()


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)
    mock, _ = s.scripted_provider(40)
    made = World(storage, *companies, mock=mock)
    flows = FlowRegistry()
    registration.register(flows)
    bindings = BindingRegistry()
    bindings.register(
        colab.FLOW_ID,
        GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore(), chat_route="mock", embedding_route="mock-gw1"),
    )
    monkeypatch.setattr(tasks, "REGISTRY", flows)
    monkeypatch.setattr(tasks, "BINDINGS", bindings)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "monotonic", lambda: made.mono)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: SOFT_S)
    monkeypatch.setattr(context, "call_sink", lambda: made.sink)

    def make(name: str, **kwargs: Any) -> Any:
        return made.mock if name == "mock" else llm_adapters.make(name, **kwargs)

    monkeypatch.setattr(context, "build_client", partial(context.build_client, make=make))
    real_progress = run_services.step_progress

    def progress(**kwargs: Any) -> Any:
        written = real_progress(**kwargs)
        if made.after_progress is not None:
            made.after_progress(str(kwargs["step"]), int(kwargs["done"]))
        return written

    monkeypatch.setattr(run_services, "step_progress", progress)
    return made


def sample_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    """끼움의 읽개를 표본 쪽 글로(시험 안만 — 문서 bytes 는 PDF 가 아니다)."""
    monkeypatch.setattr(colab, "PDF_TEXT", s.SamplePdf)


def document(world: World, *, content: bytes = s.SAMPLE_BYTES, name: str = s.SAMPLE_NAME) -> int:
    company = world.company_a
    key = f"companies/{company}/documents/g1b-{len(world.storage.objects)}/original"
    etag = world.storage.put(key, content)
    row = DocumentRow.for_company(company).create(
        company_id=company,
        uploaded_by="1",
        file_name=name,
        storage_key=key,
        size_bytes=len(content),
        etag=etag,
        status="uploaded",
    )
    return row.pk


def create(client: Client, body: Mapping[str, object]) -> Any:
    return client.post("/api/runs", data=body, content_type="application/json")


def new_run(client: Client, world: World, options: Mapping[str, object], **doc: Any) -> int:
    login(client)
    response = create(client, {"module": "greenwash", "documentId": document(world, **doc), "options": options})
    assert response.status_code == 201, response.content.decode()
    run_id: int = response.json()["id"]
    return run_id


def execute(world: World, run_id: int) -> None:
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(world, company_id=str(world.company_a), run_id=str(run_id))


def run_of(world: World, run_id: int) -> run_selectors.Run:
    found = run_selectors.find_run(company_id=world.company_a, run_id=run_id)
    assert found is not None
    return found


def result_body(world: World, run_id: int) -> dict[str, Any]:
    (only,) = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    assert only.schema_version == "greenwash.result@1"
    assert isinstance(only.body, dict)
    return only.body  # pyright: ignore[reportReturnType]


def expected(options: Mapping[str, object]) -> dict[str, Any]:
    """같은 입력을 흐름에 바로 넣은 결과(대본 = ScriptedChat, 표본 쪽 글, 모의 임베딩)."""
    given = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).inputs(
        DocumentInput(content=s.SAMPLE_BYTES, media_type="application/pdf", file_name=s.SAMPLE_NAME),
        options,
    )
    return s.result_of(s.run(given, s.adapters(llm=ScriptedChat())))


# ── 3-2-7 ──


def test_the_process_binding_is_the_greenwash_binding_with_real_routes() -> None:
    binding = BINDINGS.get("greenwash.colab@E0")
    assert isinstance(binding, GreenwashBinding)
    assert (binding.chat_route, binding.embedding_route) == ("light-openai-41", "light-openai")


def test_post_runs_greenwash_is_201_with_the_versions(client: Client, world: World) -> None:
    run_id = new_run(client, world, MINIMAL)
    run = run_of(world, run_id)
    assert (run.module, run.flow_id, run.status, run.options) == ("greenwash", colab.FLOW_ID, "queued", MINIMAL)
    # G2c2: 만들 때의 AI 설정 판 id(적용 판 없음 = None)가 더해진다
    assert run.versions == {
        **colab.run_versions(None),
        "aiSettingId": None,
        "flow": "greenwash.colab@E0",
        "modelSettingsSha256": DEFAULT_MODEL_SHA,
    }
    assert sorted(run.versions) == ["aiSetting", "aiSettingId", "evalPromptSha256", "flow", "modelSettingsSha256"]
    steps = run_selectors.step_rows(company_id=world.company_a, run_id=run_id)
    assert [x.name for x in steps] == list(colab.FLOW.steps)


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({**MINIMAL, "criteria": {}}, "알 수 없는 옵션이에요: criteria"),
        ({"parts": {"ceo": [], "company": [], "climate": []}}, "점검할 페이지를 하나 이상 골라 주세요"),
        ({**MINIMAL, "extraTerms": ["녹색(인증)"]}, "추가 단어에는 괄호나 따옴표를 쓸 수 없어요"),
    ],
)
def test_refused_options_are_400_with_the_bindings_sentence(
    client: Client, world: World, options: dict[str, Any], message: str
) -> None:
    login(client)
    response = create(client, {"module": "greenwash", "documentId": document(world), "options": options})
    assert (response.status_code, response.json()["error"]["code"]) == (400, "INVALID_OPTIONS")
    assert response.json()["error"]["message"] == message
    page = run_selectors.run_page(
        company_id=world.company_a, module=None, status=None, document_id=None, limit=10, offset=0
    )
    assert page.count == 0


# ── 3-2-8 ──


def test_the_executor_runs_the_bound_flow_to_done(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_pages(monkeypatch)
    run_id = new_run(client, world, MINIMAL)
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.error_code, run.failed_step, run.attempts) == ("done", None, None, 1)
    body = result_body(world, run_id)
    assert body == expected(MINIMAL)
    assert s.as_gw1(body) == s.gw1_view(s.golden("sample-mock.json"))
    assert s.provider_hashes(world.mock.calls) == s.golden("sample-mock.json")["messages"]
    outputs = [f.name for f in run_selectors.run_files(company_id=world.company_a, run_id=run_id) if f.step is None]
    assert outputs == ["greenwash-report.xlsx"]
    assert len(world.sink.records) >= 12  # 분모: 대화 12 + 임베딩
    assert {r.run_id for r in world.sink.records} == {str(run_id)}
    assert {r.tenant for r in world.sink.records} == {str(world.company_a)}
    assert {r.module for r in world.sink.records} == {"greenwash"}


def test_an_unscripted_mock_ends_the_run_as_measured(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """대본 없는 모의 대화: 쪽마다 공급사 오류 → 노트북 루프가 삼켜 failed_pages(흠 12·19) — 실행은 done, items 0."""
    sample_pages(monkeypatch)
    world.mock = MockProvider()
    run_id = new_run(client, world, MINIMAL)
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.error_code) == ("done", None)
    body = result_body(world, run_id)
    assert body["items"] == []
    assert [p["page"] for p in body["candidateStats"]["failedPages"]] == [1, 2, 3, 4]


# ── 3-2-9 이어 돌기 ──


def test_a_run_folded_after_the_second_judged_page_resumes_to_the_same_result(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_pages(monkeypatch)
    options = {**MINIMAL, "extraTerms": ["가상상사", "확대"]}
    whole_mock, _ = s.scripted_provider(40)
    world.mock = whole_mock
    whole_id = new_run(client, world, options)
    execute(world, whole_id)
    whole = result_body(world, whole_id)
    assert whole["extraTerms"] == ["가상상사", "확대"]

    world.mock, _ = s.scripted_provider(40)

    def late_after_second(step: str, done: int) -> None:
        if step == "judge" and done == 2 and world.mono == 0.0:
            world.mono = LATE

    world.after_progress = late_after_second
    run_id = new_run(client, world, options)
    execute(world, run_id)
    assert (run_of(world, run_id).status, len(world.retries)) == ("queued", 1)  # 접고 다시 넣음
    judge = next(x for x in run_selectors.step_rows(company_id=world.company_a, run_id=run_id) if x.name == "judge")
    assert (judge.done, judge.total) == (2, 4)
    world.mono = 0.0
    world.after_progress = None
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.attempts) == ("done", 2)
    assert result_body(world, run_id) == whole
    assert s.provider_hashes(world.mock.calls) == s.provider_hashes(whole_mock.calls)  # 끝난 쪽은 다시 묻지 않음


# ── 3-2-10 글자 층 없음 ──


def test_a_pdf_without_a_text_layer_fails_in_extract(client: Client, world: World) -> None:
    doc = pdfbuild.Doc()
    doc.new_page()
    doc.new_page()
    run_id = new_run(client, world, MINIMAL, content=doc.tobytes(), name="scan.pdf")
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.failed_step, run.error_code) == ("failed", "extract", "no_text_layer")
    assert run.error_message == "문서에 글자 층이 없다(스캔 PDF — 모든 쪽의 글이 비었다)"
    assert world.mock.calls == []
    listed = client.get("/api/greenwash/checks")  # 목록 줄에도 같은 code(밴드 G1e)
    assert listed.status_code == 200, listed.content.decode()
    (row,) = [r for r in listed.json()["runs"] if r["runId"] == run_id]
    assert (row["status"], row["errorCode"]) == ("failed", "no_text_layer")
