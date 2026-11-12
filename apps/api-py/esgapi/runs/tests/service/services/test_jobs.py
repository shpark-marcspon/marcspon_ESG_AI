"""일감을 잡고 끝내는 쓰기와 다시 넣기 명령을 진짜 DB 로 잰다. 업무 층: 테스트마다 되돌린다(주인 역할).

★ 무효 조건: 이 층은 연결이 하나다. 앱 역할 연결에서의 테넌트 경계와 두 연결의 경합은 보안 층
  (tests/security/test_jobs.py)이 잰다. 여기서 본 잠금은 SQL 의 글자와 차례뿐이다.
★ 브로커가 없다. 갈고리는 탐지기로 바꿔 끼운다(진짜 celery_app() 으로 send_task 를 부르지 않는다).
"""

from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any

import psycopg
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from esgapi.config.env import BrokerSettings
from esgapi.core.calc.jobs import AlreadyFinished, Exhausted, LeaseHeld
from esgapi.core.models import DocumentRow
from esgapi.core.resources import queue as hooks
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.core.service.services import documents as services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.models import JobRow
from esgapi.runs.service.selectors.jobs import stale_jobs
from esgapi.runs.service.services.jobs import (
    Claimed,
    Deferred,
    DocumentMissing,
    Done,
    Failed,
    Finished,
    JobNotFound,
    Superseded,
    claim_job,
    finish_job,
)

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
LEASE_S = 90
MAX = 3
BROKER = BrokerSettings(
    url="sqs://queue:9324",
    region="ap-northeast-2",
    queue_name="esg-jobs",
    queue_url="http://queue:9324/000000000000/esg-jobs",
    secure=False,
)


def no_enqueue(**_: Any) -> None:
    """큐에 넣지 않는다(이 층에는 브로커가 없다)."""


def seed(company_id: int, **job: Any) -> int:
    """올림이 확인된 문서 하나와 그 분해 일감(queued) 하나. 일감의 id 를 돌려준다. `job` 으로 일감의 칸을 덮어쓴다."""
    storage = FakeStorage()
    created = services.create_document(
        company_id=company_id,
        uploaded_by="user-1",
        file_name="a.pdf",
        size_bytes=5,
        max_upload_bytes=1000,
        storage=storage,
    )
    assert isinstance(created, services.DocumentCreated)
    storage.put(created.document.storage_key, b"12345")
    confirmed = services.confirm_upload(
        company_id=company_id,
        document_id=created.document.id,
        storage=storage,
        now=NOW - timedelta(hours=1),
        enqueue=no_enqueue,
    )
    assert isinstance(confirmed, services.UploadConfirmed)
    job_id = confirmed.jobs[0].id
    JobRow.unscoped.filter(pk=job_id).update(updated_at=NOW - timedelta(hours=1), **job)
    return job_id


def row(job_id: int) -> dict[str, Any]:
    return JobRow.unscoped.filter(pk=job_id).values().get()


def claim(job_id: int, company_id: int, now: datetime = NOW) -> Any:
    return claim_job(company_id=company_id, job_id=job_id, now=now, lease_s=LEASE_S, max_attempts=MAX)


# ── 잡기 ──


def test_claiming_a_queued_job_makes_it_processing_with_a_lease(companies: tuple[int, int]) -> None:
    a, _ = companies
    job_id = seed(a)
    claimed = claim(job_id, a)
    assert isinstance(claimed, Claimed)
    assert (claimed.attempt, claimed.job.status, claimed.job.attempts) == (1, "processing", 1)
    assert (claimed.document.company_id, claimed.document.status) == (a, "uploaded")
    assert claimed.document.id == row(job_id)["document_id"]
    after = row(job_id)
    assert (after["status"], after["attempts"]) == ("processing", 1)
    assert after["lease_expires_at"] == NOW + timedelta(seconds=LEASE_S)
    assert after["updated_at"] == NOW
    assert (after["finished_at"], after["error_code"], after["summary"]) == (None, None, {})


