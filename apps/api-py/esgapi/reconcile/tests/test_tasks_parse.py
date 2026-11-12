# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""분해 태스크(`jobs.parse`)를 진짜 DB 로 잰다. 업무 층: 저장소·파서는 가짜, 태스크는 **함수를 직접 부른다**.

★ 브로커도 워커도 없다. pytest 프로세스 안에서 진짜 워커를 띄우지 않는다. 「다시 해 보기」는 태스크의 retry 를
  탐지기로 바꿔 끼워 본다(진짜 retry 는 쪽지를 큐에 넣는다).
★ 무효 조건: 이 층은 연결이 하나다(주인 역할, 테스트마다 되돌린다). 트랜잭션 둘의 커밋·두 연결의 경합은
  보안 층(tests/security/test_jobs.py)이 잰다.
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import copy
import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction

from esgapi.config.env import JobSettings
from esgapi.core.models import DocumentRow
from esgapi.core.resources.ports.parser import Parsed, ParseFailed, ParseFailureDetail, ParseResult
from esgapi.core.resources.ports.storage import StorageDenied, StorageUnavailable
from esgapi.core.service.services import documents as services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.reconcile import tasks
from esgapi.reconcile.calc.job_summary import SUMMARY_KEYS
from esgapi.reconcile.service.services.parse import ParserNotConfiguredError
from esgapi.runs.models import JobRow
from esgapi.runs.service.services.jobs import Claimed, Done, Finished, claim_job, finish_job
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

SYNTHETIC = Path(__file__).resolve().parent / "golden" / "synthetic"
PDF = b"%PDF-1.7 (synthetic bytes, not a real pdf)"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
SYNTHETIC_SHA = "5" * 64  # 지은 문서 모델의 source.sha256
MARKER = "본문-표식-글자-7f3a"


def load(name: str) -> Any:
    return json.loads((SYNTHETIC / name).read_text(encoding="utf-8"))


def good() -> Parsed:
    return Parsed(load("document.json"), load("char-places.json"))


def failed(
    kind: Any, message: str = "무슨 일인지", *, code: str | None = None, status: int | None = None
) -> ParseFailed:
    return ParseFailed(kind, ParseFailureDetail(status=status, code=code, message=message))


class RetryAsked(Exception):
    """탐지기로 바꾼 retry 가 돌려주는 것(태스크가 `raise self.retry(…)` 로 던진다)."""


@dataclass
class World:
    storage: FakeStorage
    company_id: int  # 문서·일감의 회사(고정물 companies 의 A)
    other_company_id: int  # 남의 회사(B)
    now: datetime = NOW
    result: ParseResult | Exception = field(default_factory=good)
    parsed: list[bytes] = field(default_factory=list[bytes])  # 파서가 받은 바이트
    retries: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    during: Callable[[], None] | None = None  # 파서 호출 안에서 한 번 끼어드는 것

    def parse(self, pdf: bytes, *, file_name: str) -> ParseResult:
        self.parsed.append(pdf)
        if self.during is not None:
            hook, self.during = self.during, None
            hook()
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    made = World(FakeStorage(), *companies)
    plug_storage(monkeypatch, made.storage, max_upload_bytes=1000)
    monkeypatch.setattr(tasks, "default_parser", lambda: made)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "clock", lambda: made.now)

    def retry(**kwargs: Any) -> RetryAsked:
        made.retries.append(kwargs)
        return RetryAsked()

    monkeypatch.setattr(tasks.parse_job, "retry", retry)
    return made


def no_enqueue(**_: Any) -> None:
    """큐에 넣지 않는다(이 층에는 브로커가 없다)."""


