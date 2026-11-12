"""고객사 인덱스 선택 경로 둘(밴드 K1b-2b ③ — service/apis/index_selection.py · 발주서 §3-3). 업무 층.

    GET /api/inventory/scope12/index-tree?year=           inventory_scope12_index_tree
    PUT /api/inventory/scope12/index-selections/{year}    inventory_scope12_index_selections_save

★ 이 층의 연결은 주인 역할이다(회사 격리는 tests/security/test_index_selection.py 가 앱 역할로 잰다).
고객사 사용자는 tests/support/http 의 customer_bearer, 운영 관리자는 core 의 토큰 함수로 낸 access 이고 작업 회사는
core/auth/bearer.py 의 포트를 바꿔 끼운다(K1b-1 test_branches 꼴 — 안 바꾸면 진짜 포트가 회사 둘로 400).
이름·값은 지어낸 것이다.
"""

from typing import Any
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import get_resolver

from esgapi.core.auth import bearer as bearer_module
from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.conf import app_config, now
from esgapi.core.exceptions import ApplicationError
from esgapi.inventory.models import CompanyIndexSelection, InventoryYear
from esgapi.inventory.tests.index_selection_support import YEAR, Leaf, current_version, site, two_leaves
from tests.support.http import customer_bearer

pytestmark = pytest.mark.django_db

TREE = f"/api/inventory/scope12/index-tree?year={YEAR}"
SAVE = f"/api/inventory/scope12/index-selections/{YEAR}"


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


@pytest.fixture
def leaves(companies: tuple[int, int]) -> tuple[Leaf, Leaf]:
    a, _ = companies
    boiler, burner = two_leaves()
    site(a, boiler.code_id, burner.code_id)
    return boiler, burner


def put(client: Client, body: dict[str, Any], path: str = SAVE) -> Any:
    return client.put(path, data=body, content_type="application/json")


def error(response: Any) -> tuple[int, str, list[str]]:
    body = response.json()["error"]
    return response.status_code, body["code"], sorted(body.get("fields") or {})


def test_a_customer_saves_and_reads_the_tree(companies: tuple[int, int], leaves: tuple[Leaf, Leaf]) -> None:
    a, _ = companies
    boiler, burner = leaves
    client = customer(a, "tenant-a")
    saved = put(client, {"facilityNodeIds": [boiler.id]})
    assert (saved.status_code, saved.json()) == (200, {"selected": 1, "hiddenWithData": 0})
    found = client.get(TREE)
    assert found.status_code == 200
    body = found.json()
    assert body["year"] == YEAR
    lines = {line["id"]: line for line in body["nodes"]}
    assert all(isinstance(line["id"], str) for line in body["nodes"])  # 응답 id 는 글자
    leaf = lines[str(boiler.id)]
    assert isinstance(leaf["parentId"], str)
    assert {key: value for key, value in leaf.items() if key != "parentId"} == {
        "id": str(boiler.id),
        "level": "facility",
        "name": "가 보일러",
        "facilityCodeId": str(boiler.code_id),
        "availableCount": 1,
        "selected": True,
        "hasFactor": True,
        "hasData": False,
    }
    assert lines[str(burner.id)]["selected"] is False
    upper = next(line for line in body["nodes"] if line["level"] == "activity")
    assert (upper["availableCount"], upper["selected"], upper["hasFactor"], upper["hasData"]) == (2, False, None, None)
    assert CompanyIndexSelection.for_company(a).get().factor_version_id == current_version(boiler.id)


def test_an_operator_works_on_the_chosen_company(
    companies: tuple[int, int], leaves: tuple[Leaf, Leaf], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = companies
    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: a)
    operator = Client(headers={"Authorization": f"Bearer {operator_access()}"})
    assert put(operator, {"facilityNodeIds": [leaves[0].id]}).status_code == 200
    assert operator.get(TREE).status_code == 200
    assert (InventoryYear.for_company(a).count(), InventoryYear.for_company(b).count()) == (1, 0)


def test_an_operator_with_two_companies_is_400(companies: tuple[int, int], leaves: tuple[Leaf, Leaf]) -> None:
    operator = Client(headers={"Authorization": f"Bearer {operator_access()}"})  # 진짜 포트 — 회사 둘
    assert error(operator.get(TREE))[:2] == (400, "COMPANY_AMBIGUOUS")
    assert error(put(operator, {"facilityNodeIds": [leaves[0].id]}))[:2] == (400, "COMPANY_AMBIGUOUS")
    assert InventoryYear.unscoped.count() == 0


