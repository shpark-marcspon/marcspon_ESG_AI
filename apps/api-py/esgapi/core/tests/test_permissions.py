"""권한 표(core/permissions.py)를 잰다. 순수 층: 표의 칸(동작 → 필요한 것), 표와 계약(generated/openapi.json), 경로가
표를 읽는 자리.

core 의 테스트라 업무 모듈을 import 하지 않는다(계약 가). 다른 도메인의 파일은 경로로 읽는다.
"""

import ast
import json
from dataclasses import fields
from pathlib import Path
from typing import Any, get_args

import pytest
from django.contrib.auth.hashers import make_password

from esgapi.core import permissions
from esgapi.core.auth.principal import Kind
from esgapi.core.permissions import (
    COMPANY,
    CUSTOMER,
    INITIAL_ALLOWED,
    OPERATION_POLICY,
    OPERATOR,
    OPERATOR_RUN_MODULES,
    Policy,
    forbidden_message,
    is_allowed,
    needs_of,
)

ESGAPI = Path(__file__).resolve().parents[2]
API_PY = ESGAPI.parent
KINDS: tuple[Kind, ...] = get_args(Kind)

# 권한 표를 글자로 한 번 더 적은 것(사용자 결정 2026-10-15 14:46 — 역할 둘). 회사 경로의 동작 31
# = 고객사 사용자 10 + 회사 업무 20(두 kind 다 — 운영 관리자는 작업 회사로, 결정 MARC-ENT-374. OP2 +1 영문번역 결과,
# MARC-ENT-380. DV1e +1 데이터 검증 결과, MARC-ENT-390).
# DV1g +1 데이터 검증 목록, MARC-ENT-420.
# IR3b +1 중대성평가 IRO 결과, MARC-ENT-419.
# IR3c +1 중대성평가 IRO 목록, MARC-ENT-419.
# TRP6 +1 영문번역 문서 쪽 수, MARC-ENT-452.
# TRS3 +1 영문번역 layout 읽기, MARC-ENT-471.
CUSTOMER_OPERATIONS = {
    "accounts_me",
    "accounts_sites_list",
    "accounts_sites_create",
    "inventory_calc",
    "inventory_scope3_shortlist",
    "inventory_scope3_classify",
    "reference_sources",
    "reference_factors",
    "reference_assemble",
    "reference_assemble_electricity",
}
COMPANY_WORK_OPERATIONS = {
    "core_documents_create",
    "core_documents_confirm",
    "core_documents_get",
    "core_documents_update",
    "core_documents_file_get",
    "core_documents_list",
    "core_documents_versions",
    "runs_create",
    "runs_list",
    "runs_get",
    "runs_file_get",
    "runs_segments_list",  # RM1c ③ +1
    "greenwash_result_get",
    "greenwash_result2_get",  # GE1b ④ +1
    "greenwash_review_get",
    "greenwash_review_put",
    "greenwash_item_rejudge",  # GRJ1 +1
    "greenwash_compare_get",
    "greenwash_report_get",
    "greenwash_terms_default",
    "greenwash_checks_get",
    "translation_result_get",
    "translation_glossary_read",
    "translation_glossary_template",
    "translation_batches_list",
    "translation_batch_get",
    "translation_batch_archive",
    "translation_document_pages",
    "translation_layout_get",
    "dataverify_result_get",
    "dataverify_runs_list",
    "dataverify_edk_read",
    "dataverify_edk_template",
    "materiality_result_get",
    "materiality_runs_list",
    "materiality_value_chain_read",
    "materiality_result_edits_get",  # IRS3 ② 결과 고침 둘
    "materiality_result_edits_post",
    "materiality_report_get",  # IRS3 ③ 고친 판 최종 엑셀
    # RP1 원고작성 다섯(프로젝트 넷·결과 하나 — 운영 관리자는 작업 회사로)
    "drafting_projects_create",
    "drafting_project_get",
    "drafting_project_document_put",
    "drafting_outline_put",
    "drafting_result_get",
    "drafting_projects_list",  # RP2d
    "drafting_result_download",  # RP2d
    "drafting_outline_changes",  # RP2c
    "drafting_project_runs",  # RPS1
    # K1b-1 사업장 여섯·코드 목록 읽기 하나(MARC-ENT-469 3·4 — 플랫폼-서버 ce 허락 2026-10-28)
    "organization_branches_list",
    "organization_branches_get",
    "organization_branches_create",
    "organization_branches_save",
    "organization_branches_inventory",
    "organization_branches_delete",
    "organization_facility_codes_list",
    # K1b-2b 고객사 인덱스 선택 둘(MARC-ENT-469 4·374 — 플랫폼-서버 e7 허락 2026-10-29)
    "inventory_scope12_index_tree",
    "inventory_scope12_index_selections_save",
    # S12a Scope 1·2 입력 아홉(MARC-ENT-469 4 — 플랫폼-서버 e7 허락 2026-10-29)
    "inventory_scope12_years",
    "inventory_scope12_rows",
    "inventory_scope12_index_detail",
    "inventory_scope12_rows_save",
    "inventory_scope12_rows_delete",
    "inventory_scope12_memo_save",
    "inventory_scope12_lock",
    "inventory_scope12_decimals_save",
    "inventory_scope12_row_history",
    # S12a-2 입력주기·히스토리 복구 둘(MARC-ENT-469 4 — 플랫폼-서버 e7 허락 2026-10-29)
    "inventory_scope12_period_save",
    "inventory_scope12_history_restore",
    # S3K1 Scope 3 코랩 둘(빈 양식·결과 — 469-4 「대신하기」 꼴, 플랫폼-서버 e7 1-5 H2)
    "inventory_scope3_template",
    "inventory_scope3_result_get",
    "inventory_scope3_original_get",  # S3Q1 +1: 올린 엑셀 원본 내려받기(같은 꼴, 플랫폼-서버 7a 허락)
    # S12a-3 대시보드 하나(S1 읽기 — 469-1, 플랫폼-서버 7a 허락)
    "inventory_scope12_dashboard",
    # S12b-1 엑셀 내려받기 둘(양식·데이터 — 469-4 「대신하기」 꼴, 플랫폼-서버 7a 허락)
    "inventory_scope12_template",
    "inventory_scope12_export",
    "inventory_scope12_upload",  # S12b-2 일괄 올리기(플랫폼-서버 7a 허락)
    # S3K2a Scope 3 연도 상태·카테고리 잠그기 둘(469 2 — 고객사가 건다·운영 관리자 대행, 플랫폼-서버 7a 허락)
    "inventory_scope3_year_get",
    "inventory_scope3_lock",
    "inventory_scope3_export",  # S3D1 Scope 3 데이터 엑셀(회사 업무 — 플랫폼-서버 줄 테스트 6d 허락)
    # S3K2b-1 Scope 3 줄 덧판 넷(469 4 — 고객사·운영 관리자 대행, 플랫폼-서버 7a 허락)
    "inventory_scope3_rows_exclude",
    "inventory_scope3_rows_restore",
    "inventory_scope3_edits_get",
    "inventory_scope3_history_get",
    "inventory_scope3_row_factor",
}
SELF_OPERATIONS = {"user_me", "user_password_change"}  # 자기 계정의 동작(K2a): 두 kind 다
# 고객사 사용자 관리(K2c·UA1)·감사 기록 조회(AU1a)·감사 기록의 사람 목록(AU1b-1)·실행 기록 둘(AU1b-2): 운영 관리자만
OPERATOR_OPERATIONS = {
    "user_list",
    "user_create",
    "user_password_reset",
    "user_update",
    "user_audit_list",
    "user_audit_actors",
    "user_run_log_list",
    "user_run_log_metrics",
    "user_run_log_export",  # AD4S
    "user_run_log_get",  # AD4D
    "user_run_log_file_get",  # RF1
    # 그린워싱 AI 설정 판 다섯(G2c2 — 백엔드 c1 허락 2026-10-19)
    "greenwash_ai_setting_list",
    "greenwash_ai_setting_default",
    "greenwash_ai_setting_get",
    "greenwash_ai_setting_create",
    "greenwash_ai_setting_apply",
    # 프롬프트·모델 읽기 둘(AS2a — 백엔드 99 허락 2026-10-20)
    "greenwash_ai_setting_prompt_model",
    "greenwash_ai_setting_default_prompt_model",
    # 영문번역 AI 설정 판 일곱(TR4 — 플랫폼-서버 d9 허락 2026-10-23)
    "translation_ai_setting_list",
    "translation_ai_setting_default",
    "translation_ai_setting_get",
    "translation_ai_setting_create",
    "translation_ai_setting_apply",
    "translation_ai_setting_prompt_model",
    "translation_ai_setting_default_prompt_model",
    # 데이터 검증 AI 설정 판 일곱(DVA1 — 플랫폼-서버 e5 허락 2026-10-26)
    "dataverify_ai_setting_list",
    "dataverify_ai_setting_default",
    "dataverify_ai_setting_get",
    "dataverify_ai_setting_create",
    "dataverify_ai_setting_apply",
    "dataverify_ai_setting_prompt_model",
    "dataverify_ai_setting_default_prompt_model",
    # 중대성평가 IRO AI 설정 판 일곱(IR4 — 플랫폼-서버 e5 허락 2026-10-27)
    "materiality_ai_setting_list",
    "materiality_ai_setting_default",
    "materiality_ai_setting_get",
    "materiality_ai_setting_create",
    "materiality_ai_setting_apply",
    "materiality_ai_setting_prompt_model",
    "materiality_ai_setting_default_prompt_model",
    # 원고작성 AI 설정 판 일곱(RPA1 — 플랫폼-서버 7a 허락 2026-10-30)
    "drafting_ai_setting_list",
    "drafting_ai_setting_default",
    "drafting_ai_setting_get",
    "drafting_ai_setting_create",
    "drafting_ai_setting_apply",
    "drafting_ai_setting_prompt_model",
    "drafting_ai_setting_default_prompt_model",
    # K1b-1 자산/시설 코드 목록 넷(MARC-ENT-469 3 — 플랫폼-서버 ce 허락 2026-10-28)
    "organization_admin_facility_codes_list",
    "organization_admin_facility_codes_create",
    "organization_admin_facility_codes_update",
    "organization_admin_facility_codes_delete",
    # K1b-2a — 온실가스 인덱스 풀·계수 풀 열둘(공통 풀, 운영 관리자만)
    "inventory_admin_ghg_nodes_list",
    "inventory_admin_ghg_nodes_create",
    "inventory_admin_ghg_nodes_update",
    "inventory_admin_ghg_nodes_delete",
    "inventory_admin_ghg_facilities_get",
    "inventory_admin_ghg_facilities_create",
    "inventory_admin_ghg_facilities_save",
    "inventory_admin_ghg_factors_create",
    "inventory_admin_ghg_factors_get",
    "inventory_admin_ghg_factors_save",
    "inventory_admin_ghg_factors_delete",
    "inventory_admin_ghg_options",
    # S12a 잠금 풀기(MARC-ENT-469 2 — 회사 경로라 작업 회사를 고른다, e7 허락 2026-10-29)
    "inventory_scope12_unlock",
    # S12a-2 행 계수 바꿈(MARC-ENT-469 — 계수 수정은 운영 관리자, 작업 회사를 고른다 · e7 허락 2026-10-29)
    "inventory_scope12_row_factor_save",
    # S3K2a Scope 3 카테고리 잠금 풀기(469 2 · RPT-21 §3.3 — 작업 회사를 고른다 · 플랫폼-서버 7a 허락)
    "inventory_scope3_unlock",
}
NEEDS: dict[str, str] = (
    {op: "customer" for op in CUSTOMER_OPERATIONS}
    | {op: "company" for op in COMPANY_WORK_OPERATIONS}
    | {op: "self" for op in SELF_OPERATIONS}
    | {op: "operator" for op in OPERATOR_OPERATIONS}
)
# 권한을 경로가 아니라 Selector·Service 안에서 보는 둘.
# operationId → (그 경로가 부르는 함수가 사는 파일, 그 함수의 이름, 권한 함수의 이름)
INSIDE: dict[str, tuple[str, str, str]] = {
    "accounts_sites_list": ("organization/service/selectors/organization.py", "list_sites", "can_view_sites"),
    "accounts_sites_create": ("organization/service/services/organization.py", "create_site", "can_create_site"),
}
# 경로의 첫 문장(permitted — 인증·is_initial·표)에 더해 그 경로가 부르는 Selector·Service·Action 도 첫 줄에서 표를 읽는
# 여덟(K2c·UA1 — 명령이 같은 service·action 을 부른다. AU1a·AU1b-1 — core 의 감사 selector 는 표를 바로 읽는다.
# AU1b-2 — runs 의 운영 관리자 실행 selector 는 표를 바로 읽는다).
# G2c2 +5: 그린워싱 AI 설정 판의 actions 다섯 · AS2a +2: 프롬프트·모델 읽기 둘(운영 관리자 칸 전부 — 열다섯).
# operationId → (파일, 함수, 권한 함수).
ALSO_INSIDE: dict[str, tuple[str, str, str]] = {
    "user_list": ("user/service/selectors/user.py", "list_customer_users", "can_manage_customer_users"),
    "user_create": ("user/service/services/user.py", "create_customer_user", "can_manage_customer_users"),
    "user_password_reset": ("user/service/actions/password.py", "reset_password", "can_manage_customer_users"),
    "user_update": ("user/service/actions/account.py", "update_customer_user", "can_manage_customer_users"),
    "user_audit_list": ("core/service/selectors/audit.py", "list_audit_events", "is_allowed"),
    "user_audit_actors": ("core/service/selectors/audit.py", "list_audit_actors", "is_allowed"),
    "user_run_log_list": ("runs/service/selectors/operator.py", "operator_run_page", "is_allowed"),
    "user_run_log_metrics": ("runs/service/selectors/operator.py", "operator_run_cohort", "is_allowed"),
    "user_run_log_export": ("runs/service/selectors/operator.py", "operator_run_export", "is_allowed"),  # AD4S
    "user_run_log_get": ("runs/service/selectors/operator.py", "operator_run_detail", "is_allowed"),  # AD4D
    "user_run_log_file_get": ("runs/service/selectors/operator.py", "operator_run_file", "is_allowed"),  # RF1
    # G2c2 — 그린워싱 AI 설정 판의 actions 다섯(기본 판도 같은 꼴 — 운영 관리자 칸 전부가 ALSO_INSIDE 라는 단언 그대로)
    "greenwash_ai_setting_list": ("greenwash/service/actions/ai_settings.py", "setting_list", "is_allowed"),
    "greenwash_ai_setting_default": ("greenwash/service/actions/ai_settings.py", "default_setting", "is_allowed"),
    "greenwash_ai_setting_get": ("greenwash/service/actions/ai_settings.py", "setting_detail", "is_allowed"),
    "greenwash_ai_setting_create": ("greenwash/service/actions/ai_settings.py", "save_setting", "is_allowed"),
    "greenwash_ai_setting_apply": ("greenwash/service/actions/ai_settings.py", "apply_setting", "is_allowed"),
    # AS2a — 프롬프트·모델 읽기 둘
    "greenwash_ai_setting_prompt_model": ("greenwash/service/actions/ai_settings.py", "prompt_model", "is_allowed"),
    "greenwash_ai_setting_default_prompt_model": (
        "greenwash/service/actions/ai_settings.py",
        "default_prompt_model",
        "is_allowed",
    ),
    # TR4 — 영문번역 AI 설정 판의 actions 일곱(그린워싱과 같은 꼴)
    "translation_ai_setting_list": ("translation/service/actions/ai_settings.py", "setting_list", "is_allowed"),
    "translation_ai_setting_default": ("translation/service/actions/ai_settings.py", "default_setting", "is_allowed"),
    "translation_ai_setting_get": ("translation/service/actions/ai_settings.py", "setting_detail", "is_allowed"),
    "translation_ai_setting_create": ("translation/service/actions/ai_settings.py", "save_setting", "is_allowed"),
    "translation_ai_setting_apply": ("translation/service/actions/ai_settings.py", "apply_setting", "is_allowed"),
    "translation_ai_setting_prompt_model": ("translation/service/actions/ai_settings.py", "prompt_model", "is_allowed"),
    "translation_ai_setting_default_prompt_model": (
        "translation/service/actions/ai_settings.py",
        "default_prompt_model",
        "is_allowed",
    ),
    # DVA1 — 데이터 검증 AI 설정 판의 actions 일곱(영문번역과 같은 꼴)
    "dataverify_ai_setting_list": ("dataverify/service/actions/ai_settings.py", "setting_list", "is_allowed"),
    "dataverify_ai_setting_default": ("dataverify/service/actions/ai_settings.py", "default_setting", "is_allowed"),
    "dataverify_ai_setting_get": ("dataverify/service/actions/ai_settings.py", "setting_detail", "is_allowed"),
    "dataverify_ai_setting_create": ("dataverify/service/actions/ai_settings.py", "save_setting", "is_allowed"),
    "dataverify_ai_setting_apply": ("dataverify/service/actions/ai_settings.py", "apply_setting", "is_allowed"),
    "dataverify_ai_setting_prompt_model": ("dataverify/service/actions/ai_settings.py", "prompt_model", "is_allowed"),
    "dataverify_ai_setting_default_prompt_model": (
        "dataverify/service/actions/ai_settings.py",
        "default_prompt_model",
        "is_allowed",
    ),
    # IR4 — 중대성평가 IRO AI 설정 판의 actions 일곱(데이터 검증과 같은 꼴)
    "materiality_ai_setting_list": ("materiality/service/actions/ai_settings.py", "setting_list", "is_allowed"),
    "materiality_ai_setting_default": ("materiality/service/actions/ai_settings.py", "default_setting", "is_allowed"),
    "materiality_ai_setting_get": ("materiality/service/actions/ai_settings.py", "setting_detail", "is_allowed"),
    "materiality_ai_setting_create": ("materiality/service/actions/ai_settings.py", "save_setting", "is_allowed"),
    "materiality_ai_setting_apply": ("materiality/service/actions/ai_settings.py", "apply_setting", "is_allowed"),
    "materiality_ai_setting_prompt_model": ("materiality/service/actions/ai_settings.py", "prompt_model", "is_allowed"),
    "materiality_ai_setting_default_prompt_model": (
        "materiality/service/actions/ai_settings.py",
        "default_prompt_model",
        "is_allowed",
    ),
    # RPA1 — 원고작성 AI 설정 판의 actions 일곱(중대성평가 IRO 와 같은 꼴)
    "drafting_ai_setting_list": ("drafting/service/actions/ai_settings.py", "setting_list", "is_allowed"),
    "drafting_ai_setting_default": ("drafting/service/actions/ai_settings.py", "default_setting", "is_allowed"),
    "drafting_ai_setting_get": ("drafting/service/actions/ai_settings.py", "setting_detail", "is_allowed"),
    "drafting_ai_setting_create": ("drafting/service/actions/ai_settings.py", "save_setting", "is_allowed"),
    "drafting_ai_setting_apply": ("drafting/service/actions/ai_settings.py", "apply_setting", "is_allowed"),
    "drafting_ai_setting_prompt_model": ("drafting/service/actions/ai_settings.py", "prompt_model", "is_allowed"),
    "drafting_ai_setting_default_prompt_model": (
        "drafting/service/actions/ai_settings.py",
        "default_prompt_model",
        "is_allowed",
    ),
    # K1b-1 — 자산/시설 코드 목록 넷(목록은 selector, 쓰기 셋은 services — 표 하나라 actions 없음)
    "organization_admin_facility_codes_list": (
        "organization/service/selectors/facility_codes.py",
        "admin_code_page",
        "is_allowed",
    ),
    "organization_admin_facility_codes_create": (
        "organization/service/services/facility_codes.py",
        "create_code",
        "is_allowed",
    ),
    "organization_admin_facility_codes_update": (
        "organization/service/services/facility_codes.py",
        "rename_code",
        "is_allowed",
    ),
    "organization_admin_facility_codes_delete": (
        "organization/service/services/facility_codes.py",
        "delete_codes",
        "is_allowed",
    ),
    # K1b-2a — 온실가스 풀 열둘(읽기 넷은 selector, 노드 만들기·이름은 services, 두 표 이상은 actions)
    "inventory_admin_ghg_nodes_list": (
        "inventory/service/selectors/ghg_pool.py",
        "node_list",
        "is_allowed",
    ),
    "inventory_admin_ghg_nodes_create": (
        "inventory/service/services/ghg_pool.py",
        "create_node",
        "is_allowed",
    ),
    "inventory_admin_ghg_nodes_update": (
        "inventory/service/services/ghg_pool.py",
        "rename_node",
        "is_allowed",
    ),
    "inventory_admin_ghg_nodes_delete": (
        "inventory/service/actions/ghg_pool.py",
        "delete_nodes",
        "is_allowed",
    ),
    "inventory_admin_ghg_facilities_get": (
        "inventory/service/selectors/ghg_pool.py",
        "facility_detail",
        "is_allowed",
    ),
    "inventory_admin_ghg_facilities_create": (
        "inventory/service/actions/ghg_pool.py",
        "create_facility",
        "is_allowed",
    ),
    "inventory_admin_ghg_facilities_save": (
        "inventory/service/actions/ghg_pool.py",
        "save_facility",
        "is_allowed",
    ),
    "inventory_admin_ghg_factors_create": (
        "inventory/service/actions/ghg_pool.py",
        "create_factor",
        "is_allowed",
    ),
    "inventory_admin_ghg_factors_get": (
        "inventory/service/selectors/ghg_pool.py",
        "factor_version",
        "is_allowed",
    ),
    "inventory_admin_ghg_factors_save": (
        "inventory/service/actions/ghg_pool.py",
        "save_factor",
        "is_allowed",
    ),
    "inventory_admin_ghg_factors_delete": (
        "inventory/service/actions/ghg_pool.py",
        "delete_factors",
        "is_allowed",
    ),
    "inventory_admin_ghg_options": (
        "inventory/service/selectors/ghg_pool.py",
        "options",
        "is_allowed",
    ),
    # S12a — 잠금 풀기(운영 관리자 칸의 회사 경로 첫 사례 — e7 허락 2026-10-29)
    "inventory_scope12_unlock": ("inventory/service/actions/entries.py", "unlock_index", "is_allowed"),
    # S12a-2 — 행 계수 바꿈(첫 문장. 복구의 계수 줄 판정은 ALSO_INSIDE 밖 — inventory·보안 층 시험, e7 허락 2026-10-29)
    "inventory_scope12_row_factor_save": ("inventory/service/actions/entries.py", "set_row_factor", "is_allowed"),
    # S3K2a — Scope 3 카테고리 잠금 풀기(첫 문장 — unlock_index 꼴, 7a 허락)
    "inventory_scope3_unlock": ("inventory/service/actions/scope3_state.py", "unlock", "is_allowed"),
}
CHECKERS = {"permitted_session", "permitted"}  # 밴드 CU1 이 documents·runs 의 겉 `_permitted` 를 걷었다
# 인증이 없는 동작(표 밖). 여기 더하는 것은 공개를 정하는 일이다 — 더할 때는 그 결정 shortId 를 주석에(AUTHZ1).
PUBLIC_OPERATIONS = {
    "accounts_auth_exchange",
    "accounts_auth_logout",
    "user_auth_login",
    "user_auth_refresh",
    "user_auth_revoke",
    "config_healthz",
    "config_readyz",
}


