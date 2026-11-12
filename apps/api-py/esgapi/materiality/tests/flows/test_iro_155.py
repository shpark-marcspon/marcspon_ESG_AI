"""1부 → 2부 한 실행(flows/iro_155.py, 밴드 IR2b — 발주서 §3 S3·S4·S5·S8·S10·S11·S12·S13·S14): 호출 수·차례, @2 하나,
part1 = 1부 단독 흐름의 part1, 엑셀 둘, 요청 바이트가 1부 단독·2부 시험 흐름과 같음, 기간 거르기는 2부 입력에만, 자동
서브토픽 경고는 한 번, 등록, 어림, 순수. 공급사는 모의만(실호출 0). 「오늘」은 고정(support.TODAY). 기대값은 손셈."""

import ast
import io
import json
import re
from pathlib import Path
from typing import Any, cast

import pytest
from openpyxl import load_workbook

from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowInputError
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.types import ProviderRequest, TextPart
from esgapi.materiality.contracts import shapes
from esgapi.materiality.contracts.digest_shapes import DIGEST_SHAPE, DIGEST_SHAPES
from esgapi.materiality.flows import colab_155, iro_155, part2_155, registration
from esgapi.materiality.outputs.digest import digest
from esgapi.materiality.tests.flows import support
from esgapi.materiality.tests.flows.support import CALL_USD, CALL_USD2, SEARCH_USD, SUBTOPICS2

TOPICS = ("가상토픽 하나", "가상토픽 둘")
"""received2 의 토픽(입력 차례)."""


def run_iro(given: dict[str, Any] | None = None, **dated: Any) -> tuple[MockProvider, Any]:
    received = given if given is not None else support.received2()
    mock = MockProvider("openai")
    support.script_iro(mock, received, **dated)
    done = support.run_iro(support.iro_inputs(received), support.spy2(mock))
    assert mock.pending == 0
    return mock, done


def run_part1_alone(received: dict[str, Any], **dated: Any) -> tuple[MockProvider, Any]:
    mock = MockProvider("openai")
    support.script_part1_dated(mock, received, **dated)
    done = run_flow(
        colab_155.FLOW,
        colab_155.MaterialityInputs(
            received=received, tags=support.TAGS, max_cost_usd=support.COST, **support.PART1_CODE
        ),
        colab_155.MaterialityAdapters(llm=support.spy2(mock)),
    )
    return mock, done


def run_part2_alone(received: dict[str, Any], part1: dict[str, Any]) -> MockProvider:
    mock = MockProvider("openai")
    support.script_part2(mock)
    support.run2(support.inputs2(received, part1=part1), support.spy2(mock))
    return mock


def body(request: ProviderRequest) -> bytes:
    """요청 몸 바이트(openai 공급사가 SDK 에 넘기는 kwargs 의 JSON)."""
    return json.dumps(OpenAIProvider().build_request(request), ensure_ascii=False, sort_keys=True).encode()


def user_text(request: ProviderRequest) -> str:
    (part,) = request.user
    assert isinstance(part, TextPart)
    return part.text


def calls(done: Any, *steps: str) -> list[dict[str, Any]]:
    return [c for step in steps for c in cast("list[dict[str, Any]]", done.steps[step].data["calls"])]


def sheet_text(content: bytes) -> str:
    book = load_workbook(io.BytesIO(content))
    return "\n".join(str(v) for ws in book.worksheets for row in ws.iter_rows(values_only=True) for v in row if v)


# ── S3 한 실행 ─────────────────────────────────────────────────────────────────────────────


