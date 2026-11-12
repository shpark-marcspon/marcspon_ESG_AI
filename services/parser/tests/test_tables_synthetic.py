"""합성 PDF 로 보는 표 추출 전략의 동작 (실제 보고서 값이 아니다)."""

from docparse.document import parse_pdf
from docparse.layout import page_chunks
from docparse.tables import extract_tables

from . import pdfbuild
from .conftest import put, seam


def _page(width=300, height=200):
    return pdfbuild.Doc().new_page(width=width, height=height)


def test_lines_strategy_builds_grid_from_horizontal_segments_only(synthetic_ruled_page):
    tables = extract_tables(seam(synthetic_ruled_page), "auto")
    assert len(tables) == 1
    t = tables[0]
    assert t.method == "lines" and t.status == "ok"
    assert t.grid == [
        ["Item", "Unit", "2023", "2024"],
        ["Alpha", "t", "1,200", "1,304"],
        ["", "kg", "15", "-"],  # 세로 병합 셀의 값은 첫 행에만
        ["Beta", "t", "7.5", "8.25"],
    ]
    assert t.header == {"rows": [0], "cols": [0, 1], "basis": "rows_before_first_numeric_row"}


def test_text_strategy_splits_side_by_side_tables(synthetic_ruleless_page):
    tables = extract_tables(seam(synthetic_ruleless_page), "auto")
    assert [t.method for t in tables] == ["text", "text"]
    assert all(t.status == "low_confidence" for t in tables)
    left, right = tables
    assert left.grid[0] == ["Left", "", "2023", "2024", "2025"]
    assert right.grid[0] == ["Right", "", "2023", "2024", "2025"]
    assert left.grid[4] == ["Emissions", "tCO2e", "1,000", "2,000", "3,000"]
    assert left.grid[3] == ["Waste recycled", "%", "90", "91", "-"]
    assert all(len(r) == 5 for r in left.grid + right.grid)


def test_lines_only_strategy_finds_nothing_without_rules(synthetic_ruleless_page):
    assert extract_tables(seam(synthetic_ruleless_page), "lines") == []


def test_number_text_is_copied_verbatim_and_footnote_mark_is_separated():
    page = _page()
    put(page, 40, 60, "1,304")
    w = pdfbuild.text_length("1,304", fontsize=8)
    put(page, 40 + w, 56, "5)", size=4)
    put(page, 40, 90, "Plant")
    w = pdfbuild.text_length("Plant", fontsize=8)
    put(page, 40 + w, 86, "2)", size=4)
    chunks, _ = page_chunks(seam(page))
    by_text = {c.text: c for c in chunks}
    assert by_text["1,304"].marks == ["5)"]  # 숫자 값은 그대로, 각주 위첨자는 따로
    assert "Plant2)" in by_text  # 글자 셀은 텍스트 계층 순서 그대로 붙인다


def test_slightly_smaller_text_is_body_text_not_a_footnote_mark():
    # 코스맥스 150쪽의 "- 직원 1인당 교육시간" 처럼 글자 크기가 조금 섞인 줄: 글자를 잃으면 안 된다
    page = _page()
    put(page, 40, 60, "- ", size=7.6)
    w = pdfbuild.text_length("- ", fontsize=7.6)
    put(page, 40 + w, 60, "staff hours", size=6.9)
    put(page, 40, 90, "12", size=8)
    w = pdfbuild.text_length("12", fontsize=8)
    put(page, 40 + w, 86, "km", size=4)  # 작은 글자지만 각주 표시 모양이 아니다
    chunks, _ = page_chunks(seam(page))
    texts = sorted(c.text for c in chunks)
    assert texts == ["- staff hours", "12", "km"] and all(not c.marks for c in chunks)


def test_invisible_tiny_text_is_dropped_and_counted():
    page = _page()
    put(page, 40, 60, "visible")
    put(page, 40, 80, "17,861", size=0.1)
    chunks, stats = page_chunks(seam(page))
    assert [c.text for c in chunks] == ["visible"]
    assert stats["tiny_text_spans_dropped"] == 1


def test_page_without_text_layer_is_marked_none_and_not_ocred(tmp_path):
    doc = pdfbuild.Doc()
    page = doc.new_page(width=300, height=200)
    page.insert_image((20, 20, 280, 180), gray=128, pixels=(60, 40))
    text_page = doc.new_page(width=300, height=200)
    put(text_page, 40, 60, "synthetic text page")
    pdf = tmp_path / "synthetic_scan.pdf"
    doc.save(pdf)
    parsed = parse_pdf(pdf)
    assert [p["text_layer"] for p in parsed["pages"]] == ["none", "present"]
    # 그림이 덮는 넓이 260 × 160 을 쪽 300 × 200 으로 나눈 값 (소수 셋째 자리)
    assert parsed["pages"][0]["image_coverage"] == 0.693
    assert not [b for b in parsed["blocks"] if b["page"] == 1]
    assert parsed["parser"]["ocr_used"] is False and parsed["parser"]["llm_used"] is False


def _full_width_ruled_page():
    """가로선이 표 전체 폭으로 한 줄씩만 그어진 합성 표: 괘선에서 열 경계를 얻을 수 없다."""
    page = _page()
    for i, (name, a, b) in enumerate((("Item", "2023", "2024"), ("Alpha", "10", "11"), ("Beta", "20", "21"))):
        put(page, 40, 60 + 14 * i, name)
        put(page, 180, 60 + 14 * i, a, right=True)
        put(page, 240, 60 + 14 * i, b, right=True)
        page.draw_line((40, 64 + 14 * i), (240, 64 + 14 * i), width=0.25)
    page.draw_line((40, 50), (240, 50), width=0.25)
    return page


def test_table_candidate_without_grid_is_failed_not_empty():
    # 괘선 기반만 쓰면 격자가 서지 않는다. 빈 표나 「표 없음」이 아니라 failed 로 남아야 한다.
    tables = extract_tables(seam(_full_width_ruled_page()), "lines")
    assert len(tables) == 1
    assert tables[0].status == "failed" and tables[0].method == "none" and tables[0].grid == []


def test_auto_falls_back_to_text_strategy_when_rules_give_no_columns():
    tables = extract_tables(seam(_full_width_ruled_page()), "auto")
    assert [(t.method, t.status) for t in tables] == [("text", "low_confidence")]
    assert tables[0].grid == [["Item", "2023", "2024"], ["Alpha", "10", "11"], ["Beta", "20", "21"]]
