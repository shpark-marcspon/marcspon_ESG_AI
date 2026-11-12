"""판의 저장 프롬프트 글로 부르는 실행 — 끼움의 versions_with·inputs_with 와 흐름의 judge(밴드 AS3a-2 §3-4, 순수 층 —
가짜 판 포트 tests/flows/settings_store.py). 업무 끝까지(3-4-3·4)는 test_binding_e0_settings_runs.py.

    3-4-1  versions_with: 저장 글 판 → evalPromptSha256 = 저장 EVAL 의 sha·promptsSha256 · 코드 글 판·기본 판 → 바닥
           dict 그대로(열쇠 없음) · 저장 글이 지금 받기에 안 맞으면 RunVersionsRejected
    3-4-2  inputs_with: 저장 글 → inputs.prompts == pack_from(받은 값) · 코드 글 → None · 열쇠만/칸만 → mismatch
           (모델 열쇠 없는 AS2b 앞 실행도) · 기본 판에 열쇠 → mismatch · 만든 뒤 받기가 좁아짐 → mismatch
    3-4-5  받기는 그대로, versions 의 promptsSha256·evalPromptSha256 가운데 하나만 바꿈 → mismatch(B2)
    3-4-6  dry-run + 저장 글 → ValueError · 다리 아닌 포트 + 기본과 다른 묶음 → TypeError(쪽 루프 밖) · 글 속
           `{{system}}` 은 공급사에 그대로 · binding_e0 는 prompt_model_e0 을 들이지 않음(AST — M2)

글은 지어낸 것이다(코드 글 앞에 지어낸 머리 한 줄 — 출력절은 그대로). 실제 AI 호출 0.
"""

import ast
from pathlib import Path

import pytest

from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.core.calc.ai_settings import AcceptedPrompts, check_prompts, prompts_sha256
from esgapi.core.contracts.ai_setting_shapes import AiPromptsIn
from esgapi.core.flows.binding import RunVersionsRejected
from esgapi.core.flows.types import FlowStepFailed
from esgapi.core.llm.log import sha256_text
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.greenwash.engines.e0.ports import ScriptedChat
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, PromptPack, default_prompts
from esgapi.greenwash.flows import binding_e0
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.binding_e0 import AiSettingMismatch, GreenwashBinding, SavedSetting
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.flows import test_criteria_flow as flow_cases
from esgapi.greenwash.tests.flows.settings_store import DefaultOnlyStore, FakeStore
from esgapi.greenwash.tests.flows.support import REAL_MODELS
from esgapi.greenwash.tests.flows.test_binding_e0_settings import (
    DEFAULT_MODEL_SHA,
    DOCUMENT,
    OPTIONS,
    STORED_DEFAULT,
    A,
    edited,
)

KEYS = ("detect", "eval", "repair", "low_only")


def code_texts() -> dict[str, str]:
    pack = default_prompts(PROMPT_VERSION)
    return {key: getattr(pack, field) for key, field in colab.PROMPT_FIELDS.items()}


def edited_texts() -> dict[str, str]:
    """넷 다 고친 글 — 출력절은 그대로 두고 머리에 지어낸 한 줄(detect 에는 글자 그대로의 `{{system}}`)."""
    heads = {key: f"[지어낸 머리 {key}]" for key in KEYS} | {"detect": "[지어낸 머리 detect {{system}}]"}
    return {key: f"{heads[key]}\n{text}" for key, text in code_texts().items()}


def prompts_in(texts: dict[str, str]) -> AiPromptsIn:
    return {
        "steps": [
            {
                "key": colab.JUDGE_STEP,
                "prompts": [{"key": key, "text": texts[key], "memo": f"지어낸 메모 {key}"} for key in KEYS],
            }
        ]
    }


SAVED = prompts_in(edited_texts())


def accepted_saved() -> AcceptedPrompts:
    found = check_prompts(SAVED, layout=colab.LAYOUT)
    assert isinstance(found, AcceptedPrompts), found
    return found


def store_of(prompts: AiPromptsIn | None) -> FakeStore:
    saved = SavedSetting(id=7, name="v3", criteria=edited(), model_settings=STORED_DEFAULT, prompts=prompts, terms=None)
    return FakeStore(saved={A: [saved]}, applied_id={A: 7})


def binding_of(prompts: AiPromptsIn | None) -> GreenwashBinding:
    return GreenwashBinding(models=REAL_MODELS, store=store_of(prompts))


