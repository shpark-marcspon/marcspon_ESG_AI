"""로그인·잠금·토큰 짝의 규칙과 갈래. 순수하다(표준 라이브러리만 — 계약 다). DB 도 틀도 없이 돈다.

잠금(원문:48 — 5회 실패 10분): 다섯째 실패에 잠그고, 잠긴 동안은 비밀번호를 보지 않는다. 잠김 판정은 is_locked 하나다
(같은 초 = 아직 잠김, K-B1). 로그인·비밀번호 바꾸기가 부르고, K2c 의 UserOut.isLocked 도 이것을 부른다.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from esgapi.core.auth.principal import Kind
from esgapi.core.auth.tokens import LOCK_SECONDS, MAX_LOGIN_FAILURES


def is_locked(login_expiry_at: datetime | None, now: datetime) -> bool:
    """잠겼는가(사용자 행의 login_expiry_at 을 넘긴다). 그 칸이 있고 지금이 그 시각 이전이거나 같으면 잠김이다
    (같은 초 = 잠김, K-B1). 행 대신 칸을 받는 까닭: django-types 의 칸 타입이 Protocol 과 맞지 않는다."""
    return login_expiry_at is not None and now <= login_expiry_at


@dataclass(frozen=True)
class LockState:
    login_failed_count: int
    login_expiry_at: datetime | None


def after_failure(state: LockState, now: datetime) -> LockState:
    """틀린 비밀번호 한 번 뒤의 셈. 잠금이 지났으면 셈을 0 으로 보고 잇는다. 다섯째 실패에 잠근다."""
    base = 0 if state.login_expiry_at is not None and now > state.login_expiry_at else state.login_failed_count
    count = base + 1
    return LockState(count, now + timedelta(seconds=LOCK_SECONDS) if count >= MAX_LOGIN_FAILURES else None)


@dataclass(frozen=True)
class TokenPair:
    access: str
    refresh: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    is_initial: bool
    kind: Kind


LoginRejection = Literal["invalid_credentials", "account_locked"]


@dataclass(frozen=True)
class LoginOk:
    pair: TokenPair


@dataclass(frozen=True)
class LoginRejected:
    reason: LoginRejection


RefreshRejection = Literal["unknown", "revoked", "reused", "expired", "inactive"]


@dataclass(frozen=True)
class RefreshOk:
    pair: TokenPair


@dataclass(frozen=True)
class RefreshRejected:
    reason: RefreshRejection


@dataclass(frozen=True)
class Revoked:
    """그 계보를 끊었다(이미 끊겼어도 같다 — 멱등)."""


@dataclass(frozen=True)
class AttemptRecorded:
    """비밀번호 확인의 결과를 적었다(맞음이면 셈 0, 틀림이면 셈 +1)."""


@dataclass(frozen=True)
class AttemptLocked:
    """블록 안에서 다시 보니 잠겨 있었다(그 사이 다른 요청이 잠갔다 — K-B2). 아무것도 바꾸지 않았다."""


@dataclass(frozen=True)
class AccountGone:
    """그 사용자가 없거나 꺼졌다."""


PasswordChangeRejection = Literal[
    "account_locked", "current_password_mismatch", "password_rejected", "user_unavailable"
]


@dataclass(frozen=True)
class PasswordChangeRejected:
    reason: PasswordChangeRejection
    messages: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class PasswordRejected:
    """비밀번호 검사기가 거절했다. messages 는 검사기의 사람용 문장이다(비밀번호 글자는 싣지 않는다)."""

    messages: tuple[str, ...]


@dataclass(frozen=True)
class UsernameTaken:
    """그 자리(운영 관리자는 전역, 고객사 사용자는 그 회사 안)에 같은 username 이 있다."""


@dataclass(frozen=True)
class UserNotFound:
    """그 자리에 그 사용자가 없다."""


@dataclass(frozen=True)
class UserCreated:
    user_id: int


@dataclass(frozen=True)
class PasswordReset:
    user_id: int


@dataclass(frozen=True)
class UserUpdated:
    user_id: int
