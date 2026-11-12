"""우리 JWT 둘(access·refresh)의 서명과 읽기. 순수 층: DB 없음.

칸막이는 aud 하나다(세션·access·refresh). 만료는 시계 인자로 본다(now >= exp 이면 만료).
core 의 테스트라 업무 모듈을 import 하지 않는다(계약 가).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from esgapi.core.auth.tokens import (
    ACCESS_AUDIENCE,
    ACCESS_TTL_SECONDS,
    LOCK_SECONDS,
    MAX_LOGIN_FAILURES,
    REFRESH_AUDIENCE,
    REFRESH_TTL_SECONDS,
    AccessActive,
    AccessClaims,
    RefreshActive,
    RefreshClaims,
    TokenRejected,
    new_access_claims,
    new_refresh_claims,
    read_access,
    read_refresh,
    sign_access,
    sign_refresh,
)
from esgapi.core.tenancy.session import SESSION_AUDIENCE, new_session, sign_session
from tests.support import keys

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
SECRET = keys.SESSION_SECRET
OTHER_SECRET = "another-secret-0123456789abcdef-0123456789"
JTI = UUID("11111111-1111-4111-8111-111111111111")
FAMILY = UUID("22222222-2222-4222-8222-222222222222")


def customer(**overrides: Any) -> AccessClaims:
    fields: dict[str, Any] = {
        "user_id": "42",
        "kind": "service",
        "level": 79,
        "company_id": 7,
        "company_is_active": True,
        "is_initial": True,
        "jti": JTI,
        "now": NOW,
    }
    return new_access_claims(**(fields | overrides))


def operator() -> AccessClaims:
    return new_access_claims(
        user_id="9", kind="admin", level=99, company_id=None, company_is_active=None, is_initial=False, jti=JTI, now=NOW
    )


def refresh_claims(company_id: int | None = 7) -> RefreshClaims:
    return new_refresh_claims(user_id="42", company_id=company_id, jti=JTI, family=FAMILY, now=NOW)


def access_payload(**overrides: Any) -> dict[str, Any]:
    """멀쩡한 access 의 내용(손으로 짠 것). 바꾸고 싶은 칸만 넘긴다."""
    payload: dict[str, Any] = {
        "aud": ACCESS_AUDIENCE,
        "sub": "42",
        "iat": int(NOW.timestamp()),
        "exp": int(NOW.timestamp()) + ACCESS_TTL_SECONDS,
        "jti": str(JTI),
        "user_kind": "service",
        "level": 79,
        "company_id": 7,
        "company_is_active": True,
        "is_initial": True,
        "role_id": None,
    }
    return payload | overrides


def hand_access(**overrides: Any) -> str:
    return jwt.encode(access_payload(**overrides), SECRET, algorithm="HS256")


# ── 상수 ──────────────────────────────────────────────────────────────


def test_the_lengths_and_the_lock_are_the_agreed_numbers() -> None:
    # 원문:48(5회 실패 10분)·원문:49(access 30분, refresh 7일)
    assert (ACCESS_TTL_SECONDS, REFRESH_TTL_SECONDS, MAX_LOGIN_FAILURES, LOCK_SECONDS) == (1800, 604800, 5, 600)


# ── 서명 → 읽기 ────────────────────────────────────────────────────────


def test_an_access_token_round_trips() -> None:
    claims = customer()
    assert claims.expires_at == NOW + timedelta(seconds=ACCESS_TTL_SECONDS)
    read = read_access(sign_access(claims, secret=SECRET), secret=SECRET, now=NOW)
    assert read == AccessActive(claims)
    assert isinstance(read, AccessActive)
    assert (read.claims.company_id, read.claims.company_is_active, read.claims.role_id) == (7, True, None)


def test_an_operator_access_token_has_no_company() -> None:
    claims = operator()
    read = read_access(sign_access(claims, secret=SECRET), secret=SECRET, now=NOW)
    assert read == AccessActive(claims)
    assert isinstance(read, AccessActive)
    assert (read.claims.kind, read.claims.level, read.claims.company_id, read.claims.company_is_active) == (
        "admin",
        99,
        None,
        None,
    )


@pytest.mark.parametrize("company_id", [7, None], ids=["customer", "operator"])
def test_a_refresh_token_round_trips(company_id: int | None) -> None:
    claims = refresh_claims(company_id)
    assert claims.expires_at == NOW + timedelta(seconds=REFRESH_TTL_SECONDS)
    read = read_refresh(sign_refresh(claims, secret=SECRET), secret=SECRET, now=NOW)
    assert read == RefreshActive(claims)
    assert isinstance(read, RefreshActive)
    assert (read.claims.family, read.claims.company_id, read.claims.jti) == (FAMILY, company_id, JTI)


def test_issued_at_drops_the_fraction_of_a_second() -> None:
    claims = customer(now=NOW + timedelta(microseconds=900_000))
    assert claims.issued_at == NOW


# ── 만료의 경계 ────────────────────────────────────────────────────────


def test_an_access_token_is_active_one_second_before_exp_and_expired_at_exp() -> None:
    claims = customer()
    token = sign_access(claims, secret=SECRET)
    assert isinstance(read_access(token, secret=SECRET, now=claims.expires_at - timedelta(seconds=1)), AccessActive)
    assert read_access(token, secret=SECRET, now=claims.expires_at) == TokenRejected("expired")


def test_a_refresh_token_is_active_one_second_before_exp_and_expired_at_exp() -> None:
    claims = refresh_claims()
    token = sign_refresh(claims, secret=SECRET)
    assert isinstance(read_refresh(token, secret=SECRET, now=claims.expires_at - timedelta(seconds=1)), RefreshActive)
    assert read_refresh(token, secret=SECRET, now=claims.expires_at) == TokenRejected("expired")


def test_tokens_issued_on_a_future_clock_are_read_on_that_clock() -> None:
    """iat 는 주입한 시계로만 본다 — 벽시계보다 앞선 시계로 낸 토큰도 그 시계에서 통한다(K2a 검증 권고 1)."""
    future = datetime(2099, 1, 1, tzinfo=UTC)
    access = customer(now=future)
    assert read_access(sign_access(access, secret=SECRET), secret=SECRET, now=future) == AccessActive(access)
    refresh = new_refresh_claims(user_id="42", company_id=7, jti=JTI, family=FAMILY, now=future)
    assert read_refresh(sign_refresh(refresh, secret=SECRET), secret=SECRET, now=future) == RefreshActive(refresh)
    # 분모: 끝은 여전히 그 시계로 본다
    assert read_access(sign_access(access, secret=SECRET), secret=SECRET, now=access.expires_at) == TokenRejected(
        "expired"
    )


def test_an_expired_refresh_is_read_only_when_expired_is_allowed() -> None:
    """로그아웃(revoke)만 allow_expired 로 지난 refresh 를 읽는다."""
    claims = refresh_claims()
    token = sign_refresh(claims, secret=SECRET)
    later = claims.expires_at + timedelta(days=30)
    assert read_refresh(token, secret=SECRET, now=later) == TokenRejected("expired")
    assert read_refresh(token, secret=SECRET, now=later, allow_expired=True) == RefreshActive(claims)


# ── 서명과 알고리즘 ───────────────────────────────────────────────────


def test_a_token_signed_with_another_secret_is_a_bad_signature() -> None:
    assert read_access(sign_access(customer(), secret=OTHER_SECRET), secret=SECRET, now=NOW) == TokenRejected(
        "bad_signature"
    )
    assert read_refresh(sign_refresh(refresh_claims(), secret=OTHER_SECRET), secret=SECRET, now=NOW) == TokenRejected(
        "bad_signature"
    )


def test_an_unsigned_token_is_rejected() -> None:
    """alg none. HS256 밖의 알고리즘은 PyJWT 가 InvalidAlgorithmError 로 거절한다 → malformed."""
    token = jwt.encode(access_payload(), "", algorithm="none")
    assert read_access(token, secret=SECRET, now=NOW) == TokenRejected("malformed")


def test_an_rs256_token_is_rejected() -> None:
    """남의 키(RS256)로 서명한 것. 알고리즘이 HS256 하나라 받지 않는다 → malformed."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(access_payload(), key, algorithm="RS256")
    assert read_access(token, secret=SECRET, now=NOW) == TokenRejected("malformed")
    assert read_refresh(token, secret=SECRET, now=NOW) == TokenRejected("malformed")


