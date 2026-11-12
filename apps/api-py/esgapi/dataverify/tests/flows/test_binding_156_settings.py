"""끼움 DataverifyBinding 의 AI 설정 판(밴드 DVA1 §3-4-1·2 — 순수 층, DB 0). 판 포트는 가짜(settings_store.py), 모델
원천은 저장소 정본 models.json(실제 파일 — 모의 경로 0). 영문번역 test_binding_158_settings.py 의 꼴.

    3-4-1  versions_with: 기본 판 = versions + aiSetting 「기본 설정」 + core ai_versions(None, 명세 기본값) · 저장 판 =
           판 이름 + ai_versions(판 id, 다시 받은 모델, 다시 받은 글|None) · 다시 받기 거절 → RunVersionsRejected
    3-4-2  inputs_with: 저장 판 → texts_from·models_from(route·temperature·위끝 — 검증 ① V5) · 코드 글 판 →
           DEFAULT_TEXTS · 기본 판·옛 실행 → 코드 값(흐름 상수) · 열쇠만/글만·기본 판에 열쇠 → mismatch(유무
           검사가 모델 대조보다 먼저) · sha 다름·없는 판·남의 회사 판·int 아닌 id → mismatch · 만든 뒤 받기가
           좁아짐 → mismatch(code 를 글에) · 진행 중 실행은 만들 때의 판(적용을 바꿔도 get 만)
    + 판 글·temperature·위끝이 흐름을 지나 공급사 요청에 닿는다(표지 — 업무 층 양성은 test_runs_dataverify_settings.py)
글은 지어낸 것이다. 실제 AI 호출 0.
"""

import dataclasses
from typing import Any

import pytest

from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.core.calc.ai_settings import AcceptedModelSettings, ai_versions, defaults, prompts_sha256
from esgapi.core.calc.ai_settings import model_settings_sha256 as model_sha
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.flows.binding import RunVersionsMismatch, RunVersionsRejected
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.dataverify.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.dataverify.engines.colab_156.prompts import DEFAULT_TEXTS
from esgapi.dataverify.flows import colab_156
from esgapi.dataverify.flows import prompt_model_156 as pm
from esgapi.dataverify.flows.binding_156 import (
    CODE_MODEL,
    AiSettingMismatch,
    DataverifyBinding,
    SavedSetting,
)
from esgapi.dataverify.flows.colab_156 import DataverifyInputs
from esgapi.dataverify.tests.flows.settings_store import FakeStore, FileModels
from esgapi.dataverify.tests.flows.support import options, run, spy
from esgapi.dataverify.tests.flows.test_flow_texts import system_user, three_stages
from esgapi.dataverify.tests.flows.test_prompt_model_156 import CONFIG, accepted_prompts, model_body, prompts_body

A, B = 1, 2
MODELS = FileModels(CONFIG)
DEFAULT_MODEL_SHA = model_sha(defaults(CONFIG, pm.MODELS))
EDITED: AiModelSettingsIn = model_body(temperature=0.3, cap=8000)
MARKED = prompts_body(
    plan_system="⟦DVA1-plan_system⟧ 지어낸 계획 지시 글",
    review_user="⟦DVA1-review_user⟧ {계산 계획의 산식 목록} · {입력 데이터 JSON}",
    insight_user="⟦DVA1-insight_user⟧ {기업명} {SASB 산업분류} {중대토픽} {보고연도} {입력 데이터 JSON}",
)


def accepted_model(given: AiModelSettingsIn) -> AcceptedModelSettings:
    found = pm.accept_model(CONFIG, given)
    assert isinstance(found, AcceptedModelSettings), found
    return found


def saved(setting_id: int, *, prompts: AiPromptsIn | None, model: AiModelSettingsIn = EDITED) -> SavedSetting:
    return SavedSetting(id=setting_id, name=f"v{setting_id}", model_settings=model, prompts=prompts)


