"""영문번역 AI 설정 판의 선언과 ai.prompt-model@3(밴드 TR4 §3-3-1 — 순수 층, DB 0).

    선언      check_module(SPEC) · 모델 칸 셋·묶음 다섯·칸 열넷이 발주서 2-1 · 기본 값이 다리 상수
    @3        기본 판 strict · defaultText == 엔진 글 · outputSection 은 범용 QA·검수 둘만 · editable 둘 true ·
              routeChoices 의 acceptsTemperature 는 늘 false(core 가 true 여도 — MARC-ISSUE-372)
    경로      칸 셋 다 standard-openai-41 인 판 + light-openai-41 없는 설정 → 칸마다 unavailableRoutes, 고른 경로가
              빠지면
              LlmConfigError(배포 잘못 — MARC-ISSUE-280 Q4)
    받기      temperature 값은 경로가 받아도 거절(R5) · 칸 차례 · 칸 하나 범위 밖 · 기본 글 열넷은 받기를 지난다
    잇기      texts_from·models_from 이 칸 key → 엔진·다리 칸
    고정 값   한 번은 글자로(96·95·120·6000·2·1·24) · AST: 제품 파일에 0·1 밖 수·경로·단가 글자 0
설정은 패키지의 실제 파일이다(가상 경로 0). 글은 지어낸 것이다. 실제 AI 호출 0.
"""

import ast
import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AcceptedPrompts,
    ModelSettingRefused,
    check_module,
    defaults,
    layout_of,
    route_choice,
)
from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_V3, AiModelSettingsIn, AiPromptsIn
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.core.llm.errors import LlmConfigError
from esgapi.translation.contracts import ai_setting_shapes as shapes
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.engines.colab_158.texts import DEFAULT_TEXTS
from esgapi.translation.flows import binding_158
from esgapi.translation.flows import prompt_model_158 as pm
from esgapi.translation.tools.llm_bridge import DEFAULT_MODELS, CallModel, TranslationModels

CONFIG: LlmConfig = load_config(default_config_sources(synthetic=False))
PACKAGE_MODELS = Path(str(default_config_sources(synthetic=False)[0]))
STANDARD = "standard-openai-41"
LIGHT = "light-openai-41"


def model_body(*steps: tuple[str, str, int], temperature: float | None = None) -> AiModelSettingsIn:
    return {
        "steps": [
            {"key": key, "route": route, "temperature": temperature, "webSearch": False, "maxOutputTokens": cap}
            for key, route, cap in steps
        ]
    }


ALL_STANDARD = model_body(
    ("translate_ceo", STANDARD, 3000), ("translate_other", STANDARD, 2000), ("review", STANDARD, 1500)
)


def prompts_body(**changed: str) -> AiPromptsIn:
    """기본 글 열넷(메모 = 기본 메모) — changed 의 칸만 그 글."""
    return {
        "steps": [
            {
                "key": group,
                "prompts": [
                    {"key": key, "text": changed.get(key, pm.default_text(key)), "memo": pm.DEFAULT_MEMOS[key]}
                    for key in keys
                ],
            }
            for group, keys in pm.LAYOUT
        ]
    }


def accepted_model(given: AiModelSettingsIn) -> AcceptedModelSettings:
    found = pm.accept_model(CONFIG, given)
    assert isinstance(found, AcceptedModelSettings), found
    return found


def accepted_prompts(given: AiPromptsIn) -> AcceptedPrompts:
    found = pm.accept_prompts(given)
    assert isinstance(found, AcceptedPrompts), found
    return found


def default_body() -> Any:
    return pm.prompt_model(CONFIG, setting_name=shapes.DEFAULT_NAME, model=defaults(CONFIG, pm.MODELS))


# ── 선언 ──


