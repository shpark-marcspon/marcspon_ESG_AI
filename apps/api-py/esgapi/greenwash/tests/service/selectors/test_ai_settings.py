# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""AI 설정 판의 목록·잠금 읽기(밴드 G2c3 §3-1 — MARC-ISSUE-229). 업무 층: 진짜 DB(주인 역할).

    3-1-1  목록·목록 조립·잠금의 SQL 에 기준표 칸("criteria") 0 — 대조: 한 판 읽기는 싣고, 잠금은 FOR UPDATE
    3-1-2  비지 않은 쪽은 문 하나, 빈 쪽(offset ≥ 전체)은 문 둘이고 셈·적용 판이 맞음
    3-1-3  값: 판 셋·적용 하나·남의 판 둘에서 total·applied_id·id 차례·상태가 따로 센 값과 같다

기준 글은 지어낸 것이다(synthetic).
"""

import copy
from datetime import UTC, datetime

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.flows.criteria_e0 import default_criteria
from esgapi.greenwash.models import GreenwashAiSettingRow
from esgapi.greenwash.service.actions import ai_settings as actions
from esgapi.greenwash.service.selectors import ai_settings as selectors
from esgapi.greenwash.service.services import ai_settings as services

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 20, 1, 0, tzinfo=UTC)
CRITERIA = '"criteria"'


def edited(text: str) -> GreenwashCriteria:
    criteria = copy.deepcopy(default_criteria())
    criteria["rows"][9]["text"] = text
    return criteria


def three(company_id: int) -> list[int]:
    """판 셋(v1·v2·v3), v2 를 적용했다가 v3 으로 → v1 은 testing, v2 는 past, v3 은 applied."""
    ids: list[int] = []
    for i in range(3):
        created = services.create_setting(
            company_id=company_id,
            created_by_user_id=9,
            title=f"지어낸 판 {i}",
            criteria=edited(f"지어낸 글 {i}"),
            memo="",
        )
        assert isinstance(created, services.Created)
        ids.append(created.id)
    services.apply_setting(company_id=company_id, setting_id=ids[1], now=NOW)
    services.apply_setting(company_id=company_id, setting_id=ids[2], now=NOW)
    return ids


def sqls(queries: CaptureQueriesContext) -> list[str]:
    return [q["sql"] for q in queries.captured_queries]


@pytest.fixture
def world(companies: tuple[int, int]) -> tuple[int, int, list[int]]:
    a, b = companies
    ids = three(a)
    for i in range(2):
        services.create_setting(
            company_id=b, created_by_user_id=9, title=f"남의 판 {i}", criteria=edited(f"남의 글 {i}"), memo=""
        )
    return a, b, ids


# ── 3-1-1 기준표 칸을 싣지 않음 ──


def test_the_list_and_the_lock_never_read_the_criteria(world: tuple[int, int, list[int]]) -> None:
    a, _, ids = world
    with CaptureQueriesContext(connection) as page:
        selectors.ai_setting_page(company_id=a, limit=20, offset=0)
    with CaptureQueriesContext(connection) as listed:
        actions.setting_list(actor_kind="admin", company_id=a, limit=20, offset=0)
    with transaction.atomic(), CaptureQueriesContext(connection) as locked:
        selectors.lock_settings(a)
    with CaptureQueriesContext(connection) as detail:
        selectors.ai_setting_detail(company_id=a, setting_id=ids[0])
    for name, captured in {"page": page, "list": listed, "lock": locked}.items():
        assert sqls(captured), name  # 분모: 문이 있다
        assert [s for s in sqls(captured) if CRITERIA in s] == [], name
    assert [s for s in sqls(detail) if CRITERIA in s]  # 대조: 한 판 읽기는 싣는다(잡기가 그 글자를 본다)
    assert [s for s in sqls(locked) if "FOR UPDATE" in s]  # 대조: 잠금 문이 잡혔다


def test_the_list_and_the_lock_never_read_the_model_settings(world: tuple[int, int, list[int]]) -> None:
    """AS2b: 모델 설정 칸("model_settings")도 목록·잠금은 싣지 않는다(HEAD_FIELDS 그대로). 대조: 한 판 읽기는
    싣는다."""
    a, _, ids = world
    with CaptureQueriesContext(connection) as page:
        selectors.ai_setting_page(company_id=a, limit=20, offset=0)
    with transaction.atomic(), CaptureQueriesContext(connection) as locked:
        selectors.lock_settings(a)
    with CaptureQueriesContext(connection) as detail:
        selectors.ai_setting_detail(company_id=a, setting_id=ids[0])
    for name, captured in {"page": page, "lock": locked}.items():
        assert sqls(captured), name  # 분모: 문이 있다
        assert [s for s in sqls(captured) if '"model_settings"' in s] == [], name
    assert [s for s in sqls(detail) if '"model_settings"' in s]  # 대조: 한 판 읽기는 싣는다


def test_the_lock_keeps_id_name_and_applied(world: tuple[int, int, list[int]]) -> None:
    a, _, ids = world
    with transaction.atomic():
        locked = selectors.lock_settings(a)
    assert list(locked.values()) == [
        selectors.SettingLock(ids[0], "v1", False),
        selectors.SettingLock(ids[1], "v2", False),
        selectors.SettingLock(ids[2], "v3", True),
    ]


# ── 3-1-2 문 수 ──


def test_a_non_empty_page_is_one_statement(world: tuple[int, int, list[int]]) -> None:
    a, _, ids = world
    with CaptureQueriesContext(connection) as queries:
        page = selectors.ai_setting_page(company_id=a, limit=2, offset=1)
    assert len(queries.captured_queries) == 1, sqls(queries)
    assert (page.total, page.applied_id, [s.id for s in page.items]) == (3, ids[2], [ids[1], ids[0]])


@pytest.mark.parametrize("offset", [3, 50])
def test_an_empty_page_still_counts(world: tuple[int, int, list[int]], offset: int) -> None:
    a, _, ids = world
    with CaptureQueriesContext(connection) as queries:
        page = selectors.ai_setting_page(company_id=a, limit=20, offset=offset)
    assert len(queries.captured_queries) == 2, sqls(queries)
    assert (page.total, page.applied_id, page.items) == (3, ids[2], ())


def test_a_company_without_versions_is_zero_and_default(companies: tuple[int, int]) -> None:
    a, _ = companies
    page = selectors.ai_setting_page(company_id=a, limit=20, offset=0)
    assert (page.total, page.applied_id, page.items) == (0, None, ())


# ── 3-1-3 값 ──


def test_the_page_values_match_a_separate_count(world: tuple[int, int, list[int]]) -> None:
    a, b, ids = world
    page = selectors.ai_setting_page(company_id=a, limit=20, offset=0)
    rows = GreenwashAiSettingRow.for_company(a)
    expected_applied = rows.filter(applied=True).values_list("id", flat=True).first()
    assert (page.total, page.applied_id) == (rows.count(), expected_applied) == (3, ids[2])
    assert [s.id for s in page.items] == list(rows.order_by("-id").values_list("id", flat=True)) == ids[::-1]
    assert [selectors.status_of(s.applied, s.applied_at) for s in page.items] == ["applied", "past", "testing"]
    assert all(isinstance(s, selectors.AiSettingHead) and not hasattr(s, "criteria") for s in page.items)
    other = selectors.ai_setting_page(company_id=b, limit=20, offset=0)
    assert (other.total, other.applied_id) == (2, None)  # 분모: 남의 판은 거기 있다
    assert not {s.id for s in other.items} & set(ids)
