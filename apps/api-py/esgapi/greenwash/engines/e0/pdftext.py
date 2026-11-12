# pyright: basic
# ruff: noqa: UP006, UP035
# ↑ GW1 사본이라 본문을 고치지 않는다(AST 대조). 끈 규칙은 이 파일이 실제로 어기는 것만:
#   typing.List 꼴; typing 의 옛 이름
"""PDF → 쪽 글 목록(`pypdf`). 노트북의 `PyPDFLoader(pdf_path).load()` 자리다(셀 8).

쪽 번호는 0부터다(`metadata["page"]`). `PyPDFLoader` 가 붙이는 `source` 따위의 메타는 옮기지 않는다.
"""

import hashlib
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from pypdf import PdfReader


def read_page_texts(pdf_path) -> List[str]:
    """쪽마다 `extract_text()` 한 글. `PyPDFLoader` 의 기본(쪽 단위, plain)과 같은 글이 되게 한다(README 의 ★1)."""
    reader = PdfReader(str(pdf_path))
    return [_loader_text(page.extract_text()) for page in reader.pages]


def _loader_text(text: str) -> str:
    # `PyPDFLoader`(langchain-community 0.4.2 의 `PyPDFParser`)는 쪽 글의 양끝 공백을 뗀다. 가운데는 건드리지 않는다.
    return text.strip()


def docs_from_texts(texts: List[str]) -> List[Document]:
    return [Document(page_content=t, metadata={"page": i}) for i, t in enumerate(texts)]


def load_docs(pdf_path) -> List[Document]:
    return docs_from_texts(read_page_texts(pdf_path))


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()
