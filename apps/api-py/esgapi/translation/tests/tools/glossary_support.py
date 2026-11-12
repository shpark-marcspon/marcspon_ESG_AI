"""용어집 엑셀 시험의 도움(밴드 TR3a): 지어낸 xlsx 를 메모리에서 짓고(openpyxl), 항목을 갈아 끼워 공격 파일을 짓는다.
파일로 쓰지 않는다. 글은 전부 지어낸 것이다(「가상용어」 꼴).

지은 바이트는 벽시계를 싣지 않는다(밴드 TRS4, MARC-ISSUE-420): openpyxl 이 적는 문서 속성의 두 시각과 zip 항목 시각을
고정한다 — 두 시각이 다른 초에 걸리면 표본이 몇 바이트 커져 1MiB 둘레 시험이 흔들렸다."""

import io
import re
import zipfile
from collections.abc import Mapping, Sequence

from openpyxl import Workbook

SHEET = "xl/worksheets/sheet1.xml"
STRINGS = "xl/sharedStrings.xml"
CONTENT_TYPES = "[Content_Types].xml"
CORE = "docProps/core.xml"
FIXED_DATE = (1980, 1, 1, 0, 0, 0)
FIXED_STAMP = b"1980-01-01T00:00:00Z"


def synthetic_pairs(n: int, *, ko_chars: int = 10, en_chars: int = 30) -> list[tuple[str, str]]:
    """지어낸 짝 n 개(국문 ko_chars 자·영문 en_chars 자 — 실제 용어집이 아니다)."""
    return [
        (f"가상용어{i:04d}".ljust(ko_chars, "가")[:ko_chars], f"Virtual Term {i:04d}".ljust(en_chars, "x")[:en_chars])
        for i in range(n)
    ]


def book(
    rows: Sequence[Sequence[object]], *, header: Sequence[object] | None = ("한국어", "영문"), sheets: int = 1
) -> bytes:
    """첫 시트에 header 행(None 이면 없음)과 rows 를 적은 xlsx 바이트."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    if header is not None:
        sheet.append(list(header))
    for row in rows:
        sheet.append(list(row))
    for n in range(1, sheets):
        workbook.create_sheet(f"다른시트{n}").append(["가상", "virtual"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    items = entries(buffer.getvalue())
    items[CORE] = _fixed_core(items[CORE])
    return _pack(items)


def _fixed_core(content: bytes) -> bytes:
    return re.sub(
        rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)",
        lambda m: m.group(1) + FIXED_STAMP + m.group(2),
        content,
    )


def _pack(items: Mapping[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    """항목을 차례 그대로 싼다. zip 머리 시각은 FIXED_DATE(`writestr(이름, …)` 는 지금 시각을 적는다)."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression) as archive:
        for name, content in items.items():
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = compression
            archive.writestr(info, content)
    return out.getvalue()


def glossary(pairs: Sequence[tuple[str, str]]) -> bytes:
    return book([list(p) for p in pairs])


def entries(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {info.filename: archive.read(info.filename) for info in archive.infolist()}


def rezip(
    data: bytes,
    *,
    replace: Mapping[str, bytes] | None = None,
    add: Mapping[str, bytes] | None = None,
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    """항목을 갈아 끼우거나 더해 다시 싼다(차례 그대로, 더한 것은 끝에)."""
    items = entries(data)
    items.update(replace or {})
    items.update(add or {})
    return _pack(items, compression)


def with_doctype(xml: bytes) -> bytes:
    """XML 선언 뒤에 DOCTYPE(내부 부분 집합 — 엔티티 하나)을 끼운다."""
    head, sep, rest = xml.partition(b"?>")
    doctype = b'<!DOCTYPE x [<!ENTITY e "virtual">]>'
    return head + sep + doctype + rest if sep else doctype + xml


def laughs(levels: int = 9) -> bytes:
    """엔티티 부풀리기(10^levels 배) 공유 문자열 파트."""
    lines = ['<!ENTITY l0 "lol">']
    lines += [f'<!ENTITY l{i} "{("&l" + str(i - 1) + ";") * 10}">' for i in range(1, levels + 1)]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE sst [' + "".join(lines) + "]>"
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1">'
        f"<si><t>&l{levels};</t></si></sst>"
    ).encode()


def deep_sheet(depth: int) -> bytes:
    """뿌리 아래 depth 겹 중첩(DOCTYPE 없음) 워크시트."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{ns}"><sheetData>'.encode()
        + b"<x>" * depth
        + b"</x>" * depth
        + b"</sheetData></worksheet>"
    )


def far_row_sheet(row: int) -> bytes:
    """A1·B1 머리와 row 행의 칸 하나만 있는 워크시트(그 사이 빈 행 — inline 글)."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{ns}"><sheetData>'
        '<row r="1"><c r="A1" t="inlineStr"><is><t>한국어</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>영문</t></is></c></row>'
        f'<row r="{row}"><c r="A{row}" t="inlineStr"><is><t>가상</t></is></c></row>'
        "</sheetData></worksheet>"
    ).encode()


WORKBOOK_RELS = "xl/_rels/workbook.xml.rels"
IMAGE_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


def moved(data: bytes, old: str, new: str, *, content: bytes | None = None, rel_type: str | None = None) -> bytes:
    """파트 old 를 이름 new 로 옮긴다: 워크북 rels 의 Target 을 고치고 [Content_Types] 의 그 Override 를 지운다(검증 B1
    의 꼴). content 를 주면 그 바이트로, rel_type 을 주면 그 관계의 Type 을 갈아 끼운다."""
    items = entries(data)
    body = items.pop(old) if content is None else (items.pop(old), content)[1]
    rels = items[WORKBOOK_RELS].decode()
    relative = old.removeprefix("xl/")
    assert f'Target="{relative}"' in rels or f'Target="/{old}"' in rels, old
    rels = rels.replace(f'Target="{relative}"', f'Target="{new.removeprefix("xl/")}"').replace(
        f'Target="/{old}"', f'Target="/{new}"'
    )
    if rel_type is not None:
        relative_new = f'Target="{new.removeprefix("xl/")}"'
        start = rels.index(relative_new) if relative_new in rels else rels.index(f'Target="/{new}"')
        head = rels.rfind("<Relationship ", 0, start)
        end = rels.index("/>", start)
        element = rels[head:end]
        typed = element.split('Type="', 1)
        element = typed[0] + f'Type="{rel_type}"' + typed[1].split('"', 1)[1]
        rels = rels[:head] + element + rels[end:]
    items[WORKBOOK_RELS] = rels.encode()
    types = items[CONTENT_TYPES].decode()
    head = types.find(f'PartName="/{old}"')
    if head != -1:
        start = types.rfind("<Override", 0, head)
        types = types[:start] + types[types.index("/>", head) + 2 :]
    items[CONTENT_TYPES] = types.encode()
    items[new] = body
    return _pack(items)
