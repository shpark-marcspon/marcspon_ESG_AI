"""사업장 유스케이스. 바깥(DB)을 가짜 함수로 넘겨, DB 없이 갈래마다 잰다. 순수 층."""

from datetime import UTC, datetime

import pytest

from esgapi.core.auth.principal import Principal, principal_of_session
from esgapi.core.permissions import OPERATION_POLICY, OPERATOR
from esgapi.core.tenancy.session import Role, Session
from esgapi.organization.service.permissions.organization import Forbidden
from esgapi.organization.service.selectors.organization import SiteList, list_sites
from esgapi.organization.service.services.organization import SiteCreated, create_site
from esgapi.organization.service.utils.entities import Site

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
COMPANY_ID = 11  # 순수 층의 가짜 회사 id(DB 가 없다)


def session(role: Role) -> Principal:
    """옛 교환 쿠키의 세션이 경로에서 principal_of_session 을 거쳐 닿는 꼴(K2b — 함수는 주체를 받는다)."""
    return principal_of_session(
        Session(user_id="user-1", tenant_id="tenant-a", company_id=COMPANY_ID, role=role, expires_at=NOW)
    )


def test_a_customer_cannot_create_when_the_cell_is_operator_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """쿠키 세션(역할과 무관하게 고객사 사용자)은 사업장을 보고 만든다(가2). 만들기 칸을 운영 관리자 몫으로 옮기면
    403 갈래이고 DB 에 쓰지 않는다."""
    site = Site(id="s1", company_id=COMPANY_ID, external_id=None, name="본사")
    asked: list[int] = []

    def all_sites(company_id: int) -> list[Site]:
        asked.append(company_id)
        return [site]

    monkeypatch.setitem(OPERATION_POLICY, "accounts_sites_create", OPERATOR)
    assert list_sites(session("viewer"), all_sites=all_sites) == SiteList([site])
    assert asked == [COMPANY_ID]  # 조회의 회사는 세션의 것

    def must_not_insert(company_id: int, name: str, external_id: str | None) -> Site:
        raise AssertionError("권한이 없는데 DB 에 쓰려 했다")

    result = create_site(session("viewer"), name="공장", external_id=None, insert_site=must_not_insert)
    assert isinstance(result, Forbidden) and result == Forbidden("accounts_sites_create")
    assert result.message == "이 일은 운영 관리자만 한다"


def test_editor_creates_in_the_session_tenant() -> None:
    seen: list[tuple[int, str, str | None]] = []

    def insert(company_id: int, name: str, external_id: str | None) -> Site:
        seen.append((company_id, name, external_id))
        return Site(id="s1", company_id=company_id, external_id=external_id, name=name)

    result = create_site(session("editor"), name="공장", external_id="edk-9", insert_site=insert)
    assert isinstance(result, SiteCreated)
    assert seen == [(COMPANY_ID, "공장", "edk-9")]  # 회사는 세션의 것
