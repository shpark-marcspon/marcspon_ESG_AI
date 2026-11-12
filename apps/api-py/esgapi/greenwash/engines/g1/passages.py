"""찾는 단위 = 단락(블록 여럿). AI 0. 랩 `esg-lab/py/semgraph/{units,passages,fixunits}.py`(SG1g) 를 문서 산출물 뷰
(core.documents.view.DocArtifactView) 위로 옮겼다.

  ① 단위: 블록 하나 = 단위 하나(읽는 차례). 표 블록은 칸을 행마다 ' | ' 로 이은 글(빈 칸 뺌).
  ② 보정(랩 fixunits — 차례 b → e → a → c):
     b. region 이 body 아닌 블록(머리·꼬리)을 뺀다.
     e. 쪽의 30% 이상에 되풀이되는 8자 이상 문단 글(머리띠·쪽 메뉴)을 뺀다.
     a. 도표 라벨(문서 산출물 chart_labels — 밴드 GE1c, 넘겼을 때만): 범주가 붙은 값 낱말이 든 도표를 「도표」 단위
        (kind table) 하나로 세워 첫 그릇 바로 앞에 둔다. 글 = 「도표: <제목>」 · 줄마다 「<범주>[ · <계열>] | <값>」 ·
        「원문: <먹은 그릇 글>」. 200자 이하거나 표인 그릇은 먹는다(단위에서 빠짐). 단락 구성(members)에는 도표 id 를
        넣지 않고 먹은 그릇 블록(없으면 그릇 블록 전부)을 둔다 — blockRanges 가 body 블록만 받는다. 첫 그릇이 같은
        도표 둘은 랩 꼴 그대로 뒤 것만 남는다(「a 덮인 도표」). 라벨을 넘기지 않으면 a 는 돌지 않는다(stat 열쇠도 0).
     c. 각주(「1)」「*」「※」로 시작, 600자 미만 문단)를 같은 쪽 가장 가까운 앞 표의 글 뒤에 「주:」로 붙인다.
  ③ 단락 짓기(랩 passages.build): 같은 섹션의 잇단 문단을 읽는 차례로 합친다. 쪽이 바뀌면 앞이 문장으로 끝나지 않을
     때만 잇는다. 문장이 끝나고 150자 이상이면, 제목·표가 끼면, 1200자를 넘으면 닫는다. 제목은 다음 단락 첫 줄에
     「섹션 제목 · 가까운 제목」으로 붙는다(열린 단락이 150자 미만이면 제목을 글로 잇는다). 표는 하나씩, 첫 줄 = 섹션
     제목 · 가까운 제목 · 바로 앞 문단 앞 120자.
  ④ f. 같은 섹션·같은 쪽의 잇단 짧은 단락(머리 줄 뺀 글 60자 미만)을 1200자까지 묶고, 표 바로 앞의 짧은 단락은 그
     표의 첫 줄로 넣는다(랩 merge_tiny — 감독 답 ①, 11-10).
  ⑤ d. 400자 넘고 글머리표 셋 이상인 단락은 글머리마다(80자 넘을 때까지 이어) 쪼갠다. 머리 줄은 항목마다. 단락의
     블록이 하나면 그 블록 글 안의 글자 범위를 span 에 둔다(못 찾으면 None).
단락 id 는 마지막에 읽는 차례로 P1, P2, … 를 다시 매긴다. 섹션 제목은 뷰에 섹션 목록 칸이 없어 섹션 첫 블록의
title_path 로 얻는다(섹션이 모두 level 1 인 문서에서 그 값 = 자기 제목. 더 깊은 섹션이면 끝 칸).
"""

import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Final, Literal, Protocol

END: Final = re.compile(r"(다|요|음|함|임|됨)\s*[.。]?\s*$|[.!?。]\s*$|[.!?]\)\s*$")
MIN, MAX = 150, 1200
FOOT: Final = re.compile(r"^\s*(?:\d{1,2}\)|\*|※)")
FOOT_MAX: Final = 600
BULLET: Final = re.compile(r"\s*(?:•|■|‒|(?<=\s)-\s)")
SPLIT_MIN, BULLET_MIN, ITEM_MIN = 400, 3, 80
REPEAT: Final = 0.3
REPEAT_MIN_CHARS: Final = 8
REPEAT_MIN_PAGES: Final = 2
"""되풀이 글의 쪽 수 하한(642-1 — 3쪽 이하면 0.3×쪽 수가 1 아래라 한 쪽에만 나온 글도 「되풀이」로 빠져 단락이 0 이었다.
4쪽 이상은 0.3×쪽 수 ≥ 1.2 라 정수 쪽 수로 ≥ 2 와 같다 — 값 그대로)."""
TINY: Final = 60
TABLE_TAG_CHARS: Final = 120

