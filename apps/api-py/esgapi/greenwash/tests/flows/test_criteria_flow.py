"""흐름 greenwash.colab@E0 가 기준표(greenwash.criteria@1)를 받는다: 기본 판(기준표 없음·기본 기준표)은 요청 바이트가
골든과 같고(모의 대화·대조 B), 고친 판은 고친 줄만 바뀐 EVAL 을 core.llm 다리까지 보낸다. 다리의 pack, dry-run 의 한계,
이어 돌기, 받기 거절. 실제 공급사·키 0 — 모의 대화(ScriptedChat)·모의 공급사(MockProvider)만 쓴다.

고친 판 기준표는 contract-examples/criteria/criteria-edited.json(지어낸 글)이다.
"""

import difflib
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from esgapi.core.flows.types import FlowStepFailed
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, ProviderRequest, ProviderResponse, Tags, TextPart
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.engines.e0.ports import HumanMessage, ScriptedChat, SystemMessage, prompt_kind
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, PromptPack, default_prompts
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import criteria_e0
from esgapi.greenwash.flows.colab_e0 import PROMPT_IDS, LlmChatBridge
from esgapi.greenwash.flows.criteria_e0 import (
    CriteriaRejected,
    accept_criteria,
    build_eval_prompt,
    default_criteria,
    eval_pack,
)
from esgapi.greenwash.tests.flows import support as s

TAGS = Tags(tenant="tenant-synthetic", module="greenwash")
EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "contract-examples" / "criteria"


def edited() -> GreenwashCriteria:
    raw = json.loads((EXAMPLES / "criteria-edited.json").read_text(encoding="utf-8"))
    return accept_criteria(raw)


def inputs(criteria: GreenwashCriteria | None, *, dry_run: bool = False) -> colab.GreenwashInputs:
    return colab.GreenwashInputs(
        document=s.SAMPLE_BYTES,
        media_type="application/pdf",
        file_name=s.SAMPLE_NAME,
        ceo="1",
        company="2",
        climate="3~4",
        dry_run=dry_run,
        criteria=criteria,
    )


def scripted_provider(calls: int, pack: PromptPack | None = None) -> MockProvider:
    """받은 요청의 system·user 글로 ScriptedChat(pack) 의 대본 답을 돌려주는 모의 공급사(큐에 calls 개).
    test_colab_e0.scripted_provider 의 꼴에 pack 을 더한 것 — 기본 pack 이면 고친 EVAL 을 「unknown」 으로 본다."""
    script = ScriptedChat(pack=pack)

    def reply(request: ProviderRequest) -> ProviderResponse:
        system = "".join(seg.text for seg in request.system)
        user = "".join(part.text for part in request.user if isinstance(part, TextPart))
        return Completed(text=script.respond(system, user), usage=SYNTHETIC_USAGE)

    mock = MockProvider()
    for _ in range(calls):
        mock.enqueue(reply)
    return mock


def bridge(mock: MockProvider, sink: MemorySink) -> LlmChatBridge:
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=True)),
        providers={"mock": mock},
        prompts=PackagePromptStore(),
        log=sink,
    )
    return LlmChatBridge(client, route="mock", tags=TAGS)


def pairs(requests: list[ProviderRequest]) -> list[tuple[str, str]]:
    return [
        ("".join(seg.text for seg in r.system), "".join(p.text for p in r.user if isinstance(p, TextPart)))
        for r in requests
    ]


def provider_hashes(requests: list[ProviderRequest]) -> list[str]:
    return [s.sha256_text(json.dumps(list(pair), ensure_ascii=False)) for pair in pairs(requests)]


# ── 1. 기본 판: 모의 대화에 간 메시지 = 골든 ──


