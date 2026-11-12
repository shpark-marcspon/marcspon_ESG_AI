"""모듈 공통 AI 설정의 순수 규칙(밴드 AS1, 이슈 MARC-ISSUE-240, 결정 MARC-ENT-353): 단계마다 고를 수 있는 경로의 능력,
모델 설정 받기, 받은 값의 sha. 꼴은 contracts/ai_setting_shapes.py.

순수하다(django·ninja·psycopg 를 모른다. `.importlinter` 계약 다). 도메인을 모른다: 단계 명세(`AiStepSpec`)·허용
경로·기본값은 부르는 쪽이 넘기고, 설정(`LlmConfig`)도 부르는 쪽이 넘긴다(화면·받기용은
`default_config_sources(synthetic=False)` 로 지은 것).

★ 판정은 호출 층(core/llm/client.py 의 `_check_temperature`·`_check_tool_models`)과 같아야 한다. 판정 상수는 그 파일의
  공개 상수를 import 한다 — 여기에 복사하지 않는다(core/tests/calc/test_ai_settings.py 가 AST 로 보고 client 와 견준다).

받기 차례(어기는 첫 것 하나. 단계는 명세 차례로 돌고, 한 단계 안에서는 2→6 차례 — 밴드 CO1 이 2a·2b·5a 를 끼움):
    1  ai_model_steps_fixed              단계 key 목록이 명세의 목록·차례와 다름
    2  ai_model_route_unknown            경로가 그 단계의 routes 밖
    2a ai_model_route_unavailable        경로가 단계 routes 안인데 설정에 없음(배포로 빠질 수 있다 — MARC-ISSUE-248)
    2b ai_model_tool_loop_unsupported    고리 단계인데 경로가 고리를 못 지남(client `_check_tool_models`, 도구 없음 칸)
    3  ai_model_temperature_range        temperature 가 값인데 유한한 수가 아니거나 범위 밖
    4  ai_model_temperature_unsupported  temperature 가 값인데 경로 모델 하나라도 안 받음(null 은 늘 통과)
    5  ai_model_web_search_unsupported   webSearch 인데 그 단계에서 web_search 를 실을 수 없음
    5a ai_model_web_search_fixed         webSearch 가 그 단계 기본값과 다름(흐름 고정값 — MARC-ENT-372)
    6  ai_model_max_output_range         maxOutputTokens 가 1 보다 작거나 경로 상한 위(호출 층보다 엄격: 아래끝도 봄)
기본값이 받기를 못 지나거나 단계 key 가 겹치면 LlmConfigError(도메인 잘못 — 거절이 아니다). 설정에 없는 경로는 받기
거절(2a)이다.

프롬프트 글 받기(`check_prompts` — 밴드 AS3a-1, 이슈 MARC-ISSUE-257, 결정 MARC-ENT-381·384·385). 모듈은
layout(단계 key 와 그 칸 key 의 차례)만 넘긴다. 어기는 첫 것 하나 — 1 다음 단계를 명세 차례로 돌며 한 단계 안에서
2→7, 끝에 8:
    1  ai_prompt_steps_fixed      단계 key 목록이 layout 과 다름                      field prompts.steps
    2  ai_prompt_keys_fixed       칸 key 목록·차례가 layout 과 다름                    field prompts.steps.<i>.prompts
    3  ai_prompt_text_empty       글이 공백뿐                                          field …prompts.<j>.text
    4  ai_prompt_text_duplicate   한 단계 안 두 칸의 글이 같음(엔진이 system 글자 같음으로 칸을 가른다)  …<j>.text
    5  ai_prompt_text_length      글 > PROMPT_TEXT_MAX_CHARS                           …<j>.text
    6  ai_prompt_chars            글·메모에 NUL·짝 없는 서로게이트(DB 가 못 받는다)     …<j>.text|memo
    7  ai_prompt_memo_length      메모(strip 뒤) > PROMPT_MEMO_MAX_CHARS                …<j>.memo
    8  ai_prompt_total_size       prompts_size(정규형) > PROMPTS_MAX_OCTETS             field prompts
글은 바이트 그대로 받는다(strip·줄바꿈 바꿈 0). 메모는 strip 한 값이 정규형이다. sha(`prompts_sha256`)는 글만 품는다 —
메모만 다른 판은 같은 sha. 상수 셋은 contracts/ai_setting_shapes.py 에 있다(이 파일은 수 글자를 쓰지 않는다).

부품과 모듈 선언(밴드 AP1a, 결정 MARC-ENT-399 — 꼴 표는 contracts/ai_setting_shapes.py 머리말). 모듈은
`AiModuleSpec(module, models, groups)` 하나로 선언하고 `compose` 로 ai.prompt-model@3 을 짓는다 — 단계에 모델을
박지 않는다. 모델 칸 명세는 `AiModelSlotSpec`(옛 이름 `AiStepSpec` 은 별칭 — AP1c 가 지운다), 받기는 위 차례
그대로(`refused.step` = 칸 key). 프롬프트 묶음 명세는 `AiPromptGroupSpec`, 받기 layout 은 `layout_of(spec)`. 입력 @1 의
steps[i] 는 칸 i·묶음 i 다.
`check_module` 은 구조만 본다(설정 없이). 어기면 LlmConfigError(도메인 잘못), 글에 그 key:
    module 이 빈 글 · 모델 칸 0 · 프롬프트 묶음 0 · 칸 key 겹침 · 묶음 key 겹침 · 묶음 안 칸 key 0 ·
    묶음 안 칸 key 겹침 · 묶음 model_slots 에 모르는 칸 key
`compose` 는 그 위에 받은 모델 값의 칸 차례·묶음의 프롬프트 열쇠(정확히 같아야)·묶음 안 칸 차례를 대 보고(어긋나면
LlmConfigError), 쓸 수 없는 경로는 `unavailableRoutes` 로 낸다(`route_choices` — `unusable_routes` 와 같은 판정).
칸의 고른 경로 자체를 쓸 수 없으면 LlmConfigError(배포 잘못 — MARC-ISSUE-280 처분 Q4). 판 규칙(`next_version_name`·
`version_status`·`ai_versions`)은 판 목록·꼴 없이 순수 규칙만이다(판 꼴은 모듈마다 — MARC-ENT-350).
"""

