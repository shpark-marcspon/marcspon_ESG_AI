"""글자 자리: 문서 모델의 글(블록의 글, 표 칸의 글)의 글자마다 PDF 좌표를 낸다 (곁 파일 `char-places.json`).

문서 모델(`document.json`)은 고치지 않는다. 분해가 글을 세울 때 쓰고 버리던 글자별 상자를 버리지 않고,
그릇(블록 ID 또는 `표ID:r행c열`)마다 「글의 몇 번째 글자부터가 한 줄 토막이고 그 글자마다 가로 범위가 어디인가」로
남긴다.
형식은 `schemas/char-places.schema.json`.

여기에는 숫자를 알아보는 규칙이 없다. 어디가 숫자인지는 읽는 쪽(`ts/reconcile` 의 숫자 뽑기)이 글자 범위로 알려 주고,
상자는 그 범위의 글자 상자를 줄마다 묶어 얻는다 (`span_boxes`). 글자 범위의 단위는 UTF-16 자리다 (JavaScript 문자열의
자리와 같다).

글과 글자 상자를 맞추지 못한 그릇은 지어내지 않고 `unlinked` 에 까닭과 함께 남긴다.
"""

SCHEMA_VERSION = "0.1"


def _u16(ch):
    return 2 if ord(ch) > 0xFFFF else 1


def _r(v):
    return round(v, 1)


def container_runs(text, chunks):
    """그릇의 글과 그 글을 이룬 조각(차례대로)에서 줄 토막 목록을 만든다. (토막 목록, None) 또는 (None, 까닭).

    토막 = 한 조각 안에서 세로 범위가 같은 글자가 이어진 것. 조각 사이의 빈칸은 어느 토막에도 들지 않는다.
    조각 안의 빈칸(공백 뭉치를 줄인 것)은 앞뒤 글자 사이의 틈을 제 범위로 갖는다.
    """
    kept = [c for c in chunks if c.text]
    if " ".join(c.text for c in kept) != text:
        return None, "text_differs_from_chunks"
    if any(c.glyphs is None or len(c.glyphs) != len(c.text) for c in kept):
        return None, "glyphs_not_aligned"
    runs, at = [], 0
    for c in kept:
        run = None
        for k, (ch, box) in enumerate(zip(c.text, c.glyphs, strict=False)):
            if box is None:
                before = next((b for b in reversed(c.glyphs[:k]) if b is not None), None)
                after = next((b for b in c.glyphs[k + 1 :] if b is not None), None)
                if before is None or after is None:
                    return None, "glyphs_not_aligned"
                box = (before[2], before[1], max(before[2], after[0]), before[3])
            y0, y1 = _r(box[1]), _r(box[3])
            if run is None or (run["y0"], run["y1"]) != (y0, y1):
                run = {"start": at, "y0": y0, "y1": y1, "x0": [], "x1": []}
                runs.append(run)
            for _ in range(_u16(ch)):
                run["x0"].append(_r(box[0]))
                run["x1"].append(_r(box[2]))
            at += _u16(ch)
        at += 1  # 조각 사이의 빈칸
    return runs, None


def _bbox(runs):
    return [
        min(min(r["x0"]) for r in runs),
        min(r["y0"] for r in runs),
        max(max(r["x1"]) for r in runs),
        max(r["y1"] for r in runs),
    ]


def build_container(cid, kind, page, text, chunks):
    """(그릇 dict, None) 또는 (None, 잇지 못한 까닭 dict)."""
    runs, reason = container_runs(text, chunks)
    if runs is None or not runs:
        return None, {"id": cid, "page": page, "reason": reason or "empty"}
    return {"id": cid, "kind": kind, "page": page, "bbox": _bbox(runs), "runs": runs}, None


def same_line(a, b):
    """두 세로 범위가 한 줄인가: 겹친 높이가 낮은 쪽 높이의 절반을 넘는다."""
    overlap = min(a[1], b[1]) - max(a[0], b[0])
    return overlap > 0.5 * min(a[1] - a[0], b[1] - b[0])


def span_boxes(container, start=None, end=None):
    """그릇의 글자 범위 [start, end) (UTF-16 자리)의 상자 목록. 줄마다 하나다. 범위를 안 주면 글 전체.

    범위 안에 좌표 있는 글자가 하나도 없으면 빈 목록.
    """
    boxes = []
    for run in container["runs"]:
        lo = run["start"] if start is None else max(start, run["start"])
        hi = run["start"] + len(run["x0"]) if end is None else min(end, run["start"] + len(run["x0"]))
        if lo >= hi:
            continue
        a, b = lo - run["start"], hi - run["start"]
        box = [min(run["x0"][a:b]), run["y0"], max(run["x1"][a:b]), run["y1"]]
        if boxes and same_line((boxes[-1][1], boxes[-1][3]), (box[1], box[3])):
            last = boxes[-1]
            boxes[-1] = [min(last[0], box[0]), min(last[1], box[1]), max(last[2], box[2]), max(last[3], box[3])]
        else:
            boxes.append(box)
    return boxes


def covered(container, start, end):
    """범위 [start, end) 의 글자 가운데 좌표가 있는 글자의 수."""
    n = 0
    for run in container["runs"]:
        n += max(0, min(end, run["start"] + len(run["x0"])) - max(start, run["start"]))
    return n
