"""실행 출력 파일의 바이트 읽기(runs/service/services/files.py — RF1)를 가짜 저장소로 잰다. 순수 층(DB 0).

재는 것: 바이트 · 객체 없음 None · 상한 넘음 None · 거절·닿지 않음·저장소 없음은 503 셋의 code(글은 고객사 경로와 같음).
★ 바이트는 전부 지어낸 것이다(synthetic).
"""

from datetime import UTC, datetime

import pytest

from esgapi.core.exceptions import ApplicationError
from esgapi.core.resources.ports.storage import StorageDenied, StorageUnavailable
from esgapi.core.service.services import documents
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.service.selectors.runs import RunFile
from esgapi.runs.service.services.files import output_bytes
from tests.support.patches import plug_storage

KEY = "runs/1/1/out/report.xls"
FILE = RunFile(
    step=None,
    name="report.xls",
    media_type="application/vnd.ms-excel",
    storage_key=KEY,
    size_bytes=3,
    sha256="0" * 64,
    created_at=datetime(2026, 10, 22, tzinfo=UTC),
)


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=10)


def code_of(file: RunFile) -> tuple[str, str, str]:
    with pytest.raises(ApplicationError) as raised:
        output_bytes(file)
    return raised.value.kind, raised.value.code, raised.value.message


def test_the_bytes_of_the_files_key(storage: FakeStorage) -> None:
    storage.put(KEY, b"XLS")
    assert output_bytes(FILE) == b"XLS"
    assert storage.get_calls == [KEY]


def test_a_missing_object_is_none(storage: FakeStorage) -> None:
    assert output_bytes(FILE) is None


def test_an_object_over_the_cap_is_none(storage: FakeStorage) -> None:
    storage.put(KEY, b"X" * 11)  # 상한 10
    assert output_bytes(FILE) is None
    storage.put(KEY, b"X" * 10)  # 분모: 상한 안
    assert output_bytes(FILE) == b"X" * 10


def test_a_denial_is_storage_denied(storage: FakeStorage) -> None:
    storage.put(KEY, b"XLS")
    storage.fail_with = StorageDenied("거절(시험)")
    assert code_of(FILE) == ("unavailable", "storage_denied", "저장소가 요청을 거절했다")


def test_an_unreachable_store_is_storage_unavailable(storage: FakeStorage) -> None:
    storage.put(KEY, b"XLS")
    storage.fail_with = StorageUnavailable("닿지 못함(시험)")
    assert code_of(FILE) == ("unavailable", "storage_unavailable", "저장소에 닿지 못했다. 잠시 뒤 다시 시도해 달라")


def test_no_store_is_storage_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(documents, "default_storage", lambda: None)
    assert code_of(FILE) == ("unavailable", "storage_unconfigured", "이 서버에 원본 파일 저장소가 준비되어 있지 않다")