import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from esgapi.core.contracts.ai_setting_shapes import (
    PROMPT_MEMO_MAX_CHARS,
    PROMPT_MODEL_V3_SHAPE,
    PROMPT_TEXT_MAX_CHARS,
    PROMPTS_MAX_OCTETS,
    AiFixedGroup,
    AiModelRef,
    AiModelSetting,
    AiModelSettingsIn,
    AiModelSlot,
    AiModelStepIn,
    AiPromptEntry,
    AiPromptGroup,
    AiPromptIn,
    AiPromptLimits,
    AiPromptModel3,
    AiPromptModelEditable,
    AiPromptsIn,
    AiRouteChoice,
    AiVersionsCommon,
    AiVersionStatus,
)
from esgapi.core.llm.client import (
    TEMPERATURE_MAX,
    TEMPERATURE_MIN,
    TEMPERATURE_UNSUPPORTED_MODELS,
    TEMPERATURE_UNSUPPORTED_PROVIDERS,
    TOOL_MODELS,
    TOOL_PROVIDERS,
)
from esgapi.core.llm.config import LlmConfig, ModelConfig, resolve_route
from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.log import sha256_json, sha256_text


@dataclass(frozen=True, slots=True)
class AiModelSlotSpec:
    """도메인이 단계마다 하나. `routes` = 그 단계에 허용된 경로(차례 = 화면 차례). `tool_loop` = 그 단계가 도구 고리
    (`call_tools`)를 지나는가 — web_search 가능의 전제. `default` = 기본 판의 값(key 는 이 단계의 key)."""

    key: str
    label: str
    routes: tuple[str, ...]
    tool_loop: bool
    default: AiModelStepIn


