"""교환의 판정, 토큰의 내용 읽기, 권한 규칙, 세션의 규칙. 순수 층: DB 도 틀도 없이 돈다."""

from datetime import UTC, datetime, timedelta

import pytest

from esgapi.core.auth.principal import principal_of_session
from esgapi.core.permissions import OPERATION_POLICY, OPERATOR
from esgapi.core.tenancy.session import ROLES, Role, is_expired, new_session
from esgapi.organization.service.permissions.organization import can_create_site, can_view_sites
from esgapi.user.service.utils.entities import Tenant, User
from esgapi.user.service.utils.exchange import Admitted, ExchangeRejected, TenantRegistered, TenantUnknown, admit
from esgapi.user.service.utils.tokens import (
    EdkClaims,
    TokenOk,
    TokenRejected,
    claims_from_payload,
    is_valid_tenant_id,
)

CLAIMS = EdkClaims(issuer="https://edk.test", external_id="u1", tenant_id="tenant-a", role="editor", name="김담당")
PAYLOAD: dict[str, object] = {
    "iss": "https://edk.test",
    "sub": "u1",
    "tenant_id": "tenant-a",
    "role": "editor",
    "name": "김담당",
}
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def test_registered_tenant_is_admitted() -> None:
    tenant = Tenant(id="tenant-a", name="가 회사", company_id=1)
    assert admit(CLAIMS, TenantRegistered(tenant)) == Admitted(CLAIMS, tenant)


def test_unknown_tenant_is_rejected_by_name() -> None:
    assert admit(CLAIMS, TenantUnknown()) == ExchangeRejected("unknown_tenant")


def test_claims_are_read_from_a_verified_payload() -> None:
    assert claims_from_payload(PAYLOAD) == TokenOk(CLAIMS)


@pytest.mark.parametrize(
    ("key", "bad"),
    [
        ("sub", None),
        ("sub", ""),
        ("sub", 123),
        ("name", None),
        ("tenant_id", None),
        ("tenant_id", "Tenant-A"),  # 대문자
        ("tenant_id", "../x"),
        ("tenant_id", "a" * 64),
        ("role", None),
        ("role", "superadmin"),  # 우리가 모르는 역할을 admin 으로도 viewer 로도 읽지 않는다
        ("role", ["admin"]),
    ],
)
def test_missing_or_misshapen_claims_are_bad_claims(key: str, bad: object) -> None:
    payload = {**PAYLOAD, key: bad}
    if bad is None:
        del payload[key]
    assert claims_from_payload(payload) == TokenRejected("bad_claims")


def test_tenant_id_shape_matches_the_ts_skeleton() -> None:
    assert is_valid_tenant_id("tenant-a")
    for bad in ["", "Tenant", "a/b", "../x", "a b", "-a", "a" * 64, None, 1]:
        assert not is_valid_tenant_id(bad)


@pytest.mark.parametrize("cell", ["as_is", "operator_only"])
@pytest.mark.parametrize("role", ["admin", "editor", "viewer"])
def test_every_role_creates_sites_unless_the_cell_is_operator_only(
    role: Role, cell: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """교환 다리의 세션은 역할과 무관하게 고객사 사용자다(가2). 칸을 운영 관리자 몫으로 옮기면 셋 다 못 한다."""
    if cell == "operator_only":
        monkeypatch.setitem(OPERATION_POLICY, "accounts_sites_create", OPERATOR)
    kind = principal_of_session(
        new_session(user_id="1", tenant_id="t", company_id=1, role=role, now=NOW, ttl_seconds=60)
    ).kind
    assert can_create_site(kind) is (cell == "as_is")
    assert can_view_sites(kind) is True


def test_roles_are_exactly_the_three_in_the_plan() -> None:
    assert ROLES == ("admin", "editor", "viewer")


def test_session_freezes_tenant_and_role_and_expires_after_ttl() -> None:
    user = User(
        id="user-1", company_id=1, tenant_id="tenant-a", issuer="i", external_id="u1", name="김담당", role="viewer"
    )
    # 세션의 발급은 core 의 것이라 User 를 모른다. 교환(services.exchange)이 하는 대로 값 넷을 넘긴다.
    session = new_session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        company_id=user.company_id,
        role=user.role,
        now=NOW,
        ttl_seconds=600,
    )
    assert (session.user_id, session.tenant_id, session.role) == ("user-1", "tenant-a", "viewer")
    assert session.expires_at == NOW + timedelta(seconds=600)
    assert not is_expired(session, now=NOW + timedelta(seconds=599))
    assert is_expired(session, now=NOW + timedelta(seconds=600))  # 끝나는 순간부터 만료다
