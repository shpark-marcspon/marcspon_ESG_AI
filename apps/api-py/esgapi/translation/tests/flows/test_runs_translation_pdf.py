# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""흐름 translation.pdf@158 을 진짜 DB 의 실행 만들기·실행기로 잰다(밴드 TRD2 F2·F3, 업무 층). 저장소·파서는 가짜(core
FakeParser — 지어낸 분해 판 2 문서), 공급사는 대본 심은 모의(test_runs_translation 의 world·scripted 그대로). 전역
REGISTRY·BINDINGS 의 끼움(apps.py 가 단 것)을 쓰고 파서를 만드는 함수만 갈아 끼운다.

    F3  POST /runs {flowId: translation.pdf@158} 201 · versions 의 input·adapter·parserLayout · 실행기 끝 → done ·
        결과 행 셋(result@1·digest@1·layout@1 strict) · 16KiB 넘는 옵션(용어집 500짝)이 받아짐(apps.py 의
        max_options_bytes — 빠지면 400) · 실패 쪽만 다시: 같은 PDF·범위는 done, 다른 쪽 범위는 retry_source_mismatch
    R1  (TRS3 G7) 워드 실행·다른 어댑터 판의 PDF 실행을 앞 실행으로 → retry_source_not_found·공급사 0 · 워드 흐름은 BASE
        그대로(워드 → 워드 done, PDF 앞 실행 → mismatch)
    F2  파서 503 busy → 실행기가 이 시도를 접고 다시 넣음(RunRetryLater) → 둘째 시도에 done
