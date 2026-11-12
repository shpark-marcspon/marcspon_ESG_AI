"""organization 의 경로 열하나 — 사업장(/branches 여섯)·자산/시설 코드 목록(/facility-codes 하나 · /admin/facility-codes
넷). 밴드 K1b-1 ②(결정 MARC-ENT-469 3·4, 감독 판단 1). service/apis/organization.py 의 router 가 이 router 를 「""」 에
붙인다(config/api.py 0줄 — organization 라우터는 이미 맨 위 /).

    GET  /branches?q=&page=&pageSize=        organization_branches_list       회사 업무(작업 회사)
    GET  /branches/{branch_id}               organization_branches_get        〃
    POST /branches                           organization_branches_create     〃 → 201
    PUT  /branches/{branch_id}               organization_branches_save       〃
    POST /branches/inventory                 organization_branches_inventory  〃
    POST /branches/delete                    organization_branches_delete     〃
    GET  /facility-codes                     organization_facility_codes_list 회사 업무 — 작업 회사를 고르지 않는다
    GET  /admin/facility-codes?page=&pageSize=      organization_admin_facility_codes_list    운영 관리자만
    POST /admin/facility-codes                      organization_admin_facility_codes_create  〃 → 201
    PATCH /admin/facility-codes/{code_id}           organization_admin_facility_codes_update  〃(code 그대로)
    POST /admin/facility-codes/delete               organization_admin_facility_codes_delete  〃

인증: 회사 업무 일곱은 옛 /sites 와 같은 [company_scoped_auth_or_next, session_cookie](Bearer 먼저·옛 쿠키), admin 넷은
access_token_auth(Bearer). 차례: permitted(첫 문장) → 회사(company_of — 고객사 사용자는 주체의 회사, 운영 관리자는 작업
회사: 둘 이상 400 company_ambiguous) → actions·services·selectors. admin 넷은 회사를 고르지 않는다(company_of 0 — 회사
넘는 읽기 0). 경로는 models 를 import 하지 않는다(`.importlinter` 계약 라).
오류: 이름 겹침 422 `fields.name` · 사업장 안 (코드, 세부시설명) 겹침 422 `fields.facilities` · 지운 코드를 고름 422
`fields.facilityCodeId` · 본사 지움·끔 409 `headquarters_locked`(일괄이면 요청 전체) · 쓰이는 행 409 `in_use` · 남의
회사·삭제된 id(경로·ids[]·facilities[].id) 404 `not_found` · 저장 본문의 updatedAt 이 지금 판과 다름 409 `stale`(K1b-3 —
판정 차례 404 → 409 stale → 본사 → 줄) — 어느 거절이든 행 0.
★ 회사 id 는 인증 주체(토큰·세션)에서만 온다. 본문에 회사 칸이 없다(companyId → 422).
"""

from typing import Annotated

from django.http import HttpRequest
from ninja import Router, Status
from ninja.params.functions import Query

from esgapi.core.auth.bearer import access_token_auth, company_of, company_scoped_auth_or_next, permitted
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import (
    TOKEN_BODY_ERROR_RESPONSES,
    TOKEN_ERROR_RESPONSES,
    page_number_page,
)
from esgapi.organization.service.actions import branches as actions
from esgapi.organization.service.permissions.organization import Forbidden
from esgapi.organization.service.schemas.branches import (
    AdminFacilityCodeOut,
    AdminFacilityCodePageOut,
    BranchCreateIn,
    BranchDetailOut,
    BranchFacilityIn,
    BranchFacilityOut,
    BranchIdsIn,
    BranchInventoryIn,
    BranchOut,
    BranchPageOut,
    BranchSaveIn,
    CountOut,
    FacilityCodeNameIn,
    FacilityCodeOut,
    FacilityCodesOut,
    parse_seen_at,
)
from esgapi.organization.service.selectors import branches as selectors
from esgapi.organization.service.selectors import facility_codes as code_selectors
from esgapi.organization.service.services import facility_codes as code_services
from esgapi.organization.service.services.branches import FacilityRow, FacilityTaken, InUse, NameTaken
from esgapi.organization.service.utils.entities import Branch, BranchDetail, FacilityCodeInfo
from esgapi.user.service.apis.auth import session_cookie