@pytest.mark.parametrize(
    "token",
    [
        "garbage",
        "",
        "a.b.c",
        sign_access(customer(), secret=SECRET)[:-5],
        sign_access(customer(), secret=SECRET).rsplit(".", 1)[0],
    ],
    ids=["garbage", "empty", "three-dots", "truncated", "no-signature"],
)
def test_a_broken_token_is_malformed(token: str) -> None:
    assert read_access(token, secret=SECRET, now=NOW) == TokenRejected("malformed")
    assert read_refresh(token, secret=SECRET, now=NOW) == TokenRejected("malformed")


# ── aud 칸막이(세션·access·refresh) ────────────────────────────────────


def test_an_access_token_is_not_a_refresh() -> None:
    token = sign_access(customer(), secret=SECRET)
    assert read_refresh(token, secret=SECRET, now=NOW) == TokenRejected("wrong_audience")


def test_a_refresh_token_is_not_an_access() -> None:
    token = sign_refresh(refresh_claims(), secret=SECRET)
    assert read_access(token, secret=SECRET, now=NOW) == TokenRejected("wrong_audience")


def test_a_session_cookie_is_not_an_access() -> None:
    """같은 비밀(SESSION_SECRET)로 서명한 쿠키 세션 값. 세션에는 iat·jti 가 없어 PyJWT 가 aud 보다 먼저 필수 칸에서
    거절한다(malformed). 칸을 채운 세션 aud 의 것은 aud 에서 걸린다(wrong_audience) — 칸막이는 aud 다."""
    session = new_session(user_id="42", tenant_id="tenant-a", company_id=7, role="admin", now=NOW, ttl_seconds=600)
    cookie = sign_session(session, secret=SECRET)
    assert read_access(cookie, secret=SECRET, now=NOW) == TokenRejected("malformed")
    assert read_refresh(cookie, secret=SECRET, now=NOW) == TokenRejected("malformed")
    full = hand_access(aud=SESSION_AUDIENCE)
    assert read_access(full, secret=SECRET, now=NOW) == TokenRejected("wrong_audience")


