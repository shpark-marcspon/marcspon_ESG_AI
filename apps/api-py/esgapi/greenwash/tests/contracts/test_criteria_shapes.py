"""판정 기준표 꼴 greenwash.criteria@1(contracts/criteria_shapes.py): 고정 스키마 파일과 바이트까지 같고, 예시 둘이 그
꼴에 맞으며, 모르는 키·id·구분은 꼴에서 거절되고, 클래스 이름이 다른 꼴과 겹치지 않는다.

고친 판 예시(criteria-edited.json)의 바뀐 글·낱말은 지어낸 글이다.
"""

import copy
import json
from pathlib import Path
from typing import Any, cast, get_args, is_typeddict

import pytest
from pydantic import ValidationError

from esgapi.greenwash.contracts import compare_shapes, criteria_shapes, review_shapes, shapes, terms_shapes
from esgapi.greenwash.flows.criteria_e0 import default_criteria

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes" / "criteria"
EXAMPLES = DATA / "contract-examples" / "criteria"
EXAMPLE_NAMES = ["criteria-default.json", "criteria-edited.json"]
ADAPTER = criteria_shapes.CRITERIA_SHAPES[criteria_shapes.SHAPE]


def pinned_text() -> str:
    return json.dumps(ADAPTER.json_schema(), ensure_ascii=False, indent=2) + "\n"


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def test_the_json_schema_is_pinned_byte_for_byte() -> None:
    pinned = PINNED / f"{criteria_shapes.SHAPE}.schema.json"
    assert pinned.read_bytes() == pinned_text().encode("utf-8")
    assert {p.name for p in PINNED.iterdir()} == {pinned.name}
    schema = json.loads(pinned.read_text(encoding="utf-8"))
    assert next(iter(schema["properties"])) == "schemaVersion"
    assert schema["required"] == ["schemaVersion", "version", "rows"]
    assert all(schema["$defs"][name]["additionalProperties"] is False for name in schema["$defs"])


def test_the_examples_are_the_two() -> None:
    assert sorted(p.name for p in EXAMPLES.iterdir()) == EXAMPLE_NAMES


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_an_example_fits_the_shape(name: str) -> None:
    value = load(name)
    assert next(iter(value)) == "schemaVersion"
    ADAPTER.validate_python(value, strict=True)
    ids = [row["id"] for row in value["rows"]]
    assert ids == list(get_args(criteria_shapes.GreenwashCriterionId))
    assert [row["order"] for row in value["rows"]] == list(range(1, 16))


def test_the_edited_example_differs_where_the_web_mock_differs() -> None:
    """고친 판 = high-2 글 고침 · exception-4 끔 · evidence-quantity 에 가이드라인 · keyword-exclusion 낱말 하나."""
    base, edited = load("criteria-default.json"), load("criteria-edited.json")
    assert (base["version"], edited["version"]) == ("colab-2026-01-15-v1", "example-edited-v1")
    changed = {b["id"]: sorted(k for k in b if b[k] != e[k]) for b, e in zip(base["rows"], edited["rows"], strict=True)}
    assert {k: v for k, v in changed.items() if v} == {
        "keyword-exclusion": ["terms"],
        "evidence-quantity": ["guideline"],
        "high-2": ["text"],
        "exception-4": ["enabled"],
    }
    by_id = {row["id"]: row for row in edited["rows"]}
    assert by_id["evidence-quantity"]["guideline"] == {"text": "[기관] · [조항]", "status": "draft"}
    old_terms = next(r for r in base["rows"] if r["id"] == "keyword-exclusion")["terms"]
    assert by_id["keyword-exclusion"]["terms"][:-1] == old_terms


def mutate(path: tuple[str | int, ...], value: object) -> dict[str, Any]:
    out = copy.deepcopy(load("criteria-default.json"))
    target: Any = out
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return out


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param({**load("criteria-default.json"), "extra": 1}, id="unknown-top-key"),
        pytest.param(mutate(("rows", 0, "note"), "x"), id="unknown-row-key"),
        pytest.param(mutate(("rows", 2, "guideline"), {"text": "x", "status": "draft", "u": 1}), id="guideline-key"),
        pytest.param(mutate(("rows", 6, "id"), "high-l"), id="id-typo"),
        pytest.param(mutate(("rows", 6, "category"), "High"), id="category-typo"),
        pytest.param(mutate(("rows", 6, "verdict"), "Low"), id="verdict-unknown"),
        pytest.param(mutate(("rows", 6, "order"), "7"), id="order-string"),
        pytest.param(mutate(("rows", 6, "enabled"), 1), id="enabled-int"),
        pytest.param(mutate(("rows", 2, "guideline"), {"text": "x", "status": "done"}), id="guideline-status"),
        pytest.param(mutate(("schemaVersion",), "greenwash.criteria@2"), id="schema-version"),
    ],
)
def test_the_shape_refuses(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(bad, strict=True)


def test_the_class_names_have_the_prefix_and_do_not_clash() -> None:
    mine = {
        name
        for name, value in vars(criteria_shapes).items()
        if isinstance(value, type) and is_typeddict(value) and value.__module__ == criteria_shapes.__name__
    }
    assert mine == {"GreenwashCriteria", "GreenwashCriterionRow", "GreenwashCriterionGuideline"}
    others = {
        name
        for module in (shapes, review_shapes, compare_shapes, terms_shapes)
        for name, value in vars(module).items()
        if isinstance(value, type) and is_typeddict(value)
    }
    assert others and mine.isdisjoint(others)


def test_the_default_example_is_the_default_criteria() -> None:
    """예시는 상수에서 나온다(발주서 정한 것 2) — flows/criteria_e0.default_criteria() 를 뽑은 바이트와 같다."""
    want = json.dumps(default_criteria(), ensure_ascii=False, indent=2) + "\n"
    assert (EXAMPLES / "criteria-default.json").read_bytes() == want.encode("utf-8")
