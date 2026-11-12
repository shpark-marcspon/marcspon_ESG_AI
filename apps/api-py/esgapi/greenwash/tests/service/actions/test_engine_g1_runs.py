"""흐름 greenwash.engine@G1 을 진짜 DB 의 실행 만들기·실행기·문서 산출물 포트(service/actions/engine_g1.RunG1Documents)
로 한 바퀴 잰다(밴드 GE1b ③ — T16~T19 의 실행기 몫). 전역 REGISTRY·BINDINGS 는 apps.py 가 단 그대로다(바꿔 끼움 0).

    T16  직렬: POST /runs flowId G1 201 → 실행기 → done · result@2 한 행 · versions = 판 열쇠 + flow · 호출 기록 run_id
    T17  쪽지(segment_parallel 2): 주차 → 구획 쪽지 → done · 결과 바이트 = 직렬
    T18  이어 돌기: judge 구획 하나 끝난 뒤 마감으로 시도를 접고 다시 → 끝난 구획 0회·index 다시 0회 · 결과 = 직렬 ·
         고른 다시(retrySegments) → 그 구획만 부름 · 같은 결과
    T19  묶음 export → import(B) 에 G1 실행·구획 행 · 넣은 실행에서 고른 다시 201 → done(B 에서 산출물을 다시 지음)
    포트  RunG1Document: 산출물 짓기 한 번·뒤는 찾기만 · 다른 회사·없는 실행 → document_missing · 문서가 바뀌면
         (etag) 뒤 단계가 G1ArtifactChanged
    T25b 켬으로 만든 done 실행 → 끔 → 고른 다시 400 INVALID_OPTIONS · 행 0
★ 스위치: Config.greenwash_g1_runs_enabled 의 기본은 끔이라(D4) world 하나가 켠다(test_binding_157_end_to_end 꼴). 끔은
  test_engine_g1_switch.py 가 world 밖에서 잰다(함정 ⑥).
★ 공급사: context.build_client·build_embedding_client 의 make 를 갈아 openai 자리에 대본 모의(채팅 = 꼴 이름으로 답 +
  탐지 · 임베딩 = MockEmbeddingProvider). 파서는 끼움 문서 포트의 parser 를 FakeParser 로(파서 HTTP 0). 실제
  공급사·키·네트워크 0. 문서·문장은 지어낸 글(실제 기업·보고서 0).
"""

import contextlib
import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import partial
from io import StringIO
from pathlib import Path
from typing import Any, cast

import pytest
from django.core.management import call_command
from django.test import Client

from esgapi.config.env import JobSettings
from esgapi.core.flows.binding import BINDINGS
from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockEmbeddingProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, InvokeOptions, ProviderRequest, ProviderResponse
from esgapi.core.models import DocumentRow
from esgapi.core.resources import llm as llm_adapters
from esgapi.core.resources import queue
from esgapi.core.resources.ports.parser import Parsed
from esgapi.core.tests.artifact_fakes import fake_document, fake_places, section
from esgapi.core.tests.resource_fakes import FakeParser, FakeStorage, build_pdf
from esgapi.greenwash.contracts import result2_shapes as r2
from esgapi.greenwash.flows import engine_g1 as E
from esgapi.greenwash.flows.binding_g1 import G1Binding
from esgapi.greenwash.service.actions import engine_g1 as port
from esgapi.greenwash.tests.flows.test_engine_g1_flow import PAGE_SENTENCES, Answering, page_blocks
from esgapi.runs import context, tasks
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.services import runs as run_services
from esgapi.user.service.services.user import create_customer_user
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
OPTIONS: dict[str, Any] = {"parts": {"ceo": [1], "company": [2, 3], "climate": [3, 4]}}
PDF = build_pdf(4, text="Synthetic greenwash engine report")
PDF_NEXT = build_pdf(4, text="Synthetic greenwash engine report second")
FILE_NAME = "가상-2차-보고서.pdf"
LATE = 10_000.0


def parsed(content: bytes) -> Parsed:
    """지어낸 PDF 의 판 2 분해(쪽 넷 — 흐름 시험의 page_blocks). source.sha256 = 바이트의 sha."""
    sha = hashlib.sha256(content).hexdigest()
    blocks = [b for n in (1, 2, 3, 4) for b in page_blocks(n)]
    sections = [section("s1", "가상 환경 경영", page_start=1, page_end=4)]
    return Parsed(
        document=fake_document(sha, page_count=4, blocks=blocks, sections=sections),
        char_places=fake_places(sha, page_count=4),
    )


