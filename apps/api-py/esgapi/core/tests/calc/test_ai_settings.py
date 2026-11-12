"""모듈 공통 AI 설정의 순수 규칙(core/calc/ai_settings.py — 밴드 AS1). 순수 층.

실제 설정(synthetic=False)의 경로 여덟 능력, 시험이 지은 섞인 경로, 받기 차례 아홉과 그 순서(밴드 CO1 이 2a·2b·5a),
호출 층과 같은 판정(client 대조: temperature·web_search·도구 고리·출력 상한), 받은 값의 sha, 판정 상수를 import
하는지(AST), 명세의 못 쓰는 경로(`unusable_routes`)·key 중복·응답 칸의 같음.
"""

import ast
import dataclasses
import math
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.calc import ai_settings
from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AiStepSpec,
    ModelSettingRefused,
    check_model_settings,
    defaults,
    model_setting_view,
    model_settings_sha256,
    route_choice,
    to_input,
    unusable_routes,
)
from esgapi.core.contracts.ai_setting_shapes import AiModelStepIn
from esgapi.core.llm import client
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config, resolve_route
from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.log import sha256_json
from esgapi.core.llm.prompts import FilePromptStore, RenderedPrompt
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import FunctionTool, Tags, WebSearchTool

SOURCE = Path(ai_settings.__file__)
CONFIG = load_config(default_config_sources(synthetic=False))
MIXED = dataclasses.replace(
    CONFIG, routes={**CONFIG.routes, "mixed-t": ("gpt-4.1-mini", "gpt-6-luna"), "mixed-w": ("gpt-4.1", "gpt-4.1")}
)

# §0-1 의 표: 경로 → (모델 키 차례, T, W(tool_loop), 상한)
CAPABILITIES = {
    "light": (["claude-haiku-4-5", "gpt-6-luna"], False, False, 64000),
    "light-openai": (["gpt-6-luna"], False, False, 128000),
    "light-anthropic": (["claude-haiku-4-5"], False, False, 64000),
    "light-gemini": (["gemini-3.1-flash-lite"], True, False, 65536),
    "light-gemini-35": (["gemini-3.5-flash-lite"], True, False, 65536),
    "standard": (["claude-sonnet-4-6", "gpt-6.1-sol"], False, False, 128000),
    "light-openai-41": (["gpt-4.1-mini"], True, False, 32768),
    "standard-openai-41": (["gpt-4.1"], True, True, 32768),
    "standard-openai-4o": (["gpt-4o"], True, True, 16384),
}


def step(key: str = "judge", route: str = "light-openai-41", **over: Any) -> AiModelStepIn:
    value: dict[str, Any] = {
        "key": key,
        "route": route,
        "temperature": 0.0,
        "webSearch": False,
        "maxOutputTokens": 1300,
    }
    value.update(over)
    return value  # pyright: ignore[reportReturnType]


def spec(
    key: str = "judge",
    routes: tuple[str, ...] = tuple(CAPABILITIES),
    *,
    tool_loop: bool = False,
    web_search: bool = False,
) -> AiStepSpec:
    """기본은 도구 고리 밖 단계(CO1: 고리 단계는 고리를 못 지나는 경로를 거절해 기본 경로가 빨개진다 — LOOP 를 쓴다)."""
    default = step(key, route=routes[0] if tool_loop else "light-openai-41", webSearch=web_search)
    return AiStepSpec(key=key, label=key, routes=routes, tool_loop=tool_loop, default=default)


# 도구 고리 단계: 고리를 지나는 경로 하나, 웹 검색이 기본으로 켜짐.
LOOP = spec(routes=("standard-openai-41",), tool_loop=True, web_search=True)
LOOP_STEP = step(route="standard-openai-41", webSearch=True)


def check(*steps: AiModelStepIn, specs: tuple[AiStepSpec, ...] = (spec(),), config: LlmConfig = CONFIG) -> object:
    return check_model_settings(config, {"steps": list(steps)}, steps=specs)


def code(result: object) -> str:
    return result.code if isinstance(result, ModelSettingRefused) else "accepted"


def accepted(
    *steps: AiModelStepIn, specs: tuple[AiStepSpec, ...] = (spec(),), config: LlmConfig = CONFIG
) -> AcceptedModelSettings:
    result = check(*steps, specs=specs, config=config)
    assert isinstance(result, AcceptedModelSettings), result
    return result


# ── 능력(3-3-2·3-3-3) ──


def test_the_real_routes_are_the_nine() -> None:
    assert set(CONFIG.routes) == set(CAPABILITIES)


@pytest.mark.parametrize("route", sorted(CAPABILITIES))
def test_a_real_route_has_its_capabilities(route: str) -> None:
    keys, temperature, web, maximum = CAPABILITIES[route]
    choice = route_choice(CONFIG, route, tool_loop=True)
    assert [m["key"] for m in choice["models"]] == keys
    assert (choice["acceptsTemperature"], choice["webSearchAvailable"], choice["maxOutputTokensMax"]) == (
        temperature,
        web,
        maximum,
    )
    assert choice["models"][0]["label"] == CONFIG.models[keys[0]].entry.label
    assert not route_choice(CONFIG, route, tool_loop=False)["webSearchAvailable"]


