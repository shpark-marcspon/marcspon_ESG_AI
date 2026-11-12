"""읽기. 실행 묶음(RX1a — runbundle 앱의 export_runs·import_runs)이 쓰는 실행 넷의 행. 쓰지 않는다.

    bundle_rows(company_id, run_ids)                      실행·단계·결과·파일·구획 행 그대로(칸 이름(attname) → 값 —
                                                          options·data·partial 은 풀린 dict). 표마다 한 쿼리
                                                          (구획은 RM1c — (실행, 단계, 차례))
    pick_runs(company_id, module, since, until, limit)    그 모듈의 실행 가운데 since ≤ created_at < until 인 것의
                                                          (id, 상태)(id 오름 — 많아야 limit + 1 줄: 넘침은
                                                          부르는 쪽이 본다)
    taken_keys(company_id, keys)                          그 회사에 이미 있는 Idempotency-Key(만든 사람 무관 — 같은 묶음
                                                          두 번 넣기를 막는 재료, Q4)

★ 조회마다 회사 조건을 적는다. 실행 표를 여는 문은 `_bundle_runs` 하나(bundle_rows 도 그 위 — 회사 없는 길 0),
  단계·결과·파일 표는 <표>.for_company(company_id) 로 바로 연다. 남의 회사 실행은 빠진다(「없음」과 같다).
★ 실행을 고르는 판정(상태·닫힘)은 부르는 쪽(runbundle)의 일이다. 여기는 행만 준다.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from esgapi.runs.models import RunFileRow, RunResultRow, RunRow, RunSegmentRow, RunStepRow

if TYPE_CHECKING:
    from django.db.models import QuerySet


@dataclass(frozen=True, slots=True)
class BundleRows:
    """표마다 행(id 오름 — 단계·결과는 (실행, 차례), 파일은 (실행, id)). 행은 칸 이름 → 값."""

    runs: list[dict[str, object]]
    steps: list[dict[str, object]]
    results: list[dict[str, object]]
    files: list[dict[str, object]]
    segments: list[dict[str, object]]


def _bundle_runs(company_id: int) -> "QuerySet[RunRow]":
    """그 회사의 실행 행. 이 파일에서 run_runs 를 읽는 문은 여기 하나다."""
    return RunRow.for_company(company_id)


def bundle_rows(*, company_id: int, run_ids: Collection[int]) -> BundleRows:
    if not run_ids:
        return BundleRows(runs=[], steps=[], results=[], files=[], segments=[])
    runs = [dict(row) for row in _bundle_runs(company_id).filter(pk__in=run_ids).order_by("id").values()]
    found = [row["id"] for row in runs]
    steps = RunStepRow.for_company(company_id).filter(run_id__in=found).order_by("run_id", "position").values()
    results = RunResultRow.for_company(company_id).filter(run_id__in=found).order_by("run_id", "position").values()
    files = RunFileRow.for_company(company_id).filter(run_id__in=found).order_by("run_id", "id").values()
    segments = (
        RunSegmentRow.for_company(company_id).filter(run_id__in=found).order_by("run_id", "step", "position").values()
    )
    return BundleRows(
        runs=runs,
        steps=[dict(row) for row in steps],
        results=[dict(row) for row in results],
        files=[dict(row) for row in files],
        segments=[dict(row) for row in segments],
    )


def pick_runs(
    *, company_id: int, module: str, since: datetime, until: datetime, limit: int
) -> tuple[tuple[int, str], ...]:
    rows = (
        _bundle_runs(company_id)
        .filter(module=module, created_at__gte=since, created_at__lt=until)
        .order_by("id")
        .values_list("id", "status")[: limit + 1]
    )
    return tuple((run_id, status) for run_id, status in rows)


def taken_keys(*, company_id: int, keys: Collection[str]) -> frozenset[str]:
    if not keys:
        return frozenset()
    found = _bundle_runs(company_id).filter(idempotency_key__in=keys).values_list("idempotency_key", flat=True)
    return frozenset(key for key in found if key is not None)
