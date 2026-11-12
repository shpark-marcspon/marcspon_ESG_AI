"""받는 쪽의 문(runbundle/calc/gate.py) — S4: 모르는 흐름·꼴·단계, 칸 더 많음, 받는 쪽 필수 칸 없음, 보낸 쪽 잎이 받는
그래프에 없음 → Refused, 받는 쪽이 앞선 것은 통과, carrier 없는 모듈은 거절. ★ 값은 전부 지어낸 것이다(synthetic).
"""

import copy
from typing import cast

import pytest

from esgapi.core.flows.carriers import NO_ROWS, CarrierRegistry
from esgapi.runbundle.calc.bundle import NOT_CARRIED, TABLES, Bundle, Refused, check_bundle
from esgapi.runbundle.calc.gate import check_carriers, check_columns, check_flows, check_migrations, check_statuses
from esgapi.runbundle.tests.calc.test_bundle import good
from esgapi.runbundle.tests.support import FLOW_ID, flows


def bundle() -> Bundle:
    header = copy.deepcopy(good())
    cast("dict[str, list[dict[str, object]]]", header["rows"])["run_runs"][0]["flow_id"] = FLOW_ID
    return check_bundle(header)


def receiving(extra: dict[str, dict[str, bool]] | None = None) -> dict[str, dict[str, bool]]:
    found = {table: dict.fromkeys(check_bundle(good()).tables[table], False) for table in TABLES}
    for table, columns in (extra or {}).items():
        found[table] |= columns
    return found


def test_known_flows_shapes_and_steps_pass() -> None:
    check_flows(bundle(), flows())


@pytest.mark.parametrize(
    ("table", "column", "value"),
    [
        ("run_runs", "flow_id", "rxtest.unknown@1"),
        ("run_runs", "module", "other"),
        ("run_results", "schema_version", "rxtest.other@1"),
        ("run_steps", "name", "report"),
    ],
    ids=["flow", "module", "shape", "step"],
)
def test_unknown_flows_shapes_and_steps_are_refused(table: str, column: str, value: str) -> None:
    found = bundle()
    found.rows[table][0][column] = value
    with pytest.raises(Refused):
        check_flows(found, flows())


@pytest.mark.parametrize("status", ["queued", "processing", None])
def test_unfinished_runs_are_refused(status: str | None) -> None:
    found = bundle()
    found.rows["run_runs"][0]["status"] = status
    with pytest.raises(Refused, match="끝난 실행"):
        check_statuses(found)


# failed 는 done 후손이 있을 때만 통과 — test_a_failed_run_with_a_done_descendant_passes 가 잰다
@pytest.mark.parametrize("status", ["done"])
def test_finished_runs_pass(status: str) -> None:
    found = bundle()
    found.rows["run_runs"][0]["status"] = status
    check_statuses(found)


def test_columns() -> None:
    check_columns(bundle(), receiving())
    check_columns(bundle(), receiving({"run_runs": {"newer": False}}))  # 받는 쪽에 더 있는 선택 칸은 통과
    check_columns(bundle(), receiving({"run_runs": dict.fromkeys(NOT_CARRIED["run_runs"], True)}))  # 넣기가 채움
    narrow = receiving()
    del narrow["run_runs"]["flow_id"]
    with pytest.raises(Refused, match="모르는 칸"):
        check_columns(bundle(), narrow)
    with pytest.raises(Refused, match="필수 칸"):
        check_columns(bundle(), receiving({"run_runs": {"must_have": True}}))
    missing = receiving()
    del missing["run_files"]
    with pytest.raises(Refused, match="표가 없다"):
        check_columns(bundle(), missing)


def test_migrations() -> None:
    nodes = {("runs", "0003_a"), ("runs", "0004_x"), ("runs", "0005_newer"), ("core", "0001_initial")}
    sent = {"runs": ["0004_x"], "core": ["0001_initial"]}
    check_migrations(sent, nodes, {"core", "runs"})  # 받는 쪽이 앞섬 — 통과
    with pytest.raises(Refused, match="모른다"):
        check_migrations(sent | {"runs": ["0006_future"]}, nodes, {"core", "runs"})
    with pytest.raises(Refused, match="모른다"):
        check_migrations(sent | {"greenwash": ["0001_initial"]}, nodes, {"core", "runs"})


@pytest.mark.parametrize(
    "sent",
    [{}, {"runs": ["0004_x"]}, {"core": ["0001_initial"], "runs": []}],
    ids=["empty", "no_core", "empty_runs"],
)
def test_the_core_and_runs_leaves_must_be_there(sent: dict[str, list[str]]) -> None:
    """③ S4: 머리의 migrations 가 비거나 core·runs(와 묶음 모듈 가운데 앱) 잎이 없으면 거절."""
    with pytest.raises(Refused, match="없다"):
        check_migrations(sent, {("runs", "0004_x"), ("core", "0001_initial")}, {"core", "runs"})


def chained(*runs: tuple[int, str, int | None]) -> Bundle:
    """(옛 id, 상태, 앞 실행 옛 id) 의 실행만 바꾼 묶음(나머지 표는 good 그대로 — 상태 문만 잰다)."""
    found = bundle()
    template = found.rows["run_runs"][0]
    found.rows["run_runs"][:] = [
        template | {"oldId": old, "status": status, "resumedFromOldId": parent} for old, status, parent in runs
    ]
    return found


@pytest.mark.parametrize(
    "runs",
    [
        ((1, "failed", None), (2, "done", 1)),
        ((1, "failed", None), (2, "failed", 1), (3, "done", 2)),
        ((1, "done", None),),
    ],
    ids=["failed_then_done", "two_failed_then_done", "done_alone"],
)
def test_a_failed_run_with_a_done_descendant_passes(runs: tuple[tuple[int, str, int | None], ...]) -> None:
    check_statuses(chained(*runs))


@pytest.mark.parametrize(
    "runs",
    [
        ((1, "failed", None),),
        ((1, "failed", None), (2, "failed", 1)),
        ((1, "failed", None), (2, "done", None)),
    ],
    ids=["failed_alone", "failed_chain_only", "done_not_resuming_it"],
)
def test_a_lonely_failed_run_is_refused(runs: tuple[tuple[int, str, int | None], ...]) -> None:
    """③ S3: 묶음 안에 이어 간 done 후손이 없는 failed(꾸민 묶음의 외톨이)는 쓰기 앞에서 거절."""
    with pytest.raises(Refused, match="done 실행이 없는 failed"):
        check_statuses(chained(*runs))


def test_files_of_runs_outside_or_steps_outside_are_refused() -> None:
    """③ 잔손 1: 파일 행의 실행이 묶음 밖이거나 단계가 흐름 선언 밖이면 거절."""
    outside = bundle()
    outside.rows["run_files"][0]["runOldId"] = 99
    with pytest.raises(Refused, match="묶음에 없는 실행"):
        check_flows(outside, flows())
    step = bundle()
    step.rows["run_files"][0]["step"] = "report"
    with pytest.raises(Refused, match="파일의 단계"):
        check_flows(step, flows())
    good_step = bundle()
    good_step.rows["run_files"][0]["step"] = "extract"
    check_flows(good_step, flows())


def test_carriers() -> None:
    registry = CarrierRegistry()
    registry.register("rxtest", NO_ROWS)
    check_carriers(["rxtest", "rxtest"], registry)
    with pytest.raises(Refused, match="carrier"):
        check_carriers(["rxtest", "greenwash"], registry)