def test_the_claim_locks_the_row_before_it_writes(companies: tuple[int, int]) -> None:
    """잡기가 낸 SQL: run_jobs 의 FOR UPDATE 가 있고 그 뒤에 UPDATE 가 온다. 무효 조건: 글자와 차례만 봤다."""
    a, _ = companies
    job_id = seed(a)
    with CaptureQueriesContext(connection) as captured:
        claim(job_id, a)
    statements = [query["sql"] for query in captured.captured_queries]
    locks = [
        n for n, text in enumerate(statements) if 'FROM "run_jobs"' in text and text.rstrip().endswith("FOR UPDATE")
    ]
    updates = [n for n, text in enumerate(statements) if text.startswith('UPDATE "run_jobs"')]
    assert len(locks) == 1 and len(updates) == 1, statements
    assert locks[0] < updates[0]
    # 갱신의 조건에 읽은 상태와 시도가 있다(울타리).
    assert '"run_jobs"."status" = \'queued\'' in statements[updates[0]]
    assert '"run_jobs"."attempts" = 0' in statements[updates[0]]


def test_a_job_whose_lease_is_still_held_is_not_taken(companies: tuple[int, int]) -> None:
    a, _ = companies
    job_id = seed(a)
    assert isinstance(claim(job_id, a), Claimed)
    before = row(job_id)
    held = claim(job_id, a, NOW + timedelta(seconds=LEASE_S - 1))
    assert held == LeaseHeld(NOW + timedelta(seconds=LEASE_S))
    assert row(job_id) == before


def test_a_job_whose_lease_has_passed_is_taken_over(companies: tuple[int, int]) -> None:
    a, _ = companies
    job_id = seed(a)
    assert isinstance(claim(job_id, a), Claimed)
    later = NOW + timedelta(seconds=LEASE_S)  # 딱 그 시각이면 지난 것이다
    taken = claim(job_id, a, later)
    assert isinstance(taken, Claimed) and taken.attempt == 2
    after = row(job_id)
    assert (after["status"], after["attempts"], after["lease_expires_at"]) == (
        "processing",
        2,
        later + timedelta(seconds=LEASE_S),
    )


@pytest.mark.parametrize("status", ["done", "failed"])
def test_a_finished_job_is_not_taken(status: str, companies: tuple[int, int]) -> None:
    a, _ = companies
    job_id = seed(a, status=status, attempts=1, finished_at=NOW)
    before = row(job_id)
    assert claim(job_id, a) == AlreadyFinished()
    assert row(job_id) == before


def test_a_job_out_of_attempts_is_finished_as_failed(companies: tuple[int, int]) -> None:
    a, _ = companies
    job_id = seed(a, status="processing", attempts=MAX, lease_expires_at=NOW - timedelta(seconds=1))
    assert claim(job_id, a) == Exhausted()
    after = row(job_id)
    assert (after["status"], after["error_code"], after["attempts"]) == ("failed", "attempts_exhausted", MAX)
    assert (after["finished_at"], after["lease_expires_at"], after["updated_at"]) == (NOW, None, NOW)
    assert after["error_message"] == "시도 3번을 다 썼다"
    assert claim(job_id, a) == AlreadyFinished()  # 한 번 끝났으면 다시 끝나지 않는다


def test_an_unknown_job_is_not_found(companies: tuple[int, int]) -> None:
    a, _ = companies
    job_id = seed(a)
    unknown = [n for n in (job_id - 2, job_id - 1, job_id + 1, job_id + 2) if n > 0]  # 숫자 id 의 이웃
    assert unknown  # 분모
    assert [claim(n, a) for n in unknown] == [JobNotFound()] * len(unknown)


