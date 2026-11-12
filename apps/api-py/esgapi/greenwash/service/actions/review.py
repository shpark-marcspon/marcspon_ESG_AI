"""결과 읽기와 검토 읽기·저장. runs(실행·결과)·core(문서·감사)·user(이름)를 엮어 조립하므로 Action 이다(Service·Selector
는 남의 도메인을 import 하지 않는다 — `.importlinter` 계약 바).

    run_result(company_id, run_id)               결과 GET: 규칙 1·2 → greenwash.result@1 본문
    review_state(company_id, run_id)             검토 GET: 규칙 1·2·3 → 검토 상태(행이 없으면 pending)
    put_review(company_id, actor_*, run_id, …)   검토 PUT: 규칙 1~7(4' 고침·정규화) + 감사 셋(adopt·exclude·confirm)

규칙(발주서 G1b §2-3, 계약 머리말 contracts/review_shapes.py):
  1. 실행이 없거나 남의 회사, 또는 module != greenwash → NotFound(404)
  2. status != done → RunNotDone(409 RUN_NOT_DONE)
  3. 결과 본문이 dry-run(dryRun 칸이 값) → NoReview(409 NO_REVIEW) — 검토만
  5. 확정된 실행에 PUT → ReviewLocked(409 REVIEW_LOCKED) — 1~3 뒤, 4 앞
  4. 표시 검사 → InvalidReview(400 INVALID_REVIEW, 한국어 한 문장): itemIndex 가 0 ≤ i < items 수 밖 ·
     같은 itemIndex 두 번 · adopted 인데 사유가 null 아님 · excluded 인데 사유가 비었거나 공백뿐 · 사유 500자 초과
  4'. 고침 검사(G1b-3, edits 가 목록일 때) → InvalidReview: itemIndex 범위 밖 · 같은 itemIndex 두 번 · 판정 사유가
     빈 항목을 버린 뒤 0 줄·10 줄 초과·한 줄 500자 초과 · 수정 방향이 앞뒤 공백을 지운 뒤 빈 글·2,000자 초과 ·
     strip 전 그물(GRV1) 원래 항목 50 초과·원래 한 줄 1,000자 초과·원래 수정 방향 4,000자 초과
     → 정규화(아래) 뒤 갈아 넣기. AI 값도 같은 다듬기를 한 뒤 견준다(GRV1)
  6. 상태: 표시나 (정규화 뒤) 고침이 하나라도 있으면 in_review, 둘 다 0 이고 state 없음이면 그대로(행이 없으면
     만들지 않는다 — AI 와 같은 값만 보낸 PUT 은 고침 0 이라 행 0·상태 그대로).
     confirmed → 미검토를 adopted 로 채우고 confirmedAt·confirmedBy → 잠금
  7. 동시성: 검토 행을 FOR UPDATE 로 잡고 한 atomic 안에서 갈아 넣는다(만들기 경합은 services 의 세이브포인트).
     둘이 겹쳐 하나가 확정이면 다른 하나는 잠근 뒤 확정을 보고 ReviewLocked. 행을 방금 만들었으면 잠근 뒤 표시 행과
     기준 판단을 다시 읽는다(겹친 첫 PUT 이 먼저 만든 행을 보고 upsert — GRJ1 ④ B2)
  8. 확정 PUT 인데 그 실행에 대기·진행 중인 재판단이 하나라도 있음 → RejudgeRunning(409 REJUDGE_RUNNING, GRJ1 ④ B1).
     재판단 만들기와 같은 검토 행 잠금 아래라, 확정 뒤에 끝나는 재판단은 생기지 않는다(만들기는 확정 뒤 REVIEW_LOCKED)
     evidence 를 실은 PUT 이 재판단이 대기·진행 중인 문장의 근거를 지금 유효한 값(evidence_now)과 다르게 바꿔도
     RejudgeRunning(GRJ3 — 도는 재판단이 읽은 근거와 화면이 어긋나지 않게). 같은 값을 다시 실음·다른 문장·표시·
     고침은 받는다

★ 갈아 넣기는 upsert 다(DELETE 없음 — 개정 1 B2): 보낸 itemIndex 는 INSERT·UPDATE, 보내지 않은 itemIndex 의 행은
  decision·사유를 NULL 로 UPDATE. 응답 marks 는 decision 이 있는 행만(itemIndex 오름).
★ 고침(G1b-3 — 꼴 머리말 contracts/review_shapes.py). 표시와 같은 행의 칸 셋 × 값·때·사람.
  - edits None(본문 생략·null) = 고침 쓰기 0. 목록 = 그 실행의 고침 전부 갈아 넣기 — 보내지 않은 itemIndex 의 고침 칸은
    NULL(행은 남김). marks 갈아 넣기는 고침 칸을, edits 갈아 넣기는 decision·사유를 건드리지 않는다.
  - 정규화: 저장 값은 strip 한 값(판정 사유는 항목마다, 빈 항목은 버림). AI 값(결과 items[i] 의 그 칸 — strip 하지
    않음)과 같으면 그 칸은 null(고침 없음). 상태·조기 반환은 정규화 뒤 고침으로 판단한다.
  - 칸마다 때·사람: 그 칸의 정규화 값이 앞과 다를 때만 now·actor 로, 같으면 앞 때·사람 그대로, null 로 돌아가면 셋 다
    NULL. UPDATE 는 바뀐 칸만 쓴다.
★ 감사: 고침만 바꾼 PUT 은 감사 0 줄이다(새 action 없음 — 발주서 G1b-3 처분 Q2 (나)). 고친 사람·때는 검토 행(표시 표의
  고침 칸)에 있다. adopt·exclude·confirm 갈래는 그대로.
★ 감사(MARC-ENT-295, 표는 발주서 §2-3): 새로 adopted(없음→채택·제외→채택) 문장마다 adopt — 단 확정 PUT 에서
  없음→채택은 확정 채우기와 같아 줄 0(B5). 새로 excluded 문장마다 exclude(사유 글은 싣지 않는다). 확정 PUT 에 confirm
  하나. 같은 값을 다시 보내거나 표시를 지운 것은 줄 0. 사유만 바꾼 제외(제외→제외)도 줄 0(MARC-ISSUE-220 (1), 처분 Q3).
  감사는 업무 블록의 **마지막 문장들**이다(record_event 는
  던지지 않고 자기 세이브포인트에서 실패를 받는다 — runs/service/actions/runs.py 의 꼴). 결과는 늘 success(거절은 행이
  남지 않는다).
★ 이름은 user 의 people_of(그 회사의 고객사 사용자와 운영 관리자 — MARC-ENT-374)로 확정자·칸마다 고친 사람을 모아
  한 번에 푼다. 못 풀면 「알 수 없는 사용자」(계약 name 은 빈 글자 금지).
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Final, Literal, cast

from django.db import transaction

from esgapi.core.auth.principal import Kind
from esgapi.core.calc.ai_settings import has_bad_chars
from esgapi.core.schemas import to_seoul_iso
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.core.service.services.audit import record_event
from esgapi.greenwash.contracts.rejudge_shapes import SHAPE as REJUDGE_SHAPE
from esgapi.greenwash.contracts.rejudge_shapes import GreenwashEvidenceAdded
from esgapi.greenwash.contracts.review_shapes import (
    SHAPE as REVIEW_SHAPE,
)
from esgapi.greenwash.contracts.review_shapes import (
    GreenwashRejudged,
    GreenwashRejudgeStatus,
    GreenwashReviewEdit,
    GreenwashReviewEditIn,
    GreenwashReviewer,
    GreenwashReviewEvidence,
    GreenwashReviewEvidenceIn,
    GreenwashReviewMark,
    GreenwashReviewRejudge,
    GreenwashReviewState,
    GreenwashReviewStateName,
)
from esgapi.greenwash.contracts.shapes import SHAPE as RESULT_SHAPE
from esgapi.greenwash.contracts.shapes import Level
from esgapi.greenwash.models import (
    EDIT_FIX_MAX_CHARS,
    EDIT_FIX_RAW_MAX_CHARS,
    EDIT_REASON_MAX_CHARS,
    EDIT_REASON_RAW_MAX_CHARS,
    EDIT_REASONS_MAX_LINES,
    EDIT_REASONS_RAW_MAX_LINES,
    EVIDENCE_ADDED_MAX_ITEMS,
    EVIDENCE_TEXT_MAX_CHARS,
    EVIDENCE_TEXT_RAW_MAX_CHARS,
    EXCLUDE_REASON_MAX_CHARS,
)
from esgapi.greenwash.service.selectors import review as selectors
from esgapi.greenwash.service.selectors.review import MarkRow
from esgapi.greenwash.service.services import review as services
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.selectors.runs import Run
from esgapi.user.service.selectors.user import people_of

MODULE = "greenwash"
UNKNOWN_USER = "알 수 없는 사용자"
LABEL_MAX = 255  # core_audit_events.target_label 의 길이


@dataclass(frozen=True, slots=True)
class NotFound:
    """실행이 없다(남의 회사·그린워싱 아닌 실행도 이 갈래)."""


@dataclass(frozen=True, slots=True)
class RunNotDone:
    status: str


@dataclass(frozen=True, slots=True)
class NoReview:
    """dry-run 실행이라 검토가 없다."""


@dataclass(frozen=True, slots=True)
class ReviewLocked:
    """확정된 실행이다."""


@dataclass(frozen=True, slots=True)
class RejudgeRunning:
    """그 문장(확정 PUT 이면 그 실행의 어느 문장)의 재판단이 대기·진행 중이다."""


@dataclass(frozen=True, slots=True)
class InvalidReview:
    message: str  # 사람에게 보일 한 문장


@dataclass(frozen=True, slots=True)
class Done:
    run: Run
    result: dict[str, object]


type Refusal = NotFound | RunNotDone | NoReview | ReviewLocked | RejudgeRunning | InvalidReview


def _done_run(company_id: int, run_id: int) -> Done | NotFound | RunNotDone:
    """규칙 1·2. 끝난 그린워싱 실행과 그 결과 본문."""
    run = run_selectors.find_run(company_id=company_id, run_id=run_id)
    if run is None or run.module != MODULE:
        return NotFound()
    if run.status != "done":
        return RunNotDone(run.status)
    results = run_selectors.run_results(company_id=company_id, run_id=run_id)
    body = next((r.body for r in results if r.schema_version == RESULT_SHAPE), None)
    if not isinstance(body, dict):  # 끝난 그린워싱 실행에는 늘 있다(흐름 report 단계) — 없으면 없는 실행으로
        return NotFound()
    return Done(run, body)  # pyright: ignore[reportUnknownArgumentType]


def run_result(*, company_id: int, run_id: int) -> dict[str, object] | NotFound | RunNotDone:
    found = _done_run(company_id, run_id)
    return found.result if isinstance(found, Done) else found


def _reviewable(company_id: int, run_id: int) -> Done | NotFound | RunNotDone | NoReview:
    """규칙 1·2·3."""
    found = _done_run(company_id, run_id)
    if isinstance(found, Done) and found.result.get("dryRun") is not None:
        return NoReview()
    return found


def _item_list(result: Mapping[str, object]) -> list[dict[str, Any]]:
    items = result.get("items")
    return cast("list[dict[str, Any]]", items) if isinstance(items, list) else []


# ── 기준 판단(GRJ1 — 꼴 머리말 contracts/review_shapes.py) ─────────────────────────────────

JUDGED_KEYS: Final = (
    "level",
    "riskTags",
    "confirmedInEvidence",
    "missingFields",
    "reasonBullets",
    "fixParagraph",
    "evidencePages",
)
"""판정이 내는 칸(결과 Item 과 재판단 결과 item 이 같이 갖는 칸). 기준 판단은 이 칸들만 바꾼다."""
RUNNING_STATUSES: Final = frozenset({"queued", "processing"})


@dataclass(frozen=True, slots=True)
class Basis:
    """문장 하나의 기준 판단. run_id None = 첫 판단(결과 items[i]), 값 = 그 재판단 실행."""

    run_id: int | None
    item: Mapping[str, Any]  # JUDGED_KEYS 칸. nonrisk 이면 level None
    outcome: Literal["judged", "nonrisk"]
    added: list[GreenwashEvidenceAdded]  # 그 판단에 보낸 더한 조각(첫 판단은 [])
    judged_at: datetime | None
    judged_by: int | None


@dataclass(frozen=True, slots=True)
class RejudgeLine:
    """문장 하나의 재판단 줄(재판단 실행이 하나라도 있는 문장만)."""

    status: GreenwashRejudgeStatus
    count: int


def first_basis(item: Mapping[str, Any]) -> Basis:
    return Basis(
        run_id=None,
        item={key: item.get(key) for key in JUDGED_KEYS},
        outcome="judged",
        added=[],
        judged_at=None,
        judged_by=None,
    )


def judgments(
    company_id: int, run_id: int, items: Sequence[Mapping[str, Any]], rows: Mapping[int, MarkRow]
) -> tuple[list[Basis], dict[int, RejudgeLine]]:
    """문장마다 기준 판단(items 차례)과 재판단 줄. 기준 = rejudge_run_ids 가운데 가장 늦게 만든 done 실행의 결과
    (rejudge@1 — 원 실행·문장이 맞는 것만), 없으면 첫 판단. 쿼리 = 실행 1·결과 1(재판단이 없으면 0)."""
    rejudges = {i: list(row.rejudge_run_ids) for i, row in rows.items() if row.rejudge_run_ids}
    return judgments_of(company_id, {run_id: (items, rejudges)})[run_id]


def judgments_of(
    company_id: int, wanted: Mapping[int, tuple[Sequence[Mapping[str, Any]], Mapping[int, Sequence[int]]]]
) -> dict[int, tuple[list[Basis], dict[int, RejudgeLine]]]:
    """judgments 의 여러 실행 판(목록 셈 checks.py 가 쓴다 — 규칙 한 벌). wanted = 원 실행 id → (items, itemIndex →
    재판단 실행 id 들). 쿼리 = 실행 1·결과 1(모든 원 실행을 합쳐 — 재판단이 없으면 0)."""
    picked = {
        run_id: {i: list(ids) for i, ids in rejudges.items() if ids and i < len(items)}
        for run_id, (items, rejudges) in wanted.items()
    }
    ids = [run for per_item in picked.values() for runs in per_item.values() for run in runs]
    found = run_selectors.runs_of(company_id=company_id, run_ids=ids) if ids else {}
    done = [run for run in ids if run in found and found[run].status == "done"]
    results = (
        run_selectors.results_of(company_id=company_id, run_ids=done, schema_versions=[REJUDGE_SHAPE]) if done else {}
    )
    out: dict[int, tuple[list[Basis], dict[int, RejudgeLine]]] = {}
    for run_id, (items, _rejudges) in wanted.items():
        bases = [first_basis(item) for item in items]
        lines: dict[int, RejudgeLine] = {}
        for index, runs in picked[run_id].items():
            latest = found.get(runs[-1])
            # 가장 늦은 재판단 실행의 행이 없으면(지워짐) 다시 돌 수 없다 → failed(GRS1 — MARC-ISSUE-633). 기준은 아래
            # 루프가 앞 done 그대로 둔다. 409 REJUDGE_RUNNING(만들기·검토 PUT·확정)은 이 status 를 읽는다.
            status: GreenwashRejudgeStatus = (
                "failed"
                if latest is None
                else "running"
                if latest.status in RUNNING_STATUSES
                else cast("GreenwashRejudgeStatus", latest.status)
            )
            count = 0
            for rejudge in runs:
                run = found.get(rejudge)
                body = next((r.body for r in results.get(rejudge, ()) if r.schema_version == REJUDGE_SHAPE), None)
                if run is None or run.status != "done" or not isinstance(body, dict):
                    continue
                judged = cast("dict[str, Any]", body)
                if judged.get("fromRunId") != run_id or judged.get("itemIndex") != index:
                    continue  # 다른 문장의 결과는 기준이 되지 못한다(쓰는 길이 막는다 — 그물)
                count += 1
                item = cast("dict[str, Any]", judged["item"])
                bases[index] = Basis(
                    run_id=rejudge,
                    item={key: item.get(key) for key in JUDGED_KEYS},
                    outcome=cast("Literal['judged', 'nonrisk']", judged["outcome"]),
                    added=list(judged["added"]),
                    judged_at=run.finished_at,
                    judged_by=run.created_by_user_id,
                )
            lines[index] = RejudgeLine(status=status, count=count)
        out[run_id] = (bases, lines)
    return out


def evidence_now(row: MarkRow | None, basis: Basis) -> tuple[list[int], list[GreenwashEvidenceAdded]]:
    """지금 유효한 근거 고침 (removed, added). removed 는 기준 판단이 그때와 같을 때만(감독 R3 안 C — 기준이 바뀌면
    옛 칩을 가리키므로 [])."""
    if row is None or row.evidence_added is None:
        return [], []
    removed = list(row.evidence_removed or []) if row.evidence_basis_run_id == basis.run_id else []
    return removed, cast("list[GreenwashEvidenceAdded]", list(row.evidence_added))


def nothing_to_rejudge(removed: Sequence[int], added: Sequence[GreenwashEvidenceAdded], basis: Basis) -> bool:
    """감독 R4: 지운 칩이 없고 더한 조각이 기준 판단에 보낸 것과 같으면 다시 판단할 것이 없다(웹 entities/greenwash
    model 의 같은 이름 함수와 같은 규칙)."""
    return not removed and list(added) == list(basis.added)


def _edits_of(rows: Mapping[int, MarkRow], names: Mapping[int, str]) -> list[GreenwashReviewEdit]:
    """고친 칸이 하나 이상인 행 → 응답 edits(itemIndex 오름). 칸마다 {value, editedAt, editedBy}."""

    def who(user_id: int | None) -> GreenwashReviewer:
        user = user_id if user_id is not None else 0
        return {"id": user, "name": names.get(user, UNKNOWN_USER)}

    def when(at: datetime | None) -> str:
        return to_seoul_iso(at) if at is not None else ""  # CHECK 가 값·때·사람을 같이 막는다

    edits: list[GreenwashReviewEdit] = []
    for index in sorted(rows):
        row = rows[index]
        if row.edited_level is None and row.edited_reason_bullets is None and row.edited_fix_paragraph is None:
            continue
        edits.append(
            {
                "itemIndex": index,
                "level": (
                    {
                        "value": cast("Level", row.edited_level),  # 표의 CHECK 가 셋으로 막는다
                        "editedAt": when(row.level_edited_at),
                        "editedBy": who(row.level_edited_by_user_id),
                    }
                    if row.edited_level is not None
                    else None
                ),
                "reasonBullets": (
                    {
                        "value": list(row.edited_reason_bullets),
                        "editedAt": when(row.reasons_edited_at),
                        "editedBy": who(row.reasons_edited_by_user_id),
                    }
                    if row.edited_reason_bullets is not None
                    else None
                ),
                "fixParagraph": (
                    {
                        "value": row.edited_fix_paragraph,
                        "editedAt": when(row.fix_edited_at),
                        "editedBy": who(row.fix_edited_by_user_id),
                    }
                    if row.edited_fix_paragraph is not None
                    else None
                ),
            }
        )
    return edits


def _people(rows: Mapping[int, MarkRow], confirmer: int | None, bases: Sequence[Basis]) -> set[int]:
    """확정자와 칸마다 고친 사람(값이 있는 칸만)·근거를 고친 사람·기준 판단의 재판단을 누른 사람."""
    found = {confirmer} if confirmer is not None else set[int]()
    for row in rows.values():
        for value, user in (
            (row.edited_level, row.level_edited_by_user_id),
            (row.edited_reason_bullets, row.reasons_edited_by_user_id),
            (row.edited_fix_paragraph, row.fix_edited_by_user_id),
            (row.evidence_added, row.evidence_edited_by_user_id),
        ):
            if value is not None and user is not None:
                found.add(user)
    found |= {basis.judged_by for basis in bases if basis.judged_by is not None}
    return found


def _who(names: Mapping[int, str], user_id: int | None) -> GreenwashReviewer:
    user = user_id if user_id is not None else 0
    return {"id": user, "name": names.get(user, UNKNOWN_USER)}


def _evidence_of(
    rows: Mapping[int, MarkRow], bases: Sequence[Basis], names: Mapping[int, str]
) -> list[GreenwashReviewEvidence]:
    """지금 유효한 근거 고침이 있는 문장 → 응답 evidence(itemIndex 오름)."""
    shown: list[GreenwashReviewEvidence] = []
    for index in sorted(rows):
        row = rows[index]
        if index >= len(bases) or row.evidence_added is None or row.evidence_edited_at is None:
            continue
        removed, added = evidence_now(row, bases[index])
        if not removed and not added:
            continue
        shown.append(
            {
                "itemIndex": index,
                "removed": removed,
                "added": added,
                "editedAt": to_seoul_iso(row.evidence_edited_at),
                "editedBy": _who(names, row.evidence_edited_by_user_id),
            }
        )
    return shown


def _rejudges_of(
    lines: Mapping[int, RejudgeLine], bases: Sequence[Basis], names: Mapping[int, str]
) -> list[GreenwashReviewRejudge]:
    shown: list[GreenwashReviewRejudge] = []
    for index in sorted(lines):
        basis = bases[index]
        current: GreenwashRejudged | None = None
        if basis.run_id is not None and basis.judged_at is not None:
            item = basis.item
            current = {
                "runId": basis.run_id,
                "judgedAt": to_seoul_iso(basis.judged_at),
                "judgedBy": _who(names, basis.judged_by),
                "outcome": basis.outcome,
                "level": item["level"],
                "riskTags": list(item["riskTags"]),
                "confirmedInEvidence": list(item["confirmedInEvidence"]),
                "missingFields": list(item["missingFields"]),
                "reasonBullets": list(item["reasonBullets"]),
                "fixParagraph": item["fixParagraph"],
                "evidencePages": list(item["evidencePages"]),
                "added": list(basis.added),
            }
        shown.append(
            {"itemIndex": index, "status": lines[index].status, "count": lines[index].count, "current": current}
        )
    return shown


def _state_of(company_id: int, run_id: int, items: Sequence[Mapping[str, Any]]) -> GreenwashReviewState:
    """검토 GET 의 몸. 쿼리 = 검토 1 · 표시 행 1 · 재판단 실행·결과 0~2 · 이름 0~1(고친 문장 수와 무관)."""
    review = selectors.find_review(company_id=company_id, run_id=run_id)
    rows = selectors.mark_rows(company_id=company_id, run_id=run_id)
    bases, lines = judgments(company_id, run_id, items, rows)
    marks: list[GreenwashReviewMark] = [
        {"itemIndex": index, "decision": row.decision, "excludeReason": row.exclude_reason}  # pyright: ignore[reportAssignmentType]
        for index, row in rows.items()
        if row.decision is not None
    ]
    confirmed = review is not None and review.confirmed_at is not None and review.confirmed_by_user_id is not None
    confirmer = review.confirmed_by_user_id if confirmed and review is not None else None
    wanted = _people(rows, confirmer, bases)
    found = people_of(company_id, wanted) if wanted else {}
    names = {user: found[user][1] for user in found if found[user][1].strip()}
    edits = _edits_of(rows, names)
    evidence = _evidence_of(rows, bases, names)
    rejudges = _rejudges_of(lines, bases, names)
    if review is None:
        return {
            "schemaVersion": REVIEW_SHAPE,
            "runId": run_id,
            "state": "pending",
            "confirmedAt": None,
            "confirmedBy": None,
            "marks": marks,
            "edits": edits,
            "evidence": evidence,
            "rejudges": rejudges,
        }
    return {
        "schemaVersion": REVIEW_SHAPE,
        "runId": run_id,
        "state": cast("GreenwashReviewStateName", review.state),  # 표의 CHECK 가 셋으로 막는다
        "confirmedAt": to_seoul_iso(review.confirmed_at) if review.confirmed_at is not None else None,
        "confirmedBy": (
            {"id": confirmer, "name": names.get(confirmer, UNKNOWN_USER)} if confirmer is not None else None
        ),
        "marks": marks,
        "edits": edits,
        "evidence": evidence,
        "rejudges": rejudges,
    }


def review_state(*, company_id: int, run_id: int) -> GreenwashReviewState | NotFound | RunNotDone | NoReview:
    found = _reviewable(company_id, run_id)
    if not isinstance(found, Done):
        return found
    return _state_of(company_id, run_id, _item_list(found.result))


def _checked_marks(marks: Sequence[GreenwashReviewMark], items: int) -> dict[int, services.Decision] | InvalidReview:
    """규칙 4. itemIndex → (decision, 사유)."""
    wanted: dict[int, services.Decision] = {}
    for mark in marks:
        index, decision, reason = mark["itemIndex"], mark["decision"], mark["excludeReason"]
        if not 0 <= index < items:
            return InvalidReview(f"문장 번호 {index}은(는) 이 결과에 없어요(0부터 {items - 1}까지)")
        if index in wanted:
            return InvalidReview(f"문장 번호 {index}이(가) 두 번 왔어요")
        if decision == "adopted" and reason is not None:
            return InvalidReview("채택한 문장에는 제외 사유를 넣지 않아요")
        if decision == "excluded":
            if reason is None or not reason.strip():
                return InvalidReview("제외한 문장에는 사유가 있어야 해요")
            if len(reason) > EXCLUDE_REASON_MAX_CHARS:
                return InvalidReview(f"제외 사유는 {EXCLUDE_REASON_MAX_CHARS}자까지 쓸 수 있어요")
        wanted[index] = (decision, reason)
    return wanted


Edit = tuple[str | None, list[str] | None, str | None]  # 정규화한 고침 (등급, 판정 사유, 수정 방향). None = AI 그대로


def _tidy_reasons(lines: Sequence[str]) -> list[str]:
    """판정 사유 다듬기: 줄마다 strip, 빈 줄은 버린다. 사람 값과 AI 값에 같이 쓴다."""
    return [line.strip() for line in lines if line.strip()]


def _tidy_fix(text: str) -> str:
    """수정 방향 다듬기: 앞뒤 공백을 지운다. 사람 값과 AI 값에 같이 쓴다."""
    return text.strip()


def _same_as_ai(value: object, ai: object) -> bool:
    """다듬은 사람 값이 같은 규칙으로 다듬은 AI 값과 같은가. AI 값이 None·꼴이 다르면 날것끼리 견준다."""
    if isinstance(value, list) and isinstance(ai, list) and all(isinstance(line, str) for line in cast(list[Any], ai)):
        return value == _tidy_reasons(cast(list[str], ai))
    if isinstance(value, str) and isinstance(ai, str):
        return value == _tidy_fix(ai)
    return value == ai


def _checked_edits(
    edits: Sequence[GreenwashReviewEditIn], items: Sequence[Mapping[str, Any]]
) -> dict[int, Edit] | InvalidReview:
    """규칙 4' 와 정규화. itemIndex → 정규화한 고침(AI 와 같은 칸은 None). 칸이 다 None 인 문장은 싣지 않는다."""
    wanted: dict[int, Edit] = {}
    seen: set[int] = set()
    count = len(items)
    for edit in edits:
        index = edit["itemIndex"]
        if not 0 <= index < count:
            return InvalidReview(f"문장 번호 {index}은(는) 이 결과에 없어요(0부터 {count - 1}까지)")
        if index in seen:
            return InvalidReview(f"고친 문장 번호 {index}이(가) 두 번 왔어요")
        seen.add(index)
        bullets: list[str] | None = None
        if edit["reasonBullets"] is not None:
            raw = edit["reasonBullets"]
            if len(raw) > EDIT_REASONS_RAW_MAX_LINES:
                return InvalidReview(f"판정 사유는 {EDIT_REASONS_MAX_LINES}줄까지 쓸 수 있어요")
            if any(len(line) > EDIT_REASON_RAW_MAX_CHARS for line in raw):
                return InvalidReview(f"판정 사유는 한 줄에 {EDIT_REASON_MAX_CHARS}자까지 쓸 수 있어요")
            bullets = _tidy_reasons(raw)
            if not bullets:
                return InvalidReview("판정 사유는 한 줄 이상 있어야 해요")
            if len(bullets) > EDIT_REASONS_MAX_LINES:
                return InvalidReview(f"판정 사유는 {EDIT_REASONS_MAX_LINES}줄까지 쓸 수 있어요")
            if any(len(line) > EDIT_REASON_MAX_CHARS for line in bullets):
                return InvalidReview(f"판정 사유는 한 줄에 {EDIT_REASON_MAX_CHARS}자까지 쓸 수 있어요")
        fix: str | None = None
        if edit["fixParagraph"] is not None:
            if len(edit["fixParagraph"]) > EDIT_FIX_RAW_MAX_CHARS:
                return InvalidReview(f"수정 방향은 {EDIT_FIX_MAX_CHARS}자까지 쓸 수 있어요")
            fix = _tidy_fix(edit["fixParagraph"])
            if not fix:
                return InvalidReview("수정 방향은 비워 둘 수 없어요")
            if len(fix) > EDIT_FIX_MAX_CHARS:
                return InvalidReview(f"수정 방향은 {EDIT_FIX_MAX_CHARS}자까지 쓸 수 있어요")
        ai = items[index]
        level = edit["level"] if edit["level"] != ai.get("level") else None
        bullets = None if bullets is None or _same_as_ai(bullets, ai.get("reasonBullets")) else bullets
        fix = None if fix is None or _same_as_ai(fix, ai.get("fixParagraph")) else fix
        if level is not None or bullets is not None or fix is not None:
            wanted[index] = (level, bullets, fix)
    return wanted


