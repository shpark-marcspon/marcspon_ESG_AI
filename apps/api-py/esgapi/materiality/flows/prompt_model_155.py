"""중대성평가 IRO AI 설정 판의 모듈 선언과 프롬프트·모델 보기(ai.prompt-model@3 — 밴드 IR4 ②, 결정 MARC-ENT-399·381·
387·372). 모델 칸 둘·프롬프트 묶음 여섯(칸 열넷)·칸 key → 엔진 칸 표·기본 메모·출력절·읽기 전용 고정 값은 이 파일 한
곳이다. 꼴은 core/contracts/ai_setting_shapes.py 그대로, 받기·sha·조합·판 규칙은 core/calc/ai_settings.py 를 부른다
(dataverify flows/prompt_model_156.py 의 꼴 — 넷째 모듈, sid:MARC-ISSUE-369).

- 칸 열넷(밴드 IRA3 — 결정 MARC-ENT-569): 1부 가변 입력 셋(regulation_input·keywords_input·controversy_input)은
  판 칸이 아니다 — 엔진 칸은 열일곱 그대로이고 그 셋은 늘 기본 글(FIELDS 열넷). 옛 판(칸 열일곱)은 읽는 자리에서
  accept_stored 가 셋을 떼고, IRA3 앞 실행의 sha 는 legacy_sha256 이 잰다. 저장 POST 는 accept_prompts(열넷만).
- 모델 칸 둘(MODELS — 처분 Q8~Q11): research 「리서치 모델」(1부 규제·키워드·사건, 경로 colab_155.ROUTE 하나)과
  analysis 「분석 모델」(2부 영향·재무·경로, part2_155.ROUTE_PART2 하나). 둘 다 도구 고리 칸(1부는 늘 call_tools, 2부는
  latestEventMode 참이면 — 처분 Q10). 기본값은 흐름의 코드 값(colab_155.CODE_RESEARCH·part2_155.CODE_ANALYSIS)
  을 가리킨다 — 수 글자를 여기 박지 않는다. webSearch 는 받기 고정값(research true · analysis false)일 뿐
  흐름이 읽지 않는다 (web_search 는 흐름 고정 — 결정 372·425).
- temperature(처분 Q9): research 는 0~2 의 수(core 받기는 null 을 통과시키므로 accept_model 이 그 뒤에 core 꼴의
  ai_model_temperature_range 를 더한다), analysis 는 null 만(2부는 코랩대로 temperature 를 싣지 않는다 — 값이면 core
  code ai_model_temperature_unsupported 그대로, 새 code 0).
- 프롬프트 묶음 여섯(GROUPS — 처분 Q2) · 칸 열넷(1부 호출마다 지시 글·입력 글, 2부 지시 글·입력 글, 신뢰
  출처 목록 비금융·금융 — 처분 Q1·Q3). promptId 는 그 칸 호출 단계의 core 프롬프트 id(신뢰 출처 칸은 규제 단계),
  promptVersion 은 엔진 판. 받기는 core check_prompts 뒤에 자리 지킴 하나(처분 Q5·Q6): texts.REQUIRED(날 글 칸은 기본
  글의 자리 전부, 규제 지시 글은 {신뢰 출처 목록}). 그 밖 칸은 통째로 바꿔도 된다.
- 칸 key → 엔진 PromptTexts 칸(FIELDS)은 이 표 하나다(엔진은 칸 key 를 모른다). 저장 글은 texts_from 으로, 모델 값은
  models_from 으로 흐름 값이 된다.
- 출력절 = 기본 글에서 OUTPUT_MARKS[칸] 의 (머리, 끝 머리|None) 로 자른 바이트. 저장 글이 그 절을 바이트 그대로 품지
  않으면 outputKept false(화면 경고 — 저장은 안 막는다).
- 고정 값(fixed_groups)은 엔진·흐름 상수에서 읽는다(웹 검색 둘 · 실행 규칙 — 처분 Q12). 함수로 늦게 짓는다.
  비용 상한도 흐름 colab_155 에서 읽는다 — binding_155 는 import 하지 않는다(MARC-ISSUE-412 ①).
- 순수하다: 설정(LlmConfig)은 부르는 쪽이 넘긴다(실제 파일 — service/selectors/ai_settings.RunModelSource).
"""

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Final, Protocol

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AcceptedPrompt,
    AcceptedPrompts,
    AcceptedPromptStep,
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
    prompts_sha256,
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
from esgapi.materiality.engines.colab_155 import constants, texts
from esgapi.materiality.engines.colab_155.texts import DEFAULT_TEXTS, PromptTexts
from esgapi.materiality.flows import colab_155, part2_155
from esgapi.materiality.flows.colab_155 import StageModel

