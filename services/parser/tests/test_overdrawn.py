"""겹쳐 그려진 글자를 한 번만 뽑는 옵션 (`parse --dedupe-overdrawn`, 밴드 CT1).

합성(synthetic) PDF 만 쓴다. 실제 보고서의 값이 아니다.

pdfium 은 같은 글자가 가까운 자리에 또 그려지면 뒤의 것을 스스로 버린다 (글자 목록에 나오지 않는다). 다만 내용 스트림에서
몇 객체 앞까지만 돌아본다: 두 번 그린 것 사이에 다른 줄의 글 객체가 다섯 넘게 끼면 둘 다 나온다 (재 본 것. `test_pdfium_looks_back_only_a_few_text_objects`).
그래서 테스트마다 두 가지를 본다.
- 잇달아 그린 덧그림: 옵션과 무관하게 pdfium 이 버린다. 옵션을 켜도 산출이 같고 버렸다는 표시(`notes`)도 없다.
- 멀리 떨어져 그린 덧그림(`bury` 뒤에 그린 것): pdfium 이 못 버려 두 번 나온다. 옵션이 버리는 것은 이것이다.
원본(esg-lab `py/docparse/tests/test_overdrawn.py`)에서는 이 가운데 넷이 pdfium 엔진에서 「옵션을 끄면 두 번 뽑힌다」가 서지 않아 실패를 기대하는 표시가 붙어 있었다.
"""

import json

from docparse.cli import main
from docparse.document import parse_pdf, parse_pdf_places, validate
from docparse.layout import OVERDRAWN_OFFSET_RATIO

from . import pdfbuild
from .conftest import FONT, put

# 얼림: pdfium 이 덧그림을 찾아 돌아보는 범위. 사이에 낀 글 객체가 넷이면 버리고 다섯이면 못 버린다 (pypdfium2 5.14.0 에서 쟀다).
LOOKBACK = 4


def page_of():
    doc = pdfbuild.Doc()
    return doc, doc.new_page(width=400, height=300)


def bury(page, n=LOOKBACK + 1, y=150):
    """다른 줄의 글 객체를 n 개 놓는다. 이 뒤에 그리는 글은 앞서 그린 것과 pdfium 이 돌아보는 범위 밖으로 떨어진다."""
    for k in range(n):
        put(page, 40, y + 12 * k, f"filler line {k}")


def save(tmp_path, doc, name="synthetic_overdrawn.pdf"):
    path = tmp_path / name
    doc.save(path)
    return path


def texts(model):
    return [b["text"] for b in model["blocks"] if b["kind"] != "table"]


def count(model, needle):
    return sum(t.split().count(needle) for t in texts(model))


def test_glyphs_drawn_twice_at_the_same_place_come_out_once(tmp_path):
    # 잇달아 두 번: pdfium 이 스스로 버린다. 옵션이 할 일이 없다.
    doc, page = page_of()
    put(page, 40, 60, "Synthetic body line")
    put(page, 40, 280, "65")
    put(page, 40, 280, "65")
    pdf = save(tmp_path, doc, "synthetic_adjacent.pdf")
    off, on = parse_pdf(pdf), parse_pdf(pdf, dedupe_overdrawn=True)
    assert count(off, "65") == 1 and count(off, "Synthetic") == 1
    assert on == off and on["pages"][0]["notes"] == []
    # 멀리 떨어져 두 번: pdfium 이 못 버린다. 옵션이 버린다.
    doc, page = page_of()
    put(page, 40, 60, "Synthetic body line")
    put(page, 40, 280, "65")
    bury(page)
    put(page, 40, 280, "65")
    pdf = save(tmp_path, doc)
    off, on = parse_pdf(pdf), parse_pdf(pdf, dedupe_overdrawn=True)
    assert count(off, "65") == 2  # 옵션을 끄면 두 번 뽑힌다
    assert count(on, "65") == 1  # 한 번은 남는다 (둘 다 사라지면 안 된다)
    assert count(on, "Synthetic") == 1 and count(on, "filler") == LOOKBACK + 1
    assert on["pages"][0]["notes"] == ["overdrawn_spans_dropped:1"]
    assert validate(on) == []


def test_pdfium_looks_back_only_a_few_text_objects(tmp_path):
    seen = {}
    for between in (LOOKBACK, LOOKBACK + 1):
        doc, page = page_of()
        put(page, 40, 280, "65")
        bury(page, between)
        put(page, 40, 280, "65")
        pdf = save(tmp_path, doc, f"synthetic_between_{between}.pdf")
        seen[between] = (count(parse_pdf(pdf), "65"), count(parse_pdf(pdf, dedupe_overdrawn=True), "65"))
    assert seen == {
        LOOKBACK: (1, 1),
        LOOKBACK + 1: (2, 1),
    }  # 얼림: 넷이 끼면 pdfium 이 버리고, 다섯이 끼면 옵션이 버린다


