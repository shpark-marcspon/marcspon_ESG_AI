"""2부 단계(flows/part2_155.py)를 시험용 흐름(씨앗 → impact → financial → pathway → report2)으로 끝까지(발주서 §3 S4·
S5·S10·S11·S12·S14·S15): 코랩 차례·수(3 × 서브토픽), 요청의 칸(gpt-4.1·temperature 없음·상한·system 자리·id), 보내는 글
(엔진 글과 바이트 같음), @2 결과, 호출 기록의 손셈, 가치사슬·잇기·NaN, 순수. 공급사는 모의만(실호출 0)."""

import ast
import io
import json
import math
from pathlib import Path
from typing import Any, cast

import pytest
from openpyxl import load_workbook

from esgapi.core.llm.client import CallRequest, ToolCallRequest
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import ProviderRequest, TextPart, WebSearchTool
from esgapi.materiality.contracts import shapes, wire
from esgapi.materiality.engines.colab_155 import part2_prompts, part2_render
from esgapi.materiality.flows import part2_155
from esgapi.materiality.tests.flows import support
from esgapi.materiality.tests.flows.support import CALL_USD2, SEARCH_USD, SUBTOPICS2, USAGE


def run_all(given: dict[str, Any] | None = None, *, hosted: int = 0, **changes: Any) -> tuple[MockProvider, Any, Any]:
    mock = MockProvider("openai")
    support.script_part2(mock, hosted=hosted)
    llm = support.spy2(mock)
    done = support.run2(support.inputs2(given, **changes), llm)
    assert mock.pending == 0
    return mock, llm, support.result(done)


def records(done: Any, phase: str) -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", done.steps[phase].data["calls"])


def user_text(request: ProviderRequest) -> str:
    (part,) = request.user
    assert isinstance(part, TextPart)
    return part.text


def system_text(request: ProviderRequest) -> str:
    (segment,) = request.system
    return segment.text


def expected_messages(given: dict[str, Any]) -> list[tuple[str, str]]:
    """엔진 글(코랩 차례 — 영향 셋 → 재무 셋 → Pathway 셋)."""
    part2_input, _ = wire.part2_input_from_result(given, support.part1_result(given))
    value_chain = part2_input["valueChain"] or []
    topics = {t["topic"]: t for t in part2_input["topics"]}
    places = [("가상토픽 하나", "가상 서브 가"), ("가상토픽 하나", "가상 서브 나"), ("가상토픽 둘", "가상 서브 다")]
    descriptions = {
        "가상 서브 가": "가상 서브 가의 설명",
        "가상 서브 나": "가상 서브 나의 설명",
        "가상 서브 다": "가상 서브 다의 설명",
    }
    out: list[tuple[str, str]] = []
    for build, system in (
        (part2_prompts.impact_user, part2_prompts.IMPACT_SYSTEM),
        (part2_prompts.financial_user, part2_prompts.FINANCIAL_SYSTEM),
    ):
        for topic, sub in places:
            t = topics[topic]
            user = build(
                "가상물류",
                part2_input["industry"],
                value_chain,
                topic,
                sub,
                descriptions[sub],
                t["controversyText"],
                t["regulationText"],
            )
            out.append((system, user))
    for topic, sub in places:
        rows = json.loads(support.financial_answer(sub))["impacts"]
        table = part2_render.pathway_table(topic, sub, rows)
        out.append((part2_prompts.PATHWAY_SYSTEM, part2_prompts.pathway_user(table)))
    return out


# ── S4 끝까지 ───────────────────────────────────────────────────────────────────────────────


def test_calls_follow_colab_order_and_count() -> None:
    mock, llm, result = run_all()
    assert len(mock.calls) == 9  # 3 단계 × 서브토픽 3
    assert [r.prompt for r in llm.requests] == ["materiality/impact@1"] * 3 + ["materiality/financial@1"] * 3 + [
        "materiality/pathway@1"
    ] * 3
    given = support.received2()
    assert [(system_text(r), user_text(r)) for r in mock.calls] == expected_messages(given)
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE_V2].validate_python(result, strict=True)


def test_every_request_is_the_colab_part2_runner() -> None:
    mock, llm, _ = run_all()
    for request in llm.requests:
        assert isinstance(request, CallRequest)
        request = cast("CallRequest[str]", request)
        assert request.route == "standard-openai-41"
        assert request.temperature is None
        assert request.schema is None
        assert request.max_output_tokens == 32_768
        assert request.timeout_ms == 600_000
    for sent in mock.calls:
        assert sent.api_model_id == "gpt-4.1"
        assert sent.temperature is None
        assert sent.max_output_tokens == 32_768  # (c) 추론 여유분 없이 그대로
        assert sent.tools == ()
        assert sent.tool_choice is None
        assert sent.system_placement == "instructions"  # 처분 ⑥ — call 은 instructions 칸
        assert sent.json_schema is None


