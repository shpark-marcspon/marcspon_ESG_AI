"""응답 바닥의 꼴(밴드 E2): 시각 +09:00(③)."""

import json
import re
from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from django.test import Client
from ninja import Schema

from esgapi.core.schemas import (
    CursorPage,
    DateOnly,
    KstDateTime,
    LimitOffsetPage,
    PageNumberPage,
    limit_offset_page,
    page_number_page,
    to_seoul_iso,
)
from tests.support.http import login

KST_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{6})?\+09:00$")


# ── ⓓ 바꾸기 ──


def test_utc_near_midnight_moves_to_the_next_seoul_day() -> None:
    assert to_seoul_iso(datetime(2026, 10, 16, 15, 30, tzinfo=UTC)) == "2026-10-17T00:30:00+09:00"
    assert to_seoul_iso(datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)) == "2027-01-01T08:59:59+09:00"


def test_microseconds_are_kept_and_other_offsets_are_moved() -> None:
    value = datetime(2026, 10, 14, 1, 20, 30, 123456, tzinfo=UTC)
    assert to_seoul_iso(value) == "2026-10-14T10:20:30.123456+09:00"
    assert to_seoul_iso(datetime(2026, 10, 14, 10, 0, tzinfo=timezone(timedelta(hours=-5)))) == (
        "2026-10-15T00:00:00+09:00"
    )


def test_a_naive_datetime_is_refused() -> None:
    with pytest.raises(ValueError, match="naive"):
        to_seoul_iso(datetime(2026, 10, 16, 12, 0))


class _Sample(Schema):
    at: KstDateTime
    maybe: KstDateTime | None
    day: DateOnly


def test_the_types_serialise_in_python_and_json_modes() -> None:
    sample = _Sample(at=datetime(2026, 10, 16, 15, 0, tzinfo=UTC), maybe=None, day=date(2026, 10, 17))
    expected = {"at": "2026-10-17T00:00:00+09:00", "maybe": None, "day": "2026-10-17"}
    assert sample.model_dump() == expected  # ninja 가 쓰는 꼴(python 모드)에서도 글자다
    assert json.loads(sample.model_dump_json()) == expected


# ── 업무 층: 실제 응답 ──


@pytest.mark.django_db
def test_the_exchange_answers_its_expiry_in_seoul_time(client: Client, tenants: None) -> None:
    body = login(client)
    assert KST_ISO.match(body["expiresAt"]), body["expiresAt"]
    me = client.get("/api/me").json()
    assert KST_ISO.match(me["expiresAt"]), me["expiresAt"]


# ── ⓖ 목록의 꼴 셋 ──


class _Item(Schema):
    n: int


class _ItemPage(LimitOffsetPage[_Item]):
    pass


def test_limit_offset_page() -> None:
    assert limit_offset_page(12, 0, [1, 2, 3, 4, 5]) == {"count": 12, "isNext": True, "results": [1, 2, 3, 4, 5]}
    assert limit_offset_page(12, 10, [11, 12])["isNext"] is False
    assert limit_offset_page(0, 0, []) == {"count": 0, "isNext": False, "results": []}
    page = _ItemPage.model_validate(limit_offset_page(1, 0, [{"n": 1}]))
    assert page.model_dump() == {"count": 1, "isNext": False, "results": [{"n": 1}]}


def test_a_subclass_keeps_its_own_schema_name() -> None:
    assert _ItemPage.model_json_schema()["title"] == "_ItemPage"
    assert set(_ItemPage.model_json_schema()["properties"]) == {"count", "isNext", "results"}


@pytest.mark.parametrize(
    ("count", "page", "size", "expected"),
    [
        (25, 1, 10, (3, True, False)),
        (25, 3, 10, (3, False, True)),
        (20, 2, 10, (2, False, True)),
        (0, 1, 10, (0, False, False)),
    ],
)
def test_page_number_page(count: int, page: int, size: int, expected: tuple[int, bool, bool]) -> None:
    out = page_number_page(count, page, size, [])
    assert (out["totalPages"], out["hasNext"], out["hasPrevious"]) == expected
    assert set(out) == set(PageNumberPage[_Item].model_fields)
    assert (out["page"], out["pageSize"], out["count"]) == (page, size, count)


def test_cursor_page_shape() -> None:
    page = CursorPage[_Item](count=3, cursor=None, results=[_Item(n=1)])
    assert page.model_dump() == {"count": 3, "cursor": None, "results": [{"n": 1}]}
    assert set(CursorPage[_Item].model_fields) == {"count", "cursor", "results"}