def test_one_run_calls_part1_then_part2_and_returns_one_v2_result() -> None:
    mock, done = run_iro()
    assert len(mock.calls) == 14  # 1부 2 + 1 + 2, 2부 3 × 3
    assert [c["phase"] for c in calls(done, "regulation", "keywords", "controversy")] == [
        "regulation",
        "regulation",
        "keywords",
        "controversy",
        "controversy",
    ]
    assert [(c["phase"], c["subtopic"]) for c in calls(done, *part2_155.PHASES2)] == [
        (phase, name) for phase in part2_155.PHASES2 for name in SUBTOPICS2
    ]
    assert [r.api_model_id for r in mock.calls] == ["gpt-4o"] * 5 + ["gpt-4.1"] * 9
    result = support.result(done)
    assert result["schemaVersion"] == "materiality.result@2"
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE_V2].validate_python(result, strict=True)
    assert list(done.output.results) == [result, digest(result)]  # 곁에 요약 digest@1(IR3c)
    DIGEST_SHAPES[DIGEST_SHAPE].validate_python(done.output.results[1], strict=True)
    assert result["part2"]["status"] == "done"
    assert [t["topic"] for t in result["part2"]["topics"]] == list(TOPICS)
    assert result["warnings"] == []
    assert list(done.steps) == list(iro_155.FLOW.steps)


def test_part1_fields_are_the_part1_flow_result() -> None:
    received = support.received2()
    _, done = run_iro(received)
    _, alone = run_part1_alone(received)
    result = support.result(done)
    part1 = support.result(alone)
    assert result["part1"] == part1["part1"]
    assert result["scope"] == part1["scope"]
    assert {k: result["settings"][k] for k in part1["settings"]} == part1["settings"]
    assert result["company"] == part1["company"]


def test_two_files_part1_research_then_final_report() -> None:
    _, done = run_iro()
    first, final = done.output.files
    assert (first.name, final.name) == ("materiality-websearch.xlsx", "materiality-final-report.xlsx")
    assert first.content == done.steps["report"].files[0].content  # 1부 report 의 바이트 그대로
    book1 = load_workbook(io.BytesIO(first.content))
    assert book1.worksheets[0].title == "Shortlist"
    assert book1.worksheets[0]["B1"].value == "1-1. Short-list 선정"
    book2 = load_workbook(io.BytesIO(final.content))
    assert book2.worksheets[0].title == "1-1. Short-list 선정"
    assert book2.worksheets[0]["B1"].value == "1-1. Short-list 선정"


def test_call_costs_by_hand() -> None:
    _, done = run_iro()
    part1 = calls(done, "regulation", "keywords", "controversy")
    part2 = calls(done, *part2_155.PHASES2)
    assert [c["costUsd"] for c in part1] == [round(CALL_USD + SEARCH_USD, 6)] * 5  # 0.055
    assert [c["costUsd"] for c in part2] == [CALL_USD2] * 9  # 0.036
    assert done.steps[part2_155.SEED].data["spentUsd"] == pytest.approx(5 * 0.055)
    assert done.steps["pathway"].data["spentUsd"] == pytest.approx(5 * 0.055 + 9 * 0.036)  # 0.599


# ── S4 요청 바이트 ─────────────────────────────────────────────────────────────────────────


def test_requests_are_byte_identical_to_part1_alone_and_part2_test_flow() -> None:
    received = support.received2()
    mock, _ = run_iro(received)
    alone, part1_run = run_part1_alone(received)
    part1 = dict(support.result(part1_run))
    part2 = run_part2_alone(received, part1)
    assert [body(r) for r in mock.calls[:5]] == [body(r) for r in alone.calls]
    assert [body(r) for r in mock.calls[5:]] == [body(r) for r in part2.calls]
    assert len(part2.calls) == 9


# ── S5 기간은 2부 입력에만 ─────────────────────────────────────────────────────────────────


