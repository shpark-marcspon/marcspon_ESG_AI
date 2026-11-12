"""인증 있는 동작 모두가 저마다 자기 operationId 로 권한 표(core/permissions.py)를 읽는지를 진짜 DB 로 잰다. 업무 층.

재는 법: 표의 한 칸을 운영 관리자 몫(OPERATOR)으로 바꿔 끼우면 고객사 사용자(쿠키 세션 — 역할과 무관)의 같은
요청이 403 `forbidden` 이 된다(역할 둘 — 사용자 결정 2026-10-15 14:46. 운영 관리자 칸은 K2c 가 단다).
이것이 잡는 것: 경로가 표를 안 읽는다(상수로 본다, 표의 사본을 읽는다, 모듈을 들일 때 값을 굳혔다) ·
남의 operationId 로 읽는다 · 권한보다 다른 검사가 앞이다(저장소 503, 조회 404 …).
★ 보는 것은 상태와 `error.code` 뿐이다(문장은 순수 층 test_permissions.py 가 본다).

core 는 업무 모듈을 import 하지 않는다(계약 가). 로그인은 tests.support.http.login, 테넌트는 뿌리 conftest 의 tenants.
자기 계정의 동작 둘(user_me·user_password_change, 칸 SELF)은 Bearer 만 받는다 — 고객사 사용자의 access 로 보낸다
(tests.support.http.customer_bearer 가 사용자를 만들고 비밀번호를 한 번 바꿔 is_initial 을 끈다).
사용자 관리 셋(user_list·user_create·user_password_reset, 칸 OPERATOR — K2c)은 운영 관리자의 access 로 보낸다(core 의
토큰 함수로 낸다 — 인증은 DB 를 읽지 않는다). 칸을 거꾸로 CUSTOMER 로 바꾸면 운영 관리자가 403 이다.
회사 업무 42(칸 COMPANY — 결정 MARC-ENT-374·380·390)는 운영 관리자의 Bearer 도 지난다(작업 회사는 core/auth/bearer.py 의
포트 — 여기서는 tenant-a 하나로 바꿔 끼운다). 칸을 CUSTOMER 로 낮추면 운영 관리자가 403 이다.
"""

from typing import Any
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import get_resolver

from esgapi.core.auth import bearer as bearer_module
from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.conf import app_config, now
from esgapi.core.permissions import COMPANY, CUSTOMER, OPERATION_POLICY, OPERATOR
from tests.support.http import bearer, customer_bearer, login

pytestmark = pytest.mark.django_db

