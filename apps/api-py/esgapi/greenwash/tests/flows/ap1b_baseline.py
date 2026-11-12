"""밴드 AP1b ①-0 바닥 기준물 — 그린워싱 prompt-model·versions 를 core 부품으로 갈아타기 전 코드로 뽑아 커밋한 것
(tests/data/ap1b-baseline/)과 갈아탄 뒤를 견준다(순수 층 — DB·실제 공급사·키 0).

갈래 아홉. 판 고정값은 g2d-baseline/fixtures.json(v1~v3 = g2d a~c 와 같은 판):
    versions(끼움 versions_with 가 지은 dict — 열쇠 차례째 바이트, versions-<갈래>.json)
    v1-default               기본 판(적용 판 없음)
    v2-saved-code-text       저장 판·코드 글·단어 칸 없음
    v3-saved-text            저장 판·저장 글
    v4-saved-terms           저장 판·단어 칸(켠 낱말 = 기본 목록 + 지어낸 낱말 하나 — 기본과 다름)
    v5-saved-text-terms      저장 글 + v4 의 단어 칸
    v6-saved-terms-folded    단어 칸 = 기본 목록 차례까지(실행 inputs.terms 는 None 으로 접히고 termsSha256 은 실린다)
    @2 몸(BASE 의 prompt_model 이 지은 ai.prompt-model@2 — prompt-model-v2-<갈래>.json, 다시 뽑지 않는다)
    p1-default               기본 판
    p2-saved-model           모델 바꾼 판(코드 글)
    p3-saved-text            모델 바꾼 판 + 저장 글

p1~p3 는 @2 를 짓는 코드가 있을 때(BASE)만 뽑힌다 — 그 뒤엔 prompt_v2 가 AssertionError 로 멈춘다(README 「다시 뽑지
않는다」). 글·낱말은 지어낸 것이다.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Final, cast

from esgapi.core.calc.ai_settings import AcceptedModelSettings, AcceptedPrompts, check_prompts, defaults
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.greenwash.contracts.terms_shapes import GreenwashTerm
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import prompt_model_e0 as pm
from esgapi.greenwash.flows.binding_e0 import GreenwashBinding, SavedSetting
from esgapi.greenwash.tests.flows import g2d_baseline as g2d
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.flows.settings_store import DefaultOnlyStore, FakeStore

DATA: Final = Path(__file__).resolve().parents[1] / "data" / "ap1b-baseline"
VERSIONS: Final = (
    "v1-default",
    "v2-saved-code-text",
    "v3-saved-text",
    "v4-saved-terms",
    "v5-saved-text-terms",
    "v6-saved-terms-folded",
)
PROMPT_MODELS: Final = ("p1-default", "p2-saved-model", "p3-saved-text")
ADDED_TERM: Final = "지어낸 낱말"
"""v4·v5 의 판에 더한 지어낸 낱말(켠 낱말이 기본 목록과 다르게)."""
CHANGED_MODEL: Final[AiModelSettingsIn] = {
    "steps": [
        {"key": "judge", "route": "standard-openai-41", "temperature": 0.3, "webSearch": False, "maxOutputTokens": 2000}
    ]
}
"""p2·p3 의 모델 값 — AP1a test_prompt_model_e0_v3.CHANGED_MODEL 과 같은 값."""
SETTING_NAMES: Final = {"p1-default": "colab-default", "p2-saved-model": "v2", "p3-saved-text": "v3"}


def company() -> int:
    return cast("int", g2d.fixtures()["companyId"])


def options() -> dict[str, object]:
    return cast("dict[str, object]", g2d.fixtures()["options"])


def terms_of(branch: str) -> list[GreenwashTerm] | None:
    if branch in ("v4-saved-terms", "v5-saved-text-terms"):
        return [*({"text": t, "enabled": True} for t in colab.DEFAULT_TERMS), {"text": ADDED_TERM, "enabled": True}]
    if branch == "v6-saved-terms-folded":
        return [{"text": t, "enabled": True} for t in colab.DEFAULT_TERMS]
    return None


def setting_of(branch: str) -> SavedSetting:
    saved = g2d.saved_setting(prompts=branch in ("v3-saved-text", "v5-saved-text-terms"))
    return replace(saved, terms=terms_of(branch))


def binding_of(branch: str) -> GreenwashBinding:
    if branch == "v1-default":
        return GreenwashBinding(models=s.REAL_MODELS, store=DefaultOnlyStore())
    setting = setting_of(branch)
    return GreenwashBinding(
        models=s.REAL_MODELS, store=FakeStore(saved={company(): [setting]}, applied_id={company(): setting.id})
    )


def versions_of(branch: str) -> dict[str, object]:
    """지금 코드의 versions_with 결과(갈래 하나)."""
    return binding_of(branch).versions_with(options(), company_id=company())


def config() -> LlmConfig:
    return load_config(default_config_sources(synthetic=False))


def model_of(branch: str) -> AcceptedModelSettings:
    if branch == "p1-default":
        return defaults(config(), pm.STEPS)
    found = pm.accept_model(config(), CHANGED_MODEL)
    assert isinstance(found, AcceptedModelSettings), found
    return found


def accepted_saved() -> AcceptedPrompts:
    """g2d 고정값의 저장 글(= test_binding_e0_prompts.SAVED — 그 모듈은 django 를 들여 여기서 부르지 않는다)."""
    found = check_prompts(cast("AiPromptsIn", g2d.fixtures()["savedPrompts"]), layout=colab.LAYOUT)
    assert isinstance(found, AcceptedPrompts), found
    return found


def prompt_v2(branch: str) -> Any:
    """BASE 의 prompt_model 이 지은 @2 몸. 지금 코드가 @2 를 내지 않으면 AssertionError(다시 뽑지 않는다)."""
    body = cast(
        "dict[str, Any]",
        pm.prompt_model(
            config(),
            setting_name=SETTING_NAMES[branch],
            criteria=None,
            model=model_of(branch),
            editable_model=pm.EDITABLE_MODEL,
            prompts=accepted_saved() if branch == "p3-saved-text" else None,
        ),
    )
    assert body["schemaVersion"] == "ai.prompt-model@2", "p1~p3 는 @2 를 짓는 BASE 코드로만 뽑는다"
    return body


def dump(found: object) -> bytes:
    """파일 바이트 — 열쇠 차례 그대로(정렬 없음)."""
    return (json.dumps(found, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def versions_file(branch: str) -> str:
    return f"versions-{branch}.json"


def prompt_file(branch: str) -> str:
    return f"prompt-model-v2-{branch}.json"


def stored_versions(branch: str) -> dict[str, object]:
    return cast("dict[str, object]", json.loads((DATA / versions_file(branch)).read_bytes()))


def stored_prompt(branch: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((DATA / prompt_file(branch)).read_bytes()))
