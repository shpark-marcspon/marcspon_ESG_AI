"""운영 관리자의 작업 회사 고르기 operator_work_company(결정 MARC-ENT-374, 밴드 OP1 §2-2). 업무 층.

core 의 company_of 가 운영 관리자에게 부르는 포트다(config/api.py 가 꽂는다). 하나뿐인 활성 회사면 그 id, 둘 이상이면
400 company_ambiguous, 없으면 400 company_not_found(사용자 관리 경로의 같은 code 는 404 — chosen_company), 하나인데 사용
중지면 403 company_inactive. 회사 표의 앞 두 행 말고는 읽지 않는다(쿼리 하나).
회사: 뿌리 conftest 의 tenants(둘)·seed_company 명령(하나 — test_users.py 의 solo 꼴). 사용 중지는 선택자를 감싸
is_active 를 끈 값으로(user 의 테스트는 organization 의 models 를 import 하지 않는다 — 계약 나. 진짜 사용 중지 행은
보안 층 tests/security/test_operator_company.py 가 잰다).
"""

from dataclasses import replace

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from esgapi.core.auth import bearer as bearer_module
from esgapi.core.exceptions import ApplicationError
from esgapi.user.service.apis import users as users_api

pytestmark = pytest.mark.django_db


def seed_one() -> int:
    call_command("seed_company", name="홀로 회사", business_licence_number="333-33-33333", subdomain="solo")
    sole = users_api.find_sole_company()
    assert isinstance(sole, users_api.SoleCompany), sole
    return sole.company.id


def refused() -> tuple[str, str]:
    with pytest.raises(ApplicationError) as caught:
        users_api.operator_work_company()
    return caught.value.kind, caught.value.code


def test_one_active_company_is_the_work_company_reading_one_query() -> None:
    company_id = seed_one()
    with CaptureQueriesContext(connection) as queries:
        assert users_api.operator_work_company() == company_id
    assert len(queries) == 1
    assert "LIMIT 2" in queries[0]["sql"]  # 앞 두 행만


def test_two_companies_are_ambiguous(tenants: None) -> None:
    with CaptureQueriesContext(connection) as queries:
        assert refused() == ("invalid_input", "company_ambiguous")
    assert len(queries) == 1


def test_no_company_is_400_not_404() -> None:
    assert refused() == ("invalid_input", "company_not_found")


def test_one_inactive_company_is_403(monkeypatch: pytest.MonkeyPatch) -> None:
    seed_one()
    real = users_api.find_sole_company

    def inactive() -> object:
        found = real()
        assert isinstance(found, users_api.SoleCompany)
        return users_api.SoleCompany(replace(found.company, is_active=False))

    monkeypatch.setattr(users_api, "find_sole_company", inactive)
    assert refused() == ("forbidden", "company_inactive")


def test_config_plugs_it_into_core() -> None:
    """config/api.py 가 꽂은 포트가 이 함수다(core 는 user 를 import 하지 못한다 — 계약 가)."""
    from django.urls import get_resolver

    get_resolver().url_patterns  # noqa: B018 — config.api 를 들인다
    assert bearer_module._operator_company is users_api.operator_work_company  # pyright: ignore[reportPrivateUsage]
