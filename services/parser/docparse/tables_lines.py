"""괘선 기반 표 추출.

InDesign 계열 PDF 는 가로 괘선을 셀마다 한 토막씩 그린다. 그래서 세로선이 하나도 없는 표라도
가로 토막의 양 끝 x 가 열 경계가 되고, 토막의 y 가 행 경계가 된다. 세로로 병합된 셀은 그 열에
토막이 없는 것으로 드러난다. (pymupdf `find_tables` 는 세로선이 없으면 표로 보지 않는다.)

절차: 괘선 토막을 표 단위로 묶는다 → x·y 경계로 격자를 만든다 → 변이 없는 곳은 병합으로 본다
      → 글자 조각을 셀에 넣는다. 병합 셀의 글자는 병합 범위의 첫 행·첫 열에 둔다.
"""

import itertools
import os
from bisect import bisect_left, bisect_right
from statistics import median

from .layout import Seg, cluster_values
from .table_model import METHOD_LINES, STATUS_LOW, STATUS_OK, Table, estimate_header, prune_empty, pruned_index

SAME_LEVEL_TOL = 0.75  # 같은 높이의 가로선으로 보는 y 차이 (pt)
TOUCH_GAP = 4.0  # 같은 높이에서 이어진 토막으로 보는 x 틈
MAX_ROW_GAP = 40.0  # 위아래 가로선이 같은 표에 속한다고 보는 최대 간격
X_CLUSTER_GAP = 2.0
Y_CLUSTER_GAP = 1.5


def _limit(name: str, default: int) -> int:
    """상한은 환경 변수로 올릴 수 있다. 0 이하나 숫자가 아닌 값이면 import 때 죽는다(조용히 상한 없음이 되지 않게)."""
    value = int(os.environ.get(name, default))
    if value <= 0:
        raise ValueError(f"{name} 은 0보다 커야 한다: {value}")
    return value


# 괘선 묶음 하나(표 후보)의 크기 상한(밴드 PX2 ⑧). 넘으면 그 묶음만 괘선 기반을 포기하고, 그 글자는
# 글자 정렬 기반·글로 간다. 기본값은 공개 보고서 여덟(2026-10-16 잼)의 최대(격자 후보 칸 1739, 괘선 토막 594)의
# 열 배 남짓이다. 근거는 README 「분해 안의 상한」.
MAX_TABLE_RULES = _limit("PARSER_MAX_TABLE_RULES", 5000)  # 묶음 안 괘선 토막(가로+세로) 수
MAX_TABLE_CELLS = _limit("PARSER_MAX_TABLE_CELLS", 20000)  # x·y 경계로 세운 격자 후보의 칸 수


class _TooLarge(Exception):
    """표 후보가 상한을 넘었다. 글은 쪽의 notes 에 남길 표시다."""


class _ByPos:
    """괘선 토막을 pos(가로선은 y, 세로선은 x)로 정렬해 둔 것. `near` 는 pos 가 p±tol 안인 토막만 돌려준다.

    덮음 검사(`_h_cover` 따위)가 칸마다 괘선 전부를 훑지 않게 한다(칸 × 괘선 → 칸 × 그 높이의 괘선). 판정은 같다:
    고르는 쪽이 원래의 조건을 그대로 다시 본다.
    """

    def __init__(self, segs: list[Seg]):
        self.segs = sorted(segs, key=lambda s: s.pos)
        self.keys = [s.pos for s in self.segs]

    def near(self, p, tol):
        slack = tol + 1e-6
        return self.segs[bisect_left(self.keys, p - slack) : bisect_right(self.keys, p + slack)]


