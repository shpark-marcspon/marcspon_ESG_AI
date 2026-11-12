# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""중대성평가 IRO 한 실행을 진짜 DB 의 실행 만들기·실행기로 잰다(밴드 IR3a §3-2, 업무 층). 저장소는 가짜, 태스크는
함수를 직접 부른다(dataverify/tests/flows/test_runs_dataverify.py 꼴). 전역 REGISTRY·BINDINGS 의 끼움(apps.py 가
단 것)을 쓴다.

    3-2-1  문서 없이 POST /runs {module: materiality, options: {input}} 201·판 묶음 → 실행기 끝(모의 14 호출) → done·
           단계 열·결과 @2 한 행·엑셀 둘 · documentId null · 문서 읽기 0
    3-2-2  호출 기록의 run_id·tenant(회사 id 글자) · 1부 규제·컨트로버시 요청의 web_search · load 의 창 끝 = 서울 날짜
    3-2-3  옵션 거절 400 INVALID_OPTIONS(끼움 문장)·행 0 · 256KiB 경계(바로 밑 201·done, 바로 위 400) · 20KiB 201
    3-2-4  documentId 를 주면 422 DOCUMENT_NOT_ACCEPTED·행 0
    3-2-5  flowId materiality.colab@155(1부 단독 — 끼우지 않음)는 422 FLOW_NOT_RUNNABLE·행 0
    3-2-6  서버 그대로(공급사 make 를 갈지 않음 — 키 없는 openai)의 끝(★C)
    3-2-7  ★B: 실행기를 거친 14 요청 몸 == 같은 입력을 run_flow 에 바로 넣은 것(EXEC_SAME)
    3-2-8  report_iro 에서 실패한 실행을 다음 날 이어 돌림 → 공급사 0·1부 엑셀 바이트 그대로·창 그대로(RESUME_SAME)
★ 공급사: context.build_client 의 make 를 갈아 openai 에 대본 심은 MockProvider(실제 공급사·키·네트워크 0). 정본
  models.json(support.real_client 와 같은 설정). 「오늘」은 binding_155.clock 을 갈아 고정한다(실제 날짜와 다른 값).
★ 실행·결과 행은 runs 의 selectors 로 읽는다(runs.models 를 import 하지 않는다). 입력은 전부 지어낸 것이다.
★ 환경 변수 IR3A_DUMP 가 있으면 3-2-7·3-2-8 이 견준 두 쪽을 그 폴더에 JSON 으로 쓴다(scripts/materiality_compare_ir3a.py
  가 다시 견줘 EXEC_SAME·RESUME_SAME 을 센다). 없으면 쓰지 않는다.
