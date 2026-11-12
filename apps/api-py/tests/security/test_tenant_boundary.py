"""테넌트의 경계를 앱 역할의 연결에서 잰다. 보안 층: Django 의 연결은 앱 역할(esg_app)이고 RLS 가 없다.

★ 앱 역할은 이제 표의 모든 행을 읽을 수 있다(GRANT 만 걸린다). 남의 행을 막는 것은 조회의 조건(①, selector 가
  인자로 받는다)과 회사 범위 표의 기본 매니저(②, 테넌트를 정하지 않은 조회와 다른 테넌트로의 쓰기를 거절한다)다.
  이 파일은 ② 를 ORM 으로 직접 부르고, ① 을 경로(/sites)로 부른다. 분모는 주인 연결이나 `<Model>.unscoped` 로 센다.
  회사 칸 표(sites·users)의 범위는 회사의 숫자 id 다(Site.for_company). 회사 id 는 고정물이 돌려준 것을 쓴다.
"""

from typing import Any

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory

from esgapi.core.isolation.managers import CrossCompanyWriteError, UnscopedQueryError
from esgapi.core.tenancy.middleware import TenantMiddleware
from esgapi.organization.models import Company, Site
from esgapi.organization.service.selectors import organization as selectors
from esgapi.user.models import User
from tests.security.conftest import count
from tests.security.seed import add_site
from tests.support.http import login

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]


@pytest.fixture
def sites(owner: Owner, companies: tuple[int, int]) -> tuple[int, int]:
    """A 에 둘, B 에 셋. A·B 의 회사 id 를 돌려준다."""
    a, b = companies
    for name in ("A 본사", "A 공장"):
        add_site(owner, a, name)
    for name in ("B 본사", "B 공장", "B 창고"):
        add_site(owner, b, name)
    return companies


