"""쓰기. 유스케이스 셋: 문서 만들기, 올림 확인, 문서 고치기(보고 연도·앞 판 — X1b-2a).
HTTP 를 모른다(요청·응답·상태 코드가 없다).
실행 묶음의 넣기 셋(import_document·set_imported_etag·restore_document_times — RX1a)은 파일 끝에 있다.

결과는 예외가 아니라 갈래로 돌려준다(frozen dataclass). esgapi/core/service/apis/documents.py 가 갈래를 응답으로 바꾼다.
바깥(저장소·시계·큐 넣기)은 함수 인자로 받는다. 회사 id 도 인자다(세션 객체를 받지 않는다: 인증이 바뀌어도
이 파일이 남는다. 권한 가름은 경로 쪽에 있다).

★ 올림 확인이 믿는 것과 안 믿는 것
  믿는 것: 저장소의 head 가 말한 크기와 ETag.
  안 믿는 것: 클라이언트의 「올렸다」는 말(요청에 본문이 없다), 만들 때 말한 크기(head 의 크기와 견준다),
             서명 조건이 크기를 막아 준다는 것(Versity 에서만 잰 것이라 head 가 닻이다).
  쪽 수·앞 TEXT_PROBE_PAGES 쪽 글자 층은 올림 확인이 잰다(X1b-2a — 블록 밖에서 바이트를 읽어 자식 프로세스로).
             못 재면(PDF 아님·암호·시간 넘김·죽음·저장소 읽기 실패·head 와 읽은 객체의 ETag 다름) 값 둘은 NULL 이고
             올림은 막지 않는다.
  못 보는 것: 올림 확인 뒤 주소의 수명 안에 같은 키에 다시 올린 것(ETag 를 적어 두었다. 원본 내려받기가 견준다).

★ 거절은 쓰기 앞에서 돌아온다(요청마다의 트랜잭션이 없어 쓰기 뒤에 거절하면 그 쓰기가 남는다). 거절을 행에 적는
  일은 아직 없다(X1). 크기가 어긋난 객체가 저장소에 있어도 문서는 `awaiting_upload` 로 남고, 클라이언트는 주소의
  수명 안에서 다시 올릴 수 있다.

★ 판 사슬(update_document): 두 행(대상·앞 판)을 **id 차례로** FOR UPDATE 로 잡은 블록 하나에서 규칙을 보고 쓴다(교착 0).
  갈래 금지의 경합(두 PATCH 가 같은 앞 판)은 DB 의 부분 UNIQUE core_documents_previous_uniq 가 막고 그 위반은
  갈래 값이다.
  무효 조건: 잠금 집합이 겹치지 않는 두 PATCH(B→C·D→A 가 있을 때 A→B ∥ C→D)는 둘 다 검사를 지나 순환을 만들 수 있다
  (지나는 행마다 잠그는 길은 버림 — 잠금 수가 사슬 길이만큼). 순환이 든 데이터에서도 걷기는 끝난다(방문 집합).

★ 테스트가 바꿔 끼우는 틈 넷(전부 「부를 때 모듈 속성으로 읽는다」):
    services.default_storage      monkeypatch.setattr(services, "default_storage", lambda: fake)
    services.max_upload_bytes     monkeypatch.setattr(services, "max_upload_bytes", lambda: 1000)
    services.default_pdf_probe    monkeypatch.setattr(services, "default_pdf_probe", lambda: fake_probe)
    hooks.enqueue_job             monkeypatch.setattr(hooks, "enqueue_job", spy)
  어댑터의 캐시(storage_from)는 default_storage 의 **안쪽**에 있어 위 길로 덮인다(테스트 사이에 남지 않는다).
"""

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import cache

from django.db import IntegrityError, transaction

