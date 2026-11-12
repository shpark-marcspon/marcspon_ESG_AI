"""계수 낱줄 → 후보(`Factor`)의 판정과, 목록을 받는 카탈로그. esg-lab `adapters/jsonlFactorCatalog.ts` 의 규칙을 옮겼다.

파일을 읽지 않는다: 낱줄은 값으로 받는다(업무 층이 `reference` 의 selector 에서 읽어 넘긴다).

후보 자격은 넷이다: `record_type == "emission_factor"` · `gas == "CO2e"` · `value` 가 None 아님 ·
Scope 3 범주가 하나 이상.
기체별 행, 값 없는 행, 발열량·에너지 환산 낱줄은 후보가 아니다.

★ `value_raw` 의 규칙(이 밴드): Scope 3 의 계산은 `value_raw` 를 엄격 십진(`-?[0-9]+(\\.[0-9]+)?`, 64자)으로만 읽는다.
  지수 표기(`9e-05`)·쉼표·공백·단위 붙은 값은 받지 않는다. 십진으로 푸는 규칙을 새로 더하지 않는다.
  음수는 받는다(TS 의 `isDecimalString` 그대로).
  자격을 갖췄는데 이 규칙에 걸리는 줄은 조용히 빼지 않는다: 그 줄만 후보에서 빼고 `rejected` 에 싣는다.
  TS 는 표 전체를 예외로 거부했다. 여기서는 요청마다 표를 다시 읽는 서버에서 줄 하나가 기능 전체를 멈추지 않게 했다.
  무효 조건: 기체별 행(CH4·N2O)을 Scope 3 가 읽게 되면 지수 표기 460건이 여기 걸린다. 그때 규칙을 다시 연다.
  (조립용 규칙은 `reference/calc/value_raw.py` 에 따로 있다: 그쪽은 세 자리 쉼표를 풀어 받고 음수를 거절한다.)
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal, cast

from esgapi.core.calc.decimal import parse_external_decimal
from esgapi.inventory.engines.scope3.llm_first_1.types import (
    Basis,
    CandidateQuery,
    Factor,
    FactorClassification,
    LicenseStatus,
    SpendInfo,
)
from esgapi.inventory.engines.scope3.llm_first_1.units import unit_dim


@dataclass(frozen=True, slots=True)
class RawRecord:
    """계수 낱줄에서 추리기와 계산이 읽는 칸. `value`(float)는 「값이 있는가」만 본다. 계산에 닿지 않는다."""

    id: str
    record_type: str
    gas: str
    value: float | None
    value_raw: str | None
    scope3_categories: tuple[int, ...]
    factor_type: str
    name_original: str
    category_path: tuple[str, ...]
    unit: str
    unit_numerator: str
    unit_denominator: str
    license_status: str
    source_id: str
    region: str
    classification: Mapping[str, object] | None
    spend: Mapping[str, object] | None


NotCandidateReason = Literal["not_emission_factor", "not_co2e", "no_value", "no_scope3_category"]


@dataclass(frozen=True, slots=True)
class NotCandidate:
    """후보 자격 넷 가운데 하나가 없다. 오류가 아니다(표에는 그런 줄이 많다)."""

    id: str
    reason: NotCandidateReason


@dataclass(frozen=True, slots=True)
class Rejected:
    """자격은 갖췄는데 후보로 쓸 수 없는 줄. 조용히 빼지 않고 응답에 싣는다."""

    id: str
    reason: Literal["invalid_value_raw"] = "invalid_value_raw"


def judge(record: RawRecord) -> Factor | NotCandidate | Rejected:
    if record.record_type != "emission_factor":
        return NotCandidate(record.id, "not_emission_factor")
    if record.gas != "CO2e":
        return NotCandidate(record.id, "not_co2e")
    if record.value is None:
        return NotCandidate(record.id, "no_value")
    if not record.scope3_categories:
        return NotCandidate(record.id, "no_scope3_category")
    if record.value_raw is None or parse_external_decimal(record.value_raw) is None:
        return Rejected(record.id)
    classification = record.classification
    spend = record.spend
    return Factor(
        id=record.id,
        name=record.name_original,
        category_path=record.category_path,
        factor_type=cast("Basis", record.factor_type),
        scope3_categories=record.scope3_categories,
        unit=record.unit,
        unit_numerator=record.unit_numerator,
        unit_denominator=record.unit_denominator,
        denominator_dim=unit_dim(record.unit_denominator),
        value_raw=record.value_raw,
        license_status=cast("LicenseStatus", record.license_status),
        source_id=record.source_id,
        region=record.region,
        classification=(
            None
            if classification is None
            else FactorClassification(str(classification["system"]), str(classification["code"]))
        ),
        spend=(
            None
            if spend is None
            else SpendInfo(str(spend["currency"]), cast("int", spend["price_year"]), str(spend["price_basis"]))
        ),
    )


class ListFactorCatalog:
    """받은 낱줄의 차례가 곧 「표 순서」다(동점을 가르는 마지막 기준). 차례를 정하는 것은 부르는 쪽이다."""

    def __init__(self, records: Iterable[RawRecord]) -> None:
        ordered: list[Factor] = []
        rejected: list[Rejected] = []
        not_candidates = 0
        for record in records:
            judged = judge(record)
            if isinstance(judged, Factor):
                ordered.append(judged)
            elif isinstance(judged, Rejected):
                rejected.append(judged)
            else:
                not_candidates += 1
        self._ordered = tuple(ordered)
        self._by_id = {factor.id: factor for factor in ordered}
        self.rejected: tuple[Rejected, ...] = tuple(rejected)
        self.not_candidate_count = not_candidates

    @property
    def candidate_count(self) -> int:
        return len(self._ordered)

    def all(self) -> tuple[Factor, ...]:
        """후보가 될 수 있는 계수 전부(표의 순서)."""
        return self._ordered

    def get(self, factor_id: str) -> Factor | None:
        """후보가 될 수 있는 계수만 돌려준다. 후보가 아닌 낱줄의 id 와 없는 id 는 None."""
        return self._by_id.get(factor_id)

    def candidates(self, query: CandidateQuery) -> list[Factor]:
        """조건에 맞는 후보(표의 순서). 빈 목록은 「조건에 맞는 계수가 없다」는 뜻이다."""
        excluded = set(query.exclude_license_statuses)
        return [
            factor
            for factor in self._ordered
            if query.category in factor.scope3_categories
            and ((factor.factor_type == "spend") == (query.basis == "spend"))
            and factor.license_status not in excluded
        ]
