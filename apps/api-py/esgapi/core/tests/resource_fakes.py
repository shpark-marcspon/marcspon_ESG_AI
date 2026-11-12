"""core/resources 의 포트 셋(저장소·파서·PDF 재기)의 가짜. 테스트 파일이 아니다(시험들이 같이 쓰는 준비물).

제품 모듈(core/resources/storage.py·parser.py)에 있던 것을 밴드 CU2(2026-10-16)가 여기로 옮겼다. 그 모듈의 make 는
이제 가짜를 고르지 않는다. 여기는 `esgapi/**/tests` 라 wheel 에 실리지 않는다(pyproject.toml 의 exclude) —
제품이 이것을 import 하면 설치본에서 ImportError 다.

    FakeStorage   메모리의 저장소(포트 ObjectStorage). 포트의 넷에 더해, 바이트를 심는 put(키, 바이트)과 실패를 시키는
                  fail_with·put_fail_with
    FakeParser    PDF 의 sha256 → 결과의 표를 쥔 파서(포트 DocumentParser). 결과를 고치거나 짓지 않는다
    FakePdfProbe  정해 둔 결과 하나를 돌려주는 PDF 재기(포트 PdfProbe — X1b-2a). 부른 것은 calls 에
    build_pdf     시험이 짓는 작은 PDF 바이트(쪽 n 개, 쪽마다 같은 글 또는 빈 쪽 — 저장소에 .pdf 파일을 두지 않는다)
"""

import hashlib
from collections.abc import Mapping
from typing import overload

from esgapi.core.resources.ports.parser import ParseFailed, ParseFailureDetail, ParseResult
from esgapi.core.resources.ports.pdf import ProbeResult
from esgapi.core.resources.ports.storage import (
    GetResult,
    HeadResult,
    ObjectBytes,
    ObjectFound,
    ObjectMissing,
    ObjectPut,
    ObjectTooLarge,
    PresignedUpload,
    PutResult,
    StorageDenied,
    StorageUnavailable,
)
from esgapi.core.resources.storage import DEFAULT_UPLOAD_TTL_S


class FakeStorage:
    """메모리의 가짜. 포트의 넷에 더해, 테스트가 바이트를 심는 put(키, 바이트)과 실패를 시키는 fail_with 를 갖는다.

    put 은 두 꼴이다: put(키, 바이트) 은 테스트가 심는 것(ETag 를 돌려준다), put(키, content=, media_type=) 은 포트의
    쓰기(실행기 — ObjectPut 갈래를 돌려준다). 포트의 쓰기는 put_calls 에 적히고 put_fail_with 가 있으면 그것을 돌려준다
    (head·get 의 fail_with 와 따로 — 읽기는 되고 쓰기만 실패하는 저장소를 흉내 낸다). 쓴 꼴은 media_types 에.
    presign_upload 의 주소는 닿지 않는 가짜다(.invalid). 부른 것은 presigned·head_calls·get_calls 에 적힌다.
    """

    def __init__(self, *, upload_ttl_s: int = DEFAULT_UPLOAD_TTL_S) -> None:
        self.upload_ttl_s = upload_ttl_s
        self.objects: dict[str, tuple[bytes, str]] = {}  # 키 → (바이트, ETag)
        self.fail_with: StorageDenied | StorageUnavailable | None = None  # 있으면 head·get 이 이것을 돌려준다
        self.put_fail_with: StorageDenied | StorageUnavailable | None = None  # 있으면 포트의 put 이 이것을 돌려준다
        self.presigned: list[tuple[str, int]] = []  # (키, content_length)
        self.head_calls: list[str] = []
        self.get_calls: list[str] = []
        self.put_calls: list[str] = []  # 포트의 put 만(심기는 적지 않는다)
        self.media_types: dict[str, str] = {}  # 포트의 put 으로 쓴 키 → 꼴

    @overload
    def put(self, key: str, data: bytes, *, etag: str | None = None) -> str: ...

    @overload
    def put(self, key: str, *, content: bytes, media_type: str) -> PutResult: ...

    def put(
        self,
        key: str,
        data: bytes | None = None,
        *,
        etag: str | None = None,
        content: bytes | None = None,
        media_type: str | None = None,
    ) -> str | PutResult:
        """put(키, 바이트) — 객체를 심는다(클라이언트가 올린 셈이다). ETag 를 안 주면 S3 의 한 번 올리기와 같은 꼴
        (따옴표 낀 md5). put(키, content=, media_type=) — 포트의 쓰기."""
        if data is None:
            assert content is not None and media_type is not None  # overload 가 막는다
            self.put_calls.append(key)
            if self.put_fail_with is not None:
                return self.put_fail_with
            self.media_types[key] = media_type
            return ObjectPut(etag=self._keep(key, content, None))
        return self._keep(key, data, etag)

    def _keep(self, key: str, data: bytes, etag: str | None) -> str:
        tag = etag if etag is not None else f'"{hashlib.md5(data, usedforsecurity=False).hexdigest()}"'
        self.objects[key] = (data, tag)
        return tag

    def presign_upload(self, key: str, *, content_length: int) -> PresignedUpload:
        self.presigned.append((key, content_length))
        return PresignedUpload(
            url=f"https://fake-storage.invalid/{key}?size={content_length}", expires_in_s=self.upload_ttl_s
        )

    def head(self, key: str) -> HeadResult:
        self.head_calls.append(key)
        if self.fail_with is not None:
            return self.fail_with
        found = self.objects.get(key)
        if found is None:
            return ObjectMissing()
        return ObjectFound(size_bytes=len(found[0]), etag=found[1])

    def get(self, key: str, *, max_bytes: int) -> GetResult:
        self.get_calls.append(key)
        if self.fail_with is not None:
            return self.fail_with
        found = self.objects.get(key)
        if found is None:
            return ObjectMissing()
        if len(found[0]) > max_bytes:
            return ObjectTooLarge(max_bytes)
        return ObjectBytes(data=found[0], etag=found[1])


