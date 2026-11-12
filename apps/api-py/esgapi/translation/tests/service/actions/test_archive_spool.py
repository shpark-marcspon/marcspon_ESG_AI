"""[모두 받기] zip 의 spool(밴드 TRS2, MARC-ISSUE-399) — DB 없이: 뷰가 응답에 넘기기 전에 던지면 spool 을 닫는다(R3),
항목은 조각으로 흘려 써 writestr 와 같은 항목이고 메모리 봉우리가 항목 크기를 따라 자라지 않는다(R2).
갈래별 길(404·409·503·감사)은 test_archive.py(업무 층). ★ 바이트·이름은 지어낸 것이다.
"""

import io
import os
import tempfile
import time
import tracemalloc
import zipfile
from types import SimpleNamespace
from typing import Any, cast

import pytest
from django.core.signals import request_finished
from django.db import close_old_connections, connections
from django.http import FileResponse, HttpRequest

from esgapi.translation.service.actions import archive
from esgapi.translation.service.apis import translation

MiB = 1024 * 1024
B1 = "00000000-0000-4000-8000-0000000000a1"


class Spool(io.BytesIO):
    """닫혔는지 셀 수 있는 spool 대역."""

    closes = 0

    def close(self) -> None:
        self.closes += 1
        super().close()


@pytest.fixture
def found(monkeypatch: pytest.MonkeyPatch) -> archive.Archive:
    spool = Spool(b"PK\x05\x06" + b"\0" * 18)
    got = archive.Archive(name="translation-7-00000000.zip", data=spool, entries=("1-a.docx",), missing=0)

    def permitted(request: object, operation: str) -> object:
        return SimpleNamespace(kind="user", user_id="1")

    def company_of(principal: object) -> int:
        return 1

    def made(**kwargs: object) -> archive.Archive:
        return got

    monkeypatch.setattr(translation, "permitted", permitted)
    monkeypatch.setattr(translation, "company_of", company_of)
    monkeypatch.setattr(translation.archive_actions, "archive", made)
    return got


def test_the_spool_is_closed_when_the_audit_line_raises(
    found: archive.Archive, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(**kwargs: object) -> None:
        raise RuntimeError("감사 실패")

    monkeypatch.setattr(translation, "record_event", broken)
    with pytest.raises(RuntimeError, match="감사 실패"):
        translation.batch_archive(cast(HttpRequest, object()), 7, B1)
    spool = cast(Spool, found.data)
    assert spool.closed and spool.closes == 1


def _close_like_the_server(response: FileResponse) -> None:
    """응답을 닫되 request_finished 의 DB 갈고리는 뗀다(Django 시험 클라이언트 꼴): close() 가 그 신호를 쏘면 같은
    워커의 앞 시험이 남긴 연결을 되짚다 DB 막개에 걸린다(MARC-ISSUE-420). 이 시험이 보는 것은 spool 뿐이다."""
    request_finished.disconnect(close_old_connections)
    try:
        response.close()
    finally:
        request_finished.connect(close_old_connections)


def _handed_over(found: archive.Archive, monkeypatch: pytest.MonkeyPatch) -> FileResponse:
    def recorded(**kwargs: object) -> None:
        return None

    monkeypatch.setattr(translation, "record_event", recorded)
    response = translation.batch_archive(cast(HttpRequest, object()), 7, B1)
    assert isinstance(response, FileResponse)
    return response


def test_a_handed_over_spool_is_left_to_the_response(found: archive.Archive, monkeypatch: pytest.MonkeyPatch) -> None:
    response = _handed_over(found, monkeypatch)
    spool = cast(Spool, found.data)
    assert not spool.closed
    _close_like_the_server(response)
    assert spool.closed


def test_closing_the_response_does_not_reach_a_connection_left_by_an_earlier_test(
    found: archive.Archive, monkeypatch: pytest.MonkeyPatch
) -> None:
    """앞 `django_db` 시험이 이 워커에 연결을 남긴 꼴을 심는다 — 묶음 차례와 상관없이 같은 결과여야 한다."""
    response = _handed_over(found, monkeypatch)
    monkeypatch.setattr(connections["default"], "connection", object())
    _close_like_the_server(response)
    assert cast(Spool, found.data).closed
    assert request_finished.disconnect(close_old_connections)  # 다시 붙어 있다(뗀 채면 이 워커의 뒤 시험이 달라진다)
    request_finished.connect(close_old_connections)


def _zip_of(rows: dict[str, bytes], put: Any) -> bytes:
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, data in rows.items():
            put(zipped, name, data)
    return target.getvalue()


def test_a_streamed_entry_is_the_entry_writestr_makes(monkeypatch: pytest.MonkeyPatch) -> None:
    """이름·권한·압축·크기·CRC·내용이 writestr 와 같다(시각은 같은 초로 못 박는다)."""

    def fixed() -> float:
        return 1_790_000_000.0

    monkeypatch.setattr(time, "time", fixed)  # archive·zipfile 이 같은 time 모듈을 본다
    monkeypatch.setattr(archive, "WRITE_CHUNK", 1000)  # 조각 경계를 여러 번 지나게
    rows = {"1-translation-autofix-a.docx": os.urandom(4321), "2-빈.docx": b"", "3-b.docx": "가상 ".encode() * 3000}
    put = archive._put  # pyright: ignore[reportPrivateUsage]
    streamed, whole = _zip_of(rows, put), _zip_of(rows, zipfile.ZipFile.writestr)
    assert streamed == whole


def test_a_large_entry_does_not_hold_its_compressed_copy() -> None:
    """문턱(SPOOL_MAX_BYTES 8MiB)보다 큰 항목 20MiB — 받은 바이트 밖의 파이썬 메모리 봉우리가 writestr(잰 값 49.6MiB)의
    압축본 한 벌·spool 넘김 복사 없이 문턱 + 조각 안쪽이다(TRS2 잰 값 10.6MiB)."""
    blob = os.urandom(20 * MiB)  # 재기 전에 지음 — 봉우리에서 빠진다
    row = cast(Any, SimpleNamespace(name="a.docx"))

    def output_bytes(got: object) -> bytes:
        return blob

    with (
        pytest.MonkeyPatch.context() as patch,
        tempfile.SpooledTemporaryFile(max_size=archive.SPOOL_MAX_BYTES) as spool,
    ):
        patch.setattr(archive.file_services, "output_bytes", output_bytes)
        tracemalloc.start()
        try:
            entries = archive._write(spool, [("1-a.docx", 1, row)])  # pyright: ignore[reportPrivateUsage]
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        with zipfile.ZipFile(spool) as zipped:
            assert entries == ["1-a.docx"] and zipped.read("1-a.docx") == blob
    assert peak < archive.SPOOL_MAX_BYTES + 4 * archive.WRITE_CHUNK, f"{peak / MiB:.1f}MiB"
