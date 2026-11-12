"""원고작성 AI 설정 판의 모듈 선언과 프롬프트·모델 보기(ai.prompt-model@3 — 밴드 RPA1 ①, 결정 MARC-ENT-399·381·
387·514). 모델 칸 둘·프롬프트 묶음 둘(칸 넷)·칸 key → 엔진 칸 표·기본 메모·자리 지킴·읽기 전용 고정 값은 이 파일 한
곳이다. 꼴은 core/contracts/ai_setting_shapes.py 그대로, 받기·sha·조합·판 규칙은 core/calc/ai_settings.py 를 부른다
(dataverify flows/prompt_model_156.py · materiality flows/prompt_model_155.py 의 꼴 — 판별 복사, 모듈끼리 import 0).

- 모델 칸 둘(MODELS — 처분 ①②③): map 「목차 달기」·draft 「초안 짓기」(판 말 — RPA4, 웹이 「모델」을 붙인다).
  경로는 칸마다 ROUTES(mini·4.1),
  기본은 흐름 상수 draft_v2.ROUTE. 도구 고리 없음(tool_loop False — 두 단계 다 call 하나). 기본값은 흐름 상수(ROUTE·
  TEMPERATURE·MAX_OUTPUT_TOKENS)를 가리킨다 — 수 글자를 여기 박지 않는다. webSearch 는 false 고정(core 받기의
  ai_model_web_search_fixed).
- temperature 는 0~2 의 수(처분 ③ — 흐름은 늘 싣는다). core 받기는 null 을 통과시키므로 accept_model 이 그 뒤에 core
  꼴의 거절(ai_model_temperature_range, 칸 key)을 더한다.
- 프롬프트 묶음 둘(GROUPS) · 칸 넷(단계마다 지시 글·입력 글): promptId 는 그 단계의 core 프롬프트 id(draft_v2.
  PROMPT_IDS — 두 칸 같음), promptVersion 은 엔진 판. 받기는 core check_prompts 뒤에 입력 글 자리 지킴 하나(처분 ⑥):
  입력 글 둘은 기본 글의 자리 전부(REQUIRED)를 품어야 한다. 지시 글은 자리가 없다(끼움 없음 — engines/v2/prompts).
- 칸 key → 엔진 PromptTexts 칸(FIELDS)은 이 표 하나다(엔진은 칸 key 를 모른다). 저장 글은 texts_from 으로 흐름 값이
  된다. 표지 규칙(MARKER_RULES)은 칸 밖 고정 꼬리다 — 저장 draft_system 뒤에도 흐름이 붙인다(처분 ⑦).
- 출력절은 없다(OUTPUT_MARKS 빈 표 — 답 꼴은 흐름의 JSON 스키마가 정한다).
- 고정 값(fixed_groups)은 엔진·흐름 상수에서 읽는다(표지 규칙 · 실행 규칙 — 처분 ⑦). 함수로 늦게 짓는다.
- 받은 모델 값은 models_from 으로 흐름 입력 칸(draft_v2.StageModels — 칸 key map·draft)이 된다(RPA1 ②).
- 순수하다: 설정(LlmConfig)은 부르는 쪽이 넘긴다(실제 파일 — service/selectors/ai_settings.RunModelSource).
"""

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Final, Protocol

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AcceptedPrompts,
    AiModelSlotSpec,
    AiModuleSpec,
    AiPromptGroupSpec,
    ModelSettingRefused,
    PromptLayout,
    PromptRefused,
    check_model_settings,
    check_prompts,
    compose,
    layout_of,
    prompt_entry,
)
from esgapi.core.contracts.ai_setting_shapes import (
    AiFixedGroup,
    AiModelSettingsIn,
    AiPromptEntry,
    AiPromptModel3,
    AiPromptModelEditable,
    AiPromptsIn,
)
from esgapi.core.llm.config import LlmConfig
from esgapi.drafting.engines.v1 import pages
from esgapi.drafting.engines.v2 import material
from esgapi.drafting.engines.v2.texts import (
    DEFAULT_TEXTS,
    MARKER_RULES,
    OUTLINE_SLOT,
    PAGES_SLOT,
    REQUIREMENT_SLOT,
    TITLE_SLOT,
    WRITING_RULES,
    PromptTexts,
)
from esgapi.drafting.flows import draft_v2

