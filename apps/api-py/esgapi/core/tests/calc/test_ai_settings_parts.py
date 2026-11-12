"""모듈 공통 AI 설정의 부품·모듈 선언·조합(core/calc/ai_settings.py — 밴드 AP1a, 결정 MARC-ENT-399). 순수 층.

모듈 선언 거절 여덟(`check_module`), 조합(`compose`)의 차례·열쇠 대조와 결과 꼴, 쓸 수 없는 경로가 `unavailableRoutes`
로 나옴(MARC-ISSUE-280 — `route_choices` 는 `unusable_routes` 와 같은 판정), 판 규칙 셋, core 에 모듈 글자 0(AST),
옛 판 행(저장 정규형)이 새 이름으로 그대로 읽히고 sha 둘이 BASE(4e28a54)에서 뽑은 값과 같음(마이그레이션 0).
모듈 이름·칸 key·글은 지어낸 것이다.
"""

import ast
import dataclasses
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from esgapi.core.calc import ai_settings
from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AcceptedPrompts,
    AiModelSlotSpec,
    AiModuleSpec,
    AiPromptGroupSpec,
    AiStepSpec,
    ai_versions,
    check_model_settings,
    check_module,
    check_prompts,
    compose,
    layout_of,
    model_settings_sha256,
    next_version_name,
    prompt_entry,
    prompt_limits,
    prompts_input,
    prompts_sha256,
    route_choice,
    route_choices,
    to_input,
    unusable_routes,
    version_status,
)
from esgapi.core.contracts import ai_setting_shapes
from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_V3, AiFixedGroup, AiModelStepIn, AiPromptEntry
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.log import sha256_text

CONFIG = load_config(default_config_sources(synthetic=False))
MISSING = dataclasses.replace(CONFIG, routes={k: v for k, v in CONFIG.routes.items() if k != "standard-openai-41"})
EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "ai-setting-examples"

# BASE(4e28a54) 트리를 git archive 로 밖에 풀어 그 트리의 셈으로 뽑은 값(★B — 보고 band-reports/AP1a.md).
BASE_EXAMPLE_MODEL_SHA = "4cfca533661b6611b792c63e12fbc41a5fe26ca618e63142859a88ddc642b7b0"
BASE_EXAMPLE_PROMPTS_SHA = "219d8f302e2432825bdd237d8c53c9ce911259493537c9b99c79beb7fe98026d"
BASE_DEFAULT_MODEL_SHA = "6392cbf83b77fcbd9c5032a1050d075165094e756d53b6204395cf46bac041ec"


def step(key: str, route: str = "light-openai-41", **over: Any) -> AiModelStepIn:
    value: dict[str, Any] = {"key": key, "route": route, "temperature": 0.0, "webSearch": False, "maxOutputTokens": 900}
    value.update(over)
    return cast("AiModelStepIn", value)


def slot(
    key: str,
    routes: tuple[str, ...] = ("light-openai-41", "standard-openai-41"),
    *,
    tool_loop: bool = False,
    default: AiModelStepIn | None = None,
) -> AiModelSlotSpec:
    return AiModelSlotSpec(
        key=key, label=f"가상 칸 {key}", routes=routes, tool_loop=tool_loop, default=default or step(key, routes[0])
    )


def group(
    key: str, prompt_keys: tuple[str, ...] = ("a", "b"), model_slots: tuple[str, ...] = ("m1",)
) -> AiPromptGroupSpec:
    return AiPromptGroupSpec(key=key, label=f"가상 묶음 {key}", prompt_keys=prompt_keys, model_slots=model_slots)


SPEC = AiModuleSpec(
    module="fake-mod",
    models=(slot("m1"), slot("m2", ("standard-openai-41", "light-openai-41", "light-openai"))),
    groups=(group("g1", ("a", "b"), ("m1",)), group("g2", ("c",), ("m1", "m2"))),
)


def accepted_model(spec: AiModuleSpec = SPEC, config: LlmConfig = CONFIG) -> AcceptedModelSettings:
    return ai_settings.defaults(config, spec.models)


def entry(key: str, text: str | None = None) -> AiPromptEntry:
    body = text or f"가상 지시 {key}"
    return prompt_entry(
        key=key,
        label=f"가상 칸 {key}",
        prompt_id=f"fake-mod.{key}",
        prompt_version="fake-v1",
        text=body,
        memo="",
        default_text=body,
        output_section=None,
    )


def entries(spec: AiModuleSpec = SPEC) -> dict[str, list[AiPromptEntry]]:
    return {g.key: [entry(k) for k in g.prompt_keys] for g in spec.groups}


