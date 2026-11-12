"""끼움 MaterialityBinding 의 AI 설정 판(밴드 IR4 §3-4-1·2 — 순수 층, DB 0). 판 포트는 가짜(settings_store.py),
모델 원천은 저장소 정본 models.json(실제 파일 — 모의 경로 0). 데이터 검증 test_binding_156_settings.py 의 꼴.

    3-4-1  versions_with: 기본 판 = versions + aiSetting 「기본 설정」 + core ai_versions(None, 명세 기본값) · 저장 판 =
           판 이름 + ai_versions(판 id, 다시 받은 모델, 다시 받은 글|None) · 다시 받기 거절 → RunVersionsRejected
    3-4-2  inputs_with: 저장 판 → texts_from·models_from(research·analysis 의 route·temperature·위끝) · 코드 글 판 →
           DEFAULT_TEXTS · 기본 판·옛 실행 → 코드 값(흐름 상수) · 열쇠만/글만·기본 판에 열쇠 → mismatch(유무
           검사가 모델 대조보다 먼저) · sha 다름·없는 판·남의 회사 판·int 아닌 id → mismatch · 만든 뒤 받기가
           좁아짐 → mismatch(code 를 글에) · 진행 중 실행은 만들 때의 판(적용을 바꿔도 get 만)
    + 판 글·temperature·위끝이 1부·2부를 지나 공급사 요청에 닿는다(표지 — 업무 층 양성은
      test_runs_materiality_settings.py)
글은 지어낸 것이다. 실제 AI 호출 0.
"""

import dataclasses
from typing import Any

import pytest

from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.core.calc.ai_settings import AcceptedModelSettings, AcceptedPrompts, ai_versions, defaults, prompts_sha256
from esgapi.core.calc.ai_settings import model_settings_sha256 as model_sha
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.flows.binding import RunVersionsMismatch, RunVersionsRejected
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.materiality.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.materiality.flows import colab_155, part2_155
from esgapi.materiality.flows import prompt_model_155 as pm
from esgapi.materiality.flows.binding_155 import CODE_MODELS, AiSettingMismatch, MaterialityBinding, SavedSetting
from esgapi.materiality.flows.colab_155 import DEFAULT_TEXTS, StageModel
from esgapi.materiality.flows.iro_155 import IroInputs
from esgapi.materiality.tests.flows import support
from esgapi.materiality.tests.flows.settings_store import FakeStore, FileModels
from esgapi.materiality.tests.flows.support import options
from esgapi.materiality.tests.flows.test_prompt_model_155 import (
    CONFIG,
    LEGACY,
    OLD_TEXT,
    accepted_prompts,
    legacy_body,
    model_body,
    prompts_body,
)

A, B = 1, 2
MODELS = FileModels(CONFIG)
DEFAULT_MODEL_SHA = model_sha(defaults(CONFIG, pm.MODELS))
EDITED: AiModelSettingsIn = model_body(temperature=0.3, cap=8000, analysis_cap=9000)
MARKED = prompts_body(
    impact_system="⟦IR4-impact_system⟧ 지어낸 영향 지시 글",
    regulation_prefix=pm.default_text("regulation_prefix") + "⟦IR4-regulation_prefix⟧",
    whitelist_non_financial=pm.default_text("whitelist_non_financial") + "⟦IR4-whitelist_non_financial⟧",
    whitelist_financial=pm.default_text("whitelist_financial") + "⟦IR4-whitelist_financial⟧",
)


def accepted_model(given: AiModelSettingsIn) -> AcceptedModelSettings:
    found = pm.accept_model(CONFIG, given)
    assert isinstance(found, AcceptedModelSettings), found
    return found


def saved(setting_id: int, *, prompts: AiPromptsIn | None, model: AiModelSettingsIn = EDITED) -> SavedSetting:
    return SavedSetting(id=setting_id, name=f"v{setting_id}", model_settings=model, prompts=prompts)


def binding_of(*settings: SavedSetting, company: int = A, applied: int | None = None) -> MaterialityBinding:
    store = FakeStore(saved={company: list(settings)}, applied_id={} if applied is None else {company: applied})
    return MaterialityBinding(settings=store, models=MODELS)


def made_versions(binding: MaterialityBinding, company: int = A) -> dict[str, object]:
    return binding.versions_with(options(), company_id=company)


def inputs_of(binding: MaterialityBinding, versions: dict[str, object], company: int = A) -> IroInputs:
    return binding.inputs_with(options(), company_id=company, versions=versions)


def model_of(inputs: IroInputs) -> tuple[StageModel, StageModel]:
    return (inputs.research, inputs.analysis)


