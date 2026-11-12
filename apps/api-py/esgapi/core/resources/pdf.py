"""포트 `pdf`(core/resources/ports/pdf.py 의 PdfProbe)의 구현: 자식 프로세스에서 pypdfium2 로 잰다(X1b-2a).

    PdfiumProbe().probe(content, text_pages=n)   쪽 수와 앞 n 쪽의 글자 층 유무

★ 왜 자식 프로세스인가: 믿지 못할 PDF 를 C 라이브러리(pdfium)로 연다. 파이썬의 시간 한도(signal·스레드)는 C 코드에
  끼어들지 못한다 — 붙들리거나 죽으면 api 일꾼(gunicorn sync, timeout 30초)이 같이 죽고, 올림 확인 앞이라 문서가
  `awaiting_upload` 에 남아 부를 때마다 다시 잰다(critic X1b-2a-1 B2). 그래서 이 프로세스는 pypdfium2 를
  import 하지 않고, 자식(`_CHILD`)만 연다: 벽시계 한도 `timeout=`(넘으면 죽인다), 주소 공간·CPU·파일 크기 한도
  (`_limits` — RLIMIT_AS·RLIMIT_CPU·RLIMIT_FSIZE).
★ 자식의 출력은 부모 메모리로 통째 들이지 않는다(가지 리뷰 X1b-2a): 자식은 쪽마다 strip() 뒤 앞
  PDF_PROBE_TEXT_CHARS 자만 내고, 부모는 stdout·stderr 를 임시 파일로 받아 PDF_PROBE_OUTPUT_BYTES 까지만 읽는다
  (넘으면 PdfUnreadable("error")). 압축 글 스트림 PDF 는 쪽 하나에 몇 MB 의 글을 낼 수 있다(검증 실측 — 쪽당
  100만 자 → 3.06MB).
★ 실패는 던지지 않는다. 자식을 띄우지 못함(OSError·SubprocessError — preexec_fn 안의 실패 포함)까지
  PdfUnreadable 갈래다.
  기록(log)에는 갈래와 예외 클래스 이름만 싣는다(파일 이름·바이트·자식의 stderr 본문은 싣지 않는다).
★ 글자 층의 판정 규칙은 부모의 core/calc/documents.py has_text 하나다: 자식은 앞 n 쪽의 글(쪽마다 strip() 뒤 앞
  몇 자)을 돌려줄 뿐이다.
★ 자식에게 DB 연결을 물려주지 않는다: subprocess 의 close_fds 기본값(True)이 표준 입출력 밖의 파일 기술자를 닫는다.
  자식은 `-I`(격리 — 현재 폴더·사용자 site·PYTHON* 환경 무시)로, **빈 환경**(`env={}` — DB URL·비밀 키·API 키를
  물려주지 않는다)으로 뜬다. 넘길 것이 없다: 파이썬은 절대 경로(sys.executable)로 부르고 pypdfium2 는 제 패키지 안의
  라이브러리를 연다.
★ 테스트가 바꿔 끼우는 틈(부를 때 모듈 속성으로 읽는다): `_CHILD`(자식 글), `subprocess.run`.
무효 조건: setrlimit 이 안 되는 플랫폼(macOS 는 RLIMIT_AS 를 받지 않는다)에서는 그 한도 없이 돌고 경고 줄
  하나를 남긴다 — 벽시계 한도는 그대로다. 한도 값(core/calc/documents.py)은 어림이다.
"""

import json
import logging
import os
import resource
import subprocess
import sys
import tempfile
from typing import Final, cast

from esgapi.core.calc.documents import (
    PDF_PROBE_MEMORY_BYTES,
    PDF_PROBE_OUTPUT_BYTES,
    PDF_PROBE_TEXT_CHARS,
    PDF_PROBE_TIMEOUT_S,
    has_text,
)
from esgapi.core.resources.ports.pdf import PdfProbed, PdfUnreadable, ProbeResult
from esgapi.core.resources.ports.storage import ObjectBytes, ObjectStorage

logger = logging.getLogger(__name__)

# 자식이 setrlimit 을 못 했을 때 stderr 에 남기는 표지(부모가 보고 경고 줄로 옮긴다).
_NO_LIMIT_MARK: Final = b"pdf-probe: setrlimit unsupported:"

# 자식의 글. 표준 라이브러리와 pypdfium2 만 import 한다. 입력: stdin 의 PDF 바이트, argv[1] 의 쪽 수 n.
# argv[2] 의 글자 수 k. 출력: JSON 한 줄 — {"pages": 쪽 수, "texts": [앞 n 쪽마다 strip() 뒤 앞 k 자]} 또는
# {"error": "not_pdf" | "encrypted"}.
# pdfium 의 오류 코드 4 = FPDF_ERR_PASSWORD(암호), 그 밖은 PDF 로 못 엶.
_CHILD: str = """
import json, sys
import pypdfium2 as pdfium
data = sys.stdin.buffer.read()
n, k = int(sys.argv[1]), int(sys.argv[2])
try:
    pdf = pdfium.PdfDocument(data)
except pdfium.PdfiumError as err:
    print(json.dumps({"error": "encrypted" if err.err_code == 4 else "not_pdf"}))
    sys.exit(0)
pages = len(pdf)
texts = [pdf[i].get_textpage().get_text_range().strip()[:k] for i in range(min(n, pages))]
print(json.dumps({"pages": pages, "texts": texts}))
"""


