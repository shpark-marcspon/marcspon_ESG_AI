# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""만들기(POST /runs)의 본문 launchKey 를 진짜 DB 로 잰다(밴드 LK1 — MARC-ISSUE-303 ①, 발주서 §2-9 업무 1~5). 업무 층.

    1 launchKey 둘로 셋 → 행 셋에 그대로, 응답은 {id,status}(LK1 앞 꼴). 없음·null → NULL
    2 틀린 꼴(대문자·"1"·빈 글자·37자) → 422 VALIDATION_ERROR, 행 0
    3 launchKey 없음 → LK1 앞(BASE 151e394 에서 뜬 값 — LK1.out/capture/base)과 응답 바이트·행 칸·감사·쪽지·쿼리 수가
      같다(새 칸 NULL)
    4 다시 하기(303 닫는 조건): 묶음 k 의 실패를 k 로 이어 돌기 → 409 LAUNCH_KEY_REUSED·쓰기 0, 새 열쇠면 201 이고 원
      묶음 수 그대로·새 실행은 1/1. launchKey 없는 이어 돌기는 201·NULL(분모)
    5 Idempotency-Key 와 함께(Q5): 같은 머리 열쇠·같은 launchKey → 같은 실행 201, 다른 launchKey·없음→있음 → 409
운영 관리자의 작업 회사(업무 6)는 test_runs_operator.py, run-logs 의 묶음 셈(업무 7~11)은 user 의
test_run_logs_launch.py. 앱 역할(유일 아님·회사 둘)은 보안 층 tests/security/test_runs.py ⓙ.
흐름·끼움·저장소는 test_runs.py 의 world(가짜)를 그대로 쓴다.
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.models import AuditEventRow
from esgapi.runs.models import RunRow, RunStepRow
from esgapi.runs.service.selectors import operator as operator_selectors
from esgapi.runs.tests.service.apis.test_runs import World, document, error_of, failed_run, resume_body, world
from esgapi.runs.tests.service.apis.test_runs_idempotency import BASE_AUDIT, BASE_CONTENT, BASE_HEADERS, BASE_ROW
from tests.support.http import login

pytestmark = pytest.mark.django_db

K = "1a2b3c4d-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID — 같이 시작 묶음 하나
K2 = "5e6f7a8b-9999-4aaa-8bbb-cccccccccccc"
IDEM = "0b0e6c1e-1111-4222-8333-444455556666"  # Idempotency-Key

__all__ = ["world"]  # 고정 장치(test_runs.py 의 것)


def create(client: Client, body: dict[str, Any], *, key: str | None = None) -> Any:
    headers = {} if key is None else {"Idempotency-Key": key}
    return client.post("/api/runs", data=body, content_type="application/json", headers=headers)


def counts() -> tuple[int, int, int]:
    """(실행 행, 단계 행, 감사 run 줄) — 회사 둘 다."""
    return (
        RunRow.unscoped.count(),
        RunStepRow.unscoped.count(),
        AuditEventRow.unscoped.filter(action="run").count(),
    )


def launch_of(company_id: int) -> dict[int, tuple[object, ...]]:
    """run-logs 의 selector 가 낸 (열쇠, 첫 id, 차례, 수, 앞 실행) — 고른 회사의 쪽 하나(100줄)."""
    page = operator_selectors.operator_run_page(
        actor_kind="admin", company_id=company_id, module=None, status=None, date_from=None, date_to=None, q=None,
        limit=100, offset=0,
    )  # fmt: skip
    assert isinstance(page, operator_selectors.OperatorRunPage)
    return {
        run.id: (run.launch_key, run.launch_first_run_id, run.launch_index, run.launch_size, run.resumed_from_run_id)
        for run in page.runs
    }


# ── 1 적힘 ────────────────────────────────────────────────────────────


