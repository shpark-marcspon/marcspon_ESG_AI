"""입력 꼴 → 엔진 인자, 코랩 답 묶음 ↔ 결과 꼴(Outcome), 경고 조립. 엔진을 import 하지 않는다(dict 만 — 축 시험).

- 엔진에 넘기는 dict 는 코랩 키 이름·차례로 새로 짓는다(industry: standard·industry_name·description, topics: topic·
  description). 받은 글은 고치지 않는다 — 프롬프트가 그 dict 의 repr 을 싣는다(발주서 §1-8).
- 묶음(engines/colab_155/outcomes.py 의 코랩 dict) → Outcome: parsed 가 있으면 done(받은 그대로 + 얇은 보기 items),
  없으면 failed(코랩 묶음의 원문·parse_error 그대로 + failure). 되돌리는 함수(bundle_of_*)는 그 역함수다 — 엑셀
  RAW_JSON 이 코랩 payload 를 되짓는 데 쓴다(발주서 §2-1 S7).
- items 는 코랩 셀 33 의 추출 규칙(R/1636-1648)으로 뽑은 원소 가운데 객체인 것만, 칸은 셀 33 표시 칸 차례(R/1651-1653).
  칸 값이 글이 아니면 json.dumps(ensure_ascii=False) — 엑셀은 코랩 지시대로 str()(다른 자리 표).
새 셈은 없다 — 코랩이 하던 견줌(셀 22 의 topic_name)과 셀 33 의 추출만 옮긴다.
"""

import copy
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Final, cast

from .shapes import (
    CONTROVERSY_ITEM_KEYS,
    REGULATION_ITEM_KEYS,
    RESULT_SHAPE,
    RESULT_SHAPE_V2,
    MaterialityContext,
    MaterialityContextItem,
    MaterialityControversyItem,
    MaterialityFailure,
    MaterialityFinancialRow,
    MaterialityImpactRow,
    MaterialityKeywordsDone,
    MaterialityKeywordsFailed,
    MaterialityOutcomeFailed,
    MaterialityOutcomeNotRun,
    MaterialityPart2Done,
    MaterialityPart2Failed,
    MaterialityPart2Settings,
    MaterialityPathwayRow,
    MaterialityRegulationItem,
    MaterialityResult,
    MaterialityResult2,
    MaterialitySettings,
    MaterialitySettings2,
    MaterialitySubtopicResult,
    MaterialityTopicResult,
    MaterialityWarning,
    MaterialityWarning2,
    Part2Input,
    Part2Phase,
    Part2Source,
    Part2Topic,
    WarningCode,
    WarningCode2,
    WarningPhase,
    Whitelist,
)

NO_KEYWORDS: Final = "(키워드 없음)"
"""키워드가 없는 토픽의 keyword_str(코랩 셀 22 R/1084 — engines/colab_155/parsing.NO_KEYWORDS 의 판별 복사, 시험이
견준다)."""
UNPARSABLE: Final = "모델의 답에서 JSON 객체를 읽지 못했다."
PART2_NOT_RUN: Final = "2부(IRO 분석)는 이 판에서 돌리지 않는다."

Outcome = dict[str, Any]
"""결과 꼴의 regulation·controversy 한 칸(MaterialityRegulation·MaterialityControversy 의 갈래 하나)."""


def engine_industry(received: Mapping[str, Any]) -> list[dict[str, str]]:
    """입력 industries → 코랩 셀 11 industry(키 standard·industry_name·description 차례)."""
    return [
        {"standard": i["standard"], "industry_name": i["industryName"], "description": i["description"]}
        for i in received["industries"]
    ]


def engine_topics(received: Mapping[str, Any]) -> list[dict[str, str]]:
    """입력 topics → 코랩 셀 11 topics(키 topic·description 차례)."""
    return [{"topic": t["topic"], "description": t["description"]} for t in received["topics"]]


def engine_subtopics(received: Mapping[str, Any]) -> dict[str, list[dict[str, str]]]:
    """입력 subtopicsByTopic → 코랩 셀 44 subtopics_by_topic(없으면 빈 dict — 코랩 셀 46 이 토픽마다 지어 넣는다)."""
    given = cast("Mapping[str, list[Mapping[str, str]]] | None", received["subtopicsByTopic"])
    if given is None:
        return {}
    return {k: [{"name": s["name"], "description": s["description"]} for s in v] for k, v in given.items()}


def warning(code: WarningCode, message: str, topic: str | None = None) -> MaterialityWarning:
    return {"code": code, "message": message, "topic": topic}


SUBTOPIC_MESSAGES: Final[Mapping[str, str]] = {
    "subtopic_autofilled": "서브토픽이 없어 토픽 설명으로 하나 지어 넣었다(코랩 셀 46).",
    "subtopic_key_unmatched": "서브토픽 키가 어느 토픽명과도 맞지 않아 쓰이지 않는다(코랩은 조용히 버린다).",
}


def subtopic_warnings(pairs: Sequence[tuple[str, str]]) -> list[MaterialityWarning]:
    """engines/colab_155/inputs.resolve_subtopics 의 경고 갈래 → 경고. 맞지 않는 키는 topic 이 아니라 글에 싣는다."""
    out: list[MaterialityWarning] = []
    for code, name in pairs:
        if code == "subtopic_autofilled":
            out.append(warning("subtopic_autofilled", SUBTOPIC_MESSAGES[code], name))
        else:
            out.append(warning("subtopic_key_unmatched", f"{SUBTOPIC_MESSAGES[code]} 키: {name}"))
    return out


