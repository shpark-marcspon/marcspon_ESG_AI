"""EDK 인벤토리 엑셀 시험의 도움(밴드 DVX1): 지어낸 xlsx 를 메모리에서 짓고(openpyxl), 항목을 갈아 끼워 공격 파일을
짓는다. 파일로 쓰지 않는다. 기업·값은 전부 지어낸 것이다(「가상」 꼴).

★ 공격 파일 도움(entries·rezip·with_doctype·laughs·deep_sheet·moved)은 translation/tests/tools/glossary_support.py(밴드
TR3a)를 옮겨 적은 것이다(import 0 — 모듈끼리 의존 0). 바꾼 것은 지은 파일의 꼴(EDK 머리 14열)과 far_row_sheet 의
머리뿐."""

import io
import zipfile
from collections.abc import Mapping, Sequence
from typing import Final

from openpyxl import Workbook

SHEET = "xl/worksheets/sheet1.xml"
STRINGS = "xl/sharedStrings.xml"
CONTENT_TYPES = "[Content_Types].xml"
NS: Final = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

YEARS: Final = ("2022", "2023", "2024")


def header(years: Sequence[str] = YEARS) -> list[str]:
    """지금 양식의 머리 14열(연도 열 셋이면) — 도구의 header_row 와 따로 적는다(시험이 도구를 베끼지 않게)."""
    head = ["ID", "테마", "항목", "대분류", "중분류", "소분류", "입력 방식", "단위"]
    return [*head, *(f"{y}년" for y in years), "메모", "공시", "핵심데이터"]


def row(
    id_: object,
    theme: object,
    name: object,
    values: Sequence[object],
    *,
    key: object = "Y",
    method: object = "숫자",
    unit: object = "tCO2eq",
    memo: object = None,
    disclosure: object = "가상 공시",
) -> list[object]:
    """header(연도 len(values)) 차례의 한 행. 분류 셋은 지어낸 고정 글."""
    return [id_, theme, name, "가상대분류", "가상중분류", "가상소분류", method, unit, *values, memo, disclosure, key]


def book(
    rows: Sequence[Sequence[object]],
    *,
    head: Sequence[object] | None = None,
    sheets: int = 1,
    title: str = "인벤토리 데이터",
) -> bytes:
    """첫 시트에 head 행(None 이면 header())과 rows 를 적은 xlsx 바이트. head=() 면 머리 행 없음."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = title
    first = header() if head is None else list(head)
    if first:
        sheet.append(first)
    for line in rows:
        sheet.append(list(line))
    for n in range(1, sheets):
        workbook.create_sheet(f"다른시트{n}").append(["가상", "virtual"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


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
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression) as archive:
        for name, content in items.items():
            archive.writestr(name, content)
    return out.getvalue()


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


def _column(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def far_row_sheet(row_number: int) -> bytes:
    """1행 EDK 머리(inline 글)와 row_number 행의 A 칸(ID 수) 하나만 있는 워크시트(그 사이 빈 행). 그 행은 테마가 비어
    no_theme 이다 — 훑기가 거기까지 닿았다는 표지."""
    cells = "".join(f'<c r="{_column(i)}1" t="inlineStr"><is><t>{name}</t></is></c>' for i, name in enumerate(header()))
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{NS}"><sheetData>'
        f'<row r="1">{cells}</row>'
        f'<row r="{row_number}"><c r="A{row_number}"><v>1</v></c></row>'
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
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, part in items.items():
            archive.writestr(name, part)
    return out.getvalue()
