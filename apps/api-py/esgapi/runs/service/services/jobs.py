"""일감(표 run_jobs)을 워커가 잡고 끝내는 쓰기. HTTP 도 Celery 도 모른다.

    claim_job(company_id, job_id, now, lease_s, max_attempts)  잡기: 행을 잠그고(FOR UPDATE) 판정한 뒤 `processing` 으로
    finish_job(company_id, job_id, attempt, now, outcome)     끝내기: `done`·`failed` 로, 또는 임대를 당겨 두기

읽기는 여기 없다. 전부 Selector 를 부른다(잠가 읽기 lock_job·하나 읽기 find_job·다시 넣을 것 고르기 stale_jobs 는
runs/service/selectors/jobs.py, find_document 는 core/service/selectors/documents.py). 이 파일이 표에 직접 하는 것은
쓰기뿐이다.

결과는 예외가 아니라 갈래로 돌려준다. 판정의 규칙은 core/calc/jobs.py(순수)에 있다.
**트랜잭션 안에서** 부른다(워커는 transaction.atomic(durable=True) 블록). 밖이면 던진다.
회사는 인자로 받는다: 읽기(Selector)와 쓰기의 조건마다 그 회사로 연다(<Row>.for_company). 회사 범위 표의 기본
매니저는 회사를 정하지 않은 조회를 거절한다(core/isolation). DB 의 RLS 는 없다.
남의 일감은 0행 → JobNotFound.

★ 중복은 큐가 아니라 여기서 막는다. 같은 일감의 쪽지가 여러 번 와도:
  - 잡기는 행을 잠근 뒤 상태와 임대를 본다. 끝난 일감·남이 쥔 일감은 잡지 않는다.
  - **일감의 갱신에는 늘 `status` 와 `attempts` 조건이 있다**(울타리 표시). 끝내기의 조건은
    「`processing` 이고 attempts 가 내 시도」다. 임대가 끝나 다른 워커가 이어받았으면(attempts 가 늘었다) 0행이고
    Superseded 다: 먼저 잡았던 워커는 늦게 쓰지 못한다.
  - 갱신한 행 수를 본다. 잡기에서 1 이 아니거나, 끝내기에서 2 이상이거나, 문서의 sha256 갱신이 1 이 아니면
    JobUpdateError 다(트랜잭션이 되돌려진다).

★ 한 번만 「끝난다」이지 한 번만 「돈다」가 아니다: 임대가 끝난 뒤 이어받으면 저장소·파서가 두 번 불릴 수 있다.

★ 일감은 남의 회사 문서에 걸리지 않는다: DB 의 같은 회사 외래 키(company_id, document_id) → core_documents
  (company_id, id) 가 그런 행을 거절한다(runs/migrations/0001, 받침 ⑤ — core/isolation/foreign_keys.py). 그래서 잡기의
  document_missing 과 끝내기의 「문서 갱신 0행 → JobUpdateError」 갈래는 지금 닿는 길이 없다. 방어로 남긴다.
"""

from dataclasses import dataclass
from datetime import datetime

from django.db import connection
from django.db.models import QuerySet

from esgapi.core.calc import jobs as rules
from esgapi.core.calc.jobs import (
    MAX_ERROR_CODE_CHARS,
    MAX_ERROR_MESSAGE_CHARS,
    AlreadyFinished,
    Exhausted,
    LeaseHeld,
    Take,
    lease_until,
)
from esgapi.core.models import DocumentRow
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.core.service.selectors.documents import Document, Job, job_of
from esgapi.runs.models import JobRow
from esgapi.runs.service.selectors import jobs as selectors
from esgapi.runs.service.selectors.jobs import NotInTransactionError


class JobUpdateError(Exception):
    """갱신한 행 수가 맞지 않는다. 조용히 넘어가지 않는다. 부른 쪽의 트랜잭션이 되돌려진다.

    태스크는 이것을 잡지 않는다: Celery 는 다시 하지 않고(쪽지는 ack 된다) 행은 `processing` 으로 남는다.
    임대가 끝난 뒤 다시 넣으면 다시 잡히고, 시도 상한에서 `failed`·attempts_exhausted 로 끝난다.
    """


# ── 잡기 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Claimed:
    job: Job  # 잡은 뒤의 모습(`processing`, attempts = attempt)
    document: Document
    attempt: int


@dataclass(frozen=True, slots=True)
class JobNotFound:
    """그런 일감이 없다. 다른 회사의 일감도 이 갈래다."""


@dataclass(frozen=True, slots=True)
class DocumentMissing:
    """일감이 가리키는 문서가 이 회사에 보이지 않는다. 일감을 `failed`·document_missing 으로 끝냈다."""


ClaimResult = Claimed | JobNotFound | AlreadyFinished | LeaseHeld | Exhausted | DocumentMissing


def _require_transaction(name: str) -> None:
    if not connection.in_atomic_block:
        raise NotInTransactionError(f"{name} 는 transaction.atomic() 안에서만 부른다")


def _fail(guard: "QuerySet[JobRow]", *, code: str, message: str, now: datetime) -> int:
    return guard.update(
        status="failed",
        error_code=code[:MAX_ERROR_CODE_CHARS],
        error_message=message[:MAX_ERROR_MESSAGE_CHARS],
        finished_at=now,
        lease_expires_at=None,
        updated_at=now,
    )


