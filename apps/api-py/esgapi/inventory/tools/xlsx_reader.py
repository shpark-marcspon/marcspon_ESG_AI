"""xlsx 바이트 → 읽힌 표(`tools/scope3_sheets/grid.py` 의 `Workbook`). **xlsx 를 여는 것은 이 파일뿐이다.**

표준 라이브러리(`zipfile` + `xml.etree.ElementTree`)로 읽는다. 나중에 다른 읽개(openpyxl 등)로 바꿀 때
이 파일만 바뀌게, zip·XML 을 아는 코드는 여기에 가둔다. 디스크에 쓰지 않고 풀어 놓지도 않는다(메모리의 바이트만).

`read_workbook` 은 어떤 바이트를 받아도 예외를 내지 않는다: 읽히면 `Workbook`, 아니면 `ReaderProblem`(갈래).

★ 무효 조건(이 읽개가 잰 것과 안 잰 것):
- 잰 것은 **Excel 이 저장한 두 파일**(2026-10-13 에 받은 계수 책과 입력 템플릿)과 **openpyxl 3.1.5·pandas `to_excel`
  저장 꼴**(절대 Target·inlineStr·빈 수식 값·참거짓 칸 — S3C-r1)이다. 다른 도구(한글·LibreOffice·구글 시트)가 저장한
  xlsx 는 재지 않았다.
- **서식을 읽지 않는다**(styles.xml 을 열지 않는다). 그래서 날짜·백분율 칸을 못 가른다: 날짜 칸은 수로 읽힌다.
- 여는 항목은 `xl/workbook.xml` · `xl/_rels/workbook.xml.rels` · `xl/sharedStrings.xml` 과
  관계가 가리키는 워크시트뿐이다.
  테마·calcChain·그림·확장 목록(extLst)의 유효성은 읽지 않는다. 숨은 시트를 가리지 않는다.
- `inlineStr` 칸은 공유 문자열과 같은 규칙으로 잇는다(`<t>`·`<r>/<t>`, `<rPh>` 뺌, `<is>` 가 없으면 칸 없음). 인라인
  글자의 길이에는 공유 문자열처럼 상한이 없다(칸 수는 `MAX_CELLS` 가 센다).
- 참거짓(`t="b"`)은 **엑셀 표시 글자 `TRUE`/`FALSE` 로** 읽는다(`<v>` 가 정확히 `1`/`0` 일 때만. openpyxl·pandas 는
  bool 로 읽는다 — grid 에 참거짓 칸이 없다).
- `t="e"` · `t="d"` · 배열 수식은 **파일째 거절**한다(잰 파일에 0건이었다). 채워진 템플릿에는 `#N/A` 가 올 수 있다 —
  Scope 1·2 올리기(S12b-2)는 파일째 거절 그대로 두고 글에 칸 주소만 싣는다(`tools/scope12_upload.py`).
- 관계의 Target 은 `xl/` 아래 상대 경로와, 앞 `/` 하나를 떼면 `xl/` 로 시작하는 절대 part 이름(openpyxl 의 꼴)만
  받는다. 그 밖의 절대 꼴(`/docProps/…`·`//xl/…`)·`..`·역슬래시·`:`·바깥은 거절한다.
- zip 항목은 STORED·DEFLATED 만 받고, 항목마다 선언된 크기 + 1 바이트까지만 푼다(선언을 속인 zip 의 방어).
  압축이 큰 XML 은 항목마다 깊이(`MAX_XML_DEPTH`)와 요소 수(`MAX_XML_ELEMENTS`)로, 병합은 시트마다
  `MAX_MERGES` 로 막는다(S12b-2 — 잰 것: 상한 전에 8.8 KB 의 깊은 XML 이 379 MiB, 8.7 KB 의 평평한 XML 이 230 MiB).
  유효성·정의된 이름의 수는 요소 수 상한 안에서만 늘 수 있다.
- 상한의 값은 어림이다(근거는 두 파일의 크기: 0.10·0.11 MB, 항목 21·33, 칸 3,829·1,937).
  새 상한 셋은 Excel 이 저장한 파일을 재서 골랐다: 깊이 5 · 항목 하나의 요소 102,477 · 시트 하나의 병합 30.
  요소 수 상한은 칸 상한이 먼저 답하도록 칸 하나의 c·v·f 셋에 줄까지 든 값보다 크게 둔다.
- XML 의 방어: DOCTYPE 이 있으면 거절한다(파서의 갈고리. 바이트 검색이 아니므로 UTF-16 으로 적혀도 걸린다).
  엔티티 부풀리기는 expat 이 막는다. 이미지(리눅스) 안의 expat 판은 재지 않았다.

수의 글자: float 는 표기를 풀 때 한 번만 쓴다(`repr(float(글자))` = 가장 짧은 왕복 표기). 셈하지 않는다.
"""

