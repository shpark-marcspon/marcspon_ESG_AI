"""목록 줄(GET /greenwash/checks — greenwash.checks@1). runs(실행·단계·결과)·core(문서)·user(이름·회사 이름)를 엮어
조립하므로 Action 이다(Service·Selector 는 남의 도메인을 import 하지 않는다 — `.importlinter` 계약 바).

    checks(company_id, user_id)   그 회사의 그린워싱 실행 전부와 그 문서들 → greenwash.checks@1

규칙(발주서 G1b §2-5, 꼴은 contracts/checks_shapes.py):
  - 실행은 module = greenwash 이고 흐름이 1차(greenwash.colab@E0)인 것만 — 2차 엔진(engine@G1)·재판단 실행은 0줄(GE1b
    ③ B1 — 검토·셈·단계·결과·문서·이름 읽기가 전부 이 거름 뒤). 문서는 그 실행들이 가리키는 것만(같은 회사 —
    문서도 회사 조건으로 읽는다).
  - 차례는 정하지 않는다(웹이 정렬한다). 실행은 runs 의 run_page 차례(새 것 먼저) 그대로.
  - levelCounts·review 는 끝난 실행만. dry-run 실행(결과 dryRun 칸이 값)은 review null.
  - levelCounts 는 효력 등급(고친 등급 ?? 기준 판단 ?? 첫 AI 등급)으로 센 결과 items 전부다 — 결과 counts.byLevel 에서
    등급을 고쳤거나 재판단이 기준이 된 문장마다 첫 등급 −1·효력 등급 +1(G1b-3, 디자인 80 Q8 · GRJ1). 효력이 「리스크
    아님」(재판단 nonrisk·고친 등급 없음)이면 −1 만(세 칸 합 < 문장 수 — 감독 R5). review.reviewed 는 그대로.
  - finishedAt 은 Run.finished_at 그대로 +09:00 글자(done·failed 로 끝났을 때 값, 그 밖 null — GCB1, 목록 「AI점검
    완료 일자」). 이웃 시각 칸(createdAt)처럼 글자 칸이라 openapi date-time 셈 밖이다. 쿼리 0 더함(run_page 의 Run).
  - errorCode 는 failed 실행만 Run.error_code 그대로, 그 밖 null(남은 값이 있어도 — 밴드 G1e 상태 가드).
  - failedPageCount 는 끝난 실행 결과 candidateStats.failedPages 의 수(빈 목록 → 0). 끝나지 않음·dry-run 결과
    (candidateStats null)·결과 없음·꼴 어긋남은 null(G1b-2b, 감독 처분 Q5 (가)). 아래 묶음 결과 읽기의 같은 본문에서.
  - pageCount 는 그 문서의 끝난 실행 결과 source.pageCount(새 실행 먼저). reportYear·previousDocumentId 는 문서의
    칸 그대로(PATCH /documents/{id} — X1b-2a. G1b-2a, 감독 처분 Q11·J2 (가)).
★ 쿼리 수(G1b-2b — MARC-ISSUE-219): 실행 1개 이상에서 실행 수와 무관한 상수 k = 회사 이름 1 · 실행 쪽 2(줄·수) ·
  검토 2 · 단계 1 · 결과 1 · 문서 1 · 이름 1(= 9). 재판단이 있는 실행이 하나라도 있으면 +2(재판단 실행 1·결과 1 —
  GRJ1, 실행 수와 무관). 실행 0 이면 묶음 읽기·검토·이름 읽기가 쿼리를 내지 않아 더 적다.
  단계·결과·문서는 묶음 읽기(runs 의 step_rows_of·results_of, core 의 documents_of) 하나씩 — 실행마다·문서마다 읽지
  않는다. 업무 시험이 실행 1개와 5개에서 같은 수를 잰다.
★ 실행은 RUNS_MAX 까지(새 것 먼저 — 묶음 읽기 입력의 상한도 이것). 넘으면 오래된 것이 빠지고 truncated 가 true 다
  (G1b-2b, 감독 처분 Q4) — 페이지네이션은 후속.
"""

from collections.abc import Mapping, Sequence
from typing import cast

from esgapi.core.schemas import to_seoul_iso
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.greenwash.contracts.checks_shapes import (
    SHAPE,
    GreenwashCheckDocument,
    GreenwashCheckReview,
    GreenwashCheckRun,
    GreenwashCheckRunStatus,
    GreenwashChecks,
    GreenwashCheckStep,
    GreenwashCheckStepStatus,
)
from esgapi.greenwash.contracts.review_shapes import GreenwashReviewStateName
from esgapi.greenwash.contracts.shapes import SHAPE as RESULT_SHAPE
from esgapi.greenwash.contracts.shapes import Level, LevelCounts
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.service.actions import review as review_actions
from esgapi.greenwash.service.selectors import review as review_selectors
from esgapi.greenwash.service.selectors.run_extras import review_shown
from esgapi.organization.service.selectors.organization import company_name
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.selectors.runs import Run, RunResult
from esgapi.user.service.selectors.user import people_of