def upload(world: World, data: bytes = PDF) -> int:
    """문서를 만들고 가짜 저장소에 바이트를 심고 올림을 확인한다. 분해 일감(queued)의 id 를 돌려준다."""
    created = services.create_document(
        company_id=world.company_id,
        uploaded_by="user-1",
        file_name="지은 문서.pdf",
        size_bytes=len(data),
        max_upload_bytes=1000,
        storage=world.storage,
    )
    assert isinstance(created, services.DocumentCreated)
    world.storage.put(created.document.storage_key, data)
    confirmed = services.confirm_upload(
        company_id=world.company_id,
        document_id=created.document.id,
        storage=world.storage,
        now=NOW - timedelta(minutes=1),
        enqueue=no_enqueue,
    )
    assert isinstance(confirmed, services.UploadConfirmed)
    world.storage.head_calls.clear()
    world.storage.get_calls.clear()
    return confirmed.jobs[0].id


def run(world: World, job_id: int, *, company_id: str | None = None) -> None:
    """쪽지 하나를 태스크에 먹인다. 값은 갈고리가 싣는 꼴(십진 숫자 글자)이다. company_id 를 주면 그 글자로."""
    tasks.parse_job(company_id=str(world.company_id) if company_id is None else company_id, job_id=str(job_id))


def row(job_id: int) -> dict[str, Any]:
    return JobRow.unscoped.filter(pk=job_id).values().get()


def document_row() -> dict[str, Any]:
    return DocumentRow.unscoped.values().get()


# ── 끝까지 ──


def test_a_queued_job_runs_to_done(world: World) -> None:
    job_id = upload(world)
    run(world, job_id)
    after = row(job_id)
    assert (after["status"], after["attempts"], after["lease_expires_at"]) == ("done", 1, None)
    assert (after["finished_at"], after["error_code"], after["error_message"]) == (NOW, None, None)
    assert set(after["summary"]) == set(SUMMARY_KEYS)  # jsonb 는 키의 차례를 지키지 않는다: 집합으로 견준다
    assert after["summary"] == {"pages": 3, "tables": 5, "facts": 99, "has_places": True, "warnings": 0}
    assert document_row()["sha256"] == SYNTHETIC_SHA
    assert world.parsed == [PDF]  # 파서가 받은 바이트 = 심은 바이트
    assert (len(world.storage.get_calls), world.storage.head_calls) == (1, [])
    assert world.retries == []


def test_the_same_note_twice_runs_the_parser_once_and_leaves_the_row(world: World) -> None:
    job_id = upload(world)
    run(world, job_id)
    before, document_before = row(job_id), document_row()
    world.now = NOW + timedelta(seconds=30)
    run(world, job_id)
    assert len(world.parsed) == 1
    assert row(job_id) == before  # updated_at 까지 그대로다
    assert document_row() == document_before
    assert len(world.storage.get_calls) == 1


def test_a_note_with_an_empty_tenant_is_skipped_and_touches_no_row(
    world: World, caplog: pytest.LogCaptureFixture
) -> None:
    job_id = upload(world)
    before, document_before = row(job_id), document_row()
    a, b = world.company_id, world.other_company_id
    shapes = ("", "0", "-1", f"0{a}", f"{a}.0", f" {a}", "tenant-a")  # 회사 id 의 십진 숫자 글자가 아니다
    with caplog.at_level(logging.INFO, logger=tasks.logger.name):
        for text in shapes:
            run(world, job_id, company_id=text)
        run(world, job_id, company_id=str(b))  # 꼴은 맞는 남의 회사: 조회는 하지만 0행 → 같은 「없음」
    assert [r.getMessage() for r in caplog.records if r.name == tasks.logger.name] == [
        f"job_skipped job_id={job_id} kind=parse reason=JobNotFound"
    ] * (len(shapes) + 1)
    assert (world.parsed, world.storage.get_calls, world.retries) == ([], [], [])
    assert (row(job_id), document_row()) == (before, document_before)
    assert JobRow.unscoped.count() == 1  # 분모


def test_a_job_another_worker_holds_is_left_alone(world: World) -> None:
    job_id = upload(world)
    JobRow.unscoped.filter(pk=job_id).update(
        status="processing", attempts=1, lease_expires_at=NOW + timedelta(seconds=1)
    )
    before = row(job_id)
    run(world, job_id)
    assert (world.parsed, world.storage.get_calls) == ([], [])
    assert row(job_id) == before