FIXED: list[AiFixedGroup] = [{"key": "k", "label": "가상 값", "items": [{"key": "n", "label": "가상 수", "value": 3}]}]


def built(spec: AiModuleSpec = SPEC, *, config: LlmConfig = CONFIG, **over: Any) -> Any:
    kwargs: dict[str, Any] = {
        "setting_name": "v2",
        "editable": {"prompts": True, "model": False},
        "model": accepted_model(spec),
        "prompts": entries(spec),
        "fixed": FIXED,
    }
    kwargs.update(over)
    return compose(config, spec, **kwargs)


# ── 3-2-1 모듈 선언 거절 여덟 ──


@pytest.mark.parametrize(
    ("spec", "said"),
    [
        pytest.param(dataclasses.replace(SPEC, module=" "), "이름이 비었다", id="module-empty"),
        pytest.param(dataclasses.replace(SPEC, models=()), "fake-mod", id="no-slot"),
        pytest.param(dataclasses.replace(SPEC, groups=()), "fake-mod", id="no-group"),
        pytest.param(dataclasses.replace(SPEC, models=(slot("m1"), slot("m1"))), "m1", id="slot-key-twice"),
        pytest.param(dataclasses.replace(SPEC, groups=(group("g1"), group("g1"))), "g1", id="group-key-twice"),
        pytest.param(dataclasses.replace(SPEC, groups=(group("g9", ()),)), "g9", id="group-without-prompt"),
        pytest.param(dataclasses.replace(SPEC, groups=(group("g9", ("a", "a")),)), "g9", id="prompt-key-twice"),
        pytest.param(dataclasses.replace(SPEC, groups=(group("g9", ("a",), ("m7",)),)), "m7", id="unknown-slot"),
    ],
)
def test_a_bad_module_is_a_config_error(spec: AiModuleSpec, said: str) -> None:
    with pytest.raises(LlmConfigError, match=said):
        check_module(spec)
    with pytest.raises(LlmConfigError, match=said):
        built(spec)


def test_a_good_module_passes_and_an_empty_model_slot_list_is_allowed() -> None:
    check_module(SPEC)
    check_module(dataclasses.replace(SPEC, groups=(group("g1", ("a",), ()),)))
    assert layout_of(SPEC) == (("g1", ("a", "b")), ("g2", ("c",)))


# ── 3-2-2 조합 ──


def test_compose_keeps_the_declared_order_and_values() -> None:
    model = accepted_model()
    body = built(model=model)
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    assert next(iter(body)) == "schemaVersion" and body["schemaVersion"] == "ai.prompt-model@3"
    assert [m["key"] for m in body["models"]] == ["m1", "m2"]
    assert [g["key"] for g in body["promptGroups"]] == ["g1", "g2"]
    assert [g["modelSlots"] for g in body["promptGroups"]] == [["m1"], ["m1", "m2"]]
    assert body["promptGroups"][0]["prompts"] == entries()["g1"]
    assert body["modelSettingsSha256"] == model_settings_sha256(model)
    assert body["limits"] == prompt_limits()
    assert body["editable"] == {"prompts": True, "model": False}
    assert body["fixed"] == FIXED
    assert (body["module"], body["settingName"]) == ("fake-mod", "v2")
    assert body["models"][1]["model"] == ai_settings.model_setting_view(CONFIG, model.steps[1])
    assert body["models"][1]["routeChoices"] == [
        route_choice(CONFIG, r, tool_loop=False) for r in ("standard-openai-41", "light-openai-41", "light-openai")
    ]
    assert [m["unavailableRoutes"] for m in body["models"]] == [[], []]


def test_compose_refuses_a_model_value_in_another_slot_order() -> None:
    swapped = AcceptedModelSettings(steps=tuple(reversed(accepted_model().steps)))
    with pytest.raises(LlmConfigError, match="칸 차례"):
        built(model=swapped)


@pytest.mark.parametrize(
    "prompts",
    [
        pytest.param({"g1": [entry("a"), entry("b")]}, id="missing-group"),
        pytest.param({**entries(), "g3": [entry("x")]}, id="extra-group"),
        pytest.param({**entries(), "g1": [entry("b"), entry("a")]}, id="prompt-order"),
        pytest.param({**entries(), "g1": [entry("a")]}, id="prompt-missing"),
    ],
)
def test_compose_refuses_prompts_off_the_declaration(prompts: dict[str, list[AiPromptEntry]]) -> None:
    with pytest.raises(LlmConfigError):
        built(prompts=prompts)


# ── 3-2-3 쓸 수 없는 경로(MARC-ISSUE-280) ──

