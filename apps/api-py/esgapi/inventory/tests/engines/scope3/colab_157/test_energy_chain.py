"""T1 에너지 계수 사슬 — 이기는 정의 `lookup_energy_ef`(셀 27 `:8229`) → `:7508`(`resolve_energy_ef_row` `:7436`) →
`:6822`(`:479` → 폴백 계수 `ENERGY_FALLBACK_EF_PATCH`). C3 계수(`lookup_energy_ef_c3` `:9113`)는 사슬 밖이다.

계수 시트는 셀 25 다시 읽기 뒤의 꼴(머리글 「활동유형(에너지원)」·「투입량 기준단위」·「CO2eq ★」)이다. 이름은 코랩
규칙이 읽는 분류어(전력·경유·도시가스(LNG) …)이거나 지어낸 `가상…`, 계수는 지어낸 `9.` 꼴이다.
"""

from difflib import SequenceMatcher

import pandas as pd
import pytest

from esgapi.inventory.engines.scope3.colab_157 import energy
from esgapi.inventory.engines.scope3.colab_157.energy import (
    C3Lookup,
    EnergyLookup,
    EnergyMatch,
    energy_alias_candidates,
    lookup_energy_ef,
    lookup_energy_ef_c3,
    resolve_energy_ef_row,
)

NAME, UNIT, EF = "활동유형(에너지원)", "투입량 기준단위", "CO2eq ★\n(kgCO2eq/단위)"


def energy_db(*rows: tuple[object, object, object]) -> pd.DataFrame:
    """(이름, 단위, 계수) 줄 → 다시 읽은 `에너지` 시트 꼴(앞 칸 둘·발열량 칸 포함)."""
    return pd.DataFrame(
        [("가상 구분", "가상 활동", name, unit, None, ef) for name, unit, ef in rows],
        columns=["구분", "배출활동", NAME, UNIT, "순발열량", EF],
    ).astype(object)


BASE = energy_db(
    ("전력", "kWh", 0.0941),
    ("경유", "L", 0.942),
    ("도시가스(LNG)", "Nm³", 0.943),
    ("천연가스(LNG)", "kg", 0.944),
)


def match(name: str, hint: str, raw_name: object, raw_unit: object, kind: str, score: float | None) -> EnergyMatch:
    return EnergyMatch(name, hint, raw_name, raw_unit, kind, score)


def test_exact_name_is_exact_raw_with_score_one() -> None:
    assert lookup_energy_ef(BASE, "전력") == EnergyLookup(
        "전력", 0.0941, "kWh", "exact_raw", match("전력", "", "전력", "kWh", "exact_raw", 1.0)
    )


@pytest.mark.parametrize(
    ("hint", "title", "unit", "ef"), [("Nm³", "도시가스(LNG)", "Nm³", 0.943), ("kg", "천연가스(LNG)", "kg", 0.944)]
)
def test_gas_with_a_unit_takes_the_unit_priority_title(hint: str, title: str, unit: str, ef: float) -> None:
    """`_fix_lookup_energy_title_exact`(`:8213`): 가스 낱말 + 단위면 그 제목을 먼저(match_type unit_priority_alias)."""
    got = lookup_energy_ef(BASE, "LNG", unit_hint=hint)
    assert got == EnergyLookup(
        title, ef, unit, "unit_priority_alias", match("LNG", hint, title, unit, "unit_priority_alias", 1.0)
    )


def test_gas_without_the_priority_title_falls_through_to_the_resolver() -> None:
    db = energy_db(("천연가스(LNG)", "kg", 0.944))
    got = lookup_energy_ef(db, "도시가스", unit_hint="Nm³")
    # 「도시가스」 후보 → 「도시가스(LNG)」 없음 → 「천연가스(LNG)」 정확(alias, 0.97) − 다른 단위 0.05
    assert (got.name, got.via, got.match.match_type, got.match.score) == (
        "천연가스(LNG)",
        "alias_exact",
        "alias_exact",
        0.92,
    )


def test_the_c8_main_loop_passes_no_hint_so_no_unit_priority() -> None:
    """C8·C13 본 고리(`:6157`)는 힌트 없이 부른다 — 가스 이름이어도 단위 우선이 아니라 후보 차례(도시가스 먼저)."""
    got = lookup_energy_ef(BASE, "LNG")
    assert (got.name, got.via, got.match.score) == ("도시가스(LNG)", "alias_exact", 0.97)


@pytest.mark.parametrize(
    ("name", "hint", "expected"),
    [
        ("LNG", None, ["LNG", "도시가스(LNG)", "천연가스(LNG)"]),
        ("LNG", "kg", ["LNG", "천연가스(LNG)", "도시가스(LNG)"]),
        ("전기", None, ["전기", "전력"]),
        ("LPG", "Nm³", ["LPG", "도시가스(LPG)", "액화석유가스(LPG)"]),
        ("등유", None, ["등유", "보일러 등유", "실내 등유"]),
    ],
)
def test_alias_candidates_follow_the_gas_and_unit_rules(name: str, hint: str | None, expected: list[str]) -> None:
    assert energy_alias_candidates(name, unit_hint=hint) == expected


