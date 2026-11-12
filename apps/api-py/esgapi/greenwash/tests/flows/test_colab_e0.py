"""흐름 greenwash.colab@E0: 선언, 대조 A(GW1 골든과 같음), 점검 쪽 없음, 단계 산출물의 왕복, judge 루프 = GW1 스캔,
쪽 단위 진행과 이어 돌기(대조 D), dry-run(대조 C), locate, 셈, 상수. 실제 공급사 0 — 가짜 어댑터만 쓴다.

어댑터: 프롬프트 렌더 확인(§2-5), LlmChatBridge 로 지난 대조 B, L1 임베딩 포트로 지난 대조 A, 메시지 해시 도우미.
모의 공급사·모의 임베딩만 쓴다(core 의 synthetic 모델 파일). 실제 공급사·키 0.
"""

import json
from typing import Any, cast

import pytest
from langchain_core.documents import Document

from esgapi.config.env import LlmSettings
from esgapi.core.flows.types import FlowStepFailed, StepContext, StepOutput
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.embedding import ClientEmbeddingPort
from esgapi.core.llm.prompts import PackagePromptStore, parse_prompt_id, render_prompt
from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.setup import build_embedding_client
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, ProviderRequest, ProviderResponse, Tags, TextPart
from esgapi.greenwash.contracts import shapes
from esgapi.greenwash.engines.e0 import checker as checker_mod
from esgapi.greenwash.engines.e0 import result as gw1_result
from esgapi.greenwash.engines.e0.checker import (
    scan_report_greenwashing_pages,  # pyright: ignore[reportUnknownVariableType]
)
from esgapi.greenwash.engines.e0.chunking import build_chunks_from_docs
from esgapi.greenwash.engines.e0.gw1 import build_results_by_part
from esgapi.greenwash.engines.e0.parts import build_section_pages
from esgapi.greenwash.engines.e0.pdftext import docs_from_texts
from esgapi.greenwash.engines.e0.ports import EMBEDDING_MODEL, HumanMessage, MockEmbedding, ScriptedChat, SystemMessage
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.engines.e0.retrieval import VectorIndex
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.colab_e0 import PROMPT_IDS, EmbeddingPort, LlmChatBridge
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.sample_text import page_texts

STEPS = ("extract", "index", "judge", "wordcount", "locate", "report")
TAGS = Tags(tenant="tenant-synthetic", module="greenwash")


def check_shape(result: dict[str, Any]) -> None:
    assert next(iter(result)) == "schemaVersion"
    shapes.RESULT_SHAPES[shapes.SHAPE].validate_python(result, strict=True)


def test_the_flow_is_declared() -> None:
    flow = colab.FLOW
    assert (flow.module, flow.id, flow.input_shape) == ("greenwash", "greenwash.colab@E0", "greenwash.document@1")
    assert flow.steps == STEPS
    assert flow.result_shapes == ("greenwash.result@1",)
    assert flow.output_files == ("greenwash-report.xlsx",)
    assert flow.adapter_names == ("pdf_text", "llm", "embedding", "coordinates", "tokens")
    assert flow.optional_adapters == ("coordinates", "tokens")


# ── 대조 A (pytest 판): 표본 쪽 글 + 내장 대본 + 모의 임베딩 ──


def test_contrast_a_matches_gw1() -> None:
    gw1 = s.golden("sample-mock.json")
    chat, emb = ScriptedChat(), MockEmbedding()
    flow_run = s.run(s.inputs(), s.adapters(llm=chat, embedding=emb))
    result = s.result_of(flow_run)
    check_shape(result)
    assert s.as_gw1(result) == s.gw1_view(gw1)
    assert s.message_hashes(chat.sent) == gw1["messages"] and len(gw1["messages"]) == 12
    assert s.chat_calls(chat.sent) == gw1["calls"]["chat"]
    assert len(emb.document_requests) == gw1["calls"]["embedding_document_requests"]
    assert emb.query_requests == gw1["calls"]["embedding_query_requests"]
    assert all(item["position"] is None and item["exampleSentence"] is None for item in result["items"])
    assert (result["dryRun"], result["report"]) == (None, {"file": "greenwash-report.xlsx"})
    assert [f.name for f in flow_run.output.files] == ["greenwash-report.xlsx"]
    assert len(result["items"]) == 6 and {i["level"] for i in result["items"]} == {"High", "Mid", "Low"}