def test_a_job_whose_lease_has_passed_is_taken_over_and_finished(world: World) -> None:
    job_id = upload(world)
    JobRow.unscoped.filter(pk=job_id).update(status="processing", attempts=1, lease_expires_at=NOW)
    run(world, job_id)
    after = row(job_id)
    assert (after["status"], after["attempts"], after["finished_at"]) == ("done", 2, NOW)
    assert len(world.parsed) == 1


def test_a_worker_that_was_taken_over_answers_late_and_writes_nothing(world: World) -> None:
    """먼저 잡은 워커가 파서를 기다리는 동안 임대가 끝나 다른 워커가 이어받았다(아직 돈다). 늦은 답은 쓰이지 않는다.

    뒤 워커가 **끝내기 전**이라 행은 여전히 `processing` 이다. 먼저 잡은 쪽을 막는 것은 상태가 아니라 attempts 다.
    """
    job_id = upload(world)
    world.result = failed("rejected", "늦게 온 답", code="late_answer")
    taken: list[dict[str, Any]] = []

    def second_worker_takes_over() -> None:
        world.now = NOW + timedelta(seconds=SETTINGS.lease_s)  # 임대가 끝났다
        with transaction.atomic(durable=True):
            claimed = claim_job(
                company_id=world.company_id, job_id=job_id, now=world.now, lease_s=SETTINGS.lease_s, max_attempts=3
            )
        assert isinstance(claimed, Claimed) and claimed.attempt == 2
        taken.append(row(job_id))
        world.now = NOW + timedelta(seconds=SETTINGS.lease_s + 20)  # 먼저 잡은 워커가 이제야 답을 받는다

    world.during = second_worker_takes_over
    run(world, job_id)
    assert (taken[0]["status"], taken[0]["attempts"]) == ("processing", 2)
    assert row(job_id) == taken[0]  # 먼저 잡은 쪽의 끝내기는 Superseded: 뒤 워커가 쥔 행 그대로다
    assert world.retries == []

    # 뒤 워커가 자기 시도로 끝낸다. 끝은 그 한 번이다.
    with transaction.atomic(durable=True):
        done = finish_job(
            company_id=world.company_id, job_id=job_id, attempt=2, now=world.now, outcome=Done({"pages": 1}, "a" * 64)
        )
    assert done == Finished()
    assert (row(job_id)["status"], row(job_id)["attempts"], row(job_id)["error_code"]) == ("done", 2, None)


def test_after_a_takeover_the_parser_may_run_twice_but_the_end_is_written_once(world: World) -> None:
    """★ 한 번만 「끝난다」이지 한 번만 「도는」 것이 아니다: 이어받은 워커도 파서를 부른다."""
    job_id = upload(world)
    first_answer = failed("rejected", "늦게 온 답", code="late_answer")
    seen: list[dict[str, Any]] = []

    def second_worker() -> None:
        world.now = NOW + timedelta(seconds=SETTINGS.lease_s)
        world.result = good()
        run(world, job_id)  # 이어받아(attempts 2) 끝까지 간다
        seen.append(row(job_id))
        world.result = first_answer
        world.now = NOW + timedelta(seconds=SETTINGS.lease_s + 20)

    world.during = second_worker
    run(world, job_id)
    assert len(world.parsed) == 2  # 파서는 두 번 불렸다
    assert (seen[0]["status"], seen[0]["attempts"]) == ("done", 2)
    assert row(job_id) == seen[0]  # 끝은 뒤 워커가 쓴 것 하나다
    assert row(job_id)["error_code"] is None


def test_a_job_out_of_attempts_fails_without_calling_anything(world: World) -> None:
    job_id = upload(world)
    JobRow.unscoped.filter(pk=job_id).update(
        status="processing", attempts=3, lease_expires_at=NOW - timedelta(seconds=1)
    )
    run(world, job_id)
    after = row(job_id)
    assert (after["status"], after["error_code"], after["attempts"]) == ("failed", "attempts_exhausted", 3)
    assert (world.parsed, world.storage.get_calls, world.retries) == ([], [], [])


