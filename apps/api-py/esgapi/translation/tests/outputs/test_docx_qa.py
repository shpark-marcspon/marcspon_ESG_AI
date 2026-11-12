"""검수 Word(발주서 §3 S3·S5 의 W9·W10): 섹션 둘(이슈 있음·없음) → `render_qa` 바이트 → 다시 읽은 값이 코랩 셀 62·63 의
상수·규칙에서 손으로 적은 기대값과 같다(근거 R/ 는 읽기판 보고서_AI번역_v3_1 의 줄). 읽기는 readback(정본 하나)으로
하고, 경우마다 python-docx·ElementTree 로 손수 읽은 단언을 따로 둔다(도우미가 틀려도 시험이 같이 틀리지 않게).
"""

import io
import xml.etree.ElementTree as ET
from typing import Any

import docx
import pytest
from docx.enum.text import WD_COLOR_INDEX

from esgapi.translation.outputs import docx_qa
from esgapi.translation.outputs.docx_qa import (
    QaIssue,
    QaSection,
    collect_issue_spans_for_highlight,
    find_highlight_intervals,
    prepare_full_translation_for_qa,
    render_qa,
)
from esgapi.translation.outputs.failures import WordFailed
from esgapi.translation.outputs.readback import read_word
from esgapi.translation.tests.docx_support import W_NS, parts_of


def issue(span: str, severity: str = "HIGH") -> QaIssue:
    return QaIssue("TERMINOLOGY", severity, span, "가상 제안", "가상 이유")


# 쪽 1: [PAGE 1] 줄(빠짐)·국문 병기 괄호(빠짐)·빈 줄 셋(하나로)·하위 태그·pipe 행·짧은 span(안 칠함)·태그 span(안 칠함)·
#   긴 span 안의 짧은 span(겹쳐 건너뜀 — 같은 줄), 다른 줄의 짧은 span(칠함). 쪽 0: 이슈 없음(W9 — 쪽 0·수 0 은 빈 칸).
SECTIONS = [
    QaSection(
        1,
        "[PAGE 1]\n[BLOCK 1]\nVirtual Co. reduced emissions (가상 회사) sharply.\n\n\n[CAPTION]\n"
        "| Year | emissions value |\nshort abc text",
        [issue("reduced emissions"), issue("emissions", "LOW"), issue("abc", "MEDIUM"), issue("[BLOCK 1]")],
    ),
    QaSection(0, "[PAGE 0]\nNothing to see.", []),
]

# (글, 굵게, 크기, 색, 하이라이트) — 문단마다 run 목록. 크기 8.8 은 w:sz 17 → 8.5.
Run = tuple[str, bool | None, float | None, str | None, str | None]
PARAGRAPHS: list[list[Run]] = [
    [("QA Report - Style A", True, 14.0, "1F4E79", None)],  # 제목 1(R/5515, R/5970)
    [
        (
            "This QA report shows the full English translation for every page. "
            "Detected issue spans are highlighted in yellow.",
            False,
            8.5,
            "666666",
            None,
        )
    ],  # R/5971-5977
    [("QA Summary", True, 11.0, "2E75B6", None)],  # 제목 2(R/5517, R/5558)
    # (요약표)
    [],  # 표 뒤 빈 문단(R/5582)
    [("[PAGE 1] Style A", True, 11.0, "2E75B6", None)],  # R/5985
    [("QA issues: 4", True, 9.0, "C00000", None)],  # 이슈 있으면 C00000(R/5987-5996)
    [("Highlighted text in the translation indicates the exact QA issue span.", True, 8.5, "C00000", None)],
    [("Full English Translation", True, 9.5, "404040", None)],  # 제목 3(R/5519)
    [("[BLOCK 1]", True, 9.0, "2E75B6", None)],  # 태그 줄(R/5880-5890)
    [  # 국문 병기 빠짐, 긴 span 칠함 + 그 안 짧은 span 은 겹쳐 건너뜀(R/5786-5790)
        ("Virtual Co. ", False, 8.5, "000000", None),
        ("reduced emissions", True, 8.5, "C00000", "YELLOW"),
        (" sharply.", False, 8.5, "000000", None),
    ],
    [],  # 빈 줄 셋 → 하나(R/5541-5546) → 빈 문단(R/5872-5874)
    [("[CAPTION]", True, 8.0, "808080", None)],  # 하위 태그(R/5892-5902)
    [  # pipe 행 7.5·444444, 다른 줄의 짧은 span 은 칠함(R/5904-5914)
        ("| Year | ", False, 7.5, "444444", None),
        ("emissions", True, 7.5, "C00000", "YELLOW"),
        (" value |", False, 7.5, "444444", None),
    ],
    [("short abc text", False, 8.5, "000000", None)],  # 4자 미만 span 은 안 칠함(R/5752)
    [("QA Issues", True, 9.5, "404040", None)],
    # (이슈표)
    [],  # 표 뒤 빈 문단(R/5612)
    [("", None, None, None, None)],  # 쪽 나눔(R/5982-5983)
    [("[PAGE 0] Style A", True, 11.0, "2E75B6", None)],
    [("QA issues: 0", True, 9.0, "548235", None)],
    [("No definite QA issues found.", True, 8.5, "548235", None)],  # 안내(R/5935-5943)
    [("Full English Translation", True, 9.5, "404040", None)],
    [("Nothing to see.", False, 8.5, "000000", None)],
    [("QA Issues", True, 9.5, "404040", None)],
    [("No definite QA issues found.", False, 8.5, "666666", None)],  # 이슈표 자리(R/5587-5589)
]

