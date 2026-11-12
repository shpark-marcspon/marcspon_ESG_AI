"""Scope 3 데이터 엑셀을 짓는 순수 도구(밴드 S3D1 ① — 결정 MARC-ENT-592 · 442, 발주서 Q1~Q11·critic r2).

    build_export(ExportBook)       요약 시트 「Scope 3 배출량」 + 카테고리 시트 열넷(이름 = 엔진 OUT_SHEET_NAME_MAP)
    export_file_name(year, company)  `{해}_{회사}_Scope3_데이터.xlsx`(scope12 꼴 — 이름 안 금지 글자는 `_`)
    category_rows(...)             카테고리 하나의 「지금 줄」(제외·계수 고침 덧씌움) — 시트 합·생물기원 합의 한 재료

화면 상세 표(웹 entities/ghg-scope3 의 server.ts `rowOf`·`detailOf`·`inputOf` + model/detail.ts `layoutOf`·`cellOf`)와
같은 값을 낸다. 표시 글·열 차례는 `scope3_xlsx_labels.json` 한 곳(웹 상수와 같은 글자 — 웹 vitest
pages/ghg-scope3/ui/xlsxLabels.test.ts 가 대조, critic M1·R1·R5). 화면과 다른 것은 셋뿐이다:
  - 수 칸은 수(Q6 — parseNumber 꼴 글자만 Decimal, 서식 소수 6자리). 단위는 그 열 바로 뒤의 글 칸 「<머리> 단위」(C0 3).
  - 비율·FCF 는 엑셀 백분율 칸(값 0~1, 서식 0.0% — C0 4). 비율 = 줄 / 그 시트 합(제외 줄은 빈 칸).
  - 엑셀에만 있는 열: 「시트」·「제외」(앞)와 「수정」(끝) — Y 또는 빈 칸(Q2).
평범한 dataclass·Mapping 만 받는다 — django·esgapi 를 import 하지 않는다(순수 시험이 단언).

★ 같은 입력 → 같은 바이트(scope12_xlsx 의 `_restamp` 꼴을 옮겨 적음). 글 칸은 늘 글 칸(`data_type="s"`), 수 칸은
  `format(d, "f")` + `data_type="n"`(scope12_xlsx 머리 주석의 까닭 그대로).
"""

import io
import json
import re
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from importlib import resources
from typing import Final, cast

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.worksheet import Worksheet

MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FIXED_DATE: Final = (1980, 1, 1, 0, 0, 0)
FIXED_STAMP: Final = b"1980-01-01T00:00:00Z"
NUMBER_FORMAT: Final = "#,##0.000000"  # Q6 — Scope 3 에는 자릿수 재료가 없어 고정
PERCENT_FORMAT: Final = "0.0%"
_SUM_PRECISION: Final = 60  # utils/entries.py sum_or_none 과 같은 자릿수
_NUMBER: Final = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")  # 웹 parseNumber 의 NUMBER_TEXT
_LAYOUT_HEAD: Final = re.compile(r"(?<![a-z0-9])c(\d{1,2})(?:-(\d))?(?!\d)", re.IGNORECASE)  # 웹 layoutOf
_ROW_TAIL: Final = re.compile(r"^([1-9]\d*)(?:#([1-9]\d*))?$")  # 웹 rowParts
_BAD_NAME: Final = re.compile(r'[/\\:*?"<>|\x00-\x1f\x7f]')
_HEAD_FONT: Final = Font(bold=True)
_CENTER: Final = Alignment(horizontal="center", vertical="center")
_MISSING: Final = object()  # 칸이 없음(웹의 undefined) — None(null) 과 가른다

LABELS: Final[Mapping[str, object]] = json.loads(
    resources.files(__package__).joinpath("scope3_xlsx_labels.json").read_text(encoding="utf-8")
)


def _labels(key: str) -> Mapping[str, object]:
    return cast("Mapping[str, object]", LABELS[key])


