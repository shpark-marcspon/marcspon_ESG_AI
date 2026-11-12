"""쪽에서 글자 조각(chunk)과 괘선(rule)을 뽑는 기본 연산.

글자 조각 = 텍스트 계층에서 한 줄 위에 붙어 있는 글자 묶음(대개 표의 한 셀, 본문의 한 줄).
글자는 텍스트 계층의 문자열을 그대로 쓴다. 숫자를 고치거나 추측하지 않는다.
"""

import math
import re
import unicodedata
from dataclasses import dataclass, field

from .engine import Rect

# 이보다 작은 글자는 사람 눈에 보이지 않는다. KB금융 50쪽에 0.1pt 글자("17,861")가 숨어 있다.
MIN_VISIBLE_FONT_SIZE = 2.0

_NUM_RE = re.compile(r"^[\(\-+△▲▽▼]?\d[\d.,]*%?\)?$")
_DASH_RE = re.compile(r"^[-‐‑‒–—―−]$")
_YEAR_RE = re.compile(r"^(FY)?'?(19|20)\d{2}(년|년도)?$")
# 각주 표시로 볼 수 있는 위첨자 글자: 1) 2)3) * ** † 등. 그 밖의 작은 글자는 본문이다.
_MARK_RE = re.compile(r"^[\d\)\(\*,†‡]{1,8}$")
SUPERSCRIPT_SIZE_RATIO = 0.72  # 줄의 글자 크기 대비 이보다 작아야 위첨자로 본다
# 겹쳐 그려진 글자(`page_chunks(dedupe_overdrawn=True)`): 같은 글자가 글자 크기의 이 비율 안에서 또 그려졌으면 같은
# 자리로 본다.
# 굵게 보이려고 살짝 어긋나게 겹친 글자(어긋남이 크기의 몇 %)는 들고, 옆 글자(가장 좁은 글자의 폭이 크기의 약 0.2배)는
# 들지 않는 값이다.
OVERDRAWN_OFFSET_RATIO = 0.1
OVERDRAWN_SIZE_RATIO = 0.02  # 글자 크기가 이 비율 안에서 같아야 한다


def is_numeric(text):
    """숫자 값 셀인가 (쉼표·퍼센트·괄호·부호 허용). 연도 표기도 참이다."""
    s = unicodedata.normalize("NFKC", text).replace(" ", "")
    return bool(_NUM_RE.match(s))


def is_dash(text):
    return bool(_DASH_RE.match(text.strip()))


def is_year(text):
    s = unicodedata.normalize("NFKC", text).replace(" ", "")
    return bool(_YEAR_RE.match(s))


def is_value(text):
    """표의 값 칸에 올 만한 글자인가: 숫자, 연도 머리글, 값 없음 표시('-')."""
    return is_numeric(text) or is_dash(text) or is_year(text)


@dataclass
class Chunk:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    size: float
    marks: list = field(default_factory=list)  # 숫자 뒤에 붙어 있던 각주 위첨자 (값에서 떼어 낸 것)
    # text 의 글자마다 PDF 글자 상자 (x0, y0, x1, y1). 공백 뭉치를 줄여 만든 빈칸은 None.
    # 글자 자리를 내 달라고 했을 때만(`page_chunks(glyphs=True)`) 있고, text 와 맞추지 못하면 None 이다.
    glyphs: list | None = None
    # 머리에 위첨자(각주 표시)가 붙은 조각이면 그 뒤 본문 글자의 x0. 없으면 None. 번역 판(layout 2)의 줄 잇기만 쓴다
    # (`blocks.build_text_blocks`). 엔진이 줄 끝 위첨자를 다음 줄 객체의 머리에 붙여 「1)되며 …」 꼴 조각이 된다.
    body_x0: float | None = None
    # marks 로 뗀 위첨자의 글자 상자(marks 를 이은 글자 차례). 글자 자리를 읽을 때만 있다. 번역 판(layout 2)이 블록 글에
    # marks 를 붙일 때 글자 자리 그릇에 쓴다(`blocks.build_text_blocks`). 기본 판은 쓰지 않는다.
    mark_glyphs: list | None = None

    @property
    def xc(self):
        return (self.x0 + self.x1) / 2

    @property
    def yc(self):
        return (self.y0 + self.y1) / 2

    @property
    def bbox(self):
        return [self.x0, self.y0, self.x1, self.y1]

    @property
    def numeric(self):
        return is_numeric(self.text)

    @property
    def value_like(self):
        return is_value(self.text)


