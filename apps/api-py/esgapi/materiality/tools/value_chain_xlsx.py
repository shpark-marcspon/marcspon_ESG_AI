# pyright: reportUnknownMemberType=false
"""가치사슬 표 엑셀(마크스폰 중대성평가 템플릿의 「0. Value Chain 파악」 꼴 — 열 다섯) 바이트 → 행 목록(밴드 IRW2,
MARC-ENT-464·421). 상태가 없다: 디스크·저장소·DB 에 쓰지 않고, 메모리의 바이트 하나를 아래 방어 뒤에 openpyxl 에 넘긴다.

    read_value_chain(data) -> ValueChainRead | ValueChainRejected   어떤 바이트도 예외 대신 갈래(MemoryError 만 밖으로)

★ 출처: zip·XML 방어(1·2)는 translation/tools/glossary_xlsx.py(밴드 TR3a)를 **옮겨 적은 것**이다 — `_read`·
`_declared_sizes`·`_read_entry`·`_check_entries`·`_XML_SIGNATURES`·`_SPACE_THEN_LT`·`_looks_like_xml`·`_parser`·
`_feed`·`_scan`·`_content_types_root`·`_ZIP_ERRORS`·`_WORKBOOK_ERRORS` 와 상한 상수(곁 글 포함)는 글자째, 바꾼 것은
거절 글·kind 이름·결과 이름(GlossaryRead → ValueChainRead · _pairs → _table)뿐이다. import 하지 않는다(모듈끼리
의존 0 — 발주서 Q1). **한쪽을 고치면 다른 쪽도** — tests/tools/test_value_chain_xlsx_twin.py 가 두 소스의 AST 를 견준다.

읽는 차례(어기는 첫 것 하나로 거절):
1·2. glossary_xlsx.py 의 머리말 1·2 그대로(바이트 상한 → zip 항목 상한·선언 대조 → XML 로 보이는 모든 항목을 expat 으로
   끝까지 훑기 — DOCTYPE·엔티티·깊이·요소 수 합·표지 간격).
3. `openpyxl.load_workbook(BytesIO, read_only=True, data_only=True)` → 시트 고르기: 이름에 「value chain」(대소문자·
   공백 무시)이 든 **첫 보이는**(`sheet_state == "visible"`) 시트, 없으면 첫 보이는 시트(발주서 Q4 ①).
4. 병합: read_only 워크시트는 병합 범위를 주지 않는다 → 고른 시트의 XML 항목을 `xl/workbook.xml`(`<sheet name r:id>`)과
   `xl/_rels/workbook.xml.rels`(`<Relationship Id Target>` — openpyxl `get_dependents` 와 같은 풀이)로 찾아, 2 에서 이미
   훑은 바이트를 `_parser()` 의 expat 으로 다시 읽어 `<mergeCell ref>` 만 모은다(트리 0·openpyxl 0·요소 수 예산 그대로).
   mergeCell > MAX_MERGES 거나 병합끼리 겹치면(Excel 은 겹친 병합을 짓지 않는다) 거절. 병합 범위의 빈 칸 = 왼쪽 위 값.
   머리 행과 그 위에서 시작한 병합은 데이터 행을 채우지 않는다(머리 행의 채움은 그대로 — IRW3, MARC-ISSUE-410 ④).
5. `iter_rows(min_row=1, max_col=MAX_HEADER_COL, values_only=True)` → 훑은 행(빈 행 포함) ≤ MAX_SCANNED_ROWS. 머리 = 위
   MAX_HEADER_ROWS 행 안에서 열 이름 다섯(HEADER)이 이웃한 다섯 칸에 차례대로 있는 첫 행(앞뒤 공백 무시, 시작 열 아무
   데나) — 그 다섯 열만 읽는다(Q4 ②). 끝에 `close()`(finally).
6. 머리 다음 행마다: 밸류체인·이해관계자·관련 비즈니스 활동이 다 빈 행은 건너뛴다(Q4 ④ — 데이터 행 번호를 세지
   않는다) → 데이터 행 번호 +1 → 글자가 아닌 칸(수·날짜·bool) · 글자 수 넘음(열마다 MAX_CHARS) · 데이터 행 >
   MAX_DATA_ROWS → 거절. 사업 부문 칸이 빈 행은 바로 위 데이터 행의 사업 부문을, 사업 내용도 비었으면 그 사업 내용을
   물려받는다(첫 데이터 행이면 `""`). 사업 부문이 있으면 사업 내용 빔은 `""` 그대로(Q4 ③ — 감독 10-28).
   글은 `strip()` 만. 「ex.)」 예시 행은 거르지 않는다(Q4 ⑤). 밸류체인 값은 받은 글 그대로다(값 검사·바꿈은 웹
   model/valueChain.ts — Q3).

`row` 는 머리 다음부터 센 **데이터 행 번호**(1부터, 건너뛴 행은 안 셈 — 화면 표의 「{n}행」), `column` 은 0..4(HEADER
차례). 파일 전체의 까닭이면 둘 다 None. 거절 글은 해요체 한 문장이고 칸의 값은 싣지 않는다(로그·응답에 고객 글이 새지
않게).

★ 무효 조건(잰 것과 안 잰 것):
- 잰 것은 openpyxl 3.1.5 가 지은 파일(템플릿 꼴을 지어낸 내용으로 재현)과 손으로 지은 공격 파일뿐이다. 마크스폰 템플릿
  원본·Excel·한글·구글 시트가 저장한 실제 표는 재지 않았다(표본 0 — 템플릿 꼴은 감독 실측 10-27 의 글 설명). 상한의
  값은 전부 어림이다.
- 워크북 파트는 `xl/workbook.xml` 자리로만 찾는다(OPC 꼴 지도로 찾지 않는다 — Excel·openpyxl 이 짓는 자리). 다른
  자리면 not_xlsx.
- `#N/A` 같은 오류 칸은 openpyxl 이 글자로 내준다 — 그 글이 그대로 칸 값이 된다. 숨은 행·열은 그대로 읽는다.
"""

