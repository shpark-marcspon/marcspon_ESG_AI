"""S3C-c1b-2 C14 프랜차이즈 — 처리 때 `standardize_c14_sheet`(`:5590`, rename 만) → 셀 25 `:7623`(매핑 칸), 최종 값은
결과 후처리 `_fix_result_energy_sheet`(`:8862` → `_fix_calc_energy_usage_row` `:8277`). 값은 손셈이고 계수는 지은 것
(support `에너지` — 전력 0.0941 kWh · 경유 0.942 L).

T2 C14 손셈(후처리로만 생기는 칸 — 배출계수·EF단위·EF매핑명·배출량·계산식, 사용량은 환산값으로 덮임 · 단위 힌트) ·
후처리 예외 → 처리 때 값(그 칸이 없음) · T4 줄 json.
"""

from typing import Any, cast

import pandas as pd
import pytest

from esgapi.inventory.engines.scope3.colab_157 import energy, product
from esgapi.inventory.engines.scope3.colab_157.energy import EnergyLookup
from esgapi.inventory.engines.scope3.colab_157.pipeline import ColabRun
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.tests.engines.scope3.colab_157.support import C14_ROW, Value, c14_sheet, row_input
from esgapi.inventory.tests.engines.scope3.colab_157.test_product_use_sheet import (
    DIESEL,
    ELEC,
    SCHEMA,
    column,
    fail,
    processed,
    run_on,
)

KWH_ROW: list[Value] = ["가상국", "가상가맹B", 95, "전력", 92000, "kWh", None]
MWH_ROW: list[Value] = ["가상국", "가상가맹C", 9, "전력", 92, "MWh", None]


def rows_json(result: ColabRun) -> list[dict[str, Any]]:
    sheets = cast("list[dict[str, Any]]", result_to_dict(result, SCHEMA)["sheets"])
    return cast("list[dict[str, Any]]", sheets[0]["rows"])


def formula(usage: float, ef: float, emission: float) -> str:
    return f"배출량(tCO2e) = 사용량 × EF / 1000 = {usage:g} × {ef:g} / 1000 = {emission:g}"


def test_c14_rows_are_the_postprocessed_values() -> None:
    frame = processed(run_on([c14_sheet("c14_프랜차이즈", C14_ROW, KWH_ROW, MWH_ROW)])).frame
    usage = [9100.0, 92000.0, 92000.0]  # MWh 줄은 환산값으로 덮임(`:8865`)
    efs = [DIESEL, ELEC, ELEC]
    emissions = [u * ef / 1000.0 for u, ef in zip(usage, efs, strict=True)]
    assert column(frame, "사용량") == usage
    assert column(frame, "배출계수(kgCO2eq/단위)") == efs
    assert column(frame, "EF단위") == ["L", "kWh", "kWh"]
    assert column(frame, "EF매핑명") == ["경유", "전력", "전력"]
    assert column(frame, "단위환산비고") == [None, None, "MWh→kWh (×1000)"]
    assert column(frame, "배출량(tCO2e)") == emissions
    assert column(frame, "계산식") == [formula(u, ef, e) for u, ef, e in zip(usage, efs, emissions, strict=True)]
    assert column(frame, "EF매핑방식") == ["exact_raw"] * 3  # `:7623`(처리 때)
    assert column(frame, "EF매핑점수") == [1.0, 1.0, 0.95]
    assert column(frame, "가맹점수") == [9, 95, 9]  # rename(`:5600`)


def test_without_the_postprocess_c14_has_no_emission_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """C14 는 본 고리 갈래가 없어(`:6070-6192`) 계수·배출량은 후처리로만 생긴다 — 후처리 실패면 처리 때 꼴."""
    monkeypatch.setattr(energy, "fix_calc_energy_usage_row", fail)
    monkeypatch.setattr(product, "fix_calc_energy_usage_row", fail)
    result = run_on([c14_sheet("c14_프랜차이즈", MWH_ROW)])
    frame = processed(result).frame
    for name in ("배출계수(kgCO2eq/단위)", "EF단위", "배출량(tCO2e)", "계산식"):
        assert name not in frame.columns
    assert column(frame, "사용량") == [92]
    (row,) = rows_json(result)
    assert (row["co2e"], row["factor"], row["missing"]) == (None, None, ["factor"])
    assert row["activity"] == {"value": "92.0", "unit": "MWh", "baseValue": None, "baseUnit": "MWh", "note": None}
    assert row["match"] == {"type": "exact_raw", "score": "0.95"}


def test_the_c14_chain_gets_the_unit_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[object, object]] = []
    original = energy.lookup_energy_ef

    def spy(db: pd.DataFrame, energy_name: object, unit_hint: object = None) -> EnergyLookup:
        seen.append((energy_name, unit_hint))
        return original(db, energy_name, unit_hint=unit_hint)

    monkeypatch.setattr(energy, "lookup_energy_ef", spy)
    monkeypatch.setattr(product, "lookup_energy_ef", spy)
    run_on([c14_sheet("c14_프랜차이즈", MWH_ROW)])
    # 매핑 칸(`:7623`) · 후처리(`:8285`) · 채운 템플릿의 커서 표준화(`:9382` — `std_fn` 이 `:7623` 판이라
    # 매핑 칸을 다시)
    assert seen == [("전력", "MWh")] * 3


def test_c14_row_json_keeps_the_raw_usage_and_the_formula() -> None:
    (row,) = rows_json(run_on([c14_sheet("c14_프랜차이즈", MWH_ROW)]))
    emission = 92000.0 * ELEC / 1000.0
    assert row == {
        "rowId": "c14_프랜차이즈!3",
        "kind": "franchise",
        "month": None,
        "activity": {
            "value": "92.0", "unit": "MWh", "baseValue": "92000.0", "baseUnit": "kWh", "note": "MWh→kWh (×1000)",
        },
        "factor": {
            "sheet": "에너지", "title": "전력", "value": "0.0941", "unit": "kWh", "column": "CO2eq ★\n(kgCO2eq/단위)",
            "code": None,
        },
        "co2e": repr(emission),
        "unit": "tCO2eq",
        "formula": formula(92000.0, ELEC, emission),
        "match": {"type": "exact_raw", "score": "0.95"},
        "allocation": None,
        "biogenic": None,
        "product": None,
        "investment": None,
        "origin": "rule",
        "originSteps": [
            {"step": "unit", "origin": "rule", "via": "rule"},
            {"step": "factor", "origin": "rule", "via": "exact_raw"},
        ],
        "missing": [],
        "input": row_input(country="가상국", name="가상가맹C", energy="전력", stores="9.0"),
    }  # fmt: skip
