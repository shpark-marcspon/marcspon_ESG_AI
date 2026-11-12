"""도표를 찾고, 도표 속 숫자마다 「값인가 눈금인가, 어느 범주의, 어느 계열의 값인가」를 붙인다 (새 산출. 문서 모델은
고치지 않는다).

LLM·OCR 을 쓰지 않는다. PDF 의 글자 좌표와 벡터 그림 요소(막대 사각형, 꺾은선, 표식, 범례 표식)만 본다.
그림으로 박힌 도표는 대상이 아니다. 숫자를 읽어 값을 정하지 않는다: 여기서 붙이는 것은 글이고 값은 다른 코드가 읽는다.

라벨을 붙이는 방법 둘:
- (가) 좌표 `coord`: 값 글자의 가로(가로 막대는 세로) 가운데를 범주 축의 글자에 맞춘다. 계열은 알 수 없다.
- (나) 그림 요소 `elem`: 값 글자를 가까운 그림 요소(막대의 끝, 꺾은선의 점)에 걸고, 그 요소의 자리로 범주를, 색과 범례로
계열을 붙인다.
- 합친 것 `label`: 범주는 둘이 같거나 한쪽만 붙였을 때만 싣고 둘이 다르면 싣지 않는다. 계열은 (나)의 것.

틀린 라벨은 없는 라벨보다 나쁘다. 애매하면 붙이지 않고 까닭(`status`)을 남긴다.
"""

import math
import re

from .layout import is_numeric, page_chunks
from .places import link_page

# 꼴을 가르는 문턱 (pt). 근거: 본문 글자 8.5pt, 도표 속 글자 6~7pt, 표식의 지름 4~5pt 인 조판을 보고 정했다 (추정).
SWATCH_MAX = 8.5  # 범례 표식(작은 사각형·점)의 한 변
MARKER_MAX = 9.0  # 꺾은선 표식의 지름
DATA_LINE_MIN_WIDTH = 0.9  # 이보다 굵은 선은 값의 선, 가는 선은 눈금선·이음선
LEADER_MAX = 45.0  # 값 글자와 그림 요소를 잇는 가는 이음선의 길이
EDGE = 0.8  # 「같은 밑선」으로 보는 허용폭
VALUE_MARK_MAX = 30.0  # 값 글자와 그림 요소 사이의 거리가 이보다 멀면 걸지 않는다
SAME_PLACE = 1.5  # 두 요소까지의 거리 차가 이보다 작으면 어느 쪽인지 가를 수 없다
NEAR_RATIO = 0.6  # 가장 가까운 범주까지의 거리가 다음 범주까지의 거리의 이 비율보다 크면 애매하다
FRAME_MIN = (100.0, 50.0)
TITLE_MAX = 40  # 이보다 긴 글 줄은 본문이지 도표의 제목이 아니다 (글자 수)

WHITE = "#ffffff"


def _hex(c):
    return None if c is None else "#{:02x}{:02x}{:02x}".format(*(round(v * 255) for v in c))


def _dist_box_point(b, x, y):
    dx = max(b[0] - x, 0.0, x - b[2])
    dy = max(b[1] - y, 0.0, y - b[3])
    return math.hypot(dx, dy)


def _dist_box_box(a, b):
    dx = max(a[0] - b[2], 0.0, b[0] - a[2])
    dy = max(a[1] - b[3], 0.0, b[1] - a[3])
    return math.hypot(dx, dy)


def _union(boxes):
    boxes = list(boxes)
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _overlap_1d(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0)


