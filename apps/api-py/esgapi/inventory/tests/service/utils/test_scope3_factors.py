"""Scope 3 줄 계수 수정의 순수 셈(밴드 S3K2b-2 ① — 결정 MARC-ENT-570·442, 발주서 Q5·Q6·Q8). 값은 지어낸 것이다."""

from typing import Any

import pytest

from esgapi.inventory.service.utils.ghg_pool import Invalid
from esgapi.inventory.service.utils.scope3_edits import REASON_BAD, SCOPE3_REASON_MAX
from esgapi.inventory.service.utils.scope3_factors import (
    CUSTOM_BAD,
    RANK_BAD,
    RANK_UNKNOWN,
    SCOPE3_FACTOR_TEXT_MAX,
    TEXT_BAD,
    VALUE_BAD,
    VALUE_NOT_POSITIVE,
    Ai,
    Custom,
    Factor,
    FactorBody,
    Recomputed,
    ai_of,
    check_factor_body,
    chosen,
    editable,
    recompute,
    same_choice,
)
from esgapi.inventory.service.utils.scope3_state import FLOW_ID, RESULT_SHAPE

BOOK = {"sheet": "가상_구매표", "column": "가상 열\n2025 기준"}


def check(choice: Any, rank: int | None = None, custom: Custom | None = None, reason: str = "가상 사유") -> Any:
    return check_factor_body("가상!1", choice, rank, custom, reason, SCOPE3_REASON_MAX, REASON_BAD)


def custom_of(value: str = "1.5", title: str = "가상 계수", source: str = "가상 출처") -> Custom:
    return Custom(title, value, source)


def purchase(**over: Any) -> dict[str, Any]:
    return {
        "rowId": "가상!1",
        "kind": "purchase",
        "amount": "1000.0",
        "factor": {"title": "가상 계수", "value": "0.5", "unit": "kgCO2e/KRW", "column": "가상 열\n2025 기준"},
        "co2e": "0.5",
        "recommendations": [{"title": "가상 추천 1", "value": "0.25", "expectedCo2e": "0.25"}],
    } | over


def waste(fcf: str | None, treatment: str = "소각", **over: Any) -> dict[str, Any]:
    return {
        "rowId": "가상!2",
        "kind": "waste",
        "activity": {"value": "1000.0", "baseValue": "1000.0"},
        "factor": {"sheet": "가상_폐기물표", "title": None, "value": "2.0", "unit": "kgCO2eq/kg"},
        "co2e": "2.0",
        "treatment": treatment,
        "biogenic": {"fossilCo2e": "2.0", "biogenicCo2e": "0.0", "fcf": fcf, "note": "가상"},
    } | over


def can_edit(row: dict[str, Any]) -> bool:
    return editable(row, RESULT_SHAPE, FLOW_ID)


# ── 몸 검사(Q6·짝 규칙) ──


def test_a_custom_value_is_stored_like_the_engine_writes_numbers() -> None:
    body = check("custom", custom=custom_of("0.10", "  가상 계수 ", " 가상 출처\n"))
    assert body == FactorBody("가상!1", "custom", None, Custom("가상 계수", "0.1", "가상 출처"), "가상 사유")


def test_ten_decimals_pass_and_very_small_numbers_keep_the_float_text() -> None:
    assert check("custom", custom=custom_of("0.0000000001")).custom.value == repr(1e-10)


@pytest.mark.parametrize(
    ("value", "why"),
    [
        ("-1", VALUE_BAD),
        ("+1", VALUE_BAD),
        ("0.00000000001", VALUE_BAD),
        ("1e-3", VALUE_BAD),
        ("1E3", VALUE_BAD),
        ("NaN", VALUE_BAD),
        ("inf", VALUE_BAD),
        ("", VALUE_BAD),
        (" 1", VALUE_BAD),
        ("1.", VALUE_BAD),
        (".5", VALUE_BAD),
        ("١", VALUE_BAD),
        ("9" * 400, VALUE_BAD),
        ("0", VALUE_NOT_POSITIVE),
        ("0.0000000000", VALUE_NOT_POSITIVE),
    ],
)
def test_a_custom_value_must_be_a_positive_plain_decimal(value: str, why: str) -> None:
    assert check("custom", custom=custom_of(value)) == Invalid({"custom.value": why})


