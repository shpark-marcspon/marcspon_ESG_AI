"""끼움의 둘째 꼴(RunFactsBinding — 밴드 G2c2 ③): 만들 때 회사의 적용 판으로 판 묶음, 돌 때 실행에 박힌 판으로 입력.
순수 층(가짜 판 포트 tests/flows/settings_store.py). 기준 글은 지어낸 것이다.

    §3-1-1  versions_with: 기본 → aiSettingId None + 지금과 같은 이름·sha · 저장 판 → 그 이름·id·다시 지은 sha
    §3-1-2  inputs_with: None·열쇠 없음 → criteria None · 값 → 그 기준표 · 없는 판·sha 다름·int 아님 → 예외
    §3-1-3  기본 판 바이트 같음: inputs_with 의 기본 갈래 입력으로 돈 메시지 해시 = 골든 sample-mock.json 12개
    §3-1-4  고친 판: inputs_with 로 지은 입력의 judge EVAL 이 그 판의 조립 글(고친 줄만 다름)
    G2c3 §3-2-4  받기 규칙이 좁아져 저장 판을 못 받음: versions_with → RunVersionsRejected(글에 판 이름만),
            inputs_with → RunVersionsMismatch(실행기 error_code versions_mismatch — MARC-ENT-352)
"""

import copy
import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AiStepSpec,
    check_model_settings,
    defaults,
    model_settings_sha256,
    to_input,
)
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn
from esgapi.core.flows.binding import (
    DocumentInput,
    RunBinding,
    RunFactsBinding,
    RunVersionsMismatch,
    RunVersionsRejected,
)
from esgapi.core.llm.config import LlmConfig
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.engines.e0.ports import ScriptedChat
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import criteria_e0, prompt_model_e0
from esgapi.greenwash.flows.binding_e0 import AiSettingMismatch, GreenwashBinding, SavedSetting
from esgapi.greenwash.flows.criteria_e0 import accept_criteria, build_eval_prompt, default_criteria
from esgapi.greenwash.flows.prompt_model_e0 import STEPS
from esgapi.greenwash.service.selectors import ai_settings as selectors
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.flows import test_criteria_flow as flow_cases
from esgapi.greenwash.tests.flows.settings_store import DefaultOnlyStore, FakeStore
from esgapi.greenwash.tests.flows.support import REAL_MODELS

A, B = 11, 22
DOCUMENT = DocumentInput(content=s.SAMPLE_BYTES, media_type="application/pdf", file_name=s.SAMPLE_NAME)
OPTIONS: dict[str, object] = {"parts": {"ceo": [1], "company": [2], "climate": [3, 4]}}
EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "contract-examples" / "criteria"
STORED_DEFAULT = to_input(defaults(REAL_MODELS.config(), STEPS))
"""이행(0003)된 옛 행·기본값으로 저장한 판의 모델 설정(R1 갈래 — inputs.model None)."""
DEFAULT_MODEL_SHA = model_settings_sha256(defaults(REAL_MODELS.config(), STEPS))


def edited(name: str = "v3") -> GreenwashCriteria:
    """웹 목의 고친 판 예시를 받기에 넣고 서버 이름으로 덮은 것(저장된 판의 꼴)."""
    accepted = accept_criteria(json.loads((EXAMPLES / "criteria-edited.json").read_text(encoding="utf-8")))
    return {**accepted, "version": name}


def store_with(applied: bool = True) -> FakeStore:
    store = FakeStore(
        saved={
            A: [
                SavedSetting(
                    id=7, name="v3", criteria=edited(), model_settings=STORED_DEFAULT, prompts=None, terms=None
                )
            ]
        }
    )
    if applied:
        store.applied_id[A] = 7
    return store


def test_the_greenwash_binding_has_both_shapes() -> None:
    binding = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore())
    assert isinstance(binding, RunFactsBinding)
    plain: RunBinding = binding
    assert plain.versions(OPTIONS) == colab.run_versions(None)  # 옛 꼴은 기본 판 그대로


# ── §3-1-1 versions_with ──


def test_versions_with_the_default_setting() -> None:
    got = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).versions_with(OPTIONS, company_id=A)
    assert got == {**colab.run_versions(None), "aiSettingId": None, "modelSettingsSha256": DEFAULT_MODEL_SHA}
    assert got["aiSetting"] == "colab-2026-01-15-v1"


