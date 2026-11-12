"""문서 서비스의 X1b-2a 몫을 HTTP 없이 진짜 DB 로 잰다. 업무 층: 테스트마다 되돌린다(주인 역할).

    올림 확인의 쪽 수·글자 층 재기(③' — 블록 밖, 어떤 실패도 올림을 막지 않고 값 둘 NULL)
    만들기의 보고 연도
    문서 고치기(update_document — 보고 연도·앞 판, 판 사슬 규칙, 두 행 잠금의 차례, 부분 UNIQUE 의 경합)

옛 평평한 파일 core/tests/test_documents_services.py 의 몫(만들기·올림 확인의 상태·일감·감사)은 거기 그대로다.
PDF 는 시험이 짓는다(resource_fakes.build_pdf). 갈래는 진짜 어댑터의 이음매(`_CHILD`·`subprocess.run`)나
가짜 FakePdfProbe 로.
"""

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import connection

from esgapi.core.calc.versions import ChainCycle, ChainFork, ChainSelf, ChainTooLong
from esgapi.core.models import AuditEventRow, DocumentRow
from esgapi.core.resources import pdf
from esgapi.core.resources.ports.pdf import PdfProbed, PdfUnreadable, ProbeResult
from esgapi.core.resources.ports.storage import GetResult, ObjectBytes, StorageUnavailable
from esgapi.core.service.selectors import documents as selectors
from esgapi.core.service.selectors.documents import DocumentNotFound
from esgapi.core.service.services import documents as services
from esgapi.core.tests.resource_fakes import FakePdfProbe, FakeStorage, build_pdf
from esgapi.runs.models import JobRow

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def created(storage: FakeStorage, company_id: int, content: bytes, **overrides: Any) -> int:
    result = services.create_document(
        company_id=company_id,
        uploaded_by="7",
        file_name="a.pdf",
        size_bytes=len(content),
        max_upload_bytes=10_000_000,
        storage=storage,
        **overrides,
    )
    assert isinstance(result, services.DocumentCreated)
    storage.put(result.document.storage_key, content)
    return result.document.id


def no_queue(**_: object) -> None:
    """큐에 넣지 않는다(이 파일은 일감의 쪽지를 재지 않는다)."""


def confirmed(storage: FakeStorage, company_id: int, document_id: int) -> services.UploadConfirmed:
    result = services.confirm_upload(
        company_id=company_id, document_id=document_id, storage=storage, now=NOW, enqueue=no_queue
    )
    assert isinstance(result, services.UploadConfirmed), result
    return result


def row_of(document_id: int) -> tuple[object, ...]:
    row = DocumentRow.unscoped.get(pk=document_id)
    return (row.company_id, row.status, row.page_count, row.has_text)


def counts(company_id: int) -> tuple[int, int]:
    """(그 회사의 일감 수, 감사 줄 수)."""
    return JobRow.for_company(company_id).count(), AuditEventRow.for_company(company_id).count()


# ── 올림 확인의 재기 ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (build_pdf(5, text="Hello"), (5, True)),
        (build_pdf(4), (4, False)),
    ],
    ids=["5쪽-글있음", "4쪽-글없음"],
)
def test_the_confirm_measures_a_real_pdf(
    companies: tuple[int, int], content: bytes, expected: tuple[int, bool]
) -> None:
    a, _ = companies
    storage = FakeStorage()
    document_id = created(storage, a, content)
    done = confirmed(storage, a, document_id)
    assert (done.document.page_count, done.document.has_text) == expected
    assert row_of(document_id) == (a, "uploaded", *expected)
    assert counts(a) == (1, 1)  # 일감 하나·감사 줄 하나 — 전과 같다
    assert len(storage.get_calls) == 1  # 바이트는 한 번 읽었다


def test_bytes_that_are_not_a_pdf_still_confirm_with_unknown_values(companies: tuple[int, int]) -> None:
    a, _ = companies
    storage = FakeStorage()
    document_id = created(storage, a, b"12345")
    done = confirmed(storage, a, document_id)
    assert (done.document.status, done.document.page_count, done.document.has_text) == ("uploaded", None, None)
    assert counts(a) == (1, 1)