import decimal
import io
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass
from typing import Final, Literal

from esgapi.core.calc.decimal import EXTERNAL_MAX_LENGTH, is_decimal_string
from esgapi.inventory.tools.scope3_sheets.grid import (
    AddressProblem,
    Cell,
    DefinedName,
    FormulaCell,
    NumberCell,
    SharedFormula,
    Sheet,
    TextCell,
    Validation,
    Workbook,
    format_address,
    parse_address,
)

# ── 상한(전부 어림. 머리말의 무효 조건) ──
MAX_BYTES: Final = 10 * 1024 * 1024  # 받은 바이트(기본). 부르는 쪽이 `read_workbook(max_bytes=)` 로 바꿔 넘길 수 있다
GHG_UPLOAD_MAX_BYTES: Final = 20 * 1024 * 1024
"""온실가스 엑셀 올리기의 상한(결정 MARC-ENT-593 — 20MB, 웹 `MAX_UPLOAD_BYTES`·`ENTRY_UPLOAD_MAX_BYTES` 와 같은 셈).
inventory 의 자리는 이 상수 하나다: Scope 1·2 올리기 경로(`service/apis/scope12_excel.py`)의 본문 상한과 Scope 1·2
읽기(`tools/scope12_upload.py`)·Scope 3 템플릿 읽기(`flows/scope3_colab_157.py`)가 넘기는 `max_bytes` 가 이 값이다.
항목·칸·XML 상한(`MAX_ENTRY_BYTES`·`MAX_OPENED_BYTES`·`MAX_CELLS`·`MAX_XML_*`)은 올리지 않았다(MARC-ISSUE-586)."""
MAX_ENTRIES: Final = 200  # zip 항목 수
MAX_ENTRY_BYTES: Final = 8 * 1024 * 1024  # 항목 하나의 선언된(풀린) 크기
MAX_OPENED_BYTES: Final = 16 * 1024 * 1024  # 여는 항목의 선언된 크기 합
MAX_SHEETS: Final = 64
MAX_SHARED_STRINGS: Final = 100_000
MAX_CELLS: Final = 200_000  # 통합 문서 통째로
MAX_MERGES: Final = 20_000  # 시트 하나
MAX_XML_DEPTH: Final = 64  # 항목 하나의 요소 깊이
MAX_XML_ELEMENTS: Final = 1_000_000  # 항목 하나의 요소 수

ProblemKind = Literal[
    "empty",
    "too_many_bytes",
    "not_a_zip",
    "too_many_entries",
    "duplicate_entry",
    "entry_too_large",
    "opened_entries_too_large",
    "encrypted_entry",
    "unsupported_compression",
    "missing_entry",
    "unreadable_entry",
    "broken_xml",
    "doctype",
    "unexpected_xml",
    "too_many_sheets",
    "bad_relationship",
    "too_many_shared_strings",
    "too_many_cells",
    "too_many_merges",
    "xml_too_deep",
    "too_many_xml_elements",
    "bad_cell_address",
    "duplicate_cell",
    "unsupported_cell_type",
    "bad_shared_string",
    "bad_number",
    "unsupported_formula",
    "bad_shared_formula",
]


@dataclass(frozen=True, slots=True)
class ReaderProblem:
    kind: ProblemKind
    where: str  # zip 항목 이름, 칸이면 `항목!주소`
    detail: str