def narrow(monkeypatch: pytest.MonkeyPatch) -> None:
    """받기 규칙을 좁힌다: 글 상한을 10자로(저장할 때는 받았던 글이 이제 거절된다)."""
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)


# ── 3-4-1 versions_with ──


def test_versions_with_a_saved_text_carries_both_shas() -> None:
    got = binding_of(SAVED).versions_with(OPTIONS, company_id=A)
    pack = colab.pack_from(accepted_saved())
    assert got == {
        "aiSetting": "v3",
        "evalPromptSha256": sha256_text(pack.eval_system_prompt),
        "aiSettingId": 7,
        "modelSettingsSha256": DEFAULT_MODEL_SHA,
        "promptsSha256": prompts_sha256(accepted_saved()),
    }
    assert got["evalPromptSha256"] != colab.run_versions(edited())["evalPromptSha256"]  # 기준표 EVAL 이 아니다


def test_versions_with_a_code_text_or_the_default_have_no_prompts_key() -> None:
    code = binding_of(None).versions_with(OPTIONS, company_id=A)
    assert code == {
        "aiSetting": "v3",
        "evalPromptSha256": colab.run_versions(edited())["evalPromptSha256"],
        "aiSettingId": 7,
        "modelSettingsSha256": DEFAULT_MODEL_SHA,
    }
    default = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).versions_with(OPTIONS, company_id=A)
    assert default == {**colab.run_versions(None), "aiSettingId": None, "modelSettingsSha256": DEFAULT_MODEL_SHA}


def test_versions_with_a_saved_text_the_rules_no_longer_take_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = binding_of(SAVED)
    assert "promptsSha256" in binding.versions_with(OPTIONS, company_id=A)  # 분모: 좁히기 전엔 지어진다
    narrow(monkeypatch)
    with pytest.raises(RunVersionsRejected) as refused:
        binding.versions_with(OPTIONS, company_id=A)
    assert "(v3)" in refused.value.message
    assert "지어낸" not in refused.value.message  # 글·메모 0
    assert "promptsSha256" not in binding_of(None).versions_with(OPTIONS, company_id=A)  # 코드 글 판은 좁혀도 그대로


# ── 3-4-2 inputs_with ──


def test_inputs_with_a_saved_text_carries_its_pack() -> None:
    binding = binding_of(SAVED)
    versions = binding.versions_with(OPTIONS, company_id=A)
    got = binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions)
    assert got.prompts == colab.pack_from(accepted_saved())
    assert got.prompts == PromptPack(**{field: edited_texts()[key] for key, field in colab.PROMPT_FIELDS.items()})
    assert got.criteria == edited()  # 기준표는 그대로 실린다(실행 글에는 저장 글이 앞선다)
    old = {k: v for k, v in versions.items() if k != "modelSettingsSha256"}  # AS2b 앞 꼴로 만든 실행
    assert binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=old).prompts == got.prompts


def test_inputs_with_a_code_text_carries_none() -> None:
    binding = binding_of(None)
    versions = binding.versions_with(OPTIONS, company_id=A)
    assert binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions).prompts is None


@pytest.mark.parametrize("model_key", [True, False], ids=["with-model-key", "before-as2b"])
@pytest.mark.parametrize("case", ["key-only", "field-only"])
def test_inputs_with_a_key_and_field_that_disagree_fail(case: str, model_key: bool) -> None:
    """저장 글 있음 ⇔ 열쇠 있음 — 모델 열쇠가 없는 실행(checks_model 일찍 돌아가기)에서도 본다(P13)."""
    made = binding_of(SAVED).versions_with(OPTIONS, company_id=A)
    if case == "key-only":  # 코드 글 판인데 실행에 열쇠가 있다
        versions = {**binding_of(None).versions_with(OPTIONS, company_id=A), "promptsSha256": made["promptsSha256"]}
        worker = binding_of(None)
    else:  # 저장 글 판인데 실행에 열쇠가 없다
        versions = {k: v for k, v in made.items() if k != "promptsSha256"}
        worker = binding_of(SAVED)
    if not model_key:
        versions = {k: v for k, v in versions.items() if k != "modelSettingsSha256"}
    with pytest.raises(AiSettingMismatch, match="유무"):
        worker.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions)


def test_inputs_with_a_prompts_key_on_the_default_fails() -> None:
    binding = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore())
    versions = binding.versions_with(OPTIONS, company_id=A)
    assert binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions).prompts is None  # 분모
    keyed = {**versions, "promptsSha256": prompts_sha256(accepted_saved())}
    with pytest.raises(AiSettingMismatch, match="기본 판"):
        binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=keyed)


