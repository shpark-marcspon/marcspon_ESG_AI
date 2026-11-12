"""묶음 꼴(runbundle/calc/bundle.py)을 순수 층에서 잰다 — S1 꼴·S2 의 이름 문.

    S1  머리·표가 왕복하고, 모르는 format·빠진 열쇠·사람/회사 칸 실림·tables 와 다른 칸·counts 어긋남 → Refused
    S2  zip 항목 목록 밖·`../x`·`/abs`·겹침·빠짐 → Refused, JSON 의 NaN·Infinity → Refused
    T4  (RX1b) 모듈 행은 받는 carrier 의 columns() 선언으로 검사(표·칸 집합·사람·회사·id 칸·꼴)하고 time 칸을 푼다 ·
        선언 자리 밖 바이트 견줌(same_outside — 목록 `[]` 경로·열쇠 차례·더해진 열쇠)
★ 값은 전부 지어낸 것이다(synthetic).
"""

import copy
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest

from esgapi.runbundle.calc.bundle import (
    Blob,
    Refused,
    check_bundle,
    check_members,
    check_module_rows,
    decode_row,
    dumps,
    encode_value,
    loads,
    same_outside,
)

DOC = hashlib.sha256(b"doc").hexdigest()
FILE = hashlib.sha256(b"file").hexdigest()


SEGMENT_COLUMNS = (
    "step",
    "position",
    "kind",
    "key",
    "key_sha256",
    "status",
    "attempts",
    "data",
    "error_code",
    "started_at",
    "finished_at",
    "data_octets",
)


def legacy() -> dict[str, object]:
    """옛 묶음(RM1c 앞 — 표 여섯): tables·rows·counts 셋 다 run_segments 가 없다."""
    header = good()
    for part in ("tables", "rows", "counts"):
        cast("dict[str, object]", header[part]).pop("run_segments")
    return header


def good() -> dict[str, object]:
    return {
        "format": "esg.run-bundle@1",
        "bundleId": "0b9a7c3e-6f1d-4c2b-9a8e-1d2c3b4a5f60",
        "createdAt": "2026-10-27T00:00:00+00:00",
        "appCommit": "test",
        "sourceCompanyId": 1,
        "migrations": {"runs": ["0004_x"]},
        "flows": ["rxtest.flow@1"],
        "shapes": ["rxtest.result@1"],
        "tables": {
            "core_documents": ["file_name", "created_at", "size_bytes", "sha256"],
            "run_runs": ["module", "flow_id"],
            "run_steps": ["name"],
            "run_results": ["position", "schema_version", "body"],
            "run_files": ["step", "name", "size_bytes", "sha256"],
            "core_llm_call_logs": ["ts", "cost_usd"],
            "run_segments": list(SEGMENT_COLUMNS),  # RM1c: 일곱째 표(이 묶음은 구획 0)
        },
        "counts": {
            "core_documents": 1,
            "run_runs": 1,
            "run_steps": 1,
            "run_results": 1,
            "run_files": 1,
            "core_llm_call_logs": 1,
            "run_segments": 0,
        },
        "blobs": [{"sha256": DOC, "size": 3, "role": "document"}, {"sha256": FILE, "size": 4, "role": "run_file"}],
        "rows": {
            "core_documents": [
                {
                    "oldId": 5,
                    "previousOldId": None,
                    "blob": DOC,
                    "file_name": "가상.pdf",
                    "created_at": "x",
                    "size_bytes": 3,
                    "sha256": None,
                }
            ],
            "run_runs": [
                {"oldId": 9, "documentOldId": 5, "resumedFromOldId": None, "module": "rxtest", "flow_id": "f"}
            ],
            "run_steps": [{"runOldId": 9, "name": "extract"}],
            "run_results": [{"runOldId": 9, "position": 0, "schema_version": "rxtest.result@1", "body": {}}],
            "run_files": [
                {"runOldId": 9, "blob": FILE, "step": None, "name": "out.json", "size_bytes": 4, "sha256": FILE}
            ],
            "core_llm_call_logs": [{"runOldId": 9, "ts": "2026-10-01T00:00:00+00:00", "cost_usd": "0.1"}],
            "run_segments": [],
            "modules": {"rxtest": {"rxtest_settings": [{"oldId": 7}]}},
        },
    }


def test_a_good_header_passes_and_round_trips() -> None:
    header = good()
    bundle = check_bundle(loads(dumps(header)))
    assert bundle.bundle_id == header["bundleId"] and bundle.source_company_id == 1
    assert bundle.blobs == (Blob(DOC, 3, "document"), Blob(FILE, 4, "run_file"))
    assert bundle.modules == {"rxtest": {"rxtest_settings": [{"oldId": 7}]}}


