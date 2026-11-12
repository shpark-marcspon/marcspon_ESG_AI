"""Scope 3 줄 계수 수정의 순수 셈 — kind 별 식·몸 검사·고칠 수 있음 판정. 밴드 S3K2b-2 ①(결정 MARC-ENT-570·442).

★ 엔진을 import 하지 않는다(pandas 없이, colab_157 판에 묶지 않음 — 이 밴드의 감독 판단). 엔진 식을 결과 줄 칸만으로
  여기에 다시 적었다. 곱 차례까지 같아야 글자가 같다(`repr(float)`). 엔진 식이 바뀌면 같은-계수 대조
  (tests/service/utils/test_scope3_factors_same.py)가 빨개진다.

  recompute          줄 하나 + 계수 값 → 배출량·생물기원(글자). 칸이 모자라 못 세면 None
  editable           Q5: 고칠 수 있는 줄인가 — C12·C15 아님 · 칸이 다 있음 · 원래 계수로 본문과 글자가 같음(R6 · C0 Q-a)
  check_factor_body  몸 검사(Q6·짝 규칙) — FactorBody 또는 Invalid
  ai_of              결과 본문의 그 줄이 말하는 AI 원안(대표 제목·값·출처·배출량)
  chosen             고름 → 사건에 남길 값. 추천 순위가 밖이면 Invalid, 셈이 안 되면 None

출처 글은 그 계수의 시트 이름이다(구매 줄은 factorBook.sheet + factor.column). `factor.source` 는 출처가 아니다.
"""

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, Literal, cast, get_args

from esgapi.inventory.service.utils.ghg_pool import Invalid
from esgapi.inventory.service.utils.scope3_state import FLOW_ID, RESULT_SHAPE

Choice = Literal["applied", "recommended", "custom"]

FACTOR_CHOICES: Final[tuple[Choice, ...]] = get_args(Choice)
FACTOR_CHOICE_MAX: Final = 11
FACTOR_RANK_FIRST: Final = 1
FACTOR_RANK_LAST: Final = 4
SCOPE3_FACTOR_TEXT_MAX: Final = 200
"""직접 입력 제목·출처 글자 수 [우리 해석]. 출처 칸 길이이기도 하다(시트 이름 + 열 이름은 이 안 — C0-5)."""
FACTOR_TITLE_MAX: Final = 300
"""제목 칸 길이 — 책의 제목이 그대로 든다(패키지 책 가장 긴 글 칸 215자 — C0 Q-d). 직접 입력은 위 200 으로 막는다."""
FACTOR_NUMBER_MAX: Final = 32
"""수 글자 칸 길이 — `repr(float)` 는 24자 안."""
FACTOR_UNIT_MAX: Final = 32
"""단위 칸 길이 — 패키지 책 단위 20자 안(C0-5)."""
VALUE_DECIMALS: Final = 10

_DECIMAL: Final = re.compile(r"[0-9]+(\.([0-9]+))?")

RANK_BAD: Final = f"추천 순위는 {FACTOR_RANK_FIRST}~{FACTOR_RANK_LAST} 이고 추천을 고를 때만 보낸다"
RANK_UNKNOWN: Final = "이 줄에 없는 추천 순위다"
CUSTOM_BAD: Final = "직접 입력을 고를 때만 보낸다"
VALUE_BAD: Final = f"소수 {VALUE_DECIMALS}자리까지의 십진 수다"
VALUE_NOT_POSITIVE: Final = "0보다 큰 수다"
TEXT_BAD: Final = f"앞뒤 공백을 걷고 1~{SCOPE3_FACTOR_TEXT_MAX}자다"


@dataclass(frozen=True, slots=True)
class Custom:
    """직접 입력 몸. 단위는 받지 않는다 — 그 줄 factor.unit 그대로(Q6)."""

    title: str
    value: str
    source: str


@dataclass(frozen=True, slots=True)
class FactorBody:
    """검사를 지난 몸. custom 의 글은 걷은 값, value 는 저장 꼴 `repr(float(입력))`(Q6 — 엔진과 같은 꼴)."""

    row_id: str
    choice: Choice
    rank: int | None
    custom: Custom | None
    reason: str


