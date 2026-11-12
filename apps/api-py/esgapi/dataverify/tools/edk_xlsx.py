# pyright: reportUnknownMemberType=false
"""EDK 인벤토리 엑셀(지금 양식 — 1행 머리 14열, 연도 열 「YYYY년」) 바이트 → 데이터 검증 입력 dataverify.input@1 의
`data` 꼴(테마 → 항목, 열쇠 열하나), 그리고 같은 머리의 양식(밴드 DVX1, MARC-ENT-505 §2.1 ③). 상태가 없다: 디스크·
저장소·DB 에 쓰지 않고, 메모리의 바이트 하나를 아래 방어 뒤에 openpyxl 에 넘긴다.

    read_edk(data) -> EdkRead | EdkRejected      어떤 바이트도 예외 대신 갈래(MemoryError 만 밖으로)
    template(year) -> bytes                      양식(시트 「인벤토리 데이터」 머리 14열 + 가상 예시 한 줄 ·
                                                 「작성 안내」). 매번 같은 바이트
    workbook(years, rows) -> bytes               같은 머리로 행을 적은 통합 문서(양식·데모 스크립트가 같이 쓴다)

★ 출처: zip·XML 방어(1·2)는 translation/tools/glossary_xlsx.py(밴드 TR3a)를 **옮겨 적은 것**이다 — `_read`·
`_declared_sizes`·`_read_entry`·`_check_entries`·`_XML_SIGNATURES`·`_SPACE_THEN_LT`·`_looks_like_xml`·`_parser`·
`_feed`·`_scan`·`_content_types_root`·`_ZIP_ERRORS`·`_WORKBOOK_ERRORS` 와 상한 상수(곁 글 포함)는 글자째, 바꾼 것은
거절 글·kind 이름·결과 이름(GlossaryRead → EdkRead · _pairs → _items)과 `MAX_XML_ELEMENTS` 의 값 하나뿐이다(곁 글에
까닭). import 하지 않는다(모듈끼리 의존 0). **한쪽을 고치면 다른 쪽도** — tests/tools/test_edk_xlsx_twin.py 가 두
소스의 AST 를 견준다. zip 가운데 목록 앞 검사(translation/tools/zip_guard.py)는 부르지 않는다 — 그 까닭은
MAX_BYTES ≤ zip_guard 의 MAX_CENTRAL_DIRECTORY(가운데 목록은 본문보다 클 수 없다. 1MiB 안 최대 항목 1.2만 개 zip 이
unsafe_xlsx 0.015초·RSS +6.8MB — DVX1 보고)이고, 같음 시험이 두 값을 견준다(MAX_BYTES 를 올리면 깨진다).
defusedxml 은 api venv 에 없고 더하지 않는다 — 방어는 openpyxl 앞의 expat 훑기(2)가 맡는다.

읽는 차례(어기는 첫 것 하나로 거절):
1·2. glossary_xlsx.py 의 머리말 1·2 그대로(바이트 상한 → zip 항목 상한·선언 대조 → XML 로 보이는 모든 항목을 expat 으로
   끝까지 훑기 — DOCTYPE·엔티티·깊이·요소 수 합·표지 간격).
3. `openpyxl.load_workbook(BytesIO, read_only=True, data_only=True)` 의 `worksheets[0]`(차례상 첫째 — 이름·숨김 무시)
   → `iter_rows(min_row=1, max_col=MAX_COLUMNS, values_only=True)` → 훑은 행(빈 행 포함) ≤ MAX_SCANNED_ROWS → 끝에
   `close()`(finally). 둘째 시트부터는 읽지 않는다.
4. 머리 = **1행만**. 열 이름은 앞뒤 공백을 떼고 정확히 같은지, 자리와 상관없이 이름으로 찾는다: 꼭 있는 열 열
   (REQUIRED) + 연도 열(`^[0-9]{4}년$`, 또는 1002~9999 의 정수 칸) 하나 이상. 빠짐·같은 이름 둘·같은 연도 둘이면
   bad_header. 그 밖의 머리 칸(「공시」 등)은 읽지 않고 수(ignoredColumns)만 센다.
5. 2행부터: 읽는 칸(꼭 열 + 연도 열)이 다 빈 행은 건너뛴다(skippedEmptyRows — 읽지 않는 열에만 값이 있어도 빈 행).
   읽는 칸이 bool·날짜·시각·유한하지 않은 수면 bad_cell, 글자가 MAX_CELL_CHARS 를 넘으면 long_cell(둘 다 그 칸의 엑셀
   행·열 번호), 테마 칸이 글자가 아니거나 빈 글이면 no_theme. 항목 수(테마를 거르기 전) >
   MAX_ITEMS 면 too_many_rows. 수 칸의 정수인 float(`90001.0`, |값| < 2**53)는 int, 그 밖의 값(글자 — strip 0)은
   받은 그대로, 빈 칸은 None. 연도 열쇠는 머리에서 「년」을 뗀 글(빈 칸이어도 열쇠는 둔다, 오름차순).
6. 검증 대상 테마(engines/colab_156/inputs.py 의 THEMES — 지금 「환경」 하나)만 `data` 에 싣고(항목은 파일 차례), 나머지
   테마는 수(skipped)만 낸다(이름·값 0 — 응답 크기와 고객 글을 줄인다. 흐름도 split_themes 로 그 테마만 본다). 테마는
   앞뒤 공백을 뗀 글로 묶는다(「환경 」도 환경 — 항목의 테마 칸 값은 받은 그대로). 항목이 하나도 없으면 no_rows, 있는데
   대상 테마가 0이면 no_target_theme.
7. 크기: 싣는 항목의 글자(UTF-8 바이트)·수(글자 꼴 길이) 합을 모으며 세어 OPTIONS_MAX_OCTETS 를 넘으면 그 자리에서
   converted_too_large — 그 data 로는 실행 옵션 상한을 넘는다(공유 문자열 하나를 여러 칸이 가리켜 작은 파일이 큰 응답을
   짓는 꼴을 막는다).

`row`·`column` 은 엑셀의 행·열 번호(1부터 — 머리가 1행)다. 파일 전체의 까닭이면 None. 거절 글은 해요체 한 문장이고
칸의 값은 싣지 않는다(로그·응답에 고객 글이 새지 않게).

★ 무효 조건(잰 것과 안 잰 것):
- 잰 것은 openpyxl 3.1.5 가 지은 파일(지어낸 가상 기업), 손으로 지은 공격 파일, 받은 견본 둘(MARC-ENT-506 — 수·kind
  만, 보고)뿐이다. Excel 이외(한글·구글 시트)가 저장한 파일은 재지 않았다. 상한의 값은 전부 어림이다(근거는 상수 곁).
- 지금 양식만 안다(일반 엑셀 구조화 0 · v3 양식 MARC-ENT-507 은 밖). 머리가 2행 이상이면 bad_header.
- `#N/A` 같은 오류 칸은 openpyxl 이 글자로 내준다 — 그 글이 그대로 값이 된다. 숨은 행·열은 그대로 읽는다.
"""