def _limits() -> None:
    """자식에서 exec 앞에 돈다(preexec_fn). 한도마다 따로 걸고, 못 걸면 stderr 에 표지를 남기고 넘어간다."""
    cpu = PDF_PROBE_TIMEOUT_S + 1
    for name, limit, value in (
        ("RLIMIT_AS", resource.RLIMIT_AS, PDF_PROBE_MEMORY_BYTES),
        ("RLIMIT_CPU", resource.RLIMIT_CPU, cpu),
        ("RLIMIT_FSIZE", resource.RLIMIT_FSIZE, 2 * PDF_PROBE_OUTPUT_BYTES),
    ):
        try:
            resource.setrlimit(limit, (value, value))
        except (ValueError, OSError):
            # fd 2 = 부모가 받는 stderr 관(파이썬 버퍼를 거치지 않는다)
            os.write(2, _NO_LIMIT_MARK + name.encode() + b"\n")


def _decoded(stdout: bytes) -> ProbeResult:
    """자식의 JSON 한 줄 → 갈래. 꼴이 어긋나면 error, 쪽 0 이면 empty."""
    try:
        parsed: object = json.loads(stdout)
    except ValueError:
        return PdfUnreadable("error")
    if not isinstance(parsed, dict):
        return PdfUnreadable("error")
    answer = cast(dict[str, object], parsed)
    error = answer.get("error")
    if error == "not_pdf":
        return PdfUnreadable("not_pdf")
    if error == "encrypted":
        return PdfUnreadable("encrypted")
    pages, texts = answer.get("pages"), answer.get("texts")
    if not isinstance(pages, int) or isinstance(pages, bool) or not isinstance(texts, list):
        return PdfUnreadable("error")
    page_texts = [text for text in cast(list[object], texts) if isinstance(text, str)]
    if len(page_texts) != len(cast(list[object], texts)):
        return PdfUnreadable("error")
    if pages < 1:
        return PdfUnreadable("empty")  # page_count ≥1 CHECK — 값으로 내면 올림 확인의 갱신이 깨진다
    return PdfProbed(page_count=pages, has_text=has_text(page_texts))


class PdfiumProbe:
    def probe(self, content: bytes, *, text_pages: int) -> ProbeResult:
        limit = PDF_PROBE_OUTPUT_BYTES
        try:
            with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err_out:
                done = subprocess.run(  # noqa: S603  고정된 인자(이 파이썬·고정 글·정수)만 넘긴다
                    [sys.executable, "-I", "-c", _CHILD, str(text_pages), str(PDF_PROBE_TEXT_CHARS)],
                    input=content,
                    stdout=out,
                    stderr=err_out,
                    env={},
                    timeout=PDF_PROBE_TIMEOUT_S,
                    check=False,
                    preexec_fn=_limits,  # gunicorn sync 일꾼(스레드 없음)과 워커에서 부른다
                )
                out.seek(0)
                stdout = out.read(limit + 1)
                err_out.seek(0)
                stderr = err_out.read(limit)
        except subprocess.TimeoutExpired:
            logger.warning("pdf_probe_unreadable reason=timeout")
            return PdfUnreadable("timeout")
        except (OSError, subprocess.SubprocessError) as err:
            logger.warning("pdf_probe_unreadable reason=error error_class=%s", type(err).__name__)
            return PdfUnreadable("error")
        if _NO_LIMIT_MARK in stderr:
            logger.warning("pdf_probe_no_rlimit (이 플랫폼은 자식의 한도 일부를 받지 않는다 — 벽시계 한도만)")
        if done.returncode < 0:
            logger.warning("pdf_probe_unreadable reason=crashed signal=%s", -done.returncode)
            return PdfUnreadable("crashed")
        if done.returncode != 0:
            logger.warning("pdf_probe_unreadable reason=error returncode=%s", done.returncode)
            return PdfUnreadable("error")
        if len(stdout) > limit:
            logger.warning("pdf_probe_unreadable reason=error output_over_limit=%s", limit)
            return PdfUnreadable("error")
        result = _decoded(stdout)
        if isinstance(result, PdfUnreadable):
            logger.warning("pdf_probe_unreadable reason=%s", result.reason)
        return result


def stored_bytes(storage: ObjectStorage, key: str, *, max_bytes: int, etag: str) -> bytes | None:
    """재려고 저장소의 원본을 읽는다. 못 읽었거나(없음·너무 큼·거절·못 닿음) ETag 가 `etag` 와 다르면 None.

    트랜잭션 밖에서 부른다(올림 확인의 ③' — 저장소가 느려도 행을 붙들지 않는다).
    """
    content = storage.get(key, max_bytes=max_bytes)
    if not isinstance(content, ObjectBytes) or content.etag != etag:
        return None
    return content.data
