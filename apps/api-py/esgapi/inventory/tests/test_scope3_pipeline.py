"""묶음의 판단 9갈래와 실행. esg-lab `pipeline.test.ts` 의 스물넷, `ports.test.ts` 의 가짜 포트 둘,
`outputCap.test.ts` 의 상한 하나, `e2e.test.ts` 의 「확정한 매핑을 기억에 넣으면 다음 실행에서 호출 0」을 옮겼다.

순수 층: DB 도 Django 도 쓰지 않는다. 생성 모델은 모의 공급사(심어 둔 응답)뿐이고 소켓 문지기 아래에서 돈다.
"""

import json
from dataclasses import replace

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import CallMeta, LlmResult, Refusal, Success, Usage
from esgapi.inventory.engines.scope3.llm_first_1.calc import Computed, CurrencyAdjustment, NotCalculated
from esgapi.inventory.engines.scope3.llm_first_1.catalog import ListFactorCatalog
from esgapi.inventory.engines.scope3.llm_first_1.llm_steps import (
    CLASSIFY_PROMPT,
    RECOMMEND_PROMPT,
    ClassificationOut,
    LlmUsage,
    RecommendationOut,
)
from esgapi.inventory.engines.scope3.llm_first_1.memory import InMemoryMappingMemory
from esgapi.inventory.engines.scope3.llm_first_1.normalize import group_rows
from esgapi.inventory.engines.scope3.llm_first_1.pipeline import (
    BasisTrace,
    CandidateStats,
    ClassificationFailed,
    MemoryCategoryMismatch,
    MemoryFactorExcluded,
    MemoryFactorMissing,
    NoCandidates,
    NoSuitableFactor,
    PipelineOptions,
    PipelineRejected,
    PipelineResult,
    RecommendationFailed,
    Recommended,
    RowResult,
    UnsupportedCategory,
    decide_group,
    run_pipeline,
)
from esgapi.inventory.engines.scope3.llm_first_1.review import (
    Actor,
    AiProposal,
    accept,
    finalize,
    propose,
    to_memory_entry,
)
from esgapi.inventory.engines.scope3.llm_first_1.serialize import calc_to_dict, decision_to_dict, usage_to_dict
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import lexical_shortlister
from esgapi.inventory.engines.scope3.llm_first_1.types import CandidateQuery, Factor, InputRow
from esgapi.inventory.tests.scope3_catalog_support import HELPER_RECORDS
from esgapi.inventory.tests.scope3_llm_support import (
    ROUTE,
    TAGS,
    Harness,
    classification,
    harness,
    recommendation,
    remembered,
    user_texts,
)
from esgapi.inventory.tests.scope3_support import row, transport

SYNTHETIC_USAGE = Usage(input_tokens=10, output_tokens=1, cache_read_tokens=0, cache_write_tokens=0)


def setup(**options: object) -> Harness:
    return harness(ListFactorCatalog(HELPER_RECORDS), **options)  # type: ignore[arg-type]


def run(h: Harness, rows: list[InputRow]) -> PipelineResult:
    result = run_pipeline(rows, h.options)
    assert isinstance(result, PipelineResult)
    return result


def only(h: Harness, entry: InputRow) -> RowResult:
    return run(h, [entry]).rows[0]


def seed(mock: MockProvider, *texts: str) -> None:
    for text in texts:
        mock.enqueue_text(text)


# ── 확정 매핑 기억 ──


def test_remembered_rows_do_not_call_the_model(blocked_network: list[object]) -> None:
    h = setup(memory=InMemoryMappingMemory([remembered("합성 강판", "syn:steel-kg")]))
    result = run(h, [row("합성 강판", row_id="a"), row("합성강판", row_id="b", quantity="4")])
    assert h.mock.calls == []
    assert result.usage == LlmUsage()
    for entry in result.rows:
        decision = entry.decision
        assert isinstance(decision, Recommended)
        assert (decision.source, decision.category, decision.candidates) == ("memory", 1, None)
        assert [pick.factor_id for pick in decision.picks] == ["syn:steel-kg"]
        assert decision.picks[0].reason == "확정 매핑 기억 (synthetic-reviewer, 2026-09-30T09:00:00+09:00)"
        assert decision.basis == BasisTrace("activity", False, None)
    emissions = [entry.calc.co2e for entry in result.rows if isinstance(entry.calc, Computed)]
    assert emissions == ["0.025", "0.01"]
    assert [group.shortlists for group in result.groups] == [()]
    assert blocked_network == []


