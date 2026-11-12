"""글자 자리(`parse --places`, char-places.json). 합성(synthetic) PDF 로 본다. 문장과 숫자는 지어낸 것이다
(`59,498명` 은 발주서 MARC-TICK-35 §3 이 든 본보기 글자를 그대로 쓴 것이다).

기대하는 상자는 분해의 길과 따로, PDF 를 지을 때 글을 놓은 자리에서 셈한다 (`find`): 가로는 놓은 x 에 앞 글자들의 너비
(`pdfbuild.text_length`)를 더한 것이고, 세로는 놓은 바닥선이다. 분해기도 PDF 엔진도 거치지 않는다.
원본(esg-lab `py/docparse/tests/test_charplaces.py`)은 이 자리를 PDF 라이브러리의 글자 찾기로 얻었다.
숫자가 글의 어디인지는 테스트가 글자를 직접 찾아(`str.index`) 준다. docparse 에는 숫자를 알아보는 규칙이 없다.
"""

import json
import re
from pathlib import Path
from typing import NamedTuple

import pytest

from docparse import charplaces
from docparse.cli import main
from docparse.document import parse_pdf, parse_pdf_places, validate, validate_places
from docparse.layout import Chunk, page_chunks

from . import pdfbuild
from .conftest import hline, put, require_reports, seam

FIXTURE = Path(__file__).parent / "fixtures" / "char-places-utf16.json"
# pt. 글자 자리는 소수 한 자리로 반올림해 싣고(0.05), 엔진의 글자 상자는 글리프의 그림이 걸음보다 0.01em 남짓 더 나올 수 있다
# (크기 8 에서 0.11 까지 쟀다). 가장 좁은 글자의 너비(크기 8 의 `,` 2.2pt)보다 훨씬 좁아서 글자 하나가 밀리면 어긋난다.
TOL = 0.2
CENTER_PAD = 0.15  # 글자의 가운데가 상자 안인지 볼 때의 여유 (pt). 좌표를 소수 한 자리로 반올림해 싣기 때문이다

_TEXT_OP = re.compile(rb"BT (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) Tm /(\w+) (\S+) Tf <([0-9a-f]*)> Tj")


class Hit(NamedTuple):
    """놓은 글 안의 한 토막이 있어야 할 자리: 가로 범위, 바닥선, 글자 크기."""

    x0: float
    x1: float
    base: float
    size: float


def placed(page):
    """`pdfbuild` 가 이 쪽에 놓은 글 [(x, 바닥선, 글, 크기, 글꼴)]. 쪽이 적어 둔 글 연산자에서 읽는다 (돌리지 않은 글만)."""
    out = []
    for op in page.ops:
        m = _TEXT_OP.search(op)
        if not m:
            continue
        a, b, c, d, x, y = (float(v) for v in m.groups()[:6])
        assert (a, b, c, d) == (1, 0, 0, 1)
        font = m.group(7).decode("ascii")
        text = bytes.fromhex(m.group(9).decode("ascii")).decode("cp1252" if font == pdfbuild.LATIN else "utf-16-be")
        out.append((x, page.height - y, text, float(m.group(8)), font))
    return out


def find(page, needle):
    """쪽에 놓은 글에서 needle 이 나오는 자리 전부. 위에서 아래로, 왼쪽에서 오른쪽으로."""
    hits = []
    for x, base, text, size, font in placed(page):
        at = text.find(needle)
        while at >= 0:
            x0 = x + pdfbuild.text_length(text[:at], size, font)
            hits.append(Hit(x0, x0 + pdfbuild.text_length(needle, size, font), base, size))
            at = text.find(needle, at + 1)
    return sorted(hits, key=lambda h: (h.base, h.x0))


def u16(text):
    return len(text.encode("utf-16-le")) // 2


def span_of(text, needle, occurrence=1):
    """글에서 needle 이 occurrence 번째로 나오는 자리 (UTF-16 시작, 끝)."""
    at = -1
    for _ in range(occurrence):
        at = text.index(needle, at + 1)
    return u16(text[:at]), u16(text[: at + len(needle)])


