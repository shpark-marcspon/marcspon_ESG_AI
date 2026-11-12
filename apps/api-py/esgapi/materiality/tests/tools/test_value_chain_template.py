"""웹 [양식 받기]의 빈 가치사슬 양식(apps/web/public/templates/가치사슬_양식.xlsx — 밴드 IRW15 ①, MARC-ENT-668)이
서버 읽개와 맞는가: 첫 행이 HEADER 와 같고 데이터 행은 0, 읽개에 넣으면 열 이름 오류(bad_header)가
아니라 「빈 표」 갈래(no_rows)다.
양식 파일을 다시 지으면(열 이름이 바뀌면) 이 시험이 먼저 빨개진다."""

import io
from pathlib import Path
from typing import Final

from openpyxl import load_workbook

from esgapi.materiality.tools.value_chain_xlsx import HEADER, ValueChainRejected, read_value_chain

ROOT: Final = Path(__file__).resolve().parents[5]
"""apps/ (이 파일은 apps/api-py/esgapi/materiality/tests/tools/ 에 있다)."""
TEMPLATE: Final = ROOT / "web" / "public" / "templates" / "가치사슬_양식.xlsx"


def _rows() -> list[tuple[object, ...]]:
    book = load_workbook(io.BytesIO(TEMPLATE.read_bytes()), read_only=True, data_only=True)
    try:
        return [tuple(row) for row in book.worksheets[0].iter_rows(values_only=True)]
    finally:
        book.close()


def test_template_first_row_is_header() -> None:
    rows = _rows()
    assert rows[0] == HEADER


def test_template_has_no_data_rows() -> None:
    rows = _rows()
    assert all(all(cell is None for cell in row) for row in rows[1:])


def test_template_reads_as_empty_table_not_bad_header() -> None:
    read = read_value_chain(TEMPLATE.read_bytes())
    assert isinstance(read, ValueChainRejected)
    assert read.kind == "no_rows"
    assert (read.row, read.column) == (None, None)