def fake_parser() -> FakeParser:
    return FakeParser({hashlib.sha256(c).hexdigest(): parsed(c) for c in (PDF, PDF_NEXT)})


class Script(Answering):
    """openai 자리의 대본: 꼴 이름 있는 요청(facets·rerank·judge)은 Answering, 꼴 없는 요청은 E0 탐지(쪽 번호로 그 쪽
    문장 JSON — 흐름 시험의 Detect 와 같은 답). 판정 부름의 주장 글을 적는다(구획마다 몇 번 불렸는지)."""

    def __init__(self) -> None:
        super().__init__()
        self.judged: list[str] = []
        self.detected: list[int] = []

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        if request.json_schema is None:
            self.calls.append(request)
            user = "".join(getattr(p, "text", "") for p in request.user)
            m = re.search(r"(\d+)페이지", user)
            page = int(m.group(1)) if m else 0
            self.detected.append(page)
            body = [{"sentence": s} for s in PAGE_SENTENCES.get(page, [])]
            return Completed(text=json.dumps(body, ensure_ascii=False), usage=SYNTHETIC_USAGE)
        if request.json_schema.name not in ("facets", "rerank"):
            self.judged.append("".join(getattr(p, "text", "") for p in request.user))
        return super().invoke(request, options)


class RetryAsked(Exception):
    """가짜 retry 가 돌려주는 것."""


@dataclass
class World:
    storage: FakeStorage
    company_a: int
    company_b: int
    chat: Script = field(default_factory=Script)
    embedding: MockEmbeddingProvider = field(default_factory=lambda: MockEmbeddingProvider("openai"))
    parser: FakeParser = field(default_factory=fake_parser)
    sink: MemorySink = field(default_factory=MemorySink)
    mono: float = 0.0
    parallel: int = 1
    notes: list[tuple[str, dict[str, Any]]] = field(default_factory=list[tuple[str, dict[str, Any]]])
    fold_after_segments: int | None = None
    finished_segments: int = 0
    retries: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])

    def retry(self, **kwargs: Any) -> RetryAsked:
        self.retries.append(kwargs)
        return RetryAsked()


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int], settings: Any) -> World:
    settings.ESG_CONFIG = dataclasses.replace(settings.ESG_CONFIG, greenwash_g1_runs_enabled=True)
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)
    made = World(storage, *companies)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "monotonic", lambda: made.mono)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: 240)
    monkeypatch.setattr(tasks, "segment_parallel", lambda: made.parallel)
    monkeypatch.setattr(context, "call_sink", lambda: made.sink)

    def make(name: str, **kwargs: Any) -> Any:
        return made.chat if name == "openai" else llm_adapters.make(name, **kwargs)

    def make_embedding(name: str, **kwargs: Any) -> Any:
        return made.embedding if name == "openai" else llm_adapters.make_embedding(name, **kwargs)

    monkeypatch.setattr(context, "build_client", partial(context.build_client, make=make))
    monkeypatch.setattr(context, "build_embedding_client", partial(context.build_embedding_client, make=make_embedding))
    binding = BINDINGS.get(E.FLOW_ID)
    assert isinstance(binding, G1Binding)
    documents = cast("port.RunG1Documents", binding.documents)
    monkeypatch.setattr(documents, "parser", lambda: made.parser)  # 파서 HTTP 0
    real_finished = run_services.segment_finished

    def finished(**kwargs: Any) -> Any:
        written = real_finished(**kwargs)
        made.finished_segments += 1
        if made.fold_after_segments is not None and made.finished_segments >= made.fold_after_segments:
            made.mono = LATE  # 다음 사건 뒤 협조 마감 — 시도를 접는다
        return written

    monkeypatch.setattr(run_services, "segment_finished", finished)

    def segment_note(**kw: Any) -> None:
        made.notes.append(("segment", kw))

    def run_note(**kw: Any) -> None:
        made.notes.append(("run", kw))

    monkeypatch.setattr(queue, "enqueue_segment", segment_note)
    monkeypatch.setattr(queue, "enqueue_run", run_note)
    return made


def document(world: World, company: int, content: bytes = PDF) -> int:
    key = f"companies/{company}/documents/ge1b-{len(world.storage.objects)}/original"
    etag = world.storage.put(key, content)
    row = DocumentRow.for_company(company).create(
        company_id=company,
        uploaded_by="1",
        file_name=FILE_NAME,
        storage_key=key,
        size_bytes=len(content),
        etag=etag,
        status="uploaded",
    )
    return row.pk


def post(client: Client, body: Mapping[str, object]) -> Any:
    return client.post("/api/runs", data=dict(body), content_type="application/json")


