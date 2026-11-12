"""영문번역의 경로 여덟. config/api.py 가 이 router 를 /translation 아래에 Bearer 인증(머리가 없으면 옛 교환 쿠키,
K2b)을 꽂아 건다(/greenwash 와 같은 auth).

    GET  /translation/runs/{run_id}/result     한 실행의 결과(translation.result@1 — done·rejected 판별 유니온)   회사
    GET  /translation/runs/{run_id}/layout     PDF 실행의 블록·좌표 결과(translation.layout@1 — TRS3)          회사
    POST /translation/glossary/read            용어집 엑셀(맨 바이트 본문) → 짝 목록 | 거절 갈래(둘 다 200)    회사
    GET  /translation/glossary/template        빈 용어집 양식(xlsx)                                          회사
    GET  /translation/batches                  묶음 목록 한 쪽((문서, 묶음) 하나가 한 줄 — TR3b)                  회사
    GET  /translation/documents/{document_id}/batches/{batch_key}
                                               묶음 하나(목록 줄과 같은 꼴 + truncated)                      회사
    GET  /translation/documents/{document_id}/batches/{batch_key}/archive
                                               [모두 받기] — 끝난 파트의 자동수정 병기본 zip                    회사
    GET  /translation/documents/{document_id}/pages   올린 docx·txt 의 [PAGE n] 최댓값(그리드 표시용 — TRP6)      회사

몸: service/actions/result.py · service/actions/layout.py(layout@1 결과 행 그대로 — 워드 실행은 404, TRS3) ·
service/actions/batches.py(묶음 둘 — MARC-ENT-392·393) ·
service/actions/pages.py(문서 쪽 수 — 원본을 요청마다 읽어 셈, 못 세면 null, MARC-ENT-452) ·
service/actions/glossary.py(용어집 둘 — 상태 없음, 테넌트 행을 읽지 않아 company_of 를
부르지 않는다. 그린워싱 기본 단어 목록 꼴이라 운영 관리자도 회사를 고르지 않고 같은 결과). 경로는 models 를
import 하지 않는다(`.importlinter` 계약 라) — 갈래를 응답으로 바꿀 뿐이다. 실행 만들기·상태는 runs 의
경로(POST /runs {module:"translation"}·GET /runs/{id})다.
오류: 실행·묶음 없음·남의 회사·영문번역 아님 404 NOT_FOUND · 끝나지 않음 409 RUN_NOT_DONE(그린워싱 결과 경로와 같은
code·글).
★ id 는 int 다. 회사 id 는 company_of 에서만 온다 — 고객사 사용자는 토큰의 회사, 운영 관리자는 작업 회사(MARC-ENT-374,
OP2). 쿼리·본문에 그 칸이 없다.
"""

from typing import Annotated

from django.http import FileResponse, HttpRequest, HttpResponse
from ninja import Query, Router, Schema
from pydantic import Field

from esgapi.core.auth.bearer import company_of, permitted
from esgapi.core.conf import now
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES
from esgapi.core.service.services.audit import record_event
from esgapi.translation.contracts.batch_shapes import BatchState, TranslationBatchDetail, TranslationBatchPage
from esgapi.translation.contracts.glossary_shapes import TranslationGlossaryRead
from esgapi.translation.contracts.layout_shapes import TranslationLayout
from esgapi.translation.contracts.pages_shapes import TranslationDocumentPages
from esgapi.translation.contracts.shapes import TranslationResult
from esgapi.translation.service.actions import archive as archive_actions
from esgapi.translation.service.actions import batches as batch_actions
from esgapi.translation.service.actions import glossary as glossary_actions
from esgapi.translation.service.actions import layout as layout_actions
from esgapi.translation.service.actions import pages as page_actions
from esgapi.translation.service.actions import result as actions

