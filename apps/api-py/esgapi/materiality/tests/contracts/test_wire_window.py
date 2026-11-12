"""contracts/wire.py 의 조사 기간 창(밴드 IR2b — MARC-ENT-425 ②): dateRange 문법, 항목 날짜 읽기, 1부 결과
복사본에서 기간 밖 항목 빼기와 경고(발주서 §3 S1·S2). 「오늘」은 고정 날짜로 넘긴다. 기대값은 손으로 적었다.
결과·항목은 전부 지어낸 「가상…」이다.

사례 표(WINDOW_RANGE_CASES·WINDOW_ITEM_CASES)는 자기검증 스크립트(scripts/materiality_compare_ir2b.py)가 표로
다시 적는다.
"""

import copy
import json
from datetime import date
from typing import Any

import pytest

from esgapi.materiality.contracts import wire

TODAY = date(2025, 6, 30)
"""고정 「오늘」 — 실제 날짜와 다른 값(시계를 읽으면 빨개진다)."""

WINDOW_RANGE_CASES: list[tuple[str, tuple[date, date] | None]] = [
    ("2024-01-01~오늘까지", (date(2024, 1, 1), TODAY)),
    ("  2024-01-01 ~ 오늘까지  ", (date(2024, 1, 1), TODAY)),
    ("2024-01-01~2024-12-31", (date(2024, 1, 1), date(2024, 12, 31))),
    ("2024-02-29~2024-03-01", (date(2024, 2, 29), date(2024, 3, 1))),
    ("2024-05-05~2024-05-05", (date(2024, 5, 5), date(2024, 5, 5))),
    ("2025-06-30~오늘까지", (TODAY, TODAY)),
    ("2025-02-29~오늘까지", None),
    ("2024-13-01~오늘까지", None),
    ("2024-01-01~2024-02-30", None),
    ("2025-01-02~2025-01-01", None),
    ("2025-07-01~오늘까지", None),
    ("", None),
    ("최근 1년", None),
    ("2024-01-01", None),
    ("~오늘까지", None),
    ("2024-1-01~오늘까지", None),
    ("2024-01-01~오늘", None),
    ("2024-01-01T00:00~오늘까지", None),
    ("２０２４-01-01~오늘까지", None),
]
"""(dateRange 글, 기대 (시작, 끝) 또는 None — 오늘 = TODAY)."""

WINDOW_ITEM_CASES: list[tuple[object, date | None]] = [
    ("2025-03-02", date(2025, 3, 2)),
    ("  2025-03-02 ", date(2025, 3, 2)),
    ("2024-02-29", date(2024, 2, 29)),
    ("2025-02-29", None),
    ("2024-03", None),
    ("2024", None),
    ("2024-03-01T09:00:00", None),
    ("2024/03/01", None),
    ("", None),
    (None, None),
    (20240301, None),
]
"""(항목 날짜 칸 값, 기대 날짜 또는 None = 못 읽음)."""


# ── S1 창 문법 ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("text", "expected"), WINDOW_RANGE_CASES)
def test_date_range_grammar(text: str, expected: tuple[date, date] | None) -> None:
    assert wire.parse_date_range(text, TODAY) == expected


def test_date_range_that_is_not_text_is_unreadable() -> None:
    assert wire.parse_date_range(None, TODAY) is None
    assert wire.parse_date_range(["2024-01-01~오늘까지"], TODAY) is None


def test_until_today_follows_the_given_today_not_the_clock() -> None:
    assert wire.parse_date_range("2000-01-01~오늘까지", date(2001, 2, 3)) == (date(2000, 1, 1), date(2001, 2, 3))
    assert wire.parse_date_range("2001-02-04~오늘까지", date(2001, 2, 3)) is None


def test_date_range_text_is_read_not_rewritten() -> None:
    received = {"dateRange": "  2024-01-01 ~ 오늘까지  "}
    before = copy.deepcopy(received)
    wire.parse_date_range(received["dateRange"], TODAY)
    assert received == before


@pytest.mark.parametrize(("value", "expected"), WINDOW_ITEM_CASES)
def test_item_date(value: object, expected: date | None) -> None:
    assert wire.item_date(value) == expected


# ── S2 거르기 ──────────────────────────────────────────────────────────────────────────────

START, END = date(2025, 1, 1), date(2025, 12, 31)


def reg(title: str, *, publish: object = None, event: object = None) -> dict[str, Any]:
    return {"title": title, "event_date": event, "publish_date": publish, "primary_url": "https://example.com/r"}


def con(title: str, day: object) -> dict[str, Any]:
    return {"title": title, "date": day, "url": "https://example.com/c"}


def done(parsed: Any) -> dict[str, Any]:
    return {"status": "done", "parsed": parsed, "items": [], "selfCheck": None, "topicNameMismatch": False}


def failed(raw: str) -> dict[str, Any]:
    return {"status": "failed", "raw": raw, "parseError": "가상", "failure": {"kind": "unparsable", "message": "x"}}


