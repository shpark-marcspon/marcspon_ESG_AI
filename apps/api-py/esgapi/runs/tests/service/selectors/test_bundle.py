"""실행 묶음이 읽는 실행 넷(runs/service/selectors/bundle.py — RX1a)을 진짜 DB 로 잰다: 그 회사의 그 실행만, 칸 전부,
options·data 는 쓴 열쇠 차례의 풀린 dict, pick_runs 의 모듈·시각 반열림 구간·limit + 1, taken_keys 는 만든 사람 무관.
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from pytest_django import DjangoAssertNumQueries

from esgapi.runs.models import RunFileRow, RunResultRow, RunRow, RunStepRow
from esgapi.runs.service.selectors.bundle import bundle_rows, pick_runs, taken_keys

pytestmark = pytest.mark.django_db


def a_run(company_id: int, *, module: str = "probe", user: int = 1, key: str | None = None) -> int:
    run = RunRow.for_company(company_id).create(
        company_id=company_id,
        module=module,
        flow_id=f"{module}.flow@1",
        status="done",
        options={"zeta": 1, "alpha": {"b": 2, "a": 1}},
        versions={"flow": f"{module}.flow@1"},
        created_by_user_id=user,
        idempotency_key=key,
        idempotency_sha256=None if key is None else "s" * 64,
    )
    RunStepRow.for_company(company_id).create(
        company_id=company_id, run_id=run.pk, name="judge", position=0, status="done", data={"z": 1, "a": 2}
    )
    RunResultRow.for_company(company_id).create(
        company_id=company_id, run_id=run.pk, position=0, schema_version="probe.result@1", body={"ok": True}
    )
    RunFileRow.for_company(company_id).create(
        company_id=company_id,
        run_id=run.pk,
        step=None,
        name="out.json",
        media_type="application/json",
        storage_key=f"runs/{company_id}/{run.pk}/out/out.json",
        size_bytes=2,
        sha256="f" * 64,
    )
    return run.pk


def test_the_rows_of_that_companys_runs(companies: tuple[int, int]) -> None:
    a, b = companies
    first, second, other = a_run(a), a_run(a), a_run(b)
    rows = bundle_rows(company_id=a, run_ids={second, first, other})
    assert [row["id"] for row in rows.runs] == [first, second]
    assert [row["run_id"] for row in rows.steps] == [first, second]
    assert [row["run_id"] for row in rows.results] == [first, second]
    assert [row["run_id"] for row in rows.files] == [first, second]
    assert set(rows.runs[0]) == {field.attname for field in RunRow._meta.concrete_fields}  # 분모: 칸 전부
    options, data = rows.runs[0]["options"], rows.steps[0]["data"]
    assert isinstance(options, dict) and isinstance(data, dict)  # 풀린 dict(감싼 꼴이 아니다)
    assert list(cast("dict[str, object]", options)) == ["zeta", "alpha"]  # 쓴 차례
    assert list(cast("dict[str, object]", data)) == ["z", "a"]
    assert bundle_rows(company_id=b, run_ids={first}).runs == []


def test_no_runs_no_query(companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries) -> None:
    with django_assert_num_queries(0):
        assert bundle_rows(company_id=companies[0], run_ids=()).runs == []


def test_pick_by_module_and_half_open_window(companies: tuple[int, int]) -> None:
    a, b = companies
    inside, edge, other_module = a_run(a), a_run(a), a_run(a, module="other")
    a_run(b)
    start = datetime(2026, 10, 1, tzinfo=UTC)
    RunRow.for_company(a).filter(pk=inside).update(created_at=start)
    RunRow.for_company(a).filter(pk=edge).update(created_at=start + timedelta(days=1))
    RunRow.for_company(a).filter(pk=other_module).update(created_at=start)
    picked = pick_runs(company_id=a, module="probe", since=start, until=start + timedelta(days=1), limit=10)
    assert picked == ((inside, "done"),)
    assert len(pick_runs(company_id=a, module="probe", since=start, until=start + timedelta(days=2), limit=1)) == 2


def test_taken_keys_whoever_made_them(companies: tuple[int, int]) -> None:
    a, b = companies
    a_run(a, user=1, key="11111111-1111-5111-8111-111111111111")
    a_run(a, user=2, key="22222222-2222-5222-8222-222222222222")
    a_run(b, user=1, key="33333333-3333-5333-8333-333333333333")
    keys = {"11111111-1111-5111-8111-111111111111", "22222222-2222-5222-8222-222222222222"}
    assert taken_keys(company_id=a, keys=keys | {"33333333-3333-5333-8333-333333333333"}) == keys
    assert taken_keys(company_id=b, keys=keys) == frozenset()
