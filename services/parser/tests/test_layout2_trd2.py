"""번역 판 `layout=2` 의 손질(밴드 TRD2 커밋 ①, MARC-ISSUE-422 의 1·2·4). 기본 판(1) 산출에는 단언하지 않는다.

R1 내용 키는 쪽 범위 분해에 흔들리지 않는다: 글 블록의 해시 종류는 "text" 하나다(heading·paragraph 는 문서 전체 본문
   글자 크기에 기대어, 쪽을 골라 분해하면 바뀔 수 있다).
R2 표 밖 숫자 조각의 각주 위첨자는 블록 글에 남고(조각 글 바로 뒤), 글자 자리 그릇이 그 글자 상자까지 갖는다.
R3 단 틈 자르기에서 남은 칸이 빈 글이라 걷히는 행·열의 조각은 칸에서 빠져 글 블록으로 간다(KeyError 0). 빈 글 조각은
   PDF 길(`layout._finish`)로는 생기지 않아 손으로 지은 조각으로 잰다.
R4 기본 판(1)은 R2 의 PDF 에서도 BASE 그대로다(위첨자는 블록 글에 붙지 않는다).
"""

import pytest

from docparse import tables_text
from docparse.balance import char_balance
from docparse.document import parse_pdf_places
from docparse.engine import open_pdf
from docparse.layout import Chunk, page_chunks
from docparse.table_model import Table

from . import pdfbuild
from .layout2_doc import RAISE, SUP, _end, _put

FILLER = "Small print fills the first page so that the body size of the whole report stays small."


def _key_flip_pdf():
    """1쪽은 8pt 본문이 많고 2쪽은 11pt 짧은 줄 + 11pt 긴 문단. 전 쪽 분해에서는 2쪽 짧은 줄이 제목(본문 8pt 의
    1.25 배 넘음), 2쪽만 분해하면 본문이 11pt 라 문단이 된다."""
    doc = pdfbuild.Doc()
    page = doc.new_page(600, 800)
    for k in range(30):
        _put(page, 40, 100 + 18 * k, FILLER, size=8)
    page = doc.new_page(600, 800)
    _put(page, 40, 100, "Water use", size=11)
    lines = [
        "Water withdrawal is measured at every site and reported",
        "once a year together with the discharge figures and the",
        "recycling rate so that the trend can be followed easily.",
    ]
    for k, line in enumerate(lines):
        _put(page, 40, 140 + 14 * k, line, size=11)
    return doc.tobytes()


def _superscript_pdf():
    """표 밖 숫자 「12,345」 바로 뒤에 위첨자 「1)」(숫자 조각의 marks 로 떼어지는 꼴)."""
    doc = pdfbuild.Doc()
    page = doc.new_page(600, 800)
    _put(page, 40, 120, "Emissions fell to")
    _put(page, 40, 160, "12,345")
    _put(page, _end(40, "12,345") + 0.2, 160 - RAISE, "1)", size=SUP)
    _put(page, 300, 160, "units in the year.")
    return doc.tobytes()


@pytest.fixture(scope="module")
def key_flip(tmp_path_factory):
    path = tmp_path_factory.mktemp("trd2-keys") / "keys.pdf"
    path.write_bytes(_key_flip_pdf())
    return path


@pytest.fixture(scope="module")
def superscript(tmp_path_factory):
    path = tmp_path_factory.mktemp("trd2-sup") / "sup.pdf"
    path.write_bytes(_superscript_pdf())
    return path


def test_r1_keys_do_not_move_with_the_page_range(key_flip):
    whole, _ = parse_pdf_places(key_flip, layout=2)
    part, _ = parse_pdf_places(key_flip, pages=[2], layout=2)
    on_two = [b for b in whole["blocks"] if b["page"] == 2]
    assert [b["kind"] for b in on_two] == ["heading", "paragraph"]
    assert [b["kind"] for b in part["blocks"]] == ["paragraph", "paragraph"]  # 갈래가 실제로 바뀌는 꼴
    assert [(b["id"], b["key"]) for b in part["blocks"]] == [(b["id"], b["key"]) for b in on_two]


