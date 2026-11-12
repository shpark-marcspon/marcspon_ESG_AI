# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""중대성평가 IRO 실행 목록 GET /materiality/runs 를 진짜 DB 로 잰다(밴드 IR3c §3-2, 업무 층 — DV1g 꼴).

    3-2-1  줄 칸: IRO 셋(done·queued·failed) + 데이터 검증 하나 + 남의 회사 하나 → 중대성평가·내 회사만, 새 것 먼저,
           칸 집합 = 처분 ③, 토픽 이름·설명·산업 설명·서브토픽·가치사슬 글자 0(표지), 만든 사람 · 「알 수 없는 사용자」
    3-2-2  꼴 어긋난 옵션(산업·토픽·기업명·기간·최신 이슈 반영·input) → 200, 그 칸만 null
    3-2-3  상태별: queued · processing(running 단계) · failed(failedStep, 두 수 null) · done(요약) · done 인데 요약
           없음·꼴 밖 요약 · done·part2 not_run(null)
    3-2-4  거름: status 여러 값 · status 하나 · 빈 status 422 · mine · limit 21 422 · offset·count·isNext
    3-2-5  쿼리 수(★E — action 층 많아야 5, HTTP 층은 줄 수와 무관)
    ★I     끝까지 돈 실행(지어낸 입력·답 셋): topicCount = 결과 scope.topicCount, 두 수 = 최종 엑셀 2-1·2-2 데이터 줄 수
운영 관리자는 test_materiality_operator.py, 이어 돌기(★H)는 tests/flows/test_runs_materiality.py.
★ 실행·단계·결과 행은 apps.get_model 로 심는다(runs.models 를 import 하지 않는다 — 계약 나). 끝까지 도는 실행은
  tests/flows/test_runs_materiality.py 의 도우미(모의 공급사 — 실제 호출 0). 입력·이름은 전부 지어낸 것이다.
"""

import copy
import io
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from django.apps import apps
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import TypeAdapter
from pytest_django import DjangoAssertNumQueries

from esgapi.materiality.contracts.digest_shapes import DIGEST_SHAPE
from esgapi.materiality.contracts.run_list_shapes import MaterialityRunPage
from esgapi.materiality.flows import iro_155
from esgapi.materiality.outputs import final_xlsx
from esgapi.materiality.service.actions import runs as run_actions
from esgapi.materiality.tests.flows import support
from esgapi.materiality.tests.flows.support import options, received2
from esgapi.materiality.tests.flows.test_runs_materiality import (
    World,
    execute,
    new_run,
    result_body,
    run_of,
    scripted,
    stored,
)
from tests.support.http import login

pytestmark = pytest.mark.django_db

PAGE: TypeAdapter[Any] = TypeAdapter(MaterialityRunPage)
START = datetime(2026, 10, 1, tzinfo=UTC)
STEPS = iro_155.FLOW.steps
MARK = "ZZ-표지"
ROW_FIELDS = {
    "id",
    "status",
    "createdAt",
    "startedAt",
    "finishedAt",
    "createdBy",
    "companyName",
    "industries",
    "topicCount",
    "dateRange",
    "latestEventMode",
    "failedStep",
    "currentStep",
    "impactRows",
    "pathwayRows",
}
INDUSTRIES = [
    {"standard": "SASB", "industryName": "가상 산업 하나(Virtual Industry A)"},
    {"standard": "KSIC", "industryName": "가상 산업 둘"},
]
DIGEST = {"schemaVersion": DIGEST_SHAPE, "impactRows": 4, "pathwayRows": 3}
_clock = [0]


def marked() -> dict[str, Any]:
    """옵션의 싣지 않는 칸마다 표지를 심은 입력(토픽 설명·산업 설명·서브토픽·가치사슬·범위)."""
    given = received2()
    for topic in given["topics"]:
        topic["description"] = f"{topic['description']} {MARK}"
    for industry in given["industries"]:
        industry["description"] = f"{industry['description']} {MARK}"
    for subs in given["subtopicsByTopic"].values():
        for sub in subs:
            sub["description"] = f"{sub['description']} {MARK}"
    given["valueChain"][0]["business_activity"] = MARK
    given["geoScope"] = MARK
    return given


def seed(
    company_id: int,
    *,
    status: str = "done",
    body: Any = None,
    created_by: int = 1,
    module: str = "materiality",
    digest: Any = DIGEST,
    failed_step: str | None = None,
    running: str | None = None,
) -> int:
    """실행 행 하나(created_at 은 부를 때마다 1분씩 뒤 — 차례를 박는다)와 단계 열·결과(done 이면 result@2 자리 +
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
        started_at=None if status == "queued" else at + timedelta(seconds=5),
        finished_at=at + timedelta(seconds=30) if status in ("done", "failed") else None,
        error_code="flow_failed" if status == "failed" else None,
        failed_step=failed_step,
    )
    run_row.for_company(company_id).filter(pk=made.pk).update(created_at=at)
    for position, name in enumerate(STEPS):
        step_status = "done" if status == "done" else "pending"
        if status == "processing":
            step_status = "done" if position < STEPS.index(running or "report_iro") else "pending"
        if name == running:  # processing 밖에 심으면 남은 running 행(목록은 processing 실행만 본다)
            step_status = "running"
        apps.get_model("runs", "RunStepRow").for_company(company_id).create(
            company_id=company_id, run_id=made.pk, name=name, position=position, status=step_status
        )
    if status == "done":
        rows = [{"schemaVersion": "materiality.result@2", "big": "본문"}] + ([digest] if digest is not None else [])
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
    return client.get("/api/materiality/runs", params)


