"""교환의 유스케이스. 바깥(검증·회사 찾기·DB)을 가짜 함수로 넘겨, DB 없이 갈래마다 잰다(순수 층).
끝의 절 하나는 진짜 upsert_user 가 남의 회사 행을 안 보고 안 건드리는가를 잰다(업무 층, 주인 역할 연결).
맨 끝의 절은 계정 만들기와 비밀번호 검사(K2a)다.
"""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from django.db.models import Max
from django.test import override_settings

from esgapi.core.models import AuditEventRow
from esgapi.core.tenancy.session import Role
from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.utils.entities import CompanyActive
from esgapi.user.models import User as UserRow
from esgapi.user.service.services.user import (
    ExchangePorts,
    create_customer_user,
    create_operator,
    exchange,
    password_problems,
    upsert_user,
)
from esgapi.user.service.utils.entities import Tenant, User
from esgapi.user.service.utils.exchange import (
    ExchangeOk,
    ExchangeRejected,
    TenantLookup,
    TenantRegistered,
    TenantUnknown,
    UserInactive,
    UserLookup,
    UserSaved,
)
from esgapi.user.service.utils.login import PasswordRejected, UserCreated, UsernameTaken
from esgapi.user.service.utils.tokens import EdkClaims, TokenOk, TokenRejected, TokenRejection, TokenResult

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
CLAIMS = EdkClaims(issuer="https://edk.test", external_id="u1", tenant_id="tenant-a", role="editor", name="김담당")
COMPANY_ID = 11  # 순수 층의 가짜 회사 id(DB 가 없다)
OTHER_COMPANY_ID = 12
TENANT = Tenant(id="tenant-a", name="가 회사", company_id=COMPANY_ID)
USER = User(
    id="user-1",
    company_id=COMPANY_ID,
    tenant_id="tenant-a",
    issuer=CLAIMS.issuer,
    external_id="u1",
    name="김담당",
    role="editor",
)


class Fakes:
    """교환이 바깥에 시킨 일을 순서대로 적어 둔다."""

    def __init__(self, token: TokenResult, tenant: TenantLookup, upsert: UserLookup) -> None:
        self.calls: list[str] = []
        self.upserted_for: list[int] = []  # upsert 가 받은 회사 id
        self._token, self._tenant, self._upsert = token, tenant, upsert

    def ports(self) -> ExchangePorts:
        return ExchangePorts(verify_token=self._verify, find_tenant=self._find, upsert_user=self._save)

    def _verify(self, token: str) -> TokenResult:
        self.calls.append("verify")
        return self._token

    def _find(self, tenant_id: str) -> TenantLookup:
        self.calls.append(f"find:{tenant_id}")
        return self._tenant

    def _save(self, company_id: int, claims: EdkClaims) -> UserLookup:
        self.calls.append("upsert")
        self.upserted_for.append(company_id)
        return self._upsert


def run(fakes: Fakes) -> ExchangeOk | ExchangeRejected:
    return exchange("token", ports=fakes.ports(), now=NOW, session_ttl_seconds=600)


def test_ok_verifies_then_looks_up_then_upserts() -> None:
    fakes = Fakes(TokenOk(CLAIMS), TenantRegistered(TENANT), UserSaved(USER))
    result = run(fakes)
    assert isinstance(result, ExchangeOk)
    assert (result.user, result.tenant) == (USER, TENANT)
    assert (result.session.user_id, result.session.tenant_id, result.session.role) == ("user-1", "tenant-a", "editor")
    # 조회의 테넌트는 서명이 확인된 토큰의 것이다.
    assert fakes.calls == ["verify", "find:tenant-a", "upsert"]


@pytest.mark.parametrize(
    "reason",
    ["malformed", "bad_algorithm", "bad_signature", "expired", "wrong_audience", "wrong_issuer", "bad_claims"],
)
def test_rejected_token_keeps_its_reason_and_never_touches_the_db(reason: TokenRejection) -> None:
    fakes = Fakes(TokenRejected(reason), TenantRegistered(TENANT), UserSaved(USER))
    assert run(fakes) == ExchangeRejected(reason)
    assert fakes.calls == ["verify"]


