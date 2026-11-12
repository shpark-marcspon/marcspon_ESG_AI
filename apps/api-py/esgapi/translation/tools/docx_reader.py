# pyright: reportUnknownMemberType=false
"""docx 바이트 → 구조 글(코랩 셀 7 `docx_to_structured_txt` R/241, `_iter_docx_blocks` R/228). **올린(남이 준) docx 를
여는 것은 이 파일뿐이다**(outputs/readback 은 우리가 지은 바이트만 연다). python-docx 에는 아래 방어를 지난 같은
바이트만 넘긴다(메모리의 바이트 하나 — 디스크에 쓰지 않는다).

`read_docx` 는 어떤 바이트를 받아도 예외를 내지 않는다: 읽히면 `DocxText`, 아니면 `DocxRejected`(갈래). 단 잡는 것은
이름 붙인 목록이고 `MemoryError` 는 밖으로 낸다(OOM 신호를 「문서 못 읽음」으로 바꾸지 않는다).

글은 코랩대로다: 몸의 직속 자식 중 문단(`w:p`)과 표(`w:tbl`)만 차례대로. 문단은 `.text.rstrip()`(빈 문단은 빈 줄),
표는 행마다 `row.cells` 의 `cell.text` 를 `structured.table_rows_to_markdown` 에 넘기고, 바로 앞 줄이 `[MARKDOWN_TABLE]`
이 아니면 그 줄을 끼우고, 표 뒤에 빈 줄. 마지막에 `"\\n".join`.

★ 여기서 정규화(`normalize_structured_tags`)를 하지 않는다: 엔진의 `source_and_pages` 가 한 번 한다(코랩도 셀 7 에서 한
번 — R/271 — 하고 파일로 쓴 뒤 셀 17 이 읽는다). 정규화는 멱등이 아니다: `'****[PAGE 1]****'` → `'**[PAGE 1]**'` →
`'[PAGE 1]'`. 여기서 하면 두 번이 된다.

★ 무효 조건(이 읽개가 잰 것과 안 잰 것):
- 잰 것은 시험이 python-docx 1.2.0 으로 지은 문서와 손으로 지은 공격 파일뿐이다. Word·한글·LibreOffice·구글 문서가
  저장한 실제 보고서는 재지 않았다(표본 0 — MARC-ENT-170). 상한의 값은 전부 어림이다(아래 상수 곁의 근거).
- 약점 W11(코랩대로): 몸 직속의 `w:sdt`(내용 컨트롤 — 목차 등)·`w:altChunk`·`w:customXml` 안의 글은 빠진다. 대신 태그별
  수를 `skipped` 로 돌려준다(`w:sectPr` 는 세지 않는다). 머리말·바닥글·글상자·각주는 읽지 않는다.
- 약점 W12(python-docx 1.2.0 의 `_Row.cells`): 가로 병합 칸은 칸 수만큼 되풀이되고 세로 병합의 이어진 칸은 위 칸으로
  돌아온다 — 같은 글이 pipe 표의 여러 칸에 나온다. 판을 올리면 W11·W12 를 다시 잰다.
- zip: 항목마다 선언된 크기 + 1 바이트까지만 풀어 길이가 선언과 다르면 거절한다. CPython zipfile 이 이미 선언된
  크기에서 자르고 CRC 로 거절한다 — +1 은 겹친 방어다. 항목은 하나씩 풀어 보고 버린다(그 뒤 python-docx 가 관계가
  가리키는 파트를 다시 풀어 메모리에 든다 — 선언 크기 합 상한이 그 몫을 묶는다).
- DOCTYPE 훑기의 대상(넓은 쪽) = 이름이 `.xml`·`.rels` 인 항목 ∪ `[Content_Types].xml` 의 Default(확장자)·Override(파트
  이름) 꼴이 `xml` 로 끝나는 항목. python-docx 는 이름이 아니라 내용 꼴로 파싱하기 때문이다. expat 에 DOCTYPE 갈고리와
  뿌리 요소 갈고리만 건다(트리 0 — 뿌리 요소가 나오면 멈춘다. DOCTYPE 은 그 앞에만 올 수 있다). expat 이 그 머리를 못
  읽으면(깨진 XML·expat 이 모르는 인코딩) 거절한다 — Word 가 저장한 파트는 UTF-8 이다(추정).
- 파싱될 XML 합(`MAX_XML_BYTES`)의 대상(좁은 쪽) = `[Content_Types].xml` + 모든 `.rels` + 꼴이 python-docx 1.2.0 이
  바로 파싱하는 여덟(`docx/__init__.py:44-51` 의 등록 — `PARSED_CONTENT_TYPES`)인 파트. 그 밖의 꼴(차트·테마·각주 등)은
  python-docx 가 바이트 덩이로만 든다(`docx/opc/part.py:85-86`). 두 집합이 다른 까닭: DOCTYPE 은 파싱되지 않을 파트에
  있어도 값싸게 거절할 수 있고, 메모리 증폭(RSS ≈ XML 바이트 × 약 58 — critic 실측 하나)은 파싱되는 파트에서만 난다.
- python-docx 는 엔티티를 풀지 않고(`resolve_entities=False`) 외부 관계(`TargetMode="External"`)를 열지 않는다.
  이 읽개도 열지 않는다.
- Strict OOXML(`http://purl.oclc.org/ooxml/` 이름 공간)은 python-docx 가 못 읽는다 — `unreadable_document` 로 거절하고
  detail 에 그렇다고 적는다.
"""

