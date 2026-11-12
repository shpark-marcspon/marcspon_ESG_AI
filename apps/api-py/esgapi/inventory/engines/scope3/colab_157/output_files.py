"""출력 파일 둘의 **내용** — 코랩 `<base>_result.xlsx`(셀 23 `:6205-6246` + 셀 27 후처리 `:8878-8911`)와
`<base>_filled_template.xlsx`(셀 30 `build_filled_template` `:9178-9469`).

    build_outputs(template, parts, post_failed, runs) -> OutputFiles

엔진은 xlsx 를 열지도 쓰지도 않는다(처분 ⑤ — `test_purity.py`). 여기는 파일에 적힐 것만 짓는다:
- 결과 파일: 시트·열·줄 값(`ResultSheet`). 값은 코랩이 **둘째 파일에 쓰기 직전**의 값이다 — 모든 시트가 첫 왕복
  (`to_excel` → `read_excel` `:8882`)을 거치므로 후처리가 쓰지 않은 칸은 첫 왕복을 흉내 낸 값(`=…` 글·빈 글 → None,
  결측 글자 → None, 수 꼴 글만 든 열은 수). `%.16g` 자름은 쓰개(openpyxl)가 한다.
- 채운 템플릿: 원본 템플릿에서 바꿀 칸의 목록(`CellWrite`)과 시트마다 코랩 코드의 갈래(`FilledSheet`). 원본을 열고 칸에
  넣고 저장하는 쓰개에는 판단이 없다.
바이트를 쓰는 쓰개는 아직 시험 덤프(`tests/scope3colab_dump.py`)에만 있다(흐름 파일은 S3C-c3).

왕복 흉내(`reread`): openpyxl 이 쓰는 꼴(수 `"%.16g"`, `=…` 글은 수식 — 저장 값 없음, 빈 글은 빈 칸, 오류 글자는
오류 칸, pandas 의 무한 `inf_rep`)로 grid `Sheet` 를 짓고 `frames.read_frame(header=0)` 으로 읽는다. frames 가 흉내 내지
않는 참거짓 열은 여기서 따로 짓는다(우리 venv 탐침 — 보고 2-0 f). 같음은 시험 T3 이 실제 쓰기→읽기와
`DataFrame.equals` 로 보인다.

코랩과 다른 자리(보고 표):
- 짓다 예외가 나면 `OutputsFailed` 로 남기고 시트 결과는 지킨다(코랩은 그 자리에서 실행이 죽는다 — pipeline).
- 파일 이름·경로는 모른다(`<base>_…` 는 덤프 인자). 첫 파일과 `__fixed_tmp` 바꿔치기 없이 내용 한 번.
- 후처리가 쓰지 않은 `=…` 글은 첫 왕복에서 빈다(코랩 그대로 — 최종 파일에서 빈칸, 보고 2-8 결함 후보).
"""

import math
import numbers
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final, Literal, cast

