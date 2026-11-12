# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
"""병기 txt → Word(코랩 셀 54 전부 — R/4112-4917, 함수 24 를 이름 그대로). 입구는 `render_bilingual(text)`.

코랩 셀 55(R/4920-4956)는 문체마다 병기 txt 가 있으면 이것을 부르고, 셀 67(R/6947-6951)은 자동수정 뒤 병기 글로 다시
부른다 — 결과에서 무엇을 지을지는 files.py 가 고른다. 이 파일은 글 하나 → Word 바이트 하나다.

코랩과 다른 자리(보고 「코랩과 다른 자리」 표):
- 파일 → 바이트: `output_path`·`os.remove`·`doc.save(path)`(R/4912-4914) 대신 `doc.save(BytesIO)`.
- `except Exception` → `print` 후 `False`(R/4915-4917) 대신: 코랩에서 실패가 되는 입력 둘을 python-docx 에 넘기기 전에
  알아보고(`writable` — 못 담는 글자, `require_styles` — 틀에 없는 스타일) `WordFailed` 로 낸다. 잡는 것은 그 둘과
  `PythonDocxError` 뿐 — `ValueError`·`KeyError`·그 밖의 예외·`MemoryError` 는 밖으로 나간다(우리 버그를 「Word 실패」로
  숨기지 않는다 — 감독 처분, 가지 리뷰 M2). Word 가 생기는 입력·실패가 되는 입력은 코랩과 같다(못 담는 글자의 집합이
  lxml 과 같음 — 차등 시험).
- 지역 변수 `l`(R/4603) 을 `s2` 로(ruff E741). 글은 같다.

약점 W10(코랩대로): XML 에 못 담는 제어 문자(`\\x01`·`\\x08`·`\\x1f`·`\\x00` 등) 하나가 run 글에 있으면 Word 하나가
통째로 안 생긴다(코랩은 python-docx 의 `ValueError` → `False`, 우리는 넘기기 전에 `WordFailed`).
`\\x0b`·`\\x0c` 등은 `parse_blocks` 의
`str.splitlines()`(R/4551)가 줄 끝으로 보아 줄바꿈이 된다 — 실패가 아니다.

python-docx 의 비공개 속성(`._p`·`._r`·`._element`·`._tc`·`._tbl`)은 코랩 서식을 그대로 내려고 쓴다 — 그래서 머리에
`reportPrivateUsage` 완화. `reportUnknown*` 셋은 lxml 위 요소(타입 정보 없음 — 읽개와 같은 까닭). python-docx 의
타입이 좁지 않은 세 자리(스타일 꼴·`rFonts` 의 None)는 `cast`(실행 동작 0).
python-docx 가 쓴 docx 는 zip 항목 시각이 들어가 바이트가 실행마다 다를 수 있다 — 시험은 다시 읽어 견준다.
"""

import io
import re
from typing import Any, Final, cast

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.exceptions import PythonDocxError
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.text.font import CT_Fonts
from docx.shared import Inches, Pt, RGBColor
from docx.styles.style import ParagraphStyle
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from esgapi.translation.outputs.failures import WordFailed, WordUnwritable, writable

# 잡는 것(가지 리뷰 M2 — 감독 처분을 고침, 보고에 줄마다):
#   WordUnwritable  — 넘기기 전에 알아본 실패: 못 담는 글자(W10 — lxml 이면 ValueError)·틀에 없는 스타일(KeyError 자리)
#   PythonDocxError — python-docx 자신의 오류(InvalidXmlError 등)
# 넣지 않은 것: ValueError·KeyError(미리 알아보므로 남는 것은 우리 버그), TypeError·AttributeError·IndexError,
#   RecursionError(재귀 0), lxml 의 XMLSyntaxError(쓰기에서는 파싱 0), MemoryError(OOM 은 밖으로).
_WORD_ERRORS: Final = (WordUnwritable, PythonDocxError)
STYLES: Final = ("Normal", "Table Grid")
"""셀 54 가 이름으로 부르는 스타일(R/4206 `doc.styles["Normal"]`·R/4541·R/4348 `"Table Grid"`)."""

TOP_LEVEL_BREAK_RE = re.compile(
    r"^\[(?:PAGE\s+\d+|BLOCK\s+\d+|TABLE\s+\d+|VISUAL\s+\d+|"
    r"HEADER|FOOTER|PAGE_NUMBER|QUALITY_CHECK|UNREADABLE|"
    r"POSSIBLY_MISSING|MERGE_QUALITY_CHECK)\]\s*$",
    re.IGNORECASE,
)  # R/4134

