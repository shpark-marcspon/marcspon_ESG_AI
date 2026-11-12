"""끼움 versions_with 가 공통 열쇠를 core ai_versions 로 지어도 바닥과 바이트가 같다(밴드 AP1b §3-1, 결정 MARC-ENT-399
·352 — 순수 층, 바닥 기준물 tests/data/ap1b-baseline, 도우미 tests/flows/ap1b_baseline.py).

    3-1-1  v1~v6: 지금 versions_with 의 바이트(열쇠 차례째) = versions-<갈래>.json · termsSha256 은 v4~v6 에만
    3-1-2  옛 실행 mismatch 0: 고정 사본 versions 가 inputs_with 를 지남(terms = 켠 낱말·접기 None·칸 없음 None)
           · 단어 판의 실행에서 termsSha256 을 빼면 AiSettingMismatch(분모) · 새 실행 길: 지금 versions 도 같은 inputs
    3-1-3  ai_versions(…) 의 값 ⊆ v1~v6 · 모듈 열쇠 셋(aiSetting·evalPromptSha256·termsSha256)은 그 결과에 없다

판·글·낱말은 지어낸 것이다. 실제 AI 호출 0.
"""

import pytest

from esgapi.core.calc.ai_settings import AcceptedModelSettings, ai_versions, check_model_settings, defaults
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import prompt_model_e0 as pm
from esgapi.greenwash.flows.binding_e0 import AiSettingMismatch
from esgapi.greenwash.tests.flows import ap1b_baseline as baseline
from esgapi.greenwash.tests.flows import g2d_baseline as g2d

MODULE_KEYS = ("aiSetting", "evalPromptSha256", "termsSha256")


def inputs_of(branch: str, versions: dict[str, object]) -> colab.GreenwashInputs:
    return baseline.binding_of(branch).inputs_with(
        g2d.DOCUMENT, baseline.options(), company_id=baseline.company(), versions=versions
    )


# ── 3-1-1 바이트 ──


@pytest.mark.parametrize("branch", baseline.VERSIONS)
def test_the_versions_are_the_baseline_to_the_byte(branch: str) -> None:
    built = baseline.versions_of(branch)
    assert baseline.dump(built) == (baseline.DATA / baseline.versions_file(branch)).read_bytes()
    assert ("termsSha256" in built) == (branch in ("v4-saved-terms", "v5-saved-text-terms", "v6-saved-terms-folded"))


# ── 3-1-2 옛 실행·새 실행 ──


@pytest.mark.parametrize("branch", baseline.VERSIONS)
def test_an_old_run_passes_the_worker_check(branch: str) -> None:
    terms = inputs_of(branch, baseline.stored_versions(branch)).terms
    if branch in ("v4-saved-terms", "v5-saved-text-terms"):
        assert terms == (*colab.DEFAULT_TERMS, baseline.ADDED_TERM)
    else:
        assert terms is None  # 칸 없음 · 기본 목록 그대로(접기)


@pytest.mark.parametrize("branch", baseline.VERSIONS)
def test_a_new_run_builds_the_same_inputs(branch: str) -> None:
    assert inputs_of(branch, baseline.versions_of(branch)) == inputs_of(branch, baseline.stored_versions(branch))


def test_a_terms_run_without_its_key_is_a_mismatch() -> None:
    """분모: 판 단어로 만든 실행(v4)에서 termsSha256 을 빼면 워커가 거절한다."""
    stored = baseline.stored_versions("v4-saved-terms")
    with pytest.raises(AiSettingMismatch):
        inputs_of("v4-saved-terms", {k: v for k, v in stored.items() if k != "termsSha256"})


# ── 3-1-3 공통 열쇠 ──


def _model(branch: str) -> AcceptedModelSettings:
    config = baseline.config()
    if branch == "v1-default":
        return defaults(config, pm.STEPS)
    found = check_model_settings(config, baseline.setting_of(branch).model_settings, steps=pm.STEPS)
    assert isinstance(found, AcceptedModelSettings), found
    return found


@pytest.mark.parametrize("branch", baseline.VERSIONS)
def test_the_common_keys_are_core_ai_versions(branch: str) -> None:
    stored = baseline.stored_versions(branch)
    saved_text = branch in ("v3-saved-text", "v5-saved-text-terms")
    common = ai_versions(
        setting_id=None if branch == "v1-default" else baseline.setting_of(branch).id,
        model=_model(branch),
        prompts=baseline.accepted_saved() if saved_text else None,
    )
    assert {key: stored[key] for key in common} == dict(common)
    assert ("promptsSha256" in common) == saved_text
    assert not set(MODULE_KEYS) & set(common)
    assert set(stored) == {*common, "aiSetting", "evalPromptSha256", *(["termsSha256"] if "terms" in branch else [])}
