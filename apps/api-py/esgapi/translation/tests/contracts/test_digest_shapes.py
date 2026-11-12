"""꼴 translation.digest@1(contracts/digest_shapes.py — 밴드 TR3a §3-3): 고정 스키마 파일과 글자까지 같고, 모르는
키·빠진 키·범위 밖 값을 거부한다. 요약의 셈은 tests/outputs/test_digest.py."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from esgapi.translation.contracts.digest_shapes import DIGEST_SHAPE, DIGEST_SHAPES

PINNED = Path(__file__).resolve().parents[1] / "data" / "flow-shapes" / f"{DIGEST_SHAPE}.schema.json"
ADAPTER = DIGEST_SHAPES[DIGEST_SHAPE]


def a_digest() -> dict[str, Any]:
    return {
        "schemaVersion": "translation.digest@1",
        "status": "done",
        "rejectionKind": None,
        "outcome": "done",
        "pageCount": 2,
        "failedPages": [],
        "variants": [
            {
                "label": "single",
                "reviewStatus": "reviewed",
                "reviewStoppedAt": None,
                "parseFailedPages": 0,
                "issueCount": 1,
                "issueCounts": {"high": 1, "medium": 0, "low": 0},
                "glossaryMisses": 0,
                "autofixStatus": "done",
                "autofixChangedPages": 1,
                "files": {"bilingual": "translation-bilingual-single.docx", "qa": None, "autofix": None},
            }
        ],
        "warningCount": 0,
    }


def test_the_json_schema_is_pinned() -> None:
    assert json.dumps(ADAPTER.json_schema(), ensure_ascii=False, indent=2) + "\n" == PINNED.read_text(encoding="utf-8")


def test_a_digest_fits() -> None:
    ADAPTER.validate_python(a_digest(), strict=True)


def broken() -> list[dict[str, Any]]:
    base = a_digest()
    out: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    out.append({**base, "extra": 1})
    out.append({**base, "schemaVersion": "translation.result@1"})
    out.append({**base, "outcome": "failed"})
    out.append({**base, "pageCount": -1})
    out.append({**base, "rejectionKind": "unknown"})
    variant = copy.deepcopy(base)
    variant["variants"][0]["reviewStatus"] = "parse_failed"  # parse_failed 쪽은 셈 칸으로 — 멈춤 갈래가 아니다
    out.append(variant)
    files = copy.deepcopy(base)
    files["variants"][0]["files"]["qa"] = ""
    out.append(files)
    extra = copy.deepcopy(base)
    extra["variants"][0]["files"]["zip"] = None
    out.append(extra)
    return out


@pytest.mark.parametrize("value", broken())
def test_a_broken_digest_is_rejected(value: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(value, strict=True)
