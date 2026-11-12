"""flows/prompt_model_e0(밴드 AS2a §3-1): 그린워싱 판의 ai.prompt-model@1 — AS1 꼴 strict 통과, 판정 단계 하나·프롬프트
넷의 차례·id·판 글자, eval 의 sha 가 실행의 run_versions 와 같음(기본 판·고친 판), 모델 칸·고를 경로의 능력, 명세 위생,
못 받는 기준표의 CriteriaRejected.

설정은 패키지의 실제 파일(default_config_sources(synthetic=False))이다. 기준 글은 지어낸 것이다. 실제 AI 호출 0.
"""

import ast
import copy
import dataclasses
import hashlib
import importlib
from pathlib import Path
from typing import Any, cast

import pytest

from esgapi.core.calc.ai_settings import (
    PROMPT_MEMO_MAX_CHARS,
    PROMPT_TEXT_MAX_CHARS,
    AcceptedModelSettings,
    AcceptedPrompts,
    ModelSettingRefused,
    check_module,
    check_prompts,
    defaults,
    layout_of,
    model_settings_sha256,
    route_choice,
    to_input,
    unusable_routes,
)
from esgapi.core.contracts.ai_setting_shapes import (
    PROMPT_MODEL_V3,
    AiModelSettingsIn,
    AiModelStepIn,
    AiPromptModel3,
    AiPromptsIn,
)
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.core.llm.errors import LlmConfigError
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.engines.e0 import checker as checker_mod
from esgapi.greenwash.engines.e0.prompts import default_prompts
from esgapi.greenwash.flows import binding_e0, colab_e0, criteria_e0
from esgapi.greenwash.flows import prompt_model_e0 as pm

CONFIG: LlmConfig = load_config(default_config_sources(synthetic=False))
VERSION = colab_e0.judged_prompt_version(dict(colab_e0.SCAN_CONFIG))


def build(criteria: GreenwashCriteria | None = None, name: str = criteria_e0.DEFAULT_VERSION) -> AiPromptModel3:
    return pm.prompt_model(
        CONFIG,
        setting_name=name,
        criteria=criteria,
        model=defaults(CONFIG, pm.STEPS),
        editable_model=pm.EDITABLE_MODEL,
    )


def edited(text: str = "지어낸 기준 글: 근거 없이 쓴 환경 성과 주장") -> GreenwashCriteria:
    criteria: dict[str, Any] = copy.deepcopy(dict(criteria_e0.default_criteria()))
    criteria["version"] = "v1"
    criteria["rows"][9]["text"] = text
    return criteria  # type: ignore[return-value]


def prompts_of(found: AiPromptModel3) -> dict[str, Any]:
    return {entry["key"]: entry for entry in found["promptGroups"][0]["prompts"]}


# ── 1. 꼴·단계·프롬프트 차례 ──


def test_the_default_board_passes_the_as1_shape_strictly() -> None:
    found = build()
    PROMPT_MODEL_V3.validate_python(found, strict=True)
    assert found["schemaVersion"] == "ai.prompt-model@3"
    assert found["module"] == "greenwash"
    assert found["settingName"] == criteria_e0.DEFAULT_VERSION
    assert [slot["key"] for slot in found["models"]] == [group["key"] for group in found["promptGroups"]] == ["judge"]
    assert found["models"][0]["label"] == found["promptGroups"][0]["label"] == "판정"
    entries = found["promptGroups"][0]["prompts"]
    assert [entry["key"] for entry in entries] == list(colab_e0.PROMPT_IDS)
    assert [entry["promptId"] for entry in entries] == [colab_e0.PROMPT_IDS[entry["key"]] for entry in entries]
    assert {entry["promptVersion"] for entry in entries} == {VERSION}
    assert [entry["label"] for entry in entries] == [label for _, label, _ in pm.PROMPTS]
    assert [entry["label"] for entry in entries] == ["문장 찾기", "판정", "수정 방향 다듬기", "Low 문장 설명"]
    assert found["editable"] == {"prompts": pm.EDITABLE_PROMPTS, "model": pm.EDITABLE_MODEL}
    assert found["editable"] == {"prompts": True, "model": True}  # AS2b 모델 · AS3a-2 프롬프트 글을 새 판에


