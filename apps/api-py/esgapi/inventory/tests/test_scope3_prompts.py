"""프롬프트 템플릿과 응답 스키마. 순수 층.

템플릿 둘은 esg-lab 의 것을 본문 그대로 옮긴 사본이다(esgapi/inventory/prompts/README.md 에 원본의 sha256).
"""

import hashlib
import json
from importlib import resources

import pytest
from pydantic import TypeAdapter, ValidationError

from esgapi.core.llm.prompts import PackagePromptStore, parse_prompt_id, render_prompt
from esgapi.core.llm.schema import to_strict_json_schema
from esgapi.core.llm.types import (
    BudgetExceeded,
    CallMeta,
    CutOff,
    ProviderFailed,
    Refused,
    SchemaIssue,
    SchemaMismatch,
    Scope,
    TimedOut,
)
from esgapi.inventory.engines.scope3.llm_first_1.llm_steps import (
    CLASSIFY_MAX_OUTPUT_TOKENS,
    CLASSIFY_PROMPT,
    MAX_PICKS,
    RECOMMEND_MAX_OUTPUT_TOKENS,
    RECOMMEND_PROMPT,
    ClassificationOut,
    LlmFailure,
    candidate_for_prompt,
    classify_request,
    describe_failure,
    item_for_prompt,
    recommend_request,
    recommendation_schema,
)
from esgapi.inventory.tests.scope3_llm_support import TAGS, classification, recommendation
from esgapi.inventory.tests.scope3_support import FACTOR_BY_ID, factor, row, transport

# 원본(esg-lab f1b2c77 `ts/scope3/prompts/scope3/{classify,recommend}/1.md`)의 sha256. 확인 2026-10-08.
ORIGINAL_SHA256 = {
    "scope3-classify": "3d3aaf5e90c14f5ee82da2acbd84dba513edb108ccebaab778295ad98cf2b158",
    "scope3-recommend": "48a0c743b771c580cf96cd76359157152fdc04a56bf7dbba68ebc4b2e9effebd",
}
META = CallMeta(call_id="c", prompt_id="p", attempts=(), total_cost_usd=0.0, warnings=())


@pytest.mark.parametrize("name", sorted(ORIGINAL_SHA256))
def test_the_templates_are_byte_for_byte_copies(name: str) -> None:
    body = resources.files("esgapi.inventory").joinpath("prompts", name, "1.md").read_bytes()
    assert hashlib.sha256(body).hexdigest() == ORIGINAL_SHA256[name]


def test_the_prompt_ids_resolve_in_the_package_store() -> None:
    store = PackagePromptStore()
    classify = store.get(parse_prompt_id(CLASSIFY_PROMPT))
    rendered = render_prompt(classify, {"item_json": "{}"})
    assert rendered.user == "ITEM_JSON: {}"
    assert [segment.cache for segment in rendered.system] == [True]
    recommend = store.get(parse_prompt_id(RECOMMEND_PROMPT))
    values = {"category": "1", "basis": "지출 기반", "item_json": "{}", "candidates_json": "[]"}
    assert render_prompt(recommend, values).user == "CATEGORY: 1\nBASIS: 지출 기반\nITEM_JSON: {}\nCANDIDATES_JSON: []"


def test_numbers_do_not_go_into_the_item() -> None:
    moved = transport(origin="부산", destination="평택", mode="트럭", weight_kg="98765", distance_km="43210")
    item = item_for_prompt(row("원자재 운송 80g", quantity="13579", amount="24680000", unit=None, transport=moved))
    assert item == {
        "item_name": "원자재 운송 80g",
        "unit": None,
        "currency": "KRW",
        "transport": {"origin": "부산", "destination": "평택", "mode": "트럭"},
    }
    assert list(item) == ["item_name", "unit", "currency", "transport"]
    assert item_for_prompt(row("x"))["transport"] is None