def _texts(key: str) -> Mapping[str, str]:
    return cast("Mapping[str, str]", LABELS[key])


EMISSION_UNIT: Final = cast("str", LABELS["emissionUnit"])
FACTOR_NUMERATOR: Final = cast("str", LABELS["factorNumerator"])
SHEET_LAYOUTS: Final = cast("Mapping[str, list[str]]", LABELS["sheetLayouts"])
LAYOUT_BY_KIND: Final = cast("Mapping[str, Mapping[str, str]]", LABELS["layoutByKind"])
TEXT_COLUMNS: Final = frozenset(cast("list[str]", LABELS["textColumns"]))
INPUT_COLUMNS: Final = _texts("inputColumns")
INPUT_KEYS: Final = tuple(cast("list[str]", LABELS["inputKeys"]))
OPTIONAL_INPUT_KEYS: Final = ("useMonths",)  # 웹 OPTIONAL_INPUT_KEYS
ACTIVITY_KINDS: Final = frozenset(cast("list[str]", LABELS["activityKinds"]))
ENERGY_KINDS: Final = frozenset(cast("list[str]", LABELS["energyKinds"]))
COLUMNS: Final = _texts("columns")
SHEET_COLUMNS: Final = cast("Mapping[str, Mapping[str, str]]", LABELS["sheetColumns"])
SOURCE_KINDS: Final = _texts("sourceKinds")
SOURCE_BOOKS: Final = _texts("sourceBooks")
SOURCE_SHEETS: Final = _texts("sourceSheets")
SOURCE_PURCHASE_PREFIX: Final = cast("str", LABELS["sourcePurchasePrefix"])
MODE_LABELS: Final = _texts("modeLabels")
MODE_OTHER: Final = cast("str", LABELS["modeOther"])
BIOGENIC_CATEGORIES: Final = frozenset(cast("list[str]", LABELS["biogenicCategories"]))
WORKBOOK: Final = _labels("workbook")
EMISSION_COLUMNS: Final = ("co2e", "biogenic")
PERCENT_COLUMNS: Final = ("share", "fcf")
UNIT_COLUMNS: Final = ("activity", "baseAmount", "inWeight", "factor")
"""웹 cellOf 가 단위 글자를 붙이는 수 칸 — 엑셀은 바로 뒤에 단위 글 칸을 둔다(C0 3)."""
TAIL_ORDER: Final = ("co2e", "share", "biogenic", "factor", "fcf", "source")
GENERIC: Final = "generic"


# ── 입력 꼴 ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FixedFactor:
    """계수 사건(recommended·custom — applied 는 덧씌우지 않는다). 글자는 사건 그대로."""

    value: str | None
    unit: str | None
    source: str | None
    co2e: str | None
    biogenic_co2e: str | None


@dataclass(frozen=True)
class EngineSheet:
    """결과 본문의 processed 시트 하나(줄은 본문 그대로 — 고치지 않는다)."""

    name: str
    rows: Sequence[object]


@dataclass(frozen=True)
class CategoryBook:
    """카테고리 하나: 요약 줄 재료(total·sheets·failed — 서버 category_value) + 지금 결과 실행의 시트와 덧판."""

    category: str  # C1 …
    name: str  # 카테고리 이름(CATEGORY_NAMES)
    sheet_name: str  # 엑셀 시트 이름(엔진 OUT_SHEET_NAME_MAP)
    total: Decimal | None
    sheets: int
    failed_sheets: int
    engine_sheets: Sequence[EngineSheet] = ()
    excluded: frozenset[str] = frozenset()
    fixed: Mapping[str, FixedFactor] = field(default_factory=dict[str, FixedFactor])


@dataclass(frozen=True)
class ExportBook:
    year: int
    categories: Sequence[CategoryBook]


# ── 수·글 ───────────────────────────────────────────────────────────


def number(text: object) -> Decimal | None:
    """수 글자 → Decimal(웹 parseNumber 꼴만 — nan·inf·빈 글자는 None). -0 은 0."""
    if not isinstance(text, str) or not _NUMBER.fullmatch(text):
        return None
    value = Decimal(text)
    return Decimal(0) if value == 0 else value