import io
import struct
import xml.parsers.expat
import zipfile
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final, Literal, cast

from docx.document import Document
from docx.exceptions import PythonDocxError
from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.exceptions import OpcError
from docx.opc.packuri import PackURI
from docx.oxml.document import CT_Body
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.package import Package
from docx.parts.document import DocumentPart
from docx.table import Table
from docx.text.paragraph import Paragraph

from esgapi.translation.engines.colab_158.structured import table_rows_to_markdown
from esgapi.translation.tools.zip_guard import MAX_CENTRAL_DIRECTORY, central_directory_refusal

# ── 상한(전부 어림 — 근거와 무엇을 재면 바뀌나) ──
MAX_BYTES: Final = 50 * 1024 * 1024
"""받은 바이트. = 올리기 상한 기본값(config/env.py max_upload_bytes). 그 이상은 올리기 경로가 413 이다."""
MAX_ENTRIES: Final = 1_000
"""zip 항목 수. python-docx 의 방문 목록이 list(파트 수의 제곱 셈)이고 관계 사슬이 재귀 생성기라(깊이 약 499 까지 —
★d 실측 RecursionError 0) 둘을 함께 묶는 값."""
MAX_ENTRY_BYTES: Final = 64 * 1024 * 1024
"""항목 하나의 선언된(풀린) 크기. 그림 등 파싱되지 않는 파트 몫."""
MAX_DECLARED_BYTES: Final = 256 * 1024 * 1024
"""모든 항목의 선언된 크기 합."""
MAX_XML_BYTES: Final = 8 * 1024 * 1024
"""파싱될 XML(위 좁은 쪽)의 선언된 크기 합. compose 의 api-py·worker-py mem_limit 1g 에서 거꾸로 낸 값(RSS ≈ XML × 약 58
→ 8 MiB ≈ 0.46 GB). ★c 의 잰 값으로 다시 정한다."""
MAX_GRID_COLS: Final = 64
"""표 한 행의 폭(gridBefore + Σ gridSpan + gridAfter). Word 표의 열 상한 63(critic 추정)을 덮는 값."""
MAX_TABLE_CELLS: Final = 200_000
"""문서 전체 Σ 행 폭 = `row.cells` 가 내는 칸 수(xlsx 읽개 MAX_CELLS 꼴). gridSpan 10,000,000 칸 하나가 140초·727 MiB
(critic 실측)라 칸 수를 먼저 센다."""
MAX_VMERGE_STEPS: Final = 500_000
"""세로 병합 되짚기 수 = Σ(이어진 칸마다 그 칸의 사슬 깊이). python-docx 의 `_tc_above` 는 이어진 칸마다 사슬을 뿌리까지
다시 걷는다(n² — 실측 열 하나 사슬 300행 1.0초·600행 4.5초·1,000행 15.5초에 RecursionError). 한 번 약 33µs 라 상한에서
약 16초. 깊이 1,000 사슬 하나(약 499,500)는 지난다 — 그 RecursionError 는 `unreadable_document` 로 받는다.
(감독 처분 ★d)"""

