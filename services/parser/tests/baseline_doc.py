"""기준선 대조(밴드 PB1)의 합성 PDF 짓개. `pdfbuild`(표준 라이브러리만)로 짓는다. 글은 전부 지어낸 것이다.

`build(toc=False)` 는 PDF 바이트를 돌려준다. 같은 판이면 몇 번을 지어도 바이트가 같다(고정값이 PDF 해시도 잰다).
판은 둘이다: 목차 없는 판(`sections_from_titles` 갈래)과 같은 쪽에 목차를 단 판(`sections_from_outline` 갈래).

쪽마다 건드리는 분해기 갈래(쪽은 600 × 800pt, 꼬리 띠는 쪽 높이의 0.92 = 736pt 아래):

1. 제목(18pt, heading) 아래 두 단 본문 — `reading_order` 의 x 절단과 `columns == 2`(단 높이가 쪽의 0.4 이상).
   단마다 문단 여덟. 한 단의 글자 크기가 9.37pt(소수 둘째 자리)라 블록의 `font_size` 반올림 자리가 산출에 드러난다.
   꼬리 띠에 블록 둘(왼쪽 글, 오른쪽 쪽 번호) — 읽는 순서의 맨 뒤로 간다. 단 끝과 가까워 꼬리 판정이 꺼지면 순서가 바뀐다.
2. 괘선 표(method `lines`): 세로선·가로선이 다 있는 격자. 0열의 둘째·셋째 행은 사이 가로 토막이 없어 세로 병합이고,
   넷째 행은 안쪽 세로선 하나가 빠지고 위 가로선이 끊김 없이 지나가 가로 병합이다(`tables_lines` 의 가로 병합 갈래).
   병합 칸의 글은 병합이 아니면 다른 칸에 들어가도록 놓았다(병합 판정이 꺼지면 `cells` 가 달라진다).
   값 칸 하나에 각주 위첨자(`1)`)가 붙어 `footnote_marks` 로 나온다. 표 아래에 한국어(`pdfbuild.KOREAN`) 문단.
3. 세로선·가로선 없는 표(method `text`, 이름이 줄바꿈된 행 하나 — `wrapped_line_merged`)와 그 위의 소제목, 아래의 꼬리 띠 블록.
4. 글자 없는 쪽(그림 하나만) — `text_layer: "none"`, `image_coverage > 0`, 표 추출을 건너뛴다.
5. 한국어 제목과 여러 줄 한국어 문단, 라틴 글 문단.
"""

from . import pdfbuild

W, H = 600, 800
LAT, KOR = pdfbuild.LATIN, pdfbuild.KOREAN


def _put(page, x, y, text, size=9.0, font=LAT, right=False):
    if right:
        x -= pdfbuild.text_length(text, fontsize=size, font=font)
    page.insert_text((x, y), text, fontsize=size, font=font)


def _para(page, x, y, lines, size, font=LAT, leading=1.3):
    """줄마다 글 객체 하나. 줄 간격은 글자 크기 × leading. 다음 줄의 y 를 돌려준다."""
    for line in lines:
        _put(page, x, y, line, size=size, font=font)
        y += size * leading
    return y


LEFT_COLUMN = [
    "Synthetic paragraph one describes a fictional plant",
    "that reports energy use and water intake for a",
    "made-up year. None of these words come from a",
    "real report; they only exercise the parser.",
]
RIGHT_COLUMN = [
    "The second column has a slightly different size",
    "so the rounding of font_size is visible in the",
    "output. Readers go down this column only after",
    "the left one is finished.",
]


def _page_columns(doc):
    page = doc.new_page(W, H)
    _put(page, 40, 70, "Synthetic Baseline Report", size=18)
    y = 120
    # 문단 여덟: 단 높이가 쪽의 0.4 이상이고, 단 끝(≈650)과 꼬리 띠(≈764) 사이 틈이 단 사이 틈(≈68)의 두 배보다 좁다.
    # 그래서 꼬리 띠 판정(FOOTER_ZONE)이 꺼지면 x 절단이 먼저 와 왼쪽 꼬리 블록이 왼쪽 단 끝에 끼어든다.
    for k in range(8):
        y = _para(page, 40, y, [f"{k + 1}. {LEFT_COLUMN[0]}", *LEFT_COLUMN[1:]], size=9.0) + 22
    y = 120
    for k in range(8):
        y = _para(page, 320, y, [f"{k + 1}. {RIGHT_COLUMN[0]}", *RIGHT_COLUMN[1:]], size=9.37) + 22
    _put(page, 40, 770, "Synthetic baseline - page 1", size=7)
    _put(page, 560, 770, "1", size=7, right=True)


def _vline(page, x, y0, y1):
    page.draw_line((x, y0), (x, y1), width=0.5)


def _hline(page, x0, x1, y):
    page.draw_line((x0, y), (x1, y), width=0.5)