def _sum(values: Sequence[Decimal | None]) -> Decimal | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    with localcontext(prec=_SUM_PRECISION):
        return sum(present, Decimal(0))


def factor_unit_of(unit: str | None) -> str | None:
    """웹 factorUnitOf: 「/」 없는 단위 글자면 앞에 「kgCO2eq/」. 「/」가 있거나 비면 그대로."""
    if unit is None or unit.strip() == "" or "/" in unit:
        return unit
    return f"{FACTOR_NUMERATOR}/{unit.strip()}"


def raw_source_text(text: str) -> str:
    """웹 rawSourceText: 서버 출처 글(시트 이름) → 화면 글. 표에 없는 글은 그대로."""
    sheet = text.strip()
    if sheet in SOURCE_SHEETS:
        return SOURCE_SHEETS[sheet]
    if sheet.startswith(SOURCE_PURCHASE_PREFIX):
        return SOURCE_BOOKS["usepa"]
    return text


def mode_text(value: str) -> str:
    """웹 modeText: 정규화 코드 → 이름표, 모르면 「기타」."""
    return MODE_LABELS.get(value, MODE_OTHER)


def row_number(row_id: str | None) -> str | None:
    """웹 rowNumber: 「시트!12」 → 「12」, 「시트!12#2」 → 「12-2」. 꼴이 아니면 None."""
    if row_id is None or "!" not in row_id:
        return None
    match = _ROW_TAIL.fullmatch(row_id[row_id.rindex("!") + 1 :])
    if match is None:
        return None
    nth = match.group(2) or "1"
    return match.group(1) if nth == "1" else f"{match.group(1)}-{nth}"


def _row_order(row_id: str | None) -> tuple[int, int] | None:
    if row_id is None or "!" not in row_id:
        return None
    match = _ROW_TAIL.fullmatch(row_id[row_id.rindex("!") + 1 :])
    return None if match is None else (int(match.group(1)), int(match.group(2) or "1"))


def screen_order(rows: Sequence["Row"]) -> tuple["Row", ...]:
    """웹 sortRows(rows, null): 행 번호(엑셀 줄, 그다음 #n) 차례, 같으면 서버 차례. 행 번호 없는 줄은 뒤(서버 차례)."""
    keyed = [(_row_order(row.row_id), index, row) for index, row in enumerate(rows)]
    keyed.sort(key=lambda item: (item[0] is None, item[0] or (0, 0), item[1]))
    return tuple(row for _, _, row in keyed)


def header_of(layout: str, column: str) -> str:
    """웹 headerOf: 시트별 글 → 공통 글. 배출량 열은 끝에 (tCO2eq)."""
    by_sheet: Mapping[str, str] = {} if layout == GENERIC else SHEET_COLUMNS.get(layout, {})
    name = by_sheet.get(column, COLUMNS[column])
    return f"{name}({EMISSION_UNIT})" if column in EMISSION_COLUMNS else name


# ── 줄 읽기(웹 server.ts 의 rowOf·detailOf·inputOf) ─────────────────


def _mapping(value: object) -> Mapping[str, object] | None:
    return cast("Mapping[str, object]", value) if isinstance(value, Mapping) else None


def _text_or_null(value: object) -> object:
    """글자나 None 이면 그 값, 아니면(칸 없음 포함) _MISSING(웹 textOrNull 의 undefined)."""
    return value if value is None or isinstance(value, str) else _MISSING


def _cells(body: object, keys: Sequence[str]) -> dict[str, str | None] | None:
    found = _mapping(body)
    if found is None:
        return None
    out: dict[str, str | None] = {}
    for key in keys:
        value = _text_or_null(found.get(key, _MISSING))
        if value is _MISSING:
            return None
        out[key] = cast("str | None", value)
    return out


