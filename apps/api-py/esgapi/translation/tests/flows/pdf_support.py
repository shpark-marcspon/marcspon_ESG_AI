"""흐름 translation.pdf@158 시험의 도움(밴드 TRD2): 지어낸 분해 판 2 문서 + 가짜 파서(core FakeParser) + 모의 공급사로
흐름을 끝까지 돌린다. 실호출 0 · 파서 HTTP 0 · 글·회사는 전부 지어낸 것."""

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from esgapi.core.flows.binding import DocumentInput
from esgapi.core.flows.run import run_flow
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.types import ProviderResponse
from esgapi.core.resources.ports.parser import DocumentParser, Parsed, ParseFailed, ParseFailureDetail, ParseResult
from esgapi.core.tests.resource_fakes import FakeParser
from esgapi.translation.flows import pdf_158 as pdf
from esgapi.translation.flows.binding_pdf_158 import TranslationPdfBinding
from esgapi.translation.tests.flows.settings_store import DefaultOnlyStore, FileModels
from esgapi.translation.tests.flows.support import FakeStore, Ran, mock_client

PDF = b"%PDF-1.7\n% virtual pdf for the translation flow tests\n"
PDF_SHA = hashlib.sha256(PDF).hexdigest()

ONE_PAGE_EN = "[BLOCK 1]\nWater stewardship\n\nThe virtual site cut its water use by 12 percent."
"""1쪽 문서의 모의 번역(엔진 번역 호출의 답 — 쪽 머리 [PAGE n] 는 엔진이 붙인다)."""


def block(page: int, order: int, text: str, bbox: list[float], **more: Any) -> dict[str, Any]:
    kind = more.pop("kind", "paragraph")
    return {
        "id": f"p{page}-b{order}",
        "page": page,
        "order": order,
        "kind": kind,
        "bbox": bbox,
        "text": text,
        "font_size": 9.0,
        "region": more.pop("region", "body"),
        "key": f"k{page:02d}{order:02d}",
    }


def document(pages: int = 1, *, layer: str = "present", layout: int = 2) -> dict[str, Any]:
    """쪽마다: 머리글 · 제목 + 문단(한 묶음). 쪽 1 의 문단에 숫자 12."""
    blocks: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        blocks += [
            block(page, 1, "Synthetic header", [40, 20, 300, 30], region="header"),
            block(page, 2, "물 관리", [40, 80, 280, 96], kind="heading"),
            block(page, 3, f"가상 사업장은 물 사용량을 {12 if page == 1 else page}% 줄였다.", [40, 100, 280, 140]),
        ]
    marked = {"layout": layout} if layout >= 2 else {}
    return {
        "schema_version": "0.1",
        "source": {"file_name": pdf.PARSER_FILE_NAME, "sha256": PDF_SHA, "page_count": pages},
        "parser": {"name": "docparse", "version": "0.0-virtual", "table_strategy": "lines", **marked},
        "pages": [{"page": p, "width": 595, "height": 842.0, "text_layer": layer} for p in range(1, pages + 1)],
        "sections": [],
        "blocks": blocks,
        "tables": [],
    }


def parsed(doc: Mapping[str, Any] | None = None) -> Parsed:
    return Parsed(document=dict(doc or document()), char_places={"containers": []})


def failed(kind: Any, code: str | None, status: int | None = None) -> ParseFailed:
    return ParseFailed(kind, ParseFailureDetail(status=status, code=code, message=f"가짜 파서 실패 {code}"))


def pdf_binding(parser: FakeParser, store: FakeStore | None = None, max_usd: float = 5.0) -> TranslationPdfBinding:
    return TranslationPdfBinding(
        store=store or FakeStore(),
        settings=DefaultOnlyStore(),
        models=FileModels(),
        max_usd=lambda: max_usd,
        mock=lambda: False,
        spent_usd=lambda _c, _r: 0.0,
        parser=lambda: parser,
    )


@dataclass(frozen=True)
class PdfRan(Ran):
    parser: FakeParser


def run_pdf(
    given: Mapping[str, Any],
    replies: Sequence[ProviderResponse] = (),
    *,
    result: ParseResult | None = None,
    content: bytes = PDF,
    llm: LlmClient | None = None,
    store: FakeStore | None = None,
    versions: Mapping[str, object] | None = None,
    max_usd: float = 5.0,
    parser_factory: Callable[[], DocumentParser] | None = None,
) -> PdfRan:
    """옵션을 PDF 끼움으로 받아(회사 1) 흐름을 끝까지 돌린다. 가짜 파서는 PDF 의 sha → result(기본 1쪽 문서).
    parser_factory 를 주면 어댑터가 그것으로 파서를 짓는다(설정 오류 시험)."""
    parser = FakeParser({PDF_SHA: result if result is not None else parsed()})
    doc = DocumentInput(content=content, media_type="application/pdf", file_name="virtual.pdf")
    binding = pdf_binding(parser, store, max_usd)
    inputs = binding.inputs_with(doc, given, company_id=1, versions=versions or {})
    made, openai = mock_client(replies)
    adapters = pdf.PdfAdapters(
        llm=llm or made,
        tenant="1",
        mock=False,
        spent_usd=lambda: 0.0,
        parser=parser_factory or (lambda: parser),
    )
    run = run_flow(pdf.FLOW, inputs, adapters)
    assert openai.pending == 0, f"심은 답 {openai.pending} 개가 남았다"
    return PdfRan(run, openai, parser)


def results_of(ran: Ran) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """결과 셋: result@1 · digest@1 · layout@1(차례 그대로)."""
    result, summary, layout = ran.run.output.results
    assert [r["schemaVersion"] for r in (result, summary, layout)] == [
        "translation.result@1",
        "translation.digest@1",
        "translation.layout@1",
    ]
    return result, summary, layout