import io
import math
import re
import struct
import xml.parsers.expat
import zipfile
import zlib
from collections.abc import Generator, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils.exceptions import InvalidFileException, ReadOnlyWorkbookException

from esgapi.dataverify.engines.colab_156.inputs import THEMES

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

MAX_XML_ELEMENTS: Final = 500_000
"""훑기 대상 XML 의 요소 수 합 — 속성 하나·이름공간 선언 하나도 1 로 같은 예산에 더한다(glossary_xlsx.py 와 같은 셈).
**옮긴 상수 가운데 값이 다른 하나**(glossary 는 100,000 — 쌍둥이 시험의 「다름 허락」): 받은 견본 하나가 그 예산으로
unsafe_xlsx 였다(약 117k — 발주서 Q4). openpyxl 의 일은 요소 수에 비례한다(glossary 머리말: 200만 개가 4.1초·RSS
+315MB) — 이 예산 안 가장 나쁜 꼴 셋을 잰 값은 보고 ★D(밴드 DVX1)."""

MAX_XML_SPAN: Final = 1024 * 1024
"""이벤트(요소 시작·끝·글 조각) 사이의 바이트 상한. expat 은 시작 표지 하나를 다 읽은 뒤에야 속성 전부를 사전으로 지어
handler 에 넘긴다 — 8MiB 항목 한 요소의 속성 80만 개는 그 사전만으로 0.96초·RSS +300MB 였다(러너 실측). 먹이는
조각마다 이 간격을 재서 사전을 짓기 전에 거절한다. 글은 expat 이 조각으로 알려 주므로 긴 칸 글은 걸리지 않는다."""


