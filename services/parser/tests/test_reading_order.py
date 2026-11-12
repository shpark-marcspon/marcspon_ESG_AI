"""읽는 순서 복원."""

from docparse.document import parse_pdf
from docparse.reading_order import reading_order

from . import pdfbuild
from .conftest import put


def test_title_then_left_column_then_right_column():
    boxes = [
        [300, 100, 550, 200],  # 0 오른쪽 단 위
        [40, 100, 280, 150],  # 1 왼쪽 단 위
        [40, 20, 550, 60],  # 2 전폭 제목
        [40, 160, 280, 400],  # 3 왼쪽 단 아래
        [300, 205, 550, 400],  # 4 오른쪽 단 아래
    ]
    order, columns = reading_order(boxes, page_height=500)
    assert order == [2, 1, 3, 0, 4]
    assert columns == 2


def test_columns_are_not_interleaved_by_small_vertical_gaps():
    # 좌우 단의 문단 사이 틈이 같은 높이에 있어도 단을 먼저 가른다
    boxes = [[40, 100, 280, 200], [300, 100, 550, 200], [40, 206, 280, 300], [300, 206, 550, 300]]
    order, _ = reading_order(boxes, page_height=400)
    assert order == [0, 2, 1, 3]


def test_single_column_is_top_to_bottom_and_footer_goes_last():
    boxes = [[40, 760, 60, 770], [40, 300, 500, 400], [40, 100, 500, 200]]
    order, columns = reading_order(boxes, page_height=800)
    assert order == [2, 1, 0]
    assert columns == 1


def test_empty_page():
    assert reading_order([], page_height=800) == ([], 0)


def test_two_column_pdf_blocks_come_out_in_column_order(tmp_path):
    doc = pdfbuild.Doc()
    page = doc.new_page(width=600, height=400)
    put(page, 40, 40, "SYNTHETIC TITLE", size=20)
    for k in range(20):
        put(page, 40, 90 + 12 * k, f"left column line {k} of synthetic prose")
        put(page, 320, 90 + 12 * k, f"right column line {k} of synthetic prose")
    pdf = tmp_path / "synthetic_two_columns.pdf"
    doc.save(pdf)
    parsed = parse_pdf(pdf)
    texts = [b["text"] for b in sorted(parsed["blocks"], key=lambda b: b["order"])]
    assert texts[0] == "SYNTHETIC TITLE"
    assert texts[1].startswith("left column line 0") and "left column line 19" in texts[1]
    assert texts[2].startswith("right column line 0")
    assert parsed["blocks"][0]["kind"] == "heading"
    assert parsed["pages"][0]["columns"] == 2
