"""운영 관리자 실행 기록(AU1b-2 — GET /run-logs·/run-logs/metrics)의 회사 경계를 앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 고객사 사용자 Bearer 는 두 경로 다 403 이고 응답에 줄·수치 0(분모: 운영 관리자의 같은 요청은 200 — 목록은 줄 ≥1,
     지표는 runs ≥1)
  ⓑ companyId=B 로 고른 운영 관리자에게 A 의 실행 0, R_B 의 토큰은 B 의 LLM 줄 값뿐(A 의 줄이 run_id=R_B 로 적혀 있어도
     — 양성 대조: B 의 줄은 실린다). 분모: 같은 함수 안에서 companyId=A 로 R_A 1
  ⓒ companyId=B 의 지표 runs 는 B 의 실행만(R_A 를 안 셈). 분모: 같은 함수 안에서 companyId=A 로 runs ≥1
  (401 은 tests/security/test_tenant_paths.py 의 test_without_a_session_it_is_401 매개 둘이 잰다)

함수: test_a_customer_bearer_is_refused_on_both_paths(ⓐ) · test_choosing_b_shows_no_run_or_llm_line_of_a(ⓑ) ·
test_metrics_for_b_do_not_count_the_runs_of_a(ⓒ).
AD4D(GET /run-logs/{run_id}, MARC-TICK-231 의 9f 허락):
  ⓖ B 를 고르면 A 의 실행 id 로 404 RUN_NOT_FOUND — 상태·몸이 없는 id 의 404 와 바이트까지 같다(분모: A 를 고르면 200)
  ⓖ' B 꼬리표 LLM 줄이 run_id = A 실행·step = A 단계 이름이어도 A 상세의 단계 토큰·합계에 0
     (분모: A 꼬리표 줄은 든다)
  ⓗ 고객사 Bearer 는 403 이고 몸에 실행·단계 0(분모: 운영 관리자 200)
함수: test_choosing_b_gets_404_on_a_run_of_a_byte_for_byte_like_a_missing_id(ⓖ) ·
test_a_b_tagged_llm_line_on_a_run_and_step_of_a_adds_nothing_to_its_detail(ⓖ') ·
test_a_customer_bearer_gets_no_run_detail(ⓗ).
RF1(GET /run-logs/{run_id}/files/{name}, MARC-TICK-241 의 9f 허락):
  ⓘ B 를 고르면 A 실행의 출력 파일 이름으로 404 RUN_NOT_FOUND — 상태·몸이 없는 실행 id 의 404 와 바이트까지 같고
     바이트 0·감사 0(분모: 같은 함수에서 A 를 고르면 200·바이트·감사 한 줄)
  ⓙ 고객사 Bearer 는 403 FORBIDDEN 이고 몸에 바이트 0·감사 0(분모: 운영 관리자 200)
함수: test_choosing_b_gets_404_on_a_file_of_a_run_of_a_like_a_missing_id(ⓘ) ·
test_a_customer_bearer_gets_no_run_file(ⓙ). 저장소는 plug_storage + FakeStorage(바이트는 지어낸 것).
LK1(같이 시작 묶음 칸, MARC-TICK-259 의 73 허락):
  ⓚ 주인 역할로 A 에 실행 둘·B 에 하나를 같은 launch_key·같은 created_by_user_id 로 심으면 companyId=B 의 목록·상세 줄은
     launchSize 1·launchIndex 1·launchFirstRunId = B 의 id 이고 응답 몸에 A 의 id 0(분모: companyId=A 는 2·1/2·2/2·첫
     id = A 의 앞 것)
함수: test_a_launch_of_a_does_not_count_into_b(ⓚ).
Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다(행을 심고 분모를 센다).
★ 뒤 밴드는 함수를 더하기만 한다(이 파일의 기존 함수의 단언을 바꾸지 않는다).
무효 조건: 실행은 주인 역할이 now() 로 심는다 — 지표의 「이번 달」(서버 시계의 KST 그달)과 DB 의 now() 가 달 경계를
사이에 두고 갈리면(KST 1일 00:00 바로 앞뒤) ⓐ·ⓒ 의 분모가 0 이 될 수 있다(그 순간만).
"""

import io
from typing import Any

import psycopg
import pytest
from django.test import Client
from openpyxl import load_workbook