def test_the_declaration_is_the_order() -> None:
    check_module(pm.SPEC)
    assert pm.ROUTES == (LIGHT, STANDARD)  # R3
    assert [(s.key, s.label, s.routes, s.tool_loop) for s in pm.MODELS] == [
        ("translate_ceo", "번역 · CEO 메시지", (LIGHT, STANDARD), False),
        ("translate_other", "번역 · 그 밖 파트", (LIGHT, STANDARD), False),
        ("review", "검수", (LIGHT, STANDARD), False),
    ]
    assert [(g.key, g.label, g.prompt_keys, g.model_slots) for g in pm.GROUPS] == [
        (
            "translate",
            "번역",
            (
                "tone_ceo_message",
                "tone_story",
                "tone_general",
                "style_a",
                "style_b",
                "style_rules",
                "subject_fragment_rules",
                "terminology_note",
                "table_rules",
            ),
            ("translate_ceo", "translate_other"),
        ),
        ("polish", "윤문", ("polish",), ("translate_ceo", "translate_other")),
        ("editorial_qa", "범용 QA", ("editorial_qa",), ("translate_ceo", "translate_other")),
        ("review", "검수", ("review",), ("review",)),
        ("autofix", "자동 수정", ("autofix", "autofix_korean"), ("translate_ceo", "translate_other")),
    ]
    assert layout_of(pm.SPEC) == pm.LAYOUT
    keys = [key for _, group in pm.LAYOUT for key in group]
    assert len(keys) == len(set(keys)) == 14
    assert set(pm.LABELS) == set(pm.FIELDS) == set(pm.DEFAULT_MEMOS) == set(keys)
    assert set(pm.FIELDS.values()) == {f.name for f in dataclasses.fields(DEFAULT_TEXTS)}
    assert pm.PROMPT_VERSION == binding_158.ENGINE == shapes.DEFAULT_NAME


def test_the_default_model_values_are_the_bridge_constants() -> None:
    model = defaults(CONFIG, pm.MODELS)  # ★D: 지금 설정에서 기본값이 받기를 지난다
    assert [(s.key, s.route, s.temperature, s.web_search, s.max_output_tokens) for s in model.steps] == [
        (
            "translate_ceo",
            DEFAULT_MODELS.translate_ceo.route,
            None,
            False,
            DEFAULT_MODELS.translate_ceo.max_output_tokens,
        ),
        (
            "translate_other",
            DEFAULT_MODELS.translate_other.route,
            None,
            False,
            DEFAULT_MODELS.translate_other.max_output_tokens,
        ),
        ("review", DEFAULT_MODELS.review.route, None, False, DEFAULT_MODELS.review.max_output_tokens),
    ]
    assert pm.models_from(model) == DEFAULT_MODELS


# ── @3 ──


def test_the_default_prompt_model_is_strict_v3() -> None:
    body = default_body()
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    assert (body["schemaVersion"], body["module"], body["settingName"]) == (
        "ai.prompt-model@3",
        "translation",
        shapes.DEFAULT_NAME,
    )
    assert body["editable"] == {"prompts": True, "model": True}
    assert [slot["key"] for slot in body["models"]] == ["translate_ceo", "translate_other", "review"]
    assert [slot["unavailableRoutes"] for slot in body["models"]] == [[], [], []]
    assert [[c["route"] for c in slot["routeChoices"]] for slot in body["models"]] == [[LIGHT, STANDARD]] * 3
    assert [group["key"] for group in body["promptGroups"]] == [g.key for g in pm.GROUPS]


def test_each_entry_is_the_engine_text_and_the_board_memo() -> None:
    body = default_body()
    entries = {p["key"]: p for group in body["promptGroups"] for p in group["prompts"]}
    assert len(entries) == 14
    for key, entry in entries.items():
        engine = getattr(DEFAULT_TEXTS, pm.FIELDS[key])
        assert entry["text"] == entry["defaultText"] == engine, key
        assert (entry["memo"], entry["label"], entry["isDefault"]) == (pm.DEFAULT_MEMOS[key], pm.LABELS[key], True)
        assert (entry["promptId"], entry["promptVersion"]) == (f"translation/{key}", "colab_158")
        assert len(engine) <= body["limits"]["textMax"], key
    assert entries["tone_story"]["text"] == prompts.STORY_TONE
    assert entries["review"]["text"] == prompts.QA_SYSTEM_PROMPT
    assert entries["autofix"]["text"].replace("{page_num}", "7") == prompts.autofix_system(7)


