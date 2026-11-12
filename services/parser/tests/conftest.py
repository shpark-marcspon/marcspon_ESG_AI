"""테스트 공용 도구. 합성(synthetic) PDF 는 `pdfbuild`(표준 라이브러리만)로 그 자리에서 짓는다. 실제 보고서의 값이 아니다.

원본(esg-lab `py/docparse/tests/conftest.py`, 커밋 2e2c2c4)은 PDF 라이브러리로 짓고 두 엔진으로 번갈아 돌렸다.
여기는 엔진이 pdfium 하나라 엔진 매개변수가 없다.
"""

import os
import tempfile

import pytest

from docparse.config import MissingPathError, gold_dir, reports_dir
from docparse.engine import open_pdf

from . import pdfbuild

FONT = pdfbuild.LATIN
SIZE = 8


def put(page, x, y, text, size=SIZE, right=False, font=FONT):
    """(x, y) 를 기준선 왼쪽 끝(right=True 면 오른쪽 끝)으로 글자를 쓴다."""
    if right:
        x -= pdfbuild.text_length(text, fontsize=size, font=font)
    page.insert_text((x, y), text, fontsize=size, font=font)


def hline(page, x0, x1, y, width=0.25):
    page.draw_line((x0, y), (x1, y), width=width)


_REOPENED = []


@pytest.fixture(autouse=True)
def _close_reopened():
    yield
    while _REOPENED:
        doc, path = _REOPENED.pop()
        doc.close()
        os.unlink(path)


def seam(obj):
    """`pdfbuild` 로 지은 쪽(또는 문서)을 엔진의 쪽(문서)으로 연다. 분해 규칙에는 이것을 건넨다. 테스트가 끝나면 닫히고 지워진다."""
    if isinstance(obj, pdfbuild.Page):
        doc, index = obj.parent, obj.number
    elif isinstance(obj, pdfbuild.Doc):
        doc, index = obj, None
    else:
        return obj
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(doc.tobytes())
    opened = open_pdf(f.name)
    _REOPENED.append((opened, f.name))
    return opened if index is None else opened[index]


@pytest.fixture
def synthetic_ruled_page():
    """세로선 없이 셀마다 가로 토막만 있는 합성 표. 0열은 두 행이 세로 병합(토막 없음)."""
    doc = pdfbuild.Doc()
    page = doc.new_page(width=400, height=300)
    xs = [40, 120, 160, 230, 300]
    rows = [
        ("Item", "Unit", "2023", "2024"),
        ("Alpha", "t", "1,200", "1,304"),
        ("", "kg", "15", "-"),
        ("Beta", "t", "7.5", "8.25"),
    ]
    y = 50
    for i, r in enumerate(rows):
        base = y + 10
        if r[0]:
            put(page, xs[0] + 2, base, r[0])
        put(page, xs[1] + 2, base, r[1])
        put(page, xs[3] - 2, base, r[2], right=True)
        put(page, xs[4] - 2, base, r[3], right=True)
        y += 14
        for j in range(4):
            if i == 1 and j == 0:
                continue  # Alpha 는 아래 행과 병합: 0열 토막을 그리지 않는다
            hline(page, xs[j], xs[j + 1], y)
    for j in range(4):
        hline(page, xs[j], xs[j + 1], 50, width=1.0)
    return page


@pytest.fixture
def synthetic_ruleless_page():
    """괘선이 전혀 없는 합성 표 두 개가 좌우로 나란히 있는 쪽."""
    doc = pdfbuild.Doc()
    page = doc.new_page(width=600, height=300)
    for ox, name in ((40, "Left"), (320, "Right")):
        rows = [
            (name, "", "2023", "2024", "2025"),
            ("Energy use", "GWh", "100", "110", "121"),
            ("Water", "kt", "5.5", "6.0", "6.5"),
            ("Waste recycled", "%", "90", "91", "-"),
            ("Emissions", "tCO2e", "1,000", "2,000", "3,000"),
        ]
        for i, r in enumerate(rows):
            base = 60 + 14 * i
            put(page, ox, base, r[0])
            if r[1]:
                put(page, ox + 90, base, r[1])
            for k, v in enumerate(r[2:]):
                put(page, ox + 170 + 40 * k, base, v, right=True)
    return page


def require_reports():
    """공개 보고서 PDF 의 폴더. 없으면 건너뛰지 않고 실패한다: 원본이 없으면 「못 쟀다」이지 통과가 아니다."""
    try:
        d = reports_dir()
    except MissingPathError as e:
        pytest.fail(f"{e}. 원본이 없으면 회귀 테스트는 「못 쟀다」이지 통과가 아니다.")
    if not d.is_dir():
        pytest.fail(f"원본 PDF 디렉터리가 없다: {d}. PARSER_REPORTS_DIR 로 위치를 지정한다.")
    return d


def require_gold():
    """정답 표의 폴더. 없으면 건너뛰지 않고 실패한다."""
    try:
        d = gold_dir()
    except MissingPathError as e:
        pytest.fail(f"{e}. 정답 표가 없으면 회귀 테스트는 「못 쟀다」이지 통과가 아니다.")
    if not d.is_dir():
        pytest.fail(f"정답 표 디렉터리가 없다: {d}. PARSER_GOLD_DIR 로 위치를 지정한다.")
    return d