Evidence = tuple[list[int], list[GreenwashEvidenceAdded]]  # 정규화한 근거 고침 (removed, added). 둘 다 비면 고침 없음


def _page_count(result: Mapping[str, object]) -> int:
    source = result.get("source")
    count = cast("dict[str, object]", source).get("pageCount") if isinstance(source, dict) else None
    return count if isinstance(count, int) and not isinstance(count, bool) else 0


def _checked_evidence(
    evidence: Sequence[GreenwashReviewEvidenceIn], bases: Sequence[Basis], pages: int
) -> dict[int, Evidence] | InvalidReview:
    """근거 고침 검사(GRJ1)와 정규화. itemIndex → (removed 오름·겹침 없음, added strip). 둘 다 빈 문장은 싣지 않는다.
    removed 의 차례는 그 문장의 기준 판단 confirmedInEvidence 차례다."""
    wanted: dict[int, Evidence] = {}
    seen: set[int] = set()
    count = len(bases)
    for edit in evidence:
        index = edit["itemIndex"]
        if not 0 <= index < count:
            return InvalidReview(f"문장 번호 {index}은(는) 이 결과에 없어요(0부터 {count - 1}까지)")
        if index in seen:
            return InvalidReview(f"근거를 고친 문장 번호 {index}이(가) 두 번 왔어요")
        seen.add(index)
        chips = len(bases[index].item.get("confirmedInEvidence") or [])
        removed = sorted(set(edit["removed"]))
        if any(not 0 <= chip < chips for chip in removed):
            return InvalidReview(f"지운 근거 번호가 이 문장의 근거({chips}개) 밖이에요")
        if len(edit["added"]) > EVIDENCE_ADDED_MAX_ITEMS:
            return InvalidReview(f"근거는 문장마다 {EVIDENCE_ADDED_MAX_ITEMS}개까지 더할 수 있어요")
        added: list[GreenwashEvidenceAdded] = []
        for piece in edit["added"]:
            if len(piece["text"]) > EVIDENCE_TEXT_RAW_MAX_CHARS:
                return InvalidReview(f"더한 근거는 {EVIDENCE_TEXT_MAX_CHARS}자까지 쓸 수 있어요")
            # NUL·짝 없는 서로게이트는 jsonb 가 받지 않는다(MARC-ISSUE-289 의 꼴 — ④ M1)
            if has_bad_chars(piece["text"]):
                return InvalidReview("더한 근거에 쓸 수 없는 글자가 있어요")
            text = piece["text"].strip()
            if not text:
                return InvalidReview("더한 근거는 비워 둘 수 없어요")
            if len(text) > EVIDENCE_TEXT_MAX_CHARS:
                return InvalidReview(f"더한 근거는 {EVIDENCE_TEXT_MAX_CHARS}자까지 쓸 수 있어요")
            page = piece["page"]
            if page is not None and not 1 <= page <= pages:
                return InvalidReview(f"더한 근거의 페이지는 1부터 {pages}까지예요")
            added.append({"text": text, "page": page})
        if removed or added:
            wanted[index] = (removed, added)
    return wanted


