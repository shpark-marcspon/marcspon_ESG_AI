"""온실가스 풀 경로 열둘(밴드 K1b-2a ③ — service/apis/ghg_pool.py, 발주서 §3-3). 업무 층.

운영 관리자는 core 의 토큰 함수로 낸 access(K1b-1 의 test_branches 꼴 — 인증은 DB 0), 고객사 사용자는 tests/support 의
customer_bearer. 공통 풀이라 회사를 고르지 않는다(작업 회사 포트를 바꿔 끼우지 않아도 지난다).
단언: 열둘 운영 관리자 200/201 · 고객사 403·행 0 · 응답 id 글자·요청 id 정수 · Decimal 글자(지수 0·끝 0 걷음) ·
version 쿼리 · q 조상 · 본문 companyId 422 · 거절 code(404·409·422). 숫자는 뻔한 가짜다(실제 계수·GWP 0).
"""

from typing import Any
from uuid import uuid4

import pytest
from django.test import Client

from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.conf import app_config, now
from esgapi.inventory.models import GhgFactorGas, GhgFactorVersion
from esgapi.inventory.tests.ghg_pool_support import code, counts
from tests.support.http import customer_bearer

pytestmark = pytest.mark.django_db
ROOT = "/api/inventory/admin"


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
def operator() -> Client:
    return Client(headers={"Authorization": f"Bearer {operator_access()}"})


