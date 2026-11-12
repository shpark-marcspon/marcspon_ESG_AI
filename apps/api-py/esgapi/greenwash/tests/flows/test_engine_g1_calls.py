"""흐름 greenwash.engine@G1 의 대화 다리(flows/engine_g1.G1Calls — 밴드 GE1 T10·T11): 요청 몸(경로 light-openai =
luna, 구조화 출력, temperature 없음, 답 상한 + 추론 여유)과 실패 옮김(판정 실패 갈래 셋, 근거 찾기 SearchFailed, 재순위
잘림의 id 건짐). 공급사는 모의(MockProvider)를 openai 자리에 끼운다 — 실제 네트워크·키 0. 글은 지어낸 것.
"""

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

import pytest

from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.embedding import EmbeddingFailed, EmbeddingPort, EmbedProviderFailed
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import (
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    Refusal,
    Tags,
    Truncated,
    Usage,
)
from esgapi.greenwash.engines.g1 import evidence as ev
from esgapi.greenwash.engines.g1 import judge as J
from esgapi.greenwash.flows import criteria_e0
from esgapi.greenwash.flows import engine_g1 as E

TAGS = Tags(tenant="tenant-synthetic", module="greenwash")
U = Usage(input_tokens=10, output_tokens=5, cache_read_tokens=0, cache_write_tokens=0)
LINES = (J.CriterionLine(id="made-line-1", group="high", text="가상 점검 줄 하나"),)
ANSWER = (
    '{"criteria":[{"lineId":"made-line-1","hit":true}],"level":"None","category":null,'
    '"reason":"가상 근거가 받친다.","confirmed":["가상 수치"],"missing":[],"evidence":["P2"]}'
)


class NoEmbedding:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("부르면 안 된다")

    def embed_query(self, text: str) -> list[float]:
        raise AssertionError("부르면 안 된다")


class FailingEmbedding(NoEmbedding):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingFailed(cast("EmbedProviderFailed", SimpleNamespace(kind="provider_error")))


def calls_with(mock: MockProvider, embedding: EmbeddingPort | None = None) -> E.G1Calls:
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": mock},
        prompts=PackagePromptStore(),
        log=MemorySink(),
        store_bodies=True,
    )
    return E.G1Calls(client, embedding or NoEmbedding(), tags=TAGS, vocab="가상 말 목록")


def judge_vars() -> dict[str, str]:
    return J.judge_vars(
        claim="가상회사는 가상 목표를 이뤘다.", page=4, evidence="[P2 · p.9] 가상 근거", lines=LINES, categories=[]
    )


# ── T10 요청 몸 ──


def test_the_route_is_luna_alone_in_the_real_config() -> None:
    config = load_config(default_config_sources(synthetic=False))
    assert config.routes[E.ROUTE] == ("gpt-6-luna",)


@pytest.mark.parametrize(
    ("step", "schema", "answer_max", "reply"),
    [
        ("judge", "judge", E.JUDGE_MAX_TOKENS, ANSWER),
        ("plan", "facets", E.PLAN_MAX_TOKENS, '{"facets":[]}'),
        ("rerank", "rerank", E.RERANK_MAX_TOKENS, '{"order":["P1"]}'),
    ],
)
def test_requests_carry_a_schema_no_temperature_and_the_answer_cap_plus_reasoning(
    step: str, schema: str, answer_max: int, reply: str
) -> None:
    mock = MockProvider("openai").enqueue_text(reply)
    calls = calls_with(mock)
    run: dict[str, Callable[[], object]] = {
        "judge": lambda: calls.judge(judge_vars()),
        "plan": lambda: calls.plan("가상 주장"),
        "rerank": lambda: calls.rerank("가상 주장", "[P1] 가상 단락"),
    }
    run[step]()
    (sent,) = mock.calls
    assert sent.api_model_id == "gpt-6-luna"
    assert sent.temperature is None
    assert sent.json_schema is not None
    assert sent.json_schema.name == schema
    assert sent.max_output_tokens == answer_max + 2000