MODULE = "greenwash"
UNKNOWN_USER = "알 수 없는 사용자"
RUNS_MAX = 1000


def _checked_pages(options: Mapping[str, object]) -> int:
    """옵션 parts 셋의 합집합 수. 꼴이 어긋난 값은 세지 않는다(끼움이 만들 때 이미 검사했다)."""
    parts = options.get("parts")
    pages: set[int] = set()
    if isinstance(parts, dict):
        for value in cast("dict[str, object]", parts).values():
            if isinstance(value, list):
                pages |= {p for p in cast("list[object]", value) if isinstance(p, int) and not isinstance(p, bool)}
    return len(pages)


def _result_of(run: Run, results: Mapping[int, tuple[RunResult, ...]]) -> dict[str, object] | None:
    """끝난 실행의 결과 본문(묶음 읽기 results 에서). 끝나지 않았거나 없으면 None."""
    if run.status != "done":
        return None
    body = next((r.body for r in results.get(run.id, ()) if r.schema_version == RESULT_SHAPE), None)
    return cast("dict[str, object]", body) if isinstance(body, dict) else None


def _level_counts(result: Mapping[str, object]) -> LevelCounts | None:
    counts = result.get("counts")
    if not isinstance(counts, dict):
        return None  # dry-run 결과는 counts 가 null 이다
    by_level = cast("dict[str, object]", counts).get("byLevel")
    if not isinstance(by_level, dict):
        return None
    levels = cast("dict[str, int]", by_level)
    return {"High": levels["High"], "Mid": levels["Mid"], "Low": levels["Low"]}


def effective_level_counts(
    result: Mapping[str, object],
    edited_levels: Mapping[int, str],
    basis_levels: Mapping[int, str | None] | None = None,
) -> LevelCounts | None:
    """결과의 등급별 수를 효력 등급(고친 등급 ?? 기준 판단 ?? 첫 판단)으로(머리말). edited_levels = itemIndex → 고친
    등급, basis_levels = 재판단이 기준이 된 itemIndex → 그 등급(None = 리스크 아님 — 세 칸 어디에도 세지 않는다,
    감독 R5). 결과 밖 itemIndex 는 세지 않는다."""
    counts = _level_counts(result)
    items = result.get("items")
    if counts is None or not isinstance(items, list):
        return counts
    items = cast("list[dict[str, object]]", items)
    basis = basis_levels or {}
    for index in sorted(set(edited_levels) | set(basis)):
        if not 0 <= index < len(items):
            continue
        now = edited_levels[index] if index in edited_levels else basis[index]
        counts[cast("Level", items[index]["level"])] -= 1
        if now is not None:
            counts[cast("Level", now)] += 1
    return counts


def _basis_levels(
    company_id: int,
    runs: Sequence[Run],
    results: Mapping[int, tuple[RunResult, ...]],
    tallies: Mapping[int, review_selectors.MarkTally],
) -> dict[int, dict[int, str | None]]:
    """재판단이 기준이 된 문장의 등급(실행 id → itemIndex → 등급, None = 리스크 아님). 검토 GET 과 같은 규칙
    (actions/review.judgments_of — 한 벌). 재판단 있는 실행이 없으면 쿼리 0, 있으면 실행 1·결과 1(실행 수와 무관)."""
    wanted: dict[int, tuple[list[dict[str, object]], dict[int, list[int]]]] = {}
    for run in runs:
        tally = tallies.get(run.id)
        result = _result_of(run, results)
        if tally is None or not tally.rejudges or result is None or not isinstance(result.get("items"), list):
            continue
        wanted[run.id] = (cast("list[dict[str, object]]", result["items"]), tally.rejudges)
    if not wanted:
        return {}
    judged = review_actions.judgments_of(company_id, wanted)
    return {
        run_id: {i: basis.item.get("level") for i, basis in enumerate(bases) if basis.run_id is not None}
        for run_id, (bases, _lines) in judged.items()
    }


def _failed_page_count(result: Mapping[str, object] | None) -> int | None:
    """결과 candidateStats.failedPages 의 수. candidateStats 가 dict 가 아니거나(dry-run 은 null) failedPages 가 목록이
    아니면 None."""
    stats = result.get("candidateStats") if result is not None else None
    if not isinstance(stats, dict):
        return None
    failed = cast("dict[str, object]", stats).get("failedPages")
    return len(cast("list[object]", failed)) if isinstance(failed, list) else None


def _items(result: Mapping[str, object]) -> int:
    items = result.get("items")
    return len(cast("list[object]", items)) if isinstance(items, list) else 0


def _page_count(result: Mapping[str, object]) -> int | None:
    source = result.get("source")
    if not isinstance(source, dict):
        return None
    value = cast("dict[str, object]", source).get("pageCount")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _user_id(uploaded_by: str) -> int | None:
    """문서 uploaded_by 는 세션 주체 id 의 십진 글자다(core 의 문서 경로). 아니면 None."""
    return int(uploaded_by) if uploaded_by.isdecimal() else None


