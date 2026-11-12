"""올린 문서의 쪽 수(GET /translation/documents/{document_id}/pages 의 몸 — 밴드 TRP6, 결정 MARC-ENT-452).

core 의 문서 셀렉터(회사 조건)로 문서를 찾고, core 의 저장소 이음매로 원본을 읽어 tools/page_tags.py 로 센다. 남의
도메인(core)을 엮으므로 Action 이다(batches.py·runs/service/services/files.py 꼴). 쓰기·감사 0, 쿼리는 문서 하나.
요청마다 읽는다(캐시·DB 0). 읽기 길은 runs/tasks.py `_document` 꼴(회사 범위 → 저장소 → etag 대조).

갈래(예외 0 — MemoryError 빼고). 못 읽음은 404·503 이 아니라 **값 null** 이다 — 웹은 그리드를 숨기고 올림은 성공:
    NotFound   없는 문서·남의 회사 문서
    Pages      count = [PAGE n] 최댓값 | None, reason = None 의 까닭(로그용)
로그 `translation_pages_unreadable reason=<r>` 에는 문서 글·저장소 키를 싣지 않는다(`no_pages` 는 로그 0). 단계는 까닭이
가른다(밴드 TRS2, MARC-ISSUE-385): 사용자 파일 탓(page_tags 의 Reason — pdf·not_utf8·too_large·unreadable 등)과 아직
올림 전(`not_uploaded`)은 INFO, 저장소·설정 탓(object_missing·object_too_large·storage_denied·storage_unavailable·
storage_unconfigured·etag_mismatch)은 WARNING — 운영이 볼 것만 경고로 남긴다.
"""

import logging
from dataclasses import dataclass
from typing import Final, get_args

from esgapi.core.resources.ports.storage import ObjectBytes, ObjectMissing, ObjectTooLarge, StorageDenied
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.core.service.services import documents
from esgapi.translation.tools import page_tags

logger = logging.getLogger(__name__)

_NOT_OURS: Final = frozenset((*get_args(page_tags.Reason), "not_uploaded"))
"""INFO 로 남기는 까닭 — 사용자 파일 탓이거나 올림 전. 그 밖(저장소·설정)은 WARNING."""


@dataclass(frozen=True, slots=True)
class NotFound:
    """문서가 없다(남의 회사 문서도 이 갈래)."""


@dataclass(frozen=True, slots=True)
class Pages:
    document_id: int
    page_count: int | None
    reason: str | None


def document_pages(*, company_id: int, document_id: int) -> Pages | NotFound:
    """그 회사 문서의 [PAGE n] 최댓값(못 세면 None)."""
    document = document_selectors.find_document(company_id=company_id, document_id=document_id)
    if document is None:
        return NotFound()
    if document.status != "uploaded":
        return _unknown(document_id, "not_uploaded")
    storage = documents.default_storage()
    if storage is None:
        return _unknown(document_id, "storage_unconfigured")
    got = storage.get(document.storage_key, max_bytes=min(document.size_bytes, documents.max_upload_bytes()))
    if not isinstance(got, ObjectBytes):
        return _unknown(document_id, _storage_reason(got))
    if document.etag is not None and got.etag != document.etag:
        return _unknown(document_id, "etag_mismatch")
    counted = page_tags.page_count(got.data)
    if counted.count is None:
        return _unknown(document_id, counted.reason or "no_pages")
    return Pages(document_id, counted.count, None)


def _storage_reason(got: object) -> str:
    match got:
        case ObjectMissing():
            return "object_missing"
        case ObjectTooLarge():
            return "object_too_large"
        case StorageDenied():
            return "storage_denied"
        case _:
            return "storage_unavailable"


def _unknown(document_id: int, reason: str) -> Pages:
    if reason != "no_pages":
        level = logging.INFO if reason in _NOT_OURS else logging.WARNING
        logger.log(level, "translation_pages_unreadable reason=%s", reason)
    return Pages(document_id, None, reason)
