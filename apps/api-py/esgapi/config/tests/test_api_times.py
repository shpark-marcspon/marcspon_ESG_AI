"""응답 시각 칸 전수가 +09:00 으로 나간다(밴드 E2 ③ ⓓ). 모듈을 가로지르므로 config 의 시험이다."""

import importlib
import json
import pkgutil
from datetime import datetime
from typing import Annotated, Any, get_args, get_origin

from ninja import Schema
from pydantic import PlainSerializer

import esgapi
from esgapi.config.api import api
from esgapi.core.schemas import to_seoul_iso


def _models() -> dict[str, type[Schema]]:
    """esgapi 의 schemas 모듈(…/schemas.py, …/schemas/*.py)에 정의된 Schema 전부."""
    found: dict[str, type[Schema]] = {}
    for info in pkgutil.walk_packages(esgapi.__path__, "esgapi."):
        if ".tests" in info.name or not (info.name.endswith(".schemas") or ".schemas." in info.name):
            continue
        module = importlib.import_module(info.name)
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, Schema) and value.__module__ == module.__name__:
                found[f"{value.__module__}.{value.__qualname__}"] = value
    return found


def _parts(annotation: Any) -> list[Any]:
    """`X | None` 를 펴서 X 들. Annotated 는 그대로 둔다."""
    args = get_args(annotation)
    return (
        [a for a in args if a is not type(None)] if args and get_origin(annotation) is not Annotated else [annotation]
    )


def _is_datetime(annotation: Any) -> bool:
    return any(p is datetime or (get_origin(p) is Annotated and get_args(p)[0] is datetime) for p in _parts(annotation))


def _seoul(metadata: Any) -> bool:
    return any(isinstance(m, PlainSerializer) and m.func is to_seoul_iso for m in metadata)


def _datetime_fields() -> list[tuple[str, str, bool]]:
    """(모델, 칸, +09:00 으로 내보내는가)."""
    out: list[tuple[str, str, bool]] = []
    for name, model in _models().items():
        for field, info in model.model_fields.items():
            if _is_datetime(info.annotation):
                seoul = _seoul(info.metadata) or any(
                    _seoul(getattr(p, "__metadata__", ())) for p in _parts(info.annotation)
                )
                out.append((name, field, seoul))
    return out


def test_every_datetime_field_of_a_schema_goes_out_in_seoul_time() -> None:
    fields = _datetime_fields()
    assert [(name, field) for name, field, seoul in fields if not seoul] == []
    assert len(fields) >= 14  # 분모: 스키마 파일의 시각 칸 14(+ 물려받은 칸)


def test_every_date_time_in_the_openapi_document_is_a_seoul_field() -> None:
    document: dict[str, Any] = json.loads(json.dumps(api.get_openapi_schema(path_prefix="")))
    names: set[tuple[str, str]] = set()
    for schema_name, schema in document["components"]["schemas"].items():
        for prop, spec in schema.get("properties", {}).items():
            variants = spec.get("anyOf", [spec])
            if any(v.get("format") == "date-time" for v in variants):
                names.add((schema_name, prop))
    assert len(names) == 45  # 분모(E2 바닥에서 셈): 스키마 9 의 시각 칸 · UA1 +1: CustomerUserOut.createdAt
    # · RM1c ③ +2: RunSegmentOut.startedAt·finishedAt
    # · S3K2b-1 +2: Scope3RowEditOut.editedAt·Scope3RowEditHistoryOut.at
    # · AU1a +1: AuditEventOut.at · AU1b-2 +3: RunLogOut.createdAt·startedAt·finishedAt
    # · AD4D +5: RunLogDetailOut.createdAt·startedAt·finishedAt(물려받은 칸) · RunLogStepOut.startedAt·finishedAt
    # · K1b-1 +2: BranchOut·BranchDetailOut.createdAt
    # · K1b-2a +2: GhgFactorOut.createdAt·updatedAt
    # · S12a +2: EntryIndexOut.lockedAt · EntryHistoryOut.at
    # · RP2d +3: DraftingProject.createdAt · DraftingProjectDocument.attachedAt · DraftingProjectListItem.createdAt
    # · RPS1 +2: DraftingRunItem.createdAt·finishedAt
    # · K1b-3 +1: BranchDetailOut.updatedAt(요청 BranchSaveIn.updatedAt 은 글자 칸이라 셈 0)
    # · S3K2a +1: Scope3YearCategoryOut.lockedAt
    # · RM1b +2: RunStepSegmentsOut.firstStartedAt·lastFinishedAt
    in_models = {(name.rsplit(".", 1)[1], field) for name, field, _ in _datetime_fields()}
    assert names <= in_models