# ── 이 읽개의 상한(전부 어림 — 발주서 Q4) ──
MAX_COLUMNS: Final = 40
"""읽는 열(A~AN). 지금 양식은 14열이다(연도 열을 더해도 넉넉히). 머리가 그 너머면 bad_header."""
MAX_ITEMS: Final = 2_000
"""항목 수(빈 행 빼고, 테마를 거르기 전). 받은 견본 최대 약 600(발주서 Q4). 웹(entities/dataverify)도 같은 값."""
MAX_CELL_CHARS: Final = 2_000
"""읽는 칸 하나의 글자 수(가지 리뷰 B1a — 공유 문자열 하나가 수백만 자여도 칸마다 여기서 멈춘다)."""
OPTIONS_MAX_OCTETS: Final = 256 * 1024
"""실은 글자·수 합의 상한(가지 리뷰 B1b) = 데이터 검증 흐름의 옵션 상한(core/flows/binding.py 의 dataverify.colab@156
max_options_bytes) = 웹 model/options.ts OPTIONS_MAX_OCTETS — 같은 값 시험이 본다. 합은 JSON 바이트보다 작은 어림이라
넘으면 실행 옵션도 반드시 넘는다."""

ID_COLUMN: Final = "ID"
THEME_COLUMN: Final = "테마"
VALUES_KEY: Final = "values"
REQUIRED: Final = ("ID", "테마", "항목", "대분류", "중분류", "소분류", "입력 방식", "단위", "메모", "핵심데이터")
"""꼭 있어야 하는 머리 열(연도 열 빼고). 지금 양식의 「공시」는 읽지 않는다(항목 열쇠가 아니다 — 발주서 Q7)."""
ITEM_KEYS: Final = (
    "ID",
    "테마",
    "항목",
    "대분류",
    "중분류",
    "소분류",
    "입력 방식",
    "단위",
    VALUES_KEY,
    "핵심데이터",
    "메모",
)
"""항목 열쇠 열하나와 그 차례(contracts/shapes.py 의 EdkItem 차례 — 코랩 셀 2)."""
YEAR_HEADER: Final = re.compile(r"[0-9]{4}년")
"""연도 열 머리(fullmatch). 열쇠는 「년」을 뗀 네 자리."""
YEAR_NUMBER_MIN: Final = 1002
"""머리 칸이 수일 때 연도로 받는 범위(양식 GET 의 year 범위와 같음 — 그 밖의 수 머리는 읽지 않는 열)."""
YEAR_NUMBER_MAX: Final = 9999
_EXACT_FLOAT_LIMIT: Final = 2**53
"""이 크기 안의 정수인 float 만 int 로 바꾼다(그 밖은 float 가 정확한 정수가 아니라 받은 float 그대로)."""

SHEET_TITLE: Final = "인벤토리 데이터"
GUIDE_TITLE: Final = "작성 안내"
TEMPLATE_DATE: Final = (1980, 1, 1, 0, 0, 0)
"""양식 zip 항목의 시각(zip 이 적을 수 있는 가장 이른 시각 — 매번 같은 바이트)."""

RejectionKind = Literal[
    "too_large",
    "not_xlsx",
    "unsafe_xlsx",
    "bad_header",
    "bad_cell",
    "no_theme",
    "too_many_rows",
    "too_many_scanned_rows",
    "no_rows",
    "no_target_theme",
    "long_cell",
    "converted_too_large",
]

EdkCell = str | int | float | None
"""읽은 칸의 값(contracts/shapes.py 의 EdkValue 와 같은 꼴)."""
EdkItemDict = dict[str, EdkCell | dict[str, EdkCell]]


@dataclass(frozen=True, slots=True)
class EdkRead:
    data: dict[str, list[EdkItemDict]]
    """대상 테마 → 항목(파일의 행 차례). 열쇠는 ITEM_KEYS 차례."""
    skipped_themes: int
    """싣지 않은 테마 수(이름은 내지 않는다)."""
    skipped_items: int
    """그 테마들의 항목 수."""
    years: tuple[str, ...]
    """머리의 연도(오름차순)."""
    skipped_empty_rows: int
    """건너뛴 빈 행 수(머리 아래, 마지막 항목 뒤의 것도)."""
    ignored_columns: int
    """읽지 않은 머리 칸 수(빈 머리 칸은 세지 않는다)."""

    @property
    def item_count(self) -> int:
        return sum(len(items) for items in self.data.values())


