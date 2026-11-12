"""우리 세션: 꼴, 규칙, 서명과 읽기. 그리고 역할(Role).

순수하다: django·ninja·psycopg 를 import 하지 않는다(PyJWT 만). DB 없이 테스트된다.
core 에 있는 까닭: 테넌트 미들웨어가 세션에서 테넌트를 읽어야 하고, core 는 업무 모듈(user·organization)을 import 하지
않는다. 세션을 **언제 내주는가**(교환)는 user 의 일이다. user 가 여기의 new_session·sign_session 을 부른다.

세션에는 회사가 두 꼴로 실린다(K1u-a): tenant_id = 회사의 subdomain 글자(core 의 표가 아직 이 글자로 가른다 — K1u-b 가
옮긴다), company_id = 회사의 숫자 id(organization·user 의 표가 이것으로 가른다). 둘 다 교환이 같은 회사에서 싣는다.

우리 세션은 우리가 서명한 JWT(HS256, 비밀은 SESSION_SECRET)이고 쿠키에 실린다. 서버에 저장하지 않는다.
Django 의 signing 대신 JWT 를 고른 까닭: 이미 PyJWT 가 있고, 틀을 바꿔도(FastAPI) 이 파일이 그대로 남는다.

★ EDK 토큰과 섞이지 않는다: 알고리즘이 다르고(HS256 대 RS256) 키가 다르고 aud 가 다르다.
  EDK 토큰을 쿠키에 넣어도 세션으로 읽히지 않고, 우리 세션을 교환에 내도 통하지 않는다.
무효 조건: 서버에 세션 목록이 없으므로 로그아웃은 쿠키를 지울 뿐이다. 쿠키를 베껴 둔 쪽은 만료까지 쓸 수 있다.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal, TypeGuard, get_args

import jwt

from esgapi.core.calc.ids import is_company_id

# 사업계획서 3.3 의 역할 셋. admin = 관리자, editor = 담당자, viewer = 열람자.
Role = Literal["admin", "editor", "viewer"]
ROLES: tuple[Role, ...] = get_args(Role)


def is_role(value: object) -> TypeGuard[Role]:
    return isinstance(value, str) and value in ROLES


@dataclass(frozen=True)
class Session:
    """우리 세션의 내용. 쿠키에 서명되어 실린다. 교환 뒤로는 이것만 믿는다(EDK 를 다시 부르지 않는다)."""

    user_id: str
    tenant_id: str
    company_id: int
    role: Role
    expires_at: datetime


def new_session(
    *, user_id: str, tenant_id: str, company_id: int, role: Role, now: datetime, ttl_seconds: int
) -> Session:
    """방금 교환을 마친 사용자의 세션. 테넌트와 역할은 이 순간의 값으로 굳는다.

    무효 조건: EDK 에서 역할이 바뀌거나 사용자가 빠져도, 이 세션은 expires_at 까지 옛 값으로 통한다.
    (그래서 수명을 짧게 둔다. 중간에 끊는 길은 아직 없다.)
    """
    return Session(
        user_id=user_id,
        tenant_id=tenant_id,
        company_id=company_id,
        role=role,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )


def is_expired(session: Session, *, now: datetime) -> bool:
    return now >= session.expires_at


SessionRejection = Literal["malformed", "bad_signature", "expired"]


@dataclass(frozen=True)
class SessionActive:
    session: Session


@dataclass(frozen=True)
class SessionAbsent:
    """쿠키가 없다(로그인한 적이 없거나 로그아웃했다)."""


@dataclass(frozen=True)
class SessionRejected:
    """쿠키는 왔지만 믿을 수 없다. 「없다」와 다르다: 까닭이 있다."""

    reason: SessionRejection


SessionState = SessionActive | SessionAbsent | SessionRejected

SESSION_ALGORITHM: Final = "HS256"
SESSION_AUDIENCE: Final = "esgapi-session"


def sign_session(session: Session, *, secret: str) -> str:
    return jwt.encode(
        {
            "aud": SESSION_AUDIENCE,
            "sub": session.user_id,
            "tenant_id": session.tenant_id,
            "company_id": session.company_id,
            "role": session.role,
            "exp": int(session.expires_at.timestamp()),
        },
        secret,
        algorithm=SESSION_ALGORITHM,
    )


def read_session(cookie: str | None, *, secret: str, now: datetime) -> SessionState:
    if cookie is None or cookie == "":
        return SessionAbsent()
    try:
        payload = jwt.decode(
            cookie,
            key=secret,
            algorithms=[SESSION_ALGORITHM],
            audience=SESSION_AUDIENCE,
            # 만료는 아래에서 is_expired 로 본다. 시계를 인자로 받기 위해서다.
            options={"require": ["exp", "aud", "sub"], "verify_exp": False},
        )
    except jwt.InvalidSignatureError:
        return SessionRejected("bad_signature")
    except jwt.InvalidTokenError:
        return SessionRejected("malformed")

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    company_id = payload.get("company_id")
    role = payload.get("role")
    exp = payload.get("exp")
    if not (isinstance(user_id, str) and isinstance(tenant_id, str) and is_role(role) and isinstance(exp, int)):
        return SessionRejected("malformed")
    # 회사 칸이 없거나 꼴이 틀린(0·음수·bool·글자) 쿠키는 믿지 않는다(K1u-a 전에 내준 쿠키도 여기서 걸린다 — 다시 교환).
    if not is_company_id(company_id):
        return SessionRejected("malformed")
    session = Session(
        user_id=user_id,
        tenant_id=tenant_id,
        company_id=company_id,
        role=role,
        expires_at=datetime.fromtimestamp(exp, UTC),
    )
    if is_expired(session, now=now):
        return SessionRejected("expired")
    return SessionActive(session)
