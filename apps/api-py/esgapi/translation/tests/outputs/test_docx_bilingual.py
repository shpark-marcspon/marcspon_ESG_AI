"""병기 Word(발주서 §3 S2·S5 의 W10): 지어낸 병기 글 → `render_bilingual` 바이트 → python-docx 로 다시 읽은 값이 코랩
셀 54 의 상수·규칙에서 손으로 적은 기대값과 같다(근거 R/ 는 읽기판 보고서_AI번역_v3_1 의 줄). 글 함수(`parse_blocks`·
`merge_wrapped_lines`·`split_lines_into_segments`)는 docx 없이 따로 잰다.

★e: python-docx 가 쓴 바이트는 zip 항목 시각(초 단위)이 들어가 실행마다 다를 수 있다 — 항목 내용은 같다(실측). 그래서
바이트가 아니라 다시 읽은 값과 항목 내용을 견준다.
"""

import io
import xml.etree.ElementTree as ET
from typing import cast

import docx
import pytest
from docx.document import Document as DocumentObject
from docx.exceptions import InvalidXmlError
from docx.shared import Length, RGBColor
from docx.styles.style import ParagraphStyle
from docx.text.paragraph import Paragraph

from esgapi.translation.outputs import docx_bilingual
from esgapi.translation.outputs.docx_bilingual import (
    merge_wrapped_lines,
    parse_blocks,
    render_bilingual,
    split_lines_into_segments,
)
from esgapi.translation.outputs.failures import WordFailed
from esgapi.translation.outputs.readback import read_word
from esgapi.translation.tests.docx_support import W_NS, parts_of

# 쪽 셋, 같은 쪽 번호 반복([PAGE 1] 두 번), BLOCK·TABLE(소개·캡션·구조 노트·pipe 표·표 주석)·VISUAL·HEADER·plain.
TEXT = """[PAGE 1]
[BLOCK 1]
Sustainability Report Title
This is a long sentence that is wrapped across lines in the extracted
text and continues here until it ends.
- bullet item one
Scope:
[PAGE 1]
[TABLE 1]
Table intro heading
[CAPTION]
Table 1. Emissions by year
[STRUCTURE_NOTES]
two columns
[MARKDOWN_TABLE]
| Year | tCO2e |
| --- | --- |
| 2024 | 1&#124;2 |
| 2025 |
Note: figures are estimates
[PAGE 2]
[VISUAL 1]
[CHART]
Bar chart of emissions
[HEADER]
가상 회사 Report
[PAGE 3]
Plain closing line
"""

# (글, 굵게, 기울임, 크기 pt, 색 16진, 뒤 간격 pt) — 쪽 나눔 문단과 표 뒤 빈 문단은 None.
# 크기: Pt(9.3)·Pt(9.2) 는 w:sz(반 포인트 정수)로 18 이 되어 9.0 으로 읽힌다(코랩도 같은 python-docx — 9.3 은 9.0).
Row = tuple[str, bool, bool, float, str, float] | None
EXPECTED: list[Row] = [
    ("[PAGE 1]", True, False, 8.5, "808080", 2.0),  # 첫 PAGE 라벨 LIGHT_GRAY(R/4776)
    ("[BLOCK 1]", True, False, 9.0, "2F5496", 2.0),  # BLUE 9 굵게(R/4816)
    ("Sustainability Report Title", True, False, 10.5, "000000", 3.0),  # 첫 줄 굵게 10.5(R/4827-4830)
    (
        "This is a long sentence that is wrapped across lines in the extracted text and continues here until it ends.",
        False,
        False,
        9.5,
        "000000",
        1.2,
    ),  # 60자 넘는 줄 + 문장 끝 줄 → 한 문단(R/4415-4420)
    ("- bullet item one", False, False, 9.5, "000000", 1.2),  # 글머리표 따로(R/4400)
    ("Scope:", False, False, 9.5, "000000", 1.2),  # 콜론 35자 이하 따로(R/4405)
    # 둘째 [PAGE 1] 은 같은 쪽 — 아무것도 없음(R/4793-4794)
    ("[TABLE 1]", True, False, 9.0, "2F5496", 1.5),  # R/4836
    ("Table intro heading", True, False, 9.0, "2F5496", 3.0),  # 소개 첫 줄 BLUE 9.3(→ 9.0)(R/4847-4856)
    ("Table 1. Emissions by year", True, False, 9.0, "2F5496", 1.0),  # 캡션(R/4858-4860)
    ("two columns", False, True, 8.0, "666666", 0.8),  # 구조 노트 GRAY 기울임(R/4862-4863)
    None,  # 표 뒤 빈 문단(R/4368)
    ("Note: figures are estimates", False, True, 8.0, "666666", 0.8),  # pipe 아닌 줄 → 표 주석(R/4637-4645)
    None,  # 쪽 나눔(R/4798)
    ("[PAGE 2]", True, False, 8.5, "808080", 2.0),
    ("[VISUAL 1]", True, False, 9.0, "2F5496", 2.0),  # R/4879
    ("[CHART]", True, False, 8.5, "666666", 1.0),  # keep_subtags — GRAY 8.5 굵게(R/4518-4520)
    ("Bar chart of emissions", False, False, 9.0, "000000", 1.0),  # 9.2(→ 9.0), 첫 줄 굵게 아님(R/4890-4897)
    ("[HEADER]", True, False, 8.0, "666666", 1.0),  # meta(R/4900)
    ("가상 회사 Report", False, False, 8.0, "666666", 0.8),
    None,  # 쪽 나눔
    ("[PAGE 3]", True, False, 8.5, "808080", 2.0),
    ("Plain closing line", False, False, 9.5, "000000", 1.2),  # plain(R/4905-4911)
]