def page_of(client: Client, **params: Any) -> dict[str, Any]:
    response = listed(client, **params)
    assert response.status_code == 200, response.content.decode()
    found: dict[str, Any] = response.json()
    PAGE.validate_python(found, strict=True)
    return found


def ids(found: dict[str, Any]) -> list[int]:
    return [row["id"] for row in found["results"]]


# ── 3-2-1 줄 칸 ──


def test_the_rows_are_my_company_materiality_runs_newest_first(client: Client, world: World) -> None:
    a, b = world.company_a, world.company_b
    user = me(client)
    done = seed(a, created_by=user)
    queued = seed(a, status="queued", created_by=user)
    failed = seed(a, status="failed", failed_step="impact", created_by=987_654)  # 모르는 사람
    seed(a, module="dataverify", body={"input": {"company": {"name": "가상기업"}}})
    seed(b)  # 남의 회사
    found = page_of(client)
    assert ids(found) == [failed, queued, done]
    assert (found["count"], found["isNext"]) == (3, False)
    assert {frozenset(row) for row in found["results"]} == {frozenset(ROW_FIELDS)}
    rows = {row["id"]: row for row in found["results"]}
    for row in found["results"]:
        assert (row["companyName"], row["industries"], row["topicCount"]) == ("가상물류", INDUSTRIES, 2)
        assert (row["dateRange"], row["latestEventMode"]) == ("2025-01-01~오늘까지", False)
        assert row["createdAt"].endswith("+09:00")
    assert rows[done]["status"] == "done" and rows[done]["finishedAt"].endswith("+09:00")
    assert rows[done]["startedAt"].endswith("+09:00") and rows[queued]["startedAt"] is None
    assert (rows[done]["impactRows"], rows[done]["pathwayRows"]) == (4, 3)
    assert rows[done]["createdBy"] == {"userId": user, "name": "김담당"}
    assert rows[failed]["createdBy"] == {"userId": 987_654, "name": "알 수 없는 사용자"}


def test_the_rows_carry_no_topic_names_descriptions_or_other_option_fields(client: Client, world: World) -> None:
    me(client)
    seed(world.company_a, body=options(marked()))
    response = listed(client)
    assert response.status_code == 200, response.content.decode()
    text = json.dumps(response.json(), ensure_ascii=False)
    words = (MARK, "가상토픽 하나", "가상토픽 둘", "가상 서브 가", "가상 설명", "subtopicsByTopic", "valueChain")
    for word in (*words, "geoScope", '"description"', '"topics"', '"input"', "big", "본문"):
        assert word not in text, word
    assert "가상물류" in text and "가상 산업 둘" in text  # 분모: 기업명·산업 이름은 싣는다


# ── 3-2-2 꼴 어긋난 옵션 ──

OPTION_FIELDS = ("companyName", "industries", "topicCount", "dateRange", "latestEventMode")