def test_only_unremembered_groups_go_to_the_model() -> None:
    h = setup(memory=InMemoryMappingMemory([remembered("합성 강판", "syn:steel-kg")]))
    seed(h.mock, classification(1), recommendation(["syn:pp-kg", "syn:steel-kg"]))
    rows = [row("합성 강판", row_id="a"), row("폴리프로필렌 수지", row_id="b"), row("폴리프로필렌  수지", row_id="c")]
    result = run(h, rows)
    # 묶음당 분류 1회 + 추천 1회.
    assert len(h.mock.calls) == 2
    assert (result.usage.calls, result.usage.attempts) == (2, 2)
    assert set(result.usage.by_prompt) == {CLASSIFY_PROMPT, RECOMMEND_PROMPT}
    assert [entry.decision.source for entry in result.rows] == ["memory", "llm", "llm"]
    third = result.rows[2].decision
    assert isinstance(third, Recommended)
    assert [pick.factor_id for pick in third.picks] == ["syn:pp-kg", "syn:steel-kg"]
    # 겹친 후보는 하나(폴리프로필렌)다. 나머지 둘은 표 순서로 채워졌다.
    assert third.candidates == CandidateStats(total=3, shown=3, lexical_matches=1, method="lexical-v2")
    assert [group.row_ids for group in result.groups] == [("a",), ("b", "c")]


def test_a_remembered_factor_missing_from_the_table_is_a_status_not_a_model_call() -> None:
    h = setup(memory=InMemoryMappingMemory([remembered("합성 강판", "syn:gone")]))
    entry = only(h, row("합성 강판"))
    assert h.mock.calls == []
    assert isinstance(entry.decision, MemoryFactorMissing)
    assert entry.calc == NotCalculated("memory_factor_missing")
    assert calc_to_dict(entry.calc) == {"status": "not_calculated", "reason": "memory_factor_missing"}


def test_a_remembered_category_outside_the_factors_categories_is_a_status() -> None:
    h = setup(memory=InMemoryMappingMemory([remembered("합성 강판", "syn:steel-kg", 6)]))
    entry = only(h, row("합성 강판"))
    assert h.mock.calls == []
    assert isinstance(entry.decision, MemoryCategoryMismatch)
    assert entry.decision.factor_categories == (1,)
    assert decision_to_dict(entry.decision)["factorCategories"] == [1]


def test_a_remembered_factor_excluded_by_license_is_a_status() -> None:
    h = setup(memory=InMemoryMappingMemory([remembered("폴리프로필렌", "syn:pp-kg")]), exclude=("disputed",))
    entry = only(h, row("폴리프로필렌"))
    assert h.mock.calls == []
    assert isinstance(entry.decision, MemoryFactorExcluded)
    assert entry.decision.license_status == "disputed"


# ── 생성 모델은 후보 목록 안의 id 만 고를 수 있다 ──


def test_an_id_in_the_table_but_not_among_the_candidates_is_a_schema_mismatch() -> None:
    h = setup()
    # syn:rail 은 표에 있는 계수지만 범주 6·7 의 것이라 이 품목의 후보 목록에 없다.
    seed(h.mock, classification(1), *[recommendation(["syn:rail"])] * 3)
    result = run(h, [row("합성 강판")])
    decision = result.rows[0].decision
    assert isinstance(decision, RecommendationFailed)
    assert (decision.basis, decision.llm.kind) == ("physical", "schema_mismatch")
    assert result.rows[0].calc == NotCalculated("recommendation_failed")
    # 분류 1회 + 추천 3회(처음 + 스키마 재시도 2회). 거부된 뒤 다른 후보로 넘어가지 않는다.
    assert len(h.mock.calls) == 4
    assert (result.usage.calls, result.usage.attempts) == (2, 4)
    # 추천 호출이 실패했어도 추린 목록은 남는다(「합성」이 겹친 둘이 앞, 겹친 것이 없는 하나가 뒤).
    assert [trace.shown_ids for trace in result.groups[0].shortlists] == [("syn:steel-kg", "syn:pp-kg", "syn:steel-t")]


