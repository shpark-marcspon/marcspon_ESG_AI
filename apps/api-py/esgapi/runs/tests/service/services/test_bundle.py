"""실행 묶음의 넣기(runs/service/services/bundle.py — RX1a)를 진짜 DB 로 잰다: 그 회사로 넣고 임대 NULL·셈 칸 그대로,
id·company_id·시각·(실행) lease_expires_at·(하위) run_id 가 실리면 ValueError, restore_times 는 실행·단계의 두 시각을
원래 값으로(남의 회사 행이면 RestoreError).
★a(발주서 §2-1): create() 는 created_at·updated_at 을 넣은 때로 찍는다(넘긴 값을 덮는다 — 그래서 시각 칸을 받지 않는다),
  QuerySet.update() 는 auto_now 를 안 채운다(되돌린 updated_at 이 남는다).
★ 숫자는 전부 지어낸 것이다(synthetic).
"""

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from django.db import transaction

from esgapi.runs.models import RunFileRow, RunResultRow, RunRow, RunStepRow
from esgapi.runs.service.services.bundle import (
    RestoreError,
    insert_files,
    insert_results,
    insert_run,
    insert_steps,
    restore_times,
)

pytestmark = pytest.mark.django_db
OLD = datetime(2026, 9, 1, tzinfo=UTC)
OLDER = datetime(2026, 8, 1, tzinfo=UTC)
RUN = {
    "module": "probe",
    "flow_id": "probe.flow@1",
    "options": {"zeta": 1, "alpha": 2},
    "versions": {"flow": "probe.flow@1", "aiSettingId": None},
    "purpose": "service",
    "status": "done",
    "attempts": 2,
    "stalled_attempts": 1,
    "progress_attempt": 2,
    "created_by_user_id": 9,
    "started_at": OLDER,
    "finished_at": OLD,
    "document_id": None,
}


def test_a_run_and_its_rows_go_in(companies: tuple[int, int]) -> None:
    b = companies[1]
    before = datetime.now(UTC)
    run_id = insert_run(company_id=b, fields=RUN)
    step_ids = insert_steps(
        company_id=b,
        run_id=run_id,
        steps=[{"name": "judge", "position": 0, "status": "done", "data": {"z": 1, "a": 2}, "partial": None}],
    )
    insert_results(
        company_id=b, run_id=run_id, results=[{"position": 0, "schema_version": "probe.result@1", "body": [1]}]
    )
    insert_files(
        company_id=b,
        run_id=run_id,
        files=[
            {
                "step": None,
                "name": "out.json",
                "media_type": "application/json",
                "storage_key": f"runs/{b}/{run_id}/out/out.json",
                "size_bytes": 2,
                "sha256": "f" * 64,
            }
        ],
    )
    run = RunRow.for_company(b).get(pk=run_id)
    assert (run.attempts, run.stalled_attempts, run.progress_attempt, run.lease_expires_at) == (2, 1, 2, None)
    assert (run.started_at, run.finished_at, list(run.options)) == (OLDER, OLD, ["zeta", "alpha"])
    assert run.created_at >= before  # ★a: create 는 넣은 때
    assert list(RunStepRow.for_company(b).values_list("id", flat=True)) == list(step_ids)
    assert RunResultRow.for_company(b).get(run_id=run_id).created_at >= before
    assert RunFileRow.for_company(b).get(run_id=run_id).storage_key == f"runs/{b}/{run_id}/out/out.json"

    restore_times(company_id=b, table="run_runs", times={run_id: (OLDER, OLD)})
    restore_times(company_id=b, table="run_steps", times={step_ids[0]: (OLDER, OLD)})
    run = RunRow.for_company(b).get(pk=run_id)
    step = RunStepRow.for_company(b).get(pk=step_ids[0])
    assert (run.created_at, run.updated_at, step.created_at, step.updated_at) == (OLDER, OLD, OLDER, OLD)


@pytest.mark.parametrize("extra", ["id", "company_id", "created_at", "updated_at", "lease_expires_at"])
def test_a_run_refuses_carried_ids_and_times(companies: tuple[int, int], extra: str) -> None:
    with pytest.raises(ValueError, match=extra):
        insert_run(company_id=companies[1], fields=RUN | {extra: None})
    assert not RunRow.for_company(companies[1]).exists()


@pytest.mark.parametrize("extra", ["id", "company_id", "run_id", "created_at"])
def test_child_rows_refuse_carried_ids(companies: tuple[int, int], extra: str) -> None:
    b = companies[1]
    run_id = insert_run(company_id=b, fields=RUN)
    with pytest.raises(ValueError, match=extra):
        insert_results(
            company_id=b,
            run_id=run_id,
            results=[{"position": 0, "schema_version": "probe.result@1", "body": [1], extra: 1}],
        )


def test_restoring_another_companys_row_fails(companies: tuple[int, int]) -> None:
    a, b = companies
    run_id = insert_run(company_id=a, fields=RUN)
    with pytest.raises(RestoreError), transaction.atomic():
        restore_times(company_id=b, table="run_runs", times={run_id: (OLDER, OLD)})
    assert RunRow.for_company(a).get(pk=run_id).created_at != OLDER


def test_only_the_run_tables_are_restored(companies: tuple[int, int]) -> None:
    with pytest.raises(ValueError, match="run_results"):
        restore_times(company_id=companies[1], table=cast("Any", "run_results"), times={1: (OLDER, OLD)})