def page_elements(page):
    """쪽의 벡터 그림 요소를 갈래로 나눈다. 좌표는 pt.

    bars: 색을 채운 사각형 / markers: 작은 원 / lines: 굵은 선(값의 선)의 꼭짓점 / thin: 가는 선분(눈금선, 이음선) /
    frames: 테두리 사각형
    """
    bars, markers, lines, thin, frames = [], [], [], [], []
    for d in page.get_drawings():
        fill, stroke = _hex(d.get("fill")), _hex(d.get("color"))
        width = d.get("width") or 0.0
        items = d["items"]
        r = d["rect"]
        kinds = {it[0] for it in items}
        if kinds == {"c"} or (
            kinds <= {"c", "l"} and "c" in kinds and r.width <= MARKER_MAX and r.height <= MARKER_MAX
        ):
            if r.width <= MARKER_MAX and r.height <= MARKER_MAX:
                color = fill if fill and fill != WHITE else stroke
                if color:
                    markers.append(
                        {
                            "x": (r.x0 + r.x1) / 2,
                            "y": (r.y0 + r.y1) / 2,
                            "color": color,
                            "box": [r.x0, r.y0, r.x1, r.y1],
                        }
                    )
            continue
        if kinds <= {"re", "qu"}:
            for it in items:
                q = it[1]
                box = [min(q.x0, q.x1), min(q.y0, q.y1), max(q.x0, q.x1), max(q.y0, q.y1)]
                w, h = box[2] - box[0], box[3] - box[1]
                if fill and fill != WHITE and min(w, h) >= 1.0:
                    bars.append({"box": box, "color": fill})
                elif stroke and not fill and w >= FRAME_MIN[0] and h >= FRAME_MIN[1]:
                    frames.append(box)
            continue
        if kinds == {"l"} and stroke:
            pts = []
            for it in items:
                for p in (it[1], it[2]):
                    if not pts or abs(pts[-1][0] - p.x) > 0.05 or abs(pts[-1][1] - p.y) > 0.05:
                        pts.append((p.x, p.y))
            if width >= DATA_LINE_MIN_WIDTH:
                lines.append({"points": pts, "color": stroke, "box": [r.x0, r.y0, r.x1, r.y1]})
            elif len(pts) == 2:
                thin.append({"a": pts[0], "b": pts[1], "color": stroke})
    return {"bars": bars, "markers": markers, "lines": lines, "thin": thin, "frames": frames}


def _frame_of(box, frames):
    """상자를 품는 가장 작은 테두리. 없으면 None."""
    inside = [
        f for f in frames if f[0] - 1 <= box[0] and f[1] - 1 <= box[1] and f[2] + 1 >= box[2] and f[3] + 1 >= box[3]
    ]
    return min(inside, key=lambda f: (f[2] - f[0]) * (f[3] - f[1])) if inside else None


def find_legends(elements, chunks):
    """범례: 작은 색 사각형·점이나 짧은 굵은 선 바로 오른쪽에 붙은 글. [{"color", "name", "box"}]"""
    swatches = []
    for b in elements["bars"]:
        w, h = b["box"][2] - b["box"][0], b["box"][3] - b["box"][1]
        if w <= SWATCH_MAX and h <= SWATCH_MAX:
            swatches.append((b["box"], b["color"]))
    for ln in elements["lines"]:
        box = ln["box"]
        if box[3] - box[1] <= 1.0 and 6.0 <= box[2] - box[0] <= 32.0:
            swatches.append((box, ln["color"]))
    for m in elements["markers"]:
        swatches.append((m["box"], m["color"]))
    out = []
    for box, color in swatches:
        yc = (box[1] + box[3]) / 2
        right = [
            c for c in chunks if c.y0 - 1 <= yc <= c.y1 + 1 and 0 <= c.x0 - box[2] <= 7.0 and not is_numeric(c.text)
        ]
        if not right:
            continue
        c = min(right, key=lambda c: c.x0)
        if any(o["name"] == c.text and o["color"] == color and _dist_box_box(o["box"], box) < 40 for o in out):
            continue
        out.append({"color": color, "name": c.text, "box": [box[0], box[1], c.x1, max(box[3], c.y1)], "swatch": box})
    return out


def _bar_groups(bars, legends):
    """막대의 묶음. 세로 막대는 밑선이 같고 높이가 서로 다르다. 가로 막대는 왼쪽 선이 같고 길이가 서로 다르다."""
    swatch_boxes = [tuple(lg["swatch"]) for lg in legends]
    real = [b for b in bars if tuple(b["box"]) not in swatch_boxes]
    groups, used = [], set()
    for axis in ("v", "h"):
        key = (lambda b: b["box"][3]) if axis == "v" else (lambda b: b["box"][0])
        rest = sorted((b for b in real if id(b) not in used), key=key)
        run = []
        for b in [*rest, None]:
            if b is not None and run and key(b) - key(run[-1]) <= EDGE:
                run.append(b)
                continue
            if len(run) >= 2:
                size = [(x["box"][3] - x["box"][1]) if axis == "v" else (x["box"][2] - x["box"][0]) for x in run]
                thick = [(x["box"][2] - x["box"][0]) if axis == "v" else (x["box"][3] - x["box"][1]) for x in run]
                if max(size) - min(size) > 0.5 and max(thick) <= 1.6 * min(thick):
                    groups.append({"axis": axis, "bars": list(run)})
                    used.update(id(x) for x in run)
            run = [b] if b is not None else []
    # 쌓은 막대: 묶음의 막대 바로 위에 같은 너비로 얹힌 사각형
    for g in groups:
        if g["axis"] != "v":
            continue
        grew = True
        while grew:
            grew = False
            for b in real:
                if id(b) in used:
                    continue
                if any(
                    abs(b["box"][0] - m["box"][0]) <= EDGE
                    and abs(b["box"][2] - m["box"][2]) <= EDGE
                    and abs(b["box"][3] - m["box"][1]) <= EDGE
                    for m in g["bars"]
                ):
                    g["bars"].append(b)
                    used.add(id(b))
                    grew = True
    return groups