SUBTAG_ONLY_RE = re.compile(r"^\[[A-Z_]+(?:\s+\d+)?\]$")  # R/4141

BULLET_RE = re.compile(r"^(?:[-•◦▪‣*]\s+|\d+[\.\)]\s+|[A-Za-z][\.\)]\s+|[가-힣]\.\s+)")  # R/4143

BLUE = RGBColor(47, 84, 150)  # R/4147-4150
BLACK = RGBColor(0, 0, 0)
GRAY = RGBColor(102, 102, 102)
LIGHT_GRAY = RGBColor(128, 128, 128)

# 밴드 TRW13 C(sid:MARC-ISSUE-612 b — Word 에서 제목 단계가 안 보임). 코랩 셀 54 에 없는 우리 덧: BLOCK 첫 줄이
# 번호 꼴 제목이면 단계별 크기를 준다(굵게·색·간격 뒤는 그대로 — 크기와 위 간격만). 번호 꼴이 아니면 코랩대로 10.5.
# 영문 줄도 같다(번역이 번호를 그대로 두므로 — 병기 「1-1. Title (1-1. 제목)」도 같은 꼴). 번호는 한두 자리만(연도 0),
# 번호 뒤 첫 글자가 영문 소문자면 제목 아님(「2.5 million」 꼴 수치 문장), 80자를 넘으면 제목 아님(번호 목록 문장).
HEADING_MAX_LEN: Final = 80
_N: Final = r"\d{1,2}"
_ROMAN: Final = r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]"
_ROMAN_ASCII: Final = r"(?:IX|IV|V?I{1,3}|VI{0,3}|X)"  # 영문 번역이 Ⅰ 을 I 로 옮긴 꼴 — 뒤에 빈칸 필수(「I.e.」 0)
HEADING_LEVEL_RES: Final = (
    (3, re.compile(rf"^{_N}-{_N}-{_N}\.?\s+|^{_N}\.{_N}\.{_N}\.?\s+")),  # 1-1-1 · 1.1.1
    (2, re.compile(rf"^{_N}-{_N}\.?\s+|^{_N}\.{_N}\.?\s+")),  # 1-1. · 1.1
    (1, re.compile(rf"^{_N}\.\s+|^{_ROMAN}\.\s*|^{_ROMAN_ASCII}\.\s+")),  # 1. · Ⅰ. · II.
)
HEADING_SIZES: Final = {1: 14.0, 2: 12.5, 3: 11.5}
"""단계별 크기(pt). 보통 첫 줄 10.5·본문 9.5 보다 크게, 단계마다 1pt 넘게 벌림(반 포인트 정수 — 다시 읽어도 같은 값)."""
HEADING_SPACE_BEFORE: Final = {1: 6.0, 2: 4.0, 3: 2.0}


def heading_level(line: str) -> int | None:
    """번호 꼴 제목의 단계(1~3), 아니면 None. 깊은 꼴부터 본다(「1-1-1」이 「1-1」로 잡히지 않게)."""
    s = line.strip()
    if not s or len(s) > HEADING_MAX_LEN:
        return None
    for level, pattern in HEADING_LEVEL_RES:
        found = pattern.match(s)
        if found is None:
            continue
        rest = s[found.end() :]
        if not rest or rest[0].islower():
            return None
        return level
    return None


Block = dict[str, Any]


def require_styles(doc: DocumentObject, names: tuple[str, ...]) -> None:
    """(TR1b) 이름으로 부를 스타일이 틀에 다 있는가 — 없으면 python-docx 가 KeyError 를 낼 자리를 미리
    `WordUnwritable`."""
    for name in names:
        if name not in doc.styles:
            raise WordUnwritable(f"틀에 스타일 {name} 이 없다")


def word_failed(error: WordUnwritable | PythonDocxError) -> WordFailed:
    if isinstance(error, WordUnwritable):
        return WordFailed(str(error))
    return WordFailed(f"{type(error).__name__}: {error}")


def is_top_level_break(line: str) -> bool:  # R/4153
    return bool(TOP_LEVEL_BREAK_RE.match(line.strip()))


def rgb_hex(color: RGBColor) -> str:  # R/4157
    r, g, b = tuple(color)
    return f"{r:02X}{g:02X}{b:02X}"


