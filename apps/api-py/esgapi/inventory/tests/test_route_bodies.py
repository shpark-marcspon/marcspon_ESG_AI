"""inventory 경로 셋의 응답 본문이 serializer 가 낸 dict 의 글자와 바이트까지 같은가(밴드 RR1 의 T2). 업무 층.

경로의 응답 꼴(ninja)은 본문을 그 꼴로 다시 검사해 그 꼴의 차례로 dump 한다(ninja/operation.py 의 _result_to_response).
그래서 응답 꼴이 무엇이든 본문은 serializer 의 글자 그대로여야 한다 — 이 파일이 그것을 문다:
경로가 부르는 서비스 함수를 감싸 serializer 가 낸 dict 를 붙잡고, 그 dict 를 ninja 의 렌더러(JSONRenderer =
json.dumps(값, cls=NinjaJSONEncoder))로 적은 바이트와 `response.content` 를 견준다. `json.loads` 뒤 == 가 아니다
(0 == 0.0, True == 1 이 같게 나온다).

분모: 골든 일곱(HTTP 로 닿는 것 — c-unknown-source 는 422 라 밖), 실패 갈래 열둘 가운데 HTTP 로 닿는 열,
cited 출처에 locator 가 없는 본문 하나, 추리기 세 갈래(shortlisted 둘·no_candidates), 분류 둘(모의 공급사).
HTTP 로 닿지 않는 실패 갈래 둘(calorific_basis_mismatch·invalid_reference_value)은 경로의 응답 꼴에 직접 넣어 잰다.

`RR1_BODIES_DIR` 이 있으면 요청마다 `response.content` 를 `<이름>.json` 으로 그 폴더에 쓴다(전·뒤 본문을 cmp 하려고).
"""

import copy
import json
import os
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any, cast

import pytest
from django.http import HttpResponse
from django.test import Client
from ninja.operation import ResponseObject

from esgapi.config.api import api
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.inventory.engines.scope12.engine_1 import types as s12
from esgapi.inventory.engines.scope12.engine_1.serialize import failure_to_dict
from esgapi.inventory.engines.scope12.engine_1.tables import merge_tables
from esgapi.inventory.service.actions import scope3_shortlist as actions
from esgapi.inventory.service.services import inventory as services
from esgapi.inventory.tests.scope3_llm_support import classification, mock_client
from esgapi.inventory.tests.support import TEST_DATA, package_parts, read_test_data, synthetic_tables
from esgapi.inventory.tests.test_api import HTTP_GOLDENS
from esgapi.inventory.tests.test_scope3_api import seed
from tests.support.http import login

pytestmark = pytest.mark.django_db

CALC = "/api/inventory/calc"
SHORTLIST = "/api/inventory/scope3/shortlist"
CLASSIFY = "/api/inventory/scope3/classify"

# 실패 갈래 열둘(contracts/shapes.py 의 FailureJson) 가운데 HTTP 로 닿는 열.
HTTP_FAILURES = [
    "invalid_activity",
    "factor_not_found",
    "factor_ambiguous",
    "factor_kind_mismatch",
    "factor_incomplete",
    "unit_conversion_not_found",
    "unit_conversion_ambiguous",
    "gwp_set_not_found",
    "gwp_set_ambiguous",
    "gwp_value_missing",
]
# 닿지 않는 둘. calorific_basis_mismatch: 요청에 발열량 기준 칸이 없다(service/services/inventory.py 의 calc_rows).
# invalid_reference_value: 표의 값은 validate_tables 가 먼저 400 invalid_tables 로 막는다.
DIRECT_FAILURES: list[s12.Failure] = [
    s12.CalorificBasisMismatch(factor_id="synthetic:fuel-a:mobile", required="net", actual="gross"),
    s12.InvalidReferenceValue(where="factors[0].calorific.value", value="x"),
]