MODULE: Final = "materiality"

PROMPT_VERSION: Final = "colab_155"
"""칸의 promptVersion(엔진 판 — binding_155.ENGINE 과 같은 글자, 시험이 견준다)."""

RESEARCH: Final = "research"
ANALYSIS: Final = "analysis"


def _slot(key: str, label: str, model: StageModel, *, web_search: bool) -> AiModelSlotSpec:
    return AiModelSlotSpec(
        key=key,
        label=label,
        routes=(model.route,),
        tool_loop=True,
        default={
            "key": key,
            "route": model.route,
            "temperature": model.temperature,
            "webSearch": web_search,
            "maxOutputTokens": model.max_output_tokens,
        },
    )


MODELS: Final[tuple[AiModelSlotSpec, ...]] = (
    _slot(RESEARCH, "리서치 모델", colab_155.CODE_RESEARCH, web_search=True),
    _slot(ANALYSIS, "분석 모델", part2_155.CODE_ANALYSIS, web_search=False),
)

GROUPS: Final[tuple[AiPromptGroupSpec, ...]] = (
    AiPromptGroupSpec(
        key="regulation",
        label="규제·정책 리서치",
        prompt_keys=("regulation_system", "regulation_prefix"),
        model_slots=(RESEARCH,),
    ),
    AiPromptGroupSpec(
        key="controversy",
        label="컨트로버시 리서치",
        prompt_keys=("keywords_system", "keywords_prefix", "controversy_system", "controversy_prefix"),
        model_slots=(RESEARCH,),
    ),
    AiPromptGroupSpec(
        key="impact",
        label="환경·사회 영향 정의",
        prompt_keys=("impact_system", "impact_input"),
        model_slots=(ANALYSIS,),
    ),
    AiPromptGroupSpec(
        key="financial",
        label="재무 영향 정의",
        prompt_keys=("financial_system", "financial_input"),
        model_slots=(ANALYSIS,),
    ),
    AiPromptGroupSpec(
        key="pathway",
        label="재무 영향 경로",
        prompt_keys=("pathway_system", "pathway_input"),
        model_slots=(ANALYSIS,),
    ),
    AiPromptGroupSpec(
        key="whitelist",
        label="신뢰 출처 목록",
        prompt_keys=("whitelist_non_financial", "whitelist_financial"),
        model_slots=(RESEARCH,),
    ),
)

SPEC: Final = AiModuleSpec(module=MODULE, models=MODELS, groups=GROUPS)
LAYOUT: Final[PromptLayout] = layout_of(SPEC)

LABELS: Final[Mapping[str, str]] = {
    "regulation_system": "지시 글",
    "regulation_prefix": "입력 글",
    "keywords_system": "키워드 지시",
    "keywords_prefix": "키워드 입력",
    "controversy_system": "이슈 지시",
    "controversy_prefix": "이슈 입력",
    "impact_system": "지시 글",
    "impact_input": "입력 글",
    "financial_system": "지시 글",
    "financial_input": "입력 글",
    "pathway_system": "지시 글",
    "pathway_input": "입력 글",
    "whitelist_non_financial": "비금융",
    "whitelist_financial": "금융",
}
"""칸 이름(서버 글 — 시안 AD-02-IR_r1 · 처분 Q1). 묶음 이름이 단계를 말한다."""

FIELDS: Final[Mapping[str, str]] = {key: key for key in LABELS}
"""칸 key → 엔진 PromptTexts 칸(같은 이름 — 열넷). 이 표 하나(엔진은 칸 key 를 모른다). 엔진 칸 셋(regulation_input·
keywords_input·controversy_input)은 이 표에 없어 늘 엔진 기본 글이다(MARC-ENT-569 — 되돌리지 말 것)."""

LEGACY_KEYS: Final[Mapping[str, frozenset[str]]] = {
    "regulation": frozenset({"regulation_input"}),
    "controversy": frozenset({"keywords_input", "controversy_input"}),
}
"""단계 key → 옛 판(칸 열일곱 — IRA3 앞)에만 있던 칸. 저장된 판을 읽는 자리(accept_stored)에서 그 단계에서만 뗀다."""

