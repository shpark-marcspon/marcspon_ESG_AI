"""번역 판(`layout=2`, 밴드 TRD1)의 합성 PDF 짓개. `pdfbuild`(표준 라이브러리만)로 짓는다. 글은 전부 지어낸 것이다.

`build(extra_block=False)` 는 PDF 바이트를 돌려준다. 같은 인자면 몇 번을 지어도 바이트가 같다. `extra_block=True` 는 1쪽
맨 위에 무관한 문단 하나를 더한 판이다(내용 키가 앞 블록에 흔들리지 않는지 본다 — 위치 ID 는 밀린다).

쪽마다 건드리는 갈래(기본 판의 증상 → 번역 판이 고친 것):

1. 줄 끝 위첨자(600 × 800). 본문 줄 끝의 각주 위첨자 `1)` 가 다음 글 객체의 머리에 그려져 엔진이 줄을 끊는다(올려 쓴
   어긋남이 위첨자 크기의 0.8 배를 넘음). 그 조각의 y0 가 왼쪽 조각보다 0.05pt 작아 (y0, x0) 정렬에서 먼저 오는 줄 하나,
   위첨자 상자가 왼쪽 조각 끝과 0.3pt 겹치는 줄 하나. 쪽 위 띠(머리글)와 아래 띠(쪽 번호)도 있다.
2. 대분류 세로 병합 괘선 표(600 × 800). 0~3열(대·중·소·세분류)은 머리 행 밑으로 안쪽 세로선이 없다. 0열은 가로 토막이
   없어 전 행 세로 병합, 1열은 무리 사이에만 토막. 중분류 글은 소분류 열로, 소분류의 긴 행 머리는 세분류 열로 넘친다.
3. 3단 쪽(842 × 595). 왼 단에 막대 도표 라벨(연도·값, 괘선 없음), 가운데 단 문단의 줄이 라벨 줄과 같은 높이에 있어
   글자 정렬 표가 단 사이 틈을 건너 문단 줄을 칸으로 삼킨다. 라벨 밑 끝과 1pt 안에 중심이 놓인 문단 줄도 하나.
4. 칸 밖 조각(600 × 800). 괘선 표 위 괘선에 걸친 제목(중심이 표 상자 안 1pt, 어느 칸에도 없음), 표 오른쪽 끝 밖
   1~2pt 에 중심이 놓인 값(괘선 표는 칸에 넣고 표 밖 거름은 못 거름), 큰 괘선 틀 안에 안긴 작은 괘선 표(두 표가 같은 조각).
"""

from . import pdfbuild

LAT, KOR = pdfbuild.LATIN, pdfbuild.KOREAN


def _put(page, x, y, text, size=9.0, font=LAT, right=False):
    if right:
        x -= pdfbuild.text_length(text, fontsize=size, font=font)
    page.insert_text((x, y), text, fontsize=size, font=font)


def _end(x, text, size=9.0, font=LAT):
    return x + pdfbuild.text_length(text, fontsize=size, font=font)


def _hline(page, x0, x1, y):
    page.draw_line((x0, y), (x1, y), width=0.5)


def _vline(page, x, y0, y1):
    page.draw_line((x, y0), (x, y1), width=0.5)


def _bands(page, w, h, title, number):
    """쪽 위 띠(머리글: 아래 끝이 쪽 높이의 0.075 안)와 아래 띠(쪽 번호: 쪽 높이의 0.92 아래)."""
    _put(page, 40, 0.045 * h, title, size=7)
    _put(page, w - 40, 0.96 * h, str(number), size=7, right=True)


SUP = 5.0  # 위첨자 크기
RAISE = 4.5  # 위첨자 올림(pt). 위첨자 크기의 0.9 배라 엔진이 줄을 끊는다


def _sup_line(page, x, y, left, mark, right, nudge_x=0.0, nudge_y=0.0):
    """한 줄: 왼쪽 글, 위첨자, 오른쪽 글. 위첨자와 오른쪽 글은 엔진에서 새 줄(다음 글 객체 머리)이 된다.

    nudge_x: 위첨자를 왼쪽 글의 끝보다 이만큼 왼쪽에서 시작(겹침). nudge_y: 오른쪽 글의 밑줄을 이만큼 위로.
    """
    _put(page, x, y, left)
    sx = _end(x, left) - nudge_x
    _put(page, sx, y - RAISE, mark, size=SUP)
    _put(page, _end(sx, mark, size=SUP) + 0.4, y - nudge_y, right)