MODULE: Final = "drafting"

PROMPT_VERSION: Final = "v2"
"""칸의 promptVersion(엔진 판 — binding_v2.ENGINE 과 같은 글자, 시험이 견준다)."""

MAP: Final = "map"
DRAFT: Final = "draft"

ROUTES: Final = (draft_v2.ROUTE, "standard-openai-41")
"""칸마다 고를 수 있는 경로(처분 ② — mini·4.1, 차례 = 화면 차례). 기본은 draft_v2.ROUTE(첫째). 돈은 흐름의 위끝 가드
(DRAFTING_RUN_MAX_USD) 그대로다."""


def _slot(key: str, label: str) -> AiModelSlotSpec:
    return AiModelSlotSpec(
        key=key,
        label=label,
        routes=ROUTES,
        tool_loop=False,
        default={
            "key": key,
            "route": draft_v2.ROUTE,
            "temperature": draft_v2.TEMPERATURE,
            "webSearch": False,
            "maxOutputTokens": draft_v2.MAX_OUTPUT_TOKENS,
        },
    )


MODELS: Final[tuple[AiModelSlotSpec, ...]] = (
    _slot(MAP, "목차 달기"),
    _slot(DRAFT, "초안 짓기"),
)

GROUPS: Final[tuple[AiPromptGroupSpec, ...]] = (
    AiPromptGroupSpec(key=MAP, label="목차 달기", prompt_keys=("map_system", "map_user"), model_slots=(MAP,)),
    AiPromptGroupSpec(key=DRAFT, label="초안 짓기", prompt_keys=("draft_system", "draft_user"), model_slots=(DRAFT,)),
)

SPEC: Final = AiModuleSpec(module=MODULE, models=MODELS, groups=GROUPS)
LAYOUT: Final[PromptLayout] = layout_of(SPEC)

LABELS: Final[Mapping[str, str]] = {
    "map_system": "지시 글",
    "map_user": "입력 글",
    "draft_system": "지시 글",
    "draft_user": "입력 글",
}
"""칸 이름(서버 글). 묶음 이름이 단계를 말한다."""

FIELDS: Final[Mapping[str, str]] = {key: key for key in LABELS}
"""칸 key → 엔진 PromptTexts 칸(같은 이름). 이 표 하나(엔진은 칸 key 를 모른다)."""

DEFAULT_MEMOS: Final[Mapping[str, str]] = {
    "map_system": "페이지마다 그 내용이 쓰일 목차 잎 key 를 고름 — 목록에 없는 key 는 쓰지 않음",
    "map_user": "",
    "draft_system": "자료에 적힌 사실만으로 개조식 bullet · bullet 마다 근거 블록과 문장을 닮",
    "draft_user": "",
}
"""저장 글 없는 판의 칸 메모 — 지시 글 둘에 기본 메모, 입력 글은 빈 메모(처분 ⑧)."""

OUTPUT_MARKS: Final[Mapping[str, tuple[str, str | None]]] = {}
"""출력 형식 절의 (머리, 끝 머리|None). 원고작성 칸에는 절이 없다(답 꼴은 흐름의 JSON 스키마)."""

PLACEHOLDERS: Final[Mapping[str, tuple[str, ...]]] = {
    "map_system": (),
    "map_user": (OUTLINE_SLOT, PAGES_SLOT),
    "draft_system": (),
    "draft_user": (TITLE_SLOT, REQUIREMENT_SLOT, PAGES_SLOT),
}
"""칸 → 기본 글의 자리(engines/v2/prompts.map_texts·draft_texts 가 끼우는 것 — v2 슬롯, 재료 자리 `{페이지 글}`).
지시 글은 끼움이 없다."""

