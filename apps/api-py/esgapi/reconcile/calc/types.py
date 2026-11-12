"""숫자 뽑기가 내는 꼴. TS 는 `facts.ts` 와 `kinds.ts` 가 서로를 보지만 파이썬에서는 순환 import 라 꼴을 여기에 모았다.

전부 frozen dataclass 다. 목록은 튜플이다(값 후보 목록은 한 번 만들면 바뀌지 않는다).
이름은 TS 의 것을 snake_case 로 옮겼다(`unitSuffix` → `unit_suffix`). 값은 십진 문자열이다.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

# ── 표기 (notation) ──────────────────────────────────────────────────────────

# 표 칸 하나의 갈래. `value` 만 값 후보다.
CellKind = Literal[
    "blank",
    "value",  # 숫자 하나 (부호·괄호·쉼표·%·단위 접미 허용)
    "no_value_marker",  # `-`, `N/A`, `해당없음`. 0 이 아니라 「값 없음」이다
    "year",  # `FY2025`, `2025년`
    "code",  # 앞자리 0 (`04`), 조항 번호 (`6(1)`), 버전 (`1.2.3`)
    "date",  # `2025.7.1`, `2025-07-01`
    "range",  # `10~20`, `65-66`, `3~17%`
    "multi_number",  # 숫자가 둘 이상 (`116,818 15,649`)
    "text_with_digits",  # 글 속에 숫자가 섞임
    "text",
]
CELL_KINDS: tuple[CellKind, ...] = (
    "blank",
    "value",
    "no_value_marker",
    "year",
    "code",
    "date",
    "range",
    "multi_number",
    "text_with_digits",
    "text",
)

SignRule = Literal["none", "minus", "plus", "paren_negative", "triangle_negative", "triangle_ambiguous"]
SIGN_RULES: tuple[SignRule, ...] = (
    "none",
    "minus",
    "plus",
    "paren_negative",
    "triangle_negative",
    "triangle_ambiguous",
)

NotationFlag = Literal[
    "paren_negative_assumed",  # (123) 을 음수로 읽었다. 괄호 속 부분 수일 수도 있다
    "triangle_negative",  # △ 를 음수로 읽었다 (재무제표 관례)
    "sign_ambiguous",  # ▲ ▼ 는 증감 표시라 부호를 정할 수 없다
    "year_like",  # 1900~2100 의 쉼표 없는 네 자리 정수. 연도일 수 있다
    "percent_format_scaled",  # 엑셀의 퍼센트 서식 칸: 저장 값(0.123)에 100 을 곱해 % 단위의 값(12.3)으로 읽었다
]
NOTATION_FLAGS: tuple[NotationFlag, ...] = (
    "paren_negative_assumed",
    "triangle_negative",
    "sign_ambiguous",
    "year_like",
    "percent_format_scaled",
)

# 글 속 숫자 덩어리의 갈래. `value` 만 값 후보다.
TokenKind = Literal[
    "value",
    "year",  # 2025년, 2050, ’25
    "date_part",  # 3월, 15일, 2025.7.1 의 조각
    "identifier",  # Scope 1, GRI 305-1, CO2, 02-1234-5678, URL 속 숫자
    "ordinal",  # 제3조, 1차, 2단계
    "marker",  # 각주·목록 번호 `1)`, `(2)`
    "range_part",  # 10~20 의 양 끝
]
TOKEN_KINDS: tuple[TokenKind, ...] = ("value", "year", "date_part", "identifier", "ordinal", "marker", "range_part")


@dataclass(frozen=True, slots=True)
class ParsedNumber:
    value: str  # 표기 그대로의 수. 수 단위 낱말(천, 억)은 곱하지 않았다. 십진 문자열
    decimals: int  # 표시된 소수 자릿수. 반올림 허용폭의 근거다
    sign: SignRule
    percent: bool
    unit_suffix: str | None  # 숫자 뒤에 붙어 있던 단위 글자 (`%`, `명`, `만 톤`)
    flags: tuple[NotationFlag, ...]


@dataclass(frozen=True, slots=True)
class CellNotation:
    kind: CellKind
    number: ParsedNumber | None


@dataclass(frozen=True, slots=True)
class NumberToken:
    raw: str  # 원문 글자 그대로 (부호와 % 포함)
    start: int  # 원문에서의 시작·끝 (★ UTF-16 자리. JS 의 문자열 자리와 같다)
    end: int
    occurrence: int  # 같은 원문 글자가 이 글에서 몇 번째로 나온 것인지 (1부터)
    kind: TokenKind
    number: ParsedNumber | None


# ── 문서 모델에서 읽는 부분 (document.py 가 검증해 만든다) ───────────────────

BlockKind = Literal["paragraph", "table", "heading"]
TextLayer = Literal["present", "none"]
TableMethod = Literal["lines", "text", "none"]
TableStatus = Literal["ok", "low_confidence", "failed"]


@dataclass(frozen=True, slots=True)
class DocSource:
    file_name: str
    sha256: str
    page_count: int


@dataclass(frozen=True, slots=True)
class DocPage:
    page: int
    height: float
    text_layer: TextLayer


@dataclass(frozen=True, slots=True)
class DocBlock:
    id: str
    kind: BlockKind
    page: int
    bbox: tuple[float, float, float, float]
    order: int
    text: str | None
    table_id: str | None


@dataclass(frozen=True, slots=True)
class GridHeader:
    rows: tuple[int, ...]
    cols: tuple[int, ...]
    basis: str


@dataclass(frozen=True, slots=True)
class FootnoteMark:
    row: int
    col: int
    mark: str


@dataclass(frozen=True, slots=True)
class DocTable:
    id: str
    page: int
    cells: tuple[tuple[str, ...], ...]
    header: GridHeader
    method: TableMethod
    status: TableStatus
    footnote_marks: tuple[FootnoteMark, ...]


@dataclass(frozen=True, slots=True)
class DocModel:
    """검증을 통과한 문서 모델. `document.validate_document` 만 만든다(`extract_document` 는 dict 를 받지 않는다)."""

    source: DocSource
    pages: tuple[DocPage, ...]
    blocks: tuple[DocBlock, ...]
    tables: tuple[DocTable, ...]


# ── 값 후보 (facts) ──────────────────────────────────────────────────────────

GridStatus = Literal["ok", "low_confidence"]
DisplayStatus = Literal["rendered", "general_approximated", "unsupported_format"]


@dataclass(frozen=True, slots=True)
class StoredNumber:
    """엑셀 숫자 칸의 저장 값과 화면 표기. 둘이 다를 수 있어 둘 다 남긴다. (엑셀 파일을 읽는 일은 이 패키지에 없다)"""

    stored_raw: str  # 파일에 저장된 글자 그대로
    stored: str  # 저장 값의 십진 문자열 (지수 표기를 풀었다)
    format_code: str
    display: str | None  # 서식을 적용한 화면 표기. 지원하지 않는 서식이면 None
    display_status: DisplayStatus
    is_date: bool
    formula: bool


@dataclass(frozen=True, slots=True)
class Grid:
    """표 하나 또는 시트 하나의 격자."""

    id: str
    doc_id: str
    kind: Literal["pdf_table", "sheet"]
    page: int | None
    sheet: str | None
    cells: tuple[tuple[str, ...], ...]
    header: GridHeader
    status: GridStatus
    footnote_marks: tuple[FootnoteMark, ...]
    title_candidates: tuple[str, ...]  # 표 바로 앞의 글 블록(가까운 것부터 최대 3개). 제목일 수도 아닐 수도 있다
    unit_lines: tuple[str, ...]  # `단위:` 가 든 줄
    inner_headers: tuple[int, ...] | None = None  # 본문 중간의 머리글 행(추정, 정상 표만). None 이면 아직 구하지 않았다
    numeric: tuple[tuple[StoredNumber | None, ...], ...] | None = None  # 엑셀 숫자 칸. 그 밖의 칸은 None
    refs: tuple[tuple[str, ...], ...] | None = None  # 엑셀 칸 주소 (`D5`)


@dataclass(frozen=True, slots=True)
class HeaderRef:
    cell: str  # 머리글 칸의 ID (격자 안의 `r0c3`)
    text: str
    inherited: bool  # 병합 칸이라 비어 있어서 위(행 머리)나 왼쪽(열 머리)의 글자를 물려받았다. 추정이다


@dataclass(frozen=True, slots=True)
class Headers:
    row: tuple[HeaderRef, ...]
    col: tuple[HeaderRef, ...]


FactBucket = Literal[
    "table_cell",  # 표의 숫자 칸
    "table_text_cell",  # 표의 글 칸 속 숫자
    "sentence",  # 문단·제목 속 숫자
    "number_only_block",  # 숫자뿐인 블록 (도표의 숫자 등)
]
FACT_BUCKETS: tuple[FactBucket, ...] = ("table_cell", "table_text_cell", "sentence", "number_only_block")


@dataclass(frozen=True, slots=True)
class Span:
    start: int  # ★ UTF-16 자리
    end: int
    occurrence: int


@dataclass(frozen=True, slots=True)
class FactWhere:
    page: int | None
    sheet: str | None
    grid_id: str | None
    row: int | None
    col: int | None
    ref: str | None  # 엑셀 칸 주소
    block_id: str | None
    span: Span | None  # 글 속 숫자일 때: 원문에서의 자리와, 같은 글자가 몇 번째 나온 것인지


@dataclass(frozen=True, slots=True)
class Fact:
    """값 후보 하나."""

    id: str
    doc_id: str
    bucket: FactBucket
    where: FactWhere
    raw: str  # 원문 글자. 표 칸이면 칸 전체, 글 속이면 그 숫자 덩어리
    value: str  # 읽은 값 (십진 문자열). 수 단위 낱말은 곱하지 않은 표기 그대로의 수
    decimals: int
    sign: SignRule
    percent: bool
    unit_suffix: str | None
    flags: tuple[NotationFlag, ...]
    footnote_marks: tuple[str, ...]
    table_status: GridStatus | None  # 표에서 나온 숫자면 그 표의 추출 상태
    headers: Headers | None
    stored: StoredNumber | None
    stored_as_text: bool


NonValueClass = Literal[
    "no_value_marker",
    "year",
    "code",
    "date",
    "range",
    "date_part",
    "identifier",
    "ordinal",
    "marker",
    "range_part",
    "header",
    "page_reference",
    "page_number",
    "formula_without_result",
]
NON_VALUE_CLASSES: tuple[NonValueClass, ...] = (
    "no_value_marker",
    "year",
    "code",
    "date",
    "range",
    "date_part",
    "identifier",
    "ordinal",
    "marker",
    "range_part",
    "header",
    "page_reference",
    "page_number",
    "formula_without_result",
)


@dataclass(frozen=True, slots=True)
class NonValue:
    """숫자가 있지만 값 후보가 아닌 것. 버리지 않고 갈래와 함께 남긴다."""

    doc_id: str
    where: FactWhere
    raw: str
    cls: NonValueClass  # TS 의 `class`


@dataclass(frozen=True, slots=True)
class FailedTable:
    id: str
    page: int


ValueKind = Literal["value", "identifier", "duration", "count", "year_label", "scale"]
VALUE_KINDS: tuple[ValueKind, ...] = ("value", "identifier", "duration", "count", "year_label", "scale")


@dataclass(frozen=True, slots=True)
class Extraction:
    doc_id: str
    file_name: str
    grids: tuple[Grid, ...]
    facts: tuple[Fact, ...]
    non_values: tuple[NonValue, ...]
    failed_tables: tuple[FailedTable, ...]  # 격자를 세우지 못한 표. 안의 숫자 수는 모른다
    pages_without_text: tuple[int, ...]  # 텍스트 계층이 없는 쪽 (스캔본 등). 숫자가 있어도 읽지 못한다
    kinds: Mapping[str, ValueKind] | None = None  # 값 후보의 종류 (ID → 종류). `kinds` 옵션을 켰을 때만


# ── 자리 (places) ────────────────────────────────────────────────────────────

Box = tuple[float, float, float, float]  # [x0, y0, x1, y1] pt, 왼쪽 위 원점


@dataclass(frozen=True, slots=True)
class PlaceRun:
    """줄 토막: 그릇의 글에서 `start` 자리부터 이어지는 글자들의 가로 범위와, 토막의 세로 범위. 자리는 UTF-16."""

    start: int
    y0: float
    y1: float
    x0: tuple[float, ...]
    x1: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PlaceContainer:
    """그릇 하나: 글 블록(`p3-b2`) 또는 표의 칸(`p3-t1:r2c4`)."""

    id: str
    kind: Literal["block", "cell"]
    page: int
    bbox: Box  # 그릇의 글자 전체를 감싼 상자
    runs: tuple[PlaceRun, ...]


@dataclass(frozen=True, slots=True)
class Unlinked:
    id: str
    page: int
    reason: str


@dataclass(frozen=True, slots=True)
class CharPlaces:
    """검증을 통과한 글자 자리. `places.validate_places` 만 만든다."""

    source: DocSource
    containers: tuple[PlaceContainer, ...]
    unlinked: tuple[Unlinked, ...]


@dataclass(frozen=True, slots=True)
class PlaceIndex:
    containers: Mapping[str, PlaceContainer]
    unlinked: frozenset[str]


PlaceMissingReason = Literal[
    "unknown_id",  # 그런 ID 의 값 후보가 없다
    "no_places",  # 글자 자리 없이 분해한 문서다
    "not_in_document",  # 엑셀처럼 PDF 문서 모델에서 나오지 않은 자리다
    "container_unlinked",  # 분해가 그 그릇의 글자 자리를 잇지 못했다
    "container_missing",  # 글자 자리에 그 그릇이 없다
    "no_glyphs_in_span",  # 그 글자 범위에 좌표 있는 글자가 없다
]
PLACE_MISSING_REASONS: tuple[PlaceMissingReason, ...] = (
    "unknown_id",
    "no_places",
    "not_in_document",
    "container_unlinked",
    "container_missing",
    "no_glyphs_in_span",
)


@dataclass(frozen=True, slots=True)
class PlaceFound:
    page: int
    boxes: tuple[Box, ...]  # 줄마다 하나. 숫자가 두 줄에 걸치면 둘이다
    container_box: Box  # 그릇(칸·블록)의 글자 전체를 감싼 상자
    covered: int  # 범위의 글자 가운데 좌표가 있는 글자의 수
    length: int  # 범위의 글자 수 (UTF-16). covered 와 같지 않으면 분해가 끼운 빈칸이 범위에 들어 있다
    found: Literal[True] = True


@dataclass(frozen=True, slots=True)
class PlaceMissing:
    reason: PlaceMissingReason
    found: Literal[False] = False


Place = PlaceFound | PlaceMissing