PROMPT_IDS: Final[Mapping[str, str]] = {
    "regulation_system": colab_155.PROMPT_IDS["regulation"],
    "regulation_prefix": colab_155.PROMPT_IDS["regulation"],
    "keywords_system": colab_155.PROMPT_IDS["keywords"],
    "keywords_prefix": colab_155.PROMPT_IDS["keywords"],
    "controversy_system": colab_155.PROMPT_IDS["controversy"],
    "controversy_prefix": colab_155.PROMPT_IDS["controversy"],
    "impact_system": part2_155.PROMPT_IDS2["impact"],
    "impact_input": part2_155.PROMPT_IDS2["impact"],
    "financial_system": part2_155.PROMPT_IDS2["financial"],
    "financial_input": part2_155.PROMPT_IDS2["financial"],
    "pathway_system": part2_155.PROMPT_IDS2["pathway"],
    "pathway_input": part2_155.PROMPT_IDS2["pathway"],
    "whitelist_non_financial": colab_155.PROMPT_IDS["regulation"],
    "whitelist_financial": colab_155.PROMPT_IDS["regulation"],
}
"""칸 → 그 칸이 실리는 호출 단계의 core 프롬프트 id(신뢰 출처 칸은 규제 system 에 끼므로 규제 단계)."""

DEFAULT_MEMOS: Final[Mapping[str, str]] = {
    **{key: "" for key in LABELS},
    "regulation_system": "국가별 최소 3건 · 최근 2년 안 업데이트가 없으면 시행 중인 제도로 채움",
    "keywords_system": "토픽마다 키워드 10~15개 · 이슈 5~7건, 한국 이슈 2건 이상",
    "impact_system": "서브토픽마다 긍정 1 · 부정 1까지",
    "financial_system": "서브토픽마다 리스크 1 · 기회 1",
    "pathway_system": "영향 정의 한 줄마다 ① → ② → ③",
}
"""저장 글 없는 판의 칸 메모 — 묶음 첫 칸에 시안 메모, 나머지 칸·신뢰 출처 둘은 빈 메모(처분 Q7)."""

OUTPUT_MARKS: Final[Mapping[str, tuple[str, str | None]]] = {
    "regulation_system": ("[10] 출력 형식 강제 — JSON ONLY", None),
    "keywords_prefix": ("3) 아래 JSON 형식으로만", None),
    "controversy_system": ("[OUTPUT] 출력 형식 강제", "[작성 규칙]"),
    "impact_system": ("[FINAL OUTPUT — JSON ONLY]", None),
    "financial_system": ("[FINAL OUTPUT — JSON ONLY]", None),
    "pathway_system": ("[FINAL OUTPUT — JSON ONLY]", None),
}
"""출력 형식 절의 (머리, 끝 머리|None). 머리는 마지막 것, 절은 그 머리부터 끝 머리 앞까지(None 이면 글 끝까지).
나머지 칸(접두·가변 입력·2부 입력 글·신뢰 출처)은 절이 없다."""

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
    """판의 모델 설정 받기 — core 받기 한 겹 + research temperature null 거절 + analysis temperature 값 거절(처분 Q9).
    given 은 꼴(AiModelSettingsIn)을 지난 값."""
    found = check_model_settings(config, given, steps=steps)
    if isinstance(found, ModelSettingRefused):
        return found
    for step in found.steps:
        if step.key == RESEARCH and step.temperature is None:
            return ModelSettingRefused(
                "ai_model_temperature_range", "temperature 는 0~2 사이 수로 넣어 주세요", step.key
            )
        if step.key == ANALYSIS and step.temperature is not None:
            return ModelSettingRefused(
                "ai_model_temperature_unsupported", "분석 모델은 temperature 를 싣지 않아요(코랩 2부)", step.key
            )
    return found


def accept_prompts(given: AiPromptsIn) -> AcceptedPrompts | PromptRefused:
    """판의 프롬프트 글 받기 — core check_prompts 한 겹(layout = LAYOUT) + 자리 지킴(처분 Q5·Q6 — 첫 빠진 칸 하나, 그
    칸의 첫 빠진 자리)."""
    found = check_prompts(given, layout=LAYOUT)
    if isinstance(found, PromptRefused):
        return found
    for i, step in enumerate(found.steps):
        for j, prompt in enumerate(step.prompts):
            missing = texts.missing_slots(prompt.text, texts.REQUIRED.get(FIELDS[prompt.key], ()))
            if missing:
                return PromptRefused(
                    "ai_prompt_placeholder_missing",
                    f"{LABELS[prompt.key]}에서 {missing[0]} 자리를 지우면 안 돼요",
                    f"prompts.steps.{i}.prompts.{j}.text",
                )
    return found


def _without_legacy(given: AiPromptsIn) -> AiPromptsIn:
    """given 의 새 사본 — 단계마다 LEGACY_KEYS[그 단계] 칸만 뺀다(원본은 안 고친다). 다른 단계·표 밖 칸은 그대로."""
    return {
        "steps": [
            {
                "key": step["key"],
                "prompts": [p for p in step["prompts"] if p["key"] not in LEGACY_KEYS.get(step["key"], frozenset())],
            }
            for step in given["steps"]
        ]
    }