def test_web_search_needs_the_tool_loop() -> None:
    assert route_choice(CONFIG, "standard-openai-41", tool_loop=True)["webSearchAvailable"]
    assert not route_choice(CONFIG, "standard-openai-41", tool_loop=False)["webSearchAvailable"]


def test_one_model_refusing_temperature_turns_the_mixed_route_off() -> None:
    choice = route_choice(MIXED, "mixed-t", tool_loop=True)
    assert not choice["acceptsTemperature"]
    assert choice["maxOutputTokensMax"] == min(32768, 128000)


def test_two_models_turn_web_search_off() -> None:
    choice = route_choice(MIXED, "mixed-w", tool_loop=True)
    assert not choice["webSearchAvailable"]
    assert choice["acceptsTemperature"]


def test_a_route_missing_from_the_config_is_a_config_error() -> None:
    with pytest.raises(LlmConfigError):
        route_choice(CONFIG, "no-such-route", tool_loop=False)


# ── 받기(3-3-4) ──


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        pytest.param(step(), "accepted", id="denominator"),
        pytest.param(step(route="gpt-4.1"), "ai_model_route_unknown", id="route-not-a-route"),
        pytest.param(step(temperature=2.5), "ai_model_temperature_range", id="temperature-above"),
        pytest.param(step(temperature=-0.1), "ai_model_temperature_range", id="temperature-below"),
        pytest.param(
            step(route="light-openai", temperature=0.5), "ai_model_temperature_unsupported", id="t-unsupported"
        ),
        pytest.param(step(webSearch=True), "ai_model_web_search_unsupported", id="web-search-unsupported"),
        pytest.param(step(maxOutputTokens=0), "ai_model_max_output_range", id="max-output-zero"),
        pytest.param(step(maxOutputTokens=32769), "ai_model_max_output_range", id="max-output-above"),
        pytest.param(step(maxOutputTokens=32768), "accepted", id="max-output-at-the-bound"),
        pytest.param(step(maxOutputTokens=1), "accepted", id="max-output-one"),
    ],
)
def test_a_rule_refuses_its_case(given: AiModelStepIn, expected: str) -> None:
    assert code(check(given)) == expected


def test_web_search_is_accepted_on_a_loop_step_at_its_default() -> None:
    """옮김(앞 판 매개 web-search-accepted): 웹 검색은 고리 단계의 기본값일 때 받는다. 끄면 고정(5a)."""
    assert code(check(LOOP_STEP, specs=(LOOP,))) == "accepted"
    assert code(check(step(route="standard-openai-41", webSearch=False), specs=(LOOP,))) == "ai_model_web_search_fixed"


def test_a_route_outside_the_step_is_refused_even_if_configured() -> None:
    result = check(step(), specs=(spec(routes=("standard-openai-41",)),))
    assert result == ModelSettingRefused("ai_model_route_unknown", "고를 수 없는 모델이에요", "judge")


def test_the_route_is_checked_before_the_temperature() -> None:
    """경로·temperature 둘 다 어기면 경로(2)가 먼저다."""
    assert code(check(step(route="nowhere", temperature=9.0))) == "ai_model_route_unknown"


def test_the_range_is_checked_before_the_support() -> None:
    assert code(check(step(route="light-openai", temperature=9.0))) == "ai_model_temperature_range"


def test_the_temperature_is_checked_before_web_search_and_output() -> None:
    assert code(check(step(route="light-openai", temperature=0.5, webSearch=True, maxOutputTokens=0))) == (
        "ai_model_temperature_unsupported"
    )
    assert code(check(step(webSearch=True, maxOutputTokens=0))) == "ai_model_web_search_unsupported"


@pytest.mark.parametrize(
    ("temperature", "expected"),
    [
        (2.0, "accepted"),
        (2.0000001, "ai_model_temperature_range"),
        (0, "accepted"),
        (0.0, "accepted"),
        (math.nan, "ai_model_temperature_range"),
        (math.inf, "ai_model_temperature_range"),
        (-math.inf, "ai_model_temperature_range"),
        (True, "ai_model_temperature_range"),
    ],
)
def test_the_temperature_bounds(temperature: object, expected: str) -> None:
    assert code(check(step(temperature=temperature))) == expected


def test_null_temperature_passes_where_temperature_is_refused() -> None:
    assert code(check(step(route="light-openai", temperature=None))) == "accepted"
    assert code(check(step(route="light-openai", temperature=0.0))) == "ai_model_temperature_unsupported"


def test_a_refusal_names_its_step() -> None:
    specs = (spec("detect"), spec("judge"))
    result = check(step("detect"), step("judge", temperature=3.0), specs=specs)
    assert isinstance(result, ModelSettingRefused)
    assert (result.code, result.step) == ("ai_model_temperature_range", "judge")


