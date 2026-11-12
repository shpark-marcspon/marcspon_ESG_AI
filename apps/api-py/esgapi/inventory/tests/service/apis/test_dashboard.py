"""Scope 1·2 대시보드 경로(밴드 S12a-3 ② — service/apis/dashboard.py · 발주서 §3-3). 업무 층.

고객사·운영 관리자(작업 회사) 200 · 회사 둘 고른 운영 관리자 400 company_ambiguous · 로그인 0 401 · id·Decimal 글자 ·
scope2Market·scope3 null · scope3Categories [] · year 정수 아님 422 · 리스트와 같은 값 · 설정 안 된 해.
셈은 actions 시험이 잰다. ★ 이 층의 연결은 주인 역할이다(회사 격리는 tests/security/test_entries.py 가 앱 역할로 잰다).
이름·값은 지어낸 것이다(손셈: 1000 kg × 1.5 kg/kg = 1.5 tCO2-eq — ghg_pool_support.draft).
"""

from typing import Any
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import get_resolver

from esgapi.core.auth import bearer as bearer_module
from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.conf import app_config, now
from esgapi.inventory.tests.entries_support import Place, place
from esgapi.inventory.tests.ghg_pool_support import activity
from esgapi.inventory.tests.index_selection_support import YEAR, pool_leaf
from esgapi.inventory.tests.service.actions.test_scope3_state import done_body, failed, plant, processed
from tests.support.http import customer_bearer

pytestmark = pytest.mark.django_db

URL = "/api/inventory/scope12/dashboard"
JAN = f"{YEAR}-01"


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


def customer(company_id: int, subdomain: str) -> Client:
    return Client(
        headers={"Authorization": f"Bearer {customer_bearer(Client(), company_id=company_id, subdomain=subdomain)}"}
    )


def operator_on(company_id: int, monkeypatch: pytest.MonkeyPatch) -> Client:
    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: company_id)
    return Client(headers={"Authorization": f"Bearer {operator_access()}"})


def save(client: Client, where: Place) -> Any:
    """1000 kg 한 행 — 손셈 1.5 tCO2-eq."""
    url = f"/api/inventory/scope12/years/{YEAR}/indexes/{where.node_id}/sites/{where.site_id}/rows"
    row = {"siteFacilityId": where.facility_id, "unit": "kg", "values": [{"slot": JAN, "amount": "1000"}]}
    return client.put(url, data={"rows": [row]}, content_type="application/json")


@pytest.fixture
def here(companies: tuple[int, int]) -> Place:
    a, _ = companies
    return place(a, pool_leaf(activity(), "가 보일러"))


def board(client: Client, year: Any = YEAR) -> Any:
    return client.get(URL, {"year": year})


def test_a_customer_reads_text_ids_and_decimals_with_null_scope3(here: Place) -> None:
    client = customer(here.company_id, "tenant-a")
    assert save(client, here).status_code == 200
    response = board(client)
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    assert (body["year"], body["configured"], body["decimals"], body["basis"], body["unit"], body["complete"]) == (
        YEAR,
        True,
        2,
        "location",
        "tCO2-eq",
        True,
    )
    (scope,) = body["scopes"]
    assert isinstance(scope["scopeId"], str) and (scope["scopeName"], scope["value"]) == ("범위 가", "1.5")
    assert scope["scopeOrder"] == 1  # 풀 뿌리 가운데 몇째(DB1 검증 B1)
    (source,) = scope["topSources"]
    assert (source["name"], source["value"], source["share"]) == ("유형 가", "1.5", "100.0")
    assert isinstance(source["nodeId"], str)
    assert body["total"] == {
        "scope12": "1.5",
        "scope2Market": None,
        "scope3": None,
        "sum": "1.5",
        "scope3FailedSheets": 0,
    }
    (site,) = body["bySite"]
    assert site == {
        "siteId": str(here.site_id),
        "siteName": "가 공장",
        "scopes": [{"scopeId": scope["scopeId"], "value": "1.5"}],
        "scope3": None,
    }
    assert body["scope3Categories"] == []
    listed = client.get("/api/inventory/scope12/rows", {"year": YEAR}).json()
    assert [(s["scopeId"], s["values"][str(YEAR)]) for s in listed["scopes"]] == [(scope["scopeId"], scope["value"])]


