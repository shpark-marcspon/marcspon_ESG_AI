"""표·읽는 차례·위첨자 붙이기의 최악 비용(밴드 PX2 ⑧, 결함 D4 [의심]).

재현(2026-10-16, 이 기계, 1분 부하 2~3):
- 온 폭 괘선 R×C 표(칸마다 숫자) 한 쪽: 120×60 6.2초, 160×80 18.4초, 200×100 45.2초. 시간은 괘선 표의 「값 행이 쌓인
  구간」 고리(띠마다 조각 전부의 띠를 다시 셈 — 띠² × 조각)와 layout 의 위첨자 붙이기(숫자 조각 수의 제곱)에 들었다.
  고친 뒤 200×100 이 1.1초.
- 읽는 차례: 왼쪽 키 큰 상자·위 넓은 상자를 번갈아 덧댄 계단은 가를 때마다 깊이가 하나씩 는다. 상자 1000 에서
  `RecursionError`(재귀 한도 1000). 고친 뒤 상자 5000 이 2초 안.

고친 것은 산출이 같아야 한다: 옛 꼴(재귀, 조각 전부 훑기)을 여기에 그대로 두고 무작위 입력에서 견준다.
상한(`PARSER_MAX_TABLE_CELLS`·`PARSER_MAX_TABLE_RULES`)을 넘는 괘선 묶음은 그 묶음만 괘선 기반을 건너뛰고 쪽의 notes 에
까닭을 남긴다. 같은 쪽의 다른 표는 그대로다.
"""

import copy
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import pytest

import docparse.tables_lines as tables_lines
from docparse import layout
from docparse.document import parse_pdf_places
from docparse.layout import SUPERSCRIPT_SIZE_RATIO, Chunk, Seg, is_dash
from docparse.reading_order import COLUMN_MIN_HEIGHT, MIN_GAP_X, MIN_GAP_Y, _cut, _gaps, reading_order

from . import pdfbuild

PARSER_ROOT = Path(__file__).resolve().parents[1]


def ruled_grid(page, rows, cols, left, top, w, h, numbers=True):
    """온 폭 가로선 rows+1 개·온 높이 세로선 cols+1 개의 표. 칸마다 숫자 하나."""
    for i in range(rows + 1):
        page.draw_line((left, top + i * h), (left + cols * w, top + i * h), width=0.5)
    for j in range(cols + 1):
        page.draw_line((left + j * w, top), (left + j * w, top + rows * h), width=0.5)
    if numbers:
        for i in range(rows):
            for j in range(cols):
                page.insert_text(
                    (left + j * w + 1, top + i * h + h * 0.75), str((i * 7 + j) % 100), fontsize=min(h * 0.6, 8)
                )


def grid_pdf(tmp_path, rows, cols, w, h):
    doc = pdfbuild.Doc()
    page = doc.new_page(width=40 + cols * w, height=40 + rows * h)
    ruled_grid(page, rows, cols, 20, 20, w, h)
    path = tmp_path / f"grid_{rows}x{cols}.pdf"
    doc.save(path)
    return path


# ── 표 ─────────────────────────────────────────────────────────────────


def test_a_large_ruled_table_is_decomposed_within_seconds(tmp_path):
    """200×100 온 폭 괘선 표(칸 2만, 숫자 조각 2만) 한 쪽. 고치기 전 45초, 고친 뒤 1초 남짓."""
    path = grid_pdf(tmp_path, 200, 100, 10, 8)
    started = time.monotonic()
    document, _ = parse_pdf_places(path)
    took = time.monotonic() - started
    [table] = document["tables"]
    assert (table["n_rows"], table["n_cols"], table["method"]) == (200, 100, "lines")
    assert took < 10, f"{took:.1f}초"


def two_tables_page(tmp_path):
    """작은 표(4×3) 위, 큰 표(30×20) 아래. 한 쪽."""
    doc = pdfbuild.Doc()
    page = doc.new_page(width=500, height=500)
    ruled_grid(page, 4, 3, 20, 20, 40, 14)
    ruled_grid(page, 30, 20, 20, 120, 20, 12)
    path = tmp_path / "two.pdf"
    doc.save(path)
    return path


def test_without_limits_both_tables_are_ruled(tmp_path):
    document, _ = parse_pdf_places(two_tables_page(tmp_path))
    assert sorted((t["n_rows"], t["n_cols"], t["method"]) for t in document["tables"]) == [
        (4, 3, "lines"),
        (30, 20, "lines"),
    ]
    assert document["pages"][0]["notes"] == []