def test_an_id_not_in_the_table_is_rejected_too() -> None:
    h = setup()
    seed(h.mock, classification(1), *[recommendation(["syn:steel-kg", "syn:invented"])] * 3)
    decision = only(h, row("합성 강판")).decision
    assert isinstance(decision, RecommendationFailed)
    assert decision.llm.kind == "schema_mismatch"


def test_a_factor_excluded_by_license_is_not_a_candidate_so_picking_it_is_rejected() -> None:
    h = setup(exclude=("disputed",))
    seed(h.mock, classification(1), *[recommendation(["syn:pp-kg"])] * 3)
    decision = only(h, row("폴리프로필렌")).decision
    assert isinstance(decision, RecommendationFailed)
    assert decision.llm.kind == "schema_mismatch"
    assert "syn:pp-kg" not in user_texts(h.mock)[1]


def test_answering_with_a_candidate_id_on_the_retry_is_accepted() -> None:
    h = setup()
    seed(h.mock, classification(1), recommendation(["syn:rail"]), recommendation(["syn:steel-kg"]))
    decision = only(h, row("합성 강판")).decision
    assert isinstance(decision, Recommended)
    assert [pick.factor_id for pick in decision.picks] == ["syn:steel-kg"]


def test_picking_the_same_id_twice_or_four_ids_is_rejected() -> None:
    h = setup()
    seed(
        h.mock,
        classification(1),
        recommendation(["syn:steel-kg", "syn:steel-kg"]),
        recommendation(["syn:steel-kg", "syn:steel-t", "syn:pp-kg", "syn:steel-kg"]),
        '{"picks":[],"none_suitable":false}',
    )
    decision = only(h, row("합성 강판")).decision
    assert isinstance(decision, RecommendationFailed)
    assert decision.llm.kind == "schema_mismatch"


# ── 활동 기반 → 지출 기반 ──


def test_activity_candidates_with_a_matching_unit_are_used_first() -> None:
    h = setup()
    seed(h.mock, classification(1), recommendation(["syn:steel-t"]))
    entry = only(h, row("합성 강판", quantity="3", unit="kg"))
    assert isinstance(entry.decision, Recommended)
    assert entry.decision.basis == BasisTrace("activity", False, None)
    # kg 수량을 톤 계수에 맞춘다: 3 × 0.001 × 2400.
    assert isinstance(entry.calc, Computed)
    assert (entry.calc.co2e, entry.calc.activity_amount) == ("0.0072", "0.003")
    assert entry.calc.formula == "3 kg × 0.001 × 2400 kg CO2e/tonnes × 0.001"


def test_a_unit_mismatch_falls_back_to_spend_with_the_reason() -> None:
    h = setup()
    seed(h.mock, classification(1), recommendation(["syn:spend-computer"]))
    decision = only(h, row("노트북", quantity="2", unit="대")).decision
    assert isinstance(decision, Recommended)
    assert decision.basis == BasisTrace("spend", True, "unit_mismatch")
    assert decision.candidates == CandidateStats(total=3, shown=3, lexical_matches=0, method="lexical-v2")
    assert len(h.mock.calls) == 2
    assert "syn:spend-computer" in user_texts(h.mock)[1]
    assert "syn:steel-kg" not in user_texts(h.mock)[1]
    assert "BASIS: 지출 기반" in user_texts(h.mock)[1]


def test_no_activity_candidates_in_the_category_falls_back_to_spend() -> None:
    h = setup()
    seed(h.mock, classification(2), recommendation(["syn:spend-storage"]))
    decision = only(h, row("스토리지 장비", unit="kg")).decision
    assert isinstance(decision, Recommended)
    assert decision.category == 2
    assert decision.basis == BasisTrace("spend", True, "no_activity_candidates")


def test_when_the_model_finds_no_suitable_activity_factor_it_is_asked_once_more_on_spend() -> None:
    h = setup()
    seed(h.mock, classification(1), recommendation([]), recommendation(["syn:spend-legal"]))
    result = run(h, [row("특수 합금", unit="kg")])
    assert len(h.mock.calls) == 3
    decision = result.rows[0].decision
    assert isinstance(decision, Recommended)
    assert decision.basis == BasisTrace("spend", True, "llm_found_none_suitable")
    assert [trace.basis for trace in result.groups[0].shortlists] == ["physical", "spend"]


