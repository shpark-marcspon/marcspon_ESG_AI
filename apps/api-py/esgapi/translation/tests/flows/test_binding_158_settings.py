"""끼움 TranslationBinding 의 AI 설정 판(밴드 TR4 §3-4-1·2 — 순수 층, DB 0). 판 포트는 가짜(settings_store.py), 모델
원천은 저장소 정본 models.json(실제 파일 — 모의 경로 0).

    3-4-1  versions_with: 기본 판 = versions + aiSetting 「기본 설정」 + core ai_versions(None, 명세 기본값) · 저장 판 =
           판 이름 + ai_versions(판 id, 다시 받은 모델, 다시 받은 글|None) · 다시 받기 거절 → RunVersionsRejected
    3-4-2  inputs_with: 저장 판 → texts_from·models_from · 코드 글 판 → DEFAULT_TEXTS · 열쇠만/글만·기본 판에 열쇠 →
           mismatch(유무 검사가 모델 대조보다 먼저) · 옛 실행(열쇠 없음) → 코드 값 · sha 다름·없는 판·남의 회사 판·
           int 아닌 id → mismatch · 만든 뒤 받기가 좁아짐 → mismatch(code 를 글에)
    + 판 글·모델이 흐름을 지나 공급사 요청에 닿는다(표지 — 업무 층 양성은 test_runs_translation_settings.py)
글은 지어낸 것이다. 실제 AI 호출 0.
"""

import dataclasses
from typing import Any

import pytest

from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.core.calc.ai_settings import ai_versions, defaults, model_settings_sha256, prompts_sha256
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.flows.binding import RunVersionsMismatch, RunVersionsRejected
from esgapi.core.flows.run import run_flow
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.translation.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.translation.engines.colab_158.texts import DEFAULT_TEXTS
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.flows import prompt_model_158 as pm
from esgapi.translation.flows.binding_158 import AiSettingMismatch, SavedSetting, TranslationBinding
from esgapi.translation.tests.engines.colab_158.support import client
from esgapi.translation.tests.flows.settings_store import FakeStore, FileModels
from esgapi.translation.tests.flows.support import FakeStore as RetryStore
from esgapi.translation.tests.flows.support import document, options
from esgapi.translation.tests.flows.test_colab_158_models import answer
from esgapi.translation.tests.flows.test_prompt_model_158 import (
    ALL_STANDARD,
    CONFIG,
    LIGHT,
    accepted_model,
    accepted_prompts,
    prompts_body,
)
from esgapi.translation.tools.llm_bridge import DEFAULT_MODELS

A, B = 1, 2
MODELS = FileModels(CONFIG)
DEFAULT_MODEL_SHA = model_settings_sha256(defaults(CONFIG, pm.MODELS))
MARKED = prompts_body(
    tone_story="⟦TR4-tone_story⟧ 지어낸 스토리 톤",
    style_b="⟦TR4-style_b⟧ 지어낸 문체 B",
    table_rules="⟦TR4-table_rules⟧ 지어낸 표 규칙",
)


def saved(setting_id: int, *, prompts: AiPromptsIn | None, model: AiModelSettingsIn = ALL_STANDARD) -> SavedSetting:
    return SavedSetting(id=setting_id, name=f"v{setting_id}", model_settings=model, prompts=prompts)


def binding_of(*settings: SavedSetting, company: int = A, applied: int | None = None) -> TranslationBinding:
    store = FakeStore(saved={company: list(settings)}, applied_id={} if applied is None else {company: applied})
    return TranslationBinding(
        store=RetryStore(),
        settings=store,
        models=MODELS,
        max_usd=lambda: 5.0,
        mock=lambda: False,
        spent_usd=lambda _c, _r: 0.0,
    )


def made_versions(binding: TranslationBinding, company: int = A) -> dict[str, object]:
    return binding.versions_with(options(), company_id=company)


def inputs_of(binding: TranslationBinding, versions: dict[str, object], company: int = A) -> colab.TranslationRunInputs:
    return binding.inputs_with(document(), options(), company_id=company, versions=versions)


def narrow(monkeypatch: pytest.MonkeyPatch) -> None:
    """받기 규칙을 좁힌다: 글 상한을 10자로(저장할 때는 받았던 글이 이제 거절된다)."""
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)


# ── 3-4-1 versions_with ──


def test_the_default_setting_adds_the_title_and_the_core_keys() -> None:
    b = binding_of()
    versions = made_versions(b)
    common = ai_versions(setting_id=None, model=defaults(CONFIG, pm.MODELS), prompts=None)
    assert versions == {**b.versions(options()), "aiSetting": DEFAULT_TITLE, **common}
    assert common == {"aiSettingId": None, "modelSettingsSha256": DEFAULT_MODEL_SHA}
    assert list(versions) == ["engine", "flow", "promptIds", "aiSetting", "aiSettingId", "modelSettingsSha256"]


def test_a_code_text_setting_carries_no_prompts_key() -> None:
    b = binding_of(saved(7, prompts=None), applied=7)
    versions = made_versions(b)
    common = ai_versions(setting_id=7, model=accepted_model(ALL_STANDARD), prompts=None)
    assert versions == {**b.versions(options()), "aiSetting": "v7", **common}
    assert "promptsSha256" not in versions