class _DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def group_rules(hs, vs):
    """괘선 토막을 표 후보 단위로 묶는다. [(가로선들, 세로선들)]"""
    n = len(hs)
    dsu = _DSU(n + len(vs))
    order = sorted(range(n), key=lambda i: hs[i].pos)
    for oi, i in enumerate(order):
        a = hs[i]
        for j in order[oi + 1 :]:
            b = hs[j]
            dy = b.pos - a.pos
            if dy > MAX_ROW_GAP:
                break
            gap = max(a.a0, b.a0) - min(a.a1, b.a1)
            if dy <= SAME_LEVEL_TOL:
                if gap <= TOUCH_GAP:
                    dsu.union(i, j)
            elif -gap >= 0.5 * min(a.length, b.length):
                dsu.union(i, j)
    for k, v in enumerate(vs):
        for i, h in enumerate(hs):
            if h.a0 - 2 <= v.pos <= h.a1 + 2 and v.a0 - 2 <= h.pos <= v.a1 + 2:
                dsu.union(n + k, i)
    groups = {}
    for i in range(n):
        groups.setdefault(dsu.find(i), ([], []))[0].append(hs[i])
    for k in range(len(vs)):
        root = dsu.find(n + k)
        if root in groups:
            groups[root][1].append(vs[k])
    return list(groups.values())


def _h_cover(hs, y, x0, x1):
    need = 0.5 * (x1 - x0)
    return any(
        abs(s.pos - y) <= Y_CLUSTER_GAP and min(s.a1, x1) - max(s.a0, x0) >= need for s in hs.near(y, Y_CLUSTER_GAP)
    )


def _v_cover(vs, x, y0, y1):
    need = 0.5 * (y1 - y0)
    return any(
        abs(s.pos - x) <= X_CLUSTER_GAP + 0.5 and min(s.a1, y1) - max(s.a0, y0) >= need
        for s in vs.near(x, X_CLUSTER_GAP + 0.5)
    )


def _h_continuous(hs, y, x):
    return any(
        abs(s.pos - y) <= Y_CLUSTER_GAP and s.a0 <= x - 2.5 and s.a1 >= x + 2.5 for s in hs.near(y, Y_CLUSTER_GAP)
    )


def _pick_col(chunk, xs):
    """조각이 들어갈 열. 한 열에 60% 이상 들어 있으면 그 열, 여러 열에 걸치면 걸친 열 중 가장 왼쪽."""
    width = max(chunk.x1 - chunk.x0, 0.1)
    overlaps = [(max(0.0, min(chunk.x1, xs[j + 1]) - max(chunk.x0, xs[j])), j) for j in range(len(xs) - 1)]
    best = max(overlaps)
    if best[0] <= 0:
        return None
    if best[0] >= 0.6 * width:
        return best[1]
    wide = [j for ov, j in overlaps if ov >= min(3.0, 0.3 * width)]
    return min(wide) if wide else best[1]


def _text_lines(chunks):
    """조각들의 y 중심을 줄 단위로 묶어 줄 중심 목록을 돌려준다."""
    if not chunks:
        return []
    tol = 0.45 * median(c.y1 - c.y0 for c in chunks)
    return cluster_values([c.yc for c in chunks], tol)


def _split_level(ys, xs, chunks):
    """위아래로 붙어 있는 두 표가 한 묶음이 된 경우, 두 표 사이 띠의 번호를 돌려준다(없으면 None).

    표 사이 띠는 보통 행보다 높고, 비어 있거나 글자 줄 사이에 빈 공간(각주와 다음 표 머리글 사이)이 있다.
    줄바꿈된 셀은 줄 사이가 붙어 있어 여기에 걸리지 않는다.
    """
    heights = [b - a for a, b in itertools.pairwise(ys)]
    med = median(heights)
    inside = [c for c in chunks if xs[0] - 2 <= c.xc <= xs[-1] + 2]
    for i, h in enumerate(heights):
        if h <= 1.5 * med or i == 0 or i == len(heights) - 1:
            continue
        band = sorted((c for c in inside if ys[i] < c.yc < ys[i + 1]), key=lambda c: c.y0)
        if not band:
            return i
        line_h = median(c.y1 - c.y0 for c in band)
        reach = band[0].y1
        for c in band[1:]:
            if c.y0 - reach > 0.6 * line_h:
                return i
            reach = max(reach, c.y1)
    return None


