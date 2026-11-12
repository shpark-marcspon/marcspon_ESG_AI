# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""모듈 공통 AI 설정 꼴 둘(contracts/ai_setting_shapes.py — 밴드 AS1). 순수 층.

    고정 스키마 둘이 바이트까지 같고, 예시 셋이 strict 로 지나며 그 sha·능력이 실제 설정으로 다시 셈한 값과 같고,
    모르는 칸·틀린 값은 거절되며, 꼴 문서가 「모델 설정만 바꿔도 새 판」을 말한다.

예시의 프롬프트 글은 지은 것이다.
"""

import copy
import json
from pathlib import Path
from typing import Any, cast, is_typeddict

import pytest
from pydantic import ValidationError

from esgapi.core.calc import ai_settings
from esgapi.core.contracts import ai_setting_shapes
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.log import sha256_text
from esgapi.core.schemas import StrictIn

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "ai-setting"
EXAMPLES = DATA / "ai-setting-examples"
EXAMPLE_SHAPES = {
    "prompt-model-default.json": ai_setting_shapes.PROMPT_MODEL_SHAPE,
    "prompt-model-saved.json": ai_setting_shapes.PROMPT_MODEL_SHAPE,
    "model-settings.json": ai_setting_shapes.MODEL_SETTINGS_SHAPE,
    "prompts.json": ai_setting_shapes.PROMPTS_SHAPE,
    "prompt-model3-default.json": ai_setting_shapes.PROMPT_MODEL_V3_SHAPE,
    "prompt-model3-saved.json": ai_setting_shapes.PROMPT_MODEL_V3_SHAPE,
    "prompt-model3-fake-module.json": ai_setting_shapes.PROMPT_MODEL_V3_SHAPE,
}


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


@pytest.mark.parametrize("shape", sorted(ai_setting_shapes.SHAPES))
def test_the_json_schema_is_pinned_byte_for_byte(shape: str) -> None:
    pinned = PINNED / f"{shape}.schema.json"
    text = json.dumps(ai_setting_shapes.SHAPES[shape].json_schema(), ensure_ascii=False, indent=2) + "\n"
    assert pinned.read_bytes() == text.encode("utf-8")
    schema = json.loads(text)
    assert schema["additionalProperties"] is False
    assert all(d.get("additionalProperties") is False for d in schema["$defs"].values() if d.get("type") == "object")


def test_the_pinned_files_are_the_three() -> None:
    assert sorted(p.name for p in PINNED.iterdir()) == sorted(f"{s}.schema.json" for s in ai_setting_shapes.SHAPES)


def test_the_examples_are_the_seven() -> None:
    assert sorted(p.name for p in EXAMPLES.iterdir()) == sorted(EXAMPLE_SHAPES)


@pytest.mark.parametrize("name", sorted(EXAMPLE_SHAPES))
def test_an_example_fits_its_shape(name: str) -> None:
    ai_setting_shapes.SHAPES[EXAMPLE_SHAPES[name]].validate_python(load(name), strict=True)


def test_the_response_starts_with_its_shape_id() -> None:
    schema = ai_setting_shapes.SHAPES[ai_setting_shapes.PROMPT_MODEL_SHAPE].json_schema()
    assert schema["required"][0] == "schemaVersion"
    assert schema["properties"]["schemaVersion"]["const"] == ai_setting_shapes.PROMPT_MODEL_SHAPE


def test_the_examples_carry_real_shas_and_choices() -> None:
    """예시의 sha·경로 능력은 실제 설정(synthetic=False)으로 다시 셈한 값이다(웹이 예시를 믿고 짓는다)."""
    config = load_config(default_config_sources(synthetic=False))
    for name in ("prompt-model-default.json", "prompt-model-saved.json"):
        body = load(name)
        (step,) = body["steps"]
        model = step["model"]
        given: Any = {"steps": [{"key": step["key"], **{k: model[k] for k in model if k != "models"}}]}
        spec = ai_settings.AiStepSpec(
            key=step["key"],
            label=step["label"],
            routes=tuple(c["route"] for c in step["routeChoices"]),
            tool_loop=False,
            default=given["steps"][0],
        )
        accepted = ai_settings.check_model_settings(config, given, steps=[spec])
        assert isinstance(accepted, ai_settings.AcceptedModelSettings)
        assert body["modelSettingsSha256"] == ai_settings.model_settings_sha256(accepted)
        assert model == ai_settings.model_setting_view(config, accepted.steps[0])
        assert step["routeChoices"] == [ai_settings.route_choice(config, r, tool_loop=False) for r in spec.routes]
        assert all(p["sha256"] == sha256_text(p["text"]) for p in step["prompts"])
    saved_input = load("model-settings.json")
    saved = load("prompt-model-saved.json")["steps"][0]["model"]
    assert saved_input["steps"][0] == {"key": "judge", **{k: saved[k] for k in saved if k != "models"}}


def _broken(name: str, path: tuple[str | int, ...], value: object) -> dict[str, Any]:
    body = copy.deepcopy(load(name))
    target: Any = body
    for key in path[:-1]:
        target = target[key]
    if value is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return body


M = ("steps", 0, "model")


@pytest.mark.parametrize(
    ("name", "path", "value"),
    [
        pytest.param("prompt-model-default.json", ("extra",), 1, id="response-unknown-key"),
        pytest.param("prompt-model-default.json", (*M, "extra"), 1, id="model-unknown-key"),
        pytest.param("prompt-model-default.json", ("steps", 0, "prompts", 0, "extra"), 1, id="prompt-unknown-key"),
        pytest.param("prompt-model-default.json", (*M, "temperature"), True, id="temperature-bool"),
        pytest.param("prompt-model-default.json", (*M, "temperature"), 2.5, id="temperature-above"),
        pytest.param("prompt-model-default.json", ("steps",), [], id="steps-empty"),
        pytest.param("prompt-model-default.json", (*M, "models"), [], id="models-empty"),
        pytest.param("prompt-model-default.json", ("steps", 0, "routeChoices"), [], id="route-choices-empty"),
        pytest.param("prompt-model-default.json", ("steps", 0, "prompts"), [], id="prompts-empty"),
        pytest.param("prompt-model-default.json", (*M, "maxOutputTokens"), "1", id="max-output-text"),
        pytest.param("prompt-model-default.json", (*M, "maxOutputTokens"), 0, id="max-output-zero"),
        pytest.param("prompt-model-default.json", ("modelSettingsSha256",), "abc", id="sha-short"),
        pytest.param("prompt-model-default.json", ("editable", "model"), KeyError, id="editable-without-model"),
        pytest.param("prompt-model-default.json", ("schemaVersion",), "ai.model-settings@1", id="shape-id"),
        pytest.param("model-settings.json", ("steps", 0, "extra"), 1, id="input-unknown-key"),
        pytest.param("model-settings.json", ("schemaVersion",), "ai.model-settings@1", id="input-shape-id"),
        pytest.param("model-settings.json", ("steps", 0, "temperature"), True, id="input-temperature-bool"),
        pytest.param("model-settings.json", ("steps", 0, "maxOutputTokens"), "1", id="input-max-output-text"),
        pytest.param("model-settings.json", ("steps", 0, "maxOutputTokens"), True, id="input-max-output-bool"),
        pytest.param("model-settings.json", ("steps", 0, "webSearch"), 0, id="input-web-search-int"),
        pytest.param("model-settings.json", ("steps", 0, "route"), KeyError, id="input-without-route"),
        pytest.param("model-settings.json", ("steps", 0, "temperature"), KeyError, id="input-without-temperature"),
    ],
)
def test_a_broken_body_is_refused(name: str, path: tuple[str | int, ...], value: object) -> None:
    with pytest.raises(ValidationError):
        ai_setting_shapes.SHAPES[EXAMPLE_SHAPES[name]].validate_python(_broken(name, path, value), strict=True)


@pytest.mark.parametrize(
    "raw", ['{"steps":[{"key":"a","route":"r","temperature":0,"webSearch":false,"maxOutputTokens":1}]}']
)
def test_an_integer_temperature_is_a_number(raw: str) -> None:
    """JSON 정수 0 은 strict float 을 지난다(받기가 0.0 으로 정규화한다)."""
    body = ai_setting_shapes.MODEL_SETTINGS.validate_json(raw, strict=True)
    assert body["steps"][0]["temperature"] == 0


def test_the_shape_doc_says_a_model_change_is_a_new_version() -> None:
    """c3 요청(10-20): 판 불변 규칙과의 관계를 꼴 문서에 적는다."""
    doc = ai_setting_shapes.__doc__ or ""
    assert "모델 설정만 바꿔도 새 판이다" in doc
    assert "기존 판에 모델 설정을 붙이지 않는다" in doc
    assert "synthetic=False" in doc


def test_the_class_names_start_with_ai_and_are_new() -> None:
    found = {n for n, v in vars(ai_setting_shapes).items() if isinstance(v, type) and is_typeddict(v)}
    assert found and all(n.startswith("Ai") for n in found), found
    openapi = json.loads(
        (Path(__file__).resolve().parents[4] / "generated" / "openapi.json").read_text(encoding="utf-8")
    )
    # AS2a 부터 core 꼴이 openapi 에 실림 — Ai* 이름은 core 꼴만
    assert {n for n in openapi["components"]["schemas"] if n.startswith("Ai")} <= found


def test_a_strict_body_keeps_the_input_shapes_strict() -> None:
    """AS2b(Q-B5 (가)): 본문 꼴(StrictIn) 안에 실린 AiModelSettingsIn 도 strict — 바깥 strict 가 중첩 TypedDict 로
    내려가지 않아 꼴 스스로 STRICT_FORBID 를 단다. 정수 0 은 실수 0.0 으로 지난다."""

    class Body(StrictIn):
        modelSettings: ai_setting_shapes.AiModelSettingsIn

    step = {"key": "judge", "route": "r", "temperature": 0, "webSearch": False, "maxOutputTokens": 5}
    accepted = Body.model_validate({"modelSettings": {"steps": [step]}})
    temperature = accepted.modelSettings["steps"][0]["temperature"]
    assert temperature == 0.0 and type(temperature) is float
    for key, value in (("maxOutputTokens", True), ("maxOutputTokens", "5"), ("temperature", True), ("webSearch", 0)):
        with pytest.raises(ValidationError):
            Body.model_validate({"modelSettings": {"steps": [{**step, key: value}]}})


# ── AS3a-1: ai.prompt-model@2 · ai.prompts@1 ──


def test_the_shape_ids_are_the_new_ones() -> None:
    assert ai_setting_shapes.PROMPT_MODEL_SHAPE == "ai.prompt-model@2"
    assert ai_setting_shapes.PROMPTS_SHAPE == "ai.prompts@1"
    assert sorted(ai_setting_shapes.SHAPES) == [
        "ai.model-settings@1",
        "ai.prompt-model@2",
        "ai.prompt-model@3",
        "ai.prompts@1",
    ]


def test_the_examples_carry_real_marks_and_limits() -> None:
    """예시의 isDefault·outputKept 는 prompt_entry 규칙대로, limits 는 core 상수(웹이 예시를 믿고 짓는다)."""
    kept: list[bool] = []
    for name in ("prompt-model-default.json", "prompt-model-saved.json"):
        body = load(name)
        assert body["limits"] == ai_settings.prompt_limits()
        for entry in body["steps"][0]["prompts"]:
            assert entry["isDefault"] is (entry["text"] == entry["defaultText"])
            section = entry["outputSection"]
            assert section is None or entry["defaultText"].endswith(section)
            assert entry["outputKept"] is (section is None or section in entry["text"])
            kept.append(entry["outputKept"])
    assert True in kept and False in kept  # 분모: 예시가 둘 다 보인다
    assert load("prompt-model-default.json")["fixed"] and load("prompt-model-saved.json")["fixed"] == []
    given = load("prompts.json")
    saved = load("prompt-model-saved.json")["steps"][0]["prompts"]
    assert [[p["key"], p["text"], p["memo"]] for p in given["steps"][0]["prompts"]] == [
        [p["key"], p["text"], p["memo"]] for p in saved
    ]


P = ("steps", 0, "prompts", 0)
F = ("fixed", 1, "items", 0)


@pytest.mark.parametrize(
    ("name", "path", "value"),
    [
        pytest.param("prompt-model-default.json", ("limits",), KeyError, id="response-without-limits"),
        pytest.param("prompt-model-default.json", ("fixed",), KeyError, id="response-without-fixed"),
        pytest.param("prompt-model-default.json", ("limits", "extra"), 1, id="limits-unknown-key"),
        pytest.param("prompt-model-default.json", ("limits", "textMax"), "8000", id="limits-text"),
        pytest.param("prompt-model-default.json", (*P, "memo"), KeyError, id="entry-without-memo"),
        pytest.param("prompt-model-default.json", (*P, "defaultText"), KeyError, id="entry-without-default"),
        pytest.param("prompt-model-default.json", (*P, "isDefault"), "true", id="entry-is-default-text"),
        pytest.param("prompt-model-default.json", (*P, "outputSection"), 1, id="entry-section-number"),
        pytest.param("prompt-model-default.json", (*P, "outputKept"), KeyError, id="entry-without-kept"),
        pytest.param("prompt-model-default.json", (*F, "value"), {"a": 1}, id="fixed-value-dict"),
        pytest.param("prompt-model-default.json", (*F, "value"), [1], id="fixed-value-int-list"),
        pytest.param("prompt-model-default.json", (*F, "extra"), 1, id="fixed-item-unknown-key"),
        pytest.param("prompt-model-default.json", ("fixed", 0, "items"), KeyError, id="fixed-group-without-items"),
        pytest.param("prompt-model-default.json", ("schemaVersion",), "ai.prompt-model@1", id="old-shape-id"),
        pytest.param("prompts.json", ("steps", 0, "prompts", 0, "text"), 1, id="input-text-number"),
        pytest.param("prompts.json", ("steps", 0, "prompts", 0, "memo"), True, id="input-memo-bool"),
        pytest.param("prompts.json", ("steps", 0, "prompts", 0, "memo"), None, id="input-memo-null"),
        pytest.param("prompts.json", ("steps", 0, "prompts", 0, "extra"), 1, id="input-prompt-unknown-key"),
        pytest.param("prompts.json", ("steps", 0, "prompts", 0, "memo"), KeyError, id="input-without-memo"),
        pytest.param("prompts.json", ("steps", 0, "prompts", 0, "text"), KeyError, id="input-without-text"),
        pytest.param("prompts.json", ("steps", 0, "prompts"), KeyError, id="input-step-without-prompts"),
        pytest.param("prompts.json", ("steps", 0, "key"), KeyError, id="input-step-without-key"),
        pytest.param("prompts.json", ("steps",), KeyError, id="input-without-steps"),
        pytest.param("prompts.json", ("schemaVersion",), "ai.prompts@1", id="input-shape-id"),
    ],
)
def test_a_broken_prompt_body_is_refused(name: str, path: tuple[str | int, ...], value: object) -> None:
    with pytest.raises(ValidationError):
        ai_setting_shapes.SHAPES[EXAMPLE_SHAPES[name]].validate_python(_broken(name, path, value), strict=True)


@pytest.mark.parametrize("value", [3, "빠름", ["가", "나"], [], None])
def test_a_fixed_value_takes_its_four_forms(value: object) -> None:
    body = _broken("prompt-model-default.json", (*F, "value"), value)
    ai_setting_shapes.PROMPT_MODEL.validate_python(body, strict=True)


def test_a_strict_body_keeps_the_prompts_input_strict() -> None:
    """본문 꼴(StrictIn) 안에 실린 AiPromptsIn 도 strict — 꼴 스스로 STRICT_FORBID 를 단다(AS2b 와 같은 까닭)."""

    class Body(StrictIn):
        prompts: ai_setting_shapes.AiPromptsIn | None

    prompt = {"key": "detect", "text": "지어낸 글", "memo": ""}
    accepted = Body.model_validate({"prompts": {"steps": [{"key": "judge", "prompts": [prompt]}]}})
    assert accepted.prompts is not None and accepted.prompts["steps"][0]["prompts"][0] == prompt
    assert Body.model_validate({"prompts": None}).prompts is None  # null = 코드 글
    for key, value in (("text", 1), ("memo", True), ("memo", None), ("extra", "x")):
        with pytest.raises(ValidationError):
            Body.model_validate({"prompts": {"steps": [{"key": "judge", "prompts": [{**prompt, key: value}]}]}})


def test_the_shape_doc_says_a_prompt_change_is_a_new_version() -> None:
    doc = ai_setting_shapes.__doc__ or ""
    assert "한 번 저장 = 판 하나" in doc
    assert "글·메모만 바꿔도 새 판이다" in doc
    assert "prompts 의 null 은 뜻이 있다" in doc
    assert "서버는 접지 않는다" in doc
    assert "저장을 막지 않는다" in doc
