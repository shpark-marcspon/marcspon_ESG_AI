"""원고작성 꼴은 openapi 에서 모두 닫혀 있다(밴드 RP2d 병합 전 블로커 — 응답 Schema 가 ninja 기본(열림)으로 옮겨 가
additionalProperties: false 가 빠졌던 것). 순수 층: DB 0.

    C1  Drafting 으로 시작하는 컴포넌트 전부(요청 *In·응답·결과 계약·목록 쪽)가 additionalProperties false — 조회 인자
        *Query 는 뺀다(core 목록 꼴대로 열림). 분모: 옮긴 응답 셋과 목록 둘이 그 안에 있다 · RP2b B11: 결과
        drafting.bullets@2 의 새 꼴 넷(basis·parser·sentence·쪽 크기)도 그 안에 있다 · RP2c B10: 결과 @3 의 base·
        reusedFrom 꼴과 목차 차이 응답 둘도 그 안에 있다(조회 인자 DraftingOutlineChangesQuery 는 뺀다) · RPS1 B1:
        실행 줄 넷(DraftingRunItem·Progress·Leaves·Page)도 그 안에 있다(조회 인자 DraftingProjectRunsQuery 는 뺀다)
    C2  (RPS1 B1) 실행 줄의 칸: 시각 둘은 date-time · rebuild 는 null 없는 글자 목록 · 목록 줄 +3·프로젝트 +1 칸이
        required 이고 nullable(latestRun 은 DraftingRunItem 꼴)
"""

import json
from typing import Any

from esgapi.config.api import api


def drafting_components() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(json.dumps(api.get_openapi_schema(path_prefix="")))
    schemas: dict[str, Any] = document["components"]["schemas"]
    return {name: schema for name, schema in schemas.items() if name.startswith("Drafting")}


def test_c1_every_drafting_component_is_closed() -> None:
    found = drafting_components()
    shapes = {name: schema for name, schema in found.items() if not name.endswith("Query")}
    assert {
        "DraftingProject",
        "DraftingProjectDocument",
        "DraftingProjectOutline",
        "DraftingProjectListItem",
        "DraftingProjectPage",
        "DraftingBasis",
        "DraftingParser",
        "DraftingSentence",
        "DraftingPageSize",
        "DraftingBase",
        "DraftingLeafOrigin",
        "DraftingOutlineChanges",
        "DraftingOutlineLeafChange",
        "DraftingRunItem",
        "DraftingRunProgress",
        "DraftingRunLeaves",
        "DraftingRunPage",
    } <= set(shapes)
    assert set(found) - set(shapes) == {
        "DraftingProjectListQuery",
        "DraftingOutlineChangesQuery",
        "DraftingProjectRunsQuery",
    }
    assert [name for name, schema in shapes.items() if schema.get("additionalProperties") is not False] == []


def nullable_ref(spec: dict[str, Any]) -> set[str]:
    """anyOf [{$ref}, {type: null}] 의 컴포넌트 이름(null 갈래가 없으면 빈 집합)."""
    variants = spec.get("anyOf", [])
    if {"type": "null"} not in variants:
        return set()
    return {v["$ref"].rsplit("/", 1)[1] for v in variants if "$ref" in v}


def test_c2_run_item_fields_and_the_added_fields() -> None:
    found = drafting_components()
    item = found["DraftingRunItem"]
    props = item["properties"]
    assert (
        set(item["required"])
        == set(props)
        == {
            "id",
            "status",
            "createdAt",
            "finishedAt",
            "outlineId",
            "baseRunId",
            "rebuild",
            "progress",
            "rejected",
            "leaves",
        }
    )
    assert props["createdAt"]["format"] == "date-time"
    assert {"type": "string", "format": "date-time"} in props["finishedAt"]["anyOf"]
    assert props["rebuild"] == {**props["rebuild"], "type": "array", "items": {"type": "string"}}
    assert set(props["status"]["enum"]) == {"queued", "processing", "done", "failed"}
    assert nullable_ref(props["progress"]) == {"DraftingRunProgress"}
    assert nullable_ref(props["leaves"]) == {"DraftingRunLeaves"}
    assert set(found["DraftingRunLeaves"]["required"]) == {"total", "drafted", "noMaterial", "failed", "notRun"}
    listed = found["DraftingProjectListItem"]
    assert {"documentName", "outlineId", "latestRun"} <= set(listed["required"])
    assert nullable_ref(listed["properties"]["latestRun"]) == {"DraftingRunItem"}
    assert {"type": "null"} in listed["properties"]["documentName"]["anyOf"]
    project = found["DraftingProject"]
    assert "latestRun" in project["required"]
    assert nullable_ref(project["properties"]["latestRun"]) == {"DraftingRunItem"}
