"""Scope 1·2 엑셀 경로 셋(밴드 S12b-1 ③·S12b-2 ③ — 결정 MARC-ENT-472). apis/inventory.py 가 이 router 를 「""」
에 붙인다. 아래 경로는 /inventory 뒤의 것이다. `Y` = /scope12/years/{year}.

    GET Y/template?scope=&siteId=   inventory_scope12_template   회사 업무(COMPANY) — 일괄업로드 양식(xlsx)
    GET Y/export?scope=             inventory_scope12_export     〃 — 데이터 엑셀(xlsx)
    POST Y/uploads                  inventory_scope12_upload     〃 — 일괄 올리기(본문 = xlsx 바이트 그대로)

몸: service/actions/scope12_excel.py(읽기만) · scope12_upload.py(올리기). 꼴은 scope3_runs.py 의 양식 경로 그대로:
바이트 응답 · RFC 6266
첨부(한글 이름 → filename*=utf-8''…) · nosniff. 인증 [company_scoped_auth_or_next, session_cookie] · 차례 permitted(첫
문장) → company_of(principal) → actions. 운영 관리자는 작업 회사(회사 둘이면 400 company_ambiguous).
★ 회사 id 는 인증 주체에서만 온다 — 쿼리 칸에 companyId 가 없다(실어 보내도 읽지 않는다: 쿼리는 열림 관례).
오류: 해 없음·숨기지 않은 선택 0·채울 줄 0·그 회사 켠 사업장이 아닌 siteId 404 `not_found` · scope 밖 422
`fields.scope`. year 범위 검사는 entries GET 과 같이 두지 않는다(없는 해 = 404 — C0 물음 A).
올리기: 맨 바이트 본문이다(multipart 경로가 없다 — dataverify_edk_read 꼴). 상한은 이 경로만 `GHG_UPLOAD_MAX_BYTES`
(20MB — 결정 MARC-ENT-593, 71 허락 꼴): 머리 CONTENT_LENGTH 가 넘으면 읽기 전에, 아니면
`request.read(상한 + 1)` 로 읽어 읽은 길이가 넘으면 `RequestDataTooBig` 을 던져 바닥
(config/api.py)의 처리기가 413 `body_too_large` 로 답한다. ★ 이 경로에서 `request.body` 를 읽지 않는다(전역
DATA_UPLOAD_MAX_MEMORY_SIZE 2.5MB 에 걸린다 — 다른 경로의 상한은 그대로다).
오류: 해 없음·숨기지 않은 선택 0 404 · 잠금 경합 409 `locked` · 파일·줄·칸 오류 422
`invalid_upload` — `fields` 는 `<시트>!<칸>`·`file`·`more` → 글 하나.
"""

from typing import Annotated

from django.core.exceptions import RequestDataTooBig
from django.http import HttpRequest, HttpResponse
from django.utils import http as django_http
from ninja import Router
from ninja.params.functions import Query

from esgapi.core.auth.bearer import company_of, company_scoped_auth_or_next, permitted
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES
from esgapi.inventory.service.actions import scope12_excel as actions
from esgapi.inventory.service.actions import scope12_upload as upload_actions
from esgapi.inventory.service.schemas.entries import EntryUploadOut
from esgapi.inventory.service.utils.entries import Actor, Locked
from esgapi.inventory.service.utils.ghg_pool import Invalid, NotFound
from esgapi.inventory.tools.xlsx_reader import GHG_UPLOAD_MAX_BYTES
from esgapi.user.service.apis.auth import session_cookie

router = Router(tags=["Scope 1·2 입력"])
COMPANY_AUTH = [company_scoped_auth_or_next, session_cookie]
YEAR_PATH = "/scope12/years/{year}"
ERRORS_404: dict[int, type[ErrorBody]] = {**TOKEN_ERROR_RESPONSES, 404: ErrorBody}
NOT_FOUND = "그런 해·사업장이 없거나 내려받을 줄이 없다"
INVALID = "입력을 확인한다"
NOT_FOUND_YEAR = "그런 해가 없거나 고른 인덱스가 없다"
INVALID_UPLOAD = "올린 파일을 확인한다"
LOCKED = "잠긴 인덱스라 바꿀 수 없다"
UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "content": {actions.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
    }
}

Scope = Annotated[str | None, Query(max_length=3, description="Scope 거름")]
SiteId = Annotated[int | None, Query(alias="siteId", description="그 회사 켠 사업장 id(없으면 전부)")]


