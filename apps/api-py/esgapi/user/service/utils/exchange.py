"""교환의 갈래와 판정. 「그 테넌트·사용자를 받아도 되는가」의 답을 갈래로 낸다. 순수하다(표준 라이브러리만).

★ 없음과 실패를 None 이나 bool 로 접지 않는다. 갈래마다 이름이 있고, api 층이 갈래마다 다른 응답을 낸다.
"""

from dataclasses import dataclass
from typing import Literal

from esgapi.core.tenancy.session import Session
from esgapi.user.service.utils.entities import Tenant, User
from esgapi.user.service.utils.tokens import EdkClaims, TokenRejection

# ── 테넌트·사용자를 찾아본 결과 ───────────────────────────────────────


@dataclass(frozen=True)
class TenantRegistered:
    tenant: Tenant


@dataclass(frozen=True)
class TenantUnknown:
    """등록되지 않았거나 쓸 수 없는(비활성) 회사. 교환은 회사를 만들지 않는다."""


TenantLookup = TenantRegistered | TenantUnknown


@dataclass(frozen=True)
class UserSaved:
    """그 회사의 사용자를 찾아 덮어썼거나 만들었다.

    같은 sub 가 다른 회사에 있어도 그 회사의 별개 사용자다(처분 2 ㉡).
    """

    user: User


@dataclass(frozen=True)
class UserInactive:
    """그 회사에 그 사용자가 있지만 꺼져 있다(is_active 거짓). 덮어쓰지 않았다(CA·D3)."""


@dataclass(frozen=True)
class UsernameConflict:
    """그 회사의 같은 username 이 비밀번호 사용자(쓸 수 있는 비밀번호가 있는 행)다. 덮어쓰지 않았다(CA·D5)."""


UserLookup = UserSaved | UserInactive | UsernameConflict


# ── 교환의 결과 ───────────────────────────────────────────────────────

ExchangeRejection = TokenRejection | Literal["unknown_tenant", "user_inactive", "username_conflict"]


@dataclass(frozen=True)
class ExchangeOk:
    user: User
    tenant: Tenant
    session: Session


@dataclass(frozen=True)
class ExchangeRejected:
    reason: ExchangeRejection


ExchangeResult = ExchangeOk | ExchangeRejected


@dataclass(frozen=True)
class Admitted:
    """이 주장을 들고 온 사람을 이 테넌트의 사용자로 받아도 된다."""

    claims: EdkClaims
    tenant: Tenant


def admit(claims: EdkClaims, tenant: TenantLookup) -> Admitted | ExchangeRejected:
    """서명이 확인된 주장과 테넌트 조회 결과로 「받는다 / 거절한다(까닭)」를 정한다."""
    if isinstance(tenant, TenantUnknown):
        return ExchangeRejected("unknown_tenant")
    return Admitted(claims, tenant.tenant)