def test_versions_with_a_saved_setting_rebuilds_its_sha() -> None:
    store = store_with()
    got = GreenwashBinding(models=REAL_MODELS, store=store).versions_with(OPTIONS, company_id=A)
    assert got == {
        "aiSetting": "v3",
        "evalPromptSha256": colab.run_versions(edited())["evalPromptSha256"],
        "aiSettingId": 7,
        "modelSettingsSha256": DEFAULT_MODEL_SHA,
    }
    assert got["evalPromptSha256"] != colab.run_versions(None)["evalPromptSha256"]
    assert store.calls == [("applied", A, None)]
    # 다른 회사는 그 회사의 적용 판(없음 = 기본)
    assert GreenwashBinding(models=REAL_MODELS, store=store).versions_with(OPTIONS, company_id=B)["aiSettingId"] is None


# ── §3-1-2 inputs_with ──


@pytest.mark.parametrize(
    "versions",
    [
        pytest.param({**colab.run_versions(None), "aiSettingId": None}, id="default"),
        pytest.param(colab.run_versions(None), id="no-key-g1b-run"),
    ],
)
def test_inputs_with_no_setting_is_the_current_path(versions: dict[str, object]) -> None:
    store = store_with()
    binding = GreenwashBinding(models=REAL_MODELS, store=store)
    got = binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions)
    assert got.criteria is None
    assert got == binding.inputs(DOCUMENT, OPTIONS) == s.inputs()
    assert store.calls == []  # 판을 읽지 않는다


def test_inputs_with_a_setting_reads_that_version() -> None:
    store = store_with(applied=False)  # 지금 적용과 무관하게 versions 의 id 로 읽는다
    binding = GreenwashBinding(models=REAL_MODELS, store=store)
    versions = {
        "aiSetting": "v3",
        "evalPromptSha256": colab.run_versions(edited())["evalPromptSha256"],
        "aiSettingId": 7,
    }
    got = binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions)
    assert got.criteria == edited()
    assert store.calls == [("get", A, 7)]
    base = binding.inputs(DOCUMENT, OPTIONS)
    assert (got.ceo, got.company, got.climate, got.extra_terms, got.dry_run) == (
        base.ceo,
        base.company,
        base.climate,
        base.extra_terms,
        False,
    )


@pytest.mark.parametrize(
    ("company_id", "versions", "match"),
    [
        pytest.param(A, {"evalPromptSha256": "x", "aiSettingId": 99}, "없다", id="missing"),
        pytest.param(B, {"evalPromptSha256": "x", "aiSettingId": 7}, "없다", id="other-company"),
        pytest.param(A, {"evalPromptSha256": "0" * 64, "aiSettingId": 7}, "다르다", id="sha-differs"),
        pytest.param(A, {"evalPromptSha256": "x", "aiSettingId": "7"}, "int", id="id-text"),
        pytest.param(A, {"evalPromptSha256": "x", "aiSettingId": True}, "int", id="id-bool"),
        pytest.param(A, {"evalPromptSha256": "0" * 64, "aiSettingId": None}, "기본 판", id="default-sha-differs"),
    ],
)
def test_inputs_with_a_wrong_setting_fails(company_id: int, versions: dict[str, object], match: str) -> None:
    with pytest.raises(AiSettingMismatch, match=match):
        GreenwashBinding(models=REAL_MODELS, store=store_with()).inputs_with(
            DOCUMENT, OPTIONS, company_id=company_id, versions=versions
        )


def narrow(monkeypatch: pytest.MonkeyPatch, criteria: GreenwashCriteria) -> None:
    """받기 규칙을 좁힌다: 기준 글 상한을 그 기준표의 가장 긴 글 − 1 로(저장할 때는 받았던 판이 이제 거절된다)."""
    monkeypatch.setattr(criteria_e0, "TEXT_CHARS", max(len(row["text"]) for row in criteria["rows"]) - 1)


def test_versions_with_a_version_the_rules_no_longer_take_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    texts = [row["text"] for row in edited()["rows"]]  # 좁히기 전에 읽는다(edited 도 받기를 거친다)
    binding = GreenwashBinding(models=REAL_MODELS, store=store_with())
    assert binding.versions_with(OPTIONS, company_id=A)["aiSettingId"] == 7  # 분모: 좁히기 전엔 지어진다
    narrow(monkeypatch, edited())
    with pytest.raises(RunVersionsRejected) as refused:
        binding.versions_with(OPTIONS, company_id=A)
    message = refused.value.message
    assert "(v3)" in message
    assert not [text for text in texts if text in message]  # 기준 글 0
    assert str(A) not in message  # 회사 id 0
    assert binding.versions_with(OPTIONS, company_id=B)["aiSettingId"] is None  # 기본 판 갈래는 좁혀도 그대로


