"""그린워싱 계약 — 검토 review@1 의 confirmed_by, PUT 본문의 state(confirmed 만), 경로 둘(보고서 내려받기 자리 ·
기본 단어 목록), result@1 의 불변 열쇠 문구, 409 code 다섯의 설명. 순수 층(DB 없음). (GC2 `MARC-TICK-104` 에서 생김)

잰다: confirmed_by 의 꼴과 예시 셋 · 본문 state 가 confirmed·생략·null 만 받는다(openapi 는 const) · 기본 단어 목록이
엔진의 GREEN_TERMS 와 차례까지 같다 · 보고서 경로의 쿼리 하나·xlsx 200·404·409 · 둘 다 세션 없이 401 · 새 구성요소
이름 · 권한 표를 읽는다 · result@1 고정 스키마와 불변 문구 · 확정 예시의 marks 수 = 결과 items 수.
경로 호출은 `test_contracts_shapes_paths.py` 의 꼴을 따른다: 401 은 TestClient(api) 를 쿠키 없이, 200·501 은
경로 함수를 세션을 넣은 가짜 요청으로.
"""

import copy
import json
from dataclasses import replace
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
from esgapi.greenwash.contracts import review_shapes, shapes, terms_shapes
from esgapi.greenwash.engines.e0 import wordcount
from esgapi.greenwash.service.apis import greenwash as routes

DATA = Path(__file__).resolve().parents[1] / "data"
EXAMPLES = DATA / "contract-examples"
PINNED = DATA / "flow-shapes"
REVIEW_EXAMPLES = ["review-pending.json", "review-in-review.json", "review-confirmed.json"]
REPORT = ("get", "/greenwash/runs/{run_id}/report")
TERMS = ("get", "/greenwash/terms/default")
GC2_ROUTES = {REPORT: "greenwash_report_get", TERMS: "greenwash_terms_default"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FIXED_KEY = (
    "실행마다 한 번 쓰면 바뀌지 않고 items 의 차례가 고정이다 — (runId, itemIndex) 가 문장의 고정 열쇠다"
    "(검토 표시·비교·엑셀이 이것으로 잇는다)"
)


def load(*parts: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(EXAMPLES.joinpath(*parts).read_text(encoding="utf-8")))


def review(name: str) -> dict[str, Any]:
    return load("review", name)


def check_review(value: dict[str, Any]) -> None:
    review_shapes.REVIEW_SHAPES[review_shapes.SHAPE].validate_python(value, strict=True)


def pinned_text(adapter: TypeAdapter[Any]) -> str:
    return json.dumps(adapter.json_schema(), ensure_ascii=False, indent=2) + "\n"


def _document() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(json.dumps(api.get_openapi_schema(path_prefix=""))))


def _operations(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(m, p): op for p, item in document["paths"].items() for m, op in item.items()}


# ── (a) confirmed_by ───────────────────────────────────────────────────


def test_confirmed_by_comes_right_after_confirmed_at_and_takes_null() -> None:
    names = list(get_type_hints(review_shapes.GreenwashReviewState))
    assert names[names.index("confirmedAt") + 1] == "confirmedBy"
    state = review("review-in-review.json")
    assert state["confirmedBy"] is None
    check_review(state)
    missing = {k: v for k, v in state.items() if k != "confirmedBy"}
    with pytest.raises(ValidationError):
        check_review(missing)  # 칸은 늘 있다(값이 null 일 뿐)


@pytest.mark.parametrize(
    "who",
    [
        {"id": 7, "name": "검토자 가", "email": "x"},
        {"id": 7},
        {"name": "검토자 가"},
        {"id": "7", "name": "검토자 가"},
        {"id": 7, "name": ""},
    ],
)
def test_confirmed_by_is_exactly_id_and_name(who: dict[str, Any]) -> None:
    state = copy.deepcopy(review("review-confirmed.json"))
    state["confirmedBy"] = who
    with pytest.raises(ValidationError):
        check_review(state)


def test_only_the_confirmed_example_names_who_confirmed() -> None:
    by_name = {name: review(name)["confirmedBy"] for name in REVIEW_EXAMPLES}
    assert by_name["review-pending.json"] is None
    assert by_name["review-in-review.json"] is None
    who = by_name["review-confirmed.json"]
    assert isinstance(who, dict) and set(cast("dict[str, Any]", who)) == {"id", "name"}
    for name in REVIEW_EXAMPLES:
        state = review(name)
        confirmed = state["state"] == "confirmed"
        assert (state["confirmedBy"] is not None) == confirmed == (state["confirmedAt"] is not None)
        assert next(iter(state)) == "schemaVersion"
        check_review(state)