@pytest.mark.parametrize(
    "child",
    [
        "import time; time.sleep(30)",  # 시간 넘김 → 죽임
        "import os, signal; os.kill(os.getpid(), signal.SIGKILL)",  # 신호로 죽음
        "print('garbage')",  # 이상 출력
        "import json; print(json.dumps({'pages': 0, 'texts': []}))",  # 쪽 0
        "import json; print(json.dumps({'pages': 1, 'texts': ['x' * 3_060_000]}))",  # 출력 상한 넘음(가지 리뷰)
    ],
    ids=["timeout", "crashed", "error", "empty", "too_much_output"],
)
def test_every_probe_failure_confirms_with_null_values_and_the_same_company(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int], child: str
) -> None:
    """어떤 실패도 올림을 막지 않는다: 200 갈래·`uploaded`·값 둘 NULL·행의 회사 그대로·일감 하나·감사 줄 하나."""
    a, _ = companies
    monkeypatch.setattr(pdf, "PDF_PROBE_TIMEOUT_S", 1)
    monkeypatch.setattr(pdf, "_CHILD", child)
    storage = FakeStorage()
    document_id = created(storage, a, build_pdf(2, text="Hi"))
    started = time.monotonic()
    done = confirmed(storage, a, document_id)
    # 시간 한도(1초로 줄임)가 자식을 끊는다 — 한도가 빠지면 잠드는 자식(30초)을 기다려 여기서 빨개진다
    assert time.monotonic() - started < 1 + 2
    assert (done.document.page_count, done.document.has_text) == (None, None)
    assert row_of(document_id) == (a, "uploaded", None, None)
    assert counts(a) == (1, 1)


def test_failing_to_start_the_child_confirms_with_null_values(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    a, _ = companies

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise OSError("fork failed")

    monkeypatch.setattr(pdf.subprocess, "run", refuse)
    storage = FakeStorage()
    document_id = created(storage, a, build_pdf(2, text="Hi"))
    confirmed(storage, a, document_id)
    assert row_of(document_id) == (a, "uploaded", None, None)
    assert counts(a) == (1, 1)


class GetFails(FakeStorage):
    def get(self, key: str, *, max_bytes: int) -> GetResult:
        self.get_calls.append(key)
        return StorageUnavailable("down")


class ReuploadedBetween(FakeStorage):
    """head 와 get 사이에 같은 키로 다시 올라온 저장소: get 이 다른 ETag 의 바이트를 준다."""

    def get(self, key: str, *, max_bytes: int) -> GetResult:
        self.get_calls.append(key)
        return ObjectBytes(data=build_pdf(9, text="Other"), etag='"another-etag"')


@pytest.mark.parametrize("storage_class", [GetFails, ReuploadedBetween], ids=["get-실패", "etag-다름"])
def test_a_failed_or_mismatched_read_confirms_without_measuring(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int], storage_class: type[FakeStorage]
) -> None:
    a, _ = companies
    probe = FakePdfProbe(PdfProbed(page_count=9, has_text=True))
    monkeypatch.setattr(services, "default_pdf_probe", lambda: probe)
    storage = storage_class()
    document_id = created(storage, a, build_pdf(1, text="Hi"))
    confirmed(storage, a, document_id)
    assert row_of(document_id) == (a, "uploaded", None, None)
    assert probe.calls == []  # 재지 않았다
    assert len(storage.get_calls) == 1  # 분모: 읽기는 했다


