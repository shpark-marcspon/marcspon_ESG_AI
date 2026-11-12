"""DB 없이 답해야 하는 경로들과 계약(OpenAPI). 순수 층: 이 파일의 테스트가 DB 에 닿으면 pytest-django 가 실패시킨다."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Final

from django.conf import global_settings, settings
from django.test import Client

from esgapi.config.api import api
from esgapi.core.flows.registry import MODULE_ID, VERSIONED_ID
from esgapi.runs.models import RUN_ROW_STATUSES

GENERATED = Path(__file__).resolve().parents[3] / "generated" / "openapi.json"
TYPES_SOURCE_HASH = GENERATED.with_name("api.d.ts.source-sha256")

# 계약의 이름표: (메서드, 경로) → operationId. 전부 손으로 적은 `<모듈>_<동작>` 이다.
# 경로 함수를 다른 파일로 옮겨도 이름이 바뀌지 않는다는 것을 이 표가 못 박는다(프론트의 타입 이름이 여기서 나온다).
# 경로를 더하면 이 표에 한 줄을 더한다.
OPERATION_IDS = {
    ("get", "/healthz"): "config_healthz",
    ("get", "/readyz"): "config_readyz",
    ("post", "/auth/exchange"): "accounts_auth_exchange",
    ("post", "/auth/logout"): "accounts_auth_logout",
    ("get", "/me"): "accounts_me",
    ("get", "/sites"): "accounts_sites_list",
    ("post", "/sites"): "accounts_sites_create",
    ("post", "/inventory/calc"): "inventory_calc",
    ("post", "/inventory/scope3/shortlist"): "inventory_scope3_shortlist",
    ("post", "/inventory/scope3/classify"): "inventory_scope3_classify",
    ("get", "/reference/sources"): "reference_sources",
    ("get", "/reference/factors"): "reference_factors",
    ("post", "/reference/assemble"): "reference_assemble",
    ("post", "/reference/assemble-electricity"): "reference_assemble_electricity",
    ("post", "/documents"): "core_documents_create",
    ("post", "/documents/{document_id}/confirm"): "core_documents_confirm",
    ("get", "/documents/{document_id}"): "core_documents_get",
    # 계약 먼저(밴드 XC)였던 둘 — 몸은 X1b-2a. 아래 RUN_CONTRACT 가 꼴을 못 박는다.
    ("get", "/documents"): "core_documents_list",
    ("get", "/documents/{document_id}/versions"): "core_documents_versions",
    # X1b-2a: 문서 고치기(보고 연도·앞 판)와 원본 내려받기.
    ("patch", "/documents/{document_id}"): "core_documents_update",
    ("get", "/documents/{document_id}/file"): "core_documents_file_get",
    ("post", "/runs"): "runs_create",
    ("get", "/runs"): "runs_list",
    ("get", "/runs/{run_id}"): "runs_get",
    ("get", "/runs/{run_id}/files/{name}"): "runs_file_get",
    ("get", "/runs/{run_id}/segments"): "runs_segments_list",  # RM1c ③ +1
    ("get", "/greenwash/runs/{run_id}/result"): "greenwash_result_get",
    ("get", "/greenwash/runs/{run_id}/result2"): "greenwash_result2_get",  # GE1b ④
    ("get", "/greenwash/runs/{run_id}/review"): "greenwash_review_get",
    ("put", "/greenwash/runs/{run_id}/review"): "greenwash_review_put",
    ("post", "/greenwash/runs/{run_id}/items/{item_index}/rejudge"): "greenwash_item_rejudge",  # GRJ1 +1
    ("get", "/greenwash/compare"): "greenwash_compare_get",
    ("get", "/greenwash/runs/{run_id}/report"): "greenwash_report_get",
    ("get", "/greenwash/terms/default"): "greenwash_terms_default",
    ("get", "/greenwash/checks"): "greenwash_checks_get",
    ("get", "/translation/runs/{run_id}/result"): "translation_result_get",
    ("get", "/translation/runs/{run_id}/layout"): "translation_layout_get",
    ("post", "/translation/glossary/read"): "translation_glossary_read",
    ("get", "/translation/glossary/template"): "translation_glossary_template",
    ("get", "/translation/batches"): "translation_batches_list",
    ("get", "/translation/documents/{document_id}/batches/{batch_key}"): "translation_batch_get",
    ("get", "/translation/documents/{document_id}/batches/{batch_key}/archive"): "translation_batch_archive",
    ("get", "/translation/documents/{document_id}/pages"): "translation_document_pages",
    ("get", "/dataverify/runs/{run_id}/result"): "dataverify_result_get",
    ("get", "/dataverify/runs"): "dataverify_runs_list",
    ("post", "/dataverify/edk/read"): "dataverify_edk_read",
    ("get", "/dataverify/edk/template"): "dataverify_edk_template",
    ("get", "/materiality/runs/{run_id}/result"): "materiality_result_get",
    ("get", "/materiality/runs"): "materiality_runs_list",
    ("post", "/materiality/value-chain/read"): "materiality_value_chain_read",
    ("get", "/materiality/runs/{run_id}/result/edits"): "materiality_result_edits_get",  # IRS3 ②
    ("post", "/materiality/runs/{run_id}/result/edits"): "materiality_result_edits_post",
    ("get", "/materiality/runs/{run_id}/report"): "materiality_report_get",  # IRS3 ③
    # 원고작성(RP1 ③)
    ("post", "/drafting/projects"): "drafting_projects_create",
    ("get", "/drafting/projects/{project_id}"): "drafting_project_get",
    ("put", "/drafting/projects/{project_id}/document"): "drafting_project_document_put",
    ("put", "/drafting/projects/{project_id}/outline"): "drafting_outline_put",
    ("get", "/drafting/runs/{run_id}/result"): "drafting_result_get",
    ("get", "/drafting/projects"): "drafting_projects_list",  # RP2d
    ("get", "/drafting/runs/{run_id}/result.docx"): "drafting_result_download",  # RP2d
    ("get", "/drafting/projects/{project_id}/outline/changes"): "drafting_outline_changes",  # RP2c
    ("get", "/drafting/projects/{project_id}/runs"): "drafting_project_runs",  # RPS1
    # 로그인·토큰·자기 계정(밴드 K2a). 토큰을 받는 넷만 444 를 선언한다(아래 test_444_is_declared_by_the_token_takers).
    ("post", "/auth/login"): "user_auth_login",
    ("post", "/auth/refresh"): "user_auth_refresh",
    ("post", "/auth/revoke"): "user_auth_revoke",
    ("get", "/users/me"): "user_me",
    ("post", "/users/me/password"): "user_password_change",
    # 고객사 사용자 관리(밴드 K2c·UA1 — 운영 관리자 전용). 넷 다 Bearer 라 444 를 선언한다.
    ("get", "/users"): "user_list",
    ("post", "/users"): "user_create",
    ("post", "/users/{user_id}/password-reset"): "user_password_reset",
    ("patch", "/users/{user_id}"): "user_update",
    # 감사 기록 조회(AU1a — AD-05, 운영 관리자 전용). Bearer 라 444 를 선언한다.
    ("get", "/audit-logs"): "user_audit_list",
    # 감사 기록에 나온 사람 목록(AU1b-1 — 운영 관리자 전용). Bearer 라 444 를 선언한다.
    ("get", "/audit-logs/actors"): "user_audit_actors",
    # 운영 관리자 실행 기록(AU1b-2 — AD-04, 운영 관리자 전용): 목록과 이번 달 지표. Bearer 라 444 를 선언한다.
    ("get", "/run-logs"): "user_run_log_list",
    ("get", "/run-logs/metrics"): "user_run_log_metrics",
    # 실행 기록 엑셀 내보내기(AD4S — 운영 관리자 전용). Bearer 라 444 를 선언한다.
    ("get", "/run-logs/export"): "user_run_log_export",
    # 실행 상세(AD4D — AD-04a, 운영 관리자 전용). Bearer 라 444 를 선언한다.
    ("get", "/run-logs/{run_id}"): "user_run_log_get",
    ("get", "/run-logs/{run_id}/files/{name}"): "user_run_log_file_get",  # RF1
    # 그린워싱 AI 설정 판(G2c2 — 운영 관리자 전용, /ai-settings/<모듈> — MARC-ENT-335). Bearer 라 444 를 선언한다.
    ("get", "/ai-settings/greenwash"): "greenwash_ai_setting_list",
    ("get", "/ai-settings/greenwash/default"): "greenwash_ai_setting_default",
    ("get", "/ai-settings/greenwash/{setting_id}"): "greenwash_ai_setting_get",
    ("post", "/ai-settings/greenwash"): "greenwash_ai_setting_create",
    ("put", "/ai-settings/greenwash/applied"): "greenwash_ai_setting_apply",
    # AS2a: 판의 프롬프트·모델 읽기 둘(ai.prompt-model@1)
    ("get", "/ai-settings/greenwash/{setting_id}/prompt-model"): "greenwash_ai_setting_prompt_model",
    ("get", "/ai-settings/greenwash/default/prompt-model"): "greenwash_ai_setting_default_prompt_model",
    # TR4: 영문번역 AI 설정 판 일곱(그린워싱과 같은 꼴 — 프롬프트·모델은 ai.prompt-model@3)
    ("get", "/ai-settings/translation"): "translation_ai_setting_list",
    ("get", "/ai-settings/translation/default"): "translation_ai_setting_default",
    ("get", "/ai-settings/translation/{setting_id}"): "translation_ai_setting_get",
    ("post", "/ai-settings/translation"): "translation_ai_setting_create",
    ("put", "/ai-settings/translation/applied"): "translation_ai_setting_apply",
    ("get", "/ai-settings/translation/{setting_id}/prompt-model"): "translation_ai_setting_prompt_model",
    ("get", "/ai-settings/translation/default/prompt-model"): "translation_ai_setting_default_prompt_model",
    # DVA1: 데이터 검증 AI 설정 판 일곱(영문번역과 같은 꼴 — 프롬프트·모델은 ai.prompt-model@3)
    ("get", "/ai-settings/dataverify"): "dataverify_ai_setting_list",
    ("get", "/ai-settings/dataverify/default"): "dataverify_ai_setting_default",
    ("get", "/ai-settings/dataverify/{setting_id}"): "dataverify_ai_setting_get",
    ("post", "/ai-settings/dataverify"): "dataverify_ai_setting_create",
    ("put", "/ai-settings/dataverify/applied"): "dataverify_ai_setting_apply",
    ("get", "/ai-settings/dataverify/{setting_id}/prompt-model"): "dataverify_ai_setting_prompt_model",
    ("get", "/ai-settings/dataverify/default/prompt-model"): "dataverify_ai_setting_default_prompt_model",
    # IR4: 중대성평가 IRO AI 설정 판 일곱(데이터 검증과 같은 꼴 — 프롬프트·모델은 ai.prompt-model@3)
    ("get", "/ai-settings/materiality"): "materiality_ai_setting_list",
    ("get", "/ai-settings/materiality/default"): "materiality_ai_setting_default",
    ("get", "/ai-settings/materiality/{setting_id}"): "materiality_ai_setting_get",
    ("post", "/ai-settings/materiality"): "materiality_ai_setting_create",
    ("put", "/ai-settings/materiality/applied"): "materiality_ai_setting_apply",
    ("get", "/ai-settings/materiality/{setting_id}/prompt-model"): "materiality_ai_setting_prompt_model",
    ("get", "/ai-settings/materiality/default/prompt-model"): "materiality_ai_setting_default_prompt_model",
    # RPA1: 원고작성 AI 설정 판 일곱(중대성평가 IRO 와 같은 꼴 — 프롬프트·모델은 ai.prompt-model@3)
    ("get", "/ai-settings/drafting"): "drafting_ai_setting_list",
    ("get", "/ai-settings/drafting/default"): "drafting_ai_setting_default",
    ("get", "/ai-settings/drafting/{setting_id}"): "drafting_ai_setting_get",
    ("post", "/ai-settings/drafting"): "drafting_ai_setting_create",
    ("put", "/ai-settings/drafting/applied"): "drafting_ai_setting_apply",
    ("get", "/ai-settings/drafting/{setting_id}/prompt-model"): "drafting_ai_setting_prompt_model",
    ("get", "/ai-settings/drafting/default/prompt-model"): "drafting_ai_setting_default_prompt_model",
    # K1b-1: 사업장 여섯 · 자산/시설 코드 목록 다섯(organization — 플랫폼-서버 ce 허락 (다) 2026-10-28)
    ("get", "/branches"): "organization_branches_list",
    ("get", "/branches/{branch_id}"): "organization_branches_get",
    ("post", "/branches"): "organization_branches_create",
    ("put", "/branches/{branch_id}"): "organization_branches_save",
    ("post", "/branches/inventory"): "organization_branches_inventory",
    ("post", "/branches/delete"): "organization_branches_delete",
    ("get", "/facility-codes"): "organization_facility_codes_list",
    ("get", "/admin/facility-codes"): "organization_admin_facility_codes_list",
    ("post", "/admin/facility-codes"): "organization_admin_facility_codes_create",
    ("patch", "/admin/facility-codes/{code_id}"): "organization_admin_facility_codes_update",
    ("post", "/admin/facility-codes/delete"): "organization_admin_facility_codes_delete",
    # K1b-2a: 온실가스 인덱스 풀·계수 풀 열둘(inventory — 운영 관리자 Bearer, 플랫폼-서버 dc 허락 H6 2026-10-28)
    ("get", "/inventory/admin/ghg-index/nodes"): "inventory_admin_ghg_nodes_list",
    ("post", "/inventory/admin/ghg-index/nodes"): "inventory_admin_ghg_nodes_create",
    ("patch", "/inventory/admin/ghg-index/nodes/{node_id}"): "inventory_admin_ghg_nodes_update",
    ("post", "/inventory/admin/ghg-index/nodes/delete"): "inventory_admin_ghg_nodes_delete",
    ("get", "/inventory/admin/ghg-index/facilities/{node_id}"): "inventory_admin_ghg_facilities_get",
    ("post", "/inventory/admin/ghg-index/facilities"): "inventory_admin_ghg_facilities_create",
    ("put", "/inventory/admin/ghg-index/facilities/{node_id}"): "inventory_admin_ghg_facilities_save",
    ("post", "/inventory/admin/ghg-index/facilities/{node_id}/factors"): "inventory_admin_ghg_factors_create",
    ("get", "/inventory/admin/ghg-factors/{factor_id}"): "inventory_admin_ghg_factors_get",
    ("put", "/inventory/admin/ghg-factors/{factor_id}"): "inventory_admin_ghg_factors_save",
    ("post", "/inventory/admin/ghg-factors/delete"): "inventory_admin_ghg_factors_delete",
    ("get", "/inventory/admin/ghg-options"): "inventory_admin_ghg_options",
    # K1b-2b 고객사 인덱스 선택 둘(플랫폼-서버 e7 허락 2026-10-29)
    ("get", "/inventory/scope12/index-tree"): "inventory_scope12_index_tree",
    ("put", "/inventory/scope12/index-selections/{year}"): "inventory_scope12_index_selections_save",
    # S12a Scope 1·2 입력 열(플랫폼-서버 e7 허락 2026-10-29)
    ("get", "/inventory/scope12/years"): "inventory_scope12_years",
    ("get", "/inventory/scope12/rows"): "inventory_scope12_rows",
    ("get", "/inventory/scope12/years/{year}/indexes/{node_id}"): "inventory_scope12_index_detail",
    ("put", "/inventory/scope12/years/{year}/indexes/{node_id}/sites/{site_id}/rows"): "inventory_scope12_rows_save",
    ("post", "/inventory/scope12/years/{year}/indexes/{node_id}/rows/delete"): "inventory_scope12_rows_delete",
    ("put", "/inventory/scope12/years/{year}/indexes/{node_id}/memo"): "inventory_scope12_memo_save",
    ("post", "/inventory/scope12/years/{year}/indexes/{node_id}/lock"): "inventory_scope12_lock",
    ("delete", "/inventory/scope12/years/{year}/indexes/{node_id}/lock"): "inventory_scope12_unlock",
    ("put", "/inventory/scope12/years/{year}/decimals"): "inventory_scope12_decimals_save",
    ("get", "/inventory/scope12/years/{year}/indexes/{node_id}/rows/{row_id}/history"): "inventory_scope12_row_history",
    # S12a-2: 입력주기 · 행 계수 바꿈 · 히스토리 복구
    (
        "put",
        "/inventory/scope12/years/{year}/indexes/{node_id}/sites/{site_id}/period",
    ): "inventory_scope12_period_save",
    (
        "put",
        "/inventory/scope12/years/{year}/indexes/{node_id}/rows/{row_id}/factor",
    ): "inventory_scope12_row_factor_save",
    (
        "post",
        "/inventory/scope12/years/{year}/indexes/{node_id}/rows/{row_id}/history/{history_id}/restore",
    ): "inventory_scope12_history_restore",
    ("get", "/inventory/scope3/template"): "inventory_scope3_template",  # S3K1
    ("get", "/inventory/scope3/runs/{run_id}/result"): "inventory_scope3_result_get",  # S3K1
    ("get", "/inventory/scope3/runs/{run_id}/original"): "inventory_scope3_original_get",  # S3Q1 +1
    ("get", "/inventory/scope12/dashboard"): "inventory_scope12_dashboard",  # S12a-3
    ("get", "/inventory/scope12/years/{year}/template"): "inventory_scope12_template",  # S12b-1
    ("get", "/inventory/scope12/years/{year}/export"): "inventory_scope12_export",  # S12b-1
    ("post", "/inventory/scope12/years/{year}/uploads"): "inventory_scope12_upload",  # S12b-2
    ("get", "/inventory/scope3/years/{year}"): "inventory_scope3_year_get",  # S3K2a
    ("get", "/inventory/scope3/years/{year}/export"): "inventory_scope3_export",  # S3D1
    ("post", "/inventory/scope3/years/{year}/categories/{category}/lock"): "inventory_scope3_lock",  # S3K2a
    ("delete", "/inventory/scope3/years/{year}/categories/{category}/lock"): "inventory_scope3_unlock",  # S3K2a
    (
        "post",
        "/inventory/scope3/runs/{run_id}/categories/{category}/exclusions",
    ): "inventory_scope3_rows_exclude",  # S3K2b-1
    (
        "post",
        "/inventory/scope3/runs/{run_id}/categories/{category}/restorations",
    ): "inventory_scope3_rows_restore",  # S3K2b-1
    ("get", "/inventory/scope3/runs/{run_id}/edits"): "inventory_scope3_edits_get",  # S3K2b-1
    ("get", "/inventory/scope3/runs/{run_id}/history"): "inventory_scope3_history_get",  # S3K2b-1
    ("post", "/inventory/scope3/runs/{run_id}/categories/{category}/factors"): "inventory_scope3_row_factor",  # S3K2b-2
}
OPERATION_ID_SHAPE = re.compile(r"[a-z]+(_[a-z0-9]+)+")


def _document() -> dict[str, Any]:
    return json.loads(json.dumps(api.get_openapi_schema(path_prefix="")))


def _operations(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(method, path): operation for path, item in document["paths"].items() for method, operation in item.items()}


# config/api.py 가 모듈의 라우터를 거는 자리. user·organization 은 맨 위(/)에 걸려 있다.
MODULE_PREFIXES = (
    "/inventory/",
    "/reference/",
    "/greenwash/",
    "/translation/",  # TR2
    "/dataverify/",  # DV1e
    "/materiality/",  # IR3b
    "/drafting/",  # RP1
)


def test_healthz_is_ok_without_touching_the_db(client: Client) -> None:
    response = client.get("/api/healthz")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


def test_openapi_and_docs_are_served(client: Client) -> None:
    schema: dict[str, Any] = client.get("/api/openapi.json").json()
    # 모듈의 자리(/<모듈>/…) 밖에 걸린 경로는 정확히 이 스물일곱이다
    # (상태 확인 둘 + user·organization 넷(교환·로그아웃·me 셋 + /sites 하나) + core 의 문서 다섯
    #  (X1b-2a +1 원본, 감독 c1 허락) + 실행 셋
    #  + 로그인·자기 계정 다섯(K2a) + 사용자 관리 셋(K2c·UA1 — 동작 넷) + 감사 기록 둘(AU1a·AU1b-1)
    #  + 실행 기록 둘(AU1b-2) + 실행 기록 내보내기(AD4S)).
    # 다른 모듈의 경로는 자기 자리(/<모듈>/…) 아래에만 생긴다. 그쪽은 그 모듈의 테스트가 잰다.
    # /documents 를 MODULE_PREFIXES 에 넣지 않은 까닭: 그 경로 자체는 "/documents/" 로 시작하지 않는다.
    at_root = {path for path in schema["paths"] if not path.startswith(MODULE_PREFIXES)}
    assert at_root == {
        "/healthz",
        "/readyz",
        "/auth/exchange",
        "/auth/logout",
        "/me",
        "/sites",
        "/documents",
        "/documents/{document_id}",
        "/documents/{document_id}/confirm",
        "/documents/{document_id}/versions",
        "/documents/{document_id}/file",
        "/runs",
        "/runs/{run_id}",
        "/runs/{run_id}/files/{name}",
        "/runs/{run_id}/segments",
        "/auth/login",
        "/auth/refresh",
        "/auth/revoke",
        "/users/me",
        "/users/me/password",
        "/users",
        "/users/{user_id}/password-reset",
        "/users/{user_id}",
        "/audit-logs",
        "/audit-logs/actors",
        "/run-logs",
        "/run-logs/metrics",
        "/run-logs/export",  # AD4S
        "/run-logs/{run_id}",  # AD4D
        "/run-logs/{run_id}/files/{name}",  # RF1
        # G2c2: 그린워싱 AI 설정 판(/ai-settings/greenwash — 경로 넷, 동작 다섯)
        "/ai-settings/greenwash",
        "/ai-settings/greenwash/default",
        "/ai-settings/greenwash/{setting_id}",
        "/ai-settings/greenwash/applied",
        # AS2a: 판의 프롬프트·모델 읽기 둘
        "/ai-settings/greenwash/{setting_id}/prompt-model",
        "/ai-settings/greenwash/default/prompt-model",
        # TR4: 영문번역 AI 설정 판(경로 여섯, 동작 일곱)
        "/ai-settings/translation",
        "/ai-settings/translation/default",
        "/ai-settings/translation/{setting_id}",
        "/ai-settings/translation/applied",
        "/ai-settings/translation/{setting_id}/prompt-model",
        "/ai-settings/translation/default/prompt-model",
        # DVA1: 데이터 검증 AI 설정 판(경로 여섯, 동작 일곱)
        "/ai-settings/dataverify",
        "/ai-settings/dataverify/default",
        "/ai-settings/dataverify/{setting_id}",
        "/ai-settings/dataverify/applied",
        "/ai-settings/dataverify/{setting_id}/prompt-model",
        "/ai-settings/dataverify/default/prompt-model",
        # IR4: 중대성평가 IRO AI 설정 판(경로 여섯, 동작 일곱)
        "/ai-settings/materiality",
        "/ai-settings/materiality/default",
        "/ai-settings/materiality/{setting_id}",
        "/ai-settings/materiality/applied",
        "/ai-settings/materiality/{setting_id}/prompt-model",
        "/ai-settings/materiality/default/prompt-model",
        # RPA1: 원고작성 AI 설정 판(경로 여섯, 동작 일곱)
        "/ai-settings/drafting",
        "/ai-settings/drafting/default",
        "/ai-settings/drafting/{setting_id}",
        "/ai-settings/drafting/applied",
        "/ai-settings/drafting/{setting_id}/prompt-model",
        "/ai-settings/drafting/default/prompt-model",
        # K1b-1: 사업장(경로 넷, 동작 여섯) · 자산/시설 코드 목록(경로 넷, 동작 다섯)
        "/branches",
        "/branches/{branch_id}",
        "/branches/inventory",
        "/branches/delete",
        "/facility-codes",
        "/admin/facility-codes",
        "/admin/facility-codes/{code_id}",
        "/admin/facility-codes/delete",
    }
    assert client.get("/api/docs").status_code == 200


def test_request_bodies_have_no_tenant_or_user_field() -> None:
    """테넌트·사용자 ID 를 본문으로 받는 칸이 없다(계약으로 보인다)."""
    document: dict[str, Any] = json.loads(json.dumps(api.get_openapi_schema(path_prefix="")))
    schemas: dict[str, dict[str, Any]] = document["components"]["schemas"]
    for name in ("ExchangeIn", "SiteIn", "DocumentIn", "RunIn", "LoginIn", "RefreshIn", "PasswordChangeIn"):
        assert schemas[name]["additionalProperties"] is False
        properties: dict[str, Any] = schemas[name]["properties"]
        fields = {field.lower() for field in properties}
        assert not fields & {"tenantid", "tenant_id", "userid", "user_id", "role", "companyid", "company_id"}
    # 운영 관리자 전용 둘(K2c)은 대상 회사를 고르는 companyId 하나만 든다
    # (운영 관리자에게는 회사 범위가 없다 — 자기 회사를 본문으로 고르는 칸이 아니다). 그 밖의 테넌트·사용자·역할 칸은 0.
    for name in ("UserCreateIn", "PasswordResetIn"):
        assert schemas[name]["additionalProperties"] is False
        fields = {field.lower() for field in schemas[name]["properties"]}
        assert fields & {"tenantid", "tenant_id", "userid", "user_id", "role", "companyid", "company_id"} == {
            "companyid"
        }
        assert not fields & {"kind", "level", "isinitial"}


def test_the_scope3_latest_status_is_the_run_status_list(client: Client) -> None:
    """549 ⑤: inventory 는 runs.models 를 못 들인다(no-foreign-models) — 그 Literal 과 실행 상태를 여기서 묶는다."""
    schemas = client.get("/api/openapi.json").json()["components"]["schemas"]
    assert schemas["Scope3YearLatestOut"]["properties"]["status"]["enum"] == list(RUN_ROW_STATUSES)


def test_the_served_openapi_is_the_committed_one(client: Client) -> None:
    """런타임 문서(/api/openapi.json)가 generated/openapi.json 과 같다.

    ninja 는 문서 뷰에서 mount 자리(/api/)를 paths 키에 붙인다(config/api.py 의 _Api 가 막는다).
    붙으면 키가 /api/me 가 되고 Swagger 가 servers 와 겹쳐 /api/api/me 를 부른다."""
    served = client.get("/api/openapi.json")
    assert served.status_code == 200
    assert served.json() == json.loads(GENERATED.read_text())


def test_the_contract_says_the_mount_once_in_servers(client: Client) -> None:
    """접두는 servers 의 "/api" 한 곳에만 있다: paths 키에는 없다. 문서 화면은 그 문서(/api/openapi.json)를 읽는다."""
    document: dict[str, Any] = client.get("/api/openapi.json").json()
    assert document["servers"] == [{"url": "/api"}]
    assert [key for key in document["paths"] if key == "/api" or key.startswith("/api/")] == []
    assert "/api/openapi.json" in client.get("/api/docs").content.decode()


def test_committed_openapi_matches_the_code() -> None:
    """generated/openapi.json 은 커밋한 생성물이다. 경로를 고치고 scripts/gen-ts-types.sh 를 잊으면 여기서 걸린다."""
    current = json.loads(json.dumps(api.get_openapi_schema(path_prefix=""), sort_keys=True))
    assert json.loads(GENERATED.read_text()) == current, "scripts/gen-ts-types.sh 를 다시 돌린다"


def test_operation_ids_are_the_hand_written_table() -> None:
    """operationId 마흔다섯이 표와 글자까지 같다. ninja 가 모듈 경로로 지은 이름(`esgapi_…`)은 0 이다."""
    found = {key: operation["operationId"] for key, operation in _operations(_document()).items()}
    assert found == OPERATION_IDS
    assert len(found) == 167  # TR2 +1 · AD4S +1 · AD4D +1 · RF1 +1 · DV1e +1 · TR3a +2 · TR3b +3 · TR4 +7 · IR3b +1
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · S3D1 +1: Scope 3 데이터 엑셀
    # · S3K2b-2 +1: Scope 3 계수 수정
    # · IRS3 +3: 결과 고침 둘 · 고친 판 엑셀(③)
    # · DVA1 +7(found 둘 다)
    # · IR3c +1
    # · TRP6 +1
    # · TRS3 +1
    # · IRW2 +1
    # · IR4 +7(found 둘 다)
    # · K1b-1 +11(found 둘 다)
    # · K1b-2a +12(found 둘 다)
    # · S12a +10(found 둘 다)
    # · DVX1 +2(found 둘 다)
    # · RP1 +5(found 둘 다)
    # · RP2d +2(found 둘 다)
    # · RP2c +1(found 둘 다)
    # · RPS1 +1(found 둘 다)
    # · S12a-2 +3(found 둘 다)
    # · RPA1 +7(found 둘 다)
    # · S12a-3 +1(found 둘 다)
    # · S12b-1 +2(found 둘 다)
    # · S3K2a +3(found 둘 다)
    assert len(set(found.values())) == 167  # TR2 +1 · AD4S +1 · AD4D +1 · RF1 +1 · DV1e +1 · TR3a +2 · TR3b +3 · TR4 +7
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · S3D1 +1: Scope 3 데이터 엑셀
    # · S3K2b-2 +1: Scope 3 계수 수정
    # · IRS3 +3: 결과 고침 둘 · 고친 판 엑셀(③)
    # · IR3b +1
    # · IR3c +1
    # · TRP6 +1
    # · TRS3 +1
    # · S12a-2 +3
    # · S12a-3 +1
    # · S12b-1 +2
    # · S3K2a +3
    assert [name for name in found.values() if OPERATION_ID_SHAPE.fullmatch(name) is None] == []
    assert [name for name in found.values() if name.startswith("esgapi_")] == []


def test_an_operation_declares_413_exactly_when_it_takes_a_body() -> None:
    """본문을 받는 동작 ⇔ 413 을 선언한다(core.schemas.BODY_ERROR_RESPONSES). 양쪽 방향을 다 본다.

    본문이 있는데 413 이 없으면: 큰 본문에 실제로 413 이 나가는데 계약에 없다.
    본문이 없는데 413 이 있으면: 낼 길이 없는 답을 계약에 적은 것이다.
    """
    operations = _operations(_document())
    with_body = {key for key, operation in operations.items() if "requestBody" in operation}
    with_413 = {key for key, operation in operations.items() if "413" in operation["responses"]}
    assert with_body == with_413
    assert (len(operations), len(with_body)) == (167, 62)  # TR2 +1: GET /translation/runs/{run_id}/result · AD4S +1
    # · RM1c ③ +1(본문 없음): GET /runs/{run_id}/segments
    # · S3Q1 +1(본문 없음): GET /inventory/scope3/runs/{run_id}/original
    # · S3D1 +1(본문 없음): Scope 3 데이터 엑셀
    # · S3K2b-2 +1(본문 +1): Scope 3 계수 수정
    # · IRS3 +3(본문 +1 — POST …/result/edits · ③ GET …/report 는 본문 없음)
    # · AD4D +1 · RF1 +1 · DV1e +1(본문 없음)
    # · TR3a +2(본문 +1 — POST /translation/glossary/read 의 맨 바이트 xlsx)
    # · TR3b +3(본문 없음 — 묶음 목록·하나 보기·zip)
    # · TR4 +7(본문 +2 — POST /ai-settings/translation · PUT …/applied)
    # · DVA1 +7(본문 +2 — POST /ai-settings/dataverify · PUT …/applied)
    # · DV1g +1(본문 없음 — GET /dataverify/runs)
    # · IR3b +1(본문 없음 — GET /materiality/runs/{run_id}/result)
    # · IR3c +1(본문 없음 — GET /materiality/runs)
    # · TRP6 +1(본문 없음 — GET /translation/documents/{document_id}/pages)
    # · TRS3 +1(본문 없음 — GET /translation/runs/{run_id}/layout)
    # · IRW2 +1(본문 +1 — POST /materiality/value-chain/read 의 맨 바이트 xlsx)
    # · IR4 +7(본문 +2 — POST /ai-settings/materiality · PUT …/applied)
    # · K1b-1 +11(본문 +7 — 사업장 만들기·저장·토글·삭제, 코드 만들기·고침·삭제)
    # · K1b-2a +12(본문 +8 — 노드 만들기·이름·지우기, 잎 만들기·저장, 계수 만들기·고침·지우기)
    # · K1b-2b +2(본문 +1 — PUT /inventory/scope12/index-selections/{year})
    # · S12a +10(본문 +4 — 행 저장·행 지움·메모·자릿수)
    # · DVX1 +2(본문 +1 — POST /dataverify/edk/read 의 맨 바이트 xlsx)
    # · RP1 +5(본문 +3 — POST /drafting/projects · PUT …/document · PUT …/outline)
    # · RP2d +2(본문 없음 — GET /drafting/projects · GET …/runs/{run_id}/result.docx)
    # · RP2c +1(본문 없음 — GET /drafting/projects/{project_id}/outline/changes)
    # · RPS1 +1(본문 없음 — GET /drafting/projects/{project_id}/runs)
    # · S12a-2 +3(본문 +3 — PUT …/sites/{site_id}/period · PUT …/rows/{row_id}/factor · POST …/restore)
    # · RPA1 +7(본문 +2 — POST /ai-settings/drafting · PUT …/applied)
    # · S12a-3 +1(본문 없음 — GET /inventory/scope12/dashboard)
    # · S12b-1 +2(본문 없음 — GET …/years/{year}/template · …/export)
    # · S3K2a +3(본문 없음 — GET /inventory/scope3/years/{year} · POST·DELETE …/categories/{category}/lock)


# 토큰을 받는 동작(K2a — 처분 B4): refresh·revoke 는 본문의 refresh, /users/me* 와 운영 관리자 경로 여덟(K2c·UA1 의
# 사용자 관리 넷 + AU1a 의 감사 기록 조회 + AU1b-1 의 행위자 목록 + AU1b-2 의 실행 기록 둘)은 Bearer access.
USER_ADMIN_OPERATIONS: Final = frozenset(
    {
        ("get", "/users"),
        ("post", "/users"),
        ("post", "/users/{user_id}/password-reset"),
        ("patch", "/users/{user_id}"),
        ("get", "/audit-logs"),
        ("get", "/audit-logs/actors"),
        ("get", "/run-logs"),
        ("get", "/run-logs/metrics"),
        ("get", "/run-logs/export"),  # AD4S
        ("get", "/run-logs/{run_id}"),  # AD4D
        ("get", "/run-logs/{run_id}/files/{name}"),  # RF1
    }
)
# 그린워싱 AI 설정 판 다섯(G2c2 — 운영 관리자 Bearer). USER_ADMIN_OPERATIONS 의 「여덟」 셈과 따로 센다.
AI_SETTING_OPERATIONS: Final = frozenset(key for key in OPERATION_IDS if key[1].startswith("/ai-settings/"))
# K1b-1: 자산/시설 코드 목록 넷(운영 관리자 Bearer — /admin/facility-codes).
FACILITY_CODE_OPERATIONS: Final = frozenset(key for key in OPERATION_IDS if key[1].startswith("/admin/facility-codes"))
# K1b-1 의 열하나(organization_branches_* · organization_facility_codes_list · organization_admin_facility_codes_*).
# K1b-2a: 온실가스 풀 열둘(운영 관리자 Bearer — /inventory/admin/ghg-*).
GHG_POOL_OPERATIONS: Final = frozenset(key for key in OPERATION_IDS if key[1].startswith("/inventory/admin/ghg-"))
# K1b-2b: 고객사 인덱스 선택 둘(회사 경로 — 이름으로 적은 닫힌 집합).
INDEX_SELECTION_OPERATIONS: Final = frozenset(
    key
    for key, name in OPERATION_IDS.items()
    if name in {"inventory_scope12_index_tree", "inventory_scope12_index_selections_save"}
)
# S12a: Scope 1·2 입력 열(회사 경로 — 이름으로 적은 닫힌 집합. 풀기는 운영 관리자 칸이지만 같은 회사 인증).
ENTRY_OPERATIONS: Final = frozenset(
    key
    for key, name in OPERATION_IDS.items()
    if name
    in {
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
        "inventory_scope12_period_save",  # S12a-2
        "inventory_scope12_row_factor_save",  # S12a-2
        "inventory_scope12_history_restore",  # S12a-2
        "inventory_scope12_dashboard",  # S12a-3
        "inventory_scope12_template",  # S12b-1
        "inventory_scope12_export",  # S12b-1
        "inventory_scope12_upload",  # S12b-2
    }
)
# S3K1: Scope 3 코랩 둘(회사 경로 — 빈 양식·한 실행의 결과) · S3Q1 +1: 올린 원본.
SCOPE3_RUN_OPERATIONS: Final = frozenset(
    key
    for key, name in OPERATION_IDS.items()
    if name in {"inventory_scope3_template", "inventory_scope3_result_get", "inventory_scope3_original_get"}
)
# S3K2a: Scope 3 연도 상태·카테고리 잠금 셋(회사 경로 — 풀기도 같은 회사 인증) · S3D1 +1: 데이터 엑셀.
SCOPE3_STATE_OPERATIONS: Final = frozenset(
    key
    for key, name in OPERATION_IDS.items()
    if name
    in {"inventory_scope3_year_get", "inventory_scope3_lock", "inventory_scope3_unlock", "inventory_scope3_export"}
)
# S3K2b-1: Scope 3 줄 덧판 넷 · S3K2b-2 +1: 계수 수정(회사 경로).
SCOPE3_EDIT_OPERATIONS: Final = frozenset(
    key
    for key, name in OPERATION_IDS.items()
    if name
    in {
        "inventory_scope3_rows_exclude",
        "inventory_scope3_rows_restore",
        "inventory_scope3_edits_get",
        "inventory_scope3_history_get",
        "inventory_scope3_row_factor",
    }
)
ORGANIZATION_OPERATIONS: Final = frozenset(
    key for key, name in OPERATION_IDS.items() if name.startswith("organization_")
)
TOKEN_TAKERS: Final = frozenset(
    {("post", "/auth/refresh"), ("post", "/auth/revoke"), ("get", "/users/me"), ("post", "/users/me/password")}
    | USER_ADMIN_OPERATIONS
    | AI_SETTING_OPERATIONS
    | FACILITY_CODE_OPERATIONS
    | GHG_POOL_OPERATIONS
)


# 회사 경로(K2b — 사용자 결정 ㉠ Bearer 통일): Bearer 를 먼저, 머리가 없으면 옛 교환 쿠키. GET /me 만 쿠키뿐.
COMPANY_SECURITY: Final[list[dict[str, list[str]]]] = [{"CompanyScopedAuth": []}, {"SessionCookie": []}]


def test_444_is_declared_by_the_token_takers() -> None:
    """444(token_not_valid)를 선언한 동작 ⇔ 토큰을 받는 동작: K2a·K2c·UA1·AU1a·AU1b-1 의 열 + AU1b-2 의 둘
    + 회사 경로 27(K2b 24 + G1b-1 목록 하나 + X1b-2a 문서 둘).
    로그인·교환·로그아웃·상태 확인 둘·GET /me 는 444 를 선언하지 않는다."""
    operations = _operations(_document())
    company = {key for key, operation in operations.items() if operation.get("security") == COMPANY_SECURITY}
    assert len(company) == 95  # 분모: 쿠키 인증이던 회사 동작 25 에서 GET /me 하나를 뺀 것 + G1b-1 목록 줄 하나
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · S3D1 +1: Scope 3 데이터 엑셀
    # · S3K2b-2 +1: Scope 3 계수 수정
    # · IRS3 +3: 결과 고침 둘 · 고친 판 엑셀(③)
    # + X1b-2a 문서 둘(PATCH·원본)
    # + TR2 영문번역 결과 하나(GET /translation/runs/{run_id}/result)
    # + DV1e 데이터 검증 결과 하나(GET /dataverify/runs/{run_id}/result)
    # + TR3a 용어집 둘(POST /translation/glossary/read · GET /translation/glossary/template)
    # + TR3b 묶음 셋(GET /translation/batches · GET …/batches/{batch_key} · GET …/batches/{batch_key}/archive)
    # + IR3b 중대성평가 IRO 결과 하나(GET /materiality/runs/{run_id}/result)
    # + IR3c 중대성평가 IRO 목록 하나(GET /materiality/runs)
    # + TRP6 영문번역 문서 쪽 수 하나(GET /translation/documents/{document_id}/pages)
    # + TRS3 영문번역 layout 읽기 하나(GET /translation/runs/{run_id}/layout)
    # + IRW2 중대성평가 가치사슬 엑셀 읽기 하나(POST /materiality/value-chain/read)
    # + K1b-1 사업장 여섯·코드 목록 읽기 하나(옛 /sites 와 같은 인증)
    # + K1b-2b 고객사 인덱스 선택 둘(GET /inventory/scope12/index-tree · PUT …/index-selections/{year})
    # + S12a Scope 1·2 입력 열(/inventory/scope12/years·rows·years/{year}/… — 풀기도 같은 회사 인증)
    # + DVX1 데이터 검증 EDK 엑셀 둘(POST /dataverify/edk/read · GET /dataverify/edk/template)
    # + RP1 원고작성 다섯(/drafting — 프로젝트 넷·결과 하나)
    # + RP2d 원고작성 둘(GET /drafting/projects · GET /drafting/runs/{run_id}/result.docx)
    # + RP2c 원고작성 목차 차이 하나(GET /drafting/projects/{project_id}/outline/changes)
    # + RPS1 원고작성 프로젝트 실행 목록 하나(GET /drafting/projects/{project_id}/runs)
    # + S12a-2 Scope 1·2 셋(입력주기·행 계수 바꿈·복구 — 계수 바꿈도 같은 회사 인증)
    # + S12a-3 Scope 1·2 대시보드 하나(GET /inventory/scope12/dashboard)
    # + S12b-1 Scope 1·2 엑셀 둘(GET …/years/{year}/template · …/export)
    # + S3K2a Scope 3 연도 상태·잠금 셋(GET /inventory/scope3/years/{year} · POST·DELETE …/lock — 풀기도 회사 인증)
    assert ("get", "/me") not in company
    assert operations[("get", "/me")].get("security") == [{"SessionCookie": []}]
    with_444 = {key for key, operation in operations.items() if "444" in operation["responses"]}
    assert with_444 == TOKEN_TAKERS | company
    assert len(with_444) == 161  # G1b-1 +1: GET /greenwash/checks · G2c2 +5: AI 설정 판 · AS2a +2: prompt-model 둘
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · S3D1 +1: Scope 3 데이터 엑셀
    # · S3K2b-2 +1: Scope 3 계수 수정
    # · IRS3 +3: 결과 고침 둘 · 고친 판 엑셀(③)
    # · X1b-2a +2: PATCH /documents/{id}·GET /documents/{id}/file
    # · TR2 +1: GET /translation/runs/{run_id}/result
    # · AD4S +1: GET /run-logs/export
    # · AD4D +1: GET /run-logs/{run_id}
    # · RF1 +1: GET /run-logs/{run_id}/files/{name}
    # · DV1e +1: GET /dataverify/runs/{run_id}/result
    # · TR3a +2: POST /translation/glossary/read · GET /translation/glossary/template
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
    # · K1b-2b +2: /inventory/scope12 둘(회사 경로)
    # · S12a +10: /inventory/scope12 열(회사 경로)
    # · DVX1 +2: POST /dataverify/edk/read · GET /dataverify/edk/template
    # · RP1 +5: /drafting 다섯(회사 경로)
    # · RP2d +2: GET /drafting/projects · GET /drafting/runs/{run_id}/result.docx
    # · RP2c +1: GET /drafting/projects/{project_id}/outline/changes
    # · RPS1 +1: GET /drafting/projects/{project_id}/runs
    # · S12a-2 +3: /inventory/scope12 셋(회사 경로)
    # · RPA1 +7: /ai-settings/drafting 일곱
    # · S12a-3 +1: GET /inventory/scope12/dashboard
    # · S12b-1 +2: GET /inventory/scope12/years/{year}/template · …/export
    # · S3K2a +3: GET /inventory/scope3/years/{year} · POST·DELETE …/categories/{category}/lock
    bearer = {key for key, operation in operations.items() if operation.get("security") == [{"AccessTokenAuth": []}]}
    assert (
        bearer
        == {("get", "/users/me"), ("post", "/users/me/password")}
        | USER_ADMIN_OPERATIONS
        | AI_SETTING_OPERATIONS
        | FACILITY_CODE_OPERATIONS  # K1b-1
        | GHG_POOL_OPERATIONS  # K1b-2a
    )


def test_the_document_operations_require_the_session_cookie() -> None:
    """core 의 문서 경로 일곱은 config/api.py 가 꽂은 세션 인증을 계약에 드러낸다
    (core/service/apis/documents.py 는 auth= 를 적지 않는다).

    `add_router(…, auth=session_cookie)` 를 빼면 여기서 걸린다. 본문에는 이름·크기(와 계약 먼저의 두 칸)뿐이다
    (파일 바이트가 없다).
    """
    document = _document()
    operations = _operations(document)
    keys = [key for key in OPERATION_IDS if OPERATION_IDS[key].startswith("core_documents_")]
    assert len(keys) == 7
    for key in keys:
        assert operations[key].get("security") == COMPANY_SECURITY, key
    scheme = document["components"]["securitySchemes"]["SessionCookie"]
    assert (scheme["type"], scheme["in"], scheme["name"]) == ("apiKey", "cookie", "esg_session")
    # 본문을 받는 것은 만들기와 고치기(PATCH — X1b-2a)이고 꼴은 JSON 이다. 올림 확인에는 본문이 없다.
    assert [key for key in keys if "requestBody" in operations[key]] == [
        ("post", "/documents"),
        ("patch", "/documents/{document_id}"),
    ]
    body = operations[("post", "/documents")]["requestBody"]["content"]
    assert list(body) == ["application/json"]
    assert set(document["components"]["schemas"]["DocumentIn"]["properties"]) == {
        "fileName",
        "sizeBytes",
        "reportYear",
        "previousDocumentId",
    }
    # 응답의 문서에는 저장소의 자리·테넌트·올린 사람이 없고, 일감에는 임대 기한이 없다.
    schemas = document["components"]["schemas"]
    assert set(schemas["DocumentOut"]["properties"]) == {
        "id",
        "fileName",
        "status",
        "sizeBytes",
        "etag",
        "createdAt",
        "uploadedAt",
        "reportYear",
        "previousDocumentId",
        "pageCount",
        "hasText",
    }
    # 원본 내려받기(X1b-2a)의 성공 응답은 PDF 바이트다(JSON 이 아니다).
    original = operations[("get", "/documents/{document_id}/file")]["responses"]["200"]["content"]
    assert original == {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}
    assert set(schemas["JobOut"]["properties"]) == {
        "id",
        "kind",
        "status",
        "attempts",
        "errorCode",
        "errorMessage",
        "summary",
        "createdAt",
        "finishedAt",
    }


def test_committed_types_were_generated_from_the_committed_openapi() -> None:
    """generated/api.d.ts 를 만든 openapi.json 의 sha256 이 지금 것과 같다(scripts/gen-ts-types.sh 가 적어 둔다).

    잡는 것: openapi.json 만 다시 만들고 api.d.ts 를 잊은 것(네트워크 없이 잰다).
    못 잡는 것: api.d.ts 를 손으로 고친 것, 적힌 값을 손으로 맞춘 것.
    """
    assert hashlib.sha256(GENERATED.read_bytes()).hexdigest() == TYPES_SOURCE_HASH.read_text().strip(), (
        "scripts/gen-ts-types.sh 를 다시 돌린다"
    )


def test_the_body_limit_is_the_django_default_written_down() -> None:
    """본문 상한은 Django 의 기본값을 우리 설정에 그대로 적은 것이다(값을 고르지 않았다).

    넘으면 413 `body_too_large` 다. 그것은 업무 층이 잰다(inventory·accounts 의 test_api.py).
    """
    assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE == global_settings.DATA_UPLOAD_MAX_MEMORY_SIZE == 2_621_440


# ── 계약 먼저(밴드 XC): 실행 넷과 문서 목록·판 사슬. 몸은 501 이고 꼴만 계약이다 ──
# 정본은 이 표와 generated/openapi.json 이다(프론트에 넘기는 「계약 한 장」). 칸을 빼거나 더하면 여기서 걸린다.

NEW_OPERATIONS = {key for key, name in OPERATION_IDS.items() if name.startswith("runs_")} | {
    ("get", "/documents"),
    ("get", "/documents/{document_id}/versions"),
}
# 아직 501 을 선언하는 것: 없다. 실행의 나머지 셋은 X1b-1, 문서 둘은 X1b-2a, 실행 만들기의 resumeFromRunId 는
# X1b-2b 가 몸을 채웠다. 이름은 남긴다(새 동작이 501 로 들어오면 여기에 적는다).
STILL_501: set[tuple[str, str]] = set()
# X1b-2a 가 더한 문서 동작 둘(XC 의 「새 여섯」 밖 — 열일곱의 셈에서 따로 뺀다). 원본은 application/pdf 라
# RUN_CONTRACT 의 binary(octet-stream) 꼴에 넣지 않는다 — 꼴은 test_the_document_operations_require_the_session_cookie
# 가 본다.
DOCUMENT_BODY_OPERATIONS: Final = frozenset(
    {("patch", "/documents/{document_id}"), ("get", "/documents/{document_id}/file")}
)
# TR2·TRP6·TRS3 가 더한 영문번역 결과·문서 쪽 수·layout 경로 셋(열일곱의 셈에서 따로 뺀다).
TRANSLATION_OPERATIONS: Final = frozenset(
    {("get", "/translation/runs/{run_id}/result"), ("get", "/translation/documents/{document_id}/pages")}
) | frozenset({("get", "/translation/runs/{run_id}/layout")})
# DV1e·DV1g·DVX1 이 더한 데이터 검증 결과·목록·EDK 엑셀 읽기·양식 경로 넷(같은 까닭으로 따로 뺀다).
DATAVERIFY_OPERATIONS: Final = frozenset(
    {
        ("get", "/dataverify/runs/{run_id}/result"),
        ("get", "/dataverify/runs"),
        ("post", "/dataverify/edk/read"),
        ("get", "/dataverify/edk/template"),
    }
)
# IR3b·IR3c·IRW2 가 더한 중대성평가 IRO 결과·목록·가치사슬 읽기 경로 셋(같은 까닭으로 따로 뺀다).
MATERIALITY_OPERATIONS: Final = frozenset(
    {
        ("get", "/materiality/runs/{run_id}/result"),
        ("get", "/materiality/runs"),
        ("post", "/materiality/value-chain/read"),
        ("get", "/materiality/runs/{run_id}/result/edits"),  # IRS3 ②
        ("post", "/materiality/runs/{run_id}/result/edits"),
        ("get", "/materiality/runs/{run_id}/report"),  # IRS3 ③
    }
)
# RP1 이 더한 원고작성 경로 다섯 + RP2d 둘 + RP2c 하나(같은 까닭으로 따로 뺀다).
DRAFTING_OPERATIONS: Final = frozenset(
    {
        ("post", "/drafting/projects"),
        ("get", "/drafting/projects/{project_id}"),
        ("put", "/drafting/projects/{project_id}/document"),
        ("put", "/drafting/projects/{project_id}/outline"),
        ("get", "/drafting/runs/{run_id}/result"),
        ("get", "/drafting/projects"),  # RP2d
        ("get", "/drafting/runs/{run_id}/result.docx"),  # RP2d
        ("get", "/drafting/projects/{project_id}/outline/changes"),  # RP2c
        ("get", "/drafting/projects/{project_id}/runs"),  # RPS1
    }
)
# TR3a 가 더한 용어집 경로 둘(같은 까닭으로 따로 뺀다).
GLOSSARY_OPERATIONS: Final = frozenset(
    {("post", "/translation/glossary/read"), ("get", "/translation/glossary/template")}
)
# TR3b 가 더한 묶음 경로(같은 까닭으로 따로 뺀다).
BATCH_OPERATIONS: Final = frozenset(
    {
        ("get", "/translation/batches"),
        ("get", "/translation/documents/{document_id}/batches/{batch_key}"),
        ("get", "/translation/documents/{document_id}/batches/{batch_key}/archive"),
    }
)
# (메서드, 경로) → (경로 인자 {이름: 타입}, 쿼리 인자, 성공 상태, 성공 응답의 꼴, 404 를 선언하나)
#   꼴: "$<스키마>" 는 그 스키마 하나, "[]<스키마>" 는 그 스키마의 배열, "binary" 는 application/octet-stream
RUN_CONTRACT: dict[tuple[str, str], tuple[dict[str, str], set[str], str, str, bool]] = {
    ("post", "/runs"): ({}, set(), "201", "$RunCreatedOut", True),  # X1b-1: 남의·없는 문서 → 404
    ("get", "/runs"): ({}, {"module", "status", "documentId", "limit", "offset"}, "200", "$RunPageOut", False),
    ("get", "/runs/{run_id}"): ({"run_id": "integer"}, set(), "200", "$RunOut", True),
    ("get", "/runs/{run_id}/files/{name}"): ({"run_id": "integer", "name": "string"}, set(), "200", "binary", True),
    # RM1c ③: 구획 목록(data 0)
    ("get", "/runs/{run_id}/segments"): (
        {"run_id": "integer"},
        {"step", "status", "limit", "offset"},
        "200",
        "$RunSegmentPageOut",
        True,
    ),
    ("get", "/documents"): (
        {},
        {"reportYear", "q", "uploadedBy", "latestOnly", "limit", "offset"},
        "200",
        "$DocumentPageOut",
        False,
    ),
    ("get", "/documents/{document_id}/versions"): ({"document_id": "integer"}, set(), "200", "[]DocumentOut", True),
}
RUN_OUT_FIELDS = {
    "id",
    "module",
    "flowId",
    "documentId",
    "options",
    "status",
    "steps",
    "createdAt",
    "startedAt",
    "finishedAt",
    "failedStep",
    "errorCode",
    "errorMessage",
    "resultShapes",
    "files",
    "resumedFromRunId",
}
# RM1c ③: 구획 목록의 한 줄 — data(산출) 칸이 없다
RUN_SEGMENT_FIELDS = {
    "position",
    "keySha256",
    "key",
    "status",
    "attempts",
    "errorCode",
    "startedAt",
    "finishedAt",
}
DOCUMENT_ITEM_FIELDS = {
    "id",
    "fileName",
    "status",
    "sizeBytes",
    "etag",
    "createdAt",
    "uploadedAt",
    "reportYear",
    "previousDocumentId",
    "pageCount",
    "hasText",
    "uploadedBy",
}
# 스키마 → (칸 전부, required). 응답 꼴은 칸 전부가 required 다(null 이어도 칸은 온다).
RUN_SCHEMAS: dict[str, tuple[set[str], set[str]]] = {
    "RunIn": (
        {"module", "flowId", "documentId", "options", "resumeFromRunId", "launchKey", "retrySegments"},  # RM1c ③ +1
        {"module"},  # ND1: documentId 는 문서 요구 흐름만(없으면 422 DOCUMENT_REQUIRED)
    ),
    "RunCreatedOut": ({"id", "status"}, {"id", "status"}),
    "RunPageOut": ({"count", "isNext", "results"}, {"count", "isNext", "results"}),
    "RunSummaryOut": (
        {"id", "module", "flowId", "documentId", "documentName", "status", "createdAt", "finishedAt"},
        {"id", "module", "flowId", "documentId", "documentName", "status", "createdAt", "finishedAt"},
    ),
    "RunOut": (
        RUN_OUT_FIELDS,
        RUN_OUT_FIELDS,
    ),
    "RunStepOut": ({"step", "status", "done", "total", "segments"}, {"step", "status", "done", "total"}),
    # RM1b
    "RunStepSegmentsOut": (
        {"planned", "pending", "running", "done", "failed", "firstStartedAt", "lastFinishedAt"},
        {"planned", "pending", "running", "done", "failed", "firstStartedAt", "lastFinishedAt"},
    ),
    # RM1c ③
    "RunRetrySegmentsIn": ({"fromRunId", "step", "keys"}, {"fromRunId", "step", "keys"}),
    "RunSegmentPageOut": ({"count", "isNext", "results"}, {"count", "isNext", "results"}),
    "RunSegmentOut": (RUN_SEGMENT_FIELDS, RUN_SEGMENT_FIELDS),
    "RunSegmentKeyOut": (
        {"kind", "span", "documentSha256", "parserVersion"},
        {"kind", "span", "documentSha256", "parserVersion"},
    ),
    "DocumentPageOut": ({"count", "isNext", "results"}, {"count", "isNext", "results"}),
    "DocumentListItemOut": (
        DOCUMENT_ITEM_FIELDS,
        DOCUMENT_ITEM_FIELDS,
    ),
}
RUN_STATUSES = ["queued", "processing", "done", "failed"]
RUN_STEP_STATUSES = ["pending", "running", "done", "failed"]


def _types(field: dict[str, Any]) -> set[str]:
    """칸의 타입(nullable 이면 anyOf 안의 null 밖의 것)."""
    options: list[dict[str, Any]] = field.get("anyOf", [field])
    return {option["type"] for option in options if option.get("type") != "null"}


def _formats(field: dict[str, Any]) -> set[str | None]:
    options: list[dict[str, Any]] = field.get("anyOf", [field])
    return {option.get("format") for option in options if option.get("type") != "null"}


def test_the_run_and_version_operations_are_the_contract_sheet() -> None:
    """새 동작 여섯의 경로·인자·응답과 그 꼴들이 「계약 한 장」(RUN_CONTRACT·RUN_SCHEMAS)과 같다."""
    document = _document()
    operations = _operations(document)
    schemas: dict[str, dict[str, Any]] = document["components"]["schemas"]
    assert set(RUN_CONTRACT) == NEW_OPERATIONS
    for key, (path_params, query_params, success, shape, with_404) in RUN_CONTRACT.items():
        operation = operations[key]
        assert operation.get("security") == COMPANY_SECURITY, key
        parameters: list[dict[str, Any]] = operation.get("parameters", [])
        assert {p["name"]: p["schema"]["type"] for p in parameters if p["in"] == "path"} == path_params, key
        assert {p["name"] for p in parameters if p["in"] == "query"} == query_params, key
        responses: dict[str, Any] = operation["responses"]
        assert {success} <= set(responses), key
        assert ("501" in responses) is (key in STILL_501), key  # X1b-1: 몸이 선 셋은 501 을 걷었다
        assert ("404" in responses) is with_404, key
        if key in STILL_501:
            assert responses["501"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorBody"), key
        content: dict[str, Any] = responses[success]["content"]
        if shape == "binary":
            assert content == {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}, key
        elif shape.startswith("[]"):
            assert content["application/json"]["schema"]["items"]["$ref"].endswith("/" + shape[2:]), key
        else:
            assert content["application/json"]["schema"]["$ref"].endswith("/" + shape[1:]), key
    # 쿼리: limit 은 1~100(기본 20), offset 은 0 이상. 실행 상태로 거르는 칸은 상태의 글자 넷이다.
    for key in (("get", "/runs"), ("get", "/documents"), ("get", "/users"), ("get", "/runs/{run_id}/segments")):
        query = {p["name"]: p["schema"] for p in operations[key]["parameters"]}
        assert (query["limit"]["minimum"], query["limit"]["maximum"], query["limit"]["default"]) == (1, 100, 20)
        assert (query["offset"]["minimum"], query["offset"]["default"]) == (0, 0)
    status_query = {p["name"]: p["schema"] for p in operations[("get", "/runs")]["parameters"]}["status"]
    assert [option.get("enum") for option in status_query["anyOf"] if "enum" in option] == [RUN_STATUSES]
    # 머리 매개변수: runs_create 의 선택 Idempotency-Key(IK1 — 소문자 UUID) 하나뿐, 다른 동작은 0
    headers = {
        key: {p["name"]: p["required"] for p in op.get("parameters", []) if p["in"] == "header"}
        for key, op in operations.items()
    }
    assert {key: found for key, found in headers.items() if found} == {("post", "/runs"): {"Idempotency-Key": False}}

    for name, (fields, required) in RUN_SCHEMAS.items():
        assert set(schemas[name]["properties"]) == fields, name
        assert set(schemas[name].get("required", [])) == required, name
    for name in ("RunCreatedOut", "RunSummaryOut", "RunOut"):
        assert schemas[name]["properties"]["status"]["enum"] == RUN_STATUSES, name
    assert schemas["RunStepOut"]["properties"]["status"]["enum"] == RUN_STEP_STATUSES
    assert schemas["RunIn"]["additionalProperties"] is False
    # RM1c ③: 고른 구획 열쇠 — sha256 16진 64자, 1~10,000개(FanoutStep 상한). 구획 상태는 단계 상태와 같은 넷
    retry_keys = schemas["RunRetrySegmentsIn"]["properties"]["keys"]
    assert (retry_keys["items"]["pattern"], retry_keys["minItems"], retry_keys["maxItems"]) == (
        "^[0-9a-f]{64}$",
        1,
        10_000,
    )
    assert schemas["RunRetrySegmentsIn"]["additionalProperties"] is False
    assert schemas["RunSegmentOut"]["properties"]["status"]["enum"] == RUN_STEP_STATUSES
    assert schemas["RunIn"]["properties"]["options"]["type"] == "object"
    # module·flowId 의 무늬 = 흐름 레지스트리의 무늬(^…$ 를 붙인 것).
    assert schemas["RunIn"]["properties"]["module"]["pattern"] == f"^{MODULE_ID.pattern}$"
    flow_id = schemas["RunIn"]["properties"]["flowId"]
    assert [option.get("pattern") for option in flow_id["anyOf"] if "pattern" in option] == [
        f"^{VERSIONED_ID.pattern}$"
    ]

    # 칸의 타입: `id`·`…Id` 는 integer(문서·일감 id 도 — K1u-b, 처분 1 ㉠), `…At` 는 date-time.
    for name in [*RUN_SCHEMAS, "DocumentOut", "DocumentIn", "DocumentPatchIn", "JobOut"]:
        for field, spec in schemas[name]["properties"].items():
            where = f"{name}.{field}"
            if field == "id" or field.endswith("Id"):
                if field == "flowId":
                    assert _types(spec) == {"string"}, where  # 흐름 id@판 은 글자다
                else:
                    assert _types(spec) == {"integer"}, where
            if field.endswith("At"):
                assert (_types(spec), _formats(spec)) == ({"string"}, {"date-time"}), where


# 그린워싱 계약(GC1, 비교만 501). 꼴은 esgapi/greenwash/tests/contracts/test_contracts_shapes_paths.py 가 못 박는다.
# 로그인 다섯(밴드 K2a)은 「XC·GC1 밖」 열일곱의 셈에서 뺀다(그 열일곱은 XC 전의 기존 동작이다).
# 사용자 관리 셋(밴드 K2c)은 이름 붙은 집합(USER_ADMIN_OPERATIONS)으로 따로 뺀다.
LOGIN_OPERATIONS: Final = frozenset(
    key for key, name in OPERATION_IDS.items() if name.startswith("user_") and key not in USER_ADMIN_OPERATIONS
)
GREENWASH_CONTRACT_OPERATIONS: Final = frozenset(key for key in OPERATION_IDS if key[1].startswith("/greenwash/"))
# G1b-1 이 몸을 채운 셋(501 걷음). 남는 그린워싱 501 = 비교(G1b-2).
GREENWASH_BODIED: Final = frozenset(
    {
        ("get", "/greenwash/runs/{run_id}/result"),
        ("get", "/greenwash/runs/{run_id}/result2"),
        ("get", "/greenwash/runs/{run_id}/review"),
        ("put", "/greenwash/runs/{run_id}/review"),
        ("post", "/greenwash/runs/{run_id}/items/{item_index}/rejudge"),  # 재판단 만들기(GRJ1 — 처음부터 몸)
        ("get", "/greenwash/checks"),  # 목록 줄(G1b-1 ③ — 처음부터 몸)
        ("get", "/greenwash/runs/{run_id}/report"),  # 엑셀 보고서(G1b-2a)
    }
)


def test_existing_operations_only_gained() -> None:
    """501 을 선언한 것은 그린워싱 비교 하나(결과·검토 셋은 G1b-1, 보고서는 G1b-2a)뿐이다(새 여섯은 X1b-1·X1b-2a·
    X1b-2b 가 몸을 채웠다 — 실행 만들기의 501 은 X1b-2b, 문서 만들기의 501 은 X1b-2a 가 걷었다).
    기존 열일곱의 나머지 꼴은 바이트 대조(scripts/section4-XC.sh 의 「더하기만」)가 기준 커밋의 openapi 와 견준다."""
    operations = _operations(_document())
    with_501 = {key for key, operation in operations.items() if "501" in operation["responses"]}
    assert len(GREENWASH_CONTRACT_OPERATIONS) == 9  # GRJ1 +1: 재판단 만들기 · GE1b +1: 2차 결과
    assert with_501 == (
        STILL_501 | (GREENWASH_CONTRACT_OPERATIONS - {("get", "/greenwash/terms/default")} - GREENWASH_BODIED)
    )
    assert len(LOGIN_OPERATIONS) == 5
    assert len(USER_ADMIN_OPERATIONS) == 11  # AD4S +1 · AD4D +1 · RF1 +1
    assert len(AI_SETTING_OPERATIONS) == 35  # G2c2 · AS2a +2 · TR4 +7 · DVA1 +7 · IR4 +7 · RPA1 +7
    assert len(TRANSLATION_OPERATIONS) == 3  # TR2 · TRP6 · TRS3
    assert len(DATAVERIFY_OPERATIONS) == 4  # DV1e · DV1g · DVX1 +2
    assert len(MATERIALITY_OPERATIONS) == 6  # IR3b · IR3c · IRW2 · IRS3 +3
    assert len(DRAFTING_OPERATIONS) == 9  # RP1 · RP2d +2 · RP2c +1 · RPS1 +1
    assert len(GLOSSARY_OPERATIONS) == 2  # TR3a
    assert len(BATCH_OPERATIONS) == 3  # TR3b
    assert len(ORGANIZATION_OPERATIONS) == 11  # K1b-1: 사업장 여섯 · 코드 목록 다섯
    assert len(GHG_POOL_OPERATIONS) == 12  # K1b-2a: 온실가스 풀 열둘
    assert len(INDEX_SELECTION_OPERATIONS) == 2  # K1b-2b: 고객사 인덱스 선택 둘
    assert len(ENTRY_OPERATIONS) == 17  # S12a: Scope 1·2 입력 열
    # · S12a-2 +3: 입력주기·행 계수 바꿈·복구
    # · S12a-3 +1: 대시보드
    # · S12b-1 +2: 엑셀 내려받기 둘
    # · S12b-2 +1: 일괄 올리기
    assert len(SCOPE3_RUN_OPERATIONS) == 3  # S3K1: Scope 3 빈 양식·결과
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    assert len(SCOPE3_STATE_OPERATIONS) == 4  # S3K2a: Scope 3 연도 상태·잠그기·풀기 · S3D1 +1: 데이터 엑셀
    assert len(SCOPE3_EDIT_OPERATIONS) == 5  # S3K2b-1: Scope 3 줄 덧판 넷 · S3K2b-2 +1
    assert (
        len(OPERATION_IDS)
        - len(NEW_OPERATIONS)
        - len(GREENWASH_CONTRACT_OPERATIONS)
        - len(LOGIN_OPERATIONS)
        - len(USER_ADMIN_OPERATIONS)
        - len(DOCUMENT_BODY_OPERATIONS)
        - len(AI_SETTING_OPERATIONS)
        - len(TRANSLATION_OPERATIONS)
        - len(DATAVERIFY_OPERATIONS)
        - len(MATERIALITY_OPERATIONS)
        - len(DRAFTING_OPERATIONS)
        - len(GLOSSARY_OPERATIONS)
        - len(BATCH_OPERATIONS)
        - len(ORGANIZATION_OPERATIONS)
        - len(GHG_POOL_OPERATIONS)
        - len(INDEX_SELECTION_OPERATIONS)
        - len(ENTRY_OPERATIONS)
        - len(SCOPE3_RUN_OPERATIONS)
        - len(SCOPE3_STATE_OPERATIONS)
        - len(SCOPE3_EDIT_OPERATIONS)
        == 17
    )


# ── 응답 코드의 집합과 실행 꼴의 칸 타입(MARC-ISSUE-95 (1)(2), X1b-1 처분 ⑮) ──
# 동작마다 선언한 응답 코드 전부. 기준은 X1b-1 BASE(da0fa43)의 openapi 에 X1b-1 의 넷(runs_list·runs_get·
# runs_file_get 의 501 걷음, runs_create 의 404 더함)을 얹은 것이다(X1b-2a: 문서 셋의 501 걷음, 새 동작 둘).
# 바뀌면 「뜻한 바뀜」인지 사람이 보고 이 표를 같이 고친다.
RESPONSE_CODES: Final[dict[str, str]] = {
    "accounts_auth_exchange": "200 400 401 403 409 413 422 500 503",
    "accounts_auth_logout": "204",
    "accounts_me": "200 400 401 403 409 422 500 503",
    "accounts_sites_create": "201 400 401 403 409 413 422 444 500 503",
    "accounts_sites_list": "200 400 401 403 409 422 444 500 503",
    "config_healthz": "200",
    "config_readyz": "200 503",
    "core_documents_confirm": "200 400 401 403 404 409 422 444 500 503",
    "core_documents_create": "201 400 401 403 409 413 422 444 500 503",
    "core_documents_file_get": "200 400 401 403 404 409 422 444 500 503",
    "core_documents_get": "200 400 401 403 404 409 422 444 500 503",
    "core_documents_list": "200 400 401 403 409 422 444 500 503",
    "core_documents_update": "200 400 401 403 404 409 413 422 444 500 503",
    "core_documents_versions": "200 400 401 403 404 409 422 444 500 503",
    "dataverify_result_get": "200 400 401 403 404 409 422 444 500 503",
    "dataverify_runs_list": "200 400 401 403 409 422 444 500 503",
    "dataverify_edk_read": "200 400 401 403 409 413 422 444 500 503",
    "dataverify_edk_template": "200 400 401 403 409 422 444 500 503",
    "greenwash_compare_get": "200 400 401 403 404 409 422 444 500 501 503",
    "greenwash_report_get": "200 400 401 403 404 409 422 444 500 503",
    "greenwash_result_get": "200 400 401 403 404 409 422 444 500 503",
    "greenwash_result2_get": "200 400 401 403 404 409 422 444 500 503",
    "greenwash_review_get": "200 400 401 403 404 409 422 444 500 503",
    "greenwash_review_put": "200 400 401 403 404 409 413 422 444 500 503",
    "greenwash_item_rejudge": "202 400 401 403 404 409 422 444 500 503",  # GRJ1
    "greenwash_terms_default": "200 400 401 403 409 422 444 500 503",
    "greenwash_checks_get": "200 400 401 403 409 422 444 500 503",
    "translation_result_get": "200 400 401 403 404 409 422 444 500 503",
    "translation_layout_get": "200 400 401 403 404 409 422 444 500 503",
    "translation_glossary_read": "200 400 401 403 409 413 422 444 500 503",
    "translation_glossary_template": "200 400 401 403 409 422 444 500 503",
    "translation_batches_list": "200 400 401 403 409 422 444 500 503",
    "translation_batch_get": "200 400 401 403 404 409 422 444 500 503",
    "translation_batch_archive": "200 400 401 403 404 409 422 444 500 503",
    "translation_document_pages": "200 400 401 403 404 409 422 444 500 503",
    "inventory_calc": "200 400 401 403 409 413 422 444 500 503",
    "inventory_scope3_classify": "200 400 401 403 409 413 422 444 500 503",
    "inventory_scope3_shortlist": "200 400 401 403 409 413 422 444 500 503",
    "materiality_result_get": "200 400 401 403 404 409 422 444 500 503",
    "materiality_runs_list": "200 400 401 403 409 422 444 500 503",
    "materiality_value_chain_read": "200 400 401 403 409 413 422 444 500 503",
    "materiality_result_edits_get": "200 400 401 403 404 409 422 444 500 503",  # IRS3 ②
    "materiality_result_edits_post": "200 400 401 403 404 409 413 422 444 500 503",
    "materiality_report_get": "200 400 401 403 404 409 422 444 500 503",  # IRS3 ③
    "drafting_projects_create": "201 400 401 403 409 413 422 444 500 503",
    "drafting_project_get": "200 400 401 403 404 409 422 444 500 503",
    "drafting_project_document_put": "200 400 401 403 404 409 413 422 444 500 503",
    "drafting_outline_put": "200 400 401 403 404 409 413 422 444 500 503",
    "drafting_result_get": "200 400 401 403 404 409 422 444 500 503",
    "drafting_projects_list": "200 400 401 403 409 422 444 500 503",  # RP2d
    "drafting_result_download": "200 400 401 403 404 409 422 444 500 503",  # RP2d
    "drafting_outline_changes": "200 400 401 403 404 409 422 444 500 503",  # RP2c
    "drafting_project_runs": "200 400 401 403 404 409 422 444 500 503",  # RPS1
    "reference_assemble": "200 400 401 403 409 413 422 444 500 503",
    "reference_assemble_electricity": "200 400 401 403 409 413 422 444 500 503",
    "reference_factors": "200 400 401 403 409 422 444 500 503",
    "reference_sources": "200 400 401 403 409 422 444 500 503",
    "runs_create": "201 400 401 403 404 409 413 422 444 500 503",
    "runs_file_get": "200 400 401 403 404 409 422 444 500 503",
    "runs_segments_list": "200 400 401 403 404 409 422 444 500 503",  # RM1c ③
    "runs_get": "200 400 401 403 404 409 422 444 500 503",
    "runs_list": "200 400 401 403 409 422 444 500 503",
    "user_audit_actors": "200 400 401 403 404 409 422 444 500 503",
    "user_audit_list": "200 400 401 403 404 409 422 444 500 503",
    "user_auth_login": "200 400 401 403 409 413 422 500 503",
    "user_auth_refresh": "200 400 401 403 409 413 422 444 500 503",
    "user_auth_revoke": "204 400 401 403 409 413 422 444 500 503",
    "user_create": "201 400 401 403 404 409 413 422 444 500 503",
    "user_list": "200 400 401 403 404 409 422 444 500 503",
    "user_me": "200 400 401 403 409 422 444 500 503",
    "user_password_change": "200 400 401 403 409 413 422 444 500 503",
    "user_password_reset": "200 400 401 403 404 409 413 422 444 500 503",
    "user_run_log_list": "200 400 401 403 404 409 422 444 500 503",
    "user_run_log_metrics": "200 400 401 403 404 409 422 444 500 503",
    "user_run_log_export": "200 400 401 403 404 409 422 444 500 503",  # AD4S(409 = 상한)
    "user_run_log_get": "200 400 401 403 404 409 422 444 500 503",  # AD4D
    "user_run_log_file_get": "200 400 401 403 404 409 422 444 500 503",  # RF1(200 은 이진)
    # G2c2: 그린워싱 AI 설정 판 다섯(운영 관리자 Bearer — 기본 판은 회사를 고르지 않아 404 없음)
    "greenwash_ai_setting_list": "200 400 401 403 404 409 422 444 500 503",
    "greenwash_ai_setting_default": "200 400 401 403 409 422 444 500 503",
    "greenwash_ai_setting_get": "200 400 401 403 404 409 422 444 500 503",
    "greenwash_ai_setting_create": "201 400 401 403 404 409 413 422 444 500 503",
    "greenwash_ai_setting_apply": "200 400 401 403 404 409 413 422 444 500 503",
    # AS2a: 프롬프트·모델 읽기 둘(기본 판은 회사를 고르지 않아 404 없음)
    "greenwash_ai_setting_prompt_model": "200 400 401 403 404 409 422 444 500 503",
    "greenwash_ai_setting_default_prompt_model": "200 400 401 403 409 422 444 500 503",
    # TR4: 영문번역 AI 설정 판 일곱(그린워싱과 같은 꼴 — 기본 판 둘은 회사를 고르지 않아 404 없음)
    "translation_ai_setting_list": "200 400 401 403 404 409 422 444 500 503",
    "translation_ai_setting_default": "200 400 401 403 409 422 444 500 503",
    "translation_ai_setting_get": "200 400 401 403 404 409 422 444 500 503",
    "translation_ai_setting_create": "201 400 401 403 404 409 413 422 444 500 503",
    "translation_ai_setting_apply": "200 400 401 403 404 409 413 422 444 500 503",
    "translation_ai_setting_prompt_model": "200 400 401 403 404 409 422 444 500 503",
    "translation_ai_setting_default_prompt_model": "200 400 401 403 409 422 444 500 503",
    # DVA1: 데이터 검증 AI 설정 판 일곱(영문번역과 같은 꼴)
    "dataverify_ai_setting_list": "200 400 401 403 404 409 422 444 500 503",
    "dataverify_ai_setting_default": "200 400 401 403 409 422 444 500 503",
    "dataverify_ai_setting_get": "200 400 401 403 404 409 422 444 500 503",
    "dataverify_ai_setting_create": "201 400 401 403 404 409 413 422 444 500 503",
    "dataverify_ai_setting_apply": "200 400 401 403 404 409 413 422 444 500 503",
    "dataverify_ai_setting_prompt_model": "200 400 401 403 404 409 422 444 500 503",
    "dataverify_ai_setting_default_prompt_model": "200 400 401 403 409 422 444 500 503",
    # IR4: 중대성평가 IRO AI 설정 판 일곱(데이터 검증과 같은 꼴)
    "materiality_ai_setting_list": "200 400 401 403 404 409 422 444 500 503",
    "materiality_ai_setting_default": "200 400 401 403 409 422 444 500 503",
    "materiality_ai_setting_get": "200 400 401 403 404 409 422 444 500 503",
    "materiality_ai_setting_create": "201 400 401 403 404 409 413 422 444 500 503",
    "materiality_ai_setting_apply": "200 400 401 403 404 409 413 422 444 500 503",
    "materiality_ai_setting_prompt_model": "200 400 401 403 404 409 422 444 500 503",
    "materiality_ai_setting_default_prompt_model": "200 400 401 403 409 422 444 500 503",
    # RPA1: 원고작성 AI 설정 판 일곱(중대성평가 IRO 와 같은 꼴)
    "drafting_ai_setting_list": "200 400 401 403 404 409 422 444 500 503",
    "drafting_ai_setting_default": "200 400 401 403 409 422 444 500 503",
    "drafting_ai_setting_get": "200 400 401 403 404 409 422 444 500 503",
    "drafting_ai_setting_create": "201 400 401 403 404 409 413 422 444 500 503",
    "drafting_ai_setting_apply": "200 400 401 403 404 409 413 422 444 500 503",
    "drafting_ai_setting_prompt_model": "200 400 401 403 404 409 422 444 500 503",
    "drafting_ai_setting_default_prompt_model": "200 400 401 403 409 422 444 500 503",
    "user_update": "200 400 401 403 404 409 413 422 444 500 503",
    # K1b-1: 404 는 없는·남의 회사·삭제된 id 를 받는 일곱(목록·코드 목록 읽기·코드 만들기는 404 없음)
    "organization_branches_list": "200 400 401 403 409 422 444 500 503",
    "organization_branches_get": "200 400 401 403 404 409 422 444 500 503",
    "organization_branches_create": "201 400 401 403 404 409 413 422 444 500 503",
    "organization_branches_save": "200 400 401 403 404 409 413 422 444 500 503",
    "organization_branches_inventory": "200 400 401 403 404 409 413 422 444 500 503",
    "organization_branches_delete": "200 400 401 403 404 409 413 422 444 500 503",
    "organization_facility_codes_list": "200 400 401 403 409 422 444 500 503",
    "organization_admin_facility_codes_list": "200 400 401 403 409 422 444 500 503",
    "organization_admin_facility_codes_create": "201 400 401 403 409 413 422 444 500 503",
    "organization_admin_facility_codes_update": "200 400 401 403 404 409 413 422 444 500 503",
    "organization_admin_facility_codes_delete": "200 400 401 403 404 409 413 422 444 500 503",
    # K1b-2a
    "inventory_admin_ghg_nodes_list": "200 400 401 403 404 409 422 444 500 503",
    "inventory_admin_ghg_nodes_create": "201 400 401 403 404 409 413 422 444 500 503",
    "inventory_admin_ghg_nodes_update": "200 400 401 403 404 409 413 422 444 500 503",
    "inventory_admin_ghg_nodes_delete": "200 400 401 403 404 409 413 422 444 500 503",
    "inventory_admin_ghg_facilities_get": "200 400 401 403 404 409 422 444 500 503",
    "inventory_admin_ghg_facilities_create": "201 400 401 403 404 409 413 422 444 500 503",
    "inventory_admin_ghg_facilities_save": "200 400 401 403 404 409 413 422 444 500 503",
    "inventory_admin_ghg_factors_create": "201 400 401 403 404 409 413 422 444 500 503",
    "inventory_admin_ghg_factors_get": "200 400 401 403 404 409 422 444 500 503",
    "inventory_admin_ghg_factors_save": "200 400 401 403 404 409 413 422 444 500 503",
    "inventory_admin_ghg_factors_delete": "200 400 401 403 404 409 413 422 444 500 503",
    "inventory_admin_ghg_options": "200 400 401 403 409 422 444 500 503",
    # K1b-2b
    "inventory_scope12_index_tree": "200 400 401 403 409 422 444 500 503",
    "inventory_scope12_index_selections_save": "200 400 401 403 409 413 422 444 500 503",
    # S12a
    "inventory_scope12_years": "200 400 401 403 409 422 444 500 503",
    "inventory_scope12_rows": "200 400 401 403 409 422 444 500 503",
    "inventory_scope12_index_detail": "200 400 401 403 404 409 422 444 500 503",
    "inventory_scope12_rows_save": "200 400 401 403 404 409 413 422 444 500 503",
    "inventory_scope12_rows_delete": "200 400 401 403 404 409 413 422 444 500 503",
    "inventory_scope12_memo_save": "200 400 401 403 404 409 413 422 444 500 503",
    "inventory_scope12_lock": "200 400 401 403 404 409 422 444 500 503",
    "inventory_scope12_unlock": "200 400 401 403 404 409 422 444 500 503",
    "inventory_scope12_decimals_save": "200 400 401 403 404 409 413 422 444 500 503",
    "inventory_scope12_row_history": "200 400 401 403 404 409 422 444 500 503",
    "inventory_scope12_period_save": "200 400 401 403 404 409 413 422 444 500 503",  # S12a-2
    "inventory_scope12_row_factor_save": "200 400 401 403 404 409 413 422 444 500 503",  # S12a-2
    "inventory_scope12_history_restore": "200 400 401 403 404 409 413 422 444 500 503",  # S12a-2
    "inventory_scope3_template": "200 400 401 403 409 422 444 500 503",  # S3K1
    "inventory_scope3_result_get": "200 400 401 403 404 409 422 444 500 503",  # S3K1
    "inventory_scope3_original_get": "200 400 401 403 404 409 422 444 500 503",  # S3Q1 +1
    "inventory_scope12_dashboard": "200 400 401 403 409 422 444 500 503",  # S12a-3
    "inventory_scope12_template": "200 400 401 403 404 409 422 444 500 503",  # S12b-1
    "inventory_scope12_export": "200 400 401 403 404 409 422 444 500 503",  # S12b-1
    "inventory_scope12_upload": "200 400 401 403 404 409 413 422 444 500 503",  # S12b-2
    "inventory_scope3_year_get": "200 400 401 403 409 422 444 500 503",  # S3K2a
    "inventory_scope3_lock": "200 400 401 403 404 409 422 444 500 503",  # S3K2a
    "inventory_scope3_unlock": "200 400 401 403 404 409 422 444 500 503",  # S3K2a
    "inventory_scope3_export": "200 400 401 403 404 409 422 444 500 503",  # S3D1
    "inventory_scope3_rows_exclude": "200 400 401 403 404 409 413 422 444 500 503",  # S3K2b-1
    "inventory_scope3_rows_restore": "200 400 401 403 404 409 413 422 444 500 503",  # S3K2b-1
    "inventory_scope3_edits_get": "200 400 401 403 404 409 422 444 500 503",  # S3K2b-1
    "inventory_scope3_history_get": "200 400 401 403 404 409 422 444 500 503",  # S3K2b-1
    "inventory_scope3_row_factor": "200 400 401 403 404 409 413 422 444 500 503",  # S3K2b-2
}
# 실행 꼴의 칸 → openapi 타입("a|null" 은 nullable, "[]X" 는 X 의 배열, "type/format").
RUN_FIELD_TYPES: Final[dict[str, dict[str, str]]] = {
    "RunCreatedOut": {
        "id": "integer",
        "status": "string",
    },
    "RunPageOut": {
        "count": "integer",
        "isNext": "boolean",
        "results": "[]RunSummaryOut",
    },
    "RunSummaryOut": {
        "createdAt": "string/date-time",
        "documentId": "integer|null",  # ND1: 문서 없는 흐름의 실행
        "documentName": "string|null",
        "finishedAt": "string/date-time|null",
        "flowId": "string",
        "id": "integer",
        "module": "string",
        "status": "string",
    },
    "RunStepOut": {
        "done": "integer|null",
        "status": "string",
        "step": "string",
        "total": "integer|null",
        "segments": "RunStepSegmentsOut|null",
    },
    # RM1b
    "RunStepSegmentsOut": {
        "planned": "integer|null",
        "pending": "integer",
        "running": "integer",
        "done": "integer",
        "failed": "integer",
        "firstStartedAt": "string/date-time|null",
        "lastFinishedAt": "string/date-time|null",
    },
    "RunOut": {
        "createdAt": "string/date-time",
        "documentId": "integer|null",  # ND1
        "errorCode": "string|null",
        "errorMessage": "string|null",
        "failedStep": "string|null",
        "files": "[]string",
        "finishedAt": "string/date-time|null",
        "flowId": "string",
        "id": "integer",
        "module": "string",
        "options": "object",
        "resultShapes": "[]string",
        "resumedFromRunId": "integer|null",
        "startedAt": "string/date-time|null",
        "status": "string",
        "steps": "[]RunStepOut",
    },
    # RM1c ③
    "RunRetrySegmentsIn": {
        "fromRunId": "integer",
        "keys": "[]string",
        "step": "string",
    },
    "RunSegmentPageOut": {
        "count": "integer",
        "isNext": "boolean",
        "results": "[]RunSegmentOut",
    },
    "RunSegmentOut": {
        "attempts": "integer",
        "errorCode": "string|null",
        "finishedAt": "string/date-time|null",
        "key": "RunSegmentKeyOut",
        "keySha256": "string",
        "position": "integer",
        "startedAt": "string/date-time|null",
        "status": "string",
    },
    "RunSegmentKeyOut": {
        "documentSha256": "string|null",
        "kind": "string",
        "parserVersion": "string|null",
        "span": "string",
    },
}


def test_every_operation_declares_exactly_these_response_codes() -> None:
    operations = _operations(_document())
    declared = {operation["operationId"]: " ".join(sorted(operation["responses"])) for operation in operations.values()}
    assert declared == RESPONSE_CODES
    assert set(RESPONSE_CODES) == set(OPERATION_IDS.values())  # 분모: 손으로 적은 동작 표와 같은 동작을 잰다


def _field_type(spec: dict[str, Any]) -> str:
    found: list[str] = []
    for option in spec.get("anyOf", [spec]):
        if "$ref" in option:
            found.append(option["$ref"].rsplit("/", 1)[-1])
        elif option.get("type") == "array":
            items = option["items"]
            found.append("[]" + (items["$ref"].rsplit("/", 1)[-1] if "$ref" in items else items["type"]))
        else:
            found.append(option["type"] + ("/" + option["format"] if "format" in option else ""))
    return "|".join(found)


def test_the_run_shapes_have_these_field_types() -> None:
    schemas: dict[str, dict[str, Any]] = _document()["components"]["schemas"]
    for name, fields in RUN_FIELD_TYPES.items():
        assert {field: _field_type(spec) for field, spec in schemas[name]["properties"].items()} == fields, name
    assert set(RUN_FIELD_TYPES["RunOut"]) == RUN_OUT_FIELDS  # 분모: 계약 한 장의 칸과 같은 칸을 잰다