REQUIRED: Final[Mapping[str, tuple[str, ...]]] = {key: slots for key, slots in PLACEHOLDERS.items() if slots}
"""입력 글 둘 → 지켜야 하는 자리(처분 ⑥ — 기본 글의 자리 전부. 지우면 재료가 안 실린다)."""

EDITABLE: Final[AiPromptModelEditable] = {"prompts": True, "model": True}
"""이 모듈이 새 판에 넣을 수 있는 것(모듈 능력 — 판의 상태 아님)."""


class ModelSettingsSource(Protocol):
    """모델 설정 받기·sha 의 원천(구현 service/selectors/ai_settings.RunModelSource — 판 저장·적용·prompt-model 과
    실행기의 끼움이 같은 것을 본다)."""

    def config(self) -> LlmConfig: ...

    def steps(self) -> Sequence[AiModelSlotSpec]: ...


def accept_model(
    config: LlmConfig, given: AiModelSettingsIn, *, steps: Sequence[AiModelSlotSpec] = MODELS
) -> AcceptedModelSettings | ModelSettingRefused:
    """판의 모델 설정 받기 — core 받기 한 겹 + temperature null 거절(처분 ③). given 은 꼴(AiModelSettingsIn)을 지난
    값."""
    found = check_model_settings(config, given, steps=steps)
    if isinstance(found, ModelSettingRefused):
        return found
    for step in found.steps:
        if step.temperature is None:
            return ModelSettingRefused(
                "ai_model_temperature_range", "temperature 는 0~2 사이 수로 넣어 주세요", step.key
            )
    return found


def missing_slots(text: str, slots: Sequence[str]) -> list[str]:
    """`slots` 중 `text` 에 나오지 않는 자리(차례 그대로). 끼움(engines/v2/prompts — v1 render)은 자리 글자
    그대로만 본다."""
    return [slot for slot in slots if slot not in text]


def accept_prompts(given: AiPromptsIn) -> AcceptedPrompts | PromptRefused:
    """판의 프롬프트 글 받기 — core check_prompts 한 겹(layout = LAYOUT) + 입력 글 자리 지킴(처분 ⑥ — 첫 빠진 칸 하나,
    그 칸의 첫 빠진 자리)."""
    found = check_prompts(given, layout=LAYOUT)
    if isinstance(found, PromptRefused):
        return found
    for i, step in enumerate(found.steps):
        for j, prompt in enumerate(step.prompts):
            missing = missing_slots(prompt.text, REQUIRED.get(FIELDS[prompt.key], ()))
            if missing:
                return PromptRefused(
                    "ai_prompt_placeholder_missing",
                    f"입력 글에서 {missing[0]} 자리를 지우면 안 돼요",
                    f"prompts.steps.{i}.prompts.{j}.text",
                )
    return found


def default_text(key: str) -> str:
    """칸의 기본 글(엔진 v2 DEFAULT_TEXTS 의 그 칸 — 자리 글자 그대로)."""
    text: str = getattr(DEFAULT_TEXTS, FIELDS[key])
    return text


def output_section(key: str, text: str) -> str | None:
    """글의 출력 형식 절 — 그 칸 OUTPUT_MARKS 의 마지막 머리부터 끝 머리 앞(없으면 끝)까지. 절이 없는 칸이거나 머리가
    없으면 None(원고작성은 늘 None)."""
    mark = OUTPUT_MARKS.get(key)
    if mark is None:
        return None
    head, end = mark
    at = text.rfind(head)
    if at < 0:
        return None
    stop = -1 if end is None else text.find(end, at)
    return text[at:] if stop < 0 else text[at:stop]


