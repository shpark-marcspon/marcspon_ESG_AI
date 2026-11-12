"""엔진 이음매: pdfium 엔진이 지어낸 PDF 를 뜻대로 읽는가 (밴드 PD2. 원본은 esg-lab `py/docparse/tests/test_engine.py`, 커밋 2e2c2c4).

원본은 같은 PDF 를 두 엔진으로 읽어 나란히 견줬다. 여기는 엔진이 pdfium 하나라 견줄 상대가 없다.
기대 값은 `pdfbuild` 에 준 좌표, 글자 너비표(`pdfbuild.text_length`), 연산자의 뜻, 문턱값의 뜻에서 끌어낸다.

글꼴은 파일을 심지 않는다. `LATIN`(Helvetica)의 글자 걸음은 너비표와 같고, 글자 상자의 세로는 pdfium 이 품은 대체 글꼴의 것이라
「바닥선이 상자 안에 있다」까지만 본다. `KOREAN` 글꼴로 쓴 ASCII 글자의 상자 오른쪽은 기계의 대체 글꼴에 달려 있어 보지 않는다.
"""

import ast
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

import docparse.engine
from docparse.cli import main
from docparse.document import ParseError, parse_pdf
from docparse.engine import DEFAULT_ENGINE, ENGINES, open_pdf

from . import pdfbuild
from .pdfbuild import KOREAN, LATIN

NEAR = 0.002  # pt. 엔진은 좌표를 단정밀도로 셈한다: 끝자리만 다르다
EDGE = 0.005  # em. 문턱의 양쪽을 볼 때 문턱에서 떨어지는 거리 (크기 8·10·20 에서 0.001 도 섰다. 기계가 달라도 서도록 다섯 배를 둔다)
# 글리프의 그림이 걸음보다 오른쪽으로 나오는 글자(`A`·`f`·`r` 등)의 상자 오른쪽이 걸음보다 넓은 만큼의 한도 (em. 잰 것은 0.014 까지)
OVERHANG = 0.02


def new_page(doc, width=400, height=300):
    return doc.new_page(width=width, height=height)


def put(page, x, y, text, size=10, font=LATIN, **options):
    page.insert_text((x, y), text, fontsize=size, font=font, **options)


def width_of(text, size=10, font=LATIN):
    return pdfbuild.text_length(text, fontsize=size, font=font)


def save(tmp_path, doc, name="engine.pdf", **options):
    path = tmp_path / name
    doc.save(path, **options)
    return path


def read(path, what):
    """what(첫 쪽)."""
    with open_pdf(path) as doc:
        return what(doc[0])


def lines_of(page):
    return [
        [(s["text"], round(s["size"], 3)) for s in line["spans"]]
        for block in page.get_text_blocks()
        for line in block["lines"]
    ]


def spans_of(page):
    return [[s["text"] for s in line["spans"]] for block in page.get_text_blocks() for line in block["lines"]]


def blocks_of(page):
    """[블록: [줄: [스팬의 글]]]"""
    return [[[s["text"] for s in line["spans"]] for line in block["lines"]] for block in page.get_text_blocks()]


def blocks_of_text(blocks):
    return ["".join(s["text"] for line in b["lines"] for s in line["spans"]) for b in blocks]


def words_of(page):
    return [(w[4], w[:4]) for w in page.get_words()]


def drawings_of(page):
    def hexa(c):
        return None if c is None else "#{:02x}{:02x}{:02x}".format(*tuple(round(v * 255) for v in c))

    return [
        (
            "".join(it[0][0] for it in d["items"]),
            tuple(d["rect"]),
            hexa(d.get("fill")),
            hexa(d.get("color")),
            round(d["width"], 3) if d.get("width") is not None else None,
        )
        for d in page.get_drawings()
    ]


def assert_boxes_near(a, b, tol=NEAR):
    assert len(a) == len(b), (a, b)
    for x, y in zip(a, b, strict=False):
        assert all(abs(u - v) <= tol for u, v in zip(x, y, strict=False)), (x, y)


def assert_latin_word(word, text, x, baseline, size=10, overhang=False):
    """`LATIN` 글꼴로 (x, baseline) 에 놓인 낱말의 상자: 가로는 너비표, 세로는 바닥선이 상자 안.

    overhang: 끝 글자의 그림이 걸음보다 오른쪽으로 나오는 낱말이면 오른쪽 끝을 그 한도 안에서 본다.
    """
    got, (x0, y0, x1, y1) = word
    assert got == text
    assert abs(x0 - x) <= NEAR, (text, x0, x)
    end = x + width_of(text, size)
    if overhang:
        assert end - NEAR <= x1 <= end + OVERHANG * size, (text, x1, end)
    else:
        assert abs(x1 - end) <= NEAR, (text, x1, end)
    assert y0 < baseline < y1 and y1 - y0 < 1.5 * size, (text, y0, baseline, y1)


def korean_box(x, baseline, count, size=10):
    """`KOREAN` 글꼴의 한글 `count` 자가 (x, baseline) 에서 시작할 때의 상자 (글꼴 사전의 오름 0.88, 내림 0.12, 너비 1em)."""
    return (x, baseline - 0.88 * size, x + count * size, baseline + 0.12 * size)


# ── 고르기 ────────────────────────────────────────────────────────────────


def test_default_engine_is_pymupdf(tmp_path):
    """엔진은 pdfium 하나다. 고르는 인자는 CLI 에 없다. (이름은 원본의 것을 그대로 뒀다.)"""
    assert DEFAULT_ENGINE == "pdfium" and docparse.engine.DEFAULT_ENGINE == "pdfium"
    assert ENGINES == ("pdfium",)
    doc = pdfbuild.Doc()
    put(new_page(doc), 40, 60, "Default engine")
    pdf = save(tmp_path, doc)
    with open_pdf(pdf) as opened:
        assert type(opened).__module__ == "docparse.engine.pdfium_engine"
    assert main(["parse", str(pdf), "--out", str(tmp_path / "plain")]) == 0
    assert (tmp_path / "plain" / "document.json").is_file()
    with pytest.raises(SystemExit):
        main(["parse", str(pdf), "--out", str(tmp_path / "named"), "--engine", "pdfium"])
    assert not (tmp_path / "named").exists()


def test_unknown_engine_is_refused(tmp_path):
    with pytest.raises(ValueError):
        open_pdf(tmp_path / "x.pdf", "ghostscript")
    with pytest.raises(ValueError):
        open_pdf(tmp_path / "x.pdf", "pymupdf")  # 원본의 다른 엔진 이름도 이제 모르는 이름이다