EDITED_MODELS = (
    StageModel(route=colab_155.ROUTE, temperature=0.3, max_output_tokens=8000),
    StageModel(route=part2_155.ROUTE_PART2, temperature=None, max_output_tokens=9000),
)


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
        saved(7, prompts=None, model=model_body(analysis_temperature=0.3)),
        saved(7, prompts=None, model=model_body(route="light-openai-41")),
        saved(7, prompts=prompts_body(impact_input="자리를 지운 지어낸 글")),
        saved(7, prompts=prompts_body(regulation_system="신뢰 출처 자리를 지운 지어낸 지시 글")),
        saved(7, prompts=prompts_body(impact_system="가" * 9_000)),
    ],
    ids=["research-temperature-null", "analysis-temperature", "route", "slot", "whitelist-slot", "text-length"],
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
    """판의 temperature·위끝·경로가 흐름 입력에 — 끼움이 코드 상수를 넣으면 빨강."""
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    inputs = inputs_of(b, made_versions(b))
    assert inputs.texts == pm.texts_from(accepted_prompts(MARKED))
    assert inputs.texts.impact_system.startswith("⟦IR4-impact_system⟧") and inputs.texts != DEFAULT_TEXTS
    assert model_of(inputs) == EDITED_MODELS
    assert model_of(inputs) != CODE_MODELS


def test_a_code_text_setting_gives_the_default_texts_and_its_model_values() -> None:
    b = binding_of(saved(7, prompts=None), applied=7)
    inputs = inputs_of(b, made_versions(b))
    assert inputs.texts is DEFAULT_TEXTS
    assert model_of(inputs) == EDITED_MODELS


def test_the_web_search_cells_are_fixed_by_the_rules() -> None:
    """칸 webSearch 는 받기 고정값(research true · analysis false) — 뒤집으면 거절, 흐름은 칸을 읽지 않는다(372·425)."""
    for body in (model_body(web_search=False), model_body(analysis_web_search=True)):
        assert isinstance(pm.accept_model(CONFIG, body), core_ai_settings.ModelSettingRefused)


def test_the_default_setting_gives_the_code_values() -> None:
    b = binding_of()
    inputs = inputs_of(b, made_versions(b))
    assert inputs.texts is DEFAULT_TEXTS
    assert model_of(inputs) == CODE_MODELS
    assert inputs == b.inputs(options(), company_id=A)  # 판 없는 꼴과 같은 입력(기본 바이트 — §4-6 지문)


def test_the_code_models_are_the_flow_constants() -> None:
    assert CODE_MODELS == (colab_155.CODE_RESEARCH, part2_155.CODE_ANALYSIS)
    assert pm.models_from(defaults(CONFIG, pm.MODELS)) == CODE_MODELS  # 명세 기본값 = 코드 값(M4)


def test_an_old_run_without_the_keys_gives_the_code_values_whatever_is_applied() -> None:
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    old = b.versions(options())
    inputs = inputs_of(b, old)
    assert inputs.texts is DEFAULT_TEXTS
    assert model_of(inputs) == CODE_MODELS


