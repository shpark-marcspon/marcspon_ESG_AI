"""Scope 3 연도 상태의 셈 — 순수(django 0). 밴드 S3K2a ①(결정 MARC-ENT-559 · 515 · 469 2, 발주서 Q6·Q9·Q11).

「지금 결과」는 저장하지 않고 읽을 때 셈한다(실행기에 끝남 고리 0): 잠긴 카테고리는 핀 실행, 아니면 그 해 기준 실행 R.

  CATEGORIES        밖 이름 열넷(C1~C15, C10 뺌 — 엔진 결과 시트의 "CategoryN" 과 같은 번호)
  CATEGORY_NAMES    카테고리 이름 — 웹 S3_TEXT.categories 글자 그대로의 서버 상수(대시보드 name)
  counts_for_year   실행 하나가 그 해 Scope 3 기준 실행 후보인가(flow · purpose · options.reportYear — Q6)
  is_done_result    결과 본문이 scope3.colab.result@1 의 done 갈래인가(rejected 는 R 이 아니다)
  base_run          만든 차례(새 것 먼저)의 후보에서 latest(가장 새 후보)와 R(첫 「done + 결과 done」)
  category_value    실행 결과 하나에서 카테고리 하나의 값(Q11 — 웹 summarize 와 같은 재료: processed 만 셈. S3K2b-1:
                    제외된 줄은 합에서 빠지고 시트 수·잠금 자격은 그대로. S3K2b-2: 계수 고친 줄은 사건의 배출량)
  lockable          잠글 수 있는 값인가(processed 시트가 하나 이상)
  top_categories    대시보드 상위 5(값 없는 카테고리는 빠지고 0·음수는 든다 · 큰 차례 · 같으면 C 번호
                    · share 는 Scope 3 합 대비)

수 글자는 코랩 repr(float) 그대로라(MARC-ENT-442) 웹 parseNumber 와 같은 꼴만 수로 읽는다(nan·inf·빈 글자는 빠짐).
합은 sum_or_none(prec 60) 의 Decimal 정확합이다.
"""

import re
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Final, cast

from esgapi.inventory.service.utils.dashboard import share
from esgapi.inventory.service.utils.entries import sum_or_none

CATEGORIES: Final = tuple(f"C{n}" for n in range(1, 16) if n != 10)
CATEGORY_NAMES: Final[Mapping[str, str]] = {
    "C1": "구매 상품 및 서비스",
    "C2": "자본재",
    "C3": "연료 및 에너지 활동",
    "C4": "업스트림 운송 및 유통",
    "C5": "사업장 발생 폐기물",
    "C6": "출장",
    "C7": "출퇴근",
    "C8": "업스트림 임차 자산",
    "C9": "다운스트림 운송 및 유통",
    "C11": "판매된 제품의 사용",
    "C12": "판매된 제품의 폐기",
    "C13": "다운스트림 임차 자산",
    "C14": "프랜차이즈",
    "C15": "투자",
}
"""웹 apps/web/src/entities/ghg-scope3/config/text.ts 의 S3_TEXT.categories 글자 그대로(C10 뺌 — 1차 계산 0)."""

FLOW_ID: Final = "scope3.colab@157"
"""기준 실행이 되는 흐름(Q6). 옛 scope3.llm-first@1 실행은 후보가 아니다."""
RESULT_SHAPE: Final = "scope3.colab.result@1"
PURPOSE: Final = "service"
TOP_CATEGORIES: Final = 5
_NUMBER: Final = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")  # 웹 parseNumber 의 NUMBER_TEXT 와 같은 꼴
_NO_CO2E: Final[Mapping[str, str | None]] = MappingProxyType({})
_SKIP: Final = object()


def engine_category(category: str) -> str:
    """밖 이름 「C4」 → 엔진 결과 시트의 category 칸 「Category4」."""
    return f"Category{category[1:]}"


@dataclass(frozen=True, slots=True)
class Candidate:
    """실행 목록(만든 차례 — 새 것 먼저)의 한 줄에서 R 고르기에 쓰는 칸만."""

    id: int
    status: str
    flow_id: str
    purpose: str
    options: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class Base:
    """latest = 그 해 가장 새 후보(id·상태 — 어느 상태든) · run_id·body = R(없으면 None)."""

    latest: tuple[int, str] | None
    run_id: int | None
    body: Mapping[str, object] | None


@dataclass(frozen=True, slots=True)
class Value:
    """카테고리 하나의 값(Q11). total None = 셈한 수가 없음."""

    total: Decimal | None
    sheets: int
    failed_sheets: int


@dataclass(frozen=True, slots=True)
class Ranked:
    category: str
    name: str
    value: Decimal
    share: Decimal | None


def counts_for_year(candidate: Candidate, year: int) -> bool:
    """그 해 기준 실행 후보: flow scope3.colab@157 · purpose service · options.reportYear == year(참거짓 아님)."""
    report_year = candidate.options.get("reportYear")
    return (
        candidate.flow_id == FLOW_ID
        and candidate.purpose == PURPOSE
        and isinstance(report_year, int)
        and not isinstance(report_year, bool)
        and report_year == year
    )