class FakeParser:
    """PDF 의 sha256 → 결과의 표를 쥔 가짜. 표에 없는 입력은 rejected(code `unknown_pdf`)다.

    결과를 고치거나 짓지 않는다.
    """

    def __init__(self, results: Mapping[str, ParseResult] | None = None) -> None:
        self._results = dict(results or {})
        self.calls: list[tuple[str, str]] = []  # (sha256, file_name)
        self.layouts: list[int] = []  # 부를 때마다 받은 분해 판(calls 와 같은 차례)
        self.charts: list[bool] = []  # 부를 때마다 받은 도표 라벨 요청(calls 와 같은 차례 — CHL1). 결과는 표 그대로

    def parse(self, pdf: bytes, *, file_name: str, layout: int = 1, charts: bool = False) -> ParseResult:
        digest = hashlib.sha256(pdf).hexdigest()
        self.calls.append((digest, file_name))
        self.layouts.append(layout)
        self.charts.append(charts)
        found = self._results.get(digest)
        if found is None:
            return ParseFailed(
                "rejected",
                ParseFailureDetail(
                    status=None, code="unknown_pdf", message=f"가짜 파서의 표에 없는 PDF 다: sha256 {digest}"
                ),
            )
        return found


class FakePdfProbe:
    """정해 둔 결과를 그대로 돌려주는 가짜. 부른 것은 calls 에 (바이트, text_pages) 로 적힌다."""

    def __init__(self, result: ProbeResult) -> None:
        self.result = result
        self.calls: list[tuple[bytes, int]] = []

    def probe(self, content: bytes, *, text_pages: int) -> ProbeResult:
        self.calls.append((content, text_pages))
        return self.result


def build_pdf(pages: int, *, text: str | None = None) -> bytes:
    """쪽 `pages` 개의 PDF. `text` 가 있으면 쪽마다 그 글(Helvetica, 괄호·역빗금 없는 ASCII), 없으면 빈 쪽.

    xref 의 자리를 손으로 셈한 가장 작은 꼴이다(pdfium·pypdf 둘 다 연다).
    쪽 0 은 pdfium 이 열지 않는다(잰 — 2026-10-19).
    """
    if text is not None and not (text.isascii() and not set(text) & set("()\\")):
        raise ValueError("text 는 괄호·역빗금 없는 ASCII 여야 한다")
    font = 3 + 2 * pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(pages))
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode()]
    for i in range(pages):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 {font} 0 R >> >> "
            f"/Contents {4 + 2 * i} 0 R >>".encode()
        )
        body = b"" if text is None else f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
        objects.append(b"<< /Length %d >>\nstream\n" % len(body) + body + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)
