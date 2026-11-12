"""그린워싱 선언을 core 부품으로 조합한다(밴드 AP1a 3-4, 결정 MARC-ENT-399 — 제품 코드 0줄, 순수 층).

    3-4-1  모듈 선언 MODULE_SPEC(AP1b — 시험 안의 선언을 갈음)이 check_module 을 지나고 layout_of 가 LAYOUT
    3-4-2  기본 판·저장 판(모델 바꿈·글 바꿈)의 제품 prompt_model(@3 — AP1b)이 BASE @2 고정 사본(ap1b-baseline p1~p3)과
           뜻이 같다(schemaVersion 만 바뀌고 칸은
           옮겨지며, 새 칸은 unavailableRoutes == []·modelSlots == ["judge"])
    3-4-3  판 규칙(next_version_name·version_status)이 그린워싱 next_name·status_of 와 같고 판 상수 넷이 G/models.py·
           G/contracts/ai_setting_shapes.py 와 같다
    3-4-4  ai_versions 가 끼움(binding_e0.versions_with)이 지은 versions 의 공통 열쇠와 같다(기본 판·코드 글 판·
           저장 글 판)

칸 글은 그린워싱이 prompt_entry 로 짓고 compose 가 묶는다(AP1b). 설정은 패키지의 실제
파일이다. 글은 지어낸 것이다. 실제 AI 호출 0.
"""

import re
from datetime import UTC, datetime
from typing import Any

import pytest

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AcceptedPrompts,
    ai_versions,
    check_module,
    check_prompts,
    defaults,
    layout_of,
    next_version_name,
    prompts_sha256,
    version_status,
)
from esgapi.core.contracts import ai_setting_shapes as core_shapes
from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_V3, AiModelSettingsIn, AiPromptModel3
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.greenwash import models as greenwash_models
from esgapi.greenwash.contracts import ai_setting_shapes as greenwash_shapes
from esgapi.greenwash.engines.e0.prompts import default_prompts
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import prompt_model_e0 as pm
from esgapi.greenwash.flows.binding_e0 import GreenwashBinding
from esgapi.greenwash.service.selectors.ai_settings import status_of
from esgapi.greenwash.service.services.ai_settings import next_name
from esgapi.greenwash.tests.flows import ap1b_baseline
from esgapi.greenwash.tests.flows.settings_store import DefaultOnlyStore
from esgapi.greenwash.tests.flows.support import REAL_MODELS
from esgapi.greenwash.tests.flows.test_binding_e0_prompts import SAVED, accepted_saved, binding_of
from esgapi.greenwash.tests.flows.test_binding_e0_settings import OPTIONS, STORED_DEFAULT, A

CONFIG: LlmConfig = load_config(default_config_sources(synthetic=False))
SPEC = pm.MODULE_SPEC
# BASE(4e28a54) 트리의 셈으로 뽑은 기본 글 넷(코드 글 + DEFAULT_MEMOS)의 prompts_sha256(★B — 보고 band-reports/AP1a.md).
BASE_DEFAULT_PROMPTS_SHA = "26dc93ac7af582f9c4049ac6546b053b203ab78a7baad1235740c0a8fa018ede"
CHANGED_MODEL: AiModelSettingsIn = {
    "steps": [
        {"key": "judge", "route": "standard-openai-41", "temperature": 0.3, "webSearch": False, "maxOutputTokens": 2000}
    ]
}


# ── 3-4-1 선언 ──


def test_the_declaration_passes_and_its_layout_is_the_modules() -> None:
    check_module(SPEC)
    assert layout_of(SPEC) == tuple((key, tuple(keys)) for key, keys in pm.LAYOUT)
    assert [(k, list(v)) for k, v in layout_of(SPEC)] == [(k, list(v)) for k, v in pm.LAYOUT]
    assert [g.key for g in SPEC.groups] == ["judge"] and SPEC.groups[0].label == "판정"


def test_the_default_texts_keep_the_base_sha() -> None:
    pack = default_prompts(colab.judged_prompt_version(dict(colab.SCAN_CONFIG)))
    body: Any = {
        "steps": [
            {
                "key": pm.JUDGE.key,
                "prompts": [
                    {"key": key, "text": getattr(pack, field), "memo": pm.DEFAULT_MEMOS[key]}
                    for key, _, field in pm.PROMPTS
                ],
            }
        ]
    }
    accepted = check_prompts(body, layout=layout_of(SPEC))
    assert isinstance(accepted, AcceptedPrompts)
    assert prompts_sha256(accepted) == BASE_DEFAULT_PROMPTS_SHA


# ── 3-4-2 뜻 같음 ──


def _accepted_model(given: AiModelSettingsIn | None) -> AcceptedModelSettings:
    if given is None:
        return defaults(CONFIG, pm.STEPS)
    found = pm.accept_model(CONFIG, given)
    assert isinstance(found, AcceptedModelSettings), found
    return found


CASES = {
    "default": (None, None, "colab-default", "p1-default"),
    "saved-model": (CHANGED_MODEL, None, "v2", "p2-saved-model"),
    "saved-text": (CHANGED_MODEL, "saved", "v3", "p3-saved-text"),
}