from esgapi.core.tests.resource_fakes import FakeStorage
from tests.security.test_audit import customer_access, operator_access
from tests.security.test_greenwash import owner_done_run
from tests.security.test_runs import owner_document, owner_run
from tests.support.http import bearer
from tests.support.patches import plug_storage

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]


def owner_llm_line(owner: Owner, company_id: int, run_id: int, input_tokens: int) -> None:
    """주인 역할이 LLM 호출 기록 한 줄을 그 실행 id 의 꼬리표로 넣는다(앱 코드를 지나지 않는 길)."""
    owner.execute(
        "INSERT INTO core_llm_call_logs (company_id, module, ts, call_id, attempt, prompt_id, prompt_version, "
        "template_hash, request_hash, input_tokens, cost_usd, duration_ms, result_kind, warnings, has_error_status, "
        "has_previous_error_status, run_id, created_at) "
        "VALUES (%s, 'greenwash', now(), 'c', 1, 'p', 1, 't', 'r', %s, 0.5, 1.0, 'success', '[]'::jsonb, false, "
        "false, %s, now())",
        [company_id, input_tokens, run_id],
    )


def run_logs(client: Client, access: str, company_id: int) -> Any:
    return client.get(f"/api/run-logs?companyId={company_id}&limit=100", **bearer(access))


def run_metrics(client: Client, access: str, company_id: int) -> Any:
    return client.get(f"/api/run-logs/metrics?companyId={company_id}", **bearer(access))