def _imported_modules(source):
    """파이썬 글이 import 하는 모듈 이름들 (AST 로 본다. 문자열·주석 속의 낱말은 잡히지 않는다)."""
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_rules_do_not_import_pymupdf():
    """`services/parser` 아래의 어느 파이썬 파일도 pymupdf(옛 이름 fitz)를 import 하지 않는다. 테스트 파일도 든다."""
    banned = {"pymupdf", "fitz"}

    def hits(source):
        return [name for name in _imported_modules(source) if name.split(".")[0] in banned]

    probe = "\n".join(
        [
            "im" + "port fitz",
            "def f():\n    fr" + "om pymupdf.utils import x",
            "# 주석의 pymupdf",
            "s = 'fitz'",
            "import os",
        ]
    )
    assert hits(probe) == ["fitz", "pymupdf.utils"]  # 훑는 법이 듣는다는 확인
    root = Path(docparse.engine.__file__).resolve().parents[2]
    files = [p for p in root.rglob("*.py") if ".venv" not in p.relative_to(root).parts]
    names = {str(p.relative_to(root)) for p in files}
    assert {"docparse/engine/pdfium_engine.py", "docparse/cli.py", "tests/pdfbuild.py", "tests/test_engine.py"} <= names
    users = sorted(str(p.relative_to(root)) for p in files if hits(p.read_text(encoding="utf-8")))
    assert users == []


def test_pdfium_path_runs_without_pymupdf(tmp_path):
    """pymupdf 를 import 할 수 없게 막은 프로세스에서 `parse`(자리·렌더 포함)와 `render` 가 끝까지 돈다.

    `score` 는 정답 표와 원본 PDF 가 있어야 돌아서 여기서 부르지 않는다. 도표 쪽 명령 넷은 이 저장소에 아직 없다.
    """
    doc = pdfbuild.Doc()
    page = new_page(doc)
    put(page, 40, 60, "Blocked import 12.5")
    page.draw_rect((40, 100, 60, 180), fill=(0.9, 0.5, 0.1), color=None)
    pdf = save(tmp_path, doc)
    out = tmp_path / "out"
    script = (
        "import importlib, sys\n"
        "sys.modules['pymupdf'] = None\nsys.modules['fitz'] = None\n"
        "for name in ('pymupdf', 'fitz'):\n"
        "    try:\n"
        "        importlib.import_module(name)\n"
        "    except ImportError:\n"
        "        continue\n"
        "    sys.exit(90)\n"  # 막기가 듣지 않는다
        "from docparse.cli import main\n"
        f"pdf, out = {str(pdf)!r}, {str(out)!r}\n"
        "codes = [main(['parse', pdf, '--out', out, '--places', '--render', '--dpi', '50']),\n"
        "         main(['render', pdf, '--out', out + '/again', '--dpi', '50'])]\n"
        "assert not [k for k, v in sys.modules.items() if k.split('.')[0] in ('pymupdf', 'fitz') and v is not None], 'pymupdf 가 불려 왔다'\n"
        "sys.exit(max(codes))\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(docparse.engine.__file__).resolve().parents[2],
    )
    assert done.returncode == 0, done.stderr[-2000:]
    model = json.loads((out / "document.json").read_text(encoding="utf-8"))
    assert "Blocked import 12.5" in " ".join(b.get("text", "") for b in model["blocks"])
    assert (out / "char-places.json").stat().st_size > 0
    for png in (out / "pages" / "p0001.png", out / "again" / "p0001.png"):
        data = png.read_bytes()
        assert pdfbuild.png_size(data) == (
            math.ceil(400 * 50 / 72),
            math.ceil(300 * 50 / 72),
        )  # 400×300 pt 를 50 dpi 로 (pdfium 은 올림한다)
        # 채운 네모 (40, 100)~(60, 180) 의 가운데 (50, 140)pt → (34, 97)점: 주황
        r, g, b = pdfbuild.png_pixel(data, 34, 97)[:3]
        assert r > 200 and b < 60, (r, g, b)


# ── 글자, 줄, 스팬, 낱말 ─────────────────────────────────────────────────


def test_char_boxes_and_sizes_agree(tmp_path):
    doc = pdfbuild.Doc()
    page = new_page(doc)
    put(page, 40, 60, "Alpha 12.5%", size=10)
    put(page, 40, 90, "한글 표 1,304", size=9, font=KOREAN)
    pdf = save(tmp_path, doc)

    def chars(p):
        return [
            (c["c"], tuple(c["bbox"]), s["size"])
            for b in p.get_text_blocks(chars=True)
            for line in b["lines"]
            for s in line["spans"]
            for c in s["chars"]
        ]

    got = read(pdf, chars)
    latin, korean = "Alpha 12.5%", "한글 표 1,304"
    assert [c[0] for c in got] == list(latin + korean)
    assert [c[2] for c in got] == [10.0] * len(latin) + [9.0] * len(korean)
    for k, (c, (x0, y0, x1, y1), _size) in enumerate(got[: len(latin)]):
        start, end = 40 + width_of(latin[:k]), 40 + width_of(latin[: k + 1])
        assert abs(x0 - start) <= NEAR, (c, x0, start)
        if c == "A":  # 그림이 걸음보다 오른쪽으로 나오는 글자
            assert end - NEAR <= x1 <= end + OVERHANG * 10, (c, x1, end)
        else:
            assert abs(x1 - end) <= NEAR, (c, x1, end)
        assert y0 < 60 < y1 and y1 - y0 < 15, (c, y0, y1)
    for k, (c, box, _size) in enumerate(got[len(latin) :]):
        start = 40 + width_of(korean[:k], 9, KOREAN)
        assert abs(box[0] - start) <= NEAR, (c, box, start)
        assert abs(box[1] - (90 - 0.88 * 9)) <= NEAR and abs(box[3] - (90 + 0.12 * 9)) <= NEAR, (c, box)
        if c in "한글표" or c == " ":  # 숫자·기호의 오른쪽은 기계의 대체 글꼴에 달려 있어 보지 않는다
            assert abs(box[2] - (start + width_of(c, 9, KOREAN))) <= NEAR, (c, box)


def test_gaps_make_spaces_and_line_breaks_the_same_way(tmp_path):
    """글자 사이의 틈: 0.1em 은 붙고, 0.3em 은 공백 하나, 0.5em 은 공백이 따로 스팬, 0.9em 은 새 줄. 한글 뒤의 틈에는 공백을 넣지 않는다."""
    # 틈은 그 글 「뒤」의 것이다: AB·0.1·CD·0.28·EF·0.5·GH·0.9·IJ
    # (원본의 0.3 은 넓은 공백의 문턱 바로 위라 단정밀도 끝자리에 따라 흔들린다. 0.28 로 옮겼다. 문턱은 아래 경계 테스트가 본다.)
    doc = pdfbuild.Doc()
    page = new_page(doc)
    x = 40
    for text, gap in (("AB", 0.1), ("CD", 0.28), ("EF", 0.5), ("GH", 0.9), ("IJ", 0.0)):
        put(page, x, 60, text)
        x += width_of(text) + gap * 10
    put(page, 40, 100, "가나", font=KOREAN)
    put(page, 40 + width_of("가나", font=KOREAN) + 4, 100, "다라", font=KOREAN)  # 0.4em 뒤: 같은 줄, 공백 없음
    put(page, 40, 140, "Mm")
    put(page, 40 + width_of("Mm"), 140 - 3, "2", size=6)  # 올려 쓴 작은 글자: 같은 줄, 다른 스팬
    put(page, 40, 180, "Q")
    put(page, 40.4, 180, "Q")  # 같은 글자를 0.04em 옆에 또: 한 번만
    put(page, 395, 220, "ZZZZ")  # 쪽 밖으로 나가는 글자는 빠진다
    pdf = save(tmp_path, doc)
    got = read(pdf, lines_of)
    flat = ["".join(t for t, _ in line) for line in got]
    assert flat == ["ABCD EF GH", "IJ", "가나다라", "Mm2", "Q", "Z"]
    assert got[0] == [("ABCD EF", 10.0), (" ", 10.0), ("GH", 10.0)]
    assert got[3] == [("Mm", 10.0), ("2", 6.0)]


