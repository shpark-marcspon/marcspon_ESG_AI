"""Scope 3 의 LLM 단계·파이프라인 테스트(커밋 경계 ③)가 같이 쓰는 것. ★ 전부 테스트 전용이다(제품 코드에 두지 않는다).

- 모의 공급사 하나로 세운 `LlmClient`(가상 모델 파일, 경로 `mock`)와 파이프라인 옵션
- 규칙 응답기: esg-lab `ts/scope3/src/eval/mockHeuristic.ts`(53줄)의 옮김. 정답을 보지 않고 프롬프트에 든 글자만으로
  답한다. 도구가 끝까지 도는지 보려는 것이고 이 응답으로 나온 정확도는 성능과 무관하다
- 예제 폴더의 기억·보정 계수 로더, TS CLI 의 `rowDump` 꼴 만들기
"""

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import (
    Completed,
    InvokeOptions,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    Tags,
    TextPart,
)
from esgapi.inventory.engines.scope3.llm_first_1.calc import AdjustmentSource, CurrencyAdjustment
from esgapi.inventory.engines.scope3.llm_first_1.llm_steps import MAX_PICKS
from esgapi.inventory.engines.scope3.llm_first_1.memory import InMemoryMappingMemory, MappingMemory, MemoryEntry
from esgapi.inventory.engines.scope3.llm_first_1.normalize import group_key
from esgapi.inventory.engines.scope3.llm_first_1.pipeline import (
    DEFAULT_SHORTLIST_SIZE,
    ClassificationFailed,
    GroupDecision,
    MemoryCategoryMismatch,
    MemoryFactorExcluded,
    MemoryFactorMissing,
    PipelineOptions,
    PipelineResult,
    RecommendationFailed,
    Recommended,
    UnsupportedCategory,
)
from esgapi.inventory.engines.scope3.llm_first_1.ports import FactorCatalog
from esgapi.inventory.engines.scope3.llm_first_1.serialize import basis_to_dict, failure_to_dict, trace_to_dict
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import Shortlister, default_shortlister
from esgapi.inventory.engines.scope3.llm_first_1.types import LicenseStatus, SupportedCategory
from esgapi.inventory.tests.scope3_catalog_support import Example
from esgapi.inventory.tools.jsrepr import js_json

TAGS: Final = Tags(tenant="tenant-synthetic", module="inventory")
ROUTE: Final = "mock"


def classification(category: int | str, keywords: Sequence[str] = ()) -> str:
    """분류 응답의 글자(가상)."""
    return js_json(
        {
            "category": category,
            "keywords_en": list(keywords),
            "confidence": "medium",
            "reason": "테스트 응답 (synthetic)",
        }
    )


def recommendation(ids: Sequence[str]) -> str:
    """추천 응답의 글자(가상)."""
    picks = [{"factor_id": item, "reason": "테스트 응답 (synthetic)", "confidence": "medium"} for item in ids]
    return js_json({"picks": picks, "none_suitable": len(ids) == 0})


def user_text(request: ProviderRequest) -> str:
    return "\n".join(part.text if isinstance(part, TextPart) else "" for part in request.user)


def user_texts(mock: MockProvider) -> list[str]:
    """모의 공급사가 받은 요청의 사용자 글자."""
    return [user_text(call) for call in mock.calls]


# ── 규칙 응답기(테스트 전용) ──

_RULES: Final[tuple[tuple[int, tuple[str, ...]], ...]] = (
    (7, ("통근", "출퇴근", "셔틀", "재택")),
    (6, ("출장", "항공", "호텔", "숙박", "ktx", "택시", "렌터카")),
    (2, ("설비", "장비", "기계", "서버", "노트북", "차량 구매", "공사")),
)


def _field(text: str, label: str) -> Any:
    for line in text.split("\n"):
        if line.startswith(f"{label}: "):
            return json.loads(line[len(label) + 2 :])
    raise ValueError(f"모의 응답기: 프롬프트에 {label} 줄이 없다")


def heuristic_reply(request: ProviderRequest) -> ProviderResponse:
    """규칙 기반 모의 응답(synthetic). 분류는 낱말 규칙, 추천은 추린 후보의 앞 세 개다."""
    text = user_text(request)
    name = None if request.json_schema is None else request.json_schema.name
    if name == "scope3_classification":
        item = _field(text, "ITEM_JSON")
        lowered = str(item["item_name"]).lower()
        matched = next((category for category, words in _RULES if any(word in lowered for word in words)), 1)
        category = 4 if item["transport"] is not None else matched
        reply: dict[str, object] = {
            "category": category,
            "keywords_en": [],
            "confidence": "low",
            "reason": "모의 응답 (synthetic): 낱말 규칙으로 분류",
        }
        return Completed(text=js_json(reply), usage=SYNTHETIC_USAGE)
    if name == "scope3_recommendation":
        candidates = _field(text, "CANDIDATES_JSON")
        picks = [
            {"factor_id": candidate["id"], "reason": "모의 응답 (synthetic): 추린 목록의 앞 순서", "confidence": "low"}
            for candidate in candidates[:MAX_PICKS]
        ]
        return Completed(text=js_json({"picks": picks, "none_suitable": len(picks) == 0}), usage=SYNTHETIC_USAGE)
    return ProviderError(status=None, retryable=False, message="모의 응답기가 모르는 요청이다")


class HeuristicMockProvider(MockProvider):
    """심어 둔 응답이 있으면 그것을, 없으면 규칙 기반 응답을 돌려주는 모의 공급사. 네트워크를 쓰지 않는다."""

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        if self.pending == 0:
            self.enqueue(heuristic_reply)
        return super().invoke(request, options)