def test_no_pages_skips_the_index_and_calls_nothing() -> None:
    gw1 = s.golden("sample-none.json")
    forbidden = s.Forbidden()
    flow_run = s.run(s.inputs(ceo="", company="", climate=""), s.adapters(llm=forbidden, embedding=forbidden))
    result = s.result_of(flow_run)
    check_shape(result)
    assert forbidden.calls == 0
    assert flow_run.steps["index"].data == {"chunks": [], "chunk_config": None, "empty_chunks": 0, "vectors": None}
    assert flow_run.steps["index"].files == ()
    assert result["items"] == [] and result["pages"] == []
    assert s.as_gw1(result) == s.gw1_view(gw1)


def test_every_step_output_round_trips_and_steps_run_alone() -> None:
    flow_run = s.run(s.inputs(), s.adapters(coordinates=s.BoxCoordinates()))
    for name in STEPS:
        data = flow_run.steps[name].data
        assert json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False)) == data
    carried = {name: flow_run.steps[name] for name in STEPS}
    alone = colab.wordcount(s.inputs(), s.adapters(), carried, StepContext(resume=None))
    assert alone.data == flow_run.steps["wordcount"].data
    again = colab.extract(s.inputs(), s.adapters(), {}, StepContext(resume=None))
    assert again.data == flow_run.steps["extract"].data
    assert flow_run.steps["extract"].data["pages"] == page_texts()


def test_the_vectors_file_holds_float32_rows_in_chunk_order() -> None:
    flow_run = s.run(s.inputs(), s.adapters())
    index = flow_run.steps["index"]
    meta = cast("dict[str, int]", index.data["vectors"])
    (blob,) = [f.content for f in index.files if f.name == colab.VECTORS_FILE]
    assert len(blob) == meta["rows"] * meta["dim"] * 4 and meta["rows"] == len(cast("list[Any]", index.data["chunks"]))
    assert index.data["empty_chunks"] == 0


# ── judge 의 루프 = GW1 scan_report_greenwashing_pages ──


def test_the_judge_loop_is_the_gw1_scan() -> None:
    gw1_chat, flow_chat = ScriptedChat(), ScriptedChat()
    want = gw1_scan(gw1_chat)
    assert s.run(s.inputs(), s.adapters(llm=flow_chat)).steps["judge"].data == want
    assert s.message_hashes(flow_chat.sent) == s.message_hashes(gw1_chat.sent)


def gw1_scan(chat: Any) -> dict[str, Any]:
    """GW1 checker.scan_report_greenwashing_pages 를 cli.run_scan 과 같은 인자로 부른다(표본, 쪽 입력 1 / 2 / 3~4)."""
    docs = docs_from_texts(page_texts())
    _, manual_pages = build_section_pages("1", "2", "3~4", len(docs))
    built = build_chunks_from_docs(docs, **colab.CHUNK_ARGS)
    outcome = scan_report_greenwashing_pages(
        docs,
        manual_pages,
        evidence_allowed_pages=manual_pages,
        config=dict(colab.SCAN_CONFIG),
        vectorstore=VectorIndex.from_documents(built["chunks"], MockEmbedding()),
        llm=chat,
    )
    want = {
        "results": outcome.results,
        "agg": outcome.agg,
        "failed": outcome.failed,
        "failed_pages": outcome.failed_pages,
        "pages_norm": outcome.pages_norm,
        "allowed_norm": outcome.allowed_norm,
    }
    return json.loads(json.dumps(want, ensure_ascii=False))


@pytest.mark.parametrize("fail_pages", [[2], [1, 4]])
def test_a_failing_page_is_swallowed_like_gw1(fail_pages: list[int]) -> None:
    """흠 12·19: 쪽 안의 예외는 삼켜 failed_pages 에 적고, 그 쪽의 후보·판정은 버린다 — GW1 함수와 칸마다 같다."""
    gw1_chat, flow_chat = s.FailingChat(fail_pages), s.FailingChat(fail_pages)
    want = gw1_scan(gw1_chat)
    flow_run = s.run(s.inputs(), s.adapters(llm=flow_chat))
    assert flow_run.steps["judge"].data == want
    assert want["failed"] == len(fail_pages) and [f["page"] for f in want["failed_pages"]] == fail_pages
    assert s.message_hashes(flow_chat.sent) == s.message_hashes(gw1_chat.sent)
    result = s.result_of(flow_run)
    check_shape(result)
    assert result["candidateStats"]["failedPages"] == want["failed_pages"]
    assert all(item["page"] not in fail_pages for item in result["items"])


