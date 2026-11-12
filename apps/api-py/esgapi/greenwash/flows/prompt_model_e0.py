"""E0 판의 프롬프트·모델 보기(ai.prompt-model@3 — 밴드 AS2a·AS3a-1·AP1b, 이슈 MARC-ISSUE-240·257·280, 결정
MARC-ENT-350·353·381·384·385·399). 그린워싱 판의 단계 명세·허용 경로·프롬프트 표(칸 이름·기본 메모·출력절·layout)·읽기
전용 고정 값과 모듈 선언(MODULE_SPEC)은 이 파일 한 곳이다. 몸은 core compose 가 짓는다(꼴은 core/contracts/
ai_setting_shapes.py 그대로 — 그린워싱 쪽에 꼴을 새로 두지 않는다). 설정에서 빠진 고르지 않은 경로는 500 이 아니라
unavailableRoutes 다(280).

- 단계는 판정(judge) 하나다. 노트북 스캔의 대화가 프롬프트 넷(문장 찾기·판정·수정 방향 다듬기·Low 문장 설명)을
  같은 경로·온도·출력 상한으로 부른다(colab_e0.LlmChatBridge). judge 는 call.complete 길이라 도구 고리가 아니다 →
  web_search 0.
- 프롬프트 받기는 core check_prompts 하나다 — 이 파일은 layout(LAYOUT)·기본 글·출력절·고정 값만 넘긴다. 엔진은 system
  글이 넷 중 어느 것인지 글자 같음으로 가른다(engines/e0/ports.prompt_kind) → 한 단계 안 같은 글 둘은 받기가 거절한다.
- 출력절 = 기본 글의 마지막 OUTPUT_MARK 줄부터 끝. 저장 글이 그 절을 바이트 그대로 품지 않으면 outputKept false(화면
  경고 — 저장은 안 막는다. 절이 깨지면 엔진의 JSON 읽기가 조용히 기본값으로 떨어진다).
- 고정 값(fixed_groups)은 코드 상수에서 읽는다: 파트 = binding_e0.PARTS × colab_e0.PART_ORDER, 처리 값 =
  colab_e0.scan_cfg() 의 칸. 함수로 늦게 짓는다(import 때 0).
- 기본값은 colab_e0 의 이름(CHAT_ROUTE·TEMPERATURE·MAX_OUTPUT_TOKENS)을 가리킨다 — 수 글자를 여기 박지 않는다.
- eval 글은 실행이 보낼 글과 같은 길로 짓는다: 판 글자 = judged_prompt_version(SCAN_CONFIG), 기준표가 있으면
  criteria_e0.eval_pack(accept_criteria(…), 판 글자). 그래서 eval 의 sha256 ==
  run_versions(<기준표>)["evalPromptSha256"].
  받기를 못 지나는 기준표는 CriteriaRejected 를 그대로 올린다(잡는 것은 service 의 actions).
- 판의 모델 설정(AS2b): accept_model = core 받기(check_model_settings) 한 겹. 저장 판은 그 정규형(to_input)을 품는다.
- 판의 프롬프트 글(AS3a-2): accept_prompts = core 받기(check_prompts, layout = colab_e0.LAYOUT) 한 겹. 저장 판은 그
  정규형(prompts_input)을 품고, 없으면(NULL) 코드 글이다.
- 순수하다: 설정(LlmConfig)은 부르는 쪽이 넘긴다(실제 파일 — service/selectors/ai_settings.RunModelSource).
"""

from collections.abc import Mapping, Sequence
from typing import Final

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AcceptedPrompts,
    AiModuleSpec,
    AiPromptGroupSpec,
    AiStepSpec,
    ModelSettingRefused,
    PromptLayout,
    PromptRefused,
    check_model_settings,
    check_prompts,
    compose,
    prompt_entry,
)
from esgapi.core.contracts.ai_setting_shapes import (
    AiFixedGroup,
    AiModelSettingsIn,
    AiPromptEntry,
    AiPromptModel3,
    AiPromptsIn,
)
from esgapi.core.llm.config import LlmConfig
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.engines.e0.prompts import PromptPack, default_prompts
from esgapi.greenwash.flows import binding_e0, criteria_e0
from esgapi.greenwash.flows import colab_e0 as colab

MODULE: Final = "greenwash"