class _Rejected(Exception):
    """제어 흐름용. 밖으로 새지 않는다: read_workbook 이 갈래로 바꾼다."""

    def __init__(self, kind: ProblemKind, where: str, detail: str) -> None:
        super().__init__(kind)
        self.problem = ReaderProblem(kind, where, detail)


class _DoctypeRefusingBuilder(ET.TreeBuilder):
    """DOCTYPE 을 만나면 그 자리에서 멈춘다(엔티티 선언을 읽기 전이다). 요소의 깊이와 수도 짓는 자리에서 센다:
    나무를 다 지은 뒤에 재면 이미 메모리를 쓴 뒤다. `xml.parsers.expat` 을 따로 들이지 않고 여기서 센다."""

    def __init__(self) -> None:
        super().__init__()
        self._depth = 0
        self._elements = 0

    def doctype(self, name: str | None, pubid: str | None, system: str | None) -> None:
        raise _Rejected("doctype", "", f"DOCTYPE 선언({name})이 있다")

    def start(self, tag: str, attrs: dict[str, str], /) -> ET.Element:
        self._depth += 1
        self._elements += 1
        if self._depth > MAX_XML_DEPTH:
            raise _Rejected("xml_too_deep", "", f"요소 깊이 > 상한 {MAX_XML_DEPTH}")
        if self._elements > MAX_XML_ELEMENTS:
            raise _Rejected("too_many_xml_elements", "", f"요소 수 > 상한 {MAX_XML_ELEMENTS}")
        return super().start(tag, attrs)

    def end(self, tag: str, /) -> ET.Element:
        self._depth -= 1
        return super().end(tag)


_MAIN: Final = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_DOC_REL: Final = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL: Final = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_WORKBOOK: Final = "xl/workbook.xml"
_RELS: Final = "xl/_rels/workbook.xml.rels"
_SHARED_STRINGS: Final = "xl/sharedStrings.xml"

# 수의 글자. float() 는 `1_000`·` 12 `·`nan`·`Infinity`·전각 숫자를 받으므로 먼저 이 문법에 통째로 맞아야 한다.
_NUMBER: Final = re.compile(r"-?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?")
_INTEGER: Final = re.compile(r"-?[0-9]+")
_INDEX: Final = re.compile(r"[0-9]{1,9}")

# zipfile 이 망가진 바이트에서 낼 수 있는 것들. 하나로 뭉뚱그려 삼키지 않고 이름으로 적는다.
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


def read_workbook(data: bytes, *, max_bytes: int | None = None) -> Workbook | ReaderProblem:
    """`max_bytes` 는 받은 바이트의 상한이다. 없으면 `MAX_BYTES`(부를 때 읽는다). 다른 상한은 바꾸지 않는다."""
    try:
        return _read(data, MAX_BYTES if max_bytes is None else max_bytes)
    except _Rejected as rejected:
        return rejected.problem


