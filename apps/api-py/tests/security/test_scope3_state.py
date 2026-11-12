"""Scope 3 연도 상태·카테고리 잠금(S3K2a — 결정 MARC-ENT-559·469 2, 테스트 6d 허락)의 보안 층. 앱 역할, 진짜 커밋.

카테고리 잠금 표(inventory_scope3_categories)는 회사 칸 표다(conftest 의 tenant_tables 에 저절로 든다). 경로 셋
(scope3_state_paths)은 회사 행 id 를 경로에 받지 않고(해·카테고리), 잠그기만 쿼리 runId(회사 행인 실행)를 받는다.
여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 연도 상태: A 는 A 의 실행만 R·latest 로(B 가 더 늦게 만든 done 이 있어도) · B 의 잠금 0 · 응답 글자에 B 의 실행 id 0
  ⓑ 잠그기 runId: B 의 실행 id → 404 이고 없는 id 의 404 와 바이트가 같다 · 잠금 행 0(A·B 둘 다).
     분모: 제 실행 id 는 200
  ⓒ 풀기: 운영 관리자가 회사 하나(A)에서 풀면 A 의 잠금이 풀림 · 고객사 Bearer 403(제 회사도) · 회사 둘이면 400
     company_ambiguous(A·B 잠금 그대로 — 회사 하나인 운영 관리자는 B 에 닿을 길이 없다). OPERATOR_COMPANY_OPERATIONS 로
     test_tenant_paths·test_operator_company 의 고리에서 뺀 것을 여기서 다시 잰다
  ⓓ 앱 역할은 잠금 행을 지우지 못한다(42501 — 풀기는 칸을 비움)
시험마다 B 의 행이 실제로 있음을 첫 단언으로 둔다(분모). 401·444·400 은 test_tenant_paths 의 분류가 잰다.
실행 행은 주인 역할로 심는다(실행기 0). 이름·값은 지어낸 것이다.
"""

import io
import json
from typing import Any, Final

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction

from tests.security.seed import add_company
from tests.security.test_operator_company import customer_client, operator_client

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
YEAR: Final = 2025
ROOT: Final = "/api/inventory/scope3/years"
TABLE: Final = "inventory_scope3_categories"


def done_body(total: str) -> dict[str, Any]:
    return {
        "schemaVersion": "scope3.colab.result@1",
        "status": "done",
        "reportYear": YEAR,
        "sheets": [
            {
                "sheet": "가상_C4",
                "category": "Category4",
                "status": "processed",
                "rows": [{"rowId": "가상_C4!20", "co2e": total}],
            }
        ],
        "llmCalls": {},
    }


def owner_run(owner: Owner, company_id: int, total: str, *, minutes: int) -> int:
    """그 회사의 끝난 Scope 3 실행 하나와 결과(만든 때 = 지금 + minutes 분 — 만든 차례를 정한다). 주인 역할로."""
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now() + make_interval(mins => %s), now(), %s, NULL, 'inventory.scope3', 'scope3.colab@157', "
        "'{\"reportYear\": 2025}', '{}', 'service', 'done', 1, 0, 7) RETURNING id",
        [minutes, company_id],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    owner.execute(
        "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
        "VALUES (now(), %s, %s, 0, 'scope3.colab.result@1', %s::jsonb)",
        [company_id, run_id, json.dumps(done_body(total), ensure_ascii=False)],
    )
    return run_id


def owner_lock(owner: Owner, company_id: int, run_id: int, category: str = "C4") -> None:
    owner.execute(
        f"INSERT INTO {TABLE} (created_at, updated_at, company_id, year, category, locked_at, locked_by_user_id, "
        "pinned_run_id) VALUES (now(), now(), %s, %s, %s, now(), 7, %s)",
        [company_id, YEAR, category, run_id],
    )


def locks(owner: Owner, company_id: int) -> list[tuple[str, int | None]]:
    return [
        (str(category), None if pinned is None else int(pinned))
        for category, pinned in owner.execute(
            f"SELECT category, pinned_run_id FROM {TABLE} WHERE company_id = %s ORDER BY category",
            [company_id],
        ).fetchall()
    ]


def lock_url(category: str = "C4") -> str:
    return f"{ROOT}/{YEAR}/categories/{category}/lock"


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def test_the_year_state_shows_only_the_own_runs_and_locks(owner: Owner, companies: tuple[int, int]) -> None:
    a, b = companies
    mine = owner_run(owner, a, "1.5", minutes=0)
    theirs = owner_run(owner, b, "9", minutes=5)  # B 가 더 늦게 만듦
    owner_lock(owner, b, theirs)
    assert locks(owner, b) == [("C4", theirs)]  # 분모: B 의 잠금이 있다
    response = customer_client(a, "tenant-a").get(f"{ROOT}/{YEAR}")
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    assert (body["baseRunId"], body["latest"]["runId"]) == (str(mine), str(mine))
    (c4,) = [line for line in body["categories"] if line["category"] == "C4"]
    assert (c4["locked"], c4["current"]["runId"], c4["current"]["total"]) == (False, str(mine), "1.5")
    assert f'"{theirs}"' not in response.content.decode()
    assert "나 회사" not in response.content.decode() and "tenant-b" not in response.content.decode()


