"""올린 docx·txt 의 `[PAGE n]` 최댓값(밴드 TRP6, 결정 MARC-ENT-452). 새 번역 화면의 쪽 그리드 **표시용**이다 — 엔진의
범위 판정(pipeline.source_and_pages)은 그대로이고, 이 수로 바꾸지 않는다.

    page_count(data) -> PageTags(count, reason)    count = 1 이상 n 의 최댓값 | None(모름 — 웹은 그리드를 숨김)

어떤 바이트를 받아도 예외 대신 None 과 까닭이다. `MemoryError` 와 우리 셈의 실수(KeyError·IndexError·RuntimeError —
아래 _ERRORS)만 밖으로 낸다(OOM 신호·버그를 「못 셈」으로 바꾸지 않는다).

★ 요청 안에서 부른다(gunicorn 동기 작업자) — 흐름의 문서 읽기·docx 읽개·python-docx 를 부르지 않는다(세로 병합 docx 가
  python-docx 에서 n² — docx_reader.py MAX_VMERGE_STEPS). 바이트와 XML 을 한 번 훑고, 줄마다 상수 일이다(선형).
  요소 깊이(MAX_DEPTH)·`>` 없이 이어진 바이트(MAX_TAG_RUN)가 상한을 넘으면 None `unsafe` — 셈 깊이는 5 라 값에는 0.
  최댓값이 MAX_PAGES 를 넘으면 None `too_many_pages`(그리드 칸 수 상한):
- 머리로 가른다(flows/colab_158.py 의 문서 읽기와 같은 차례): `PK\\x03\\x04` docx · `%PDF-` None ·
  그 밖 txt(UTF-8 strict).
- docx: zip 을 열기 전에 끝의 EOCD 로 가운데 목록 크기를 본다(1MiB 넘음·zip64 면 None — zipfile 이 목록 전체를
  ZipInfo 로 푸는 일을 막는다. tools/zip_guard.py — docx_reader 와 같이 쓴다). zip 의 `word/document.xml` 하나만
  64KiB 씩 expat 에 흘려 넣는다(트리 0, DOCTYPE 이면 멈춤 — 외부 엔티티 0).
  글은 python-docx 1.2.0 의 문단 글과 같은 자리에서만 모은다 — 몸 직속 `w:p` 의 `w:r`·`w:hyperlink/w:r` 의 직속
  `w:t`·`w:tab`·`w:ptab`·`w:cr`·`w:br`(`w:type` 없음·textWrapping 만 `\\n`)·`w:noBreakHyphen`
  (docx/oxml/text/paragraph.py:102 · hyperlink.py:45 · run.py:136-138·188). 표 칸·`w:sdt`·`w:ins`·`w:smartTag`·
  `w:fldSimple`·글상자의 글은 버린다(docx_reader 도 몸 직속 `w:p`·`w:tbl` 만 읽고, 표 줄은 pipe 라 태그 줄이 못 된다).
- 줄마다: `page`(대소문자 무시)가 없는 줄은 건너뛰고, 있으면 `normalize_structured_tags(줄).strip()` 이
  `PAGE_TAG_LINE_RE` 에 맞을 때 n 을 모은다. 정규화 앞에서 5칸 이상 이어진 빈칸·탭을 4칸으로 줄인다 — 정규화의
  `[ \\t]+\\n` 이 긴 빈칸에서 n² 라서다(4칸 이상은 정규화·태그 꼴에서 같은 뜻 — `^\\s{0,3}#` 만 칸 수를 센다).

엔진 셈과 다를 수 있는 자리(그리드 표시용으로 받아들임 — tests/tools/test_page_tags.py 의 표본 셋은 같음을 단언):
| 자리 | 이 셈 | 엔진 |
|---|---|---|
| 표 칸·`w:sdt` 안 태그 | 안 셈 | 안 셈(표는 pipe 줄, sdt 는 빠짐 — 같음) |
| `word/document.xml` 이 아닌 이름의 본문 파트 | None | 관계로 찾아 읽음 |
| 정규화가 줄·문단을 넘어 합치는 꼴(`**` ↵ 태그 ↵ `**` 등) | 줄마다 | 글 전체 |
| `>` 없이 MAX_TAG_RUN(256KiB) 넘게 이어진 글(한 `w:t` 에 한글 약 8.7만 자) | None `unsafe` | 셈 |
| 최댓값 > MAX_PAGES(10,000) | None `too_many_pages` | 셈 |
| 글 길이 상한(MAX_SOURCE_CHARS) | 안 잼 — 그리드는 뜬다 | 쪽 범위 안 글자로 잼(표 pipe 줄까지, 밴드 TRS4) |
| txt 바이트 > MAX_TEXT_BYTES(2MiB) | None `too_large` | 범위 안 글자로 잼 |
| 쪽 조각 > MAX_PAGE_CHUNKS(300) | 값을 냄(최댓값 ≤ MAX_PAGES) | 실행 거절 |
| docx_reader 가 문서를 거절하는 꼴(다른 파트의 DOCTYPE·암호 항목·vMerge/칸 상한 넘음) | 값을 냄 | 실행 거절 |
글 길이·쪽 조각·docx_reader 의 셋은 그리드는 뜨고 실행은 거절된다 — 표시 전용이라 받는다(발주서 F9). 글이 길면 쪽 범위를
고르게 그리드를 띄우고 실행이 범위 안 글자로 거절한다(MARC-ISSUE-393). 바깥 울타리는 바이트 상한이다.
"""

