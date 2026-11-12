# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""중대성평가 IRO 결과 경로 GET /materiality/runs/{run_id}/result 를 진짜 DB 로 잰다(밴드 IR3b §3-2-1~3, 업무 층).

    3-2-1  문서 없이 만든 실행 → 실행기 끝(모의 14 호출) → 200 · 본문 = 결과 행의 @2 본문(strict) · resultShapes @2
    3-2-2  없는 id · 남의 회사 · 다른 모듈 실행(끝난 것·안 끝난 것) · done 인데 @2 결과 없음(@1 행만) → 404, 본문 같음
    3-2-3  queued · processing · failed(키 없는 서버 그대로 — failed·setup_error·regulation) → 409 RUN_NOT_DONE
★ 실행 만들기·실행기는 tests/flows/test_runs_materiality.py 의 도우미를 쓴다(공급사는 모의 — 실제 호출 0).
★ 실행·결과 행은 runs 의 selectors 로만 읽고, 심을 수 없는 갈래(processing·@1 행만)는 결과 action 이 읽는 selectors
  를 바꿔 끼운다(runs.models 를 import 하지 않는다 — 계약 나). 입력은 전부 지어낸 것이다.
"""

import dataclasses
from typing import Any

import pytest
from django.test import Client

from esgapi.dataverify.tests.flows import support as dataverify_support
from esgapi.materiality.contracts import shapes
from esgapi.materiality.service.actions import result as actions
from esgapi.materiality.tests.flows.support import options
from esgapi.materiality.tests.flows.test_runs_materiality import (
    World,
    create,
    done_run,
    execute,
    new_run,
    result_body,
    run_of,
)
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import login

pytestmark = pytest.mark.django_db


def result_of(client: Client, run_id: int) -> Any:
    return client.get(f"/api/materiality/runs/{run_id}/result")


def refused(response: Any) -> tuple[int, str, str]:
    error = response.json()["error"]
    return response.status_code, error["code"], error["message"]


NOT_FOUND = (404, "NOT_FOUND", "그런 실행이 없다")
NOT_DONE = (409, "RUN_NOT_DONE", "실행이 아직 끝나지 않았다")


def dataverify_run(client: Client) -> int:
    """같은 회사의 데이터 검증 실행(문서 없이 만들기만 — queued)."""
    response = create(client, {"module": "dataverify", "options": dataverify_support.options()})
    assert response.status_code == 201, response.content.decode()
    run_id: int = response.json()["id"]
    return run_id


def renamed(monkeypatch: pytest.MonkeyPatch, **changes: Any) -> None:
    """결과 action 이 읽는 실행을 고쳐 끼운다(업무 층에서 심을 수 없는 갈래 — DV1e 꼴)."""
    found = run_selectors.find_run

    def changed(*, company_id: int, run_id: int) -> run_selectors.Run | None:
        run = found(company_id=company_id, run_id=run_id)
        return None if run is None else dataclasses.replace(run, **changes)

    monkeypatch.setattr(actions.run_selectors, "find_run", changed)


# ── 3-2-1 끝까지 ──


def test_a_done_run_reads_its_result_in_the_result_shape(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = done_run(client, world, monkeypatch, options())
    response = result_of(client, run_id)
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    assert body == result_body(world, run_id)  # ★G 응답 본문 == 행 body
    shapes.RESULT_SHAPES["materiality.result@2"].validate_python(body, strict=True)
    assert next(iter(body)) == "schemaVersion"
    assert client.get(f"/api/runs/{run_id}").json()["resultShapes"] == ["materiality.result@2", "materiality.digest@1"]


# ── 3-2-2 404 ──


def test_no_run_another_company_and_another_module_are_the_same_404(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    mine = done_run(client, world, monkeypatch, options())
    missing = result_of(client, mine + 1000)
    assert refused(missing) == NOT_FOUND
    queued_other = dataverify_run(client)  # 다른 모듈, 안 끝난 것
    assert run_of(world, queued_other).status == "queued"
    assert refused(result_of(client, queued_other)) == NOT_FOUND
    other = Client()
    login(other, tenant_id="tenant-b")
    theirs = result_of(other, mine)
    assert refused(theirs) == NOT_FOUND
    assert theirs.content == missing.content  # 남의 회사 실행 = 없는 실행(본문 바이트 같음)
    assert result_of(client, mine).status_code == 200  # 분모: 제 회사로는 보인다


def test_a_done_run_of_another_module_is_404(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """다른 모듈의 끝난 실행(@2 행이 있어도) — 실행의 module 을 바꿔 끼운다(끝난 것만 module 검사에 닿는다)."""
    run_id = done_run(client, world, monkeypatch, options())
    renamed(monkeypatch, module="dataverify")
    assert refused(result_of(client, run_id)) == NOT_FOUND


def test_a_done_run_without_an_at_2_result_is_404(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """④ 가: 경로는 materiality.result@2 행만 읽는다 — @1 행만 있는 끝난 실행은 결과 없음."""
    run_id = done_run(client, world, monkeypatch, options())
    (row,) = [
        r
        for r in run_selectors.run_results(company_id=world.company_a, run_id=run_id)
        if r.schema_version == "materiality.result@2"
    ]
    old = dataclasses.replace(row, schema_version="materiality.result@1", body={**result_body(world, run_id)})

    def only_at_1(*, company_id: int, run_id: int) -> tuple[run_selectors.RunResult, ...]:
        return (old,)

    monkeypatch.setattr(actions.run_selectors, "run_results", only_at_1)
    assert refused(result_of(client, run_id)) == NOT_FOUND


# ── 3-2-3 409 ──


def test_queued_processing_and_failed_runs_are_409(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    queued = new_run(client, options())
    assert run_of(world, queued).status == "queued"
    assert refused(result_of(client, queued)) == NOT_DONE
    failed = new_run(client, options())
    execute(world, failed)  # 키 없는 서버 그대로 — failed·setup_error·regulation(IR3a ★C)
    run = run_of(world, failed)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "setup_error", "regulation")
    assert refused(result_of(client, failed)) == NOT_DONE
    renamed(monkeypatch, status="processing")
    assert refused(result_of(client, queued)) == NOT_DONE
