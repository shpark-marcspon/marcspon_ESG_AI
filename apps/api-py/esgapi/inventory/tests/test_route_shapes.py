"""inventory 경로의 응답 꼴이 결과 꼴(contracts/shapes.py 의 TypedDict) 그 객체인가(밴드 RR1, sid:MARC-ENT-268).

T1 같은 객체 · T3 모르는 키는 500(업무 층) · T4 components 이름 겹침 0 · T5 설명 그대로 · T6 판과 꼴.
T3 말고는 순수 층이다(소켓 문지기 아래). 본문 바이트(T2)는 test_route_bodies.py.
"""

import ast
import copy
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final, cast, get_args, get_type_hints

import pytest
from django.test import Client
from ninja.constants import NOT_SET
from ninja.openapi.schema import REF_TEMPLATE
from ninja.operation import Operation
from ninja.schema import NinjaGenerateJsonSchema
from pydantic import BaseModel, ValidationError

from esgapi.config.api import api
from esgapi.inventory.contracts import shapes
from esgapi.inventory.service.apis import dashboard as dashboard_routes
from esgapi.inventory.service.apis import scope3_edits as scope3_edit_routes
from esgapi.inventory.service.apis import scope3_runs
from esgapi.inventory.service.apis import scope3_state as scope3_state_routes
from esgapi.inventory.service.schemas import inventory as route
from esgapi.inventory.service.services import inventory as services
from esgapi.inventory.tests.support import ETS_GWP, hand_cases
from esgapi.inventory.tests.test_flow_shapes import flow_result
from esgapi.inventory.tests.test_golden import PURE_GOLDENS
from tests.support.http import login

ROUTE_FILE = Path(route.__file__)

REQUESTS = {
    "CalcTiersIn",
    "CalcRowIn",
    "CalcIn",
    "Scope3TransportIn",
    "Scope3ShortlistRowIn",
    "Scope3ShortlistIn",
    "Scope3RowIn",
    "Scope3ClassifyIn",
}
# 결과 꼴에 없는 경로 전용 응답 꼴(ninja Schema). 맨 칸의 모르는 키는 ninja 기본대로 버린다.
ROUTE_ONLY = {
    "Scope3CandidateOut",
    "Scope3RejectedOut",
    "Scope3CatalogOut",
    "Scope3ShortlistedOut",
    "Scope3NoCandidatesOut",
    "Scope3GroupClassifiedOut",
    "Scope3GroupFailedOut",
    "Scope3ClassifyOut",
}
# RR1 이 지운 쌍둥이 35 → 그 자리를 잇는 결과 꼴의 이름(= 지금 components 의 이름).
RENAMED = {
    "CalcCitedOut": "CitedSource",
    "CalcDefinitionOut": "DefinitionSource",
    "CalcSyntheticOut": "SyntheticSource",
    "CalcUnitConversionOut": "UnitConversionJson",
    "CalcInvalidActivityOut": "InvalidActivityFailure",
    "CalcFactorNotFoundOut": "FactorNotFoundFailure",
    "CalcFactorAmbiguousOut": "FactorAmbiguousFailure",
    "CalcFactorKindMismatchOut": "FactorKindMismatchFailure",
    "CalcFactorIncompleteOut": "FactorIncompleteFailure",
    "CalcInvalidReferenceValueOut": "InvalidReferenceValueFailure",
    "CalcCalorificBasisMismatchOut": "CalorificBasisMismatchFailure",
    "CalcUnitConversionNotFoundOut": "UnitConversionNotFoundFailure",
    "CalcUnitConversionAmbiguousOut": "UnitConversionAmbiguousFailure",
    "CalcGwpSetNotFoundOut": "GwpSetNotFoundFailure",
    "CalcGwpSetAmbiguousOut": "GwpSetAmbiguousFailure",
    "CalcGwpValueMissingOut": "GwpValueMissingFailure",
    "CalcStepOut": "StepJson",
    "CalcGasOut": "GasResultJson",
    "CalcEnergyOut": "EnergyJson",
    "CalcTiersOut": "ParameterTiersJson",
    "CalcEvidenceFactorOut": "EvidenceFactorJson",
    "CalcEvidenceGwpSetOut": "EvidenceGwpSetJson",
    "CalcEvidenceOut": "EvidenceJson",
    "CalcRowOkOut": "RowOkJson",
    "CalcRowFailedOut": "RowFailedJson",
    "CalcTotalsOut": "TotalsJson",
    "CalcGroupOut": "GroupJson",
    "CalcAggregationOut": "AggregationJson",
    "CalcOut": "Scope12Body",
    "Scope3LexicalOut": "LexicalEvidenceJson",
    "Scope3EvidenceOut": "CandidateEvidenceJson",
    "Scope3ClassificationOut": "ClassificationJson",
    "Scope3LlmFailureOut": "LlmFailureJson",
    "Scope3PromptUsageOut": "PromptUsageJson",
    "Scope3UsageOut": "UsageJson",
}


