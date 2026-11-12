"""데이터 검증 AI 설정 판의 선언과 ai.prompt-model@3(밴드 DVA1 §3-3-1 — 순수 층, DB 0).

    선언      check_module(SPEC) · 모델 칸 하나·묶음 셋·칸 여섯이 발주서 2-1 · 기본 값이 흐름 상수 · promptId core 문법
    @3        기본 판 strict · defaultText == 엔진 글 · outputSection 은 계획·인사이트 지시 글 둘만 · editable 둘 true
    받기      temperature null 거절(Q6) · core 꼴 code · 입력 글 자리 지킴(Q3·Q4) · 지시 글 자리는 지워도 됨
    잇기      texts_from·models_from 이 칸 key → 엔진·흐름 값
    고정 값   한 번은 글자로("0.0"·12·「산식 수 × 3 · 36 까지」·12) · TOOL_KINDS · AST: 0·1 밖 수·경로·단가 글자 0
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
from esgapi.dataverify.contracts import ai_setting_shapes as shapes
from esgapi.dataverify.engines.colab_156 import prompts, schemas
from esgapi.dataverify.engines.colab_156.prompts import DEFAULT_TEXTS
from esgapi.dataverify.flows import binding_156, colab_156
from esgapi.dataverify.flows import prompt_model_156 as pm

CONFIG: LlmConfig = load_config(default_config_sources(synthetic=False))
STANDARD = "standard-openai-41"
KEYS = ["plan_system", "plan_user", "review_system", "review_user", "insight_system", "insight_user"]


def model_body(
    *, route: str = STANDARD, temperature: Any = 0.1, web_search: bool = True, cap: int = 32768
) -> AiModelSettingsIn:
    return {
        "steps": [
            {
                "key": "shared",
                "route": route,
                "temperature": temperature,
                "webSearch": web_search,
                "maxOutputTokens": cap,
            }
        ]
    }


def prompts_body(**changed: str) -> AiPromptsIn:
    """기본 글 여섯(메모 = 기본 메모) — changed 의 칸만 그 글."""
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
        ("shared", "세 단계 공통", (STANDARD,), True)
    ]
    assert pm.MODELS[0].routes == (colab_156.ROUTE,)
    assert [(g.key, g.label, g.prompt_keys, g.model_slots) for g in pm.GROUPS] == [
        ("plan", "계산 계획", ("plan_system", "plan_user"), ("shared",)),
        ("review", "계산 검토", ("review_system", "review_user"), ("shared",)),
        ("insight", "리스크 진단", ("insight_system", "insight_user"), ("shared",)),
    ]
    assert layout_of(pm.SPEC) == pm.LAYOUT
    assert [key for _, group in pm.LAYOUT for key in group] == KEYS
    assert set(pm.LABELS) == set(pm.FIELDS) == set(pm.DEFAULT_MEMOS) == set(KEYS)
    assert [pm.LABELS[key] for key in KEYS] == ["지시 글", "입력 글"] * 3
    assert set(pm.FIELDS.values()) == {f.name for f in dataclasses.fields(DEFAULT_TEXTS)}
    assert pm.PROMPT_VERSION == binding_156.ENGINE == shapes.DEFAULT_NAME
    assert unusable_routes(CONFIG, pm.MODELS) == ()


def test_the_default_model_values_are_the_flow_constants() -> None:
    model = defaults(CONFIG, pm.MODELS)  # ★D: 지금 설정에서 기본값이 받기를 지난다(gpt-4.1 web_search·위끝)
    assert [(s.key, s.route, s.temperature, s.web_search, s.max_output_tokens) for s in model.steps] == [
        ("shared", colab_156.ROUTE, colab_156.TEMPERATURE, True, colab_156.MAX_OUTPUT_TOKENS)
    ]
    assert pm.models_from(model) == pm.StageModel(
        route=colab_156.ROUTE, temperature=colab_156.TEMPERATURE, max_output_tokens=colab_156.MAX_OUTPUT_TOKENS
    )


# ── @3 ──


def test_the_default_prompt_model_is_strict_v3() -> None:
    body = default_body()
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    assert (body["schemaVersion"], body["module"], body["settingName"]) == (
        "ai.prompt-model@3",
        "dataverify",
        "colab_156",
    )
    assert body["editable"] == {"prompts": True, "model": True}
    (slot,) = body["models"]
    assert (slot["key"], slot["label"], slot["unavailableRoutes"]) == ("shared", "세 단계 공통", [])
    assert [c["route"] for c in slot["routeChoices"]] == [STANDARD]
    assert slot["routeChoices"][0]["webSearchAvailable"] is True
    assert slot["model"]["webSearch"] is True
    assert [group["key"] for group in body["promptGroups"]] == ["plan", "review", "insight"]
    assert [group["modelSlots"] for group in body["promptGroups"]] == [["shared"]] * 3
    assert [group["key"] for group in body["fixed"]] == ["tools", "processing"]


def test_each_entry_is_the_engine_text_the_board_memo_and_the_core_prompt_id() -> None:
    body = default_body()
    entries = {p["key"]: (group["key"], p) for group in body["promptGroups"] for p in group["prompts"]}
    assert list(entries) == KEYS
    for key, (group, entry) in entries.items():
        engine = getattr(DEFAULT_TEXTS, pm.FIELDS[key])
        assert entry["text"] == entry["defaultText"] == engine, key
        assert (entry["memo"], entry["label"], entry["isDefault"]) == (pm.DEFAULT_MEMOS[key], pm.LABELS[key], True)
        assert entry["promptId"] == prompts.PROMPT_IDS[group] == f"dataverify/{group}@1"
        parse_prompt_id(entry["promptId"])  # core 프롬프트 id 문법(R1)
        assert entry["promptVersion"] == "colab_156"
        assert len(engine) <= body["limits"]["textMax"], key
    assert [entries[key][1]["memo"] for key in ("plan_user", "review_user", "insight_user")] == ["", "", ""]
    assert entries["review_system"][1]["text"] == prompts.REVIEW_SYSTEM
    assert "{기업명}" in entries["plan_user"][1]["text"]


def test_only_the_plan_and_insight_system_texts_carry_an_output_section() -> None:
    body = default_body()
    sections = {p["key"]: p["outputSection"] for g in body["promptGroups"] for p in g["prompts"]}
    assert {key for key, section in sections.items() if section is not None} == {"plan_system", "insight_system"}
    plan = prompts.PLAN_SYSTEM
    assert sections["plan_system"] == plan[plan.index("출력 규칙:") : plan.index("\n[툴 사용 및 스텝 제한 규칙]")]
    assert sections["insight_system"] == prompts.INSIGHT_SYSTEM[prompts.INSIGHT_SYSTEM.rfind("# 출력 형식") :]
    assert (sections["plan_system"] or "").startswith("출력 규칙:\n- 출력은 반드시 python list 형태여야 한다.")
    assert (sections["plan_system"] or "").endswith(
        '  "온실가스 집약도(1+2, KRW) = 총 배출량(Scope1+2 Emissions) / 매출액"\n]\n'
    )
    assert (sections["insight_system"] or "").endswith(
        "- 각 영역(환경, 사회, 지배구조)별로 구분하여 표를 제시하라.\n  "
    )


def test_a_saved_text_keeps_or_breaks_its_output_section_and_is_not_folded() -> None:
    kept = prompts.PLAN_SYSTEM.replace("역할:", "역할(지어낸 고침):", 1)
    broken = prompts.INSIGHT_SYSTEM.replace("# 출력 형식", "# 결과 꼴")
    saved = accepted_prompts(prompts_body(plan_system=kept, insight_system=broken, review_system="⟦지어낸 지시 글⟧"))
    body = pm.prompt_model(CONFIG, setting_name="v1", model=defaults(CONFIG, pm.MODELS), prompts=saved)
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    entries = {p["key"]: p for g in body["promptGroups"] for p in g["prompts"]}
    assert (entries["plan_system"]["outputKept"], entries["insight_system"]["outputKept"]) == (True, False)
    assert entries["review_system"]["outputKept"] is True  # 절 없는 칸
    assert [key for key, e in entries.items() if not e["isDefault"]] == [
        "plan_system",
        "review_system",
        "insight_system",
    ]
    assert (
        pm.texts_from(accepted_prompts(prompts_body())) == DEFAULT_TEXTS
    )  # 기본 글과 같은 저장 글 — 접지 않고 같은 글


# ── 받기 ──


@pytest.mark.parametrize("temperature", [None])
def test_a_null_temperature_is_refused(temperature: Any) -> None:
    found = pm.accept_model(CONFIG, model_body(temperature=temperature))
    assert found == ModelSettingRefused(
        "ai_model_temperature_range", "temperature 는 0~2 사이 수로 넣어 주세요", "shared"
    )


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (model_body(temperature=2.5), "ai_model_temperature_range"),
        (model_body(route="light-openai-41"), "ai_model_route_unknown"),
        (model_body(web_search=False), "ai_model_web_search_fixed"),
        (model_body(cap=40000), "ai_model_max_output_range"),
    ],
)
def test_the_core_model_rules_still_refuse(body: AiModelSettingsIn, code: str) -> None:
    found = pm.accept_model(CONFIG, body)
    assert isinstance(found, ModelSettingRefused)
    assert (found.code, found.step) == (code, "shared")


def test_an_edited_model_is_accepted() -> None:
    found = pm.accept_model(CONFIG, model_body(temperature=0, cap=8000))
    assert isinstance(found, AcceptedModelSettings)
    assert pm.models_from(found) == pm.StageModel(route=STANDARD, temperature=0.0, max_output_tokens=8000)


REQUIRED_CASES = [
    (index, key, slot) for index, key in enumerate(KEYS) if key.endswith("_user") for slot in prompts.REQUIRED[key]
]


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
    assert len(REQUIRED_CASES) == 5 + 2 + 5


@pytest.mark.parametrize("key", ["plan_system", "review_system", "insight_system"])
def test_a_system_text_may_drop_the_step_slots(key: str) -> None:
    text = pm.default_text(key)
    for slot in (prompts.STEPS, prompts.STEPS_MINUS_4, prompts.STEPS_MINUS_2):
        text = text.replace(slot, "")
    assert isinstance(pm.accept_prompts(prompts_body(**{key: text})), AcceptedPrompts)


def test_the_ascii_spelling_and_moved_slots_are_kept() -> None:
    moved = "⟦지어낸 입력 글⟧ {입력 데이터 JSON} · {중대토픽}{보고연도}{SASB 산업분류}{기업명}"
    assert isinstance(pm.accept_prompts(prompts_body(plan_user=moved)), AcceptedPrompts)


def test_the_core_prompt_rules_run_first() -> None:
    found = pm.accept_prompts(prompts_body(plan_user="  "))
    assert isinstance(found, PromptRefused)
    assert (found.code, found.field) == ("ai_prompt_text_empty", "prompts.steps.0.prompts.1.text")


# ── 잇기 ──


def test_texts_from_maps_each_key_to_its_engine_field() -> None:
    marks = {key: f"⟦DVA1-{key}⟧" + pm.default_text(key) for key in KEYS}
    texts = pm.texts_from(accepted_prompts(prompts_body(**marks)))
    assert {key: getattr(texts, pm.FIELDS[key]) for key in KEYS} == marks
    assert pm.texts_from(None) is DEFAULT_TEXTS


# ── 고정 값 ──


def test_the_fixed_values_once_in_letters() -> None:
    tools, processing = pm.fixed_groups()
    assert (tools["key"], tools["label"], processing["key"], processing["label"]) == (
        "tools",
        "계산 도구",
        "processing",
        "처리 값",
    )
    assert [(item["key"], item["label"]) for item in tools["items"]] == [
        ("sum", "두 값의 합"),
        ("sum_n", "여러 값의 합"),
        ("ratio", "비율"),
        ("value_of", "값 찾기"),
        ("search", "항목 찾기"),
    ]
    assert tools["items"][0]["value"] == "합계 = 앞 값 + 뒤 값인지 연도마다 봐요"
    assert [(item["key"], item["label"], item["value"]) for item in processing["items"]] == [
        ("tolerance", "판정 허용 오차", "0.0"),
        ("plan_steps", "계산 계획 걸음", 12),
        ("review_steps", "계산 검토 걸음", "산식 수 × 3 · 36 까지"),
        ("insight_steps", "리스크 진단 걸음", 12),
    ]
    assert default_body()["fixed"] == pm.fixed_groups()


def test_the_tool_kinds_split_the_eight_engine_tools() -> None:
    names = [tool["name"] for tool in schemas.TOOLS_RESPONSES]
    split = [name for kind in pm.TOOL_KINDS.values() for name in kind]
    assert sorted(split) == sorted(names) and len(split) == len(set(split)) == 8
    assert list(pm.TOOL_KINDS) == [key for key, _, _ in pm.TOOLS]


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
