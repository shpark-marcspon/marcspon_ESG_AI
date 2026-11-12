# pyright: reportUnknownMemberType=false
"""용어집 엑셀(「한국어 | 영문」 두 열) 바이트 → 짝 목록, 그리고 빈 양식(밴드 TR3a). **남이 준 xlsx 를 여는 제품 경로는
이 파일이 처음이다**(inventory/tools/xlsx_reader.py 는 올리기 경로가 없다). 상태가 없다: 디스크·저장소·DB 에 쓰지 않고,
메모리의 바이트 하나를 아래 방어 뒤에 openpyxl 에 넘긴다.

    read_glossary(data) -> GlossaryRead | GlossaryRejected    어떤 바이트도 예외 대신 갈래(MemoryError 만 밖으로 —
                                                               OOM 신호를 「파일 못 읽음」으로 바꾸지 않는다)
    template() -> bytes                                        빈 양식(시트 「용어집」, 머리 둘). 매번 같은 바이트

읽는 차례(어기는 첫 것 하나로 거절):
1. 바이트 ≤ MAX_BYTES → zip 열기 → 항목 ≤ MAX_ENTRIES · 항목 선언 ≤ MAX_ENTRY_BYTES · 선언 합 ≤ MAX_DECLARED_BYTES ·
   항목마다 선언 + 1 바이트까지만 풀어 길이 대조(docx_reader 와 같은 꼴 — 선언을 속인 zip).
2. XML 훑기: **zip 의 모든 항목**을 보고 바이트가 XML 로 보이면(`_looks_like_xml` — 첫 바이트가 XML 1.0 부록 F
   (인코딩 자동 감지, https://www.w3.org/TR/xml/#sec-guessing — 10-23 확인) 표 `_XML_SIGNATURES` 의 하나이거나,
   UTF-8·UTF-16LE/BE·UCS-4LE/BE 의 앞 공백 뒤 `<`) 이름·꼴·관계·TargetMode 와 상관없이 expat 으로 끝까지 훑는다
   (트리 0): DOCTYPE·엔티티 선언·외부 엔티티면, 요소 중첩이 MAX_XML_DEPTH 를 넘거나 요소·속성·이름공간 선언 수 합이
   MAX_XML_ELEMENTS 를 넘거나 이벤트 사이가 MAX_XML_SPAN 바이트를 넘으면, expat 이 못 읽으면(UCS-4·EBCDIC 포함)
   거절. 그 밖(그림·printerSettings*.bin·thumbnail.jpeg)은 훑지 않는다 — lxml·expat 도 첫 바이트에서 실패한다.
   ★ 이름·꼴·rels 로 대상을 고르던 판(docx_reader 선례)은 우회가 셋 나왔다(시트를 `.dat` 로 옮김 · 관계 Type 을
   image 로 속임 · TargetMode External 의 Target — 검증 B1·B2). openpyxl 3.1.5 는 worksheet·sharedStrings 를 stdlib
   `xml.etree.ElementTree.iterparse`(expat)로, 그 밖은 lxml `fromstring(parser=XMLParser(resolve_entities=False))` 로
   연다(`openpyxl/xml/functions.py`) — 훑기를 지난 바이트만 간다. ★ 가지 리뷰(10-23): UCS-4 는 lxml 만 읽고, BOM 없는
   UTF-16 의 앞 공백 뒤 `<` 는 expat 만 읽는다(러너 실측) — 둘 다 판정에 든다. ★ docx_reader 와 달리 뿌리에서 멈추지
   않는다: 12KB 짜리 xlsx 의 100만 겹 중첩 워크시트가 openpyxl 에서 2.4초·RSS +592MB 였다(★B 실측 — 보고). 끝까지
   훑는 값은 항목 선언 합 상한(16MiB)이 묶는다.
3. `openpyxl.load_workbook(BytesIO, read_only=True, data_only=True)` 의 `worksheets[0]`(차례상 첫째 — 숨김 여부 무시)
   → `iter_rows(min_row=1, max_col=2, values_only=True)` → 훑은 행(빈 행 포함 — read_only 는 빈 행 번호도 내준다)
   ≤ MAX_SCANNED_ROWS → 끝에 `close()`(finally).
4. 1행 = 「한국어」「영문」(앞뒤 공백 무시, C 열부터는 읽지 않는다) → 2행부터: 둘 다 빈 행은 건너뛴다 · 한 칸만 빔 ·
   글자가 아님(수·날짜·bool — 서식이 숫자인 칸) · 길이 넘음 · 같은 한국어 두 번 · 데이터 행 > MAX_PAIRS → 거절.
   글은 `strip()` 만 한다. 값 없는 수식 칸(data_only — 계산된 값이 저장되지 않은 파일)은 빈 칸이다.

거절 글은 해요체 한 문장 + 행 번호다. 칸의 값은 싣지 않는다(로그·응답에 고객 용어가 새지 않게).

★ 무효 조건(잰 것과 안 잰 것):
- 잰 것은 openpyxl 3.1.5 가 지은 파일과 손으로 지은 공격 파일뿐이다. Excel·한글·LibreOffice·구글 시트가 저장한 실제
  용어집은 재지 않았다(표본 0). 상한의 값은 전부 어림이다(근거는 상수 곁).
- `#N/A` 같은 오류 칸은 openpyxl 이 글자로 내준다 — 그 글이 그대로 짝이 된다(가를 길이 없다).
- 공유 수식·서식은 보지 않는다. 숨은 시트·숨은 행도 그대로 읽는다(첫 시트만).
"""