def _rows(header: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    return cast("dict[str, list[dict[str, object]]]", header["rows"])


def _part(header: dict[str, object], name: str) -> dict[str, object]:
    return cast("dict[str, object]", header[name])


CASES: dict[str, Callable[[dict[str, object]], object]] = {
    "format": lambda h: h.__setitem__("format", "esg.run-bundle@2"),
    "missing_key": lambda h: h.pop("appCommit"),
    "extra_key": lambda h: h.__setitem__("tenant", 1),
    "upper_uuid": lambda h: h.__setitem__("bundleId", str(h["bundleId"]).upper()),
    "person_in_run": lambda h: _rows(h)["run_runs"][0].__setitem__("created_by_user_id", 3),
    # 묶음이 실제로 실을 꼴(머리 tables 와 행 둘 다) — 칸 목록 대조가 아니라 사람 칸 검사가 막아야 한다(P2)
    "person_carried": lambda h: (
        _part(h, "tables").__setitem__("run_runs", ["module", "flow_id", "created_by_user_id"]),
        _rows(h)["run_runs"][0].__setitem__("created_by_user_id", 3),
    ),
    "company_in_log": lambda h: _rows(h)["core_llm_call_logs"][0].__setitem__("company_id", 3),
    "uploaded_by": lambda h: _rows(h)["core_documents"][0].__setitem__("uploaded_by", "3"),
    "person_in_tables": lambda h: _part(h, "tables").__setitem__("run_runs", ["module", "created_by_user_id"]),
    "column_not_in_tables": lambda h: _rows(h)["run_steps"][0].__setitem__("status", "done"),
    "missing_column": lambda h: _rows(h)["run_steps"][0].pop("name"),
    "counts": lambda h: _part(h, "counts").__setitem__("run_steps", 2),
    "blob_not_listed": lambda h: _rows(h)["run_files"][0].__setitem__("blob", "0" * 64),
    "blob_role": lambda h: _rows(h)["run_files"][0].__setitem__("blob", DOC),
    "old_id_not_positive": lambda h: _rows(h)["run_runs"][0].__setitem__("oldId", 0),
    "old_id_bool": lambda h: _rows(h)["run_steps"][0].__setitem__("runOldId", True),
    "duplicate_old_id": lambda h: _rows(h)["run_runs"].append(dict(_rows(h)["run_runs"][0])),
    # ③ 잔손: 바이트 칸과 blob, 실행 없는 LLM 기록
    "document_size": lambda h: _rows(h)["core_documents"][0].__setitem__("size_bytes", 4),
    "document_sha": lambda h: _rows(h)["core_documents"][0].__setitem__("sha256", FILE),
    "file_size": lambda h: _rows(h)["run_files"][0].__setitem__("size_bytes", 5),
    "file_sha": lambda h: _rows(h)["run_files"][0].__setitem__("sha256", "0" * 64),
    "no_byte_columns": lambda h: (
        _part(h, "tables").__setitem__("run_files", ["step", "name", "sha256"]),
        _rows(h)["run_files"][0].pop("size_bytes"),
    ),
    "log_without_run": lambda h: _rows(h)["core_llm_call_logs"][0].__setitem__("runOldId", None),
}


@pytest.mark.parametrize("case", list(CASES))
def test_a_wrong_header_is_refused(case: str) -> None:
    header = copy.deepcopy(good())
    CASES[case](header)
    with pytest.raises(Refused):
        check_bundle(header)


@pytest.mark.parametrize("text", [b'{"a": NaN}', b'{"a": Infinity}', b'{"a": -Infinity}', b"{", b"\xff"])
def test_json_constants_and_garbage_are_refused(text: bytes) -> None:
    with pytest.raises(Refused):
        loads(text)


def test_writing_nan_fails() -> None:
    with pytest.raises(ValueError):
        dumps({"a": float("nan")})


@pytest.mark.parametrize(
    "names",
    [
        ["bundle.json", f"blobs/{DOC}", f"blobs/{FILE}", "extra.txt"],
        ["bundle.json", f"blobs/{DOC}", f"blobs/{FILE}", "../x"],
        ["bundle.json", f"blobs/{DOC}", f"blobs/{FILE}", "/abs"],
        ["bundle.json", f"blobs/{DOC}", f"blobs/{FILE}", f"blobs/{FILE}"],
        ["bundle.json", f"blobs/{DOC}"],
        ["bundle.json", f"blobs/{DOC}", f"blobs/../{FILE}"],
    ],
    ids=["outside", "dotdot", "absolute", "duplicate", "missing", "dotdot_inner"],
)
def test_zip_members_outside_the_list_are_refused(names: list[str]) -> None:
    blobs = (Blob(DOC, 3, "document"), Blob(FILE, 4, "run_file"))
    with pytest.raises(Refused):
        check_members(names, blobs)


def test_the_listed_members_pass() -> None:
    check_members(
        ["bundle.json", f"blobs/{FILE}", f"blobs/{DOC}"], (Blob(DOC, 3, "document"), Blob(FILE, 4, "run_file"))
    )


def test_values_encode_and_decode() -> None:
    moment = datetime(2026, 10, 1, 1, 2, 3, 456000, tzinfo=UTC)
    row = {"ts": encode_value(moment), "cost_usd": encode_value(Decimal("0.00012345")), "step": "judge"}
    assert row == {"ts": "2026-10-01T01:02:03.456000+00:00", "cost_usd": "0.00012345", "step": "judge"}
    assert decode_row("core_llm_call_logs", row) == {"ts": moment, "cost_usd": Decimal("0.00012345"), "step": "judge"}
    for bad in ({"ts": "어제"}, {"ts": "2026-10-01T00:00:00"}, {"cost_usd": "NaN"}, {"cost_usd": 1}):
        with pytest.raises(Refused):
            decode_row("core_llm_call_logs", bad)
    with pytest.raises(ValueError):
        encode_value(datetime(2026, 10, 1))


# ── 모듈 행(T4 — RX1b Qb7) ─────────────────────────────────────────────

DECLARED = {
    "rxtest": {
        "rxtest_reviews": {"runOldId": "id", "state": "plain", "confirmed_at": "time", "created_at": "time"},
        "rxtest_settings": {"oldId": "id", "name": "plain"},
    }
}


def review(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "runOldId": 3,
        "state": "confirmed",
        "confirmed_at": "2026-09-01T01:02:03+00:00",
        "created_at": "2026-09-01T01:00:00+00:00",
    }
    return {**row, **changes}


def test_module_rows_are_checked_against_the_receiving_declaration_and_times_are_decoded() -> None:
    found = check_module_rows({"rxtest": {"rxtest_reviews": [review(confirmed_at=None)]}}, DECLARED)
    row = found["rxtest"]["rxtest_reviews"][0]
    assert row["created_at"] == datetime(2026, 9, 1, 1, 0, tzinfo=UTC)
    assert row["confirmed_at"] is None
    assert (row["runOldId"], row["state"]) == (3, "confirmed")


@pytest.mark.parametrize(
    "modules",
    [
        {"rxtest": {"rxtest_reviews": [review(confirmed_by_user_id=5)]}},  # 사람 칸(꾸민 묶음)
        {"rxtest": {"rxtest_reviews": [review(id=9)]}},  # id 칸
        {"rxtest": {"rxtest_reviews": [review(company_id=2)]}},
        {"rxtest": {"rxtest_reviews": [review(extra="x")]}},  # 선언 밖 칸
        {"rxtest": {"rxtest_reviews": [{"runOldId": 3, "state": "x", "confirmed_at": None}]}},  # 빠진 칸
        {"rxtest": {"rxtest_marks": []}},  # 선언 밖 표
        {"other": {"rxtest_reviews": []}},  # 선언 없는 모듈
        {"rxtest": {"rxtest_reviews": [review(runOldId="3")]}},  # id 꼴
        {"rxtest": {"rxtest_reviews": [review(runOldId=0)]}},
        {"rxtest": {"rxtest_reviews": [review(confirmed_at="2026-09-01T01:02:03")]}},  # 시간대 없음
        {"rxtest": {"rxtest_reviews": [review(confirmed_at=5)]}},
    ],
)
def test_a_forged_module_row_is_refused(modules: dict[str, dict[str, list[dict[str, object]]]]) -> None:
    with pytest.raises(Refused):
        check_module_rows(modules, DECLARED)


def test_a_declaration_with_a_person_column_is_refused() -> None:
    declared = {"rxtest": {"rxtest_marks": {"runOldId": "id", "fix_edited_by_user_id": "plain"}}}
    with pytest.raises(Refused):
        check_module_rows({"rxtest": {"rxtest_marks": []}}, declared)


def test_only_declared_places_may_change() -> None:
    before = {"retry": {"fromRunId": 3, "pages": [1]}, "results": [{"settings": {"fromRunId": 3}, "n": 1}]}
    after = {"retry": {"fromRunId": 30, "pages": [1]}, "results": [{"settings": {"fromRunId": 30}, "n": 1}]}
    assert same_outside(before, after, ["retry.fromRunId", "results[].settings.fromRunId"])
    assert not same_outside(before, after, ["retry.fromRunId"])
    assert not same_outside(before, {**after, "added": 1}, ["retry.fromRunId", "results[].settings.fromRunId"])
    reordered = {"results": after["results"], "retry": after["retry"]}
    assert not same_outside(before, reordered, ["retry.fromRunId", "results[].settings.fromRunId"])  # 열쇠 차례
    assert not same_outside({"a": 1}, {"a": 1, "fromRunId": 2}, ["fromRunId"])  # 없던 선언 자리를 더함
