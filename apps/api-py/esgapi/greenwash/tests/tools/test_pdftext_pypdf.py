"""PDF 읽개 PypdfText(tools/pdftext_pypdf.py): 바이트에서 쪽 글을 쪽마다 읽는다. 파일·공급사 0 — 메모리에서 지은 PDF."""

import io

from pypdf import PdfWriter

from esgapi.greenwash.tools.pdftext_pypdf import PypdfText


def test_pypdf_text_reads_pages_from_bytes() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    out = io.BytesIO()
    writer.write(out)
    assert PypdfText().page_texts(out.getvalue()) == ["", ""]
