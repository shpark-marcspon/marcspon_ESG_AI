"""순수 층의 값 → 나갈 JSON 의 dict. 키는 camelCase, 차례는 esg-lab 의 TS 가 내던 것과 같다.

「없음」을 적는 법은 TS 그대로다: TS 가 `null` 을 내는 자리는 None(늘 있는 키), TS 가 키를 안 내는 자리
(`evidence.lexical`, `MemoryEntry.label`, 후보의 `path`)는 키가 없다.
"""

from esgapi.inventory.engines.scope3.llm_first_1.calc import (
    CalcResult,
    Computed,
    CurrencyAdjustment,
    InvalidNumber,
    MissingAmount,
    MissingQuantity,
    NeedsCurrencyAdjustment,
    NeedsDistance,
    NotCalculated,
    UnitMismatch,
    UnsupportedFactorUnit,
)
from esgapi.inventory.engines.scope3.llm_first_1.llm_steps import (
    Classification,
    LlmFailure,
    LlmUsage,
    candidate_for_prompt,
)
from esgapi.inventory.engines.scope3.llm_first_1.memory import MemoryEntry
from esgapi.inventory.engines.scope3.llm_first_1.pipeline import (
    BasisTrace,
    CandidateStats,
    ClassificationFailed,
    GroupDecision,
    MemoryCategoryMismatch,
    MemoryFactorExcluded,
    MemoryFactorMissing,
    NoCandidates,
    NoSuitableFactor,
    RecommendationFailed,
    Recommended,
    ShortlistTrace,
    UnsupportedCategory,
)
from esgapi.inventory.engines.scope3.llm_first_1.types import Factor, FactorPick


def pick_to_dict(pick: FactorPick) -> dict[str, object]:
    return {"factorId": pick.factor_id, "reason": pick.reason, "confidence": pick.confidence}


def classification_to_dict(classification: Classification) -> dict[str, object]:
    return {
        "category": classification.category,
        "keywords": list(classification.keywords),
        "confidence": classification.confidence,
        "reason": classification.reason,
    }


def failure_to_dict(failure: LlmFailure) -> dict[str, object]:
    return {"kind": failure.kind, "detail": failure.detail}


def memory_entry_to_dict(entry: MemoryEntry) -> dict[str, object]:
    out: dict[str, object] = {
        "key": entry.key,
        "category": entry.category,
        "factorId": entry.factor_id,
        "confirmedBy": entry.confirmed_by,
        "confirmedAt": entry.confirmed_at,
    }
    if entry.label is not None:
        out["label"] = entry.label
    return out


def basis_to_dict(basis: BasisTrace) -> dict[str, object]:
    return {"used": basis.used, "fellBack": basis.fell_back, "fallbackReason": basis.fallback_reason}


def stats_to_dict(stats: CandidateStats) -> dict[str, object]:
    return {
        "total": stats.total,
        "shown": stats.shown,
        "lexicalMatches": stats.lexical_matches,
        "method": stats.method,
    }


def trace_to_dict(trace: ShortlistTrace) -> dict[str, object]:
    """`failure` 는 늘 null 이다: 추리지 못하는 갈래(임베딩)는 옮기지 않았다. TS 의 결과 파일과 꼴을 맞추려고 둔다."""
    return {
        "basis": trace.basis,
        "method": trace.method,
        "total": trace.total,
        "shownIds": list(trace.shown_ids),
        "evidence": [entry.to_json() for entry in trace.evidence],
        "failure": None,
    }