class Bodies:
    """서비스가 낸 dict 를 붙잡고, 본문을 견주고, 폴더가 주어지면 본문을 쓴다."""

    def __init__(self) -> None:
        self.captured: list[Mapping[str, object]] = []
        folder = os.environ.get("RR1_BODIES_DIR")
        self.folder = Path(folder) if folder else None

    def wrap[**P, R](
        self, function: Callable[P, R], output: Callable[[R], Mapping[str, object] | None]
    ) -> Callable[P, R]:
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            result = function(*args, **kwargs)
            out = output(result)
            if out is not None:
                self.captured.append(out)
            return result

        return wrapped

    def check(self, name: str, response: Any) -> dict[str, Any]:
        """본문 바이트 == 붙잡은 dict 를 렌더러로 적은 바이트. 붙잡은 것은 이 요청의 것 하나뿐이어야 한다."""
        assert response.status_code == 200, (name, response.content.decode())
        (out,) = self.captured
        self.captured.clear()
        expected = api.renderer.render(response.wsgi_request, out, response_status=200).encode()
        assert response.content == expected, name
        if self.folder is not None:
            self.folder.mkdir(parents=True, exist_ok=True)
            (self.folder / f"{name}.json").write_bytes(response.content)
        body: dict[str, Any] = json.loads(response.content)
        return body


@pytest.fixture
def bodies(monkeypatch: pytest.MonkeyPatch) -> Bodies:
    """경로가 부르는 서비스 함수 셋(모듈 속성 자리)을 감싼다. 결과는 바꾸지 않는다."""
    found = Bodies()
    monkeypatch.setattr(
        services,
        "calc_rows",
        found.wrap(services.calc_rows, lambda r: r.output if isinstance(r, services.CalcDone) else None),
    )
    monkeypatch.setattr(actions, "scope3_shortlist_output", found.wrap(actions.scope3_shortlist_output, lambda r: r))
    monkeypatch.setattr(
        services,
        "scope3_classify_output",
        found.wrap(
            services.scope3_classify_output, lambda r: r.output if isinstance(r, services.Scope3ClassifyDone) else None
        ),
    )
    return found


def post(client: Client, path: str, body: Any) -> Any:
    return client.post(path, data=json.dumps(body), content_type="application/json")


def walk(value: object) -> Iterator[Mapping[str, object]]:
    """본문 안의 객체 전부."""
    if isinstance(value, Mapping):
        found = cast("Mapping[str, object]", value)
        yield found
        for entry in found.values():
            yield from walk(entry)
    elif isinstance(value, list):
        for entry in cast("list[object]", value):
            yield from walk(entry)


# ── 계산(Scope 1·2) ───────────────────────────────────────────────────


def failure_request(kind: str | None) -> dict[str, Any]:
    """그 실패 갈래 하나가 나오는 요청(None 이면 실패 없는 요청). 가상 표를 본문에 싣는다.

    행은 예제의 r1(이동연소, 가상 연료 A, L).
    """
    tables = copy.deepcopy(synthetic_tables())
    row: dict[str, Any] = dict(read_test_data("examples/activity.synthetic.json")["activities"][0])
    gwp = "synthetic-gwp"
    synthetic = {"kind": "synthetic", "note": "가상"}
    match kind:
        case "invalid_activity":
            row["amount"] = "-1"
        case "factor_not_found":
            row["fuel"] = "no-such-fuel"
        case "factor_ambiguous":
            tables["factors"].append({**copy.deepcopy(tables["factors"][0]), "id": "synthetic:dup"})
        case "factor_kind_mismatch":
            row["factorId"] = "synthetic:electricity"
        case "factor_incomplete":
            first = tables["factors"][0]
            first["emissionFactors"] = [e for e in first["emissionFactors"] if e["gas"] != "CH4"]
        case "unit_conversion_not_found":
            row["unit"] = "kg"
        case "unit_conversion_ambiguous":
            tables["unitConversions"].append({"from": "MJ", "to": "TJ", "factor": "0.001", "source": synthetic})
        case "gwp_set_not_found":
            gwp = "no-such-set"
        case "gwp_set_ambiguous":
            tables["gwpSets"].append(copy.deepcopy(tables["gwpSets"][0]))
        case "gwp_value_missing":
            gwp = "partial-gwp"
            tables["gwpSets"].append(
                {"id": gwp, "label": "가상", "source": synthetic, "values": {"CO2": "1", "CH4": "20"}}
            )
        case _:
            pass  # 실패 없는 행
    return {"rows": [row], "tables": tables, "gwpSetId": gwp}