def keywords_done(by_topic: Mapping[str, list[str]], raw: str) -> MaterialityKeywordsDone:
    """키워드 답을 읽었다(코랩 topic_to_keywords 의 차례 그대로)."""
    return {"status": "done", "byTopic": [{"topic": k, "keywords": list(v)} for k, v in by_topic.items()], "raw": raw}


def keywords_failed(
    raw: str | None, *, failure: MaterialityFailure | None, reason: str | None = None
) -> MaterialityKeywordsFailed:
    """키워드 답을 읽지 못했거나(raw 있음, failure None — unparsable, message 는 엔진 KeywordsUnparsable.reason) 호출이
    실패했다(raw null, failure 는 흐름이 core 갈래로 준다). failure 는 부르는 쪽이 매번 정한다(기본값 없음)."""
    if failure is None:
        if raw is None:
            raise ValueError("호출 실패에는 failure 를 준다")
        failure = {"kind": "unparsable", "message": reason or UNPARSABLE}
    return {"status": "failed", "raw": raw, "failure": failure}


def duplicate_keyword_warnings(duplicates: Sequence[str]) -> list[MaterialityWarning]:
    return [
        warning("keywords_duplicate_topic", "키워드 답에 같은 토픽이 둘 이상이라 뒤 것이 남았다(코랩대로).", topic)
        for topic in duplicates
    ]


