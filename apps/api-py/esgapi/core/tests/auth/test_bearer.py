"""access 토큰(Bearer)의 인증(AccessTokenAuth)과 권한 검사(permitted). 순수 층: DB 없음(RequestFactory).

토큰은 core/auth/tokens 로 설정의 비밀(app_config().session_secret)에 서명한다. 시계는 claims 의 now 를 과거로 둔다.
core 의 테스트라 업무 모듈을 import 하지 않는다(계약 가).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from django.http import HttpRequest
from django.test import RequestFactory

from esgapi.core.auth import bearer as bearer_module
from esgapi.core.auth.bearer import (
    AccessTokenAuth,
    CompanyScopedAuth,
    access_token_auth,
    company_of,
    company_scoped_auth_or_next,
    permitted,
    use_operator_company,
)
from esgapi.core.auth.principal import Principal
from esgapi.core.auth.tokens import ACCESS_TTL_SECONDS, new_access_claims, sign_access
from esgapi.core.conf import app_config
from esgapi.core.exceptions import ApplicationError
from esgapi.core.tenancy.session import Session, new_session

JTI = UUID("33333333-3333-4333-8333-333333333333")
COMPANY_OPERATION = "inventory_calc"  # 표의 고객사 사용자 칸(CUSTOMER) 하나
COMPANY_WORK_OPERATION = "core_documents_list"  # 표의 회사 업무 칸(COMPANY) 하나 — 두 kind 다(MARC-ENT-374)


def access(*, now: datetime | None = None, **overrides: Any) -> str:
    fields: dict[str, Any] = {
        "user_id": "42",
        "kind": "service",
        "level": 79,
        "company_id": 7,
        "company_is_active": True,
        "is_initial": False,
        "jti": JTI,
        "now": now or datetime.now(UTC),
    }
    return sign_access(new_access_claims(**(fields | overrides)), secret=app_config().session_secret)


def operator_access() -> str:
    return access(user_id="9", kind="admin", level=99, company_id=None, company_is_active=None)


def request_with(authorization: str | None) -> HttpRequest:
    if authorization is None:
        return RequestFactory().get("/users/me")
    return RequestFactory().get("/users/me", HTTP_AUTHORIZATION=authorization)


def rejected(auth: AccessTokenAuth, request: HttpRequest) -> tuple[str, str]:
    with pytest.raises(ApplicationError) as caught:
        auth(request)
    return caught.value.kind, caught.value.code


def principal(*, kind: str = "service", is_initial: bool = False) -> Principal:
    if kind == "admin":
        return Principal(user_id="9", company_id=None, kind="admin", is_initial=is_initial, via="bearer")
    return Principal(user_id="42", company_id=7, kind="service", is_initial=is_initial, via="bearer")


class AuthedRequest(HttpRequest):
    """django-ninja 의 인증이 결과를 넣어 두는 칸(`auth`)을 선언한 요청. HttpRequest 의 선언에는 그 칸이 없다."""

    auth: Principal | Session


def authed(auth: Principal | Session) -> HttpRequest:
    request = AuthedRequest()
    request.auth = auth
    return request


# ── 인증 ──


def test_without_a_header_the_optional_auth_returns_none() -> None:
    assert AccessTokenAuth()(request_with(None)) is None


def test_a_non_bearer_header_returns_none() -> None:
    assert AccessTokenAuth()(request_with("Basic x")) is None


def test_the_required_auth_without_a_header_is_no_token() -> None:
    assert rejected(access_token_auth, request_with(None)) == ("unauthenticated", "no_token")
    assert rejected(access_token_auth, request_with("Basic x")) == ("unauthenticated", "no_token")


def test_an_expired_access_is_token_not_valid() -> None:
    expired = access(now=datetime.now(UTC) - timedelta(seconds=ACCESS_TTL_SECONDS + 1))
    assert rejected(AccessTokenAuth(), request_with(f"Bearer {expired}")) == ("token_not_valid", "token_not_valid")
    # 분모: 같은 꼴의 살아 있는 토큰은 지난다
    assert AccessTokenAuth()(request_with(f"Bearer {access()}")) is not None


def test_an_empty_bearer_is_token_not_valid() -> None:
    assert rejected(AccessTokenAuth(), request_with("Bearer ")) == ("token_not_valid", "token_not_valid")


def test_a_customer_access_becomes_a_service_principal() -> None:
    found = AccessTokenAuth()(request_with(f"Bearer {access(is_initial=True)}"))
    assert found == Principal(user_id="42", company_id=7, kind="service", is_initial=True, via="bearer")


def test_an_operator_access_becomes_an_admin_principal_without_a_company() -> None:
    found = access_token_auth(request_with(f"Bearer {operator_access()}"))
    assert found == Principal(user_id="9", company_id=None, kind="admin", is_initial=False, via="bearer")


# ── 권한 ──


def forbidden_code(request: HttpRequest, operation_id: str) -> tuple[str, str]:
    with pytest.raises(ApplicationError) as caught:
        permitted(request, operation_id)
    return caught.value.kind, caught.value.code


def test_an_initial_principal_on_a_company_operation_must_change_the_password_first() -> None:
    """is_initial 이 표보다 먼저다: 고객사 사용자의 칸이 열려 있어도 password_change_required(forbidden 아님)."""
    request = authed(principal(is_initial=True))
    assert forbidden_code(request, COMPANY_OPERATION) == ("forbidden", "password_change_required")
    # 운영 관리자여도 같다(표의 forbidden 보다 앞)
    request = authed(principal(kind="admin", is_initial=True))
    assert forbidden_code(request, COMPANY_OPERATION) == ("forbidden", "password_change_required")


@pytest.mark.parametrize("operation_id", ["user_me", "user_password_change"])
def test_an_initial_principal_may_use_its_own_account(operation_id: str) -> None:
    found = principal(is_initial=True)
    assert permitted(authed(found), operation_id) == found


def test_both_kinds_pass_a_company_work_operation() -> None:
    assert permitted(authed(principal(kind="admin")), COMPANY_WORK_OPERATION).kind == "admin"
    assert permitted(authed(principal()), COMPANY_WORK_OPERATION).kind == "service"


def test_an_operator_on_a_company_operation_is_forbidden() -> None:
    assert forbidden_code(authed(principal(kind="admin")), COMPANY_OPERATION) == ("forbidden", "forbidden")
    # 분모: 같은 동작을 고객사 사용자는 지난다
    assert permitted(authed(principal()), COMPANY_OPERATION).kind == "service"


def test_a_cookie_session_is_a_service_principal() -> None:
    session = new_session(
        user_id="42", tenant_id="tenant-a", company_id=7, role="viewer", now=datetime.now(UTC), ttl_seconds=600
    )
    found = permitted(authed(session), COMPANY_OPERATION)
    assert found == Principal(user_id="42", company_id=7, kind="service", is_initial=False, via="session")


def test_no_auth_on_the_request_is_no_session() -> None:
    assert forbidden_code(RequestFactory().get("/"), "user_me") == ("unauthenticated", "no_session")


# ── CompanyScopedAuth(K2b — 회사 경로의 Bearer, 머리가 없으면 다음) ─────────────────


def test_the_company_auth_without_a_bearer_header_passes_to_the_next() -> None:
    assert company_scoped_auth_or_next(request_with(None)) is None
    assert company_scoped_auth_or_next(request_with("Basic x")) is None


def test_the_company_auth_lets_an_operator_token_through_without_a_company() -> None:
    """운영 관리자(회사 없음)는 회사 경로의 인증을 지난다(MARC-ENT-374). 회사 칸은 None 그대로 — 회사는 permitted 뒤
    company_of 가 정한다."""
    found = CompanyScopedAuth()(request_with(f"Bearer {operator_access()}"))
    assert found == Principal(user_id="9", company_id=None, kind="admin", is_initial=False, via="bearer")


def test_the_company_auth_refuses_an_initial_token_before_the_body() -> None:
    assert rejected(CompanyScopedAuth(), request_with(f"Bearer {access(is_initial=True)}")) == (
        "forbidden",
        "password_change_required",
    )
    initial_operator = access(
        user_id="9", kind="admin", level=99, company_id=None, company_is_active=None, is_initial=True
    )
    assert rejected(CompanyScopedAuth(), request_with(f"Bearer {initial_operator}")) == (
        "forbidden",
        "password_change_required",
    )


def test_a_bad_company_bearer_is_444_not_none() -> None:
    """틀린 Bearer 는 None(다음 — 쿠키)이 아니라 444 다(쿠키로 넘어가지 않는다)."""
    assert rejected(CompanyScopedAuth(), request_with("Bearer not-a-token")) == ("token_not_valid", "token_not_valid")
    found = company_scoped_auth_or_next(request_with(f"Bearer {access()}"))  # 분모: 고객사 사용자는 지난다
    assert found is not None and (found.kind, found.company_id) == ("service", 7)


# ── company_of(회사 업무의 회사 — 운영 관리자는 꽂힌 포트, MARC-ENT-374) ─────────────────


@pytest.fixture
def no_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """포트를 비운다(config.api 가 먼저 import 돼 꽂혀 있어도 이 시험 안에서만)."""
    monkeypatch.setattr(bearer_module, "_operator_company", None)


def counting_port(answer: int) -> tuple[list[int], Any]:
    calls: list[int] = []

    def choose() -> int:
        calls.append(answer)
        return answer

    return calls, choose


def test_a_customer_company_is_its_own_and_never_asks_the_port(no_port: None) -> None:
    calls, choose = counting_port(5)
    use_operator_company(choose)
    assert company_of(principal()) == 7
    assert calls == []


def test_an_operator_company_is_what_the_port_chooses(no_port: None) -> None:
    calls, choose = counting_port(5)
    use_operator_company(choose)
    assert company_of(principal(kind="admin")) == 5
    assert calls == [5]


def test_without_a_port_an_operator_is_company_required(no_port: None) -> None:
    with pytest.raises(ApplicationError) as caught:
        company_of(principal(kind="admin"))
    assert (caught.value.kind, caught.value.code) == ("unauthenticated", "company_required")
    assert company_of(principal()) == 7  # 분모: 고객사 사용자는 포트 없이도 제 회사


def test_plugging_the_same_port_twice_is_fine_but_another_is_refused(no_port: None) -> None:
    _, choose = counting_port(5)
    use_operator_company(choose)
    use_operator_company(choose)  # 멱등
    _, other = counting_port(6)
    with pytest.raises(RuntimeError):
        use_operator_company(other)
    assert company_of(principal(kind="admin")) == 5  # 처음 꽂은 것 그대로