@pytest.mark.parametrize(
    "keys",
    [
        pytest.param(("detect",), id="missing"),
        pytest.param(("detect", "judge", "extra"), id="added"),
        pytest.param(("detect", "detect"), id="repeated"),
        pytest.param(("judge", "detect"), id="reordered"),
        pytest.param((), id="empty"),
    ],
)
def test_the_steps_are_fixed(keys: tuple[str, ...]) -> None:
    result = check(*(step(k) for k in keys), specs=(spec("detect"), spec("judge")))
    assert result == ModelSettingRefused("ai_model_steps_fixed", "단계 구성은 바꿀 수 없어요", None)


def test_the_steps_are_fixed_before_a_step_rule() -> None:
    assert code(check(step("detect", temperature=9.0), specs=(spec("detect"), spec("judge")))) == "ai_model_steps_fixed"


def test_the_accepted_value_resolves_the_models_and_normalizes() -> None:
    (got,) = accepted(step(route="light-openai", temperature=None, maxOutputTokens=100)).steps
    assert got == ai_settings.AcceptedStep("judge", "light-openai", ("gpt-6-luna",), None, False, 100)
    (zero,) = accepted(step(temperature=-0.0)).steps
    assert zero.temperature is not None and math.copysign(1.0, zero.temperature) == 1.0
    (whole,) = accepted(step(temperature=1)).steps
    assert type(whole.temperature) is float


def test_the_stored_input_round_trips() -> None:
    specs = (spec("detect"), spec("judge", routes=("standard-openai-41",), tool_loop=True, web_search=True))
    first = accepted(
        step("detect", temperature=0), step("judge", route="standard-openai-41", webSearch=True), specs=specs
    )
    stored = to_input(first)
    assert check_model_settings(CONFIG, stored, steps=specs) == first
    assert [sorted(s) for s in stored["steps"]] == [sorted(step())] * 2


def test_the_defaults_pass_the_same_check() -> None:
    assert defaults(CONFIG, (spec(),)) == accepted(step())


def test_a_default_the_config_refuses_is_a_config_error() -> None:
    bad = AiStepSpec(
        key="judge", label="판정", routes=("light-openai",), tool_loop=False, default=step(route="light-openai")
    )
    with pytest.raises(LlmConfigError):
        defaults(CONFIG, (bad,))


# ── client 대조(3-3-5) ──

ROUTES = (*sorted(CAPABILITIES), "mixed-t", "mixed-w")


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("temperature", [None, 0, 0.7, 2.0, 2.5, math.nan])
def test_the_temperature_rule_is_the_clients(route: str, temperature: float | None) -> None:
    ours = code(
        check(step(route=route, temperature=temperature, maxOutputTokens=1), specs=(spec(routes=ROUTES),), config=MIXED)
    )
    try:
        client._check_temperature(temperature, resolve_route(MIXED, route))  # pyright: ignore[reportPrivateUsage]
        theirs = False
    except LlmConfigError:
        theirs = True
    assert ours in ("accepted", "ai_model_temperature_range", "ai_model_temperature_unsupported")
    assert (ours != "accepted") == theirs


@pytest.mark.parametrize("route", ROUTES)
def test_the_web_search_rule_is_the_clients(route: str) -> None:
    ours = route_choice(MIXED, route, tool_loop=True)["webSearchAvailable"]
    try:
        client._check_tool_models(resolve_route(MIXED, route), [WebSearchTool()])  # pyright: ignore[reportPrivateUsage]
        theirs = True
    except LlmConfigError:
        theirs = False
    assert ours == theirs


def test_the_comparison_sees_both_answers() -> None:
    """분모: 대조가 참·거짓을 다 본다(한쪽만 보면 같음이 빈말이다)."""
    web = {route_choice(MIXED, r, tool_loop=True)["webSearchAvailable"] for r in ROUTES}
    temperature = {route_choice(MIXED, r, tool_loop=True)["acceptsTemperature"] for r in ROUTES}
    assert web == temperature == {True, False}


# ── 도구 고리·출력 상한의 client 대조(CO1 §3-1-2~4) ──

# 실제 경로 가운데 도구 고리를 지나는 것(★D: 모델 하나 · TOOL_PROVIDERS · openai 면 TOOL_MODELS).
LOOP_ROUTES = {"standard-openai-41", "standard-openai-4o"}
TOOL = FunctionTool(name="look_up", description="시험용 도구", parameters={"type": "object"})
# 공급사 어댑터 0 — `_build_provider_request` 는 공급사를 부르지 않는다.
LLM = client.LlmClient(config=MIXED, providers={}, prompts=FilePromptStore(SOURCE.parent), log=MemorySink())
RENDERED = RenderedPrompt(system=(), user="")


def loop_code(route: str, *, tool_loop: bool = True, config: LlmConfig = MIXED) -> str:
    return code(
        check(
            step(route=route, temperature=None, maxOutputTokens=1),
            specs=(spec(routes=ROUTES, tool_loop=tool_loop),),
            config=config,
        )
    )


def client_loops(route: str) -> bool:
    try:
        client._check_tool_models(resolve_route(MIXED, route), [TOOL])  # pyright: ignore[reportPrivateUsage]
    except LlmConfigError:
        return False
    return True


