"""가치사슬 엑셀 시험의 도움(밴드 IRW2): 지어낸 xlsx 를 메모리에서 짓고(openpyxl), 항목을 갈아 끼워 공격 파일을 짓는다.
파일로 쓰지 않는다. 글은 전부 지어낸 것이다(「가상부문」 꼴).

★ 출처: translation/tests/tools/glossary_support.py(밴드 TR3a)를 옮겨 적은 것이다(import 0 — 모듈끼리 의존 0, 발주서
Q1). `entries`·`rezip`·`with_doctype`·`laughs`·`deep_sheet`·`moved` 는 글자째, `book`·`far_row_sheet` 는 열 다섯·
「value chain」 시트에 맞춰 고쳤고, `template_like`·`with_merges` 는 새것이다(마크스폰 템플릿 꼴 — 발주서 Q4)."""

import io
import zipfile
from collections.abc import Mapping, Sequence

from openpyxl import Workbook

SHEET = "xl/worksheets/sheet1.xml"
STRINGS = "xl/sharedStrings.xml"
CONTENT_TYPES = "[Content_Types].xml"
HEADER = ("사업 부문", "사업 내용", "밸류체인", "이해관계자", "관련 비즈니스 활동")
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def synthetic_rows(n: int, *, chars: Sequence[int] = (8, 12, 4, 8, 12)) -> list[tuple[str, str, str, str, str]]:
    """지어낸 행 n 개(칸마다 chars 자 — 실제 가치사슬이 아니다)."""
    seeds = ("가상부문", "가상사업내용", "업스트림", "가상이해관계자", "가상활동")
    return [
        tuple(f"{seed}{i:03d}".ljust(width, "가")[:width] for seed, width in zip(seeds, chars, strict=True))  # pyright: ignore[reportReturnType]
        for i in range(n)
    ]


def book(rows: Sequence[Sequence[object]], *, header: Sequence[object] | None = HEADER, sheets: int = 1) -> bytes:
    """첫 시트(A 열부터)에 header 행(None 이면 없음)과 rows 를 적은 xlsx 바이트. 다른 시트는 뒤에 붙는다."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    if header is not None:
        sheet.append(list(header))
    for row in rows:
        sheet.append(list(row))
    for n in range(1, sheets):
        workbook.create_sheet(f"다른시트{n}").append(list(HEADER))
        workbook[f"다른시트{n}"].append(["다른", "다른", "다른", "다른", "다른"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def table(rows: Sequence[tuple[str, str, str, str, str]]) -> bytes:
    return book([list(r) for r in rows])


def template_like(
    data_rows: Sequence[Sequence[object]] | None = None,
    *,
    hidden_value_chain: bool = False,
    value_chain_title: str = "0. Value Chain 파악",
) -> bytes:
    """마크스폰 템플릿 꼴(감독 실측 10-27 의 글 설명)을 지어낸 내용으로: 시트 셋(「목차」·「방법론」·
    value_chain_title) · 2행 제목 · 4행 B4:F4 병합 안내 · 5행 B~F 머리 ·
    6~9행 데이터(B6:B9·C6:C9 세로 병합) · 10~16행 빈 자리(B·C 병합만).
    data_rows 를 주면 6행부터 그것을 B 열부터 적고 병합은 걸지 않는다."""
    workbook = Workbook()
    first = workbook.active
    assert first is not None
    first.title = "목차"
    first["A1"] = "가상 목차"
    workbook.create_sheet("방법론")["A1"] = "가상 방법론"
    sheet = workbook.create_sheet(value_chain_title)
    if hidden_value_chain:
        sheet.sheet_state = "hidden"
    sheet["B2"] = "가상 가치사슬 파악"
    sheet.merge_cells("B4:F4")
    sheet["B4"] = "가상 안내 — 아래 표를 채워 주세요"
    for column, name in enumerate(HEADER, start=2):
        sheet.cell(5, column, name)
    if data_rows is None:
        sheet.merge_cells("B6:B9")
        sheet.merge_cells("C6:C9")
        sheet["B6"] = "ex.) 가상건설부문"
        sheet["C6"] = "가상 시공 사업"
        for row, (stage, stakeholder, activity) in enumerate(
            [
                ("업스트림", "가상협력사", "자재 조달"),
                ("자체운영", "가상임직원", "현장 시공"),
                ("자체운영", "가상지역사회", "현장 안전 관리"),
                ("다운스트림", "가상고객", "준공 후 유지보수"),
            ],
            start=6,
        ):
            sheet.cell(row, 4, stage)
            sheet.cell(row, 5, stakeholder)
            sheet.cell(row, 6, activity)
        for row in range(10, 17, 2):
            sheet.merge_cells(f"B{row}:B{row + 1}")
            sheet.merge_cells(f"C{row}:C{row + 1}")
    else:
        for row, values in enumerate(data_rows, start=6):
            for column, value in enumerate(values, start=2):
                sheet.cell(row, column, value)
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


def with_merges(data: bytes, refs: Sequence[str], *, sheet: str = SHEET) -> bytes:
    """시트 XML 의 `</sheetData>` 뒤에 `<mergeCells>` 를 끼운다(openpyxl 이 짓지 않는 꼴 — 겹침·많음)."""
    xml = entries(data)[sheet]
    cells = "".join(f'<mergeCell ref="{ref}"/>' for ref in refs)
    merged = xml.replace(b"</sheetData>", f'</sheetData><mergeCells count="{len(refs)}">{cells}</mergeCells>'.encode())
    assert merged != xml
    return rezip(data, replace={sheet: merged})


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
    """A1~E1 머리와 row 행의 밸류체인 칸(C) 하나만 있는 워크시트(그 사이 빈 행 — inline 글)."""
    head = "".join(
        f'<c r="{column}1" t="inlineStr"><is><t>{name}</t></is></c>'
        for column, name in zip("ABCDE", HEADER, strict=True)
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{NS}"><sheetData>'
        f'<row r="1">{head}</row>'
        f'<row r="{row}"><c r="C{row}" t="inlineStr"><is><t>업스트림</t></is></c></row>'
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