import io
import re
import struct
import xml.parsers.expat
import zipfile
import zlib
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from typing import Final, Literal

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils.exceptions import InvalidFileException, ReadOnlyWorkbookException

# ── 상한(전부 어림) ──
MAX_BYTES: Final = 1024 * 1024
"""받는 바이트. 500짝(국 30·영 100자)도 sharedStrings 로 수십 KB 다(★B 실측은 보고) — 그 위로 넉넉히."""
MAX_ENTRIES: Final = 100
"""zip 항목 수. openpyxl 이 지은 빈 양식은 9개다."""
MAX_ENTRY_BYTES: Final = 8 * 1024 * 1024
"""항목 하나의 선언된(풀린) 크기(inventory xlsx_reader 와 같은 값)."""
MAX_DECLARED_BYTES: Final = 16 * 1024 * 1024
"""선언된 크기 합(inventory xlsx_reader 의 MAX_OPENED_BYTES 와 같은 값)."""
MAX_SCANNED_ROWS: Final = 10_000
"""훑는 행(머리·빈 행 포함). read_only 는 빈 행 번호마다 빈 행을 내주므로 1,048,576행에 칸 하나인 파일도 여기서
멈춘다."""
MAX_PAIRS: Final = 500
"""파일당 데이터 행(옵션 options@1 의 glossary.base·final 상한과 같다 — contracts/options_shapes.py)."""
MAX_KO_CHARS: Final = 30
MAX_EN_CHARS: Final = 100
"""칸 글자 수(추정 — 표본 0). 500 + 500짝이 이 최댓값이어도 옵션 바이트 상한(256KiB) 안이다(발주서 처분 표)."""

MAX_XML_DEPTH: Final = 64
"""XML 요소 중첩 상한. openpyxl 이 짓는 워크시트는 worksheet > sheetData > row > c > is > r > t 의 7겹 안팎이다(그림
DrawingML 도 수십 겹 안 — 추정)."""

MAX_XML_ELEMENTS: Final = 100_000
"""훑기 대상 XML 의 요소 수 합 — 속성 하나·이름공간 선언 하나도 1 로 같은 예산에 더한다(가지 리뷰 처분, 추정).
지어낸 500짝 파일은 수천 개다(★B 실측 — 보고). openpyxl 의 일은 요소 수에 비례한다: 200만 개(8MiB 의 빈 요소)가
4.1초·RSS +315MB, 30만 칸 한 행이 2.5초·+467MB 였다."""