def test_candidates_carry_no_value_and_the_path_only_when_it_adds_something() -> None:
    steel = candidate_for_prompt(FACTOR_BY_ID["syn:steel-kg"])
    assert steel == {
        "id": "syn:steel-kg",
        "name": "합성 강판 (synthetic)",
        "path": "합성 자재 > 금속",
        "per": "kg",
        "source": "synthetic",
        "region": "GLOBAL",
    }
    assert list(steel) == ["id", "name", "path", "per", "source", "region"]
    # 경로가 없으면 키가 없다(null 이 아니다).
    assert "path" not in candidate_for_prompt(FACTOR_BY_ID["syn:spend-legal"])
    # 이름이 경로의 첫 마디로 시작하면 경로를 싣지 않는다.
    repeated = factor(
        "syn:r", "Synthetic freight flights", (4,), "distance", "tonne.km", "1.1", path=("Synthetic freight",)
    )
    assert "path" not in candidate_for_prompt(repeated)


def test_the_requests_carry_the_ported_output_caps_and_schema_names() -> None:
    classify = classify_request(row("합성 강판"), "mock", TAGS)
    assert (classify.prompt, classify.route, classify.schema_name) == (CLASSIFY_PROMPT, "mock", "scope3_classification")
    assert classify.max_output_tokens == CLASSIFY_MAX_OUTPUT_TOKENS == 400
    assert classify.vars == {"item_json": '{"item_name":"합성 강판","unit":"kg","currency":"KRW","transport":null}'}
    candidates = [FACTOR_BY_ID["syn:steel-kg"], FACTOR_BY_ID["syn:steel-t"]]
    recommend = recommend_request(row("합성 강판"), 1, "physical", candidates, "mock", TAGS)
    assert (recommend.prompt, recommend.schema_name) == (RECOMMEND_PROMPT, "scope3_recommendation")
    assert recommend.max_output_tokens == RECOMMEND_MAX_OUTPUT_TOKENS == 800
    assert recommend.vars["category"] == "1"
    assert recommend.vars["basis"] == "활동(물량·거리) 기반"
    assert recommend_request(row("x"), 2, "spend", candidates, "mock", TAGS).vars["basis"] == "지출 기반"
    assert [entry["id"] for entry in json.loads(recommend.vars["candidates_json"])] == ["syn:steel-kg", "syn:steel-t"]
    assert MAX_PICKS == 3


def classify_adapter() -> TypeAdapter[ClassificationOut]:
    return TypeAdapter(ClassificationOut)


@pytest.mark.parametrize("category", [1, 2, 4, 6, 7, 9, "other"])
def test_classification_accepts_the_six_categories_and_other(category: int | str) -> None:
    parsed = classify_adapter().validate_json(classification(category, ["steel"]), strict=True)
    assert parsed.category == category
    assert type(parsed.category) is type(category)


@pytest.mark.parametrize(
    "text",
    [
        classification(3),
        classification(5),
        classification("1"),
        '{"category":true,"keywords_en":[],"confidence":"low","reason":"x"}',
        '{"category":1,"keywords_en":[],"confidence":"low","reason":""}',
        '{"category":1,"keywords_en":[""],"confidence":"low","reason":"x"}',
        '{"category":1,"keywords_en":["' + "k" * 61 + '"],"confidence":"low","reason":"x"}',
        '{"category":1,"keywords_en":["a","b","c","d","e","f","g","h","i"],"confidence":"low","reason":"x"}',
        '{"category":1,"keywords_en":[],"confidence":"sure","reason":"x"}',
        '{"category":1,"keywords_en":[],"confidence":"low","reason":"x","extra":1}',
        '{"category":1,"keywords_en":[],"confidence":"low"}',
    ],
)
def test_classification_rejects_what_zod_rejected(text: str) -> None:
    with pytest.raises(ValidationError):
        classify_adapter().validate_json(text, strict=True)


