"""Scope 3 의 두 길이 같은 규칙으로 후보를 고르고 같은 루프로 묶음을 분류하는가(밴드 CU1 ③④). 순수 층.

두 길: 업무 층의 `scope3_shortlist`·`scope3_classify`(service/services/inventory.py)와 순수 층의 파이프라인
(`decide_group`·`run_pipeline`, engines/scope3/llm_first_1/pipeline.py). 밴드 CU1 전에는 「활동량 후보 →
단위 환산이 되는 것만 → 없으면 지출, 사유 unit_mismatch·no_activity_candidates」와 「행 → 묶음 → 묶음마다 분류」를
두 벌로 적었다.
이 파일은 걷기 전 코드에서도 초록이었다: 기댓값은 그때 잰 값을 글자로 적은 것이다.

★ 계수는 전부 가상(synthetic)이다(scope3_catalog_support 의 HELPER_RECORDS).
"""

from dataclasses import dataclass

import pytest

from esgapi.inventory.engines.scope3.llm_first_1.catalog import ListFactorCatalog, RawRecord
from esgapi.inventory.engines.scope3.llm_first_1.llm_steps import Classification, LlmFailure, LlmUsage
from esgapi.inventory.engines.scope3.llm_first_1.pipeline import (
    ClassificationFailed,
    NoCandidates,
    PipelineRejected,
    PipelineResult,
    Recommended,
    UnsupportedCategory,
    run_pipeline,
)
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import DEFAULT_SHORTLIST_METHOD
from esgapi.inventory.engines.scope3.llm_first_1.types import (
    CandidateBasis,
    FallbackReason,
    InputRow,
    SupportedCategory,
)
from esgapi.inventory.service.services import inventory as services
from esgapi.inventory.tests.scope3_catalog_support import HELPER_RECORDS, catalog_from
from esgapi.inventory.tests.scope3_llm_support import Harness, classification, harness, heuristic_reply
from esgapi.inventory.tests.scope3_support import row, transport

STEEL = ("syn:pp-kg", "syn:steel-kg", "syn:steel-t")
SPEND = ("syn:spend-computer", "syn:spend-legal", "syn:spend-storage")


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    category: SupportedCategory
    row: InputRow
    # (쓴 기반, 지출로 넘어간 까닭, 후보 id 들) — 후보가 없으면 기반은 None
    expected: tuple[CandidateBasis | None, FallbackReason | None, tuple[str, ...]]
    records: tuple[RawRecord, ...] = HELPER_RECORDS


CASES = [
    Case("후보 있음(kg → kg·t)", 1, row("합성 강판", unit="kg"), ("physical", None, STEEL)),
    Case(
        "후보 있음(운송 → tonne.km)",
        9,
        row("강판 운송", unit=None, transport=transport()),
        ("physical", None, ("syn:truck",)),
    ),
    Case("환산 안 됨 → 지출", 1, row("합성 강판", unit="kWh"), ("spend", "unit_mismatch", SPEND)),
    Case("활동량 후보 0 → 지출", 2, row("노트북", unit="kg"), ("spend", "no_activity_candidates", SPEND)),
    Case("환산 안 됨·지출 0 → 후보 없음", 6, row("출장 숙박", unit="kg"), (None, "unit_mismatch", ())),
    Case("환산 안 됨(km ↔ passenger.km)·지출 0", 7, row("통근", unit="km"), (None, "unit_mismatch", ())),
    Case("빈 표 → 후보 없음", 1, row("합성 강판", unit="kg"), (None, "no_activity_candidates", ()), records=()),
]


def catalog(records: tuple[RawRecord, ...] = HELPER_RECORDS) -> ListFactorCatalog:
    return catalog_from(records, "file")


def by_shortlist(case: Case, basis: CandidateBasis | None = None) -> tuple[object, ...]:
    result = services.scope3_shortlist(
        row=case.row,
        category=case.category,
        keywords=(),
        basis=basis,
        method=DEFAULT_SHORTLIST_METHOD,
        bigrams=True,
        size=50,
        catalog=catalog(case.records),
    )
    if isinstance(result, services.Scope3NoCandidates):
        return (None, result.physical, ())
    assert result.total == len(result.factors)
    return (result.basis, result.fallback_reason, tuple(sorted(factor.id for factor in result.factors)))


