"""감사 기록 조회 경로(AU1a ③ — GET /audit-logs, 운영 관리자 전용 AD-05). 업무 층.

주인 역할 연결에서 잰다(앱 역할의 경계는 보안 층 tests/security/test_audit.py 의 ⓗⓘⓙ).
줄은 record_event 로 2025 년에 심고 dateFrom·dateTo 로 그 해만 본다 — 시험이 만든 운영 관리자의 로그인·비밀번호 바꾸기
줄(지금 시각, 회사 없음)이 쪽에 섞이지 않게. 재는 것: 칸 전부 · 고른 회사 ∪ 회사 없는 줄 · 새 것 먼저 · 쪽·count ·
거르기 넷 · 꼴 422 · 없는 회사 404 · 고객사 403(몸 앞) · 이름 풀기(지금 이름, 남의 회사 null, 쿼리 수).
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from django.test import Client, override_settings
from pytest_django import DjangoAssertNumQueries

from esgapi.core.models import AuditEventRow
from esgapi.core.service.selectors import audit as audit_selectors
from esgapi.core.service.services.audit import AuditRecorded, record_event
from esgapi.user.models import User
from esgapi.user.service.apis import audit as audit_api
from esgapi.user.service.selectors.user import find_admin, names_of
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair

pytestmark = pytest.mark.django_db

PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"
YEAR = "&dateFrom=2025-01-01&dateTo=2025-12-31"
OUT_KEYS = {
    "id",
    "at",
    "companyId",
    "actorKind",
    "actorUserId",
    "actorName",
    "actorUsername",
    "action",
    "event",
    "result",
    "reason",
    "targetKind",
    "targetId",
    "targetLabel",
    "changedFields",
    "module",
    "requestId",
}


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


def customer(company_id: int, username: str, name: str = "김담당") -> int:
    created = create_customer_user(
        actor_kind="admin", company_id=company_id, username=username, name=name, password=PASSWORD
    )
    assert isinstance(created, UserCreated), created
    return created.user_id


def operator(username: str = "ops", name: str = "운영자") -> int:
    created = create_operator(username=username, name=name, password=PASSWORD)
    assert isinstance(created, UserCreated), created
    return created.user_id


def changed_access(client: Client, *, username: str, subdomain: str | None) -> str:
    """로그인하고 비밀번호를 한 번 바꿔(is_initial 끔) 새 access."""
    first = bearer_pair(client, username=username, password=PASSWORD, company_subdomain=subdomain)
    changed = client.post(
        "/api/users/me/password",
        data={"currentPassword": PASSWORD, "newPassword": CHANGED},
        content_type="application/json",
        **bearer(first["access"]),
    )
    assert changed.status_code == 200, changed.content.decode()
    return changed.json()["access"]


def operator_access(client: Client) -> str:
    operator()
    return changed_access(client, username="ops", subdomain=None)


def write(
    company_id: int | None,
    at: datetime,
    *,
    actor_kind: str = "service",
    actor_user_id: int | None = None,
    action: str = "login",
    event: str = "login_succeeded",
) -> int:
    done = record_event(
        at=at, company_id=company_id, actor_kind=actor_kind, actor_user_id=actor_user_id, action=action,
        event=event, result="success",
    )  # fmt: skip
    assert isinstance(done, AuditRecorded), done
    return done.id


def logs(client: Client, access: str, query: str) -> Any:
    return client.get(f"/api/audit-logs?{query}", **bearer(access))


def page_ids(response: Any) -> list[int]:
    assert response.status_code == 200, response.content.decode()
    return [line["id"] for line in response.json()["results"]]


def error(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def at(day: int, hour: int = 3) -> datetime:
    return datetime(2025, 3, day, hour, tzinfo=UTC)


# ── 쪽 ──────────────────────────────────────────────────────────────


def test_an_operator_reads_the_chosen_company_and_the_companyless_lines_newest_first(
    client: Client, companies: tuple[int, int]
) -> None:
    a, b = companies
    access = operator_access(client)
    old = write(a, at(1))
    other = write(b, at(2))
    none = write(None, at(3), actor_kind="command")
    new = write(a, at(4))
    response = logs(client, access, f"companyId={a}{YEAR}")
    assert page_ids(response) == [new, none, old]
    assert other not in page_ids(logs(client, access, f"companyId={a}&limit=100"))  # 남의 회사 줄 0
    body = response.json()
    assert (body["count"], body["isNext"]) == (3, False)
    assert all(set(line) == OUT_KEYS for line in body["results"])
    # 쪽: count 는 거른 뒤의 전부, isNext 는 다음 쪽이 있는가
    first = logs(client, access, f"companyId={a}{YEAR}&limit=2").json()
    second = logs(client, access, f"companyId={a}{YEAR}&limit=2&offset=2").json()
    assert [line["id"] for line in first["results"]] == [new, none]
    assert (first["count"], first["isNext"]) == (3, True)
    assert [line["id"] for line in second["results"]] == [old]
    assert (second["count"], second["isNext"]) == (3, False)
    # 분모: 회사 B 를 고르면 B 의 줄과 회사 없는 줄
    assert page_ids(logs(client, access, f"companyId={b}{YEAR}")) == [none, other]


def test_every_field_of_a_line_is_in_the_contract_shape(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    ops = User.admin_by_id(operator("ops2", "둘째 운영자")).get()
    kim = customer(a, "kim", "김담당")
    done = record_event(
        at=datetime(2025, 3, 1, 15, 30, tzinfo=UTC), company_id=a, actor_kind="admin", actor_user_id=ops.pk,
        action="setting_change", event="user_updated", result="success", target_kind="user", target_id=kim,
        target_label="kim", changed_fields=("name", "is_active"),
    )  # fmt: skip
    assert isinstance(done, AuditRecorded)
    failed = write(None, at(1), actor_kind="anonymous")
    lines = logs(client, access, f"companyId={a}{YEAR}").json()["results"]
    assert lines[0] == {
        "id": done.id,
        "at": "2025-03-02T00:30:00+09:00",
        "companyId": a,
        "actorKind": "admin",
        "actorUserId": ops.pk,
        "actorName": "둘째 운영자",
        "actorUsername": "ops2",
        "action": "setting_change",
        "event": "user_updated",
        "result": "success",
        "reason": None,
        "targetKind": "user",
        "targetId": kim,
        "targetLabel": "kim",
        "changedFields": ["name", "is_active"],
        "requestId": None,
        "module": None,  # 모듈과 무관한 줄
    }
    assert lines[1]["id"] == failed
    assert (lines[1]["companyId"], lines[1]["actorKind"], lines[1]["actorUserId"]) == (None, "anonymous", None)
    assert (lines[1]["actorName"], lines[1]["actorUsername"], lines[1]["changedFields"]) == (None, None, None)


# ── 거르기 ─────────────────────────────────────────────────────────


def test_the_four_filters(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    kim, lee = customer(a, "kim"), customer(a, "lee")
    login_kim = write(a, at(1), actor_user_id=kim)
    upload_kim = write(a, at(2), actor_user_id=kim, action="upload", event="document_uploaded")
    login_lee = write(a, at(3), actor_user_id=lee)
    # KST 의 하루: 3월 4일 14:59Z = 3월 4일 23:59 KST, 15:00Z = 3월 5일 00:00 KST
    late = write(a, datetime(2025, 3, 4, 14, 59, tzinfo=UTC), actor_user_id=lee)
    next_day = write(a, datetime(2025, 3, 4, 15, 0, tzinfo=UTC), actor_user_id=lee)
    assert page_ids(logs(client, access, f"companyId={a}{YEAR}&action=upload")) == [upload_kim]
    assert page_ids(logs(client, access, f"companyId={a}{YEAR}&actorUserId={kim}")) == [upload_kim, login_kim]
    assert page_ids(logs(client, access, f"companyId={a}&dateFrom=2025-03-04&dateTo=2025-03-04")) == [late]
    assert page_ids(logs(client, access, f"companyId={a}&dateFrom=2025-03-05&dateTo=2025-03-05")) == [next_day]
    assert page_ids(logs(client, access, f"companyId={a}&dateFrom=2025-03-02&dateTo=2025-03-03")) == [
        login_lee,
        upload_kim,
    ]
    # 분모: 거르지 않으면 다섯 다
    assert len(page_ids(logs(client, access, f"companyId={a}{YEAR}"))) == 5


@pytest.mark.parametrize(
    "query",
    [
        "action=export",
        "action=settingChange",
        "actorUserId=0",
        "dateFrom=2025-13-01",
        "dateTo=yesterday",
        "limit=0",
        "limit=101",
        "offset=-1",
        "dateTo=9999-12-31",
        "dateFrom=0001-01-01",
        "dateFrom=1999-12-31",
        "dateTo=3000-01-01",
        "q=",
        pytest.param("q=" + "가" * 151, id="q=<151자>"),
    ],
)
def test_a_query_out_of_shape_is_422(client: Client, companies: tuple[int, int], query: str) -> None:
    a, _ = companies
    access = operator_access(client)
    assert logs(client, access, f"companyId={a}&{query}").status_code == 422
    assert logs(client, access, f"companyId={a}").status_code == 200  # 분모


def test_dates_are_bounded_2000_to_2999_and_outside_is_a_validation_error(
    client: Client, companies: tuple[int, int]
) -> None:
    """ⓙ 날짜 범위(MARC-ISSUE-192 의 1): 끝 값은 지나고(200), 밖은 VALIDATION_ERROR 422(500 이 아니다)."""
    a, _ = companies
    access = operator_access(client)
    edges = logs(client, access, f"companyId={a}&dateFrom=2000-01-01&dateTo=2999-12-31")
    assert edges.status_code == 200, edges.content.decode()
    for query in ("dateTo=9999-12-31", "dateFrom=0001-01-01", "dateFrom=1999-12-31", "dateTo=3000-01-01"):
        assert error(logs(client, access, f"companyId={a}&{query}")) == (422, "VALIDATION_ERROR"), query


def test_an_unknown_company_is_404(client: Client, companies: tuple[int, int]) -> None:
    access = operator_access(client)
    assert error(logs(client, access, "companyId=9000000")) == (404, "COMPANY_NOT_FOUND")
    assert error(logs(client, access, "")) == (400, "COMPANY_AMBIGUOUS")  # 회사가 둘(/users 와 같은 규칙)


# ── 권한 ──────────────────────────────────────────────────────────


def test_a_customer_gets_403_before_the_body_reads_anything(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    write(a, at(1))
    customer(a, "kim")
    access = changed_access(client, username="kim", subdomain="tenant-a")
    calls: list[str] = []
    real_ports, real_read = audit_api.company_ports, audit_selectors.list_audit_events

    def ports() -> Any:
        calls.append("company_ports")
        return real_ports()

    def read(**kwargs: Any) -> Any:
        calls.append("list_audit_events")
        return real_read(**kwargs)

    monkeypatch.setattr(audit_api, "company_ports", ports)
    monkeypatch.setattr(audit_selectors, "list_audit_events", read)
    response = logs(client, access, f"companyId={a}{YEAR}")
    assert error(response) == (403, "FORBIDDEN")
    assert "results" not in response.json()
    assert calls == []  # 403 은 몸(회사 고르기) 앞이다
    # 분모: 운영 관리자의 같은 요청은 지나고 둘 다 부른다
    assert len(page_ids(logs(client, operator_access(Client()), f"companyId={a}{YEAR}"))) == 1
    assert calls == ["company_ports", "list_audit_events"]


def test_an_operator_before_changing_the_password_gets_403(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    operator()
    first = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)
    assert error(logs(client, first["access"], f"companyId={a}")) == (403, "PASSWORD_CHANGE_REQUIRED")


# ── 이름 풀기 ─────────────────────────────────────────────────────


def test_names_are_the_current_ones_and_other_companies_people_stay_null(
    client: Client, companies: tuple[int, int]
) -> None:
    a, b = companies
    access = operator_access(client)
    kim, park = customer(a, "kim", "김옛이름"), customer(b, "park", "박담당")
    ops = User.admin_by_id(operator("ops2", "둘째 운영자")).get().pk
    by_kim = write(a, at(1), actor_user_id=kim)
    by_ops = write(None, at(2), actor_kind="admin", actor_user_id=ops)
    # 남의 회사 사람의 id 가 이 회사 줄에 실렸다(있을 수 없는 줄 — 그래도 이름은 풀리지 않는다)
    by_park = write(a, at(3), actor_user_id=park)
    by_command = write(None, at(4), actor_kind="command")
    User.for_company(a).filter(pk=kim).update(name="김새이름", username="kim-new")
    lines = {line["id"]: line for line in logs(client, access, f"companyId={a}{YEAR}").json()["results"]}
    named = {i: (lines[i]["actorUsername"], lines[i]["actorName"]) for i in (by_kim, by_ops, by_park, by_command)}
    assert named == {
        by_kim: ("kim-new", "김새이름"),
        by_ops: ("ops2", "둘째 운영자"),
        by_park: (None, None),
        by_command: (None, None),
    }
    assert lines[by_park]["actorUserId"] == park  # id 는 그대로 — 이름만 풀지 않는다
    # 분모: 회사 B 를 고르면 그 사람의 이름이 풀린다
    write(b, at(5), actor_user_id=park)
    in_b = logs(client, access, f"companyId={b}{YEAR}").json()["results"]
    assert (in_b[0]["actorUsername"], in_b[0]["actorName"]) == ("park", "박담당")


def test_names_of_reads_customers_once_and_each_operator_once(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, b = companies
    kim, lee, park = customer(a, "kim", "김"), customer(a, "lee", "이"), customer(b, "park", "박")
    one, two = operator("ops1", "하나"), operator("ops2", "둘")
    # 고객사 한 번 + 운영 관리자 id 하나마다 한 번(셋 — kim 은 운영 관리자 입구에서 빈 것이라 풀리지 않는다)
    with django_assert_num_queries(1 + 3):
        names = names_of(a, {kim, lee, park}, {one, two, kim})
    assert names == {kim: ("kim", "김"), lee: ("lee", "이"), one: ("ops1", "하나"), two: ("ops2", "둘")}
    with django_assert_num_queries(0):
        assert names_of(a, set(), set()) == {}


# ── q(AU1b-1 ① — 사람 이름·아이디·대상 글자) ─────────────────────────


def labelled(company_id: int | None, when: datetime, label: str, *, actor_user_id: int | None = None,
             action: str = "upload") -> int:  # fmt: skip
    done = record_event(
        at=when, company_id=company_id, actor_kind="service", actor_user_id=actor_user_id, action=action,
        event="document_uploaded", result="success", target_kind="document", target_id=1, target_label=label,
    )  # fmt: skip
    assert isinstance(done, AuditRecorded), done
    return done.id


def found(response: Any) -> tuple[int, list[int]]:
    body = response.json()
    return body["count"], page_ids(response)


def test_q_finds_people_by_current_name_and_username_and_lines_by_target_label(
    client: Client, companies: tuple[int, int]
) -> None:
    """ⓐ 고객사 사람 이름 일부 ⓑ 운영 관리자 아이디 일부 ⓒ 대상 글자 일부 ⓓ 대소문자 다른 글자 ⓔ q 와 action 은 AND ·
    count 는 거른 뒤의 수, 쪽 넘김은 거른 집합 위."""
    a, _ = companies
    access = operator_access(client)
    kim, lee = customer(a, "kim", "김담당"), customer(a, "lee", "이수진")
    ops = operator("ops2", "둘째 운영자")
    kim1 = write(a, at(1), actor_user_id=kim)
    kim2 = labelled(a, at(2), "Annual-Report.PDF", actor_user_id=kim)
    kim3 = write(a, at(3), actor_user_id=kim, action="logout", event="logout")
    lee1 = labelled(a, at(4), "보고서-2025.xlsx", actor_user_id=lee)
    by_ops = write(None, at(5), actor_kind="admin", actor_user_id=ops)
    # 분모: 거르지 않으면 다섯 다
    assert found(logs(client, access, f"companyId={a}{YEAR}")) == (5, [by_ops, lee1, kim3, kim2, kim1])
    # ⓐ 고객사 사람의 이름 일부 — 그 사람의 줄 셋, count 는 거른 뒤
    assert found(logs(client, access, f"companyId={a}{YEAR}&q=담당")) == (3, [kim3, kim2, kim1])
    paged = logs(client, access, f"companyId={a}{YEAR}&q=담당&limit=1&offset=1").json()
    assert ([line["id"] for line in paged["results"]], paged["count"], paged["isNext"]) == ([kim2], 3, True)
    # ⓑ 운영 관리자의 아이디 일부
    assert found(logs(client, access, f"companyId={a}{YEAR}&q=ps2")) == (1, [by_ops])
    # ⓒ 대상 글자 일부(그때의 글자) — 사람에게는 안 맞는다
    assert found(logs(client, access, f"companyId={a}{YEAR}&q=보고서")) == (1, [lee1])
    # ⓓ 대소문자 무시: 아이디(kim)와 대상 글자(Annual-Report.PDF)
    assert found(logs(client, access, f"companyId={a}{YEAR}&q=KIM")) == (3, [kim3, kim2, kim1])
    assert found(logs(client, access, f"companyId={a}{YEAR}&q=report.pdf")) == (1, [kim2])
    # ⓔ q 와 action 은 AND
    assert found(logs(client, access, f"companyId={a}{YEAR}&q=담당&action=logout")) == (1, [kim3])
    # 아무에게도 안 맞으면 0
    assert found(logs(client, access, f"companyId={a}{YEAR}&q=없는글자")) == (0, [])


def test_q_never_resolves_a_person_of_another_company(client: Client, companies: tuple[int, int]) -> None:
    """ⓕ 회사 A 의 줄에 B 사람의 id 가 실려도 A 를 고른 q 는 그 이름으로 찾지 못한다(고객사 이름은 고른 회사
    안에서만)."""
    a, b = companies
    access = operator_access(client)
    park = customer(b, "park", "박담당")
    in_a = write(a, at(1), actor_user_id=park)  # 있을 수 없는 줄 — 그래도 이름은 풀리지 않는다
    in_b = write(b, at(2), actor_user_id=park)
    assert found(logs(client, access, f"companyId={a}{YEAR}&q=박담당")) == (0, [])
    assert found(logs(client, access, f"companyId={a}{YEAR}&q=park")) == (0, [])
    # 분모: B 를 고르면 그 사람의 줄이 찾힌다
    assert found(logs(client, access, f"companyId={b}{YEAR}&q=박담당")) == (1, [in_b])
    # 양성 대조: 줄은 A 에서 보인다(이름만 안 풀린다)
    assert found(logs(client, access, f"companyId={a}{YEAR}&actorUserId={park}")) == (1, [in_a])


@pytest.mark.parametrize("q", ["%", "_", "."])
def test_q_takes_wildcard_letters_as_letters(client: Client, companies: tuple[int, int], q: str) -> None:
    """ⓖ % _ . 는 글자다 — 셋이 든 대상 글자의 줄만 맞고, 셋 다 없는 줄은 안 맞는다(action 으로 두 줄만 남긴다)."""
    a, _ = companies
    access = operator_access(client)
    with_all = labelled(a, at(1), "100%_v1.pdf", action="download")
    without = labelled(a, at(2), "kim", action="download")
    narrowed = f"companyId={a}{YEAR}&action=download"
    # 고정물: 보는 범위의 사람 아이디·이름에 세 글자가 없다(있으면 사람으로 맞아 이 시험이 뜻을 잃는다)
    actors = audit_selectors.audit_actors_for_search(actor_kind="admin", company_id=a)
    assert not isinstance(actors, audit_selectors.AuditForbidden)
    people = names_of(
        a,
        {x.actor_user_id for x in actors if x.actor_kind == "service"},
        {x.actor_user_id for x in actors if x.actor_kind == "admin"},
    )
    assert len(people) >= 1  # 분모: 운영 관리자(ops)가 있다
    assert not [text for pair in people.values() for text in pair if set(text) & set("%_.")]
    assert found(logs(client, access, narrowed)) == (2, [without, with_all])  # 분모
    assert found(logs(client, access, f"{narrowed}&q={q.replace('%', '%25')}")) == (1, [with_all])


def test_q_keeps_target_label_matches_when_no_person_matches(client: Client, companies: tuple[int, int]) -> None:
    """ⓗ q 가 사람에게 안 맞아도(맞는 id 집합이 비어도) 대상 글자 일치는 남는다 — 빈 집합이 줄 전체를 0 으로
    만들지 않는다."""
    a, _ = companies
    access = operator_access(client)
    kim = customer(a, "kim", "김담당")
    hit = labelled(a, at(1), "탄소-계획.pdf", actor_user_id=kim)
    write(a, at(2), actor_user_id=kim)
    assert audit_api.matching_ids({kim: ("kim", "김담당")}, "탄소") == frozenset()  # 사람에게는 안 맞는다
    assert found(logs(client, access, f"companyId={a}{YEAR}&q=탄소")) == (1, [hit])


def test_without_q_the_query_count_is_unchanged_and_with_q_names_are_read_once(
    client: Client, companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    """ⓘ q 가 없으면 행위자 읽기 0 — 쿼리 수가 AU1a 와 같다. q 가 있으면 행위자 1 + 이름(고객사 1 + 운영 관리자 k)
    + 목록·셈, 응답의 이름 풀기는 q 길의 사전을 다시 쓴다(names_of 한 번)."""
    a, _ = companies
    access = operator_access(client)
    kim = customer(a, "kim", "김담당")
    ops = operator("ops2", "둘째 운영자")
    write(a, at(1), actor_user_id=kim)
    write(None, at(2), actor_kind="admin", actor_user_id=ops)
    with django_assert_num_queries(WITHOUT_Q):
        assert len(page_ids(logs(client, access, f"companyId={a}{YEAR}"))) == 2
    with django_assert_num_queries(WITH_Q):
        assert len(page_ids(logs(client, access, f"companyId={a}{YEAR}&q=담당"))) == 1


# 쿼리 수(ⓘ): 인증·회사 고르기·셈·쪽·이름(고객사 1 + 운영 관리자 1). q 길은 행위자 1 + 이름(고객사 1 + 운영 관리자 둘 —
# 보는 범위의 운영 관리자는 ops·ops2) 이고 응답의 이름 풀기는 다시 읽지 않는다.
WITHOUT_Q = 5
WITH_Q = 7


@pytest.mark.parametrize(
    ("names", "q", "expected"),
    [
        ({}, "kim", frozenset[int]()),
        ({1: ("kim", "김담당")}, "lee", frozenset[int]()),
        ({1: ("kim", "김담당"), 2: ("lee", "이수진")}, "담당", frozenset({1})),
        ({1: ("kim", "김담당"), 2: ("lee", "이수진")}, "ee", frozenset({2})),
        ({1: ("Kim", "김담당"), 2: ("lee", "KIMBERLY")}, "kIM", frozenset({1, 2})),
    ],
    ids=["empty", "no-match", "name-only", "username-only", "case"],
)
def test_matching_ids_picks_people_whose_username_or_name_holds_q(
    names: dict[int, tuple[str, str]], q: str, expected: frozenset[int]
) -> None:
    """경로의 matching_ids 경우표(DB 를 읽지 않는 순수 함수 — 이 파일의 pytestmark 로 업무 층에서 돈다)."""
    assert audit_api.matching_ids(names, q) == expected


# ── 행위자 목록(AU1b-1 ② — GET /audit-logs/actors) ─────────────────────


def actors_of(client: Client, access: str, query: str) -> Any:
    return client.get(f"/api/audit-logs/actors?{query}", **bearer(access))


def test_actors_list_the_people_of_the_visible_lines_including_operators(
    client: Client, companies: tuple[int, int]
) -> None:
    """고른 회사의 줄과 회사 없는 줄에 나온 사람 — 운영 관리자 포함, command·anonymous 0, 같은 사람 여럿 → 하나,
    고른 회사 밖 고객사 사람 0. 차례: 이름 풀린 사람 먼저 아이디 → 갈래 → id(운영 관리자와 고객사가 같은 아이디
    kim), 풀리지 않은 사람(남의 회사 사람·지운 사람)은 이름 null 로 맨 뒤 id 차례."""
    a, b = companies
    access = operator_access(client)  # 운영 관리자 ops 의 로그인·비밀번호 바꾸기 줄(회사 없음)
    kim, lee, park = customer(a, "kim", "김담당"), customer(a, "lee", "이수진"), customer(b, "park", "박담당")
    ops = User.admin_by_id(operator("ops-kim", "운영김")).get().pk
    User.admin_by_id(ops).update(username="kim")  # 고객사 kim 과 같은 아이디(차례의 갈래 가름 — 만든 뒤 바꿈)
    only_b = customer(b, "choi", "최담당")
    ghost = 9_000_000
    write(a, at(1), actor_user_id=kim)
    write(a, at(2), actor_user_id=kim)
    write(a, at(3), actor_user_id=lee, action="upload", event="document_uploaded")
    write(None, at(4), actor_kind="admin", actor_user_id=ops)
    write(a, at(5), actor_user_id=park)  # 남의 회사 사람의 id 가 A 의 줄에 — 이름은 풀리지 않는다
    write(a, at(6), actor_user_id=ghost)  # 없는 사람
    write(b, at(7), actor_user_id=only_b)  # B 에만 있는 사람 — A 를 고르면 0
    write(a, at(8), actor_kind="command")
    write(None, at(9), actor_kind="anonymous")
    response = actors_of(client, access, f"companyId={a}")
    assert response.status_code == 200, response.content.decode()
    results = response.json()["results"]
    found_self = find_admin("ops")
    assert found_self is not None
    ops_self = found_self.pk
    assert results == [
        {"actorKind": "admin", "actorUserId": ops, "actorName": "운영김", "actorUsername": "kim"},
        {"actorKind": "service", "actorUserId": kim, "actorName": "김담당", "actorUsername": "kim"},
        {"actorKind": "service", "actorUserId": lee, "actorName": "이수진", "actorUsername": "lee"},
        {"actorKind": "admin", "actorUserId": ops_self, "actorName": "운영자", "actorUsername": "ops"},
        {"actorKind": "service", "actorUserId": park, "actorName": None, "actorUsername": None},
        {"actorKind": "service", "actorUserId": ghost, "actorName": None, "actorUsername": None},
    ]
    # 분모: B 를 고르면 B 의 사람(park·choi)이 풀리고 A 에만 있는 kim·lee 는 0, 회사 없는 줄의 운영 관리자는 그대로
    listed_b = actors_of(client, access, f"companyId={b}").json()["results"]
    in_b = {(line["actorKind"], line["actorUserId"]) for line in listed_b}
    assert in_b == {("admin", ops), ("admin", ops_self), ("service", only_b)}
    # 거른 줄이 실제로 있다: 목록의 id 로 /audit-logs 를 거르면 줄이 나온다(안 풀린 사람도)
    assert len(page_ids(logs(client, access, f"companyId={a}{YEAR}&actorUserId={ghost}"))) == 1


def test_actors_an_unknown_company_is_404(client: Client, companies: tuple[int, int]) -> None:
    access = operator_access(client)
    assert error(actors_of(client, access, "companyId=9000000")) == (404, "COMPANY_NOT_FOUND")
    assert error(actors_of(client, access, "")) == (400, "COMPANY_AMBIGUOUS")  # 회사가 둘(/audit-logs 와 같은 규칙)


def test_actors_a_customer_gets_403_before_the_body_reads_anything(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    customer(a, "kim")
    access = changed_access(client, username="kim", subdomain="tenant-a")
    calls: list[str] = []
    real_ports, real_read = audit_api.company_ports, audit_selectors.list_audit_actors

    def ports() -> Any:
        calls.append("company_ports")
        return real_ports()

    def read(**kwargs: Any) -> Any:
        calls.append("list_audit_actors")
        return real_read(**kwargs)

    monkeypatch.setattr(audit_api, "company_ports", ports)
    monkeypatch.setattr(audit_selectors, "list_audit_actors", read)
    response = actors_of(client, access, f"companyId={a}")
    assert error(response) == (403, "FORBIDDEN")
    assert "results" not in response.json()
    assert calls == []  # 403 은 몸(회사 고르기) 앞이다
    # 분모: 운영 관리자의 같은 요청은 지나고 둘 다 부른다(kim 의 로그인 줄로 kim 이 목록에 있다)
    seen = actors_of(Client(), operator_access(Client()), f"companyId={a}")
    assert seen.status_code == 200 and len(seen.json()["results"]) >= 1
    assert calls == ["company_ports", "list_audit_actors"]


def test_actors_an_operator_before_changing_the_password_gets_403(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    operator()
    first = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)
    assert error(actors_of(client, first["access"], f"companyId={a}")) == (403, "PASSWORD_CHANGE_REQUIRED")


def test_actors_read_the_people_once_and_each_operator_once(
    client: Client, companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    """쿼리 = 인증 앞뒤의 공통 + 회사 고르기 1 + 행위자 1 + 고객사 이름 1 + 운영 관리자 k(여기 ops·ops2 둘)."""
    a, _ = companies
    access = operator_access(client)
    kim, lee = customer(a, "kim", "김"), customer(a, "lee", "이")
    ops = operator("ops2", "둘")
    write(a, at(1), actor_user_id=kim)
    write(a, at(2), actor_user_id=lee)
    write(None, at(3), actor_kind="admin", actor_user_id=ops)
    with django_assert_num_queries(ACTORS_QUERIES):
        assert len(actors_of(client, access, f"companyId={a}").json()["results"]) == 4


# 회사 고르기 1 + 행위자 1 + 고객사 이름 1 + 운영 관리자 둘(ops·ops2). 인증은 쿼리 0(토큰).
ACTORS_QUERIES = 5


# ── 모듈(AD4S ③) ────────────────────────────────────────────────────


def test_a_module_line_carries_its_module(client: Client, companies: tuple[int, int]) -> None:
    """detail 의 module 이 module 칸으로 나온다. module 이 없는 줄·글자가 아닌 옛 값은 null."""
    a, _ = companies
    access = operator_access(client)
    with_module = record_event(
        at=at(2), company_id=a, actor_kind="admin", actor_user_id=None, action="setting_change",
        event="ai_setting_applied", result="success", target_kind="ai_setting", changed_fields=("applied",),
        module="greenwash",
    )  # fmt: skip
    assert isinstance(with_module, AuditRecorded)
    without = write(a, at(1))
    odd = write(a, at(3))
    AuditEventRow.for_company(a).filter(pk=odd).update(detail={"module": ["greenwash"]})  # 꼴 밖 옛 값(손으로)
    rows = {line["id"]: line["module"] for line in logs(client, access, f"companyId={a}{YEAR}").json()["results"]}
    assert rows == {with_module.id: "greenwash", without: None, odd: None}
