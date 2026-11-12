"""값 후보의 종류. 옵션이다: 숫자 뽑기의 기본 동작(값 후보 목록, ID, 갈래)은 바꾸지 않는다.

esg-lab `ts/reconcile/src/domain/kinds.ts`(139줄)를 옮겼다.
값 후보는 버리지 않는다. 종류는 「이 숫자가 검증할 값인가, 값이 아닌 표시인가」를 가르는 꼬리표일 뿐이다.
규칙은 꼴(앞뒤 글자, 단위, 머리글, 좌표, 수열)만 본다. **틀릴 수 있다** — KB 두 문서를 보고 만든 규칙이고
다른 문서에서 틀린 자리가 알려져 있다(README 의 reconcile 소절, `band-reports/G1-generalize.md`). 여기서는 고치지
않는다.

  value: 검증할 값 (잰 양·금액·비율·목표값·문턱값)   identifier: 가리키는 번호 (규격·조항·각주·쪽 번호, 이름의 일부)
  duration: 기간·시점 (10년, 3개년, 6개월)            count: 구성을 센 수(3종, 4대)와 정해 둔 빈도(연 1회 이상)
  year_label: 연도 표시 (표·도표의 연도 칸)           scale: 눈금·척도·기준 단위 (축 눈금, 5점 척도, 1억 원당)
"""

import re
from dataclasses import dataclass
from typing import Final

from esgapi.reconcile.calc.dec import dec, show, sub
from esgapi.reconcile.calc.jstext import WS, js_round, js_trim, to_units
from esgapi.reconcile.calc.notation import classify_cell, scan_numbers
from esgapi.reconcile.calc.types import DocModel, Extraction, Fact, ValueKind


def is_non_value(kind: ValueKind) -> bool:
    return kind != "value"


@dataclass(frozen=True, slots=True)
class KindContext:
    """글 속 값 후보 하나의 앞뒤 글. 표의 숫자 칸이면 `text` 는 칸 글자, `start`·`end` 는 칸 전체다. 자리는 UTF-16."""

    text: str
    start: int
    end: int
    column_headers: tuple[str, ...]  # 표에서 나온 숫자면 열 머리글의 글자


_S: Final = f"[{WS}]"
# kinds.ts:29-32
_LABEL_RUN: Final = re.compile(
    rf"(Scope|Category|CAT|Cat|Tier|Level|Phase|Step|Type|Class|스코프|카테고리){_S}?[0-9]+"
    rf"(?:{_S}?[,&]{_S}?[0-9]+)*{_S}?[,&]{_S}?\Z"
)
_ACRONYM_BEFORE: Final = re.compile(r"(?:^|[^A-Za-z])[A-Z]{2,}(?:/[A-Z]{2,})? ?\Z")
_CLAUSE_BEFORE: Final = re.compile(rf"(문단|조항|원칙|Article|Section|Principle|Paragraph){_S}?\Z|제[0-9]+조의\Z")
# `i` 플래그는 ASCII 로만 접는다(까닭은 facts.py 의 _PAGE_REFERENCE_HEADER).
_STANDARD_HEADER: Final = re.compile(
    r"GRI|SASB|ESRS|KSSB|IFRS|TCFD|ISO|코드|지표 ?번호|index", re.IGNORECASE | re.ASCII
)
_DURATION_UNITS: Final = frozenset({"년", "개월", "일", "시간", "주"})  # kinds.ts:33

_PAREN_NUMBER_AFTER: Final = re.compile(r"\([0-9]+\)")
_DIGIT_SLASH_END: Final = re.compile(r"[0-9]/\Z")
_SLASH_DIGIT: Final = re.compile(r"/[0-9]")
_PAGE_AFTER: Final = re.compile(r" ?(페이지|쪽(?![가-힣]))")
_HANGUL_OR_PERCENT_AFTER: Final = re.compile(r" ?[가-힣%]")
# kinds.ts:56 의 `[^\d]{2,40}` 은 `u` 플래그라 코드포인트로 센다. UTF-16 자리의 문자열에서는 짝 맞는 대행 글자 둘이 한
# 글자다.
# 짝이 맞는 둘은 되짚기로도 쪼개지지 않게 한다(앞 대행 글자는 뒤에 짝이 없을 때만 홀로 센다).
_NOT_DIGIT_POINT: Final = "(?:[\ud800-\udbff][\udc00-\udfff]|[^0-9\ud800-\udbff]|[\ud800-\udbff](?![\udc00-\udfff]))"
_CONTENTS_LINE: Final = re.compile(rf"[0-9]{{1,3}} {_NOT_DIGIT_POINT}{{2,40}}")
_SENTENCE_END: Final = re.compile(r"[.。] ?\Z")
_APOSTROPHE_END: Final = re.compile(r"['’]\Z")
_YEARS_AFTER: Final = re.compile(r" ?개년")
_SCALE_AFTER: Final = re.compile(r"점 ?(척도|만점|[~∼〜]|에서|까지)")
_NEAR_AFTER: Final = re.compile(r"에 가까")
_ONE_FOLLOWED_BY_ZEROS: Final = re.compile(r"1(,?0)*")
_PER_AFTER: Final = re.compile(r" ?[가-힣]{0,2} ?[가-힣]{1,2} ?당(?![가-힣])")
_COUNT_AFTER: Final = re.compile(r" ?(종|대|가지)(?=\Z|[^가-힣]|(?:으로|로|의|을|를|이|가|은|는|에)(?![가-힣]))")
_PIECES_AFTER: Final = re.compile(r" ?개(?![월년소국사])")
_TIMES_AFTER: Final = re.compile(r"회")
_FREQUENCY_BEFORE: Final = re.compile(r"(연|매년|분기|분기별|반기|매월|월|주) ?\Z")
_TIMES_OR_MORE_AFTER: Final = re.compile(r"회 ?이상")
_ZERO: Final = re.compile(r"-?0(\.0+)?")