PARSED_CONTENT_TYPES: Final = frozenset(
    {
        CT.OPC_CORE_PROPERTIES,
        CT.WML_COMMENTS,
        CT.WML_DOCUMENT_MAIN,
        CT.WML_FOOTER,
        CT.WML_HEADER,
        CT.WML_NUMBERING,
        CT.WML_SETTINGS,
        CT.WML_STYLES,
    }
)
"""python-docx 1.2.0 이 `XmlPart.load` 로 바로 파싱하는 꼴 여덟(`docx/__init__.py:44-51`). 판을 올리면 다시 잰다."""

RejectionKind = Literal[
    "empty",
    "too_many_bytes",
    "not_a_zip",
    "too_many_entries",
    "duplicate_entry",
    "entry_too_large",
    "declared_entries_too_large",
    "encrypted_entry",
    "unsupported_compression",
    "missing_entry",
    "unreadable_entry",
    "broken_xml",
    "doctype",
    "xml_too_large",
    "not_a_word_document",
    "unreadable_document",
    "table_too_large",
    "vertical_merge_too_deep",
]


@dataclass(frozen=True, slots=True)
class DocxRejected:
    kind: RejectionKind
    where: str  # zip 항목 이름, 표면 `표 <n>`, 문서 전체면 빈 글
    detail: str


@dataclass(frozen=True, slots=True)
class DocxText:
    text: str
    """정규화 전 구조 글(코랩 셀 7 의 `"\\n".join(lines)` — R/270). 엔진에 structuredText 로 넣는다."""
    skipped: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    """읽지 않고 건너뛴 몸 직속 자식의 태그별 수(W11). 비면 건너뛴 것 0."""


class _Rejected(Exception):
    """제어 흐름용. 밖으로 새지 않는다: read_docx 가 갈래로 바꾼다."""

    def __init__(self, kind: RejectionKind, where: str, detail: str) -> None:
        super().__init__(kind)
        self.rejection = DocxRejected(kind, where, detail)


class _RootSeen(Exception):
    """expat 훑기를 뿌리 요소에서 멈추는 신호."""


# zipfile 이 망가진 바이트에서 낼 수 있는 것들(xlsx_reader._ZIP_ERRORS 판별 복사). 이름으로 적는다.
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
# python-docx·lxml 이 방어를 지난 바이트에서 낼 수 있는 것들. SyntaxError = lxml 의 XMLSyntaxError(lxml 을 import 하지
# 않고 잡는다). RecursionError 는 RuntimeError 아래지만 까닭을 보이려고 따로 적는다(세로 병합 사슬 — ★d).
_DOCUMENT_ERRORS: Final = (
    *_ZIP_ERRORS,
    RecursionError,
    SyntaxError,
    PythonDocxError,
    OpcError,
    TypeError,
    AttributeError,
)

_CT_NS: Final = "http://schemas.openxmlformats.org/package/2006/content-types"
_STRICT_NS: Final = "http://purl.oclc.org/ooxml/"
_W_NS: Final = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_CONTENT_TYPES: Final = "[Content_Types].xml"
_CHUNK: Final = 64 * 1024


