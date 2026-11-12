"""테스트가 EDK 인 척(또는 공격자인 척) 토큰을 만드는 도구."""

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from tests.support import keys


def claims(**overrides: Any) -> dict[str, Any]:
    """멀쩡한 EDK 토큰의 내용. 바꾸고 싶은 것만 넘긴다. 값이 None 이면 그 칸을 뺀다."""
    payload: dict[str, Any] = {
        "iss": keys.ISSUER,
        "aud": keys.AUDIENCE,
        "sub": "edk-user-1",
        "tenant_id": "tenant-a",
        "role": "editor",
        "name": "김담당",
        "exp": int(time.time()) + 300,
    }
    payload.update(overrides)
    return {k: v for k, v in payload.items() if v is not None}


def edk_token(*, key: RSAPrivateKey = keys.EDK_KEY, headers: dict[str, Any] | None = None, **overrides: Any) -> str:
    """RS256 으로 서명한 토큰. key 를 바꾸면 「다른 키로 서명한」 토큰이 된다."""
    return jwt.encode(claims(**overrides), key, algorithm="RS256", headers=headers)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unsigned(header: dict[str, Any], payload: dict[str, Any]) -> str:
    return _b64(json.dumps(header).encode()) + "." + _b64(json.dumps(payload).encode())


def alg_none_token(**overrides: Any) -> str:
    """서명이 없는 토큰(헤더 alg: none). PyJWT 가 만들어 주지 않아 손으로 잇는다."""
    return _unsigned({"alg": "none", "typ": "JWT"}, claims(**overrides)) + "."


def hs256_token(secret: bytes, **overrides: Any) -> str:
    """바꿔치기: 헤더에 HS256 을 적고 secret 으로 HMAC 서명한다.

    secret 에 EDK 의 「공개키」를 넣으면, 검증하는 쪽이 「설정의 키 + 헤더의 알고리즘」으로 검증할 때 통한다.
    공개키는 누구나 아는 값이므로 누구나 만들 수 있는 토큰이다.
    (PyJWT 는 PEM 을 HMAC 비밀로 쓰는 것을 막아 두어 encode 로는 못 만든다. 그래서 손으로 잇는다.)
    """
    body = _unsigned({"alg": "HS256", "typ": "JWT"}, claims(**overrides))
    signature = hmac.new(secret, body.encode(), hashlib.sha256).digest()
    return body + "." + _b64(signature)