def test_nearby_but_different_glyphs_stay(tmp_path):
    # 멀리 떨어져 그린 것: pdfium 이 손대지 않으므로 옵션의 규칙만 본다.
    doc, page = page_of()
    put(page, 40, 60, "1111 8888")  # 같은 글자가 바로 옆에 이어진 것은 겹친 것이 아니다
    put(page, 40, 80, "ABC")
    put(page, 40, 100, "77")
    put(page, 200, 100, "42", size=8)
    bury(page)
    put(page, 40, 80, "ABD")  # 같은 자리에서 시작하지만 다른 글이다: 통째로 남긴다
    put(page, 40, 100 + 3.0, "77")  # 석 pt 아래에 걸쳐 그린 다른 줄
    put(page, 200, 100, "42", size=12)  # 같은 기준점이지만 크기가 다르다
    pdf = save(tmp_path, doc)
    on = parse_pdf(pdf, dedupe_overdrawn=True)
    joined = " ".join(texts(on))
    assert "1111 8888" in joined
    assert count(on, "ABC") == 1 and count(on, "ABD") == 1
    assert count(on, "77") == 2 and joined.count("42") == 2
    assert on["pages"][0]["notes"] == []
    assert on == parse_pdf(pdf)
    # 잇달아 그린 것: pdfium 이 글자 단위로 버린다. `ABC` 위의 `ABD` 는 `A`·`B` 가 버려져 `ABCD` 가 되고,
    # 같은 기준점의 크기 다른 `42` 는 `4` 가 버려져 `42` 뒤에 큰 `2` 가 붙는다. 석 pt 아래의 `77` 은 남는다. 옵션은 여기서도 아무것도 버리지 않는다.
    doc, page = page_of()
    put(page, 40, 60, "1111 8888")
    put(page, 40, 80, "ABC")
    put(page, 40, 80, "ABD")
    put(page, 40, 100, "77")
    put(page, 40, 100 + 3.0, "77")
    put(page, 200, 100, "42", size=8)
    put(page, 200, 100, "42", size=12)
    pdf = save(tmp_path, doc, "synthetic_adjacent.pdf")
    off, on = parse_pdf(pdf), parse_pdf(pdf, dedupe_overdrawn=True)
    assert sorted(texts(off)) == ["1111 8888", "422", "77", "77", "ABCD"]  # 얼림: pdfium 이 버리고 남긴 글자
    assert on == off and on["pages"][0]["notes"] == []


def test_faux_bold_drawn_slightly_shifted_comes_out_once(tmp_path):
    size = 10
    shift = 0.03 * size  # 굵게 보이려고 0.3pt 어긋나게 한 번 더 그린 숫자
    assert shift < OVERDRAWN_OFFSET_RATIO * size
    # 잇달아 그린 굵은 글자: pdfium 이 스스로 버린다.
    doc, page = page_of()
    put(page, 40, 60, "1,234", size=size)
    put(page, 40 + shift, 60, "1,234", size=size)
    put(page, 40, 120, "Title", size=size)
    put(page, 40 + shift, 120 + shift, "Title", size=size)
    pdf = save(tmp_path, doc, "synthetic_adjacent.pdf")
    off, on = parse_pdf(pdf), parse_pdf(pdf, dedupe_overdrawn=True)
    assert count(off, "1,234") == 1 and count(off, "Title") == 1
    assert on == off and on["pages"][0]["notes"] == []

    def far(dx, dy, name):
        """`1,234` 와 `Title` 을 그리고, 멀리 떨어져 (dx, dy) 어긋나게 한 번씩 더 그린 PDF."""
        doc, page = page_of()
        put(page, 40, 60, "1,234", size=size)
        put(page, 40, 120, "Title", size=size)
        bury(page)
        put(page, 40 + dx, 60, "1,234", size=size)
        put(page, 40 + dx, 120 + dy, "Title", size=size)
        return save(tmp_path, doc, name)

    # 멀리 떨어져 그린 굵은 글자: 옵션이 버린다.
    pdf = far(shift, shift, "synthetic_far_bold.pdf")
    off, on = parse_pdf(pdf), parse_pdf(pdf, dedupe_overdrawn=True)
    assert count(off, "1,234") == 2 and count(on, "1,234") == 1
    assert count(off, "Title") == 2 and count(on, "Title") == 1
    assert on["pages"][0]["notes"] == ["overdrawn_spans_dropped:2"]
    # 문턱(글자 크기의 0.1배)의 바로 양쪽. 가로로만 넘어도, 세로로만 넘어도 겹쳐 그린 것이 아니다.
    inside, outside = (OVERDRAWN_OFFSET_RATIO - 0.01) * size, (OVERDRAWN_OFFSET_RATIO + 0.01) * size

    def notes(dx, dy):
        return parse_pdf(far(dx, dy, f"synthetic_far_{dx}_{dy}.pdf"), dedupe_overdrawn=True)["pages"][0]["notes"]

    assert notes(inside, inside) == ["overdrawn_spans_dropped:2"]
    assert notes(outside, inside) == []
    assert notes(inside, outside) == ["overdrawn_spans_dropped:1"]  # `1,234` 는 가로로만 어긋났다
    # 반 글자쯤 어긋난 것은 겹쳐 그린 것으로 보지 않는다
    pdf = far(0.25 * size, 0, "synthetic_far.pdf")
    on = parse_pdf(pdf, dedupe_overdrawn=True)
    assert on["pages"][0]["notes"] == [] and count(on, "1,234") == 2


