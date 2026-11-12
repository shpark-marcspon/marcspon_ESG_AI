"""core 의 경로: 문서 일곱. config/api.py 가 이 router 를 /documents 아래에 **세션 인증을 꽂아** 건다.

    POST  /documents                         문서 행을 만들고 서명된 올리기 주소를 내준다       고객사 사용자
    GET   /documents                         문서 목록(보고 연도·이름·올린 사람·사슬의 마지막)   고객사 사용자
    POST  /documents/{document_id}/confirm   저장소에 물어 올라왔는지 확인하고 일감을 queued 로   고객사 사용자
    GET   /documents/{document_id}           문서와 일감의 상태                                  고객사 사용자
    PATCH /documents/{document_id}           보고 연도·앞 판을 정한다                           고객사 사용자
    GET   /documents/{document_id}/versions  그 문서를 포함한 판의 사슬                         고객사 사용자
    GET   /documents/{document_id}/file      원본 PDF 를 서버를 거쳐 내려받는다                 고객사 사용자

★ 몸은 X1b-2a 가 채웠다(계약은 XC — 목록·versions 의 501 과 만들기 두 칸의 501 을 걷음, PATCH·원본 내려받기를 더함).
  만들기는 reportYear 를 적고 previousDocumentId 에 값이 있으면 쓰기 앞에서 422 `previous_via_patch` 다(앞 판은 PATCH
  로만 — 올리기가 끊겨 버려진 행이 앞 판을 쥐지 않게). 세 경로의 document_id 는 숫자다(K1u-b — 문서 id 가 BigInt).
  경로 함수의 docstring(openapi 의 description)에는 이 일시적인 사정을 적지 않는다(이 머리 글에만).

하는 일은 셋뿐이다: 요청에서 값을 꺼낸다 → services·selectors 를 부른다 → 갈래를 응답(schemas)으로 바꾼다.
models 를 직접 import 하지 않는다(`.importlinter` 계약 라).

★ 서버는 올릴 파일 바이트를 받지 않는다. 만들기의 본문은 이름과 크기(와 보고 연도)뿐이고 올림 확인에는 본문이 없다.
  클라이언트가 내준 주소로 저장소에 직접 PUT 한다. 내려받기(원본)는 서버를 거친다: 저장소에서 바이트를 읽어
  (상한 max_upload_bytes) 표에 적힌 ETag 와 견주고(다르면 409 `object_changed` — 올림 확인 뒤 같은 키에 다시 올림),
  감사 줄 하나(action download — MARC-ENT-295)를 남긴 뒤 `application/pdf`·`attachment`·`nosniff` 로 낸다
  (SecurityMiddleware 가 없어 nosniff 는 이 경로가 단다 — 감독 처분).
★ 쿠키 인증 객체(`session_cookie`)는 user 에 있고 core 는 user 를 import 하지 못한다(계약 가). 그래서 이 파일은
  `auth=` 를 적지 않는다: config/api.py 가 `add_router("/documents", router, auth=[company_scoped_auth_or_next,
  session_cookie])` 로 꽂는다 — Bearer 를 먼저 보고 머리가 없으면 옛 교환 쿠키(K2b, 사용자 결정 ㉠).
★ 회사·사용자 id 는 세션에서만 온다(본문·쿼리·헤더에 그 칸이 없다). 다른 회사의 문서는 「없다」와 구별되지
  않는다(둘 다 404 — 경로 id 든 PATCH 본문의 previousDocumentId 든). 문서 id 는 숫자라 셀 수 있다 — 이웃 id 를
  넣어도 남의 회사 것은 404 다. 목록의 uploadedBy 가 남의 회사 사용자면 빈 쪽이다(회사 조건이 먼저).
★ 4xx·5xx 로 답하면 미들웨어가 되돌린다 → 거절을 행에 적을 수 없다(service/services/documents.py 의 머리말).
★ services.default_storage·services.max_upload_bytes 는 **부를 때마다 모듈 속성으로** 읽는다
  (`from … import default_storage` 로 들이지 않는다: 테스트가 그 이름을 바꿔 끼운다).
"""