import io
import posixpath
import re
import struct
import xml.parsers.expat
import zipfile
import zlib
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from typing import Final, Literal

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException, ReadOnlyWorkbookException

# ── 상한 — glossary_xlsx.py 에서 옮김(값·곁 글 글자째. 곁 글의 「용어집·짝」은 원본의 근거 그대로 둔다) ──
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

# ── 이 읽개의 상한(전부 어림 — 발주서 Q4·Q5) ──
MAX_DATA_ROWS: Final = 100
"""데이터 행(건너뛴 행 빼고). 코랩 예시는 37행이다(발주서 Q5 — 확인). 웹 붙여 넣기도 같은 값(model/valueChain.ts)."""
MAX_CHARS: Final = (50, 200, 20, 50, 200)
"""칸 글자 수(HEADER 차례 — 사업 부문·사업 내용·밸류체인·이해관계자·관련 비즈니스 활동). 코랩 예시의 칸 최장 94자(발주서
Q5 — 확인)에서 어림. 웹 붙여 넣기도 같은 값(section4 가 두 곳을 grep 으로 견준다)."""
MAX_HEADER_ROWS: Final = 20
"""머리를 찾는 위 행 수(템플릿은 5행 — 2행 제목·4행 병합 안내 뒤)."""
MAX_HEADER_COL: Final = 26
"""읽는 열(A~Z). 템플릿 머리는 B~F 다(어림 — 머리가 Z 열 너머면 bad_header)."""
MAX_MERGES: Final = 1_000
"""고른 시트의 mergeCell 수(템플릿은 수십 개 — 어림). 넘으면 unsafe_xlsx."""

HEADER: Final = ("사업 부문", "사업 내용", "밸류체인", "이해관계자", "관련 비즈니스 활동")
SHEET_HINT: Final = "valuechain"
"""시트 이름에서 공백을 다 빼고 소문자로 바꾼 글에 이것이 들면 가치사슬 시트(템플릿 「0. Value Chain 파악」)."""

RejectionKind = Literal[
    "too_large",
    "not_xlsx",
    "unsafe_xlsx",
    "bad_header",
    "not_text",
    "too_long",
    "too_many_rows",
    "too_many_scanned_rows",
    "no_rows",
]

Row = tuple[str, str, str, str, str]


@dataclass(frozen=True, slots=True)
class ValueChainRead:
    rows: tuple[Row, ...]
    """(사업 부문, 사업 내용, 밸류체인, 이해관계자, 관련 비즈니스 활동) — 파일의 행 차례, 빈 칸은 `""`."""


