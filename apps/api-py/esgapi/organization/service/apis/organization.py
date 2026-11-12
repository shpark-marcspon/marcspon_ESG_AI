"""organization 의 경로: 사업장(/sites). config/api.py 가 이 router 를 맨 위(/)에 걸어 두었다(PY1 의 계약 그대로,
operationId 는 accounts_* 그대로).

하는 일은 셋뿐이다: 요청에서 값을 꺼낸다 → services·selectors 의 함수를 부른다 → 갈래를 응답(schemas)으로 바꾼다.
models 를 직접 import 하지 않는다(`.importlinter` 계약 라). 세션 인증의 바인딩은 user 의 것을 들인다(apis 층).
"""

from django.http import HttpRequest
from ninja import Router, Status

from esgapi.core.auth.bearer import company_scoped_auth_or_next, principal_of
from esgapi.core.exceptions import ApplicationError
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES
from esgapi.organization.service.apis.branches import NAME_TAKEN
from esgapi.organization.service.apis.branches import router as branches_router
from esgapi.organization.service.permissions.organization import Forbidden
from esgapi.organization.service.schemas.organization import SiteCreatedOut, SiteIn, SiteOut, SitesOut
from esgapi.organization.service.selectors import organization as selectors
from esgapi.organization.service.services import organization as services
from esgapi.organization.service.services.branches import NameTaken
from esgapi.user.service.apis.auth import session_cookie

router = Router()
# K1b-1: /branches 여섯·/facility-codes·/admin/facility-codes 넷(apis/branches.py).
# 옛 /sites 둘은 계약 그대로 deprecated.
router.add_router("", branches_router)


def _forbidden(result: Forbidden) -> ApplicationError:
    return ApplicationError("forbidden", "forbidden", result.message)


@router.get(
    "/sites",
    operation_id="accounts_sites_list",
    response={200: SitesOut, **TOKEN_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
    tags=["사업장"],
    deprecated=True,
)
def sites_list(request: HttpRequest) -> SitesOut:
    """이 주체의 회사의 사업장 전부. 고객사 사용자(권한 표 customer) — Bearer 또는 옛 교환 쿠키.
    회사로 가르는 일은 앱이 한다(주체의 회사 조건)."""
    # 위 docstring 은 OpenAPI 의 설명으로 나가 옛 글자 그대로 둔다(generated 는 더함만).
    # 회사 조건은 selector 가 주체(Bearer 또는 옛 교환 쿠키의 세션 — principal_of)에서 받는다.
    result = selectors.list_sites(principal_of(request))
    if isinstance(result, Forbidden):
        raise _forbidden(result)
    return SitesOut(sites=[SiteOut(id=site.id, name=site.name, externalId=site.external_id) for site in result.sites])


@router.post(
    "/sites",
    operation_id="accounts_sites_create",
    response={201: SiteCreatedOut, **TOKEN_BODY_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
    tags=["사업장"],
    deprecated=True,
)
def sites_create(request: HttpRequest, body: SiteIn) -> Status[SiteCreatedOut]:
    """사업장을 만든다. 고객사 사용자(권한 표 customer) — Bearer 또는 옛 교환 쿠키. 회사는 주체에서 온다
    (본문에 그 칸이 없다)."""
    result = services.create_site(principal_of(request), name=body.name, external_id=body.externalId)
    if isinstance(result, Forbidden):
        raise _forbidden(result)
    # K1b-1: 이름 unique(삭제 안 된 것끼리) — 이미 선언된 422 fields.name(1-5 N4: 이 줄 없이 잰 지금 값 500)
    if isinstance(result, NameTaken):
        raise ApplicationError("validation", "validation_error", NAME_TAKEN, fields={"name": [NAME_TAKEN]})
    site = result.site
    return Status(201, SiteCreatedOut(site=SiteOut(id=site.id, name=site.name, externalId=site.external_id)))