AiStepSpec = AiModelSlotSpec  # 옛 이름(AP1a Q8 — AP1c 가 지운다)


@dataclass(frozen=True, slots=True)
class AcceptedStep:
    """받은 단계 값의 정규형. `api_model_ids` 는 받을 때 경로가 푼 모델(첫째가 주, 대체 차례째)."""

    key: str
    route: str
    api_model_ids: tuple[str, ...]
    temperature: float | None
    web_search: bool
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class AcceptedModelSettings:
    steps: tuple[AcceptedStep, ...]


@dataclass(frozen=True, slots=True)
class ModelSettingRefused:
    """받기 거절. code 는 소문자(나갈 때 대문자), step 은 어긴 단계 key(단계 구성 거절은 None)."""

    code: str
    message: str
    step: str | None


def _model_ref(model: ModelConfig) -> AiModelRef:
    return {"key": model.key, "label": model.entry.label, "provider": model.provider}


def _accepts_temperature(models: Sequence[ModelConfig]) -> bool:
    """경로 모델 전부가 temperature 를 받는다(client `_check_temperature` 의 모델 판정)."""
    return all(
        model.provider not in TEMPERATURE_UNSUPPORTED_PROVIDERS
        and model.api_model_id not in TEMPERATURE_UNSUPPORTED_MODELS
        for model in models
    )


def _passes_tool_loop(model: ModelConfig) -> bool:
    """모델이 도구 고리를 지난다(client `_check_tool_models` 의 공급사·모델 판정)."""
    return model.provider in TOOL_PROVIDERS and (model.provider != "openai" or model.api_model_id in TOOL_MODELS)


def _carries_web_search(model: ModelConfig) -> bool:
    return _passes_tool_loop(model) and model.hosted_tool_pricing is not None


def _loop_route(models: Sequence[ModelConfig]) -> bool:
    """경로가 도구 고리를 지난다(client `_check_tool_models` 의 도구 없음 칸: 모델 하나, 그 모델이 고리를 지남)."""
    return len(models) == 1 and all(_passes_tool_loop(model) for model in models)


def _web_search_available(models: Sequence[ModelConfig], *, tool_loop: bool) -> bool:
    """도구 고리를 지나는 단계이고 경로가 web_search 를 실을 수 있다(client `_check_tool_models` 의 판정: 모델 하나)."""
    return tool_loop and _loop_route(models) and all(_carries_web_search(model) for model in models)


def _max_output(models: Sequence[ModelConfig]) -> int:
    return min(model.max_output_tokens for model in models)


def route_choice(config: LlmConfig, route: str, *, tool_loop: bool) -> AiRouteChoice:
    """경로 하나의 능력. 경로가 설정에 없으면 LlmConfigError(도메인 명세 잘못)."""
    models = resolve_route(config, route)
    return {
        "route": route,
        "models": [_model_ref(model) for model in models],
        "acceptsTemperature": _accepts_temperature(models),
        "webSearchAvailable": _web_search_available(models, tool_loop=tool_loop),
        "maxOutputTokensMax": _max_output(models),
    }


def _temperature_out_of_range(temperature: float) -> bool:
    return (
        isinstance(temperature, bool)
        or not math.isfinite(temperature)
        or not TEMPERATURE_MIN <= temperature <= TEMPERATURE_MAX
    )


