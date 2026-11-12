"""오류 응답의 한 꼴과 바닥의 처리기(밴드 E2 ②): 422 VALIDATION_ERROR·500 INTERNAL_SERVER_ERROR·444 선언.

순수 층은 ninja.testing.TestClient(미들웨어·DB 없음)로, 업무 층(django_db)은 로그인한 Client 로 잰다.
"""

import json
import logging
from typing import Any

import pytest
from django.db import InterfaceError, OperationalError
from django.test import Client
from ninja.testing import TestClient

import esgapi.config.api as config_api
import esgapi.config.urls as urls
import esgapi.core.tenancy.middleware as tenancy_middleware
from esgapi.config.api import INTERNAL_MESSAGE, VALIDATION_MESSAGE, api, field_name
from tests.support.errors import error_detail, error_of, fields_of
from tests.support.http import login

ERROR_REF = "#/components/schemas/ErrorBody"
# 오류 상태인데 ErrorBody 가 아닌 것: /readyz 의 503 은 상태 확인의 꼴(ReadyOut)이다.
NOT_ERROR_BODY = {("get", "/readyz", "503")}
BEARER_SCHEMES = {"AccessTokenAuth", "CompanyScopedAuth"}
# 본문(refresh 토큰)으로 토큰을 받는 동작. 보안 선언이 없어도 444 를 낸다.
BODY_TOKEN_TAKERS = {("post", "/auth/refresh"), ("post", "/auth/revoke")}


def _operations() -> dict[tuple[str, str], dict[str, Any]]:
    document: dict[str, Any] = json.loads(json.dumps(api.get_openapi_schema(path_prefix="")))
    return {(method, path): op for path, item in document["paths"].items() for method, op in item.items()}


def _security(operation: dict[str, Any]) -> list[dict[str, Any]]:
    security: list[dict[str, Any]] = operation.get("security") or []
    return security


def _client() -> Any:
    """ninja 의 TestClient(미들웨어·DB 를 거치지 않는다). 타입 표시가 덜 되어 있어 Any 로 쓴다."""
    return TestClient(api)


# ── ⓐ 선언 전수: 4xx·5xx 는 전부 ErrorBody ──


def test_every_declared_error_status_is_the_one_error_body() -> None:
    seen = 0
    for (method, path), operation in _operations().items():
        for status, answer in operation["responses"].items():
            if int(status) < 400 or (method, path, status) in NOT_ERROR_BODY:
                continue
            seen += 1
            assert answer["content"]["application/json"]["schema"] == {"$ref": ERROR_REF}, (method, path, status)
    assert seen > 300  # 분모: 동작 37 × 오류 상태 열 안팎


def test_every_operation_that_declares_errors_declares_422_and_500() -> None:
    with_errors = 0
    for key, operation in _operations().items():
        statuses = {s for s in operation["responses"] if int(s) >= 400} - {"503"}
        if not statuses:
            continue  # 로그아웃·healthz·readyz
        with_errors += 1
        assert {"422", "500"} <= statuses, key
    assert with_errors == 164  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · S3K2b-1 +4: Scope 3 줄 덧판 넷
    # · S3K2b-2 +1: Scope 3 계수 수정
    # · S3D1 +1: GET /inventory/scope3/years/{year}/export
    # · IRS3 +3: GET·POST /materiality/runs/{run_id}/result/edits · GET …/report(③)
    # · AU1b-2 +2: GET /run-logs·/run-logs/metrics
    # · G1b-1 +1: GET /greenwash/checks
    # · X1b-2a +2: PATCH /documents/{id}·GET /documents/{id}/file
    # · G2c2 +5: /ai-settings/greenwash 다섯
    # · AS2a +2: /ai-settings/greenwash 의 prompt-model 둘
    # · TR2 +1: GET /translation/runs/{run_id}/result
    # · AD4S +1: GET /run-logs/export
    # · AD4D +1: GET /run-logs/{run_id}
    # · RF1 +1: GET /run-logs/{run_id}/files/{name}
    # · DV1e +1: GET /dataverify/runs/{run_id}/result
    # · DV1g +1: GET /dataverify/runs
    # · TR3b +3: GET /translation/batches · GET …/batches/{batch_key} · GET …/batches/{batch_key}/archive
    # · TR4 +7: /ai-settings/translation 일곱
    # · IR3b +1: GET /materiality/runs/{run_id}/result
    # · DVA1 +7: /ai-settings/dataverify 일곱
    # · IR3c +1: GET /materiality/runs
    # · TRP6 +1: GET /translation/documents/{document_id}/pages
    # · TRS3 +1: GET /translation/runs/{run_id}/layout
    # · IRW2 +1: POST /materiality/value-chain/read
    # · IR4 +7: /ai-settings/materiality 일곱
    # · K1b-1 +11: /branches 여섯 · /facility-codes · /admin/facility-codes 넷
    # · K1b-2a +12: /inventory/admin/ghg-* 열둘
    # · K1b-2b +2: /inventory/scope12 둘
    # · S12a +10: /inventory/scope12 열(Scope 1·2 입력)
    # · DVX1 +2: POST /dataverify/edk/read · GET /dataverify/edk/template
    # · RP1 +5: /drafting 다섯
    # · RP2d +2: GET /drafting/projects · GET /drafting/runs/{run_id}/result.docx
    # · RP2c +1: GET /drafting/projects/{project_id}/outline/changes
    # · RPS1 +1: GET /drafting/projects/{project_id}/runs
    # · S12a-2 +3: /inventory/scope12 셋(입력주기·행 계수 바꿈·복구)
    # · RPA1 +7: /ai-settings/drafting 일곱
    # · S12a-3 +1: GET /inventory/scope12/dashboard
    # · S12b-1 +2: GET /inventory/scope12/years/{year}/template · …/export
    # · S3K2a +3: GET /inventory/scope3/years/{year} · POST·DELETE …/categories/{category}/lock


