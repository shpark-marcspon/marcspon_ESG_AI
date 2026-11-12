"""Scope 1·2 엑셀 내려받기 경로 둘(밴드 S12b-1 ③ — service/apis/scope12_excel.py · 발주서 §3-3). 업무 층.

고객사·운영 관리자(작업 회사) 200 · 머리 셋(media·RFC 6266 한글 이름·nosniff) · 내려받은 바이트를 openpyxl 로 다시 열어
시트 꼴 · 쿼리 companyId 는 읽지 않음(회사는 주체에서만) · scope 밖 422 fields.scope · siteId 정수 아님 422 · 해 없음·
남의 siteId 404 · 운영 관리자 회사 둘 400. 몸의 줄·셈은 actions 시험(test_scope12_excel)이 잰다.
★ 이 층의 연결은 주인 역할이다(회사 격리는 tests/security/test_scope12_excel.py 가 앱 역할로 잰다). 클라이언트는
apis/test_entries 의 것(customer · operator_on — 작업 회사 포트를 바꿔 끼움). 이름·값은 지어낸 것이다.
"""

import io
from urllib.parse import quote

import pytest
from django.test import Client
from openpyxl import load_workbook

from esgapi.inventory.service.actions import scope12_excel as actions
from esgapi.inventory.tests.index_selection_support import YEAR, Leaf
from esgapi.inventory.tests.service.actions.test_scope12_excel import World, filled, leaves, world
from esgapi.inventory.tests.service.apis.test_entries import customer, operator_access, operator_on
from esgapi.inventory.tools import scope12_xlsx

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (leaves, world, filled)  # actions 시험의 고정물을 이 모듈에서도 이름으로 찾게

ROOT = f"/api/inventory/scope12/years/{YEAR}"


def _titles(content: bytes) -> list[str]:
    return [sheet.title for sheet in load_workbook(io.BytesIO(content)).worksheets]


def _error(response: object) -> tuple[int, str, list[str]]:
    body = response.json()["error"]  # type: ignore[attr-defined]
    return response.status_code, body["code"], sorted(body.get("fields") or {})  # type: ignore[attr-defined]


def test_a_customer_downloads_both_files_with_the_three_headers(filled: World) -> None:
    client = customer(filled.company_id, "tenant-a")
    for url, sheets, name in (
        (f"{ROOT}/template", scope12_xlsx.TEMPLATE_SHEETS, "_온실가스 인벤토리_데이터_일괄업로드_양식.xlsx"),
        (f"{ROOT}/export", scope12_xlsx.EXPORT_SHEETS, "_온실가스 인벤토리_지역기반_전체(scope 1+2) 데이터.xlsx"),
    ):
        response = client.get(url)
        assert response.status_code == 200, response.content.decode(errors="replace")[:300]
        assert response["Content-Type"] == actions.MEDIA_TYPE
        assert response["X-Content-Type-Options"] == "nosniff"
        disposition = response["Content-Disposition"]
        assert disposition.startswith("attachment; filename*=utf-8''"), disposition
        assert disposition.endswith(quote(name)), disposition  # 한글 이름 → 퍼센트(RFC 6266)
        assert _titles(response.content) == list(sheets)


def test_an_operator_gets_the_work_companys_same_bytes(filled: World, monkeypatch: pytest.MonkeyPatch) -> None:
    mine = customer(filled.company_id, "tenant-a")
    operator = operator_on(filled.company_id, monkeypatch)
    for url in (f"{ROOT}/template", f"{ROOT}/export?scope=1"):
        theirs = operator.get(url)
        assert theirs.status_code == 200, theirs.content.decode(errors="replace")[:300]
        assert theirs.content == mine.get(url).content


def test_an_operator_with_two_companies_is_refused(filled: World) -> None:
    operator = Client(headers={"Authorization": f"Bearer {operator_access()}"})  # 진짜 포트 — 시험 DB 는 회사 둘
    for url in (f"{ROOT}/template", f"{ROOT}/export"):
        assert _error(operator.get(url))[:2] == (400, "COMPANY_AMBIGUOUS")


def test_a_company_id_in_the_query_is_not_read(filled: World, companies: tuple[int, int]) -> None:
    client = customer(filled.company_id, "tenant-a")
    _, b = companies
    for url in (f"{ROOT}/template", f"{ROOT}/export"):
        plain, steered = client.get(url), client.get(f"{url}?companyId={b}")
        assert steered.status_code == 200 and steered.content == plain.content  # 회사는 주체에서만


def test_refusals(filled: World, companies: tuple[int, int], leaves: tuple[Leaf, Leaf, Leaf]) -> None:
    client = customer(filled.company_id, "tenant-a")
    other = World(companies[1], *leaves, prefix="남의")
    assert _error(client.get(f"{ROOT}/template?scope=3")) == (422, "VALIDATION_ERROR", ["scope"])
    assert _error(client.get(f"{ROOT}/export?scope=x"))[:3] == (422, "VALIDATION_ERROR", ["scope"])
    assert _error(client.get(f"{ROOT}/template?siteId=abc"))[:2] == (422, "VALIDATION_ERROR")
    assert _error(client.get(f"{ROOT}/template?siteId={other.ga}"))[:2] == (404, "NOT_FOUND")
    missing = f"/api/inventory/scope12/years/{YEAR + 1}"
    for url in (f"{missing}/template", f"{missing}/export"):
        assert _error(client.get(url))[:2] == (404, "NOT_FOUND")


def test_a_too_long_scope_is_the_same_422_shape(filled: World) -> None:  # 검증 R8(③)
    """4글자 이상은 경로층(Query max_length=3)이, 3글자 안의 밖 값은 actions 가 거른다 — 둘 다 422 VALIDATION_ERROR 에
    fields.scope 하나(화면이 같은 칸에 붙인다). message·legacyCode 는 층마다 지금 글 그대로다(공통 오류 꼴)."""
    client = customer(filled.company_id, "tenant-a")
    for path, why in (("template", actions.BAD_TEMPLATE_SCOPE), ("export", actions.BAD_EXPORT_SCOPE)):
        long = client.get(f"{ROOT}/{path}?scope=alll")
        short = client.get(f"{ROOT}/{path}?scope=x")
        assert (long.status_code, short.status_code) == (422, 422), path
        assert long.json()["error"] == {
            "code": "VALIDATION_ERROR",
            "message": "입력값을 확인해 달라",
            "fields": {"scope": ["String should have at most 3 characters"]},
            "legacyCode": "invalid_input",
        }, path
        assert short.json()["error"] == {
            "code": "VALIDATION_ERROR",
            "message": "입력을 확인한다",
            "fields": {"scope": [why]},
            "legacyCode": "validation_error",
        }, path