from esgapi.config.env import StorageSettings
from esgapi.core.auth.principal import Kind
from esgapi.core.calc.documents import JOB_KINDS, TEXT_PROBE_PAGES, BadTenantId, is_job_finished, storage_key
from esgapi.core.calc.versions import ChainCycle, ChainFork, ChainSelf, ChainTooLong, chain_problem
from esgapi.core.conf import app_config
from esgapi.core.models import DocumentRow
from esgapi.core.resources import queue as hooks
from esgapi.core.resources import storage as storage_adapter
from esgapi.core.resources.pdf import PdfiumProbe, stored_bytes
from esgapi.core.resources.ports.pdf import PdfProbe, PdfProbed
from esgapi.core.resources.ports.storage import (
    ObjectFound,
    ObjectMissing,
    ObjectStorage,
    PresignedUpload,
    StorageDenied,
    StorageUnavailable,
)
from esgapi.core.service.selectors import documents as selectors
from esgapi.core.service.selectors.documents import Document, DocumentNotFound, Job, document_of
from esgapi.core.service.services.audit import record_event
from esgapi.runs.models import JobRow

# 큐에 넣는 함수의 꼴: enqueue(company_id=…, job_id=…, kind=…)
Enqueue = Callable[..., None]


def _sending(send: Enqueue, *, company_id: int, job_id: int, kind: str) -> Callable[[], None]:
    """커밋 뒤에 `send(…)` 를 부를 것 하나. 값은 여기서 묶는다(부르는 쪽의 반복 변수를 닫아 잡지 않는다).

    functools.partial 을 쓰지 않는다: Django 5.2 는 robust 갈고리가 던지면 `func.__qualname__` 을 기록에 넣는데
    partial 에는 그것이 없어 기록하는 줄이 AttributeError 로 죽고 요청이 500 이 된다.
    """

    def send_job() -> None:
        send(company_id=company_id, job_id=job_id, kind=kind)

    return send_job


# ── 저장소와 상한 (이음매) ────────────────────────────────────────────


@cache
def storage_from(settings: StorageSettings) -> ObjectStorage:
    """설정 → s3 어댑터. 프로세스마다, 설정 값마다 한 번 만든다(boto3 클라이언트를 요청마다 짓지 않는다)."""
    return storage_adapter.make(
        "s3",
        bucket=settings.bucket,
        region=settings.region,
        endpoint=settings.endpoint,
        public_endpoint=settings.public_endpoint,
        force_path_style=settings.force_path_style,
        access_key_id=settings.access_key_id,
        secret_access_key=settings.secret_access_key,
        upload_ttl_s=settings.upload_url_ttl_seconds,
    )


def default_storage() -> ObjectStorage | None:
    """이 서버의 저장소. 설정에 없으면(S3_BUCKET 없음) None. ★ 이음매다: 경로는 부를 때마다 이 이름을 읽는다."""
    settings = app_config().storage
    return None if settings is None else storage_from(settings)


def max_upload_bytes() -> int:
    """올릴 수 있는 파일의 상한(MAX_UPLOAD_BYTES). 저장소 설정이 없으면 그 기본값. ★ 이음매다."""
    settings = app_config().storage
    return StorageSettings.max_upload_bytes if settings is None else settings.max_upload_bytes


def default_pdf_probe() -> PdfProbe:
    """이 서버의 PDF 재기(자식 프로세스 + pypdfium2 — core/resources/pdf.py). ★ 이음매다."""
    return PdfiumProbe()


# ── 문서 만들기 ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DocumentCreated:
    document: Document
    upload: PresignedUpload


@dataclass(frozen=True, slots=True)
class UploadTooLarge:
    max_bytes: int


