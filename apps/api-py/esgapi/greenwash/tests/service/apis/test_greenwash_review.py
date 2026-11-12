# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""결과 GET·검토 GET/PUT 의 몸(밴드 G1b §3-2-1~5). 업무 층: 진짜 DB, 세션은 EDK 교환(login — 회사 A 의 고객사 사용자).

    3-2-1  검토 상태 기계: pending → 표시 → in_review → marks [] → in_review → 확정(미검토 채움·이름) → 409 잠김
    3-2-2  409 RUN_NOT_DONE(queued·processing·failed × GET·PUT), 409 NO_REVIEW(dry-run), 404(없음·남의 회사·다른 모듈)
    3-2-3  400 INVALID_REVIEW 다섯 갈래와 그때 표·감사 행 0
    3-2-4  감사 adopt·exclude·confirm(B5 — 확정의 없음→채택은 줄 0), 지운 표시는 decision NULL(DELETE 0)
    3-2-5  결과 GET 은 심은 결과를 그대로

★ 실행·결과 행은 seed(apps.get_model)로 심는다 — runs.models 를 import 하지 않는다(계약 나).
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from django.apps import apps
from django.test import Client

from esgapi.core.models import AuditEventRow
from esgapi.core.service.services.audit import AuditRefused
from esgapi.greenwash.contracts.review_shapes import REVIEW_SHAPES
from esgapi.greenwash.models import MARK_DECISIONS, REVIEW_STATES, GreenwashReviewMarkRow, GreenwashReviewRow
from esgapi.greenwash.service.actions import review as actions
from esgapi.greenwash.tests.service import seed
from tests.support.http import login

pytestmark = pytest.mark.django_db

NORMAL = seed.example("result-normal")  # items 넷


def user_id(company_id: int) -> int:
    """login 이 만든 고객사 사용자(토큰 sub edk-user-1)의 id."""
    user = apps.get_model("user", "User").for_company(company_id).get(username="edk-user-1")
    return int(user.pk)


def put(client: Client, run_id: int, body: dict[str, Any]) -> Any:
    return client.put(f"/api/greenwash/runs/{run_id}/review", data=body, content_type="application/json")


def get(client: Client, run_id: int, what: str = "review") -> Any:
    return client.get(f"/api/greenwash/runs/{run_id}/{what}")


def mark(index: int, decision: str = "adopted", reason: str | None = None) -> dict[str, Any]:
    return {"itemIndex": index, "decision": decision, "excludeReason": reason}


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def lines(company_id: int) -> list[tuple[Any, ...]]:
    rows = AuditEventRow.for_company(company_id).filter(action__in=("adopt", "exclude", "confirm")).order_by("id")
    return [(r.action, r.event, r.target_kind, r.target_id, r.target_label, r.actor_user_id) for r in rows]


def marks_in_db(company_id: int, run_id: int) -> dict[int, tuple[str | None, str | None]]:
    rows = GreenwashReviewMarkRow.for_company(company_id).filter(run_id=run_id).order_by("item_index")
    return {r.item_index: (r.decision, r.exclude_reason) for r in rows}


@pytest.fixture
def done_run(client: Client, companies: tuple[int, int]) -> int:
    login(client)
    return seed.run(companies[0], result=NORMAL)


def test_the_model_values_are_the_contract_values() -> None:
    assert REVIEW_STATES == ("pending", "in_review", "confirmed")
    assert MARK_DECISIONS == ("adopted", "excluded")


# ── 3-2-1 상태 기계 ──