def test_another_companys_run_id_is_the_same_404_as_none(owner: Owner, companies: tuple[int, int]) -> None:
    a, b = companies
    owner_run(owner, a, "1", minutes=0)
    theirs = owner_run(owner, b, "2", minutes=5)
    assert len(owner.execute("SELECT id FROM run_runs WHERE company_id = %s", [b]).fetchall()) == 1  # 분모
    client = customer_client(a, "tenant-a")
    foreign = client.post(f"{lock_url()}?runId={theirs}")
    missing = client.post(f"{lock_url()}?runId={theirs + 1_000_000}")
    assert code(foreign) == (404, "NOT_FOUND")
    assert foreign.content == missing.content  # 남의 id 와 없는 id 가 같은 바이트
    assert (locks(owner, a), locks(owner, b)) == ([], [])  # 행 0 — 걸기가 판정 전에 빈 행만 둔 것도 되돌렸다
    # 양성 대조: 제 실행 id 는 잠근다(그 회사에만)
    (mine,) = [int(r[0]) for r in owner.execute("SELECT id FROM run_runs WHERE company_id = %s", [a]).fetchall()]
    assert client.post(f"{lock_url()}?runId={mine}").status_code == 200
    assert (locks(owner, a), locks(owner, b)) == ([("C4", mine)], [])


def test_unlock_by_the_sole_company_operator_and_two_companies_refuse(owner: Owner) -> None:
    a = add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
    run_a = owner_run(owner, a, "1", minutes=0)
    owner_lock(owner, a, run_a)
    assert locks(owner, a) == [("C4", run_a)]  # 분모
    operator, _ = operator_client(owner)
    assert code(customer_client(a, "tenant-a").delete(lock_url())) == (403, "FORBIDDEN")  # 고객사 — 제 회사도
    assert locks(owner, a) == [("C4", run_a)]
    opened = operator.delete(lock_url())  # 회사 하나 — 작업 회사 A
    assert opened.status_code == 200, opened.content.decode()
    assert locks(owner, a) == [("C4", None)]
    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    run_b = owner_run(owner, b, "2", minutes=5)
    owner_lock(owner, b, run_b)
    owner.execute(
        f"UPDATE {TABLE} SET locked_at = now(), locked_by_user_id = 7, pinned_run_id = %s WHERE company_id = %s",
        [run_a, a],
    )
    assert code(operator.delete(lock_url())) == (400, "COMPANY_AMBIGUOUS")  # 회사 둘 — 누구 것도 안 풂
    assert (locks(owner, a), locks(owner, b)) == ([("C4", run_a)], [("C4", run_b)])


def test_the_app_role_cannot_delete_a_lock_row(owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    owner_lock(owner, a, owner_run(owner, a, "1", minutes=0))
    assert locks(owner, a) != []  # 분모
    with pytest.raises(DatabaseError) as caught, transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {TABLE} WHERE company_id = %s", [a])
    assert "permission denied" in str(caught.value)
    assert len(locks(owner, a)) == 1


# ── S3D1: 데이터 엑셀(GET …/years/{year}/export — scope3_state_paths, 테스트 6d 허락 조건 (나)) ──


def export_url(year: int = YEAR) -> str:
    return f"{ROOT}/{year}/export"


def workbook_values(content: bytes) -> list[object]:
    from openpyxl import load_workbook

    book = load_workbook(io.BytesIO(content))
    return [value for sheet in book.worksheets for line in sheet.iter_rows(values_only=True) for value in line]


def test_the_export_of_another_companys_year_is_the_same_404_as_no_year(
    owner: Owner, companies: tuple[int, int]
) -> None:
    a, b = companies
    owner_run(owner, a, "1.5", minutes=0)
    assert customer_client(a, "tenant-a").get(export_url()).status_code == 200  # 분모: A 의 해는 내려받힌다
    theirs = customer_client(b, "tenant-b")
    foreign, missing = theirs.get(export_url()), theirs.get(export_url(YEAR + 1))
    assert code(foreign) == (404, "NOT_FOUND")
    assert foreign.content == missing.content  # A 의 결과가 있는 해와 없는 해가 같은 바이트


def test_the_export_carries_no_other_companys_values(owner: Owner, companies: tuple[int, int]) -> None:
    a, b = companies
    owner_run(owner, a, "1.5", minutes=0)
    theirs = owner_run(owner, b, "987.654", minutes=5)  # B 가 더 늦게 만듦
    owner_lock(owner, b, theirs)
    assert locks(owner, b) == [("C4", theirs)]  # 분모: B 의 실행·잠금이 있다
    response = customer_client(a, "tenant-a").get(export_url())
    assert response.status_code == 200, response.content.decode(errors="replace")[:300]
    values = workbook_values(response.content)
    assert 1.5 in values  # 양성 대조: 제 값은 있다
    assert 987.654 not in values and theirs not in values
    assert not [value for value in values if isinstance(value, str) and ("나 회사" in value or "tenant-b" in value)]


def test_the_export_without_a_session_is_401() -> None:
    from django.test import Client

    assert Client().get(export_url()).status_code == 401