@dataclass(frozen=True, slots=True)
class ValueChainRejected:
    kind: RejectionKind
    row: int | None
    """데이터 행 번호(머리 다음부터 1, 건너뛴 행은 세지 않음). 파일 전체면 None."""
    column: int | None
    """0..4(HEADER 차례). 파일 전체·행 전체면 None."""
    message: str


class _RootSeen(Exception):
    """뿌리 요소 확인을 멈추는 신호."""


class _Rejected(Exception):
    """제어 흐름용. 밖으로 새지 않는다: read_value_chain 이 갈래로 바꾼다."""

    def __init__(self, kind: RejectionKind, message: str, row: int | None = None, column: int | None = None) -> None:
        super().__init__(kind)
        self.rejection = ValueChainRejected(kind, row, column, message)


# ── glossary_xlsx.py 에서 옮김(zip·openpyxl 이 낼 수 있는 예외 · 꼴 지도 상수) ──
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

_NOT_XLSX: Final = "엑셀(.xlsx) 파일이 아니에요 — 가치사슬 표가 든 엑셀 파일을 올려 주세요."
_UNSAFE: Final = "이 엑셀 파일은 열 수 없어요 — 표만 새 파일에 옮겨 올려 주세요."
_BAD_HEADER: Final = (
    "열 이름 「사업 부문」「사업 내용」「밸류체인」「이해관계자」「관련 비즈니스 활동」을 차례대로 찾지 못했어요."
)


def read_value_chain(data: bytes) -> ValueChainRead | ValueChainRejected:
    try:
        return _read(data)
    except _Rejected as rejected:
        return rejected.rejection


def _read(data: bytes) -> ValueChainRead:
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
    return _table(data)


# ── glossary_xlsx.py 에서 옮김(아래 `_content_types_root` 까지 글자째) ──
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


# ── 고른 시트의 병합(expat — 트리를 짓지 않는다. 2 에서 이미 훑은 항목만 다시 읽는다) ──────────

_WORKBOOK: Final = "xl/workbook.xml"
_WORKBOOK_RELS: Final = "xl/_rels/workbook.xml.rels"
_REL_NS: Final = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CELL: Final = re.compile(r"\$?([A-Z]{1,3})\$?([1-9][0-9]{0,6})")


def _attributes(data: bytes, local: str, limit: int | None = None) -> list[dict[str, str]]:
    """끝 이름(이름공간을 뗀 것)이 local 인 요소들의 속성(문서 차례). `_parser()` 의 expat 이라 DOCTYPE·엔티티는 거절,
    요소·속성 수 합 ≤ MAX_XML_ELEMENTS · 표지 간격 ≤ MAX_XML_SPAN 은 _scan 과 같다. limit 를 넘게 모이면 거절."""
    parser = _parser()
    found: list[dict[str, str]] = []
    elements = [0]
    last = [0]

    def on_start(name: str, attributes: dict[str, str]) -> None:
        last[0] = parser.CurrentByteIndex
        elements[0] += 1 + len(attributes)
        if elements[0] > MAX_XML_ELEMENTS:
            raise _Rejected("unsafe_xlsx", _UNSAFE)
        if name.rsplit(" ", 1)[-1] == local:
            found.append(attributes)
            if limit is not None and len(found) > limit:
                raise _Rejected("unsafe_xlsx", _UNSAFE)

    def on_other(*_: object) -> None:
        last[0] = parser.CurrentByteIndex

    parser.StartElementHandler = on_start
    parser.EndElementHandler = on_other
    parser.CharacterDataHandler = on_other
    parser.CommentHandler = on_other
    parser.ProcessingInstructionHandler = on_other
    _feed(parser, data, last)
    return found


def _sheet_path(archive: zipfile.ZipFile, sizes: Mapping[str, int], title: str) -> str:
    """시트 이름 → 그 워크시트 XML 항목의 이름. openpyxl 이 같은 시트를 여는 풀이(`reader/workbook.py`
    `find_sheets` 의 `<sheet r:id>` → `packaging/relationship.py` `get_dependents` — External 은 Target 그대로, `/` 로
    시작하면 뗌, 그 밖은 `xl/` 기준 normpath)."""
    if _WORKBOOK not in sizes or _WORKBOOK_RELS not in sizes:
        raise _Rejected("not_xlsx", _NOT_XLSX)
    sheets = _attributes(_read_entry(archive, sizes, _WORKBOOK), "sheet")
    rels = _attributes(_read_entry(archive, sizes, _WORKBOOK_RELS), "Relationship")
    for sheet in sheets:
        rid = sheet.get(f"{_REL_NS} id")
        if sheet.get("name") != title or rid is None:
            continue
        for rel in rels:
            if rel.get("Id") != rid:
                continue
            target = rel.get("Target", "")
            if rel.get("TargetMode") == "External":
                path = target
            elif target.startswith("/"):
                path = target[1:]
            else:
                path = posixpath.normpath(posixpath.join(posixpath.dirname(_WORKBOOK), target))
            if path in sizes:
                return path
            break
        break
    raise _Rejected("not_xlsx", _NOT_XLSX)


