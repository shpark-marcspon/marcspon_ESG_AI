"""프로젝트의 원고작성 실행 읽기(service/actions/runs.py — 밴드 RPS1 B2). 순수 층: DB 0 — runs 의 selectors 셋과
drafting 의 project_head 를 가짜로 바꿔 끼우고(지어낸 Run·단계·결과), 거름·차례·쪽·셈을 손셈과 견준다.

    B2-1  거름: 옵션 projectId 가 그 프로젝트인 실행만(다른 프로젝트·projectId 없음·true 는 0) · 새 것 먼저(run_page
          차례 그대로) · 쪽 자름·count·isNext · 프로젝트 없음 NotFound(실행을 읽지 않음)
    B2-2  잎 셈(손셈): done 2·no_material 1·failed 1·not_run 1 · rejected(status.status) · 옛 결과·결과 없음·꼴 밖·
          failed 실행은 rejected·leaves null
    B2-3  progress: processing 의 선언 차례로 처음 running 단계 · running 없음 null · queued null(단계를 읽지 않음)
    B2-4  옵션 칸: base 없음 → baseRunId null·rebuild [] · versions.outlineId 없음 → null
    B2-5  latestRun: 프로젝트마다 가장 새 것 · 실행 없는 프로젝트는 열쇠 없음 · 빈 입력이면 run_page 0
    B2-6  묶음: 단계·결과는 쪽마다 한 번씩(processing·done id 만) · run_page 는 module drafting·RUN_SCAN_MAX·offset 0
"""

from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from esgapi.drafting.service.actions import runs as runs_actions
from esgapi.drafting.service.selectors import projects as selectors
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.selectors.runs import Run, RunPage, RunResult, RunStepLine

PROJECT = 7
OTHER = 8
T0 = datetime(2026, 1, 5, 1, 0, tzinfo=UTC)


def run(
    run_id: int,
    *,
    status: str = "done",
    project: object = PROJECT,
    base: dict[str, Any] | None = None,
    outline_id: object = 11,
) -> Run:
    options: dict[str, object] = {} if project is None else {"projectId": project}
    if base is not None:
        options["base"] = base
    created = T0 + timedelta(minutes=run_id)
    return Run(
        id=run_id,
        company_id=1,
        document_id=None,
        module="drafting",
        flow_id="drafting.draft@v2",
        options=options,
        versions={} if outline_id is None else {"outlineId": outline_id},
        purpose="service",
        status=status,
        attempts=1,
        stalled_attempts=0,
        progress_attempt=None,
        created_by_user_id=3,
        created_at=created,
        started_at=None,
        finished_at=created + timedelta(seconds=30) if status in ("done", "failed") else None,
        failed_step=None,
        error_code=None,
        error_message=None,
        resumed_from_run_id=None,
    )


def leaf(status: str) -> dict[str, Any]:
    return {"key": f"k-{status}", "outcome": {"status": status}}


def body(*statuses: str, rejected: bool = False) -> dict[str, Any]:
    status: dict[str, Any] = {"status": "rejected", "code": "too_large"} if rejected else {"status": "done"}
    return {"schemaVersion": "drafting.bullets@3", "status": status, "leaves": [leaf(s) for s in statuses]}


def step(name: str, position: int, status: str, done: int | None = None, total: int | None = None) -> RunStepLine:
    return RunStepLine(
        name=name, position=position, status=status, done=done, total=total, started_at=None, finished_at=None
    )


