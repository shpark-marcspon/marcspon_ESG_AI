"""짓는 길 — 문서 산출물(밴드 RP2a ①, 결정 MARC-ENT-514 — 설계 §1-3). 찾기는 selectors.py 를 부르기만 한다.

    ensure_artifact(company_id, document_id, etag, *, layout, parser, max_pages)
        -> ArtifactRef | ArtifactRefused | ArtifactUnreadable   (ArtifactInvalid 는 던짐, 잠깐 장애는 RunRetryLater)

차례(발주서 §1-C C-2):
  ⓐ uses (문서, etag, CONTRACT, layout, EPOCH) 있음 → 그 산출물(저장소·파서 0)
  ⓑ sha = core_documents.sha256(NULL 이면 ⓒ0 의 바이트로 셈) → 같은 회사·sha·layout·EPOCH 산출물 있음 → uses 만 넣음
  ⓒ0 문서 없음 document_missing · 행의 etag 다름 object_changed · 저장소 설정 없음 storage_unconfigured · 잠깐 장애
     RunRetryLater · 그 밖 저장소 결과의 타입 이름 · 객체 etag 다름·sha 가 행 값과 다름 object_changed (행 0)
  ⓒ1 core_documents.page_count > max_pages → ArtifactRefused(too_many_pages) — 파서 0
  ⓒ2 파서 rejected → ArtifactRefused(code)(parse_timeout 포함, 행 0) · ⓒ3 unavailable → RunRetryLater(행 0, e7 ⑩)
  ⓒ4 invalid_response·꼴 어김 → ArtifactInvalid · 지나면 글자의 NUL 을 U+FFFD 로(contract.scrub_nul, QC3)
  ⓒ5 page_count 가 NULL 이었고 분해 뒤 쪽 > max_pages → ArtifactRefused(too_many_pages)(행 0)
  ⓒ6 본문 > ARTIFACT_MAX_BYTES → `too_large` 행(본문 NULL) + uses — 부르는 쪽이 거절한다(다시 분해 0)
  ⓒ7 정상 → 산출물 + uses
  판 2 면 파서를 charts=True 로 불러 도표 라벨도 셋째 칸에 싣는다(밴드 CHL1 — 부르는 쪽 인자 그대로). 판 1 은 부르는 꼴
  그대로(charts 인자 0).
★ 파서는 트랜잭션 밖에서 부른다(분해는 수십 초~). 넣기는 블록 하나에서 **INSERT 마다 세이브포인트**: 산출물 INSERT 가
  열쇠 경합(IntegrityError)이면 그 열쇠의 행을 다시 읽고, uses INSERT 가 겹치면 uses 를 다시 읽어 그 산출물을 쓴다
  (514-8 — 행 잠금 0). 동시 분해는 파서를 두 번 부를 수 있다(1차 허용 — 행은 하나).
★ 저장소·상한은 core/service/services/documents.py 의 이음매(default_storage·max_upload_bytes)를 부를 때 읽는다.
  파서는 인자(만드는 함수 — 부를 때만 짓는다: 주소가 없으면 ParserSetupError 가 그대로 올라간다).
"""

import hashlib
import logging
from collections.abc import Callable
from typing import Any

from django.db import IntegrityError, transaction

from esgapi.core.documents import selectors
from esgapi.core.documents.contract import (
    ARTIFACT_MAX_BYTES,
    CONTRACT,
    EPOCH,
    PARSE_FILE_NAME,
    ArtifactInvalid,
    ArtifactRef,
    ArtifactRefused,
    ArtifactUnreadable,
    body_bytes,
    page_count_of,
    parser_info_of,
    scrub_nul,
    shape_problem,
)
from esgapi.core.flows.binding import RunRetryLater
from esgapi.core.models import DocumentArtifactRow, DocumentArtifactUseRow
from esgapi.core.resources.ports.parser import DocumentParser, ParseFailed
from esgapi.core.resources.ports.storage import ObjectBytes, StorageUnavailable
from esgapi.core.service.services import documents

