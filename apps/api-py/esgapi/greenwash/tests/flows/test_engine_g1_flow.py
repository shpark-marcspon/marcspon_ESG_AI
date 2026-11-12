"""흐름 greenwash.engine@G1 조립(flows/engine_g1 — 밴드 GE1 T13~T18): 장벽 extract·index·candidates → 펼침 judge →
모음 gather 가 run_flow 로 끝까지 돌고 result@2 를 낸다. 구획 열쇠 결정적 · 구획 실패는 pass_to_gather · 같은
stableKey 합침 · 문장 → 블록 짝 · 전역 등록(GE1b ③ — 기본값 E0·끼움 있음) · 크기 · E0 후보 몫과 같은 후보.

공급사는 모두 지어낸 것: 대화는 요청의 꼴 이름(facets·rerank·judge)으로 답하는 모의 공급사(openai 자리), 탐지는 쪽
번호로 답하는 ChatPort, 임베딩은 글의 해시로 짓는 벡터. 문서·문장은 지어낸 글(실제 기업·보고서 0).
"""

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast, get_args

import pytest

from esgapi.core.documents.contract import ArtifactRef, ParserInfo
from esgapi.core.documents.view import DocArtifactView
from esgapi.core.flows.binding import BINDINGS, NoBinding, RunOptionsRejected
from esgapi.core.flows.registry import REGISTRY, FlowRegistry
from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowStepFailed, StepContext, StepOutput
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, InvokeOptions, ProviderRequest, ProviderResponse, Tags
from esgapi.core.tests.artifact_fakes import block, fake_document, section
from esgapi.greenwash.contracts import result2_shapes as r2
from esgapi.greenwash.engines.e0.checker import GreenwashingChecker, GWConfig
from esgapi.greenwash.engines.e0.ports import ChatReply, Message
from esgapi.greenwash.engines.g1 import claims as cl
from esgapi.greenwash.engines.g1 import evidence as ev
from esgapi.greenwash.engines.g1 import judge as jd
from esgapi.greenwash.engines.g1 import ranges as rg
from esgapi.greenwash.flows import engine_g1 as E
from esgapi.greenwash.flows import registration
from esgapi.greenwash.flows.binding_g1 import G1Binding

SHA = "a" * 64
TAGS = Tags(tenant="tenant-synthetic", module="greenwash")
BROKEN = "가상 고장 문장"

# 쪽마다 탐지가 돌려줄 문장(지어낸 글 — 환경 낱말이 들어 E0 거름을 지난다)
PAGE_SENTENCES: dict[int, list[str]] = {
    n: [f"가상회사는 {n}번 사업장의 온실가스 배출량을 전년보다 {10 + k}% 줄였습니다." for k in range(3)]
    for n in (1, 2, 3, 4)
}


def page_blocks(n: int) -> list[dict[str, Any]]:
    """쪽 n: 머리띠(머리) · 문장 셋 각각 한 블록 · 긴 설명 블록 하나."""
    blocks = [block(f"p{n}-h", "머리띠 글", page=n, order=0, region="header", section_id="s1")]
    for k, s in enumerate(PAGE_SENTENCES[n]):
        blocks.append(block(f"p{n}-b{k + 1}", s, page=n, order=k + 1, section_id="s1"))
    detail = f"가상회사의 {n}번 사업장은 재생에너지 설비를 들여 전력 사용량을 점검하는 체계를 두고 있습니다. " * 3
    blocks.append(block(f"p{n}-b9", detail, page=n, order=9, section_id="s1"))
    return blocks


