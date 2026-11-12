"""흐름 시험의 공용: 지은 입력, 정본 설정 + openai 자리의 모의 공급사(경로 standard-openai-4o), 받은 요청을 적는 대역,
지어낸 모델 답과 손셈 비용.

mock-synthetic 경로는 web_search 건당 요금이 없어 흐름의 요청을 거절한다 — dataverify tests/flows/support.py 처럼 저장소
정본 models.json 에 MockProvider("openai") 를 끼운다. 실제 공급사·네트워크·키 0. 흐름은 core.flows.run.run_flow 로 돈다
(실행기가 부르는 길과 같은 입구). 입력·답은 전부 지어낸 「가상…」 값이다(실재 기업 0).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Final, cast

import esgapi.core.flows.types as flow_types
import esgapi.core.llm.client as core_client
import esgapi.core.llm.types as core_types
import esgapi.materiality.flows.iro_155 as iro_155
import esgapi.materiality.flows.part2_155 as part2_155
from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowRun
from esgapi.core.llm.client import LlmClient, ToolCallRequest
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import DryRunReport, Tags, ToolExecutor, ToolLoopResult, Usage
from esgapi.materiality.contracts import shapes, wire
from esgapi.materiality.flows import colab_155
from esgapi.materiality.flows.binding_155 import MaterialityBinding
from esgapi.materiality.flows.colab_155 import MaterialityAdapters, MaterialityInputs
from esgapi.materiality.outputs import final_xlsx
from esgapi.materiality.tests.flows.settings_store import DefaultOnlyStore, FileModels

EXAMPLES: Final = Path(__file__).resolve().parents[1] / "data" / "examples"
TAGS: Final = Tags(tenant="tenant-synthetic", module="materiality")
COST: Final = 5.0
"""실행 비용 상한(시험의 기본 — 닿지 않는 값)."""

USAGE: Final = Usage(input_tokens=10_000, output_tokens=2_000, cache_read_tokens=0, cache_write_tokens=0)
CALL_USD: Final = 0.045
"""USAGE 한 번의 토큰 비용 손셈(gpt-4o 2.5·10 / 1M): 10,000 × 2.5/1M + 2,000 × 10/1M = 0.025 + 0.02."""
SEARCH_USD: Final = 0.01
"""web_search 건당(Tools 표 $10.00 / 1k calls)."""


def received(*, topics: int = 3, industries: int = 2, sector: str = "non_financial") -> dict[str, Any]:
    """IR1a 의 지은 입력(tests/data/examples/input-sample.json)에서 토픽·산업 수와 sector 를 바꾼 것."""
    body = cast("dict[str, Any]", json.loads((EXAMPLES / "input-sample.json").read_text(encoding="utf-8")))
    names = ["하나", "둘", "셋"] + [f"{n}번" for n in range(4, topics + 1)]
    body["topics"] = [
        {"topic": f"가상토픽 {name}", "description": f"가상토픽 {name}의 설명 — 가상의 관리"} for name in names[:topics]
    ]
    body["industries"] = [
        {"standard": "SASB", "industryName": f"가상 산업 {n}", "description": f"가상 설명 {n} — 가상의 시설 운영"}
        for n in range(1, industries + 1)
    ]
    body["sector"] = sector
    return body


def topic_names(given: Mapping[str, Any]) -> list[str]:
    return [t["topic"] for t in given["topics"]]


PART1_CODE: Final[Mapping[str, Any]] = {
    "texts": colab_155.DEFAULT_TEXTS,
    "temperature": colab_155.CODE_RESEARCH.temperature,
    "max_output_tokens": colab_155.CODE_RESEARCH.max_output_tokens,
}
"""1부 입력의 IR4 칸 — 코드 값(기본 글·코드 모델 값. 처분 Q13 — 흐름 입력에 기본값이 없다)."""
PART2_CODE: Final[Mapping[str, Any]] = {
    "texts": colab_155.DEFAULT_TEXTS,
    "max_output_tokens": part2_155.CODE_ANALYSIS.max_output_tokens,
}
IRO_CODE: Final[Mapping[str, Any]] = {
    "texts": colab_155.DEFAULT_TEXTS,
    "research": colab_155.CODE_RESEARCH,
    "analysis": part2_155.CODE_ANALYSIS,
}


def inputs(**changes: Any) -> MaterialityInputs:
    given: dict[str, Any] = {"received": received(), "tags": TAGS, "max_cost_usd": COST, **PART1_CODE, **changes}
    return MaterialityInputs(**given)


def real_client(mock: MockProvider, sink: MemorySink | None = None) -> LlmClient:
    return LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": mock},
        prompts=PackagePromptStore(),
        log=sink or MemorySink(),
    )


@dataclass
class Spy:
    """LlmClient 를 감싸 흐름이 넘긴 요청을 적는다."""

    client: LlmClient
    tool_requests: list[ToolCallRequest] = field(default_factory=list[ToolCallRequest])
    dry_runs: list[ToolCallRequest] = field(default_factory=list[ToolCallRequest])

    def call_tools(self, request: ToolCallRequest, execute: ToolExecutor) -> ToolLoopResult:
        self.tool_requests.append(request)
        return self.client.call_tools(request, execute)

    def dry_run_tools(self, request: ToolCallRequest) -> DryRunReport:
        self.dry_runs.append(request)
        return self.client.dry_run_tools(request)


def spy(mock: MockProvider) -> Spy:
    return Spy(real_client(mock))


def run(given: MaterialityInputs, llm: Spy) -> FlowRun:
    return run_flow(colab_155.FLOW, given, MaterialityAdapters(llm=llm))


def result(done: FlowRun) -> Mapping[str, Any]:
    """흐름의 결과 본문 — 꼴로 고른다(iro 흐름은 곁에 digest@1 을 낸다, IR3c)."""
    (only,) = [r for r in done.output.results if r["schemaVersion"] != "materiality.digest@1"]
    return only


# ── 지어낸 모델 답 ─────────────────────────────────────────────────────────────────────────


def regulation_answer(topic: str) -> str:
    """셀 17 꼴의 답(results 가 지역 dict). 끝 utm 은 엔진이 지운다."""
    body = {
        "topic_name": topic,
        "results": {
            "KR": [{"title": f"{topic} 가상 규정", "primary_url": "https://example.com/r?utm_source=openai"}],
            "EU": [],
            "US": [],
        },
        "self_check": {"ok": True},
    }
    return "```json\n" + json.dumps(body, ensure_ascii=False) + "\n```"


def keywords_answer(topics: list[str]) -> str:
    """셀 20 꼴의 답(토픽마다 키워드 둘)."""
    body = {"topics": [{"topic": t, "keywords": [f"{t} 키워드 1", f"{t} 키워드 2"]} for t in topics]}
    return json.dumps(body, ensure_ascii=False)


def controversy_answer(topic: str) -> str:
    """셀 22 꼴의 답(results > items)."""
    body = {
        "topic_name": topic,
        "results": {"items": [{"title": f"{topic} 가상 사건", "url": "https://example.com/c"}]},
    }
    return json.dumps(body, ensure_ascii=False)


def script_all(mock: MockProvider, given: Mapping[str, Any], *, hosted: int = 1) -> None:
    """끝까지 다 끝나는 답을 코랩 차례로 심는다: 규제 토픽마다 → 키워드 한 번 → 컨트로버시 토픽마다."""
    names = topic_names(given)
    for name in names:
        mock.enqueue_text(regulation_answer(name), USAGE, hosted_calls=hosted)
    mock.enqueue_text(keywords_answer(names), USAGE, hosted_calls=hosted)
    for name in names:
        mock.enqueue_text(controversy_answer(name), USAGE, hosted_calls=hosted)


# ── 2부(밴드 IR2a): 씨앗 단계 → flows/part2_155 의 단계 넷을 잇는 시험용 흐름 ─────────────────────────────────
# 흐름 id·입력 꼴·등록은 IR2b 몫이라(발주서 처분 ⑭) 시험 안에만 짓는다. 씨앗은 1부 결과(@1 지은 예시)를 받아
# contracts/wire.part2_input_from_result 로 2부 입력을 짓는다. 경로 standard-openai-41(gpt-4.1)도 정본 models.json 에
# MockProvider("openai") 를 끼운다. 입력·답은 전부 지어낸 「가상…」.

CALL_USD2: Final = 0.036
"""USAGE 한 번의 토큰 비용 손셈(gpt-4.1 2.0·8.0 / 1M): 10,000 × 2.0/1M + 2,000 × 8.0/1M = 0.02 + 0.016."""


def received2(*, latest: bool = False, value_chain: bool = True) -> dict[str, Any]:
    """토픽 둘 · 서브토픽 셋(가상토픽 하나에 둘, 둘에 하나)의 입력."""
    body = cast("dict[str, Any]", json.loads((EXAMPLES / "input-sample.json").read_text(encoding="utf-8")))
    body["topics"] = body["topics"][:2]
    body["latestEventMode"] = latest
    body["subtopicsByTopic"] = {
        "가상토픽 하나": [
            {"name": "가상 서브 가", "description": "가상 서브 가의 설명"},
            {"name": "가상 서브 나", "description": "가상 서브 나의 설명"},
        ],
        "가상토픽 둘": [{"name": "가상 서브 다", "description": "가상 서브 다의 설명"}],
    }
    if not value_chain:
        body["valueChain"] = None
    return body


def part1_result(given: Mapping[str, Any]) -> dict[str, Any]:
    """1부 결과(@1 지은 예시)에서 입력 토픽만 남긴 것."""
    body = cast("dict[str, Any]", json.loads((EXAMPLES / "result-sample.json").read_text(encoding="utf-8")))
    names = topic_names(given)
    body["part1"]["topics"] = [t for t in body["part1"]["topics"] if t["topic"] in names]
    body["scope"]["topicCount"] = len(names)
    return body


@dataclass(frozen=True, kw_only=True)
class SeededInputs(part2_155.Part2Inputs):
    """시험용 흐름의 입력: 2부 입력 + 씨앗(입력 꼴 dict, 1부 결과, 1부 지출)."""

    received: Mapping[str, Any]
    part1: Mapping[str, Any]
    part1_spent: float = 0.0


def _seed_step(
    inputs: SeededInputs, adapters: part2_155.Part2Adapters, carried: flow_types.Carried, ctx: flow_types.StepContext
) -> flow_types.StepOutput:
    part2_input, warnings = wire.part2_input_from_result(inputs.received, inputs.part1)
    data: dict[str, object] = {
        "input": part2_input,
        "result": dict(inputs.part1),
        "warnings": warnings,
        "spentUsd": inputs.part1_spent,
    }
    return flow_types.StepOutput(data=data)


PART2_FLOW: Final = make_flow(
    module="materiality",
    id="materiality.part2-test@1",
    input_shape=shapes.INPUT_SHAPE,
    inputs=SeededInputs,
    adapters=part2_155.Part2Adapters,
    result_shapes=(shapes.RESULT_SHAPE_V2,),
    output_files=(final_xlsx.FILENAME,),
    steps=(
        flow_types.FlowStep(name=part2_155.SEED, run=_seed_step),
        *(flow_types.FlowStep[SeededInputs, part2_155.Part2Adapters](name=n, run=f) for n, f in part2_155.STEPS),
    ),
)


def inputs2(given: Mapping[str, Any] | None = None, **changes: Any) -> SeededInputs:
    received_now = dict(given) if given is not None else received2()
    base: dict[str, Any] = {
        "received": received_now,
        "part1": part1_result(received_now),
        "tags": TAGS,
        "max_cost_usd": COST,
        **PART2_CODE,
        **changes,
    }
    return SeededInputs(**base)


@dataclass
class Spy2:
    """LlmClient 를 감싸 2부가 넘긴 요청을 적는다(call·call_tools 둘 다)."""

    client: LlmClient
    requests: list[core_client.CallRequest[str] | ToolCallRequest] = field(
        default_factory=list[core_client.CallRequest[str] | ToolCallRequest]
    )
    dry_runs: list[core_client.CallRequest[str] | ToolCallRequest] = field(
        default_factory=list[core_client.CallRequest[str] | ToolCallRequest]
    )

    def call(self, request: core_client.CallRequest[str]) -> core_types.LlmResult[str]:
        self.requests.append(request)
        return self.client.call(request)

    def dry_run(self, request: core_client.CallRequest[str]) -> DryRunReport:
        self.dry_runs.append(request)
        return self.client.dry_run(request)

    def call_tools(self, request: ToolCallRequest, execute: ToolExecutor) -> ToolLoopResult:
        self.requests.append(request)
        return self.client.call_tools(request, execute)

    def dry_run_tools(self, request: ToolCallRequest) -> DryRunReport:
        self.dry_runs.append(request)
        return self.client.dry_run_tools(request)


def spy2(mock: MockProvider) -> Spy2:
    return Spy2(real_client(mock))


def run2(given: SeededInputs, llm: Spy2) -> FlowRun:
    return run_flow(PART2_FLOW, given, part2_155.Part2Adapters(llm=llm))


def context_of(n: str) -> dict[str, Any]:
    return {
        "controversies": [
            {"title": f"가상 사건 {n}", "summary": f"가상 사건 {n}의 요약", "url": f"https://example.com/c/{n}"}
        ],
        "regulations": [
            {"title": f"가상 규정 {n}", "summary": f"가상 규정 {n}의 요약", "url": f"https://example.com/r/{n}"}
        ],
    }


def impact_answer(subtopic: str) -> str:
    """셀 46 JSON 절 꼴의 답(부정 하나)."""
    body = {
        "topic": "가상",
        "subtopic": subtopic,
        "impacts": [
            {
                "impact_definition": f"{subtopic} 가상 환경 영향",
                "impact_type": "부정",
                "value_chain_activities": ["가상 활동"],
                "context": context_of(f"{subtopic} 영향"),
            }
        ],
    }
    return json.dumps(body, ensure_ascii=False)


def financial_definitions(subtopic: str) -> list[str]:
    return [f"{subtopic} 가상 비용 증가", f"{subtopic} 가상 매출 기회"]


def financial_answer(subtopic: str) -> str:
    """셀 50 JSON 꼴의 답(리스크 하나·기회 하나)."""
    first, second = financial_definitions(subtopic)
    body: dict[str, Any] = {
        "topic": "가상",
        "subtopic": subtopic,
        "impacts": [
            {
                "impact_definition": first,
                "impact_type": "리스크",
                "risk_type": "리스크-규제 및 법률",
                "value_chain_activities": ["가상 활동"],
                "context": context_of(f"{subtopic} 재무"),
            },
            {
                "impact_definition": second,
                "impact_type": "기회",
                "risk_type": None,
                "value_chain_activities": [],
                "context": {"controversies": [], "regulations": []},
            },
        ],
    }
    return json.dumps(body, ensure_ascii=False)


def pathway_answer(subtopic: str) -> str:
    """셀 55 JSON 절 꼴의 답(재무 행 둘에 i 1·2)."""
    body = {
        "pathways": [
            {
                "i": i,
                "impact_definition": definition,
                "impact_driver": f"가상 동인 {i}",
                "business_impact": f"가상 비즈니스 영향 {i}",
                "financial_impact": f"비용: 가상 재무 영향 {i}",
            }
            for i, definition in enumerate(financial_definitions(subtopic), 1)
        ]
    }
    return json.dumps(body, ensure_ascii=False)


SUBTOPICS2: Final = ("가상 서브 가", "가상 서브 나", "가상 서브 다")
"""received2 의 자리 차례(토픽 입력 차례 → 서브토픽 차례)."""


def script_part2(mock: MockProvider, subtopics: tuple[str, ...] = SUBTOPICS2, *, hosted: int = 0) -> None:
    """끝까지 다 끝나는 답을 코랩 차례로 심는다: 영향 자리마다 → 재무 자리마다 → Pathway 자리마다."""
    for name in subtopics:
        mock.enqueue_text(impact_answer(name), USAGE, hosted_calls=hosted)
    for name in subtopics:
        mock.enqueue_text(financial_answer(name), USAGE, hosted_calls=hosted)
    for name in subtopics:
        mock.enqueue_text(pathway_answer(name), USAGE, hosted_calls=hosted)


# ── 1부 → 2부 한 실행(밴드 IR2b): flows/iro_155 의 흐름 materiality.iro@155 ──────────────────────────────────────
# 「오늘」은 고정 날짜(실제 날짜와 다른 값 — 시계를 읽으면 빨개진다). 답의 항목 날짜는 지어낸 값이다.

TODAY: Final = date(2025, 6, 30)
"""흐름 입력 today 의 고정값."""
IN_RANGE: Final = "2025-03-02"
"""received2 의 dateRange(2025-01-01~오늘까지) 안의 날."""


def iro_inputs(given: Mapping[str, Any] | None = None, **changes: Any) -> iro_155.IroInputs:
    base: dict[str, Any] = {
        "received": dict(given) if given is not None else received2(),
        "tags": TAGS,
        "max_cost_usd": COST,
        "today": TODAY,
        **IRO_CODE,
        **changes,
    }
    return iro_155.IroInputs(**base)


def run_iro(given: iro_155.IroInputs, llm: Spy2) -> FlowRun:
    return run_flow(iro_155.FLOW, given, iro_155.IroAdapters(llm=llm))


def regulation_answer_dated(topic: str, *, publish: str | None = IN_RANGE, event: str | None = None) -> str:
    """셀 17 꼴의 답(KR 에 날짜를 단 항목 하나)."""
    item = {
        "title": f"{topic} 가상 규정",
        "event_date": event,
        "publish_date": publish,
        "primary_url": "https://example.com/r",
    }
    body = {"topic_name": topic, "results": {"KR": [item], "EU": [], "US": []}}
    return json.dumps(body, ensure_ascii=False)


def controversy_answer_dated(topic: str, days: tuple[str | None, ...] = (IN_RANGE,)) -> str:
    """셀 22 꼴의 답(results > items, 날짜마다 항목 하나 — 제목 「<토픽> 가상 사건 <n>」)."""
    items = [
        {"title": f"{topic} 가상 사건 {n}", "date": day, "url": f"https://example.com/c/{n}"}
        for n, day in enumerate(days, 1)
    ]
    return json.dumps({"topic_name": topic, "results": {"items": items}}, ensure_ascii=False)


def script_part1_dated(
    mock: MockProvider, given: Mapping[str, Any], *, controversy_days: tuple[str | None, ...] = (IN_RANGE,)
) -> None:
    """1부 답을 코랩 차례로(날짜가 든 항목): 규제 토픽마다 → 키워드 → 컨트로버시 토픽마다. web_search 1건씩."""
    names = topic_names(given)
    for name in names:
        mock.enqueue_text(regulation_answer_dated(name), USAGE, hosted_calls=1)
    mock.enqueue_text(keywords_answer(names), USAGE, hosted_calls=1)
    for name in names:
        mock.enqueue_text(controversy_answer_dated(name, controversy_days), USAGE, hosted_calls=1)


def script_iro(mock: MockProvider, given: Mapping[str, Any], **dated: Any) -> None:
    """한 실행의 답: 1부 다섯(토픽 둘) → 2부 아홉(서브토픽 셋)."""
    script_part1_dated(mock, given, **dated)
    script_part2(mock)


# ── 실행기 끼움(밴드 IR3a): flows/binding_155 의 옵션 materiality.options@1 ──────────────────────────────────────


def options(given: Mapping[str, Any] | None = None, **changes: Any) -> dict[str, Any]:
    """지은 옵션 {"input": received2()}. changes 는 맨 위 열쇠를 더하거나 바꾼다."""
    return {"input": dict(given) if given is not None else received2(), **changes}


def binding() -> MaterialityBinding:
    """판 포트를 꽂은 끼움 — 어느 회사든 기본 판(IR4 앞 시험이 그대로 돈다), 모델 원천은 정본 models.json."""
    return MaterialityBinding(settings=DefaultOnlyStore(), models=FileModels())


def octets(given: Mapping[str, Any]) -> int:
    """runs 가 옵션 상한에 견주는 크기(json.dumps ensure_ascii=False 의 UTF-8 바이트 — runs/service/actions/runs.py)."""
    return len(json.dumps(given, ensure_ascii=False).encode("utf-8"))


PAD_CHUNK: Final = 20_000
"""채움 산업 하나의 설명 글자 수 상한(엑셀 칸 하나의 32,767자 아래)."""


def sized(target: int) -> dict[str, Any]:
    """크기가 정확히 target 바이트인 옵션: received2 의 토픽·서브토픽은 그대로 두고 지은 채움 산업(설명 'a' 글)을 더해
    맞춘다(토픽이 그대로라 script_iro 의 대본으로 끝까지 돈다)."""
    given = options()
    industries: list[dict[str, str]] = given["input"]["industries"]
    n = 0
    while True:
        n += 1
        industries.append({"standard": "SASB", "industryName": f"가상 채움 산업 {n:03d}", "description": ""})
        short = target - octets(given)
        assert short >= 0, "target 이 기본 옵션보다 작다"
        industries[-1]["description"] = "a" * min(short, PAD_CHUNK)
        if short <= PAD_CHUNK:
            break
    assert octets(given) == target
    return given


def colab_like(*, topics: int, subtopics: int, description: int, value_chain: int) -> dict[str, Any]:
    """옵션 크기를 재는 지은 입력(★E): 토픽 topics 개, 서브토픽 subtopics 개(토픽 차례로 돌려 단다), 토픽·서브토픽·산업
    설명은 한글 description 자, 가치사슬 value_chain 줄. 값은 전부 지어낸 「가상…」."""
    body = received(topics=topics, industries=2)
    text = ("가상의 설명 글" * (description // 7 + 1))[:description]
    for topic in body["topics"]:
        topic["description"] = text
    for industry in body["industries"]:
        industry["description"] = text
    names = topic_names(body)
    by_topic: dict[str, list[dict[str, str]]] = {}
    for n in range(subtopics):
        by_topic.setdefault(names[n % len(names)], []).append({"name": f"가상 서브토픽 {n + 1}", "description": text})
    body["subtopicsByTopic"] = by_topic
    body["valueChain"] = [
        {
            "business_unit": f"가상 사업부 {n}",
            "business_unit_description": f"가상 사업부 {n}의 설명 — 가상의 제품을 만든다",
            "value_chain_stage": "운영",
            "stakeholder": "가상 이해관계자",
            "business_activity": f"가상 활동 {n}",
        }
        for n in range(1, value_chain + 1)
    ]
    shapes.check_input(body)
    return {"input": body}


def reordered2() -> dict[str, Any]:
    """received2 와 값은 같고 열쇠 차례만 꼴과 다른 입력: 맨 위 topics 가 먼저, 토픽·산업·가치사슬 행은 열쇠를 거꾸로.
    산업·가치사슬은 2부 프롬프트에 파이썬 repr 로 실려(engines/colab_155/part2_prompts) 열쇠 차례가 요청 글에 닿는다."""
    given = received2()
    body: dict[str, Any] = {"topics": given["topics"], **{k: v for k, v in given.items() if k != "topics"}}
    for name in ("topics", "industries", "valueChain"):
        body[name] = [dict(reversed(list(row.items()))) for row in given[name]]
    return body
