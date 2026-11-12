"""실행 옵션 꼴 greenwash.options@1(contracts/options_shapes.py — 밴드 G1b): 고정 스키마 파일과 바이트까지 같고, 예시
둘이 꼴과 끼움(flows/binding_e0) 둘 다를 지나며, 꼴의 상한이 끼움의 상수와 같고, 클래스 이름이 다른 꼴과 겹치지 않는다.
순수 층. 예시의 낱말은 지은 것이다.
"""

import json
from pathlib import Path
from typing import Any, cast, is_typeddict

import pytest
from pydantic import ValidationError

from esgapi.core.flows.binding import RunOptionsRejected
from esgapi.greenwash.contracts import (
    compare_shapes,
    criteria_shapes,
    options_shapes,
    review_shapes,
    shapes,
    terms_shapes,
)
from esgapi.greenwash.flows import binding_e0
from esgapi.greenwash.flows.binding_e0 import GreenwashBinding
from esgapi.greenwash.tests.flows.settings_store import DefaultOnlyStore
from esgapi.greenwash.tests.flows.support import REAL_MODELS

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes" / "options"
EXAMPLES = DATA / "contract-examples" / "options"
EXAMPLE_NAMES = ["options-extra-terms.json", "options-minimal.json"]
ADAPTER = options_shapes.OPTIONS_SHAPES[options_shapes.SHAPE]


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def test_the_json_schema_is_pinned_byte_for_byte() -> None:
    pinned = PINNED / f"{options_shapes.SHAPE}.schema.json"
    text = json.dumps(ADAPTER.json_schema(), ensure_ascii=False, indent=2) + "\n"
    assert pinned.read_bytes() == text.encode("utf-8")
    assert {p.name for p in PINNED.iterdir()} == {pinned.name}
    schema = json.loads(text)
    assert schema["required"] == ["parts"] and schema["additionalProperties"] is False
    assert schema["$defs"]["GreenwashOptionParts"]["additionalProperties"] is False


def test_the_examples_are_the_two() -> None:
    assert sorted(p.name for p in EXAMPLES.iterdir()) == EXAMPLE_NAMES


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_an_example_fits_the_shape_and_the_binding(name: str) -> None:
    value = load(name)
    ADAPTER.validate_python(value, strict=True)
    GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).check_options(value)


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param({"parts": {"ceo": [1], "company": [], "climate": []}, "criteria": {}}, id="unknown-key"),
        pytest.param({"parts": {"ceo": [1], "company": []}}, id="part-missing"),
        pytest.param({"parts": {"ceo": [0], "company": [], "climate": []}}, id="page-0"),
        pytest.param({"parts": {"ceo": [301], "company": [], "climate": []}}, id="page-301"),
        pytest.param({"parts": {"ceo": [True], "company": [], "climate": []}}, id="page-bool"),
        pytest.param({"parts": {"ceo": ["3"], "company": [], "climate": []}}, id="page-text"),
        pytest.param({"parts": {"ceo": [1], "company": [], "climate": []}, "extraTerms": ["가"] * 101}, id="terms-101"),
    ],
)
def test_the_shape_refuses_what_the_binding_refuses(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(bad, strict=True)
    with pytest.raises(RunOptionsRejected):
        GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).check_options(bad)


def test_the_limits_are_the_bindings() -> None:
    schema = ADAPTER.json_schema()
    page = schema["$defs"]["GreenwashOptionParts"]["properties"]["ceo"]["items"]
    assert (page["minimum"], page["maximum"]) == (1, binding_e0.PAGE_MAX)
    assert schema["properties"]["extraTerms"]["maxItems"] == binding_e0.EXTRA_TERMS_SENT_MAX
    assert tuple(schema["$defs"]["GreenwashOptionParts"]["required"]) == binding_e0.PARTS
    assert frozenset(schema["properties"]) == binding_e0.OPTION_KEYS


def test_the_class_names_have_the_prefix_and_do_not_clash() -> None:
    mine = {
        name
        for name, value in vars(options_shapes).items()
        if isinstance(value, type) and is_typeddict(value) and value.__module__ == options_shapes.__name__
    }
    assert mine == {"GreenwashOptions", "GreenwashOptionParts"}
    others = {
        name
        for module in (shapes, review_shapes, compare_shapes, terms_shapes, criteria_shapes)
        for name, value in vars(module).items()
        if isinstance(value, type) and is_typeddict(value)
    }
    assert others and mine.isdisjoint(others)