def client_takes_output(route: str, tokens: int) -> bool:
    """경로의 모델 전부에서 client 가 그 출력 상한의 요청을 짓는다(대체 모델은 시도할 때 본다 — 물을 거리 2)."""
    request = client.CallRequest[str](
        prompt="t/plain@1", route=route, tags=Tags(tenant="t", module="m"), max_output_tokens=tokens
    )
    try:
        for model in resolve_route(MIXED, route):
            LLM._build_provider_request(request, RENDERED, model, None)  # pyright: ignore[reportPrivateUsage]
    except LlmConfigError:
        return False
    return True


@pytest.mark.parametrize("route", sorted(CAPABILITIES))
def test_a_loop_step_refuses_a_route_the_loop_refuses(route: str) -> None:
    expected = "accepted" if route in LOOP_ROUTES else "ai_model_tool_loop_unsupported"
    assert loop_code(route, config=CONFIG) == expected
    assert loop_code(route, tool_loop=False, config=CONFIG) == "accepted"  # 분모: 고리 밖 단계는 받는다


@pytest.mark.parametrize("route", ROUTES)
def test_the_tool_loop_rule_is_the_clients(route: str) -> None:
    ours = loop_code(route)
    assert ours in ("accepted", "ai_model_tool_loop_unsupported")
    assert (ours == "accepted") == client_loops(route)


def output_bounds() -> list[tuple[str, int]]:
    cases: list[tuple[str, int]] = []
    for route in ROUTES:
        bound = route_choice(MIXED, route, tool_loop=False)["maxOutputTokensMax"]
        cases += [(route, 1), (route, bound), (route, bound + 1)]
    return cases


@pytest.mark.parametrize(("route", "tokens"), output_bounds())
def test_the_output_bound_is_the_clients(route: str, tokens: int) -> None:
    ours = code(
        check(step(route=route, temperature=None, maxOutputTokens=tokens), specs=(spec(routes=ROUTES),), config=MIXED)
    )
    assert ours in ("accepted", "ai_model_max_output_range")
    assert (ours == "accepted") == client_takes_output(route, tokens)


def test_zero_output_is_refused_here_only() -> None:
    """엄격한 한쪽: 아래끝(0)은 client 가 안 보고 받기만 본다(머리말의 「아래끝도 봄」)."""
    assert code(check(step(maxOutputTokens=0))) == "ai_model_max_output_range"
    assert client_takes_output("light-openai-41", 0)


def test_the_new_comparisons_see_both_answers() -> None:
    """분모: 도구 고리·출력 상한의 대조가 참·거짓을 다 본다."""
    assert {client_loops(r) for r in ROUTES} == {True, False}
    assert {client_takes_output(r, n) for r, n in output_bounds()} == {True, False}


# ── 경로 없음·웹 검색 고정·차례(CO1 §3-1-5~7) ──

MISSING = dataclasses.replace(CONFIG, routes={k: v for k, v in CONFIG.routes.items() if k != "standard-openai-41"})


def test_a_step_route_missing_from_the_config_is_refused() -> None:
    result = check(step(route="standard-openai-41"), config=MISSING)
    assert result == ModelSettingRefused("ai_model_route_unavailable", "지금 쓸 수 없는 모델이에요", "judge")
    assert code(check(step(), config=MISSING)) == "accepted"  # 분모: 남은 경로는 받는다


def test_a_route_outside_the_step_stays_unknown_when_missing() -> None:
    specs = (spec(routes=("light-openai-41",)),)
    assert code(check(step(route="standard-openai-41"), specs=specs, config=MISSING)) == "ai_model_route_unknown"


@pytest.mark.parametrize(
    ("the_spec", "given", "expected"),
    [
        pytest.param(LOOP, LOOP_STEP, "accepted", id="loop-at-default"),
        pytest.param(LOOP, step(route="standard-openai-41"), "ai_model_web_search_fixed", id="loop-turned-off"),
        pytest.param(spec(), step(webSearch=True), "ai_model_web_search_unsupported", id="plain-turned-on"),
        pytest.param(spec(), step(), "accepted", id="plain-at-default"),
        pytest.param(spec(web_search=True), step(), "ai_model_web_search_fixed", id="plain-default-on-turned-off"),
    ],
)
def test_web_search_is_fixed_to_the_default(the_spec: AiStepSpec, given: AiModelStepIn, expected: str) -> None:
    """MARC-ENT-372: 웹 검색은 흐름 고정값. 실을 수 없는 켬은 고정보다 먼저 unsupported(그린워싱 code 그대로)."""
    assert code(check(given, specs=(the_spec,))) == expected


def test_the_new_rules_keep_their_place() -> None:
    assert (
        code(check(step(route="standard-openai-41", temperature=9.0), config=MISSING)) == "ai_model_route_unavailable"
    )
    assert code(check(step(route="light-openai", temperature=9.0), specs=(spec(tool_loop=True),))) == (
        "ai_model_tool_loop_unsupported"
    )
    assert code(check(step(route="standard-openai-41", maxOutputTokens=0), specs=(LOOP,))) == (
        "ai_model_web_search_fixed"
    )
    assert code(check(step(route="nowhere"), specs=(spec(tool_loop=True),), config=MISSING)) == "ai_model_route_unknown"