TOO_MANY_PAGES = "too_many_pages"
CHARTS_LAYOUT = 2  # 도표 라벨을 받는 판(파서의 charts 는 판 2 에만 — CHL1)
# 도표 라벨을 붙인 요청이 이 code 로 거절되면 라벨 없이 한 번 더 부른다(CHL1 ④ N1 — 라벨 실패가 본 분해를 죽이지
# 않게). 분해를 마친 뒤에도 날 수 있는 거절만이다. 여는 자리의 거절(not_a_pdf·password_protected·too_many_pages …)은
# 라벨 없이도 같으므로 다시 부르지 않는다. parse_failed·output_schema_invalid 는 분해 자체에서도 날 수 있어 그때는 두 번
# 부르고 두 번째 거절을 낸다. parse_timeout 은 다시 부르지 않는다: 첫 부름이 이미 파서 상한(180초)을 쓴 뒤라 두 번째는
# 일감의 시간 상한에 잘린다(행 0 으로 되풀이하며 파서 일꾼을 쥔다 — CHL1 ④ 검증 B1).
CHARTS_RETRY_CODES = frozenset({"parse_failed", "output_schema_invalid", "bad_charts"})

logger = logging.getLogger(__name__)


def _read(source: selectors.SourceDocument, etag: str) -> bytes | ArtifactUnreadable:
    """원본 바이트(ⓒ0). 잠깐 장애는 RunRetryLater 를 던진다."""
    storage = documents.default_storage()
    if storage is None:
        return ArtifactUnreadable("storage_unconfigured")
    got = storage.get(source.storage_key, max_bytes=documents.max_upload_bytes())
    if isinstance(got, StorageUnavailable):
        raise RunRetryLater("저장소에 잠깐 닿지 못했다")
    if not isinstance(got, ObjectBytes):
        return ArtifactUnreadable(type(got).__name__)
    if got.etag != etag:
        return ArtifactUnreadable("object_changed")
    if source.sha256 is not None and hashlib.sha256(got.data).hexdigest() != source.sha256:
        return ArtifactUnreadable("object_changed")
    return got.data


def ensure_artifact(
    company_id: int,
    document_id: int,
    etag: str,
    *,
    layout: int,
    parser: Callable[[], DocumentParser],
    max_pages: int,
) -> ArtifactRef | ArtifactRefused | ArtifactUnreadable:
    """그 문서의 그 etag 바이트를 그 판으로 분해한 산출물(없으면 짓는다). 머리말의 차례대로."""
    found = selectors.find_artifact(company_id=company_id, document_id=document_id, etag=etag, layout=layout)  # ⓐ
    if found is not None:
        return found
    source = selectors.source_of(company_id=company_id, document_id=document_id)
    if source is None:
        return ArtifactUnreadable("document_missing")
    if source.etag != etag:
        return ArtifactUnreadable("object_changed")
    content: bytes | None = None
    sha = source.sha256
    if sha is None:
        read = _read(source, etag)
        if isinstance(read, ArtifactUnreadable):
            return read
        content, sha = read, hashlib.sha256(read).hexdigest()
    same = selectors.find_by_source(company_id=company_id, sha256=sha, layout=layout)  # ⓑ
    built: dict[str, Any] = {}  # ⓒ 의 행 칸(ⓑ 면 빈 채)
    if same is None:
        made = _parse(source, etag, content, sha, layout=layout, parser=parser, max_pages=max_pages)
        if isinstance(made, ArtifactRefused | ArtifactUnreadable):
            return made
        built = made
    with transaction.atomic():  # ⓑ·ⓒ6·ⓒ7 — INSERT 마다 세이브포인트
        if same is not None:
            artifact = same
        else:
            try:
                with transaction.atomic():
                    row = DocumentArtifactRow.for_company(company_id).create(company_id=company_id, **built)
                artifact = selectors.ref_of(row)
            except IntegrityError:  # 같은 열쇠를 다른 일꾼이 먼저 넣었다
                raced = selectors.find_by_source(company_id=company_id, sha256=sha, layout=layout)
                if raced is None:
                    raise
                artifact = raced
        try:
            with transaction.atomic():
                DocumentArtifactUseRow.for_company(company_id).create(
                    company_id=company_id,
                    document_id=document_id,
                    document_etag=etag,
                    artifact_id=artifact.id,
                    contract=CONTRACT,
                    layout=layout,
                    epoch=EPOCH,
                )
        except IntegrityError:  # 같은 이음을 다른 일꾼이 먼저 넣었다
            raced = selectors.find_artifact(company_id=company_id, document_id=document_id, etag=etag, layout=layout)
            if raced is None:
                raise
            artifact = raced
    return artifact


