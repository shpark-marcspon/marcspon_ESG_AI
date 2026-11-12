"""영문번역 AI 설정 판의 모듈 선언과 프롬프트·모델 보기(ai.prompt-model@3 — 밴드 TR4 ②, 결정 MARC-ENT-399·381·387·
402). 모델 칸 셋·프롬프트 묶음 다섯(칸 열넷)·칸 key → 엔진 칸 표·기본 메모·출력절·읽기 전용 고정 값은 이 파일 한
곳이다. 꼴은 core/contracts/ai_setting_shapes.py 그대로, 받기·sha·조합·판 규칙은 core/calc/ai_settings.py 를 부른다.

- 모델 칸 셋(MODELS): 번역 · CEO 메시지(translate_ceo) · 번역 · 그 밖 파트(translate_other) · 검수(review). 칸이
  맡는 자리는 tools/llm_bridge.model_for 의 갈래다(역할 translate 는 파트가 ceo_message 면 앞 칸, 아니면 둘째 칸 —
  review 밖 아홉 자리. 역할 review 는 셋째 칸). 기본값은 llm_bridge.DEFAULT_MODELS(경로 상수 셋, 위끝 = 맡는 자리
  max_tokens 의 큰 값)를 가리킨다 — 수 글자를 여기 박지 않는다. 고리 단계가 아니다 → web_search 0.
- temperature 는 늘 null(R5 — MARC-ENT-402, 판 「temperature 는 보내지 않아요」). core 받기는 temperature 를 받는
  경로(gpt-4.1)에서 값을 통과시키므로 accept_model 이 그 뒤에 core 꼴의 거절(ai_model_temperature_unsupported, 칸
  key)을 더한다. 다른 규칙은 더하지 않는다. 보기도 routeChoices 의 acceptsTemperature 를 false 로 낸다(받기와 같은
  뜻 — MARC-ISSUE-372).
- 프롬프트 묶음 다섯(GROUPS) · 칸 열넷: 이름·기본 메모는 판 AD-02-TR_r1 의 글(R6). 받기는 core check_prompts 하나
  (layout = layout_of(SPEC)). 한 묶음 안 같은 글 둘은 받기가 거절한다(규칙 4) — 기본 글 열넷은 서로 다르다.
- 칸 key → 엔진 PromptTexts 칸(FIELDS)은 이 표 하나다(엔진은 칸 key 를 모른다 — tests/test_axes.py). 저장 글은
  texts_from 으로, 모델 값은 models_from 으로 엔진·다리 값이 된다.
- 출력절 = 기본 글의 마지막 OUTPUT_MARKS[칸] 부터 끝(범용 QA·검수 둘만). 저장 글이 그 절을 바이트 그대로 품지 않으면
  outputKept false(화면 경고 — 저장은 안 막는다).
- 고정 값(fixed_groups)은 엔진 상수에서 읽는다(처리 값 일곱·읽기 전용 글 넷). 함수로 늦게 짓는다(import 때 0).
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
    AiModelSlot,
    AiPromptEntry,
    AiPromptModel3,
    AiPromptModelEditable,
    AiPromptsIn,
)
from esgapi.core.llm.config import LlmConfig
from esgapi.translation.engines.colab_158 import gates, review_rules
from esgapi.translation.engines.colab_158 import prompts as engine_prompts
from esgapi.translation.engines.colab_158.texts import DEFAULT_TEXTS, PromptTexts
from esgapi.translation.tools.llm_bridge import (
    CEO_TRANSLATE_ROUTE,
    DEFAULT_MODELS,
    TRANSLATE_ROUTE,
    CallModel,
    TranslationModels,
)

MODULE: Final = "translation"

ROUTES: Final = (TRANSLATE_ROUTE, CEO_TRANSLATE_ROUTE)
"""칸 셋에 고를 수 있는 경로(화면 차례 — R3: light-openai-41·standard-openai-41, 그린워싱 JUDGE_ROUTES 와 같은 둘 —
다리의 경로 상수를 가리킨다, 이 파일에 경로 글자 0). 넓히는 길 = 이 줄 + 시험 셈 + 그 경로 실측 한 번
(MARC-ENT-262 안)."""

PROMPT_VERSION: Final = "colab_158"
"""칸의 promptVersion(엔진 판 — binding_158.ENGINE 과 같은 글자, 시험이 견준다). promptId 는 `translation/<칸 key>`
(글 열넷은 core 프롬프트 템플릿이 아니라 엔진 조립의 조각이다 — 발주서 2-1 추정)."""


def _slot(key: str, label: str, model: CallModel) -> AiModelSlotSpec:
    return AiModelSlotSpec(
        key=key,
        label=label,
        routes=ROUTES,
        tool_loop=False,
        default={
            "key": key,
            "route": model.route,
            "temperature": None,
            "webSearch": False,
            "maxOutputTokens": model.max_output_tokens,
        },
    )


MODELS: Final[tuple[AiModelSlotSpec, ...]] = (
    _slot("translate_ceo", "번역 · CEO 메시지", DEFAULT_MODELS.translate_ceo),
    _slot("translate_other", "번역 · 그 밖 파트", DEFAULT_MODELS.translate_other),
    _slot("review", "검수", DEFAULT_MODELS.review),
)
MODEL_FIELDS: Final[Mapping[str, str]] = {
    "translate_ceo": "translate_ceo",
    "translate_other": "translate_other",
    "review": "review",
}
"""모델 칸 key → TranslationModels 칸."""

_TRANSLATE_SLOTS: Final = ("translate_ceo", "translate_other")

GROUPS: Final[tuple[AiPromptGroupSpec, ...]] = (
    AiPromptGroupSpec(
        key="translate",
        label="번역",
        prompt_keys=(
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
        model_slots=_TRANSLATE_SLOTS,
    ),
    AiPromptGroupSpec(key="polish", label="윤문", prompt_keys=("polish",), model_slots=_TRANSLATE_SLOTS),
    AiPromptGroupSpec(key="editorial_qa", label="범용 QA", prompt_keys=("editorial_qa",), model_slots=_TRANSLATE_SLOTS),
    AiPromptGroupSpec(key="review", label="검수", prompt_keys=("review",), model_slots=("review",)),
    AiPromptGroupSpec(
        key="autofix", label="자동 수정", prompt_keys=("autofix", "autofix_korean"), model_slots=_TRANSLATE_SLOTS
    ),
)

SPEC: Final = AiModuleSpec(module=MODULE, models=MODELS, groups=GROUPS)
LAYOUT: Final[PromptLayout] = layout_of(SPEC)

LABELS: Final[Mapping[str, str]] = {
    "tone_ceo_message": "파트 톤 · CEO 메시지",
    "tone_story": "파트 톤 · 스토리",
    "tone_general": "파트 톤 · 일반",
    "style_a": "문체 A",
    "style_b": "문체 B",
    "style_rules": "문체·어휘 규칙",
    "subject_fragment_rules": "주어·짧은 글 규칙",
    "terminology_note": "용어 안내",
    "table_rules": "표 번역 규칙",
    "polish": "윤문",
    "editorial_qa": "범용 QA",
    "review": "검수",
    "autofix": "자동 수정",
    "autofix_korean": "자동 수정 뒤 한국어 보정",
}
"""칸 이름(서버 글 — 판 AD-02-TR_r1, MARC-ENT-384)."""

FIELDS: Final[Mapping[str, str]] = {
    "tone_ceo_message": "ceo_message_tone",
    "tone_story": "story_tone",
    "tone_general": "general_tone",
    "style_a": "style_a",
    "style_b": "style_b",
    "style_rules": "style_rules",
    "subject_fragment_rules": "subject_fragment_rules",
    "terminology_note": "terminology_note",
    "table_rules": "table_rules",
    "polish": "polish",
    "editorial_qa": "editorial_qa",
    "review": "review",
    "autofix": "autofix",
    "autofix_korean": "autofix_korean",
}
"""칸 key → 엔진 PromptTexts 칸. 이 표 하나(엔진은 칸 key 를 모른다)."""

DEFAULT_MEMOS: Final[Mapping[str, str]] = {
    "tone_ceo_message": "CEO·의장 메시지 파트의 톤 — 번역이 아니라 대표 서한으로 다시 쓰는 편집 지침",
    "tone_story": "회사 소개·전략·사례 같은 서술 파트의 톤",
    "tone_general": "성과 데이터·KPI·부록 같은 일반 파트의 톤 — 정확성과 검증 가능성 우선",
    "style_a": "표준 전문 문체 — A·B 비교를 끄면 이 문체 하나로 옮겨요",
    "style_b": "미국 원어민 문체 — A·B 비교를 켜면 A 와 함께 두 번 옮겨요",
    "style_rules": "보고서 문체·낱말 가드레일·기계번역 티 빼기·용어 일관·숫자 단위 규칙 — 그 파트 톤 앞에 붙어요",
    "subject_fragment_rules": "주어(회사 이름 → we)와 제목·표·차트 같은 짧은 글을 옮기는 규칙 — 그 파트 톤 뒤에 붙어요",
    "terminology_note": "용어집 값을 그대로 쓰는 규칙 — 고른 문체 앞에 붙어요",
    "table_rules": "표 칸 조각을 JSON 으로 받고 돌려주는 규칙 — 24칸씩 묶어 보내요",
    "polish": "국문과 영문 초안을 함께 보고 출판용 영문으로 다듬기 — 사실·숫자·용어집 낱말은 그대로",
    "editorial_qa": "0~100점과 이슈를 매기고 필요하면 고친 글을 내는 관문 — 96점 아래면 고친 글을 써요",
    "review": "원어민 교정자 관점의 이슈 열 가지와 심각도 — 결과의 이슈 목록과 검수 Word 의 바탕",
    "autofix": "검수 이슈만 고치기 — 쪽 전체를 다시 쓰지 않음",
    "autofix_korean": "자동 수정 뒤에도 한국어가 남은 쪽만 한 번 더",
}
"""저장 글 없는 판의 칸 메모 — 판 AD-02-TR_r1 의 「기본 메모 예시」 글(R6)."""

OUTPUT_MARKS: Final[Mapping[str, str]] = {
    "editorial_qa": "Return JSON only:",
    "review": "## Output",
}
"""출력 형식 절 머리(그 칸의 기본 글에 하나씩 — 마지막 것부터 끝이 절). 나머지 칸은 절이 없다."""

EDITABLE: Final[AiPromptModelEditable] = {"prompts": True, "model": True}
"""이 모듈이 새 판에 넣을 수 있는 것(모듈 능력 — 판의 상태 아님)."""

PROCESSING: Final[tuple[tuple[str, str, int], ...]] = (
    ("editorial_qa_min_score", "범용 QA 통과 점수", gates.GENERIC_EDITORIAL_QA_MIN_SCORE),
    ("editorial_qa_soft_score", "범용 QA 약한 이슈 점수", gates.GENERIC_EDITORIAL_QA_SOFT_SCORE),
    ("polish_min_chars", "윤문 최소 글자", gates.EDITORIAL_POLISH_MIN_CHARS),
    ("polish_max_chars", "윤문 최대 글자", gates.EDITORIAL_POLISH_MAX_CHARS),
    ("korean_repair_rounds", "한국어 다시 번역", gates.MAX_UNTRANSLATED_REPAIR_ROUNDS),
    ("autofix_korean_rounds", "자동 수정 뒤 보정", review_rules.PART_QA_AUTOFIX_MAX_KOREAN_REPAIR_ROUNDS),
    ("table_batch_size", "표 묶음", gates.TABLE_BATCH_SIZE),
)
"""처리 값(읽기 전용, 발주서 2-6): (key, 화면 이름, 엔진 상수). 수 글자를 여기 박지 않는다."""


class ModelSettingsSource(Protocol):
    """모델 설정 받기·sha 의 원천(구현 service/selectors/ai_settings.RunModelSource — 판 저장·적용·prompt-model 과
    실행기의 끼움이 같은 것을 본다)."""

    def config(self) -> LlmConfig: ...

    def steps(self) -> Sequence[AiModelSlotSpec]: ...


def accept_model(
    config: LlmConfig, given: AiModelSettingsIn, *, steps: Sequence[AiModelSlotSpec] = MODELS
) -> AcceptedModelSettings | ModelSettingRefused:
    """판의 모델 설정 받기 — core 받기 한 겹 + temperature 는 늘 null(R5). given 은 꼴(AiModelSettingsIn)을 지난 값."""
    found = check_model_settings(config, given, steps=steps)
    if isinstance(found, ModelSettingRefused):
        return found
    for step in found.steps:
        if step.temperature is not None:
            return ModelSettingRefused(
                "ai_model_temperature_unsupported", "이 모델은 temperature 를 바꿀 수 없어요", step.key
            )
    return found


def accept_prompts(given: AiPromptsIn) -> AcceptedPrompts | PromptRefused:
    """판의 프롬프트 글 받기 — core check_prompts 한 겹, layout = LAYOUT."""
    return check_prompts(given, layout=LAYOUT)


def default_text(key: str) -> str:
    """칸의 기본 글(엔진 DEFAULT_TEXTS 의 그 칸)."""
    text: str = getattr(DEFAULT_TEXTS, FIELDS[key])
    return text


def output_section(key: str, text: str) -> str | None:
    """글의 출력 형식 절 — 그 칸 OUTPUT_MARKS 의 마지막 자리부터 끝. 절이 없는 칸이거나 머리가 없으면 None."""
    mark = OUTPUT_MARKS.get(key)
    at = -1 if mark is None else text.rfind(mark)
    return None if at < 0 else text[at:]


def texts_from(accepted: AcceptedPrompts | None) -> PromptTexts:
    """판의 저장 글(accept_prompts 를 지난 값) → 엔진 글 열넷. None(코드 글) 이면 DEFAULT_TEXTS 그대로."""
    if accepted is None:
        return DEFAULT_TEXTS
    return dataclasses.replace(
        DEFAULT_TEXTS, **{FIELDS[prompt.key]: prompt.text for step in accepted.steps for prompt in step.prompts}
    )


def models_from(accepted: AcceptedModelSettings) -> TranslationModels:
    """받은 모델 값(accept_model 이나 defaults 를 지난 값) → 다리의 칸 셋(경로·위끝)."""
    slots = {step.key: CallModel(step.route, step.max_output_tokens) for step in accepted.steps}
    return TranslationModels(**{MODEL_FIELDS[key]: model for key, model in slots.items()})


def fixed_groups() -> list[AiFixedGroup]:
    """판과 무관한 읽기 전용 코드 값 둘(처리 값 · 읽기 전용 글). 부를 때 짓는다."""
    return [
        {
            "key": "processing",
            "label": "처리 값",
            "items": [{"key": key, "label": label, "value": value} for key, label, value in PROCESSING],
        },
        {
            "key": "readonly_prompts",
            "label": "고정 글",
            "items": [
                {
                    "key": "base_system",
                    "label": "바탕 지시",
                    "value": engine_prompts.base_system_prompt("{industry_standards}"),
                },
                {
                    "key": "glossary_repair_rules",
                    "label": "용어집 보정 규칙",
                    "value": [engine_prompts.GLOSSARY_REPAIR_TABLE_RULE, engine_prompts.GLOSSARY_REPAIR_STRUCTURE_RULE],
                },
                {
                    "key": "korean_repair_rules",
                    "label": "한국어 보정 규칙",
                    "value": [engine_prompts.KOREAN_REPAIR_TABLE_RULE, engine_prompts.KOREAN_REPAIR_STRUCTURE_RULE],
                },
                {
                    "key": "critical_repair_mode",
                    "label": "보정 강화 모드",
                    "value": engine_prompts.CRITICAL_REPAIR_MODE,
                },
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
                    prompt_id=f"{MODULE}/{key}",
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
    칸의 고른 경로를 지금 쓸 수 없으면 compose 의 LlmConfigError(배포 잘못 — MARC-ISSUE-280 Q4)."""
    body = compose(
        config,
        SPEC,
        setting_name=setting_name,
        editable=EDITABLE,
        model=model,
        prompts=_entries(prompts),
        fixed=fixed_groups(),
    )
    return {**body, "models": [_without_temperature(slot) for slot in body["models"]]}


def _without_temperature(slot: AiModelSlot) -> AiModelSlot:
    """칸의 routeChoices 를 acceptsTemperature false 로(R5 — 받기가 늘 거절하니 보기도 「–」). 새 dict."""
    return {**slot, "routeChoices": [{**choice, "acceptsTemperature": False} for choice in slot["routeChoices"]]}
