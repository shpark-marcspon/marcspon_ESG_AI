"""EDK 가 서명한 토큰의 판정. 순수하다: django·ninja·psycopg 를 import 하지 않는다(PyJWT 와 cryptography 만).

★ 검증 방법을 정하는 상수 셋(키·알고리즘·aud)과 발급자(iss)는 토큰이 아니라 우리 쪽에서만 온다.
  - 키: 설정의 공개키(EDK_JWT_PUBLIC_KEY). 토큰 헤더의 jwk·jku·kid·x5c 는 읽지 않는다(읽는 코드가 없다).
  - 알고리즘: 아래 EDK_ALGORITHMS 하나. 토큰 헤더의 alg 는 「이 목록에 있는가」로만 쓰인다.
  - aud, iss: 설정값과 같아야 한다.
  무효 조건: EDK_ALGORITHMS 에 대칭 알고리즘(HS256 등)을 더하면, 공개키(누구나 아는 값)를 비밀로 써서
  서명한 토큰이 통할 길이 열린다. 목록을 늘리지 않는다.

(나중 자리) EDK 가 키를 주소(JWKS)로 내놓으면: 그 주소도 설정에서만 오고, 받아 온 키 가운데 고르는 일만
토큰의 kid 가 한다. 아직 하지 않았다.

우리 세션(쿠키)의 서명과 읽기는 여기가 아니라 core/tenancy/session.py 에 있다.

★ 없음과 실패를 None 이나 bool 로 접지 않는다. 갈래마다 이름이 있고, api 층이 갈래마다 다른 응답을 낸다.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal, TypeGuard

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from esgapi.core.tenancy.session import Role, is_role

# ── EDK 토큰: 내용과 검증의 결과 ──────────────────────────────────────


@dataclass(frozen=True)
class EdkClaims:
    """서명이 확인된 EDK 토큰에서 꺼낸 값. 교환의 입력이다."""

    issuer: str
    external_id: str  # 토큰의 sub
    tenant_id: str
    role: Role
    name: str


TokenRejection = Literal[
    "malformed",  # 토큰의 꼴이 아니다
    "bad_algorithm",  # 헤더의 alg 가 우리가 정한 것(RS256)이 아니다 (none, HS256 바꿔치기 등)
    "bad_signature",  # 우리 설정의 공개키로 서명이 맞지 않는다
    "expired",  # 만료됐다
    "wrong_audience",  # aud 가 우리가 아니다(다른 서비스에게 준 토큰)
    "wrong_issuer",  # iss 가 우리가 믿는 발급자가 아니다
    "bad_claims",  # 서명은 맞지만 필요한 값(sub·tenant_id·role·name)이 없거나 꼴이 틀렸다
]


@dataclass(frozen=True)
class TokenOk:
    claims: EdkClaims


@dataclass(frozen=True)
class TokenRejected:
    reason: TokenRejection


TokenResult = TokenOk | TokenRejected

# 테넌트 ID 의 꼴. TS 뼈대(packages/core 의 TENANT_ID)와 같은 규칙이다: 소문자·숫자·하이픈, 1~63자.
_TENANT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def is_valid_tenant_id(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and _TENANT_ID.fullmatch(value) is not None


def _is_text(value: object, limit: int = 200) -> TypeGuard[str]:
    return isinstance(value, str) and 0 < len(value) <= limit


# 주장의 길이 상한. sub 는 users.username(150), name 은 users.name(20) 에 들어간다(EDK 칸 길이 — 처분 4 ㉠).
# 넘으면 표에 넣기 전에 bad_claims 로 거절한다. iss 는 표에 안 들어가 옛 상한 그대로다.
SUB_MAX: Final = 150
NAME_MAX: Final = 20


def claims_from_payload(payload: Mapping[str, object]) -> TokenResult:
    """서명·만료·aud·iss 가 이미 확인된 토큰의 내용에서 우리가 쓰는 값을 꺼낸다.

    ★ 무효 조건: 이 함수는 서명을 보지 않는다. 검증을 거치지 않은 내용에 부르면 아무 뜻이 없다.
    ★ 주장의 이름(sub·tenant_id·role·name)은 추정이다. 실제 EDK 토큰의 이름은 킥오프 뒤에 정해진다.
    """
    issuer = payload.get("iss")
    external_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    role = payload.get("role")
    name = payload.get("name")
    if not (_is_text(issuer) and _is_text(external_id, SUB_MAX) and _is_text(name, NAME_MAX)):
        return TokenRejected("bad_claims")
    if not is_valid_tenant_id(tenant_id) or not is_role(role):
        return TokenRejected("bad_claims")
    return TokenOk(EdkClaims(issuer=issuer, external_id=external_id, tenant_id=tenant_id, role=role, name=name))


# ── EDK 토큰: 검증 ────────────────────────────────────────────────────

EDK_ALGORITHMS: Final = ("RS256",)


class BadPublicKeyError(Exception):
    pass


def load_public_key(pem: str) -> RSAPublicKey:
    """설정의 PEM 을 키로 읽는다. 서버가 뜰 때 한 번 부른다(틀렸으면 뜨지 않는다)."""
    try:
        key = load_pem_public_key(pem.encode())
    except ValueError as err:
        raise BadPublicKeyError("EDK_JWT_PUBLIC_KEY 를 PEM 공개키로 읽지 못했다") from err
    if not isinstance(key, RSAPublicKey):
        raise BadPublicKeyError("EDK_JWT_PUBLIC_KEY 가 RSA 공개키가 아니다")
    return key


def verify_edk_token(token: str, *, public_key: RSAPublicKey, audience: str, issuer: str) -> TokenResult:
    try:
        payload = jwt.decode(
            token,
            key=public_key,
            algorithms=list(EDK_ALGORITHMS),
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "aud", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        return TokenRejected("expired")
    except jwt.InvalidAudienceError:
        return TokenRejected("wrong_audience")
    except jwt.InvalidIssuerError:
        return TokenRejected("wrong_issuer")
    except jwt.MissingRequiredClaimError:
        return TokenRejected("bad_claims")
    except jwt.InvalidAlgorithmError:
        return TokenRejected("bad_algorithm")
    except jwt.InvalidSignatureError:
        return TokenRejected("bad_signature")
    except jwt.InvalidTokenError:
        return TokenRejected("malformed")
    return claims_from_payload(payload)