def test_a_customer_bearer_is_refused_on_both_paths(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓐ 두 경로 다 403 FORBIDDEN, 몸에 줄·수치 0 — 분모: 운영 관리자의 같은 요청은 200 이고 줄·수치가 있다."""
    a, _ = companies
    owner_run(owner, a, owner_document(owner, a))
    access = customer_access(client, a)
    for response in (run_logs(client, access, a), run_metrics(client, access, a)):
        assert (response.status_code, response.json()["error"]["code"]) == (403, "FORBIDDEN")
        assert {"results", "count", "runs", "tokens", "costUsd"} & set(response.json()) == set()
    operator = operator_access(Client())
    seen = run_logs(Client(), operator, a)
    assert seen.status_code == 200
    assert len(seen.json()["results"]) >= 1
    counted = run_metrics(Client(), operator, a)
    assert counted.status_code == 200
    assert counted.json()["runs"] >= 1


def test_choosing_b_shows_no_run_or_llm_line_of_a(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓑ companyId=B 는 R_B 만이고 R_B 의 토큰은 B 의 줄 값뿐 — A 의 줄이 run_id=R_B 로 적혀 있어도 안 든다.
    양성 대조: B 의 줄(7)은 실린다. 분모: companyId=A 로 R_A 1."""
    a, b = companies
    run_a = owner_run(owner, a, owner_document(owner, a, "a"))
    run_b = owner_run(owner, b, owner_document(owner, b, "b"))
    owner_llm_line(owner, a, run_b, 1000)  # A 의 줄이 B 의 실행 id 꼬리표를 달았다
    owner_llm_line(owner, b, run_b, 7)
    access = operator_access(client)
    in_b = run_logs(client, access, b)
    assert in_b.status_code == 200
    assert [(row["id"], row["tokens"]) for row in in_b.json()["results"]] == [(run_b, 7)]
    assert run_a not in {row["id"] for row in in_b.json()["results"]}
    in_a = run_logs(client, access, a)
    assert in_a.status_code == 200
    assert [row["id"] for row in in_a.json()["results"]] == [run_a]  # 분모: A 로 고르면 A 의 실행 1
    assert in_a.json()["count"] == 1


def test_metrics_for_b_do_not_count_the_runs_of_a(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓒ companyId=B 의 runs 는 B 의 실행만(R_A 를 안 셈). 분모: companyId=A 로 runs ≥1."""
    a, b = companies
    owner_run(owner, a, owner_document(owner, a, "a"))
    owner_run(owner, a, owner_document(owner, a, "a2"))
    owner_run(owner, b, owner_document(owner, b, "b"))
    access = operator_access(client)
    of_b = run_metrics(client, access, b)
    assert of_b.status_code == 200
    assert of_b.json()["runs"] == 1
    of_a = run_metrics(client, access, a)
    assert of_a.status_code == 200
    assert of_a.json()["runs"] == 2  # 분모: A 로 고르면 A 의 실행 둘(≥1)


# ── AD4S(검토 칸·review 거르기 · 내보내기) — 더하기만 ──────────────────────────
# ⓕ(M2) 회사 A 의 검토 행(confirmed)이 run_id = R_B(B 의 그린워싱 done 실행 + 결과 dryRun null, B 검토 행 없음)를
#    가리킨다(greenwash_reviews.run_id 는 외래 키가 아니다). companyId=B 로 고르면 review=confirmed 0줄·R_B 는 pending·
#    review=pending 에 R_B. 분모: 같은 함수 안에서 B 에 confirmed 행을 심으면 R_B 는 confirmed.


def owner_review(owner: Owner, company_id: int, run_id: int, state: str) -> None:
    """주인 역할이 그린워싱 검토 행 하나를 넣는다(confirmed 면 확정 시각·사람 둘 다 — CHECK)."""
    confirmed = state == "confirmed"
    owner.execute(
        "INSERT INTO greenwash_reviews (created_at, updated_at, company_id, run_id, state, confirmed_at, "
        "confirmed_by_user_id) VALUES (now(), now(), %s, %s, %s, CASE WHEN %s THEN now() END, "
        "CASE WHEN %s THEN 1 END)",
        [company_id, run_id, state, confirmed, confirmed],
    )


def reviewed_logs(client: Client, access: str, company_id: int, review: str | None = None) -> Any:
    query = "" if review is None else f"&review={review}"
    response = client.get(f"/api/run-logs?companyId={company_id}&limit=100{query}", **bearer(access))
    assert response.status_code == 200, response.content.decode()
    return response.json()["results"]


def test_a_review_row_of_a_does_not_reach_the_runs_of_b(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """ⓕ A 의 confirmed 행이 run_id=R_B — B 로 고르면 confirmed 0·R_B pending.
    분모: B 에 confirmed 를 심으면 R_B confirmed."""
    a, b = companies
    run_b = owner_done_run(owner, b)
    owner_review(owner, a, run_b, "confirmed")  # 교차 행
    access = operator_access(client)
    assert [(row["id"], row["review"]) for row in reviewed_logs(client, access, b)] == [(run_b, "pending")]
    assert reviewed_logs(client, access, b, "confirmed") == []
    assert [row["id"] for row in reviewed_logs(client, access, b, "pending")] == [run_b]
    owner_review(owner, b, run_b, "confirmed")  # 분모
    assert [(row["id"], row["review"]) for row in reviewed_logs(client, access, b)] == [(run_b, "confirmed")]
    assert [row["id"] for row in reviewed_logs(client, access, b, "confirmed")] == [run_b]


# ⓓ 고객사 Bearer 로 GET /run-logs/export 는 403 이고 몸에 엑셀·줄 0(분모: 운영 관리자의 같은 요청은 200 xlsx).
# ⓔ companyId=B 로 고른 내보내기의 셀 글(openpyxl 로 연 값 — xlsx 는 zip 이라 바이트 grep 은 늘 0)에 A 의 문서 이름 0.
#    분모: 같은 함수 안에서 companyId=A 로 고르면 그 이름이 셀에 있다. Cache-Control no-store 도 여기서 단언한다.

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def export_of(client: Client, access: str, company_id: int) -> Any:
    return client.get(f"/api/run-logs/export?companyId={company_id}", **bearer(access))


def cell_texts(content: bytes) -> set[str]:
    book = load_workbook(io.BytesIO(content))
    return {str(cell.value) for sheet in book.worksheets for row in sheet.iter_rows() for cell in row if cell.value}


def test_a_customer_bearer_gets_no_export(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓓ 403 FORBIDDEN, 엑셀 0 — 분모: 운영 관리자의 같은 요청은 200 xlsx 이고 줄이 있다."""
    a, _ = companies
    owner_run(owner, a, owner_document(owner, a, "ad4s-d"))
    access = customer_access(client, a)
    refused = export_of(client, access, a)
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "FORBIDDEN")
    assert refused["Content-Type"] != XLSX and refused.get("Content-Disposition") is None
    operator = operator_access(Client())
    seen = export_of(Client(), operator, a)
    assert (seen.status_code, seen["Content-Type"]) == (200, XLSX)
    assert "ad4s-d.pdf" in cell_texts(seen.content)


def test_the_export_for_b_holds_no_name_of_a(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓔ B 를 고르면 셀에 A 의 문서 이름 0 · B 의 이름은 있음. 분모: A 를 고르면 A 의 이름이 있다."""
    a, b = companies
    owner_run(owner, a, owner_document(owner, a, "ad4s-only-in-a"))
    owner_run(owner, b, owner_document(owner, b, "ad4s-only-in-b"))
    access = operator_access(client)
    of_b = export_of(client, access, b)
    assert of_b.status_code == 200
    assert of_b["Cache-Control"] == "no-store"
    texts_b = cell_texts(of_b.content)
    assert "ad4s-only-in-a.pdf" not in texts_b
    assert "ad4s-only-in-b.pdf" in texts_b
    of_a = export_of(client, access, a)
    assert of_a.status_code == 200
    assert "ad4s-only-in-a.pdf" in cell_texts(of_a.content)  # 분모


# ── AD4D: 실행 상세 GET /run-logs/{run_id} ──


def detail_of(client: Client, access: str, run_id: int, company_id: int) -> Any:
    return client.get(f"/api/run-logs/{run_id}?companyId={company_id}", **bearer(access))


def owner_step(owner: Owner, company_id: int, run_id: int, name: str, position: int) -> None:
    owner.execute(
        "INSERT INTO run_steps (created_at, updated_at, company_id, run_id, name, position, status) "
        "VALUES (now(), now(), %s, %s, %s, %s, 'done')",
        [company_id, run_id, name, position],
    )


def owner_step_line(owner: Owner, company_id: int, run_id: int, step: str, input_tokens: int) -> None:
    """주인 역할이 단계 칸이 든 LLM 줄 하나를 넣는다(꼬리표 = company_id)."""
    owner.execute(
        "INSERT INTO core_llm_call_logs (company_id, module, ts, call_id, attempt, prompt_id, prompt_version, "
        "template_hash, request_hash, input_tokens, cost_usd, duration_ms, result_kind, warnings, has_error_status, "
        "has_previous_error_status, run_id, step, created_at) "
        "VALUES (%s, 'greenwash', now(), 'c', 1, 'p', 1, 't', 'r', %s, 0.5, 1.0, 'success', '[]'::jsonb, false, "
        "false, %s, %s, now())",
        [company_id, input_tokens, run_id, step],
    )


def test_choosing_b_gets_404_on_a_run_of_a_byte_for_byte_like_a_missing_id(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """ⓖ B 로 고른 운영 관리자에게 A 의 실행 id 는 404 이고, 상태·몸이 없는 id 의 404 와 같다. 분모: A 로 고르면 200."""
    a, b = companies
    run_a = owner_run(owner, a, owner_document(owner, a, "ad4d-g"))
    owner_step(owner, a, run_a, "extract", 0)
    access = operator_access(client)
    foreign = detail_of(client, access, run_a, b)
    missing = detail_of(client, access, 9_000_000_000_000_000_000, b)
    assert (foreign.status_code, foreign.json()["error"]["code"]) == (404, "RUN_NOT_FOUND")
    assert (foreign.status_code, foreign.content) == (missing.status_code, missing.content)
    assert b"ad4d-g" not in foreign.content and b"extract" not in foreign.content
    seen = detail_of(client, access, run_a, a)
    assert seen.status_code == 200  # 분모: 같은 함수로 A 를 고르면 보인다
    assert (seen.json()["id"], seen.json()["documentName"], [s["name"] for s in seen.json()["steps"]]) == (
        run_a,
        "ad4d-g.pdf",
        ["extract"],
    )


def test_a_b_tagged_llm_line_on_a_run_and_step_of_a_adds_nothing_to_its_detail(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """ⓖ' B 꼬리표 줄(run_id = A 실행, step = A 단계 이름)은 A 상세의 단계 토큰·합계에 0.
    분모: A 꼬리표 줄(3)은 든다."""
    a, b = companies
    run_a = owner_run(owner, a, owner_document(owner, a, "ad4d-g2"))
    owner_step(owner, a, run_a, "judge", 0)
    owner_step_line(owner, b, run_a, "judge", 1000)  # B 의 줄이 A 의 실행·단계를 달았다
    owner_step_line(owner, a, run_a, "judge", 3)
    access = operator_access(client)
    body = detail_of(client, access, run_a, a).json()
    assert body["stepUsageRecorded"] is True
    assert [(s["name"], s["tokens"]) for s in body["steps"]] == [("judge", 3)]
    assert body["tokens"] == 3


def test_a_customer_bearer_gets_no_run_detail(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓗ 고객사 Bearer 는 403 FORBIDDEN, 몸에 실행·단계 0 — 분모: 운영 관리자의 같은 요청은 200 이고 단계가 있다."""
    a, _ = companies
    run_a = owner_run(owner, a, owner_document(owner, a, "ad4d-h"))
    owner_step(owner, a, run_a, "extract", 0)
    refused = detail_of(client, customer_access(client, a), run_a, a)
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "FORBIDDEN")
    assert {"id", "steps", "files", "tokens"} & set(refused.json()) == set()
    assert b"ad4d-h" not in refused.content
    seen = detail_of(Client(), operator_access(Client()), run_a, a)
    assert seen.status_code == 200
    assert [s["name"] for s in seen.json()["steps"]] == ["extract"]


# ── ND1: 문서 없는 실행(MARC-TICK-236 의 9f 허락 ⓗ) — 더하기만 ──
# ND1 ⓗ A 의 문서 없는 실행(문서 칸 NULL)이 companyId=B 로 고른 목록·엑셀에 0줄. 분모: 같은 함수 안에서 companyId=A 로
#    고르면 목록 1줄(documentId·documentName null)·엑셀 1줄(문서 칸 빈칸).


def owner_documentless_run(owner: Owner, company_id: int) -> int:
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'probe', 'probe.bare@1', '{}', '{}', 'service', 'queued', 0, 0, 7) "
        "RETURNING id",
        [company_id],
    ).fetchone()
    assert row is not None
    return int(row[0])


