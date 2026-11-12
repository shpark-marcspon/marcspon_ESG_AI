"""감사 기록 읽기(core/service/selectors/audit.py 의 list_audit_events — AU1a)를 진짜 DB 로 잰다. 업무 층.

권한 표의 줄(user_audit_list)은 커밋 ③ 이 더한다 — 여기서는 시험만 그 줄을 세운다(setitem, 제품 표는 그대로).
재는 것: 첫 줄 권한(고객사 kind 는 쿼리 0) · 고른 회사 ∪ 회사 없는 줄, 남의 회사 줄 0 · 거르기 넷 · 새 것 먼저 · 쪽 ·
count 는 거른 뒤 · KST 날짜의 경계.
AU1b-1 ①: q 갈래(대상 글자 ∪ 행위자 id 집합, 빈 집합이면 대상 글자만) · 보는 범위의 서로 다른 행위자(_actors) ·
audit_actors_for_search 가 자기 동작(user_audit_list)의 칸을 읽는가.
"""

from datetime import UTC, date, datetime

import pytest
from pytest_django import DjangoAssertNumQueries

from esgapi.core import permissions
from esgapi.core.service.selectors.audit import (
    AuditActor,
    AuditForbidden,
    AuditPage,
    audit_actors_for_search,
    list_audit_actors,
    list_audit_events,
)
from esgapi.core.service.services.audit import AuditRecorded, record_event

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def operator_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_audit_list", permissions.OPERATOR)


def write(company_id: int | None, at: datetime, *, action: str = "login", actor_user_id: int | None = 5) -> int:
    kind = "service" if company_id is not None else "admin"
    done = record_event(
        at=at, company_id=company_id, actor_kind=kind, actor_user_id=actor_user_id, action=action,
        event=f"{action}_done", result="success",
    )  # fmt: skip
    assert isinstance(done, AuditRecorded)
    return done.id


def read(company_id: int, **filters: object) -> AuditPage:
    options: dict[str, object] = {
        "action": None,
        "actor_user_id": None,
        "date_from": None,
        "date_to": None,
        "limit": 20,
        "offset": 0,
        **filters,
    }
    page = list_audit_events(actor_kind="admin", company_id=company_id, **options)  # type: ignore[arg-type]
    assert isinstance(page, AuditPage)
    return page


def ids(page: AuditPage) -> list[int]:
    return [row.id for row in page.rows]


