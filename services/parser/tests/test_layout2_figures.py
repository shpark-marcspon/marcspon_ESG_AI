"""번역 판 `layout=2` 의 도표 표 거름(밴드 TRD3): 막대 도표·연표가 괘선 표로 서지 않고 그 글자는 글 블록으로 간다.

합성 PDF 는 `figure_doc`(쪽 넷)이다. 기본 판(1)은 도표를 그대로 표로 낸다(BASE 동작 — 바이트 단언은 PB1 이 한다).
F6·F8 은 거름 함수에 가짜 그리기·가짜 표를 주어 문턱 경계와 실패 항목을 본다.
"""

import pytest

from docparse import tables as T
from docparse.balance import char_balance
from docparse.document import parse_pdf_places
from docparse.engine import Rect, open_pdf
from docparse.layout import Chunk, page_chunks
from docparse.table_model import METHOD_LINES, METHOD_NONE, STATUS_FAILED, Table
from docparse.tables import extract_tables

from . import figure_doc


@pytest.fixture(scope="module")
def pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("figures") / "figures.pdf"
    path.write_bytes(figure_doc.build())
    return path


@pytest.fixture(scope="module")
def document(pdf):
    return parse_pdf_places(pdf, layout=2)[0]


def _tables(document, page):
    return [t for t in document["tables"] if t["page"] == page]


def _block_text(document, page):
    return " ".join(b["text"] for b in document["blocks"] if b["page"] == page and b["kind"] != "table")


def _notes(document, page):
    return next(p["notes"] for p in document["pages"] if p["page"] == page)


def test_build_is_stable():
    assert figure_doc.build() == figure_doc.build()


# ── F1 막대 도표 ────────────────────────────────────────────────────


def test_f1_bar_chart_is_not_a_table_and_its_labels_stay_as_text(pdf, document):
    assert _tables(document, 1) == []
    text = _block_text(document, 1)
    for label in figure_doc.BAR_VALUES + figure_doc.BAR_YEARS:
        assert label in text
    assert [n for n in _notes(document, 1) if n.startswith("figure_table_dropped:")] == [
        "figure_table_dropped:lines:60.0,186.0,280.0,274.0"
    ]
    with open_pdf(pdf) as opened:  # 기본 판은 그대로 괘선 표를 낸다(BASE 동작)
        assert [t.method for t in extract_tables(opened[0], "auto")] == [METHOD_LINES]


# ── F2 연표 ─────────────────────────────────────────────────────────


def test_f2_timeline_is_not_a_table_and_its_text_stays(pdf, document):
    assert _tables(document, 2) == []
    text = _block_text(document, 2)
    for piece in figure_doc.TIMELINE_YEARS + figure_doc.TIMELINE_NOTES:
        assert piece in text
    assert any(n.startswith("figure_table_dropped:lines:") for n in _notes(document, 2))
    with open_pdf(pdf) as opened:
        assert [t.method for t in extract_tables(opened[1], "auto")] == [METHOD_LINES]


# ── F3·F4 진짜 표는 남는다 ──────────────────────────────────────────


def test_f3_ruled_table_with_header_fill_stays(document):
    tables = _tables(document, 3)
    assert len(tables) == 1 and tables[0]["method"] == "lines"
    assert tables[0]["cells"] == figure_doc.RULED
    assert not any(n.startswith("figure_") for n in _notes(document, 3))


def test_f4_plain_number_table_stays_a_text_table(document):
    tables = _tables(document, 4)
    assert len(tables) == 1 and tables[0]["method"] == "text"
    assert tables[0]["cells"] == figure_doc.PLAIN


# ── F5 글자 보존 ────────────────────────────────────────────────────


def test_f5_every_page_keeps_every_character_once(pdf, document):
    with open_pdf(pdf) as opened:
        for meta in document["pages"]:
            chunks, _ = page_chunks(opened[meta["page"] - 1], glyphs=True)
            missing, extra = char_balance(document, meta["page"], chunks)
            assert not missing and not extra, (meta["page"], dict(missing), dict(extra))


# ── F6 문턱 경계 (가짜 그리기·가짜 표) ──────────────────────────────


class _Page:
    def __init__(self, drawings):
        self.drawings = drawings

    def get_drawings(self):
        return self.drawings


def _fill(x0, y0, x1, y1):
    return {"items": [("re", Rect(x0, y0, x1, y1))], "rect": Rect(x0, y0, x1, y1), "fill": (0, 0, 1), "color": None}


