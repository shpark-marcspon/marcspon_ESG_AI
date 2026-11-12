"""운영 관리자 실행 기록(GET /run-logs)의 만든 사람 이름 — 작업 회사로 실행을 만든 운영 관리자(밴드 OP1 §2-3, 결정
MARC-ENT-374). 업무 층. 이름 풀기는 user 의 people_of: 그 회사 고객사 사용자 먼저, 못 푼 id 는 운영 관리자.
도우미는 test_run_logs.py 의 것을 쓴다(실행 행은 등록부로 — 계약 나)."""

import pytest
from django.test import Client

from esgapi.user.models import User
from esgapi.user.tests.service.apis.test_run_logs import at, customer, document, logs, made, operator_access

pytestmark = pytest.mark.django_db


def test_a_run_made_by_the_operator_carries_the_operators_name(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    ops = User.unscoped.get(username="ops", kind="admin").pk
    kim = customer(a, "kim", "김담당")
    by_operator = made(a, document(a), created_at=at(1), created_by_user_id=ops)
    by_customer = made(a, document(a), created_at=at(2), created_by_user_id=kim)
    rows = {row["id"]: row for row in logs(client, access, f"companyId={a}").json()["results"]}
    assert (rows[by_operator]["createdByName"], rows[by_operator]["createdByUsername"]) == ("운영자", "ops")
    assert (rows[by_customer]["createdByName"], rows[by_customer]["createdByUsername"]) == ("김담당", "kim")