def test_out_of_range_items_leave_only_the_part2_input() -> None:
    days = (support.IN_RANGE, "2024-12-31")
    received = support.received2()
    mock, done = run_iro(received, controversy_days=days)
    result = support.result(done)
    out = "가상토픽 하나 가상 사건 2"
    part2_text = "\n".join(user_text(r) for r in mock.calls[5:])
    assert out not in part2_text
    assert "가상토픽 하나 가상 사건 1" in part2_text
    parsed = result["part1"]["topics"][0]["controversy"]["parsed"]
    assert [i["title"] for i in parsed["results"]["items"]] == ["가상토픽 하나 가상 사건 1", out]
    first, final = done.output.files
    assert out in sheet_text(first.content)
    shortlist = load_workbook(io.BytesIO(final.content)).worksheets[0]
    assert out not in "\n".join(str(v) for row in shortlist.iter_rows(values_only=True) for v in row if v)
    assert [(w["code"], w["topic"], w["phase"], w["message"]) for w in result["warnings"]] == [
        (
            "items_out_of_range",
            topic,
            "controversy",
            "컨트로버시 항목 1건 뺌(기간 2025-01-01~2025-06-30) — 2부 입력에서만, part1 은 그대로.",
        )
        for topic in TOPICS
    ]
    _, alone = run_part1_alone(received, controversy_days=days)
    assert result["part1"] == alone.output.results[0]["part1"]


def test_unreadable_item_dates_are_kept_with_a_warning() -> None:
    mock, done = run_iro(controversy_days=("2025-03",))
    result = support.result(done)
    assert "가상토픽 둘 가상 사건 1" in "\n".join(user_text(r) for r in mock.calls[5:])
    assert [(w["code"], w["topic"]) for w in result["warnings"]] == [
        ("item_date_unreadable", "가상토픽 하나"),
        ("item_date_unreadable", "가상토픽 둘"),
    ]


# ── S8 자동 서브토픽 · S10 서브토픽 이름 겹침 ─────────────────────────────────────────────────


def test_autofilled_subtopic_warning_appears_once_per_topic() -> None:
    received = support.received2()
    received["subtopicsByTopic"] = None
    mock = MockProvider("openai")
    support.script_part1_dated(mock, received)
    support.script_part2(mock, TOPICS)  # 지어 넣은 서브토픽 이름 = 토픽명
    done = support.run_iro(support.iro_inputs(received), support.spy2(mock))
    result = support.result(done)
    autofilled = [(w["topic"], w["phase"]) for w in result["warnings"] if w["code"] == "subtopic_autofilled"]
    assert autofilled == [("가상토픽 하나", None), ("가상토픽 둘", None)]
    load_warnings = cast("list[dict[str, Any]]", done.steps["load"].data["warnings"])
    assert [w["code"] for w in load_warnings] == ["subtopic_autofilled"] * 2  # 1부 load 에도 있다(@1 칸)


def test_same_subtopic_name_twice_in_a_topic_runs_both() -> None:
    received = support.received2()
    received["subtopicsByTopic"]["가상토픽 하나"][1]["name"] = "가상 서브 가"
    names = ("가상 서브 가", "가상 서브 가", "가상 서브 다")
    mock = MockProvider("openai")
    support.script_part1_dated(mock, received)
    support.script_part2(mock, names)
    done = support.run_iro(support.iro_inputs(received), support.spy2(mock))
    result = support.result(done)
    assert len(mock.calls) == 14
    assert [s["name"] for s in result["part2"]["topics"][0]["subtopics"]] == ["가상 서브 가", "가상 서브 가"]
    assert [s["description"] for s in result["part2"]["topics"][0]["subtopics"]] == [
        "가상 서브 가의 설명",
        "가상 서브 나의 설명",
    ]


# ── S11 등록 ───────────────────────────────────────────────────────────────────────────────


def test_the_flow_declaration() -> None:
    flow = iro_155.FLOW
    assert (flow.module, flow.id, flow.input_shape) == ("materiality", "materiality.iro@155", "materiality.input@1")
    assert flow.result_shapes == ("materiality.result@2", "materiality.digest@1")
    assert flow.output_files == ("materiality-websearch.xlsx", "materiality-final-report.xlsx")
    assert flow.steps == (
        "load",
        "regulation",
        "keywords",
        "controversy",
        "report",
        "part2_seed",
        "impact",
        "financial",
        "pathway",
        "report_iro",
    )
    assert flow.adapter_names == ("llm",)
    assert flow.optional_adapters == ()


