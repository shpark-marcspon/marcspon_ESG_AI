"""받는 쪽의 문 HD1 몫(runbundle/calc/gate.py) — 순수 층.

    R4  check_carried: 꼭 실을 칸(REQUIRED_COLUMNS)이 빠지면 · position 이 bool·float·글자면 → Refused(제 글)
    R2  check_shape: 실행 0 · 어느 실행도 쓰지 않는 문서 · 실행 없는 모듈의 행 → Refused, 앞 판 사슬 위 문서는 통과
    S2  check_module_runs: 모듈 행의 runOldId 가 다른 모듈 실행·묶음 밖·꼴 밖이면 Refused
★ 값은 전부 지어낸 것이다(synthetic).
"""

import copy
from typing import Any, cast

import pytest

from esgapi.runbundle.calc.bundle import REQUIRED_COLUMNS, TABLES, Bundle, Refused, check_bundle
from esgapi.runbundle.calc.gate import check_carried, check_module_runs, check_shape
from esgapi.runbundle.tests.calc.test_bundle import good

FILLER: dict[str, object] = {"options": {}, "versions": {}, "data": {}, "partial": None, "body": {}, "position": 0}


def full() -> dict[str, Any]:
    """good() 에 꼭 실을 칸을 다 채운 머리(값은 지어낸 것 — 칸이 있느냐만 본다)."""
    header = cast("dict[str, Any]", copy.deepcopy(good()))
    for table in TABLES:
        columns = list(header["tables"][table])
        for name in sorted(REQUIRED_COLUMNS[table] - set(columns)):
            columns.append(name)
            for row in header["rows"][table]:
                row[name] = FILLER.get(name, "x")
        header["tables"][table] = columns
    header["rows"]["run_runs"][0]["status"] = "done"
    return header


def carried(header: dict[str, Any]) -> Bundle:
    return check_bundle(header)


def test_a_full_bundle_passes_every_new_gate() -> None:
    found = carried(full())
    check_carried(found)
    check_shape(found)
    check_module_runs(found)


# 문서·파일의 size_bytes·sha256 은 check_bundle 이 먼저 제 글로 막는다(옛 문 — 아래 둘째 시험)
BYTE_COLUMNS = {
    ("core_documents", "size_bytes"),
    ("core_documents", "sha256"),
    ("run_files", "size_bytes"),
    ("run_files", "sha256"),
}


def without(table: str, column: str) -> dict[str, Any]:
    header = full()
    header["tables"][table] = [name for name in header["tables"][table] if name != column]
    for row in header["rows"][table]:
        row.pop(column)
    return header


@pytest.mark.parametrize(
    ("table", "column"),
    [(t, c) for t in TABLES for c in sorted(REQUIRED_COLUMNS[t]) if (t, c) not in BYTE_COLUMNS],
)
def test_a_missing_required_column_is_refused(table: str, column: str) -> None:
    with pytest.raises(Refused, match=f"{table} 에 꼭 실을 칸이 없다"):
        check_carried(carried(without(table, column)))


@pytest.mark.parametrize(("table", "column"), sorted(BYTE_COLUMNS))
def test_a_missing_byte_column_is_refused_by_the_header_check(table: str, column: str) -> None:
    with pytest.raises(Refused, match="size_bytes·sha256 칸이 없다"):
        carried(without(table, column))


@pytest.mark.parametrize("table", ["run_steps", "run_results"])
@pytest.mark.parametrize("value", [True, 1.0, "1", None], ids=["bool", "float", "text", "null"])
def test_a_position_that_is_not_an_int_is_refused(table: str, value: object) -> None:
    header = full()
    header["rows"][table][0]["position"] = value
    with pytest.raises(Refused, match=f"{table} 의 position 은 정수여야 한다"):
        check_carried(carried(header))


def test_a_bundle_without_runs_is_refused() -> None:
    header = full()
    for table in ("run_runs", "run_steps", "run_results", "run_files", "core_llm_call_logs", "core_documents"):
        header["rows"][table] = []
        header["counts"][table] = 0
    header["blobs"] = []
    header["rows"]["modules"] = {}
    with pytest.raises(Refused, match="묶음에 실행이 없다"):
        check_shape(carried(header))


def test_a_document_no_run_uses_is_refused() -> None:
    header = full()
    header["rows"]["run_runs"][0]["documentOldId"] = None
    with pytest.raises(Refused, match="어느 실행도 쓰지 않는 문서가 있다"):
        check_shape(carried(header))


def test_a_previous_version_on_the_chain_passes() -> None:
    header = full()
    older = dict(header["rows"]["core_documents"][0]) | {"oldId": 4}
    header["rows"]["core_documents"][0]["previousOldId"] = 4
    header["rows"]["core_documents"].append(older)
    header["counts"]["core_documents"] = 2
    check_shape(carried(header))


def test_module_rows_of_a_module_without_runs_are_refused() -> None:
    header = full()
    header["rows"]["modules"]["other"] = {"other_settings": []}
    with pytest.raises(Refused, match="실행이 없는 모듈의 행이 실렸다"):
        check_shape(carried(header))


def two_modules() -> dict[str, Any]:
    header = full()
    second = dict(header["rows"]["run_runs"][0]) | {"oldId": 10, "module": "other", "documentOldId": 5}
    header["rows"]["run_runs"].append(second)
    header["counts"]["run_runs"] = 2
    header["rows"]["modules"] = {"rxtest": {"marks": [{"runOldId": 9}]}, "other": {}}
    return header


def test_a_module_row_pointing_at_its_own_modules_run_passes() -> None:
    check_module_runs(carried(two_modules()))


@pytest.mark.parametrize("pointed", [10, 99, True, "9"], ids=["other_module", "outside", "bool", "text"])
def test_a_module_row_pointing_elsewhere_is_refused(pointed: object) -> None:
    header = two_modules()
    header["rows"]["modules"]["rxtest"]["marks"][0]["runOldId"] = pointed
    with pytest.raises(Refused, match="그 모듈 실행이 아닌 실행을 가리킨다"):
        check_module_runs(carried(header))