THREE = slot("m1", ("light-openai-41", "standard-openai-41", "light-openai"))


def test_a_missing_route_is_named_not_a_server_error() -> None:
    spec = dataclasses.replace(SPEC, models=(THREE,), groups=(group("g1", ("a",), ("m1",)),))
    body = built(spec, config=MISSING, model=accepted_model(spec, MISSING))
    (got,) = body["models"]
    assert [c["route"] for c in got["routeChoices"]] == ["light-openai-41", "light-openai"]
    assert got["unavailableRoutes"] == ["standard-openai-41"]
    PROMPT_MODEL_V3.validate_python(body, strict=True)


def test_a_route_the_loop_refuses_is_named_too() -> None:
    loop = slot("m1", ("standard-openai-41", "light-openai-41"), tool_loop=True)
    spec = dataclasses.replace(SPEC, models=(loop,), groups=(group("g1", ("a",), ("m1",)),))
    (got,) = built(spec, model=accepted_model(spec))["models"]
    assert [c["route"] for c in got["routeChoices"]] == ["standard-openai-41"]
    assert got["unavailableRoutes"] == ["light-openai-41"]


def test_a_missing_chosen_route_stays_a_config_error() -> None:
    """고른 경로 자체가 빠지면 지금 그대로 LlmConfigError(기본 판 — 배포 잘못, 처분 Q4)."""
    spec = dataclasses.replace(
        SPEC,
        models=(slot("m1", ("standard-openai-41", "light-openai-41")),),
        groups=(group("g1", ("a",), ("m1",)),),
    )
    with pytest.raises(LlmConfigError):
        built(spec, config=MISSING, model=accepted_model(spec))


MIXED = dataclasses.replace(CONFIG, routes={**CONFIG.routes, "mixed-w": ("gpt-4.1", "gpt-4.1")})


@pytest.mark.parametrize("config", [CONFIG, MISSING, MIXED], ids=["real", "missing", "mixed"])
@pytest.mark.parametrize("tool_loop", [False, True])
def test_route_choices_split_like_unusable_routes(config: LlmConfig, tool_loop: bool) -> None:
    routes = (*sorted(CONFIG.routes), "mixed-w", "nowhere")
    the_slot = slot("m1", routes, tool_loop=tool_loop)
    choices, unavailable = route_choices(config, the_slot)
    assert unavailable == [route for _, route in unusable_routes(config, (the_slot,))]
    assert [c["route"] for c in choices] == [r for r in routes if r not in unavailable]
    assert choices == [route_choice(config, c["route"], tool_loop=tool_loop) for c in choices]
    assert unavailable  # 분모: 빠지는 것이 늘 있다(nowhere)


# ── 3-2-4 판 규칙 ──


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        ([], "v1"),
        (["v1", "v3", "x", "v0", "v01"], "v4"),
        (["v9"], "v10"),
        (["x", "v", "V2", "v2a"], "v1"),
        (["v07", "v00"], "v1"),
    ],
)
def test_the_next_version_name(names: list[str], expected: str) -> None:
    got = next_version_name(names)
    assert got == expected
    assert re.fullmatch(ai_setting_shapes.VERSION_NAME_PATTERN, got)
    assert len(got) <= ai_setting_shapes.VERSION_NAME_MAX_CHARS


def test_the_version_status_has_three_ways() -> None:
    at = datetime(2026, 10, 1, tzinfo=UTC)
    assert version_status(True, at) == "applied"
    assert version_status(True, None) == "applied"
    assert version_status(False, at) == "past"
    assert version_status(False, None) == "testing"


def test_ai_versions_carries_the_common_keys() -> None:
    model = accepted_model()
    texts = check_prompts(
        {"steps": [{"key": "g1", "prompts": [{"key": "a", "text": "가상 글", "memo": ""}]}]}, layout=(("g1", ("a",)),)
    )
    assert isinstance(texts, AcceptedPrompts)
    assert ai_versions(setting_id=None, model=model, prompts=None) == {
        "aiSettingId": None,
        "modelSettingsSha256": model_settings_sha256(model),
    }
    assert ai_versions(setting_id=7, model=model, prompts=texts) == {
        "aiSettingId": 7,
        "modelSettingsSha256": model_settings_sha256(model),
        "promptsSha256": prompts_sha256(texts),
    }
    assert ai_setting_shapes.AiVersionsCommon.__required_keys__ == {"aiSettingId", "modelSettingsSha256"}
    assert ai_setting_shapes.AiVersionsCommon.__optional_keys__ == {"promptsSha256"}