def test_registration_has_both_and_defaults_to_the_one_run_flow() -> None:
    registry = FlowRegistry()
    registration.register(registry)
    assert registry.flows_of("materiality") == (colab_155.FLOW, iro_155.FLOW)
    assert registry.defaults() == {"materiality": "materiality.iro@155"}
    assert registry.default_of("materiality") is iro_155.FLOW


# ── S12 어림 ───────────────────────────────────────────────────────────────────────────────


def test_estimate_calls_no_provider_and_adds_both_parts() -> None:
    mock = MockProvider("openai")
    llm = support.spy2(mock)
    given = support.iro_inputs()
    got = iro_155.estimate_iro(given, llm)
    assert mock.calls == []
    assert llm.requests == []
    assert got["maxProviderCalls"] == 2 * 5 + 3 * 3
    assert got["part1"]["maxProviderCalls"] == 10
    assert got["part2"]["maxProviderCalls"] == 9
    assert got["totalUpperBoundUsd"]["withoutRetry"] == pytest.approx(
        got["part1"]["totalUpperBoundUsd"]["withoutRetry"] + got["part2"]["totalUpperBoundUsd"], abs=1e-6
    )
    assert got["totalUpperBoundUsd"]["withRetry"] == pytest.approx(
        got["part1"]["totalUpperBoundUsd"]["withRetry"] + got["part2"]["totalUpperBoundUsd"], abs=1e-6
    )
    assert got["unestimated"][-1] == "part2_context_text"
    assert "controversy_keywords" in got["unestimated"]
    assert "pathway_input" in got["unestimated"]
    user = next(r for r in llm.dry_runs if r.prompt == "materiality/impact@1").vars["user"]
    assert "제공된 정책/규정/가이드라인 정보 없음" in user


def test_estimate_rejects_a_bad_window_without_calls() -> None:
    received = support.received2()
    received["dateRange"] = "최근 1년"
    mock = MockProvider("openai")
    with pytest.raises(FlowInputError, match="dateRange 문법 밖"):
        iro_155.estimate_iro(support.iro_inputs(received), support.spy2(mock))
    assert mock.calls == []


# ── S13 축·순수 · S14 이름·키 ────────────────────────────────────────────────────────────────

FLOW_FILE = Path(iro_155.__file__)
WIRE_FILE = Path(shapes.__file__).with_name("wire.py")


def imported(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize("path", [FLOW_FILE, WIRE_FILE], ids=["iro_155", "wire"])
def test_no_clock_reads(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    for word in ("date.today", "datetime.now", "datetime.today", "datetime.utcnow", "time.time", "import time"):
        assert word not in source, word


def test_the_flow_imports_no_settings_sdk_or_part1_private_names() -> None:
    names = imported(FLOW_FILE)
    bad = [
        n
        for n in names
        if n.split(".")[0] in {"openai", "anthropic", "django", "os", "time"}
        or n.startswith(("esgapi.config", "esgapi.materiality.engines"))
        or re.search(r"\._[a-z]", n)
    ]
    assert bad == []
    source = FLOW_FILE.read_text(encoding="utf-8")
    assert "colab_155._" not in source
    assert "part2_155._" not in source
    assert "environ" not in source


def test_contracts_do_not_import_flows_or_engines() -> None:
    names = imported(WIRE_FILE)
    assert [n for n in names if ".engines" in n or ".flows" in n] == []


def test_no_key_like_text_in_the_new_files() -> None:
    for path in (FLOW_FILE, Path(__file__), Path(support.__file__)):
        assert re.search(r"sk-[A-Za-z0-9_-]{16,}", path.read_text(encoding="utf-8")) is None
