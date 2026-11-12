"""/branches 여섯·/facility-codes·/admin/facility-codes 넷과 옛 /sites 둘(밴드 K1b-1 ② — 발주서 §3-3·3-3′). 업무 층.

★ 이 층의 연결은 주인 역할이다. 행 수는 unscoped 로 센다(분모). 회사 id 는 상수로 박지 않는다(conftest 의 companies).
운영 관리자는 core 의 토큰 함수로 낸 access(test_permissions_wiring 의 operator_access 꼴 — 인증은 DB 0)이고,
작업 회사는 core/auth/bearer.py 의 포트를 회사 하나로 바꿔 끼운다(둘이면 진짜 포트가 400 company_ambiguous).
이름·글은 지어낸 것이다.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import get_resolver

from esgapi.core.auth import bearer as bearer_module
from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.conf import app_config, now
from esgapi.organization.models import FacilityCode, Site, SiteFacility
from esgapi.organization.service.selectors import branches as branch_selectors
from esgapi.organization.service.services import branches as branch_services
from esgapi.organization.service.services import facility_codes as code_services
from esgapi.organization.service.services.branches import ensure_headquarters
from tests.support.http import customer_bearer, login

pytestmark = pytest.mark.django_db


def operator_access() -> str:
    claims = new_access_claims(
        user_id="1",
        kind="admin",
        level=99,
        company_id=None,
        company_is_active=None,
        is_initial=False,
        jti=uuid4(),
        now=now(),
    )
    return sign_access(claims, secret=app_config().session_secret)


@pytest.fixture
def customer(client: Client, companies: tuple[int, int]) -> Client:
    """tenant-a 의 고객사 사용자(옛 교환 쿠키 — 쿠키 세션의 주체는 늘 고객사 사용자)."""
    login(client, tenant_id="tenant-a")
    return client


@pytest.fixture
def operator(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> Client:
    """작업 회사 = tenant-a 인 운영 관리자의 Bearer."""
    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: companies[0])
    return Client(headers={"Authorization": f"Bearer {operator_access()}"})


def call(client: Client, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    if method == "GET":
        return client.get("/api" + path)
    kwargs: dict[str, Any] = {} if body is None else {"data": body, "content_type": "application/json"}
    return getattr(client, method.lower())("/api" + path, **kwargs)


def version(site_id: int | str) -> str:
    """그 사업장의 지금 판(DB 의 updated_at — PUT 본문 updatedAt). UTC 표기다 — GET 의 +09:00 글자와 달라도 같은
    순간이라 지난다(K1b-3 — 견줌은 순간 비교)."""
    return Site.unscoped.get(pk=int(site_id)).updated_at.isoformat()


def code(name: str) -> int:
    made = code_services.create_code(actor_kind="admin", name=name)
    assert not isinstance(made, code_services.CodeNameTaken | code_services.CodesMissing)
    return made.id  # type: ignore[union-attr]


def make_site(company_id: int, name: str, **fields: Any) -> Site:
    return Site.for_company(company_id).create(name=name, **fields)


def error(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


# ── 경로마다 두 주체(고객사 사용자·작업 회사를 고른 운영 관리자)가 지난다 ─────────────


@pytest.mark.parametrize("who", ["customer", "operator"])
def test_every_branch_route_works_for_both_kinds(
    request: pytest.FixtureRequest, companies: tuple[int, int], who: str
) -> None:
    client: Client = request.getfixturevalue(who)
    a, _ = companies
    boiler = code("보일러")
    made = call(
        client,
        "POST",
        "/branches",
        {"name": "가 공장", "facilities": [{"facilityCodeId": boiler, "detailName": "1호기"}]},
    )
    assert made.status_code == 201, made.content.decode()
    branch_id = made.json()["id"]
    assert made.json()["facilities"][0]["facilityCode"] == f"F{boiler:04d}"
    assert call(client, "GET", "/branches").status_code == 200
    assert call(client, "GET", f"/branches/{branch_id}").status_code == 200
    saved = call(
        client,
        "PUT",
        f"/branches/{branch_id}",
        {"name": "가 공장", "inventoryEnabled": False, "facilities": [], "updatedAt": version(branch_id)},
    )
    assert saved.status_code == 200, saved.content.decode()
    assert call(client, "POST", "/branches/inventory", {"ids": [int(branch_id)], "enabled": True}).json() == {
        "count": 1
    }
    assert call(client, "GET", "/facility-codes").json()["items"][0]["name"] == "보일러"
    assert call(client, "POST", "/branches/delete", {"ids": [int(branch_id)]}).json() == {"count": 1}
    # 만든 행의 회사는 작업 회사(운영 관리자) = 주체의 회사(고객사 사용자) = A
    assert list(Site.unscoped.values_list("company_id", flat=True)) == [a]
    assert set(SiteFacility.unscoped.values_list("company_id", flat=True)) == {a}


def test_an_operator_with_two_companies_is_ambiguous_on_branches_but_reads_the_codes(
    companies: tuple[int, int],
) -> None:
    get_resolver().url_patterns  # noqa: B018 — 진짜 포트(회사 둘 → 400)
    client = Client(headers={"Authorization": f"Bearer {operator_access()}"})
    for method, path, body in (
        ("GET", "/branches", None),
        ("POST", "/branches", {"name": "가 공장"}),
        ("POST", "/branches/delete", {"ids": [1]}),
    ):
        assert error(call(client, method, path, body)) == (400, "COMPANY_AMBIGUOUS"), path
    assert call(client, "GET", "/facility-codes").status_code == 200  # 작업 회사를 고르지 않는다
    assert Site.unscoped.count() == 0


def test_a_customer_is_refused_the_four_admin_routes(customer: Client, companies: tuple[int, int]) -> None:
    """고객사 사용자의 Bearer 는 인증을 지나고 권한에서 403(옛 쿠키는 admin 넷에 닿지 않는다 — 401)."""
    access = customer_bearer(Client(), company_id=companies[0], subdomain="tenant-a")
    customer = Client(headers={"Authorization": f"Bearer {access}"})
    boiler = code("보일러")
    for method, path, body in (
        ("GET", "/admin/facility-codes", None),
        ("POST", "/admin/facility-codes", {"name": "냉동기"}),
        ("PATCH", f"/admin/facility-codes/{boiler}", {"name": "냉동기"}),
        ("POST", "/admin/facility-codes/delete", {"ids": [boiler]}),
    ):
        assert error(call(customer, method, path, body)) == (403, "FORBIDDEN"), path
    assert list(FacilityCode.objects.values_list("name", "deleted_at")) == [("보일러", None)]


# ── 목록: 검색·페이지·본사 먼저·삭제 표시 ─────────────────────────────────


def test_the_list_searches_pages_and_puts_the_headquarters_first(customer: Client, companies: tuple[int, int]) -> None:
    a, b = companies
    for name in ("Seoul 공장", "seoul 물류", "부산 공장"):
        make_site(a, name)
    hq = ensure_headquarters(a)
    make_site(b, "Seoul 남의 공장")
    first = call(customer, "GET", "/branches?pageSize=2").json()
    assert [row["name"] for row in first["results"]] == ["본사", "Seoul 공장"]
    assert first["results"][0] == {
        **first["results"][0],
        "id": str(hq),
        "isHeadquarters": True,
        "inventoryEnabled": True,
    }
    assert first["results"][0]["createdAt"].endswith("+09:00")
    assert (first["count"], first["totalPages"], first["hasNext"], first["hasPrevious"]) == (4, 2, True, False)
    second = call(customer, "GET", "/branches?page=2&pageSize=2").json()
    assert [row["name"] for row in second["results"]] == ["seoul 물류", "부산 공장"]
    assert second["hasNext"] is False
    found = call(customer, "GET", "/branches?q=SEOUL").json()
    assert [row["name"] for row in found["results"]] == ["Seoul 공장", "seoul 물류"]  # 대소문자 무시, 남의 회사 0
    empty = call(customer, "GET", "/branches?page=9").json()
    assert (empty["count"], empty["results"], empty["hasNext"]) == (4, [], False)


def test_a_deleted_branch_is_not_listed_nor_found(customer: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    kept = make_site(a, "가 공장")
    gone = make_site(a, "나 공장", deleted_at=now())
    assert [row["id"] for row in call(customer, "GET", "/branches").json()["results"]] == [str(kept.pk)]
    assert error(call(customer, "GET", f"/branches/{gone.pk}")) == (404, "NOT_FOUND")


@pytest.mark.parametrize("query", ["pageSize=0", "pageSize=101", "page=0"])
def test_page_bounds_are_422(customer: Client, query: str) -> None:
    assert error(call(customer, "GET", f"/branches?{query}")) == (422, "VALIDATION_ERROR")


# ── 거절(행 0) ────────────────────────────────────────────────────────


def test_a_taken_name_is_422_on_create_and_save_and_never_500(customer: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    make_site(a, "가 공장")
    other = make_site(a, "나 공장")
    response = call(customer, "POST", "/branches", {"name": "  가 공장 "})  # 앞뒤 공백을 걷어 견준다
    assert error(response) == (422, "VALIDATION_ERROR")
    assert list(response.json()["error"]["fields"]) == ["name"]
    saved = call(
        customer,
        "PUT",
        f"/branches/{other.pk}",
        {"name": "가 공장", "inventoryEnabled": True, "facilities": [], "updatedAt": version(other.pk)},
    )
    assert error(saved) == (422, "VALIDATION_ERROR")
    assert sorted(Site.unscoped.values_list("name", flat=True)) == ["가 공장", "나 공장"]


def test_a_race_on_the_name_is_422_not_500(
    customer: Client, monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    """먼저 조회는 비었다고 보고(경합), 제약이 막는다 → IntegrityError 를 422 로(services 의 블록 바깥 try)."""
    make_site(companies[0], "가 공장")

    def never(*args: object, **kwargs: object) -> bool:
        return False

    monkeypatch.setattr(branch_selectors, "name_taken", never)
    assert error(call(customer, "POST", "/branches", {"name": "가 공장"})) == (422, "VALIDATION_ERROR")
    assert call(customer, "GET", "/branches").status_code == 200  # 바깥 트랜잭션이 깨진 채 남지 않았다
    assert Site.unscoped.count() == 1


def test_a_body_company_field_is_422(customer: Client, companies: tuple[int, int]) -> None:
    assert error(call(customer, "POST", "/branches", {"name": "가 공장", "companyId": companies[1]})) == (
        422,
        "VALIDATION_ERROR",
    )
    assert Site.unscoped.count() == 0


def test_a_deleted_code_is_422_on_pick(customer: Client) -> None:
    boiler = code("보일러")
    assert code_services.delete_codes(actor_kind="admin", ids=[boiler]) == 1
    response = call(
        customer,
        "POST",
        "/branches",
        {"name": "가 공장", "facilities": [{"facilityCodeId": boiler, "detailName": "1호기"}]},
    )
    assert error(response) == (422, "VALIDATION_ERROR")
    assert list(response.json()["error"]["fields"]) == ["facilityCodeId"]
    assert (Site.unscoped.count(), SiteFacility.unscoped.count()) == (0, 0)


def test_the_headquarters_cannot_be_deleted_or_switched_off(customer: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    hq = ensure_headquarters(a)
    plant = make_site(a, "가 공장")
    for path, body in (
        ("/branches/delete", {"ids": [plant.pk, hq]}),
        ("/branches/inventory", {"ids": [plant.pk, hq], "enabled": False}),
    ):
        assert error(call(customer, "POST", path, body)) == (409, "HEADQUARTERS_LOCKED"), path
    saved = call(
        customer,
        "PUT",
        f"/branches/{hq}",
        {"name": "본점", "inventoryEnabled": False, "facilities": [], "updatedAt": version(hq)},
    )
    assert error(saved) == (409, "HEADQUARTERS_LOCKED")
    rows = sorted(Site.unscoped.values_list("name", "inventory_enabled", "deleted_at"))
    assert rows == [("가 공장", True, None), ("본사", True, None)]  # 요청 전체가 거절 — 가 공장도 그대로
    renamed = call(
        customer,
        "PUT",
        f"/branches/{hq}",
        {"name": "본점", "inventoryEnabled": True, "facilities": [], "updatedAt": version(hq)},
    )
    assert renamed.status_code == 200  # 본사 이름 고치기는 된다(감독 판단 8)


def test_another_companys_ids_are_404_and_change_nothing(customer: Client, companies: tuple[int, int]) -> None:
    a, b = companies
    mine = make_site(a, "가 공장")
    theirs = make_site(b, "나 공장")
    boiler = code("보일러")
    their_row = SiteFacility.for_company(b).create(site=theirs, facility_code_id=boiler, detail_name="1호기")
    requests: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
        ("GET", f"/branches/{theirs.pk}", None),
        (
            "PUT",
            f"/branches/{theirs.pk}",
            {"name": "x", "inventoryEnabled": True, "facilities": [], "updatedAt": version(theirs.pk)},
        ),
        ("POST", "/branches/inventory", {"ids": [mine.pk, theirs.pk], "enabled": False}),
        ("POST", "/branches/delete", {"ids": [mine.pk, theirs.pk]}),
        (
            "PUT",
            f"/branches/{mine.pk}",
            {
                "name": "가 공장",
                "inventoryEnabled": True,
                "facilities": [{"id": their_row.pk, "facilityCodeId": boiler, "detailName": "2호기"}],
                "updatedAt": version(mine.pk),
            },
        ),
    )
    for method, path, body in requests:
        assert error(call(customer, method, path, body)) == (404, "NOT_FOUND"), (method, path)
    assert sorted(Site.unscoped.values_list("name", "inventory_enabled", "deleted_at")) == [
        ("가 공장", True, None),
        ("나 공장", True, None),
    ]
    assert list(SiteFacility.unscoped.values_list("detail_name", "site_id", "deleted_at")) == [
        ("1호기", theirs.pk, None)
    ]


def test_an_in_use_code_delete_is_409_on_the_route(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> None:
    """경로가 InUse 갈래를 409 in_use 로 바꾼다(가짜 — 사용 중 판정의 몸은 K1b-2a)."""
    get_resolver().url_patterns  # noqa: B018
    client = Client(headers={"Authorization": f"Bearer {operator_access()}"})
    boiler = code("보일러")

    def used(**kwargs: object) -> branch_services.InUse:
        return branch_services.InUse(frozenset({boiler}))

    monkeypatch.setattr(code_services, "delete_codes", used)
    assert error(call(client, "POST", "/admin/facility-codes/delete", {"ids": [boiler]})) == (409, "IN_USE")


# ── PUT 의 자산/시설: 고침·새로·빠진 것 삭제 표시 ─────────────────────────


def test_put_updates_adds_and_marks_the_missing_facilities_deleted(
    customer: Client, companies: tuple[int, int]
) -> None:
    a, _ = companies
    boiler, chiller = code("보일러"), code("냉동기")
    made = call(
        customer,
        "POST",
        "/branches",
        {
            "name": "가 공장",
            "facilities": [
                {"facilityCodeId": boiler, "detailName": "1호기"},
                {"facilityCodeId": boiler, "detailName": "2호기"},
            ],
        },
    ).json()
    first, second = made["facilities"]
    saved = call(
        customer,
        "PUT",
        f"/branches/{made['id']}",
        {
            "name": "가 공장",
            "inventoryEnabled": True,
            "facilities": [
                {"id": int(first["id"]), "facilityCodeId": boiler, "detailName": "1호기(개조)"},
                {"facilityCodeId": chiller, "detailName": "A동"},
            ],
            "updatedAt": version(made["id"]),
        },
    )
    assert saved.status_code == 200, saved.content.decode()
    assert [(f["facilityName"], f["detailName"]) for f in saved.json()["facilities"]] == [
        ("냉동기", "A동"),
        ("보일러", "1호기(개조)"),
    ]  # 코드 이름 → 세부시설명
    assert SiteFacility.unscoped.get(pk=int(second["id"])).deleted_at is not None  # 빠진 줄은 삭제 표시(지우지 않음)
    assert SiteFacility.unscoped.filter(company_id=a).count() == 3


def test_a_duplicate_facility_in_one_request_is_422(customer: Client) -> None:
    boiler = code("보일러")
    rows = [{"facilityCodeId": boiler, "detailName": "1호기"}, {"facilityCodeId": boiler, "detailName": " 1호기"}]
    response = call(customer, "POST", "/branches", {"name": "가 공장", "facilities": rows})
    assert error(response) == (422, "VALIDATION_ERROR")
    assert list(response.json()["error"]["fields"]) == ["facilities"]
    assert Site.unscoped.count() == 0


# ── 코드 목록: 운영 관리자 넷 ──────────────────────────────────────────────


def test_the_admin_routes_make_rename_page_and_delete_codes(operator: Client, customer: Client) -> None:
    made = call(operator, "POST", "/admin/facility-codes", {"name": "보일러"})
    assert made.status_code == 201
    assert made.json()["code"] == f"F{int(made.json()['id']):04d}"
    call(operator, "POST", "/admin/facility-codes", {"name": "냉동기"})
    assert error(call(operator, "POST", "/admin/facility-codes", {"name": "보일러"})) == (422, "VALIDATION_ERROR")
    renamed = call(operator, "PATCH", f"/admin/facility-codes/{made.json()['id']}", {"name": "증기 보일러"})
    assert renamed.json() == {**made.json(), "name": "증기 보일러"}  # code 그대로
    page = call(operator, "GET", "/admin/facility-codes?pageSize=1").json()
    assert (page["count"], page["totalPages"], [r["name"] for r in page["results"]]) == (2, 2, ["증기 보일러"])
    assert page["results"][0]["inUse"] is False
    assert call(operator, "POST", "/admin/facility-codes/delete", {"ids": [int(made.json()["id"])]}).json() == {
        "count": 1
    }
    assert [item["name"] for item in call(customer, "GET", "/facility-codes").json()["items"]] == ["냉동기"]
    assert error(call(operator, "PATCH", f"/admin/facility-codes/{made.json()['id']}", {"name": "x"})) == (
        404,
        "NOT_FOUND",
    )


# ── 옛 /sites 둘(계약 그대로 — 행은 본사 +1) ──────────────────────────────────


def test_the_old_get_sites_keeps_its_shape_order_and_hides_deleted_rows(
    customer: Client, companies: tuple[int, int]
) -> None:
    a, _ = companies
    plant = make_site(a, "가 공장", external_id="edk-1")
    make_site(a, "나 공장", deleted_at=now())
    hq = ensure_headquarters(a)
    body = call(customer, "GET", "/sites").json()
    assert body == {
        "sites": [
            {"id": str(plant.pk), "name": "가 공장", "externalId": "edk-1"},
            {"id": str(hq), "name": "본사", "externalId": None},
        ]
    }  # 꼴 그대로(칸 셋), 만든 차례 그대로, 삭제 표시 안 보임, 본사 행 +1


def test_the_old_post_sites_turns_a_taken_name_into_422(customer: Client, companies: tuple[int, int]) -> None:
    make_site(companies[0], "가 공장")
    response = call(customer, "POST", "/sites", {"name": "가 공장"})
    assert error(response) == (422, "VALIDATION_ERROR")
    assert list(response.json()["error"]["fields"]) == ["name"]
    assert Site.unscoped.count() == 1


def test_the_old_sites_routes_stay_customer_only(operator: Client) -> None:
    for method, path, body in (("GET", "/sites", None), ("POST", "/sites", {"name": "가 공장"})):
        assert error(call(operator, method, path, body)) == (403, "FORBIDDEN"), path
    assert Site.unscoped.count() == 0


def test_the_old_and_new_routes_call_the_same_inner_functions(
    customer: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """옛 /sites 둘과 /branches 가 같은 안쪽 함수(search_sites·insert_site_row)를 부른다 — 부름 기록으로 잰다(N3)."""
    calls: list[str] = []
    real_search, real_insert = branch_selectors.search_sites, branch_services.insert_site_row

    def search(*args: Any, **kwargs: Any) -> Any:
        calls.append("search")
        return real_search(*args, **kwargs)

    def insert(*args: Any, **kwargs: Any) -> Any:
        calls.append("insert")
        return real_insert(*args, **kwargs)

    monkeypatch.setattr(branch_selectors, "search_sites", search)
    monkeypatch.setattr(branch_services, "insert_site_row", insert)
    assert call(customer, "GET", "/sites").status_code == 200
    assert call(customer, "GET", "/branches").status_code == 200
    assert call(customer, "POST", "/sites", {"name": "가 공장"}).status_code == 201
    assert call(customer, "POST", "/branches", {"name": "나 공장"}).status_code == 201
    assert calls == ["search", "search", "insert", "insert"]


def test_deleting_a_branch_also_marks_its_facilities_deleted(customer: Client, companies: tuple[int, int]) -> None:
    """지운 사업장의 자산/시설도 같은 트랜잭션에서 삭제 표시(R5 — 사업장 밖에서 읽어도 유령 행 0)."""
    a, _ = companies
    boiler = code("보일러")
    plant, other = make_site(a, "가 공장"), make_site(a, "나 공장")
    gone = SiteFacility.for_company(a).create(site=plant, facility_code_id=boiler, detail_name="1호기")
    kept = SiteFacility.for_company(a).create(site=other, facility_code_id=boiler, detail_name="1호기")
    assert call(customer, "POST", "/branches/delete", {"ids": [plant.pk]}).json() == {"count": 1}
    assert SiteFacility.unscoped.get(pk=gone.pk).deleted_at is not None
    assert SiteFacility.unscoped.get(pk=kept.pk).deleted_at is None  # 다른 사업장의 줄은 그대로


def test_the_same_facility_id_twice_in_one_put_is_422(customer: Client, companies: tuple[int, int]) -> None:
    """한 요청에 같은 줄 id 가 두 번이면 어느 쪽이 이기는지 조용히 고르지 않고 422 fields.facilities(R6)."""
    a, _ = companies
    boiler = code("보일러")
    plant = make_site(a, "가 공장")
    row = SiteFacility.for_company(a).create(site=plant, facility_code_id=boiler, detail_name="1호기")
    twice = [
        {"id": row.pk, "facilityCodeId": boiler, "detailName": "2호기"},
        {"id": row.pk, "facilityCodeId": boiler, "detailName": "3호기"},
    ]
    response = call(
        customer,
        "PUT",
        f"/branches/{plant.pk}",
        {"name": "가 공장", "inventoryEnabled": True, "facilities": twice, "updatedAt": version(plant.pk)},
    )
    assert error(response) == (422, "VALIDATION_ERROR")
    assert list(response.json()["error"]["fields"]) == ["facilities"]
    assert list(SiteFacility.unscoped.values_list("detail_name", "deleted_at")) == [("1호기", None)]


# ── 가지 리뷰 고침(커밋 ④) ──────────────────────────────────────────────


def _two_rows(customer: Client, boiler: int) -> tuple[str, dict[str, Any], dict[str, Any]]:
    rows = [{"facilityCodeId": boiler, "detailName": "1호기"}, {"facilityCodeId": boiler, "detailName": "2호기"}]
    made = call(customer, "POST", "/branches", {"name": "가 공장", "facilities": rows}).json()
    first, second = made["facilities"]
    return made["id"], first, second


def test_put_can_swap_two_facilities(customer: Client) -> None:
    """M1: 두 줄의 세부시설명을 맞바꾼다 — 줄마다 고치면 차례에 부분 unique 가 걸리던 자리. id 그대로 200."""
    boiler = code("보일러")
    branch_id, first, second = _two_rows(customer, boiler)
    swapped = [
        {"id": int(first["id"]), "facilityCodeId": boiler, "detailName": "2호기"},
        {"id": int(second["id"]), "facilityCodeId": boiler, "detailName": "1호기"},
    ]
    saved = call(
        customer,
        "PUT",
        f"/branches/{branch_id}",
        {"name": "가 공장", "inventoryEnabled": True, "facilities": swapped, "updatedAt": version(branch_id)},
    )
    assert saved.status_code == 200, saved.content.decode()
    by_id = {f["id"]: f["detailName"] for f in saved.json()["facilities"]}
    assert by_id == {first["id"]: "2호기", second["id"]: "1호기"}
    assert SiteFacility.unscoped.filter(deleted_at__isnull=False).count() == 0  # 잠깐의 삭제 표시는 남지 않는다


def test_put_can_chain_facility_renames(customer: Client) -> None:
    """M1: #1 → #2 의 값, #2 → 새 값(사슬) — 차례 상관없이 200."""
    boiler = code("보일러")
    branch_id, first, second = _two_rows(customer, boiler)
    chained = [
        {"id": int(first["id"]), "facilityCodeId": boiler, "detailName": "2호기"},
        {"id": int(second["id"]), "facilityCodeId": boiler, "detailName": "3호기"},
    ]
    saved = call(
        customer,
        "PUT",
        f"/branches/{branch_id}",
        {"name": "가 공장", "inventoryEnabled": True, "facilities": chained, "updatedAt": version(branch_id)},
    )
    assert saved.status_code == 200, saved.content.decode()
    assert sorted(f["detailName"] for f in saved.json()["facilities"]) == ["2호기", "3호기"]
    # 짝: 끝 상태가 정말 겹치면 그대로 422(줄 둘이 같은 값)
    same = [{**chained[0], "detailName": "3호기"}, chained[1]]
    refused = call(
        customer,
        "PUT",
        f"/branches/{branch_id}",
        {"name": "가 공장", "inventoryEnabled": True, "facilities": same, "updatedAt": version(branch_id)},
    )
    assert error(refused) == (422, "VALIDATION_ERROR")