def test_a_saved_text_setting_carries_the_prompts_sha() -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    versions = made_versions(b)
    texts = accepted_prompts(MARKED)
    assert versions == {
        **b.versions(options()),
        "aiSetting": "v7",
        **ai_versions(setting_id=7, model=accepted_model(ALL_STANDARD), prompts=texts),
    }
    assert versions["promptsSha256"] == prompts_sha256(texts)
    assert versions["modelSettingsSha256"] != DEFAULT_MODEL_SHA


def test_another_companys_applied_setting_is_not_read() -> None:
    b = binding_of(saved(7, prompts=MARKED), company=B, applied=7)
    assert made_versions(b, A)["aiSettingId"] is None
    assert made_versions(b, B)["aiSettingId"] == 7


@pytest.mark.parametrize(
    "setting",
    [
        saved(7, prompts=None, model={"steps": [{**step, "temperature": 0.2} for step in ALL_STANDARD["steps"]]}),
        saved(7, prompts=None, model={"steps": list(reversed(ALL_STANDARD["steps"]))}),
        saved(7, prompts=prompts_body(polish="가" * 9_000)),
    ],
    ids=["temperature", "slot-order", "text-length"],
)
def test_an_applied_setting_the_rules_refuse_cannot_make_a_run(setting: SavedSetting) -> None:
    with pytest.raises(RunVersionsRejected, match=r"AI 설정 판\(v7\)"):
        made_versions(binding_of(setting, applied=7))


def test_a_setting_the_narrowed_rules_refuse_cannot_make_a_run(monkeypatch: pytest.MonkeyPatch) -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    assert "promptsSha256" in made_versions(b)  # 분모: 좁히기 전엔 지어진다
    narrow(monkeypatch)
    with pytest.raises(RunVersionsRejected):
        made_versions(b)
    assert "promptsSha256" not in made_versions(binding_of(saved(8, prompts=None), applied=8))  # 코드 글 판은 그대로


# ── 3-4-2 inputs_with ──


def test_a_saved_setting_gives_its_texts_and_models() -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    inputs = inputs_of(b, made_versions(b))
    assert inputs.texts == pm.texts_from(accepted_prompts(MARKED))
    assert inputs.models == pm.models_from(accepted_model(ALL_STANDARD))
    assert inputs.texts.story_tone.startswith("⟦TR4-tone_story⟧") and inputs.texts != DEFAULT_TEXTS
    assert inputs.models != DEFAULT_MODELS


def test_a_code_text_setting_gives_the_default_texts_and_its_models() -> None:
    b = binding_of(saved(7, prompts=None), applied=7)
    inputs = inputs_of(b, made_versions(b))
    assert inputs.texts is DEFAULT_TEXTS
    assert inputs.models == pm.models_from(accepted_model(ALL_STANDARD))


def test_the_default_setting_gives_the_code_values() -> None:
    b = binding_of()
    inputs = inputs_of(b, made_versions(b))
    assert (inputs.texts, inputs.models) == (DEFAULT_TEXTS, DEFAULT_MODELS)


def test_an_old_run_without_the_keys_gives_the_code_values_whatever_is_applied() -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    old = b.versions(options())
    inputs = inputs_of(b, old)
    assert (inputs.texts, inputs.models) == (DEFAULT_TEXTS, DEFAULT_MODELS)


def test_the_run_keeps_the_setting_it_was_made_with() -> None:
    """만든 뒤 적용을 바꿔도 실행은 만들 때의 판(get) — applied 를 다시 읽지 않는다."""
    store = FakeStore(saved={A: [saved(7, prompts=MARKED), saved(8, prompts=None)]}, applied_id={A: 7})
    b = TranslationBinding(
        store=RetryStore(),
        settings=store,
        models=MODELS,
        max_usd=lambda: 5.0,
        mock=lambda: False,
        spent_usd=lambda _c, _r: 0.0,
    )
    versions = made_versions(b)
    store.applied_id[A] = 8
    store.calls.clear()
    assert inputs_of(b, versions).texts.story_tone.startswith("⟦TR4-tone_story⟧")
    assert store.calls == [("get", A, 7)]


def test_a_default_run_with_a_prompts_key_is_a_mismatch() -> None:
    b = binding_of()
    versions = {**made_versions(b), "promptsSha256": prompts_sha256(accepted_prompts(MARKED))}
    with pytest.raises(AiSettingMismatch, match="기본 판으로 만든 실행에 저장 프롬프트"):
        inputs_of(b, versions)


def test_a_default_run_whose_model_defaults_changed_is_a_mismatch() -> None:
    b = binding_of()
    versions = {**made_versions(b), "modelSettingsSha256": "0" * 64}
    with pytest.raises(AiSettingMismatch, match="기본 판의 모델 설정"):
        inputs_of(b, versions)


