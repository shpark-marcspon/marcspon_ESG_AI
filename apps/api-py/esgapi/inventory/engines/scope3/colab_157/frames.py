"""읽힌 시트(`tools/scope3_sheets/grid.py` 의 `Sheet`) → `pandas.DataFrame`.

코랩의 `pd.read_excel(...)` 을 흉내 낸다(처분 ⑤).

엔진은 xlsx 를 열지 않는다. xlsx 바이트는 흐름이 `tools/xlsx_reader.read_workbook` 으로 읽어 `Workbook` 을 넘긴다.
여기서는 그 칸 값으로 pandas(openpyxl 엔진)가 같은 시트에서 낼 frame 을 짓는다. 같음은 시험(S2)이 같은 xlsx 바이트를
`pd.read_excel(io.BytesIO(...))` 으로 읽어 `DataFrame.equals` 로 보인다.

코랩이 쓰는 꼴 셋:
- `read_frame(sheet, header=None)`                     — `read_template_sheet`(:2128)
- `read_frame(sheet, header=None, nrows=20)`           — `detect_template_header_row`(:2091)
- `read_frame(sheet, header=k)`                        — `_read_integrated_db_sheet`(:7877, 구매_USEPA)
- `read_frame(sheet, header=k, as_text=True)`          — `_load_ef_sheet`(:307, `dtype=str`)

pandas 3.0.6 + openpyxl 3.1.5 에서 잰 것(2026-10-19, 지어낸 xlsx — 시험 `test_frames.py` 가 경우마다 다시 잰다):
- 칸 값: 글 칸은 글자 그대로, 수 칸은 정수로 떨어지면 `int`, 아니면 `float`(openpyxl 가 읽고 pandas 가 `int(v) == v`
  로 내림). 수식 칸은 저장된 값(openpyxl `data_only=True`). 저장된 값이 없으면 빈 칸과 같다(NaN).
- 줄: 시트의 1행·A열부터 센다. 앞쪽 빈 줄과 가운데 빈 줄은 **남는다**(모두 NaN 인 줄). 끝 빈 줄과 줄 끝의 빈 칸은
  걷는다. 너비는 읽은 줄(nrows 가 있으면 그 안) 가운데 가장 긴 것.
- 결측: 빈 칸과 기본 결측 글자(`NA_STRINGS` — `NA`·`None`·`nan`·`N/A` 등 19개)인 글 칸은 NaN 이다.
- 열의 꼴(dtype 을 주지 않을 때): 결측을 뺀 값이 모두 수(수 꼴의 글자 포함)면 수 열(`int64`, 결측이 있으면 `float64`),
  모두 결측이면 `float64`, 그 밖(글만, 글·수 섞임)은 `object`(값은 그대로).
- `as_text=True`(`dtype=str`): 결측은 NaN, 나머지는 `str(값)`. 열은 모두 `object`.
- **글 열의 dtype 은 pandas 2.x 꼴(`object`)이다.** pandas 3.0.6 의 `read_excel` 은 글 열을
  `str`(`StringDtype(na_value=nan)`) 로 내는데, 그 열에는 수를 넣지 못해(TypeError) 코랩의
  `df.loc[mask, "구매금액"] = …` 꼴이 2.x 와 다르게 돈다(탐침). 그래서 코랩이 돈 2.x 의 읽기를 낸다.
  시험(S2)은 `pdcompat.legacy_strings()`(= `future.infer_string=False`) 안의 `pd.read_excel` 과 견준다 —
  그 문맥의 3.0.6 이 2.x 의 글 추론과 같다는 것은 S3C-o 대조(코랩 쪽 2.3.3)가 문다.
- 머리글 줄(`header=k`): k 앞 줄은 버리고, 빈 머리글은 `Unnamed: <열 번호>`, 겹치면 뒤에 `.1`·`.2`.
- 개정 1 B2·개정 2: `dtype=str` 로 읽은 **글 칸의 빈 칸**은 NaN 이다. 코랩처럼 `astype(str)` 하면 pandas 2.3.3 은
  `'nan'`, 3.0.6 은 NaN 그대로다. 코랩 꼴은 `pdcompat.colab_str` 로 건다 — 두 판 다 `'nan'`(critic 2 B1: xlsx 의
  빈 칸은 쓴 값이 `None` 이어도 NaN 으로 읽혀 `'nan'` 이 된다. `'None'` 은 파이썬 `None` 이 든 object Series 뿐).

흉내 내지 않는 것(무효 조건 — 이런 칸이 오면 코랩과 frame 이 다를 수 있다):
- 날짜·시각 서식 칸: openpyxl 은 서식을 읽어 `datetime` 을 내지만 우리 읽개는 서식을 읽지 않아 수로 읽는다.
- `TRUE`/`FALSE` 같은 참거짓 글자만 든 열: pandas 는 bool 로 바꾼다. 우리 읽개는 `t="b"` 칸을 파일째 거절한다.
- 병합 칸: 둘 다 왼쪽 위 칸에만 값이 있다(같음 — 시험 경우 하나).
"""

import math
from typing import Any, Final

import pandas as pd

from esgapi.inventory.tools.scope3_sheets.grid import (
    CellAddress,
    FormulaCell,
    NumberCell,
    Sheet,
    TextCell,
    parse_address,
)