@dataclass(frozen=True, slots=True)
class EdkRejected:
    kind: RejectionKind
    row: int | None
    """엑셀의 행 번호(1부터 — 머리가 1). 파일 전체면 None."""
    column: int | None
    """엑셀의 열 번호(1부터). 파일·행 전체면 None."""
    message: str


class _RootSeen(Exception):
    """뿌리 요소 확인을 멈추는 신호."""


class _Rejected(Exception):
    """제어 흐름용. 밖으로 새지 않는다: read_edk 가 갈래로 바꾼다."""

    def __init__(self, kind: RejectionKind, message: str, row: int | None = None, column: int | None = None) -> None:
        super().__init__(kind)
        self.rejection = EdkRejected(kind, row, column, message)


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

_NOT_XLSX: Final = "엑셀 파일을 열지 못했어요 — EDK 인벤토리 양식을 .xlsx 로 저장해 올려 주세요."
_UNSAFE: Final = "이 엑셀 파일은 열 수 없어요 — 표만 새 파일에 옮겨 저장한 뒤 올려 주세요."
_BAD_HEADER: Final = "1행에서 EDK 인벤토리 양식의 열 이름을 찾지 못했어요 — 첫 행을 고치지 말고 올려 주세요."


def read_edk(data: bytes) -> EdkRead | EdkRejected:
    try:
        return _read(data)
    except _Rejected as rejected:
        return rejected.rejection


def _read(data: bytes) -> EdkRead:
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
    return _items(data)


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


def _rows(data: bytes) -> Generator[tuple[object, ...]]:
    """첫 시트의 행(값만, MAX_COLUMNS 열까지). 훑은 행이 상한을 넘으면 거절. 통합 문서는 끝나든 거절하든 닫는다."""
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except _WORKBOOK_ERRORS:
        raise _Rejected("not_xlsx", _NOT_XLSX) from None
    try:
        try:
            sheets = workbook.worksheets
            if not sheets:
                raise _Rejected("not_xlsx", _NOT_XLSX)
            rows = sheets[0].iter_rows(min_row=1, max_col=MAX_COLUMNS, values_only=True)
            for scanned, row in enumerate(rows, start=1):
                if scanned > MAX_SCANNED_ROWS:
                    raise _Rejected(
                        "too_many_scanned_rows",
                        f"빈 행이 너무 많아요 — 표 아래의 빈 행을 지우고 {MAX_SCANNED_ROWS:,}행 안으로 올려 주세요.",
                    )
                yield tuple(row)
        except _WORKBOOK_ERRORS:
            raise _Rejected("not_xlsx", _NOT_XLSX) from None
    finally:
        workbook.close()


@dataclass(frozen=True, slots=True)
class _Header:
    columns: dict[str, int]
    """꼭 열 이름 → 0부터의 자리."""
    years: tuple[tuple[str, int], ...]
    """(연도 네 자리, 0부터의 자리) — 오름차순."""
    ignored: int


def _header(cells: Sequence[object]) -> _Header:
    """1행 → 꼭 열·연도 열의 자리. 빠짐·겹침이면 bad_header(겹침은 그 열 번호)."""
    columns: dict[str, int] = {}
    years: dict[str, int] = {}
    ignored = 0
    for index, cell in enumerate(cells):
        name = cell.strip() if isinstance(cell, str) else cell
        if name is None or name == "":
            continue
        if name in REQUIRED:
            if name in columns:
                raise _Rejected("bad_header", _BAD_HEADER, 1, index + 1)
            columns[str(name)] = index
        elif isinstance(name, str) and YEAR_HEADER.fullmatch(name):
            year = name[:-1]
            if year in years:
                raise _Rejected("bad_header", _BAD_HEADER, 1, index + 1)
            years[year] = index
        elif isinstance(name, int) and not isinstance(name, bool) and YEAR_NUMBER_MIN <= name <= YEAR_NUMBER_MAX:
            # 머리 칸을 수로 적은 연도(2023) — 「2023년」과 같은 열쇠라 둘 다 있으면 겹침이다.
            year = str(name)
            if year in years:
                raise _Rejected("bad_header", _BAD_HEADER, 1, index + 1)
            years[year] = index
        else:
            ignored += 1
    if len(columns) != len(REQUIRED) or not years:
        raise _Rejected("bad_header", _BAD_HEADER, 1)
    return _Header(columns, tuple(sorted(years.items())), ignored)