JUDGE_ROUTES: Final = ("light-openai-41", "standard-openai-41")
"""judge 에 고를 수 있는 경로(화면 차례). openai 둘만 — 그린워싱 프롬프트를 실측한 공급사가 openai 하나다(AS2a 처분
Q-A1). 넓히는 길 = 이 줄 + 시험 셈 + 그 경로 실측 한 번(MARC-ENT-262 안)."""

JUDGE: Final = AiStepSpec(
    key=colab.JUDGE_STEP,
    label="판정",
    routes=JUDGE_ROUTES,
    tool_loop=False,
    default={
        "key": colab.JUDGE_STEP,
        "route": colab.CHAT_ROUTE,
        "temperature": colab.TEMPERATURE,
        "webSearch": False,
        "maxOutputTokens": colab.MAX_OUTPUT_TOKENS,
    },
)
STEPS: Final[tuple[AiStepSpec, ...]] = (JUDGE,)
MODULE_SPEC: Final = AiModuleSpec(
    module=MODULE,
    models=STEPS,
    groups=(
        AiPromptGroupSpec(
            key=JUDGE.key, label=JUDGE.label, prompt_keys=tuple(colab.PROMPT_IDS), model_slots=(JUDGE.key,)
        ),
    ),
)
"""모듈 선언(core 부품 — 밴드 AP1b, MARC-ENT-399): 모델 칸 = STEPS, 프롬프트 묶음 = judge 하나(칸 = PROMPT_IDS 차례).
layout_of(MODULE_SPEC) == LAYOUT(워커와 같은 것 하나 — tests/flows/test_prompt_model_e0.py)."""

PROMPTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("detect", "문장 찾기", "detect_system_prompt"),
    ("eval", "판정", "eval_system_prompt"),
    ("repair", "수정 방향 다듬기", "repair_fix_prompt"),
    ("low_only", "Low 문장 설명", "low_only_prompt"),
)
"""(key, 화면 이름, PromptPack 칸) — 차례·key 는 colab_e0.PROMPT_IDS 와 같다(tests/flows/test_prompt_model_e0.py).
이름은 MARC-ENT-384(서버 글 — 웹은 글 표를 두지 않는다)."""

LAYOUT: Final[PromptLayout] = colab.LAYOUT
"""core check_prompts 에 넘기는 명세(단계 key, 칸 key 차례) — colab_e0.LAYOUT 하나(워커와 같은 것, AS3a-2 M2)."""

DEFAULT_MEMOS: Final[Mapping[str, str]] = {
    "detect": "가장 상위 규칙 정의: 역할 정의, 핵심 목표, 강한 제외, 출력(json 배열 only)",
    "eval": "High·Mid·NonRisk 만 판단(Low 는 시스템이 먼저 확정, NonRisk 는 결과 리포트에서 제외)",
    "repair": "High·Mid 인데 수정 방향이 일반론이면 1회 다시 요청 — 등급에 맞는 '수정 방향'만 작성",
    "low_only": "Low 확정 문장용 — 사유·수정 방향만 출력(판정 X)",
}
"""저장 글 없는 판의 칸 메모 — share/2026-10-21-AD-02-프롬프트-수정안.html 「기본 판 메모 예시」 글."""

OUTPUT_MARK: Final = "[출력(JSON"
"""기본 글의 출력 형식 절 머리(넷 다 하나씩)."""

EDITABLE_PROMPTS: Final = True
"""프롬프트 글을 새 판에 넣을 수 있는가. AS3a-1 은 보기만 — 저장을 받는 AS3a-2 가 True 로 바꿨다."""

PROCESSING: Final[tuple[tuple[str, str], ...]] = (
    ("max_candidates_per_page", "페이지당 후보 문장"),
    ("max_chars_page_text", "페이지 글자"),
    ("evidence_k", "근거 조각 수"),
    ("max_chars_per_chunk", "조각 글자"),
    ("max_chars_evidence_total", "근거 합 글자"),
)
"""처리 값(읽기 전용): (colab_e0.scan_cfg() 의 칸, 화면 이름). 값은 그 칸에서 읽는다 — 수 글자를 여기 박지 않는다."""

EDITABLE_MODEL: Final = True
"""모델 설정을 새 판에 넣을 수 있는가. AS2a 는 읽기만(처분 Q-A2) — 저장·적용을 받는 AS2b 가 True 로 바꿨다."""


