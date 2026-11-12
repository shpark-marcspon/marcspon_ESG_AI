# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""근거 고침·재판단 만들기(밴드 GRJ1 ① — 결정 MARC-ENT-617, 꼴 greenwash.review@3). 업무 층: 진짜 DB, 세션은 EDK 교환.

    근거 고침 PUT: 저장·정규화(removed 오름·겹침 없음, 글 strip)·둘 다 비면 칸 NULL·400 갈래·확정 뒤 409
    재판단 POST: 근거 그대로 409 NOTHING_TO_REJUDGE · 202 + 옵션 굳힘·rejudge_run_ids 붙임·감사 한 줄 · 진행 중 409
      REJUDGE_RUNNING · 문장 밖·남의 회사 404 · 확정 뒤 409 REVIEW_LOCKED
    ④ 고침: 재판단 대기·진행 중 확정 409 REJUDGE_RUNNING(done 뒤 확정 됨) · 겹친 첫 PUT 이 잠근 뒤 다시 읽음 · NUL·짝
      없는 서로게이트 400
    직접 POST /runs(rejudge 흐름 새로 만들기·실패한 재판단 이어 돌기) 400 INVALID_OPTIONS·행 0 · 원 판을 다시 지을 수
      없으면 409 AI_SETTING_UNUSABLE · 문이 요청 사이에 새지 않음
    기준 판단(심은 done 재판단): removed 는 [] 로 읽고 added 는 남음 · 같은 added 면 409 · 고침 정규화가 기준과 견줌 ·
      가장 늦은 재판단이 실패면 status failed·current 앞 값 그대로

