"""데이터 검증 AI 설정 판의 모듈 선언과 프롬프트·모델 보기(ai.prompt-model@3 — 밴드 DVA1 ②, 결정 MARC-ENT-399·381·
387·372). 모델 칸 하나·프롬프트 묶음 셋(칸 여섯)·칸 key → 엔진 칸 표·기본 메모·출력절·읽기 전용 고정 값은 이 파일 한
곳이다. 꼴은 core/contracts/ai_setting_shapes.py 그대로, 받기·sha·조합·판 규칙은 core/calc/ai_settings.py 를 부른다.

- 모델 칸 하나(MODELS): 세 단계 공통(shared). 경로는 흐름 상수 colab_156.ROUTE 하나(처분 Q7), 도구 고리 칸(tool_loop
  — 세 단계 다 call_tools). 기본값은 흐름 상수(ROUTE·TEMPERATURE·MAX_OUTPUT_TOKENS)를 가리킨다 — 수 글자를 여기 박지
  않는다. webSearch 는 기본 true 로 고정이다(core 받기의 ai_model_web_search_fixed — 결정 372·303). 실행의
  web_search 는 칸 값이 아니라 binding 상수다.
- temperature 는 0~2 의 수(처분 Q6 — 기본 0.1). core 받기는 null 을 통과시키므로 accept_model 이 그 뒤에 core 꼴의
  거절(ai_model_temperature_range, 칸 key)을 더한다.
- 프롬프트 묶음 셋(GROUPS) · 칸 여섯(단계마다 지시 글·입력 글 — 처분 Q1): 이름·기본 메모는 시안 AD-02-DV_r1 의 글
  (처분 Q5 — 입력 글 칸은 메모 ""). promptId 는 그 단계의 core 프롬프트 id(engines prompts.PROMPT_IDS — 두 칸 같음),
  promptVersion 은 엔진 판(처분 R1). 받기는 core check_prompts 뒤에 입력 글 자리 지킴 하나(처분 Q3·Q4): 입력 글 셋은
  기본 글의 자리 전부(prompts.REQUIRED — ASCII 변형 글자도 그 자리)를 품어야 한다. 지시 글은 자리를 지워도 된다.
- 칸 key → 엔진 PromptTexts 칸(FIELDS)은 이 표 하나다(엔진은 칸 key 를 모른다). 저장 글은 texts_from 으로, 모델 값은
  models_from 으로 흐름 값이 된다.
- 출력절 = 기본 글에서 OUTPUT_MARKS[칸] 의 (머리, 끝 머리|None) 로 자른 바이트(계산 계획·인사이트 지시 글 둘만).
  저장 글이 그 절을 바이트 그대로 품지 않으면 outputKept false(화면 경고 — 저장은 안 막는다).
- 고정 값(fixed_groups)은 엔진·흐름 상수에서 읽는다(계산 도구 다섯·처리 값 넷). 함수로 늦게 짓는다(import 때 0).
  고정 규칙 글은 웹 모듈 글이다(처분 Q8).
- 순수하다: 설정(LlmConfig)은 부르는 쪽이 넘긴다(실제 파일 — service/selectors/ai_settings.RunModelSource).
"""

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from esgapi.dataverify.engines.colab_156 import prompts
from esgapi.dataverify.engines.colab_156.prompts import DEFAULT_TEXTS, PromptTexts
from esgapi.dataverify.flows import colab_156

MODULE: Final = "dataverify"

PROMPT_VERSION: Final = "colab_156"
"""칸의 promptVersion(엔진 판 — binding_156.ENGINE 과 같은 글자, 시험이 견준다). promptId 는 그 단계의 core 프롬프트
id(prompts.PROMPT_IDS — 봉투 prompts/<이름>/1.md, 지시 글·입력 글 두 칸 같음 — 처분 R1)."""

SLOT: Final = "shared"
"""모델 칸 key(세 단계 공통)."""

MODELS: Final[tuple[AiModelSlotSpec, ...]] = (
    AiModelSlotSpec(
        key=SLOT,
        label="세 단계 공통",
        routes=(colab_156.ROUTE,),
        tool_loop=True,
        default={
            "key": SLOT,
            "route": colab_156.ROUTE,
            "temperature": colab_156.TEMPERATURE,
            "webSearch": True,
            "maxOutputTokens": colab_156.MAX_OUTPUT_TOKENS,
        },
    ),
)