SOME_ID = "9000000000000000000"  # 그런 문서는 없다(숫자 id. 404 까지 가면 권한을 지난 것이다)
# operationId → (메서드, 경로, 본문). editor 가 보내면 꼴 검사와 권한을 지나는 가장 작은 요청이다.
# K1b-2a 온실가스 풀의 본문(지어낸 값 — 뻔한 가짜 수). 없는 부모·잎이라 404 까지 간다.
GHG_UNIT = {"kind": "mass", "unit": "kg"}
GHG_FACILITY_BODY: dict[str, Any] = {"parentId": 2_000_000_000, "facilityCodeId": 2_000_000_000, "unit": GHG_UNIT}
GHG_FACILITY_SAVE_BODY: dict[str, Any] = {"facilityCodeId": 2_000_000_000, "unit": GHG_UNIT}
GHG_FACTOR_BODY: dict[str, Any] = {
    "name": "계수",
    "source": "지어낸 출처",
    "baseYear": 2024,
    "tier": 1,
    "countryCode": "KR",
    "industryCode": "other",
    "inputUnit": GHG_UNIT,
    "gases": [{"gas": "CO2", "enabled": True, "factor": "1", "gwp": "1"}],
}
DRAFTING_OUTLINE_BODY: dict[str, Any] = {
    "nodes": [{"key": "a", "parentKey": None, "depth": 1, "title": "probe", "requirement": ""}]
}
REQUESTS: dict[str, tuple[str, str, dict[str, Any] | None]] = {
    "accounts_me": ("GET", "/api/me", None),
    "accounts_sites_list": ("GET", "/api/sites", None),
    "accounts_sites_create": ("POST", "/api/sites", {"name": "공장"}),
    "core_documents_create": ("POST", "/api/documents", {"fileName": "a.pdf", "sizeBytes": 1}),
    "core_documents_confirm": ("POST", f"/api/documents/{SOME_ID}/confirm", None),
    "core_documents_get": ("GET", f"/api/documents/{SOME_ID}", None),
    # 계약 먼저(밴드 XC)였던 둘 — 몸은 X1b-2a: 목록은 200(빈 쪽), versions 는 없는 id 라 404.
    "core_documents_list": ("GET", "/api/documents", None),
    "core_documents_versions": ("GET", "/api/documents/1/versions", None),
    # X1b-2a: 고치기는 비지 않은 바른 본문(빈 본문이면 꼴 검사 422 가 권한보다 먼저), 원본은 없는 id — 둘 다 404.
    "core_documents_update": ("PATCH", f"/api/documents/{SOME_ID}", {"reportYear": 2025}),
    "core_documents_file_get": ("GET", "/api/documents/1/file", None),
    "runs_create": ("POST", "/api/runs", {"module": "greenwash", "documentId": 1}),
    "runs_list": ("GET", "/api/runs", None),
    "runs_get": ("GET", "/api/runs/1", None),
    "runs_file_get": ("GET", "/api/runs/1/files/a.xlsx", None),
    "runs_segments_list": ("GET", "/api/runs/1/segments?step=x", None),  # RM1c ③ +1
    # 그린워싱 넷은 몸이 501 이다(권한을 지나면 501 — 아래 단언의 「400·401·403·405 아님」에 든다).
    "greenwash_result_get": ("GET", "/api/greenwash/runs/1/result", None),
    "greenwash_result2_get": ("GET", "/api/greenwash/runs/1/result2", None),  # GE1b ④
    "greenwash_review_get": ("GET", "/api/greenwash/runs/1/review", None),
    "greenwash_review_put": ("PUT", "/api/greenwash/runs/1/review", {"marks": []}),
    "greenwash_item_rejudge": ("POST", "/api/greenwash/runs/1/items/0/rejudge", None),
    "greenwash_compare_get": ("GET", "/api/greenwash/compare?base=1&target=2", None),
    # 그린워싱 계약 보탬(밴드 GC2): 보고서는 없는 실행 404, 기본 단어 목록은 200(둘 다 「400·401·403·405 아님」).
    "greenwash_report_get": ("GET", "/api/greenwash/runs/1/report", None),
    "greenwash_terms_default": ("GET", "/api/greenwash/terms/default", None),
    "greenwash_checks_get": ("GET", "/api/greenwash/checks", None),
    "translation_result_get": ("GET", "/api/translation/runs/1/result", None),
    "translation_glossary_read": ("POST", "/api/translation/glossary/read", None),
    "translation_glossary_template": ("GET", "/api/translation/glossary/template", None),
    "translation_batches_list": ("GET", "/api/translation/batches", None),
    "translation_batch_get": ("GET", "/api/translation/documents/1/batches/run-1", None),
    "translation_batch_archive": ("GET", "/api/translation/documents/1/batches/run-1/archive", None),
    "translation_document_pages": ("GET", "/api/translation/documents/1/pages", None),
    "translation_layout_get": ("GET", "/api/translation/runs/1/layout", None),
    "dataverify_result_get": ("GET", "/api/dataverify/runs/1/result", None),
    "dataverify_runs_list": ("GET", "/api/dataverify/runs", None),
    "dataverify_edk_read": ("POST", "/api/dataverify/edk/read", None),
    "dataverify_edk_template": ("GET", "/api/dataverify/edk/template", None),
    "materiality_result_get": ("GET", "/api/materiality/runs/1/result", None),
    "materiality_runs_list": ("GET", "/api/materiality/runs", None),
    "materiality_value_chain_read": ("POST", "/api/materiality/value-chain/read", None),
    # IRS3 ② 결과 고침 둘(없는 실행 — 404 까지 가면 권한을 지난 것이다)
    "materiality_result_edits_get": ("GET", "/api/materiality/runs/1/result/edits", None),
    "materiality_result_edits_post": (
        "POST",
        "/api/materiality/runs/1/result/edits",
        {
            "baseRevision": 0,
            "changes": [{"pointer": "/part2/topics/0/subtopics/0/impact/rows/0/impactDefinition", "value": "가상"}],
        },
    ),
    "materiality_report_get": ("GET", "/api/materiality/runs/1/report", None),  # IRS3 ③
    # RP1 원고작성 다섯(없는 id — 404 까지 가면 권한을 지난 것이다. 만들기는 201)
    "drafting_projects_create": ("POST", "/api/drafting/projects", {"year": 2025, "name": "probe"}),
    "drafting_project_get": ("GET", f"/api/drafting/projects/{SOME_ID}", None),
    "drafting_project_document_put": (
        "PUT",
        f"/api/drafting/projects/{SOME_ID}/document",
        {"documentId": 2_000_000_000},
    ),
    "drafting_outline_put": ("PUT", f"/api/drafting/projects/{SOME_ID}/outline", DRAFTING_OUTLINE_BODY),
    "drafting_result_get": ("GET", "/api/drafting/runs/1/result", None),
    "drafting_projects_list": ("GET", "/api/drafting/projects", None),  # RP2d
    "drafting_result_download": ("GET", "/api/drafting/runs/1/result.docx", None),  # RP2d
    "drafting_outline_changes": ("GET", f"/api/drafting/projects/{SOME_ID}/outline/changes?baseRunId=1", None),  # RP2c
    "drafting_project_runs": ("GET", f"/api/drafting/projects/{SOME_ID}/runs", None),  # RPS1
    "inventory_calc": ("POST", "/api/inventory/calc", {"rows": [], "gwpSetId": "kr-ets-decree-annex2"}),
    "inventory_scope3_shortlist": (
        "POST",
        "/api/inventory/scope3/shortlist",
        {"row": {"itemName": "합성 강판"}, "category": 1},
    ),
    # 빈 목록은 생성 모델 쪽을 건드리지 않는다.
    "inventory_scope3_classify": ("POST", "/api/inventory/scope3/classify", {"rows": []}),
    "reference_sources": ("GET", "/api/reference/sources", None),
    "reference_factors": ("GET", "/api/reference/factors", None),
    "reference_assemble": ("POST", "/api/reference/assemble", {}),
    "reference_assemble_electricity": ("POST", "/api/reference/assemble-electricity", {}),
    # 자기 계정(Bearer). 바꾸기는 지금 비밀번호가 틀린 본문 — 권한을 지나면 400 current_password_mismatch 다.
    "user_me": ("GET", "/api/users/me", None),
    "user_password_change": (
        "POST",
        "/api/users/me/password",
        {"currentPassword": "Wrong-Lantern-5932", "newPassword": "Amber-Forest-6142"},
    ),
    # 사용자 관리(Bearer, 운영 관리자). COMPANY 는 보낼 때 tenant-a 의 id 로 바꾼다.
    # 초기화는 없는 id — 권한을 지나면 404.
    "user_list": ("GET", "/api/users?companyId=COMPANY", None),
    "user_create": (
        "POST",
        "/api/users",
        {"companyId": "COMPANY", "username": "new-kim", "name": "김새", "password": "x"},
    ),
    "user_password_reset": ("POST", f"/api/users/{SOME_ID}/password-reset", {"companyId": "COMPANY", "password": "x"}),
    # 수정(UA1)도 없는 id — 권한을 지나면 404.
    "user_update": ("PATCH", f"/api/users/{SOME_ID}", {"companyId": "COMPANY", "name": "김새"}),
    # 감사 기록 조회(AU1a): 권한을 지나면 200(줄이 없어도 빈 쪽).
    "user_audit_list": ("GET", "/api/audit-logs?companyId=COMPANY", None),
    # 감사 기록의 사람 목록(AU1b-1): 권한을 지나면 200(사람이 없어도 빈 목록).
    "user_audit_actors": ("GET", "/api/audit-logs/actors?companyId=COMPANY", None),
    # 운영 관리자 실행 기록(AU1b-2): 권한을 지나면 200(실행이 없어도 빈 쪽·0 지표).
    "user_run_log_list": ("GET", "/api/run-logs?companyId=COMPANY", None),
    "user_run_log_metrics": ("GET", "/api/run-logs/metrics?companyId=COMPANY", None),
    "user_run_log_export": ("GET", "/api/run-logs/export?companyId=COMPANY", None),  # AD4S: 빈 엑셀 200
    "user_run_log_get": ("GET", f"/api/run-logs/{SOME_ID}?companyId=COMPANY", None),  # AD4D: 없는 실행이라 404
    "user_run_log_file_get": ("GET", f"/api/run-logs/{SOME_ID}/files/a.xlsx?companyId=COMPANY", None),  # RF1: 404
    # 그린워싱 AI 설정 판(G2c2): 목록·기본 판 200 · 한 판·적용은 없는 id 라 404 · 저장은 받기가 0줄 기준표를 거절해 400
    # (행 0 — 꼴 검사 다음).
    "greenwash_ai_setting_list": ("GET", "/api/ai-settings/greenwash?companyId=COMPANY", None),
    "greenwash_ai_setting_default": ("GET", "/api/ai-settings/greenwash/default", None),
    "greenwash_ai_setting_get": ("GET", f"/api/ai-settings/greenwash/{SOME_ID}?companyId=COMPANY", None),
    "greenwash_ai_setting_create": (
        "POST",
        "/api/ai-settings/greenwash?companyId=COMPANY",
        {"criteria": {"schemaVersion": "greenwash.criteria@1", "version": "probe-1", "rows": []}, "title": "probe"},
    ),
    "greenwash_ai_setting_apply": (
        "PUT",
        "/api/ai-settings/greenwash/applied?companyId=COMPANY",
        {"id": 2_000_000_000},
    ),
    # AS2a: 프롬프트·모델 읽기 — 기본 판 200 · 한 판은 없는 id 라 404.
    "greenwash_ai_setting_default_prompt_model": ("GET", "/api/ai-settings/greenwash/default/prompt-model", None),
    "greenwash_ai_setting_prompt_model": (
        "GET",
        f"/api/ai-settings/greenwash/{SOME_ID}/prompt-model?companyId=COMPANY",
        None,
    ),
    # 영문번역 AI 설정 판(TR4): 목록·기본 판 둘 200 · 한 판·적용·한 판의 프롬프트·모델은 없는 id 라 404 · 저장은 이름만
    # 보내 코드 값의 판 201.
    "translation_ai_setting_list": ("GET", "/api/ai-settings/translation?companyId=COMPANY", None),
    "translation_ai_setting_default": ("GET", "/api/ai-settings/translation/default", None),
    "translation_ai_setting_get": ("GET", f"/api/ai-settings/translation/{SOME_ID}?companyId=COMPANY", None),
    "translation_ai_setting_create": ("POST", "/api/ai-settings/translation?companyId=COMPANY", {"title": "probe"}),
    "translation_ai_setting_apply": (
        "PUT",
        "/api/ai-settings/translation/applied?companyId=COMPANY",
        {"id": 2_000_000_000},
    ),
    "translation_ai_setting_default_prompt_model": ("GET", "/api/ai-settings/translation/default/prompt-model", None),
    "translation_ai_setting_prompt_model": (
        "GET",
        f"/api/ai-settings/translation/{SOME_ID}/prompt-model?companyId=COMPANY",
        None,
    ),
    # 데이터 검증 AI 설정 판(DVA1): 영문번역과 같은 꼴 — 목록·기본 판 둘 200 · 없는 id 404 · 저장은 이름만 보내 201.
    "dataverify_ai_setting_list": ("GET", "/api/ai-settings/dataverify?companyId=COMPANY", None),
    "dataverify_ai_setting_default": ("GET", "/api/ai-settings/dataverify/default", None),
    "dataverify_ai_setting_get": ("GET", f"/api/ai-settings/dataverify/{SOME_ID}?companyId=COMPANY", None),
    "dataverify_ai_setting_create": ("POST", "/api/ai-settings/dataverify?companyId=COMPANY", {"title": "probe"}),
    "dataverify_ai_setting_apply": (
        "PUT",
        "/api/ai-settings/dataverify/applied?companyId=COMPANY",
        {"id": 2_000_000_000},
    ),
    "dataverify_ai_setting_default_prompt_model": ("GET", "/api/ai-settings/dataverify/default/prompt-model", None),
    "dataverify_ai_setting_prompt_model": (
        "GET",
        f"/api/ai-settings/dataverify/{SOME_ID}/prompt-model?companyId=COMPANY",
        None,
    ),
    # 중대성평가 IRO AI 설정 판(IR4): 데이터 검증과 같은 꼴 — 목록·기본 판 둘 200 · 없는 id 404 · 저장 201.
    "materiality_ai_setting_list": ("GET", "/api/ai-settings/materiality?companyId=COMPANY", None),
    "materiality_ai_setting_default": ("GET", "/api/ai-settings/materiality/default", None),
    "materiality_ai_setting_get": ("GET", f"/api/ai-settings/materiality/{SOME_ID}?companyId=COMPANY", None),
    "materiality_ai_setting_create": ("POST", "/api/ai-settings/materiality?companyId=COMPANY", {"title": "probe"}),
    "materiality_ai_setting_apply": (
        "PUT",
        "/api/ai-settings/materiality/applied?companyId=COMPANY",
        {"id": 2_000_000_000},
    ),
    "materiality_ai_setting_default_prompt_model": ("GET", "/api/ai-settings/materiality/default/prompt-model", None),
    "materiality_ai_setting_prompt_model": (
        "GET",
        f"/api/ai-settings/materiality/{SOME_ID}/prompt-model?companyId=COMPANY",
        None,
    ),
    # 원고작성 AI 설정 판(RPA1): 중대성평가 IRO 와 같은 꼴 — 목록·기본 판 둘 200 · 없는 id 404 · 저장 201.
    "drafting_ai_setting_list": ("GET", "/api/ai-settings/drafting?companyId=COMPANY", None),
    "drafting_ai_setting_default": ("GET", "/api/ai-settings/drafting/default", None),
    "drafting_ai_setting_get": ("GET", f"/api/ai-settings/drafting/{SOME_ID}?companyId=COMPANY", None),
    "drafting_ai_setting_create": ("POST", "/api/ai-settings/drafting?companyId=COMPANY", {"title": "probe"}),
    "drafting_ai_setting_apply": ("PUT", "/api/ai-settings/drafting/applied?companyId=COMPANY", {"id": 2_000_000_000}),
    "drafting_ai_setting_default_prompt_model": ("GET", "/api/ai-settings/drafting/default/prompt-model", None),
    "drafting_ai_setting_prompt_model": (
        "GET",
        f"/api/ai-settings/drafting/{SOME_ID}/prompt-model?companyId=COMPANY",
        None,
    ),
    # K1b-1 사업장 여섯(회사 업무): 목록 200 · 만들기 201 · 없는 id 의 하나·저장·토글·삭제 404.
    "organization_branches_list": ("GET", "/api/branches", None),
    "organization_branches_get": ("GET", f"/api/branches/{SOME_ID}", None),
    "organization_branches_create": ("POST", "/api/branches", {"name": "새 사업장"}),
    "organization_branches_save": (
        "PUT",
        f"/api/branches/{SOME_ID}",
        {"name": "새 사업장", "inventoryEnabled": True, "facilities": [], "updatedAt": "2026-01-02T03:04:05+09:00"},
    ),
    "organization_branches_inventory": ("POST", "/api/branches/inventory", {"ids": [2_000_000_000], "enabled": True}),
    "organization_branches_delete": ("POST", "/api/branches/delete", {"ids": [2_000_000_000]}),
    # K1b-1 코드 목록 읽기(회사 업무 — 작업 회사를 고르지 않는다) 200 · 운영 관리자 넷.
    "organization_facility_codes_list": ("GET", "/api/facility-codes", None),
    # K1b-2b 고객사 인덱스 선택 둘(회사 업무): 트리 200 · 빈 선택 저장 200(그 회사에 해 행 하나).
    "inventory_scope12_index_tree": ("GET", "/api/inventory/scope12/index-tree?year=2025", None),
    "inventory_scope12_index_selections_save": (
        "PUT",
        "/api/inventory/scope12/index-selections/2025",
        {"facilityNodeIds": []},
    ),
    # S12a Scope 1·2 입력 열(회사 업무 아홉 · 풀기 운영 관리자): 해·리스트 200 · 나머지는 없는 해·잎이라 404.
    "inventory_scope12_years": ("GET", "/api/inventory/scope12/years", None),
    "inventory_scope12_rows": ("GET", "/api/inventory/scope12/rows?year=2025", None),
    "inventory_scope12_index_detail": ("GET", f"/api/inventory/scope12/years/2025/indexes/{SOME_ID}", None),
    "inventory_scope12_rows_save": (
        "PUT",
        f"/api/inventory/scope12/years/2025/indexes/{SOME_ID}/sites/{SOME_ID}/rows",
        {"rows": []},
    ),
    "inventory_scope12_rows_delete": (
        "POST",
        f"/api/inventory/scope12/years/2025/indexes/{SOME_ID}/rows/delete",
        {"ids": [2_000_000_000]},
    ),
    "inventory_scope12_memo_save": (
        "PUT",
        f"/api/inventory/scope12/years/2025/indexes/{SOME_ID}/memo",
        {"memo": "메모"},
    ),
    "inventory_scope12_lock": ("POST", f"/api/inventory/scope12/years/2025/indexes/{SOME_ID}/lock", None),
    "inventory_scope12_unlock": ("DELETE", f"/api/inventory/scope12/years/2025/indexes/{SOME_ID}/lock", None),
    "inventory_scope12_decimals_save": ("PUT", "/api/inventory/scope12/years/2025/decimals", {"decimals": 2}),
    "inventory_scope12_row_history": (
        "GET",
        f"/api/inventory/scope12/years/2025/indexes/{SOME_ID}/rows/{SOME_ID}/history",
        None,
    ),
    # S12a-2: 입력주기 · 행 계수 바꿈 · 히스토리 복구
    "inventory_scope12_period_save": (
        "PUT",
        f"/api/inventory/scope12/years/2025/indexes/{SOME_ID}/sites/{SOME_ID}/period",
        {"period": "month"},
    ),
    "inventory_scope12_row_factor_save": (
        "PUT",
        f"/api/inventory/scope12/years/2025/indexes/{SOME_ID}/rows/{SOME_ID}/factor",
        {"factorId": 1, "reason": "사유"},  # 본문 id 는 정수(SOME_ID 는 경로 글자)
    ),
    "inventory_scope12_history_restore": (
        "POST",
        f"/api/inventory/scope12/years/2025/indexes/{SOME_ID}/rows/{SOME_ID}/history/{SOME_ID}/restore",
        {},
    ),
    # S3K1: Scope 3 코랩 둘(빈 양식 · 한 실행의 결과)
    "inventory_scope3_template": ("GET", "/api/inventory/scope3/template", None),
    "inventory_scope3_result_get": ("GET", "/api/inventory/scope3/runs/1/result", None),
    "inventory_scope3_original_get": ("GET", "/api/inventory/scope3/runs/1/original", None),  # S3Q1 +1
    # S12a-3: 대시보드(S1 읽기)
    "inventory_scope12_dashboard": ("GET", "/api/inventory/scope12/dashboard?year=2025", None),
    # S12b-1: 엑셀 내려받기 둘(양식·데이터)
    "inventory_scope12_template": ("GET", "/api/inventory/scope12/years/2025/template", None),
    "inventory_scope12_export": ("GET", "/api/inventory/scope12/years/2025/export", None),
    # S12b-2: 일괄 올리기(맨 바이트 본문 — 비어도 permitted 가 먼저)
    "inventory_scope12_upload": ("POST", "/api/inventory/scope12/years/2025/uploads", None),
    # S3K2a: Scope 3 연도 상태 · 카테고리 잠그기(?runId= 필수 — 없으면 422 가 403 보다 먼저) · 풀기(운영 관리자)
    "inventory_scope3_year_get": ("GET", "/api/inventory/scope3/years/2025", None),
    # S3D1: Scope 3 데이터 엑셀(R 이 없어 404 — 권한은 그 앞)
    "inventory_scope3_export": ("GET", "/api/inventory/scope3/years/2025/export", None),
    "inventory_scope3_lock": ("POST", "/api/inventory/scope3/years/2025/categories/C4/lock?runId=1", None),
    "inventory_scope3_unlock": ("DELETE", "/api/inventory/scope3/years/2025/categories/C4/lock", None),
    # S3K2b-1: Scope 3 줄 덧판 넷(몸 둘은 지어낸 줄·사유, 경로의 실행 id 도 지어낸 값)
    "inventory_scope3_rows_exclude": (
        "POST",
        "/api/inventory/scope3/runs/1/categories/C4/exclusions",
        {"rowIds": ["가상_C4!20"], "reason": "가상 사유"},
    ),
    "inventory_scope3_rows_restore": (
        "POST",
        "/api/inventory/scope3/runs/1/categories/C4/restorations",
        {"rowIds": ["가상_C4!20"], "reason": "가상 사유"},
    ),
    "inventory_scope3_edits_get": ("GET", "/api/inventory/scope3/runs/1/edits", None),
    "inventory_scope3_history_get": ("GET", "/api/inventory/scope3/runs/1/history", None),
    "inventory_scope3_row_factor": (
        "POST",
        "/api/inventory/scope3/runs/1/categories/C1/factors",
        {"rowId": "가상_C1!20", "choice": "applied", "rank": None, "custom": None, "reason": "가상 사유"},
    ),
    "organization_admin_facility_codes_list": ("GET", "/api/admin/facility-codes", None),
    "organization_admin_facility_codes_create": ("POST", "/api/admin/facility-codes", {"name": "보일러"}),
    "organization_admin_facility_codes_update": ("PATCH", f"/api/admin/facility-codes/{SOME_ID}", {"name": "보일러"}),
    "organization_admin_facility_codes_delete": ("POST", "/api/admin/facility-codes/delete", {"ids": [2_000_000_000]}),
    # K1b-2a 온실가스 풀 열둘(운영 관리자 Bearer). 경로·본문의 id 는 없는 것.
    "inventory_admin_ghg_nodes_list": ("GET", "/api/inventory/admin/ghg-index/nodes", None),
    "inventory_admin_ghg_nodes_create": (
        "POST",
        "/api/inventory/admin/ghg-index/nodes",
        {"level": "scope", "name": "범위"},
    ),
    "inventory_admin_ghg_nodes_update": ("PATCH", f"/api/inventory/admin/ghg-index/nodes/{SOME_ID}", {"name": "범위"}),
    "inventory_admin_ghg_nodes_delete": (
        "POST",
        "/api/inventory/admin/ghg-index/nodes/delete",
        {"ids": [2_000_000_000]},
    ),
    "inventory_admin_ghg_facilities_get": ("GET", f"/api/inventory/admin/ghg-index/facilities/{SOME_ID}", None),
    "inventory_admin_ghg_facilities_create": ("POST", "/api/inventory/admin/ghg-index/facilities", GHG_FACILITY_BODY),
    "inventory_admin_ghg_facilities_save": (
        "PUT",
        f"/api/inventory/admin/ghg-index/facilities/{SOME_ID}",
        GHG_FACILITY_SAVE_BODY,
    ),
    "inventory_admin_ghg_factors_create": (
        "POST",
        f"/api/inventory/admin/ghg-index/facilities/{SOME_ID}/factors",
        GHG_FACTOR_BODY,
    ),
    "inventory_admin_ghg_factors_get": ("GET", f"/api/inventory/admin/ghg-factors/{SOME_ID}", None),
    "inventory_admin_ghg_factors_save": ("PUT", f"/api/inventory/admin/ghg-factors/{SOME_ID}", GHG_FACTOR_BODY),
    "inventory_admin_ghg_factors_delete": ("POST", "/api/inventory/admin/ghg-factors/delete", {"ids": [2_000_000_000]}),
    "inventory_admin_ghg_options": ("GET", "/api/inventory/admin/ghg-options", None),
}
SELF_OPERATIONS = ("user_me", "user_password_change")
OPERATOR_OPERATIONS = (
    "user_list",
    "user_create",
    "user_password_reset",
    "user_update",
    "user_audit_list",
    "user_audit_actors",
    "user_run_log_list",
    "user_run_log_metrics",
    "user_run_log_export",
    "user_run_log_get",
    "user_run_log_file_get",
    "greenwash_ai_setting_list",
    "greenwash_ai_setting_default",
    "greenwash_ai_setting_get",
    "greenwash_ai_setting_create",
    "greenwash_ai_setting_apply",
    "greenwash_ai_setting_prompt_model",
    "greenwash_ai_setting_default_prompt_model",
    "translation_ai_setting_list",
    "translation_ai_setting_default",
    "translation_ai_setting_get",
    "translation_ai_setting_create",
    "translation_ai_setting_apply",
    "translation_ai_setting_prompt_model",
    "translation_ai_setting_default_prompt_model",
    "dataverify_ai_setting_list",
    "dataverify_ai_setting_default",
    "dataverify_ai_setting_get",
    "dataverify_ai_setting_create",
    "dataverify_ai_setting_apply",
    "dataverify_ai_setting_prompt_model",
    "dataverify_ai_setting_default_prompt_model",
    "materiality_ai_setting_list",
    "materiality_ai_setting_default",
    "materiality_ai_setting_get",
    "materiality_ai_setting_create",
    "materiality_ai_setting_apply",
    "materiality_ai_setting_prompt_model",
    "materiality_ai_setting_default_prompt_model",
    "drafting_ai_setting_list",
    "drafting_ai_setting_default",
    "drafting_ai_setting_get",
    "drafting_ai_setting_create",
    "drafting_ai_setting_apply",
    "drafting_ai_setting_prompt_model",
    "drafting_ai_setting_default_prompt_model",
    "organization_admin_facility_codes_list",  # K1b-1 코드 목록 넷
    "organization_admin_facility_codes_create",
    "organization_admin_facility_codes_update",
    "organization_admin_facility_codes_delete",
    # K1b-2a 온실가스 풀 열둘
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
    "inventory_scope12_unlock",  # S12a: 회사 경로의 운영 관리자 칸(작업 회사를 고른다)
    "inventory_scope12_row_factor_save",  # S12a-2: 같은 꼴(행 계수 바꿈)
    "inventory_scope3_unlock",  # S3K2a: 같은 꼴(Scope 3 카테고리 잠금 풀기)
)
COOKIE_OPERATIONS = sorted(set(REQUESTS) - set(SELF_OPERATIONS) - set(OPERATOR_OPERATIONS))
# 운영 관리자가 그대로 보냈을 때(권한을 지남): 목록·감사 기록·사람 목록·실행 기록 둘 200 · 만들기는 검사기가 짧은
# 비밀번호를 거절해 400 password_rejected(행 0 — 칸 검사 다음) · 초기화·수정은 없는 id 라 404 user_not_found.
OPERATOR_PASSES: dict[str, tuple[int, str | None]] = {
    "user_list": (200, None),
    "user_create": (400, "PASSWORD_REJECTED"),
    "user_password_reset": (404, "USER_NOT_FOUND"),
    "user_update": (404, "USER_NOT_FOUND"),
    "user_audit_list": (200, None),
    "user_audit_actors": (200, None),
    "user_run_log_list": (200, None),
    "user_run_log_metrics": (200, None),
    "user_run_log_export": (200, None),
    "user_run_log_get": (404, "RUN_NOT_FOUND"),
    "user_run_log_file_get": (404, "RUN_NOT_FOUND"),  # RF1
    "greenwash_ai_setting_list": (200, None),
    "greenwash_ai_setting_default": (200, None),
    "greenwash_ai_setting_get": (404, "NOT_FOUND"),
    "greenwash_ai_setting_create": (400, "CRITERIA_ROWS_FIXED"),
    "greenwash_ai_setting_apply": (404, "NOT_FOUND"),
    "greenwash_ai_setting_prompt_model": (404, "NOT_FOUND"),
    "greenwash_ai_setting_default_prompt_model": (200, None),
    "translation_ai_setting_list": (200, None),
    "translation_ai_setting_default": (200, None),
    "translation_ai_setting_get": (404, "NOT_FOUND"),
    "translation_ai_setting_create": (201, None),
    "translation_ai_setting_apply": (404, "NOT_FOUND"),
    "translation_ai_setting_prompt_model": (404, "NOT_FOUND"),
    "translation_ai_setting_default_prompt_model": (200, None),
    "dataverify_ai_setting_list": (200, None),
    "dataverify_ai_setting_default": (200, None),
    "dataverify_ai_setting_get": (404, "NOT_FOUND"),
    "dataverify_ai_setting_create": (201, None),
    "dataverify_ai_setting_apply": (404, "NOT_FOUND"),
    "dataverify_ai_setting_prompt_model": (404, "NOT_FOUND"),
    "dataverify_ai_setting_default_prompt_model": (200, None),
    "materiality_ai_setting_list": (200, None),
    "materiality_ai_setting_default": (200, None),
    "materiality_ai_setting_get": (404, "NOT_FOUND"),
    "materiality_ai_setting_create": (201, None),
    "materiality_ai_setting_apply": (404, "NOT_FOUND"),
    "materiality_ai_setting_prompt_model": (404, "NOT_FOUND"),
    "materiality_ai_setting_default_prompt_model": (200, None),
    "drafting_ai_setting_list": (200, None),
    "drafting_ai_setting_default": (200, None),
    "drafting_ai_setting_get": (404, "NOT_FOUND"),
    "drafting_ai_setting_create": (201, None),
    "drafting_ai_setting_apply": (404, "NOT_FOUND"),
    "drafting_ai_setting_prompt_model": (404, "NOT_FOUND"),
    "drafting_ai_setting_default_prompt_model": (200, None),
    # K1b-1 코드 목록 넷: 목록 200 · 만들기 201 · 없는 코드의 고침·지움 404.
    "organization_admin_facility_codes_list": (200, None),
    "organization_admin_facility_codes_create": (201, None),
    "organization_admin_facility_codes_update": (404, "NOT_FOUND"),
    "organization_admin_facility_codes_delete": (404, "NOT_FOUND"),
    # K1b-2a 온실가스 풀 열둘: 목록·선택 목록 200 · 범위 만들기 201 · 없는 노드·잎·계수 404.
    "inventory_admin_ghg_nodes_list": (200, None),
    "inventory_admin_ghg_nodes_create": (201, None),
    "inventory_admin_ghg_nodes_update": (404, "NOT_FOUND"),
    "inventory_admin_ghg_nodes_delete": (404, "NOT_FOUND"),
    "inventory_admin_ghg_facilities_get": (404, "NOT_FOUND"),
    "inventory_admin_ghg_facilities_create": (404, "NOT_FOUND"),
    "inventory_admin_ghg_facilities_save": (404, "NOT_FOUND"),
    "inventory_admin_ghg_factors_create": (404, "NOT_FOUND"),
    "inventory_admin_ghg_factors_get": (404, "NOT_FOUND"),
    "inventory_admin_ghg_factors_save": (404, "NOT_FOUND"),
    "inventory_admin_ghg_factors_delete": (404, "NOT_FOUND"),
    "inventory_admin_ghg_options": (200, None),
    # S12a: 권한은 지나고 작업 회사를 고르다 멈춘다(이 시험의 companies 는 회사 둘 — 칸을 내리면 403 은 그대로)
    "inventory_scope12_unlock": (400, "COMPANY_AMBIGUOUS"),
    "inventory_scope12_row_factor_save": (400, "COMPANY_AMBIGUOUS"),  # S12a-2: 풀기와 같은 꼴
    "inventory_scope3_unlock": (400, "COMPANY_AMBIGUOUS"),  # S3K2a: Scope 1·2 풀기와 같은 꼴
}