from django.http import HttpRequest, HttpResponse
from django.utils import http as django_http
from ninja import Query, Router, Status

from esgapi.core.auth.bearer import company_of, permitted
from esgapi.core.calc.documents import BadTenantId
from esgapi.core.calc.versions import ChainCycle, ChainFork, ChainSelf, ChainTooLong
from esgapi.core.conf import now
from esgapi.core.exceptions import ApplicationError, ErrorBody, ErrorDetail
from esgapi.core.resources.ports.storage import (
    ObjectMissing,
    ObjectStorage,
    ObjectTooLarge,
    StorageDenied,
    StorageUnavailable,
)
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES
from esgapi.core.service.schemas.documents import (
    DocumentCreatedOut,
    DocumentIn,
    DocumentListItemOut,
    DocumentListQuery,
    DocumentOut,
    DocumentPageOut,
    DocumentPatchIn,
    DocumentStatusOut,
    JobOut,
    UploadOut,
)
from esgapi.core.service.selectors import documents as selectors
from esgapi.core.service.services import documents as services
from esgapi.core.service.services.audit import record_event

router = Router(tags=["문서"])

# operation_id 는 손으로 적는다(`<모듈>_<동작>`). 표는 esgapi/config/tests/test_api_contract.py 가 못 박는다.

PDF_RESPONSE = {
    "responses": {
        200: {
            "description": "원본 PDF 의 바이트(Content-Disposition: attachment)",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        }
    }
}


def _storage() -> ObjectStorage:
    storage = services.default_storage()
    if storage is None:
        raise ApplicationError("unavailable", "storage_unconfigured", "이 서버에 원본 파일 저장소가 준비되어 있지 않다")
    return storage


def _not_found() -> ApplicationError:
    return ApplicationError("not_found", "not_found", "그런 문서가 없다")


def _not_uploaded() -> ApplicationError:
    return ApplicationError("conflict", "not_uploaded", "저장소에 아직 올라오지 않았다")


def _storage_failed(result: StorageDenied | StorageUnavailable) -> ApplicationError:
    if isinstance(result, StorageDenied):
        return ApplicationError("unavailable", "storage_denied", "저장소가 요청을 거절했다")
    return ApplicationError("unavailable", "storage_unavailable", "저장소에 닿지 못했다. 잠시 뒤 다시 시도해 달라")


def _chain_refused(result: ChainSelf | ChainFork | ChainCycle | ChainTooLong) -> ApplicationError:
    if isinstance(result, ChainSelf):
        return ApplicationError("validation", "version_chain_self", "문서는 자기 자신의 앞 판이 될 수 없다")
    if isinstance(result, ChainFork):
        return ApplicationError("conflict", "version_chain_fork", "그 앞 판에는 이미 다른 뒤 판이 있다")
    if isinstance(result, ChainCycle):
        return ApplicationError("conflict", "version_chain_cycle", "판 사슬이 돌게 된다(앞 판이 이 문서의 뒤 판이다)")
    return ApplicationError("conflict", "version_chain_too_long", "판 사슬이 너무 길다")


def _document_out(document: selectors.Document) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        fileName=document.file_name,
        status=document.status,
        sizeBytes=document.size_bytes,
        etag=document.etag,
        createdAt=document.created_at,
        uploadedAt=document.uploaded_at,
        reportYear=document.report_year,
        previousDocumentId=document.previous_document_id,
        pageCount=document.page_count,
        hasText=document.has_text,
    )


def _user_id(uploaded_by: str) -> int | None:
    """표의 올린 사람(글자)을 사용자 id 로. 숫자 글자가 아니면(옛 교환 쿠키의 sub 등) None."""
    return int(uploaded_by) if uploaded_by.isascii() and uploaded_by.isdigit() else None