def _read(data: bytes, max_bytes: int) -> Workbook:
    if len(data) == 0:
        raise _Rejected("empty", "", "받은 바이트가 없다")
    if len(data) > max_bytes:
        raise _Rejected("too_many_bytes", "", f"{len(data)} 바이트 > 상한 {max_bytes}")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except _ZIP_ERRORS as error:
        raise _Rejected("not_a_zip", "", type(error).__name__) from None
    with archive:
        sizes = _declared_sizes(archive)
        workbook_root = _parse_xml(_read_entry(archive, sizes, _WORKBOOK), _WORKBOOK, f"{_MAIN}workbook")
        sheet_refs = _sheet_refs(workbook_root)
        defined_names = _defined_names(workbook_root)
        targets = _relationship_targets(
            _parse_xml(_read_entry(archive, sizes, _RELS), _RELS, f"{_PKG_REL}Relationships")
        )
        paths: list[str] = []
        for name, relation_id in sheet_refs:
            if relation_id not in targets:
                raise _Rejected("bad_relationship", _RELS, f"시트 {name!r} 의 관계 {relation_id!r} 가 없다")
            paths.append(targets[relation_id])
        if len(set(paths)) != len(paths):
            raise _Rejected("bad_relationship", _RELS, "두 시트가 같은 항목을 가리킨다")
        # 읽기 전에 여는 항목의 선언된 크기 합을 본다. 이것만으로는 폭탄을 못 막는다(선언은 속일 수 있다):
        # 항목마다 선언된 크기 + 1 바이트까지만 푸는 `_read_entry` 와 같이 서야 방어가 된다.
        opened = [_WORKBOOK, _RELS, *([_SHARED_STRINGS] if _SHARED_STRINGS in sizes else []), *paths]
        for path in paths:
            if path not in sizes:
                raise _Rejected("missing_entry", path, "관계가 가리키는 워크시트가 zip 에 없다")
        total = sum(sizes[path] for path in opened)
        if total > MAX_OPENED_BYTES:
            raise _Rejected("opened_entries_too_large", "", f"선언된 크기 합 {total} > 상한 {MAX_OPENED_BYTES}")
        strings: tuple[str, ...] = ()
        if _SHARED_STRINGS in sizes:
            strings = _shared_strings(
                _parse_xml(_read_entry(archive, sizes, _SHARED_STRINGS), _SHARED_STRINGS, f"{_MAIN}sst")
            )
        sheets: list[Sheet] = []
        seen_cells = 0
        for (name, _), path in zip(sheet_refs, paths, strict=True):
            root = _parse_xml(_read_entry(archive, sizes, path), path, f"{_MAIN}worksheet")
            sheet, seen_cells = _sheet(name, path, root, strings, seen_cells)
            sheets.append(sheet)
    return Workbook(tuple(sheets), defined_names)


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
            # LZMA·BZIP2 등은 망가진 자료에서 여기 적지 않은 예외(lzma.LZMAError 등)를 낸다. xlsx 는 DEFLATE 를 쓴다.
            raise _Rejected("unsupported_compression", entry.filename, f"압축 방식 {entry.compress_type}")
        if entry.flag_bits & 0x1:
            raise _Rejected("encrypted_entry", entry.filename, "암호가 걸린 항목이다")
        if entry.file_size > MAX_ENTRY_BYTES:
            raise _Rejected(
                "entry_too_large", entry.filename, f"선언된 크기 {entry.file_size} > 상한 {MAX_ENTRY_BYTES}"
            )
        sizes[entry.filename] = entry.file_size
    return sizes


def _read_entry(archive: zipfile.ZipFile, sizes: dict[str, int], name: str) -> bytes:
    if name not in sizes:
        raise _Rejected("missing_entry", name, "zip 에 그 항목이 없다")
    try:
        # `archive.read(name)` 을 쓰지 않는다: 그것은 압축을 끝까지 푼 뒤에 선언된 크기로 자른다(선언을 속인 항목이
        # 메모리를 다 쓴다). 선언된 크기 + 1 바이트까지만 풀어 달라고 하고, 길이가 선언과 다르면 거절한다.
        with archive.open(name) as stream:
            data = stream.read(sizes[name] + 1)
    except _ZIP_ERRORS as error:
        raise _Rejected("unreadable_entry", name, type(error).__name__) from None
    if len(data) != sizes[name]:
        raise _Rejected("unreadable_entry", name, "풀린 크기가 선언된 크기와 다르다")
    return data


# ── XML ──────────────────────────────────────────────────────────────────


def _parse_xml(data: bytes, where: str, expected_root: str) -> ET.Element:
    """XML 을 파싱하는 자리는 여기 하나다. DOCTYPE 은 갈고리가 거절하고, 엔티티 부풀리기는 expat 이 막고,
    바깥 엔티티는 풀리지 않는다(ParseError)."""
    parser = ET.XMLParser(target=_DoctypeRefusingBuilder())  # noqa: S314 (DOCTYPE 거절 갈고리 + expat 의 부풀리기 방어)
    try:
        parser.feed(data)
        root = parser.close()
    except _Rejected as rejected:
        raise _Rejected(rejected.problem.kind, where, rejected.problem.detail) from None
    except (ET.ParseError, ValueError, LookupError) as error:
        # ParseError: 깨진 XML · 엔티티 부풀리기 · 풀리지 않는 엔티티. ValueError·LookupError: 모르는 인코딩 선언.
        raise _Rejected("broken_xml", where, type(error).__name__) from None
    if root.tag != expected_root:
        raise _Rejected("unexpected_xml", where, "뿌리 요소가 기대한 것이 아니다")
    return root


