"""쓰기. 실행 묶음(RX1a — runbundle 앱의 import_runs)이 넣는 실행 넷의 행과 시각 되돌리기.
HTTP 도 Celery 도 모른다.

    insert_run(company_id, fields)                    실행 행 하나 → 새 id
    insert_steps(company_id, run_id, steps)           단계 행들(data·partial 그대로) → 새 id(받은 차례)
    insert_results(company_id, run_id, results)       결과 행들
    insert_files(company_id, run_id, files)           파일 행들(키는 부르는 쪽이 runs/calc/keys.py 로 지어 온다)
    insert_segments(company_id, run_id, segments)     구획 행들(RM1c — 임대는 늘 NULL, 꼴 검사는 부르는 쪽의 문)
    restore_times(company_id, table, times)           run_runs·run_steps 의 created_at·updated_at 을 원래 값으로

★ 부르는 쪽(runbundle)의 durable 블록 안에서 부른다(여기의 블록은 세이브포인트다). 읽기는 여기 없다.
★ 행에 id·company_id·created_at·updated_at 이 실려 있으면 ValueError 다: 회사는 인자, id 는 DB 가 매긴다. 시각은 넣은
  때가 찍히고, 실행·단계만 restore_times 로 되돌린다(앱 역할에 UPDATE 가 있는 표 — 결과·파일은 넣은 때 그대로).
  실행의 lease_expires_at 은 늘 NULL 로 넣는다(아무도 안 쥔 실행). 셈 칸(attempts·stalled_attempts·progress_attempt)은
  그대로다.
★ 지우지 않는다(delete 0 — 앱 역할에 DELETE 도 없다).
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal

from django.db import transaction

from esgapi.runs.models import RunFileRow, RunResultRow, RunRow, RunSegmentRow, RunStepRow

NOT_CARRIED = frozenset({"id", "company_id", "created_at", "updated_at"})
NOT_CARRIED_RUN = NOT_CARRIED | {"lease_expires_at"}
NOT_CARRIED_CHILD = NOT_CARRIED | {"run_id"}
NOT_CARRIED_SEGMENT = NOT_CARRIED_CHILD | {"lease_expires_at"}


class RestoreError(Exception):
    """되돌린 행 수가 맞지 않는다. 부른 쪽의 트랜잭션이 되돌려진다."""


def _checked(row: Mapping[str, object], refused: frozenset[str], table: str) -> dict[str, object]:
    carried = refused & set(row)
    if carried:
        raise ValueError(f"{table} 행에 싣지 않는 칸이 있다: {sorted(carried)}")
    return dict(row)


def insert_run(*, company_id: int, fields: Mapping[str, object]) -> int:
    values = _checked(fields, NOT_CARRIED_RUN, "run_runs")
    with transaction.atomic():
        row = RunRow.for_company(company_id).create(company_id=company_id, lease_expires_at=None, **values)
    return row.id


def insert_steps(*, company_id: int, run_id: int, steps: Sequence[Mapping[str, object]]) -> tuple[int, ...]:
    rows = [_checked(step, NOT_CARRIED_CHILD, "run_steps") for step in steps]
    with transaction.atomic():
        made = [RunStepRow.for_company(company_id).create(company_id=company_id, run_id=run_id, **row) for row in rows]
    return tuple(row.id for row in made)


def insert_results(*, company_id: int, run_id: int, results: Sequence[Mapping[str, object]]) -> None:
    rows = [_checked(result, NOT_CARRIED_CHILD, "run_results") for result in results]
    with transaction.atomic():
        for row in rows:
            RunResultRow.for_company(company_id).create(company_id=company_id, run_id=run_id, **row)


def insert_files(*, company_id: int, run_id: int, files: Sequence[Mapping[str, object]]) -> None:
    rows = [_checked(file, NOT_CARRIED_CHILD, "run_files") for file in files]
    with transaction.atomic():
        for row in rows:
            RunFileRow.for_company(company_id).create(company_id=company_id, run_id=run_id, **row)


def insert_segments(*, company_id: int, run_id: int, segments: Sequence[Mapping[str, object]]) -> None:
    rows = [_checked(segment, NOT_CARRIED_SEGMENT, "run_segments") for segment in segments]
    with transaction.atomic():
        for row in rows:
            RunSegmentRow.for_company(company_id).create(
                company_id=company_id, run_id=run_id, lease_expires_at=None, **row
            )


def _restore_runs(company_id: int, times: Mapping[int, tuple[datetime, datetime]]) -> None:
    for run_id, (created_at, updated_at) in times.items():
        updated = RunRow.for_company(company_id).filter(pk=run_id).update(created_at=created_at, updated_at=updated_at)
        if updated != 1:
            raise RestoreError(f"run_runs 의 시각 되돌리기가 {updated}행이다(1행이어야 한다)")


def _restore_steps(company_id: int, times: Mapping[int, tuple[datetime, datetime]]) -> None:
    for step_id, (created_at, updated_at) in times.items():
        updated = (
            RunStepRow.for_company(company_id).filter(pk=step_id).update(created_at=created_at, updated_at=updated_at)
        )
        if updated != 1:
            raise RestoreError(f"run_steps 의 시각 되돌리기가 {updated}행이다(1행이어야 한다)")


def restore_times(
    *, company_id: int, table: Literal["run_runs", "run_steps"], times: Mapping[int, tuple[datetime, datetime]]
) -> None:
    """행 id → (created_at, updated_at). 한 행이라도 1행이 아니면 RestoreError. 표 T 밖의 표면 ValueError(쓰기 0)."""
    with transaction.atomic():
        if table == "run_runs":
            _restore_runs(company_id, times)
        elif table == "run_steps":
            _restore_steps(company_id, times)
        else:
            raise ValueError(f"시각을 되돌리는 표가 아니다: {table!r}")