import io
import re
import struct
import xml.parsers.expat
import zipfile
import zlib
from dataclasses import dataclass
from typing import Final, Literal

from esgapi.translation.engines.colab_158.pages import PAGE_TAG_LINE_RE, file_roundtrip
from esgapi.translation.engines.colab_158.structured import normalize_structured_tags
from esgapi.translation.tools.docx_reader import MAX_BYTES, MAX_ENTRIES, MAX_XML_BYTES
from esgapi.translation.tools.zip_guard import central_directory_refusal

Reason = Literal[
    "pdf",
    "not_utf8",
    "too_large",
    "too_many_entries",
    "no_document_xml",
    "encrypted",
    "unsupported_compression",
    "unsafe",
    "unreadable",
    "no_pages",
    "too_many_pages",
]


@dataclass(frozen=True, slots=True)
class PageTags:
    count: int | None
    """1 이상 [PAGE n] 의 최댓값. None = 모름."""
    reason: Reason | None
    """None 일 때의 까닭(로그용 — 문서 글은 싣지 않는다). 값이 있으면 None."""


DOCUMENT_XML: Final = "word/document.xml"
CHUNK: Final = 64 * 1024
MAX_DEPTH: Final = 256
"""요소 깊이 상한 — 셈은 깊이 5 까지만 본다(경로 스택이 끝없이 자라지 않게)."""
MAX_TAG_RUN: Final = 256 * 1024
"""`>` 없이 이어진 바이트 상한 — 속성이 끝없는 태그 하나를 expat 이 통째로 들고 푸는 일을 막는다."""
MAX_PAGES: Final = 10_000
"""[PAGE n] 최댓값 상한 — 웹 그리드 칸 수(엔진의 쪽 조각 상한 300 보다 넉넉하게)."""
MAX_TEXT_BYTES: Final = 2 * 1024 * 1024
"""txt 의 디코드 전 바이트 상한(정직한 한글 약 70만 자) — 요청 길의 훑기를 2초 안에 묶는다. 태그·`page` 짧은 줄로만 채운
공격 꼴이 8MiB 에서 3.4~5.7초, 이 값에서 0.8~1.4초(밴드 TRS4 실측)."""

