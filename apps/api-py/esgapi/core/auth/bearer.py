"""우리 access 토큰(Bearer)이 경로와 닿는 자리: ninja 의 인증 AccessTokenAuth·CompanyScopedAuth 와 권한 검사 함수
permitted.
ninja 를 안다.

core 에 있는 까닭: core 의 경로(문서·실행)가 user 를 import 하지 못한다(계약 가 — py-edk-align-plan-review.md 4절 3 ㉡).
토큰의 꼴·서명·읽기는 core/auth/tokens.py(순수), 주체는 core/auth/principal.py, 권한 표는 core/permissions.py 다.

★ AccessTokenAuth 는 DB 를 읽지 않는다(우리 선택 — 리뷰 R13). 무효 조건: 계정을 끄거나 회사를 끄거나 비밀번호를
  바꾸거나 초기화해도 이미 낸 access 는 만료(30분)까지 통한다. refresh 는 DB 를 본다(user/service/services/login.py).
★ AccessTokenAuth 는 두 kind(운영 관리자·고객사 사용자)를 다 받는다. 무엇을 할 수 있는지는 권한 표가 가른다(permitted).
★ 회사 경로는 CompanyScopedAuth(머리가 없으면 다음 — 옛 교환 쿠키)와 쿠키를 함께 받는다(K2b, 사용자 결정 ㉠).
★ 운영 관리자(회사 없음)도 회사 경로의 인증을 지난다(결정 MARC-ENT-374). 회사 업무(권한 표 company)의 회사는 permitted
  뒤 company_of 가 꽂힌 포트(use_operator_company — config/api.py 가 user 의 작업 회사 고르기를 꽂는다)로 정한다.
★ 토큰이 틀리면(서명·꼴·만료·aud) 444 token_not_valid(원문:129). 머리가 없으면 — 필수 인스턴스(access_token_auth)는
  401 no_token 을 스스로 던진다(ninja 기본의 {"detail": "Unauthorized"} 가 아니라 우리 오류 꼴로 — K-B5).
"""

from collections.abc import Callable
from typing import Final

from django.http import HttpRequest
from ninja.security import HttpBearer

from esgapi.core import permissions
from esgapi.core.auth.principal import Principal, principal_of_session
from esgapi.core.auth.tokens import TokenRejected, TokenRejection, read_access
from esgapi.core.conf import app_config, now
from esgapi.core.exceptions import ApplicationError
from esgapi.core.tenancy.session import Session

TOKEN_REJECTIONS: Final[dict[TokenRejection, str]] = {
    "malformed": "토큰의 꼴이 아니다. 다시 로그인하거나 refresh 한다",
    "bad_signature": "토큰의 서명이 맞지 않는다. 다시 로그인한다",
    "expired": "토큰이 만료됐다. refresh 로 새 토큰을 받는다",
    "wrong_audience": "access 토큰이 아니다",
}


MISSING_HEADER_MESSAGE: Final = "토큰이 없다. Authorization: Bearer <access> 로 보낸다"


def token_not_valid(reason: TokenRejection) -> ApplicationError:
    return ApplicationError("token_not_valid", "token_not_valid", TOKEN_REJECTIONS[reason])


class AccessTokenAuth(HttpBearer):
    """`Authorization: Bearer <access>` 를 받는 경로에 건다. 통과하면 경로 함수의 request.auth 가 Principal 이다.

    required=True(필수 인스턴스 access_token_auth): 머리가 없거나 Bearer 가 아니면 401 no_token 을 던진다.
    required=False: None 을 돌려 다음 인증에 넘긴다(이중 인증 — K2b 가 쓴다).
    openapi 의 보안 구성요소 이름은 클래스 이름이다(AccessTokenAuth 하나).
    """

    def __init__(self, *, required: bool = False) -> None:
        super().__init__()
        self.required = required

    def __call__(self, request: HttpRequest) -> Principal | None:
        found: Principal | None = super().__call__(request)
        if found is None and self.required:
            raise ApplicationError("unauthenticated", "no_token", MISSING_HEADER_MESSAGE)
        return found

    def authenticate(self, request: HttpRequest, token: str) -> Principal:
        read = read_access(token, secret=app_config().session_secret, now=now())
        if isinstance(read, TokenRejected):
            raise token_not_valid(read.reason)
        claims = read.claims
        return Principal(
            user_id=claims.user_id,
            company_id=claims.company_id,
            kind=claims.kind,
            is_initial=claims.is_initial,
            via="bearer",
        )


access_token_auth = AccessTokenAuth(required=True)

COMPANY_REQUIRED_MESSAGE: Final = "회사가 있는 주체가 필요하다(고객사 사용자로 로그인한다)"


def company_required() -> ApplicationError:
    return ApplicationError("unauthenticated", "company_required", COMPANY_REQUIRED_MESSAGE)