MAX_XML_SPAN: Final = 1024 * 1024
"""이벤트(요소 시작·끝·글 조각) 사이의 바이트 상한. expat 은 시작 표지 하나를 다 읽은 뒤에야 속성 전부를 사전으로 지어
handler 에 넘긴다 — 8MiB 항목 한 요소의 속성 80만 개는 그 사전만으로 0.96초·RSS +300MB 였다(러너 실측). 먹이는
조각마다 이 간격을 재서 사전을 짓기 전에 거절한다. 글은 expat 이 조각으로 알려 주므로 긴 칸 글은 걸리지 않는다."""

HEADER: Final = ("한국어", "영문")
SHEET_TITLE: Final = "용어집"
TEMPLATE_DATE: Final = (1980, 1, 1, 0, 0, 0)
"""양식 zip 항목의 시각(zip 이 적을 수 있는 가장 이른 시각 — 매번 같은 바이트)."""

RejectionKind = Literal[
    "too_large",
    "not_xlsx",
    "unsafe_xlsx",
    "bad_header",
    "empty_cell",
    "not_text",
    "too_long",
    "duplicate_ko",
    "too_many_rows",
    "no_rows",
]


@dataclass(frozen=True, slots=True)
class GlossaryRead:
    pairs: tuple[tuple[str, str], ...]
    """(한국어, 영문) — 파일의 행 차례."""


@dataclass(frozen=True, slots=True)
class GlossaryRejected:
    kind: RejectionKind
    row: int | None
    """엑셀의 행 번호(1부터). 파일 전체면 None."""
    message: str


class _RootSeen(Exception):
    """뿌리 요소 확인을 멈추는 신호."""


class _Rejected(Exception):
    """제어 흐름용. 밖으로 새지 않는다: read_glossary 가 갈래로 바꾼다."""

    def __init__(self, kind: RejectionKind, message: str, row: int | None = None) -> None:
        super().__init__(kind)
        self.rejection = GlossaryRejected(kind, row, message)


# zipfile 이 망가진 바이트에서 낼 수 있는 것들(docx_reader._ZIP_ERRORS 판별 복사). 이름으로 적는다.
_ZIP_ERRORS: Final = (
    zipfile.BadZipFile,
    zlib.error,
    struct.error,
    EOFError,
    RuntimeError,  # 암호 걸린 항목. NotImplementedError(모르는 압축 방식)도 이 아래다
    KeyError,
    ValueError,
    IndexError,
    OverflowError,
    OSError,
)
# openpyxl·lxml 이 방어를 지난 바이트에서 낼 수 있는 것들. SyntaxError = lxml 의 XMLSyntaxError(lxml 을 import 하지 않고
# 잡는다). RecursionError 는 RuntimeError 아래지만 까닭을 보이려고 따로 적는다.
_WORKBOOK_ERRORS: Final = (
    *_ZIP_ERRORS,
    RecursionError,
    SyntaxError,
    InvalidFileException,
    ReadOnlyWorkbookException,
    TypeError,
    AttributeError,
    AssertionError,
)

_CONTENT_TYPES: Final = "[Content_Types].xml"
_CT_NS: Final = "http://schemas.openxmlformats.org/package/2006/content-types"
_CHUNK: Final = 64 * 1024
_COLUMNS: Final = ("한국어", "영문")
_LIMITS: Final = (MAX_KO_CHARS, MAX_EN_CHARS)

_NOT_XLSX: Final = "엑셀(.xlsx) 파일이 아니에요 — 용어집 양식에 채워 올려 주세요."
_UNSAFE: Final = "이 엑셀 파일은 열 수 없어요 — 양식을 새로 받아 채워 올려 주세요."
_BAD_HEADER: Final = "1행의 머리가 「한국어」「영문」이 아니에요 — 양식을 그대로 써 주세요."


def read_glossary(data: bytes) -> GlossaryRead | GlossaryRejected:
    try:
        return _read(data)
    except _Rejected as rejected:
        return rejected.rejection