@pytest.mark.parametrize(
    ("change", "nulls"),
    [
        ({"industries": [{"standard": 1}]}, {"industries"}),
        ({"industries": [INDUSTRIES[0], {"standard": "SASB"}]}, {"industries"}),
        ({"industries": [INDUSTRIES[0], "가상 글자"]}, {"industries"}),
        ({"industries": "가상 글자"}, {"industries"}),
        ({"topics": "가상 글자"}, {"topicCount"}),
        ({"company": {"name": 1}}, {"companyName"}),
        ({"company": "가상 글자"}, {"companyName"}),
        ({"dateRange": 2025}, {"dateRange"}),
        ({"latestEventMode": "false"}, {"latestEventMode"}),
        ({"latestEventMode": 0}, {"latestEventMode"}),
    ],
    ids=[
        "industry-standard-number",
        "industry-without-name",
        "industry-text",
        "industries-text",
        "topics-text",
        "company-name-number",
        "company-text",
        "date-range-number",
        "latest-text",
        "latest-zero",
    ],
)
def test_a_value_out_of_shape_is_null_and_the_row_stays(
    client: Client, world: World, change: dict[str, Any], nulls: set[str]
) -> None:
    me(client)
    good = seed(world.company_a)
    bad = seed(world.company_a, body=options({**received2(), **change}))
    found = page_of(client)
    assert ids(found) == [bad, good]
    rows = {row["id"]: row for row in found["results"]}
    for field in OPTION_FIELDS:
        assert (rows[bad][field] is None) == (field in nulls), field
        assert rows[good][field] is not None, field
    assert (rows[bad]["impactRows"], rows[bad]["pathwayRows"]) == (4, 3)  # 요약은 옵션과 따로


@pytest.mark.parametrize("body", [{"input": "가상 글자"}, {}, {"input": None}], ids=["text", "no-input", "null"])
def test_options_without_an_input_object_null_every_option_field(
    client: Client, world: World, body: dict[str, Any]
) -> None:
    me(client)
    seed(world.company_a, body=body)
    (row,) = page_of(client)["results"]
    assert [row[f] for f in OPTION_FIELDS] == [None] * len(OPTION_FIELDS)


def test_an_empty_industry_list_is_an_empty_list(client: Client, world: World) -> None:
    me(client)
    seed(world.company_a, body=options({**received2(), "industries": []}))
    (row,) = page_of(client)["results"]
    assert row["industries"] == []


# ── 3-2-3 상태별 ──


def test_each_status_fills_its_own_fields(client: Client, world: World) -> None:
    a = world.company_a
    me(client)
    queued = seed(a, status="queued")
    processing = seed(a, status="processing", running="impact")
    waiting = seed(a, status="processing", running=None)  # 단계 사이(running 없음)
    failed = seed(a, status="failed", failed_step="financial")
    done = seed(a)
    old = seed(a, digest=None)  # 요약을 남기기 전의 옛 실행(★H — IR3c 앞)
    odd = seed(a, digest={**DIGEST, "impactRows": "4"})  # 꼴 밖 요약
    unrun = seed(a, digest={**DIGEST, "impactRows": None, "pathwayRows": None})  # part2 not_run
    rows = {row["id"]: row for row in page_of(client)["results"]}
    picked = ("currentStep", "failedStep", "impactRows", "pathwayRows")
    assert [rows[queued][k] for k in picked] == [None, None, None, None]
    assert [rows[processing][k] for k in picked] == ["impact", None, None, None]
    assert [rows[waiting][k] for k in picked] == [None, None, None, None]
    assert [rows[failed][k] for k in picked] == [None, "financial", None, None]
    assert [rows[done][k] for k in picked] == [None, None, 4, 3]
    assert [rows[old][k] for k in picked] == [None, None, None, None]
    assert [rows[odd][k] for k in picked] == [None, None, None, None]
    assert [rows[unrun][k] for k in picked] == [None, None, None, None]
    assert rows[queued]["finishedAt"] is None and rows[failed]["finishedAt"] is not None


def test_a_failed_step_on_a_done_run_and_a_running_step_on_a_failed_run_are_not_shown(
    client: Client, world: World
) -> None:
    a = world.company_a
    me(client)
    done = seed(a, failed_step="impact", running="report_iro")
    failed = seed(a, status="failed", failed_step="pathway", running="pathway")
    rows = {row["id"]: row for row in page_of(client)["results"]}
    assert (rows[done]["failedStep"], rows[done]["currentStep"]) == (None, None)
    assert (rows[failed]["failedStep"], rows[failed]["currentStep"]) == ("pathway", None)