# ── 저장소의 갈래 ──


def test_an_object_swapped_after_the_confirm_is_not_parsed(world: World) -> None:
    job_id = upload(world)
    key = document_row()["storage_key"]
    world.storage.put(key, PDF[::-1])  # 같은 크기의 다른 바이트(ETag 가 달라진다)
    run(world, job_id)
    after = row(job_id)
    assert (after["status"], after["error_code"], after["attempts"]) == ("failed", "object_changed", 1)
    assert world.parsed == []
    assert document_row()["sha256"] is None


def remove_object(world: World, key: str) -> None:
    del world.storage.objects[key]


def grow_object(world: World, key: str) -> None:
    world.storage.put(key, b"x" * 1001)  # 상한(1000)보다 크다


def deny(world: World, key: str) -> None:
    world.storage.fail_with = StorageDenied("403 AccessDenied")


@pytest.mark.parametrize(
    ("break_it", "code"),
    [(remove_object, "object_missing"), (grow_object, "object_too_large"), (deny, "storage_denied")],
)
def test_storage_failures_that_will_not_heal_fail_the_job(
    world: World, break_it: Callable[[World, str], None], code: str
) -> None:
    job_id = upload(world)
    break_it(world, document_row()["storage_key"])
    run(world, job_id)
    after = row(job_id)
    assert (after["status"], after["error_code"], after["attempts"]) == ("failed", code, 1)
    assert after["finished_at"] == NOW
    assert (world.parsed, world.retries) == ([], [])


def test_a_missing_storage_or_parser_setting_fails_the_job(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = upload(world)
    plug_storage(monkeypatch, None)
    run(world, job_id)
    assert (row(job_id)["status"], row(job_id)["error_code"]) == ("failed", "storage_unconfigured")

    plug_storage(monkeypatch, world.storage)
    JobRow.unscoped.all().delete()
    DocumentRow.unscoped.all().delete()
    job_id = upload(world)

    def no_parser() -> Any:
        raise ParserNotConfiguredError("PARSER_URL 이 없다")

    monkeypatch.setattr(tasks, "default_parser", no_parser)
    run(world, job_id)
    assert (row(job_id)["status"], row(job_id)["error_code"]) == ("failed", "parser_unconfigured")
    assert world.storage.get_calls == []


# ── 잠깐의 실패: 임대를 당기고 다시 해 보기를 청한다 ──


def break_storage(world: World) -> None:
    world.storage.fail_with = StorageUnavailable("닿지 못했다")


def break_parser(world: World) -> None:
    world.result = failed("unavailable", "503", status=503)


def time_out(world: World) -> None:
    world.result = SoftTimeLimitExceeded()


@pytest.mark.parametrize("break_it", [break_storage, break_parser, time_out])
def test_a_passing_failure_keeps_processing_pulls_the_lease_and_asks_for_a_retry(
    world: World, break_it: Callable[[World], None]
) -> None:
    job_id = upload(world)
    break_it(world)
    world.now = NOW + timedelta(seconds=2)
    with pytest.raises(RetryAsked):
        run(world, job_id)
    after = row(job_id)
    assert (after["status"], after["attempts"]) == ("processing", 1)
    assert after["lease_expires_at"] == world.now  # 임대 = 지금
    assert (after["finished_at"], after["error_code"]) == (None, None)
    assert world.retries == [{"countdown": 5, "max_retries": None}]


def test_passing_failures_use_up_the_attempts_and_then_the_job_fails(world: World) -> None:
    """잠깐의 실패도 시도를 쓴다. 상한(3)까지 되풀이되면 넷째 쪽지에서 `failed`·attempts_exhausted 로 끝난다."""
    job_id = upload(world)
    break_parser(world)
    for attempt in (1, 2, 3):
        world.now = NOW + timedelta(seconds=5 * attempt)
        with pytest.raises(RetryAsked):
            run(world, job_id)
        assert (row(job_id)["status"], row(job_id)["attempts"]) == ("processing", attempt)
    world.now = NOW + timedelta(seconds=20)
    run(world, job_id)
    after = row(job_id)
    assert (after["status"], after["error_code"], after["attempts"]) == ("failed", "attempts_exhausted", 3)
    assert len(world.parsed) == 3 and len(world.retries) == 3


# ── 파서의 갈래 ──


def mismatched() -> Parsed:
    places = load("char-places.json")
    places["source"]["sha256"] = "6" * 64
    return Parsed(load("document.json"), places)


def broken_document() -> Parsed:
    document = load("document.json")
    document["blocks"][0]["bbox"] = [1, 2, 3]
    return Parsed(document, load("char-places.json"))


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (failed("rejected", "PDF 가 아니다", code="not_a_pdf", status=422), "not_a_pdf"),
        (failed("rejected", "거절", status=400), "rejected"),
        (failed("invalid_response", "봉투가 틀리다", status=200), "invalid_response"),
        (broken_document(), "document_invalid"),
        (mismatched(), "places_source_mismatch"),
    ],
)
def test_parser_problems_that_will_not_heal_fail_the_job_with_their_code(
    world: World, result: ParseResult, code: str
) -> None:
    job_id = upload(world)
    world.result = result
    run(world, job_id)
    after = row(job_id)
    assert (after["status"], after["error_code"], after["attempts"]) == ("failed", code, 1)
    assert after["error_message"] and len(after["error_message"]) <= 500
    assert (after["summary"], document_row()["sha256"]) == ({}, None)
    assert world.retries == []
    # 끝난 일감은 다시 돌지 않는다.
    run(world, job_id)
    assert len(world.parsed) == 1