def document(*, extra: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
    blocks = [b for n in (1, 2, 3, 4) for b in page_blocks(n)] + list(extra)
    return fake_document(
        SHA, page_count=4, blocks=blocks, sections=[section("s1", "가상 환경 경영", page_start=1, page_end=4)]
    )


def inputs(**parts: tuple[int, ...]) -> E.G1Inputs:
    given = {"ceo": (1,), "company": (2, 3), "climate": (3, 4)} | parts
    return E.G1Inputs(parts=given)


class JsonDocument:
    """문서 포트(E.G1Document)의 가짜: 지어낸 산출물 JSON 하나를 판 2 산출물로 내준다(GE1b ② — DB 0). ensure 를 센다.
    chart_labels 는 뷰에 그대로 싣는다(GE1c ④ — 몸 포트가 charts=True: None = 칸 없음, 지어낸 라벨, UNAVAILABLE)."""

    def __init__(self, doc: Mapping[str, Any] | None = None, *, artifact_id: int = 1, chart_labels: Any = None) -> None:
        self.doc = dict(doc if doc is not None else document())
        self.artifact_id = artifact_id
        self.chart_labels = chart_labels
        self.ensured: int = 0

    def ensure(self) -> Any:
        self.ensured += 1
        src = cast("Mapping[str, Any]", self.doc["source"])
        parser = cast("Mapping[str, Any]", self.doc["parser"])
        return ArtifactRef(
            id=self.artifact_id,
            source_sha256=str(src["sha256"]),
            parser=ParserInfo(name=str(parser["name"]), version=str(parser["version"]), layout=int(parser["layout"])),
            epoch=2,
            page_count=int(src["page_count"]),
            body_bytes=len(json.dumps(self.doc)),
            status="ready",
        )

    def view(self, ref: ArtifactRef) -> DocArtifactView:
        return DocArtifactView(artifact_id=ref.id, document=self.doc, char_places=None, chart_labels=self.chart_labels)

    def file_name(self) -> str:
        return str(cast("Mapping[str, Any]", self.doc["source"])["file_name"])


def view(doc: Mapping[str, Any] | None = None) -> DocArtifactView:
    fake = JsonDocument(doc)
    return fake.view(fake.ensure())


def extracted(doc: Mapping[str, Any] | None = None) -> StepOutput:
    """extract 단계 산출물(모음·구획이 읽는 source 칸)."""
    return E.extract(inputs(), adapters(doc=doc), {}, StepContext(resume=None))


class Detect:
    """E0 탐지 ChatPort: 쪽 번호로 그 쪽 문장을 JSON 으로 돌려준다(부른 쪽을 적는다)."""

    def __init__(self, extra: Mapping[int, list[str]] | None = None) -> None:
        self.pages: list[int] = []
        self.extra = dict(extra or {})

    def invoke(self, messages: Sequence[Message]) -> ChatReply:
        text = str(messages[-1].content)
        m = re.search(r"(\d+)페이지", text)
        page = int(m.group(1)) if m else 0
        self.pages.append(page)
        sentences = self.extra.get(page, []) + PAGE_SENTENCES.get(page, [])  # E0 탐지 상한 3 — 덧붙인 것을 앞에
        return ChatReply(content=json.dumps([{"sentence": s} for s in sentences], ensure_ascii=False))


class Answering(MockProvider):
    """요청의 꼴 이름으로 답하는 모의 공급사(openai 자리). 판정은 받은 근거의 첫 단락을 인용하고 level 을 고른다."""

    def __init__(self, level: str = "Mid") -> None:
        super().__init__("openai")
        self.level = level
        self.cite: str | None = None

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        self.calls.append(request)
        name = request.json_schema.name if request.json_schema else ""
        user = "".join(getattr(p, "text", "") for p in request.user)
        if name == "facets":
            body: dict[str, object] = {
                "facets": [{"name": "가상 배출 실적", "keywords": ["온실가스"], "likelihood": "high", "reason": "가상"}]
            }
        elif name == "rerank":
            body = {"order": re.findall(r"\[(P\d+)\]", user)}
        else:
            ids = re.findall(r"\[(P\d+) ·", user)
            body = {
                "criteria": [{"lineId": "keyword-ghg", "hit": True}],
                "level": self.level,
                "category": None,
                "reason": "가상 근거가 주장의 일부만 받친다.",
                "confirmed": ["가상 확인"],
                "missing": ["가상 빠짐"],
                "evidence": [self.cite] if self.cite else ids[:1],
            }
        return Completed(text=json.dumps(body, ensure_ascii=False), usage=SYNTHETIC_USAGE)


@dataclass
class HashEmbedding:
    """글의 sha256 으로 짓는 8차원 벡터. broken 이 든 글이면 RuntimeError(구획 실패 시험) — query_only 면 첫 부름(index
    단계의 단락 임베딩) 뒤에만."""

    broken: str | None = None
    query_only: bool = False
    texts: list[str] = field(default_factory=list[str])
    calls: int = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.texts += texts
        self.calls += 1
        if self.query_only and self.calls == 1:
            pass
        elif self.broken and any(self.broken in t for t in texts):
            raise RuntimeError("가상 임베딩 고장")
        return [[b / 255 for b in hashlib.sha256(t.encode()).digest()[:8]] for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def adapters(
    provider: MockProvider | None = None,
    *,
    detect: Detect | None = None,
    emb: HashEmbedding | None = None,
    doc: Mapping[str, Any] | None = None,
) -> E.G1Adapters:
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": provider or Answering()},
        prompts=PackagePromptStore(),
        log=MemorySink(),
    )
    return E.G1Adapters(
        client=client,
        embedding=emb or HashEmbedding(),
        detect=detect or Detect(),
        tags=TAGS,
        document=JsonDocument(doc),
    )


def result_of(run: Any) -> dict[str, Any]:
    (result,) = run.output.results
    return cast("dict[str, Any]", result)


# ── T13 끝까지 · 결정적 ──


def test_the_flow_runs_to_a_result2_and_every_candidate_is_an_item() -> None:
    run = run_flow(E.g1_flow(), inputs(), adapters())
    result = result_of(run)
    r2.check_result(result)
    assert run.steps.keys() == {"extract", "index", "candidates", "judge", "gather"}
    assert [f.name for f in run.steps["index"].files] == [E.VECTORS_FILE]
    items = [i for s in result["segments"] for i in s["items"]]
    assert len(items) == 12
    assert [len(s["items"]) for s in result["segments"]] == [8, 4]
    assert {i["status"] for i in items} == {"done"}
    assert {i["verdict"]["level"] for i in items} == {"Mid"}
    assert items[0]["target"]["blockIds"] == ["p1-b1"]
    assert items[0]["module"]["parts"] == ["ceo"]
    assert next(i["module"]["parts"] for i in items if i["target"]["page"] == 3) == ["company", "climate"]
    assert result["failures"] == {"segments": 0, "items": 0}


def test_evidence_ranges_read_back_to_the_passage_blocks() -> None:
    """R4: 모음이 지은 blockRanges 를 body 차례로 다시 읽으면 그 단락의 구성 블록이다."""
    result = result_of(run_flow(E.g1_flow(), inputs(), adapters()))
    built = E.built_of(view())
    order = rg.block_order(view())
    by_id = {p.id: p for p in built.passages}
    docs = [e for s in result["segments"] for i in s["items"] for e in i["evidence"] if e["kind"] == "document"]
    assert docs
    for e in docs:
        back = [b for a, z in e["blockRanges"] for b in rg.read(a, z, order)]
        assert back == sorted(dict.fromkeys(by_id[e["passageId"]].members), key=order.__getitem__)


def test_same_input_twice_gives_the_same_segment_keys_and_result() -> None:
    one = run_flow(E.g1_flow(), inputs(), adapters())
    two = run_flow(E.g1_flow(), inputs(), adapters())
    keys = [s["keySha256"] for s in cast("list[dict[str, Any]]", one.steps["judge"].data["segments"])]
    assert keys == [s["keySha256"] for s in cast("list[dict[str, Any]]", two.steps["judge"].data["segments"])]
    assert json.dumps(result_of(one), ensure_ascii=False) == json.dumps(result_of(two), ensure_ascii=False)
    spans = [s["key"]["span"] for s in result_of(one)["segments"]]
    assert spans == ["c1-8:p1-b1~p3-b2", "c9-12:p3-b3~p4-b3"]


def test_only_the_union_of_part_pages_is_scanned_once_each() -> None:
    detect = Detect()
    run_flow(E.g1_flow(), inputs(ceo=(1,), company=(1, 3), climate=()), adapters(detect=detect))
    assert detect.pages == [1, 3]


# ── T14 구획 실패 ──


def test_a_failing_segment_is_passed_to_gather_and_the_rest_stay() -> None:
    extra = {4: [f"{BROKEN} 온실가스 감축을 이어 가겠습니다."]}
    doc = document(extra=[block("p4-b8", extra[4][0], page=4, order=8, section_id="s1")])
    emb = HashEmbedding(broken=BROKEN, query_only=True)
    run = run_flow(E.g1_flow(), inputs(), adapters(detect=Detect(extra), emb=emb, doc=doc))
    result = result_of(run)
    assert [s["status"] for s in result["segments"]] == ["done", "failed"]
    failed = result["segments"][1]
    assert failed["items"] == [] and failed["unplaced"] == [] and failed["errorCode"]
    assert len(result["segments"][0]["items"]) == 8
    assert result["failures"] == {"segments": 1, "items": 0}


class BrokenDetect(Detect):
    """쪽 3 에서 탐지 공급사가 던진다."""

    def invoke(self, messages: Sequence[Message]) -> ChatReply:
        if "3페이지" in str(messages[-1].content):
            raise RuntimeError("가상 탐지 고장")
        return super().invoke(messages)


def test_a_detect_failure_fails_the_candidates_step_not_a_page() -> None:
    """검증 4 R1: 쪽 하나의 탐지 실패를 삼켜 후보를 조용히 잃지 않는다 — 단계 실패."""
    with pytest.raises(FlowStepFailed) as got:
        run_flow(E.g1_flow(), inputs(), adapters(detect=BrokenDetect()))
    assert got.value.step == "candidates"


def test_the_index_step_failing_fails_the_run_not_a_segment() -> None:
    with pytest.raises(FlowStepFailed) as got:
        run_flow(E.g1_flow(), inputs(), adapters(emb=HashEmbedding(broken="가상회사")))
    assert got.value.step == "index"


# ── T15 합침 · 짝 ──


def test_place_finds_one_block_two_neighbours_or_nothing() -> None:
    units = E.cl.pages_of(E.units_of(view()))[1]
    first, second = PAGE_SENTENCES[1][0], PAGE_SENTENCES[1][1]
    assert cl.place(first, units) == ("p1-b1",)
    assert cl.place(first.replace(" ", "  "), units) == ("p1-b1",)
    across = first[-12:] + " " + second[:10]
    assert cl.place(across, units) == ("p1-b1", "p1-b2")
    assert cl.place("문서 어디에도 없는 가상 문장입니다.", units) is None
    assert cl.place("머리띠 글", units) is None  # 머리(region header)는 짝 밖


def test_an_unplaced_candidate_goes_to_unplaced_not_items() -> None:
    missing = "문서에 없는 가상 온실가스 감축 문장입니다."
    run = run_flow(E.g1_flow(), inputs(), adapters(detect=Detect({1: [missing]})))
    result = result_of(run)
    unplaced = [u for s in result["segments"] for u in s["unplaced"]]
    assert unplaced == [{"text": missing, "page": 1, "errorCode": "quote_not_found"}]
    assert missing not in [i["target"]["text"] for s in result["segments"] for i in s["items"]]


def test_merge_keeps_the_first_of_a_stable_key_and_joins_parts() -> None:
    page = E.cl.pages_of(E.units_of(view()))[3]
    s = PAGE_SENTENCES[3][0]
    a = cl.make_candidate(SHA, s, page, ["company"])
    b = cl.make_candidate(SHA, s.replace(" ", "　"), page, ["climate"])
    c = cl.make_candidate(SHA, PAGE_SENTENCES[3][1], page, ["company"])
    merged = cl.merge([a, c, b])
    assert [m.sentence for m in merged] == [s, PAGE_SENTENCES[3][1]]
    assert merged[0].parts == ["company", "climate"]


def test_gather_drops_a_repeated_stable_key_across_segments() -> None:
    result = result_of(run_flow(E.g1_flow(), inputs(), adapters()))
    entries: list[dict[str, Any]] = []
    for seg in result["segments"]:
        entries.append(
            {"key": seg["key"], "keySha256": seg["keySha256"], "status": "done", "errorCode": None, "data": seg}
        )
    entries[1]["data"] = entries[1]["data"] | {"items": entries[1]["data"]["items"] + entries[0]["data"]["items"][:1]}
    carried = {"extract": extracted(), "judge": StepOutput(data={"segments": entries})}
    out = E.gather(inputs(), adapters(), carried, StepContext(resume=None))
    (gathered,) = cast("list[dict[str, Any]]", out.data["results"])
    assert len(gathered["segments"][1]["items"]) == 4
    assert [i["key"] for i in gathered["segments"][1]["items"]] == ["i1", "i2", "i3", "i4"]


# ── 항목 짓기(검사·실패·자르기) ──


def built_index() -> tuple[ev.Index, dict[str, int], dict[str, str]]:
    built = E.built_of(view())
    vecs = HashEmbedding().embed_documents([p.text for p in built.passages])
    import numpy as np

    return ev.Index(built, np.asarray(vecs, dtype=np.float32)), rg.block_order(view()), built.block_text


def judged(**over: Any) -> jd.Judged:
    base: dict[str, Any] = {
        "level": "Mid",
        "category": None,
        "reason": "가상 이유",
        "confirmed": ("가상",),
        "missing": (),
        "criteria_hit": ("keyword-ghg",),
        "cited": ("P1",),
    }
    return jd.Judged(**(base | over))


def item(got: ev.Outcome, j: jd.JudgeOutcome | None, sentence: str | None = None) -> dict[str, Any]:
    idx, order, text = built_index()
    page = E.cl.pages_of(E.units_of(view()))[1]
    c = cl.make_candidate(SHA, sentence or PAGE_SENTENCES[1][0], page, ["ceo"])
    return E.item_of(c, got, j, idx, order, text, c.parts)


FOUND = ev.Found(passage_ids=("P1", "P2"), chars=10, self_excluded=(), facets=(), pool=2, returned=2, warnings=())


@pytest.mark.parametrize(
    ("got", "j", "code"),
    [
        (ev.Failed(stage="embed", code="provider_error"), None, "evidence_search_failed"),
        (FOUND, jd.NotJudged(code="judge_unparsed"), "judge_unparsed"),
        (FOUND, jd.NotJudged(code="judge_cut_off"), "judge_cut_off"),
        (FOUND, jd.NotJudged(code="judge_failed"), "judge_failed"),
    ],
)
def test_search_and_judge_failures_are_failed_items_without_a_verdict(
    got: ev.Outcome, j: jd.JudgeOutcome | None, code: str
) -> None:
    out = item(got, j)
    assert (out["status"], out["errorCode"], out["verdict"]) == ("failed", code, None)
    assert out["checks"]["evidenceInPool"] == "skipped"


@pytest.mark.parametrize(
    ("j", "code", "check"),
    [
        (judged(cited=("P1", "P999")), "evidence_outside_pool", "evidenceInPool"),
        (judged(category="가상 갈래"), "category_unknown", "categoryInList"),
        (judged(level="Low"), "level_rule_broken", "levelRule"),
    ],
)
def test_a_broken_check_keeps_the_verdict_and_names_the_check(j: jd.Judged, code: str, check: str) -> None:
    out = item(FOUND, j)
    assert (out["status"], out["errorCode"]) == ("failed", code)
    assert out["verdict"] is not None
    assert out["checks"][check] == "fail"


def test_item_evidence_stays_inside_the_pool_even_when_the_judge_cites_outside() -> None:
    """검증 4 R2: 판정이 풀 밖(문서에는 있는) 단락을 인용해도 항목 근거는 풀 안 단락만."""
    out = item(FOUND, judged(cited=("P1", "P3")))
    assert out["errorCode"] == "evidence_outside_pool"
    docs = [e["passageId"] for e in out["evidence"] if e["kind"] == "document"]
    assert docs and set(docs) <= set(FOUND.passage_ids)


def test_a_declarative_low_passes_the_level_rule_and_the_quote_check_comes_first() -> None:
    out = item(FOUND, judged(level="Low"), "가상회사는 온실가스 감축을 추진할 계획입니다.")  # 문서에 없는 선언문
    assert (out["errorCode"], out["checks"]["quoteInBlock"], out["checks"]["levelRule"]) == (
        "quote_not_found",
        "fail",
        "pass",
    )


def test_not_risky_is_a_done_item_with_level_none() -> None:
    out = item(FOUND, judged(level="None", missing=()))
    assert (out["status"], out["verdict"]["level"]) == ("done", "None")


def test_long_answers_are_cut_and_named_in_truncated() -> None:
    j = judged(reason="가" * 600, confirmed=("나" * 200,) * 6, criteria_hit=tuple(f"l{i}" for i in range(20)))
    out = item(FOUND, j)
    assert set(out["checks"]["truncated"]) >= {"reason", "module.confirmed", "evidence", "criteriaLines"}
    assert len(out["reason"]) == r2.REASON_MAX
    assert len(out["evidence"]) == r2.EVIDENCE_MAX


# ── T15 전역 등록(GE1b ③ — 앞 판 T16 「전역 0」을 뒤집음) ──


def test_the_g1_flow_is_registered_globally_but_is_not_the_default() -> None:
    flow = REGISTRY.get(E.FLOW_ID)
    assert flow is registration.FLOWS[-1]
    assert flow.step_kinds == ("barrier", "barrier", "barrier", "fanout", "barrier")
    assert REGISTRY.default_of("greenwash").id == "greenwash.colab@E0"
    assert registration.DEFAULTS == {"greenwash": "greenwash.colab@E0"}
    binding = BINDINGS.get(E.FLOW_ID)
    assert isinstance(binding, G1Binding)
    assert not isinstance(binding, NoBinding)
    fresh = FlowRegistry()
    registration.register(fresh)
    assert [f.id for f in fresh.flows_of("greenwash")][-1] == E.FLOW_ID
    assert fresh.default_of("greenwash").id == "greenwash.colab@E0"


def test_the_global_g1_binding_refuses_to_start_while_the_switch_is_off() -> None:
    """기본 꺼짐(GREENWASH_G1_RUNS_ENABLED 없음 — 시험 설정) — 옳은 옵션도 스위치 글로 거절(permits 74 조건 3)."""
    binding = BINDINGS.get(E.FLOW_ID)
    assert isinstance(binding, G1Binding)
    assert binding.runs_enabled() is False
    with pytest.raises(RunOptionsRejected, match="아직 열려 있지 않아요"):
        binding.check_options({"parts": {"ceo": [1], "company": [], "climate": []}})


def test_a_fresh_registry_takes_the_g1_flow() -> None:
    fresh = FlowRegistry()
    flow = E.g1_flow()
    fresh.register(flow)
    assert fresh.get(E.FLOW_ID) is flow
    assert flow.step_kinds == ("barrier", "barrier", "barrier", "fanout", "barrier")


def test_unknown_or_filled_only_fields_are_refused() -> None:
    parts = {"ceo": [1], "company": [], "climate": []}
    assert E.inputs_from({"parts": parts}).parts["ceo"] == (1,)
    bads: list[dict[str, object]] = [
        {"parts": parts, "reportYear": 2025},
        {"parts": parts, "document": document()},  # GE1b ②: 문서는 입력이 아니라 포트
        {"parts": parts, "industry": "가상"},
        {"parts": parts, "variant": "financial"},
        {"parts": parts, "evidenceScope": "pages"},
        {"parts": {"ceo": [1]}},
        {"parts": {"ceo": [0], "company": [], "climate": []}},
        {"parts": {"ceo": [E.PAGE_MAX + 1], "company": [], "climate": []}},
        {"parts": {"ceo": [], "company": [], "climate": []}},
    ]
    for bad in bads:
        with pytest.raises(ValueError):
            E.inputs_from(bad)


# ── T17 크기(감독 답 ⓒ ③ — 꽉 찬 1,200 → 잘림 길로 예산 안 · 보통 크기 → 잘림 0 · 구획 512KiB) ──

FULL_ID = "b" * r2.ID_MAX


def full_item(n: int) -> dict[str, object]:
    """2-1 상한을 꽉 채운 항목(id 16자 · 근거 12 = 문서 근거, 범위 8 · 노트 4×150 · 기준 줄 15)."""
    ids = [f"{'b' * (r2.ID_MAX - 4)}{k:04d}" for k in range(2 * r2.EVIDENCE_RANGES_MAX)]
    ranges = [[ids[2 * k], ids[2 * k + 1]] for k in range(r2.EVIDENCE_RANGES_MAX)]
    doc_ev = {"kind": "document", "passageId": "P" * r2.ID_MAX, "blockRanges": ranges, "page": 300}
    return {
        "key": f"i{n}",
        "stableKey": hashlib.sha256(str(n).encode()).hexdigest()[:32],
        "status": "done",
        "errorCode": None,
        "target": {"kind": "sentence", "text": "가" * r2.TARGET_TEXT_MAX, "page": 300, "blockIds": [FULL_ID] * 2},
        "verdict": {"level": "High", "category": None},
        "reason": "나" * r2.REASON_MAX,
        "evidence": [doc_ev] * r2.EVIDENCE_MAX,
        "checks": {
            "quoteInBlock": "pass",
            "evidenceInPool": "pass",
            "categoryInList": "pass",
            "levelRule": "pass",
            "truncated": [t for t in get_args(r2.TruncatedField) if t != "budget"],
        },
        "module": {
            "confirmed": ["다" * r2.NOTE_LINE_MAX] * r2.NOTE_LINES_MAX,
            "missing": ["라" * r2.NOTE_LINE_MAX] * r2.NOTE_LINES_MAX,
            "criteriaLines": ["c" * r2.LINE_ID_MAX] * r2.CRITERIA_LINES_MAX,
            "parts": list(E.PARTS),
        },
    }


def usual_item(n: int) -> dict[str, object]:
    """보통 크기(네 권 실측 꼴: 대상 ~100자 · 이유 ~300자 · 노트 3×80 · 문서 근거 6 × 범위 3 · 블록 id 8자 · 기준 5)."""
    ranges = [[f"p{n % 300}-b{k}", f"p{n % 300}-b{k + 1}"] for k in range(0, 6, 2)]
    doc_ev = {"kind": "document", "passageId": f"P{n}", "blockRanges": ranges, "page": 12}
    item = full_item(n)
    replaced: dict[str, object] = {
        "target": {"kind": "sentence", "text": "가" * 100, "page": 12, "blockIds": ["p12-b3"]},
        "reason": "나" * 300,
        "evidence": [doc_ev] * 6 + [{"kind": "criteria", "lineId": "keyword-ghg"}] * 5,
        "checks": cast("dict[str, object]", item["checks"]) | {"truncated": []},
        "module": {
            "confirmed": ["다" * 80] * 3,
            "missing": ["라" * 80] * 3,
            "criteriaLines": ["keyword-ghg"] * 5,
            "parts": ["climate"],
        },
    }
    return item | replaced


def octets(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def judge_data(make: Any, *, fit: bool = True) -> list[dict[str, Any]]:
    """150 구획 × 8 항목의 펼침 단계 data(구획마다 judge_segment 와 같은 예산 몫 fit 을 지남)."""
    entries: list[dict[str, Any]] = []
    for s_ in range(E.MAX_SEGMENTS):
        items = [make(s_ * cl.SEGMENT_SIZE + k + 1) for k in range(cl.SEGMENT_SIZE)]
        if fit:
            items, _ = E.fit(items, E.SEGMENT_BUDGET_OCTETS, octets({"items": [], "unplaced": []}))
        key = {"kind": "claims", "span": f"c{s_ * 8 + 1}-{s_ * 8 + 8}", "documentSha256": SHA, "parserVersion": "0.1.0"}
        entries.append({"key": key, "keySha256": "0" * 64, "status": "done", "data": {"items": items, "unplaced": []}})
    return entries


def gathered(entries: list[dict[str, Any]]) -> dict[str, Any]:
    carried = {"extract": extracted(), "judge": StepOutput(data={"segments": entries})}
    out = E.gather(inputs(), adapters(), carried, StepContext(resume=None))
    (result,) = cast("list[dict[str, Any]]", out.data["results"])
    return result


def test_a_full_item_and_a_full_segment_fit_their_own_limits() -> None:
    from esgapi.core.flows.types import SEGMENT_DATA_MAX_OCTETS

    biggest = octets(full_item(1))
    print(f"꽉 찬 항목 {biggest} 바이트 · 문턱(8MiB ÷ 1,200) {8 * 1024 * 1024 // 1200}")
    seg = {"items": [full_item(k) for k in range(cl.SEGMENT_SIZE)], "unplaced": []}
    assert octets(seg) <= SEGMENT_DATA_MAX_OCTETS
    assert E.PAGE_MAX * (GWConfig().max_candidates_per_page + 1) <= E.MAX_SEGMENTS * cl.SEGMENT_SIZE
    assert E.RESULT_BODY_MAX_OCTETS == 8 * 1024 * 1024  # runs/models.py RUN_RESULT_BODY_MAX_OCTETS 사본


def test_1200_full_items_take_the_budget_path_and_stay_under_the_limits() -> None:
    from esgapi.core.flows.types import FANOUT_DATA_MAX_OCTETS

    entries = judge_data(full_item)
    assert octets({"segments": entries}) <= E.BUDGET_OCTETS < FANOUT_DATA_MAX_OCTETS
    result = gathered(entries)
    r2.check_result(result)
    assert octets(result) <= E.RESULT_BODY_MAX_OCTETS
    items = [i for s_ in result["segments"] for i in s_["items"]]
    assert len(items) == 1200
    trimmed = [i for i in items if "budget" in i["checks"]["truncated"]]
    assert result["budgetTrimmed"] == len(trimmed) > 0
    for i in trimmed:
        assert all(e["blockRanges"] == [] for e in i["evidence"] if e["kind"] == "document")
        assert i["module"]["confirmed"] == [] == i["module"]["missing"]
        assert i["reason"] and i["target"]["text"]


def test_the_budget_trim_drops_a_span_with_the_ranges() -> None:
    """검증 4 R4: 예산 잘림은 span 도 지운다(span 은 블록 하나의 범위 하나에만 붙는다)."""
    one = full_item(1)
    spanned = {"kind": "document", "passageId": "P1", "blockRanges": [["p1-b1", "p1-b1"]], "page": 1, "span": [0, 9]}
    one["evidence"] = [spanned]
    trimmed = E.trim_for_budget(one)
    ev0 = cast("list[dict[str, Any]]", trimmed["evidence"])[0]
    assert "span" not in ev0 and ev0["blockRanges"] == []
    entries = judge_data(full_item)[:1]
    entries[0]["data"]["items"][-1] = trimmed
    r2.check_result(gathered(entries))


def test_usual_sized_items_are_never_trimmed() -> None:
    entries = judge_data(usual_item)
    result = gathered(entries)
    assert result["budgetTrimmed"] == 0
    assert octets(result) <= E.BUDGET_OCTETS


def test_without_the_segment_fit_full_items_are_over_the_fanout_limit() -> None:
    """잘림 길이 없으면 넘는다는 셈(예산 길이 왜 있는지)."""
    from esgapi.core.flows.types import FANOUT_DATA_MAX_OCTETS

    assert octets({"segments": judge_data(full_item, fit=False)}) > FANOUT_DATA_MAX_OCTETS


def test_empty_ranges_need_the_budget_mark() -> None:
    result = gathered(judge_data(full_item)[:1])
    item = result["segments"][0]["items"][0]
    item["evidence"][0]["blockRanges"] = []
    with pytest.raises(r2.Result2Invalid, match="블록 범위가 비었다"):
        r2.check_result(result)
    result["budgetTrimmed"] += 1
    item["checks"]["truncated"].append("budget")
    r2.check_result(result)


def test_a_result_over_the_body_limit_is_a_named_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(E, "RESULT_BODY_MAX_OCTETS", 10_000)
    with pytest.raises(E.ResultTooLarge):
        gathered(judge_data(usual_item)[:3])


def test_more_segments_than_the_maximum_fail_the_judge_step() -> None:
    with pytest.raises(FlowStepFailed) as got:
        run_flow(E.g1_flow(max_segments=1), inputs(), adapters())
    assert got.value.step == "judge"
    assert E.g1_flow().fanouts["judge"].max_segments == E.MAX_SEGMENTS == 150


# ── T18 E0 후보 몫과 같음 ──


def test_page_candidates_are_the_e0_analyze_page_candidates() -> None:
    """E0 analyze_page 를 같은 쪽 글·같은 모의 탐지로 돌린 후보(근거·평가는 끼운 가짜) == page_candidates."""
    from langchain_core.documents import Document

    pages = E.cl.pages_of(E.units_of(view()))
    extra = {2: ["가상회사는 온실가스 감축을 추진할 계획입니다.", "가상회사는 재생에너지 확대를 추진할 계획입니다."]}
    for n in (1, 2, 3):
        docs = [Document(page_content=pages[k].text) for k in (1, 2, 3, 4)]
        e0 = GreenwashingChecker(docs=docs, vectorstore=None, llm=Detect(extra), cfg=GWConfig())
        e0.build_evidence = lambda s, allowed_pages: ("", [])  # type: ignore[method-assign]
        e0.eval_low_only = lambda s, ev_text, debug=False: {}  # type: ignore[method-assign]
        e0.eval_high_mid_or_nonrisk = lambda s, ev_text, debug=False: {"decision": "Mid"}  # type: ignore[method-assign]
        e0_rows, _ = e0.analyze_page(n, None)
        mine = GreenwashingChecker(docs=None, vectorstore=None, llm=Detect(extra), cfg=GWConfig())
        text = E.page_text_of(docs[n - 1], int(GWConfig().max_chars_page_text))
        got = E.page_candidates(mine, text, n)
        assert got == [r["sentence"] for r in e0_rows]
        if n == 2:  # 선언문 둘 가운데 Low 1 만(E0 쿼터)
            assert sum(s_ in got for s_ in extra[2]) == 1