router = Router(tags=["사업장"])
COMPANY_AUTH = [company_scoped_auth_or_next, session_cookie]
Page = Annotated[int, Query(ge=1, le=100_000)]  # 가지 리뷰 L4: 끝없는 OFFSET 0
Search = Annotated[str | None, Query(max_length=200)]  # 이름 칸 길이(200)까지
PageSize = Annotated[int, Query(ge=1, le=100)]
# 404 를 내는 일곱(없는·남의 회사·삭제된 id): 관례(core documents·dataverify ai_settings)대로 404 를 선언한다.
ERRORS_404: dict[int, type[ErrorBody]] = {**TOKEN_ERROR_RESPONSES, 404: ErrorBody}
BODY_ERRORS_404: dict[int, type[ErrorBody]] = {**TOKEN_BODY_ERROR_RESPONSES, 404: ErrorBody}

NOT_FOUND = "그런 사업장·자산/시설이 없다"
NAME_TAKEN = "같은 이름의 사업장이 이미 있다"
FACILITY_TAKEN = "자산/시설 줄이 겹친다(같은 코드·세부시설명이 이미 있거나 같은 줄을 두 번 보냈다)"
CODE_GONE = "고를 수 없는 자산/시설 코드다(없거나 지운 코드)"
HEADQUARTERS_LOCKED = "본사는 지울 수 없고 인벤토리 사용을 끌 수 없다"
IN_USE = "쓰이고 있어 지울 수 없다"
STALE = "다른 곳에서 먼저 저장했다 — 다시 읽고 저장하라"
CODE_NOT_FOUND = "그런 자산/시설 코드가 없다"
CODE_NAME_TAKEN = "같은 이름의 자산/시설 코드가 이미 있다"


def _branch_out(branch: Branch) -> BranchOut:
    return BranchOut(
        id=str(branch.id),
        name=branch.name,
        isHeadquarters=branch.is_headquarters,
        inventoryEnabled=branch.inventory_enabled,
        externalId=branch.external_id,
        createdAt=branch.created_at,
    )


def _detail_out(found: BranchDetail) -> BranchDetailOut:
    return BranchDetailOut(
        **_branch_out(found.branch).model_dump(),
        facilities=[
            BranchFacilityOut(
                id=str(facility.id),
                facilityCodeId=str(facility.facility_code_id),
                facilityCode=facility.facility_code,
                facilityName=facility.facility_name,
                detailName=facility.detail_name,
            )
            for facility in found.facilities
        ],
        updatedAt=found.branch.updated_at,
    )


def _rows(facilities: list[BranchFacilityIn]) -> list[FacilityRow]:
    return [FacilityRow(facility_code_id=f.facilityCodeId, detail_name=f.detailName, id=f.id) for f in facilities]


def _refused(found: object) -> ApplicationError:
    """actions·services 의 거절 갈래 → 오류. 갈래가 아니면 부른 쪽이 잘못 넘긴 것이다."""
    match found:
        case actions.NotFound():
            return ApplicationError("not_found", "not_found", NOT_FOUND)
        case actions.Stale():
            return ApplicationError("conflict", "stale", STALE)
        case NameTaken():
            return ApplicationError("validation", "validation_error", NAME_TAKEN, fields={"name": [NAME_TAKEN]})
        case FacilityTaken():
            return ApplicationError(
                "validation", "validation_error", FACILITY_TAKEN, fields={"facilities": [FACILITY_TAKEN]}
            )
        case actions.CodeGone():
            return ApplicationError("validation", "validation_error", CODE_GONE, fields={"facilityCodeId": [CODE_GONE]})
        case actions.HeadquartersLocked():
            return ApplicationError("conflict", "headquarters_locked", HEADQUARTERS_LOCKED)
        case InUse():
            return ApplicationError("conflict", "in_use", IN_USE)
        case code_services.CodesMissing():
            return ApplicationError("not_found", "not_found", CODE_NOT_FOUND)
        case code_services.CodeNameTaken():
            return ApplicationError(
                "validation", "validation_error", CODE_NAME_TAKEN, fields={"name": [CODE_NAME_TAKEN]}
            )
        case Forbidden():
            return ApplicationError("forbidden", "forbidden", found.message)
        case _:
            raise TypeError(f"모르는 갈래: {found!r}")


# ── 사업장(회사 업무 — 고객사 사용자와 작업 회사를 고른 운영 관리자) ─────────────────