# 앞뒤 글을 보는 창 (kinds.ts:40-41). UTF-16 자리로 센다.
_BEFORE_WINDOW: Final = 32
_AFTER_WINDOW: Final = 16
# 숫자뿐인 블록의 왼쪽·오른쪽 끝을 묶는 폭(pt). kinds.ts:132 의 `Math.round(x / 2)`.
_COLUMN_SNAP: Final = 2


def _digits(fact: Fact) -> str:
    return fact.value.removeprefix("-")


def kind_of(fact: Fact, context: KindContext) -> ValueKind:
    """값 후보 하나의 종류(앞뒤 글자만 본다). 수열·좌표로 보는 눈금은 `classify_kinds` 가 따로 붙인다. kinds.ts:38-73"""
    if fact.bucket == "table_cell":
        return "year_label" if "year_like" in fact.flags else "value"
    text = to_units(context.text)
    before = text[max(0, context.start - _BEFORE_WINDOW) : context.start]
    after = text[context.end : context.end + _AFTER_WINDOW]
    bare = not fact.percent and fact.unit_suffix is None
    integer = fact.decimals == 0
    digits = _digits(fact)
    small = integer and "," not in fact.raw and len(digits) <= 2

    # 가리키는 번호
    if bare and _LABEL_RUN.search(before):
        return "identifier"
    if bare and (before.endswith("*") or (before.endswith(")") and after.startswith(")"))):
        return "identifier"
    if bare and (_CLAUSE_BEFORE.search(before) or _PAREN_NUMBER_AFTER.match(after)):
        return "identifier"
    if bare and (_DIGIT_SLASH_END.search(before) or _SLASH_DIGIT.match(after)):
        return "identifier"
    if bare and _PAGE_AFTER.match(after):
        return "identifier"
    # 대문자 약어 뒤의 번호: 쉼표 없는 세 자리 이상의 정수면 규격 번호로 본다(뒤에 조사가 붙어도).
    # 그보다 짧거나 소수면 뒤에 한글이 바로 오지 않을 때만.
    if (
        bare
        and _ACRONYM_BEFORE.search(before)
        and ((integer and "," not in fact.raw and len(digits) >= 3) or not _HANGUL_OR_PERCENT_AFTER.match(after))
    ):
        return "identifier"
    if bare and any(_STANDARD_HEADER.search(header) for header in context.column_headers):
        return "identifier"
    whole = js_trim(text)
    # 차례의 한 줄(`쪽 번호 + 제목`)과 글 끝에 홀로 붙은 쪽 번호.
    if bare and integer and len(digits) <= 3 and _CONTENTS_LINE.fullmatch(whole) and context.start == text.find(whole):
        return "identifier"
    if bare and integer and len(digits) <= 3 and js_trim(text[context.end :]) == "" and _SENTENCE_END.search(before):
        return "identifier"

    # 기간·시점
    if _APOSTROPHE_END.search(before):
        return "duration"
    if integer and fact.unit_suffix is not None and fact.unit_suffix in _DURATION_UNITS:
        return "duration"
    if integer and _YEARS_AFTER.match(after):
        return "duration"

    # 눈금·척도·기준 단위
    if _SCALE_AFTER.match(after) or _NEAR_AFTER.match(after):
        return "scale"
    if _ONE_FOLLOWED_BY_ZEROS.fullmatch(fact.raw) and _PER_AFTER.match(after):
        return "scale"

    # 구성을 센 수, 정해 둔 빈도
    if small and _COUNT_AFTER.match(after):
        return "count"
    if small and _PIECES_AFTER.match(after):
        return "count"
    if small and _TIMES_AFTER.match(after) and (_FREQUENCY_BEFORE.search(before) or _TIMES_OR_MORE_AFTER.match(after)):
        return "count"
    return "value"


