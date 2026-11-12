"""묶음의 구획 표(RM1c ② — T11·T12 의 순수 몫): 옛 묶음 받기, 일부만 있는 묶음 거절, 구획 행의 문. DB 0.
흐름은 시험 레지스트리에만 단 펼침 흐름 `rxtest.fan@1`(제품 등록 0). ★ 값은 전부 지어낸 것이다(synthetic).
"""

import copy
from collections.abc import Callable
from typing import cast

import pytest

from esgapi.core.flows.registry import FlowRegistry, make_flow
from esgapi.core.flows.types import (
    Carried,
    FanoutStep,
    FlowStep,
    Segment,
    SegmentKey,
    SegmentOutput,
    StepContext,
    StepOutput,
    segment_key_fields,
    segment_key_sha256,
)
from esgapi.runbundle.calc.bundle import SEGMENTS, Bundle, Refused, check_bundle
from esgapi.runbundle.calc.gate import check_carried, check_columns, check_segments, tables_of
from esgapi.runbundle.tests.calc.test_bundle import good as good_header
from esgapi.runbundle.tests.calc.test_bundle import legacy
from esgapi.runbundle.tests.support import MODULE, RxAdapters, RxInputs
from esgapi.runs.calc.segments import data_octets

FAN_ID = "rxtest.fan@1"
MAX = 4


def _prepare(inputs: RxInputs, adapters: RxAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"count": 2})


def _plan(inputs: RxInputs, carried: Carried) -> tuple[Segment, ...]:
    return ()


def _spread(
    inputs: RxInputs, adapters: RxAdapters, carried: Carried, segment: Segment, ctx: StepContext
) -> SegmentOutput:
    return SegmentOutput(data={})


FAN = make_flow(
    module=MODULE,
    id=FAN_ID,
    input_shape="rxtest.document@1",
    inputs=RxInputs,
    adapters=RxAdapters,
    result_shapes=("rxtest.result@1",),
    steps=(
        FlowStep(name="prepare", run=_prepare),
        FanoutStep(
            name="spread", plan=_plan, run=_spread, on_failure="pass_to_gather", allow_empty=True, max_segments=MAX
        ),
        FlowStep(name="gather", run=_prepare),
    ),
)


def registry() -> FlowRegistry:
    found = FlowRegistry()
    found.register(FAN)
    return found


def key(n: int) -> SegmentKey:
    return SegmentKey(kind="block", span=f"b{n}", document_sha256=None, parser_version="p1")


def segment(position: int, status: str = "done") -> dict[str, object]:
    k = key(position + 1)
    done = status == "done"
    data = {"z": position, "a": "가"} if done else None
    return {
        "runOldId": 9,
        "step": "spread",
        "position": position,
        "kind": k.kind,
        "key": segment_key_fields(k),
        "key_sha256": segment_key_sha256(k),
        "status": status,
        "attempts": 1,
        "data": data,
        "error_code": "step_error" if status == "failed" else None,
        "started_at": "2026-10-01T00:00:00+00:00",
        "finished_at": "2026-10-01T00:01:00+00:00",
        "data_octets": None if data is None else data_octets(data),
    }


def header(rows: list[dict[str, object]]) -> dict[str, object]:
    found = copy.deepcopy(good_header())
    head_rows = cast("dict[str, list[dict[str, object]]]", found["rows"])
    head_rows["run_runs"][0]["flow_id"] = FAN_ID
    head_rows[SEGMENTS] = rows
    cast("dict[str, int]", found["counts"])[SEGMENTS] = len(rows)
    return found


def checked(rows: list[dict[str, object]]) -> Bundle:
    return check_bundle(header(rows))


def gate(rows: list[dict[str, object]]) -> None:
    check_segments(checked(rows), registry())


# ── 받는 것 ────────────────────────────────────────────────────────────


def test_good_segments_pass() -> None:
    gate([segment(0), segment(1, "failed"), segment(2, "pending"), segment(3, "running")])
    for row in ([segment(0) | {"data_octets": None}], []):  # 직렬 done(NULL) · 구획 0 도 받는다
        gate(row)


