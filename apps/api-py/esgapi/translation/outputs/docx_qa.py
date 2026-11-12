# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false, reportOptionalMemberAccess=false
"""검수 Word(코랩 셀 62 의 살아남는 도우미 일곱 R/5446-5617 + 셀 63 전부 R/5716-6018). 입구는
`render_qa(sections, label)`.

마지막 정의가 이긴다: 셀 62 의 v1 `add_translation_text_qa`(R/5619)·`build_qa_docx`(R/5652)는 셀 63 의 v2 가 덮으므로
옮기지 않는다. 코랩 셀 65 는 쪽마다 `(pnum, display, issues)` 를 `all_sections` 에 넣고(R/6269) `build_qa_docx` 를
부른다(R/6293) — 그 한 줄이 `QaSection`, 이슈 한 건이 `QaIssue`(코랩 dict 키 이름 그대로)다. 결과에서 그것을 짓는 것은
files.py 다.

코랩과 다른 자리(보고 「코랩과 다른 자리」 표):
- 파일 → 바이트: `doc.save(output_path)`·`os.path.exists`(R/6013-6014) 대신 `doc.save(BytesIO)`.
- 코랩 `build_qa_docx` 에는 try 가 없다 — 예외면 셀 65 가 멈추고 그 뒤(자동수정)가 안 돈다. 우리는 Word 를 결과 뒤에
  지으므로 코랩에서 실패가 되는 입력(못 담는 글자·없는 스타일)을 넘기기 전에 알아보고 `WordFailed` 로 낸다(처분 ⑧,
  가지 리뷰 M2 — run 여섯 자리에 `writable`). 그 밖의 예외와 `MemoryError` 는 밖으로.
- 이슈는 dict 대신 `QaIssue`: `x.get("severity")`(R/5571-5573)·`issue.get("issue_type", "")`(R/5600-5604) 자리가
  속성이다. 코랩은 키가 없으면 빈 글 — `QaIssue` 는 칸이 늘 있다(결과의 이슈는 다섯 칸이 늘 있다 — shapes.ReviewIssue).
- `page_num` 인자(R/5522)는 코랩도 쓰지 않는다 — 그대로 받는다.

약점(코랩대로): W9 요약표의 수 칸이 0 이면 빈 칸(`str(text or "")` R/5486 — HIGH·MEDIUM·LOW 0 과 쪽 번호 0). W10 XML
에 못 담는 글자 — 본문은 `splitlines()` 로 갈라 `\\x0b`·`\\x0c` 가 줄바꿈이 되지만, 이슈 칸(문제 구간·제안·이유)과 문체
라벨은 가르지 않아 `\\x0b` 도 `ValueError` 다.

python-docx 비공개 속성(`._tc`·`._element`)과 lxml 요소 때문에 머리 완화 — docx_bilingual 의 넷 + `rPr` 의 None
(`reportOptionalMemberAccess` — 코랩은 `run.font.size`·`.name` 을 먼저 써 `rPr`·`rFonts` 가 늘 있다).
"""

import io
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_COLOR_INDEX
from docx.exceptions import PythonDocxError
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.table import _Cell
from docx.text.paragraph import Paragraph

from esgapi.translation.engines.colab_158.review_rules import strip_korean_bilingual_annotations
from esgapi.translation.outputs.docx_bilingual import require_styles, word_failed
from esgapi.translation.outputs.failures import WordFailed, WordUnwritable, writable

# docx_bilingual._WORD_ERRORS 와 같은 둘(가지 리뷰 M2): 넘기기 전에 알아본 실패(`WordUnwritable` — 못 담는 글자는 run
# 여섯 자리의 `writable`, 틀에 없는 스타일은 `require_styles`)와 `PythonDocxError`. ValueError·KeyError 는 밖으로 —
# `RGBColor.from_string` 의 ValueError 는 색이 상수뿐이라 나면 우리 버그다.
_WORD_ERRORS: Final = (WordUnwritable, PythonDocxError)
STYLES: Final = ("Table Grid",)
"""셀 62 가 이름으로 부르는 스타일(R/5562·R/5592)."""


@dataclass(frozen=True, slots=True)
class QaIssue:
    """코랩 이슈 dict 한 건(셀 58 `review_page_pair` 가 내는 키 — R/5600-5604 가 읽는 다섯)."""

    issue_type: str
    severity: str
    original_span: str
    suggestion: str
    reason: str