# ── 조립 ──


@dataclass(frozen=True, slots=True)
class Harness:
    mock: MockProvider
    log: MemorySink
    client: LlmClient
    options: PipelineOptions


def mock_client(mock: MockProvider, log: MemorySink | None = None) -> LlmClient:
    """모의 공급사 하나만 가진 클라이언트. 프롬프트는 패키지에 실린 것(esgapi/inventory/prompts)을 읽는다."""
    return LlmClient(
        config=load_config(default_config_sources(synthetic=True)),
        providers={"mock": mock},
        prompts=PackagePromptStore(),
        log=log or MemorySink(),
    )


def harness(
    store: FactorCatalog,
    *,
    memory: MappingMemory | None = None,
    heuristic: bool = False,
    exclude: tuple[LicenseStatus, ...] = (),
    shortlist_size: int = DEFAULT_SHORTLIST_SIZE,
    shortlister: Shortlister | None = None,
    adjustments: tuple[CurrencyAdjustment, ...] = (),
) -> Harness:
    """모의 공급사 하나와 받은 계수 표로 파이프라인 옵션을 만든다. 심어 둔 응답이 없으면 모의 공급사는 오류를 돌려준다
    (`heuristic` 을 켜면 규칙 응답기가 답한다)."""
    mock = HeuristicMockProvider() if heuristic else MockProvider()
    log = MemorySink()
    client = mock_client(mock, log)
    options = PipelineOptions(
        client=client,
        store=store,
        memory=memory or InMemoryMappingMemory(),
        route=ROUTE,
        tags=TAGS,
        exclude_license_statuses=exclude,
        shortlist_size=shortlist_size,
        shortlister=shortlister or default_shortlister(),
        adjustments=adjustments,
    )
    return Harness(mock, log, client, options)


def remembered(item_name: str, factor_id: str, category: SupportedCategory = 1, unit: str | None = "kg") -> MemoryEntry:
    """그 품목(기본 단위 kg)의 묶음 키로 확정된 가상 매핑."""
    return MemoryEntry(
        key=group_key(item_name, unit, None),
        category=category,
        factor_id=factor_id,
        confirmed_by="synthetic-reviewer",
        confirmed_at="2026-09-30T09:00:00+09:00",
    )


# ── 예제 폴더의 곁 파일 ──


def load_memory(path: Path) -> InMemoryMappingMemory:
    """예제 폴더의 `memory.synthetic.json`(가상 확정 매핑)."""
    body = json.loads(path.read_text(encoding="utf-8"))
    if body["version"] != 1 or body["synthetic"] is not True:
        raise ValueError(f"가상 기억 파일이 아니다: {path}")
    return InMemoryMappingMemory(
        [
            MemoryEntry(
                key=entry["key"],
                category=entry["category"],
                factor_id=entry["factorId"],
                confirmed_by=entry["confirmedBy"],
                confirmed_at=entry["confirmedAt"],
                label=entry.get("label"),
            )
            for entry in body["entries"]
        ]
    )


def load_adjustments(path: Path) -> tuple[CurrencyAdjustment, ...]:
    """가상 보정 계수 파일. 실제 환율·물가지수가 아니다."""
    body = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        CurrencyAdjustment(
            currency=entry["currency"],
            target_currency=entry["targetCurrency"],
            target_price_year=entry["targetPriceYear"],
            multiplier=entry["multiplier"],
            synthetic=entry["synthetic"],
            source=None
            if entry["source"] is None
            else AdjustmentSource(entry["source"]["url"], entry["source"]["checkedOn"]),
        )
        for entry in body["adjustments"]
    )


# ── TS CLI 의 rows.json 꼴(esg-lab `cli.ts` 의 `rowDump`, `evaluate.ts` 의 `predictedCategory`) ──


def predicted_category(decision: GroupDecision) -> int | str | None:
    """판단이 가리키는 범주. 분류에 실패했으면 None, AI 적용 범위 밖이면 "other"."""
    match decision:
        case UnsupportedCategory():
            return "other"
        case MemoryFactorMissing() | MemoryCategoryMismatch() | MemoryFactorExcluded():
            return decision.memory_entry.category
        case ClassificationFailed():
            return None
        case _:
            return decision.category


def row_dump(examples: Iterable[Example], result: PipelineResult) -> list[dict[str, object]]:
    group_of = {row_id: group for group in result.groups for row_id in group.row_ids}
    by_row = {entry.row.row_id: entry for entry in result.rows}
    dump: list[dict[str, object]] = []
    for example in examples:
        entry = by_row[example.row.row_id]
        decision = entry.decision
        classified = getattr(decision, "classification", None)
        failed = decision.llm if isinstance(decision, (ClassificationFailed, RecommendationFailed)) else None
        recommended = decision if isinstance(decision, Recommended) else None
        dump.append(
            {
                "rowId": example.row.row_id,
                "itemName": example.row.item_name,
                "unit": example.row.unit,
                "gold": {
                    "category": example.gold.category,
                    "factorIds": list(example.gold.factor_ids),
                    "note": example.gold.note,
                },
                "status": decision.status,
                "source": decision.source,
                "predictedCategory": predicted_category(decision),
                "keywords": None if classified is None else list(classified.keywords),
                "picks": [] if recommended is None else [pick.factor_id for pick in recommended.picks],
                "basis": None if recommended is None else basis_to_dict(recommended.basis),
                "failure": None if failed is None else failure_to_dict(failed),
                "shortlists": [trace_to_dict(trace) for trace in group_of[example.row.row_id].shortlists],
                "calcStatus": entry.calc.status,
            }
        )
    return dump
