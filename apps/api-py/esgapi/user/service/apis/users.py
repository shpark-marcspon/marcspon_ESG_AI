"""user 의 고객사 사용자 관리 경로(K2c·UA1): 운영 관리자 전용 목록·만들기·비밀번호 초기화·수정.
대상은 고른 회사의 고객사 사용자.

하는 일은 셋뿐이다: 요청에서 값을 꺼낸다 → selectors·services·actions 의 함수를 부른다 → 갈래를 응답(schemas)으로
바꾼다. models 를 직접 import 하지 않는다(`.importlinter` 계약 라). 이 router 는 service/apis/user.py 가 user 의
router 에 단다.

차례(c-0-2): 인증(Bearer) → permitted(is_initial → 표) → 그다음에야 몸이 회사를 고르고 대상을 찾는다. 그래서 고객사
사용자의 403 은 회사 세기·DB 읽기 0 이다. 넷의 몸이 부르는 selectors·services·actions 도 첫 줄에서 권한을 다시 본다
(user/service/permissions — 명령이 같은 service·action 을 부른다).

회사 고르기(네 경로 같은 규칙, 몸의 첫 일): companyId 가 있으면 그 회사(없으면 404 company_not_found), 없거나 null 이면
하나뿐인 회사(0 이면 404, 둘 이상이면 400 company_ambiguous — 아무것도 안 읽고 안 쓴다). 회사 찾기는 organization 의
selectors 라 도메인을 넘는다 — 그 둘을 꽂는 자리(company_ports)가 여기 있다(교환·로그인의 포트와 같은 꼴, 계약 바).
운영 관리자에게는 회사 범위가 없다: 대상 사용자는 고른 회사 id 로 User.for_company 에서 연다(회사를 넘는 조회 0).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

from django.http import HttpRequest
from ninja import Router, Status
from ninja.params.functions import Query

from esgapi.core.auth.bearer import access_token_auth, permitted
from esgapi.core.conf import now
from esgapi.core.exceptions import ApplicationError
from esgapi.organization.service.selectors.organization import (
    CompanyRef,
    ManyCompanies,
    NoCompany,
    SoleCompany,
    find_company_by_id,
    find_sole_company,
)
from esgapi.user.service.actions import account
from esgapi.user.service.actions import password as actions
from esgapi.user.service.permissions.user import Forbidden
from esgapi.user.service.schemas.users import (
    USER_ADMIN_BODY_ERROR_RESPONSES,
    USER_ADMIN_ERROR_RESPONSES,
    CustomerUserOut,
    PasswordResetIn,
    UserCreateIn,
    UserPageOut,
    UserUpdateIn,
)
from esgapi.user.service.selectors import user as selectors
from esgapi.user.service.services import user as services
from esgapi.user.service.utils.login import PasswordRejected, UsernameTaken, UserNotFound, is_locked

router = Router(tags=["사용자 관리"])

COMPANY_NOT_FOUND: Final = "그 회사가 없다"
COMPANY_AMBIGUOUS: Final = "회사가 둘 이상이라 companyId 를 골라야 한다"
COMPANY_INACTIVE: Final = "작업 회사가 사용 중지 상태다"
USER_NOT_FOUND: Final = "그 회사에 그 고객사 사용자가 없다"
STATUS_DESCRIPTION: Final = (
    "active 사용 중 · initial 초기화 대기 · locked 잠김 · inactive 사용 중지(앞섬: 사용 중지 > 잠김 > 초기화 대기)"
)

# ── 회사 고르기의 포트 둘 ─────────────────────────────────────────────


@dataclass(frozen=True)
class CompanyPorts:
    """회사 고르기가 바깥에 시키는 일 둘. 인터페이스가 아니라 함수 둘의 묶음이다(테스트는 감싸 호출을 센다)."""

    company_by_id: Callable[[int], CompanyRef | None]
    sole_company: Callable[[], SoleCompany | NoCompany | ManyCompanies]


def company_ports() -> CompanyPorts:
    """진짜 구현(organization 의 selectors)."""
    return CompanyPorts(company_by_id=find_company_by_id, sole_company=find_sole_company)


def chosen_company(company_id: int | None, ports: CompanyPorts) -> int:
    """요청의 companyId 로 대상 회사의 id 를 정한다(네 경로 같은 규칙)."""
    if company_id is not None:
        found = ports.company_by_id(company_id)
        if found is None:
            raise ApplicationError("not_found", "company_not_found", COMPANY_NOT_FOUND)
        return found.id
    sole = ports.sole_company()
    if isinstance(sole, ManyCompanies):
        raise ApplicationError("invalid_input", "company_ambiguous", COMPANY_AMBIGUOUS)
    if isinstance(sole, NoCompany):
        raise ApplicationError("not_found", "company_not_found", COMPANY_NOT_FOUND)
    return sole.company.id


def operator_work_company() -> int:
    """운영 관리자가 회사 업무(문서·실행·그린워싱)를 하는 작업 회사의 id(결정 MARC-ENT-374 — 하나뿐인 회사).
    core 의 company_of 가 포트로 부른다(config/api.py 가 꽂는다 — core 는 user·organization 을 import 하지 못한다).
    회사가 둘 이상이면 400 company_ambiguous, 없으면 400 company_not_found(업무 경로 — 사용자 관리 경로의 같은 code 는
    404), 하나인데 사용 중지면 403 company_inactive. 셋 다 회사 표의 앞 두 행 말고는 읽지도 쓰지도 않는다."""
    sole = company_ports().sole_company()
    if isinstance(sole, ManyCompanies):
        raise ApplicationError("invalid_input", "company_ambiguous", COMPANY_AMBIGUOUS)
    if isinstance(sole, NoCompany):
        raise ApplicationError("invalid_input", "company_not_found", COMPANY_NOT_FOUND)
    if not sole.company.is_active:
        raise ApplicationError("forbidden", "company_inactive", COMPANY_INACTIVE)
    return sole.company.id


# ── 갈래를 응답으로 ───────────────────────────────────────────────────


def forbidden(refused: Forbidden) -> ApplicationError:
    return ApplicationError("forbidden", "forbidden", refused.message)


def customer_user_out(company_id: int, user_id: int, moment: datetime) -> CustomerUserOut:
    """방금 만들거나 초기화하거나 고친 사용자를 다시 읽어 응답으로(같은 회사 조건 — selectors.account)."""
    row = selectors.account(company_id, user_id)
    if row is None:  # 방금 쓴 행이 사라졌다(동시 삭제 — 1차엔 삭제 경로 0)
        raise ApplicationError("not_found", "user_not_found", USER_NOT_FOUND)
    return out_of(row, moment)


def out_of(row: selectors.User, moment: datetime) -> CustomerUserOut:
    company = row.company
    if (
        row.company_id is None or company is None
    ):  # 운영 관리자 행(회사 NULL)은 이 경로들의 조회에 없다 — for_company 의 kind service
        raise ApplicationError("not_found", "user_not_found", USER_NOT_FOUND)
    return CustomerUserOut(
        id=row.pk,
        companyId=row.company_id,
        username=row.username,
        name=row.name,
        isActive=row.is_active,
        isInitial=row.is_initial,
        # 로그인과 같은 판정(K2a 의 is_locked — 같은 초도 잠김). 따로 셈하지 않는다(처분 B11).
        isLocked=is_locked(row.login_expiry_at, moment),
        branchId=None,
        lastLoginAt=row.last_login,
        createdAt=row.date_joined,  # Django 의 「만든 때」(default=timezone.now — 새 칸 0, 처분 ④)
        companyName=company.name,  # 셀렉터가 select_related("company") 로 같이 읽는다(처분 ⑤)
    )


# ── 경로 넷 ──────────────────────────────────────────────────────────


@router.get(
    "/users",
    operation_id="user_list",
    response={200: UserPageOut, **USER_ADMIN_ERROR_RESPONSES},
    auth=access_token_auth,
)
def users_list(
    request: HttpRequest,
    companyId: int | None = Query(None, description="대상 고객사의 id. 없으면 하나뿐인 회사"),  # 이름이 계약(camelCase)
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, min_length=1, max_length=150, description="아이디·이름의 부분 일치(대소문자 무시)"),
    status: Literal["active", "initial", "locked", "inactive"] | None = Query(None, description=STATUS_DESCRIPTION),
) -> UserPageOut:
    """그 회사의 고객사 사용자 목록(id 오름, 사용 중지 포함 · 교환이 만든 행 뺌). q·status 로 거르고 count 는 거른 뒤의
    수다. companyId 를 생략하면 하나뿐인 회사."""
    principal = permitted(request, "user_list")
    company_id = chosen_company(companyId, company_ports())
    moment = now()
    page = selectors.list_customer_users(
        actor_kind=principal.kind, company_id=company_id, limit=limit, offset=offset, now=moment, q=q, status=status
    )
    if isinstance(page, Forbidden):
        raise forbidden(page)
    return UserPageOut(
        count=page.count,
        isNext=offset + len(page.rows) < page.count,
        results=[out_of(row, moment) for row in page.rows],
    )


@router.post(
    "/users",
    operation_id="user_create",
    response={201: CustomerUserOut, **USER_ADMIN_BODY_ERROR_RESPONSES},
    auth=access_token_auth,
)
def users_create(request: HttpRequest, body: UserCreateIn) -> Status[CustomerUserOut]:
    """그 회사에 고객사 사용자를 만든다(kind service·level 79·isInitial 참). 비밀번호는 응답에 없다."""
    principal = permitted(request, "user_create")
    company_id = chosen_company(body.companyId, company_ports())
    result = services.create_customer_user(
        actor_kind=principal.kind,
        company_id=company_id,
        username=body.username,
        name=body.name,
        password=body.password,
        actor_user_id=int(principal.user_id),
    )
    if isinstance(result, Forbidden):
        raise forbidden(result)
    if isinstance(result, UsernameTaken):
        raise ApplicationError("conflict", "username_taken", "그 회사에 그 username 이 이미 있다")
    if isinstance(result, PasswordRejected):
        raise ApplicationError("invalid_input", "password_rejected", " ".join(result.messages))
    return Status(201, customer_user_out(company_id, result.user_id, now()))


@router.post(
    "/users/{int:user_id}/password-reset",
    operation_id="user_password_reset",
    response={200: CustomerUserOut, **USER_ADMIN_BODY_ERROR_RESPONSES},
    auth=access_token_auth,
)
def users_password_reset(request: HttpRequest, user_id: int, body: PasswordResetIn) -> CustomerUserOut:
    """그 회사의 고객사 사용자의 비밀번호를 초기화한다: isInitial 참·잠금 풀림·그 사람의 refresh 전부 끊음.
    남의 회사의 id·운영 관리자의 id·없는 id 는 404 user_not_found(행 0 변화)."""
    principal = permitted(request, "user_password_reset")
    company_id = chosen_company(body.companyId, company_ports())
    prepared = services.prepare_customer_reset(company_id=company_id, user_id=user_id, password=body.password)
    if isinstance(prepared, UserNotFound):
        raise ApplicationError("not_found", "user_not_found", USER_NOT_FOUND)
    if isinstance(prepared, PasswordRejected):
        raise ApplicationError("invalid_input", "password_rejected", " ".join(prepared.messages))
    moment = now()
    done = actions.reset_password(
        actor_kind=principal.kind,
        company_id=company_id,
        user_id=user_id,
        password_hash=prepared.password_hash,
        now=moment,
        actor_user_id=int(principal.user_id),
    )
    if isinstance(done, Forbidden):
        raise forbidden(done)
    if isinstance(done, UserNotFound):
        raise ApplicationError("not_found", "user_not_found", USER_NOT_FOUND)
    return customer_user_out(company_id, done.user_id, moment)


@router.patch(
    "/users/{int:user_id}",
    operation_id="user_update",
    response={200: CustomerUserOut, **USER_ADMIN_BODY_ERROR_RESPONSES},
    auth=access_token_auth,
)
def users_update(request: HttpRequest, user_id: int, body: UserUpdateIn) -> CustomerUserOut:
    """그 회사의 고객사 사용자의 이름·사용 여부를 고친다(UA1 — 결정 MARC-ENT-281 의 4). 같은 값이면 그대로 200.
    사용을 멈추거나 다시 열면 그 사람의 refresh 를 모두 끊는다. 이미 낸 access 는 만료(30분)까지 통한다.
    남의 회사의 id·운영 관리자의 id·없는 id·교환이 만든 행은 404 user_not_found(행 0 변화)."""
    principal = permitted(request, "user_update")
    company_id = chosen_company(body.companyId, company_ports())
    moment = now()
    done = account.update_customer_user(
        actor_kind=principal.kind,
        company_id=company_id,
        user_id=user_id,
        name=body.name,
        is_active=body.isActive,
        now=moment,
        actor_user_id=int(principal.user_id),
    )
    if isinstance(done, Forbidden):
        raise forbidden(done)
    if isinstance(done, UserNotFound):
        raise ApplicationError("not_found", "user_not_found", USER_NOT_FOUND)
    return customer_user_out(company_id, done.user_id, moment)
