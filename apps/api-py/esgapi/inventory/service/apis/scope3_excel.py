"""Scope 3 데이터 엑셀 경로(밴드 S3D1 ① — 결정 MARC-ENT-592). apis/inventory.py 가 이 router 를 「""」 에 붙인다.

    GET /scope3/years/{year}/export   inventory_scope3_export   회사 업무(COMPANY) — 데이터 엑셀(xlsx)

몸: service/actions/scope3_excel.py(읽기만). 꼴은 scope12_excel.py 의 export 그대로: 바이트 응답 · RFC 6266
첨부(한글 이름
→ filename*=utf-8''…) · nosniff. 인증 [company_scoped_auth_or_next, session_cookie] · 차례 permitted(첫 문장) →
company_of(principal) → actions. ★ 회사 id 는 인증 주체에서만 온다(쿼리 칸 0 — Scope 3 은 scope·siteId 거름이 없다).
오류: 해가 범위 밖 422 `fields.year`(scope3_state 꼴) · 그 해 기준 실행 R 없음 404 `not_found`.
`_download` 는 scope12_excel 의 것과 같은 꼴을 옮겨 적었다(다른 경로 모듈 — 0줄 파일이라 묶지 않는다).
"""

from django.http import HttpRequest, HttpResponse
from django.utils import http as django_http
from ninja import Router

from esgapi.core.auth.bearer import company_of, company_scoped_auth_or_next, permitted
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_ERROR_RESPONSES
from esgapi.inventory.service.actions import scope3_excel as actions
from esgapi.inventory.service.utils.ghg_pool import Invalid, NotFound
from esgapi.user.service.apis.auth import session_cookie

router = Router(tags=["인벤토리 Scope 3"])
COMPANY_AUTH = [company_scoped_auth_or_next, session_cookie]
ERRORS_404: dict[int, type[ErrorBody]] = {**TOKEN_ERROR_RESPONSES, 404: ErrorBody}
NOT_FOUND = "그 해의 Scope 3 결과가 없다"
INVALID = "입력을 확인한다"
BINARY: dict[str, object] = {
    "responses": {
        200: {
            "description": "Scope 3 데이터 엑셀(xlsx — 요약 + 카테고리 시트 열넷, Content-Disposition: attachment)",
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
    # RFC 6266: 한글 이름이라 filename*=utf-8''<퍼센트>(scope12_excel.py 와 같은 꼴). django-stubs 에 이 함수가 없다.
    disposition: str = django_http.content_disposition_header(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        as_attachment=True, filename=found.file_name
    )
    response["Content-Disposition"] = disposition
    response["X-Content-Type-Options"] = "nosniff"
    return response


@router.get(
    "/scope3/years/{year}/export",
    operation_id="inventory_scope3_export",
    response={**ERRORS_404},
    auth=COMPANY_AUTH,
    openapi_extra=BINARY,
)
def export(request: HttpRequest, year: int) -> HttpResponse:
    """한 해의 Scope 3 데이터 엑셀: 지금 결과(잠금 핀·제외·계수 고침)의 요약 + 카테고리 시트."""
    principal = permitted(request, "inventory_scope3_export")
    found = actions.export(company_of(principal), year)
    if isinstance(found, NotFound | Invalid):
        raise _refused(found)
    return _download(found)
