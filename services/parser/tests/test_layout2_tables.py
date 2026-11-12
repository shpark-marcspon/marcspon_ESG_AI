"""번역 판 `layout=2` 의 표 손질(밴드 TRD1 커밋 ②): L3 글자 보존, L5 세로 병합 행 머리, L6 단 넘는 글자 정렬 표.

합성 PDF 는 `layout2_doc`(쪽 넷)와 PB1 의 `baseline_doc`(판 둘)이다. 기본 판(1) 산출에는 단언하지 않는다(발주서 §0 라).
"""

import pytest

from docparse.balance import char_balance
from docparse.document import parse_pdf_places
from docparse.engine import open_pdf
from docparse.layout import page_chunks

from . import baseline_doc, layout2_doc

BUILDERS = {
    **{name: (lambda kw=kw: baseline_doc.build(**kw)) for name, kw in baseline_doc.VARIANTS.items()},
    **{name: (lambda kw=kw: layout2_doc.build(**kw)) for name, kw in layout2_doc.VARIANTS.items()},
}


@pytest.fixture(scope="module")
def parsed(tmp_path_factory):
    """판 이름 → (PDF 경로, 문서 모델). 번역 판으로 한 번씩."""
    folder = tmp_path_factory.mktemp("layout2-tables")
    out = {}
    for name, build in BUILDERS.items():
        path = folder / f"{name}.pdf"
        path.write_bytes(build())
        out[name] = (path, parse_pdf_places(path, layout=2)[0])
    return out


# ── L3 쪽 글자 보존 ─────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_l3_every_page_keeps_every_character_once(parsed, name):
    path, document = parsed[name]
    with open_pdf(path) as opened:
        for meta in document["pages"]:
            chunks, _ = page_chunks(opened[meta["page"] - 1], glyphs=True)
            missing, extra = char_balance(document, meta["page"], chunks)
            assert not missing and not extra, (meta["page"], dict(missing), dict(extra))
            blocks = [b["text"] for b in document["blocks"] if b["page"] == meta["page"] and b["kind"] != "table"]
            cells = [x for t in document["tables"] if t["page"] == meta["page"] for row in t["cells"] for x in row]
            assert meta["char_count"] == sum(len(s.replace(" ", "")) for s in blocks + cells)


def test_l3_out_of_cell_pieces_become_text_and_counted_once(parsed):
    document = parsed["layout2"][1]
    page4 = [b for b in document["blocks"] if b["page"] == 4]
    texts = [b.get("text") for b in page4]
    assert "Targets and results" in texts  # 위 괘선에 걸친 제목: 표 상자 안 1pt 지만 어느 칸에도 없다 → 글
    assert "19" not in texts  # 표 오른쪽 끝 밖 1.5pt 의 값: 칸에 들었으니 글 블록에 또 넣지 않는다
    tables = {t["id"]: t for t in document["tables"] if t["page"] == 4}
    assert any("19" in x for t in tables.values() for row in t["cells"] for x in row)
    # 안긴 표: 같은 조각은 작은 표에만. 큰 틀의 왼쪽 몸 칸은 비고 그 까닭이 notes 에 남는다
    frame = next(t for t in tables.values() if t["cells"][0][0] == "Frame left")
    inner = next(t for t in tables.values() if t["cells"][0][0] == "Inner")
    assert frame["cells"][1][0] == "" and "chunks_moved_to_inner_table:9" in frame["notes"]
    assert inner["cells"] == [["Inner", "2024", "2025"], ["Gas", "12", "11"], ["Oil", "7", "6"]]


# ── L5 세로 병합 행 머리 ────────────────────────────────────────────


def test_l5_row_heads_stay_in_their_rows(parsed):
    document = parsed["layout2"][1]
    table = next(t for t in document["tables"] if t["page"] == 2)
    want = [
        ["Group", "Sub", "Item", "Detail", "Unit", "2024", "2025"],
        ["Green goods trade", "Sales of green items", "", "", "t", "120", "130"],
        ["", "", "Home", "", "t", "100", "110"],
        ["", "", "Plant Alpha Overseas Unit", "", "t", "0", "0"],
        ["", "", "Plant Beta Overseas Unit", "", "t", "N/A", "0"],
        ["", "Purchases of green items", "", "", "t", "20", "25"],
        ["", "", "Home", "", "t", "18", "22"],
        ["", "", "Plant Alpha Overseas Unit", "", "t", "0", "0"],
        ["", "", "Plant Beta Overseas Unit", "", "t", "N/A", "3"],
    ]
    assert table["method"] == "lines" and table["cells"] == want


# ── L6 단 넘는 글자 정렬 표 ─────────────────────────────────────────


def test_l6_text_table_does_not_cross_the_column_gutter(parsed):
    document = parsed["layout2"][1]
    page = next(p for p in document["pages"] if p["page"] == 3)
    assert page["columns"] == 3
    tables = [t for t in document["tables"] if t["page"] == 3]
    assert len(tables) == 1 and tables[0]["method"] == "text" and tables[0]["bbox"][2] < 240  # 왼 단 안
    assert "cut_at_column_gutter" in tables[0]["notes"]
    middle = [b for b in document["blocks"] if b["page"] == 3 and b["kind"] == "paragraph" and b["bbox"][0] >= 300]
    returning = [b for b in middle if b["text"].startswith("The site returns more water")]
    assert len(returning) == 1  # 옆 단 문단이 줄 빠짐 없이 블록 하나
    assert returning[0]["text"].endswith("that the balance stays positive across the whole year.")
    assert "while the loss is made up by joint outside projects so" in returning[0]["text"]