def test_words_agree(tmp_path):
    doc = pdfbuild.Doc()
    page = new_page(doc)
    latin = ["Total", "1,304", "tCO2e", "(2024)"]
    put(page, 40, 60, " ".join(latin))
    put(page, 40, 90, "합계 12.5 %", font=KOREAN)
    put(page, 200, 90, "따로", font=KOREAN)
    pdf = save(tmp_path, doc)
    got = read(pdf, words_of)
    assert [w[0] for w in got] == [*latin, "합계", "12.5", "%", "따로"]
    for k, text in enumerate(latin):
        assert_latin_word(got[k], text, 40 + width_of(" ".join(latin[:k]) + (" " if k else "")), 60)
    assert_boxes_near([got[4][1], got[7][1]], [korean_box(40, 90, 2), korean_box(200, 90, 2)])
    # 한글 글꼴로 쓴 숫자·기호: 시작 자리와 세로만 본다 (오른쪽은 기계의 대체 글꼴에 달려 있다)
    for word, before in ((got[5], "합계 "), (got[6], "합계 12.5 ")):
        x = 40 + width_of(before, font=KOREAN)
        assert abs(word[1][0] - x) <= NEAR and word[1][2] > x, word
        assert abs(word[1][1] - (90 - 8.8)) <= NEAR and abs(word[1][3] - (90 + 1.2)) <= NEAR, word
    numbering = read(pdf, lambda p: [w[5:] for w in p.get_words()])
    # (줄 번호, 낱말 번호). 「따로」는 같은 바닥선에서 0.8em 넘게 떨어져 새 줄이고, 어긋남이 없어 같은 블록이다
    assert [n[1:] for n in numbering] == [(0, 0), (0, 1), (0, 2), (0, 3), (0, 0), (0, 1), (0, 2), (1, 0)]
    assert [n[0] for n in numbering] == [0, 0, 0, 0, 1, 1, 1, 1]


def test_unembedded_font_boxes_differ_in_height_only(tmp_path):
    """글꼴을 심지 않은 Helvetica 의 낱말 상자: 가로는 너비표와 맞고 바닥선이 상자 안에 있다.

    (원본은 「두 엔진의 가로는 같고 높이가 다르다」였다. 견줄 엔진이 없어 pdfium 이 내는 값으로 바꿨다. 이름은 원본의 것이다.)
    """
    doc = pdfbuild.Doc()
    page = doc.new_page(width=400, height=300)
    page.insert_text((40, 60), "Plain 12", fontsize=10, font=LATIN)
    pdf = save(tmp_path, doc)
    got = read(pdf, words_of)
    assert len(got) == 2
    assert_latin_word(got[0], "Plain", 40, 60)
    assert_latin_word(got[1], "12", 40 + width_of("Plain "), 60)


# ── 벡터 그림 ─────────────────────────────────────────────────────────────


def test_drawing_items_colors_and_widths_agree(tmp_path):
    doc = pdfbuild.Doc()
    page = new_page(doc)
    page.draw_rect((40, 40, 90, 70), fill=(1, 0, 0), color=None)  # 채운 네모
    page.draw_rect((100, 40, 150, 70), fill=None, color=(0, 0, 1), width=2)  # 테두리 네모
    page.draw_rect((160, 40, 210, 70), fill=(0, 1, 0), color=(0, 0, 0), width=0.5)  # 한 번에 채우고 긋기
    page.draw_rect((220, 40, 270, 70), fill=(1, 1, 0), color=None)  # 따로 채우고
    page.draw_rect((220, 40, 270, 70), fill=None, color=(0, 0, 0), width=1)  # 같은 꼴로 따로 긋기: 한 항목
    page.draw_line((40, 100), (200, 100), color=(0.2, 0.2, 0.2), width=0.25)  # 선
    page.draw_polyline([(40, 150), (80, 120), (120, 140), (160, 110)], color=(1, 0, 1), width=1.5)  # 꺾은선
    page.draw_circle((60, 200), 4, fill=(0, 0, 1), color=None)  # 원 (곡선)
    pdf = save(tmp_path, doc)
    got = read(pdf, drawings_of)
    expected = [
        ("r", (40, 40, 90, 70), "#ff0000", None, None),
        ("r", (100, 40, 150, 70), None, "#0000ff", 2.0),
        ("r", (160, 40, 210, 70), "#00ff00", "#000000", 0.5),
        ("r", (220, 40, 270, 70), "#ffff00", "#000000", 1.0),
        ("l", (40, 100, 200, 100), None, "#333333", 0.25),
        ("lll", (40, 110, 160, 150), None, "#ff00ff", 1.5),
        ("cccc", (56, 196, 64, 204), "#0000ff", None, None),
    ]  # 곡선 넷의 제어점은 원을 두른 네모 안이다
    assert len(got) == 7
    for a, b in zip(got, expected, strict=False):
        assert (a[0], a[2], a[3], a[4]) == (b[0], b[2], b[3], b[4])
    assert_boxes_near([d[1] for d in got], [d[1] for d in expected])


def test_closed_four_line_outline_is_read_differently(tmp_path):
    """선 넷으로 처음 점까지 돌아온 뒤 닫은 윤곽선(`m l l l l h S`)은 선 넷으로 읽는다.

    pdfium 은 경로 닫기를 「처음 점으로 가는 선」으로 적어서 `re`·`m l l l h` 와 `m l l l l h` 가 같은 점 목록이 된다.
    pdfium 엔진은 앞의 것(흔한 쪽)으로 읽는다. 그래서 뒤의 꼴은 사각 `qu` 가 아니라 선 넷이다 (원본의 다른 엔진은 사각으로 읽었다).
    """
    doc = pdfbuild.Doc()
    page = new_page(doc)
    # 쪽 좌표의 (120, 190) → (118, 220) → (158, 225) → (160, 195) → (120, 190). 날 연산자는 왼쪽 아래 원점이라 y 를 300 에서 뺀다.
    page.add_content("q 0 0 0 RG 1 w 120 110 m 118 80 l 158 75 l 160 105 l 120 110 l h S Q")
    pdf = save(tmp_path, doc)
    got = read(pdf, drawings_of)
    assert [d[0] for d in got] == ["llll"]
    assert_boxes_near([d[1] for d in got], [(118, 190, 160, 225)])


def test_image_boxes_agree(tmp_path):
    doc = pdfbuild.Doc()
    page = new_page(doc)
    page.insert_image((50, 60, 250, 180), gray=180, pixels=(30, 20))
    pdf = save(tmp_path, doc)
    got = read(pdf, lambda p: p.get_image_boxes())
    assert_boxes_near(got, [(50, 60, 250, 180)])
    assert parse_pdf(pdf)["pages"][0]["image_coverage"] == 0.2  # 200 × 120 / (400 × 300)