def operations() -> list[dict[str, Any]]:
    """계약(generated/openapi.json)의 동작 전부."""
    document: dict[str, Any] = json.loads((API_PY / "generated" / "openapi.json").read_text(encoding="utf-8"))
    return [
        operation
        for methods in document["paths"].values()
        for operation in methods.values()
        if isinstance(operation, dict)
    ]


def authenticated_operations() -> set[str]:
    return {operation["operationId"] for operation in operations() if operation.get("security")}


def test_every_authenticated_operation_is_in_the_table() -> None:
    assert authenticated_operations() == set(OPERATION_POLICY)


def test_the_public_operations_are_these_seven() -> None:
    """security 칸이 없거나 빈 동작은 이 일곱뿐이다. 인증을 빠뜨린 새 경로는 여기서 이름으로 빨갛다."""
    everything = operations()
    assert len(everything) == 167  # 분모: 공개 7 · 인증 81(G2c2 +5 · AS2a +2 · TR2·AD4S·AD4D·RF1·DV1e 각 +1 · TR3a +2)
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: inventory_scope3_original_get
    # · TR3b +3: translation_batches_list · translation_batch_get · translation_batch_archive
    # · TR4 +7: translation_ai_setting_* 일곱
    # · IR3b +1: materiality_result_get
    # · DVA1 +7: dataverify_ai_setting_* 일곱
    # · IR3c +1: materiality_runs_list
    # · TRP6 +1: translation_document_pages
    # · TRS3 +1: translation_layout_get
    # · IRW2 +1: materiality_value_chain_read
    # · IRS3 +3: materiality_result_edits_get · materiality_result_edits_post · materiality_report_get(③)
    # · IR4 +7: materiality_ai_setting_* 일곱
    # · K1b-1 +11: organization_branches_* 여섯 · organization_facility_codes_list
    # · S12a-2 +3: inventory_scope12_period_save · history_restore(회사 업무) · row_factor_save(운영 관리자)
    #   · organization_admin_facility_codes_* 넷
    # · S3K1 +2: inventory_scope3_template · inventory_scope3_result_get(회사 업무)
    # · K1b-2a +12: inventory_admin_ghg_* 열둘
    # · K1b-2b +2: inventory_scope12_index_tree · inventory_scope12_index_selections_save
    # · S12a +10: inventory_scope12_* 열(회사 업무 9 · 풀기 1)
    # · DVX1 +2: dataverify_edk_read · dataverify_edk_template
    # · RP1 +5: drafting_* 다섯
    # · RP2d +2: drafting_projects_list · drafting_result_download
    # · RP2c +1: drafting_outline_changes
    # · RPS1 +1: drafting_project_runs
    # · RPA1 +7: drafting_ai_setting_* 일곱
    # · S12a-3 +1: inventory_scope12_dashboard(회사 업무)
    # · S12b-1 +2: inventory_scope12_template·inventory_scope12_export(회사 업무)
    # · S12b-2 +1: inventory_scope12_upload(회사 업무)
    # · S3K2a +3: inventory_scope3_year_get · inventory_scope3_lock(회사 업무) · inventory_scope3_unlock(운영 관리자)
    # · S3K2b-1 +4: Scope 3 줄 덧판(제외·복구·지금 상태·히스토리)
    # · S3K2b-2 +1: Scope 3 계수 수정
    # · S3D1 +1: inventory_scope3_export(회사 업무)
    assert {operation["operationId"] for operation in everything if not operation.get("security")} == PUBLIC_OPERATIONS
    assert PUBLIC_OPERATIONS & set(OPERATION_POLICY) == set()
    assert len(PUBLIC_OPERATIONS) + len(OPERATION_POLICY) == len(everything)  # 공개 ∪ 표 = 동작 전부, 겹침 0