def normalize_inline_breaks(text: str | None) -> str:  # R/4162
    if text is None:
        return ""
    return text.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")


def clear_paragraph_shading(paragraph: Paragraph) -> None:  # R/4172
    pPr = paragraph._p.get_or_add_pPr()
    for child in list(pPr):
        if child.tag == qn("w:shd"):
            pPr.remove(child)


def force_run_color(run: Run, hex_color: str) -> None:  # R/4179
    rPr = run._r.get_or_add_rPr()
    for child in list(rPr):
        if child.tag == qn("w:color"):
            rPr.remove(child)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), hex_color)
    rPr.append(color)


def apply_run_style(
    run: Run, *, size: float = 9.5, color: RGBColor = BLACK, bold: bool = False, italic: bool = False
) -> None:  # R/4189
    run.bold = bold
    run.italic = italic
    run.font.name = "Malgun Gothic"
    cast(CT_Fonts, run._element.get_or_add_rPr().rFonts).set(qn("w:eastAsia"), "Malgun Gothic")
    run.font.size = Pt(size)
    run.font.color.rgb = color
    force_run_color(run, rgb_hex(color))


def add_styled_paragraph(
    doc: DocumentObject,
    text: str = "",
    *,
    color: RGBColor = BLACK,
    size: float = 9.5,
    bold: bool = False,
    italic: bool = False,
    space_before: float = 0,
    space_after: float = 0,
    line_spacing: float = 1.05,
) -> Paragraph:  # R/4199
    p = doc.add_paragraph()
    p.style = cast(ParagraphStyle, doc.styles["Normal"])
    clear_paragraph_shading(p)
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing

    parts = normalize_inline_breaks(text).split("\n")
    for idx, part in enumerate(parts):
        run = p.add_run(writable(part))  # (TR1b) W10 을 넘기기 전에 — failures.writable
        apply_run_style(run, size=size, color=color, bold=bold, italic=italic)
        if idx < len(parts) - 1:
            run.add_break()
    return p


def set_cell_shading(cell: _Cell, fill: str) -> None:  # R/4228
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag == qn("w:shd"):
            tcPr.remove(child)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def set_table_borders(table: Table, color: str = "C9C9C9", size: str = "4") -> None:  # R/4238
    tblPr = table._tbl.tblPr
    for child in list(tblPr):
        if child.tag == qn("w:tblBorders"):
            tblPr.remove(child)

    borders = OxmlElement("w:tblBorders")
    for border_name in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        border = OxmlElement(f"w:{border_name}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), size)
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), color)
        borders.append(border)
    tblPr.append(borders)


def set_cell_margins(cell: _Cell, top: int = 60, start: int = 70, bottom: int = 60, end: int = 70) -> None:  # R/4255
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = tcPr.first_child_found_in("w:tcMar")
    if tcMar is None:
        tcMar = OxmlElement("w:tcMar")
        tcPr.append(tcMar)

    for margin_name, value in [("top", top), ("start", start), ("bottom", bottom), ("end", end)]:
        node = tcMar.find(qn(f"w:{margin_name}"))
        if node is None:
            node = OxmlElement(f"w:{margin_name}")
            tcMar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def split_md_row(row: str) -> list[str]:  # R/4271
    """Markdown pipe row를 안전하게 셀 배열로 분리."""
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip().replace("&#124;", "|") for c in row.split("|")]


def is_md_separator_row(line: str) -> bool:  # R/4281
    line = line.strip()
    if not (line.startswith("|") and line.endswith("|")):
        return False
    cells = split_md_row(line)
    if not cells:
        return False
    return all(re.fullmatch(r":?-{3,}:?", (cell or "").strip()) for cell in cells)


def looks_like_md_row(line: str) -> bool:  # R/4291
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 2


def normalize_md_cell_for_word(text: str | None) -> str:  # R/4296
    if text is None:
        return ""
    t = str(text).replace("&#124;", "|").strip()
    return t


def normalize_table_row_cells(cells: list[str], col_count: int) -> list[str]:  # R/4303
    cells = [normalize_md_cell_for_word(c) for c in cells]
    if len(cells) < col_count:
        cells += [""] * (col_count - len(cells))
    elif len(cells) > col_count:
        cells = [*cells[: col_count - 1], " | ".join(cells[col_count - 1 :])]
    return cells