# ── 쪽의 좌표: CropBox, 회전, 폼 ────────────────────────────────────────


def _geometry_page(doc):
    page = new_page(doc)
    put(page, 120, 150, "Corner 42")
    page.draw_rect((110, 160, 180, 200), fill=(0, 0.5, 1), color=None)
    return page


@pytest.mark.parametrize("crop, rotation", [(None, 0), ((50, 40, 350, 260), 0), (None, 90), ((50, 40, 350, 260), 270)])
def test_cropbox_and_rotation_agree(tmp_path, crop, rotation):
    """좌표의 원점은 CropBox 의 왼쪽 위고 y 는 아래로 간다. /Rotate 는 쪽 상자의 너비·높이만 바꾼다 (글자·그림의 좌표는 돌리기 전의 것)."""
    doc = pdfbuild.Doc()
    page = _geometry_page(doc)
    if crop:
        page.set_cropbox(crop)
    page.set_rotation(rotation)
    pdf = save(tmp_path, doc)
    left, top = (crop[0], crop[1]) if crop else (0, 0)
    width, height = (crop[2] - crop[0], crop[3] - crop[1]) if crop else (400, 300)
    if rotation in (90, 270):
        width, height = height, width
    assert read(pdf, lambda p: tuple(p.rect)) == (0.0, 0.0, float(width), float(height))
    words = read(pdf, words_of)
    assert len(words) == 2
    assert_latin_word(words[0], "Corner", 120 - left, 150 - top, overhang=True)  # 바닥선 150 은 위에서 잰 것이다
    assert_latin_word(words[1], "42", 120 - left + width_of("Corner "), 150 - top)
    drawings = read(pdf, drawings_of)
    assert [d[0] for d in drawings] == ["r"]
    assert_boxes_near([drawings[0][1]], [(110 - left, 160 - top, 180 - left, 200 - top)])  # y 는 위에서 아래로
    assert (
        drawings[0][1][1] > words[0][1][3] - 3
    )  # 네모는 글의 아래에 있다 (바닥선에서 10pt 아래. 글자의 내림은 3pt 를 넘지 않는다)


def test_text_and_paths_inside_a_form_agree(tmp_path):
    """다른 쪽을 줄여 붙인 폼(XObject): 그 안의 글자·경로는 폼의 행렬을 곱해야 제자리고, 글자 크기에도 배율이 든다."""
    src = pdfbuild.Doc()
    inner = _geometry_page(src)
    doc = pdfbuild.Doc()
    page = new_page(doc)
    page.show_form((100, 50, 300, 200), inner)  # 400×300 을 200×150 으로: 배율 0.5, 옮김 (100, 50)
    pdf = save(tmp_path, doc)

    def at(x, y):
        return (100 + 0.5 * x, 50 + 0.5 * y)

    words = read(pdf, words_of)
    assert len(words) == 2
    assert_latin_word(words[0], "Corner", *at(120, 150), size=5, overhang=True)
    assert_latin_word(words[1], "42", at(120, 150)[0] + width_of("Corner ", 5), at(120, 150)[1], size=5)
    sizes = read(pdf, lambda p: [s["size"] for b in p.get_text_blocks() for line in b["lines"] for s in line["spans"]])
    assert sizes == [5.0]
    drawings = read(pdf, drawings_of)
    assert [d[0] for d in drawings] == ["r"]
    assert_boxes_near([drawings[0][1]], [at(110, 160) + at(180, 200)])
    assert_boxes_near([drawings[0][1]], [(155.0, 130.0, 190.0, 150.0)])


# ── 문서: 책갈피, 암호, 렌더 ─────────────────────────────────────────────


def test_outline_agrees(tmp_path):
    doc = pdfbuild.Doc()
    for title in ("One", "Two", "Three"):
        put(new_page(doc), 40, 60, title)
    doc.set_toc([[1, "첫 장", 1], [2, "첫 절", 2], [1, "둘째 장", 3]])
    pdf = save(tmp_path, doc)
    with open_pdf(pdf) as opened:
        assert len(opened) == 3
        assert opened.get_toc() == [[1, "첫 장", 1], [2, "첫 절", 2], [1, "둘째 장", 3]]
    # 문서 모델의 장·절은 책갈피에서 온다: 장은 다음 같은 단계의 앞 쪽까지, 절은 제 쪽까지
    sections = parse_pdf(pdf)["sections"]
    assert [(s["title"], s["level"], s["page_start"], s["page_end"], s["basis"]) for s in sections] == [
        ("첫 장", 1, 1, 2, "pdf_outline"),
        ("첫 절", 2, 2, 2, "pdf_outline"),
        ("둘째 장", 1, 3, 3, "pdf_outline"),
    ]


def test_password_protected_pdf_is_refused_by_both(tmp_path):
    """암호가 걸린 PDF 는 거절한다. (원본은 AES-256 으로 걸었다. 여기는 `pdfbuild` 가 쓰는 RC4 40비트다. 이름은 원본의 것이다.)"""
    doc = pdfbuild.Doc()
    put(new_page(doc), 40, 60, "Secret")
    pdf = save(tmp_path, doc, user_pw="user", owner_pw="owner")
    with open_pdf(pdf) as opened:
        assert opened.needs_pass and len(opened) == 0
    with pytest.raises(ParseError, match="암호"):
        parse_pdf(pdf)
    # 같은 문서를 암호 없이 쓰면 읽힌다: 거절의 까닭이 암호다
    plain = save(tmp_path, doc, "plain.pdf")
    assert "Secret" in " ".join(b.get("text", "") for b in parse_pdf(plain)["blocks"])


def test_broken_file_is_a_parse_error_in_both(tmp_path):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"not a pdf at all")
    with pytest.raises(ParseError):
        parse_pdf(bad)


