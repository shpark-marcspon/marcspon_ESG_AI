"""테스트가 같이 쓰는 도우미. TS `test/helpers.ts` 의 `syntheticDocument` 를 옮겼다.

★ 테스트의 문서와 숫자는 전부 지어낸 것이다(synthetic). 어느 회사의 실제 값도 아니다.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from esgapi.reconcile.calc.facts import estimate_header
from esgapi.reconcile.calc.types import (
    DocBlock,
    DocModel,
    DocPage,
    DocSource,
    DocTable,
    FootnoteMark,
    GridHeader,
    TableStatus,
)

HEADER = GridHeader((0,), (0,), "rows_before_first_numeric_row")


@dataclass(frozen=True)
class TableSpec:
    id: str
    cells: Sequence[Sequence[str]]
    page: int = 1
    status: TableStatus = "ok"
    header: GridHeader | None = None
    footnotes: Sequence[FootnoteMark] = ()
    before: Sequence[str] = ()  # 표 앞에 오는 글 블록 (제목, 단위 줄)


@dataclass(frozen=True)
class BlockSpec:
    id: str
    text: str
    page: int = 1
    bbox: tuple[float, float, float, float] = (50, 300, 500, 320)
    kind: str = "paragraph"


def synthetic_document(
    name: str,
    tables: Sequence[TableSpec],
    blocks: Sequence[BlockSpec] = (),
    pages: int = 2,
    no_text_pages: Sequence[int] = (),
    extra_blocks: Sequence[DocBlock] = (),
) -> DocModel:
    """가상(synthetic) 문서 모델. 블록이 먼저, 그 뒤에 표마다 앞 글과 표 블록이 온다(순서 번호는 1부터)."""
    made: list[DocBlock] = []
    order = 0

    def push(
        block_id: str,
        kind: str,
        page: int,
        bbox: tuple[float, float, float, float],
        text: str | None,
        table_id: str | None,
    ) -> None:
        nonlocal order
        order += 1
        made.append(DocBlock(block_id, kind, page, bbox, order, text, table_id))  # pyright: ignore[reportArgumentType]

    for block in blocks:
        push(block.id, block.kind, block.page, block.bbox, block.text, None)
    for table in tables:
        for index, text in enumerate(table.before):
            push(f"{table.id}-before{index}", "paragraph", table.page, (50, 200, 500, 220), text, None)
        push(f"{table.id}-block", "table", table.page, (50, 400, 500, 600), None, table.id)
    made.extend(extra_blocks)
    return DocModel(
        source=DocSource(f"{name}.synthetic.pdf", "0" * 64, pages),
        pages=tuple(DocPage(i + 1, 800, "none" if i + 1 in no_text_pages else "present") for i in range(pages)),
        blocks=tuple(made),
        tables=tuple(
            DocTable(
                id=table.id,
                page=table.page,
                cells=() if table.status == "failed" else tuple(tuple(row) for row in table.cells),
                header=table.header or estimate_header(table.cells),
                method="none" if table.status == "failed" else "lines",
                status=table.status,
                footnote_marks=tuple(table.footnotes),
            )
            for table in tables
        ),
    )