# ── ⓔ 444: 토큰을 받는 동작 전수가 선언한다 ──


def test_444_is_declared_exactly_by_the_operations_that_take_a_token() -> None:
    operations = _operations()
    takers = {
        key
        for key, operation in operations.items()
        if any(name in BEARER_SCHEMES for item in _security(operation) for name in item)
    } | BODY_TOKEN_TAKERS
    declared = {key for key, operation in operations.items() if "444" in operation["responses"]}
    assert declared == takers
    assert len(takers) == 161  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · S3K2b-1 +4: Scope 3 줄 덧판 넷
    # · S3K2b-2 +1: Scope 3 계수 수정
    # · S3D1 +1: GET /inventory/scope3/years/{year}/export
    # · IRS3 +3: GET·POST /materiality/runs/{run_id}/result/edits · GET …/report(③)
    # · AU1b-2 +2: GET /run-logs·/run-logs/metrics
    # · G1b-1 +1: GET /greenwash/checks
    # · X1b-2a +2: PATCH /documents/{id}·GET /documents/{id}/file
    # · G2c2 +5: /ai-settings/greenwash 다섯
    # · AS2a +2: /ai-settings/greenwash 의 prompt-model 둘
    # · TR2 +1: GET /translation/runs/{run_id}/result
    # · AD4S +1: GET /run-logs/export
    # · AD4D +1: GET /run-logs/{run_id}
    # · RF1 +1: GET /run-logs/{run_id}/files/{name}
    # · DV1e +1: GET /dataverify/runs/{run_id}/result
    # · DV1g +1: GET /dataverify/runs
    # · TR3b +3: GET /translation/batches · GET …/batches/{batch_key} · GET …/batches/{batch_key}/archive
    # · TR4 +7: /ai-settings/translation 일곱
    # · IR3b +1: GET /materiality/runs/{run_id}/result
    # · DVA1 +7: /ai-settings/dataverify 일곱
    # · IR3c +1: GET /materiality/runs
    # · TRP6 +1: GET /translation/documents/{document_id}/pages
    # · TRS3 +1: GET /translation/runs/{run_id}/layout
    # · IRW2 +1: POST /materiality/value-chain/read
    # · IR4 +7: /ai-settings/materiality 일곱
    # · K1b-1 +11: /branches 여섯 · /facility-codes · /admin/facility-codes 넷
    # · K1b-2a +12: /inventory/admin/ghg-* 열둘
    # · K1b-2b +2: /inventory/scope12 둘
    # · S12a +10: /inventory/scope12 열(Scope 1·2 입력)
    # · DVX1 +2: POST /dataverify/edk/read · GET /dataverify/edk/template
    # · RP1 +5: /drafting 다섯
    # · RP2d +2: GET /drafting/projects · GET /drafting/runs/{run_id}/result.docx
    # · RP2c +1: GET /drafting/projects/{project_id}/outline/changes
    # · RPS1 +1: GET /drafting/projects/{project_id}/runs
    # · S12a-2 +3: /inventory/scope12 셋(입력주기·행 계수 바꿈·복구)
    # · RPA1 +7: /ai-settings/drafting 일곱
    # · S12a-3 +1: GET /inventory/scope12/dashboard
    # · S12b-1 +2: GET /inventory/scope12/years/{year}/template · …/export
    # · S3K2a +3: GET /inventory/scope3/years/{year} · POST·DELETE …/categories/{category}/lock


# ── ⓑ 422: fields 의 칸 이름 ──


@pytest.mark.parametrize(
    ("loc", "name"),
    [
        (("body", "body", "rows", 0, "factorYear"), "rows.0.factorYear"),
        (("body", "payload", "name"), "name"),
        (("body", "body"), "body"),
        (("query", "limit"), "limit"),
        (("query", "record_type"), "recordType"),
        (("path", "document_id"), "documentId"),
        (("body", "body", "extra_field"), "extra_field"),  # 보낸 쪽이 쓴 모르는 칸 이름은 그대로
    ],
)
def test_field_name(loc: tuple[object, ...], name: str) -> None:
    assert field_name(loc) == name