def test_render_writes_a_png_of_the_same_size(tmp_path):
    doc = pdfbuild.Doc()
    _geometry_page(doc)
    pdf = save(tmp_path, doc)
    assert main(["render", str(pdf), "--out", str(tmp_path / "png"), "--dpi", "72"]) == 0
    data = (tmp_path / "png" / "p0001.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert pdfbuild.png_size(data) == (400, 300)
    r, g, b = pdfbuild.png_pixel(data, 145, 180)[:3]  # 채운 네모 (110, 160)~(180, 200) 의 자리가 푸르다
    assert b > 200 and r < 60, (r, g, b)
    assert pdfbuild.png_pixel(data, 145, 120)[:3] == (255, 255, 255)  # 위아래를 뒤집은 자리는 비어 있다
    assert pdfbuild.png_pixel(data, 145, 210)[:3] == (255, 255, 255) and pdfbuild.png_pixel(data, 100, 180)[:3] == (
        255,
        255,
        255,
    )  # 네모의 밖


def test_document_models_agree_on_a_synthetic_table(tmp_path, synthetic_ruled_page):
    """괘선 표 하나짜리 쪽의 문서 모델: 표의 칸이 지어 넣은 글 그대로다. (원본은 두 엔진의 문서 모델을 견줬다.)"""
    pdf = save(tmp_path, synthetic_ruled_page.parent, "ruled.pdf")
    model = parse_pdf(pdf)
    rows = [
        ["Item", "Unit", "2023", "2024"],
        ["Alpha", "t", "1,200", "1,304"],
        ["", "kg", "15", "-"],
        ["Beta", "t", "7.5", "8.25"],
    ]
    assert [t["cells"] for t in model["tables"]] == [rows]
    table = model["tables"][0]
    assert (table["method"], table["status"], table["header"]["rows"]) == ("lines", "ok", [0])
    assert_boxes_near([table["bbox"]], [(40, 50, 300, 50 + 14 * 4)])  # 괘선의 왼쪽·오른쪽 끝, 맨 위 선과 맨 아래 선
    assert len(model["pages"]) == 1
    page = model["pages"][0]
    assert (page["page"], page["width"], page["height"], page["text_layer"], page["image_coverage"]) == (
        1,
        400.0,
        300.0,
        "present",
        0.0,
    )
    assert page["char_count"] == sum(len(cell) for row in rows for cell in row)
    assert [(s["page_start"], s["page_end"]) for s in model["sections"]] == [(1, 1)]


# ── 보강 (검증 지적): 다시 세우는 규칙 하나하나 ──────────────────────────


def test_space_threshold_and_overprint(tmp_path):
    """틈 0.2em 은 공백 하나(0.15 와 0.25 사이). 같은 글자를 0.09em 옆에 또 찍으면 한 번만.

    글꼴만 다른 같은 글자를 0.05em 옆에 찍은 것도 한 번만 나온다. (원본의 PDF 에서는 pdfium 이 스스로 버리지 않아 엔진의 규칙이
    버렸다. 여기서 쓰는 글꼴 파일 없는 한글 글꼴로는 pdfium 이 먼저 버린다. 엔진의 덧찍기 규칙은 아래 경계 테스트가 크기가 다른 글자로 본다.)
    """
    doc = pdfbuild.Doc()
    page = new_page(doc)
    put(page, 40, 60, "AB")
    put(page, 40 + width_of("AB") + 2.0, 60, "CD")
    put(page, 40, 100, "Q")
    put(page, 40.9, 100, "Q")
    put(page, 40, 140, "Q")
    put(page, 40.5, 140, "Q", font=KOREAN)
    page.add_content("q 200 200 50 50 re W n Q\n260 200 30 30 re n")  # 클립만 하는 경로, 칠하지 않는 경로
    pdf = save(tmp_path, doc)
    assert ["".join(t for t, _ in line) for line in read(pdf, lines_of)] == ["AB CD", "Q", "Q"]
    assert read(pdf, drawings_of) == []


def test_spans_split_on_raised_glyph_and_color(tmp_path):
    doc = pdfbuild.Doc()
    page = new_page(doc)
    put(page, 40, 60, "Mm")
    put(page, 40 + width_of("Mm"), 60 - 3, "x")  # 같은 크기, 올려 쓴 글자
    put(page, 40, 100, "Mm")
    put(page, 40 + width_of("Mm"), 100 + 3, "x")  # 내려 쓴 글자는 가르지 않는다
    put(page, 40, 140, "Red")
    put(page, 40 + width_of("Red"), 140, "Blue", color=(0, 0, 1))
    pdf = save(tmp_path, doc)
    assert read(pdf, spans_of) == [["Mm", "x"], ["Mmx"], ["Red", "Blue"]]


def test_line_direction_and_content_order(tmp_path):
    doc = pdfbuild.Doc()
    page = new_page(doc)
    put(page, 200, 60, "World")  # 내용 스트림에서 먼저, 자리는 오른쪽
    put(page, 40, 60, "Hello")
    put(page, 100, 250, "Up", rotate=90)  # 아래에서 위로 읽는 글
    pdf = save(tmp_path, doc)
    got = read(
        pdf,
        lambda p: [
            ("".join(s["text"] for s in line["spans"]), tuple(round(v, 3) for v in line["dir"]))
            for b in p.get_text_blocks()
            for line in b["lines"]
        ],
    )
    assert got == [("World", (1.0, 0.0)), ("Hello", (1.0, 0.0)), ("Up", (0.0, -1.0))]
    words = read(pdf, words_of)
    assert len(words) == 3
    assert_latin_word(words[0], "World", 200, 60)
    assert_latin_word(words[1], "Hello", 40, 60)
    # 세운 글: 바닥선은 x = 100 의 세로선이고 글은 y = 250 에서 위로 글의 너비만큼 간다
    text, (x0, y0, x1, y1) = words[2]
    assert text == "Up"
    assert abs(y1 - 250) <= NEAR and abs(y0 - (250 - width_of("Up"))) <= NEAR
    assert x0 < 100 < x1 and x1 - x0 < 15


def test_glyph_left_of_origin_and_nbsp_and_hyphen(tmp_path):
    doc = pdfbuild.Doc()
    page = new_page(doc)
    put(page, 40, 60, "jar jig")  # j 는 글리프가 원점보다 왼쪽으로 나온다: 상자는 원점에서 시작한다
    put(page, 40, 100, "A B")  # 줄 바꾸지 않는 공백도 낱말을 가른다
    put(page, 40, 140, "Self-")  # 줄 끝의 붙임표
    put(page, 40, 152, "made text")
    pdf = save(tmp_path, doc)
    words = read(pdf, words_of)
    assert [w[0] for w in words] == ["jar", "jig", "A", "B", "Self-", "made", "text"]
    assert_latin_word(words[0], "jar", 40, 60, overhang=True)
    assert_latin_word(words[1], "jig", 40 + width_of("jar "), 60)
    assert_latin_word(words[2], "A", 40, 100, overhang=True)
    assert_latin_word(words[3], "B", 40 + width_of("A "), 100)  # Helvetica 의 줄 바꾸지 않는 공백은 공백과 너비가 같다
    assert_latin_word(words[4], "Self-", 40, 140)
    assert_latin_word(words[5], "made", 40, 152)
    assert_latin_word(words[6], "text", 40 + width_of("made "), 152)
    numbering = read(pdf, lambda p: [w[5:] for w in p.get_words()])
    # 「made text」는 1.2em 아래에서 머리로 돌아온 줄: 같은 블록의 둘째 줄
    assert numbering == [(0, 0, 0), (0, 0, 1), (1, 0, 0), (1, 0, 1), (2, 0, 0), (2, 1, 0), (2, 1, 1)]


def test_whitespace_only_object_is_restored(tmp_path):
    """공백 하나만 든 글 객체: pdfium 은 글자로 내지 않는다. 한글 사이에서는 틈으로 공백을 짓지도 않으므로 되살려야 낱말이 갈린다."""
    doc = pdfbuild.Doc()
    page = new_page(doc)
    x = 40
    for text in ("가나", " ", "다라"):
        put(page, x, 60, text, font=KOREAN)
        x += width_of(text, font=KOREAN)
    pdf = save(tmp_path, doc)
    words = read(pdf, words_of)
    assert [w[0] for w in words] == ["가나", "다라"]
    assert_boxes_near([w[1] for w in words], [korean_box(40, 60, 2), korean_box(40 + 20 + 5, 60, 2)])
    assert ["".join(t for t, _ in line) for line in read(pdf, lines_of)] == ["가나 다라"]


def test_run_of_spaces_at_object_end_keeps_the_line(tmp_path):
    """글 객체 끝의 잇단 공백: pdfium 은 하나만 남긴다. 빠진 공백의 자리만큼 펜을 옮기지 않으면 다음 글이 새 줄로 끊긴다."""
    doc = pdfbuild.Doc()
    page = new_page(doc)
    head = "가나" + " " * 8
    put(page, 40, 60, head, font=KOREAN)
    put(page, 40 + width_of(head, font=KOREAN), 60, "다라", font=KOREAN)
    pdf = save(tmp_path, doc)
    lines = read(
        pdf,
        lambda p: [
            re.sub(r" +", " ", "".join(s["text"] for s in line["spans"]))
            for b in p.get_text_blocks()
            for line in b["lines"]
        ],
    )
    assert lines == ["가나 다라"]
    words = read(pdf, lambda p: [(w[4], w[6]) for w in p.get_words()])
    assert words == [("가나", 0), ("다라", 0)]
    assert_boxes_near([w[1] for w in read(pdf, words_of)], [korean_box(40, 60, 2), korean_box(40 + 20 + 8 * 5, 60, 2)])


def test_stroke_quad_width_scale_opacity_and_curve_box(tmp_path):
    src = pdfbuild.Doc()
    inner = new_page(src)
    inner.draw_rect((40, 40, 140, 100), fill=None, color=(0, 0, 0), width=3)
    doc = pdfbuild.Doc()
    page = new_page(doc)
    page.show_form((0, 0, 200, 150), inner)  # 배율 0.5: 굵기 3 → 1.5
    page.draw_polyline(
        [(220, 40), (300, 50), (290, 100), (215, 90), (220, 40)], color=(0, 0, 0), width=1
    )  # 닫지 않고 처음 점으로: 사각
    page.draw_rect((40, 180, 90, 220), fill=(1, 0, 0), color=None, fill_opacity=0)  # 보이지 않는 채움
    page.draw_bezier((120, 200), (140, 150), (180, 260), (200, 200), color=(0, 0, 1), width=1)  # 제어점이 끝점 밖
    pdf = save(tmp_path, doc)
    got = read(pdf, drawings_of)
    assert [d[0] for d in got] == ["r", "q", "r", "c"]
    assert [d[4] for d in got] == [1.5, 1.0, None, 1.0]
    # 폼 안의 네모는 절반 크기로, 사각은 네 꼭짓점을 두른 상자, 곡선의 상자에는 제어점이 든다
    assert_boxes_near(
        [d[1] for d in got], [(20, 20, 70, 50), (215, 40, 300, 100), (40, 180, 90, 220), (120, 150, 200, 260)]
    )
    opacity = read(pdf, lambda p: [d.get("fill_opacity") for d in p.get_drawings()])
    assert opacity == [None, None, 0.0, None]


def test_image_inside_a_form_and_text_blocks_without_images(tmp_path):
    src = pdfbuild.Doc()
    inner = new_page(src)
    inner.insert_image((100, 100, 300, 200), gray=120, pixels=(30, 20))
    put(inner, 40, 60, "Caption")
    doc = pdfbuild.Doc()
    page = new_page(doc)
    page.show_form((100, 50, 300, 200), inner)
    pdf = save(tmp_path, doc)
    boxes = read(pdf, lambda p: p.get_image_boxes())
    assert_boxes_near(
        boxes, [(150.0, 100.0, 250.0, 150.0)]
    )  # (100 + 0.5 × 100, 50 + 0.5 × 100) ~ (100 + 0.5 × 300, 50 + 0.5 × 200)
    blocks = read(pdf, lambda p: p.get_text_blocks())
    assert len(blocks) == 1 and all("lines" in b for b in blocks)  # 글 블록만 온다 (그림 블록이 섞이지 않는다)
    assert blocks_of_text(blocks) == ["Caption"]


def test_render_clip_gives_the_same_size(tmp_path):
    from docparse.render import render_page

    doc = pdfbuild.Doc()
    _geometry_page(doc)
    pdf = save(tmp_path, doc)
    out = render_page(pdf, 1, tmp_path / "clip.png", dpi=72, clip=(100, 150, 200, 210))
    data = out.read_bytes()
    assert pdfbuild.png_size(data) == (100, 60)
    r, g, b = pdfbuild.png_pixel(data, 40, 30)[:3]  # 잘라 낸 그림의 (40, 30) = 쪽의 (140, 180): 푸른 네모 안
    assert b > 200 and r < 60, (r, g, b)
    assert pdfbuild.png_pixel(data, 90, 30)[:3] == (255, 255, 255)  # 쪽의 (190, 180): 네모의 오른쪽 밖
    assert pdfbuild.png_pixel(data, 40, 55)[:3] == (255, 255, 255)  # 쪽의 (140, 205): 네모의 아래 밖


def test_score_and_render_commands_pass_the_engine_on(tmp_path):
    """엔진을 고르는 인자는 어느 명령에도 없다: `--engine` 을 주면 세 명령 다 거절하고 아무것도 하지 않는다.

    (원본은 `score`·`render` 가 `--engine` 의 값을 아래로 넘기는지를 봤다. 넘길 인자가 없어졌다. 이름은 원본의 것이다.)
    """
    doc = pdfbuild.Doc()
    put(new_page(doc), 40, 60, "No engine flag")
    pdf = save(tmp_path, doc)
    out = tmp_path / "out"
    for command in (
        ["parse", str(pdf), "--out", str(out)],
        ["score", "--gold", str(tmp_path), "--strategy", "auto"],
        ["render", str(pdf), "--out", str(out)],
    ):
        with pytest.raises(SystemExit) as refused:
            main([*command, "--engine", "pdfium"])
        assert refused.value.code == 2, command  # argparse 가 모르는 인자를 거절할 때의 값
    assert not out.exists()
    assert main(["render", str(pdf), "--out", str(out)]) == 0  # 인자를 빼면 돈다
    assert (out / "p0001.png").is_file()


# ── 다시 쓰기(원본 밴드 PD1)에서 재서 찾은 것: 명세에 없던 동작 ──────────────


def test_wide_space_splits_just_above_three_tenths(tmp_path):
    """지어 넣은 공백이 따로 스팬이 되는 틈은 0.3em 을 넘을 때다 (0.25 는 한 스팬, 0.35 는 따로)."""
    doc = pdfbuild.Doc()
    page = new_page(doc)
    for y, gap in ((60, 0.25), (100, 0.35)):
        put(page, 40, y, "AB")
        put(page, 40 + width_of("AB") + gap * 10, y, "CD")
    pdf = save(tmp_path, doc)
    assert read(pdf, spans_of) == [["AB CD"], ["AB", " ", "CD"]]


def test_blocks_follow_indent_and_list_markers(tmp_path):
    """한 줄 아래(1.1em)의 줄: 앞 줄의 머리로 돌아오면 같은 블록, 들여 쓰면 새 블록. 앞 줄이 번호·글머리표로 시작하면 들여 써도 같은 블록."""
    doc = pdfbuild.Doc()
    page = new_page(doc)
    put(page, 40, 40, "Head")
    put(page, 40, 51, "back")  # 머리로 돌아온 줄: 같은 블록의 둘째 줄
    put(page, 40, 100, "Head")
    put(page, 60, 111, "inset")  # 들여 쓴 줄: 새 블록
    put(page, 40, 160, "1 Item")
    put(page, 60, 171, "inset")  # 번호로 시작한 줄 아래: 같은 블록
    put(page, 40, 220, "• Item")
    put(page, 60, 231, "inset")  # 글머리표
    put(page, 40, 260, "- Item")
    put(page, 60, 271, "inset")  # 붙임표는 글머리표로 치지 않는다
    pdf = save(tmp_path, doc)
    shape = read(
        pdf, lambda p: [["".join(s["text"] for s in line["spans"]) for line in b["lines"]] for b in p.get_text_blocks()]
    )
    assert shape == [
        ["Head", "back"],
        ["Head"],
        ["inset"],
        ["1 Item", "inset"],
        ["• Item", "inset"],
        ["- Item"],
        ["inset"],
    ]
    numbering = read(pdf, lambda p: [(w[4], w[6], w[7]) for w in p.get_words()])
    # (낱말, 블록 안의 줄 번호, 줄 안의 낱말 번호)
    assert numbering == [
        ("Head", 0, 0),
        ("back", 1, 0),
        ("Head", 0, 0),
        ("inset", 0, 0),
        ("1", 0, 0),
        ("Item", 0, 1),
        ("inset", 1, 0),
        ("•", 0, 0),
        ("Item", 0, 1),
        ("inset", 1, 0),
        ("-", 0, 0),
        ("Item", 0, 1),
        ("inset", 0, 0),
    ]


def test_flat_curves_implicit_subpaths_and_in_place_lines(tmp_path):
    doc = pdfbuild.Doc()
    page = new_page(doc)
    put(page, 300, 280, "x")
    page.add_content(
        b"100 100 m 100 100 150 130 150 130 c S\n"  # 제어점이 양 끝점에 겹친 곡선은 선이다
        b"200 100 m 200 100 250 100 250 100 c 250 100 250 130 250 130 c 250 130 200 130 200 130 c h f\n"  # 그런 곡선 셋 + 닫기: 네모
        b"100 200 m 150 200 l h 150 220 l 100 220 l h S\n"  # 닫은 뒤 옮김 없이 이어 그은 것은 닫아도 선이 더해지지 않는다
        b"200 200 m 250 200 l 250 220 l 200 200 m 200 200 l h S\n"  # 옮김 바로 뒤의 제자리 선은 남는다
        b"300 100 50 0 re f 300 150 0 30 re S\n"
    )  # 높이·너비가 없는 네모도 네모다
    pdf = save(tmp_path, doc)
    got = read(pdf, drawings_of)
    assert [d[0] for d in got] == ["l", "r", "llll", "lll", "r", "r"]
    # 날 연산자의 좌표는 왼쪽 아래 원점이다: 쪽 좌표의 y 는 300 에서 뺀 것
    assert_boxes_near(
        [d[1] for d in got],
        [
            (100, 170, 150, 200),
            (200, 170, 250, 200),
            (100, 80, 150, 100),
            (200, 80, 250, 100),
            (300, 200, 350, 200),
            (300, 120, 300, 150),
        ],
    )
    assert [(d[2] is not None, d[3] is not None) for d in got] == [
        (False, True),
        (True, False),
        (False, True),
        (False, True),
        (True, False),
        (False, True),
    ]


def test_shading_box_is_grown_to_the_pixel_grid(tmp_path):
    """음영으로 칠한 자리의 그림 상자: 바깥쪽 정수 눈금으로. 눈금을 살짝 넘은 변도 다음 눈금으로 간다. 칠할 자리가 없으면 (0, 0, 0, 0)."""
    doc = pdfbuild.Doc()
    page = new_page(doc)
    put(page, 300, 280, "x")
    page.add_shading(
        "Sh0",
        "<< /ShadingType 2 /ColorSpace /DeviceRGB /Coords [0 0 400 0] "
        "/Function << /FunctionType 2 /Domain [0 1] /C0 [1 0 0] /C1 [0 0 1] /N 1 >> /Extend [true true] >>",
    )
    page.add_content(
        b"q 1 0 0 -1 0 300 cm 47.07 76.11 6.84 6.93 re W n /Sh0 sh Q\n"  # (47.07, 76.11, 53.91, 83.04)
        b"q 1 0 0 -1 0 300 cm 109.9999 120 20.0002 20 re W n /Sh0 sh Q\n"  # 눈금을 0.0001 넘음
        b"q 10 20 30 30 re W n 200 200 5 5 re W n /Sh0 sh Q\n"
    )  # 겹치지 않는 클립 둘: 빈 자리
    pdf = save(tmp_path, doc)
    got = read(pdf, lambda p: p.get_image_boxes())
    assert got == [(47.0, 76.0, 54.0, 84.0), (109.0, 120.0, 131.0, 140.0), (0.0, 0.0, 0.0, 0.0)]


def test_outline_empty_title_and_missing_target(tmp_path):
    doc = pdfbuild.Doc()
    for _ in range(3):
        new_page(doc)
    doc.set_toc([[1, "장", 1], [2, "", 2], [1, "밖", -1], [2, "웹", 1, {"uri": "https://example.com"}], [1, "끝", 3]])
    pdf = save(tmp_path, doc)
    with open_pdf(pdf) as opened:
        toc = opened.get_toc()
    # 빈 제목은 " ", 가리키는 쪽이 없는 책갈피와 웹 주소로 가는 책갈피의 쪽은 -1
    assert toc == [[1, "장", 1], [2, " ", 2], [1, "밖", -1], [2, "웹", -1], [1, "끝", 3]]


# ── 재검증 지적: 경계를 못 박는다 ─────────────────────────────────────────


def test_wide_space_boundary_lies_between_three_tenths_and_one_third(tmp_path):
    """지어 넣은 공백이 따로 스팬이 되는 틈: 0.29em 은 한 스팬, 0.32em 은 따로다 (문턱이 1/3 이면 0.32 가 한 스팬으로 남는다)."""
    doc = pdfbuild.Doc()
    page = new_page(doc)
    put(page, 40, 60, "AB")
    put(page, 40 + width_of("AB") + 2.9, 60, "CD")
    put(page, 40, 100, "AB")
    put(page, 40 + width_of("AB") + 3.2, 100, "CD")
    pdf = save(tmp_path, doc)
    assert read(pdf, spans_of) == [["AB CD"], ["AB", " ", "CD"]]


def test_slightly_tilted_text_stays_on_the_line_and_more_tilt_breaks_it(tmp_path):
    """앞 글에 바로 이어 2도 기운 글은 같은 줄, 10도 기운 글은 새 줄이다. 기우는 쪽은 가리지 않는다."""
    doc = pdfbuild.Doc()
    page = new_page(doc)
    for y, degrees in ((40, 2), (100, 10), (160, -2), (220, -10)):
        put(page, 40, y, "AB")
        put(page, 40 + width_of("AB"), y, "CD", rotate=degrees)
    pdf = save(tmp_path, doc)
    got = read(
        pdf, lambda p: ["".join(s["text"] for s in line["spans"]) for b in p.get_text_blocks() for line in b["lines"]]
    )
    assert got == ["ABCD", "AB", "CD", "ABCD", "AB", "CD"]


def test_closed_rectangle_starting_with_a_vertical_side_is_not_a_rect_item(tmp_path):
    """닫힌 직사각형이라도 세로 변부터 그은 것은 네모 항목이 아니라 선 넷이다 (가로 변부터 그은 것은 네모)."""
    doc = pdfbuild.Doc()
    page = new_page(doc)
    page.draw_polyline(
        [(100, 200), (100, 170), (150, 170), (150, 200)], close=True, fill=(0, 1, 0), color=None
    )  # 세로 먼저
    page.draw_polyline(
        [(200, 200), (250, 200), (250, 170), (200, 170)], close=True, fill=(0, 1, 0), color=None
    )  # 가로 먼저
    pdf = save(tmp_path, doc)
    got = read(pdf, drawings_of)
    assert [d[0] for d in got] == ["llll", "r"]
    assert_boxes_near([d[1] for d in got], [(100, 170, 150, 200), (200, 170, 250, 200)])


# ── 문턱의 바로 양쪽 (밴드 PD2 에서 더함. 원본에 없다) ────────────────────
#
# 문턱값은 `docparse/engine/pdfium_engine.py` 머리의 상수다. 틈·어긋남은 뒤 글자 크기의 배수(em)로 잰다.
# 문턱에서 `EDGE`(0.005em) 만큼 떨어진 양쪽을 본다: 좌표가 PDF 에 소수 여섯 자리로 적히고 엔진이 단정밀도로 셈하므로
# 문턱 값 자체(예: 0.300)는 어느 쪽으로도 떨어질 수 있다. 재 보니 ±0.001 은 크기 8·10·20 에서 다 섰다.
# 앞 글의 끝 글자는 상자가 걸음과 같은 `B` 다.

SIZES = [8, 10, 20]


def _pair(page, y, gap, shift, size):
    """`AB` 뒤에 틈 gap(em), 아래로 어긋남 shift(em) 을 두고 `CD` 를 놓는다."""
    put(page, 40, y, "AB", size=size)
    put(page, 40 + width_of("AB", size) + gap * size, y + shift * size, "CD", size=size)


def _two_pairs(tmp_path, size, near, far):
    """(gap, shift) 둘을 한 쪽의 위아래에 놓고 블록마다의 줄·스팬을 돌려준다. 두 묶음은 멀리 떨어져 블록이 갈린다."""
    doc = pdfbuild.Doc()
    page = new_page(doc, width=600, height=400)
    _pair(page, 100, *near, size)
    _pair(page, 300, *far, size)
    return read(save(tmp_path, doc), blocks_of)


@pytest.mark.parametrize("size", SIZES)
def test_space_gap_boundary(tmp_path, size):
    """`SPACE_GAP` 0.15em: 틈이 바로 아래면 붙고 바로 위면 공백 하나를 지어 넣는다."""
    got = _two_pairs(tmp_path, size, (0.15 - EDGE, 0), (0.15 + EDGE, 0))
    assert got == [[["ABCD"]], [["AB CD"]]]


@pytest.mark.parametrize("size", SIZES)
def test_wide_space_gap_boundary(tmp_path, size):
    """`WIDE_SPACE_GAP` 0.3em: 틈이 바로 아래면 공백이 앞뒤와 한 스팬, 바로 위면 공백이 따로 스팬이다."""
    got = _two_pairs(tmp_path, size, (0.3 - EDGE, 0), (0.3 + EDGE, 0))
    assert got == [[["AB CD"]], [["AB", " ", "CD"]]]


@pytest.mark.parametrize("size", SIZES)
def test_line_break_gap_boundary(tmp_path, size):
    """`LINE_BREAK_GAP` 0.8em: 틈이 바로 아래면 같은 줄(넓은 공백), 바로 위면 새 줄이다. 어긋남이 없어 블록은 같다."""
    got = _two_pairs(tmp_path, size, (0.8 - EDGE, 0), (0.8 + EDGE, 0))
    assert got == [[["AB", " ", "CD"]], [["AB"], ["CD"]]]


@pytest.mark.parametrize("size", SIZES)
def test_line_break_gap_boundary_backwards(tmp_path, size):
    """뒤로 물러난 틈도 같은 문턱이다: -0.8em 에 못 미치면 같은 줄, 넘으면 새 줄."""
    got = _two_pairs(tmp_path, size, (-0.8 + EDGE, 0), (-0.8 - EDGE, 0))
    assert got == [[["ABCD"]], [["AB"], ["CD"]]]


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("down", [1, -1])
def test_line_break_shift_boundary(tmp_path, size, down):
    """`LINE_BREAK_SHIFT` 0.8em: 바닥선의 어긋남이 바로 아래면 같은 줄, 바로 위면 새 줄이다 (아래로든 위로든).

    새 줄은 앞 줄의 머리보다 오른쪽에서 시작하므로 새 블록이 된다. 위로 어긋난 같은 줄의 글자는 올려 쓴 글자라 스팬이 갈린다.
    """
    got = _two_pairs(tmp_path, size, (0, down * (0.8 - EDGE)), (0, down * (0.8 + EDGE)))
    same_line = [["ABCD"]] if down == 1 else [["AB", "CD"]]
    assert got == [same_line, [["AB"]], [["CD"]]]


@pytest.mark.parametrize("size", SIZES)
def test_raised_shift_boundary(tmp_path, size):
    """`RAISED_SHIFT` 0.1em: 줄 머리보다 바로 그 아래만큼 위에 있으면 같은 스팬, 넘게 위에 있으면 올려 쓴 글자로 스팬이 갈린다."""
    got = _two_pairs(tmp_path, size, (0, -(0.1 - EDGE)), (0, -(0.1 + EDGE)))
    assert got == [[["ABCD"]], [["AB", "CD"]]]


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("dx, dy", [(1, 0), (0, 1), (0, -1)])
def test_same_place_reach_boundary(tmp_path, size, dx, dy):
    """`SAME_PLACE_REACH` 0.1em: 같은 글자의 원점이 앞 것에서 그 안이면 덧찍기로 버리고, 한쪽으로라도 그 밖이면 남긴다.

    뒤 글자는 크기를 1.2배로 했다: 글꼴·크기가 같은 글자가 겹치면 pdfium 이 먼저 버려서 엔진의 규칙까지 오지 않는다.
    거리는 뒤 글자의 크기로 잰다.
    """
    second = size * 1.2
    doc = pdfbuild.Doc()
    page = new_page(doc, width=600, height=400)
    for y, reach in ((100, 0.1 - EDGE), (300, 0.1 + EDGE)):
        put(page, 40, y, "Q", size=size)
        put(page, 40 + dx * reach * second, y + dy * reach * second, "Q", size=second)
    got = read(save(tmp_path, doc), blocks_of)
    assert ["".join(t for line in block for t in line) for block in got] == ["Q", "QQ"]