@dataclass
class Seg:
    """괘선 한 토막. 가로선은 (a0,a1)=x 범위·pos=y, 세로선은 (a0,a1)=y 범위·pos=x."""

    a0: float
    a1: float
    pos: float

    @property
    def length(self):
        return self.a1 - self.a0


def _clean(text):
    return re.sub(r"\s+", " ", text).strip()


def _clean_glyphs(pairs):
    """[(글자, 상자)] 에 `_clean` 과 같은 일을 한다: 공백 뭉치는 빈칸 하나(상자 없음), 양 끝 공백은 버린다."""
    out = []
    for ch, box in pairs:
        if re.fullmatch(r"\s", ch):
            if out and out[-1][0] != " ":
                out.append((" ", None))
        else:
            out.append((ch, box))
    if out and out[-1][0] == " ":
        out.pop()
    return out


def _span_glyphs(parts):
    return [(c["c"], tuple(c["bbox"])) for p in parts for c in p[4]]


def _finish(parts):
    """span 묶음 [(text, bbox, size, is_super, chars)] 을 Chunk 로 만든다. 글자가 없으면 None.

    chars 는 그 span 의 글자별 자료(rawdict)이거나 None 이다. 있으면 Chunk.glyphs 를 채운다.
    """
    body = [p for p in parts if not p[3] and p[0].strip()]
    if not body:
        body = [p for p in parts if p[0].strip()]
        if not body:
            return None
        parts = [(t, b, s, False, ch) for t, b, s, _, ch in parts]
    size = max(p[2] for p in body)
    visible = [p for p in parts if p[0].strip()]
    x0 = min(p[1][0] for p in visible)
    x1 = max(p[1][2] for p in visible)
    y0 = min(p[1][1] for p in body)
    y1 = max(p[1][3] for p in body)
    lead = 0
    while lead < len(parts) and (parts[lead][3] or not parts[lead][0].strip()):
        lead += 1
    head = "".join(p[0] for p in parts[:lead] if p[3]).replace(" ", "")
    body_x0 = parts[lead][1][0] if head and lead < len(parts) and _MARK_RE.match(head) else None
    # 끝에 붙은 위첨자를 떼어 본다. 본문이 숫자면 값이 오염되지 않게 marks 로 옮기고, 글자면 뒤에 그대로 붙인다.
    k = len(parts)
    while k > 0 and (parts[k - 1][3] or not parts[k - 1][0].strip()):
        k -= 1
    sup = "".join(p[0] for p in parts[k:] if p[3]).replace(" ", "")
    sup_parts = [p for p in parts[k:] if p[3]]
    if sup and _MARK_RE.match(sup):
        parts = parts[:k]
    else:
        sup = ""
    main = _clean("".join(p[0] for p in parts))
    marks = []
    if sup:
        if is_numeric(main) or is_dash(main):
            marks.append(sup)
        else:
            main = main + sup
    chunk = Chunk(x0, y0, x1, y1, main, size, marks, body_x0=body_x0)
    if parts[0][4] is not None:
        pairs = _clean_glyphs(_span_glyphs(parts))
        if sup and not marks:
            pairs += [g for g in _span_glyphs(sup_parts) if g[0] != " "]
        # 글자가 하나라도 어긋나면 자리를 내지 않는다 (틀린 자리를 가리키느니 없는 편이 낫다).
        if "".join(ch for ch, _ in pairs) == main:
            chunk.glyphs = [box for _, box in pairs]
        sup_glyphs = [g for g in _span_glyphs(sup_parts) if g[0] != " "] if marks else []
        if marks and "".join(ch for ch, _ in sup_glyphs) == "".join(marks):
            chunk.mark_glyphs = [box for _, box in sup_glyphs]
    return chunk


def _horizontal(line):
    dx, dy = line.get("dir", (1, 0))
    return not (abs(dy) > 0.1 or dx < 0.9)


