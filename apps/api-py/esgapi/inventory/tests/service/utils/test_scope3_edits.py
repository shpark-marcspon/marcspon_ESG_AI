"""Scope 3 줄 덧판의 순수 셈(밴드 S3K2b-1 ① — service/utils/scope3_edits.py). 값·이름은 지어낸 것이다."""

from datetime import UTC, datetime

import pytest

from esgapi.inventory.service.utils.ghg_pool import Invalid
from esgapi.inventory.service.utils.scope3_edits import (
    FACTOR_AXIS,
    REASON_BAD,
    ROW_AXIS,
    ROW_IDS_EMPTY,
    ROW_IDS_MAX,
    ROW_IDS_REPEATED,
    ROW_IDS_TOO_MANY,
    SCOPE3_REASON_MAX,
    EditKind,
    Event,
    check_body,
    edited_rows,
    excluded_of,
    fold,
    rows_of,
)

AT = datetime(2026, 3, 1, tzinfo=UTC)


def event(id_: int, row_id: str, kind: EditKind = "exclude", *, run_id: int = 1, category: str = "C5") -> Event:
    return Event(
        id=id_,
        run_id=run_id,
        category=category,
        row_id=row_id,
        kind=kind,
        reason="가상 사유",
        at=AT,
        actor_user_id=7,
        batch_id=None,
    )


def test_the_body_passes_and_gives_the_stripped_reason() -> None:
    assert check_body(["가상!1"], "  가상 사유\n") == "가상 사유"
    assert check_body(["가상!1", "가상!2"], "가" * SCOPE3_REASON_MAX) == "가" * SCOPE3_REASON_MAX
    assert check_body([f"가상!{n}" for n in range(ROW_IDS_MAX)], "가") == "가"


@pytest.mark.parametrize(
    ("row_ids", "reason", "fields"),
    [
        ([], "가", {"rowIds": ROW_IDS_EMPTY}),
        ([f"가상!{n}" for n in range(ROW_IDS_MAX + 1)], "가", {"rowIds": ROW_IDS_TOO_MANY}),
        (["가상!1", "가상!1"], "가", {"rowIds": ROW_IDS_REPEATED}),
        (["가상!1"], "", {"reason": REASON_BAD}),
        (["가상!1"], " \t\n ", {"reason": REASON_BAD}),
        (["가상!1"], "가" * (SCOPE3_REASON_MAX + 1), {"reason": REASON_BAD}),
        ([], "", {"rowIds": ROW_IDS_EMPTY, "reason": REASON_BAD}),
    ],
    ids=["no-rows", "over-max", "repeated", "empty-reason", "blank-reason", "long-reason", "both"],
)
def test_the_body_refuses(row_ids: list[str], reason: str, fields: dict[str, str]) -> None:
    assert check_body(row_ids, reason) == Invalid(fields)


def test_the_reason_limit_counts_after_stripping() -> None:
    assert isinstance(check_body(["가상!1"], f"  {'가' * SCOPE3_REASON_MAX}  "), str)


def test_fold_keeps_the_largest_id_whatever_the_order() -> None:
    first, second = event(1, "가상!1"), event(2, "가상!1", "restore")
    assert fold([second, first]) == {(1, "가상!1", ROW_AXIS): second}
    assert fold([first, second]) == {(1, "가상!1", ROW_AXIS): second}


def test_fold_keeps_runs_apart() -> None:
    """570: 같은 rowId 도 실행이 다르면 다른 줄이다."""
    old, new = event(1, "가상!1", run_id=1), event(2, "가상!1", "restore", run_id=2)
    assert fold([old, new]) == {(1, "가상!1", ROW_AXIS): old, (2, "가상!1", ROW_AXIS): new}


def test_fold_keeps_the_two_axes_apart() -> None:
    """계수 사건이 제외 상태를 가리지 않는다(P3) — 열쇠에 축이 든다."""
    out, fixed = event(1, "가상!1"), event(2, "가상!1", "factor")
    assert fold([out, fixed]) == {(1, "가상!1", ROW_AXIS): out, (1, "가상!1", FACTOR_AXIS): fixed}
    assert excluded_of(fold([out, fixed]), 1, "C5") == {"가상!1"}


def test_edited_rows_count_only_rows_away_from_the_original() -> None:
    now = fold(
        [
            event(1, "가상!1"),
            event(2, "가상!2"),
            event(3, "가상!2", "restore"),  # 제외 뒤 복구 = 원안
            event(4, "가상!3", category="C11"),
            event(5, "가상!4", run_id=2),
        ]
    )
    assert edited_rows(now, 1, "C5") == 1
    assert edited_rows(now, 1, "C11") == 1
    assert edited_rows(now, 2, "C5") == 1
    assert edited_rows(now, 3, "C5") == 0
    assert excluded_of(now, 1, "C5") == {"가상!1"}


def test_rows_of_reads_every_processed_sheet_of_the_category() -> None:
    body: dict[str, object] = {
        "sheets": [
            {"sheet": "가", "category": "Category4", "status": "processed", "rows": [{"rowId": "가!1"}]},
            {"sheet": "나", "category": "Category4", "status": "processed", "rows": [{"rowId": "나!1"}, {"x": 1}]},
            {"sheet": "다", "category": "Category4", "status": "failed"},
            {"sheet": "라", "category": "Category5", "status": "processed", "rows": [{"rowId": "라!1"}]},
            "모르는 꼴",
        ]
    }
    assert rows_of(body, "C4") == {"가!1", "나!1"}
    assert rows_of(body, "C6") == frozenset()
    assert rows_of(None, "C4") == frozenset()