def test_contrast_d_carries_a_failed_page_across_the_resume() -> None:
    whole_run = s.run(s.inputs(), s.adapters(llm=s.FailingChat([1])))
    whole = s.result_of(whole_run)
    chat = s.FailingChat([1])
    used = s.adapters(llm=chat)
    recorder = s.Recorder(stop_after=2)
    with pytest.raises(s.Interrupted):
        s.run(s.inputs(), used, events=recorder)
    assert recorder.saved is not None and recorder.saved["failed"] == 1
    carried = {name: recorder.finished[name] for name in ("extract", "index")}
    resumed_run = s.run(s.inputs(), used, start_at="judge", carried=carried, resume=recorder.saved)
    resumed = s.result_of(resumed_run)
    assert resumed == whole
    assert resumed_run.steps["judge"].data == whole_run.steps["judge"].data  # failed 수처럼 결과에 없는 칸까지
    assert [f["page"] for f in resumed["candidateStats"]["failedPages"]] == [1]


def test_progress_total_is_the_checked_pages_not_the_document() -> None:
    recorder = s.Recorder()
    s.run(s.inputs(ceo="1", company="", climate="3"), s.adapters(), events=recorder)
    assert [(d, t) for step, d, t in recorder.progress if step == "judge"] == [(1, 2), (2, 2)]


def test_the_index_counts_empty_chunks_without_dropping_them(monkeypatch: pytest.MonkeyPatch) -> None:
    def chunks_with_an_empty_one(docs: list[Document], **kwargs: Any) -> dict[str, Any]:
        made = [Document(page_content="글", metadata={"page": 0}), Document(page_content="", metadata={"page": 1})]
        return {"chunks": made, "config": {}}

    monkeypatch.setattr(colab, "build_chunks_from_docs", chunks_with_an_empty_one)
    flow_run = s.run(s.inputs(dry_run=True), s.adapters(tokens=s.char_counter()))
    index = flow_run.steps["index"].data
    assert index["empty_chunks"] == 1 and len(cast("list[Any]", index["chunks"])) == 2


def test_the_judge_reports_progress_page_by_page() -> None:
    recorder = s.Recorder()
    s.run(s.inputs(), s.adapters(), events=recorder)
    assert [(d, t) for step, d, t in recorder.progress if step == "judge"] == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert {step for step, _, _ in recorder.progress} == {"judge"}


# ── 대조 D: judge 가 둘째 쪽 뒤에 끊긴 뒤 이어 돈다 ──


def detect_pages(sent: list[list[Any]]) -> list[int]:
    """탐지 프롬프트의 user 글에서 쪽 번호를 읽는다(「…보고서의 {쪽}페이지 일부입니다」)."""
    pack_detect = ScriptedChat().pack.detect_system_prompt
    out: list[int] = []
    for msgs in sent:
        if msgs[0].content == pack_detect:
            head = msgs[1].content.split("페이지", 1)[0]
            out.append(int(head.rsplit(" ", 1)[-1]))
    return out


def test_contrast_d_resume_after_the_second_page() -> None:
    whole = s.result_of(s.run(s.inputs(), s.adapters()))

    chat, emb = ScriptedChat(), MockEmbedding()
    used = s.adapters(llm=chat, embedding=emb)
    recorder = s.Recorder(stop_after=2)
    with pytest.raises(s.Interrupted):
        s.run(s.inputs(), used, events=recorder)
    assert recorder.saved is not None and recorder.saved["done_pages"] == [1, 2]
    first_part = len(chat.sent)
    carried = {name: recorder.finished[name] for name in ("extract", "index")}

    resumed = s.run(s.inputs(), used, start_at="judge", carried=carried, resume=recorder.saved)
    assert s.result_of(resumed) == whole
    assert detect_pages(chat.sent[:first_part]) == [1, 2]
    assert detect_pages(chat.sent[first_part:]) == [3, 4]  # 끝난 쪽은 다시 묻지 않는다
    assert s.message_hashes(chat.sent) == s.golden("sample-mock.json")["messages"]


# ── dry-run (대조 C 의 pytest 판) ──


def test_dry_run_counts_without_calling_llm_or_embedding() -> None:
    forbidden = s.Forbidden()
    flow_run = s.run(s.inputs(dry_run=True), s.adapters(llm=forbidden, embedding=forbidden, tokens=s.char_counter()))
    result = s.result_of(flow_run)
    check_shape(result)
    assert forbidden.calls == 0
    assert result["dryRun"] == s.golden_wire("sample-dryrun.json")["dryRun"]
    assert (result["items"], result["candidateStats"], result["counts"], result["report"]) == ([], None, None, None)
    assert result["wordCounts"] == s.golden_wire("sample-mock.json")["wordCounts"]
    assert flow_run.output.files == ()
    assert flow_run.steps["index"].data["vectors"] is None and flow_run.steps["index"].files == ()