def binding_of(*settings: SavedSetting, company: int = A, applied: int | None = None) -> DataverifyBinding:
    store = FakeStore(saved={company: list(settings)}, applied_id={} if applied is None else {company: applied})
    return DataverifyBinding(settings=store, models=MODELS)


def made_versions(binding: DataverifyBinding, company: int = A) -> dict[str, object]:
    return binding.versions_with(options(), company_id=company)


def inputs_of(binding: DataverifyBinding, versions: dict[str, object], company: int = A) -> DataverifyInputs:
    return binding.inputs_with(options(), company_id=company, versions=versions)


def model_of(inputs: DataverifyInputs) -> tuple[str, float, int]:
    return (inputs.route, inputs.temperature, inputs.max_output_tokens)


CODE = (colab_156.ROUTE, colab_156.TEMPERATURE, colab_156.MAX_OUTPUT_TOKENS)


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
    assert list(versions) == [
        "engine",
        "flow",
        "promptIds",
        "route",
        "aiSetting",
        "aiSettingId",
        "modelSettingsSha256",
    ]


def test_a_code_text_setting_carries_no_prompts_key() -> None:
    b = binding_of(saved(7, prompts=None), applied=7)
    versions = made_versions(b)
    common = ai_versions(setting_id=7, model=accepted_model(EDITED), prompts=None)
    assert versions == {**b.versions(options()), "aiSetting": "v7", **common}
    assert "promptsSha256" not in versions


def test_a_saved_text_setting_carries_the_prompts_sha() -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    versions = made_versions(b)
    texts = accepted_prompts(MARKED)
    assert versions == {
        **b.versions(options()),
        "aiSetting": "v7",
        **ai_versions(setting_id=7, model=accepted_model(EDITED), prompts=texts),
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
        saved(7, prompts=None, model=model_body(temperature=None)),
        saved(7, prompts=None, model=model_body(route="light-openai-41")),
        saved(7, prompts=prompts_body(review_user="산식 자리를 지운 지어낸 글 {입력 데이터 JSON}")),
        saved(7, prompts=prompts_body(plan_system="가" * 9_000)),
    ],
    ids=["temperature-null", "route", "slot", "text-length"],
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


def test_a_saved_setting_gives_its_texts_and_model_values() -> None:
    """검증 ① V5: 판의 temperature·위끝·경로가 흐름 입력에 — 끼움이 코드 상수를 넣으면 빨강."""
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    inputs = inputs_of(b, made_versions(b))
    assert inputs.texts == pm.texts_from(accepted_prompts(MARKED))
    assert inputs.texts.plan_system.startswith("⟦DVA1-plan_system⟧") and inputs.texts != DEFAULT_TEXTS
    assert model_of(inputs) == (colab_156.ROUTE, 0.3, 8000)
    assert model_of(inputs) != CODE
    assert inputs.web_search is True  # 흐름 고정(372·303)


def test_a_code_text_setting_gives_the_default_texts_and_its_model_values() -> None:
    b = binding_of(saved(7, prompts=None), applied=7)
    inputs = inputs_of(b, made_versions(b))
    assert inputs.texts is DEFAULT_TEXTS
    assert model_of(inputs) == (colab_156.ROUTE, 0.3, 8000)


def test_the_web_search_cell_does_not_turn_the_flow_search_off() -> None:
    """칸 webSearch 는 5a 로 고정 — 받기가 false 를 거절하므로 저장 판은 늘 true, 실행도 binding 의 True."""
    assert isinstance(pm.accept_model(CONFIG, model_body(web_search=False)), core_ai_settings.ModelSettingRefused)
    b = binding_of(saved(7, prompts=None), applied=7)
    assert inputs_of(b, made_versions(b)).web_search is True


def test_the_default_setting_gives_the_code_values() -> None:
    b = binding_of()
    inputs = inputs_of(b, made_versions(b))
    assert inputs.texts is DEFAULT_TEXTS
    assert model_of(inputs) == CODE
    assert inputs == b.inputs(options(), company_id=A)  # 판 없는 꼴과 같은 입력(기본 바이트 — §4-6 지문)