# zipfile·expat 이 망가진 바이트에서 낼 수 있는 것들. ValueError 는 숫자 칸이 너무 긴 태그(int 변환 상한)도 덮는다.
# LookupError = expat 이 모르는 encoding. NotImplementedError = zipfile 이 지역 머리의 flag 5·6 비트·높은 판 번호에서
# 내는 것. docx_reader._ZIP_ERRORS 와 달리 KeyError·IndexError·RuntimeError 는 잡지 않는다(밴드 TRS2,
# MARC-ISSUE-385): 이 셈에서 그것들은 갈고리·셈의 실수이고, unreadable 로 묻으면 정상 문서의 그리드가 조용히 사라진다.
# KeyError·IndexError 는 LookupError 아래라 page_count 가 먼저 다시 던진다(_OUR_MISTAKES).
_ERRORS: Final = (
    xml.parsers.expat.ExpatError,
    LookupError,
    ValueError,
    zipfile.BadZipFile,
    zlib.error,
    struct.error,
    EOFError,
    NotImplementedError,
    OverflowError,
    OSError,
)
_OUR_MISTAKES: Final = (KeyError, IndexError)

_W: Final = "http://schemas.openxmlformats.org/wordprocessingml/2006/main "
_DOCUMENT, _BODY, _P, _R, _HYPERLINK = (_W + name for name in ("document", "body", "p", "r", "hyperlink"))
_T, _BR, _TYPE = _W + "t", _W + "br", _W + "type"
# run 직속 자식 중 글이 되는 빈 요소(w:t·w:br 은 따로) — python-docx 1.2.0 의 __str__.
_RUN_MARKS: Final = {_W + "tab": "\t", _W + "ptab": "\t", _W + "cr": "\n", _W + "noBreakHyphen": "-"}
# 글을 모으는 run 의 자리: 몸 직속 문단의 run, 또는 그 문단의 하이퍼링크 안 run.
_RUN_PATHS: Final = ((_DOCUMENT, _BODY, _P, _R), (_DOCUMENT, _BODY, _P, _HYPERLINK, _R))
_LONG_BLANKS: Final = re.compile(r"[ \t]{5,}")


class _Stop(Exception):
    reason: Reason

    def __init__(self, reason: Reason) -> None:
        super().__init__(reason)
        self.reason = reason


def page_count(data: bytes) -> PageTags:
    """바이트 → [PAGE n] 최댓값 | None + 까닭. 예외 0(MemoryError·우리 셈의 실수 빼고)."""
    try:
        if data.startswith(b"PK\x03\x04"):
            return _docx(data)
        if data.startswith(b"%PDF-"):
            return PageTags(None, "pdf")
        return _text(data)
    except _Stop as stop:
        return PageTags(None, stop.reason)
    except _OUR_MISTAKES:
        raise
    except _ERRORS:
        return PageTags(None, "unreadable")


def _text(data: bytes) -> PageTags:
    if len(data) > MAX_TEXT_BYTES:  # 디코드 전에 거른다
        return PageTags(None, "too_large")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return PageTags(None, "not_utf8")
    return _result(_tags_of(text))


def _docx(data: bytes) -> PageTags:
    if len(data) > MAX_BYTES:
        return PageTags(None, "too_large")
    if (refused := central_directory_refusal(data)) is not None:
        return PageTags(None, refused)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ENTRIES:
            return PageTags(None, "too_many_entries")
        try:
            entry = archive.getinfo(DOCUMENT_XML)
        except KeyError:
            return PageTags(None, "no_document_xml")
        if entry.flag_bits & 0x1:
            return PageTags(None, "encrypted")
        if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            return PageTags(None, "unsupported_compression")
        if entry.file_size > MAX_XML_BYTES:
            return PageTags(None, "too_large")
        reader = _BodyText()
        parser = reader.parser()
        limit = entry.file_size + 1  # 선언 + 1 바이트까지만(docx_reader._read_entry 꼴)
        read = 0
        run = 0  # 마지막 `>` 뒤로 이어진 바이트(청크 경계를 넘어 센다)
        with archive.open(entry) as stream:
            while read < limit and (chunk := stream.read(min(CHUNK, limit - read))):
                read += len(chunk)
                first = chunk.find(b">")
                if run + (len(chunk) if first < 0 else first) > MAX_TAG_RUN:
                    raise _Stop("unsafe")
                run = run + len(chunk) if first < 0 else len(chunk) - chunk.rfind(b">") - 1
                parser.Parse(chunk, False)
        if read != entry.file_size:
            return PageTags(None, "unreadable")
        parser.Parse(b"", True)
    return _result(reader.found)