def test_a_job_on_another_tenants_document_is_refused_by_the_db_and_a_missing_document_fails_the_job(
    monkeypatch: pytest.MonkeyPatch,
    companies: tuple[int, int],
) -> None:
    """일감의 company_id 를 문서의 것과 다르게 고치면 DB 가 그 문에서 거절한다(받침 ⑤, migrations/0001. NOT DEFERRABLE).

    그래서 「잡을 때 문서가 이 테넌트에 안 보인다」 갈래(document_missing)에는 지금 닿는 길이 없다. 갈래는 방어로 남아
    있으므로 문서 찾기를 None 으로 바꿔 끼워 그 갈래를 잰다(남의 문서 없이).
    """
    a, b = companies
    job_id = seed(a)
    before = row(job_id)
    with pytest.raises(IntegrityError) as refused, transaction.atomic():
        JobRow.unscoped.filter(pk=job_id).update(company_id=b)  # A 의 문서에 건 B 의 일감으로 만들려 한다
    cause = refused.value.__cause__
    assert isinstance(cause, psycopg.Error)
    assert cause.sqlstate == "23503"
    assert row(job_id) == before  # 그대로(A, queued)
    assert JobRow.unscoped.filter(company_id=b).count() == 0
    assert JobRow.unscoped.count() == 1  # 분모: 일감 하나

    def not_visible(**_: Any) -> None:
        return None

    monkeypatch.setattr(document_selectors, "find_document", not_visible)
    assert claim(job_id, a) == DocumentMissing()
    after = row(job_id)
    assert (after["status"], after["error_code"], after["finished_at"]) == ("failed", "document_missing", NOW)
    assert DocumentRow.unscoped.values_list("company_id", "sha256").get() == (a, None)


# ── 끝내기 ──


def claimed_job(company_id: int) -> int:
    job_id = seed(company_id)
    assert isinstance(claim(job_id, company_id), Claimed)
    return job_id


def test_done_writes_the_summary_and_the_documents_sha256(companies: tuple[int, int]) -> None:
    a, _ = companies
    job_id = claimed_job(a)
    later = NOW + timedelta(seconds=7)
    summary = {"pages": 3, "tables": 5, "facts": 99, "has_places": True, "warnings": 0}
    assert finish_job(company_id=a, job_id=job_id, attempt=1, now=later, outcome=Done(summary, "5" * 64)) == Finished()
    after = row(job_id)
    assert (after["status"], after["attempts"], after["summary"]) == ("done", 1, summary)
    assert (after["finished_at"], after["lease_expires_at"], after["updated_at"]) == (later, None, later)
    assert (after["error_code"], after["error_message"]) == (None, None)
    assert DocumentRow.unscoped.values_list("sha256", "updated_at").get() == ("5" * 64, later)


def test_failed_writes_the_code_and_cuts_both_texts_to_the_columns(companies: tuple[int, int]) -> None:
    a, _ = companies
    job_id = claimed_job(a)
    outcome = Failed("c" * 80, "가" * 800)
    assert finish_job(company_id=a, job_id=job_id, attempt=1, now=NOW, outcome=outcome) == Finished()
    after = row(job_id)
    assert (after["status"], after["error_code"], after["error_message"]) == ("failed", "c" * 64, "가" * 500)
    assert (after["finished_at"], after["lease_expires_at"], after["summary"]) == (NOW, None, {})
    assert DocumentRow.unscoped.values_list("sha256", flat=True).get() is None


def test_deferred_keeps_processing_and_pulls_the_lease_to_now(companies: tuple[int, int]) -> None:
    a, _ = companies
    job_id = claimed_job(a)
    later = NOW + timedelta(seconds=3)
    assert finish_job(company_id=a, job_id=job_id, attempt=1, now=later, outcome=Deferred()) == Finished()
    after = row(job_id)
    assert (after["status"], after["attempts"], after["lease_expires_at"]) == ("processing", 1, later)
    assert (after["finished_at"], after["error_code"]) == (None, None)
    # 그래서 같은 시각에 다시 온 쪽지가 잡는다.
    again = claim(job_id, a, later)
    assert isinstance(again, Claimed) and again.attempt == 2


@pytest.mark.parametrize("outcome", [Done({"pages": 1}, "a" * 64), Failed("rejected", "x"), Deferred()])
def test_a_worker_that_was_taken_over_cannot_write(outcome: Any, companies: tuple[int, int]) -> None:
    """임대가 끝나 다른 워커가 이어받았다(attempts 2). 먼저 잡았던 시도(1)의 끝내기는 0행이고 쓰지 않는다."""
    a, _ = companies
    job_id = claimed_job(a)
    assert isinstance(claim(job_id, a, NOW + timedelta(seconds=LEASE_S)), Claimed)
    before = row(job_id)
    assert (
        finish_job(company_id=a, job_id=job_id, attempt=1, now=NOW + timedelta(seconds=200), outcome=outcome)
        == Superseded()
    )
    assert row(job_id) == before
    assert DocumentRow.unscoped.values_list("sha256", flat=True).get() is None