def save(tmp_path, doc, name="synthetic.pdf"):
    path = tmp_path / name
    doc.save(path)
    return path


def parse(tmp_path, doc):
    pdf = save(tmp_path, doc)
    model, places = parse_pdf_places(pdf)
    # 옵션을 켜도 꺼도 문서 모델은 같고, 문서 모델의 스키마(모르는 필드 금지)를 통과한다. 글자 자리는 곁 파일에만 있다.
    assert json.dumps(parse_pdf(pdf), ensure_ascii=False) == json.dumps(model, ensure_ascii=False)
    assert validate(model) == [] and validate_places(places) == []
    assert places["source"] == model["source"]
    kinds = {b["id"]: "block" for b in model["blocks"] if b["kind"] != "table"}
    assert all(c["kind"] == kinds.get(c["id"], "cell") for c in places["containers"])
    return model, places, {c["id"]: c for c in places["containers"]}


def close_x(box, hit):
    return abs(box[0] - hit.x0) <= TOL and abs(box[2] - hit.x1) <= TOL


def on_line(box, hit):
    """상자가 그 글의 줄에 있는가: 바닥선이 상자 안이고, 상자의 높이가 한 줄의 것이다."""
    return box[1] < hit.base < box[3] and box[3] - box[1] < 1.5 * hit.size


def at(box, hit):
    return close_x(box, hit) and on_line(box, hit)


def one_block(model, containers, part):
    block = next(b for b in model["blocks"] if part in b.get("text", ""))
    return block, containers[block["id"]]


def text_in_box(page, box):
    """가운데가 상자 안에 든 글자를 왼쪽부터 이은 것. 분해의 길(`layout.page_chunks`)을 거치지 않고 엔진의 낱 글자를 따로 읽는다."""
    hit = []
    for block in seam(page).get_text_blocks(chars=True):
        for line in block["lines"]:
            for span in line["spans"]:
                for c in span["chars"]:
                    x0, y0, x1, y1 = c["bbox"]
                    if (
                        c["c"].strip()
                        and box[0] - CENTER_PAD <= (x0 + x1) / 2 <= box[2] + CENTER_PAD
                        and box[1] - CENTER_PAD <= (y0 + y1) / 2 <= box[3] + CENTER_PAD
                    ):
                        hit.append((x0, y0, c["c"]))
    return "".join(c for _x, _y, c in sorted(hit))


def test_every_table_cell_gets_the_box_of_its_own_text(tmp_path, synthetic_ruled_page):
    model, places, containers = parse(tmp_path, synthetic_ruled_page.parent)
    assert places["unlinked"] == [] and validate_places(places) == []
    table = model["tables"][0]
    assert table["method"] == "lines"
    filled = [(i, j, text) for i, row in enumerate(table["cells"]) for j, text in enumerate(row) if text]
    assert len(filled) == 15
    assert sorted(text for _i, _j, text in filled) == sorted(
        text for _x, _y, text, _s, _f in placed(synthetic_ruled_page)
    )
    for i, j, text in filled:
        cell = containers[f"{table['id']}:r{i}c{j}"]
        assert cell["kind"] == "cell" and cell["page"] == 1
        hits = find(synthetic_ruled_page, text)
        boxes = charplaces.span_boxes(cell)
        assert len(boxes) == 1
        # 같은 글자가 여러 칸에 있어도(`t`) 제 칸의 것 하나와만 맞는다.
        assert sum(1 for h in hits if at(boxes[0], h)) == 1, (i, j, text)
        assert boxes[0] == cell["bbox"]
    # 칸의 상자는 열 차례대로 왼쪽에서 오른쪽으로, 행 차례대로 위에서 아래로 놓인다.
    assert containers["p1-t1:r1c2"]["bbox"][2] < containers["p1-t1:r1c3"]["bbox"][0]
    assert containers["p1-t1:r1c2"]["bbox"][3] <= containers["p1-t1:r2c2"]["bbox"][1] + 1