def reopen(data: bytes | WordFailed) -> DocumentObject:
    assert isinstance(data, bytes), data
    return docx.Document(io.BytesIO(data))


def body_xml(data: bytes | WordFailed) -> ET.Element:
    """서식 칸(음영·테두리·글꼴·색·쪽 나눔)은 python-docx 요소(lxml — 타입 정보 없음) 대신 표준 ElementTree 로
    읽는다."""
    assert isinstance(data, bytes), data
    return ET.fromstring(parts_of(data)["word/document.xml"])  # noqa: S314 (시험이 방금 지은 바이트)


def w(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def attr(element: ET.Element | None, name: str) -> str | None:
    assert element is not None
    return element.get(w(name))


def seen(paragraph: Paragraph) -> Row:
    if not paragraph.text:
        return None
    run = paragraph.runs[0]
    size: Length | None = run.font.size
    # space_after 는 python-docx 의 꼴 표시가 Unknown 을 섞는다(lxml 위 서술자) — 읽는 값은 Length
    after = cast(Length | None, paragraph.paragraph_format.space_after)  # pyright: ignore[reportUnknownMemberType]
    color: RGBColor | None = run.font.color.rgb
    assert size is not None and after is not None
    return (paragraph.text, bool(run.bold), bool(run.italic), size.pt, str(color), after.pt)


def page_breaks(root: ET.Element) -> int:
    return sum(1 for br in root.iter(w("br")) if attr(br, "type") == "page")


def test_the_bilingual_word_reads_back_as_cell_54_writes_it() -> None:
    data = render_bilingual(TEXT)
    assert [seen(p) for p in reopen(data).paragraphs] == EXPECTED
    assert len(EXPECTED) == 22  # 경우 수(글 있는 문단 19 + 빈 문단 셋)
    # 쪽 셋, 같은 쪽 번호 반복은 나누지 않음 → 쪽 나눔 둘(R/4793-4798)
    assert page_breaks(body_xml(data)) == 2


def test_every_run_has_the_malgun_gothic_font_and_a_forced_color() -> None:
    root = body_xml(render_bilingual(TEXT))
    body = root.find(w("body"))
    assert body is not None
    runs = [r for p in body.findall(w("p")) for r in p.findall(w("r")) if r.find(w("t")) is not None]
    assert len(runs) == 19
    for run in runs:
        props = run.find(w("rPr"))
        assert props is not None
        fonts = props.find(w("rFonts"))
        assert attr(fonts, "ascii") == attr(fonts, "hAnsi") == attr(fonts, "eastAsia") == "Malgun Gothic"  # R/4192-4193
        assert len(props.findall(w("color"))) == 1  # force_run_color 가 지우고 하나만(R/4179-4186)


def test_the_document_is_configured_as_cell_54() -> None:
    document = reopen(render_bilingual(TEXT))
    normal = document.styles["Normal"]
    assert isinstance(normal, ParagraphStyle)
    size: Length | None = normal.font.size
    assert normal.font.name == "Malgun Gothic"
    assert size is not None and size.pt == 9.5
    section = document.sections[0]
    for margin in (section.top_margin, section.bottom_margin, section.left_margin, section.right_margin):
        assert margin is not None and round(margin.inches, 2) == 0.55  # R/4544-4548


def test_the_markdown_table_becomes_a_word_table() -> None:
    data = render_bilingual(TEXT)
    document = reopen(data)
    assert len(document.tables) == 1
    table = document.tables[0]
    # 짧은 행은 빈 칸으로 채움(R/4305-4306), &#124; → |(R/4278)
    assert [[c.text for c in row.cells] for row in table.rows] == [["Year", "tCO2e"], ["2024", "1|2"], ["2025", ""]]
    assert table.style is not None and table.style.name == "Table Grid"  # R/4348
    for cell in table.rows[0].cells:
        # `cell.text = ""`(R/4313)가 빈 run 하나를 먼저 남긴다(python-docx 1.2.0) — 서식 run 은 그 뒤
        empty, run = cell.paragraphs[0].runs
        size: Length | None = run.font.size
        assert empty.text == "" and empty.bold is None
        assert run.bold is True and size is not None and size.pt == 8.0  # 8.2 → w:sz 16

    tbl = body_xml(data).find(f"{w('body')}/{w('tbl')}")
    assert tbl is not None
    rows = tbl.findall(w("tr"))
    fills = [[attr(tc.find(f"{w('tcPr')}/{w('shd')}"), "fill") for tc in rows[0].findall(w("tc"))]]
    assert fills == [["DDEBF7", "DDEBF7"]]  # 머리 칸 음영(R/4356)
    for tr in rows[1:]:
        assert all(tc.find(f"{w('tcPr')}/{w('shd')}") is None for tc in tr.findall(w("tc")))
    borders = tbl.find(f"{w('tblPr')}/{w('tblBorders')}")
    assert borders is not None
    sides = [(b.tag.split("}")[1], attr(b, "val"), attr(b, "sz"), attr(b, "color")) for b in borders]
    assert sides == [  # R/4238-4252
        (name, "single", "4", "C9C9C9") for name in ("top", "left", "bottom", "right", "insideH", "insideV")
    ]
    margins = tbl.find(f"{w('tr')}/{w('tc')}/{w('tcPr')}/{w('tcMar')}")
    assert margins is not None
    assert [(m.tag.split("}")[1], attr(m, "w"), attr(m, "type")) for m in margins] == [  # R/4255-4268
        ("top", "60", "dxa"), ("start", "70", "dxa"), ("bottom", "60", "dxa"), ("end", "70", "dxa"),
    ]  # fmt: skip


def test_a_table_without_a_separator_row_becomes_small_paragraphs() -> None:
    document = reopen(render_bilingual("[TABLE 1]\n| a | b |\n| c | d |\n"))
    assert document.tables == []
    rows = [seen(p) for p in document.paragraphs]
    assert rows == [  # R/4334-4337
        ("[TABLE 1]", True, False, 9.0, "2F5496", 1.5),
        ("| a | b |", False, False, 8.5, "000000", 1.0),
        ("| c | d |", False, False, 8.5, "000000", 1.0),
    ]


def test_br_tags_become_line_breaks_inside_one_paragraph() -> None:
    document = reopen(render_bilingual("[BLOCK 1]\nfirst<br>second<br/>third\n"))
    paragraph = document.paragraphs[1]
    assert paragraph.text == "first\nsecond\nthird"  # R/4162-4169 + run.add_break(R/4223-4224)
    assert len(paragraph.runs) == 3


# ── 글 함수(docx 없이) ──────────────────────────────────────────────────


def test_parse_blocks_splits_the_text_as_cell_54() -> None:
    blocks = parse_blocks(TEXT)
    assert [b["type"] for b in blocks] == [
        "page", "block", "page", "table", "page", "visual", "meta", "page", "plain",
    ]  # fmt: skip
    table = blocks[3]
    assert table == {
        "type": "table",
        "tag": "[TABLE 1]",
        "intro_lines": ["Table intro heading"],
        "caption_lines": ["Table 1. Emissions by year"],
        "structure_notes": ["two columns"],
        "rows": ["| Year | tCO2e |", "| --- | --- |", "| 2024 | 1&#124;2 |", "| 2025 |"],
        "notes": ["Note: figures are estimates"],
        "extra_lines": [],
    }
    assert blocks[5] == {"type": "visual", "tag": "[VISUAL 1]", "content": "[CHART]\nBar chart of emissions"}
    assert blocks[6] == {"type": "meta", "tag": "[HEADER]", "content_lines": ["가상 회사 Report"]}


def test_parse_blocks_table_modes() -> None:
    # 태그 없이 pipe 행이 오면 markdown 으로(R/4622-4625), 구분선 ---------- 은 건너뜀(R/4637-4638)
    blocks = parse_blocks("[TABLE 2]\n| x | y |\n----------\n| 1 | 2 |\nafter\n")
    assert blocks[0]["rows"] == ["| x | y |", "| 1 | 2 |"]
    assert blocks[0]["notes"] == ["after"]
    # 이상한 PAGE 꼴은 plain 이 아니라 그 줄부터 plain 이 된다 — [PAGE x] 는 top-level 이 아님
    assert parse_blocks("[PAGE x]\nbody\n") == [{"type": "plain", "content_lines": ["[PAGE x]", "body"]}]


LINE_60 = "a" * 60
LINE_61 = "b" * 61


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        # 60자 이하·문장 끝 없음 → 따로(R/4410-4413). 61자는 버퍼에 들어가 다음 문장 끝 줄과 합쳐짐.
        ([LINE_60, "end."], [LINE_60, "end."]),
        ([LINE_61, "end."], [f"{LINE_61} end."]),
        # 콜론 35자 이하 → 따로
        (["x" * 34 + ":", "y" * 70 + "."], ["x" * 34 + ":", "y" * 70 + "."]),
        # 글머리표·번호·한글 목차 → 따로
        (["1) one", "가. 둘", "• three"], ["1) one", "가. 둘", "• three"]),
        # 빈 줄은 버퍼를 비움, 끝에 남은 버퍼도 비움
        ([LINE_61, "", LINE_61], [LINE_61, LINE_61]),
        # subtag 는 keep_subtags=False 면 버림
        (["[CHART]", "text."], ["text."]),
        # md 행은 그대로
        (["| a | b |"], ["| a | b |"]),
    ],
)
def test_merge_wrapped_lines(lines: list[str], expected: list[str]) -> None:
    assert merge_wrapped_lines(lines) == expected