# ── 명세: key 중복·못 쓰는 경로·응답 칸(CO1 §3-1-8~10) ──


def test_a_repeated_step_key_is_a_config_error() -> None:
    twice = (spec("judge"), spec("judge"))
    with pytest.raises(LlmConfigError):
        check(step("judge"), step("judge"), specs=twice)
    with pytest.raises(LlmConfigError):
        defaults(CONFIG, twice)
    with pytest.raises(LlmConfigError):
        unusable_routes(CONFIG, twice)


def test_unusable_routes_names_what_the_check_always_refuses() -> None:
    loop = spec(routes=tuple(CAPABILITIES), tool_loop=True)
    assert unusable_routes(CONFIG, (loop,)) == tuple(("judge", r) for r in CAPABILITIES if r not in LOOP_ROUTES)
    assert unusable_routes(CONFIG, (spec(),)) == ()
    assert unusable_routes(MISSING, (spec("detect"), spec())) == (
        ("detect", "standard-openai-41"),
        ("judge", "standard-openai-41"),
    )
    assert unusable_routes(CONFIG, (LOOP,)) == ()


def test_the_view_refuses_a_route_that_moved() -> None:
    (got,) = accepted(step()).steps
    moved = dataclasses.replace(CONFIG, routes={**CONFIG.routes, "light-openai-41": ("gpt-4.1",)})
    with pytest.raises(LlmConfigError):
        model_setting_view(moved, got)
    assert model_setting_view(CONFIG, got) == {
        "route": "light-openai-41",
        "models": [ai_settings._model_ref(CONFIG.models["gpt-4.1-mini"])],  # pyright: ignore[reportPrivateUsage]
        "temperature": 0.0,
        "webSearch": False,
        "maxOutputTokens": 1300,
    }


# ── sha(3-3-6) ──


def test_the_same_value_has_the_same_sha() -> None:
    assert model_settings_sha256(accepted(step())) == model_settings_sha256(accepted(step()))
    base: dict[str, Any] = dict(step())
    reordered: Any = {k: base[k] for k in reversed(list(base))}
    assert model_settings_sha256(accepted(reordered)) == model_settings_sha256(accepted(step()))


@pytest.mark.parametrize("temperature", [0, 0.0, -0.0])
def test_zero_temperatures_share_a_sha(temperature: float) -> None:
    assert model_settings_sha256(accepted(step(temperature=temperature))) == model_settings_sha256(accepted(step()))


@pytest.mark.parametrize(
    "changed",
    [
        pytest.param(step(temperature=0.5), id="temperature"),
        pytest.param(step(temperature=None), id="temperature-null"),
        pytest.param(step(route="standard-openai-41"), id="route"),
        pytest.param(step(maxOutputTokens=1301), id="max-output"),
    ],
)
def test_a_changed_value_has_another_sha(changed: AiModelStepIn) -> None:
    assert model_settings_sha256(accepted(changed)) != model_settings_sha256(accepted(step()))


def test_web_search_changes_the_sha() -> None:
    """옮김(앞 판 매개 web-search): 공식이 webSearch 를 품는다(받기 고정 5a 와 따로 — 같은 값의 다른 칸)."""
    (got,) = accepted(LOOP_STEP, specs=(LOOP,)).steps
    off = dataclasses.replace(got, web_search=False)
    assert model_settings_sha256(AcceptedModelSettings((got,))) != model_settings_sha256(AcceptedModelSettings((off,)))


def test_the_fallback_order_is_the_routes_order() -> None:
    """대체 모델 차례: 응답 models[]·sha 의 apiModelIds 가 설정 routes 의 차례 그대로이고,
    차례를 뒤집으면 sha 가 달라진다."""
    forward = dataclasses.replace(CONFIG, routes={**CONFIG.routes, "mixed-o": ("gpt-4.1-mini", "gpt-4.1")})
    backward = dataclasses.replace(CONFIG, routes={**CONFIG.routes, "mixed-o": ("gpt-4.1", "gpt-4.1-mini")})
    specs = (spec(routes=("mixed-o",)),)
    given = step(route="mixed-o", temperature=None, maxOutputTokens=1)
    (got,) = accepted(given, specs=specs, config=forward).steps
    assert got.api_model_ids == ("gpt-4.1-mini", "gpt-4.1")
    view = ai_settings.model_setting_view(forward, got)
    assert [m["key"] for m in view["models"]] == ["gpt-4.1-mini", "gpt-4.1"]
    assert [m["key"] for m in route_choice(forward, "mixed-o", tool_loop=False)["models"]] == [
        "gpt-4.1-mini",
        "gpt-4.1",
    ]
    (back,) = accepted(given, specs=specs, config=backward).steps
    assert back.api_model_ids == ("gpt-4.1", "gpt-4.1-mini")
    assert model_settings_sha256(AcceptedModelSettings((got,))) != model_settings_sha256(AcceptedModelSettings((back,)))


def test_a_moved_route_has_another_sha() -> None:
    """배포로 경로가 다른 모델을 가리키면 같은 저장 값도 sha 가 달라진다(versions_mismatch)."""
    moved = dataclasses.replace(CONFIG, routes={**CONFIG.routes, "light-openai-41": ("gpt-4.1",)})
    assert model_settings_sha256(accepted(step(), config=moved)) != model_settings_sha256(accepted(step()))