@pytest.mark.parametrize("text", ["", "   ", "가" * (SCOPE3_FACTOR_TEXT_MAX + 1)], ids=["empty", "blank", "long"])
def test_custom_title_and_source_are_required_and_bounded(text: str) -> None:
    assert check("custom", custom=custom_of(title=text)) == Invalid({"custom.title": TEXT_BAD})
    assert check("custom", custom=custom_of(source=text)) == Invalid({"custom.source": TEXT_BAD})


def test_the_text_limit_counts_after_stripping() -> None:
    assert isinstance(check("custom", custom=custom_of(title=f" {'가' * SCOPE3_FACTOR_TEXT_MAX} ")), FactorBody)


@pytest.mark.parametrize(
    ("choice", "rank", "custom", "fields"),
    [
        ("applied", 1, None, {"rank": RANK_BAD}),
        ("applied", None, custom_of(), {"custom": CUSTOM_BAD}),
        ("recommended", None, None, {"rank": RANK_BAD}),
        ("recommended", 0, None, {"rank": RANK_BAD}),
        ("recommended", 5, None, {"rank": RANK_BAD}),
        ("recommended", 1, custom_of(), {"custom": CUSTOM_BAD}),
        ("custom", None, None, {"custom": CUSTOM_BAD}),
        ("custom", 1, custom_of(), {"rank": RANK_BAD}),
    ],
)
def test_the_pairs_are_closed(choice: Any, rank: int | None, custom: Custom | None, fields: dict[str, str]) -> None:
    assert check(choice, rank, custom) == Invalid(fields)


@pytest.mark.parametrize("reason", ["", "   ", "가" * (SCOPE3_REASON_MAX + 1)], ids=["empty", "blank", "long"])
def test_the_reason_follows_the_exclude_rule(reason: str) -> None:
    assert check("applied", reason=reason) == Invalid({"reason": REASON_BAD})


# ── 식 ──


def test_a_c5_row_splits_like_the_engine_with_the_fcf_of_the_row() -> None:
    """Q8: 화석기원이 co2e, 생물기원은 따로. 나눔이 없는 줄은 전부 화석기원."""
    em = 1000.0 * 3.0 / 1000
    bio = em * (1 - 0.25)
    assert recompute(waste("0.25"), 3.0) == Recomputed(repr(em - bio), repr(bio))
    assert recompute(waste(None), 3.0) == Recomputed(repr(em), repr(0.0))


@pytest.mark.parametrize("fcf", ["0.25", None], ids=["fcf", "no-fcf"])
def test_a_c5_value_that_overflows_has_no_count(fcf: str | None) -> None:
    assert recompute(waste(fcf), 1.7e308) is None


def test_c12_and_c15_have_no_formula() -> None:
    assert recompute({"kind": "product_eol", "activity": {"baseValue": "9.0"}}, 1.0) is None
    assert recompute({"kind": "investment"}, 1.0) is None
    assert recompute({"kind": "가상 종류"}, 1.0) is None


# ── 고칠 수 있음(Q5) ──


def test_a_full_row_is_editable_and_a_row_without_a_found_factor_too() -> None:
    assert can_edit(purchase())
    no_value = purchase(factor={"title": None, "value": None, "unit": "kgCO2e/KRW"}, co2e=None)
    assert can_edit(no_value)


