"""우리 JWT 둘(access·refresh): 꼴, 서명, 읽기. 순수하다(django·ninja 0, PyJWT 만 — 계약 다).
꼴은 core/tenancy/session.py 를 따랐다.

로그인(username·비밀번호)이 내준다(user/service/services/login.py). 이 파일은 「언제 내주는가」를 모른다.
EDK 의 RS256 검증(교환)은 user/service/utils/tokens.py 다 — 이름이 겹치니 import 를 헷갈리지 않는다.

★ 비밀은 쿠키 세션과 같은 SESSION_SECRET 이다(새 env 0, 처분 B5). 셋(세션·access·refresh)을 가르는 칸막이는 aud 하나다:
  세션 "esgapi-session", access "esgapi-access", refresh "esgapi-refresh". aud 검사를 빼면 refresh 를 Bearer 로,
  세션 쿠키 값을 access 로 쓸 수 있게 된다(심은 파손 P3 이 문다).
★ 만료는 verify_exp=False 로 풀고 시계 인자로 본다(now >= exp 이면 만료 — 세션과 같은 경계).
★ refresh 토큰의 글자는 저장하지 않는다. 표(user_refresh_tokens)에는 jti 와 계보(fam)만 든다.
무효 조건: access 는 서버가 끊지 못한다 — 계정을 끄거나 비밀번호를 바꿔도 만료(30분)까지 통한다.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal, get_args
from uuid import UUID

import jwt

from esgapi.core.auth.principal import Kind
from esgapi.core.calc.ids import is_company_id

# 길이와 잠금은 코드 상수다(env 아님). 출처: EDK 리뉴얼 백엔드 전달사항 원문:48(5회 실패 10분 잠금)·원문:49(access 30분,
# refresh 7일 rotate)·원문:50(클레임 여섯).
ACCESS_TTL_SECONDS: Final = 30 * 60
REFRESH_TTL_SECONDS: Final = 7 * 24 * 60 * 60
MAX_LOGIN_FAILURES: Final = 5
LOCK_SECONDS: Final = 10 * 60

SIGNING_ALGORITHM: Final = "HS256"
ACCESS_AUDIENCE: Final = "esgapi-access"
REFRESH_AUDIENCE: Final = "esgapi-refresh"
LEVELS: Final = (99, 89, 79)  # 원문:30. 주장에 싣되 권한에는 읽지 않는다
KINDS: tuple[Kind, ...] = get_args(Kind)

TokenRejection = Literal["malformed", "bad_signature", "expired", "wrong_audience"]


@dataclass(frozen=True, slots=True)
class AccessClaims:
    """access 의 주장. EDK 여섯(user_kind·level·company_id·company_is_active·is_initial·role_id)과 sub·jti·시각."""

    user_id: str
    kind: Kind
    level: int
    company_id: int | None  # 고객사 사용자는 늘 int, 운영 관리자는 늘 None
    company_is_active: bool | None  # 운영 관리자는 None
    is_initial: bool
    jti: UUID
    issued_at: datetime
    expires_at: datetime
    role_id: None = None  # 1차 늘 null(role 표는 2차)


@dataclass(frozen=True, slots=True)
class RefreshClaims:
    user_id: str
    company_id: int | None  # 사용자를 다시 읽을 회사 조건(K-B3). 운영 관리자는 None
    jti: UUID
    family: UUID
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AccessActive:
    claims: AccessClaims


@dataclass(frozen=True, slots=True)
class RefreshActive:
    claims: RefreshClaims


@dataclass(frozen=True, slots=True)
class TokenRejected:
    reason: TokenRejection


def _seconds(moment: datetime) -> int:
    return int(moment.timestamp())


def _moment(seconds: int) -> datetime:
    return datetime.fromtimestamp(seconds, tz=UTC)


def new_access_claims(
    *,
    user_id: str,
    kind: Kind,
    level: int,
    company_id: int | None,
    company_is_active: bool | None,
    is_initial: bool,
    jti: UUID,
    now: datetime,
) -> AccessClaims:
    issued = _moment(_seconds(now))
    return AccessClaims(
        user_id=user_id,
        kind=kind,
        level=level,
        company_id=company_id,
        company_is_active=company_is_active,
        is_initial=is_initial,
        jti=jti,
        issued_at=issued,
        expires_at=issued + timedelta(seconds=ACCESS_TTL_SECONDS),
    )


def new_refresh_claims(
    *, user_id: str, company_id: int | None, jti: UUID, family: UUID, now: datetime
) -> RefreshClaims:
    issued = _moment(_seconds(now))
    return RefreshClaims(
        user_id=user_id,
        company_id=company_id,
        jti=jti,
        family=family,
        issued_at=issued,
        expires_at=issued + timedelta(seconds=REFRESH_TTL_SECONDS),
    )


def sign_access(claims: AccessClaims, *, secret: str) -> str:
    return jwt.encode(
        {
            "aud": ACCESS_AUDIENCE,
            "sub": claims.user_id,
            "iat": _seconds(claims.issued_at),
            "exp": _seconds(claims.expires_at),
            "jti": str(claims.jti),
            "user_kind": claims.kind,
            "level": claims.level,
            "company_id": claims.company_id,
            "company_is_active": claims.company_is_active,
            "is_initial": claims.is_initial,
            "role_id": claims.role_id,
        },
        secret,
        algorithm=SIGNING_ALGORITHM,
    )


def sign_refresh(claims: RefreshClaims, *, secret: str) -> str:
    return jwt.encode(
        {
            "aud": REFRESH_AUDIENCE,
            "sub": claims.user_id,
            "iat": _seconds(claims.issued_at),
            "exp": _seconds(claims.expires_at),
            "jti": str(claims.jti),
            "fam": str(claims.family),
            "company_id": claims.company_id,
        },
        secret,
        algorithm=SIGNING_ALGORITHM,
    )


ACCESS_REQUIRED: Final = (
    "aud",
    "sub",
    "iat",
    "exp",
    "jti",
    "user_kind",
    "level",
    "company_id",
    "company_is_active",
    "is_initial",
    "role_id",
)
REFRESH_REQUIRED: Final = ("aud", "sub", "iat", "exp", "jti", "fam", "company_id")


def _decode(token: str, *, secret: str, audience: str, required: tuple[str, ...]) -> dict[str, object] | TokenRejected:
    try:
        payload: dict[str, object] = jwt.decode(
            token,
            key=secret,
            algorithms=[SIGNING_ALGORITHM],
            audience=audience,
            # 만료는 부르는 쪽의 시계로 본다. PyJWT 의 require 는 값이 None 인 칸을 「없음」으로 보므로 늘 값이 있는
            # 다섯만 맡기고, null 이 될 수 있는 칸(company_id·company_is_active·role_id)은 아래에서 칸이 있는지 본다.
            # iat 도 PyJWT 에 맡기지 않는다: PyJWT 는 iat 를 벽시계와 견주어(미래면 ImmatureSignature) 주입한 시계와
            # 어긋난다(K2a 검증 권고 1). 우리가 서명한 토큰만 여기 오고, 끝은 exp 를 부르는 쪽의 시계로 본다.
            options={"require": ["aud", "sub", "iat", "exp", "jti"], "verify_exp": False, "verify_iat": False},
        )
    except jwt.InvalidSignatureError:
        return TokenRejected("bad_signature")
    except jwt.InvalidAudienceError:
        return TokenRejected("wrong_audience")
    except jwt.InvalidTokenError:
        return TokenRejected("malformed")
    if any(name not in payload for name in required):
        return TokenRejected("malformed")
    return payload


def _uuid(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _user_id(value: object) -> str | None:
    return value if isinstance(value, str) and value.isdecimal() and value[0] != "0" else None


def _kind(value: object) -> Kind | None:
    if value == "admin":
        return "admin"
    if value == "service":
        return "service"
    return None


def read_access(token: str, *, secret: str, now: datetime) -> AccessActive | TokenRejected:
    payload = _decode(token, secret=secret, audience=ACCESS_AUDIENCE, required=ACCESS_REQUIRED)
    if isinstance(payload, TokenRejected):
        return payload
    user_id, kind, level = _user_id(payload["sub"]), _kind(payload["user_kind"]), _int(payload["level"])
    company_id, company_is_active = payload["company_id"], payload["company_is_active"]
    is_initial, jti = payload["is_initial"], _uuid(payload["jti"])
    issued, expires = _int(payload["iat"]), _int(payload["exp"])
    if (
        user_id is None
        or kind is None
        or level not in LEVELS
        or not isinstance(is_initial, bool)
        or payload["role_id"] is not None
        or jti is None
        or issued is None
        or expires is None
    ):
        return TokenRejected("malformed")
    # 짝: 고객사 사용자 ⇔ 회사 있음·회사 활성 여부 있음, 운영 관리자 ⇔ 둘 다 null(P8)
    if kind == "service" and is_company_id(company_id) and isinstance(company_is_active, bool):
        company: tuple[int | None, bool | None] = (company_id, company_is_active)
    elif kind == "admin" and company_id is None and company_is_active is None:
        company = (None, None)
    else:
        return TokenRejected("malformed")
    claims = AccessClaims(
        user_id=user_id,
        kind=kind,
        level=level,
        company_id=company[0],
        company_is_active=company[1],
        is_initial=is_initial,
        jti=jti,
        issued_at=_moment(issued),
        expires_at=_moment(expires),
    )
    if now >= claims.expires_at:
        return TokenRejected("expired")
    return AccessActive(claims)


def read_refresh(
    token: str, *, secret: str, now: datetime, allow_expired: bool = False
) -> RefreshActive | TokenRejected:
    """refresh 를 읽는다. allow_expired 는 로그아웃(revoke)만 쓴다 — 지난 토큰으로도 그 계보를 끊을 수 있게."""
    payload = _decode(token, secret=secret, audience=REFRESH_AUDIENCE, required=REFRESH_REQUIRED)
    if isinstance(payload, TokenRejected):
        return payload
    user_id, raw_company = _user_id(payload["sub"]), payload["company_id"]
    jti, family = _uuid(payload["jti"]), _uuid(payload["fam"])
    issued, expires = _int(payload["iat"]), _int(payload["exp"])
    if user_id is None or jti is None or family is None or issued is None or expires is None:
        return TokenRejected("malformed")
    if is_company_id(raw_company):
        company_id: int | None = raw_company
    elif raw_company is None:
        company_id = None
    else:
        return TokenRejected("malformed")
    claims = RefreshClaims(
        user_id=user_id,
        company_id=company_id,
        jti=jti,
        family=family,
        issued_at=_moment(issued),
        expires_at=_moment(expires),
    )
    if not allow_expired and now >= claims.expires_at:
        return TokenRejected("expired")
    return RefreshActive(claims)
