"""PDF 재기 어댑터(core/resources/pdf.py — X1b-2a). 순수 층: DB 없이, 진짜 자식 프로세스(이 파이썬 + pypdfium2)로.

PDF 는 시험이 짓는다(resource_fakes.build_pdf — 저장소에 .pdf 파일 0). 갈래(시간 넘김·죽음·이상 출력·쪽 0·띄우기 실패)는
이음매 `_CHILD`(자식 글)와 `subprocess.run` 을 바꿔 끼워 낸다.
"""

import ast
import io
import logging
import signal
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from types import FrameType
from typing import Any

import pypdf
import pytest

from esgapi.core.resources import pdf
from esgapi.core.resources.ports.pdf import PdfProbed, PdfUnreadable
from esgapi.core.tests.resource_fakes import FakeStorage, build_pdf

SOURCE = Path(pdf.__file__)


def probe(content: bytes, *, text_pages: int = 3) -> object:
    return pdf.PdfiumProbe().probe(content, text_pages=text_pages)


@pytest.fixture
def short_timeout(monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    """자식의 벽시계 한도를 1초로, 시험 자신의 한도(SIGALRM)를 한도 + 2초로. 한도가 빠지면 시험이 스스로 빨개진다."""
    monkeypatch.setattr(pdf, "PDF_PROBE_TIMEOUT_S", 1)

    def expired(signum: int, frame: FrameType | None) -> None:
        raise AssertionError("자식의 시간 한도가 없다: 시험의 한도(한도 + 2초)가 먼저 왔다")

    before = signal.signal(signal.SIGALRM, expired)
    signal.alarm(1 + 2)
    try:
        yield 1
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, before)


def test_a_pdf_with_text_gives_its_page_count_and_true() -> None:
    assert probe(build_pdf(5, text="Hello")) == PdfProbed(page_count=5, has_text=True)


def test_a_pdf_without_a_text_layer_gives_false() -> None:
    assert probe(build_pdf(4)) == PdfProbed(page_count=4, has_text=False)
    assert probe(build_pdf(2, text="   ")) == PdfProbed(page_count=2, has_text=False)  # 공백만 든 쪽


def test_only_the_first_text_pages_count() -> None:
    assert probe(build_pdf(3, text="Hello"), text_pages=1) == PdfProbed(page_count=3, has_text=True)
    assert probe(build_pdf(3, text="Hello"), text_pages=0) == PdfProbed(page_count=3, has_text=False)  # 분모


def test_bytes_that_are_not_a_pdf_are_not_pdf() -> None:
    assert probe(b"hello") == PdfUnreadable("not_pdf")
    assert probe(b"") == PdfUnreadable("not_pdf")