def new_run(client: Client, document_id: int, **more: object) -> int:
    made = post(
        client, {"module": "greenwash", "flowId": E.FLOW_ID, "documentId": document_id, "options": OPTIONS, **more}
    )
    assert made.status_code == 201, made.content.decode()
    run_id: int = made.json()["id"]
    return run_id


def execute(world: World, run_id: int, company: int | None = None) -> None:
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(world, company_id=str(company or world.company_a), run_id=str(run_id))


def drain(world: World, company: int | None = None, limit: int = 200) -> int:
    delivered = 0
    while world.notes:
        kind, kw = world.notes.pop(0)
        if kind == "run":
            execute(world, int(kw["run_id"]), company)
        else:
            with contextlib.suppress(RetryAsked):
                tasks.execute_segment(world, **{k: str(v) for k, v in kw.items() if k != "countdown"})
        delivered += 1
        assert delivered < limit, "쪽지가 끝나지 않는다"
    return delivered


def run_of(world: World, run_id: int, company: int | None = None) -> run_selectors.Run:
    found = run_selectors.find_run(company_id=company or world.company_a, run_id=run_id)
    assert found is not None
    return found


def result2(world: World, run_id: int, company: int | None = None) -> dict[str, Any]:
    run = run_of(world, run_id, company)
    assert (run.status, run.error_code) == ("done", None), (run.error_code, run.error_message)
    (only,) = run_selectors.run_results(company_id=company or world.company_a, run_id=run_id)
    assert only.schema_version == r2.SHAPE
    body = cast("dict[str, Any]", only.body)
    r2.RESULT2.validate_python(body)  # 저장 꼴(jsonb 는 열쇠 차례를 바꾼다 — 첫 열쇠 규칙은 흐름 출력 몫)
    return body


def segments(client: Client, run_id: int) -> list[dict[str, Any]]:
    got = client.get(f"/api/runs/{run_id}/segments", {"step": "judge", "limit": 100})
    assert got.status_code == 200, got.content.decode()
    return cast("list[dict[str, Any]]", got.json()["results"])


def run_count(company: int) -> int:
    return run_selectors.run_page(
        company_id=company, module=None, status=None, document_id=None, limit=100, offset=0
    ).count


def serial_result(client: Client, world: World) -> tuple[int, dict[str, Any]]:
    run_id = new_run(client, document(world, world.company_a))
    execute(world, run_id)
    return run_id, result2(world, run_id)


def same_but_run(a: Mapping[str, Any], b: Mapping[str, Any]) -> None:
    """두 결과 본문이 실행마다 다를 수 없는 칸까지 바이트로 같다."""
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


# ── T16 직렬 ──


def test_a_g1_run_goes_from_post_to_a_stored_result2(client: Client, world: World) -> None:
    login(client)
    run_id, body = serial_result(client, world)
    run = run_of(world, run_id)
    assert (run.module, run.flow_id) == ("greenwash", E.FLOW_ID)
    binding = BINDINGS.get(E.FLOW_ID)
    assert isinstance(binding, G1Binding)
    assert dict(run.versions) == {**binding.keys(), "flow": E.FLOW_ID}
    assert "promptsSha256" not in run.versions
    assert body["source"]["fileName"] == FILE_NAME
    assert body["segments"] and all(s["status"] == "done" for s in body["segments"])
    assert len(world.chat.judged) == sum(len(s["items"]) for s in body["segments"]) > 0
    assert [sha for sha, _name in world.parser.calls] == [hashlib.sha256(PDF).hexdigest()]  # 짓기 한 번 — 뒤는 찾기만
    assert world.parser.layouts == [2]
    assert {r.run_id for r in world.sink.records} == {str(run_id)}  # 호출 기록은 그 실행의 것
    assert world.embedding.calls  # 임베딩 경로를 지났다(모의)


# ── T17 쪽지 ──


def test_segment_notes_end_with_the_same_result_as_the_serial_run(client: Client, world: World) -> None:
    login(client)
    _serial, alone = serial_result(client, world)
    world.parallel = 2
    run_id = new_run(client, document(world, world.company_a))
    execute(world, run_id)  # 지휘 시도 — 펼침에 닿아 주차
    assert [kind for kind, _ in world.notes].count("segment") == 2
    drain(world)
    same_but_run(result2(world, run_id), alone)
    assert [s["status"] for s in segments(client, run_id)] == ["done"] * len(alone["segments"])


# ── T18 이어 돌기·고른 다시 ──


