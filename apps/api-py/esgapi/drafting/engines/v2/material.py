"""S3 재료 — 잎에 달린 쪽의 body 블록에 블록 id·문장 번호 표지를 단 글(밴드 RP2b §2-2, 결정 MARC-ENT-514 2번·512).

    [PAGE 12]
    [B p12-b3] 제목 글
    [B p12-b4] ⟨0⟩첫 문장. ⟨1⟩둘째 문장.
    [T p12-t1]
    ⟨0⟩| 칸 | 칸 |
    ⟨2⟩| 칸 | 칸 |

material(pages, view)  쪽 차례 · 쪽 안은 body 블록을 읽는 차례(order). 문단 = 문장마다 ⟨i⟩(sentences.split, 0부터) ·
                       제목 = 표지 없이 글만(답의 s 는 null 이어야) · 표 = 표 id 로 [T …] 줄 + 행마다 ⟨r⟩(r = 실제 행
                       번호 — 칸이 다 빈 행은 빠져 번호가 건너뜀). 블록 글은 v1 pages.escape_heads 뒤(표지 흉내 0).
                       → Material(글, 실은 블록 {id → GivenBlock}, 잘림 여부). 블록 id 와 표 id 는 한 dict 열쇠라 같은
                       id 가 두 번 실리면 GivenConflict(덮어쓰지 않는다 — 흐름은 첫 S3 전에 단계 실패, 이슈 482)
locate(view, block_id) 블록(또는 표) 하나를 통째로 다시 지음(report 가 상자를 지을 때 — 같은 규칙이라 번호가 같다)

자르기(§2-0 ⑥ — 상한 둘 다 표지 글자까지 센다: 위끝 셈 = 실제 싣는 글):
    블록(표지 포함) 길이가 남은 쪽 몫(PAGE_MAX_CHARS)·남은 전체 몫(MATERIAL_MAX_CHARS) 안이면 넣고, 아니면 그 블록만
    빼고 다음 블록 계속. 쪽에 아직 넣은 블록이 없을 때 블록 혼자 쪽 몫을 넘으면 문장(표는 행) 단위로 들어가는 데까지 —
    문장 하나가 쪽 몫을 넘으면 그 문장은 뺀다. 전체 몫은 쪽 머리·블록을 넣을 때마다 누적(이음 글자 포함). 뺀 것이
    있으면 cut. 쪽 몫은 그 쪽 블록 줄(앞 줄바꿈 포함)의 합이다(쪽 머리는 전체 몫에만).

표 행 줄은 tools/blocks_text.table_lines 의 규칙 복사다(엔진은 tools 를 import 하지 않는다 — 시험이 견준다).
뷰는 덕 타이핑(ViewLike) — core 를 import 하지 않는다.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from esgapi.drafting.engines.v1.pages import JOIN, PAGE_MAX_CHARS, escape_heads

from .sentences import Span, pieces, split

MATERIAL_MAX_CHARS: Final = 40000
LINE: Final = "\n"
HEADING: Final = "heading"
TABLE: Final = "table"
PARAGRAPH: Final = "paragraph"

Box = tuple[float, float, float, float]


class MarkLike(Protocol):
    @property
    def row(self) -> int: ...
    @property
    def col(self) -> int: ...
    @property
    def mark(self) -> str: ...


class BlockLike(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def kind(self) -> str: ...
    @property
    def page(self) -> int: ...
    @property
    def bbox(self) -> Box: ...
    @property
    def order(self) -> int: ...
    @property
    def text(self) -> str: ...
    @property
    def table_id(self) -> str | None: ...


class TableLike(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def page(self) -> int: ...
    @property
    def bbox(self) -> Box: ...
    @property
    def cells(self) -> tuple[tuple[str, ...], ...]: ...
    @property
    def footnote_marks(self) -> Sequence[MarkLike]: ...


class ViewLike(Protocol):
    """core/documents/view.DocArtifactView 의 쓰는 몫."""

    def body_blocks(self, page: int | None = None) -> Sequence[BlockLike]: ...

    def block(self, block_id: str) -> BlockLike | None: ...

    def table(self, table_id: str) -> TableLike | None: ...

    def boxes(self, container_id: str, start: int, end: int) -> Sequence[Box] | None: ...


class GivenConflict(ValueError):
    """재료에 같은 id(블록 id = 표 id 등)가 두 번 실린다. str(e) 는 id 만 싣는다."""


def _give(given: dict[str, "GivenBlock"], block: "GivenBlock") -> None:
    if block.id in given:
        raise GivenConflict(f"재료의 블록 id {block.id} 가 겹친다")
    given[block.id] = block


@dataclass(frozen=True, slots=True)
class GivenBlock:
    """재료에 실은 블록 하나(표면 표 하나)."""

    id: str
    """블록 id(표면 표 id)."""
    kind: str
    page: int
    order: int
    bbox: Box
    units: Mapping[int, str]
    """실은 문장(표는 행) 번호 → 실은 글(이스케이프 뒤). 제목은 빈 것."""
    spans: Mapping[int, Span]
    """문장 번호 → 블록 원문 위 UTF-16 범위(문단만)."""
    cells: Mapping[int, tuple[str, ...]]
    """행 번호 → 칸 글 원문(표만)."""
    text: str
    """숫자 대조 글 = 실은 글의 합(제목은 글, 표는 실은 행 줄 전부 — 각주 표시 포함)."""


@dataclass(frozen=True, slots=True)
class Material:
    text: str
    given: dict[str, GivenBlock]
    cut: bool


def _cell(text: str, marks: Iterable[str]) -> str:
    joined = text + "".join(marks)
    return " ".join(joined.replace("|", "\\|").splitlines())


def table_rows(table: TableLike) -> dict[int, str]:
    """행 번호 → `| a | b |` 줄(칸이 다 빈 행은 뺌) — blocks_text.table_lines 와 같은 줄."""
    marks: dict[tuple[int, int], list[str]] = {}
    for mark in table.footnote_marks:
        marks.setdefault((mark.row, mark.col), []).append(mark.mark)
    rows: dict[int, str] = {}
    for r, row in enumerate(table.cells):
        cells = [_cell(text, marks.get((r, c), ())) for c, text in enumerate(row)]
        if any(cell.strip() for cell in cells):
            rows[r] = "| " + " | ".join(cells) + " |"
    return rows


def _whole(view: ViewLike, block: BlockLike) -> GivenBlock | None:
    """블록 하나를 통째로(빈 블록이면 None)."""
    if block.kind == TABLE:
        table = None if block.table_id is None else view.table(block.table_id)
        if table is None:
            return None
        rows = {r: escape_heads(line) for r, line in table_rows(table).items()}
        if not rows:
            return None
        cells = {r: table.cells[r] for r in rows}
        return GivenBlock(
            table.id, TABLE, table.page, block.order, table.bbox, rows, {}, cells, LINE.join(rows.values())
        )
    if block.kind == HEADING:
        text = escape_heads(block.text.strip())
        return (
            None if not text else GivenBlock(block.id, HEADING, block.page, block.order, block.bbox, {}, {}, {}, text)
        )
    spans = split(block.text)
    if not spans:
        return None
    units = dict(enumerate(pieces(escape_heads(block.text), spans)))
    return GivenBlock(
        block.id,
        block.kind,
        block.page,
        block.order,
        block.bbox,
        units,
        dict(enumerate(spans)),
        {},
        " ".join(units.values()),
    )


def _line(block: GivenBlock, chosen: Sequence[int]) -> str:
    if block.kind == TABLE:
        return f"[T {block.id}]" + "".join(f"{LINE}⟨{r}⟩{block.units[r]}" for r in chosen)
    if block.kind == HEADING:
        return f"[B {block.id}] {block.text}"
    return f"[B {block.id}] " + " ".join(f"⟨{i}⟩{block.units[i]}" for i in chosen)


def _clipped(block: GivenBlock, chosen: Sequence[int]) -> GivenBlock:
    units = {i: block.units[i] for i in chosen}
    joiner = LINE if block.kind == TABLE else " "
    return GivenBlock(
        block.id,
        block.kind,
        block.page,
        block.order,
        block.bbox,
        units,
        {i: block.spans[i] for i in chosen if i in block.spans},
        {i: block.cells[i] for i in chosen if i in block.cells},
        joiner.join(units.values()),
    )


def locate(view: ViewLike, block_id: str) -> GivenBlock | None:
    found = view.block(block_id)
    if found is not None and found.kind != TABLE:
        return _whole(view, found)
    table = view.table(block_id)
    if table is None:
        return None
    owner = next((b for b in view.body_blocks(table.page) if b.table_id == table.id), None)
    return None if owner is None else _whole(view, owner)


def material(pages: Sequence[int], view: ViewLike) -> Material:
    parts: list[str] = []
    given: dict[str, GivenBlock] = {}
    total = 0
    cut = False
    for number in pages:
        head = f"[PAGE {number}]"
        head_cost = len(head) + (len(JOIN) if parts else 0)
        lines: list[str] = []
        used = 0
        for block in view.body_blocks(number):
            whole = _whole(view, block)
            if whole is None:
                continue
            opening = 0 if lines else head_cost
            line = _line(whole, list(whole.units))
            cost = len(LINE) + len(line)
            if used + cost <= PAGE_MAX_CHARS and total + opening + cost <= MATERIAL_MAX_CHARS:
                lines.append(line)
                _give(given, whole)
                used, total = used + cost, total + opening + cost
                continue
            cut = True
            if lines or cost <= PAGE_MAX_CHARS or not whole.units:
                continue
            chosen: list[int] = []
            for at, unit in whole.units.items():
                if len(unit) > PAGE_MAX_CHARS:
                    continue
                trial = len(LINE) + len(_line(whole, [*chosen, at]))
                if trial > PAGE_MAX_CHARS or total + opening + trial > MATERIAL_MAX_CHARS:
                    break
                chosen.append(at)
            if chosen:
                part = _clipped(whole, chosen)
                line = _line(part, chosen)
                cost = len(LINE) + len(line)
                lines.append(line)
                _give(given, part)
                used, total = used + cost, total + opening + cost
        if lines:
            parts.append(head + "".join(LINE + line for line in lines))
    return Material(JOIN.join(parts), given, cut)