def test_a_finished_job_cannot_be_finished_again(companies: tuple[int, int]) -> None:
    a, _ = companies
    job_id = claimed_job(a)
    assert (
        finish_job(company_id=a, job_id=job_id, attempt=1, now=NOW, outcome=Done({"pages": 1}, "a" * 64)) == Finished()
    )
    before = row(job_id)
    for outcome in (Failed("rejected", "x"), Done({"pages": 2}, "b" * 64), Deferred()):
        assert (
            finish_job(company_id=a, job_id=job_id, attempt=1, now=NOW + timedelta(seconds=9), outcome=outcome)
            == Superseded()
        )
    assert row(job_id) == before
    assert DocumentRow.unscoped.values_list("sha256", flat=True).get() == "a" * 64


def test_the_finish_write_is_fenced_by_status_and_attempts(companies: tuple[int, int]) -> None:
    a, _ = companies
    job_id = claimed_job(a)
    with CaptureQueriesContext(connection) as captured:
        finish_job(company_id=a, job_id=job_id, attempt=1, now=NOW, outcome=Failed("rejected", "x"))
    update = next(q["sql"] for q in captured.captured_queries if q["sql"].startswith('UPDATE "run_jobs"'))
    assert '"run_jobs"."status" = \'processing\'' in update and '"run_jobs"."attempts" = 1' in update


# ── 다시 넣을 것과 명령 ──


def six_jobs(company_id: int) -> dict[str, int]:
    """일감 여섯: 고를 것은 둘(임대 지난 processing, 오래된 queued)이다."""
    old = NOW - timedelta(seconds=500)
    made = {
        "queued-fresh": seed(company_id),
        "queued-old": seed(company_id),
        "processing-held": seed(
            company_id, status="processing", attempts=1, lease_expires_at=NOW + timedelta(seconds=30)
        ),
        "processing-lapsed": seed(
            company_id, status="processing", attempts=1, lease_expires_at=NOW - timedelta(seconds=1)
        ),
        "done": seed(company_id, status="done", attempts=1, finished_at=old, lease_expires_at=None),
        "failed": seed(company_id, status="failed", attempts=3, finished_at=old, error_code="rejected"),
    }
    JobRow.unscoped.filter(pk=made["queued-fresh"]).update(updated_at=NOW - timedelta(seconds=10))
    JobRow.unscoped.filter(pk=made["queued-old"]).update(updated_at=old)
    return made


def test_stale_jobs_are_the_lapsed_processing_and_the_old_queued_only(companies: tuple[int, int]) -> None:
    a, _ = companies
    made = six_jobs(a)
    stale = stale_jobs(company_id=a, now=NOW, queued_older_than_s=LEASE_S)
    assert {job.id for job in stale} == {made["queued-old"], made["processing-lapsed"]}  # 여섯 가운데 둘
    assert JobRow.unscoped.count() == 6
    # 딱 그 시각의 임대는 지난 것이고, 임대가 없는 processing 도 고른다(잡기의 판정과 같다).
    JobRow.unscoped.filter(pk=made["processing-held"]).update(lease_expires_at=NOW)
    JobRow.unscoped.filter(pk=made["queued-fresh"]).update(status="processing", lease_expires_at=None)
    assert len(stale_jobs(company_id=a, now=NOW, queued_older_than_s=LEASE_S)) == 4
    # 고르기만 한다: 행은 그대로다.
    assert row(made["queued-old"])["status"] == "queued"


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(hooks, "enqueue_job", lambda **kwargs: calls.append(kwargs))  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    return calls


