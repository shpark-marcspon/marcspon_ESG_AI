"""contracts/wire.py: 입력 → 엔진 dict(코랩 키 차례), 묶음 ↔ Outcome 왕복, items 칸 차례·region·items_skipped, 경고,
결과 한 건이 결과 꼴에 맞음(발주서 §3 S7)."""

import json
from pathlib import Path
from typing import Any, cast

import pytest

from esgapi.materiality.contracts import shapes, wire
from esgapi.materiality.engines.colab_155 import outcomes, parsing

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"
TOPIC = "가상토픽 하나"
SETTINGS: shapes.MaterialitySettings = {
    "model": "gpt-4o",
    "temperature": "0.1",
    "searchContextSize": "low",
    "promptIds": {"regulation": None, "keywords": None, "controversy": None},
}


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def test_engine_dicts_use_colab_keys_in_colab_order() -> None:
    received = load("input-sample.json")
    industry = wire.engine_industry(received)
    assert [list(i) for i in industry] == [["standard", "industry_name", "description"]] * 2
    assert industry[0]["industry_name"] == received["industries"][0]["industryName"]
    assert [list(t) for t in wire.engine_topics(received)] == [["topic", "description"]] * 3
    assert wire.engine_subtopics(received) == {
        "가상토픽 하나": [{"name": "가상 서브토픽 가", "description": "가상 서브토픽 가의 설명"}]
    }
    assert wire.engine_subtopics({**received, "subtopicsByTopic": None}) == {}


REGULATION = {
    "topic_name": TOPIC,
    "results": {
        "KR": [
            {
                "title": "가상 규정",
                "summary": "요약",
                "event_date": None,
                "primary_url": "https://example.go.kr/a",
                "status": 3,
                "why_dates_differ": "동일",
            },
            "글 원소",
        ],
        "EU": [],
        "note": "목록이 아닌 값은 건너뛴다",
        "US": [{"title": "가상 US", "jurisdiction": ["US", "캐나다"]}],
    },
    "self_check": {"notes": "가상 메모"},
}


def test_regulation_items_follow_cell_33() -> None:
    items, skipped = wire.regulation_items(REGULATION)
    assert skipped == 1
    assert [list(i) for i in items] == [[*shapes.REGULATION_ITEM_KEYS, "region"]] * 2
    assert items[0] == {
        "title": "가상 규정",
        "summary": "요약",
        "jurisdiction": None,
        "authority": None,
        "event_date": None,
        "publish_date": None,
        "status": "3",
        "primary_url": "https://example.go.kr/a",
        "region": "KR",
    }
    assert items[1]["jurisdiction"] == '["US", "캐나다"]'  # 글이 아니면 json.dumps(ensure_ascii=False)
    assert items[1]["region"] == "US"
    assert wire.regulation_items({"items": [{"title": "가"}]})[0][0]["region"] is None  # 규칙 3
    assert wire.regulation_items({"results": [{"title": "가"}]})[0][0]["title"] == "가"
    assert wire.regulation_items({"topic_name": "가"}) == ([], 0)


def test_controversy_items_follow_cell_33() -> None:
    parsed = {
        "results": {"items": [{"title": "가", "severity": "높음", "url": "https://example.com/x", "extra": 1}, 5]}
    }
    items, skipped = wire.controversy_items(parsed)
    assert skipped == 1
    assert items == [
        {
            "title": "가",
            "date": None,
            "summary": None,
            "severity": "높음",
            "status": None,
            "url": "https://example.com/x",
            "region": None,
        }
    ]
    assert wire.controversy_items({"items": [{"title": "나"}]})[0][0]["title"] == "나"
    assert wire.controversy_items({"results": {"found_count": 0}}) == ([], 0)


ANSWERS = [
    None,
    "",
    "객체 없음",
    '{"a": 1,}',
    json.dumps(REGULATION, ensure_ascii=False),
    '{"topic_name": "다른", "items": []}',
]


@pytest.mark.parametrize("text", ANSWERS)
def test_regulation_bundles_round_trip(text: str | None) -> None:
    bundle = outcomes.regulation_bundle(text)
    outcome, _ = wire.regulation_outcome(bundle, TOPIC, failure=None)
    assert list((wire.bundle_of_regulation(outcome) or {}).items()) == list(bundle.items())
    assert outcome["status"] == ("done" if bundle["parsed"] is not None else "failed")


@pytest.mark.parametrize("text", ANSWERS)
def test_controversy_bundles_round_trip(text: str | None) -> None:
    bundle = outcomes.controversy_bundle(text, TOPIC)
    failure: shapes.MaterialityFailure = {"kind": "provider_error", "message": "provider_error"}
    outcome, _ = wire.controversy_outcome(bundle, TOPIC, failure=failure if text is None else None)
    assert list((wire.bundle_of_controversy(outcome) or {}).items()) == list(bundle.items())


