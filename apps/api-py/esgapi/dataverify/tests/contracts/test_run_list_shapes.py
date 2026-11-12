"""목록 꼴(contracts/run_list_shapes.py — 밴드 DV1g §3-1-3): source 는 옵션 꼴의 DataverifySource 그 객체이고, 계약
파일은 ninja·core.schemas 를 import 하지 않으며, openapi 에 오를 이름은 전부 Dataverify 머리라 다른 모듈의
컴포넌트(이미 있는 `Source` 등)와 겹치지 않는다. 줄 칸 집합은 발주서 Q5 그대로다."""

import ast
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from esgapi.dataverify.contracts import options_shapes, run_list_shapes
from esgapi.dataverify.contracts.run_list_shapes import DataverifyRunPage, DataverifyRunRow

PAGE: TypeAdapter[Any] = TypeAdapter(DataverifyRunPage)
ROW_FIELDS = {
    "id",
    "status",
    "createdAt",
    "finishedAt",
    "createdBy",
    "source",
    "companyName",
    "reportingYear",
    "itemCount",
    "failedStep",
    "currentStep",
    "stages",
    "checks",
}


def a_row(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 1,
        "status": "done",
        "createdAt": "2026-10-23T09:00:00+09:00",
        "finishedAt": "2026-10-23T09:01:00+09:00",
        "createdBy": {"userId": 1, "name": "가상 담당"},
        "source": {"kind": "file", "name": "가상 입력.json"},
        "companyName": "가상건설",
        "reportingYear": "2025",
        "itemCount": 2,
        "failedStep": None,
        "currentStep": None,
        "stages": {
            "plan": {"status": "done", "partial": False},
            "review": {"status": "done", "partial": True},
            "insight": {"status": "done", "partial": False},
        },
        "checks": {"ok": 1, "fail": 0, "notComputed": 0, "naValues": 0, "toolErrors": 0},
    }
    row.update(changes)
    return row


def test_the_source_is_the_options_shape_object() -> None:
    source = DataverifyRunRow.__annotations__["source"]
    assert any(arg is options_shapes.DataverifySource for arg in get_args(source))
    assert type(None) in get_args(source)


def test_the_row_fields_are_q5() -> None:
    assert set(DataverifyRunRow.__annotations__) == ROW_FIELDS


def test_a_page_fits_and_empty_values_are_null() -> None:
    PAGE.validate_python({"count": 1, "isNext": False, "results": [a_row()]}, strict=True)
    empty = a_row(source=None, companyName=None, reportingYear=None, itemCount=None, stages=None, checks=None)
    paste = a_row(source={"kind": "paste"})
    PAGE.validate_python({"count": 2, "isNext": False, "results": [empty, paste]}, strict=True)


@pytest.mark.parametrize(
    "row",
    [
        a_row(extra=1),
        a_row(source={"kind": "file"}),
        a_row(source={"kind": "paste", "name": "a"}),
        a_row(status="canceled"),
        a_row(createdBy={"userId": 1}),
        a_row(itemCount=-1),
    ],
)
def test_a_broken_row_is_rejected(row: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PAGE.validate_python({"count": 1, "isNext": False, "results": [row]}, strict=True)


def test_the_contract_file_imports_neither_ninja_nor_core_schemas() -> None:
    tree = ast.parse(Path(run_list_shapes.__file__).read_text(encoding="utf-8"))
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert not {m for m in modules if m and (m.startswith("ninja") or m == "esgapi.core.schemas")}


def test_every_component_name_has_the_dataverify_head() -> None:
    """openapi 컴포넌트가 될 이름(쪽 꼴과 그 $defs) — 다른 모듈의 것(`Source`·`Person` 등)과 겹치면 하나로 합쳐진다."""
    schema = PAGE.json_schema()
    names = {schema["title"], *schema["$defs"]}
    assert names >= {"DataverifyRunPage", "DataverifyRunRow", "DataverifyPerson", "DataverifyFileSource"}
    assert [n for n in names if not n.startswith("Dataverify")] == []
    assert "Source" not in names