def test_launch_keys_are_written_as_given_and_the_response_keeps_its_shape(client: Client, world: World) -> None:
    login(client)
    doc = document(world.company_a)
    made = [create(client, {"module": "probe", "documentId": doc, "launchKey": k}) for k in (K, K, K2)]
    assert [r.status_code for r in made] == [201, 201, 201]
    assert all(set(r.json()) == {"id", "status"} for r in made)
    ids = [r.json()["id"] for r in made]
    assert list(RunRow.unscoped.filter(pk__in=ids).order_by("id").values_list("launch_key", flat=True)) == [K, K, K2]
    omitted = create(client, {"module": "probe", "documentId": doc})
    null = create(client, {"module": "probe", "documentId": doc, "launchKey": None})
    assert (omitted.status_code, null.status_code) == (201, 201)
    plain = RunRow.unscoped.filter(pk__in=[omitted.json()["id"], null.json()["id"]])
    assert list(plain.values_list("launch_key", flat=True)) == [None, None]
    assert counts() == (5, 15, 5)


# ── 2 틀린 꼴 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "launch_key",
    [
        "1A2B3C4D-1111-4222-8333-444455556666",  # 대문자
        "1",
        "",
        "1a2b3c4d-1111-4222-8333-4444556666777",  # 37자
        7,
    ],
)
def test_a_malformed_launch_key_is_422_and_writes_nothing(client: Client, world: World, launch_key: object) -> None:
    login(client)
    doc = document(world.company_a)
    response = create(client, {"module": "probe", "documentId": doc, "launchKey": launch_key})
    assert error_of(response) == (422, "VALIDATION_ERROR")
    assert counts() == (0, 0, 0)
    assert world.sent == []
    assert create(client, {"module": "probe", "documentId": doc, "launchKey": K}).status_code == 201  # 분모


# ── 3 launchKey 없음 = BASE ───────────────────────────────────────────

SKIPPED = ("id", "created_at", "updated_at", "company_id", "document_id", "created_by_user_id")
# BASE 151e394 의 같은 요청 쿼리 수(LK1.out/capture/base/keyless-post.json — IK1 의 KEYLESS_QUERIES 와 같은 값)
BASE_QUERIES = 11


def test_without_a_launch_key_the_post_is_byte_for_byte_like_base(
    client: Client, world: World, django_capture_on_commit_callbacks: Any
) -> None:
    login(client)
    doc = document(world.company_a)
    for _ in range(2):
        with django_capture_on_commit_callbacks(execute=True) as callbacks, CaptureQueriesContext(connection) as seen:
            response = create(client, {"module": "probe", "documentId": doc, "options": {"b": 1, "a": "가"}})
        run_id = response.json()["id"]
        assert response.status_code == 201
        assert response.content.decode().replace(str(run_id), "<ID>") == BASE_CONTENT
        assert sorted((k, v) for k, v in response.headers.items() if k.lower() not in ("date", "x-request-id")) == (
            BASE_HEADERS
        )
        row = RunRow.for_company(world.company_a).filter(pk=run_id).values().get()
        assert (row.pop("idempotency_key"), row.pop("idempotency_sha256"), row.pop("launch_key")) == (None,) * 3
        assert row.pop("parked_at") is None  # RM1b 0006: 만들 때 NULL(주차 아님)
        assert {k: v for k, v in row.items() if k not in SKIPPED} == BASE_ROW
        assert RunStepRow.for_company(world.company_a).filter(run_id=run_id).count() == 3
        assert (len(callbacks), len(seen.captured_queries)) == (1, BASE_QUERIES)
    lines = AuditEventRow.unscoped.filter(action="run").order_by("id")
    assert [(a.actor_kind, a.event, a.result, a.target_kind, a.target_label) for a in lines] == [BASE_AUDIT] * 2
    assert (len(world.sent), RunRow.unscoped.count()) == (2, 2)


def test_a_launch_key_costs_no_extra_query_on_create(client: Client, world: World) -> None:
    """launchKey 는 INSERT 의 칸 하나다 — 만들기 쿼리 수는 열쇠 없는 것과 같다."""
    login(client)
    doc = document(world.company_a)
    with CaptureQueriesContext(connection) as seen:
        assert create(client, {"module": "probe", "documentId": doc, "launchKey": K}).status_code == 201
    assert len(seen.captured_queries) == BASE_QUERIES


# ── 4 다시 하기 ───────────────────────────────────────────────────────