def test_the_prompt_texts_are_the_engine_pack() -> None:
    pack = default_prompts(VERSION)
    texts = {key: entry["text"] for key, entry in prompts_of(build()).items()}
    assert texts == {
        "detect": pack.detect_system_prompt,
        "eval": pack.eval_system_prompt,
        "repair": pack.repair_fix_prompt,
        "low_only": pack.low_only_prompt,
    }


# ── 2. eval sha 대조 ──


def test_the_eval_sha_is_the_run_versions_sha() -> None:
    default = prompts_of(build())
    assert default["eval"]["sha256"] == colab_e0.run_versions(None)["evalPromptSha256"]

    criteria = edited()
    changed = prompts_of(build(criteria, "v1"))
    accepted = criteria_e0.accept_criteria(criteria)
    assert changed["eval"]["text"] == criteria_e0.build_eval_prompt(accepted, VERSION)
    assert changed["eval"]["sha256"] == colab_e0.run_versions(criteria)["evalPromptSha256"]
    assert changed["eval"]["sha256"] != default["eval"]["sha256"]  # 분모: 고친 판은 다른 글
    for key in ("detect", "repair", "low_only"):
        assert changed[key]["text"].encode() == default[key]["text"].encode(), key
    for entry in (*default.values(), *changed.values()):
        assert entry["sha256"] == hashlib.sha256(entry["text"].encode("utf-8")).hexdigest()


# ── 3. 모델 칸 ──


def test_the_model_cell_is_the_colab_defaults() -> None:
    found = build()
    step = found["models"][0]
    model = step["model"]
    assert model["route"] == colab_e0.CHAT_ROUTE
    assert model["temperature"] == checker_mod.TEMPERATURE
    assert model["maxOutputTokens"] == colab_e0.MAX_OUTPUT_TOKENS
    assert model["webSearch"] is False
    # 한 번은 글자로
    assert (model["route"], model["temperature"], model["maxOutputTokens"]) == ("light-openai-41", 0.0, 1300)
    assert model["models"][0]["key"] == "gpt-4.1-mini"
    choices = step["routeChoices"]
    assert [choice["route"] for choice in choices] == list(pm.JUDGE_ROUTES)
    assert [choice["acceptsTemperature"] for choice in choices] == [True, True]
    assert [choice["maxOutputTokensMax"] for choice in choices] == [32768, 32768]
    standard = {choice["route"]: choice for choice in choices}["standard-openai-41"]
    assert standard["webSearchAvailable"] is False  # judge 는 도구 고리가 아니다
    assert route_choice(CONFIG, "standard-openai-41", tool_loop=True)["webSearchAvailable"] is True  # 분모
    assert found["modelSettingsSha256"] == model_settings_sha256(defaults(CONFIG, pm.STEPS))


# ── 4. 명세 위생 ──


def test_the_spec_points_at_real_routes_only() -> None:
    assert set(pm.JUDGE_ROUTES) <= set(CONFIG.routes)
    for route in pm.JUDGE_ROUTES:
        providers = {ref["provider"] for ref in route_choice(CONFIG, route, tool_loop=False)["models"]}
        assert not [p for p in providers if p.startswith("mock")], route
    assert pm.JUDGE.default["route"] in pm.JUDGE.routes
    assert pm.STEPS == (pm.JUDGE,)
    defaults(CONFIG, pm.STEPS)  # 거절이면 LlmConfigError
    assert [key for key, _, _ in pm.PROMPTS] == list(colab_e0.PROMPT_IDS)


def test_the_module_writes_no_number() -> None:
    tree = ast.parse(Path(pm.__file__).read_text(encoding="utf-8"))
    numbers = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, int | float)
        and not isinstance(node.value, bool)
        and node.value not in (0, 1)
    ]
    assert numbers == []


# ── 5. 못 받는 기준표 ──


