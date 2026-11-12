"""Scope 3 연도 상태의 셈(밴드 S3K2a ① — service/utils/scope3_state.py). 순수 층.

R 고르기(Q6 — 만든 차례 첫 「done + 결과 done」, 후보 거름) · Q11 갈래 넷 · 수 글자 · 상위 5·share(Q9) · 이름 상수.
값·이름은 지어낸 것이다.
"""

from collections.abc import Mapping
from decimal import Decimal

from esgapi.inventory.flows.binding_157 import FLOW_ID
from esgapi.inventory.flows.scope3_colab_157 import RESULT_SHAPE
from esgapi.inventory.service.utils import scope3_state as s3
from esgapi.inventory.service.utils.scope3_state import Candidate, Value


def processed(n: int, *co2e: str | None) -> dict[str, object]:
    return {
        "sheet": f"가상_C{n}",
        "category": f"Category{n}",
        "status": "processed",
        "rows": [{"rowId": f"가상!{i}", "co2e": value} for i, value in enumerate(co2e)],
    }


def sheet(n: int, status: str) -> dict[str, object]:
    return {"sheet": f"가상_C{n}", "category": f"Category{n}", "status": status}


def done(*sheets: dict[str, object]) -> dict[str, object]:
    return {"schemaVersion": RESULT_SHAPE, "status": "done", "reportYear": 2025, "sheets": list(sheets)}


REJECTED: Mapping[str, object] = {"schemaVersion": RESULT_SHAPE, "status": "rejected", "rejected": {}}


def run(
    run_id: int, status: str = "done", *, year: object = 2025, flow: str = FLOW_ID, purpose: str = "service"
) -> Candidate:
    return Candidate(id=run_id, status=status, flow_id=flow, purpose=purpose, options={"reportYear": year})


def test_the_constants_match_the_engine_and_the_screen() -> None:
    assert (s3.FLOW_ID, s3.RESULT_SHAPE) == (FLOW_ID, RESULT_SHAPE)
    assert s3.CATEGORIES == ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C11", "C12", "C13", "C14", "C15")
    assert tuple(s3.CATEGORY_NAMES) == s3.CATEGORIES
    # 마크스폰 용어(박세현 11-10): 임차 자산(밴드 S3V1 덧 5)·운송(밴드 S3T1) 모두 업스트림·다운스트림
    assert (s3.CATEGORY_NAMES["C4"], s3.CATEGORY_NAMES["C9"]) == ("업스트림 운송 및 유통", "다운스트림 운송 및 유통")
    assert (s3.CATEGORY_NAMES["C8"], s3.CATEGORY_NAMES["C13"]) == ("업스트림 임차 자산", "다운스트림 임차 자산")
    assert s3.engine_category("C12") == "Category12"


def test_base_run_is_the_first_done_with_a_done_result_in_creation_order() -> None:
    bodies: dict[int, Mapping[str, object] | None] = {9: REJECTED, 8: done(), 7: done()}
    asked: list[int] = []

    def result_of(run_id: int) -> Mapping[str, object] | None:
        asked.append(run_id)
        return bodies.get(run_id)

    candidates = [
        run(12, "processing"),
        run(11, "failed"),
        run(10, "done", purpose="test"),  # 시험 실행 — 후보 밖(latest 에도 안 듦)
        run(9),  # 결과 rejected — 건너뜀
        run(13, year=2024),  # 다른 해
        run(14, flow="scope3.llm-first@1"),  # 다른 흐름
        run(8),  # R
        run(7),  # 더 읽지 않는다
    ]
    base = s3.base_run(candidates, 2025, result_of)
    assert (base.latest, base.run_id) == ((12, "processing"), 8)
    assert asked == [9, 8]  # done 후보에만, 새 것부터, R 에서 멈춤


def test_no_base_run_keeps_the_latest() -> None:
    base = s3.base_run([run(3, "failed"), run(2, "queued")], 2025, lambda _: None)
    assert (base.latest, base.run_id, base.body) == ((3, "failed"), None, None)
    assert s3.base_run([], 2025, lambda _: None).latest is None