router = Router(tags=["영문번역"])

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
    operation_id="translation_result_get",
    response={200: TranslationResult, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def result_get(request: HttpRequest, run_id: RunId) -> dict[str, object]:
    """한 실행의 결과(translation.result@1). 번역을 돌렸으면 status done, 시작 전에 막혔으면 status rejected."""
    principal = permitted(request, "translation_result_get")
    found = actions.run_result(company_id=company_of(principal), run_id=run_id)
    if isinstance(found, actions.NotFound | actions.RunNotDone):
        raise _refused(found)
    return found


@router.get(
    "/runs/{run_id}/layout",
    operation_id="translation_layout_get",
    response={200: TranslationLayout, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def layout_get(request: HttpRequest, run_id: RunId) -> dict[str, object]:
    """PDF 실행의 블록·좌표 결과(translation.layout@1). 결과 행 그대로 — 파서 앞·파서 거절이면 status rejected 에
    variants 빈 목록. 워드 흐름의 실행에는 이 결과가 없어 404 다(layout 있음 판별은 GET /runs/{id} 의 resultShapes)."""
    principal = permitted(request, "translation_layout_get")
    found = layout_actions.run_layout(company_id=company_of(principal), run_id=run_id)
    if isinstance(found, actions.NotFound | actions.RunNotDone):
        raise _refused(found)
    return found


# 용어집 엑셀은 맨 바이트 본문이다(multipart 경로가 없다 — 발주서 처분). 본문 꼴은 schema 가 아니라 이것으로만 선언한다.
# 본문 상한은 DATA_UPLOAD_MAX_MEMORY_SIZE(넘으면 config/api.py 의 413 body_too_large).
GLOSSARY_READ_BODY = {
    "requestBody": {
        "required": True,
        "content": {glossary_actions.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
    }
}
GLOSSARY_TEMPLATE_RESPONSE = {
    "responses": {
        200: {
            "description": "빈 용어집 양식의 바이트(Content-Disposition: attachment)",
            "content": {glossary_actions.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
        }
    }
}


@router.post(
    "/glossary/read",
    operation_id="translation_glossary_read",
    response={200: TranslationGlossaryRead, **TOKEN_BODY_ERROR_RESPONSES},
    openapi_extra=GLOSSARY_READ_BODY,
)
def glossary_read(request: HttpRequest) -> dict[str, object]:
    """용어집 엑셀(「한국어 | 영문」 두 열, 첫 시트) 읽기. 본문은 xlsx 파일의 바이트 그대로다. 읽었으면
    `{ok: true, pairs, rowCount}`, 못 읽었으면 `{ok: false, kind, row, message}` — 둘 다 200(빈 본문·JSON 본문은
    not_xlsx). 아무것도 저장하지 않는다. 웹은 pairs 를 실행 옵션 glossary.base·final 에 그대로 싣는다."""
    permitted(request, "translation_glossary_read")
    return dict(glossary_actions.read(request.body))


@router.get(
    "/glossary/template",
    operation_id="translation_glossary_template",
    response={**TOKEN_ERROR_RESPONSES},
    openapi_extra=GLOSSARY_TEMPLATE_RESPONSE,
)
def glossary_template(request: HttpRequest) -> HttpResponse:
    """빈 용어집 양식 내려받기(xlsx 한 파일 — 시트 「용어집」, 1행 「한국어」「영문」, 데이터 행 0, 매번 같은
    바이트)."""
    permitted(request, "translation_glossary_template")
    response = HttpResponse(glossary_actions.template(), content_type=glossary_actions.MEDIA_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{glossary_actions.FILE_NAME}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


# ── 묶음(밴드 TR3b — MARC-ENT-392·393) ──


class TranslationBatchListQuery(Schema):
    """`GET /translation/batches` 의 조회 인자. 거름은 묶은 뒤·자르기 전이고 count·isNext 는 거른 뒤 묶음 수다."""

    documentId: int | None = Field(default=None, ge=1, description="그 문서의 묶음만")
    state: BatchState | None = Field(default=None, description="묶음 상태(파트 최신 실행만 본다)")
    mine: bool = Field(default=False, description="true 면 내가 올린 문서의 묶음만(운영 관리자도 같은 규칙)")
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


BatchKey = Annotated[str, Field(max_length=64, description="묶음 열쇠 — batchId(소문자 uuid) 또는 run-<실행 id>")]
DocumentId = Annotated[int, Field(description="문서 id")]


@router.get(
    "/batches",
    operation_id="translation_batches_list",
    response={200: TranslationBatchPage, **TOKEN_ERROR_RESPONSES},
)
def batches_list(request: HttpRequest, query: Query[TranslationBatchListQuery]) -> TranslationBatchPage:
    """이 회사의 영문번역 묶음 한 쪽((문서, 묶음) 하나가 한 줄 — 묶음 안 가장 새 실행이 새 것 먼저). 파트마다 최신
    실행·앞 회차·단계·요약(digest)을 싣고, 옵션 본문·결과 본문은 싣지 않는다."""
    principal = permitted(request, "translation_batches_list")
    return batch_actions.batches(
        company_id=company_of(principal),
        user_id=int(principal.user_id),
        document_id=query.documentId,
        state=query.state,
        mine=query.mine,
        limit=query.limit,
        offset=query.offset,
    )


@router.get(
    "/documents/{document_id}/batches/{batch_key}",
    operation_id="translation_batch_get",
    response={200: TranslationBatchDetail, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def batch_get(request: HttpRequest, document_id: DocumentId, batch_key: BatchKey) -> TranslationBatchDetail:
    """그 문서의 묶음 하나(목록 줄과 같은 꼴 + truncated). 꼴 밖 열쇠·없는 묶음·남의 회사 문서·batchId 있는 실행의
    run-<id> 는 404."""
    principal = permitted(request, "translation_batch_get")
    found = batch_actions.batch(company_id=company_of(principal), document_id=document_id, batch_key=batch_key)
    if isinstance(found, batch_actions.NotFound):
        raise ApplicationError("not_found", "not_found", "그런 묶음이 없다")
    return found


ARCHIVE_RESPONSE = {
    "responses": {
        200: {
            "description": "zip 의 바이트(Content-Disposition: attachment). 머리 X-Archive-Missing = 이름은 있는데"
            " 파일이 없어 뺀 항목 수(늘 실음, 0 포함)",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        }
    }
}


@router.get(
    "/documents/{document_id}/batches/{batch_key}/archive",
    operation_id="translation_batch_archive",
    response={**NOT_FOUND, **TOKEN_ERROR_RESPONSES},
    openapi_extra=ARCHIVE_RESPONSE,
)
def batch_archive(request: HttpRequest, document_id: DocumentId, batch_key: BatchKey) -> FileResponse:
    """[모두 받기] — 묶음의 파트마다 최신 실행이 끝났으면 문체마다 자동수정 병기본(`<part>-<파일 이름>`)을 zip 하나로.
    없는 묶음 404 · 넣을 것이 0 이면 409 NO_FINISHED_PARTS · 크기 합 상한을 넘으면 409 ARCHIVE_TOO_LARGE(다시 해도 같은
    거절) · 저장소 503 셋은 실행 파일 내려받기와 같은 code·글."""
    principal = permitted(request, "translation_batch_archive")
    company_id = company_of(principal)
    found = archive_actions.archive(company_id=company_id, document_id=document_id, batch_key=batch_key)
    if isinstance(found, batch_actions.NotFound):
        raise ApplicationError("not_found", "not_found", "그런 묶음이 없다")
    if isinstance(found, archive_actions.NothingFinished):
        raise ApplicationError("conflict", "no_finished_parts", "내려받을 끝난 파트가 없다")
    if isinstance(found, archive_actions.TooLarge):
        raise ApplicationError(
            "conflict", "archive_too_large", "내려받을 파일이 너무 크다. 파트마다 따로 내려받아 달라"
        )
    try:
        record_event(
            at=now(),
            company_id=company_id,
            actor_kind=principal.kind,
            actor_user_id=int(principal.user_id),
            action="download",
            event="translation_batch_downloaded",
            result="success",
            target_kind="document",
            target_id=document_id,
            target_label=found.name,
        )
        # 흘려보내고 응답 끝에 닫는다(MARC-ISSUE-324). 이 줄 뒤로는 응답이 닫는다.
        response = FileResponse(found.data, content_type="application/zip")
    except BaseException:
        found.data.close()  # 응답에 넘기기 전에 던지면 spool(임시 파일일 수 있음)을 GC 에 맡기지 않는다(MARC-ISSUE-399)
        raise
    response["Content-Disposition"] = f'attachment; filename="{found.name}"'  # 이름은 ASCII 뿐(숫자·열쇠 앞 8)
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Archive-Missing"] = str(found.missing)
    return response


@router.get(
    "/documents/{document_id}/pages",
    operation_id="translation_document_pages",
    response={200: TranslationDocumentPages, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def document_pages(request: HttpRequest, document_id: DocumentId) -> TranslationDocumentPages:
    """올린 문서의 [PAGE n] 최댓값(새 번역 화면의 쪽 그리드 표시용 — 엔진의 범위 판정은 그대로). 원본을 요청마다 읽어
    센다(DB·캐시 0). 못 세면(태그 없음·PDF·저장소 실패·꼴·크기) 200 에 pageCount null. 없는 문서·남의 회사 문서는
    404."""
    principal = permitted(request, "translation_document_pages")
    found = page_actions.document_pages(company_id=company_of(principal), document_id=document_id)
    if isinstance(found, page_actions.NotFound):
        raise ApplicationError("not_found", "not_found", "그런 문서가 없다")
    return {"documentId": found.document_id, "pageCount": found.page_count}
