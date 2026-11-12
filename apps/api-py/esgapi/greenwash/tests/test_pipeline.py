# pyright: basic
# ruff: noqa: E501, I001  (긴 줄, import 차례(경로를 바꾼 import) — GW1 그대로)
# ↑ GW1 테스트의 사본(import 경로만 바꿈. CLI·PDF 절의 테스트 넷과 그것만 쓰던 import·고정물은 뺐다). 타입 표기 없는 GW1 의 꼴 그대로라 strict 를 끈다.
"""조각내기, 정확 L2 검색, 포트(모의·기록·토큰 세기), dry-run 의 셈, 결과 JSON 의 스키마, CLI."""

import json

import numpy as np
import pytest

from esgapi.greenwash.engines.e0 import heuristics
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.engines.e0 import result as result_mod
from esgapi.greenwash.engines.e0.checker import MAX_TOKENS
from esgapi.greenwash.engines.e0.chunking import build_chunks_from_docs
from esgapi.greenwash.engines.e0.dryrun import dry_run
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.engines.e0.ports import (
    CHAT_ENCODING,
    EMBEDDING_ENCODING,
    CallLog,
    MockEmbedding,
    RecordingChat,
    RecordingEmbedding,
    ScriptedChat,
    Tally,
    TokenCounter,
)
from esgapi.greenwash.engines.e0.retrieval import VectorIndex, embedding_request_count, l2_order
from esgapi.greenwash.tests.conftest import make_docs

SCAN_CONFIG = {"debug": True, "debug_pages": 2}
CHAR_COUNTER = TokenCounter({CHAT_ENCODING: len, EMBEDDING_ENCODING: len})  # 글자 수 = 토큰 수인 가짜 세기


# ---------------- 조각내기 ----------------
def test_chunks_carry_page_and_ids_and_leave_docs_alone(sample_docs):
    before = [d.page_content for d in sample_docs]
    built = build_chunks_from_docs(sample_docs)
    chunks = built["chunks"]
    assert built["config"] == {
        "chunk_size": 800,
        "chunk_overlap": 150,
        "embedding_model": "text-embedding-3-small",
        "embedding_batch_size": 50,
        "separators": ["\n\n", "\n", " "],
        "normalize": True,
    }
    assert [d.page_content for d in sample_docs] == before
    assert all(len(c.page_content) <= 800 for c in chunks)
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))
    last = chunks[-1].metadata
    assert set(last) == {"page", "start_index", "source_page", "chunk_index", "chunk_id"}
    assert (last["page"], last["source_page"], last["chunk_id"]) == (3, 4, f"p4-c{len(chunks) - 1}")
    page4 = [c for c in chunks if c.metadata["page"] == 3]
    assert len(page4) >= 5 and page4[1].metadata["start_index"] < len(page4[0].page_content)  # 겹침이 있다
    assert "\n" not in chunks[0].page_content  # 줄바꿈 하나는 공백이 된다
    with pytest.raises(ValueError):
        build_chunks_from_docs([])


# ---------------- 검색 ----------------
def test_l2_order_is_exact_and_stable_on_ties():
    m = np.array([[1, 0], [0, 1], [1, 0], [0.9, 0.1], [-1, 0]], dtype=np.float32)
    assert l2_order(m, np.array([1, 0], dtype=np.float32), 4) == [0, 2, 3, 1]
    assert l2_order(m, np.array([1, 0], dtype=np.float32), 99) == [0, 2, 3, 1, 4]
    assert l2_order(np.zeros((0, 2), dtype=np.float32), np.array([1, 0]), 3) == []


def test_index_embeds_in_batches_of_fifty_and_query_once(sample_docs):
    docs = make_docs([f"조각 {i} 온실가스" for i in range(120)])
    emb = MockEmbedding()
    index = VectorIndex.from_documents(docs, emb)
    assert (
        emb.document_requests == [50, 50, 20] and embedding_request_count(120) == 3 and embedding_request_count(0) == 0
    )
    got = index.similarity_search("조각 77 온실가스", k=12)
    assert emb.query_requests == 1 and len(got) == 12
    assert got[0].page_content == "조각 77 온실가스"  # 흠 3: 같은 글의 조각이 맨 앞에 돌아온다
    assert (
        emb.embed_query("가나다") == emb.embed_query("가나다")
        and abs(sum(x * x for x in emb.embed_query("가나다")) - 1) < 1e-9
    )


