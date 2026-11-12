# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""웹이 PDF 에 쓰는 길을 HTTP 째(밴드 TRS3 E1, 발주서 §1-1·§1-2·§1-3 — 업무 층). 새 경로는 layout 하나이고 나머지는
이미 있는 길이다: 올림(POST /documents → 저장소 → confirm 의 pageCount·hasText) → POST /runs {flowId pdf} +
Idempotency-Key → 실행기 → GET /runs/{id}(flowId·steps·resultShapes) → 결과·layout → 묶음 목록 줄(inputKind pdf) →
같은 본문 다시 보냄(앞 실행 201) → 다시 하기(retryPart 꼴 — 받은 options·flowId 그대로) → flowId 빠진 다시 보냄은
워드 흐름이 PDF 를 unsupported_input 으로 거절(웹이 flowId 를 실어야 하는 근거).
저장소·파서는 가짜(PDF 는 시험이 지음 — core resource_fakes.build_pdf, 파서는 그 바이트의 sha256 표), 공급사는 대본 심은
모의(test_runs_translation 의 scripted). ★ 전부 지어낸 것이다.
"""

import hashlib
import uuid
from typing import Any

import pytest
from django.test import Client

from esgapi.core.flows.binding import BINDINGS
from esgapi.core.models import DocumentRow
from esgapi.core.tests.resource_fakes import FakeParser, FakeStorage, build_pdf
from esgapi.runs import context, tasks
from esgapi.translation.contracts.batch_shapes import BATCH_SHAPE, BATCH_SHAPES
from esgapi.translation.contracts.layout_shapes import LAYOUT_SHAPE, LAYOUT_SHAPES
from esgapi.translation.contracts.shapes import RESULT_SHAPE, RESULT_SHAPES
from esgapi.translation.flows import pdf_158 as pdf
from esgapi.translation.tests.engines.colab_158.support import ok
from esgapi.translation.tests.flows.pdf_support import ONE_PAGE_EN, document, parsed
from esgapi.translation.tests.flows.support import options
from esgapi.translation.tests.flows.test_runs_translation import NO_ISSUES, SETTINGS, World, execute, run_of, scripted
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

PDF_BYTES = build_pdf(1, text="Synthetic climate page")
BATCH = "00000000-0000-4000-8000-0000000000e1"


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    """test_runs_translation_pdf 의 world 와 같은 짜임 + 이 PDF 바이트를 아는 가짜 파서."""
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)
    made = World(storage, *companies)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "monotonic", lambda: 0.0)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: 240)
    monkeypatch.setattr(context, "call_sink", lambda: made.sink)
    scripted(monkeypatch, made)
    binding = BINDINGS.get(pdf.FLOW_ID)
    monkeypatch.setattr(binding, "mock", lambda: False)
    known = {hashlib.sha256(PDF_BYTES).hexdigest(): parsed(document(pages=1))}
    monkeypatch.setattr(binding, "parser", lambda: FakeParser(known))
    return made


def upload(client: Client, world: World) -> dict[str, Any]:
    """웹의 uploadDocument: POST /documents → (PUT 은 저장소에 바로) → POST /documents/{id}/confirm 의 document."""
    made = client.post(
        "/api/documents",
        data={"fileName": "지어낸 보고서.pdf", "sizeBytes": len(PDF_BYTES)},
        content_type="application/json",
    )
    assert made.status_code == 201, made.content.decode()
    document_id = made.json()["document"]["id"]
    world.storage.put(DocumentRow.unscoped.get(pk=document_id).storage_key, PDF_BYTES)
    confirmed = client.post(f"/api/documents/{document_id}/confirm")
    assert confirmed.status_code == 200, confirmed.content.decode()
    return confirmed.json()["document"]


def post_run(client: Client, body: dict[str, Any], key: str) -> Any:
    return client.post("/api/runs", data=body, content_type="application/json", headers={"Idempotency-Key": key})


def test_the_web_path_for_a_pdf_end_to_end(client: Client, world: World) -> None:
    login(client)
    doc = upload(client, world)
    assert (doc["pageCount"], doc["hasText"]) == (1, True)  # 입력 그리드의 쪽 수 원천(G3 — 파서 0)

    given = options(batchId=BATCH)
    body = {"module": "translation", "flowId": pdf.FLOW_ID, "documentId": doc["id"], "launchKey": str(uuid.uuid4())}
    body["options"] = given
    key = str(uuid.uuid4())
    first = post_run(client, body, key)
    assert (first.status_code, first.json()["status"]) == (201, "queued"), first.content.decode()
    run_id = first.json()["id"]
    again = post_run(client, body, key)  # 같은 열쇠·같은 본문 → 앞 실행(새 실행 0)
    assert (again.status_code, again.json()["id"]) == (201, run_id)

    world.mock.enqueue(ok(ONE_PAGE_EN)).enqueue(NO_ISSUES)
    execute(world, run_id)
    run = client.get(f"/api/runs/{run_id}").json()
    assert (run["status"], run["flowId"]) == ("done", pdf.FLOW_ID)
    assert [s["step"] for s in run["steps"]] == ["prepare", "translate", "report"]
    assert LAYOUT_SHAPE in run["resultShapes"]  # layout 있음 판별(§1-1)

    result = client.get(f"/api/translation/runs/{run_id}/result")
    assert (result.status_code, result.json()["status"]) == (200, "done")
    RESULT_SHAPES[RESULT_SHAPE].validate_python(result.json(), strict=True)
    layout = client.get(f"/api/translation/runs/{run_id}/layout")
    assert layout.status_code == 200, layout.content.decode()
    LAYOUT_SHAPES[LAYOUT_SHAPE].validate_python(layout.json(), strict=True)
    assert layout.json()["status"] == "done" and layout.json()["source"]["adapter"] == "pdf_tags@3"

    (line,) = client.get("/api/translation/batches").json()["results"]
    BATCH_SHAPES[BATCH_SHAPE].validate_python(line, strict=True)
    assert (line["batchKey"], line["inputKind"], line["parts"][0]["latest"]["flowId"]) == (BATCH, "pdf", pdf.FLOW_ID)

    # retryPart 꼴: GET /runs/{id} 의 options·flowId 를 그대로 + 새 launchKey
    read = client.get(f"/api/runs/{run_id}").json()
    retry = {
        "module": read["module"],
        "flowId": read["flowId"],
        "documentId": read["documentId"],
        "launchKey": str(uuid.uuid4()),
        "options": read["options"],
    }
    world.mock.enqueue(ok(ONE_PAGE_EN)).enqueue(NO_ISSUES)
    redo = post_run(client, retry, str(uuid.uuid4()))
    assert redo.status_code == 201, redo.content.decode()
    execute(world, redo.json()["id"])
    assert run_of(world, redo.json()["id"]).status == "done"
    (line,) = client.get("/api/translation/batches").json()["results"]
    assert (line["parts"][0]["round"], line["parts"][0]["latest"]["runId"], line["inputKind"]) == (
        2,
        redo.json()["id"],
        "pdf",
    )


def test_a_retry_without_the_flow_id_is_the_word_flow_refusing_the_pdf(client: Client, world: World) -> None:
    """flowId 가 빠지면 기본 흐름(워드)이 돈다 — PDF 바이트를 unsupported_input 으로 거절(공급사 0). 웹이 flowId 를
    실어야 하는 근거(§1-1 다시 하기)."""
    login(client)
    doc = upload(client, world)
    body = {"module": "translation", "documentId": doc["id"], "launchKey": str(uuid.uuid4()), "options": options()}
    made = post_run(client, body, str(uuid.uuid4()))
    assert made.status_code == 201, made.content.decode()
    before = len(world.mock.calls)
    execute(world, made.json()["id"])
    run = run_of(world, made.json()["id"])
    assert (run.status, run.flow_id) == ("done", "translation.colab@158")
    result = client.get(f"/api/translation/runs/{made.json()['id']}/result").json()
    assert (result["status"], result["rejection"]["kind"]) == ("rejected", "unsupported_input")
    assert client.get(f"/api/translation/runs/{made.json()['id']}/layout").status_code == 404
    assert len(world.mock.calls) == before
