"""Scope 1·2 입력(S2·S3·S12)의 순수 도움말(django 0 — .importlinter 다). 밴드 S12a(결정 MARC-ENT-463·469).

  slots            그 해의 입력 칸 — 입력주기(S7, S12a-2)마다 월 열둘(`YYYY-MM`)·분기 넷(`YYYY-Qn`)·연 하나(`YYYY`)
  custom_version   직접입력 계수(S9·S11, S12a-2) → 셈 칸(판과 같은 꼴 — 켠 가스만)
  custom_gases·gases_of  가스 일곱 줄 ↔ inventory_custom_factors.gases 의 JSON 줄(판단 B)
  amount_problem   요청의 금액 글자 검사: 0 이상 · 소수 6자리 · 정수 18자리 · 지수·부호 0(DB Decimal(24,6) 과 같은 꼴)
  unit_options     행 단위로 고를 수 있는 것: 잎 단위 + 같은 종류에서 잎 단위로 환산 쌍이 있는 단위
  conversions_of   환산표 파일(inventory/data/unit-conversions.json)의 줄 → {(from, to): Decimal}(쌍 그대로 — 역·다단 0)
  restore_problem  복구(S12)가 안 되는 까닭 하나(판단 D) — 히스토리의 restorable 과 복구 판정이 같이 쓴다
  (②) 요청·보기 꼴(RowInput·IndexDetail·RowList·HistoryPage …) · row_total·sum_or_none(N/A·빈 행은 합에서 빠짐 —
  판단 10. 합은 넉넉한 정밀도 문맥에서 — 470 M3) · paths_of(뿌리부터의 노드 줄 — 리스트의 scopeId·상세의 path)

MAX_ROWS_PER_SAVE·MEMO_MAX·REASON_MAX 는 요청 크기 한도다[우리 해석 — 화면 스펙에 수 없음]. 배출계수 같은 수치가 아니다.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from typing import Final

from esgapi.core.auth.principal import Kind
from esgapi.inventory.calc.entry_emission import EMISSION_UNIT, Gas, Version
from esgapi.inventory.service.utils.ghg_pool import (
    UNITS,
    FactorValues,
    FactorView,
    GasValues,
    NodeView,
    parse_decimal,
    unit_kind,
)
from esgapi.inventory.service.utils.ghg_pool import decimal_text as pool_decimal_text

MAX_ROWS_PER_SAVE: Final = 200  # [우리 해석]
MEMO_MAX: Final = 2000  # [우리 해석]
AMOUNT_DECIMALS: Final = 6  # inventory_entry_values.amount 의 decimal_places
REASON_MAX: Final = 500  # [우리 해석] 계수 바꿈·복구의 사유
# DB CHECK(inventory_entry_values_slot_format — 0004)와 같은 글자: 월 `YYYY-MM` · 분기 `YYYY-Qn` · 연 `YYYY`
SLOT_PATTERN: Final = r"^[0-9]{4}(-(0[1-9]|1[0-2]|Q[1-4]))?$"
# S12a-2 +3: unit(행 단위 바뀜 — 470 M2) · period(블록 입력주기 바뀜 — S7) · factor(행 계수 바꿈 — S9·S11)
HISTORY_KINDS: Final = ("value", "na_on", "na_off", "unit", "period", "factor")
RESTORABLE: Final = ("value", "period", "factor")  # 복구(S12)가 되는 종류 — 판단 D·F
PERIODS: Final = ("month", "quarter", "year")  # 입력주기(S7). 주기 행이 없는 블록은 month
DEFAULT_PERIOD: Final = "month"
_SUM_PRECISION: Final = 60  # Decimal(30,12) 여럿의 합이 잘리지 않는 자릿수(470 M3 — 기본 문맥은 28)

Conversions = Mapping[tuple[str, str], Decimal]


def slots(year: int, period: str = DEFAULT_PERIOD) -> tuple[str, ...]:
    """그 해의 입력 칸: month 월 열둘 · quarter 분기 넷 · year 연 하나. 목록 밖 주기는 ValueError."""
    if period == "month":
        return tuple(f"{year:04d}-{month:02d}" for month in range(1, 13))
    if period == "quarter":
        return tuple(f"{year:04d}-Q{quarter}" for quarter in range(1, 5))
    if period == "year":
        return (f"{year:04d}",)
    raise ValueError(f"입력주기가 아니다: {period!r}")


def amount_problem(text: str) -> str | None:
    """금액 글자가 저장할 수 있는 꼴이면 None, 아니면 까닭."""
    value = parse_decimal(text)
    if value is None:
        return "0 이상의 숫자로 입력해 주세요. 정수 부분은 18자리까지, 1E+5 같은 지수 표기 없이 넣어 주세요"
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > AMOUNT_DECIMALS:
        return f"소수점 아래는 {AMOUNT_DECIMALS}자리까지 입력할 수 있어요"
    return None


def conversions_of(rows: Iterable[Mapping[str, object]]) -> dict[tuple[str, str], Decimal]:
    """환산표 줄 → {(from, to): factor}. 값은 글자 그대로 Decimal 로(정의값 — 새 수치 0)."""
    return {(str(row["from"]), str(row["to"])): Decimal(str(row["factor"])) for row in rows}


def unit_options(leaf_unit: str, conversions: Conversions) -> tuple[str, ...]:
    """잎 단위를 먼저, 그다음 같은 종류(UNITS 차례)에서 「그 단위 → 잎 단위」 쌍이 있는 것."""
    kind = unit_kind(leaf_unit)
    others = tuple(unit for unit in UNITS.get(kind or "", ()) if unit != leaf_unit and (unit, leaf_unit) in conversions)
    return (leaf_unit, *others)


CUSTOM_UNIT_MISMATCH: Final = "이 시설의 단위로 바꿀 수 없는 계수 단위다"  # [우리 해석] sid:MARC-ISSUE-548
# [우리 해석] sid:MARC-ISSUE-558 — 웹이 이 글을 창 줄에 그대로 보여서 해요체다
POOL_UNIT_MISMATCH: Final = "이 시설의 단위로 계산할 수 없는 배출계수예요. 다른 배출계수를 골라 주세요"


def _convertible(source: str, target: str, conversions: Conversions) -> bool:
    """셈(calc/entry_emission.py 의 _rate)과 같은 규칙: 같은 단위이거나 환산표에 그 쌍이 있다(역·다단 유도 0)."""
    return source == target or (source, target) in conversions


def custom_unit_problem(
    row_units: Sequence[str], values: FactorValues | FactorView, conversions: Conversions
) -> dict[str, str]:
    """계수(직접입력 또는 풀의 판)를 행 단위들(잎 1차 단위의 unit_options) 하나하나로 셈할 수 있는지
    (sid:MARC-ISSUE-548).
    셈의 차례 그대로: 행 단위 → 투입(못 하면 custom.inputUnit) → 분모(켬 ncvUnit→분모 = custom.ncvUnit /
    끔 투입→분모 = custom.factorUnit) → 분자 → t(custom.factorUnit). 다 되면 {}.
    계수 단위 꼴은 check_factor 가 이미 봤다."""
    errors: dict[str, str] = {}
    input_unit = values.input_unit[1]
    if any(not _convertible(unit, input_unit, conversions) for unit in row_units):
        errors["custom.inputUnit"] = CUSTOM_UNIT_MISMATCH
    numerator, _, denominator = values.factor_unit.partition("/")
    if values.ncv_unit is not None:
        if not _convertible(values.ncv_unit[1], denominator, conversions):
            errors["custom.ncvUnit"] = CUSTOM_UNIT_MISMATCH
    elif not _convertible(input_unit, denominator, conversions):
        errors["custom.factorUnit"] = CUSTOM_UNIT_MISMATCH
    if not _convertible(numerator, EMISSION_UNIT, conversions):
        errors["custom.factorUnit"] = CUSTOM_UNIT_MISMATCH
    return errors


def pool_unit_problem(row_units: Sequence[str], view: FactorView, conversions: Conversions) -> dict[str, str]:
    """고른 풀 계수의 판을 custom_unit_problem 과 같게 대조한다(sid:MARC-ISSUE-558). 고칠 칸이 없어 키는 factorId."""
    return {"factorId": POOL_UNIT_MISMATCH} if custom_unit_problem(row_units, view, conversions) else {}


# ── 요청·보기(②) — 경로가 HTTP 로 바꾼다 ───────────────────────────


@dataclass(frozen=True)
class Actor:
    """쓰는 사람: kind(service = 고객사 사용자 · admin = 운영 관리자)와 users.pk."""

    kind: Kind
    user_id: int


@dataclass(frozen=True)
class SlotInput:
    """요청의 월 칸 하나. amount 는 Decimal 글자(None = 빈 칸)."""

    slot: str
    amount: str | None
    estimated: bool = False


@dataclass(frozen=True)
class RowInput:
    """요청의 행 하나. row_id None = 새 행(그 자산/시설에 살아 있는 행이 없어야 한다). values 는 준 칸만 바꾼다."""

    site_facility_id: int
    unit: str
    na: bool = False
    values: Sequence[SlotInput] = ()
    row_id: int | None = None


@dataclass(frozen=True)
class Locked:
    """잠긴 인덱스다(409 locked — 아무것도 바꾸지 않았다)."""


@dataclass(frozen=True)
class SlotValue:
    slot: str
    amount: Decimal | None
    estimated: bool


@dataclass(frozen=True)
class RowView:
    """상세의 입력 행 하나(살아 있는 행 — 꺼진·지운 사업장의 행은 빠진다)."""

    id: int
    site_facility_id: int
    detail_name: str
    unit: str
    na: bool
    values: tuple[SlotValue, ...]
    emission: Decimal | None
    emission_problem: str | None
    factor: "FactorView | CustomView | None" = None  # S12a-2: None = 선택의 잡은 판(판단 C)
    factor_version_id: int | None = None  # S12a-2: factor 가 판 보기일 때 그 판 id(응답 versionId)


@dataclass(frozen=True)
class FacilityLine:
    """사업장의 그 잎 코드 자산/시설 한 줄(행을 새로 세울 자리). has_row = 살아 있는 행이 있음."""

    id: int
    detail_name: str
    has_row: bool


@dataclass(frozen=True)
class SiteBlock:
    site_id: int
    site_name: str
    facilities: tuple[FacilityLine, ...]
    rows: tuple[RowView, ...]
    period: str = DEFAULT_PERIOD  # S12a-2 입력주기(S7) — 행 값은 이 주기의 칸만
    slots: tuple[str, ...] = ()


@dataclass(frozen=True)
class SiteTotals:
    site_id: int
    site_name: str
    values: Mapping[int, Decimal | None]


@dataclass(frozen=True)
class Totals:
    """Y-2·Y-1·Y 의 tCO2-eq 합(켠 사업장만). 그 해 셈한 행이 하나도 없으면 None(「-」)."""

    years: tuple[int, ...]
    all: Mapping[int, Decimal | None]
    by_site: tuple[SiteTotals, ...]


@dataclass(frozen=True)
class IndexDetail:
    """S3 상세. factor 는 잡은 판(선택 행의 factor_version — 요청에서 받지 않는다)."""

    year: int
    node_id: int
    name: str
    path: tuple[str, ...]
    decimals: int
    memo: str
    locked_at: datetime | None
    locked_by: tuple[int, str] | None
    unit_options: tuple[str, ...]
    factor_version_id: int
    factor: FactorView
    totals: Totals
    sites: tuple[SiteBlock, ...]


@dataclass(frozen=True)
class YearLine:
    year: int
    configured: bool


@dataclass(frozen=True)
class ListRow:
    """S2 리스트 한 줄(숨기지 않은 선택 잎 하나)."""

    node_id: int
    path: tuple[str, ...]
    values: Mapping[int, Decimal | None]
    has_memo: bool
    estimated: bool
    locked: bool


@dataclass(frozen=True)
class ScopeGroup:
    """뿌리 노드(Scope) 하나 아래의 줄과 그 합(판단 8)."""

    scope_id: int
    scope_name: str
    values: Mapping[int, Decimal | None]
    rows: tuple[ListRow, ...]


@dataclass(frozen=True)
class RowList:
    year: int
    years: tuple[int, ...]
    configured: bool
    decimals: int
    scopes: tuple[ScopeGroup, ...]


@dataclass(frozen=True)
class HistoryLine:
    id: int
    at: datetime
    kind: str
    slot: str | None
    before: str | None
    after: str | None
    unit: str
    actor_kind: str
    actor_user_id: int | None
    actor_name: str | None
    reason: str | None = None  # S12a-2: 계수 바꿈·복구의 사유
    restorable: bool = False  # S12a-2: restore_problem 이 None(판단 D)
    before_factor: "FactorRef | None" = None  # S12a-2: factor 줄의 앞뒤 계수
    after_factor: "FactorRef | None" = None


@dataclass(frozen=True)
class HistoryPage:
    count: int
    lines: tuple[HistoryLine, ...]


# ── S12a-2(S7·S9·S11·S12) ─────────────────────────────────────────


@dataclass(frozen=True)
class CustomView:
    """행 전용 직접입력 계수 하나(inventory_custom_factors — 고치지 않는다). 셈은 custom_version."""

    id: int
    name: str
    source: str
    base_year: int
    tier: int
    country_code: str
    industry_code: str
    input_unit: tuple[str, str]
    ncv: Decimal | None
    ncv_unit: tuple[str, str] | None
    factor_unit: str
    gases: tuple[GasValues, ...]
    note: str
    created_at: datetime

    @property
    def is_custom(self) -> bool:
        return True


@dataclass(frozen=True)
class FactorRef:
    """히스토리 factor 줄의 앞 또는 뒤 계수: 풀 판(version_id) 또는 직접입력(custom_id) 하나와 이름."""

    version_id: int | None
    custom_id: int | None
    name: str

    @property
    def is_custom(self) -> bool:
        return self.custom_id is not None


@dataclass(frozen=True)
class RestoreStale:
    """그 줄의 뒤 상태로 되돌릴 수 없다(409 restore_stale — 칸이 지금 주기 밖·단위 바뀜·지운 풀 계수). 0 바뀜."""


RESTORE_KIND: Final = "kind"  # 복구 안 되는 종류(na_on·na_off·unit)
RESTORE_TOP: Final = "top"  # 그 행의 맨 위(가장 새) 줄
RESTORE_LOCKED: Final = "locked"
RESTORE_STALE: Final = "stale"


def restore_problem(kind: str, *, top: bool, locked: bool, stale: bool) -> str | None:
    """복구가 안 되는 까닭(판단 D) — 차례대로 첫 하나. None 이면 복구 가능(히스토리의 restorable)."""
    if kind not in RESTORABLE:
        return RESTORE_KIND
    if top:
        return RESTORE_TOP
    if locked:
        return RESTORE_LOCKED
    if stale:
        return RESTORE_STALE
    return None


def reason_text(text: str | None) -> str | None:
    """사유의 앞뒤 공백을 걷는다. 비면 None."""
    if text is None:
        return None
    cleaned = text.strip()
    return cleaned or None


def custom_gases(gases: Sequence[GasValues]) -> list[dict[str, object]]:
    """check_factor 를 지난 가스 줄 → inventory_custom_factors.gases 의 JSON 줄(Decimal 은 지수 없는 글자로 —
    custom_version 이 그 글자를 다시 Decimal 로 읽는다)."""
    return [
        {
            "gas": gas.gas,
            "enabled": gas.enabled,
            "factor": None if gas.factor is None else pool_decimal_text(gas.factor),
            "gwp": None if gas.gwp is None else pool_decimal_text(gas.gwp),
        }
        for gas in gases
    ]


def list_years(year: int) -> tuple[int, ...]:
    """리스트·상세 합의 세 해(Y-2·Y-1·Y — 스펙-1 S2 [우리 해석])."""
    return (year - 2, year - 1, year)


def decimal_text(value: Decimal | None) -> str | None:
    """히스토리 칸의 Decimal 글자(뒤 0 을 걷는다 — 1.500000 → 1.5). None 은 빈 칸."""
    if value is None:
        return None
    return f"{value.normalize():f}"


def row_total(na: bool, amounts: Iterable[Decimal | None]) -> Decimal | None:
    """행의 활동량 합. N/A 거나 값이 하나도 없으면 None(셈하지 않는다 — 판단 10)."""
    if na:
        return None
    found = [amount for amount in amounts if amount is not None]
    if not found:
        return None
    with localcontext(prec=_SUM_PRECISION):
        return sum(found, Decimal(0))


def sum_or_none(values: Iterable[Decimal | None]) -> Decimal | None:
    """합. 셈한 값이 하나도 없으면 None(N/A·빈 행은 합에서 빠진다)."""
    found = [value for value in values if value is not None]
    if not found:
        return None
    with localcontext(prec=_SUM_PRECISION):
        return sum(found, Decimal(0))


def gases_of(lines: Sequence[Mapping[str, object]]) -> tuple[GasValues, ...]:
    """inventory_custom_factors.gases 의 JSON 줄 → 가스 값(custom_gases 의 거꾸로). 넣는 길은 insert_custom 하나라
    글자는 늘 check_factor 를 지난 숫자다 — 꼴이 아닌 글자는 빈 값(None)으로 읽어 500 을 내지 않는다(검증 5d 권고 1)."""
    found: list[GasValues] = []
    for line in lines:
        factor, gwp = line.get("factor"), line.get("gwp")
        found.append(
            GasValues(
                gas=str(line.get("gas")),
                enabled=line.get("enabled") is True,
                factor=parse_decimal(factor) if isinstance(factor, str) else None,
                gwp=parse_decimal(gwp) if isinstance(gwp, str) else None,
            )
        )
    return tuple(found)


def custom_version(view: CustomView) -> Version:
    """직접입력 계수의 셈 칸(판의 calc_version 과 같은 꼴 — 켠 가스 가운데 계수·GWP 가 다 있는 것만)."""
    return Version(
        input_unit=view.input_unit[1],
        ncv=view.ncv,
        ncv_unit=view.ncv_unit[1] if view.ncv_unit is not None else None,
        factor_unit=view.factor_unit,
        gases=tuple(
            Gas(factor=gas.factor, gwp=gas.gwp)
            for gas in view.gases
            if gas.enabled and gas.factor is not None and gas.gwp is not None
        ),
    )


def paths_of(nodes: Iterable[NodeView]) -> dict[int, tuple[NodeView, ...]]:
    """노드 id → 뿌리부터 그 노드까지의 줄(삭제 안 된 노드만 — 끊긴 줄은 빠진다)."""
    by_id = {node.id: node for node in nodes}
    found: dict[int, tuple[NodeView, ...]] = {}

    def walk(node_id: int) -> tuple[NodeView, ...] | None:
        if node_id in found:
            return found[node_id]
        node = by_id.get(node_id)
        if node is None:
            return None
        if node.parent_id is None:
            line: tuple[NodeView, ...] | None = (node,)
        else:
            up = walk(node.parent_id)
            line = None if up is None else (*up, node)
        if line is not None:
            found[node_id] = line
        return line

    for node_id in by_id:
        walk(node_id)
    return found
