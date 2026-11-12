"""문서 모델의 글자를 PDF 의 좌표에 잇는다 (새 산출. 문서 모델은 고치지 않는다).

문서 모델(`document.json`)의 글 블록과 표 칸에는 글자만 있고 낱말의 좌표가 없다.
여기서는 같은 PDF 를 다시 읽어, 글 블록·표 칸의 글자를 이루는 낱말마다
「어느 그릇(블록 ID 또는 `표ID:r행c열`)의 몇 번째 글자부터 몇 번째 글자까지인가」와 좌표를 낸다.
값 후보의 ID 는 그릇과 글자 자리에서 나오므로(`ts/reconcile`), 이 산출로 값 후보의 좌표를 알 수 있다.

잇지 못한 것은 지어내지 않고 `unlinked` 에 남긴다. 숫자를 고치거나 추측하지 않는다.
"""

from statistics import median
from typing import Any

from .layout import page_chunks


def _u16(s):
    return len(s.encode("utf-16-le")) // 2


def _center_inside(c, box, pad=1.0):
    return box[0] - pad <= c.xc <= box[2] + pad and box[1] - pad <= c.yc <= box[3] + pad


def _paragraph_members(chunks):
    """`blocks.build_text_blocks` 와 같은 순서·같은 규칙으로 묶되, 문단마다 조각의 목록을 남긴다."""
    paras = []
    for c in sorted(chunks, key=lambda c: (c.y0, c.x0)):
        if not c.text:
            continue
        home = None
        for p in reversed(paras[-40:]):
            if abs(p["size"] - c.size) > 0.12 * c.size:
                continue
            x0, _y0, x1, _y1 = p["bbox"]
            same_line = c.y0 < p["last_y1"] - 0.5 * c.size and 0 <= c.x0 - p["last_x1"] <= 1.5 * c.size
            overlap = min(x1, c.x1) - max(x0, c.x0)
            next_line = (
                0 <= c.y0 - p["last_y1"] + 0.35 * c.size <= 1.0 * c.size
                and overlap >= 0.5 * min(x1 - x0, c.x1 - c.x0)
                and abs(c.x0 - x0) <= 2.5 * c.size
            )
            if same_line or next_line:
                home = p
                break
        if home is None:
            paras.append({"bbox": list(c.bbox), "chunks": [c], "size": c.size, "last_y1": c.y1, "last_x1": c.x1})
        else:
            b = home["bbox"]
            home["bbox"] = [min(b[0], c.x0), min(b[1], c.y0), max(b[2], c.x1), max(b[3], c.y1)]
            home["chunks"].append(c)
            home["last_y1"], home["last_x1"] = c.y1, c.x1
    return paras


def _segment(text, pool):
    """칸의 글자를 조각 글자의 차례로 가른다. pool: 글자 → 남은 개수. 긴 것부터 맞춰 보고 막히면 되돌아간다."""
    if text == "":
        return []
    options = sorted(
        (t for t, n in pool.items() if n > 0 and (text == t or text.startswith(t + " "))), key=len, reverse=True
    )
    for t in options:
        pool[t] -= 1
        rest = _segment(text[len(t) + 1 :], pool) if len(text) > len(t) else []
        if rest is not None:
            return [t, *rest]
        pool[t] += 1
    return None


def _hull(chunks):
    return [min(c.x0 for c in chunks), min(c.y0 for c in chunks), max(c.x1 for c in chunks), max(c.y1 for c in chunks)]


def _cell_order(chunks):
    """`tables_lines` 가 칸 안의 조각을 늘어놓는 차례: 줄(세로 가운데)로 묶고 줄 안에서는 왼쪽부터."""
    cs = sorted(chunks, key=lambda c: c.yc)
    tol = 0.45 * median(c.y1 - c.y0 for c in cs)
    lines = []
    for c in cs:
        if lines and c.yc - lines[-1][-1].yc <= tol:
            lines[-1].append(c)
        else:
            lines.append([c])
    return [c for line in lines for c in sorted(line, key=lambda c: c.x0)]