def create_document(
    *,
    company_id: int,
    uploaded_by: str,
    file_name: str,
    size_bytes: int,
    max_upload_bytes: int,
    storage: ObjectStorage,
    report_year: int | None = None,
) -> DocumentCreated | BadTenantId | UploadTooLarge:
    """문서 행(`awaiting_upload`)을 만들고, 그 크기의 본문만 받는 올리기 주소를 서명해 돌려준다.

    상한을 넘으면 행을 만들지 않고 서명도 하지 않는다. 행을 넣은 **뒤에**, 같은 블록 안에서 서명한다: 서명이 실패하면
    이 블록이 행을 되돌리므로 고아 행이 남지 않는다(서명은 계산이지 네트워크가 아니다). 파일 이름의 꼴은 경로의
    스키마가 걸렀다(여기서 다시 보지 않는다).
    행은 company_id 의 범위로 만든다(DocumentRow.for_company. 다른 회사로 쓰면 CrossCompanyWriteError).
    저장소 키의 UUID 는 따로 짓는다(문서 id 는 DB 가 매기는 숫자다 — 키에 넣지 않는다).
    보고 연도는 그대로 적는다(범위는 경로의 스키마와 DB CHECK). 앞 판은 받지 않는다 — PATCH 로만(X1b-2a: 올리기가
    끊겨 `awaiting_upload` 로 버려진 행이 앞 판을 쥐면 갈래 금지가 그 앞 판의 수정본을 영영 막는다).
    """
    if size_bytes > max_upload_bytes:
        return UploadTooLarge(max_upload_bytes)
    key = storage_key(company_id, str(uuid.uuid4()))
    if isinstance(key, BadTenantId):
        return key
    with transaction.atomic():
        row = DocumentRow.for_company(company_id).create(
            company_id=company_id,
            uploaded_by=uploaded_by,
            file_name=file_name,
            storage_key=key.key,
            size_bytes=size_bytes,
            status="awaiting_upload",
            report_year=report_year,
        )
        upload = storage.presign_upload(key.key, content_length=size_bytes)
    return DocumentCreated(document_of(row), upload)


# ── 올림 확인 ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class UploadConfirmed:
    document: Document
    jobs: tuple[Job, ...]


@dataclass(frozen=True, slots=True)
class NotUploaded:
    """저장소에 그 키의 객체가 없다(아직 안 올렸다)."""


@dataclass(frozen=True, slots=True)
class UploadSizeMismatch:
    """올라온 객체의 크기가 만들 때 말한 크기와 다르다."""

    expected: int
    actual: int


def _measured(storage: ObjectStorage, document: Document, found: ObjectFound) -> tuple[int | None, bool | None]:
    """올라온 원본의 (쪽 수, 글자 층). 못 재면 (None, None) — 읽기 실패·ETag 다름·PDF 재기 실패 어느 것이든.

    읽는 상한은 만들 때 말한 크기다(head 가 같은 크기를 말했다). head 와 읽은 객체의 ETag 가 다르면(그 사이에 같은 키로
    다시 올림) 적을 ETag 와 잰 객체가 달라지므로 재지 않는다. 바이트 읽기는 pdf 어댑터 모듈의 stored_bytes 다
    (이 파일에 저장소 `.get` 을 두지 않는다 — core/tests/test_selector_scope.py 의 「Service 는 읽지 않는다」가
    이름으로 본다).
    """
    content = stored_bytes(storage, document.storage_key, max_bytes=document.size_bytes, etag=found.etag)
    if content is None:
        return None, None
    result = default_pdf_probe().probe(content, text_pages=TEXT_PROBE_PAGES)
    if isinstance(result, PdfProbed):
        return result.page_count, result.has_text
    return None, None