SUMMARY = [
    [("Style", "404040"), ("Page", "404040"), ("HIGH", "404040"), ("MEDIUM", "404040"), ("LOW", "404040")],
    [("A", None), ("1", None), ("2", None), ("1", None), ("1", None)],
    [("A", None), ("", None), ("", None), ("", None), ("", None)],  # W9: 쪽 0·수 0 → 빈 칸(R/5486)
]
ISSUES = [
    [("유형", "404040"), ("심각도", "404040"), ("문제 구간", "404040"), ("수정 제안", "404040"), ("이유", "404040")],
    [("TERMINOLOGY", None), ("HIGH", None), ("reduced emissions", None), ("가상 제안", None), ("가상 이유", None)],
    [("TERMINOLOGY", None), ("LOW", None), ("emissions", None), ("가상 제안", None), ("가상 이유", None)],
    [("TERMINOLOGY", None), ("MEDIUM", None), ("abc", None), ("가상 제안", None), ("가상 이유", None)],
    [("TERMINOLOGY", None), ("HIGH", None), ("[BLOCK 1]", None), ("가상 제안", None), ("가상 이유", None)],
]


def built() -> bytes:
    data = render_qa(SECTIONS, "A")
    assert isinstance(data, bytes), data
    return data


def runs_of(block: dict[str, Any]) -> list[Run]:
    return [(r["text"], r["bold"], r["sizePt"], r["color"], r["highlight"]) for r in block["runs"]]


def cells_of(block: dict[str, Any]) -> list[list[tuple[str, str | None]]]:
    return [[(c["text"], c["fill"]) for c in row] for row in block["rows"]]


def test_the_qa_word_reads_back_as_cell_63_writes_it() -> None:
    blocks = read_word(built())["blocks"]
    assert [b["type"] for b in blocks].count("table") == 2
    paragraphs = [runs_of(b) for b in blocks if b["type"] == "paragraph"]
    tables = [cells_of(b) for b in blocks if b["type"] == "table"]
    assert paragraphs == PARAGRAPHS
    assert tables == [SUMMARY, ISSUES]
    # 표의 자리: 요약표는 「QA Summary」 뒤, 이슈표는 쪽 1 의 「QA Issues」 뒤
    kinds = [b["type"] for b in blocks]
    assert kinds.index("table") == 3
    assert kinds[16] == "table"
    page_breaks = [r for b in blocks if b["type"] == "paragraph" for r in b["runs"] if r["pageBreak"]]
    assert len(page_breaks) == 1  # 섹션 둘 → 쪽 나눔 하나(R/5982)
    for block in blocks:
        if block["type"] == "paragraph":
            for run in block["runs"]:
                if run["text"]:
                    assert run["font"] == run["eastAsiaFont"] == "Malgun Gothic"


def test_the_qa_word_by_hand_with_python_docx() -> None:
    """readback 과 따로: python-docx 의 문단 글·하이라이트, ElementTree 의 표 음영."""
    data = built()
    document = docx.Document(io.BytesIO(data))
    texts = [p.text for p in document.paragraphs]
    assert texts[9] == "Virtual Co. reduced emissions sharply."
    assert "[PAGE 1]" not in texts and "(가상 회사)" not in "".join(texts)
    highlighted = [
        r.text for p in document.paragraphs for r in p.runs if r.font.highlight_color == WD_COLOR_INDEX.YELLOW
    ]
    assert highlighted == ["reduced emissions", "emissions"]
    assert texts.count("No definite QA issues found.") == 2
    summary, issues = document.tables
    assert [c.text for c in summary.rows[2].cells] == ["A", "", "", "", ""]
    assert [c.text for c in issues.rows[0].cells] == ["유형", "심각도", "문제 구간", "수정 제안", "이유"]
    root = ET.fromstring(parts_of(data)["word/document.xml"])  # noqa: S314 (시험이 방금 지은 바이트)
    w = f"{{{W_NS}}}"
    head = root.find(f"{w}body/{w}tbl/{w}tr")
    assert head is not None
    fills = [shd.get(f"{w}fill") for shd in head.iter(f"{w}shd")]
    assert fills == ["404040"] * 5
    colors = [c.get(f"{w}val") for c in head.iter(f"{w}color")]
    assert colors == ["FFFFFF"] * 5  # 흰 글(R/5568)