import numpy as np
import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.activity import COLS_TO_DROP, ActivityRun
from esgapi.inventory.engines.scope3.colab_157.company_mapping import openpyxl_value
from esgapi.inventory.engines.scope3.colab_157.energy import EnergyRun, standardize_energy_sheet
from esgapi.inventory.engines.scope3.colab_157.frames import read_frame
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_str
from esgapi.inventory.engines.scope3.colab_157.product import (
    annotate_energy_match,
    calc_c11_6961,
    rename_c11_sheet,
    standardize_c14_sheet,
    standardize_product_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.purchase import (
    RowMeta,
    fix_num,
    fix_text,
    standardize_c1_sheet,
    standardize_c2_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.spend import (
    standardize_c4_spend_sheet,
    standardize_c6_spend_sheet,
    standardize_c9_spend_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.template import (
    TEMPLATE_ROW,
    SheetProcessor,
    match_sheet_processor,
    read_template_rows,
)
from esgapi.inventory.engines.scope3.colab_157.transport import standardize_c4_dist_sheet, standardize_c9_dist_sheet
from esgapi.inventory.engines.scope3.colab_157.travel import standardize_c6_dist_sheet, standardize_c7_sheet
from esgapi.inventory.engines.scope3.colab_157.waste import standardize_c5_sheet
from esgapi.inventory.tools.scope3_sheets.grid import (
    Cell as GridCell,
)
from esgapi.inventory.tools.scope3_sheets.grid import (
    CellAddress,
    CellRange,
    FormulaCell,
    NumberCell,
    Sheet,
    TextCell,
    Workbook,
    column_letters,
    parse_address,
    parse_range,
)

type Cell = str | bool | int | float | None


@dataclass(frozen=True)
class ResultSheet:
    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]  # 열 차례 = columns


@dataclass(frozen=True)
class CellWrite:
    sheet: str
    row: int  # 1부터. 병합이면 이미 왼쪽 위
    column: int
    value: int | float


FilledStatus = Literal["filled", "no_result", "standardize_failed", "empty", "no_gray_columns"]


@dataclass(frozen=True)
class FilledSheet:
    """`build_filled_template` 의 시트 하나가 간 갈래(코드와 1:1). 처리 대상이 아닌 시트(`match is None`)는 없다."""

    sheet: str
    status: FilledStatus
    filled: int  # 코랩 `filled_count`(`[filled-template] … n칸 채움`)
    pairing: Literal["note", "position"] | None
    unmatched_results: int  # 코랩 `[주의] … 매칭 안 된 결과 행 n개`(`:9452`) — 비고 짝에서만


@dataclass(frozen=True)
class OutputFiles:
    result: tuple[ResultSheet, ...]
    writes: tuple[CellWrite, ...]  # 코랩 `_set_cell_value` 부름 차례. 같은 칸에 두 번 쓰면 뒤가 이긴다
    filled_sheets: tuple[FilledSheet, ...]


@dataclass(frozen=True)
class OutputsFailed:
    error: str
    kind: Literal["outputs_failed"] = "outputs_failed"


@dataclass(frozen=True)
class ProcessedPart:
    """결과 시트에 이어 붙는 처리된 템플릿 시트 하나(pipeline 의 `ProcessedSheet` 와 그 처리 때 줄)."""

    sheet: str
    processor: SheetProcessor
    frame: pd.DataFrame  # 후처리 뒤(`ProcessedSheet.frame`)
    metas: tuple[object, ...]
    before: tuple[dict[str, object], ...] | None = None  # C6·C7·C11·C14 의 처리 때 줄. 그 밖은 frame 이 처리 때 값


@dataclass(frozen=True)
class Runs:
    """표준화를 다시 돌 때 쓰는 실행 하나의 LLM·캐시(코랩 lru_cache — 처리 때와 같은 것)."""

    activity: ActivityRun
    energy: EnergyRun


# ── 결과 파일 ──

# 코랩 `out_sheet_name_map`(`:6205-6220`) = `_OUT_SHEET_NAME_MAP`(`:9337`)
OUT_SHEET_NAME_MAP: Final[dict[str, str]] = {
    "Category1": "C1_구매품서비스",
    "Category2": "C2_자본재",
    "Category3": "C3_연료에너지",
    "Category4": "C4_업스트림운송",
    "Category5": "C5_사업장폐기물",
    "Category6": "C6_출장",
    "Category7": "C7_통근",
    "Category8": "C8_임차자산",
    "Category9": "C9_다운스트림운송",
    "Category11": "C11_판매제품사용",
    "Category12": "C12_판매제품폐기",
    "Category13": "C13_임대자산",
    "Category14": "C14_프랜차이즈",
    "Category15": "C15_투자",
}

# 후처리가 쓰는 열(코랩 코드 차례). `.at[idx, k] = v`·열 대입은 **문장이 실행되면** 값이 None 이어도 열을 끝에 붙인다.
# 실행 술어가 줄의 값에 달린 것은 둘뿐 — C14 `if usage is not None`(사용량)·C11/C14 `if unit_note:`(단위환산비고).
# `_fix_result_c1_c2`(`:8799-8818`) — 시트 조건 「구매금액」·「배출계수」 열이 있으면 열째
C1_C2_WRITES: Final = ("배출량(kgCO2e)", "배출량(tCO2e)", "배출량", "배출계수기준컬럼", "배출계수단위", "계산식")
# `_fix_result_c6`(`:8821-8842`): Distance 갈래 `:8832-8836`, Spend 갈래 `calc_travel_spend_emission`(`:8641`)의 키
C6_DISTANCE_WRITES: Final = ("배출량(tCO2e)", "배출량", "출장비용", "거리왕복계수", "계산식")
C6_SPEND_EARLY_WRITES: Final = ("배출량(tCO2e)", "Spend방식")  # 출장비용이 없을 때의 이른 반환(`:8644`)
C6_SPEND_WRITES: Final = (
    "배출량(tCO2e)", "배출량", "Spend방식", "EF_DB", "NAICS", "배출계수", "배출계수단위", "계산식",
)  # fmt: skip
C6_ALWAYS: Final = "정규화이동수단"  # `:8842`
# `_fix_result_c7`(`:8845-8859`) — 줄마다 늘
C7_WRITES: Final = (
    "평균통근거리(km)",
    "배출계수",
    "배출량(tCO2e)",
    "배출량",
    "거리왕복계수",
    "정규화이동수단",
    "계산식",
)
# C11 `standardize_c11_sheet`(`:8720-8754`) — 줄 사본에 쓰고 `pd.DataFrame(rows)`(열 = 처음 나온 차례 합집합)
UNIT_NOTE: Final = "단위환산비고"
C11_WRITES: Final = (
    "사용기간(년)",
    "총사용량",
    "배출계수(kgCO2eq/단위)",
    "EF단위",
    "EF매핑명",
    UNIT_NOTE,
    "배출량(tCO2e)",
)
# C14 `_fix_result_energy_sheet`(`:8862-8875`, usage_col 「사용량」)
USAGE: Final = "사용량"
C14_WRITES: Final = (USAGE, "배출계수(kgCO2eq/단위)", "EF단위", "EF매핑명", UNIT_NOTE, "배출량(tCO2e)", "계산식")
VALUE_PREDICATED: Final = frozenset({USAGE, UNIT_NOTE})  # 값이 비지 않을 때만 실행되는 쓰기
PostKind = Literal["c1_c2", "c6", "c7", "c11", "c14"]
POST_KINDS: Final[dict[str, PostKind]] = {
    "Category1": "c1_c2",
    "Category2": "c1_c2",
    "Category6": "c6",
    "Category7": "c7",
    "Category11": "c11",
    "Category14": "c14",
}


def _is_missing(value: object) -> bool:
    if value is None or value is pd.NA:
        return True
    return isinstance(value, float) and math.isnan(value)


def to_cell(value: object) -> Cell:
    """frame 의 칸 값 → 파이썬 값(numpy 스칼라 → bool·int·float, NaN·빈 글 → None)."""
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, np.bool_):
        return bool(cast(object, value))
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        f = float(value)
        return None if math.isnan(f) else f
    if isinstance(value, str):
        return value or None
    raise TypeError(f"결과 파일에 쓸 수 없는 값 {type(value).__name__}: {value!r}")


# ── 왕복 흉내(openpyxl 쓰기 → pandas read_excel) ──

# openpyxl `ERROR_CODES` — 이 글은 오류 칸으로 쓰이고 pandas 는 NaN 으로 읽는다
ERROR_CODES: Final = frozenset({"#NULL!", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NUM!", "#N/A"})
# pandas 파서의 기본 참거짓 글자(우리 venv 탐침 — `True`·`TRUE` 는 bool 로 읽힘)
TRUE_TEXTS: Final = frozenset({"True", "TRUE", "true"})
FALSE_TEXTS: Final = frozenset({"False", "FALSE", "false"})
_BOOL_PLACEHOLDER: Final = TextCell("TRUE")


def _number_cell(value: int | float) -> GridCell:
    if isinstance(value, float) and math.isinf(value):
        return TextCell("inf" if value > 0 else "-inf")  # pandas `inf_rep`
    xml = format(value, ".16g")  # openpyxl `safe_string` 의 `"%.16g" %`(정수도)와 같은 글자 — S3C-r1 2-0 i
    exact = Decimal(xml) if any(c in xml for c in ".eE") else Decimal(int(xml))
    return NumberCell(xml, format(exact.normalize(), "f"))


def _written(value: Cell) -> GridCell | None:
    """칸 하나가 openpyxl 로 쓰인 꼴(None = 빈 칸)."""
    if value is None or isinstance(value, bool):
        return _BOOL_PLACEHOLDER if isinstance(value, bool) else None
    if isinstance(value, int | float):
        return None if isinstance(value, float) and math.isnan(value) else _number_cell(value)
    if value == "" or value in ERROR_CODES:
        return None
    if len(value) > 1 and value.startswith("="):
        return FormulaCell(value[1:], None, None)  # 수식 칸 — 저장 값이 없어 다시 읽으면 빔
    return TextCell(value)


def _bool_column(values: list[object]) -> "pd.Series[Any]":
    """파이썬 bool 이 든 열을 pandas 가 읽는 꼴(탐침: bool 만 → bool, + 빔 → float64, + 수 → 수,
    + 글 → object 그대로)."""
    present = [v for v in values if not _is_missing(v)]
    others = [v for v in present if not isinstance(v, bool)]
    missing = len(present) < len(values)
    if not others:
        if not missing:
            return pd.Series(values, dtype=bool)
        return pd.Series([math.nan if _is_missing(v) else float(bool(v)) for v in values], dtype="float64")
    if all(isinstance(v, int | float) for v in others):
        numeric = [math.nan if _is_missing(v) else (int(v) if isinstance(v, bool) else v) for v in values]
        return pd.to_numeric(pd.Series(numeric, dtype=object))
    return pd.Series([math.nan if _is_missing(v) else v for v in values], dtype=object)


def _text_bool_column(series: "pd.Series[Any]") -> "pd.Series[Any] | None":
    """참거짓 글자만 든 글 열(frames 가 흉내 내지 않음): 빔이 없으면 bool, 있으면 object(bool·NaN). 아니면 None."""
    present = [v for v in series if not _is_missing(v)]
    if not present or not all(isinstance(v, str) and (v in TRUE_TEXTS or v in FALSE_TEXTS) for v in present):
        return None
    flags = [math.nan if _is_missing(v) else v in TRUE_TEXTS for v in series]
    if len(present) == len(series):
        return pd.Series(flags, dtype=bool)
    return pd.Series(flags, dtype=object)


def reread(columns: Sequence[str], rows: Sequence[Sequence[Cell]]) -> pd.DataFrame:
    """`df.to_excel(index=False)`(openpyxl) 로 쓴 시트를 `pd.read_excel(sheet_name=None)` 으로 다시 읽은 frame."""
    cells: dict[str, GridCell] = {}
    for c, name in enumerate(columns, start=1):
        header = _written(name)
        if header is not None:
            cells[f"{column_letters(c)}1"] = header
    for r, row in enumerate(rows, start=2):
        for c, value in enumerate(row, start=1):
            written = _written(value)
            if written is not None:
                cells[f"{column_letters(c)}{r}"] = written
    frame = read_frame(Sheet("결과", cells, (), ()), header=0)
    for position in range(min(len(columns), frame.shape[1])):
        column = frame.columns[position]
        original = [row[position] for row in rows[: len(frame)]]
        if any(isinstance(v, bool) for v in original):
            read = list(frame.iloc[:, position])
            merged: list[object] = [v if isinstance(v, bool) else read[i] for i, v in enumerate(original)]
            frame[column] = _bool_column(merged).to_numpy()
            continue
        text_bool = _text_bool_column(frame.iloc[:, position])
        if text_bool is not None:
            frame[column] = text_bool.to_numpy()
    return frame


def _frame_cells(frame: pd.DataFrame) -> list[list[Cell]]:
    return [[to_cell(v) for v in row] for row in frame.itertuples(index=False, name=None)]


# ── 결과 시트 하나: b(첫 파일) → 첫 왕복 → 후처리(c) ──


def _before_rows(part: ProcessedPart) -> list[dict[str, object]]:
    if part.before is not None:
        return [dict(r) for r in part.before]
    return [{str(k): v for k, v in r.items()} for r in part.frame.to_dict(orient="records")]


# C11 처리 때(`:7613`): `:6961` 이 줄 Series 로 frame 을 지은 **뒤** `annotate_energy_mapping_columns`(`:7583`)가
# 매핑 칸 셋을 붙이고 그 뒤에 자동카테고리·출처시트. product.py 는 한 줄 dict 에 다 넣고 frame 을 지어 줄마다 다른
# 칸(`if unit_note:` 의 단위환산비고)이 끝으로 밀린다 — 결과 파일 열 차례만 코랩 꼴로 다시 센다(값·줄 대조와 무관).
C11_LATE_COLUMNS: Final = ("EF매핑명", "EF매핑방식", "EF매핑점수", "자동카테고리", "출처시트")


def _two_stage_order(rows: Sequence[dict[str, object]], late: Sequence[str]) -> list[str]:
    order = dict.fromkeys(k for r in rows for k in r if k not in late)
    order.update(dict.fromkeys(k for r in rows for k in r if k in late))
    return list(order)


def _c1_c2_absent_before(metas: Sequence[object]) -> set[str]:
    """C1·C2 의 처리 때 frame(코랩 `calc_category1_2_detail` `:8464` 결과)에서 전부 빈 열 — purchase.py 는 후처리한
    frame 만 남기므로 줄 메타(금액·후보 계수)로 센다. 후처리가 덮는 열 가운데 빌 수 있는 것은 배출량 셋과
    추천 예상 넷."""
    trio = ("배출량(kgCO2e)", "배출량", "배출량(tCO2e)")
    present: set[str] = set()
    for meta in metas:
        if not isinstance(meta, RowMeta):
            raise TypeError(f"C1·C2 줄 메타가 아니다: {type(meta).__name__}")
        spend = fix_num(meta.spend.amount_krw)
        if spend is None:
            continue
        cands = meta.candidates
        if cands and fix_num(cands[0].ef) is not None:
            present.update(trio)
        for i in range(1, 5):
            if i < len(cands) and fix_num(cands[i].ef) is not None:
                present.add(f"추천EF{i}_예상배출량(tCO2e)")
    return {*trio, *(f"추천EF{i}_예상배출량(tCO2e)" for i in range(1, 5))} - present


def _first_file_columns(frames: list[pd.DataFrame], absent: set[str]) -> list[str]:
    """`pd.concat` 합집합 → `COLS_TO_DROP`·우리 줄 번호 열 → `notna().any()`(`:6238-6243`)."""
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return [
        str(c)
        for c in merged.columns
        if c not in COLS_TO_DROP and c != TEMPLATE_ROW and str(c) not in absent and bool(merged[c].notna().any())
    ]


def _row_writes(kind: PostKind, row: "pd.Series[Any]", columns: list[str]) -> tuple[str, ...]:
    """후처리가 이 줄에서 실행하는 쓰기의 열(코드 차례). 값 술어(사용량·단위환산비고)는 부르는 쪽이 값으로 거른다."""
    if kind == "c7":
        return C7_WRITES
    if kind == "c11":
        return C11_WRITES
    if kind == "c14":
        return C14_WRITES
    if kind == "c1_c2":
        if "구매금액" not in columns or "배출계수" not in columns:
            return ()
        extra = tuple(f"추천EF{i}_예상배출량(tCO2e)" for i in range(1, 5) if f"추천EF{i}_배출계수" in columns)
        return C1_C2_WRITES + extra
    method = fix_text(row.get("계산방식"))  # `:8823`
    if method == "Distance":
        return (*C6_DISTANCE_WRITES, C6_ALWAYS)
    if method == "Spend":
        # `:8642` 의 `or` 사슬 그대로(NaN 은 참)
        spend = fix_num(row.get("출장비용") or row.get("월출장비용") or row.get("연간출장비용(원)"))
        return (*(C6_SPEND_EARLY_WRITES if spend is None else C6_SPEND_WRITES), C6_ALWAYS)
    return (C6_ALWAYS,)


def build_result_sheet(category: str, parts: Sequence[ProcessedPart], post_failed: bool) -> ResultSheet:
    """Category 하나의 결과 시트(2-0 a·b·c·d). `parts` 는 그 Category 의 처리된 시트(템플릿 차례)."""
    before = [r for part in parts for r in _before_rows(part)]
    after = [{str(k): v for k, v in r.items()} for part in parts for r in part.frame.to_dict(orient="records")]
    if len(before) != len(after):
        raise ValueError(f"{category}: 처리 때 줄 {len(before)} 와 후처리 뒤 줄 {len(after)} 가 다르다")
    kind = POST_KINDS.get(category)
    absent: set[str] = _c1_c2_absent_before([m for p in parts for m in p.metas]) if kind == "c1_c2" else set()
    frames = [pd.DataFrame(_before_rows(part)) for part in parts]
    if category == "Category11":
        frames = [f[_two_stage_order(_before_rows(p), C11_LATE_COLUMNS)] for f, p in zip(frames, parts, strict=True)]
    columns = _first_file_columns(frames, absent)
    first = reread(columns, [[to_cell(r.get(c)) for c in columns] for r in before])  # 첫 왕복(`:8882`)
    if len(first) != len(before):
        raise ValueError(f"{category}: 첫 왕복에서 줄 수가 바뀐다({len(before)} → {len(first)})")
    values = _frame_cells(first)
    if kind is None or post_failed:  # 후처리 없음·예외(`:8903-8905`) — 다시 읽은 그대로 다시 쓴다
        return ResultSheet(OUT_SHEET_NAME_MAP[category][:31], tuple(columns), tuple(tuple(v) for v in values))
    out_columns = list(columns)
    touched: list[set[str]] = []
    for i, (_, row) in enumerate(first.iterrows()):
        done: set[str] = set()
        for name in _row_writes(kind, row, out_columns):
            if name in VALUE_PREDICATED and to_cell(after[i].get(name)) is None:
                continue
            if name not in out_columns:
                out_columns.append(name)
            done.add(name)
        touched.append(done)
    rows: list[tuple[Cell, ...]] = []
    for i, base in enumerate(values):
        cells: list[Cell] = []
        for position, name in enumerate(out_columns):
            if name in touched[i]:
                cells.append(to_cell(after[i].get(name)))
            else:
                cells.append(base[position] if position < len(columns) else None)
        rows.append(tuple(cells))
    return ResultSheet(OUT_SHEET_NAME_MAP[category][:31], tuple(out_columns), tuple(rows))


def build_result_file(parts: Sequence[ProcessedPart], post_failed: frozenset[str]) -> tuple[ResultSheet, ...]:
    """시트 차례 = Category 가 처음 처리된 차례(`results` dict `:6194-6196`)."""
    by_category: dict[str, list[ProcessedPart]] = {}
    for part in parts:
        by_category.setdefault(part.processor.category, []).append(part)
    return tuple(build_result_sheet(cat, ps, cat in post_failed) for cat, ps in by_category.items())


# ── 채운 템플릿(셀 30) ──


class TemplateView:
    """openpyxl `load_workbook(input_file)`(data_only=False) 의 워크시트 값: 글 → 글, 수 → int·float(`_cast_number`),
    수식 → `"=" + 수식 글자`(공유 수식의 딸린 칸은 `"="` — 비었는지만 쓴다), 병합 안의 왼쪽 위 밖 칸 → None(MergedCell).
    `max_row`·`max_column` 은 마지막 값 칸(고리의 끝만 정한다)."""

    def __init__(self, sheet: Sheet) -> None:
        self.merges: list[CellRange] = []
        for text in sheet.merges:
            cells = parse_range(text)
            if isinstance(cells, CellRange):
                self.merges.append(cells)
        self.values: dict[tuple[int, int], object] = {}
        for address, cell in sheet.cells.items():
            parsed = parse_address(address)
            if not isinstance(parsed, CellAddress) or self._hidden(parsed.row, parsed.column):
                continue
            value = f"={cell.formula or ''}" if isinstance(cell, FormulaCell) else openpyxl_value(sheet, address)
            if value is not None and value != "":
                self.values[(parsed.row, parsed.column)] = value
        self.max_row = max((r for r, _ in self.values), default=1)
        self.max_column = max((c for _, c in self.values), default=1)

    def merge_of(self, row: int, column: int) -> CellRange | None:
        for cells in self.merges:
            if cells.first.row <= row <= cells.last.row and cells.first.column <= column <= cells.last.column:
                return cells
        return None

    def _hidden(self, row: int, column: int) -> bool:
        cells = self.merge_of(row, column)
        return cells is not None and (cells.first.row, cells.first.column) != (row, column)

    def value(self, row: int, column: int) -> object:
        return self.values.get((row, column))


def find_ef_em_columns(ws: TemplateView, max_scan_row: int = 30) -> tuple[int, int, int, str] | None:
    """`_find_ef_em_columns`(`:9214`): 줄 안 마지막 「배출계수」·「배출량」 칸(`elif` — 둘 다 든 글은 배출계수),
    머리 끝 = 두 머리 칸이 든 병합의 끝 줄 가운데 큰 것."""
    for r in range(1, min(max_scan_row, ws.max_row) + 1):
        ef_col = em_col = 0
        ef_header_text = ""
        for c in range(1, ws.max_column + 1):
            v = ws.value(r, c)
            if isinstance(v, str):
                if "배출계수" in v:
                    ef_col, ef_header_text = c, v
                elif "배출량" in v:
                    em_col = c
        if ef_col and em_col:
            header_end = r
            for col in (ef_col, em_col):
                cells = ws.merge_of(r, col)
                if cells is not None:
                    header_end = max(header_end, cells.last.row)
            return header_end, ef_col, em_col, ef_header_text
    return None


def ef_unit_scale_factor(header_text: str) -> float:
    """`_ef_unit_scale_factor`(`:9245`)."""
    t_compact = str(header_text or "").replace(" ", "").lower()
    if "kgco2e" in t_compact or "kgco2eq" in t_compact:
        return 1.0
    if "tco2e" in t_compact or "tco2eq" in t_compact:
        return 1.0 / 1000.0
    return 1.0


def find_note_column(ws: TemplateView, max_scan_row: int = 30) -> int | None:
    """`_find_note_column`(`:9264`): 15자 이하(strip) 「비고」·「설명」·「적요」 칸."""
    for r in range(1, min(max_scan_row, ws.max_row) + 1):
        for c in range(1, ws.max_column + 1):
            v = ws.value(r, c)
            if isinstance(v, str) and len(v.strip()) <= 15 and ("비고" in v or "설명" in v or "적요" in v):
                return c
    return None


def find_data_rows(ws: TemplateView, header_end_row: int, n_needed: int, scan_max_col: int) -> list[int]:
    """`_find_data_rows`(`:9277`)."""
    rows: list[int] = []
    r = header_end_row + 1
    while len(rows) < n_needed and r <= ws.max_row:
        vals = [ws.value(r, c) for c in range(1, scan_max_col + 1)]
        if any(v is not None and str(v).strip() != "" for v in vals):
            rows.append(r)
        r += 1
    return rows


# `:9293`
EF_META_COLS: Final = frozenset(
    {"배출계수기준연도", "배출계수기준컬럼", "배출계수단위", "EF단위", "EF매핑명", "EF매핑방식", "EF매핑점수"}
)


def _is_number(v: object) -> bool:
    """코랩 `isinstance(v, (int, float)) and pd.notnull(v) and not isinstance(v, bool)` — numpy 정수는 int 가 아니다.
    int64 열이 행 꺼냄에서 `np.int64` 로 남아 빔이 되는 꼴은 pandas 2.3.3(코랩 쪽)·3.0.6 같음 — r1 2-0 h."""
    return isinstance(v, int | float) and not isinstance(v, bool) and bool(pd.notnull(v))


def extract_ef_em(row: "pd.Series[Any]") -> tuple[Any, Any]:
    """`_extract_ef_em`(`:9296`)."""
    ef_val = None
    for c in row.index:
        cs = str(c)
        if cs in EF_META_COLS:
            continue
        if "배출계수" in cs or cs == "EF(kgCO2e/KRW)":
            v = row.get(c)
            if _is_number(v):
                ef_val = v
                break
    priority = [c for c in row.index if str(c) == "배출량(tCO2e)"]
    priority += [c for c in row.index if str(c) == "배출량"]
    priority += [
        c
        for c in row.index
        if "배출량" in str(c)
        and "kgCO2e" not in str(c)
        and "예상" not in str(c)
        and "추천" not in str(c)
        and str(c) not in ("배출량(tCO2e)", "배출량")
    ]
    em_val = None
    for c in priority:
        v = row.get(c)
        if _is_number(v):
            em_val = v
            break
    return ef_val, em_val


def find_result_note_column(df: pd.DataFrame) -> object:
    """`_find_result_note_column`(`:9328`)."""
    for c in df.columns:
        cs = str(c)
        if "비고" in cs or "설명" in cs or "적요" in cs:
            return c
    return None


def _write_value(value: Any) -> int | float:
    return int(value) if isinstance(value, numbers.Integral) else float(value)


class CellWriter:
    def __init__(self, sheet: str, ws: TemplateView) -> None:
        self.sheet, self.ws = sheet, ws
        self.writes: list[CellWrite] = []

    def set(self, row: int, column: int, value: Any) -> None:
        """`_set_cell_value`(`:9201`): None 이면 안 씀, 병합 칸은 왼쪽 위로(병합을 못 찾는 경우는 grid 에 없다)."""
        if value is None:
            return
        cells = self.ws.merge_of(row, column)
        if cells is not None:
            row, column = cells.first.row, cells.first.column
        self.writes.append(CellWrite(self.sheet, row, column, _write_value(value)))


def _fill_row(writer: CellWriter, r: int, ef_col: int, em_col: int, scale: float, match_row: "pd.Series[Any]") -> int:
    ef_val, em_val = extract_ef_em(match_row)
    count = 0
    if ef_val is not None:
        writer.set(r, ef_col, ef_val * scale)  # 곱셈(`:9431`) — 늘 float
        count += 1
    if em_val is not None:
        writer.set(r, em_col, em_val)
        count += 1
    return count


def standardize_for_cursor(runs: Runs, processor: SheetProcessor, df: pd.DataFrame) -> pd.DataFrame:
    """`std_fn(df0)`(`:9382`) — 처리 때와 같은 함수·같은 LLM·캐시(보고 2-0 e)."""
    key = processor.key
    if key == "c1":
        return standardize_c1_sheet(df)
    if key == "c2":
        return standardize_c2_sheet(df)
    if key == "c4_dist":
        return standardize_c4_dist_sheet(runs.activity.llm, runs.activity.units, df)[0]
    if key == "c9_dist":
        return standardize_c9_dist_sheet(runs.activity.llm, runs.activity.units, df)[0]
    if key == "c4_spend":
        return standardize_c4_spend_sheet(df)
    if key == "c9_spend":
        return standardize_c9_spend_sheet(df)
    if key == "c6_spend":
        return standardize_c6_spend_sheet(df)
    if key == "c6_dist":
        return standardize_c6_dist_sheet(df)
    if key == "c7":
        return standardize_c7_sheet(df)
    if key == "c5":
        return standardize_c5_sheet(df)
    if key in ("c12", "c15"):
        return standardize_product_sheet(df, key)
    if key == "c11":  # `:7613` = `:6961`(rename + 줄 셈) + `annotate_energy_mapping_columns`
        df = rename_c11_sheet(df)
        for _, row in df.iterrows():
            calc_c11_6961(runs.energy, row)
            annotate_energy_match(runs.energy, row, ("에너지명", "에너지원"))
        return df
    if key == "c14":  # `:7623` = `:5590` + annotate
        df = standardize_c14_sheet(df)
        for _, row in df.iterrows():
            annotate_energy_match(runs.energy, row, ("에너지원", "연료 종류"))
        return df
    return standardize_energy_sheet(df, key)


Standardize = Callable[[SheetProcessor, pd.DataFrame], pd.DataFrame]


def build_filled_template(
    template: Workbook,
    result: Sequence[ResultSheet],
    standardize: Standardize,
    *,
    reraise: Callable[[BaseException], bool] | None = None,
) -> tuple[tuple[CellWrite, ...], tuple[FilledSheet, ...]]:
    """`build_filled_template`(`:9353-9469`). 결과 시트는 둘째 왕복(`:9360`)으로 다시 읽은 frame 으로 본다.

    reraise 는 표준화 실패 자리가 다시 던질지의 판별이다(S3L1 — 표준화가 단위 환산 LLM 을 부른다). None = BASE.
    """
    result_sheets = {sheet.name: reread(sheet.columns, sheet.rows) for sheet in result}
    cursors = dict.fromkeys(OUT_SHEET_NAME_MAP, 0)
    writes: list[CellWrite] = []
    reports: list[FilledSheet] = []
    for sheet in template.sheets:
        processor = match_sheet_processor(sheet.name)
        if processor is None:
            continue
        category = processor.category
        out_name = OUT_SHEET_NAME_MAP.get(category)
        if out_name is None or out_name not in result_sheets:
            reports.append(FilledSheet(sheet.name, "no_result", 0, None, 0))
            continue
        try:
            df0 = read_template_rows(sheet)
            if df0.empty:
                reports.append(FilledSheet(sheet.name, "empty", 0, None, 0))
                continue
            df0 = standardize(processor, df0)
        except Exception as error:  # 코랩 `[filled-template][skip] … 표준화 실패`
            if reraise is not None and reraise(error):
                raise
            reports.append(FilledSheet(sheet.name, "standardize_failed", 0, None, 0))
            continue
        n = len(df0)
        start = cursors.get(category, 0)
        end = start + n
        matched = result_sheets[out_name].iloc[start:end].copy()
        cursors[category] = end
        if matched.empty:  # 코랩은 로그 없이 넘긴다
            reports.append(FilledSheet(sheet.name, "filled", 0, None, 0))
            continue
        ws = TemplateView(sheet)
        found = find_ef_em_columns(ws)
        if found is None:
            reports.append(FilledSheet(sheet.name, "no_gray_columns", 0, None, 0))
            continue
        header_end, ef_col, em_col, ef_header_text = found
        scale = ef_unit_scale_factor(ef_header_text)
        data_rows = find_data_rows(ws, header_end, max(len(matched), 500), em_col)
        data_rows = data_rows[:n] if len(data_rows) > n else data_rows
        note_col_ws = find_note_column(ws, header_end)
        note_col_df = find_result_note_column(matched)
        writer = CellWriter(sheet.name, ws)
        filled = 0
        if note_col_ws and note_col_df is not None:
            used: set[object] = set()
            unmatched_rows: list[int] = []
            notes = colab_str(matched[note_col_df]).str.strip()
            for r in data_rows:
                note_val = ws.value(r, note_col_ws)
                note_key = str(note_val).strip() if note_val is not None else ""
                match_row: pd.Series[Any] | None = None
                if note_key:
                    cand = [i for i in matched.index[notes == note_key] if i not in used]
                    if cand:
                        match_row = cast("pd.Series[Any]", matched.loc[cand[0]])
                        used.add(cand[0])
                if match_row is None:
                    unmatched_rows.append(r)
                    continue
                filled += _fill_row(writer, r, ef_col, em_col, scale, match_row)
            leftover = [i for i in matched.index if i not in used]
            if unmatched_rows and leftover:
                for r, i in zip(unmatched_rows, leftover, strict=False):
                    used.add(i)
                    filled += _fill_row(writer, r, ef_col, em_col, scale, cast("pd.Series[Any]", matched.loc[i]))
            unmatched = len(matched) - len(used) if len(used) < len(matched) else 0
            reports.append(FilledSheet(sheet.name, "filled", filled, "note", unmatched))
        else:
            for i, r in enumerate(data_rows):
                if i >= len(matched):
                    break
                filled += _fill_row(writer, r, ef_col, em_col, scale, matched.iloc[i])
            reports.append(FilledSheet(sheet.name, "filled", filled, "position", 0))
        writes.extend(writer.writes)
    return tuple(writes), tuple(reports)


def build_outputs(
    template: Workbook, parts: Sequence[ProcessedPart], post_failed: frozenset[str], runs: Runs
) -> OutputFiles:
    """두 파일의 내용. 예외는 밖으로(pipeline 이 `OutputsFailed` 로 남긴다)."""
    result = build_result_file(parts, post_failed)
    writes, filled = build_filled_template(
        template, result, lambda p, df: standardize_for_cursor(runs, p, df), reraise=runs.activity.llm.reraise
    )
    return OutputFiles(result, writes, filled)
