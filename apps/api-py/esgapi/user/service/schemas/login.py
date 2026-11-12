"""로그인·토큰·자기 계정 경로의 요청과 응답의 꼴(K2a).
필드 이름은 camelCase, 새 스키마의 id 는 정수다(XC 의 꼴, 원문:111).

refresh 는 응답 본문으로 내고 요청 본문으로 받는다(쿠키 아님 — 처분 B2).
시각 칸은 KstDateTime 이다: Asia/Seoul +09:00 으로 내보낸다(밴드 E2, core/schemas.py).
"""

from typing import Literal

from ninja import Schema
from pydantic import Field

from esgapi.core.schemas import KstDateTime, StrictIn

# 회사 서브도메인의 꼴(organization/models.py 의 SUBDOMAIN_PATTERN 과 같은 규칙 — 남의 models 를 import 하지 않는다).
SUBDOMAIN_PATTERN = r"^[a-z0-9][a-z0-9-]{0,62}$"


class LoginIn(StrictIn):
    companySubdomain: str | None = Field(
        default=None,
        pattern=SUBDOMAIN_PATTERN,
        description=(
            "고객사 사용자는 회사 서브도메인. 없거나 null 이면 운영 관리자, 그 아이디의 운영 관리자가 없으면"
            " 하나뿐인 쓸 수 있는 회사의 고객사 사용자(회사가 둘 이상이면 운영 관리자만)"
        ),
    )
    username: str = Field(min_length=1, max_length=150, pattern=r"^[\w.@+-]+$")
    password: str = Field(min_length=1, max_length=1024)


class RefreshIn(StrictIn):
    refresh: str = Field(min_length=1, max_length=4096, description="로그인·refresh 가 낸 refresh 토큰")


class PasswordChangeIn(StrictIn):
    currentPassword: str = Field(min_length=1, max_length=1024)
    newPassword: str = Field(min_length=1, max_length=1024)


class TokenPairOut(Schema):
    access: str
    refresh: str
    accessExpiresAt: KstDateTime
    refreshExpiresAt: KstDateTime
    isInitial: bool
    kind: Literal["admin", "service"]


class UserMeOut(Schema):
    id: int
    username: str
    name: str
    kind: Literal["admin", "service"]
    companyId: int | None
    isInitial: bool
