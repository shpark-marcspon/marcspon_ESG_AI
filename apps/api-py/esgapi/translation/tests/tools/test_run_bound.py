"""run_bound 셈 단위(밴드 TRE1 S3, 순수 — 공급사·설정 0). 값은 지어낸 어림."""

import pytest

from esgapi.translation.tools import run_bound
from esgapi.translation.tools.llm_bridge import DryRunSummary


def summary(**per_site: tuple[int, float]) -> DryRunSummary:
    return {
        "perSite": {site: {"calls": calls, "estimateUsd": usd} for site, (calls, usd) in per_site.items()},
        "totalEstimateUsd": sum(usd for _, usd in per_site.values()),
        "assumptions": [],
        "unestimated": [],
        "warnings": [],
    }


def test_s3_a_site_missing_from_the_table_keeps_its_strict_estimate() -> None:
    """모르는 자리는 ρ = 1(새 자리를 더하면 셈이 늘 커지는 쪽 — ρ=0 이면 빨강, P7)."""
    bound = run_bound.run_bound(summary(**{"virtual-site": (3, 0.3)}), 0.0)
    assert run_bound.ratio("virtual-site") == 1.0
    assert bound["perSite"]["virtual-site"] == {"calls": 3, "estimateUsd": 0.3, "ratio": 1.0}
    assert bound["totalUsd"] == pytest.approx(0.3)


def test_s3_the_last_call_guard_is_added_once() -> None:
    """위끝 = Σ ρ × 어림 + max_guard(요청 하나의 머리 여유 최댓값 — 지우면 빨강, P6). ceilingUsd = 엄격 합. 머리
    여유 배수 = max(GUARD_FACTOR 2, 1 + 재시도 수)(감독 결정 D2 — 배수를 GUARD_FACTOR 로만 두면 빨강, P11)."""
    given = summary(section=(2, 0.2), review=(1, 0.05))
    bound = run_bound.run_bound(given, 0.3)
    expected = sum(run_bound.ratio(s) * v["estimateUsd"] for s, v in given["perSite"].items())
    assert bound["totalUsd"] == pytest.approx(expected + 0.3)
    assert bound["ceilingUsd"] == pytest.approx(0.25)
    assert run_bound.GUARD_FACTOR == 2.0
    assert [run_bound.guard_factor(n) for n in (0, 1, 2, 3)] == [2.0, 2.0, 3.0, 4.0]


def test_s3_every_ratio_is_between_the_floor_and_one() -> None:
    assert all(run_bound.FLOOR <= rho <= 1.0 for rho in run_bound.RATIOS.values())


# ── ② ρ 표 ──

TRL2_B = {
    "section": 0.308668,
    "polish": 0.5400776,
    "korean-repair": 0.85448,
    "editorial-qa": 0.1698824,
    "review": 0.1631376,
    "autofix": 0.1689736,
    "autofix-korean": 0.207332,
}
"""TRL2 6쪽(MARC-TICK-382)의 live 자리별 엄격 어림 USD(in-process dry_run, gpt-4.1-mini — 보고 ★①). 숫자만."""
TRL2_SPENT = {
    "section": 0.0692952,
    "polish": 0.0841532,
    "editorial-qa": 0.0066524,
    "review": 0.0196964,
    "autofix": 0.0066036,
    "korean-repair": 0.0,
    "autofix-korean": 0.0,
}
"""TRL2 실비 USD(서버 장부 run 11 — 자리별 합). 숫자만."""


def test_s3_the_table_follows_the_rule_on_the_trl2_record() -> None:
    """실측 자리 ρ = min(1, max(FLOOR, MARGIN × r)) 를 셋째 자리에서 올린 값(r = 실비 / B)."""
    for site, spent in TRL2_SPENT.items():
        expected = min(1.0, max(run_bound.FLOOR, run_bound.MARGIN * spent / TRL2_B[site]))
        assert expected <= run_bound.ratio(site) <= expected + 0.001, site
    assert run_bound.ratio("table-batch") == 0.5
    assert run_bound.ratio("cell") == run_bound.FLOOR
    assert run_bound.ratio("glossary-repair") == 0.25


def test_s3_r1_the_trl2_record_stays_under_the_new_estimate() -> None:
    """R1: 자리마다 ρ × B ≥ 실비, 합 ≥ TRL2 실비 0.1864008(위끝을 실비 아래로 낮추면 빨강 — P5)."""
    for site, spent in TRL2_SPENT.items():
        assert run_bound.ratio(site) * TRL2_B[site] >= spent, site
    bound = run_bound.run_bound(summary(**{s: (1, b) for s, b in TRL2_B.items()}), 0.0)
    assert bound["totalUsd"] >= 0.1864008
    assert bound["totalUsd"] <= bound["ceilingUsd"] * 0.3