def test_only_the_two_judged_texts_carry_an_output_section() -> None:
    body = default_body()
    sections = {p["key"]: p["outputSection"] for g in body["promptGroups"] for p in g["prompts"]}
    assert {key for key, section in sections.items() if section is not None} == {"editorial_qa", "review"}
    assert (
        sections["editorial_qa"]
        == prompts.GENERIC_EDITORIAL_QA_PROMPT[prompts.GENERIC_EDITORIAL_QA_PROMPT.rfind("Return JSON only:") :]
    )
    assert sections["review"] == prompts.QA_SYSTEM_PROMPT[prompts.QA_SYSTEM_PROMPT.rfind("## Output") :]
    assert (len(sections["editorial_qa"] or ""), len(sections["review"] or "")) == (297, 348)  # ★F


def test_a_saved_text_keeps_or_breaks_its_output_section() -> None:
    kept = prompts.GENERIC_EDITORIAL_QA_PROMPT.replace("MANDATORY", "REQUIRED", 1)
    assert kept != prompts.GENERIC_EDITORIAL_QA_PROMPT
    broken = prompts.QA_SYSTEM_PROMPT.replace("## Output", "## Result")
    saved = accepted_prompts(prompts_body(editorial_qa=kept, review=broken, tone_story="⟦지어낸 톤⟧"))
    body = pm.prompt_model(CONFIG, setting_name="v1", model=defaults(CONFIG, pm.MODELS), prompts=saved)
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    entries = {p["key"]: p for g in body["promptGroups"] for p in g["prompts"]}
    assert (entries["editorial_qa"]["outputKept"], entries["review"]["outputKept"]) == (True, False)
    assert [key for key, e in entries.items() if not e["isDefault"]] == ["tone_story", "editorial_qa", "review"]
    assert entries["tone_story"]["text"] == "⟦지어낸 톤⟧"


def test_no_route_choice_offers_a_temperature() -> None:
    """보기도 받기와 같은 뜻(R5 — MARC-ISSUE-372): 기본 판·저장 판 둘 다 칸 셋의 경로 전부 acceptsTemperature false.
    저장 판은 기본과 다른 허용 경로 + temperature null 이 받기를 지난 값이다."""
    assert route_choice(CONFIG, STANDARD, tool_loop=False)["acceptsTemperature"] is True  # core 는 받는다 — 덮는 뜻
    saved = pm.prompt_model(CONFIG, setting_name="v1", model=accepted_model(ALL_STANDARD))
    for body in (default_body(), saved):
        PROMPT_MODEL_V3.validate_python(body, strict=True)
        assert [[c["acceptsTemperature"] for c in slot["routeChoices"]] for slot in body["models"]] == [
            [False, False]
        ] * 3
    assert [slot["model"]["route"] for slot in saved["models"]] == [STANDARD] * 3


# ── 경로 ──


def config_without(route: str, tmp_path: Path) -> LlmConfig:
    data = json.loads(PACKAGE_MODELS.read_text(encoding="utf-8"))
    del data["routes"][route]
    path = tmp_path / "models.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return load_config((path,))


def test_a_route_the_deployment_dropped_is_named_not_failed(tmp_path: Path) -> None:
    narrow = config_without(LIGHT, tmp_path)
    model = pm.accept_model(narrow, ALL_STANDARD)
    assert isinstance(model, AcceptedModelSettings)
    body = pm.prompt_model(narrow, setting_name="v1", model=model)
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    assert [slot["unavailableRoutes"] for slot in body["models"]] == [[LIGHT]] * 3
    assert [[c["route"] for c in slot["routeChoices"]] for slot in body["models"]] == [[STANDARD]] * 3
    # 고른 경로(기본 판의 light-openai-41)가 빠지면 배포 잘못이다.
    with pytest.raises(LlmConfigError):
        pm.prompt_model(narrow, setting_name=shapes.DEFAULT_NAME, model=defaults(CONFIG, pm.MODELS))


# ── 받기 ──


