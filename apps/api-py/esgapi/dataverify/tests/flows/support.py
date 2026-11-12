"""흐름 시험의 공용: 지은 입력, 정본 설정 + openai 자리의 모의 공급사(경로 standard-openai-41), 받은 요청을 적는 대역.

mock-synthetic 경로는 web_search 건당 요금이 없고 출력 상한이 4,000 이라 흐름의 요청(web_search·32,768)을 거절한다 —
greenwash tests/flows/test_bridge_temperature.py 처럼 저장소 정본 models.json 에 MockProvider("openai") 를 끼운다.
실제 공급사·네트워크·키 0. 흐름은 core.flows.run.run_flow 로 돈다(실행기가 부르는 길과 같은 입구).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowRun
from esgapi.core.llm.client import CallRequest, LlmClient, ToolCallRequest
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import DryRunReport, LlmResult, Tags, ToolExecutor, ToolLoopResult
from esgapi.dataverify.contracts import shapes
from esgapi.dataverify.contracts.digest_shapes import DIGEST_SHAPE, DIGEST_SHAPES
from esgapi.dataverify.engines.colab_156 import prompts
from esgapi.dataverify.flows import colab_156
from esgapi.dataverify.flows.binding_156 import DataverifyBinding
from esgapi.dataverify.flows.colab_156 import DataverifyAdapters, DataverifyInputs, StageCosts
from esgapi.dataverify.outputs.digest import digest
from esgapi.dataverify.tests.engines.colab_156.support import data
from esgapi.dataverify.tests.flows.settings_store import DefaultOnlyStore, FileModels

TAGS: Final = Tags(tenant="tenant-synthetic", module="dataverify")
COMPANY: Final = {
    "name": "가상기업",
    "sasbIndustry": "가상 산업분류",
    "materialTopics": ["가상 토픽 A", "가상 토픽 B"],
    "reportingYear": "2024",
}
COSTS: Final = StageCosts(plan=1.0, review=1.0, insight=1.0)


def received(environment: bool = True) -> dict[str, Any]:
    body: dict[str, Any] = data() if environment else {"사회": data()["환경"][:1]}
    return {"schemaVersion": "dataverify.input@1", "company": dict(COMPANY), "data": body}


def inputs(**changes: Any) -> DataverifyInputs:
    given: dict[str, Any] = {
        "received": received(),
        "tags": TAGS,
        "max_cost_usd": COSTS,
        "texts": prompts.DEFAULT_TEXTS,
        "temperature": colab_156.TEMPERATURE,
        **changes,
    }
    return DataverifyInputs(**given)


def binding() -> DataverifyBinding:
    """판 포트를 꽂은 끼움 — 어느 회사든 기본 판(DVA1 앞 시험이 그대로 돈다), 모델 원천은 정본 models.json."""
    return DataverifyBinding(settings=DefaultOnlyStore(), models=FileModels())


def real_client(mock: MockProvider, sink: MemorySink | None = None) -> LlmClient:
    return LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": mock},
        prompts=PackagePromptStore(),
        log=sink or MemorySink(),
    )


@dataclass
class Spy:
    """LlmClient 를 감싸 흐름이 넘긴 요청을 적는다(단계마다 max_cost_usd·max_steps·tools 를 시험이 단언 — critic B1)."""

    client: LlmClient
    tool_requests: list[ToolCallRequest] = field(default_factory=list[ToolCallRequest])
    call_requests: list[CallRequest[Any]] = field(default_factory=list[CallRequest[Any]])
    dry_runs: int = 0

    def call_tools(self, request: ToolCallRequest, execute: ToolExecutor) -> ToolLoopResult:
        self.tool_requests.append(request)
        return self.client.call_tools(request, execute)

    def dry_run_tools(self, request: ToolCallRequest) -> DryRunReport:
        self.dry_runs += 1
        return self.client.dry_run_tools(request)

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]:
        self.call_requests.append(request)
        return self.client.call(request)

    def dry_run[T](self, request: CallRequest[T]) -> DryRunReport:
        self.dry_runs += 1
        return self.client.dry_run(request)


def spy(mock: MockProvider) -> Spy:
    return Spy(real_client(mock))


def run(given: DataverifyInputs, llm: Spy) -> FlowRun:
    return run_flow(colab_156.FLOW, given, DataverifyAdapters(llm=llm))


def result(done: FlowRun) -> Mapping[str, Any]:
    """결과 dataverify.result@2(둘째 결과는 요약 dataverify.digest@1 — DV1g). 요약이 그 결과의 셈인지도 본다."""
    found, summary = done.output.results
    assert (found["schemaVersion"], summary["schemaVersion"]) == ("dataverify.result@2", "dataverify.digest@1")
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(found, strict=True)  # 요약이 결과에 칸을 더하지 않는다
    DIGEST_SHAPES[DIGEST_SHAPE].validate_python(summary, strict=True)
    assert summary == digest(found)
    return found


# ── 실행 옵션(dataverify.options@1 — 밴드 DV1d) ─────────────────────────────────────────────────


def options(**changes: Any) -> dict[str, Any]:
    """지은 옵션 {"input": received()}. changes 는 맨 위 열쇠를 더하거나 바꾼다."""
    return {"input": received(), **changes}


def long_item(n: int) -> dict[str, Any]:
    """긴 꼴 지은 항목 하나(이름 20자·메모 40자·연도 다섯 — 옵션 크기 재기용, 값은 전부 지어낸 것)."""
    return {
        "ID": f"E-{n:04d}",
        "테마": "환경",
        "항목": f"가상긴항목이름{n:013d}",
        "대분류": "온실가스 배출량",
        "중분류": "직접 배출량",
        "소분류": "Scope 1",
        "입력 방식": "직접 입력",
        "단위": "tCO2eq",
        "values": {str(year): 1000 + n for year in range(2020, 2025)},
        "핵심데이터": "",
        "메모": f"가상메모{n:036d}",
    }


def with_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    """「환경」 항목 목록을 갈아 끼운 옵션."""
    given = received()
    given["data"] = {"환경": items}
    return {"input": given}


def octets(given: Mapping[str, Any]) -> int:
    """runs 가 옵션 상한에 견주는 크기(json.dumps ensure_ascii=False 의 UTF-8 바이트 — runs/service/actions/runs.py)."""
    return len(json.dumps(given, ensure_ascii=False).encode("utf-8"))


def sized(target: int) -> dict[str, Any]:
    """크기가 정확히 target 바이트인 옵션(긴 꼴 항목을 채우고 마지막 항목의 메모 글자 수로 맞춘다).
    긴 꼴 항목은 n 이 9000 아래면 바이트가 같아(자릿수 고정) 둘째부터는 항목 하나에 같은 바이트가 는다."""
    one, two = octets(with_items([long_item(1)])), octets(with_items([long_item(1), long_item(2)]))
    count = 1 + (target - one) // (two - one)
    items = [long_item(n) for n in range(1, count + 1)]
    short = target - octets(with_items(items))
    assert short >= 0
    items[-1]["메모"] += "a" * short
    given = with_items(items)
    assert octets(given) == target
    return given
