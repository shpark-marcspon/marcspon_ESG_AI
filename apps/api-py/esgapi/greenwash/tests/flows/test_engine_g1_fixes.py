"""흐름 greenwash.engine@G1 의 GE1b ① 고침(sid:MARC-ISSUE-642 1~7 · result@2 꼴 셋 — 밴드 GE1b T3~T7): 비용 상한의
이름(budget_exceeded)과 구획 안 멈춤 · 펼침 이어 받기 · 구획 keySha256 · 접두 · 처분 시험(4·6) · parts 꼴.

틀(문서·탐지·모의 공급사·임베딩)은 test_engine_g1_flow 의 것을 그대로 쓴다. 글은 지어낸 것(실제 기업·보고서 0).
"""

import json
from collections.abc import Callable
from typing import Any, cast, get_args

import pytest

from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import SegmentEnded, SegmentOutput, StepContext, StepOutput
from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Scope
from esgapi.core.tests.artifact_fakes import block, fake_document, section
from esgapi.greenwash.contracts import result2_shapes as r2
from esgapi.greenwash.contracts import shapes as r1
from esgapi.greenwash.engines.g1 import evidence as ev
from esgapi.greenwash.engines.g1 import judge as jd
from esgapi.greenwash.flows import engine_g1 as E
from esgapi.greenwash.tests.flows.test_engine_g1_flow import (
    FOUND,
    SHA,
    TAGS,
    Answering,
    Detect,
    HashEmbedding,
    JsonDocument,
    adapters,
    extracted,
    full_item,
    gathered,
    inputs,
    item,
    judge_data,
    octets,
    result_of,
    view,
)

TINY_USD = 0.000001
"""실행 상한 — 지어낸 SYNTHETIC_USAGE 한 부름의 비용보다 작다(첫 부름 뒤 누적이 넘는다)."""


def capped(provider: MockProvider, limit_usd: float = TINY_USD, sink: MemorySink | None = None) -> E.G1Adapters:
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": provider},
        prompts=PackagePromptStore(),
        log=sink or MemorySink(),
        limits=(BudgetLimit(Scope(), limit_usd),),
    )
    return E.G1Adapters(client=client, embedding=HashEmbedding(), detect=Detect(), tags=TAGS, document=JsonDocument())


def all_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for s in result["segments"] for i in s["items"]]


# ── T4 비용 상한(642-2) ──


def test_the_budget_is_named_and_the_rest_of_the_segment_is_not_called() -> None:
    """첫 부름(갈래) 뒤 누적이 상한을 넘는다 → 그 후보의 재순위에서 걸림 → 그 구획의 남은 일곱은 부르기 0, 다음
    구획 첫 후보는 부르기 전에 걸림. 항목은 전부 budget_exceeded(judge_failed·evidence_search_failed 로 접지 않음),
    구획은 done(고른 구획 다시로 다시 돈다)."""
    provider = Answering()
    sink = MemorySink()
    result = result_of(run_flow(E.g1_flow(), inputs(), capped(provider, sink=sink)))
    r2.check_result(result)
    items = all_items(result)
    assert len(items) == 12
    assert {(i["status"], i["errorCode"]) for i in items} == {("failed", "budget_exceeded")}
    assert [s["status"] for s in result["segments"]] == ["done", "done"]
    assert result["failures"] == {"segments": 0, "items": 12}
    assert len(provider.calls) == 1  # 공급사에 닿은 부름은 첫 갈래 하나뿐
    # 클라이언트에 온 부름 = 첫 후보의 갈래(성공)·재순위(상한) + 둘째 구획 첫 후보의 갈래(상한). 남은 열 후보는 0회
    assert [r.result_kind for r in sink.records] == ["success", "budget_exceeded", "budget_exceeded"]


def test_a_judge_over_the_budget_is_budget_exceeded_not_judge_failed() -> None:
    provider = Answering()
    calls = E.G1Calls(capped(provider).client, HashEmbedding(), tags=TAGS, vocab="가상 말 목록")
    calls.plan("가상 주장")  # 누적이 상한을 넘는다
    reply = calls.judge({"criteria": "", "categories": "", "claim": "가상", "page": "1", "evidence": ""})
    assert (reply.answer, reply.failure) == (None, "budget_exceeded")
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    ("got", "judged"),
    [
        (ev.Failed(stage="rerank", code="budget_exceeded"), None),
        (ev.Failed(stage="embed", code="budget_exceeded"), None),
        (FOUND, jd.NotJudged(code="budget_exceeded")),
    ],
)
def test_the_budget_name_survives_into_the_item(got: ev.Outcome, judged: jd.JudgeOutcome | None) -> None:
    out = item(got, judged)
    assert (out["status"], out["errorCode"], out["verdict"]) == ("failed", "budget_exceeded", None)


