"""일감을 잡는 순수 규칙(esgapi/core/calc/jobs.py). 순수 층: DB 없음."""

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import get_args

import pytest

from esgapi.core.calc.documents import JOB_KINDS, JOB_STATUSES, JobStatus
from esgapi.core.calc.jobs import (
    JOB_ERROR_CODES,
    MAX_ERROR_CODE_CHARS,
    AlreadyFinished,
    Exhausted,
    LeaseHeld,
    Take,
    claim_decision,
    lease_until,
    task_name,
)

NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=UTC)
MAX = 3
# 임대의 네 경우: 없음 · 안 지남 · 딱 지금 · 지남
LEASES: dict[str, datetime | None] = {
    "없음": None,
    "안 지남": NOW + timedelta(seconds=1),
    "딱 지금": NOW,
    "지남": NOW - timedelta(seconds=1),
}
# 시도의 세 경우: 0 · 상한-1 · 상한
ATTEMPTS = {"0": 0, "상한-1": MAX - 1, "상한": MAX}

# 답을 글자로 적은 표. (상태, 임대, 시도) → 답. 4 × 4 × 3 = 48칸.
#   T<n> = Take(n) · F = AlreadyFinished · H = LeaseHeld · X = Exhausted
# ★ 「딱 지금」은 지난 것이다(Deferred 가 임대를 지금으로 당긴다. 같은 시각의 쪽지가 잡을 수 있어야 한다).
# ★ queued 는 임대를 보지 않는다(임대는 processing 의 것이다).
TABLE = """
queued      없음     0=T1  상한-1=T3  상한=X
queued      안 지남  0=T1  상한-1=T3  상한=X
queued      딱 지금  0=T1  상한-1=T3  상한=X
queued      지남     0=T1  상한-1=T3  상한=X
processing  없음     0=T1  상한-1=T3  상한=X
processing  안 지남  0=H   상한-1=H   상한=H
processing  딱 지금  0=T1  상한-1=T3  상한=X
processing  지남     0=T1  상한-1=T3  상한=X
done        없음     0=F   상한-1=F   상한=F
done        안 지남  0=F   상한-1=F   상한=F
done        딱 지금  0=F   상한-1=F   상한=F
done        지남     0=F   상한-1=F   상한=F
failed      없음     0=F   상한-1=F   상한=F
failed      안 지남  0=F   상한-1=F   상한=F
failed      딱 지금  0=F   상한-1=F   상한=F
failed      지남     0=F   상한-1=F   상한=F
"""


def _written_table() -> dict[tuple[str, str, str], str]:
    cells: dict[tuple[str, str, str], str] = {}
    for line in TABLE.strip().splitlines():
        status, rest = line.split(maxsplit=1)
        lease = next(name for name in sorted(LEASES, key=len, reverse=True) if rest.startswith(name))
        for cell in rest[len(lease) :].split():
            attempts, answer = cell.split("=")
            cells[(status, lease, attempts)] = answer
    return cells


def _answer(status: JobStatus, lease: datetime | None, attempts: int) -> str:
    decision = claim_decision(status, lease, attempts, NOW, MAX)
    if isinstance(decision, Take):
        return f"T{decision.attempt}"
    if isinstance(decision, AlreadyFinished):
        return "F"
    if isinstance(decision, LeaseHeld):
        assert decision.until == lease
        return "H"
    assert isinstance(decision, Exhausted)
    return "X"


def test_the_claim_decision_is_exactly_the_written_table() -> None:
    written = _written_table()
    assert len(written) == len(JOB_STATUSES) * len(LEASES) * len(ATTEMPTS) == 48
    actual = {
        (status, lease_name, attempts_name): _answer(status, lease, attempts)
        for status in JOB_STATUSES
        for lease_name, lease in LEASES.items()
        for attempts_name, attempts in ATTEMPTS.items()
    }
    assert actual == written


def test_a_lease_equal_to_now_has_passed() -> None:
    assert claim_decision("processing", NOW, 1, NOW, MAX) == Take(2)
    assert claim_decision("processing", NOW + timedelta(microseconds=1), 1, NOW, MAX) == LeaseHeld(
        NOW + timedelta(microseconds=1)
    )


def test_a_finished_job_is_never_taken_whatever_the_lease_or_attempts() -> None:
    for status in ("done", "failed"):
        for lease in LEASES.values():
            for attempts in range(MAX + 2):
                assert claim_decision(status, lease, attempts, NOW, MAX) == AlreadyFinished()


def test_lease_until_adds_seconds() -> None:
    assert lease_until(NOW, 90) == NOW + timedelta(seconds=90)


def test_task_names_are_made_from_the_job_kinds_only() -> None:
    assert [task_name(kind) for kind in JOB_KINDS] == ["jobs.parse"]
    for bad in ("", "translate", "parse ", "jobs.parse"):
        with pytest.raises(ValueError, match="모르는 일감의 종류"):
            task_name(bad)


def test_error_codes_fit_the_column_and_are_distinct() -> None:
    assert JOB_ERROR_CODES == (
        "object_changed",
        "object_missing",
        "object_too_large",
        "storage_denied",
        "storage_unconfigured",
        "parser_unconfigured",
        "document_missing",
        "attempts_exhausted",
    )
    assert len(set(JOB_ERROR_CODES)) == len(JOB_ERROR_CODES)
    assert all(len(code) <= MAX_ERROR_CODE_CHARS for code in JOB_ERROR_CODES)
    assert set(get_args(JobStatus)) == {"queued", "processing", "done", "failed"}


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


# 사본에서 뜻이 없다: mutmut 이 심은 트램펄린(mutmut.mutation.trampoline import)을 소스에서 읽는다(scripts/weekly.sh ②)
@pytest.mark.not_under_mutmut
def test_the_pure_rules_import_neither_celery_nor_django() -> None:
    """`.importlinter` 계약 (다)는 django·ninja·psycopg 를 막는다. celery·kombu 는 금지 목록에 없어 여기서 본다."""
    path = Path(__file__).resolve().parents[1] / "calc" / "jobs.py"
    assert _imported_roots(path) == {"dataclasses", "datetime", "typing", "esgapi"}
