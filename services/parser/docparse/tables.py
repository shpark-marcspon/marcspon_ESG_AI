"""표 추출 전략의 조합: 괘선 기반 → 실패 시 글자 정렬 기반. 표마다 쓰인 전략을 기록한다."""

from .layout import page_chunks, page_rules
from .table_model import METHOD_LINES, METHOD_NONE, METHOD_TEXT, STATUS_FAILED, Table
from .tables_lines import find_lines_tables
from .tables_text import cut_at_gutters, find_text_tables

STRATEGIES = ("auto", METHOD_LINES, METHOD_TEXT)


def _inside(c, box, pad=1.0):
    return box[0] - pad <= c.xc <= box[2] + pad and box[1] - pad <= c.yc <= box[3] + pad


def _has_value_rows(chunks):
    from .tables_text import cluster_rows

    rows = cluster_rows(chunks)
    return sum(1 for r in rows if len(r) >= 2 and any(c.value_like for c in r)) >= 2


def extract_tables(page, strategy="auto", chunks=None, notes=None, layout=1):
    """쪽 하나에서 표를 뽑는다. 위→아래, 왼쪽→오른쪽 순으로 돌려준다.

    strategy: auto(괘선 기반 → 남은 영역에 글자 정렬 기반) | lines | text
    layout: 분해 판(`document.LAYOUTS`). 기본 1 은 그대로다.
    격자를 세우지 못한 표 후보는 빈 표가 아니라 status=failed, method=none 인 항목으로 남긴다.
    상한을 넘어 괘선 기반을 건너뛴 표 후보는 표를 내지 않고 그 까닭을 `notes`(주면)에 덧붙인다.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"알 수 없는 전략: {strategy}")
    if chunks is None:
        chunks, _ = page_chunks(page)
    tables, failed_boxes = [], []
    rest = list(chunks)
    if strategy in ("auto", METHOD_LINES):
        hs, vs = page_rules(page)
        tables, rejected = (
            find_lines_tables(hs, vs, chunks, notes, layout=layout)
            if layout >= 2
            else find_lines_tables(hs, vs, chunks, notes)
        )
        rest = [c for c in chunks if not any(_inside(c, t.bbox) for t in tables)]
        # 괘선은 있는데 격자가 서지 않았고 그 안에 값 줄이 있으면 실패한 표 후보다.
        # auto 에서는 글자 정렬 기반이 그 자리를 표로 세우지 못했을 때만 failed 로 남는다(아래 겹침 검사).
        failed_boxes = [b for b in rejected if _has_value_rows([c for c in rest if _inside(c, b)])]
    if strategy in ("auto", METHOD_TEXT):
        text_tables, text_failed = find_text_tables(rest)
        if layout >= 2:
            text_tables = _cut_text_tables(text_tables, chunks, page.rect.height)
        tables.extend(text_tables)
        failed_boxes.extend(text_failed)
    for b in failed_boxes:
        if any(_overlap(b, t.bbox) > 0.5 * _area(b) for t in tables):
            continue
        tables.append(
            Table(
                bbox=[round(v, 1) for v in b],
                grid=[],
                method=METHOD_NONE,
                status=STATUS_FAILED,
                notes=["grid_not_built"],
                header={"rows": [], "cols": [], "basis": "empty"},
            )
        )
    if layout >= 2:
        tables = _drop_figure_tables(page, tables, chunks, notes)
    tables.sort(key=lambda t: (round(t.bbox[1] / 20), t.bbox[0]))
    if layout >= 2:
        _one_table_per_chunk(tables)
    return tables


def _cut_text_tables(tables, chunks, page_height):
    """번역 판(2): 쪽의 단 틈을 건너는 글자 정렬 표를 틈에서 잘라 다시 세운다(`tables_text.cut_at_gutters`).

    표로 다시 서지 못한 조각은 어느 칸에도 없으므로 글 블록으로 간다(`document`). 괘선 표는 건드리지 않는다.
    """
    out = []
    for t in tables:
        cut = cut_at_gutters(t, chunks, page_height)
        out.extend([t] if cut is None else cut[0])
    return out


# 도표 표 거름(번역 판 2, 밴드 TRD3)의 문턱. 근거는 BASE 458edea8 layout 2 실측(TRD3 보고): 정답 표 33(괘선 33)과
# 합성 고정값 표는 아래 두 신호가 모두 0 이고, 재현 PDF 의 막대 도표 둘은 막대 줄 4·11,
# 연표는 곡선 닿은 행 1.0·빈 칸 0.56.
FIGURE_BAR_RUN_MIN = 3
"""막대 줄: 표 상자 안 「글 없는 채움 사각형」(선 없음, 두 변 3pt 이상) 중 아랫변(세로 막대)이나 왼변(가로 막대)을
같이 쓰고 길이가 둘 이상으로 갈리는 것의 수. 정답 33표 최대 0, 재현 막대 도표 4·11 — 그 틈의 아래 끝."""
FIGURE_EMPTY_RATIO_MIN = 0.5
"""곡선 갈래의 빈 칸 비율 하한. 정답 33표 최대 0.35, 재현 연표 0.56.
(그리기 0 인 합성 L6 표 0.50 은 곡선이 없어 남는다.)"""
FIGURE_CURVE_ROWS_MIN = 1.0
"""곡선 갈래: 글이 든 행 중 곡선 그리기(둥근 막대·도식 상자)와 세로로 겹치는 행의 비율 하한. 정답 33표는 곡선 0.
1.0 미만이면 도식 밑에 진짜 표가 한 격자로 붙은 꼴(공개 보고서 표본 0.30·0.69)까지 빠져서 모든 행을 요구한다."""


def _figure_signals(t, drawings, chunks, pad=2.0):
    """(막대 줄, 곡선 수, 곡선 닿은 행 비율). 표 상자(±pad) 안에 다 든 그리기만 센다."""
    b = t.bbox
    inside = [
        d
        for d in drawings
        if b[0] - pad <= d["rect"].x0 <= d["rect"].x1 <= b[2] + pad
        and b[1] - pad <= d["rect"].y0 <= d["rect"].y1 <= b[3] + pad
    ]
    bars = [
        r
        for d in inside
        if d.get("fill") is not None
        and d.get("color") is None
        and all(it[0] in ("re", "qu") for it in d["items"])
        and (r := d["rect"]).width >= 3
        and r.height >= 3
        and not any(_inside(c, (r.x0, r.y0, r.x1, r.y1), pad=0) for c in chunks)
    ]
    run = 0
    for edge, size in ((lambda r: r.y1, lambda r: r.height), (lambda r: r.x0, lambda r: r.width)):
        groups = {}
        for r in bars:
            groups.setdefault(round(edge(r)), []).append(round(size(r)))
        run = max([run] + [len(g) for g in groups.values() if len(set(g)) >= 2])
    curves = [d["rect"] for d in inside if any(it[0] == "c" for it in d["items"])]
    spans = {}
    for (i, _j), cs in t.cell_chunks.items():
        for c in cs:
            lo, hi = spans.get(i, (c.y0, c.y1))
            spans[i] = (min(lo, c.y0), max(hi, c.y1))
    touched = sum(1 for lo, hi in spans.values() if any(r.y0 < hi and r.y1 > lo for r in curves))
    return run, len(curves), (touched / len(spans) if spans else 0.0)


def _is_figure_table(t, drawings, chunks):
    """막대 도표·연표처럼 그리기가 표를 흉내 낸 것인가. 그리기 신호가 반드시 있어야 한다(글자 신호만으로 빼지 않음)."""
    if not t.grid:
        return False
    run, curves, curve_rows = _figure_signals(t, drawings, chunks)
    if run >= FIGURE_BAR_RUN_MIN:
        return True
    cells = [c for row in t.grid for c in row]
    empty = sum(1 for c in cells if not c) / len(cells)
    return curves >= 1 and empty >= FIGURE_EMPTY_RATIO_MIN and curve_rows >= FIGURE_CURVE_ROWS_MIN


def _drop_figure_tables(page, tables, chunks, notes):
    """번역 판(2): 막대 도표·연표처럼 그리기(채움 막대·둥근 도형)가 괘선 격자를 세운 표를 뺀다(괘선·글자 정렬 모두).

    뺀 표의 조각은 어느 칸에도 없으므로 글 블록으로 간다(`document`). 뺀 표 상자 안에 중심이 있는 실패 항목도 뺀다.
    `notes`(주면)에 `figure_table_dropped:<method>:<x0>,<y0>,<x1>,<y1>` 과 `figure_failed_dropped:<수>` 를 남긴다.
    """
    if not any(t.grid for t in tables):
        return tables
    drawings = page.get_drawings()
    dropped = [t for t in tables if _is_figure_table(t, drawings, chunks)]
    if not dropped:
        return tables
    failed = [
        t
        for t in tables
        if not t.grid
        and any(_inside_point(((t.bbox[0] + t.bbox[2]) / 2, (t.bbox[1] + t.bbox[3]) / 2), f.bbox) for f in dropped)
    ]
    if notes is not None:
        for t in dropped:
            notes.append(f"figure_table_dropped:{t.method}:" + ",".join(f"{v:.1f}" for v in t.bbox))
        if failed:
            notes.append(f"figure_failed_dropped:{len(failed)}")
    gone = {id(t) for t in dropped + failed}
    return [t for t in tables if id(t) not in gone]


def _inside_point(p, box, pad=1.0):
    return box[0] - pad <= p[0] <= box[2] + pad and box[1] - pad <= p[1] <= box[3] + pad


def _one_table_per_chunk(tables):
    """번역 판(2): 조각 하나는 표 하나의 칸에만 둔다. 두 표의 칸에 든 조각(큰 괘선 틀 안에 안긴 표)은
    넓이가 가장 작은 표에 남기고 다른 표의 칸 글에서 뺀다(칸 글과 각주 표시를 남은 조각으로 다시 쓴다.
    행·열은 지우지 않는다).
    `t.notes` 에 `chunks_moved_to_inner_table:<수>` 를 남긴다.
    """
    owner = {}
    for t in tables:
        for cs in t.cell_chunks.values():
            for c in cs:
                if id(c) not in owner or _area(t.bbox) < _area(owner[id(c)].bbox):
                    owner[id(c)] = t
    for t in tables:
        moved = 0
        for (i, j), cs in list(t.cell_chunks.items()):
            kept = [c for c in cs if owner[id(c)] is t]
            if len(kept) == len(cs):
                continue
            moved += len(cs) - len(kept)
            t.grid[i][j] = " ".join(c.text for c in kept if c.text)
            t.footnote_marks = [m for m in t.footnote_marks if (m["row"], m["col"]) != (i, j)] + [
                {"row": i, "col": j, "mark": m} for c in kept for m in c.marks
            ]
            if kept:
                t.cell_chunks[(i, j)] = kept
            else:
                del t.cell_chunks[(i, j)]
        if moved:
            t.notes.append(f"chunks_moved_to_inner_table:{moved}")


def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _overlap(a, b):
    return _area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])
