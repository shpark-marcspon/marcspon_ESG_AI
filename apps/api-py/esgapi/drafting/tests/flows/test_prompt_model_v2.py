"""원고작성 AI 설정 판의 선언과 ai.prompt-model@3(밴드 RPA1 B2 — 순수 층, DB 0. dataverify test_prompt_model_156 의 꼴).

    선언      check_module(SPEC) · 모델 칸 둘·묶음 둘·칸 넷이 발주서 2-1 · 기본 값이 흐름 상수 · promptId 는 흐름의 id
    @3        기본 판 strict · defaultText == v2 엔진 글 · outputSection 없음 · editable 둘 true · 경로 둘
    받기      temperature null·범위 밖·경로 밖·webSearch true 거절 · 입력 글 자리 다섯 지킴(⑥) · 지시 글은 받음
    잇기      texts_from 이 칸 key → 엔진 값 · texts_from(None) == v2 DEFAULT_TEXTS
    고정 값   rules == MARKER_RULES · 실행 규칙이 엔진·흐름 상수 · AST: 0·1 밖 수·경로 글자는 ROUTES 둘째 하나
설정은 패키지의 실제 파일이다(가상 경로 0). 글은 지어낸 것이다. 실제 AI 호출 0.
"""

import ast
import dataclasses
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AcceptedPrompts,
    ModelSettingRefused,
    PromptRefused,
    check_module,
    defaults,
    layout_of,
    unusable_routes,
)
from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_V3, AiModelSettingsIn, AiPromptsIn
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.core.llm.prompts import parse_prompt_id
from esgapi.drafting.contracts import ai_setting_shapes as shapes
from esgapi.drafting.engines.v1 import pages
from esgapi.drafting.engines.v1 import texts as v1_texts
from esgapi.drafting.engines.v2 import material
from esgapi.drafting.engines.v2 import texts as v2_texts
from esgapi.drafting.engines.v2.texts import DEFAULT_TEXTS, MARKER_RULES, WRITING_RULES
from esgapi.drafting.flows import binding_v2, draft_v2
from esgapi.drafting.flows import prompt_model_v2 as pm

CONFIG: LlmConfig = load_config(default_config_sources(synthetic=False))
LIGHT = "light-openai-41"
STANDARD = "standard-openai-41"
KEYS = ["map_system", "map_user", "draft_system", "draft_user"]


def step(key: str, *, route: str = LIGHT, temperature: Any = 0.0, web_search: bool = False, cap: int = 4000) -> Any:
    return {"key": key, "route": route, "temperature": temperature, "webSearch": web_search, "maxOutputTokens": cap}


def model_body(**draft: Any) -> AiModelSettingsIn:
    """map 은 기본, draft 칸만 draft 의 값."""
    return {"steps": [step("map"), step("draft", **draft)]}


def prompts_body(**changed: str) -> AiPromptsIn:
    """기본 글 넷(메모 = 기본 메모) — changed 의 칸만 그 글."""
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


def accepted_prompts(given: AiPromptsIn) -> AcceptedPrompts:
    found = pm.accept_prompts(given)
    assert isinstance(found, AcceptedPrompts), found
    return found


def default_body() -> Any:
    return pm.prompt_model(CONFIG, setting_name=shapes.DEFAULT_NAME, model=defaults(CONFIG, pm.MODELS))


# ── 선언 ──