def test_failures_and_warnings() -> None:
    reg, warnings = wire.regulation_outcome(outcomes.regulation_bundle(None), TOPIC, failure=None)
    assert reg == {
        "status": "failed",
        "raw": "",
        "parseError": "Empty LLM output",
        "failure": {"kind": "unparsable", "message": wire.UNPARSABLE},
    }
    assert warnings == []
    with pytest.raises(ValueError, match="no_result"):
        wire.controversy_outcome(outcomes.controversy_bundle(None, TOPIC), TOPIC, failure=None)
    con, warnings = wire.controversy_outcome(
        outcomes.controversy_bundle('{"topic_name": "다른", "items": [1, {"title": "가"}]}', TOPIC), TOPIC, failure=None
    )
    assert con["topicNameMismatch"] is True
    assert [w["code"] for w in warnings] == ["items_skipped", "topic_name_mismatch"]
    assert all(w["topic"] == TOPIC for w in warnings)
    reg, warnings = wire.regulation_outcome(outcomes.regulation_bundle(json.dumps(REGULATION)), TOPIC, failure=None)
    assert reg["topicNameMismatch"] is False
    assert reg["selfCheck"] == {"notes": "가상 메모"}
    assert [w["code"] for w in warnings] == ["items_skipped"]
    assert wire.keywords_failed("가상 원문", failure=None)["failure"]["kind"] == "unparsable"
    with pytest.raises(ValueError, match="failure"):
        wire.keywords_failed(None, failure=None)


def test_no_keywords_mark_is_the_engine_one() -> None:
    assert wire.NO_KEYWORDS == parsing.NO_KEYWORDS


def test_the_example_result_is_what_wire_builds() -> None:
    """합성 예시(result-sample.json)를 wire 로 다시 지으면 같은 글이다 — 예시가 실제 조립과 어긋나지 않는다."""
    received = load("input-sample.json")
    example = load("result-sample.json")
    topics_out: list[shapes.MaterialityTopicResult] = []
    warnings: list[shapes.MaterialityWarning] = []
    for t in example["part1"]["topics"]:
        topic_in = next(x for x in received["topics"] if x["topic"] == t["topic"])
        reg_bundle = wire.bundle_of_regulation(t["regulation"])
        con_bundle = wire.bundle_of_controversy(t["controversy"])
        reg: dict[str, Any] = dict(t["regulation"])
        con: dict[str, Any] = dict(t["controversy"])
        if reg_bundle is not None:
            reg, more = wire.regulation_outcome(reg_bundle, t["topic"], failure=t["regulation"].get("failure"))
            warnings += more
        if con_bundle is not None:
            con, more = wire.controversy_outcome(con_bundle, t["topic"], failure=t["controversy"].get("failure"))
            warnings += more
        topics_out.append(wire.topic_result(topic_in, keyword_str=t["keywordStr"], regulation=reg, controversy=con))
    warnings += wire.subtopic_warnings([("subtopic_autofilled", "가상토픽 둘"), ("subtopic_autofilled", "가상토픽 셋")])
    result = wire.build_result(
        received,
        whitelist="cell73",
        settings=SETTINGS,
        keywords=example["part1"]["keywords"],
        topics=topics_out,
        warnings=warnings,
    )
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)
    assert json.dumps(result, ensure_ascii=False) == json.dumps(example, ensure_ascii=False)  # 키 차례까지


def test_websearch_payload_skips_not_run_and_keeps_input_order() -> None:
    payload = wire.websearch_payload(load("result-sample.json"))
    assert list(payload) == ["regulation_updates_by_topic", "controversies_by_topic"]
    assert list(payload["regulation_updates_by_topic"]) == ["가상토픽 하나", "가상토픽 둘"]
    assert payload["controversies_by_topic"]["가상토픽 둘"] == {
        "json": None,
        "raw_text": "",
        "parse_error": "no_result",
    }
    assert list(payload["controversies_by_topic"]["가상토픽 하나"]) == ["json", "raw_text", "parse_error"]