def overdrawn_spans(blocks, offset_ratio=OVERDRAWN_OFFSET_RATIO, size_ratio=OVERDRAWN_SIZE_RATIO):
    """같은 글자가 같은 자리에 또 그려진 span 을 찾는다. rawdict 의 blocks 를 받아 버릴 span 의 목록을 돌려준다.

    [{"key": (블록, 줄, span 번호), "text", "bbox", "size"}]. 먼저 나온 것이 남고 뒤에 나온 것이 버려진다.
    span 을 통째로만 버린다: 보이는 글자 전부가 저마다, 앞서 남긴 같은 글자(크기도 같은 것)와 같은 자리일 때만.
    일부만 겹친 span 은 그대로 둔다 (글자를 솎아 내면 남은 글이 깨진다).
    글꼴 이름과 색은 보지 않는다 (색만 바꿔 덧그린 것도 같은 글이다).
    """
    kept = {}  # 글자 -> [(x0, y0, size)]
    dropped = []
    for bi, block in enumerate(blocks):
        for li, line in enumerate(block.get("lines", [])):
            if not _horizontal(line):
                continue
            for si, s in enumerate(line["spans"]):
                if s["size"] < MIN_VISIBLE_FONT_SIZE:
                    continue
                visible = [c for c in s["chars"] if c["c"].strip()]
                if not visible:
                    continue
                tol, size = offset_ratio * s["size"], s["size"]

                def drawn_before(c, tol=tol, size=size):
                    x0, y0 = c["bbox"][0], c["bbox"][1]
                    return any(
                        abs(x0 - kx) <= tol and abs(y0 - ky) <= tol and abs(size - ks) <= size_ratio * size
                        for kx, ky, ks in kept.get(c["c"], ())
                    )

                if all(drawn_before(c) for c in visible):
                    dropped.append(
                        {
                            "key": (bi, li, si),
                            "text": "".join(c["c"] for c in s["chars"]),
                            "bbox": tuple(s["bbox"]),
                            "size": size,
                        }
                    )
                else:
                    for c in visible:
                        kept.setdefault(c["c"], []).append((c["bbox"][0], c["bbox"][1], size))
    return dropped


def page_chunks(page, glyphs=False, dedupe_overdrawn=False):
    """(조각 목록, 버린 것 통계). 가로쓰기 줄만 다룬다.

    glyphs=True 면 글자별 상자도 읽어(rawdict) 조각마다 `glyphs` 를 채운다. 조각의 글자·좌표·차례는 같다.
    dedupe_overdrawn=True 면 같은 글자가 같은 자리에 또 그려진 span 을 버린다(`overdrawn_spans`). 기본은 끔이다.
    """
    stats = {"tiny_text_spans_dropped": 0, "rotated_lines_skipped": 0}
    chunks = []
    raw = glyphs or dedupe_overdrawn
    blocks = page.get_text_blocks(chars=raw)
    overdrawn = set()
    if dedupe_overdrawn:
        overdrawn = {d["key"] for d in overdrawn_spans(blocks)}
        stats["overdrawn_spans_dropped"] = len(overdrawn)
    for bi, block in enumerate(blocks):
        for li, line in enumerate(block.get("lines", [])):
            if raw:
                for s in line["spans"]:
                    s["text"] = "".join(c["c"] for c in s["chars"])
                    if not glyphs:
                        del s["chars"]
                if overdrawn:
                    line["spans"] = [s for si, s in enumerate(line["spans"]) if (bi, li, si) not in overdrawn]
            if not _horizontal(line):
                if any(s["text"].strip() for s in line["spans"]):
                    stats["rotated_lines_skipped"] += 1
                continue
            spans = []
            for s in line["spans"]:
                if not s["text"]:
                    continue
                if s["size"] < MIN_VISIBLE_FONT_SIZE:
                    if s["text"].strip():
                        stats["tiny_text_spans_dropped"] += 1
                    continue
                spans.append(s)
            if not spans:
                continue
            line_size = (
                max(s["size"] for s in spans if s["text"].strip()) if any(s["text"].strip() for s in spans) else 0
            )
            if not line_size:
                continue
            parts, prev_x1 = [], None
            for s in spans:
                # pymupdf 의 위첨자 플래그는 조금 작은 본문 글자에도 켜지므로 쓰지 않고 크기로만 판정한다.
                sup = s["size"] < SUPERSCRIPT_SIZE_RATIO * line_size
                if prev_x1 is not None and s["bbox"][0] - prev_x1 > 0.8 * line_size and s["text"].strip():
                    c = _finish(parts)
                    if c:
                        chunks.append(c)
                    parts = []
                parts.append((s["text"], s["bbox"], s["size"], sup, s.get("chars")))
                if s["text"].strip():
                    prev_x1 = s["bbox"][2]
            c = _finish(parts)
            if c:
                chunks.append(c)
    return _attach_superscripts(chunks), stats


_X1_BUCKET = 1.5  # 위첨자의 왼쪽 끝과 붙을 조각의 오른쪽 끝이 이만큼 안이다(아래 조건). 그 너비로 조각을 나눠 둔다


