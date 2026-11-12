"""2차 엔진 결과 읽기 GET /greenwash/runs/{run_id}/result2(밴드 GE1b ④ — service/actions/engine_g1.run_result2 ·
service/apis/greenwash.result2_get).

    T20  끝난 G1 실행 200 = 저장 본문(result@2 꼴로 다시 직렬화 — 첫 열쇠 schemaVersion, jsonb 차례를 내보내지 않음) ·
         끝나지 않음 409 RUN_NOT_DONE · 1차(E0) 실행·다른 모듈·남의 회사·없는 id·result@2 행 없는 G1 실행 404 · 읽기만
    T21  openapi 의 200 꼴 = result@2 TypeAdapter 의 JSON 스키마(인라인 견줌) · 구성요소 이름 GreenwashResult2 접두
★ 실행·결과 행은 seed(apps.get_model)로 심는다(runs.models import 0). 결과 본문은 계약 예시 result2/*. 지어낸 값이다.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from django.test import Client

from esgapi.greenwash.contracts import result2_shapes as r2
from esgapi.greenwash.flows import engine_g1 as E
from esgapi.greenwash.service.actions import engine_g1 as g1_actions
from esgapi.greenwash.tests.service import seed
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import login

OPENAPI = Path(__file__).resolve().parents[5] / "generated" / "openapi.json"
URL = "/api/greenwash/runs/{}/result2"
NORMAL2 = seed.example("result2/result2-normal")


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def run_count(company: int) -> int:
    return run_selectors.run_page(
        company_id=company, module=None, status=None, document_id=None, limit=100, offset=0
    ).count


# ── T20 ──


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["result2-normal", "result2-failed", "result2-empty"])
def test_a_done_g1_run_returns_its_stored_result_in_the_shape_order(
    client: Client, companies: tuple[int, int], name: str
) -> None:
    a, _b = companies
    login(client)
    body = seed.example(f"result2/{name}")
    run_id = seed.run(a, result=body, flow_id=E.FLOW_ID)
    stored = run_selectors.run_results(company_id=a, run_id=run_id)[0].body
    assert next(iter(cast("dict[str, Any]", stored))) != "schemaVersion"  # 분모: jsonb 가 열쇠 차례를 바꿨다
    got = client.get(URL.format(run_id))
    assert got.status_code == 200, got.content.decode()
    assert next(iter(got.json())) == "schemaVersion"
    assert got.json() == body
    r2.check_result(got.json())  # 흐름 출력 규칙(첫 열쇠 포함) 그대로
    # 몸(actions)이 이미 꼴 차례로 돌려준다 — 응답 꼴(ninja)에 기대지 않는다(감독 53)
    direct = g1_actions.run_result2(company_id=a, run_id=run_id)
    assert isinstance(direct, dict)
    assert list(direct) == list(body)


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_an_unfinished_g1_run_is_409(client: Client, companies: tuple[int, int], status: str) -> None:
    a, _b = companies
    login(client)
    run_id = seed.run(a, status=status, flow_id=E.FLOW_ID)
    assert code(client.get(URL.format(run_id))) == (409, "RUN_NOT_DONE")


@pytest.mark.django_db
def test_first_engine_foreign_missing_and_bodiless_runs_are_404(client: Client, companies: tuple[int, int]) -> None:
    a, b = companies
    login(client)
    e0 = seed.run(a, result=seed.example("result-normal"))
    e0_with_r2 = seed.run(a, result=NORMAL2)  # 흐름 E0 인데 result@2 행 — 흐름 거름만 막는다
    other_module = seed.run(a, module="probe", result=NORMAL2)
    # 흐름 G1 인데 다른 모듈 — module 거름만 막는다
    other_module_g1 = seed.run(a, module="probe", result=NORMAL2, flow_id=E.FLOW_ID)
    theirs = seed.run(b, result=NORMAL2, flow_id=E.FLOW_ID)
    bodiless = seed.run(a, flow_id=E.FLOW_ID)
    mine = seed.run(a, result=NORMAL2, flow_id=E.FLOW_ID)
    before = run_count(a)
    for run_id in (e0, e0_with_r2, other_module, other_module_g1, theirs, bodiless, mine + 1000):
        got = client.get(URL.format(run_id))
        assert code(got) == (404, "NOT_FOUND")
        assert b"greenwash.result@2" not in got.content
    # 남의 회사 = 없는 id(있음 누설 0)
    assert client.get(URL.format(theirs)).content == client.get(URL.format(mine + 1000)).content
    assert run_count(a) == before
    assert client.get(URL.format(mine)).status_code == 200  # 분모: 제 G1 실행은 된다


# ── T21 ──


def inline(schema: Any, resolve: Callable[[str], Any]) -> Any:
    """$ref 를 펼친 꼴(이름·설명·$defs 칸 제외, 판별 짝은 이름만 — 꼴만 견준다)."""
    if isinstance(schema, dict):
        given = cast("dict[str, Any]", schema)
        if "$ref" in given:
            return inline(resolve(str(given["$ref"])), resolve)
        if "mapping" in given and "propertyName" in given:  # 판별 짝의 $ref 글자는 자리(#/$defs·#/components)만 다르다
            return {**given, "mapping": {k: str(v).rsplit("/", 1)[-1] for k, v in given["mapping"].items()}}
        return {k: inline(v, resolve) for k, v in given.items() if k not in ("title", "description", "$defs")}
    if isinstance(schema, list):
        return [inline(v, resolve) for v in cast("list[Any]", schema)]
    return schema


def test_the_openapi_200_shape_is_the_result2_type_adapter() -> None:
    document = json.loads(OPENAPI.read_text(encoding="utf-8"))
    components: dict[str, Any] = document["components"]["schemas"]
    operation = document["paths"]["/greenwash/runs/{run_id}/result2"]["get"]
    assert operation["operationId"] == "greenwash_result2_get"
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response == {"$ref": "#/components/schemas/GreenwashResult2"}
    pinned = r2.RESULT2.json_schema()
    defs: dict[str, Any] = pinned.get("$defs", {})
    got = inline(response, lambda ref: components[ref.rsplit("/", 1)[-1]])
    want = inline(pinned, lambda ref: defs[ref.rsplit("/", 1)[-1]])
    assert got == want
    assert all(name.startswith("GreenwashResult2") for name in defs)
    assert {"409", "404"} <= set(operation["responses"])