"""

import contextlib
import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from typing import Any, cast

import pytest
from django.test import Client

from esgapi.config.env import JobSettings
from esgapi.core.calc.ai_settings import defaults, model_settings_sha256
from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import OutputFile, StepOutput
from esgapi.core.llm.client import LlmClient, ToolCallRequest
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import ProviderRequest, Tags, ToolExecutor, ToolLoopResult, WebSearchTool
from esgapi.core.models import DocumentRow
from esgapi.core.resources import llm as llm_adapters
from esgapi.core.resources.storage import ObjectBytes
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.materiality.contracts import shapes
from esgapi.materiality.flows import binding_155, iro_155, prompt_model_155
from esgapi.materiality.flows.iro_155 import IroAdapters
from esgapi.materiality.outputs.digest import digest
from esgapi.materiality.tests.flows.settings_store import file_config
from esgapi.materiality.tests.flows.support import (
    IRO_CODE,
    binding,
    octets,
    options,
    real_client,
    received2,
    reordered2,
    script_iro,
    sized,
)
from esgapi.runs import context, tasks
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
NOON_UTC = datetime(2025, 6, 30, 3, 0, tzinfo=UTC)
"""clock 의 기본 고정값 — 서울 2025-06-30 12:00(실제 날짜와 다른 값)."""
FILES = ["materiality-websearch.xlsx", "materiality-final-report.xlsx"]


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
    at(monkeypatch, NOON_UTC)
    original = LlmClient.call_tools

    def recorded(self: LlmClient, request: ToolCallRequest, execute: ToolExecutor) -> ToolLoopResult:
        made.tool_requests.append(request)
        return original(self, request, execute)

    monkeypatch.setattr(LlmClient, "call_tools", recorded)
    return made


def at(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    monkeypatch.setattr(binding_155, "clock", lambda: when)


def scripted(monkeypatch: pytest.MonkeyPatch, world: World) -> None:
    """실행기의 클라이언트가 openai 를 대본 심은 world.mock 으로 짓게 한다."""

    def make(name: str, **kwargs: Any) -> Any:
        if name == "openai":
            return world.mock
        return llm_adapters.make(name, **kwargs)

    monkeypatch.setattr(context, "build_client", partial(context.build_client, make=make))


def create(client: Client, body: Mapping[str, object]) -> Any:
    login(client)
    return client.post("/api/runs", data=body, content_type="application/json")


def new_run(client: Client, given: Mapping[str, object]) -> int:
    response = create(client, {"module": "materiality", "options": given})
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
    rows = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    (only,) = [row for row in rows if row.schema_version == "materiality.result@2"]  # 곁에 digest@1(IR3c)
    assert isinstance(only.body, dict)
    return cast("dict[str, Any]", only.body)


def step_data(world: World, run_id: int, name: str) -> dict[str, Any]:
    (step,) = [s for s in run_selectors.step_rows(company_id=world.company_a, run_id=run_id) if s.name == name]
    assert step.data is not None
    return step.data


def stored(world: World, run_id: int, *, step: str | None, name: str) -> bytes:
    (row,) = [
        f
        for f in run_selectors.run_files(company_id=world.company_a, run_id=run_id)
        if f.step == step and f.name == name
    ]
    got = world.storage.get(row.storage_key, max_bytes=row.size_bytes)
    assert isinstance(got, ObjectBytes)
    return got.data


def document_gets(world: World) -> list[str]:
    return [key for key in world.storage.get_calls if "/documents/" in key]


def done_run(client: Client, world: World, monkeypatch: pytest.MonkeyPatch, given: Mapping[str, Any]) -> int:
    scripted(monkeypatch, world)
    script_iro(world.mock, given["input"])
    run_id = new_run(client, given)
    execute(world, run_id)
    assert world.mock.pending == 0
    return run_id


def body(request: ProviderRequest) -> bytes:
    """요청 몸 바이트(openai 공급사가 SDK 에 넘기는 kwargs 의 JSON — test_iro_155.body 와 같은 셈)."""
    return json.dumps(OpenAIProvider().build_request(request), ensure_ascii=False, sort_keys=True).encode()


def dump(name: str, pair: Mapping[str, object]) -> None:
    """IR3A_DUMP 가 있으면 견준 두 쪽을 JSON 으로 쓴다(머리말)."""
    where = os.environ.get("IR3A_DUMP")
    if where:
        Path(where).mkdir(parents=True, exist_ok=True)
        (Path(where) / f"{name}.json").write_text(json.dumps(pair, ensure_ascii=False, indent=1), encoding="utf-8")


# ── 3-2-1 끝까지 ──


def test_post_runs_materiality_without_a_document_is_201_with_the_versions(client: Client, world: World) -> None:
    run_id = new_run(client, options())
    run = run_of(world, run_id)
    assert (run.module, run.flow_id, run.status, run.document_id) == (
        "materiality",
        "materiality.iro@155",
        "queued",
        None,
    )
    assert run.versions == {
        "engine": "colab_155",
        "flow": "materiality.iro@155",
        "promptIds": {
            "regulation": "materiality/regulation@1",
            "keywords": "materiality/keywords@1",
            "controversy": "materiality/controversy@1",
            "impact": "materiality/impact@1",
            "financial": "materiality/financial@1",
            "pathway": "materiality/pathway@1",
        },
        # IR4 ③: 적용 판 없음 = 기본 판의 열쇠(promptsSha256 은 저장 글 판만)
        "aiSetting": "기본 설정",
        "aiSettingId": None,
        "modelSettingsSha256": model_settings_sha256(defaults(file_config(), prompt_model_155.MODELS)),
    }
    steps = run_selectors.step_rows(company_id=world.company_a, run_id=run_id)
    assert [s.name for s in steps] == [
        "load",
        "regulation",
        "keywords",
        "controversy",
        "report",
        "part2_seed",
        "impact",
        "financial",
        "pathway",
        "report_iro",
    ]


def test_the_executor_runs_materiality_to_done_with_one_v2_result_and_two_workbooks(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = done_run(client, world, monkeypatch, options())
    run = run_of(world, run_id)
    assert (run.status, run.error_code, run.failed_step, run.attempts) == ("done", None, None, 1)
    found = result_body(world, run_id)
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE_V2].validate_python(found, strict=True)
    assert found["part2"]["status"] == "done"
    assert len(world.mock.calls) == 14

    response = client.get(f"/api/runs/{run_id}")
    assert response.status_code == 200
    out = response.json()
    assert (out["status"], out["documentId"]) == ("done", None)
    assert [(s["step"], s["status"]) for s in out["steps"]] == [(name, "done") for name in iro_155.FLOW.steps]
    assert out["resultShapes"] == ["materiality.result@2", "materiality.digest@1"]
    assert out["files"] == FILES
    for name in FILES:
        workbook = client.get(f"/api/runs/{run_id}/files/{name}")
        assert workbook.status_code == 200
        assert workbook.content[:4] == b"PK\x03\x04"
    assert document_gets(world) == []


# ── 3-2-2 요청에 실린 것 ──


def test_the_requests_carry_the_run_and_company_tags_and_web_search(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = done_run(client, world, monkeypatch, options())
    assert world.sink.records
    assert {r.run_id for r in world.sink.records} == {str(run_id)}
    assert {(r.tenant, r.module) for r in world.sink.records} == {(str(world.company_a), "materiality")}
    prompts = [r.prompt for r in world.tool_requests]
    searched = [r.prompt for r in world.tool_requests if any(isinstance(t, WebSearchTool) for t in r.tools)]
    assert (
        prompts[:5] == ["materiality/regulation@1"] * 2 + ["materiality/keywords@1"] + ["materiality/controversy@1"] * 2
    )
    assert {"materiality/regulation@1", "materiality/controversy@1"} <= set(searched)


@pytest.mark.parametrize(
    ("when", "end"),
    [
        (datetime(2025, 6, 30, 14, 59, 59, tzinfo=UTC), "2025-06-30"),
        (datetime(2025, 6, 30, 15, 0, 0, tzinfo=UTC), "2025-07-01"),
    ],
    ids=["before-seoul-midnight", "seoul-midnight"],
)
def test_the_window_ends_on_the_seoul_date_of_the_run(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, when: datetime, end: str
) -> None:
    at(monkeypatch, when)
    run_id = done_run(client, world, monkeypatch, options())
    assert step_data(world, run_id, "load")["window"] == {"start": "2025-01-01", "end": end}


# ── 3-2-3 만들기 거절 ──


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ({}, "옵션 input이(가) 없어요"),
        (options(today="2025-06-30"), "알 수 없는 옵션이에요: today"),
        (
            {"input": {**received2(), "schemaVersion": "materiality.input@2"}},
            "옵션 input.schemaVersion의 값이 맞지 않아요",
        ),
        ({"input": {**received2(), "dateRange": "최근 1년"}}, "옵션 input.dateRange의 값이 맞지 않아요"),
        ({"input": {**received2(), "dateRange": "2025-07-01~오늘까지"}}, "옵션 input.dateRange의 값이 맞지 않아요"),
    ],
    ids=["empty", "today", "schemaVersion", "dateRange-words", "dateRange-after-today"],
)
def test_options_that_do_not_fit_are_400_with_the_binding_sentence_and_no_row(
    client: Client, world: World, given: dict[str, Any], message: str
) -> None:
    response = create(client, {"module": "materiality", "options": given})
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
    # 끼움이 거절할 열쇠(today)를 품은 채 크기만 넘긴다 — 크기 문장이 끼움 문장보다 먼저다
    share = octets(options(today="2025-06-30")) - octets(options())
    given = {**sized(262_144 + over - share), "today": "2025-06-30"}
    assert octets(given) == 262_144 + over
    response = create(client, {"module": "materiality", "options": given})
    assert (response.status_code, response.json()["error"]["code"]) == (400, "INVALID_OPTIONS")
    assert response.json()["error"]["message"] == "옵션이 너무 크다(JSON 으로 262144바이트까지)"
    assert run_count(world) == 0


def test_options_of_20kib_are_over_the_default_16kib_and_still_accepted(client: Client, world: World) -> None:
    run_id = new_run(client, sized(20 * 1024))
    assert run_of(world, run_id).status == "queued"


# ── 3-2-4 문서를 주면 ──


def test_a_document_id_is_not_accepted(client: Client, world: World) -> None:
    key = f"companies/{world.company_a}/documents/ir3a/original"
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
    response = create(client, {"module": "materiality", "documentId": row.pk, "options": options()})
    assert (response.status_code, response.json()["error"]["code"]) == (422, "DOCUMENT_NOT_ACCEPTED")
    assert run_count(world) == 0


# ── 3-2-5 1부 단독은 끼우지 않음(처분 ⑧ 가) ──


def test_the_part1_flow_alone_is_not_runnable(client: Client, world: World) -> None:
    response = create(client, {"module": "materiality", "flowId": "materiality.colab@155", "options": options()})
    assert (response.status_code, response.json()["error"]["code"]) == (422, "FLOW_NOT_RUNNABLE")
    assert run_count(world) == 0


# ── 3-2-6 서버 그대로(★C) ──


def test_the_server_as_is_ends_the_run_without_calling_a_provider(client: Client, world: World) -> None:
    run_id = new_run(client, options())
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "setup_error", "regulation")
    assert world.mock.calls == []
    assert [r.prompt for r in world.tool_requests] == ["materiality/regulation@1"]  # 고리를 부르나 공급사를 짓다 멈춘다


# ── 3-2-7 ★B 실행기를 거친 요청 == run_flow 에 바로 넣은 요청 ──


def test_the_executor_sends_the_same_request_bodies_as_run_flow(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    reordered = reordered2()
    done_run(client, world, monkeypatch, {"input": reordered})
    through_runs = [body(r) for r in world.mock.calls]

    direct = MockProvider("openai")
    script_iro(direct, reordered)
    run_flow(
        iro_155.FLOW,
        # 끼움을 거치지 않고 손으로 지은 같은 입력(받은 dict 그대로·같은 today·tags·상한)
        iro_155.IroInputs(
            received=reordered,
            tags=Tags(tenant=str(world.company_a), module="materiality"),
            max_cost_usd=5.0,
            today=date(2025, 6, 30),
            **IRO_CODE,
        ),
        IroAdapters(llm=real_client(direct)),
    )
    straight = [body(r) for r in direct.calls]
    dump("exec", {"executor": [b.decode() for b in through_runs], "run_flow": [b.decode() for b in straight]})
    assert len(through_runs) == 14
    assert through_runs == straight


# ── 3-2-8 이어 돌기(계획 9절) ──


def once_failing(original: Callable[..., StepOutput]) -> Callable[..., StepOutput]:
    calls = {"n": 0}

    def report2(*args: Any) -> StepOutput:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("가상 실패 — 한 번")
        return original(*args)

    return report2


def test_resuming_after_report_iro_failed_ends_with_the_first_runs_part1_workbook(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = iro_155.PART2[iro_155.REPORT2]
    monkeypatch.setitem(iro_155.PART2, iro_155.REPORT2, once_failing(original))
    first = done_run(client, world, monkeypatch, options())
    run = run_of(world, first)
    assert (run.status, run.failed_step) == ("failed", "report_iro")
    part1_book = stored(world, first, step="report", name="materiality-websearch.xlsx")
    calls_before = len(world.mock.calls)
    window = step_data(world, first, "load")["window"]

    monkeypatch.setitem(iro_155.PART2, iro_155.REPORT2, original)
    at(monkeypatch, datetime(2025, 7, 1, 3, 0, tzinfo=UTC))  # 다음 날(서울 2025-07-01)
    gets_before = len(world.storage.get_calls)
    response = create(client, {"module": "materiality", "options": {}, "resumeFromRunId": first})
    assert response.status_code == 201, response.content.decode()
    resumed: int = response.json()["id"]
    execute(world, resumed)

    assert run_of(world, resumed).status == "done"
    assert len(world.mock.calls) == calls_before  # 새 실행의 공급사 호출 0
    steps = run_selectors.step_rows(company_id=world.company_a, run_id=resumed)
    assert [s.status for s in steps] == ["done"] * 10
    assert step_data(world, resumed, "load")["window"] == window  # 창 그대로(다음 날이어도)
    final_book = stored(world, resumed, step=None, name="materiality-websearch.xlsx")
    assert hashlib.sha256(final_book).hexdigest() == hashlib.sha256(part1_book).hexdigest()
    first_keys = {f.storage_key for f in run_selectors.run_files(company_id=world.company_a, run_id=first)}
    assert any(key in first_keys for key in world.storage.get_calls[gets_before:])  # 새 키는 앞 키에서 옮김

    # 같은 carried 로 report_iro 만 바로 돌린 것과 결과가 같다
    carried = {
        s.name: StepOutput(
            data=step_data(world, first, s.name),
            files=tuple(
                OutputFile(name=f.name, media_type=f.media_type, content=stored(world, first, step=s.name, name=f.name))
                for f in run_selectors.run_files(company_id=world.company_a, run_id=first)
                if f.step == s.name
            ),
        )
        for s in run_selectors.step_rows(company_id=world.company_a, run_id=first)
        if s.status == "done"
    }
    direct = run_flow(
        iro_155.FLOW,
        binding().inputs(options(), company_id=world.company_a),
        IroAdapters(llm=real_client(MockProvider("openai"))),
        start_at="report_iro",
        carried=carried,
    )
    straight, summary = direct.output.results
    assert summary == digest(straight)  # ★H 이어 돈 report_iro 도 요약을 낸다(IR3c)
    found = result_body(world, resumed)
    dump(
        "resume",
        {
            "resumed": found,
            "report_iro": straight,
            "part1_sha256": [hashlib.sha256(part1_book).hexdigest(), hashlib.sha256(final_book).hexdigest()],
        },
    )
    assert found == straight
    rows = run_selectors.run_results(company_id=world.company_a, run_id=resumed)
    assert [(row.schema_version, row.body) for row in rows] == [
        ("materiality.result@2", found),
        ("materiality.digest@1", digest(found)),
    ]
    listed = {row["id"]: row for row in client.get("/api/materiality/runs").json()["results"]}  # ★H 목록의 두 수
    assert (listed[resumed]["impactRows"], listed[resumed]["pathwayRows"]) == (
        digest(found)["impactRows"],
        digest(found)["pathwayRows"],
    )
    assert (listed[first]["status"], listed[first]["impactRows"], listed[first]["pathwayRows"]) == (
        "failed",
        None,
        None,
    )


# ── ★D 만들 때 읽힌 dateRange 를 돌 때 못 읽음(시계가 뒤로 — 「오늘」은 앞으로만 가 실제로는 닿지 않는 갈래) ──


def test_a_date_range_unreadable_at_run_time_fails_before_any_step(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    at(monkeypatch, datetime(2025, 7, 1, 3, 0, tzinfo=UTC))
    run_id = new_run(client, {"input": {**received2(), "dateRange": "2025-07-01~오늘까지"}})
    at(monkeypatch, NOON_UTC)  # 서울 2025-06-30 — 시작이 오늘 뒤
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "options_rejected", None)
    assert world.mock.calls == []
    assert [s.status for s in run_selectors.step_rows(company_id=world.company_a, run_id=run_id)] == ["pending"] * 10


# ── IRW6 S8~S10 단계 안 진행(done/total)·같은 실행 다시 넣기·이어 받은 실행(발주서 §3) ──
# controversy 의 둘째 토픽 호출을 갈아(colab_155.call_message — 1부 단계가 모듈 전역 이름으로 부른다) 공급사 앞에서
# 한 번 잠깐 오류(RunRetryLater)나 실패(RuntimeError)를 낸다. received2 = 토픽 둘·서브토픽 자리 셋.

from esgapi.core.flows.binding import RunRetryLater  # noqa: E402
from esgapi.materiality.flows import colab_155  # noqa: E402
from esgapi.materiality.tests.flows.support import (  # noqa: E402
    USAGE,
    controversy_answer_dated,
    keywords_answer,
    regulation_answer_dated,
    script_part2,
    topic_names,
)

COUNTS_DONE = {
    "regulation": (2, 2),
    "controversy": (2, 2),
    "impact": (3, 3),
    "financial": (3, 3),
    "pathway": (3, 3),
}
"""received2 의 끝난 실행: 1부 토픽 단계는 토픽 수, 2부 셋은 서브토픽 자리 수, 나머지 다섯은 (None, None)."""


def failing_second_controversy(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """controversy 둘째 토픽에서 한 번(공급사 앞) error 를 낸다. 그 뒤는 원래대로."""
    original = colab_155.call_message
    seen = {"controversy": 0, "raised": False}

    def call(llm: Any, message: colab_155.Message, inputs: Any, spent: float) -> colab_155.Called:
        if message.phase == "controversy":
            seen["controversy"] += 1
            if seen["controversy"] == 2 and not seen["raised"]:
                seen["raised"] = True
                raise error
        return original(llm, message, inputs, spent)

    monkeypatch.setattr(colab_155, "call_message", call)


def counts(client: Client, run_id: int) -> dict[str, tuple[int | None, int | None]]:
    out = client.get(f"/api/runs/{run_id}").json()
    return {s["step"]: (s["done"], s["total"]) for s in out["steps"]}


def direct_bodies(world: World, given: Mapping[str, Any]) -> list[bytes]:
    """같은 입력을 run_flow 에 바로 넣은 요청 몸 열(3-2-7 의 바로 돈 쪽과 같은 셈)."""
    direct = MockProvider("openai")
    script_iro(direct, given)
    run_flow(
        iro_155.FLOW,
        iro_155.IroInputs(
            received=dict(given),
            tags=Tags(tenant=str(world.company_a), module="materiality"),
            max_cost_usd=5.0,
            today=date(2025, 6, 30),
            **IRO_CODE,
        ),
        IroAdapters(llm=real_client(direct)),
    )
    return [body(r) for r in direct.calls]


def test_a_done_run_shows_done_over_total_for_the_counted_steps(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = done_run(client, world, monkeypatch, options())
    assert counts(client, run_id) == {name: COUNTS_DONE.get(name, (None, None)) for name in iro_155.FLOW.steps}


def test_a_requeued_attempt_resumes_controversy_without_repeating_calls(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    failing_second_controversy(monkeypatch, RunRetryLater("가상 잠깐 오류"))
    scripted(monkeypatch, world)
    script_iro(world.mock, received2())
    run_id = new_run(client, options())
    execute(world, run_id)

    assert run_of(world, run_id).status == "queued"
    (row,) = [s for s in run_selectors.step_rows(company_id=world.company_a, run_id=run_id) if s.name == "controversy"]
    assert (row.done, row.total) == (1, 2)
    assert row.partial is not None
    assert [a["topic"] for a in cast("list[dict[str, Any]]", row.partial["answers"])] == topic_names(received2())[:1]
    assert len(world.mock.calls) == 4  # 규제 둘 · 키워드 · 컨트로버시 하나

    execute(world, run_id)
    assert run_of(world, run_id).status == "done"
    assert world.mock.pending == 0
    assert [body(r) for r in world.mock.calls] == direct_bodies(world, received2())  # 되풀이 0
    assert counts(client, run_id)["controversy"] == (2, 2)


def test_a_run_resumed_from_a_failed_controversy_starts_that_step_over(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    failing_second_controversy(monkeypatch, RuntimeError("가상 실패 — 한 번"))
    scripted(monkeypatch, world)
    names = topic_names(received2())
    for name in names:
        world.mock.enqueue_text(regulation_answer_dated(name), USAGE, hosted_calls=1)
    world.mock.enqueue_text(keywords_answer(names), USAGE, hosted_calls=1)
    world.mock.enqueue_text(controversy_answer_dated(names[0]), USAGE, hosted_calls=1)
    first = new_run(client, options())
    execute(world, first)

    assert (run_of(world, first).status, run_of(world, first).failed_step) == ("failed", "controversy")
    (row,) = [s for s in run_selectors.step_rows(company_id=world.company_a, run_id=first) if s.name == "controversy"]
    assert (row.status, row.done, row.total) == ("failed", 1, 2)
    assert world.mock.pending == 0

    for name in names:
        world.mock.enqueue_text(controversy_answer_dated(name), USAGE, hosted_calls=1)
    script_part2(world.mock)
    calls_before = len(world.mock.calls)
    response = create(client, {"module": "materiality", "options": {}, "resumeFromRunId": first})
    assert response.status_code == 201, response.content.decode()
    resumed: int = response.json()["id"]
    execute(world, resumed)

    assert run_of(world, resumed).status == "done"
    assert world.mock.pending == 0
    # 이어 받은 실행은 실패 단계의 partial 을 옮기지 않는다(runs 의 지금 동작) — controversy 를 처음부터(공급사 2)
    assert len(world.mock.calls) - calls_before == len(names) + 9
    assert len(cast("list[object]", step_data(world, resumed, "controversy")["calls"])) == len(names)
    assert counts(client, resumed)["controversy"] == (2, 2)