@dataclass(frozen=True, slots=True)
class QaSection:
    """코랩 `all_sections` 한 줄 `(pnum, display_translation_content, issues)`(R/6269)."""

    page_num: int
    content: str
    issues: Sequence[QaIssue]


# ── 셀 62 의 살아남는 도우미 일곱 ────────────────────────────────────────


def set_cell_shading_qa(cell: _Cell, fill: str) -> None:  # R/5469
    """Word table cell 배경색 지정."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))

    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)

    shd.set(qn("w:fill"), fill)


def set_cell_text_qa(
    cell: _Cell, text: object, bold: bool = False, font_size: float = 8.5, color: str = "000000"
) -> None:  # R/5481
    """Word table cell 텍스트 지정."""
    cell.text = ""

    p = cell.paragraphs[0]
    run = p.add_run(writable(str(text or "")))
    run.bold = bold
    run.font.size = Pt(font_size)
    run.font.name = "Malgun Gothic"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    run.font.color.rgb = RGBColor.from_string(color)

    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_para_qa(
    doc: DocumentObject,
    text: object = "",
    bold: bool = False,
    size: float = 9,
    color: str = "000000",
    space_after: float = 2,
) -> Paragraph:  # R/5496
    """QA Word 문단 추가."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.05

    run = p.add_run(writable(str(text or "")))
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = "Malgun Gothic"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    run.font.color.rgb = RGBColor.from_string(color)

    return p


def add_heading_qa(doc: DocumentObject, text: str, level: int = 1) -> Paragraph:  # R/5512
    """QA Word 제목 추가."""
    if level == 1:
        return add_para_qa(doc, text, bold=True, size=14, color="1F4E79", space_after=6)
    elif level == 2:
        return add_para_qa(doc, text, bold=True, size=11, color="2E75B6", space_after=4)
    else:
        return add_para_qa(doc, text, bold=True, size=9.5, color="404040", space_after=3)


def prepare_full_translation_for_qa(content: str, page_num: int | None = None) -> list[str]:  # R/5522
    """
    QA Word 표시용 번역문 정리.
    - 국문 병기 괄호는 제거해서 영어본 중심으로 표시
    - 단, 실제 미번역 한글은 남겨서 확인 가능하게 함
    - [PAGE n] 중복 태그는 제거
    """
    text = strip_korean_bilingual_annotations(content)

    lines: list[str] = []
    prev_blank = False

    for raw in text.splitlines():
        line = raw.rstrip()
        s = line.strip()

        # [PAGE n] 태그는 QA Word에서 별도 제목으로 처리하므로 본문에서는 제거
        if re.match(r"^\[PAGE\s+\d+\]$", s, re.IGNORECASE):
            continue

        # 빈 줄 과다 방지
        if not s:
            if prev_blank:
                continue
            prev_blank = True
            lines.append("")
            continue

        prev_blank = False
        lines.append(line)

    return lines


def add_issue_summary_table_qa(
    doc: DocumentObject, all_sections: Sequence[QaSection], variant_label: str
) -> None:  # R/5556
    """전체 페이지별 이슈 수 요약표."""
    add_heading_qa(doc, "QA Summary", level=2)

    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ["Style", "Page", "HIGH", "MEDIUM", "LOW"]

    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        set_cell_text_qa(cell, h, bold=True, font_size=8.5, color="FFFFFF")
        set_cell_shading_qa(cell, "404040")

    for section in all_sections:
        pnum, issues = section.page_num, section.issues
        high = sum(1 for x in issues if x.severity == "HIGH")
        med = sum(1 for x in issues if x.severity == "MEDIUM")
        low = sum(1 for x in issues if x.severity == "LOW")

        row = table.add_row().cells
        values: list[object] = [variant_label, pnum, high, med, low]

        for i, v in enumerate(values):
            set_cell_text_qa(row[i], v, font_size=8.5)

    doc.add_paragraph()