def test_an_unconfigured_year_is_200_with_empty_scopes(here: Place) -> None:
    body = board(customer(here.company_id, "tenant-a"), YEAR + 1).json()
    assert (body["configured"], body["scopes"], body["complete"]) == (False, [], True)
    assert body["total"] == {
        "scope12": None,
        "scope2Market": None,
        "scope3": None,
        "sum": None,
        "scope3FailedSheets": 0,
    }
    assert body["bySite"] == [{"siteId": str(here.site_id), "siteName": "가 공장", "scopes": [], "scope3": None}]


def test_an_operator_reads_the_work_company(here: Place, monkeypatch: pytest.MonkeyPatch) -> None:
    assert save(customer(here.company_id, "tenant-a"), here).status_code == 200
    response = board(operator_on(here.company_id, monkeypatch))
    assert response.status_code == 200, response.content.decode()
    assert response.json()["total"]["scope12"] == "1.5"


def test_an_operator_with_two_companies_is_400(here: Place) -> None:
    operator = Client(headers={"Authorization": f"Bearer {operator_access()}"})  # 진짜 포트 — 회사 둘
    response = board(operator)
    assert (response.status_code, response.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS")


def test_no_login_is_401(here: Place) -> None:
    assert board(Client()).status_code == 401


def test_a_year_that_is_not_an_integer_is_422(here: Place) -> None:
    client = customer(here.company_id, "tenant-a")
    assert board(client, "올해").status_code == 422
    assert client.get(URL).status_code == 422


# ── S3K2a ②: Scope 3 칸 ──


def test_the_scope3_fields_are_text_and_independent_of_configured(here: Place) -> None:
    client = customer(here.company_id, "tenant-a")
    plant(here.company_id, done_body(processed(4, "1.25"), processed(12, "0.75")))
    unset = board(client).json()  # Scope 1·2 행 저장 전에도 Scope 3 은 셈
    assert unset["total"]["scope3"] == "2"
    assert unset["scope3Categories"] == [
        {"category": "C4", "name": "업스트림 운송 및 유통", "value": "1.25", "share": "62.5"},
        {"category": "C12", "name": "판매된 제품의 폐기", "value": "0.75", "share": "37.5"},
    ]
    assert save(client, here).status_code == 200
    body = board(client).json()
    assert body["total"] == {
        "scope12": "1.5",
        "scope2Market": None,
        "scope3": "2",
        "sum": "3.5",
        "scope3FailedSheets": 0,
    }
    assert [site["scope3"] for site in body["bySite"]] == [None]  # 1차 늘 null
    assert body["complete"] is True


def test_another_year_without_scope12_still_shows_scope3(here: Place) -> None:
    client = customer(here.company_id, "tenant-a")
    plant(here.company_id, done_body(processed(4, "3")), year=YEAR - 1)
    body = board(client, YEAR - 1).json()
    assert (body["configured"], body["scopes"], body["total"]["scope12"]) == (False, [], None)
    assert (body["total"]["scope3"], body["total"]["sum"]) == ("3", "3")


def test_the_failed_sheet_count_is_an_integer(here: Place) -> None:
    client = customer(here.company_id, "tenant-a")
    plant(here.company_id, done_body(processed(4, "1"), failed(4), failed(12)))
    total = board(client).json()["total"]
    assert (total["scope3"], total["scope3FailedSheets"]) == ("1", 2)


def test_scope_order_is_the_pool_rank_when_only_the_second_root_is_chosen(companies: tuple[int, int]) -> None:
    """검증 B1: 둘째 뿌리의 잎만 고른 회사 — scopes 는 하나, scopeOrder 2(화면이 「Scope 2」 자리에 그린다)."""
    a, _ = companies
    activity()  # 첫째 뿌리(범위 가) — 고르지 않는다
    second = place(a, pool_leaf(activity("나"), "나 버너"))
    client = customer(a, "tenant-a")
    assert save(client, second).status_code == 200
    (scope,) = board(client).json()["scopes"]
    assert (scope["scopeName"], scope["scopeOrder"], scope["value"]) == ("범위 나", 2, "1.5")