def test_the_table_is_these_needs() -> None:
    assert {op: needs_of(op) for op in OPERATION_POLICY} == NEEDS
    # 분모: 고객사 10 · 회사 업무 20(OP2·DV1e +1) · 자기 2 · 운영 관리자 17(K2c·UA1·AU1a·AU1b·G2c2·AS2a·AD4S·AD4D)
    assert len(NEEDS) == 160  # 분모: 고객사 10 · 회사 업무 30(IR3b·IR3c·IRW2) · 자기 2 · 운영 관리자 39(RF1 +1 · TR4 +7
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · DVA1 +7)
    # · IR4 +7
    # · IRS3 +3: 회사 업무 +3(결과 고침 둘 · 고친 판 엑셀)
    # · K1b-1 +11: 회사 업무 +7(사업장 6·코드 목록 1) · 운영 관리자 +4(코드 목록 넷)
    # · K1b-2a +12: 운영 관리자 +12(온실가스 풀 열둘)
    # · K1b-2b +2: 회사 업무 +2(인덱스 선택 둘)
    # · S12a +10: 회사 업무 +9(Scope 1·2 입력) · 운영 관리자 +1(잠금 풀기)
    # · DVX1 +2: 회사 업무 +2(EDK 엑셀 읽기·양식)
    # · RP1 +5: 회사 업무 +5(원고작성)
    # · RP2d +2: 회사 업무 +2(원고작성 목록·docx)
    # · RP2c +1: 회사 업무 +1(원고작성 목차 차이)
    # · RPS1 +1: 회사 업무 +1(원고작성 프로젝트 실행 목록)
    # · S12a-2 +3: 회사 업무 +2(입력주기·복구) · 운영 관리자 +1(행 계수 바꿈)
    # · RPA1 +7: 운영 관리자 +7(원고작성 AI 설정 판)
    # · S3K1 +2: inventory_scope3_template · inventory_scope3_result_get(회사 업무)
    # · S12a-3 +1: inventory_scope12_dashboard(회사 업무)
    # · S12b-1 +2: inventory_scope12_template·inventory_scope12_export(회사 업무)
    # · S12b-2 +1: inventory_scope12_upload(회사 업무)
    # · S3K2a +3: 회사 업무 +2(Scope 3 연도 상태·잠그기) · 운영 관리자 +1(잠금 풀기)
    allowed = {(op, kind): is_allowed(op, kind=kind) for op in OPERATION_POLICY for kind in KINDS}
    assert allowed == {
        (op, kind): NEEDS[op] in ("self", "company")
        or (NEEDS[op] == "customer" and kind == "service")
        or (NEEDS[op] == "operator" and kind == "admin")
        for op in OPERATION_POLICY
        for kind in KINDS
    }