def test_the_sha_is_the_written_json() -> None:
    by_hand = sha256_json(
        {
            "steps": [
                {
                    "key": "judge",
                    "route": "light-openai-41",
                    "apiModelIds": ["gpt-4.1-mini"],
                    "temperature": 0.0,
                    "webSearch": False,
                    "maxOutputTokens": 1300,
                }
            ]
        }
    )
    assert model_settings_sha256(accepted(step())) == by_hand


# ── AST(3-3-7) ──


def _tree() -> ast.Module:
    return ast.parse(SOURCE.read_text(encoding="utf-8"))


# 수 글자는 정수 0·1 과 정규화의 0.0 뿐(1.0 은 정수 1 과 같은 값이라 꼴까지 견준다).
ALLOWED_NUMBERS = {(int, 0), (int, 1), (float, 0.0)}


def test_the_rule_spells_no_number_and_no_model_name() -> None:
    hits: list[str] = []
    openai = 0
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Constant):
            continue
        value = node.value
        if (
            isinstance(value, int | float)
            and not isinstance(value, bool)
            and (type(value), value) not in ALLOWED_NUMBERS
        ):
            hits.append(f"{node.lineno} {value!r}")
        if isinstance(value, str):
            if "anthropic" in value or "gpt-" in value:
                hits.append(f"{node.lineno} {value!r}")
            openai += value == "openai"
            if value != "openai" and "openai" in value:
                hits.append(f"{node.lineno} {value!r}")
    assert hits == []
    assert openai == 1  # client `_check_tool_models` 와 같은 판정 자리 하나


def test_the_judge_constants_come_from_the_client() -> None:
    names = {
        alias.name
        for node in ast.walk(_tree())
        if isinstance(node, ast.ImportFrom) and node.module == "esgapi.core.llm.client"
        for alias in node.names
    }
    assert names >= {
        "TEMPERATURE_MIN",
        "TEMPERATURE_MAX",
        "TEMPERATURE_UNSUPPORTED_PROVIDERS",
        "TEMPERATURE_UNSUPPORTED_MODELS",
        "TOOL_PROVIDERS",
        "TOOL_MODELS",
    }
    assigned = {
        t.id
        for node in ast.walk(_tree())
        if isinstance(node, ast.Assign)
        for t in node.targets
        if isinstance(t, ast.Name)
    }
    assert not assigned & names


# ── AS3a-1 3-2: 프롬프트 받기 여덟(check_prompts) ──
# 이 절의 import·이름은 끝에 더함만 — 위쪽 줄 0(발주서 §1-3). 글은 지어낸 것이다.

LAYOUT2 = (("judge", ("a", "b", "c")), ("rewrite", ("x",)))
LAYOUT4 = (("judge", ("detect", "eval", "repair", "low_only")),)
FOUR_BYTE = "\U0001f600"  # UTF-8 4바이트 글자 하나


def prompts_body(*steps: tuple[str, list[tuple[str, str, str]]]) -> Any:
    return {
        "steps": [
            {"key": key, "prompts": [{"key": k, "text": t, "memo": m} for k, t, m in rows]} for key, rows in steps
        ]
    }


def good2() -> Any:
    return prompts_body(
        ("judge", [("a", "지어낸 글 가", "메모 가"), ("b", "지어낸 글 나", ""), ("c", "지어낸 글 다", "메모 다")]),
        ("rewrite", [("x", "지어낸 글 가", "")]),  # 다른 단계의 같은 글은 받는다
    )


def refused(given: Any, layout: Any = LAYOUT2) -> ai_settings.PromptRefused:
    found = ai_settings.check_prompts(given, layout=layout)
    assert isinstance(found, ai_settings.PromptRefused), found
    return found


def accepted_prompts(given: Any, layout: Any = LAYOUT2) -> ai_settings.AcceptedPrompts:
    found = ai_settings.check_prompts(given, layout=layout)
    assert isinstance(found, ai_settings.AcceptedPrompts), found
    return found


def changed(path: tuple[int, int, str], value: str, body: Any = None) -> Any:
    body = good2() if body is None else body
    i, j, field = path
    body["steps"][i]["prompts"][j][field] = value
    return body


def test_the_good_body_is_accepted() -> None:
    accepted_prompts(good2())


def mutate(body: Any, op: tuple[Any, ...]) -> None:
    """op = ("steps-reverse",) · ("steps-pop",) · ("prompts-reverse", i) · ("prompts-append", i, key) ·
    ("set", i, j, 칸, 값)."""
    match op:
        case ("steps-reverse",):
            body["steps"].reverse()
        case ("steps-pop",):
            body["steps"].pop()
        case ("prompts-reverse", i):
            body["steps"][i]["prompts"].reverse()
        case ("prompts-append", i, key):
            body["steps"][i]["prompts"].append({"key": key, "text": "지어낸 글 라", "memo": ""})
        case ("set", i, j, field, value):
            body["steps"][i]["prompts"][j][field] = value
        case _:
            raise AssertionError(op)