@dataclass(frozen=True, slots=True)
class Recomputed:
    co2e: str
    biogenic_co2e: str | None


@dataclass(frozen=True, slots=True)
class Ai:
    """사건 때 뜬 AI 원안(537 — 결과 본문은 덮지 않으니 사건 표 하나로 원안과 고른 값을 읽는다)."""

    title: str | None
    value: str | None
    source: str | None
    co2e: str | None


@dataclass(frozen=True, slots=True)
class Factor:
    """계수 사건의 값. co2e·biogenic_co2e 는 수정 때 한 번 센 값이다(Q3 — 읽을 때 식을 다시 돌지 않는다)."""

    choice: Choice
    rank: int | None
    title: str | None
    value: str | None
    source: str | None
    unit: str | None
    co2e: str | None
    biogenic_co2e: str | None
    ai: Ai


def _mapping(value: object) -> Mapping[str, object]:
    return cast("Mapping[str, object]", value) if isinstance(value, Mapping) else {}


def _float(text: object) -> float | None:
    """수 글자 → 유한한 float. 글자가 아니거나 수가 아니면 None."""
    if not isinstance(text, str):
        return None
    try:
        found = float(text)
    except ValueError:
        return None
    return found if math.isfinite(found) else None


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _field(row: Mapping[str, object], part: str, name: str) -> float | None:
    return _float(_mapping(row.get(part)).get(name))


def _purchase(row: Mapping[str, object], value: float) -> float | None:
    """purchase.py:1032-1033 (금액 × EF) / 1000."""
    amount = _float(row.get("amount"))
    return None if amount is None else (amount * value) / 1000.0


def _transport_spend(row: Mapping[str, object], value: float) -> float | None:
    """spend.py:375·389 금액 × EF / 1000 — baseValue 가 그 갈래의 금액(KRW 또는 USD)이다."""
    base = _field(row, "activity", "baseValue")
    return None if base is None else base * value / 1000


def _travel_spend(row: Mapping[str, object], value: float) -> float | None:
    """spend.py:422 금액 × EF / 1000."""
    amount = _field(row, "activity", "value")
    return None if amount is None else amount * value / 1000.0


def _transport_distance(row: Mapping[str, object], value: float) -> float | None:
    """transport.py:398 거리 × (kg / 1000) × EF / 1000."""
    km, kg = _field(row, "distance", "km"), _field(row, "activity", "baseValue")
    return None if km is None or kg is None else km * (kg / 1000.0) * value / 1000.0


def _travel_distance(row: Mapping[str, object], value: float) -> float | None:
    """travel.py:318 거리 × 왕복 × 인원 × 횟수 × EF / 1000."""
    km, trip = _field(row, "distance", "km"), _field(row, "distance", "roundTrip")
    people, trips = _field(row, "distance", "people"), _field(row, "distance", "trips")
    if km is None or trip is None or people is None or trips is None:
        return None
    return km * trip * people * trips * value / 1000.0


def _commute(row: Mapping[str, object], value: float) -> float | None:
    """travel.py:288 인원 × 거리 × 왕복 × 근무일 × EF / 1000 — 출장과 곱 차례가 다르다."""
    km, trip = _field(row, "distance", "km"), _field(row, "distance", "roundTrip")
    people, days = _field(row, "distance", "people"), _field(row, "distance", "workdays")
    if km is None or trip is None or people is None or days is None:
        return None
    return people * km * trip * days * value / 1000.0


def _energy(row: Mapping[str, object], value: float) -> float | None:
    """energy.py:1026·1055 사용량 × EF / 1000 — 계수는 참거짓으로 본다(0 이면 없음)."""
    base = _field(row, "activity", "baseValue")
    return base * value / 1000 if base is not None and value else None


def _product_use(row: Mapping[str, object], value: float) -> float | None:
    """product.py:566 총사용량 × EF / 1000."""
    total = _field(row, "product", "totalUsage")
    return None if total is None else total * value / 1000.0


def _franchise(row: Mapping[str, object], value: float) -> float | None:
    """energy.py:776 사용량 × EF / 1000."""
    base = _field(row, "activity", "baseValue")
    return None if base is None else base * value / 1000.0


