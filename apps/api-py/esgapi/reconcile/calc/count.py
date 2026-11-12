"""표 숫자와 문장 숫자의 비율. 값 후보만 센다. esg-lab `ts/reconcile/src/domain/count.ts` 의 `countRatio`.

(사람이 읽는 표 `renderRatioTable` 은 보고 생성기라 옮기지 않았다.)
"""

from collections.abc import Mapping
from dataclasses import dataclass

from esgapi.reconcile.calc.types import Extraction


@dataclass(frozen=True, slots=True)
class RatioCount:
    doc_id: str
    file_name: str
    value_candidates: int  # 값 후보 전체. 아래 여섯 갈래의 합이다
    table_cells_ok: int
    table_cells_low_confidence: int
    table_text_cells_ok: int
    table_text_cells_low_confidence: int
    sentences: int
    number_only_blocks: int
    failed_tables: int  # 격자를 세우지 못한 표의 수. 그 안의 숫자 수는 모른다(어느 갈래에도 들어 있지 않다)
    pages_without_text: int
    tables_ok: int
    tables_low_confidence: int
    non_values: Mapping[str, int]  # 숫자가 있지만 값 후보가 아닌 것, 갈래별
    non_value_total: int


def count_ratio(extraction: Extraction) -> RatioCount:
    def count(bucket: str, status: str | None = None) -> int:
        return sum(1 for f in extraction.facts if f.bucket == bucket and (status is None or f.table_status == status))

    non_values: dict[str, int] = {}
    for item in extraction.non_values:
        non_values[item.cls] = non_values.get(item.cls, 0) + 1
    return RatioCount(
        doc_id=extraction.doc_id,
        file_name=extraction.file_name,
        value_candidates=len(extraction.facts),
        table_cells_ok=count("table_cell", "ok"),
        table_cells_low_confidence=count("table_cell", "low_confidence"),
        table_text_cells_ok=count("table_text_cell", "ok"),
        table_text_cells_low_confidence=count("table_text_cell", "low_confidence"),
        sentences=count("sentence"),
        number_only_blocks=count("number_only_block"),
        failed_tables=len(extraction.failed_tables),
        pages_without_text=len(extraction.pages_without_text),
        tables_ok=sum(1 for grid in extraction.grids if grid.status == "ok"),
        tables_low_confidence=sum(1 for grid in extraction.grids if grid.status == "low_confidence"),
        non_values=non_values,
        non_value_total=len(extraction.non_values),
    )
