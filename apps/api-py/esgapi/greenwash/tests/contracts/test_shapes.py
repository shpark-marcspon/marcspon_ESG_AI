"""결과 꼴 greenwash.result@1(contracts/shapes.py): 고정 스키마 파일과 글자까지 같고, 지은 예시 넷이 그 꼴에 맞으며,
counts 가 items 에서 다시 센 값과 같고, 칸을 빼거나 더하면 빨갛다.

예시 넷(tests/data/contract-examples/)은 로직보다 먼저 손으로 지은 것이다(문장·근거는 전부 지어낸 글). 프론트가
화면을 짓는 데 쓴다. 흐름의 골든과는 따로다.
"""

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from esgapi.greenwash.contracts import shapes

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes"
EXAMPLES = DATA / "contract-examples"
EXAMPLE_NAMES = ["result-normal.json", "result-dry-run.json", "result-no-pages.json", "result-many.json"]
LEVELS = ("High", "Mid", "Low")


def pinned_text(shape: str) -> str:
    return json.dumps(shapes.RESULT_SHAPES[shape].json_schema(), ensure_ascii=False, indent=2) + "\n"


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def check(result: dict[str, Any]) -> None:
    assert next(iter(result)) == "schemaVersion"
    shapes.RESULT_SHAPES[result["schemaVersion"]].validate_python(result, strict=True)


def recount(result: dict[str, Any]) -> dict[str, Any]:
    """parts.build_results_by_part 의 셈: 쪽이 든 파트마다 센다(두 파트 쪽은 두 번)."""
    by_level = dict.fromkeys(LEVELS, 0)
    by_part = {part["name"]: dict.fromkeys(LEVELS, 0) for part in result["parts"]}
    for item in result["items"]:
        by_level[item["level"]] += 1
        for part in result["parts"]:
            if item["page"] in part["pages"]:
                by_part[part["name"]][item["level"]] += 1
    return {"total": len(result["items"]), "byLevel": by_level, "byPart": by_part}


def test_the_json_schema_is_pinned() -> None:
    assert pinned_text(shapes.SHAPE) == (PINNED / f"{shapes.SHAPE}.schema.json").read_text(encoding="utf-8")


def test_every_shape_is_pinned() -> None:
    """결과 꼴 result@1 만 본다(같은 폴더의 하위 폴더 compare/·review/ 는 계약 밴드 GC1 의 꼴)."""
    files = {p.name.removesuffix(".schema.json") for p in PINNED.glob("greenwash.result@*.schema.json")}
    assert set(shapes.RESULT_SHAPES) == files == {"greenwash.result@1"}


def test_the_examples_are_the_four() -> None:
    """결과 예시 result-*.json 만 본다(하위 폴더 compare/·review/ 는 GC1 의 예시)."""
    assert sorted(p.name for p in EXAMPLES.glob("result-*.json")) == sorted(EXAMPLE_NAMES)


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_an_example_fits_the_shape(name: str) -> None:
    result = load(name)
    check(result)
    assert result["pages"] == sorted({p for part in result["parts"] for p in part["pages"]})
    for item in result["items"]:
        assert item["parts"] == [part["name"] for part in result["parts"] if item["page"] in part["pages"]]
        assert item["exampleSentence"] is None  # E0 는 늘 null
        assert item["fixParagraph"]
        assert len(item["fixParagraph"]) >= (40 if item["level"] == "Low" else 60)  # 짧으면 노트북이 바꾼다
        if item["level"] == "Low":  # GW1 checker.analyze_page 의 Low 갈래
            low = (item["riskTags"], item["confirmedInEvidence"], item["missingFields"], item["evidenceInternal"])
            assert low == (["선언적 문장"], [], [], "")
    low_pages = [item["page"] for item in result["items"] if item["level"] == "Low"]
    assert len(low_pages) == len(set(low_pages))  # Low 는 쪽마다 많아야 하나
    if result["dryRun"] is None:
        assert result["counts"] == recount(result)
        assert result["candidateStats"] is not None
        assert result["report"] == {"file": "greenwash-report.xlsx"}
    else:
        assert result["items"] == []
        assert (result["candidateStats"], result["counts"], result["report"]) == (None, None, None)


def test_the_normal_example_covers_what_the_screen_needs() -> None:
    result = load("result-normal.json")
    items = result["items"]
    assert {item["level"] for item in items} == set(LEVELS)
    assert any(len(item["parts"]) == 2 for item in items)  # 한 문장이 두 파트
    assert any(item["evidencePages"] == [] for item in items)
    assert any(item["position"] is not None and len(item["position"]["boxes"]) == 2 for item in items)
    assert any(item["position"] is None for item in items)
    assert result["candidateStats"]["failedPages"]
    assert result["wordCounts"]["total"]
    by_part_sum = sum(sum(levels.values()) for levels in result["counts"]["byPart"].values())
    assert by_part_sum > result["counts"]["total"]  # 두 파트 쪽을 두 번 셈


def test_the_other_examples() -> None:
    assert load("result-no-pages.json")["items"] == []
    assert load("result-no-pages.json")["pages"] == []
    many = load("result-many.json")
    assert len(many["items"]) >= 30
    assert all(sum(levels.values()) > 0 for levels in many["counts"]["byPart"].values())


def test_a_missing_or_extra_key_is_rejected() -> None:
    base = load("result-normal.json")
    check(base)
    broken: list[dict[str, Any]] = [
        {k: v for k, v in base.items() if k != key} for key in ("schemaVersion", "items", "counts", "dryRun")
    ]
    broken.append({**base, "unknown": 1})
    broken.append({**base, "provider": "mock"})  # GW1 에서 뺀 칸
    broken.append({**base, "schemaVersion": "greenwash.result@2"})
    for key in ("position", "exampleSentence", "evidencePages", "parts"):
        no_key = copy.deepcopy(base)
        del no_key["items"][0][key]
        broken.append(no_key)
    nested = copy.deepcopy(base)
    nested["items"][0]["span"] = None  # GW1 의 칸 이름
    broken.append(nested)
    bad_level = copy.deepcopy(base)
    bad_level["items"][0]["level"] = "Safe"
    broken.append(bad_level)
    bad_box = copy.deepcopy(base)
    bad_box["items"][0]["position"]["boxes"][0] = [1.0, 2.0, 3.0]
    broken.append(bad_box)
    page_zero = copy.deepcopy(base)
    page_zero["items"][0]["page"] = 0
    broken.append(page_zero)
    broken.append({**base, "source": {**base["source"], "sha256": "x"}})
    # 갈래가 섞이면 빨갛다: 점검 결과에 dry_run, dry-run 결과에 items·counts·report
    dry = load("result-dry-run.json")
    check(dry)
    broken.append({**base, "dryRun": dry["dryRun"]})
    broken.append({**base, "candidateStats": None})
    broken.append({**dry, "items": base["items"]})
    broken.append({**dry, "counts": base["counts"]})
    broken.append({**dry, "report": base["report"]})
    broken.append({**dry, "dryRun": None})
    for item in broken:
        with pytest.raises(ValidationError):
            shapes.RESULT_SHAPES[shapes.SHAPE].validate_python(item, strict=True)


def test_schema_version_must_be_the_first_key() -> None:
    base = load("result-normal.json")
    moved = {"source": base["source"], **{k: v for k, v in base.items() if k != "source"}}
    with pytest.raises(AssertionError):
        check(moved)
