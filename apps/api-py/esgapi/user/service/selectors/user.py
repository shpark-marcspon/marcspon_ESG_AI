"""읽기: 로그인·토큰 잇기가 읽는 사용자와 refresh 행. Django ORM 을 쓴다. 쓰지 않는다
(행 잠금은 여기에만 — 읽기의 끝맺음).

★ 고객사 사용자는 `User.for_company(company_id)` 로만 연다(회사를 넘는 조회 0). 운영 관리자는 이름 붙은 입구 둘
  (`User.admin_by_username`·`User.admin_by_id` — 몸에 kind="admin"·회사 NULL 조건)로만. refresh 행은 RefreshToken 의
  입구(`by_jti`)로. 부르는 자리는 core/tests/isolation/test_static_rules.py 의 USER_ENTRANCES 가 지킨다.
★ 행 잠금(select_for_update)은 이 파일에만 둔다(core/tests/test_selector_scope.py).
★ refresh 행의 user 를 따라 사용자를 읽지 않는다(K-B3): 사용자는 부르는 쪽이 넘긴 회사 조건으로 따로 읽는다.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db.models import Q, QuerySet

from esgapi.core.auth.principal import Kind
from esgapi.user.models import RefreshToken, User
from esgapi.user.service.permissions.user import Forbidden, can_manage_customer_users


def find_customer(company_id: int, username: str) -> User | None:
    """그 회사의 고객사 사용자(kind service) 하나. 남의 회사의 같은 username 은 보지 않는다."""
    return User.for_company(company_id).filter(kind="service", username=username).first()


def find_admin(username: str) -> User | None:
    """그 username 의 운영 관리자. 고객사 사용자의 행은 보지 않는다(입구의 조건)."""
    return User.admin_by_username(username).first()


def account(company_id: int | None, user_id: int) -> User | None:
    """id 로 사용자 하나. 회사가 있으면 그 회사의 고객사 사용자에서, 없으면 운영 관리자에서만 찾는다.
    회사의 활성 여부를 같이 읽는다(select_related — 토큰의 company_is_active)."""
    if company_id is None:
        return User.admin_by_id(user_id).first()
    return User.for_company(company_id).select_related("company").filter(pk=user_id, kind="service").first()


def lock_account(company_id: int | None, user_id: int) -> User | None:
    """그 사용자 행을 잠가 다시 읽는다(셈·잠금·비밀번호를 쓰기 전에 — 블록 안에서 부른다)."""
    if company_id is None:
        return User.admin_by_id(user_id).select_for_update().first()
    return User.for_company(company_id).select_for_update().filter(pk=user_id, kind="service").first()


def names_of(company_id: int, customer_ids: set[int], operator_ids: set[int]) -> dict[int, tuple[str, str]]:
    """감사 기록 쪽의 사람 id → (아이디, 이름) — 읽을 때의 지금 값(AU1a — AD-05). 고객사 사용자는 고른 회사 안에서만
    푼다(남의 회사 id 는 빠진다). 운영 관리자는 이름 붙은 입구로 id 하나마다 한 번(1차 운영 관리자는 몇 명 — 늘면
    user 밴드가 입구를 더한다). 쿼리 = 고객사 0~1 + 고유 운영 관리자 수."""
    names: dict[int, tuple[str, str]] = {}
    if customer_ids:
        for row in _customers(company_id, customer_ids):
            names[row.pk] = (row.username, row.name)
    for user_id in sorted(operator_ids):
        admin = User.admin_by_id(user_id).first()
        if admin is not None:
            names[admin.pk] = (admin.username, admin.name)
    return names


def _customers(company_id: int, ids: set[int]) -> QuerySet[User]:
    """그 회사의 고객사 사용자(kind service) 가운데 그 id 들. 남의 회사 id 는 빠진다."""
    return User.for_company(company_id).filter(pk__in=ids, kind="service")


def people_of(company_id: int, ids: set[int]) -> dict[int, tuple[str, str]]:
    """회사 업무 기록(실행·검토)에 남은 사람 id → (아이디, 이름) — 읽을 때의 지금 값. 그 회사의 고객사 사용자(kind
    service — 남의 회사 고객사 id 는 빠진다)와 운영 관리자(이름 붙은 입구 — kind admin, 작업 회사로 일한 운영 관리자.
    결정 MARC-ENT-374)를 한 조회로 푼다(두 조건의 OR). 넘긴 id 말고는 풀지 않는다. 쿼리 = 1(id 가 없으면 0) — 그린워싱
    목록 줄의 쿼리 수 k 를 그대로 둔다(밴드 OP1, 검증 37 의 (가))."""
    if not ids:
        return {}
    found = _customers(company_id, ids)
    for user_id in sorted(ids):
        found = found | User.admin_by_id(user_id)
    return {row.pk: (row.username, row.name) for row in found}


def lock_refresh(jti: UUID) -> RefreshToken | None:
    """그 refresh 행을 잠가 읽는다(rotate 와 재사용 판정 — 블록 안에서 부른다)."""
    return RefreshToken.by_jti(jti).select_for_update().first()


# ── 고객사 사용자 목록(K2c — 운영 관리자 전용 GET /users) ─────────────────


@dataclass(frozen=True)
class CustomerUserPage:
    """그 회사의 고객사 사용자 한 쪽(id 오름)과 전체 수."""

    rows: list[User]
    count: int


UserStatus = Literal["active", "initial", "locked", "inactive"]


def _status_filter(status: UserStatus, now: datetime) -> Q:
    """상태 넷의 뜻(웹 statusOf 의 앞섬 — 사용 중지 > 잠김 > 초기화 대기 > 사용 중). 잠김은 로그인과 같은 판정
    (utils/login.py 의 is_locked — 같은 초도 잠김)."""
    locked = Q(login_expiry_at__isnull=False, login_expiry_at__gte=now)
    if status == "inactive":
        return Q(is_active=False)
    if status == "locked":
        return Q(is_active=True) & locked
    if status == "initial":
        return Q(is_active=True, is_initial=True) & ~locked
    return Q(is_active=True, is_initial=False) & ~locked


def list_customer_users(
    *,
    actor_kind: Kind,
    company_id: int,
    limit: int,
    offset: int,
    now: datetime,
    q: str | None = None,
    status: UserStatus | None = None,
) -> CustomerUserPage | Forbidden:
    """그 회사의 고객사 사용자(kind service — 비활성 포함), id 오름. 운영 관리자 행(회사 NULL)은 조회에 없다.
    교환이 만든 행(비밀번호를 쓸 수 없음 — EDK 사용자)은 뺀다(처분 ⑨ — 초기화·수정이 그 행에 404 인 것과 같은 규칙).
    q 는 아이디·이름의 부분 일치(대소문자 무시), status 는 상태 넷 하나. count 는 거른 뒤의 수.
    권한은 첫 줄에서 본다(막히면 아무것도 안 읽는다). 회사는 부르는 쪽(경로)이 고른 id 다 — 회사를 넘는 조회 0."""
    if not can_manage_customer_users(actor_kind):
        return Forbidden("user_list")
    rows = (
        User.for_company(company_id)
        .select_related("company")
        .filter(kind="service")
        .exclude(password__startswith=UNUSABLE_PASSWORD_PREFIX)
    )
    if q is not None:
        rows = rows.filter(Q(username__icontains=q) | Q(name__icontains=q))
    if status is not None:
        rows = rows.filter(_status_filter(status, now))
    rows = rows.order_by("id")
    return CustomerUserPage(rows=list(rows[offset : offset + limit]), count=rows.count())