_FORMULAS: Final[Mapping[str, Callable[[Mapping[str, object], float], float | None]]] = {
    "purchase": _purchase,
    "transport_spend": _transport_spend,
    "travel_spend": _travel_spend,
    "transport_distance": _transport_distance,
    "travel_distance": _travel_distance,
    "commute": _commute,
    "fuel_energy": _energy,
    "leased_asset": _energy,
    "leased_out_asset": _energy,
    "product_use": _product_use,
    "franchise": _franchise,
}
"""`waste` 는 생물기원을 함께 내서 `_waste` 가 따로 본다. `product_eol`·`investment` 는 식이 없다(Q5 ⓐⓒ)."""


def _waste(row: Mapping[str, object], value: float) -> Recomputed | None:
    """waste.py:234·134 처리량(kg) × EF / 1000 을 화석·생물기원으로 나눈다(Q8). 처리량·계수는 참거짓으로 본다.

    소각 줄의 나눔 칸이 비었으면 그룹(FCF)을 잃은 줄이라 나눌 수 없다(C0 Q-b — 계수 0 인 소각 줄) → None."""
    kg = _field(row, "activity", "baseValue")
    biogenic = _mapping(row.get("biogenic"))
    if not (kg and value) or (row.get("treatment") == "소각" and biogenic.get("fossilCo2e") is None):
        return None
    emission = kg * value / 1000
    if not math.isfinite(emission):
        return None
    fcf = _float(biogenic.get("fcf"))
    if fcf is None:
        return Recomputed(repr(emission), repr(0.0))
    part = emission * (1 - fcf)
    return Recomputed(repr(emission - part), repr(part))


def recompute(row: Mapping[str, object], value: float) -> Recomputed | None:
    """그 줄에 계수 value 를 넣은 배출량(C0-2 표의 식). 식이 없는 kind·칸이 모자란 줄·셈이 없는 값은 None."""
    kind = row.get("kind")
    if kind == "waste":
        return _waste(row, value)
    formula = _FORMULAS.get(kind) if isinstance(kind, str) else None
    found = None if formula is None else formula(row, value)
    return None if found is None or not math.isfinite(found) else Recomputed(repr(found), None)


def editable(row: Mapping[str, object], schema: object, flow: object) -> bool:
    """Q5(`factor_not_editable` 의 안쪽): 흐름·결과 꼴이 맞고 · factor 객체와 단위가 있고 · 식이 서고 · 원래 계수로
    다시 세면 본문과 글자가 같다. 마지막이 후처리 실패 시트의 C6·C7 줄(본문 co2e null)을 막는다(R6). 계수를 못 찾은 줄
    (값 null)은 비교할 값이 없어 받는다."""
    factor = _mapping(row.get("factor"))
    if schema != RESULT_SHAPE or flow != FLOW_ID or _text(factor.get("unit")) is None:
        return False
    if recompute(row, 1.0) is None:
        return False
    value = _float(factor.get("value"))
    if value is None:
        return True
    again = recompute(row, value)
    return (None if again is None else again.co2e) == row.get("co2e")


def _check_value(text: str) -> str | None:
    """직접 입력 값의 문제 글(없으면 None). 지수·부호·공백은 꼴에서 걸린다."""
    match = _DECIMAL.fullmatch(text)
    if match is None or len(match.group(2) or "") > VALUE_DECIMALS:
        return VALUE_BAD
    found = float(text)
    if not math.isfinite(found):
        return VALUE_BAD
    return VALUE_NOT_POSITIVE if found <= 0 else None


def _custom_problems(custom: Custom) -> dict[str, str]:
    fields: dict[str, str] = {}
    problem = _check_value(custom.value)
    if problem is not None:
        fields["custom.value"] = problem
    if not 1 <= len(custom.title.strip()) <= SCOPE3_FACTOR_TEXT_MAX:
        fields["custom.title"] = TEXT_BAD
    if not 1 <= len(custom.source.strip()) <= SCOPE3_FACTOR_TEXT_MAX:
        fields["custom.source"] = TEXT_BAD
    return fields