def test_a_digest_on_a_failed_run_is_not_shown(client: Client, world: World) -> None:
    a = world.company_a
    me(client)
    failed = seed(a, status="failed", failed_step="report_iro")
    apps.get_model("runs", "RunResultRow").for_company(a).create(
        company_id=a, run_id=failed, position=0, schema_version=DIGEST_SHAPE, body=DIGEST
    )
    (row,) = page_of(client)["results"]
    assert (row["impactRows"], row["pathwayRows"]) == (None, None)


# ── 3-2-4 거름 ──


def test_the_status_filter_takes_several_values(client: Client, world: World) -> None:
    a = world.company_a
    me(client)
    queued, processing = seed(a, status="queued"), seed(a, status="processing", running="regulation")
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
    response = client.get("/api/materiality/runs" + query)
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
        seed(a, status="processing", running="impact")
        seed(a)
        seed(a, status="failed")
    # 실행 쪽 2(줄·count) · 단계 1 · 요약 1 · 이름 1 + 세이브포인트 2
    with django_assert_num_queries(7):  # DVI1 +2: 세이브포인트
        found = run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=0)
    assert len(found["results"]) == 9
    # 쪽이 비면 단계·요약·이름 0 + 세이브포인트 2
    with django_assert_num_queries(4):  # DVI1 +2: 세이브포인트
        run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=40)
    # processing·done 이 없으면 단계·요약 0(이름 1) + 세이브포인트 2
    with django_assert_num_queries(5):  # DVI1 +2: 세이브포인트
        run_actions.runs(company_id=a, user_id=1, statuses=["failed"], mine=False, limit=20, offset=0)


def http_queries(client: Client) -> int:
    with CaptureQueriesContext(connection) as captured:
        assert listed(client).status_code == 200
    return len(captured)


def test_the_http_query_count_does_not_grow_with_the_rows(client: Client, world: World) -> None:
    a = world.company_a
    me(client)
    seed(a, status="processing", running="impact")
    seed(a)
    few = http_queries(client)
    for _ in range(9):
        seed(a, status="processing", running="pathway", created_by=2)
        seed(a, created_by=3)
    many = http_queries(client)
    assert len(page_of(client)["results"]) == 20
    assert few == many


# ── ★I 끝까지 돈 실행: 토픽 수 = 결과 scope.topicCount, 두 수 = 최종 엑셀 2-1·2-2 데이터 줄 수 ──


def all_done(mock: Any) -> None:
    support.script_part2(mock)


def impact_fails_once(mock: Any) -> None:
    """둘째 서브토픽의 영향 답을 읽지 못함 → 그 impact failed(영향 줄 하나 빠짐). 재무·Pathway 는 그대로."""
    for n, name in enumerate(support.SUBTOPICS2):
        mock.enqueue_text("가상 — JSON 아님" if n == 1 else support.impact_answer(name), support.USAGE)
    for name in support.SUBTOPICS2:
        mock.enqueue_text(support.financial_answer(name), support.USAGE)
    for name in support.SUBTOPICS2:
        mock.enqueue_text(support.pathway_answer(name), support.USAGE)


def financial_fails_once(mock: Any) -> None:
    """첫 서브토픽의 재무 답을 읽지 못함 → 그 자리 Pathway 는 부르지 않음(not_run — 경로 줄 둘 빠짐)."""
    for name in support.SUBTOPICS2:
        mock.enqueue_text(support.impact_answer(name), support.USAGE)
    for n, name in enumerate(support.SUBTOPICS2):
        mock.enqueue_text("가상 — JSON 아님" if n == 0 else support.financial_answer(name), support.USAGE)
    for name in support.SUBTOPICS2[1:]:
        mock.enqueue_text(support.pathway_answer(name), support.USAGE)


def sheet_rows(sheet: Worksheet) -> int:
    return sum(1 for r in range(6, sheet.max_row + 1) if sheet[f"D{r}"].value is not None)