@pytest.mark.parametrize("bad", ["1", "x", "0", True, 1.5])
def test_a_request_id_that_is_not_a_positive_integer_is_422(customer: Client, bad: object) -> None:
    """요청 id 는 정수만(sid:MARC-ISSUE-92 — 수 글자도 거절): 글자·0·bool·소수는 422. 응답 id 는 글자라 웹이
    Number() 로 바꿔 보낸다(가지 리뷰 M2 는 감독 판단으로 걷음)."""
    assert error(call(customer, "POST", "/branches/delete", {"ids": [bad]})) == (422, "VALIDATION_ERROR")


@pytest.mark.parametrize("query", ["page=100001", "q=" + "가" * 201])
def test_page_and_search_have_an_upper_bound(customer: Client, query: str) -> None:
    """L4: page ≤ 100000, q ≤ 200 글자(넘으면 422)."""
    assert error(call(customer, "GET", f"/branches?{query}")) == (422, "VALIDATION_ERROR")
    assert call(customer, "GET", "/branches?page=100000&q=" + "가" * 200).status_code == 200  # 짝: 끝값은 된다


# ── 낡은 판 거절(밴드 K1b-3 — 발주서 3-1 · sid:MARC-ISSUE-427) ──────────────────────────


def body(name: str, seen: object, **fields: Any) -> dict[str, Any]:
    return {"name": name, "inventoryEnabled": True, "facilities": [], "updatedAt": seen, **fields}