def test_alias_exact_scores_097_and_contains_090() -> None:
    assert lookup_energy_ef(BASE, "전기").match.score == 0.97
    db = energy_db(("가상 전력(계통)", "kWh", 0.91))
    got = lookup_energy_ef(db, "전기")  # 후보 「전력」 ⊂ 「가상전력계통」
    assert (got.via, got.match.score) == ("alias_contains", 0.9)


def test_the_raw_name_is_candidate_zero_so_query_contains_is_never_reached() -> None:
    """후보 첫째가 입력 그대로라 「별칭 포함」(0.90)이 「입력 포함」(`:7488`, 0.86)보다 늘 먼저 걸린다 — 코랩에서 닿지
    않는 갈래(결함 후보 아님, 보고 「코랩과 같은 흠」)."""
    got = lookup_energy_ef(energy_db(("가상연료혼합", "L", 0.91)), "가상연료")
    assert (got.via, got.match.score) == ("alias_contains", 0.9)


def test_the_unit_hint_bonus_picks_the_row_with_that_unit() -> None:
    db = energy_db(("가상연료", "L", 0.91), ("가상연료", "kg", 0.92))
    assert lookup_energy_ef(db, "가상연료").ef == 0.91  # 힌트 없음 — 같은 점수, 앞 줄
    picked = lookup_energy_ef(db, "가상연료", unit_hint="kg")
    assert (picked.ef, picked.match.score) == (0.92, 1.0)  # 1.0 + 0.08 → 상한 1.0


def test_tj_rows_are_normalised_to_gj() -> None:
    """`:7520-7522`: DB 단위 TJ 면 계수 ÷1000, 단위 GJ."""
    db = energy_db(("열(스팀)", "TJ", 9100.0))
    got = lookup_energy_ef(db, "스팀")
    assert (got.name, got.ef, got.unit, got.match.raw_unit) == ("열(스팀)", 9.1, "GJ", "GJ")


# 25 글자(서로 다름)와 앞 18·17 글자가 같은 입력: SequenceMatcher 비 = 2×18/50 = 0.72(문턱 그대로), 2×17/50 = 0.68
LONG = "abcdefghijklmnopqrstuvwxy"
AT_THRESHOLD = LONG[:18] + "1234567"
BELOW = LONG[:17] + "12345678"


def test_fuzzy_threshold_is_inclusive_at_072() -> None:
    assert SequenceMatcher(None, AT_THRESHOLD, LONG).ratio() == 0.72
    db = energy_db((LONG, "L", 0.91))
    got = lookup_energy_ef(db, AT_THRESHOLD)
    assert (got.via, got.match.match_type, got.match.score, got.ef) == ("fuzzy", "fuzzy", 0.72, 0.91)


def test_fuzzy_below_the_threshold_finds_nothing() -> None:
    assert SequenceMatcher(None, BELOW, LONG).ratio() == 0.68
    got = lookup_energy_ef(energy_db((LONG, "L", 0.91)), BELOW)
    assert got == EnergyLookup(None, None, None, "none", match(BELOW, "", None, None, "not_found", 0.0))


def test_fuzzy_score_is_capped_at_093() -> None:
    db = energy_db((LONG, "L", 0.91))
    near = LONG[:24] + "1"  # 2×24/50 = 0.96
    assert resolve_energy_ef_row(db, near).score == 0.93


def test_the_fallback_patch_answers_when_the_db_has_no_such_energy() -> None:
    """`:6822`: 통합 DB 에 없는 「휘발유」 → 폴백 계수(코랩 상수). 코랩 match_type 은 legacy_lookup, score 없음."""
    got = lookup_energy_ef(BASE, "휘발유")
    assert got == EnergyLookup(
        "휘발유", 2.30, "L", "fallback_patch", match("휘발유", "", "휘발유", "L", "legacy_lookup", None)
    )


def test_the_first_definition_479_answers_after_the_resolver_hits_an_empty_factor() -> None:
    """해석은 정규화가 같은 두 줄 가운데 앞 줄(계수 빔)을 고르고 계수가 없어 넘긴다 → `:479` 정확(소문자·공백만)이
    뒤 줄."""
    db = energy_db(("가상연료(A)", "L", None), ("가상연료a", "L", 0.93))
    got = lookup_energy_ef(db, "가상연료a")
    assert (got.name, got.ef, got.via, got.match.match_type, got.match.score) == (
        "가상연료a",
        0.93,
        "legacy_479",
        "legacy_lookup",
        None,
    )


def test_an_empty_name_takes_the_first_row_through_479_partial_match() -> None:
    """코랩 흠 후보(고치지 않음): 빈 이름은 해석이 못 찾고 `:479` 의 「"" ⊂ 이름」 이 첫 줄을 낸다."""
    got = lookup_energy_ef(BASE, "")
    assert (got.name, got.via) == ("전력", "legacy_479")