def _nullable(body: object, keys: Sequence[str]) -> object:
    """웹 nullable(cellsOf): None → None, 꼴이 맞으면 칸들, 틀리거나 없으면 _MISSING."""
    if body is None:
        return None
    cells = _cells(body, keys)
    return _MISSING if cells is None else cells


def _factor(body: object, with_source: bool) -> dict[str, str | None] | None:
    cells = _cells(body, ("title", "value", "unit"))
    found = _mapping(body)
    if cells is None or found is None:
        return None
    source = found.get("source" if with_source else "sheet")
    if with_source and not isinstance(source, str):
        return None
    return {**cells, "source": source if isinstance(source, str) else None}


@dataclass(frozen=True)
class Detail:
    """웹 RowDetail 중 표 칸이 쓰는 것. shape basic 이면 나머지는 빈 값."""

    shape: str
    kind: str | None = None
    factor: Mapping[str, str | None] | None = None
    group: str | None = None
    spend: str | None = None
    activity: Mapping[str, str | None] = field(default_factory=dict[str, "str | None"])
    treatment: str | None = None
    mode: str | None = None
    distance: Mapping[str, str | None] | None = None
    fcf: str | None = None
    building_total: str | None = None
    investment: Mapping[str, str | None] | None = None


BASIC: Final = Detail(shape="basic")


def _detail(body: Mapping[str, object]) -> Detail:
    kind = body.get("kind")
    if not isinstance(body.get("originSteps"), list) or not isinstance(kind, str):
        return BASIC
    biogenic = _mapping(body.get("biogenic"))
    raw = body.get("biogenic", _MISSING)
    fcf: object = (
        _text_or_null(biogenic.get("fcf", _MISSING))
        if biogenic is not None
        else (None if raw is None or raw is _MISSING else _MISSING)
    )
    note: object = _text_or_null(biogenic.get("note", _MISSING)) if biogenic is not None else None
    if kind == "purchase":
        group = _mapping(body.get("group"))
        factor = _factor(body.get("factor"), True)
        spend = _text_or_null(body.get("spendKrw", _MISSING))
        if group is None or not isinstance(group.get("name"), str) or factor is None or spend is _MISSING:
            return BASIC
        return Detail(
            shape="purchase",
            kind=kind,
            factor=factor,
            group=cast("str", group["name"]),
            spend=cast("str | None", spend),
        )
    activity = _cells(body.get("activity"), ("value", "unit", "baseValue", "baseUnit"))
    if activity is None or fcf is _MISSING or note is _MISSING:
        return BASIC
    if kind in ACTIVITY_KINDS:
        factor = _factor(body.get("factor"), False)
        treatment = _text_or_null(body.get("treatment", _MISSING))
        mode_body = body.get("mode", _MISSING)
        mode: object = None
        if mode_body is not None:
            found = _mapping(mode_body)
            mode = found["value"] if found is not None and isinstance(found.get("value"), str) else _MISSING
        distance = _nullable(body.get("distance", _MISSING), ("km", "roundTrip", "people", "trips", "workdays"))
        if factor is None or treatment is _MISSING or mode is _MISSING or distance is _MISSING:
            return BASIC
        return Detail(
            shape="activity",
            kind=kind,
            factor=factor,
            activity=activity,
            treatment=cast("str | None", treatment),
            mode=cast("str | None", mode),
            distance=cast("Mapping[str, str | None] | None", distance),
            fcf=cast("str | None", fcf),
        )
    if kind in ENERGY_KINDS:
        factor_body = body.get("factor", _MISSING)
        factor_cells: object = None
        if factor_body is not None:
            factor_cells = _factor(factor_body, False) or _MISSING
        allocation = _nullable(body.get("allocation", _MISSING), ("buildingTotal",))
        product = _nullable(body.get("product", _MISSING), ("years",))
        investment = _nullable(body.get("investment", _MISSING), ("share", "scope1", "scope2"))
        if _MISSING in (factor_cells, allocation, product, investment):
            return BASIC
        return Detail(
            shape="energy",
            kind=kind,
            factor=cast("Mapping[str, str | None] | None", factor_cells),
            activity=activity,
            building_total=None
            if allocation is None
            else cast("Mapping[str, str | None]", allocation)["buildingTotal"],
            investment=cast("Mapping[str, str | None] | None", investment),
            fcf=cast("str | None", fcf),
        )
    return BASIC