def test_no_spend_candidates_either_is_no_candidates_not_an_empty_recommendation() -> None:
    h = setup()
    seed(h.mock, classification(6))
    decision = only(h, row("출장 일비", unit="일")).decision
    assert len(h.mock.calls) == 1
    assert isinstance(decision, NoCandidates)
    assert (decision.category, decision.physical) == (6, "unit_mismatch")
    assert decision_to_dict(decision)["status"] == "no_candidates"


def test_no_suitable_spend_factor_is_no_suitable_factor() -> None:
    h = setup()
    seed(h.mock, classification(1), recommendation([]))
    decision = only(h, row("상품권", unit="매")).decision
    assert isinstance(decision, NoSuitableFactor)
    assert decision.physical == "unit_mismatch"


def test_none_suitable_on_physical_with_no_spend_candidates_is_no_suitable_factor() -> None:
    h = setup()
    seed(h.mock, classification(4), recommendation([]))
    moved = transport(origin="부산", destination="평택", mode="트럭", weight_kg="12000", distance_km="350")
    decision = only(h, row("원자재 운송", quantity=None, unit=None, transport=moved)).decision
    assert isinstance(decision, NoSuitableFactor)
    assert decision.physical == "llm_found_none_suitable"


def test_transport_rows_get_tonne_km_factors() -> None:
    h = setup()
    seed(h.mock, classification(4), recommendation(["syn:truck"]))
    moved = transport(origin="부산", destination="평택", mode="트럭", weight_kg="12000", distance_km="350")
    entry = only(h, row("원자재 운송", quantity=None, unit=None, transport=moved))
    assert isinstance(entry.decision, Recommended)
    assert entry.decision.basis == BasisTrace("distance", False, None)
    assert isinstance(entry.calc, Computed)
    assert (entry.calc.co2e, entry.calc.activity_amount) == ("0.42", "4200")


# ── 실패는 빈 결과가 아니라 갈래다 ──


def test_a_category_outside_the_supported_six_is_unsupported_and_does_not_recommend() -> None:
    h = setup()
    seed(h.mock, classification("other"))
    entry = only(h, row("폐기물 처리"))
    assert len(h.mock.calls) == 1
    assert isinstance(entry.decision, UnsupportedCategory)
    assert entry.decision.classification.category == "other"
    assert entry.calc == NotCalculated("unsupported_category")


def test_a_provider_error_is_classification_failed() -> None:
    h = setup()  # 심어 둔 응답이 없으면 모의 공급사는 오류를 돌려준다.
    decision = only(h, row("합성 강판")).decision
    assert len(h.mock.calls) == 1
    assert isinstance(decision, ClassificationFailed)
    assert decision.llm.kind == "provider_error"
    assert decision.llm.detail.startswith("status=null retryable=false ")


def test_a_refusal_at_the_recommendation_step_is_recommendation_failed() -> None:
    h = setup()
    h.mock.enqueue_text(classification(1)).enqueue(Refusal("거부 (synthetic)", None, SYNTHETIC_USAGE))
    decision = only(h, row("합성 강판")).decision
    assert isinstance(decision, RecommendationFailed)
    assert (decision.llm.kind, decision.llm.detail) == ("refusal", "거부 (synthetic)")
    assert decision_to_dict(decision)["llm"] == {"kind": "refusal", "detail": "거부 (synthetic)"}


def test_a_classification_answer_off_schema_is_classification_failed() -> None:
    h = setup()
    seed(h.mock, *[classification(5)] * 3)
    decision = only(h, row("합성 강판")).decision
    assert isinstance(decision, ClassificationFailed)
    assert decision.llm.kind == "schema_mismatch"
    assert len(h.mock.calls) == 3


def test_a_boolean_category_is_not_category_one() -> None:
    h = setup()
    seed(h.mock, *['{"category":true,"keywords_en":[],"confidence":"low","reason":"x"}'] * 3)
    decision = only(h, row("합성 강판")).decision
    assert isinstance(decision, ClassificationFailed)
    assert decision.llm.kind == "schema_mismatch"


def test_duplicate_row_ids_reject_the_whole_run_without_calling_the_model() -> None:
    h = setup()
    result = run_pipeline([row("a"), row("b")], h.options)
    assert result == PipelineRejected("duplicate_row_id", row_id="r1")
    assert h.mock.calls == []


