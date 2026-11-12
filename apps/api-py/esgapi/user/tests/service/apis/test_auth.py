"""permitted_session 이 권한 표(core/permissions.py)를 읽는다. 순수 층."""

from datetime import UTC, datetime

import pytest
from django.http import HttpRequest

from esgapi.core.exceptions import ApplicationError
from esgapi.core.permissions import OPERATION_POLICY, OPERATOR
from esgapi.core.tenancy.session import Role, Session, new_session
from esgapi.user.service.apis.auth import permitted_session

# ── 403 으로 바꾸는 자리(경로 쪽). DB 없이 잰다: 요청 자리에 세션만 든 가짜를 넣는다 ──


class AuthedRequest(HttpRequest):
    """django-ninja 의 인증이 세션을 넣어 두는 칸(`auth`)을 선언한 요청. HttpRequest 의 선언에는 그 칸이 없다."""

    auth: Session


def request_of(role: Role) -> HttpRequest:
    request = AuthedRequest()
    request.auth = new_session(
        user_id="u", tenant_id="t", company_id=1, role=role, now=datetime(2026, 1, 1, tzinfo=UTC), ttl_seconds=60
    )
    return request


def test_permitted_session_returns_the_session_or_raises_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    # 쿠키 세션의 주체는 역할과 무관하게 고객사 사용자다(가2): viewer 세션도 지난다.
    assert permitted_session(request_of("viewer"), "accounts_me").role == "viewer"
    monkeypatch.setitem(OPERATION_POLICY, "accounts_me", OPERATOR)
    for role in ("admin", "editor", "viewer"):
        with pytest.raises(ApplicationError) as caught:
            permitted_session(request_of(role), "accounts_me")
        assert (caught.value.kind, caught.value.code) == ("forbidden", "forbidden")
        assert caught.value.message == "이 일은 운영 관리자만 한다"