def _value(cell: object, row: int, index: int) -> EdkCell:
    """읽는 칸 하나 → 값. 정수인 float 는 int, 글자·수는 그대로, 빈 칸 None. bool·날짜·시각·무한·NaN 은 bad_cell."""
    if cell is None:
        return cell
    if isinstance(cell, str):
        if len(cell) > MAX_CELL_CHARS:
            raise _Rejected(
                "long_cell",
                f"{row}행 {index + 1}열 칸의 글이 너무 길어요 — {MAX_CELL_CHARS:,}자 안으로 줄여 주세요.",
                row,
                index + 1,
            )
        return cell
    if isinstance(cell, bool) or not isinstance(cell, int | float):
        raise _Rejected(
            "bad_cell",
            f"{row}행 {index + 1}열에 날짜나 참/거짓 칸이 있어요 — 숫자나 글자로 바꿔 주세요.",
            row,
            index + 1,
        )
    if isinstance(cell, float):
        if not math.isfinite(cell):
            raise _Rejected(
                "bad_cell", f"{row}행 {index + 1}열의 숫자를 읽지 못했어요 — 숫자나 글자로 바꿔 주세요.", row, index + 1
            )
        if cell.is_integer() and abs(cell) < _EXACT_FLOAT_LIMIT:
            return int(cell)
    return cell


def _item(cells: Sequence[object], header: _Header, row: int) -> EdkItemDict:
    """데이터 행 하나 → 항목(ITEM_KEYS 차례). 읽는 칸을 열 차례로 보고(bad_cell 이 먼저), 그 뒤 테마 칸."""
    read = {i: _value(cells[i], row, i) for i in sorted([*header.columns.values(), *(i for _, i in header.years)])}
    found = {name: read[i] for name, i in header.columns.items()}
    values = {year: read[i] for year, i in header.years}
    theme = found[THEME_COLUMN]
    if not isinstance(theme, str) or not theme.strip():
        raise _Rejected("no_theme", f"{row}행의 테마 칸이 비어 있어요.", row, header.columns[THEME_COLUMN] + 1)
    return {key: values if key == VALUES_KEY else found[key] for key in ITEM_KEYS}


def _octets(item: EdkItemDict) -> int:
    """항목이 싣는 글자(UTF-8 바이트)·수(글자 꼴 길이)의 합 — JSON 바이트의 아래 어림(열쇠·따옴표·쉼표 뺌)."""
    total = 0
    for key, value in item.items():
        for cell in value.values() if key == VALUES_KEY and isinstance(value, Mapping) else (value,):  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if isinstance(cell, str):
                total += len(cell.encode("utf-8", "surrogatepass"))
            elif isinstance(cell, int | float):
                total += len(repr(cell))
    return total


def _items(data: bytes) -> EdkRead:
    target: dict[str, list[EdkItemDict]] = {}
    others: dict[str, int] = {}
    total = 0
    empty = 0
    octets = 0
    rows = _rows(data)
    try:
        first = next(rows, None)
        if first is None:  # 빈 시트
            raise _Rejected("bad_header", _BAD_HEADER, 1)
        header = _header(first)
        read = sorted([*header.columns.values(), *(i for _, i in header.years)])
        for number, row in enumerate(rows, start=2):
            cells = (*row, *([None] * (MAX_COLUMNS - len(row))))
            if all(cells[i] is None for i in read):  # 읽지 않는 열에만 값이 있어도 빈 행
                empty += 1
                continue
            item = _item(cells, header, number)
            total += 1
            if total > MAX_ITEMS:
                raise _Rejected("too_many_rows", f"항목이 너무 많아요 — 파일 하나에 {MAX_ITEMS:,}개까지예요.", number)
            theme = str(item[THEME_COLUMN]).strip()
            if theme not in THEMES:
                others[theme] = others.get(theme, 0) + 1
                continue
            octets += _octets(item)
            if octets > OPTIONS_MAX_OCTETS:
                raise _Rejected(
                    "converted_too_large",
                    "읽은 항목이 너무 많아 한 번에 검증할 수 없어요 — 환경 테마 줄을 나눠 올려 주세요.",
                    number,
                )
            target.setdefault(theme, []).append(item)
    finally:
        rows.close()
    if total == 0:
        raise _Rejected("no_rows", "항목이 하나도 없어요 — 2행부터 항목을 채워 올려 주세요.")
    if not target:
        raise _Rejected("no_target_theme", "검증하는 테마의 항목이 없어요 — 환경 테마 줄이 든 파일을 올려 주세요.")
    return EdkRead(
        data={theme: target[theme] for theme in THEMES if theme in target},
        skipped_themes=len(others),
        skipped_items=sum(others.values()),
        years=tuple(year for year, _ in header.years),
        skipped_empty_rows=empty,
        ignored_columns=header.ignored,
    )


