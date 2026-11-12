"""올린 문서의 쪽 수(GET /translation/documents/{document_id}/pages — 밴드 TRP6, 결정 MARC-ENT-452).

새 번역 화면이 올린 docx·txt 의 쪽 그리드를 띄우는 데만 쓴다(표시용 — 엔진의 쪽 범위 판정은 그대로). 값은 요청마다
원본을 읽어 센다(DB 에 적지 않는다). 칸마다 아래의 docstring 이 OpenAPI 의 description 이 된다.
"""

from typing import Annotated, TypedDict

from pydantic import Field, with_config

from esgapi.translation.contracts.shapes import FORBID


@with_config(FORBID)
class TranslationDocumentPages(TypedDict):
    """그 문서의 [PAGE n] 최댓값."""

    documentId: int
    """경로의 문서 id."""
    pageCount: Annotated[int, Field(ge=1)] | None
    """[PAGE n] 의 가장 큰 n. null = 모름(태그 없음·PDF·읽지 못함·글이 너무 김) — 웹은 그리드를 숨긴다."""