def test_the_cells_are_partitioned() -> None:
    cells: dict[str, set[str]] = {"customer": set(), "operator": set(), "self": set(), "company": set()}
    for op, policy in OPERATION_POLICY.items():
        cells[policy.needs].add(op)
    assert cells == {
        "customer": CUSTOMER_OPERATIONS,
        "operator": OPERATOR_OPERATIONS,
        "self": SELF_OPERATIONS,
        "company": COMPANY_WORK_OPERATIONS,
    }
    assert sum(map(len, cells.values())) == len(authenticated_operations())  # 겹침 0·빠짐 0


def test_an_operator_is_refused_every_customer_cell() -> None:
    refused = {op for op in CUSTOMER_OPERATIONS if not is_allowed(op, kind="admin")}
    assert refused == CUSTOMER_OPERATIONS
    assert all(is_allowed(op, kind="service") for op in CUSTOMER_OPERATIONS)  # 분모: 고객사 사용자는 지난다


def test_both_kinds_do_the_company_work() -> None:
    """회사 업무 25(문서 7·실행 4·그린워싱 7·영문번역 6·데이터 검증 1)는 두 kind 다(결정 MARC-ENT-374·380·390). 회사는
    표가 아니라 core/auth/bearer.py 의 company_of 가 정한다."""
    assert len(COMPANY_WORK_OPERATIONS) == 83  # 분모: 문서 7 · 실행 5 · 그린워싱 9 · 영문번역 8 · 데이터 검증 4
    # · RM1c ③ +1: 실행 구획 목록
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · 중대성평가 3(IR3b·IR3c·IRW2)
    # · IRS3 +3: 중대성평가 결과 고침 둘(읽기·저장) · 고친 판 엑셀(③)
    # · K1b-1 +7: 사업장 6 · 코드 목록 읽기 1
    # · K1b-2b +2: 인덱스 선택 둘(트리·저장)
    # · S12a +9: Scope 1·2 입력 아홉(풀기는 운영 관리자 칸)
    # · DVX1 +2: 데이터 검증 EDK 엑셀 둘(읽기·양식)
    # · RP1 +5: 원고작성 다섯
    # · RP2d +2: 원고작성 목록·docx
    # · RP2c +1: 원고작성 목차 차이
    # · RPS1 +1: 원고작성 프로젝트 실행 목록
    # · S12a-2 +2: 입력주기·히스토리 복구(계수 바꿈은 운영 관리자 칸)
    # · S3K1 +2: inventory_scope3_template · inventory_scope3_result_get(회사 업무)
    # · S12a-3 +1: inventory_scope12_dashboard(회사 업무)
    # · S12b-1 +2: inventory_scope12_template·inventory_scope12_export(회사 업무)
    # · S12b-2 +1: inventory_scope12_upload(회사 업무)
    # · S3K2a +2: inventory_scope3_year_get · inventory_scope3_lock(회사 업무 — 풀기는 운영 관리자 칸)
    # · S3K2b-1 +4: Scope 3 줄 덧판(제외·복구·지금 상태·히스토리)
    # · S3K2b-2 +1: Scope 3 계수 수정
    # · S3D1 +1: inventory_scope3_export(회사 업무)
    assert {OPERATION_POLICY[op] for op in COMPANY_WORK_OPERATIONS} == {COMPANY}
    assert {(op, kind): is_allowed(op, kind=kind) for op in COMPANY_WORK_OPERATIONS for kind in KINDS} == {
        (op, kind): True for op in COMPANY_WORK_OPERATIONS for kind in KINDS
    }
    assert forbidden_message("core_documents_list") == "이 일은 회사 업무를 하는 사용자만 한다"