# ── 양식 ─────────────────────────────────────────────────────────────────


def header_row(years: Sequence[str]) -> tuple[str, ...]:
    """지금 양식의 1행 머리(14열 차례 — 연도 열은 「단위」와 「메모」 사이, 「공시」는 읽지 않지만 양식에는 둔다)."""
    return (
        "ID",
        "테마",
        "항목",
        "대분류",
        "중분류",
        "소분류",
        "입력 방식",
        "단위",
        *(f"{y}년" for y in years),
        "메모",
        "공시",
        "핵심데이터",
    )


def row_of(item: Mapping[str, object], years: Sequence[str]) -> list[object]:
    """항목 하나 → header_row(years) 차례의 칸(「공시」는 빈 칸). 데모 스크립트가 쓴다."""
    raw = item.get(VALUES_KEY)
    values: Mapping[str, object] = raw if isinstance(raw, Mapping) else {}  # pyright: ignore[reportUnknownVariableType]
    head = [item.get(key) for key in REQUIRED[:8]]
    return [*head, *(values.get(y) for y in years), item.get("메모"), None, item.get("핵심데이터")]


GUIDE: Final = (
    "EDK 인벤토리 양식 — 작성 안내",
    "1. 「인벤토리 데이터」 시트의 첫 행(열 이름)은 바꾸지 않아요.",
    "2. 연도 열은 「YYYY년」 꼴이면 바꾸거나 더해도 돼요.",
    "3. 검증하는 줄은 테마가 「환경」이고 핵심데이터가 「Y」인 줄이에요(그 밖의 환경 줄은 맥락으로 써요).",
    f"4. 파일 하나는 {MAX_BYTES // (1024 * 1024)}MB, 항목 {MAX_ITEMS:,}개 안이에요.",
    "5. 숫자 칸은 숫자로 적어 주세요. 날짜·참/거짓 칸은 읽지 않아요.",
    f"6. 칸 하나의 글은 {MAX_CELL_CHARS:,}자 안으로 적어 주세요.",
    "7. 2행은 지어낸 예시 줄이에요 — 지우고 채워 주세요.",
)


def workbook(years: Sequence[str], rows: Iterable[Sequence[object]], *, guide: bool = False) -> bytes:
    """첫 시트 「인벤토리 데이터」(굵은 머리 header_row(years) + 행)와, guide 면 「작성 안내」 시트. 매번 같은 바이트
    (_restamp)."""
    book = Workbook()
    sheet = book.worksheets[0]
    sheet.title = SHEET_TITLE
    sheet.append(list(header_row(years)))
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(list(row))
    if guide:
        notes = book.create_sheet(GUIDE_TITLE)
        for line in GUIDE:
            notes.append([line])
        notes.column_dimensions["A"].width = 100
    book.properties.creator = "esgapi"
    buffer = io.BytesIO()
    book.save(buffer)
    return _restamp(buffer.getvalue())


def template(year: int) -> bytes:
    """양식: 연도 열 셋(year−2·year−1·year)과 가상 예시 한 줄(테마 「환경」·핵심데이터 「Y」 — 지어낸 값)."""
    years = [str(year - 2), str(year - 1), str(year)]
    example = {
        "ID": 1,
        "테마": "환경",
        "항목": "가상 직접 배출량",
        "대분류": "온실가스",
        "중분류": "Scope 1",
        "소분류": "가상 연소",
        "입력 방식": "숫자",
        "단위": "tCO2eq",
        "values": dict(zip(years, (1200, 1150, 1100), strict=True)),
        "메모": "예시 줄 — 지우고 채워 주세요",
        "핵심데이터": "Y",
    }
    return workbook(years, [row_of(example, years)], guide=True)


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
