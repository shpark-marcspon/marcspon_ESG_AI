"""흐름 dataverify.colab@156(발주서 §3 S3~S11·S13). run_flow 로 돌리고, 모의 공급사에 짜 둔 답 열을 심는다.

기대값은 손으로 적었다: 모델에 돌려준 도구 결과 글(기본 구분자·한국어 그대로), 걸음 수, 갈래, 결과 칸. 모의의 사용량은
가상 값(입력 100·출력 20 토큰 — gpt-4.1 단가 입력 2.00·출력 8.00 USD/1M 이면 걸음 하나 0.00036 USD, models.json
2026-10-19 확인)이라 비용 상한을 손셈으로 맞출 수 있다.
"""

import io
import math
from typing import Any

import pytest
from openpyxl import load_workbook

from esgapi.core.flows.types import FlowInputError, FlowStepFailed
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import (
    FunctionTool,
    ProviderError,
    ProviderRequest,
    ToolOutput,
    UrlCitation,
    WebSearchTool,
)
from esgapi.dataverify.contracts import shapes
from esgapi.dataverify.flows import colab_156
from esgapi.dataverify.flows.colab_156 import StageCosts
from esgapi.dataverify.outputs import xlsx
from esgapi.dataverify.tests.flows.support import COMPANY, TAGS, inputs, received, result, run, spy

STEP_USD = 0.00036
"""가상 사용량(100·20 토큰)의 걸음 하나 비용 — 2.00×100/1e6 + 8.00×20/1e6."""
S1_2022 = '{"대분류": "온실가스 배출량", "중분류": "직접 배출량", "소분류": "Scope 1", "단위": "tCO2eq", "year": 2022}'
SUM_ARGS = (
    '{"total": ["온실가스 배출량", "총 배출량", "Scope 1+2", "tCO2eq"], '
    '"a": ["온실가스 배출량", "직접 배출량", "Scope 1", "tCO2eq"], '
    '"b": ["온실가스 배출량", "간접 배출량", "Scope 2", "tCO2eq"], "years": ["2022"]}'
)
SUM_TEXT = (
    '{"results": [{"year": "2022", "ok": true, "status": "OK", "diff": 0.0, '
    '"explanation": "Sum(1200.0 + 300.0) - Target(1500.0) = 0.000000 → within tolerance (0.0)."}]}'
)
SEARCH_TEXT = (
    '{"total": 1, "items": [{"대분류": "온실가스 배출량", "중분류": "간접 배출량", "소분류": "Scope 2", '
    '"단위": "tCO2eq", "values": {"2022": 300, "2023": " 12 ", "2024": "N/A"}, "메모": "", "핵심데이터": ""}], '
    '"limit": 200, "offset": 0}'
)
INSIGHT = """## 가상 인사이트

| 영역 | 지표 | 관찰 | 리스크 | 해석 |
|---|---|---|---|---|
| 환경 | 가상 지표 A | 가상 관찰 A | 가상 리스크 A | 가상 해석 A |
| 환경 | 가상 지표 B | 가상 관찰 B | 가상 리스크 B | 가상 해석 B |
"""
FUNCTION_NAMES = [
    "value_of_by_name",
    "sum_check",
    "sum_n_check",
    "ratio_check",
    "sum_check_by_name",
    "sum_n_check_by_names",
    "ratio_check_by_name",
    "search_items",
]
CITATIONS = (
    UrlCitation(url="https://example.com/synthetic-a", title="가상 출처 A", start_index=0, end_index=1),
    UrlCitation(url="https://example.org/synthetic-b", title="가상 출처 B", start_index=2, end_index=3),
    UrlCitation(url="https://example.com/synthetic-a", title="가상 출처 A 다시", start_index=4, end_index=5),
)


def outputs_of(request: ProviderRequest) -> list[str]:
    return [turn.output for turn in request.turns if isinstance(turn, ToolOutput)]


def happy(mock: MockProvider) -> MockProvider:
    """Plan 두 걸음(값 조회 → 산식 둘), 검토 두 걸음(합계·검색 → 글), 인사이트 한 걸음(표 + 출처 셋 + 검색 1건)."""
    mock.enqueue_tool_calls([("value_of_by_name", S1_2022)])
    mock.enqueue_text("['가상 산식 1', '가상 산식 2']")
    mock.enqueue_tool_calls([("sum_check_by_name", SUM_ARGS), ("search_items", '{"소분류_contains": "Scope 2"}')])
    mock.enqueue_text("  가상 검토 리포트\n")
    mock.enqueue_text(INSIGHT, citations=CITATIONS, hosted_calls=1)
    return mock