def _input(body: object) -> dict[str, str | None] | None:
    found = _mapping(body)
    if found is None or not set(found) <= set(INPUT_KEYS):
        return None
    filled = {**found, **{key: None for key in OPTIONAL_INPUT_KEYS if key not in found}}
    return _cells(filled, INPUT_KEYS)


@dataclass(frozen=True)
class Row:
    """지금 줄 하나(웹 ResultRow + overlayRow). co2e·biogenic 은 고친 줄이면 사건 값."""

    row_id: str | None
    co2e: str | None
    biogenic: str | None
    detail: Detail
    input: Mapping[str, str | None] | None
    excluded: bool = False
    fixed: FixedFactor | None = None


def read_row(body: object, excluded: frozenset[str], fixed: Mapping[str, FixedFactor]) -> Row | None:
    """본문 줄 하나 → 지금 줄. 매핑이 아니면 None(줄 아님 — category_value 도 셈 0). 덧판 짝은 rowId."""
    found = _mapping(body)
    if found is None:
        return None
    co2e = found.get("co2e")
    biogenic = _mapping(found.get("biogenic"))
    bio = biogenic.get("biogenicCo2e") if biogenic is not None else None
    row_id = found.get("rowId")
    key = row_id if isinstance(row_id, str) else None
    edit = None if key is None else fixed.get(key)
    return Row(
        row_id=key,
        co2e=edit.co2e if edit is not None else (co2e if isinstance(co2e, str) else None),
        biogenic=edit.biogenic_co2e if edit is not None else (bio if isinstance(bio, str) else None),
        detail=_detail(found),
        input=_input(found.get("input")),
        excluded=key is not None and key in excluded,
        fixed=edit,
    )


# ── 시트 꼴·칸(웹 layoutOf·cellOf) ──────────────────────────────────


def _layout_category(layout: str) -> str:
    return f"Category{layout[1:].split('-')[0]}"


def layout_of(sheet: str, category: str, rows: Sequence[Row]) -> str:
    """웹 layoutOf: 이름 안 「c8-2」 꼴 낱말 중 그 카테고리 꼴인 첫 것 → 첫 줄 kind → generic(critic R1)."""
    for head in _LAYOUT_HEAD.finditer(sheet):
        name = f"C{head.group(1)}-{head.group(2)}" if head.group(2) else f"C{head.group(1)}"
        if name in SHEET_LAYOUTS and name != GENERIC and _layout_category(name) == category:
            return name
    for row in rows:
        if row.detail.shape == "basic" or row.detail.kind is None:
            continue
        layout = LAYOUT_BY_KIND.get(row.detail.kind, {}).get(category)
        if layout is not None:
            return layout
    return GENERIC


@dataclass(frozen=True)
class Value:
    """칸 하나: text(글) 또는 number(Decimal)·unit."""

    text: str | None = None
    number: Decimal | None = None
    unit: str | None = None
    is_number: bool = False


def _num(text: object, unit: str | None = None) -> Value:
    return Value(number=number(text), unit=unit, is_number=True)


def _txt(text: str | None) -> Value:
    return Value(text=text)


def _blank(column: str) -> Value:
    return _txt(None) if column in TEXT_COLUMNS or column == "source" else Value(is_number=True)


def _source_text(code: str | None) -> str | None:
    kind = SOURCE_KINDS.get(code) if code is not None else None
    return None if kind is None else SOURCE_BOOKS.get(kind)