def check_factor_body(
    row_id: str, choice: Choice, rank: int | None, custom: Custom | None, reason: str, reason_max: int, reason_bad: str
) -> FactorBody | Invalid:
    """몸 검사(Q6·짝 규칙): recommended ⇔ rank 1~4 · custom ⇔ custom 있음 · applied 는 둘 다 null · 사유 걷고 1~max."""
    fields: dict[str, str] = {}
    wants_rank = choice == "recommended"
    if wants_rank != (rank is not None) or (rank is not None and not FACTOR_RANK_FIRST <= rank <= FACTOR_RANK_LAST):
        fields["rank"] = RANK_BAD
    if (choice == "custom") != (custom is not None):
        fields["custom"] = CUSTOM_BAD
    elif custom is not None:
        fields |= _custom_problems(custom)
    stripped = reason.strip()
    if not 1 <= len(stripped) <= reason_max:
        fields["reason"] = reason_bad
    if fields:
        return Invalid(fields)
    kept = None
    if custom is not None:
        kept = Custom(custom.title.strip(), repr(float(custom.value)), custom.source.strip())
    return FactorBody(row_id, choice, rank, kept, stripped)


def _source(factor: Mapping[str, object], book: Mapping[str, object]) -> str | None:
    """그 계수의 시트 이름. 구매 줄은 factor.sheet 칸이 없어 factorBook.sheet + factor.column(줄바꿈은 공백으로)."""
    sheet = _text(factor.get("sheet"))
    if sheet is not None:
        return sheet
    name, column = _text(book.get("sheet")), _text(factor.get("column"))
    if name is None or column is None:
        return name
    return f"{name} {column.replace(chr(10), ' ')}"


def ai_of(row: Mapping[str, object], book: Mapping[str, object]) -> Ai:
    """결과 본문의 그 줄이 말하는 AI 원안."""
    factor = _mapping(row.get("factor"))
    return Ai(_text(factor.get("title")), _text(factor.get("value")), _source(factor, book), _text(row.get("co2e")))


def _recommended(row: Mapping[str, object], rank: int) -> Mapping[str, object] | None:
    """그 순위의 추천(값이 있는 것만). `recommendations` 는 result@1 에서 purchase 줄에만 있다."""
    found = row.get("recommendations")
    items = cast("list[object]", found) if isinstance(found, list) else []
    item = _mapping(items[rank - 1] if rank <= len(items) else None)
    return item if _float(item.get("value")) is not None else None


def chosen(body: FactorBody, row: Mapping[str, object], book: Mapping[str, object]) -> Factor | Invalid | None:
    """고름 → 사건에 남길 값. 추천 순위가 그 줄에 없으면 Invalid(⑨). 셈이 안 되면 None(부르는 쪽이 409)."""
    ai = ai_of(row, book)
    unit = _text(_mapping(row.get("factor")).get("unit"))
    if body.choice == "applied":
        kept = _text(_mapping(row.get("biogenic")).get("biogenicCo2e"))
        return Factor("applied", None, ai.title, ai.value, ai.source, unit, ai.co2e, kept, ai)
    if body.custom is not None:
        title, value, source = body.custom.title, body.custom.value, body.custom.source
    else:
        item = _recommended(row, body.rank or 0)
        if item is None:
            return Invalid({"rank": RANK_UNKNOWN})
        title, value, source = _text(item.get("title")), _text(item.get("value")), ai.source
    number = _float(value)
    found = None if number is None else recompute(row, number)
    if found is None:
        return None
    return Factor(body.choice, body.rank, title, value, source, unit, found.co2e, found.biogenic_co2e, ai)


def same_choice(now: Factor | None, body: FactorBody, wanted: Factor) -> bool:
    """⑩ 지금 계수 상태와 같은 고름인가(갈래·순위·값·제목·출처 — 값은 저장 글자끼리). 사건이 없으면 지금은 AI 원안."""
    if now is None:
        return body.choice == "applied"
    return (now.choice, now.rank, now.value, now.title, now.source) == (
        wanted.choice,
        wanted.rank,
        wanted.value,
        wanted.title,
        wanted.source,
    )
