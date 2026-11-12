"""user 의 경로: 교환·로그아웃·/me. django-ninja 의 함수 하나가 경로 하나다. config/api.py 가 이 router 를 맨 위(/)에
걸어 두었다(organization 의 /sites 와 함께 — PY1 의 계약 그대로, operationId 는 accounts_* 그대로).

하는 일은 셋뿐이다: 요청에서 값을 꺼낸다 → services 의 함수를 부른다 → 갈래를 응답(schemas)으로 바꾼다.
models 를 직접 import 하지 않는다(`.importlinter` 계약 라).

교환의 바깥 셋을 꽂는 자리(exchange_ports)가 여기 있다(처분 7): 회사 찾기는 organization 의 selectors 라
도메인을 넘는다.
services·selectors 는 남의 도메인을 import 하지 않으므로(계약 바) 그 조립은 apis 에서 한다.
"""

from typing import Final

from django.http import HttpRequest, HttpResponse
from ninja import Router, Status

from esgapi.core.conf import app_config, now
from esgapi.core.exceptions import ApplicationError, ErrorKind
from esgapi.core.schemas import BODY_ERROR_RESPONSES, ERROR_RESPONSES
from esgapi.organization.service.selectors.organization import SoleCompany, find_company, find_sole_company
from esgapi.organization.service.utils.entities import CompanyActive
from esgapi.user.service.apis.auth import clear_session_cookie, permitted_session, session_cookie, set_session_cookie
from esgapi.user.service.apis.users import router as users_router
from esgapi.user.service.schemas.user import ExchangeIn, ExchangeOut, MeOut, TenantOut, UserOut
from esgapi.user.service.services import user as services
from esgapi.user.service.services.login import LoginPorts
from esgapi.user.service.utils.entities import Tenant
from esgapi.user.service.utils.exchange import (
    ExchangeRejected,
    ExchangeRejection,
    TenantLookup,
    TenantRegistered,
    TenantUnknown,
)

router = Router()
router.add_router("", users_router)  # 고객사 사용자 관리 셋(K2c — service/apis/users.py, 운영 관리자 전용)

# operation_id 는 손으로 적는다(`<모듈>_<동작>`). 안 적으면 ninja 가 함수의 모듈 경로로 지어
# 파일을 옮길 때 프론트의 타입 이름이 바뀐다. 표는 esgapi/config/tests/test_api_contract.py 가 못 박는다.
# accounts 에서 옮겨 왔어도 이름은 accounts_* 그대로다(프론트의 계약).

# 교환이 거절된 갈래마다의 오류 종류와 문장. 갈래가 늘면 pyright 가 여기 빠진 것을 잡는다(dict 의 키 타입).
# 종류 → 상태 코드: unauthenticated 401, forbidden 403 (config/api.py 의 HTTP_STATUS).
EXCHANGE_REJECTIONS: Final[dict[ExchangeRejection, tuple[ErrorKind, str]]] = {
    "malformed": ("unauthenticated", "토큰의 꼴이 아니다"),
    "bad_algorithm": ("unauthenticated", "토큰의 서명 알고리즘이 허용된 것이 아니다"),
    "bad_signature": ("unauthenticated", "토큰의 서명이 맞지 않는다"),
    "expired": ("unauthenticated", "토큰이 만료됐다. EDK 에서 새 토큰을 받아 다시 교환한다"),
    "wrong_audience": ("unauthenticated", "이 서비스에게 준 토큰이 아니다(aud)"),
    "wrong_issuer": ("unauthenticated", "믿는 발급자가 낸 토큰이 아니다(iss)"),
    "bad_claims": ("unauthenticated", "토큰에 필요한 값이 없거나 꼴이 틀렸다(sub·tenant_id·role·name)"),
    "unknown_tenant": ("forbidden", "등록되지 않은 테넌트다. 마크스폰 관리자가 등록해야 한다"),
    "user_inactive": ("forbidden", "쓸 수 없는 계정이다. 마크스폰 관리자에게 묻는다"),
    "username_conflict": ("conflict", "그 username 은 이 회사의 비밀번호 사용자다. 마크스폰 관리자에게 묻는다"),
}