class Fakes:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, runs: list[Run]) -> None:
        self.runs = runs  # 새 것 먼저(run_page 차례)
        self.results: dict[int, tuple[RunResult, ...]] = {}
        self.steps: dict[int, tuple[RunStepLine, ...]] = {}
        self.pages: list[dict[str, Any]] = []
        self.step_calls: list[set[int]] = []
        self.result_calls: list[tuple[set[int], list[str] | None]] = []
        self.heads: list[int] = []
        self.projects: set[int] = {PROJECT, OTHER}
        monkeypatch.setattr(run_selectors, "run_page", self.run_page)
        monkeypatch.setattr(run_selectors, "step_lines_of", self.step_lines_of)
        monkeypatch.setattr(run_selectors, "results_of", self.results_of)
        monkeypatch.setattr(selectors, "project_head", self.project_head)

    def run_page(self, **kwargs: Any) -> RunPage:
        self.pages.append(kwargs)
        found = self.runs[kwargs["offset"] : kwargs["offset"] + kwargs["limit"]]
        return RunPage(count=len(self.runs), runs=tuple((r, None) for r in found))

    def step_lines_of(self, *, company_id: int, run_ids: Collection[int]) -> dict[int, tuple[RunStepLine, ...]]:
        self.step_calls.append(set(run_ids))
        return {i: self.steps[i] for i in run_ids if i in self.steps}

    def results_of(
        self, *, company_id: int, run_ids: Collection[int], schema_versions: Collection[str] | None = None
    ) -> dict[int, tuple[RunResult, ...]]:
        wanted = None if schema_versions is None else list(schema_versions)
        self.result_calls.append((set(run_ids), wanted))
        return {
            i: tuple(r for r in self.results[i] if wanted is None or r.schema_version in wanted)
            for i in run_ids
            if i in self.results
        }

    def project_head(self, *, company_id: int, project_id: int) -> object:
        self.heads.append(project_id)
        return object() if project_id in self.projects else None

    def result(self, run_id: int, shape: str, given: object) -> None:
        self.results[run_id] = (RunResult(position=0, schema_version=shape, body=given),)


def page(**kwargs: Any) -> dict[str, Any]:
    found = runs_actions.project_runs(company_id=1, project_id=kwargs.pop("project_id", PROJECT), **kwargs)
    assert isinstance(found, dict)
    return found


# ── B2-1 ──


def test_b2_1_only_runs_of_the_project_newest_first_and_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = Fakes(
        monkeypatch,
        [
            run(9, status="queued"),
            run(8, project=OTHER),
            run(7, status="processing"),
            run(6, project=None),
            run(5, project=True),  # bool 은 id 가 아니다(True == 1 이어도)
            run(4, status="failed"),
            run(3),
        ],
    )
    whole = page(limit=50, offset=0)
    assert (whole["count"], whole["isNext"], [r["id"] for r in whole["results"]]) == (4, False, [9, 7, 4, 3])
    cut = page(limit=2, offset=1)
    assert (cut["count"], cut["isNext"], [r["id"] for r in cut["results"]]) == (4, True, [7, 4])
    tail = page(limit=2, offset=3)
    assert (tail["count"], tail["isNext"], [r["id"] for r in tail["results"]]) == (4, False, [3])
    other = page(limit=50, offset=0, project_id=OTHER)
    assert [r["id"] for r in other["results"]] == [8]
    assert all(
        call == {"company_id": 1, "module": "drafting", "status": None, "document_id": None, "limit": 1000, "offset": 0}
        for call in fakes.pages
    )
    assert runs_actions.RUN_SCAN_MAX == 1000
    calls = len(fakes.pages)
    missing = runs_actions.project_runs(company_id=1, project_id=999, limit=20, offset=0)
    assert isinstance(missing, runs_actions.NotFound)
    assert len(fakes.pages) == calls  # 프로젝트가 없으면 실행을 읽지 않는다


# ── B2-2 ──