def _split_by_bands(slots, cands, first):
    """같은 글자의 조각 여럿을 칸에 나눠 준다. first=1 이면 열(가로 띠)부터, 0 이면 행(세로 띠)부터 끊는다. {(칸, 자리):
    조각}"""
    second = 1 - first
    pos = (lambda c: c.yc, lambda c: c.xc)
    out = {}
    ordered = sorted(cands, key=pos[first])
    at = 0
    for a in sorted({key[first] for key, _k in slots}):
        band = sorted((key[second], k, key) for key, k in slots if key[first] == a)
        group = sorted(ordered[at : at + len(band)], key=pos[second])
        at += len(band)
        for (_b, k, key), c in zip(band, group, strict=False):
            out[(key, k)] = c
    return out


def _link_table(table, chunks):
    """(칸 → 조각 차례, 잇지 못한 칸의 목록). 글자가 하나뿐인 조각은 바로 잇고, 같은 글자가 여럿이면 격자의 띠 차례로
    가른다.

    열은 가로로 겹치지 않는 띠이고 한 열 안에서 행은 위에서 아래로 놓인다. 그래서 먼저 열부터 끊는다
    (세로로 병합된 칸은 여러 행의 높이에 걸쳐 있어 행부터 끊으면 틀린다). 가로로 병합된 칸이 있으면 열부터 끊은 것이
    틀릴 수 있다. 그때는 칸의 글자 차례가 맞지 않게 되므로, 그 칸에 걸린 글자만 행부터 끊어 다시 보고 틀린 칸이 줄면
    그쪽을 쓴다.
    """
    cells = [(i, j, text) for i, row in enumerate(table["cells"]) for j, text in enumerate(row) if text]
    pool, by_text = {}, {}
    for c in chunks:
        pool[c.text] = pool.get(c.text, 0) + 1
        by_text.setdefault(c.text, []).append(c)
    wanted, unsegmented = {}, []
    for i, j, text in cells:
        seg = _segment(text, pool)
        if seg is None:
            unsegmented.append((i, j))
        else:
            wanted[(i, j)] = seg
    need = {}
    for key, seg in wanted.items():
        for k, t in enumerate(seg):
            need.setdefault(t, []).append((key, k))
    dup_keys = {key for t, slots in need.items() if len(slots) > 1 or len(by_text.get(t, [])) > 1 for key, _k in slots}

    def bind(row_first):
        bound: dict[Any, list[Any]] = {key: [None] * len(seg) for key, seg in wanted.items()}
        for t, slots in need.items():
            cands = by_text.get(t, [])
            if len(cands) != len(slots):
                continue
            for (key, k), c in _split_by_bands(slots, cands, 0 if t in row_first else 1).items():
                bound[key][k] = c
        out, failed = {}, list(unsegmented)
        for key, cs in bound.items():
            if any(c is None for c in cs):
                failed.append(key)
                continue
            ordered = _cell_order(cs) if table["method"] == "lines" else cs
            if table["method"] == "lines" and " ".join(c.text for c in ordered) != table["cells"][key[0]][key[1]]:
                failed.append(key)
                continue
            out[key] = ordered
        # 띠의 확인: 같은 행의 칸은 열 차례대로 왼쪽에서 오른쪽으로, 같은 열의 칸은 행 차례대로 위에서 아래로 놓여야
        # 한다. 어긋난 칸은 잇지 않는다.
        centers = {key: ((h := _hull(cs))[0] + h[2], h[1] + h[3]) for key, cs in out.items()}
        for key in sorted(dup_keys & set(out)):
            i, j = key
            x, y = centers[key]
            if any(
                (kk[0] == i and (kk[1] < j) != (centers[kk][0] < x))
                or (kk[1] == j and (kk[0] < i) != (centers[kk][1] < y))
                for kk in out
                if kk != key and kk not in dup_keys and (kk[0] == i or kk[1] == j)
            ):
                failed.append(key)
        for key in failed:
            out.pop(key, None)
        return out, sorted(set(failed))

    out, failed = bind(set())
    if failed:
        retry = {t for key in failed for t in wanted.get(key, [])}
        out2, failed2 = bind(retry)
        if len(failed2) < len(failed):
            out, failed = out2, failed2
    return out, failed


