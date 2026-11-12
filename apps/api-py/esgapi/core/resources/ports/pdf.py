"""포트: PDF 재기. 「PDF 바이트 → 쪽 수와 앞 n 쪽의 글자 층 유무」(X1b-2a — 올림 확인이 부른다).

구현은 core/resources/pdf.py(자식 프로세스 + pypdfium2). 시험의 가짜는 core/tests/resource_fakes.py 의 FakePdfProbe.
표준 라이브러리만 쓴다.

실패는 던지지 않고 갈래로 돌려준다. 올림 확인은 어느 갈래든 올림을 막지 않고 값 둘을 NULL(「모른다」)로 둔다:
  not_pdf    PDF 로 열리지 않는다
  encrypted  암호가 걸려 열지 못했다
  empty      쪽이 0 이다(page_count ≥1 CHECK 에 걸리므로 값으로 내지 않는다)
  timeout    자식 프로세스가 시간 한도를 넘었다(죽였다)
  crashed    자식 프로세스가 신호로 죽었다(C 라이브러리의 충돌·메모리 한도)
  error      그 밖(0 아닌 종료, 읽지 못할 출력, 자식을 띄우지 못함)
"""

from dataclasses import dataclass
from typing import Literal, Protocol

PdfUnreadableReason = Literal["not_pdf", "encrypted", "empty", "timeout", "crashed", "error"]


@dataclass(frozen=True, slots=True)
class PdfProbed:
    page_count: int  # ≥1
    has_text: bool  # 앞 text_pages 쪽 가운데 공백 밖 글자가 있는 쪽이 있다


@dataclass(frozen=True, slots=True)
class PdfUnreadable:
    reason: PdfUnreadableReason


ProbeResult = PdfProbed | PdfUnreadable


class PdfProbe(Protocol):
    def probe(self, content: bytes, *, text_pages: int) -> ProbeResult:
        """쪽 수와 앞 `text_pages` 쪽의 글자 층 유무. 실패를 던지지 않고 `PdfUnreadable` 로 돌려준다."""
        ...
