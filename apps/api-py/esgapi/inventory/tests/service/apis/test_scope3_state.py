# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 연도 상태·카테고리 잠금 경로 셋(밴드 S3K2a ① — service/apis/scope3_state.py · 발주서 1-4). 업무 층.

연도 상태 꼴(id 글자·수 글자·열넷 차례) · 두 역할 잠그기 200 · runId 다름 409 stale_run · runId 빠짐 422 ·
셈한 시트 없음 409 not_computed · 모르는 카테고리 404 · 남의 회사 runId 404(없는 id 와 같은 바이트) · 고객사 풀기 403 ·
운영 관리자 풀기 200 · 해 범위 밖 422 fields.year · 로그인 0 401 · 틀린 Bearer 444 · 회사 둘 고른 운영 관리자 400.
몸의 갈래는 actions 시험이 잰다. ★ 이 층의 연결은 주인 역할이다(회사 격리는 tests/security/test_scope3_state.py).
값·이름은 지어낸 것이다.
"""

from typing import Any

import pytest
from django.test import Client

from esgapi.inventory.models import Scope3CategoryState
from esgapi.inventory.tests.service.actions.test_scope3_state import done_body, failed, plant, processed
from esgapi.inventory.tests.service.apis.test_dashboard import customer, operator_access, operator_on
from tests.support.http import bearer

pytestmark = pytest.mark.django_db

YEAR = 2025


def year_url(year: object = YEAR) -> str:
    return f"/api/inventory/scope3/years/{year}"


def lock_url(category: str, year: object = YEAR) -> str:
    return f"/api/inventory/scope3/years/{year}/categories/{category}/lock"


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


@pytest.fixture
def a(companies: tuple[int, int]) -> int:
    return companies[0]


@pytest.fixture
def mine(a: int) -> Client:
    return customer(a, "tenant-a")


def test_the_year_state_shape(a: int, mine: Client) -> None:
    run = plant(a, done_body(processed(4, "1.50", "2"), failed(4), failed(5)))
    response = mine.get(year_url())
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    assert (body["year"], body["baseRunId"], body["latest"]) == (YEAR, str(run), {"runId": str(run), "status": "done"})
    assert [line["category"] for line in body["categories"]] == [
        "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C11", "C12", "C13", "C14", "C15",
    ]  # fmt: skip
    by = {line["category"]: line for line in body["categories"]}
    assert by["C4"] == {
        "category": "C4",
        "current": {"runId": str(run), "total": "3.5", "sheets": 1, "failedSheets": 1},
        "locked": False,
        "lockedAt": None,
        "lockedBy": None,
        "editedRows": 0,
    }
    assert body["editedRowsUnlocked"] == 0
    assert by["C5"]["current"] == {"runId": str(run), "total": None, "sheets": 0, "failedSheets": 1}


def test_an_empty_year_has_null_runs(mine: Client) -> None:
    body = mine.get(year_url()).json()
    assert (body["baseRunId"], body["latest"]) == (None, None)
    assert {line["current"] for line in body["categories"]} == {None}


def test_both_roles_lock_and_the_operator_unlocks(a: int, mine: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    run = plant(a, done_body(processed(4, "1"), processed(5, "2")))
    locked = mine.post(f"{lock_url('C4')}?runId={run}")
    assert locked.status_code == 200, locked.content.decode()
    body = locked.json()
    assert (body["category"], body["locked"], body["lockedBy"]["name"]) == ("C4", True, "김담당")
    assert body["lockedAt"].endswith("+09:00")
    assert body["current"]["runId"] == str(run)
    operator = operator_on(a, monkeypatch)
    by_operator = operator.post(f"{lock_url('C5')}?runId={run}")
    assert by_operator.status_code == 200, by_operator.content.decode()
    assert code(mine.delete(lock_url("C4"))) == (403, "FORBIDDEN")
    assert Scope3CategoryState.for_company(a).filter(locked_at__isnull=False).count() == 2
    opened = operator.delete(lock_url("C4"))
    assert opened.status_code == 200, opened.content.decode()
    assert (opened.json()["locked"], opened.json()["lockedBy"]) == (False, None)
    assert operator.delete(lock_url("C9")).status_code == 200  # 안 잠겼어도 200


def test_lock_refusals(a: int, b_run: int, mine: Client) -> None:
    old = plant(a, done_body(processed(4, "1"), failed(5)))
    new = plant(a, done_body(processed(4, "2"), failed(5)))
    assert code(mine.post(f"{lock_url('C4')}?runId={old}")) == (409, "STALE_RUN")
    assert code(mine.post(f"{lock_url('C5')}?runId={new}")) == (409, "NOT_COMPUTED")
    assert code(mine.post(f"{lock_url('C10')}?runId={new}")) == (404, "NOT_FOUND")
    missing = mine.post(lock_url("C4"))
    assert missing.status_code == 422
    assert code(mine.post(f"{lock_url('C4')}?runId=x")) == (422, "VALIDATION_ERROR")
    theirs = mine.post(f"{lock_url('C4')}?runId={b_run}")
    nobody = mine.post(f"{lock_url('C4')}?runId=9000000")
    assert code(theirs) == (404, "NOT_FOUND")
    assert theirs.content == nobody.content  # 남의 id 와 없는 id 가 같은 바이트
    assert not Scope3CategoryState.for_company(a).filter(locked_at__isnull=False).exists()


@pytest.fixture
def b_run(companies: tuple[int, int]) -> int:
    return plant(companies[1], done_body(processed(4, "5")))


@pytest.mark.parametrize("year", [1989, 2101])
def test_a_year_out_of_range_is_422(mine: Client, year: int) -> None:
    for response in (mine.get(year_url(year)), mine.post(f"{lock_url('C4', year)}?runId=1")):
        assert code(response) == (422, "VALIDATION_ERROR")
        assert "year" in response.json()["error"]["fields"]


def test_no_login_is_401_and_a_bad_bearer_is_444(a: int) -> None:
    assert Client().get(year_url()).status_code == 401
    assert Client().post(f"{lock_url('C4')}?runId=1").status_code == 401
    assert code(Client().get(year_url(), **bearer("not-a-token"))) == (444, "TOKEN_NOT_VALID")


def test_an_operator_with_two_companies_is_400(a: int) -> None:
    operator = Client(headers={"Authorization": f"Bearer {operator_access()}"})
    for response in (
        operator.get(year_url()),
        operator.post(f"{lock_url('C4')}?runId=1"),
        operator.delete(lock_url("C4")),
    ):
        assert code(response) == (400, "COMPANY_AMBIGUOUS")
