"""runs 의 순수 규칙(runs/calc): 파일 키, 잡기 판정과 시도 상한의 셈, 협조 마감, 오류 code 표. DB 없음."""

import importlib
from datetime import UTC, datetime, timedelta

import pytest

from esgapi.core.calc.jobs import AlreadyFinished, Exhausted, LeaseHeld, Take
from esgapi.core.flows.types import FlowOutputError
from esgapi.core.llm.errors import LiveSetupError
from esgapi.runs import models
from esgapi.runs.calc.claims import RunClaim, run_claim
from esgapi.runs.calc.deadline import DEADLINE_MARGIN_S, RunYield, deadline_of
from esgapi.runs.calc.errors import RUN_ERROR_MESSAGES, RUN_FATAL_ERRORS, STEP_ERROR_CODES, run_fatal, step_error_code
from esgapi.runs.calc.keys import FILE_NAME, file_key

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def test_keys_put_outputs_and_step_files_under_their_own_run() -> None:
    assert file_key(company_id=7, run_id=41, step=None, name="report.xlsx") == "runs/7/41/out/report.xlsx"
    assert file_key(company_id=7, run_id=41, step="extract", name="p.json") == "runs/7/41/steps/extract/p.json"
    assert FILE_NAME.pattern == models.RUN_FILE_NAME  # 표의 CHECK 와 같은 꼴


@pytest.mark.parametrize(
    ("step", "name"), [(None, "../x"), (None, "a/b"), (None, ".."), (None, ""), ("Bad", "x"), ("../x", "y")]
)
def test_keys_refuse_names_that_would_leave_their_place(step: str | None, name: str) -> None:
    with pytest.raises(ValueError, match="꼴"):
        file_key(company_id=7, run_id=41, step=step, name=name)


def claim(
    status: str, *, lease: datetime | None = None, attempts: int = 0, stalled: int = 0, progress: int | None = None
) -> RunClaim:
    return run_claim(
        status=status,
        lease_expires_at=lease,
        attempts=attempts,
        stalled_attempts=stalled,
        progress_attempt=progress,
        now=NOW,
        max_attempts=3,
    )


def test_a_queued_run_is_taken_without_counting() -> None:
    got = claim("queued", attempts=2, stalled=2, progress=1)
    assert (got.decision, got.stalled_attempts) == (Take(3), 2)  # 앞 시도의 셈은 끝내기가 이미 했다


def test_finished_and_held_runs_are_not_taken() -> None:
    assert claim("done").decision == AlreadyFinished()
    assert claim("failed").decision == AlreadyFinished()
    held = NOW + timedelta(seconds=1)
    assert claim("processing", lease=held, attempts=1).decision == LeaseHeld(held)


def test_a_dead_attempt_without_progress_is_counted_before_taking() -> None:
    got = claim("processing", lease=NOW, attempts=2, stalled=0, progress=1)  # 시도 2 는 진행을 남기지 않았다
    assert (got.decision, got.stalled_attempts) == (Take(3), 1)
    assert claim("processing", lease=None, attempts=1, progress=None).stalled_attempts == 1  # 임대 없음도 지남


def test_a_dead_attempt_with_progress_is_compared_before_the_increment() -> None:
    """진행을 남긴 시도(progress_attempt = 그 시도 번호)가 끝내기 없이 죽으면 셈 그대로(P20: 늘린 뒤 견주면 +1)."""
    got = claim("processing", lease=NOW, attempts=2, stalled=1, progress=2)
    assert (got.decision, got.stalled_attempts) == (Take(3), 1)


def test_the_limit_counts_stalled_attempts_not_attempts() -> None:
    assert claim("queued", attempts=9, stalled=2, progress=9).decision == Take(10)  # 시도는 많아도 진행이 있었다
    assert claim("queued", attempts=3, stalled=3).decision == Exhausted()
    got = claim("processing", lease=NOW, attempts=3, stalled=2, progress=2)
    assert (got.decision, got.stalled_attempts) == (Exhausted(), 3)