def test_failure_is_a_required_keyword_and_a_provider_failure_stays_itself() -> None:
    """감독 처분 I1(가지 리뷰): failure 는 기본값 없는 키워드 — 부르는 쪽이 매번 정한다. 셀 17 묶음은 호출 실패와 빈
    답이 같아서(W8) 기본값이 있으면 공급사 실패가 unparsable 로 접힌다."""
    bundle = outcomes.regulation_bundle(None)
    loose: dict[str, Any] = {  # 타입 검사를 지나 failure 없이 부르려고 Any 로 잡는다
        "regulation": wire.regulation_outcome,
        "controversy": wire.controversy_outcome,
        "keywords": wire.keywords_failed,
    }
    with pytest.raises(TypeError):
        loose["regulation"](bundle, TOPIC)
    with pytest.raises(TypeError):
        loose["controversy"](outcomes.controversy_bundle(None, TOPIC), TOPIC)
    with pytest.raises(TypeError):
        loose["keywords"]("가상 원문")
    provider: shapes.MaterialityFailure = {"kind": "provider_error", "message": "provider_error"}
    reg, _ = wire.regulation_outcome(bundle, TOPIC, failure=provider)
    assert reg["failure"] == provider
    con, _ = wire.controversy_outcome(outcomes.controversy_bundle(None, TOPIC), TOPIC, failure=provider)
    assert con["failure"] == provider
    assert wire.keywords_failed(None, failure=provider)["failure"] == provider


def test_keywords_unparsable_reason_is_the_failure_message() -> None:
    """감독 처분 사소 4: 엔진 KeywordsUnparsable.reason(모델 글 0)이 failure.message 로."""
    text = '{"topics": [{"topic": "가상토픽 하나"}]}'
    parsed = parsing.parse_keywords(text)
    assert isinstance(parsed, parsing.KeywordsUnparsable)
    failed = wire.keywords_failed(text, failure=None, reason=parsed.reason)
    assert failed["failure"] == {"kind": "unparsable", "message": parsed.reason}
    assert "가상토픽" not in failed["failure"]["message"]
    assert wire.keywords_failed(text, failure=None)["failure"]["message"] == wire.UNPARSABLE


@pytest.mark.parametrize(
    ("side", "parsed"),
    [
        ("regulation", {"topic_name": "x", "updates": [{"title": "가"}]}),
        ("regulation", {"results": {"KR": "none"}}),
        ("controversy", {"topic_name": "x", "updates": [{"title": "가"}]}),
        ("controversy", {"topic_name": "x", "results": {"found_count": 0}}),
    ],
)
def test_an_unrecognized_answer_is_done_with_a_warning(side: str, parsed: dict[str, Any]) -> None:
    """감독 처분 I2(가): 항목 목록 자리를 못 알아본 답은 done 그대로 + items_unrecognized."""
    text = json.dumps(parsed, ensure_ascii=False)
    if side == "regulation":
        outcome, warnings = wire.regulation_outcome(outcomes.regulation_bundle(text), TOPIC, failure=None)
    else:
        outcome, warnings = wire.controversy_outcome(outcomes.controversy_bundle(text, "x"), "x", failure=None)
    assert outcome["status"] == "done"
    assert outcome["items"] == []
    assert [w["code"] for w in warnings] == ["items_unrecognized"]


def test_recognized_answers_with_empty_lists_have_no_unrecognized_warning() -> None:
    regulation: list[dict[str, Any]] = [{"results": {"KR": [], "EU": [], "US": []}}, {"items": []}, {"results": []}]
    for parsed in regulation:
        _, warnings = wire.regulation_outcome(outcomes.regulation_bundle(json.dumps(parsed)), TOPIC, failure=None)
        assert warnings == []
    controversy: list[dict[str, Any]] = [
        {"topic_name": TOPIC, "results": {"items": []}},
        {"topic_name": TOPIC, "items": []},
    ]
    for parsed in controversy:
        _, warnings = wire.controversy_outcome(
            outcomes.controversy_bundle(json.dumps(parsed), TOPIC), TOPIC, failure=None
        )
        assert warnings == []


def test_a_model_answering_the_no_keywords_mark_is_still_warned() -> None:
    """글자 대조가 맞다는 고정(MARC-ISSUE-345 3, 밴드 IRS1 D2): 모델이 「(키워드 없음)」 하나만 키워드로 내면
    keyword_str 는 「키워드 없음」과 같은 글이고(프롬프트에 간 글이 바이트 같다) 경고도 그 토픽에 하나 — 경고 문장이
    참이다."""
    keyword_str = parsing.keyword_str({TOPIC: ["(키워드 없음)"]}, TOPIC)
    assert keyword_str == wire.NO_KEYWORDS == parsing.keyword_str({}, TOPIC)
    topics = cast("list[shapes.MaterialityTopicResult]", [{"topic": TOPIC, "keywordStr": keyword_str}])
    warnings = wire.missing_keyword_warnings(topics)
    assert [(w["code"], w["topic"]) for w in warnings] == [("keywords_missing_for_topic", TOPIC)]