def test_the_company_work_is_not_the_self_cell() -> None:
    """회사 업무 칸과 자기 계정 칸은 섞이지 않는다: 이름이 겹치지 않고, is_initial 에 열린 것은 자기 칸뿐이다."""
    assert COMPANY != permissions.SELF
    assert not COMPANY_WORK_OPERATIONS & SELF_OPERATIONS
    assert not COMPANY_WORK_OPERATIONS & INITIAL_ALLOWED  # 비밀번호를 바꾸기 전의 운영 관리자에게 열리지 않는다
    assert {OPERATION_POLICY[op] for op in SELF_OPERATIONS} == {permissions.SELF}


def test_the_operator_runs_greenwash_translation_dataverify_and_materiality() -> None:
    """운영 관리자가 만들고 보는 실행의 모듈(결정 MARC-ENT-374·380 — 그린워싱·영문번역, 390 — 데이터 검증). runs 의
    경로가 이것을 읽는다. 419 — 중대성평가. S3K1 — Scope 3 코랩(inventory.scope3)."""
    assert (
        frozenset({"greenwash", "translation", "dataverify", "materiality", "drafting", "inventory.scope3"})
        == OPERATOR_RUN_MODULES
    )


def test_a_customer_is_refused_every_operator_cell() -> None:
    refused = {op for op in OPERATOR_OPERATIONS if not is_allowed(op, kind="service")}
    assert refused == OPERATOR_OPERATIONS
    assert all(is_allowed(op, kind="admin") for op in OPERATOR_OPERATIONS)  # 분모: 운영 관리자는 지난다