def test_a_hand_built_access_payload_is_read() -> None:
    """분모: 아래의 손으로 짠 토큰들은 한 칸만 틀렸다."""
    assert isinstance(read_access(hand_access(), secret=SECRET, now=NOW), AccessActive)
    assert REFRESH_AUDIENCE != ACCESS_AUDIENCE


# ── 주장의 꼴 → malformed ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "overrides",
    [
        {"level": 88},
        {"level": "79"},
        {"level": True},
        {"company_id": True},
        {"company_id": "1"},
        {"company_id": 0},
        {"company_id": -1},
        {"user_kind": "editor"},
        {"sub": "abc"},
        {"sub": "042"},
        {"jti": "not-a-uuid"},
        {"is_initial": 1},
        {"role_id": 3},
    ],
    ids=[
        "level-88",
        "level-text",
        "level-bool",
        "company-bool",
        "company-text",
        "company-zero",
        "company-negative",
        "kind-unknown",
        "sub-text",
        "sub-leading-zero",
        "jti-not-uuid",
        "initial-int",
        "role-set",
    ],
)
def test_a_bad_claim_shape_is_malformed(overrides: dict[str, Any]) -> None:
    assert read_access(hand_access(**overrides), secret=SECRET, now=NOW) == TokenRejected("malformed")


@pytest.mark.parametrize(
    "overrides",
    [
        {"user_kind": "service", "company_id": None, "company_is_active": None},
        {"user_kind": "service", "company_id": 7, "company_is_active": None},
        {"user_kind": "admin", "company_id": 1, "company_is_active": True},
        {"user_kind": "admin", "company_id": 1, "company_is_active": None},
        {"user_kind": "admin", "company_id": None, "company_is_active": False},
    ],
    ids=[
        "service-without-company",
        "service-without-active",
        "admin-with-company",
        "admin-with-company-only",
        "admin-with-active-only",
    ],
)
def test_kind_and_company_must_pair(overrides: dict[str, Any]) -> None:
    assert read_access(hand_access(**overrides), secret=SECRET, now=NOW) == TokenRejected("malformed")


@pytest.mark.parametrize("missing", ["company_id", "company_is_active", "role_id", "level"])
def test_a_missing_access_claim_is_malformed(missing: str) -> None:
    payload = {k: v for k, v in access_payload().items() if k != missing}
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    assert read_access(token, secret=SECRET, now=NOW) == TokenRejected("malformed")


@pytest.mark.parametrize(
    "overrides",
    [{"company_id": True}, {"company_id": "1"}, {"company_id": 0}, {"fam": "x"}, {"sub": "abc"}],
    ids=["company-bool", "company-text", "company-zero", "family-not-uuid", "sub-text"],
)
def test_a_bad_refresh_claim_shape_is_malformed(overrides: dict[str, Any]) -> None:
    payload: dict[str, Any] = {
        "aud": REFRESH_AUDIENCE,
        "sub": "42",
        "iat": int(NOW.timestamp()),
        "exp": int(NOW.timestamp()) + REFRESH_TTL_SECONDS,
        "jti": str(uuid4()),
        "fam": str(FAMILY),
        "company_id": 7,
    } | overrides
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    assert read_refresh(token, secret=SECRET, now=NOW) == TokenRejected("malformed")