def cell_of(row: Row, column: str, sheet_total: Decimal | None) -> Value:
    """웹 cellOf + cellText 의 글 바꿈(수단 이름표·출처 책 이름). 수는 Decimal, 비율·FCF 는 0~1."""
    if column == "row":
        return _txt(row_number(row.row_id))
    if column == "co2e":
        return _num(row.co2e)
    if column == "share":
        return Value(number=None if row.excluded else share_of(row.co2e, sheet_total), is_number=True)
    if column == "biogenic":
        return _num(row.biogenic)
    key = INPUT_COLUMNS.get(column)
    if key is not None:
        given = row.input
        if column == "inEnergy":
            if given is not None:
                return _txt(given["energy"])
            factor = row.detail.factor
            return _txt(None if row.detail.shape == "basic" or factor is None else factor.get("title"))
        if column in TEXT_COLUMNS:
            return _txt(None if given is None else given[key])
        unit = (given or {}).get("weightUnit") if column == "inWeight" else None
        return _num(None if given is None else given[key], unit)
    fixed = row.fixed
    if fixed is not None and column == "factor":
        return _num(fixed.value, factor_unit_of(fixed.unit))
    if fixed is not None and column == "source":
        return _txt(None if fixed.source is None else raw_source_text(fixed.source))
    detail = row.detail
    if detail.shape == "basic":
        return _blank(column)
    factor = detail.factor
    if column == "factor":
        return _num(factor.get("value"), factor_unit_of(factor.get("unit"))) if factor else Value(is_number=True)
    if column == "source":
        return _txt(_source_text(factor.get("source")) if detail.shape == "purchase" and factor else None)
    if column == "group":
        return _txt(detail.group if detail.shape == "purchase" else None)
    if column == "spendKrw":
        return _num(detail.spend if detail.shape == "purchase" else None)
    if column == "fcf":
        return Value(number=None if detail.shape == "purchase" else number(detail.fcf), is_number=True)
    if detail.shape == "purchase":
        return Value(is_number=True)
    amount = detail.activity
    if column == "activity":
        return _num(amount.get("value"), amount.get("unit"))
    if column == "baseAmount":
        return _num(amount.get("baseValue"), amount.get("baseUnit"))
    if detail.shape == "activity":
        distance = detail.distance or {}
        if column == "treatment":
            return _txt(detail.treatment)
        if column == "mode":
            return _txt(None if detail.mode is None else mode_text(detail.mode))
        if column in ("km", "roundTrip", "people", "trips", "workdays"):
            return _num(distance.get(column))
        return _blank(column)
    investment = detail.investment or {}
    if column == "buildingTotal":
        return _num(detail.building_total)
    if column == "investShare":
        return _num(investment.get("share"))
    if column in ("scope1", "scope2"):
        return _num(investment.get(column))
    return _blank(column)


def share_of(co2e: str | None, total: Decimal | None) -> Decimal | None:
    """줄 / 그 시트 합(0~1 — 웹 shareOf 의 %÷100). 합이 0·없음이거나 줄 수가 없으면 None."""
    value = number(co2e)
    if value is None or total is None or total == 0:
        return None
    with localcontext(prec=_SUM_PRECISION):
        return value / total


# ── 카테고리 셈 ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class SheetRows:
    name: str
    layout: str
    rows: tuple[Row, ...]
    total: Decimal | None
    biogenic: Decimal | None


def category_rows(book: CategoryBook) -> tuple[SheetRows, ...]:
    """카테고리의 processed 시트마다 지금 줄 · 시트 합(제외 뺌 — 웹 categorySheets) · 생물기원 합(제외 뺌)."""
    found: list[SheetRows] = []
    engine = f"Category{book.category[1:]}"
    for sheet in book.engine_sheets:
        rows = screen_order(
            [row for row in (read_row(body, book.excluded, book.fixed) for body in sheet.rows) if row is not None]
        )
        kept = [row for row in rows if not row.excluded]
        found.append(
            SheetRows(
                name=sheet.name,
                layout=layout_of(sheet.name, engine, rows),
                rows=rows,
                total=_sum([number(row.co2e) for row in kept]),
                biogenic=_sum([number(row.biogenic) for row in kept]),
            )
        )
    return tuple(found)


