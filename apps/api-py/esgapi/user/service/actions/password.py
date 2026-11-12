"""비밀번호 바꾸기와 초기화: users 와 user_refresh_tokens 두 표에 쓴다 → `@transaction.atomic` 함수
(E1b 의 규칙, 원문:172).

차례(처분 B9 — 바꾸기의 현재 비밀번호 확인은 로그인과 같은 잠금 규칙):
  change_password   대상 읽기 → 잠김이면 401(비밀번호를 보지 않음) → 현재 비밀번호 확인(블록 밖) → 셈 적기(한 표 블록,
                    services.login.record_password_attempt — 로그인과 같은 함수) → 검사기 → 해시(블록 밖) →
                    apply_new_password(두 표 블록) → 새 계보로 새 짝
  reset_password    부트스트랩 명령 reset_password(actor_kind="admin")와 K2c 의 HTTP 초기화가 부른다. 첫 줄이 권한.
                    검사기·해시는 앞에서(services.user.prepare_reset·prepare_customer_reset) — 이 블록은
                    해시 값만 받는다.
행 잠금은 Selector 를 부른다(select_for_update 는 user/service/selectors 에만).
거절은 값으로 돌려준다(블록 안에서 던지지 않는다 — K-B4).
"""

from datetime import datetime

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction

from esgapi.core.auth.principal import Kind
from esgapi.user.models import RefreshToken
from esgapi.user.service.permissions.user import Forbidden, can_manage_customer_users, is_resettable
from esgapi.user.service.selectors import user as selectors
from esgapi.user.service.services import login as services
from esgapi.user.service.services.user import password_problems
from esgapi.user.service.utils.login import (
    AccountGone,
    AttemptLocked,
    PasswordChangeRejected,
    PasswordReset,
    TokenPair,
    UserNotFound,
    is_locked,
)


@transaction.atomic
def apply_new_password(*, company_id: int | None, user_id: int, password_hash: str, now: datetime) -> bool:
    """새 해시를 싣고 is_initial 을 끄고 그 사용자의 refresh 계보 전부를 끊는다. 대상이 없으면 False(아무것도 안 씀)."""
    row = selectors.lock_account(company_id, user_id)
    if row is None:
        return False
    row.password, row.is_initial = password_hash, False
    row.save(update_fields=["password", "is_initial"])
    RefreshToken.of_user(row.pk).filter(revoked_at__isnull=True).update(revoked_at=now)
    return True


@transaction.atomic
def reset_password(
    *,
    actor_kind: Kind,
    company_id: int | None,
    user_id: int,
    password_hash: str,
    now: datetime,
    actor_user_id: int | None = None,
) -> PasswordReset | UserNotFound | Forbidden:
    """초기화: 새 해시, is_initial 참, 셈 0, 잠금 풀림, 그 사용자의 refresh 계보 전부 끊음. 운영 관리자만(첫 줄 — K2c).
    company_id 가 None 이면 운영 관리자 갈래(부르는 자리 = 명령 하나 — is_resettable 를 묻지 않는다). 회사가 있으면
    대상은 그 회사의 고객사 사용자뿐이다(is_resettable). 남의 회사 id 면 UserNotFound(행 0 변화)."""
    if not can_manage_customer_users(actor_kind):
        return Forbidden("user_password_reset")
    row = selectors.lock_account(company_id, user_id)
    # 교환이 만든 행(비밀번호를 쓸 수 없음 — EDK 사용자)은 초기화하지 않는다: 비밀번호 로그인이 열리지 않게(D5)
    if row is None or (company_id is not None and not is_resettable(row.kind)) or not row.has_usable_password():
        return UserNotFound()
    row.password, row.is_initial = password_hash, True
    row.login_failed_count, row.login_expiry_at = 0, None
    row.save(update_fields=["password", "is_initial", "login_failed_count", "login_expiry_at"])
    RefreshToken.of_user(row.pk).filter(revoked_at__isnull=True).update(revoked_at=now)
    # 감사 줄은 이 블록의 세이브포인트다(record_event 는 던지지 않는다 — K-B4). 명령이면 행위자 command(개정 1 B3)
    kind, who = services.audit_actor(actor_kind, actor_user_id)
    services.note(
        "password_reset", row, now=now, actor_user_id=actor_user_id, audit_actor_kind=kind, audit_actor_user_id=who
    )
    return PasswordReset(row.pk)


def change_password(
    *, company_id: int | None, user_id: int, current: str, new: str, now: datetime
) -> TokenPair | PasswordChangeRejected:
    """첫 로그인(is_initial) 때와 그 뒤의 비밀번호 바꾸기. 성공하면 새 계보의 새 짝(isInitial 거짓)."""
    user = selectors.account(company_id, user_id)
    if user is None or not user.is_active:
        return PasswordChangeRejected("user_unavailable")
    if is_locked(user.login_expiry_at, now):
        return PasswordChangeRejected("account_locked")
    ok = check_password(current, user.password)
    attempt = services.record_password_attempt(company_id=company_id, user_id=user_id, ok=ok, now=now)
    if isinstance(attempt, AttemptLocked):
        return PasswordChangeRejected("account_locked")
    if isinstance(attempt, AccountGone):
        return PasswordChangeRejected("user_unavailable")
    if not ok:
        return PasswordChangeRejected("current_password_mismatch")
    rejected = password_problems(new)
    if rejected is not None:
        return PasswordChangeRejected("password_rejected", rejected.messages)
    if new == current:
        return PasswordChangeRejected("password_rejected", ("새 비밀번호가 지금 비밀번호와 같다",))
    if not apply_new_password(company_id=company_id, user_id=user_id, password_hash=make_password(new), now=now):
        return PasswordChangeRejected("user_unavailable")
    fresh = selectors.account(company_id, user_id)
    if fresh is None:
        return PasswordChangeRejected("user_unavailable")
    services.note("password_changed", fresh, now=now)  # 행위자 = 대상 = 본인
    return services.issue_pair(fresh, company_is_active=services.company_is_active_of(fresh), now=now)