# ── S3 끝까지 ──


def test_s3_end_to_end_requests_outputs_and_result() -> None:
    mock = happy(MockProvider("openai"))
    llm = spy(mock)
    done = run(inputs(), llm)
    out = result(done)
    assert mock.pending == 0
    assert len(mock.calls) == 5

    # 단계마다 첫 요청: 도구·코랩 첫 몸의 값·출력 상한
    for index, names in ((0, FUNCTION_NAMES), (2, FUNCTION_NAMES), (4, None)):
        sent = mock.calls[index]
        if names is None:
            assert sent.tools == (WebSearchTool(search_context_size="medium"),)
        else:
            assert [tool.name for tool in sent.tools if isinstance(tool, FunctionTool)] == names
            assert len(sent.tools) == 8
        assert sent.api_model_id == "gpt-4.1"
        assert sent.system_placement == "input_message"
        assert sent.temperature == 0.1
        assert sent.tool_choice == "auto"
        assert sent.parallel_tool_calls is False
        assert sent.max_output_tokens == 32768
        assert sent.max_hosted_calls is None
        assert sent.turns == ()

    # 둘째 걸음에 실린 도구 결과 글(손으로 적음)
    assert outputs_of(mock.calls[1]) == ['{"value": 1200.0}']
    assert outputs_of(mock.calls[3]) == [SUM_TEXT, SEARCH_TEXT]

    # 단계마다 흐름이 건 상한(critic B1)
    assert [(r.prompt, r.max_steps, r.max_cost_usd, len(r.tools)) for r in llm.tool_requests] == [
        ("dataverify/plan@1", 12, 1.0, 8),
        ("dataverify/review@1", 6, 1.0, 8),
        ("dataverify/insight@1", 12, 1.0, 1),
    ]

    assert out["schemaVersion"] == "dataverify.result@2"
    assert out["company"] == COMPANY
    assert out["scope"] == {"themes": ["환경"], "itemCount": 12, "keyItemCount": 4, "years": ["2022", "2023", "2024"]}
    assert out["settings"] == {
        "model": "gpt-4.1",
        "tolerance": "0.0",
        "temperature": "0.1",
        "maxSteps": {"plan": 12, "review": 6, "insight": 12},
        "promptIds": {"plan": "dataverify/plan@1", "review": "dataverify/review@1", "insight": "dataverify/insight@1"},
    }
    assert out["plan"] == {
        "status": "done",
        "partial": False,
        "formulas": ["가상 산식 1", "가상 산식 2"],
        "raw": "['가상 산식 1', '가상 산식 2']",
        "failure": None,
    }
    review = out["review"]
    assert (review["status"], review["partial"], review["report"], review["failure"]) == (
        "done",
        False,
        "가상 검토 리포트",
        None,
    )
    assert [(check["seq"], check["tool"], check["kind"]) for check in review["checks"]] == [
        (1, "sum_check_by_name", "check"),
        (2, "search_items", "search"),
    ]
    assert review["checks"][0]["years"] == [
        {
            "year": "2022",
            "ok": True,
            "status": "OK",
            "diff": "0.0",
            "note": None,
            "explanation": "Sum(1200.0 + 300.0) - Target(1500.0) = 0.000000 → within tolerance (0.0).",
        }
    ]
    assert review["checks"][1] == {
        "seq": 2,
        "tool": "search_items",
        "kind": "search",
        "filter": {"소분류_contains": "Scope 2"},
        "total": 1,
        "limit": 200,
        "offset": 0,
        "returned": 1,
    }
    insight = out["insight"]
    assert (insight["status"], insight["partial"], insight["report"], insight["rowsParsed"]) == (
        "done",
        False,
        INSIGHT.strip(),
        "parsed",
    )
    assert insight["rows"] == [
        {
            "area": "환경",
            "indicator": f"가상 지표 {x}",
            "observation": f"가상 관찰 {x}",
            "risk": f"가상 리스크 {x}",
            "interpretation": f"가상 해석 {x}",
        }
        for x in "AB"
    ]
    assert insight["sources"] == [
        {"title": "가상 출처 A", "url": "https://example.com/synthetic-a"},
        {"title": "가상 출처 B", "url": "https://example.org/synthetic-b"},
    ]
    assert out["warnings"] == []
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(out, strict=True)

    (report,) = done.output.files
    assert (report.name, report.media_type) == ("dataverify-report.xlsx", xlsx.MEDIA_TYPE)
    book = load_workbook(io.BytesIO(report.content))
    assert book.sheetnames == list(xlsx.SHEETS)
    assert set(done.steps) == {"load", "plan", "review", "insight", "report"}