@pytest.mark.parametrize("given", ["none", "default"])
def test_the_default_criteria_send_the_golden_messages(given: str) -> None:
    gw1 = s.golden("sample-mock.json")
    chat = ScriptedChat()
    criteria = None if given == "none" else default_criteria()
    result = s.result_of(s.run(inputs(criteria), s.adapters(llm=chat)))
    assert s.message_hashes(chat.sent) == gw1["messages"] and len(gw1["messages"]) == 12
    assert s.chat_calls(chat.sent) == gw1["calls"]["chat"]
    assert s.as_gw1(result) == s.gw1_view(gw1)
    plain = s.result_of(s.run(s.inputs(), s.adapters()))
    assert json.dumps(result, ensure_ascii=False).encode("utf-8") == json.dumps(plain, ensure_ascii=False).encode(
        "utf-8"
    )


# ── 2. 기본 판: 모의 공급사(대조 B) ──


@pytest.mark.parametrize("given", ["none", "default"])
def test_the_default_criteria_reach_the_provider_unchanged(given: str) -> None:
    gw1 = s.golden("sample-mock.json")
    mock, sink = scripted_provider(20), MemorySink()
    criteria = None if given == "none" else default_criteria()
    result = s.result_of(s.run(inputs(criteria), s.adapters(llm=bridge(mock, sink))))
    assert s.as_gw1(result) == s.gw1_view(gw1)
    assert provider_hashes(mock.calls) == gw1["messages"]
    assert len(sink.records) == 12
    assert {r.prompt_id for r in sink.records} == set(PROMPT_IDS.values())
    assert [(r.temperature, type(r.temperature)) for r in mock.calls] == [(0.0, float)] * 12
    assert all(r.max_output_tokens == 1300 for r in mock.calls)


# ── 3. 고친 판: 고친 줄만 바뀐 EVAL 이 공급사까지 ──


def kinds(requests: list[ProviderRequest], pack: PromptPack) -> list[str]:
    return [prompt_kind(system, pack) for system, _ in pairs(requests)]


def test_the_edited_criteria_reach_the_provider_as_the_edited_eval() -> None:
    gw1 = s.golden("sample-mock.json")
    criteria = edited()
    pack = eval_pack(criteria, PROMPT_VERSION)
    mock, sink = scripted_provider(20, pack), MemorySink()
    flow_run = s.run(inputs(criteria), s.adapters(llm=bridge(mock, sink)))
    judged = flow_run.steps["judge"].data
    # ① 쪽 안의 예외는 checker 가 삼킨다 — 「예외 없이 끝남」이 아니라 실패 쪽 0 을 잰다
    assert (judged["failed"], judged["failed_pages"]) == (0, [])
    # ② 요청 12, 그 가운데 eval 4, 프롬프트 id 넷
    assert len(mock.calls) == 12
    assert kinds(mock.calls, pack).count("eval") == gw1["calls"]["chat"]["eval"] == 4
    assert {r.prompt_id for r in sink.records} == set(PROMPT_IDS.values())
    # ③ eval 요청의 system 글 = 고친 판 조립, 원본과의 차이는 고친 줄뿐
    edited_eval = build_eval_prompt(criteria, PROMPT_VERSION)
    evals = [system for system, _ in pairs(mock.calls) if system == pack.eval_system_prompt]
    assert evals == [edited_eval] * 4
    engine = default_prompts(PROMPT_VERSION).eval_system_prompt.split("\n")
    diff = [line for line in difflib.ndiff(engine, edited_eval.split("\n")) if line[:1] in "-+"]
    assert [line[:1] for line in diff] == ["-", "+", "-", "+", "-"]
    assert diff[1].startswith("+ - 배제용어: ") and diff[1].endswith(", 녹색전환")
    assert diff[3].startswith("+ - 탄소중립·넷제로 같은 목표")
    assert diff[4].startswith("- -법적/거버넌스 체계")
    # ④ 탐지·다시 묻기·Low 전용 요청은 기본 판 실행(같은 대본)의 같은 차례 요청과 바이트가 같다
    base = scripted_provider(20)
    s.run(inputs(None), s.adapters(llm=bridge(base, MemorySink())))
    assert kinds(base.calls, default_prompts(PROMPT_VERSION)) == kinds(mock.calls, pack)
    for (got, want), kind in zip(
        zip(pairs(mock.calls), pairs(base.calls), strict=True), kinds(mock.calls, pack), strict=True
    ):
        if kind == "eval":
            assert got[1].encode("utf-8") == want[1].encode("utf-8")  # user 글은 같다
        else:
            assert json.dumps(got, ensure_ascii=False).encode("utf-8") == json.dumps(want, ensure_ascii=False).encode(
                "utf-8"
            )


