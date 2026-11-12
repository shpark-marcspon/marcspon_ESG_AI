"""Scope 3 코랩 흐름의 경로 셋(밴드 S3K1 ③ · S3Q1 ①). apis/inventory.py 가 이 router 를 /inventory 아래에 붙인다.

    GET /inventory/scope3/template                빈 입력 양식 v2.2(xlsx)                회사 업무(고객사·운영 관리자)
    GET /inventory/scope3/runs/{run_id}/result    한 실행의 결과(scope3.colab.result@1)  회사 업무(같음)
    GET /inventory/scope3/runs/{run_id}/original  그 실행에 올린 엑셀 원본(바이트 그대로)  회사 업무(같음 — S3Q1)

몸: service/actions/scope3_runs.py. 실행 만들기·상태는 runs 의 경로(POST /runs {module:"inventory.scope3"}·
GET /runs/{id})다. 운영 관리자는 작업 회사(company_of)의 실행을 읽는다(469-4). 양식은 테넌트 행을 읽지 않아
company_of 를 부르지 않는다(dataverify_edk_template 꼴).
오류: 실행 없음·남의 회사·Scope 3 아님·코랩 결과 없음 404 NOT_FOUND · 끝나지 않음(queued·processing·failed) 409
RUN_NOT_DONE(데이터 검증·그린워싱·영문번역 결과 경로와 같은 code·글) · 양식이 배포에 없음 503 UNAVAILABLE.
결과의 수는 코랩 그대로 repr(float) 글자다(MARC-ENT-442 — 표기는 웹 한 곳).
원본(S3Q1, MARC-ENT-639): 실행 상태를 보지 않는다. 없음·남의 회사·Scope 3 아님·문서 없음·안 올라옴·저장소에 원본
없음 404 NOT_FOUND · 저장소 없음·거부·닿지 못함 503 · 상한 넘음 409 OBJECT_TOO_LARGE · 올림 뒤 바뀜 409 OBJECT_CHANGED.
감사 줄 하나(action download, event document_downloaded — core 원본 내려받기와 같은 이름, MARC-ENT-295). 이름은 올린
이름 그대로.
★ id 는 int 다. 테넌트 id 는 인증 주체(토큰)에서만 온다(쿼리·본문에 그 칸이 없다).
"""

from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils import http as django_http
from ninja import Router
from pydantic import Field

from esgapi.core.auth.bearer import company_of, company_scoped_auth_or_next, permitted
from esgapi.core.conf import now
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_ERROR_RESPONSES
from esgapi.core.service.services.audit import record_event
from esgapi.inventory.contracts.shapes import Scope3ColabResult
from esgapi.inventory.flows.binding_157 import MODULE
from esgapi.inventory.service.actions import scope3_runs as actions
from esgapi.user.service.apis.auth import session_cookie

router = Router(tags=["인벤토리 Scope 3"])

NOT_FOUND: dict[int, type[ErrorBody]] = {404: ErrorBody}
"""없는 실행(404). 409·503 은 TOKEN_ERROR_RESPONSES 에 든다."""

TEMPLATE_RESPONSE = {
    "responses": {
        200: {
            "description": "Scope 3 빈 입력 양식의 바이트(판·sha 는 data/README.md, Content-Disposition: attachment)",
            "content": {actions.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
        }
    }
}

ORIGINAL_RESPONSE = {
    "responses": {
        200: {
            "description": "그 실행에 올린 엑셀 원본의 바이트(Content-Disposition: attachment — 올린 이름 그대로)",
            "content": {
                actions.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}},
                actions.XLS_MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}},
                actions.OTHER_MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}},
            },
        }
    }
}

RunId = Annotated[int, Field(description="실행 id")]


def _refused(refusal: actions.Refusal) -> ApplicationError:
    """actions 의 거절 갈래 → 오류(config/api.py 가 상태 코드로 바꾼다)."""
    match refusal:
        case actions.NotFound():
            return ApplicationError("not_found", "not_found", "그런 실행이 없다")
        case actions.RunNotDone():
            return ApplicationError("conflict", "run_not_done", "실행이 아직 끝나지 않았다")