def _read(data: bytes) -> GlossaryRead:
    if len(data) == 0:
        raise _Rejected("not_xlsx", _NOT_XLSX)
    if len(data) > MAX_BYTES:
        raise _Rejected("too_large", f"파일이 너무 커요 — {MAX_BYTES // (1024 * 1024)}MB 이하로 올려 주세요.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except _ZIP_ERRORS:
        raise _Rejected("not_xlsx", _NOT_XLSX) from None
    with archive:
        sizes = _declared_sizes(archive)
        _check_entries(archive, sizes)
    return _pairs(data)


# ── zip ──────────────────────────────────────────────────────────────────


def _declared_sizes(archive: zipfile.ZipFile) -> dict[str, int]:
    """항목 이름 → 선언된(풀린) 크기. 아무것도 풀지 않는다."""
    try:
        entries = archive.infolist()
    except _ZIP_ERRORS:
        raise _Rejected("not_xlsx", _NOT_XLSX) from None
    if len(entries) > MAX_ENTRIES:
        raise _Rejected("unsafe_xlsx", _UNSAFE)
    sizes: dict[str, int] = {}
    for entry in entries:
        if entry.filename in sizes:  # 같은 이름이 둘이면 zipfile 은 조용히 뒤의 것을 준다
            raise _Rejected("unsafe_xlsx", _UNSAFE)
        if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) or entry.flag_bits & 0x1:
            raise _Rejected("unsafe_xlsx", _UNSAFE)
        if entry.file_size > MAX_ENTRY_BYTES:
            raise _Rejected("unsafe_xlsx", _UNSAFE)
        sizes[entry.filename] = entry.file_size
    if sum(sizes.values()) > MAX_DECLARED_BYTES:
        raise _Rejected("unsafe_xlsx", _UNSAFE)
    return sizes


def _read_entry(archive: zipfile.ZipFile, sizes: Mapping[str, int], name: str) -> bytes:
    try:
        # `archive.read(name)` 을 쓰지 않는다: 선언된 크기 + 1 바이트까지만 풀고, 길이가 다르면 거절한다.
        with archive.open(name) as stream:
            data = stream.read(sizes[name] + 1)
    except _ZIP_ERRORS:
        raise _Rejected("unsafe_xlsx", _UNSAFE) from None
    if len(data) != sizes[name]:
        raise _Rejected("unsafe_xlsx", _UNSAFE)
    return data


def _check_entries(archive: zipfile.ZipFile, sizes: Mapping[str, int]) -> None:
    """모든 항목을 하나씩 풀어 보고(선언 + 1), 바이트가 XML 로 보이면(_looks_like_xml) 이름·꼴·관계와 상관없이 끝까지
    훑는다(DOCTYPE·엔티티·중첩·요소 수 합). `[Content_Types].xml` 은 꼴 지도의 뿌리도 본다(xlsx 인가)."""
    if _CONTENT_TYPES not in sizes:
        raise _Rejected("not_xlsx", _NOT_XLSX)
    _content_types_root(_read_entry(archive, sizes, _CONTENT_TYPES))
    elements = [0]  # 요소 수는 파일 전체의 합이다
    for name in sizes:
        entry = _read_entry(archive, sizes, name)
        if _looks_like_xml(entry):
            _scan(entry, elements)


_XML_SIGNATURES: Final = (
    b"\x00\x00\x00<",  # UCS-4 BE(1234) BOM 없음
    b"<\x00\x00\x00",  # UCS-4 LE(4321) BOM 없음
    b"\x00\x00<\x00",  # UCS-4 2143
    b"\x00<\x00\x00",  # UCS-4 3412
    b"\x00\x00\xfe\xff",  # UCS-4 BE BOM
    b"\xff\xfe\x00\x00",  # UCS-4 LE BOM
    b"\x00\x00\xff\xfe",  # UCS-4 2143 BOM
    b"\xfe\xff\x00\x00",  # UCS-4 3412 BOM
    b"\xfe\xff",  # UTF-16 BE BOM
    b"\xff\xfe",  # UTF-16 LE BOM
    b"\xef\xbb\xbf",  # UTF-8 BOM
    b"\x00<\x00?",  # UTF-16 BE BOM 없음
    b"<\x00?\x00",  # UTF-16 LE BOM 없음
    b"<?xm",  # UTF-8·ASCII 꼴
    b"\x4c\x6f\xa7\x94",  # EBCDIC
)
"""XML 1.0 부록 F(https://www.w3.org/TR/xml/#sec-guessing — 10-23 확인)의 머리 바이트 표. 이것으로 시작하면 XML 로
본다."""