def test_dry_run_without_tokens_fails_in_judge() -> None:
    forbidden = s.Forbidden()
    with pytest.raises(FlowStepFailed) as failed:
        s.run(s.inputs(dry_run=True), s.adapters(llm=forbidden, embedding=forbidden))
    assert failed.value.step == "judge"
    assert "tokens" in str(failed.value.__cause__)
    assert forbidden.calls == 0


def test_a_non_pdf_fails_in_extract() -> None:
    given = colab.GreenwashInputs(
        document=b"x", media_type="text/plain", file_name="x.txt", ceo="1", company="", climate=""
    )
    with pytest.raises(FlowStepFailed) as failed:
        s.run(given, s.adapters())
    assert failed.value.step == "extract"


# ── locate ──


def test_locate_without_coordinates_is_all_null_and_with_fake_boxes_fits_the_shape() -> None:
    plain = s.result_of(s.run(s.inputs(), s.adapters()))
    assert [i["position"] for i in plain["items"]] == [None] * len(plain["items"])
    coordinates = s.BoxCoordinates()
    boxed = s.result_of(s.run(s.inputs(), s.adapters(coordinates=coordinates)))
    check_shape(boxed)
    assert [(i["page"], i["sentence"]) for i in boxed["items"]] == coordinates.calls
    assert all(i["position"] is not None and i["position"]["page"] == i["page"] for i in boxed["items"])
    assert all(i["exampleSentence"] is None for i in boxed["items"])
    assert any(len(i["position"]["boxes"]) == 2 for i in boxed["items"])
    dry = s.run(s.inputs(dry_run=True), s.adapters(coordinates=coordinates, tokens=s.char_counter()))
    assert dry.steps["locate"].data == {"positions": []}


# ── 셈 ──


def test_counts_by_part_count_a_page_in_two_parts_twice() -> None:
    result = s.result_of(s.run(s.inputs(ceo="1~2", company="2", climate="2~4"), s.adapters()))
    check_shape(result)
    counts = result["counts"]
    section = {p["name"]: p["pages"] for p in result["parts"]}
    want = {
        part: {level: sum(1 for r in rows if r["level"] == level) for level in ("High", "Mid", "Low")}
        for part, rows in build_results_by_part(result["items"], section).items()
    }
    assert counts["byPart"] == want
    assert counts["total"] == len(result["items"]) == sum(counts["byLevel"].values())
    assert sum(sum(levels.values()) for levels in counts["byPart"].values()) > counts["total"]


# ── 상수 = GW1 ──


def test_the_constants_are_gw1s() -> None:
    consts = s.golden("gw1-consts.json")
    assert consts["SCAN_CONFIG"] == colab.SCAN_CONFIG
    assert gw1_result.chunk_defaults() == consts["chunk_defaults"]
    chunk_args = {k: v for k, v in consts["chunk_defaults"].items() if k != "separators"}
    assert chunk_args == colab.CHUNK_ARGS
    assert (
        consts["MODEL_NAME"],
        consts["TEMPERATURE"],
        consts["MAX_TOKENS"],
    ) == (colab.MODEL_NAME, colab.TEMPERATURE, colab.MAX_TOKENS)
    assert colab.MAX_OUTPUT_TOKENS == consts["MAX_TOKENS"] == checker_mod.MAX_TOKENS
    assert consts["PROMPT_VERSION"] == PROMPT_VERSION and consts["EMBEDDING_MODEL"] == EMBEDDING_MODEL
    assert "env_keywords_extra" not in colab.SCAN_CONFIG and "include_general_env" not in colab.SCAN_CONFIG


def test_step_output_is_a_step_output() -> None:
    out = colab.extract(s.inputs(), s.adapters(), {}, StepContext(resume=None))
    assert isinstance(out, StepOutput) and out.files == ()
    docs = [Document(page_content=t, metadata={"page": i}) for i, t in enumerate(page_texts())]
    assert [d.page_content for d in docs] == out.data["pages"]


# ── 어댑터: 프롬프트 렌더(§2-5), LlmChatBridge 로 지난 대조 B, L1 임베딩 포트로 지난 대조 A(모의 공급사·모의 임베딩) ──