GROUPS: Final[tuple[AiPromptGroupSpec, ...]] = (
    AiPromptGroupSpec(key="plan", label="계산 계획", prompt_keys=("plan_system", "plan_user"), model_slots=(SLOT,)),
    AiPromptGroupSpec(
        key="review", label="계산 검토", prompt_keys=("review_system", "review_user"), model_slots=(SLOT,)
    ),
    AiPromptGroupSpec(
        key="insight", label="리스크 진단", prompt_keys=("insight_system", "insight_user"), model_slots=(SLOT,)
    ),
)

SPEC: Final = AiModuleSpec(module=MODULE, models=MODELS, groups=GROUPS)
LAYOUT: Final[PromptLayout] = layout_of(SPEC)

LABELS: Final[Mapping[str, str]] = {
    "plan_system": "지시 글",
    "plan_user": "입력 글",
    "review_system": "지시 글",
    "review_user": "입력 글",
    "insight_system": "지시 글",
    "insight_user": "입력 글",
}
"""칸 이름(서버 글 — 시안 AD-02-DV_r1). 묶음 이름이 단계를 말한다."""

FIELDS: Final[Mapping[str, str]] = {
    "plan_system": "plan_system",
    "plan_user": "plan_user",
    "review_system": "review_system",
    "review_user": "review_user",
    "insight_system": "insight_system",
    "insight_user": "insight_user",
}
"""칸 key → 엔진 PromptTexts 칸. 이 표 하나(엔진은 칸 key 를 모른다)."""

DEFAULT_MEMOS: Final[Mapping[str, str]] = {
    "plan_system": "모든 행을 차례로 한 번씩 보고 검증 산식만 세움 — 셈은 하지 않음",
    "plan_user": "",
    "review_system": "숫자는 계산 도구로만 셈, 계산할 수 없는 산식은 SKIP 으로 남김 · 표에 입력값·계산값·차이",
    "review_user": "",
    "insight_system": "데이터 품질·정보 리스크를 영역별 표로 10~20줄 — 근거 없는 가설 금지, 찾아본 곳은 출처를 밝힘",
    "insight_user": "",
}
"""저장 글 없는 판의 칸 메모 — 시안의 지시 글 메모, 입력 글은 빈 메모(처분 Q5)."""

OUTPUT_MARKS: Final[Mapping[str, tuple[str, str | None]]] = {
    "plan_system": ("출력 규칙:", "\n[툴 사용 및 스텝 제한 규칙]"),
    "insight_system": ("# 출력 형식", None),
}
"""출력 형식 절의 (머리, 끝 머리|None). 머리는 마지막 것, 절은 그 머리부터 끝 머리 앞까지(None 이면 글 끝까지).
나머지 칸(계산 검토 지시 글 — 시안 경고 없음 · 입력 글 셋)은 절이 없다."""

EDITABLE: Final[AiPromptModelEditable] = {"prompts": True, "model": True}
"""이 모듈이 새 판에 넣을 수 있는 것(모듈 능력 — 판의 상태 아님)."""

TOOLS: Final[tuple[tuple[str, str, str], ...]] = (
    ("sum", "두 값의 합", "합계 = 앞 값 + 뒤 값인지 연도마다 봐요"),
    ("sum_n", "여러 값의 합", "구성 항목을 더한 값이 합계와 맞는지 봐요"),
    ("ratio", "비율", "분자 ÷ 분모가 적힌 비율과 맞는지 봐요"),
    ("value_of", "값 찾기", "항목 이름·단위·연도로 값 하나를 읽어요"),
    ("search", "항목 찾기", "분류로 항목 목록을 쪽 나눠 읽어요"),
)
"""계산 도구 다섯(읽기 전용, 발주서 2-6): (key, 화면 이름, 설명)."""

TOOL_KINDS: Final[Mapping[str, tuple[str, ...]]] = {
    "sum": ("sum_check", "sum_check_by_name"),
    "sum_n": ("sum_n_check", "sum_n_check_by_names"),
    "ratio": ("ratio_check", "ratio_check_by_name"),
    "value_of": ("value_of_by_name",),
    "search": ("search_items",),
}
"""계산 도구 다섯 → 엔진 도구 이름(schemas.TOOLS_RESPONSES 의 여덟 — 합집합 = 여덟, 겹침 0. 시험이 견준다)."""