def test_the_detail_carries_its_version_and_a_save_hands_back_the_next(
    customer: Client, companies: tuple[int, int]
) -> None:
    """GET 의 updatedAt = DB 값(µs, +09:00) · 그 판으로 PUT 200 → 응답 판은 다르다(고친 뒤 값) → 그 판으로
    곧장 다시 200."""
    plant = make_site(companies[0], "가 공장")
    stored = Site.unscoped.get(pk=plant.pk).updated_at
    shown = call(customer, "GET", f"/branches/{plant.pk}").json()["updatedAt"]
    assert shown.endswith("+09:00")
    assert datetime.fromisoformat(shown) == stored  # µs 까지 같은 순간
    first = call(customer, "PUT", f"/branches/{plant.pk}", body("나 공장", shown))
    assert first.status_code == 200, first.content.decode()
    after = first.json()["updatedAt"]
    assert after != shown
    assert datetime.fromisoformat(after) == Site.unscoped.get(pk=plant.pk).updated_at  # 응답 판 = 고친 뒤의 DB 값
    again = call(customer, "PUT", f"/branches/{plant.pk}", body("다 공장", after))
    assert again.status_code == 200, again.content.decode()


def test_an_old_version_is_409_stale_and_writes_nothing(customer: Client, companies: tuple[int, int]) -> None:
    """옛 판 → 409 STALE, 사업장 행·자산/시설 줄·updated_at 0 바뀜(낡은 판은 남의 줄을 지우지 못한다)."""
    boiler = code("보일러")
    plant = make_site(companies[0], "가 공장")
    old = version(plant.pk)
    rows = [{"facilityCodeId": boiler, "detailName": "1호기"}]
    added = call(customer, "PUT", f"/branches/{plant.pk}", body("가 공장", old, facilities=rows))
    assert added.status_code == 200, added.content.decode()
    before = Site.unscoped.values_list("name", "inventory_enabled", "updated_at").get(pk=plant.pk)
    lines = list(SiteFacility.unscoped.values_list("id", "detail_name", "deleted_at", "updated_at"))
    refused = call(customer, "PUT", f"/branches/{plant.pk}", body("나 공장", old))  # 옛 판 + 줄 0(= 1호기 지움)
    assert error(refused) == (409, "STALE")
    assert Site.unscoped.values_list("name", "inventory_enabled", "updated_at").get(pk=plant.pk) == before
    assert list(SiteFacility.unscoped.values_list("id", "detail_name", "deleted_at", "updated_at")) == lines