def _binary(description: str) -> dict[str, object]:
    return {
        "responses": {
            200: {
                "description": description,
                "content": {actions.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
            }
        }
    }


def _refused(found: NotFound | Invalid) -> ApplicationError:
    match found:
        case NotFound():
            return ApplicationError("not_found", "not_found", NOT_FOUND)
        case Invalid(fields=fields):
            return ApplicationError(
                "validation", "validation_error", INVALID, fields={name: [why] for name, why in fields.items()}
            )


def _download(found: actions.Download) -> HttpResponse:
    response = HttpResponse(found.content, content_type=actions.MEDIA_TYPE)
    # RFC 6266: 한글 이름이라 filename*=utf-8''<퍼센트>(scope3_runs.py 양식과 같은 꼴). django-stubs 에 이 함수가 없다.
    disposition: str = django_http.content_disposition_header(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        as_attachment=True, filename=found.file_name
    )
    response["Content-Disposition"] = disposition
    response["X-Content-Type-Options"] = "nosniff"
    return response


@router.get(
    f"{YEAR_PATH}/template",
    operation_id="inventory_scope12_template",
    response={**ERRORS_404},
    auth=COMPANY_AUTH,
    openapi_extra=_binary("Scope 1·2 일괄업로드 양식(xlsx — 시트 년도·분기·월, Content-Disposition: attachment)"),
)
def template(request: HttpRequest, year: int, scope: Scope = None, site_id: SiteId = None) -> HttpResponse:
    """한 해의 일괄업로드 양식: 숨기지 않은 선택 잎 × 그 잎의 사업장 블록 줄(값 칸 빔). scope 1|2 · siteId 로 거른다."""
    principal = permitted(request, "inventory_scope12_template")
    found = actions.template(company_of(principal), year, scope, site_id)
    if isinstance(found, NotFound | Invalid):
        raise _refused(found)
    return _download(found)


@router.get(
    f"{YEAR_PATH}/export",
    operation_id="inventory_scope12_export",
    response={**ERRORS_404},
    auth=COMPANY_AUTH,
    openapi_extra=_binary("Scope 1·2 데이터 엑셀(xlsx — 시트 다섯, Content-Disposition: attachment)"),
)
def export(request: HttpRequest, year: int, scope: Scope = None) -> HttpResponse:
    """한 해의 데이터 엑셀(지역기반): 사업장별 Scope 합 · 연도별 · 상세(년도·분기·월). scope all|1|2."""
    principal = permitted(request, "inventory_scope12_export")
    found = actions.export(company_of(principal), year, scope)
    if isinstance(found, NotFound | Invalid):
        raise _refused(found)
    return _download(found)


def _upload_refused(found: NotFound | Invalid | Locked) -> ApplicationError:
    match found:
        case NotFound():
            return ApplicationError("not_found", "not_found", NOT_FOUND_YEAR)
        case Locked():
            return ApplicationError("conflict", "locked", LOCKED)
        case Invalid(fields=fields):
            return ApplicationError(
                "validation", "invalid_upload", INVALID_UPLOAD, fields={name: [why] for name, why in fields.items()}
            )


def _declared_length(request: HttpRequest) -> int:
    """CONTENT_LENGTH 머리 값. 없거나 수가 아니면 0(읽은 길이 검사가 남는다)."""
    try:
        return int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return 0


def _refuse_over_limit(length: int) -> None:
    """GHG_UPLOAD_MAX_BYTES 를 넘으면 RequestDataTooBig — 바닥(config/api.py)이 413 `body_too_large` 로 답한다."""
    if length > GHG_UPLOAD_MAX_BYTES:
        raise RequestDataTooBig("요청 본문이 너무 크다")


@router.post(
    f"{YEAR_PATH}/uploads",
    operation_id="inventory_scope12_upload",
    response={200: EntryUploadOut, **TOKEN_BODY_ERROR_RESPONSES, 404: ErrorBody},
    auth=COMPANY_AUTH,
    openapi_extra=UPLOAD_BODY,
)
def upload(request: HttpRequest, year: int) -> EntryUploadOut:
    """일괄업로드 양식을 올린다(본문 = xlsx 바이트 그대로). 빈 칸만 채우고, 하나라도 틀리면 아무것도 쓰지 않는다."""
    principal = permitted(request, "inventory_scope12_upload")
    _refuse_over_limit(_declared_length(request))  # 머리 값이 넘으면 읽기 전에(Django body 의 꼴)
    data = request.read(GHG_UPLOAD_MAX_BYTES + 1)  # request.body 금지(머리말 — 전역 2.5MB)
    _refuse_over_limit(len(data))  # 머리 값만 믿지 않는다 — 읽은 길이로 늘 다시 잰다
    actor = Actor(kind=principal.kind, user_id=int(principal.user_id))
    found = upload_actions.upload(company_of(principal), year, data, actor)
    if isinstance(found, NotFound | Invalid | Locked):
        raise _upload_refused(found)
    return EntryUploadOut(
        added=found.added, filled=found.filled, unchanged=found.unchanged, unresolved=found.unresolved
    )
