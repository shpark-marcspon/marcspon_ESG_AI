"""흐름이 입력의 글 여섯·temperature 로 부르는가(밴드 DVA1 §3-2). run_flow 로 돌리고 모의 공급사가 받은 요청을 본다.

흐름 층 표지: `DataverifyInputs(texts=표지 판)` 으로 돌리면 공급사 요청의 system·user 에 그 칸의 표지가 실린다 — 단계
함수가 `texts=` 를 빠뜨리면 기본 글이 나가 빨개진다. 기본 바이트는 §4-6 지문(texts_digest.py)이 본다.
"""

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from esgapi.core.llm.client import CallRequest, ToolCallRequest
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import DryRunReport, ProviderRequest
from esgapi.dataverify.engines.colab_156 import prompts
from esgapi.dataverify.flows import colab_156
from esgapi.dataverify.flows.colab_156 import DataverifyInputs
from esgapi.dataverify.tests.flows.support import COSTS, TAGS, Spy, inputs, real_client, received, result, run, spy

FIELDS = [one.name for one in dataclasses.fields(prompts.PromptTexts)]


def marker(name: str) -> str:
    return f"⟦DVA1-{name}⟧"


def marked() -> prompts.PromptTexts:
    """칸마다 제 표지를 앞에 붙인 글 여섯(자리는 그대로 — 기본 글과 같은 자리를 끼운다)."""
    return dataclasses.replace(
        prompts.DEFAULT_TEXTS, **{name: marker(name) + getattr(prompts.DEFAULT_TEXTS, name) for name in FIELDS}
    )


def system_user(request: ProviderRequest) -> tuple[str, str]:
    body: dict[str, Any] = request.to_json()
    return json.dumps(body["system"], ensure_ascii=False), json.dumps(body["user"], ensure_ascii=False)


def three_stages(mock: MockProvider) -> MockProvider:
    mock.enqueue_text("['가상 산식 1', '가상 산식 2']")
    mock.enqueue_text("가상 검토")
    mock.enqueue_text("가상 인사이트", hosted_calls=1)
    return mock


@pytest.mark.parametrize("missing", ["texts", "temperature"])
def test_texts_and_temperature_have_no_default(missing: str) -> None:
    given: dict[str, Any] = {
        "received": received(),
        "tags": TAGS,
        "max_cost_usd": COSTS,
        "texts": prompts.DEFAULT_TEXTS,
        "temperature": colab_156.TEMPERATURE,
    }
    del given[missing]
    with pytest.raises(TypeError):
        DataverifyInputs(**given)


@pytest.mark.parametrize("web_search", [True, False])
def test_the_temperature_reaches_every_stage_and_the_settings(web_search: bool) -> None:
    mock = three_stages(MockProvider("openai"))
    llm = spy(mock)
    out = result(run(inputs(temperature=0.7, web_search=web_search), llm))
    assert [request.temperature for request in mock.calls] == [0.7, 0.7, 0.7]
    assert [request.temperature for request in llm.tool_requests] == [0.7] * (3 if web_search else 2)
    assert [request.temperature for request in llm.call_requests] == ([] if web_search else [0.7])
    assert out["settings"]["temperature"] == "0.7"


def test_the_flow_sends_each_field_to_its_own_stage() -> None:
    mock = three_stages(MockProvider("openai"))
    run(inputs(texts=marked()), spy(mock))
    assert len(mock.calls) == 3
    for request, stage in zip(mock.calls, ("plan", "review", "insight"), strict=True):
        system, user = system_user(request)
        for name in FIELDS:
            own, part = name.split("_")
            assert (marker(name) in system) == (own == stage and part == "system"), (stage, name)
            assert (marker(name) in user) == (own == stage and part == "user"), (stage, name)
    # 자리는 끼워졌다(표지 판도 기본 글의 자리를 갖는다)
    _, plan_user = system_user(mock.calls[0])
    assert "[기업명]: 가상기업" in plan_user
    review_system, review_user = system_user(mock.calls[1])
    assert "최대 6 스텝" in review_system
    assert "- 가상 산식 1\\n- 가상 산식 2</힌트>" in review_user


def test_the_web_search_off_insight_sends_the_texts_too() -> None:
    mock = three_stages(MockProvider("openai"))
    run(inputs(texts=marked(), web_search=False), spy(mock))
    system, user = system_user(mock.calls[2])
    assert marker("insight_system") in system
    assert marker("insight_user") in user


@dataclass
class DrySpy(Spy):
    """dry-run 요청까지 적는 대역(estimate 가 넘긴 글·temperature 를 본다)."""

    dry_requests: list[ToolCallRequest | CallRequest[Any]] = field(
        default_factory=list[ToolCallRequest | CallRequest[Any]]
    )

    def dry_run_tools(self, request: ToolCallRequest) -> DryRunReport:
        self.dry_requests.append(request)
        return super().dry_run_tools(request)

    def dry_run[T](self, request: CallRequest[T]) -> DryRunReport:
        self.dry_requests.append(request)
        return super().dry_run(request)


@pytest.mark.parametrize("web_search", [True, False])
def test_the_estimate_uses_the_texts_and_the_temperature(web_search: bool) -> None:
    mock = MockProvider("openai")
    llm = DrySpy(real_client(mock))
    colab_156.estimate(inputs(texts=marked(), temperature=0.4, web_search=web_search), llm)
    assert mock.calls == []
    assert [(request.prompt, request.temperature) for request in llm.dry_requests] == [
        ("dataverify/plan@1", 0.4),
        ("dataverify/review@1", 0.4),
        ("dataverify/insight@1", 0.4),
    ]
    for request, stage in zip(llm.dry_requests, ("plan", "review", "insight"), strict=True):
        sent = json.dumps(request.vars, ensure_ascii=False)
        assert marker(f"{stage}_system") in sent
        assert marker(f"{stage}_user") in sent