@pytest.mark.parametrize(
    ("name", "value", "note"),
    [
        ("MAX_TABLE_CELLS", 200, "lines_table_skipped:too_many_cells:600"),
        ("MAX_TABLE_RULES", 40, "lines_table_skipped:too_many_rules:52"),
    ],
)
def test_over_a_limit_only_that_table_gives_up_and_its_text_stays(tmp_path, monkeypatch, name, value, note):
    """상한을 넘은 큰 표만 괘선 기반을 포기한다(표 대신 글자 정렬 기반·글로). 작은 표는 그대로, 문서 전체는 거절하지 않는다."""
    monkeypatch.setattr(tables_lines, name, value)
    document, places = parse_pdf_places(two_tables_page(tmp_path))
    assert document["pages"][0]["notes"] == [note]
    ruled = [(t["n_rows"], t["n_cols"]) for t in document["tables"] if t["method"] == "lines"]
    assert ruled == [(4, 3)]
    assert all(t["bbox"][1] >= 110 for t in document["tables"] if t["method"] != "lines")  # 큰 표 자리만
    # 큰 표의 글은 버려지지 않았다: 글자 정렬 기반 표의 칸이나 글 블록에 남는다
    big_text = [t for t in document["tables"] if t["method"] == "text" for row in t["cells"] for t in row if t]
    big_text += [b["text"] for b in document["blocks"] if b.get("text") and b["bbox"][1] >= 110]
    assert sum(len(s.split()) for s in big_text) >= 30 * 20 * 0.9
    assert places is not None


@pytest.mark.parametrize(("env", "value"), [("PARSER_MAX_TABLE_CELLS", "7"), ("PARSER_MAX_TABLE_RULES", "9")])
def test_limits_come_from_the_environment(env, value):
    code = f"import docparse.tables_lines as t; print(t.{env.removeprefix('PARSER_')})"
    done = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PARSER_ROOT,
        env={**os.environ, env: value},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0 and done.stdout.strip() == value, done.stderr


