"""고객사 사용자 관리의 권한 규칙(user/service/permissions — K2c). 순수 층: 표(core/permissions.py)를 읽는지 잰다."""

import pytest

from esgapi.core.permissions import CUSTOMER, OPERATION_POLICY, OPERATOR
from esgapi.user.service.permissions.user import (
    USER_ADMIN_OPERATIONS,
    Forbidden,
    can_manage_customer_users,
    is_resettable,
)


def test_only_the_operator_manages_customer_users() -> None:
    assert (can_manage_customer_users("admin"), can_manage_customer_users("service")) == (True, False)


@pytest.mark.parametrize("operation_id", USER_ADMIN_OPERATIONS)
def test_user_permissions_read_the_core_table(monkeypatch: pytest.MonkeyPatch, operation_id: str) -> None:
    """넷 가운데 한 칸만 바꿔도 답이 바뀐다(사본 표 0 — 넷을 다 읽는다)."""
    monkeypatch.setitem(OPERATION_POLICY, operation_id, CUSTOMER)
    assert can_manage_customer_users("admin") is False
    monkeypatch.setitem(OPERATION_POLICY, operation_id, OPERATOR)
    assert can_manage_customer_users("admin") is True  # 분모: 되돌리면 지난다


def test_the_three_operations_are_the_user_admin_cells() -> None:
    # UA1: 수정(user_update)이 넷째 — 이름은 옛 그대로(id 를 바꾸지 않는다)
    assert set(USER_ADMIN_OPERATIONS) == {"user_list", "user_create", "user_password_reset", "user_update"}
    assert {OPERATION_POLICY[op] for op in USER_ADMIN_OPERATIONS} == {OPERATOR}


def test_only_customer_users_are_resettable_over_http() -> None:
    assert (is_resettable("service"), is_resettable("admin"), is_resettable("")) == (True, False, False)


def test_forbidden_names_who_may_do_it() -> None:
    assert Forbidden("user_create").message == "이 일은 운영 관리자만 한다"
