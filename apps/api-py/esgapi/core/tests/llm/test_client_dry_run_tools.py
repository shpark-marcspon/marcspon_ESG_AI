"""도구 호출 고리의 dry-run `LlmClient.dry_run_tools`(밴드 TL1 `MARC-TICK-180` 의 T14). 순수 층, 공급사 호출 0.

위끝 식(발주서 개정 1 B5): 걸음 k 위끝 = cost(in₁ + (k−1)·maxOut, maxOut), 고리 위끝 = Σ + N × max_hosted_calls × 건당.
값은 손으로 셈한 것을 박는다. 어림기는 글마다 500 토큰을 돌려주는 가짜라 in₁ = 프롬프트 500 + 도구 정의 500 = 1000.
모의 모델(mock-synthetic) 단가: 입력 1.0, 출력 2.0 USD / 1M 토큰. 건당 요금 0.01 은 가상(synthetic) 값이다.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from esgapi.core.llm.client import LlmClient, ToolCallRequest
from esgapi.core.llm.config import HostedToolPricing, LlmConfig
from esgapi.core.llm.prompts import FilePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.retry import RetryPolicy
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import FunctionTool, WebSearchTool
from esgapi.core.tests.llm_support import TAGS, config_with, synthetic_config

PARAMS: dict[str, object] = {"type": "object", "properties": {"x": {"type": "number"}}}
TOOLS = (FunctionTool(name="tool_a", description="가상 도구 a", parameters=PARAMS),)
REQUEST = ToolCallRequest(
    prompt="t/plain@1",
    vars={"question": "q"},
    route="mock",
    tags=TAGS,
    tools=TOOLS,
    max_steps=3,
    max_output_tokens=100,
)
HOSTED = HostedToolPricing(web_search_per_call=0.01)

# 손셈(마이크로 USD = 토큰 × 단가): 걸음 1 = 1000×1 + 100×2 = 1200, 걸음 2 = 1100×1 + 200 = 1300, 걸음 3 = 1400.
STEP_BOUNDS = [0.0012, 0.0013, 0.0014]
LOOP_BOUND = 0.0039
# web_search 를 싣고 max_hosted_calls=2: + 3 걸음 × 2 건 × 0.01 = 0.06.
LOOP_BOUND_WITH_SEARCH = 0.0639


class FixedEstimator:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def estimate(self, text: str) -> int:
        self.texts.append(text)
        return 500


class Rig:
    def __init__(
        self, prompt_root: Path, config: LlmConfig | None = None, retry: dict[str, RetryPolicy] | None = None
    ) -> None:
        self.mock = MockProvider()
        self.log = MemorySink()
        self.estimator = FixedEstimator()
        self.client = LlmClient(
            config=config or synthetic_config(),
            providers={"mock": self.mock},
            prompts=FilePromptStore(prompt_root),
            log=self.log,
            estimator=self.estimator,
            provider_retry=retry,
        )


def tool_loop(report_json: dict[str, object]) -> dict[str, Any]:
    return cast("dict[str, Any]", report_json["toolLoop"])


def test_step_bounds_add_the_replayed_outputs_of_earlier_steps(prompt_root: Path) -> None:
    rig = Rig(prompt_root)

    report = rig.client.dry_run_tools(REQUEST)

    assert rig.mock.calls == []
    assert rig.log.records == []
    body = cast("dict[str, Any]", report.request)
    assert body["tools"] == [{"type": "function", "name": "tool_a", "description": "가상 도구 a", "parameters": PARAMS}]
    # 입력 어림 = 프롬프트 + 어댑터가 싣는 도구 정의의 JSON 글자.
    assert rig.estimator.texts[1] == json.dumps(body["tools"], ensure_ascii=False, separators=(",", ":"))
    assert len(rig.estimator.texts) == 2
    assert report.estimate.input_tokens == 1000
    assert report.estimate.max_output_tokens == 100
    assert report.estimate.cost_upper_bound_usd == STEP_BOUNDS[0]
    loop = tool_loop(report.to_json())
    assert loop == {
        "maxSteps": 3,
        "stepUpperBoundsUsd": STEP_BOUNDS,
        "loopUpperBoundUsd": LOOP_BOUND,
        "maxProviderCalls": 3,
        "unestimated": ["tool_outputs"],
    }
    assert [warning.code for warning in report.warnings] == ["tool_outputs_unestimated"]
    assert report.fallback_models == ()


def test_web_search_with_a_per_response_cap_adds_steps_times_cap_times_price(prompt_root: Path) -> None:
    rig = Rig(prompt_root, config=config_with(hosted_tool_pricing=HOSTED))

    report = rig.client.dry_run_tools(replace(REQUEST, tools=(*TOOLS, WebSearchTool()), max_hosted_calls=2))

    loop = tool_loop(report.to_json())
    assert loop["stepUpperBoundsUsd"] == STEP_BOUNDS
    assert loop["loopUpperBoundUsd"] == LOOP_BOUND_WITH_SEARCH
    assert loop["unestimated"] == ["tool_outputs", "web_search_content"]
    assert [warning.code for warning in report.warnings] == ["tool_outputs_unestimated"]


def test_web_search_without_a_cap_leaves_the_call_count_out_and_says_so(prompt_root: Path) -> None:
    rig = Rig(prompt_root, config=config_with(hosted_tool_pricing=HOSTED))

    report = rig.client.dry_run_tools(replace(REQUEST, tools=(*TOOLS, WebSearchTool())))

    loop = tool_loop(report.to_json())
    assert loop["loopUpperBoundUsd"] == LOOP_BOUND
    assert loop["unestimated"] == ["tool_outputs", "web_search_content", "web_search_calls"]
    assert [warning.code for warning in report.warnings] == ["tool_outputs_unestimated", "hosted_calls_unbounded"]


def test_provider_calls_count_same_model_retries_per_step(prompt_root: Path) -> None:
    rig = Rig(prompt_root, retry={"mock": RetryPolicy(max_retries=2, base_delay_ms=0, max_delay_ms=0)})

    report = rig.client.dry_run_tools(REQUEST)

    # 기록 줄 기준: 3 걸음 × (1 + 2 재시도).
    assert tool_loop(report.to_json())["maxProviderCalls"] == 9