def _mapping(value: object) -> Mapping[str, object] | None:
    return cast("Mapping[str, object]", value) if isinstance(value, Mapping) else None


def _items(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []


def is_done_result(body: object) -> bool:
    found = _mapping(body)
    return found is not None and found.get("status") == "done" and isinstance(found.get("sheets"), list)


def base_run(
    candidates: Iterable[Candidate], year: int, result_of: Callable[[int], Mapping[str, object] | None]
) -> Base:
    """만든 차례(새 것 먼저)로 받은 실행에서 latest 와 R. result_of(run_id) 는 그 실행의 결과 본문(없으면 None) —
    status done 인 후보에만, 새 것부터 부른다. 첫 「done + 결과 done」에서 멈춘다(그 뒤 줄은 읽지 않음)."""
    latest: tuple[int, str] | None = None
    for candidate in candidates:
        if not counts_for_year(candidate, year):
            continue
        if latest is None:
            latest = (candidate.id, candidate.status)
        if candidate.status != "done":
            continue
        body = result_of(candidate.id)
        if is_done_result(body):
            return Base(latest=latest, run_id=candidate.id, body=body)
    return Base(latest=latest, run_id=None, body=None)


def number(text: object) -> Decimal | None:
    """수 글자 → Decimal. 꼴이 아니면(nan·inf·빈 글자·글자 아님) None. -0 은 0."""
    if not isinstance(text, str) or not _NUMBER.fullmatch(text):
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:  # 꼴은 위에서 걸렀다 — 닫힌 쪽으로
        return None
    return Decimal(0) if value == 0 else value


def _line_value(row: Mapping[str, object], excluded: Collection[str], co2e_of: Mapping[str, str | None]) -> object:
    """합에 넣을 그 줄의 co2e 글자 — 빠졌으면 _SKIP. rowId 가 글자가 아닌 줄은 본문 값 그대로(561 L5)."""
    row_id = row.get("rowId")
    if not isinstance(row_id, str):
        return row.get("co2e")
    if row_id in excluded:
        return _SKIP
    return co2e_of[row_id] if row_id in co2e_of else row.get("co2e")


def category_value(
    body: Mapping[str, object] | None,
    category: str,
    excluded: Collection[str] = frozenset(),
    co2e_of: Mapping[str, str | None] = _NO_CO2E,
) -> Value:
    """결과 본문 하나에서 카테고리 하나(Q11): processed 시트의 줄 co2e 합(수 0 이면 None) · processed 수 · failed 수.
    empty·not_yet_supported·모르는 갈래는 셈 0. 본문이 done 이 아니면 빈 값. excluded 의 rowId 는 합에서만 빠지고
    (S3K2b-1 Q5 — 시트 수·잠금 자격은 시트 단위 그대로), co2e_of 의 rowId 는 본문 값 대신 그 값이다(S3K2b-2 — 본문은
    덮지 않는다)."""
    if body is None or not is_done_result(body):
        return Value(total=None, sheets=0, failed_sheets=0)
    name = engine_category(category)
    found: list[Decimal | None] = []
    sheets = failed = 0
    for item in _items(body.get("sheets")):
        sheet = _mapping(item)
        if sheet is None or sheet.get("category") != name:
            continue
        status = sheet.get("status")
        if status == "failed":
            failed += 1
        elif status == "processed":
            sheets += 1
            for line in _items(sheet.get("rows")):
                row = _mapping(line)
                value = _SKIP if row is None else _line_value(row, excluded, co2e_of)
                if value is not _SKIP:
                    found.append(number(value))
    return Value(total=sum_or_none(found), sheets=sheets, failed_sheets=failed)


def lockable(value: Value) -> bool:
    """잠금 자격(Q11): processed 시트가 하나 이상(failed 가 섞여도). failed 만·empty·시트 없음은 아니다."""
    return value.sheets > 0


def scope3_total(values: Iterable[Decimal | None]) -> Decimal | None:
    """카테고리 지금 결과 합(값 없는 카테고리는 빠짐 — 다 없으면 None)."""
    return sum_or_none(values)


def top_categories(values: Mapping[str, Decimal | None], whole: Decimal | None) -> tuple[Ranked, ...]:
    """상위 5(Q9): 값 없는(None) 카테고리는 빠지고 0·음수는 든다. 큰 차례, 같으면 C 번호. share = whole(Scope 3 합)
    대비."""
    order = {category: index for index, category in enumerate(CATEGORIES)}
    valued = [(category, value) for category, value in values.items() if value is not None]
    valued.sort(key=lambda item: order[item[0]])
    valued.sort(key=lambda item: item[1], reverse=True)
    return tuple(
        Ranked(category=category, name=CATEGORY_NAMES[category], value=value, share=share(value, whole))
        for category, value in valued[:TOP_CATEGORIES]
    )
