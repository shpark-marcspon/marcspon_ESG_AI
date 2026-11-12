"""영문번역 모양 가짜 모듈 `fake-tr` 을 core 부품으로 선언·받기·조합한다(밴드 AP1a 3-3, 결정 MARC-ENT-399). 순수 층.

모델 칸 셋(칸마다 경로·기본값이 다름 — 하나는 temperature null, 하나는 다른 출력 상한)과 프롬프트 묶음
다섯(9·1·1·1·2 = 14칸, 첫 묶음은 모델 칸 둘이 받음)이 그린워싱 모양(칸 하나·묶음 하나)과 같은 함수로 선언·받기·
ai.prompt-model@3 조합되고,
예시 prompt-model3-fake-module.json 이 그 조합 결과와 바이트까지 같다(예시가 낡지 않게).
이름·글은 지어낸 것이다(실제 영문번역 모듈의 칸·글이 아니다).
"""

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AcceptedPrompts,
    AiModelSlotSpec,
    AiModuleSpec,
    AiPromptGroupSpec,
    ModelSettingRefused,
    PromptRefused,
    check_model_settings,
    check_module,
    check_prompts,
    compose,
    defaults,
    layout_of,
    model_settings_sha256,
    prompt_entry,
)
from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_V3, AiFixedGroup, AiPromptEntry, AiPromptsIn
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.errors import LlmConfigError

CONFIG = load_config(default_config_sources(synthetic=False))
EXAMPLE = Path(__file__).resolve().parents[1] / "data" / "ai-setting-examples" / "prompt-model3-fake-module.json"

SLOTS = (
    AiModelSlotSpec(
        key="translate_ceo",
        label="가상 대표 인사말 번역",
        routes=("standard-openai-41", "light-openai-41"),
        tool_loop=False,
        default={
            "key": "translate_ceo",
            "route": "standard-openai-41",
            "temperature": 0.2,
            "webSearch": False,
            "maxOutputTokens": 4000,
        },
    ),
    AiModelSlotSpec(
        key="translate",
        label="가상 본문 번역",
        routes=("light-openai-41", "standard-openai-41"),
        tool_loop=False,
        default={
            "key": "translate",
            "route": "light-openai-41",
            "temperature": 0.0,
            "webSearch": False,
            "maxOutputTokens": 8000,
        },
    ),
    AiModelSlotSpec(
        key="review",
        label="가상 검토",
        routes=("light-openai", "light-openai-41"),
        tool_loop=False,
        default={
            "key": "review",
            "route": "light-openai",
            "temperature": None,
            "webSearch": False,
            "maxOutputTokens": 2000,
        },
    ),
)
GROUPS = (
    AiPromptGroupSpec("translate", "가상 번역", tuple(f"t{n}" for n in range(1, 10)), ("translate_ceo", "translate")),
    AiPromptGroupSpec("polish", "가상 다듬기", ("p1",), ("translate",)),
    AiPromptGroupSpec("editorial_qa", "가상 편집 점검", ("q1",), ("review",)),
    AiPromptGroupSpec("review", "가상 검토", ("r1",), ("review",)),
    AiPromptGroupSpec("autofix", "가상 자동 고침", ("f1", "f2"), ("translate",)),
)
SPEC = AiModuleSpec(module="fake-tr", models=SLOTS, groups=GROUPS)
FIXED: list[AiFixedGroup] = [
    {"key": "glossary", "label": "가상 용어집", "items": [{"key": "terms", "label": "가상 용어 수", "value": 12}]}
]


def text(group: str, key: str) -> str:
    return f"가상 {group} 지시 {key}: 지어낸 보고서 문장을 옮긴다.\n[출력]\n가상 형식"


def prompts_body() -> AiPromptsIn:
    return {
        "steps": [
            {"key": g.key, "prompts": [{"key": k, "text": text(g.key, k), "memo": ""} for k in g.prompt_keys]}
            for g in GROUPS
        ]
    }


def entries() -> dict[str, list[AiPromptEntry]]:
    return {
        g.key: [
            prompt_entry(
                key=k,
                label=f"가상 칸 {k}",
                prompt_id=f"fake-tr.{g.key}.{k}",
                prompt_version="fake-tr-v1",
                text=text(g.key, k),
                memo="",
                default_text=text(g.key, k),
                output_section="[출력]\n가상 형식",
            )
            for k in g.prompt_keys
        ]
        for g in GROUPS
    }


