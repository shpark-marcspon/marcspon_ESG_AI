"""낱줄 → 후보의 판정과 카탈로그. esg-lab `factors.test.ts` 의 「후보 자격」·「기반과 이용 조건」을 옮겼다. 순수 층.

옮기지 않은 둘: 파일이 없거나 깨졌을 때의 예외(파일을 읽지 않는다), 실제 표의 271 → 73(§4 의 컨테이너 curl 이 잰다).
"""

from dataclasses import replace

import pytest

from esgapi.inventory.engines.scope3.llm_first_1.catalog import ListFactorCatalog, NotCandidate, Rejected, judge
from esgapi.inventory.engines.scope3.llm_first_1.types import CandidateQuery, Factor, FactorClassification, SpendInfo
from esgapi.inventory.tests.scope3_catalog_support import HELPER_RECORDS, catalog_from, synthetic_record


def ids(factors: list[Factor]) -> list[str]:
    return [factor.id for factor in factors]


def test_only_co2e_emission_factors_with_a_value_are_candidates() -> None:
    catalog = ListFactorCatalog(HELPER_RECORDS)
    assert len(HELPER_RECORDS) == 10
    assert catalog.candidate_count == 8
    assert catalog.not_candidate_count == 2
    assert catalog.rejected == ()
    assert catalog.get("syn:steel-kg-ch4") is None
    assert catalog.get("syn:empty") is None
    assert catalog.get("없는 id") is None
    steel = catalog.get("syn:steel-kg")
    assert steel is not None
    assert steel.denominator_dim == "kg"
    assert steel.category_path == ("합성 자재", "금속")
    computer = catalog.get("syn:spend-computer")
    assert computer is not None
    assert computer.spend == SpendInfo("USD", 2022, "purchaser")
    assert computer.classification == FactorClassification("NAICS 2017", "334111")
    assert computer.denominator_dim == "usd_2022_purchaser"


def test_each_missing_qualification_has_its_own_reason() -> None:
    base = synthetic_record("syn:x", "x", (1,), "activity", "kg", "1")
    assert isinstance(judge(base), Factor)
    assert judge(replace(base, record_type="heating_value")) == NotCandidate("syn:x", "not_emission_factor")
    assert judge(replace(base, gas="CH4")) == NotCandidate("syn:x", "not_co2e")
    assert judge(replace(base, value=None)) == NotCandidate("syn:x", "no_value")
    assert judge(replace(base, scope3_categories=())) == NotCandidate("syn:x", "no_scope3_category")


def test_physical_and_spend_split_and_license_filter() -> None:
    catalog = ListFactorCatalog(HELPER_RECORDS)
    physical = catalog.candidates(CandidateQuery(1, "physical"))
    assert ids(physical) == ["syn:steel-kg", "syn:steel-t", "syn:pp-kg"]
    kept = catalog.candidates(CandidateQuery(1, "physical", ("disputed", "unverified")))
    assert ids(kept) == ["syn:steel-kg", "syn:steel-t"]
    assert catalog.candidates(CandidateQuery(2, "physical")) == []
    assert len(catalog.candidates(CandidateQuery(2, "spend"))) == 3
    # 거리 기반도 "physical" 이다.
    assert ids(catalog.candidates(CandidateQuery(4, "physical"))) == ["syn:truck"]
    assert catalog.candidates(CandidateQuery(4, "spend")) == []


@pytest.mark.parametrize(
    "value_raw",
    ["9e-05", "9E-05", "73,200", " 1.5", "1.5 ", "1.5 kg", "+1", ".5", "5.", "１.５", "", "1" * 65, None],
)
def test_a_qualified_line_with_a_non_strict_value_raw_is_rejected_not_dropped(value_raw: str | None) -> None:
    """지수 표기·쉼표·공백·단위 붙은 값·전각·64자 초과는 받지 않는다. 십진으로 풀지 않는다."""
    line = replace(
        synthetic_record("syn:bad", "합성 지수 표기 (synthetic)", (1,), "activity", "kg", "1"), value_raw=value_raw
    )
    assert judge(line) == Rejected("syn:bad", "invalid_value_raw")
    catalog = ListFactorCatalog([*HELPER_RECORDS, line])
    # 그 줄만 빠진다(표 전체를 거부하지 않는다). 그리고 빠진 것이 남는다.
    assert catalog.candidate_count == 8
    assert catalog.get("syn:bad") is None
    assert catalog.rejected == (Rejected("syn:bad"),)
    assert "syn:bad" not in ids(catalog.candidates(CandidateQuery(1, "physical")))


@pytest.mark.parametrize("value_raw", ["0", "-0.5", "12", "0.000092", "1" * 64])
def test_strict_decimals_including_negatives_are_accepted(value_raw: str) -> None:
    judged = judge(replace(synthetic_record("syn:ok", "x", (1,), "activity", "kg", "1"), value_raw=value_raw))
    assert isinstance(judged, Factor)
    assert judged.value_raw == value_raw


def test_a_gas_row_with_exponent_notation_is_simply_not_a_candidate() -> None:
    """DEFRA 의 지수 표기는 전부 기체별 행이다. 후보 자격이 없으므로 value_raw 를 보지도 않는다."""
    line = replace(synthetic_record("syn:ch4", "x", (1,), "activity", "kg", "1", gas="CH4"), value_raw="9e-05")
    assert judge(line) == NotCandidate("syn:ch4", "not_co2e")
    assert ListFactorCatalog([line]).rejected == ()


def test_table_order_is_the_order_given() -> None:
    by_file = catalog_from(HELPER_RECORDS, "file")
    by_id = catalog_from(HELPER_RECORDS, "id")
    assert ids(list(by_file.all()))[:3] == ["syn:steel-kg", "syn:steel-t", "syn:pp-kg"]
    assert ids(list(by_id.all())) == sorted(ids(list(by_file.all())))
    assert ids(by_id.candidates(CandidateQuery(1, "physical"))) == ["syn:pp-kg", "syn:steel-kg", "syn:steel-t"]
