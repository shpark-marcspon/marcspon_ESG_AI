"""실행 하나의 금액 위끝(prepare 의 `totalEstimateUsd` — MARC-ENT-482 ②, 밴드 TRE1). 순수 — 공급사·설정 0.

    위끝 = Σ_자리 ρ_자리 × B_자리 + max_guard

`B_자리` 는 다리 `dry_run` 의 자리별 `estimateUsd`(엄격 위끝 — 모든 호출이 출력 상한을 다 쓰고 조건부 자리가 모두
도는 합). 그 합은 실측의 약 24배라(TRL2 — MARC-ISSUE-268) 상한에 걸려 쓸 만한 문서가 거절된다. 그래서 자리마다 실측
비율 ρ 를 곱해 낮추고, 「실비 ≤ 위끝」은 셈이 아니라 실행이 지킨다: 흐름의 실행 중 상한이 `min(max_usd, 위끝)` 이고
호출 일지(tools/call_journal.py)가 실제 호출 전마다 `지출 + 머리 여유(그 요청의 dry_run 위끝 × GUARD_FACTOR) ≤ 상한` 이
아니면 부르지 않는다(over_budget). 마지막 항 `max_guard` 는 계획 안 요청 하나의 머리 여유 최댓값 — 실비가 어림대로
와도 마지막 호출이 머리 여유에 걸리지 않게 하는 몫이다.

머리 여유 = 위끝 × guard_factor(그 공급사의 재시도 수) = 위끝 × max(GUARD_FACTOR, 1 + 재시도 수)(감독 결정 D2): 실비를
모르는 시도(사용량 없는 실패)는 시도마다 위끝만큼 깎이는데(D1) 공급사 재시도로 한 호출에 1 + 재시도 수 개까지 날 수
있어, 머리 여유가 그보다 작으면 들여보낸 호출이 상한을 넘겨 깎인다. 재시도 수는 운영 client 의 설정
(`core.llm.retry.DEFAULT_PROVIDER_RETRY` — `core/llm/setup.py` 가 provider_retry 를 주지 않아 이것을 쓴다)에서 읽는다
(openai 2 → 3배).

GUARD_FACTOR 2.0 의 유도(추정): 2.0 = 어림 입력 토큰 대비 실제 입력 토큰 비율의 위 끝(MARC-RPT-4 — 실제 공급사 계수가
국문 어림의 1.2~2.0배, 다리 DRY_RUN_ASSUMPTIONS 가 인용). gpt-4.1·mini 는 `p_out = 4·p_in`(models.json)이고 위끝 =
`p_in·I어림 + p_out·O상한`, 실비 ≤ `p_in·I실제 + p_out·O상한` 이라 **실비 > 머리 여유 ⇔ 실제 입력 비용 >
2·어림 입력 비용 + 출력 상한 비용** — 출력 상한 몫까지 여유로 쓰므로 입력이 2배를 꽤 넘어도 무너지지 않는다.
1.0 이면 국문 과소 어림 때 마지막 호출 하나가 상한을 넘을 수 있다.

ρ = min(1, max(FLOOR, MARGIN × r)), r = 실비_자리 / live B_자리. 실측 자리의 r 은 TRL2(MARC-TICK-382, 6쪽 general·A/B·
자동수정 1벌, gpt-4.1-mini, 2026-10-28 — 실비 = 서버 DB core_llm_call_logs run 11, **확인**)에서 셌다. B 는 같은 입력의
in-process `dry_run`(DEFAULT_MODELS, 공급사 0, 2026-10-29) — TRL2 보고의 「서버 4.502」는 mock 단가(MOCK_MODELS) 셈이라
쓰지 않는다(보고 ★①). 표·ceo_message·용어집 문서는 실측(따로 승인 — MARC-ENT-262) 뒤 다시 잰다(감독 결정 10-29).
표에 없는 자리는 ρ = 1(엄격 그대로 — 새 자리를 더하면 셈이 늘 커지는 쪽).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, TypedDict

if TYPE_CHECKING:
    from esgapi.translation.tools.llm_bridge import DryRunSummary

GUARD_FACTOR: Final = 2.0
"""머리 여유 배수의 바닥(추정 — 머리말의 유도. 재시도가 많으면 guard_factor 가 더 크게). 어림 입력 토큰 대비
실제 입력 토큰 비율을 재면(국문 많은 문서의 실측) 다시."""
MARGIN: Final = 3.0
"""추정: 표본 1벌(6쪽 general)이라 문서마다 자리 실비가 2~3배 흔들려도 산출 0 의 over_budget 이 나지 않게 잡은 여유.
표본이 늘면(문서 셋 이상) 자리별 r 의 최댓값/평균으로 다시."""
FLOOR: Final = 0.05
"""추정: TRL2 에서 0 회였던 조건부 자리(한국어 보정·자동수정 한국어)도 계획 호출의 약 5% 몫(korean-repair 72 중 약
4호출 꼴)은 예비. 국문이 남는 원문을 실측하면 그 r 로."""

RATIOS: Final[Mapping[str, float]] = MappingProxyType(
    {
        # 실측(TRL2 — r = 실비 / live B, ρ = 3r 를 셋째 자리에서 올림): 실비 USD(호출) / B USD(계획 호출)
        "section": 0.674,  # 0.0692952(36) / 0.3087(36), r 0.2245
        "polish": 0.468,  # 0.0841532(38) / 0.5401(48), r 0.1558
        "editorial-qa": 0.118,  # 0.0066524(2) / 0.1699(12), r 0.0392
        "review": 0.363,  # 0.0196964(12) / 0.1631(12), r 0.1208
        "autofix": 0.118,  # 0.0066036(2) / 0.1690(12), r 0.0391
        # 바닥값(추정 — FLOOR): TRL2 에서 0 회
        "korean-repair": FLOOR,  # 0(0) / 0.8545(72)
        "autofix-korean": FLOOR,  # 0(0) / 0.2073(12)
        # TRL2 에 없는 자리(추정)
        # 표 묶음은 문서마다 늘 돌고 출력 상한 8192 가 커서 실측 자리 ρ 보다 넉넉히 반. 표 많은 쪽 실측 때 다시
        "table-batch": 0.5,
        "cell": FLOOR,  # 칸 대체는 표 묶음 JSON 실패 때만(드묾). JSON 실패율을 재면 다시
        # 용어집이 있으면 key 든 구획마다 돌 수 있음 — polish 와 같은 꼴로 봄. 용어집 문서 실측 때 다시
        "glossary-repair": 0.25,
    }
)
"""자리 → ρ(머리말). 표에 없는 자리는 1. 표·ceo_message·용어집 문서는 실측(따로 승인) 뒤 다시."""


def guard_factor(retries: int) -> float:
    """머리 여유 배수(머리말 — 감독 결정 D2)."""
    return max(GUARD_FACTOR, 1.0 + retries)


class SiteBound(TypedDict):
    calls: int
    estimateUsd: float
    ratio: float


class RunBound(TypedDict):
    totalUsd: float
    """새 위끝(prepare `totalEstimateUsd`)."""
    ceilingUsd: float
    """옛 엄격 합(다리 dry_run 의 `totalEstimateUsd` — 비교용)."""
    perSite: dict[str, SiteBound]


def ratio(site: str) -> float:
    return RATIOS.get(site, 1.0)


def run_bound(summary: "DryRunSummary", max_guard_usd: float) -> RunBound:
    """머리말의 셈. `max_guard_usd` = 계획 안 요청 하나의 머리 여유 최댓값(다리 `dry_run_with_max`)."""
    per_site: dict[str, SiteBound] = {}
    total = max_guard_usd
    for site, value in summary["perSite"].items():
        rho = ratio(site)
        per_site[site] = SiteBound(calls=value["calls"], estimateUsd=value["estimateUsd"], ratio=rho)
        total += rho * value["estimateUsd"]
    return RunBound(totalUsd=total, ceilingUsd=summary["totalEstimateUsd"], perSite=per_site)