def send(client: Client, operation_id: str, company_id: int | None = None, **headers: Any) -> Any:
    method, path, body = REQUESTS[operation_id]
    if company_id is not None:
        path = path.replace("COMPANY", str(company_id))
        body = None if body is None else {k: company_id if v == "COMPANY" else v for k, v in body.items()}
    if method == "GET":
        return client.get(path, **headers)
    if method == "PUT":
        return client.put(path, data=body, content_type="application/json", **headers)
    if method == "PATCH":
        return client.patch(path, data=body, content_type="application/json", **headers)
    if method == "DELETE":
        return client.delete(path, **headers)
    if body is None:
        return client.post(path, **headers)
    return client.post(path, data=body, content_type="application/json", **headers)


def test_every_operation_in_the_table_has_a_request_here() -> None:
    assert set(REQUESTS) == set(OPERATION_POLICY)


@pytest.mark.parametrize("operation_id", COOKIE_OPERATIONS)
def test_raising_the_cell_makes_that_route_forbidden(
    client: Client, tenants: None, monkeypatch: pytest.MonkeyPatch, operation_id: str
) -> None:
    assert login(client)["role"] == "editor"
    # 그대로 보내면 꼴 검사와 인증과 권한을 지난다(200·201·404·409·503 은 다 된다).
    assert send(client, operation_id).status_code not in (400, 401, 403, 405)

    monkeypatch.setitem(OPERATION_POLICY, operation_id, OPERATOR)
    response = send(client, operation_id)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "FORBIDDEN")