def _page_ruled_table(doc):
    page = doc.new_page(W, H)
    _put(page, 40, 70, "Ruled table with merged cells", size=14)
    xs = [40, 160, 240, 320, 400]
    ys = [100, 118, 136, 154, 172, 190]  # 행 다섯
    rows = [
        ("Item", "Unit", "2023", "2024"),
        ("", "MWh", "1,200", "1,304"),
        # 0열은 위 행과 세로 병합: 글은 아래 띠에 있어도 병합 칸의 첫 행에 들어가야 한다
        ("Energy", "GJ", "4,320", "4,694"),
        ("", "", "88", "91"),
        ("Waste", "t", "15", "-"),
    ]
    for i, row in enumerate(rows):
        base = ys[i] + 12
        for j, text in enumerate(row):
            if not text:
                continue
            if j >= 2:
                _put(page, xs[j + 1] - 4, base, text, size=8, right=True)
            else:
                _put(page, xs[j] + 4, base, text, size=8)
    # 행 3 은 0·1열이 가로 병합. 글은 1열 자리에만(오른쪽 맞춤) 두어 경계를 넘지 않는다:
    # 병합이면 0열(병합 칸의 첫 열)에, 병합이 아니면 1열에 들어간다. 글이 경계를 넘으면 글자 판정 갈래가 대신 병합해 버린다.
    _put(page, xs[2] - 4, ys[3] + 12, "Water total", size=8, right=True)
    # 각주 위첨자: 「1,304」 바로 뒤에 작은 「1)」
    _put(page, xs[4] - 4, ys[1] + 8, "1)", size=4)
    # 가로선: 칸마다 한 토막. 0열의 행 1·2 사이는 긋지 않는다(세로 병합). 행 3 의 위 선은 한 줄로 끊김 없이(가로 병합).
    for y_i, y in enumerate(ys):
        if y_i == 3:
            _hline(page, xs[0], xs[-1], y)
            continue
        for j in range(len(xs) - 1):
            if y_i == 2 and j == 0:
                continue
            _hline(page, xs[j], xs[j + 1], y)
    # 세로선: 행마다 한 토막. 행 3 의 xs[1] 은 긋지 않는다(가로 병합).
    for i in range(len(ys) - 1):
        for k, x in enumerate(xs):
            if i == 3 and k == 1:
                continue
            _vline(page, x, ys[i], ys[i + 1])
    _put(page, 40, 204, "1) Synthetic footnote for the ruled table.", size=6)
    _para(
        page,
        40,
        250,
        ["합성 기준선 문서의 한국어 문단이다. 실제 보고서의 글이 아니다.", "둘째 줄은 같은 문단으로 이어진다."],
        size=10,
        font=KOR,
    )


def _page_text_table(doc):
    page = doc.new_page(W, H)
    _put(page, 40, 70, "Table without rules", size=14)
    rows = [
        ("Metric", "", "2022", "2023", "2024"),
        ("Electricity", "MWh", "310", "325", "340"),
        ("Fuel", "GJ", "7.5", "8.0", "8.25"),
        ("Recycled share", "%", "61", "64", "-"),
        ("of waste", None),  # 앞 행의 이름이 줄바꿈된 줄(값 없음, 행 간격의 0.75 배 안): 앞 행에 합쳐진다
        ("Scope total", "tCO2e", "2,100", "2,050", "1,980"),
    ]
    base = 96
    for r in rows:
        if r[1] is None:
            _put(page, 40, base + 8, r[0], size=8)
            base += 8
            continue
        base += 14
        _put(page, 40, base, r[0], size=8)
        if r[1]:
            _put(page, 150, base, r[1], size=8)
        for k, v in enumerate(r[2:]):
            _put(page, 250 + 50 * k, base, v, size=8, right=True)
    _put(page, 40, 772, "Synthetic baseline - page 3", size=7)


def _page_image_only(doc):
    page = doc.new_page(W, H)
    page.insert_image((60, 80, 540, 560), gray=150, pixels=(48, 48))


def _page_korean(doc):
    page = doc.new_page(W, H)
    _put(page, 40, 70, "지어낸 한국어 소제목", size=15, font=KOR)
    _para(
        page,
        40,
        110,
        [
            "이 쪽은 한국어 글꼴의 글자와 자리를 본다. 글리프는 비어 있다.",
            "줄이 여러 개인 문단은 한 블록으로 묶여야 한다.",
            "숫자 1,234 와 영문 ABC 가 섞여도 같은 문단이다.",
        ],
        size=10,
        font=KOR,
    )
    _para(page, 40, 200, ["A closing Latin paragraph on the last page.", "It has two lines."], size=9.0)


def build(toc=False):
    """합성 PDF 의 바이트. toc=True 면 같은 다섯 쪽에 목차(수준 1 둘, 수준 2 하나)를 단다."""
    doc = pdfbuild.Doc()
    _page_columns(doc)
    _page_ruled_table(doc)
    _page_text_table(doc)
    _page_image_only(doc)
    _page_korean(doc)
    if toc:
        doc.set_toc([[1, "Overview", 1], [2, "Tables", 2], [1, "Appendix", 4]])
    return doc.tobytes()


# 고정 JSON 의 판 이름 → 짓는 인자
VARIANTS = {"synthetic": {"toc": False}, "synthetic_toc": {"toc": True}}