def _parse(
    source: selectors.SourceDocument,
    etag: str,
    content: bytes | None,
    sha: str,
    *,
    layout: int,
    parser: Callable[[], DocumentParser],
    max_pages: int,
) -> dict[str, Any] | ArtifactRefused | ArtifactUnreadable:
    """ⓒ1~ⓒ6 — 산출물 행의 칸(회사 칸 빼고). 블록 밖에서 부른다(저장소·파서)."""
    if source.page_count is not None and source.page_count > max_pages:  # ⓒ1
        return ArtifactRefused(TOO_MANY_PAGES)
    if content is None:
        read = _read(source, etag)
        if isinstance(read, ArtifactUnreadable):
            return read
        content = read
    reader = parser()
    if layout == CHARTS_LAYOUT:
        parsed = reader.parse(content, file_name=PARSE_FILE_NAME, layout=layout, charts=True)
        if isinstance(parsed, ParseFailed) and parsed.kind == "rejected" and parsed.detail.code in CHARTS_RETRY_CODES:
            # 문서의 글은 싣지 않는다(code·문서 id 만)
            logger.warning(
                "도표 라벨을 붙인 분해가 거절돼(code %s) 라벨 없이 다시 분해한다 document_id=%s",
                parsed.detail.code,
                source.id,
            )
            parsed = reader.parse(content, file_name=PARSE_FILE_NAME, layout=layout)  # 이 행의 chart_labels 는 NULL
    else:
        parsed = reader.parse(content, file_name=PARSE_FILE_NAME, layout=layout)
    if isinstance(parsed, ParseFailed):
        if parsed.kind == "rejected":  # ⓒ2
            return ArtifactRefused(parsed.detail.code or "rejected")
        if parsed.kind == "unavailable":  # ⓒ3
            raise RunRetryLater(f"파서를 지금 쓸 수 없다(상태 {parsed.detail.status}, code {parsed.detail.code})")
        raise ArtifactInvalid(f"파서 응답이 약속한 꼴이 아니다: {parsed.detail.message}")  # ⓒ4
    problem = shape_problem(
        parsed.document, parsed.char_places, layout=layout, sha256=sha, chart_labels=parsed.chart_labels
    )
    if problem is not None:
        raise ArtifactInvalid(problem)  # ⓒ4
    document, nul_document = scrub_nul(parsed.document)
    places, nul_places = scrub_nul(parsed.char_places or {})
    labels, nul_labels = (None, 0) if parsed.chart_labels is None else scrub_nul(parsed.chart_labels)
    nul = nul_document + nul_places + nul_labels
    if nul:  # 문서 모델에 문서 단위 경고 칸이 없다 — 로그 한 줄(계약 꼴 0 바뀜)
        logger.warning("파서 출력의 NUL %d 개를 U+FFFD 로 바꿨다 sha256=%s", nul, sha)
    pages = page_count_of(document)
    if source.page_count is None and pages > max_pages:  # ⓒ5
        return ArtifactRefused(TOO_MANY_PAGES)
    size = body_bytes(document, places, labels)
    ready = size <= ARTIFACT_MAX_BYTES  # 아니면 ⓒ6
    info = parser_info_of(document, layout=layout)
    return {
        "contract": CONTRACT,
        "epoch": EPOCH,
        "source_sha256": sha,
        "layout": layout,
        "parser_name": info.name,
        "parser_version": info.version,
        "status": "ready" if ready else "too_large",
        "page_count": pages,
        "body_bytes": size,
        "document": document if ready else None,
        "char_places": places if ready else None,
        "chart_labels": labels if ready else None,
    }