def by_pipeline(case: Case) -> tuple[object, ...]:
    """분류는 그 범주로 심고, 추천은 추린 목록의 앞 순서(규칙 응답기)로 받는다."""
    setup = harness(catalog(case.records), shortlist_size=50)
    setup.mock.enqueue_text(classification(case.category)).enqueue(heuristic_reply)
    result = run_pipeline([case.row], setup.options)
    assert isinstance(result, PipelineResult)
    group = result.groups[0]
    decision = group.decision
    if isinstance(decision, NoCandidates):
        assert group.shortlists == ()
        return (None, decision.physical, ())
    assert isinstance(decision, Recommended)
    (trace,) = group.shortlists
    reason = decision.basis.fallback_reason
    assert trace.total == len(trace.shown_ids)
    return (trace.basis, reason, tuple(sorted(trace.shown_ids)))


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_the_two_paths_pick_the_same_candidates(case: Case) -> None:
    assert by_shortlist(case) == case.expected
    assert by_pipeline(case) == case.expected


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_a_shortlist_that_names_its_basis(case: Case) -> None:
    """기반을 고른 요청은 업무 층의 길에만 있다: spend 는 활동량을 보지 않고, physical 은 지출로 넘어가지 않는다."""
    has_spend = case.category in (1, 2) and case.records
    assert by_shortlist(case, "spend") == (("spend", None, SPEND) if has_spend else (None, None, ()))
    basis, reason, ids = case.expected
    assert by_shortlist(case, "physical") == ((basis, reason, ids) if basis == "physical" else (None, reason, ()))


# ── ④ 행 → 묶음 → 묶음마다 분류 ──

ROWS = [
    row("합성 강판", row_id="a"),
    row("합성강판", row_id="b"),  # a 와 한 묶음
    row("폐기물 처리", row_id="c"),
    row("!!!", row_id="d"),  # 품목명 키가 비면 행 하나가 한 묶음
    row("!!!", row_id="e"),
    row("출장 숙박", row_id="f", unit="박"),  # 이 묶음은 응답을 심지 않아 호출이 실패한다
]
# 앞 넷은 「other」 — 파이프라인이 추천으로 넘어가지 않고 분류에서 멈춘다(UnsupportedCategory).
REPLIES = 4


type Found = tuple[str, tuple[str, ...], Classification | LlmFailure]


@dataclass(frozen=True, slots=True)
class Classified:
    """묶음마다 (키, 행 id, 분류 또는 실패), 사용량, 모의 공급사가 받은 호출 수."""

    groups: tuple[Found, ...]
    usage: LlmUsage
    calls: int


def setup_with_replies() -> Harness:
    setup = harness(catalog())
    for _ in range(REPLIES):
        setup.mock.enqueue_text(classification("other", ["waste"]))
    return setup


def classified_by_service(monkeypatch: pytest.MonkeyPatch, rows: list[InputRow]) -> Classified | tuple[str, str]:
    setup = setup_with_replies()
    monkeypatch.setattr(services, "scope3_gateway", lambda: setup.client)
    result = services.scope3_classify(rows=rows, company_id=7)
    if isinstance(result, services.Scope3DuplicateRowId):
        return ("duplicate_row_id", result.row_id)
    assert isinstance(result, services.Scope3Classified)
    groups = tuple(
        (g.key, g.row_ids, g.classification if isinstance(g, services.Scope3GroupClassified) else g.llm)
        for g in result.groups
    )
    return Classified(groups, result.usage, len(setup.mock.calls))


def classified_by_pipeline(rows: list[InputRow]) -> Classified | tuple[str, str]:
    setup = setup_with_replies()
    result = run_pipeline(rows, setup.options)
    if isinstance(result, PipelineRejected):
        assert result.row_id is not None
        return (result.kind, result.row_id)
    groups: list[Found] = []
    for group in result.groups:
        decision = group.decision
        assert isinstance(decision, UnsupportedCategory | ClassificationFailed)
        found = decision.classification if isinstance(decision, UnsupportedCategory) else decision.llm
        groups.append((group.key, group.row_ids, found))
    return Classified(tuple(groups), result.usage, len(setup.mock.calls))


def test_the_two_paths_group_and_classify_alike(monkeypatch: pytest.MonkeyPatch) -> None:
    service = classified_by_service(monkeypatch, ROWS)
    assert service == classified_by_pipeline(ROWS)
    assert isinstance(service, Classified)
    assert [(key, row_ids) for key, row_ids, _ in service.groups] == [
        ("합성강판|kg|", ("a", "b")),
        ("폐기물처리|kg|", ("c",)),
        ("|kg|#d", ("d",)),
        ("|kg|#e", ("e",)),
        ("출장숙박|room_night|", ("f",)),
    ]
    assert [type(found) for _, _, found in service.groups] == [Classification] * 4 + [LlmFailure]
    assert service.usage.calls == 5
    assert service.calls >= 5


def test_a_duplicate_row_id_stops_both_paths_before_any_call(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [*ROWS, row("다른 품목", row_id="c")]
    assert classified_by_service(monkeypatch, rows) == ("duplicate_row_id", "c")
    assert classified_by_pipeline(rows) == ("duplicate_row_id", "c")