def test_a_retry_cannot_join_the_original_launch_and_a_new_key_keeps_it_apart(
    client: Client, world: World, django_capture_on_commit_callbacks: Any
) -> None:
    """303 닫는 조건: 같이 시작한 셋(K) 중 실패한 것을 이어 돌리며 K 를 실으면 409 LAUNCH_KEY_REUSED·쓰기 0. 새 열쇠
    K2 면 201 — 원 묶음은 여전히 3, 새 실행은 1/1·앞 실행 = 실패한 것."""
    login(client)
    doc = document(world.company_a)
    started = [create(client, {"module": "probe", "documentId": doc, "launchKey": K}) for _ in range(2)]
    me = RunRow.unscoped.get(pk=started[0].json()["id"]).created_by_user_id
    failed = failed_run(world, doc)  # 셋째 파트가 실패했다(같은 사람·같은 묶음)
    RunRow.unscoped.filter(pk=failed).update(launch_key=K, created_by_user_id=me)
    group = [r.json()["id"] for r in started] + [failed]
    before = (counts(), list(RunRow.unscoped.order_by("id").values()), len(world.sent))
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        refused = create(client, resume_body(doc, failed, launchKey=K))
    assert error_of(refused) == (409, "LAUNCH_KEY_REUSED")
    assert refused.json()["error"]["message"] == "다시 하기는 새 launchKey 로 — 앞 실행의 묶음에 넣을 수 없다"
    assert (counts(), list(RunRow.unscoped.order_by("id").values()), len(world.sent)) == before
    assert len(callbacks) == 0
    retried = create(client, resume_body(doc, failed, launchKey=K2))
    assert retried.status_code == 201, retried.content.decode()
    child = retried.json()["id"]
    seen = launch_of(world.company_a)
    assert [seen[i] for i in group] == [(K, group[0], n, 3, None) for n in (1, 2, 3)]  # 원 묶음 그대로 3
    assert seen[child] == (K2, child, 1, 1, failed)
    # 분모: launchKey 없이 다른 실패 실행을 이어 돌리면 201·열쇠 NULL(같은 실패는 이미 이어 받아 RESUME_ALREADY)
    other = failed_run(world, doc)
    bare = create(client, resume_body(doc, other))
    assert bare.status_code == 201, bare.content.decode()
    assert launch_of(world.company_a)[bare.json()["id"]] == (None, None, None, None, other)


def test_a_retry_with_a_key_other_than_the_previous_runs_passes(client: Client, world: World) -> None:
    """앞 실행의 열쇠와 다르면(앞 실행이 열쇠 없이 만들어졌어도) 이어 돌기는 지난다 — 검사는 「앞과 같은 열쇠」 하나."""
    login(client)
    doc = document(world.company_a)
    failed = failed_run(world, doc)  # 열쇠 없음
    response = create(client, resume_body(doc, failed, launchKey=K))
    assert response.status_code == 201, response.content.decode()
    assert RunRow.unscoped.get(pk=response.json()["id"]).launch_key == K


# ── 5 Idempotency-Key 와 함께 ─────────────────────────────────────────


def test_idempotency_counts_the_launch_key_in_the_body(client: Client, world: World) -> None:
    login(client)
    doc = document(world.company_a)
    body = {"module": "probe", "documentId": doc, "launchKey": K}
    first = create(client, body, key=IDEM)
    again = create(client, body, key=IDEM)
    assert (first.status_code, again.status_code, again.json()["id"]) == (201, 201, first.json()["id"])
    before = counts()
    assert error_of(create(client, {**body, "launchKey": K2}, key=IDEM)) == (409, "IDEMPOTENCY_KEY_REUSED")
    plain = {"module": "probe", "documentId": doc}
    assert error_of(create(client, plain, key=IDEM)) == (409, "IDEMPOTENCY_KEY_REUSED")  # 있음 → 없음
    assert counts() == before
    other = "2c3d4e5f-1111-4222-8333-444455556666"
    assert create(client, plain, key=other).status_code == 201  # 없음 → 있음
    assert error_of(create(client, body, key=other)) == (409, "IDEMPOTENCY_KEY_REUSED")
