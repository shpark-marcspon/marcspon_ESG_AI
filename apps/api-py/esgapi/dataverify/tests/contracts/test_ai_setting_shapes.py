"""AI 설정 판 꼴 셋(contracts/ai_setting_shapes.py — 밴드 DVA1 ②): 고정 스키마 파일과 글자까지 같고, 클래스 이름이
`DataverifyAiSetting` 으로 시작하며, 상한이 표의 칸과 core 판 상수와 같다. 지은 몸이 꼴에 맞고 모르는 키는 거절한다.
몸의 글·이름은 지어낸 것이다."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from esgapi.core.contracts import ai_setting_shapes as core_shapes
from esgapi.dataverify import models
from esgapi.dataverify.contracts import ai_setting_shapes as shapes

PINNED = Path(__file__).resolve().parents[1] / "data" / "flow-shapes" / "ai-setting"
ALL_SHAPES = {**shapes.LIST_SHAPES, **shapes.SETTING_SHAPES, **shapes.DEFAULT_SHAPES}
SUMMARY: dict[str, Any] = {
    "id": 3,
    "name": "v2",
    "title": "지어낸 판 이름",
    "status": "applied",
    "createdAt": "2026-10-23T10:00:00+09:00",
    "createdBy": {"id": 9, "name": None},
    "memo": "",
}
BODIES: dict[str, dict[str, Any]] = {
    shapes.LIST_SHAPE: {
        "schemaVersion": shapes.LIST_SHAPE,
        "companyId": 1,
        "applied": {"kind": "saved", "id": 3},
        "default": {"name": shapes.DEFAULT_NAME, "title": shapes.DEFAULT_TITLE},
        "items": [SUMMARY],
        "total": 1,
    },
    shapes.SETTING_SHAPE: {"schemaVersion": shapes.SETTING_SHAPE, **SUMMARY},
    shapes.DEFAULT_SHAPE: {
        "schemaVersion": shapes.DEFAULT_SHAPE,
        "name": shapes.DEFAULT_NAME,
        "title": shapes.DEFAULT_TITLE,
    },
}


def pinned_text(shape: str) -> str:
    return json.dumps(ALL_SHAPES[shape].json_schema(), ensure_ascii=False, indent=2) + "\n"


@pytest.mark.parametrize("shape", sorted(ALL_SHAPES))
def test_the_json_schema_is_pinned(shape: str) -> None:
    assert pinned_text(shape) == (PINNED / f"{shape}.schema.json").read_text(encoding="utf-8")


def test_the_pinned_files_are_the_three() -> None:
    assert (
        {p.name.removesuffix(".schema.json") for p in PINNED.glob("*.schema.json")}
        == set(ALL_SHAPES)
        == {
            "dataverify.ai-settings@1",
            "dataverify.ai-setting@1",
            "dataverify.ai-setting-default@1",
        }
    )


@pytest.mark.parametrize("shape", sorted(BODIES))
def test_a_body_fits_and_an_unknown_key_is_refused(shape: str) -> None:
    body = BODIES[shape]
    ALL_SHAPES[shape].validate_python(body, strict=True)
    assert next(iter(body)) == "schemaVersion"
    with pytest.raises(ValidationError):
        ALL_SHAPES[shape].validate_python({**body, "criteria": {}}, strict=True)


def test_the_bounds_are_the_table_and_the_core_constants() -> None:
    assert shapes.TITLE_MAX_CHARS == core_shapes.VERSION_TITLE_MAX_CHARS
    assert shapes.MEMO_MAX_CHARS == core_shapes.VERSION_MEMO_MAX_CHARS
    meta = models.DataverifyAiSettingRow._meta
    assert meta.get_field("title").max_length == shapes.TITLE_MAX_CHARS
    assert meta.get_field("memo").max_length == shapes.MEMO_MAX_CHARS
    assert meta.get_field("name").max_length == core_shapes.VERSION_NAME_MAX_CHARS


def test_the_class_names_are_prefixed() -> None:
    names = {
        name for name, value in vars(shapes).items() if isinstance(value, type) and value.__module__ == shapes.__name__
    }
    assert names and all(name.startswith("DataverifyAiSetting") for name in names)