def _column(letters: str) -> int:
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - ord("A") + 1
    return number


def _range(ref: str) -> tuple[int, int, int, int] | None:
    """「B6:B9」·「B6」 → (위 행, 왼 열, 아래 행, 오른 열), 1부터. 꼴이 아니면 None(그 병합은 없는 것으로)."""
    corners: list[tuple[int, int]] = []
    for part in ref.split(":"):
        matched = _CELL.fullmatch(part)
        if matched is None:
            return None
        corners.append((int(matched.group(2)), _column(matched.group(1))))
    if len(corners) not in (1, 2):
        return None
    (r1, c1), (r2, c2) = corners[0], corners[-1]
    return min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)


def _merges(data: bytes, title: str) -> list[tuple[int, int, int, int]]:
    """고른 시트의 병합 범위(위 행 차례). 읽는 자리(MAX_SCANNED_ROWS 행 · MAX_HEADER_COL 열) 밖은 자르거나 뺀다."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except _ZIP_ERRORS:
        raise _Rejected("not_xlsx", _NOT_XLSX) from None
    with archive:
        sizes = _declared_sizes(archive)
        sheet = _read_entry(archive, sizes, _sheet_path(archive, sizes, title))
    ranges: list[tuple[int, int, int, int]] = []
    for attributes in _attributes(sheet, "mergeCell", MAX_MERGES):
        found = _range(attributes.get("ref", ""))
        if found is None:
            continue
        r1, c1, r2, c2 = found
        if r1 <= MAX_SCANNED_ROWS and c1 <= MAX_HEADER_COL:
            ranges.append((r1, c1, min(r2, MAX_SCANNED_ROWS), min(c2, MAX_HEADER_COL)))
    return sorted(ranges)


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _filled(
    rows: Generator[tuple[object, ...]], ranges: list[tuple[int, int, int, int]], cut: list[int]
) -> Generator[tuple[object, ...]]:
    """행마다(1행부터 빠짐없이) 병합 범위의 빈 칸을 그 범위 왼쪽 위 칸의 값으로 채운다. 한 행에 걸린 범위들은 열이
    겹치지 않는다(겹치면 거절 — 그래서 한 행의 일은 MAX_HEADER_COL 안이다). `cut` 에 머리 행 번호가 들어오면(부르는
    쪽이 머리 행을 받은 뒤 넣는다 — 생성기가 게을러 다음 행보다 먼저 든다)
    왼쪽 위 행이 그 번호 이하인 범위로는 채우지 않는다(겹침 검사에는 남는다)."""
    active: list[tuple[int, int, int, int, object]] = []  # (위 행, 아래 행, 왼 열, 오른 열, 왼쪽 위 값)
    waiting = 0
    for number, row in enumerate(rows, start=1):
        cells = list((*row, *([None] * MAX_HEADER_COL))[:MAX_HEADER_COL])
        active = [a for a in active if a[1] >= number]
        while waiting < len(ranges) and ranges[waiting][0] <= number:
            r1, c1, r2, c2 = ranges[waiting]
            waiting += 1
            if r1 < number:  # 1행부터 빠짐없이 오므로 생기지 않는다 — 생기면 그 범위는 놓친 것
                continue
            if any(c1 <= right and left <= c2 for _, _, left, right, _ in active):
                raise _Rejected("unsafe_xlsx", _UNSAFE)
            active.append((r1, r2, c1, c2, cells[c1 - 1]))
        for top, _, left, right, value in active:
            if cut and top <= cut[0]:
                continue
            for column in range(left - 1, right):
                if _blank(cells[column]):
                    cells[column] = value
        yield tuple(cells)


# ── openpyxl ─────────────────────────────────────────────────────────────


def _rows(data: bytes, cut: list[int]) -> Generator[tuple[object, ...]]:
    """고른 시트의 A~(MAX_HEADER_COL) 칸(값만, 병합 채운 뒤 — `cut` 은 `_filled` 로 넘김). 훑은 행이 상한을 넘으면
    거절. 통합 문서는 끝나든 거절하든 닫는다(glossary_xlsx.py `_rows` 의 꼴)."""
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except _WORKBOOK_ERRORS:
        raise _Rejected("not_xlsx", _NOT_XLSX) from None
    try:
        try:
            sheets = workbook.worksheets
            if not sheets:
                raise _Rejected("not_xlsx", _NOT_XLSX)
            # 이름에 「value chain」(공백·대소문자 무시)이 든 첫 보이는 시트, 없으면 첫 보이는 시트(Q4 ①)
            visible = [s for s in sheets if s.sheet_state == "visible"]
            if not visible:
                raise _Rejected("not_xlsx", _NOT_XLSX)
            hinted = [s for s in visible if SHEET_HINT in re.sub(r"\s", "", s.title).lower()]
            sheet = (hinted or visible)[0]
            ranges = _merges(data, sheet.title)
            rows = sheet.iter_rows(min_row=1, max_col=MAX_HEADER_COL, values_only=True)
            for scanned, row in enumerate(_filled(rows, ranges, cut), start=1):
                if scanned > MAX_SCANNED_ROWS:
                    raise _Rejected(
                        "too_many_scanned_rows",
                        f"빈 행이 너무 많아요 — 표만 남기고 {MAX_SCANNED_ROWS:,}행 안으로 올려 주세요.",
                    )
                yield row
        except _WORKBOOK_ERRORS:
            raise _Rejected("not_xlsx", _NOT_XLSX) from None
    finally:
        workbook.close()


def _header_at(cells: tuple[object, ...]) -> int | None:
    """열 이름 다섯이 이웃한 다섯 칸에 차례대로 있는 첫 시작 열(0부터), 없으면 None."""
    stripped = tuple(c.strip() if isinstance(c, str) else c for c in cells)
    for start in range(len(stripped) - len(HEADER) + 1):
        if stripped[start : start + len(HEADER)] == HEADER:
            return start
    return None


def _text(value: object, row: int, column: int) -> str:
    """칸 하나 → strip 한 글(빈 칸이면 `""`). 글자가 아니거나 길면 거절."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise _Rejected(
            "not_text",
            f"{row}행의 {HEADER[column]} 칸이 글자가 아니에요 — 셀 서식을 텍스트로 바꿔 주세요.",
            row,
            column,
        )
    text = value.strip()
    if len(text) > MAX_CHARS[column]:
        raise _Rejected(
            "too_long", f"{row}행의 {HEADER[column]} 칸이 너무 길어요 — {MAX_CHARS[column]}자까지예요.", row, column
        )
    return text


