# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""원고작성 한 실행을 진짜 DB 의 실행 만들기·실행기로 잰다(밴드 RP1 §3 S13, 업무 층). 저장소는 가짜, 태스크는 함수를
직접 부른다(materiality/tests/flows/test_runs_materiality.py 꼴). 전역 REGISTRY·BINDINGS 의 끼움(apps.py 가 단 것)을
쓴다. 프로젝트·문서 달기·목차는 services 로 넣는다(경로는 ③).

    S13-1  프로젝트 → 문서(build_pdf) → 목차 → POST /runs {module: drafting, options: {projectId}} 201·documentId null
           → 실행기(대본 모의 S2 1 + S3 2) → done·단계 넷·결과 drafting.bullets@3 한 행 · 판 묶음에 목차 판·문서 etag
           (RP2b B9: 출처 = blockId·sentence.boxes(글자 자리째 뷰) · versions v2·@v2·draft@2·segmenter · basis)
    S13-2  documentId 를 주면 422 DOCUMENT_NOT_ACCEPTED · 모르는 옵션 400 INVALID_OPTIONS — 행 0
    S13-3  저장소 잠깐 장애 → 다시 넣음(공급사 0) → 나은 뒤 done
    S13-4  만든 뒤 문서 바이트가 바뀜(etag 다름) → extract 에서 실패(공급사 0)
    S13-5  만든 뒤 목차를 고쳐도 실행은 만들 때의 판으로 돈다
  RP2a ②(§3 S2·S3·S6·S7·S9 — 쪽 글은 core 문서 산출물):
    S2     첫 실행 = 파서 1(판 2·이름 고정) · extract data 에 artifactId·pagesSha256
    S3     같은 문서 다시 생성 = 파서 0·저장소 get 0·pagesSha256 같음 · 바이트가 바뀐(etag 다른) 문서 = 새 분해
    S6     etag 없는 올린 문서 → 만들기 409·행 0
    S7     파서 거절(password_protected) → extract 실패(공급사 0) · 파서 잠깐 장애 → 다시 넣음 → done
  RP2c B8(앞 실행 이어 받기):
    B8-1   첫 실행 done → 목차 PUT 로 잎 하나(energy)의 요구를 바꿈 → POST /runs {base: {runId: 첫 실행}} → 실행기 →
           파서 0·S2 1(그 잎 하나)·S3 1 · GET 결과 200 의 base.matched·옮긴 잎 reusedFrom = 첫 실행
    B8-2   남의 회사(B) 실행 id 를 base 로 → 409 · @2 결과만 있는 실행 id → 409 — 둘 다 없는 실행 id 와 같은 글, 행 0
★ 파서: world 가 끼움의 산출물 포트(RunArtifacts)의 parser 를 FakeParser 로 간다(지어낸 PDF 의 sha256 → 지어낸 분해 —
  파서 HTTP 0, translation/tests/flows/test_runs_translation_pdf.py 꼴).
★ 공급사: context.build_client 의 make 를 갈아 openai 에 대본 심은 MockProvider(실제 공급사·키·네트워크 0). 끼움의
  mock 은 False 로 갈아 실제 경로(light-openai-41)를 탄다. 입력은 전부 지어낸 것이다.