def test_bad_adjustments_reject_the_whole_run_without_calling_the_model() -> None:
    bad = CurrencyAdjustment("KRW", "USD", 2022, "1e-3", synthetic=True, source=None)
    h = setup(adjustments=(bad,))
    result = run_pipeline([row("a")], h.options)
    assert isinstance(result, PipelineRejected)
    assert result.kind == "invalid_adjustments"
    assert [problem.kind for problem in result.problems] == ["invalid_multiplier"]
    assert h.mock.calls == []


# ── 숫자는 생성 모델에 넘기지 않는다 ──


def test_quantity_amount_weight_distance_and_factor_values_do_not_reach_the_prompt() -> None:
    h = setup()
    seed(h.mock, classification(4), recommendation(["syn:truck"]))
    moved = transport(origin="부산", destination="평택", mode="트럭", weight_kg="98765", distance_km="43210")
    run(h, [row("원자재 운송", quantity="13579", amount="24680000", unit=None, transport=moved)])
    sent = "\n".join(json.dumps(call.to_json(), ensure_ascii=False) for call in h.mock.calls)
    for number in ["98765", "43210", "13579", "24680000", "0.1"]:
        assert number not in sent
    assert "원자재 운송" in user_texts(h.mock)[0]
    assert '"id":"syn:truck"' in user_texts(h.mock)[1]


def test_only_the_shortlisted_candidates_go_into_the_prompt() -> None:
    h = setup(shortlist_size=1)
    seed(h.mock, classification(1, ["legal"]), recommendation(["syn:spend-legal"]))
    run(h, [row("법률 자문", unit="식")])
    candidates = json.loads(user_texts(h.mock)[1].split("CANDIDATES_JSON: ")[1])
    assert [candidate["id"] for candidate in candidates] == ["syn:spend-legal"]


def test_the_output_caps_ride_on_the_request_sent_to_the_provider() -> None:
    h = setup()
    seed(h.mock, classification(1), recommendation(["syn:steel-kg"]))
    run(h, [row("합성 강판")])
    # 모의 모델에는 추론 여유분이 없다: 단계의 상한이 그대로 나간다.
    assert [call.max_output_tokens for call in h.mock.calls] == [400, 800]
    names = [call.json_schema.name for call in h.mock.calls if call.json_schema is not None]
    assert names == ["scope3_classification", "scope3_recommendation"]


def test_the_shortlist_method_and_evidence_ride_on_the_result() -> None:
    h = setup()
    seed(h.mock, classification(1), recommendation(["syn:steel-kg"]))
    result = run(h, [row("합성 강판")])
    assert result.shortlist.method == "lexical-v2"
    [trace] = result.groups[0].shortlists
    assert (trace.basis, trace.method, trace.total) == ("physical", "lexical-v2", 3)
    assert trace.shown_ids[0] == "syn:steel-kg"
    assert trace.evidence[0].lexical is not None
    assert "강판" in trace.evidence[0].lexical.matched_terms
    # lexical-v1 을 고르면 처음 방식으로 추린다.
    first = setup(shortlister=lexical_shortlister("lexical-v1"))
    seed(first.mock, classification(1), recommendation(["syn:steel-kg"]))
    assert run(first, [row("합성 강판")]).shortlist.method == "lexical-v1"


def test_usage_is_summed_per_prompt() -> None:
    h = setup()
    seed(h.mock, classification(1), recommendation(["syn:steel-kg"]))
    usage = usage_to_dict(run(h, [row("합성 강판")]).usage)
    assert usage["calls"] == 2
    assert usage["attempts"] == 2
    assert usage["byPrompt"] == {
        CLASSIFY_PROMPT: {"calls": 1, "attempts": 1, "costUsd": 0.00014},
        RECOMMEND_PROMPT: {"calls": 1, "attempts": 1, "costUsd": 0.00014},
    }
    # 가상 단가(입력 1.0 · 출력 2.0 USD/백만 토큰)와 가상 사용량(100 · 20)의 곱이다. 실제 비용이 아니다.
    assert usage["costUsd"] == 0.00028


# ── 포트: 가짜 카탈로그와 가짜 게이트웨이 ──