def test_the_declaration_is_the_order() -> None:
    check_module(pm.SPEC)
    assert [(s.key, s.label, s.routes, s.tool_loop) for s in pm.MODELS] == [
        ("map", "목차 달기", (LIGHT, STANDARD), False),
        ("draft", "초안 짓기", (LIGHT, STANDARD), False),
    ]
    assert pm.ROUTES[0] == draft_v2.ROUTE
    assert [(g.key, g.label, g.prompt_keys, g.model_slots) for g in pm.GROUPS] == [
        ("map", "목차 달기", ("map_system", "map_user"), ("map",)),
        ("draft", "초안 짓기", ("draft_system", "draft_user"), ("draft",)),
    ]
    assert layout_of(pm.SPEC) == pm.LAYOUT
    assert [key for _, group in pm.LAYOUT for key in group] == KEYS
    assert set(pm.LABELS) == set(pm.FIELDS) == set(pm.DEFAULT_MEMOS) == set(pm.PLACEHOLDERS) == set(KEYS)
    assert [pm.LABELS[key] for key in KEYS] == ["지시 글", "입력 글"] * 2
    assert set(pm.FIELDS.values()) == {f.name for f in dataclasses.fields(DEFAULT_TEXTS)}
    assert pm.PROMPT_VERSION == binding_v2.ENGINE
    assert f"default_{binding_v2.ENGINE}" == shapes.DEFAULT_NAME  # 저장 판 이름 v<n> 과 겹치지 않게
    assert pm.OUTPUT_MARKS == {}
    assert unusable_routes(CONFIG, pm.MODELS) == ()


def test_the_default_model_values_are_the_flow_constants() -> None:
    model = defaults(CONFIG, pm.MODELS)
    assert [(s.key, s.route, s.temperature, s.web_search, s.max_output_tokens) for s in model.steps] == [
        (key, draft_v2.ROUTE, draft_v2.TEMPERATURE, False, draft_v2.MAX_OUTPUT_TOKENS) for key in ("map", "draft")
    ]


def test_the_placeholders_are_every_slot_of_the_default_texts() -> None:
    every = (v2_texts.OUTLINE_SLOT, v2_texts.PAGES_SLOT, v2_texts.TITLE_SLOT, v2_texts.REQUIREMENT_SLOT)
    for key in KEYS:
        assert tuple(slot for slot in every if slot in pm.default_text(key)) == tuple(
            sorted(pm.PLACEHOLDERS[key], key=every.index)
        ), key
    assert {"map_user": pm.PLACEHOLDERS["map_user"], "draft_user": pm.PLACEHOLDERS["draft_user"]} == pm.REQUIRED


# ── @3 ──


def test_the_default_prompt_model_is_strict_v3() -> None:
    body = default_body()
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    assert (body["schemaVersion"], body["module"], body["settingName"]) == (
        "ai.prompt-model@3",
        "drafting",
        "default_v2",
    )
    assert body["editable"] == {"prompts": True, "model": True}
    assert [(slot["key"], slot["label"], slot["unavailableRoutes"]) for slot in body["models"]] == [
        ("map", "목차 달기", []),
        ("draft", "초안 짓기", []),
    ]
    for slot in body["models"]:
        assert [c["route"] for c in slot["routeChoices"]] == [LIGHT, STANDARD]
        assert slot["model"]["webSearch"] is False
    assert [group["key"] for group in body["promptGroups"]] == ["map", "draft"]
    assert [group["modelSlots"] for group in body["promptGroups"]] == [["map"], ["draft"]]
    assert [group["key"] for group in body["fixed"]] == ["rules", "processing"]


def test_each_entry_is_the_v2_engine_text_the_memo_and_the_flow_prompt_id() -> None:
    body = default_body()
    entries = {p["key"]: (group["key"], p) for group in body["promptGroups"] for p in group["prompts"]}
    assert list(entries) == KEYS
    for key, (group, entry) in entries.items():
        engine = getattr(DEFAULT_TEXTS, pm.FIELDS[key])
        assert entry["text"] == entry["defaultText"] == engine, key
        assert (entry["memo"], entry["label"], entry["isDefault"]) == (pm.DEFAULT_MEMOS[key], pm.LABELS[key], True)
        assert entry["promptId"] == draft_v2.PROMPT_IDS[group]
        parse_prompt_id(entry["promptId"])
        assert entry["promptVersion"] == "v2"
        assert entry["outputSection"] is None
        assert len(engine) <= body["limits"]["textMax"], key
    assert [entries[key][1]["memo"] for key in ("map_user", "draft_user")] == ["", ""]
    assert MARKER_RULES not in entries["draft_system"][1]["text"]  # 꼬리는 칸 밖(⑦)
    assert WRITING_RULES not in entries["draft_system"][1]["text"]