def _check_step(config: LlmConfig, spec: AiStepSpec, given: AiModelStepIn) -> AcceptedStep | ModelSettingRefused:
    route = given["route"]
    if route not in spec.routes:
        return ModelSettingRefused("ai_model_route_unknown", "고를 수 없는 모델이에요", spec.key)
    try:
        models = resolve_route(config, route)
    except LlmConfigError:
        return ModelSettingRefused("ai_model_route_unavailable", "지금 쓸 수 없는 모델이에요", spec.key)
    if spec.tool_loop and not _loop_route(models):
        return ModelSettingRefused("ai_model_tool_loop_unsupported", "이 단계에서는 쓸 수 없는 모델이에요", spec.key)
    temperature = given["temperature"]
    if temperature is not None and _temperature_out_of_range(temperature):
        return ModelSettingRefused("ai_model_temperature_range", "temperature 는 0~2 사이 수로 넣어 주세요", spec.key)
    if temperature is not None and not _accepts_temperature(models):
        return ModelSettingRefused(
            "ai_model_temperature_unsupported", "이 모델은 temperature 를 바꿀 수 없어요", spec.key
        )
    if given["webSearch"] and not _web_search_available(models, tool_loop=spec.tool_loop):
        return ModelSettingRefused("ai_model_web_search_unsupported", "이 모델은 웹 검색을 쓸 수 없어요", spec.key)
    if given["webSearch"] != spec.default["webSearch"]:
        return ModelSettingRefused("ai_model_web_search_fixed", "웹 검색 여부는 바꿀 수 없어요", spec.key)
    max_output_tokens = given["maxOutputTokens"]
    if max_output_tokens < 1 or max_output_tokens > _max_output(models):
        return ModelSettingRefused("ai_model_max_output_range", "출력 상한이 모델이 받는 범위를 넘어요", spec.key)
    return AcceptedStep(
        key=spec.key,
        route=route,
        api_model_ids=tuple(model.api_model_id for model in models),
        # int → float, -0.0 → 0.0: 같은 값은 같은 sha.
        temperature=None if temperature is None else float(temperature) + 0.0,
        web_search=given["webSearch"],
        max_output_tokens=max_output_tokens,
    )


def _check_unique_keys(steps: Sequence[AiStepSpec]) -> None:
    keys = [spec.key for spec in steps]
    if len(set(keys)) != len(keys):
        raise LlmConfigError(f"AI 설정 단계 명세의 key 가 겹친다: {keys}")


def check_model_settings(
    config: LlmConfig, given: AiModelSettingsIn, *, steps: Sequence[AiStepSpec]
) -> AcceptedModelSettings | ModelSettingRefused:
    """받기. `given` 은 이미 꼴(`MODEL_SETTINGS`)을 지난 값이다(꼴 틀림은 부르는 쪽의 422). 어기는 첫 것 하나.
    명세의 단계 key 가 겹치면 LlmConfigError(도메인 잘못)."""
    _check_unique_keys(steps)
    if [step["key"] for step in given["steps"]] != [spec.key for spec in steps]:
        return ModelSettingRefused("ai_model_steps_fixed", "단계 구성은 바꿀 수 없어요", None)
    accepted: list[AcceptedStep] = []
    for spec, step in zip(steps, given["steps"], strict=True):
        result = _check_step(config, spec, step)
        if isinstance(result, ModelSettingRefused):
            return result
        accepted.append(result)
    return AcceptedModelSettings(steps=tuple(accepted))


def defaults(config: LlmConfig, steps: Sequence[AiStepSpec]) -> AcceptedModelSettings:
    """명세의 기본값을 같은 받기로. 지금 설정에 안 맞으면 LlmConfigError(도메인 잘못)."""
    result = check_model_settings(config, {"steps": [spec.default for spec in steps]}, steps=steps)
    if isinstance(result, ModelSettingRefused):
        raise LlmConfigError(f"AI 설정 기본값이 받기를 못 지난다: {result.code} (단계 {result.step})")
    return result


def unusable_routes(config: LlmConfig, steps: Sequence[AiStepSpec]) -> tuple[tuple[str, str], ...]:
    """명세가 허용한 경로 가운데 받기가 늘 거절할 것 — (단계 key, 경로), 명세 차례. 설정에 없는 경로(2a)와 도구 고리
    단계에서 고리를 못 지나는 경로(2b). 도메인 시험이 `== ()` 로 명세를 잰다. 단계 key 가 겹치면 LlmConfigError."""
    _check_unique_keys(steps)
    found: list[tuple[str, str]] = []
    for spec in steps:
        for route in spec.routes:
            try:
                models = resolve_route(config, route)
            except LlmConfigError:
                found.append((spec.key, route))
                continue
            if spec.tool_loop and not _loop_route(models):
                found.append((spec.key, route))
    return tuple(found)


