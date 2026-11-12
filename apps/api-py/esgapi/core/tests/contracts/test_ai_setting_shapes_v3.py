# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""ai.prompt-model@3 꼴(contracts/ai_setting_shapes.py — 밴드 AP1a, 결정 MARC-ENT-399). 순수 층.

    @3 고정 스키마가 바이트까지 같고 옛 꼴 셋(@2·model-settings@1·prompts@1)의 고정 파일과 다시 뽑은 스키마가 BASE
    (4e28a54)와 바이트까지 같으며, 예시 셋이 strict 로 지나고 그 sha·경로 능력이 실제 설정으로 다시 셈한 값이고,
    모르는 칸·빈 목록·@2 섞임은 거절되며, 겹치는 구성요소(Ai*)의 정의가 @2 와 값까지 같다(웹 타입 이름이 그대로 산다).

예시의 글은 지어낸 것이다.
"""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from esgapi.core.calc import ai_settings
from esgapi.core.contracts import ai_setting_shapes
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.log import sha256_text

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "ai-setting"
EXAMPLES = DATA / "ai-setting-examples"
V3 = ai_setting_shapes.PROMPT_MODEL_V3_SHAPE
V3_EXAMPLES = ("prompt-model3-default.json", "prompt-model3-saved.json", "prompt-model3-fake-module.json")

# BASE(4e28a54) 의 고정 파일 sha256(git show 4e28a54:<경로> | shasum -a 256).
BASE_PINNED = {
    "ai.prompt-model@2": "97c7effb168803e8ae54be0d594a0949add3889ad014b939b34b28c7df9c1434",
    "ai.model-settings@1": "132e82bb8cb3b312d1e4d738d27215d6eadecd6a18c927ea864407b0f45a101c",
    "ai.prompts@1": "b77b4dc153ac051b46705987634f55acdff77681627428a2643edead09549353",
}


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def schema_text(shape: str) -> str:
    return json.dumps(ai_setting_shapes.SHAPES[shape].json_schema(), ensure_ascii=False, indent=2) + "\n"


# ── 3-1-1 고정 파일 ──


def test_the_v3_schema_is_pinned_byte_for_byte() -> None:
    text = schema_text(V3)
    assert (PINNED / f"{V3}.schema.json").read_bytes() == text.encode("utf-8")
    schema = json.loads(text)
    assert schema["additionalProperties"] is False
    objects = [d for d in schema["$defs"].values() if d.get("type") == "object"]
    assert objects and all(d.get("additionalProperties") is False for d in objects)


@pytest.mark.parametrize("shape", sorted(BASE_PINNED))
def test_the_old_shapes_are_the_base_bytes(shape: str) -> None:
    pinned = (PINNED / f"{shape}.schema.json").read_bytes()
    assert hashlib.sha256(pinned).hexdigest() == BASE_PINNED[shape]
    assert hashlib.sha256(schema_text(shape).encode("utf-8")).hexdigest() == BASE_PINNED[shape]


# ── 3-1-2 예시 ──


@pytest.mark.parametrize("name", V3_EXAMPLES)
def test_a_v3_example_fits_and_starts_with_its_id(name: str) -> None:
    body = load(name)
    ai_setting_shapes.PROMPT_MODEL_V3.validate_python(body, strict=True)
    assert next(iter(body)) == "schemaVersion" and body["schemaVersion"] == V3
    schema = ai_setting_shapes.PROMPT_MODEL_V3.json_schema()
    assert schema["required"][0] == "schemaVersion"
    assert schema["properties"]["schemaVersion"]["const"] == V3


@pytest.mark.parametrize("name", V3_EXAMPLES)
def test_a_v3_example_carries_real_shas_and_choices(name: str) -> None:
    """예시의 sha·경로 능력은 실제 설정(synthetic=False)으로 다시 셈한 값이다(웹이 예시를 믿고 짓는다)."""
    config = load_config(default_config_sources(synthetic=False))
    body = load(name)
    specs: list[ai_settings.AiModelSlotSpec] = []
    given: Any = {"steps": []}
    for slot in body["models"]:
        model = slot["model"]
        value: Any = {"key": slot["key"], **{k: model[k] for k in model if k != "models"}}
        given["steps"].append(value)
        routes = (*(c["route"] for c in slot["routeChoices"]), *slot["unavailableRoutes"])
        specs.append(ai_settings.AiModelSlotSpec(slot["key"], slot["label"], routes, False, value))
    accepted = ai_settings.check_model_settings(config, given, steps=specs)
    assert isinstance(accepted, ai_settings.AcceptedModelSettings)
    assert body["modelSettingsSha256"] == ai_settings.model_settings_sha256(accepted)
    for slot, spec, got in zip(body["models"], specs, accepted.steps, strict=True):
        assert slot["model"] == ai_settings.model_setting_view(config, got)
        choices, unavailable = ai_settings.route_choices(config, spec)
        assert (slot["routeChoices"], slot["unavailableRoutes"]) == (choices, unavailable)
    assert body["limits"] == ai_settings.prompt_limits()
    for group in body["promptGroups"]:
        assert all(p["sha256"] == sha256_text(p["text"]) for p in group["prompts"])
        assert set(group["modelSlots"]) <= {slot["key"] for slot in body["models"]}


@pytest.mark.parametrize("name", ["prompt-model-default.json", "prompt-model-saved.json"])
def test_the_v3_example_moves_the_v2_values(name: str) -> None:
    """그린워싱 모양 예시 둘은 @2 예시의 값을 옮긴 것이다(칸 하나·묶음 하나)."""
    old = load(name)
    new = load(name.replace("prompt-model-", "prompt-model3-"))
    (step,) = old["steps"]
    for key in ("module", "settingName", "editable", "modelSettingsSha256", "limits", "fixed"):
        assert new[key] == old[key]
    assert new["models"] == [
        {
            "key": step["key"],
            "label": step["label"],
            "model": step["model"],
            "routeChoices": step["routeChoices"],
            "unavailableRoutes": [],
        }
    ]
    assert new["promptGroups"] == [
        {"key": step["key"], "label": step["label"], "modelSlots": [step["key"]], "prompts": step["prompts"]}
    ]


# ── 3-1-3 거절 ──


def _broken(path: tuple[str | int, ...], value: object) -> dict[str, Any]:
    body = copy.deepcopy(load("prompt-model3-default.json"))
    target: Any = body
    for key in path[:-1]:
        target = target[key]
    if value is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return body


@pytest.mark.parametrize(
    ("path", "value"),
    [
        pytest.param(("extra",), 1, id="response-unknown-key"),
        pytest.param(("models", 0, "extra"), 1, id="slot-unknown-key"),
        pytest.param(("promptGroups", 0, "extra"), 1, id="group-unknown-key"),
        pytest.param(("models",), [], id="models-empty"),
        pytest.param(("promptGroups",), [], id="groups-empty"),
        pytest.param(("models", 0, "routeChoices"), [], id="route-choices-empty"),
        pytest.param(("promptGroups", 0, "prompts"), [], id="group-prompts-empty"),
        pytest.param(("promptGroups", 0, "modelSlots"), [1], id="model-slots-number"),
        pytest.param(("promptGroups", 0, "modelSlots"), "judge", id="model-slots-text"),
        pytest.param(("models", 0, "unavailableRoutes"), KeyError, id="slot-without-unavailable"),
        pytest.param(("models", 0, "unavailableRoutes"), [None], id="unavailable-null"),
        pytest.param(("promptGroups", 0, "modelSlots"), KeyError, id="group-without-model-slots"),
        pytest.param(("steps",), [], id="v2-steps-mixed-in"),
        pytest.param(("schemaVersion",), "ai.prompt-model@2", id="v2-shape-id"),
        pytest.param(("models",), KeyError, id="without-models"),
    ],
)
def test_a_broken_v3_body_is_refused(path: tuple[str | int, ...], value: object) -> None:
    with pytest.raises(ValidationError):
        ai_setting_shapes.PROMPT_MODEL_V3.validate_python(_broken(path, value), strict=True)


def test_an_empty_model_slot_list_and_no_unavailable_route_pass() -> None:
    body = _broken(("promptGroups", 0, "modelSlots"), [])
    ai_setting_shapes.PROMPT_MODEL_V3.validate_python(body, strict=True)


def test_a_v2_body_is_not_a_v3_body() -> None:
    with pytest.raises(ValidationError):
        ai_setting_shapes.PROMPT_MODEL_V3.validate_python(load("prompt-model-default.json"), strict=True)


# ── 3-1-4 구성요소 ──


def test_the_shared_components_are_the_v2_ones() -> None:
    old = ai_setting_shapes.PROMPT_MODEL.json_schema()["$defs"]
    new = ai_setting_shapes.PROMPT_MODEL_V3.json_schema()["$defs"]
    assert set(new) == (set(old) - {"AiPromptStep"}) | {"AiModelSlot", "AiPromptGroup"}
    shared = set(old) & set(new)
    assert shared >= {
        "AiModelSetting",
        "AiRouteChoice",
        "AiPromptEntry",
        "AiFixedGroup",
        "AiPromptLimits",
        "AiPromptModelEditable",
    }
    assert {name: new[name] for name in shared} == {name: old[name] for name in shared}


def test_the_doc_names_the_parts_and_the_fixed_sha() -> None:
    doc = ai_setting_shapes.__doc__ or ""
    assert "sha 앞바이트 불변" in doc
    assert "입력 @1 의 steps = 칸 목록" in doc
    assert "routeChoices ≥1 은 compose 가 보장한다" in doc
    assert "AP1b·AP1c 가 걷는다" in doc