def build_lattice(hs, vs, chunks, layout=1):
    """괘선 묶음 하나에서 표를 만든다. 위아래로 붙은 표는 나눈다. 격자가 서지 않으면 빈 목록."""
    if len(hs) < 2:
        return []
    ys0 = cluster_values([s.pos for s in hs], Y_CLUSTER_GAP)
    xs0 = cluster_values([v for s in hs for v in (s.a0, s.a1)], X_CLUSTER_GAP)
    if len(ys0) >= 4 and len(xs0) >= 2:
        k = _split_level(ys0, xs0, chunks)
        if k is not None:
            cut = (ys0[k] + ys0[k + 1]) / 2
            out = []
            for part in (lambda p: p < cut, lambda p: p > cut):
                phs = [s for s in hs if part(s.pos)]
                pvs = [s for s in vs if part((s.a0 + s.a1) / 2)]
                out.extend(build_lattice(phs, pvs, chunks, layout))
            return out
    t = _build_one(hs, vs, chunks, layout)
    return [t] if t is not None else []


def _build_one(hs, vs, chunks, layout=1):
    if len(hs) < 2:
        return None
    xs = cluster_values([v for s in hs for v in (s.a0, s.a1)] + [s.pos for s in vs], X_CLUSTER_GAP)
    xs = [x for i, x in enumerate(xs) if i == 0 or x - xs[i - 1] >= 6]
    ys = cluster_values([s.pos for s in hs], Y_CLUSTER_GAP)
    ys = [y for i, y in enumerate(ys) if i == 0 or y - ys[i - 1] >= 3]
    if len(xs) < 3 or len(ys) < 2:
        return None
    cells = (len(xs) - 1) * (len(ys) - 1)
    if cells > MAX_TABLE_CELLS:
        raise _TooLarge(f"lines_table_skipped:too_many_cells:{cells}")
    hs, vs = _ByPos(hs), _ByPos(vs)
    notes = []
    x_lo, x_hi = xs[0], xs[-1]
    inside = [c for c in chunks if x_lo - 2 <= c.xc <= x_hi + 2]
    band_h = median(b - a for a, b in itertools.pairwise(ys))

    def cols_of(row_chunks):
        return {j for j in (_pick_col(c, xs) for c in row_chunks) if j is not None}

    # 머리글 행이 맨 위 괘선 위에 놓인 표(삼성전자 Facts & Figures): 위쪽 한 줄이 두 열 이상에 걸쳐 있으면 행으로 넣는다.
    reach = min(band_h, 30.0) * 1.3
    above = [c for c in inside if ys[0] - reach < c.yc < ys[0] and c.y1 <= ys[0] + 1.5]
    if above:
        last = max(_text_lines(above))
        row = [c for c in above if abs(c.yc - last) <= 0.5 * (c.y1 - c.y0)]
        ncols = len(cols_of(row))
        # 표 제목과 단위 표기만 있는 줄(두 조각)은 머리글 행이 아니다.
        if ncols >= 3 or (ncols >= 2 and any(c.value_like for c in row)):
            top = min(c.y0 for c in row) - 1.0
            ys.insert(0, top)
            notes.append("header_row_above_top_rule")
    # 마지막 행 아래에 괘선이 없는 표: 값이 있는 한 줄이 두 열 이상에 걸쳐 있으면 행으로 넣는다.
    below = [c for c in inside if ys[-1] < c.yc < ys[-1] + reach and c.y0 >= ys[-1] - 1.5]
    if below:
        first = min(_text_lines(below))
        row = [c for c in below if abs(c.yc - first) <= 0.5 * (c.y1 - c.y0)]
        if len(cols_of(row)) >= 2 and any(c.numeric for c in row):
            ys.append(max(c.y1 for c in row) + 1.0)
            notes.append("last_row_below_bottom_rule")
    virtual_top = "header_row_above_top_rule" in notes

    inside = [c for c in inside if ys[0] <= c.yc <= ys[-1]]
    if not inside:
        return None

    def band_of(c):
        for i in range(len(ys) - 1):
            if ys[i] <= c.yc <= ys[i + 1]:
                return i
        return None

    # 괘선 없이 값 행이 여러 줄 쌓인 구간: 두 열 이상에서 숫자가 두 줄 이상이면 글자 줄로 행을 나눈다.
    # 조각마다 띠와 열은 한 번만 센다(띠마다·열마다 다시 세면 띠² × 조각 꼴로 커진다. 밴드 PX2 ⑧).
    bands = {}
    for c in inside:
        bands.setdefault(band_of(c), []).append(c)
    extra = []
    for i in range(len(ys) - 1):
        if virtual_top and i == 0:
            continue
        band = bands.get(i, [])
        band_nums = [(c, _pick_col(c, xs)) for c in band if c.numeric]
        stacked = 0
        for j in range(len(xs) - 1):
            nums = [c for c, col in band_nums if col == j]
            if len(_text_lines(nums)) >= 2:
                stacked += 1
        if stacked >= 2:
            lines = _text_lines(band)
            extra.extend((a + b) / 2 for a, b in itertools.pairwise(lines))
    if extra:
        notes.append("rows_split_by_text_lines")
        ys = sorted(ys + extra)
    virtual = set(extra)

    nb, nc = len(ys) - 1, len(xs) - 1
    dsu = _DSU(nb * nc)

    def closed_below(i, j):
        y = ys[i + 1]
        if y in virtual or (virtual_top and i == 0):
            return True
        return _h_cover(hs, y, xs[j], xs[j + 1])

    by_band = {}
    for c in inside:
        b = band_of(c)
        if b is not None:
            by_band.setdefault(b, []).append(c)
    for i in range(nb):
        inner_v = any(_v_cover(vs, xs[k], ys[i], ys[i + 1]) for k in range(1, nc))
        weak = []  # 세로선은 없지만 가로선이 끊겨 있어 병합인지 불확실한 열 경계
        for j in range(nc):
            if i + 1 < nb and not closed_below(i, j):
                dsu.union(i * nc + j, (i + 1) * nc + j)
            if j + 1 < nc and inner_v and not _v_cover(vs, xs[j + 1], ys[i], ys[i + 1]):
                # 세로선이 표 안쪽에 그어진 띠에서 세로선이 없는 열 경계. 위나 아래 가로선이 그 경계를
                # 끊김 없이 지나가면 가로 병합이다 (병합 셀의 배경 사각형이 이 모양이다).
                if _h_continuous(hs, ys[i], xs[j + 1]) or _h_continuous(hs, ys[i + 1], xs[j + 1]):
                    dsu.union(i * nc + j, i * nc + j + 1)
                else:
                    weak.append(j)
        # 불확실한 경계는 글자로 판정한다: 이어진 열 구간에 글자가 한 줄에 한 조각뿐이고 그 조각이 경계를 넘으면 병합.
        k = 0
        while k < len(weak):
            run = [weak[k]]
            while k + 1 < len(weak) and weak[k + 1] == run[-1] + 1:
                k += 1
                run.append(weak[k])
            k += 1
            lo, hi = xs[run[0]], xs[run[-1] + 2]
            members = [c for c in by_band.get(i, []) if lo <= c.xc <= hi]
            one_per_line = len(_text_lines(members)) == len(members)
            crosses = any(c.x0 < xs[j + 1] - 2 and c.x1 > xs[j + 1] + 2 for c in members for j in run)
            if members and one_per_line and crosses:
                for j in run:
                    # 번역 판(2): 무리 통째가 아니라 조각이 실제로 넘는 경계만 잇는다. 무리 통째로 이으면 세로 병합된 대분류
                    # 열과 이어져 띠마다의 행 머리가 표 맨 윗칸 하나로 모인다(밴드 TRD1 ★①, 공개 보고서 표 둘).
                    if layout >= 2 and not any(c.x0 < xs[j + 1] - 2 and c.x1 > xs[j + 1] + 2 for c in members):
                        continue
                    dsu.union(i * nc + j, i * nc + j + 1)

    anchors = {}
    for k in range(nb * nc):
        root = dsu.find(k)
        i, j = divmod(k, nc)
        ai, aj = anchors.get(root, (i, j))
        anchors[root] = (min(ai, i), min(aj, j))

    cells = {}
    unplaced = 0
    for c in inside:
        i, j = band_of(c), _pick_col(c, xs)
        if i is None or j is None:
            unplaced += 1
            continue
        cells.setdefault(anchors[dsu.find(i * nc + j)], []).append(c)
    grid = [["" for _ in range(nc)] for _ in range(nb)]
    marks = []
    members = {}
    for (i, j), cs in cells.items():
        tol = 0.45 * median(c.y1 - c.y0 for c in cs)
        cs.sort(key=lambda c: c.yc)
        lines = []
        for c in cs:
            if lines and c.yc - lines[-1][-1].yc <= tol:
                lines[-1].append(c)
            else:
                lines.append([c])
        ordered = [c for line in lines for c in sorted(line, key=lambda c: c.x0)]
        grid[i][j] = " ".join(c.text for c in ordered if c.text)
        members[(i, j)] = ordered
        for c in ordered:
            marks.extend({"row": i, "col": j, "mark": m} for m in c.marks)
    rmap, cmap = pruned_index(grid)
    grid, marks = prune_empty(grid, marks)
    if len(grid) < 2 or len(grid[0]) < 2:
        return None
    filled = sum(1 for r in grid for c in r if c)
    if filled < 4:
        return None
    status = STATUS_OK
    if unplaced:
        notes.append(f"chunks_unplaced:{unplaced}")
        status = STATUS_LOW
    if "rows_split_by_text_lines" in notes:
        status = STATUS_LOW
    bbox = [xs[0], ys[0], xs[-1], ys[-1]]
    return Table(
        bbox=[round(v, 1) for v in bbox],
        grid=grid,
        method=METHOD_LINES,
        status=status,
        notes=notes,
        footnote_marks=marks,
        header=estimate_header(grid),
        cell_chunks={(rmap[i], cmap[j]): cs for (i, j), cs in members.items() if i in rmap and j in cmap},
    )