def add_text_to_cell(
    cell: _Cell, text: str, *, font_size: float = 8.5, bold: bool = False, color: RGBColor = BLACK
) -> None:  # R/4312
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0

    parts = normalize_inline_breaks(text).split("\n")
    for idx, part in enumerate(parts):
        run = p.add_run(writable(part))  # (TR1b) W10 을 넘기기 전에 — failures.writable
        apply_run_style(run, size=font_size, color=color, bold=bold)
        if idx < len(parts) - 1:
            run.add_break()

    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    set_cell_margins(cell)


def add_markdown_table(doc: DocumentObject, rows: list[str]) -> None:  # R/4330
    """Markdown pipe table을 실제 Word 표로 변환한다."""
    clean_rows = [r.strip() for r in rows if r and r.strip()]

    if len(clean_rows) < 2 or not is_md_separator_row(clean_rows[1]):
        for row in clean_rows:
            add_styled_paragraph(doc, row, color=BLACK, size=8.5, space_after=1, line_spacing=1.0)
        return

    header = split_md_row(clean_rows[0])
    col_count = len(header)
    header = normalize_table_row_cells(header, col_count)

    body_rows: list[list[str]] = []
    for r in clean_rows[2:]:
        if not looks_like_md_row(r):
            continue
        cells = normalize_table_row_cells(split_md_row(r), col_count)
        body_rows.append(cells)

    table = doc.add_table(rows=1, cols=col_count)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    set_table_borders(table)

    header_cells = table.rows[0].cells
    for i, text in enumerate(header):
        add_text_to_cell(header_cells[i], text, font_size=8.2, bold=True, color=BLACK)
        set_cell_shading(header_cells[i], "DDEBF7")

    for row_data in body_rows:
        row_cells = table.add_row().cells
        for i in range(col_count):
            cell_text = row_data[i] if i < len(row_data) else ""
            add_text_to_cell(row_cells[i], cell_text, font_size=8.0, color=BLACK)

    doc.add_paragraph()


def merge_wrapped_lines(lines: list[str], *, keep_subtags: bool = False) -> list[str]:  # R/4371
    """
    PDF/Word 추출에서 줄바꿈된 본문을 문단 단위로 다시 합친다.
    markdown 표 행, subtag, bullet/번호 목록은 분리 유지한다.

    v0.7.5 수정: 짧은 줄(≤60자, 마침표 없음)은 독립 유지
    → BLOCK 제목과 본문이 한 줄로 합쳐지던 문제 해결
    """
    merged: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if buf:
            merged.append(" ".join(x.strip() for x in buf if x.strip()))
            buf = []

    for raw in lines:
        s = raw.strip()

        if not s:
            flush()
            continue

        if SUBTAG_ONLY_RE.match(s):
            flush()
            if keep_subtags:
                merged.append(raw)
            continue

        if looks_like_md_row(s):
            flush()
            merged.append(raw)
            continue

        if BULLET_RE.match(s):
            flush()
            merged.append(raw)
            continue

        # 짧은 독립 제목 (콜론으로 끝나는 35자 이하)
        if len(s) <= 35 and s.endswith(":"):
            flush()
            merged.append(raw)
            continue

        # ★ 수정: 짧은 줄(≤60자, 문장 종결 없음)은 독립 유지
        # 제목, 라벨, 소제목 등이 본문과 합쳐지는 것을 방지
        if len(s) <= 60 and not s.endswith((".", "!", "?")):
            flush()
            merged.append(raw)
            continue

        buf.append(raw)

        # 문장 종결 시 flush (wrapping된 긴 문장 처리)
        if s.endswith((".", "!", "?")):
            flush()

    flush()
    return merged


def split_lines_into_segments(lines: list[str]) -> list[Block]:  # R/4433
    """
    일반 텍스트와 markdown 표를 섞어서 분리한다.
    [MARKDOWN_TABLE] 태그가 없어도
    | header |
    | --- |
    | row |
    형태면 표로 인식한다.
    """
    segments: list[Block] = []
    text_buf: list[str] = []
    i = 0

    while i < len(lines):
        raw = lines[i].rstrip()
        s = raw.strip()

        if s == "[MARKDOWN_TABLE]":
            i += 1
            continue

        if looks_like_md_row(raw) and i + 1 < len(lines) and is_md_separator_row(lines[i + 1].strip()):
            if text_buf:
                segments.append({"type": "text", "lines": text_buf})
                text_buf = []

            table_rows = [lines[i].rstrip(), lines[i + 1].rstrip()]
            i += 2

            while i < len(lines):
                raw2 = lines[i].rstrip()
                if looks_like_md_row(raw2):
                    table_rows.append(raw2)
                    i += 1
                    continue
                break

            segments.append({"type": "table", "rows": table_rows})
            continue

        text_buf.append(raw)
        i += 1

    if text_buf:
        segments.append({"type": "text", "lines": text_buf})

    return segments