def test_unknown_tenant_is_rejected_and_no_user_is_written() -> None:
    fakes = Fakes(TokenOk(CLAIMS), TenantUnknown(), UserSaved(USER))
    assert run(fakes) == ExchangeRejected("unknown_tenant")
    assert "upsert" not in fakes.calls


def test_an_inactive_user_gets_no_session() -> None:
    """(CA·D3) upsert 가 「꺼진 사용자」라 답하면 세션을 내지 않고 user_inactive 로 거절한다."""
    fakes = Fakes(TokenOk(CLAIMS), TenantRegistered(TENANT), UserInactive())
    assert run(fakes) == ExchangeRejected("user_inactive")
    assert fakes.calls == ["verify", "find:tenant-a", "upsert"]


@pytest.mark.django_db
def test_upsert_user_leaves_an_inactive_row_alone(tenants: None) -> None:
    """(CA·D3) 꺼진 행은 이름·level 을 덮지 않고 UserInactive."""
    a = company_id_of("tenant-a")
    upsert_user(a, claims_for("tenant-a", name="가담당", role="editor"))
    UserRow.unscoped.update(is_active=False)
    assert upsert_user(a, claims_for("tenant-a", name="가관리", role="admin")) == UserInactive()
    assert list(UserRow.unscoped.values_list("name", "level")) == [("가담당", 79)]


def test_a_sub_in_another_company_is_this_companys_own_user() -> None:
    """같은 sub 가 다른 회사에 있어도 교환은 받은 회사에서 찾고 만든다(처분 2 ㉡).
    옛 user_in_other_tenant 갈래(409)를 뒤집었다.

    가짜 upsert 는 (회사, sub) 로 가르는 표다. 다른 회사의 같은 sub 행이 미리 있다.
    """
    other = User(
        id="user-9",
        company_id=OTHER_COMPANY_ID,
        tenant_id="tenant-b",
        issuer=CLAIMS.issuer,
        external_id=CLAIMS.external_id,
        name="나담당",
        role="viewer",
    )
    rows: dict[tuple[int, str], User] = {(OTHER_COMPANY_ID, CLAIMS.external_id): other}

    def upsert(company_id: int, claims: EdkClaims) -> UserSaved:
        fakes.calls.append("upsert")
        fakes.upserted_for.append(company_id)
        key = (company_id, claims.external_id)
        rows[key] = replace(USER, id=f"user-{len(rows) + 1}", company_id=company_id, name=claims.name)
        return UserSaved(rows[key])

    fakes = Fakes(TokenOk(CLAIMS), TenantRegistered(TENANT), UserSaved(USER))
    result = exchange("token", ports=replace(fakes.ports(), upsert_user=upsert), now=NOW, session_ttl_seconds=600)
    assert isinstance(result, ExchangeOk)
    assert fakes.calls == ["verify", "find:tenant-a", "upsert"]
    assert fakes.upserted_for == [TENANT.company_id]  # 받아들인 회사의 것(다른 회사의 것이 아니다)
    assert (result.user.company_id, result.session.company_id) == (COMPANY_ID, COMPANY_ID)
    assert len(rows) == 2  # 회사마다 하나씩
    assert rows[(OTHER_COMPANY_ID, CLAIMS.external_id)] is other  # 다른 회사의 행은 그대로


# ── 업무 층: 진짜 upsert_user 의 회사 조건(옛 test_selectors_tenant 의 사용자 몫) ───────────────
# ★ 이 층의 연결은 주인 역할이다. 행 수는 UserRow.unscoped 로 센다(분모). 회사 id 는 상수로 박지 않는다 —
#   회사는 tenants 고정물이 심고, id 는 organization 의 찾기(find_company)로 읽는다
#   (user 는 남의 models 를 import 하지 않는다 — .importlinter 「나」).


def company_id_of(subdomain: str) -> int:
    found = find_company(subdomain)
    assert isinstance(found, CompanyActive), found
    return found.company.id


def claims_for(tenant_id: str, *, name: str, role: Role) -> EdkClaims:
    return EdkClaims(issuer="https://edk.test", external_id="edk-user-1", tenant_id=tenant_id, role=role, name=name)


ROW_FIELDS = ("company_id", "kind", "username", "name", "level")