def composed(model: AcceptedModelSettings | None = None) -> Any:
    return compose(
        CONFIG,
        SPEC,
        setting_name="v3",
        editable={"prompts": True, "model": True},
        model=model or defaults(CONFIG, SLOTS),
        prompts=entries(),
        fixed=FIXED,
    )


def example_text() -> str:
    return json.dumps(composed(), ensure_ascii=False, indent=2) + "\n"


# ── 3-3-1 선언 ──


def test_the_fake_module_is_declared() -> None:
    check_module(SPEC)
    assert [len(keys) for _, keys in layout_of(SPEC)] == [9, 1, 1, 1, 2]
    assert sum(len(keys) for _, keys in layout_of(SPEC)) == 14
    assert [key for key, _ in layout_of(SPEC)] == ["translate", "polish", "editorial_qa", "review", "autofix"]
    typo = dataclasses.replace(GROUPS[4], model_slots=("translat",))
    with pytest.raises(LlmConfigError, match="translat"):
        check_module(dataclasses.replace(SPEC, groups=(*GROUPS[:4], typo)))


# ── 3-3-2 모델 받기 ──


def test_the_three_slots_are_accepted() -> None:
    model = defaults(CONFIG, SLOTS)
    assert [s.key for s in model.steps] == ["translate_ceo", "translate", "review"]
    assert [s.temperature for s in model.steps] == [0.2, 0.0, None]
    assert [s.max_output_tokens for s in model.steps] == [4000, 8000, 2000]


def test_a_refusal_names_the_slot() -> None:
    given: Any = {"steps": [dict(s.default) for s in SLOTS]}
    given["steps"][1]["maxOutputTokens"] = 10**9
    refused = check_model_settings(CONFIG, given, steps=SLOTS)
    assert isinstance(refused, ModelSettingRefused)
    assert (refused.code, refused.step) == ("ai_model_max_output_range", "translate")


def test_the_slot_order_is_fixed() -> None:
    given: Any = {"steps": [dict(s.default) for s in reversed(SLOTS)]}
    refused = check_model_settings(CONFIG, given, steps=SLOTS)
    assert isinstance(refused, ModelSettingRefused)
    assert (refused.code, refused.step) == ("ai_model_steps_fixed", None)


# ── 3-3-3 프롬프트 받기 ──


def test_the_fourteen_prompts_are_accepted() -> None:
    accepted = check_prompts(prompts_body(), layout=layout_of(SPEC))
    assert isinstance(accepted, AcceptedPrompts)
    assert sum(len(s.prompts) for s in accepted.steps) == 14


def test_a_blank_prompt_in_the_fourth_group_names_its_field() -> None:
    body: Any = prompts_body()
    body["steps"][3]["prompts"][0]["text"] = "  "
    refused = check_prompts(body, layout=layout_of(SPEC))
    assert isinstance(refused, PromptRefused)
    assert (refused.code, refused.field) == ("ai_prompt_text_empty", "prompts.steps.3.prompts.0.text")


# ── 3-3-4 조합 ──


def test_compose_builds_the_v3_shape() -> None:
    body = composed()
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    assert [m["key"] for m in body["models"]] == ["translate_ceo", "translate", "review"]
    assert [g["key"] for g in body["promptGroups"]] == ["translate", "polish", "editorial_qa", "review", "autofix"]
    assert body["promptGroups"][0]["modelSlots"] == ["translate_ceo", "translate"]
    assert [m["model"]["temperature"] for m in body["models"]] == [0.2, 0.0, None]
    assert all(m["unavailableRoutes"] == [] for m in body["models"])


def test_the_sha_holds_every_slot() -> None:
    model = defaults(CONFIG, SLOTS)
    warmer = AcceptedModelSettings(
        steps=(model.steps[0], dataclasses.replace(model.steps[1], temperature=0.5), model.steps[2])
    )
    assert composed(warmer)["modelSettingsSha256"] == model_settings_sha256(warmer)
    assert model_settings_sha256(warmer) != model_settings_sha256(model)


# ── 3-3-5 예시 = 조합 결과 ──


def test_the_example_is_the_composed_body() -> None:
    assert EXAMPLE.read_text(encoding="utf-8") == example_text()