def _split_by_frame(group, frames):
    """밑선이 같은 막대가 옆 도표의 것과 섞이지 않게: 품는 테두리가 다르면 가른다."""
    by_frame = {}
    for b in group["bars"]:
        f = _frame_of(b["box"], frames)
        by_frame.setdefault(tuple(f) if f else None, []).append(b)
    return [{"axis": group["axis"], "bars": bars} for bars in by_frame.values() if len(bars) >= 2]


def _axis_lines(elements):
    """가로로 긴 가는 선(축선, 눈금선)."""
    return [t for t in elements["thin"] if abs(t["a"][1] - t["b"][1]) <= 0.6 and abs(t["a"][0] - t["b"][0]) >= 60]


def drop_text_boxes(elements, chunks):
    """글(숫자가 아닌 글자)이 든 색 사각형은 표의 칸 배경이나 도식의 상자다. 막대에서 뺀다. 가로·세로로 곧은 굵은
    선(표의 괘선)도 값의 선에서 뺀다."""
    texts = [c for c in chunks if not _numeric(c.text) and any(ch.isalpha() for ch in c.text)]

    def holds(b, cs):
        return sum(1 for c in cs if b["box"][0] <= c.xc <= b["box"][2] and b["box"][1] <= c.yc <= b["box"][3])

    # 숫자가 둘 이상 든 사각형도 막대가 아니다 (표의 줄 배경). 막대 안에 적힌 값은 많아야 하나다.
    bars = [b for b in elements["bars"] if holds(b, texts) == 0 and holds(b, chunks) <= 1]
    lines = [
        ln
        for ln in elements["lines"]
        if len(ln["points"]) >= 3 or (ln["box"][3] - ln["box"][1] > 0.3 and ln["box"][2] - ln["box"][0] > 0.3)
    ]
    return {**elements, "bars": bars, "lines": lines}


def _on_rule(y, x0, x1, rules):
    """높이 y 에, 가로 구간 [x0, x1] 의 대부분(90%)을 덮는 가는 가로선이 있는가."""
    for t in rules:
        if abs(t["a"][1] - y) <= EDGE:
            r0, r1 = sorted((t["a"][0], t["b"][0]))
            if min(r1, x1) - max(r0, x0) >= 0.9 * (x1 - x0):
                return True
    return False


def drop_grid_cells(elements):
    """괘선 표의 칸 배경은 막대가 아니다: 위 변과 아래 변이 둘 다 가는 가로 괘선에 맞닿은 색 사각형을 막대에서 뺀다.

    막대는 밑변만 축선에 닿고 끝 변은 값의 높이에 있어 괘선과 맞닿지 않는다 (가로 막대는 위·아래 변이 둘 다 닿지
    않는다).
    """
    rules = [t for t in elements["thin"] if abs(t["a"][1] - t["b"][1]) <= 0.6]
    bars = [
        b
        for b in elements["bars"]
        if not (
            _on_rule(b["box"][1], b["box"][0], b["box"][2], rules)
            and _on_rule(b["box"][3], b["box"][0], b["box"][2], rules)
        )
    ]
    return {**elements, "bars": bars}