def test_a_toggle_after_the_read_makes_the_old_version_409(customer: Client, companies: tuple[int, int]) -> None:
    """토글(POST /branches/inventory)도 판을 올린다 — 옛 판의 inventoryEnabled 로 덮지 않는다."""
    plant = make_site(companies[0], "가 공장")
    old = version(plant.pk)
    toggled = call(customer, "POST", "/branches/inventory", {"ids": [plant.pk], "enabled": False})
    assert toggled.json() == {"count": 1}
    assert error(call(customer, "PUT", f"/branches/{plant.pk}", body("가 공장", old))) == (409, "STALE")
    assert Site.unscoped.get(pk=plant.pk).inventory_enabled is False


@pytest.mark.parametrize("seen", [None, "", "x", "2026-10-30T09:00:00", "2026-10-30", 1_700_000_000, "9" * 41])
def test_a_missing_or_malformed_version_is_422_on_the_version_field(
    customer: Client, companies: tuple[int, int], seen: object
) -> None:
    """없음·빈·꼴 틀림·시간대 없음·날짜만·수·41자 → 422 fields.updatedAt(행 0)."""
    plant = make_site(companies[0], "가 공장")
    sent = body("나 공장", seen)
    if seen is None:
        del sent["updatedAt"]
    response = call(customer, "PUT", f"/branches/{plant.pk}", sent)
    assert error(response) == (422, "VALIDATION_ERROR")
    assert list(response.json()["error"]["fields"]) == ["updatedAt"]
    assert Site.unscoped.get(pk=plant.pk).name == "가 공장"