_SPACE_THEN_LT: Final = tuple(
    re.compile(
        b"(?:"
        + b"|".join(re.escape(c.encode(codec)) for c in " \t\r\n")
        + b")*"
        + re.escape(b"<".decode().encode(codec))
    )
    for codec in ("utf-8", "utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be")
)
"""앞 공백(SP·TAB·CR·LF) 뒤 `<` — 그 인코딩의 단위로 뗀다. 부록 F 표는 첫 네 바이트만 보므로 BOM 없는 UTF-16 의 앞 공백
(`0A 00 3C 00`)을 놓친다 — expat 은 그것을 읽는다(러너 실측)."""


def _looks_like_xml(data: bytes) -> bool:
    """바이트가 XML 로 보이는가(감독 63 처분 — 고르는 기준은 이름이 아니라 내용): 부록 F 표의 머리로 시작하거나, 다섯
    인코딩 가운데 하나로 앞 공백 뒤 `<`. 그 밖(PNG·JPEG·printerSettings 의 바이너리)은 lxml·expat 도 첫 바이트에서
    실패한다 — 훑지 않는다. XML 로 보이되 expat 이 못 읽는 꼴(UCS-4·EBCDIC)은 _feed 가 거절한다."""
    return data.startswith(_XML_SIGNATURES) or any(pattern.match(data) for pattern in _SPACE_THEN_LT)


# ── XML(expat — 트리를 짓지 않는다) ──────────────────────────────────────


def _parser() -> xml.parsers.expat.XMLParserType:
    """DOCTYPE·엔티티 선언·외부 엔티티 참조 어느 하나라도 만나면 거절하는 expat(두 겹 — 엔티티 선언은 DOCTYPE 안에만
    올 수 있지만 갈고리를 따로 건다). 매개변수 엔티티는 풀지 않는다."""
    parser = xml.parsers.expat.ParserCreate(namespace_separator=" ")
    parser.SetParamEntityParsing(xml.parsers.expat.XML_PARAM_ENTITY_PARSING_NEVER)

    def on_doctype(name: str, system_id: str | None, public_id: str | None, has_internal_subset: bool) -> None:
        raise _Rejected("unsafe_xlsx", _UNSAFE)

    def on_entity(*_: object) -> None:
        raise _Rejected("unsafe_xlsx", _UNSAFE)

    def on_external(*_: object) -> int:
        raise _Rejected("unsafe_xlsx", _UNSAFE)

    parser.StartDoctypeDeclHandler = on_doctype
    parser.EntityDeclHandler = on_entity
    parser.ExternalEntityRefHandler = on_external
    return parser


def _feed(parser: xml.parsers.expat.XMLParserType, data: bytes, last: list[int]) -> None:
    """조각으로 먹인다. last[0] = 마지막 이벤트의 바이트 자리(handler 들이 parser.CurrentByteIndex 로 적는다) — 먹인
    끝과 그 사이가 MAX_XML_SPAN 을 넘으면 거절한다(긴 표지 하나 — 속성 사전을 짓기 전)."""
    try:
        for start in range(0, len(data), _CHUNK):
            parser.Parse(data[start : start + _CHUNK], False)
            if min(len(data), start + _CHUNK) - last[0] > MAX_XML_SPAN:
                raise _Rejected("unsafe_xlsx", _UNSAFE)
        parser.Parse(b"", True)
    except (xml.parsers.expat.ExpatError, LookupError):  # 깨진 XML · expat·codecs 가 모르는 encoding
        raise _Rejected("unsafe_xlsx", _UNSAFE) from None