def test_the_three_user_admin_cells_are_the_same() -> None:
    """운영 관리자 동작(사용자 관리·감사 기록·실행 기록)은 한 칸(운영 관리자)이다.
    user/service/permissions 의 can_manage_customer_users 가 사용자 관리 넷을 함께 읽는다."""
    assert {OPERATION_POLICY[op] for op in OPERATOR_OPERATIONS} == {OPERATOR}
    assert set(ALSO_INSIDE) == OPERATOR_OPERATIONS
    assert not OPERATOR_OPERATIONS & INITIAL_ALLOWED  # 바꾸기 전의 운영 관리자에게 열림이 아니다(c-0-3)


def test_no_cell_is_proposed() -> None:
    """가안(proposed) 칸은 0 이다. 결정 MARC-ENT-276 의 2 에 따른 기대 변경(AUTHZ1): LLM 경로의 「편집자 이상」은
    1차에서 고객사 사용자로 읽는다 — 분류 칸은 회사 동작과 같은 CUSTOMER 다."""
    assert [field.name for field in fields(Policy)] == ["needs"]  # 가안 표시 칸이 없다
    assert OPERATION_POLICY["inventory_scope3_classify"] == CUSTOMER


def test_an_unknown_operation_is_a_key_error() -> None:
    with pytest.raises(KeyError):
        needs_of("nope")
    with pytest.raises(KeyError):
        is_allowed("nope", kind="service")