def test_s3_plan_partial_is_done_with_partial_true_and_review_runs() -> None:
    """처분 ⑨: Plan 이 걸음을 다해도 글이 읽히면 done·partial true 이고 검토로 간다(코랩도 부분 글을 그대로 읽는다)."""
    mock = MockProvider("openai")
    for _ in range(11):
        mock.enqueue_tool_calls([("value_of_by_name", S1_2022)])
    mock.enqueue_tool_calls([("value_of_by_name", S1_2022)], text="['가상 산식']")
    mock.enqueue_text("가상 검토")
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    out = result(run(inputs(), spy(mock)))
    assert len(mock.calls) == 14
    assert out["plan"] == {
        "status": "done",
        "partial": True,
        "formulas": ["가상 산식"],
        "raw": "['가상 산식']",
        "failure": None,
    }
    assert out["review"]["status"] == "done"
    assert out["settings"]["maxSteps"] == {"plan": 12, "review": 3, "insight": 12}


# ── S4 부분 ──


def test_s4_review_reaches_max_steps_is_partial_and_pending_calls_are_not_checks() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_tool_calls([("value_of_by_name", S1_2022)])
    mock.enqueue_tool_calls([("search_items", '{"소분류_contains": "Scope 2"}')])
    mock.enqueue_tool_calls([("nope", "{}")], text="  가상 부분 리포트 ")
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    out = result(run(inputs(), spy(mock)))
    review = out["review"]
    assert len(mock.calls) == 1 + 3 + 1  # 검토 공급사 호출 = max_steps(1×3)
    assert (review["status"], review["partial"], review["report"]) == ("done", True, "가상 부분 리포트")
    assert [(c["seq"], c["tool"]) for c in review["checks"]] == [(1, "value_of_by_name"), (2, "search_items")]
    assert out["settings"]["maxSteps"]["review"] == 3


# ── S5 실패 ──


def test_s5_provider_error_on_the_second_review_step_keeps_the_first_checks() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_tool_calls([("value_of_by_name", S1_2022)])
    mock.enqueue(ProviderError(status=500, retryable=False, message="가상 공급사 오류 글"))
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    out = result(run(inputs(), spy(mock)))
    review = out["review"]
    assert review["status"] == "failed"
    assert review["partial"] is None
    assert review["report"] is None
    assert review["failure"] == {"kind": "provider_error", "budgetSource": None, "message": "provider_error status=500"}
    assert [(c["seq"], c["kind"], c["value"]) for c in review["checks"]] == [(1, "value", "1200.0")]
    assert out["insight"]["status"] == "done"


def test_s5_review_cost_limit_after_the_first_step() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_tool_calls([("value_of_by_name", S1_2022)])
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    llm = spy(mock)
    out = result(run(inputs(max_cost_usd=StageCosts(plan=1.0, review=STEP_USD, insight=1.0)), llm))
    assert out["review"]["failure"] == {
        "kind": "budget_exceeded",
        "budgetSource": "loop",
        "message": "budget_exceeded (loop)",
    }
    assert [c["seq"] for c in out["review"]["checks"]] == [1]
    assert len(mock.calls) == 3  # 검토 둘째 걸음은 부르지 않았다
    assert [r.max_cost_usd for r in llm.tool_requests] == [1.0, STEP_USD, 1.0]


