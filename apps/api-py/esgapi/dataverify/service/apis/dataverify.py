"""데이터 검증의 경로 넷(밴드 DV1e·DV1g·DVX1). config/api.py 가 이 router 를 /dataverify 아래에 Bearer 인증(머리가
없으면 옛 교환 쿠키, K2b)을 꽂아 건다(/greenwash·/translation 과 같은 auth).

    GET /dataverify/runs/{run_id}/result     한 실행의 결과(dataverify.result@2)   회사 업무(고객사 사용자·운영 관리자)
    GET /dataverify/runs                     실행 목록 한 쪽(새 것 먼저 — DV1g)     회사 업무(고객사 사용자·운영 관리자)
    POST /dataverify/edk/read                EDK 엑셀(맨 바이트) → data | 거절(둘 다 200 — DVX1)  회사 업무(같음)
    GET /dataverify/edk/template             EDK 엑셀 양식(xlsx — DVX1)              회사 업무(같음)

몸: service/actions/result.py · service/actions/runs.py(목록 — 거름은 status 여러 값·mine, 기업명·보고연도 거름은
없다 MARC-ISSUE-336) · service/actions/edk.py(엑셀 둘 — 상태 없음, 테넌트 행을 읽지 않아 company_of 를 부르지
않는다. 운영 관리자도 회사를 고르지 않고 같은 결과. 원본 파일은 저장하지 않는다). 경로는 models 를 import 하지
않는다(`.importlinter` 계약 라) — 갈래를 응답으로 바꿀 뿐이다. 실행 만들기·상태·엑셀은 runs 의
경로(POST /runs {module:"dataverify"}·GET /runs/{id}·
GET /runs/{id}/files/dataverify-report.xlsx)다. 운영 관리자는 작업 회사(company_of)의 실행을 읽는다(MARC-ENT-390).
오류: 실행 없음·남의 회사·데이터 검증 아님·끝났는데 @2 결과 없음 404 NOT_FOUND · 끝나지 않음(queued·processing·
failed) 409 RUN_NOT_DONE(그린워싱·영문번역 결과 경로와 같은 code·글). 단계의 실패(비용 상한·잘림)는 done 결과 안의
failure 다.
★ id 는 int 다. 테넌트 id 는 인증 주체(토큰)에서만 온다(쿼리·본문에 그 칸이 없다).
"""

from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils import http as django_http
from ninja import Query, Router, Schema
from pydantic import Field

from esgapi.core.auth.bearer import company_of, permitted
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES
from esgapi.dataverify.contracts.edk_read_shapes import DataverifyEdkRead
from esgapi.dataverify.contracts.run_list_shapes import DataverifyRunPage, DataverifyRunStatus
from esgapi.dataverify.contracts.shapes import DataverifyResult
from esgapi.dataverify.service.actions import edk as edk_actions
from esgapi.dataverify.service.actions import result as actions
from esgapi.dataverify.service.actions import runs as run_actions

router = Router(tags=["데이터 검증"])

# operation_id 는 손으로 적는다(`<모듈>_<동작>`). 표는 esgapi/config/tests/test_api_contract.py 가 못 박는다.

NOT_FOUND: dict[int, type[ErrorBody]] = {404: ErrorBody}
"""없는 실행(404). 409 는 TOKEN_ERROR_RESPONSES 에 든다."""


def _refused(refusal: actions.Refusal) -> ApplicationError:
    """actions 의 거절 갈래 → 오류(config/api.py 가 상태 코드로 바꾼다)."""
    match refusal:
        case actions.NotFound():
            return ApplicationError("not_found", "not_found", "그런 실행이 없다")
        case actions.RunNotDone():
            return ApplicationError("conflict", "run_not_done", "실행이 아직 끝나지 않았다")


RunId = Annotated[int, Field(description="실행 id")]


