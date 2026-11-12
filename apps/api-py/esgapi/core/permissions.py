"""권한 표: 인증 있는 동작(operationId)마다 그 일을 누가 하는가. 순수하다(표준 라이브러리와 core/auth/principal 만).

필요한 것은 넷이다(사용자 결정 2026-10-15 14:46 — 1차 역할은 운영 관리자·고객사 사용자 둘, RPT-21 rev 2):
    customer   고객사 사용자(kind service)만 — 회사 경로 중 회사 업무가 아닌 것(계정·옛 사업장 /sites·인벤토리·
               기준 자료)
    operator   운영 관리자(kind admin)만 — 운영 관리자 경로(사용자 관리 넷·감사 기록 조회)
    self       둘 다 — 자기 계정의 동작(/users/me·비밀번호 바꾸기)
    company    둘 다 — 회사 업무(문서·실행·그린워싱·영문번역·데이터 검증 결과·목록·중대성평가 IRO 결과·목록·가치사슬·
               사업장 /branches·자산/시설 코드 목록 읽기 — K1b-1, MARC-ENT-469 3·4).
               원고작성 프로젝트·목차·결과(RP1)도 회사 업무다.
               운영 관리자는 작업 회사로 한다
               (결정 MARC-ENT-374·380 — 회사는 core/auth/bearer.py 의 company_of 가 정한다. self 와 섞지 않는다)
「표 둘」(고객사 사용자 표·운영 관리자 표)을 사전 하나에 값 셋으로 적는다: 동작마다 정확히 한 칸이다(겹침 0·빠짐 0).
level(99/89/79)은 표에 없다 — 고객사 안 level 구분은 2차다. 더할 때는 Policy 에 minimum_level 칸 하나로 충분하다.
쿠키 세션의 역할(admin·editor·viewer)은 권한에 쓰지 않는다 — 쿠키 세션의 주체는 늘 고객사 사용자다
(core/auth/principal.py).

생성 모델을 부르는 inventory_scope3_classify 도 고객사 사용자다(결정 MARC-ENT-276 의 2 — 「편집자 이상」 = 1차의 고객사
사용자). 가안(proposed) 표시는 걷었다.
★ core 에 있는 까닭: 모든 앱의 경로가 같은 표를 읽어야 하고 core 는 업무 모듈을 import 하지 못한다(계약 가).
  그래서 열쇠는 import 가 아니라 operationId 의 글자다. 표와 계약(generated/openapi.json)이 어긋나면
  core/tests/test_permissions.py 가 빨갛다(동작을 더하고 이 표에 줄을 안 더하면 거기서 걸린다).
  앱별 권한 모듈(organization/service/permissions 등)은 이 표를 읽기만 한다 — 사본 표를 두지 않는다.
★ 예외를 던지지 않는다(core/exceptions.py 는 django·ninja 를 들인다). 403 으로 바꾸는 것은 경로 쪽이다.
"""

from dataclasses import dataclass
from typing import Final, Literal

from esgapi.core.auth.principal import Kind

Needs = Literal["customer", "operator", "self", "company"]  # 고객사 / 운영 관리자 / 둘 다(자기 동작) / 둘 다(회사 업무)


@dataclass(frozen=True, slots=True)
class Policy:
    needs: Needs


CUSTOMER: Final = Policy("customer")
OPERATOR: Final = Policy("operator")
SELF: Final = Policy("self")
COMPANY: Final = Policy("company")