def test_an_operator_with_one_inactive_company_is_refused(
    companies: tuple[int, int], leaves: tuple[Leaf, Leaf], monkeypatch: pytest.MonkeyPatch
) -> None:
    """회사 0·비활성은 포트가 끊는다(company_of 400·403) — 여기서는 포트가 그 오류를 던지면 몸에 닿지 않음을 본다."""
    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    refused = ApplicationError("forbidden", "company_inactive", "작업 회사가 비활성이다")

    def inactive() -> int:
        raise refused

    monkeypatch.setattr(bearer_module, "_operator_company", inactive)
    operator = Client(headers={"Authorization": f"Bearer {operator_access()}"})
    assert error(operator.get(TREE))[:2] == (403, "COMPANY_INACTIVE")
    assert error(put(operator, {"facilityNodeIds": [leaves[0].id]}))[:2] == (403, "COMPANY_INACTIVE")
    assert InventoryYear.unscoped.count() == 0


def test_the_body_cannot_name_a_company(companies: tuple[int, int], leaves: tuple[Leaf, Leaf]) -> None:
    a, b = companies
    client = customer(a, "tenant-a")
    assert error(put(client, {"facilityNodeIds": [leaves[0].id], "companyId": b}))[0] == 422
    assert error(put(client, {"facilityNodeIds": ["1"]}))[0] == 422  # 요청 id 는 정수
    assert error(put(client, {"facilityNodeIds": [True]}))[0] == 422
    assert InventoryYear.unscoped.count() == 0


def test_a_bad_year_is_422_on_fields_year(companies: tuple[int, int], leaves: tuple[Leaf, Leaf]) -> None:
    a, _ = companies
    client = customer(a, "tenant-a")
    assert error(client.get("/api/inventory/scope12/index-tree")) == (422, "VALIDATION_ERROR", ["year"])
    assert error(client.get("/api/inventory/scope12/index-tree?year=abc")) == (422, "VALIDATION_ERROR", ["year"])
    assert error(client.get("/api/inventory/scope12/index-tree?year=1989")) == (422, "VALIDATION_ERROR", ["year"])
    late = put(client, {"facilityNodeIds": []}, "/api/inventory/scope12/index-selections/2999")
    assert error(late) == (422, "VALIDATION_ERROR", ["year"])
    assert InventoryYear.unscoped.count() == 0


def test_a_bad_leaf_is_422_on_fields_facility_node_ids(companies: tuple[int, int], leaves: tuple[Leaf, Leaf]) -> None:
    a, _ = companies
    client = customer(a, "tenant-a")
    assert error(put(client, {"facilityNodeIds": [10**9]})) == (422, "VALIDATION_ERROR", ["facilityNodeIds"])
    assert error(put(client, {"facilityNodeIds": list(range(1, 1002))}))[:2] == (422, "VALIDATION_ERROR")
    assert (InventoryYear.unscoped.count(), CompanyIndexSelection.unscoped.count()) == (0, 0)


def test_a_leaf_without_facilities_saves_200_and_its_detail_has_no_sites(companies: tuple[int, int]) -> None:
    """S12-05(MARC-ENT-644): 이 회사에 자산/시설이 없는 잎도 200 으로 고르고, 상세 GET 은 sites [] 200."""
    a, _ = companies
    boiler, burner = two_leaves()
    site(a, boiler.code_id)  # burner 의 코드는 이 회사에 없다
    client = customer(a, "tenant-a")
    saved = put(client, {"facilityNodeIds": [burner.id]})
    assert (saved.status_code, saved.json()) == (200, {"selected": 1, "hiddenWithData": 0})
    lines = {line["id"]: line for line in client.get(TREE).json()["nodes"]}
    assert (lines[str(burner.id)]["availableCount"], lines[str(burner.id)]["selected"]) == (0, True)
    found = client.get(f"/api/inventory/scope12/years/{YEAR}/indexes/{burner.id}")
    assert found.status_code == 200, found.json()
    assert found.json()["sites"] == []