def test_merge_wrapped_lines_keeps_subtags_when_asked() -> None:
    assert merge_wrapped_lines(["[CHART]", "text."], keep_subtags=True) == ["[CHART]", "text."]


def test_split_lines_into_segments() -> None:
    lines = ["intro", "[MARKDOWN_TABLE]", "| h |", "| --- |", "| v |", "tail", "| lone |"]
    assert split_lines_into_segments(lines) == [  # R/4433-4483
        {"type": "text", "lines": ["intro"]},
        {"type": "table", "rows": ["| h |", "| --- |", "| v |"]},
        {"type": "text", "lines": ["tail", "| lone |"]},
    ]


# ── 실패 갈래(처분 ⑧, 감독 처분 — 이름 붙인 목록) ─────────────────────────


@pytest.mark.parametrize("char", ["\x01", "\x08", "\x1f", "\x00"])
def test_w10_a_control_character_fails_the_whole_word(char: str) -> None:
    """W10(코랩대로): XML 에 못 담는 글자 하나로 병기 Word 가 통째로 안 생긴다 — 코랩 R/4915 의 False 자리."""
    result = render_bilingual(f"[PAGE 1]\nfine line\nbad{char}line\n")
    assert isinstance(result, WordFailed)
    assert result.message.startswith(f"XML 에 못 담는 글자 U+{ord(char):04X}")