def _table(data: bytes) -> ValueChainRead:
    found: list[Row] = []
    start: int | None = None
    cut: list[int] = []  # 머리 행 번호(찾으면) — `_filled` 가 그 행과 위에서 시작한 병합을 버린다
    rows = _rows(data, cut)
    try:
        for scanned, cells in enumerate(rows, start=1):
            if start is None:
                if scanned > MAX_HEADER_ROWS:
                    break
                start = _header_at(cells)
                if start is not None:
                    cut.append(scanned)
                continue
            five = cells[start : start + len(HEADER)]
            if all(_blank(c) for c in five[2:]):
                continue
            number = len(found) + 1
            if number > MAX_DATA_ROWS:
                raise _Rejected("too_many_rows", f"활동이 너무 많아요 — {MAX_DATA_ROWS}행까지 넣을 수 있어요.", number)
            unit, description, stage, stakeholder, activity = (
                _text(value, number, column) for column, value in enumerate(five)
            )
            if found and not unit:  # 사업 부문이 빈 행만 위 데이터 행에서 물려받는다(Q4 ③ — 감독 10-28 (나))
                unit = found[-1][0]
                description = description or found[-1][1]
            found.append((unit, description, stage, stakeholder, activity))
    finally:
        rows.close()
    if start is None:
        raise _Rejected("bad_header", _BAD_HEADER)
    if not found:
        raise _Rejected("no_rows", "활동이 없어요 — 열 이름 아래에 가치사슬 활동을 적어 주세요.")
    return ValueChainRead(tuple(found))
