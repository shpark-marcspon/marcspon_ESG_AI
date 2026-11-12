"""중대성평가 IRO 코랩의 입력 손질 — 셀 11 industry_text, 셀 46 의 서브토픽 지어 넣기(R/2285-2290).

코랩과 다른 자리(발주서 처분 ⑦ 가): 코랩은 전역 subtopics_by_topic 을 고쳐 쓰고 print 로 알린다 — 여기는 받은 dict 를
고치지 않고 새 dict 와 경고 갈래를 돌려준다. 어느 토픽명과도 맞지 않는 서브토픽 키는 코랩이 조용히 버리는(쓰지 않는)
것 그대로 새 dict 에 남기고 경고만 단다. 경고의 글은 계약 쪽(contracts/wire.py)이 짓는다.
"""

from collections.abc import Mapping, Sequence
from typing import Literal

SubtopicWarning = tuple[Literal["subtopic_autofilled", "subtopic_key_unmatched"], str]
"""(갈래, 토픽명 또는 맞지 않는 서브토픽 키)."""


def industry_text(industry: Sequence[Mapping[str, str]]) -> str:
    """셀 11 R/369-371: 산업마다 `- 기준: …, 산업명: …, 설명: …` 한 줄(끝 줄바꿈 포함)을 잇는다."""
    text = ""
    for i in industry:
        text += f"- 기준: {i['standard']}, 산업명: {i['industry_name']}, 설명: {i['description']}\n"
    return text


def resolve_subtopics(
    subtopics_by_topic: Mapping[str, list[dict[str, str]]], topics: Sequence[Mapping[str, str]]
) -> tuple[dict[str, list[dict[str, str]]], list[SubtopicWarning]]:
    """셀 46 R/2285-2290: 토픽마다 서브토픽이 없거나 비면 토픽 설명으로 하나 지어 넣는다(이름 = 토픽명). 받은 dict 의
    키 차례를 따르고 지어 넣은 것은 뒤에 붙는다(코랩이 전역 dict 에 써 넣은 차례와 같다). 받은 dict 는 고치지 않는다."""
    resolved = dict(subtopics_by_topic)
    warnings: list[SubtopicWarning] = []
    names = [t["topic"] for t in topics]
    for topic_each in names:
        subtopics = resolved.get(topic_each, [])
        if not subtopics:
            topic_desc = next((t.get("description", "") for t in topics if t.get("topic") == topic_each), "")
            resolved[topic_each] = [{"name": topic_each, "description": topic_desc}]
            warnings.append(("subtopic_autofilled", topic_each))
    for key in subtopics_by_topic:
        if key not in names:
            warnings.append(("subtopic_key_unmatched", key))
    return resolved, warnings