def test_the_version_limits_are_the_four() -> None:
    assert ai_setting_shapes.VERSION_NAME_MAX_CHARS == 16
    assert ai_setting_shapes.VERSION_TITLE_MAX_CHARS == 40
    assert ai_setting_shapes.VERSION_MEMO_MAX_CHARS == 200
    assert ai_setting_shapes.VERSION_NAME_PATTERN == r"^v[1-9][0-9]{0,14}$"


# ── 3-2-5 core 에 모듈 글자 0 ──


@pytest.mark.parametrize("module", [ai_settings, ai_setting_shapes], ids=["calc", "contracts"])
def test_core_spells_no_module_name(module: object) -> None:
    source = Path(cast("Any", module).__file__).read_text(encoding="utf-8")
    hits = [
        f"{node.lineno} {node.value[:40]!r}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and any(word in node.value for word in ("judge", "translate", "greenwash"))
    ]
    assert hits == []


# ── 3-5 옛 판 행 읽기(저장 정규형 → 새 이름 → sha = BASE) ──


def _load(name: str) -> Any:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def test_an_old_stored_row_reads_with_the_new_names() -> None:
    stored = _load("model-settings.json")
    (given,) = stored["steps"]
    the_slot = AiModelSlotSpec(
        key=given["key"], label="가상", routes=("light-openai-41", "standard-openai-41"), tool_loop=False, default=given
    )
    model = check_model_settings(CONFIG, stored, steps=(the_slot,))
    assert isinstance(model, AcceptedModelSettings)
    assert to_input(model) == stored
    assert model_settings_sha256(model) == BASE_EXAMPLE_MODEL_SHA

    texts = _load("prompts.json")
    spec = AiModuleSpec(
        module="fake-mod",
        models=(the_slot,),
        groups=tuple(
            AiPromptGroupSpec(s["key"], "가상", tuple(p["key"] for p in s["prompts"]), (the_slot.key,))
            for s in texts["steps"]
        ),
    )
    check_module(spec)
    accepted = check_prompts(texts, layout=layout_of(spec))
    assert isinstance(accepted, AcceptedPrompts)
    assert prompts_input(accepted) == texts
    assert prompts_sha256(accepted) == BASE_EXAMPLE_PROMPTS_SHA


def test_the_old_default_reads_with_the_new_names() -> None:
    """지금 쓰는 모듈 하나의 기본 판 값(모듈 코드의 값을 글자로 옮김 — core 는 모듈을 import 하지 않는다)."""
    default = step("judge", temperature=0.0, maxOutputTokens=1300)
    the_slot = AiModelSlotSpec("judge", "판정", ("light-openai-41", "standard-openai-41"), False, default)
    model = ai_settings.defaults(CONFIG, (the_slot,))
    assert to_input(model) == {"steps": [default]}
    assert model_settings_sha256(model) == BASE_DEFAULT_MODEL_SHA


def test_the_old_name_is_an_alias() -> None:
    assert AiStepSpec is AiModelSlotSpec


def test_the_prompt_sha_is_the_text() -> None:
    assert entry("a")["sha256"] == sha256_text("가상 지시 a")


@pytest.mark.parametrize(
    ("chosen", "narrow"),
    [
        pytest.param("standard-openai-41", slot("m1", ("light-openai-41",)), id="chosen-route-outside-the-slot"),
        pytest.param(
            "light-openai-41",
            slot("m1", ("standard-openai-41", "light-openai-41"), tool_loop=True),
            id="chosen-route-off-the-loop",
        ),
    ],
)
def test_a_chosen_route_the_slot_cannot_offer_is_a_config_error(chosen: str, narrow: AiModelSlotSpec) -> None:
    """검증 ① R1: 고른 경로가 칸이 지금 내놓는 routeChoices 에 없으면(명세가 좁아짐·고리 칸이 됨) LlmConfigError —
    routeChoices ≥1 과 「고른 경로 ∈ routeChoices」를 compose 가 보장한다(설정의 경로 자체는 있음)."""
    wide = dataclasses.replace(SPEC, models=(slot("m1"),), groups=(group("g1", ("a",), ("m1",)),))
    given = check_model_settings(CONFIG, {"steps": [step("m1", chosen)]}, steps=wide.models)
    assert isinstance(given, AcceptedModelSettings)
    assert built(wide, model=given)["models"][0]["model"]["route"] == chosen  # 분모: 넓은 칸은 지난다
    with pytest.raises(LlmConfigError, match="고른 경로"):
        compose(
            CONFIG,
            dataclasses.replace(wide, models=(narrow,)),
            setting_name="v2",
            editable={"prompts": True, "model": True},
            model=given,
            prompts={"g1": [entry("a")]},
            fixed=[],
        )
