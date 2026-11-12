"""끼움 DraftingBinding 의 AI 설정 판(밴드 RPA1 B6·B8 — 순수 층, DB 0). 판 포트는 가짜(settings_store.py), 모델 원천은
저장소 정본 models.json(실제 파일 — 모의 경로 0). 데이터 검증 test_binding_156_settings.py 의 꼴.

    versions_with  기본 판 = 지금 열쇠 + aiSetting 「기본 설정」 + core ai_versions(None, 명세 기본값) · 저장 판 =
                   판 이름 + ai_versions(판 id, 다시 받은 모델, 다시 받은 글|None) · 다시 받기 거절 →
                   RunVersionsRejected · 프로젝트 판정이 먼저(판 읽기 0)
    inputs_with    저장 판 → texts_from·models_from(칸 둘의 route·temperature·위끝) · 코드 글 판 → DEFAULT_TEXTS ·
                   기본 판·옛 실행 → 코드 값(흐름 상수) · 열쇠만/글만·기본 판에 열쇠 → mismatch(유무 검사가 모델
                   대조보다 먼저) · sha 다름·없는 판·남의 회사 판·int 아닌 id → mismatch · 만든 뒤 받기가 좁아짐 →
                   mismatch · 진행 중 실행은 만들 때의 판(적용을 바꿔도 get 만)
    B8 이어 받기   앞 실행과 AI 열쇠가 다르면 versions_same False(판이 다르면 처음부터), 같으면 True · AI 열쇠가 없는
                   앞 실행(RPA1 앞)도 False
    포트           settings·models 기본값 없음
글은 지어낸 것이다. 실제 AI 호출 0.
"""

import dataclasses
from typing import Any

import pytest

from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.core.calc.ai_settings import AcceptedModelSettings, PromptRefused, ai_versions, defaults, prompts_sha256
from esgapi.core.calc.ai_settings import model_settings_sha256 as model_sha
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.flows.binding import RunVersionsMismatch, RunVersionsRejected
from esgapi.drafting.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.drafting.engines.v2.texts import DEFAULT_TEXTS
from esgapi.drafting.flows import draft_v2
from esgapi.drafting.flows import prompt_model_v2 as pm
from esgapi.drafting.flows.binding_v2 import AiSettingMismatch, BaseFacts, DraftingBinding, SavedSetting
from esgapi.drafting.flows.draft_v2 import CODE_MODELS, DraftInputs, StageModel, StageModels
from esgapi.drafting.tests.flows.settings_store import DefaultOnlyStore, FakeStore, FileModels
from esgapi.drafting.tests.flows.support import base_result
from esgapi.drafting.tests.flows.test_binding_v2 import A, B, NoArtifacts, Source, source
from esgapi.drafting.tests.flows.test_prompt_model_v2 import CONFIG, accepted_prompts, model_body, prompts_body

OPTIONS = {"projectId": 7}
MODELS = FileModels(CONFIG)
DEFAULT_MODEL_SHA = model_sha(defaults(CONFIG, pm.MODELS))
EDITED: AiModelSettingsIn = {
    "steps": [
        {"key": "map", "route": "light-openai-41", "temperature": 0.2, "webSearch": False, "maxOutputTokens": 3000},
        {
            "key": "draft",
            "route": "standard-openai-41",
            "temperature": 0.7,
            "webSearch": False,
            "maxOutputTokens": 6000,
        },
    ]
}
MARKED_DRAFT_USER = "⟦RPA1-draft_user⟧ {제목 경로} · {요구 내용} · {페이지 글}"
MARKED = prompts_body(map_system="⟦RPA1-map_system⟧ 지어낸 쪽 붙이기 지시 글", draft_user=MARKED_DRAFT_USER)


def accepted_model(given: AiModelSettingsIn) -> AcceptedModelSettings:
    found = pm.accept_model(CONFIG, given)
    assert isinstance(found, AcceptedModelSettings), found
    return found