def test_text_based_table_cells_get_boxes_too(tmp_path, synthetic_ruleless_page):
    model, places, containers = parse(tmp_path, synthetic_ruleless_page.parent)
    assert places["unlinked"] == []
    assert [t["method"] for t in model["tables"]] == ["text", "text"]
    left, right = model["tables"]
    a = containers[f"{left['id']}:r4c2"]
    b = containers[f"{right['id']}:r4c2"]
    hits = find(synthetic_ruleless_page, "1,000")
    assert len(hits) == 2 and at(a["bbox"], hits[0]) and at(b["bbox"], hits[1])
    assert a["bbox"][2] < b["bbox"][0]


def test_footnote_mark_is_outside_the_number_box(tmp_path, synthetic_ruled_page):
    page = synthetic_ruled_page
    hit = find(page, "1,304")[0]
    put(page, hit.x1, hit.base - 3, "5)", size=4)  # 숫자의 바로 오른쪽에, 바닥선보다 3pt 올려 쓴 작은 글자
    model, _places, containers = parse(tmp_path, page.parent)
    assert model["tables"][0]["cells"][1][3] == "1,304"
    assert model["tables"][0]["footnote_marks"] == [{"row": 1, "col": 3, "mark": "5)"}]
    assert at(containers["p1-t1:r1c3"]["bbox"], hit)


def test_number_in_a_paragraph_gets_its_own_box(tmp_path):
    doc = pdfbuild.Doc()
    page = doc.new_page(width=400, height=200)
    put(page, 40, 60, "Direct emissions were 12,345 tCO2e in total.")
    model, _places, containers = parse(tmp_path, doc)
    block, container = one_block(model, containers, "12,345")
    boxes = charplaces.span_boxes(container, *span_of(block["text"], "12,345"))
    assert len(boxes) == 1 and at(boxes[0], find(page, "12,345")[0])
    assert text_in_box(page, boxes[0]) == "12,345"


def test_same_number_twice_in_one_paragraph_keeps_two_places(tmp_path):
    doc = pdfbuild.Doc()
    page = doc.new_page(width=400, height=200)
    put(page, 40, 60, "Scope 1 was 500 t and Scope 2 was 500 t.")
    model, _places, containers = parse(tmp_path, doc)
    block, container = one_block(model, containers, "500")
    first = charplaces.span_boxes(container, *span_of(block["text"], "500", 1))
    second = charplaces.span_boxes(container, *span_of(block["text"], "500", 2))
    hits = find(page, "500")
    assert len(hits) == 2 and hits[0].x1 < hits[1].x0
    assert at(first[0], hits[0]) and at(second[0], hits[1])
    assert not close_x(second[0], hits[0])


def test_number_glued_to_hangul_gets_a_box_of_the_digits_only(tmp_path):
    doc = pdfbuild.Doc()
    page = doc.new_page(width=400, height=200)
    page.insert_text((40, 60), "임직원 59,498명이 참여했다 (가상).", fontsize=9, font=pdfbuild.KOREAN)
    model, _places, containers = parse(tmp_path, doc)
    block, container = one_block(model, containers, "59,498")
    assert "59,498명" in block["text"]
    box = charplaces.span_boxes(container, *span_of(block["text"], "59,498"))[0]
    number, unit = find(page, "59,498")[0], find(page, "명")[0]
    assert number.x1 == unit.x0
    # 한글 글꼴로 쓴 숫자의 상자 오른쪽은 기계의 대체 글꼴에 달려 있다 (맥에서 `8` 이 걸음보다 0.96pt 더 나왔다).
    # 그래서 오른쪽은 「숫자의 걸음을 다 덮고, 「명」의 가운데를 넘지 않는다」까지만 본다. 왼쪽과 줄은 좁게 본다.
    assert abs(box[0] - number.x0) <= TOL and on_line(box, number)
    assert number.x1 - TOL <= box[2] < (unit.x0 + unit.x1) / 2  # 「명」을 물지 않는다
    assert text_in_box(page, box) == "59,498"
    whole = charplaces.span_boxes(container, *span_of(block["text"], "59,498명"))[0]
    assert abs(whole[2] - unit.x1) <= TOL and whole[2] > box[2]
    assert abs(whole[0] - number.x0) <= TOL