def test_s5_plan_cost_limit_fails_the_plan_and_the_insight_still_runs() -> None:
    mock = MockProvider("openai")
    mock.enqueue_tool_calls([("value_of_by_name", S1_2022)])
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    llm = spy(mock)
    out = result(run(inputs(max_cost_usd=StageCosts(plan=STEP_USD, review=1.0, insight=1.0)), llm))
    assert out["plan"] == {
        "status": "failed",
        "partial": None,
        "formulas": [],
        "raw": None,
        "failure": {"kind": "budget_exceeded", "budgetSource": "loop", "message": "budget_exceeded (loop)"},
    }
    assert out["review"]["status"] == "not_run"
    assert out["insight"]["status"] == "done"
    assert len(mock.calls) == 2
    assert [(r.prompt, r.max_cost_usd) for r in llm.tool_requests] == [
        ("dataverify/plan@1", STEP_USD),
        ("dataverify/insight@1", 1.0),
    ]
    assert out["settings"]["maxSteps"] == {"plan": 12, "review": None, "insight": 12}
    assert out["settings"]["promptIds"]["review"] is None


def test_s5_insight_cost_limit_fails_the_insight() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_text("가상 검토")
    mock.enqueue_tool_calls([("web_search", "{}")], hosted_calls=1)
    llm = spy(mock)
    out = result(run(inputs(max_cost_usd=StageCosts(plan=1.0, review=1.0, insight=0.0103)), llm))
    # 걸음 하나 = 토큰 0.00036 + 검색 1건 0.01 = 0.01036 ≥ 0.0103 → 둘째 걸음을 막는다
    assert out["insight"] == {
        "status": "failed",
        "partial": None,
        "report": None,
        "rows": [],
        "rowsParsed": "none",
        "sources": [],
        "failure": {"kind": "budget_exceeded", "budgetSource": "loop", "message": "budget_exceeded (loop)"},
        "partialText": None,
    }
    assert len(mock.calls) == 3
    assert outputs_of(mock.calls[2]) == []
    assert llm.tool_requests[2].max_cost_usd == 0.0103


def test_s5_the_failure_message_carries_no_provider_text() -> None:
    mock = MockProvider("openai")
    mock.enqueue(ProviderError(status=None, retryable=False, message="가상 고객 데이터가 섞인 글"))
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    out = result(run(inputs(), spy(mock)))
    assert out["plan"]["failure"] == {
        "kind": "provider_error",
        "budgetSource": None,
        "message": "provider_error status=none",
    }
    assert "가상 고객" not in repr(out)


# ── S6 Plan 읽기 실패 ──


@pytest.mark.parametrize("answer", ["가상 산식 목록 아님", "{'가상': '산식'}", "['가상', 1]"])
def test_s6_plan_answer_that_is_not_a_list_of_strings(answer: str) -> None:
    mock = MockProvider("openai")
    mock.enqueue_text(f"  {answer}\n")
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    llm = spy(mock)
    out = result(run(inputs(), llm))
    assert out["plan"] == {
        "status": "failed",
        "partial": None,
        "formulas": [],
        "raw": answer,
        "failure": {
            "kind": "unparsable",
            "budgetSource": None,
            "message": "계산 Plan 의 답이 글자 원소의 python list 가 아니다",
        },
    }
    assert out["review"]["status"] == "not_run"
    assert [r.prompt for r in llm.tool_requests] == ["dataverify/plan@1", "dataverify/insight@1"]
    assert out["insight"]["status"] == "done"


# ── S7 걸음 천장 ──


def test_s7_zero_hints_is_one_review_step() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text("[]")
    mock.enqueue_text("가상 검토")
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    llm = spy(mock)
    out = result(run(inputs(), llm))
    assert llm.tool_requests[1].max_steps == 1
    assert out["settings"]["maxSteps"]["review"] == 1
    assert "최대 0 스텝" in llm.tool_requests[1].vars["system"]  # 프롬프트는 len×3 그대로
    assert out["warnings"] == []


def test_s7_thirteen_hints_cap_the_loop_at_36_with_a_warning() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text(repr([f"가상 산식 {n}" for n in range(13)]))
    mock.enqueue_text("가상 검토")
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    llm = spy(mock)
    out = result(run(inputs(), llm))
    assert llm.tool_requests[1].max_steps == 36
    assert "최대 39 스텝" in llm.tool_requests[1].vars["system"]
    assert out["settings"]["maxSteps"]["review"] == 36
    assert out["warnings"] == [
        {
            "code": "review_steps_capped",
            "message": "검토 걸음 39(산식 13×3)을 천장 36으로 줄였다(프롬프트의 걸음 글은 그대로)",
        }
    ]