def read_docx(data: bytes) -> DocxText | DocxRejected:
    try:
        return _read(data)
    except _Rejected as rejected:
        return rejected.rejection


def _read(data: bytes) -> DocxText:
    if len(data) == 0:
        raise _Rejected("empty", "", "받은 바이트가 없다")
    if len(data) > MAX_BYTES:
        raise _Rejected("too_many_bytes", "", f"{len(data)} 바이트 > 상한 {MAX_BYTES}")
    # ZipFile 은 여는 자리에서 가운데 목록 전체를 ZipInfo 로 푼다 — 항목 수(_declared_sizes)를 보기 전에 끝의 EOCD 로
    # 가운데 목록 크기·zip64 를 거른다(밴드 TRS2, MARC-ISSUE-385. page_tags 와 같은 검사).
    match central_directory_refusal(data):
        case "too_many_entries":
            raise _Rejected("too_many_entries", "", f"가운데 목록이 {MAX_CENTRAL_DIRECTORY:,} 바이트를 넘거나 zip64 다")
        case "unreadable":
            raise _Rejected("not_a_zip", "", "BadZipFile")  # EOCD 가 없음 — ZipFile 이 냈을 그 이름
        case None:
            pass
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except _ZIP_ERRORS as error:
        raise _Rejected("not_a_zip", "", type(error).__name__) from None
    with archive:
        sizes = _declared_sizes(archive)
        _check_entries(archive, sizes)
    document, body = _open_document(data)
    _check_tables(body)
    try:
        return _structured_text(document, body)
    except _DOCUMENT_ERRORS as error:
        raise _Rejected("unreadable_document", "", type(error).__name__) from None


# ── zip ──────────────────────────────────────────────────────────────────


def _declared_sizes(archive: zipfile.ZipFile) -> dict[str, int]:
    """항목 이름 → 선언된(풀린) 크기. 아무것도 풀지 않는다."""
    entries = archive.infolist()
    if len(entries) > MAX_ENTRIES:
        raise _Rejected("too_many_entries", "", f"항목 {len(entries)} > 상한 {MAX_ENTRIES}")
    sizes: dict[str, int] = {}
    for entry in entries:
        if entry.filename in sizes:
            # 같은 이름이 둘이면 zipfile 은 조용히 뒤의 것을 준다. 무엇을 읽었는지 말할 수 없으므로 거절한다.
            raise _Rejected("duplicate_entry", entry.filename, "같은 이름의 항목이 둘 이상이다")
        if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise _Rejected("unsupported_compression", entry.filename, f"압축 방식 {entry.compress_type}")
        if entry.flag_bits & 0x1:
            raise _Rejected("encrypted_entry", entry.filename, "암호가 걸린 항목이다")
        if entry.file_size > MAX_ENTRY_BYTES:
            raise _Rejected(
                "entry_too_large", entry.filename, f"선언된 크기 {entry.file_size} > 상한 {MAX_ENTRY_BYTES}"
            )
        sizes[entry.filename] = entry.file_size
    total = sum(sizes.values())
    if total > MAX_DECLARED_BYTES:
        raise _Rejected("declared_entries_too_large", "", f"선언된 크기 합 {total} > 상한 {MAX_DECLARED_BYTES}")
    return sizes


def _read_entry(archive: zipfile.ZipFile, sizes: Mapping[str, int], name: str) -> bytes:
    try:
        # `archive.read(name)` 을 쓰지 않는다: 선언된 크기 + 1 바이트까지만 풀어 달라고 하고, 길이가 다르면 거절한다.
        with archive.open(name) as stream:
            data = stream.read(sizes[name] + 1)
    except _ZIP_ERRORS as error:
        raise _Rejected("unreadable_entry", name, type(error).__name__) from None
    if len(data) != sizes[name]:
        raise _Rejected("unreadable_entry", name, "풀린 크기가 선언된 크기와 다르다")
    return data


