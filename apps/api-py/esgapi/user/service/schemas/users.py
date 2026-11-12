"""고객사 사용자 관리 경로(K2c·UA1 — 운영 관리자 전용 목록·만들기·비밀번호 초기화·수정)의 요청과 응답의 꼴.
필드 이름은 camelCase, id 는 정수(XC 의 꼴).

companyId 는 넷 다 선택이다(사용자 결정 「시드로하자」): 없거나 null 이면 회사 표에 하나뿐인 회사로 한다. 회사가 둘
이상이면 400 company_ambiguous(감독 처분 — E2 가 422 로 옮길지 정한다).
비밀번호는 요청에만 있다 — 응답·기록에 싣지 않는다. kind·level·isInitial 은 본문에 칸이 없다(늘 service·79·참).
응답의 이름이 CustomerUserOut 인 까닭: UserOut 은 교환 응답(ExchangeOut.user)이 이미 쓰는 구성요소다(감독 처분).
"""

from typing import Self

from ninja import Schema
from pydantic import Field, model_validator

from esgapi.core.exceptions import ErrorBody
from esgapi.core.schemas import (
    TOKEN_BODY_ERROR_RESPONSES,
    TOKEN_ERROR_RESPONSES,
    KstDateTime,
    LimitOffsetPage,
    StrictIn,
)

# 넷의 오류 표: 토큰을 받는 동작의 표(444 포함)에 404(company_not_found·user_not_found)를 더한다.
# 409(username_taken)·400(company_ambiguous·password_rejected)는 바닥의 표에 이미 있다.
USER_ADMIN_ERROR_RESPONSES: dict[int, type[ErrorBody]] = {**TOKEN_ERROR_RESPONSES, 404: ErrorBody}
USER_ADMIN_BODY_ERROR_RESPONSES: dict[int, type[ErrorBody]] = {**TOKEN_BODY_ERROR_RESPONSES, 404: ErrorBody}

COMPANY_ID_DESCRIPTION = "대상 고객사의 id. 없거나 null 이면 하나뿐인 회사(둘 이상이면 400 company_ambiguous)"


class UserCreateIn(StrictIn):
    companyId: int | None = Field(default=None, description=COMPANY_ID_DESCRIPTION)
    # ASCII 만(처분 ⑥ — 전각 「ｋｉｍ」 과 「kim」 이 다른 계정이 되는 혼동을 막는다. 로그인의 꼴은 그대로 넓다).
    username: str = Field(min_length=1, max_length=150, pattern=r"^[A-Za-z0-9_.@+-]+$")
    name: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=1024, description="임시 비밀번호(첫 로그인 때 바꿔야 한다)")


class PasswordResetIn(StrictIn):
    companyId: int | None = Field(default=None, description=COMPANY_ID_DESCRIPTION)
    password: str = Field(min_length=1, max_length=1024, description="새 임시 비밀번호(첫 로그인 때 바꿔야 한다)")


class UserUpdateIn(StrictIn):
    """계정 수정(UA1 — 결정 MARC-ENT-281 의 4): 이름·사용 중지 둘 중 하나 이상. null 이거나 없으면 그 칸은 안 바꾼다."""

    companyId: int | None = Field(default=None, description=COMPANY_ID_DESCRIPTION)
    name: str | None = Field(default=None, min_length=1, max_length=20, description="새 이름. 없거나 null 이면 그대로")
    isActive: bool | None = Field(
        default=None, description="거짓이면 사용 중지, 참이면 다시 사용. 바뀌면 그 사람의 refresh 를 모두 끊는다"
    )

    @model_validator(mode="after")
    def something_to_change(self) -> Self:
        if self.name is None and self.isActive is None:
            raise ValueError("name 과 isActive 중 하나는 있어야 한다")
        return self


class CustomerUserOut(Schema):
    id: int
    companyId: int
    username: str
    name: str
    isActive: bool
    isInitial: bool
    isLocked: bool = Field(description="5번 틀려 잠긴 동안 참(로그인과 같은 판정 — 같은 초도 잠김)")
    branchId: int | None = Field(description="1차엔 늘 null(사업장은 K1b)")
    lastLoginAt: KstDateTime | None
    createdAt: KstDateTime = Field(description="계정을 만든 때")
    companyName: str = Field(description="그 사용자의 회사 이름")


class UserPageOut(LimitOffsetPage[CustomerUserOut]):
    pass