def to_input(accepted: AcceptedModelSettings) -> AiModelSettingsIn:
    """저장하는 꼴(정규형). 다시 받으면 같은 값이 된다."""
    return {
        "steps": [
            {
                "key": step.key,
                "route": step.route,
                "temperature": step.temperature,
                "webSearch": step.web_search,
                "maxOutputTokens": step.max_output_tokens,
            }
            for step in accepted.steps
        ]
    }


def model_setting_view(config: LlmConfig, accepted: AcceptedStep) -> AiModelSetting:
    """응답의 단계 모델 칸. 같은 설정으로 받은 값이어야 한다 — 경로가 받을 때와 다른 모델로 풀리면 LlmConfigError."""
    models = resolve_route(config, accepted.route)
    if tuple(model.api_model_id for model in models) != accepted.api_model_ids:
        raise LlmConfigError(f"경로 {accepted.route} 가 받을 때와 다른 모델로 풀린다: {accepted.api_model_ids}")
    return {
        "route": accepted.route,
        "models": [_model_ref(model) for model in models],
        "temperature": accepted.temperature,
        "webSearch": accepted.web_search,
        "maxOutputTokens": accepted.max_output_tokens,
    }


def model_settings_sha256(accepted: AcceptedModelSettings) -> str:
    """받은 값의 sha(실행 versions 에 실릴 값). 경로 이름과 풀린 api_model_id 를 함께 품는다 — 배포로 경로→모델 짝이
    바뀌면 같은 저장 값이 다른 sha 가 되어 워커 대조에서 versions_mismatch(MARC-ENT-352)."""
    return sha256_json(
        {
            "steps": [
                {
                    "key": step.key,
                    "route": step.route,
                    "apiModelIds": list(step.api_model_ids),
                    "temperature": step.temperature,
                    "webSearch": step.web_search,
                    "maxOutputTokens": step.max_output_tokens,
                }
                for step in accepted.steps
            ]
        }
    )


def prompt_entry(
    *,
    key: str,
    label: str,
    prompt_id: str,
    prompt_version: str,
    text: str,
    memo: str,
    default_text: str,
    output_section: str | None,
) -> AiPromptEntry:
    """응답의 프롬프트 칸. `output_section` 은 기본 글(default_text)에서 뗀 출력 형식 절이다(부르는 쪽이 넘긴다)."""
    return {
        "key": key,
        "label": label,
        "promptId": prompt_id,
        "promptVersion": prompt_version,
        "sha256": sha256_text(text),
        "text": text,
        "memo": memo,
        "defaultText": default_text,
        "isDefault": text == default_text,
        "outputSection": output_section,
        "outputKept": output_section is None or output_section in text,
    }


PromptLayout = Sequence[tuple[str, Sequence[str]]]
"""모듈의 프롬프트 명세: (단계 key, 그 단계 칸 key 들) 의 차례."""


@dataclass(frozen=True, slots=True)
class AcceptedPrompt:
    key: str
    text: str
    """받은 글 바이트 그대로."""
    memo: str
    """strip 한 메모."""


@dataclass(frozen=True, slots=True)
class AcceptedPromptStep:
    key: str
    prompts: tuple[AcceptedPrompt, ...]


@dataclass(frozen=True, slots=True)
class AcceptedPrompts:
    steps: tuple[AcceptedPromptStep, ...]


@dataclass(frozen=True, slots=True)
class PromptRefused:
    """프롬프트 받기 거절. code 는 소문자(나갈 때 대문자), field 는 422 의 fields 와 같은 점 경로."""

    code: str
    message: str
    field: str


def prompt_limits() -> AiPromptLimits:
    return {"textMax": PROMPT_TEXT_MAX_CHARS, "memoMax": PROMPT_MEMO_MAX_CHARS}


def has_bad_chars(value: str) -> bool:
    """NUL 이나 짝 없는 서로게이트(JSON 의 \\ud800 처럼 홀로 온 것 — 짝이 맞으면 글자 하나로 풀려 여기 안 온다)."""
    return any(char == "\x00" or "\ud800" <= char <= "\udfff" for char in value)