def _check_entries(archive: zipfile.ZipFile, sizes: Mapping[str, int]) -> None:
    """모든 항목을 하나씩 풀어 보고(선언 + 1), XML 꼴이면 머리를 훑고(DOCTYPE·Strict), 파싱될 XML 합을 센다."""
    if _CONTENT_TYPES not in sizes:
        raise _Rejected("missing_entry", _CONTENT_TYPES, "zip 에 그 항목이 없다")
    defaults, overrides = _content_types(_read_entry(archive, sizes, _CONTENT_TYPES))
    parsed_total = sizes[_CONTENT_TYPES]
    for name in sizes:
        if name == _CONTENT_TYPES:
            continue
        entry = _read_entry(archive, sizes, name)
        content_types = _content_type_candidates(name, defaults, overrides)
        lowered = name.lower()
        if lowered.endswith((".xml", ".rels")) or any(c.endswith("xml") for c in content_types):
            namespace = _scan_head(entry, name)
            if namespace.startswith(_STRICT_NS):
                raise _Rejected("unreadable_document", name, f"Strict OOXML 이름 공간({namespace})은 읽지 못한다")
        if lowered.endswith(".rels") or not content_types.isdisjoint(PARSED_CONTENT_TYPES):
            parsed_total += sizes[name]
    if parsed_total > MAX_XML_BYTES:
        raise _Rejected("xml_too_large", "", f"파싱될 XML 합 {parsed_total:,} 바이트 > 상한 {MAX_XML_BYTES:,}")


def _content_type_of(name: str, defaults: Mapping[str, str], overrides: Mapping[str, str]) -> str | None:
    """python-docx `_ContentTypeMap.__getitem__` 꼴: Override(파트 이름, 대소문자 무시) 먼저, 그다음 Default(확장자).
    확장자는 python-docx 와 같은 함수 `PackURI.ext`(= `posixpath.splitext` — 앞 점만 있는 `.foo` 는 확장자 없음 `""`).
    손으로 뽑으면 갈린다(가지 리뷰 B1 — `rsplit(".")` 는 `word/.foo` 에서 `foo` 를 내 `Default Extension=""` 인 본문을
    셈·DOCTYPE 훑기 밖으로 빼먹었다)."""
    partname = f"/{name}".lower()
    if partname in overrides:
        return overrides[partname]
    return defaults.get(PackURI(partname).ext)


def _content_type_candidates(name: str, defaults: Mapping[str, str], overrides: Mapping[str, str]) -> frozenset[str]:
    """겹친 방어(가지 리뷰 B1): python-docx 와 같은 꼴(`_content_type_of`)과 마지막 점 뒤를 확장자로 본 꼴 — 둘 중
    어느 쪽으로든 xml 꼴이거나 파싱되는 꼴이면 훑기·셈 대상이다. 갈래가 python-docx 판에 따라 달라져도 좁아지지 않게."""
    partname = f"/{name}".lower()
    base = partname.rsplit("/", 1)[-1]
    by_last_dot = defaults.get(base.rsplit(".", 1)[-1] if "." in base else "")
    return frozenset(c for c in (_content_type_of(name, defaults, overrides), by_last_dot) if c is not None)


# ── XML(expat — 트리를 짓지 않는다) ──────────────────────────────────────


def _parser(where: str) -> xml.parsers.expat.XMLParserType:
    parser = xml.parsers.expat.ParserCreate(namespace_separator=" ")

    def on_doctype(name: str, system_id: str | None, public_id: str | None, has_internal_subset: bool) -> None:
        raise _Rejected("doctype", where, f"DOCTYPE 선언({name})이 있다")

    parser.StartDoctypeDeclHandler = on_doctype
    return parser