def test_the_review_schema_is_pinned_with_confirmed_by() -> None:
    adapter = review_shapes.REVIEW_SHAPES[review_shapes.SHAPE]
    pinned = PINNED / "review" / f"{review_shapes.SHAPE}.schema.json"
    assert pinned.read_bytes() == pinned_text(adapter).encode("utf-8")
    schema = adapter.json_schema()
    assert "confirmedBy" in schema["required"]
    assert set(schema["$defs"]["GreenwashReviewer"]["properties"]) == {"id", "name"}
    assert schema["$defs"]["GreenwashReviewer"]["additionalProperties"] is False


# ── (b) PUT 본문의 state ───────────────────────────────────────────────


@pytest.mark.parametrize("extra", [{"state": "confirmed"}, {}, {"state": None}])
def test_the_body_takes_confirmed_or_nothing(extra: dict[str, Any]) -> None:
    body = routes.GreenwashReviewUpdate.model_validate_json(json.dumps({"marks": [], **extra}))
    assert body.state == extra.get("state")


@pytest.mark.parametrize("value", ["pending", "in_review", "x", ""])
def test_the_body_refuses_any_other_state(value: str) -> None:
    with pytest.raises(ValidationError):
        routes.GreenwashReviewUpdate.model_validate_json(json.dumps({"state": value, "marks": []}))


def test_openapi_says_the_body_state_is_the_const_confirmed() -> None:
    state = _document()["components"]["schemas"]["GreenwashReviewUpdate"]["properties"]["state"]
    assert state["anyOf"] == [{"const": "confirmed", "type": "string"}, {"type": "null"}]


def test_the_put_declares_409() -> None:
    put = _operations(_document())[("put", "/greenwash/runs/{run_id}/review")]
    schema = put["responses"]["409"]["content"]["application/json"]["schema"]
    assert schema == {"$ref": "#/components/schemas/ErrorBody"}


# ── 경로 호출(DB 없이) ─────────────────────────────────────────────────


def _request(role: Role) -> Any:
    session = Session(
        user_id="u-1", tenant_id="t-1", company_id=1, role=role, expires_at=datetime(2099, 1, 1, tzinfo=UTC)
    )
    return SimpleNamespace(auth=session)


def _call(operation_id: str, role: Role = "viewer") -> Any:
    request = _request(role)
    if operation_id == "greenwash_report_get":
        return routes.report_get(request, 1, confirmed=False)
    return routes.terms_default(request)


# ── (c) 기본 단어 목록 ─────────────────────────────────────────────────


def test_the_default_terms_are_green_terms_in_order() -> None:
    answer = _call("greenwash_terms_default")
    assert answer == {"terms": wordcount.GREEN_TERMS}
    assert list(answer) == ["terms"]
    assert "eco프리" in answer["terms"]  # 노트북에서 붙은 낱말도 그대로
    terms_shapes.TERMS_SHAPES[terms_shapes.SHAPE].validate_python(answer, strict=True)
    assert routes.GREEN_TERMS is wordcount.GREEN_TERMS  # 상수를 import 한다(사본이 아니다)
    answer["terms"].append("x")
    assert wordcount.GREEN_TERMS[-1] != "x"  # 돌려준 목록을 고쳐도 상수는 그대로


def test_the_terms_schema_is_pinned() -> None:
    adapter = terms_shapes.TERMS_SHAPES[terms_shapes.SHAPE]
    pinned = PINNED / "terms" / f"{terms_shapes.SHAPE}.schema.json"
    assert pinned.read_bytes() == pinned_text(adapter).encode("utf-8")
    assert {p.name for p in (PINNED / "terms").iterdir()} == {pinned.name}
    assert 'normalize_term(t).replace(" ", "")' in adapter.json_schema()["description"]


def test_the_terms_200_is_the_pinned_shape() -> None:
    document = _document()
    response = _operations(document)[TERMS]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response == {"$ref": "#/components/schemas/GreenwashDefaultTerms"}
    component = document["components"]["schemas"]["GreenwashDefaultTerms"]
    assert component == terms_shapes.TERMS_SHAPES[terms_shapes.SHAPE].json_schema()


# ── (d) 보고서 내려받기 ────────────────────────────────────────────────


def test_the_report_route_is_declared() -> None:
    operation = _operations(_document())[REPORT]
    params = {p["name"]: p for p in operation["parameters"]}
    assert set(params) == {"run_id", "confirmed"}
    assert (params["run_id"]["in"], params["run_id"]["schema"]["type"]) == ("path", "integer")
    confirmed = params["confirmed"]
    assert (confirmed["in"], confirmed["required"]) == ("query", False)
    assert (confirmed["schema"]["type"], confirmed["schema"]["default"]) == ("boolean", False)
    responses: dict[str, Any] = operation["responses"]
    assert set(responses["200"]["content"]) == {XLSX}
    assert responses["200"]["content"][XLSX]["schema"] == {"type": "string", "format": "binary"}
    assert "Content-Disposition: attachment" in responses["200"]["description"]
    for code in ("404", "409"):
        schema = responses[code]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/ErrorBody"}, code
    assert {"401", "403", "444"} <= set(responses)
    assert "413" not in responses
    assert "requestBody" not in operation
    assert operation.get("security") == [{"CompanyScopedAuth": []}, {"SessionCookie": []}]


