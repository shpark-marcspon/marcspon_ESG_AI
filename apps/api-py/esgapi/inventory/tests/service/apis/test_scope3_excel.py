# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 데이터 엑셀 경로(밴드 S3D1 ① — service/apis/scope3_excel.py). 업무 층.

고객사 200 · 머리 셋(media·RFC 6266 한글 이름·nosniff — critic R4: P5) · 내려받은 바이트를 다시 열어 시트 열다섯 ·
운영 관리자
(작업 회사) 같은 바이트 · 회사 둘 400 · 쿼리 companyId 는 읽지 않음 · R 없음 404 · 해 범위 밖 422 fields.year · 정책 칸
COMPANY(critic R4: P6). 몸의 셈은 actions 시험이 잰다. ★ 이 층의 연결은 주인 역할이다. 값·이름은 지어낸 것이다.
"""

import io
from urllib.parse import quote

import pytest
from django.test import Client
from openpyxl import load_workbook

from esgapi.core.permissions import COMPANY, OPERATION_POLICY
from esgapi.inventory.service.actions import scope3_excel as actions
from esgapi.inventory.tests.service.actions.test_scope3_state import YEAR, done_body, plant, processed
from esgapi.inventory.tests.service.apis.test_entries import customer, operator_access, operator_on
from esgapi.organization.service.selectors.organization import company_name

pytestmark = pytest.mark.django_db
URL = f"/api/inventory/scope3/years/{YEAR}/export"


@pytest.fixture
def a(companies: tuple[int, int]) -> int:
    return companies[0]


def _error(response: object) -> tuple[int, str, list[str]]:
    body = response.json()["error"]  # type: ignore[attr-defined]
    return response.status_code, body["code"], sorted(body.get("fields") or {})  # type: ignore[attr-defined]


def test_a_customer_downloads_the_file_with_the_three_headers(a: int) -> None:
    plant(a, done_body(processed(4, "1.0")))
    response = customer(a, "tenant-a").get(URL)
    assert response.status_code == 200, response.content.decode(errors="replace")[:300]
    assert response["Content-Type"] == actions.MEDIA_TYPE
    assert response["X-Content-Type-Options"] == "nosniff"
    disposition = response["Content-Disposition"]
    assert disposition.startswith("attachment; filename*=utf-8''"), disposition
    assert disposition.endswith(quote(f"{YEAR}_{company_name(a)}_Scope3_데이터.xlsx")), disposition
    titles = [sheet.title for sheet in load_workbook(io.BytesIO(response.content)).worksheets]
    assert titles[0] == "Scope 3 배출량" and len(titles) == 15


def test_an_operator_gets_the_work_companys_same_bytes(a: int, monkeypatch: pytest.MonkeyPatch) -> None:
    plant(a, done_body(processed(4, "1.0")))
    theirs = operator_on(a, monkeypatch).get(URL)
    assert theirs.status_code == 200, theirs.content.decode(errors="replace")[:300]
    assert theirs.content == customer(a, "tenant-a").get(URL).content


def test_an_operator_with_two_companies_is_refused(a: int) -> None:
    plant(a, done_body(processed(4, "1.0")))
    operator = Client(headers={"Authorization": f"Bearer {operator_access()}"})
    assert _error(operator.get(URL))[:2] == (400, "COMPANY_AMBIGUOUS")


def test_a_company_id_in_the_query_is_not_read(a: int, companies: tuple[int, int]) -> None:
    plant(a, done_body(processed(4, "1.0")))
    plant(companies[1], done_body(processed(4, "9.0")))
    client = customer(a, "tenant-a")
    plain, steered = client.get(URL), client.get(f"{URL}?companyId={companies[1]}")
    assert steered.status_code == 200 and steered.content == plain.content


def test_refusals(a: int) -> None:
    client = customer(a, "tenant-a")
    assert _error(client.get(URL))[:2] == (404, "NOT_FOUND")
    assert _error(client.get("/api/inventory/scope3/years/1800/export")) == (422, "VALIDATION_ERROR", ["year"])
    assert _error(client.get("/api/inventory/scope3/years/abc/export"))[:2] == (422, "VALIDATION_ERROR")


def test_the_policy_cell_is_company_work() -> None:
    assert OPERATION_POLICY["inventory_scope3_export"] == COMPANY