def test_rendering_keeps_a_value_byte_for_byte() -> None:
    """core 는 한 번만 치환하고 넣은 값을 다시 훑지 않는다 — 앞뒤 공백·줄바꿈과 `{{` 가 든 값이 그대로 나온다."""
    system = "  \n앞에 공백과 줄바꿈 {{user}} {{ not_a_var }} {{x}}\t\n\n"
    user = "\n\t{{system}} 노트북의 글처럼 {{ 와 }} 가 든 값\n  "
    for prompt_id in PROMPT_IDS.values():
        template = PackagePromptStore().get(parse_prompt_id(prompt_id))
        rendered = render_prompt(template, {"system": system, "user": user})
        assert [seg.text for seg in rendered.system] == [system]
        assert rendered.user == user


def scripted_provider(calls: int) -> tuple[MockProvider, ScriptedChat]:
    """받은 요청의 system·user 글로 ScriptedChat 과 같은 대본 답을 돌려주는 모의 공급사(큐에 calls 개)."""
    script = ScriptedChat()

    def reply(request: ProviderRequest) -> ProviderResponse:
        system = "".join(seg.text for seg in request.system)
        user = "".join(part.text for part in request.user if isinstance(part, TextPart))
        return Completed(text=script.respond(system, user), usage=SYNTHETIC_USAGE)

    mock = MockProvider()
    for _ in range(calls):
        mock.enqueue(reply)
    return mock, script


def bridge(mock: MockProvider, sink: MemorySink) -> LlmChatBridge:
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=True)),
        providers={"mock": mock},
        prompts=PackagePromptStore(),
        log=sink,
    )
    return LlmChatBridge(client, route="mock", tags=TAGS)


def provider_hashes(requests: list[ProviderRequest]) -> list[str]:
    pairs = [
        ["".join(seg.text for seg in r.system), "".join(p.text for p in r.user if isinstance(p, TextPart))]
        for r in requests
    ]
    return [s.sha256_text(json.dumps(pair, ensure_ascii=False)) for pair in pairs]


def test_contrast_b_through_core_llm_is_the_same() -> None:
    gw1 = s.golden("sample-mock.json")
    mock, _ = scripted_provider(20)
    sink = MemorySink()
    result = s.result_of(s.run(s.inputs(), s.adapters(llm=bridge(mock, sink))))
    assert s.as_gw1(result) == s.gw1_view(gw1)
    assert provider_hashes(mock.calls) == gw1["messages"]
    assert len(sink.records) == len(gw1["messages"]) == 12
    assert mock.pending == 20 - 12  # 남은 큐(보고에 적는다)
    assert {r.prompt_id for r in sink.records} == set(PROMPT_IDS.values())
    assert all(r.max_output_tokens == 1300 for r in mock.calls)
    # 코랩 온도(checker.TEMPERATURE)가 요청마다 float 0.0 으로 간다(밴드 GTE1). int 0·-0.0 은 요청 해시가 갈린다.
    assert [(r.temperature, type(r.temperature)) for r in mock.calls] == [(0.0, float)] * 12
    assert [str(r.temperature) for r in mock.calls] == ["0.0"] * 12  # -0.0 이면 "-0.0"


def test_the_bridge_refuses_what_is_not_a_notebook_call() -> None:
    mock, _ = scripted_provider(1)
    used = bridge(mock, MemorySink())
    with pytest.raises(ValueError, match="프롬프트 넷"):
        used.invoke([SystemMessage(content="다른 system 글"), HumanMessage(content="u")])
    with pytest.raises(ValueError, match="둘이어야"):
        used.invoke([HumanMessage(content="u")])
    empty = bridge(MockProvider(), MemorySink())  # 큐가 비면 공급사 오류 → Success 가 아님
    pack = default_prompts(PROMPT_VERSION)
    with pytest.raises(RuntimeError, match="성공하지 못했다"):
        empty.invoke([SystemMessage(content=pack.detect_system_prompt), HumanMessage(content="u")])


def test_the_l1_embedding_port_fills_the_port_and_gives_the_same_result() -> None:
    client = build_embedding_client(LlmSettings(), mock=True)
    port: EmbeddingPort = ClientEmbeddingPort(client, route="mock-gw1", tags=TAGS, batch_size=50)
    flow_run = s.run(s.inputs(), s.adapters(embedding=port))
    assert s.as_gw1(s.result_of(flow_run)) == s.gw1_view(s.golden("sample-mock.json"))
    assert flow_run.steps["index"].data["empty_chunks"] == 0


def test_message_hash_helper_matches_the_driver() -> None:
    sent = [[SystemMessage(content="가"), HumanMessage(content="나")]]
    assert s.message_hashes(sent) == [s.sha256_text(json.dumps(["가", "나"], ensure_ascii=False))]
