"""1부 한 건을 지어낸 모델 답으로 끝까지: 입력 꼴 → 엔진 dict → 프롬프트 → (지어낸 답) → 파싱·묶음 → 결과 꼴(발주서 §0
— LLM·네트워크 0). 호출 차례(키워드 한 번 → 토픽마다 규제·컨트로버시)와 흐름 등록은 IR1b 몫이고, 여기는 그 조립이
결과 꼴에 맞는지만 본다."""

import json
from pathlib import Path
from typing import Any, cast

from esgapi.materiality.contracts import shapes, wire
from esgapi.materiality.engines.colab_155 import constants, inputs, outcomes, parsing, prompts, whitelists

EXAMPLES = Path(__file__).resolve().parent / "data" / "examples"


def answer_for(user: str) -> str | None:
    """지어낸 모델: 프롬프트 글을 보고 정해진 답을 낸다(호출 0)."""
    if "topics: [" in user:  # 키워드 가변 글
        return '```json\n{"topics": [{"topic": "가상토픽 하나", "keywords": ["가상 키워드 1", "가상 키워드 2"]}]}\n```'
    if "keyword:" in user:  # 컨트로버시 가변 글
        if "가상토픽 셋" in user:
            return None  # 호출 실패
        return '{"topic_name": "가상토픽 하나", "results": {"items": [{"title": "가상 사건", "url": "https://example.com/a?utm_source=openai"}]}}'
    if "가상토픽 둘" in user:
        return "가상 답 — 객체가 없다"
    return '{"topic_name": "가상토픽 하나", "results": {"KR": [{"title": "가상 규정"}], "EU": [], "US": []}}'


def test_part1_end_to_end_with_made_up_answers() -> None:
    received = cast("dict[str, Any]", json.loads((EXAMPLES / "input-sample.json").read_text(encoding="utf-8")))
    before = json.dumps(received, ensure_ascii=False)
    shapes.check_input(received)
    industry = wire.engine_industry(received)
    topics = wire.engine_topics(received)
    name, raw_whitelist = whitelists.whitelist_for(received["sector"])
    system = prompts.regulation_system(raw_whitelist)
    assert "고용노동부" in system  # 비금융권 판(셀 73)

    keyword_text = answer_for(prompts.keywords_user(industry, received["dateRange"], received["mainLanguage"], topics))
    assert keyword_text is not None
    keywords = parsing.parse_keywords(keyword_text)
    assert isinstance(keywords, parsing.KeywordsParsed)
    warnings = wire.duplicate_keyword_warnings(keywords.duplicates)
    _, pairs = inputs.resolve_subtopics(wire.engine_subtopics(received), topics)
    warnings += wire.subtopic_warnings(pairs)

    text = inputs.industry_text(industry)
    results: list[shapes.MaterialityTopicResult] = []
    for t in topics:
        reg_answer = answer_for(
            prompts.regulation_user(t["topic"], t["description"], text, received["geoScope"], received["mainLanguage"])
        )
        reg, more = wire.regulation_outcome(outcomes.regulation_bundle(reg_answer), t["topic"], failure=None)
        warnings += more
        kw = parsing.keyword_str(keywords.by_topic, t["topic"])
        con_answer = answer_for(
            prompts.controversy_user(
                t["topic"], t["description"], industry, received["geoScope"], received["mainLanguage"], kw
            )
        )
        failure: shapes.MaterialityFailure | None = (
            {"kind": "provider_error", "message": "provider_error"} if con_answer is None else None
        )
        con, more = wire.controversy_outcome(
            outcomes.controversy_bundle(con_answer, t["topic"]), t["topic"], failure=failure
        )
        warnings += more
        results.append(wire.topic_result(t, keyword_str=kw, regulation=reg, controversy=con))

    settings: shapes.MaterialitySettings = {
        "model": constants.MODEL,
        "temperature": repr(constants.TEMPERATURE),
        "searchContextSize": constants.SEARCH_CONTEXT_SIZE,
        "promptIds": {"regulation": None, "keywords": None, "controversy": None},
    }
    result = wire.build_result(
        received,
        whitelist=name,
        settings=settings,
        keywords=wire.keywords_done(keywords.by_topic, keyword_text),
        topics=results,
        warnings=warnings,
    )
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)
    assert json.dumps(received, ensure_ascii=False) == before  # 입력은 그대로
    part1 = cast("list[dict[str, Any]]", result["part1"]["topics"])
    assert [t["regulation"]["status"] for t in part1] == ["done", "failed", "done"]
    assert [t["controversy"]["status"] for t in part1] == ["done", "done", "failed"]
    assert part1[0]["controversy"]["items"][0]["url"] == "https://example.com/a"  # utm 지움
    assert part1[1]["controversy"]["topicNameMismatch"] is True
    assert part1[1]["keywordStr"] == "(키워드 없음)"
    assert result["scope"]["whitelist"] == "cell73"
    assert result["settings"]["temperature"] == "0.1"
    codes = [(w["code"], w["topic"]) for w in result["warnings"]]
    assert codes == [
        ("subtopic_autofilled", "가상토픽 둘"),
        ("subtopic_autofilled", "가상토픽 셋"),
        ("topic_name_mismatch", "가상토픽 둘"),
        ("keywords_missing_for_topic", "가상토픽 둘"),
        ("keywords_missing_for_topic", "가상토픽 셋"),
    ]
