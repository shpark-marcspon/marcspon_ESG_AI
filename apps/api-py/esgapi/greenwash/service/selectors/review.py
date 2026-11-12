"""읽기. 검토(표 greenwash_reviews)와 표시(greenwash_review_marks). 쓰지 않는다. 그린워싱의 표만 읽는다 — 실행·결과는
actions 가 runs 의 selector 로 읽는다.

    find_review(company_id, run_id)    검토 하나(Review). 없으면 None. 잠그지 않는다
    lock_review(company_id, run_id)    검토 행을 FOR UPDATE 로 읽는다(변경 트랜잭션 안에서만)
    decided_marks(company_id, run_id)  decision 이 있는 표시(itemIndex 오름) — 응답·목록 셈·감사가 보는 것
    mark_rows(company_id, run_id)      표시 행 전부(decision NULL·고침만 있는 행 포함) itemIndex → 행 값(MarkRow —
                                       decision·사유·고침 칸 셋 × 값·때·사람·근거 고침·재판단 실행 id(GRJ1)) — 검토
                                       GET·갈아 넣기의 앞 상태·확정본 엑셀
    reviews_of(company_id, run_ids)    실행 여럿의 검토(run_id → Review) — 목록 줄, 쿼리 하나
    mark_tallies(company_id, run_ids)  실행 여럿의 표시 셈(run_id → MarkTally: decision 이 있는 표시 수·고친 등급
                                       itemIndex → 등급·재판단 id 들) — 목록 줄, 쿼리 하나(G1b-3 — 옛 decided_counts
                                       를 넓힘 · GRJ1 재판단 id)
    bundle_review_rows(company_id, run_ids)
                                       실행 묶음(RX1b)이 싣는 검토·표시 행(BundleReviewRows) — 사람 칸·id·회사 칸
                                       없이, created_at·updated_at 은 함께(쿼리 둘)

★ 조회마다 회사 조건을 적는다(<표>.for_company(company_id) — core/tests/test_selector_scope.py). 남의 회사 실행 id 는
  「없음」과 같다.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from django.db.models import Q

from esgapi.greenwash.models import GreenwashReviewMarkRow, GreenwashReviewRow


@dataclass(frozen=True, slots=True)
class Review:
    id: int
    run_id: int
    state: str
    confirmed_at: datetime | None
    confirmed_by_user_id: int | None


@dataclass(frozen=True, slots=True)
class MarkRow:
    """표시 행 하나의 값. 칸 이름은 표의 칸 이름 그대로다(actions 가 바뀐 칸만 골라 services 에 넘긴다)."""

    decision: str | None
    exclude_reason: str | None
    edited_level: str | None
    level_edited_at: datetime | None
    level_edited_by_user_id: int | None
    edited_reason_bullets: list[str] | None
    reasons_edited_at: datetime | None
    reasons_edited_by_user_id: int | None
    edited_fix_paragraph: str | None
    fix_edited_at: datetime | None
    fix_edited_by_user_id: int | None
    # 근거 고침·재판단(GRJ1 — 마이그레이션 0007). 기본값 None 은 옛 꼴로 짓는 자리(시험·EMPTY_ROW)를 위해서다
    evidence_removed: list[int] | None = None
    evidence_added: list[dict[str, object]] | None = None
    evidence_edited_at: datetime | None = None
    evidence_edited_by_user_id: int | None = None
    evidence_basis_run_id: int | None = None
    rejudge_run_ids: list[int] | None = None


@dataclass(frozen=True, slots=True)
class MarkTally:
    """목록 줄 한 실행의 표시 셈. decided = decision 이 있는 표시 수, edited_levels = 등급을 고친 itemIndex → 고친
    등급."""

    decided: int
    edited_levels: dict[int, str]
    rejudges: dict[int, list[int]]
    """재판단이 있는 itemIndex → 그 재판단 실행 id 들(요청 차례 — rejudge_run_ids 그대로, GRJ1). 기준 판단은
    actions/review.judgments_of 가 고른다."""


@dataclass(frozen=True, slots=True)
class Mark:
    item_index: int
    decision: str
    exclude_reason: str | None


def review_of(row: GreenwashReviewRow) -> Review:
    return Review(
        id=row.id,
        run_id=row.run_id,
        state=row.state,
        confirmed_at=row.confirmed_at,
        confirmed_by_user_id=row.confirmed_by_user_id,
    )


def find_review(*, company_id: int, run_id: int) -> Review | None:
    row = GreenwashReviewRow.for_company(company_id).filter(run_id=run_id).first()
    return None if row is None else review_of(row)


def lock_review(*, company_id: int, run_id: int) -> Review | None:
    """그 회사의 그 실행의 검토 행을 FOR UPDATE 로 읽는다. 트랜잭션 밖이면 Django 가 던진다."""
    row = GreenwashReviewRow.for_company(company_id).select_for_update().filter(run_id=run_id).first()
    return None if row is None else review_of(row)


def decided_marks(*, company_id: int, run_id: int) -> tuple[Mark, ...]:
    rows = (
        GreenwashReviewMarkRow.for_company(company_id)
        .filter(run_id=run_id, decision__isnull=False)
        .order_by("item_index")
    )
    return tuple(Mark(item_index=r.item_index, decision=str(r.decision), exclude_reason=r.exclude_reason) for r in rows)


def mark_rows(*, company_id: int, run_id: int) -> dict[int, MarkRow]:
    rows = GreenwashReviewMarkRow.for_company(company_id).filter(run_id=run_id).order_by("item_index")
    return {
        r.item_index: MarkRow(
            decision=r.decision,
            exclude_reason=r.exclude_reason,
            edited_level=r.edited_level,
            level_edited_at=r.level_edited_at,
            level_edited_by_user_id=r.level_edited_by_user_id,
            edited_reason_bullets=r.edited_reason_bullets,
            reasons_edited_at=r.reasons_edited_at,
            reasons_edited_by_user_id=r.reasons_edited_by_user_id,
            edited_fix_paragraph=r.edited_fix_paragraph,
            fix_edited_at=r.fix_edited_at,
            fix_edited_by_user_id=r.fix_edited_by_user_id,
            evidence_removed=r.evidence_removed,
            evidence_added=r.evidence_added,
            evidence_edited_at=r.evidence_edited_at,
            evidence_edited_by_user_id=r.evidence_edited_by_user_id,
            evidence_basis_run_id=r.evidence_basis_run_id,
            rejudge_run_ids=r.rejudge_run_ids,
        )
        for r in rows
    }


def reviews_of(*, company_id: int, run_ids: Collection[int]) -> dict[int, Review]:
    rows = GreenwashReviewRow.for_company(company_id).filter(run_id__in=list(run_ids))
    return {row.run_id: review_of(row) for row in rows}


def mark_tallies(*, company_id: int, run_ids: Collection[int]) -> dict[int, MarkTally]:
    rows = (
        GreenwashReviewMarkRow.for_company(company_id)
        .filter(
            Q(decision__isnull=False) | Q(edited_level__isnull=False) | Q(rejudge_run_ids__isnull=False),
            run_id__in=list(run_ids),
        )
        .values_list("run_id", "item_index", "decision", "edited_level", "rejudge_run_ids")
    )
    decided: dict[int, int] = {}
    edited: dict[int, dict[int, str]] = {}
    rejudges: dict[int, dict[int, list[int]]] = {}
    for run_id, item_index, decision, edited_level, rejudge_run_ids in rows:
        decided.setdefault(run_id, 0)
        edited.setdefault(run_id, {})
        rejudges.setdefault(run_id, {})
        if decision is not None:
            decided[run_id] += 1
        if edited_level is not None:
            edited[run_id][item_index] = edited_level
        if rejudge_run_ids:
            rejudges[run_id][item_index] = [int(i) for i in rejudge_run_ids]
    return {
        run_id: MarkTally(decided=decided[run_id], edited_levels=edited[run_id], rejudges=rejudges[run_id])
        for run_id in decided
    }


REVIEW_BUNDLE_FIELDS = ("run_id", "state", "confirmed_at", "created_at", "updated_at")
MARK_BUNDLE_FIELDS = (
    "run_id",
    "item_index",
    "decision",
    "exclude_reason",
    "edited_level",
    "level_edited_at",
    "edited_reason_bullets",
    "reasons_edited_at",
    "edited_fix_paragraph",
    "fix_edited_at",
    "evidence_removed",
    "evidence_added",
    "evidence_edited_at",
    "evidence_basis_run_id",
    "rejudge_run_ids",
    "created_at",
    "updated_at",
)


@dataclass(frozen=True, slots=True)
class BundleReviewRows:
    """실행 묶음의 검토·표시 행(칸 이름 → 값). 사람 칸(confirmed_by·*_edited_by)·id·회사 칸은 싣지 않는다 — 넣는 쪽이
    때가 있는 칸의 사람을 --user 로 채운다(RX1b Qb3)."""

    reviews: list[dict[str, object]]
    marks: list[dict[str, object]]


def bundle_review_rows(*, company_id: int, run_ids: Collection[int]) -> BundleReviewRows:
    ids = list(run_ids)
    reviews = GreenwashReviewRow.for_company(company_id).filter(run_id__in=ids).order_by("run_id")
    marks = GreenwashReviewMarkRow.for_company(company_id).filter(run_id__in=ids).order_by("run_id", "item_index")
    return BundleReviewRows(
        reviews=[dict(row) for row in reviews.values(*REVIEW_BUNDLE_FIELDS)],
        marks=[dict(row) for row in marks.values(*MARK_BUNDLE_FIELDS)],
    )