def _scan(data: bytes, elements: list[int]) -> None:
    """끝까지 훑는다: DOCTYPE 이거나 중첩이 MAX_XML_DEPTH 를 넘거나 요소·속성·이름공간 선언·주석·처리 지시 수 합
    (elements — 항목들에 걸쳐 센다)이 MAX_XML_ELEMENTS 를 넘거나 이벤트 사이가 MAX_XML_SPAN 을 넘거나 뿌리 요소가 없으면
    거절한다. 주석·처리 지시는 lxml 이 노드로 짓는다(가지 리뷰 10-23 — 28KB 업로드가 처리 지시 320만 개·RSS +220MB).
    CDATA·공백은 노드를 짓지 않고(러너 실측), 그 밖의 선언은 DOCTYPE 안에만 온다."""
    parser = _parser()
    depth = [0]
    seen = [False]
    last = [0]

    def count(n: int) -> None:
        elements[0] += n
        if elements[0] > MAX_XML_ELEMENTS:
            raise _Rejected("unsafe_xlsx", _UNSAFE)

    def on_start(name: str, attributes: dict[str, str]) -> None:
        last[0] = parser.CurrentByteIndex
        depth[0] += 1
        seen[0] = True
        if depth[0] > MAX_XML_DEPTH:
            raise _Rejected("unsafe_xlsx", _UNSAFE)
        count(1 + len(attributes))

    def on_namespace(prefix: str | None, uri: str) -> None:
        count(1)

    def on_end(name: str) -> None:
        last[0] = parser.CurrentByteIndex
        depth[0] -= 1

    def on_text(text: str) -> None:
        last[0] = parser.CurrentByteIndex

    def on_node(*_: object) -> None:  # 주석·처리 지시
        last[0] = parser.CurrentByteIndex
        count(1)

    parser.StartElementHandler = on_start
    parser.StartNamespaceDeclHandler = on_namespace
    parser.EndElementHandler = on_end
    parser.CharacterDataHandler = on_text
    parser.CommentHandler = on_node
    parser.ProcessingInstructionHandler = on_node
    _feed(parser, data, last)
    if not seen[0]:
        raise _Rejected("unsafe_xlsx", _UNSAFE)


def _content_types_root(data: bytes) -> None:
    """`[Content_Types].xml` 의 뿌리가 `Types`(OPC 꼴 지도)인가 — 아니면 xlsx 가 아니다. 뿌리 요소에서 멈춘다(DOCTYPE
    은 그 앞에만 올 수 있어 먼저 거절된다. 끝까지 훑기는 _check_entries 의 모든 항목 몫)."""
    parser = _parser()

    def on_start(name: str, attributes: dict[str, str]) -> None:
        if name != f"{_CT_NS} Types":
            raise _Rejected("not_xlsx", _NOT_XLSX)
        raise _RootSeen

    parser.StartElementHandler = on_start
    try:
        _feed(parser, data, [0])  # 이벤트는 뿌리 하나뿐 — 뿌리 앞이 MAX_XML_SPAN 을 넘으면 거절
    except _RootSeen:
        return
    raise _Rejected("not_xlsx", _NOT_XLSX)


# ── openpyxl ─────────────────────────────────────────────────────────────


def _rows(data: bytes) -> Generator[tuple[object, object]]:
    """첫 시트의 A·B 칸(값만). 훑은 행이 상한을 넘으면 거절. 통합 문서는 끝나든 거절하든 닫는다."""
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except _WORKBOOK_ERRORS:
        raise _Rejected("not_xlsx", _NOT_XLSX) from None
    try:
        try:
            sheets = workbook.worksheets
            if not sheets:
                raise _Rejected("not_xlsx", _NOT_XLSX)
            rows = sheets[0].iter_rows(min_row=1, max_col=2, values_only=True)
            for scanned, row in enumerate(rows, start=1):
                if scanned > MAX_SCANNED_ROWS:
                    raise _Rejected(
                        "too_many_rows", f"행이 너무 많아요 — 빈 행을 지우고 {MAX_SCANNED_ROWS:,}행 안으로 올려 주세요."
                    )
                cells = (*row, None, None)
                yield cells[0], cells[1]
        except _WORKBOOK_ERRORS:
            raise _Rejected("not_xlsx", _NOT_XLSX) from None
    finally:
        workbook.close()