def _page_superscript(doc, extra_block):
    w, h = 600, 800
    page = doc.new_page(w, h)
    _bands(page, w, h, "Synthetic layout two report - header band", 1)
    y = 110
    if extra_block:
        _put(page, 40, 90, "An unrelated note added in front of everything else.")
        y = 130
    _put(page, 40, y, "Line end superscripts", size=14)
    y += 30
    lines = [
        ("The supply chain plan sets yearly targets for each", None),
        ("partner and reviews progress twice a year so that", None),
        ("the figures stay consistent with the method", ("1)", "and the", 0.0, 0.05)),
        ("review panel confirms every change before the", None),
        ("data is published together with the external", ("2)", "audit", 0.3, 0.0)),
        ("opinion on the last page of the annex.", None),
    ]
    for left, sup in lines:
        if sup is None:
            _put(page, 40, y, left)
        else:
            mark, right, nx, ny = sup
            _sup_line(page, 40, y, left, mark, right, nudge_x=nx, nudge_y=ny)
        y += 12
    y += 20
    _put(page, 40, y, "A second paragraph follows after a clear gap and has")
    _put(page, 40, y + 12, "no superscript at all, so it stays as it is.")


def _page_vertical_merge(doc):
    w, h = 600, 800
    page = doc.new_page(w, h)
    _bands(page, w, h, "Synthetic layout two report - header band", 2)
    _put(page, 40, 80, "Ruled table with a vertically merged category", size=12)
    xs = [40, 90, 150, 210, 300, 340, 400, 460]  # 대·중·소·세분류·단위·값 둘
    top, row_h = 100, 12
    ys = [top + row_h * k for k in range(10)]  # 머리 + 8행
    heads = ["Group", "Sub", "Item", "Detail", "Unit", "2024", "2025"]
    for j, t in enumerate(heads):
        _put(page, xs[j] + 3, ys[0] + 9, t, size=7)
    # 행 1~8: 중분류 무리 둘(1~4, 5~8). 1·5 행은 중분류 글(소분류 열로 넘침), 2·6 은 짧은 소분류, 3·4·7·8 은 긴 소분류(세분류 열로 넘침)
    rows = [
        ("sub", "Sales of green items"),
        ("item", "Home"),
        ("item", "Plant Alpha Overseas Unit"),
        ("item", "Plant Beta Overseas Unit"),
        ("sub", "Purchases of green items"),
        ("item", "Home"),
        ("item", "Plant Alpha Overseas Unit"),
        ("item", "Plant Beta Overseas Unit"),
    ]
    values = [
        ("120", "130"),
        ("100", "110"),
        ("0", "0"),
        ("N/A", "0"),
        ("20", "25"),
        ("18", "22"),
        ("0", "0"),
        ("N/A", "3"),
    ]
    for i, ((kind, text), (a, b)) in enumerate(zip(rows, values, strict=True), 1):
        base = ys[i] + 9
        _put(page, xs[1] + 3 if kind == "sub" else xs[2] + 3, base, text, size=7)
        _put(page, xs[4] + 3, base, "t", size=7)
        _put(page, xs[6] - 3, base, a, size=7, right=True)
        _put(page, xs[7] - 3, base, b, size=7, right=True)
    # 대분류: 0열 가운데 세 줄(세로 병합 칸 안)
    for k, t in enumerate(("Green", "goods", "trade")):
        _put(page, xs[0] + 3, ys[3] + 3 + 8 * k, t, size=7)
    # 가로 토막: 맨 위·머리 밑·맨 밑은 칸마다. 그 사이는 2~6열은 행마다, 1열은 무리 사이(행 4·5 사이)만, 0열은 없음.
    for y in (ys[0], ys[1], ys[-1]):
        for j in range(len(xs) - 1):
            _hline(page, xs[j], xs[j + 1], y)
    for i in range(2, 9):
        for j in range(2, len(xs) - 1):
            _hline(page, xs[j], xs[j + 1], ys[i])
    _hline(page, xs[1], xs[2], ys[5])
    # 세로선: 머리 행은 칸마다, 그 밑은 단위 열 경계(xs[4])부터만
    for x in xs:
        _vline(page, x, ys[0], ys[1])
    for i in range(1, 9):
        for x in xs[4:]:
            _vline(page, x, ys[i], ys[i + 1])