# ── 4. 다리 단독 ──


def test_the_default_bridge_refuses_the_edited_eval_and_the_packed_one_takes_it() -> None:
    edited_eval = build_eval_prompt(edited(), PROMPT_VERSION)
    messages = [SystemMessage(content=edited_eval), HumanMessage(content="u")]
    plain = bridge(scripted_provider(1, eval_pack(edited(), PROMPT_VERSION)), MemorySink())
    with pytest.raises(ValueError, match="프롬프트 넷"):
        plain.invoke(messages)
    mock, sink = scripted_provider(1, eval_pack(edited(), PROMPT_VERSION)), MemorySink()
    packed = bridge(mock, sink).with_pack(eval_pack(edited(), PROMPT_VERSION))
    packed.invoke(messages)
    assert [r.prompt_id for r in sink.records] == ["greenwash/eval@1"]
    assert pairs(mock.calls) == [(edited_eval, "u")]


def test_with_pack_keeps_the_client_route_and_tags() -> None:
    first = bridge(MockProvider(), MemorySink())
    pack = eval_pack(edited(), PROMPT_VERSION)
    second = first.with_pack(pack)
    assert (second.client, second.route, second.tags, second.pack) == (first.client, first.route, first.tags, pack)
    assert first.pack == default_prompts(PROMPT_VERSION)


# ── 5. dry-run: 판정 몫만 고친 기준표로 보정(밴드 G2c2 Q8 — 이 자리가 못 박던 「기준표를 보지 못한다」 한계를 걷음) ──


def test_dry_run_with_criteria_calls_nothing_and_counts_the_edited_eval() -> None:
    forbidden = s.Forbidden()
    used = s.adapters(llm=forbidden, embedding=forbidden, tokens=s.char_counter())
    with_criteria = s.result_of(s.run(inputs(edited(), dry_run=True), used))
    assert forbidden.calls == 0
    without = s.result_of(s.run(inputs(None, dry_run=True), s.adapters(tokens=s.char_counter())))
    diff = len(eval_pack(edited(), PROMPT_VERSION).eval_system_prompt) - len(
        default_prompts(PROMPT_VERSION).eval_system_prompt
    )
    assert diff != 0  # 분모: 고친 판의 EVAL 은 기본과 길이가 다르다
    assert without["dryRun"]["upper"]["chatByKind"]["eval"]["requests"] > 0  # 분모: 판정 요청이 있다
    expected = json.loads(json.dumps(without))
    for end in ("lower", "upper"):
        requests = expected["dryRun"][end]["chatByKind"]["eval"]["requests"]
        for tally in (expected["dryRun"][end]["chatByKind"]["eval"], expected["dryRun"][end]["chat"]):
            tally["inputChars"] += requests * diff
            tally["inputTokens"]["value"] += requests * diff  # 글자 = 토큰인 가짜 세기
    assert with_criteria == expected


# ── 6. 이어 돌기: 고친 판으로 둘째 쪽 뒤 끊기고 이어 돈 것 = 한 번에 돈 것 ──


