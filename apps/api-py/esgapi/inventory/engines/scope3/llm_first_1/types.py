"""Scope 3 순수 층의 낱말. esg-lab `ts/scope3/src/domain/types.ts`·`factor.ts` 를 옮긴 것이다.

수량·금액·무게·거리는 십진 문자열이다(연산은 `esgapi/core/calc/decimal.py` 에서만).
"""

from dataclasses import dataclass
from typing import Final, Literal, TypeGuard

from esgapi.inventory.engines.scope3.llm_first_1.units import UnitDim

# AI 를 적용하는 Scope 3 범주: 1·2 구매, 4·9 운송, 6 출장, 7 통근.
SUPPORTED_CATEGORIES: Final = (1, 2, 4, 6, 7, 9)
SupportedCategory = Literal[1, 2, 4, 6, 7, 9]

Confidence = Literal["high", "medium", "low"]
Basis = Literal["activity", "distance", "spend"]
# 후보를 부르는 기반: "physical" 은 활동(물량)·거리 기반, "spend" 는 지출 기반.
CandidateBasis = Literal["physical", "spend"]
# 활동 기반에서 지출 기반으로 넘어간 까닭.
FallbackReason = Literal["no_activity_candidates", "unit_mismatch", "llm_found_none_suitable"]
LicenseStatus = Literal["ok", "disputed", "unverified"]
LICENSE_STATUSES: Final[tuple[LicenseStatus, ...]] = ("ok", "disputed", "unverified")


def is_supported_category(value: object) -> TypeGuard[SupportedCategory]:
    """파이썬에서는 True == 1 이다. bool 이 범주 1 로 통과하지 못하게 타입을 먼저 본다."""
    return type(value) is int and value in SUPPORTED_CATEGORIES


@dataclass(frozen=True, slots=True)
class TransportInfo:
    """운송 행의 부가 정보. 거리는 입력으로 받는다. 없으면 None 이고 추정하지 않는다."""

    origin: str
    destination: str
    mode: str
    weight_kg: str | None
    distance_km: str | None


@dataclass(frozen=True, slots=True)
class InputRow:
    """구매·물류·출장·통근 내역의 한 행."""

    row_id: str
    item_name: str
    quantity: str | None
    unit: str | None
    amount: str | None
    currency: str | None
    date: str
    org_unit: str
    transport: TransportInfo | None


@dataclass(frozen=True, slots=True)
class FactorPick:
    """추천된 계수 하나와 그 선택 이유·신뢰도."""

    factor_id: str
    reason: str
    confidence: Confidence


@dataclass(frozen=True, slots=True)
class FactorClassification:
    system: str
    code: str


@dataclass(frozen=True, slots=True)
class SpendInfo:
    currency: str
    price_year: int
    price_basis: str


@dataclass(frozen=True, slots=True)
class Factor:
    """추천 후보가 될 수 있는 계수 한 건. 값은 원자료 표기(`value_raw`)만 들고 계산 때만 읽는다."""

    id: str
    name: str
    category_path: tuple[str, ...]
    factor_type: Basis
    scope3_categories: tuple[int, ...]
    unit: str
    unit_numerator: str
    unit_denominator: str
    denominator_dim: UnitDim
    value_raw: str
    license_status: LicenseStatus
    source_id: str
    region: str
    classification: FactorClassification | None
    spend: SpendInfo | None


@dataclass(frozen=True, slots=True)
class CandidateQuery:
    category: int
    basis: CandidateBasis
    # 이 이용 조건 상태의 계수를 후보에서 뺀다.
    exclude_license_statuses: tuple[LicenseStatus, ...] = ()