def test_a_json_number_written_as_1_point_0_is_category_one_as_in_js() -> None:
    """JS 에서는 1.0 === 1 이라 zod 가 받았다. 여기서도 받고, 값은 정수 1 이 된다(프롬프트에 "1.0" 이 가지 않는다)."""
    text = '{"category":1.0,"keywords_en":[],"confidence":"low","reason":"x"}'
    parsed = classify_adapter().validate_json(text, strict=True)
    assert parsed.category == 1
    assert type(parsed.category) is int


def test_keyword_limits_are_eight_keywords_of_sixty_characters() -> None:
    parsed = classify_adapter().validate_json(classification(1, ["k" * 60] * 8), strict=True)
    assert len(parsed.keywords_en) == 8


IDS = ["defra-2026:19_505_5144_15_1", "keiti-epd:row160", "epa-seef-v1.3:334111"]


def test_a_recommendation_schema_built_per_call_validates_strict_json() -> None:
    """★ 다: 후보 id 에는 `:`·`_`·`.` 이 있다. 열거로 그때그때 만든 모델이 호출 층의 검증 길을 그대로 지나는가."""
    schema = recommendation_schema(IDS)
    adapter = TypeAdapter(schema)
    parsed = adapter.validate_json(recommendation(IDS[:2]), strict=True)
    assert [pick.factor_id for pick in parsed.picks] == IDS[:2]
    assert parsed.none_suitable is False
    empty = adapter.validate_json(recommendation([]), strict=True)
    assert (empty.picks, empty.none_suitable) == ([], True)
    # 호출 층의 스키마 다듬기를 지나고, 열거가 JSON 스키마에 실린다.
    strict = json.dumps(to_strict_json_schema(adapter.json_schema()), ensure_ascii=False)
    for candidate_id in IDS:
        assert candidate_id in strict


@pytest.mark.parametrize(
    "text",
    [
        recommendation(["syn:invented"]),
        recommendation([IDS[0], IDS[0]]),
        recommendation([IDS[0], IDS[1], IDS[2], IDS[0]]),
        '{"picks":[],"none_suitable":false}',
        '{"picks":[{"factor_id":"keiti-epd:row160","reason":"x","confidence":"low"}],"none_suitable":true}',
        '{"picks":[{"factor_id":"keiti-epd:row160","reason":"","confidence":"low"}],"none_suitable":false}',
        '{"picks":[{"factor_id":"keiti-epd:row160","reason":"x","confidence":"low","value":1}],"none_suitable":false}',
        '{"picks":[],"none_suitable":"true"}',
    ],
)
def test_recommendation_rejects_ids_outside_the_candidates_and_inconsistent_answers(text: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(recommendation_schema(IDS)).validate_json(text, strict=True)


def test_a_recommendation_schema_needs_candidates() -> None:
    with pytest.raises(ValueError, match="후보가 없는"):
        recommendation_schema([])


def test_each_of_the_six_failure_kinds_keeps_its_detail() -> None:
    issues = (SchemaIssue("picks.0.factor_id", "bad"), SchemaIssue("none_suitable", "worse"))
    assert describe_failure(SchemaMismatch(issues, "{}", META)) == LlmFailure(
        "schema_mismatch", "picks.0.factor_id: bad; none_suitable: worse"
    )
    assert describe_failure(Refused("거부 (synthetic)", None, META)) == LlmFailure("refusal", "거부 (synthetic)")
    assert describe_failure(CutOff("{", META)) == LlmFailure("truncated", "출력 토큰 상한에서 잘렸다")
    assert describe_failure(ProviderFailed(None, False, "끊겼다", META)) == LlmFailure(
        "provider_error", "status=null retryable=false 끊겼다"
    )
    assert describe_failure(ProviderFailed(429, True, "잠시 뒤", META)) == LlmFailure(
        "provider_error", "status=429 retryable=true 잠시 뒤"
    )
    assert describe_failure(TimedOut("늦었다", META)) == LlmFailure("timeout", "늦었다")
    assert describe_failure(BudgetExceeded(2.0, 1.5, Scope(), META)) == LlmFailure(
        "budget_exceeded", "상한 2 USD, 누적 1.5 USD"
    )