def test_a_documentless_run_of_a_is_not_in_bs_list_or_workbook(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    a, b = companies
    run_a = owner_documentless_run(owner, a)
    access = operator_access(client)
    in_b = run_logs(client, access, b)
    assert (in_b.status_code, in_b.json()["count"], in_b.json()["results"]) == (200, 0, [])
    of_b = export_of(client, access, b)
    assert of_b.status_code == 200
    assert len(list(load_workbook(io.BytesIO(of_b.content)).worksheets[0].iter_rows())) == 1  # 머리 줄만
    in_a = run_logs(client, access, a)
    assert [(r["id"], r["documentId"], r["documentName"]) for r in in_a.json()["results"]] == [(run_a, None, None)]
    of_a = export_of(client, access, a)
    rows = [tuple(c.value for c in row) for row in load_workbook(io.BytesIO(of_a.content)).worksheets[0].iter_rows()]
    assert len(rows) == 2 and rows[1][2] is None  # 분모: A 로 고르면 한 줄, 문서 칸 빈칸


# ── RF1: 결과 파일 받기(MARC-TICK-241 의 9f 허락 ⓘ·ⓙ) — 더하기만 ──

RF1_BYTES = b"RF1-SYNTHETIC-OUTPUT"


@pytest.fixture
def rf1_storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1000)