@router.get(
    "/scope3/template",
    operation_id="inventory_scope3_template",
    response={**TOKEN_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
    openapi_extra=TEMPLATE_RESPONSE,
)
def template(request: HttpRequest) -> HttpResponse:
    """Scope 3 빈 입력 양식 내려받기(마크스폰 양식 — 판·sha 는 data/README.md, 매번 같은 바이트)."""
    permitted(request, "inventory_scope3_template")
    content = actions.template()
    if isinstance(content, actions.Unavailable):
        raise ApplicationError("unavailable", "unavailable", "Scope 3 양식이 배포에 없다. 운영자에게 알려 달라")
    response = HttpResponse(content, content_type=actions.MEDIA_TYPE)
    # RFC 6266: 한글 이름이라 filename*=utf-8''<퍼센트> 하나(dataverify_edk_template 과 같은 꼴). django-stubs 에
    # 이 함수가 없다(Django 4.2+).
    disposition: str = django_http.content_disposition_header(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        as_attachment=True, filename=actions.FILE_NAME
    )
    response["Content-Disposition"] = disposition
    response["X-Content-Type-Options"] = "nosniff"
    return response


@router.get(
    "/scope3/runs/{run_id}/result",
    operation_id="inventory_scope3_result_get",
    response={200: Scope3ColabResult, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
)
def result_get(request: HttpRequest, run_id: RunId) -> dict[str, object]:
    """한 실행의 결과(scope3.colab.result@1 — done 이면 시트·행·합계, rejected 면 갈래와 까닭)."""
    principal = permitted(request, "inventory_scope3_result_get")
    found = actions.run_result(company_id=company_of(principal), run_id=run_id)
    if isinstance(found, actions.NotFound | actions.RunNotDone):
        raise _refused(found)
    return found


def _original_refused(refusal: actions.NotFound | actions.Unavailable | actions.Conflict) -> ApplicationError:
    """원본 거절 갈래 → 오류(core 원본 내려받기와 같은 code 글자)."""
    match refusal:
        case actions.NotFound():
            return ApplicationError("not_found", "not_found", "그 실행의 원본 파일이 없다")
        case actions.Conflict(why="object_too_large"):
            return ApplicationError("conflict", "object_too_large", "원본이 내려받기 상한보다 크다")
        case actions.Conflict():
            return ApplicationError("conflict", "object_changed", "올림 확인 뒤 원본이 바뀌었다")
        case actions.Unavailable(why="storage_unconfigured"):
            return ApplicationError(
                "unavailable", "storage_unconfigured", "이 서버에 원본 파일 저장소가 준비되어 있지 않다"
            )
        case actions.Unavailable(why="storage_denied"):
            return ApplicationError("unavailable", "storage_denied", "저장소가 요청을 거절했다")
        case actions.Unavailable():
            return ApplicationError(
                "unavailable", "storage_unavailable", "저장소에 닿지 못했다. 잠시 뒤 다시 시도해 달라"
            )


@router.get(
    "/scope3/runs/{run_id}/original",
    operation_id="inventory_scope3_original_get",
    response={**NOT_FOUND, **TOKEN_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
    openapi_extra=ORIGINAL_RESPONSE,
)
def original_get(request: HttpRequest, run_id: RunId) -> HttpResponse:
    """그 실행에 올린 엑셀 원본을 내려받는다(바이트 그대로 · 올린 이름 · `attachment`). 실행 상태는 보지 않는다."""
    principal = permitted(request, "inventory_scope3_original_get")
    company_id = company_of(principal)
    found = actions.original(company_id=company_id, run_id=run_id)
    if not isinstance(found, actions.Original):
        raise _original_refused(found)
    record_event(
        at=now(),
        company_id=company_id,
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        action="download",
        event="document_downloaded",
        result="success",
        target_kind="document",
        target_id=found.document_id,
        target_label=found.file_name,
        module=MODULE,
    )
    response = HttpResponse(found.content, content_type=found.media_type)
    disposition: str = django_http.content_disposition_header(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        as_attachment=True, filename=found.file_name
    )
    response["Content-Disposition"] = disposition
    response["X-Content-Type-Options"] = "nosniff"
    return response