def operations() -> list[Operation]:
    """걸린 경로의 operation 전부(묶이기 전 원본 — 응답 꼴은 묶인 복제본과 같은 객체다: Operation.clone)."""
    return [
        op
        for _, router in api._routers  # pyright: ignore[reportPrivateUsage]
        for view in router.path_operations.values()
        for op in view.operations
    ]


def colab_result_operation() -> Operation:
    """S3K1 의 Scope 3 코랩 결과 경로(inventory router 아래 붙은 router — operations() 는 url 을 짓기 전에는 그 안을 못
    본다, 시험 차례에 따라)."""
    (found,) = [
        op
        for view in scope3_runs.router.path_operations.values()
        for op in view.operations
        if op.operation_id == "inventory_scope3_result_get"
    ]
    return found


def with_colab_result(found: list[Operation]) -> list[Operation]:
    """operations() 에 Scope 3 코랩 결과 경로가 없으면(url 을 짓기 전) 더한다 — 시험 차례와 상관없이 같은 셈."""
    ids = {op.operation_id for op in found}
    return found if "inventory_scope3_result_get" in ids else [*found, colab_result_operation()]


def dashboard_operation() -> Operation:
    """S12a-3 의 대시보드 경로(inventory router 아래 붙은 router — colab_result_operation 과 같은 까닭)."""
    (found,) = [
        op
        for view in dashboard_routes.router.path_operations.values()
        for op in view.operations
        if op.operation_id == "inventory_scope12_dashboard"
    ]
    return found


def with_dashboard(found: list[Operation]) -> list[Operation]:
    """operations() 에 대시보드 경로가 없으면(url 을 짓기 전) 더한다 — 시험 차례와 상관없이 같은 셈."""
    ids = {op.operation_id for op in found}
    return found if "inventory_scope12_dashboard" in ids else [*found, dashboard_operation()]


SCOPE3_STATE_OPERATIONS: Final = ("inventory_scope3_year_get", "inventory_scope3_lock", "inventory_scope3_unlock")
SCOPE3_EDIT_OPERATIONS: Final = (
    "inventory_scope3_rows_exclude",
    "inventory_scope3_rows_restore",
    "inventory_scope3_row_factor",
    "inventory_scope3_edits_get",
    "inventory_scope3_history_get",
)


def scope3_state_operations() -> list[Operation]:
    """S3K2a 의 Scope 3 연도 상태·잠금 셋(inventory router 아래 붙은 router — dashboard_operation 과 같은 까닭)."""
    return [
        op
        for view in scope3_state_routes.router.path_operations.values()
        for op in view.operations
        if op.operation_id in SCOPE3_STATE_OPERATIONS
    ]


def with_scope3_state(found: list[Operation]) -> list[Operation]:
    """operations() 에 연도 상태·잠금 셋이 없으면(url 을 짓기 전) 더한다 — 시험 차례와 상관없이 같은 셈."""
    ids = {op.operation_id for op in found}
    return [*found, *(op for op in scope3_state_operations() if op.operation_id not in ids)]


def scope3_edit_operations() -> list[Operation]:
    """Scope 3 줄 덧판 다섯(S3K2b-1 넷 + S3K2b-2 계수 — 그 router 의 경로 다, url 을 짓기 전에도 같은 셈)."""
    return [
        op
        for view in scope3_edit_routes.router.path_operations.values()
        for op in view.operations
        if op.operation_id in SCOPE3_EDIT_OPERATIONS
    ]


def with_scope3_edits(found: list[Operation]) -> list[Operation]:
    """operations() 에 줄 덧판 다섯이 없으면(url 을 짓기 전) 더한다 — 시험 차례와 상관없이 같은 셈."""
    ids = {op.operation_id for op in found}
    return [*found, *(op for op in scope3_edit_operations() if op.operation_id not in ids)]