def test_the_review_state_machine(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a = companies[0]
    pending = get(client, done_run)
    assert pending.status_code == 200
    assert pending.json() == {
        "schemaVersion": "greenwash.review@3",
        "runId": done_run,
        "state": "pending",
        "confirmedAt": None,
        "confirmedBy": None,
        "marks": [],
        "edits": [],
        "evidence": [],  # GRJ1(review@3)
        "rejudges": [],
    }
    assert GreenwashReviewRow.for_company(a).filter(run_id=done_run).count() == 0  # 읽기는 행을 만들지 않는다
    # 표시도 확정도 없는 PUT 은 행을 만들지 않는다
    assert put(client, done_run, {"marks": []}).json()["state"] == "pending"
    assert GreenwashReviewRow.for_company(a).filter(run_id=done_run).count() == 0

    # 받은 차례와 무관하게 itemIndex 오름
    marked = put(client, done_run, {"marks": [mark(2, "excluded", "근거 있음"), mark(0)]})
    assert marked.status_code == 200, marked.content.decode()
    assert marked.json()["state"] == "in_review"
    assert marked.json()["marks"] == [mark(0), mark(2, "excluded", "근거 있음")]
    REVIEW_SHAPES["greenwash.review@3"].validate_python(marked.json(), strict=True)
    assert get(client, done_run).json() == marked.json()

    cleared = put(client, done_run, {"marks": []})
    assert (cleared.json()["state"], cleared.json()["marks"]) == ("in_review", [])
    # 지운 표시의 행은 남고 decision·사유가 NULL(DELETE 0 — B2)
    assert marks_in_db(a, done_run) == {0: (None, None), 2: (None, None)}

    confirmed = put(client, done_run, {"state": "confirmed", "marks": [mark(1, "excluded", "기타 사유")]})
    body = confirmed.json()
    assert confirmed.status_code == 200, confirmed.content.decode()
    assert body["state"] == "confirmed"
    assert body["marks"] == [mark(0), mark(1, "excluded", "기타 사유"), mark(2), mark(3)]  # 미검토를 채택으로
    assert body["confirmedBy"] == {"id": user_id(a), "name": "김담당"}
    assert body["confirmedAt"].endswith("+09:00")
    REVIEW_SHAPES["greenwash.review@3"].validate_python(body, strict=True)
    assert get(client, done_run).json() == body

    locked = put(client, done_run, {"marks": [mark(0)]})
    assert code(locked) == (409, "REVIEW_LOCKED")
    # 잠긴 뒤 잘못된 본문도 409 가 먼저(규칙 5 는 4 앞)
    assert code(put(client, done_run, {"marks": [mark(99)]})) == (409, "REVIEW_LOCKED")
    assert get(client, done_run).json() == body


def test_an_unresolvable_confirmer_is_the_fallback_name(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    a = companies[0]
    put(client, done_run, {"state": "confirmed", "marks": []})
    GreenwashReviewRow.for_company(a).filter(run_id=done_run).update(confirmed_by_user_id=987654)
    assert get(client, done_run).json()["confirmedBy"] == {"id": 987654, "name": "알 수 없는 사용자"}


# ── 3-2-2 409·404 ──


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_a_run_that_is_not_done_is_409_everywhere(client: Client, companies: tuple[int, int], status: str) -> None:
    login(client)
    run_id = seed.run(companies[0], status=status)
    assert code(get(client, run_id)) == (409, "RUN_NOT_DONE")
    assert code(get(client, run_id, "result")) == (409, "RUN_NOT_DONE")
    assert code(put(client, run_id, {"marks": [mark(0)]})) == (409, "RUN_NOT_DONE")
    assert GreenwashReviewRow.for_company(companies[0]).count() == 0


def test_a_dry_run_has_no_review_but_has_a_result(client: Client, companies: tuple[int, int]) -> None:
    login(client)
    dry = seed.example("result-dry-run")
    run_id = seed.run(companies[0], result=dry)
    assert code(get(client, run_id)) == (409, "NO_REVIEW")
    assert code(put(client, run_id, {"state": "confirmed", "marks": []})) == (409, "NO_REVIEW")
    assert get(client, run_id, "result").json() == dry
    assert GreenwashReviewRow.for_company(companies[0]).count() == 0


def test_missing_foreign_and_other_module_runs_are_404(client: Client, companies: tuple[int, int]) -> None:
    a, b = companies
    login(client)
    theirs = seed.run(b, result=NORMAL)
    other_module = seed.run(a, module="probe", result=NORMAL)
    mine = seed.run(a, result=NORMAL)
    for run_id in (mine + 1000, theirs, other_module):
        assert code(get(client, run_id)) == (404, "NOT_FOUND")
        assert code(get(client, run_id, "result")) == (404, "NOT_FOUND")
        assert code(put(client, run_id, {"state": "confirmed", "marks": []})) == (404, "NOT_FOUND")
    assert GreenwashReviewRow.unscoped.count() == 0
    assert lines(a) == [] and lines(b) == []
    # 분모: 같은 세션의 제 실행은 된다
    assert put(client, mine, {"marks": [mark(0)]}).status_code == 200


def test_another_companys_review_rows_on_the_same_run_id_do_not_leak(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    """검토 표의 run_id 는 외래 키가 아니다(MARC-ENT-210) — 남의 회사 행이 같은 run_id 로 있어도(손으로 심음)
    읽기·쓰기는 세션의 회사 행만 본다(selector 의 for_company)."""
    a, b = companies
    GreenwashReviewRow.for_company(b).create(
        company_id=b, run_id=done_run, state="confirmed", confirmed_at=seed_time(), confirmed_by_user_id=5
    )
    GreenwashReviewMarkRow.for_company(b).create(
        company_id=b, run_id=done_run, item_index=0, decision="excluded", exclude_reason="B 의 사유"
    )
    assert get(client, done_run).json()["state"] == "pending"
    saved = put(client, done_run, {"marks": [mark(1)]})
    assert (saved.status_code, saved.json()["state"], saved.json()["marks"]) == (200, "in_review", [mark(1)])
    assert marks_in_db(b, done_run) == {0: ("excluded", "B 의 사유")}  # B 의 행 그대로
    assert marks_in_db(a, done_run) == {1: ("adopted", None)}


def seed_time() -> datetime:
    return datetime.now(tz=UTC)


def test_a_put_leaves_the_marks_of_another_run_alone(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """같은 회사의 두 실행에 같은 itemIndex 표시 — 한쪽을 지우고 확정해도 다른 실행의 표시는 그대로(검증 2 B2)."""
    a = companies[0]
    other = seed.run(a, result=NORMAL)
    both = {"marks": [mark(0), mark(1, "excluded", "근거")]}
    assert put(client, done_run, both).status_code == 200
    assert put(client, other, both).status_code == 200
    assert put(client, done_run, {"marks": []}).status_code == 200
    assert put(client, done_run, {"state": "confirmed", "marks": [mark(2, "excluded", "다른 근거")]}).status_code == 200
    assert marks_in_db(a, other) == {0: ("adopted", None), 1: ("excluded", "근거")}
    assert get(client, other).json()["state"] == "in_review"


# ── 3-2-3 400 INVALID_REVIEW ──


@pytest.mark.parametrize(
    ("marks", "message"),
    [
        ([mark(4)], "문장 번호 4은(는) 이 결과에 없어요(0부터 3까지)"),
        ([mark(1), mark(1, "excluded", "둘")], "문장 번호 1이(가) 두 번 왔어요"),
        ([mark(0, "adopted", "")], "채택한 문장에는 제외 사유를 넣지 않아요"),
        ([mark(0, "excluded", "   ")], "제외한 문장에는 사유가 있어야 해요"),
        ([mark(0, "excluded", "가" * 501)], "제외 사유는 500자까지 쓸 수 있어요"),
    ],
    ids=["range", "twice", "adopted-reason", "blank-reason", "long-reason"],
)
def test_bad_marks_are_400_and_write_nothing(
    client: Client, companies: tuple[int, int], done_run: int, marks: list[dict[str, Any]], message: str
) -> None:
    a = companies[0]
    response = put(client, done_run, {"marks": [mark(3), *marks]})
    assert code(response) == (400, "INVALID_REVIEW")
    assert response.json()["error"]["message"] == message
    assert GreenwashReviewRow.for_company(a).count() == 0
    assert GreenwashReviewMarkRow.for_company(a).count() == 0
    assert lines(a) == []
    # 분모: 500자 사유·빈 표시는 받는다
    assert put(client, done_run, {"marks": [mark(0, "excluded", "가" * 500)]}).status_code == 200


def test_a_null_reason_on_exclude_is_400(client: Client, done_run: int) -> None:
    assert code(put(client, done_run, {"marks": [mark(0, "excluded", None)]})) == (400, "INVALID_REVIEW")


# ── 3-2-4 감사 ──


def test_the_audit_lines_follow_what_changed(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a = companies[0]
    me = user_id(a)
    label = seed.FILE_NAME
    three = {"marks": [mark(0), mark(1), mark(2, "excluded", "자료 없음")]}
    assert put(client, done_run, three).status_code == 200
    assert lines(a) == [
        ("adopt", "greenwash_item_adopted", "greenwash_item", done_run, f"{label} · 문장 1", me),
        ("adopt", "greenwash_item_adopted", "greenwash_item", done_run, f"{label} · 문장 2", me),
        ("exclude", "greenwash_item_excluded", "greenwash_item", done_run, f"{label} · 문장 3", me),
    ]
    assert "자료 없음" not in str(list(AuditEventRow.for_company(a).values()))  # 사유 글은 싣지 않는다

    assert put(client, done_run, three).status_code == 200  # 같은 본문 다시 → 0 줄
    assert len(lines(a)) == 3
    assert put(client, done_run, {"marks": [mark(0)]}).status_code == 200  # 둘을 지움 → 0 줄
    assert len(lines(a)) == 3
    assert marks_in_db(a, done_run) == {0: ("adopted", None), 1: (None, None), 2: (None, None)}

    # 웹 꼴 확정: 미검토(1·2·3)를 adopted 로 채운 marks 전부 → 없음→채택은 줄 0, confirm 하나
    web_confirm = {"state": "confirmed", "marks": [mark(0), mark(1), mark(2), mark(3)]}
    assert put(client, done_run, web_confirm).status_code == 200
    assert lines(a)[3:] == [("confirm", "greenwash_review_confirmed", "run", done_run, label, me)]  # adopt 0(B5)
    rows = AuditEventRow.for_company(a).filter(action="confirm")
    assert [(r.actor_kind, r.result) for r in rows] == [("service", "success")]


def test_a_confirm_that_turns_an_exclusion_into_adoption_writes_one_adopt(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    a = companies[0]
    assert put(client, done_run, {"marks": [mark(1, "excluded", "근거")]}).status_code == 200
    assert put(client, done_run, {"state": "confirmed", "marks": [mark(1)]}).status_code == 200
    assert [x[0] for x in lines(a)] == ["exclude", "adopt", "confirm"]
    assert lines(a)[1][4] == f"{seed.FILE_NAME} · 문장 2"


def test_a_long_file_name_is_cut_to_the_label_size(client: Client, companies: tuple[int, int]) -> None:
    a = companies[0]
    login(client)
    run_id = seed.run(a, result=NORMAL, document_id=seed.document(a, name="가" * 255))
    assert put(client, run_id, {"marks": [mark(0)]}).status_code == 200
    assert lines(a)[0][4] == ("가" * 255 + " · 문장 1")[:255]


def refused(**_: object) -> AuditRefused:
    return AuditRefused("action")


def test_a_refused_audit_line_still_saves(
    client: Client, companies: tuple[int, int], done_run: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = companies[0]
    monkeypatch.setattr(actions, "record_event", refused)
    response = put(client, done_run, {"state": "confirmed", "marks": [mark(0, "excluded", "근거")]})
    assert response.status_code == 200
    assert response.json()["state"] == "confirmed"
    assert lines(a) == []


# ── 3-2-5 결과 GET ──


@pytest.mark.parametrize("name", ["result-normal", "result-many", "result-no-pages"])
def test_the_result_is_the_stored_body(client: Client, companies: tuple[int, int], name: str) -> None:
    login(client)
    body = seed.example(name)
    run_id = seed.run(companies[0], result=body)
    response = get(client, run_id, "result")
    assert response.status_code == 200
    assert response.json() == body
    assert next(iter(response.json())) == "schemaVersion"  # 선언한 꼴의 차례(jsonb 의 열쇠 차례가 아니다)
