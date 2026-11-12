# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""[모두 받기] zip(GET …/batches/{batch_key}/archive — 밴드 TR3b §3-2-6). 업무 층, 저장소는 가짜(FakeStorage).

넣는 것 = 파트 최신 실행이 done·digest done 이면 문체마다 files.autofix 이름 그대로(`<part>-<이름>`). 빠진 항목은 머리
X-Archive-Missing·로그 한 줄, 넣은 것 0 이면 409, 크기 합 상한 409, 저장소 503 셋, 감사 한 줄.
TRS1(MARC-ISSUE-324): 응답은 흘려보내는 FileResponse(통째 바이트 복사 0 — 문턱 넘으면 임시 파일), 남의 회사·없는 문서는
묶음 하나 보기와 같은 404.
★ 바이트·이름은 지어낸 것이다(실제 Word 0 — 바이트는 표지 글).
"""

import hashlib
import io
import logging
import tracemalloc
import zipfile
from collections.abc import Iterable
from typing import cast

import pytest
from django.db import connection
from django.http import FileResponse
from django.test import Client

from esgapi.core.resources.ports.storage import StorageDenied, StorageUnavailable
from esgapi.core.service.services import documents as document_services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.translation.service.actions import archive
from esgapi.translation.tests.service import seed
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

B1 = "00000000-0000-4000-8000-0000000000a1"
A_FILE, B_FILE = "translation-autofix-a.docx", "translation-autofix-b.docx"


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)


def ab_digest() -> dict[str, object]:
    digest = seed.digest()
    variant = digest["variants"][0]
    digest["variants"] = [variant, {**variant, "label": "B", "files": {**variant["files"], "autofix": B_FILE}}]
    return digest


def url(document_id: int, key: str = B1) -> str:
    return f"/api/translation/documents/{document_id}/batches/{key}/archive"


def body(got: object) -> bytes:
    """흘려보낸 응답의 바이트(오류 응답은 그대로 content)."""
    if isinstance(got, FileResponse):
        return b"".join(cast("Iterable[bytes]", got.streaming_content))
    return cast("bytes", getattr(got, "content"))  # noqa: B009


def entries(data: object) -> dict[str, bytes]:
    raw = data if isinstance(data, bytes) else body(data)
    with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
        return {name: zipped.read(name) for name in zipped.namelist()}


def audit_rows() -> list[tuple[object, ...]]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT action, event, target_kind, target_id, target_label FROM core_audit_events ORDER BY id")
        return list(cursor.fetchall())


def test_two_finished_parts_with_a_and_b_are_three_entries_named_as_the_digest(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    story = seed.run(a, doc, "story", batch_id=B1, digest_body=ab_digest())
    general = seed.run(a, doc, "general", batch_id=B1)
    seed.run(a, doc, "ceo_message", batch_id=B1, digest_body=seed.digest("rejected", autofix=None))  # not_run — 빠짐
    for run_id, name, data in ((story, A_FILE, b"story-a"), (story, B_FILE, b"story-b"), (general, A_FILE, b"gen-a")):
        seed.output(a, run_id, name, data, storage)
    got = client.get(url(doc))
    assert got.status_code == 200, got.content.decode()
    assert entries(got) == {
        f"story-{A_FILE}": b"story-a",
        f"story-{B_FILE}": b"story-b",
        f"general-{A_FILE}": b"gen-a",
    }
    assert got["Content-Type"] == "application/zip"
    assert got["Content-Disposition"] == f'attachment; filename="translation-{doc}-{B1[:8]}.zip"'
    assert (got["X-Archive-Missing"], got["X-Content-Type-Options"]) == ("0", "nosniff")
    assert audit_rows()[-1] == (
        "download",
        "translation_batch_downloaded",
        "document",
        doc,
        f"translation-{doc}-{B1[:8]}.zip",
    )


def test_a_part_whose_latest_is_not_done_is_left_out(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    old = seed.run(a, doc, "story", batch_id=B1)
    seed.output(a, old, A_FILE, b"old", storage)
    seed.run(a, doc, "story", batch_id=B1, status="processing")  # 같은 파트를 다시 돌리는 중 — 옛 파일을 넣지 않는다
    general = seed.run(a, doc, "general", batch_id=B1)
    seed.output(a, general, A_FILE, b"gen", storage)
    assert set(entries(client.get(url(doc)))) == {f"general-{A_FILE}"}


def test_a_missing_object_or_row_is_left_out_with_the_header_and_a_log_line(
    client: Client, companies: tuple[int, int], storage: FakeStorage, caplog: pytest.LogCaptureFixture
) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    story = seed.run(a, doc, "story", batch_id=B1, digest_body=ab_digest())
    seed.output(a, story, A_FILE, b"story-a", storage)
    seed.output(a, story, B_FILE, None, storage)  # 행은 있는데 객체가 없다
    general = seed.run(a, doc, "general", batch_id=B1)  # 이름은 digest 에 있는데 행이 없다
    with caplog.at_level(logging.WARNING, logger=archive.__name__):
        got = client.get(url(doc))
    assert got.status_code == 200
    assert (got["X-Archive-Missing"], set(entries(got))) == ("2", {f"story-{A_FILE}"})
    lines = sorted(r.getMessage() for r in caplog.records if r.name == archive.__name__)
    assert lines == sorted(
        [
            f"translation_archive_missing run_id={story} name={B_FILE}",
            f"translation_archive_missing run_id={general} name={A_FILE}",
        ]
    )


def test_nothing_finished_is_409(client: Client, companies: tuple[int, int], storage: FakeStorage) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    seed.run(a, doc, "story", batch_id=B1, status="processing")
    seed.run(a, doc, "general", batch_id=B1, digest_body=seed.digest(autofix=None))  # 자동수정 안 돎
    got = client.get(url(doc))
    assert (got.status_code, got.json()["error"]["code"]) == (409, "NO_FINISHED_PARTS")
    assert [r for r in audit_rows() if r[1] == "translation_batch_downloaded"] == []


def test_over_the_size_cap_is_409_before_reading_bytes(
    client: Client, companies: tuple[int, int], storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    monkeypatch.setattr(archive, "ARCHIVE_MAX_BYTES", 10)
    doc = seed.document(a)
    story = seed.run(a, doc, "story", batch_id=B1)
    seed.output(a, story, A_FILE, b"x" * 11, storage)
    got = client.get(url(doc))
    assert (got.status_code, got.json()["error"]["code"]) == (409, "ARCHIVE_TOO_LARGE")
    assert storage.get_calls == []  # 바이트를 읽기 전에 거절
    monkeypatch.setattr(archive, "ARCHIVE_MAX_BYTES", 11)
    within = client.get(url(doc))
    assert within.status_code == 200  # 분모: 상한 안이면 지난다
    within.close()  # 흘려보낸 응답 — 다 읽지 않으면 시험 쪽이 닫는다(서버는 WSGI 가 close 를 부른다)


@pytest.mark.parametrize(
    ("fail", "code"),
    [
        (None, "STORAGE_UNCONFIGURED"),
        (StorageDenied("403"), "STORAGE_DENIED"),
        (StorageUnavailable("x"), "STORAGE_UNAVAILABLE"),
    ],
)
def test_storage_failures_are_the_runs_503s(
    client: Client,
    companies: tuple[int, int],
    storage: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
    fail: StorageDenied | StorageUnavailable | None,
    code: str,
) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    story = seed.run(a, doc, "story", batch_id=B1)
    seed.output(a, story, A_FILE, b"a", storage)
    if fail is None:
        monkeypatch.setattr(document_services, "default_storage", lambda: None)
    else:
        storage.fail_with = fail
    got = client.get(url(doc))
    assert (got.status_code, got.json()["error"]["code"]) == (503, code)


def test_an_old_run_without_a_digest_gives_its_autofix_outputs(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    old = seed.run(a, doc, "story", digest_body=False)
    seed.output(a, old, A_FILE, b"old-a", storage)
    seed.output(a, old, "translation-bilingual-a.docx", b"bilingual", storage)  # 자동수정 갈래만
    got = client.get(url(doc, f"run-{old}"))
    assert entries(got) == {f"story-{A_FILE}": b"old-a"}


def test_the_archive_is_404_where_the_batch_is(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, b = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    batched = seed.run(a, doc, "story", batch_id=B1)
    theirs = seed.document(b)
    seed.run(b, theirs, "story", batch_id=B1)
    for document, key in ((doc, "RUN-1"), (doc, f"run-{batched}"), (theirs, B1), (doc + 1000, B1)):
        assert client.get(url(document, key)).status_code == 404, key


# ── TRS1(MARC-ISSUE-324) ──


def noise(size: int) -> bytes:
    """잘 줄지 않는 지어낸 바이트(sha256 사슬 — 늘 같은 값)."""
    return b"".join(hashlib.sha256(i.to_bytes(4, "big")).digest() for i in range(size // 32))


def test_the_archive_streams_a_file_response_with_the_same_headers(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    story = seed.run(a, doc, "story", batch_id=B1)
    seed.output(a, story, A_FILE, b"story-a", storage)
    got = client.get(url(doc))
    assert got.status_code == 200
    assert isinstance(got, FileResponse) and got.streaming
    assert entries(got) == {f"story-{A_FILE}": b"story-a"}
    assert got["Content-Type"] == "application/zip"
    assert got["Content-Disposition"] == f'attachment; filename="translation-{doc}-{B1[:8]}.zip"'
    assert (got["X-Archive-Missing"], got["X-Content-Type-Options"]) == ("0", "nosniff")


def test_an_archive_over_the_spool_threshold_is_the_same_zip_from_a_temporary_file(
    client: Client, companies: tuple[int, int], storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """문턱을 넘는 가짜 파일 — 임시 파일로 넘어가도 항목·바이트가 같다. 큰 쪽의 최고 메모리도 잰다(보고용 출력)."""
    a, _ = companies
    login(client, tenant_id="tenant-a")
    monkeypatch.setattr(archive, "SPOOL_MAX_BYTES", 1024)
    rolled: list[bool] = []
    write = archive._write  # pyright: ignore[reportPrivateUsage]

    def watched(target: object, rows: object) -> list[str]:
        found = write(target, rows)  # type: ignore[arg-type]
        rolled.append(bool(getattr(target, "_rolled", False)))
        return found

    monkeypatch.setattr(archive, "_write", watched)
    doc = seed.document(a)
    story = seed.run(a, doc, "story", batch_id=B1, digest_body=ab_digest())
    big_a, big_b = noise(512 * 1024), b"B" * 300_000  # 안 줄어드는 512KiB·잘 줄어드는 300KB
    seed.output(a, story, A_FILE, big_a, storage)
    seed.output(a, story, B_FILE, big_b, storage)
    tracemalloc.start()
    got = client.get(url(doc))
    raw = body(got)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"TRS1 archive peak_bytes={peak} zip_bytes={len(raw)} input_bytes={len(big_a) + len(big_b)}")
    assert rolled == [True]  # 문턱을 넘어 임시 파일로
    assert entries(raw) == {f"story-{A_FILE}": big_a, f"story-{B_FILE}": big_b}


def test_a_missing_document_is_404_even_with_a_batch(
    client: Client, companies: tuple[int, int], storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """묶음은 있어도 문서가 그 회사에 없으면(documents_of 에 없음) 404 — batches.batch 와 같은 문서 확인, 바이트 읽기 0.
    남의 회사 문서를 가리키는 실행은 run_runs 의 같은 회사 FK 가 막아 지을 수 없다(남의 회사 문서 404 는 위 시험)."""
    a, _ = companies
    login(client, tenant_id="tenant-a")
    mine = seed.document(a)
    seed.output(a, seed.run(a, mine, "story", batch_id=B1), A_FILE, b"a", storage)
    asked: list[object] = []

    def none_of(**kwargs: object) -> dict[int, object]:
        asked.append(kwargs)
        return {}

    monkeypatch.setattr(archive.document_selectors, "documents_of", none_of)
    got = client.get(url(mine))
    assert (got.status_code, got.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert asked == [{"company_id": a, "document_ids": [mine]}]
    assert storage.get_calls == []
