"""회사별 자동매칭 폴백 — 코랩 `_fill_missing_from_company_mapping`(`:6326-6370`). 부르는 곳 `:5978-5985`.

코랩은 입력 파일을 openpyxl(`data_only=True`)로 다시 열어 `기업정보!C7`(고른 회사)과 매핑 시트(2행부터 A 회사·B 상세명·
C 값)를 읽고, 대상 열의 **빈 칸만** 상세명으로 채운다. 여기는 흐름이 읽어 넘긴 템플릿 `Workbook` 의 칸을 쓴다(수식 칸은
저장된 값 — data_only 와 같다). 칸 값은 openpyxl 의 꼴로 다시 짓는다(`openpyxl_value`): 수 칸은 xml 글자에 `.`·`e`·`E`
가 있으면 float, 아니면 int — 그래서 `9.0` 으로 저장된 칸은 `"9.0"`(frames.py 의 pandas 꼴 `9` 와 다르다).
매핑 시트가 없는 템플릿(v2.1 꼴 — `MARC-ENT-169` asked)이면 그대로.
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_loc_set, colab_str
from esgapi.inventory.tools.scope3_sheets.grid import (
    CellAddress,
    FormulaCell,
    NumberCell,
    Sheet,
    TextCell,
    Workbook,
    parse_address,
)

COMPANY_SHEET = "기업정보"
COMPANY_CELL = "C7"

type OpenpyxlValue = str | int | float | None


@dataclass(frozen=True)
class MappingFill:
    """채운 뒤의 frame 과 매핑이 값을 넣은 줄(index 이름표)."""

    frame: pd.DataFrame
    filled: frozenset[object]


def _number(xml_text: str) -> int | float:
    """openpyxl `_cast_number`: `.`·`E`·`e` 가 있으면 float, 아니면 int."""
    if "." in xml_text or "E" in xml_text or "e" in xml_text:
        return float(xml_text)
    return int(xml_text)


def openpyxl_value(sheet: Sheet, address: str) -> OpenpyxlValue:
    """openpyxl(data_only) 가 그 칸에서 낼 값. 빈 칸·저장된 값 없는 수식은 None."""
    match sheet.cells.get(address):
        case None:
            return None
        case TextCell(text=text):
            return text
        case NumberCell(xml_text=xml_text):
            return _number(xml_text)
        case FormulaCell(cached=TextCell(text=text)):
            return text
        case FormulaCell(cached=NumberCell(xml_text=xml_text)):
            return _number(xml_text)
        case FormulaCell():
            return None


def _sheet(book: Workbook, name: str) -> Sheet | None:
    return next((s for s in book.sheets if s.name == name), None)


def _mapping_rows(sheet: Sheet) -> list[tuple[OpenpyxlValue, OpenpyxlValue, OpenpyxlValue]]:
    """`ws.iter_rows(min_row=2, max_col=3, values_only=True)` — 2행부터 시트의 마지막 줄까지 A·B·C."""
    rows = [parsed.row for parsed in map(parse_address, sheet.cells) if isinstance(parsed, CellAddress)]
    last = max(rows, default=0)
    return [
        (openpyxl_value(sheet, f"A{r}"), openpyxl_value(sheet, f"B{r}"), openpyxl_value(sheet, f"C{r}"))
        for r in range(2, last + 1)
    ]


def fill_missing_from_company_mapping(
    df: pd.DataFrame, template: Workbook, mapping_sheet: str, detail_col: str, target_cols: list[str]
) -> MappingFill:
    """코랩 `_fill_missing_from_company_mapping` 그대로. 매핑이 값을 넣은 줄(빈 칸이었고 매핑에 걸림)을 함께 낸다."""
    targets = [c for c in target_cols if c in df.columns]
    if not targets or detail_col not in df.columns:
        return MappingFill(df, frozenset())
    if all(bool(df[c].notna().all()) and bool((colab_str(df[c]).str.strip() != "").all()) for c in targets):
        return MappingFill(df, frozenset())

    mapping_ws = _sheet(template, mapping_sheet)
    company_ws = _sheet(template, COMPANY_SHEET)
    if mapping_ws is None or company_ws is None:
        return MappingFill(df, frozenset())
    raw_company = openpyxl_value(company_ws, COMPANY_CELL)
    company = str(raw_company).strip() if raw_company else None
    if not company:
        return MappingFill(df, frozenset())

    mapping: dict[str, str] = {}
    for c, k, v in _mapping_rows(mapping_ws):
        if c is not None and k is not None and v is not None and str(c).strip() == company:
            key = str(k).strip().lower()
            if key:
                mapping[key] = str(v).strip()
    if not mapping:
        return MappingFill(df, frozenset())

    df = df.copy()
    detail_series = colab_str(df[detail_col]).str.strip().str.lower()
    filled_rows: set[object] = set()
    for target_col in targets:
        cur: pd.Series[Any] = df[target_col]
        stripped = colab_str(cur).str.strip()
        blank_mask = (cur.isna() | (stripped == "") | (stripped.str.lower() == "none")).astype(bool)
        if not bool(blank_mask.any()):
            continue
        filled = detail_series.map(mapping)
        colab_loc_set(df, blank_mask, target_col, filled[blank_mask])
        filled_rows |= set(filled[blank_mask & filled.notna()].index.tolist())
    return MappingFill(df, frozenset(filled_rows))
