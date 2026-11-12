"""꼴 materiality.digest@1(contracts/digest_shapes.py — 밴드 IR3c §3-1-2·3): 고정 스키마 파일과 글자까지 같고, 모르는
키·빠진 키·범위 밖 값을 거부하며, 계약 파일은 ninja·core.schemas 를 import 하지 않는다. 요약의 셈은
tests/outputs/test_digest.py."""

import ast
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from esgapi.materiality.contracts import digest_shapes
from esgapi.materiality.contracts.digest_shapes import DIGEST_SHAPE, DIGEST_SHAPES

PINNED = Path(__file__).resolve().parents[1] / "data" / "flow-shapes" / f"{DIGEST_SHAPE}.schema.json"
ADAPTER = DIGEST_SHAPES[DIGEST_SHAPE]


def a_digest() -> dict[str, Any]:
    return {"schemaVersion": "materiality.digest@1", "impactRows": 3, "pathwayRows": 0}


def test_the_json_schema_is_pinned() -> None:
    assert json.dumps(ADAPTER.json_schema(), ensure_ascii=False, indent=2) + "\n" == PINNED.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "value", [a_digest(), {"schemaVersion": "materiality.digest@1", "impactRows": None, "pathwayRows": None}]
)
def test_a_digest_fits(value: dict[str, Any]) -> None:
    ADAPTER.validate_python(value, strict=True)


def broken() -> list[dict[str, Any]]:
    base = a_digest()
    out: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    out.append({**base, "extra": 1})
    out.append({**base, "schemaVersion": "materiality.result@2"})
    for key in ("impactRows", "pathwayRows"):
        out.append({**base, key: -1})
        out.append({**base, key: "1"})
        out.append({**base, key: 1.0})
        out.append({**base, key: True})
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
