# pyright: reportPrivateUsage=false
"""목록 줄 꼴 greenwash.checks@1(contracts/checks_shapes.py — 밴드 G1b): 고정 스키마 파일과 바이트까지 같고, 예시 둘이
strict 로 지나며, 모르는 칸·틀린 값은 거절되고, 새 클래스 이름이 `GreenwashCheck` 로 시작해 다른 꼴과 겹치지 않는다.
순수 층. 예시의 이름·수는 지은 것이다.
"""

import copy
import json
from pathlib import Path
from typing import Any, cast, is_typeddict

import pytest
from pydantic import ValidationError

from esgapi.greenwash.contracts import (
    checks_shapes,
    compare_shapes,
    criteria_shapes,
    options_shapes,
    review_shapes,
    shapes,
    terms_shapes,
)
from esgapi.greenwash.tests.contracts.test_contracts_shapes_paths import _document, _inline, _operations

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes" / "checks"
EXAMPLES = DATA / "contract-examples" / "checks"
EXAMPLE_NAMES = ["checks-empty.json", "checks-normal.json"]
ADAPTER = checks_shapes.CHECKS_SHAPES[checks_shapes.SHAPE]


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def test_the_json_schema_is_pinned_byte_for_byte() -> None:
    pinned = PINNED / f"{checks_shapes.SHAPE}.schema.json"
    text = json.dumps(ADAPTER.json_schema(), ensure_ascii=False, indent=2) + "\n"
    assert pinned.read_bytes() == text.encode("utf-8")
    assert {p.name for p in PINNED.iterdir()} == {pinned.name}
    schema = json.loads(text)
    assert schema["required"] == ["schemaVersion", "currentUserId", "companyName", "documents", "runs", "truncated"]
    assert schema["additionalProperties"] is False
    assert all(d.get("additionalProperties") is False for d in schema["$defs"].values() if d.get("type") == "object")
    run = schema["$defs"]["GreenwashCheckRun"]
    assert run["properties"]["finishedAt"]["anyOf"] == [{"type": "string"}, {"type": "null"}]  # date-time 셈 밖(GCB1)
    assert "finishedAt" in run["required"]


def test_the_examples_are_the_two() -> None:
    assert sorted(p.name for p in EXAMPLES.iterdir()) == EXAMPLE_NAMES


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_an_example_fits_the_shape(name: str) -> None:
    ADAPTER.validate_python(load(name), strict=True)


def _broken(path: tuple[str | int, ...], value: object) -> dict[str, Any]:
    body = copy.deepcopy(load("checks-normal.json"))
    target: Any = body
    for key in path[:-1]:
        target = target[key]
    if value is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return body


@pytest.mark.parametrize(
    ("path", "value"),
    [
        pytest.param(("extra",), 1, id="unknown-top-key"),
        pytest.param(("schemaVersion",), "greenwash.checks@2", id="schema-version"),
        pytest.param(("runs", 0, "runId"), "101", id="run-id-text"),
        pytest.param(("runs", 0, "status"), "running", id="run-status"),
        pytest.param(("runs", 0, "steps", 0, "status"), "queued", id="step-status"),
        pytest.param(("runs", 0, "review", "state"), "done", id="review-state"),
        pytest.param(("runs", 0, "review", "confirmedBy", "name"), "", id="confirmer-name-empty"),
        pytest.param(("runs", 0, "levelCounts", "High"), -1, id="level-negative"),
        pytest.param(("runs", 0, "checkedPages"), True, id="pages-bool"),
        pytest.param(("documents", 0, "pageCount"), -1, id="page-count-negative"),
        pytest.param(("documents", 0, "uploadedBy", "secret"), "x", id="uploader-extra"),
        pytest.param(("documents", 0, "reportYear"), KeyError, id="report-year-missing"),
        pytest.param(("runs", 1, "errorCode"), KeyError, id="error-code-missing"),
        pytest.param(("runs", 1, "errorCode"), 123, id="error-code-number"),
        pytest.param(("runs", 1, "errorCode"), True, id="error-code-bool"),
        pytest.param(("truncated",), KeyError, id="truncated-missing"),
        pytest.param(("truncated",), "false", id="truncated-text"),
        pytest.param(("runs", 0, "failedPageCount"), KeyError, id="failed-page-count-missing"),
        pytest.param(("runs", 0, "failedPageCount"), -1, id="failed-page-count-negative"),
        pytest.param(("runs", 0, "finishedAt"), KeyError, id="finished-at-missing"),
        pytest.param(("runs", 0, "finishedAt"), 1760000000, id="finished-at-number"),
        pytest.param(("runs", 0, "finishedAt"), True, id="finished-at-bool"),
    ],
)
def test_the_shape_refuses_a_wrong_value(path: tuple[str | int, ...], value: object) -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(_broken(path, value), strict=True)


def test_the_class_names_have_the_prefix_and_do_not_clash() -> None:
    mine = {
        name
        for name, value in vars(checks_shapes).items()
        if isinstance(value, type) and is_typeddict(value) and value.__module__ == checks_shapes.__name__
    }
    assert mine == {
        "GreenwashChecks",
        "GreenwashCheckDocument",
        "GreenwashCheckUploader",
        "GreenwashCheckRun",
        "GreenwashCheckStep",
        "GreenwashCheckReview",
    }
    others = {
        name
        for module in (shapes, review_shapes, compare_shapes, terms_shapes, criteria_shapes, options_shapes)
        for name, value in vars(module).items()
        if isinstance(value, type) and is_typeddict(value) and value.__module__ == module.__name__
    }
    assert others and mine.isdisjoint(others)


def test_the_route_answers_the_pinned_shape() -> None:
    """openapi 의 GET /greenwash/checks: 200 = 고정 스키마(구성요소를 펼친 것), 인증 둘(Bearer 먼저), 501·404 없음."""
    document = _document()
    components: dict[str, Any] = document["components"]["schemas"]
    operation = _operations(document)[("get", "/greenwash/checks")]
    assert operation["operationId"] == "greenwash_checks_get"
    assert {"200", "401", "403", "444"} <= set(operation["responses"])
    assert {"404", "501", "413"} & set(operation["responses"]) == set()
    assert "requestBody" not in operation and not operation.get("parameters")
    assert operation.get("security") == [{"CompanyScopedAuth": []}, {"SessionCookie": []}]
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    pinned = ADAPTER.json_schema()
    defs: dict[str, Any] = pinned.get("$defs", {})
    got = _inline(response, lambda ref: components[ref.rsplit("/", 1)[-1]])
    assert got == _inline(pinned, lambda ref: defs[ref.rsplit("/", 1)[-1]])