def add_issues_table_qa(doc: DocumentObject, issues: Sequence[QaIssue]) -> None:  # R/5585
    """페이지별 이슈 목록표."""
    if not issues:
        add_para_qa(doc, "No definite QA issues found.", bold=False, size=8.5, color="666666")
        return

    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ["유형", "심각도", "문제 구간", "수정 제안", "이유"]

    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        set_cell_text_qa(cell, h, bold=True, font_size=8, color="FFFFFF")
        set_cell_shading_qa(cell, "404040")

    for issue in issues:
        row = table.add_row().cells

        values = [
            issue.issue_type,
            issue.severity,
            issue.original_span,
            issue.suggestion,
            issue.reason,
        ]

        for i, v in enumerate(values):
            set_cell_text_qa(row[i], v, font_size=7.5)

    doc.add_paragraph()


# ── 셀 63(v2) ─────────────────────────────────────────────────────────


def collect_issue_spans_for_highlight(issues: Sequence[QaIssue] | None) -> list[str]:  # R/5737
    """
    QA 이슈에서 본문 하이라이트할 original_span 수집.
    - 빈 값 제거
    - 너무 짧은 값 제거
    - 긴 span 우선 정렬
    """
    spans: list[str] = []

    for issue in issues or []:
        span = str(issue.original_span or "").strip()

        if not span:
            continue

        # 너무 짧은 단어는 오탐 하이라이트가 많아서 제외
        if len(span) < 4:
            continue

        # 태그 자체는 하이라이트하지 않음
        if re.fullmatch(r"\[[A-Z_]+(?:\s+\d+)?\]", span.strip(), re.IGNORECASE):
            continue

        if span not in spans:
            spans.append(span)

    # 긴 문구부터 매칭해야 짧은 단어가 먼저 먹는 문제 방지
    spans.sort(key=len, reverse=True)
    return spans


def find_highlight_intervals(line: str, spans: Sequence[str]) -> list[tuple[int, int]]:  # R/5768
    """
    한 줄 안에서 하이라이트할 구간 계산.
    겹치는 span은 긴 span 우선으로 처리.
    """
    if not line or not spans:
        return []

    intervals: list[tuple[int, int]] = []

    for span in spans:
        start = 0

        while True:
            idx = line.find(span, start)

            if idx == -1:
                break

            end = idx + len(span)

            # 기존 구간과 겹치면 스킵
            overlaps = any(not (end <= s or idx >= e) for s, e in intervals)

            if not overlaps:
                intervals.append((idx, end))

            start = end

    intervals.sort()
    return intervals


def add_highlighted_line_qa(
    doc: DocumentObject,
    line: str,
    spans: Sequence[str],
    bold: bool = False,
    size: float = 8.8,
    color: str = "000000",
    space_after: float = 2,
    highlight_color: WD_COLOR_INDEX = WD_COLOR_INDEX.YELLOW,
) -> Paragraph:  # R/5801
    """
    한 줄을 Word 문단으로 추가하면서,
    issue span에 해당하는 부분만 노란색 하이라이트.
    """
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.05

    intervals = find_highlight_intervals(line, spans)

    if not intervals:
        run = p.add_run(writable(str(line or "")))
        run.bold = bold
        run.font.size = Pt(size)
        run.font.name = "Malgun Gothic"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
        run.font.color.rgb = RGBColor.from_string(color)
        return p

    cursor = 0

    for s, e in intervals:
        # 일반 구간
        if s > cursor:
            run = p.add_run(writable(line[cursor:s]))
            run.bold = bold
            run.font.size = Pt(size)
            run.font.name = "Malgun Gothic"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
            run.font.color.rgb = RGBColor.from_string(color)

        # 하이라이트 구간
        run = p.add_run(writable(line[s:e]))
        run.bold = True
        run.font.size = Pt(size)
        run.font.name = "Malgun Gothic"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
        run.font.color.rgb = RGBColor.from_string("C00000")
        run.font.highlight_color = highlight_color

        cursor = e

    # 남은 일반 구간
    if cursor < len(line):
        run = p.add_run(writable(line[cursor:]))
        run.bold = bold
        run.font.size = Pt(size)
        run.font.name = "Malgun Gothic"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
        run.font.color.rgb = RGBColor.from_string(color)

    return p