@pytest.mark.parametrize(
    ("given", "answers", "counts"),
    [
        (received2, all_done, (3, 6)),
        (lambda: received2(value_chain=False), impact_fails_once, (2, 6)),
        (
            lambda: {**received2(), "industries": copy.deepcopy(received2()["industries"][:1])},
            financial_fails_once,
            (3, 4),
        ),
    ],
    ids=["all-done", "impact-failed", "financial-failed"],
)
def test_a_finished_run_carries_the_result_topic_count_and_the_workbook_row_counts(
    client: Client,
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    given: Callable[[], dict[str, Any]],
    answers: Callable[[Any], None],
    counts: tuple[int, int],
) -> None:
    received = given()
    scripted(monkeypatch, world)
    support.script_part1_dated(world.mock, received)
    answers(world.mock)
    run_id = new_run(client, options(received))
    execute(world, run_id)
    assert run_of(world, run_id).status == "done" and world.mock.pending == 0
    (row,) = page_of(client)["results"]
    assert row["id"] == run_id and row["status"] == "done"
    assert row["topicCount"] == result_body(world, run_id)["scope"]["topicCount"] == len(received["topics"])
    book = load_workbook(io.BytesIO(stored(world, run_id, step="report_iro", name=final_xlsx.FILENAME)))
    soc = cast("Worksheet", book[final_xlsx.SOC_SHEET])
    fin = cast("Worksheet", book[final_xlsx.FIN_SHEET])
    assert (row["impactRows"], row["pathwayRows"]) == (sheet_rows(soc), sheet_rows(fin)) == counts
    assert row["industries"] == [
        {"standard": i["standard"], "industryName": i["industryName"]} for i in received["industries"]
    ]


# ── IRS2 444: 목록이 options 본문 대신 투영을 읽어도 옵션 다섯 칸·startedAt 이 BASE 셈과 같다(HD1 347 ① 꼴) ──


def _changed(**changes: Any) -> dict[str, Any]:
    return options({**received2(), **changes})


def _without(key: str) -> dict[str, Any]:
    found = received2()
    found.pop(key)
    return options(found)


def _nul_topic() -> dict[str, Any]:
    found = received2()
    found["topics"][0]["description"] = "가상\x00설명"
    return options(found)


BRIEF_CASES: dict[str, dict[str, Any]] = {
    "good": options(),
    "latest_true": options(received2(latest=True)),
    "no_input": {},
    "input_text": {"input": "가상 글자"},
    "input_null": {"input": None},
    "input_list": {"input": ["가상"]},
    "company_text": _changed(company="가상 글자"),
    "company_null": _changed(company=None),
    "no_company": _without("company"),
    "name_number": _changed(company={"name": 1}),
    "no_name": _changed(company={}),
    "industries_empty": _changed(industries=[]),
    "industries_text": _changed(industries="가상 글자"),
    "industries_null": _changed(industries=None),
    "no_industries": _without("industries"),
    "industry_bad": _changed(industries=[INDUSTRIES[0], {"standard": 1, "industryName": "가상"}]),
    "topics_text": _changed(topics="가상 글자"),
    "topics_null": _changed(topics=None),
    "topics_empty": _changed(topics=[]),
    "no_topics": _without("topics"),
    "date_number": _changed(dateRange=2025),
    "date_null": _changed(dateRange=None),
    "latest_zero": _changed(latestEventMode=0),
    "latest_text": _changed(latestEventMode="false"),
    "latest_null": _changed(latestEventMode=None),
    "nul_in_topic": _nul_topic(),
    "nul_in_name": _changed(company={"name": "가상\x00기업"}),
    "backslash_u0000_text": _changed(company={"name": "가상\\u0000기업"}),  # 글자 그대로(진짜 NUL 아님)
}
BRIEF_FIELDS = ("startedAt", *OPTION_FIELDS)


def base_fields(company_id: int, run_id: int) -> dict[str, object]:
    """BASE 의 셈(옵션 본문 → _input → 다섯 함수, started_at 은 실행 행 — 그 함수들은 IRS2 가 0줄)."""
    from esgapi.core.schemas import to_seoul_iso
    from esgapi.runs.service.selectors.runs import find_run

    found = find_run(company_id=company_id, run_id=run_id)
    assert found is not None
    given = run_actions._input(found.options)  # pyright: ignore[reportPrivateUsage]
    values = (
        None if found.started_at is None else to_seoul_iso(found.started_at),
        run_actions._company(given),  # pyright: ignore[reportPrivateUsage]
        run_actions._industries(given),  # pyright: ignore[reportPrivateUsage]
        run_actions._topic_count(given),  # pyright: ignore[reportPrivateUsage]
        run_actions._text(given.get("dateRange")),  # pyright: ignore[reportPrivateUsage]
        run_actions._latest(given),  # pyright: ignore[reportPrivateUsage]
    )
    return dict(zip(BRIEF_FIELDS, values, strict=True))