def _evenly_spaced(values: list[str]) -> bool:
    """수들이 같은 간격으로 늘어서 있는가 (셋 이상, 간격이 0 이 아님)."""
    if len(values) < 3:
        return False
    step = show(sub(dec(values[1]), dec(values[0])))
    if _ZERO.fullmatch(step):
        return False
    return all(show(sub(dec(values[i]), dec(values[i - 1]))) == step for i in range(1, len(values)))


def _round_pair(raws: list[str], values: list[str]) -> bool:
    """수 둘이 눈금 꼴인가: 끝자리가 0 이고 둘 다 그 간격의 배수다(`600 400`). 값 둘(`18.2 18.1`)은 아니다."""
    if len(values) != 2 or not all(raw.endswith("0") for raw in raws):
        return False
    # 두 수를 같은 소수 자리의 정수로 맞춰 본다 (십진 그대로).
    p, q = dec(values[0]), dec(values[1])
    places = max(p.scale, q.scale)
    x = p.coef * 10 ** (places - p.scale)
    y = q.coef * 10 ** (places - q.scale)
    step = abs(x - y)
    return step > 0 and x % step == 0 and y % step == 0


def classify_kinds(document: DocModel, extraction: Extraction) -> dict[str, ValueKind]:
    """문서 하나의 모든 값 후보에 종류를 붙인다. 값 후보 목록은 건드리지 않는다(ID → 종류의 표만 낸다). kinds.ts:101-139

    앞뒤 글자로 보는 규칙(`kind_of`) 뒤에 눈금 둘을 더 본다:
     - 숫자만 든 표의 글 칸(도표의 축이 한 칸으로 읽힌 것)에서 수들이 같은 간격으로 늘어서 있거나(셋 이상), 둘뿐이면
       눈금 꼴일 때.
     - 단위 없는 숫자뿐인 블록이 한 쪽에서 같은 세로줄(왼쪽이나 오른쪽 끝이 2pt 안)에 셋 이상 같은 간격으로 쌓여 있을
       때.
    """
    kinds: dict[str, ValueKind] = {}
    blocks = {block.id: block for block in document.blocks}
    grids = {grid.id: grid for grid in extraction.grids}

    def cell_text(fact: Fact) -> str | None:
        where = fact.where
        grid = grids.get(where.grid_id or "")
        if grid is None or where.row is None or where.col is None or not 0 <= where.row < len(grid.cells):
            return None
        cells = grid.cells[where.row]
        return cells[where.col] if 0 <= where.col < len(cells) else None

    by_cell: dict[str, list[Fact]] = {}
    for fact in extraction.facts:
        where = fact.where
        raw_length = len(to_units(fact.raw))
        if where.block_id is not None:
            block = blocks.get(where.block_id)
            text = block.text if block is not None and block.text is not None else fact.raw
            context = KindContext(
                text, where.span.start if where.span else 0, where.span.end if where.span else raw_length, ()
            )
        else:
            found = cell_text(fact)
            text = found if found is not None else fact.raw
            context = KindContext(
                text,
                where.span.start if where.span else 0,
                where.span.end if where.span else len(to_units(text)),
                tuple(ref.text for ref in fact.headers.col) if fact.headers else (),
            )
            if fact.bucket == "table_text_cell":
                by_cell.setdefault(f"{where.grid_id}:r{where.row}c{where.col}", []).append(fact)
        kinds[fact.id] = kind_of(fact, context)

    for facts in by_cell.values():
        text = cell_text(facts[0]) or ""
        if classify_cell(text).kind != "multi_number" or len(scan_numbers(text)) != len(facts):
            continue
        values = [fact.value for fact in facts]
        if all(not fact.percent for fact in facts) and (
            _evenly_spaced(values) or _round_pair([fact.raw for fact in facts], values)
        ):
            for fact in facts:
                kinds[fact.id] = "scale"

    columns: dict[str, list[tuple[Fact, float]]] = {}
    per_block: dict[str, int] = {}
    for fact in extraction.facts:
        if fact.where.block_id is not None:
            per_block[fact.where.block_id] = per_block.get(fact.where.block_id, 0) + 1
    for fact in extraction.facts:
        block_id = fact.where.block_id
        if fact.bucket != "number_only_block" or fact.unit_suffix is not None or fact.percent or block_id is None:
            continue
        if per_block.get(block_id) != 1:
            continue
        block = blocks.get(block_id)
        if block is None:
            continue
        x0, y0, x1, _ = block.bbox
        # JS 의 Math.round 는 0.5 를 위로 올린다. 파이썬의 round() 는 짝수로 가서 세로줄 열쇠가 달라진다.
        left = f"{block.page}|L{js_round(x0 / _COLUMN_SNAP)}"
        right = f"{block.page}|R{js_round(x1 / _COLUMN_SNAP)}"
        for key in (left, right):
            columns.setdefault(key, []).append((fact, y0))
    for column in columns.values():
        ordered = sorted(column, key=lambda item: item[1])
        if _evenly_spaced([fact.value for fact, _ in ordered]):
            for fact, _ in ordered:
                kinds[fact.id] = "scale"
    return kinds
