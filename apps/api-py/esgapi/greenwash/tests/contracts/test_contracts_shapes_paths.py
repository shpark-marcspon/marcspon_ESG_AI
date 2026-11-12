"""그린워싱 계약 — 비교 compare@1·검토 review@3 꼴, 예시 일곱, 경로 넷의 자리(몸은 501). 순수 층(DB 없음).
(GC1 `MARC-TICK-95` 에서 생김)

잰다: 꼴 둘이 모르는 키를 거절하고 고정 스키마와 글자까지 같다 · 예시 일곱이 꼴을 지나고 G1a 의 결과와 맞물린다
(ItemRef 가 가리키는 결과 항목과 칸이 같다, 분류의 규칙, counts) · PUT 본문에 테넌트·사용자 칸이 없다 ·
openapi 의 경로 넷(operationId, 404·501·413, 세션 인증, 구성요소 이름, 200 응답 = 고정 스키마) · 경로 호출(401, 501).

예시의 자리(감독 결정 2026-10-15 밤): G1a 의 테스트가 contract-examples/*.json·flow-shapes/*.schema.json 을 자기 것으로
못 박으므로 이 밴드의 것은 계약 이름의 한 단 아래 폴더(compare/·review/)에 둔다.
compare-normal 의 방향(감독 결정): target(이번 판) = G1a 의 result-normal.json(확정본), base(앞 판) = 지어낸 v1 결과
compare/compare-normal.base-result.json. result-normal 의 항목이 넷뿐이라 base 쪽 짝 여섯을 가리킬 수 없어서다.
"""

import copy
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast, get_type_hints

import pytest
from ninja.testing import TestClient
from pydantic import TypeAdapter, ValidationError

from esgapi.config.api import api
from esgapi.core.exceptions import ApplicationError
from esgapi.core.tenancy.session import Role, Session
from esgapi.greenwash.contracts import compare_shapes, review_shapes, shapes
from esgapi.greenwash.service.apis import greenwash as routes

DATA = Path(__file__).resolve().parents[1] / "data"
EXAMPLES = DATA / "contract-examples"
PINNED = DATA / "flow-shapes"
OUTCOMES = (
    "resolved_deleted",
    "resolved_not_flagged",
    "resolved_undetermined",
    "remaining",
    "level_changed",
    "new",
    "out_of_scope",
)
COMPARE_EXAMPLES = ["compare-normal.json", "compare-unconfirmed.json", "compare-empty.json"]
REVIEW_EXAMPLES = ["review-pending.json", "review-in-review.json", "review-confirmed.json"]
EDITED_EXAMPLE = "review-edited.json"  # review@3 의 고침·근거 고침·재판단(GRJ1)
# 고침은 G1b-3 — tests/contracts/test_review_edits_shapes.py 가 잰다
BASE_RESULT = "compare-normal.base-result.json"
TENANT_OR_USER = ("tenant", "company", "user", "role", "owner")


def load(*parts: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(EXAMPLES.joinpath(*parts).read_text(encoding="utf-8")))


def compare(name: str) -> dict[str, Any]:
    return load("compare", name)


def review(name: str) -> dict[str, Any]:
    return load("review", name)


def pinned_text(adapter: TypeAdapter[Any]) -> str:
    return json.dumps(adapter.json_schema(), ensure_ascii=False, indent=2) + "\n"


def check_compare(value: dict[str, Any]) -> None:
    assert next(iter(value)) == "schemaVersion"
    compare_shapes.COMPARE_SHAPES[value["schemaVersion"]].validate_python(value, strict=True)


def check_review(value: dict[str, Any]) -> None:
    assert next(iter(value)) == "schemaVersion"
    review_shapes.REVIEW_SHAPES[value["schemaVersion"]].validate_python(value, strict=True)


def check_result(value: dict[str, Any]) -> None:
    assert next(iter(value)) == "schemaVersion"
    shapes.RESULT_SHAPES[value["schemaVersion"]].validate_python(value, strict=True)