# ---------------- 포트 ----------------
def test_scripted_chat_cycles_per_kind_and_renders_entries():
    chat = ScriptedChat({"detect": [{"pick_env": 1}, "[]"], "eval": [{"fenced": {"decision": "High"}}]})
    pack = chat.pack
    user = (
        "머리\n\n[텍스트]\n탄소 감축. 가상상사는 온실가스 배출량을 줄였습니다. 재생에너지 사용을 늘렸다고 밝혔습니다."
    )
    assert json.loads(chat.respond(pack.detect_system_prompt, user)) == [
        {"sentence": "가상상사는 온실가스 배출량을 줄였습니다."}
    ]
    assert chat.respond(pack.detect_system_prompt, user) == "[]"
    assert chat.respond(pack.detect_system_prompt, user).startswith("[{")  # 한 바퀴 돌아 처음으로
    assert chat.respond(pack.eval_system_prompt, "") == '```json\n{\n  "decision": "High"\n}\n```'
    with pytest.raises(ValueError):
        chat.respond(pack.repair_fix_prompt, "")  # 대본에 없는 갈래
    with pytest.raises(ValueError):
        chat.respond("넷 가운데 어느 것도 아닌 프롬프트", "")


CALL_RECORD_KEYS = {
    "ts",
    "callId",
    "attempt",
    "provider",
    "model",
    "apiModelId",
    "responseModelId",
    "promptId",
    "promptVersion",
    "templateHash",
    "requestHash",
    "inputTokens",
    "outputTokens",
    "cacheReadTokens",
    "cacheWriteTokens",
    "costUsd",
    "durationMs",
    "resultKind",
    "tenant",
    "module",
    "warnings",
}


def test_call_records_use_the_ts_llm_field_names_and_do_not_store_bodies():
    log = CallLog()
    chat = RecordingChat(
        ScriptedChat({"detect": ["[]"]}), log, provider="mock", model="gpt-4.1-mini", params={"temperature": 0.0}
    )
    emb = RecordingEmbedding(MockEmbedding(), log, provider="mock")
    from esgapi.greenwash.engines.e0.ports import HumanMessage, SystemMessage

    chat.invoke([SystemMessage(chat.pack.detect_system_prompt), HumanMessage("비밀 글")])
    emb.embed_documents([f"글 {i}" for i in range(51)])
    emb.embed_query("물음")
    assert [r["promptId"] for r in log.records] == ["greenwash/detect", "embedding", "embedding", "embedding"]
    assert set(log.records[0]) == CALL_RECORD_KEYS and set(log.records[1]) == CALL_RECORD_KEYS | {"embeddingInputs"}
    assert [r.get("embeddingInputs") for r in log.records] == [None, 50, 1, 1]
    first = log.records[0]
    assert (first["provider"], first["module"], first["resultKind"], first["promptVersion"]) == (
        "mock",
        "greenwash",
        "ok",
        "2026-01-15-v1",
    )
    assert first["inputTokens"] is None and first["costUsd"] is None  # 0 이 아니라 null
    assert "비밀 글" not in json.dumps(log.records, ensure_ascii=False)
    assert [r["callId"] for r in log.records] == ["gw-00001", "gw-00002", "gw-00003", "gw-00004"]


def test_tally_keeps_unmeasured_apart_from_zero():
    assert (CHAT_ENCODING, EMBEDDING_ENCODING) == ("o200k_base", "cl100k_base")  # tiktoken 이 두 모델에 주는 부호화
    t = Tally(CHAT_ENCODING)
    t.add(CHAR_COUNTER, ["가나", "다"])
    assert t.to_json() == {
        "requests": 1,
        "input_chars": 3,
        "input_tokens": {"status": "measured", "encoding": CHAT_ENCODING, "value": 3},
    }
    empty = Tally(CHAT_ENCODING)
    assert empty.to_json()["input_tokens"] == {
        "status": "measured",
        "encoding": CHAT_ENCODING,
        "value": 0,
    }  # 요청이 없어서 0
    lost = Tally(CHAT_ENCODING)
    lost.add(TokenCounter({}, {CHAT_ENCODING: "ConnectionError: 받지 못함"}), ["가나"])
    assert lost.to_json()["input_tokens"] == {
        "status": "unmeasured",
        "encoding": CHAT_ENCODING,
        "reason": "ConnectionError: 받지 못함",
    }
    t.merge(lost)
    assert t.to_json()["input_tokens"]["status"] == "unmeasured" and t.to_json()["input_chars"] == 5