def biogenic_total(book: CategoryBook, sheets: Sequence[SheetRows]) -> Decimal | None:
    """요약 시트의 생물기원 합(critic R3 — category_value 가 주지 않음): C5·C12 만, 제외 줄 뺌·고친 줄은 사건 값."""
    if book.category not in BIOGENIC_CATEGORIES:
        return None
    return _sum([sheet.biogenic for sheet in sheets])


def columns_of(sheets: Sequence[SheetRows]) -> tuple[tuple[str, str], ...]:
    """카테고리 시트의 데이터 열 (열 id, 머리 글) — 시트 꼴이 여럿이면 합집합(Q4: 앞 열은 나온 차례, 꼬리는 TAIL_ORDER).
    머리는 그 열이 처음 나온 시트 꼴의 글. 시트가 없으면 generic."""
    layouts = [sheet.layout for sheet in sheets] or [GENERIC]
    heads: dict[str, str] = {}
    for layout in layouts:
        for column in SHEET_LAYOUTS[layout]:
            heads.setdefault(column, header_of(layout, column))
    front = [column for column in heads if column not in TAIL_ORDER]
    tail = [column for column in TAIL_ORDER if column in heads]
    return tuple((column, heads[column]) for column in (*front, *tail))


# ── 짓기 ────────────────────────────────────────────────────────────


def _put(sheet: Worksheet, row: int, column: int, value: str | int | Decimal | None, number_format: str = "") -> Cell:
    cell: Cell = sheet.cell(row=row, column=column)  # pyright: ignore[reportAssignmentType]
    if value is None or (isinstance(value, Decimal) and not value.is_finite()):
        return cell
    if isinstance(value, Decimal):
        cell.value = format(value, "f")
        cell.data_type = "n"
        if number_format:
            cell.number_format = number_format
    elif isinstance(value, int):
        cell.value = value
    else:
        cell.value = value
        cell.data_type = "s"  # `=` 로 시작해도 글 칸(수식 주입 0)
    return cell


def _head_row(sheet: Worksheet, heads: Sequence[str]) -> None:
    for index, text in enumerate(heads, start=1):
        cell = _put(sheet, 1, index, text)
        cell.font = _HEAD_FONT
        cell.alignment = _CENTER


def _w(key: str) -> str:
    return cast("str", WORKBOOK[key])


def summary_heads() -> tuple[str, ...]:
    head = cast("list[str]", WORKBOOK["summaryHead"])
    return (head[0], head[1], f"{head[2]}({EMISSION_UNIT})", f"{head[3]}({EMISSION_UNIT})", *head[4:])


