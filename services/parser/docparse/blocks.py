"""표 밖 글자 조각을 문단·제목 블록으로 묶는다."""

from dataclasses import replace
from statistics import median

# 번역 판(layout 2): 머리 위첨자 조각과 y0 차가 글자 크기의 이 비율 안인 조각은 같은 줄로 본다
SAME_LINE_Y0_RATIO = 0.2


def _line_order(chunks):
    """(y0, x0) 차례에서 머리에 위첨자가 붙은 조각만 같은 줄의 왼쪽 조각 뒤로 옮긴다(layout 2).

    줄 끝 위첨자가 다음 줄 객체의 머리에 붙은 조각은 y0 가 소수 자리만 위라 같은 줄의 왼쪽 조각보다 먼저 온다.
    그러면 앞 문단의 다음 줄로 보는 x 정렬 거름에 걸려 새 문단을 연다(밴드 TRD1 ★④). 다른 조각은 옮기지 않는다
    (줄 전체를 x 차례로 놓으면 좁은 단 사이 틈을 같은 줄 잇기로 건너는 블록이 생긴다 — 6권 실측).
    """
    out = sorted(chunks, key=lambda c: (c.y0, c.x0))
    moved = set()
    i = 0
    while i < len(out):
        c = out[i]
        if c.body_x0 is None or id(c) in moved:
            i += 1
            continue
        moved.add(id(c))
        last, k = i, i + 1
        while k < len(out) and out[k].y0 - c.y0 < SAME_LINE_Y0_RATIO * c.size:
            if out[k].x0 < c.x0:
                last = k
            k += 1
        if last > i:
            out.insert(last, out.pop(i))
        else:
            i += 1
    return out


def build_text_blocks(chunks, layout=1):
    """조각을 문단으로 묶는다. [{"bbox", "text", "size", "chunks"}] (chunks = 글을 이룬 조각, 글의 차례대로)

    layout 2(번역 판): 머리에 위첨자가 붙은 조각을 같은 줄의 왼쪽 조각 뒤로 놓고(`_line_order`), 그 조각의 같은 줄
    잇기 틈을 위첨자 뒤 본문 자리(`Chunk.body_x0`)에서 잰다(위첨자 상자가 왼쪽 조각과 조금 겹친다). 위첨자 글자는 글에
    그대로 남는다. 숫자 조각에서 뗀 각주 위첨자(`Chunk.marks`)는 그 조각 글 바로 뒤에 붙인다(`_with_marks`).
    layout 1 은 BASE 그대로다.
    """
    paras = []
    if layout >= 2:
        chunks = [_with_marks(c) for c in chunks]
    ordered = _line_order(chunks) if layout >= 2 else sorted(chunks, key=lambda c: (c.y0, c.x0))
    for c in ordered:
        if not c.text:
            continue
        cx0 = c.body_x0 if layout >= 2 and c.body_x0 is not None else c.x0
        home = None
        for p in reversed(paras[-40:]):
            if abs(p["size"] - c.size) > 0.12 * c.size:
                continue
            x0, _y0, x1, _y1 = p["bbox"]
            same_line = c.y0 < p["last_y1"] - 0.5 * c.size and 0 <= cx0 - p["last_x1"] <= 1.5 * c.size
            overlap = min(x1, c.x1) - max(x0, c.x0)
            next_line = (
                0 <= c.y0 - p["last_y1"] + 0.35 * c.size <= 1.0 * c.size
                and overlap >= 0.5 * min(x1 - x0, c.x1 - c.x0)
                and abs(c.x0 - x0) <= 2.5 * c.size
            )
            if same_line or next_line:
                home = p
                break
        # 위첨자 머리 조각이 같은 줄로 붙으면 줄 밑을 올리지 않는다: 그 조각만 글씨가 작으면 다음 줄이 줄 간격 거름에
        # 걸린다(layout 2).
        keep_y1 = layout >= 2 and c.body_x0 is not None and home is not None and same_line
        if home is None:
            paras.append(
                {
                    "bbox": list(c.bbox),
                    "parts": [c.text],
                    "chunks": [c],
                    "size": c.size,
                    "last_y1": c.y1,
                    "last_x1": c.x1,
                }
            )
        else:
            b = home["bbox"]
            home["bbox"] = [min(b[0], c.x0), min(b[1], c.y0), max(b[2], c.x1), max(b[3], c.y1)]
            home["parts"].append(c.text)
            home["chunks"].append(c)
            home["last_y1"], home["last_x1"] = (max(home["last_y1"], c.y1) if keep_y1 else c.y1), c.x1
    return [
        {
            "bbox": [round(v, 1) for v in p["bbox"]],
            "text": " ".join(p["parts"]),
            "size": p["size"],
            "chunks": p["chunks"],
        }
        for p in paras
    ]


def _with_marks(c):
    """번역 판(layout 2): 숫자 조각에서 뗀 각주 위첨자를 글 뒤에 붙인 조각(밴드 TRD2, MARC-ISSUE-422 의 2). 표 밖 조각의
    marks 가 블록 글에서 사라지지 않게 한다. 위첨자 글자 상자(`mark_glyphs`)가 없으면 glyphs 를 None 으로 두어 그 그릇만
    잇지 않는다(지어내지 않음 — `charplaces`)."""
    if not c.marks:
        return c
    glyphs = c.glyphs + c.mark_glyphs if c.glyphs is not None and c.mark_glyphs is not None else None
    return replace(c, text=c.text + "".join(c.marks), marks=[], glyphs=glyphs, mark_glyphs=None)


def body_font_size(blocks):
    """글자 수로 가중한 본문 글자 크기(중앙값)."""
    sizes = [b["size"] for b in blocks for _ in range(max(1, len(b["text"]) // 10))]
    return median(sizes) if sizes else 0.0


def classify(block, body_size):
    """heading | paragraph. 본문보다 1.25배 이상 크고 120자 이하면 제목으로 본다."""
    if body_size and block["size"] >= 1.25 * body_size and len(block["text"]) <= 120:
        return "heading"
    return "paragraph"
