"""contracts/wire.py 의 2부(밴드 IR2a): 1부 결과 → 2부 입력(셀 50 꼴 글, 토픽마다 제 글 — 셀 51 결함 ④ 없음, @1·@2 다
받음), 엔진의 읽기 → 결과 칸(done·failed·not_run, 경고 셈), 잘림 경고, @2 조립(발주서 §3 S2·S12 일부). 기대값은 손으로
적었다. 입력·답은 전부 지어낸 「가상…」.
"""

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from esgapi.materiality.contracts import shapes, wire

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


# ── S2 입력 ─────────────────────────────────────────────────────────────────────────────────


def test_done_topic_gets_the_cell50_dump_of_its_own_bundle() -> None:
    received, result = load("input-sample.json"), load("result-sample.json")
    got, _ = wire.part2_input_from_result(received, result)
    first = result["part1"]["topics"][0]
    expected_reg = json.dumps(
        {"parsed": first["regulation"]["parsed"], "raw": None, "parse_error": None}, ensure_ascii=False, indent=2
    )
    expected_con = json.dumps(
        {"json": first["controversy"]["parsed"], "raw_text": None, "parse_error": None}, ensure_ascii=False, indent=2
    )
    assert got["topics"][0]["regulationText"] == expected_reg
    assert got["topics"][0]["controversyText"] == expected_con
    assert '\n  "parsed": {' in expected_reg  # indent 2
    assert "가상 규정 가" in expected_reg  # 한글 그대로(ensure_ascii=False)
    assert "\\u" not in expected_reg


def test_failed_and_not_run_topics() -> None:
    received, result = load("input-sample.json"), load("result-sample.json")
    got, _ = wire.part2_input_from_result(received, result)
    failed = result["part1"]["topics"][1]
    assert got["topics"][1]["regulationText"] == json.dumps(
        {"parsed": None, "raw": failed["regulation"]["raw"], "parse_error": failed["regulation"]["parseError"]},
        ensure_ascii=False,
        indent=2,
    )
    assert got["topics"][1]["controversyText"] == json.dumps(
        {"json": None, "raw_text": failed["controversy"]["raw"], "parse_error": failed["controversy"]["parseError"]},
        ensure_ascii=False,
        indent=2,
    )
    assert got["topics"][2]["regulationText"] == "제공된 정책/규정/가이드라인 정보 없음"
    assert got["topics"][2]["controversyText"] == "제공된 컨트로버시 정보 없음"


def test_the_rest_of_the_input() -> None:
    received, result = load("input-sample.json"), load("result-sample.json")
    got, warnings = wire.part2_input_from_result(received, result)
    assert got["company"] == "가상물류"
    assert got["industry"] == wire.engine_industry(received)
    assert got["valueChain"] == received["valueChain"]
    assert got["valueChain"] is not received["valueChain"]
    assert got["latestEventMode"] is False
    assert got["subtopics"] == {
        "가상토픽 하나": [{"name": "가상 서브토픽 가", "description": "가상 서브토픽 가의 설명"}]
    }
    assert got["source"] == "result"
    assert [t["topic"] for t in got["topics"]] == ["가상토픽 하나", "가상토픽 둘", "가상토픽 셋"]
    assert [t["description"] for t in got["topics"]] == [t["description"] for t in received["topics"]]
    # 1부 경고 넷 가운데 서브토픽 둘은 빼고(2부가 다시 단다) 둘을 phase·subtopic null 로
    assert [(w["code"], w["topic"], w["phase"], w["subtopic"]) for w in warnings] == [
        ("topic_name_mismatch", "가상토픽 하나", None, None),
        ("keywords_missing_for_topic", "가상토픽 둘", None, None),
    ]


def test_v2_result_is_accepted_and_its_part2_warnings_are_not_carried() -> None:
    received = load("input-sample.json")
    v1_input, _ = wire.part2_input_from_result(received, load("result-sample.json"))
    v2_input, warnings = wire.part2_input_from_result(received, load("result2-sample.json"))
    assert v2_input == v1_input
    assert [w["code"] for w in warnings] == ["topic_name_mismatch", "keywords_missing_for_topic"]