def test_a_saved_text_is_not_folded_into_the_default() -> None:
    saved = accepted_prompts(prompts_body(draft_system="⟦지어낸 초안 지시 글⟧"))
    body = pm.prompt_model(CONFIG, setting_name="v1", model=defaults(CONFIG, pm.MODELS), prompts=saved)
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    entries = {p["key"]: p for g in body["promptGroups"] for p in g["prompts"]}
    assert [key for key, e in entries.items() if not e["isDefault"]] == ["draft_system"]
    assert entries["draft_system"]["outputKept"] is True  # 절 없는 칸
    assert pm.texts_from(accepted_prompts(prompts_body())) == DEFAULT_TEXTS


# ── 받기 ──


def test_a_null_temperature_is_refused() -> None:
    found = pm.accept_model(CONFIG, model_body(temperature=None))
    assert found == ModelSettingRefused(
        "ai_model_temperature_range", "temperature 는 0~2 사이 수로 넣어 주세요", "draft"
    )


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (model_body(temperature=2.5), "ai_model_temperature_range"),
        (model_body(route="mock"), "ai_model_route_unknown"),
        (model_body(web_search=True), "ai_model_web_search_unsupported"),
        (model_body(cap=10**9), "ai_model_max_output_range"),
    ],
)
def test_the_core_model_rules_still_refuse(body: AiModelSettingsIn, code: str) -> None:
    found = pm.accept_model(CONFIG, body)
    assert isinstance(found, ModelSettingRefused)
    assert (found.code, found.step) == (code, "draft")


def test_an_edited_model_is_accepted() -> None:
    found = pm.accept_model(CONFIG, model_body(route=STANDARD, temperature=0.7, cap=8000))
    assert isinstance(found, AcceptedModelSettings)
    assert [(s.key, s.route, s.temperature, s.max_output_tokens) for s in found.steps] == [
        ("map", LIGHT, 0.0, 4000),
        ("draft", STANDARD, 0.7, 8000),
    ]


REQUIRED_CASES = [(index, key, slot) for index, key in enumerate(KEYS) for slot in pm.REQUIRED.get(key, ())]


@pytest.mark.parametrize(("index", "key", "slot"), REQUIRED_CASES)
def test_an_input_text_must_keep_every_slot(index: int, key: str, slot: str) -> None:
    text = pm.default_text(key).replace(slot, "(지운 자리)")
    found = pm.accept_prompts(prompts_body(**{key: text}))
    assert found == PromptRefused(
        "ai_prompt_placeholder_missing",
        f"입력 글에서 {slot} 자리를 지우면 안 돼요",
        f"prompts.steps.{index // 2}.prompts.{index % 2}.text",
    )


def test_the_slot_cases_cover_every_input_slot() -> None:
    assert len(REQUIRED_CASES) == 2 + 3


@pytest.mark.parametrize("key", ["map_system", "draft_system"])
def test_a_system_text_may_be_replaced_whole(key: str) -> None:
    assert isinstance(pm.accept_prompts(prompts_body(**{key: "⟦지어낸 지시 글⟧"})), AcceptedPrompts)


def test_moved_slots_are_kept() -> None:
    moved = "⟦지어낸 입력 글⟧ {페이지 글} · {요구 내용}{제목 경로}"
    assert isinstance(pm.accept_prompts(prompts_body(draft_user=moved)), AcceptedPrompts)


def test_the_core_prompt_rules_run_first() -> None:
    found = pm.accept_prompts(prompts_body(map_user="  "))
    assert isinstance(found, PromptRefused)
    assert (found.code, found.field) == ("ai_prompt_text_empty", "prompts.steps.0.prompts.1.text")


# ── 잇기 ──