def decision_to_dict(decision: GroupDecision) -> dict[str, object]:
    match decision:
        case Recommended():
            classification = decision.classification
            entry = decision.memory_entry
            stats = decision.candidates
            return {
                "status": decision.status,
                "source": decision.source,
                "category": decision.category,
                "picks": [pick_to_dict(pick) for pick in decision.picks],
                "basis": basis_to_dict(decision.basis),
                "classification": None if classification is None else classification_to_dict(classification),
                "memoryEntry": None if entry is None else memory_entry_to_dict(entry),
                "candidates": None if stats is None else stats_to_dict(stats),
            }
        case MemoryFactorMissing():
            return {
                "status": decision.status,
                "source": decision.source,
                "memoryEntry": memory_entry_to_dict(decision.memory_entry),
            }
        case MemoryCategoryMismatch():
            return {
                "status": decision.status,
                "source": decision.source,
                "memoryEntry": memory_entry_to_dict(decision.memory_entry),
                "factorCategories": list(decision.factor_categories),
            }
        case MemoryFactorExcluded():
            return {
                "status": decision.status,
                "source": decision.source,
                "memoryEntry": memory_entry_to_dict(decision.memory_entry),
                "licenseStatus": decision.license_status,
            }
        case ClassificationFailed():
            return {"status": decision.status, "source": decision.source, "llm": failure_to_dict(decision.llm)}
        case UnsupportedCategory():
            return {
                "status": decision.status,
                "source": decision.source,
                "classification": classification_to_dict(decision.classification),
            }
        case NoCandidates() | NoSuitableFactor():
            return {
                "status": decision.status,
                "source": decision.source,
                "category": decision.category,
                "classification": classification_to_dict(decision.classification),
                "physical": decision.physical,
            }
        case RecommendationFailed():
            return {
                "status": decision.status,
                "source": decision.source,
                "category": decision.category,
                "classification": classification_to_dict(decision.classification),
                "basis": decision.basis,
                "llm": failure_to_dict(decision.llm),
            }


def adjustment_to_dict(adjustment: CurrencyAdjustment) -> dict[str, object]:
    source = adjustment.source
    return {
        "currency": adjustment.currency,
        "targetCurrency": adjustment.target_currency,
        "targetPriceYear": adjustment.target_price_year,
        "multiplier": adjustment.multiplier,
        "synthetic": adjustment.synthetic,
        "source": None if source is None else {"url": source.url, "checkedOn": source.checked_on},
    }


def calc_to_dict(result: CalcResult) -> dict[str, object]:
    match result:
        case Computed():
            adjustment = result.adjustment
            return {
                "status": result.status,
                "co2e": result.co2e,
                "unit": result.unit,
                "factorId": result.factor_id,
                "factorValueRaw": result.factor_value_raw,
                "factorUnit": result.factor_unit,
                "activityAmount": result.activity_amount,
                "formula": result.formula,
                "adjustment": None if adjustment is None else adjustment_to_dict(adjustment),
                "synthetic": result.synthetic,
            }
        case NeedsDistance() | MissingQuantity() | MissingAmount():
            return {"status": result.status, "factorId": result.factor_id}
        case NeedsCurrencyAdjustment():
            return {
                "status": result.status,
                "factorId": result.factor_id,
                "currency": result.currency,
                "targetCurrency": result.target_currency,
                "targetPriceYear": result.target_price_year,
            }
        case InvalidNumber():
            return {"status": result.status, "factorId": result.factor_id, "field": result.field}
        case UnitMismatch():
            return {
                "status": result.status,
                "factorId": result.factor_id,
                "rowUnit": result.row_unit,
                "factorUnit": result.factor_unit,
            }
        case UnsupportedFactorUnit():
            return {"status": result.status, "factorId": result.factor_id, "factorUnit": result.factor_unit}
        case NotCalculated():
            return {"status": result.status, "reason": result.reason}


def usage_to_dict(usage: LlmUsage) -> dict[str, object]:
    return {
        "calls": usage.calls,
        "attempts": usage.attempts,
        "costUsd": usage.cost_usd,
        "byPrompt": {
            prompt: {"calls": slot.calls, "attempts": slot.attempts, "costUsd": slot.cost_usd}
            for prompt, slot in usage.by_prompt.items()
        },
    }


def candidate_to_dict(factor: Factor) -> dict[str, object]:
    """추린 후보 하나를 화면에 보일 꼴. 프롬프트에 가는 칸(값 없음)에 이용 조건 상태를 붙였다. 계수 값은 싣지 않는다."""
    return {**candidate_for_prompt(factor), "licenseStatus": factor.license_status}