def confirm_upload(
    *,
    company_id: int,
    document_id: int,
    storage: ObjectStorage,
    now: datetime,
    enqueue: Enqueue | None = None,
    actor_user_id: int | None = None,
    actor_kind: Kind | None = None,
) -> UploadConfirmed | DocumentNotFound | NotUploaded | UploadSizeMismatch | StorageDenied | StorageUnavailable:
    """저장소에 물어 올라왔는지 확인하고, 문서를 `uploaded` 로, 분해 일감 하나를 `queued` 로 만든다.

    차례: ① 잠그지 않고 찾는다 → ② 이미 `uploaded` 면 저장소에 다시 묻지 않고 ⑤ 로 → ③ head(잠금을 쥐지 않은 채.
    저장소가 느려도 행을 붙들지 않는다). 크기를 견준다 → ③' 바이트를 읽어(get) 쪽 수·글자 층을 잰다(probe — 둘 다
    블록 밖. 어떤 실패도 막지 않고 값 둘을 NULL 로 — X1b-2a) → ④ FOR UPDATE 로 다시 읽어 여전히
    `awaiting_upload` 일 때만 적고 일감을 만든다(같은 문서의 올림 확인 둘이 겹쳐도 일감은 하나다) → ⑤ 끝나지
    않은 일감마다 커밋 뒤에 큐에 넣는다.

    그래서 여러 번 불러도 된다: 일감은 하나로 남고, 쪽지를 잃었으면 다시 부르는 것이 다시 넣는 길이다.
    ①②③ 은 트랜잭션 밖이고, ④⑤ 는 이 함수가 스스로 여는 블록 하나다(FOR UPDATE 와 on_commit 이 그것을 전제한다.
    바깥 트랜잭션 안에서 불리면 그 블록은 세이브포인트다). head 는 블록 밖이다(바깥 호출 동안 트랜잭션을 쥐지 않는다).
    `enqueue` 가 None 이면 **부를 때** hooks.enqueue_job 을 읽는다(기본값 인자에 묶지 않는다: 테스트가 바꿔 끼운다).
    PDF 재기도 부를 때 default_pdf_probe 를 읽는다(이음매). 이미 `uploaded`(②)면 다시 재지 않는다.

    감사 줄(AU1a — upload)은 ④ 에서 옮김을 했을 때만, 블록이 **닫힌 뒤** 하나다. 이미 `uploaded` 인 멱등 호출·409·저장소
    오류는 0줄. 행위자는 경로의 사람 — 그 kind 는 actor_kind(경로가 넘긴다: 회사 업무라 고객사 사용자 service 와 작업
    회사로 일하는 운영 관리자 admin — 결정 MARC-ENT-374). actor_kind 의 None 은 옛 부름 전용(부르는 자리 25곳 —
    service 로 적는다), actor_user_id 를 넘기지 않은 부름(시험·워커 쪽)은 command(감독 처분 2026-10-19 — 선택 인자).
    무효 조건: 블록 커밋과 감사 커밋 사이에 프로세스가 죽으면 그 줄이 빠진다. X1b-1 이 이 옮김을 실행 만들기로 옮길 때
    감사 지점도 같이 옮긴다.
    """
    document = selectors.find_document(company_id=company_id, document_id=document_id)  # ①
    if document is None:
        return DocumentNotFound()

    found: ObjectFound | None = None
    page_count: int | None = None
    text_layer: bool | None = None
    if document.status == "awaiting_upload":  # ② 가 아니면
        head = storage.head(document.storage_key)  # ③ — 블록 밖
        if isinstance(head, ObjectMissing):
            return NotUploaded()
        if isinstance(head, StorageDenied | StorageUnavailable):
            return head
        if head.size_bytes != document.size_bytes:
            return UploadSizeMismatch(expected=document.size_bytes, actual=head.size_bytes)
        found = head
        page_count, text_layer = _measured(storage, document, found)  # ③' — 블록 밖

    moved = False
    with transaction.atomic():
        if found is not None:
            locked = selectors.lock_document(company_id=company_id, document_id=document_id)  # ④
            if locked is None:
                raise RuntimeError("잠그려던 core_documents 의 행이 없다(①에서는 있었다)")
            if locked.status == "awaiting_upload":
                updated = (
                    DocumentRow.for_company(company_id)
                    .filter(pk=document_id, status="awaiting_upload")
                    .update(
                        etag=found.etag,
                        uploaded_at=now,
                        status="uploaded",
                        page_count=page_count,
                        has_text=text_layer,
                        updated_at=now,
                    )
                )
                if updated != 1:
                    # 잠근 행이 사라졌거나 상태가 바뀌었다. 조용히 넘어가지 않는다(예외 → 503, 블록이 되돌려진다).
                    raise RuntimeError(f"core_documents 의 갱신이 {updated}행이다(1행이어야 한다)")
                # 일감의 회사는 인자가 아니라 **문서 행의 것**이다.
                JobRow.for_company(locked.company_id).create(
                    company_id=locked.company_id, document=locked, kind=JOB_KINDS[0], status="queued", attempts=0
                )
                moved = True
            document = selectors.find_document(company_id=company_id, document_id=document_id)
            if document is None:
                raise RuntimeError("방금 고친 core_documents 의 행이 없다")

        jobs = selectors.jobs_of(company_id=company_id, document_id=document_id)
        send = hooks.enqueue_job if enqueue is None else enqueue
        for job in jobs:  # ⑤ — on_commit 은 블록 안에서 건다(블록이 되돌려지면 같이 버려진다)
            if not is_job_finished(job.status):
                # robust=True: 갈고리가 던져도 커밋은 이미 끝났고 요청은 200 이다(core/resources/queue.py 의 머리말).
                transaction.on_commit(
                    _sending(send, company_id=job.company_id, job_id=job.id, kind=job.kind), robust=True
                )
    if moved:
        record_event(
            at=now,
            company_id=company_id,
            actor_kind="command" if actor_user_id is None else (actor_kind or "service"),
            actor_user_id=actor_user_id,
            action="upload",
            event="document_uploaded",
            result="success",
            target_kind="document",
            target_id=document.id,
            target_label=document.file_name,
        )
    return UploadConfirmed(document, jobs)