def _status_out(document: selectors.Document, jobs: tuple[selectors.Job, ...]) -> DocumentStatusOut:
    return DocumentStatusOut(
        document=_document_out(document),
        jobs=[
            JobOut(
                id=job.id,
                kind=job.kind,
                status=job.status,
                attempts=job.attempts,
                errorCode=job.error_code,
                errorMessage=job.error_message,
                summary=job.summary,
                createdAt=job.created_at,
                finishedAt=job.finished_at,
            )
            for job in jobs
        ],
    )


@router.post(
    "",
    operation_id="core_documents_create",
    response={201: DocumentCreatedOut, **TOKEN_BODY_ERROR_RESPONSES},
)
def documents_create(request: HttpRequest, body: DocumentIn) -> Status[DocumentCreatedOut] | Status[ErrorBody]:
    """문서 행을 만들고(`awaiting_upload`) 서명된 올리기 주소를 내준다.
    회사 업무(권한 표 company — 고객사 사용자, 운영 관리자는 작업 회사로).

    그 주소로 `sizeBytes` 바이트의 본문을 PUT 한다(크기는 서명 조건이다). 주소는 `expiresInSeconds` 초 동안만 통하고
    서버에 남지 않는다. `sizeBytes` 가 상한(MAX_UPLOAD_BYTES)을 넘으면 413 `upload_too_large` 이고 행을 만들지 않는다.
    """
    principal = permitted(request, "core_documents_create")
    if body.previousDocumentId is not None:  # 읽기 0 — 남의 id·없는 id·내 id 가 같은 답
        raise ApplicationError("validation", "previous_via_patch", "앞 판은 올린 뒤 PATCH 로 정한다")
    storage = _storage()
    result = services.create_document(
        company_id=company_of(principal),
        uploaded_by=principal.user_id,
        file_name=body.fileName,
        size_bytes=body.sizeBytes,
        max_upload_bytes=services.max_upload_bytes(),
        storage=storage,
        report_year=body.reportYear,
    )
    if isinstance(result, services.UploadTooLarge):
        message = f"한 번에 {result.max_bytes}바이트까지 올린다"
        return Status(413, ErrorBody(error=ErrorDetail(code="upload_too_large", message=message)))
    if isinstance(result, BadTenantId):
        raise ApplicationError("conflict", "tenant_id_not_storable", "이 테넌트의 ID 는 저장소의 자리가 될 꼴이 아니다")
    upload = result.upload
    return Status(
        201,
        DocumentCreatedOut(
            document=_document_out(result.document),
            upload=UploadOut(url=upload.url, method=upload.method, expiresInSeconds=upload.expires_in_s),
        ),
    )


@router.get("", operation_id="core_documents_list", response={200: DocumentPageOut, **TOKEN_ERROR_RESPONSES})
def documents_list(request: HttpRequest, query: Query[DocumentListQuery]) -> DocumentPageOut:
    """이 회사의 문서 목록. 새 것 먼저. `reportYear` 는 「같다」, `q` 는 파일 이름의 부분 일치다. 고객사 사용자가 본다."""  # noqa: E501
    principal = permitted(request, "core_documents_list")
    page = selectors.list_documents(
        company_id=company_of(principal),
        report_year=query.reportYear,
        q=query.q,
        uploaded_by=query.uploadedBy,
        latest_only=query.latestOnly,
        limit=query.limit,
        offset=query.offset,
    )
    return DocumentPageOut(
        count=page.count,
        isNext=query.offset + len(page.documents) < page.count,
        results=[
            DocumentListItemOut(**_document_out(document).model_dump(), uploadedBy=_user_id(document.uploaded_by))
            for document in page.documents
        ],
    )