def _page_three_columns(doc):
    w, h = 842, 595
    page = doc.new_page(w, h)
    _bands(page, w, h, "Synthetic layout two report - header band", 3)
    left, mid, right = 42, 302, 562
    col_lines = [
        "This column keeps a steady flow of words so that the",
        "reading order has a long body on each side of the gap",
        "between columns, and the gap stays clear from top to",
        "bottom of the page for the column detector to see.",
    ]
    for x in (left, mid, right):
        y = 70
        for _k in range(3):
            for line in col_lines:
                _put(page, x, y, line, size=8)
                y += 11
            y += 8
    # 왼 단: 막대 도표 라벨(연도 + 값). 가운데 단: 같은 높이의 문단 줄(값 없음).
    y0 = 240
    _put(page, mid, y0 - 12, "Returning water", size=10)
    labels = [("2023", "92,600"), ("2024", "101,100"), ("2025", "107,900")]
    para = [
        "The site returns more water to nature than it takes in",
        "through a long term plan with partners in the region",
        "and treats every litre before it leaves the plant",
        "while the loss is made up by joint outside projects so",
        "that the balance stays positive across the whole year.",
    ]
    for k, (year, value) in enumerate(labels):
        yy = y0 + 13 * k
        _put(page, left + 8, yy, year, size=7)
        _put(page, left + 60 + 30 * k, yy, value, size=7)
    for k, line in enumerate(para):
        _put(page, mid, y0 + 13 * k - 2 if k < 3 else y0 + 13 * k - 8, line, size=8)
    y = 330
    for line in col_lines * 2:
        _put(page, left, y, line, size=8)
        _put(page, mid, y, line, size=8)
        _put(page, right, y, line, size=8)
        y += 11


def _grid(page, xs, ys):
    for y in ys:
        for j in range(len(xs) - 1):
            _hline(page, xs[j], xs[j + 1], y)
    for i in range(len(ys) - 1):
        for x in xs:
            _vline(page, x, ys[i], ys[i + 1])


def _page_out_of_cells(doc):
    w, h = 600, 800
    page = doc.new_page(w, h)
    _bands(page, w, h, "Synthetic layout two report - header band", 4)
    # (가) 위 괘선에 걸친 제목: 중심이 표 상자 위 끝보다 0.5pt 위(상자 + 1pt 안), 맨 윗행 띠 밖.
    xs, ys = [60, 200, 280, 360], [120, 136, 152, 168]
    _put(page, 62, 120 + 2.2, "Targets and results", size=8)
    for i, row in enumerate([("Metric", "2024", "2025"), ("Energy", "410", "395"), ("Water", "75", "70")]):
        _put(page, xs[0] + 4, ys[i] + 12, row[0], size=7)
        _put(page, xs[2] - 4, ys[i] + 12, row[1], size=7, right=True)
        _put(page, xs[3] - 4, ys[i] + 12, row[2], size=7, right=True)
    _grid(page, xs, ys)
    # (나) 표 오른쪽 끝 밖: 중심이 끝 + 1.5pt, 왼 끝은 표 안(칸에는 들고 표 밖 거름 ±1pt 는 못 거름).
    xs2, ys2 = [60, 200, 280, 360], [220, 236, 252, 268]
    for i, row in enumerate([("Metric", "2024", "2025"), ("Waste", "15", "14"), ("Staff", "320", "318")]):
        _put(page, xs2[0] + 4, ys2[i] + 12, row[0], size=7)
        _put(page, xs2[2] - 4, ys2[i] + 12, row[1], size=7, right=True)
        _put(page, xs2[3] - 4, ys2[i] + 12, row[2], size=7, right=True)
    _put(page, xs2[3] + 1.5 - pdfbuild.text_length("19", fontsize=5) / 2, ys2[2] + 8, "19", size=5)
    _grid(page, xs2, ys2)
    # (다) 큰 틀(2행 2열, 머리 띠 + 큰 몸 칸) 안의 왼쪽 몸 칸에 작은 괘선 표. 틀의 가로선은 작은 표의 가로선과
    # 40pt 넘게 떨어져 괘선 묶음이 따로 선다.
    fx, fy = [40, 300, 560], [330, 344, 560]
    _put(page, fx[0] + 4, fy[0] + 10, "Frame left", size=7)
    _put(page, fx[1] + 4, fy[0] + 10, "Frame right", size=7)
    _put(page, fx[1] + 4, fy[1] + 30, "Notes on the right side of the frame.", size=7)
    _grid(page, fx, fy)
    ix, iy = [60, 160, 220, 280], [420, 434, 448, 462]
    for i, row in enumerate([("Inner", "2024", "2025"), ("Gas", "12", "11"), ("Oil", "7", "6")]):
        _put(page, ix[0] + 4, iy[i] + 10, row[0], size=7)
        _put(page, ix[2] - 4, iy[i] + 10, row[1], size=7, right=True)
        _put(page, ix[3] - 4, iy[i] + 10, row[2], size=7, right=True)
    _grid(page, ix, iy)


def build(extra_block=False):
    """합성 PDF 의 바이트."""
    doc = pdfbuild.Doc()
    _page_superscript(doc, extra_block)
    _page_vertical_merge(doc)
    _page_three_columns(doc)
    _page_out_of_cells(doc)
    return doc.tobytes()


# 고정 JSON(`baseline/layout2.sha256.json`)의 판 이름 → 짓는 인자
VARIANTS = {"layout2": {}, "layout2_extra": {"extra_block": True}}
