"""Scope 1·2 입력의 순수 도움말(service/utils/entries.py — 밴드 S12a ①·S12a-2 ①). DB 0.

값은 지어낸 것이다(실제 계수 0).
"""

import json
import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from esgapi.inventory.calc.entry_emission import Gas, emission
from esgapi.inventory.data_loader import read_data
from esgapi.inventory.models import InventoryEntryValue
from esgapi.inventory.service.utils.entries import (
    HISTORY_KINDS,
    PERIODS,
    RESTORABLE,
    RESTORE_KIND,
    RESTORE_LOCKED,
    RESTORE_STALE,
    RESTORE_TOP,
    SLOT_PATTERN,
    CustomView,
    amount_problem,
    conversions_of,
    custom_gases,
    custom_version,
    gases_of,
    reason_text,
    restore_problem,
    row_total,
    slots,
    sum_or_none,
    unit_options,
)
from esgapi.inventory.service.utils.ghg_pool import FactorDraft, FactorValues, GasDraft, check_factor

CONVERSIONS = conversions_of(read_data("unit-conversions.json")["unitConversions"])  # type: ignore[arg-type]


def test_a_year_has_twelve_month_slots() -> None:
    found = slots(2025)
    assert found == tuple(f"2025-{month:02d}" for month in range(1, 13))
    assert all(re.fullmatch(SLOT_PATTERN, slot) for slot in found)  # DB CHECK 와 같은 글자


def test_the_model_check_carries_the_slot_pattern() -> None:
    """모델 CHECK 의 글자가 SLOT_PATTERN 이다(469 R3 — DB 의 글자는 makemigrations --check 가 지킨다)."""
    (check,) = [c for c in InventoryEntryValue._meta.constraints if c.name == "inventory_entry_values_slot_format"]
    assert str(SLOT_PATTERN) in str(check)


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("month", tuple(f"2025-{month:02d}" for month in range(1, 13))),
        ("quarter", ("2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4")),
        ("year", ("2025",)),
    ],
)
def test_each_period_has_its_slots(period: str, expected: tuple[str, ...]) -> None:
    assert slots(2025, period) == expected
    assert all(re.fullmatch(SLOT_PATTERN, slot) for slot in expected)  # DB CHECK 와 같은 글자
    assert all(len(slot) <= 7 for slot in expected)  # 값·히스토리의 slot 칸 char 7


def test_the_periods_do_not_share_a_slot() -> None:
    found = [slot for period in PERIODS for slot in slots(2025, period)]
    assert len(found) == len(set(found)) == 12 + 4 + 1  # 주기를 바꾸면 옛 칸은 새 주기 칸이 아니다(숨김 — 판단 E)


def test_an_unknown_period_is_refused() -> None:
    with pytest.raises(ValueError, match="입력주기"):
        slots(2025, "week")


@pytest.mark.parametrize("slot", ["2025-Q0", "2025-Q5", "2025-q1", "2025Q1", "2025-", "202", "2025-H1"])
def test_a_slot_out_of_the_pattern(slot: str) -> None:
    assert re.fullmatch(SLOT_PATTERN, slot) is None


def test_the_restorable_kinds_are_history_kinds() -> None:
    assert set(RESTORABLE) <= set(HISTORY_KINDS)
    assert {"na_on", "na_off", "unit"}.isdisjoint(RESTORABLE)  # 판단 F — 단위 줄은 복구 안 됨
    assert all(len(kind) <= 10 for kind in HISTORY_KINDS)  # 히스토리 kind 칸 char 10


def test_a_sum_beyond_28_digits_is_kept() -> None:
    """470 M3: Decimal(30,12) 둘의 합(정수 18 + 소수 12 = 30자리)이 기본 문맥 28자리에서 잘리지 않는다."""
    big = Decimal("999999999999999999.999999999999")
    assert sum_or_none([big, big]) == Decimal("1999999999999999999.999999999998")
    assert row_total(False, [big, big]) == Decimal("1999999999999999999.999999999998")
    assert sum_or_none([None, None]) is None and row_total(True, [big]) is None


def custom(gases: list[dict[str, object]], **fields: object) -> CustomView:
    """지어낸 직접입력 보기(투입 kL · 순발열량 끔 · kg/kL)."""
    values: dict[str, object] = {
        "id": 1,
        "name": "가 직접 계수",
        "source": "지어낸 출처",
        "base_year": 2024,
        "tier": 1,
        "country_code": "KR",
        "industry_code": "other",
        "input_unit": ("volume", "kL"),
        "ncv": None,
        "ncv_unit": None,
        "factor_unit": "kg/kL",
        "gases": gases_of(gases),
        "note": "",
        "created_at": datetime(2026, 10, 29, tzinfo=UTC),
    } | fields
    return CustomView(**values)  # type: ignore[arg-type]


def test_a_custom_factor_counts_only_enabled_gases_with_values() -> None:
    """직접입력 → 셈 칸: 켠 가스만, 계수·GWP 가 다 있는 것만(판의 calc_version 과 같은 꼴)."""
    version = custom_version(
        custom(
            [
                {"gas": "CO2", "enabled": True, "factor": "2.5", "gwp": "1"},
                {"gas": "CH4", "enabled": True, "factor": "0.01", "gwp": "30"},
                {"gas": "N2O", "enabled": False, "factor": "9", "gwp": "9"},
                {"gas": "HFCs", "enabled": True, "factor": None, "gwp": "100"},
            ]
        )
    )
    assert version.gases == (Gas(Decimal("2.5"), Decimal(1)), Gas(Decimal("0.01"), Decimal(30)))
    # 손셈: 4 kL × (2.5×1 + 0.01×30) kg/kL = 4 × 2.8 = 11.2 kg = 0.0112 t
    assert emission(Decimal(4), "kL", version, CONVERSIONS) == Decimal("0.011200000000")