def test_a_temperature_is_refused_even_where_the_route_takes_it() -> None:
    given = model_body(
        ("translate_ceo", STANDARD, 3000),
        ("translate_other", STANDARD, 2000),
        ("review", STANDARD, 1500),
        temperature=0.2,
    )
    found = pm.accept_model(CONFIG, given)
    assert found == ModelSettingRefused(
        "ai_model_temperature_unsupported", "이 모델은 temperature 를 바꿀 수 없어요", "translate_ceo"
    )


def test_the_model_slots_keep_their_order_and_their_caps() -> None:
    swapped = model_body(("translate_other", LIGHT, 100), ("translate_ceo", LIGHT, 100), ("review", LIGHT, 100))
    refused = pm.accept_model(CONFIG, swapped)
    assert isinstance(refused, ModelSettingRefused)
    assert (refused.code, refused.step) == ("ai_model_steps_fixed", None)
    huge = model_body(("translate_ceo", LIGHT, 100), ("translate_other", LIGHT, 10**9), ("review", LIGHT, 100))
    refused = pm.accept_model(CONFIG, huge)
    assert isinstance(refused, ModelSettingRefused)
    assert (refused.code, refused.step) == ("ai_model_max_output_range", "translate_other")


def test_the_default_texts_pass_the_core_rules() -> None:
    saved = accepted_prompts(prompts_body())
    assert pm.texts_from(saved) == DEFAULT_TEXTS
    for group, keys in pm.LAYOUT:  # 받기 규칙 4: 한 묶음 안 기본 글은 서로 다르다
        assert len({pm.default_text(key) for key in keys}) == len(keys), group


# ── 잇기 ──


def test_texts_from_maps_each_key_to_its_engine_field() -> None:
    marks = {key: f"⟦TR4-{key}⟧" for _, keys in pm.LAYOUT for key in keys}
    texts = pm.texts_from(accepted_prompts(prompts_body(**marks)))
    assert {pm.FIELDS[key]: getattr(texts, pm.FIELDS[key]) for key in marks} == {
        pm.FIELDS[key]: mark for key, mark in marks.items()
    }
    assert pm.texts_from(None) is DEFAULT_TEXTS


def test_models_from_maps_each_slot_to_its_bridge_field() -> None:
    model = accepted_model(
        model_body(("translate_ceo", LIGHT, 3000), ("translate_other", STANDARD, 2000), ("review", STANDARD, 1500))
    )
    assert pm.models_from(model) == TranslationModels(
        translate_ceo=CallModel(LIGHT, 3000),
        translate_other=CallModel(STANDARD, 2000),
        review=CallModel(STANDARD, 1500),
    )


# ── 고정 값 ──


def test_the_fixed_values_once_in_letters() -> None:
    processing, readonly = pm.fixed_groups()
    assert (processing["key"], readonly["key"]) == ("processing", "readonly_prompts")
    assert [item["value"] for item in processing["items"]] == [96, 95, 120, 6000, 2, 1, 24]
    assert [item["label"] for item in readonly["items"]] == [
        "바탕 지시",
        "용어집 보정 규칙",
        "한국어 보정 규칙",
        "보정 강화 모드",
    ]
    assert readonly["items"][0]["value"] == prompts.base_system_prompt("{industry_standards}")
    assert readonly["items"][3]["value"] == prompts.CRITICAL_REPAIR_MODE
    assert default_body()["fixed"] == pm.fixed_groups()


def _literals(tree: ast.AST) -> list[object]:
    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and id(node) not in docstrings and not isinstance(node.value, bool)
    ]


def test_the_flow_file_writes_no_number_route_or_price() -> None:
    tree = ast.parse(Path(pm.__file__).read_text(encoding="utf-8"))
    found = _literals(tree)
    assert {value for value in found if isinstance(value, int | float)} <= {0, 1}
    assert [v for v in found if isinstance(v, str) and ("openai" in v or "gpt" in v or "claude" in v)] == []
    assert [v for v in found if isinstance(v, str) and any(ch.isdigit() for ch in v) and "$" in v] == []