class ModelSettingsSource(Protocol):
    """모델 설정 받기·sha 의 원천(구현 service/selectors/ai_settings.RunModelSource — 판 저장·적용·prompt-model 과
    실행기의 끼움이 같은 것을 본다)."""

    def config(self) -> LlmConfig: ...

    def steps(self) -> Sequence[AiModelSlotSpec]: ...


@dataclass(frozen=True, slots=True)
class StageModel:
    """세 단계가 부르는 모델 값(받은 모델 칸 하나 — 흐름 DataverifyInputs 의 route·temperature·max_output_tokens)."""

    route: str
    temperature: float
    max_output_tokens: int


def accept_model(
    config: LlmConfig, given: AiModelSettingsIn, *, steps: Sequence[AiModelSlotSpec] = MODELS
) -> AcceptedModelSettings | ModelSettingRefused:
    """판의 모델 설정 받기 — core 받기 한 겹 + temperature null 거절(처분 Q6). given 은 꼴(AiModelSettingsIn)을 지난
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


def accept_prompts(given: AiPromptsIn) -> AcceptedPrompts | PromptRefused:
    """판의 프롬프트 글 받기 — core check_prompts 한 겹(layout = LAYOUT) + 입력 글 자리 지킴(처분 Q3·Q4 — 첫 빠진
    칸 하나, 그 칸의 첫 빠진 자리)."""
    found = check_prompts(given, layout=LAYOUT)
    if isinstance(found, PromptRefused):
        return found
    for i, step in enumerate(found.steps):
        for j, prompt in enumerate(step.prompts):
            missing = prompts.missing_slots(prompt.text, prompts.REQUIRED.get(FIELDS[prompt.key], ()))
            if missing:
                return PromptRefused(
                    "ai_prompt_placeholder_missing",
                    f"입력 글에서 {missing[0]} 자리를 지우면 안 돼요",
                    f"prompts.steps.{i}.prompts.{j}.text",
                )
    return found


def default_text(key: str) -> str:
    """칸의 기본 글(엔진 DEFAULT_TEXTS 의 그 칸 — 자리 글자 그대로)."""
    text: str = getattr(DEFAULT_TEXTS, FIELDS[key])
    return text


def output_section(key: str, text: str) -> str | None:
    """글의 출력 형식 절 — 그 칸 OUTPUT_MARKS 의 마지막 머리부터 끝 머리 앞(없으면 끝)까지. 절이 없는 칸이거나 머리가
    없으면 None."""
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
    """판의 저장 글(accept_prompts 를 지난 값) → 엔진 글 여섯. None(코드 글) 이면 DEFAULT_TEXTS 그대로."""
    if accepted is None:
        return DEFAULT_TEXTS
    return dataclasses.replace(
        DEFAULT_TEXTS, **{FIELDS[prompt.key]: prompt.text for step in accepted.steps for prompt in step.prompts}
    )


def models_from(accepted: AcceptedModelSettings) -> StageModel:
    """받은 모델 값(accept_model 이나 defaults 를 지난 값) → 세 단계의 경로·temperature·위끝."""
    (step,) = accepted.steps
    if step.temperature is None:  # accept_model·defaults 가 막는다(기본값은 흐름 상수)
        raise ValueError(f"모델 칸 {step.key} 의 temperature 가 없다")
    return StageModel(route=step.route, temperature=step.temperature, max_output_tokens=step.max_output_tokens)


def fixed_groups() -> list[AiFixedGroup]:
    """판과 무관한 읽기 전용 코드 값 둘(계산 도구 · 처리 값). 부를 때 짓는다."""
    return [
        {
            "key": "tools",
            "label": "계산 도구",
            "items": [{"key": key, "label": label, "value": text} for key, label, text in TOOLS],
        },
        {
            "key": "processing",
            "label": "처리 값",
            "items": [
                {"key": "tolerance", "label": "판정 허용 오차", "value": repr(prompts.TOLERANCE)},
                {"key": "plan_steps", "label": "계산 계획 걸음", "value": prompts.PLAN_MAX_STEPS},
                {
                    "key": "review_steps",
                    "label": "계산 검토 걸음",
                    "value": (f"산식 수 × {prompts.REVIEW_STEPS_PER_FORMULA} · {colab_156.REVIEW_MAX_STEPS_CAP} 까지"),
                },
                {"key": "insight_steps", "label": "리스크 진단 걸음", "value": prompts.INSIGHT_MAX_STEPS},
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
                    prompt_id=prompts.PROMPT_IDS[group.key],
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
