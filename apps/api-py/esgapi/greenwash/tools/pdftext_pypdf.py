"""PDF 읽개 하나 — pypdf. 다음 읽개는 옆 파일로 두고, 어느 읽개를 쓸지는 판(흐름)이 고른다(MARC-ENT-267)."""

import io

from pypdf import PdfReader


class PypdfText:
    """pypdf 로 쪽 글을 뽑는다. GW1 `pdftext.read_page_texts`(사본 engines/e0/pdftext.py)와 같은 처리를 bytes 로
    다시 쓴 것이다(그 함수는 경로를 받아 파일을 연다):
    쪽마다 `extract_text()` 뒤 양끝 공백을 뗀다(GW1 `_loader_text`)."""

    def page_texts(self, pdf: bytes) -> list[str]:
        reader = PdfReader(io.BytesIO(pdf))
        return [page.extract_text().strip() for page in reader.pages]