def test_a_customer_kind_is_forbidden_before_anything_is_read(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    write(a, datetime(2026, 10, 1, tzinfo=UTC))
    with django_assert_num_queries(0):
        refused = list_audit_events(
            actor_kind="service", company_id=a, action=None, actor_user_id=None, date_from=None, date_to=None,
            limit=20, offset=0,
        )  # fmt: skip
    assert refused == AuditForbidden()


def test_the_chosen_company_and_the_lines_without_a_company_are_seen_but_not_another_company(
    companies: tuple[int, int],
) -> None:
    a, b = companies
    at = datetime(2026, 10, 1, tzinfo=UTC)
    in_a, in_b, none = write(a, at), write(b, at), write(None, at)
    assert sorted(ids(read(a))) == sorted([in_a, none])
    assert in_b not in ids(read(a))  # 남의 회사 줄 0
    assert sorted(ids(read(b))) == sorted([in_b, none])  # 분모: B 로 읽으면 B 의 줄이 보인다


def test_newest_first_paging_and_count_after_filtering(companies: tuple[int, int]) -> None:
    a, _ = companies
    first = write(a, datetime(2026, 10, 1, tzinfo=UTC))
    second = write(a, datetime(2026, 10, 2, tzinfo=UTC), action="logout")
    third = write(a, datetime(2026, 10, 2, tzinfo=UTC))  # 같은 때 — id 내림
    fourth = write(a, datetime(2026, 10, 3, tzinfo=UTC), actor_user_id=9)
    assert ids(read(a)) == [fourth, third, second, first]
    page = read(a, limit=2, offset=1)
    assert (page.count, ids(page)) == (4, [third, second])
    login = read(a, action="login")
    assert (login.count, ids(login)) == (3, [fourth, third, first])
    by_person = read(a, actor_user_id=9)
    assert (by_person.count, ids(by_person)) == (1, [fourth])
    assert read(a, action="upload").count == 0


def test_dates_are_kst_days_including_both_ends(companies: tuple[int, int]) -> None:
    a, _ = companies
    # KST 10월 2일의 처음과 끝 짝: 10-01T15:00Z = 10-02 00:00 KST, 10-02T14:59:59Z = 10-02 23:59:59 KST
    before = write(a, datetime(2026, 10, 1, 14, 59, 59, tzinfo=UTC))  # 10-01 23:59:59 KST
    start = write(a, datetime(2026, 10, 1, 15, 0, tzinfo=UTC))
    end = write(a, datetime(2026, 10, 2, 14, 59, 59, tzinfo=UTC))
    after = write(a, datetime(2026, 10, 2, 15, 0, tzinfo=UTC))  # 10-03 00:00 KST
    day = date(2026, 10, 2)
    assert ids(read(a, date_from=day, date_to=day)) == [end, start]
    assert ids(read(a, date_from=day)) == [after, end, start]
    assert ids(read(a, date_to=day)) == [end, start, before]
    assert read(a).count == 4  # 분모


# ── AU1b-1 ① q 와 행위자 ────────────────────────────────────────────


def labelled(company_id: int, label: str, actor_user_id: int | None) -> int:
    done = record_event(
        at=datetime(2026, 10, 1, tzinfo=UTC), company_id=company_id, actor_kind="service", actor_user_id=actor_user_id,
        action="upload", event="document_uploaded", result="success", target_label=label,
    )  # fmt: skip
    assert isinstance(done, AuditRecorded)
    return done.id


def test_q_matches_the_target_label_or_the_given_actor_ids(companies: tuple[int, int]) -> None:
    a, _ = companies
    report = labelled(a, "Report.pdf", 7)
    other = labelled(a, "plan.xlsx", 8)
    by_eight = write(a, datetime(2026, 10, 2, tzinfo=UTC), actor_user_id=8)
    assert read(a).count == 3  # 분모
    # 빈 id 집합이면 대상 글자만(대소문자 무시)
    only_label = read(a, q="report", q_actor_ids=frozenset[int]())
    assert (only_label.count, ids(only_label)) == (1, [report])
    # id 집합이 있으면 대상 글자 ∪ 그 사람의 줄
    both = read(a, q="report", q_actor_ids=frozenset({8}))
    assert (both.count, ids(both)) == (3, [by_eight, other, report])
    # q 가 없으면 id 집합은 무시된다
    assert read(a, q=None, q_actor_ids=frozenset({8})).count == 3


def actors(company_id: int) -> tuple[AuditActor, ...]:
    """보는 범위의 행위자(_actors)를 운영 관리자로 읽는다."""
    found = audit_actors_for_search(actor_kind="admin", company_id=company_id)
    assert not isinstance(found, AuditForbidden)
    return found


def test_actors_are_the_distinct_people_of_the_visible_lines(companies: tuple[int, int]) -> None:
    a, b = companies
    at = datetime(2026, 10, 1, tzinfo=UTC)
    write(a, at, actor_user_id=5)
    write(a, at, actor_user_id=5)  # 같은 사람 줄 여럿 → 하나
    write(a, at, actor_user_id=6)
    write(None, at, actor_user_id=1)  # 회사 없는 운영 관리자 줄
    write(b, at, actor_user_id=9)  # 남의 회사 줄의 사람 — 0
    for kind in ("command", "anonymous"):  # id 없는 행위자 — 0
        done = record_event(at=at, company_id=a, actor_kind=kind, actor_user_id=None, action="login",
                            event="login_done", result="success")  # fmt: skip
        assert isinstance(done, AuditRecorded)
    found = actors(a)
    assert sorted(found, key=lambda x: x.actor_user_id) == [
        AuditActor("admin", 1),
        AuditActor("service", 5),
        AuditActor("service", 6),
    ]
    assert sorted(x.actor_user_id for x in actors(b)) == [1, 9]  # 분모: B 로 읽으면 9 가 보인다


def test_actors_for_search_read_the_cell_of_user_audit_list(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    """자기 칸 판별: user_audit_list 칸을 고객사로 바꾸면 service 가 지나고, 남의 칸(user_audit_actors)을 바꾸면
    그대로 막힌다."""
    a, _ = companies
    write(a, datetime(2026, 10, 1, tzinfo=UTC), actor_user_id=5)
    with django_assert_num_queries(0):
        assert audit_actors_for_search(actor_kind="service", company_id=a) == AuditForbidden()
    assert audit_actors_for_search(actor_kind="admin", company_id=a) == (AuditActor("service", 5),)  # 분모
    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_audit_actors", permissions.CUSTOMER)
    assert audit_actors_for_search(actor_kind="service", company_id=a) == AuditForbidden()
    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_audit_actors", permissions.OPERATOR)
    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_audit_list", permissions.CUSTOMER)
    assert audit_actors_for_search(actor_kind="service", company_id=a) == (AuditActor("service", 5),)


def test_list_audit_actors_reads_the_cell_of_user_audit_actors(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    """자기 칸 판별(AU1b-1 ②): user_audit_actors 칸을 고객사로 바꾸면 service 가 지나고, 남의 칸(user_audit_list)을
    바꾸면 그대로 막힌다."""
    a, _ = companies
    write(a, datetime(2026, 10, 1, tzinfo=UTC), actor_user_id=5)
    with django_assert_num_queries(0):
        assert list_audit_actors(actor_kind="service", company_id=a) == AuditForbidden()
    assert list_audit_actors(actor_kind="admin", company_id=a) == (AuditActor("service", 5),)  # 분모
    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_audit_list", permissions.CUSTOMER)
    assert list_audit_actors(actor_kind="service", company_id=a) == AuditForbidden()
    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_audit_list", permissions.OPERATOR)
    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_audit_actors", permissions.CUSTOMER)
    assert list_audit_actors(actor_kind="service", company_id=a) == (AuditActor("service", 5),)
