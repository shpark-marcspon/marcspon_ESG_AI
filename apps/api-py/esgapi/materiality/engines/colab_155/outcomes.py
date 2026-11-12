"""중대성평가 IRO 코랩 1부의 답 묶음 — 답 글(또는 호출 실패) → 코랩이 토픽마다 저장하던 dict.

셀 17 regulation_updates_by_topic[토픽] = {"parsed", "raw", "parse_error"}, 셀 22
controversies_by_topic[토픽] = {"json", "raw_text", "parse_error"} 를 키 차례까지 그대로 짓는다.
2부·엑셀 RAW_JSON 이 이 꼴을 읽는다.
약점 그대로(MARC-ENT-425 ①):
- 규제는 호출 실패(코랩 None)와 빈 답이 같은 갈래 — 둘 다 빈 글이 되어 「Empty LLM output」(W8).
  parse_error 는 str(예외).
- 컨트로버시는 호출 실패면 {"json": None, "raw_text": "", "parse_error": "no_result"}, parse_error 는 repr(예외)(W8).
- 컨트로버시만 답의 topic_name 이 다르면 parsed 에 topic_name_expected 를 더한다(W9).
"""

from typing import Any

from .parsing import extract_json_obj, strip_utm


def regulation_bundle(text: str | None) -> dict[str, Any]:
    """셀 17 R/789·R/793-809. text 는 모델의 답 글, 호출이 실패했으면 None."""
    specific_text = text if text else ""
    if specific_text:
        specific_text = strip_utm(specific_text)
    parse_error = None
    try:
        parsed = extract_json_obj(specific_text)
    except Exception as e:  # 코랩대로 무엇이든 잡아 글로 남긴다
        parsed = None
        parse_error = str(e)
    return {
        "parsed": parsed,
        "raw": specific_text if parsed is None else None,
        "parse_error": parse_error if parsed is None else None,
    }


def controversy_bundle(text: str | None, topic_name: str) -> dict[str, Any]:
    """셀 22 R/1093-1131. text 는 모델의 답 글, 호출이 실패했으면 None."""
    if text is None:
        return {"json": None, "raw_text": "", "parse_error": "no_result"}
    text = strip_utm(text or "")
    parsed = None
    parse_error = None
    try:
        parsed = extract_json_obj(text)
        if parsed.get("topic_name") != topic_name:
            parsed["topic_name_expected"] = topic_name
    except Exception as e:  # 코랩대로 무엇이든 잡아 repr 로 남긴다
        parse_error = repr(e)
    return {"json": parsed, "raw_text": text if parsed is None else None, "parse_error": parse_error}