def test_run_yield_is_not_an_exception() -> None:
    """흐름·단계·LLM 의 `except Exception` 이 잡지 못해야 한다(P19)."""
    assert issubclass(RunYield, BaseException)
    assert not issubclass(RunYield, Exception)
    caught = False
    try:
        try:
            raise RunYield("마감")
        except Exception:  # 단계가 삼키려 해도
            caught = True
    except RunYield:
        pass
    assert caught is False


def test_the_deadline_leaves_a_margin_before_the_soft_limit() -> None:
    assert deadline_of(started=100.0, soft_limit_s=240) == 100.0 + 240 - DEADLINE_MARGIN_S


def test_every_error_code_fits_the_column_and_has_a_fixed_message() -> None:
    assert all(len(code) <= 64 for code in RUN_ERROR_MESSAGES)
    assert all(0 < len(message) <= 500 for message in RUN_ERROR_MESSAGES.values())
    assert set(STEP_ERROR_CODES.values()) <= set(RUN_ERROR_MESSAGES)
    assert step_error_code(FlowOutputError) == "step_output_invalid"
    assert step_error_code(KeyError) == "step_error"
    assert step_error_code(KeyError, default="internal") == "internal"
    assert "step_error" in RUN_ERROR_MESSAGES and "internal" in RUN_ERROR_MESSAGES


@pytest.mark.parametrize("key", sorted(STEP_ERROR_CODES))
def test_every_step_error_key_names_a_real_exception_class_by_its_module_path(key: str) -> None:
    # 정의 자리의 모듈을 import 해 견준다(정적 import 아님 — runs 시험이 greenwash 를 import 하지 않게)
    module, _, qualname = key.rpartition(".")
    found = getattr(importlib.import_module(module), qualname)
    assert isinstance(found, type) and issubclass(found, BaseException)
    assert (found.__module__, found.__qualname__) == (module, qualname)
    assert step_error_code(found) == STEP_ERROR_CODES[key]


def test_a_same_named_exception_from_another_module_is_not_folded() -> None:
    # 표의 것과 이름·qualname 이 같고 모듈만 다른 예외(시험 안에서 만든 것) — 클래스 이름으로 접던 꼴이면 엉뚱한 code
    for name in ("NoTextLayer", "LiveSetupError"):
        same_name = type(name, (Exception,), {"__module__": "tests.elsewhere", "__qualname__": name})
        assert (same_name.__name__, same_name.__qualname__) == (name, name)
        assert step_error_code(same_name) == "step_error"
        assert step_error_code(same_name, default="internal") == "internal"


def test_a_missing_ai_setup_folds_into_setup_error_and_others_stay_step_error() -> None:
    assert step_error_code(LiveSetupError) == "setup_error"
    assert step_error_code(LiveSetupError, default="internal") == "setup_error"
    assert step_error_code(KeyError) == "step_error"  # 분모: 표 밖
    assert "setup_error" in RUN_ERROR_MESSAGES


@pytest.mark.parametrize("key", sorted(RUN_FATAL_ERRORS))
def test_every_run_fatal_name_is_a_real_class_with_a_step_error_code(key: str) -> None:
    """RM1b 635-1: 치명 표(여섯)의 이름은 실제 예외 클래스이고 오류 code 표에 있다(새 code 0)."""
    module, _, qualname = key.rpartition(".")
    found = getattr(importlib.import_module(module), qualname)
    assert isinstance(found, type) and issubclass(found, BaseException)
    assert run_fatal(found)
    assert key in STEP_ERROR_CODES


def test_the_run_fatal_table_has_six_names_and_matches_exactly() -> None:
    assert len(RUN_FATAL_ERRORS) == 6  # 분모: 감독 답 Q2 의 여섯
    assert not run_fatal(FlowOutputError)  # 단계 산출 꼴은 그 구획의 실패
    assert not run_fatal(KeyError)

    class Narrower(FlowOutputError):
        pass

    assert not run_fatal(Narrower)
