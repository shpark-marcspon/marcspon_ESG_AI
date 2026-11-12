# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""데이터 검증 실행 목록 GET /dataverify/runs 를 진짜 DB 로 잰다(밴드 DV1g §3-2, 업무 층).

    3-2-1  줄 칸: 올린 파일·붙여 넣기·source 없음 + 그린워싱 하나 + 다른 회사 하나 → 데이터 검증·내 회사만, 새 것 먼저,
           칸 집합 = Q5, 옵션의 입력 데이터·중대토픽 글자 0, 만든 사람 이름 · 모르는 사람 「알 수 없는 사용자」
    3-2-2  꼴 어긋난 옵션(source·기업명·보고연도·data) → 200, 그 칸만 null
    3-2-3  상태별: queued · processing(running 단계) · failed(failedStep) · done(요약) · done 인데 요약 없음·꼴 밖 요약
    3-2-4  거름: status 여러 값 · status 하나 · 빈 status 422 · mine · limit 21 422 · offset·count·isNext
    3-2-5  쿼리 수(★E — action 층 많아야 5, HTTP 층은 줄 수와 무관)
    ★I     itemCount = 끝난 실행의 결과 scope.itemCount(지어낸 입력 셋)
운영 관리자는 test_dataverify_operator.py.
★ 실행·단계·결과 행은 apps.get_model 로 심는다(runs.models 를 import 하지 않는다 — 계약 나). 끝까지 도는 실행은
  tests/flows/test_runs_dataverify.py 의 도우미(모의 공급사 — 실제 호출 0). 입력·이름은 전부 지어낸 것이다.
