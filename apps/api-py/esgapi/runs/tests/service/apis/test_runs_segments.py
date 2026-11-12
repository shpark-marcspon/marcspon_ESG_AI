"""`GET /runs/{id}` 의 구획 셈(RM1b ③ — T16·T15 의 API 몫). 업무 층.

펼침 단계 행만 `segments`(planned·pending·running·done·failed·firstStartedAt·lastFinishedAt)를 싣고 장벽 단계·등록 밖
흐름은 null 이다. 흐름은 경로의 REGISTRY 를 시험 레지스트리로 바꿔 끼운다(제품 흐름 등록 0 — RM1a 시험의 가짜 흐름).
구획 행은 손으로 쓴다(실행기가 쓰는 꼴). 값은 지어낸 것이다.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import segment_key_fields, segment_key_sha256
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.models import RunRow, RunSegmentRow, RunStepRow
from esgapi.runs.service.apis import runs as apis
from esgapi.runs.tests.test_executor_segments import PLAIN, SEGMENTED, Script, World, key_at, new_run
from tests.support.http import login

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 11, 10, 1, 0, tzinfo=UTC)


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    flows = FlowRegistry()
    for flow in (SEGMENTED, PLAIN):
        flows.register(flow)
    monkeypatch.setattr(apis, "REGISTRY", flows)
    return World(FakeStorage(), companies[0], Script())


def add_segments(world: World, run_id: int, statuses: list[str]) -> None:
    for position, status in enumerate(statuses):
        key = key_at(position + 1)
        started = None if status == "pending" else T0 + timedelta(minutes=position)
        finished = T0 + timedelta(minutes=position, seconds=30) if status in ("done", "failed") else None
        RunSegmentRow.for_company(world.company_id).create(
            company_id=world.company_id,
            run_id=run_id,
            step="spread",
            position=position,
            kind=key.kind,
            key=segment_key_fields(key),
            key_sha256=segment_key_sha256(key),
            status=status,
            attempts=0 if status == "pending" else 1,
            data={"square": position} if status == "done" else None,
            data_octets=14 if status == "done" else None,
            error_code="step_error" if status == "failed" else None,
            started_at=started,
            finished_at=finished,
        )


def set_step(world: World, run_id: int, name: str, status: str) -> None:
    RunStepRow.for_company(world.company_id).filter(run_id=run_id, name=name).update(status=status)


def steps_of(client: Client, run_id: int) -> dict[str, Any]:
    response = client.get(f"/api/runs/{run_id}")
    assert response.status_code == 200
    return {step["step"]: step for step in response.json()["steps"]}


def parsed(text: str | None) -> datetime | None:
    return None if text is None else datetime.fromisoformat(text)


def test_the_fanout_step_carries_its_counts_and_times_and_barriers_carry_null(client: Client, world: World) -> None:
    login(client)
    run_id = new_run(world)
    RunRow.for_company(world.company_id).filter(pk=run_id).update(
        status="failed", failed_step="spread", error_code="segments_failed", error_message="x"
    )
    set_step(world, run_id, "prepare", "done")
    set_step(world, run_id, "spread", "failed")
    statuses = ["done"] * 10 + ["failed"] * 2 + ["running"] * 3 + ["pending"] * 5
    add_segments(world, run_id, statuses)
    steps = steps_of(client, run_id)
    assert steps["prepare"]["segments"] is None
    assert steps["gather"]["segments"] is None
    segments = steps["spread"]["segments"]
    assert {k: segments[k] for k in ("planned", "pending", "running", "done", "failed")} == {
        "planned": 20,
        "pending": 5,
        "running": 3,  # fail_run 으로 끝난 실행에도 돌던 구획이 남는다
        "done": 10,
        "failed": 2,
    }
    assert parsed(segments["firstStartedAt"]) == T0
    assert parsed(segments["lastFinishedAt"]) == T0 + timedelta(minutes=11, seconds=30)  # 가장 늦은 끝
    assert segments["firstStartedAt"].endswith("+09:00")  # 서울 시각
    assert (steps["spread"]["done"], steps["spread"]["total"]) == (None, None)


@pytest.mark.parametrize("status", ["pending", "running", "failed"])
def test_before_planning_the_planned_count_is_null(client: Client, world: World, status: str) -> None:
    login(client)
    run_id = new_run(world)
    set_step(world, run_id, "spread", status)
    segments = steps_of(client, run_id)["spread"]["segments"]
    assert segments == {
        "planned": None,
        "pending": 0,
        "running": 0,
        "done": 0,
        "failed": 0,
        "firstStartedAt": None,
        "lastFinishedAt": None,
    }


def test_a_done_fanout_step_without_rows_planned_zero(client: Client, world: World) -> None:
    login(client)
    run_id = new_run(world)
    set_step(world, run_id, "spread", "done")
    assert steps_of(client, run_id)["spread"]["segments"]["planned"] == 0


def test_a_barrier_flow_and_an_unregistered_flow_carry_null_without_a_count_query(client: Client, world: World) -> None:
    login(client)
    plain = new_run(world, PLAIN)
    gone = new_run(world)
    RunRow.for_company(world.company_id).filter(pk=gone).update(flow_id="probe.gone@1")
    fanout = new_run(world)
    queries: dict[int, int] = {}
    for run_id in (plain, gone, fanout):
        client.get(f"/api/runs/{run_id}")  # 세션·캐시를 데운다
        with CaptureQueriesContext(connection) as captured:
            steps = steps_of(client, run_id)
        queries[run_id] = len(captured)
        if run_id != fanout:
            assert {name: step["segments"] for name, step in steps.items()} == dict.fromkeys(steps)
    assert queries[plain] == queries[gone]
    assert queries[fanout] == queries[plain] + 1  # 펼침 흐름만 셈 쿼리 하나


def test_another_companys_run_is_not_found(client: Client, world: World, companies: tuple[int, int]) -> None:
    login(client)
    other = World(FakeStorage(), companies[1], Script())
    run_id = new_run(other)
    add_segments(other, run_id, ["done", "pending"])
    response = client.get(f"/api/runs/{run_id}")
    assert response.status_code == 404