def test_topic_a_text_never_goes_to_topic_b() -> None:
    """셀 51 결함 ④(마지막 토픽의 규제를 모든 토픽에) 없음: 토픽마다 제 결과 칸."""
    received, result = load("input-sample.json"), load("result-sample.json")
    marked = copy.deepcopy(result)
    for t in marked["part1"]["topics"]:
        if t["regulation"]["status"] == "done":
            t["regulation"]["parsed"]["mark"] = f"표지 {t['topic']}"
    got, _ = wire.part2_input_from_result(received, marked)
    assert "표지 가상토픽 하나" in got["topics"][0]["regulationText"]
    assert all("표지" not in t["regulationText"] for t in got["topics"][1:])


def test_bad_results_are_refused() -> None:
    received, result = load("input-sample.json"), load("result-sample.json")
    with pytest.raises(ValueError, match="꼴이 아니다"):
        wire.part2_input_from_result(received, {**result, "schemaVersion": "greenwash.result@1"})
    short = copy.deepcopy(result)
    short["part1"]["topics"].pop()
    with pytest.raises(ValueError, match="입력 토픽이 없다"):
        wire.part2_input_from_result(received, short)


# ── 읽기 → 결과 칸 ──────────────────────────────────────────────────────────────────────────


def ctx(n: str) -> dict[str, Any]:
    return {
        "controversies": [{"title": f"가상 사건 {n}", "summary": f"요약 {n}", "url": f"https://example.com/{n}"}],
        "regulations": [],
    }


def read(rows: list[Any] | None, *, dropped: int = 0, parse_error: str | None = None, **more: Any) -> dict[str, Any]:
    parsed = None if rows is None and parse_error else {"impacts": rows}
    return {"parsed": parsed, "parseError": parse_error, "rows": rows, "dropped": dropped, **more}


def test_impact_done_view_and_warnings() -> None:
    rows: list[dict[str, Any]] = [
        {
            "impact_definition": "가상 정의",
            "impact_type": "부정",
            "value_chain_activities": ["가상 활동", "없는 활동", 3, None],
            "context": {"controversies": [*ctx("가")["controversies"], "글 원소"], "regulations": []},
        },
        {"impact_definition": None, "impact_type": "중립", "value_chain_activities": "가상 활동", "context": {}},
    ]
    outcome, warnings = wire.impact_outcome(
        "원문",
        read(rows, dropped=2),
        topic="가상토픽",
        subtopic="가상 서브",
        known_activities=["가상 활동"],
        failure=None,
    )
    assert outcome["status"] == "done"
    assert outcome["rows"] == [
        {
            "impactDefinition": "가상 정의",
            "impactType": "부정",
            "valueChainActivities": ["가상 활동", "없는 활동", "3"],
            "context": {
                "regulations": [],
                "controversies": [{"title": "가상 사건 가", "summary": "요약 가", "url": "https://example.com/가"}],
            },
        },
        {
            "impactDefinition": None,
            "impactType": "중립",
            "valueChainActivities": [],
            "context": {"regulations": [], "controversies": []},
        },
    ]
    assert [(w["code"], w["topic"], w["phase"], w["subtopic"]) for w in warnings] == [
        ("rows_dropped", "가상토픽", "impact", "가상 서브"),
        ("items_skipped", "가상토픽", "impact", "가상 서브"),
        ("value_chain_activity_unknown", "가상토픽", "impact", "가상 서브"),
        ("impact_type_unexpected", "가상토픽", "impact", "가상 서브"),
    ]
    assert "2개" in warnings[0]["message"] and "1개" in warnings[1]["message"]
    assert "2개" in warnings[2]["message"]  # 「없는 활동」·「3」
    assert "없는 활동" not in warnings[2]["message"]  # 모델 글을 싣지 않는다