@router.post(
    "/{document_id}/confirm",
    operation_id="core_documents_confirm",
    response={200: DocumentStatusOut, 404: ErrorBody, **TOKEN_ERROR_RESPONSES},
)
def documents_confirm(request: HttpRequest, document_id: int) -> DocumentStatusOut:
    """올림 확인. 본문이 없다: 서버가 저장소에 물어(head) 크기를 견주고 ETag 를 적는다.
    회사 업무(권한 표 company — 고객사 사용자, 운영 관리자는 작업 회사로).

    올라와 있으면 문서가 `uploaded` 가 되고 분해 일감 하나가 `queued` 로 생긴다. 여러 번 불러도 일감은 하나다.
    아직 없으면 409 `not_uploaded`, 크기가 만들 때 말한 것과 다르면 409 `upload_size_mismatch`(둘 다 문서는 그대로).
    ★ 지금은 워커가 없다: 일감은 `queued` 에 머문다.
    """
    principal = permitted(request, "core_documents_confirm")
    result = services.confirm_upload(
        company_id=company_of(principal),
        document_id=document_id,
        storage=_storage(),
        now=now(),
        actor_user_id=int(principal.user_id),
        actor_kind=principal.kind,
    )
    if isinstance(result, selectors.DocumentNotFound):
        raise _not_found()
    if isinstance(result, services.NotUploaded):
        raise _not_uploaded()
    if isinstance(result, services.UploadSizeMismatch):
        message = f"올라온 크기({result.actual}바이트)가 만들 때 말한 크기({result.expected}바이트)와 다르다"
        raise ApplicationError("conflict", "upload_size_mismatch", message)
    if isinstance(result, StorageDenied | StorageUnavailable):
        raise _storage_failed(result)
    return _status_out(result.document, result.jobs)


@router.get(
    "/{document_id}",
    operation_id="core_documents_get",
    response={200: DocumentStatusOut, 404: ErrorBody, **TOKEN_ERROR_RESPONSES},
)
def documents_get(request: HttpRequest, document_id: int) -> DocumentStatusOut:
    """문서와 그 일감들의 상태. 고객사 사용자가 본다. 저장소에 묻지 않는다(표에 적힌 것만)."""
    principal = permitted(request, "core_documents_get")
    result = selectors.get_document(company_id=company_of(principal), document_id=document_id)
    if isinstance(result, selectors.DocumentNotFound):
        raise _not_found()
    return _status_out(result.document, result.jobs)


@router.patch(
    "/{document_id}",
    operation_id="core_documents_update",
    response={200: DocumentOut, 404: ErrorBody, **TOKEN_BODY_ERROR_RESPONSES},
)
def documents_update(request: HttpRequest, document_id: int, body: DocumentPatchIn) -> DocumentOut:
    """보고 연도와 앞 판을 정한다. 보낸 칸만 바꾸고 null 은 지운다(둘 다 빠지면 422).
    회사 업무(권한 표 company — 고객사 사용자, 운영 관리자는 작업 회사로).

    대상과 앞 판은 같은 회사의 올라온(`uploaded`) 문서여야 한다: 없으면 404 `NOT_FOUND`, 아직 안 올라왔으면 409
    `NOT_UPLOADED`. 자기 자신을 앞 판으로 하면 422 `VERSION_CHAIN_SELF`, 한 앞 판에 뒤 판은 하나뿐이라 이미 다른 뒤 판이
    있으면 409 `VERSION_CHAIN_FORK`, 사슬이 돌게 되면 409 `VERSION_CHAIN_CYCLE`, 너무 길어지면 409
    `VERSION_CHAIN_TOO_LONG`(어느 거절이든 문서는 그대로).
    """
    principal = permitted(request, "core_documents_update")
    sent = body.model_fields_set
    result = services.update_document(
        company_id=company_of(principal),
        document_id=document_id,
        now=now(),
        report_year=body.reportYear if "reportYear" in sent else services.KEEP,
        previous_document_id=body.previousDocumentId if "previousDocumentId" in sent else services.KEEP,
    )
    if isinstance(result, selectors.DocumentNotFound):
        raise _not_found()
    if isinstance(result, services.DocumentNotUploaded | services.PreviousNotUploaded):
        raise _not_uploaded()
    if isinstance(result, services.PreviousNotFound):
        raise ApplicationError("not_found", "not_found", "앞 판 문서가 없다")
    if isinstance(result, ChainSelf | ChainFork | ChainCycle | ChainTooLong):
        raise _chain_refused(result)
    return _document_out(result.document)


