"""people_of(밴드 OP1 §2-3 — 결정 MARC-ENT-374): 회사 업무 기록의 사람 id → (아이디, 이름). 업무 층.

그 회사의 고객사 사용자와 운영 관리자의 입구(kind admin)를 한 조회(OR)로 푼다. 남의 회사 고객사 사용자의 id 는 풀지
않는다. 넘긴 id 말고는 풀지 않는다. 쿼리 = 1(id 가 없으면 0 — 그린워싱 목록 줄의 k 를 그대로 둔다).
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.utils.entities import CompanyActive
from esgapi.user.models import User
from esgapi.user.service.selectors.user import people_of

pytestmark = pytest.mark.django_db


def company_id_of(subdomain: str) -> int:
    found = find_company(subdomain)
    assert isinstance(found, CompanyActive), found
    return found.company.id


def insert(*, kind: str, username: str, name: str, company_id: int | None) -> int:
    level = 99 if kind == "admin" else 79
    row = User.unscoped.create(
        kind=kind, username=username, company_id=company_id, name=name, level=level, password="!"
    )
    return row.pk


def test_a_customer_of_the_company_and_an_operator_are_both_named(tenants: None) -> None:
    a = company_id_of("tenant-a")
    kim = insert(kind="service", username="kim", name="김가", company_id=a)
    ops = insert(kind="admin", username="ops", name="운영자", company_id=None)
    with CaptureQueriesContext(connection) as queries:
        found = people_of(a, {kim, ops})
    assert found == {kim: ("kim", "김가"), ops: ("ops", "운영자")}
    assert len(queries) == 1  # 고객사·운영 관리자를 한 조회로


def test_a_customer_of_another_company_is_not_named_but_the_operator_is(tenants: None) -> None:
    a, b = company_id_of("tenant-a"), company_id_of("tenant-b")
    stranger = insert(kind="service", username="lee", name="이나", company_id=b)
    ops = insert(kind="admin", username="ops", name="운영자", company_id=None)
    with CaptureQueriesContext(connection) as queries:
        found = people_of(a, {stranger, ops})
    assert found == {ops: ("ops", "운영자")}
    assert len(queries) == 1
    assert people_of(b, {stranger}) == {stranger: ("lee", "이나")}  # 분모: 제 회사로는 푼다


def test_only_the_ids_asked_for_are_named(tenants: None) -> None:
    a = company_id_of("tenant-a")
    kim = insert(kind="service", username="kim", name="김가", company_id=a)
    insert(kind="service", username="park", name="박가", company_id=a)
    insert(kind="admin", username="ops", name="운영자", company_id=None)
    with CaptureQueriesContext(connection) as queries:
        assert people_of(a, {kim}) == {kim: ("kim", "김가")}
    assert len(queries) == 1  # 운영 관리자가 있어도 넘긴 id 만
    with CaptureQueriesContext(connection) as queries:
        assert people_of(a, set()) == {}
    assert len(queries) == 0