def test_no_text_of_the_document_reaches_either_table(world: World) -> None:
    """분해 결과의 본문은 저장하지 않는다: 문서 모델에 심은 표식 글자가 두 표의 어느 칸에도 없다."""
    document = copy.deepcopy(load("document.json"))
    marked = 0
    for block in document["blocks"]:
        if isinstance(block.get("text"), str):
            block["text"] = f"{MARKER} {block['text']}"
            marked += 1
    assert marked > 0
    world.result = Parsed(document, None, (f"경고 속의 {MARKER}",))
    job_id = upload(world)
    run(world, job_id)
    after = row(job_id)
    assert after["status"] == "done" and after["summary"]["warnings"] == 1
    everything = json.dumps([after, document_row()], default=str, ensure_ascii=False)
    assert MARKER not in everything
    assert hashlib.sha256(PDF).hexdigest() not in everything  # 적히는 sha256 은 파서가 말한 것이다


# ── 예상 밖 예외(D8) ──


def test_an_unexpected_exception_fails_the_job_instead_of_leaving_it_processing(
    world: World, caplog: pytest.LogCaptureFixture
) -> None:
    """★ 분해 중 예상 밖 예외는 T2 를 건너뛰지 않는다: `failed`·internal 로 끝난다(쪽지는 ack 되어 다시 오지 않고,
    beat 가 없어 임대가 지나도 저절로 다시 잡히지 않는다 — 고치기 전에는 `processing` 에 묶였다).
    예외의 글(문서 글이 섞일 수 있다)은 표의 칸에 싣지 않는다."""
    job_id = upload(world)
    world.result = RuntimeError(f"예상 밖 {MARKER}")
    with caplog.at_level(logging.ERROR, logger=tasks.__name__):
        run(world, job_id)
    after = row(job_id)
    assert (after["status"], after["error_code"], after["attempts"]) == ("failed", "internal", 1)
    assert after["finished_at"] == NOW
    assert MARKER not in json.dumps([after, document_row()], default=str, ensure_ascii=False)
    assert world.retries == []
    [record] = [r for r in caplog.records if r.name == tasks.__name__ and r.levelno == logging.ERROR]
    assert record.exc_info is not None
    assert MARKER not in record.getMessage()
    # 끝난 일감은 다시 돌지 않는다.
    run(world, job_id)
    assert len(world.parsed) == 1