★ 문서는 전부 지어낸 것이다. 실행·결과 행은 runs 의 selectors 로 읽는다.
"""

import json
from typing import Any

import pytest
from django.apps import apps
from django.test import Client

from esgapi.core.flows.binding import BINDINGS
from esgapi.core.resources.ports.parser import ParseResult
from esgapi.core.tests.resource_fakes import FakeParser, FakeStorage
from esgapi.runs import context, tasks
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.translation.contracts.layout_shapes import LAYOUT_SHAPE, LAYOUT_SHAPES
from esgapi.translation.contracts.shapes import RESULT_SHAPE
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.flows import pdf_158 as pdf
from esgapi.translation.tests.engines.colab_158.support import ok
from esgapi.translation.tests.flows.pdf_support import ONE_PAGE_EN, PDF, PDF_SHA, document, failed, parsed
from esgapi.translation.tests.flows.support import SIMPLE_EN, options
from esgapi.translation.tests.flows.test_binding_158 import synthetic_glossary
from esgapi.translation.tests.flows.test_runs_translation import (
    NO_ISSUES,
    SETTINGS,
    World,
    create,
    execute,
    run_of,
    scripted,
)
from esgapi.translation.tests.flows.test_runs_translation import document as stored
from esgapi.translation.tools.pdf_tags import ADAPTER_VERSION
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    """test_runs_translation 의 world 와 같은 짜임(가짜 저장소·실행기 설정·호출 기록)."""
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)
    made = World(storage, *companies)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "monotonic", lambda: 0.0)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: 240)
    monkeypatch.setattr(context, "call_sink", lambda: made.sink)
    return made


class Parsers:
    """부를 때마다 차례로 결과를 내는 가짜 파서 짓개(끝은 되풀이). layouts 는 받은 분해 판."""

    def __init__(self, *results: ParseResult) -> None:
        self.results = list(results)
        self.layouts: list[int] = []

    def __call__(self) -> FakeParser:
        result = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        made = FakeParser({PDF_SHA: result})
        real = made.parse

        def parse(data: bytes, *, file_name: str, layout: int = 1) -> ParseResult:
            self.layouts.append(layout)
            return real(data, file_name=file_name, layout=layout)

        made.parse = parse  # type: ignore[method-assign]
        return made


def plugged(monkeypatch: pytest.MonkeyPatch, world: World, *results: ParseResult) -> Parsers:
    scripted(monkeypatch, world)
    binding = BINDINGS.get(pdf.FLOW_ID)
    monkeypatch.setattr(binding, "mock", lambda: False)
    parsers = Parsers(*(results or (parsed(),)))
    monkeypatch.setattr(binding, "parser", parsers)
    return parsers


def new_pdf_run(client: Client, world: World, given: dict[str, Any]) -> Any:
    login(client)
    body = {"module": "translation", "flowId": pdf.FLOW_ID, "documentId": stored(world, world.company_a, PDF, "v.pdf")}
    return client.post("/api/runs", data={**body, "options": given}, content_type="application/json")


def created(client: Client, world: World, given: dict[str, Any]) -> int:
    response = new_pdf_run(client, world, given)
    assert response.status_code == 201, response.content.decode()
    run_id: int = response.json()["id"]
    return run_id


def bodies(world: World, run_id: int) -> dict[str, dict[str, Any]]:
    rows = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    return {r.schema_version: r.body for r in rows}  # pyright: ignore[reportReturnType]


def test_post_runs_with_the_pdf_flow_runs_to_done_with_three_results(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    parsers = plugged(monkeypatch, world)
    run_id = created(client, world, options())
    run = run_of(world, run_id)
    assert (run.flow_id, run.versions["input"], run.versions["adapter"], run.versions["parserLayout"]) == (
        pdf.FLOW_ID,
        "pdf",
        ADAPTER_VERSION,
        2,
    )
    world.mock.enqueue(ok(ONE_PAGE_EN)).enqueue(NO_ISSUES)
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.error_code, run.attempts) == ("done", None, 1)
    found = bodies(world, run_id)
    assert sorted(found) == ["translation.digest@1", LAYOUT_SHAPE, RESULT_SHAPE]
    LAYOUT_SHAPES[LAYOUT_SHAPE].validate_python(found[LAYOUT_SHAPE], strict=True)
    assert found[LAYOUT_SHAPE]["variants"][0]["units"][0]["level"] == "block"
    assert parsers.layouts == [2] and world.mock.pending == 0


def test_a_busy_parser_defers_the_attempt_and_the_next_one_is_done(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    parsers = plugged(monkeypatch, world, failed("unavailable", "busy", 503), parsed())
    run_id = created(client, world, options())
    execute(world, run_id)
    first = run_of(world, run_id)
    assert (first.status, first.error_code, len(world.retries)) == ("queued", None, 1)
    world.mock.enqueue(ok(ONE_PAGE_EN)).enqueue(NO_ISSUES)
    execute(world, run_id)
    assert (run_of(world, run_id).status, parsers.layouts) == ("done", [2, 2])


def test_options_over_sixteen_kib_are_accepted(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    plugged(monkeypatch, world)
    given = options(glossary={"base": synthetic_glossary(250), "final": synthetic_glossary(250)})
    assert len(json.dumps(given, ensure_ascii=False).encode()) > 16 * 1024
    assert new_pdf_run(client, world, given).status_code == 201


def two_pages_done(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> int:
    plugged(monkeypatch, world, parsed(document(pages=2)))
    reply = "[BLOCK 1]\nWater stewardship\n\nThe virtual site cut its water use by 2 percent."
    world.mock.enqueue(ok(ONE_PAGE_EN)).enqueue(ok(reply))
    run_id = created(client, world, options())
    execute(world, run_id)
    assert run_of(world, run_id).status == "done" and world.mock.pending == 0
    return run_id


def test_retry_of_the_same_pdf_and_range_is_done(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    first = two_pages_done(client, world, monkeypatch)
    world.mock.enqueue(ok(ONE_PAGE_EN.replace("12 percent", "twelve percent"))).enqueue(NO_ISSUES)
    run_id = created(client, world, options(retry={"fromRunId": first, "pages": [1]}))
    execute(world, run_id)
    result = bodies(world, run_id)[RESULT_SHAPE]
    assert result["status"] == "done"
    assert result["settings"]["retry"] == {"fromRunId": first, "pages": [1], "skippedPages": []}
    assert "twelve percent" in result["variants"][0]["translatedText"]


def test_retry_with_another_page_range_is_a_mismatch(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = two_pages_done(client, world, monkeypatch)
    before = len(world.mock.calls)
    given = options(pages={"start": 1, "end": 1}, retry={"fromRunId": first, "pages": [1]})
    run_id = created(client, world, given)
    execute(world, run_id)
    result = bodies(world, run_id)[RESULT_SHAPE]
    assert (result["status"], result["rejection"]["kind"]) == ("rejected", "retry_source_mismatch")
    assert len(world.mock.calls) == before  # 거절된 다시 하기는 공급사 0


# ── R1 실패 쪽만 다시의 흐름·어댑터 판 거름(밴드 TRS3 G7 — PDF 끼움만, 워드 끼움은 BASE 그대로) ──


def word_done(client: Client, world: World) -> int:
    """워드 흐름(기본 흐름)의 끝난 실행 하나 — 같은 회사, 지어낸 글 문서."""
    world.mock.enqueue(ok(SIMPLE_EN)).enqueue(NO_ISSUES)
    login(client)
    response = create(client, "translation", stored(world, world.company_a), options())
    assert response.status_code == 201, response.content.decode()
    run_id: int = response.json()["id"]
    execute(world, run_id)
    assert (run_of(world, run_id).status, run_of(world, run_id).flow_id) == ("done", colab.FLOW_ID)
    return run_id


def test_a_word_run_is_not_a_retry_source_for_the_pdf_flow(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugged(monkeypatch, world)
    word = word_done(client, world)
    before = len(world.mock.calls)
    run_id = created(client, world, options(retry={"fromRunId": word, "pages": [1]}))
    execute(world, run_id)
    result = bodies(world, run_id)[RESULT_SHAPE]
    assert (result["status"], result["rejection"]["kind"]) == ("rejected", "retry_source_not_found")
    assert len(world.mock.calls) == before  # 공급사 호출 0


def test_a_pdf_run_of_another_adapter_version_is_not_a_retry_source(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """같은 PDF·같은 범위여도 versions.adapter 가 다른 판이면 찾지 못한다(지도가 달라졌을 수 있다)."""
    first = two_pages_done(client, world, monkeypatch)
    rows = apps.get_model("runs", "RunRow").for_company(world.company_a)  # pyright: ignore[reportAttributeAccessIssue]
    row = rows.get(pk=first)
    rows.filter(pk=first).update(versions={**row.versions, "adapter": "pdf_tags@0"})
    before = len(world.mock.calls)
    run_id = created(client, world, options(retry={"fromRunId": first, "pages": [1]}))
    execute(world, run_id)
    result = bodies(world, run_id)[RESULT_SHAPE]
    assert (result["status"], result["rejection"]["kind"]) == ("rejected", "retry_source_not_found")
    assert len(world.mock.calls) == before


def test_the_word_flow_keeps_its_base_retry_reading(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """워드 끼움은 거름 인자가 없다(BASE 동작): 워드 → 워드 done, PDF 앞 실행은 찾아지고 원문 sha 가 달라 mismatch."""
    pdf_first = two_pages_done(client, world, monkeypatch)
    word = word_done(client, world)
    world.mock.enqueue(ok(SIMPLE_EN)).enqueue(NO_ISSUES)
    again = create(
        client, "translation", stored(world, world.company_a), options(retry={"fromRunId": word, "pages": [1]})
    )
    assert again.status_code == 201, again.content.decode()
    execute(world, again.json()["id"])
    assert bodies(world, again.json()["id"])[RESULT_SHAPE]["status"] == "done"
    given = options(retry={"fromRunId": pdf_first, "pages": [1]})
    crossed = create(client, "translation", stored(world, world.company_a), given)
    execute(world, crossed.json()["id"])
    result = bodies(world, crossed.json()["id"])[RESULT_SHAPE]
    assert (result["status"], result["rejection"]["kind"]) == ("rejected", "retry_source_mismatch")