Kind = Literal["paragraph", "heading", "table"]


class BlockLike(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def kind(self) -> str: ...
    @property
    def page(self) -> int: ...
    @property
    def section_id(self) -> str | None: ...
    @property
    def text(self) -> str: ...
    @property
    def table_id(self) -> str | None: ...
    @property
    def region(self) -> str: ...


class TableLike(Protocol):
    @property
    def cells(self) -> tuple[tuple[str, ...], ...]: ...


class PageLike(Protocol):
    @property
    def page(self) -> int: ...


class ChartLike(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def title(self) -> str | None: ...


class ChartWordLike(Protocol):
    @property
    def chart(self) -> str: ...
    @property
    def container(self) -> str: ...
    @property
    def text(self) -> str: ...
    @property
    def category(self) -> str | None: ...
    @property
    def series(self) -> str | None: ...


class ChartLabelsLike(Protocol):
    """도표 라벨에서 쓰는 몫(core.documents.view.ChartLabels 가 맞는다 — engines 는 core 를 import 하지 않는다)."""

    @property
    def charts(self) -> Sequence[ChartLike]: ...
    def values(self, chart_id: str | None = None) -> Sequence[ChartWordLike]: ...


class DocumentView(Protocol):
    """뷰에서 쓰는 몫(DocArtifactView 가 맞는다)."""

    def pages(self) -> Sequence[PageLike]: ...
    def blocks(self, page: int | None = None, region: str | None = None) -> Sequence[BlockLike]: ...
    def table(self, table_id: str) -> TableLike | None: ...
    def title_path(self, block_id: str) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class Unit:
    id: str
    kind: Kind
    page: int
    section_id: str
    text: str
    rows: tuple[tuple[str, ...], ...] = ()
    region: str = "body"


@dataclass(slots=True)
class Passage:
    id: str
    kind: Literal["paragraph", "table"]
    pages: list[int]
    section_id: str
    members: list[str]
    """구성 블록 id(읽는 차례)."""
    text: str
    span: tuple[int, int] | None = None
    """d 쪼갬 단락이고 블록이 하나일 때 그 블록 글 안 [start, end)."""
    tiny: bool = field(default=False, repr=False)

    @property
    def page(self) -> int:
        return self.pages[0]


@dataclass(frozen=True, slots=True)
class Built:
    passages: tuple[Passage, ...]
    stat: dict[str, int]
    units: tuple[Unit, ...]
    """보정 뒤 단위(말 목록이 제목·표 머리를 읽는다)."""
    titles: dict[str, str]
    block_text: dict[str, str]
    """블록 id → 단위 글(표는 칸을 이은 글). 원문 확인·자기 뺌이 읽는다."""


def _table_text(rows: Sequence[Sequence[str]]) -> str:
    return "\n".join(" | ".join(c for c in r if c) for r in rows)


def units_of(view: DocumentView) -> list[Unit]:
    out: list[Unit] = []
    for b in view.blocks():
        kind: Kind = "table" if b.kind == "table" else "heading" if b.kind == "heading" else "paragraph"
        if kind == "table":
            table = view.table(b.table_id or "")
            rows = tuple(tuple(c or "" for c in r) for r in (table.cells if table is not None else ()))
            out.append(Unit(b.id, kind, b.page, b.section_id or "", _table_text(rows), rows, b.region))
        else:
            out.append(Unit(b.id, kind, b.page, b.section_id or "", b.text or "", (), b.region))
    return out


def section_titles(view: DocumentView, units: Sequence[Unit]) -> dict[str, str]:
    first: dict[str, str] = {}
    for u in units:
        first.setdefault(u.section_id, u.id)
    out: dict[str, str] = {}
    for sid, bid in first.items():
        path = view.title_path(bid)
        out[sid] = path[-1] if path else ""
    return out


def _space(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


CHART_EAT_CHARS: Final = 200
"""도표 그릇 중 이 글자 수 이하(또는 표)인 것은 도표 단위가 먹는다(랩 fixunits :118)."""


def chart_units(
    keep: Sequence[Unit], labels: ChartLabelsLike, table_block: dict[str, str], known: set[str]
) -> tuple[list[Unit], dict[str, list[str]], Counter[str]]:
    """보정 a(랩 fixunits.fix_units 의 a 그대로). 돌려주는 members = 놓인 도표 id → 단락 구성 블록(먹은 그릇, 없으면
    그릇 전부 — 읽는 차례). table_block = 표 id → 표 블록 id(그릇 「<표 id>:r<i>c<j>」 를 앱 단위 = 표 블록으로),
    known = 문서의 블록 id 전부. 라벨이 문서와 어긋난 낱말(도표가 charts 에 없음 · 그릇이 문서에 없음 · 표에 블록이
    없음)은 건너뛰고 stat 에 센다(b·e 가 뺀 그릇은 어긋남이 아니다 — 랩처럼 조용히 그릇에서 빠진다)."""
    stat: Counter[str] = Counter({"a 건너뜀: 도표 없음": 0, "a 건너뜀: 그릇 없음": 0, "a 건너뜀: 표 블록 없음": 0})
    title_of = {c.id: c.title or "" for c in labels.charts}
    by_chart: dict[str, list[ChartWordLike]] = defaultdict(list)
    for w in labels.values():
        if not w.category:
            continue
        head, sep, _ = w.container.partition(":")
        if w.chart not in title_of:
            stat["a 건너뜀: 도표 없음"] += 1
        elif sep and head not in known and head not in table_block:
            stat["a 건너뜀: 표 블록 없음"] += 1
        elif not sep and head not in known:
            stat["a 건너뜀: 그릇 없음"] += 1
        else:
            by_chart[w.chart].append(w)
    at = {u.id: i for i, u in enumerate(keep)}
    gone: set[str] = set()
    chart_at: dict[str, Unit] = {}
    members: dict[str, list[str]] = {}
    built = 0
    for cid, ws in by_chart.items():
        conts: list[str] = []
        for w in ws:
            k = w.container.split(":")[0]
            k = table_block.get(k, k)
            if k in at and k not in conts:
                conts.append(k)
        if not conts:
            continue
        lines = [f"{w.category}" + (f" · {w.series}" if w.series else "") + f" | {w.text}" for w in ws]
        eat = [k for k in conts if len(keep[at[k]].text) <= CHART_EAT_CHARS or keep[at[k]].kind == "table"]
        text = (
            f"도표: {title_of[cid]}\n"
            + "\n".join(lines)
            + "\n원문: "
            + " / ".join(keep[at[k]].text.replace("\n", " / ") for k in eat)
        )
        first = keep[at[conts[0]]]
        rows = tuple((w.category or "", w.series or "", w.text) for w in ws)
        chart_at[conts[0]] = Unit(cid, "table", first.page, first.section_id, text, rows)
        members[cid] = sorted(eat or conts, key=at.__getitem__)
        gone.update(eat)
        built += 1
    out: list[Unit] = []
    for u in keep:
        if u.id in chart_at:
            out.append(chart_at[u.id])
        if u.id not in gone:
            out.append(u)
    stat["a 도표 단위"] = built
    stat["a 흡수한 조각"] = len(gone)
    stat["a 덮인 도표"] = built - len(chart_at)
    placed = {u.id for u in chart_at.values()}
    return out, {c: m for c, m in members.items() if c in placed}, stat


def fix_units(
    units: Sequence[Unit],
    page_count: int,
    labels: ChartLabelsLike | None = None,
    table_block: dict[str, str] | None = None,
) -> tuple[list[Unit], dict[str, list[str]], Counter[str], dict[str, list[str]]]:
    """보정 b·e·(a)·c. 돌려주는 absorbed = 표·도표 단위 id → 붙인 각주 블록 id, chart_members = 도표 단위 id → 단락
    구성 블록(labels 가 None 이면 a 를 돌지 않고 빈 dict)."""
    stat: Counter[str] = Counter()
    keep = [u for u in units if u.region == "body"]
    stat["b 머리·꼬리 뺌"] = len(units) - len(keep)
    pages_of: dict[str, set[int]] = defaultdict(set)
    for u in keep:
        if u.kind != "table":
            pages_of[_space(u.text)].add(u.page)
    rep = {
        t
        for t, ps in pages_of.items()
        if len(t) >= REPEAT_MIN_CHARS and len(ps) >= max(REPEAT_MIN_PAGES, REPEAT * page_count)
    }
    n0 = len(keep)
    keep = [u for u in keep if u.kind == "table" or _space(u.text) not in rep]
    stat["e 되풀이 글 뺌"] = n0 - len(keep)
    chart_members: dict[str, list[str]] = {}
    if labels is not None:
        keep, chart_members, a_stat = chart_units(keep, labels, table_block or {}, {u.id for u in units})
        stat.update(a_stat)
    absorbed: dict[str, list[str]] = defaultdict(list)
    res: list[Unit] = []
    last_table: dict[int, int] = {}
    for u in keep:
        if u.kind == "table":
            last_table[u.page] = len(res)
            res.append(u)
            continue
        if u.kind == "paragraph" and FOOT.match(u.text) and len(u.text) < FOOT_MAX and u.page in last_table:
            t = res[last_table[u.page]]
            res[last_table[u.page]] = replace(t, text=t.text + "\n주: " + u.text.strip())
            absorbed[t.id].append(u.id)
            stat["c 표에 붙인 각주"] += 1
            continue
        res.append(u)
    return res, dict(absorbed), stat, chart_members


@dataclass(slots=True)
class _Open:
    members: list[str]
    lines: list[str]
    pages: list[int]
    section_id: str

    def chars(self) -> int:
        return sum(len(x) + 1 for x in self.lines)


def build(units: Sequence[Unit], titles: dict[str, str]) -> list[Passage]:
    """랩 passages.build 그대로(id 는 임시 — 끝에 다시 매긴다). 머리 줄 이름표는 닫을 때의 가까운 제목이다."""
    out: list[Passage] = []
    head: dict[str, str] = {}
    prev_par: Unit | None = None
    cur: _Open | None = None

    def label(sid: str) -> str:
        return " · ".join(t for t in (titles.get(sid, ""), head.get(sid, "")) if t)

    def close() -> None:
        nonlocal cur
        if cur is not None and cur.members:
            first = label(cur.section_id)
            body = " ".join(cur.lines)
            text = (first + "\n" if first else "") + body
            out.append(
                Passage(f"P{len(out) + 1}", "paragraph", sorted(set(cur.pages)), cur.section_id, cur.members, text)
            )
        cur = None

    for u in units:
        if u.kind == "heading":
            # 그림 속 숫자·낱말이 제목으로 잡혀 짧은 조각 사이에 끼는 꼴: 단락이 짧으면 닫지 않고 글로 잇는다
            if cur is not None and cur.section_id == u.section_id and cur.chars() < MIN and u.text.strip():
                cur.members.append(u.id)
                cur.lines.append(u.text.strip())
                cur.pages.append(u.page)
                continue
            close()
            head[u.section_id] = u.text
            continue
        if u.kind == "table":
            close()
            tag = [titles.get(u.section_id, ""), head.get(u.section_id, "")]
            if prev_par is not None and prev_par.section_id == u.section_id:
                tag.append(prev_par.text[:TABLE_TAG_CHARS])
            text = " · ".join(t for t in tag if t) + "\n" + u.text
            out.append(Passage(f"P{len(out) + 1}", "table", [u.page], u.section_id, [u.id], text))
            continue
        t = u.text.strip()
        if not t:
            continue
        if cur is not None and (
            cur.section_id != u.section_id or (u.page != cur.pages[-1] and END.search(cur.lines[-1]))
        ):
            close()
        if cur is None:
            cur = _Open([], [], [], u.section_id)
        cur.members.append(u.id)
        cur.lines.append(t)
        cur.pages.append(u.page)
        prev_par = u
        n = cur.chars()
        if (END.search(t) and n >= MIN) or n > MAX:
            close()
    close()
    return out


def _body(p: Passage) -> str:
    return p.text.partition("\n")[2] if "\n" in p.text else p.text


def merge_tiny(ps: list[Passage]) -> tuple[list[Passage], int]:
    """보정 f(랩 fixunits.merge_tiny 그대로)."""
    out: list[Passage] = []
    n = 0
    for p in ps:
        body = _body(p)
        prev = out[-1] if out else None
        if (
            prev is not None
            and p.kind == prev.kind == "paragraph"
            and len(body) < TINY
            and prev.section_id == p.section_id
            and prev.pages[-1] == p.pages[0]
            and prev.tiny
            and len(prev.text) + len(body) < MAX
        ):
            prev.text += " · " + body
            prev.members = prev.members + p.members
            prev.pages = sorted(set(prev.pages + p.pages))
            n += 1
            continue
        p.tiny = p.kind == "paragraph" and len(body) < TINY
        out.append(p)
    res: list[Passage] = []
    for i, p in enumerate(out):
        nxt = out[i + 1] if i + 1 < len(out) else None
        if (
            p.tiny
            and nxt is not None
            and nxt.kind == "table"
            and nxt.section_id == p.section_id
            and nxt.pages[0] in p.pages
        ):
            body = _body(p) or p.text
            head, _, rest = nxt.text.partition("\n")
            nxt.text = f"{head} · {body}\n{rest}"
            nxt.members = p.members + nxt.members
            n += 1
            continue
        res.append(p)
    return res, n


def _span_of(block: str, first: str, last: str) -> tuple[int, int] | None:
    start = block.find(first)
    if start < 0:
        return None
    end_at = block.find(last, start)
    if end_at < 0:
        return None
    return (start, end_at + len(last))


def split_summary(ps: list[Passage], block_text: dict[str, str]) -> tuple[list[Passage], int]:
    """보정 d(랩 fixunits.split_summary 그대로) + 블록 하나인 단락의 span."""
    out: list[Passage] = []
    n = 0
    for p in ps:
        head, _, body = p.text.partition("\n") if "\n" in p.text else ("", "", p.text)
        parts = [x.strip() for x in BULLET.split(body) if x.strip()]
        if not (p.kind == "paragraph" and len(p.text) > SPLIT_MIN and len(parts) >= BULLET_MIN + 1):
            out.append(p)
            continue
        chunks: list[list[str]] = []
        cur: list[str] = []
        for x in parts:
            cur.append(x)
            if len(" • ".join(cur)) >= ITEM_MIN:
                chunks.append(cur)
                cur = []
        if cur:
            if chunks and len(" • ".join(cur)) < ITEM_MIN:
                chunks[-1] += cur
            else:
                chunks.append(cur)
        if len(chunks) < 2:
            out.append(p)
            continue
        n += 1
        only = block_text.get(p.members[0], "") if len(p.members) == 1 else ""
        for c in chunks:
            span = _span_of(only, c[0], c[-1]) if only else None
            text = (head + "\n" if head else "") + " • ".join(c)
            out.append(Passage("", "paragraph", list(p.pages), p.section_id, list(p.members), text, span))
    return out, n


def build_passages(view: DocumentView, chart_labels: ChartLabelsLike | None = None) -> Built:
    """뷰 → 단락(보정 b·e·(a)·c → 짓기 → f → d). 같은 뷰·같은 라벨이면 같은 단락·같은 id. chart_labels 가 None 이면
    도표 단위 0(GE1c 앞과 바이트 같음)."""
    units = units_of(view)
    titles = section_titles(view, units)
    table_block = {b.table_id: b.id for b in view.blocks() if b.table_id} if chart_labels is not None else None
    fixed, absorbed, stat, chart_members = fix_units(units, len(view.pages()), chart_labels, table_block)
    ps = build(fixed, titles)
    for p in ps:  # 도표 단위 id 는 구성 블록으로 바꾸고, 붙인 각주 블록을 그 표·도표 단락의 구성에 넣는다
        own = [b for m in p.members for b in chart_members.get(m, [m])]
        p.members = own + [a for m in p.members for a in absorbed.get(m, [])]
    block_text = {u.id: u.text for u in units}
    ps, stat["f 묶은 짧은 단락"] = merge_tiny(ps)
    ps, stat["d 쪼갠 요약 단락"] = split_summary(ps, block_text)
    for i, p in enumerate(ps):
        p.id = f"P{i + 1}"
    return Built(passages=tuple(ps), stat=dict(stat), units=tuple(fixed), titles=titles, block_text=block_text)