class FakeCatalog:
    """`FactorCatalog` 포트의 가짜. 목록을 그대로 돌려준다."""

    def __init__(self, factors: list[Factor]) -> None:
        self._factors = factors

    def get(self, factor_id: str) -> Factor | None:
        return next((factor for factor in self._factors if factor.id == factor_id), None)

    def candidates(self, query: CandidateQuery) -> list[Factor]:
        return [factor for factor in self._factors if (factor.factor_type == "spend") == (query.basis == "spend")]


class FakeGateway:
    """`LlmGateway` 포트의 가짜. 공급사도 호출 층도 없이 스키마에 맞는 값을 바로 돌려준다."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]:
        self.prompts.append(request.prompt)
        meta = CallMeta(call_id="fake", prompt_id=request.prompt, attempts=(), total_cost_usd=0.0, warnings=())
        assert request.schema is not None
        if request.schema is ClassificationOut:
            data = request.schema.model_validate(json.loads(classification(1)))  # type: ignore[attr-defined]
        else:
            assert issubclass(request.schema, RecommendationOut)
            data = request.schema.model_validate(json.loads(recommendation(["syn:steel-kg"])))
        return Success(data=data, text="", meta=meta)  # type: ignore[arg-type]


def fake_options(gateway: FakeGateway, memory: InMemoryMappingMemory | None = None) -> PipelineOptions:
    catalog = ListFactorCatalog(HELPER_RECORDS)
    steel = catalog.get("syn:steel-kg")
    assert steel is not None
    return PipelineOptions(gateway, FakeCatalog([steel]), memory or InMemoryMappingMemory(), ROUTE, TAGS)


def test_decide_group_reaches_a_recommendation_through_fake_ports() -> None:
    gateway = FakeGateway()
    [group] = group_rows([row("합성 강판")])
    decision = decide_group(fake_options(gateway), group, LlmUsage())
    assert isinstance(decision, Recommended)
    assert [pick.factor_id for pick in decision.picks] == ["syn:steel-kg"]
    assert gateway.prompts == [CLASSIFY_PROMPT, RECOMMEND_PROMPT]


def test_a_remembered_group_does_not_touch_the_gateway_port() -> None:
    gateway = FakeGateway()
    memory = InMemoryMappingMemory([remembered("합성 강판", "syn:steel-kg")])
    [group] = group_rows([row("합성 강판")])
    decision = decide_group(fake_options(gateway, memory), group, LlmUsage())
    assert isinstance(decision, Recommended)
    assert decision.source == "memory"
    assert gateway.prompts == []


# ── 검토 → 기억 → 다음 실행 ──


def test_a_mapping_confirmed_in_review_makes_the_next_run_skip_the_model() -> None:
    memory = InMemoryMappingMemory()
    h = setup(memory=memory)
    seed(h.mock, classification(1), recommendation(["syn:steel-kg", "syn:steel-t"]))
    first = run(h, [row("합성 강판")])
    decision = first.rows[0].decision
    assert isinstance(decision, Recommended)
    assert len(h.mock.calls) == 2

    who = Actor("reviewer-synthetic", "2026-10-01T11:00:00+09:00")
    proposal = AiProposal(decision.category, decision.picks, "2026-10-01T10:00:00+09:00")
    done = finalize(accept(propose("r1", first.rows[0].group_key, proposal), who), who)
    entry = to_memory_entry(done, "합성 강판")
    assert entry is not None
    memory.confirm(entry)

    again = setup(memory=memory)
    second = run(again, [row("합성강판", row_id="r2", quantity="4")])
    assert again.mock.calls == []
    remembered_decision = second.rows[0].decision
    assert isinstance(remembered_decision, Recommended)
    assert remembered_decision.source == "memory"
    assert remembered_decision.memory_entry == entry
    assert decision_to_dict(remembered_decision)["memoryEntry"] == {
        "key": "합성강판|kg|",
        "category": 1,
        "factorId": "syn:steel-kg",
        "confirmedBy": "reviewer-synthetic",
        "confirmedAt": "2026-10-01T11:00:00+09:00",
        "label": "합성 강판",
    }
    assert isinstance(second.rows[0].calc, Computed)
    assert second.rows[0].calc.co2e == "0.01"
    # 기억 항목에 이름표가 없으면 JSON 에 그 키가 없다.
    unlabeled = replace(remembered_decision, memory_entry=replace(entry, label=None))
    assert "label" not in decision_to_dict(unlabeled)["memoryEntry"]  # type: ignore[operator]