def backend_state() -> tuple[int, str | None]:
    """지금 Django 가 쥔 DB 연결의 번호(pid)와 그 연결에 남은 테넌트 값(아무도 싣지 않으므로 늘 None 이어야 한다)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid(), nullif(current_setting('app.tenant_id', true), '')")
        row = cursor.fetchone()
    assert row is not None
    return int(row[0]), row[1]


def test_tests_run_as_the_app_role_which_is_not_a_superuser() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        assert cursor.fetchone() == ("esg_app", False, False)
        cursor.execute("SELECT tableowner FROM pg_tables WHERE tablename IN ('company', 'users', 'sites')")
        assert "esg_app" not in {owner for (owner,) in cursor.fetchall()}  # 표의 주인도 아니다


def test_session_a_sees_only_a(client: Client, owner: Owner, sites: tuple[int, int]) -> None:
    login(client, tenant_id="tenant-a")
    response = client.get("/api/sites")
    assert response.status_code == 200
    assert [site["name"] for site in response.json()["sites"]] == ["A 본사", "A 공장"]
    assert count(owner, "sites") == 5  # 실제로는 다섯 행이 있다

    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    assert len(other.get("/api/sites").json()["sites"]) == 3


def test_without_session_http_is_401_and_an_unscoped_orm_query_is_refused(
    client: Client, owner: Owner, sites: tuple[int, int]
) -> None:
    a, _ = sites
    assert client.get("/api/sites").status_code == 401
    # 미들웨어를 건너뛰고 ORM 으로 바로 물어도(테넌트를 정하지 않음), 기본 매니저가 DB 로 가기 전에 거절한다.
    with pytest.raises(UnscopedQueryError):
        Site.objects.count()
    with pytest.raises(UnscopedQueryError):
        list(Site.objects.all())
    with pytest.raises(UnscopedQueryError):
        User.objects.count()
    with pytest.raises(UnscopedQueryError):
        Company.objects.count()
    with pytest.raises(UnscopedQueryError):
        Site.for_company(0)
    # 분모: 행은 다섯이고, 앱 역할은 조건 없이도 다섯을 다 읽을 수 있다(그래서 위의 거절이 막는 것이 있다).
    assert count(owner, "sites") == 5
    assert Site.unscoped.count() == 5
    assert [site.name for site in selectors.all_sites(a)] == ["A 본사", "A 공장"]


def test_query_without_where_is_still_scoped(owner: Owner, sites: tuple[int, int]) -> None:
    """앱 코드가 WHERE company_id 를 적지 않아도(여기서는 아예 없다) for_company 의 범위가 조건을 붙인다."""
    a, b = sites
    with transaction.atomic():
        scoped = Site.for_company(a)
        assert sorted(scoped.values_list("company_id", flat=True)) == [a, a]
        # 남의 회사를 콕 집어 물어도 0행이다(범위의 조건과 AND 로 붙는다).
        assert scoped.filter(company_id=b).count() == 0
        # 남의 행을 고치려 해도 대상이 0행이다.
        assert scoped.filter(company_id=b).update(name="뺏었다") == 0
        # 분모: 범위 밖에서 세면 다섯이다(A 둘, B 셋).
        assert Site.unscoped.count() == 5
        assert Site.unscoped.filter(company_id=b).count() == 3
    assert owner.execute("SELECT count(*) FROM sites WHERE name = '뺏었다'").fetchone() == (0,)


def test_insert_for_another_tenant_is_refused_by_the_manager(owner: Owner, sites: tuple[int, int]) -> None:
    a, b = sites
    with pytest.raises(CrossCompanyWriteError), transaction.atomic():
        Site.for_company(a).create(company_id=b, name="A 가 B 에 심은 것")
    with pytest.raises(CrossCompanyWriteError), transaction.atomic():
        Site.for_company(a).update(company_id=b)  # 제 행을 남의 회사로 옮기기
    assert count(owner, "sites") == 5
    assert owner.execute("SELECT company_id, count(*) FROM sites GROUP BY 1 ORDER BY 1").fetchall() == sorted(
        [(a, 2), (b, 3)]
    )


def test_app_role_cannot_create_tenants_or_delete(owner: Owner, sites: tuple[int, int]) -> None:
    """앱 역할의 권한: company 는 읽기만(만드는 입구 register 도 앱 역할로는 거절), 업무 표는 지우지 못한다."""
    with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
        Company.register(name="교환이 만든 회사", business_licence_number="000-00-00003", subdomain="tenant-c")
    with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
        Company.unscoped.create(name="교환이 만든 회사", business_licence_number="000-00-00004", subdomain="tenant-d")
    with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
        Site.unscoped.all().delete()
    assert (count(owner, "company"), count(owner, "sites")) == (2, 5)


def test_tenant_does_not_leak_to_the_next_request_on_the_same_connection(
    client: Client, sites: tuple[int, int]
) -> None:
    """연결 재사용: 요청 둘이 같은 DB 연결을 쓴다. 둘째(세션 없음)가 첫째의 테넌트를 물려받지 않는다.

    테넌트는 요청에 붙을 뿐 연결(DB 설정)에 실리지 않는다. 누가 다시 연결에 싣기 시작하면 leftover 가 빨개진다.
    """
    pid_before, _ = backend_state()
    login(client, tenant_id="tenant-a")
    assert len(client.get("/api/sites").json()["sites"]) == 2  # 첫째 요청: A 의 세션

    pid_after, leftover = backend_state()
    assert pid_after == pid_before  # 정말 같은 연결이었다(이것이 다르면 이 테스트는 아무것도 재지 못한 것이다)
    assert leftover is None  # 요청이 끝난 연결에 테넌트가 남아 있지 않다(NULL·빈 글자)
    assert Client().get("/api/sites").status_code == 401  # 같은 연결의 다음 요청(세션 없음)
    with pytest.raises(UnscopedQueryError):
        Site.objects.count()  # 같은 연결의 다음 조회(회사를 정하지 않음)
    assert backend_state() == (pid_before, None)


def test_tenant_does_not_leak_from_a_to_b_on_the_same_connection(client: Client, sites: tuple[int, int]) -> None:
    login(client, tenant_id="tenant-a")
    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    pid, _ = backend_state()
    for _ in range(3):
        assert {s["name"][0] for s in client.get("/api/sites").json()["sites"]} == {"A"}
        assert {s["name"][0] for s in other.get("/api/sites").json()["sites"]} == {"B"}
    assert backend_state() == (pid, None)


def test_the_middleware_opens_no_transaction(owner: Owner, companies: tuple[int, int]) -> None:
    """요청마다의 트랜잭션은 없다(EDK 리뉴얼 꼴). 경로 안은 트랜잭션 밖이고, 쓰고 나서 오류로 답해도 쓴 것이 남는다
    (그래서 거절은 쓰기 앞에서 한다).
    """
    seen: list[bool] = []
    a, _ = companies

    def write_then_fail(request: HttpRequest) -> HttpResponse:
        seen.append(connection.in_atomic_block)
        Site.unscoped.create(company_id=a, name="반쯤 쓴 것")
        return HttpResponse(status=500)

    def write_then_ok(request: HttpRequest) -> HttpResponse:
        seen.append(connection.in_atomic_block)
        Site.unscoped.create(company_id=a, name="다 쓴 것")
        return HttpResponse(status=201)

    request = RequestFactory().post("/sites")
    assert count(owner, "sites") == 0  # 분모: 쓰기 전
    assert TenantMiddleware(write_then_fail)(request).status_code == 500
    assert count(owner, "sites") == 1  # 오류로 답했어도 남는다(자동 커밋)
    assert TenantMiddleware(write_then_ok)(request).status_code == 201
    assert sorted(owner.execute("SELECT name FROM sites").fetchall()) == [("다 쓴 것",), ("반쯤 쓴 것",)]
    assert seen == [False, False]


def test_exchanging_again_for_another_tenant_switches_the_whole_session(client: Client, sites: tuple[int, int]) -> None:
    """A 의 세션을 든 채 B 의 토큰으로 다시 교환하면: 교환은 토큰의 테넌트로 돌고, 그 뒤로는 B 만 보인다."""
    login(client, sub="edk-user-1", tenant_id="tenant-a")
    body = login(client, sub="edk-user-2", tenant_id="tenant-b")
    assert body["tenant"]["id"] == "tenant-b"
    assert {s["name"][0] for s in client.get("/api/sites").json()["sites"]} == {"B"}