def test_result_by_hand() -> None:
    _, _, result = run_all()
    assert result["schemaVersion"] == "materiality.result@2"
    assert result["part1"] == support.part1_result(support.received2())["part1"]
    assert result["settings"]["part2"] == {
        "model": "gpt-4.1",
        "maxOutputTokens": 32768,
        "latestEventMode": False,
        "promptIds": {
            "impact": "materiality/impact@1",
            "financial": "materiality/financial@1",
            "pathway": "materiality/pathway@1",
        },
    }
    part2 = result["part2"]
    assert part2["status"] == "done" and part2["input"] == {"source": "result"}
    assert [(t["topic"], [s["name"] for s in t["subtopics"]]) for t in part2["topics"]] == [
        ("가상토픽 하나", ["가상 서브 가", "가상 서브 나"]),
        ("가상토픽 둘", ["가상 서브 다"]),
    ]
    sub = part2["topics"][0]["subtopics"][0]
    assert sub["autofilled"] is False
    assert sub["impact"]["rows"] == [
        {
            "impactDefinition": "가상 서브 가 가상 환경 영향",
            "impactType": "부정",
            "valueChainActivities": ["가상 활동"],
            "context": {
                "regulations": [
                    {
                        "title": "가상 규정 가상 서브 가 영향",
                        "summary": "가상 규정 가상 서브 가 영향의 요약",
                        "url": "https://example.com/r/가상 서브 가 영향",
                    }
                ],
                "controversies": [
                    {
                        "title": "가상 사건 가상 서브 가 영향",
                        "summary": "가상 사건 가상 서브 가 영향의 요약",
                        "url": "https://example.com/c/가상 서브 가 영향",
                    }
                ],
            },
        }
    ]
    assert [(r["impactType"], r["riskType"]) for r in sub["financial"]["rows"]] == [
        ("리스크", "리스크-규제 및 법률"),
        ("기회", None),
    ]
    assert [(r["i"], r["impactDriver"], r["impactType"], r["riskType"]) for r in sub["pathway"]["rows"]] == [
        (1, "가상 동인 1", "리스크", "리스크-규제 및 법률"),
        (2, "가상 동인 2", "기회", None),
    ]
    assert sub["pathway"]["rows"][0]["context"] == sub["financial"]["rows"][0]["context"]
    codes = [(w["code"], w["phase"]) for w in result["warnings"]]
    assert codes == [("topic_name_mismatch", None), ("keywords_missing_for_topic", None)]  # 1부에서 옮긴 둘뿐


def test_call_records_by_hand() -> None:
    mock = MockProvider("openai")
    support.script_part2(mock)
    done = support.run2(support.inputs2(), support.spy2(mock))
    calls = [c for phase in ("impact", "financial", "pathway") for c in records(done, phase)]
    assert [(c["phase"], c["topic"], c["subtopic"], c["ending"]) for c in calls] == [
        (phase, topic, sub, "done")
        for phase in ("impact", "financial", "pathway")
        for topic, sub in (
            ("가상토픽 하나", "가상 서브 가"),
            ("가상토픽 하나", "가상 서브 나"),
            ("가상토픽 둘", "가상 서브 다"),
        )
    ]
    assert {c["costUsd"] for c in calls} == {CALL_USD2}
    assert {c["model"] for c in calls} == {"gpt-4.1"}
    assert {c["hostedCalls"] for c in calls} == {0}
    assert done.steps["impact"].data["spentUsd"] == pytest.approx(3 * CALL_USD2)
    assert done.steps["pathway"].data["spentUsd"] == pytest.approx(9 * CALL_USD2)  # 0.324


def test_each_topic_gets_its_own_regulation_text() -> None:
    """셀 51 결함 ④ 없음 — 기대 글을 wire 로 짓지 않고 1부 예시의 글자로 본다: 가상토픽 하나의 자리(영향·재무 각 둘)는
    제 규제(「가상 규정 가」)를, 가상토픽 둘의 자리는 제 실패 묶음(「가상 답 — 객체가 없다」)을 싣는다."""
    mock, _, _ = run_all()
    users = [user_text(r) for r in mock.calls[:6]]
    first = [users[i] for i in (0, 1, 3, 4)]
    second = [users[i] for i in (2, 5)]
    assert all('"title": "가상 규정 가"' in u and "가상 답 — 객체가 없다" not in u for u in first)
    assert all('"raw": "가상 답 — 객체가 없다"' in u and "가상 규정 가" not in u for u in second)