def test_texts_from_maps_each_key_to_its_engine_field() -> None:
    marks = {key: f"⟦RPA1-{key}⟧" + pm.default_text(key) for key in KEYS}
    texts = pm.texts_from(accepted_prompts(prompts_body(**marks)))
    assert {key: getattr(texts, pm.FIELDS[key]) for key in KEYS} == marks
    assert pm.texts_from(None) is DEFAULT_TEXTS


# ── 고정 값 ──


def test_the_fixed_values() -> None:
    rules, processing = pm.fixed_groups()
    assert (rules["key"], rules["label"], processing["key"], processing["label"]) == (
        "rules",
        "근거 표지·글 규칙",
        "processing",
        "실행 규칙",
    )
    assert [(item["key"], item["value"]) for item in rules["items"]] == [
        ("markers", MARKER_RULES),
        ("writing", WRITING_RULES),
    ]
    assert [(item["key"], item["value"]) for item in processing["items"]] == [
        ("page_max_chars", pages.PAGE_MAX_CHARS),
        ("batch_max_chars", pages.BATCH_MAX_CHARS),
        ("material_max_chars", material.MATERIAL_MAX_CHARS),
        ("timeout_ms", draft_v2.TIMEOUT_MS),
    ]
    assert [item["value"] for item in processing["items"]] == [8000, 24000, 40000, 120000]  # 한 번은 글자로
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


def test_the_flow_file_writes_no_number_and_one_route() -> None:
    found = _literals(ast.parse(Path(pm.__file__).read_text(encoding="utf-8")))
    assert {value for value in found if isinstance(value, int | float)} <= {0, 1}
    assert [v for v in found if isinstance(v, str) and ("openai" in v or "gpt" in v or "claude" in v)] == [STANDARD]
    assert [v for v in found if isinstance(v, str) and any(ch.isdigit() for ch in v) and "$" in v] == []


# ── RPA4 B7 — 판 말 글자(서버 label·메모)·key 그대로·v2 슬롯 ──


def test_rpa4_b7_the_labels_are_the_board_words_and_the_keys_did_not_move() -> None:
    assert [(spec.key, spec.label) for spec in pm.MODELS] == [("map", "목차 달기"), ("draft", "초안 짓기")]
    assert [(group.key, group.label, group.prompt_keys) for group in pm.GROUPS] == [
        ("map", "목차 달기", ("map_system", "map_user")),
        ("draft", "초안 짓기", ("draft_system", "draft_user")),
    ]
    rules, processing = pm.fixed_groups()
    assert [(item["key"], item["label"]) for item in rules["items"] + processing["items"]] == [
        ("markers", "자료 표지"),
        ("writing", "글 규칙"),
        ("page_max_chars", "페이지 글 상한(자)"),
        ("batch_max_chars", "페이지 묶음 상한(자)"),
        ("material_max_chars", "초안 재료 전체 상한(자)"),
        ("timeout_ms", "호출 시간 상한(밀리초)"),
    ]
    assert (rules["label"], processing["label"]) == ("근거 표지·글 규칙", "실행 규칙")


def test_rpa4_b7_the_memos() -> None:
    assert (
        pm.DEFAULT_MEMOS["map_system"] == "페이지마다 그 내용이 쓰일 목차 잎 key 를 고름 — 목록에 없는 key 는 쓰지 않음"
    )
    assert (
        pm.DEFAULT_MEMOS["draft_system"] == "자료에 적힌 사실만으로 개조식 bullet · bullet 마다 근거 블록과 문장을 닮"
    )
    assert all("쪽" not in memo for memo in pm.DEFAULT_MEMOS.values())


def test_rpa4_b7_the_required_slots_are_the_v2_slots() -> None:
    assert pm.REQUIRED == {
        "map_user": (v2_texts.OUTLINE_SLOT, "{페이지 글}"),
        "draft_user": (v2_texts.TITLE_SLOT, v2_texts.REQUIREMENT_SLOT, "{페이지 글}"),
    }
    assert all(v1_texts.PAGES_SLOT not in slots for slots in pm.REQUIRED.values())