# ── §3-1 꼴: strict, 고정 스키마, 첫 키 ────────────────────────────────


@pytest.mark.parametrize(
    ("shape", "adapter", "path"),
    [
        (compare_shapes.SHAPE, compare_shapes.COMPARE_SHAPES[compare_shapes.SHAPE], "compare"),
        (review_shapes.SHAPE, review_shapes.REVIEW_SHAPES[review_shapes.SHAPE], "review"),
    ],
)
def test_the_json_schema_is_pinned_byte_for_byte(shape: str, adapter: TypeAdapter[Any], path: str) -> None:
    pinned = PINNED / path / f"{shape}.schema.json"
    assert pinned.read_bytes() == pinned_text(adapter).encode("utf-8")
    assert {p.name for p in (PINNED / path).iterdir()} == {pinned.name}


def test_the_shapes_start_with_schema_version() -> None:
    """꼴 셋(compare·review, 그리고 base-result 가 따르는 result@1 의 두 갈래)의 첫 칸이 schemaVersion 이다."""
    for typed in (
        compare_shapes.GreenwashCompareResult,
        review_shapes.GreenwashReviewState,
        shapes.ScanResult,
        shapes.DryRunResult,
    ):
        assert next(iter(get_type_hints(typed))) == "schemaVersion", typed


def test_unknown_or_missing_keys_are_rejected() -> None:
    normal = compare("compare-normal.json")
    broken: list[dict[str, Any]] = [{**normal, "extra": 1}, {k: v for k, v in normal.items() if k != "counts"}]
    pair = copy.deepcopy(normal)
    pair["pairs"][0]["base"]["id"] = 1
    broken.append(pair)
    side = copy.deepcopy(normal)
    side["base"]["company_id"] = 1
    broken.append(side)
    counts = copy.deepcopy(normal)
    del counts["counts"]["new"]
    broken.append(counts)
    outcome = copy.deepcopy(normal)
    outcome["pairs"][0]["outcome"] = "resolved"
    broken.append(outcome)
    as_text = copy.deepcopy(normal)
    as_text["base"]["runId"] = "91"
    broken.append(as_text)
    broken.append({**normal, "schemaVersion": "greenwash.compare@2"})
    for value in broken:
        with pytest.raises(ValidationError):
            compare_shapes.COMPARE_SHAPES[compare_shapes.SHAPE].validate_python(value, strict=True)

    state = review("review-in-review.json")
    rejected: list[dict[str, Any]] = [{**state, "extra": 1}, {**state, "state": "done"}]
    mark = copy.deepcopy(state)
    mark["marks"][0]["decision"] = "maybe"
    rejected.append(mark)
    no_reason = copy.deepcopy(state)
    del no_reason["marks"][0]["excludeReason"]
    rejected.append(no_reason)
    for value in rejected:
        with pytest.raises(ValidationError):
            review_shapes.REVIEW_SHAPES[review_shapes.SHAPE].validate_python(value, strict=True)


def test_schema_version_must_be_the_first_key() -> None:
    normal = compare("compare-normal.json")
    moved = {"base": normal["base"], **{k: v for k, v in normal.items() if k != "base"}}
    with pytest.raises(AssertionError):
        check_compare(moved)


# ── §3-2 예시가 꼴을 지난다 ────────────────────────────────────────────


def test_the_examples_are_these() -> None:
    assert sorted(p.name for p in (EXAMPLES / "compare").iterdir()) == sorted([*COMPARE_EXAMPLES, BASE_RESULT])
    assert sorted(p.name for p in (EXAMPLES / "review").iterdir()) == sorted([*REVIEW_EXAMPLES, EDITED_EXAMPLE])


@pytest.mark.parametrize("name", COMPARE_EXAMPLES)
def test_a_compare_example_fits(name: str) -> None:
    check_compare(compare(name))