# ── S8 입력 거절 ──


@pytest.mark.parametrize(
    "costs",
    [
        None,
        {"plan": 1.0, "review": 1.0, "insight": 1.0},
        StageCosts(plan=0.0, review=1.0, insight=1.0),
        StageCosts(plan=1.0, review=-1.0, insight=1.0),
        StageCosts(plan=1.0, review=1.0, insight=math.nan),
        StageCosts(plan=1.0, review=1.0, insight=math.inf),
        StageCosts(plan=True, review=1.0, insight=1.0),
        StageCosts(plan=1.0, review="1", insight=1.0),  # pyright: ignore[reportArgumentType]
    ],
)
def test_s8_bad_cost_limits_stop_at_load(costs: Any) -> None:
    mock = MockProvider("openai")
    with pytest.raises(FlowStepFailed) as raised:
        run(inputs(max_cost_usd=costs), spy(mock))
    assert raised.value.step == "load"
    assert isinstance(raised.value.__cause__, FlowInputError)
    assert mock.calls == []


def test_s8_a_wrong_input_shape_stops_at_load() -> None:
    mock = MockProvider("openai")
    bad = received()
    del bad["company"]["reportingYear"]
    with pytest.raises(FlowStepFailed) as raised:
        run(inputs(received=bad), spy(mock))
    assert raised.value.step == "load"
    assert isinstance(raised.value.__cause__, FlowInputError)
    assert mock.calls == []


# ── S9 web_search ──


def test_s9_web_search_off_calls_the_insight_once_without_tools() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_text("가상 검토")
    mock.enqueue_text(INSIGHT)
    llm = spy(mock)
    out = result(run(inputs(web_search=False), llm))
    assert [r.prompt for r in llm.tool_requests] == ["dataverify/plan@1", "dataverify/review@1"]
    (call,) = llm.call_requests
    assert isinstance(call, CallRequest)
    assert (call.prompt, call.temperature, call.max_output_tokens) == ("dataverify/insight@1", 0.1, 32768)
    assert mock.calls[2].tools == ()
    assert mock.calls[2].system_placement == "instructions"
    insight = out["insight"]
    assert (insight["status"], insight["partial"], insight["sources"], insight["rowsParsed"]) == (
        "done",
        False,
        [],
        "parsed",
    )
    assert out["settings"]["maxSteps"]["insight"] == 1
    assert out["warnings"] == [
        {"code": "web_search_disabled", "message": "web_search 를 끄고 인사이트를 도구 없이 한 번 불렀다(출처 없음)"}
    ]


def test_s9_web_search_on_without_a_search_warns_and_stays_done() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_text("가상 검토")
    mock.enqueue_text("가상 인사이트(표 없음)")
    out = result(run(inputs(), spy(mock)))
    assert (out["insight"]["status"], out["insight"]["rowsParsed"]) == ("done", "unparsed")
    assert out["warnings"] == [
        {
            "code": "insight_no_web_search",
            "message": "인사이트가 web_search 를 한 번도 실행하지 않았다(프롬프트는 1회 이상)",
        }
    ]


# ── S10 대상 테마 없음 ──


def test_s10_no_target_theme_runs_nothing() -> None:
    mock = MockProvider("openai")
    llm = spy(mock)
    out = result(run(inputs(received=received(environment=False)), llm))
    assert mock.calls == []
    assert llm.tool_requests == []
    assert [out[name]["status"] for name in ("plan", "review", "insight")] == ["not_run"] * 3
    assert out["scope"] == {"themes": [], "itemCount": 0, "keyItemCount": 0, "years": []}
    assert out["settings"] == {
        "model": None,
        "tolerance": "0.0",
        "temperature": None,
        "maxSteps": {"plan": None, "review": None, "insight": None},
        "promptIds": {"plan": None, "review": None, "insight": None},
    }
    assert out["warnings"] == [
        {"code": "no_target_theme", "message": "입력에 대상 테마(환경)가 없어 세 단계를 돌리지 않았다"}
    ]


# ── S11 도구 결과 상한·깨진 인자 ──