def test_overdrawn_in_another_colour_and_in_a_table_cell(tmp_path, synthetic_ruled_page):
    # 표의 둘째 행에 덧그린다. 그 행을 그린 뒤에 두 행(글 객체 일곱)이 더 그려져 있어서 pdfium 이 버리지 못한다.
    page = synthetic_ruled_page
    put(page, 230 - 2, 74, "1,200", right=True)  # 표의 숫자 칸(행 1, 2023 열)에 같은 글자를 한 번 더
    x = 300 - 2 - pdfbuild.text_length("1,304", fontsize=8, font=FONT)
    page.insert_text((x, 74), "1,304", fontsize=8, font=FONT, color=(1, 0, 0))  # 색만 다른 덧그림
    pdf = save(tmp_path, page.parent)
    base = parse_pdf(pdf)
    on = parse_pdf(pdf, dedupe_overdrawn=True)
    assert base["tables"][0]["cells"][1] != ["Alpha", "t", "1,200", "1,304"]  # 끄면 칸의 글이 두 번이다
    assert on["tables"][0]["cells"][1] == ["Alpha", "t", "1,200", "1,304"]
    assert on["pages"][0]["notes"] == ["overdrawn_spans_dropped:2"]


def test_option_off_is_the_default_and_leaves_the_output_alone(tmp_path, capsys):
    doc, page = page_of()
    put(page, 40, 60, "Synthetic body line")
    put(page, 40, 280, "65")
    bury(page)
    put(page, 40, 280, "65")
    pdf = save(tmp_path, doc)
    assert main(["parse", str(pdf), "--out", str(tmp_path / "off")]) == 0
    assert main(["parse", str(pdf), "--out", str(tmp_path / "on"), "--dedupe-overdrawn"]) == 0
    assert main(["parse", str(pdf), "--out", str(tmp_path / "onp"), "--dedupe-overdrawn", "--places"]) == 0
    capsys.readouterr()
    off = json.loads((tmp_path / "off" / "document.json").read_text(encoding="utf-8"))
    on = json.loads((tmp_path / "on" / "document.json").read_text(encoding="utf-8"))
    assert off == parse_pdf(pdf) == parse_pdf(pdf, dedupe_overdrawn=False)
    assert all(not n.startswith("overdrawn") for p in off["pages"] for n in p["notes"])
    assert count(off, "65") == 2 and count(on, "65") == 1
    assert on == parse_pdf(pdf, dedupe_overdrawn=True)
    # 글자 자리(곁 파일)도 남은 한 번만 가리킨다
    assert (tmp_path / "onp" / "document.json").read_bytes() == (tmp_path / "on" / "document.json").read_bytes()
    places = json.loads((tmp_path / "onp" / "char-places.json").read_text(encoding="utf-8"))
    model, places2 = parse_pdf_places(pdf, dedupe_overdrawn=True)
    assert places == places2 and places["unlinked"] == []
    ids = {b["id"] for b in model["blocks"] if b.get("text") == "65"}
    assert len(ids) == 1 and len([c for c in places["containers"] if c["id"] in ids]) == 1
    # 잇달아 두 번 그린 PDF 에서는 pdfium 이 이미 버렸으므로 옵션을 켠 산출과 끈 산출이 글자까지 같다.
    doc, page = page_of()
    put(page, 40, 60, "Synthetic body line")
    put(page, 40, 280, "65")
    put(page, 40, 280, "65")
    pdf = save(tmp_path, doc, "synthetic_adjacent.pdf")
    assert main(["parse", str(pdf), "--out", str(tmp_path / "adjacent-off")]) == 0
    assert main(["parse", str(pdf), "--out", str(tmp_path / "adjacent-on"), "--dedupe-overdrawn"]) == 0
    capsys.readouterr()
    assert (tmp_path / "adjacent-on" / "document.json").read_bytes() == (
        tmp_path / "adjacent-off" / "document.json"
    ).read_bytes()
    assert count(json.loads((tmp_path / "adjacent-off" / "document.json").read_text(encoding="utf-8")), "65") == 1
