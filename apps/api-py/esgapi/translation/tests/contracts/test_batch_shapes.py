"""꼴 translation.batch@1(contracts/batch_shapes.py — 밴드 TR3b §3-3): 고정 스키마 파일과 글자까지 같고, 모르는 키·빠진
키·범위 밖 값을 거부한다. 쪽 범위·문체 칸은 옵션 꼴(contracts/shapes.py PageRange·Style)과 같다. 조립은
tests/service/actions/test_batches.py."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from esgapi.translation.contracts import batch_shapes, shapes
from esgapi.translation.contracts.batch_shapes import BATCH_SHAPE, BATCH_SHAPES

PINNED = Path(__file__).resolve().parents[1] / "data" / "api-shapes" / f"{BATCH_SHAPE}.schema.json"
ADAPTER = BATCH_SHAPES[BATCH_SHAPE]


def a_batch() -> dict[str, Any]:
    run = {
        "runId": 3,
        "flowId": "translation.pdf@158",
        "status": "processing",
        "pages": {"start": 1, "end": None},
        "style": {"compareAb": False, "single": "B"},
        "glossaryCounts": {"base": 0, "final": 2},
        "createdAt": "2026-10-22T10:00:00+09:00",
        "startedAt": "2026-10-22T10:00:01+09:00",
        "finishedAt": None,
        "failedStep": None,
        "errorCode": None,
        "steps": [{"step": "translate", "status": "running", "done": 1, "total": 4}],
        "digest": None,
    }
    return {
        "batchKey": "00000000-0000-4000-8000-000000000001",
        "inputKind": "pdf",
        "document": {
            "id": 1,
            "fileName": "지은.docx",
            "uploadedAt": None,
            "uploadedBy": {"userId": 1, "name": "지은 이"},
        },
        "createdBy": {"userId": 1, "name": "지은 이"},
        "parts": [
            {
                "part": "story",
                "latest": run,
                "earlier": [
                    {
                        "runId": 2,
                        "status": "done",
                        "createdAt": "2026-10-22T09:00:00+09:00",
                        "finishedAt": "2026-10-22T09:10:00+09:00",
                        "outcome": "partial",
                    }
                ],
                "round": 2,
            }
        ],
        "state": "active",
        "doneParts": 0,
        "partCount": 1,
    }


def test_the_json_schema_is_pinned() -> None:
    assert json.dumps(ADAPTER.json_schema(), ensure_ascii=False, indent=2) + "\n" == PINNED.read_text(encoding="utf-8")


def test_a_batch_fits_and_a_run_key_fits() -> None:
    ADAPTER.validate_python(a_batch(), strict=True)
    ADAPTER.validate_python({**a_batch(), "batchKey": "run-12"}, strict=True)


def broken() -> list[dict[str, Any]]:
    base = a_batch()
    out: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    out.append({**base, "extra": 1})
    out.append({**base, "batchKey": "run-0"})
    out.append({**base, "batchKey": "RUN-1"})
    out.append({**base, "state": "partial"})
    out.append({**base, "partCount": 0})
    part = copy.deepcopy(base)
    part["parts"][0]["part"] = "cover"
    out.append(part)
    status = copy.deepcopy(base)
    status["parts"][0]["latest"]["status"] = "rejected"
    out.append(status)
    rounds = copy.deepcopy(base)
    rounds["parts"][0]["round"] = 0
    out.append(rounds)
    out.append({**base, "inputKind": "hwp"})  # TRS3: word·pdf 둘만
    no_flow = copy.deepcopy(base)
    del no_flow["parts"][0]["latest"]["flowId"]
    out.append(no_flow)
    return out


@pytest.mark.parametrize("value", broken())
def test_a_broken_batch_is_refused(value: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(value, strict=True)


def test_pages_and_style_are_the_option_shapes() -> None:
    assert batch_shapes.TranslationBatchPages.__annotations__ == shapes.PageRange.__annotations__
    assert batch_shapes.TranslationBatchStyle.__annotations__.keys() == shapes.Style.__annotations__.keys()


def test_a_page_needs_the_company_name_as_a_string() -> None:
    """목록 쪽 꼴(TranslationBatchPage — 고정 스키마 밖)의 companyName(밴드 TRC1 §3-1). 묶음 꼴 @1 에는 없다."""
    pages: Any = TypeAdapter(batch_shapes.TranslationBatchPage)
    page = {"companyName": "지어낸 회사", "count": 1, "isNext": False, "truncated": False, "results": [a_batch()]}
    pages.validate_python(page, strict=True)
    pages.validate_python({**page, "companyName": ""}, strict=True)
    for bad in ({k: v for k, v in page.items() if k != "companyName"}, {**page, "companyName": 7}):
        with pytest.raises(ValidationError):
            pages.validate_python(bad, strict=True)
    assert "companyName" not in json.dumps(ADAPTER.json_schema())


def test_the_two_trs3_fields_are_the_only_change_from_the_frozen_tr3b_schema() -> None:
    """TRS3 는 칸 둘만 더했다(@1 안): latest.flowId(string)·묶음 inputKind(word|pdf). 그 밖 칸은 그대로다."""
    schema = ADAPTER.json_schema()
    run = schema["$defs"]["TranslationBatchRun"]
    batch = schema["$defs"]["TranslationBatch"]
    assert run["properties"]["flowId"]["type"] == "string"
    assert "flowId" in run["required"]
    assert batch["properties"]["inputKind"]["enum"] == ["word", "pdf"]
    assert "inputKind" in batch["required"]
    assert "inputKind" not in schema["$defs"]["TranslationBatchEarlier"]["properties"]
    assert "flowId" not in schema["$defs"]["TranslationBatchEarlier"]["properties"]
