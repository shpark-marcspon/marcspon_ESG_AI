"""운영 관리자 실행 기록(GET /run-logs·/run-logs/{id}·/run-logs/export)의 같이 시작 묶음 칸(밴드 LK1 — MARC-ISSUE-303 ①,
발주서 §2-9 업무 7~11). 업무 층.

    7 같은 열쇠 셋 → 줄마다 첫 id = 맨 앞 id · 차례 1·2·3 · 수 3 · 열쇠. 열쇠 없는 줄은 묶음 넷 null
    8 거르기·쪽 무관: status=failed·limit=1 에서도, 상세에서도 원래 차례/수
    9 같은 회사 다른 사람의 같은 열쇠 = 다른 묶음 · 고른 회사 안만(운영 관리자가 회사 A·B 에 같은 열쇠)
    10 쿼리 수: 열쇠 없는 쪽 = LK1 앞 · 열쇠 있는 쪽 +1 · 상세 +1 · 내보내기 = LK1 앞(열쇠 있어도) · 엑셀 줄 값은 열쇠
       유무와 무관
    11 resumedFromRunId 가 줄·상세에 실림(null 분모)

실행 행은 test_run_logs.py 처럼 등록부(apps.get_model)로 심는다 — user 의 시험은 esgapi.runs.models 를 import 하지
않는다.
앱 역할의 경계(회사 B 줄에 A 의 id 0)는 보안 층 tests/security/test_run_logs.py ⓚ.
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.user.tests.service.apis.test_run_logs import (
    at,
    body_queries,
    customer,
    document,
    logs,
    made,
    operator_access,
    run_rows,
    sheet_rows,
)
from tests.support.http import bearer

pytestmark = pytest.mark.django_db

K = "1a2b3c4d-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID
K2 = "5e6f7a8b-9999-4aaa-8bbb-cccccccccccc"
LAUNCH_KEYS = ("launchKey", "launchFirstRunId", "launchIndex", "launchSize")


def cells(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row[k] for k in LAUNCH_KEYS)


def lines(client: Client, access: str, query: str) -> dict[int, tuple[Any, ...]]:
    response = logs(client, access, query)
    assert response.status_code == 200, response.content.decode()
    return {row["id"]: cells(row) for row in response.json()["results"]}


def detail(client: Client, access: str, run_id: int, company_id: int) -> Any:
    response = client.get(f"/api/run-logs/{run_id}?companyId={company_id}", **bearer(access))
    assert response.status_code == 200, response.content.decode()
    return response.json()


def three(company_id: int, *, statuses: tuple[str, str, str] = ("done", "failed", "done")) -> list[int]:
    """같은 사람(7)이 같은 열쇠 K 로 같이 시작한 셋(만든 차례 = id 오름)."""
    doc = document(company_id)
    return [made(company_id, doc, created_at=at(1, 10, n), status=s, launch_key=K) for n, s in enumerate(statuses)]


# ── 7 묶음 칸 ─────────────────────────────────────────────────────────


def test_a_launch_of_three_shows_first_index_and_size(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    ids = three(a)
    plain = made(a, document(a), created_at=at(2))
    assert lines(client, access, f"companyId={a}") == {
        plain: (None, None, None, None),  # 묶음 없음 — 1/1 이 아니다
        ids[2]: (K, ids[0], 3, 3),
        ids[1]: (K, ids[0], 2, 3),
        ids[0]: (K, ids[0], 1, 3),
    }


# ── 8 거르기·쪽 무관 ──────────────────────────────────────────────────


def test_the_launch_cells_ignore_filters_paging_and_hold_in_the_detail(
    client: Client, companies: tuple[int, int]
) -> None:
    a, _ = companies
    access = operator_access(client)
    ids = three(a)
    assert lines(client, access, f"companyId={a}&status=failed") == {ids[1]: (K, ids[0], 2, 3)}
    assert lines(client, access, f"companyId={a}&limit=1") == {ids[2]: (K, ids[0], 3, 3)}  # 새 것 먼저
    assert lines(client, access, f"companyId={a}&limit=1&offset=2") == {ids[0]: (K, ids[0], 1, 3)}
    assert cells(detail(client, access, ids[1], a)) == (K, ids[0], 2, 3)


# ── 9 범위 ────────────────────────────────────────────────────────────


def test_another_person_with_the_same_key_is_another_launch(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    kim = customer(a, "kim")
    doc = document(a)
    mine = [made(a, doc, created_at=at(1, 10, n), launch_key=K) for n in range(2)]
    theirs = made(a, doc, created_at=at(1, 11), launch_key=K, created_by_user_id=kim)
    assert lines(client, access, f"companyId={a}") == {
        theirs: (K, theirs, 1, 1),
        mine[1]: (K, mine[0], 2, 2),
        mine[0]: (K, mine[0], 1, 2),
    }


def test_the_launch_is_counted_inside_the_chosen_company(client: Client, companies: tuple[int, int]) -> None:
    """운영 관리자가 회사 A 에 둘·B 에 하나를 같은 열쇠로(같은 사람) — B 를 고르면 1/1·첫 id 는 B 의 것."""
    a, b = companies
    access = operator_access(client)
    in_a = [made(a, document(a), created_at=at(1, 10, n), launch_key=K) for n in range(2)]
    in_b = made(b, document(b), created_at=at(1, 12), launch_key=K)
    assert lines(client, access, f"companyId={b}") == {in_b: (K, in_b, 1, 1)}
    assert cells(detail(client, access, in_b, b)) == (K, in_b, 1, 1)
    assert lines(client, access, f"companyId={a}") == {in_a[1]: (K, in_a[0], 2, 2), in_a[0]: (K, in_a[0], 1, 2)}


# ── 10 쿼리 수·엑셀 ───────────────────────────────────────────────────


def counted(client: Client, access: str, path: str) -> tuple[int, Any]:
    with CaptureQueriesContext(connection) as seen:
        response = client.get(path, **bearer(access))
    assert response.status_code == 200, response.content.decode()
    return len(body_queries(seen)), response


def test_a_key_on_the_page_costs_one_query_and_the_export_none(client: Client, companies: tuple[int, int]) -> None:
    _, b = companies
    access = operator_access(client)
    # 원천 없는 모듈(inventory)만 — 원천 쿼리가 섞이지 않게
    plain = [
        made(b, document(b), created_at=at(1, 10, n), module="inventory", flow_id="inventory.x@1") for n in range(3)
    ]
    paths = (f"/api/run-logs?companyId={b}", f"/api/run-logs/{plain[0]}?companyId={b}")
    keyless = [counted(client, access, path)[0] for path in paths]
    keyless_export, keyless_sheet = counted(client, access, f"/api/run-logs/export?companyId={b}")
    # 목록 = 회사 고르기 1 + 셈 1 + 쪽 1 + LLM 합 1 + 이름 1(LK1 앞 — test_run_logs.py 의 test_query_counts 와 같은 셈)
    assert keyless[0] == 5
    run_rows().filter(pk__in=plain).update(launch_key=K)
    keyed = [counted(client, access, path)[0] for path in paths]
    keyed_export, keyed_sheet = counted(client, access, f"/api/run-logs/export?companyId={b}")
    assert keyed == [n + 1 for n in keyless]  # 목록·상세 = 묶음 쿼리 +1
    assert keyed_export == keyless_export  # 내보내기는 묶음을 세지 않는다
    assert sheet_rows(keyed_sheet) == sheet_rows(keyless_sheet)  # 엑셀 줄 값 그대로(칸 0)
    assert lines(client, access, f"companyId={b}")[plain[0]] == (K, plain[0], 1, 3)  # 분모: 셈은 했다


# ── 11 resumedFromRunId ──────────────────────────────────────────────


def test_resumed_from_is_on_the_line_and_the_detail(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    doc = document(a)
    first = made(a, doc, created_at=at(1), status="failed")
    child = made(a, doc, created_at=at(2), resumed_from_run_id=first, launch_key=K2)
    response = logs(client, access, f"companyId={a}")
    found = {row["id"]: row["resumedFromRunId"] for row in response.json()["results"]}
    assert found == {child: first, first: None}
    body = detail(client, access, child, a)
    assert (body["resumedFromRunId"], cells(body)) == (first, (K2, child, 1, 1))  # 다시 하기 = 새 열쇠 1/1
    assert detail(client, access, first, a)["resumedFromRunId"] is None