def _has_legacy(given: AiPromptsIn) -> bool:
    return any(p["key"] in LEGACY_KEYS.get(s["key"], frozenset()) for s in given["steps"] for p in s["prompts"])


def accept_stored(given: AiPromptsIn) -> AcceptedPrompts | PromptRefused:
    """저장된 판의 글 받기(읽는 자리 — prompt-model·적용·실행 만들기·다시 짓기). 옛 판(칸 열일곱)의 칸 셋을 그
    단계에서만 떼고 accept_prompts(MARC-ENT-569 — 표는 불변 행이라 읽을 때 정규화). 옛 칸이 없으면 accept_prompts 와
    같다. 저장 POST 는 이것을 쓰지 않는다(열일곱이면 ai_prompt_keys_fixed)."""
    return accept_prompts(_without_legacy(given))


def legacy_sha256(given: AiPromptsIn) -> str | None:
    """옛 판(LEGACY 칸이 하나라도 있음)이면 받은 그대로(열일곱)의 core prompts_sha256 — IRA3 앞에 만든 실행의
    promptsSha256 과 견줄 값(처분 Q3). 옛 칸이 없으면 None. 메모는 sha 에 안 든다(core 규칙)."""
    if not _has_legacy(given):
        return None
    as_given = AcceptedPrompts(
        steps=tuple(
            AcceptedPromptStep(
                key=step["key"],
                prompts=tuple(AcceptedPrompt(key=p["key"], text=p["text"], memo="") for p in step["prompts"]),
            )
            for step in given["steps"]
        )
    )
    return prompts_sha256(as_given)


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
    """판의 저장 글(accept_prompts·accept_stored 를 지난 값 — 칸 열넷) → 엔진 글 열일곱(FIELDS 밖 셋은 기본 글).
    None(코드 글) 이면 DEFAULT_TEXTS 그대로."""
    if accepted is None:
        return DEFAULT_TEXTS
    return dataclasses.replace(
        DEFAULT_TEXTS, **{FIELDS[prompt.key]: prompt.text for step in accepted.steps for prompt in step.prompts}
    )


def models_from(accepted: AcceptedModelSettings) -> tuple[StageModel, StageModel]:
    """받은 모델 값(accept_model 이나 defaults 를 지난 값) → (research, analysis) 의 경로·temperature·위끝."""
    slots = {
        step.key: StageModel(route=step.route, temperature=step.temperature, max_output_tokens=step.max_output_tokens)
        for step in accepted.steps
    }
    research = slots[RESEARCH]
    if research.temperature is None:  # accept_model·defaults 가 막는다(기본값은 흐름 상수)
        raise ValueError(f"모델 칸 {RESEARCH} 의 temperature 가 없다")
    return research, slots[ANALYSIS]


def fixed_groups() -> list[AiFixedGroup]:
    """판과 무관한 읽기 전용 코드 값 둘(웹 검색 · 실행 규칙 — 처분 Q12). 부를 때 짓는다."""
    return [
        {
            "key": "tools",
            "label": "웹 검색",
            "items": [
                {
                    "key": RESEARCH,
                    "label": "리서치 모델",
                    "value": (
                        "리서치 두 단계는 늘 웹 검색 · 검색 범위 "
                        f"{constants.SEARCH_CONTEXT_SIZE} · 위치는 새 평가의 기준 국가"
                    ),
                },
                {
                    "key": ANALYSIS,
                    "label": "분석 모델",
                    "value": (
                        "영향·재무 단계는 새 평가에서 최신 이슈 반영을 켰을 때만 · 검색 범위 "
                        f"{constants.PART2_SEARCH_CONTEXT_SIZE}"
                    ),
                },
            ],
        },
        {
            "key": "processing",
            "label": "실행 규칙",
            "items": [
                {
                    "key": "calls",
                    "label": "호출 단위",
                    "value": "규제·이슈는 토픽마다 · 키워드는 실행마다 한 번 · 영향·재무·경로는 서브토픽마다",
                },
                {"key": "max_steps", "label": "호출마다 걸음", "value": colab_155.MAX_STEPS},
                {"key": "retry", "label": "잘림 다시 시도", "value": constants.RETRY_ON_INCOMPLETE},
                {"key": "max_cost_usd", "label": "실행 비용 상한(USD)", "value": repr(colab_155.RUN_MAX_COST_USD)},
                {"key": "whitelist", "label": "신뢰 출처 판 고름", "value": "입력의 업종 구분(금융·비금융)"},
                {"key": "analysis_temperature", "label": "분석 모델 temperature", "value": "싣지 않음(코랩 2부)"},
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
                    prompt_id=PROMPT_IDS[key],
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
