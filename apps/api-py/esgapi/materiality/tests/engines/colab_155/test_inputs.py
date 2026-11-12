"""engines/colab_155/inputs.py: industry_text(셀 11 손셈), resolve_subtopics(셀 46 — 경고 둘, 받은 dict 그대로)
(발주서 §3 S5)."""

import copy
import json

from esgapi.materiality.engines.colab_155 import inputs

INDUSTRY = [
    {"standard": "SASB", "industry_name": "가상 산업 하나", "description": "가상 설명 {하나}"},
    {"standard": "KSIC", "industry_name": "가상 산업 둘", "description": "가상 설명 둘"},
]
TOPICS = [
    {"topic": "가상토픽 하나", "description": "하나의 설명"},
    {"topic": "가상토픽 둘", "description": "둘의 설명"},
    {"topic": "가상토픽 셋", "description": "셋의 설명"},
]


def test_industry_text_by_hand() -> None:
    assert inputs.industry_text(INDUSTRY) == (
        "- 기준: SASB, 산업명: 가상 산업 하나, 설명: 가상 설명 {하나}\n"
        "- 기준: KSIC, 산업명: 가상 산업 둘, 설명: 가상 설명 둘\n"
    )
    assert inputs.industry_text([]) == ""


def test_resolve_subtopics_fills_missing_and_empty_topics_and_flags_unmatched_keys() -> None:
    given = {
        "가상 다른 토픽": [{"name": "가상 서브", "description": "가상"}],
        "가상토픽 둘": [],
        "가상토픽 하나": [{"name": "가상 서브 가", "description": "가상 서브 가의 설명"}],
    }
    before = copy.deepcopy(given)
    before_text = json.dumps(given, ensure_ascii=False)
    resolved, warnings = inputs.resolve_subtopics(given, TOPICS)
    assert list(resolved) == ["가상 다른 토픽", "가상토픽 둘", "가상토픽 하나", "가상토픽 셋"]
    assert resolved["가상토픽 둘"] == [{"name": "가상토픽 둘", "description": "둘의 설명"}]
    assert resolved["가상토픽 셋"] == [{"name": "가상토픽 셋", "description": "셋의 설명"}]
    assert resolved["가상토픽 하나"] is given["가상토픽 하나"]
    assert warnings == [
        ("subtopic_autofilled", "가상토픽 둘"),
        ("subtopic_autofilled", "가상토픽 셋"),
        ("subtopic_key_unmatched", "가상 다른 토픽"),
    ]
    assert given == before  # 받은 dict 는 그대로(코랩은 전역 dict 를 고쳐 쓴다)
    assert json.dumps(given, ensure_ascii=False) == before_text
    assert resolved is not given


def test_resolve_subtopics_from_nothing() -> None:
    resolved, warnings = inputs.resolve_subtopics({}, TOPICS[:1])
    assert resolved == {"가상토픽 하나": [{"name": "가상토픽 하나", "description": "하나의 설명"}]}
    assert warnings == [("subtopic_autofilled", "가상토픽 하나")]