def checks(*, company_id: int, user_id: int) -> GreenwashChecks:
    page = run_selectors.run_page(
        company_id=company_id, module=MODULE, status=None, document_id=None, limit=RUNS_MAX, offset=0
    )
    # X1b-2a: run_page 줄은 (Run, 문서 이름) · GE1b ③: 1차 흐름만(2차 엔진 결과 본문·문서 줄을 읽지 않는다)
    runs = tuple(run for run, _document_name in page.runs if run.flow_id == colab.FLOW_ID)
    reviews = review_selectors.reviews_of(company_id=company_id, run_ids={r.id for r in runs})
    tallies = review_selectors.mark_tallies(company_id=company_id, run_ids={r.id for r in runs})
    step_rows = run_selectors.step_rows_of(company_id=company_id, run_ids=[r.id for r in runs])
    results = run_selectors.results_of(company_id=company_id, run_ids=[r.id for r in runs if r.status == "done"])
    basis_levels = _basis_levels(company_id, runs, results, tallies)

    run_rows: list[GreenwashCheckRun] = []
    page_counts: dict[int, int] = {}  # 문서 id → 쪽 수(새 실행 먼저 — 처음 본 값)
    for run in runs:
        if run.document_id is None:  # 문서 없는 실행은 그린워싱에 없다(ND1)
            continue
        steps: list[GreenwashCheckStep] = [
            {
                "step": s.name,
                "status": cast("GreenwashCheckStepStatus", s.status),  # runs 의 단계 상태 넷(RunStepStatus)
                "done": s.done,
                "total": s.total,
            }
            for s in step_rows.get(run.id, ())
        ]
        result = _result_of(run, results)
        level_counts: LevelCounts | None = None
        review: GreenwashCheckReview | None = None
        if result is not None:
            tally = tallies.get(run.id)
            level_counts = effective_level_counts(
                result, tally.edited_levels if tally is not None else {}, basis_levels.get(run.id)
            )
            pages = _page_count(result)
            if pages is not None:
                page_counts.setdefault(run.document_id, pages)
            if review_shown(run.status, result):
                found = reviews.get(run.id)
                confirmed_at = found.confirmed_at if found is not None else None
                review = {
                    "state": cast("GreenwashReviewStateName", found.state) if found is not None else "pending",
                    "reviewed": tally.decided if tally is not None else 0,
                    "total": _items(result),
                    "confirmedAt": to_seoul_iso(confirmed_at) if confirmed_at is not None else None,
                    "confirmedBy": None,  # 이름은 아래에서 한 번에 푼다
                }
        run_rows.append(
            {
                "runId": run.id,
                "documentId": run.document_id,
                "createdAt": to_seoul_iso(run.created_at),
                "finishedAt": None if run.finished_at is None else to_seoul_iso(run.finished_at),
                "createdByUserId": run.created_by_user_id,
                "status": cast("GreenwashCheckRunStatus", run.status),
                "errorCode": run.error_code if run.status == "failed" else None,
                "failedPageCount": _failed_page_count(result),
                "steps": steps,
                "checkedPages": _checked_pages(run.options),
                "levelCounts": level_counts,
                "review": review,
            }
        )

    wanted_documents = list(
        dict.fromkeys(r.document_id for r in runs if r.document_id is not None)
    )  # 처음 본 차례(새 실행 먼저)
    found_documents = document_selectors.documents_of(company_id=company_id, document_ids=wanted_documents)
    documents = [found_documents[d] for d in wanted_documents if d in found_documents]
    uploaders = {d.id: _user_id(d.uploaded_by) for d in documents}
    confirmers = {
        run.id: found.confirmed_by_user_id
        for run in runs
        if (found := reviews.get(run.id)) is not None and found.confirmed_by_user_id is not None
    }
    wanted = {u for u in uploaders.values() if u is not None} | set(confirmers.values())
    names = people_of(company_id, wanted) if wanted else {}

    def name(user: int | None) -> str:
        found = names.get(user) if user is not None else None
        return found[1] if found is not None and found[1].strip() else UNKNOWN_USER

    for row in run_rows:
        confirmer = confirmers.get(row["runId"])
        if row["review"] is not None and confirmer is not None:
            row["review"]["confirmedBy"] = {"id": confirmer, "name": name(confirmer)}

    document_rows: list[GreenwashCheckDocument] = [
        {
            "documentId": d.id,
            "fileName": d.file_name,
            "reportYear": d.report_year,
            "previousDocumentId": d.previous_document_id,
            "pageCount": page_counts.get(d.id),
            "uploadedAt": to_seoul_iso(d.uploaded_at) if d.uploaded_at is not None else None,
            "uploadedBy": {"userId": uploaders[d.id] or 0, "name": name(uploaders[d.id])},
        }
        for d in documents
    ]
    return {
        "schemaVersion": SHAPE,
        "currentUserId": user_id,
        "companyName": company_name(company_id),
        "documents": document_rows,
        "runs": run_rows,
        "truncated": page.count > RUNS_MAX,
    }