def test_the_list_never_selects_the_whole_options_outside_the_nul_branch(world: World) -> None:
    """T1: 첫 쿼리 SELECT 안 "run_runs"."options" 뒤는 늘 -> #> — 통째는 \\u0000 표시 CASE 갈래(THEN) 하나뿐."""
    import re

    a = world.company_a
    seed(a)
    with CaptureQueriesContext(connection) as captured:
        found = run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=0)
    assert captured.captured_queries[0]["sql"].startswith("SAVEPOINT")  # DVI1: 줄 쿼리 앞
    selected = captured.captured_queries[1]["sql"].split(" FROM ")[0]  # DVI1 +2: 세이브포인트
    reads = re.findall(r'(\S+\s+)?"run_runs"\."options"(\s*\S+)', selected)
    assert reads  # 분모: 옵션 경로를 읽었다
    whole = [(before, after) for before, after in reads if not after.strip().startswith(("->", "#>"))]
    assert [before.strip() for before, _after in whole] == ["THEN"], whole
    (row,) = found["results"]
    assert (row["companyName"], row["industries"], row["topicCount"]) == ("가상물류", INDUSTRIES, 2)


@pytest.mark.parametrize("case", list(BRIEF_CASES))
def test_the_option_fields_equal_the_base_count_for_every_shape(world: World, case: str) -> None:
    """T2: 꼴마다 투영 셈 = BASE 셈(옵션 다섯 칸·startedAt)."""
    a = world.company_a
    run_id = seed(a, body=copy.deepcopy(BRIEF_CASES[case]))
    found = run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=0)
    (row,) = [r for r in found["results"] if r["id"] == run_id]
    assert {field: row[field] for field in BRIEF_FIELDS} == base_fields(a, run_id)


def test_the_good_input_fills_every_option_field(world: World) -> None:
    """T2 의 분모: 좋은 입력은 다섯 칸이 다 차고 startedAt 도 있다(BASE 와 같음이 null 끼리의 같음이 아니다)."""
    a = world.company_a
    run_id = seed(a, body=options(received2(latest=True)))
    (row,) = run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=0)["results"]
    assert row["id"] == run_id
    assert (row["companyName"], row["industries"], row["topicCount"]) == ("가상물류", INDUSTRIES, 2)
    assert (row["dateRange"], row["latestEventMode"]) == ("2025-01-01~오늘까지", True)
    assert row["startedAt"] is not None and row["startedAt"].endswith("+09:00")


def test_an_old_unwrapped_options_row_counts_the_same(world: World) -> None:
    """T3: 감싸지 않은 옛 options(OrderedJSONField 가 그대로 읽는 갈래)도 BASE 셈과 같다."""
    from django.db.models import JSONField, Value

    a = world.company_a
    run_id = seed(a)
    body = _changed(company={"name": "가상옛기업"})
    run_row = apps.get_model("runs", "RunRow")
    run_row.for_company(a).filter(pk=run_id).update(options=Value(body, output_field=JSONField()))
    (row,) = run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=0)["results"]
    assert {field: row[field] for field in BRIEF_FIELDS} == base_fields(a, run_id)
    assert (row["companyName"], row["topicCount"]) == ("가상옛기업", 2)


def test_every_shape_on_one_page_is_200_and_reads_at_most_five_queries(
    client: Client, world: World, django_assert_max_num_queries: Any
) -> None:
    """\\u0000 이 든 줄이 있어도 쪽이 500 이 아니고 칸이 BASE 와 같고, 쿼리는 그대로 많아야 5."""
    me(client)
    a = world.company_a
    made = {case: seed(a, body=copy.deepcopy(body)) for case, body in BRIEF_CASES.items()}
    rows = {row["id"]: row for offset in (0, 20) for row in page_of(client, limit=20, offset=offset)["results"]}
    assert set(rows) == set(made.values())
    for case, run_id in made.items():
        assert {field: rows[run_id][field] for field in BRIEF_FIELDS} == base_fields(a, run_id), case
    with django_assert_max_num_queries(7):  # DVI1 +2: 세이브포인트
        run_actions.runs(company_id=a, user_id=1, statuses=None, mine=False, limit=20, offset=0)
