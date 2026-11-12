# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""재판단 흐름 greenwash.rejudge@E0 을 진짜 DB 의 실행기로 잰다(밴드 GRJ1 ② — 결정 MARC-ENT-617, 발주서 §2-3). 업무 층:
원 실행(greenwash.colab@E0)을 test_binding_e0_runs 의 world 로 끝까지 돌린 뒤, 검토 화면의 길(PUT evidence → POST
…/rejudge)로 재판단을 만들고 실행기를 다시 부른다(태스크 함수를 직접).

    호출 1 · 요청 바이트가 원 실행의 그 문장 판정 요청과 [근거 컨텍스트] 칸만 다르다(system·모델·온도·출력 상한 같음)
    결과 greenwash.rejudge@1(꼴 검사) · 검토 GET 의 기준 판단이 그 결과
    Low 갈래(원 판단 Low) → eval_low_only · Low 고정 칸(riskTags ["선언적 문장"], 칩·빠진 항목 [])
    NonRisk → outcome nonrisk·level null(문장은 남음)
    공급사 오류 → 실행 failed · 기준 판단은 첫 판단 그대로
    판은 원 실행 versions 로 다시 지은 것(inputs_with) · 판 칸이 있으면 colab 의 judge_chat 길
    근거 글 꼴(build_evidence 와 같음)