OPERATION_POLICY: Final[dict[str, Policy]] = {
    "accounts_me": CUSTOMER,
    "accounts_sites_list": CUSTOMER,
    "accounts_sites_create": CUSTOMER,
    # 회사 업무 83(문서 7·실행 5·그린워싱 9·영문번역 8·데이터 검증 4·중대성평가 6·원고작성 9·사업장 6·코드 목록 1
    # ·인덱스 선택 2 ·Scope 1·2 입력 11 ·엑셀 2 ·올리기 1 ·대시보드 1 ·인벤토리 Scope 3 11): 두 kind 다 —
    # 운영 관리자는 작업 회사로.
    "core_documents_create": COMPANY,
    "core_documents_confirm": COMPANY,
    "core_documents_get": COMPANY,
    # 계약 먼저(밴드 XC)였던 둘 — 몸은 X1b-2a. 고치기·원본 내려받기도 X1b-2a.
    "core_documents_list": COMPANY,
    "core_documents_versions": COMPANY,
    "core_documents_update": COMPANY,
    "core_documents_file_get": COMPANY,
    "runs_create": COMPANY,
    "runs_list": COMPANY,
    "runs_get": COMPANY,
    "runs_file_get": COMPANY,
    "runs_segments_list": COMPANY,  # RM1c 구획 목록(실행 하나와 같은 회사 업무)
    "greenwash_result_get": COMPANY,
    "greenwash_result2_get": COMPANY,  # GE1b ④ 2차 엔진 결과(결과 읽기와 같은 회사 업무)
    "greenwash_review_get": COMPANY,
    # 검토 확정·잠금은 회사 업무를 하는 누구나(감독 덧붙임 2 — sid:MARC-TICK-74 노트의 사용자 결정. 결재자 89 는 2차).
    "greenwash_review_put": COMPANY,
    "greenwash_item_rejudge": COMPANY,  # GRJ1 재판단 만들기(검토 PUT 과 같은 회사 업무)
    "greenwash_compare_get": COMPANY,
    "greenwash_report_get": COMPANY,
    "greenwash_terms_default": COMPANY,
    "greenwash_checks_get": COMPANY,
    "translation_result_get": COMPANY,
    "translation_glossary_read": COMPANY,
    "translation_glossary_template": COMPANY,
    "translation_batches_list": COMPANY,
    "translation_batch_get": COMPANY,
    "translation_batch_archive": COMPANY,
    "translation_document_pages": COMPANY,
    "translation_layout_get": COMPANY,
    "dataverify_result_get": COMPANY,
    "dataverify_runs_list": COMPANY,
    "dataverify_edk_read": COMPANY,
    "dataverify_edk_template": COMPANY,
    "materiality_result_get": COMPANY,
    "materiality_runs_list": COMPANY,
    "materiality_value_chain_read": COMPANY,
    # IRS3 ② 결과 글 칸 고침(읽기·저장 — greenwash_review_put 과 같은 회사 업무)
    "materiality_result_edits_get": COMPANY,
    "materiality_result_edits_post": COMPANY,
    "materiality_report_get": COMPANY,  # IRS3 ③ 고친 판 최종 엑셀
    # 원고작성(RP1 — 프로젝트 넷·결과 하나. 운영 관리자는 작업 회사로, MARC-ENT-419 꼴)
    "drafting_projects_create": COMPANY,
    "drafting_project_get": COMPANY,
    "drafting_project_document_put": COMPANY,
    "drafting_outline_put": COMPANY,
    "drafting_result_get": COMPANY,
    "drafting_projects_list": COMPANY,  # RP2d
    "drafting_result_download": COMPANY,  # RP2d
    "drafting_outline_changes": COMPANY,  # RP2c
    "drafting_project_runs": COMPANY,  # RPS1
    # 사업장(K1b-1 — MARC-ENT-469 4: 고객사 사용자가 하고 운영 관리자도 작업 회사로 대신 한다).
    # 옛 /sites 둘은 CUSTOMER 그대로.
    "organization_branches_list": COMPANY,
    "organization_branches_get": COMPANY,
    "organization_branches_create": COMPANY,
    "organization_branches_save": COMPANY,
    "organization_branches_inventory": COMPANY,
    "organization_branches_delete": COMPANY,
    # 자산/시설 코드 목록 읽기(K1b-1 — MARC-ENT-469 3: 공통 목록, 읽기는 로그인 둘 다). 작업 회사를 고르지 않는다.
    "organization_facility_codes_list": COMPANY,
    # 고객사 인덱스 선택(K1b-2b — MARC-ENT-469 4·374: 고객사 사용자가 하고 운영 관리자도 작업 회사로 대신 한다).
    "inventory_scope12_index_tree": COMPANY,
    "inventory_scope12_index_selections_save": COMPANY,
    # Scope 1·2 입력(S12a — MARC-ENT-469 4: 고객사 사용자가 입력·메모·잠그기, 운영 관리자도 작업 회사로 대신 한다).
    "inventory_scope12_years": COMPANY,
    "inventory_scope12_rows": COMPANY,
    "inventory_scope12_index_detail": COMPANY,
    "inventory_scope12_rows_save": COMPANY,
    "inventory_scope12_rows_delete": COMPANY,
    "inventory_scope12_memo_save": COMPANY,
    "inventory_scope12_lock": COMPANY,
    "inventory_scope12_decimals_save": COMPANY,
    "inventory_scope12_row_history": COMPANY,
    # S12a-2: 입력주기(S7)·히스토리 복구(S12) — 회사 업무. 복구의 계수 줄은 action 이 row_factor_save 칸으로 본다.
    "inventory_scope12_period_save": COMPANY,
    "inventory_scope12_history_restore": COMPANY,
    "inventory_scope12_dashboard": COMPANY,  # S12a-3 대시보드(S1) 읽기 — 회사 업무
    # S12b-1: Scope 1·2 엑셀 내려받기 둘(양식·데이터 — 읽기만). 운영 관리자도 작업 회사로.
    "inventory_scope12_template": COMPANY,
    "inventory_scope12_export": COMPANY,
    # S12b-2: Scope 1·2 일괄 올리기(맨 바이트 본문). 운영 관리자도 작업 회사로.
    "inventory_scope12_upload": COMPANY,
    # Scope 3 코랩 흐름(S3K1 — 469-4 「대신하기」 꼴): 빈 양식 내려받기·한 실행의 결과. 운영 관리자도 작업 회사로.
    "inventory_scope3_template": COMPANY,
    "inventory_scope3_result_get": COMPANY,
    "inventory_scope3_original_get": COMPANY,  # S3Q1: 그 실행에 올린 엑셀 원본 내려받기(읽기) — 같은 꼴
    # S3K2a: Scope 3 연도 상태 읽기·카테고리 잠그기(469 2 — 고객사가 건다, 운영 관리자 대행) — 회사 업무.
    "inventory_scope3_year_get": COMPANY,
    "inventory_scope3_export": COMPANY,
    "inventory_scope3_lock": COMPANY,
    # S3K2b-1: Scope 3 줄 덧판 넷(산정 제외·복구·지금 상태·히스토리 — 469 4 대신하기) — 회사 업무.
    "inventory_scope3_rows_exclude": COMPANY,
    "inventory_scope3_rows_restore": COMPANY,
    "inventory_scope3_edits_get": COMPANY,
    "inventory_scope3_history_get": COMPANY,
    # S3K2b-2: Scope 3 줄 계수 수정 — 회사 업무(469 4 대신하기 · RPT-21 「고객사 안 관리자·일반 구분은 2차」). Scope 1·2
    # 계수 바꿈(아래 OPERATOR)과 다르다: 기획이 Scope 3 수정을 고객사 몫으로 그렸다.
    "inventory_scope3_row_factor": COMPANY,
    # 잠금 풀기는 운영 관리자만(MARC-ENT-469 2) — 회사 경로라 작업 회사를 고른다(company_of). action 첫 문장도 이 표.
    "inventory_scope12_unlock": OPERATOR,
    # S3K2a: Scope 3 카테고리 잠금 풀기도 운영 관리자만(469 2 · RPT-21 §3.3) — 같은 꼴(작업 회사, action 첫 문장도).
    "inventory_scope3_unlock": OPERATOR,
    # 행 하나의 계수 바꿈(S9·S11 — MARC-ENT-469: 계수 수정은 운영 관리자) — 풀기와 같은 꼴(작업 회사). action 첫 문장도.
    "inventory_scope12_row_factor_save": OPERATOR,
    "inventory_calc": CUSTOMER,
    "inventory_scope3_shortlist": CUSTOMER,
    # 생성 모델을 부른다(비용이 든다). 고객사 사용자 — 결정 MARC-ENT-276 의 2.
    "inventory_scope3_classify": CUSTOMER,
    "reference_sources": CUSTOMER,
    "reference_factors": CUSTOMER,
    "reference_assemble": CUSTOMER,
    "reference_assemble_electricity": CUSTOMER,
    # 자기 계정의 동작(K2a): 두 kind 다. is_initial 이어도 열린다(INITIAL_ALLOWED).
    "user_me": SELF,
    "user_password_change": SELF,
    # 고객사 사용자 관리(K2c·UA1): 운영 관리자만(사용자 결정 14:46). 넷이 같은 칸이다(user/service/permissions).
    "user_list": OPERATOR,
    "user_create": OPERATOR,
    "user_password_reset": OPERATOR,
    "user_update": OPERATOR,
    # 감사 기록 조회(AU1a — AD-05): 운영 관리자만.
    "user_audit_list": OPERATOR,
    # 감사 기록에 나온 사람 목록(AU1b-1 — AD-05 의 사람 고르기): 운영 관리자만.
    "user_audit_actors": OPERATOR,
    # 운영 관리자 실행 기록(AU1b-2 — AD-04 의 목록과 이번 달 지표): 운영 관리자만.
    "user_run_log_list": OPERATOR,
    "user_run_log_metrics": OPERATOR,
    # 실행 기록 엑셀 내보내기(AD4S — AD-04 「엑셀 내보내기」): 운영 관리자만.
    "user_run_log_export": OPERATOR,
    # 실행 상세(AD4D — AD-04a 단계별 시각·토큰·비용·결과 파일): 운영 관리자만.
    "user_run_log_get": OPERATOR,
    "user_run_log_file_get": OPERATOR,  # RF1 — 실행의 출력 파일 받기(MARC-ENT-395, 모든 모듈)
    # 그린워싱 AI 설정 판(G2c2 — AD-02, 결정 MARC-ENT-341·244·193): 운영 관리자만. 목록·기본 판·한 판·저장·적용
    # ·프롬프트·모델 둘(AS2a).
    "greenwash_ai_setting_list": OPERATOR,
    "greenwash_ai_setting_default": OPERATOR,
    "greenwash_ai_setting_get": OPERATOR,
    "greenwash_ai_setting_create": OPERATOR,
    "greenwash_ai_setting_apply": OPERATOR,
    "greenwash_ai_setting_prompt_model": OPERATOR,
    "greenwash_ai_setting_default_prompt_model": OPERATOR,
    # 영문번역 AI 설정 판(TR4 — AD-02, 결정 MARC-ENT-399·387): 운영 관리자만. 그린워싱 일곱과 같은 꼴.
    "translation_ai_setting_list": OPERATOR,
    "translation_ai_setting_default": OPERATOR,
    "translation_ai_setting_get": OPERATOR,
    "translation_ai_setting_create": OPERATOR,
    "translation_ai_setting_apply": OPERATOR,
    "translation_ai_setting_prompt_model": OPERATOR,
    "translation_ai_setting_default_prompt_model": OPERATOR,
    # 데이터 검증 AI 설정 판(DVA1 — AD-02, 결정 MARC-ENT-399·387): 운영 관리자만. 영문번역 일곱과 같은 꼴.
    "dataverify_ai_setting_list": OPERATOR,
    "dataverify_ai_setting_default": OPERATOR,
    "dataverify_ai_setting_get": OPERATOR,
    "dataverify_ai_setting_create": OPERATOR,
    "dataverify_ai_setting_apply": OPERATOR,
    "dataverify_ai_setting_prompt_model": OPERATOR,
    "dataverify_ai_setting_default_prompt_model": OPERATOR,
    # 중대성평가 IRO AI 설정 판(IR4 — 결정 MARC-ENT-399·381): 운영 관리자만. 데이터 검증 일곱과 같은 꼴.
    "materiality_ai_setting_list": OPERATOR,
    "materiality_ai_setting_default": OPERATOR,
    "materiality_ai_setting_get": OPERATOR,
    "materiality_ai_setting_create": OPERATOR,
    "materiality_ai_setting_apply": OPERATOR,
    "materiality_ai_setting_prompt_model": OPERATOR,
    "materiality_ai_setting_default_prompt_model": OPERATOR,
    # 원고작성 AI 설정 판(RPA1 — 결정 MARC-ENT-399·381): 운영 관리자만. 중대성평가 IRO 일곱과 같은 꼴.
    "drafting_ai_setting_list": OPERATOR,
    "drafting_ai_setting_default": OPERATOR,
    "drafting_ai_setting_get": OPERATOR,
    "drafting_ai_setting_create": OPERATOR,
    "drafting_ai_setting_apply": OPERATOR,
    "drafting_ai_setting_prompt_model": OPERATOR,
    "drafting_ai_setting_default_prompt_model": OPERATOR,
    # 자산/시설 코드 목록 쓰기·운영 관리자 목록(K1b-1 — MARC-ENT-469 3: 모든 고객사 공통 하나, 고치는 것은
    # 운영 관리자만).
    "organization_admin_facility_codes_list": OPERATOR,
    "organization_admin_facility_codes_create": OPERATOR,
    "organization_admin_facility_codes_update": OPERATOR,
    "organization_admin_facility_codes_delete": OPERATOR,
    # 온실가스 인덱스 풀·시설별 배출계수 풀(K1b-2a — MARC-ENT-469 3·MARC-ENT-478: 모든 고객사 공통 하나, 고치는 것은
    # 운영 관리자만).
    "inventory_admin_ghg_nodes_list": OPERATOR,
    "inventory_admin_ghg_nodes_create": OPERATOR,
    "inventory_admin_ghg_nodes_update": OPERATOR,
    "inventory_admin_ghg_nodes_delete": OPERATOR,
    "inventory_admin_ghg_facilities_get": OPERATOR,
    "inventory_admin_ghg_facilities_create": OPERATOR,
    "inventory_admin_ghg_facilities_save": OPERATOR,
    "inventory_admin_ghg_factors_create": OPERATOR,
    "inventory_admin_ghg_factors_get": OPERATOR,
    "inventory_admin_ghg_factors_save": OPERATOR,
    "inventory_admin_ghg_factors_delete": OPERATOR,
    "inventory_admin_ghg_options": OPERATOR,
}