def test_a_resumed_judge_step_skips_ended_segments_and_reads_the_stored_vectors(client: Client, world: World) -> None:
    login(client)
    _serial, alone = serial_result(client, world)
    planned = len(alone["segments"])
    assert planned >= 2  # 분모: 구획 둘 이상
    alone_judged = len(world.chat.judged)
    alone_embedded = len(world.embedding.calls)
    world.chat.judged.clear()
    world.embedding.calls.clear()
    world.finished_segments = 0
    world.fold_after_segments = 1
    run_id = new_run(client, document(world, world.company_a))
    execute(world, run_id)  # 구획 하나 끝 → 마감 → 시도 접음
    assert run_of(world, run_id).status != "done"
    assert len(world.retries) == 1
    statuses = [s["status"] for s in segments(client, run_id)]
    assert statuses.count("done") == 1
    world.fold_after_segments = None
    world.mono = 0.0
    execute(world, run_id)  # 이어 돎(같은 실행)
    same_but_run(result2(world, run_id), alone)
    assert len(world.chat.judged) == alone_judged  # 끝난 구획 다시 0회
    assert len(world.embedding.calls) == alone_embedded  # 단락 벡터는 index 의 파일에서 — 다시 임베딩 0


def test_retrying_chosen_segments_calls_only_them(client: Client, world: World) -> None:
    login(client)
    first, alone = serial_result(client, world)
    listed = segments(client, first)
    assert len(listed) >= 2
    chosen = listed[-1]
    world.chat.judged.clear()
    retried = new_run(
        client,
        run_of(world, first).document_id or 0,
        retrySegments={"fromRunId": first, "step": "judge", "keys": [chosen["keySha256"]]},
    )
    execute(world, retried)
    same_but_run(result2(world, retried), alone)
    assert len(world.chat.judged) == len(alone["segments"][-1]["items"])
    again = segments(client, retried)
    assert [s["attempts"] for s in again] == [0] * (len(listed) - 1) + [1]
    assert [s["keySha256"] for s in again] == [s["keySha256"] for s in listed]
    assert [s["keySha256"] for s in alone["segments"]] == [s["keySha256"] for s in listed]  # 결과 구획 짝 = 구획 목록


# ── T19 묶음 ──


def a_user(company_id: int, username: str) -> int:
    made = create_customer_user(
        actor_kind="admin",
        company_id=company_id,
        username=username,
        name=f"가상 {username}",
        password="Gasang-Pw-2026!",
    )
    assert isinstance(made, UserCreated)
    return made.user_id


def round_trip(tmp_path: Path, a: int, runs: list[int], b: int, user_b: int) -> dict[int, int]:
    out = tmp_path / "bundle.zip"
    call_command(
        "export_runs", "--company", str(a), "--runs", ",".join(map(str, runs)), "--out", str(out), stdout=StringIO()
    )
    printed = StringIO()
    call_command(
        "import_runs",
        str(out),
        "--company",
        str(b),
        "--user",
        str(user_b),
        "--orphans-out",
        str(tmp_path / "o.txt"),
        stdout=printed,
    )
    return {int(old): int(new) for old, new in re.findall(r"실행 (\d+) → (\d+)", printed.getvalue())}


@pytest.mark.django_db(transaction=True)  # 묶음 명령이 격리 수준을 정한다(test_bundle_carrier 꼴)
def test_an_imported_g1_run_keeps_its_segments_and_retries_chosen_ones(
    client: Client, world: World, tmp_path: Path
) -> None:
    login(client)
    first, alone = serial_result(client, world)
    a_user(world.company_a, "ge1b-a")
    user_b = a_user(world.company_b, "ge1b-b")
    moved = round_trip(tmp_path, world.company_a, [first], world.company_b, user_b)
    new = moved[first]
    imported = run_of(world, new, world.company_b)
    assert (imported.flow_id, imported.status) == (E.FLOW_ID, "done")
    assert dict(imported.versions) == dict(run_of(world, first).versions)  # 판 열쇠에 옮길 id 0(FIXED {})
    same_but_run(result2(world, new, world.company_b), alone)
    ended = run_selectors.ended_segments(company_id=world.company_b, run_id=new)
    assert len(ended["judge"]) == len(alone["segments"])
    # 넣어 온 실행에서 고른 다시 — B 의 세션으로(판이 같으니 201)
    login(client, sub="edk-user-2", tenant_id="tenant-b")
    key = segments(client, new)[-1]["keySha256"]
    world.chat.judged.clear()
    retried = new_run(
        client, imported.document_id or 0, retrySegments={"fromRunId": new, "step": "judge", "keys": [key]}
    )
    execute(world, retried, world.company_b)
    same_but_run(result2(world, retried, world.company_b), alone)
    assert len(world.chat.judged) == len(alone["segments"][-1]["items"])
    assert len(world.parser.calls) == 2  # B 에서 산출물을 다시 지음(묶음은 산출물 표를 싣지 않는다)