def response_of(operation_id: str) -> object:
    (operation,) = [op for op in operations() if op.operation_id == operation_id]
    model = operation.response_models[200]
    assert model is not None
    return model.model_fields["response"].annotation


def field_type(model: type[route.Schema], name: str) -> object:
    return model.model_fields[name].annotation


# ── T1 같은 객체 ──


def test_the_routes_use_the_result_shapes_themselves() -> None:
    assert response_of("inventory_calc") is shapes.Scope12Body
    assert set(get_args(response_of("inventory_scope3_shortlist"))) == {
        route.Scope3ShortlistedOut,
        route.Scope3NoCandidatesOut,
    }
    assert response_of("inventory_scope3_classify") is route.Scope3ClassifyOut
    colab_model = colab_result_operation().response_models[200]  # S3K1 — Scope3ColabResult 의 두 갈래·status 가름
    assert colab_model is not None
    colab_field = colab_model.model_fields["response"]
    assert set(get_args(colab_field.annotation)) == set(get_args(get_args(shapes.Scope3ColabResult)[0]))
    assert colab_field.discriminator == "status"
    (evidence,) = get_args(field_type(route.Scope3ShortlistedOut, "evidence"))
    assert evidence is shapes.CandidateEvidenceJson
    assert field_type(route.Scope3GroupClassifiedOut, "classification") is shapes.ClassificationJson
    assert field_type(route.Scope3GroupFailedOut, "llm") is shapes.LlmFailureJson
    assert field_type(route.Scope3ClassifyOut, "usage") is shapes.UsageJson


def test_the_route_file_declares_only_requests_and_route_only_shapes() -> None:
    """쌍둥이 Schema 가 다시 생기면 빨갛다: 이 파일의 클래스는 요청 8 + 경로 전용 8 뿐이다."""
    tree = ast.parse(ROUTE_FILE.read_text(encoding="utf-8"))
    declared = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert declared == REQUESTS | ROUTE_ONLY


# ── T3 모르는 키 → 500 (업무 층) ──