def test_span_over_two_lines_gives_two_boxes(tmp_path):
    # 분해는 줄을 이을 때 빈칸을 끼운다. 그래서 줄 끝에서 끊긴 숫자 `1,` / `234` 는 글에서 `1, 234` 가 된다.
    doc = pdfbuild.Doc()
    page = doc.new_page(width=400, height=200)
    put(page, 40, 60, "The synthetic plant reported a total of 1,")
    put(page, 40, 70, "234 tonnes of waste in the year.")
    model, _places, containers = parse(tmp_path, doc)
    block, container = one_block(model, containers, "total of")
    assert "1, 234" in block["text"]
    start, end = span_of(block["text"], "1, 234")
    boxes = charplaces.span_boxes(container, start, end)
    assert len(boxes) == 2
    assert at(boxes[0], find(page, "1,")[0]) and at(boxes[1], find(page, "234")[0])
    assert boxes[0][3] <= boxes[1][1] + 1 and boxes[1][0] < boxes[0][0]
    assert charplaces.covered(container, start, end) == end - start - 1  # 끼운 빈칸 하나에는 좌표가 없다
    # 한 줄 안의 범위는 상자가 하나다.
    assert len(charplaces.span_boxes(container, *span_of(block["text"], "234"))) == 1


def test_wrapped_label_and_two_chunk_cells_in_a_text_table_keep_reading_order(tmp_path):
    # 글 기반 표: 첫 열의 이름이 두 줄로 꺾이고(줄바꿈 병합), 한 칸에 조각이 둘 들어간다.
    doc = pdfbuild.Doc()
    page = doc.new_page(width=400, height=300)
    rows = [
        ("Item", "2023", "2024"),
        ("Energy use", "100", "110"),
        ("Water", "5.5", "6.0"),
        ("Waste sent", "90", "91"),
        ("Emissions", "1,000", "2,000"),
    ]
    for i, r in enumerate(rows):
        base = 60 + 14 * i
        put(page, 40, base, r[0])
        put(page, 200, base, r[1], right=True)
        put(page, 260, base, r[2], right=True)
    put(page, 40, 60 + 14 * 3 + 8, "to landfill")  # `Waste sent` 의 둘째 줄 (값 없는 좁은 줄)
    model, places, containers = parse(tmp_path, doc)
    table = model["tables"][0]
    assert table["method"] == "text" and "wrapped_line_merged" in table["notes"]
    assert places["unlinked"] == []
    row = next(i for i, r in enumerate(table["cells"]) if r[0] == "Waste sent to landfill")
    cell = containers[f"{table['id']}:r{row}c0"]
    boxes = charplaces.span_boxes(cell)
    assert len(boxes) == 2 and at(boxes[0], find(page, "Waste sent")[0]) and at(boxes[1], find(page, "to landfill")[0])
    assert cell["bbox"] == [min(b[0] for b in boxes), boxes[0][1], max(b[2] for b in boxes), boxes[1][3]]
    landfill = charplaces.span_boxes(cell, *span_of("Waste sent to landfill", "landfill"))
    assert landfill == [[cell["runs"][-1]["x0"][3], boxes[1][1], boxes[1][2], boxes[1][3]]]
    assert at(landfill[0], find(page, "landfill")[0])