@pytest.mark.django_db
def test_upsert_user_neither_sees_nor_touches_another_companys_row(tenants: None) -> None:
    a, b = company_id_of("tenant-a"), company_id_of("tenant-b")
    upsert_user(b, claims_for("tenant-b", name="나담당", role="viewer"))
    b_row = UserRow.unscoped.get()
    assert UserRow.unscoped.count() == 1  # 분모: 이 연결에는 모든 회사의 행이 보인다

    first = upsert_user(a, claims_for("tenant-a", name="가담당", role="admin"))
    assert isinstance(first, UserSaved)
    assert first.user.company_id == a
    assert first.user.id != str(b_row.pk)  # B 의 행을 찾지 않았다(새로 만들었다)
    assert sorted(UserRow.unscoped.values_list(*ROW_FIELDS)) == sorted(
        [(a, "service", "edk-user-1", "가담당", 99), (b, "service", "edk-user-1", "나담당", 79)]
    )

    second = upsert_user(a, claims_for("tenant-a", name="가관리", role="editor"))
    assert isinstance(second, UserSaved)
    assert second.user.id == first.user.id  # A 의 행을 덮어썼다
    assert UserRow.unscoped.count() == 2  # 분모 그대로
    assert UserRow.unscoped.filter(pk=b_row.pk).values_list(*ROW_FIELDS).get() == (
        b,
        "service",
        "edk-user-1",
        "나담당",
        79,
    )  # B 의 행은 그대로


@pytest.mark.django_db
def test_the_user_scope_opens_only_its_company_not_the_neighbours(tenants: None) -> None:
    a, b = company_id_of("tenant-a"), company_id_of("tenant-b")
    upsert_user(a, claims_for("tenant-a", name="가담당", role="editor"))
    upsert_user(b, claims_for("tenant-b", name="나담당", role="editor"))
    assert UserRow.unscoped.count() == 2  # 분모
    assert list(UserRow.for_company(a).values_list("company_id", "name")) == [(a, "가담당")]
    assert list(UserRow.for_company(b).values_list("company_id", "name")) == [(b, "나담당")]
    neighbours = sorted(n for n in {a - 1, a + 1, b - 1, b + 1} - {a, b} if n > 0)  # 이웃 id(±1)
    assert neighbours  # 적어도 하나는 본다
    for neighbour in neighbours:
        assert UserRow.for_company(neighbour).count() == 0, neighbour


# ── 계정 만들기와 비밀번호 검사(K2a) ──────────────────────────────────
# 해시는 MD5 로 바꿔 빠르게 돈다(fast_hasher). 제품의 해시기가 PBKDF2 인 것은 core/tests/test_permissions.py 가 잰다.

PASSWORD = "Blue-Harbor-7310"


@pytest.fixture
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


@pytest.mark.parametrize(
    "password",
    ["Short-1", "Long-" * 205],
    ids=["short", "too-long"],
)
def test_password_problems_refuse_without_echoing_the_password(password: str) -> None:
    rejected = password_problems(password)
    assert isinstance(rejected, PasswordRejected), rejected
    assert rejected.messages
    assert all(password not in message for message in rejected.messages)


def test_password_problems_draw_the_line_between_seven_and_eight_characters() -> None:
    # 8자 이상 하나(MARC-ENT-282): 7자는 거절, 8자는 받는다.
    seven = password_problems("Abcdef1")
    assert isinstance(seven, PasswordRejected), seven
    assert all("Abcdef1" not in message for message in seven.messages)
    assert password_problems("Abcdefg1") is None


@pytest.mark.parametrize(
    "password",
    ["12345678901", "password123", "harborman"],
    ids=["numeric", "common", "like-the-username"],
)
def test_password_problems_now_pass_what_the_removed_validators_refused(password: str) -> None:
    # 결정 MARC-ENT-282 가 바꾼 동작: 흔함·숫자만·아이디와 비슷함(전엔 거절)을 이제 받는다(8자 이상이면).
    assert password_problems(password) is None


def test_password_problems_pass_a_good_password() -> None:
    assert password_problems(PASSWORD) is None