def test_r2_superscript_after_a_number_stays_in_the_block_text(superscript):
    document, places = parse_pdf_places(superscript, layout=2)
    block = next(b for b in document["blocks"] if b["text"].startswith("12,345"))
    assert block["text"] == "12,3451)"
    with open_pdf(superscript) as opened:
        chunks, _ = page_chunks(opened[0], glyphs=True)
    assert [c.marks for c in chunks if c.text == "12,345"] == [["1)"]]
    assert char_balance(document, 1, chunks) == ({}, {})
    assert places["unlinked"] == []
    box = next(c for c in places["containers"] if c["id"] == block["id"])
    assert sum(len(r["x0"]) for r in box["runs"]) == len("12,3451)")
    assert box["bbox"][2] > _end(40, "12,345")  # 위첨자 글자 상자까지


def test_r3_cut_at_gutters_sends_chunks_of_pruned_cells_to_text(monkeypatch):
    def chunk(x0, y0, text):
        return Chunk(x0, y0, x0 + 10, y0 + 10, text, 9)

    a, b, c, d = chunk(20, 10, "Alpha"), chunk(20, 30, "Beta"), chunk(45, 10, "X"), chunk(45, 30, "Y")
    empty, gone = chunk(65, 10, ""), chunk(105, 30, "Gone")
    table = Table(
        bbox=[20, 10, 115, 40],
        grid=[["Alpha", "X", ""], ["Beta", "Y", "Gone"]],
        method="text",
        status="low_confidence",
        notes=[],
        cell_chunks={(0, 0): [a], (1, 0): [b], (0, 1): [c], (1, 1): [d], (0, 2): [empty], (1, 2): [gone]},
    )
    monkeypatch.setattr(tables_text, "column_gutters", lambda *_args: [(90, 100)])
    monkeypatch.setattr(tables_text, "_continues_a_paragraph", lambda *_args: True)
    tables, removed = tables_text.cut_at_gutters(table, [a, b, c, d, empty, gone], 800)
    assert [t.grid for t in tables] == [[["Alpha", "X"], ["Beta", "Y"]]]
    assert {id(x) for x in removed} == {id(empty), id(gone)}
    kept = {id(x) for cs in tables[0].cell_chunks.values() for x in cs}
    assert kept | {id(x) for x in removed} == {id(x) for x in (a, b, c, d, empty, gone)}  # 조각 보존
    assert not kept & {id(x) for x in removed}


def test_r4_the_default_layout_keeps_the_superscript_out_of_the_block(superscript):
    document, places = parse_pdf_places(superscript)
    assert [b["text"] for b in document["blocks"] if b["text"].startswith("12,345")] == ["12,345"]
    assert places["unlinked"] == []


def _span(text, x0, size, sup, drop=0):
    chars = [{"c": ch, "bbox": [x0 + 4 * k, 100.0, x0 + 4 * k + 4, 100.0 + size]} for k, ch in enumerate(text)]
    box = (x0, 100.0, x0 + 4 * len(text), 100.0 + size)
    return (text, box, size, sup, chars[: len(chars) - drop])


def test_r2_the_same_span_superscript_keeps_its_glyph_boxes():
    """`layout._finish`: 같은 줄 span 의 위첨자가 숫자 뒤 marks 로 떼어질 때 그 글자 상자를 mark_glyphs 로 남긴다.
    위첨자 글자 상자가 하나라도 모자라면 None(지어내지 않음)."""
    from docparse import layout

    sup = _span("1)", 64.0, 5.0, True)
    chunk = layout._finish([_span("12,345", 40.0, 9.0, False), sup])
    assert chunk.text == "12,345" and chunk.marks == ["1)"]
    assert chunk.mark_glyphs == [tuple(c["bbox"]) for c in sup[4]]
    short = layout._finish([_span("12,345", 40.0, 9.0, False), _span("1)", 64.0, 5.0, True, drop=1)])
    assert short.marks == ["1)"] and short.mark_glyphs is None