@pytest.mark.parametrize("operation_id", SELF_OPERATIONS)
def test_raising_the_self_cell_makes_that_route_forbidden(
    client: Client, tenants: None, monkeypatch: pytest.MonkeyPatch, operation_id: str
) -> None:
    """회사 id 는 쿠키 세션의 /me 로 읽는다(core 는 organization 을 import 하지 않는다 — 계약 가)."""
    cookie = Client()
    login(cookie, tenant_id="tenant-a")
    company_id: int = cookie.get("/api/me").json()["companyId"]
    headers = bearer(customer_bearer(client, company_id=company_id, subdomain="tenant-a"))
    # 그대로 보내면 인증과 권한을 지난다(/users/me 200, 바꾸기는 지금 비밀번호 확인까지 가서 400).
    response = send(client, operation_id, **headers)
    if operation_id == "user_me":
        assert response.status_code == 200
    else:
        assert (response.status_code, response.json()["error"]["code"]) == (400, "CURRENT_PASSWORD_MISMATCH")

    monkeypatch.setitem(OPERATION_POLICY, operation_id, OPERATOR)
    response = send(client, operation_id, **headers)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "FORBIDDEN")


def operator_access() -> str:
    """운영 관리자(kind admin, 회사 없음, 비밀번호를 바꾼 뒤)의 access. 인증은 서명·만료만 본다(DB 0)."""
    claims = new_access_claims(
        user_id="1",
        kind="admin",
        level=99,
        company_id=None,
        company_is_active=None,
        is_initial=False,
        jti=uuid4(),
        now=now(),
    )
    return sign_access(claims, secret=app_config().session_secret)