def password_change_required() -> ApplicationError:
    return ApplicationError("forbidden", "password_change_required", "먼저 비밀번호를 바꾼다(첫 로그인·초기화 뒤)")


class CompanyScopedAuth(AccessTokenAuth):
    """회사 경로의 Bearer(K2b — 사용자 결정 ㉠ Bearer 통일). `auth=[company_scoped_auth_or_next, session_cookie]` 의 앞.

    머리가 없거나 `Bearer` 가 아니면 None → 다음 인증(옛 교환 쿠키 — C1 이 걷는다). 머리가 `Bearer …` 이면 이것이
    정한다:
    틀린 토큰은 444 token_not_valid(유효 쿠키가 같이 와도 쿠키로 넘어가지 않는다), is_initial 은 kind 와 상관없이
    403 password_change_required(회사 경로는 전부 INITIAL_ALLOWED 밖 — 본문 꼴 검사·회사 고르기보다 먼저 막는다).
    운영 관리자(회사 없음)는 지난다(결정 MARC-ENT-374 — DB 를 읽지 않는다). 고객사 전용 동작은 permitted 가 403
    forbidden 으로, 회사 업무의 회사는 permitted 뒤 company_of 가 정한다. 회사 없는 고객사 사용자는 토큰 읽기가 이미
    막지만 여기서 한 번 더 401 company_required(방어).
    경로마다 하위 클래스를 만들지 않는다(필요한 것의 검사는 첫 문장 permitted 가 권한 표로 한다).
    """

    def authenticate(self, request: HttpRequest, token: str) -> Principal:
        principal = super().authenticate(request, token)
        if principal.company_id is None and principal.kind != "admin":
            raise company_required()
        if principal.is_initial:
            raise password_change_required()
        return principal


company_scoped_auth_or_next = CompanyScopedAuth(required=False)


def principal_of(request: HttpRequest) -> Principal:
    """인증이 request.auth 에 넣어 둔 것의 주체. Bearer 면 그대로, 쿠키 세션이면 고객사 사용자. 없으면 401."""
    auth: object = getattr(request, "auth", None)
    if isinstance(auth, Principal):
        return auth
    if isinstance(auth, Session):
        return principal_of_session(auth)
    raise ApplicationError("unauthenticated", "no_session", "세션이 없다. 먼저 로그인한다")


# 운영 관리자의 작업 회사를 정하는 함수(포트). core 는 user·organization 을 import 하지 못해서(계약 가) config/api.py 가
# 꽂는다(use_operator_company). 안 꽂혔으면 None — company_of 가 401 company_required 로 끊는다(조용한 기본값 없음).
_operator_company: Callable[[], int] | None = None


def use_operator_company(choose: Callable[[], int]) -> None:
    """운영 관리자의 작업 회사를 정하는 함수를 꽂는다. 같은 함수를 다시 꽂는 것은 아무 일도 안 한다(멱등), 다른 함수면
    RuntimeError(두 자리가 다르게 꽂으면 어느 쪽이 이겼는지 모른다)."""
    global _operator_company
    if _operator_company is not None and _operator_company is not choose:
        raise RuntimeError("운영 관리자의 작업 회사 고르기가 이미 다른 함수로 꽂혀 있다")
    _operator_company = choose


def company_of(principal: Principal) -> int:
    """회사 업무 경로의 몸이 쓰는 회사 id(permitted 뒤에만 부른다). 고객사 사용자는 주체의 회사 그대로(포트를 부르지
    않는다), 운영 관리자는 꽂힌 포트가 고른 작업 회사(결정 MARC-ENT-374 — 하나뿐인 회사. 둘 이상·없음·비활성이면
    포트가 400·403 을 던진다). 포트가 안 꽂혔으면 401 company_required."""
    if principal.kind != "admin":
        if principal.company_id is None:  # 토큰 읽기가 짝을 검사한다(방어)
            raise company_required()
        return principal.company_id
    if _operator_company is None:
        raise company_required()
    return _operator_company()


def permitted(request: HttpRequest, operation_id: str) -> Principal:
    """경로의 첫 문장. 주체를 꺼내고 — is_initial 이면 INITIAL_ALLOWED 밖은 403 password_change_required(권한보다 먼저),
    그다음 권한 표(core/permissions.py)가 그 kind 를 받지 않으면 403 forbidden. 회사 경로의 고객사 전용 동작에 온 운영
    관리자의 Bearer 는 여기서 403 forbidden 이다(인증은 지난다 — 회사를 고르기 전, DB 0)."""
    principal = principal_of(request)
    if principal.is_initial and operation_id not in permissions.INITIAL_ALLOWED:
        raise password_change_required()
    if not permissions.is_allowed(operation_id, kind=principal.kind):
        raise ApplicationError("forbidden", "forbidden", permissions.forbidden_message(operation_id))
    return principal