def _evidence_columns(
    before: MarkRow, new: Evidence | None, basis: Basis, *, actor_user_id: int, now: datetime
) -> dict[str, Any]:
    """근거 고침 칸 다섯의 새 값. 지금 유효한 값과 같으면 앞 때·사람 그대로, 다르면 now·actor, 고침 없음이면 다 NULL.
    basis 칸은 늘 지금 기준 판단(removed 가 가리키는 판단)이다."""
    if new is None:
        return {
            "evidence_removed": None,
            "evidence_added": None,
            "evidence_edited_at": None,
            "evidence_edited_by_user_id": None,
            "evidence_basis_run_id": None,
        }
    removed, added = new
    same = evidence_now(before, basis) == (removed, added) and before.evidence_edited_at is not None
    return {
        "evidence_removed": removed,
        "evidence_added": added,
        "evidence_edited_at": before.evidence_edited_at if same else now,
        "evidence_edited_by_user_id": before.evidence_edited_by_user_id if same else actor_user_id,
        "evidence_basis_run_id": basis.run_id,
    }


EMPTY_ROW = MarkRow(None, None, None, None, None, None, None, None, None, None, None)


def _edited_columns(before: MarkRow, edit: Edit, *, actor_user_id: int, now: datetime) -> dict[str, Any]:
    """고침 칸 아홉의 새 값. 칸마다 값이 앞과 같으면 앞 때·사람 그대로, 다르면 now·actor, None 이면 셋 다 NULL."""
    level, bullets, fix = edit

    def column(new: object, old: object, at: datetime | None, by: int | None) -> tuple[Any, Any, Any]:
        if new is None:
            return None, None, None
        if new == old:
            return old, at, by
        return new, now, actor_user_id

    lv = column(level, before.edited_level, before.level_edited_at, before.level_edited_by_user_id)
    rs = column(bullets, before.edited_reason_bullets, before.reasons_edited_at, before.reasons_edited_by_user_id)
    fx = column(fix, before.edited_fix_paragraph, before.fix_edited_at, before.fix_edited_by_user_id)
    return {
        "edited_level": lv[0],
        "level_edited_at": lv[1],
        "level_edited_by_user_id": lv[2],
        "edited_reason_bullets": rs[0],
        "reasons_edited_at": rs[1],
        "reasons_edited_by_user_id": rs[2],
        "edited_fix_paragraph": fx[0],
        "fix_edited_at": fx[1],
        "fix_edited_by_user_id": fx[2],
    }