# ---------------- dry-run ----------------
def test_dry_run_bounds(sample_docs):
    d = dry_run(sample_docs, [1, 2, 3, 4], [1, 2, 3, 4], SCAN_CONFIG, CHAR_COUNTER)
    assert (d["pages_checked"], d["pages_with_text"], d["pages_truncated"]) == (4, 4, 1)
    assert d["embedding_index"]["requests"] == 1 and d["chunks"] == len(build_chunks_from_docs(sample_docs)["chunks"])
    assert d["rule_candidates"] == sum(p["rule_candidates"] for p in d["per_page"]) == 9
    lower, upper = d["lower"], d["upper"]
    judged = sum(p["lower_judged"] for p in d["per_page"])
    # 아래끝: 탐지는 쪽마다 1, 판정은 규칙 후보가 거름과 쿼터를 지난 수, 다시 묻기 0, 근거 물음은 판정마다 1.
    assert [p["lower_judged"] for p in d["per_page"]] == [2, 0, 1, 1]
    assert lower["judged"] == judged == 4
    assert lower["chat"]["requests"] == 4 + judged
    assert {k: v["requests"] for k, v in lower["chat_by_kind"].items()} == {
        "detect": 4,
        "eval": 1,
        "low_only": 3,
        "repair": 0,
    }
    assert lower["embedding_queries"]["requests"] == judged
    # 위끝: 쪽마다 탐지 1 + 평가 3 + Low 전용 1 + 다시 묻기 3, 근거 물음 4.
    assert {k: v["requests"] for k, v in upper["chat_by_kind"].items()} == {
        "detect": 4,
        "eval": 12,
        "low_only": 4,
        "repair": 12,
    }
    assert upper["chat"]["requests"] == 8 * 4 and upper["embedding_queries"]["requests"] == 4 * 4
    assert upper["output_tokens_max"] == 8 * 4 * MAX_TOKENS
    assert upper["chat_by_kind"]["detect"] == lower["chat_by_kind"]["detect"]
    assert (
        upper["evidence_cap_reached"] is False
        and upper["evidence_chars"] <= 2 * (len("[p.4]\n") + 450 + len(" ...")) + 2
    )
    assert upper["chat"]["input_tokens"] == {
        "status": "measured",
        "encoding": CHAT_ENCODING,
        "value": upper["chat"]["input_chars"],
    }
    assert upper["chat"]["input_chars"] > lower["chat"]["input_chars"]
    # 위끝의 글: 문장 자리에 그 쪽의 가장 긴 문장, 근거 자리에 가장 큰 조각 둘(기본 설정의 최대 = 2 × (머리 줄 + 450자 + 꼬리) + 2).
    pack = default_prompts(PROMPT_VERSION)
    longest = [max(heuristics.split_sentences_kor(heuristics.get_page_text(doc, 2500)), key=len) for doc in sample_docs]
    assert upper["evidence_chars"] == 2 * (len("[p.4]\n") + 450 + len(" ...")) + 2 == 922
    users = [len(f"[문장]\n{s}\n\n[근거 컨텍스트]\n") + 922 + 1 for s in longest]
    assert upper["chat_by_kind"]["eval"]["input_chars"] == sum(3 * (len(pack.eval_system_prompt) + u) for u in users)
    assert upper["chat_by_kind"]["low_only"]["input_chars"] == sum(len(pack.low_only_prompt) + u for u in users)
    assert upper["chat_by_kind"]["repair"]["input_chars"] == sum(
        3 * (len(pack.repair_fix_prompt) + u + len("\n[리스크 등급]\nHigh\n")) for u in users
    )
    assert upper["embedding_queries"]["input_chars"] == 4 * sum(len(s) for s in longest)
    assert d["embedding_index"]["input_chars"] == sum(
        len(c.page_content) for c in build_chunks_from_docs(sample_docs)["chunks"]
    )


def test_dry_run_counts_index_requests_in_batches_of_fifty_and_refuses_a_failed_lower_run():
    docs = make_docs([f"쪽 {i} 의 글입니다." for i in range(120)])
    d = dry_run(docs, [1], [1], SCAN_CONFIG, CHAR_COUNTER)
    assert (d["chunks"], d["embedding_index"]["requests"]) == (120, 3)
    assert SCAN_CONFIG == colab.SCAN_CONFIG == {"debug": True, "debug_pages": 2}  # 셀 16 의 설정
    assert result_mod.chunk_defaults() == build_chunks_from_docs(docs)["config"]


def test_dry_run_empty_page_sends_nothing_and_missing_encoder_is_unmeasured():
    docs = make_docs(["", "가상상사는 재생에너지 사용을 확대해 나가겠습니다."])
    d = dry_run(
        docs,
        [1, 2],
        [1, 2],
        SCAN_CONFIG,
        TokenCounter({}, {CHAT_ENCODING: "받지 못함", EMBEDDING_ENCODING: "받지 못함"}),
    )
    assert (d["pages_checked"], d["pages_with_text"]) == (2, 1)
    assert d["lower"]["chat"]["requests"] == 2 and d["upper"]["chat"]["requests"] == 8
    for tally in (
        d["embedding_index"],
        d["lower"]["chat"],
        d["upper"]["chat"],
        d["lower"]["embedding_queries"],
        d["upper"]["embedding_queries"],
    ):
        assert tally["input_tokens"]["status"] == "unmeasured" and "value" not in tally["input_tokens"]
        assert tally["input_chars"] > 0
    assert d["lower"]["chat_by_kind"]["repair"]["input_tokens"]["status"] == "measured"  # 요청 0 이라 잴 것이 없었다