def saved(setting_id: int, *, prompts: AiPromptsIn | None, model: AiModelSettingsIn = EDITED) -> SavedSetting:
    return SavedSetting(id=setting_id, name=f"v{setting_id}", model_settings=model, prompts=prompts)


def with_company_b(found: Source) -> Source:
    """회사 B 에도 같은 프로젝트·목차·문서(남의 회사의 판을 읽지 않는지 보는 분모)."""
    for (_, key), value in list(found.projects.items()):
        found.projects[(B, key)] = value
    for (_, key), value in list(found.outlines.items()):
        found.outlines[(B, key)] = value
    for (_, key), value in list(found.documents.items()):
        found.documents[(B, key)] = value
    return found


def binding_with(store: Any, found: Source | None = None) -> DraftingBinding:
    chosen = found or with_company_b(source())
    return DraftingBinding(
        projects=chosen,
        max_usd=lambda: 2.5,
        mock=lambda: False,
        spent_usd=lambda c, r: 0.0,
        artifacts=NoArtifacts(),
        bases=chosen,
        settings=store,
        models=MODELS,
    )


def binding_of(*settings: SavedSetting, company: int = A, applied: int | None = None) -> DraftingBinding:
    store = FakeStore(saved={company: list(settings)}, applied_id={} if applied is None else {company: applied})
    return binding_with(store)


def made_versions(binding: DraftingBinding, company: int = A) -> dict[str, object]:
    return binding.versions_with(OPTIONS, company_id=company)


def inputs_of(binding: DraftingBinding, versions: dict[str, object], company: int = A) -> DraftInputs:
    return binding.inputs_with(OPTIONS, company_id=company, versions=versions)


def facts(binding: DraftingBinding, company: int = A) -> dict[str, object]:
    """AI 열쇠를 뺀 versions_with(RPA1 앞의 열쇠 전부)."""
    return {k: v for k, v in made_versions(binding, company).items() if k not in AI_KEYS}


AI_KEYS = ("aiSetting", "aiSettingId", "modelSettingsSha256", "promptsSha256")
EDITED_MODELS = StageModels(
    map=StageModel(route="light-openai-41", temperature=0.2, max_output_tokens=3000),
    draft=StageModel(route="standard-openai-41", temperature=0.7, max_output_tokens=6000),
)


def narrow(monkeypatch: pytest.MonkeyPatch) -> None:
    """받기 규칙을 좁힌다: 글 상한을 10자로(저장할 때는 받았던 글이 이제 거절된다)."""
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)


# ── versions_with ──


def test_the_default_setting_adds_the_title_and_the_core_keys() -> None:
    b = binding_of()
    versions = made_versions(b)
    common = ai_versions(setting_id=None, model=defaults(CONFIG, pm.MODELS), prompts=None)
    assert versions == {**facts(b), "aiSetting": DEFAULT_TITLE, **common}
    assert common == {"aiSettingId": None, "modelSettingsSha256": DEFAULT_MODEL_SHA}
    assert list(versions)[-3:] == ["aiSetting", "aiSettingId", "modelSettingsSha256"]
    assert DEFAULT_TITLE == "기본 설정"


def test_a_code_text_setting_carries_no_prompts_key() -> None:
    b = binding_of(saved(7, prompts=None), applied=7)
    versions = made_versions(b)
    common = ai_versions(setting_id=7, model=accepted_model(EDITED), prompts=None)
    assert versions == {**facts(b), "aiSetting": "v7", **common}
    assert "promptsSha256" not in versions


def test_a_saved_text_setting_carries_the_prompts_sha() -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    versions = made_versions(b)
    texts = accepted_prompts(MARKED)
    assert versions == {
        **facts(b),
        "aiSetting": "v7",
        **ai_versions(setting_id=7, model=accepted_model(EDITED), prompts=texts),
    }
    assert versions["promptsSha256"] == prompts_sha256(texts)
    assert versions["modelSettingsSha256"] != DEFAULT_MODEL_SHA


def test_another_companys_applied_setting_is_not_read() -> None:
    b = binding_of(saved(7, prompts=MARKED), company=B, applied=7)
    assert made_versions(b, A)["aiSettingId"] is None
    assert made_versions(b, B)["aiSettingId"] == 7