class _BodyText:
    """expat 갈고리: 몸 직속 문단의 글을 문단마다 줄로 나눠 [PAGE n] 을 모은다."""

    def __init__(self) -> None:
        self.stack: list[str] = []
        self.parts: list[str] | None = None  # 몸 직속 문단 안일 때만 목록
        self.in_text = False  # 모으는 자리의 w:t 바로 안(자식 요소가 나오면 그 뒤 글은 버림 — lxml .text 꼴)
        self.found: list[int] = []

    def parser(self) -> xml.parsers.expat.XMLParserType:
        parser = xml.parsers.expat.ParserCreate(namespace_separator=" ")
        parser.SetParamEntityParsing(xml.parsers.expat.XML_PARAM_ENTITY_PARSING_NEVER)
        parser.buffer_text = True
        parser.StartDoctypeDeclHandler = self.on_doctype
        parser.StartElementHandler = self.on_start
        parser.EndElementHandler = self.on_end
        parser.CharacterDataHandler = self.on_chars
        return parser

    def on_doctype(self, name: str, system_id: str | None, public_id: str | None, has_internal_subset: bool) -> None:
        raise _Stop("unsafe")

    def on_start(self, name: str, attributes: dict[str, str]) -> None:
        self.in_text = False
        stack = self.stack
        if len(stack) >= MAX_DEPTH:
            raise _Stop("unsafe")
        if len(stack) == 2 and name == _P and stack[1] == _BODY and stack[0] == _DOCUMENT:
            self.parts = []
        elif self.parts is not None and len(stack) in (4, 5) and tuple(stack) in _RUN_PATHS:  # 깊이로 먼저 — 선형
            if name == _T:
                self.in_text = True
            elif name == _BR:
                kind = attributes.get(_TYPE)
                if kind is None or kind == "textWrapping":
                    self.add("\n")
            elif name in _RUN_MARKS:
                self.add(_RUN_MARKS[name])
        stack.append(name)

    def on_end(self, name: str) -> None:
        self.in_text = False
        self.stack.pop()
        if len(self.stack) == 2 and self.parts is not None:
            self.found.extend(_tags_of("".join(self.parts)))
            self.parts = None

    def on_chars(self, data: str) -> None:
        if self.in_text:
            self.add(data)

    def add(self, text: str) -> None:
        if self.parts is None:
            return
        self.parts.append(text)


def _tags_of(text: str) -> list[int]:
    """글의 줄마다 [PAGE n] 의 n(엔진 앞몫 — 줄바꿈 통일·정규화 — 를 줄 단위로)."""
    found: list[int] = []
    for line in file_roundtrip(text).split("\n"):
        if "page" not in line.lower():
            continue
        match = PAGE_TAG_LINE_RE.match(normalize_structured_tags(_LONG_BLANKS.sub("    ", line)).strip())
        if match is not None:
            found.append(int(match.group(1)))
    return found


def _result(found: list[int]) -> PageTags:
    pages = [n for n in found if n >= 1]
    if not pages:
        return PageTags(None, "no_pages")
    largest = max(pages)
    return PageTags(largest, None) if largest <= MAX_PAGES else PageTags(None, "too_many_pages")