def test_b2_2_leaf_counts_and_rejected_by_hand(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = Fakes(monkeypatch, [run(i) for i in (16, 15, 14, 13, 12)] + [run(11, status="failed")])
    fakes.result(16, "drafting.bullets@3", body("done", "done", "no_material", "failed", "not_run"))
    fakes.result(15, "drafting.bullets@3", body("not_run", "not_run", rejected=True))
    fakes.result(14, "drafting.bullets@2", body("done"))  # 옛 꼴
    fakes.result(12, "drafting.bullets@3", {"schemaVersion": "drafting.bullets@3", "leaves": "x"})  # 꼴 밖
    fakes.result(11, "drafting.bullets@3", body("done"))  # failed 실행은 결과를 읽지 않는다
    rows = {r["id"]: r for r in page(limit=50, offset=0)["results"]}
    assert (rows[16]["rejected"], rows[16]["leaves"]) == (
        False,
        {"total": 5, "drafted": 2, "noMaterial": 1, "failed": 1, "notRun": 1},
    )
    assert (rows[15]["rejected"], rows[15]["leaves"]) == (
        True,
        {"total": 2, "drafted": 0, "noMaterial": 0, "failed": 0, "notRun": 2},
    )
    for old in (14, 13, 12, 11):  # 옛 결과 · 결과 없음 · 꼴 밖 · failed
        assert (rows[old]["rejected"], rows[old]["leaves"]) == (None, None), old
    assert fakes.result_calls == [({16, 15, 14, 13, 12}, ["drafting.bullets@3"])]


# ── B2-3 ──


def test_b2_3_progress_is_the_first_running_step_of_a_processing_run(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = Fakes(monkeypatch, [run(23, status="queued"), run(22, status="processing"), run(21, status="processing")])
    fakes.steps[22] = (step("extract", 0, "done"), step("map", 1, "running", 3, 8), step("draft", 2, "running"))
    fakes.steps[21] = (step("extract", 0, "done"), step("map", 1, "pending"))
    fakes.steps[23] = (step("extract", 0, "running", 0, 1),)  # queued 는 단계가 있어도 null
    rows = {r["id"]: r for r in page(limit=50, offset=0)["results"]}
    assert rows[22]["progress"] == {"step": "map", "done": 3, "total": 8}
    assert rows[21]["progress"] is None
    assert rows[23]["progress"] is None
    assert fakes.step_calls == [{22, 21}]  # queued·끝난 실행의 단계는 읽지 않는다
    assert fakes.result_calls == []  # done 이 없으면 결과 0


# ── B2-4 ──


def test_b2_4_option_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    Fakes(
        monkeypatch,
        [
            run(33, base={"runId": 31, "rebuild": ["ghg", "energy"]}),
            run(32, base={"runId": 31, "rebuild": []}, outline_id=None),
            run(31, status="failed"),
        ],
    )
    rows = {r["id"]: r for r in page(limit=50, offset=0)["results"]}
    assert {k: rows[33][k] for k in ("outlineId", "baseRunId", "rebuild")} == {
        "outlineId": 11,
        "baseRunId": 31,
        "rebuild": ["ghg", "energy"],
    }
    assert {k: rows[32][k] for k in ("outlineId", "baseRunId", "rebuild")} == {
        "outlineId": None,
        "baseRunId": 31,
        "rebuild": [],
    }
    assert {k: rows[31][k] for k in ("baseRunId", "rebuild")} == {"baseRunId": None, "rebuild": []}
    assert (rows[31]["status"], rows[31]["createdAt"], rows[31]["finishedAt"]) == (
        "failed",
        T0 + timedelta(minutes=31),
        T0 + timedelta(minutes=31, seconds=30),
    )


# ── B2-5 ──


def test_b2_5_latest_run_per_project(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = Fakes(monkeypatch, [run(45, project=OTHER), run(44), run(43, project=OTHER), run(42)])
    latest = runs_actions.latest_runs(company_id=1, project_ids=[PROJECT, OTHER, 99])
    assert {project: item["id"] for project, item in latest.items()} == {PROJECT: 44, OTHER: 45}
    calls = len(fakes.pages)
    assert runs_actions.latest_runs(company_id=1, project_ids=[]) == {}
    assert len(fakes.pages) == calls  # 빈 입력이면 run_page 0


# ── B2-6 ──


def test_b2_6_steps_and_results_are_read_once_per_page(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [run(100 + i, status=("done", "processing", "queued", "failed")[i % 4]) for i in range(20)]
    fakes = Fakes(monkeypatch, list(reversed(runs)))
    for r in runs:
        if r.status == "done":
            fakes.result(r.id, "drafting.bullets@3", body("done"))
    found = page(limit=50, offset=0)
    assert len(found["results"]) == 20
    assert len(fakes.pages) == len(fakes.step_calls) == len(fakes.result_calls) == 1
    assert fakes.step_calls[0] == {r.id for r in runs if r.status == "processing"}
    assert fakes.result_calls[0][0] == {r.id for r in runs if r.status == "done"}