def test_pruned_empty_column_keeps_cell_ids_in_step_with_the_model(tmp_path):
    # 괘선 표: 글자가 없는 열 하나(없어진다)와 한 칸에 두 줄. 칸 번호는 정리된 뒤의 번호여야 한다.
    doc = pdfbuild.Doc()
    page = doc.new_page(width=420, height=300)
    xs = [40, 120, 160, 230, 300]
    rows = [("Item", "", "2023", "2024"), ("Alpha", "", "1,200", "1,304"), ("Beta", "", "7.5", "8.25")]
    y = 50
    for j in range(4):
        hline(page, xs[j], xs[j + 1], y, width=1.0)
    for i, r in enumerate(rows):
        put(page, xs[0] + 2, y + 10, r[0])
        put(page, xs[3] - 2, y + 10, r[2], right=True)
        put(page, xs[4] - 2, y + 10, r[3], right=True)
        if i == 1:
            put(page, xs[0] + 2, y + 19, "plant")  # `Alpha` 칸의 둘째 줄
        y += 24
        for j in range(4):
            hline(page, xs[j], xs[j + 1], y)
    model, places, containers = parse(tmp_path, doc)
    table = model["tables"][0]
    assert (
        table["method"] == "lines" and table["n_cols"] == 3 and table["cells"][1] == ["Alpha plant", "1,200", "1,304"]
    )
    assert places["unlinked"] == []
    assert at(containers[f"{table['id']}:r1c1"]["bbox"], find(page, "1,200")[0])
    assert at(containers[f"{table['id']}:r2c2"]["bbox"], find(page, "8.25")[0])
    two = charplaces.span_boxes(containers[f"{table['id']}:r1c0"])
    assert len(two) == 2 and at(two[0], find(page, "Alpha")[0]) and at(two[1], find(page, "plant")[0])


def test_runs_of_different_size_on_one_line_merge_and_precision_is_a_tenth_of_a_point(tmp_path):
    mixed = {
        "runs": [
            {"start": 0, "y0": 100, "y1": 110, "x0": [10, 15], "x1": [15, 20]},
            {"start": 2, "y0": 102, "y1": 109, "x0": [20], "x1": [24]},
        ]
    }
    assert charplaces.span_boxes(mixed, 0, 3) == [[10, 100, 24, 110]]
    assert charplaces.span_boxes(mixed, 3, 9) == []
    doc = pdfbuild.Doc()
    page = doc.new_page(width=400, height=200)
    put(page, 40.37, 60, "Total 12,345 units")
    model, _places, containers = parse(tmp_path, doc)
    block, container = one_block(model, containers, "12,345")
    box = charplaces.span_boxes(container, *span_of(block["text"], "12,345"))[0]
    hit = find(page, "12,345")[0]
    # 숫자 글자의 상자는 걸음과 같다(`test_pdfbuild.py`). 그래서 반올림의 몫 0.05 만 남는다.
    assert abs(box[0] - hit.x0) <= 0.051 and abs(box[2] - hit.x1) <= 0.051  # 소수 한 자리. 정수로 깎으면 어긋난다
    assert box[0] == round(box[0], 1) != round(box[0]) and box[2] == round(box[2], 1) != round(box[2])
    assert container["bbox"][0] < box[0] and container["bbox"][2] > box[2]


def test_default_parse_is_unchanged_and_carries_no_places(tmp_path, synthetic_ruled_page, capsys):
    pdf = save(tmp_path, synthetic_ruled_page.parent)
    plain = parse_pdf(pdf)
    with_places, places = parse_pdf_places(pdf)
    dump = lambda d: json.dumps(d, ensure_ascii=False, indent=1)  # noqa: E731
    assert dump(plain) == dump(with_places)
    assert '"runs"' not in dump(plain) and '"glyphs"' not in dump(plain) and "chunks" not in dump(plain)
    assert all(c.glyphs is None for c in page_chunks(seam(synthetic_ruled_page))[0])
    assert all(
        c.glyphs is not None and len(c.glyphs) == len(c.text)
        for c in page_chunks(seam(synthetic_ruled_page), glyphs=True)[0]
    )
    assert main(["parse", str(pdf), "--out", str(tmp_path / "off")]) == 0
    off = json.loads(capsys.readouterr().out)
    assert "char_places" not in off
    assert sorted(p.name for p in (tmp_path / "off").iterdir()) == ["document.json"]
    assert main(["parse", str(pdf), "--out", str(tmp_path / "on"), "--places"]) == 0
    on = json.loads(capsys.readouterr().out)
    assert (
        on["schema_valid"] is True
        and on["char_places"]["unlinked"] == 0
        and on["char_places"]["containers"] == len(places["containers"])
    )
    assert sorted(p.name for p in (tmp_path / "on").iterdir()) == ["char-places.json", "document.json"]
    assert (tmp_path / "on" / "document.json").read_bytes() == (tmp_path / "off" / "document.json").read_bytes()
    assert validate_places(json.loads((tmp_path / "on" / "char-places.json").read_text(encoding="utf-8"))) == []