def test_a_custom_factor_with_ncv_goes_through_energy() -> None:
    version = custom_version(
        custom(
            [{"gas": "CO2", "enabled": True, "factor": "5", "gwp": "1"}],
            ncv=Decimal(2),
            ncv_unit=("energy", "TJ"),
            factor_unit="kg/TJ",
        )
    )
    # 손셈: 3 kL × 2 TJ/kL × 5 kg/TJ = 30 kg = 0.03 t
    assert emission(Decimal(3), "kL", version, CONVERSIONS) == Decimal("0.030000000000")


def test_checked_gases_go_to_json_and_back_unchanged() -> None:
    """S20 검사(check_factor)를 지난 가스 → JSON 글자 → 다시 Decimal: 값이 그대로(검증 5d 권고 1)."""
    checked = check_factor(
        FactorDraft(
            name="가 직접 계수",
            source="지어낸 출처",
            base_year=2024,
            tier=1,
            country_code="KR",
            industry_code="other",
            input_unit=("mass", "kg"),
            emission_unit=None,
            ncv_enabled=False,
            ncv=None,
            ncv_unit=None,
            factor_unit=None,
            gases=(
                GasDraft("CO2", enabled=True, factor="0.000000000123", gwp="1"),
                GasDraft("CH4", enabled=True, factor="123456789012345678.5", gwp="28.000"),
            ),
            note="",
        )
    )
    assert isinstance(checked, FactorValues), checked
    lines = custom_gases(checked.gases)
    assert all(isinstance(line["factor"], str | None) and "E" not in str(line["factor"]) for line in lines)
    assert gases_of(lines) == checked.gases
    assert json.loads(json.dumps(lines)) == lines  # JSON 한 칸에 그대로 든다


def test_unreadable_gas_text_is_an_empty_value_not_an_error() -> None:
    """넣는 길 밖의 글자(손으로 고친 행 — 앱 역할에 UPDATE 없음)는 빈 값이라 셈에 안 든다(500 0)."""
    (gas,) = gases_of([{"gas": "CO2", "enabled": True, "factor": "두 배", "gwp": "1e3"}])
    assert (gas.factor, gas.gwp) == (None, None)
    assert custom_version(custom([{"gas": "CO2", "enabled": True, "factor": "x", "gwp": "1"}])).gases == ()


def test_restore_problem_order_and_reason_text() -> None:
    """복구 판정(판단 D): 종류 → 맨 위 → 잠김 → 낡음 차례로 첫 하나. None = restorable."""
    assert [kind for kind in HISTORY_KINDS if restore_problem(kind, top=False, locked=False, stale=False)] == [
        "na_on",
        "na_off",
        "unit",
    ]
    assert restore_problem("unit", top=True, locked=True, stale=True) == RESTORE_KIND
    assert restore_problem("value", top=True, locked=True, stale=True) == RESTORE_TOP
    assert restore_problem("period", top=False, locked=True, stale=True) == RESTORE_LOCKED
    assert restore_problem("factor", top=False, locked=False, stale=True) == RESTORE_STALE
    assert restore_problem("factor", top=False, locked=False, stale=False) is None
    assert (reason_text(None), reason_text("  "), reason_text(" 가 ")) == (None, None, "가")


@pytest.mark.parametrize("text", ["0", "1", "12.5", "0.000001", "123456789012345678", "123456789012345678.123456"])
def test_an_amount_in_form_is_taken(text: str) -> None:
    assert amount_problem(text) is None


@pytest.mark.parametrize(
    "text",
    ["", "-1", "+1", "1e3", "1E3", "0.0000001", "1234567890123456789", "1,000", " 1", "١٢", "NaN", "Infinity", "."],
)
def test_an_amount_out_of_form_is_refused(text: str) -> None:
    assert amount_problem(text) is not None


def test_an_amount_refusal_reads_as_the_e6_wording() -> None:
    """칸 오류 글 둘은 e6 확정 글 그대로(sid:MARC-ISSUE-589)."""
    form = "0 이상의 숫자로 입력해 주세요. 정수 부분은 18자리까지, 1E+5 같은 지수 표기 없이 넣어 주세요"
    assert amount_problem("1e3") == form
    assert amount_problem("0.0000001") == "소수점 아래는 6자리까지 입력할 수 있어요"


def test_conversions_keep_the_pairs_as_they_are() -> None:
    assert CONVERSIONS[("kL", "L")] == Decimal(1000)
    assert CONVERSIONS[("MJ", "TJ")] == Decimal("0.000001")
    assert ("L", "kL") in CONVERSIONS and ("TJ", "kWh") not in CONVERSIONS  # 역·다단 유도 0
    assert len(CONVERSIONS) == len(read_data("unit-conversions.json")["unitConversions"])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("leaf", "expected"),
    [
        ("kL", ("kL", "L", "m3")),  # 부피: L → kL · m3 → kL 쌍이 있다(Nm3·kNm3 는 없다)
        ("kg", ("kg", "g", "t")),
        ("t", ("t", "g", "kg")),
        ("TJ", ("TJ", "MJ", "GJ")),
        ("MWh", ("MWh", "kWh", "GWh")),
        ("Nm3", ("Nm3", "kNm3")),
    ],
)
def test_unit_options_are_the_leaf_unit_and_paired_units_of_the_same_kind(leaf: str, expected: tuple[str, ...]) -> None:
    assert unit_options(leaf, CONVERSIONS) == expected


def test_unit_options_of_an_unknown_unit_are_itself() -> None:
    assert unit_options("lb", CONVERSIONS) == ("lb",)