def pair(case: str) -> tuple[Any, AiPromptModel3]:
    """(BASE @2 몸 — 고정 사본 tests/data/ap1b-baseline, 제품 prompt_model 의 @3 몸)."""
    given, texts, name, branch = CASES[case]
    model = _accepted_model(given)
    prompts = accepted_saved() if texts == "saved" else None
    old = ap1b_baseline.stored_prompt(branch)
    new = pm.prompt_model(
        CONFIG, setting_name=name, criteria=None, model=model, editable_model=pm.EDITABLE_MODEL, prompts=prompts
    )
    return old, new


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_v3_body_means_the_v2_body(case: str) -> None:
    old, new = pair(case)
    PROMPT_MODEL_V3.validate_python(new, strict=True)
    assert (old["schemaVersion"], new["schemaVersion"]) == ("ai.prompt-model@2", "ai.prompt-model@3")
    for key in ("module", "settingName", "editable", "modelSettingsSha256", "limits", "fixed"):
        assert new[key] == old[key], key
    (step,) = old["steps"]
    (slot,) = new["models"]
    (group,) = new["promptGroups"]
    assert (slot["model"], slot["routeChoices"]) == (step["model"], step["routeChoices"])
    assert group["prompts"] == step["prompts"]
    assert (slot["key"], slot["label"]) == (group["key"], group["label"]) == (step["key"], step["label"])
    assert slot["unavailableRoutes"] == [] and group["modelSlots"] == ["judge"]
    assert list(new) == [
        "schemaVersion",
        "module",
        "settingName",
        "editable",
        "modelSettingsSha256",
        "models",
        "promptGroups",
        "limits",
        "fixed",
    ]


def test_the_cases_differ() -> None:
    """분모: 세 판이 서로 다른 값을 낸다(모델 sha·글)."""
    bodies = {case: pair(case)[1] for case in CASES}
    assert bodies["default"]["modelSettingsSha256"] != bodies["saved-model"]["modelSettingsSha256"]
    assert bodies["saved-model"]["promptGroups"] != bodies["saved-text"]["promptGroups"]


# ── 3-4-3 판 규칙 ──

NAME_CASES = [
    (),
    ("v1",),
    ("v1", "v3", "x", "v0", "v01"),
    ("v9",),
    ("v07", "v00", "V2", "v2a", "v"),
    ("v12", "v2"),
]


@pytest.mark.parametrize("names", NAME_CASES)
def test_the_next_version_name_is_the_modules(names: tuple[str, ...]) -> None:
    assert next_version_name(names) == next_name(names)
    assert re.fullmatch(core_shapes.VERSION_NAME_PATTERN, next_version_name(names))


@pytest.mark.parametrize("applied", [True, False])
@pytest.mark.parametrize("applied_at", [None, datetime(2026, 10, 1, tzinfo=UTC)])
def test_the_version_rules_are_the_modules(applied: bool, applied_at: datetime | None) -> None:
    assert version_status(applied, applied_at) == status_of(applied, applied_at)


def test_the_module_version_rules_are_core_aliases() -> None:
    assert (next_name, status_of) == (next_version_name, version_status) and next_name is next_version_name


def test_the_version_limits_are_the_modules() -> None:
    assert core_shapes.VERSION_NAME_PATTERN == greenwash_models.AI_SETTING_NAME_PATTERN
    assert core_shapes.VERSION_NAME_MAX_CHARS == greenwash_models.AI_SETTING_NAME_MAX_CHARS
    assert core_shapes.VERSION_TITLE_MAX_CHARS == greenwash_models.AI_SETTING_TITLE_MAX_CHARS
    assert core_shapes.VERSION_MEMO_MAX_CHARS == greenwash_models.AI_SETTING_MEMO_MAX_CHARS
    assert core_shapes.VERSION_TITLE_MAX_CHARS == greenwash_shapes.TITLE_MAX_CHARS
    assert core_shapes.VERSION_MEMO_MAX_CHARS == greenwash_shapes.MEMO_MAX_CHARS


# ── 3-4-4 versions 공통 열쇠 ──

COMMON = ("aiSettingId", "modelSettingsSha256", "promptsSha256")


def _common(versions: dict[str, object]) -> dict[str, object]:
    return {key: versions[key] for key in COMMON if key in versions}


def test_ai_versions_is_the_bindings_common_keys() -> None:
    default = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).versions_with(OPTIONS, company_id=A)
    assert _common(default) == ai_versions(setting_id=None, model=defaults(CONFIG, pm.STEPS), prompts=None)

    stored = _accepted_model(STORED_DEFAULT)
    code_text = binding_of(None).versions_with(OPTIONS, company_id=A)
    assert _common(code_text) == ai_versions(setting_id=7, model=stored, prompts=None)
    assert "promptsSha256" not in code_text

    saved_text = binding_of(SAVED).versions_with(OPTIONS, company_id=A)
    assert _common(saved_text) == ai_versions(setting_id=7, model=stored, prompts=accepted_saved())
    assert set(_common(saved_text)) == set(COMMON)
