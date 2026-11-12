# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실행기(runs/tasks.py)의 꼴과 갈래 표. 순수 층: 태스크를 돌리지 않는다(돌리는 것은 test_executor.py — 업무 층)."""

import ast
from pathlib import Path
from typing import Any, cast

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.db import IntegrityError, InterfaceError, OperationalError

from esgapi.config.celery import app
from esgapi.core.flows.binding import RunOptionsRejected, RunRetryLater
from esgapi.core.flows.types import FlowOutputError, FlowStepFailed, SegmentFatal, SegmentKey
from esgapi.core.llm.embedding import EmbeddingFailed, EmbedMeta, EmbedProviderFailed, EmbedTimedOut
from esgapi.core.llm.errors import LiveSetupError
from esgapi.runs import tasks
from esgapi.runs.service.services.runs import RunDeferred, RunFailed

SOURCE = Path(tasks.__file__).read_text(encoding="utf-8")


def test_every_retry_has_no_celery_limit() -> None:
    """Celery 의 기본 3 이 시도 상한의 셈(진행 없는 시도만)을 넷째에서 끊지 않게 — 늘 max_retries=None(N3)."""
    retries = [
        node
        for node in ast.walk(ast.parse(SOURCE))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "retry"
    ]
    assert len(retries) == 1  # 분모
    for call in retries:
        limits = [k for k in call.keywords if k.arg == "max_retries"]
        assert len(limits) == 1 and isinstance(limits[0].value, ast.Constant) and limits[0].value.value is None


def test_the_task_is_registered_by_its_name() -> None:
    assert tasks.execute_task.name == "runs.execute"
    assert "runs.execute" in app.tasks  # 갈고리가 보내는 이름(core/calc/jobs.py 의 RUN_TASK_NAME)으로 선다
    assert app.tasks["runs.execute"].run.__name__ == "execute_run"


def failed_step(cause: BaseException) -> FlowStepFailed:
    err = FlowStepFailed("judge", completed={}, partial=None)
    err.__cause__ = cause
    return err


def fail(step: str | None, code: str) -> RunFailed:
    return RunFailed(step, code, tasks.RUN_ERROR_MESSAGES[code])


META = EmbedMeta.__new__(EmbedMeta)  # 갈래의 꼴만 본다(칸은 읽지 않는다)


@pytest.mark.parametrize(
    "err",
    [
        SoftTimeLimitExceeded(),
        RunRetryLater("저장소에 닿지 못함"),
        OperationalError("끊김"),
        InterfaceError("닫힘"),
        failed_step(SoftTimeLimitExceeded()),
        failed_step(RunRetryLater("x")),
        failed_step(EmbeddingFailed(EmbedTimedOut(message="t", meta=META))),
        failed_step(EmbeddingFailed(EmbedProviderFailed(status=503, retryable=True, message="m", meta=META))),
    ],
    ids=lambda e: type(e).__name__ + ("<" + type(e.__cause__).__name__ + ">" if e.__cause__ else ""),
)
def test_transient_failures_defer(err: Exception) -> None:
    assert tasks.outcome_of(err, run_id=1) == RunDeferred()


@pytest.mark.parametrize(
    ("err", "expected"),
    [
        (
            failed_step(ValueError("문서 글이 섞일 수 있는 원문")),
            fail("judge", "step_error"),
        ),
        (
            failed_step(LiveSetupError("키가 없다")),
            fail("judge", "setup_error"),
        ),
        (
            failed_step(FlowOutputError("x")),
            fail("judge", "step_output_invalid"),
        ),
        (
            failed_step(EmbeddingFailed(EmbedProviderFailed(status=400, retryable=False, message="m", meta=META))),
            fail("judge", "embedding_failed"),
        ),
        (
            RunOptionsRejected("쪽 범위가 틀렸다"),
            fail(None, "options_rejected"),
        ),
        (tasks.StorageRefused("403"), fail(None, "storage_denied")),
        (IntegrityError("크기 CHECK"), fail(None, "internal")),
        (KeyError("x"), fail(None, "internal")),
    ],
    ids=[
        "step-value-error",
        "step-live-setup",
        "step-output",
        "embedding-permanent",
        "options",
        "storage-denied",
        "integrity",
        "other",
    ],
)
def test_other_failures_end_the_run_with_a_fixed_code_and_message(err: Exception, expected: RunFailed) -> None:
    got = tasks.outcome_of(err, run_id=1)
    assert got == expected
    assert isinstance(got, RunFailed) and "원문" not in got.message  # 예외의 글은 표에 싣지 않는다


def test_the_segment_task_is_registered_by_its_name() -> None:
    """RM1b: 구획 쪽지의 태스크(`runs.segment`)도 같은 파일에서 선다(autodiscover). 다시 넣기(retry)는 없다."""
    assert tasks.segment_task.name == "runs.segment"
    assert "runs.segment" in app.tasks  # 큐 넣기가 보내는 이름(core/calc/jobs.py 의 SEGMENT_TASK_NAME)
    assert app.tasks["runs.segment"].run.__name__ == "execute_segment"
    registered = sorted(name for name in app.tasks if name.startswith("runs."))
    assert registered == ["runs.execute", "runs.segment"]  # 분모: 태스크 둘 · retry 하나(위 시험)


def test_the_segment_note_calls_its_outside_work_only_outside_the_blocks() -> None:
    """RM1b 7a 허락 Qn2 ③: 쪽지 넣기·구획 돌리기·계획 다시 셈은 잡기·끝냄 블록 밖(커밋 뒤)에서만 부른다."""
    from esgapi.core.tests.test_transaction_rules import outside_calls

    inside, outside = outside_calls(SOURCE)
    assert inside == []
    names = {site.split(":", 1)[1] for site in outside}
    assert {"enqueue_segment", "enqueue_run", "run_segment", "plan_segments", "run_flow"} <= names


def test_the_serial_fanout_folds_a_run_fatal_error_into_segment_fatal() -> None:
    """직렬(상한 1)도 쪽지와 같은 치명 집합: segment_failed 가 행을 쓰지 않고 SegmentFatal(원래 예외)을 던진다."""
    events = tasks.RowEvents(company_id=1, run_id=1, attempt=1, deadline=0.0, lease_s=1, storage=cast(Any, None))
    cause = LiveSetupError("키가 없다")
    with pytest.raises(SegmentFatal) as caught:
        events.segment_failed(
            "probe.x@1", "spread", SegmentKey(kind="block", span="b1", document_sha256=None, parser_version=None), cause
        )
    assert caught.value.cause is cause
    assert caught.value.__cause__ is cause


def test_the_segment_cap_seam_defaults_to_two() -> None:
    """바꿔 끼우지 않은 이음매: 기본 상한 2(감독 답 Q3) — 1 이면 펼침이 RM1a 직렬로 돌아간다(끄는 꼴)."""
    from esgapi.runs.calc.segments import SEGMENT_PARALLEL_DEFAULT

    assert tasks.segment_parallel() == SEGMENT_PARALLEL_DEFAULT == 2