def _sheet_refs(root: ET.Element) -> list[tuple[str, str]]:
    """workbook.xml 의 차례대로 (시트 이름, 관계 id). zip 안의 차례가 아니다."""
    sheets = root.find(f"{_MAIN}sheets")
    refs: list[tuple[str, str]] = []
    if sheets is not None:
        for sheet in sheets.findall(f"{_MAIN}sheet"):
            name, relation_id = sheet.get("name"), sheet.get(f"{_DOC_REL}id")
            if name is None or relation_id is None:
                raise _Rejected("unexpected_xml", _WORKBOOK, "sheet 요소에 name 이나 r:id 가 없다")
            refs.append((name, relation_id))
    if len(refs) > MAX_SHEETS:
        raise _Rejected("too_many_sheets", _WORKBOOK, f"시트 {len(refs)} > 상한 {MAX_SHEETS}")
    if len({name for name, _ in refs}) != len(refs):
        raise _Rejected("unexpected_xml", _WORKBOOK, "같은 이름의 시트가 둘 이상이다")
    return refs


def _defined_names(root: ET.Element) -> tuple[DefinedName, ...]:
    names = root.find(f"{_MAIN}definedNames")
    found: list[DefinedName] = []
    if names is not None:
        for item in names.findall(f"{_MAIN}definedName"):
            name = item.get("name")
            if name is None:
                raise _Rejected("unexpected_xml", _WORKBOOK, "definedName 요소에 name 이 없다")
            found.append(DefinedName(name, item.text if item.text is not None else ""))
    return tuple(found)


def _relationship_targets(root: ET.Element) -> dict[str, str]:
    """관계 id → zip 항목 이름. `xl/` 아래 상대 경로, 그리고 OPC 뿌리 기준 절대 part 이름(`/xl/…` — openpyxl 이 쓰는
    꼴)은 앞 `/` 하나를 떼고 `xl/` 로 시작하며 빈 조각이 없을 때만 받는다. 글자만 다룬다(퍼센트 부호화는 풀지
    않는다)."""
    targets: dict[str, str] = {}
    for relation in root.findall(f"{_PKG_REL}Relationship"):
        relation_id, target = relation.get("Id"), relation.get("Target")
        if relation_id is None or target is None:
            raise _Rejected("bad_relationship", _RELS, "Relationship 요소에 Id 나 Target 이 없다")
        if not relation.get("Type", "").endswith("/worksheet"):
            continue  # 서식·테마·공유 문자열 등. 따라가지 않는다
        if relation.get("TargetMode") == "External":
            raise _Rejected("bad_relationship", _RELS, f"관계 {relation_id!r} 가 바깥(External)을 가리킨다")
        if "\\" in target or ".." in target.split("/") or ":" in target:
            raise _Rejected("bad_relationship", _RELS, f"관계 {relation_id!r} 의 Target 이 xl/ 아래 경로가 아니다")
        if target.startswith("/"):
            part = target[1:]
            if not part.startswith("xl/") or "" in part.split("/"):
                raise _Rejected(
                    "bad_relationship", _RELS, f"관계 {relation_id!r} 의 절대 Target 이 /xl/ 아래 part 가 아니다"
                )
            targets[relation_id] = part
        else:
            targets[relation_id] = f"xl/{target}"
    return targets


def _shared_strings(root: ET.Element) -> tuple[str, ...]:
    items = root.findall(f"{_MAIN}si")
    if len(items) > MAX_SHARED_STRINGS:
        raise _Rejected("too_many_shared_strings", _SHARED_STRINGS, f"{len(items)} > 상한 {MAX_SHARED_STRINGS}")
    return tuple(_string_item(item) for item in items)


