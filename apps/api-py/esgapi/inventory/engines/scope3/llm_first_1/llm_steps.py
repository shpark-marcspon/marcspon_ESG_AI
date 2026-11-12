"""분류·추천 호출의 조립과 응답 스키마. esg-lab `ts/scope3/src/domain/llmSteps.ts` 를 옮긴 것이다.

★ 숫자는 생성 모델에 넘기지 않는다. 프롬프트에 가는 것은 품목명·단위·통화·운송의 출발지·도착지·수단과,
  후보의 id·이름·경로(조건부)·분모 단위·출처·지역뿐이다. 수량·금액·무게·거리·계수 값은 가지 않는다.
  품목명에 든 규격 숫자("80g")는 이름의 일부라 그대로 간다.

TS 와 다르게 한 것:
  - 프롬프트 id 가 `모듈/이름@판` 이라 `scope3/classify@1` → `inventory/scope3-classify@1`,
    `scope3/recommend@1` → `inventory/scope3-recommend@1`(템플릿 본문은 그대로다).
  - zod 의 `max(60)` 은 UTF-16 길이, Pydantic 의 `max_length` 는 코드 포인트 수다(BMP 밖 글자에서만 갈린다).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, create_model, model_validator

from esgapi.core.calc.guards import NotBool
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.types import (
    BudgetExceeded,
    CallMeta,
    CutOff,
    ProviderFailed,
    Refused,
    SchemaMismatch,
    Tags,
    TimedOut,
)
from esgapi.inventory.engines.scope3.llm_first_1.types import (
    CandidateBasis,
    Confidence,
    Factor,
    InputRow,
    SupportedCategory,
)
from esgapi.inventory.tools.jsrepr import js_json, js_string

CLASSIFY_PROMPT: Final = "inventory/scope3-classify@1"
RECOMMEND_PROMPT: Final = "inventory/scope3-recommend@1"
CLASSIFY_SCHEMA_NAME: Final = "scope3_classification"
RECOMMEND_SCHEMA_NAME: Final = "scope3_recommendation"

# 출처: esg-lab ts/scope3/src/domain/llmSteps.ts:9 (HEAD f1b2c77, 확인 2026-10-08).
MAX_PICKS: Final = 3
# 답의 출력 토큰 상한. 추론 토큰이 출력 상한을 같이 쓰는 것은 모델의 성질이라 여기 넣지 않는다(호출 층이 모델 설정의
# 여유분을 더해 보낸다). 출처: 같은 파일 16-17 줄(추론 없는 모델의 실측 최대는 분류 143 · 추천 321 토큰, 2026-10-02).
CLASSIFY_MAX_OUTPUT_TOKENS: Final = 400
RECOMMEND_MAX_OUTPUT_TOKENS: Final = 800

MAX_KEYWORDS: Final = 8
MAX_KEYWORD_LENGTH: Final = 60


class _Strict(BaseModel):
    """zod 의 `strictObject`: 모르는 칸을 거절한다."""

    model_config = ConfigDict(extra="forbid")


Keyword = Annotated[str, StringConstraints(min_length=1, max_length=MAX_KEYWORD_LENGTH)]
Reason = Annotated[str, StringConstraints(min_length=1)]
# 파이썬에서는 True == 1 이라 Literal[1, …] 이 true 를 범주 1 로 받을 수 있다. 먼저 거른다.
CategoryOut = Annotated[Literal[1, 2, 4, 6, 7, 9, "other"], NotBool]


class ClassificationOut(_Strict):
    """분류 응답의 스키마(생성 모델이 내는 JSON 의 꼴)."""

    category: CategoryOut
    keywords_en: Annotated[list[Keyword], Field(max_length=MAX_KEYWORDS)]
    confidence: Confidence
    reason: Reason


class PickOut(_Strict):
    factor_id: str
    reason: Reason
    confidence: Confidence


class RecommendationOut(_Strict):
    """추천 응답의 스키마의 바탕. 호출마다 `recommendation_schema` 가 `factor_id` 를 후보 id 의 열거로 좁힌다."""

    picks: Annotated[list[PickOut], Field(max_length=MAX_PICKS)]
    none_suitable: bool

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [pick.factor_id for pick in self.picks]
        if len(set(ids)) != len(ids):
            raise ValueError("같은 factor_id 를 두 번 골랐다")
        if (len(self.picks) == 0) != self.none_suitable:
            raise ValueError("picks 가 비면 none_suitable 은 true, 아니면 false 여야 한다")
        return self


def recommendation_schema(candidate_ids: Sequence[str]) -> type[RecommendationOut]:
    """추천 응답의 스키마. `factor_id` 는 이번 호출에 넘긴 후보 id 만 허용한다.

    후보 밖 id 는 여기서 스키마 불일치가 되고, 호출 층이 다시 부른 뒤에도 같으면 `schema_mismatch` 로 끝난다.
    """
    if len(candidate_ids) == 0:
        raise ValueError("후보가 없는 추천 스키마는 만들 수 없다")
    # 열거는 호출마다 다르다. Literal 을 그때그때 만든다(타입 검사기는 이 값을 볼 수 없어 Any 로 둔다).
    id_type: Any = Literal[tuple(candidate_ids)]  # pyright: ignore[reportInvalidTypeArguments]
    pick: Any = create_model("Scope3Pick", __base__=PickOut, factor_id=(id_type, ...))
    picks_type: Any = Annotated[list[pick], Field(max_length=MAX_PICKS)]
    model = create_model("Scope3Recommendation", __base__=RecommendationOut, picks=(picks_type, ...))
    return model


@dataclass(frozen=True, slots=True)
class Classification:
    category: SupportedCategory | Literal["other"]
    keywords: tuple[str, ...]
    confidence: Confidence
    reason: str


def item_for_prompt(row: InputRow) -> dict[str, object]:
    """생성 모델에 보여 주는 품목 정보. 수량, 금액, 무게, 거리는 넣지 않는다(숫자 판단은 코드의 몫이다)."""
    transport = row.transport
    return {
        "item_name": row.item_name,
        "unit": row.unit,
        "currency": row.currency,
        "transport": (
            None
            if transport is None
            else {"origin": transport.origin, "destination": transport.destination, "mode": transport.mode}
        ),
    }


def candidate_for_prompt(factor: Factor) -> dict[str, object]:
    """생성 모델에 보여 주는 후보 정보. 계수 값은 넣지 않는다.

    `path` 는 경로가 있고 이름이 경로의 첫 마디로 시작하지 않을 때만 싣는다(없으면 키가 없다).
    """
    out: dict[str, object] = {"id": factor.id, "name": factor.name}
    path = " > ".join(factor.category_path)
    if path != "" and not factor.name.startswith(factor.category_path[0]):
        out["path"] = path
    out["per"] = factor.unit_denominator
    out["source"] = factor.source_id
    out["region"] = factor.region
    return out


def classify_request(row: InputRow, route: str, tags: Tags) -> CallRequest[ClassificationOut]:
    return CallRequest(
        prompt=CLASSIFY_PROMPT,
        # JSON.stringify 와 같은 글자(공백 없음, 한글 그대로).
        vars={"item_json": js_json(item_for_prompt(row))},
        route=route,
        tags=tags,
        schema=ClassificationOut,
        schema_name=CLASSIFY_SCHEMA_NAME,
        max_output_tokens=CLASSIFY_MAX_OUTPUT_TOKENS,
    )


def recommend_request(
    row: InputRow,
    category: SupportedCategory,
    basis: CandidateBasis,
    candidates: Sequence[Factor],
    route: str,
    tags: Tags,
) -> CallRequest[RecommendationOut]:
    return CallRequest(
        prompt=RECOMMEND_PROMPT,
        vars={
            "category": str(category),
            "basis": "활동(물량·거리) 기반" if basis == "physical" else "지출 기반",
            "item_json": js_json(item_for_prompt(row)),
            "candidates_json": js_json([candidate_for_prompt(factor) for factor in candidates]),
        },
        route=route,
        tags=tags,
        schema=recommendation_schema([factor.id for factor in candidates]),
        schema_name=RECOMMEND_SCHEMA_NAME,
        max_output_tokens=RECOMMEND_MAX_OUTPUT_TOKENS,
    )


FailureKind = Literal["schema_mismatch", "refusal", "truncated", "provider_error", "timeout", "budget_exceeded"]


@dataclass(frozen=True, slots=True)
class LlmFailure:
    """성공이 아닌 호출 결과를 종류와 함께 보존한다. 빈 결과로 바꾸지 않는다."""

    kind: FailureKind
    detail: str


type FailedResult = SchemaMismatch | Refused | CutOff | ProviderFailed | TimedOut | BudgetExceeded


def describe_failure(result: FailedResult) -> LlmFailure:
    match result:
        case SchemaMismatch():
            return LlmFailure(result.kind, "; ".join(f"{issue.path}: {issue.message}" for issue in result.issues))
        case Refused():
            return LlmFailure(result.kind, result.text)
        case CutOff():
            return LlmFailure(result.kind, "출력 토큰 상한에서 잘렸다")
        case ProviderFailed():
            status, retryable = js_string(result.status), js_string(result.retryable)
            return LlmFailure(result.kind, f"status={status} retryable={retryable} {result.message}")
        case TimedOut():
            return LlmFailure(result.kind, result.message)
        case BudgetExceeded():
            limit, spent = js_string(result.limit_usd), js_string(result.spent_usd)
            return LlmFailure(result.kind, f"상한 {limit} USD, 누적 {spent} USD")


@dataclass(slots=True)
class PromptUsage:
    calls: int = 0
    attempts: int = 0
    cost_usd: float = 0.0


@dataclass(slots=True)
class LlmUsage:
    """호출 집계. `calls` 는 호출 층을 부른 수, `attempts` 는 공급사를 실제로 부른 수(재시도·대체 포함)."""

    calls: int = 0
    attempts: int = 0
    cost_usd: float = 0.0
    by_prompt: dict[str, PromptUsage] = field(default_factory=dict[str, PromptUsage])


def record_usage(usage: LlmUsage, prompt: str, meta: CallMeta) -> None:
    slot = usage.by_prompt.setdefault(prompt, PromptUsage())
    for target in (usage, slot):
        target.calls += 1
        target.attempts += len(meta.attempts)
        target.cost_usd = round_usd(target.cost_usd + meta.total_cost_usd)