def test_the_probe_runs_outside_any_transaction_and_only_once(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    a, _ = companies
    seen: list[int] = []

    class Watching(FakePdfProbe):
        def probe(self, content: bytes, *, text_pages: int) -> ProbeResult:
            seen.append(len(connection.atomic_blocks))  # 열린 블록의 깊이
            return super().probe(content, text_pages=text_pages)

    probe = Watching(PdfProbed(page_count=3, has_text=False))
    monkeypatch.setattr(services, "default_pdf_probe", lambda: probe)
    storage = FakeStorage()
    content = build_pdf(3)
    document_id = created(storage, a, content)
    confirmed(storage, a, document_id)
    confirmed(storage, a, document_id)  # 이미 `uploaded` — 다시 재지 않는다
    assert probe.calls == [(content, 3)]  # 앞 TEXT_PROBE_PAGES 쪽
    # 업무 층의 시험은 저 스스로 블록 안에서 돈다 — 잴 때의 깊이가 시험의 깊이와 같다 = 서비스의 블록 밖
    assert seen == [len(connection.atomic_blocks)]
    assert row_of(document_id) == (a, "uploaded", 3, False)


def test_an_unreadable_answer_from_a_fake_probe_is_also_null(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    a, _ = companies
    monkeypatch.setattr(services, "default_pdf_probe", lambda: FakePdfProbe(PdfUnreadable("encrypted")))
    storage = FakeStorage()
    document_id = created(storage, a, build_pdf(1))
    confirmed(storage, a, document_id)
    assert row_of(document_id) == (a, "uploaded", None, None)


# ── 만들기의 보고 연도 ─────────────────────────────────────────────


def test_the_create_stores_the_report_year(companies: tuple[int, int]) -> None:
    a, _ = companies
    storage = FakeStorage()
    with_year = created(storage, a, b"12345", report_year=2025)
    without = created(storage, a, b"12345")
    years = dict(DocumentRow.unscoped.filter(pk__in=[with_year, without]).values_list("pk", "report_year"))
    assert years == {with_year: 2025, without: None}


# ── 문서 고치기(PATCH) ─────────────────────────────────────────────


def stored(company_id: int, *, status: str = "uploaded", previous: int | None = None, year: int | None = None) -> int:
    """문서 행 하나를 바로 심는다(올리기를 거치지 않음)."""
    row = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="7",
        file_name="a.pdf",
        storage_key=f"companies/{company_id}/documents/{uuid.uuid4()}/original",
        size_bytes=5,
        status=status,
        previous_document_id=previous,
        report_year=year,
    )
    return row.id


def chain_of(document_id: int) -> tuple[int | None, int | None]:
    row = DocumentRow.unscoped.get(pk=document_id)
    return row.previous_document_id, row.report_year


def test_the_update_changes_only_the_sent_fields(companies: tuple[int, int]) -> None:
    a, _ = companies
    first, second = stored(a), stored(a, year=2024)
    later = NOW + timedelta(hours=1)
    done = services.update_document(company_id=a, document_id=second, now=later, previous_document_id=first)
    assert isinstance(done, services.DocumentUpdated)
    assert (done.document.previous_document_id, done.document.report_year) == (first, 2024)  # 연도는 그대로
    assert chain_of(second) == (first, 2024)
    assert DocumentRow.unscoped.get(pk=second).updated_at == later
    again = services.update_document(company_id=a, document_id=second, now=NOW, previous_document_id=first)
    assert isinstance(again, services.DocumentUpdated)  # 같은 앞 판을 다시(멱등)
    services.update_document(company_id=a, document_id=second, now=NOW, report_year=None)
    assert chain_of(second) == (first, None)  # None = 지움, 앞 판은 그대로
    services.update_document(company_id=a, document_id=second, now=NOW, previous_document_id=None, report_year=2026)
    assert chain_of(second) == (None, 2026)


def test_the_update_refuses_documents_of_another_company_as_missing(companies: tuple[int, int]) -> None:
    a, b = companies
    mine, theirs = stored(b), stored(a)
    assert services.update_document(company_id=b, document_id=theirs, now=NOW, report_year=2025) == DocumentNotFound()
    refused = services.update_document(company_id=b, document_id=mine, now=NOW, previous_document_id=theirs)
    assert refused == services.PreviousNotFound()
    assert services.update_document(company_id=b, document_id=mine, now=NOW, previous_document_id=10**12) == (
        services.PreviousNotFound()
    )
    assert services.update_document(company_id=b, document_id=10**12, now=NOW, report_year=2025) == DocumentNotFound()
    assert chain_of(mine) == (None, None) and chain_of(theirs) == (None, None)  # 둘 다 그대로
    done = services.update_document(company_id=b, document_id=mine, now=NOW, report_year=2025)
    assert isinstance(done, services.DocumentUpdated)  # 분모: 제 문서는 고쳐진다


def test_the_update_needs_uploaded_documents_on_both_ends(companies: tuple[int, int]) -> None:
    a, _ = companies
    waiting, ready = stored(a, status="awaiting_upload"), stored(a)
    assert services.update_document(company_id=a, document_id=waiting, now=NOW, report_year=2025) == (
        services.DocumentNotUploaded()
    )
    assert services.update_document(company_id=a, document_id=ready, now=NOW, previous_document_id=waiting) == (
        services.PreviousNotUploaded()
    )
    assert chain_of(waiting) == (None, None) and chain_of(ready) == (None, None)


def test_the_update_refuses_self_fork_and_cycle(companies: tuple[int, int]) -> None:
    a, _ = companies
    one = stored(a)
    two = stored(a, previous=one)
    three = stored(a, previous=two)
    other = stored(a)
    assert services.update_document(company_id=a, document_id=one, now=NOW, previous_document_id=one) == ChainSelf()
    assert services.update_document(company_id=a, document_id=other, now=NOW, previous_document_id=one) == ChainFork()
    assert services.update_document(company_id=a, document_id=one, now=NOW, previous_document_id=three) == ChainCycle()
    assert [chain_of(i)[0] for i in (one, two, three, other)] == [None, one, two, None]  # 아무것도 안 바뀜
    tail = services.update_document(company_id=a, document_id=other, now=NOW, previous_document_id=three)
    assert isinstance(tail, services.DocumentUpdated)  # 분모: 끝에 잇는 것은 된다


def test_the_update_refuses_a_chain_over_the_limit(companies: tuple[int, int]) -> None:
    a, _ = companies
    last: int | None = None
    for _ in range(100):  # VERSION_CHAIN_MAX 판
        last = stored(a, previous=last)
    assert last is not None
    extra = stored(a)
    assert services.update_document(company_id=a, document_id=extra, now=NOW, previous_document_id=last) == (
        ChainTooLong(100)
    )
    assert chain_of(extra) == (None, None)


def test_the_two_rows_are_locked_in_id_order(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> None:
    a, _ = companies
    low, high = stored(a), stored(a)
    order: list[int] = []
    real = selectors.lock_document

    def spy(*, company_id: int, document_id: int) -> DocumentRow | None:
        order.append(document_id)
        return real(company_id=company_id, document_id=document_id)

    monkeypatch.setattr(selectors, "lock_document", spy)
    services.update_document(company_id=a, document_id=low, now=NOW, previous_document_id=high)
    services.update_document(company_id=a, document_id=high, now=NOW, previous_document_id=None)
    services.update_document(company_id=a, document_id=high, now=NOW, previous_document_id=low)
    assert order == [low, high, high, low, high]  # 작은 id 부터(대상이 크든 작든)


def test_a_racing_fork_is_stopped_by_the_unique_constraint(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    """갈래 검사를 「뒤 판 없음」으로 속이면 두 번째 쓰기가 DB 의 부분 UNIQUE 에 닿는다 → ChainFork, 행 그대로."""
    a, _ = companies
    first, second, third = stored(a), stored(a), stored(a)
    assert isinstance(
        services.update_document(company_id=a, document_id=second, now=NOW, previous_document_id=first),
        services.DocumentUpdated,
    )

    def no_later_version(*, company_id: int, document_id: int) -> int | None:
        return None

    monkeypatch.setattr(selectors, "next_id_of", no_later_version)
    raced = services.update_document(company_id=a, document_id=third, now=NOW, previous_document_id=first)
    assert raced == ChainFork()
    assert (chain_of(second)[0], chain_of(third)[0]) == (first, None)