@pytest.mark.parametrize("operation_id", OPERATOR_OPERATIONS)
def test_lowering_the_operator_cell_makes_that_route_forbidden_for_the_operator(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch, operation_id: str
) -> None:
    headers = bearer(operator_access())
    response = send(client, operation_id, companies[0], **headers)
    status, code = OPERATOR_PASSES[operation_id]
    assert response.status_code == status, response.content.decode()
    if code is not None:
        assert response.json()["error"]["code"] == code

    monkeypatch.setitem(OPERATION_POLICY, operation_id, CUSTOMER)
    response = send(client, operation_id, companies[0], **headers)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "FORBIDDEN")


COMPANY_WORK_OPERATIONS = sorted(op for op, policy in OPERATION_POLICY.items() if policy == COMPANY)


@pytest.mark.parametrize("operation_id", COMPANY_WORK_OPERATIONS)
def test_lowering_the_company_work_cell_makes_that_route_forbidden_for_the_operator(
    client: Client, tenants: None, monkeypatch: pytest.MonkeyPatch, operation_id: str
) -> None:
    """회사 업무 칸은 운영 관리자의 Bearer 도 꼴 검사·인증·권한을 지난다(작업 회사 tenant-a). CUSTOMER 면 403."""
    assert len(COMPANY_WORK_OPERATIONS) == 83  # 분모: 문서 7 · 실행 5 · 그린워싱 9 · 영문번역 8 · 데이터 검증 4
    # · RM1c ③ +1: 실행 구획 목록
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · 중대성평가 3(IR3b·IR3c·IRW2)
    # · IRS3 +3: 중대성평가 결과 고침 둘(읽기·저장) · 고친 판 엑셀(③)
    # · K1b-1 +7: 사업장 6 · 코드 목록 읽기 1
    # · K1b-2b +2: 인덱스 선택 둘
    # · S12a +9: Scope 1·2 입력 아홉
    # · DVX1 +2: 데이터 검증 EDK 엑셀 둘
    # · RP1 +5: 원고작성 다섯
    # · RP2d +2: 원고작성 목록·docx
    # · RP2c +1: 원고작성 목차 차이
    # · RPS1 +1: 원고작성 프로젝트 실행 목록
    # · S12a-2 +2: 입력주기·히스토리 복구
    # · S12a-3 +1: 대시보드(S1 읽기)
    # · S12b-1 +2: 엑셀 내려받기 둘
    # · S12b-2 +1: 일괄 올리기
    # · S3K2a +2: Scope 3 연도 상태·잠그기
    # · S3D1 +1: Scope 3 데이터 엑셀
    # · GRJ1 +1: 그린워싱 재판단
    cookie = Client()
    login(cookie, tenant_id="tenant-a")
    company_id: int = cookie.get("/api/me").json()["companyId"]
    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: company_id)
    headers = bearer(operator_access())
    response = send(client, operation_id, **headers)
    assert response.status_code not in (400, 401, 403, 405), response.content.decode()

    monkeypatch.setitem(OPERATION_POLICY, operation_id, CUSTOMER)
    response = send(client, operation_id, **headers)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "FORBIDDEN")
