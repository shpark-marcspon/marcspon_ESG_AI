"""꼴 dataverify.digest@1(contracts/digest_shapes.py — 밴드 DV1g §3-1-2·3): 고정 스키마 파일과 글자까지 같고, 모르는
키·빠진 키·범위 밖 값을 거부하며, 계약 파일은 ninja·core.schemas 를 import 하지 않는다. 요약의 셈은
tests/outputs/test_digest.py."""

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from esgapi.dataverify.contracts import digest_shapes
from esgapi.dataverify.contracts.digest_shapes import DIGEST_SHAPE, DIGEST_SHAPES

PINNED = Path(__file__).resolve().parents[1] / "data" / "flow-shapes" / f"{DIGEST_SHAPE}.schema.json"
ADAPTER = DIGEST_SHAPES[DIGEST_SHAPE]


def a_digest() -> dict[str, Any]:
    return {
        "schemaVersion": "dataverify.digest@1",
        "stages": {
            "plan": {"status": "done", "partial": False},
            "review": {"status": "failed", "partial": None},
            "insight": {"status": "not_run", "partial": None},
        },
        "checks": {"ok": 1, "fail": 2, "notComputed": 0, "naValues": 3, "toolErrors": 0},
    }


def test_the_json_schema_is_pinned() -> None:
    assert json.dumps(ADAPTER.json_schema(), ensure_ascii=False, indent=2) + "\n" == PINNED.read_text(encoding="utf-8")


def test_a_digest_fits() -> None:
    ADAPTER.validate_python(a_digest(), strict=True)


def broken() -> list[dict[str, Any]]:
    base = a_digest()
    out: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    out.append({**base, "extra": 1})
    out.append({**base, "schemaVersion": "dataverify.result@2"})
    for key in base["checks"]:
        negative = copy.deepcopy(base)
        negative["checks"][key] = -1
        out.append(negative)
        missing = copy.deepcopy(base)
        del missing["checks"][key]
        out.append(missing)
    bad_status = copy.deepcopy(base)
    bad_status["stages"]["plan"]["status"] = "partial"
    out.append(bad_status)
    no_stage = copy.deepcopy(base)
    del no_stage["stages"]["insight"]
    out.append(no_stage)
    extra_stage = copy.deepcopy(base)
    extra_stage["stages"]["report"] = {"status": "done", "partial": None}
    out.append(extra_stage)
    words = copy.deepcopy(base)
    words["checks"]["ok"] = "1"
    out.append(words)
    return out


@pytest.mark.parametrize("value", broken())
def test_a_broken_digest_is_rejected(value: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(value, strict=True)


def test_the_contract_file_imports_neither_ninja_nor_core_schemas() -> None:
    tree = ast.parse(Path(digest_shapes.__file__).read_text(encoding="utf-8"))
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert not {m for m in modules if m and (m.startswith("ninja") or m == "esgapi.core.schemas")}