def _check_prompt_step(
    index: int, keys: Sequence[str], given: list[AiPromptIn]
) -> tuple[AcceptedPrompt, ...] | PromptRefused:
    at = f"prompts.steps.{index}.prompts"
    if [prompt["key"] for prompt in given] != list(keys):
        return PromptRefused("ai_prompt_keys_fixed", "프롬프트 칸 구성은 바꿀 수 없어요", at)
    for j, prompt in enumerate(given):
        if not prompt["text"].strip():
            return PromptRefused("ai_prompt_text_empty", "프롬프트 글을 넣어 주세요", f"{at}.{j}.text")
    seen: set[str] = set()
    for j, prompt in enumerate(given):
        if prompt["text"] in seen:
            return PromptRefused(
                "ai_prompt_text_duplicate", "같은 단계의 프롬프트 글은 서로 달라야 해요", f"{at}.{j}.text"
            )
        seen.add(prompt["text"])
    for j, prompt in enumerate(given):
        if len(prompt["text"]) > PROMPT_TEXT_MAX_CHARS:
            return PromptRefused("ai_prompt_text_length", "프롬프트 글이 너무 길어요", f"{at}.{j}.text")
    for j, prompt in enumerate(given):
        for field in ("text", "memo"):
            if has_bad_chars(prompt[field]):
                return PromptRefused("ai_prompt_chars", "쓸 수 없는 글자가 들어 있어요", f"{at}.{j}.{field}")
    for j, prompt in enumerate(given):
        if len(prompt["memo"].strip()) > PROMPT_MEMO_MAX_CHARS:
            return PromptRefused("ai_prompt_memo_length", "메모가 너무 길어요", f"{at}.{j}.memo")
    return tuple(AcceptedPrompt(p["key"], p["text"], p["memo"].strip()) for p in given)


def check_prompts(given: AiPromptsIn, *, layout: PromptLayout) -> AcceptedPrompts | PromptRefused:
    """받기. `given` 은 이미 꼴(`PROMPTS`)을 지난 값이다(꼴 틀림은 부르는 쪽의 422). 어기는 첫 것 하나."""
    if [step["key"] for step in given["steps"]] != [key for key, _ in layout]:
        return PromptRefused("ai_prompt_steps_fixed", "프롬프트 단계 구성은 바꿀 수 없어요", "prompts.steps")
    steps: list[AcceptedPromptStep] = []
    for index, ((key, keys), step) in enumerate(zip(layout, given["steps"], strict=True)):
        result = _check_prompt_step(index, keys, step["prompts"])
        if isinstance(result, PromptRefused):
            return result
        steps.append(AcceptedPromptStep(key=key, prompts=result))
    accepted = AcceptedPrompts(steps=tuple(steps))
    if prompts_size(accepted) > PROMPTS_MAX_OCTETS:
        return PromptRefused("ai_prompt_total_size", "프롬프트 글과 메모를 합친 크기가 너무 커요", "prompts")
    return accepted


def prompts_input(accepted: AcceptedPrompts) -> AiPromptsIn:
    """저장하는 꼴(정규형 — 글 그대로·메모 strip). 다시 받으면 같은 값이 된다."""
    return {
        "steps": [
            {"key": step.key, "prompts": [{"key": p.key, "text": p.text, "memo": p.memo} for p in step.prompts]}
            for step in accepted.steps
        ]
    }


def prompts_size(accepted: AcceptedPrompts) -> int:
    """저장 꼴의 직렬화 UTF-8 바이트 — postgres `jsonb::text` 와 같은 꼴(", "·": " 구분, 비ASCII 그대로, 제어 글자는
    \\u00XX)로 셈한다. 열쇠 차례는 크기를 바꾸지 않는다."""
    text = json.dumps(prompts_input(accepted), ensure_ascii=False, separators=(", ", ": "))
    return len(text.encode("utf-8"))