def _string_item(item: ET.Element) -> str:
    """<t> 와 <r>/<t> 만 잇는다. 후리가나(<rPh>)의 글자는 붙이지 않는다. 앞뒤 공백은 그대로 둔다."""
    pieces: list[str] = []
    for child in item:
        if child.tag == f"{_MAIN}t":
            pieces.append(child.text if child.text is not None else "")
        elif child.tag == f"{_MAIN}r":
            for inner in child.findall(f"{_MAIN}t"):
                pieces.append(inner.text if inner.text is not None else "")
    return "".join(pieces)


# ── 시트 ─────────────────────────────────────────────────────────────────


def _sheet(name: str, path: str, root: ET.Element, strings: tuple[str, ...], seen_cells: int) -> tuple[Sheet, int]:
    cells: dict[str, Cell] = {}
    seen_addresses: set[str] = set()
    masters: dict[int, tuple[str, str]] = {}  # 묶음 번호 → (으뜸 칸 주소, ref)
    followers: list[tuple[str, int, TextCell | NumberCell | None]] = []
    data = root.find(f"{_MAIN}sheetData")
    rows = data.findall(f"{_MAIN}row") if data is not None else []
    for row in rows:
        for element in row.findall(f"{_MAIN}c"):
            seen_cells += 1
            if seen_cells > MAX_CELLS:
                raise _Rejected("too_many_cells", path, f"칸 > 상한 {MAX_CELLS}")
            address = _cell_address(element, path)
            where = f"{path}!{address}"
            if address in seen_addresses:
                raise _Rejected("duplicate_cell", where, "한 시트에 같은 주소의 칸이 둘이다")
            seen_addresses.add(address)
            cell_type = element.get("t", "n")
            if cell_type not in ("n", "s", "str", "b", "inlineStr"):
                raise _Rejected("unsupported_cell_type", where, f't="{cell_type}" 칸은 읽지 않는다')
            formula = element.find(f"{_MAIN}f")
            if cell_type == "inlineStr":
                if formula is not None:
                    raise _Rejected("unsupported_formula", where, "inlineStr 칸에 <f> 가 있다")
                if element.find(f"{_MAIN}v") is not None:
                    raise _Rejected("unexpected_xml", where, "inlineStr 칸에 <v> 가 있다")
                inline = element.find(f"{_MAIN}is")
                if inline is not None:  # <is> 가 없으면 칸 없음(openpyxl 이 None 을 쓴 꼴)
                    cells[address] = TextCell(_string_item(inline))
                continue
            value = _stored_value(element.find(f"{_MAIN}v"), cell_type, strings, where, formula is not None)
            if formula is None:
                if value is not None:
                    cells[address] = value
                continue
            formula_type = formula.get("t", "normal")
            text = formula.text if formula.text is not None and formula.text != "" else None
            if formula_type == "normal":
                if text is None:
                    raise _Rejected("unsupported_formula", where, "식 글자가 없는 수식 칸이다")
                cells[address] = FormulaCell(text, None, value)
            elif formula_type == "shared":
                index_text = formula.get("si", "")
                if _INDEX.fullmatch(index_text) is None:
                    raise _Rejected("bad_shared_formula", where, "공유 수식의 묶음 번호(si)가 수가 아니다")
                index = int(index_text)
                if text is None:
                    followers.append((address, index, value))  # 딸린 칸. 으뜸 칸이 뒤에 올 수도 있어 나중에 잇는다
                    continue
                reference = formula.get("ref")
                if reference is None or index in masters:
                    raise _Rejected("bad_shared_formula", where, "으뜸 칸에 ref 가 없거나 같은 묶음의 으뜸 칸이 둘이다")
                masters[index] = (address, reference)
                cells[address] = FormulaCell(text, SharedFormula(index, address, reference), value)
            else:
                raise _Rejected("unsupported_formula", where, f'<f t="{formula_type}"> 은 읽지 않는다')
    for address, index, value in followers:
        if index not in masters:
            raise _Rejected("bad_shared_formula", f"{path}!{address}", "딸린 칸의 으뜸 칸이 이 시트에 없다")
        master, reference = masters[index]
        # 식 글자는 싣지 않는다(None). 주소를 밀어 식을 지어내지 않는다.
        cells[address] = FormulaCell(None, SharedFormula(index, master, reference), value)
    return Sheet(name, cells, _merges(root, path), _validations(root, path)), seen_cells