def test_a_malformed_login_body_is_422_with_camel_fields_and_no_echo() -> None:
    secret = "do-not-echo-9f31"
    response = _client().post(
        "/auth/login", json={"username": ["x"], "password": secret, "companySubdomain": 7, "extra_field": secret}
    )
    assert error_of(response) == (422, "VALIDATION_ERROR")
    detail = error_detail(response)
    assert (detail["message"], detail["legacyCode"]) == (VALIDATION_MESSAGE, "invalid_input")
    fields = fields_of(response)
    assert fields is not None
    assert set(fields) == {"username", "companySubdomain", "extra_field"}
    assert all(messages for messages in fields.values())
    assert secret not in response.content.decode()


def test_a_body_that_is_not_json_is_400_in_the_one_shape() -> None:
    response = _client().post("/auth/login", data="{not json", content_type="application/json")
    assert error_of(response) == (400, "BAD_REQUEST")
    assert fields_of(response) is None


# ── ⓒ 500: 상세는 로그에만 ──


def test_an_unexpected_exception_is_500_with_no_detail_and_is_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "secret-detail /srv/app/internal.py"

    def broken(**_: Any) -> Any:
        raise RuntimeError(secret)

    monkeypatch.setattr(config_api, "HealthOut", broken)
    with caplog.at_level(logging.ERROR, logger="esgapi.config.api"):
        response = _client().get("/healthz")
    assert error_of(response) == (500, "INTERNAL_SERVER_ERROR")
    detail = error_detail(response)
    assert (detail["message"], detail["fields"], detail["legacyCode"]) == (INTERNAL_MESSAGE, None, None)
    body = response.content.decode()
    assert secret not in body and "RuntimeError" not in body and "Traceback" not in body
    assert secret in caplog.text  # 예외의 글자는 기록에 있다(log.exception 의 traceback)


# ── 업무 층: 로그인한 요청의 표본 ──


@pytest.mark.django_db
def test_a_nested_body_error_names_the_field_path_and_does_not_echo(client: Client, tenants: None) -> None:
    login(client)
    secret = "nested-secret-77"
    response = client.post(
        "/api/inventory/calc",
        data={"rows": [{"id": "r1", "factorYear": secret}], "gwpSetId": "g"},
        content_type="application/json",
    )
    assert error_of(response) == (422, "VALIDATION_ERROR")
    fields = fields_of(response)
    assert fields is not None
    assert "rows.0.factorYear" in fields
    assert secret not in response.content.decode()


@pytest.mark.parametrize("error", [OperationalError, InterfaceError])
def test_an_unreachable_db_is_503_unavailable_not_500(monkeypatch: pytest.MonkeyPatch, error: type[Exception]) -> None:
    def broken(**_: Any) -> Any:
        raise error("connection refused: secret-host:5432")

    monkeypatch.setattr(config_api, "HealthOut", broken)
    response = _client().get("/healthz")
    assert error_of(response) == (503, "UNAVAILABLE")
    assert "secret-host" not in response.content.decode()


# ── 405·ninja 밖의 500 도 한 꼴(검증 B1·R1) — Django 의 사슬(미들웨어·urls)을 거친다 ──


@pytest.mark.parametrize(
    ("method", "path", "allowed"), [("delete", "/api/healthz", "GET"), ("put", "/api/auth/login", "POST")]
)
def test_a_method_the_path_does_not_have_is_405_in_the_one_shape_and_keeps_allow(
    method: str, path: str, allowed: str
) -> None:
    response = getattr(Client(), method)(path)
    assert response["Content-Type"].startswith("application/json")
    assert error_of(response) == (405, "METHOD_NOT_ALLOWED")
    assert (fields_of(response), error_detail(response)["legacyCode"]) == (None, None)
    assert allowed in response["Allow"]


def test_an_exception_outside_ninja_is_500_in_the_one_shape(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "outside-ninja-secret /srv/app/y.py"

    def broken(*_: Any, **__: Any) -> Any:
        raise RuntimeError(secret)

    monkeypatch.setattr(tenancy_middleware, "read_session", broken)
    with caplog.at_level(logging.ERROR, logger="django.request"):
        response = Client(raise_request_exception=False).get("/api/sites")
    assert error_of(response) == (500, "INTERNAL_SERVER_ERROR")
    assert error_detail(response)["message"] == INTERNAL_MESSAGE
    assert secret not in response.content.decode()
    assert secret in caplog.text  # Django 가 django.request 에 남긴다


def test_the_urls_hand_404_and_500_to_the_one_shape() -> None:
    assert (urls.handler404, urls.handler500) == (config_api.not_found, config_api.server_error)