def add_translation_text_qa(
    doc: DocumentObject, lines: Sequence[str], issues: Sequence[QaIssue] | None = None
) -> None:  # R/5865
    """
    영어 번역본 전체 출력 + QA 이슈 위치 하이라이트.
    기존 add_translation_text_qa() 대체 함수.
    """
    spans = collect_issue_spans_for_highlight(issues)

    for line in lines:
        s = line.strip()

        if not s:
            doc.add_paragraph()
            continue

        # BLOCK / TABLE / VISUAL 태그
        if re.match(r"^\[(BLOCK|TABLE|VISUAL)\s+\d+\]$", s, re.IGNORECASE):
            add_highlighted_line_qa(doc, s, spans=[], bold=True, size=9, color="2E75B6", space_after=2)
            continue

        # CAPTION / MARKDOWN_TABLE / STRUCTURE_NOTES 등 하위 태그
        if re.match(r"^\[[A-Z_]+\]$", s):
            add_highlighted_line_qa(doc, s, spans=[], bold=True, size=8, color="808080", space_after=1)
            continue

        # Markdown 표 row
        if s.startswith("|") and s.endswith("|"):
            add_highlighted_line_qa(doc, s, spans=spans, bold=False, size=7.5, color="444444", space_after=1)
            continue

        # 일반 번역문
        add_highlighted_line_qa(doc, line, spans=spans, bold=False, size=8.8, color="000000", space_after=2)


def add_issue_summary_note_qa(doc: DocumentObject, issues: Sequence[QaIssue]) -> None:  # R/5930
    """
    페이지 상단에 하이라이트 안내 추가.
    """
    if not issues:
        add_para_qa(doc, "No definite QA issues found.", bold=True, size=8.8, color="548235", space_after=4)
        return

    add_para_qa(
        doc,
        "Highlighted text in the translation indicates the exact QA issue span.",
        bold=True,
        size=8.5,
        color="C00000",
        space_after=4,
    )


def build_qa_docx(all_sections: Sequence[QaSection], variant_label: str = "A") -> bytes:  # R/5955
    """
    QA Word 생성 함수 덮어쓰기 버전 v2.

    구성:
    1. 전체 요약
    2. PAGE별 영어 번역본 전체
       - 이슈 original_span은 노란색 하이라이트
    3. PAGE별 QA Issues 표

    (TR1b) 파일 대신 바이트. 코랩처럼 try 가 없다 — 실패 갈래는 `render_qa` 가 짓는다.
    """
    doc = Document()
    require_styles(doc, STYLES)

    section = doc.sections[0]
    section.top_margin = Inches(0.55)
    section.bottom_margin = Inches(0.55)
    section.left_margin = Inches(0.55)
    section.right_margin = Inches(0.55)

    add_heading_qa(doc, f"QA Report - Style {variant_label}", level=1)
    add_para_qa(
        doc,
        "This QA report shows the full English translation for every page. "
        "Detected issue spans are highlighted in yellow.",
        size=8.5,
        color="666666",
        space_after=6,
    )

    add_issue_summary_table_qa(doc, all_sections, variant_label)

    for idx, qa_section in enumerate(all_sections):
        pnum, content, issues = qa_section.page_num, qa_section.content, qa_section.issues
        if idx > 0:
            doc.add_page_break()

        add_heading_qa(doc, f"[PAGE {pnum}] Style {variant_label}", level=2)

        issue_count = len(issues)
        issue_color = "C00000" if issue_count else "548235"

        add_para_qa(doc, f"QA issues: {issue_count}", bold=True, size=9, color=issue_color, space_after=2)

        add_issue_summary_note_qa(doc, issues)

        add_heading_qa(doc, "Full English Translation", level=3)

        lines = prepare_full_translation_for_qa(content, page_num=pnum)

        # 핵심: issues를 넘겨서 본문 안 original_span 하이라이트
        add_translation_text_qa(doc, lines, issues=issues)

        add_heading_qa(doc, "QA Issues", level=3)
        add_issues_table_qa(doc, issues)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def render_qa(sections: Sequence[QaSection], variant_label: str) -> bytes | WordFailed:
    """검수 Word 바이트(또는 실패 갈래). 코랩은 try 가 없어 셀 65 가 멈춘다 — 「코랩과 다른 자리」(처분 ⑧)."""
    try:
        return build_qa_docx(sections, variant_label)
    except _WORD_ERRORS as error:
        return word_failed(error)