@router.get(
    "/runs/{run_id}/result",
    operation_id="dataverify_result_get",
    response={200: DataverifyResult, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def result_get(request: HttpRequest, run_id: RunId) -> dict[str, object]:
    """한 실행의 결과(dataverify.result@2). 단계마다 done·failed·not_run 이고, 실패한 단계는 failure 에 갈래(kind)를
    싣는다."""
    principal = permitted(request, "dataverify_result_get")
    found = actions.run_result(company_id=company_of(principal), run_id=run_id)
    if isinstance(found, actions.NotFound | actions.RunNotDone):
        raise _refused(found)
    return found


# ── 실행 목록(밴드 DV1g — MARC-ISSUE-336·MARC-ENT-420) ──


class DataverifyRunListQuery(Schema):
    """`GET /dataverify/runs` 의 조회 인자. count·isNext 는 거른 뒤 실행 수다."""

    status: list[DataverifyRunStatus] | None = Field(
        default=None, description="이 상태들만(여러 번 — ?status=queued&status=processing). 없으면 전부"
    )
    mine: bool = Field(default=False, description="true 면 내가 만든 실행만(운영 관리자도 같은 규칙)")
    limit: int = Field(default=20, ge=1, le=20)
    offset: int = Field(default=0, ge=0)


@router.get(
    "/runs",
    operation_id="dataverify_runs_list",
    response={200: DataverifyRunPage, **TOKEN_ERROR_RESPONSES},
)
def runs_list(request: HttpRequest, query: Query[DataverifyRunListQuery]) -> DataverifyRunPage:
    """이 회사의 데이터 검증 실행 한 쪽(새 것 먼저). 줄마다 입력 출처·기업명·보고연도·항목 수·만든 사람·실패/지금
    단계·(끝났으면) 단계 머리와 검토 셈(요약 dataverify.digest@1)을 싣고, 옵션의 입력 데이터·결과 본문은 싣지 않는다."""
    principal = permitted(request, "dataverify_runs_list")
    return run_actions.runs(
        company_id=company_of(principal),
        user_id=int(principal.user_id),
        statuses=query.status,
        mine=query.mine,
        limit=query.limit,
        offset=query.offset,
    )


# ── EDK 인벤토리 엑셀(밴드 DVX1 — MARC-ENT-505 §2.1 ③) ──
# 엑셀은 맨 바이트 본문이다(multipart 경로가 없다 — 영문번역 용어집·중대성평가 가치사슬 읽기와 같은 꼴). 본문 꼴은
# schema 가 아니라 이것으로만 선언한다. 본문 상한은 DATA_UPLOAD_MAX_MEMORY_SIZE(넘으면 config/api.py 의 413
# body_too_large).
EDK_READ_BODY = {
    "requestBody": {
        "required": True,
        "content": {edk_actions.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
    }
}
EDK_TEMPLATE_RESPONSE = {
    "responses": {
        200: {
            "description": "EDK 인벤토리 엑셀 양식의 바이트(Content-Disposition: attachment)",
            "content": {edk_actions.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
        }
    }
}


@router.post(
    "/edk/read",
    operation_id="dataverify_edk_read",
    response={200: DataverifyEdkRead, **TOKEN_BODY_ERROR_RESPONSES},
    openapi_extra=EDK_READ_BODY,
)
def edk_read(request: HttpRequest) -> dict[str, object]:
    """EDK 인벤토리 엑셀 읽기(지금 양식 — 첫 시트 1행의 열 이름 「ID·테마·항목·대분류·중분류·소분류·입력 방식·단위·
    메모·핵심데이터」와 「YYYY년」 연도 열). 본문은 xlsx 파일의 바이트 그대로다. 읽었으면 `{ok: true, data, itemCount,
    skipped, years, skippedEmptyRows, ignoredColumns}`(data 는 검증 대상 테마만), 못 읽었으면 `{ok: false, kind, row,
    column, message}` — 둘 다 200(빈 본문·JSON 본문은 not_xlsx). 아무것도 저장하지 않는다. 웹은 data 를 실행 입력
    input.data 에 싣는다."""
    permitted(request, "dataverify_edk_read")
    return dict(edk_actions.read(request.body))


class DataverifyEdkTemplateQuery(Schema):
    """`GET /dataverify/edk/template` 의 조회 인자."""

    year: int | None = Field(
        default=None, ge=1002, le=9999, description="양식의 마지막 연도 열(네 자리). 없으면 서버 오늘의 해 − 1"
    )


@router.get(
    "/edk/template",
    operation_id="dataverify_edk_template",
    response={**TOKEN_ERROR_RESPONSES},
    openapi_extra=EDK_TEMPLATE_RESPONSE,
)
def edk_template(request: HttpRequest, query: Query[DataverifyEdkTemplateQuery]) -> HttpResponse:
    """EDK 인벤토리 엑셀 양식 내려받기(xlsx 한 파일 — 시트 「인벤토리 데이터」 1행 머리 14열(연도 열 셋)과 가상 예시
    한 줄, 시트 「작성 안내」. 같은 year 면 매번 같은 바이트)."""
    permitted(request, "dataverify_edk_template")
    response = HttpResponse(edk_actions.template(query.year), content_type=edk_actions.MEDIA_TYPE)
    # RFC 6266: 한글 이름이라 filename*=utf-8''<퍼센트> 하나(user/service/apis/run_logs.py 와 같은 꼴). django-stubs 에
    # 이 함수가 없다(Django 4.2+).
    disposition: str = django_http.content_disposition_header(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        as_attachment=True, filename=edk_actions.FILE_NAME
    )
    response["Content-Disposition"] = disposition
    response["X-Content-Type-Options"] = "nosniff"
    return response