@pytest.mark.parametrize(
    ("op", "code", "field"),
    [
        pytest.param(("steps-reverse",), "ai_prompt_steps_fixed", "prompts.steps", id="1-steps-order"),
        pytest.param(("steps-pop",), "ai_prompt_steps_fixed", "prompts.steps", id="1-step-missing"),
        pytest.param(("prompts-append", 1, "y"), "ai_prompt_keys_fixed", "prompts.steps.1.prompts", id="2-key-extra"),
        pytest.param(("prompts-reverse", 0), "ai_prompt_keys_fixed", "prompts.steps.0.prompts", id="2-order"),
        pytest.param(
            ("set", 0, 2, "text", " \n\t\u3000"), "ai_prompt_text_empty", "prompts.steps.0.prompts.2.text", id="3-blank"
        ),
        pytest.param(
            ("set", 0, 2, "text", "지어낸 글 가"),
            "ai_prompt_text_duplicate",
            "prompts.steps.0.prompts.2.text",
            id="4-duplicate",
        ),
        pytest.param(
            ("set", 1, 0, "text", "가" * 8001), "ai_prompt_text_length", "prompts.steps.1.prompts.0.text", id="5-length"
        ),
        pytest.param(
            ("set", 0, 1, "text", "지어낸\x00글"), "ai_prompt_chars", "prompts.steps.0.prompts.1.text", id="6-text-nul"
        ),
        pytest.param(
            ("set", 0, 1, "text", "지어낸\ud800글"),
            "ai_prompt_chars",
            "prompts.steps.0.prompts.1.text",
            id="6-text-surrogate",
        ),
        pytest.param(
            ("set", 0, 1, "memo", "메모\x00"), "ai_prompt_chars", "prompts.steps.0.prompts.1.memo", id="6-memo-nul"
        ),
        pytest.param(
            ("set", 0, 1, "memo", "\udfff메모"),
            "ai_prompt_chars",
            "prompts.steps.0.prompts.1.memo",
            id="6-memo-surrogate",
        ),
        pytest.param(
            ("set", 0, 0, "memo", " " + "메" * 501 + " "),
            "ai_prompt_memo_length",
            "prompts.steps.0.prompts.0.memo",
            id="7-memo-length",
        ),
    ],
)
def test_a_prompt_rule_refuses_its_case(op: tuple[Any, ...], code: str, field: str) -> None:
    body = good2()
    mutate(body, op)
    found = refused(body)
    assert (found.code, found.field) == (code, field)
    assert found.message.endswith("요")
    assert "지어낸" not in found.message and "메" * 3 not in found.message  # 값·글 0


def test_the_limits_themselves_are_accepted() -> None:
    """분모: 상한 그대로(글 8,000자·메모 strip 뒤 500자), 짝 맞은 서로게이트(4바이트 글자)는 받는다."""
    body = changed((1, 0, "text"), "가" * 8000)
    body = changed((0, 0, "memo"), "  " + "메" * 500 + "\n", body)
    body = changed((0, 1, "text"), "지어낸 " + FOUR_BYTE, body)
    found = accepted_prompts(body)
    assert found.steps[0].prompts[0].memo == "메" * 500


def test_the_steps_rule_comes_before_a_duplicate() -> None:
    body = changed((0, 2, "text"), "지어낸 글 가")
    assert refused(body).code == "ai_prompt_text_duplicate"  # 분모: 4 만이면 4
    body["steps"].reverse()
    assert refused(body).code == "ai_prompt_steps_fixed"


def test_a_blank_pair_is_empty_before_duplicate() -> None:
    body = changed((0, 1, "text"), "  ")
    body = changed((0, 2, "text"), "  ", body)
    assert (refused(body).code, refused(body).field) == ("ai_prompt_text_empty", "prompts.steps.0.prompts.1.text")


def test_the_text_is_kept_byte_for_byte_and_the_memo_is_stripped() -> None:
    text = "  지어낸 글\r\n둘째 줄\t \n"
    found = accepted_prompts(changed((0, 0, "memo"), " \n 지어낸 메모 \t", changed((0, 0, "text"), text)))
    first = found.steps[0].prompts[0]
    assert first.text.encode() == text.encode()
    assert first.memo == "지어낸 메모"
    assert ai_settings.prompts_input(found)["steps"][0]["prompts"][0] == {
        "key": "a",
        "text": text,
        "memo": "지어낸 메모",
    }
    assert ai_settings.check_prompts(ai_settings.prompts_input(found), layout=LAYOUT2) == found  # 다시 받으면 같은 값


def four(text: str, memo: str) -> Any:
    """넷 다 같은 꼴의 글(마지막 글자로 서로 다르게 — 규칙 4 를 피함)."""
    tails = ("\U0001d538", "\U0001d539", "\U0001d53b", "\U0001d53c")
    return prompts_body(
        ("judge", [(key, text[:-1] + tail, memo) for key, tail in zip(LAYOUT4[0][1], tails, strict=True)])
    )