def test_the_edited_criteria_resume_after_the_second_page() -> None:
    criteria = edited()
    pack = eval_pack(criteria, PROMPT_VERSION)
    whole_mock = scripted_provider(20, pack)
    whole = s.result_of(s.run(inputs(criteria), s.adapters(llm=bridge(whole_mock, MemorySink()))))

    mock = scripted_provider(20, pack)
    used = s.adapters(llm=bridge(mock, MemorySink()))
    recorder = s.Recorder(stop_after=2)
    with pytest.raises(s.Interrupted):
        s.run(inputs(criteria), used, events=recorder)
    assert recorder.saved is not None and recorder.saved["done_pages"] == [1, 2]
    carried = {name: recorder.finished[name] for name in ("extract", "index")}
    resumed = s.run(inputs(criteria), used, start_at="judge", carried=carried, resume=recorder.saved)
    assert s.result_of(resumed) == whole
    assert provider_hashes(mock.calls) == provider_hashes(whole_mock.calls) and len(mock.calls) == 12
    assert kinds(mock.calls, pack).count("eval") == 4
    assert resumed.steps["judge"].data["failed_pages"] == []


# ── 6a. 다리가 아닌 대화 포트 + 기본 판과 다른 기준표 = 쪽 루프 밖에서 실패(가지 리뷰 3) ──


def test_a_port_without_with_pack_fails_outside_the_page_loop() -> None:
    chat = ScriptedChat()
    with pytest.raises(FlowStepFailed) as failed:
        s.run(inputs(edited()), s.adapters(llm=chat))
    assert failed.value.step == "judge"
    assert isinstance(failed.value.__cause__, TypeError) and "LlmChatBridge" in str(failed.value.__cause__)
    assert chat.sent == []  # 쪽 루프에 들기 전 — 쪽마다 삼켜진 실패로 「완료」 되지 않는다
    same = ScriptedChat()  # 기본 판과 같은 기준표는 그대로 넘긴다
    assert s.message_hashes(same.sent) == [] and s.run(inputs(default_criteria()), s.adapters(llm=same))
    assert s.message_hashes(same.sent) == s.golden("sample-mock.json")["messages"]


# ── 6b. 판 묶음 값은 judge 와 같은 판 글자 ──


def test_the_flow_run_versions_use_the_judge_prompt_version() -> None:
    raw = cast("dict[str, Any]", json.loads((EXAMPLES / "criteria-edited.json").read_text(encoding="utf-8")))
    with_terms = colab.GreenwashInputs(
        document=s.SAMPLE_BYTES,
        media_type="application/pdf",
        file_name=s.SAMPLE_NAME,
        ceo="1",
        company="2",
        climate="3~4",
        extra_terms=("지어낸낱말",),
        criteria=edited(),
    )
    version = colab.judged_prompt_version(colab.scan_config(with_terms))
    assert version == PROMPT_VERSION
    assert colab.run_versions(raw) == criteria_e0.run_versions(raw, version)
    assert (
        colab.run_versions(raw)["evalPromptSha256"]
        == hashlib.sha256(build_eval_prompt(edited(), version).encode("utf-8")).hexdigest()
    )
    assert colab.run_versions(None) == {
        "aiSetting": "colab-2026-01-15-v1",
        "evalPromptSha256": s.sha256_text(default_prompts(PROMPT_VERSION).eval_system_prompt),
    }


# ── 7. 받기 거절은 입력을 지을 때 ──


def test_a_refused_criteria_fails_when_the_inputs_are_made() -> None:
    bad = cast("dict[str, Any]", default_criteria())
    bad["rows"] = bad["rows"][:14]
    with pytest.raises(CriteriaRejected) as refused:
        inputs(cast("GreenwashCriteria", bad))
    assert refused.value.code == "CRITERIA_ROWS_FIXED"
    assert isinstance(refused.value, ValueError)
    stripped = cast("dict[str, Any]", default_criteria())
    stripped["rows"][6]["text"] = "  지어낸 기준 글  "
    made = inputs(cast("GreenwashCriteria", stripped))
    assert made.criteria is not None and made.criteria["rows"][6]["text"] == "지어낸 기준 글"
    assert inputs(None).criteria is None