def _attach_superscripts(chunks):
    """따로 떨어진 줄로 잡힌 위첨자(각주 번호)를 바로 왼쪽 조각에 붙인다.

    붙을 조각은 정렬한 차례에서 조건을 채우는 첫 조각이다. 조각을 오른쪽 끝(x1)의 칸으로 나눠 두고 그 근처만 본다
    (조각 전부를 훑으면 쪽의 숫자 조각 수의 제곱이 된다. 밴드 PX2 ⑧). 붙이면 x1 이 늘므로 칸을 옮긴다.
    """
    chunks.sort(key=lambda c: (c.y0, c.x0))
    by_x1 = {}
    for j, base in enumerate(chunks):
        by_x1.setdefault(math.floor(base.x1 / _X1_BUCKET), set()).add(j)
    used = set()
    for i, c in enumerate(chunks):
        if not _MARK_RE.match(c.text.replace(" ", "")):
            continue
        lo, hi = math.floor((c.x0 - 1.5) / _X1_BUCKET) - 1, math.floor((c.x0 + 1.5) / _X1_BUCKET) + 1
        near = sorted(j for k in range(lo, hi + 1) for j in by_x1.get(k, ()))
        for j in near:
            base = chunks[j]
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
                    _add_mark(base, c, sup)
                else:
                    if base.glyphs is not None:
                        base.glyphs = (
                            base.glyphs + [g for ch, g in zip(c.text, c.glyphs, strict=False) if ch != " "]
                            if c.glyphs is not None
                            else None
                        )
                    base.text += sup
                by_x1[math.floor(base.x1 / _X1_BUCKET)].discard(j)
                base.x1 = max(base.x1, c.x1)
                by_x1.setdefault(math.floor(base.x1 / _X1_BUCKET), set()).add(j)
                used.add(i)
                break
    return [c for i, c in enumerate(chunks) if i not in used]


def _add_mark(base, mark, sup):
    """숫자 조각에 떼어 낸 각주 표시 하나를 더한다. 앞 marks 와 이번 표시의 글자 상자가 다 있을 때만
    mark_glyphs 도 잇는다(밴드 TRD2)."""
    boxes = [g for ch, g in zip(mark.text, mark.glyphs or [], strict=False) if ch != " "]
    aligned = base.mark_glyphs is not None or not base.marks
    base.mark_glyphs = (base.mark_glyphs or []) + boxes if aligned and len(boxes) == len(sup) else None
    base.marks.append(sup)


def page_rules(page):
    """(가로선 목록, 세로선 목록). 선, 얇은 사각형, 셀 배경 사각형의 변을 모은다."""
    pw, ph = page.rect.width, page.rect.height
    hs, vs = [], []

    def add_h(x0, x1, y):
        x0, x1 = max(0.0, min(x0, x1)), min(pw, max(x0, x1))
        if x1 - x0 >= 3 and 0 <= y <= ph:
            hs.append(Seg(x0, x1, y))

    def add_v(x, y0, y1):
        y0, y1 = max(0.0, min(y0, y1)), min(ph, max(y0, y1))
        if y1 - y0 >= 3 and 0 <= x <= pw:
            vs.append(Seg(y0, y1, x))

    for d in page.get_drawings():
        stroke = d.get("color") is not None
        fill = d.get("fill") is not None
        if not (stroke or fill):
            continue
        if fill and not stroke and d.get("fill_opacity", 1) == 0:
            continue
        for it in d["items"]:
            if it[0] == "l":
                p, q = it[1], it[2]
                if abs(p.y - q.y) <= 0.6:
                    add_h(p.x, q.x, (p.y + q.y) / 2)
                elif abs(p.x - q.x) <= 0.6:
                    add_v((p.x + q.x) / 2, p.y, q.y)
            elif it[0] in ("re", "qu"):
                r = Rect(it[1])
                r.normalize()
                w, h = r.width, r.height
                if h <= 1.5:
                    add_h(r.x0, r.x1, (r.y0 + r.y1) / 2)
                elif w <= 1.5:
                    add_v((r.x0 + r.x1) / 2, r.y0, r.y1)
                elif stroke or (h <= 90 and w <= 0.6 * pw):
                    # 셀 배경(채움)이나 테두리 사각형. 쪽 배경·띠 장식 같은 큰 채움 사각형은 뺀다.
                    add_h(r.x0, r.x1, r.y0)
                    add_h(r.x0, r.x1, r.y1)
                    add_v(r.x0, r.y0, r.y1)
                    add_v(r.x1, r.y0, r.y1)
    return hs, vs


def cluster_values(values, gap):
    """정렬해서 이웃 간격이 gap 이하면 한 묶음. 묶음의 평균 목록을 돌려준다."""
    out = []
    for v in sorted(values):
        if out and v - out[-1][-1] <= gap:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(g) / len(g) for g in out]
