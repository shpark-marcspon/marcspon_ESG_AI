"""올림 확인 둘이 같은 문서에서 겹칠 때: 일감은 하나다. 앱 역할, 연결 둘, 진짜 커밋.

W1a 가 남긴 빈 곳(MARC-ISSUE-57 의 2번)을 메운다: services.confirm_upload 의 「FOR UPDATE 로 다시 읽기」와
「갱신 1행」을 지키는 테스트가 없었다. 제품 코드(core/service/services/documents.py)는 0줄이다.

만드는 법: 스레드 둘이 각자의 연결·각자의 transaction.atomic(durable=True) 에서 confirm_upload 를 부른다.
저장소의 head 에 장벽을 두어 **둘 다 `awaiting_upload` 를 읽은 뒤에야** 잠금으로 간다.
  - 잠금이 있으면: 하나가 잠그고 적고 일감을 만든다. 다른 하나는 기다렸다가 `uploaded` 를 읽고 지나간다. 일감 1.
  - 잠금이 없으면(심은 파손 15): 둘째의 갱신이 0행이라 던진다. 「갱신 1행」 검사까지 빼면(16) 일감이 2 가 된다.

★ 무효 조건: 스레드 둘 + 연결 둘로 만든 경합이다. gunicorn 일꾼 둘의 요청으로 잰 것이 아니다.
"""

import threading
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from django.db import connections, transaction

from esgapi.core.resources.ports.storage import HeadResult
from esgapi.core.service.services import documents as services
from esgapi.core.tests.resource_fakes import FakeStorage
from tests.security.conftest import count

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
PDF = b"%PDF-1.7 synthetic " + b"x" * 81


class BarrierStorage(FakeStorage):
    """head 가 장벽에서 기다린다: 두 스레드가 다 head 에 닿아야(둘 다 문서를 읽은 뒤다) 지나간다."""

    def __init__(self) -> None:
        super().__init__()
        self.barrier = threading.Barrier(2)

    def head(self, key: str) -> HeadResult:
        self.barrier.wait(timeout=10)
        return super().head(key)


def test_two_confirms_of_the_same_document_make_one_job(owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    storage = BarrierStorage()
    with transaction.atomic(durable=True):
        created = services.create_document(
            company_id=a,
            uploaded_by="user-1",
            file_name="a.pdf",
            size_bytes=len(PDF),
            max_upload_bytes=1000,
            storage=storage,
        )
    assert isinstance(created, services.DocumentCreated)
    document_id = created.document.id
    storage.put(created.document.storage_key, PDF)

    results: list[object] = []
    errors: list[BaseException] = []
    sent: list[int] = []
    lock = threading.Lock()

    def enqueue(**kwargs: Any) -> None:
        with lock:
            sent.append(kwargs["job_id"])

    def confirm() -> None:
        try:
            with transaction.atomic(durable=True):
                result = services.confirm_upload(
                    company_id=a, document_id=document_id, storage=storage, now=NOW, enqueue=enqueue
                )
            with lock:
                results.append(result)
        except BaseException as err:
            with lock:
                errors.append(err)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=confirm) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]

    assert errors == []  # 어느 쪽도 던지지 않았다
    assert len(storage.head_calls) == 2  # 둘 다 `awaiting_upload` 를 읽고 head 까지 갔다(경합이 실제로 만들어졌다)
    assert [type(result).__name__ for result in results] == ["UploadConfirmed", "UploadConfirmed"]
    assert count(owner, "run_jobs") == 1  # 일감 1
    assert owner.execute("SELECT status, attempts, company_id FROM run_jobs").fetchall() == [("queued", 0, a)]
    assert owner.execute("SELECT status FROM core_documents").fetchall() == [("uploaded",)]
    # 두 답이 같은 일감 하나를 말하고, 커밋 뒤 갈고리는 그 일감으로 두 번 불렸다(같은 쪽지 둘: 워커의 잡기가 거른다).
    job_ids = {job.id for result in results if isinstance(result, services.UploadConfirmed) for job in result.jobs}
    assert len(job_ids) == 1 and sorted(sent) == sorted(job_ids) * 2
