"""번역 판(`layout=2`) 도표 표 거름(밴드 TRD3)의 합성 PDF 짓개. `pdfbuild`(표준 라이브러리만)로 짓는다. 글은 전부 지어낸 것이다.

`build()` 는 PDF 바이트를 돌려준다. 같은 인자면 몇 번을 지어도 바이트가 같다. 고정 해시 파일에는 넣지 않는다(시험이 구조로 단언).

쪽마다(전부 842 × 595):

1. 막대 도표. 채움 바탕 상자 안에 채움 막대(선 없음) 열 개가 아랫변을 같이 쓰고 높이가 다르다. 막대 위에 값, 축 밑에 약식 연도(`'15` 꼴)와
   `2015` 꼴 연도, 축 선 하나. 기본 판에서는 막대 변이 괘선으로 들어가 괘선 표가 선다.
2. 연표. 둥근 모서리(곡선) 세로 색 막대 하나 안에 연도 넷, 막대에 걸친 채움 바탕 상자의 오른쪽에 글 넷, 그 사이 점선 가로선.
3. 진짜 괘선 표. 머리 행 채움 띠(머리 글이 그 안에 있음)와 4×4 수치 칸.
4. 괘선 없는 숫자 표. 그리기 0, 연도 머리와 3×4 수치(글자 정렬 표).
"""

from . import pdfbuild

LAT = pdfbuild.LATIN
W, H = 842, 595

BAR_YEARS = ["'15", "'16", "'17", "'18", "'19", "'20", "'21", "'22", "'23", "2024"]
BAR_VALUES = ["31.8", "30.2", "30.7", "27.3", "28.4", "27.9", "25.3", "23.1", "24.2", "22.2"]
TIMELINE_YEARS = ["2019", "2021", "2023", "2025"]
TIMELINE_NOTES = [
    "Advisory group set up under the board",
    "First joint agreement signed with the union",
    "Wage agreement covering leave and holidays",
    "Review of the agreement with all partners",
]
RULED = [
    ["Item", "2022", "2023", "2024"],
    ["Energy", "410", "395", "380"],
    ["Water", "75", "70", "66"],
    ["Waste", "15", "14", "12"],
]
PLAIN = [
    ["Metric", "2023", "2024", "2025"],
    ["Staff", "320", "318", "330"],
    ["Hours", "41.5", "40.2", "39.8"],
]
SOFT = (0.85, 0.88, 0.92)


def _put(page, x, y, text, size=8.0, right=False):
    if right:
        x -= pdfbuild.text_length(text, fontsize=size, font=LAT)
    page.insert_text((x, y), text, fontsize=size, font=LAT)


def _rounded_bar(page, x0, y0, x1, y1, fill, r=1.5):
    """네 모서리가 둥근(곡선 `c`) 채움 막대 하나(선 없음, 변은 `l`). 좌표는 쪽 왼쪽 위 원점."""
    k = 0.5522847498 * r

    def p(x, y):
        return f"{x:.2f} {H - y:.2f}"

    path = (
        f"{p(x0 + r, y0)} m {p(x1 - r, y0)} l "
        f"{p(x1 - r + k, y0)} {p(x1, y0 + r - k)} {p(x1, y0 + r)} c {p(x1, y1 - r)} l "
        f"{p(x1, y1 - r + k)} {p(x1 - r + k, y1)} {p(x1 - r, y1)} c {p(x0 + r, y1)} l "
        f"{p(x0 + r - k, y1)} {p(x0, y1 - r + k)} {p(x0, y1 - r)} c {p(x0, y0 + r)} l "
        f"{p(x0, y0 + r - k)} {p(x0 + r - k, y0)} {p(x0 + r, y0)} c h"
    )
    page.add_content(f"q {fill[0]:.2f} {fill[1]:.2f} {fill[2]:.2f} rg {path} f Q")


def _page_bars(doc):
    page = doc.new_page(W, H)
    _put(page, 60, 80, "Pay gap by year", size=11)
    base, x = 260.0, 70.0
    page.draw_rect((60, 186, 280, 274), fill=SOFT, color=None)
    for year, value in zip(BAR_YEARS, BAR_VALUES, strict=True):
        h = 12 + 1.2 * (float(value) - 22)
        page.draw_rect((x, base - h, x + 11.3, base), fill=(0.3, 0.5, 0.8), color=None)
        _put(page, x + 5.6 - pdfbuild.text_length(value, fontsize=7) / 2, base - h - 3, value, size=7)
        _put(page, x + 5.6 - pdfbuild.text_length(year, fontsize=7) / 2, base + 11, year, size=7)
        x += 20.4
    page.draw_line((64, base), (x, base), width=0.5)
    _put(page, 60, 320, "The gap narrows every year after the new pay review started.")


def _page_timeline(doc):
    page = doc.new_page(W, H)
    _put(page, 60, 80, "Labour relations milestones", size=11)
    top, bottom = 120.0, 200.0
    page.draw_rect((80, top, 300, bottom), fill=SOFT, color=None)
    _rounded_bar(page, 62, top, 88, bottom, (0.95, 0.55, 0.2))
    step = (bottom - top) / 4
    for k, (year, note) in enumerate(zip(TIMELINE_YEARS, TIMELINE_NOTES, strict=True)):
        y = top + step * k + step / 2 + 3
        _put(page, 66, y, year, size=7)
        _put(page, 96, y, note, size=7)
        if k:
            yy = top + step * k
            page.draw_line((96, yy), (296, yy), width=0.4)
    _put(page, 60, 240, "Each milestone was agreed after talks with the worker council.")


def _page_ruled(doc):
    page = doc.new_page(W, H)
    _put(page, 60, 80, "Resource use", size=11)
    xs, ys = [60, 160, 230, 300, 370], [100, 116, 132, 148, 164]
    page.draw_rect((xs[0], ys[0], xs[-1], ys[1]), fill=SOFT, color=None)
    for i, row in enumerate(RULED):
        _put(page, xs[0] + 4, ys[i] + 11, row[0], size=7)
        for j in range(1, 4):
            _put(page, xs[j + 1] - 4, ys[i] + 11, row[j], size=7, right=True)
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y), width=0.5)
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]), width=0.5)


def _page_plain(doc):
    page = doc.new_page(W, H)
    _put(page, 60, 80, "Workforce figures", size=11)
    xs = [60, 200, 260, 320]
    for i, row in enumerate(PLAIN):
        y = 110 + 14 * i
        _put(page, xs[0], y, row[0], size=8)
        for j in range(1, 4):
            _put(page, xs[j] + 30, y, row[j], size=8, right=True)


def build():
    """합성 PDF 의 바이트."""
    doc = pdfbuild.Doc()
    _page_bars(doc)
    _page_timeline(doc)
    _page_ruled(doc)
    _page_plain(doc)
    return doc.tobytes()