def render_lines_with_tables(
    doc: DocumentObject,
    lines: list[str],
    *,
    default_color: RGBColor = BLACK,
    default_size: float = 9.5,
    first_line_bold: bool = False,
    first_line_color: RGBColor | None = None,
    first_line_size: float = 10.5,
    italic: bool = False,
    keep_subtags: bool = False,
    text_space_after: float = 1.5,
    heading_levels: bool = False,
) -> None:  # R/4486
    """
    lines 안에 markdown 표가 섞여 있으면 자동으로 Word 표로 변환해서 렌더링.
    일반 본문은 줄단위가 아니라 문단 단위로 병합한다.
    """
    rendered_text_count = 0

    for seg in split_lines_into_segments(lines):
        if seg["type"] == "table":
            add_markdown_table(doc, seg["rows"])
            continue

        merged_lines = merge_wrapped_lines(seg["lines"], keep_subtags=keep_subtags)

        for line in merged_lines:
            s = line.strip()

            if not s:
                continue

            if SUBTAG_ONLY_RE.match(s):
                if keep_subtags:
                    add_styled_paragraph(doc, line, color=GRAY, size=8.5, bold=True, space_after=1)
                continue

            is_first = first_line_bold and rendered_text_count == 0
            level = heading_level(s) if (is_first and heading_levels) else None  # TRW13 C

            add_styled_paragraph(
                doc,
                line,
                color=first_line_color if (is_first and first_line_color is not None) else default_color,
                size=HEADING_SIZES[level] if level else first_line_size if is_first else default_size,
                bold=is_first,
                italic=italic,
                space_before=HEADING_SPACE_BEFORE[level] if level else 0,
                space_after=3 if is_first else text_space_after,
            )
            rendered_text_count += 1


def configure_document(doc: DocumentObject) -> None:  # R/4537
    style = cast(ParagraphStyle, doc.styles["Normal"])
    style.font.name = "Malgun Gothic"
    cast(CT_Fonts, style.element.get_or_add_rPr().rFonts).set(qn("w:eastAsia"), "Malgun Gothic")
    style.font.size = Pt(9.5)

    sec = doc.sections[0]
    sec.top_margin = Inches(0.55)
    sec.bottom_margin = Inches(0.55)
    sec.left_margin = Inches(0.55)
    sec.right_margin = Inches(0.55)