def test_budget_exceeded_is_one_item_error_code() -> None:
    assert "budget_exceeded" in get_args(r2.ItemErrorCode)
    assert E.BUDGET_CODE == "budget_exceeded"


# ── T5 펼침 이어 받기(642-3) ──


def test_a_resumed_judge_step_skips_the_done_segment_and_reads_the_carried_vectors() -> None:
    """start_at=judge · 앞 세 단계 산출물(Carried — index 의 벡터 파일 포함) · 끝난 구획 하나 → 그 구획은 부르기 0,
    남은 구획만 판정 · 단락 벡터는 다시 짓지 않음(vectors_of) · 결과 바이트가 처음부터 돈 것과 같다."""
    whole = run_flow(E.g1_flow(), inputs(), adapters())
    entries = cast("list[dict[str, Any]]", whole.steps["judge"].data["segments"])
    first = entries[0]
    done: dict[str, SegmentEnded] = {str(first["keySha256"]): SegmentOutput(data=dict(first["data"]))}
    carried = {name: whole.steps[name] for name in ("extract", "index", "candidates")}
    provider = Answering()
    emb = HashEmbedding()
    again = run_flow(
        E.g1_flow(),
        inputs(),
        E.G1Adapters(
            client=adapters(provider).client, embedding=emb, detect=Detect(), tags=TAGS, document=JsonDocument()
        ),
        start_at="judge",
        carried=carried,
        segments_done={"judge": done},
    )
    judged = [c for c in provider.calls if c.json_schema is not None and c.json_schema.name == "judge"]
    assert len(judged) == len(entries[1]["data"]["items"]) == 4  # 끝난 구획(8)은 0회
    passages = {p.text for p in E.built_of(view()).passages}
    assert passages.isdisjoint(emb.texts)  # 단락 벡터는 Carried 파일에서(다시 임베딩 0)
    assert json.dumps(result_of(again), ensure_ascii=False) == json.dumps(result_of(whole), ensure_ascii=False)


# ── T6 구획 keySha256 · 접두(D7) ──


def test_each_result_segment_carries_the_fanout_key_sha() -> None:
    run = run_flow(E.g1_flow(), inputs(), adapters())
    entries = cast("list[dict[str, Any]]", run.steps["judge"].data["segments"])
    result = result_of(run)
    assert [s["keySha256"] for s in result["segments"]] == [e["keySha256"] for e in entries]
    assert all(len(s["keySha256"]) == 64 for s in result["segments"])
    broken = json.loads(json.dumps(result))
    broken["segments"][0]["keySha256"] = "A" * 64
    with pytest.raises(ValueError):
        r2.check_result(broken)


def test_the_result2_components_are_prefixed_and_meet_no_result1_name() -> None:
    defs2 = set(cast("dict[str, Any]", r2.RESULT2.json_schema()["$defs"]))
    assert defs2 and all(name.startswith("GreenwashResult2") for name in defs2)
    assert r2.RESULT2.json_schema()["title"] == "GreenwashResult2"
    defs1 = {n for adapter in r1.RESULT_SHAPES.values() for n in adapter.json_schema()["$defs"]}
    assert defs1.isdisjoint(defs2)


# ── T7 처분 · 꼴(642-4 · 642-6 · 642-7) ──


CONTROL = "\u0001"
"""JSON 으로 \\u0001 여섯 바이트가 되는 제어 문자(642-4 의 최악 어림)."""


def control_item(n: int) -> dict[str, object]:
    one = full_item(n)
    target = cast("dict[str, object]", one["target"])
    return one | {"target": target | {"text": CONTROL * 300}, "reason": CONTROL * 500}