NOT_RUN: dict[str, Any] = {"status": "not_run", "message": "가상"}


def topic(name: str, regulation: dict[str, Any], controversy: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic": name,
        "description": f"{name}의 설명",
        "keywordStr": "가상",
        "regulation": regulation,
        "controversy": controversy,
    }


def result_of(*topics: dict[str, Any]) -> dict[str, Any]:
    return {"schemaVersion": "materiality.result@1", "part1": {"topics": list(topics)}, "warnings": []}


def titles(elements: list[Any]) -> list[Any]:
    return [e["title"] if isinstance(e, dict) else e for e in elements]


def test_regulation_results_by_region_drop_out_of_range_and_keep_the_bounds() -> None:
    parsed = {
        "topic_name": "가상토픽 하나",
        "results": {
            "KR": [
                reg("시작 날", publish="2025-01-01"),
                reg("하루 앞", publish="2024-12-31"),
                reg("끝 날", publish="2025-12-31"),
            ],
            "EU": [reg("하루 뒤", publish="2026-01-01"), reg("안", publish="2025-06-01")],
            "US": [],
            "note": "가상 글",
        },
    }
    got, warnings = wire.part1_in_window(result_of(topic("가상토픽 하나", done(parsed), NOT_RUN)), START, END)
    results = got["part1"]["topics"][0]["regulation"]["parsed"]["results"]
    assert titles(results["KR"]) == ["시작 날", "끝 날"]
    assert titles(results["EU"]) == ["안"]
    assert results["US"] == []
    assert results["note"] == "가상 글"
    assert warnings == [
        {
            "code": "items_out_of_range",
            "message": "규제 항목 2건 뺌(기간 2025-01-01~2025-12-31) — 2부 입력에서만, part1 은 그대로.",
            "topic": "가상토픽 하나",
            "phase": "regulation",
            "subtopic": None,
        }
    ]


def test_regulation_items_list_shape() -> None:
    parsed = {"items": [reg("안", publish="2025-02-01"), reg("밖", publish="2023-02-01")], "results": ["그대로"]}
    got, _ = wire.part1_in_window(result_of(topic("가상", done(parsed), NOT_RUN)), START, END)
    after = got["part1"]["topics"][0]["regulation"]["parsed"]
    assert titles(after["items"]) == ["안"]
    assert after["results"] == ["그대로"]  # 셀 33 규칙: items 가 먼저 — results 는 보지 않는다


def test_regulation_results_list_shape() -> None:
    parsed = {"results": [reg("안", publish="2025-02-01"), reg("밖", publish="2023-02-01")]}
    got, _ = wire.part1_in_window(result_of(topic("가상", done(parsed), NOT_RUN)), START, END)
    assert titles(got["part1"]["topics"][0]["regulation"]["parsed"]["results"]) == ["안"]


def test_regulation_publish_date_wins_then_event_date() -> None:
    parsed = {
        "results": {
            "KR": [
                reg("publish 밖·event 안", publish="2024-06-01", event="2025-06-01"),
                reg("publish null·event 안", publish=None, event="2025-06-01"),
                reg("publish 못 읽음·event 밖", publish="2025-06", event="2024-06-01"),
                reg("둘 다 null"),
                reg("publish 2024-03", publish="2024-03"),
            ]
        }
    }
    got, warnings = wire.part1_in_window(result_of(topic("가상", done(parsed), NOT_RUN)), START, END)
    kept = got["part1"]["topics"][0]["regulation"]["parsed"]["results"]["KR"]
    assert titles(kept) == ["publish null·event 안", "둘 다 null", "publish 2024-03"]
    assert [(w["code"], w["message"]) for w in warnings] == [
        ("items_out_of_range", "규제 항목 2건 뺌(기간 2025-01-01~2025-12-31) — 2부 입력에서만, part1 은 그대로."),
        ("item_date_unreadable", "규제 항목 2건 날짜 못 읽어 남김."),
    ]


def test_controversy_results_items_and_items_shapes() -> None:
    nested = {"topic_name": "가상", "results": {"items": [con("안", "2025-07-07"), con("밖", "2026-01-01")]}}
    flat = {"items": [con("밖", "2024-12-31"), con("못 읽음", "2025"), con("null", None), "글 원소", 3]}
    got, warnings = wire.part1_in_window(
        result_of(topic("가상 A", NOT_RUN, done(nested)), topic("가상 B", NOT_RUN, done(flat))), START, END
    )
    a, b = got["part1"]["topics"]
    assert titles(a["controversy"]["parsed"]["results"]["items"]) == ["안"]
    assert titles(b["controversy"]["parsed"]["items"]) == ["못 읽음", "null", "글 원소", 3]
    assert [(w["code"], w["topic"], w["phase"], w["message"]) for w in warnings] == [
        (
            "items_out_of_range",
            "가상 A",
            "controversy",
            "컨트로버시 항목 1건 뺌(기간 2025-01-01~2025-12-31) — 2부 입력에서만, part1 은 그대로.",
        ),
        (
            "items_out_of_range",
            "가상 B",
            "controversy",
            "컨트로버시 항목 1건 뺌(기간 2025-01-01~2025-12-31) — 2부 입력에서만, part1 은 그대로.",
        ),
        ("item_date_unreadable", "가상 B", "controversy", "컨트로버시 항목 2건 날짜 못 읽어 남김."),
    ]


