"""문서 산출물의 구조 관계(밴드 RP2a ①, 결정 MARC-ENT-514 — 설계 §1-6). 읽을 때 코드로 짓는다(저장 0, AI 0).
표준 라이브러리만 쓴다. 이름 목록은 contract.RELATIONS 이고, 읽는 길은 view.DocArtifactView.relations·title_path 다.

    section_contains   섹션 id → 그 섹션의 블록 id(읽는 차례)                 원천 blocks[].section_id
    table_contains     표 id → 칸 id `표id:rRcC`(행 → 열 차례, 0부터)          원천 tables[].cells
    cell_row_header    칸 id → 같은 행의 머리 열 칸(자기 빼고)               원천 tables[].header.cols (추정 — basis 는
    cell_col_header    칸 id → 같은 열의 머리 행 칸(자기 빼고)                     view.table(id).header_basis)
    next_block         블록 id → 읽는 차례로 다음 본문 블록(하나 또는 0)        쪽 오름 → order 오름, region body
    title_path         블록 id → 섹션 제목 경로(level 로 쌓음) + 같은 섹션의 앞 heading 글   sections·blocks
    on_page            블록·칸 id → 쪽 번호 글자 하나                           page
모르는 id 는 빈 튜플이다(던지지 않는다). 모르는 관계 이름은 ValueError.
★ 판정은 파서 출력의 칸을 믿는다(머리 행·열은 파서의 추정이다). 블록에 region 이 없는(layout 1) 것은 본문으로 친다.
"""

from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any, Final, cast

from esgapi.core.documents.contract import RELATIONS

BODY: Final = "body"


def cell_id(table_id: str, row: int, col: int) -> str:
    return f"{table_id}:r{row}c{col}"


def parse_cell_id(value: str) -> tuple[str, int, int] | None:
    """`표id:rRcC` → (표id, 행, 열). 꼴이 아니면 None."""
    table_id, sep, tail = value.rpartition(":r")
    row, csep, col = tail.partition("c")
    if not (sep and csep and row.isdigit() and col.isdigit()):
        return None
    return table_id, int(row), int(col)


def _list(value: object) -> list[Mapping[str, Any]]:
    return [cast("Mapping[str, Any]", item) for item in cast("list[object]", value) if isinstance(item, Mapping)]


def region_of(block: Mapping[str, Any]) -> str:
    return str(block.get("region", BODY))


def reading_order(blocks: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """쪽 오름 → 쪽 안 order 오름(같으면 원래 차례)."""
    return sorted(blocks, key=lambda b: (int(b["page"]), int(b["order"])))


class Structure:
    """문서 모델 하나의 관계표. 지은 뒤 바뀌지 않는다."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        blocks = reading_order(_list(document.get("blocks", [])))
        self._blocks = {str(b["id"]): b for b in blocks}
        self._order = [str(b["id"]) for b in blocks]
        self._sections = _list(document.get("sections", []))
        self._tables = {str(t["id"]): t for t in _list(document.get("tables", []))}
        body = [i for i in self._order if region_of(self._blocks[i]) == BODY]
        self._next = dict(pairwise(body))

    def relations(self, name: str, node_id: str) -> tuple[str, ...]:
        if name not in RELATIONS:
            raise ValueError(f"모르는 관계 이름이다: {name}")
        if name == "section_contains":
            return tuple(i for i in self._order if self._blocks[i].get("section_id") == node_id)
        if name == "table_contains":
            return self._cells(node_id)
        if name in ("cell_row_header", "cell_col_header"):
            return self._headers(node_id, rows=name == "cell_col_header")
        if name == "next_block":
            found = self._next.get(node_id)
            return () if found is None else (found,)
        if name == "title_path":
            return self.title_path(node_id)
        return self._on_page(node_id)

    def _cells(self, table_id: str) -> tuple[str, ...]:
        table = self._tables.get(table_id)
        if table is None:
            return ()
        rows = cast("list[list[str]]", table.get("cells", []))
        return tuple(cell_id(table_id, r, c) for r, row in enumerate(rows) for c in range(len(row)))

    def _headers(self, node_id: str, *, rows: bool) -> tuple[str, ...]:
        parsed = parse_cell_id(node_id)
        if parsed is None or parsed[0] not in self._tables:
            return ()
        table_id, row, col = parsed
        table = self._tables[table_id]
        header = cast("Mapping[str, list[int]]", table.get("header", {}))
        if rows:  # 같은 열, 머리 행
            return tuple(cell_id(table_id, r, col) for r in header.get("rows", []) if r != row)
        return tuple(cell_id(table_id, row, c) for c in header.get("cols", []) if c != col)

    def _on_page(self, node_id: str) -> tuple[str, ...]:
        block = self._blocks.get(node_id)
        if block is not None:
            return (str(block["page"]),)
        parsed = parse_cell_id(node_id)
        table = None if parsed is None else self._tables.get(parsed[0])
        return () if table is None else (str(table["page"]),)

    def title_path(self, block_id: str) -> tuple[str, ...]:
        block = self._blocks.get(block_id)
        if block is None:
            return ()
        path: list[tuple[int, str | None]] = []  # (level, title) — 앞 섹션들을 level 로 쌓는다
        section_id = block.get("section_id")
        for section in self._sections:
            level = int(section["level"])
            while path and path[-1][0] >= level:
                path.pop()
            path.append((level, cast("str | None", section.get("title"))))
            if section["id"] == section_id:
                break
        else:
            path = []  # 섹션 밖(또는 모르는 섹션) 블록
        titles = [title for _, title in path if title]
        heading: str | None = None
        for other in self._order:
            if other == block_id:
                break
            candidate = self._blocks[other]
            if candidate.get("section_id") == section_id and candidate["kind"] == "heading":
                heading = str(candidate.get("text", ""))
        if heading and (not titles or titles[-1] != heading):
            titles.append(heading)
        return tuple(titles)