def test_schema_rejects_a_broken_places_file(tmp_path, synthetic_ruled_page):
    _model, places, _ = parse(tmp_path, synthetic_ruled_page.parent)
    assert validate_places(places) == []
    places["containers"][0]["runs"][0].pop("x1")
    places["unit"] = "codepoint"
    assert len(validate_places(places)) == 2


def glyph_chunk(text, x=10.0, y0=100.0, y1=110.0):
    """글자마다 폭 5pt(보충 평면 글자는 10pt)인 가짜 조각. 빈칸에는 상자가 없다."""
    glyphs = []
    for ch in text:
        w = 10.0 if ord(ch) > 0xFFFF else 5.0
        glyphs.append(None if ch == " " else (x, y0, x + w, y1))
        x += w
    return Chunk(10.0, y0, x, y1, text, 10.0, [], glyphs)


def test_offsets_are_utf16_units_like_javascript_strings():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    text = fixture["text"]
    assert any(ord(ch) > 0xFFFF for ch in text) and any("가" <= ch <= "힣" for ch in text)
    made, failed = charplaces.build_container("p1-b1", "block", 1, text, [glyph_chunk(text)])
    assert failed is None and made == fixture["container"]
    assert len(made["runs"][0]["x0"]) == u16(text) > len(text)
    for want in fixture["expect"]:
        start, end = span_of(text, want["raw"])
        assert (start, end) == (want["start"], want["end"])
        assert charplaces.span_boxes(made, start, end) == want["boxes"]
    # 코드 포인트로 센 자리(틀린 단위)는 다른 글자를 가리킨다.
    wrong = text.index("59,498")
    assert wrong != fixture["expect"][0]["start"]


def test_container_is_unlinked_when_text_and_glyphs_do_not_line_up():
    chunk = glyph_chunk("12 %")
    assert charplaces.build_container("x", "block", 1, "12%", [chunk]) == (
        None,
        {"id": "x", "page": 1, "reason": "text_differs_from_chunks"},
    )
    chunk.glyphs = None
    assert charplaces.build_container("x", "block", 1, "12 %", [chunk])[1]["reason"] == "glyphs_not_aligned"


@pytest.mark.reports
@pytest.mark.parametrize(
    "report,pages", [("kb_2025_databook_kor.pdf", [10, 11, 12]), ("samsung_2026_kor.pdf", [70, 71])]
)
def test_real_pages_parse_the_same_with_places_and_link_every_container(report, pages):
    pdf = require_reports() / report
    plain = parse_pdf(pdf, pages=pages)
    with_places, places = parse_pdf_places(pdf, pages=pages)
    assert json.dumps(plain, ensure_ascii=False) == json.dumps(with_places, ensure_ascii=False)
    assert validate_places(places) == [] and places["unlinked"] == []
    texts = {b["id"]: b["text"] for b in plain["blocks"] if b["kind"] != "table"}
    texts.update(
        {
            f"{t['id']}:r{i}c{j}": c
            for t in plain["tables"]
            for i, row in enumerate(t["cells"])
            for j, c in enumerate(row)
            if c
        }
    )
    assert set(texts) == {c["id"] for c in places["containers"]}
    for c in places["containers"]:
        last = c["runs"][-1]
        assert last["start"] + len(last["x0"]) == u16(texts[c["id"]])
