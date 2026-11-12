"""흐름 입력의 글·모델 칸(TR4 §3-2): 흐름 입력에 texts·models 의 기본값이 없고(끼움이 늘 싣는다), 결과의
settings.routes 와 공급사 요청이 칸의 값이다. 실호출 0 — 모의 공급사뿐."""

import dataclasses
from typing import Any

import pytest

from esgapi.core.flows.run import run_flow
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import Completed, ProviderRequest, Usage
from esgapi.translation.engines.colab_158.texts import DEFAULT_TEXTS
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.tests.engines.colab_158.support import LIGHT, LIGHT_MODEL, STANDARD, STANDARD_MODEL, client
from esgapi.translation.tests.flows.support import SIMPLE_EN, Ran, binding, document, options, result_of
from esgapi.translation.tools.llm_bridge import DEFAULT_MODELS, CallModel, TranslationModels, route_for

USAGE = Usage(input_tokens=10, output_tokens=5, cache_read_tokens=0, cache_write_tokens=0)
SWAPPED = TranslationModels(
    translate_ceo=CallModel(LIGHT, 3000), translate_other=CallModel(STANDARD, 2000), review=CallModel(STANDARD, 1500)
)
"""기본과 다른 칸 셋(경로가 기본과 뒤바뀜)."""
MODEL_IDS = {LIGHT: LIGHT_MODEL, STANDARD: STANDARD_MODEL}


def answer(request: ProviderRequest) -> Completed:
    """검수 system 이면 이슈 없음, 아니면 지어낸 영문(호출 수를 손셈하지 않는 모의 — 자리마다 같은 답)."""
    system = "".join(segment.text for segment in request.system)
    return Completed(text="[]" if "ESG report proofreader" in system else SIMPLE_EN, usage=USAGE)


def ran_with(part: str, **changes: Any) -> tuple[dict[str, Any], MockProvider]:
    inputs = binding().inputs_with(document(), options(part=part), company_id=1, versions={})
    openai = MockProvider("openai")
    for _ in range(40):
        openai.enqueue(answer)
    adapters = colab.TranslationAdapters(llm=client({"openai": openai}), tenant="1", mock=False, spent_usd=lambda: 0.0)
    run = run_flow(colab.FLOW, dataclasses.replace(inputs, **changes), adapters)
    return result_of(Ran(run, openai)), openai


@pytest.mark.parametrize("missing", ["texts", "models"])
def test_the_flow_input_has_no_default_texts_or_models(missing: str) -> None:
    inputs = binding().inputs_with(document(), options(), company_id=1, versions={})
    fields = {f.name: getattr(inputs, f.name) for f in dataclasses.fields(inputs) if f.name != missing}
    with pytest.raises(TypeError, match=missing):
        colab.TranslationRunInputs(**fields)


def test_the_binding_gives_the_code_values_for_now() -> None:
    """① 의 끼움은 늘 코드 값(판 원천은 ③)."""
    inputs = binding().inputs_with(document(), options(), company_id=1, versions={})
    assert (inputs.texts, inputs.models) == (DEFAULT_TEXTS, DEFAULT_MODELS)


@pytest.mark.parametrize("part", ["ceo_message", "story", "general"])
def test_the_result_routes_are_the_default_routes(part: str) -> None:
    result, _ = ran_with(part)
    assert result["settings"]["routes"] == {
        "translate": route_for("translate", part),
        "review": route_for("review", part),
    }


@pytest.mark.parametrize("part", ["ceo_message", "story", "general"])
def test_the_result_routes_and_requests_follow_the_slots(part: str) -> None:
    result, openai = ran_with(part, models=SWAPPED)
    translate = SWAPPED.translate_ceo if part == "ceo_message" else SWAPPED.translate_other
    assert result["status"] == "done"
    assert result["settings"]["routes"] == {"translate": translate.route, "review": SWAPPED.review.route}
    reviewed = [r for r in openai.calls if "ESG report proofreader" in "".join(s.text for s in r.system)]
    translated = [r for r in openai.calls if r not in reviewed]
    assert reviewed and translated  # 분모: 두 역할 다 불렀다
    assert {(r.api_model_id, r.temperature) for r in reviewed} == {(MODEL_IDS[SWAPPED.review.route], None)}
    assert {r.max_output_tokens for r in reviewed} == {SWAPPED.review.max_output_tokens}
    assert {(r.api_model_id, r.temperature) for r in translated} == {(MODEL_IDS[translate.route], None)}
    assert max(r.max_output_tokens for r in translated) <= translate.max_output_tokens


MARKED = dataclasses.replace(
    DEFAULT_TEXTS,
    **{f.name: f"⟦TR4-flow-{f.name}⟧\n" + getattr(DEFAULT_TEXTS, f.name) for f in dataclasses.fields(DEFAULT_TEXTS)},
)
"""칸마다 앞에 표지를 붙인 글(뒤 글은 기본 그대로 — 모의의 검수 알아보기가 그대로 든다)."""


def test_the_flow_input_texts_reach_the_provider_system() -> None:
    """흐름 입력 texts 가 엔진 입력을 거쳐 공급사 system 까지 간다(검증 ① 권고 1 — engine_input 이 texts 를 빠뜨리면
    엔진 기본값 DEFAULT_TEXTS 로 돌아 빨강). user 에는 표지 0."""
    result, openai = ran_with("story", texts=MARKED)
    assert result["status"] == "done"
    systems = ["".join(s.text for s in r.system) for r in openai.calls]
    users = repr([r.user for r in openai.calls])
    for name in ("story_tone", "style_rules", "subject_fragment_rules", "review"):
        assert any(f"⟦TR4-flow-{name}⟧" in system for system in systems), name
    assert "⟦TR4-flow-" not in users
    assert not any("⟦TR4-flow-ceo_message_tone⟧" in system for system in systems)  # 그 파트 톤만
