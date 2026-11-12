"""사업장의 권한 함수 둘이 권한 표(core/permissions.py)를 읽는다. 순수 층."""

import pytest

from esgapi.core.permissions import OPERATION_POLICY, OPERATOR
from esgapi.organization.service.permissions.organization import can_create_site, can_view_sites


def test_the_values_are_what_they_were() -> None:
    """사업장 동작은 고객사 사용자의 일이다(역할 둘 — 사용자 결정 2026-10-15 14:46). 운영 관리자는 못 한다."""
    assert {kind: can_view_sites(kind) for kind in ("service", "admin")} == {"service": True, "admin": False}
    assert {kind: can_create_site(kind) for kind in ("service", "admin")} == {"service": True, "admin": False}


def test_both_read_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(OPERATION_POLICY, "accounts_sites_list", OPERATOR)
    assert (can_view_sites("service"), can_view_sites("admin")) == (False, True)
    monkeypatch.setitem(OPERATION_POLICY, "accounts_sites_create", OPERATOR)
    assert (can_create_site("service"), can_create_site("admin")) == (False, True)