def parse_blocks(text: str) -> list[Block]:  # R/4550
    lines = text.splitlines()
    blocks: list[Block] = []
    i = 0

    while i < len(lines):
        raw = lines[i].rstrip("\n")
        stripped = raw.strip()

        if not stripped:
            i += 1
            continue

        if re.match(r"^\[PAGE\s+\d+\]$", stripped, re.IGNORECASE):
            blocks.append({"type": "page", "tag": stripped})
            i += 1
            continue

        elif re.match(r"^\[BLOCK\s+\d+\]$", stripped, re.IGNORECASE):
            tag = stripped
            content_lines: list[str] = []
            i += 1

            while i < len(lines):
                s = lines[i].strip()
                if is_top_level_break(s):
                    break
                content_lines.append(lines[i].rstrip())
                i += 1

            blocks.append({"type": "block", "tag": tag, "content_lines": content_lines})
            continue

        elif re.match(r"^\[TABLE\s+\d+\]$", stripped, re.IGNORECASE):
            tag = stripped
            intro_lines: list[str] = []
            caption_lines: list[str] = []
            structure_notes: list[str] = []
            table_rows: list[str] = []
            notes: list[str] = []
            extra_lines: list[str] = []
            current_mode: str | None = None
            i += 1

            while i < len(lines):
                raw2 = lines[i].rstrip()
                s2 = raw2.strip()  # 코랩의 `l`(R/4603) — ruff E741 로 이름만 바꿈

                if is_top_level_break(s2):
                    break

                if s2 == "[CAPTION]":
                    current_mode = "caption"
                    i += 1
                    continue
                elif s2 == "[STRUCTURE_NOTES]":
                    current_mode = "structure"
                    i += 1
                    continue
                elif s2 == "[MARKDOWN_TABLE]":
                    current_mode = "markdown"
                    i += 1
                    continue
                elif s2 == "[NOTES]":
                    current_mode = "notes"
                    i += 1
                    continue

                if current_mode is None:
                    # [MARKDOWN_TABLE] 태그 없이 바로 파이프 행이 오면 markdown 모드로 전환
                    if s2.startswith("|") and s2.count("|") >= 2:
                        current_mode = "markdown"
                        table_rows.append(raw2)
                    elif s2:
                        intro_lines.append(raw2)
                elif current_mode == "caption":
                    if s2:
                        caption_lines.append(raw2)
                elif current_mode == "structure":
                    if s2:
                        structure_notes.append(raw2)
                elif current_mode == "markdown":
                    if s2.startswith("|"):
                        table_rows.append(raw2)
                    elif s2.startswith("-" * 10):  # 구분선(---...) 스킵
                        pass
                    elif s2:
                        # 중요 수정:
                        # markdown 표가 끝난 뒤 나오는 비-pipe 줄은 표 행이 아니라
                        # 표 아래 주석/출처/번호 주석으로 처리해야 합니다.
                        # 기존처럼 table_rows에 넣으면 add_markdown_table()에서 무시되어
                        # 최종 Word에서 표 주석이 사라집니다.
                        current_mode = "notes"
                        notes.append(raw2)
                elif current_mode == "notes" and s2:
                    notes.append(raw2)

                i += 1

            blocks.append(
                {
                    "type": "table",
                    "tag": tag,
                    "intro_lines": intro_lines,
                    "caption_lines": caption_lines,
                    "structure_notes": structure_notes,
                    "rows": table_rows,
                    "notes": notes,
                    "extra_lines": extra_lines,
                }
            )
            continue

        elif re.match(r"^\[VISUAL\s+\d+\]$", stripped, re.IGNORECASE):
            tag = stripped
            visual_lines: list[str] = []
            i += 1

            while i < len(lines):
                raw2 = lines[i].rstrip()
                s = raw2.strip()

                if is_top_level_break(s):
                    break

                visual_lines.append(raw2)
                i += 1

            blocks.append({"type": "visual", "tag": tag, "content": "\n".join(visual_lines)})
            continue

        elif re.match(r"^\[(HEADER|FOOTER|PAGE_NUMBER)\]$", stripped, re.IGNORECASE):
            tag = stripped
            content_lines = []
            i += 1

            while i < len(lines):
                s = lines[i].strip()
                if is_top_level_break(s):
                    break
                content_lines.append(lines[i].rstrip())
                i += 1

            blocks.append({"type": "meta", "tag": tag, "content_lines": content_lines})
            continue

        else:
            plain_lines = [raw]
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if is_top_level_break(s):
                    break
                plain_lines.append(lines[i].rstrip())
                i += 1

            blocks.append({"type": "plain", "content_lines": plain_lines})
            continue

    return blocks