def test_inputs_with_a_saved_text_the_rules_no_longer_take_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = binding_of(SAVED)
    versions = binding.versions_with(OPTIONS, company_id=A)
    narrow(monkeypatch)
    with pytest.raises(AiSettingMismatch, match="다시 받을 수 없다: ai_prompt_"):
        binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions)


# ── 3-4-5 두 sha 대조(B2) ──


def one_char_off(sha: object) -> str:
    assert isinstance(sha, str)
    return ("1" if sha[0] == "0" else "0") + sha[1:]


@pytest.mark.parametrize(
    ("key", "match"),
    [("promptsSha256", "프롬프트 글"), ("evalPromptSha256", "판정 프롬프트")],
    ids=["prompts-sha", "eval-sha"],
)
def test_inputs_with_one_sha_changed_fails(key: str, match: str) -> None:
    binding = binding_of(SAVED)
    versions = binding.versions_with(OPTIONS, company_id=A)
    binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions=versions)  # 분모: 그대로면 지난다
    with pytest.raises(AiSettingMismatch, match=match):
        binding.inputs_with(DOCUMENT, OPTIONS, company_id=A, versions={**versions, key: one_char_off(versions[key])})


# ── 3-4-6 흐름 ──


def saved_inputs(*, dry_run: bool = False) -> colab.GreenwashInputs:
    built = binding_of(SAVED).inputs_with(
        DOCUMENT, OPTIONS, company_id=A, versions=binding_of(SAVED).versions_with(OPTIONS, company_id=A)
    )
    return colab.GreenwashInputs(
        document=s.SAMPLE_BYTES,
        media_type="application/pdf",
        file_name=s.SAMPLE_NAME,
        ceo="1",
        company="2",
        climate="3~4",
        dry_run=dry_run,
        prompts=built.prompts,
    )


def test_the_saved_texts_reach_the_provider_as_they_are() -> None:
    pack = colab.pack_from(accepted_saved())
    mock = flow_cases.scripted_provider(20, pack)
    run = s.run(saved_inputs(), s.adapters(llm=flow_cases.bridge(mock, MemorySink())))
    systems = [system for system, _ in flow_cases.pairs(mock.calls)]
    kinds = flow_cases.kinds(mock.calls, pack)
    assert "unknown" not in kinds and set(kinds) == set(KEYS)  # 넷 다 저장 글로 갔다(종류마다 ≥1)
    assert not set(systems) & set(code_texts().values())  # 코드 글 0
    assert any("{{system}}" in system for system in systems)  # 글 속 변수 꼴은 한 번만 치환 — 그대로 간다
    assert run.steps["judge"].data["failed_pages"] == []


def test_a_dry_run_with_saved_texts_is_refused() -> None:
    with pytest.raises(FlowStepFailed) as failed:
        s.run(saved_inputs(dry_run=True), s.adapters(tokens=s.char_counter()))
    assert failed.value.step == "judge"
    assert isinstance(failed.value.__cause__, ValueError) and "dry-run" in str(failed.value.__cause__)


def test_a_port_without_with_pack_fails_outside_the_page_loop() -> None:
    chat = ScriptedChat()
    with pytest.raises(FlowStepFailed) as failed:
        s.run(saved_inputs(), s.adapters(llm=chat))
    assert isinstance(failed.value.__cause__, TypeError) and "LlmChatBridge" in str(failed.value.__cause__)
    assert chat.sent == []  # 쪽 루프에 들기 전
    same = ScriptedChat()  # 분모: 코드 글과 같은 묶음은 그대로 넘긴다(골든 그대로)
    code = colab.GreenwashInputs(
        document=s.SAMPLE_BYTES,
        media_type="application/pdf",
        file_name=s.SAMPLE_NAME,
        ceo="1",
        company="2",
        climate="3~4",
        prompts=default_prompts(PROMPT_VERSION),
    )
    s.run(code, s.adapters(llm=same))
    assert s.message_hashes(same.sent) == s.golden("sample-mock.json")["messages"]


def test_the_binding_does_not_import_the_prompt_model_view() -> None:
    tree = ast.parse(Path(binding_e0.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported += [node.module or "", *(f"{node.module}.{alias.name}" for alias in node.names)]
        elif isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
    assert "esgapi.greenwash.flows.colab_e0" in imported  # 분모: 이 걷기가 import 를 본다
    assert not [name for name in imported if name.endswith("prompt_model_e0")]