# ── 교환의 바깥 셋 ────────────────────────────────────────────────────


def find_tenant(tenant_id: str) -> TenantLookup:
    """토큰의 tenant_id(= 회사의 subdomain)로 쓸 수 있는 회사를 찾는다. 없거나 비활성이면 같은 답(미등록)이다."""
    found = find_company(tenant_id)
    if not isinstance(found, CompanyActive):
        return TenantUnknown()
    company = found.company
    return TenantRegistered(Tenant(id=company.subdomain, name=company.name, company_id=company.id))


def company_id_of(subdomain: str) -> int | None:
    """로그인의 회사 찾기(K2a): 그 서브도메인의 쓸 수 있는 회사 id. 없거나 비활성이면 None(같은 답 — 드러내지 않는다).
    교환과 같은 find_company 를 쓴다(Company.by_subdomain 의 호출 자리를 늘리지 않는다)."""
    found = find_company(subdomain)
    return found.company.id if isinstance(found, CompanyActive) else None


def sole_company_id() -> int | None:
    """서브도메인 없는 로그인의 회사(UA1 — MARC-ENT-283): 회사 표에 회사가 정확히 하나이고 쓸 수 있으면 그 id, 아니면
    None(0·둘 이상·비활성 — 고객사 길이 닫히고 운영 관리자만 남는다). find_sole_company 는 앞 두 행만 읽는다."""
    sole = find_sole_company()
    if isinstance(sole, SoleCompany) and sole.company.is_active:
        return sole.company.id
    return None


def login_ports() -> LoginPorts:
    """login 에 넘길 진짜 구현."""
    return LoginPorts(company_id_of=company_id_of, sole_company_id=sole_company_id)


def exchange_ports() -> services.ExchangePorts:
    """exchange 에 넘길 진짜 구현들."""
    return services.ExchangePorts(
        verify_token=services.verify_token,
        find_tenant=find_tenant,
        upsert_user=services.upsert_user,
    )


# ── 인증 ──────────────────────────────────────────────────────────────


@router.post(
    "/auth/exchange",
    operation_id="accounts_auth_exchange",
    response={200: ExchangeOut, **BODY_ERROR_RESPONSES},
    tags=["인증"],
)
def auth_exchange(request: HttpRequest, response: HttpResponse, body: ExchangeIn) -> ExchangeOut:
    """EDK 가 서명한 토큰을 우리 세션으로 바꾼다. 세션은 쿠키로 나간다(본문에는 싣지 않는다)."""
    result = services.exchange(
        body.token,
        ports=exchange_ports(),
        now=now(),
        session_ttl_seconds=app_config().session_ttl_seconds,
    )
    if isinstance(result, ExchangeRejected):
        kind, message = EXCHANGE_REJECTIONS[result.reason]
        raise ApplicationError(kind, result.reason, message)

    set_session_cookie(response, result.session)
    user = result.user
    return ExchangeOut(
        user=UserOut(id=user.id, name=user.name, issuer=user.issuer, externalId=user.external_id),
        tenant=TenantOut(id=result.tenant.id, name=result.tenant.name),
        role=user.role,
        expiresAt=result.session.expires_at,
    )


@router.post("/auth/logout", operation_id="accounts_auth_logout", response={204: None}, tags=["인증"])
def auth_logout(request: HttpRequest, response: HttpResponse) -> Status[None]:
    """쿠키를 지운다. 서버에 세션 목록이 없으므로 그것이 전부다(베껴 둔 쿠키는 만료까지 통한다)."""
    clear_session_cookie(response)
    return Status(204, None)


@router.get(
    "/me",
    operation_id="accounts_me",
    response={200: MeOut, **ERROR_RESPONSES},
    auth=session_cookie,
    tags=["인증"],
)
def me(request: HttpRequest) -> MeOut:
    """지금 세션의 내용. DB 를 읽지 않는다(세션에 든 값 그대로)."""
    session = permitted_session(request, "accounts_me")
    return MeOut(
        userId=session.user_id,
        tenantId=session.tenant_id,
        role=session.role,
        expiresAt=session.expires_at,
        companyId=session.company_id,
    )