@pytest.mark.parametrize("value", ["0", "-1", "many"])
def test_a_bad_limit_refuses_to_start(value):
    done = subprocess.run(
        [sys.executable, "-c", "import docparse.tables_lines"],
        cwd=PARSER_ROOT,
        env={**os.environ, "PARSER_MAX_TABLE_CELLS": value},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode != 0 and "ValueError" in done.stderr


def test_default_limits_are_far_above_the_public_reports():
    """공개 보고서 여덟(2026-10-16 잼)의 최대: 격자 후보 칸 1739, 괘선 토막 594. 기본값은 그 열 배 남짓."""
    assert tables_lines.MAX_TABLE_CELLS >= 10 * 1739
    assert tables_lines.MAX_TABLE_RULES >= 8 * 594


def scanning_h_cover(hs, y, x0, x1):
    """고치기 전의 꼴(괘선 목록 전부를 훑음). 산출이 같은지 견주는 데만 쓴다."""
    need = 0.5 * (x1 - x0)
    return any(abs(s.pos - y) <= tables_lines.Y_CLUSTER_GAP and min(s.a1, x1) - max(s.a0, x0) >= need for s in hs)


def scanning_v_cover(vs, x, y0, y1):
    need = 0.5 * (y1 - y0)
    return any(abs(s.pos - x) <= tables_lines.X_CLUSTER_GAP + 0.5 and min(s.a1, y1) - max(s.a0, y0) >= need for s in vs)


def scanning_h_continuous(hs, y, x):
    return any(abs(s.pos - y) <= tables_lines.Y_CLUSTER_GAP and s.a0 <= x - 2.5 and s.a1 >= x + 2.5 for s in hs)


def test_indexed_cover_checks_match_the_full_scan():
    """덮음 검사(`_h_cover`·`_v_cover`·`_h_continuous`)가 `_ByPos` 로 고른 토막만 봐도 목록 전부를 훑은 것과 같다.

    토막의 pos 를 묻는 자리 ± 허용폭(tol) 언저리에 몰아, 고르는 폭이 tol 보다 좁거나 넓게 어긋나면 갈리게 한다
    (검증 PX2 V7: `near` 의 여유를 tol×0.5 로 줄여도 다른 시험은 다 초록이었다).
    """
    rng = random.Random(20261017)  # noqa: S311 — 시험 입력을 고르는 씨앗 고정 난수(암호 아님)
    h_tol, v_tol = tables_lines.Y_CLUSTER_GAP, tables_lines.X_CLUSTER_GAP + 0.5
    for case in range(1500):
        p = rng.uniform(50, 150)

        def segs(tol, p=p):
            out = []
            for _ in range(rng.randint(0, 12)):
                pos = p + rng.choice((-1, 1)) * tol * rng.choice((0.0, 0.3, 0.6, 0.9, 0.999, 1.0, 1.001, 1.2, 2.0))
                a0 = rng.uniform(0, 100)
                out.append(Seg(a0, a0 + rng.uniform(3, 120), pos))
            return out

        hs, vs = segs(h_tol), segs(v_tol)
        lo = rng.uniform(0, 80)
        hi = lo + rng.uniform(1, 80)
        mid = rng.uniform(0, 120)
        ih, iv = tables_lines._ByPos(hs), tables_lines._ByPos(vs)
        assert tables_lines._h_cover(ih, p, lo, hi) == scanning_h_cover(hs, p, lo, hi), case
        assert tables_lines._v_cover(iv, p, lo, hi) == scanning_v_cover(vs, p, lo, hi), case
        assert tables_lines._h_continuous(ih, p, mid) == scanning_h_continuous(hs, p, mid), case


# ── 읽는 차례 ───────────────────────────────────────────────────────────


def recursive_reading_order(boxes, page_height=None):
    """고치기 전의 꼴(재귀). 산출이 같은지 견주는 데만 쓴다."""
    state = {"columns": 1 if boxes else 0}

    def walk(indices):
        if len(indices) <= 1:
            return list(indices)
        xo, xg = _gaps(indices, boxes, 0, 2)
        yo, yg = _gaps(indices, boxes, 1, 3)
        best_x = max((g for g, _ in xg), default=0.0)
        best_y = max((g for g, _ in yg), default=0.0)
        if best_x >= MIN_GAP_X and best_x >= 0.5 * best_y:
            groups = _cut(xo, xg, MIN_GAP_X)
            if page_height:
                height = max(boxes[i][3] for i in indices) - min(boxes[i][1] for i in indices)
                if height >= COLUMN_MIN_HEIGHT * page_height:
                    state["columns"] = max(state["columns"], len(groups))
            return [i for g in groups for i in walk(g)]
        if best_y >= MIN_GAP_Y:
            return [i for g in _cut(yo, yg, max(MIN_GAP_Y, 0.5 * best_y)) for i in walk(g)]
        if best_x >= MIN_GAP_X:
            return [i for g in _cut(xo, xg, MIN_GAP_X) for i in walk(g)]
        return sorted(indices, key=lambda i: (boxes[i][1], boxes[i][0]))

    from docparse.reading_order import FOOTER_ZONE

    all_idx = list(range(len(boxes)))
    footer = []
    if page_height:
        footer = [i for i in all_idx if boxes[i][1] >= FOOTER_ZONE * page_height]
        if len(footer) == len(all_idx):
            footer = []
    foot = set(footer)
    body = [i for i in all_idx if i not in foot]
    order = walk(body) + sorted(footer, key=lambda i: (round(boxes[i][1] / 6), boxes[i][0]))
    return order, state["columns"]


def staircase(n):
    """왼쪽에 키 큰 상자(x 틈 8.5) / 위에 넓은 상자(y 틈 3.5)를 번갈아 덧댄다. 가를 때마다 상자 하나만 떨어진다(깊이 ~n)."""
    boxes = [[0.0, 0.0, 2.0, 4.0]]
    x0, y0, x1, y1 = boxes[0]
    for k in range(1, n):
        b = [x0 - 10.5, y0, x0 - 8.5, y1] if k % 2 else [x0, y0 - 7.5, x1, y0 - 3.5]
        boxes.append(b)
        x0, y0, x1, y1 = min(x0, b[0]), min(y0, b[1]), max(x1, b[2]), max(y1, b[3])
    return [[a - x0 + 10, b - y0 + 10, c - x0 + 10, d - y0 + 10] for a, b, c, d in boxes], y1 - y0 + 100


def test_a_deep_staircase_does_not_hit_the_recursion_limit():
    """고치기 전에는 상자 1000 에서 RecursionError. 차례는 바깥에서 안으로(왼쪽 상자, 위 상자, …)."""
    boxes, height = staircase(2000)
    started = time.monotonic()
    order, _columns = reading_order(boxes, height)
    assert time.monotonic() - started < 10
    assert order == list(range(1999, -1, -1))


def test_the_stack_gives_the_same_order_as_the_recursion():
    rng = random.Random(20261016)  # noqa: S311 — 시험 입력을 고르는 씨앗 고정 난수(암호 아님)
    for case in range(400):
        n = rng.randint(0, 60)
        boxes = []
        for _ in range(n):
            x, y = rng.choice(range(0, 600, 7)), rng.choice(range(0, 800, 5))
            boxes.append([x, y, x + rng.choice((3, 20, 120, 260)), y + rng.choice((2, 9, 40, 300))])
        height = rng.choice((None, 800, 400))
        assert reading_order(boxes, height) == recursive_reading_order(boxes, height), case
    boxes, height = staircase(400)
    assert reading_order(boxes, height) == recursive_reading_order(boxes, height)


# ── 위첨자 붙이기 ───────────────────────────────────────────────────────


def scanning_attach(chunks):
    """고치기 전의 꼴(조각 전부를 훑음). 산출이 같은지 견주는 데만 쓴다."""
    chunks.sort(key=lambda c: (c.y0, c.x0))
    used = set()
    for i, c in enumerate(chunks):
        if not layout._MARK_RE.match(c.text.replace(" ", "")):
            continue
        for j, base in enumerate(chunks):
            if j == i or j in used or i in used:
                continue
            if (
                c.size < SUPERSCRIPT_SIZE_RATIO * base.size
                and abs(c.x0 - base.x1) <= 1.5
                and c.y0 < base.yc < c.y1 + base.size
            ):
                if c.y1 < base.y0 or c.y0 > base.y1:
                    continue
                sup = c.text.replace(" ", "")
                if base.numeric or is_dash(base.text):
                    layout._add_mark(base, c, sup)  # 표시와 글자 상자는 같은 함수(TRD2) — 견주는 것은 찾는 차례
                else:
                    if base.glyphs is not None:
                        base.glyphs = (
                            base.glyphs + [g for ch, g in zip(c.text, c.glyphs, strict=False) if ch != " "]
                            if c.glyphs is not None
                            else None
                        )
                    base.text += sup
                base.x1 = max(base.x1, c.x1)
                used.add(i)
                break
    return [c for i, c in enumerate(chunks) if i not in used]


def random_chunks(rng, n):
    out = []
    for _ in range(n):
        x0, y0 = rng.uniform(0, 300), rng.uniform(0, 300)
        size = rng.choice((5.0, 6.0, 9.0, 10.0, 12.0))
        text = rng.choice(("12.5", "1)", "*", "2", "가나", "-", "Revenue", "3,4", "†"))
        width = 0.5 * size * len(text)
        glyphs = [(x0 + k, y0, x0 + k + 1, y0 + size) for k in range(len(text))] if rng.random() < 0.5 else None
        out.append(Chunk(x0, y0, x0 + width, y0 + size, text, size, glyphs=glyphs))
        if rng.random() < 0.4:  # 바로 오른쪽 위에 작은 표시를 붙인다
            mark = rng.choice(("1)", "2", "*", "12"))
            mx0 = x0 + width + rng.uniform(-1.6, 1.6)
            out.append(Chunk(mx0, y0 - 2, mx0 + 2 * len(mark), y0 + 0.6 * size, mark, 0.6 * size))
    return out


def test_indexed_superscripts_match_the_full_scan():
    rng = random.Random(1016)  # noqa: S311 — 시험 입력을 고르는 씨앗 고정 난수(암호 아님)
    for case in range(300):
        chunks = random_chunks(rng, rng.randint(0, 80))
        want = scanning_attach(copy.deepcopy(chunks))
        assert layout._attach_superscripts(copy.deepcopy(chunks)) == want, case


def test_many_numbers_on_a_page_attach_quickly():
    """숫자 조각 2만(200×100 칸)의 쪽. 조각 전부를 훑으면 14초, 칸으로 나눠 보면 1초 안."""
    chunks = [
        Chunk(20 + j * 10 + 1, 20 + i * 8 + 1, 20 + j * 10 + 9, 20 + i * 8 + 6, str((i * 7 + j) % 100), 4.8)
        for i in range(200)
        for j in range(100)
    ]
    started = time.monotonic()
    assert len(layout._attach_superscripts(chunks)) == 20000
    assert time.monotonic() - started < 5