WITH_LOCATOR = {"b-handcalc.kr-ets-decree-annex2.json", "b2-package-default.json"}


@pytest.mark.parametrize(("golden", "activity", "which", "by"), HTTP_GOLDENS, ids=[g[0] for g in HTTP_GOLDENS])
def test_golden_bodies_are_the_serializer_bytes(
    client: Client, tenants: None, bodies: Bodies, golden: str, activity: str, which: str | None, by: list[str] | None
) -> None:
    login(client)
    activity_file: dict[str, Any] = json.loads((TEST_DATA / activity).read_text(encoding="utf-8"))
    body: dict[str, Any] = {"rows": activity_file["activities"], "gwpSetId": activity_file["gwpSetId"]}
    if which == "synthetic":
        body["tables"] = merge_tables(synthetic_tables())
    elif which == "all":
        body["tables"] = merge_tables(*package_parts(), synthetic_tables())
    if by is not None:
        body["groupBy"] = by
    found = bodies.check(f"calc-golden-{golden.removesuffix('.json')}", post(client, CALC, body))
    if golden in WITH_LOCATOR:
        # 「없으면 키를 뺀다」 칸 locator 가 든 쪽(빠진 쪽은 test_a_cited_source_without_a_locator)
        assert any("locator" in entry for entry in walk(found) if entry.get("kind") == "cited")


def test_the_golden_bodies_have_and_lack_conversion(client: Client, tenants: None, bodies: Bodies) -> None:
    """「없으면 키를 뺀다」 칸 conversion: 골든 (가)의 열(purchased_heat) 행에 든 단계와 빠진 단계가 둘 다 있다."""
    login(client)
    example = read_test_data("examples/activity.synthetic.json")
    body = {"rows": example["activities"], "tables": synthetic_tables(), "gwpSetId": example["gwpSetId"]}
    found = bodies.check("calc-conversion", post(client, CALC, body))
    steps = [entry for entry in walk(found) if "formula" in entry]
    assert {"conversion" in step for step in steps} == {True, False}


@pytest.mark.parametrize("kind", HTTP_FAILURES)
def test_every_reachable_failure_body_is_the_serializer_bytes(
    client: Client, tenants: None, bodies: Bodies, kind: str
) -> None:
    login(client)
    found = bodies.check(f"calc-failure-{kind}", post(client, CALC, failure_request(kind)))
    assert [row["failure"]["kind"] for row in found["rows"]] == [kind]


def test_a_cited_source_without_a_locator(client: Client, tenants: None, bodies: Bodies) -> None:
    """「없으면 키를 뺀다」 칸 locator: 골든의 cited 출처는 모두 locator 가 있다. 없는 것(note 만 있는 것)을 싣는다."""
    login(client)
    request = failure_request(None)
    cited = {"kind": "cited", "title": "가상 문서", "url": "https://example.org/synthetic", "checkedOn": "2026-10-16"}
    request["tables"]["factors"][0]["source"] = {**cited, "note": "가상"}
    found = bodies.check("calc-cited-without-locator", post(client, CALC, request))
    sources = [entry for entry in walk(found) if entry.get("kind") == "cited"]
    assert sources
    assert all("locator" not in source and "note" in source for source in sources)