def test_s11_a_tool_output_over_the_limit_goes_back_as_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """상한을 작게(300자) 낮춰 search_items 의 결과(12 항목 — 수천 자)가 넘게 한다."""
    monkeypatch.setattr(colab_156, "TOOL_OUTPUT_MAX_CHARS", 300)
    mock = MockProvider("openai")
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_tool_calls([("search_items", "{}"), ("value_of_by_name", S1_2022)])
    mock.enqueue_text("가상 검토")
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    out = result(run(inputs(), spy(mock)))
    sent = outputs_of(mock.calls[2])
    assert sent[1] == '{"value": 1200.0}'
    assert sent[0].startswith('{"error": "tool output too large: ')
    assert sent[0].endswith(' chars > 300"}')
    first = out["review"]["checks"][0]
    assert (first["kind"], first["args"]) == ("error", {})
    assert first["message"].startswith("tool output too large: ")
    assert out["warnings"] == [
        {"code": "tool_output_too_large", "message": "review: 도구 결과 1건이 300자를 넘어 오류 글로 돌려줬다"}
    ]


def _one_item_input(memo: str) -> dict[str, Any]:
    item = {
        "ID": "E-001",
        "테마": "환경",
        "항목": "가상 항목",
        "대분류": "가상",
        "중분류": "가상",
        "소분류": "가상",
        "입력 방식": "직접 입력",
        "단위": "t",
        "values": {"2024": 1},
        "핵심데이터": "",
        "메모": memo,
    }
    return {"schemaVersion": "dataverify.input@1", "company": dict(COMPANY), "data": {"환경": [item]}}


# search_items 결과 글에서 메모 칸을 뺀 글자 수(손셈): 아래 글의 길이에 메모 글자 수를 더하면 결과 글자 수다.
SEARCH_FRAME = (
    '{"total": 1, "items": [{"대분류": "가상", "중분류": "가상", "소분류": "가상", "단위": "t", '
    '"values": {"2024": 1}, "메모": "", "핵심데이터": ""}], "limit": 200, "offset": 0}'
)


@pytest.mark.parametrize(("extra", "too_large"), [(0, False), (1, True)])
def test_s11_the_real_limit_is_100000_chars(extra: int, too_large: bool) -> None:
    """상한 상수(100,000)가 실제로 걸린다(검증 B1): 결과 글이 정확히 100,000 자면 그대로, 100,001 자면 오류 글."""
    assert colab_156.TOOL_OUTPUT_MAX_CHARS == 100_000
    memo = "가" * (100_000 - len(SEARCH_FRAME) + extra)
    mock = MockProvider("openai")
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_tool_calls([("search_items", "{}")])
    mock.enqueue_text("가상 검토")
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    out = result(run(inputs(received=_one_item_input(memo)), spy(mock)))
    (sent,) = outputs_of(mock.calls[2])
    if too_large:
        assert sent == '{"error": "tool output too large: 100001 chars > 100000"}'
        assert [w["code"] for w in out["warnings"]] == ["tool_output_too_large"]
    else:
        assert len(sent) == 100_000
        assert sent == SEARCH_FRAME.replace('"메모": ""', f'"메모": "{memo}"')
        assert out["warnings"] == []


def test_s11_unparsable_arguments_run_with_an_empty_object_and_warn() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_tool_calls([("value_of_by_name", '{"대분류": ')])
    mock.enqueue_text("가상 검토")
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    out = result(run(inputs(), spy(mock)))
    assert outputs_of(mock.calls[2]) == ['{"value": "N/A"}']
    check = out["review"]["checks"][0]
    assert (check["kind"], check["item"], check["na"]) == ("value", [None, None, None, None], True)
    assert out["warnings"] == [
        {
            "code": "tool_arguments_unparsable",
            "message": "review: 도구 호출 1건의 인자가 JSON 이 아니어서 빈 객체로 실행했다",
        }
    ]