def _feed(parser: xml.parsers.expat.XMLParserType, data: bytes, where: str) -> None:
    try:
        for start in range(0, len(data), _CHUNK):
            parser.Parse(data[start : start + _CHUNK], False)
        parser.Parse(b"", True)
    except xml.parsers.expat.ExpatError as error:
        raise _Rejected("broken_xml", where, f"ExpatError: {error}") from None
    except LookupError as error:  # XML 선언의 encoding 을 expat·codecs 가 모른다(가지 리뷰 poc3 — 밖으로 샜다)
        raise _Rejected("broken_xml", where, f"LookupError: {error}") from None


def _scan_head(data: bytes, where: str) -> str:
    """DOCTYPE 이면 거절하고, 아니면 뿌리 요소의 이름 공간을 돌려준다(뿌리 요소에서 멈춘다)."""
    parser = _parser(where)
    root: list[str] = []

    def on_start(name: str, attributes: dict[str, str]) -> None:
        root.append(name.split(" ", 1)[0] if " " in name else "")
        raise _RootSeen

    parser.StartElementHandler = on_start
    try:
        _feed(parser, data, where)
    except _RootSeen:
        return root[0]
    raise _Rejected("broken_xml", where, "뿌리 요소가 없다")


def _content_types(data: bytes) -> tuple[dict[str, str], dict[str, str]]:
    """`[Content_Types].xml` → (확장자 → 꼴, 파트 이름 → 꼴), 키는 소문자. DOCTYPE 이면 먼저 거절.

    python-docx 와 같은 지도를 짓는다(`opc/oxml.py` `CT_Types.defaults`·`.overrides` = 뿌리 직속 `ct:Default`·
    `ct:Override` 의 findall, `opc/pkgreader.py:108-117`): 뿌리는 `ct:Types`, 받는 것은 **뿌리 직속 자식만**(더 깊이
    숨긴 Override 로 지도를 갈라 XML 셈·DOCTYPE 대상을 빗나가게 하지 못하게), 같은 키는 뒤의 것이 이긴다. 필수 속성이
    빠진 항목은 python-docx 가 못 읽으므로 거절한다."""
    parser = _parser(_CONTENT_TYPES)
    defaults: dict[str, str] = {}
    overrides: dict[str, str] = {}
    depth = [0]
    required = {"Default": ("Extension", "ContentType"), "Override": ("PartName", "ContentType")}

    def on_start(name: str, attributes: dict[str, str]) -> None:
        depth[0] += 1
        if depth[0] == 1 and name != f"{_CT_NS} Types":
            raise _Rejected("unreadable_document", _CONTENT_TYPES, f"뿌리 요소가 Types 가 아니다({name})")
        namespace, _, local = name.rpartition(" ")
        if depth[0] != 2 or namespace != _CT_NS or local not in required:
            return
        if any(key not in attributes for key in required[local]):
            raise _Rejected("unreadable_document", _CONTENT_TYPES, f"{local} 에 필수 속성이 없다")
        if local == "Default":
            defaults[attributes["Extension"].lower()] = attributes["ContentType"]
        else:
            overrides[attributes["PartName"].lower()] = attributes["ContentType"]

    def on_end(name: str) -> None:
        depth[0] -= 1

    parser.StartElementHandler = on_start
    parser.EndElementHandler = on_end
    _feed(parser, data, _CONTENT_TYPES)
    return defaults, overrides


# ── python-docx ──────────────────────────────────────────────────────────


def _open_document(data: bytes) -> tuple[Document, CT_Body]:
    """`docx.Document(stream)`(api.py:28-30)을 두 걸음으로: 본 문서 꼴이 Word 가 아니면 갈래로."""
    try:
        part = Package.open(io.BytesIO(data)).main_document_part
        if part.content_type != CT.WML_DOCUMENT_MAIN or not isinstance(part, DocumentPart):
            raise _Rejected("not_a_word_document", part.partname, f"본 문서 꼴 {part.content_type}")
        document = part.document
        # CT_Document.body 는 lxml 위의 서술자라 pyright 가 꼴을 모른다(ZeroOrOne — 없으면 None).
        body = cast("CT_Body | None", document.element.body)
    except _DOCUMENT_ERRORS as error:
        raise _Rejected("unreadable_document", "", type(error).__name__) from None
    if document.element.tag != f"{{{_W_NS}}}document" or body is None:
        raise _Rejected("unreadable_document", "", "본 문서에 w:document·w:body 가 없다")
    return document, body


