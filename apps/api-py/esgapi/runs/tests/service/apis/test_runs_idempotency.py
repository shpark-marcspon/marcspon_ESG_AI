# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""만들기(POST /runs)의 Idempotency-Key 를 진짜 DB 로 잰다(밴드 IK1 — MARC-ISSUE-225, 발주서 §2-7 업무 1~9). 업무 층.

    1 같은 열쇠·같은 본문 두 번 → 둘 다 201·같은 id, 실행 행·단계 한 벌·쪽지 1·감사 1, 둘째 status 는 지금 값.
      다시 보냄은 검사를 다시 돌지 않는다(끼움이 바뀌어도 201 — 열쇠 찾기가 첫 문장)
    2 같은 열쇠·다른 본문(옵션 값·옵션 열쇠 차례·documentId·module) → 409 IDEMPOTENCY_KEY_REUSED, 쓰기 0
    3 열쇠 없음 → IK1 앞(BASE 4e28a54 에서 뜬 값)과 응답 바이트·행 칸·감사·쪽지가 같다(새 칸 둘 NULL)
    4 틀린 꼴 열쇠 → 422 VALIDATION_ERROR, 행 0
    5 거절 뒤 같은 열쇠 → 고쳐 보내면 새로 판정(행 0 → 1)
    6 이어 돌기: 같은 열쇠로 두 번 → 같은 자식 201(열쇠 없으면 둘째 409 RESUME_ALREADY — 분모)
    7 문서 없는 흐름도 1·2 그대로
    8 범위: 같은 회사 다른 사람의 같은 열쇠 → 따로(운영 관리자의 작업 회사 범위는 test_runs_operator.py)
    9 쿼리 수: 다시 보냄 = 세션·권한 + 열쇠 찾기 하나

흐름·끼움·저장소는 test_runs.py 의 world(가짜)를 그대로 쓴다. 동시 두 요청은 service/actions/test_create_run_race.py.
★ 무효 조건: 연결이 하나다(주인 역할, 테스트마다 되돌린다). 앱 역할의 유일·짝 CHECK 는 보안 층
  tests/security/test_runs.py.
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

from collections.abc import Mapping
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.flows.binding import BindingRegistry, RunOptionsRejected
from esgapi.core.models import AuditEventRow
from esgapi.runs.models import RunRow, RunStepRow
from esgapi.runs.service.actions import runs as actions
from esgapi.runs.tests.service.apis.test_runs import (
    PROBE,
    PROBE_TWO,
    BareBinding,
    ProbeBinding,
    World,
    bare,
    bare_body,
    document,
    error_of,
    failed_run,
    resume_body,
    world,
)
from tests.support.http import login

pytestmark = pytest.mark.django_db

KEY = "0b0e6c1e-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID
OTHER_KEY = "9f8e7d6c-5b4a-4321-8fed-cba987654321"

__all__ = ["bare", "world"]  # 고정 장치(test_runs.py 의 것)


def create(client: Client, body: dict[str, Any], key: str | None = KEY) -> Any:
    headers = {} if key is None else {"Idempotency-Key": key}
    return client.post("/api/runs", data=body, content_type="application/json", headers=headers)


def counts() -> tuple[int, int, int]:
    """(실행 행, 단계 행, 감사 run 줄) — 회사 둘 다."""
    return (
        RunRow.unscoped.count(),
        RunStepRow.unscoped.count(),
        AuditEventRow.unscoped.filter(action="run").count(),
    )


# ── 1 같은 열쇠·같은 본문 ──────────────────────────────────────────────


def test_the_same_key_and_body_twice_is_one_run_one_message_one_audit_line(
    client: Client, world: World, django_capture_on_commit_callbacks: Any
) -> None:
    login(client)
    doc = document(world.company_a)
    body = {"module": "probe", "documentId": doc, "options": {"pages": "1-3"}}
    with django_capture_on_commit_callbacks(execute=True) as first_callbacks:
        first = create(client, body)
    assert first.status_code == 201, first.content.decode()
    run_id = first.json()["id"]
    assert counts() == (1, 3, 1)
    with django_capture_on_commit_callbacks(execute=True) as second_callbacks:
        second = create(client, body)
    assert second.status_code == 201
    assert second.json() == first.json() == {"id": run_id, "status": "queued"}
    assert counts() == (1, 3, 1)  # 행·단계·감사 그대로
    assert (len(first_callbacks), len(second_callbacks)) == (1, 0)
    assert world.sent == [{"company_id": world.company_a, "run_id": run_id}]
    row = RunRow.for_company(world.company_a).get(pk=run_id)
    assert row.idempotency_key == KEY
    assert row.idempotency_sha256 is not None and len(row.idempotency_sha256) == 64
    # 둘째 응답의 status 는 지금 값(첫 응답 바이트 그대로가 아니다 — Q10)
    RunRow.for_company(world.company_a).filter(pk=run_id).update(status="processing")
    third = create(client, body)
    assert (third.status_code, third.json()) == (201, {"id": run_id, "status": "processing"})
    assert counts() == (1, 3, 1)