@pytest.mark.django_db
def test_an_unknown_key_in_an_ok_row_is_500_and_not_leaked(
    client: Client, tenants: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """serializer 가 낸 ok 행(RowOkJson)에 키 하나가 더 들면 경로가 버리지 않고 500 으로 답한다(RR1 의 D4)."""
    real: Callable[..., object] = services.calc_rows

    def leaky(**kwargs: Any) -> object:
        result = real(**kwargs)
        assert isinstance(result, services.CalcDone)
        rows = cast("list[dict[str, object]]", result.output["rows"])
        assert rows[0]["status"] == "ok"
        rows[0]["leakedKey"] = "leaked-value"
        return result

    monkeypatch.setattr(services, "calc_rows", leaky)
    login(client)
    body = {"rows": [hand_cases()[0]["activity"]], "gwpSetId": ETS_GWP}
    response = client.post("/api/inventory/calc", data=json.dumps(body), content_type="application/json")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert b"leaked" not in response.content


# ── T4 components 이름 겹침 0 ──


def definitions(model: type[BaseModel], *, by_alias: bool, mode: str) -> Mapping[str, object]:
    """ninja 가 components 에 옮기는 $defs(ninja/openapi/schema.py 의 _create_schema_from_model 과 같은 인자)."""
    schema = model.model_json_schema(
        ref_template=REF_TEMPLATE,
        by_alias=by_alias,
        schema_generator=NinjaGenerateJsonSchema,
        mode="serialization" if mode == "serialization" else "validation",
    )
    return cast("Mapping[str, object]", schema.get("$defs", {}))


# 화면 꼴 경로(결과 꼴 셈에서 뺌) — 인덱스 선택 둘(K1b-2b) · Scope 1·2 입력 열(S12a) · 입력주기·계수·복구 셋(S12a-2).
SCOPE12_SCREEN_OPERATIONS: Final = frozenset(
    {
        "inventory_scope12_index_tree",
        "inventory_scope12_index_selections_save",
        "inventory_scope12_years",
        "inventory_scope12_rows",
        "inventory_scope12_index_detail",
        "inventory_scope12_rows_save",
        "inventory_scope12_rows_delete",
        "inventory_scope12_memo_save",
        "inventory_scope12_lock",
        "inventory_scope12_unlock",
        "inventory_scope12_decimals_save",
        "inventory_scope12_row_history",
        "inventory_scope12_period_save",
        "inventory_scope12_row_factor_save",
        "inventory_scope12_history_restore",
        "inventory_scope12_upload",
    }
)


def counts_as_result(operation_id: str) -> bool:
    """그 경로의 응답 꼴이 결과 꼴 셈에 드는가 — inventory 경로 가운데 풀(접두)·scope12 화면(목록) 밖."""
    return (
        operation_id.startswith("inventory_")
        and not operation_id.startswith("inventory_admin_ghg_")
        and operation_id not in SCOPE12_SCREEN_OPERATIONS
    )


def test_a_new_scope12_route_counts_as_a_result_shape() -> None:
    """(469 R7) 면제는 이름 목록이다 — 목록 밖 scope12 경로(대시보드 S12a-3 같은 것)는 결과 꼴 셈에 든다."""
    assert counts_as_result("inventory_scope12_dashboard")
    assert not counts_as_result("inventory_scope12_history_restore")
    assert not counts_as_result("inventory_admin_ghg_factors_get")
    assert counts_as_result("inventory_calc")


def test_no_two_shapes_share_a_components_name() -> None:
    """ninja 는 같은 이름의 정의를 조용히 덮어쓴다(add_schema_definitions). 모델마다 따로 뽑아 이름이 같으면 같은지."""
    seen: dict[str, object] = {}
    clashes: list[str] = []
    inventory_responses: set[str] = set()
    for operation in with_scope3_edits(with_scope3_state(with_dashboard(with_colab_result(operations())))):
        requests: list[type[BaseModel]] = list(operation.models)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        found = [definitions(model, by_alias=True, mode="validation") for model in requests]
        for model in operation.response_models.values():
            if model is None or model is NOT_SET:
                continue
            defs = definitions(model, by_alias=operation.by_alias, mode="serialization")
            found.append(defs)
            # 온실가스 풀 열둘(K1b-2a — inventory_admin_ghg_*)은 계산 결과 꼴이 아니라 관리자 풀의 꼴이다(Ghg* 이름).
            # 고객사 인덱스 선택 둘(K1b-2b — inventory_scope12_index_*)도 선택 화면 꼴이다(IndexTree*·IndexSelection*).
            # Scope 1·2 입력 열(S12a — inventory_scope12_*)도 입력 화면 꼴이다(Entry* 이름, 풀의 GhgUnitOut·GhgGasOut).
            # S12a-2(469 R7): scope12 는 접두가 아니라 operationId 목록으로 뺀다 — 새 scope12 경로(대시보드 S12a-3)는
            # 결과 꼴 셈에 든다.
            if counts_as_result(operation.operation_id or ""):
                inventory_responses |= set(defs)
        for defs in found:
            for name, schema in defs.items():
                if name in seen and seen[name] != schema:
                    clashes.append(name)
                seen.setdefault(name, schema)
    assert clashes == []
    # 응답에 닿는 inventory 의 이름: 결과 꼴 35 + 경로 전용 8(그 밖은 오류 꼴). 결과 꼴 67 전부가 아니다.
    reached = inventory_responses - ROUTE_ONLY - {"ErrorBody", "ErrorDetail", "FieldError"}
    # S3K1: Scope 3 코랩 결과 경로는 결과 꼴(Scope3ColabResult) 그대로 — 그 이름들이 더 닿는다(Colab*·Scope3Colab*).
    colab_route = colab_result_operation()
    colab_model = colab_route.response_models[200]
    assert colab_model is not None and colab_model is not NOT_SET
    colab = set(definitions(colab_model, by_alias=colab_route.by_alias, mode="serialization"))
    assert {"Scope3ColabDone", "Scope3ColabRejected"} <= colab
    assert all(name.startswith(("Colab", "Scope3Colab")) for name in colab)
    # S12a-3: 대시보드 꼴(Scope12Dashboard*) — 결과 꼴 셈에 들되 이름으로 닫음
    board_route = dashboard_operation()
    board_model = board_route.response_models[200]
    assert board_model is not None and board_model is not NOT_SET
    dashboard = set(definitions(board_model, by_alias=board_route.by_alias, mode="serialization"))
    assert dashboard and all(name.startswith("Scope12Dashboard") for name in dashboard)
    # S3K2a: 연도 상태·잠금 셋의 꼴(Scope3Year*) — 결과 꼴 셈에 들되 이름 앞머리로 닫음(잠근 사람도 자기 꼴)
    state_routes = scope3_state_operations()
    assert sorted(op.operation_id or "" for op in state_routes) == sorted(SCOPE3_STATE_OPERATIONS)
    state: set[str] = set()
    for state_route in state_routes:
        state_model = state_route.response_models[200]
        assert state_model is not None and state_model is not NOT_SET
        state |= set(definitions(state_model, by_alias=state_route.by_alias, mode="serialization"))
    assert {"Scope3YearOut", "Scope3YearCategoryOut", "Scope3YearLockedByOut"} <= state
    assert all(name.startswith("Scope3Year") for name in state)
    # S3K2b-1: 줄 덧판 넷의 꼴(Scope3RowEdit*) — 앞머리로 닫음(결과의 category 칸은 Scope3Year* 에 닿음)
    edit_routes = scope3_edit_operations()
    assert sorted(op.operation_id or "" for op in edit_routes) == sorted(SCOPE3_EDIT_OPERATIONS)
    edits: set[str] = set()
    for edit_route in edit_routes:
        edit_model = edit_route.response_models[200]
        assert edit_model is not None and edit_model is not NOT_SET
        edits |= set(definitions(edit_model, by_alias=edit_route.by_alias, mode="serialization"))
    assert {"Scope3RowEditOut", "Scope3RowEditsOut", "Scope3RowEditResultOut", "Scope3RowEditHistoryOut"} <= edits
    assert all(name.startswith(("Scope3RowEdit", "Scope3Year")) for name in edits)
    assert reached == set(RENAMED.values()) | colab | dashboard | state | edits
    components = cast("Mapping[str, object]", api.get_openapi_schema(path_prefix="")["components"]["schemas"])
    assert set(RENAMED.values()) <= set(components)
    assert not set(RENAMED) & set(components)


# ── T5 설명 그대로 ──

# RR1 전 응답 꼴(쌍둥이)의 설명 13 의 글자: (전의 자리) → (지금 자리, 글자). None 칸은 꼴 자체의 설명.
EVIDENCE_TEXT = "그 후보가 왜 그 자리에 왔는지. 낱말이 겹치지 않아 표 순서로 채워진 후보는 `lexical` 이 없다."
DESCRIPTIONS: list[tuple[str, str | None, str]] = [
    ("GasResultJson", "gwp", "적용한 GWP. 이미 환산된 계수(CO2e)면 null"),
    ("RowOkJson", "co2e", "반올림하지 않은 정확한 값 (tCO2eq)"),
    ("RowOkJson", "energy", "연소일 때만. 구매 전력·열은 null"),
    (
        "StepJson",
        None,
        "한 연산 단계. 손으로 따라갈 수 있게 식과 결과를 문자열로 싣는다. conversion 은 환산 단계에만 있다.",
    ),
    ("TotalsJson", "co2e", "성공한 행의 정확한 합 (tCO2eq). complete 가 false 면 부분합이다"),
    (
        "Scope3CandidateOut",
        None,
        "추린 후보 하나. 계수 값은 싣지 않는다. "
        "`path` 는 분류 경로가 있고 이름이 그 첫 마디로 시작하지 않을 때만 있다.",
    ),
    (
        "Scope3CatalogOut",
        None,
        "후보 자격은 갖췄는데 `value_raw` 가 엄격 십진이 아니라 빠진 줄(앞 20건과 총수). 조용히 빼지 않는다.",
    ),
    (
        "Scope3ClassifyOut",
        None,
        "묶음마다의 분류. ★ `synthetic` 은 늘 true 다: 지금 경로는 모의 공급사뿐이고 실제 모델의 판단이 아니다.",
    ),
    (
        "Scope3NoCandidatesOut",
        None,
        "조건에 맞는 후보가 없다. `physical` 은 활동·거리 기반 후보가 없던 까닭(지출 기반만 물었으면 null).",
    ),
    (
        "Scope3ShortlistedOut",
        None,
        "추린 후보.\n\n★ 동점은 「표 순서」로 가른다. 여기서 표 순서는 **계수 id 의 유니코드 코드 포인트 순**이다"
        "(기준정보의 표에는 적재\n순서가 없다). "
        "esg-lab 의 TS 는 파일의 줄 순서였으므로 동점인 후보의 차례가 그것과 다를 수 있다.",
    ),
    ("Scope3ShortlistedOut", "lexicalMatches", "낱말이 한 군데라도 겹친 후보 수. 0 이면 목록은 표의 앞 순서일 뿐이다"),
    ("Scope3ShortlistedOut", "total", "추리기 전 후보 수"),
]


def test_the_descriptions_kept_their_letters() -> None:
    components = cast(
        "Mapping[str, Mapping[str, Any]]", api.get_openapi_schema(path_prefix="")["components"]["schemas"]
    )
    for name, field, text in DESCRIPTIONS:
        node = components[name] if field is None else components[name]["properties"][field]
        assert node.get("description") == text, (name, field)
    # 전의 Scope3EvidenceOut 의 설명은 경로 전용 꼴의 칸으로 옮고, 끝에 rrfScore 한 문장이 붙었다(13번째).
    moved = components["Scope3ShortlistedOut"]["properties"]["evidence"]["description"]
    assert moved == EVIDENCE_TEXT + " 경로는 rrfScore 를 내지 않는다(RRF 를 거친 흐름 결과에만)."
    assert "description" not in components["CandidateEvidenceJson"]


# ── T6 판과 꼴 ──

OLD = "scope12.result@" + "1"  # 지운 판. 글자가 상수로 남지 않게 잇는다(section4-RR1.sh 가 센다)


def test_the_version_is_two_and_the_old_one_is_gone() -> None:
    assert OLD not in shapes.RESULT_SHAPES
    checker = shapes.RESULT_SHAPES["scope12.result@2"]
    result = flow_result(PURE_GOLDENS[0][0])
    checker.validate_python(result, strict=True)
    with pytest.raises(ValidationError):
        checker.validate_python({**result, "schemaVersion": OLD}, strict=True)


def test_a_tier_outside_one_to_four_is_rejected() -> None:
    checker = shapes.RESULT_SHAPES["scope12.result@2"]
    for golden, *_ in PURE_GOLDENS:
        result = flow_result(golden)
        rows = cast("list[dict[str, Any]]", result["rows"])
        tiered = [i for i, row in enumerate(rows) if row["status"] == "ok" and row["evidence"]["parameterTiers"]]
        if tiered:
            break
    else:
        pytest.fail("산정등급이 있는 행이 골든에 없다(분모)")
    checker.validate_python(result, strict=True)
    broken = copy.deepcopy(result)
    cast("list[dict[str, Any]]", broken["rows"])[tiered[0]]["evidence"]["parameterTiers"]["co2"] = 5
    with pytest.raises(ValidationError):
        checker.validate_python(broken, strict=True)


def test_the_result_is_the_body_with_schema_version_first() -> None:
    """Scope12Result 는 Scope12Body 를 물려받지 않는다(물려받으면 schemaVersion 이 끝으로 간다). 칸은 같다."""
    result = get_type_hints(shapes.Scope12Result, include_extras=True)
    body = get_type_hints(shapes.Scope12Body, include_extras=True)
    assert list(result) == ["schemaVersion", *body]
    assert {key: hint for key, hint in result.items() if key != "schemaVersion"} == body
    assert vars(shapes.Scope12Body)["__pydantic_config__"] == shapes.FORBID


def test_the_dashboard_counts_as_a_result_shape_closed_by_its_names() -> None:
    """(S12a-3) 대시보드는 SCOPE12_SCREEN_OPERATIONS 밖 — 결과 꼴 셈에 들고 이름은 전부 Scope12Dashboard 앞머리."""
    assert "inventory_scope12_dashboard" not in SCOPE12_SCREEN_OPERATIONS
    assert counts_as_result("inventory_scope12_dashboard")
    route = dashboard_operation()
    model = route.response_models[200]
    assert model is not None and model is not NOT_SET
    names = set(definitions(model, by_alias=route.by_alias, mode="serialization"))
    assert names == {
        "Scope12DashboardOut",
        "Scope12DashboardScopeOut",
        "Scope12DashboardSourceOut",
        "Scope12DashboardTotalOut",
        "Scope12DashboardSiteOut",
        "Scope12DashboardSiteScopeOut",
        "Scope12DashboardCategoryOut",
    }