def find_lines_tables(hs, vs, chunks, notes=None, layout=1):
    """(표 목록, 격자를 세우지 못한 괘선 묶음의 bbox 목록).

    상한(`MAX_TABLE_RULES`·`MAX_TABLE_CELLS`)을 넘는 묶음은 그 묶음만 건너뛴다. 표도 실패 표시도 내지 않으므로 그 글자는
    부르는 쪽에서 글자 정렬 기반이나 글로 간다. 건너뛴 까닭은 `notes`(주면)에 덧붙인다. 같은 쪽의 다른 묶음은 그대로다.
    """
    tables, rejected = [], []
    for ghs, gvs in group_rules(hs, vs):
        if len(ghs) < 2:
            continue
        try:
            if len(ghs) + len(gvs) > MAX_TABLE_RULES:
                raise _TooLarge(f"lines_table_skipped:too_many_rules:{len(ghs) + len(gvs)}")
            built = build_lattice(ghs, gvs, chunks, layout) if layout >= 2 else build_lattice(ghs, gvs, chunks)
        except _TooLarge as skipped:
            if notes is not None:
                notes.append(str(skipped))
            continue
        tables.extend(built)
        if not built:
            x0 = min(s.a0 for s in ghs)
            x1 = max(s.a1 for s in ghs)
            y0 = min(s.pos for s in ghs)
            y1 = max(s.pos for s in ghs)
            if y1 - y0 >= 6 and x1 - x0 >= 20:
                rejected.append([x0, y0, x1, y1])
    return tables, rejected
