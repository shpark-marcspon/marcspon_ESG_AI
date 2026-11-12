"""EDK 인벤토리 엑셀 읽기의 응답 꼴(contracts/edk_read_shapes.py — 밴드 DVX1 §1-2): kind 열은 읽개의 RejectionKind 와
같고(계약은 도구를 import 하지 않는다 — 여기서 견준다), 두 갈래는 strict 로 받고 칸이 하나라도 더 붙으면 거절한다.
ok 갈래의 data 는 실행 입력 input@1 의 data 와 같은 꼴(EdkItem)이다."""

import typing
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from esgapi.dataverify.contracts import edk_read_shapes
from esgapi.dataverify.contracts.edk_read_shapes import DataverifyEdkRead, DataverifyEdkRejectionKind
from esgapi.dataverify.contracts.shapes import DataverifyInput
from esgapi.dataverify.tools import edk_xlsx

SHAPE: TypeAdapter[Any] = TypeAdapter(DataverifyEdkRead)
ITEM = {
    "ID": 1,
    "테마": "환경",
    "항목": "가상 직접 배출량",
    "대분류": "가상",
    "중분류": "가상",
    "소분류": "가상",
    "입력 방식": "숫자",
    "단위": "tCO2eq",
    "values": {"2023": 1, "2024": None},
    "핵심데이터": "Y",
    "메모": None,
}
OK = {
    "ok": True,
    "data": {"환경": [ITEM]},
    "itemCount": 1,
    "skipped": {"themes": 2, "items": 5},
    "years": ["2023", "2024"],
    "skippedEmptyRows": 300,
    "ignoredColumns": 1,
}


def test_the_kinds_are_the_readers_twelve() -> None:
    assert typing.get_args(DataverifyEdkRejectionKind) == typing.get_args(edk_xlsx.RejectionKind)
    assert len(typing.get_args(DataverifyEdkRejectionKind)) == 12


def test_the_contract_does_not_import_the_tool() -> None:
    import ast
    from pathlib import Path

    source = Path(edk_read_shapes.__file__).read_text(encoding="utf-8")
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert imported and not {m for m in imported if m and ".tools" in m}


def test_both_branches_are_accepted_strictly() -> None:
    SHAPE.validate_python(OK, strict=True)
    SHAPE.validate_python(
        {"ok": False, "kind": "bad_cell", "row": 3, "column": 10, "message": "3행 10열에 …"}, strict=True
    )
    SHAPE.validate_python({"ok": False, "kind": "not_xlsx", "row": None, "column": None, "message": "…"}, strict=True)


def test_the_ok_data_is_an_input_data() -> None:
    company: dict[str, object] = {
        "name": "가상기업",
        "sasbIndustry": "가상",
        "materialTopics": [],
        "reportingYear": "2024",
    }
    TypeAdapter(DataverifyInput).validate_python(
        {"schemaVersion": "dataverify.input@1", "company": company, "data": OK["data"]}, strict=True
    )


@pytest.mark.parametrize(
    "body",
    [
        {**OK, "extra": 0},
        {**OK, "skipped": {"themes": 1, "items": 1, "names": ["가상"]}},
        {**OK, "skipped": {"themes": -1, "items": 0}},
        {**OK, "years": ["24"]},
        {**OK, "itemCount": -1},
        {**OK, "ok": False},
        {"ok": False, "kind": "empty_cell", "row": None, "column": None, "message": "…"},
        {"ok": False, "kind": "bad_cell", "row": 0, "column": 1, "message": "…"},
        {"ok": False, "kind": "bad_cell", "row": 1, "column": 0, "message": "…"},
        {"ok": False, "kind": "bad_cell", "row": 1, "column": 1},
        {"ok": False, "kind": "bad_cell", "row": 1, "column": 1, "message": "…", "value": "가상"},
    ],
    ids=[
        "body_extra",
        "skipped_names",
        "skipped_negative",
        "year_shape",
        "count_negative",
        "ok_false_with_data",
        "unknown_kind",
        "row_0",
        "column_0",
        "no_message",
        "rejected_extra",
    ],
)
def test_a_body_off_the_shape_is_refused(body: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SHAPE.validate_python(body, strict=True)