def owner_output_file(owner: Owner, storage: FakeStorage, company_id: int, run_id: int, name: str) -> None:
    """주인 역할이 흐름의 출력 파일 행(step NULL)을 넣고, 가짜 저장소의 같은 키에 바이트를 둔다."""
    key = f"runs/{company_id}/{run_id}/out/{name}"
    storage.put(key, RF1_BYTES)
    owner.execute(
        "INSERT INTO run_files (created_at, company_id, run_id, step, name, media_type, storage_key, "
        "size_bytes, sha256) VALUES (now(), %s, %s, NULL, %s, 'application/vnd.ms-excel', %s, %s, %s)",
        [company_id, run_id, name, key, len(RF1_BYTES), "0" * 64],
    )


def file_of(client: Client, access: str, run_id: int, name: str, company_id: int) -> Any:
    return client.get(f"/api/run-logs/{run_id}/files/{name}?companyId={company_id}", **bearer(access))


def download_lines(owner: Owner, run_id: int) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT company_id, actor_kind, event, result, target_label FROM core_audit_events "
        "WHERE action = 'download' AND target_kind = 'run' AND target_id = %s ORDER BY id",
        [run_id],
    ).fetchall()


def test_choosing_b_gets_404_on_a_file_of_a_run_of_a_like_a_missing_id(
    client: Client, owner: Owner, companies: tuple[int, int], rf1_storage: FakeStorage
) -> None:
    """ⓘ B 로 고른 운영 관리자에게 A 실행의 출력 파일은 404 RUN_NOT_FOUND 이고, 없는 실행 id 의 404 와 같다. 바이트 0·
    감사 0. 분모: 같은 함수에서 A 로 고르면 200·바이트·감사 한 줄."""
    a, b = companies
    run_a = owner_run(owner, a, owner_document(owner, a, "rf1-i"))
    owner_output_file(owner, rf1_storage, a, run_a, "report.xls")
    access = operator_access(client)
    foreign = file_of(client, access, run_a, "report.xls", b)
    missing = file_of(client, access, 9_000_000_000_000_000_000, "report.xls", b)
    assert (foreign.status_code, foreign.json()["error"]["code"]) == (404, "RUN_NOT_FOUND")
    assert (foreign.status_code, foreign.content) == (missing.status_code, missing.content)
    assert RF1_BYTES not in foreign.content
    assert download_lines(owner, run_a) == []
    seen = file_of(client, access, run_a, "report.xls", a)
    assert (seen.status_code, seen.content) == (200, RF1_BYTES)  # 분모: 같은 함수로 A 를 고르면 받는다
    assert download_lines(owner, run_a) == [(a, "admin", "run_file_downloaded", "success", "report.xls")]