def accept_model(
    config: LlmConfig, given: AiModelSettingsIn, *, steps: Sequence[AiStepSpec] = STEPS
) -> AcceptedModelSettings | ModelSettingRefused:
    """판의 모델 설정 받기(AS2b) — core 받기 한 겹(그린워싱 규칙 더함 0). given 은 꼴(AiModelSettingsIn)을 지난 값.
    steps 는 원천(selectors.RunModelSource.steps — 실제는 STEPS)이 넘긴다."""
    return check_model_settings(config, given, steps=steps)


def accept_prompts(given: AiPromptsIn) -> AcceptedPrompts | PromptRefused:
    """판의 프롬프트 글 받기(AS3a-2) — core 받기(check_prompts) 한 겹, layout = LAYOUT. given 은 꼴(AiPromptsIn)을 지난
    값."""
    return check_prompts(given, layout=LAYOUT)


def output_section(text: str) -> str | None:
    """글의 출력 형식 절 — 마지막 OUTPUT_MARK 부터 끝. 없으면 None."""
    at = text.rfind(OUTPUT_MARK)
    return None if at < 0 else text[at:]


def fixed_groups() -> list[AiFixedGroup]:
    """판과 무관한 읽기 전용 코드 값 둘(파트·처리 값). 부를 때 짓는다."""
    cfg = colab.scan_cfg()
    return [
        {
            "key": "parts",
            "label": "파트",
            "items": [
                {"key": key, "label": label, "value": None}
                for key, label in zip(binding_e0.PARTS, colab.PART_ORDER, strict=True)
            ],
        },
        {
            "key": "processing",
            "label": "처리 값",
            "items": [{"key": field, "label": label, "value": getattr(cfg, field)} for field, label in PROCESSING],
        },
    ]


def _pack(criteria: GreenwashCriteria | None, version: str) -> PromptPack:
    if criteria is None:
        return default_prompts(version)
    return criteria_e0.eval_pack(criteria_e0.accept_criteria(criteria), version)


def _prompts(pack: PromptPack, version: str, saved: AcceptedPrompts | None) -> list[AiPromptEntry]:
    """칸 넷. 저장 글(saved)이 있으면 그 글·메모, 없으면 지금 묶음(pack)과 DEFAULT_MEMOS. 기본 글·출력절은 엔진
    글에서."""
    engine = default_prompts(version)
    stored = {} if saved is None else {(s.key, p.key): p for s in saved.steps for p in s.prompts}
    entries: list[AiPromptEntry] = []
    for key, label, field in PROMPTS:
        default_text: str = getattr(engine, field)
        found = stored.get((JUDGE.key, key))
        entries.append(
            prompt_entry(
                key=key,
                label=label,
                prompt_id=colab.PROMPT_IDS[key],
                prompt_version=version,
                text=getattr(pack, field) if found is None else found.text,
                memo=DEFAULT_MEMOS[key] if found is None else found.memo,
                default_text=default_text,
                output_section=output_section(default_text),
            )
        )
    return entries


def prompt_model(
    config: LlmConfig,
    *,
    setting_name: str,
    criteria: GreenwashCriteria | None,
    model: AcceptedModelSettings,
    editable_model: bool,
    prompts: AcceptedPrompts | None = None,
) -> AiPromptModel3:
    """한 판의 ai.prompt-model@3 — core compose(MODULE_SPEC). criteria None = 기본 판(엔진 글 그대로). model 은 받기를
    지난 값(기본 판은 defaults(config, STEPS), 저장 판은 accept_model(config, 저장 값) — AS2b). prompts = 판의 저장
    글(core check_prompts 를 지난 값, None 이면 코드 글 — 기준표로 지은 판정 글과 DEFAULT_MEMOS). 칸(prompt_entry)은
    이 모듈이 짓는다. promptId·promptVersion 은 저장 글이어도 지금 값이다(판 글자는 판 행이 말한다). 기준표가 받기를 못
    지나면 CriteriaRejected, 고른 경로를 지금 설정으로 쓸 수 없으면 LlmConfigError(compose)."""
    version = colab.judged_prompt_version(dict(colab.SCAN_CONFIG))
    entries = _prompts(_pack(criteria, version), version, prompts)
    return compose(
        config,
        MODULE_SPEC,
        setting_name=setting_name,
        editable={"prompts": EDITABLE_PROMPTS, "model": editable_model},
        model=model,
        prompts={JUDGE.key: entries},
        fixed=fixed_groups(),
    )