def test_inputs_with_a_version_the_rules_no_longer_take_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = GreenwashBinding(models=REAL_MODELS, store=store_with())
    versions = binding.versions_with(OPTIONS, company_id=A)
    assert binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions).criteria is not None  # 분모
    narrow(monkeypatch, edited())
    with pytest.raises(RunVersionsMismatch, match="다시 지을 수 없다"):
        binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions)
    assert AiSettingMismatch is RunVersionsMismatch  # 실행기 표는 `<모듈>.<qualname>` 으로(RE1)(G2c2 이름은 별칭)


# ── §3-1-3 기본 판 바이트 같음 ──


def test_the_default_path_sends_the_golden_messages() -> None:
    gw1 = s.golden("sample-mock.json")
    binding = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore())
    versions = binding.versions_with(OPTIONS, company_id=A)
    chat = ScriptedChat()
    result = s.result_of(
        s.run(binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions), s.adapters(llm=chat))
    )
    assert s.message_hashes(chat.sent) == gw1["messages"] and len(gw1["messages"]) == 12
    plain = s.result_of(s.run(s.inputs(), s.adapters()))
    assert json.dumps(result, ensure_ascii=False).encode("utf-8") == json.dumps(plain, ensure_ascii=False).encode(
        "utf-8"
    )


# ── §3-1-4 고친 판 ──


def test_the_saved_setting_reaches_the_judge_as_its_eval() -> None:
    store = store_with()
    binding = GreenwashBinding(models=REAL_MODELS, store=store)
    versions = binding.versions_with(OPTIONS, company_id=A)
    built = binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions)
    pack = colab.eval_pack(edited(), PROMPT_VERSION)
    mock = flow_cases.scripted_provider(20, pack)
    s.run(built, s.adapters(llm=flow_cases.bridge(mock, MemorySink())))
    systems = [system for system, _ in flow_cases.pairs(mock.calls)]
    edited_eval = build_eval_prompt(edited(), PROMPT_VERSION)
    assert systems.count(edited_eval) == 4  # 판정 넷이 고친 판의 조립 글
    assert default_prompts(PROMPT_VERSION).eval_system_prompt not in systems
    assert edited_eval != default_prompts(PROMPT_VERSION).eval_system_prompt


def test_a_store_is_required() -> None:
    nothing: dict[str, Any] = {}
    with pytest.raises(TypeError, match="store"):
        GreenwashBinding(**nothing)


def test_the_default_criteria_saved_as_a_version_keep_the_default_eval() -> None:
    """기본 판과 같은 15줄을 저장한 판은 판 이름만 다르고 EVAL 의 sha 는 같다(판 글자는 조립 첫 줄의 판 글자뿐)."""
    same = copy.deepcopy(default_criteria())
    same["version"] = "v1"
    assert colab.run_versions(same)["evalPromptSha256"] == colab.run_versions(None)["evalPromptSha256"]


# ── AS2b 3-4 판의 모델 설정(versions·inputs) ──

STANDARD: AiModelSettingsIn = {
    "steps": [
        {"key": "judge", "route": "standard-openai-41", "temperature": 0.7, "webSearch": False, "maxOutputTokens": 2000}
    ]
}


def accepted(given: AiModelSettingsIn) -> AcceptedModelSettings:
    found = check_model_settings(REAL_MODELS.config(), given, steps=STEPS)
    assert isinstance(found, AcceptedModelSettings), found
    return found


def store_of(model_settings: AiModelSettingsIn) -> FakeStore:
    saved = SavedSetting(id=7, name="v3", criteria=edited(), model_settings=model_settings, prompts=None, terms=None)
    return FakeStore(saved={A: [saved]}, applied_id={A: 7})


class Models:
    """설정만 바꾼 원천(워커 쪽 — ★E). config 를 replace 로 고쳐 넘긴다."""

    def __init__(self, config: LlmConfig, steps: Sequence[AiStepSpec] = STEPS) -> None:
        self.config_value = config
        self.steps_value = steps

    def config(self) -> LlmConfig:
        return self.config_value

    def steps(self) -> Sequence[AiStepSpec]:
        return self.steps_value


