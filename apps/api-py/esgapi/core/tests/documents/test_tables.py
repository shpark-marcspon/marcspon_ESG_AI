"""C2 — 표 둘(core_document_artifacts·core_document_artifact_uses)의 CHECK·UNIQUE·같은 회사 외래 키. 업무 층.
앱 역할의 권한(SELECT·INSERT 만 — UPDATE·DELETE 0, e7 ⑫)은 보안 층 tests/security/test_owner.py 가 잰다."""

from typing import Any

import pytest
from django.db import IntegrityError, transaction

from esgapi.core.documents.contract import CONTRACT, LAYOUTS, STATUSES
from esgapi.core.models import (
    DOCUMENT_ARTIFACT_LAYOUTS,
    DOCUMENT_ARTIFACT_STATUSES,
    DocumentArtifactRow,
    DocumentArtifactUseRow,
    DocumentRow,
)

pytestmark = pytest.mark.django_db

SHA = "e" * 64


def test_model_values_are_the_contract_values() -> None:
    assert (DOCUMENT_ARTIFACT_STATUSES, DOCUMENT_ARTIFACT_LAYOUTS) == (STATUSES, LAYOUTS)


def artifact(company_id: int, **overrides: Any) -> DocumentArtifactRow:
    values: dict[str, Any] = {
        "company_id": company_id,
        "contract": CONTRACT,
        "epoch": 1,
        "source_sha256": SHA,
        "layout": 2,
        "parser_name": "docparse",
        "parser_version": "0.1.0",
        "status": "ready",
        "page_count": 1,
        "body_bytes": 2,
        "document": {},
        "char_places": {},
        **overrides,
    }
    with transaction.atomic():
        return DocumentArtifactRow.for_company(company_id).create(**values)


def document(company_id: int) -> DocumentRow:
    return DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="u",
        file_name="가상.pdf",
        storage_key=f"k/{company_id}/{DocumentRow.unscoped.count()}",
        size_bytes=1,
        etag='"e"',
        status="uploaded",
    )


def use(company_id: int, document_id: int, artifact_id: int, **overrides: Any) -> DocumentArtifactUseRow:
    values: dict[str, Any] = {
        "company_id": company_id,
        "document_id": document_id,
        "document_etag": '"e"',
        "artifact_id": artifact_id,
        "contract": CONTRACT,
        "layout": 2,
        "epoch": 1,
        **overrides,
    }
    with transaction.atomic():
        return DocumentArtifactUseRow.for_company(company_id).create(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "partial"},
        {"layout": 3},
        {"epoch": 0},
        {"source_sha256": "E" * 64},
        {"page_count": 0},
        {"body_bytes": -1},
        {"document": None},  # ready 인데 본문 NULL
        {"char_places": None},
        {"status": "too_large"},  # too_large 인데 본문 있음
        {"status": "too_large", "document": None},
    ],
    ids=str,
)
def test_each_check_refuses(companies: tuple[int, int], overrides: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError):
        artifact(companies[0], **overrides)


def test_too_large_holds_no_body(companies: tuple[int, int]) -> None:
    row = artifact(companies[0], status="too_large", document=None, char_places=None)
    assert (row.document, row.char_places) == (None, None)


def test_the_key_is_unique_per_company_epoch_and_layout(companies: tuple[int, int]) -> None:
    a, b = companies
    artifact(a)
    with pytest.raises(IntegrityError):
        artifact(a)
    artifact(a, epoch=2)  # EPOCH 다르면 새 행
    artifact(a, layout=1)  # layout 다르면 새 행
    artifact(b)  # 회사 다르면 새 행
    assert DocumentArtifactRow.unscoped.count() == 4


def test_a_use_is_unique_and_stays_in_one_company(companies: tuple[int, int]) -> None:
    a, b = companies
    mine, theirs = artifact(a), artifact(b)
    doc = document(a)
    use(a, doc.id, mine.id)
    with pytest.raises(IntegrityError):
        use(a, doc.id, mine.id)
    use(a, doc.id, mine.id, epoch=2)  # 다른 판의 이음은 따로
    with pytest.raises(IntegrityError):
        use(a, doc.id, theirs.id, document_etag='"x"')  # 남의 회사 산출물(같은 회사 외래 키)
    with pytest.raises(IntegrityError):
        use(b, doc.id, theirs.id)  # 남의 회사 문서
    assert DocumentArtifactUseRow.unscoped.count() == 2
