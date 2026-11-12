# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""데이터 검증을 진짜 DB 의 실행 만들기·실행기로 잰다(밴드 DV1d §3-2, 업무 층). 저장소는 가짜, 태스크는 함수를 직접
부른다(translation/tests/flows/test_runs_translation.py 꼴). 전역 REGISTRY·BINDINGS 의 끼움(apps.py 가 단 것)을 쓴다.

    3-2-1  문서 없이 POST /runs {module: dataverify, options: {input}} 201·판 묶음 → 실행기 끝(모의) → done·결과 한 행·
           엑셀 · documentId null · 문서 읽기 0
    3-2-2  고리 요청 셋의 비용 상한 1·3·1 · 인사이트의 web_search · 호출 기록의 run_id·tenant(회사 id 글자)
    3-2-3  옵션 거절 400 INVALID_OPTIONS(끼움 문장)·행 0 · 256KiB 경계(바로 밑 201·done, 바로 위 400) · 20KiB 201
    3-2-4  documentId 를 주면 422 DOCUMENT_NOT_ACCEPTED·행 0
    3-2-5  서버 그대로(공급사 make 를 갈지 않음 — 키 없는 openai) → failed·setup_error·plan(★C) · 이어 돌기(★D)
    3-2-6  ★B: 실행기를 거친 요청의 user 글 == 같은 dict 를 run_flow 에 바로 넣은 것
    3-2-7  대상 테마 없음 → done·no_target_theme·공급사 호출 0·엑셀 있음
    DV1f   입력 출처 source: 만들기 201(file·paste)·GET 에 그대로 · 255자 이름을 품은 256KiB 경계 ·
           거절 400 글에 이름 0 · 이어 돌기가 source 를 잇고 다른 source 는 422(★D) ·
           이름이 요청·결과·엑셀·호출 기록·로그에 0(★F)
★ 공급사: context.build_client 의 make 를 갈아 openai 에 대본 심은 MockProvider(실제 공급사·키·네트워크 0). 정본
  models.json(가상 mock-synthetic 경로는 web_search·32,768 을 거절한다 — tests/flows/support.py).
★ 실행·결과 행은 runs 의 selectors 로 읽는다(runs.models 를 import 하지 않는다 — 계약 나). 입력은 전부 지어낸 것이다.
"""

import contextlib
import io
import json
import logging
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import Any

import pytest
from django.test import Client

from esgapi.config.env import JobSettings
from esgapi.core.calc.ai_settings import defaults, model_settings_sha256
from esgapi.core.flows.run import run_flow
from esgapi.core.llm.client import LlmClient, ToolCallRequest
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import ToolExecutor, ToolLoopResult, UrlCitation, WebSearchTool
from esgapi.core.models import DocumentRow
from esgapi.core.resources import llm as llm_adapters
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.dataverify.contracts import shapes
from esgapi.dataverify.flows import colab_156, prompt_model_156
from esgapi.dataverify.flows.binding_156 import DataverifyBinding
from esgapi.dataverify.outputs.digest import digest
from esgapi.dataverify.tests.flows.settings_store import file_config
from esgapi.dataverify.tests.flows.support import binding, octets, options, real_client, received, sized
from esgapi.runs import context, tasks
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
INSIGHT = """## 가상 인사이트