def test_versions_with_carry_the_model_settings_sha() -> None:
    """3-4-2: 기본 판·저장 판 열쇠 다섯, sha == model_settings_sha256(받은 값)."""
    default = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).versions_with(OPTIONS, company_id=A)
    saved = GreenwashBinding(models=REAL_MODELS, store=store_of(STANDARD)).versions_with(OPTIONS, company_id=A)
    keys = ["aiSetting", "aiSettingId", "evalPromptSha256", "modelSettingsSha256"]
    assert sorted(default) == sorted(saved) == keys  # + 실행기가 flow 를 더해 다섯
    assert default["modelSettingsSha256"] == model_settings_sha256(defaults(REAL_MODELS.config(), STEPS))
    assert saved["modelSettingsSha256"] == model_settings_sha256(accepted(STANDARD))
    assert saved["modelSettingsSha256"] != default["modelSettingsSha256"]


def test_inputs_with_carry_the_judge_step_unless_it_is_the_default() -> None:
    """3-4-3: 저장 판 → 받은 judge 단계 · 기본 판·옛 실행·기본값과 같은 저장 판 → None(지은 그대로)."""
    binding = GreenwashBinding(models=REAL_MODELS, store=store_of(STANDARD))
    versions = binding.versions_with(OPTIONS, company_id=A)
    got = binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions)
    assert got.model == accepted(STANDARD).steps[0]
    assert got.model is not None
    assert (got.model.route, got.model.temperature, got.model.max_output_tokens) == ("standard-openai-41", 0.7, 2000)
    old = {k: v for k, v in versions.items() if k != "modelSettingsSha256"}  # AS2b 앞에 만든 실행(처분 B2)
    assert binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=old).model is None

    same = GreenwashBinding(models=REAL_MODELS, store=store_of(STORED_DEFAULT))
    same_versions = same.versions_with(OPTIONS, company_id=A)
    assert same.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=same_versions).model is None

    plain = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore())
    default_versions = plain.versions_with(OPTIONS, company_id=A)
    assert plain.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=default_versions).model is None


@pytest.mark.parametrize("change", ["pair", "cap", "route", "default-temperature"])
def test_inputs_with_a_model_that_moved_fails(change: str) -> None:
    """3-4-5~8 의 순수 몫: 만든 뒤 워커 원천의 짝·상한·명세·기본값이 바뀌면 AiSettingMismatch(versions_mismatch)."""
    config = REAL_MODELS.config()
    made = GreenwashBinding(models=REAL_MODELS, store=store_of(STANDARD))
    store = store_of(STANDARD)
    if change == "default-temperature":
        made = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore())
        store = DefaultOnlyStore()
    versions = made.versions_with(OPTIONS, company_id=A)
    if change == "pair":
        worker = Models(replace(config, routes={**config.routes, "standard-openai-41": ("gpt-4.1-mini",)}))
    elif change == "cap":  # 그 모델의 출력 상한이 2000 아래로(처분 1 — 다시 받기 거절 ai_model_max_output_range)
        model = config.models["gpt-4.1"]
        lowered = replace(model, entry=model.entry.model_copy(update={"max_output_tokens": 1000}))
        worker = Models(replace(config, models={**config.models, "gpt-4.1": lowered}))
    elif change == "route":
        worker = Models(config, tuple(replace(spec, routes=("light-openai-41",)) for spec in STEPS))
    else:
        judge = replace(STEPS[0], default={**copy.deepcopy(STEPS[0].default), "temperature": 0.5})
        worker = Models(config, (judge,))
    with pytest.raises(AiSettingMismatch, match="모델 설정"):
        GreenwashBinding(models=worker, store=store).inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions)
    # 분모: 원천이 그대로면 지난다
    GreenwashBinding(models=REAL_MODELS, store=store).inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions)


def test_the_real_binding_defaults_are_the_judge_default() -> None:
    """3-4-9(★H): 지은 다리의 경로·온도·상한 == JUDGE.default(복사본으로 견줌 — L1), 원천의 명세는 STEPS 그 자체."""
    judge = copy.deepcopy(dict(prompt_model_e0.JUDGE.default))
    binding = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore())
    assert binding.chat_route == judge["route"]
    assert (judge["temperature"], judge["maxOutputTokens"]) == (colab.TEMPERATURE, colab.MAX_OUTPUT_TOKENS)
    assert selectors.RunModelSource().steps() is STEPS
