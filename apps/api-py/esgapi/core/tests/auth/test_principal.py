"""쿠키 세션의 주체. 순수 층: DB 없음. 세션의 역할(admin·editor·viewer)과 무관하게 고객사 사용자다."""

from datetime import UTC, datetime

import pytest

from esgapi.core.auth.principal import Principal, principal_of_session
from esgapi.core.tenancy.session import ROLES, Role, new_session

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("role", ROLES)
def test_a_session_principal_is_always_a_customer(role: Role) -> None:
    session = new_session(user_id="42", tenant_id="tenant-a", company_id=7, role=role, now=NOW, ttl_seconds=600)
    assert principal_of_session(session) == Principal(
        user_id="42", company_id=7, kind="service", is_initial=False, via="session"
    )