def texts_from(accepted: AcceptedPrompts | None) -> PromptTexts:
    """판의 저장 글(accept_prompts 를 지난 값) → 엔진 글 넷. None(코드 글) 이면 v2 DEFAULT_TEXTS 그대로."""
    if accepted is None:
        return DEFAULT_TEXTS
    return dataclasses.replace(
        DEFAULT_TEXTS, **{FIELDS[prompt.key]: prompt.text for step in accepted.steps for prompt in step.prompts}
    )


def models_from(accepted: AcceptedModelSettings) -> draft_v2.StageModels:
    """받은 모델 값(accept_model 이나 defaults 를 지난 값) → S2·S3 의 경로·temperature·위끝(칸 key 로 고름)."""
    found: dict[str, draft_v2.StageModel] = {}
    for step in accepted.steps:
        if step.temperature is None:  # accept_model·defaults 가 막는다(기본값은 흐름 상수)
            raise ValueError(f"모델 칸 {step.key} 의 temperature 가 없다")
        found[step.key] = draft_v2.StageModel(
            route=step.route, temperature=step.temperature, max_output_tokens=step.max_output_tokens
        )
    return draft_v2.StageModels(map=found[MAP], draft=found[DRAFT])


def fixed_groups() -> list[AiFixedGroup]:
    """판과 무관한 읽기 전용 코드 값 둘(근거 표지·글 규칙 · 실행 규칙 — 처분 ⑦ · RPQ1). 부를 때 짓는다."""
    return [
        {
            "key": "rules",
            "label": "근거 표지·글 규칙",
            "items": [
                {"key": "markers", "label": "자료 표지", "value": MARKER_RULES},
                {"key": "writing", "label": "글 규칙", "value": WRITING_RULES},
            ],
        },
        {
            "key": "processing",
            "label": "실행 규칙",
            "items": [
                {"key": "page_max_chars", "label": "페이지 글 상한(자)", "value": pages.PAGE_MAX_CHARS},
                {"key": "batch_max_chars", "label": "페이지 묶음 상한(자)", "value": pages.BATCH_MAX_CHARS},
                {"key": "material_max_chars", "label": "초안 재료 전체 상한(자)", "value": material.MATERIAL_MAX_CHARS},
                {"key": "timeout_ms", "label": "호출 시간 상한(밀리초)", "value": draft_v2.TIMEOUT_MS},
            ],
        },
    ]


def _entries(saved: AcceptedPrompts | None) -> dict[str, list[AiPromptEntry]]:
    """묶음 key → 칸. 저장 글(saved)이 있으면 그 글·메모, 없으면 기본 글과 DEFAULT_MEMOS."""
    stored = {} if saved is None else {(s.key, p.key): p for s in saved.steps for p in s.prompts}
    entries: dict[str, list[AiPromptEntry]] = {}
    for group in GROUPS:
        entries[group.key] = []
        for key in group.prompt_keys:
            base = default_text(key)
            found = stored.get((group.key, key))
            entries[group.key].append(
                prompt_entry(
                    key=key,
                    label=LABELS[key],
                    prompt_id=draft_v2.PROMPT_IDS[group.key],
                    prompt_version=PROMPT_VERSION,
                    text=base if found is None else found.text,
                    memo=DEFAULT_MEMOS[key] if found is None else found.memo,
                    default_text=base,
                    output_section=output_section(key, base),
                )
            )
    return entries


def prompt_model(
    config: LlmConfig, *, setting_name: str, model: AcceptedModelSettings, prompts: AcceptedPrompts | None = None
) -> AiPromptModel3:
    """한 판의 ai.prompt-model@3 — core compose(fixed = fixed_groups()). model 은 받기를 지난 값(기본 판은
    defaults(config, MODELS), 저장 판은 accept_model(config, 저장 값)), prompts 는 판의 저장 글(None = 코드 글).
    칸의 고른 경로를 지금 쓸 수 없으면 compose 의 LlmConfigError(배포 잘못)."""
    return compose(
        config,
        SPEC,
        setting_name=setting_name,
        editable=EDITABLE,
        model=model,
        prompts=_entries(prompts),
        fixed=fixed_groups(),
    )