def test_a_boolean_or_text_report_year_is_not_the_year() -> None:
    assert not s3.counts_for_year(run(1, year=True), 1)
    assert not s3.counts_for_year(run(1, year="2025"), 2025)
    assert s3.counts_for_year(run(1), 2025)


def test_the_four_branches_of_q11() -> None:
    body = done(
        processed(4, "1.5", "2.25", None, "nan"),
        sheet(4, "failed"),
        sheet(5, "failed"),
        sheet(6, "empty"),
        sheet(7, "not_yet_supported"),
        processed(8, None),
    )
    assert s3.category_value(body, "C4") == Value(Decimal("3.75"), 1, 1)  # processed(실패 섞임)
    assert s3.category_value(body, "C5") == Value(None, 0, 1)  # failed 만
    assert s3.category_value(body, "C6") == Value(None, 0, 0)  # empty
    assert s3.category_value(body, "C7") == Value(None, 0, 0)  # not_yet_supported
    assert s3.category_value(body, "C9") == Value(None, 0, 0)  # 시트 없음
    assert s3.category_value(body, "C8") == Value(None, 1, 0)  # processed 인데 수 0
    assert s3.category_value(None, "C4") == Value(None, 0, 0)
    assert s3.category_value(REJECTED, "C4") == Value(None, 0, 0)
    assert [s3.lockable(s3.category_value(body, c)) for c in ("C4", "C5", "C6", "C8")] == [True, False, False, True]


def test_two_processed_sheets_of_one_category_add_up_exactly() -> None:
    body = done(processed(1, "0.1", "0.2"), processed(1, "1e-05", "-0.0"))
    assert s3.category_value(body, "C1") == Value(Decimal("0.30001"), 2, 0)


def test_number_reads_only_the_web_number_shape() -> None:
    assert [s3.number(t) for t in ("12.5", "1e-05", "-3", "-0.0")] == [
        Decimal("12.5"),
        Decimal("0.00001"),
        Decimal(-3),
        Decimal(0),
    ]
    assert [s3.number(t) for t in ("nan", "inf", "", " 1", "1\n", "1,000", None, 3)] == [None] * 8


def test_top_categories_drop_null_keep_zero_and_negative_and_break_ties_by_number() -> None:
    values: dict[str, Decimal | None] = {
        "C1": Decimal(5),
        "C2": None,
        "C3": Decimal(0),
        "C4": Decimal(5),
        "C5": Decimal(-1),
        "C11": Decimal(9),
        "C12": Decimal(2),
    }
    whole = s3.scope3_total(values.values())
    assert whole == Decimal(20)
    top = s3.top_categories(values, whole)
    assert [(r.category, r.value, r.share) for r in top] == [
        ("C11", Decimal(9), Decimal("45.0")),
        ("C1", Decimal(5), Decimal("25.0")),
        ("C4", Decimal(5), Decimal("25.0")),
        ("C12", Decimal(2), Decimal("10.0")),
        ("C3", Decimal(0), Decimal("0.0")),
    ]
    assert top[0].name == "판매된 제품의 사용"


def test_share_is_null_when_the_scope3_total_is_zero() -> None:
    values: dict[str, Decimal | None] = {"C1": Decimal(2), "C2": Decimal(-2)}
    whole = s3.scope3_total(values.values())
    assert whole == 0
    assert [r.share for r in s3.top_categories(values, whole)] == [None, None]
    assert s3.scope3_total([None, None]) is None
    assert s3.top_categories({"C1": None}, None) == ()


def test_a_row_id_that_cannot_be_hashed_keeps_the_body_value() -> None:
    """561 L5: 결과 본문의 rowId 가 글자가 아니어도 500 이 아니라 본문 값 그대로."""
    sheet = {"category": "Category1", "status": "processed", "rows": [{"rowId": ["가상"], "co2e": "1.5"}]}
    body = {"status": "done", "sheets": [sheet]}
    assert s3.category_value(body, "C1", frozenset({"가상!1"}), {"가상!1": "9.0"}).total == Decimal("1.5")