def test_a_criteria_the_rules_no_longer_take_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "지어낸 기준 글: 좁히면 받지 못할 만큼 조금 긴 글"
    criteria = edited(text)
    build(criteria, "v1")  # 분모: 좁히기 전엔 지어진다
    monkeypatch.setattr(criteria_e0, "TEXT_CHARS", max(len(r["text"]) for r in criteria["rows"]) - 1)
    with pytest.raises(criteria_e0.CriteriaRejected) as refused:
        build(criteria, "v1")
    assert refused.value.code == "CRITERIA_TEXT_LENGTH"
    build(None)  # 기본 판은 받기를 지나지 않는다(엔진 글 그대로)


# ── AS2b 3-1. 판의 모델 설정 받기·이행 상수 ──

STANDARD: AiModelStepIn = {
    "key": "judge",
    "route": "standard-openai-41",
    "temperature": 0.7,
    "webSearch": False,
    "maxOutputTokens": 2000,
}


def test_the_migration_constant_is_the_code_value() -> None:
    """0003 이 기존 행에 채우는 글자 상수 == 지금 코드 값의 정규형(코드 import 없이 박은 값이 어긋나지 않는다)."""
    migration = importlib.import_module("esgapi.greenwash.migrations.0003_ai_settings_model_settings")
    assert to_input(defaults(CONFIG, pm.STEPS)) == migration.MODEL_SETTINGS_BEFORE_AS2B


def test_the_stored_shape_round_trips() -> None:
    """저장 꼴(to_input)을 다시 받으면 같은 값 — 기본값과 다른 판(standard·0.7·2000)도."""
    standard: AiModelSettingsIn = {"steps": [STANDARD]}
    for given in (to_input(defaults(CONFIG, pm.STEPS)), standard):
        accepted = pm.accept_model(CONFIG, given)
        assert isinstance(accepted, AcceptedModelSettings)
        assert pm.accept_model(CONFIG, to_input(accepted)) == accepted


@pytest.mark.parametrize(
    ("change", "code"),
    [
        pytest.param({"route": "light-openai"}, "ai_model_route_unknown", id="route-outside"),
        pytest.param({"webSearch": True}, "ai_model_web_search_unsupported", id="web-search"),
        pytest.param({"maxOutputTokens": 32769}, "ai_model_max_output_range", id="max-output"),
        pytest.param({"key": "scan"}, "ai_model_steps_fixed", id="step-key"),
    ],
)
def test_accept_model_passes_the_as1_codes(change: dict[str, Any], code: str) -> None:
    """accept_model 은 core 받기 한 겹 — AS1 의 거절 code 를 그대로. 분모: 같은 단계의 받는 값은 지난다."""
    assert isinstance(pm.accept_model(CONFIG, {"steps": [STANDARD]}), AcceptedModelSettings)
    refused = pm.accept_model(CONFIG, cast("AiModelSettingsIn", {"steps": [{**STANDARD, **change}]}))
    assert isinstance(refused, ModelSettingRefused)
    assert refused.code == code


def test_the_steps_have_no_unusable_route() -> None:
    """CO1(MARC-ISSUE-248): 명세가 허용한 경로는 실제 설정에서 받기가 늘 거절하지 않는다(설정에 있음·도구 고리)."""
    assert unusable_routes(CONFIG, pm.STEPS) == ()


# ── AS3a-1 3-5. ai.prompt-model@2 의 칸 다섯·limits·editable ──


ENGINE_FIELDS = {
    "detect": "detect_system_prompt",
    "eval": "eval_system_prompt",
    "repair": "repair_fix_prompt",
    "low_only": "low_only_prompt",
}


def test_the_default_board_shows_the_new_cells() -> None:
    found = build()
    PROMPT_MODEL_V3.validate_python(found, strict=True)
    pack = default_prompts(VERSION)
    entries = prompts_of(found)
    assert list(entries) == list(colab_e0.PROMPT_IDS)
    for key, entry in entries.items():
        engine = getattr(pack, ENGINE_FIELDS[key])
        assert entry["defaultText"] == engine == entry["text"], key
        assert (entry["isDefault"], entry["outputKept"]) == (True, True), key
        assert entry["memo"] == pm.DEFAULT_MEMOS[key]
        assert entry["outputSection"] is not None and engine.endswith(entry["outputSection"]), key
        assert entry["outputSection"].startswith(pm.OUTPUT_MARK)
    assert found["limits"] == {"textMax": PROMPT_TEXT_MAX_CHARS, "memoMax": PROMPT_MEMO_MAX_CHARS}
    assert found["editable"] == {"prompts": True, "model": True}
    assert pm.EDITABLE_PROMPTS is True