def test_controversy_results_without_items_list_falls_back_to_items() -> None:
    parsed = {"results": {"items": "글"}, "items": [con("밖", "2020-01-01")]}
    got, _ = wire.part1_in_window(result_of(topic("가상", NOT_RUN, done(parsed))), START, END)
    after = got["part1"]["topics"][0]["controversy"]["parsed"]
    assert after["items"] == []
    assert after["results"] == {"items": "글"}


def test_unknown_shapes_failed_and_not_run_stay_as_they_are() -> None:
    unknown = {"answer": [reg("밖", publish="2020-01-01")]}
    given = result_of(
        topic("가상 A", done(unknown), failed('{"results": {"KR": []}}')),
        topic("가상 B", NOT_RUN, done({"results": {"items": [con("밖", "2020-01-01")]}, "x": 1})),
        topic("가상 C", done(["목록 답"]), NOT_RUN),
    )
    got, warnings = wire.part1_in_window(given, START, END)
    a, b, c = got["part1"]["topics"]
    assert a == given["part1"]["topics"][0]
    assert c == given["part1"]["topics"][2]
    assert b["regulation"] == NOT_RUN
    assert b["controversy"]["parsed"] == {"results": {"items": []}, "x": 1}
    assert [w["topic"] for w in warnings] == ["가상 B"]


def test_all_items_out_dumps_empty_lists_not_the_none_text() -> None:
    parsed = {"topic_name": "가상", "results": {"KR": [reg("밖", publish="2020-01-01")], "EU": []}}
    received = {"topics": [{"topic": "가상", "description": "가상 설명"}]}
    got, _ = wire.part1_in_window(result_of(topic("가상", done(parsed), NOT_RUN)), START, END)
    text = wire.context_text(wire.bundle_of_regulation(got["part1"]["topics"][0]["regulation"]), "regulation")
    expected: dict[str, Any] = {
        "parsed": {"topic_name": "가상", "results": {"KR": [], "EU": []}},
        "raw": None,
        "parse_error": None,
    }
    assert text == json.dumps(expected, ensure_ascii=False, indent=2)
    assert text != wire.NO_REGULATION_TEXT
    assert received["topics"][0]["topic"] == "가상"


def test_the_given_result_is_not_changed_and_items_view_is_kept() -> None:
    parsed = {"results": {"KR": [reg("밖", publish="2020-01-01"), reg("안", publish="2025-01-01")]}}
    cell = done(parsed)
    cell["items"] = [{"title": "밖"}, {"title": "안"}]
    given = result_of(topic("가상", cell, done({"items": [con("밖", "2030-01-01")]})))
    before = copy.deepcopy(given)
    got, _ = wire.part1_in_window(given, START, END)
    assert given == before
    assert got["part1"]["topics"][0]["regulation"]["items"] == [{"title": "밖"}, {"title": "안"}]
    assert got is not given
    assert got["part1"]["topics"][0]["regulation"]["parsed"] is not parsed


def test_no_warning_when_nothing_is_dropped_or_unreadable() -> None:
    parsed = {"results": {"KR": [reg("안", publish="2025-05-05")]}}
    got, warnings = wire.part1_in_window(
        result_of(topic("가상", done(parsed), done({"items": [con("안", "2025-05-05")]}))), START, END
    )
    assert warnings == []
    assert titles(got["part1"]["topics"][0]["regulation"]["parsed"]["results"]["KR"]) == ["안"]


def test_warning_order_is_topic_then_regulation_then_controversy() -> None:
    """두 토픽이 같은 parsed 객체를 나눠 써도(JSON 왕복 전 값) 칸마다 따로 거른다."""
    reg_parsed = {"results": {"KR": [reg("밖", publish="2020-01-01"), reg("못 읽음")]}}
    con_parsed = {"items": [con("밖", "2020-01-01")]}
    _, warnings = wire.part1_in_window(
        result_of(topic("가상 A", done(reg_parsed), done(con_parsed)), topic("가상 B", NOT_RUN, done(con_parsed))),
        START,
        END,
    )
    assert [(w["topic"], w["phase"], w["code"]) for w in warnings] == [
        ("가상 A", "regulation", "items_out_of_range"),
        ("가상 A", "regulation", "item_date_unreadable"),
        ("가상 A", "controversy", "items_out_of_range"),
        ("가상 B", "controversy", "items_out_of_range"),
    ]