# ── S5 서브토픽 ─────────────────────────────────────────────────────────────────────────────


def test_subtopic_key_unmatched_and_autofill() -> None:
    given = support.received2()
    given["subtopicsByTopic"] = {"가상토픽 하나": given["subtopicsByTopic"]["가상토픽 하나"], "없는 토픽": []}
    mock = MockProvider("openai")
    support.script_part2(mock, ("가상 서브 가", "가상 서브 나", "가상토픽 둘"))
    result = support.result(support.run2(support.inputs2(given), support.spy2(mock)))
    second = result["part2"]["topics"][1]["subtopics"]
    assert [(s["name"], s["description"], s["autofilled"]) for s in second] == [
        ("가상토픽 둘", "가상토픽 둘의 설명 — 가상의 안전 관리", True)
    ]
    assert [(w["code"], w["topic"], w["message"]) for w in result["warnings"] if w["code"].startswith("subtopic")] == [
        ("subtopic_autofilled", "가상토픽 둘", "서브토픽이 없어 토픽 설명으로 하나 지어 넣었다(코랩 셀 46)."),
        (
            "subtopic_key_unmatched",
            None,
            "서브토픽 키가 어느 토픽명과도 맞지 않아 쓰이지 않는다(코랩은 조용히 버린다). 키: 없는 토픽",
        ),
    ]


def test_eighteen_subtopics_make_fifty_four_calls() -> None:
    given = support.received2()
    names = [f"가상 서브 {n}" for n in range(1, 19)]
    given["subtopicsByTopic"] = {
        "가상토픽 하나": [{"name": n, "description": "가상"} for n in names[:9]],
        "가상토픽 둘": [{"name": n, "description": "가상"} for n in names[9:]],
    }
    mock = MockProvider("openai")
    support.script_part2(mock, tuple(names))
    support.run2(support.inputs2(given), support.spy2(mock))
    assert len(mock.calls) == 54 and mock.pending == 0


# ── S10 latest ──────────────────────────────────────────────────────────────────────────────


def test_latest_event_mode_uses_the_tool_loop() -> None:
    mock, llm, result = run_all(support.received2(latest=True), hosted=1)
    for request in llm.requests:
        assert isinstance(request, ToolCallRequest)
        assert request.tools == (WebSearchTool(search_context_size="low"),)
        assert cast("WebSearchTool", request.tools[0]).user_location is None
        assert request.max_steps == 1 and request.tool_choice is None and request.temperature is None
        assert request.system_placement == "input_message"
        assert request.max_output_tokens == 32_768
    for sent in mock.calls:
        assert sent.tools == (WebSearchTool(search_context_size="low"),)
        assert sent.system_placement == "input_message"
        assert sent.temperature is None and sent.tool_choice is None
    assert result["settings"]["part2"]["latestEventMode"] is True


def test_latest_call_records_add_the_search_fee() -> None:
    mock = MockProvider("openai")
    support.script_part2(mock, hosted=1)
    done = support.run2(support.inputs2(support.received2(latest=True)), support.spy2(mock))
    calls = records(done, "impact")
    assert {(c["hostedCalls"], c["costUsd"]) for c in calls} == {(1, round(CALL_USD2 + SEARCH_USD, 6))}  # 0.046


# ── S11 잇기 · S12 가치사슬 ─────────────────────────────────────────────────────────────────


def test_pathway_takes_type_and_context_from_financial_rows_and_flags_mismatch() -> None:
    mock = MockProvider("openai")
    for name in SUBTOPICS2:
        mock.enqueue_text(support.impact_answer(name), USAGE)
    for name in SUBTOPICS2:
        mock.enqueue_text(support.financial_answer(name), USAGE)
    odd = json.loads(support.pathway_answer("가상 서브 가"))
    odd["pathways"][0]["impact_type"] = "모델이 쓴 유형"
    odd["pathways"][1]["impact_definition"] = "다르게 옮긴 정의"
    mock.enqueue_text(json.dumps(odd, ensure_ascii=False), USAGE)
    short = json.loads(support.pathway_answer("가상 서브 나"))
    short["pathways"] = short["pathways"][:1]
    mock.enqueue_text(json.dumps(short, ensure_ascii=False), USAGE)
    mock.enqueue_text(support.pathway_answer("가상 서브 다"), USAGE)
    result = support.result(support.run2(support.inputs2(), support.spy2(mock)))
    first = result["part2"]["topics"][0]["subtopics"][0]["pathway"]["rows"]
    assert first[0]["impactType"] == "리스크"  # 모델 칸이 아니라 재무 행
    mismatch = [(w["topic"], w["subtopic"]) for w in result["warnings"] if w["code"] == "pathway_row_mismatch"]
    assert mismatch == [("가상토픽 하나", "가상 서브 가"), ("가상토픽 하나", "가상 서브 나")]