"""

import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.apps import apps
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from pydantic import TypeAdapter
from pytest_django import DjangoAssertNumQueries

from esgapi.dataverify.contracts.digest_shapes import DIGEST_SHAPE
from esgapi.dataverify.contracts.run_list_shapes import DataverifyRunPage
from esgapi.dataverify.service.actions import runs as run_actions
from esgapi.dataverify.tests.flows.support import options, received
from esgapi.dataverify.tests.flows.test_runs_dataverify import (
    World,
    done_run,
    execute,
    new_run,
    result_body,
    run_of,
    scripted,
)
from tests.support.http import login

pytestmark = pytest.mark.django_db

PAGE: TypeAdapter[Any] = TypeAdapter(DataverifyRunPage)
START = datetime(2026, 10, 1, tzinfo=UTC)
STEPS = ("load", "plan", "review", "insight", "report")
FILE = {"kind": "file", "name": "가상 입력.json"}
ROW_FIELDS = {
    "id",
    "status",
    "createdAt",
    "finishedAt",
    "createdBy",
    "source",
    "companyName",
    "reportingYear",
    "itemCount",
    "failedStep",
    "currentStep",
    "stages",
    "checks",
}
DIGEST = {
    "schemaVersion": DIGEST_SHAPE,
    "stages": {
        "plan": {"status": "done", "partial": False},
        "review": {"status": "failed", "partial": None},
        "insight": {"status": "done", "partial": True},
    },
    "checks": {"ok": 3, "fail": 1, "notComputed": 2, "naValues": 1, "toolErrors": 0},
}
_clock = [0]


def seed(
    company_id: int,
    *,
    status: str = "done",
    body: Any = None,
    created_by: int = 1,
    module: str = "dataverify",
    digest: Any = DIGEST,
    failed_step: str | None = None,
    running: str | None = None,
) -> int:
    """실행 행 하나(created_at 은 부를 때마다 1분씩 뒤 — 차례를 박는다)와 단계 다섯·결과(done 이면 result@2 자리 +
    digest — digest=None 이면 요약 없는 옛 실행). running 은 running 으로 심는 단계(processing 이면 그 앞은 done)."""
    _clock[0] += 1
    at = START + timedelta(minutes=_clock[0])
    run_row = apps.get_model("runs", "RunRow")
    made = run_row.for_company(company_id).create(
        company_id=company_id,
        module=module,
        flow_id=f"{module}.probe@1",
        options=options() if body is None else body,
        versions={},
        status=status,
        created_by_user_id=created_by,
        started_at=None if status == "queued" else at,
        finished_at=at + timedelta(seconds=30) if status in ("done", "failed") else None,
        error_code="flow_failed" if status == "failed" else None,
        failed_step=failed_step,
    )
    run_row.for_company(company_id).filter(pk=made.pk).update(created_at=at)
    for position, name in enumerate(STEPS):
        step_status = "done" if status == "done" else "pending"
        if status == "processing":
            step_status = "done" if position < STEPS.index(running or "report") else "pending"
        if name == running:  # processing 밖에 심으면 남은 running 행(목록은 processing 실행만 본다)
            step_status = "running"
        apps.get_model("runs", "RunStepRow").for_company(company_id).create(
            company_id=company_id, run_id=made.pk, name=name, position=position, status=step_status
        )
    if status == "done":
        rows = [{"schemaVersion": "dataverify.result@2", "big": "본문"}] + ([digest] if digest is not None else [])
        for position, found in enumerate(rows):
            apps.get_model("runs", "RunResultRow").for_company(company_id).create(
                company_id=company_id,
                run_id=made.pk,
                position=position,
                schema_version=found["schemaVersion"],
                body=found,
            )
    return made.pk


def me(client: Client) -> int:
    """로그인한 고객사 사용자(가상 「김담당」)의 id."""
    return int(login(client)["user"]["id"])


def listed(client: Client, **params: Any) -> Any:
    return client.get("/api/dataverify/runs", params)


def page_of(client: Client, **params: Any) -> dict[str, Any]:
    response = listed(client, **params)
    assert response.status_code == 200, response.content.decode()
    found: dict[str, Any] = response.json()
    PAGE.validate_python(found, strict=True)
    return found


def ids(found: dict[str, Any]) -> list[int]:
    return [row["id"] for row in found["results"]]


# ── 3-2-1 줄 칸 ──


def test_the_rows_are_my_company_dataverify_runs_newest_first(client: Client, world: World) -> None:
    a, b = world.company_a, world.company_b
    user = me(client)
    file = seed(a, body=options(source=FILE), created_by=user)
    paste = seed(a, body=options(source={"kind": "paste"}), created_by=user)
    bare = seed(a, body=options(), created_by=987_654)  # DV1f 앞 실행(source 없음)·모르는 사람
    seed(a, module="greenwash", body={"parts": {"ceo": [1], "company": [], "climate": []}})
    seed(b, body=options(source=FILE))  # 남의 회사
    found = page_of(client)
    assert ids(found) == [bare, paste, file]
    assert (found["count"], found["isNext"]) == (3, False)
    assert {frozenset(row) for row in found["results"]} == {frozenset(ROW_FIELDS)}
    rows = {row["id"]: row for row in found["results"]}
    assert rows[file]["source"] == FILE
    assert rows[paste]["source"] == {"kind": "paste"}
    assert rows[bare]["source"] is None
    for row in found["results"]:
        assert (row["companyName"], row["reportingYear"], row["itemCount"]) == ("가상기업", "2024", 12)
        assert row["status"] == "done" and row["finishedAt"] is not None and row["createdAt"].endswith("+09:00")
    assert rows[file]["createdBy"] == {"userId": user, "name": "김담당"}
    assert rows[bare]["createdBy"] == {"userId": 987_654, "name": "알 수 없는 사용자"}


def test_the_rows_carry_no_input_data_or_material_topics(client: Client, world: World) -> None:
    me(client)
    seed(world.company_a, body=options(source=FILE))
    text = json.dumps(listed(client).json(), ensure_ascii=False)
    item = received()["data"]["환경"][0]
    for word in ("가상 토픽 A", "가상 산업분류", "materialTopics", "sasbIndustry", '"data"', '"input"', "big", "본문"):
        assert word not in text, word
    assert str(item["항목"]) not in text and str(item["ID"]) not in text
    assert "가상기업" in text  # 분모: 기업명은 싣는다


# ── 3-2-2 꼴 어긋난 옵션 ──


@pytest.mark.parametrize(
    ("change", "nulls"),
    [
        ({"source": {"kind": "file"}}, {"source"}),
        ({"source": {"kind": "x", "name": "a"}}, {"source"}),
        ({"source": "가상 글자"}, {"source"}),
        ({"source": {"kind": "file", "name": "a/b.json"}}, {"source"}),
        ({"source": {"kind": "paste", "name": "a"}}, {"source"}),
        ({"input": {**received(), "company": {"name": 1, "reportingYear": "24"}}}, {"companyName", "reportingYear"}),
        ({"input": {**received(), "data": ["가상"]}}, {"itemCount"}),
        ({"input": {**received(), "data": {"환경": "가상"}}}, {"itemCount"}),
        ({"input": "가상 글자"}, {"companyName", "reportingYear", "itemCount"}),
    ],
)
def test_a_value_out_of_shape_is_null_and_the_row_stays(
    client: Client, world: World, change: dict[str, Any], nulls: set[str]
) -> None:
    me(client)
    good = seed(world.company_a)
    bad = seed(world.company_a, body={**options(), **change})
    found = page_of(client)
    assert ids(found) == [bad, good]
    rows = {row["id"]: row for row in found["results"]}
    for field in ("source", "companyName", "reportingYear", "itemCount"):
        assert (rows[bad][field] is None) == (field in nulls or field == "source"), field
    assert rows[good]["itemCount"] == 12 and rows[good]["companyName"] == "가상기업"


def test_a_missing_theme_is_zero_items(client: Client, world: World) -> None:
    me(client)
    seed(world.company_a, body=options(input=received(environment=False)))
    (row,) = page_of(client)["results"]
    assert row["itemCount"] == 0  # 엔진처럼 없는 테마는 빈 목록(결과 scope.itemCount 와 같음 — ★I)


# ── 3-2-3 상태별 ──


def test_each_status_fills_its_own_fields(client: Client, world: World) -> None:
    a = world.company_a
    me(client)
    queued = seed(a, status="queued")
    processing = seed(a, status="processing", running="review")
    waiting = seed(a, status="processing", running=None)  # 단계 사이(running 없음)
    failed = seed(a, status="failed", failed_step="plan")
    done = seed(a)
    old = seed(a, digest=None)  # 요약을 남기기 전의 옛 실행(★H)
    odd = seed(a, digest={**DIGEST, "checks": {"ok": "3"}})  # 꼴 밖 요약
    rows = {row["id"]: row for row in page_of(client)["results"]}
    picked = ("currentStep", "failedStep", "stages", "checks")
    assert [rows[queued][k] for k in picked] == [None, None, None, None]
    assert [rows[processing][k] for k in picked] == ["review", None, None, None]
    assert [rows[waiting][k] for k in picked] == [None, None, None, None]
    assert [rows[failed][k] for k in picked] == [None, "plan", None, None]
    assert [rows[done][k] for k in picked] == [None, None, DIGEST["stages"], DIGEST["checks"]]
    assert [rows[old][k] for k in picked] == [None, None, None, None]
    assert [rows[odd][k] for k in picked] == [None, None, None, None]
    assert rows[queued]["finishedAt"] is None and rows[failed]["finishedAt"] is not None


def test_a_failed_step_on_a_done_run_and_a_running_step_on_a_failed_run_are_not_shown(
    client: Client, world: World
) -> None:
    a = world.company_a
    me(client)
    done = seed(a, failed_step="plan", running="report")
    failed = seed(a, status="failed", failed_step="review", running="review")
    rows = {row["id"]: row for row in page_of(client)["results"]}
    assert (rows[done]["failedStep"], rows[done]["currentStep"]) == (None, None)
    assert (rows[failed]["failedStep"], rows[failed]["currentStep"]) == ("review", None)


# ── 3-2-4 거름 ──


def test_the_status_filter_takes_several_values(client: Client, world: World) -> None:
    a = world.company_a
    me(client)
    queued, processing = seed(a, status="queued"), seed(a, status="processing", running="plan")
    failed, done = seed(a, status="failed"), seed(a)
    assert ids(page_of(client, status=["queued", "processing"])) == [processing, queued]
    assert page_of(client, status=["queued", "processing"])["count"] == 2
    assert ids(page_of(client, status="done")) == [done]
    assert ids(page_of(client, status=["failed", "done"])) == [done, failed]
    assert ids(page_of(client)) == [done, failed, processing, queued]  # 분모: 거르지 않으면 넷


@pytest.mark.parametrize(
    "query", ["?status=", "?status=canceled", "?limit=21", "?limit=0", "?offset=-1", "?mine=maybe"]
)
def test_a_bad_query_is_422(client: Client, world: World, query: str) -> None:
    me(client)
    response = client.get("/api/dataverify/runs" + query)
    assert response.status_code == 422, response.content.decode()


def test_mine_shows_only_the_runs_i_made(client: Client, world: World) -> None:
    a = world.company_a
    user = me(client)
    mine = seed(a, created_by=user)
    theirs = seed(a, created_by=user + 1000)  # 같은 회사 다른 사람(이 시험의 둘째 로그인과도 다른 id)
    assert ids(page_of(client, mine="true")) == [mine]
    assert ids(page_of(client, mine="false")) == [theirs, mine]  # 분모: false 면 같은 회사 남의 것도 보인다
    other = Client()
    login(other, sub="edk-user-2", name="이담당")
    assert ids(page_of(other, mine="true")) == []  # 다른 사람에게 내 실행은 「내 것」이 아니다


def test_offset_count_and_is_next(client: Client, world: World) -> None:
    me(client)
    made = [seed(world.company_a) for _ in range(23)]
    first, second = page_of(client), page_of(client, offset=20)
    assert (len(first["results"]), first["count"], first["isNext"]) == (20, 23, True)
    assert (len(second["results"]), second["count"], second["isNext"]) == (3, 23, False)
    assert ids(first) + ids(second) == list(reversed(made))
    assert page_of(client, limit=5, offset=30)["results"] == []


# ── 3-2-5 쿼리 수 ──


def test_the_action_reads_at_most_five_queries(world: World, django_assert_num_queries: DjangoAssertNumQueries) -> None:
    a = world.company_a
    for _ in range(3):
        seed(a, status="processing", running="review")
        seed(a)
        seed(a, status="failed")
    with django_assert_num_queries(7):  # 실행 쪽 2(줄·count) · 단계 1 · 요약 1 · 이름 1 · DVI1 +2: 세이브포인트
        found = run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=0)
    assert len(found["results"]) == 9
    with django_assert_num_queries(4):  # 쪽이 비면 단계·요약·이름 0 · DVI1 +2: 세이브포인트
        run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=40)
    with django_assert_num_queries(5):  # processing·done 이 없으면 단계·요약 0(이름 1) · DVI1 +2: 세이브포인트
        run_actions.runs(company_id=a, user_id=1, statuses=["failed"], mine=False, limit=20, offset=0)


def http_queries(client: Client) -> int:
    with CaptureQueriesContext(connection) as captured:
        assert listed(client).status_code == 200
    return len(captured)


def test_the_http_query_count_does_not_grow_with_the_rows(client: Client, world: World) -> None:
    a = world.company_a
    me(client)
    seed(a, status="processing", running="review")
    seed(a)
    few = http_queries(client)
    for _ in range(9):
        seed(a, status="processing", running="plan", created_by=2)
        seed(a, created_by=3)
    many = http_queries(client)
    assert len(page_of(client)["results"]) == 20
    assert few == many


# ── ★I 항목 수 = 결과 scope.itemCount ──


def three_items() -> dict[str, Any]:
    given = received()
    given["data"] = {"환경": copy.deepcopy(given["data"]["환경"][:3]), "사회": copy.deepcopy(given["data"]["환경"][:2])}
    return given


@pytest.mark.parametrize("given", [received, three_items], ids=["twelve", "three"])
def test_the_item_count_equals_the_result_scope_of_a_finished_run(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, given: Any
) -> None:
    run_id = done_run(client, world, monkeypatch, options(input=given()))
    (row,) = page_of(client)["results"]
    assert row["id"] == run_id and row["status"] == "done"
    assert row["itemCount"] == result_body(world, run_id)["scope"]["itemCount"]
    assert row["stages"] is not None and row["checks"] is not None


def test_the_item_count_equals_the_result_scope_without_the_theme(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    run_id = new_run(client, options(input=received(environment=False)))
    execute(world, run_id)
    assert run_of(world, run_id).status == "done" and world.mock.calls == []
    (row,) = page_of(client)["results"]
    assert row["itemCount"] == result_body(world, run_id)["scope"]["itemCount"] == 0
    assert row["stages"] == {k: {"status": "not_run", "partial": None} for k in ("plan", "review", "insight")}


# ── HD1 347 ①(★f): 목록이 options 본문 대신 투영을 읽어도 네 칸이 BASE 셈과 같다 — 데이터 검증 cd 허락(더하기만) ──


def _input(**changes: Any) -> dict[str, Any]:
    return {**received(), **changes}


def _company(**changes: Any) -> dict[str, Any]:
    return _input(company={**received()["company"], **changes})


def _without(key: str) -> dict[str, Any]:
    found = received()
    found.pop(key)
    return found


BRIEF_CASES: dict[str, dict[str, Any]] = {
    "good_file": options(source=FILE),
    "good_paste": options(source={"kind": "paste"}),
    "no_source": options(),
    "source_text": options(source="가상 글자"),
    "source_null": options(source=None),
    "no_input": {"source": FILE},
    "input_text": {"input": "가상 글자"},
    "input_null": {"input": None},
    "company_text": options(input=_input(company="가상 글자")),
    "no_company": options(input=_without("company")),
    "company_null": options(input=_input(company=None)),
    "name_null": options(input=_company(name=None)),
    "name_number": options(input=_company(name=1)),
    "no_name": options(input={**received(), "company": {"reportingYear": "2024"}}),
    "year_number": options(input=_company(reportingYear=2024)),
    "year_short": options(input=_company(reportingYear="24")),
    "data_list": options(input=_input(data=["가상"])),
    "no_data": options(input=_without("data")),
    "data_null": options(input=_input(data=None)),
    "no_theme": options(input=received(environment=False)),
    "theme_text": options(input=_input(data={"환경": "가상"})),
    "theme_null": options(input=_input(data={"환경": None})),
    "theme_empty": options(input=_input(data={"환경": []})),
    "theme_many": options(input=received()),
    "theme_and_other": options(input=_input(data={**received()["data"], "사회": [{"a": 1}]})),
    "nul_in_item": options(input=_input(data={"환경": [{"메모": "가상\x00글"}, {"메모": "둘"}]})),
    "nul_in_name": options(source=FILE, input=_company(name="가상\x00기업")),
    "backslash_u0000_text": options(input=_company(name="가상\\u0000기업")),  # 글자 그대로(진짜 NUL 아님)
}
BRIEF_FIELDS = ("source", "companyName", "reportingYear", "itemCount")


def base_fields(company_id: int, run_id: int) -> dict[str, object]:
    """BASE 의 셈(옵션 본문 → _source·_name·_year·_items — 그 함수들은 HD1 이 0줄)."""
    from esgapi.runs.service.selectors.runs import find_run

    found = find_run(company_id=company_id, run_id=run_id)
    assert found is not None
    opts = found.options
    values = (run_actions._source(opts), run_actions._name(opts), run_actions._year(opts), run_actions._items(opts))  # pyright: ignore[reportPrivateUsage]
    return dict(zip(BRIEF_FIELDS, values, strict=True))


@pytest.mark.parametrize("case", list(BRIEF_CASES))
def test_the_four_fields_equal_the_base_count_for_every_shape(world: World, case: str) -> None:
    a = world.company_a
    run_id = seed(a, body=copy.deepcopy(BRIEF_CASES[case]))
    found = run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=0)
    (row,) = [r for r in found["results"] if r["id"] == run_id]
    assert {field: row[field] for field in BRIEF_FIELDS} == base_fields(a, run_id)


def test_an_old_unwrapped_options_row_counts_the_same(world: World) -> None:
    """감싸지 않은 옛 options(X1b-2b 앞의 값 — OrderedJSONField 가 그대로 읽는 갈래)도 BASE 셈과 같다."""
    from django.db.models import JSONField, Value

    a = world.company_a
    run_id = seed(a)
    body = options(source=FILE, input=_company(name="가상옛기업"))
    run_row = apps.get_model("runs", "RunRow")
    run_row.for_company(a).filter(pk=run_id).update(options=Value(body, output_field=JSONField()))
    found = run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=0)
    (row,) = found["results"]
    assert {field: row[field] for field in BRIEF_FIELDS} == base_fields(a, run_id)
    assert row["companyName"] == "가상옛기업" and row["itemCount"] == 12


def test_every_shape_on_one_page_is_200_and_reads_at_most_five_queries(
    client: Client, world: World, django_assert_max_num_queries: Any
) -> None:
    """\\u0000 이 든 줄이 있어도 쪽이 500 이 아니고(M1) 네 칸이 BASE 와 같고, 쿼리는 그대로 많아야 5."""
    me(client)
    a = world.company_a
    made = {case: seed(a, body=copy.deepcopy(body)) for case, body in BRIEF_CASES.items()}
    rows = {row["id"]: row for offset in (0, 20) for row in page_of(client, limit=20, offset=offset)["results"]}
    assert set(rows) == set(made.values())
    for case, run_id in made.items():
        assert {field: rows[run_id][field] for field in BRIEF_FIELDS} == base_fields(a, run_id), case
    with django_assert_max_num_queries(7):  # DVI1 +2: 세이브포인트
        run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=0)