@router.get(
    "/{document_id}/versions",
    operation_id="core_documents_versions",
    response={200: list[DocumentOut], 404: ErrorBody, **TOKEN_ERROR_RESPONSES},
)
def documents_versions(request: HttpRequest, document_id: int) -> list[DocumentOut]:
    """그 문서를 포함한 판의 사슬(previousDocumentId 로 이은 것). 새 판 먼저. 고객사 사용자가 본다."""
    principal = permitted(request, "core_documents_versions")
    result = selectors.version_chain(company_id=company_of(principal), document_id=document_id)
    if isinstance(result, selectors.DocumentNotFound):
        raise _not_found()
    if isinstance(result, ChainTooLong):
        raise _chain_refused(result)
    return [_document_out(document) for document in result]


@router.get(
    "/{document_id}/file",
    operation_id="core_documents_file_get",
    response={404: ErrorBody, **TOKEN_ERROR_RESPONSES},
    openapi_extra=PDF_RESPONSE,
)
def documents_file_get(request: HttpRequest, document_id: int) -> HttpResponse:
    """원본 PDF 를 내려받는다(Content-Type `application/pdf`, `attachment`).
    회사 업무(권한 표 company — 고객사 사용자, 운영 관리자는 작업 회사로).

    아직 안 올라온 문서는 409 `NOT_UPLOADED`, 저장소에 원본이 없으면 409 `OBJECT_MISSING`, 상한을 넘으면 409
    `OBJECT_TOO_LARGE`, 올림 확인 뒤 원본이 바뀌었으면 409 `OBJECT_CHANGED` 다.
    """
    principal = permitted(request, "core_documents_file_get")
    company_id = company_of(principal)
    document = selectors.find_document(company_id=company_id, document_id=document_id)
    if document is None:
        raise _not_found()
    if document.status != "uploaded":
        raise _not_uploaded()
    got = _storage().get(document.storage_key, max_bytes=services.max_upload_bytes())
    if isinstance(got, StorageDenied | StorageUnavailable):
        raise _storage_failed(got)
    if isinstance(got, ObjectMissing):
        raise ApplicationError("conflict", "object_missing", "저장소에 원본이 없다")
    if isinstance(got, ObjectTooLarge):
        raise ApplicationError("conflict", "object_too_large", "원본이 내려받기 상한보다 크다")
    if got.etag != document.etag:  # 올림 확인 뒤 같은 키에 다시 올라옴
        raise ApplicationError("conflict", "object_changed", "올림 확인 뒤 원본이 바뀌었다")
    record_event(
        at=now(),
        company_id=company_id,
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        action="download",
        event="document_downloaded",
        result="success",
        target_kind="document",
        target_id=document.id,
        target_label=document.file_name,
    )
    response = HttpResponse(got.data, content_type="application/pdf")
    # RFC 6266: ASCII 이름은 filename="…"(따옴표·역빗금 escape), 아니면 filename*=utf-8''<퍼센트> 하나(ASCII 대체
    # 이름 없음 — 한글·따옴표·; 가 든 이름). django-stubs 에 이 함수가 없다(Django 4.2+).
    disposition: str = django_http.content_disposition_header(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        as_attachment=True, filename=document.file_name
    )
    response["Content-Disposition"] = disposition
    response["X-Content-Type-Options"] = "nosniff"
    return response
