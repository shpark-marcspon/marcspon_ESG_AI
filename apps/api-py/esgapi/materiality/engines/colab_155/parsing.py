"""중대성평가 IRO 코랩 1부의 답 읽기 — 셀 8 extract_json_obj, utm 지움, 셀 20 키워드 파싱, 셀 22 키워드 글.

코랩과 같은 값을 낸다(약점 포함, MARC-ENT-425 ①):
- extract_json_obj: 첫 `{` 부터 문자열·이스케이프를 따라 괄호 균형 0 까지 잘라 json.loads. ValueError 문구 셋 그대로.
- strip_utm: `?utm_source=openai`·`&utm_source=openai` 두 글만 지운다(W7).
- parse_keywords: 셀 20 의 탐욕 정규식 `\\{[\\s\\S]*\\}`(첫 `{` 부터 마지막 `}` 까지) → json.loads → topic → keywords.
  같은 토픽이 둘이면 뒤 것의 키워드가 남는다(W6). 코랩과 다른 자리(발주서 처분 ⑩ 가): 코랩은 JSONDecodeError 만 잡고
  KeyError·TypeError·AttributeError 에는 실행이 멈춘다 — 여기는 그 전부와 keywords 가 list[str] 아님(topic 이 글 아님
  포함)을 KeywordsUnparsable 로 돌려준다. 흐름은 키워드 없이 컨트로버시 조사로 계속한다(코랩의 {} 와 같은 갈래).
- keyword_str: 토픽의 키워드를 「, 」로 잇고, 없으면 「(키워드 없음)」(셀 22 R/1083-1084). 토픽명이 키워드 답과 다르면
  조용히 「(키워드 없음)」이다(W6 — 경고는 계약 쪽이 단다).
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from .constants import UTM_SUFFIXES

NO_KEYWORDS: Final = "(키워드 없음)"
"""키워드가 없는 토픽의 keyword_str(셀 22 R/1084)."""


def extract_json_obj(text: str) -> dict[str, Any]:
    """셀 8 extract_json_obj(R/216-258). 빈 글·`{` 없음·균형 안 맞음은 ValueError(문구 그대로), JSON 이 아니면
    json.JSONDecodeError."""
    if not text or not text.strip():
        raise ValueError("Empty LLM output")

    s = text.strip()

    start = s.find("{")
    if start == -1:
        raise ValueError("No JSON object start '{' found")

    depth = 0
    in_str = False
    escape = False
    end = None

    for i in range(start, len(s)):
        ch = s[i]

        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end is None:
        raise ValueError("No complete JSON object found (unbalanced braces)")

    return json.loads(s[start : end + 1])


def strip_utm(text: str) -> str:
    """답 글에서 utm 두 글을 지운다(셀 17 R/795-796 · 셀 22 R/1096-1097). 다른 utm 꼴은 그대로(W7)."""
    for suffix in UTM_SUFFIXES:
        text = text.replace(suffix, "")
    return text


@dataclass(frozen=True)
class KeywordsParsed:
    """키워드 답을 읽었다. by_topic 은 코랩 topic_to_keywords 와 같은 dict(키 차례 = 첫 자리, 값 = 뒤 것)."""

    by_topic: dict[str, list[str]]
    duplicates: tuple[str, ...]
    """답에 두 번 이상 나온 토픽명(나온 차례, 겹침 없이)."""


@dataclass(frozen=True)
class KeywordsUnparsable:
    """키워드 답을 읽지 못했다. reason 은 갈래와 예외 이름(모델 글을 싣지 않는다)."""

    reason: str


def parse_keywords(text: str) -> KeywordsParsed | KeywordsUnparsable:
    """셀 20 의 파싱(R/918-954). 탐욕 정규식·뒤 것이 남음은 코랩 그대로, 실패 갈래는 처분 ⑩ 가."""
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return KeywordsUnparsable("JSON 블록({ ... })을 찾지 못했다")
    try:
        keyword_json = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        return KeywordsUnparsable(f"JSON 파싱 오류: {e}")
    by_topic: dict[str, list[str]] = {}
    duplicates: list[str] = []
    try:
        for item in keyword_json.get("topics", []):
            topic, keywords = item["topic"], item["keywords"]
            if not isinstance(topic, str) or not _is_str_list(keywords):
                return KeywordsUnparsable("topic 이 글이 아니거나 keywords 가 글 목록이 아니다")
            if topic in by_topic and topic not in duplicates:
                duplicates.append(topic)
            by_topic[topic] = keywords
    except Exception as e:  # 코랩은 여기서 멈춘다(KeyError·TypeError·AttributeError) — 처분 ⑩ 가
        return KeywordsUnparsable(f"키워드 꼴이 아니다: {type(e).__name__}")
    return KeywordsParsed(by_topic=by_topic, duplicates=tuple(duplicates))


def _is_str_list(value: object) -> bool:
    if not isinstance(value, list):
        return False
    return all(isinstance(x, str) for x in cast("list[object]", value))


def keyword_str(by_topic: Mapping[str, Sequence[str]], topic_name: str) -> str:
    """셀 22 R/1083-1084: 토픽의 키워드를 「, 」로 잇고, 없거나 비면 「(키워드 없음)」."""
    keywords = by_topic.get(topic_name, [])
    return ", ".join(keywords) if keywords else NO_KEYWORDS