# ── 글 함수(docx 없이) ──────────────────────────────────────────────────


def test_collect_issue_spans_for_highlight() -> None:
    issues = [
        issue(" abcd "),
        issue("abc"),
        issue(""),
        issue("[TABLE 2]"),
        issue("[caption]"),
        issue("abcd"),
        issue("a much longer span"),
    ]
    # strip·4자 미만 뺌·태그 뺌(대소문자 무시)·같은 것 하나·긴 것 먼저(R/5737-5765)
    assert collect_issue_spans_for_highlight(issues) == ["a much longer span", "abcd"]
    assert collect_issue_spans_for_highlight(None) == []


@pytest.mark.parametrize(
    ("line", "spans", "expected"),
    [
        ("reduced emissions now", ["reduced emissions", "emissions"], [(0, 17)]),  # 겹치면 건너뜀(R/5786-5790)
        ("emissions and emissions", ["emissions"], [(0, 9), (14, 23)]),  # 같은 span 여러 번
        ("abcabc", ["abcabc", "cabc"], [(0, 6)]),
        ("x", [], []),
        ("", ["abcd"], []),
    ],
)
def test_find_highlight_intervals(line: str, spans: list[str], expected: list[tuple[int, int]]) -> None:
    assert find_highlight_intervals(line, spans) == expected


def test_prepare_full_translation_for_qa() -> None:
    content = "[PAGE 3]\nTitle (제목)\n\n\n\nBody line  \n[page 3]\n"
    # [PAGE n](대소문자 무시) 줄 빠짐, 국문 괄호 빠짐, 연속 빈 줄 하나, 줄 끝 빈칸 지움(R/5522-5551)
    assert prepare_full_translation_for_qa(content, page_num=3) == ["Title", "", "Body line"]


# ── 약점·실패 갈래 ────────────────────────────────────────────────────


def test_w9_zero_counts_and_page_zero_are_blank_cells() -> None:
    """W9(코랩대로): `str(text or "")`(R/5486) — 0 은 빈 칸. 쪽 번호 0·HIGH 0·MEDIUM 0·LOW 0."""
    data = render_qa([QaSection(0, "x", [issue("abcd", "LOW")])], "B")
    assert isinstance(data, bytes)
    summary = next(b for b in read_word(data)["blocks"] if b["type"] == "table")
    assert [c["text"] for c in summary["rows"][1]] == ["B", "", "", "", "1"]
    document = docx.Document(io.BytesIO(data))
    assert [c.text for c in document.tables[0].rows[1].cells] == ["B", "", "", "", "1"]


@pytest.mark.parametrize(
    ("sections", "label"),
    [
        ([QaSection(1, "fine", [QaIssue("T", "HIGH", "fine", "가상", "bad\x0bline")])], "A"),  # 이슈 칸은 가르지 않음
        ([QaSection(1, "bad\x01line", [])], "A"),  # 본문
        ([QaSection(1, "fine", [])], "A\x02"),  # 문체 라벨
    ],
)
def test_w10_a_control_character_fails_the_qa_word(sections: list[QaSection], label: str) -> None:
    """W10: 코랩은 try 가 없어 셀 65 가 멈춘다 — 우리는 WordFailed(처분 ⑧, 「코랩과 다른 자리」)."""
    result = render_qa(sections, label)
    assert isinstance(result, WordFailed)
    assert result.message.startswith("XML 에 못 담는 글자 U+")


def test_vertical_tab_in_the_body_is_a_line_break() -> None:
    data = render_qa([QaSection(1, "first\x0bsecond", [])], "A")
    assert isinstance(data, bytes)
    texts = [p.text for p in docx.Document(io.BytesIO(data)).paragraphs]
    assert "first" in texts and "second" in texts


@pytest.mark.parametrize(
    "error", [KeyError("ours"), ValueError("ours"), TypeError("ours"), AttributeError("ours"), MemoryError()]
)
def test_errors_outside_the_list_go_out(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
    def broken(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(docx_qa, "add_issue_summary_table_qa", broken)
    with pytest.raises(type(error)):
        render_qa(SECTIONS, "A")


def test_an_empty_section_list_still_builds_the_summary() -> None:
    """공통 쪽 0 이어도 코랩은 build_qa_docx 를 부른다(R/6293) — 제목·요약표 머리만."""
    data = render_qa([], "single")
    assert isinstance(data, bytes)
    blocks = read_word(data)["blocks"]
    assert runs_of(blocks[0])[0][0] == "QA Report - Style single"
    assert [cells_of(b) for b in blocks if b["type"] == "table"] == [[SUMMARY[0]]]