@pytest.mark.parametrize("text", ["[PAGE " + "9" * 5000 + "]\nhello", "[PAGE 1]\nx\n[PAGE " + "1" * 5000 + "]\ny"])
def test_a_page_number_too_long_for_int_is_word_failed(text: str) -> None:
    """가지 리뷰 ④ 재확인: `int()` 의 자릿수 상한(Python 3.13 기본 4,300)을 넘는 쪽 번호 — 코랩은 ValueError → False."""
    result = render_bilingual(text)
    assert isinstance(result, WordFailed)
    assert result.message.startswith("쪽 번호 5,000자리를 수로 못 읽는다")


def test_vertical_tab_is_a_line_break_for_parse_blocks_not_w10() -> None:
    """발주서의 W10 예 `\\x0b` 는 병기 쪽에서는 실패가 아니다: `str.splitlines()`(R/4551)가 \\x0b 를 줄 끝으로 본다."""
    document = reopen(render_bilingual("bad\x0bline is long enough to stay a separate line here ok.\n"))
    assert [p.text for p in document.paragraphs] == ["bad", "line is long enough to stay a separate line here ok."]


def test_a_python_docx_error_becomes_word_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_doc: object) -> None:
        raise InvalidXmlError("가상")

    monkeypatch.setattr(docx_bilingual, "configure_document", broken)
    assert render_bilingual("x") == WordFailed("InvalidXmlError: 가상")


