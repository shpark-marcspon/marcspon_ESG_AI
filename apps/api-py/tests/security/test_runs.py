"""흐름의 실행 넷(run_runs·run_steps·run_results·run_files — X1b-1)을 앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 앱 역할은 실행 넷을 지우거나 비우지 못한다(DELETE·TRUNCATE → 42501, 행은 그대로 — MARC-ENT-208), 결과·파일은
     고치지도 못한다(UPDATE → 42501 — MARC-ENT-210 (1)). 분모: 앱 역할로 넷 다 INSERT 가 되고(커밋돼 주인이 센다),
     실행·단계는 UPDATE 가 된다.
  ⓑ 크기 CHECK 가 앱 코드를 지나지 않는 길(주인 역할의 INSERT)에서도 큰 JSON 을 막는다(결과 본문 8MiB·options 16KiB —
     상한은 어림). 분모: 상한 안은 들어간다.
  ⓒ 경로의 회사 격리 — A 의 실행·출력 파일(주인 역할로 넣은 행 + 가짜 저장소의 바이트)을 B 의 세션으로 읽으면 404,
     B 의 목록에 0, 내려받기 감사 줄 0. 분모: A 의 세션으로는 200·바이트·목록 1·감사 줄 1(회사 A).
  ⓓ 남의 문서·실행 id 로 만들기 → 404, B 의 실행 행 0. 분모: B 의 제 문서로는 201(시험 안의 가짜 흐름·끼움을 등록부에
     바꿔 끼운다 — runs/service/actions/runs.py 의 REGISTRY·BINDINGS 틈).
  ⓔ 남의 실패한 실행 id 로 이어 돌기(resumeFromRunId — X1b-2b) → 404 NOT_FOUND, 두 회사의 실행·단계 행 앞 = 뒤,
     감사 줄 0. 분모: B 의 제 실패한 실행으로는 201.
  ⓕ 문서 없는 실행(ND1 — 가짜 흐름 probe.bare@1, 문서 칸 NULL)도 회사 격리 그대로: A 의 것을 B 로 읽으면 단건 404·
     목록 0·이어 돌기 404, 두 회사의 행 앞 = 뒤. 분모: A 로는 200·목록 1줄.
  ⓕ' B 가 A 의 문서 id 를 문서 없는 흐름에 넣으면 404(422 DOCUMENT_NOT_ACCEPTED 가 아니다 — 문서 검사가 먼저, 본문은
     없는 문서 id 의 404 와 같다), 행 0. 분모: B 의 제 문서로는 422 DOCUMENT_NOT_ACCEPTED.
  ⓖ 문서가 NULL 이면 실행의 같은 회사 외래 키(MATCH SIMPLE)는 비껴간다 — 하위 행의 같은 회사 외래 키는 그대로라 남의
     회사 단계 행은 23503. 분모: 같은 회사 단계 행은 들어간다.
  ⓗ Idempotency-Key(IK1)의 범위는 (회사, 사람)이다: 회사 A·B 가 같은 열쇠·같은 꼴 본문(각자 제 문서)으로 만들면 둘 다
     201·id 다름·각 회사 실행 행 +1, 같은 회사 다른 사람도 따로 +1. 분모: A 가 같은 열쇠로 다시 → 같은 id·행 그대로.
  ⓘ 앱 역할로 같은 (회사, 사람, 열쇠) 둘째 INSERT → 23505 run_runs_idempotency_uniq, 열쇠만 있고 sha 가 NULL →
     23514 run_runs_idempotency_pair_check. 분모: 열쇠 NULL 두 행은 들어간다.
  ⓙ launchKey(LK1)는 유일이 아니다: 앱 역할로 같은 (회사, 사람, launch_key) 두 행이 들어간다. 회사 A·B 가 같은
     launchKey 로 POST /runs(각자 제 문서) → 둘 다 201·각 회사 행 +1·두 행의 launch_key 가 같은 값. 분모: 대문자
     launchKey → 422·행 0.
  ⓚ 고른 구획 다시(retrySegments — RM1c ③)와 구획 목록(GET /runs/{run_id}/segments)의 회사 격리: B 가 A 의 done 실행
     id 를 fromRunId 에 넣으면 404 NOT_FOUND·두 회사의 행 그대로·감사 줄 0, B 가 제 실행에 A 실행의 구획 sha 를 섞으면
     422 RETRY_SEGMENTS_UNKNOWN·행 그대로, B 가 A 의 구획 목록을 읽으면 404·몸에 구획 열쇠 0. 분모: 같은 함수 안에서
     B 의 제 실행·제 열쇠로는 201, A 로는 목록 200·구획 셋.
  ⓑ 의 options 상한은 ND1 부터 RUN_OPTIONS_CEILING_OCTETS(2 × 256KiB + 64 — 감싼 꼴의 여유)다. 문서 흐름의 16KiB 는 앱
     층(실행 만들기)만 잠근다 — 업무 층 runs/tests/service/apis/test_runs.py 가 잰다.

Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다(분모를 센다).
무효 조건: 권한은 esg_app 역할로 잰 것이다. superuser 에게는 GRANT 가 걸리지 않는다. 주인 역할은 고치고 지울 수 있다.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction
from django.test import Client
from psycopg import sql

from esgapi.core.flows.binding import BindingRegistry, DocumentInput, RunContext
from esgapi.core.flows.registry import FlowRegistry, make_flow
from esgapi.core.flows.types import (
    Carried,
    FlowStep,
    StepContext,
    StepOutput,
    segment_key_fields,
    segment_key_sha256,
)
from esgapi.core.resources import queue as hooks
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.models import RUN_OPTIONS_CEILING_OCTETS, RunFileRow, RunResultRow, RunRow, RunStepRow
from esgapi.runs.service.actions import runs as actions
from esgapi.runs.service.apis import runs as run_apis
from esgapi.runs.tests.test_executor_segments import SEGMENTED, Script, key_at
from esgapi.runs.tests.test_executor_segments import Binding as SegmentBinding
from tests.security.conftest import count
from tests.security.test_documents import upload_as
from tests.support.http import customer_bearer, login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
TABLES: Final = ("run_runs", "run_steps", "run_results", "run_files")
MIB: Final = 1024 * 1024


def owner_document(owner: Owner, company_id: int, key: str = "a") -> int:
    row = owner.execute(
        "INSERT INTO core_documents (created_at, updated_at, company_id, uploaded_by, file_name, storage_key, "
        "size_bytes, status) VALUES (now(), now(), %s, '1', %s, %s, 1, 'uploaded') RETURNING id",
        [company_id, f"{key}.pdf", f"documents/{company_id}/{key}.pdf"],
    ).fetchone()
    assert row is not None
    return int(row[0])


def owner_run(owner: Owner, company_id: int, document_id: int, *, options: str = "{}") -> int:
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, %s, 'greenwash', 'greenwash.colab@E0', %s::jsonb, '{}', 'service', "
        "'queued', 0, 0, 7) "
        "RETURNING id",
        [company_id, document_id, options],
    ).fetchone()
    assert row is not None
    return int(row[0])


def owner_children(owner: Owner, company_id: int, run_id: int) -> None:
    owner.execute(
        "INSERT INTO run_steps (created_at, updated_at, company_id, run_id, name, position, status) "
        "VALUES (now(), now(), %s, %s, 'extract', 0, 'pending')",
        [company_id, run_id],
    )
    owner_result(owner, company_id, run_id, "{}")
    owner.execute(
        "INSERT INTO run_files (created_at, company_id, run_id, step, name, media_type, storage_key, size_bytes, "
        "sha256) "
        "VALUES (now(), %s, %s, NULL, 'r.xlsx', 'application/x', %s, 1, %s)",
        [company_id, run_id, f"runs/{company_id}/{run_id}/out/r.xlsx", "0" * 64],
    )


def owner_result(owner: Owner, company_id: int, run_id: int, body: str, position: int = 0) -> None:
    owner.execute(
        "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
        "VALUES (now(), %s, %s, %s, 'x.result@1', %s::jsonb)",
        [company_id, run_id, position, body],
    )


def denied(statement: str) -> str | None:
    """앱 역할로 문 하나를 보내고 그 SQLSTATE(된 것이면 None)."""
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(statement)
    except DatabaseError as error:
        return getattr(error.__cause__, "sqlstate", None)
    return None


# ── ⓐ 지울 수 없음 ──


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("verb", ["delete", "truncate"])
def test_app_role_cannot_remove_a_run_row(owner: Owner, companies: tuple[int, int], table: str, verb: str) -> None:
    a, _ = companies
    owner_children(owner, a, owner_run(owner, a, owner_document(owner, a)))
    before = {name: count(owner, name) for name in TABLES}
    assert before == dict.fromkeys(TABLES, 1)  # 분모: 넷 다 한 행
    statement = f"DELETE FROM {table}" if verb == "delete" else f"TRUNCATE {table} CASCADE"
    assert denied(statement) == "42501"  # insufficient_privilege
    assert {name: count(owner, name) for name in TABLES} == before  # 행은 그대로


@pytest.mark.parametrize(
    ("table", "assignment"),
    [("run_results", "position = 9"), ("run_files", "size_bytes = 9")],
    ids=["results", "files"],
)
def test_app_role_cannot_change_a_result_or_a_file(
    owner: Owner, companies: tuple[int, int], table: str, assignment: str
) -> None:
    a, _ = companies
    owner_children(owner, a, owner_run(owner, a, owner_document(owner, a)))
    assert denied(f"UPDATE {table} SET {assignment}") == "42501"
    column = assignment.split()[0]
    seen = owner.execute(sql.SQL("SELECT {} FROM {}").format(sql.Identifier(column), sql.Identifier(table))).fetchall()
    assert seen == [(0,) if table == "run_results" else (1,)]  # 행은 그대로


def test_app_role_appends_to_all_four_and_changes_runs_and_steps(owner: Owner, companies: tuple[int, int]) -> None:
    """분모: 앱 역할은 넷 다 덧붙일 수 있고(커밋돼 주인이 센다), 상태가 바뀌는 실행·단계는 고칠 수 있다."""
    a, _ = companies
    document_id = owner_document(owner, a)
    run = RunRow.for_company(a).create(
        company_id=a, document_id=document_id, module="greenwash", flow_id="greenwash.colab@E0", status="queued",
        created_by_user_id=7,
    )  # fmt: skip
    RunStepRow.for_company(a).create(company_id=a, run_id=run.pk, name="extract", position=0, status="pending")
    RunResultRow.for_company(a).create(company_id=a, run_id=run.pk, position=0, schema_version="x.result@1", body={})
    RunFileRow.for_company(a).create(
        company_id=a, run_id=run.pk, name="r.xlsx", media_type="m", storage_key="k", size_bytes=1, sha256="0" * 64
    )
    assert {name: count(owner, name) for name in TABLES} == dict.fromkeys(TABLES, 1)
    assert denied("UPDATE run_runs SET status = 'processing'") is None
    assert denied("UPDATE run_steps SET status = 'running'") is None
    assert owner.execute("SELECT status FROM run_runs").fetchall() == [("processing",)]
    assert owner.execute("SELECT status FROM run_steps").fetchall() == [("running",)]


# ── ⓑ 크기 CHECK(주인 역할의 INSERT — 앱 코드를 지나지 않는 길) ──


def jsonb_of_octets(owner: Owner, octets: int) -> str:
    """jsonb 의 글자(::text)가 정확히 octets 바이트인 객체 하나. 주인 연결이 그 길이를 다시 잰다(분모)."""
    base = '{"x": ""}'
    text = json.dumps({"x": "a" * (octets - len(base))})
    row = owner.execute("SELECT octet_length(%s::jsonb::text)", [text]).fetchone()
    assert row is not None and row[0] == octets
    return text


def test_a_result_body_over_the_limit_is_refused(owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = owner_run(owner, a, owner_document(owner, a))
    owner_result(owner, a, run_id, jsonb_of_octets(owner, 8 * MIB), position=0)  # 분모: 상한까지는 들어간다
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        owner_result(owner, a, run_id, jsonb_of_octets(owner, 8 * MIB + 1), position=1)
    assert caught.value.diag.constraint_name == "run_results_body_size_check"
    assert count(owner, "run_results") == 1


def test_run_options_over_the_db_ceiling_are_refused(owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    document_id = owner_document(owner, a)
    owner_run(owner, a, document_id, options=jsonb_of_octets(owner, RUN_OPTIONS_CEILING_OCTETS))  # 분모
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        owner_run(owner, a, document_id, options=jsonb_of_octets(owner, RUN_OPTIONS_CEILING_OCTETS + 1))
    assert caught.value.diag.constraint_name == "run_runs_options_size_check"
    assert count(owner, "run_runs") == 1


# ── ⓒⓓ 경로의 회사 격리(커밋 ③) ──


@dataclass(frozen=True)
class ProbeInputs:
    document: DocumentInput


@dataclass(frozen=True)
class ProbeAdapters:
    ctx: RunContext


def _probe_step(inputs: ProbeInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"results": []})


PROBE: Final = make_flow(
    module="probe",
    id="probe.one@1",
    input_shape="probe.document@1",
    inputs=ProbeInputs,
    adapters=ProbeAdapters,
    result_shapes=("probe.result@1",),
    output_files=(),
    steps=(FlowStep(name="only", run=_probe_step),),
)


class ProbeBinding:
    def check_options(self, options: Mapping[str, object]) -> None:
        return None

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> object:
        return ProbeInputs(document=document)

    def adapters(self, ctx: RunContext) -> object:
        return ProbeAdapters(ctx=ctx)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {}


def ignore(**_: Any) -> None:
    """큐 갈고리 자리: 쪽지를 버린다(이 층에 브로커가 없다 — 쪽지 꼴은 업무 층 runs/tests 가 잰다)."""


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    """문서 저장소 틈에 가짜를 꽂고, 실행 만들기의 등록부에 가짜 흐름·끼움을 단다. 큐 갈고리는 쌓기만 한다."""
    flows = FlowRegistry()
    flows.register(PROBE)
    flows.set_default("probe", PROBE.id)
    bindings = BindingRegistry()
    bindings.register(PROBE.id, ProbeBinding())
    monkeypatch.setattr(actions, "REGISTRY", flows)
    monkeypatch.setattr(actions, "BINDINGS", bindings)
    monkeypatch.setattr(hooks, "enqueue_run", ignore)
    return plug_storage(monkeypatch, FakeStorage())


# 회사 경로의 두 길(K2b): 옛 교환 쿠키(session)와 고객사 사용자의 access(bearer). test_tenant_paths 의 VIA 와 같다.
VIA: Final = ("session", "bearer")


def session_of(via: str, company_id: int, tenant: str, sub: str) -> Client:
    """그 회사의 고객사 사용자의 Client. bearer 는 비밀번호를 바꾼 사용자의 access 를 모든 요청의 머리에 싣는다."""
    if via == "session":
        client = Client()
        login(client, sub=sub, tenant_id=tenant)
        return client
    access = customer_bearer(Client(), company_id=company_id, subdomain=tenant)
    return Client(headers={"Authorization": f"Bearer {access}"})


def audit_lines(owner: Owner, action: str) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT company_id, target_id, target_label FROM core_audit_events WHERE action = %s ORDER BY id", [action]
    ).fetchall()


def a_run_with_a_file(owner: Owner, fake: FakeStorage, a: int) -> int:
    """A 의 실행 하나(단계 하나·결과 하나·출력 파일 r.xlsx — 주인 역할로)와 그 파일의 바이트(가짜 저장소)."""
    run_id = owner_run(owner, a, owner_document(owner, a))
    owner_children(owner, a, run_id)
    fake.put(f"runs/{a}/{run_id}/out/r.xlsx", b"A-ONLY")
    return run_id


@pytest.mark.parametrize("via", VIA)
def test_another_companys_run_and_file_are_not_found(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    """ⓒ A 의 실행·출력 파일을 B 로: 단건·내려받기 404, 감사 줄 0. 분모: A 로는 200·바이트·감사 줄 1(회사 A)."""
    a, b = companies
    run_id = a_run_with_a_file(owner, fake, a)
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    assert theirs.get(f"/api/runs/{run_id}").status_code == 404
    assert theirs.get(f"/api/runs/{run_id}/files/r.xlsx").status_code == 404
    assert audit_lines(owner, "download") == []

    mine = session_of(via, a, "tenant-a", "edk-user-1")
    seen = mine.get(f"/api/runs/{run_id}")
    assert (seen.status_code, seen.json()["files"], seen.json()["resultShapes"]) == (200, ["r.xlsx"], ["x.result@1"])
    downloaded = mine.get(f"/api/runs/{run_id}/files/r.xlsx")
    assert (downloaded.status_code, downloaded.content) == (200, b"A-ONLY")
    assert audit_lines(owner, "download") == [(a, run_id, "r.xlsx")]


@pytest.mark.parametrize("via", VIA)
def test_another_companys_runs_are_not_listed(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    """ⓒ B 의 목록에 A 의 실행이 0(거르기 셋을 줘도). 분모: A 로는 그 실행 하나."""
    a, b = companies
    run_id = a_run_with_a_file(owner, fake, a)
    document_id = owner.execute("SELECT document_id FROM run_runs WHERE id = %s", [run_id]).fetchone()
    assert document_id is not None
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    for query in ("", "?module=greenwash", "?status=queued", f"?documentId={document_id[0]}"):
        listed = theirs.get(f"/api/runs{query}").json()
        assert (listed["count"], listed["results"]) == (0, []), query
    mine = session_of(via, a, "tenant-a", "edk-user-1")
    assert [r["id"] for r in mine.get("/api/runs").json()["results"]] == [run_id]


@pytest.mark.parametrize("via", VIA)
def test_creating_a_run_on_another_companys_document_is_not_found(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    """ⓓ A 의 문서 id·실행 id 를 B 의 만들기 본문에 넣으면 404 이고 B 의 실행 행은 0. 분모: B 의 제 문서로는 201."""
    a, b = companies
    a_document = owner_document(owner, a)
    a_run = owner_run(owner, a, a_document)
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    assert count(owner, "run_runs") == 1  # A 의 실행 하나

    for document_id in (a_document, a_run):
        response = theirs.post(
            "/api/runs", data={"module": "probe", "documentId": document_id}, content_type="application/json"
        )
        assert response.status_code == 404, document_id
    assert (count(owner, "run_runs"), count(owner, "run_steps")) == (1, 0)
    assert audit_lines(owner, "run") == []

    b_document = upload_as(theirs, fake, owner)
    created = theirs.post(
        "/api/runs", data={"module": "probe", "documentId": b_document}, content_type="application/json"
    )
    assert created.status_code == 201, created.content.decode()
    rows = owner.execute("SELECT company_id, document_id, status FROM run_runs WHERE id = %s", [created.json()["id"]])
    assert rows.fetchall() == [(b, b_document, "queued")]
    assert count(owner, "run_steps") == 1
    assert audit_lines(owner, "run") == [(b, created.json()["id"], "a.pdf")]


def owner_failed_probe_run(owner: Owner, company_id: int, document_id: int) -> int:
    """그 회사의 실패한 probe.one@1 실행 하나(단계 only 가 failed — 주인 역할로)."""
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id, failed_step, error_code) "
        "VALUES (now(), now(), %s, %s, 'probe', %s, '{}', '{}', 'service', 'failed', 1, 0, 7, 'only', 'step_error') "
        "RETURNING id",
        [company_id, document_id, PROBE.id],
    ).fetchone()
    assert row is not None
    owner.execute(
        "INSERT INTO run_steps (created_at, updated_at, company_id, run_id, name, position, status) "
        "VALUES (now(), now(), %s, %s, 'only', 0, 'failed')",
        [company_id, row[0]],
    )
    return int(row[0])


def run_rows(owner: Owner) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    runs = owner.execute(
        "SELECT id, company_id, document_id, status, updated_at, finished_at, resumed_from_run_id FROM run_runs "
        "ORDER BY id"
    ).fetchall()
    steps = owner.execute(
        "SELECT id, company_id, run_id, name, status, data::text, partial::text, updated_at FROM run_steps ORDER BY id"
    ).fetchall()
    return runs, steps


@pytest.mark.parametrize("via", VIA)
def test_resuming_another_companys_failed_run_is_not_found(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    """ⓔ B 의 세션으로 A 의 실패한 실행 id 를 resumeFromRunId 에 넣으면 404 NOT_FOUND 이고 두 회사의 실행·단계 행은
    그대로, 감사 줄 0. 분모: 같은 함수 안에서 B 의 제 실패한 실행으로는 201(resumed_from = 그 실행)."""
    a, b = companies
    a_run = owner_failed_probe_run(owner, a, owner_document(owner, a))
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    b_document = upload_as(theirs, fake, owner)
    b_run = owner_failed_probe_run(owner, b, b_document)
    before = run_rows(owner)

    refused = theirs.post(
        "/api/runs",
        data={"module": "probe", "documentId": b_document, "resumeFromRunId": a_run},
        content_type="application/json",
    )
    assert (refused.status_code, refused.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert run_rows(owner) == before
    assert audit_lines(owner, "run") == []

    created = theirs.post(
        "/api/runs",
        data={"module": "probe", "documentId": b_document, "resumeFromRunId": b_run},
        content_type="application/json",
    )
    assert created.status_code == 201, created.content.decode()
    rows = owner.execute(
        "SELECT company_id, document_id, status, resumed_from_run_id FROM run_runs WHERE id = %s",
        [created.json()["id"]],
    )
    assert rows.fetchall() == [(b, b_document, "queued", b_run)]
    assert audit_lines(owner, "run") == [(b, created.json()["id"], "a.pdf")]


# ── ⓚ 고른 구획 다시·구획 목록(RM1c ③) ──


@pytest.fixture
def segmented_fake(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    """펼침 흐름(probe.segmented@1 — 업무 층 시험의 가짜 흐름)을 만들기·경로의 등록부에 단다. 쪽지는 버린다."""
    flows = FlowRegistry()
    flows.register(SEGMENTED)
    bindings = BindingRegistry()
    bindings.register(SEGMENTED.id, SegmentBinding(Script()))
    monkeypatch.setattr(actions, "REGISTRY", flows)
    monkeypatch.setattr(actions, "BINDINGS", bindings)
    monkeypatch.setattr(run_apis, "REGISTRY", flows)
    monkeypatch.setattr(hooks, "enqueue_run", ignore)
    return plug_storage(monkeypatch, FakeStorage())


def owner_done_segmented_run(owner: Owner, company_id: int, document_id: int, shift: str) -> tuple[int, list[str]]:
    """그 회사의 done probe.segmented@1 실행 하나(단계 셋 done·구획 셋 done — 주인 역할로)와 그 구획 sha(계획 차례).
    shift 는 열쇠의 span 을 회사마다 다르게 한다(남의 sha 를 섞는 시험)."""
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id, finished_at) "
        "VALUES (now(), now(), %s, %s, 'probe', %s, '{}', %s::jsonb, 'service', 'done', 1, 0, 7, now()) "
        "RETURNING id",
        [company_id, document_id, SEGMENTED.id, json.dumps({"flow": SEGMENTED.id})],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    for position, name in enumerate(SEGMENTED.steps):
        owner.execute(
            "INSERT INTO run_steps (created_at, updated_at, company_id, run_id, name, position, status, data) "
            "VALUES (now(), now(), %s, %s, %s, %s, 'done', %s::jsonb)",
            [company_id, run_id, name, position, json.dumps({"count": 3})],
        )
    shas: list[str] = []
    for position in range(3):
        key = key_at(position + 1, shift)
        sha = segment_key_sha256(key)
        shas.append(sha)
        owner.execute(
            "INSERT INTO run_segments (created_at, updated_at, company_id, run_id, step, position, kind, key, "
            "key_sha256, status, attempts, data, started_at, finished_at) "
            "VALUES (now(), now(), %s, %s, 'spread', %s, %s, %s::jsonb, %s, 'done', 1, %s::jsonb, now(), now())",
            [company_id, run_id, position, key.kind, json.dumps(segment_key_fields(key)), sha, '{"square": 1}'],
        )
    return run_id, shas


def segment_rows(owner: Owner) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT id, company_id, run_id, status, attempts, data::text, updated_at FROM run_segments ORDER BY id"
    ).fetchall()


def retry_body(document_id: int, from_run_id: int, keys: list[str]) -> dict[str, Any]:
    return {
        "module": "probe",
        "flowId": SEGMENTED.id,
        "documentId": document_id,
        "retrySegments": {"fromRunId": from_run_id, "step": "spread", "keys": keys},
    }


@pytest.mark.parametrize("via", VIA)
def test_retrying_another_companys_run_is_not_found(
    owner: Owner, companies: tuple[int, int], segmented_fake: FakeStorage, via: str
) -> None:
    """ⓚ B 가 A 의 done 실행 id 를 fromRunId 에 → 404·두 회사의 행 그대로·감사 줄 0. 분모: B 의 제 실행으로는 201."""
    a, b = companies
    a_run, a_shas = owner_done_segmented_run(owner, a, owner_document(owner, a), "A")
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    b_document = upload_as(theirs, segmented_fake, owner)
    b_run, b_shas = owner_done_segmented_run(owner, b, b_document, "B")
    before = (run_rows(owner), segment_rows(owner))

    for keys in (a_shas[:1], b_shas[:1]):  # 남의 실행 + 남의 sha · 남의 실행 + 제 sha 둘 다 404
        refused = theirs.post("/api/runs", data=retry_body(b_document, a_run, keys), content_type="application/json")
        assert (refused.status_code, refused.json()["error"]["code"]) == (404, "NOT_FOUND"), keys
    assert (run_rows(owner), segment_rows(owner)) == before
    assert audit_lines(owner, "run") == []

    created = theirs.post("/api/runs", data=retry_body(b_document, b_run, b_shas[:1]), content_type="application/json")
    assert created.status_code == 201, created.content.decode()
    new = created.json()["id"]
    rows = owner.execute("SELECT company_id, resumed_from_run_id FROM run_runs WHERE id = %s", [new]).fetchall()
    assert rows == [(b, b_run)]
    assert owner.execute("SELECT DISTINCT company_id FROM run_segments WHERE run_id = %s", [new]).fetchall() == [
        (b,)
    ]  # 새 실행의 구획 행은 요청 회사의 것


@pytest.mark.parametrize("via", VIA)
def test_mixing_another_runs_segment_sha_is_refused(
    owner: Owner, companies: tuple[int, int], segmented_fake: FakeStorage, via: str
) -> None:
    """ⓚ B 가 제 done 실행에 A 실행의 구획 sha 를 섞으면 422 RETRY_SEGMENTS_UNKNOWN·행 그대로. 분모: 제 sha 만은 201."""
    a, b = companies
    _a_run, a_shas = owner_done_segmented_run(owner, a, owner_document(owner, a), "A")
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    b_document = upload_as(theirs, segmented_fake, owner)
    b_run, b_shas = owner_done_segmented_run(owner, b, b_document, "B")
    assert not set(a_shas) & set(b_shas)  # 분모: 두 회사의 열쇠가 다르다
    before = (run_rows(owner), segment_rows(owner))

    for keys in (a_shas[:1], [b_shas[0], a_shas[1]]):
        refused = theirs.post("/api/runs", data=retry_body(b_document, b_run, keys), content_type="application/json")
        assert (refused.status_code, refused.json()["error"]["code"]) == (422, "RETRY_SEGMENTS_UNKNOWN"), keys
    assert (run_rows(owner), segment_rows(owner)) == before
    assert audit_lines(owner, "run") == []

    created = theirs.post("/api/runs", data=retry_body(b_document, b_run, b_shas[:2]), content_type="application/json")
    assert created.status_code == 201, created.content.decode()


@pytest.mark.parametrize("via", VIA)
def test_another_companys_segment_list_is_not_found(
    owner: Owner, companies: tuple[int, int], segmented_fake: FakeStorage, via: str
) -> None:
    """ⓚ B 가 A 실행의 구획 목록을 → 404·몸에 열쇠 0(펼침 아닌 단계도 404 가 먼저). 분모: A 로는 200·구획 셋."""
    a, b = companies
    a_run, a_shas = owner_done_segmented_run(owner, a, owner_document(owner, a), "A")
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    for query in ("?step=spread", "?step=spread&status=done", "?step=prepare"):
        answer = theirs.get(f"/api/runs/{a_run}/segments{query}")
        assert (answer.status_code, answer.json()["error"]["code"]) == (404, "NOT_FOUND"), query
        assert not any(sha in answer.content.decode() for sha in a_shas), query

    mine = session_of(via, a, "tenant-a", "edk-user-1")
    page = mine.get(f"/api/runs/{a_run}/segments?step=spread").json()
    assert (page["count"], [line["keySha256"] for line in page["results"]]) == (3, a_shas)
    assert "data" not in page["results"][0]


# ── ⓕⓕ'ⓖ 문서 없는 실행(ND1) ──


@dataclass(frozen=True)
class BareInputs:
    options: dict[str, object]
    company_id: int


class BareBinding:
    """문서 없는 끼움(DocumentlessBinding 꼴)."""

    def check_options(self, options: Mapping[str, object]) -> None:
        return None

    def inputs(self, options: Mapping[str, object], *, company_id: int) -> object:
        return BareInputs(options=dict(options), company_id=company_id)

    def adapters(self, ctx: RunContext) -> object:
        return ProbeAdapters(ctx=ctx)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {}


def _bare_step(inputs: BareInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"results": []})


BARE: Final = make_flow(
    module="probe",
    id="probe.bare@1",
    input_shape="probe.options@1",
    inputs=BareInputs,
    adapters=ProbeAdapters,
    result_shapes=("probe.result@1",),
    output_files=(),
    steps=(FlowStep(name="first", run=_bare_step), FlowStep(name="second", run=_bare_step)),
)


@pytest.fixture
def bare(monkeypatch: pytest.MonkeyPatch, fake: FakeStorage) -> FakeStorage:
    """fake 의 등록부에 문서 없는 흐름 probe.bare@1 을 더 단다(문서 흐름 probe.one@1 은 그대로)."""
    flows = FlowRegistry()
    flows.register(PROBE)
    flows.register(BARE)
    flows.set_default("probe", PROBE.id)
    bindings = BindingRegistry()
    bindings.register(PROBE.id, ProbeBinding())
    bindings.register_documentless(BARE.id, BareBinding())
    monkeypatch.setattr(actions, "REGISTRY", flows)
    monkeypatch.setattr(actions, "BINDINGS", bindings)
    return fake


def bare_body(**extra: Any) -> dict[str, Any]:
    return {"module": "probe", "flowId": BARE.id, "options": {"rows": [1, 2]}, **extra}


@pytest.mark.parametrize("via", VIA)
def test_a_documentless_run_stays_inside_its_company(
    owner: Owner, companies: tuple[int, int], bare: FakeStorage, via: str
) -> None:
    """ⓕ A 의 문서 없는 실행을 B 로: 단건 404·목록 0(거르기를 줘도)·이어 돌기 404, 두 회사의 행 앞 = 뒤.
    분모: A 로는 200(문서 칸 null)·목록 1줄."""
    a, b = companies
    mine = session_of(via, a, "tenant-a", "edk-user-1")
    made = mine.post("/api/runs", data=bare_body(), content_type="application/json")
    assert made.status_code == 201, made.content.decode()
    run_id = made.json()["id"]
    owner.execute("UPDATE run_runs SET status = 'failed', error_code = 'step_error' WHERE id = %s", [run_id])
    assert owner.execute("SELECT company_id, document_id FROM run_runs").fetchall() == [(a, None)]
    before = run_rows(owner)

    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    assert theirs.get(f"/api/runs/{run_id}").status_code == 404
    for query in ("", "?module=probe", "?status=failed"):
        listed = theirs.get(f"/api/runs{query}").json()
        assert (listed["count"], listed["results"]) == (0, []), query
    resumed = theirs.post("/api/runs", data=bare_body(resumeFromRunId=run_id), content_type="application/json")
    assert (resumed.status_code, resumed.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert run_rows(owner) == before

    seen = mine.get(f"/api/runs/{run_id}")
    assert (seen.status_code, seen.json()["documentId"]) == (200, None)
    listed = mine.get("/api/runs").json()["results"]
    assert [(r["id"], r["documentId"], r["documentName"]) for r in listed] == [(run_id, None, None)]


@pytest.mark.parametrize("via", VIA)
def test_another_companys_document_id_on_a_documentless_flow_is_not_found(
    owner: Owner, companies: tuple[int, int], bare: FakeStorage, via: str
) -> None:
    """ⓕ' B 가 A 의 문서 id 를 문서 없는 흐름에 넣으면 404(본문은 없는 문서 id 의 404 와 같다), 행 0·감사 0.
    분모: B 의 제 문서 id 로는 422 DOCUMENT_NOT_ACCEPTED(행 0) — 문서를 보고 나서야 그 갈래다."""
    a, b = companies
    a_document = owner_document(owner, a)
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    refused = theirs.post("/api/runs", data=bare_body(documentId=a_document), content_type="application/json")
    missing = theirs.post("/api/runs", data=bare_body(documentId=a_document + 1000), content_type="application/json")
    assert (refused.status_code, refused.json()) == (404, missing.json())
    assert refused.json()["error"]["code"] == "NOT_FOUND"
    assert (count(owner, "run_runs"), count(owner, "run_steps")) == (0, 0)
    assert audit_lines(owner, "run") == []

    b_document = upload_as(theirs, bare, owner)
    own = theirs.post("/api/runs", data=bare_body(documentId=b_document), content_type="application/json")
    assert (own.status_code, own.json()["error"]["code"]) == (422, "DOCUMENT_NOT_ACCEPTED")
    assert count(owner, "run_runs") == 0


def owner_documentless_run(owner: Owner, company_id: int) -> int:
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'probe', %s, '{}', '{}', 'service', 'queued', 0, 0, 7) RETURNING id",
        [company_id, BARE.id],
    ).fetchone()
    assert row is not None
    return int(row[0])


def test_a_null_document_does_not_open_the_child_rows_to_another_company(
    owner: Owner, companies: tuple[int, int]
) -> None:
    """ⓖ 문서가 NULL 인 A 의 실행에 B 의 단계 행은 23503(하위 행의 같은 회사 외래 키). 분모: A 의 단계 행은 들어간다."""
    a, b = companies
    run_id = owner_documentless_run(owner, a)
    step = (
        "INSERT INTO run_steps (created_at, updated_at, company_id, run_id, name, position, status) "
        "VALUES (now(), now(), %s, %s, %s, %s, 'pending')"
    )
    owner.execute(step, [a, run_id, "first", 0])  # 분모
    with pytest.raises(psycopg.errors.ForeignKeyViolation) as caught:
        owner.execute(step, [b, run_id, "second", 1])
    assert caught.value.sqlstate == "23503"
    assert caught.value.diag.constraint_name == "run_steps_run_id_same_company_fk"
    assert owner.execute("SELECT company_id, name FROM run_steps").fetchall() == [(a, "first")]


# ── ⓗⓘ Idempotency-Key(IK1 — MARC-ISSUE-225) ──

KEY: Final = "0b0e6c1e-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID


def keyed_post(client: Client, document_id: int) -> Any:
    return client.post(
        "/api/runs",
        data={"module": "probe", "documentId": document_id},
        content_type="application/json",
        headers={"Idempotency-Key": KEY},
    )


def runs_per_company(owner: Owner) -> dict[int, int]:
    return dict(owner.execute("SELECT company_id, count(*) FROM run_runs GROUP BY company_id").fetchall())


def test_the_same_key_in_two_companies_or_two_people_makes_separate_runs(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """ⓗ 같은 열쇠·같은 꼴 본문: A·B 각각 201·id 다름, 같은 회사 다른 사람도 따로. 분모: A 가 다시 → 같은 id."""
    a, b = companies
    mine = session_of("session", a, "tenant-a", "edk-user-1")
    theirs = session_of("session", b, "tenant-b", "edk-user-2")
    first_a = keyed_post(mine, owner_document(owner, a))
    first_b = keyed_post(theirs, owner_document(owner, b))
    assert (first_a.status_code, first_b.status_code) == (201, 201), first_b.content.decode()
    assert first_a.json()["id"] != first_b.json()["id"]
    assert runs_per_company(owner) == {a: 1, b: 1}

    again = keyed_post(mine, owner_document(owner, a, "a2"))  # 다른 문서 = 다른 본문 → 409, 행 그대로
    assert (again.status_code, again.json()["error"]["code"]) == (409, "IDEMPOTENCY_KEY_REUSED")
    document_a = owner.execute("SELECT document_id FROM run_runs WHERE id = %s", [first_a.json()["id"]]).fetchone()
    assert document_a is not None
    same = keyed_post(mine, int(document_a[0]))  # 분모: 같은 본문 → 같은 id
    assert (same.status_code, same.json()["id"]) == (201, first_a.json()["id"])
    assert runs_per_company(owner) == {a: 1, b: 1}

    colleague = session_of("session", a, "tenant-a", "edk-user-3")  # 같은 회사 다른 사람
    theirs_a = keyed_post(colleague, int(document_a[0]))
    assert theirs_a.status_code == 201
    assert theirs_a.json()["id"] != first_a.json()["id"]
    assert runs_per_company(owner) == {a: 2, b: 1}
    keys = owner.execute("SELECT company_id, created_by_user_id, idempotency_key FROM run_runs").fetchall()
    assert len(set(keys)) == 3 and {key for *_, key in keys} == {KEY}


def app_insert(company_id: int, key: str | None, sha: str | None) -> tuple[str | None, str | None]:
    """앱 역할로 run_runs 한 행(문서 없음 — ND1 꼴). 거절이면 (SQLSTATE, 제약 이름), 된 것이면 (None, None)."""
    try:
        with transaction.atomic():
            RunRow.for_company(company_id).create(
                company_id=company_id, module="probe", flow_id="probe.bare@1", status="queued",
                created_by_user_id=7, idempotency_key=key, idempotency_sha256=sha,
            )  # fmt: skip
    except DatabaseError as error:
        diag = getattr(error.__cause__, "diag", None)
        return getattr(error.__cause__, "sqlstate", None), getattr(diag, "constraint_name", None)
    return None, None


def test_the_app_role_cannot_write_a_second_row_for_the_same_key_or_a_key_without_its_sha(
    owner: Owner, companies: tuple[int, int]
) -> None:
    """ⓘ 앱 역할: 같은 (회사, 사람, 열쇠) 둘째 → 23505, 열쇠만(sha NULL) → 23514. 분모: 열쇠 NULL 두 행은 들어간다."""
    a, b = companies
    assert app_insert(a, None, None) == (None, None)
    assert app_insert(a, None, None) == (None, None)  # 분모: 열쇠 없는 행은 몇이든
    assert app_insert(a, KEY, "0" * 64) == (None, None)
    assert app_insert(a, KEY, "1" * 64) == ("23505", "run_runs_idempotency_uniq")
    assert app_insert(a, "9f8e7d6c-5b4a-4321-8fed-cba987654321", None) == ("23514", "run_runs_idempotency_pair_check")
    assert app_insert(b, KEY, "0" * 64) == (None, None)  # 분모: 다른 회사의 같은 열쇠는 들어간다
    assert runs_per_company(owner) == {a: 3, b: 1}


# ── ⓙ launchKey(LK1 — MARC-ISSUE-303 ①) ──

LAUNCH: Final = "1a2b3c4d-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID


def launch_post(client: Client, document_id: int, launch_key: str) -> Any:
    return client.post(
        "/api/runs",
        data={"module": "probe", "documentId": document_id, "launchKey": launch_key},
        content_type="application/json",
    )


def app_launch_insert(company_id: int, launch_key: str | None) -> tuple[str | None, str | None]:
    """앱 역할로 run_runs 한 행(문서 없음). 거절이면 (SQLSTATE, 제약 이름), 된 것이면 (None, None)."""
    try:
        with transaction.atomic():
            RunRow.for_company(company_id).create(
                company_id=company_id, module="probe", flow_id="probe.bare@1", status="queued",
                created_by_user_id=7, launch_key=launch_key,
            )  # fmt: skip
    except DatabaseError as error:
        diag = getattr(error.__cause__, "diag", None)
        return getattr(error.__cause__, "sqlstate", None), getattr(diag, "constraint_name", None)
    return None, None


def test_a_launch_key_is_not_unique_and_two_companies_keep_their_own_rows(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """ⓙ 앱 역할: 같은 (회사, 사람, launch_key) 두 행이 들어간다(묶음 = 실행 여럿). A·B 의 같은 launchKey 는 각자 201·
    각 회사 +1. 분모: 대문자 launchKey → 422·행 0."""
    a, b = companies
    assert app_launch_insert(a, LAUNCH) == (None, None)
    assert app_launch_insert(a, LAUNCH) == (None, None)  # 유일이 아니다
    assert runs_per_company(owner) == {a: 2}
    mine = session_of("session", a, "tenant-a", "edk-user-1")
    theirs = session_of("session", b, "tenant-b", "edk-user-2")
    refused = launch_post(theirs, owner_document(owner, b, "b0"), LAUNCH.upper())
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "VALIDATION_ERROR")
    assert runs_per_company(owner) == {a: 2}
    made_a = launch_post(mine, owner_document(owner, a), LAUNCH)
    made_b = launch_post(theirs, owner_document(owner, b), LAUNCH)
    assert (made_a.status_code, made_b.status_code) == (201, 201), made_b.content.decode()
    assert runs_per_company(owner) == {a: 3, b: 1}
    rows = owner.execute(
        "SELECT company_id, launch_key FROM run_runs WHERE id = ANY(%s) ORDER BY id",
        [[made_a.json()["id"], made_b.json()["id"]]],
    ).fetchall()
    assert rows == [(a, LAUNCH), (b, LAUNCH)]