def test_the_message_names_who_may_do_it() -> None:
    assert forbidden_message("inventory_calc") == "이 일은 고객사 사용자만 한다"


def test_the_functions_read_the_table_each_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(OPERATION_POLICY, "accounts_me", OPERATOR)
    assert (is_allowed("accounts_me", kind="service"), needs_of("accounts_me")) == (False, "operator")
    assert is_allowed("accounts_me", kind="admin")
    assert forbidden_message("accounts_me") == "이 일은 운영 관리자만 한다"
    monkeypatch.setitem(OPERATION_POLICY, "accounts_me", CUSTOMER)
    assert is_allowed("accounts_me", kind="service")  # 분모: 되돌리면 지난다


def test_initial_users_reach_only_these_operations() -> None:
    """is_initial 의 주체는 이 둘만(공개 셋은 인증이 없어 표 밖). 나머지 인증 동작은 전부 막힌다(기본 닫힘)."""
    assert {"user_me", "user_password_change"} == INITIAL_ALLOWED
    authenticated = authenticated_operations()
    assert authenticated >= INITIAL_ALLOWED
    assert (
        len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 158  # GRJ1 +1 · GE1b +1
        # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
        # · RM1c ③ +1: GET /runs/{run_id}/segments
    )  # 분모: 막힌 수(G1b-1 +1 · X1b-2a +2, 감독 c1 허락 · AS2a +2 · AD4S +1 · AD4D +1 · RF1 +1)
    # · TR2 +1: translation_result_get
    # · DV1e +1: dataverify_result_get
    # · DV1g +1: dataverify_runs_list
    # · TR3a +2: translation_glossary_read · translation_glossary_template
    # · TR3b +3: translation_batches_list · translation_batch_get · translation_batch_archive
    # · TR4 +7: translation_ai_setting_* 일곱
    # · IR3b +1: materiality_result_get
    # · DVA1 +7: dataverify_ai_setting_* 일곱
    # · IR3c +1: materiality_runs_list
    # · TRP6 +1: translation_document_pages
    # · TRS3 +1: translation_layout_get
    # · IRW2 +1: materiality_value_chain_read
    # · IRS3 +3: materiality_result_edits_get · materiality_result_edits_post · materiality_report_get(③)
    # · IR4 +7: materiality_ai_setting_* 일곱
    # · K1b-1 +11: organization_branches_* 여섯 · organization_facility_codes_list
    #   · organization_admin_facility_codes_* 넷
    # · K1b-2a +12: inventory_admin_ghg_* 열둘
    # · K1b-2b +2: inventory_scope12_index_tree · inventory_scope12_index_selections_save
    # · S12a +10: inventory_scope12_* 열(Scope 1·2 입력 아홉 · 잠금 풀기)
    # · DVX1 +2: dataverify_edk_read · dataverify_edk_template
    # · RP1 +5: drafting_* 다섯
    # · RP2c +1: drafting_outline_changes
    # · RPS1 +1: drafting_project_runs
    # · S12a-2 +3: inventory_scope12_period_save · row_factor_save · history_restore
    # · RPA1 +7: drafting_ai_setting_* 일곱
    # · S3K1 +2: inventory_scope3_template · inventory_scope3_result_get(회사 업무)
    # · S12a-3 +1: inventory_scope12_dashboard(회사 업무)
    # · S12b-1 +2: inventory_scope12_template·inventory_scope12_export(회사 업무)
    # · S12b-2 +1: inventory_scope12_upload(회사 업무)
    # · S3K2a +3: inventory_scope3_year_get · inventory_scope3_lock · inventory_scope3_unlock
    # · S3K2b-1 +4: Scope 3 줄 덧판(제외·복구·지금 상태·히스토리)
    # · S3K2b-2 +1: Scope 3 계수 수정
    # · S3D1 +1: inventory_scope3_export(회사 업무)


