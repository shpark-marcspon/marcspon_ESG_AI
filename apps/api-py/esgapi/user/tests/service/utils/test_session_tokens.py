"""우리 세션의 서명과 읽기. 순수 층: DB 없음."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from esgapi.core.tenancy.session import (
    SESSION_ALGORITHM,
    SESSION_AUDIENCE,
    Session,
    SessionAbsent,
    SessionActive,
    SessionRejected,
    read_session,
    sign_session,
)
from esgapi.user.service.utils.tokens import TokenRejected, load_public_key, verify_edk_token
from tests.support import keys, tokens

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
SESSION = Session(
    user_id="user-1", tenant_id="tenant-a", company_id=7, role="editor", expires_at=NOW + timedelta(minutes=10)
)
SECRET = keys.SESSION_SECRET


def test_round_trip() -> None:
    cookie = sign_session(SESSION, secret=SECRET)
    assert read_session(cookie, secret=SECRET, now=NOW) == SessionActive(SESSION)


def test_no_cookie_is_absent_not_rejected() -> None:
    assert read_session(None, secret=SECRET, now=NOW) == SessionAbsent()
    assert read_session("", secret=SECRET, now=NOW) == SessionAbsent()


def test_expired_session_is_rejected_with_its_reason() -> None:
    cookie = sign_session(SESSION, secret=SECRET)
    assert read_session(cookie, secret=SECRET, now=SESSION.expires_at) == SessionRejected("expired")


def test_session_signed_with_another_secret_is_rejected() -> None:
    cookie = sign_session(SESSION, secret="another-secret-0123456789abcdef-0123456789")
    assert read_session(cookie, secret=SECRET, now=NOW) == SessionRejected("bad_signature")


def test_garbage_cookie_is_malformed() -> None:
    assert read_session("garbage", secret=SECRET, now=NOW) == SessionRejected("malformed")


def test_edk_token_is_not_a_session() -> None:
    """EDK 토큰을 쿠키 자리에 넣어도 세션이 되지 않는다(알고리즘·키·aud 가 다르다)."""
    assert read_session(tokens.edk_token(), secret=SECRET, now=NOW) == SessionRejected("malformed")


def test_our_session_is_not_an_edk_token() -> None:
    """우리 세션을 교환에 내도 통하지 않는다."""
    cookie = sign_session(SESSION, secret=SECRET)
    result = verify_edk_token(
        cookie, public_key=load_public_key(keys.EDK_PUBLIC_PEM), audience=keys.AUDIENCE, issuer=keys.ISSUER
    )
    assert result == TokenRejected("bad_algorithm")


# ── 회사 칸(K1u-a) ────────────────────────────────────────────────────

MISSING = object()  # 「그 칸이 없다」의 표지


def cookie_with_company(company_id: object) -> str:
    """서명은 맞고 회사 칸만 다른 쿠키. sign_session 과 같은 주장을 손으로 실어 서명한다."""
    payload: dict[str, object] = {
        "aud": SESSION_AUDIENCE,
        "sub": SESSION.user_id,
        "tenant_id": SESSION.tenant_id,
        "role": SESSION.role,
        "exp": int(SESSION.expires_at.timestamp()),
    }
    if company_id is not MISSING:
        payload["company_id"] = company_id
    return jwt.encode(payload, SECRET, algorithm=SESSION_ALGORITHM)


def test_the_read_session_carries_the_company_that_was_signed() -> None:
    state = read_session(sign_session(SESSION, secret=SECRET), secret=SECRET, now=NOW)
    assert isinstance(state, SessionActive)
    assert state.session.company_id == SESSION.company_id == 7
    assert read_session(cookie_with_company(7), secret=SECRET, now=NOW) == SessionActive(
        SESSION
    )  # 손으로 만든 꼴도 맞다


@pytest.mark.parametrize("company_id", [0, -1, True, "1", MISSING], ids=["zero", "negative", "bool", "text", "missing"])
def test_a_company_id_out_of_form_is_malformed(company_id: object) -> None:
    assert read_session(cookie_with_company(company_id), secret=SECRET, now=NOW) == SessionRejected("malformed")
