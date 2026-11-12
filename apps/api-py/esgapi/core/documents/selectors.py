"""읽기 포트 — 문서 산출물(밴드 RP2a ①, 결정 MARC-ENT-514 — 설계 §1-7). 쓰지 않는다.

    find_artifact(company_id, document_id, etag, layout)   그 문서(그 etag)에 이어진 지금 EPOCH 의 산출물 머리 | None
    artifact_view(company_id, document_id, artifact_id, *, places=False, charts=False)   읽기 뷰(view.DocArtifactView)
    짓는 길(services.ensure_artifact)만 쓰는 것: find_by_source(ⓑ) · source_of(문서 행의 원본 칸)

★ 모든 산출물 읽기는 **uses ⋈ core_documents(같은 회사)** 를 지난다(514-9): 문서 행이 그 회사에 안 보이면 산출물도 없다.
  산출물 id 만으로는 못 읽는다(uses 행이 그 문서와 이어야 한다). 삭제 표시가 생기면 `_visible_uses` 에 조건 한 줄(e7).
  예외는 find_by_source(ⓑ — 같은 회사의 같은 PDF 를 찾음. 머리만 돌려주고 짓는 길이 곧 uses 를 넣는다) 하나다.
★ 조회마다 회사 조건을 적는다(<표>.for_company(company_id) — core/tests/test_selector_scope.py 가 이 파일도 훑는다).
★ 본문 칸(jsonb)은 find·목록에 싣지 않는다(e7 ⑬ — `HEAD_FIELDS` 만). 글자 자리는 places=True, 도표 라벨은
  charts=True 일 때만(CHL1).
"""

from dataclasses import dataclass

from django.db.models import Exists, OuterRef, QuerySet

from esgapi.core.documents.contract import (
    CONTRACT,
    EPOCH,
    ArtifactNotFound,
    ArtifactRef,
    ParserInfo,
)
from esgapi.core.documents.view import UNAVAILABLE, DocArtifactView
from esgapi.core.models import DocumentArtifactRow, DocumentArtifactUseRow, DocumentRow

CHARTS_LAYOUT, CHARTS_EPOCH = 2, 2  # 도표 라벨을 받는 판·처음 받은 EPOCH(CHL1)

HEAD_FIELDS = (
    "id",
    "company_id",
    "source_sha256",
    "parser_name",
    "parser_version",
    "layout",
    "epoch",
    "page_count",
    "body_bytes",
    "status",
)


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """짓는 길이 보는 문서 행의 칸(core_documents — 그 회사의 것)."""

    id: int
    storage_key: str
    etag: str | None
    sha256: str | None  # NULL = 분해 일감이 아직 안 채웠다(reconcile 의 layout 1 분해)
    page_count: int | None  # NULL = 올림 확인이 못 쟀다


def ref_of(row: DocumentArtifactRow) -> ArtifactRef:
    status = "ready" if row.status == "ready" else "too_large"
    return ArtifactRef(
        id=row.id,
        source_sha256=row.source_sha256,
        parser=ParserInfo(name=row.parser_name, version=row.parser_version, layout=row.layout),
        epoch=row.epoch,
        page_count=row.page_count,
        body_bytes=row.body_bytes,
        status=status,
    )


def _visible_uses(company_id: int) -> "QuerySet[DocumentArtifactUseRow]":
    """그 회사의 uses 가운데 문서 행이 그 회사에 보이는 것(uses ⋈ core_documents)."""
    documents = DocumentRow.for_company(company_id).filter(pk=OuterRef("document_id"))
    return DocumentArtifactUseRow.for_company(company_id).filter(Exists(documents))


def find_artifact(*, company_id: int, document_id: int, etag: str, layout: int) -> ArtifactRef | None:
    """그 문서의 그 etag 바이트를 그 판(layout·지금 EPOCH)으로 분해한 산출물의 머리. 없으면(남의 것이어도) None."""
    use = (
        _visible_uses(company_id)
        .filter(document_id=document_id, document_etag=etag, contract=CONTRACT, layout=layout, epoch=EPOCH)
        .values_list("artifact_id", flat=True)
        .first()
    )
    if use is None:
        return None
    row = DocumentArtifactRow.for_company(company_id).filter(pk=use).only(*HEAD_FIELDS).first()
    return None if row is None else ref_of(row)


def find_by_source(*, company_id: int, sha256: str, layout: int) -> ArtifactRef | None:
    """그 회사에서 같은 PDF(sha256)를 그 판·지금 EPOCH 로 분해한 산출물의 머리(ⓑ — 짓는 길만 부른다)."""
    row = (
        DocumentArtifactRow.for_company(company_id)
        .filter(contract=CONTRACT, source_sha256=sha256, layout=layout, epoch=EPOCH)
        .only(*HEAD_FIELDS)
        .first()
    )
    return None if row is None else ref_of(row)


def source_of(*, company_id: int, document_id: int) -> SourceDocument | None:
    """그 회사의 그 문서 행의 원본 칸. 없으면(남의 것이어도) None."""
    row = (
        DocumentRow.for_company(company_id)
        .filter(pk=document_id)
        .values("id", "storage_key", "etag", "sha256", "page_count")
        .first()
    )
    return None if row is None else SourceDocument(**row)


def artifact_view(
    *, company_id: int, document_id: int, artifact_id: int, places: bool = False, charts: bool = False
) -> DocArtifactView:
    """그 문서에 이어진 그 산출물의 읽기 뷰. 이어짐이 없거나(남의 것이어도) 본문이 없으면(`too_large`)
    ArtifactNotFound. places=False 면 글자 자리를 읽지 않는다(뷰의 boxes 는 PlacesNotLoaded). charts=False 면 도표
    라벨을 읽지 않는다(뷰의 chart_labels 는 ChartLabelsNotLoaded — CHL1)."""
    if not _visible_uses(company_id).filter(document_id=document_id, artifact_id=artifact_id).exists():
        raise ArtifactNotFound(f"문서 {document_id} 에 이어진 산출물 {artifact_id} 가 없다")
    fields = (
        "id",
        "status",
        "document",
        *(("char_places",) if places else ()),
        *(("chart_labels", "layout", "epoch") if charts else ()),
    )
    row = DocumentArtifactRow.for_company(company_id).filter(pk=artifact_id).only(*fields).first()
    if row is None or row.status != "ready" or row.document is None:
        raise ArtifactNotFound(f"산출물 {artifact_id} 의 본문이 없다")
    if not charts:
        return DocArtifactView(
            artifact_id=row.id, document=row.document, char_places=row.char_places if places else None
        )
    return DocArtifactView(
        artifact_id=row.id,
        document=row.document,
        char_places=row.char_places if places else None,
        # EPOCH 2 이상·판 2 행의 빈 칸은 「라벨 못 지음」 — None(칸 없음: EPOCH 1·판 1)과 접지 않는다(CHL1 ④ N1)
        chart_labels=UNAVAILABLE
        if row.chart_labels is None and row.layout == CHARTS_LAYOUT and row.epoch >= CHARTS_EPOCH
        else row.chart_labels,
    )