def find_plots(elements, legends):
    """그림 요소의 덩어리마다 도표 하나. [{"box", "axis", "bars", "lines", "markers"}]"""
    frames = elements["frames"]
    legend_boxes = [lg["swatch"] for lg in legends]
    plots = []
    for g in _bar_groups(elements["bars"], legends):
        for part in _split_by_frame(g, frames):
            plots.append(
                {"axis": part["axis"], "bars": part["bars"], "lines": [], "box": _union(b["box"] for b in part["bars"])}
            )
    # 밑선이 같은 세로 막대가 한 테두리 안에 두 도표로 나뉘어 있으면 축선(막대 밑의 가는 가로선)으로 가른다.
    axis_lines = _axis_lines(elements)
    split = []
    for p in plots:
        if p["axis"] != "v":
            split.append(p)
            continue
        base = max(b["box"][3] for b in p["bars"])
        under = sorted((t for t in axis_lines if abs(t["a"][1] - base) <= 2.0), key=lambda t: min(t["a"][0], t["b"][0]))
        spans = [(min(t["a"][0], t["b"][0]), max(t["a"][0], t["b"][0])) for t in under]
        parts = {}
        for b in p["bars"]:
            xc = (b["box"][0] + b["box"][2]) / 2
            hit = next((i for i, (x0, x1) in enumerate(spans) if x0 - 1 <= xc <= x1 + 1), None)
            parts.setdefault(hit, []).append(b)
        if len(parts) <= 1 or None in parts:
            split.append(p)
        else:
            split.extend(
                {"axis": "v", "bars": bars, "lines": [], "box": _union(b["box"] for b in bars)}
                for bars in parts.values()
            )
    plots = split
    for ln in elements["lines"]:
        if ln["box"] in legend_boxes or ln["box"][2] - ln["box"][0] < 20.0:
            continue
        home = None
        for p in plots:
            b = p["box"]
            if _frame_of(b, frames) != _frame_of(ln["box"], frames):
                continue
            ox = _overlap_1d(b[0], b[2], ln["box"][0], ln["box"][2])
            oy = _overlap_1d(b[1] - 30, b[3] + 5, ln["box"][1], ln["box"][3])
            if ox >= 0.5 * min(b[2] - b[0], ln["box"][2] - ln["box"][0]) and oy >= -1:
                home = p
                break
        if home is None:
            home = {"axis": "v", "bars": [], "lines": [], "box": list(ln["box"])}
            plots.append(home)
        home["lines"].append(ln)
        home["box"] = _union([home["box"], ln["box"]])
    for p in plots:
        b = p["box"]
        p["markers"] = (
            [
                m
                for m in elements["markers"]
                if b[0] - 4 <= m["x"] <= b[2] + 4 and b[1] - 4 <= m["y"] <= b[3] + 4 and m["box"] not in legend_boxes
            ]
            if p["lines"]
            else []
        )
    # 산점도: 선에 얹히지 않은 표식이 여럿 모여 있고 가로·세로 눈금이 둘 다 있는 것은 쪽 단위에서 따로 본다
    # (find_charts).
    return plots


def _numeric(text):
    return is_numeric(text) or bool(re.fullmatch(r"[-–—−]", text))