def test_the_same_instant_in_another_notation_is_200(customer: Client, companies: tuple[int, int]) -> None:
    """견줌은 순간이다 — 같은 순간의 Z 표기(UTC)로 보내도 200."""
    plant = make_site(companies[0], "가 공장")
    stored = Site.unscoped.get(pk=plant.pk).updated_at
    zulu = stored.astimezone(UTC).isoformat().replace("+00:00", "Z")
    saved = call(customer, "PUT", f"/branches/{plant.pk}", body("나 공장", zulu))
    assert saved.status_code == 200, saved.content.decode()


def test_a_version_cut_to_milliseconds_is_409(customer: Client, companies: tuple[int, int]) -> None:
    """판은 µs 까지 견준다 — 밀리초로 자른 글자(웹이 날짜로 바꿨다 되돌린 꼴)는 같은 판이 아니다 → 409 STALE, 행 0.
    받은 글자 그대로면 200."""
    plant = make_site(companies[0], "가 공장")
    Site.unscoped.filter(pk=plant.pk).update(updated_at=datetime(2026, 10, 30, 0, 0, 0, 123456, tzinfo=UTC))
    shown = call(customer, "GET", f"/branches/{plant.pk}").json()["updatedAt"]
    assert shown == "2026-10-30T09:00:00.123456+09:00"
    cut = shown.replace(".123456", ".123")
    assert error(call(customer, "PUT", f"/branches/{plant.pk}", body("나 공장", cut))) == (409, "STALE")
    assert Site.unscoped.get(pk=plant.pk).name == "가 공장"
    saved = call(customer, "PUT", f"/branches/{plant.pk}", body("나 공장", shown))
    assert saved.status_code == 200, saved.content.decode()