def test_value_chain_null_means_every_choice_is_unknown() -> None:
    rows = [{"impact_definition": "가상", "impact_type": "긍정", "value_chain_activities": ["가상 활동"]}]
    _, warnings = wire.impact_outcome("원문", read(rows), topic="t", subtopic="s", known_activities=[], failure=None)
    assert [w["code"] for w in warnings] == ["value_chain_activity_unknown"]
    _, none = wire.impact_outcome(
        "원문", read(rows), topic="t", subtopic="s", known_activities=["가상 활동"], failure=None
    )
    assert none == []


def test_financial_type_checks() -> None:
    good = [
        {"impact_type": "리스크", "risk_type": "리스크-평판"},
        {"impact_type": "기회", "risk_type": None},
    ]
    outcome, warnings = wire.financial_outcome(
        "원문", read(good), topic="t", subtopic="s", known_activities=[], failure=None
    )
    assert warnings == []
    assert [(r["impactType"], r["riskType"]) for r in outcome["rows"]] == [("리스크", "리스크-평판"), ("기회", None)]
    bad = [{"impact_type": "위험", "risk_type": None}, {"impact_type": "리스크", "risk_type": "리스크-기타"}]
    _, warnings = wire.financial_outcome("원문", read(bad), topic="t", subtopic="s", known_activities=[], failure=None)
    assert [(w["code"], w["message"]) for w in warnings] == [
        ("impact_type_unexpected", "영향 유형·리스크 종류가 시킨 값 밖인 행 2개(값은 그대로 둠).")
    ]


def test_failed_branches() -> None:
    unparsable, _ = wire.impact_outcome(
        "가상 표",
        read(None, parse_error="JSONDecodeError: Expecting value: line 1 column 1 (char 0)"),
        topic="t",
        subtopic="s",
        known_activities=[],
        failure=None,
    )
    assert unparsable == {
        "status": "failed",
        "raw": "가상 표",
        "parseError": "JSONDecodeError: Expecting value: line 1 column 1 (char 0)",
        "failure": {"kind": "unparsable", "message": wire.UNPARSABLE},
    }
    timeout: shapes.MaterialityFailure = {"kind": "timeout", "message": "timeout"}
    called, _ = wire.financial_outcome(None, None, topic="t", subtopic="s", known_activities=[], failure=timeout)
    assert called == {"status": "failed", "raw": None, "parseError": None, "failure": timeout}
    truncated: shapes.MaterialityFailure = {"kind": "truncated", "message": "truncated"}
    cut, _ = wire.pathway_outcome(
        '{"pathways": [', read(None, parse_error="잘림"), topic="t", subtopic="s", skipped=False, failure=truncated
    )
    assert cut["failure"] == truncated and cut["raw"] == '{"pathways": ['
    with pytest.raises(ValueError, match="failure"):
        wire.impact_outcome(None, None, topic="t", subtopic="s", known_activities=[], failure=None)


def test_readable_truncated_answer_is_done() -> None:
    truncated: shapes.MaterialityFailure = {"kind": "truncated", "message": "truncated"}
    outcome, _ = wire.impact_outcome("부분", read([]), topic="t", subtopic="s", known_activities=[], failure=truncated)
    assert outcome == {"status": "done", "parsed": {"impacts": []}, "rows": []}