def test_value_chain_activities() -> None:
    mock = MockProvider("openai")
    for name in SUBTOPICS2:
        body = json.loads(support.impact_answer(name))
        body["impacts"][0]["value_chain_activities"] = ["가상 활동", "입력에 없는 활동"]
        mock.enqueue_text(json.dumps(body, ensure_ascii=False), USAGE)
    for name in SUBTOPICS2:
        mock.enqueue_text(support.financial_answer(name), USAGE)
    for name in SUBTOPICS2:
        mock.enqueue_text(support.pathway_answer(name), USAGE)
    result = support.result(support.run2(support.inputs2(), support.spy2(mock)))
    rows = result["part2"]["topics"][0]["subtopics"][0]["impact"]["rows"]
    assert rows[0]["valueChainActivities"] == ["가상 활동", "입력에 없는 활동"]
    unknown = [(w["phase"], w["subtopic"]) for w in result["warnings"] if w["code"] == "value_chain_activity_unknown"]
    assert unknown == [("impact", "가상 서브 가"), ("impact", "가상 서브 나"), ("impact", "가상 서브 다")]


def test_value_chain_null_goes_as_an_empty_list() -> None:
    mock, _, result = run_all(support.received2(value_chain=False))
    # 묶음 글이 여러 줄이라 dedent 가 벗기지 않는다(코랩 셀 50 그대로) — 빈 목록 repr 이 8칸 들여 간다
    assert all("<value_chain_list>\n        []\n      </value_chain_list>" in user_text(r) for r in mock.calls[3:6])
    assert all("<value_chain_list>\n        []\n        </value_chain_list>" in user_text(r) for r in mock.calls[:3])
    unknown = [w for w in result["warnings"] if w["code"] == "value_chain_activity_unknown"]
    assert len(unknown) == 6  # 영향 셋·재무 셋이 「가상 활동」을 골랐는데 입력 사슬이 없다


# ── S14 NaN ─────────────────────────────────────────────────────────────────────────────────


def test_nan_in_an_answer_ends_as_null() -> None:
    mock = MockProvider("openai")
    for name in SUBTOPICS2:
        mock.enqueue_text(
            support.impact_answer(name).replace('"topic": "가상"', '"topic": "가상", "score": NaN'), USAGE
        )
    for name in SUBTOPICS2:
        mock.enqueue_text(support.financial_answer(name), USAGE)
    for name in SUBTOPICS2:
        mock.enqueue_text(support.pathway_answer(name), USAGE)
    result = support.result(support.run2(support.inputs2(), support.spy2(mock)))
    parsed = result["part2"]["topics"][0]["subtopics"][0]["impact"]["parsed"]
    assert "score" in parsed and parsed["score"] is None
    json.dumps(result, allow_nan=False)
    assert not any(isinstance(v, float) and math.isnan(v) for v in parsed.values())


# ── S15 순수 ────────────────────────────────────────────────────────────────────────────────