def prompts_sha256(accepted: AcceptedPrompts) -> str:
    """받은 글의 sha — [[단계, 칸, 글], …] 차례째. 메모는 품지 않는다(메모만 다른 판은 같은 sha)."""
    return sha256_json([[step.key, p.key, p.text] for step in accepted.steps for p in step.prompts])


# ── 부품·모듈 선언·조합(AP1a) ──


@dataclass(frozen=True, slots=True)
class AiPromptGroupSpec:
    """모듈의 프롬프트 묶음 하나. `prompt_keys` = 그 묶음 칸 key 차례, `model_slots` = 그 글을 받는 모델 칸
    key(화면 안내)."""

    key: str
    label: str
    prompt_keys: tuple[str, ...]
    model_slots: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AiModuleSpec:
    """모듈 선언: 이름 · 모델 칸(차례 = 입력 ai.model-settings@1 의 steps) · 프롬프트 묶음(차례 = ai.prompts@1 의
    steps)."""

    module: str
    models: tuple[AiModelSlotSpec, ...]
    groups: tuple[AiPromptGroupSpec, ...]


def _repeated(keys: Sequence[str]) -> list[str]:
    return sorted({key for key in keys if keys.count(key) > 1})


def check_module(spec: AiModuleSpec) -> None:
    """모듈 선언의 구조(설정 없이). 어기면 LlmConfigError — 차례는 머리말."""
    if not spec.module.strip():
        raise LlmConfigError("AI 설정 모듈 이름이 비었다")
    if not spec.models:
        raise LlmConfigError(f"AI 설정 모듈 {spec.module} 에 모델 칸이 없다")
    if not spec.groups:
        raise LlmConfigError(f"AI 설정 모듈 {spec.module} 에 프롬프트 묶음이 없다")
    slots = [slot.key for slot in spec.models]
    if repeated := _repeated(slots):
        raise LlmConfigError(f"AI 설정 모듈 {spec.module} 의 모델 칸 key 가 겹친다: {repeated}")
    if repeated := _repeated([group.key for group in spec.groups]):
        raise LlmConfigError(f"AI 설정 모듈 {spec.module} 의 프롬프트 묶음 key 가 겹친다: {repeated}")
    for group in spec.groups:
        if not group.prompt_keys:
            raise LlmConfigError(f"AI 설정 묶음 {group.key} 에 프롬프트 칸이 없다")
        if repeated := _repeated(group.prompt_keys):
            raise LlmConfigError(f"AI 설정 묶음 {group.key} 의 칸 key 가 겹친다: {repeated}")
        if unknown := [slot for slot in group.model_slots if slot not in slots]:
            raise LlmConfigError(f"AI 설정 묶음 {group.key} 의 model_slots 에 모르는 칸이 있다: {unknown}")


def layout_of(spec: AiModuleSpec) -> PromptLayout:
    """check_prompts 에 넘기는 layout — (묶음 key, 칸 key 차례) 의 차례."""
    return tuple((group.key, group.prompt_keys) for group in spec.groups)


def route_choices(config: LlmConfig, slot: AiModelSlotSpec) -> tuple[list[AiRouteChoice], list[str]]:
    """칸의 허용 경로를 지금 쓸 수 있는 것(능력)과 쓸 수 없는 것(이름)으로, 명세 차례. 판정은 `unusable_routes` 와
    같다(설정에 없음 · 고리 칸에서 고리를 못 지남)."""
    choices: list[AiRouteChoice] = []
    unavailable: list[str] = []
    for route in slot.routes:
        try:
            models = resolve_route(config, route)
        except LlmConfigError:
            unavailable.append(route)
            continue
        if slot.tool_loop and not _loop_route(models):
            unavailable.append(route)
            continue
        choices.append(route_choice(config, route, tool_loop=slot.tool_loop))
    return choices, unavailable