| 영역 | 지표 | 관찰 | 리스크 | 해석 |
|---|---|---|---|---|
| 환경 | 가상 지표 A | 가상 관찰 A | 가상 리스크 A | 가상 해석 A |
"""
CITATION = UrlCitation(url="https://example.com/synthetic-a", title="가상 출처 A", start_index=0, end_index=1)


class RetryAsked(Exception):
    """가짜 retry 가 돌려주는 것."""


@dataclass
class World:
    storage: FakeStorage
    company_a: int
    company_b: int
    mock: MockProvider = field(default_factory=lambda: MockProvider("openai"))
    sink: MemorySink = field(default_factory=MemorySink)
    tool_requests: list[ToolCallRequest] = field(default_factory=lambda: [])

    def retry(self, **kwargs: Any) -> RetryAsked:
        return RetryAsked()


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)
    made = World(storage, *companies)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "monotonic", lambda: 0.0)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: 240)
    monkeypatch.setattr(context, "call_sink", lambda: made.sink)
    original = LlmClient.call_tools

    def recorded(self: LlmClient, request: ToolCallRequest, execute: ToolExecutor) -> ToolLoopResult:
        made.tool_requests.append(request)
        return original(self, request, execute)

    monkeypatch.setattr(LlmClient, "call_tools", recorded)
    return made


def scripted(monkeypatch: pytest.MonkeyPatch, world: World) -> None:
    """실행기의 클라이언트가 openai 를 대본 심은 world.mock 으로 짓게 한다."""

    def make(name: str, **kwargs: Any) -> Any:
        if name == "openai":
            return world.mock
        return llm_adapters.make(name, **kwargs)

    monkeypatch.setattr(context, "build_client", partial(context.build_client, make=make))


def happy(mock: MockProvider) -> MockProvider:
    """Plan 한 걸음(산식 하나), 검토 한 걸음(글), 인사이트 한 걸음(표 + 출처 하나 + 검색 1건)."""
    mock.enqueue_text("['가상 산식 A']")
    mock.enqueue_text("가상 검토 리포트")
    mock.enqueue_text(INSIGHT, citations=(CITATION,), hosted_calls=1)
    return mock


def create(client: Client, body: Mapping[str, object]) -> Any:
    login(client)
    return client.post("/api/runs", data=body, content_type="application/json")


def new_run(client: Client, given: Mapping[str, object]) -> int:
    response = create(client, {"module": "dataverify", "options": given})
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
    found = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    assert [r.schema_version for r in found] == ["dataverify.result@2", "dataverify.digest@1"]  # 둘째는 요약(DV1g)
    only = found[0]
    assert isinstance(only.body, dict)
    assert found[1].body == digest(only.body)  # 요약은 그 결과의 셈(이어 돌기도 — ★H)
    return only.body  # pyright: ignore[reportReturnType]


def document_gets(world: World) -> list[str]:
    return [key for key in world.storage.get_calls if "/documents/" in key]


def done_run(client: Client, world: World, monkeypatch: pytest.MonkeyPatch, given: Mapping[str, object]) -> int:
    scripted(monkeypatch, world)
    happy(world.mock)
    run_id = new_run(client, given)
    execute(world, run_id)
    assert world.mock.pending == 0
    return run_id


# ── 3-2-1 끝까지 ──


def test_post_runs_dataverify_without_a_document_is_201_with_the_versions(client: Client, world: World) -> None:
    run_id = new_run(client, options())
    run = run_of(world, run_id)
    assert (run.module, run.flow_id, run.status, run.document_id) == (
        "dataverify",
        "dataverify.colab@156",
        "queued",
        None,
    )
    assert run.versions == {
        "engine": "colab_156",
        "flow": "dataverify.colab@156",
        "promptIds": {"plan": "dataverify/plan@1", "review": "dataverify/review@1", "insight": "dataverify/insight@1"},
        "route": "standard-openai-41",
        # DVA1 ③: 적용 판 없음 = 기본 판의 열쇠(promptsSha256 은 저장 글 판만)
        "aiSetting": "기본 설정",
        "aiSettingId": None,
        "modelSettingsSha256": model_settings_sha256(defaults(file_config(), prompt_model_156.MODELS)),
    }
    steps = run_selectors.step_rows(company_id=world.company_a, run_id=run_id)
    assert [s.name for s in steps] == ["load", "plan", "review", "insight", "report"]


def test_the_executor_runs_dataverify_to_done_with_a_result_and_the_workbook(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = done_run(client, world, monkeypatch, options())
    run = run_of(world, run_id)
    assert (run.status, run.error_code, run.failed_step, run.attempts) == ("done", None, None, 1)
    body = result_body(world, run_id)
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(body, strict=True)
    assert (body["plan"]["formulas"], body["review"]["report"]) == (["가상 산식 A"], "가상 검토 리포트")
    assert [s["url"] for s in body["insight"]["sources"]] == ["https://example.com/synthetic-a"]
    assert len(world.mock.calls) == 3

    response = client.get(f"/api/runs/{run_id}")
    assert response.status_code == 200
    out = response.json()
    assert (out["status"], out["documentId"]) == ("done", None)
    assert [(s["step"], s["status"]) for s in out["steps"]] == [
        ("load", "done"),
        ("plan", "done"),
        ("review", "done"),
        ("insight", "done"),
        ("report", "done"),
    ]
    assert out["resultShapes"] == ["dataverify.result@2", "dataverify.digest@1"]
    assert out["files"] == ["dataverify-report.xlsx"]
    workbook = client.get(f"/api/runs/{run_id}/files/dataverify-report.xlsx")
    assert workbook.status_code == 200
    assert workbook.content[:4] == b"PK\x03\x04"
    assert document_gets(world) == []
    listed = client.get("/api/runs", {"module": "dataverify"}).json()["results"]
    assert [(r["id"], r["documentId"], r["documentName"]) for r in listed] == [(run_id, None, None)]


# ── 3-2-2 요청에 실린 것 ──


def test_the_requests_carry_the_stage_costs_web_search_and_the_run_and_company_tags(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = done_run(client, world, monkeypatch, options())
    assert [(r.prompt, r.max_cost_usd) for r in world.tool_requests] == [
        ("dataverify/plan@1", 1.0),
        ("dataverify/review@1", 3.0),
        ("dataverify/insight@1", 1.0),
    ]
    assert world.mock.calls[-1].tools == (WebSearchTool(search_context_size="medium"),)
    assert world.sink.records
    assert {r.run_id for r in world.sink.records} == {str(run_id)}
    assert {(r.tenant, r.module) for r in world.sink.records} == {(str(world.company_a), "dataverify")}


# ── 3-2-3 만들기 거절 ──


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ({}, "옵션 input이(가) 없어요"),
        (options(webSearch=True), "알 수 없는 옵션이에요: webSearch"),
        (
            {"input": {**received(), "schemaVersion": "dataverify.input@2"}},
            "옵션 input.schemaVersion의 값이 맞지 않아요",
        ),
    ],
    ids=["empty", "webSearch", "schemaVersion"],
)
def test_options_that_do_not_fit_are_400_with_the_binding_sentence_and_no_row(
    client: Client, world: World, given: dict[str, Any], message: str
) -> None:
    response = create(client, {"module": "dataverify", "options": given})
    assert (response.status_code, response.json()["error"]["code"]) == (400, "INVALID_OPTIONS")
    assert response.json()["error"]["message"] == message
    assert run_count(world) == 0


def test_options_just_under_256kib_run_to_done(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = done_run(client, world, monkeypatch, sized(262_144 - 512))
    assert run_of(world, run_id).status == "done"


def test_options_of_exactly_256kib_are_accepted(client: Client, world: World) -> None:
    new_run(client, sized(262_144))


@pytest.mark.parametrize("over", [1, 1024])
def test_options_over_256kib_are_400_before_the_binding(client: Client, world: World, over: int) -> None:
    response = create(client, {"module": "dataverify", "options": sized(262_144 + over)})
    assert (response.status_code, response.json()["error"]["code"]) == (400, "INVALID_OPTIONS")
    assert response.json()["error"]["message"] == "옵션이 너무 크다(JSON 으로 262144바이트까지)"
    assert run_count(world) == 0


def test_options_of_20kib_are_over_the_default_16kib_and_still_accepted(client: Client, world: World) -> None:
    run_id = new_run(client, sized(20 * 1024))
    assert run_of(world, run_id).status == "queued"


# ── 3-2-4 문서를 주면 ──


def test_a_document_id_is_not_accepted(client: Client, world: World) -> None:
    key = f"companies/{world.company_a}/documents/dv1d/original"
    etag = world.storage.put(key, b"synthetic")
    row = DocumentRow.for_company(world.company_a).create(
        company_id=world.company_a,
        uploaded_by="1",
        file_name="synthetic.txt",
        storage_key=key,
        size_bytes=9,
        etag=etag,
        status="uploaded",
    )
    response = create(client, {"module": "dataverify", "documentId": row.pk, "options": options()})
    assert (response.status_code, response.json()["error"]["code"]) == (422, "DOCUMENT_NOT_ACCEPTED")
    assert run_count(world) == 0


# ── 3-2-5 서버 그대로·이어 돌기 ──


def server_as_is(client: Client, world: World) -> int:
    """make 를 갈지 않은 서버 그대로(키가 빈 openai)로 돈 실행."""
    run_id = new_run(client, options())
    execute(world, run_id)
    return run_id


def test_the_server_as_is_ends_the_run_without_calling_a_provider(client: Client, world: World) -> None:
    run_id = server_as_is(client, world)
    run = run_of(world, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "setup_error", "plan")
    assert world.mock.calls == []
    assert [r.prompt for r in world.tool_requests] == ["dataverify/plan@1"]  # 고리를 부르나 공급사를 짓다 멈춘다


def test_resuming_a_failed_run_goes_the_documentless_way(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = server_as_is(client, world)
    asked: list[tuple[Mapping[str, object], int]] = []
    original = DataverifyBinding.inputs_with  # DVA1 ③: 실행기는 판 길(inputs_with)로 부른다

    def spied(
        self: DataverifyBinding, given: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> Any:
        asked.append((given, company_id))
        return original(self, given, company_id=company_id, versions=versions)

    monkeypatch.setattr(DataverifyBinding, "inputs_with", spied)
    scripted(monkeypatch, world)
    happy(world.mock)
    response = create(client, {"module": "dataverify", "resumeFromRunId": failed})
    assert response.status_code == 201, response.content.decode()
    resumed: int = response.json()["id"]
    execute(world, resumed)
    run = run_of(world, resumed)
    assert (run.status, run.document_id) == ("done", None)
    assert asked == [(options(), world.company_a)]
    assert result_body(world, resumed)["schemaVersion"] == "dataverify.result@2"  # DV1e ★D: 이어 돌기도 @2 를 낸다
    assert document_gets(world) == []


# ── 3-2-6 ★B 열쇠 차례 ──


def test_the_executor_sends_the_same_user_text_as_run_flow(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = {
        "메모": "",
        "ID": "E-900",
        **{k: v for k, v in received()["data"]["환경"][0].items() if k not in ("메모", "ID")},
    }
    given = received()
    given["data"]["환경"] = [item, *given["data"]["환경"][1:]]
    done_run(client, world, monkeypatch, {"input": given})
    through_runs = world.mock.calls[0].user

    direct = happy(MockProvider("openai"))
    run_flow(
        colab_156.FLOW,
        binding().inputs({"input": given}, company_id=world.company_a),
        colab_156.DataverifyAdapters(llm=real_client(direct)),
    )
    assert direct.calls[0].user == through_runs
    assert '"메모":"","ID":"E-900"' in repr(through_runs)


# ── 3-2-7 대상 테마 없음 ──


def test_no_target_theme_is_done_with_a_warning_and_no_provider_call(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    run_id = new_run(client, {"input": received(environment=False)})
    execute(world, run_id)
    assert run_of(world, run_id).status == "done"
    assert [w["code"] for w in result_body(world, run_id)["warnings"]] == ["no_target_theme"]
    assert world.mock.calls == []
    assert client.get(f"/api/runs/{run_id}").json()["files"] == ["dataverify-report.xlsx"]


# ── DV1f 입력 출처 source ──

TAIL = "zq7x"
"""이름 꼬리. 16진 밖 글자라 uuid·sha256 의 우연한 글자에 걸리지 않는다(MARC-ISSUE-354)."""
NAME = f"가상출처파일-{TAIL}.json"
"""지은 파일 이름. ★F 는 이 글자(와 꼬리 TAIL)가 닿으면 안 되는 곳을 훑는다."""
FILE = {"kind": "file", "name": NAME}


def test_the_name_tail_is_not_hex() -> None:
    assert not set(TAIL) <= set("0123456789abcdef-")  # uuid 는 「-」 도 품는다


@pytest.mark.parametrize("source", [FILE, {"kind": "paste"}], ids=["file", "paste"])
def test_a_run_with_a_source_is_201_and_get_shows_it_as_given(
    client: Client, world: World, source: dict[str, Any]
) -> None:
    run_id = new_run(client, options(source=source))
    out = client.get(f"/api/runs/{run_id}").json()
    assert out["options"]["source"] == source
    assert list(out["options"]) == ["input", "source"]


def with_long_source(target: int) -> dict[str, Any]:
    """255자 이름의 source 를 품고 크기가 정확히 target 바이트인 옵션(source 몫을 빼고 sized 로 채운다)."""
    source = {"kind": "file", "name": "가" * 255}
    share = octets(options(source=source)) - octets(options())
    given = {**sized(target - share), "source": source}
    assert octets(given) == target
    return given


def test_options_of_exactly_256kib_with_a_255_char_name_are_accepted(client: Client, world: World) -> None:
    run_id = new_run(client, with_long_source(262_144))
    assert client.get(f"/api/runs/{run_id}").json()["options"]["source"]["name"] == "가" * 255


def test_options_one_byte_over_256kib_with_a_255_char_name_are_400(client: Client, world: World) -> None:
    response = create(client, {"module": "dataverify", "options": with_long_source(262_145)})
    assert (response.status_code, response.json()["error"]["code"]) == (400, "INVALID_OPTIONS")
    assert response.json()["error"]["message"] == "옵션이 너무 크다(JSON 으로 262144바이트까지)"
    assert run_count(world) == 0


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ({"kind": "paste", "name": NAME}, "알 수 없는 옵션이에요: source.name"),
        ({"kind": "file", "name": f"가상폴더/{NAME}"}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": f"{NAME}\u202e"}, "옵션 source.name의 값이 맞지 않아요"),
    ],
    ids=["paste-with-name", "slash", "bidi"],
)
def test_a_source_that_does_not_fit_is_400_without_the_name_and_no_row(
    client: Client, world: World, source: dict[str, Any], message: str
) -> None:
    response = create(client, {"module": "dataverify", "options": options(source=source)})
    assert (response.status_code, response.json()["error"]["code"]) == (400, "INVALID_OPTIONS")
    assert response.json()["error"]["message"] == message
    assert TAIL not in response.content.decode()
    assert run_count(world) == 0


def test_resuming_a_failed_run_keeps_its_source_and_another_source_is_a_mismatch(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = new_run(client, options(source=FILE))
    execute(world, failed)
    assert run_of(world, failed).status == "failed"

    other = create(
        client,
        {"module": "dataverify", "resumeFromRunId": failed, "options": options(source={"kind": "paste"})},
    )
    assert (other.status_code, other.json()["error"]["code"]) == (422, "RESUME_MISMATCH")

    scripted(monkeypatch, world)
    happy(world.mock)
    response = create(client, {"module": "dataverify", "resumeFromRunId": failed})
    assert response.status_code == 201, response.content.decode()
    resumed: int = response.json()["id"]
    assert run_of(world, resumed).options == options(source=FILE)
    execute(world, resumed)
    assert run_of(world, resumed).status == "done"


def workbook_text(client: Client, run_id: int) -> str:
    """엑셀(zip) 안 모든 부분을 풀어 이은 글."""
    content = client.get(f"/api/runs/{run_id}/files/dataverify-report.xlsx").content
    with zipfile.ZipFile(io.BytesIO(content)) as book:
        return "".join(book.read(part).decode("utf-8", "replace") for part in book.namelist())


def test_the_name_reaches_no_request_result_workbook_call_record_or_log(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    run_id = done_run(client, world, monkeypatch, options(source=FILE))
    assert run_of(world, run_id).status == "done"
    places = {
        "requests": repr(world.mock.calls) + repr(world.tool_requests),
        "result": json.dumps(result_body(world, run_id), ensure_ascii=False),
        "workbook": workbook_text(client, run_id),
        "call records": repr(world.sink.records),
        "log": caplog.text,
    }
    assert all(places.values())
    assert {where for where, text in places.items() if TAIL in text or "가상출처파일" in text} == set()
