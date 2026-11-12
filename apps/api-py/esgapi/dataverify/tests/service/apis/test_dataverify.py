# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""데이터 검증 결과 경로 GET /dataverify/runs/{run_id}/result 를 진짜 DB 로 잰다(밴드 DV1e §3-2-1~3, 업무 층).

    3-2-1  문서 없이 만든 실행 → 실행기 끝(모의) → 200 · 본문 = 결과 행의 @2 본문(strict) · resultShapes @2
    3-2-2  없는 id · 남의 회사 · 그린워싱 실행 · done 인데 @2 결과 없음(@1 행만) → 404 NOT_FOUND, 본문 같음
    3-2-3  queued · processing · failed(키 없는 서버 그대로 — failed·setup_error·plan) → 409 RUN_NOT_DONE
★ 실행 만들기·실행기는 tests/flows/test_runs_dataverify.py 의 도우미를 쓴다(공급사는 모의 — 실제 호출 0).
★ 실행·결과 행은 runs 의 selectors 로만 읽고, 심을 수 없는 갈래(processing·@1 행만)는 결과 action 이 읽는 selectors
  를 바꿔 끼운다(runs.models 를 import 하지 않는다 — 계약 나). 입력은 전부 지어낸 것이다.
"""

import dataclasses
from typing import Any

import pytest
from django.test import Client

from esgapi.core.models import DocumentRow
from esgapi.dataverify.contracts import shapes
from esgapi.dataverify.service.actions import result as actions
from esgapi.dataverify.tests.flows.support import options
from esgapi.dataverify.tests.flows.test_runs_dataverify import (
    World,
    create,
    done_run,
    new_run,
    result_body,
    run_of,
    server_as_is,
)
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import login

pytestmark = pytest.mark.django_db


def result_of(client: Client, run_id: int) -> Any:
    return client.get(f"/api/dataverify/runs/{run_id}/result")


def refused(response: Any) -> tuple[int, str, str]:
    error = response.json()["error"]
    return response.status_code, error["code"], error["message"]


NOT_FOUND = (404, "NOT_FOUND", "그런 실행이 없다")
NOT_DONE = (409, "RUN_NOT_DONE", "실행이 아직 끝나지 않았다")


def greenwash_run(client: Client, world: World) -> int:
    """같은 회사의 그린워싱 실행(만들기만 — queued)."""
    key = f"companies/{world.company_a}/documents/dv1e-g/original"
    etag = world.storage.put(key, b"%PDF-1.7 synthetic")
    row = DocumentRow.for_company(world.company_a).create(
        company_id=world.company_a,
        uploaded_by="1",
        file_name="g.pdf",
        storage_key=key,
        size_bytes=18,
        etag=etag,
        status="uploaded",
    )
    body = {
        "module": "greenwash",
        "documentId": row.pk,
        "options": {"parts": {"ceo": [1], "company": [], "climate": []}},
    }
    response = create(client, body)
    assert response.status_code == 201, response.content.decode()
    run_id: int = response.json()["id"]
    return run_id


# ── 3-2-1 끝까지 ──


def test_a_done_run_reads_its_result_in_the_result_shape(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = done_run(client, world, monkeypatch, options())
    response = result_of(client, run_id)
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    assert body == result_body(world, run_id)
    shapes.RESULT_SHAPES["dataverify.result@2"].validate_python(body, strict=True)
    assert next(iter(body)) == "schemaVersion"
    assert client.get(f"/api/runs/{run_id}").json()["resultShapes"] == ["dataverify.result@2", "dataverify.digest@1"]


# ── 3-2-2 404 ──


def test_no_run_another_company_and_another_module_are_the_same_404(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    mine = done_run(client, world, monkeypatch, options())
    missing = result_of(client, mine + 1000)
    assert refused(missing) == NOT_FOUND
    assert refused(result_of(client, greenwash_run(client, world))) == NOT_FOUND
    other = Client()
    login(other, tenant_id="tenant-b")
    theirs = result_of(other, mine)
    assert refused(theirs) == NOT_FOUND
    assert theirs.content == missing.content  # 남의 회사 실행 = 없는 실행(본문 바이트 같음)
    assert result_of(client, mine).status_code == 200  # 분모: 제 회사로는 보인다


def test_a_done_run_without_an_at_2_result_is_404(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Q6 가: 경로는 dataverify.result@2 행만 읽는다 — @1 행만 있는 끝난 실행(개발 DB 의 옛 행)은 결과 없음."""
    run_id = done_run(client, world, monkeypatch, options())
    row, _digest = run_selectors.run_results(company_id=world.company_a, run_id=run_id)  # 둘째는 요약 digest@1(DV1g)
    old = dataclasses.replace(row, schema_version="dataverify.result@1", body={**result_body(world, run_id)})

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
    failed = server_as_is(client, world)  # 키 없는 서버 그대로 — failed·setup_error·plan(DV1d ★C)
    run = run_of(world, failed)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "setup_error", "plan")
    assert refused(result_of(client, failed)) == NOT_DONE

    found = run_selectors.find_run

    def processing(*, company_id: int, run_id: int) -> run_selectors.Run | None:
        run = found(company_id=company_id, run_id=run_id)
        return None if run is None else dataclasses.replace(run, status="processing")

    monkeypatch.setattr(actions.run_selectors, "find_run", processing)
    assert refused(result_of(client, queued)) == NOT_DONE