def cell(value: Any) -> str | None:
    """항목 칸 하나: 없거나 null 이면 null, 글이면 그대로, 그 밖은 json.dumps(ensure_ascii=False)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def regulation_elements(root: Any) -> tuple[list[tuple[str | None, Any]], bool]:
    """셀 33 reg_items 규칙 2·3(R/1639-1640): results 가 dict 면 그 안의 list 값을 모두 펼침(원소마다 그 키), 아니면
    items 나 results 의 list. 돌려주는 bool 은 규칙 2·3 에 맞았는지(아니면 엑셀은 규칙 4 — 통째로 한 항목)."""
    if not isinstance(root, dict):
        return [], False
    d = cast("dict[str, Any]", root)
    results = d.get("results")
    if isinstance(results, dict):
        out: list[tuple[str | None, Any]] = []
        for key, value in cast("dict[str, Any]", results).items():
            if isinstance(value, list):
                out += [(key, element) for element in cast("list[Any]", value)]
        return out, True
    for key in ("items", "results"):
        value = d.get(key)
        if isinstance(value, list):
            return [(None, element) for element in cast("list[Any]", value)], True
    return [], False


def controversy_elements(root: Any) -> tuple[list[Any], bool]:
    """셀 33 cont_items 규칙 2·3(R/1646-1647): results > items 의 list, 아니면 items 의 list."""
    if not isinstance(root, dict):
        return [], False
    d = cast("dict[str, Any]", root)
    results = d.get("results")
    if isinstance(results, dict):
        inner = cast("dict[str, Any]", results).get("items")
        if isinstance(inner, list):
            return list(cast("list[Any]", inner)), True
    items = d.get("items")
    if isinstance(items, list):
        return list(cast("list[Any]", items)), True
    return [], False


def regulation_items(parsed: Mapping[str, Any]) -> tuple[list[MaterialityRegulationItem], int]:
    """parsed → 규제 항목 보기와 뺀(객체가 아닌) 원소 수."""
    items: list[MaterialityRegulationItem] = []
    skipped = 0
    for region, element in regulation_elements(parsed)[0]:
        if not isinstance(element, dict):
            skipped += 1
            continue
        e = cast("dict[str, Any]", element)
        row: dict[str, Any] = {key: cell(e.get(key)) for key in REGULATION_ITEM_KEYS}
        row["region"] = region
        items.append(cast("MaterialityRegulationItem", row))
    return items, skipped


def controversy_items(parsed: Mapping[str, Any]) -> tuple[list[MaterialityControversyItem], int]:
    """parsed → 컨트로버시 항목 보기와 뺀(객체가 아닌) 원소 수."""
    items: list[MaterialityControversyItem] = []
    skipped = 0
    for element in controversy_elements(parsed)[0]:
        if not isinstance(element, dict):
            skipped += 1
            continue
        e = cast("dict[str, Any]", element)
        row: dict[str, Any] = {key: cell(e.get(key)) for key in CONTROVERSY_ITEM_KEYS}
        row["region"] = None
        items.append(cast("MaterialityControversyItem", row))
    return items, skipped


def self_check(parsed: Mapping[str, Any]) -> dict[str, Any] | None:
    value = parsed.get("self_check")
    return cast("dict[str, Any]", value) if isinstance(value, dict) else None


def _skipped(topic: str, side: str, skipped: int) -> list[MaterialityWarning]:
    if not skipped:
        return []
    return [warning("items_skipped", f"{side} 항목 목록에서 객체가 아닌 원소 {skipped}개를 보기에서 뺐다.", topic)]


def regulation_shape_known(parsed: Mapping[str, Any]) -> bool:
    """규제 답의 항목 자리를 알아봤는가: results 가 dict 이고 그 안에 list 값이 하나라도 있거나, items·results 가 list.
    ({"results": {"KR": "none"}} 은 셀 33 규칙 2 에 들지만 항목 목록이 없다 — 모른다고 본다.)"""
    results = parsed.get("results")
    if isinstance(results, dict):
        return any(isinstance(v, list) for v in cast("dict[str, Any]", results).values())
    return regulation_elements(parsed)[1]


def _unrecognized(topic: str, side: str, known: bool) -> list[MaterialityWarning]:
    if known:
        return []
    return [
        warning(
            "items_unrecognized", f"{side} 답에서 항목 목록 자리를 찾지 못해 보기가 비었다(답은 parsed 그대로).", topic
        )
    ]


def _failed(raw: str | None, parse_error: str | None, failure: MaterialityFailure | None) -> MaterialityOutcomeFailed:
    return {
        "status": "failed",
        "raw": raw,
        "parseError": parse_error,
        "failure": failure if failure is not None else {"kind": "unparsable", "message": UNPARSABLE},
    }


def regulation_outcome(
    bundle: Mapping[str, Any], topic: str, *, failure: MaterialityFailure | None
) -> tuple[Outcome, list[MaterialityWarning]]:
    """셀 17 묶음 {"parsed", "raw", "parse_error"} → 결과 칸과 경고. 코랩 묶음에서는 호출 실패와 빈 답이 같다(W8) —
    그래서 failure 는 기본값 없이 부르는 쪽이 매번 정한다: 호출 실패면 core 갈래, 답을 받았으면 None(→ unparsable)."""
    parsed = bundle["parsed"]
    if parsed is None:
        return dict(_failed(bundle["raw"], bundle["parse_error"], failure)), []
    items, skipped = regulation_items(parsed)
    done = {
        "status": "done",
        "parsed": parsed,
        "items": items,
        "selfCheck": self_check(parsed),
        "topicNameMismatch": False,
    }
    return done, _skipped(topic, "규제", skipped) + _unrecognized(topic, "규제", regulation_shape_known(parsed))


def controversy_outcome(
    bundle: Mapping[str, Any], topic: str, *, failure: MaterialityFailure | None
) -> tuple[Outcome, list[MaterialityWarning]]:
    """셀 22 묶음 {"json", "raw_text", "parse_error"} → 결과 칸과 경고. 호출 실패(parse_error 「no_result」)에는 흐름이
    core 갈래의 failure 를 준다."""
    parsed = bundle["json"]
    if parsed is None:
        if bundle["parse_error"] == "no_result" and failure is None:
            raise ValueError("호출 실패(no_result)에는 failure 를 준다")
        return dict(_failed(bundle["raw_text"], bundle["parse_error"], failure)), []
    items, skipped = controversy_items(parsed)
    mismatch = parsed.get("topic_name") != topic  # 코랩 셀 22 R/1106 의 견줌
    done = {
        "status": "done",
        "parsed": parsed,
        "items": items,
        "selfCheck": self_check(parsed),
        "topicNameMismatch": mismatch,
    }
    warnings = _skipped(topic, "컨트로버시", skipped)
    warnings += _unrecognized(topic, "컨트로버시", controversy_elements(parsed)[1])
    if mismatch:
        warnings.append(warning("topic_name_mismatch", "컨트로버시 답의 topic_name 이 입력 토픽명과 다르다.", topic))
    return done, warnings


def not_run(message: str) -> MaterialityOutcomeNotRun:
    return {"status": "not_run", "message": message}


def topic_result(
    topic: Mapping[str, str], *, keyword_str: str | None, regulation: Outcome, controversy: Outcome
) -> MaterialityTopicResult:
    return cast(
        "MaterialityTopicResult",
        {
            "topic": topic["topic"],
            "description": topic["description"],
            "keywordStr": keyword_str,
            "regulation": regulation,
            "controversy": controversy,
        },
    )


def missing_keyword_warnings(topics: Sequence[MaterialityTopicResult]) -> list[MaterialityWarning]:
    """컨트로버시 조사에 「(키워드 없음)」이 간 토픽마다(코랩은 토픽명이 키워드 답과 다르면 조용히 그렇게 간다 — W6).
    글자 대조다 — 모델이 「(키워드 없음)」 하나만 키워드로 내도 keyword_str 가 같은 글이라 프롬프트가 바이트 같고 경고
    문장도 참(MARC-ISSUE-345 3, IRS1 D2)."""
    return [
        warning("keywords_missing_for_topic", "키워드가 없어 「(키워드 없음)」으로 조사했다.", t["topic"])
        for t in topics
        if t["keywordStr"] == NO_KEYWORDS
    ]


def build_result(
    received: Mapping[str, Any],
    *,
    whitelist: Whitelist,
    settings: MaterialitySettings,
    keywords: Mapping[str, Any],
    topics: Sequence[MaterialityTopicResult],
    warnings: Sequence[MaterialityWarning],
) -> MaterialityResult:
    """결과 꼴 한 건. warnings 뒤에 「(키워드 없음)」 경고를 토픽 차례로 붙인다. 꼴 검사는 부르는 쪽(RESULT_SHAPES)."""
    result = {
        "schemaVersion": "materiality.result@1",
        "company": dict(received["company"]),
        "scope": {
            "topicCount": len(received["topics"]),
            "sector": received["sector"],
            "whitelist": whitelist,
            "dateRange": received["dateRange"],
            "geoScope": received["geoScope"],
            "userLocation": received["userLocation"],
            "mainLanguage": received["mainLanguage"],
            "latestEventMode": received["latestEventMode"],
        },
        "settings": settings,
        "part1": {"keywords": dict(keywords), "topics": list(topics)},
        "part2": {"status": "not_run", "message": PART2_NOT_RUN},
        "warnings": [*warnings, *missing_keyword_warnings(topics)],
    }
    return cast("MaterialityResult", result)


def bundle_of_regulation(outcome: Mapping[str, Any]) -> dict[str, Any] | None:
    """regulation_outcome 의 역: 결과 칸 → 셀 17 묶음. not_run 이면 None(코랩에는 그 토픽의 칸이 없다)."""
    if outcome["status"] == "done":
        return {"parsed": outcome["parsed"], "raw": None, "parse_error": None}
    if outcome["status"] == "failed":
        return {"parsed": None, "raw": outcome["raw"], "parse_error": outcome["parseError"]}
    return None


def bundle_of_controversy(outcome: Mapping[str, Any]) -> dict[str, Any] | None:
    """controversy_outcome 의 역: 결과 칸 → 셀 22 묶음. not_run 이면 None."""
    if outcome["status"] == "done":
        return {"json": outcome["parsed"], "raw_text": None, "parse_error": None}
    if outcome["status"] == "failed":
        return {"json": None, "raw_text": outcome["raw"], "parse_error": outcome["parseError"]}
    return None


def websearch_payload(result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """코랩 셀 33 의 payload(R/1592-1595) — {"regulation_updates_by_topic", "controversies_by_topic"}, 토픽은 입력 차례,
    돌리지 않은 칸은 뺀다."""
    regulation: dict[str, Any] = {}
    controversy: dict[str, Any] = {}
    for t in result["part1"]["topics"]:
        reg = bundle_of_regulation(t["regulation"])
        con = bundle_of_controversy(t["controversy"])
        if reg is not None:
            regulation[t["topic"]] = reg
        if con is not None:
            controversy[t["topic"]] = con
    return {"regulation_updates_by_topic": regulation, "controversies_by_topic": controversy}


# ── 2부(materiality.result@2, 밴드 IR2a — MARC-ENT-425 ②) ─────────────────────────────────────────────────────
# 2부 입력(Part2Input)은 1부 결과 꼴 데이터에서 짓는다(코랩 셀 39 의 RAW_JSON A1 길 — A1 이 깨질 때의 고친 Shortlist
# 길은 다음 밴드). 토픽별 글은 셀 50 꼴: 결과 칸 → bundle_of_*(코랩 묶음) → json.dumps(ensure_ascii=False, indent=2),
# 돌리지 않은 칸 → 「제공된 … 정보 없음」. 셀 46·50 이 같은 글을 받는다(셀 46 의 .strip()·셀 51 의 마지막 토픽 규제
# 없이). 답 읽기(engines/colab_155/part2_parsing — 셀 50 정규화·셀 65 normalize)의 dict 를 결과 칸으로 옮기는 것과
# 경고·결과 조립만 한다. 엔진을 import 하지 않는다.

NO_REGULATION_TEXT: Final = "제공된 정책/규정/가이드라인 정보 없음"
"""규제 묶음이 없는 토픽의 글(코랩 셀 50 R/2615 — engines/colab_155/part2_render 의 판별 복사, 시험이 견준다)."""
NO_CONTROVERSY_TEXT: Final = "제공된 컨트로버시 정보 없음"
"""컨트로버시 묶음이 없는 토픽의 글(코랩 셀 50 R/2610 — 같은 판별 복사)."""
PART2_NOT_RUN_V2: Final = "2부(IRO 분석)를 돌리지 않았다."
PATHWAY_SKIPPED: Final = "재무 영향이 실패했거나 rows 가 0 이라 부르지 않았다(코랩 셀 55 의 [MISSING fin_impact])."
IMPACT_TYPES: Final = ("긍정", "부정")
"""셀 46 Step D 가 시킨 영향 유형."""
FINANCIAL_TYPES: Final = ("리스크", "기회")
"""셀 50 JSON 꼴의 impact_type."""
RISK_TYPES: Final = ("리스크-규제 및 법률", "리스크-평판", "리스크-기술", "리스크-시장")
"""셀 50 JSON 꼴의 risk_type(기회면 null)."""
PART2_PHASES: Final = ("impact", "financial", "pathway", "report")
"""1부 결과에서 옮기지 않는 경고 단계(2부를 다시 돌리면 새로 생긴다)."""
SUBTOPIC_CODES: Final = ("subtopic_autofilled", "subtopic_key_unmatched")
"""1부 결과에서 옮기지 않는 경고 — 2부 흐름이 서브토픽을 지어 넣으며 다시 단다."""


def warning2(
    code: WarningCode2,
    message: str,
    *,
    topic: str | None = None,
    phase: WarningPhase | None = None,
    subtopic: str | None = None,
) -> MaterialityWarning2:
    return {"code": code, "message": message, "topic": topic, "phase": phase, "subtopic": subtopic}


def as_warning2(
    given: Mapping[str, Any], *, phase: WarningPhase | None = None, subtopic: str | None = None
) -> MaterialityWarning2:
    """@1 경고 한 줄 → @2 꼴(phase·subtopic 을 더한다). @2 경고면 그대로 옮긴다."""
    if "phase" in given:
        return cast("MaterialityWarning2", dict(given))
    return warning2(given["code"], given["message"], topic=given["topic"], phase=phase, subtopic=subtopic)


def context_text(bundle: Mapping[str, Any] | None, kind: str) -> str:
    """코랩 셀 50 R/2604-2615: 묶음이 있으면 json.dumps(묶음, ensure_ascii=False, indent=2), 없으면
    「제공된 … 정보 없음」. kind 는 regulation·controversy(engines/colab_155/part2_render.context_text 의 판별 복사)."""
    if bundle:
        return json.dumps(bundle, ensure_ascii=False, indent=2)
    return NO_REGULATION_TEXT if kind == "regulation" else NO_CONTROVERSY_TEXT


def part2_input_from_result(
    received: Mapping[str, Any], result: Mapping[str, Any]
) -> tuple[Part2Input, list[MaterialityWarning2]]:
    """입력 꼴(materiality.input@1)과 1부 결과(@1 또는 @2, JSON 판) → 2부 엔진 입력과 옮겨 올 경고.

    토픽은 입력 차례, 글은 그 토픽의 결과 칸에서만(토픽 A 의 규제가 B 로 가지 않는다 — 셀 51 결함 ④ 없음). 1부 결과에
    입력 토픽이 없으면 ValueError(1부는 입력 토픽을 다 싣는다). 경고는 1부의 것만 옮긴다(@1 은 phase·subtopic null,
    서브토픽 경고와 2부 단계 경고는 뺀다 — 2부 흐름이 새로 단다)."""
    version = result["schemaVersion"]
    if version not in (RESULT_SHAPE, RESULT_SHAPE_V2):
        raise ValueError(f"1부 결과의 꼴이 아니다: {version!r}")
    by_name = {t["topic"]: t for t in result["part1"]["topics"]}
    topics: list[Part2Topic] = []
    for t in engine_topics(received):
        found = by_name.get(t["topic"])
        if found is None:
            raise ValueError(f"1부 결과에 입력 토픽이 없다: {t['topic']!r}")
        topics.append(
            {
                "topic": t["topic"],
                "description": t["description"],
                "regulationText": context_text(bundle_of_regulation(found["regulation"]), "regulation"),
                "controversyText": context_text(bundle_of_controversy(found["controversy"]), "controversy"),
            }
        )
    given = cast("list[dict[str, str]] | None", received["valueChain"])
    part2_input: Part2Input = {
        "company": received["company"]["name"],
        "industry": engine_industry(received),
        "valueChain": None if given is None else [dict(row) for row in given],
        "latestEventMode": received["latestEventMode"],
        "topics": topics,
        "subtopics": engine_subtopics(received),
        "source": "result",
    }
    warnings = [
        as_warning2(w)
        for w in result["warnings"]
        if w["code"] not in SUBTOPIC_CODES and w.get("phase") not in PART2_PHASES
    ]
    return part2_input, warnings


def value_chain_activities(part2_input: Mapping[str, Any]) -> list[str]:
    """입력 valueChain 의 business_activity 글(차례 그대로). 없으면 빈 목록."""
    rows = cast("list[Mapping[str, str]] | None", part2_input["valueChain"])
    return [] if rows is None else [row["business_activity"] for row in rows]


def _cells(value: Any) -> list[str]:
    """목록 칸 → 글 목록(목록이 아니면 빈 목록, null 원소는 뺌, 글이 아니면 json.dumps)."""
    if not isinstance(value, list):
        return []
    return [c for c in (cell(v) for v in cast("list[Any]", value)) if c is not None]


def _context_items(value: Any) -> tuple[list[MaterialityContextItem], int]:
    items: list[MaterialityContextItem] = []
    skipped = 0
    for element in cast("list[Any]", value) if isinstance(value, list) else []:
        if not isinstance(element, dict):
            skipped += 1
            continue
        e = cast("dict[str, Any]", element)
        items.append({"title": cell(e.get("title")), "summary": cell(e.get("summary")), "url": cell(e.get("url"))})
    return items, skipped


def context_view(value: Any) -> tuple[MaterialityContext, int]:
    """정규화된 context → 보기와 뺀(객체가 아닌) 원소 수. 객체가 아니면 빈 것(셀 50 정규화)."""
    ctx = cast("dict[str, Any]", value) if isinstance(value, dict) else {}
    regulations, a = _context_items(ctx.get("regulations"))
    controversies, b = _context_items(ctx.get("controversies"))
    return {"regulations": regulations, "controversies": controversies}, a + b


@dataclass
class _Notes:
    """한 칸(서브토픽 × 단계)의 경고 셈."""

    topic: str
    subtopic: str
    phase: Part2Phase
    skipped: int = 0
    unknown: int = 0
    unexpected: int = 0

    def _one(self, code: WarningCode2, message: str) -> MaterialityWarning2:
        return warning2(code, message, topic=self.topic, phase=self.phase, subtopic=self.subtopic)

    def warnings(self, dropped: int) -> list[MaterialityWarning2]:
        out: list[MaterialityWarning2] = []
        if dropped:
            out.append(self._one("rows_dropped", f"목록에서 객체가 아닌 원소 {dropped}개를 뺐다(코랩 셀 50)."))
        if self.skipped:
            out.append(self._one("items_skipped", f"맥락 목록에서 객체가 아닌 원소 {self.skipped}개를 보기에서 뺐다."))
        if self.unknown:
            message = f"입력 valueChain 에 없는 가치사슬 활동 {self.unknown}개(값은 그대로 둠)."
            out.append(self._one("value_chain_activity_unknown", message))
        if self.unexpected:
            message = f"영향 유형·리스크 종류가 시킨 값 밖인 행 {self.unexpected}개(값은 그대로 둠)."
            out.append(self._one("impact_type_unexpected", message))
        return out


def _activities(row: Mapping[str, Any], known: Sequence[str], notes: _Notes) -> list[str]:
    chosen = _cells(row.get("value_chain_activities"))
    notes.unknown += sum(1 for a in chosen if a not in known)
    return chosen


def _context(row: Mapping[str, Any], notes: _Notes) -> MaterialityContext:
    view, skipped = context_view(row.get("context"))
    notes.skipped += skipped
    return view


def impact_view(row: Mapping[str, Any], known: Sequence[str], notes: _Notes) -> MaterialityImpactRow:
    impact_type = cell(row.get("impact_type"))
    if impact_type not in IMPACT_TYPES:
        notes.unexpected += 1
    return {
        "impactDefinition": cell(row.get("impact_definition")),
        "impactType": impact_type,
        "valueChainActivities": _activities(row, known, notes),
        "context": _context(row, notes),
    }


def financial_view(row: Mapping[str, Any], known: Sequence[str], notes: _Notes) -> MaterialityFinancialRow:
    impact_type, risk_type = cell(row.get("impact_type")), cell(row.get("risk_type"))
    if impact_type not in FINANCIAL_TYPES or (risk_type is not None and risk_type not in RISK_TYPES):
        notes.unexpected += 1
    return {
        "impactDefinition": cell(row.get("impact_definition")),
        "impactType": impact_type,
        "riskType": risk_type,
        "valueChainActivities": _activities(row, known, notes),
        "context": _context(row, notes),
    }


def pathway_view(row: Mapping[str, Any], notes: _Notes) -> MaterialityPathwayRow:
    """engines/colab_155/part2_parsing.join_pathway 가 이은 행(모델 칸 + 재무 row 의 impact_type·risk_type·context)."""
    i = row.get("i")
    return {
        "i": i if isinstance(i, int) and not isinstance(i, bool) else None,
        "impactDefinition": cell(row.get("impact_definition")),
        "impactDriver": cell(row.get("impact_driver")),
        "businessImpact": cell(row.get("business_impact")),
        "financialImpact": cell(row.get("financial_impact")),
        "impactType": cell(row.get("impact_type")),
        "riskType": cell(row.get("risk_type")),
        "context": context_view(row.get("context"))[0],  # 이어 온 재무 context — 뺀 원소는 재무 칸에서 이미 셈(감독 ⑤)
    }


def _part2_failed(
    raw: str | None, read: Mapping[str, Any] | None, failure: MaterialityFailure | None
) -> MaterialityPart2Failed:
    if failure is None and raw is None:
        raise ValueError("답이 없는 실패(호출 실패)에는 failure 를 준다")
    return {
        "status": "failed",
        "raw": raw,
        "parseError": None if read is None else read["parseError"],
        "failure": failure if failure is not None else {"kind": "unparsable", "message": UNPARSABLE},
    }


def _readable(read: Mapping[str, Any] | None) -> bool:
    return read is not None and read["rows"] is not None


def impact_outcome(
    raw: str | None,
    read: Mapping[str, Any] | None,
    *,
    topic: str,
    subtopic: str,
    known_activities: Sequence[str],
    failure: MaterialityFailure | None,
) -> tuple[Outcome, list[MaterialityWarning2]]:
    """셀 46 답 → 결과 칸과 경고. raw 는 답 글(호출 실패면 None), read 는 엔진의 읽기({parsed, parseError, rows,
    dropped}, 답이 없으면 None). rows 가 있으면 done(잘렸어도 — 잘림 경고는 truncated_warnings), 없으면 failed:
    failure 는 기본값 없이 부르는 쪽이 매번 정한다(답을 받았으면 None → unparsable, 잘린 답을 못 읽었으면 truncated)."""
    if not _readable(read):
        return dict(_part2_failed(raw, read, failure)), []
    assert read is not None  # noqa: S101 — _readable 이 본다
    notes = _Notes(topic, subtopic, "impact")
    rows = [impact_view(r, known_activities, notes) for r in read["rows"]]
    done = {"status": "done", "parsed": read["parsed"], "rows": rows}
    return done, notes.warnings(read["dropped"])


def financial_outcome(
    raw: str | None,
    read: Mapping[str, Any] | None,
    *,
    topic: str,
    subtopic: str,
    known_activities: Sequence[str],
    failure: MaterialityFailure | None,
) -> tuple[Outcome, list[MaterialityWarning2]]:
    """셀 50 답 → 결과 칸과 경고(impact_outcome 과 같은 규칙)."""
    if not _readable(read):
        return dict(_part2_failed(raw, read, failure)), []
    assert read is not None  # noqa: S101 — _readable 이 본다
    notes = _Notes(topic, subtopic, "financial")
    rows = [financial_view(r, known_activities, notes) for r in read["rows"]]
    done = {"status": "done", "parsed": read["parsed"], "rows": rows}
    return done, notes.warnings(read["dropped"])


def pathway_outcome(
    raw: str | None,
    read: Mapping[str, Any] | None,
    *,
    topic: str,
    subtopic: str,
    skipped: bool,
    failure: MaterialityFailure | None,
) -> tuple[Outcome, list[MaterialityWarning2]]:
    """셀 55 답 → 결과 칸과 경고. skipped(재무가 실패·rows 0 이라 부르지 않음)면 not_run. read 는 엔진의 읽기에
    join_pathway 가 이은 rows 와 mismatch 를 더한 것."""
    if skipped:
        return dict(not_run(PATHWAY_SKIPPED)), []
    if not _readable(read):
        return dict(_part2_failed(raw, read, failure)), []
    assert read is not None  # noqa: S101 — _readable 이 본다
    notes = _Notes(topic, subtopic, "pathway")
    rows = [pathway_view(r, notes) for r in read["rows"]]
    warnings = notes.warnings(read["dropped"])
    if read["mismatch"]:
        warnings.append(
            warning2(
                "pathway_row_mismatch",
                "Pathway 의 행 수·영향 정의가 재무 rows 와 다르거나 i 로 잇지 못한 행이 있다.",
                topic=topic,
                phase="pathway",
                subtopic=subtopic,
            )
        )
    return {"status": "done", "parsed": read["parsed"], "rows": rows}, warnings


def truncated_warnings(calls: Sequence[Mapping[str, Any]]) -> list[MaterialityWarning2]:
    """호출 기록에서 출력 상한에 잘린 호출마다 answer_truncated(읽혔든 못 읽었든 — MARC-ISSUE-345 5). 기록 칸은 phase·
    topic·subtopic(없으면 null)·ending."""
    return [
        warning2(
            "answer_truncated",
            "답이 출력 상한에서 잘렸다(읽혔으면 그 부분으로 done, 못 읽었으면 failed·truncated).",
            topic=c["topic"],
            phase=c["phase"],
            subtopic=c.get("subtopic"),
        )
        for c in calls
        if c["ending"] == "truncated"
    ]


def subtopic_result(
    subtopic: Mapping[str, str], *, autofilled: bool, impact: Outcome, financial: Outcome, pathway: Outcome
) -> MaterialitySubtopicResult:
    return cast(
        "MaterialitySubtopicResult",
        {
            "name": subtopic["name"],
            "description": subtopic["description"],
            "autofilled": autofilled,
            "impact": impact,
            "financial": financial,
            "pathway": pathway,
        },
    )


def part2_done(
    source: Part2Source, topics: Sequence[tuple[Mapping[str, str], Sequence[MaterialitySubtopicResult]]]
) -> MaterialityPart2Done:
    """2부 결과(토픽은 입력 차례, 서브토픽은 지어 넣은 뒤의 차례)."""
    return {
        "status": "done",
        "input": {"source": source},
        "topics": [
            {"topic": t["topic"], "description": t["description"], "subtopics": list(subs)} for t, subs in topics
        ],
    }


def settings_v2(part1: Mapping[str, Any], part2: MaterialityPart2Settings) -> MaterialitySettings2:
    """1부 설정(@1 칸 그대로) + 2부 설정."""
    return cast("MaterialitySettings2", {**{k: part1[k] for k in MaterialitySettings.__annotations__}, "part2": part2})


def build_result_v2(
    received: Mapping[str, Any],
    *,
    part1_result: Mapping[str, Any],
    part2_settings: MaterialityPart2Settings,
    part2: Mapping[str, Any],
    warnings: Sequence[MaterialityWarning2],
) -> MaterialityResult2:
    """결과 꼴 @2 한 건. 1부 칸(scope·part1·settings 의 1부 칸)은 씨앗 결과(@1·@2) 그대로, company 는 입력 그대로.
    꼴 검사는 부르는 쪽(RESULT_SHAPES)."""
    result = {
        "schemaVersion": RESULT_SHAPE_V2,
        "company": dict(received["company"]),
        "scope": part1_result["scope"],
        "settings": settings_v2(part1_result["settings"], part2_settings),
        "part1": part1_result["part1"],
        "part2": part2,
        "warnings": list(warnings),
    }
    return cast("MaterialityResult2", result)


# ── 조사 기간 창(밴드 IR2b — MARC-ENT-425 ②) ─────────────────────────────────────────────────────────────────
# 1부 호출은 코랩 그대로 두고(기간은 키워드 호출에만 — 425 ①), 2부 입력을 지을 때만 1부 결과의 복사본에서 dateRange 밖
# 항목을 뺀다. 자리는 셀 33 의 추출 자리(regulation_elements·controversy_elements 와 같은 규칙)이고, 객체가 아닌 원소·
# 알아보지 못한 꼴·failed·not_run 칸은 그대로 둔다. 날짜를 못 읽은 항목은 남기고 경고한다(빼면 날짜를 비운 규제가 다
# 사라진다). 「오늘」은 부르는 쪽이 넘긴다 — 여기서 시계를 읽지 않는다.

DATE_RANGE: Final = re.compile(r"\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s*~\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|오늘까지)\s*")
"""입력 dateRange 의 문법(코랩 셀 11 date_range 꼴 「<YYYY-MM-DD>~오늘까지」 또는 명시한 끝 날짜). 전체가 맞아야
한다."""
UNTIL_TODAY: Final = "오늘까지"
ISO_DAY: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _iso_day(text: str) -> date | None:
    """YYYY-MM-DD 전체가 달력에 있는 날이면 그 날, 아니면 None."""
    if ISO_DAY.fullmatch(text) is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_date_range(text: object, today: date) -> tuple[date, date] | None:
    """dateRange 글 → (시작, 끝). 「오늘까지」면 끝은 today. 문법 밖·달력에 없는 날·시작 > 끝이면 None(거부는
    흐름이)."""
    if not isinstance(text, str):
        return None
    matched = DATE_RANGE.fullmatch(text)
    if matched is None:
        return None
    start = _iso_day(matched.group(1))
    end = today if matched.group(2) == UNTIL_TODAY else _iso_day(matched.group(2))
    if start is None or end is None or start > end:
        return None
    return start, end


def item_date(value: object) -> date | None:
    """항목 날짜 칸 하나: 글이고 앞뒤 공백을 뺀 전체가 YYYY-MM-DD 달력 날이면 그 날, 아니면 None(2024-03·ISO 시각도)."""
    if not isinstance(value, str):
        return None
    return _iso_day(value.strip())


def regulation_item_date(element: Mapping[str, Any]) -> date | None:
    """규제 항목의 날짜: publish_date, 비었거나 못 읽으면 event_date."""
    published = item_date(element.get("publish_date"))
    return published if published is not None else item_date(element.get("event_date"))


def controversy_item_date(element: Mapping[str, Any]) -> date | None:
    return item_date(element.get("date"))


@dataclass
class _Tally:
    """한 토픽·한 쪽에서 뺀 항목 수와 날짜를 못 읽어 남긴 항목 수."""

    dropped: int = 0
    unreadable: int = 0


def _kept(elements: list[Any], phase: str, start: date, end: date, tally: _Tally) -> list[Any]:
    date_of = regulation_item_date if phase == "regulation" else controversy_item_date
    kept: list[Any] = []
    for element in elements:
        if not isinstance(element, dict):
            kept.append(element)
            continue
        day = date_of(cast("dict[str, Any]", element))
        if day is None:
            tally.unreadable += 1
            kept.append(element)
        elif start <= day <= end:
            kept.append(element)
        else:
            tally.dropped += 1
    return kept


def _regulation_in_window(parsed: dict[str, Any], start: date, end: date, tally: _Tally) -> None:
    """셀 33 reg_items 의 자리(regulation_elements 와 같은 차례)에서 제자리로 뺀다 — 복사본에만 부른다."""
    results = parsed.get("results")
    if isinstance(results, dict):
        inner = cast("dict[str, Any]", results)
        for key, value in inner.items():
            if isinstance(value, list):
                inner[key] = _kept(cast("list[Any]", value), "regulation", start, end, tally)
        return
    for key in ("items", "results"):
        value = parsed.get(key)
        if isinstance(value, list):
            parsed[key] = _kept(cast("list[Any]", value), "regulation", start, end, tally)
            return


def _controversy_in_window(parsed: dict[str, Any], start: date, end: date, tally: _Tally) -> None:
    """셀 33 cont_items 의 자리(controversy_elements 와 같은 차례)에서 제자리로 뺀다 — 복사본에만 부른다."""
    results = parsed.get("results")
    if isinstance(results, dict):
        inner = cast("dict[str, Any]", results)
        if isinstance(inner.get("items"), list):
            inner["items"] = _kept(cast("list[Any]", inner["items"]), "controversy", start, end, tally)
            return
    if isinstance(parsed.get("items"), list):
        parsed["items"] = _kept(cast("list[Any]", parsed["items"]), "controversy", start, end, tally)


def _window_warnings(
    topic: str, phase: WarningPhase, side: str, tally: _Tally, start: date, end: date
) -> list[MaterialityWarning2]:
    out: list[MaterialityWarning2] = []
    if tally.dropped:
        out.append(
            warning2(
                "items_out_of_range",
                f"{side} 항목 {tally.dropped}건 뺌(기간 {start.isoformat()}~{end.isoformat()}) — 2부 입력에서만, "
                "part1 은 그대로.",
                topic=topic,
                phase=phase,
            )
        )
    if tally.unreadable:
        out.append(
            warning2(
                "item_date_unreadable",
                f"{side} 항목 {tally.unreadable}건 날짜 못 읽어 남김.",
                topic=topic,
                phase=phase,
            )
        )
    return out


def part1_in_window(
    result: Mapping[str, Any], start: date, end: date
) -> tuple[dict[str, Any], list[MaterialityWarning2]]:
    """1부 결과(@1·@2 JSON 판) → done 칸 parsed 에서 기간 밖 항목을 뺀 깊은 복사본과 경고(토픽 차례, 규제 → 컨트로버시,
    뺌 → 못 읽음). 받은 결과는 고치지 않는다. items(보기)는 고치지 않는다 — 2부 입력은 parsed 만 읽는다(bundle_of_*)."""
    windowed = copy.deepcopy(dict(result))
    warnings: list[MaterialityWarning2] = []
    for t in cast("list[dict[str, Any]]", windowed["part1"]["topics"]):
        for phase, side, cut in (
            ("regulation", "규제", _regulation_in_window),
            ("controversy", "컨트로버시", _controversy_in_window),
        ):
            outcome = cast("dict[str, Any]", t[phase])
            if outcome["status"] != "done" or not isinstance(outcome["parsed"], dict):
                continue
            tally = _Tally()
            parsed = copy.deepcopy(cast("dict[str, Any]", outcome["parsed"]))  # 칸끼리 같은 객체를 나눠 써도 한 칸만
            outcome["parsed"] = parsed
            cut(parsed, start, end, tally)
            warnings += _window_warnings(t["topic"], cast("WarningPhase", phase), side, tally, start, end)
    return windowed, warnings