def test_pathway_view_skip_and_mismatch() -> None:
    joined: list[dict[str, Any]] = [
        {
            "i": 1,
            "impact_definition": "가상 정의",
            "impact_driver": "가상 동인",
            "business_impact": "가상 비즈니스",
            "financial_impact": "비용: 가상",
            "impact_type": "리스크",
            "risk_type": "리스크-시장",
            "context": ctx("나"),
        },
        {"i": True, "impact_definition": "가상 둘", "impact_type": None, "risk_type": None, "context": {}},
    ]
    outcome, warnings = wire.pathway_outcome(
        "원문", read(joined, mismatch=True), topic="t", subtopic="s", skipped=False, failure=None
    )
    assert outcome["rows"][0] == {
        "i": 1,
        "impactDefinition": "가상 정의",
        "impactDriver": "가상 동인",
        "businessImpact": "가상 비즈니스",
        "financialImpact": "비용: 가상",
        "impactType": "리스크",
        "riskType": "리스크-시장",
        "context": {
            "regulations": [],
            "controversies": [{"title": "가상 사건 나", "summary": "요약 나", "url": "https://example.com/나"}],
        },
    }
    assert outcome["rows"][1]["i"] is None  # bool 은 정수가 아니다
    assert [w["code"] for w in warnings] == ["pathway_row_mismatch"]
    skipped, none = wire.pathway_outcome(None, None, topic="t", subtopic="s", skipped=True, failure=None)
    assert skipped == {"status": "not_run", "message": wire.PATHWAY_SKIPPED}
    assert none == []


def test_truncated_warnings_read_the_calls() -> None:
    calls = [
        {"phase": "impact", "topic": "가", "subtopic": "가1", "ending": "done"},
        {"phase": "financial", "topic": "가", "subtopic": "가1", "ending": "truncated"},
        {"phase": "regulation", "topic": "가", "ending": "truncated"},  # 1부 기록(subtopic 칸 없음)
        {"phase": "pathway", "topic": "나", "subtopic": "나1", "ending": "timeout"},
    ]
    got = wire.truncated_warnings(calls)
    assert [(w["code"], w["phase"], w["topic"], w["subtopic"]) for w in got] == [
        ("answer_truncated", "financial", "가", "가1"),
        ("answer_truncated", "regulation", "가", None),
    ]


def test_build_result_v2_keeps_part1_and_passes_the_shape() -> None:
    received, seed = load("input-sample.json"), load("result-sample.json")
    example = load("result2-sample.json")
    part2_settings = example["settings"]["part2"]
    topics = [(t, s["subtopics"]) for t, s in zip(received["topics"], example["part2"]["topics"], strict=True)]
    part2 = wire.part2_done("result", topics)
    assert part2 == example["part2"]
    result = wire.build_result_v2(
        received, part1_result=seed, part2_settings=part2_settings, part2=part2, warnings=example["warnings"]
    )
    assert result == example
    assert result["part1"] is seed["part1"]
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE_V2].validate_python(result, strict=True)


def test_as_warning2() -> None:
    v1 = {"code": "items_skipped", "message": "가상", "topic": "t"}
    assert wire.as_warning2(v1, phase="regulation") == {**v1, "phase": "regulation", "subtopic": None}
    v2 = {**v1, "phase": "impact", "subtopic": "s"}
    assert wire.as_warning2(v2) == v2


def test_joined_financial_context_is_not_counted_twice() -> None:
    """Pathway 행의 context 는 재무 행에서 이어 온 것 — 뺀 원소는 재무 칸이 이미 세므로 items_skipped 를 다시 달지
    않는다(감독 처분 ⑤)."""
    context = {"controversies": ["글 원소", {"title": "t", "summary": None, "url": None}], "regulations": []}
    fin_read = read([{"impact_type": "리스크", "risk_type": "리스크-시장", "context": context}])
    _, fin_warnings = wire.financial_outcome(
        "원문", fin_read, topic="t", subtopic="s", known_activities=[], failure=None
    )
    assert [w["code"] for w in fin_warnings] == ["items_skipped"]
    joined = [
        {"i": 1, "impact_definition": None, "impact_type": "리스크", "risk_type": "리스크-시장", "context": context}
    ]
    outcome, path_warnings = wire.pathway_outcome(
        "원문", read(joined, mismatch=False), topic="t", subtopic="s", skipped=False, failure=None
    )
    assert path_warnings == []
    assert outcome["rows"][0]["context"]["controversies"] == [{"title": "t", "summary": None, "url": None}]