def test_an_old_bundle_without_the_segment_table_passes_every_gate() -> None:
    found = check_bundle(legacy())
    assert found.has_segments is False
    assert SEGMENTS not in found.tables and SEGMENTS not in found.rows
    assert SEGMENTS not in tables_of(found)
    receiving = {table: dict.fromkeys(columns, False) for table, columns in found.tables.items()}
    receiving[SEGMENTS] = {"step": True, "position": True, "kind": True, "key": True}  # 받는 쪽엔 표가 있다
    check_columns(found, receiving)
    check_carried_without_required_columns(found)
    check_segments(found, registry())


def check_carried_without_required_columns(found: Bundle) -> None:
    """옛 묶음은 run_segments 의 꼭 실을 칸을 보지 않는다(다른 표의 칸 부족으로 빨개지는 것은 여기 밖)."""
    try:
        check_carried(found)
    except Refused as refused:
        assert SEGMENTS not in str(refused)


@pytest.mark.parametrize("part", ["tables", "rows", "counts"])
def test_a_segment_table_in_only_some_parts_is_refused(part: str) -> None:
    found = good_header()
    cast("dict[str, object]", found[part]).pop(SEGMENTS)
    with pytest.raises(Refused, match="일부"):
        check_bundle(found)


def test_a_new_bundle_keeps_has_segments() -> None:
    assert checked([segment(0)]).has_segments is True


# ── 거절(T11) ─────────────────────────────────────────────────────────


def _set(name: str, value: object) -> Callable[[list[dict[str, object]]], None]:
    def change(rows: list[dict[str, object]]) -> None:
        rows[0][name] = value

    return change


_BAD_KEY = SegmentKey(kind="Block!", span="b1", document_sha256=None, parser_version="p1")
BAD_KIND: dict[str, object] = {
    "key": segment_key_fields(_BAD_KEY),
    "key_sha256": segment_key_sha256(_BAD_KEY),
    "kind": _BAD_KEY.kind,
}

CASES: dict[str, Callable[[list[dict[str, object]]], None]] = {
    "sha": _set("key_sha256", "0" * 64),
    "key_not_shaped": _set("key", {"kind": "block", "span": "b1"}),
    "key_not_object": _set("key", "b1"),
    "key_bad_kind": lambda rows: rows[0].update(BAD_KIND),  # key·sha·kind 셋이 서로 맞는 나쁜 열쇠(꼴 검사만 막는다)
    "kind": _set("kind", "page"),
    "not_fanout": _set("step", "prepare"),
    "unknown_run": _set("runOldId", 10),
    "position_gap": _set("position", 5),
    "position_text": _set("position", "0"),
    "sha_twice": lambda rows: rows.append(segment(0) | {"position": 1}),
    "too_many": lambda rows: rows.extend(segment(p) for p in range(1, MAX + 1)),
    "done_without_data": _set("data", None),
    "done_with_code": _set("error_code", "step_error"),
    "data_not_object": _set("data", ["가"]),
    "octets_lie": _set("data_octets", 3),
    "pending_with_data": lambda rows: rows.__setitem__(0, segment(0, "pending") | {"data": {"a": 1}}),
    "pending_with_octets": lambda rows: rows.__setitem__(0, segment(0, "pending") | {"data_octets": 0}),
    "failed_with_octets": lambda rows: rows.__setitem__(0, segment(0, "failed") | {"data_octets": 0}),
    "failed_without_code": lambda rows: rows.__setitem__(0, segment(0, "failed") | {"error_code": None}),
    "code_65": lambda rows: rows.__setitem__(0, segment(0, "failed") | {"error_code": "e" * 65}),
    "status": _set("status", "queued"),
    "attempts": _set("attempts", -1),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_bad_segment_row_is_refused(case: str) -> None:
    rows = [segment(0)]
    CASES[case](rows)
    with pytest.raises(Refused):
        gate(rows)


def test_data_over_the_segment_limit_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from esgapi.runbundle.calc import gate as gate_module

    rows = [segment(0)]
    monkeypatch.setattr(
        gate_module, "SEGMENT_DATA_MAX_OCTETS", data_octets(cast("dict[str, object]", rows[0]["data"])) - 1
    )
    with pytest.raises(Refused, match="상한"):
        gate(rows)


@pytest.mark.parametrize("column", ["lease_expires_at", "company_id", "id", "run_id"])
def test_a_column_that_is_never_carried_is_refused(column: str) -> None:
    found = header([segment(0) | {column: 1}])
    tables = cast("dict[str, list[str]]", found["tables"])
    tables[SEGMENTS] = [*tables[SEGMENTS], column]
    with pytest.raises(Refused):
        check_bundle(found)