def _text(value: object, row: int, column: int) -> str | None:
    """칸 하나 → strip 한 글(빈 칸이면 None). 글자가 아니거나 길면 거절."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise _Rejected(
            "not_text", f"{row}행의 {_COLUMNS[column]} 칸이 글자가 아니에요 — 셀 서식을 텍스트로 바꿔 주세요.", row
        )
    text = value.strip()
    if not text:
        return None
    if len(text) > _LIMITS[column]:
        raise _Rejected(
            "too_long", f"{row}행의 {_COLUMNS[column]} 칸이 너무 길어요 — {_LIMITS[column]}자까지예요.", row
        )
    return text


def _pairs(data: bytes) -> GlossaryRead:
    pairs: list[tuple[str, str]] = []
    first_row: dict[str, int] = {}
    header_seen = False
    rows = _rows(data)
    try:
        for number, (ko_cell, en_cell) in enumerate(rows, start=1):
            if number == 1:
                head = tuple(c.strip() if isinstance(c, str) else c for c in (ko_cell, en_cell))
                if head != HEADER:
                    raise _Rejected("bad_header", _BAD_HEADER, 1)
                header_seen = True
                continue
            ko, en = _text(ko_cell, number, 0), _text(en_cell, number, 1)
            if ko is None and en is None:
                continue
            if ko is None or en is None:
                empty = _COLUMNS[0] if ko is None else _COLUMNS[1]
                raise _Rejected("empty_cell", f"{number}행의 {empty} 칸이 비어 있어요.", number)
            if ko in first_row:
                raise _Rejected(
                    "duplicate_ko", f"{number}행의 한국어가 {first_row[ko]}행과 같아요 — 한 번만 적어 주세요.", number
                )
            if len(pairs) == MAX_PAIRS:
                raise _Rejected("too_many_rows", f"용어가 너무 많아요 — 파일 하나에 {MAX_PAIRS}개까지예요.", number)
            first_row[ko] = number
            pairs.append((ko, en))
    finally:
        rows.close()
    if not header_seen:  # 빈 시트
        raise _Rejected("bad_header", _BAD_HEADER, 1)
    if not pairs:
        raise _Rejected("no_rows", "용어가 없어요 — 2행부터 「한국어」「영문」 짝을 적어 주세요.")
    return GlossaryRead(tuple(pairs))


# ── 양식 ─────────────────────────────────────────────────────────────────


def template() -> bytes:
    """빈 양식: 시트 「용어집」, 1행 머리 「한국어」「영문」(굵게), 두 열은 텍스트 서식, 데이터 행 0.

    매번 같은 바이트다: 문서 속성의 시각을 고정하고, openpyxl 이 지은 zip 을 항목 차례 그대로 시각 TEMPLATE_DATE 로
    다시 싼다(openpyxl 은 zip 항목에 지은 시각을 적는다)."""
    workbook = Workbook()
    sheet = workbook.worksheets[0]
    sheet.title = SHEET_TITLE
    sheet.append(list(HEADER))
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for column, width in (("A", 30), ("B", 60)):
        sheet.column_dimensions[column].width = width
        sheet.column_dimensions[column].number_format = "@"
    workbook.properties.creator = "esgapi"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return _restamp(buffer.getvalue())


def _restamp(data: bytes) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for entry in source.infolist():
            content = source.read(entry.filename)
            if entry.filename == "docProps/core.xml":
                content = _fixed_core(content)
            info = zipfile.ZipInfo(entry.filename, date_time=TEMPLATE_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, content)
    return out.getvalue()


def _fixed_core(content: bytes) -> bytes:
    """문서 속성의 created·modified 를 TEMPLATE_DATE 로(openpyxl 은 저장할 때 지금 시각을 적는다)."""
    stamp = b"1980-01-01T00:00:00Z"
    return re.sub(
        rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)",
        lambda m: m.group(1) + stamp + m.group(2),
        content,
    )