def _label(file_name: str, index: int | None) -> str:
    label = file_name if index is None else f"{file_name} · 문장 {index + 1}"
    return label[:LABEL_MAX]


AuditAction = Literal["adopt", "exclude"]


@transaction.atomic
def put_review(
    *,
    company_id: int,
    actor_kind: Kind,
    actor_user_id: int,
    run_id: int,
    confirm: bool,
    marks: Sequence[GreenwashReviewMark],
    edits: Sequence[GreenwashReviewEditIn] | None = None,
    evidence: Sequence[GreenwashReviewEvidenceIn] | None = None,
    now: datetime,
) -> GreenwashReviewState | Refusal:
    """검토 표시(와 고침·근거 고침)를 갈아 넣고 새 상태를 돌려준다. 차례는 머리말 그대로다. 거절은 쓰기 앞이라 행
    0 이다. 고침 정규화·근거 고침 검사는 기준 판단(재판단이 있으면 그 판단)과 견준다(GRJ1)."""
    found = _reviewable(company_id, run_id)
    if not isinstance(found, Done):
        return found
    review = selectors.lock_review(company_id=company_id, run_id=run_id)
    if review is not None and review.state == "confirmed":
        return ReviewLocked()
    ai_items = _item_list(found.result)
    items = len(ai_items)
    before = selectors.mark_rows(company_id=company_id, run_id=run_id)  # 잠근 뒤 읽는다(재판단 붙이기와 줄 선다)
    bases, lines = judgments(company_id, run_id, ai_items, before)
    wanted = _checked_marks(marks, items)
    if isinstance(wanted, InvalidReview):
        return wanted
    wanted_edits: dict[int, Edit] = {}
    if edits is not None:
        checked = _checked_edits(edits, [basis.item for basis in bases])
        if isinstance(checked, InvalidReview):
            return checked
        wanted_edits = checked
    wanted_evidence: dict[int, Evidence] = {}
    if evidence is not None:
        checked_evidence = _checked_evidence(evidence, bases, _page_count(found.result))
        if isinstance(checked_evidence, InvalidReview):
            return checked_evidence
        wanted_evidence = checked_evidence
    if review is None:
        # 규칙 6: 행이 없고 표시도 (정규화 뒤) 고침도 근거 고침도 확정도 없으면 만들지 않는다(읽기는 pending)
        if not wanted and not wanted_edits and not wanted_evidence and not confirm:
            return _state_of(company_id, run_id, ai_items)
        services.create_review(company_id=company_id, run_id=run_id)
        review = selectors.lock_review(company_id=company_id, run_id=run_id)
        if review is None:
            raise RuntimeError("방금 만든 greenwash_reviews 의 행이 없다")
        if review.state == "confirmed":  # 겹친 PUT 이 먼저 만들고 확정했다
            return ReviewLocked()
        # 규칙 7: 겹친 첫 PUT 이 먼저 만든 행을 잠근 뒤 다시 본다(낡은 before 로 INSERT 하면 유일 제약 500 — ④ B2).
        # 앞 검사는 그대로 맞다 — 행이 없던 실행에는 재판단도 없다(재판단 만들기는 근거 고침 행이 있어야 지난다)
        before = selectors.mark_rows(company_id=company_id, run_id=run_id)
        bases, lines = judgments(company_id, run_id, ai_items, before)
    if confirm and any(line.status == "running" for line in lines.values()):
        return RejudgeRunning()  # 규칙 8(④ B1)
    if evidence is not None:
        # 규칙 8(GRJ3): 재판단이 대기·진행 중인 문장의 근거를 지금 유효한 값과 다르게 바꾸면 거절
        # (같은 값을 다시 실은 PUT 은 받는다 — 웹은 evidence 를 전체로 싣는다)
        for index, line in lines.items():
            if (
                line.status == "running"
                and index < len(bases)
                and wanted_evidence.get(index, ([], [])) != evidence_now(before.get(index), bases[index])
            ):
                return RejudgeRunning()

    if confirm:
        for index in range(items):
            wanted.setdefault(index, ("adopted", None))
    inserts: dict[int, services.Columns] = {}
    updates: dict[int, services.Columns] = {}
    for index in sorted(set(before) | set(wanted) | set(wanted_edits) | set(wanted_evidence)):
        old = before.get(index, EMPTY_ROW)
        # 보내지 않은 표시 = 미검토(DELETE 없음). 고침은 edits 가 목록일 때만 갈아 넣는다
        decision, reason = wanted.get(index, (None, None))
        new = {**asdict(old), "decision": decision, "exclude_reason": reason}
        if edits is not None:
            new |= _edited_columns(
                old, wanted_edits.get(index, (None, None, None)), actor_user_id=actor_user_id, now=now
            )
        if evidence is not None and index < len(bases):
            new |= _evidence_columns(
                old, wanted_evidence.get(index), bases[index], actor_user_id=actor_user_id, now=now
            )
        if index not in before:
            inserts[index] = new
        else:
            columns = {name: value for name, value in new.items() if getattr(old, name) != value}
            if columns:
                updates[index] = columns
    services.write_marks(company_id=company_id, run_id=run_id, inserts=inserts, updates=updates)

    if confirm:
        services.set_state(
            company_id=company_id,
            run_id=run_id,
            state="confirmed",
            confirmed_at=now,
            confirmed_by_user_id=actor_user_id,
        )
    elif (wanted or wanted_edits or wanted_evidence) and review.state == "pending":
        services.set_state(
            company_id=company_id, run_id=run_id, state="in_review", confirmed_at=None, confirmed_by_user_id=None
        )

    changed: list[tuple[AuditAction, int]] = []
    for index in sorted(wanted):
        old = before.get(index, EMPTY_ROW).decision
        new = wanted[index][0]
        if new == old:
            continue
        if new == "adopted" and not (confirm and old is None):
            changed.append(("adopt", index))
        elif new == "excluded":
            changed.append(("exclude", index))
    state = _state_of(company_id, run_id, ai_items)
    document = (
        None
        if found.run.document_id is None
        else document_selectors.find_document(company_id=company_id, document_id=found.run.document_id)
    )
    file_name = document.file_name if document is not None else f"문서 {found.run.document_id}"
    # 감사 줄: 업무 블록의 마지막 문장들(머리말)
    for action, index in changed:
        record_event(
            at=now,
            company_id=company_id,
            actor_kind=actor_kind,
            actor_user_id=actor_user_id,
            action=action,
            event="greenwash_item_adopted" if action == "adopt" else "greenwash_item_excluded",
            result="success",
            target_kind="greenwash_item",
            target_id=run_id,
            target_label=_label(file_name, index),
        )
    if confirm:
        record_event(
            at=now,
            company_id=company_id,
            actor_kind=actor_kind,
            actor_user_id=actor_user_id,
            action="confirm",
            event="greenwash_review_confirmed",
            result="success",
            target_kind="run",
            target_id=run_id,
            target_label=_label(file_name, None),
        )
    return state


# 재판단 만들기(actions/rejudge.py)가 같은 규칙 1·2·3·항목 읽기·감사 이름표를 쓴다(GRJ1 — 규칙 한 벌)
reviewable = _reviewable
item_list = _item_list
label = _label