def sheet_heads(columns: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    """카테고리 시트 머리: 시트 · 행 · 제외 · (데이터 열 — 단위 열은 바로 뒤) · 수정."""
    out = [_w("sheetHead")]
    for column, head in columns:
        out.append(head)
        if column == "row":
            out.append(_w("excludedHead"))
        if column in UNIT_COLUMNS:
            out.append(f"{head}{_w('unitSuffix')}")
    out.append(_w("editedHead"))
    return tuple(out)


def _summary(sheet: Worksheet, book: ExportBook, sheets: Mapping[str, tuple[SheetRows, ...]]) -> None:
    _head_row(sheet, summary_heads())
    line = 2
    totals: list[Decimal | None] = []
    biogenics: list[Decimal | None] = []
    for category in book.categories:
        rows = [row for found in sheets[category.category] for row in found.rows]
        biogenic = biogenic_total(category, sheets[category.category])
        totals.append(category.total)
        biogenics.append(biogenic)
        _put(sheet, line, 1, category.category)
        _put(sheet, line, 2, category.name)
        _put(sheet, line, 3, category.total, NUMBER_FORMAT)
        _put(sheet, line, 4, biogenic, NUMBER_FORMAT)
        _put(sheet, line, 5, category.sheets)
        _put(sheet, line, 6, category.failed_sheets)
        _put(sheet, line, 7, sum(1 for row in rows if row.excluded))
        _put(sheet, line, 8, sum(1 for row in rows if row.fixed is not None))
        line += 1
    _put(sheet, line, 1, _w("summaryTotal")).font = _HEAD_FONT
    _put(sheet, line, 3, _sum(totals), NUMBER_FORMAT)
    _put(sheet, line, 4, _sum(biogenics), NUMBER_FORMAT)


def _category(sheet: Worksheet, found: Sequence[SheetRows]) -> None:
    columns = columns_of(found)
    _head_row(sheet, sheet_heads(columns))
    mark = _w("mark")
    line = 2
    for block in found:
        for row in block.rows:
            at = 1
            _put(sheet, line, at, block.name)
            for column, _ in columns:
                at += 1
                value = cell_of(row, column, block.total) if column in SHEET_LAYOUTS[block.layout] else _blank(column)
                if value.is_number:
                    _put(sheet, line, at, value.number, PERCENT_FORMAT if column in PERCENT_COLUMNS else NUMBER_FORMAT)
                else:
                    _put(sheet, line, at, value.text)
                if column == "row":
                    at += 1
                    _put(sheet, line, at, mark if row.excluded else None)
                if column in UNIT_COLUMNS:
                    at += 1
                    _put(sheet, line, at, value.unit)
            _put(sheet, line, at + 1, mark if row.fixed is not None else None)
            line += 1
        _total_row(sheet, line, block, columns)
        line += 1


def _total_row(sheet: Worksheet, line: int, block: SheetRows, columns: Sequence[tuple[str, str]]) -> None:
    """시트 끝 합 줄: 시트 · 행 칸에 「시트 합계」 · 배출량·생물기원 합(제외 뺌)."""
    _put(sheet, line, 1, block.name)
    at = 1
    for column, _ in columns:
        at += 1
        if column == "row":
            _put(sheet, line, at, _w("sheetTotal")).font = _HEAD_FONT
            at += 1
        elif column == "co2e":
            _put(sheet, line, at, block.total, NUMBER_FORMAT)
        elif column == "biogenic":
            _put(sheet, line, at, block.biogenic, NUMBER_FORMAT)
        if column in UNIT_COLUMNS:
            at += 1


def build_export(book: ExportBook) -> bytes:
    """요약 시트 + 카테고리 시트(book.categories 차례). 줄 0 인 카테고리는 머리만(Q9)."""
    workbook = Workbook()
    summary = cast("Worksheet", workbook.active)
    summary.title = _w("summarySheet")
    sheets = {category.category: category_rows(category) for category in book.categories}
    _summary(summary, book, sheets)
    for category in book.categories:
        _category(workbook.create_sheet(category.sheet_name[:31]), sheets[category.category])
    return _save(workbook)


# ── 저장·이름 ───────────────────────────────────────────────────────


def _save(workbook: Workbook) -> bytes:
    workbook.properties.creator = "esgapi"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return _restamp(buffer.getvalue())


def _restamp(data: bytes) -> bytes:
    """zip 항목 시각과 문서 속성 시각을 고정해 다시 묶는다(scope12_xlsx `_restamp` 꼴 — 옮겨 적음)."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for entry in source.infolist():
            content = source.read(entry.filename)
            if entry.filename == "docProps/core.xml":
                content = re.sub(
                    rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)",
                    lambda m: m.group(1) + FIXED_STAMP + m.group(2),
                    content,
                )
            info = zipfile.ZipInfo(entry.filename, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, content)
    return out.getvalue()


def clean_part(text: str) -> str:
    return _BAD_NAME.sub("_", text)


def export_file_name(year: int, company: str) -> str:
    """`{해}_{회사이름}_Scope3_데이터.xlsx`(Q7)."""
    return f"{year}_{clean_part(company)}_Scope3_데이터.xlsx"