def test_the_code_model_is_the_flow_constants() -> None:
    assert (CODE_MODEL.route, CODE_MODEL.temperature, CODE_MODEL.max_output_tokens) == CODE
    assert pm.models_from(defaults(CONFIG, pm.MODELS)) == CODE_MODEL  # 명세 기본값 = 코드 값


def test_an_old_run_without_the_keys_gives_the_code_values_whatever_is_applied() -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    old = b.versions(options())
    inputs = inputs_of(b, old)
    assert inputs.texts is DEFAULT_TEXTS
    assert model_of(inputs) == CODE


def test_the_run_keeps_the_setting_it_was_made_with() -> None:
    """만든 뒤 적용을 바꿔도 실행은 만들 때의 판(get) — applied 를 다시 읽지 않는다(시안 「이미 돌고 있는 실행은 v1 로
    끝나요」)."""
    store = FakeStore(
        saved={A: [saved(7, prompts=MARKED), saved(8, prompts=None, model=model_body(temperature=1.5))]},
        applied_id={A: 7},
    )
    b = DataverifyBinding(settings=store, models=MODELS)
    versions = made_versions(b)
    store.applied_id[A] = 8
    store.calls.clear()
    inputs = inputs_of(b, versions)
    assert inputs.texts.plan_system.startswith("⟦DVA1-plan_system⟧")
    assert inputs.temperature == 0.3
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
        saved(7, prompts=prompts_body(plan_system="⟦DVA1-plan_system⟧ 지어낸 계획 지시 글!")),
        saved(7, prompts=MARKED, model=model_body(temperature=0.3, cap=8001)),
        saved(7, prompts=MARKED, model=model_body(temperature=0.31, cap=8000)),
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
    assert model_of(inputs_of(b, versions, B)) != CODE  # 분모: 제 회사면 판 값
    with pytest.raises(AiSettingMismatch, match="그 회사에 없다"):
        inputs_of(b, versions, A)


def test_a_saved_text_the_narrowed_rules_refuse_is_a_mismatch_with_its_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """만든 뒤 받기가 좁아짐 → 저장 글을 다시 받는 자리가 거절을 잡는다(다시 받기를 빼면 빨강)."""
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    versions = made_versions(b)
    narrow(monkeypatch)
    with pytest.raises(AiSettingMismatch, match="프롬프트 글을 지금 받기로 다시 받을 수 없다: ai_prompt_text_length"):
        inputs_of(b, versions)


def test_a_saved_text_the_module_slot_rule_refuses_is_a_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """모듈 규칙(입력 글 자리)이 만든 뒤 좁아져도 같은 길 — accept_prompts 를 지난다."""
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    versions = made_versions(b)
    monkeypatch.setitem(
        pm.prompts.REQUIRED,  # type: ignore[arg-type]  # 시험만 좁힌다(Final 사상)
        "plan_user",
        ("{없는 자리}",),
    )
    with pytest.raises(AiSettingMismatch, match="ai_prompt_placeholder_missing"):
        inputs_of(b, versions)


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


# ── 판 값이 공급사 요청까지 ──


def test_the_saved_texts_and_model_values_reach_the_provider() -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    inputs = inputs_of(b, made_versions(b))
    mock = three_stages(MockProvider("openai"))
    llm = spy(mock)
    run(inputs, llm)
    assert len(mock.calls) == 3
    plan_system, _ = system_user(mock.calls[0])
    _, review_user = system_user(mock.calls[1])
    _, insight_user = system_user(mock.calls[2])
    assert "⟦DVA1-plan_system⟧" in plan_system
    assert "⟦DVA1-review_user⟧" in review_user and "가상 산식 1" in review_user
    assert "⟦DVA1-insight_user⟧ 가상기업" in insight_user
    assert [request.temperature for request in mock.calls] == [0.3, 0.3, 0.3]
    assert [request.max_output_tokens for request in llm.tool_requests] == [8000, 8000, 8000]
    assert {request.route for request in llm.tool_requests} == {colab_156.ROUTE}