def _tick_run(words, plot, side, reach=(45.0, 22.0)):
    """값 축의 눈금: 도표 왼쪽(side='left')에 세로로, 또는 아래(side='below')에 가로로 줄지은 숫자 낱말 (둘 이상). reach
    는 (왼쪽, 아래)로 찾는 거리."""
    b = plot["box"]
    if side == "left":
        cand = [
            w
            for w in words
            if is_numeric(w["text"])
            and w["bbox"][2] <= b[0] - 0.5
            and b[0] - w["bbox"][2] <= reach[0]
            and b[1] - 30 <= (w["bbox"][1] + w["bbox"][3]) / 2 <= b[3] + 8 + (reach[1] - 22.0)
        ]
        if len(cand) < 2:
            return []
        edge = sorted(w["bbox"][2] for w in cand)[len(cand) // 2]
        run = [w for w in cand if abs(w["bbox"][2] - edge) <= 4.0]
    else:
        cand = [
            w
            for w in words
            if is_numeric(w["text"])
            and 0 <= w["bbox"][1] - b[3] <= reach[1]
            and b[0] - 25 - (reach[0] - 45.0) <= (w["bbox"][0] + w["bbox"][2]) / 2 <= b[2] + 45
        ]
        if len(cand) < 2:
            return []
        line = sorted(w["bbox"][1] for w in cand)[len(cand) // 2]
        run = [w for w in cand if abs(w["bbox"][1] - line) <= 2.0]
    return run if len(run) >= 2 else []


def _category_labels(words, plot):
    """범주 축의 글자. 세로 도표는 밑선 바로 아래의 한 줄, 가로 막대는 막대 왼쪽의 같은 줄 글자. [{"text", "pos"}] (pos
    는 가로 또는 세로 가운데)"""
    b = plot["box"]
    if plot["axis"] == "h":
        # 가로 막대: 막대의 왼쪽 선 바로 왼쪽에 세로로 줄지은 글자 (막대가 너무 짧아 그려지지 않은 범주도 글자는 있다)
        left = [
            w
            for w in words
            if w["bbox"][2] <= b[0] + 0.5
            and b[0] - w["bbox"][2] <= 40
            and not _numeric(w["text"])
            and b[1] - 6 <= (w["bbox"][1] + w["bbox"][3]) / 2
        ]
        if not left:
            return []
        heights = sorted(w["bbox"][3] - w["bbox"][1] for w in left)
        pitch = 2.5 * heights[len(heights) // 2]
        out, last = [], b[3]
        for w in sorted(left, key=lambda w: w["bbox"][1]):
            yc = (w["bbox"][1] + w["bbox"][3]) / 2
            if yc - last > pitch:
                break
            out.append({"text": w["text"], "pos": yc})
            last = max(last, yc)
        return out
    below = [
        w
        for w in words
        if 0.5 <= (w["bbox"][1] + w["bbox"][3]) / 2 - b[3] <= 20
        and b[0] - 25 <= (w["bbox"][0] + w["bbox"][2]) / 2 <= b[2] + 25
        and w["text"] not in "-–—−"
    ]
    if not below:
        return []
    top = min(w["bbox"][1] for w in below)
    line = sorted((w for w in below if w["bbox"][1] - top <= 2.5), key=lambda w: w["bbox"][0])
    merged = []
    for w in line:
        if merged and w["bbox"][0] - merged[-1]["x1"] <= 0.8:
            merged[-1]["text"] += " " + w["text"]
            merged[-1]["x1"] = w["bbox"][2]
        else:
            merged.append({"text": w["text"], "x0": w["bbox"][0], "x1": w["bbox"][2], "words": []})
        merged[-1]["words"].append(w)
    return [{"text": m["text"], "pos": (m["x0"] + m["x1"]) / 2, "words": m["words"]} for m in merged]


def _nearest_category(pos, cats):
    """(범주, 상태). 가장 가까운 범주가 다음 범주보다 뚜렷이 가까울 때만 붙인다."""
    if not cats:
        return None, "no_category_axis"
    ranked = sorted(cats, key=lambda c: abs(c["pos"] - pos))
    d1 = abs(ranked[0]["pos"] - pos)
    if len(ranked) > 1:
        d2 = abs(ranked[1]["pos"] - pos)
        if d1 > NEAR_RATIO * d2:
            return None, "between_categories"
        spacing = min(
            abs(a["pos"] - b["pos"])
            for a, b in zip(
                sorted(cats, key=lambda c: c["pos"]), sorted(cats, key=lambda c: c["pos"])[1:], strict=False
            )
        )
        if d1 > spacing:
            return None, "outside_axis"
    return ranked[0]["text"], "ok"


def _marks(plot):
    """값이 걸릴 수 있는 그림 요소: 막대(끝 변), 꺾은선의 꼭짓점과 표식(점). [{"kind", "color", "x", "y", "box"}]"""
    marks = []
    for bar in plot["bars"]:
        x0, y0, x1, y1 = bar["box"]
        marks.append(
            {
                "kind": "bar",
                "color": bar["color"],
                "box": bar["box"],
                "x": (x0 + x1) / 2,
                "y": (y0 + y1) / 2,
                "edge": [x0, y0, x1, y0] if plot["axis"] == "v" else [x1, y0, x1, y1],
            }
        )
    points = []
    for m in plot["markers"]:
        points.append({"kind": "point", "color": m["color"], "x": m["x"], "y": m["y"]})
    for ln in plot["lines"]:
        for x, y in ln["points"]:
            if not any(abs(p["x"] - x) <= 2.5 and abs(p["y"] - y) <= 2.5 and p["color"] == ln["color"] for p in points):
                points.append({"kind": "point", "color": ln["color"], "x": x, "y": y})
    return marks + points


def _mark_distance(box, mark):
    if mark["kind"] == "bar":
        xc, yc = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        b = mark["box"]
        if b[0] <= xc <= b[2] and b[1] <= yc <= b[3]:
            return 0.0
        # 글자의 가운데에서 막대의 끝 변까지. 글자 상자로 재면 붙어 있는 옆 막대와 거리가 같아져 가를 수 없다.
        e = mark["edge"]
        if e[1] == e[3]:
            return math.hypot(max(e[0] - xc, 0.0, xc - e[2]), max(e[1] - box[3], 0.0, box[1] - e[1]))
        return math.hypot(max(e[0] - box[2], 0.0, box[0] - e[0]), max(e[1] - yc, 0.0, yc - e[3]))
    return _dist_box_point(box, mark["x"], mark["y"])


def _leader_target(box, thin):
    """값 글자에 닿은 가는 이음선이 있으면 그 반대쪽 끝점."""
    for t in thin:
        length = math.hypot(t["a"][0] - t["b"][0], t["a"][1] - t["b"][1])
        if not 3.0 <= length <= LEADER_MAX:
            continue
        for near, far in ((t["a"], t["b"]), (t["b"], t["a"])):
            if _dist_box_point(box, near[0], near[1]) <= 3.0 and _dist_box_point(box, far[0], far[1]) > 3.0:
                return far
    return None


def _title(chunks, box, exclude):
    """도표의 제목: 도표 위쪽 가장 가까운 글 줄 (숫자·단위 줄·범례가 아닌 것). 그 바로 위에 왼쪽이 맞는 글 줄이 하나 더
    있으면 앞에 붙인다."""
    above = [
        c
        for c in chunks
        if not is_numeric(c.text)
        and len(c.text) <= TITLE_MAX
        and c.text[0] not in "(■●▪"
        and c.y1 <= box[1] + 2
        and box[1] - c.y1 <= 45
        and _overlap_1d(c.x0, c.x1, box[0] - 30, box[2] + 10) > 0
        and c.text not in exclude
        and any(ch.isalpha() for ch in c.text)
    ]
    if not above:
        return None
    first = max(above, key=lambda c: (c.y1, -c.x0))
    same_line = sorted((c for c in above if abs(c.y0 - first.y0) <= 2 and c.x0 < first.x0), key=lambda c: c.x0)
    if same_line and box[0] - 30 <= same_line[0].x0:
        first = same_line[0]
    upper = [
        c
        for c in chunks
        if not is_numeric(c.text)
        and len(c.text) <= TITLE_MAX
        and c.text[0] not in "(■●▪"
        and c.y1 <= first.y0 + 1
        and first.y0 - c.y1 <= 28
        and abs(c.x0 - first.x0) <= 30
        and c.text not in exclude
        and c is not first
        and any(ch.isalpha() for ch in c.text)
    ]
    if upper:
        return max(upper, key=lambda c: c.y1).text + " / " + first.text
    return first.text


def label_page(page, places, grid_rule=True):
    """쪽 하나의 (도표 목록, 라벨이 붙은 숫자 낱말 목록). grid_rule 을 끄면 괘선 표의 칸 배경을 빼지 않는다 (고치기 전의
    성적을 다시 낼 때만)."""
    chunks, _ = page_chunks(page)
    elements = page_elements(page)
    legends = find_legends(elements, chunks)
    elements = drop_text_boxes(elements, chunks)
    if grid_rule:
        elements = drop_grid_cells(elements)
    plots = find_plots(elements, legends)
    words = [p for p in places if p["text"].strip()]
    # 표의 상자가 겹치면 같은 낱말이 두 그릇에 실려 있다. 한 번만 보고, 붙인 라벨은 끝에서 다른 그릇의 같은 낱말에도
    # 준다.
    twins = {}
    for w in words:
        twins.setdefault((w["text"], tuple(w["bbox"])), []).append(w)
    words = [group[0] for group in twins.values()]
    # 범주 축의 글자는 PDF 의 낱말에서 바로 읽는다 (문서 모델이 표로 세우지 못한 자리의 글자는 그릇에 이어지지 않는다).
    pdf_words = [{"text": w[4], "bbox": [w[0], w[1], w[2], w[3]]} for w in page.get_words() if w[4].strip()]
    charts, labelled = [], []
    legend_names = {lg["name"] for lg in legends}
    for plot in sorted(plots, key=lambda p: (round(p["box"][1] / 30), p["box"][0])):
        b = plot["box"]
        cats = _category_labels(pdf_words, plot)
        ticks = _tick_run(words, plot, "below" if plot["axis"] == "h" else "left")
        cat_boxes = [w["bbox"] for c in cats for w in c.get("words", [])]
        in_cat = [
            w
            for w in words
            if any(
                cb[0] - 0.5 <= (w["bbox"][0] + w["bbox"][2]) / 2 <= cb[2] + 0.5
                and cb[1] - 0.5 <= (w["bbox"][1] + w["bbox"][3]) / 2 <= cb[3] + 0.5
                for cb in cat_boxes
            )
        ]
        cat_words = {id(w) for w in in_cat}
        tick_ids = {id(w) for w in ticks}
        low = max([b[3]] + [c["pos"] for c in cats]) if plot["axis"] == "h" else b[3]
        zone = (
            [b[0] - 25, b[1] - 32, b[2] + 45, b[3] + 1.5]
            if plot["axis"] == "v"
            else [b[0] - 2, b[1] - 6, b[2] + 45, low + 6]
        )
        values = [
            w
            for w in words
            if is_numeric(w["text"])
            and id(w) not in cat_words
            and id(w) not in tick_ids
            and zone[0] <= (w["bbox"][0] + w["bbox"][2]) / 2 <= zone[2]
            and zone[1] <= (w["bbox"][1] + w["bbox"][3]) / 2 <= zone[3]
        ]
        numeric_cats = [w for w in in_cat if is_numeric(w["text"])]
        if len(values) + len(ticks) + len(numeric_cats) < 2 or len(cats) < 2:
            continue  # 숫자가 거의 없거나 범주 축의 글자가 없으면 도표로 보지 않는다
        frame = _frame_of(b, elements["frames"])
        scope = frame if frame else [b[0] - 40, b[1] - 60, b[2] + 160, b[3] + 45]
        mine = [
            lg for lg in legends if scope[0] <= lg["swatch"][0] <= scope[2] and scope[1] <= lg["swatch"][1] <= scope[3]
        ]
        by_color = {}
        for lg in mine:
            by_color.setdefault(lg["color"], set()).add(lg["name"])
        marks = _marks(plot)
        # (나) 값 글자 → 그림 요소: 가까운 것부터 하나씩 짝짓는다. 이음선이 있으면 그 끝점에서 잰다.
        pairs = []
        for vi, w in enumerate(values):
            target = _leader_target(w["bbox"], elements["thin"])
            for mi, m in enumerate(marks):
                if target is not None:
                    d = _dist_box_point(
                        m["edge"] if m["kind"] == "bar" else [m["x"], m["y"], m["x"], m["y"]], target[0], target[1]
                    )
                else:
                    d = _mark_distance(w["bbox"], m)
                if d <= VALUE_MARK_MAX:
                    pairs.append((d, vi, mi))
        pairs.sort()
        taken_v, taken_m, hit = set(), set(), {}
        for d, vi, mi in pairs:
            if vi in taken_v or mi in taken_m:
                continue
            taken_v.add(vi)
            taken_m.add(mi)
            hit[vi] = (mi, d)
        chart_id = f"p{page.number + 1}-c{len(charts) + 1}"
        title = _title(chunks, _union([b] + [w["bbox"] for w in values] if values else [b]), legend_names)
        multi = len(by_color) >= 2
        for vi, w in enumerate(values):
            pos = (w["bbox"][1] + w["bbox"][3]) / 2 if plot["axis"] == "h" else (w["bbox"][0] + w["bbox"][2]) / 2
            c_cat, c_status = _nearest_category(pos, cats)
            e_cat, e_status, series, s_status = None, "no_mark", None, "no_mark"
            if vi in hit:
                mi, d = hit[vi]
                m = marks[mi]
                e_cat, e_status = _nearest_category(m["y"] if plot["axis"] == "h" else m["x"], cats)
                rivals = {marks[mj]["color"] for dd, vj, mj in pairs if vj == vi and mj != mi and dd - d < SAME_PLACE}
                names = by_color.get(m["color"], set())
                if rivals - {m["color"]}:
                    series, s_status = None, "marks_overlap"
                elif len(names) == 1:
                    series, s_status = next(iter(names)), "ok"
                elif len(names) > 1:
                    series, s_status = None, "legend_color_shared"
                else:
                    series, s_status = None, "no_legend_for_color"
            if c_cat is not None and e_cat is not None and c_cat != e_cat:
                cat, status = None, "methods_disagree"
            else:
                cat = e_cat if e_cat is not None else c_cat
                status = "ok" if cat is not None else (e_status if e_status != "no_mark" else c_status)
            labelled.append(
                {
                    **{k: w[k] for k in ("container", "start", "end", "text", "bbox")},
                    "chart": chart_id,
                    "role": "value",
                    "coord": {"category": c_cat, "status": c_status},
                    "elem": {"category": e_cat, "status": e_status, "series": series, "series_status": s_status},
                    "label": {
                        "title": title,
                        "category": cat,
                        "status": status,
                        "series": series,
                        "series_status": s_status,
                    },
                }
            )
        for w in ticks:
            labelled.append(
                {**{k: w[k] for k in ("container", "start", "end", "text", "bbox")}, "chart": chart_id, "role": "tick"}
            )
        for w in numeric_cats:
            labelled.append(
                {
                    **{k: w[k] for k in ("container", "start", "end", "text", "bbox")},
                    "chart": chart_id,
                    "role": "category",
                }
            )
        box = _union([b] + [w["bbox"] for w in values + ticks] + cat_boxes)
        charts.append(
            {
                "id": chart_id,
                "page": page.number + 1,
                "bbox": [round(v, 1) for v in box],
                "plot": [round(v, 1) for v in b],
                "form": ("bar" if plot["bars"] else "")
                + ("+line" if plot["bars"] and plot["lines"] else "line" if plot["lines"] else ""),
                "orientation": "horizontal" if plot["axis"] == "h" else "vertical",
                "title": title,
                "multi_series": multi,
                "legend": sorted({(lg["name"], lg["color"]) for lg in mine}),
                "categories": [c["text"] for c in cats],
            }
        )
    charts.extend(_scatter_charts(page, elements, legends, words, charts, labelled))
    # 옆 도표와 구역이 겹쳐 한 낱말이 두 도표에 든 것은 그림 영역이 더 가까운 도표의 것만 남긴다.
    plot_of = {c["id"]: c["plot"] for c in charts}
    best = {}
    for item in labelled:
        key = (item["text"], tuple(item["bbox"]))
        d = _dist_box_box(item["bbox"], plot_of[item["chart"]])
        if key not in best or d < best[key][0]:
            best[key] = (d, item["chart"])
    labelled[:] = [item for item in labelled if best[(item["text"], tuple(item["bbox"]))][1] == item["chart"]]
    for item in list(labelled):
        for twin in twins[(item["text"], tuple(item["bbox"]))][1:]:
            labelled.append({**item, "container": twin["container"], "start": twin["start"], "end": twin["end"]})
    return charts, labelled


def _scatter_charts(page, elements, legends, words, charts, labelled):
    """산점도: 표식(점)이 여럿 모여 있고 왼쪽에 세로 눈금, 아래에 가로 눈금이 둘 다 있는 것. 값 글자가 없으니 눈금만
    가른다."""
    legend_boxes = [lg["swatch"] for lg in legends]
    free = [
        m
        for m in elements["markers"]
        if m["box"] not in legend_boxes
        and not any(c["bbox"][0] <= m["x"] <= c["bbox"][2] and c["bbox"][1] <= m["y"] <= c["bbox"][3] for c in charts)
    ]
    by_frame = {}
    for m in free:
        f = _frame_of(m["box"], elements["frames"])
        by_frame.setdefault(tuple(f) if f else None, []).append(m)
    out = []
    for group in by_frame.values():
        if len(group) < 6:
            continue
        plot = {"axis": "v", "box": _union(m["box"] for m in group)}
        left, below = _tick_run(words, plot, "left", (400.0, 120.0)), _tick_run(words, plot, "below", (400.0, 120.0))
        if len(left) < 3 or len(below) < 3:
            continue
        chart_id = f"p{page.number + 1}-c{len(charts) + len(out) + 1}"
        for w in left + below:
            labelled.append(
                {**{k: w[k] for k in ("container", "start", "end", "text", "bbox")}, "chart": chart_id, "role": "tick"}
            )
        out.append(
            {
                "id": chart_id,
                "page": page.number + 1,
                "bbox": [round(v, 1) for v in _union([plot["box"]] + [w["bbox"] for w in left + below])],
                "plot": [round(v, 1) for v in plot["box"]],
                "form": "scatter",
                "orientation": "vertical",
                "title": None,
                "multi_series": False,
                "legend": [],
                "categories": [],
            }
        )
    return out


def label_document(pdf_doc, model, grid_rule=True):
    """문서 하나의 도표 라벨 산출 (dict). `schemas/chart-labels.schema.json`."""
    charts, words, unlinked, place_count = [], [], [], 0
    all_places = []
    for meta in model["pages"]:
        page = pdf_doc[meta["page"] - 1]
        places, missing = link_page(page, meta["page"], model["blocks"], model["tables"])
        unlinked.extend(missing)
        place_count += len(places)
        page_charts, page_words = label_page(page, places, grid_rule)
        charts.extend(page_charts)
        words.extend(page_words)
        all_places.extend(places)
    return {
        "schema_version": "0.1",
        "source": model["source"],
        "llm_used": False,
        "ocr_used": False,
        "charts": charts,
        "words": words,
        "unlinked": unlinked,
        "place_count": place_count,
    }, all_places