★ 실제 공급사·키·네트워크 0(모의 공급사). 문서·글·숫자는 지어낸 것이다(synthetic).
"""

import json
from dataclasses import replace
from functools import partial
from typing import Any

import pytest
from django.test import Client

from esgapi.core.flows.binding import BindingRegistry
from esgapi.core.flows.types import StepContext
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import Completed, ProviderRequest, ProviderResponse, TextPart
from esgapi.core.resources import llm as llm_adapters
from esgapi.greenwash.contracts.rejudge_shapes import REJUDGE_SHAPES
from esgapi.greenwash.contracts.rejudge_shapes import SHAPE as REJUDGE_SHAPE
from esgapi.greenwash.engines.e0.heuristics import cap_evidence_context
from esgapi.greenwash.engines.e0.ports import ChatReply
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.flows import rejudge_e0
from esgapi.greenwash.flows.binding_e0 import GreenwashBinding, RunSetting
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.flows.settings_store import DefaultOnlyStore
from esgapi.greenwash.tests.flows.support import REAL_MODELS
from esgapi.greenwash.tests.flows.test_binding_e0_runs import (
    MINIMAL,
    World,
    execute,
    new_run,
    result_body,
    run_of,
    sample_pages,
    world,
)
from esgapi.runs import context, tasks
from esgapi.runs.service.selectors import runs as run_selectors

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (world,)

PIECE = {"text": "지어낸 근거 — 산정 범위는 국내 사업장 셋이다", "page": 2}
HIGH = 0  # 표본 결과: High · 칩 1
LOW = 1  # 표본 결과: Low(선언적 문장)


@pytest.fixture(autouse=True)
def rejudge_bound(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """실행기의 끼움에 재판단 흐름도 모의 경로로 단다(만들기는 전역 BINDINGS — apps.py 의 진짜 끼움)."""
    bindings: BindingRegistry = tasks.BINDINGS
    setting = GreenwashBinding(
        models=REAL_MODELS, store=DefaultOnlyStore(), chat_route="mock", embedding_route="mock-gw1"
    )
    bindings.register_documentless(
        rejudge_e0.FLOW_ID,
        rejudge_e0.RejudgeBinding(setting=setting),
        max_options_bytes=rejudge_e0.OPTIONS_MAX_OCTETS,
    )


def done_original(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> tuple[int, dict[str, Any]]:
    sample_pages(monkeypatch)
    run_id = new_run(client, world, MINIMAL)
    execute(world, run_id)
    assert run_of(world, run_id).status == "done"
    return run_id, result_body(world, run_id)


def use_provider(world: World, monkeypatch: pytest.MonkeyPatch, provider: MockProvider) -> None:
    def make(name: str, **kwargs: Any) -> Any:
        return provider if name == "mock" else llm_adapters.make(name, **kwargs)

    monkeypatch.setattr(context, "build_client", partial(context.build_client.func, make=make))  # pyright: ignore[reportFunctionMemberAccess]
    world.mock = provider


def scripted(calls: int = 1) -> MockProvider:
    mock, _ = s.scripted_provider(calls)
    return mock


def answering(text: str) -> MockProvider:
    mock = MockProvider()

    def reply(request: ProviderRequest) -> ProviderResponse:
        return Completed(text=text, usage=s.SYNTHETIC_USAGE)

    mock.enqueue(reply)
    return mock


def make_rejudge(client: Client, run_id: int, index: int, removed: list[int], added: list[dict[str, Any]]) -> int:
    body = {"marks": [], "evidence": [{"itemIndex": index, "removed": removed, "added": added}]}
    saved = client.put(f"/api/greenwash/runs/{run_id}/review", data=body, content_type="application/json")
    assert saved.status_code == 200, saved.content.decode()
    made = client.post(f"/api/greenwash/runs/{run_id}/items/{index}/rejudge")
    assert made.status_code == 202, made.content.decode()
    rejudge_id: int = made.json()["rejudgeRunId"]
    return rejudge_id


def rejudged(world: World, run_id: int) -> dict[str, Any]:
    (only,) = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    assert only.schema_version == REJUDGE_SHAPE
    REJUDGE_SHAPES[REJUDGE_SHAPE].validate_python(only.body, strict=True)
    assert isinstance(only.body, dict)
    return only.body  # pyright: ignore[reportReturnType]


def user_text(request: ProviderRequest) -> str:
    return "".join(p.text for p in request.user if isinstance(p, TextPart))


def asked_about(requests: list[ProviderRequest], sentence: str) -> ProviderRequest:
    (found,) = [r for r in requests if user_text(r).startswith(f"[문장]\n{sentence}\n\n")]
    return found


def review_of(client: Client, run_id: int) -> dict[str, Any]:
    got = client.get(f"/api/greenwash/runs/{run_id}/review")
    assert got.status_code == 200, got.content.decode()
    body: dict[str, Any] = got.json()
    return body


def test_one_call_whose_request_differs_only_in_the_evidence(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, original = done_original(client, world, monkeypatch)
    first_calls = list(world.mock.calls)
    item = original["items"][HIGH]
    assert (item["level"], len(item["confirmedInEvidence"])) == ("High", 1)
    rejudge_id = make_rejudge(client, run_id, HIGH, [], [PIECE])
    use_provider(world, monkeypatch, scripted())
    execute(world, rejudge_id)
    assert run_of(world, rejudge_id).status == "done"
    (call,) = world.mock.calls
    before = asked_about(first_calls, item["sentence"])
    chip = item["confirmedInEvidence"][0]
    context_text = f"{chip}\n\n[p.{PIECE['page']}]\n{PIECE['text']}"
    assert user_text(call) == f"[문장]\n{item['sentence']}\n\n[근거 컨텍스트]\n{context_text}\n"
    assert replace(call, user=before.user) == before  # system·모델·온도·출력 상한·나머지 칸 바이트 같음
    body = rejudged(world, rejudge_id)
    assert (body["fromRunId"], body["itemIndex"], body["sentence"]) == (run_id, HIGH, item["sentence"])
    assert (body["kept"], body["added"], body["item"]["evidencePages"]) == ([chip], [PIECE], [PIECE["page"]])
    assert {r.run_id for r in world.sink.records if r.run_id == str(rejudge_id)} == {str(rejudge_id)}
    (line,) = review_of(client, run_id)["rejudges"]
    assert (line["status"], line["count"], line["current"]["runId"]) == ("done", 1, rejudge_id)
    assert line["current"]["level"] == body["item"]["level"]


def test_a_low_sentence_takes_the_low_branch_with_the_fixed_fields(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, original = done_original(client, world, monkeypatch)
    first_calls = list(world.mock.calls)
    item = original["items"][LOW]
    assert item["level"] == "Low"
    rejudge_id = make_rejudge(client, run_id, LOW, [], [{"text": PIECE["text"], "page": None}])
    use_provider(world, monkeypatch, scripted())
    execute(world, rejudge_id)
    (call,) = world.mock.calls
    before = asked_about(first_calls, item["sentence"])
    assert call.system == before.system  # Low 전용 프롬프트(LOW_ONLY) — 원 실행의 그 문장과 같은 종류
    assert user_text(call) == f"[문장]\n{item['sentence']}\n\n[근거 컨텍스트]\n{PIECE['text']}\n"
    got = rejudged(world, rejudge_id)["item"]
    assert (got["level"], got["riskTags"], got["confirmedInEvidence"], got["missingFields"]) == (
        "Low",
        ["선언적 문장"],
        [],
        [],
    )
    assert got["evidencePages"] == []


def test_a_nonrisk_answer_keeps_the_sentence_with_a_null_level(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, _ = done_original(client, world, monkeypatch)
    rejudge_id = make_rejudge(client, run_id, HIGH, [0], [PIECE])
    # 엔진 가드레일: NonRisk 는 확인 사실 둘 이상·빠진 항목 0 일 때만 남는다(checker.eval_high_mid_or_nonrisk)
    facts = ["지어낸 사실 가", "지어낸 사실 나"]
    answer = {"decision": "NonRisk", "risk_tags": [], "confirmed_in_evidence": facts, "missing_fields": []}
    use_provider(world, monkeypatch, answering(json.dumps(answer, ensure_ascii=False)))
    execute(world, rejudge_id)
    body = rejudged(world, rejudge_id)
    assert (body["outcome"], body["item"]["level"], body["kept"]) == ("nonrisk", None, [])
    (line,) = review_of(client, run_id)["rejudges"]
    assert (line["current"]["outcome"], line["current"]["level"]) == ("nonrisk", None)


def test_a_provider_failure_fails_the_run_and_keeps_the_first_judgment(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, original = done_original(client, world, monkeypatch)
    rejudge_id = make_rejudge(client, run_id, HIGH, [0], [PIECE])
    use_provider(world, monkeypatch, MockProvider())  # 대본 없음 = 공급사 오류
    execute(world, rejudge_id)
    run = run_of(world, rejudge_id)
    assert (run.status, run.failed_step) == ("failed", "judge")
    assert run_selectors.run_results(company_id=world.company_a, run_id=rejudge_id) == ()
    state = review_of(client, run_id)
    (line,) = state["rejudges"]
    assert (line["status"], line["count"], line["current"]) == ("failed", 0, None)
    (shown,) = state["evidence"]
    assert (shown["removed"], shown["added"]) == ([0], [PIECE])  # 고침은 남는다(r4 ④)
    assert original["items"][HIGH]["level"] == "High"


OPTIONS: dict[str, object] = {
    "fromRunId": 1,
    "itemIndex": 0,
    "sentence": "지어낸 문장",
    "lowOnly": False,
    "kept": [],
    "added": [],
    "maxCharsPerChunk": 450,
    "maxCharsEvidenceTotal": 1600,
}


class Chat:
    """기록하는 대화 포트(LlmChatBridge 가 아님)."""

    def __init__(self) -> None:
        self.systems: list[str] = []

    def invoke(self, messages: Any) -> ChatReply:
        self.systems.append(str(messages[0].content))
        return ChatReply(content='{"decision": "Mid"}')


class Setting:
    """run_setting 만 흉내 내는 판 끼움 — 받은 versions 를 적는다."""

    def __init__(self, made: RunSetting) -> None:
        self.made = made
        self.asked: list[dict[str, object]] = []

    def run_setting(self, *, company_id: int, versions: dict[str, object]) -> RunSetting:
        self.asked.append(dict(versions))
        return self.made


def test_inputs_carry_the_setting_rebuilt_from_the_original_runs_versions() -> None:
    """§5-2 ②: 판은 원 실행 versions(만들 때 베낀 것, flow 뺌)로 다시 지은 것 — 지금 적용 판이 아니다."""
    pack = replace(default_prompts(PROMPT_VERSION), eval_system_prompt="지어낸 판정 글")
    setting = Setting(RunSetting(criteria=None, prompts=pack, model=None, terms=None))
    binding = rejudge_e0.RejudgeBinding(setting=setting)  # pyright: ignore[reportArgumentType]
    versions = {"aiSettingId": 7, "evalPromptSha256": "0" * 64, "flow": rejudge_e0.FLOW_ID}
    got = binding.inputs_with(OPTIONS, company_id=3, versions=versions)
    assert setting.asked == [{"aiSettingId": 7, "evalPromptSha256": "0" * 64}]
    assert (got.prompts, got.criteria, got.model) == (pack, None, None)
    # 판 칸이 있으면 colab 의 판정과 같은 judge_chat 길 — 다리가 아닌 포트에 고친 글은 TypeError(쪽 루프 밖)
    with pytest.raises(TypeError, match="LlmChatBridge"):
        rejudge_e0.judge(got, rejudge_e0.RejudgeAdapters(llm=Chat()), {}, StepContext(resume=None))


def test_without_a_setting_the_engine_default_eval_prompt_is_sent() -> None:
    chat = Chat()
    out = rejudge_e0.judge(
        rejudge_e0.RejudgeInputs(options=OPTIONS), rejudge_e0.RejudgeAdapters(llm=chat), {}, StepContext(resume=None)
    )
    # 첫 호출이 판정 글(엔진 기본). 일반론 수정 방향이면 엔진이 보정 호출을 하나 더 한다(REPAIR — 코랩 그대로)
    assert chat.systems[0] == default_prompts(PROMPT_VERSION).eval_system_prompt
    (result,) = out.data["results"]  # pyright: ignore[reportGeneralTypeIssues]
    assert (result["outcome"], result["item"]["level"]) == ("judged", "Mid")


def test_the_prompt_version_comes_from_the_frozen_option_and_old_options_still_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GRS1(MARC-ISSUE-632): 판 글자는 만들 때 원 실행 config 로 셈해 굳힌 promptVersion 칸 — 지금 SCAN_CONFIG 가
    아니다. 칸 없는 옛 옵션은 꼴을 지나고(NotRequired) 지금처럼 SCAN_CONFIG 로 셈한다."""
    seen: list[str] = []
    real = rejudge_e0.colab.judge_chat

    def recording(llm: Any, **kwargs: Any) -> Any:
        seen.append(kwargs["version"])
        return real(llm, **kwargs)

    monkeypatch.setattr(rejudge_e0.colab, "judge_chat", recording)
    frozen = {**OPTIONS, "promptVersion": "2025-07-01-v0"}
    assert frozen["promptVersion"] != rejudge_e0.colab.judged_prompt_version(dict(rejudge_e0.colab.SCAN_CONFIG))
    for options in (frozen, OPTIONS):
        rejudge_e0.accept_options(options)  # 둘 다 꼴을 지난다
        rejudge_e0.judge(
            rejudge_e0.RejudgeInputs(options=options),
            rejudge_e0.RejudgeAdapters(llm=Chat()),
            {},
            StepContext(resume=None),
        )
    assert seen == ["2025-07-01-v0", PROMPT_VERSION]
    assert rejudge_e0.prompt_version_of(OPTIONS) == PROMPT_VERSION
    with pytest.raises(rejudge_e0.RunOptionsRejected):  # 빈 글자는 꼴이 막는다
        rejudge_e0.accept_options({**OPTIONS, "promptVersion": ""})


def test_the_evidence_context_has_the_build_evidence_shape() -> None:
    """칩은 머리 줄 없이 · 쪽 있는 조각은 [p.N] · 조각 상한 넘으면 " ..." · 전체 상한은 cap_evidence_context."""
    added = [{"text": "  가" * 3 + "  ", "page": 4}, {"text": "나" * 12, "page": None}]
    got = rejudge_e0.evidence_context(["칩 하나"], added, per_chunk=10, total=1600)
    assert got == "칩 하나\n\n[p.4]\n가 가 가\n\n" + "나" * 10 + " ..."
    capped = rejudge_e0.evidence_context(["다" * 30], [], per_chunk=100, total=20)
    assert capped == cap_evidence_context("다" * 30, max_total_chars=20)
    assert rejudge_e0.evidence_pages(
        [{"text": "a", "page": 5}, {"text": "b", "page": 2}, {"text": "c", "page": 5}]
    ) == [
        2,
        5,
    ]