# ── 문서 고치기(PATCH — X1b-2a) ─────────────────────────────────────


class Keep:
    """PATCH 에서 보내지 않은 칸(바꾸지 않음). None(지움)과 구별한다."""


KEEP = Keep()


@dataclass(frozen=True, slots=True)
class DocumentUpdated:
    document: Document


@dataclass(frozen=True, slots=True)
class DocumentNotUploaded:
    """대상 문서가 아직 `uploaded` 가 아니다(사슬 칸을 쥘 수 없다)."""


@dataclass(frozen=True, slots=True)
class PreviousNotFound:
    """앞 판으로 가리킨 문서가 없다. 다른 회사의 문서도 이 갈래다."""


@dataclass(frozen=True, slots=True)
class PreviousNotUploaded:
    """앞 판으로 가리킨 문서가 아직 `uploaded` 가 아니다."""


UpdateResult = (
    DocumentUpdated
    | DocumentNotFound
    | DocumentNotUploaded
    | PreviousNotFound
    | PreviousNotUploaded
    | ChainSelf
    | ChainFork
    | ChainCycle
    | ChainTooLong
)

PREVIOUS_UNIQUE = "core_documents_previous_uniq"


def _unique_broken(err: IntegrityError) -> str | None:
    """IntegrityError 가 어긴 제약의 이름(psycopg 의 diag). 모르면 None."""
    diag = getattr(err.__cause__, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return name if isinstance(name, str) else None


def update_document(
    *,
    company_id: int,
    document_id: int,
    now: datetime,
    report_year: int | Keep | None = KEEP,
    previous_document_id: int | Keep | None = KEEP,
) -> UpdateResult:
    """보낸 칸만 바꾼다(None = 지움, KEEP = 그대로). 거절은 쓰기 앞에서 값으로 돌아온다.

    차례(블록 하나): 대상·앞 판을 id 차례로 FOR UPDATE → 대상 없음(남의 것이어도) DocumentNotFound → 대상이 `uploaded`
    아님 DocumentNotUploaded → 앞 판을 정하면: 자기 자신 ChainSelf → 앞 판 없음(남의 것이어도) PreviousNotFound → 앞 판
    `uploaded` 아님 PreviousNotUploaded → 갈래·순환·길이(core/calc/versions.py) → 쓰기. 같은 앞 판을 다시 보내면 지난다.
    갈래의 경합으로 부분 UNIQUE 를 어기면 블록이 되돌려지고 ChainFork 다(다른 제약 위반은 그대로 올린다).
    """
    try:
        with transaction.atomic():
            setting_previous = isinstance(previous_document_id, int)
            ids = (
                sorted({document_id, previous_document_id}) if isinstance(previous_document_id, int) else [document_id]
            )
            locked = {i: selectors.lock_document(company_id=company_id, document_id=i) for i in ids}
            target = locked[document_id]
            if target is None:
                return DocumentNotFound()
            if target.status != "uploaded":
                return DocumentNotUploaded()
            if isinstance(previous_document_id, int):
                if previous_document_id == document_id:
                    return ChainSelf()
                previous = locked[previous_document_id]
                if previous is None:
                    return PreviousNotFound()
                if previous.status != "uploaded":
                    return PreviousNotUploaded()
                problem = chain_problem(
                    document_id,
                    previous_document_id,
                    previous_of=lambda i: selectors.previous_id_of(company_id=company_id, document_id=i),
                    next_of=lambda i: selectors.next_id_of(company_id=company_id, document_id=i),
                )
                if problem is not None:
                    return problem
            changes: dict[str, object] = {}
            if not isinstance(report_year, Keep):
                changes["report_year"] = report_year
            if setting_previous or previous_document_id is None:
                changes["previous_document_id"] = previous_document_id
            updated = DocumentRow.for_company(company_id).filter(pk=document_id).update(**changes, updated_at=now)
            if updated != 1:
                raise RuntimeError(f"core_documents 의 갱신이 {updated}행이다(1행이어야 한다)")
    except IntegrityError as err:
        if _unique_broken(err) == PREVIOUS_UNIQUE:
            return ChainFork()
        raise
    document = selectors.find_document(company_id=company_id, document_id=document_id)
    if document is None:
        raise RuntimeError("방금 고친 core_documents 의 행이 없다")
    return DocumentUpdated(document)


# ── 실행 묶음의 넣기(RX1a — runbundle 앱의 import_runs) ──────────────────────
# 부르는 쪽(runbundle)의 durable 블록 안에서만 부른다(여기의 블록은 세이브포인트다). 행은 그 블록이 넣고, 바이트는 행을
# 다 넣은 뒤 그 블록 끝에서 올린다(etag 는 올린 뒤 set_imported_etag 로 — 실행기의 object_changed 가 견준다).


def import_document(
    *,
    company_id: int,
    uploaded_by: str,
    storage_key: str,
    file_name: str,
    size_bytes: int,
    sha256: str | None,
    status: str,
    uploaded_at: datetime | None,
    report_year: int | None,
    previous_document_id: int | None,
    page_count: int | None,
    has_text: bool | None,
    etag: str | None = None,
) -> int:
    """묶음의 문서 하나를 그 회사에 새 행으로 넣고 새 id. 키는 부르는 쪽이 새 UUID 로 지어 온다
    (core/calc/documents.py 의 storage_key). 앞 판은 같은 회사의 이미 넣은 행이어야 한다(같은 회사 외래 키·갈래 금지
    UNIQUE 가 DB 에서 막는다)."""
    with transaction.atomic():
        row = DocumentRow.for_company(company_id).create(
            company_id=company_id,
            uploaded_by=uploaded_by,
            file_name=file_name,
            storage_key=storage_key,
            size_bytes=size_bytes,
            etag=etag,
            sha256=sha256,
            status=status,
            uploaded_at=uploaded_at,
            report_year=report_year,
            previous_document_id=previous_document_id,
            page_count=page_count,
            has_text=has_text,
        )
    return row.id


def set_imported_etag(*, company_id: int, document_id: int, etag: str) -> None:
    """넣은 문서에 저장소가 준 ETag 를 적는다(etag 가 아직 NULL 인 행만). 1행이 아니면 RuntimeError. updated_at 은
    건드리지 않는다(QuerySet.update 는 auto_now 를 안 채운다 — 되돌린 시각이 남는다)."""
    with transaction.atomic():
        updated = DocumentRow.for_company(company_id).filter(pk=document_id, etag__isnull=True).update(etag=etag)
    if updated != 1:
        raise RuntimeError(f"core_documents 의 etag 적기가 {updated}행이다(1행이어야 한다)")


def restore_document_times(*, company_id: int, times: Mapping[int, tuple[datetime, datetime]]) -> None:
    """넣은 문서의 created_at·updated_at 을 묶음의 원래 값으로 되돌린다(문서 id → (created_at, updated_at)).
    한 행이라도 1행이 아니면 RuntimeError."""
    with transaction.atomic():
        for document_id, (created_at, updated_at) in times.items():
            updated = (
                DocumentRow.for_company(company_id)
                .filter(pk=document_id)
                .update(created_at=created_at, updated_at=updated_at)
            )
            if updated != 1:
                raise RuntimeError(f"core_documents 의 시각 되돌리기가 {updated}행이다(1행이어야 한다)")
