"""user 의 로그인 경로(K2a): 로그인·refresh·로그아웃(revoke)과 자기 계정 둘(/users/me·비밀번호 바꾸기).

하는 일은 셋뿐이다: 요청에서 값을 꺼낸다 → services·actions·selectors 의 함수를 부른다 → 갈래를 응답(schemas)으로
바꾼다. models 를 직접 import 하지 않는다(`.importlinter` 계약 라). 이 router 는 user/api.py 가 user 의 router 에 단다.

토큰 싣기(처분 B2): access 는 `Authorization: Bearer`, refresh 는 본문. 444 는 토큰을 받는 동작에만 선언한다(처분 B4 —
refresh·revoke·/users/me·바꾸기. 로그인은 토큰을 받지 않는다).
"""

from typing import Final

from django.http import HttpRequest
from ninja import Router, Status

from esgapi.core.auth.bearer import access_token_auth, permitted
from esgapi.core.conf import now
from esgapi.core.exceptions import ApplicationError, ErrorKind
from esgapi.core.schemas import BODY_ERROR_RESPONSES, TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES
from esgapi.user.service.actions import password as actions
from esgapi.user.service.apis.user import login_ports
from esgapi.user.service.schemas.login import LoginIn, PasswordChangeIn, RefreshIn, TokenPairOut, UserMeOut
from esgapi.user.service.selectors import user as selectors
from esgapi.user.service.services import login as services
from esgapi.user.service.utils.login import (
    LoginRejected,
    LoginRejection,
    PasswordChangeRejected,
    PasswordChangeRejection,
    RefreshRejected,
    TokenPair,
)

router = Router(tags=["로그인"])

LOGIN_REJECTIONS: Final[dict[LoginRejection, str]] = {
    # 무엇이 틀렸는지(회사·username·비밀번호·계정 꺼짐) 말하지 않는다.
    "invalid_credentials": "로그인 정보가 맞지 않는다",
    "account_locked": "로그인에 5번 실패해 10분 동안 잠겼다",
}
CHANGE_REJECTIONS: Final[dict[PasswordChangeRejection, tuple[ErrorKind, str]]] = {
    "account_locked": ("unauthenticated", "로그인에 5번 실패해 10분 동안 잠겼다"),
    "current_password_mismatch": ("invalid_input", "지금 비밀번호가 맞지 않는다"),
    "password_rejected": ("invalid_input", "새 비밀번호를 쓸 수 없다"),
    "user_unavailable": ("unauthenticated", "이 토큰의 사용자를 쓸 수 없다. 다시 로그인한다"),
}


def pair_out(pair: TokenPair) -> TokenPairOut:
    return TokenPairOut(
        access=pair.access,
        refresh=pair.refresh,
        accessExpiresAt=pair.access_expires_at,
        refreshExpiresAt=pair.refresh_expires_at,
        isInitial=pair.is_initial,
        kind=pair.kind,
    )


def token_not_valid() -> ApplicationError:
    return ApplicationError("token_not_valid", "token_not_valid", "refresh 토큰을 쓸 수 없다. 다시 로그인한다")


@router.post("/auth/login", operation_id="user_auth_login", response={200: TokenPairOut, **BODY_ERROR_RESPONSES})
def auth_login(request: HttpRequest, body: LoginIn) -> TokenPairOut:
    """username·비밀번호로 토큰 짝을 받는다. companySubdomain 이 있으면 그 회사의 고객사 사용자, 없으면 운영 관리자를
    먼저 찾고 그 아이디의 운영 관리자가 없으면 하나뿐인 쓸 수 있는 회사의 고객사 사용자
    (회사가 둘 이상이면 운영 관리자만)."""
    result = services.login(
        subdomain=body.companySubdomain,
        username=body.username,
        password=body.password,
        now=now(),
        ports=login_ports(),
    )
    if isinstance(result, LoginRejected):
        raise ApplicationError("unauthenticated", result.reason, LOGIN_REJECTIONS[result.reason])
    return pair_out(result.pair)


@router.post(
    "/auth/refresh", operation_id="user_auth_refresh", response={200: TokenPairOut, **TOKEN_BODY_ERROR_RESPONSES}
)
def auth_refresh(request: HttpRequest, body: RefreshIn) -> TokenPairOut:
    """refresh 를 새 짝으로 바꾼다(rotate). 옛 refresh 는 그 순간 죽는다. 다시 내면 그 계보 전부가 끊긴다."""
    result = services.refresh(body.refresh, now=now())
    if isinstance(result, RefreshRejected):
        raise token_not_valid()
    return pair_out(result.pair)


@router.post("/auth/revoke", operation_id="user_auth_revoke", response={204: None, **TOKEN_BODY_ERROR_RESPONSES})
def auth_revoke(request: HttpRequest, body: RefreshIn) -> Status[None]:
    """로그아웃: 그 refresh 의 계보 전부를 끊는다. 이미 끊겼어도 204. 이미 낸 access 는 만료(30분)까지 통한다."""
    result = services.revoke(body.refresh, now=now())
    if isinstance(result, RefreshRejected):
        raise token_not_valid()
    return Status(204, None)


@router.get(
    "/users/me",
    operation_id="user_me",
    response={200: UserMeOut, **TOKEN_ERROR_RESPONSES},
    auth=access_token_auth,
    tags=["사용자"],
)
def users_me(request: HttpRequest) -> UserMeOut:
    """지금 토큰의 사용자. is_initial 이어도 열린다(화면이 비밀번호 바꾸기로 보내야 하는지 안다)."""
    principal = permitted(request, "user_me")
    user = selectors.account(principal.company_id, int(principal.user_id))
    if user is None or not user.is_active:
        kind, message = CHANGE_REJECTIONS["user_unavailable"]
        raise ApplicationError(kind, "user_unavailable", message)
    return UserMeOut(
        id=user.pk,
        username=user.username,
        name=user.name,
        kind="admin" if user.kind == "admin" else "service",
        companyId=user.company_id,
        isInitial=user.is_initial,
    )


@router.post(
    "/users/me/password",
    operation_id="user_password_change",
    response={200: TokenPairOut, **TOKEN_BODY_ERROR_RESPONSES},
    auth=access_token_auth,
    tags=["사용자"],
)
def users_password_change(request: HttpRequest, body: PasswordChangeIn) -> TokenPairOut:
    """자기 비밀번호를 바꾼다(첫 로그인·초기화 뒤에도 열린다). 새 짝을 내고 다른 기기의 refresh 를 모두 끊는다.
    지금 비밀번호가 틀리면 로그인 실패 횟수에 든다(5번이면 10분 잠금)."""
    principal = permitted(request, "user_password_change")
    result = actions.change_password(
        company_id=principal.company_id,
        user_id=int(principal.user_id),
        current=body.currentPassword,
        new=body.newPassword,
        now=now(),
    )
    if isinstance(result, PasswordChangeRejected):
        kind, message = CHANGE_REJECTIONS[result.reason]
        if result.messages:
            message = " ".join(result.messages)
        raise ApplicationError(kind, result.reason, message)
    return pair_out(result)