def test_a_missing_style_is_found_before_python_docx(monkeypatch: pytest.MonkeyPatch) -> None:
    """KeyError 자리(R/4206·R/4348)는 넘기기 전에 알아본다(가지 리뷰 M2)."""

    def without_table_grid() -> DocumentObject:
        document = docx.Document()
        style = document.styles["Table Grid"]
        style.element.getparent().remove(style.element)  # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType]
        return document

    monkeypatch.setattr(docx_bilingual, "Document", without_table_grid)
    assert render_bilingual("x") == WordFailed("틀에 스타일 Table Grid 이 없다")


@pytest.mark.parametrize(
    "error", [KeyError("ours"), ValueError("ours"), TypeError("ours"), AttributeError("ours"), MemoryError()]
)
def test_errors_outside_the_list_go_out(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
    """목록 밖 예외(우리 버그)와 MemoryError 는 WordFailed 로 접지 않는다(코랩은 Exception 이면 False — 다른 자리)."""

    def broken(_doc: object) -> None:
        raise error

    monkeypatch.setattr(docx_bilingual, "configure_document", broken)
    with pytest.raises(type(error)):
        render_bilingual("x")


def test_the_parts_are_the_same_on_every_run() -> None:
    """★e: 바이트는 zip 항목 시각만 다를 수 있다 — 항목 이름과 내용은 같다."""
    first = render_bilingual(TEXT)
    second = render_bilingual(TEXT)
    assert isinstance(first, bytes) and isinstance(second, bytes)
    assert parts_of(first) == parts_of(second)


def test_an_empty_text_gives_an_empty_document() -> None:
    data = render_bilingual("")
    assert reopen(data).paragraphs == []
    assert page_breaks(body_xml(data)) == 0


def test_readback_reads_the_same_values_as_python_docx() -> None:
    """readback(대조 명령의 읽기 — 처분 ⑬)이 위의 손 읽기와 같은 값을 낸다(S2 를 도우미로도)."""
    data = render_bilingual(TEXT)
    assert isinstance(data, bytes)
    blocks = read_word(data)["blocks"]
    rows: list[Row] = []
    for block in blocks:
        if block["type"] != "paragraph":
            continue
        runs = block["runs"]
        text = "".join(r["text"] for r in runs)
        if not text:
            rows.append(None)
            continue
        first = runs[0]
        rows.append(
            (text, bool(first["bold"]), bool(first["italic"]), first["sizePt"], first["color"], block["spaceAfterPt"])
        )
    assert rows == EXPECTED
    assert sum(1 for b in blocks for r in b.get("runs", []) if r["pageBreak"]) == 2
    (table,) = [b for b in blocks if b["type"] == "table"]
    assert [[c["text"] for c in row] for row in table["rows"]] == [["Year", "tCO2e"], ["2024", "1|2"], ["2025", ""]]
    assert [c["fill"] for c in table["rows"][0]] == ["DDEBF7", "DDEBF7"]


# ── 밴드 TRW13 C(sid:MARC-ISSUE-612 b): BLOCK 첫 줄이 번호 꼴 제목이면 단계별 크기(우리 덧 — 코랩 셀 54 에 없음) ──
HEADED = """[PAGE 1]
[BLOCK 1]
1. 가상 전략
가상 본문 첫째.
[BLOCK 2]
1-1. 가상 목표 (1-1. Made-up Goal)
가상 본문 둘째.
[BLOCK 3]
1-1-1 Made-up Detail
가상 본문 셋째.
[BLOCK 4]
가상 보통 문단 첫 줄
가상 본문 넷째.
"""


def test_numbered_block_first_lines_get_heading_sizes_and_a_plain_block_is_unchanged() -> None:
    rows = [seen(p) for p in reopen(render_bilingual(HEADED)).paragraphs]
    firsts = {row[0]: row for row in rows if row is not None and row[1] and not row[0].startswith("[")}
    # (글, 굵게, 기울임, 크기, 색, 뒤 간격) — 단계 1·2·3 은 크기가 서로 다르고, 굵게·색·뒤 간격은 보통 첫 줄과 같다.
    assert firsts["1. 가상 전략"] == ("1. 가상 전략", True, False, 14.0, "000000", 3.0)
    assert firsts["1-1. 가상 목표 (1-1. Made-up Goal)"][3] == 12.5
    assert firsts["1-1-1 Made-up Detail"][3] == 11.5
    # 번호 꼴이 아닌 첫 줄은 코랩대로(10.5 — EXPECTED 의 「Sustainability Report Title」과 같은 서식).
    assert firsts["가상 보통 문단 첫 줄"] == ("가상 보통 문단 첫 줄", True, False, 10.5, "000000", 3.0)
    assert len({firsts[t][3] for t in firsts}) == 4
    # 본문 줄은 단계와 무관하게 9.5 그대로.
    bodies = [row for row in rows if row is not None and row[0].startswith("가상 본문")]
    assert [row[3] for row in bodies] == [9.5] * 4


def test_heading_space_before_only_on_numbered_first_lines() -> None:
    paragraphs = [p for p in reopen(render_bilingual(HEADED)).paragraphs if p.text]
    before = {p.text: cast(Length | None, p.paragraph_format.space_before) for p in paragraphs}  # pyright: ignore[reportUnknownMemberType]
    assert before["1. 가상 전략"] is not None and before["1. 가상 전략"].pt == 6.0
    plain = before["가상 보통 문단 첫 줄"]
    assert plain is None or plain.pt == 0


@pytest.mark.parametrize(
    ("line", "level"),
    [
        ("1. 가상 전략", 1),
        ("Ⅰ. 가상 개요", 1),
        ("Ⅱ.가상 개요", 1),
        ("II. Made-up Overview", 1),
        ("1-1. 가상 목표", 2),
        ("1.1 Made-up Goal", 2),
        ("1.1. Made-up Goal", 2),
        ("1-1-1 가상 세부", 3),
        ("1.1.1 Made-up Detail", 3),
        ("가상 보통 문단", None),
        ("2.5 million tonnes were cut", None),  # 번호 뒤 영문 소문자 — 수치 문장
        ("2024. 가상 연도", None),  # 세 자리 넘는 수 — 연도
        ("1. we cut made-up emissions", None),
        ("I.e. a made-up note", None),  # 영문 로마 숫자는 뒤 빈칸 필수
        ("1. " + "가" * 90, None),  # 80자 넘음 — 번호 목록 문장
        ("", None),
    ],
)
def test_heading_level(line: str, level: int | None) -> None:
    assert docx_bilingual.heading_level(line) == level


def test_table_and_visual_first_lines_ignore_heading_numbers() -> None:
    rows = [
        seen(p)
        for p in reopen(render_bilingual("[TABLE 1]\n1. 가상 표 머리\n[VISUAL 1]\n1. 가상 그림 글\n")).paragraphs
    ]
    sizes = {row[0]: row[3] for row in rows if row is not None}
    assert sizes["1. 가상 표 머리"] == 9.0  # 표 소개 첫 줄 9.3(→ 9.0) 그대로
    assert sizes["1. 가상 그림 글"] == 9.0