@pytest.mark.django_db
def test_a_customer_user_is_a_service_user_of_that_company(tenants: None, fast_hasher: None) -> None:
    a = company_id_of("tenant-a")
    created = create_customer_user(actor_kind="admin", company_id=a, username="kim", name="김담당", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    row = UserRow.for_company(a).get(pk=created.user_id)
    assert (row.company_id, row.kind, row.username, row.name, row.level, row.is_initial) == (
        a,
        "service",
        "kim",
        "김담당",
        79,
        True,
    )
    assert row.password.startswith("md5$")
    assert (row.login_failed_count, row.login_expiry_at) == (0, None)


@pytest.mark.django_db
def test_the_same_username_twice_in_one_company_is_taken(tenants: None, fast_hasher: None) -> None:
    a = company_id_of("tenant-a")
    assert isinstance(
        create_customer_user(actor_kind="admin", company_id=a, username="kim", name="김담당", password=PASSWORD),
        UserCreated,
    )
    count = UserRow.unscoped.count()
    assert (
        create_customer_user(actor_kind="admin", company_id=a, username="kim", name="김다른", password=PASSWORD)
        == UsernameTaken()
    )
    assert UserRow.unscoped.count() == count


@pytest.mark.django_db
def test_the_same_username_in_another_company_is_a_new_user(tenants: None, fast_hasher: None) -> None:
    a, b = company_id_of("tenant-a"), company_id_of("tenant-b")
    first = create_customer_user(actor_kind="admin", company_id=a, username="kim", name="김담당", password=PASSWORD)
    second = create_customer_user(actor_kind="admin", company_id=b, username="kim", name="김담당", password=PASSWORD)
    assert isinstance(first, UserCreated) and isinstance(second, UserCreated)
    assert first.user_id != second.user_id
    assert sorted(UserRow.unscoped.values_list("company_id", "username")) == sorted([(a, "kim"), (b, "kim")])


@pytest.mark.django_db
def test_a_refused_password_creates_no_user(tenants: None, fast_hasher: None) -> None:
    a = company_id_of("tenant-a")
    assert isinstance(
        create_customer_user(actor_kind="admin", company_id=a, username="kim", name="김담당", password="short"),
        PasswordRejected,
    )
    # 8자 이상 하나(MARC-ENT-282) — 7자는 거절(전엔 흔한 "password123" 이 거절이었다).
    assert isinstance(create_operator(username="ops", name="운영자", password="pass123"), PasswordRejected)
    assert UserRow.unscoped.count() == 0


@pytest.mark.django_db
def test_a_common_password_now_creates_the_user(tenants: None, fast_hasher: None) -> None:
    # 결정 MARC-ENT-282 가 바꾼 동작: 흔한 "password123"(전엔 거절)을 이제 받는다.
    created = create_operator(username="ops", name="운영자", password="password123")
    assert isinstance(created, UserCreated), created
    assert UserRow.unscoped.count() == 1


@pytest.mark.django_db
def test_an_operator_is_an_admin_without_a_company(tenants: None, fast_hasher: None) -> None:
    created = create_operator(username="ops", name="운영자", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    row = UserRow.unscoped.get(pk=created.user_id)
    assert (row.company_id, row.kind, row.username, row.level, row.is_initial) == (None, "admin", "ops", 99, True)
    assert row.password.startswith("md5$")


@pytest.mark.django_db
def test_a_second_operator_with_the_same_username_is_taken(tenants: None, fast_hasher: None) -> None:
    assert isinstance(create_operator(username="ops", name="운영자", password=PASSWORD), UserCreated)
    assert create_operator(username="ops", name="운영둘", password=PASSWORD) == UsernameTaken()
    assert UserRow.unscoped.filter(kind="admin").count() == 1
    # 고객사 사용자의 같은 username 은 이제 막는다(UA1 — MARC-ENT-283 의 겹침 규칙, 전엔 UserCreated)
    a = company_id_of("tenant-a")
    assert (
        create_customer_user(actor_kind="admin", company_id=a, username="ops", name="김담당", password=PASSWORD)
        == UsernameTaken()
    )


@pytest.mark.django_db
def test_a_customer_with_an_operators_username_is_taken_and_nothing_is_made(tenants: None, fast_hasher: None) -> None:
    """(UA1 — MARC-ENT-283 의 겹침 규칙) 서브도메인 없는 로그인은 운영 관리자를 먼저 찾으므로, 운영 관리자와 같은
    아이디의 고객사 사용자는 만들지 않는다(UsernameTaken, 행 0). 분모: 다른 아이디는 만들어진다."""
    a = company_id_of("tenant-a")
    assert isinstance(create_operator(username="ops", name="운영자", password=PASSWORD), UserCreated)
    taken = create_customer_user(actor_kind="admin", company_id=a, username="ops", name="겹침", password=PASSWORD)
    assert taken == UsernameTaken()
    assert UserRow.for_company(a).count() == 0
    made = create_customer_user(actor_kind="admin", company_id=a, username="ops2", name="다름", password=PASSWORD)
    assert isinstance(made, UserCreated)


# ── AU1a: 만들기의 감사 줄(setting_change · user_created) ─────────────────────


def audit_mark() -> int:
    return AuditEventRow.unscoped.aggregate(top=Max("pk"))["top"] or 0


def audit_after(mark: int) -> list[tuple[object, ...]]:
    """표시 뒤의 감사 줄: (행동, 사건, 결과, 행위자 갈래, 행위자 id, 회사, 대상 갈래, 대상 id, 대상 이름, detail)."""
    return [
        (r.action, r.event, r.result, r.actor_kind, r.actor_user_id, r.company_id, r.target_kind, r.target_id,
         r.target_label, r.detail)
        for r in AuditEventRow.unscoped.filter(pk__gt=mark).order_by("pk")
    ]  # fmt: skip


@pytest.mark.django_db
def test_a_customer_made_over_http_is_an_operators_line_and_by_command_a_command_line(
    tenants: None, fast_hasher: None
) -> None:
    a = company_id_of("tenant-a")
    mark = audit_mark()
    by_http = create_customer_user(
        actor_kind="admin", company_id=a, username="kim", name="김담당", password=PASSWORD, actor_user_id=5
    )
    by_command = create_customer_user(
        actor_kind="admin", company_id=a, username="lee", name="이담당", password=PASSWORD
    )
    assert isinstance(by_http, UserCreated) and isinstance(by_command, UserCreated)
    assert audit_after(mark) == [
        ("setting_change", "user_created", "success", "admin", 5, a, "user", by_http.user_id, "kim", {}),
        ("setting_change", "user_created", "success", "command", None, a, "user", by_command.user_id, "lee", {}),
    ]
    joined = [UserRow.for_company(a).get(pk=i).date_joined for i in (by_http.user_id, by_command.user_id)]
    assert list(AuditEventRow.unscoped.filter(pk__gt=mark).order_by("pk").values_list("at", flat=True)) == joined


@pytest.mark.django_db
def test_an_operator_is_always_a_command_line_without_a_company(tenants: None, fast_hasher: None) -> None:
    mark = audit_mark()
    created = create_operator(username="ops", name="운영자", password=PASSWORD)
    assert isinstance(created, UserCreated)
    assert audit_after(mark) == [
        ("setting_change", "user_created", "success", "command", None, None, "user", created.user_id, "ops", {})
    ]


@pytest.mark.django_db
def test_a_refused_creation_writes_no_line(tenants: None, fast_hasher: None) -> None:
    a = company_id_of("tenant-a")
    assert isinstance(
        create_customer_user(actor_kind="admin", company_id=a, username="kim", name="김담당", password=PASSWORD),
        UserCreated,
    )
    mark = audit_mark()
    assert isinstance(
        create_customer_user(actor_kind="admin", company_id=a, username="x", name="엑스", password="Short-1"),
        PasswordRejected,
    )
    assert (
        create_customer_user(
            actor_kind="admin", company_id=a, username="kim", name="김다른", password=PASSWORD, actor_user_id=5
        )
        == UsernameTaken()
    )
    refused = create_customer_user(
        actor_kind="service", company_id=a, username="new", name="새", password=PASSWORD, actor_user_id=5
    )
    assert not isinstance(refused, UserCreated)  # 고객사 사용자는 만들지 못한다(Forbidden)
    assert audit_after(mark) == []
