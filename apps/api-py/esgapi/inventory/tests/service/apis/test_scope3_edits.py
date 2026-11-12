# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 줄 덧판 경로 넷(밴드 S3K2b-1 ① — service/apis/scope3_edits.py · 발주서 1-4). 업무 층.

응답 꼴(id 글자·시각·이름·batchId) · 두 역할 200 · 몸 꼴 422(모르는 칸·타입) · 409 locked·stale_run · 모르는 카테고리
404 · 남의 회사 실행 404(없는 id 와 같은 바이트) · 히스토리 쪽 넘김 꼴·pageSize 범위 · 로그인 0 401 · 틀린 Bearer 444 ·
회사 둘 고른 운영 관리자 400. 몸의 갈래는 actions 시험이 잰다. ★ 이 층의 연결은 주인 역할이다(회사 격리는
tests/security/test_scope3_edits.py). 값·이름은 지어낸 것이다.
"""

from typing import Any, cast

import pytest
from django.test import Client

from esgapi.inventory.models import Scope3RowEdit
from esgapi.inventory.tests.service.actions.test_scope3_state import YEAR, done_body, plant, processed
from esgapi.inventory.tests.service.apis.test_dashboard import customer, operator_on
from esgapi.inventory.tests.service.apis.test_scope3_runs import SHARED_FIXTURES, World, done_run, result_url
from esgapi.user.service.selectors.user import people_of
from tests.support.http import bearer

pytestmark = pytest.mark.django_db
world, work_company = SHARED_FIXTURES  # 끝까지 시험의 고정물을 이 모듈에서도 이름으로 찾게

ROW1, ROW2 = "가상_C5!20", "가상_C5!21"
BODY: dict[str, object] = {"rowIds": [ROW1], "reason": "가상 사유"}


def run_url(run: object, tail: str) -> str:
    return f"/api/inventory/scope3/runs/{run}/{tail}"


def exclude_url(run: object, category: str = "C5") -> str:
    return run_url(run, f"categories/{category}/exclusions")


def restore_url(run: object, category: str = "C5") -> str:
    return run_url(run, f"categories/{category}/restorations")


def post(client: Client, url: str, body: object = BODY) -> Any:
    return client.post(url, data=body, content_type="application/json")


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


@pytest.fixture
def a(companies: tuple[int, int]) -> int:
    return companies[0]


@pytest.fixture
def mine(a: int) -> Client:
    return customer(a, "tenant-a")


def plant_run(company_id: int) -> int:
    return plant(company_id, done_body(processed(5, "1", "2")))


def test_exclude_restore_and_the_shapes(a: int, mine: Client) -> None:
    run = plant_run(a)
    response = post(mine, exclude_url(run))
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    assert body["category"]["category"] == "C5"
    assert body["category"]["current"]["runId"] == str(run)
    (row,) = body["rows"]
    assert (row["rowId"], row["category"], row["excluded"]) == (ROW1, "C5", True)
    assert row["editedAt"].endswith("+09:00")
    assert post(mine, restore_url(run)).json()["rows"][0]["excluded"] is False

    state = mine.get(run_url(run, "edits")).json()
    assert state["runId"] == str(run)
    assert [(line["rowId"], line["excluded"]) for line in state["rows"]] == [(ROW1, False)]

    history = mine.get(run_url(run, "history")).json()
    assert set(history) == {"count", "totalPages", "page", "pageSize", "hasNext", "hasPrevious", "results"}
    assert (history["count"], history["page"], history["pageSize"]) == (2, 1, 20)
    newest, oldest = history["results"]
    assert (newest["kind"], oldest["kind"]) == ("restore", "exclude")
    assert newest["id"] == str(int(oldest["id"]) + 1)
    assert newest["reason"] == "가상 사유"
    assert newest["at"].endswith("+09:00")
    assert isinstance(newest["batchId"], str) and newest["batchId"] != oldest["batchId"]


def test_the_customer_name_is_read(a: int, mine: Client) -> None:
    """고친 사람은 people_of 로 푼다 — 고객사 사용자 행의 지금 이름."""
    run = plant_run(a)
    assert post(mine, exclude_url(run)).status_code == 200
    made = Scope3RowEdit.for_company(a).get()
    expected = {"id": str(made.actor_user_id), "name": people_of(a, {made.actor_user_id})[made.actor_user_id][1]}
    assert mine.get(run_url(run, "history")).json()["results"][0]["by"] == expected
    assert mine.get(run_url(run, "edits")).json()["rows"][0]["editedBy"] == expected


def test_the_operator_edits_on_the_working_company(a: int, monkeypatch: pytest.MonkeyPatch) -> None:
    run = plant_run(a)
    response = post(operator_on(a, monkeypatch), exclude_url(run))
    assert response.status_code == 200, response.content.decode()
    assert Scope3RowEdit.for_company(a).get().actor_kind == "admin"


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"rowIds": [], "reason": "가상"}, "rowIds"),
        ({"rowIds": [ROW1, ROW1], "reason": "가상"}, "rowIds"),
        ({"rowIds": [ROW1], "reason": "  "}, "reason"),
        ({"rowIds": [ROW1], "reason": "가" * 301}, "reason"),
        ({"rowIds": ["가상_C11!20"], "reason": "가상"}, "rowIds"),
    ],
    ids=["no-rows", "repeated", "blank", "long", "other-row"],
)
def test_a_bad_body_is_422_on_that_field(a: int, mine: Client, body: dict[str, object], field: str) -> None:
    run = plant_run(a)
    response = post(mine, exclude_url(run), body)
    assert code(response) == (422, "VALIDATION_ERROR")
    assert field in response.json()["error"]["fields"]
    assert Scope3RowEdit.for_company(a).count() == 0


@pytest.mark.parametrize(
    "body",
    [
        {"rowIds": [ROW1]},
        {"reason": "가상"},
        {"rowIds": ROW1, "reason": "가상"},
        {"rowIds": [1], "reason": "가상"},
        {"rowIds": [ROW1], "reason": 1},
        {"rowIds": [ROW1], "reason": "가상", "companyId": 1},
    ],
    ids=["no-reason", "no-rows", "text-rows", "int-row", "int-reason", "unknown-field"],
)
def test_a_body_of_the_wrong_shape_is_422(a: int, mine: Client, body: dict[str, object]) -> None:
    assert post(mine, exclude_url(plant_run(a)), body).status_code == 422


def test_conflicts_and_not_found(a: int, mine: Client) -> None:
    old = plant_run(a)
    run = plant_run(a)
    assert code(post(mine, exclude_url(old))) == (409, "STALE_RUN")
    assert mine.post(f"/api/inventory/scope3/years/{YEAR}/categories/C5/lock?runId={run}").status_code == 200
    assert code(post(mine, exclude_url(run))) == (409, "LOCKED")
    assert code(post(mine, restore_url(run))) == (409, "LOCKED")
    assert code(post(mine, exclude_url(run, "C10"))) == (404, "NOT_FOUND")
    assert Scope3RowEdit.for_company(a).count() == 0


def test_another_companys_run_is_the_same_404_as_none(companies: tuple[int, int], mine: Client) -> None:
    theirs = plant_run(companies[1])
    for url in (exclude_url, restore_url):
        foreign, missing = post(mine, url(theirs)), post(mine, url(theirs + 1_000_000))
        assert code(foreign) == (404, "NOT_FOUND")
        assert foreign.content == missing.content
    for tail in ("edits", "history"):
        foreign, missing = mine.get(run_url(theirs, tail)), mine.get(run_url(theirs + 1_000_000, tail))
        assert code(foreign) == (404, "NOT_FOUND")
        assert foreign.content == missing.content


def test_history_pages_and_filters_on_the_route(a: int, mine: Client) -> None:
    run = plant_run(a)
    assert post(mine, exclude_url(run), {"rowIds": [ROW1, ROW2], "reason": "가상"}).status_code == 200
    first = mine.get(run_url(run, "history?page=1&pageSize=1")).json()
    assert (first["count"], first["totalPages"], first["hasNext"], first["hasPrevious"]) == (2, 2, True, False)
    second = mine.get(run_url(run, "history?page=2&pageSize=1")).json()
    assert (second["hasNext"], second["hasPrevious"]) == (False, True)
    assert first["results"][0]["rowId"] == ROW2 and second["results"][0]["rowId"] == ROW1
    only = mine.get(run_url(run, "history"), {"rowId": ROW1}).json()
    assert [line["rowId"] for line in only["results"]] == [ROW1]


@pytest.mark.parametrize("query", ["pageSize=0", "pageSize=101", "page=0", "page=100001", "pageSize=x"])
def test_history_paging_out_of_range_is_422(a: int, mine: Client, query: str) -> None:
    assert mine.get(run_url(plant_run(a), f"history?{query}")).status_code == 422


def test_the_result_get_stays_the_original_after_an_exclusion(client: Client, world: World) -> None:
    """§3: 편집은 결과 본문에 덮지 않는다 — 진짜 실행의 결과 GET 바이트가 제외 앞뒤로 같다."""
    run = done_run(client, world)
    before = client.get(result_url(run))
    assert before.status_code == 200, before.content.decode()
    sheet = next(item for item in before.json()["sheets"] if item["status"] == "processed" and item["rows"])
    category = sheet["category"].replace("Category", "C")
    edited = post(client, exclude_url(run, category), {"rowIds": [sheet["rows"][0]["rowId"]], "reason": "가상 사유"})
    assert edited.status_code == 200, edited.content.decode()
    assert edited.json()["rows"][0]["excluded"] is True
    assert client.get(result_url(run)).content == before.content


def test_no_login_is_401_and_a_bad_bearer_is_444(a: int) -> None:
    run = plant_run(a)
    assert post(Client(), exclude_url(run)).status_code == 401
    assert Client().get(run_url(run, "edits")).status_code == 401
    assert code(Client().get(run_url(run, "edits"), **bearer("not-a-token"))) == (444, "TOKEN_NOT_VALID")


def test_an_operator_with_two_companies_is_400(companies: tuple[int, int]) -> None:
    from esgapi.inventory.tests.service.apis.test_dashboard import operator_access

    operator = Client(headers={"Authorization": f"Bearer {operator_access()}"})
    assert code(post(operator, exclude_url(plant_run(companies[0])))) == (400, "COMPANY_AMBIGUOUS")


# ── 계수 수정(S3K2b-2) ──


def factor_url(run: object, category: str = "C1") -> str:
    return run_url(run, f"categories/{category}/factors")


def factor_body(**over: object) -> dict[str, object]:
    return {"rowId": BUY_ROW, "choice": "custom", "rank": None, "reason": "가상 사유"} | {"custom": CUSTOM} | over


BUY_ROW = "가상_C1!20"
CUSTOM: dict[str, object] = {"title": "가상 계수", "value": "2.0", "source": "가상 출처"}


def plant_buy(company_id: int) -> int:
    row = {
        "rowId": BUY_ROW,
        "kind": "purchase",
        "amount": "1000.0",
        "factor": {"title": "가상 원안", "value": "0.5", "unit": "kgCO2e/KRW", "column": "가상 열"},
        "co2e": "0.5",
        "recommendations": [{"title": "가상 추천", "value": "0.25", "expectedCo2e": "0.25"}],
    }
    sheet = {"sheet": "가상_C1", "category": "Category1", "status": "processed", "rows": [row]}
    investment = {"rowId": "가상_C15!20", "kind": "investment", "co2e": "1.0", "factor": None}
    other = {"sheet": "가상_C15", "category": "Category15", "status": "processed", "rows": [investment]}
    body: dict[str, object] = {**done_body(cast("Any", sheet), cast("Any", other))}
    return plant(company_id, body | {"factorBook": {"sheet": "가상_구매표", "column": "가상 열"}})


def test_a_factor_post_answers_the_category_and_the_row_for_both_roles(
    a: int, mine: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = plant_buy(a)
    found = post(mine, factor_url(run), factor_body())
    assert found.status_code == 200, found.content.decode()
    data = found.json()
    assert data["category"]["editedRows"] == 1
    (line,) = data["rows"]
    assert line["factor"] == {
        "choice": "custom",
        "rank": None,
        "title": "가상 계수",
        "value": "2.0",
        "source": "가상 출처",
        "unit": "kgCO2e/KRW",
        "co2e": "2.0",
        "biogenicCo2e": None,
        "ai": {"title": "가상 원안", "value": "0.5", "source": "가상_구매표 가상 열", "co2e": "0.5"},
    }
    edits_rows = mine.get(run_url(run, "edits")).json()["rows"]
    assert edits_rows[0]["factor"]["choice"] == "custom"
    history = mine.get(run_url(run, "history")).json()["results"]
    assert [(line["kind"], line["factor"]["choice"]) for line in history] == [("factor", "custom")]
    by_operator = operator_on(a, monkeypatch)
    again = post(by_operator, factor_url(run), factor_body(choice="applied", custom=None))
    assert again.status_code == 200, again.content.decode()


def test_exclude_history_lines_have_no_factor(a: int, mine: Client) -> None:
    run = plant_run(a)
    post(mine, exclude_url(run))
    (line,) = mine.get(run_url(run, "history")).json()["results"]
    assert line["factor"] is None
    assert mine.get(run_url(run, "edits")).json()["rows"][0]["factor"] is None


def test_a_factor_post_refusals_have_their_codes(a: int, mine: Client) -> None:
    run = plant_buy(a)
    assert code(post(mine, factor_url(run, "C15"), factor_body(rowId="가상_C15!20"))) == (409, "FACTOR_NOT_EDITABLE")
    assert code(post(mine, factor_url(999_999), factor_body())) == (404, "NOT_FOUND")
    assert code(post(mine, factor_url(run, "C10"), factor_body())) == (404, "NOT_FOUND")
    bad = post(mine, factor_url(run), factor_body(custom=CUSTOM | {"value": "0"}))
    assert bad.status_code == 422
    assert bad.json()["error"]["fields"] == {"custom.value": ["0보다 큰 수다"]}
    bad_rank = post(mine, factor_url(run), factor_body(choice="recommended", rank=1))
    assert bad_rank.json()["error"]["fields"] == {"custom": ["직접 입력을 고를 때만 보낸다"]}
    assert Scope3RowEdit.for_company(a).count() == 0


def test_a_factor_post_closes_its_body(a: int, mine: Client) -> None:
    run = plant_buy(a)
    assert post(mine, factor_url(run), factor_body(rank=True)).status_code == 422
    assert post(mine, factor_url(run), factor_body(extra=1)).status_code == 422
    assert post(mine, factor_url(run), factor_body(choice="가상")).status_code == 422
    assert Scope3RowEdit.for_company(a).count() == 0