def claim_job(*, company_id: int, job_id: int, now: datetime, lease_s: int, max_attempts: int) -> ClaimResult:
    """일감 하나를 잡는다. 차례: ① FOR UPDATE 로 읽는다 → ② 판정 → ③ 읽은 상태·시도를 조건으로 갱신한다.

    잡으면 `processing`·attempts+1·임대 = now + lease_s. 시도를 다 썼으면 `failed`·attempts_exhausted 로 끝낸다.
    """
    _require_transaction("claim_job")
    row = selectors.lock_job(company_id=company_id, job_id=job_id)  # ①
    if row is None:
        return JobNotFound()
    # 판정은 부를 때 모듈 속성으로 읽는다(테스트가 두 연결의 경합을 맞추려고 여기에 장벽을 끼운다).
    decision = rules.claim_decision(job_of(row).status, row.lease_expires_at, row.attempts, now, max_attempts)  # ②
    if isinstance(decision, AlreadyFinished | LeaseHeld):
        return decision

    # ③ 울타리: 내가 읽은 상태와 시도 그대로일 때만 쓴다.
    guard = JobRow.for_company(company_id).filter(pk=job_id, status=row.status, attempts=row.attempts)
    if isinstance(decision, Exhausted):
        updated = _fail(guard, code="attempts_exhausted", message=f"시도 {row.attempts}번을 다 썼다", now=now)
        if updated != 1:
            raise JobUpdateError(f"run_jobs 의 갱신이 {updated}행이다(1행이어야 한다)")
        return decision

    document = document_selectors.find_document(company_id=company_id, document_id=row.document_id)
    if document is None:
        updated = _fail(guard, code="document_missing", message="일감의 문서가 이 회사에 없다", now=now)
        if updated != 1:
            raise JobUpdateError(f"run_jobs 의 갱신이 {updated}행이다(1행이어야 한다)")
        return DocumentMissing()

    assert isinstance(decision, Take)  # noqa: S101  (갈래를 다 걸렀다. 타입 검사기에게 알린다)
    updated = guard.update(
        status="processing",
        attempts=decision.attempt,
        lease_expires_at=lease_until(now, lease_s),
        updated_at=now,
    )
    if updated != 1:
        # 잠근 행이 사라졌거나 바뀌었다(잠금 없이 읽었다는 뜻이다).
        raise JobUpdateError(f"run_jobs 의 갱신이 {updated}행이다(1행이어야 한다)")
    claimed = selectors.find_job(company_id=company_id, job_id=job_id)
    if claimed is None:
        raise JobUpdateError("방금 잡은 run_jobs 의 행이 없다")
    return Claimed(claimed, document, decision.attempt)


# ── 끝내기 ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Done:
    summary: dict[str, int | bool]  # 작은 숫자뿐이다. 분해 결과의 본문을 싣지 않는다
    sha256: str  # 파서가 읽은 원본의 sha256. 문서 행에 적는다


@dataclass(frozen=True, slots=True)
class Failed:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class Deferred:
    """잠깐의 실패다. 상태는 `processing` 그대로 두고 임대를 **지금으로** 당긴다(곧 다시 온 쪽지가 잡을 수 있게)."""


Outcome = Done | Failed | Deferred


@dataclass(frozen=True, slots=True)
class Finished:
    pass


@dataclass(frozen=True, slots=True)
class Superseded:
    """내 시도가 더는 이 일감의 주인이 아니다(임대가 끝나 다른 워커가 이어받았거나 이미 끝났다). 쓰지 않았다."""


def finish_job(*, company_id: int, job_id: int, attempt: int, now: datetime, outcome: Outcome) -> Finished | Superseded:
    """내가 잡은 시도(attempt)의 끝을 적는다. 조건은 「`processing` 이고 attempts 가 내 시도」다."""
    _require_transaction("finish_job")
    guard = JobRow.for_company(company_id).filter(pk=job_id, status="processing", attempts=attempt)
    if isinstance(outcome, Done):
        updated = guard.update(
            status="done",
            summary=outcome.summary,
            finished_at=now,
            lease_expires_at=None,
            error_code=None,
            error_message=None,
            updated_at=now,
        )
    elif isinstance(outcome, Failed):
        updated = _fail(guard, code=outcome.code, message=outcome.message, now=now)
    else:
        updated = guard.update(lease_expires_at=now, updated_at=now)
    if updated == 0:
        return Superseded()
    if updated != 1:
        raise JobUpdateError(f"run_jobs 의 갱신이 {updated}행이다(1행이어야 한다)")

    if isinstance(outcome, Done):
        job = selectors.find_job(company_id=company_id, job_id=job_id)
        if job is None:
            raise JobUpdateError("방금 끝낸 run_jobs 의 행이 없다")
        documents = (
            DocumentRow.for_company(company_id).filter(pk=job.document_id).update(sha256=outcome.sha256, updated_at=now)
        )
        if documents != 1:
            # 문서가 이 회사에 보이지 않는다(같은 회사 외래 키가 막아 닿는 길이 없다. 방어로 남긴다).
            # 일감의 `done` 도 같이 되돌려진다.
            raise JobUpdateError(f"core_documents 의 갱신이 {documents}행이다(1행이어야 한다)")
    return Finished()