@router.get(
    "/branches",
    operation_id="organization_branches_list",
    response={200: BranchPageOut, **TOKEN_ERROR_RESPONSES},
    auth=COMPANY_AUTH,
)
def branches_list(request: HttpRequest, q: Search = None, page: Page = 1, pageSize: PageSize = 20) -> BranchPageOut:
    """삭제 안 된 사업장. `q` 는 이름 부분 일치(대소문자 무시). 본사 먼저 → id 오름. 빈 쪽도 200."""
    principal = permitted(request, "organization_branches_list")
    found = selectors.search_sites(
        company_of(principal), q=q, order="headquarters", offset=(page - 1) * pageSize, limit=pageSize
    )
    results = [_branch_out(branch) for branch in found.branches]
    return BranchPageOut(**page_number_page(found.count, page, pageSize, results))


# 고정 경로(inventory·delete)를 {branch_id} 앞에 건다 — 뒤에 걸면 그 자리가 글자를 받아 405 다.
@router.post(
    "/branches/inventory",
    operation_id="organization_branches_inventory",
    response={200: CountOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def branches_inventory(request: HttpRequest, body: BranchInventoryIn) -> CountOut:
    """사업장 여럿의 인벤토리 사용을 켜거나 끈다. 끄는 요청에 본사가 섞이면 요청 전체 409."""
    principal = permitted(request, "organization_branches_inventory")
    found = actions.set_branches_inventory(company_of(principal), body.ids, enabled=body.enabled)
    if not isinstance(found, int):
        raise _refused(found)
    return CountOut(count=found)


@router.post(
    "/branches/delete",
    operation_id="organization_branches_delete",
    response={200: CountOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def branches_delete(request: HttpRequest, body: BranchIdsIn) -> CountOut:
    """사업장 여럿을 삭제 표시한다. 본사가 섞이면 요청 전체 409."""
    principal = permitted(request, "organization_branches_delete")
    found = actions.delete_branches(company_of(principal), body.ids)
    if not isinstance(found, int):
        raise _refused(found)
    return CountOut(count=found)


@router.get(
    "/branches/{branch_id}",
    operation_id="organization_branches_get",
    response={200: BranchDetailOut, **ERRORS_404},
    auth=COMPANY_AUTH,
)
def branches_get(request: HttpRequest, branch_id: int) -> BranchDetailOut:
    """사업장 하나와 그 자산/시설(삭제 안 된 것 — 코드 이름 → 세부시설명)."""
    principal = permitted(request, "organization_branches_get")
    found = selectors.branch_detail(company_of(principal), branch_id)
    if found is None:
        raise _refused(actions.NotFound())
    return _detail_out(found)


@router.post(
    "/branches",
    operation_id="organization_branches_create",
    response={201: BranchDetailOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def branches_create(request: HttpRequest, body: BranchCreateIn) -> Status[BranchDetailOut]:
    """사업장 하나(본사 아님)와 그 자산/시설을 한 트랜잭션에서 만든다."""
    principal = permitted(request, "organization_branches_create")
    found = actions.create_branch(
        company_of(principal),
        name=body.name,
        inventory_enabled=body.inventoryEnabled,
        facilities=_rows(body.facilities),
    )
    if not isinstance(found, BranchDetail):
        raise _refused(found)
    return Status(201, _detail_out(found))


@router.put(
    "/branches/{branch_id}",
    operation_id="organization_branches_save",
    response={200: BranchDetailOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def branches_save(request: HttpRequest, branch_id: int, body: BranchSaveIn) -> BranchDetailOut:
    """이름·인벤토리 사용과 자산/시설을 한 번에 저장한다 — id 있는 줄 고침, 없는 줄 새로, 빠진 기존 줄 삭제 표시."""
    # 본문 updatedAt 은 상세의 판이다 — 그사이 다른 저장·토글이 있었으면 409 stale(K1b-3, 다시 읽고 저장)
    principal = permitted(request, "organization_branches_save")
    found = actions.save_branch(
        company_of(principal),
        branch_id,
        seen_at=parse_seen_at(body.updatedAt),
        name=body.name,
        inventory_enabled=body.inventoryEnabled,
        facilities=_rows(body.facilities),
    )
    if not isinstance(found, BranchDetail):
        raise _refused(found)
    return _detail_out(found)


# ── 자산/시설 코드 목록(모든 고객사 공통) ──────────────────────────────


def _code_out(code: FacilityCodeInfo) -> FacilityCodeOut:
    return FacilityCodeOut(id=str(code.id), code=code.code, name=code.name)


@router.get(
    "/facility-codes",
    operation_id="organization_facility_codes_list",
    response={200: FacilityCodesOut, **TOKEN_ERROR_RESPONSES},
    auth=COMPANY_AUTH,
)
def facility_codes_list(request: HttpRequest) -> FacilityCodesOut:
    """새로 고를 수 있는 코드(지운 것 빼고) — 이름 가나다. 페이지 없음. 공통 목록이라 작업 회사를 고르지 않는다."""
    permitted(request, "organization_facility_codes_list")
    return FacilityCodesOut(items=[_code_out(code) for code in code_selectors.selectable_codes()])


@router.get(
    "/admin/facility-codes",
    operation_id="organization_admin_facility_codes_list",
    response={200: AdminFacilityCodePageOut, **TOKEN_ERROR_RESPONSES},
    auth=access_token_auth,
)
def admin_facility_codes_list(
    request: HttpRequest, page: Page = 1, pageSize: PageSize = 20
) -> AdminFacilityCodePageOut:
    """운영 관리자만. 코드 목록(지운 것 빼고) — 만든 차례. inUse 는 1차에 늘 거짓(회사 넘는 집계는 K1b-2a)."""
    principal = permitted(request, "organization_admin_facility_codes_list")
    found = code_selectors.admin_code_page(actor_kind=principal.kind, offset=(page - 1) * pageSize, limit=pageSize)
    if isinstance(found, Forbidden):
        raise _refused(found)
    results = [AdminFacilityCodeOut(**_code_out(item.code).model_dump(), inUse=item.in_use) for item in found.codes]
    return AdminFacilityCodePageOut(**page_number_page(found.count, page, pageSize, results))


@router.post(
    "/admin/facility-codes",
    operation_id="organization_admin_facility_codes_create",
    response={201: FacilityCodeOut, **TOKEN_BODY_ERROR_RESPONSES},
    auth=access_token_auth,
)
def admin_facility_codes_create(request: HttpRequest, body: FacilityCodeNameIn) -> Status[FacilityCodeOut]:
    """운영 관리자만. 코드 하나를 만든다 — code 는 F0001 꼴로 자동."""
    principal = permitted(request, "organization_admin_facility_codes_create")
    found = code_services.create_code(actor_kind=principal.kind, name=body.name)
    if not isinstance(found, FacilityCodeInfo):
        raise _refused(found)
    return Status(201, _code_out(found))


@router.post(
    "/admin/facility-codes/delete",
    operation_id="organization_admin_facility_codes_delete",
    response={200: CountOut, **BODY_ERRORS_404},
    auth=access_token_auth,
)
def admin_facility_codes_delete(request: HttpRequest, body: BranchIdsIn) -> CountOut:
    """운영 관리자만. 코드 여럿을 삭제 표시한다(새 선택 목록에서 빠진다 — 이미 쓰는 사업장의 줄은 그대로).
    하나라도 없거나 이미 지웠으면 404(일부만 처리 0). /{code_id} 앞에 건다."""
    principal = permitted(request, "organization_admin_facility_codes_delete")
    found = code_services.delete_codes(actor_kind=principal.kind, ids=body.ids)
    if not isinstance(found, int):
        raise _refused(found)
    return CountOut(count=found)


@router.patch(
    "/admin/facility-codes/{code_id}",
    operation_id="organization_admin_facility_codes_update",
    response={200: FacilityCodeOut, **BODY_ERRORS_404},
    auth=access_token_auth,
)
def admin_facility_codes_update(request: HttpRequest, code_id: int, body: FacilityCodeNameIn) -> FacilityCodeOut:
    """운영 관리자만. 이름을 고친다 — code 는 그대로(이미 쓰는 사업장에도 새 이름이 보인다)."""
    principal = permitted(request, "organization_admin_facility_codes_update")
    found = code_services.rename_code(actor_kind=principal.kind, code_id=code_id, name=body.name)
    if not isinstance(found, FacilityCodeInfo):
        raise _refused(found)
    return _code_out(found)