def test_s11_non_finite_arguments_are_echoed_as_words_and_the_tool_runs_as_the_colab() -> None:
    """모델이 인자에 NaN·Infinity 를 주면(json.loads 가 받는다) 도구는 그 값으로 돌고 모델에 가는 글도 코랩 그대로다.
    검사 기록의 메아리 칸에만 낱말 글자로 싣는다(감독 처분) — 아니면 단계 산출물이 JSON 으로 왕복하지 않아 흐름이
    멈춘다."""
    mock = MockProvider("openai")
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_tool_calls(
        [("sum_check", '{"a": NaN, "b": 1, "c": Infinity}'), ("ratio_check", '{"d": 1, "e": 2, "f": -Infinity}')]
    )
    mock.enqueue_text("가상 검토")
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    out = result(run(inputs(), spy(mock)))
    assert outputs_of(mock.calls[2]) == [
        '{"ok": false, "status": "FAIL", "diff": NaN, '
        '"explanation": "Sum(nan + 1.0) - Target(inf) = nan → exceeds tolerance (0.0)."}',
        '{"ok": false, "status": "FAIL", "diff": Infinity, '
        '"explanation": "Ratio = 1.0/2.0 × 100 = 50.0000%, Expected ≈ -inf%, Diff = inf → '
        'exceeds tolerance (0.0 p.p.)."}',
    ]
    first, second = out["review"]["checks"]
    assert first["items"] == {"byName": None, "raw": {"a": "NaN", "b": 1, "c": "Infinity"}}
    explanation = "Sum(nan + 1.0) - Target(inf) = nan → exceeds tolerance (0.0)."
    assert first["years"] == [dict(year=None, ok=False, status="FAIL", diff="nan", note=None, explanation=explanation)]
    assert second["items"] == {"byName": None, "raw": {"d": 1, "e": 2, "f": "-Infinity"}}
    assert second["years"][0]["diff"] == "inf"
    assert colab_156.json_safe({"a": [math.nan, {"b": -math.inf}], "c": 1.5}) == {
        "a": ["NaN", {"b": "-Infinity"}],
        "c": 1.5,
    }


# ── S13 dry-run ──


def test_s13_estimate_calls_no_provider() -> None:
    mock = MockProvider("openai")
    llm = spy(mock)
    unknown = colab_156.estimate(inputs(), llm)
    known = colab_156.estimate(inputs(), llm, hints_count=4)
    assert mock.calls == []
    assert llm.tool_requests == []
    assert llm.dry_runs == 6
    assert {stage: unknown["perStage"][stage]["maxSteps"] for stage in ("plan", "review", "insight")} == {
        "plan": 12,
        "review": 36,
        "insight": 12,
    }
    assert known["perStage"]["review"]["maxSteps"] == 12
    assert unknown["perStage"]["review"]["maxProviderCalls"] == 108  # openai 고리: 걸음 36 × 3(LH1 Q10)
    assert unknown["unestimated"] == ["tool_outputs", "web_search_content", "web_search_calls"]
    for report in (unknown, known):
        per = report["perStage"]
        assert report["totalUpperBoundUsd"] == pytest.approx(sum(per[s]["loopUpperBoundUsd"] for s in per), abs=1e-8)
        assert all(per[s]["loopUpperBoundUsd"] > 0 for s in per)
    assert unknown["perStage"]["review"]["loopUpperBoundUsd"] > known["perStage"]["review"]["loopUpperBoundUsd"]


def test_s13_estimate_with_web_search_off_uses_one_plain_call() -> None:
    mock = MockProvider("openai")
    report = colab_156.estimate(inputs(web_search=False), spy(mock))
    assert mock.calls == []
    assert report["perStage"]["insight"]["maxSteps"] == 1
    assert report["perStage"]["insight"]["maxProviderCalls"] == 1
    assert report["unestimated"] == ["tool_outputs"]


def test_s13_estimate_rejects_a_bad_cost_limit_and_no_theme_is_zero() -> None:
    mock = MockProvider("openai")
    with pytest.raises(FlowInputError):
        colab_156.estimate(inputs(max_cost_usd=StageCosts(plan=0.0, review=1.0, insight=1.0)), spy(mock))
    empty = colab_156.estimate(inputs(received=received(environment=False)), spy(mock))
    assert empty["perStage"] == {"plan": None, "review": None, "insight": None}
    assert empty["totalUpperBoundUsd"] == 0.0
    assert mock.calls == []


def test_tags_reach_core() -> None:
    mock = happy(MockProvider("openai"))
    llm = spy(mock)
    run(inputs(), llm)
    assert {r.tags for r in llm.tool_requests} == {TAGS}
    assert {r.route for r in llm.tool_requests} == {"standard-openai-41"}