@pytest.mark.parametrize("name", REVIEW_EXAMPLES)
def test_a_review_example_fits(name: str) -> None:
    check_review(review(name))


def test_the_base_result_fits_result_at_1() -> None:
    """지어낸 v1 결과는 result@1 꼴을 지나고, G1a 예시와 같은 셈(parts·pages·counts)을 지킨다."""
    result = load("compare", BASE_RESULT)
    check_result(result)
    assert result["dryRun"] is None
    assert result["pages"] == sorted({p for part in result["parts"] for p in part["pages"]})
    by_level = dict.fromkeys(("High", "Mid", "Low"), 0)
    by_part = {part["name"]: dict.fromkeys(("High", "Mid", "Low"), 0) for part in result["parts"]}
    for item in result["items"]:
        assert item["parts"] == [part["name"] for part in result["parts"] if item["page"] in part["pages"]]
        assert item["page"] in result["pages"]
        by_level[item["level"]] += 1
        for part in result["parts"]:
            if item["page"] in part["pages"]:
                by_part[part["name"]][item["level"]] += 1
    assert result["counts"] == {"total": len(result["items"]), "byLevel": by_level, "byPart": by_part}
    low_pages = [item["page"] for item in result["items"] if item["level"] == "Low"]
    assert len(low_pages) == len(set(low_pages))


# ── §3-3 검토 예시의 규칙 ──────────────────────────────────────────────


@pytest.mark.parametrize("name", REVIEW_EXAMPLES)
def test_review_marks_point_into_result_normal(name: str) -> None:
    state = review(name)
    size = len(load("result-normal.json")["items"])
    indexes = [mark["itemIndex"] for mark in state["marks"]]
    assert all(0 <= index < size for index in indexes)
    assert indexes == sorted(set(indexes))  # 겹치지 않고 오름차순
    for mark in state["marks"]:
        assert (mark["excludeReason"] is not None) == (mark["decision"] == "excluded")
        if mark["excludeReason"] is not None:
            assert mark["excludeReason"].strip()
    assert (state["confirmedAt"] is not None) == (state["state"] == "confirmed")
    if state["confirmedAt"] is not None:
        assert (
            datetime.fromisoformat(state["confirmedAt"]).utcoffset()
            == datetime.fromisoformat("2026-01-01T00:00:00+09:00").utcoffset()
        )


def test_the_review_examples_cover_the_states() -> None:
    assert [review(name)["state"] for name in REVIEW_EXAMPLES] == ["pending", "in_review", "confirmed"]
    assert review("review-pending.json")["marks"] == []
    in_review = review("review-in-review.json")
    assert {mark["decision"] for mark in in_review["marks"]} == {"adopted", "excluded"}
    assert len(in_review["marks"]) < len(load("result-normal.json")["items"])  # 미검토가 남는다
    assert len({review(name)["runId"] for name in REVIEW_EXAMPLES}) == 1


# ── §3-4 비교 예시와 결과의 맞물림 ─────────────────────────────────────

# 예시마다 쪽(base·target)이 가리키는 결과 파일. compare-empty 는 짝이 없어 가리키는 것이 없다.
POINTS_TO: dict[str, dict[str, tuple[str, ...]]] = {
    "compare-normal.json": {"base": ("compare", BASE_RESULT), "target": ("result-normal.json",)},
    "compare-unconfirmed.json": {"base": ("compare", BASE_RESULT), "target": ("result-normal.json",)},
}
PRESENT: dict[str, tuple[bool, bool] | None] = {
    "remaining": (True, True),
    "level_changed": (True, True),
    "resolved_deleted": (True, False),
    "resolved_not_flagged": (True, False),
    "resolved_undetermined": (True, False),
    "new": (False, True),
    "out_of_scope": None,  # 어느 한쪽
}