def _curve(x0, y0, x1, y1):
    return {"items": [("c", None, None, None, None)], "rect": Rect(x0, y0, x1, y1), "fill": (1, 0, 0), "color": None}


def _chunk(x, y, text="v"):
    return Chunk(x, y, x + 8, y + 6, text, 6.0)


def _table(grid, row_y=(10, 30)):
    """상자 (0, 0, 200, 100). 칸 (i, 0) 마다 y=row_y[i] 의 조각 하나."""
    t = Table(bbox=[0, 0, 200, 100], grid=grid, method=METHOD_LINES)
    t.cell_chunks = {(i, 0): [_chunk(5, y)] for i, y in enumerate(row_y[: len(grid)])}
    return t


def _bars(n):
    """아랫변 90 을 같이 쓰고 높이가 다 다른 글 없는 채움 막대 n 개."""
    return [_fill(20 + 15 * k, 50 - k, 30 + 15 * k, 90) for k in range(n)]


def _kept(drawings, table, chunks=()):
    notes = []
    out = T._drop_figure_tables(_Page(drawings), [table], list(chunks), notes)
    return bool(out), notes


FULL = [["a", "b"], ["c", "d"]]


def test_f6_bar_run_threshold():
    n = T.FIGURE_BAR_RUN_MIN
    assert _kept(_bars(n - 1), _table(FULL))[0]
    kept, notes = _kept(_bars(n), _table(FULL))
    assert not kept and notes == ["figure_table_dropped:lines:0.0,0.0,200.0,100.0"]


def test_f6_bars_need_no_text_inside_and_two_heights():
    n = T.FIGURE_BAR_RUN_MIN
    assert _kept(_bars(n), _table(FULL), chunks=[_chunk(20, 70)])[0]  # 막대 하나에 글 → 칸 바탕
    same = [_fill(20 + 15 * k, 50, 30 + 15 * k, 90) for k in range(n)]
    assert _kept(same, _table(FULL))[0]  # 높이가 다 같으면 막대 줄이 아니다


def _grid(empty, total=10):
    """2행. 빈 칸이 empty 개, 각 행 첫 칸은 차 있다."""
    half = total // 2
    rest = ["x"] * (total - 2 - empty) + [""] * empty  # 첫 칸 둘을 뺀 나머지
    return [["x", *rest[: half - 1]], ["x", *rest[half - 1 :]]]


def test_f6_empty_ratio_threshold():
    curve = [_curve(0, 0, 4, 100)]  # 두 행에 다 닿음
    below = int(T.FIGURE_EMPTY_RATIO_MIN * 10) - 1
    at = int(T.FIGURE_EMPTY_RATIO_MIN * 10)
    assert sum(c == "" for r in _grid(at) for c in r) == at
    assert _kept(curve, _table(_grid(below)))[0]
    assert not _kept(curve, _table(_grid(at)))[0]


def test_f6_curve_needs_every_text_row_and_at_least_one_curve():
    sparse = _table(_grid(int(T.FIGURE_EMPTY_RATIO_MIN * 10)))
    assert _kept([], sparse)[0]  # 곡선 0 → 빈 칸만으로는 빼지 않는다
    assert _kept([_curve(0, 0, 4, 20)], sparse)[0]  # 첫 행에만 닿음(비율 0.5)
    assert not _kept([_curve(0, 0, 4, 40)], sparse)[0]


# ── F7 notes 없이 ───────────────────────────────────────────────────


def test_f7_extract_tables_without_notes(pdf):
    with open_pdf(pdf) as opened:
        assert extract_tables(opened[0], "auto", layout=2) == []
        assert len(extract_tables(opened[2], "auto", layout=2)) == 1


# ── F8 도표 상자 안의 실패 항목 ─────────────────────────────────────


def test_f8_failed_item_inside_a_figure_box_goes_too():
    def failed(box):
        return Table(bbox=box, grid=[], method=METHOD_NONE, status=STATUS_FAILED, notes=["grid_not_built"])

    inside, outside = failed([100, 40, 260, 80]), failed([300, 40, 400, 80])
    notes = []
    out = T._drop_figure_tables(_Page(_bars(T.FIGURE_BAR_RUN_MIN)), [_table(FULL), inside, outside], [], notes)
    assert out == [outside]
    assert notes[-1] == "figure_failed_dropped:1"