def test_a_customer_bearer_gets_no_run_file(
    client: Client, owner: Owner, companies: tuple[int, int], rf1_storage: FakeStorage
) -> None:
    """ⓙ 고객사 Bearer 는 403 FORBIDDEN, 몸에 바이트 0·감사 0 — 분모: 운영 관리자의 같은 요청은 200 이고 바이트다."""
    a, _ = companies
    run_a = owner_run(owner, a, owner_document(owner, a, "rf1-j"))
    owner_output_file(owner, rf1_storage, a, run_a, "report.xls")
    refused = file_of(client, customer_access(client, a), run_a, "report.xls", a)
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "FORBIDDEN")
    assert RF1_BYTES not in refused.content
    assert download_lines(owner, run_a) == []
    seen = file_of(Client(), operator_access(Client()), run_a, "report.xls", a)
    assert (seen.status_code, seen.content) == (200, RF1_BYTES)


# ── LK1: 같이 시작 묶음 칸(MARC-TICK-259 의 73 허락 ⓚ) — 더하기만 ──

LAUNCH = "1a2b3c4d-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID


def owner_launched_run(owner: Owner, company_id: int, launch_key: str) -> int:
    """주인 역할이 실행 한 줄을 같은 사람(7)·그 launch_key 로 심는다."""
    run_id = owner_run(owner, company_id, owner_document(owner, company_id, f"launch-{company_id}-{launch_key[:4]}"))
    owner.execute("UPDATE run_runs SET launch_key = %s WHERE id = %s", [launch_key, run_id])
    return run_id


def test_a_launch_of_a_does_not_count_into_b(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓚ B 를 고르면 B 의 줄은 1/1·첫 id = B 의 것, 몸에 A 의 id 0. 분모: A 를 고르면 2·1/2·2/2·첫 id = A 의 앞 것."""
    a, b = companies
    first_a = owner_launched_run(owner, a, LAUNCH)
    second_a = owner_run(owner, a, owner_document(owner, a, "launch-a-2"))
    owner.execute("UPDATE run_runs SET launch_key = %s WHERE id = %s", [LAUNCH, second_a])
    in_b = owner_launched_run(owner, b, LAUNCH)
    access = operator_access(client)
    listed = run_logs(client, access, b)
    assert listed.status_code == 200, listed.content.decode()
    (line,) = listed.json()["results"]
    cells = (line["id"], line["launchKey"], line["launchFirstRunId"], line["launchIndex"], line["launchSize"])
    assert cells == (in_b, LAUNCH, in_b, 1, 1)
    detail = detail_of(client, access, in_b, b)
    assert detail.status_code == 200
    shown = detail.json()
    assert (shown["launchFirstRunId"], shown["launchIndex"], shown["launchSize"]) == (in_b, 1, 1)
    for row in (line, shown):  # 줄·상세의 실행 id 칸(id·launchFirstRunId·resumedFromRunId)에 A 의 실행 id 0
        assert {first_a, second_a} & {row["id"], row["launchFirstRunId"], row["resumedFromRunId"]} == set()
    mine = {row["id"]: row for row in run_logs(client, access, a).json()["results"]}
    found = [(mine[i]["launchFirstRunId"], mine[i]["launchIndex"], mine[i]["launchSize"]) for i in (first_a, second_a)]
    assert found == [(first_a, 1, 2), (first_a, 2, 2)]