def test_a_password_protected_pdf_is_encrypted() -> None:
    writer = pypdf.PdfWriter(clone_from=pypdf.PdfReader(io.BytesIO(build_pdf(2, text="Hi"))))
    writer.encrypt("secret", algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    assert probe(out.getvalue()) == PdfUnreadable("encrypted")


def test_a_child_that_hangs_is_killed_within_the_limit(
    monkeypatch: pytest.MonkeyPatch, short_timeout: int, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(pdf, "_CHILD", "import time; time.sleep(30)")
    started = time.monotonic()
    with caplog.at_level(logging.WARNING, logger=pdf.__name__):
        assert probe(build_pdf(1, text="Hi")) == PdfUnreadable("timeout")
    assert time.monotonic() - started < short_timeout + 1
    assert "reason=timeout" in caplog.text


def test_a_child_that_dies_by_a_signal_is_crashed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf, "_CHILD", "import os, signal; os.kill(os.getpid(), signal.SIGKILL)")
    assert probe(build_pdf(1)) == PdfUnreadable("crashed")


@pytest.mark.parametrize(
    "child",
    [
        "print('not json')",
        "print('[1, 2]')",
        "import json; print(json.dumps({'pages': '3', 'texts': []}))",
        "import json; print(json.dumps({'pages': True, 'texts': []}))",
        "import json; print(json.dumps({'pages': 3, 'texts': [1]}))",
        "import sys; sys.exit(3)",
    ],
)
def test_odd_output_or_a_nonzero_exit_is_error(monkeypatch: pytest.MonkeyPatch, child: str) -> None:
    monkeypatch.setattr(pdf, "_CHILD", child)
    assert probe(build_pdf(1)) == PdfUnreadable("error")


def test_zero_pages_is_empty_not_a_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """pdfium 은 쪽 0 인 PDF 를 열지 않지만(잰), 자식이 0 을 말하면 값으로 내지 않는다(page_count ≥1 CHECK)."""
    monkeypatch.setattr(pdf, "_CHILD", "import json; print(json.dumps({'pages': 0, 'texts': []}))")
    assert probe(build_pdf(1)) == PdfUnreadable("empty")


def test_output_past_the_limit_is_error_and_never_read_whole(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """부모는 자식 출력을 PDF_PROBE_OUTPUT_BYTES 까지만 읽는다 — 넘으면 값 없음(가지 리뷰 X1b-2a).

    상한과 그 두 배(자식의 RLIMIT_FSIZE) 사이의 바른 JSON 은 부모의 상한이 막는다(경고 줄로 확인)."""
    limit = pdf.PDF_PROBE_OUTPUT_BYTES
    child = f"import json; print(json.dumps({{'pages': 1, 'texts': ['x' * {limit + 1000}]}}))"
    monkeypatch.setattr(pdf, "_CHILD", child)
    with caplog.at_level(logging.WARNING, logger=pdf.__name__):
        assert probe(build_pdf(1)) == PdfUnreadable("error")
    assert f"output_over_limit={limit}" in caplog.text


def test_a_child_that_prints_megabytes_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """검증 실측의 꼴(압축 글 스트림 쪽 하나 → 글 100만 자, JSON 3.06MB). 값이 아니라 갈래로 접힌다(자식의
    RLIMIT_FSIZE 가 쓰기를 끊거나, 그 한도가 없는 플랫폼이면 부모의 상한이 막는다)."""
    monkeypatch.setattr(pdf, "_CHILD", "import json; print(json.dumps({'pages': 1, 'texts': ['x' * 3_060_000]}))")
    assert probe(build_pdf(1)) == PdfUnreadable("error")


def test_the_child_hands_back_only_the_head_of_each_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """자식은 쪽마다 strip() 뒤 앞 PDF_PROBE_TEXT_CHARS 자만 낸다: 상한을 1 KiB 로 줄여도 2,000 자 쪽 셋이 잰다.
    양성 대조: 같은 상한에서 자식이 글을 통째 내면 넘는다(쪽 셋 × 2,000 자 > 1 KiB)."""
    monkeypatch.setattr(pdf, "PDF_PROBE_OUTPUT_BYTES", 1024)
    assert 3 * 2000 > 1024
    assert probe(build_pdf(3, text="A" * 2000)) == PdfProbed(page_count=3, has_text=True)


def test_the_child_inherits_no_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """믿지 못할 PDF 를 여는 자식에게 DB URL·비밀 키를 물려주지 않는다(env={}).

    자식이 본 이름 수를 쪽 수로 돌려받는다."""
    names = ("DATABASE_URL", "DJANGO_SECRET_KEY", "SECRET_KEY", "X1B2A_PARENT_ONLY")
    for name in names:
        monkeypatch.setenv(name, "parent-only")
    child = f"import json, os; print(json.dumps({{'pages': 1 + sum(n in os.environ for n in {names!r}), 'texts': []}}))"
    monkeypatch.setattr(pdf, "_CHILD", child)
    assert probe(build_pdf(1)) == PdfProbed(page_count=1, has_text=False)


@pytest.mark.parametrize("raised", [OSError("no such file"), subprocess.SubprocessError("preexec_fn failed")])
def test_failing_to_start_the_child_is_error(monkeypatch: pytest.MonkeyPatch, raised: Exception) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise raised

    monkeypatch.setattr(pdf.subprocess, "run", refuse)
    assert probe(build_pdf(1)) == PdfUnreadable("error")


def test_a_platform_without_rlimits_still_measures_and_leaves_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """setrlimit 이 안 되는 플랫폼(macOS 의 RLIMIT_AS): 조용히 넘기지 않고 경고 줄.

    자식은 fork 된 사본이라 바꿔 낀 setrlimit 을 본다(preexec_fn 은 exec 앞에 돈다)."""

    def unsupported(*args: Any) -> None:
        raise ValueError("not supported")

    monkeypatch.setattr(pdf.resource, "setrlimit", unsupported)
    with caplog.at_level(logging.WARNING, logger=pdf.__name__):
        assert probe(build_pdf(2, text="Hi")) == PdfProbed(page_count=2, has_text=True)
    assert "pdf_probe_no_rlimit" in caplog.text


def test_the_parent_never_imports_pdfium() -> None:
    """부모 모듈은 pypdfium2 를 import 하지 않는다(자식 글 `_CHILD` 안에만 있다). 양성 대조: 자식 글에는 있다."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name.startswith("pypdfium2") for name in imported)
    assert "import pypdfium2" in getattr(pdf, "_CHILD")  # noqa: B009  이음매(비공개 이름)를 글자로 읽는다
    runs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run"
    ]
    assert len(runs) == 1 and {keyword.arg for keyword in runs[0].keywords} >= {"timeout", "preexec_fn"}


def test_stored_bytes_reads_only_the_object_with_the_same_etag() -> None:
    storage = FakeStorage()
    tag = storage.put("k", b"%PDF-1")
    assert pdf.stored_bytes(storage, "k", max_bytes=10, etag=tag) == b"%PDF-1"
    assert pdf.stored_bytes(storage, "k", max_bytes=10, etag='"other"') is None  # head 뒤에 다시 올림
    assert pdf.stored_bytes(storage, "k", max_bytes=3, etag=tag) is None  # 너무 큼
    assert pdf.stored_bytes(storage, "missing", max_bytes=10, etag=tag) is None
