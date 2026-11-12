"""Scope 1·2 입력 경로 열(밴드 S12a ③ — service/apis/entries.py · 발주서 §3-3). 업무 층.

고객사·운영 관리자(작업 회사) 200 · 풀기 고객사 403 · 운영 관리자 회사 둘 400·비활성 403 · 응답 id·Decimal 글자 ·
요청 id 정수 · 본문 companyId 422 · 422 fields 칸 · 409 locked · 404. 몸의 셈·판정은 actions 시험이 잰다.
S12a-2: 입력주기·행 계수 바꿈(운영 관리자만)·복구 경로 셋 — 블록 period·slots · 행 factor(판·직접입력 보기) · 히스토리
reason·restorable·before/afterFactor · 둘 다/둘 다 없음 422 · 409 restore_stale · 고객사 계수 바꿈·계수 줄 복구 403.
★ 이 층의 연결은 주인 역할이다(회사 격리는 tests/security/test_entries.py 가 앱 역할로 잰다).
고객사 사용자는 tests/support/http 의 customer_bearer, 운영 관리자는 core 의 토큰 함수로 낸 access 이고 작업 회사는
core/auth/bearer.py 의 포트를 바꿔 끼운다(K1b-2b test_index_selection 꼴 — 안 바꾸면 진짜 포트가 회사 둘로 400).
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
from esgapi.core.exceptions import ApplicationError
from esgapi.inventory.models import CompanyIndexSelection, InventoryEntryHistory, InventoryEntryRow, InventoryYear
from esgapi.inventory.service.utils.entries import POOL_UNIT_MISMATCH
from esgapi.inventory.service.utils.ghg_pool import GasDraft
from esgapi.inventory.tests.entries_support import Place, place
from esgapi.inventory.tests.ghg_pool_support import activity, factor
from esgapi.inventory.tests.index_selection_support import YEAR, pool_leaf, site
from esgapi.organization.service.selectors.branches import facilities_of
from tests.support.http import customer_bearer

pytestmark = pytest.mark.django_db

ROOT = "/api/inventory/scope12"
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


@pytest.fixture
def here(companies: tuple[int, int]) -> Place:
    a, _ = companies
    return place(a, pool_leaf(activity(), "가 보일러"))


def index(where: Place) -> str:
    return f"{ROOT}/years/{YEAR}/indexes/{where.node_id}"


def save(client: Client, where: Place, rows: list[dict[str, Any]], site_id: int | None = None) -> Any:
    url = f"{index(where)}/sites/{where.site_id if site_id is None else site_id}/rows"
    return client.put(url, data={"rows": rows}, content_type="application/json")


def line(where: Place, amount: str | None = "1000", **more: Any) -> dict[str, Any]:
    return {"siteFacilityId": where.facility_id, "unit": "kg", "values": [{"slot": JAN, "amount": amount}]} | more


def error(response: Any) -> tuple[int, str, list[str]]:
    body = response.json()["error"]
    return response.status_code, body["code"], sorted(body.get("fields") or {})


def test_a_customer_saves_and_reads_with_text_ids_and_decimals(here: Place) -> None:
    client = customer(here.company_id, "tenant-a")
    saved = save(client, here, [line(here)])
    assert saved.status_code == 200, saved.content.decode()
    body = saved.json()
    assert (body["year"], body["nodeId"], body["unit"], body["locked"], body["lockedBy"]) == (
        YEAR,
        str(here.node_id),
        "tCO2-eq",
        False,
        None,
    )
    assert body["unitOptions"][0] == "kg"
    factor = body["factor"]
    assert (factor["versionId"], factor["isCustom"], factor["factorUnit"]) == (str(here.version_id), False, "kg/kg")
    assert factor["gases"][0]["gas"] == "CO2" and len(factor["gases"]) == 7
    (block,) = body["sites"]
    assert (block["siteId"], [f["id"] for f in block["facilities"]]) == (str(here.site_id), [str(here.facility_id)])
    (row,) = block["rows"]
    assert isinstance(row["rowId"], str) and row["siteFacilityId"] == str(here.facility_id)
    assert row["values"] == [{"slot": JAN, "amount": "1000", "estimated": False}]  # Decimal 글자(끝 0 걷음)
    assert (row["emission"], row["emissionProblem"]) == ("1.5", None)  # 손셈 1.5 tCO2-eq
    assert body["totals"]["all"] == {str(YEAR - 2): None, str(YEAR - 1): None, str(YEAR): "1.5"}
    assert client.get(index(here)).json() == body  # 상세 = 저장 응답

    listed = client.get(f"{ROOT}/rows?year={YEAR}").json()
    assert (listed["configured"], listed["years"], listed["unit"]) == (True, [YEAR - 2, YEAR - 1, YEAR], "tCO2-eq")
    (scope,) = listed["scopes"]
    assert isinstance(scope["scopeId"], str) and scope["values"][str(YEAR)] == "1.5"
    assert [r["nodeId"] for r in scope["rows"]] == [str(here.node_id)]
    assert client.get(f"{ROOT}/years").json() == {"years": [{"year": YEAR, "configured": True}]}

    history = client.get(f"{index(here)}/rows/{row['rowId']}/history?page=1&pageSize=10").json()
    assert (history["count"], history["page"], history["pageSize"], history["hasNext"]) == (1, 1, 10, False)
    (first,) = history["results"]
    assert (first["kind"], first["slot"], first["before"], first["after"]) == ("value", JAN, None, "1000")
    assert first["actor"]["kind"] == "service" and isinstance(first["actor"]["id"], str)
    assert first["at"].endswith("+09:00")


def test_memo_lock_decimals_and_delete(here: Place) -> None:
    client = customer(here.company_id, "tenant-a")
    row_id = save(client, here, [line(here)]).json()["sites"][0]["rows"][0]["rowId"]
    memo = client.put(f"{index(here)}/memo", data={"memo": "메모 가"}, content_type="application/json")
    assert memo.json() == {"memo": "메모 가"}
    decimals = client.put(f"{ROOT}/years/{YEAR}/decimals", data={"decimals": 3}, content_type="application/json")
    assert decimals.json() == {"decimals": 3}
    locked = client.post(f"{index(here)}/lock").json()
    assert (locked["locked"], locked["memo"], locked["decimals"]) == (True, "메모 가", 3)
    assert locked["lockedAt"].endswith("+09:00") and isinstance(locked["lockedBy"]["id"], str)
    assert error(save(client, here, [line(here, "5", rowId=int(row_id))]))[:2] == (409, "LOCKED")
    assert error(client.put(f"{index(here)}/memo", data={"memo": ""}, content_type="application/json"))[:2] == (
        409,
        "LOCKED",
    )
    gone = client.post(f"{index(here)}/rows/delete", data={"ids": [int(row_id)]}, content_type="application/json")
    assert error(gone)[:2] == (409, "LOCKED")
    refused = client.delete(f"{index(here)}/lock")  # 고객사 사용자는 풀지 못한다
    assert error(refused)[:2] == (403, "FORBIDDEN")
    assert CompanyIndexSelection.for_company(here.company_id).get().locked_at is not None


def test_an_operator_works_and_unlocks_on_the_chosen_company(
    companies: tuple[int, int], here: Place, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = companies
    operator = operator_on(a, monkeypatch)
    assert save(operator, here, [line(here)]).status_code == 200
    assert operator.post(f"{index(here)}/lock").json()["locked"] is True
    unlocked = operator.delete(f"{index(here)}/lock")
    assert unlocked.status_code == 200 and unlocked.json()["locked"] is False
    history = InventoryEntryHistory.for_company(a).get()
    assert (history.actor_kind, history.actor_user_id) == ("admin", 1)  # 행위자 = 운영 관리자
    assert InventoryEntryRow.for_company(b).count() == 0


def test_an_operator_with_two_companies_is_400(here: Place) -> None:
    operator = Client(headers={"Authorization": f"Bearer {operator_access()}"})  # 진짜 포트 — 회사 둘
    for response in (
        operator.get(f"{ROOT}/years"),
        operator.get(index(here)),
        save(operator, here, [line(here)]),
        operator.delete(f"{index(here)}/lock"),
    ):
        assert error(response)[:2] == (400, "COMPANY_AMBIGUOUS")
    assert InventoryEntryRow.unscoped.count() == 0


def test_an_operator_with_an_inactive_company_is_refused(here: Place, monkeypatch: pytest.MonkeyPatch) -> None:
    """회사 비활성은 포트가 끊는다(company_of 403) — 포트가 그 오류를 던지면 몸에 닿지 않음을 본다."""
    get_resolver().url_patterns  # noqa: B018
    refused = ApplicationError("forbidden", "company_inactive", "작업 회사가 비활성이다")

    def inactive() -> int:
        raise refused

    monkeypatch.setattr(bearer_module, "_operator_company", inactive)
    operator = Client(headers={"Authorization": f"Bearer {operator_access()}"})
    assert error(save(operator, here, [line(here)]))[:2] == (403, "COMPANY_INACTIVE")
    assert error(operator.delete(f"{index(here)}/lock"))[:2] == (403, "COMPANY_INACTIVE")
    assert InventoryEntryRow.unscoped.count() == 0


def test_the_body_cannot_name_a_company_or_send_text_ids(companies: tuple[int, int], here: Place) -> None:
    _, b = companies
    client = customer(here.company_id, "tenant-a")
    assert error(save(client, here, [line(here) | {"companyId": b}]))[0] == 422
    assert (
        error(
            client.put(
                f"{index(here)}/sites/{here.site_id}/rows",
                data={"rows": [], "companyId": b},
                content_type="application/json",
            )
        )[0]
        == 422
    )
    assert error(save(client, here, [line(here) | {"siteFacilityId": str(here.facility_id)}]))[0] == 422
    assert error(save(client, here, [line(here) | {"na": 1}]))[0] == 422
    assert error(save(client, here, [line(here) | {"factorVersionId": 1}]))[0] == 422  # 판 칸 없음
    deleted = client.post(f"{index(here)}/rows/delete", data={"ids": [True]}, content_type="application/json")
    assert error(deleted)[0] == 422
    decimals = client.put(f"{ROOT}/years/{YEAR}/decimals", data={"decimals": True}, content_type="application/json")
    assert error(decimals)[0] == 422
    assert InventoryEntryRow.unscoped.count() == 0


def test_the_checks_answer_on_fields(here: Place) -> None:
    client = customer(here.company_id, "tenant-a")
    assert error(save(client, here, [line(here, "-1")])) == (422, "VALIDATION_ERROR", ["rows.0.values.0.amount"])
    bad_unit = save(client, here, [line(here) | {"unit": "L"}])
    assert error(bad_unit) == (422, "VALIDATION_ERROR", ["rows.0.unit"])
    memo = client.put(f"{index(here)}/memo", data={"memo": "가" * 2001}, content_type="application/json")
    assert error(memo) == (422, "VALIDATION_ERROR", ["memo"])
    decimals = client.put(f"{ROOT}/years/{YEAR}/decimals", data={"decimals": 9}, content_type="application/json")
    assert error(decimals) == (422, "VALIDATION_ERROR", ["decimals"])
    assert error(client.get(f"{ROOT}/rows?year={YEAR}&q={'가' * 101}"))[:2] == (422, "VALIDATION_ERROR")
    assert InventoryEntryRow.unscoped.count() == 0


def test_missing_things_are_404(here: Place) -> None:
    client = customer(here.company_id, "tenant-a")
    other_year = f"{ROOT}/years/{YEAR - 5}/indexes/{here.node_id}"
    for response in (
        client.get(other_year),
        client.get(f"{ROOT}/years/{YEAR}/indexes/{10**9}"),
        save(client, here, [line(here)], site_id=10**9),
        client.get(f"{index(here)}/rows/{10**9}/history"),
        client.post(f"{index(here)}/rows/delete", data={"ids": [10**9]}, content_type="application/json"),
        client.post(f"{other_year}/lock"),
        client.put(f"{ROOT}/years/{YEAR - 5}/decimals", data={"decimals": 2}, content_type="application/json"),
    ):
        assert error(response)[:2] == (404, "NOT_FOUND"), response.content.decode()
    assert InventoryYear.for_company(here.company_id).count() == 1  # 없는 해를 만들지 않았다


# ── S12a-2: 입력주기 · 행 계수 바꿈 · 복구 ──


CUSTOM: dict[str, Any] = {
    "name": "가 직접 계수",
    "source": "지어낸 출처",
    "baseYear": 2024,
    "tier": 1,
    "countryCode": "KR",
    "industryCode": "other",
    "inputUnit": {"kind": "mass", "unit": "kg"},
    "gases": [{"gas": "CO2", "enabled": True, "factor": "2", "gwp": "1"}],
}


def row_url(where: Place, row_id: str) -> str:
    return f"{index(where)}/rows/{row_id}"


def set_factor(client: Client, where: Place, row_id: str, body: dict[str, Any]) -> Any:
    return client.put(f"{row_url(where, row_id)}/factor", data=body, content_type="application/json")


def restore(client: Client, where: Place, row_id: str, history_id: str, body: dict[str, Any] | None = None) -> Any:
    url = f"{row_url(where, row_id)}/history/{history_id}/restore"
    return client.post(url, data={} if body is None else body, content_type="application/json")


def history_of(client: Client, where: Place, row_id: str) -> list[dict[str, Any]]:
    return client.get(f"{row_url(where, row_id)}/history").json()["results"]


def test_a_period_hides_the_old_slots_and_answers_its_slots(here: Place) -> None:
    client = customer(here.company_id, "tenant-a")
    row_id = save(client, here, [line(here)]).json()["sites"][0]["rows"][0]["rowId"]
    changed = client.put(
        f"{index(here)}/sites/{here.site_id}/period", data={"period": "quarter"}, content_type="application/json"
    )
    assert changed.status_code == 200, changed.content.decode()
    (block,) = changed.json()["sites"]
    assert (block["period"], block["slots"]) == ("quarter", [f"{YEAR}-Q{n}" for n in (1, 2, 3, 4)])
    (row,) = block["rows"]
    assert (row["values"], row["emission"], row["factor"]) == ([], None, None)  # 1월 값은 숨김(지우지 않음)
    top, first = history_of(client, here, row_id)
    assert (top["kind"], top["before"], top["after"], top["reason"], top["restorable"]) == (
        "period",
        "month",
        "quarter",
        None,
        False,  # 맨 위 줄
    )
    assert (first["kind"], first["restorable"], first["beforeFactor"], first["afterFactor"]) == (
        "value",
        False,
        None,
        None,
    )
    stale = restore(client, here, row_id, first["historyId"])  # 1월 칸은 지금 주기 밖
    assert error(stale)[:2] == (409, "RESTORE_STALE")
    quarter = save(
        client, here, [line(here) | {"rowId": int(row_id), "values": [{"slot": f"{YEAR}-Q1", "amount": "2000"}]}]
    )
    assert quarter.json()["sites"][0]["rows"][0]["emission"] == "3"  # 2000 kg × 1.5
    month = save(client, here, [line(here) | {"rowId": int(row_id)}])
    assert error(month) == (422, "VALIDATION_ERROR", ["rows.0.values.0.slot"])  # 분기 블록에 월 칸
    bad = client.put(
        f"{index(here)}/sites/{here.site_id}/period", data={"period": "week"}, content_type="application/json"
    )
    assert error(bad) == (422, "VALIDATION_ERROR", ["period"])
    assert client.get(index(here)).json()["sites"][0]["period"] == "quarter"


def test_an_operator_changes_a_row_factor_and_a_customer_is_403(
    companies: tuple[int, int], here: Place, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    client = customer(a, "tenant-a")
    row_id = save(client, here, [line(here)]).json()["sites"][0]["rows"][0]["rowId"]
    refused = set_factor(client, here, row_id, {"custom": CUSTOM, "reason": "가 사유"})
    assert error(refused)[:2] == (403, "FORBIDDEN")
    operator = operator_on(a, monkeypatch)
    custom = set_factor(operator, here, row_id, {"custom": CUSTOM, "reason": "가 사유"})
    assert custom.status_code == 200, custom.content.decode()
    row = custom.json()["sites"][0]["rows"][0]
    assert (row["emission"], row["factor"]["isCustom"], row["factor"]["name"]) == (
        "2",
        True,
        "가 직접 계수",
    )  # 1000 × 2
    assert isinstance(row["factor"]["customId"], str) and len(row["factor"]["gases"]) == 7
    other = factor(here.node_id, name="계수 나", gases=(GasDraft("CO2", enabled=True, factor="4", gwp="1"),))
    pooled = set_factor(operator, here, row_id, {"factorId": other.id, "reason": "가 사유 둘"})
    pool_row = pooled.json()["sites"][0]["rows"][0]
    assert (pool_row["emission"], pool_row["factor"]["isCustom"], pool_row["factor"]["factorId"]) == (
        "4",
        False,
        str(other.id),
    )
    assert isinstance(pool_row["factor"]["versionId"], str)
    top, mid, _ = history_of(operator, here, row_id)
    assert (top["kind"], top["reason"], top["restorable"]) == ("factor", "가 사유 둘", False)
    assert top["beforeFactor"] == {
        "versionId": None,
        "customId": row["factor"]["customId"],
        "name": "가 직접 계수",
        "isCustom": True,
    }
    assert (top["afterFactor"]["versionId"], top["afterFactor"]["isCustom"]) == (pool_row["factor"]["versionId"], False)
    assert (mid["kind"], mid["beforeFactor"]["versionId"], mid["restorable"]) == ("factor", str(here.version_id), True)
    back = restore(operator, here, row_id, mid["historyId"], {"reason": "되돌림"})  # 직접입력으로(새 줄)
    assert back.json()["sites"][0]["rows"][0]["factor"]["customId"] == row["factor"]["customId"]
    assert error(restore(client, here, row_id, mid["historyId"], {"reason": "되돌림"}))[:2] == (403, "FORBIDDEN")
    assert InventoryEntryHistory.for_company(a).filter(kind="factor").count() == 3


def test_a_customer_restores_a_value_line_as_a_new_line(here: Place) -> None:
    client = customer(here.company_id, "tenant-a")
    row_id = save(client, here, [line(here)]).json()["sites"][0]["rows"][0]["rowId"]
    save(client, here, [line(here, "500") | {"rowId": int(row_id)}])
    top, first = history_of(client, here, row_id)
    assert (top["restorable"], first["restorable"]) == (False, True)
    assert error(restore(client, here, row_id, top["historyId"])) == (422, "VALIDATION_ERROR", ["historyId"])
    back = restore(client, here, row_id, first["historyId"])
    assert back.status_code == 200, back.content.decode()
    assert back.json()["sites"][0]["rows"][0]["emission"] == "1.5"  # 1000 kg 로 — 줄의 after
    assert [line["after"] for line in history_of(client, here, row_id)] == ["1000", "500", "1000"]  # 지우기 0


def test_a_custom_factor_the_rows_units_cannot_reach_is_422_with_the_field(
    companies: tuple[int, int], here: Place, monkeypatch: pytest.MonkeyPatch
) -> None:
    """548(W12-3 ①): 잎 kg 행에 투입 GWh 직접입력 → 422 VALIDATION_ERROR fields.custom.inputUnit · 0 씀."""
    a, _ = companies
    client = customer(a, "tenant-a")
    row_id = save(client, here, [line(here)]).json()["sites"][0]["rows"][0]["rowId"]
    operator = operator_on(a, monkeypatch)
    before = InventoryEntryHistory.for_company(a).count()
    gwh = CUSTOM | {"inputUnit": {"kind": "electricity", "unit": "GWh"}}
    refused = set_factor(operator, here, row_id, {"custom": gwh, "reason": "가 사유"})
    assert error(refused) == (422, "VALIDATION_ERROR", ["custom.inputUnit"])
    assert refused.json()["error"]["fields"]["custom.inputUnit"]
    assert InventoryEntryHistory.for_company(a).count() == before
    assert client.get(index(here)).json()["sites"][0]["rows"][0]["factor"] is None


def test_a_pool_factor_the_rows_units_cannot_reach_is_422_with_factor_id(
    companies: tuple[int, int], here: Place, monkeypatch: pytest.MonkeyPatch
) -> None:
    """558: 잎 kg 행에 투입 GWh 풀 계수 → 422 VALIDATION_ERROR fields.factorId(웹이 그대로 보이는 글) · 0 씀."""
    a, _ = companies
    client = customer(a, "tenant-a")
    row_id = save(client, here, [line(here)]).json()["sites"][0]["rows"][0]["rowId"]
    operator = operator_on(a, monkeypatch)
    before = InventoryEntryHistory.for_company(a).count()
    off = factor(here.node_id, name="계수 전력", input_unit=("electricity", "GWh"))
    refused = set_factor(operator, here, row_id, {"factorId": off.id, "reason": "가 사유"})
    assert error(refused) == (422, "VALIDATION_ERROR", ["factorId"])
    assert refused.json()["error"]["fields"]["factorId"] == [POOL_UNIT_MISMATCH]
    assert InventoryEntryHistory.for_company(a).count() == before
    assert client.get(index(here)).json()["sites"][0]["rows"][0]["factor"] is None


def test_the_new_bodies_refuse_both_or_neither_and_loose_ids(
    companies: tuple[int, int], here: Place, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = companies
    client = customer(a, "tenant-a")
    row_id = save(client, here, [line(here)]).json()["sites"][0]["rows"][0]["rowId"]
    operator = operator_on(a, monkeypatch)
    both = set_factor(operator, here, row_id, {"factorId": 1, "custom": CUSTOM, "reason": "가"})
    neither = set_factor(operator, here, row_id, {"reason": "가"})
    assert error(both) == error(neither) == (422, "VALIDATION_ERROR", ["factorId"])
    assert error(set_factor(operator, here, row_id, {"factorId": True, "reason": "가"}))[0] == 422
    assert error(set_factor(operator, here, row_id, {"factorId": str(1), "reason": "가"}))[0] == 422
    assert error(set_factor(operator, here, row_id, {"factorId": 1, "reason": "가", "companyId": b}))[0] == 422
    assert error(set_factor(operator, here, row_id, {"factorId": 1, "reason": "가", "versionId": 1}))[0] == 422
    period = client.put(
        f"{index(here)}/sites/{here.site_id}/period",
        data={"period": "year", "companyId": b},
        content_type="application/json",
    )
    assert error(period)[0] == 422
    (line_one,) = history_of(client, here, row_id)
    assert error(restore(client, here, row_id, line_one["historyId"], {"companyId": b}))[0] == 422
    assert InventoryEntryHistory.for_company(a).count() == 1  # 거절은 0 씀


def test_the_new_paths_are_404_for_missing_things(here: Place, monkeypatch: pytest.MonkeyPatch) -> None:
    client = customer(here.company_id, "tenant-a")
    row_id = save(client, here, [line(here)]).json()["sites"][0]["rows"][0]["rowId"]
    operator = operator_on(here.company_id, monkeypatch)
    (only,) = history_of(client, here, row_id)
    for response in (
        client.put(f"{index(here)}/sites/{10**9}/period", data={"period": "year"}, content_type="application/json"),
        set_factor(operator, here, str(10**9), {"factorId": 1, "reason": "가"}),
        restore(client, here, str(10**9), only["historyId"]),
        restore(client, here, row_id, str(10**9)),
    ):
        assert error(response)[:2] == (404, "NOT_FOUND"), response.content.decode()


def test_a_line_of_another_row_of_my_company_is_404_on_my_row(here: Place) -> None:
    """(5d ③ B2) 같은 회사·같은 잎의 다른 행 R2 의 줄(맨 위 아님)을 R1 경로로 복구 → 404 · 두 행·히스토리 0 바뀜."""
    client = customer(here.company_id, "tenant-a")
    r1 = save(client, here, [line(here)]).json()["sites"][0]["rows"][0]["rowId"]
    (mine,) = facilities_of(here.company_id, here.site_id)
    other_site = site(here.company_id, mine.facility_code_id, name="가 둘째 공장")
    (facility,) = facilities_of(here.company_id, other_site)
    first = save(client, here, [line(here, "3000") | {"siteFacilityId": facility.id}], site_id=other_site)
    (r2_block,) = [b for b in first.json()["sites"] if b["siteId"] == str(other_site)]
    r2 = r2_block["rows"][0]["rowId"]
    again = [line(here, "4000") | {"siteFacilityId": facility.id, "rowId": int(r2)}]
    assert save(client, here, again, site_id=other_site).status_code == 200
    top, lower = history_of(client, here, r2)
    assert (top["after"], lower["after"], lower["restorable"]) == ("4000", "3000", True)  # 분모: R2 의 복구되는 줄
    before = (client.get(index(here)).json(), history_of(client, here, r1), history_of(client, here, r2))
    assert error(restore(client, here, r1, lower["historyId"]))[:2] == (404, "NOT_FOUND")
    assert (client.get(index(here)).json(), history_of(client, here, r1), history_of(client, here, r2)) == before