def test_self_cells_open_to_both_kinds() -> None:
    assert {(op, kind): is_allowed(op, kind=kind) for op in SELF_OPERATIONS for kind in KINDS} == {
        (op, kind): True for op in SELF_OPERATIONS for kind in KINDS
    }


def routes() -> dict[str, tuple[Path, ast.FunctionDef]]:
    """operation_id 가 데코레이터에 글자로 적힌 경로 함수 전부(esgapi/*/service/apis/*.py)."""
    found: dict[str, tuple[Path, ast.FunctionDef]] = {}
    for path in sorted(ESGAPI.glob("*/service/apis/*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                for keyword in decorator.keywords:
                    if keyword.arg == "operation_id":
                        assert isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str), path
                        assert keyword.value.value not in found, keyword.value.value
                        found[keyword.value.value] = (path, node)
    return found


def first_statement(function: ast.FunctionDef) -> ast.stmt:
    body = function.body
    is_docstring = (
        isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    )
    return body[1] if is_docstring else body[0]


def checker_calls(node: ast.AST) -> list[tuple[str, list[object]]]:
    """그 마디 아래에서 권한 함수(permitted_session·permitted)를 부른 것: (이름, 글자로 적힌 인자들)."""
    calls: list[tuple[str, list[object]]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id in CHECKERS:
            calls.append((child.func.id, [arg.value for arg in child.args if isinstance(arg, ast.Constant)]))
    return calls


def test_each_route_checks_its_own_operation_id_first() -> None:
    found = routes()
    assert {op for op in found if op in OPERATION_POLICY} == set(OPERATION_POLICY)
    for op, (path, function) in found.items():
        where = f"{path.name}:{function.name}"
        everywhere = checker_calls(function)
        if op not in OPERATION_POLICY or op in INSIDE:
            assert everywhere == [], where  # 인증 없는 경로와 사업장 둘은 경로에서 부르지 않는다
            continue
        first = first_statement(function)
        value = first.value if isinstance(first, ast.Assign | ast.Expr) else None
        assert isinstance(value, ast.Call), where  # 첫 문장이 호출 하나다(다른 식에 싸여 있지 않다)
        assert isinstance(value.func, ast.Name) and value.func.id in CHECKERS, where
        assert [arg.value for arg in value.args if isinstance(arg, ast.Constant)] == [op], where
        assert everywhere == [(value.func.id, [op])], where  # 한 번만, 자기 이름으로만


def test_the_two_site_routes_reach_the_table_inside_their_selector_and_service() -> None:
    """사업장 둘은 경로가 아니라 Selector·Service 안에서 본다. 그 함수가 권한 함수를 부르는지 파일을 읽어 본다."""
    found = routes()
    for op, (relative, function_name, checker) in INSIDE.items():
        route = found[op][1]
        called_by_route = {
            child.func.attr
            for child in ast.walk(route)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
        }
        assert function_name in called_by_route, op
        tree = ast.parse((ESGAPI / relative).read_text(encoding="utf-8"))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function_name)
        names = {
            child.func.id
            for child in ast.walk(function)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
        }
        assert checker in names, (op, relative)


def test_the_table_file_is_pure() -> None:
    tree = ast.parse(Path(permissions.__file__).read_text(encoding="utf-8"))
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert imported == {"dataclasses", "typing", "esgapi.core.auth.principal"}


def test_the_password_hasher_is_pbkdf2() -> None:
    """제품의 해시기는 Django 기본(PBKDF2-SHA256)이다. 업무 층의 테스트가 MD5 로 바꾸는 것은 그 테스트 안에서뿐이다."""
    assert make_password("x").startswith("pbkdf2_sha256$")


def test_the_user_admin_routes_also_reach_the_table_inside() -> None:
    """사용자 관리 셋(K2c)은 경로의 첫 문장이 permitted 이고(위의 검사), 그 경로가 부르는 Selector·Service·Action 도
    첫 문장에서 권한 함수를 부른다(명령이 같은 service·action 을 부른다 — actor_kind)."""
    found = routes()
    for op, (relative, function_name, checker) in ALSO_INSIDE.items():
        route = found[op][1]
        called_by_route = {
            child.func.attr
            for child in ast.walk(route)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
        }
        assert function_name in called_by_route, op
        assert checker_calls(route) == [("permitted", [op])], op
        tree = ast.parse((ESGAPI / relative).read_text(encoding="utf-8"))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function_name)
        first = first_statement(function)
        assert isinstance(first, ast.If), (op, relative)  # 첫 문장이 권한 검사다(읽기·쓰기 앞)
        names = {
            child.func.id
            for child in ast.walk(first.test)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
        }
        assert checker in names, (op, relative)