def test_an_empty_db_goes_to_the_fallback_or_nothing() -> None:
    empty = pd.DataFrame()
    assert lookup_energy_ef(empty, "전력").via == "fallback_patch"
    nothing = lookup_energy_ef(empty, "가상연료")
    assert (nothing.via, nothing.match.match_type) == ("none", "db_empty_or_columns_missing")


# ── C3 계수(사슬 밖) ──

C3_NAME, C3_UNIT, C3_EF = "활동유형(에너지원)", "기준단위", "EF\n(kgCO2eq/단위)"


def c3_db(*rows: tuple[object, object, object]) -> pd.DataFrame:
    return pd.DataFrame([(n, u, e, None) for n, u, e in rows], columns=[C3_NAME, C3_UNIT, C3_EF, "비고"]).astype(object)


C3_BASE = c3_db(("전력", "kWh", 0.0951), ("경유", "L", 0.0952), ("천연가스(LNG)", "kg", 0.0953))


def test_c3_lookup_exact_alias_and_contains() -> None:
    assert lookup_energy_ef_c3(C3_BASE, "전력") == C3Lookup("전력", 0.0951, "kWh", "exact_raw")
    # 「도시가스」 → 후보 도시가스(LNG)(없음) → 천연가스(LNG) — 발열량 다리를 타는 대체 매칭(rest C3 4번)
    assert lookup_energy_ef_c3(C3_BASE, "도시가스") == C3Lookup("천연가스(LNG)", 0.0953, "kg", "alias_exact")
    assert lookup_energy_ef_c3(c3_db(("가상연료혼합", "L", 0.0954)), "가상연료") == C3Lookup(
        "가상연료혼합", 0.0954, "L", "contains"
    )


def test_c3_lookup_does_not_use_the_energy_chain_or_its_fallback() -> None:
    """`에너지_C3` 에 없으면 못 찾음 — 폴백 계수(`:6805`)도 `에너지` 시트도 보지 않는다."""
    assert lookup_energy_ef_c3(C3_BASE, "휘발유") == C3Lookup(None, None, None, "none")
    assert lookup_energy_ef_c3(pd.DataFrame(), "전력") == C3Lookup(None, None, None, "none")


def test_c3_lookup_takes_only_the_first_row_of_each_subset() -> None:
    """정확 줄의 계수가 비면 다음 후보로, 포함 폴백도 첫 줄만 본다 — 그 줄도 계수가 비면 못 찾음(뒤 줄을 보지 않음)."""
    db = c3_db(("전력", "kWh", None), ("가상 전력 손실", "kWh", 0.0955))
    assert lookup_energy_ef_c3(db, "전력") == C3Lookup(None, None, None, "none")
    loss_first = c3_db(("가상 전력 손실", "kWh", 0.0955), ("전력", "kWh", None))
    assert lookup_energy_ef_c3(loss_first, "전력") == C3Lookup("가상 전력 손실", 0.0955, "kWh", "contains")


# ── MARC-ISSUE-395 1번(S3C-r1): `:479` 부르는 자리의 예외 ──


def test_an_error_in_the_first_definition_479_falls_back_like_the_colab(monkeypatch: pytest.MonkeyPatch) -> None:
    """코랩 셀 24(`:6825-6837`)는 붙잡은 `:479` 의 예외를 삼키고 폴백 계수로 간다 — 시트가 실패하지 않는다. 사슬 끝
    (`:7508` 이 해석 줄을 못 찾은 뒤)에서도 같다. R2(열 이름이 글자가 아니면 `:479` 가 TypeError)는 그대로 둔다."""

    def broken(db: pd.DataFrame, energy_name: object) -> tuple[object, object, object]:
        raise TypeError("가상: 글자가 아닌 열 이름")

    monkeypatch.setattr(energy, "lookup_energy_ef_479", broken)
    assert energy.lookup_energy_ef_6822(BASE, "휘발유") == ("휘발유", 2.30, "L", "fallback_patch")
    assert energy.lookup_energy_ef_6822(BASE, "가상연료없음") == (None, None, None, "none")
    found = lookup_energy_ef(energy_db(("가상다른것", "L", 9.1)), "휘발유")
    assert (found.name, found.ef, found.unit, found.via) == ("휘발유", 2.30, "L", "fallback_patch")


def test_any_error_in_479_falls_back_not_only_a_type_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """코랩은 `TypeError` 뒤에도 `except Exception: pass` 로 모든 예외를 삼킨다 — `KeyError` 도 폴백(검증 R3)."""

    def missing(db: pd.DataFrame, energy_name: object) -> tuple[object, object, object]:
        raise KeyError("가상 열")

    monkeypatch.setattr(energy, "lookup_energy_ef_479", missing)
    assert energy.lookup_energy_ef_6822(BASE, "휘발유") == ("휘발유", 2.30, "L", "fallback_patch")
