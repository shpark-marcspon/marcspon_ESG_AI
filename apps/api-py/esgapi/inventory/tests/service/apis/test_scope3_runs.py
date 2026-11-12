# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 코랩 흐름의 경로 둘(밴드 S3K1 ③ — service/apis/scope3_runs.py)을 진짜 DB 로 잰다. 업무 층.

    양식   GET /inventory/scope3/template — 두 역할 200 · 바이트 sha256 = 저장소 파일 · 머리 셋(xlsx·첨부 RFC 6266·
           nosniff) · 배포에 없으면 503 UNAVAILABLE
    결과   GET /inventory/scope3/runs/{id}/result — 두 역할 200(본문 = 결과 행, 계약 꼴 strict) · rejected 갈래 셋
           (표지뿐·xlsx 아님·깨진 zip — 실행은 done, 본문 status rejected) · 남의 회사·없음 404 · 안 끝남 409 ·
           실패 409 · 끝났는데 결과 없음·다른 꼴 결과뿐 404 · B 의 끝난·안 끝난 실행 id 로 A 는 없는 id 와 같은 404
    인증   세션 없이 401 · 틀린 Bearer 444
실행은 test_binding_157_end_to_end 의 짜임 그대로(실제 /documents 길 + POST /runs + 실행기 — 모의 openai, 지어낸
계수 책).
운영 관리자의 작업 회사는 포트를 회사 A 로 바꿔 끼운다 — 진짜 고르기(하나·둘·없음·비활성) × 이 경로는 보안 층
tests/security/test_operator_company.py ⑱·④ 가 잰다.
"""

import contextlib
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.apps import apps
from django.test import Client

from esgapi.inventory.contracts.shapes import RESULT_SHAPES
from esgapi.inventory.flows.binding_157 import FileMissing
from esgapi.inventory.service.utils import scope3_files
from esgapi.inventory.tests.engines.scope3.colab_157.support import sheet, workbook, xlsx_bytes
from esgapi.inventory.tests.flows.test_binding_157_end_to_end import (
    RetryAsked,
    World,
    body_of,
    execute,
    operator,
    post_run,
    upload,
    work_company,
    world,
)
from esgapi.runs import tasks
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import login

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (
    world,
    work_company,
)  # 끝까지 시험의 고정물을 이 모듈에서도 이름으로 찾게(pytest 는 모듈의 이름을 본다)

TEMPLATE_URL = "/api/inventory/scope3/template"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PACKAGED_SHA256 = "c51abfd6e023424b3194892afc2878b8a101ea355ce7c301874296301bbec42e"
"""data/scope3/scope3-template-v2.2.xlsx(data/README.md 의 표 — test_binding_157 의 SHA256 과 같은 값)."""


def result_url(run_id: int) -> str:
    return f"/api/inventory/scope3/runs/{run_id}/result"


def done_run(client: Client, world: World, content: bytes | None = None) -> int:
    """고객사 사용자가 올리고 만들고 실행기가 끝까지 돌린 Scope 3 실행."""
    login(client)
    document_id = upload(client, world) if content is None else upload(client, world, content)
    made = post_run(client, body_of(document_id, {"reportYear": 2025}))
    assert made.status_code == 201, made.content.decode()
    run_id: int = made.json()["id"]
    execute(world, run_id)
    return run_id


def runs_model(name: str) -> Any:
    return apps.get_model("runs", name)


def done_row(company_id: int, created_by: int, schema_versions: tuple[str, ...]) -> int:
    """심은 done 실행 행 — 실행기로는 만들 수 없는 꼴(끝났는데 코랩 결과가 없다). 결과 행은 그 꼴 이름으로."""
    at = datetime(2026, 10, 1, tzinfo=UTC)
    made = (
        runs_model("RunRow")
        .for_company(company_id)
        .create(
            company_id=company_id,
            module="inventory.scope3",
            flow_id="scope3.llm-first@1",
            options={},
            versions={},
            status="done",
            created_by_user_id=created_by,
            started_at=at,
            finished_at=at + timedelta(seconds=30),
        )
    )
    for position, schema_version in enumerate(schema_versions):
        runs_model("RunResultRow").for_company(company_id).create(
            company_id=company_id,
            run_id=made.pk,
            position=position,
            schema_version=schema_version,
            body={"schemaVersion": schema_version, "가상": "본문"},
        )
    return int(made.pk)


def stored(world: World, run_id: int) -> Any:
    (only,) = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    return only.body


# ── 양식 ──


def test_both_roles_download_the_packaged_template_with_three_headers(
    client: Client, world: World, work_company: None
) -> None:
    login(client)
    mine = client.get(TEMPLATE_URL)
    assert mine.status_code == 200, mine.content.decode()
    assert hashlib.sha256(mine.content).hexdigest() == PACKAGED_SHA256
    assert mine["Content-Type"] == XLSX
    assert mine["Content-Disposition"] == (
        "attachment; filename*=utf-8''Scope3_%ED%85%9C%ED%94%8C%EB%A6%BF_%EC%88%98%EC%A0%95%EB%B3%B8_v2.2.xlsx"
    )
    assert mine["X-Content-Type-Options"] == "nosniff"
    theirs = Client().get(TEMPLATE_URL, **operator())
    assert (theirs.status_code, theirs.content) == (200, mine.content)


def test_a_template_missing_from_the_deployment_is_503(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_read = scope3_files.PackagedXlsx.read

    def read(self: scope3_files.PackagedXlsx) -> bytes | FileMissing:
        return FileMissing(self.name) if self.name == scope3_files.TEMPLATE.name else real_read(self)

    monkeypatch.setattr(scope3_files.PackagedXlsx, "read", read)
    login(client)
    missing = client.get(TEMPLATE_URL)
    assert (missing.status_code, missing.json()["error"]["code"]) == (503, "UNAVAILABLE")


# ── 결과 ──


def test_both_roles_read_a_done_result_in_the_contract_shape(client: Client, world: World, work_company: None) -> None:
    run_id = done_run(client, world)
    mine = client.get(result_url(run_id))
    assert mine.status_code == 200, mine.content.decode()
    assert mine.json() == stored(world, run_id)
    assert mine.json()["status"] == "done"
    RESULT_SHAPES["scope3.colab.result@1"].validate_python(mine.json(), strict=True)
    theirs = Client().get(result_url(run_id), **operator())
    assert (theirs.status_code, theirs.json()) == (200, mine.json())


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (xlsx_bytes(workbook(sheet("표지", {1: ["가상"]}))), "legacy_template"),
        (b"%PDF-1.4 not a workbook", "reader_problem"),
        (b"PK\x03\x04 broken zip", "reader_problem"),
    ],
    ids=["cover-only", "not-xlsx", "broken-zip"],
)
def test_a_rejected_template_is_a_done_run_with_a_rejected_result(
    client: Client, world: World, content: bytes, reason: str
) -> None:
    run_id = done_run(client, world, content)
    run = run_selectors.find_run(company_id=world.company_a, run_id=run_id)
    assert run is not None and (run.status, run.error_code) == ("done", None)
    shown = client.get(result_url(run_id))
    assert shown.status_code == 200, shown.content.decode()
    assert (shown.json()["status"], shown.json()["rejected"]["reason"]) == ("rejected", reason)
    assert shown.json() == stored(world, run_id)
    RESULT_SHAPES["scope3.colab.result@1"].validate_python(shown.json(), strict=True)
    assert world.mock.texts == []  # 거절 갈래는 공급사에 닿지 않는다


def test_another_companys_view_and_a_missing_run_are_404(client: Client, world: World) -> None:
    """다른 모듈의 실행 id 404 는 보안 층 test_tenant_paths 의 scope3_run_paths(심은 데이터 검증 실행 — 끝난 것·안 끝난
    것)가 잰다."""
    run_id = done_run(client, world)
    other = Client()
    login(other, sub="b-user", tenant_id="tenant-b")
    assert other.get(result_url(run_id)).status_code == 404
    login(client)
    missing = client.get(result_url(run_id + 1000))
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert client.get(result_url(run_id)).status_code == 200  # 분모


def test_a_run_not_done_is_409(client: Client, world: World) -> None:
    login(client)
    made = post_run(client, body_of(upload(client, world), {"reportYear": 2025}))
    waiting = client.get(result_url(made.json()["id"]))
    assert (waiting.status_code, waiting.json()["error"]["code"]) == (409, "RUN_NOT_DONE")


def test_a_failed_run_is_409_not_404(client: Client, world: World) -> None:
    """실패한 실행은 있는 실행이다 — 없음(404)이 아니라 안 끝남(409). 계수 책이 깨져 실제로 실패시킨다."""
    world.book = b"PK\x03\x04 not a zip"
    login(client)
    run_id = post_run(client, body_of(upload(client, world), {"reportYear": 2025})).json()["id"]
    execute(world, run_id)
    run = run_selectors.find_run(company_id=world.company_a, run_id=run_id)
    assert run is not None and run.status == "failed"  # 먼저: 정말 실패한 실행이다
    failed = client.get(result_url(run_id))
    assert (failed.status_code, failed.json()["error"]["code"]) == (409, "RUN_NOT_DONE")


@pytest.mark.parametrize(
    "schema_versions",
    [(), ("scope3.llm-first.result@2",)],
    ids=["no-result-row", "another-shape-only"],
)
def test_a_done_run_without_a_colab_result_is_404(
    client: Client, world: World, schema_versions: tuple[str, ...]
) -> None:
    """끝났는데 scope3.colab.result@1 이 없는 실행(llm-first 결과 행만 있는 옛 실행 등)은 보여 줄 결과가 없다."""
    created_by = int(login(client)["user"]["id"])
    run_id = done_row(world.company_a, created_by, schema_versions)
    run = run_selectors.find_run(company_id=world.company_a, run_id=run_id)
    assert run is not None and (run.module, run.status) == ("inventory.scope3", "done")
    assert len(run_selectors.run_results(company_id=world.company_a, run_id=run_id)) == len(schema_versions)
    shown = client.get(result_url(run_id))
    assert (shown.status_code, shown.json()["error"]["code"]) == (404, "NOT_FOUND")


def test_a_run_of_company_b_read_as_a_is_the_same_404_as_a_missing_id(client: Client, world: World) -> None:
    """B 의 끝난 Scope 3 실행이 정말 있음을 먼저 재고(행의 회사·B 가 읽는 200 — 없는 행으로는 이 시험이 뜻이 없다),
    A 가 그 id 로 읽으면 없는 id 와 바이트까지 같은 404 다(존재 누설 0)."""
    theirs = Client()
    login(theirs, sub="b-user", tenant_id="tenant-b")
    made = post_run(theirs, body_of(upload(theirs, world), {"reportYear": 2025}))
    assert made.status_code == 201, made.content.decode()
    run_id: int = made.json()["id"]
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(world, company_id=str(world.company_b), run_id=str(run_id))
    row = runs_model("RunRow").unscoped.values("company_id", "module", "status").get(pk=run_id)
    assert row == {"company_id": world.company_b, "module": "inventory.scope3", "status": "done"}
    assert theirs.get(result_url(run_id)).status_code == 200

    login(client)
    hidden = client.get(result_url(run_id))
    missing = client.get(result_url(run_id + 1000))
    assert (hidden.status_code, missing.status_code) == (404, 404)
    assert hidden.content == missing.content


def test_a_queued_run_of_company_b_read_as_a_is_the_same_404_as_a_missing_id(client: Client, world: World) -> None:
    """안 끝난 B 의 실행도 A 에게는 없는 실행이다 — 결과 읽기 조건이 막아 주는 끝난 실행과 달리 여기서는 실행 읽기의
    회사 조건 하나가 막는다. 그 조건이 빠지면 409 로 갈려 남의 회사 실행이 있다는 것이 샌다. 끝난 실행은 위 시험."""
    theirs = Client()
    login(theirs, sub="b-user", tenant_id="tenant-b")
    made = post_run(theirs, body_of(upload(theirs, world), {"reportYear": 2025}))
    assert made.status_code == 201, made.content.decode()
    run_id: int = made.json()["id"]
    row = runs_model("RunRow").unscoped.values("company_id", "module", "status").get(pk=run_id)
    assert row == {"company_id": world.company_b, "module": "inventory.scope3", "status": "queued"}
    assert theirs.get(result_url(run_id)).status_code == 409  # 분모: 주인에게는 안 끝남

    login(client)
    hidden = client.get(result_url(run_id))
    missing = client.get(result_url(run_id + 1000))
    assert (hidden.status_code, missing.status_code) == (404, 404)
    assert hidden.content == missing.content


def test_no_session_is_401_and_a_bad_bearer_is_444(world: World) -> None:
    for url in (TEMPLATE_URL, result_url(1)):
        assert Client().get(url).status_code == 401
        assert Client().get(url, HTTP_AUTHORIZATION="Bearer not-a-token").status_code == 444