@pytest.mark.parametrize("prompts", [MARKED, None], ids=["text-without-key", "key-without-text"])
def test_the_text_presence_must_match_the_key_before_the_model_is_checked(prompts: AiPromptsIn | None) -> None:
    """유무가 어긋나고 모델 sha 도 다를 때 — 유무 글이 먼저다(검사 차례)."""
    b = binding_of(saved(7, prompts=prompts))
    versions: dict[str, Any] = {"aiSettingId": 7, "modelSettingsSha256": "0" * 64}
    if prompts is None:
        versions["promptsSha256"] = prompts_sha256(accepted_prompts(MARKED))
    with pytest.raises(AiSettingMismatch, match="유무"):
        inputs_of(b, versions)


@pytest.mark.parametrize("change", ["model", "prompts"])
def test_a_changed_sha_is_a_mismatch(change: str) -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    versions = made_versions(b)
    key = "modelSettingsSha256" if change == "model" else "promptsSha256"
    with pytest.raises(AiSettingMismatch, match="실행을 만들 때와 다르다"):
        inputs_of(b, {**versions, key: "0" * 64})


def test_a_saved_row_changed_after_the_run_was_made_is_a_mismatch() -> None:
    """판 행의 글·모델이 한 글자 바뀌면(판 불변을 어긴 행) 만들 때의 sha 와 다르다."""
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    versions = made_versions(b)
    for changed in (
        saved(
            7,
            prompts=prompts_body(
                tone_story="⟦TR4-tone_story⟧ 지어낸 스토리 톤!",
                style_b="⟦TR4-style_b⟧ 지어낸 문체 B",
                table_rules="⟦TR4-table_rules⟧ 지어낸 표 규칙",
            ),
        ),
        saved(
            7,
            prompts=MARKED,
            model={
                "steps": [
                    ALL_STANDARD["steps"][0],
                    {**ALL_STANDARD["steps"][1], "maxOutputTokens": 2001},
                    ALL_STANDARD["steps"][2],
                ]
            },
        ),
    ):
        with pytest.raises(AiSettingMismatch):
            inputs_of(binding_of(changed), versions)


@pytest.mark.parametrize("setting_id", [8, "7", True, 7.0])
def test_a_missing_or_odd_setting_id_is_a_mismatch(setting_id: object) -> None:
    b = binding_of(saved(7, prompts=None), applied=7)
    versions = {**made_versions(b), "aiSettingId": setting_id}
    with pytest.raises(AiSettingMismatch):
        inputs_of(b, versions)


def test_another_companys_setting_is_a_mismatch() -> None:
    b = binding_of(saved(7, prompts=None), company=B, applied=7)
    versions = made_versions(b, B)
    assert inputs_of(b, versions, B).models != DEFAULT_MODELS  # 분모: 제 회사면 판 값
    with pytest.raises(AiSettingMismatch, match="그 회사에 없다"):
        inputs_of(b, versions, A)


def test_a_saved_text_the_narrowed_rules_refuse_is_a_mismatch_with_its_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """만든 뒤 받기가 좁아짐 → 저장 글을 다시 받는 자리가 거절을 잡는다(검증 ② M2 — 다시 받기를 빼면 빨강)."""
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    versions = made_versions(b)
    narrow(monkeypatch)
    with pytest.raises(AiSettingMismatch, match="프롬프트 글을 지금 받기로 다시 받을 수 없다: ai_prompt_text_length"):
        inputs_of(b, versions)


def test_a_saved_model_the_narrowed_rules_refuse_is_a_mismatch_with_its_code(monkeypatch: pytest.MonkeyPatch) -> None:
    b = binding_of(saved(7, prompts=None), applied=7)
    b.models = FileModels(CONFIG)  # 이 시험만의 원천(아래에서 좁힌다)
    versions = made_versions(b)
    narrowed = tuple(dataclasses.replace(spec, routes=(LIGHT,)) for spec in pm.MODELS)  # standard 를 칸 경로에서 뺀다
    monkeypatch.setattr(b.models, "steps", lambda: narrowed)
    with pytest.raises(AiSettingMismatch, match="모델 설정을 지금 받기로 다시 받을 수 없다: ai_model_"):
        inputs_of(b, versions)


def test_a_mismatch_is_the_core_error() -> None:
    assert AiSettingMismatch is RunVersionsMismatch


# ── 판 값이 공급사 요청까지 ──


def test_the_saved_texts_and_models_reach_the_provider() -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    inputs = dataclasses.replace(
        inputs_of(b, made_versions(b)),
        part="story",
    )
    openai = MockProvider("openai")
    for _ in range(40):
        openai.enqueue(answer)
    run_flow(
        colab.FLOW,
        inputs,
        colab.TranslationAdapters(llm=client({"openai": openai}), tenant="1", mock=False, spent_usd=lambda: 0.0),
    )
    systems = ["".join(s.text for s in call.system) for call in openai.calls]
    assert any("⟦TR4-tone_story⟧" in s and "⟦TR4-style_b⟧" in s for s in systems)
    assert all("⟦TR4-" not in repr(call.user) for call in openai.calls)  # user 0
    translate = [c for c in openai.calls if "ESG report proofreader" not in "".join(s.text for s in c.system)]
    assert translate and all(c.max_output_tokens <= 2000 for c in translate)  # 그 밖 파트 칸 위끝 2000(min)