def _model_slot(config: LlmConfig, slot: AiModelSlotSpec, accepted: AcceptedStep) -> AiModelSlot:
    choices, unavailable = route_choices(config, slot)
    if accepted.route not in [choice["route"] for choice in choices]:
        raise LlmConfigError(f"AI 설정 칸 {slot.key} 의 고른 경로 {accepted.route} 를 지금 쓸 수 없다")
    return {
        "key": slot.key,
        "label": slot.label,
        "model": model_setting_view(config, accepted),
        "routeChoices": choices,
        "unavailableRoutes": unavailable,
    }


def _prompt_group(group: AiPromptGroupSpec, entries: Sequence[AiPromptEntry]) -> AiPromptGroup:
    if [entry["key"] for entry in entries] != list(group.prompt_keys):
        raise LlmConfigError(f"AI 설정 묶음 {group.key} 의 칸 차례가 명세와 다르다")
    return {"key": group.key, "label": group.label, "modelSlots": list(group.model_slots), "prompts": list(entries)}


def compose(
    config: LlmConfig,
    spec: AiModuleSpec,
    *,
    setting_name: str,
    editable: AiPromptModelEditable,
    model: AcceptedModelSettings,
    prompts: Mapping[str, Sequence[AiPromptEntry]],
    fixed: Sequence[AiFixedGroup],
) -> AiPromptModel3:
    """한 판의 ai.prompt-model@3. model 은 받기를 지난 값(칸 차례 = spec.models), prompts 는 묶음 key → 칸(prompt_entry)
    — 열쇠가 묶음과 정확히 같아야 한다. 어긋나면 LlmConfigError(도메인 잘못)."""
    check_module(spec)
    if [step.key for step in model.steps] != [slot.key for slot in spec.models]:
        raise LlmConfigError(f"AI 설정 모듈 {spec.module} 의 모델 값 칸 차례가 명세와 다르다")
    if set(prompts) != {group.key for group in spec.groups}:
        raise LlmConfigError(f"AI 설정 모듈 {spec.module} 의 프롬프트 열쇠가 묶음과 다르다: {sorted(prompts)}")
    return {
        "schemaVersion": PROMPT_MODEL_V3_SHAPE,
        "module": spec.module,
        "settingName": setting_name,
        "editable": editable,
        "modelSettingsSha256": model_settings_sha256(model),
        "models": [
            _model_slot(config, slot, accepted) for slot, accepted in zip(spec.models, model.steps, strict=True)
        ],
        "promptGroups": [_prompt_group(group, prompts[group.key]) for group in spec.groups],
        "limits": prompt_limits(),
        "fixed": list(fixed),
    }


# ── 판 규칙(AP1a — 판 목록·꼴은 모듈마다) ──

_VERSION_NUMBER = re.compile(r"v([1-9][0-9]*)")


def next_version_name(names: Iterable[str]) -> str:
    """회사 안 v<n> 의 가장 큰 n + 1. 판이 없으면 v1. 꼴 밖 이름(v0·v01·x)은 세지 않는다."""
    numbers = [int(m.group(1)) for name in names if (m := _VERSION_NUMBER.fullmatch(name)) is not None]
    return f"v{max(numbers, default=0) + 1}"


def version_status(applied: bool, applied_at: datetime | None) -> AiVersionStatus:
    """지금 적용 → applied, 적용한 적이 있고 지금 아님 → past, 한 번도 → testing."""
    if applied:
        return "applied"
    return "past" if applied_at is not None else "testing"


def ai_versions(
    *, setting_id: int | None, model: AcceptedModelSettings, prompts: AcceptedPrompts | None
) -> AiVersionsCommon:
    """실행 versions 의 공통 열쇠: aiSettingId(기본 판 None)·modelSettingsSha256, 저장 글 판이면 promptsSha256. prompts
    None(코드 글) 이면 그 열쇠를 싣지 않는다. 모듈 열쇠(글 sha 등)는 모듈이 더한다."""
    versions: AiVersionsCommon = {"aiSettingId": setting_id, "modelSettingsSha256": model_settings_sha256(model)}
    if prompts is not None:
        versions["promptsSha256"] = prompts_sha256(prompts)
    return versions