def _words_of(chunk, page_words):
    """조각 안의 낱말(빈칸으로 가른 것)마다 좌표를 낸다. PDF 의 낱말과 글자가 맞으면 그 좌표, 아니면 글자 수 비례로
    나눈다."""
    parts = chunk.text.split(" ")
    inside = sorted(
        (
            w
            for w in page_words
            if chunk.x0 - 0.5 <= (w[0] + w[2]) / 2 <= chunk.x1 + 0.5
            and chunk.y0 - 0.5 <= (w[1] + w[3]) / 2 <= chunk.y1 + 0.5
        ),
        key=lambda w: w[0],
    )
    if [w[4] for w in inside] == parts:
        return [(p, [round(v, 1) for v in w[:4]], True) for p, w in zip(parts, inside, strict=False)]
    total = max(1, len(chunk.text))
    width = chunk.x1 - chunk.x0
    out, at = [], 0
    for p in parts:
        x0 = chunk.x0 + width * at / total
        x1 = chunk.x0 + width * (at + len(p)) / total
        out.append((p, [round(x0, 1), round(chunk.y0, 1), round(x1, 1), round(chunk.y1, 1)], False))
        at += len(p) + 1
    return out


def link_page(page, page_no, model_blocks, model_tables):
    """쪽 하나의 (낱말 자리 목록, 잇지 못한 그릇 목록).

    낱말 자리: {"container", "start", "end", "text", "bbox", "size", "exact"} — start·end 는 그릇의 글자에서의 UTF-16
    자리.
    """
    chunks, _ = page_chunks(page)
    page_words = [w for w in page.get_words() if w[4].strip()]
    tables = [t for t in model_tables if t["page"] == page_no]
    places, unlinked = [], []

    def emit(container, ordered, text):
        at = 0
        for c in ordered:
            for word, bbox, exact in _words_of(c, page_words):
                places.append(
                    {
                        "container": container,
                        "start": _u16(text[:at]),
                        "end": _u16(text[: at + len(word)]),
                        "text": word,
                        "bbox": bbox,
                        "size": round(c.size, 1),
                        "exact": exact,
                    }
                )
                at += len(word) + 1

    # 표의 상자가 겹치면(도표의 틀과 그 안의 작은 격자) 문서 모델은 같은 조각을 두 표에 다 싣는다. 그래서 표마다 따로
    # 잇는다.
    used = set()
    for t in tables:
        mine = [c for c in chunks if _center_inside(c, t["bbox"])]
        used.update(id(c) for c in mine)
        if t["status"] == "failed":
            unlinked.append({"container": t["id"], "reason": "table_failed"})
            continue
        linked, failed = _link_table(t, [c for c in mine if c.text])
        for (i, j), ordered in linked.items():
            emit(f"{t['id']}:r{i}c{j}", ordered, t["cells"][i][j])
        unlinked.extend({"container": f"{t['id']}:r{i}c{j}", "reason": "cell_not_linked"} for i, j in failed)
    rest = [c for c in chunks if id(c) not in used]
    paras = {
        (" ".join(c.text for c in p["chunks"]), tuple(round(v, 1) for v in p["bbox"])): p
        for p in _paragraph_members(rest)
    }
    for b in model_blocks:
        if b["page"] != page_no or b["kind"] == "table":
            continue
        p = paras.get((b.get("text", ""), tuple(b["bbox"])))
        if p is None:
            unlinked.append({"container": b["id"], "reason": "block_not_linked"})
            continue
        emit(b["id"], p["chunks"], b["text"])
    return places, unlinked
