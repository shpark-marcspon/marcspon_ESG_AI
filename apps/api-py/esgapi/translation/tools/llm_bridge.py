"""core.llm 다리: 엔진 포트(`LlmGateway`)를 `LlmClient` 로 채운다. greenwash `tools/llm_bridge.py` 의 `LlmTextCall` 꼴을
판별 복사했다(모듈끼리 import 하지 않는다).

자리 → 프롬프트 id `translation/<자리>@<판>`(봉투 — 글은 엔진이 지어 변수 system·user 로 넘긴다).
판은 `PROMPT_VERSIONS`: 쪽 system 을 싣는 일곱 자리는 @2(봉투 `=== system cache ===` — system 에 캐시 표시,
MARC-ISSUE-213 — OpenAI 경로에서는 공급사가 system 조각을 이어 붙여 표시가 쓰이지 않는다), 검수·자동수정 셋은
@1(TR2 감독 처분 Q10). 역할 → 경로(처분 ⑨의 자리, 모델은 MARC-ENT-402 — 밴드 TR3a): translate 는 파트가
ceo_message 면 `standard-openai-41`(gpt-4.1), 아니면 `light-openai-41`(gpt-4.1-mini). review 는 늘
`light-openai-41`(파트와 무관 — 코랩 W3 의 자리).
temperature 는 싣지 않는다(코랩도 넘기지 않는다 — R/2128 은 쓰는 곳 0). thinking 도 싣지 않는다(core 가 싣지 않음 —
코랩은 CEO 번역 자리에 disabled 를 싣는다. 보고 「코랩과 다른 자리」).

갈래(코랩은 잘림·거절에 예외를 내지 않고 그 글로 계속한다 — 발주서 개정 1 B4): Success → complete, CutOff → 잘린 글·
truncated, Refused → 거절 글·refused, 그 밖(ProviderFailed·TimedOut·BudgetExceeded·SchemaMismatch) → LlmCallFailed
(메시지에 결과 kind). 글은 strip 하지 않는다 — 코랩의 strip 은 엔진이 자리마다 한다.

부르는 쪽은 경로의 공급사를 꽂는다 — 세 경로 다 openai 다(실행기가 mock 이면 흐름이 `MOCK_MODELS` 로 경로 `mock` 을
부른다 — MARC-ISSUE-331. 시험·dry-run 은
`{"anthropic": MockProvider("anthropic"), "openai": MockProvider("openai")}`). 설정·키·SDK 클라이언트는 짓지 않는다
(부르는 쪽이 `LlmClient` 를 넘긴다).

`dry_run(plan)` 은 엔진의 호출 계획(engines/colab_158/plan.py)을 요청마다 `LlmClient.dry_run` 으로 어림한다
(공급사 호출 0 — `totalEstimateUsd`·자리별 `estimateUsd`·`assumptions`, 발주서 개정 2 M3).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, TypedDict

from esgapi.core.llm.client import CallRequest, LlmClient
from esgapi.core.llm.retry import DEFAULT_PROVIDER_RETRY, NO_RETRY
from esgapi.core.llm.types import CutOff, Refused, Success, Tags
from esgapi.translation.engines.colab_158.plan import CallPlan
from esgapi.translation.engines.colab_158.ports import GatewayText, LlmCallFailed, Role
from esgapi.translation.engines.colab_158.prompts import MAX_TOKENS, SITES, Site
from esgapi.translation.tools.run_bound import guard_factor

MODULE: Final = "translation"
PROMPT_VERSIONS: Final[Mapping[Site, int]] = MappingProxyType(
    {
        "cell": 2,
        "table-batch": 2,
        "section": 2,
        "polish": 2,
        "editorial-qa": 2,
        "glossary-repair": 2,
        "korean-repair": 2,
        "review": 1,
        "autofix": 1,
        "autofix-korean": 1,
    }
)
"""자리 → 봉투 판. 실행의 `settings.promptIds` 가 이 판을 싣는다."""
CEO_TRANSLATE_ROUTE: Final = "standard-openai-41"
TRANSLATE_ROUTE: Final = "light-openai-41"
REVIEW_ROUTE: Final = "light-openai-41"

DRY_RUN_ASSUMPTIONS: Final = (
    "시도 하나 기준(재시도·대체 제외)",
    "cjkCharsPerToken = 1(models.json tokenEstimate) — 출처 없는 가정, MARC-RPT-4 는 실제 공급사 계수가 1.2~2.0배라 "
    "국문 입력의 어림이 위끝이 아님",
    "LlmClient.dry_run 은 경로의 첫 모델만 잰다 — 세 경로(standard-openai-41·light-openai-41)는 모델이 하나뿐이다",
    "LlmClient.dry_run 은 첫 모델의 출력 상한만 본다(core/llm/client.py dry_run) — 대체 모델의 상한 초과는 잡지 않는다",
    "LlmClient.dry_run 은 입력을 모두 평 입력 단가로 센다 — gpt-4.1·gpt-4.1-mini 는 캐시 쓰기 단가가 입력 단가와 "
    "같아(models.json cacheWrite) 할증이 없다",
)
"""다리가 어림에 더하는 가정(발주서 개정 2 M3·§2-4 (c)). 계획(plan.py)의 가정 뒤에 붙는다."""


class SiteEstimate(TypedDict):
    calls: int
    estimateUsd: float


class DryRunSummary(TypedDict):
    """`LlmBridge.dry_run` 의 꼴(칸 이름은 발주서 개정 2 M3)."""

    perSite: dict[str, SiteEstimate]
    totalEstimateUsd: float
    assumptions: list[str]
    unestimated: list[str]
    warnings: list[str]


def prompt_id(site: Site) -> str:
    return f"{MODULE}/{site}@{PROMPT_VERSIONS[site]}"


def prompt_ids() -> list[str]:
    """자리 열 개의 프롬프트 id(자리 차례) — 실행의 `settings.promptIds`."""
    return [prompt_id(site) for site in PROMPT_VERSIONS]


def route_for(role: Role, part: str) -> str:
    """역할 둘의 경로(처분 ⑨). 자동수정은 역할 translate(코랩 PART_QA_AUTOFIX_MODEL = TRANSLATION_MODEL, R/6366)."""
    if role == "review":
        return REVIEW_ROUTE
    return CEO_TRANSLATE_ROUTE if part == "ceo_message" else TRANSLATE_ROUTE


# ── 모델 칸(TR4 — AI 설정 판의 모델 설정, MARC-ENT-399·402) ──

REVIEW_SITES: Final[tuple[Site, ...]] = ("review",)
"""역할 review 가 부르는 자리(검수). 그 밖 아홉 자리는 역할 translate."""
TRANSLATE_SITES: Final[tuple[Site, ...]] = tuple(site for site in SITES if site not in REVIEW_SITES)


@dataclass(frozen=True)
class CallModel:
    """칸 하나의 값: 경로와 출력 상한의 위끝. 요청의 max_tokens = min(자리 값, 위끝)(발주서 R4). temperature 칸은
    없다 — 늘 싣지 않는다(R5)."""

    route: str
    max_output_tokens: int


@dataclass(frozen=True)
class TranslationModels:
    """모델 칸 셋. 번역 역할은 파트가 ceo_message 면 translate_ceo, 아니면 translate_other — 검수는 review."""

    translate_ceo: CallModel
    translate_other: CallModel
    review: CallModel


DEFAULT_MODELS: Final = TranslationModels(
    translate_ceo=CallModel(CEO_TRANSLATE_ROUTE, max(MAX_TOKENS[site] for site in TRANSLATE_SITES)),
    translate_other=CallModel(TRANSLATE_ROUTE, max(MAX_TOKENS[site] for site in TRANSLATE_SITES)),
    review=CallModel(REVIEW_ROUTE, max(MAX_TOKENS[site] for site in REVIEW_SITES)),
)
"""코드 값: 경로 상수 셋, 위끝 = 그 칸이 맡는 자리의 max_tokens 가운데 큰 값(그래서 min 이 자리 값 그대로 — 바이트
같음)."""

MOCK_ROUTE: Final = "mock"
MOCK_MAX_OUTPUT_TOKENS: Final = 4000
"""가상 모델 `mock-synthetic` 의 maxOutputTokens(core/llm/data/models.synthetic.json)."""
MOCK_MODELS: Final = TranslationModels(
    translate_ceo=CallModel(MOCK_ROUTE, MOCK_MAX_OUTPUT_TOKENS),
    translate_other=CallModel(MOCK_ROUTE, MOCK_MAX_OUTPUT_TOKENS),
    review=CallModel(MOCK_ROUTE, MOCK_MAX_OUTPUT_TOKENS),
)
"""실행기가 mock 일 때(LLM_RUN_MODE 가 live 가 아님 — 키를 비우고 모의 공급사 mock·mock-b 만 싣는다)의 모델 칸
(MARC-ISSUE-331). 세 칸 다 경로 `mock` — 심은 답이 없어 호출마다 공급사 오류 → 쪽마다 [TRANSLATION_ERROR] 인 채
done 이다(기동 확인용). 위끝 4000 이 자리 max_tokens 보다 작은 곳(table-batch 8192 등)은 mock 에서 4000 으로
준다(R4 min). live 길은 이 값을 쓰지 않는다(판의 모델 칸 그대로)."""


def model_for(role: Role, part: str, models: TranslationModels) -> CallModel:
    """`route_for` 의 갈래 그대로 칸을 고른다."""
    if role == "review":
        return models.review
    return models.translate_ceo if part == "ceo_message" else models.translate_other


def _factor(provider: str) -> float:
    """그 공급사의 머리 여유 배수 — 재시도 수는 운영 client 의 설정(DEFAULT_PROVIDER_RETRY)에서."""
    return guard_factor(DEFAULT_PROVIDER_RETRY.get(provider, NO_RETRY).max_retries)


class LlmBridge:
    """엔진 포트 하나. `part` 는 생성 인자(포트에 파트 칸이 없다 — translate 역할의 경로가 파트에 달림)."""

    def __init__(
        self, client: LlmClient, *, part: str, tenant: str, models: TranslationModels = DEFAULT_MODELS
    ) -> None:
        self.client = client
        self.part = part
        self.tags = Tags(tenant=tenant, module=MODULE)
        self.models = models
        self.last_cost_usd: float | None = None
        """마지막 `complete` 의 실비(USD — `meta.total_cost_usd`). `client.call` 이 결과 없이 던졌으면 None(밴드 TRE1 —
        호출 일지가 시도 안 허용액을 되돌릴 때 읽는다)."""
        self.last_unknown_attempts = 0
        """`meta.attempts` 가운데 `cost_usd` None 시도(사용량 없는 실패) 수 — 0 이 아니면 `last_cost_usd` 는 아는 몫의
        합이다. 공급사 재시도로 한 호출에 여럿일 수 있다(감독 결정 D1 — 기본 재시도 openai 2회면 셋까지)."""

    def _request(self, site: Site, role: Role, system: str, user: str, max_tokens: int) -> CallRequest[str]:
        """칸의 경로, 출력 상한 = min(자리 값, 칸 위끝)(R4). temperature 는 싣지 않는다."""
        model = model_for(role, self.part, self.models)
        return CallRequest[str](
            prompt=prompt_id(site),
            route=model.route,
            tags=self.tags,
            vars={"system": system, "user": user},
            max_output_tokens=min(max_tokens, model.max_output_tokens),
            temperature=None,
        )

    def route(self, role: Role) -> str:
        """그 역할이 부르는 경로(호출 일지의 열쇠 — tools/call_journal.py)."""
        return model_for(role, self.part, self.models).route

    def bound_usd(self, site: Site, role: Role, system: str, user: str, max_tokens: int) -> float:
        """그 요청 한 번의 비용 위끝(`LlmClient.dry_run` — 공급사 호출 0)."""
        return self.guard_usd(site, role, system, user, max_tokens)[0]

    def guard_usd(self, site: Site, role: Role, system: str, user: str, max_tokens: int) -> tuple[float, float]:
        """(위끝, 머리 여유 = 위끝 × 그 공급사의 배수 — tools/run_bound.py 머리말, 감독 결정 D2). 공급사 호출 0."""
        report = self.client.dry_run(self._request(site, role, system, user, max_tokens))
        bound = report.estimate.cost_upper_bound_usd
        return bound, bound * _factor(report.provider)

    def complete(self, site: Site, role: Role, system: str, user: str, max_tokens: int) -> GatewayText:
        self.last_cost_usd = None  # 앞 호출 값이 남지 않게 — 아래에서 던지면 None 그대로
        self.last_unknown_attempts = 0
        request = self._request(site, role, system, user, max_tokens)
        result = self.client.call(request)
        self.last_cost_usd = result.meta.total_cost_usd
        self.last_unknown_attempts = sum(attempt.cost_usd is None for attempt in result.meta.attempts)
        match result:
            case Success():
                return GatewayText(text=result.text, ending="complete")
            case CutOff():
                return GatewayText(text=result.partial_text, ending="truncated")
            case Refused():
                return GatewayText(text=result.text, ending="refused")
            case _:
                raise LlmCallFailed(f"{site}: {result.kind}")

    def dry_run(self, plan: CallPlan) -> DryRunSummary:
        """`dry_run_with_max` 의 어림만."""
        return self.dry_run_with_max(plan)[0]

    def dry_run_with_max(self, plan: CallPlan) -> tuple[DryRunSummary, float]:
        """(어림, 요청 하나의 머리 여유 최댓값 — tools/run_bound.py 의 마지막 호출 여유). 계획의 요청마다
        `LlmClient.dry_run`(공급사 호출 0) × 최대 횟수. 칸 이름은 발주서 개정 2 M3.

        예외를 삼키지 않는다 — 공급사 미등록·출력 상한 초과는 `LlmConfigError`, 봉투가 없으면 `PromptError`
        (흐름의 prepare 가 공급사 전에 부른다, MARC-ISSUE-196 의 2). 계획의 파트가 다리의 파트와 다르면
        `ValueError`(N8)."""
        if plan.part != self.part:
            raise ValueError(f"계획의 파트 {plan.part} 가 다리의 파트 {self.part} 와 다르다")
        per_site: dict[str, SiteEstimate] = {}
        total = 0.0
        warnings: list[str] = []
        max_guard = 0.0
        for call in plan.calls:
            report = self.client.dry_run(self._request(call.site, call.role, call.system, call.user, call.max_tokens))
            max_guard = max(max_guard, report.estimate.cost_upper_bound_usd * _factor(report.provider))
            cost = report.estimate.cost_upper_bound_usd * call.count
            site = per_site.setdefault(call.site, SiteEstimate(calls=0, estimateUsd=0.0))
            site["calls"] += call.count
            site["estimateUsd"] += cost
            total += cost
            warnings += [w.code for w in report.warnings if w.code not in warnings]
        summary: DryRunSummary = {
            "perSite": per_site,
            "totalEstimateUsd": total,
            "assumptions": [*plan.assumptions, *DRY_RUN_ASSUMPTIONS],
            "unestimated": list(plan.unestimated),
            "warnings": warnings,
        }
        return summary, max_guard