def test_part2_flow_file_reads_no_settings_and_no_sdk() -> None:
    tree = ast.parse(Path(part2_155.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    bad = sorted(
        n for n in names if n.split(".")[0] in {"os", "django", "openai", "anthropic", "httpx"} or "config" in n
    )
    assert bad == []
    assert all(not isinstance(n, ast.Name) or n.id not in {"getenv", "environ"} for n in ast.walk(tree))
    assert not hasattr(part2_155, "FLOW")  # 흐름·등록은 IR2b·IR3


# ── 어림(공급사 호출 0) ──────────────────────────────────────────────────────────────────────


def test_estimate_part2_calls_no_provider() -> None:
    mock = MockProvider("openai")
    llm = support.spy2(mock)
    given = support.received2()
    part2_input, _ = wire.part2_input_from_result(given, support.part1_result(given))
    got = part2_155.estimate_part2(part2_input, support.inputs2(given), llm)
    assert mock.calls == []
    assert got["maxProviderCalls"] == 9
    assert {phase: v["calls"] for phase, v in got["perPhase"].items()} == {"impact": 3, "financial": 3, "pathway": 3}
    assert all(isinstance(r, CallRequest) for r in llm.dry_runs) and len(llm.dry_runs) == 9
    # 위끝 ≥ 출력 상한을 다 쓴 몫: 9 × 32,768 × 8.0 / 1M = 2.359296
    assert got["totalUpperBoundUsd"] >= 9 * 32_768 * 8.0 / 1_000_000
    assert "pathway_input" in got["unestimated"]
    latest_input = {**part2_input, "latestEventMode": True}
    latest = part2_155.estimate_part2(latest_input, support.inputs2(given), llm)
    assert all(isinstance(r, ToolCallRequest) for r in llm.dry_runs[9:]) and len(llm.dry_runs) == 18
    assert latest["totalUpperBoundUsd"] > got["totalUpperBoundUsd"]  # web_search 건당 몫
    with pytest.raises(ValueError, match="assumed_fin_rows"):
        part2_155.estimate_part2(part2_input, support.inputs2(given), llm, assumed_fin_rows=0)


def test_estimate_for_eighteen_subtopics() -> None:
    given = support.received2()
    names = [f"가상 서브 {n}" for n in range(1, 19)]
    given["subtopicsByTopic"] = {
        "가상토픽 하나": [{"name": n, "description": "가상"} for n in names[:9]],
        "가상토픽 둘": [{"name": n, "description": "가상"} for n in names[9:]],
    }
    part2_input, _ = wire.part2_input_from_result(given, support.part1_result(given))
    got = part2_155.estimate_part2(part2_input, support.inputs2(given), support.spy2(MockProvider("openai")))
    assert got["maxProviderCalls"] == 54


# ── 최종 엑셀(report2 의 파일) ───────────────────────────────────────────────────────────────


def test_report2_writes_the_final_workbook() -> None:
    mock = MockProvider("openai")
    support.script_part2(mock)
    done = support.run2(support.inputs2(), support.spy2(mock))
    (report,) = done.output.files
    assert report.name == "materiality-final-report.xlsx"
    book = load_workbook(io.BytesIO(report.content))
    assert book.sheetnames == ["1-1. Short-list 선정", "2-1. 환경사회 영향 식별", "2-2. 재무 영향 식별", "RAW_JSON"]
    soc = book["2-1. 환경사회 영향 식별"]
    fin = book["2-2. 재무 영향 식별"]
    assert [soc[f"D{r}"].value for r in range(6, soc.max_row + 1)] == [1, 2, 3]  # 영향 row 셋(자리마다 하나)
    assert [fin[f"D{r}"].value for r in range(6, fin.max_row + 1)] == [1, 2, 3, 4, 5, 6]  # Pathway row 여섯
    assert [fin[f"P{r}"].value for r in range(6, 8)] == ["리스크", "기회"]
    short = book["1-1. Short-list 선정"]
    assert [short[f"C{r}"].value for r in (5, 6)] == ["가상토픽 하나", "가상토픽 둘"]
    assert str(short["F5"].value).startswith("1) [환경·사회] 제목: 가상 규정 가상 서브 가 영향\n")
    raw = book["RAW_JSON"]
    text = "".join(str(raw.cell(row=r, column=1).value) for r in range(1, raw.max_row + 1))
    assert json.loads(text) == support.result(done)


def test_long_cell_adds_an_xlsx_warning() -> None:
    mock = MockProvider("openai")
    body = json.loads(support.impact_answer("가상 서브 가"))
    body["impacts"][0]["impact_definition"] = "가" * 40_000
    mock.enqueue_text(json.dumps(body, ensure_ascii=False), USAGE)
    for name in SUBTOPICS2[1:]:
        mock.enqueue_text(support.impact_answer(name), USAGE)
    for name in SUBTOPICS2:
        mock.enqueue_text(support.financial_answer(name), USAGE)
    for name in SUBTOPICS2:
        mock.enqueue_text(support.pathway_answer(name), USAGE)
    result = support.result(support.run2(support.inputs2(), support.spy2(mock)))
    cut = [w for w in result["warnings"] if w["code"] == "xlsx_cell_truncated"]
    assert cut == [
        {
            "code": "xlsx_cell_truncated",
            "message": "엑셀 「2-1. 환경사회 영향 식별」 Q6 칸이 32,767자를 넘어 앞부분만 담았다(원문 40000자).",
            "topic": "가상토픽 하나",
            "phase": "report",
            "subtopic": None,
        }
    ]
    assert result["part2"]["topics"][0]["subtopics"][0]["impact"]["rows"][0]["impactDefinition"] == "가" * 40_000
