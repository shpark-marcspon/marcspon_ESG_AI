"""문서 산출물의 읽기 뷰 `DocArtifactView`(밴드 RP2a ①, 결정 MARC-ENT-514 — 설계 §1-7). 표준 라이브러리만 쓴다.
모듈은 이 뷰로만 산출물을 읽는다: 짓는 길은 selectors.artifact_view(DB), 시험은 core/tests/artifact_fakes.py 의
FakeArtifactView.from_dicts(지어낸 dict) — 둘이 같은 꼴이다.

    pages()                       쪽(분해한 쪽만, 쪽 오름)
    blocks(page=None, region=None)  블록(읽는 차례 — 쪽 오름 → order 오름). region 없는 블록(layout 1)은 body
    block(id) · table(id)          하나(없으면 None)
    cell(table_id, r, c)           칸 글(없으면 None — 행·열은 0부터)
    relations(name, id)            구조 관계(structure.py, 이름은 contract.RELATIONS)
    title_path(id)                 = relations("title_path", id)
    boxes(container_id, start, end)  글자 범위 [start, end) 의 줄 상자. 범위의 단위는 **UTF-16 자리**(글자 자리의
                                  단위 — 보충 평면 글자는 두 자리). 글자 자리를 실은 뷰(places=True)만 — 아니면
                                  PlacesNotLoaded. 그 그릇의 줄 토막(runs)이 없으면 None.
    chart_labels()                 도표 라벨(밴드 CHL1) — ChartLabels(찾았는데 0 이면 빈 튜플) | None(칸 없음: EPOCH 1
                                  행·판 1). 라벨을 싣지 않은 뷰(charts=False·키워드 없이 지은 뷰)는
                                  ChartLabelsNotLoaded, EPOCH 2·판 2 행인데 칸이 비면 ChartLabelsUnavailable.

★ 뷰는 바뀌지 않는다: 돌려주는 것은 frozen dataclass·튜플이다(원본 dict 를 내주지 않는다).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, cast

from esgapi.core.documents.structure import BODY, Structure, reading_order, region_of

Box = tuple[float, float, float, float]


class PlacesNotLoaded(RuntimeError):
    """글자 자리를 싣지 않은 뷰(places=False)에 상자를 물었다."""


class ChartLabelsNotLoaded(RuntimeError):
    """도표 라벨을 싣지 않은 뷰(charts=False, 또는 chart_labels 키워드 없이 지은 뷰)에 라벨을 물었다."""


class ChartLabelsUnavailable(RuntimeError):
    """도표 라벨을 받는 판(EPOCH 2 이상·판 2)의 행인데 칸이 비었다 — 라벨을 짓지 못했다(파서가 라벨 요청을 거절해 라벨
    없이 지은 행, CHL1 ④). None(칸 없음 — EPOCH 1·판 1)과 다르다."""


class _Unavailable:
    """「라벨 못 지음」 표(selectors 가 그 행에만 넘긴다)."""


UNAVAILABLE: Final = _Unavailable()


class _NotLoaded:
    """「안 실음」 표. None(칸 없음)과 일부러 다르다(밴드 CHL1 1-3 ⑤)."""


NOT_LOADED: Final = _NotLoaded()


@dataclass(frozen=True, slots=True)
class Page:
    page: int
    width: float
    height: float
    text_layer: str  # present | none


@dataclass(frozen=True, slots=True)
class Block:
    id: str
    kind: str  # paragraph | table | heading
    page: int
    bbox: Box
    order: int
    section_id: str | None
    text: str  # 표 블록은 빈 글(칸은 table(table_id))
    table_id: str | None
    region: str  # body | header | footer


@dataclass(frozen=True, slots=True)
class FootnoteMark:
    row: int
    col: int
    mark: str


@dataclass(frozen=True, slots=True)
class Table:
    id: str
    page: int
    bbox: Box
    cells: tuple[tuple[str, ...], ...]
    header_rows: tuple[int, ...]
    header_cols: tuple[int, ...]
    header_basis: str  # 머리 행·열은 파서의 추정이다
    footnote_marks: tuple[FootnoteMark, ...]
    status: str  # ok | low_confidence | failed


@dataclass(frozen=True, slots=True)
class Chart:
    """도표 하나(파서 chartLabels.charts[] — 범례·그림 영역은 싣지 않는다)."""

    id: str  # p<쪽>-c<n>
    page: int
    bbox: Box
    form: str  # bar | line | bar+line | scatter
    orientation: str  # vertical | horizontal
    title: str | None
    multi_series: bool
    categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChartWord:
    """도표 속 숫자 낱말 하나. 범주·계열·status 는 합친 라벨(label)의 것만(coord·elem 은 내지 않는다 — D5).

    role: value | tick | category. 값이 아닌 낱말(tick·category)은 category·series·status 가 None.
    category None 인 값 = 애매해서 붙이지 않음(status 가 까닭 — 틀린 라벨은 없는 라벨보다 나쁘다).
    """

    chart: str
    container: str  # 블록 id 또는 표id:r행c열
    start: int  # UTF-16 자리
    end: int
    text: str
    bbox: Box
    role: str
    category: str | None
    series: str | None
    status: str | None


@dataclass(frozen=True, slots=True)
class ChartLabels:
    """산출물의 도표 라벨. 낱말은 쪽 → 도표(charts 의 차례) → 파서가 낸 차례."""

    charts: tuple[Chart, ...]
    words: tuple[ChartWord, ...]

    def values(self, chart_id: str | None = None) -> tuple[ChartWord, ...]:
        """범주가 붙은 값 낱말만(그 도표 것만, chart_id 가 있으면)."""
        return tuple(
            w
            for w in self.words
            if w.role == "value" and w.category is not None and (chart_id is None or w.chart == chart_id)
        )


def _text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


def chart_labels_of(labels: Mapping[str, Any]) -> ChartLabels:
    """파서의 chartLabels(dict)를 뷰의 꼴로. 순수 — DB 뷰와 가짜 뷰가 같이 쓴다."""
    charts = tuple(
        Chart(
            id=str(c["id"]),
            page=int(c["page"]),
            bbox=_box(c["bbox"]),
            form=str(c["form"]),
            orientation=str(c["orientation"]),
            title=_text_or_none(c.get("title")),
            multi_series=bool(c.get("multi_series", False)),
            categories=tuple(str(x) for x in cast("list[object]", c.get("categories") or [])),
        )
        for c in _items(labels.get("charts"))
    )
    rank = {c.id: (c.page, i) for i, c in enumerate(charts)}
    raw = _items(labels.get("words"))
    ordered = sorted(range(len(raw)), key=lambda i: (*rank.get(str(raw[i]["chart"]), (1 << 30, 1 << 30)), i))
    words: list[ChartWord] = []
    for i in ordered:
        w = raw[i]
        label = cast("Mapping[str, Any]", w.get("label") or {})
        words.append(
            ChartWord(
                chart=str(w["chart"]),
                container=str(w["container"]),
                start=int(w["start"]),
                end=int(w["end"]),
                text=str(w["text"]),
                bbox=_box(w["bbox"]),
                role=str(w["role"]),
                category=_text_or_none(label.get("category")),
                series=_text_or_none(label.get("series")),
                status=_text_or_none(label.get("status")),
            )
        )
    return ChartLabels(charts=charts, words=tuple(words))


def _box(value: object) -> Box:
    x0, y0, x1, y1 = (float(v) for v in cast("list[float]", value))
    return (x0, y0, x1, y1)


def _items(value: object) -> list[Mapping[str, Any]]:
    return [cast("Mapping[str, Any]", item) for item in cast("list[object]", value or []) if isinstance(item, Mapping)]


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _same_line(a: Box, b: Box) -> bool:
    """세로 범위가 겹친 높이가 낮은 쪽 높이의 절반을 넘으면 한 줄(글자 자리 스키마의 runs 설명)."""
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    return overlap > min(a[3] - a[1], b[3] - b[1]) / 2


class DocArtifactView:
    """산출물 하나의 읽기 뷰. 만드는 길은 selectors.artifact_view 와 시험의 FakeArtifactView.from_dicts 뿐이다."""

    def __init__(
        self,
        *,
        artifact_id: int,
        document: Mapping[str, Any],
        char_places: Mapping[str, Any] | None,
        chart_labels: Mapping[str, Any] | _NotLoaded | _Unavailable | None = NOT_LOADED,
    ) -> None:
        self.artifact_id = artifact_id
        # 「안 실음」(NOT_LOADED) · None(칸 없음) · 라벨 — 셋을 접지 않는다(CHL1 1-3 ⑤)
        self._chart_labels: ChartLabels | _NotLoaded | _Unavailable | None = (
            chart_labels
            if chart_labels is None or isinstance(chart_labels, _NotLoaded | _Unavailable)
            else chart_labels_of(chart_labels)
        )
        source = cast("Mapping[str, Any]", document.get("source", {}))
        self.source_sha256 = str(source.get("sha256", ""))
        self.page_count = int(source.get("page_count", 0))
        self._pages = tuple(
            Page(int(p["page"]), float(p["width"]), float(p["height"]), str(p.get("text_layer", "present")))
            for p in sorted(_items(document.get("pages")), key=lambda p: int(p["page"]))
        )
        self._blocks = tuple(
            Block(
                id=str(b["id"]),
                kind=str(b["kind"]),
                page=int(b["page"]),
                bbox=_box(b["bbox"]),
                order=int(b["order"]),
                section_id=None if b.get("section_id") is None else str(b["section_id"]),
                text=str(b.get("text", "")),
                table_id=None if b.get("table_id") is None else str(b["table_id"]),
                region=region_of(b),
            )
            for b in reading_order(_items(document.get("blocks")))
        )
        self._block_by_id = {b.id: b for b in self._blocks}
        self._tables = {
            str(t["id"]): Table(
                id=str(t["id"]),
                page=int(t["page"]),
                bbox=_box(t["bbox"]),
                cells=tuple(tuple(str(c) for c in row) for row in cast("list[list[str]]", t.get("cells", []))),
                header_rows=tuple(int(r) for r in cast("Mapping[str, list[int]]", t["header"]).get("rows", [])),
                header_cols=tuple(int(c) for c in cast("Mapping[str, list[int]]", t["header"]).get("cols", [])),
                header_basis=str(cast("Mapping[str, Any]", t["header"]).get("basis", "")),
                footnote_marks=tuple(
                    FootnoteMark(int(m["row"]), int(m["col"]), str(m["mark"])) for m in _items(t.get("footnote_marks"))
                ),
                status=str(t.get("status", "ok")),
            )
            for t in _items(document.get("tables"))
        }
        self._structure = Structure(document)
        self._places_loaded = char_places is not None
        self._containers = {str(c["id"]): c for c in _items((char_places or {}).get("containers"))}

    # ── 쪽·블록·표 ──

    def pages(self) -> tuple[Page, ...]:
        return self._pages

    def blocks(self, page: int | None = None, region: str | None = None) -> tuple[Block, ...]:
        return tuple(
            b for b in self._blocks if (page is None or b.page == page) and (region is None or b.region == region)
        )

    def body_blocks(self, page: int | None = None) -> tuple[Block, ...]:
        return self.blocks(page, BODY)

    def block(self, block_id: str) -> Block | None:
        return self._block_by_id.get(block_id)

    def table(self, table_id: str) -> Table | None:
        return self._tables.get(table_id)

    def cell(self, table_id: str, row: int, col: int) -> str | None:
        table = self._tables.get(table_id)
        if table is None or not (0 <= row < len(table.cells)) or not (0 <= col < len(table.cells[row])):
            return None
        return table.cells[row][col]

    # ── 구조 관계 ──

    def relations(self, name: str, node_id: str) -> tuple[str, ...]:
        return self._structure.relations(name, node_id)

    def title_path(self, block_id: str) -> tuple[str, ...]:
        return self._structure.title_path(block_id)

    # ── 도표 라벨 ──

    def chart_labels(self) -> ChartLabels | None:
        """도표 라벨. None = 칸 없음(EPOCH 1 행·판 1). 안 실은 뷰는 ChartLabelsNotLoaded, 라벨을 받는 판의 행인데 짓지
        못했으면 ChartLabelsUnavailable."""
        if isinstance(self._chart_labels, _NotLoaded):
            raise ChartLabelsNotLoaded("도표 라벨을 싣지 않은 뷰다(artifact_view(…, charts=True) 로 연다)")
        if isinstance(self._chart_labels, _Unavailable):
            raise ChartLabelsUnavailable("이 산출물은 도표 라벨을 짓지 못했다(라벨 없이 분해한 행)")
        return self._chart_labels

    # ── 상자 ──

    def _container_text(self, container_id: str) -> str:
        block = self._block_by_id.get(container_id)
        if block is not None:
            return block.text
        table_id, _, tail = container_id.rpartition(":r")
        row, _, col = tail.partition("c")
        found = self.cell(table_id, int(row), int(col)) if row.isdigit() and col.isdigit() else None
        return found or ""

    def boxes(self, container_id: str, start: int, end: int) -> tuple[Box, ...] | None:
        """그릇의 글 [start, end)(UTF-16 자리) 의 줄 상자. 이웃 토막이 한 줄이면 합집합 하나로 묶는다."""
        if not self._places_loaded:
            raise PlacesNotLoaded("글자 자리를 싣지 않은 뷰다(artifact_view(…, places=True) 로 연다)")
        container = self._containers.get(container_id)
        runs = _items(None if container is None else container.get("runs"))
        if not runs:
            return None
        end = min(end, utf16_length(self._container_text(container_id)))  # 그릇 글의 끝(UTF-16)에서 자른다
        parts: list[Box] = []
        for run in runs:
            first = int(run["start"])
            x0s, x1s = cast("list[float]", run["x0"]), cast("list[float]", run["x1"])
            lo, hi = max(start, first), min(end, first + len(x0s))
            if lo >= hi:
                continue
            parts.append(
                (
                    min(float(x) for x in x0s[lo - first : hi - first]),
                    float(run["y0"]),
                    max(float(x) for x in x1s[lo - first : hi - first]),
                    float(run["y1"]),
                )
            )
        merged: list[Box] = []
        for part in parts:
            if merged and _same_line(merged[-1], part):
                last = merged[-1]
                merged[-1] = (
                    min(last[0], part[0]),
                    min(last[1], part[1]),
                    max(last[2], part[2]),
                    max(last[3], part[3]),
                )
            else:
                merged.append(part)
        return tuple(merged)