def test_the_output_sections_are_the_last_mark_to_the_end() -> None:
    """★A: 넷 다 표지 하나, 절 길이 82·384·39·285자(한 번은 글자로)."""
    pack = default_prompts(VERSION)
    lengths = {}
    for key, field in ENGINE_FIELDS.items():
        text = getattr(pack, field)
        assert text.count(pm.OUTPUT_MARK) == 1, key
        section = pm.output_section(text)
        assert section is not None
        lengths[key] = len(section)
    assert lengths == {"detect": 82, "eval": 384, "repair": 39, "low_only": 285}
    assert pm.output_section("표지 없는 지어낸 글") is None


def test_a_criteria_board_keeps_the_engine_default_text() -> None:
    """기준표로 지은 판정 글은 text 이고 defaultText 는 엔진 글 그대로 — 되돌림은 엔진 글로."""
    entries = prompts_of(build(edited(), "v1"))
    pack = default_prompts(VERSION)
    assert entries["eval"]["defaultText"] == pack.eval_system_prompt != entries["eval"]["text"]
    assert entries["eval"]["isDefault"] is False
    assert entries["eval"]["outputKept"] is True  # 기준표 판정 글도 출력절은 그대로


def test_the_layout_is_the_judge_step_and_the_four_keys() -> None:
    assert pm.LAYOUT == (("judge", ("detect", "eval", "repair", "low_only")),)
    assert pm.LAYOUT[0][1] == tuple(colab_e0.PROMPT_IDS)
    # AS3a-2 M2: layout 은 colab_e0 하나(워커와 같은 것), 칸 → PromptPack 칸 표도 prompt_model_e0 의 표와 같다
    assert pm.LAYOUT is colab_e0.LAYOUT
    assert dict(colab_e0.PROMPT_FIELDS) == {key: field for key, _, field in pm.PROMPTS}
    assert list(colab_e0.PROMPT_FIELDS) == list(colab_e0.PROMPT_IDS)


# ── AS3a-1 3-6. 저장 글을 넘김(critic 1 B2) ──


def saved_prompts(changes: dict[str, str]) -> AcceptedPrompts:
    pack = default_prompts(VERSION)
    given: AiPromptsIn = {
        "steps": [
            {
                "key": "judge",
                "prompts": [
                    {"key": key, "text": changes.get(key, str(getattr(pack, field))), "memo": f" 지어낸 메모 {key} "}
                    for key, field in ENGINE_FIELDS.items()
                ],
            }
        ]
    }
    accepted = check_prompts(given, layout=pm.LAYOUT)
    assert isinstance(accepted, AcceptedPrompts), accepted
    return accepted


def test_a_saved_text_with_a_broken_output_section_is_marked() -> None:
    pack = default_prompts(VERSION)
    engine = pack.low_only_prompt
    section = pm.output_section(engine)
    assert section is not None
    broken = engine[: len(engine) - len(section)] + section.replace("[출력(JSON", "[출력 (JSON", 1)
    found = pm.prompt_model(
        CONFIG,
        setting_name="v1",
        criteria=None,
        model=defaults(CONFIG, pm.STEPS),
        editable_model=True,
        prompts=saved_prompts({"low_only": broken}),
    )
    PROMPT_MODEL_V3.validate_python(found, strict=True)
    entries = prompts_of(found)
    low = entries["low_only"]
    assert low["text"] == broken and low["outputSection"] == section  # 절은 엔진 글에서
    assert (low["isDefault"], low["outputKept"]) == (False, False)
    assert low["memo"] == "지어낸 메모 low_only"  # 받은 정규형(strip)
    assert (low["promptId"], low["promptVersion"]) == (colab_e0.PROMPT_IDS["low_only"], VERSION)
    for key in ("detect", "eval", "repair"):
        assert (entries[key]["isDefault"], entries[key]["outputKept"]) == (True, True), key
        assert entries[key]["memo"] == f"지어낸 메모 {key}"