def extract_page_num_from_tag(tag: str) -> int | None:  # R/4726
    """[PAGE n] 태그에서 n을 정수로 추출."""
    m = re.match(r"^\[PAGE\s+(\d+)\]$", str(tag).strip(), re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError as error:  # (TR1b) Python 3.11+ int 자릿수 상한(기본 4,300) — 코랩은 except → False(R/4915)
        raise WordUnwritable(f"쪽 번호 {len(m.group(1)):,}자리를 수로 못 읽는다 — {error}") from None


def translated_to_docx(text: str) -> bytes | WordFailed:  # R/4732
    """
    txt → Word 변환.

    v0.7.4 핵심 수정:
    - [PAGE n] 태그가 같은 페이지 번호로 반복될 경우 page break를 넣지 않음
    - 같은 페이지 안의 [BLOCK], [TABLE], [VISUAL]은 연속해서 출력
    - 실제 페이지 번호가 바뀔 때만 doc.add_page_break() 실행

    (TR1b) 파일 대신 바이트, 실패는 `WordFailed` — 머리 docstring 「코랩과 다른 자리」.
    """
    try:
        doc = Document()
        require_styles(doc, STYLES)
        configure_document(doc)

        current_page_num: int | None = None
        page_label_rendered: set[int] = set()

        for block in parse_blocks(text):
            btype = block["type"]

            if btype == "page":
                page_num = extract_page_num_from_tag(block["tag"])

                # PAGE 태그가 비정상이면 출력만 하고 넘어감
                if page_num is None:
                    add_styled_paragraph(
                        doc, block["tag"], color=LIGHT_GRAY, size=8.5, bold=True, space_after=2, line_spacing=1.0
                    )
                    continue

                # 첫 PAGE 태그
                if current_page_num is None:
                    current_page_num = page_num

                    if page_num not in page_label_rendered:
                        add_styled_paragraph(
                            doc, block["tag"], color=LIGHT_GRAY, size=8.5, bold=True, space_after=2, line_spacing=1.0
                        )
                        page_label_rendered.add(page_num)

                    continue

                # 같은 PAGE 번호가 다시 나오면 중복 태그로 보고 아무 것도 하지 않음
                # 중요: 여기서 page break를 넣으면 같은 원본 페이지의 BLOCK/TABLE/VISUAL이
                #       다음 Word 페이지로 밀리는 문제가 생김
                if page_num == current_page_num:
                    continue

                # 실제 원본 페이지 번호가 바뀔 때만 새 페이지 시작
                doc.add_page_break()
                current_page_num = page_num

                if page_num not in page_label_rendered:
                    add_styled_paragraph(
                        doc, block["tag"], color=LIGHT_GRAY, size=8.5, bold=True, space_after=2, line_spacing=1.0
                    )
                    page_label_rendered.add(page_num)

                continue

            elif btype == "block":
                add_styled_paragraph(
                    doc, block["tag"], color=BLUE, size=9, bold=True, space_before=5, space_after=2, line_spacing=1.0
                )

                render_lines_with_tables(
                    doc,
                    block.get("content_lines", []),
                    default_color=BLACK,
                    default_size=9.5,
                    first_line_bold=True,
                    first_line_size=10.5,
                    text_space_after=1.2,
                    heading_levels=True,
                )

            elif btype == "table":
                add_styled_paragraph(
                    doc, block["tag"], color=BLUE, size=9, bold=True, space_before=5, space_after=1.5, line_spacing=1.0
                )

                render_lines_with_tables(
                    doc,
                    block.get("intro_lines", []),
                    default_color=BLACK,
                    default_size=9.3,
                    first_line_bold=True,
                    first_line_color=BLUE,
                    first_line_size=9.3,
                    text_space_after=1.0,
                )

                for line in merge_wrapped_lines(block.get("caption_lines", [])):
                    if line.strip():
                        add_styled_paragraph(doc, line, color=BLUE, size=9, bold=True, space_after=1)

                for line in merge_wrapped_lines(block.get("structure_notes", [])):
                    add_styled_paragraph(doc, line, color=GRAY, size=8, italic=True, space_after=0.8)

                if block.get("rows"):
                    add_markdown_table(doc, block["rows"])

                render_lines_with_tables(
                    doc, block.get("extra_lines", []), default_color=BLACK, default_size=8.8, text_space_after=1.0
                )

                for line in merge_wrapped_lines(block.get("notes", [])):
                    add_styled_paragraph(doc, line, color=GRAY, size=8, italic=True, space_after=0.8)

            elif btype == "visual":
                add_styled_paragraph(
                    doc, block["tag"], color=BLUE, size=9, bold=True, space_before=5, space_after=2, line_spacing=1.0
                )

                render_lines_with_tables(
                    doc,
                    block.get("content", "").splitlines(),
                    default_color=BLACK,
                    default_size=9.2,
                    keep_subtags=True,
                    text_space_after=1.0,
                )

            elif btype == "meta":
                add_styled_paragraph(doc, block["tag"], color=GRAY, size=8, bold=True, space_after=1)
                for line in merge_wrapped_lines(block.get("content_lines", [])):
                    add_styled_paragraph(doc, line, color=GRAY, size=8, space_after=0.8)

            elif btype == "plain":
                render_lines_with_tables(
                    doc, block.get("content_lines", []), default_color=BLACK, default_size=9.5, text_space_after=1.2
                )

        buffer = io.BytesIO()
        doc.save(buffer)
        return buffer.getvalue()

    except _WORD_ERRORS as error:
        return word_failed(error)


def render_bilingual(text: str) -> bytes | WordFailed:
    """병기 글(`variants[].bilingualText`·`autofix.bilingualText`) 하나 → 병기 Word 바이트(또는 실패 갈래)."""
    return translated_to_docx(text)