def _cell_address(element: ET.Element, path: str) -> str:
    raw = element.get("r")
    if raw is None:
        raise _Rejected("bad_cell_address", path, "r 이 없는 칸이다")
    parsed = parse_address(raw)
    if isinstance(parsed, AddressProblem) or format_address(parsed) != raw:
        raise _Rejected("bad_cell_address", path, "칸의 r 이 주소의 꼴이 아니다")
    return raw


def _stored_value(
    value: ET.Element | None, cell_type: str, strings: tuple[str, ...], where: str, in_formula: bool
) -> TextCell | NumberCell | None:
    if value is None:
        return None  # 서식만 있는 빈 칸, 또는 저장된 값이 없는 수식 칸
    text = value.text if value.text is not None else ""
    if cell_type == "str":
        return TextCell(text)  # 빈 <v/> 는 빈 글자다(없음이 아니다)
    if cell_type == "b":
        if text not in ("0", "1"):
            raise _Rejected("unsupported_cell_type", where, 't="b" 칸의 값이 0·1 이 아니다')
        return TextCell("TRUE" if text == "1" else "FALSE")
    if cell_type == "n" and in_formula and text == "":
        return None  # openpyxl 이 쓴 수식 칸(셈하지 않아 값이 빔) — <v> 가 없는 칸과 같다
    if cell_type == "s":
        if _INDEX.fullmatch(text) is None or int(text) >= len(strings):
            raise _Rejected("bad_shared_string", where, "공유 문자열 번호가 정수가 아니거나 범위 밖이다")
        return TextCell(strings[int(text)])
    return _number(text, where)


def _number(text: str, where: str) -> NumberCell:
    if _NUMBER.fullmatch(text) is None:
        raise _Rejected("bad_number", where, "수의 글자가 문법에 맞지 않는다")
    if _INTEGER.fullmatch(text) is not None:
        shortest = text
    else:
        # float 는 여기 한 번뿐이다: 같은 배정밀도 수의 가장 짧은 왕복 표기를 얻는다. 셈하지 않는다.
        shortest_repr = repr(float(text))
        if shortest_repr in ("inf", "-inf", "nan"):
            raise _Rejected("bad_number", where, "배정밀도로 유한하지 않은 수다")
        shortest = format(decimal.Decimal(shortest_repr), "f")  # 지수 표기를 푼다(자릿수는 그대로)
    if len(shortest) > EXTERNAL_MAX_LENGTH or not is_decimal_string(shortest):
        raise _Rejected("bad_number", where, f"십진 표기가 {EXTERNAL_MAX_LENGTH}자를 넘거나 엄격 십진이 아니다")
    return NumberCell(text, shortest)


def _merges(root: ET.Element, path: str) -> tuple[str, ...]:
    holder = root.find(f"{_MAIN}mergeCells")
    if holder is None:
        return ()
    merges = holder.findall(f"{_MAIN}mergeCell")
    if len(merges) > MAX_MERGES:
        raise _Rejected("too_many_merges", path, f"병합 {len(merges)} > 상한 {MAX_MERGES}")
    found: list[str] = []
    for merge in merges:
        reference = merge.get("ref")
        if reference is None:
            raise _Rejected("unexpected_xml", path, "mergeCell 요소에 ref 가 없다")
        found.append(reference)
    return tuple(found)


def _validations(root: ET.Element, path: str) -> tuple[Validation, ...]:
    holder = root.find(f"{_MAIN}dataValidations")
    if holder is None:
        return ()
    found: list[Validation] = []
    for item in holder.findall(f"{_MAIN}dataValidation"):
        reference = item.get("sqref")
        if reference is None:
            raise _Rejected("unexpected_xml", path, "dataValidation 요소에 sqref 가 없다")
        first, second = item.find(f"{_MAIN}formula1"), item.find(f"{_MAIN}formula2")
        found.append(
            Validation(
                item.get("type", ""),
                reference,
                None if first is None else (first.text if first.text is not None else ""),
                None if second is None else (second.text if second.text is not None else ""),
            )
        )
    return tuple(found)