# ── AS3a-1 3-7. 고정 값 ──


def test_the_fixed_values_come_from_the_code() -> None:
    groups = {group["key"]: group for group in build()["fixed"]}
    assert list(groups) == ["parts", "processing"]
    assert (groups["parts"]["label"], groups["processing"]["label"]) == ("파트", "처리 값")
    parts = groups["parts"]["items"]
    assert [item["key"] for item in parts] == list(binding_e0.PARTS)
    assert [item["label"] for item in parts] == list(colab_e0.PART_ORDER)
    assert [item["value"] for item in parts] == [None] * len(parts)
    cfg = colab_e0.scan_cfg()
    processing = groups["processing"]["items"]
    assert [(item["key"], item["value"]) for item in processing] == [
        (item["key"], getattr(cfg, item["key"])) for item in processing
    ]
    # 한 번은 글자로(r3 처리 값 다섯)
    assert [item["value"] for item in processing] == [3, 2500, 2, 450, 1600]
    assert [item["label"] for item in processing] == [
        "페이지당 후보 문장",
        "페이지 글자",
        "근거 조각 수",
        "조각 글자",
        "근거 합 글자",
    ]


def test_the_fixed_values_are_built_on_call_not_on_import(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    real = colab_e0.scan_cfg

    def counted() -> Any:
        calls.append(1)
        return real()

    monkeypatch.setattr(colab_e0, "scan_cfg", counted)
    importlib.reload(pm)
    assert calls == []
    pm.fixed_groups()
    assert calls == [1]


# ── AP1b 3-1-5. 모듈 선언(core 부품) ──


def test_the_module_declaration_passes_the_core_check() -> None:
    check_module(pm.MODULE_SPEC)
    assert pm.MODULE_SPEC.module == pm.MODULE == "greenwash"
    assert pm.MODULE_SPEC.models == pm.STEPS


def test_the_declarations_layout_is_the_workers() -> None:
    assert layout_of(pm.MODULE_SPEC) == pm.LAYOUT == colab_e0.LAYOUT
    (group,) = pm.MODULE_SPEC.groups
    assert (group.key, group.label, group.model_slots) == ("judge", "판정", ("judge",))


def test_editable_is_the_module_prompts_and_the_given_model() -> None:
    """editable 은 모듈 능력(prompts = EDITABLE_PROMPTS)과 넘긴 editable_model 이다(AP1b)."""
    found = pm.prompt_model(
        CONFIG, setting_name="v1", criteria=None, model=defaults(CONFIG, pm.STEPS), editable_model=False
    )
    assert found["editable"] == {"prompts": pm.EDITABLE_PROMPTS, "model": False}


# ── AP1b 3-4-0. 설정에서 빠진 경로(MARC-ISSUE-280) ──


def without(route: str) -> LlmConfig:
    """설정에서 경로 하나를 뺀 것(배포가 그 경로를 내린 꼴)."""
    return dataclasses.replace(CONFIG, routes={k: v for k, v in CONFIG.routes.items() if k != route})


def test_a_route_missing_from_the_config_is_unavailable_not_an_error() -> None:
    config = without("standard-openai-41")
    found = pm.prompt_model(
        config, setting_name="v1", criteria=None, model=defaults(config, pm.STEPS), editable_model=True
    )
    PROMPT_MODEL_V3.validate_python(found, strict=True)
    (slot,) = found["models"]
    assert slot["unavailableRoutes"] == ["standard-openai-41"]
    assert [choice["route"] for choice in slot["routeChoices"]] == ["light-openai-41"]
    assert build()["models"][0]["unavailableRoutes"] == []  # 분모: 설정에 다 있으면 빈 목록


def test_a_chosen_route_missing_from_the_config_is_a_config_error() -> None:
    """고른(기본) 경로 자체가 빠진 설정은 배포 잘못 — 지금처럼 LlmConfigError(AP1a Q4)."""
    with pytest.raises(LlmConfigError, match="light-openai-41"):
        pm.prompt_model(
            without("light-openai-41"),
            setting_name="v1",
            criteria=None,
            model=defaults(CONFIG, pm.STEPS),
            editable_model=True,
        )