# is_initial(명령으로 만들었거나 초기화한 계정)인 주체가 할 수 있는 동작. 나머지는 전부 403 password_change_required
# (기본 닫힘 — 동작을 더하면 저절로 막힌다). 공개 셋(로그인·refresh·revoke)은 인증이 없어 표 밖이다.
INITIAL_ALLOWED: Final = frozenset({"user_me", "user_password_change"})

# 운영 관리자가 실행을 만들고 볼 수 있는 모듈(MARC-ENT-374·380·390·419 —
# 그린워싱·영문번역·데이터 검증·중대성평가). 고객사 사용자는
# 모듈을 가리지 않는다. inventory.scope3 — Scope 3 코랩 흐름(469-4 「대신하기」 꼴, 밴드 S3K1 Q5).
OPERATOR_RUN_MODULES: Final = frozenset(
    {"greenwash", "translation", "dataverify", "materiality", "drafting", "inventory.scope3"}
)

_WHO: Final[dict[Needs, str]] = {
    "customer": "고객사 사용자",
    "operator": "운영 관리자",
    "self": "로그인한 사용자",
    "company": "회사 업무를 하는 사용자",
}


def needs_of(operation_id: str) -> Needs:
    """그 동작에 필요한 것. 표에 없는 이름이면 KeyError 다(표에 없는 동작은 열어 주지 않는다)."""
    return OPERATION_POLICY[operation_id].needs


def is_allowed(operation_id: str, *, kind: Kind) -> bool:
    needs = needs_of(operation_id)
    if needs == "customer":
        return kind == "service"
    if needs == "operator":
        return kind == "admin"
    return True  # self·company: 두 kind 다


def forbidden_message(operation_id: str) -> str:
    return f"이 일은 {_WHO[needs_of(operation_id)]}만 한다"
