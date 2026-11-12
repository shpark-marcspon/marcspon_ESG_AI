"""시험이 Word 를 코드로 짓는 도우미(저장소에 .docx 0 — 발주서 §1-3). 지은 바이트는 메모리에만 둔다."""

import io
import zipfile
from collections.abc import Callable, Mapping

import docx
from docx.document import Document

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f'xmlns:w="{W_NS}"'
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def built(build: Callable[[Document], object] | None = None) -> bytes:
    """python-docx 의 기본 틀에 `build` 를 한 문서의 바이트."""
    document = docx.Document()
    if build is not None:
        build(document)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def parts_of(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {info.filename: archive.read(info.filename) for info in archive.infolist()}


def zip_bytes(parts: Mapping[str, bytes], method: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", method) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def document_xml(body: str, extra_ns: str = "") -> bytes:
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W} {extra_ns}><w:body>{body}'
        "</w:body></w:document>"
    ).encode()


def with_body(body: str, extra_ns: str = "", replace: Mapping[str, bytes] | None = None) -> bytes:
    """기본 틀의 `word/document.xml` 몸을 `body` 로 바꾼 docx. `replace` 는 항목 이름 → 바이트(그 항목을 통째로)."""
    parts = parts_of(built())
    parts["word/document.xml"] = document_xml(body, extra_ns)
    parts.update(replace or {})
    return zip_bytes(parts)


def p(text: str) -> str:
    return f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def tc(text: str = "", props: str = "") -> str:
    inner = f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>' if text else ""
    return f"<w:tc><w:tcPr>{props}</w:tcPr><w:p>{inner}</w:p></w:tc>"


def tr(*cells: str, props: str = "") -> str:
    return f"<w:tr><w:trPr>{props}</w:trPr>{''.join(cells)}</w:tr>" if props else f"<w:tr>{''.join(cells)}</w:tr>"


def tbl(*rows: str) -> str:
    return f"<w:tbl>{''.join(rows)}</w:tbl>"


def vmerge_chain(rows: int) -> str:
    """열 하나·`rows` 행 표: 첫 칸 vMerge restart, 나머지 continue(세로 병합 사슬 — ★d)."""
    first = tr(tc("가상", '<w:vMerge w:val="restart"/>'))
    return tbl(first + tr(tc("", "<w:vMerge/>")) * (rows - 1))