def test_a_replay_is_found_before_the_checks_so_a_changed_binding_does_not_refuse_it(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Q8: 열쇠 찾기가 첫 문장이다 — 첫 요청 뒤 끼움이 그 옵션을 거절하게 바뀌어도 다시 보냄은 앞 실행 201(검사를 다시
    돌지 않는다). 분모: 열쇠 없이 보내면 지금 끼움이 400 으로 거절한다."""
    login(client)
    body = {"module": "probe", "documentId": document(world.company_a), "options": {"pages": "1-3"}}
    first = create(client, body)
    assert first.status_code == 201
    strict = BindingRegistry()
    strict.register(PROBE.id, Refusing())
    monkeypatch.setattr(actions, "BINDINGS", strict)
    again = create(client, body)
    assert (again.status_code, again.json()["id"]) == (201, first.json()["id"])
    assert error_of(create(client, body, key=None)) == (400, "INVALID_OPTIONS")
    assert counts() == (1, 3, 1)


class Refusing(ProbeBinding):
    def check_options(self, options: Mapping[str, object]) -> None:
        raise RunOptionsRejected("지어낸 거절: 이 끼움은 이제 쪽 범위를 받지 않는다")


# ── 2 같은 열쇠·다른 본문 ──────────────────────────────────────────────


@pytest.mark.parametrize("change", ["option_value", "option_order", "document", "module", "flow"])
def test_the_same_key_with_another_body_is_409_and_writes_nothing(
    client: Client, world: World, django_capture_on_commit_callbacks: Any, change: str
) -> None:
    login(client)
    doc = document(world.company_a)
    body: dict[str, Any] = {"module": "probe", "documentId": doc, "options": {"pages": "1-3", "lang": "ko"}}
    assert create(client, body).status_code == 201
    before = (counts(), list(RunRow.unscoped.values()))
    sent = list(world.sent)
    changed: dict[str, dict[str, Any]] = {
        "option_value": {**body, "options": {"pages": "1-4", "lang": "ko"}},
        "option_order": {**body, "options": {"lang": "ko", "pages": "1-3"}},  # 같은 값·다른 차례 = 다른 요청(Q4)
        "document": {**body, "documentId": document(world.company_a, name="다른 보고서.pdf")},
        "module": {**body, "module": "other"},
        "flow": {**body, "flowId": PROBE_TWO.id},
    }
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = create(client, changed[change])
    assert error_of(response) == (409, "IDEMPOTENCY_KEY_REUSED")
    assert response.json()["error"]["message"] == "같은 Idempotency-Key 로 다른 요청을 보냈다"
    assert (counts(), list(RunRow.unscoped.values())) == before
    assert (len(callbacks), world.sent) == (0, sent)
    # 분모: 같은 바뀐 본문을 다른 열쇠로 보내면 만들어진다(module "other" 는 그 모듈에 흐름이 없어 422)
    expected = 422 if change == "module" else 201
    assert create(client, changed[change], key=OTHER_KEY).status_code == expected


def test_flow_id_null_and_omitted_are_the_same_request(client: Client, world: World) -> None:
    login(client)
    doc = document(world.company_a)
    first = create(client, {"module": "probe", "documentId": doc})
    second = create(client, {"module": "probe", "documentId": doc, "flowId": None, "options": {}})
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] == second.json()["id"]
    assert counts() == (1, 3, 1)


# ── 3 열쇠 없음 = BASE ────────────────────────────────────────────────

# BASE 4e28a54 에서 같은 시험 몸으로 뜬 값(IK1.out/probe/keyless-base.json — 보고 §BASE 대조): id 를 뺀 응답 바이트,
# 머리(Date·X-Request-ID 제외), 실행 행의 칸(id·시각·회사·문서·사람 제외), 단계 수, 감사 줄, 쪽지
BASE_CONTENT = '{"id": <ID>, "status": "queued"}'
BASE_HEADERS = [("Content-Type", "application/json; charset=utf-8")]
BASE_ROW: dict[str, object] = {
    "module": "probe",
    "flow_id": "probe.three@1",
    "options": {"b": 1, "a": "가"},
    "versions": {"flow": "probe.three@1", "terms": "probe-terms@2"},
    "purpose": "service",
    "status": "queued",
    "attempts": 0,
    "stalled_attempts": 0,
    "progress_attempt": None,
    "lease_expires_at": None,
    "started_at": None,
    "finished_at": None,
    "failed_step": None,
    "error_code": None,
    "error_message": None,
    "resumed_from_run_id": None,
}
BASE_AUDIT = ("service", "run_created", "success", "run", "지은 보고서.pdf")
SKIPPED = ("id", "created_at", "updated_at", "company_id", "document_id", "created_by_user_id")


def test_without_a_key_two_posts_are_two_runs_byte_for_byte_like_base(
    client: Client, world: World, django_capture_on_commit_callbacks: Any
) -> None:
    login(client)
    doc = document(world.company_a)
    for _ in range(2):
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = create(client, {"module": "probe", "documentId": doc, "options": {"b": 1, "a": "가"}}, key=None)
        run_id = response.json()["id"]
        assert response.status_code == 201
        assert response.content.decode().replace(str(run_id), "<ID>") == BASE_CONTENT
        assert sorted((k, v) for k, v in response.headers.items() if k.lower() not in ("date", "x-request-id")) == (
            BASE_HEADERS
        )
        row = RunRow.for_company(world.company_a).filter(pk=run_id).values().get()
        assert (row.pop("idempotency_key"), row.pop("idempotency_sha256")) == (None, None)  # 새 칸 둘 NULL
        assert row.pop("launch_key") is None  # LK1: launchKey 없는 요청은 NULL
        assert row.pop("parked_at") is None  # RM1b 0006: 만들 때 NULL(주차 아님)
        assert {k: v for k, v in row.items() if k not in SKIPPED} == BASE_ROW
        assert list(row["options"]) == ["b", "a"]  # 쓴 차례 그대로
        assert RunStepRow.for_company(world.company_a).filter(run_id=run_id).count() == 3
        assert len(callbacks) == 1
    lines = AuditEventRow.unscoped.filter(action="run").order_by("id")
    assert [(a.actor_kind, a.event, a.result, a.target_kind, a.target_label) for a in lines] == [BASE_AUDIT] * 2
    assert (len(world.sent), RunRow.unscoped.count()) == (2, 2)


# ── 4 틀린 꼴 열쇠 ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "key",
    [
        "0B0E6C1E-1111-4222-8333-444455556666",  # 대문자
        "1",
        "",
        "0b0e6c1e-1111-4222-8333-4444556666777",  # 37자
        "0b0e6c1e11114222833344445566667",  # 이음표 없음
    ],
)
def test_a_malformed_key_is_422_validation_error_and_writes_nothing(client: Client, world: World, key: str) -> None:
    login(client)
    doc = document(world.company_a)
    response = create(client, {"module": "probe", "documentId": doc}, key=key)
    assert error_of(response) == (422, "VALIDATION_ERROR")
    assert "Idempotency-Key" in response.json()["error"]["fields"]
    assert counts() == (0, 0, 0)
    assert world.sent == []
    assert create(client, {"module": "probe", "documentId": doc}).status_code == 201  # 분모: 맞는 꼴은 지난다


# ── 5 거절 뒤 같은 열쇠 ───────────────────────────────────────────────


def test_a_refusal_leaves_no_key_so_the_fixed_request_with_the_same_key_is_created(
    client: Client, world: World
) -> None:
    login(client)
    doc = document(world.company_a, status="awaiting_upload")
    body = {"module": "probe", "documentId": doc}
    assert error_of(create(client, body)) == (409, "DOCUMENT_NOT_UPLOADED")
    assert counts() == (0, 0, 0)
    from esgapi.core.models import DocumentRow

    DocumentRow.for_company(world.company_a).filter(pk=doc).update(status="uploaded")  # 올림 확인
    response = create(client, body)
    assert response.status_code == 201
    assert counts() == (1, 3, 1)


# ── 6 이어 돌기 ───────────────────────────────────────────────────────


def test_resuming_twice_with_the_same_key_returns_the_same_child_not_resume_already(
    client: Client, world: World, django_capture_on_commit_callbacks: Any
) -> None:
    login(client)
    doc = document(world.company_a)
    previous = failed_run(world, doc)
    with django_capture_on_commit_callbacks(execute=True):
        first = create(client, resume_body(doc, previous))
    assert first.status_code == 201, first.content.decode()
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        second = create(client, resume_body(doc, previous))
    assert (second.status_code, second.json()["id"]) == (201, first.json()["id"])
    assert len(callbacks) == 0
    assert RunRow.for_company(world.company_a).filter(resumed_from_run_id=previous).count() == 1
    # 분모: 열쇠 없이 두 번이면 지금처럼 둘째가 409(새 앞 실행으로)
    other = failed_run(world, doc)
    assert create(client, resume_body(doc, other), key=None).status_code == 201
    assert error_of(create(client, resume_body(doc, other), key=None)) == (409, "RESUME_ALREADY")


def test_the_same_key_resuming_another_previous_run_is_409(client: Client, world: World) -> None:
    """IK1 검증 R1: 같은 열쇠로 resumeFromRunId 만 다른 본문 → 409 IDEMPOTENCY_KEY_REUSED(경로가 sha 에 그 칸을
    넣는다). 분모: 같은 본문은 같은 자식 201."""
    login(client)
    doc = document(world.company_a)
    first_previous, second_previous = failed_run(world, doc), failed_run(world, doc)
    first = create(client, resume_body(doc, first_previous))
    assert first.status_code == 201, first.content.decode()
    before = counts()
    assert error_of(create(client, resume_body(doc, second_previous))) == (409, "IDEMPOTENCY_KEY_REUSED")
    assert counts() == before
    assert RunRow.for_company(world.company_a).filter(resumed_from_run_id=second_previous).count() == 0
    again = create(client, resume_body(doc, first_previous))
    assert (again.status_code, again.json()["id"]) == (201, first.json()["id"])


# ── 7 문서 없는 흐름 ──────────────────────────────────────────────────


def test_a_documentless_run_follows_the_same_key_rules(
    client: Client, world: World, bare: BareBinding, django_capture_on_commit_callbacks: Any
) -> None:
    login(client)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        first = create(client, bare_body())
        second = create(client, bare_body())
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] == second.json()["id"]
    assert len(callbacks) == 1
    assert counts() == (1, 2, 1)
    changed = create(client, bare_body(options={"rows": [2, 1]}))
    assert error_of(changed) == (409, "IDEMPOTENCY_KEY_REUSED")
    assert counts() == (1, 2, 1)


# ── 8 범위 ────────────────────────────────────────────────────────────


def test_another_person_or_company_with_the_same_key_gets_their_own_run(client: Client, world: World) -> None:
    login(client)
    mine = create(client, {"module": "probe", "documentId": document(world.company_a)})
    colleague = Client()
    login(colleague, sub="edk-user-2")  # 같은 회사 다른 사람
    theirs = create(colleague, {"module": "probe", "documentId": document(world.company_a)})
    stranger = Client()
    login(stranger, sub="edk-user-3", tenant_id="tenant-b")  # 남의 회사
    far = create(stranger, {"module": "probe", "documentId": document(world.company_b)})
    assert (mine.status_code, theirs.status_code, far.status_code) == (201, 201, 201)
    assert len({mine.json()["id"], theirs.json()["id"], far.json()["id"]}) == 3
    assert (RunRow.for_company(world.company_a).count(), RunRow.for_company(world.company_b).count()) == (2, 1)
    # 분모: 처음 사람이 같은 열쇠로 한 번 더 → 그 사람의 실행 그대로
    again = create(client, {"module": "probe", "documentId": RunRow.unscoped.get(pk=mine.json()["id"]).document_id})
    assert (again.status_code, again.json()["id"]) == (201, mine.json()["id"])
    assert RunRow.unscoped.count() == 3


# ── 9 쿼리 수 ─────────────────────────────────────────────────────────


def test_a_replay_reads_the_session_and_the_key_only(client: Client, world: World) -> None:
    login(client)
    body = {"module": "probe", "documentId": document(world.company_a)}
    assert create(client, body).status_code == 201
    with CaptureQueriesContext(connection) as replay:
        assert create(client, body).status_code == 201
    run_queries = [q["sql"] for q in replay.captured_queries if '"run_runs"' in q["sql"]]
    assert len(run_queries) == 1 and "idempotency_key" in run_queries[0]  # 열쇠 찾기 하나(지금 상태도 이 줄)
    assert not [q for q in replay.captured_queries if q["sql"].startswith(("INSERT", "UPDATE"))]
    with CaptureQueriesContext(connection) as keyless:
        assert create(client, body, key=None).status_code == 201
    assert len(replay.captured_queries) == REPLAY_QUERIES
    assert len(keyless.captured_queries) == KEYLESS_QUERIES  # 분모: 열쇠 없는 만들기(BASE 와 같은 수)


# 잰 값(IK1): 다시 보냄 = 세이브포인트(create_run 의 atomic — 시험의 바깥 트랜잭션 안) + 열쇠 찾기 + 놓기. 세션은 서명
# 쿠키라 DB 0. 열쇠 없는 만들기 = 11 — BASE 4e28a54 의 같은 요청과 수·SQL 머리가 같다(보고 §쿼리)
REPLAY_QUERIES = 3
KEYLESS_QUERIES = 11