# ── 포트 ──


def test_the_port_reads_the_run_document_and_refuses_other_companies(world: World, client: Client) -> None:
    login(client)
    run_id = new_run(client, document(world, world.company_a))
    mine = port.RunG1Documents(parser=lambda: world.parser).for_run(world.company_a, run_id)
    ref = mine.ensure()
    assert not isinstance(ref, port.ArtifactUnreadable | port.ArtifactRefused)
    assert ref.source_sha256 == hashlib.sha256(PDF).hexdigest()
    assert ref.parser.layout == 2
    seen = mine.view(ref)
    assert (seen.artifact_id, len(seen.pages())) == (ref.id, 4)
    assert mine.file_name() == FILE_NAME
    assert mine.ensure() == ref and len(world.parser.calls) == 1  # 있으면 찾기만
    theirs = port.RunG1Documents(parser=lambda: world.parser).for_run(world.company_b, run_id)
    assert theirs.ensure() == port.ArtifactUnreadable("document_missing")
    assert theirs.file_name() == ""
    missing = port.RunG1Documents(parser=lambda: world.parser).for_run(world.company_a, run_id + 10_000)
    assert missing.ensure() == port.ArtifactUnreadable("document_missing")


def test_a_document_replaced_mid_run_is_a_named_failure(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    login(client)
    document_id = document(world, world.company_a)
    run_id = new_run(client, document_id)
    real_started = run_services.step_started

    def started(**kwargs: Any) -> Any:
        if kwargs["step"] == "index":  # extract 뒤 원본이 바뀜(새 etag — 같은 실행 안)
            row = DocumentRow.for_company(world.company_a).get(pk=document_id)
            row.etag = world.storage.put(row.storage_key, PDF_NEXT)
            row.size_bytes = len(PDF_NEXT)
            row.save(update_fields=["etag", "size_bytes"])
        return real_started(**kwargs)

    monkeypatch.setattr(run_services, "step_started", started)
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.failed_step, run.error_code) == ("failed", "index", "step_error")
    assert len(world.parser.calls) == 2  # 바뀐 원본의 산출물을 지었고, 견줌이 다르다고 끝냈다


def test_a_document_over_the_page_limit_fails_extract_without_parsing(client: Client, world: World) -> None:
    """쪽 상한 300(D8 — engine_g1.PAGE_MAX): 올린 문서의 쪽 수가 301 이면 core 가 too_many_pages 로 거절 → extract
    실패 · 파서 0회(검증 3 권고 2)."""
    login(client)
    document_id = document(world, world.company_a)
    DocumentRow.for_company(world.company_a).filter(pk=document_id).update(page_count=E.PAGE_MAX + 1)
    run_id = new_run(client, document_id)
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.failed_step, run.error_code) == ("failed", "extract", "step_error")
    assert world.parser.calls == []
    within = document(world, world.company_a)
    DocumentRow.for_company(world.company_a).filter(pk=within).update(page_count=E.PAGE_MAX)
    assert port.RunG1Documents(parser=lambda: world.parser).for_run(world.company_a, new_run(client, within)).ensure()
    assert len(world.parser.calls) == 1  # 분모: 300 쪽은 상한 안(파서까지 간다)


# ── T25b 켬으로 만든 실행 → 끔 → 고른 다시 ──


def test_retrying_segments_with_the_switch_turned_off_is_refused(client: Client, world: World, settings: Any) -> None:
    login(client)
    first, _alone = serial_result(client, world)
    key = segments(client, first)[0]["keySha256"]
    before = run_count(world.company_a)
    settings.ESG_CONFIG = dataclasses.replace(settings.ESG_CONFIG, greenwash_g1_runs_enabled=False)
    got = post(
        client,
        {
            "module": "greenwash",
            "flowId": E.FLOW_ID,
            "documentId": run_of(world, first).document_id,
            "options": OPTIONS,
            "retrySegments": {"fromRunId": first, "step": "judge", "keys": [key]},
        },
    )
    assert got.status_code == 400, got.content.decode()
    assert got.json()["error"]["code"] == "INVALID_OPTIONS"
    assert "아직 열려 있지 않아요" in got.json()["error"]["message"]
    assert run_count(world.company_a) == before