@pytest.mark.parametrize(
    "row",
    [
        purchase(kind="investment"),
        purchase(kind="product_eol"),
        purchase(factor=None),
        purchase(factor={"title": "가상", "value": "0.5", "unit": None}),
        purchase(amount=None),
        purchase(co2e=None),  # 후처리 실패 시트의 줄 꼴 — 본문과 식이 어긋남(R6)
        purchase(co2e="0.6"),
        waste("0.25", activity={"value": "0", "baseValue": "0.0"}),
        waste(None, co2e=None, biogenic={"fossilCo2e": None, "biogenicCo2e": None, "fcf": None, "note": None}),
    ],
    ids=["c15", "c12", "no-factor", "no-unit", "no-amount", "body-null", "body-other", "no-usage", "fcf-lost"],
)
def test_the_rows_that_cannot_be_edited(row: dict[str, Any]) -> None:
    assert not can_edit(row)


def test_the_flow_and_the_result_shape_must_be_the_ones_the_formulas_came_from() -> None:
    assert not editable(purchase(), "가상.result@9", FLOW_ID)
    assert not editable(purchase(), RESULT_SHAPE, "가상.flow@9")


# ── 고름 ──


def test_the_source_is_the_sheet_name_never_the_match_way() -> None:
    assert ai_of(purchase(), BOOK).source == "가상_구매표 가상 열 2025 기준"
    assert ai_of(waste("0.25"), BOOK).source == "가상_폐기물표"


def test_applied_keeps_the_body_letters() -> None:
    found = chosen(FactorBody("가상!1", "applied", None, None, "가"), purchase(), BOOK)
    ai = Ai("가상 계수", "0.5", "가상_구매표 가상 열 2025 기준", "0.5")
    assert found == Factor("applied", None, ai.title, ai.value, ai.source, "kgCO2e/KRW", "0.5", None, ai)


def test_recommended_takes_title_and_value_of_that_rank() -> None:
    found = chosen(FactorBody("가상!1", "recommended", 1, None, "가"), purchase(), BOOK)
    assert isinstance(found, Factor)
    assert (found.title, found.value, found.rank, found.co2e) == ("가상 추천 1", "0.25", 1, "0.25")
    assert found.source == found.ai.source


@pytest.mark.parametrize(
    "row",
    [
        purchase(),
        purchase(recommendations=[{"title": "가상", "value": None, "expectedCo2e": None}, {}]),
        waste(None),
    ],
    ids=["past-the-end", "no-value", "not-purchase"],
)
def test_a_rank_the_row_does_not_have_is_refused(row: dict[str, Any]) -> None:
    rank = 2
    assert chosen(FactorBody("가상!1", "recommended", rank, None, "가"), row, BOOK) == Invalid({"rank": RANK_UNKNOWN})


def test_rank_one_is_the_first_recommendation_not_the_second() -> None:
    row = purchase(recommendations=[{"title": "첫째", "value": "0.1"}, {"title": "둘째", "value": "0.2"}])
    found = chosen(FactorBody("가상!1", "recommended", 1, None, "가"), row, BOOK)
    assert isinstance(found, Factor)
    assert found.title == "첫째"


def test_a_row_that_cannot_be_counted_gives_none_not_an_error() -> None:
    body = FactorBody("가상!1", "custom", None, Custom("가", "1.0", "가"), "가")
    assert chosen(body, purchase(amount=None), BOOK) is None


def test_same_choice_compares_stored_letters_and_no_event_means_the_original() -> None:
    body = FactorBody("가상!1", "custom", None, Custom("가", "1.0", "나"), "가")
    wanted = chosen(body, purchase(), BOOK)
    assert isinstance(wanted, Factor)
    assert same_choice(wanted, body, wanted)
    assert not same_choice(None, body, wanted)
    applied = FactorBody("가상!1", "applied", None, None, "가")
    original = chosen(applied, purchase(), BOOK)
    assert isinstance(original, Factor)
    assert same_choice(None, applied, original)
    assert not same_choice(wanted, applied, original)