def run_requeue(*args: str) -> tuple[str, str]:
    out, err = StringIO(), StringIO()
    call_command("requeue_jobs", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def test_requeue_sends_the_stale_jobs_of_that_tenant(
    sent: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    companies: tuple[int, int],
) -> None:
    a, _ = companies
    from esgapi.runs.management.commands import requeue_jobs

    made = six_jobs(a)
    monkeypatch.setattr(requeue_jobs, "now", lambda: NOW)
    out, err = run_requeue("--tenant", str(a))
    assert {call["job_id"] for call in sent} == {made["queued-old"], made["processing-lapsed"]}
    assert all((call["company_id"], call["kind"]) == (a, "parse") for call in sent)
    assert out.splitlines()[-1] == "고른 수 2 · 넣은 수 2 · 실패한 수 0"
    assert err == ""
    # 찍는 것은 일감의 id·상태·시도뿐이다(파일 이름·저장소 키가 없다).
    assert "a.pdf" not in out and "tenants/" not in out and "companies/" not in out
    # 행은 건드리지 않는다.
    assert row(made["processing-lapsed"])["status"] == "processing"
    assert row(made["queued-old"])["status"] == "queued"


def test_requeue_dry_run_sends_nothing(
    sent: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    a, _ = companies
    from esgapi.runs.management.commands import requeue_jobs

    six_jobs(a)
    monkeypatch.setattr(requeue_jobs, "now", lambda: NOW)
    monkeypatch.setattr(hooks, "broker_settings", lambda: None)  # 고르기만 하는 데는 브로커가 필요 없다
    out, _ = run_requeue("--tenant", str(a), "--dry-run")
    assert sent == []
    assert out.splitlines()[-1] == "고른 수 2 · 넣은 수 0 · 실패한 수 0"
    assert len([line for line in out.splitlines() if line.startswith("고름 ")]) == 2


def test_requeue_takes_the_age_of_queued_jobs_as_an_option(
    sent: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    companies: tuple[int, int],
) -> None:
    a, _ = companies
    from esgapi.runs.management.commands import requeue_jobs

    six_jobs(a)
    monkeypatch.setattr(requeue_jobs, "now", lambda: NOW)
    out, _ = run_requeue("--tenant", str(a), "--queued-older-than-seconds", "5")
    assert out.splitlines()[-1] == "고른 수 3 · 넣은 수 3 · 실패한 수 0"  # 10초 머문 queued 도 든다


def test_requeue_needs_a_tenant(sent: list[dict[str, Any]], companies: tuple[int, int]) -> None:
    a, _ = companies
    six_jobs(a)
    with pytest.raises(CommandError, match="--tenant"):
        run_requeue()
    for text in ("Tenant/A", "tenant-a", "0", "-1", "01", "1.0", "", " 1"):  # 회사 id 의 십진 숫자 글자가 아니다
        with pytest.raises(CommandError, match="--tenant 의 꼴이 틀렸다") as bad:
            run_requeue("--tenant", text)
        assert bad.value.returncode == 2, text
    assert sent == []


def test_requeue_without_a_broker_ends_non_zero_and_reads_nothing(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    """이 테스트 환경에는 브로커 설정이 없다(진짜 갈고리의 진짜 설정 읽기를 그대로 쓴다)."""
    a, _ = companies
    six_jobs(a)
    assert hooks.broker_settings() is None
    monkeypatch.setattr(hooks, "celery_app", lambda: pytest.fail("브로커 없이 앱을 얻으려 했다"))
    with (
        CaptureQueriesContext(connection) as captured,
        pytest.raises(CommandError, match="CELERY_BROKER_URL 이 없다") as stopped,
    ):
        run_requeue("--tenant", str(a))
    assert stopped.value.returncode == 1
    assert captured.captured_queries == []


def test_requeue_counts_failures_and_goes_on(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> None:
    a, _ = companies
    from esgapi.runs.management.commands import requeue_jobs

    made = six_jobs(a)
    monkeypatch.setattr(requeue_jobs, "now", lambda: NOW)
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    calls: list[int] = []

    class Unreachable(Exception):
        pass

    def flaky(**kwargs: Any) -> None:
        calls.append(kwargs["job_id"])
        if len(calls) == 1:
            raise Unreachable("sqs://secret-key@queue:9324 에 닿지 않는다")

    monkeypatch.setattr(hooks, "enqueue_job", flaky)
    out, err = StringIO(), StringIO()
    with pytest.raises(CommandError, match="넣지 못한 일감이 1건") as stopped:
        call_command("requeue_jobs", "--tenant", str(a), stdout=out, stderr=err)
    assert stopped.value.returncode == 1
    assert len(calls) == 2 and set(calls) == {made["queued-old"], made["processing-lapsed"]}
    assert out.getvalue().splitlines()[-1] == "고른 수 2 · 넣은 수 1 · 실패한 수 1"
    assert "Unreachable" in err.getvalue() and "secret-key" not in err.getvalue()  # 오류의 종류만 찍는다