def test_the_total_size_refuses_four_byte_texts_with_memos() -> None:
    """규칙 8 주 사례(critic 2 B2): 4바이트 글자 8,000자 글 넷 + 4바이트 글자 500자 메모 넷(≈136,000 B) — 규칙 5·7 은
    지난다. 분모: 메모가 빈 글이면(≈128,000 B) 받는다."""
    heavy = four(FOUR_BYTE * 8000, FOUR_BYTE * 500)
    found = refused(heavy, LAYOUT4)
    assert (found.code, found.field) == ("ai_prompt_total_size", "prompts")
    light = accepted_prompts(four(FOUR_BYTE * 8000, ""), LAYOUT4)
    assert 128000 < ai_settings.prompts_size(light) <= ai_settings.PROMPTS_MAX_OCTETS


def test_the_total_size_counts_escaped_control_chars() -> None:
    """제어 글자는 직렬화에서 6바이트(\\u0001) — 글자 수 상한 안이어도 크기가 막는다."""
    found = refused(four("\x01" * 8000, ""), LAYOUT4)
    assert found.code == "ai_prompt_total_size"
    accepted_prompts(four("\x01" * 5000, ""), LAYOUT4)  # 분모: 4 × 5,000 × 6 ≈ 120,000 B


def test_the_prompt_constants() -> None:
    assert (ai_settings.PROMPT_TEXT_MAX_CHARS, ai_settings.PROMPT_MEMO_MAX_CHARS) == (8000, 500)
    assert ai_settings.PROMPTS_MAX_OCTETS == 131072
    assert ai_settings.prompt_limits() == {"textMax": 8000, "memoMax": 500}


# ── AS3a-1 3-3: prompts_sha256 · prompts_size ──


def test_the_sha_ignores_the_memo_and_sees_text_and_order() -> None:
    import hashlib
    import json

    base = accepted_prompts(good2())
    memo = accepted_prompts(changed((0, 1, "memo"), "다른 메모"))
    text = accepted_prompts(changed((0, 1, "text"), "지어낸 글 나!"))
    assert ai_settings.prompts_sha256(memo) == ai_settings.prompts_sha256(base)
    assert ai_settings.prompts_sha256(text) != ai_settings.prompts_sha256(base)
    a, b, c = base.steps[0].prompts
    swapped = dataclasses.replace(base, steps=(dataclasses.replace(base.steps[0], prompts=(b, a, c)), base.steps[1]))
    assert ai_settings.prompts_sha256(swapped) != ai_settings.prompts_sha256(base)
    rows = [["judge", "a", "지어낸 글 가"], ["judge", "b", "지어낸 글 나"], ["judge", "c", "지어낸 글 다"]]
    rows.append(["rewrite", "x", "지어낸 글 가"])
    by_hand = hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    assert ai_settings.prompts_sha256(base) == by_hand


def test_the_size_is_the_jsonb_text_length() -> None:
    """★D: postgres jsonb::text 꼴 — ", "·": " 구분, 한글 그대로(3바이트), 제어 글자 \\u0001(6바이트), 따옴표 \\"(2)."""
    found = accepted_prompts(prompts_body(("s", [("a", 'ㄱ\x01"', "m")])), (("s", ("a",)),))
    by_hand = '{"steps": [{"key": "s", "prompts": [{"key": "a", "text": "ㄱ\\u0001\\"", "memo": "m"}]}]}'
    assert ai_settings.prompts_size(found) == len(by_hand.encode("utf-8")) == len(by_hand) + 2


# ── AS3a-1 3-4: prompt_entry ──


def entry(text: str, section: str | None) -> Any:
    return ai_settings.prompt_entry(
        key="a",
        label="지어낸 칸",
        prompt_id="m/a@1",
        prompt_version="v",
        text=text,
        memo="지어낸 메모",
        default_text="지어낸 기본 글\n[출력]\n{}",
        output_section=section,
    )


def test_the_entry_marks_default_and_kept() -> None:
    default = "지어낸 기본 글\n[출력]\n{}"
    same = entry(default, "[출력]\n{}")
    assert (same["isDefault"], same["outputKept"], same["memo"]) == (True, True, "지어낸 메모")
    assert same["defaultText"] == default and same["sha256"] == ai_settings.sha256_text(default)
    one_char = entry("지어낸 기본 글!\n[출력]\n{}", "[출력]\n{}")
    assert (one_char["isDefault"], one_char["outputKept"]) == (False, True)
    broken = entry("지어낸 기본 글\n[출력]\n{ }", "[출력]\n{}")
    assert (broken["isDefault"], broken["outputKept"]) == (False, False)
    none = entry("다른 글", None)
    assert (none["isDefault"], none["outputKept"], none["outputSection"]) == (False, True, None)


def test_has_bad_chars_is_the_one_public_check() -> None:
    """나쁜 글자 판정식은 core 공개 이름 하나다 — 그린워싱 판 이름·메모 거절도 이것을 쓴다(MARC-ISSUE-289 의 2)."""
    assert ai_settings.has_bad_chars("지어낸\x00글") and ai_settings.has_bad_chars("홀로 온 \ud800")
    assert not ai_settings.has_bad_chars("지어낸 글 😀") and not ai_settings.has_bad_chars("")
    assert not hasattr(ai_settings, "_bad_chars")
