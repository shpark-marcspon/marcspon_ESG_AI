"""엔진 한 번의 결과(`TranslationRun` 을 `dataclasses.asdict` 한 dict) → 결과 꼴 translation.result@1 dict(밴드 TR1a).

엔진(engines/colab_158)과 도구(tools)를 import 하지 않는다 — dict 만 받는다(엔진은 계약을 모르고 계약은 엔진을 모른다,
tests/test_axes.py). 새 셈은 없다: 칸 이름을 camelCase 로, 쪽 번호 열쇠를 글자로(JSON 객체), 튜플을 목록으로 옮길
뿐이다. 실행 설정(경로·프롬프트 id·엔진 상수)은 부르는 쪽(흐름)이 넘긴다 — 그 값의 정본은 다리와 엔진이다.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Final

from esgapi.translation.contracts.shapes import RESULT_SHAPE

ENGINE: Final = "colab_158"


def _qa(log: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if log is None:
        return None
    return {
        "ran": log["ran"],
        "reason": log["reason"],
        "qualityScore": log["quality_score"],
        "scoreDefaulted": log["score_defaulted"],
        "hasCriticalIssue": log["has_critical_issue"],
        "applied": log["applied"],
        "issues": log["issues"],
    }


def _page(page: Mapping[str, Any]) -> dict[str, Any]:
    high, medium, low = page["counts"]
    review: dict[str, Any] = {
        "status": page["status"],
        "issues": [
            {
                "issueType": i["issue_type"],
                "severity": i["severity"],
                "originalSpan": i["original_span"],
                "suggestion": i["suggestion"],
                "reason": i["reason"],
                "source": i["source"],
            }
            for i in page["issues"]
        ],
        "counts": {"high": high, "medium": medium, "low": low},
        "message": page["message"],
    }
    return {
        "pageNum": page["page_num"],
        "translated": page["translated"],
        "bilingual": page["bilingual"],
        "review": review,
    }


def _autofix(run: Mapping[str, Any]) -> dict[str, Any]:
    stop = run["stop"]
    return {
        "status": run["status"],
        "pages": [
            {
                "pageNum": p["page_num"],
                "changed": p["changed"],
                "reason": p["reason"],
                "issueCount": p["issue_count"],
                "spanReplacements": [
                    {"issueType": s["issue_type"], "originalSpan": s["original_span"], "suggestion": s["suggestion"]}
                    for s in p["span_replacements"]
                ],
                "koreanRepairRounds": [
                    {"changed": r["changed"], "remainingKorean": list(r["remaining_korean"]), "reason": r["reason"]}
                    for r in p["korean_repair_rounds"]
                ],
                "remainingKoreanAfter": list(p["remaining_korean_after"]),
            }
            for p in run["pages"]
        ],
        "translatedText": run["translated_text"],
        "bilingualText": run["bilingual_text"],
        "stop": None
        if stop is None
        else {
            "kind": stop["kind"],
            "pageNum": stop["page_num"],
            "remainingKorean": list(stop["remaining_korean"]),
            "message": stop["message"],
        },
        "notRunReason": run["not_run_reason"],
    }


def _variant(v: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "label": v["label"],
        "translatedText": v["translated_text"],
        "bilingualText": v["bilingual_text"],
        "fragments": [
            {
                "pageNum": f["page_num"],
                "status": f["status"],
                "error": f["error"],
                "editorialQa": _qa(f["editorial_qa"]),
                "remainingKorean": list(f["remaining_korean"]),
            }
            for f in v["fragments"]
        ],
        "pages": [_page(p) for p in v["pages"]],
        "glossaryCheck": [
            {"pageNum": page_num, "termKo": ko, "termEn": en, "sourceCount": count}
            for page_num, ko, en, count in v["glossary_misses"]
        ],
        "autofix": _autofix(v["autofix"]),
    }


def to_result(
    run: Mapping[str, Any],
    *,
    routes: Mapping[str, str],
    prompt_ids: Sequence[str],
    constants: Mapping[str, int],
    source_sha256: str,
    retry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """`run` = `dataclasses.asdict(TranslationRun)`(흐름이 실행 전에 멈추면 같은 꼴의 dict — 거절 kind 가 엔진 밖).
    routes = {"translate": …, "review": …}(다리의 경로), constants = EngineConstants 의 칸(엔진 상수),
    source_sha256 = 원문 글의 sha256(흐름이 셈), retry = RetryInfo 꼴 또는 None. 거절이면 status rejected·variants 빈
    목록."""
    rejection = run["rejection"]
    return {
        "schemaVersion": RESULT_SHAPE,
        "status": "done" if rejection is None else "rejected",
        "rejection": None
        if rejection is None
        else {
            "kind": rejection["kind"],
            "message": rejection["message"],
            "pageCount": rejection["page_count"],
            "limit": rejection["limit"],
        },
        "settings": {
            "part": run["part"],
            "variants": list(run["variant_labels"]),
            "routes": {"translate": routes["translate"], "review": routes["review"]},
            "promptIds": list(prompt_ids),
            "engine": ENGINE,
            "constants": dict(constants),
            "retry": None if retry is None else dict(retry),
        },
        "document": {
            "pageNumbers": list(run["page_numbers"]),
            "duplicatePages": {str(k): v for k, v in run["duplicate_pages"].items()},
            "sourceSha256": source_sha256,
        },
        "variants": [_variant(v) for v in run["variants"]],
        "warnings": [
            {"code": w["code"], "message": w["message"], "pageNum": w["page_num"], "variant": w["variant"]}
            for w in run["warnings"]
        ],
    }
