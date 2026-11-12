"""EDK 토큰의 검증. 키 쌍은 테스트가 만든다(tests/support/keys.py). 순수 층: DB 없음.

★ 이 파일이 재는 것: 검증 방법(키·알고리즘·aud·iss)이 토큰이 아니라 설정에서만 온다는 것.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from jwt.algorithms import RSAAlgorithm

from esgapi.user.service.utils.tokens import (
    EDK_ALGORITHMS,
    TokenOk,
    TokenRejected,
    TokenResult,
    claims_from_payload,
    load_public_key,
    verify_edk_token,
)
from tests.support import keys, tokens

PUBLIC_KEY = load_public_key(keys.EDK_PUBLIC_PEM)


def verify(token: str) -> TokenResult:
    return verify_edk_token(token, public_key=PUBLIC_KEY, audience=keys.AUDIENCE, issuer=keys.ISSUER)


def test_valid_token_is_ok() -> None:
    result = verify(tokens.edk_token())
    assert isinstance(result, TokenOk)
    assert (result.claims.external_id, result.claims.tenant_id, result.claims.role) == (
        "edk-user-1",
        "tenant-a",
        "editor",
    )
    assert result.claims.issuer == keys.ISSUER


def test_expired_token_is_rejected() -> None:
    assert verify(tokens.edk_token(exp=int(time.time()) - 1)) == TokenRejected("expired")


def test_token_signed_with_another_key_is_rejected() -> None:
    assert verify(tokens.edk_token(key=keys.OTHER_KEY)) == TokenRejected("bad_signature")


def test_wrong_audience_is_rejected() -> None:
    assert verify(tokens.edk_token(aud="some-other-service")) == TokenRejected("wrong_audience")


def test_wrong_issuer_is_rejected() -> None:
    assert verify(tokens.edk_token(iss="https://evil.test")) == TokenRejected("wrong_issuer")


def test_alg_none_is_rejected() -> None:
    assert verify(tokens.alg_none_token()) == TokenRejected("bad_algorithm")


def test_swap_public_key_as_hs256_secret_is_rejected() -> None:
    """바꿔치기: EDK 의 공개키(누구나 아는 값)를 HS256 의 비밀로 써서 서명하고 헤더에 HS256 을 적는다."""
    pem = keys.EDK_PUBLIC_PEM.encode()
    der = PUBLIC_KEY.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    for secret in (pem, pem.strip(), der):
        assert verify(tokens.hs256_token(secret)) == TokenRejected("bad_algorithm")


def test_attacker_key_in_jwk_header_is_ignored() -> None:
    """공격자가 자기 키로 서명하고 그 공개키를 헤더(jwk)에 동봉한다. 헤더의 키로 검증하면 통하는 토큰이다."""
    attacker_jwk = RSAAlgorithm.to_jwk(keys.OTHER_KEY.public_key(), as_dict=True)
    token = tokens.edk_token(
        key=keys.OTHER_KEY, headers={"jwk": attacker_jwk, "kid": "attacker", "jku": "https://evil.test/jwks"}
    )
    assert jwt.get_unverified_header(token)["jwk"] == attacker_jwk  # 정말 동봉됐다
    assert verify(token) == TokenRejected("bad_signature")  # 설정의 키로만 검증했다


def test_only_rs256_is_allowed() -> None:
    assert EDK_ALGORITHMS == ("RS256",)


def test_missing_required_claims_are_rejected() -> None:
    assert verify(tokens.edk_token(exp=None)) == TokenRejected("bad_claims")
    assert verify(tokens.edk_token(sub=None)) == TokenRejected("bad_claims")
    assert verify(tokens.edk_token(aud=None)) == TokenRejected("bad_claims")
    assert verify(tokens.edk_token(tenant_id=None)) == TokenRejected("bad_claims")
    assert verify(tokens.edk_token(role="owner")) == TokenRejected("bad_claims")


def test_garbage_is_malformed() -> None:
    assert verify("not-a-token") == TokenRejected("malformed")
    assert verify("") == TokenRejected("malformed")


# 주장의 길이 상한은 표의 칸 길이다(처분 4): sub → users.username(150), name → users.name(20). iss 는 옛 200 그대로.
LIMITS: dict[str, int] = {"sub": 150, "name": 20, "iss": 200}


@pytest.mark.parametrize("key", sorted(LIMITS))
def test_claim_lengths_stop_at_the_table_columns(key: str) -> None:
    payload: dict[str, object] = {
        "iss": keys.ISSUER,
        "sub": "u1",
        "tenant_id": "tenant-a",
        "role": "editor",
        "name": "김",
    }
    at_limit = claims_from_payload({**payload, key: "가" * LIMITS[key]})
    assert isinstance(at_limit, TokenOk)
    assert claims_from_payload({**payload, key: "가" * (LIMITS[key] + 1)}) == TokenRejected("bad_claims")