@pytest.mark.parametrize("name", COMPARE_EXAMPLES)
def test_compare_refs_match_the_result_items(name: str) -> None:
    value = compare(name)
    for side in ("base", "target"):
        refs = [pair[side] for pair in value["pairs"] if pair[side] is not None]
        if not refs:
            continue
        result = load(*POINTS_TO[name][side])
        indexes = [ref["itemIndex"] for ref in refs]
        assert len(indexes) == len(set(indexes)), (name, side)  # 한 문장은 한 짝에만
        for ref in refs:
            assert 0 <= ref["itemIndex"] < len(result["items"]), (name, side, ref)
            item = result["items"][ref["itemIndex"]]
            fields = ("sentence", "level", "parts", "page")
            assert {k: ref[k] for k in fields} == {k: item[k] for k in fields}, (name, side, ref)


@pytest.mark.parametrize("name", COMPARE_EXAMPLES)
def test_compare_outcome_rules_and_counts(name: str) -> None:
    value = compare(name)
    for pair in value["pairs"]:
        has = (pair["base"] is not None, pair["target"] is not None)
        expected = PRESENT[pair["outcome"]]
        if expected is None:
            assert has in ((True, False), (False, True)), pair
        else:
            assert has == expected, pair
        if pair["outcome"] == "remaining":
            assert pair["base"]["level"] == pair["target"]["level"], pair
        if pair["outcome"] == "level_changed":
            assert pair["base"]["level"] != pair["target"]["level"], pair
    recount = dict.fromkeys(OUTCOMES, 0)
    for pair in value["pairs"]:
        recount[pair["outcome"]] += 1
    assert value["counts"] == recount
    assert list(value["counts"]) == list(OUTCOMES)


def test_compare_normal_has_all_seven_and_both_out_of_scope_sides() -> None:
    value = compare("compare-normal.json")
    assert {pair["outcome"] for pair in value["pairs"]} == set(OUTCOMES)
    sides = {
        (pair["base"] is not None, pair["target"] is not None)
        for pair in value["pairs"]
        if pair["outcome"] == "out_of_scope"
    }
    assert sides == {(True, False), (False, True)}
    assert (value["base"]["unconfirmed"], value["target"]["unconfirmed"]) == (False, False)
    assert value["base"]["documentId"] != value["target"]["documentId"]


def test_a_confirmed_target_compares_exactly_its_adopted_sentences() -> None:
    """확정본은 채택한 문장만 견준다(감독 조건): compare-normal 의 target 은 review-confirmed 의 실행이고, target 쪽
    문장 = 그 검토에서 채택한 문장. base(v1 확정본)는 지어낸 결과의 문장을 전부 채택한 것으로 둔다."""
    value = compare("compare-normal.json")
    confirmed = review("review-confirmed.json")
    assert value["target"]["runId"] == confirmed["runId"]
    adopted = {mark["itemIndex"] for mark in confirmed["marks"] if mark["decision"] == "adopted"}
    target = {pair["target"]["itemIndex"] for pair in value["pairs"] if pair["target"] is not None}
    assert target == adopted
    base = {pair["base"]["itemIndex"] for pair in value["pairs"] if pair["base"] is not None}
    assert base == set(range(len(load("compare", BASE_RESULT)["items"])))


def test_the_other_compare_examples() -> None:
    unconfirmed = compare("compare-unconfirmed.json")
    assert unconfirmed["target"]["unconfirmed"] is True
    in_review = review("review-in-review.json")
    assert unconfirmed["target"]["runId"] == in_review["runId"]  # 아직 확정 안 된 실행
    # 미확정은 전부 견준다: 검토에서 제외한 문장도 target 쪽에 나온다.
    excluded = {mark["itemIndex"] for mark in in_review["marks"] if mark["decision"] == "excluded"}
    target = {pair["target"]["itemIndex"] for pair in unconfirmed["pairs"] if pair["target"] is not None}
    assert excluded and excluded <= target
    assert target == set(range(len(load("result-normal.json")["items"])))  # 결과의 문장 전부
    empty = compare("compare-empty.json")
    assert empty["pairs"] == []
    assert set(empty["counts"].values()) == {0}