def test_the_project_is_judged_before_the_setting_is_read() -> None:
    store = FakeStore(saved={A: [saved(7, prompts=None)]}, applied_id={A: 7})
    with pytest.raises(RunVersionsRejected):
        binding_with(store).versions_with({"projectId": 99}, company_id=A)
    assert store.calls == []


@pytest.mark.parametrize(
    "setting",
    [
        saved(7, prompts=None, model=model_body(temperature=None)),
        saved(7, prompts=None, model=model_body(route="mock")),
        saved(7, prompts=prompts_body(map_user="목차 자리를 지운 지어낸 글 {페이지 글}")),
        saved(7, prompts=prompts_body(map_system="가" * 9_000)),
        saved(7, prompts=prompts_body(map_user="⟦RPA4 옛 자리⟧ {목차}\n{쪽 글}")),
    ],
    ids=["temperature-null", "route", "slot", "text-length", "rpa4-old-slot"],
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


# ── inputs_with ──


def test_a_saved_setting_gives_its_texts_and_both_slots_model_values() -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    inputs = inputs_of(b, made_versions(b))
    assert inputs.texts == pm.texts_from(accepted_prompts(MARKED))
    assert inputs.texts.map_system.startswith("⟦RPA1-map_system⟧") and inputs.texts != DEFAULT_TEXTS
    assert inputs.models == EDITED_MODELS
    assert inputs.models != CODE_MODELS


def test_a_code_text_setting_gives_the_default_texts_and_its_model_values() -> None:
    b = binding_of(saved(7, prompts=None), applied=7)
    inputs = inputs_of(b, made_versions(b))
    assert inputs.texts is DEFAULT_TEXTS
    assert inputs.models == EDITED_MODELS


def test_the_default_setting_gives_the_code_values() -> None:
    b = binding_of()
    inputs = inputs_of(b, made_versions(b))
    assert inputs.texts is DEFAULT_TEXTS
    assert inputs.models is CODE_MODELS
    assert inputs == b.inputs(OPTIONS, company_id=A)


def test_the_code_models_are_the_flow_constants() -> None:
    code = StageModel(
        route=draft_v2.ROUTE, temperature=draft_v2.TEMPERATURE, max_output_tokens=draft_v2.MAX_OUTPUT_TOKENS
    )
    assert StageModels(map=code, draft=code) == CODE_MODELS
    assert pm.models_from(defaults(CONFIG, pm.MODELS)) == CODE_MODELS  # 명세 기본값 = 코드 값


def test_models_from_picks_each_slot_by_its_key() -> None:
    assert pm.models_from(accepted_model(EDITED)) == EDITED_MODELS
    swapped = accepted_model(EDITED)
    flipped = dataclasses.replace(swapped, steps=tuple(reversed(swapped.steps)))
    assert pm.models_from(flipped) == EDITED_MODELS  # 차례가 아니라 칸 key 로 고른다


def test_an_old_run_without_the_keys_gives_the_code_values_whatever_is_applied() -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    inputs = inputs_of(b, facts(b))
    assert inputs.texts is DEFAULT_TEXTS
    assert inputs.models is CODE_MODELS


def test_the_run_keeps_the_setting_it_was_made_with() -> None:
    """만든 뒤 적용을 바꿔도 실행은 만들 때의 판(get) — applied 를 다시 읽지 않는다."""
    store = FakeStore(
        saved={A: [saved(7, prompts=MARKED), saved(8, prompts=None, model=model_body(temperature=1.5))]},
        applied_id={A: 7},
    )
    b = binding_with(store)
    versions = made_versions(b)
    store.applied_id[A] = 8
    store.calls.clear()
    inputs = inputs_of(b, versions)
    assert inputs.texts.map_system.startswith("⟦RPA1-map_system⟧")
    assert inputs.models.draft.temperature == 0.7
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
    versions: dict[str, Any] = {**facts(b), "aiSettingId": 7, "modelSettingsSha256": "0" * 64}
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
    tweaked = dict(EDITED["steps"][1], maxOutputTokens=6001)
    for changed in (
        saved(
            7,
            prompts=prompts_body(
                map_system="⟦RPA1-map_system⟧ 지어낸 쪽 붙이기 지시 글!", draft_user=MARKED_DRAFT_USER
            ),
        ),
        saved(7, prompts=MARKED, model={"steps": [EDITED["steps"][0], tweaked]}),  # type: ignore[list-item]
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
    assert inputs_of(b, versions, B).models == EDITED_MODELS  # 분모: 제 회사면 판 값
    with pytest.raises(AiSettingMismatch, match="그 회사에 없다"):
        inputs_of(b, versions, A)


def test_a_saved_text_the_narrowed_rules_refuse_is_a_mismatch_with_its_code(monkeypatch: pytest.MonkeyPatch) -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    versions = made_versions(b)
    narrow(monkeypatch)
    with pytest.raises(AiSettingMismatch, match="프롬프트 글을 지금 받기로 다시 받을 수 없다: ai_prompt_text_length"):
        inputs_of(b, versions)


def test_rpa4_b6_a_run_queued_with_an_old_slot_text_is_a_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """RPA4 앞에 저장·큐에 든 판(입력 글 자리 `{쪽 글}`): 그때의 받기(자리 = v1 글자)로 versions 를 지은 뒤 지금 받기로
    다시 받으면 자리 거절 — 조용히 돌지 않는다(호환 코드 0, §2-5)."""
    old = prompts_body(map_user="⟦RPA4 옛 자리⟧ {목차}\n{쪽 글}")
    b = binding_of(saved(7, prompts=old), applied=7)
    with monkeypatch.context() as then:
        then.setattr(pm, "REQUIRED", {"map_user": ("{목차}", "{쪽 글}"), "draft_user": pm.REQUIRED["draft_user"]})
        versions = made_versions(b)  # 분모: 그때의 받기로는 지어진다
    assert "promptsSha256" in versions
    with pytest.raises(AiSettingMismatch, match="ai_prompt_placeholder_missing"):
        inputs_of(b, versions)


def test_rpa4_b6_the_refusal_names_the_new_slot() -> None:
    found = pm.accept_prompts(prompts_body(map_user="⟦RPA4 옛 자리⟧ {목차}\n{쪽 글}"))
    assert isinstance(found, PromptRefused)
    assert (found.code, found.message, found.field) == (
        "ai_prompt_placeholder_missing",
        "입력 글에서 {페이지 글} 자리를 지우면 안 돼요",
        "prompts.steps.0.prompts.1.text",
    )


def test_a_saved_model_the_narrowed_rules_refuse_is_a_mismatch_with_its_code(monkeypatch: pytest.MonkeyPatch) -> None:
    b = binding_of(saved(7, prompts=None), applied=7)
    b.models = FileModels(CONFIG)  # 이 시험만의 원천(아래에서 좁힌다)
    versions = made_versions(b)
    narrowed = tuple(dataclasses.replace(spec, routes=("light-openai-41",)) for spec in pm.MODELS)
    monkeypatch.setattr(b.models, "steps", lambda: narrowed)
    with pytest.raises(AiSettingMismatch, match="모델 설정을 지금 받기로 다시 받을 수 없다: ai_model_"):
        inputs_of(b, versions)


def test_a_mismatch_is_the_core_error() -> None:
    assert AiSettingMismatch is RunVersionsMismatch


def spent_nothing(company_id: int, run_id: int) -> float:
    return 0.0


def test_the_ports_have_no_defaults() -> None:
    found = source()
    common: dict[str, Any] = {
        "projects": found,
        "max_usd": lambda: 2.5,
        "mock": lambda: False,
        "spent_usd": spent_nothing,
        "artifacts": NoArtifacts(),
        "bases": found,
    }
    with pytest.raises(TypeError):
        DraftingBinding(**common, models=MODELS)
    with pytest.raises(TypeError):
        DraftingBinding(**common, settings=DefaultOnlyStore())


# ── B8 이어 받기 — AI 열쇠는 versions 에 ──


def with_base_versions(versions: dict[str, object]) -> Source:
    found = with_company_b(source())
    found.bases[(A, 50)] = BaseFacts(
        run_id=50, project_id=7, status="done", versions=versions, result=base_result(50, 11)
    )
    return found


def base_of(store: Any, base_versions: dict[str, object]) -> bool:
    """앞 실행 versions 가 base_versions 일 때, 지금 적용 판으로 만든 실행의 versions_same."""
    b = binding_with(store, with_base_versions(base_versions))
    options: dict[str, object] = {"projectId": 7, "base": {"runId": 50, "rebuild": []}}
    versions = b.versions_with(options, company_id=A)
    found = b.inputs_with(options, company_id=A, versions=versions).base
    assert found is not None
    return found.versions_same


def test_rpq1_b5_another_texts_version_is_a_mismatch_on_every_path() -> None:
    """글 판 대조는 맨 앞 — 기본 판 · 저장 판 · 옛 실행(AI 열쇠 없음) 갈래 셋 다."""
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    default = binding_with(DefaultOnlyStore())
    for found, versions in (
        (default, made_versions(default)),
        (b, made_versions(b)),
        (b, facts(b)),
    ):
        assert "texts" in versions
        with pytest.raises(RunVersionsMismatch, match="글 판"):
            inputs_of(found, {**versions, "texts": "drafting-texts@0"})
        inputs_of(found, versions)  # 분모: 판이 같으면 지어진다


def test_rpa4_b5_a_run_made_with_texts_at_1_is_a_mismatch_on_every_path() -> None:
    """RPA4 앞 글(@1)로 지은 실행은 지금 코드 글(@2)로 조용히 돌지 않는다 — 기본 판 · 저장 판 · 옛 실행 갈래 셋 다."""
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    default = binding_with(DefaultOnlyStore())
    for found, versions in (
        (default, made_versions(default)),
        (b, made_versions(b)),
        (b, facts(b)),
    ):
        assert versions["texts"] == "drafting-texts@3"
        with pytest.raises(RunVersionsMismatch, match="글 판"):
            inputs_of(found, {**versions, "texts": "drafting-texts@1"})
        inputs_of(found, versions)  # 분모


def test_rpq1_b5_a_run_without_the_texts_key_gives_the_code_texts() -> None:
    b = binding_with(DefaultOnlyStore())
    versions = made_versions(b)
    del versions["texts"]
    inputs = inputs_of(b, versions)
    assert inputs.texts is DEFAULT_TEXTS


def test_rpq1_b5_a_base_before_the_texts_key_is_not_the_same_versions() -> None:
    store = DefaultOnlyStore()
    before = made_versions(binding_with(store))
    assert base_of(store, before) is True  # 분모
    del before["texts"]
    assert base_of(store, before) is False  # RPQ1 앞 글로 지은 앞 실행은 이어 받지 않는다


def test_b8_the_same_setting_is_the_same_versions() -> None:
    store = FakeStore(saved={A: [saved(7, prompts=MARKED)]}, applied_id={A: 7})
    before = made_versions(binding_with(store))
    assert base_of(store, before) is True  # 분모: 같은 판이면 이어 받는다


@pytest.mark.parametrize("applied", [None, 8], ids=["default-now", "other-version-now"])
def test_b8_another_setting_is_not_the_same_versions(applied: int | None) -> None:
    store = FakeStore(saved={A: [saved(7, prompts=MARKED), saved(8, prompts=None)]}, applied_id={A: 7})
    before = made_versions(binding_with(store))
    store.applied_id = {} if applied is None else {A: applied}
    assert base_of(store, before) is False


def test_b8_a_run_before_rpa1_is_not_the_same_versions() -> None:
    store = DefaultOnlyStore()
    old = facts(binding_with(store))
    assert base_of(store, old) is False  # 옛 실행 → 첫 새 실행은 처음부터(처분 ⑤ — 배포 전이라 해 없음)