# pandas 의 기본 결측 글자(`pandas._libs.parsers.STR_NA_VALUES`, 3.0.6 에서 잼 — 2026-10-19). read_excel 의
# keep_default_na=True 가 이것을 NaN 으로 읽는다.
NA_STRINGS: Final[frozenset[str]] = frozenset(
    {
        "",
        "#N/A",
        "#N/A N/A",
        "#NA",
        "-1.#IND",
        "-1.#QNAN",
        "-NaN",
        "-nan",
        "1.#IND",
        "1.#QNAN",
        "<NA>",
        "N/A",
        "NA",
        "NULL",
        "NaN",
        "None",
        "n/a",
        "nan",
        "null",
    }
)

type Raw = str | int | float  # 빈 칸은 ""(openpyxl 엔진의 _convert_cell 꼴)


def _number(xml_text: str) -> int | float:
    value = float(xml_text)
    if math.isfinite(value) and value.is_integer():
        return int(value)
    return value


def _raw(cell: TextCell | NumberCell | FormulaCell) -> Raw:
    match cell:
        case TextCell(text=text):
            return text
        case NumberCell(xml_text=xml_text):
            return _number(xml_text)
        case FormulaCell(cached=None):
            return ""
        case FormulaCell(cached=TextCell(text=text)):
            return text
        case FormulaCell(cached=NumberCell(xml_text=xml_text)):
            return _number(xml_text)
        case _:
            raise AssertionError(cell)


def raw_rows(sheet: Sheet, rows_needed: int | None = None) -> list[list[Raw]]:
    """openpyxl 엔진의 `get_sheet_data` 꼴: 1행·A열부터, 줄 끝 빈 칸과 끝 빈 줄을 걷고 가장 긴 줄로 맞춘다."""
    by_row: dict[int, dict[int, Raw]] = {}
    for address, cell in sheet.cells.items():
        parsed = parse_address(address)
        if not isinstance(parsed, CellAddress):
            raise AssertionError(address)
        by_row.setdefault(parsed.row, {})[parsed.column] = _raw(cell)
    last_row = max(by_row, default=0)
    data: list[list[Raw]] = []
    last_with_data = -1
    for row_number in range(1, last_row + 1):
        cells = by_row.get(row_number, {})
        width = max(cells, default=0)
        row: list[Raw] = [cells.get(column, "") for column in range(1, width + 1)]
        while row and row[-1] == "":
            row.pop()
        if row:
            last_with_data = row_number - 1
        data.append(row)
        if rows_needed is not None and len(data) >= rows_needed:
            break
    data = data[: last_with_data + 1]
    if data:
        width = max(len(row) for row in data)
        data = [row + [""] * (width - len(row)) for row in data]
    return data


def _is_missing(value: Raw) -> bool:
    return isinstance(value, str) and value in NA_STRINGS


def _column(values: list[Raw], *, as_text: bool) -> "pd.Series[Any]":
    cleaned: list[object] = [math.nan if _is_missing(value) else value for value in values]
    present = [value for value in cleaned if not _is_nan(value)]
    if as_text:
        return pd.Series([value if _is_nan(value) else str(value) for value in cleaned], dtype=object)
    if not present:
        return pd.Series(cleaned, dtype="float64")
    try:
        return pd.to_numeric(pd.Series(cleaned, dtype=object))
    except (ValueError, TypeError):
        pass
    return pd.Series(cleaned, dtype=object)


def _is_nan(value: object) -> bool:
    return isinstance(value, float) and math.isnan(value)


def _names(header: list[Raw]) -> list[object]:
    names: list[object] = []
    counts: dict[object, int] = {}
    for position, value in enumerate(header):
        name: object = f"Unnamed: {position}" if value == "" else value
        count = counts.get(name, 0)
        while count > 0:
            counts[name] = count + 1
            name = f"{name}.{count}"
            count = counts.get(name, 0)
        counts[name] = count + 1
        names.append(name)
    return names


def read_frame(sheet: Sheet, *, header: int | None, nrows: int | None = None, as_text: bool = False) -> pd.DataFrame:
    """`pd.read_excel(파일, sheet_name=시트, header=header, nrows=nrows[, dtype=str])` 와 같은 frame."""
    header_rows = 1 if header is None else header + 1  # pandas `_calc_rows` 꼴: 읽을 줄 = 머리 줄 수 + nrows
    data = raw_rows(sheet, None if nrows is None else header_rows + nrows)
    if not data:
        return pd.DataFrame()
    if header is None:
        body = data
        columns: list[object] = list(range(len(data[0])))
    else:
        if header > len(data) - 1:
            # pandas 의 TextParser 도 ValueError 를 낸다(코랩은 그 자리를 except 로 받는다).
            raise ValueError(f"header={header} 가 읽은 줄 수 {len(data)} 를 넘는다")
        columns = _names(data[header])
        body = data[header + 1 :]
    if nrows is not None:
        body = body[:nrows]
    if not body:
        series = {position: pd.Series([], dtype=object) for position in range(len(columns))}
    else:
        series = {
            position: _column([row[position] for row in body], as_text=as_text) for position in range(len(columns))
        }
    frame = pd.DataFrame(series)
    frame.columns = pd.RangeIndex(len(columns)) if header is None else pd.Index(columns)
    return frame