def test_another_companys_branch_is_404_whatever_the_version(customer: Client, companies: tuple[int, int]) -> None:
    """남의 회사 사업장 + 맞는 판·틀린 판 → 둘 다 404(409 0 — 판으로 있음이 새지 않는다). 행 그대로."""
    theirs = make_site(companies[1], "나 공장")
    for seen in (version(theirs.pk), "2000-01-01T00:00:00+09:00"):
        assert error(call(customer, "PUT", f"/branches/{theirs.pk}", body("x", seen))) == (404, "NOT_FOUND"), seen
    assert Site.unscoped.get(pk=theirs.pk).name == "나 공장"


def test_an_old_version_beats_the_headquarters_and_the_line_checks(
    customer: Client, companies: tuple[int, int]
) -> None:
    """판정 차례 404 → 409 stale → 본사 → 줄: 본사 끄기 + 낡은 판은 STALE · 낡은 판 + 그사이 지운 줄 id 도 STALE."""
    hq = ensure_headquarters(companies[0])
    old_hq = version(hq)
    renamed = call(customer, "PUT", f"/branches/{hq}", body("본점", old_hq))
    assert renamed.status_code == 200, renamed.content.decode()
    switched = call(customer, "PUT", f"/branches/{hq}", body("본점", old_hq, inventoryEnabled=False))
    assert error(switched) == (409, "STALE")
    boiler = code("보일러")
    plant = make_site(companies[0], "가 공장")
    line = SiteFacility.for_company(companies[0]).create(site=plant, facility_code_id=boiler, detail_name="1호기")
    old = version(plant.pk)
    dropped = call(customer, "PUT", f"/branches/{plant.pk}", body("가 공장", old))  # 1호기를 지움 → 판이 오른다
    assert dropped.status_code == 200, dropped.content.decode()
    kept = [{"id": line.pk, "facilityCodeId": boiler, "detailName": "1호기"}]
    assert error(call(customer, "PUT", f"/branches/{plant.pk}", body("가 공장", old, facilities=kept))) == (
        409,
        "STALE",
    )  # BASE 는 404(지운 줄 id) — 버전 판정이 먼저


def test_create_takes_no_version_and_hands_one_back(customer: Client) -> None:
    """POST 본문의 updatedAt → 422(만들기는 판이 없다) · POST 201 응답(상세)에 updatedAt."""
    refused = call(customer, "POST", "/branches", {"name": "가 공장", "updatedAt": "2026-10-30T09:00:00+09:00"})
    assert error(refused) == (422, "VALIDATION_ERROR")
    made = call(customer, "POST", "/branches", {"name": "가 공장"})
    assert made.status_code == 201, made.content.decode()
    assert datetime.fromisoformat(made.json()["updatedAt"]) == Site.unscoped.get(pk=int(made.json()["id"])).updated_at