def test_the_judge_answer_cap_is_2000_sent_as_4000() -> None:
    assert J.ANSWER_MAX_TOKENS == 2000
    mock = MockProvider("openai").enqueue_text(ANSWER)
    calls_with(mock).judge(judge_vars())
    assert mock.calls[0].max_output_tokens == 4000


def test_the_criterion_lines_in_the_prompt_are_the_argument() -> None:
    mock = MockProvider("openai").enqueue_text(ANSWER)
    reply = calls_with(mock).judge(judge_vars())
    system = "".join(s.text for s in mock.calls[0].system)
    assert "[made-line-1] (High 조건) 가상 점검 줄 하나" in system
    assert "keyword-ghg" not in system
    assert reply.answer is not None
    assert reply.answer.level == "None"


def test_default_criterion_lines_are_the_enabled_e0_rows() -> None:
    rows = [r for r in criteria_e0.default_criteria()["rows"] if r["enabled"]]
    lines = E.default_criterion_lines()
    assert [ln.id for ln in lines] == [r["id"] for r in rows]
    assert len(lines) == 15
    for ln, row in zip(lines, rows, strict=True):
        assert ln.group == row["category"]
        assert ln.text.startswith(row["text"])
        assert (row["terms"] is None) == (ln.text == row["text"])


# ── T11 실패 옮김 ──


@pytest.mark.parametrize(
    ("replies", "code"),
    [
        (['{"level": "Mid"}'] * 3, "judge_unparsed"),
        ([Refusal(text="가상 거절", category=None, usage=U)], "judge_unparsed"),
        ([Truncated(text='{"level":"Mi', usage=U)], "judge_cut_off"),
        ([ProviderError(status=400, retryable=False, message="가상")], "judge_failed"),
        ([ProviderTimeout(message="가상")], "judge_failed"),
    ],
)
def test_judge_failures_keep_their_kind_and_are_never_mid(
    replies: list[str | ProviderResponse], code: J.JudgeFailure
) -> None:
    mock = MockProvider("openai")
    for r in replies:
        if isinstance(r, str):
            mock.enqueue_text(r)
        else:
            mock.enqueue(r)
    reply = calls_with(mock).judge(judge_vars())
    assert reply == J.JudgeReply(answer=None, failure=code)
    assert J.judge(lambda _: reply, judge_vars(), LINES) == J.NotJudged(code=code)


def test_plan_and_rerank_provider_failures_are_search_failures() -> None:
    mock = MockProvider("openai").enqueue(ProviderError(status=400, retryable=False, message="가상"))
    with pytest.raises(ev.SearchFailed) as plan:
        calls_with(mock).plan("가상 주장")
    assert (plan.value.stage, plan.value.code) == ("plan", "provider_error")
    mock = MockProvider("openai").enqueue(ProviderError(status=400, retryable=False, message="가상"))
    with pytest.raises(ev.SearchFailed) as rerank:
        calls_with(mock).rerank("가상 주장", "[P1] 가상")
    assert rerank.value.stage == "rerank"


def test_embedding_failure_is_a_search_failure() -> None:
    with pytest.raises(ev.SearchFailed) as got:
        calls_with(MockProvider("openai"), FailingEmbedding()).embed(["가상 글"])
    assert (got.value.stage, got.value.code) == ("embed", "provider_error")


def test_a_cut_off_or_misshaped_rerank_salvages_ids() -> None:
    mock = MockProvider("openai").enqueue(Truncated(text='{"order":["P3","[P1] 가상 글","P', usage=U))
    assert calls_with(mock).rerank("가상", "l") == ev.RerankReply(ids=("P3", "P1"), complete=False)
    mock = MockProvider("openai")
    for _ in range(3):
        mock.enqueue_text("[P5] 가상 · P7")
    assert calls_with(mock).rerank("가상", "l") == ev.RerankReply(ids=("P5", "P7"), complete=False)
    mock = MockProvider("openai").enqueue_text('{"order":["[P2] 가상 글","P4"]}')
    assert calls_with(mock).rerank("가상", "l") == ev.RerankReply(ids=("P2", "P4"), complete=True)