def test_the_run_keeps_the_setting_it_was_made_with() -> None:
    """만든 뒤 적용을 바꿔도 실행은 만들 때의 판(get) — applied 를 다시 읽지 않는다(시안 「이미 돌고 있는 실행은 v1 로
    끝나요」)."""
    store = FakeStore(
        saved={A: [saved(7, prompts=MARKED), saved(8, prompts=None, model=model_body(temperature=1.5))]},
        applied_id={A: 7},
    )
    b = MaterialityBinding(settings=store, models=MODELS)
    versions = made_versions(b)
    store.applied_id[A] = 8
    store.calls.clear()
    inputs = inputs_of(b, versions)
    assert inputs.texts.impact_system.startswith("⟦IR4-impact_system⟧")
    assert inputs.research.temperature == 0.3
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
        saved(7, prompts=prompts_body(impact_system="⟦IR4-impact_system⟧ 지어낸 영향 지시 글!")),
        saved(7, prompts=MARKED, model=model_body(temperature=0.3, cap=8001, analysis_cap=9000)),
        saved(7, prompts=MARKED, model=model_body(temperature=0.31, cap=8000, analysis_cap=9000)),
        saved(7, prompts=MARKED, model=model_body(temperature=0.3, cap=8000, analysis_cap=9001)),
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
    assert model_of(inputs_of(b, versions, B)) != CODE_MODELS  # 분모: 제 회사면 판 값
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
    """모듈 규칙(자리 지킴)이 만든 뒤 좁아져도 같은 길 — accept_prompts 를 지난다."""
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    versions = made_versions(b)
    monkeypatch.setitem(
        pm.texts.REQUIRED,  # type: ignore[arg-type]  # 시험만 좁힌다(Final 사상)
        "impact_system",
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


@pytest.mark.parametrize("latest", [False, True], ids=["call", "latest"])
def test_the_saved_texts_and_model_values_reach_the_provider(latest: bool) -> None:
    received = support.received2(latest=latest)
    b = binding_of(saved(7, prompts=MARKED), applied=7)
    given = {"input": received}
    inputs = b.inputs_with(given, company_id=A, versions=b.versions_with(given, company_id=A))
    mock = MockProvider("openai")
    support.script_iro(mock, received)
    spy = support.spy2(mock)
    support.run_iro(inputs, spy)
    assert mock.pending == 0
    by_phase: dict[str, list[Any]] = {}
    for request in spy.requests:
        by_phase.setdefault(request.prompt.split("/")[1].split("@")[0], []).append(request)
    sector = "financial" if received["sector"] == "financial" else "non_financial"
    assert all(f"⟦IR4-whitelist_{sector}⟧" in r.vars["system"] for r in by_phase["regulation"])
    assert all("⟦IR4-regulation_prefix⟧" in r.vars["user"] for r in by_phase["regulation"])
    assert all(r.vars["system"].startswith("⟦IR4-impact_system⟧") for r in by_phase["impact"])
    assert not any("⟦IR4-impact_system⟧" in r.vars["system"] for p in ("financial", "pathway") for r in by_phase[p])
    part1 = [r for p in colab_155.PHASES for r in by_phase.get(p, [])]
    part2 = [r for p in part2_155.PHASES2 for r in by_phase.get(p, [])]
    assert [(r.temperature, r.max_output_tokens) for r in part1] == [(0.3, 8000)] * 5
    assert [(r.temperature, r.max_output_tokens) for r in part2] == [(None, 9000)] * 9


# ── 옛 판(칸 열일곱 — IRA3, MARC-ENT-569) ──

LEGACY_SAVED = legacy_body(impact_system="⟦IRA3-impact_system⟧ 지어낸 영향 지시 글")


def legacy_fourteen() -> AcceptedPrompts:
    found = pm.accept_stored(LEGACY_SAVED)
    assert isinstance(found, AcceptedPrompts), found
    return found


def test_an_applied_legacy_setting_makes_a_run_with_the_fourteen_sha() -> None:
    b = binding_of(saved(7, prompts=LEGACY_SAVED), applied=7)
    versions = made_versions(b)
    assert versions["promptsSha256"] == prompts_sha256(legacy_fourteen())
    assert versions["promptsSha256"] != pm.legacy_sha256(LEGACY_SAVED)
    inputs = inputs_of(b, versions)
    assert {key: getattr(inputs.texts, key) for key in LEGACY} == {key: getattr(DEFAULT_TEXTS, key) for key in LEGACY}
    assert inputs.texts.impact_system.startswith("⟦IRA3-impact_system⟧")


def test_an_old_run_made_with_the_seventeen_sha_is_rebuilt_with_the_default_three() -> None:
    """Q3: IRA3 앞에 만든 실행(versions 의 sha = 열일곱 그대로) → 지남 · 셋은 기본 글."""
    b = binding_of(saved(7, prompts=LEGACY_SAVED), applied=7)
    old = {**made_versions(b), "promptsSha256": pm.legacy_sha256(LEGACY_SAVED)}
    inputs = inputs_of(b, old)
    assert inputs.texts == pm.texts_from(legacy_fourteen())
    assert not any(OLD_TEXT in getattr(inputs.texts, f.name) for f in dataclasses.fields(inputs.texts))


def test_a_legacy_setting_with_neither_sha_is_a_mismatch() -> None:
    b = binding_of(saved(7, prompts=LEGACY_SAVED), applied=7)
    other = {**made_versions(b), "promptsSha256": prompts_sha256(accepted_prompts(prompts_body()))}
    with pytest.raises(AiSettingMismatch, match="프롬프트 글이 실행을 만들 때와 다르다"):
        inputs_of(b, other)


def test_a_legacy_setting_never_sends_its_old_three_texts() -> None:
    """옛 판의 1부 규제·키워드·이슈 user 는 기본 틀 렌더(코드 글 판과 같은 바이트) — 「⟦지어낸 옛 글⟧」 0."""
    received = support.received2()
    given = {"input": received}

    def users(binding: MaterialityBinding) -> dict[str, list[str]]:
        inputs = binding.inputs_with(given, company_id=A, versions=binding.versions_with(given, company_id=A))
        mock = MockProvider("openai")
        support.script_iro(mock, received)
        spy = support.spy2(mock)
        support.run_iro(inputs, spy)
        found: dict[str, list[str]] = {}
        for request in spy.requests:
            phase = request.prompt.split("/")[1].split("@")[0]
            if phase in colab_155.PHASES:
                found.setdefault(phase, []).append(request.vars["user"])
        return found

    legacy = users(binding_of(saved(7, prompts=legacy_body()), applied=7))
    code = users(binding_of(saved(8, prompts=None), applied=8))
    assert set(legacy) == {"regulation", "keywords", "controversy"}
    assert legacy == code
    assert not any(OLD_TEXT in user for texts in legacy.values() for user in texts)


@pytest.mark.parametrize("saved_prompts", [MARKED, LEGACY_SAVED], ids=["fourteen", "legacy"])
def test_a_null_prompts_sha_is_a_mismatch(saved_prompts: AiPromptsIn) -> None:
    """versions 의 promptsSha256 이 null 이면 열넷 판·옛 판 모두 mismatch(legacy_sha256 의 None 과 맞지 않음)."""
    b = binding_of(saved(7, prompts=saved_prompts), applied=7)
    broken = {**made_versions(b), "promptsSha256": None}
    with pytest.raises(AiSettingMismatch, match="프롬프트 글이 실행을 만들 때와 다르다"):
        inputs_of(b, broken)