★ 실행·결과 행은 apps.get_model 로 심는다 — runs.models 를 import 하지 않는다(계약 나). 글·이름은 지은 것이다.
"""

import copy
import io
from typing import Any

import pytest
from django.apps import apps
from django.test import Client
from openpyxl import load_workbook

from esgapi.core.models import AuditEventRow
from esgapi.core.schemas import to_seoul_iso
from esgapi.greenwash.contracts.review_shapes import REVIEW_SHAPES, SHAPE
from esgapi.greenwash.flows import colab_e0, rejudge_e0
from esgapi.greenwash.models import GreenwashReviewMarkRow
from esgapi.greenwash.outputs import xlsx
from esgapi.greenwash.service.actions import review as review_actions
from esgapi.greenwash.service.services import review as review_services
from esgapi.greenwash.tests.service import seed
from esgapi.greenwash.tests.service.apis.test_greenwash_checks import FIXED_QUERIES, checks
from tests.support.http import login

pytestmark = pytest.mark.django_db

NORMAL = seed.example("result-normal")  # items 넷: High(칩 0) · Mid(칩 0) · Mid(칩 1) · Low
ADAPTER = REVIEW_SHAPES[SHAPE]
PIECE = "지어낸 근거 조각 — 감축 실적의 산정 범위"
NONRISK_ITEM: dict[str, Any] = {
    "level": None,
    "riskTags": [],
    "confirmedInEvidence": ["지어낸 사실 가", "지어낸 사실 나"],
    "missingFields": [],
    "reasonBullets": [],
    "fixParagraph": "",
    "evidencePages": [],
    "evidenceInternal": "",
}


def put(client: Client, run_id: int, body: dict[str, Any]) -> Any:
    return client.put(f"/api/greenwash/runs/{run_id}/review", data=body, content_type="application/json")


def review(client: Client, run_id: int) -> dict[str, Any]:
    got = client.get(f"/api/greenwash/runs/{run_id}/review")
    assert got.status_code == 200, got.content.decode()
    body = got.json()
    ADAPTER.validate_python(body, strict=True)
    return body


def rejudge(client: Client, run_id: int, index: int) -> Any:
    return client.post(f"/api/greenwash/runs/{run_id}/items/{index}/rejudge")


def evidence(index: int, removed: list[int] | None = None, added: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"itemIndex": index, "removed": removed or [], "added": added or []}


def piece(text: str = PIECE, page: int | None = 3) -> dict[str, Any]:
    return {"text": text, "page": page}


def code(response: Any) -> str:
    return str(response.json()["error"]["code"]).lower()


def runs_of(company_id: int, flow_id: str) -> list[Any]:
    return list(apps.get_model("runs", "RunRow").for_company(company_id).filter(flow_id=flow_id).order_by("id"))


def row(company_id: int, run_id: int, index: int) -> Any:
    return GreenwashReviewMarkRow.for_company(company_id).filter(run_id=run_id, item_index=index).first()


def planted(
    company_id: int,
    run_id: int,
    index: int,
    *,
    status: str = "done",
    added: list[dict[str, Any]] | None = None,
    item: dict[str, Any] | None = None,
    outcome: str = "judged",
) -> int:
    """재판단 실행 하나(문서 없음)와 done 이면 rejudge@1 결과를 심고 그 문장 행에 붙인다(검토 행이 없으면 만든다)."""
    review_services.create_review(company_id=company_id, run_id=run_id)
    run_row = apps.get_model("runs", "RunRow")
    made = run_row.for_company(company_id).create(
        company_id=company_id,
        document_id=None,
        module="greenwash",
        flow_id=rejudge_e0.FLOW_ID,
        options={},
        versions={},
        status=status,
        created_by_user_id=1,
    )
    if status == "done":
        body = {
            "schemaVersion": "greenwash.rejudge@1",
            "fromRunId": run_id,
            "itemIndex": index,
            "sentence": NORMAL["items"][index]["sentence"],
            "kept": [],
            "added": added or [],
            "outcome": outcome,
            "item": item
            or {
                "level": "High",
                "riskTags": ["근거 부족"],
                "confirmedInEvidence": ["지어낸 사실 가", "지어낸 사실 나"],
                "missingFields": ["기준연도"],
                "reasonBullets": ["다시 본 사유 한 줄."],
                "fixParagraph": "다시 본 수정 방향입니다. 산정 범위를 밝히는 것이 바람직합니다.",
                "evidencePages": [3],
                "evidenceInternal": "",
            },
        }
        apps.get_model("runs", "RunResultRow").for_company(company_id).create(
            company_id=company_id, run_id=made.pk, position=0, schema_version=body["schemaVersion"], body=body
        )
        run_row.for_company(company_id).filter(pk=made.pk).update(finished_at=made.created_at)
    review_services.append_rejudge(company_id=company_id, run_id=run_id, item_index=index, rejudge_run_id=made.pk)
    return int(made.pk)


@pytest.fixture
def done_run(client: Client, companies: tuple[int, int]) -> int:
    login(client)
    return seed.run(companies[0], result=NORMAL)


# ── 근거 고침 PUT ──


def test_evidence_is_saved_tidied_and_read_back(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a = companies[0]
    saved = put(client, done_run, {"marks": [], "evidence": [evidence(2, [0, 0], [piece("  " + PIECE + "  ")])]})
    assert saved.status_code == 200, saved.content.decode()
    (shown,) = saved.json()["evidence"]
    assert (shown["itemIndex"], shown["removed"], shown["added"]) == (2, [0], [piece()])
    assert saved.json()["state"] == "in_review"  # 근거 고침도 검토 활동
    assert review(client, done_run)["evidence"] == saved.json()["evidence"]
    stored = row(a, done_run, 2)
    assert (stored.evidence_removed, stored.evidence_added, stored.evidence_basis_run_id) == ([0], [piece()], None)
    # 생략·null = 그대로 · 목록 [] = 다 지움(칸 NULL, 행은 남김)
    assert put(client, done_run, {"marks": []}).json()["evidence"] == saved.json()["evidence"]
    assert put(client, done_run, {"marks": [], "evidence": []}).json()["evidence"] == []
    stored = row(a, done_run, 2)
    assert (stored.evidence_removed, stored.evidence_added, stored.evidence_edited_at) == (None, None, None)


@pytest.mark.parametrize(
    ("given", "says"),
    [
        ([evidence(9, [], [piece()])], "문장 번호 9"),
        ([evidence(2, [], [piece()]), evidence(2, [0])], "두 번"),
        ([evidence(2, [1])], "근거(1개) 밖"),
        ([evidence(0, [0])], "근거(0개) 밖"),
        ([evidence(2, [], [piece()] * 11)], "10개까지"),
        ([evidence(2, [], [piece("가" * 1001)])], "1000자까지"),
        ([evidence(2, [], [piece(" " * 2001)])], "1000자까지"),  # strip 전 그물
        ([evidence(2, [], [piece("   ")])], "비워 둘 수 없어요"),
        ([evidence(2, [], [piece(page=9)])], "1부터 8까지"),
        ([evidence(2, [], [piece("지어낸\x00조각")])], "쓸 수 없는 글자"),  # ④ M1: jsonb 가 받지 않는 글자
    ],
)
def test_bad_evidence_is_400_and_writes_nothing(
    client: Client, companies: tuple[int, int], done_run: int, given: list[dict[str, Any]], says: str
) -> None:
    refused = put(client, done_run, {"marks": [], "evidence": given})
    assert (refused.status_code, code(refused)) == (400, "invalid_review")
    assert says in refused.json()["error"]["message"]
    assert GreenwashReviewMarkRow.for_company(companies[0]).filter(run_id=done_run).count() == 0


def test_a_lone_surrogate_never_reaches_the_store(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """④ M1 의 짝 없는 서로게이트는 본문 꼴(JSON 풀기)에서 먼저 422 — 500 도 행도 없다. 판정식 has_bad_chars 는 서버
    안 다른 길의 그물로 남는다."""
    refused = put(client, done_run, {"marks": [], "evidence": [evidence(2, [], [piece("홀로 온 \ud800")])]})
    assert refused.status_code == 422
    assert GreenwashReviewMarkRow.for_company(companies[0]).filter(run_id=done_run).count() == 0


def test_an_added_piece_with_an_unknown_key_is_refused(client: Client, done_run: int) -> None:
    """닫힌 꼴(7a 조건 ①): GreenwashEvidenceAdded 에 모르는 칸이면 본문 꼴에서 거절."""
    refused = put(client, done_run, {"marks": [], "evidence": [evidence(2, [], [{**piece(), "url": "x"}])]})
    assert refused.status_code == 422


def test_evidence_is_locked_after_confirm(client: Client, companies: tuple[int, int], done_run: int) -> None:
    assert put(client, done_run, {"marks": [], "state": "confirmed"}).status_code == 200
    locked = put(client, done_run, {"marks": [], "evidence": [evidence(2, [0])]})
    assert (locked.status_code, code(locked)) == (409, "review_locked")
    assert row(companies[0], done_run, 2).evidence_added is None


# ── 재판단 만들기 ──


def test_nothing_to_rejudge_without_an_evidence_edit(client: Client, companies: tuple[int, int], done_run: int) -> None:
    refused = rejudge(client, done_run, 2)
    assert (refused.status_code, code(refused)) == (409, "nothing_to_rejudge")
    assert runs_of(companies[0], rejudge_e0.FLOW_ID) == []


def test_a_rejudge_freezes_the_options_and_is_appended(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    a = companies[0]
    put(client, done_run, {"marks": [], "evidence": [evidence(2, [0], [piece()])]})
    made = rejudge(client, done_run, 2)
    assert made.status_code == 202, made.content.decode()
    (run,) = runs_of(a, rejudge_e0.FLOW_ID)
    assert made.json() == {"rejudgeRunId": run.pk}
    assert (run.document_id, run.module, run.status) == (None, "greenwash", "queued")
    checker = NORMAL["config"]["checker"]
    assert run.options == {
        "fromRunId": done_run,
        "itemIndex": 2,
        "sentence": NORMAL["items"][2]["sentence"],
        "lowOnly": False,
        "kept": [],  # 칩 하나를 지웠다
        "added": [piece()],
        "maxCharsPerChunk": checker["maxCharsPerChunk"],
        "maxCharsEvidenceTotal": checker["maxCharsEvidenceTotal"],
        "promptVersion": checker["promptVersion"],
    }
    assert run.versions == {"flow": rejudge_e0.FLOW_ID}  # 원 실행의 판(심은 실행은 {}) + 흐름
    assert row(a, done_run, 2).rejudge_run_ids == [run.pk]
    audit = [(e.action, e.event, e.target_kind) for e in AuditEventRow.for_company(a).order_by("id")]
    assert audit[-2:] == [("run", "run_created", "run"), ("run", "greenwash_item_rejudged", "greenwash_item")]
    # 진행 중이면 두 번째는 409(돈 드는 실행 둘 막기) · 읽기는 running·count 0·current null
    again = rejudge(client, done_run, 2)
    assert (again.status_code, code(again)) == (409, "rejudge_running")
    assert len(runs_of(a, rejudge_e0.FLOW_ID)) == 1
    assert review(client, done_run)["rejudges"] == [{"itemIndex": 2, "status": "running", "count": 0, "current": None}]
    assert not rejudge_e0.gate_open()


def test_the_prompt_version_is_counted_from_the_original_runs_config(
    client: Client, companies: tuple[int, int]
) -> None:
    """GRS1(MARC-ISSUE-632): 원 실행 config.checker 가 지금 SCAN_CONFIG 와 다르면 옵션의 판 글자는 원 config 쪽 —
    judge 와 같은 길(sanitize_config_dict → GWConfig, 앞뒤 공백을 지운다)."""
    login(client)
    a = companies[0]
    now = colab_e0.judged_prompt_version(dict(colab_e0.SCAN_CONFIG))
    old = copy.deepcopy(NORMAL)
    old["config"]["checker"]["promptVersion"] = "  2025-07-01-v0 "
    assert now != "2025-07-01-v0"
    run_id = seed.run(a, result=old)
    put(client, run_id, {"marks": [], "evidence": [evidence(2, [0])]})
    assert rejudge(client, run_id, 2).status_code == 202
    (run,) = runs_of(a, rejudge_e0.FLOW_ID)
    assert run.options["promptVersion"] == "2025-07-01-v0"


def test_a_low_sentence_keeps_the_low_branch(client: Client, companies: tuple[int, int], done_run: int) -> None:
    put(client, done_run, {"marks": [], "evidence": [evidence(3, [], [piece(page=None)])]})
    assert rejudge(client, done_run, 3).status_code == 202
    (run,) = runs_of(companies[0], rejudge_e0.FLOW_ID)
    assert (run.options["lowOnly"], run.options["kept"], run.options["added"]) == (True, [], [piece(page=None)])


def test_rejudge_refusals(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a, b = companies
    put(client, done_run, {"marks": [], "evidence": [evidence(2, [0])]})
    assert rejudge(client, done_run, 4).status_code == 404  # 문장 밖
    assert rejudge(client, done_run + 1000, 2).status_code == 404
    theirs = seed.run(b, result=NORMAL)
    assert rejudge(client, theirs, 2).status_code == 404  # 남의 회사
    put(client, done_run, {"marks": [], "state": "confirmed"})
    locked = rejudge(client, done_run, 2)
    assert (locked.status_code, code(locked)) == (409, "review_locked")
    assert runs_of(a, rejudge_e0.FLOW_ID) == []


def test_confirm_waits_for_a_running_rejudge(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """④ B1: 대기·진행 중인 재판단이 있으면 확정 PUT 은 409 REJUDGE_RUNNING·상태 그대로·쓰기 0 — 끝난(done) 뒤에는
    확정된다. 반대 방향(확정 → 재판단 409 REVIEW_LOCKED)은 test_rejudge_refusals 가 잰다. 같은 검토 행 잠금 아래서
    서로 막으므로 확정 뒤에 끝나는 재판단은 생기지 않는다."""
    a = companies[0]
    put(client, done_run, {"marks": [], "evidence": [evidence(2, [0], [piece()])]})
    made = rejudge(client, done_run, 2)
    assert made.status_code == 202, made.content.decode()

    def marks_now() -> list[tuple[int, str | None]]:
        return [(r.item_index, r.decision) for r in GreenwashReviewMarkRow.for_company(a).filter(run_id=done_run)]

    marks = marks_now()
    audits = AuditEventRow.for_company(a).count()
    for status in ("queued", "processing"):
        apps.get_model("runs", "RunRow").for_company(a).filter(pk=made.json()["rejudgeRunId"]).update(status=status)
        refused = put(client, done_run, {"marks": [], "state": "confirmed"})
        assert (refused.status_code, code(refused)) == (409, "rejudge_running")
        assert review(client, done_run)["state"] == "in_review"
        assert marks_now() == marks
        assert AuditEventRow.for_company(a).count() == audits
    # 표시·고침만 저장하는 PUT 은 그대로 된다(막는 것은 확정뿐)
    adopted = {"marks": [{"itemIndex": 0, "decision": "adopted", "excludeReason": None}]}
    assert put(client, done_run, adopted).status_code == 200
    apps.get_model("runs", "RunRow").for_company(a).filter(pk=made.json()["rejudgeRunId"]).update(status="done")
    confirmed = put(client, done_run, {"marks": [], "state": "confirmed"})
    assert confirmed.status_code == 200, confirmed.content.decode()
    assert confirmed.json()["state"] == "confirmed"


def test_evidence_of_a_running_sentence_is_held(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """GRJ3(규칙 8 넓힘): 재판단이 대기·진행 중인 문장의 근거를 지금 값과 다르게 바꾸는 PUT 은 409 REJUDGE_RUNNING·
    쓰기 0. 같은 값을 다시 실은 PUT(웹은 evidence 를 전체로 싣는다)·다른 문장의 근거·표시·고침만은 받고, 끝난
    뒤에는 받는다."""
    a = companies[0]
    first = {"marks": [], "evidence": [evidence(2, [0], [piece()])]}
    assert put(client, done_run, first).status_code == 200
    made = rejudge(client, done_run, 2)
    assert made.status_code == 202, made.content.decode()
    rejudge_run = made.json()["rejudgeRunId"]

    def stored() -> tuple[Any, Any, Any]:
        r = row(a, done_run, 2)
        return r.evidence_removed, r.evidence_added, r.evidence_edited_at

    before = stored()
    for status in ("queued", "processing"):
        apps.get_model("runs", "RunRow").for_company(a).filter(pk=rejudge_run).update(status=status)
        for changed in (
            [evidence(2, [], [piece()])],  # 칩 되살림
            [evidence(2, [0], [piece(), piece("지어낸 둘째 조각", None)])],  # 조각 더함
            [],  # 근거 고침 다 지움
            [evidence(0, [], [piece("지어낸 다른 문장 조각")]), evidence(2, [0])],  # 다른 문장과 같이, 도는 문장이 바뀜
        ):
            refused = put(client, done_run, {"marks": [], "evidence": changed})
            assert (refused.status_code, code(refused)) == (409, "rejudge_running"), changed
            assert stored() == before
            assert row(a, done_run, 0) is None or row(a, done_run, 0).evidence_added is None
        # 같은 값을 다시 실음(앞뒤 공백은 정규화로 같다)
        again = put(client, done_run, {"marks": [], "evidence": [evidence(2, [0], [piece(f"  {PIECE} ")])]})
        assert again.status_code == 200, again.content.decode()
        assert stored() == before
    # 다른 문장의 근거는 받는다(도는 문장은 같은 값으로 실음)
    other = put(
        client,
        done_run,
        {"marks": [], "evidence": [evidence(0, [], [piece("지어낸 다른 문장 조각")]), evidence(2, [0], [piece()])]},
    )
    assert other.status_code == 200, other.content.decode()
    assert row(a, done_run, 0).evidence_added == [piece("지어낸 다른 문장 조각")]
    assert stored() == before
    # 표시·고침만(evidence 생략)은 받는다
    marked = put(client, done_run, {"marks": [{"itemIndex": 2, "decision": "adopted", "excludeReason": None}]})
    assert marked.status_code == 200, marked.content.decode()
    edited = put(
        client,
        done_run,
        {
            "marks": [{"itemIndex": 2, "decision": "adopted", "excludeReason": None}],
            "edits": [{"itemIndex": 2, "level": None, "reasonBullets": None, "fixParagraph": "지어낸 고친 방향."}],
        },
    )
    assert edited.status_code == 200, edited.content.decode()
    assert stored() == before
    # 끝난(failed — 기준 판단 그대로) 뒤에는 근거를 바꿀 수 있다
    apps.get_model("runs", "RunRow").for_company(a).filter(pk=rejudge_run).update(status="failed")
    after = put(client, done_run, {"marks": [], "evidence": [evidence(2, [], [piece()])]})
    assert after.status_code == 200, after.content.decode()
    assert row(a, done_run, 2).evidence_removed == []


def test_a_running_sentence_takes_its_shown_evidence_after_the_basis_moved(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    """GRJ3 검증 W1: 앞 재판단(done)으로 기준 판단이 바뀌어 옛 지운 칩이 행에만 남은 문장에 둘째 재판단이 도는 중일 때,
    화면 값(지운 칩 [] — evidence_now)을 다시 실은 PUT 은 200·근거 그대로. 날 행 값(removed [0])과 견주면 409 가
    된다."""
    a = companies[0]
    assert put(client, done_run, {"marks": [], "evidence": [evidence(2, [0], [piece()])]}).status_code == 200
    planted(a, done_run, 2, added=[piece()])  # done — 기준 판단이 바뀐다
    planted(a, done_run, 2, status="processing")  # 둘째 재판단이 돈다
    assert row(a, done_run, 2).evidence_removed == [0]  # 옛 지운 칩이 행에 남아 있다
    shown = review(client, done_run)
    assert next(e for e in shown["evidence"] if e["itemIndex"] == 2)["removed"] == []
    again = put(client, done_run, {"marks": [], "evidence": [evidence(2, [], [piece()])]})
    assert again.status_code == 200, again.content.decode()
    changed = put(client, done_run, {"marks": [], "evidence": [evidence(2, [], [])]})
    assert (changed.status_code, code(changed)) == (409, "rejudge_running")


def test_overlapping_first_puts_read_the_rows_again_after_the_lock(
    client: Client, companies: tuple[int, int], done_run: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """④ B2(머리말 규칙 7): 검토 행이 없는 실행에 첫 PUT 둘이 겹치면, 늦은 쪽은 잠근 뒤 앞 쪽이 만든 표시 행을 보고
    UPDATE 한다(낡은 빈 before 로 INSERT 하면 유일 제약 500). 겹친 앞 PUT 은 create_review 가 흡수되는 자리에서
    표시 행 하나를 먼저 커밋한 것으로 흉내 낸다."""
    a = companies[0]
    real = review_services.create_review

    def raced(*, company_id: int, run_id: int) -> None:
        real(company_id=company_id, run_id=run_id)
        GreenwashReviewMarkRow.for_company(company_id).create(
            company_id=company_id, run_id=run_id, item_index=0, decision="adopted"
        )

    monkeypatch.setattr(review_actions.services, "create_review", raced)
    saved = put(client, done_run, {"marks": [{"itemIndex": 0, "decision": "excluded", "excludeReason": "지은 사유"}]})
    assert saved.status_code == 200, saved.content.decode()
    stored = row(a, done_run, 0)
    assert (stored.decision, stored.exclude_reason) == ("excluded", "지은 사유")
    assert GreenwashReviewMarkRow.for_company(a).filter(run_id=done_run).count() == 1


def test_posting_the_rejudge_flow_to_runs_is_refused(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """덧붙임 3: 그린 경로를 거치지 않는 만들기는 옵션 검사(check_options)의 문에서 400·행 0."""
    options = {
        "fromRunId": done_run,
        "itemIndex": 2,
        "sentence": "지은 문장",
        "lowOnly": False,
        "kept": [],
        "added": [piece()],
        "maxCharsPerChunk": 500,
        "maxCharsEvidenceTotal": 1600,
    }
    body = {"module": "greenwash", "flowId": rejudge_e0.FLOW_ID, "options": options}
    refused = client.post("/api/runs", data=body, content_type="application/json")
    assert (refused.status_code, code(refused)) == (400, "invalid_options")
    assert refused.json()["error"]["message"] == rejudge_e0.NOT_FROM_REVIEW
    assert runs_of(companies[0], rejudge_e0.FLOW_ID) == []
    assert not rejudge_e0.gate_open()


def test_resuming_a_failed_rejudge_through_runs_is_refused(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    """검증 1 B1: create_run 의 이어 돌기는 versions_with 를 부르지 않고 앞 판을 베낀다 — 문은 check_options 에도 있어
    실패한 재판단을 POST /runs resumeFromRunId 로 다시 돌리지 못한다(400·행 0·문장 행 그대로)."""
    a = companies[0]
    put(client, done_run, {"marks": [], "evidence": [evidence(2, [0], [piece()])]})
    made = rejudge(client, done_run, 2)
    assert made.status_code == 202, made.content.decode()
    first = made.json()["rejudgeRunId"]
    apps.get_model("runs", "RunRow").for_company(a).filter(pk=first).update(status="failed", failed_step="judge")
    body = {"module": "greenwash", "flowId": rejudge_e0.FLOW_ID, "options": {}, "resumeFromRunId": first}
    refused = client.post("/api/runs", data=body, content_type="application/json")
    assert (refused.status_code, code(refused)) == (400, "invalid_options"), refused.content.decode()
    assert refused.json()["error"]["message"] == rejudge_e0.NOT_FROM_REVIEW
    assert [run.pk for run in runs_of(a, rejudge_e0.FLOW_ID)] == [first]
    assert row(a, done_run, 2).rejudge_run_ids == [first]
    assert not rejudge_e0.gate_open()


def test_an_original_setting_that_cannot_be_rebuilt_is_409(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    """검증 1 B2 · §2-3: 원 실행의 AI 설정 판을 지금 다시 지을 수 없으면 만들 때 409 ai_setting_unusable·행 0."""
    a = companies[0]
    gone = {"aiSetting": "지은 판", "aiSettingId": 987654, "evalPromptSha256": "0" * 64, "flow": "greenwash.colab@E0"}
    apps.get_model("runs", "RunRow").for_company(a).filter(pk=done_run).update(versions=gone)
    put(client, done_run, {"marks": [], "evidence": [evidence(2, [0], [piece()])]})
    refused = rejudge(client, done_run, 2)
    assert (refused.status_code, code(refused)) == (409, "ai_setting_unusable"), refused.content.decode()
    assert runs_of(a, rejudge_e0.FLOW_ID) == []
    assert row(a, done_run, 2).rejudge_run_ids is None
    assert not rejudge_e0.gate_open()


def test_the_gate_closes_even_when_creating_raises() -> None:
    with pytest.raises(RuntimeError), rejudge_e0.creating({"a": 1}, {}):
        assert rejudge_e0.gate_open()
        raise RuntimeError("부러뜨림")
    assert not rejudge_e0.gate_open()


# ── 기준 판단 ──


def test_a_done_rejudge_becomes_the_basis(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a = companies[0]
    put(client, done_run, {"marks": [], "evidence": [evidence(2, [0], [piece()])]})
    first = planted(a, done_run, 2, added=[piece()])
    state = review(client, done_run)
    (line,) = state["rejudges"]
    assert (line["status"], line["count"], line["current"]["runId"]) == ("done", 1, first)
    assert line["current"]["confirmedInEvidence"] == ["지어낸 사실 가", "지어낸 사실 나"]
    # R3 안 C: removed 는 옛 칩을 가리키므로 [] · added 는 남음
    (shown,) = state["evidence"]
    assert (shown["removed"], shown["added"]) == ([], [piece()])
    # R4: 더한 조각이 기준 판단에 보낸 것과 같고 지운 칩 0 → 다시 판단할 것 없음
    assert code(rejudge(client, done_run, 2)) == "nothing_to_rejudge"
    # 새 칩(둘)의 차례로 지울 수 있다 — 범위는 기준 판단의 칩 수
    assert put(client, done_run, {"marks": [], "evidence": [evidence(2, [1], [piece()])]}).status_code == 200
    assert row(a, done_run, 2).evidence_basis_run_id == first
    assert rejudge(client, done_run, 2).status_code == 202


def test_edits_are_folded_against_the_basis(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """§2-4: 「AI 값과 같으면 null」 견줌은 기준 판단과 한다(첫 판단과 견주면 고침이 조용히 사라진다)."""
    a = companies[0]
    planted(a, done_run, 2)
    first_level = NORMAL["items"][2]["level"]  # Mid — 기준 판단은 High
    body = {"marks": [], "edits": [{"itemIndex": 2, "level": first_level, "reasonBullets": None, "fixParagraph": None}]}
    (kept,) = put(client, done_run, body).json()["edits"]
    assert kept["level"]["value"] == first_level  # 첫 판단과 같지만 기준과 달라 남는다
    body["edits"][0]["level"] = "High"
    assert put(client, done_run, body).json()["edits"] == []  # 기준 판단과 같으면 접힌다


def test_a_failed_latest_keeps_the_previous_basis(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a = companies[0]
    first = planted(a, done_run, 2)
    planted(a, done_run, 2, status="failed")
    (line,) = review(client, done_run)["rejudges"]
    assert (line["status"], line["count"], line["current"]["runId"]) == ("failed", 1, first)


def test_a_deleted_latest_is_failed_not_running(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """GRS1(MARC-ISSUE-633): 가장 늦은 재판단 실행의 행이 없으면(지워짐) running 이 아니라 failed · 기준은 앞 done
    그대로 — 그래서 재판단 만들기·근거 PUT·확정의 409 REJUDGE_RUNNING 이 영영 걸리지 않는다."""
    a = companies[0]
    first = planted(a, done_run, 2)
    gone = planted(a, done_run, 2, status="processing")
    apps.get_model("runs", "RunRow").for_company(a).filter(pk=gone).delete()
    assert gone in row(a, done_run, 2).rejudge_run_ids  # 문장 행은 지운 id 를 그대로 든다
    (line,) = review(client, done_run)["rejudges"]
    assert (line["status"], line["count"], line["current"]["runId"]) == ("failed", 1, first)
    saved = put(client, done_run, {"marks": [], "evidence": [evidence(2, [0], [piece()])]})
    assert saved.status_code == 200, saved.content.decode()  # 근거 PUT 이 막히지 않는다
    made = rejudge(client, done_run, 2)
    assert made.status_code == 202, made.content.decode()  # 만들기도 막히지 않는다
    made_id = made.json()["rejudgeRunId"]
    apps.get_model("runs", "RunStepRow").for_company(a).filter(run_id=made_id).delete()  # 단계 행이 실행을 지킨다
    apps.get_model("runs", "RunRow").for_company(a).filter(pk=made_id).delete()
    assert review(client, done_run)["rejudges"][0]["status"] == "failed"
    confirmed = put(client, done_run, {"marks": [], "state": "confirmed"})
    assert confirmed.status_code == 200, confirmed.content.decode()  # 확정도


def test_the_latest_done_rejudge_is_the_basis(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """검증 2 R1: done 이 둘이면 뒤 것이 기준(검토 GET·목록 셈 둘 다) · 뒤에 running 이 와도 앞 done 이 기준."""
    a = companies[0]
    low = {**NONRISK_ITEM, "level": "Low", "reasonBullets": ["뒤에 본 사유 한 줄."]}
    planted(a, done_run, 2)  # Mid → High
    later = planted(a, done_run, 2, item=low)  # → Low
    (line,) = review(client, done_run)["rejudges"]
    assert (line["status"], line["count"], line["current"]["runId"]) == ("done", 2, later)
    assert line["current"]["level"] == "Low"
    assert checks(client)["runs"][0]["levelCounts"] == {"High": 1, "Mid": 1, "Low": 2}
    planted(a, done_run, 2, status="processing")  # 진행 중(GET 에선 running)
    (line,) = review(client, done_run)["rejudges"]
    assert (line["status"], line["count"], line["current"]["runId"]) == ("running", 2, later)
    assert checks(client)["runs"][0]["levelCounts"] == {"High": 1, "Mid": 1, "Low": 2}


def test_a_nonrisk_basis_reads_with_a_null_level(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a = companies[0]
    item = {
        "level": None,
        "riskTags": [],
        "confirmedInEvidence": ["지어낸 사실 가", "지어낸 사실 나"],
        "missingFields": [],
        "reasonBullets": ["리스크 아님 사유."],
        "fixParagraph": "",
        "evidencePages": [],
        "evidenceInternal": "",
    }
    planted(a, done_run, 1, item=item, outcome="nonrisk")
    (line,) = review(client, done_run)["rejudges"]
    assert (line["current"]["outcome"], line["current"]["level"]) == ("nonrisk", None)


# ── 큐 넣기는 바깥 커밋 뒤(7a 조건 — create_run 과 문장 행 붙이기가 한 트랜잭션) ──


def test_the_queue_hears_only_after_the_outer_commit(
    client: Client,
    companies: tuple[int, int],
    done_run: int,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
) -> None:
    from esgapi.core.resources import queue as hooks

    sent: list[tuple[int, int]] = []

    def heard(*, company_id: int, run_id: int) -> None:
        sent.append((company_id, run_id))

    monkeypatch.setattr(hooks, "enqueue_run", heard)
    put(client, done_run, {"marks": [], "evidence": [evidence(2, [0])]})
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        made = rejudge(client, done_run, 2)
        assert made.status_code == 202
        assert sent == []  # 요청 안에서는 큐에 넣지 않는다(커밋 뒤 갈고리 하나로 미뤄짐)
    assert len(callbacks) == 1
    callbacks[0]()
    assert sent == [(companies[0], made.json()["rejudgeRunId"])]


def test_a_failure_after_create_run_leaves_no_run_and_no_queue(
    client: Client,
    companies: tuple[int, int],
    done_run: int,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
) -> None:
    from esgapi.core.resources import queue as hooks

    sent: list[int] = []

    def heard(*, company_id: int, run_id: int) -> None:
        sent.append(run_id)

    monkeypatch.setattr(hooks, "enqueue_run", heard)
    put(client, done_run, {"marks": [], "evidence": [evidence(2, [0])]})

    def broken(**_: Any) -> None:
        raise RuntimeError("붙이기 부러뜨림")

    monkeypatch.setattr(review_services, "append_rejudge", broken)
    client.raise_request_exception = False
    with django_capture_on_commit_callbacks(execute=True):
        assert rejudge(client, done_run, 2).status_code == 500
    assert runs_of(companies[0], rejudge_e0.FLOW_ID) == []  # 한 트랜잭션 — 실행 행도 되돌려졌다
    assert sent == []
    assert not rejudge_e0.gate_open()


# ── 목록·엑셀(GRJ1 ②) ──


def test_a_rejudge_run_is_not_a_list_row_and_the_basis_counts(
    client: Client, companies: tuple[int, int], done_run: int, django_assert_num_queries: Any
) -> None:
    """§1-7: 재판단 실행(문서 없음)은 목록 줄이 아니다 · levelCounts 는 기준 판단(High)으로 · 리스크 아님은 세 칸 밖."""
    a = companies[0]
    other = seed.run(a, result=NORMAL)
    planted(a, done_run, 2)  # Mid → 기준 High
    planted(a, other, 1, item={**NONRISK_ITEM}, outcome="nonrisk")  # Mid → 리스크 아님
    with django_assert_num_queries(FIXED_QUERIES + 2):  # 재판단 실행 1·결과 1(재판단 있는 실행 수와 무관)
        listed = {r["runId"]: r for r in checks(client)["runs"]}
    assert set(listed) == {done_run, other}
    assert listed[done_run]["levelCounts"] == {"High": 2, "Mid": 1, "Low": 1}
    assert listed[other]["levelCounts"] == {"High": 1, "Mid": 1, "Low": 1}  # 합 3 < 문장 4


def test_judged_keys_are_the_workbook_basis_keys() -> None:
    assert review_actions.JUDGED_KEYS == xlsx.BASIS_KEYS


def test_the_confirmed_workbook_carries_the_basis_and_the_rejudge_columns(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    a = companies[0]
    put(client, done_run, {"marks": [], "evidence": [evidence(2, [0], [piece()])]})
    first = planted(a, done_run, 2, added=[piece()])
    planted(a, done_run, 1, item={**NONRISK_ITEM}, outcome="nonrisk")
    put(client, done_run, {"marks": [], "state": "confirmed"})
    response = client.get(f"/api/greenwash/runs/{done_run}/report?confirmed=true")
    assert response.status_code == 200, response.content
    book = load_workbook(io.BytesIO(response.content), read_only=True)
    sheets: dict[str, list[tuple[Any, ...]]] = {
        name: [tuple(r) for r in book[name].iter_rows(values_only=True)] for name in book.sheetnames
    }
    header, rows = sheets["문장"][0], sheets["문장"][1:]
    assert header == xlsx.SENTENCE_HEADER + xlsx.EDIT_HEADER + xlsx.REJUDGE_HEADER
    level = xlsx.SENTENCE_HEADER.index("등급")
    tail = len(xlsx.SENTENCE_HEADER) + len(xlsx.EDIT_HEADER)
    assert (rows[2][level], rows[1][level], rows[0][level]) == ("High", xlsx.NONRISK, NORMAL["items"][0]["level"])
    made = apps.get_model("runs", "RunRow").for_company(a).get(pk=first)
    minute = to_seoul_iso(made.created_at)[:16].replace("T", " ")
    # removed 는 기준이 바뀌어 0(안 C) · 심은 실행의 만든 사람은 이름 없는 사용자
    assert rows[2][tail:] == ("지움 0 · 더함 1", f"1회 · {minute} · {review_actions.UNKNOWN_USER}")
    assert rows[0][tail:] in ((None, None), ("", ""))
    summary: dict[Any, Any] = dict(sheets["요약"][1:])
    assert (summary["등급 High"], summary["등급 Mid"], summary["등급 Low"], summary[xlsx.NONRISK_SUMMARY]) == (
        2,
        0,
        1,
        1,
    )
    # 미확정 보고서(확정 뒤에도 confirmed 없이)는 첫 AI 판단 그대로 — 칸 둘 없음
    plain = client.get(f"/api/greenwash/runs/{done_run}/report")
    first_book = load_workbook(io.BytesIO(plain.content), read_only=True)
    first_rows: list[tuple[Any, ...]] = [tuple(r) for r in first_book["문장"].iter_rows(values_only=True)]
    assert first_rows[0] == xlsx.SENTENCE_HEADER
    assert first_rows[3][level] == NORMAL["items"][2]["level"]