# ── §3-5 PUT 본문 ──────────────────────────────────────────────────────


def _property_names(schema: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(schema, dict):
        for key, value in cast("dict[str, Any]", schema).items():
            if key == "properties" and isinstance(value, dict):
                names |= set(cast("dict[str, Any]", value))
            names |= _property_names(value)
    elif isinstance(schema, list):
        for value in cast("list[Any]", schema):
            names |= _property_names(value)
    return names


def _objects(schema: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(schema, dict):
        node = cast("dict[str, Any]", schema)
        if "properties" in node:
            found.append(node)
        for value in node.values():
            found += _objects(value)
    elif isinstance(schema, list):
        for value in cast("list[Any]", schema):
            found += _objects(value)
    return found


def test_the_review_update_body_is_strict_and_has_no_tenant_or_user_field() -> None:
    schema = routes.GreenwashReviewUpdate.model_json_schema()
    assert schema["additionalProperties"] is False
    assert all(node.get("additionalProperties") is False for node in _objects(schema))  # 안의 표시도
    names = {name.lower() for name in _property_names(schema)}
    assert names == {
        "state",
        "marks",
        "itemindex",
        "decision",
        "excludereason",
        "edits",
        "level",
        "reasonbullets",
        "fixparagraph",
        "evidence",  # GRJ1 근거 고침: evidence[{itemIndex, removed, added[{text, page}]}]
        "removed",
        "added",
        "text",
        "page",
    }
    assert [name for name in names if any(word in name for word in TENANT_OR_USER)] == []


@pytest.mark.parametrize("value", [True, 1.0, "1"])
def test_the_review_update_body_does_not_coerce_an_index(value: object) -> None:
    """본문의 표시(중첩 TypedDict)도 타입을 바꿔 받지 않는다. config/tests/test_request_schemas_reject_bool.py 는
    BaseModel 만 훑어 이 칸을 못 본다 — 그래서 여기서 잰다(JSON 으로 온 본문과 같은 길)."""
    body = {"marks": [{"itemIndex": value, "decision": "adopted", "excludeReason": None}]}
    with pytest.raises(ValidationError):
        routes.GreenwashReviewUpdate.model_validate_json(json.dumps(body))
    routes.GreenwashReviewUpdate.model_validate_json(
        json.dumps({**body, "marks": [{**body["marks"][0], "itemIndex": 1}]})
    )


# ── §3-6 openapi ───────────────────────────────────────────────────────

ROUTES = {
    ("get", "/greenwash/runs/{run_id}/result"): "greenwash_result_get",
    ("get", "/greenwash/runs/{run_id}/review"): "greenwash_review_get",
    ("put", "/greenwash/runs/{run_id}/review"): "greenwash_review_put",
    ("get", "/greenwash/compare"): "greenwash_compare_get",
}
PINNED_OF: dict[str, TypeAdapter[Any]] = {
    "greenwash_result_get": shapes.RESULT_SHAPES[shapes.SHAPE],
    "greenwash_review_get": review_shapes.REVIEW_SHAPES[review_shapes.SHAPE],
    "greenwash_review_put": review_shapes.REVIEW_SHAPES[review_shapes.SHAPE],
    "greenwash_compare_get": compare_shapes.COMPARE_SHAPES[compare_shapes.SHAPE],
}
# 구조를 견주기 전에 빼거나 고르는 꾸밈 칸: 이름이 붙는 자리 둘뿐이다. description·제약·차례는 그대로 견준다.
#   title                    빼다(스키마 마디의 칸만 — properties 안의 칸 이름은 건드리지 않는다)
#   discriminator.mapping    값이 $ref 글자(`#/$defs/X` ↔ `#/components/schemas/X`)라 끝의 이름 X 로 고른다
DECORATION = ("title",)


def _document() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(json.dumps(api.get_openapi_schema(path_prefix=""))))


def _operations(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(m, p): op for p, item in document["paths"].items() for m, op in item.items()}


def _inline(schema: Any, lookup: Callable[[str], Any], seen: tuple[str, ...] = ()) -> Any:
    """$ref 를 풀어 넣고 꾸밈 칸을 뺀다."""
    if isinstance(schema, dict):
        node = cast("dict[str, Any]", schema)
        if "$ref" in node:
            ref = cast("str", node["$ref"])
            assert ref not in seen, ref  # 되도는 꼴은 없다
            rest = {k: v for k, v in node.items() if k != "$ref"}
            return _inline({**lookup(ref), **rest}, lookup, (*seen, ref))
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in DECORATION or key == "$defs":
                continue
            if key == "properties" and isinstance(value, dict):
                fields = cast("dict[str, Any]", value)
                out[key] = {name: _inline(field, lookup, seen) for name, field in fields.items()}
            elif key == "discriminator" and isinstance(value, dict):
                rule = cast("dict[str, Any]", value)
                mapping = cast("dict[str, str]", rule.get("mapping", {}))
                out[key] = {**rule, "mapping": {tag: ref.rsplit("/", 1)[-1] for tag, ref in mapping.items()}}
            else:
                out[key] = _inline(value, lookup, seen)
        return out
    if isinstance(schema, list):
        return [_inline(v, lookup, seen) for v in cast("list[Any]", schema)]
    return schema


def _refs(schema: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(schema, dict):
        node = cast("dict[str, Any]", schema)
        if isinstance(node.get("$ref"), str):
            found.add(cast("str", node["$ref"]).rsplit("/", 1)[-1])
        for value in node.values():
            found |= _refs(value)
    elif isinstance(schema, list):
        for value in cast("list[Any]", schema):
            found |= _refs(value)
    return found


def _reachable(start: Any, components: dict[str, Any]) -> set[str]:
    todo, seen = list(_refs(start)), set[str]()
    while todo:
        name = todo.pop()
        if name not in seen:
            seen.add(name)
            todo += list(_refs(components[name]))
    return seen


def test_the_four_routes_are_declared() -> None:
    document = _document()
    operations = _operations(document)
    gc2 = {
        ("get", "/greenwash/runs/{run_id}/report"): "greenwash_report_get",
        ("get", "/greenwash/terms/default"): "greenwash_terms_default",
    }  # 보고서·기본 단어 두 경로(그 꼴은 test_contracts_review_report_terms.py 가 잰다)
    g1b = {("get", "/greenwash/checks"): "greenwash_checks_get"}  # 목록 줄(G1b-1 — 꼴은 test_checks_shapes.py)
    # 재판단 만들기(GRJ1 — 꼴·상태는 tests/service/apis/test_greenwash_rejudge.py)
    grj1 = {("post", "/greenwash/runs/{run_id}/items/{item_index}/rejudge"): "greenwash_item_rejudge"}
    # 2차 엔진 결과(GE1b ④ — 꼴·상태는 tests/service/actions/test_engine_g1_result2.py)
    ge1b = {("get", "/greenwash/runs/{run_id}/result2"): "greenwash_result2_get"}
    assert {key: op["operationId"] for key, op in operations.items() if key[1].startswith("/greenwash")} == (
        ROUTES | gc2 | g1b | grj1 | ge1b
    )
    for key, operation_id in ROUTES.items():
        operation = operations[key]
        codes = set(operation["responses"])
        assert {"200", "401", "403", "404", "444"} <= codes, key  # 444: Bearer 를 받는다(K2b)
        assert ("501" in codes) == (operation_id not in BODIED), key  # G1b-1: 몸 생긴 셋은 501 을 걷었다
        assert ("413" in codes) == (key[0] == "put"), key
        assert ("requestBody" in operation) == (key[0] == "put"), key
        # Bearer 먼저, 머리가 없으면 옛 쿠키(K2b)
        assert operation.get("security") == [{"CompanyScopedAuth": []}, {"SessionCookie": []}], key
        for code in sorted({"404", "501"} & codes):
            schema = operation["responses"][code]["content"]["application/json"]["schema"]
            assert schema == {"$ref": "#/components/schemas/ErrorBody"}, (key, code)
        assert operation_id.startswith("greenwash_")
    body = operations[("put", "/greenwash/runs/{run_id}/review")]["requestBody"]["content"]["application/json"]
    assert body["schema"] == {"$ref": "#/components/schemas/GreenwashReviewUpdate"}
    params = {p["name"]: p for p in operations[("get", "/greenwash/compare")]["parameters"]}
    assert set(params) == {"base", "target"}
    assert all(p["in"] == "query" and p["required"] and p["schema"]["type"] == "integer" for p in params.values())
    for key in ROUTES:
        if "{run_id}" in key[1]:
            (param,) = operations[key]["parameters"]
            assert (param["name"], param["in"], param["schema"]["type"]) == ("run_id", "path", "integer")


@pytest.mark.parametrize("key", sorted(ROUTES))
def test_each_200_response_is_the_pinned_shape(key: tuple[str, str]) -> None:
    document = _document()
    components: dict[str, Any] = document["components"]["schemas"]
    response = _operations(document)[key]["responses"]["200"]["content"]["application/json"]["schema"]
    pinned = PINNED_OF[ROUTES[key]].json_schema()
    defs: dict[str, Any] = pinned.get("$defs", {})
    got = _inline(response, lambda ref: components[ref.rsplit("/", 1)[-1]])
    want = _inline(pinned, lambda ref: defs[ref.rsplit("/", 1)[-1]])
    assert got == want


def test_gc1_component_names_have_the_prefix_and_result_names_do_not_collide() -> None:
    document = _document()
    components: dict[str, Any] = document["components"]["schemas"]
    operations = _operations(document)
    result_names = set(shapes.RESULT_SHAPES[shapes.SHAPE].json_schema()["$defs"])
    gc1: set[str] = set()
    for key, operation_id in ROUTES.items():
        if operation_id != "greenwash_result_get":
            gc1 |= _reachable(operations[key]["responses"]["200"], components)
    gc1 |= _reachable(operations[("put", "/greenwash/runs/{run_id}/review")]["requestBody"], components)
    assert gc1, "GC1 의 구성요소를 못 찾았다"
    assert sorted(name for name in gc1 if not name.startswith("Greenwash")) == []
    # result@1 의 중첩 이름: 그 이름의 구성요소가 G1a 의 꼴 그대로이고(덮이지 않음),
    # 그린워싱 밖의 경로는 그 이름에 닿지 않는다.
    defs = shapes.RESULT_SHAPES[shapes.SHAPE].json_schema()["$defs"]
    for name in result_names:
        got = _inline(components[name], lambda ref: components[ref.rsplit("/", 1)[-1]])
        assert got == _inline(defs[name], lambda ref: defs[ref.rsplit("/", 1)[-1]]), name
    elsewhere: set[str] = set()
    for (_, path), operation in operations.items():
        if not path.startswith("/greenwash/"):
            elsewhere |= _reachable(operation, components)
    assert elsewhere & (result_names | gc1) == set()


# ── §3-7 경로 호출(DB 없이) ────────────────────────────────────────────

# 몸이 생긴 셋(G1b-1 — 몸은 DB 를 읽어 업무 층 esgapi/greenwash/tests/service/ 가 잰다)
BODIED = {"greenwash_result_get", "greenwash_review_get", "greenwash_review_put"}
CALLS: dict[str, tuple[str, str, dict[str, Any] | None]] = {
    "greenwash_result_get": ("GET", "/runs/1/result", None),
    "greenwash_review_get": ("GET", "/runs/1/review", None),
    "greenwash_review_put": ("PUT", "/runs/1/review", {"marks": []}),
    "greenwash_compare_get": ("GET", "/compare?base=1&target=2", None),
}


def _send_without_session(method: str, path: str, body: dict[str, Any] | None) -> Any:
    client = TestClient(api)
    # ninja 의 TestClient 는 인자 타입이 덜 적혀 있다(data: Dict[Unknown, Unknown]).
    if method == "GET":
        return client.get(path)  # pyright: ignore[reportUnknownMemberType]
    return client.put(path, json=body)  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.parametrize("operation_id", sorted(CALLS))
def test_without_a_session_it_is_401(operation_id: str) -> None:
    """ninja.testing.TestClient 는 Django 미들웨어를 거치지 않는다: 세션 상태가 「없음」이고 DB 에 닿지 않는다."""
    method, path, body = CALLS[operation_id]
    response = _send_without_session(method, "/greenwash" + path, body)
    assert (response.status_code, response.json()) == (
        401,
        {
            "error": {
                "code": "NO_SESSION",
                "message": "세션이 없다. 먼저 /auth/exchange 로 교환한다",
                "fields": None,
                "legacyCode": "no_session",
            }
        },
    )


def _request(role: Role) -> Any:
    session = Session(
        user_id="1", tenant_id="t-1", company_id=1, role=role, expires_at=datetime(2099, 1, 1, tzinfo=UTC)
    )
    return SimpleNamespace(auth=session)


def _call(operation_id: str, role: Role) -> Any:
    request = _request(role)
    if operation_id == "greenwash_result_get":
        return routes.result_get(request, 1)
    if operation_id == "greenwash_review_get":
        return routes.review_get(request, 1)
    if operation_id == "greenwash_review_put":
        return routes.review_put(request, 1, routes.GreenwashReviewUpdate(marks=[]))
    return routes.compare_get(request, 1, 2)


@pytest.mark.parametrize("operation_id", sorted(set(CALLS) - BODIED))
def test_with_a_permitted_session_the_body_is_501(operation_id: str) -> None:
    response = _call(operation_id, "editor")
    assert response.status_code == 501
    assert json.loads(response.content) == {
        "error": {"code": "NOT_IMPLEMENTED", "message": "아직 없다", "fields": None, "legacyCode": "not_implemented"}
    }


def _nothing(**_: object) -> object:
    return routes.actions.NotFound()


def _past_permission(operation_id: str) -> bool:
    """권한을 지나 몸까지 갔는가: 501(몸 없는 경로) 또는 몸의 404(G1b-1 — actions 를 「없음」으로 바꿔 끼움)."""
    try:
        return _call(operation_id, "viewer").status_code == 501
    except ApplicationError as refused:
        return (refused.kind, refused.code) == ("not_found", "not_found")


def test_a_customer_cannot_write_when_the_cell_is_operator_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """쿠키 세션은 역할과 무관하게 고객사 사용자다(K2a 가2 — 검토 확정은 고객사 사용자 누구나, 감독 덧붙임 2).
    review_put 칸을 운영 관리자 몫으로 옮기면 403 이다(K2a 가 이 한 테스트만 다시 썼다)."""
    from esgapi.core.permissions import OPERATION_POLICY, OPERATOR

    for name in ("run_result", "review_state", "put_review"):  # 몸 셋은 DB 없이 「없음」으로
        monkeypatch.setattr(routes.actions, name, _nothing)
    for operation_id in ("greenwash_result_get", "greenwash_review_get", "greenwash_compare_get"):
        assert _past_permission(operation_id)
    assert _past_permission("greenwash_review_put")  # 분모: 표 그대로면 viewer 세션도 몸까지
    monkeypatch.setitem(OPERATION_POLICY, "greenwash_review_put", OPERATOR)
    with pytest.raises(ApplicationError) as caught:
        _call("greenwash_review_put", "viewer")
    assert (caught.value.kind, caught.value.code) == ("forbidden", "forbidden")