"""

import contextlib
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import Any, cast

import pytest
from django.db import connection
from django.test import Client

from esgapi.config.env import JobSettings
from esgapi.core.documents.contract import EPOCH
from esgapi.core.flows.binding import BINDINGS
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.models import DocumentArtifactRow, DocumentRow
from esgapi.core.resources import llm as llm_adapters
from esgapi.core.resources.ports.parser import Parsed, ParseFailed, ParseFailureDetail, ParseResult
from esgapi.core.resources.ports.storage import StorageUnavailable
from esgapi.core.tests.artifact_fakes import block, container, fake_document, fake_places, run
from esgapi.core.tests.resource_fakes import FakeParser, FakeStorage, build_pdf
from esgapi.drafting.contracts import shapes
from esgapi.drafting.contracts.wire import outline_sha256
from esgapi.drafting.flows import draft_v2
from esgapi.drafting.flows.binding_v2 import DraftingBinding
from esgapi.drafting.service.actions import projects as actions
from esgapi.drafting.service.services import projects
from esgapi.drafting.tests.flows.support import OUTLINE, draft_reply, map_reply
from esgapi.runs import context, tasks
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
PAGE_TEXT = "Synthetic emissions 1200 tCO2eq in 2024"
PDF_BYTES = build_pdf(3, text=PAGE_TEXT)
OTHER_TEXT = "Synthetic second edition 900 tCO2eq"
PDF_OTHER = build_pdf(3, text=OTHER_TEXT)
USER_ID = 1


def parsed_pages(content: bytes, text: str) -> Parsed:
    """지어낸 PDF 의 분해(쪽 셋, 쪽마다 body 문단 하나 = text) — FakeParser 의 표 값. 글자 자리는 블록마다 한 줄 토막
    (y 100~110, 글자 i 의 x = 10 + 5i ~ 15 + 5i — RP2b B9 의 문장 상자)."""
    sha = hashlib.sha256(content).hexdigest()
    x0 = [10.0 + 5 * i for i in range(len(text))]
    lines = [container(f"p{n}", [run(0, 100.0, 110.0, x0, [x + 5 for x in x0])], page=n) for n in (1, 2, 3)]
    return Parsed(
        document=fake_document(sha, page_count=3, blocks=[block(f"p{n}", text, page=n) for n in (1, 2, 3)]),
        char_places=fake_places(sha, page_count=3, containers=lines),
    )


def fake_parser() -> FakeParser:
    return FakeParser(
        {
            hashlib.sha256(PDF_BYTES).hexdigest(): parsed_pages(PDF_BYTES, PAGE_TEXT),
            hashlib.sha256(PDF_OTHER).hexdigest(): parsed_pages(PDF_OTHER, OTHER_TEXT),
        }
    )


class RetryAsked(Exception):
    """가짜 retry 가 돌려주는 것."""


@dataclass
class World:
    storage: FakeStorage
    company_a: int
    company_b: int
    mock: MockProvider = field(default_factory=lambda: MockProvider("openai"))
    sink: MemorySink = field(default_factory=MemorySink)
    retries: list[dict[str, Any]] = field(default_factory=lambda: [])
    parser: Any = field(default_factory=fake_parser)

    def retry(self, **kwargs: Any) -> RetryAsked:
        self.retries.append(kwargs)
        return RetryAsked()


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)
    made = World(storage, *companies)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "monotonic", lambda: 0.0)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: 240)
    monkeypatch.setattr(context, "call_sink", lambda: made.sink)

    def make(name: str, **kwargs: Any) -> Any:
        if name == "openai":
            return made.mock
        return llm_adapters.make(name, **kwargs)

    monkeypatch.setattr(context, "build_client", partial(context.build_client, make=make))
    binding = cast("DraftingBinding", BINDINGS.documentless(draft_v2.FLOW_ID))
    monkeypatch.setattr(binding, "mock", lambda: False)
    monkeypatch.setattr(binding.artifacts, "parser", lambda: made.parser)  # 파서 HTTP 0
    return made


def document(world: World, company: int, content: bytes = PDF_BYTES) -> int:
    key = f"companies/{company}/documents/rp1-{len(world.storage.objects)}/original"
    etag = world.storage.put(key, content)
    row = DocumentRow.for_company(company).create(
        company_id=company,
        uploaded_by=str(USER_ID),
        file_name="지어낸 보고서.pdf",
        storage_key=key,
        size_bytes=len(content),
        etag=etag,
        status="uploaded",
    )
    return row.pk


def project(world: World, outline: Mapping[str, Any] = OUTLINE) -> tuple[int, int]:
    """회사 A 의 프로젝트(문서 달고 목차 넣음). (projectId, documentId)."""
    project_id = projects.create_project(company_id=world.company_a, year=2025, name="지어낸 보고서", user_id=USER_ID)
    document_id = document(world, world.company_a)
    attached = projects.attach_document(
        company_id=world.company_a, project_id=project_id, document_id=document_id, user_id=USER_ID
    )
    assert isinstance(attached, int)
    put = actions.put_outline(company_id=world.company_a, project_id=project_id, outline=outline, user_id=USER_ID)
    assert isinstance(put, actions.OutlinePut)
    return project_id, document_id


def create(client: Client, body: Mapping[str, object]) -> Any:
    login(client)
    return client.post("/api/runs", data=body, content_type="application/json")


def new_run(client: Client, project_id: int) -> int:
    response = create(client, {"module": "drafting", "options": {"projectId": project_id}})
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


def run_count(world: World) -> int:
    page = run_selectors.run_page(
        company_id=world.company_a, module=None, status=None, document_id=None, limit=100, offset=0
    )
    return page.count


def result_body(world: World, run_id: int) -> dict[str, Any]:
    (only,) = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    assert only.schema_version == shapes.RESULT_SHAPE
    assert isinstance(only.body, dict)
    return cast("dict[str, Any]", only.body)


def script(world: World) -> None:
    """S2 한 묶음(쪽 1 → ghg, 2 → energy, 3 → 없음) + S3 둘(ghg·energy). safety 는 쪽 0 → no_material."""
    world.mock.enqueue_text(map_reply((1, ["ghg"]), (2, ["energy"]), (3, [])))
    world.mock.enqueue_text(draft_reply(("배출량 1200 tCO2eq", [("p1", 0)])))
    world.mock.enqueue_text(draft_reply(("2024 기록", [("p2", 0)])))


def test_s13_1_a_run_end_to_end_without_a_document_id(client: Client, world: World) -> None:
    project_id, document_id = project(world)
    run_id = new_run(client, project_id)
    run = run_of(world, run_id)
    assert (run.document_id, run.module, run.flow_id) == (None, "drafting", draft_v2.FLOW_ID)
    assert {key: run.versions[key] for key in ("engine", "flow", "outlineSha256", "documentId")} == {
        "engine": "v2",
        "flow": draft_v2.FLOW_ID,
        "outlineSha256": outline_sha256(OUTLINE),
        "documentId": document_id,
    }
    assert isinstance(run.versions["outlineId"], int) and isinstance(run.versions["documentEtag"], str)
    assert run.versions["flow"] == "drafting.draft@v2" and run.versions["segmenter"] == "drafting-sentences@1"
    assert run.versions["promptIds"] == {"map": "drafting/map@1", "draft": "drafting/draft@2"}

    script(world)
    execute(world, run_id)
    assert world.mock.pending == 0
    run = run_of(world, run_id)
    assert run.status == "done", (run.failed_step, run.error_code, run.error_message)
    steps = run_selectors.step_rows(company_id=world.company_a, run_id=run_id)
    assert [step.name for step in steps] == ["extract", "map", "draft", "report"]
    assert [record.prompt_id for record in world.sink.records] == [
        "drafting/map@1",
        "drafting/draft@2",
        "drafting/draft@2",
    ]

    result = result_body(world, run_id)
    shapes.check_result(result)
    assert (result["projectId"], result["outlineId"], result["outlineSha256"]) == (
        project_id,
        run.versions["outlineId"],
        outline_sha256(OUTLINE),
    )
    assert result["document"] == {
        "documentId": document_id,
        "fileName": "지어낸 보고서.pdf",
        "pageCount": 3,
        "textPages": 3,
        "pages": [{"page": n, "width": 595.0, "height": 842.0} for n in (1, 2, 3)],
    }
    extract = {step.name: step for step in steps}["extract"].data
    assert extract is not None
    assert result["basis"] == {
        "artifactId": extract["artifactId"],
        "parser": extract["parser"],
        "epoch": extract["epoch"],
        "pagesSha256": extract["pagesSha256"],  # RP2c: 재사용 열쇠
    }
    assert result["basis"]["parser"]["layout"] == 2 and result["base"] is None
    leaves = {leaf["key"]: leaf for leaf in result["leaves"]}
    # 쪽 글 「Synthetic emissions 1200 tCO2eq in 2024」 = 39 자리, 끝 부호 없음 → 문장 0 = [0, 39) → x 10 ~ 10 + 5·39
    source = {
        "documentId": document_id,
        "blockId": "p1",
        "page": 1,
        "blockBox": [10.0, 10.0, 100.0, 20.0],
        "sentence": {"index": 0, "boxes": [[10.0, 100.0, 205.0, 110.0]]},
    }
    assert leaves["ghg"]["outcome"]["bullets"] == [
        {"text": "배출량 1200 tCO2eq", "sources": [source], "unsupported": False}
    ]
    assert leaves["energy"]["pages"] == [2]
    assert leaves["safety"]["outcome"] == {"status": "no_material"}
    assert result["settings"]["routes"] == {"map": "light-openai-41", "draft": "light-openai-41"}


def test_s13_2_a_document_id_or_an_unknown_option_is_refused(client: Client, world: World) -> None:
    project_id, document_id = project(world)
    given = {"module": "drafting", "documentId": document_id, "options": {"projectId": project_id}}
    with_document = create(client, given)
    assert with_document.status_code == 422, with_document.content.decode()
    assert with_document.json()["error"]["code"] == "DOCUMENT_NOT_ACCEPTED"
    unknown = create(client, {"module": "drafting", "options": {"projectId": project_id, "extra": 1}})
    assert unknown.status_code == 400, unknown.content.decode()
    assert unknown.json()["error"]["code"] == "INVALID_OPTIONS"
    assert run_count(world) == 0


def test_s13_3_a_storage_outage_puts_the_run_back(client: Client, world: World) -> None:
    project_id, _ = project(world)
    run_id = new_run(client, project_id)
    world.storage.fail_with = StorageUnavailable("가짜 닿지 못함")
    execute(world, run_id)
    assert len(world.retries) == 1
    assert run_of(world, run_id).status != "done"
    assert world.mock.calls == []

    world.storage.fail_with = None
    script(world)
    execute(world, run_id)
    assert run_of(world, run_id).status == "done"
    assert world.mock.pending == 0


def test_s13_4_a_changed_object_fails_the_run(client: Client, world: World) -> None:
    project_id, document_id = project(world)
    run_id = new_run(client, project_id)
    key = DocumentRow.unscoped.get(pk=document_id).storage_key
    world.storage.put(key, build_pdf(3, text="Synthetic other bytes"))
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.failed_step) == ("failed", "extract")
    assert world.mock.calls == []


def test_s13_5_an_outline_changed_after_creation_does_not_change_the_run(client: Client, world: World) -> None:
    project_id, _ = project(world)
    run_id = new_run(client, project_id)
    changed = {"nodes": [{"key": "only", "parentKey": None, "depth": 1, "title": "하나뿐", "requirement": ""}]}
    put = actions.put_outline(company_id=world.company_a, project_id=project_id, outline=changed, user_id=USER_ID)
    assert isinstance(put, actions.OutlinePut) and put.revision == 2

    script(world)
    execute(world, run_id)
    result = result_body(world, run_id)
    assert result["outlineSha256"] == outline_sha256(OUTLINE)
    assert [leaf["key"] for leaf in result["leaves"]] == ["ghg", "energy", "safety"]


# ── RP2a ②: core 문서 산출물 ──


def extract_data(world: World, run_id: int) -> dict[str, Any]:
    steps = run_selectors.step_rows(company_id=world.company_a, run_id=run_id)
    (found,) = [step for step in steps if step.name == "extract"]
    return cast("dict[str, Any]", found.data)


def test_s2_s3_the_first_run_parses_once_and_a_second_run_reads_neither_storage_nor_parser(
    client: Client, world: World
) -> None:
    project_id, document_id = project(world)
    first = new_run(client, project_id)
    script(world)
    execute(world, first)
    assert run_of(world, first).status == "done"
    assert world.parser.layouts == [2] and [name for _, name in world.parser.calls] == ["document.pdf"]
    data = extract_data(world, first)
    (artifact,) = DocumentArtifactRow.for_company(world.company_a).values_list("id", flat=True)
    assert data["artifactId"] == artifact and data["epoch"] == EPOCH and data["parser"]["layout"] == 2
    assert isinstance(data["pagesSha256"], str) and len(data["pagesSha256"]) == 64

    gets = len(world.storage.get_calls)
    second = new_run(client, project_id)
    script(world)
    execute(world, second)
    assert run_of(world, second).status == "done"
    assert len(world.parser.calls) == 1 and len(world.storage.get_calls) == gets  # 재파싱 0·저장소 0
    assert extract_data(world, second)["pagesSha256"] == data["pagesSha256"]
    assert result_body(world, second)["leaves"] == result_body(world, first)["leaves"]

    key = DocumentRow.unscoped.get(pk=document_id).storage_key
    etag = world.storage.put(key, PDF_OTHER)  # 같은 문서의 바이트가 바뀜(etag 다름)
    DocumentRow.unscoped.filter(pk=document_id).update(etag=etag, size_bytes=len(PDF_OTHER))
    third = new_run(client, project_id)
    script(world)
    execute(world, third)
    assert run_of(world, third).status == "done"
    assert len(world.parser.calls) == 2 and DocumentArtifactRow.for_company(world.company_a).count() == 2
    assert extract_data(world, third)["pagesSha256"] != data["pagesSha256"]


def test_s6_an_uploaded_document_without_an_etag_is_refused_at_create(client: Client, world: World) -> None:
    project_id, document_id = project(world)
    DocumentRow.unscoped.filter(pk=document_id).update(etag=None)
    response = create(client, {"module": "drafting", "options": {"projectId": project_id}})
    assert response.status_code == 409, response.content.decode()
    assert run_count(world) == 0 and world.parser.calls == []


class Scripted:
    """차례대로 결과를 내는 가짜 파서(잠깐 장애 → 정상)."""

    def __init__(self, *results: ParseResult) -> None:
        self.results = list(results)
        self.calls = 0

    def parse(self, pdf: bytes, *, file_name: str, layout: int = 1, charts: bool = False) -> ParseResult:
        self.calls += 1
        return self.results.pop(0)


def failed(kind: str, code: str) -> ParseFailed:
    return ParseFailed(kind, ParseFailureDetail(status=503, code=code, message="가짜"))  # type: ignore[arg-type]


def test_s7_a_parser_refusal_fails_and_an_outage_puts_the_run_back(client: Client, world: World) -> None:
    project_id, _ = project(world)
    world.parser = Scripted(failed("rejected", "password_protected"))
    refused = new_run(client, project_id)
    execute(world, refused)
    run = run_of(world, refused)
    assert (run.status, run.failed_step) == ("failed", "extract") and world.mock.calls == []
    assert DocumentArtifactRow.for_company(world.company_a).count() == 0

    world.parser = Scripted(failed("unavailable", "parser_down"), parsed_pages(PDF_BYTES, PAGE_TEXT))
    again = new_run(client, project_id)
    execute(world, again)
    assert len(world.retries) == 1 and run_of(world, again).status != "done" and world.mock.calls == []
    assert DocumentArtifactRow.for_company(world.company_a).count() == 0  # 장애는 행 0(e7 ⑩)
    script(world)
    execute(world, again)
    assert run_of(world, again).status == "done" and world.parser.calls == 2


# ── RP2c B8: 앞 실행 이어 받기 ──

CHANGED = {
    "nodes": [
        {**node, "requirement": "사용량과 절감"} if node["key"] == "energy" else dict(node) for node in OUTLINE["nodes"]
    ]
}


def test_b8_1_a_second_run_on_a_changed_leaf_redrafts_only_that_leaf(client: Client, world: World) -> None:
    project_id, _ = project(world)
    first = new_run(client, project_id)
    script(world)
    execute(world, first)
    assert run_of(world, first).status == "done"
    first_outline = run_of(world, first).versions["outlineId"]
    put = actions.put_outline(company_id=world.company_a, project_id=project_id, outline=CHANGED, user_id=USER_ID)
    assert isinstance(put, actions.OutlinePut) and put.revision == 2

    response = create(
        client, {"module": "drafting", "options": {"projectId": project_id, "base": {"runId": first, "rebuild": []}}}
    )
    assert response.status_code == 201, response.content.decode()
    second: int = response.json()["id"]
    assert run_of(world, second).versions["reuse"] == "drafting-reuse@1"
    records = len(world.sink.records)
    world.mock.enqueue_text(map_reply((2, ["energy"])))
    world.mock.enqueue_text(draft_reply(("에너지 사용량과 절감", [("p2", 0)])))
    execute(world, second)
    assert run_of(world, second).status == "done", run_of(world, second).error_message
    assert world.mock.pending == 0 and len(world.parser.calls) == 1  # 파서 0(첫 실행의 분해 그대로)
    assert [r.prompt_id for r in world.sink.records[records:]] == ["drafting/map@1", "drafting/draft@2"]

    shown = client.get(f"/api/drafting/runs/{second}/result")
    assert shown.status_code == 200, shown.content.decode()
    body = shown.json()
    assert body["base"] == {"runId": first, "outlineId": first_outline, "matched": True, "reason": None}
    leaves, old = (
        {leaf["key"]: leaf for leaf in body["leaves"]},
        {leaf["key"]: leaf for leaf in result_body(world, first)["leaves"]},
    )
    assert leaves["ghg"]["reusedFrom"] == {"runId": first, "outlineId": first_outline}
    assert leaves["ghg"]["outcome"] == old["ghg"]["outcome"]  # 같은 문서 — documentId 도 같다
    assert leaves["energy"]["reusedFrom"] is None
    assert [b["text"] for b in leaves["energy"]["outcome"]["bullets"]] == ["에너지 사용량과 절감"]


def test_rpq1_b5_a_run_made_before_the_texts_key_is_not_carried_over(client: Client, world: World) -> None:
    """RPQ1 앞 글로 지은 앞 실행(열쇠 texts 없음)은 이어 받지 않고 처음부터 — reason versions · 경고 하나."""
    project_id, _ = project(world)
    first = new_run(client, project_id)
    script(world)
    execute(world, first)
    assert run_of(world, first).status == "done"
    with connection.cursor() as cursor:
        cursor.execute("UPDATE run_runs SET versions = versions - 'texts' WHERE id = %s", [first])
    assert "texts" not in run_of(world, first).versions

    response = create(
        client, {"module": "drafting", "options": {"projectId": project_id, "base": {"runId": first, "rebuild": []}}}
    )
    assert response.status_code == 201, response.content.decode()
    second: int = response.json()["id"]
    assert run_of(world, second).versions["texts"] == "drafting-texts@3"
    script(world)
    execute(world, second)
    assert run_of(world, second).status == "done", run_of(world, second).error_message
    assert world.mock.pending == 0

    shown = client.get(f"/api/drafting/runs/{second}/result")
    assert shown.status_code == 200, shown.content.decode()
    body = shown.json()
    assert body["base"]["matched"] is False and body["base"]["reason"] == "versions"
    assert [w["code"] for w in body["warnings"]].count("base_not_reused") == 1
    assert all(leaf["reusedFrom"] is None for leaf in body["leaves"])


def test_rpa4_b5_a_run_made_with_texts_at_1_is_not_carried_over(client: Client, world: World) -> None:
    """RPA4 앞 글(@1 — 「쪽」 낱말·v1 자리 글자)로 지은 앞 실행은 이어 받지 않고 처음부터 — reason versions ·
    경고 하나."""
    project_id, _ = project(world)
    first = new_run(client, project_id)
    script(world)
    execute(world, first)
    assert run_of(world, first).status == "done"
    assert run_of(world, first).versions["texts"] == "drafting-texts@3"
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE run_runs SET versions = jsonb_set(versions, '{texts}', '\"drafting-texts@1\"') WHERE id = %s",
            [first],
        )
    assert run_of(world, first).versions["texts"] == "drafting-texts@1"

    response = create(
        client, {"module": "drafting", "options": {"projectId": project_id, "base": {"runId": first, "rebuild": []}}}
    )
    assert response.status_code == 201, response.content.decode()
    second: int = response.json()["id"]
    assert run_of(world, second).versions["texts"] == "drafting-texts@3"
    script(world)
    execute(world, second)
    assert run_of(world, second).status == "done", run_of(world, second).error_message
    assert world.mock.pending == 0

    body = client.get(f"/api/drafting/runs/{second}/result").json()
    assert body["base"]["matched"] is False and body["base"]["reason"] == "versions"
    assert [w["code"] for w in body["warnings"]].count("base_not_reused") == 1
    assert all(leaf["reusedFrom"] is None for leaf in body["leaves"])


def plant_done_run(company: int, project_id: int, shape: str, body: dict[str, Any]) -> int:
    """끝난 원고작성 실행 하나와 결과 한 행(주인 역할 — 업무 층 연결). options.projectId 는 준 값."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, "
            "versions, purpose, status, attempts, stalled_attempts, created_by_user_id) VALUES (now(), now(), %s, "
            "NULL, 'drafting', %s, %s::jsonb, '{}', 'service', 'done', 1, 0, 7) RETURNING id",
            [company, draft_v2.FLOW_ID, json.dumps({"projectId": project_id})],
        )
        row = cursor.fetchone()
        assert row is not None
        run_id = int(row[0])
        cursor.execute(
            "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
            "VALUES (now(), %s, %s, 0, %s, %s::jsonb)",
            [company, run_id, shape, json.dumps(body, ensure_ascii=False)],
        )
    return run_id


def test_b8_2_another_companys_run_or_an_at_2_result_is_refused_like_a_missing_run(
    client: Client, world: World
) -> None:
    project_id, _ = project(world)
    first = new_run(client, project_id)
    script(world)
    execute(world, first)
    done = result_body(world, first)
    theirs = plant_done_run(world.company_b, project_id, shapes.RESULT_SHAPE, done)  # 회사만 다름
    older = plant_done_run(world.company_a, project_id, "drafting.bullets@2", {**done, "schemaVersion": "x"})
    before = run_count(world)

    def based(run_id: int) -> Any:
        return create(
            client,
            {"module": "drafting", "options": {"projectId": project_id, "base": {"runId": run_id, "rebuild": []}}},
        )

    missing = based(theirs + 1000)
    assert (missing.status_code, missing.json()["error"]["message"]) == (409, "이어 받을 앞 실행을 찾을 수 없어요")
    for refused in (based(theirs), based(older)):
        assert (refused.status_code, refused.content) == (missing.status_code, missing.content)
    assert run_count(world) == before
    assert based(first).status_code == 201  # 분모: 제 회사·@3 결과면 만든다
