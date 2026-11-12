"""PDF 엔진 이음매. 분해기의 PDF 읽기는 전부 여기를 지난다.

엔진은 `pdfium`(pypdfium2) 하나다. 주고받는 자료의 꼴은 `types.py`.
원본(esg-lab `py/docparse/engine/__init__.py`)에는 엔진이 둘이었고 고르는 인자가 있었다. 여기서는 걷었다.
"""

from . import pdfium_engine
from .types import PdfOpenError, Point, Rect

DEFAULT_ENGINE = "pdfium"
ENGINES = ("pdfium",)


def open_pdf(path, engine=None):
    """PDF 를 열어 엔진의 문서 객체를 돌려준다 (`with` 로 닫는다). 열지 못하면 `PdfOpenError`.

    `engine` 은 원본에서 가져온 모듈(`document`·`render`·`score`)이 넘기는 자리라 남겼다. `None` 과 `"pdfium"` 만
    받는다.
    """
    name = engine or DEFAULT_ENGINE
    if name not in ENGINES:
        raise ValueError(f"알 수 없는 엔진: {name} (엔진은 {DEFAULT_ENGINE} 하나다)")
    return pdfium_engine.open_document(path)


__all__ = ["DEFAULT_ENGINE", "ENGINES", "PdfOpenError", "Point", "Rect", "open_pdf"]