def test_the_failures_not_reachable_over_http_render_as_the_serializer_bytes(
    client: Client, tenants: None, bodies: Bodies
) -> None:
    """HTTP 아님: 경로의 응답 꼴에 serializer 출력을 직접 넣는다(경로가 하는 일 — 검사, dump, 렌더러).

    본문의 실패 갈래 하나를 HTTP 로 닿지 않는 갈래의 serializer 출력으로 갈아 끼운 dict 를 쓴다.
    """
    login(client)
    response = post(client, CALC, failure_request("invalid_activity"))
    (base,) = bodies.captured
    bodies.captured.clear()
    (operation,) = [
        op
        # 걸린 경로의 operation(라우터는 걸릴 때 복제된다). config/tests/test_request_schemas_reject_bool.py 와 같은 길
        for _, router in api._routers  # pyright: ignore[reportPrivateUsage]
        for view in router.path_operations.values()
        for op in view.operations
        if op.operation_id == "inventory_calc"
    ]
    model = operation.response_models[200]
    assert model is not None
    for failure in DIRECT_FAILURES:
        out = cast("dict[str, Any]", copy.deepcopy(base))
        out["rows"][0]["failure"] = failure_to_dict(failure)
        # ninja 도 dict 를 그대로 싼다(operation.py 의 _result_to_response). 주석의 타입만 HttpResponse 다.
        dumped = model.model_validate(ResponseObject(cast("HttpResponse", out))).model_dump(
            by_alias=True, exclude_unset=True
        )["response"]
        rendered = api.renderer.render(response.wsgi_request, dumped, response_status=200)
        assert rendered == api.renderer.render(response.wsgi_request, out, response_status=200), failure.kind


# ── Scope 3: 추리기와 분류 ────────────────────────────────────────────


@pytest.fixture
def table(tenants: None, tmp_path: Path) -> None:
    seed(tmp_path / "factors.jsonl")


SHORTLISTS: list[tuple[str, dict[str, Any]]] = [
    ("shortlisted-physical", {"row": {"itemName": "합성 강판", "unit": "kg"}, "category": 1}),
    ("shortlisted-spend", {"row": {"itemName": "노트북 구매", "unit": "대"}, "category": 1}),
    ("no-candidates", {"row": {"itemName": "출장 렌터카", "unit": "대"}, "category": 6}),
]


def test_shortlist_bodies_are_the_serializer_bytes(client: Client, table: None, bodies: Bodies) -> None:
    login(client)
    found = {name: bodies.check(f"shortlist-{name}", post(client, SHORTLIST, body)) for name, body in SHORTLISTS}
    assert [b["status"] for b in found.values()] == ["shortlisted", "shortlisted", "no_candidates"]
    # 「없으면 키를 뺀다」 칸 둘: lexical(근거)·path(후보)가 든 것과 빠진 것이 둘 다 있다.
    evidence = [entry for b in found.values() for entry in b.get("evidence", [])]
    assert {"lexical" in entry for entry in evidence} == {True, False}
    candidates = [entry for b in found.values() for entry in b.get("candidates", [])]
    assert {"path" in entry for entry in candidates} == {True, False}


@pytest.fixture
def mock(monkeypatch: pytest.MonkeyPatch) -> MockProvider:
    provider = MockProvider()
    client = mock_client(provider)
    monkeypatch.setattr(services, "scope3_gateway", lambda: client)
    return provider


def item(row_id: str, name: str) -> dict[str, Any]:
    return {"rowId": row_id, "itemName": name, "unit": "kg"}


def test_classify_bodies_are_the_serializer_bytes(
    client: Client, tenants: None, bodies: Bodies, mock: MockProvider
) -> None:
    login(client)
    mock.enqueue_text(classification(1, ["steel"])).enqueue_text(classification("other"))
    classified = bodies.check(
        "classify-classified", post(client, CLASSIFY, {"rows": [item("a", "합성 강판"), item("b", "폐기물 처리")]})
    )
    for _ in range(3):
        mock.enqueue_text(classification(5))  # 스키마 밖의 범주: 세 번 다 틀려 실패한 묶음
    failed = bodies.check("classify-failed", post(client, CLASSIFY, {"rows": [item("a", "합성 강판")]}))
    assert [g["status"] for g in classified["groups"] + failed["groups"]] == [
        "classified",
        "classified",
        "classification_failed",
    ]
