"""목록 꼴(contracts/run_list_shapes.py — 밴드 IR3c §3-1-3): 줄 칸 집합은 처분 ③ 그대로, 계약 파일은 ninja·
core.schemas 를 import 하지 않으며, openapi 에 오를 새 이름은 전부 Materiality 머리이고 contracts 의 다른 꼴 이름(기준
컴포넌트 — `MaterialityIndustry` 등)과 겹치지 않는다. 권한 칸은 회사 업무(COMPANY — 운영 관리자도 작업 회사로,
MARC-ENT-419)."""

import ast
import inspect
from pathlib import Path
from typing import Any, is_typeddict

import pytest
from pydantic import TypeAdapter, ValidationError

from esgapi.core.permissions import COMPANY, OPERATION_POLICY
from esgapi.materiality.contracts import digest_shapes, options_shapes, run_list_shapes, shapes
from esgapi.materiality.contracts.run_list_shapes import MaterialityRunPage, MaterialityRunRow

PAGE: TypeAdapter[Any] = TypeAdapter(MaterialityRunPage)
ROW_FIELDS = {
    "id",
    "status",
    "createdAt",
    "startedAt",
    "finishedAt",
    "createdBy",
    "companyName",
    "industries",
    "topicCount",
    "dateRange",
    "latestEventMode",
    "failedStep",
    "currentStep",
    "impactRows",
    "pathwayRows",
}
NEW_NAMES = {"MaterialityRunPage", "MaterialityRunRow", "MaterialityPerson", "MaterialityRunIndustry"}
"""쪽 꼴과 그 $defs(경로의 조회 인자 MaterialityRunListQuery 는 service/apis 에 있다)."""


def a_row(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 1,
        "status": "done",
        "createdAt": "2026-10-26T09:00:00+09:00",
        "startedAt": "2026-10-26T09:00:05+09:00",
        "finishedAt": "2026-10-26T09:10:00+09:00",
        "createdBy": {"userId": 1, "name": "가상 담당"},
        "companyName": "가상물류",
        "industries": [{"standard": "SASB", "industryName": "가상 산업 하나"}],
        "topicCount": 3,
        "dateRange": "2025-01-01~오늘까지",
        "latestEventMode": False,
        "failedStep": None,
        "currentStep": None,
        "impactRows": 4,
        "pathwayRows": 2,
    }
    row.update(changes)
    return row


def test_the_row_fields_are_the_fifteen_of_disposition_3() -> None:
    assert set(MaterialityRunRow.__annotations__) == ROW_FIELDS


def test_a_page_fits_and_empty_values_are_null() -> None:
    PAGE.validate_python({"count": 1, "isNext": False, "results": [a_row()]}, strict=True)
    empty = a_row(
        startedAt=None,
        finishedAt=None,
        companyName=None,
        industries=None,
        topicCount=None,
        dateRange=None,
        latestEventMode=None,
        impactRows=None,
        pathwayRows=None,
        status="queued",
    )
    PAGE.validate_python({"count": 2, "isNext": True, "results": [empty, a_row(industries=[])]}, strict=True)


@pytest.mark.parametrize(
    "row",
    [
        a_row(extra=1),
        a_row(status="canceled"),
        a_row(createdBy={"userId": 1}),
        a_row(topicCount=-1),
        a_row(impactRows=-1),
        a_row(industries=[{"standard": "SASB", "industryName": "가상", "description": "가상 설명"}]),
        a_row(industries=[{"standard": 1, "industryName": "가상"}]),
        a_row(latestEventMode="false"),
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


def typed_dict_names(module: object) -> set[str]:
    return {name for name, value in inspect.getmembers(module) if is_typeddict(value)}


def test_the_new_component_names_are_these_and_meet_no_other_shape_name() -> None:
    """openapi 는 이름이 같은 컴포넌트를 하나로 합친다 — 새 이름이 입력·결과·옵션·요약 꼴의 이름(기준 컴포넌트)과
    겹치면 기준 컴포넌트의 값이 바뀐다."""
    schema = PAGE.json_schema()
    names = {schema["title"], *schema["$defs"]}
    assert names == NEW_NAMES
    others = typed_dict_names(shapes) | typed_dict_names(options_shapes) | typed_dict_names(digest_shapes)
    assert "MaterialityIndustry" in others  # 분모: 입력의 산업 꼴(설명 칸이 있다)은 이름이 다르다
    assert names & others == set()


def test_the_list_is_company_work() -> None:
    assert OPERATION_POLICY["materiality_runs_list"] is COMPANY