def _check_tables(body: CT_Body) -> None:
    """글을 뽑기 전에 몸 직속 표의 크기(행 폭·칸 수)와 세로 병합 되짚기 수를 센다(요소 API 만)."""
    cells = 0
    steps = 0
    try:
        tables = [child for child in _children(body) if isinstance(child, CT_Tbl)]
        for index, tbl in enumerate(tables, start=1):
            where = f"표 {index}"
            depth_above: dict[int, int] = {}
            for tr in tbl.tr_lst:
                before, after = tr.grid_before, tr.grid_after
                if before < 0 or after < 0:
                    raise _Rejected("table_too_large", where, f"gridBefore {before}·gridAfter {after} 가 음수다")
                offset = before
                depth_here: dict[int, int] = {}
                for tc in tr.tc_lst:
                    span = tc.grid_span
                    if span < 1:
                        raise _Rejected("table_too_large", where, f"gridSpan {span} < 1")
                    if tc.vMerge == "continue":
                        depth = depth_above.get(offset, 0) + 1
                        steps += depth
                        depth_here[offset] = depth
                    offset += span
                width = offset + after
                if width > MAX_GRID_COLS:
                    raise _Rejected("table_too_large", where, f"행 폭 {width:,} > 상한 {MAX_GRID_COLS}")
                cells += width
                if cells > MAX_TABLE_CELLS:
                    raise _Rejected("table_too_large", where, f"표 칸 합 {cells:,} > 상한 {MAX_TABLE_CELLS:,}")
                if steps > MAX_VMERGE_STEPS:
                    raise _Rejected(
                        "vertical_merge_too_deep", where, f"세로 병합 되짚기 {steps:,} > 상한 {MAX_VMERGE_STEPS:,}"
                    )
                depth_above = depth_here
    except _DOCUMENT_ERRORS as error:
        raise _Rejected("unreadable_document", "", type(error).__name__) from None


def _children(body: CT_Body) -> list[object]:
    return list(body.iterchildren())  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType, reportUnknownArgumentType]


def _structured_text(document: Document, body: CT_Body) -> DocxText:
    """셀 7 의 `docx_to_structured_txt` 글 몫(R/241-270) — 정규화 전에서 멈춘다(③)."""
    lines: list[str] = []
    skipped: dict[str, int] = {}
    for child in _children(body):
        if isinstance(child, CT_P):
            txt = Paragraph(child, document).text.rstrip()
            lines.append(txt if txt else "")
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            md_lines = table_rows_to_markdown([[cell.text for cell in row.cells] for row in table.rows])
            if not md_lines:
                continue
            # 직전 줄이 [MARKDOWN_TABLE]이 아니면 자동 삽입(R/259-260)
            if not lines or lines[-1].strip() != "[MARKDOWN_TABLE]":
                lines.append("[MARKDOWN_TABLE]")
            lines.extend(md_lines)
            lines.append("")
        else:
            tag = _tag_name(child)
            if tag is not None and tag != "sectPr":
                skipped[tag] = skipped.get(tag, 0) + 1
    return DocxText(text="\n".join(lines), skipped=MappingProxyType(skipped))


def _tag_name(child: object) -> str | None:
    """몸 직속 자식의 태그 — w 이름 공간이면 지역 이름(`sdt`), 아니면 `{ns}이름`. 요소가 아니면(주석·PI) None."""
    tag = getattr(child, "tag", None)
    if not isinstance(tag, str):
        return None
    prefix = f"{{{_W_NS}}}"
    return tag[len(prefix) :] if tag.startswith(prefix) else tag