def test_the_terms_route_is_declared() -> None:
    operation = _operations(_document())[TERMS]
    assert operation["parameters"] == []
    assert {"200", "401", "403", "444"} <= set(operation["responses"])
    assert "501" not in operation["responses"]  # 몸이 있다
    assert "requestBody" not in operation
    assert operation.get("security") == [{"CompanyScopedAuth": []}, {"SessionCookie": []}]


# ── 권한 표를 읽는다 ───────────────────────────────────────────────────


@pytest.mark.parametrize("operation_id", sorted(GC2_ROUTES.values()))
def test_the_routes_read_their_own_cell(operation_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """표 그대로면 viewer 세션도 몸까지 간다(분모). 그 칸만 운영 관리자 몫으로 옮기면 403 이다."""
    from esgapi.core.permissions import COMPANY, OPERATION_POLICY, OPERATOR

    assert OPERATION_POLICY[operation_id] == COMPANY
    if operation_id == "greenwash_report_get":
        # 보고서는 몸이 DB 를 읽는다(G1b-2a) — 몸을 「실행 없음」으로 바꿔 끼우고(감사의 사용자 id 는 숫자 세션으로),
        # not_found 를 받으면 몸까지 간 것으로 본다(test_contracts_shapes_paths.py 의 _past_permission 꼴)
        def nothing(**_: object) -> object:
            return routes.actions.NotFound()

        monkeypatch.setattr(routes.report_actions, "report", nothing)
        request = _request("viewer")
        request.auth = replace(request.auth, user_id="1")
        with pytest.raises(ApplicationError) as passed:
            routes.report_get(request, 1, confirmed=False)
        assert (passed.value.kind, passed.value.code) == ("not_found", "not_found")
    else:
        _call(operation_id)
    monkeypatch.setitem(OPERATION_POLICY, operation_id, OPERATOR)
    with pytest.raises(ApplicationError) as caught:
        _call(operation_id)
    assert (caught.value.kind, caught.value.code) == ("forbidden", "forbidden")


# ── (e) 세션 없이 401 ──────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/greenwash/runs/1/report?confirmed=true", "/greenwash/terms/default"])
def test_without_a_session_it_is_401(path: str) -> None:
    """ninja.testing.TestClient 는 Django 미들웨어를 거치지 않는다: 세션 상태가 「없음」이고 DB 에 닿지 않는다."""
    response = TestClient(api).get(path)  # pyright: ignore[reportUnknownMemberType]
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


# ── (f) 구성요소 이름 ──────────────────────────────────────────────────


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


def test_the_new_component_names_have_the_prefix_and_stay_in_greenwash() -> None:
    document = _document()
    components: dict[str, Any] = document["components"]["schemas"]
    operations = _operations(document)
    assert {"GreenwashReviewer", "GreenwashDefaultTerms"} <= set(components)
    new = _reachable(operations[TERMS]["responses"]["200"], components)
    new |= _reachable(operations[("get", "/greenwash/runs/{run_id}/review")]["responses"]["200"], components)
    assert {"GreenwashReviewer", "GreenwashDefaultTerms"} <= new
    assert sorted(name for name in new if not name.startswith("Greenwash")) == []
    elsewhere: set[str] = set()
    for (_, path), operation in operations.items():
        if not path.startswith("/greenwash/"):
            elsewhere |= _reachable(operation, components)
    assert elsewhere & new == set()
    assert {key: operations[key]["operationId"] for key in GC2_ROUTES} == GC2_ROUTES


# ── (g) result@1: 칸은 그대로, 불변 열쇠 문구 ──────────────────────────


def test_the_result_schema_is_pinned_and_says_the_key_is_fixed() -> None:
    adapter = shapes.RESULT_SHAPES[shapes.SHAPE]
    assert (PINNED / f"{shapes.SHAPE}.schema.json").read_bytes() == pinned_text(adapter).encode("utf-8")
    schema = adapter.json_schema()

    def flat(text: str) -> str:
        return " ".join(text.split())  # docstring 의 줄바꿈을 접는다

    assert FIXED_KEY in flat(schema["description"])
    assert FIXED_KEY in flat(schema["$defs"]["ScanResult"]["properties"]["items"]["description"])


# ── (i) 확정이면 marks 는 결과 items 전부 ──────────────────────────────


def test_a_confirmed_review_marks_every_item_of_its_result() -> None:
    confirmed = review("review-confirmed.json")
    size = len(load("result-normal.json")["items"])
    assert confirmed["state"] == "confirmed"
    assert len(confirmed["marks"]) == size
    assert [mark["itemIndex"] for mark in confirmed["marks"]] == list(range(size))


# ── (j) GC3: PUT 본문의 표시 칸은 camelCase ────────────────────────────


def test_the_body_takes_the_camel_case_mark() -> None:
    mark = {"itemIndex": 0, "decision": "excluded", "excludeReason": "사유"}
    body = routes.GreenwashReviewUpdate.model_validate_json(json.dumps({"marks": [mark]}))
    assert body.marks == [mark]


@pytest.mark.parametrize(
    "mark",
    [
        {"item_index": 0, "decision": "adopted", "excludeReason": None},
        {"itemIndex": 0, "decision": "adopted", "exclude_reason": None},
        {"item_index": 0, "decision": "adopted", "exclude_reason": None},
    ],
)
def test_the_body_refuses_the_old_snake_case_mark(mark: dict[str, Any]) -> None:
    """옛 칸은 모르는 칸이다(StrictIn — 경로에서는 config/api.py 의 처리기가 400 invalid_input 으로 낸다)."""
    with pytest.raises(ValidationError) as caught:
        routes.GreenwashReviewUpdate.model_validate_json(json.dumps({"marks": [mark]}))
    assert {e["type"] for e in caught.value.errors()} >= {"extra_forbidden"}


# ── (k) GC4: 409 code 다섯은 E2 규칙(대문자 code, 옛 글자는 legacyCode) ─────

CONFLICT_CODES = ("review_locked", "not_confirmed", "run_not_done", "no_report", "no_review")
"""그린워싱이 계약으로 적은 409 의 옛 세부 이름(소문자). code 는 이것의 대문자다(core.exceptions.edk_code)."""


def _bare_legacy(text: str) -> list[str]:
    """옛 소문자 code 가 `legacyCode `(백틱 하나 허용) 바로 뒤가 아닌 자리에 나온 것들."""
    import re

    names = "|".join(CONFLICT_CODES)
    return re.findall(rf"(?<!legacyCode )(?<!legacyCode `)\b(?:{names})\b", text)


def _says_e2(text: str, codes: tuple[str, ...]) -> None:
    for code in codes:
        assert f"`{code.upper()}`(legacyCode `{code.lower()}`)" in text, code  # 짝을 지어 한 번은 적는다
    assert _bare_legacy(text) == []


@pytest.mark.parametrize("code", CONFLICT_CODES)
def test_the_conflict_body_is_the_e2_shape(code: str) -> None:
    from esgapi.core.exceptions import error_response

    response = error_response(409, code, "x")
    assert response.status_code == 409
    assert json.loads(response.content) == {
        "error": {"code": code.upper(), "message": "x", "fields": None, "legacyCode": code}
    }


def test_openapi_names_the_conflict_codes_in_e2_form() -> None:
    document = _document()
    operations = _operations(document)
    put = operations[("put", "/greenwash/runs/{run_id}/review")]
    assert put["operationId"] == "greenwash_review_put"
    _says_e2(put["description"], ("REVIEW_LOCKED", "RUN_NOT_DONE", "NO_REVIEW"))
    report = operations[REPORT]
    assert report["operationId"] == "greenwash_report_get"
    _says_e2(report["description"], ("NOT_CONFIRMED", "RUN_NOT_DONE", "NO_REPORT"))
    body = document["components"]["schemas"]["GreenwashReviewUpdate"]
    _says_e2(body["description"], ("REVIEW_LOCKED",))


def test_the_review_shape_header_names_the_conflict_codes_in_e2_form() -> None:
    _says_e2(review_shapes.__doc__ or "", ("REVIEW_LOCKED", "RUN_NOT_DONE", "NO_REVIEW"))


def test_the_bare_legacy_rule_itself() -> None:
    """규칙의 분모: 맨 옛 글자는 걸리고, legacyCode 뒤의 것과 대문자는 걸리지 않는다."""
    assert _bare_legacy("409 `review_locked`") == ["review_locked"]
    assert _bare_legacy("409 no_report") == ["no_report"]
    assert _bare_legacy("409 `REVIEW_LOCKED`(legacyCode `review_locked`)") == []
    assert _bare_legacy("legacyCode run_not_done") == []
    with pytest.raises(AssertionError):
        _says_e2("409 `NOT_CONFIRMED`", ("NOT_CONFIRMED",))  # 대문자만 있고 짝이 없다
    with pytest.raises(AssertionError):
        _says_e2("409 `REVIEW_LOCKED`(legacyCode `no_review`)", ("REVIEW_LOCKED",))  # 짝이 틀렸다