def test_an_item_that_cannot_shrink_is_kept_and_the_result_ends_as_a_named_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """642-4 처분(동작 0줄): 예산 잘림 뒤에도 몫을 넘는 항목은 버리지 않고 그대로 싣고(fit 이 돌려줌), 본문이 상한을
    넘으면 모음이 ResultTooLarge(result_too_large) — 조용히 잃는 길 0."""
    kept, used = E.fit([control_item(1)], budget=1)
    assert len(kept) == 1 and used > 1
    assert "budget" in cast("dict[str, list[str]]", kept[0]["checks"])["truncated"]
    entries = judge_data(control_item)[:2]
    monkeypatch.setattr(E, "RESULT_BODY_MAX_OCTETS", octets({"segments": entries}) // 4)
    with pytest.raises(E.ResultTooLarge) as got:
        gathered(entries)
    assert got.value.code == "result_too_large"


def test_each_judge_segment_rebuilds_the_passages(monkeypatch: pytest.MonkeyPatch) -> None:
    """642-6 처분(GE1c — CPU 만): 단락은 extract·index 와 구획마다 다시 짓는다(같은 문서면 같은 단락)."""
    real: Callable[..., Any] = E.build_passages
    seen: list[int] = []

    def counting(view: Any, chart_labels: Any = None) -> Any:
        built = real(view, chart_labels=chart_labels)
        seen.append(len(built.passages))
        return built

    monkeypatch.setattr(E, "build_passages", counting)
    run = run_flow(E.g1_flow(), inputs(), adapters())
    segments = len(cast("list[object]", run.steps["judge"].data["segments"]))
    assert len(seen) == 2 + segments == 4
    assert len(set(seen)) == 1


@pytest.mark.parametrize(
    "parts", [{"ceo": 1, "company": [], "climate": []}, {"ceo": "1", "company": [], "climate": []}]
)
def test_parts_that_are_not_page_lists_are_refused_as_value_errors(parts: dict[str, object]) -> None:
    """642-7: 파트 값이 목록이 아니면 TypeError 가 아니라 ValueError(끼움이 RunOptionsRejected 로 옮긴다)."""
    with pytest.raises(ValueError, match="페이지 번호 목록"):
        E.inputs_from({"parts": parts})


def test_gather_takes_the_key_sha_from_the_fanout_data() -> None:
    """keySha256 는 펼침 단계 data 의 값 그대로 — 모음이 짓지 않는다(없으면 KeyError, 조용한 빈 값 0)."""
    entries = judge_data(full_item)[:1]
    del entries[0]["keySha256"]
    with pytest.raises(KeyError):
        carried = {"extract": extracted(), "judge": StepOutput(data={"segments": entries})}
        E.gather(inputs(), adapters(), carried, StepContext(resume=None))


# ── 642-1 흐름 단(검증 1 권고 — 단락 0 문서를 run_flow 로) ──

ECHO = "가상회사는 모든 사업장의 온실가스 배출량을 전년보다 줄였습니다."


def test_a_document_with_no_passages_runs_to_done_without_embedding() -> None:
    """두 쪽에 같은 글만 있는 문서: 되풀이 뺌으로 단락 0 → index 임베딩 0회 · 근거 찾기 부르기 0(Empty) · 판정은 돎 ·
    구획 실패 0(BASE 는 index 의 (0,) 벡터로 구획 전부 step_error — 642-1 원 증상)."""
    blocks = [block(f"p{n}-b1", ECHO, page=n, order=1, section_id="s1") for n in (1, 2)]
    doc = fake_document(SHA, page_count=2, blocks=blocks, sections=[section("s1", "가상", page_start=1, page_end=2)])
    inp = E.G1Inputs(parts={"ceo": (1, 2), "company": (), "climate": ()})
    assert E.built_of(view(doc)).passages == ()
    emb = HashEmbedding()
    provider = Answering()
    run = run_flow(
        E.g1_flow(),
        inp,
        E.G1Adapters(
            client=adapters(provider).client,
            embedding=emb,
            detect=Detect({1: [ECHO], 2: [ECHO]}),
            tags=TAGS,
            document=JsonDocument(doc),
        ),
    )
    result = result_of(run)
    assert run.steps["index"].data == {"count": 0, "dim": 0}
    assert emb.calls == 0
    items = all_items(result)
    assert [i["target"]["page"] for i in items] == [1, 2]
    assert {(i["status"], i["evidence"] == [] or i["evidence"][0]["kind"] == "criteria") for i in items} == {
        ("done", True)
    }
    assert result["failures"] == {"segments": 0, "items": 0}
    names = [c.json_schema.name for c in provider.calls if c.json_schema is not None]
    assert "facets" not in names and "rerank" not in names and names.count("judge") == 2