def call(client: Client, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    if method == "GET":
        return client.get(ROOT + path)
    kwargs: dict[str, Any] = {} if body is None else {"data": body, "content_type": "application/json"}
    return getattr(client, method.lower())(ROOT + path, **kwargs)


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.content.decode()
    return response.json()


def error(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def factor_body(**fields: Any) -> dict[str, Any]:
    return {
        "name": "계수 가",
        "source": "지어낸 출처",
        "baseYear": 2024,
        "tier": 1,
        "countryCode": "KR",
        "industryCode": "other",
        "inputUnit": {"kind": "volume", "unit": "L"},
        "gases": [{"gas": "CO2", "enabled": True, "factor": "1234.500", "gwp": "1"}],
        **fields,
    }


def tree(operator: Client) -> dict[str, str]:
    """범위 → 유형 → 활동 → 잎 하나를 경로로 짓는다. 이름 → id(글자)."""
    scope = ok(call(operator, "POST", "/ghg-index/nodes", {"level": "scope", "name": "범위 가"}), 201)
    kind = ok(
        call(
            operator,
            "POST",
            "/ghg-index/nodes",
            {"level": "source_type", "parentId": int(scope["id"]), "name": "유형 가"},
        ),
        201,
    )
    act = ok(
        call(
            operator, "POST", "/ghg-index/nodes", {"level": "activity", "parentId": int(kind["id"]), "name": "활동 가"}
        ),
        201,
    )
    boiler = code("Boiler 가")
    leaf = ok(
        call(
            operator,
            "POST",
            "/ghg-index/facilities",
            {"parentId": int(act["id"]), "facilityCodeId": boiler, "unit": {"kind": "volume", "unit": "L"}},
        ),
        201,
    )
    return {"scope": scope["id"], "kind": kind["id"], "activity": act["id"], "leaf": leaf["id"], "code": str(boiler)}


def test_an_operator_walks_all_twelve_routes(operator: Client) -> None:
    ids = tree(operator)
    roots = ok(call(operator, "GET", "/ghg-index/nodes"))["items"]
    assert roots == [
        {
            "id": ids["scope"],
            "level": "scope",
            "name": "범위 가",
            "parentId": None,
            "sortOrder": int(ids["scope"]),
            "childCount": 1,
            "facilityCodeId": None,
            "facilityCode": None,
        }
    ]
    leaves = ok(call(operator, "GET", f"/ghg-index/nodes?parentId={ids['activity']}"))["items"]
    assert [(row["id"], row["name"], row["facilityCodeId"]) for row in leaves] == [
        (ids["leaf"], "Boiler 가", ids["code"])
    ]
    renamed = ok(call(operator, "PATCH", f"/ghg-index/nodes/{ids['kind']}", {"name": "유형 나"}))
    assert (renamed["id"], renamed["name"]) == (ids["kind"], "유형 나")

    made = ok(call(operator, "POST", f"/ghg-index/facilities/{ids['leaf']}/factors", factor_body()), 201)
    assert isinstance(made["id"], str) and made["facilityNodeId"] == ids["leaf"]
    assert (made["version"], made["versions"], made["isDefault"], made["factorUnit"]) == (1, [1], True, "kg/L")
    assert [gas["gas"] for gas in made["gases"]] == ["CO2", "CH4", "N2O", "HFCs", "PFCs", "SF6", "NF3"]
    assert made["gases"][0] == {"gas": "CO2", "enabled": True, "factor": "1234.5", "gwp": "1"}  # 끝 0 걷음, 글자
    assert made["gases"][1] == {"gas": "CH4", "enabled": False, "factor": None, "gwp": None}
    assert (made["emissionUnit"], made["ncvEnabled"], made["ncv"], made["ncvUnit"]) == (
        {"kind": "mass", "unit": "tCO2-eq"},
        False,
        None,
        None,
    )
    assert made["createdAt"].endswith("+09:00") and made["updatedAt"].endswith("+09:00")

    detail = ok(call(operator, "GET", f"/ghg-index/facilities/{ids['leaf']}"))
    assert (detail["facilityCodeId"], detail["facilityName"], detail["unit"]) == (
        ids["code"],
        "Boiler 가",
        {"kind": "volume", "unit": "L"},
    )
    assert detail["factors"] == [
        {
            "id": made["id"],
            "name": "계수 가",
            "inputUnit": {"kind": "volume", "unit": "L"},
            "isDefault": True,
            "sortOrder": int(made["id"]),
            "version": 1,
        }
    ]
    saved = ok(
        call(
            operator,
            "PUT",
            f"/ghg-index/facilities/{ids['leaf']}",
            {
                "facilityCodeId": int(ids["code"]),
                "unit": {"kind": "volume", "unit": "kL"},
                "tooltip": "설명",
                "defaultFactorId": int(made["id"]),
            },
        )
    )
    assert (saved["unit"], saved["tooltip"]) == ({"kind": "volume", "unit": "kL"}, "설명")

    ncv = {"ncvEnabled": True, "ncv": "0.000000000001", "ncvUnit": {"kind": "energy", "unit": "MJ"}}
    again = ok(call(operator, "PUT", f"/ghg-factors/{made['id']}", factor_body(name="고친 이름", **ncv)))
    assert (again["version"], again["versions"], again["name"], again["ncv"], again["factorUnit"]) == (
        2,
        [1, 2],
        "고친 이름",
        "0.000000000001",  # 지수 표기 0
        "kg/TJ",
    )
    old = ok(call(operator, "GET", f"/ghg-factors/{made['id']}?version=1"))
    now_ = ok(call(operator, "GET", f"/ghg-factors/{made['id']}"))
    assert (old["version"], old["name"], now_["version"], now_["name"]) == (1, "계수 가", 2, "고친 이름")
    assert error(call(operator, "GET", f"/ghg-factors/{made['id']}?version=3")) == (404, "NOT_FOUND")

    options = ok(call(operator, "GET", "/ghg-options"))
    assert options["gases"][0] == "CO2" and options["defaults"]["factorUnitWithNcv"] == "kg/TJ"
    assert {row["kind"] for row in options["units"]} == {"mass", "volume", "energy", "electricity"}

    assert ok(call(operator, "POST", "/ghg-factors/delete", {"ids": [int(made["id"])]})) == {"count": 1}
    assert ok(call(operator, "POST", "/ghg-index/nodes/delete", {"ids": [int(ids["leaf"])]})) == {"count": 1}
    assert GhgFactorVersion.objects.count() == 2 and GhgFactorGas.objects.count() == 14  # 판은 그대로


def test_search_returns_the_matching_nodes_and_their_ancestors(operator: Client) -> None:
    ids = tree(operator)
    found = ok(call(operator, "GET", "/ghg-index/nodes?q=boiler"))["items"]
    assert [row["id"] for row in found] == [ids["scope"], ids["kind"], ids["activity"], ids["leaf"]]
    assert call(operator, "GET", "/ghg-index/nodes?q=" + "가" * 101).status_code == 422  # q ≤ 100자


def test_a_customer_is_refused_all_twelve_and_nothing_changes(operator: Client, companies: tuple[int, int]) -> None:
    ids = tree(operator)
    made = ok(call(operator, "POST", f"/ghg-index/facilities/{ids['leaf']}/factors", factor_body()), 201)
    access = customer_bearer(Client(), company_id=companies[0], subdomain="tenant-a")
    customer = Client(headers={"Authorization": f"Bearer {access}"})
    before = counts()
    leaf, factor = ids["leaf"], made["id"]
    for method, path, body in (
        ("GET", "/ghg-index/nodes", None),
        ("POST", "/ghg-index/nodes", {"level": "scope", "name": "범위 나"}),
        ("PATCH", f"/ghg-index/nodes/{ids['scope']}", {"name": "범위 다"}),
        ("POST", "/ghg-index/nodes/delete", {"ids": [int(leaf)]}),
        ("GET", f"/ghg-index/facilities/{leaf}", None),
        (
            "POST",
            "/ghg-index/facilities",
            {"parentId": int(ids["activity"]), "facilityCodeId": 1, "unit": {"kind": "mass", "unit": "kg"}},
        ),
        (
            "PUT",
            f"/ghg-index/facilities/{leaf}",
            {"facilityCodeId": int(ids["code"]), "unit": {"kind": "mass", "unit": "kg"}},
        ),
        ("POST", f"/ghg-index/facilities/{leaf}/factors", factor_body()),
        ("GET", f"/ghg-factors/{factor}", None),
        ("PUT", f"/ghg-factors/{factor}", factor_body()),
        ("POST", "/ghg-factors/delete", {"ids": [int(factor)]}),
        ("GET", "/ghg-options", None),
    ):
        assert error(call(customer, method, path, body)) == (403, "FORBIDDEN"), path
    assert counts() == before
    assert ok(call(operator, "GET", f"/ghg-index/nodes?parentId={ids['activity']}"))["items"][0]["id"] == leaf


def test_refusals_carry_their_codes_and_fields(operator: Client) -> None:
    ids = tree(operator)
    before = counts()
    refused = call(operator, "POST", "/ghg-index/nodes", {"level": "scope", "name": "x", "companyId": 1})
    assert refused.status_code == 422  # 본문에 회사 칸이 없다
    wrong = call(
        operator, "POST", "/ghg-index/nodes", {"level": "activity", "parentId": int(ids["scope"]), "name": "x"}
    )
    assert error(wrong) == (422, "VALIDATION_ERROR") and set(wrong.json()["error"]["fields"]) == {"parentId"}
    taken = call(operator, "POST", "/ghg-index/nodes", {"level": "scope", "name": "범위 가"})
    assert set(taken.json()["error"]["fields"]) == {"name"}
    bad = call(
        operator,
        "POST",
        f"/ghg-index/facilities/{ids['leaf']}/factors",
        factor_body(gases=[{"gas": "CO2", "enabled": True, "factor": "1e3", "gwp": "1"}]),
    )
    assert error(bad) == (422, "VALIDATION_ERROR") and set(bad.json()["error"]["fields"]) == {"gases.CO2.factor"}
    before = counts()
    mismatched = call(  # K1b-2u: 순발열량 끔 + 투입 L(부피) + 분모 TJ(에너지) → 종류가 안 맞다
        operator, "POST", f"/ghg-index/facilities/{ids['leaf']}/factors", factor_body(factorUnit="kg/TJ")
    )
    assert error(mismatched) == (422, "VALIDATION_ERROR")
    assert set(mismatched.json()["error"]["fields"]) == {"factorUnit"} and counts() == before
    assert error(call(operator, "POST", "/ghg-index/nodes/delete", {"ids": [int(ids["activity"])]})) == (
        409,
        "HAS_CHILDREN",
    )
    assert error(call(operator, "POST", "/ghg-index/nodes/delete", {"ids": [2_000_000_000]})) == (404, "NOT_FOUND")
    assert error(call(operator, "GET", f"/ghg-index/facilities/{ids['activity']}")) == (404, "NOT_FOUND")
    assert error(call(operator, "PATCH", f"/ghg-index/nodes/{ids['leaf']}", {"name": "x"}))[0] == 422
    assert counts() == before
