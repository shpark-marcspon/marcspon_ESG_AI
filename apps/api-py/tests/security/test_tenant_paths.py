"""격리의 받침 ③: openapi 의 동작 전부를 표 하나와 견주고, 회사 둘(A·B)을 세워 경로로 남의 행이 닿지 않는 것을 잰다.

보안 층. 연결은 이 층 그대로다(앱 역할 esg_app, RLS 없음, 진짜 커밋, 직렬). 분모는 주인 연결(owner)로 센다.
오류 응답은 상태 코드만 본다(오류 본문의 code 글자는 다른 밴드가 바꾼다).

표 OPERATIONS 는 (메서드, 경로) → 분류다. 열쇠는 살아 있는 API(esgapi/config/api.py 의 api)가 내는 openapi 와 글자로
같아야 한다. 분류:
    public         세션이 필요 없다(교환·나가기·상태 확인·로그인·refresh·revoke)
    bearer         access 토큰(Authorization: Bearer)의 자기 계정만(/users/me·비밀번호 바꾸기 — 테넌트 행을 경로의
                   id 로 읽지 않는다. 토큰의 사용자를 그 회사 조건으로 읽는다)과 운영 관리자의 고객사 사용자 관리 셋
                   (K2c — 세션의 회사가 아니라 요청의 companyId 로 고른 회사에서 for_company 로 연다. 회사 격리는
                   tests/security/test_user_admin.py 가 잰다)
    session        세션 자신만 돌려준다(테넌트 행을 읽고 쓰지 않는다)
    compute        계산·추리기. 저장하지 않는다
    reference      공용 기준정보(테넌트 칸이 없는 표)
    tenant_read    테넌트 행 하나를 경로의 id 로 읽거나 고친다 → 남의 id 는 404, 남의 행은 그대로
    tenant_list    테넌트 행의 목록 → 세션의 테넌트 것만
    tenant_create  테넌트 행을 만든다 → 세션의 테넌트에(본문에는 테넌트를 실을 칸이 없다)
    contract_only  꼴만 계약이고 몸이 없다(밴드 XC — 인증·권한을 지나면 501) → 세션 없이 401, A 의 세션으로 501,
                   테넌트 표의 행 수 그대로. **회사 격리 단언(남의 id → 404, 목록은 내 것만)은 몸이 없어 재지 못한다:
                   몸을 채우는 밴드가 이 경로들을 다른 분류로 옮기며 단다.**
    run_paths      실행 경로 다섯(X1b-1 이 몸을 채움 — 실행·문서 행을 경로·본문의 id 로 읽는다) → 세션 없이 401. 회사
                   격리(남의 실행·파일·문서 → 404, 목록은 내 것만)는 tests/security/test_runs.py ⓒⓓ 가 잰다(실행 행을
                   만들려면 끼움 있는 흐름이 있어야 해 이 파일의 고리로는 재지 못한다)
    greenwash_run_paths  그린워싱 결과·검토 셋·보고서(G1b-1·2a — 실행 행을 경로의 id 로 읽는다) → 세션 없이 401,
                   남의 회사 실행 id 와 없는 id 는 404 이고 검토 표의 행 수 그대로. 분모: 제 실행은 200. 더 깊은 것
                   (감사·표시 행·확정 뒤)은 tests/security/test_greenwash.py 가 잰다
    greenwash_rejudge_paths  그린워싱 재판단 만들기(GRJ1 — 실행 행을 경로의 id 로 읽는다) → 세션 없이 401, 남의 회사
                   실행 id 와 없는 id 는 404 이고 실행·검토 표의 행 수 그대로. 분모: 제 실행은 409 NOTHING_TO_REJUDGE
    greenwash_result2_paths  그린워싱 2차 엔진 결과(GE1b ④ — 실행 행을 경로의 id 로, 흐름 engine@G1 만) → 세션 없이
                   401, 남의 회사 실행 id·없는 id 는 404(본문에 결과 0)이고 실행·결과 표의 행 수 그대로. A 로도 1차(E0)
                   실행 id 는 404. 분모: 제 G1 실행은 200
    translation_run_paths  영문번역 결과(TR2 — 실행 행을 경로의 id 로 읽는다) → 세션 없이 401, 남의 회사 실행 id·다른
                   모듈의 실행 id·없는 id 는 404. 분모: 제 실행은 200. 옵션 안의 retry.fromRunId 는
                   tests/security/test_translation.py 가 잰다
    dataverify_run_paths  데이터 검증 결과(DV1e — 실행 행을 경로의 id 로 읽는다) → 세션 없이 401, 남의 회사 실행 id·
                   다른 모듈의 실행 id·없는 id 는 404. 분모: 제 실행은 200. 더 깊은 것은 test_dataverify.py
    materiality_run_paths  중대성평가 IRO 결과(IR3b — 실행 행을 경로의 id 로 읽는다) → 세션 없이 401, 남의 회사 실행
                   id·다른 모듈의 실행 id(끝난 것·안 끝난 것)·없는 id 는 404. 분모: 제 실행은 200. 더 깊은 것은
                   test_materiality.py
    scope3_run_paths  Scope 3 코랩 결과(S3K1 — 실행 행을 경로의 id 로 읽는다) → 세션 없이 401, 남의 회사 실행 id·다른
                   모듈의 실행 id(끝난 것·안 끝난 것)·없는 id 는 404. 분모: 제 실행은 200(운영 관리자도 작업 회사로 —
                   test_operator_company.py)
    scope3_original_paths  Scope 3 올린 원본(S3Q1 — 실행 행을 경로의 id 로, 그 문서를 실행의 document_id 로 읽는다) →
                   세션 없이 401, 남의 회사 실행 id·다른 모듈의 실행 id·문서 없는 실행·없는 id 는 404(본문에 원본
                   바이트 0)이고 실행·문서 표의 행 수 그대로. 분모: 제 실행은 200, 본문 = 심은 바이트
    translation_batch_paths  영문번역 묶음 목록·하나 보기·zip(TR3b — 실행 행을 묶음 열쇠로, 문서를 경로의 id 로 읽는다)
                   → 세션 없이 401, 남의 회사 문서·없는 묶음·다른 모듈 실행의 run-<id>·batchId 있는 실행의 run-<id> 는
                   404, 목록에 남의 묶음 0(두 회사가 같은 batchId 여도). 분모: 제 묶음은 200. 더 깊은 것(zip·운영
                   관리자)은 tests/security/test_translation.py 가 잰다
                   · 문서 쪽 수(TRP6 — 문서를 경로 id 로, 원본을 저장소에서 읽음): 남의 회사 문서·없는 문서 404
    translation_layout_paths  영문번역 layout 읽기(TRS3 — 실행 행을 경로 id 로, PDF 실행만 200) → 세션 없이 401,
                   남의 회사 실행 id·다른 모듈의 실행 id·워드 실행 id·없는 id 는 404. 분모: 제 PDF 실행은 200. 더 깊은
                   것(안 끝남 409·운영 관리자)은 tests/security/test_translation.py ⓖ 가 잰다
    greenwash_list 그린워싱 목록 줄(G1b-1 — 세션의 회사의 그린워싱 실행·문서를 읽는다) → 세션 없이 401, 남의 회사의
                   실행·문서 0. 분모: 제 회사의 것은 보인다
    dataverify_list 데이터 검증 실행 목록(DV1g — 세션의 회사의 데이터 검증 실행을 읽는다) → 세션 없이 401, 남의
                   회사의 실행 0. 분모: 제 회사의 것은 보인다. 더 깊은 것은 test_dataverify.py
    materiality_list 중대성평가 IRO 실행 목록(IR3c — 세션의 회사의 중대성평가 실행을 읽는다) → 세션 없이 401, 남의
                   회사의 실행 0. 분모: 제 회사의 것은 보인다. 더 깊은 것은 test_materiality.py
    document_paths 문서 목록·고치기(X1b-2a — 목록은 쿼리, PATCH 는 본문을 받아 tenant_list·tenant_read 고리에 안
                   맞는다) → 세션 없이 401. 회사 격리(목록에 남의 것 0, 남의 문서·앞 판 → 404, 행 그대로)는
                   tests/security/test_documents_chain.py ⓐⓑ 가 잰다. 판 사슬·원본 내려받기(GET 둘)는 tenant_read 다
    branch_paths   사업장 다섯(K1b-1 — 목록은 쿼리, 하나·저장은 경로 id 와 본문 facilities[].id, 토글·삭제는 본문
                   ids[] 를 받아 tenant_read·tenant_list 고리에 안 맞는다) → 세션 없이 401. 회사 격리(남의 사업장·자산/
                   시설 id·ids[] → 404·행 0, 목록에 남의 것 0)는 tests/security/test_branches.py 가 잰다
    index_selection_paths  인덱스 선택 둘(K1b-2b — 트리는 쿼리 ?year=, 저장은 경로 {year} 와 본문 facilityNodeIds[])
                   → 세션 없이 401. 본문 facilityNodeIds 는 공통 풀 노드 id(회사 행이 아니다 — MARC-ENT-469 3)라
                   ID_FIELDS 가 못 보는 자리이고 그 회사 격리는 tests/security/test_index_selection.py 가 잠근다
    entry_paths    Scope 1·2 입력 열(S12a — 경로 id 는 해 {year}·공통 풀 잎 {node_id}(회사 행 아님)·회사 행인 사업장
                   {site_id}·입력 행 {row_id}, 본문 rows[].rowId·siteFacilityId·ids[] 는 회사 행) → 세션 없이 401.
                   tenant_read 고리(문서 id 하나)에 안 맞는다 — 회사 행 id 를 받는 경로마다 「B 의 id 로 A 경로 404」와
                   상세·리스트·히스토리·저장·지움의 회사 격리는 tests/security/test_entries.py 가 잰다(대상 표를 이
                   분류에서 뽑는다). 풀 잎·해만 받는 경로(해 목록·리스트·상세·메모·잠금 둘·자릿수)는 그 회사의 선택·해
                   행만 읽는다 — 잎 id 는 공통이라 남의 것이 없다. 풀기(unlock)는 운영 관리자 칸의 회사 경로라
                   OPERATOR_COMPANY_OPERATIONS 로 따로 센다
    scope3_state_paths  Scope 3 연도 상태·카테고리 잠금 셋 + 데이터 엑셀 = 넷(S3K2a · S3D1
                   — 경로 id 는 해 {year}·카테고리 {category}(회사 행
                   아님), 잠그기의 쿼리 runId 는 회사 행인 실행) → 세션 없이 401. tenant_read 고리에 안 맞는다 — 남의
                   회사 runId 404(없는 id 와 같은 바이트)·연도 상태에 남의 실행·잠금 0·풀기가 남의 잠금을 안 건드림은
                   tests/security/test_scope3_state.py 가 잰다. 풀기(unlock)는 운영 관리자 칸의 회사 경로라
                   OPERATOR_COMPANY_OPERATIONS 로 따로 센다
    scope3_edit_paths  Scope 3 줄 덧판 다섯(S3K2b-1·2 — 경로 id 는 회사 행인 실행 {run_id}·카테고리 {category}(회사
                   행 아님), 제외·복구·계수는 본문을 받아 tenant_read 고리에 안 맞는다) → 세션 없이 401.
                   남의 회사 실행 404(없는 id 와 같은 바이트)·거절 때 쓰기 0·응답에 남의 사건 0 은
                   tests/security/test_scope3_edits.py 가 잰다
    drafting_paths 원고작성 여덟(RP1 다섯 + RP2d 둘 + RP2c 하나 — 프로젝트를 경로 id 로, 문서를 본문 documentId 로,
                   실행을 경로 id 로 읽는다.
                   만들기·문서 달기·목차 넣기가 본문을 받아 tenant_read·tenant_create 고리에 안 맞는다) → 세션 없이 401.
                   회사 격리(남의 프로젝트·문서·실행 → 404·행 0, 남의 projectId 로 실행 만들기 409)는
                   tests/security/test_drafting.py ⓐ~ⓓ 가 잰다
**경로를 더하면 이 표에 한 줄을 더한다**(빠지면 test_every_operation_is_in_the_table 이 빨갛다). tenant_read·
tenant_create 로 적으면 아래의 행 만들기·본문 표에도 한 줄을 더한다(없으면 그 테스트가 까닭을 말하고 빨개진다).
요청 본문에 `id`·`…Id` 칸을 더하면 ID_FIELDS 에 그 칸과 까닭(왜 테넌트 행을 가리키지 않는가)을 적는다.

무효 조건(이 파일이 못 재는 것):
  - 분류는 사람이 적은 것이다. compute·reference·session 으로 적은 경로가 나중에 테넌트 행을 읽거나 쓰게 되면
    이 표는 그것을 모른다(경로를 더하거나 고치는 밴드가 분류를 다시 본다).
  - 남의 id → 404 는 경로의 id 로만 잰다. 요청 본문의 id 는 이름(`id`·`…Id`)으로만 찾는다: 다른 이름의 칸이
    테넌트 행을 가리키면 못 잡는다. 쿼리 문자열의 칸은 보지 않는다 — 지금 테넌트 행을 가리키는 것은 문서 목록의
    uploadedBy(사용자 id, X1b-2a) 하나이고 그 격리(남의 회사 사용자 id 면 빈 쪽)는 test_documents_chain.py ⓑ 가 잰다.
    TR3b 의 영문번역 묶음 목록 documentId(문서 id)도 쿼리 칸이다 — 남의 회사 문서면 빈 쪽(translation_batch_paths).
    DV1g 의 데이터 검증 목록 쿼리 `status`·`mine` 은 테넌트 행을 가리키지 않는다 — mine 은 부른 사람.
    IR3c 의 중대성평가 목록 쿼리 `status`·`mine` 도 테넌트 행을 가리키지 않는다.
    K1b-1 의 일괄 본문 `ids[]`(사업장 토글·삭제 — 테넌트 행)는 이름(`id`·`…Id`)으로 못 잡는 칸이다 — 격리(남의 id 가
    섞이면 404·행 0)는 tests/security/test_branches.py 가 잰다.
  - LLM 을 부르는 /inventory/scope3/* 는 세션 없는 401 과 고객사 사용자 Bearer 의 허락 쪽만 친다(분류는 빈 목록 —
    생성 모델에 닿는 본문을 보내지 않는다. 실제 호출 0, 모의 0).
  - 세션이 있는 사람이 남의 테넌트의 세션을 만드는 길(교환)은 test_tenant_boundary.py·test_exchange_tenant.py 가 잰다.
"""

import json
import re
from pathlib import Path
from typing import Any, Final, cast

import psycopg
import pytest
from django.test import Client
from psycopg import sql

from esgapi.config.api import api
from esgapi.core.tests.resource_fakes import FakeStorage
from tests.security.conftest import count
from tests.security.seed import add_site
from tests.security.test_documents import upload_as
from tests.support.http import customer_bearer, login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
Operation = tuple[str, str]

OPERATIONS: Final[dict[Operation, str]] = {
    ("POST", "/auth/exchange"): "public",
    ("POST", "/auth/logout"): "public",
    ("GET", "/healthz"): "public",
    ("GET", "/readyz"): "public",
    ("POST", "/auth/login"): "public",
    ("POST", "/auth/refresh"): "public",
    ("POST", "/auth/revoke"): "public",
    ("GET", "/users/me"): "bearer",
    ("POST", "/users/me/password"): "bearer",
    ("GET", "/users"): "bearer",
    ("POST", "/users"): "bearer",
    ("POST", "/users/{user_id}/password-reset"): "bearer",
    ("PATCH", "/users/{user_id}"): "bearer",
    ("GET", "/audit-logs"): "bearer",
    ("GET", "/audit-logs/actors"): "bearer",
    ("GET", "/run-logs"): "bearer",
    ("GET", "/run-logs/metrics"): "bearer",
    ("GET", "/run-logs/export"): "bearer",
    ("GET", "/run-logs/{run_id}"): "bearer",  # AD4D — 격리는 tests/security/test_run_logs.py 의 ⓖ·ⓖ'·ⓗ
    ("GET", "/run-logs/{run_id}/files/{name}"): "bearer",  # RF1 — 격리는 test_run_logs.py 의 ⓘ·ⓙ
    # G2c2: 그린워싱 AI 설정 판(운영 관리자 Bearer, companyId 로 고른 회사). 격리는 tests/security/test_ai_settings.py
    ("GET", "/ai-settings/greenwash"): "bearer",
    ("GET", "/ai-settings/greenwash/default"): "bearer",
    ("GET", "/ai-settings/greenwash/{setting_id}"): "bearer",
    ("POST", "/ai-settings/greenwash"): "bearer",
    ("PUT", "/ai-settings/greenwash/applied"): "bearer",
    # AS2a: 판의 프롬프트·모델 읽기 둘(운영 관리자 Bearer). 격리는 tests/security/test_ai_settings.py
    ("GET", "/ai-settings/greenwash/{setting_id}/prompt-model"): "bearer",
    ("GET", "/ai-settings/greenwash/default/prompt-model"): "bearer",
    # TR4: 영문번역 AI 설정 판 일곱(운영 관리자 Bearer). 격리는 tests/security/test_translation_ai_settings.py
    ("GET", "/ai-settings/translation"): "bearer",
    ("GET", "/ai-settings/translation/default"): "bearer",
    ("GET", "/ai-settings/translation/{setting_id}"): "bearer",
    ("POST", "/ai-settings/translation"): "bearer",
    ("PUT", "/ai-settings/translation/applied"): "bearer",
    ("GET", "/ai-settings/translation/{setting_id}/prompt-model"): "bearer",
    ("GET", "/ai-settings/translation/default/prompt-model"): "bearer",
    # DVA1: 데이터 검증 AI 설정 판 일곱(운영 관리자 Bearer). 격리는 tests/security/test_dataverify_ai_settings.py
    ("GET", "/ai-settings/dataverify"): "bearer",
    ("GET", "/ai-settings/dataverify/default"): "bearer",
    ("GET", "/ai-settings/dataverify/{setting_id}"): "bearer",
    ("POST", "/ai-settings/dataverify"): "bearer",
    ("PUT", "/ai-settings/dataverify/applied"): "bearer",
    ("GET", "/ai-settings/dataverify/{setting_id}/prompt-model"): "bearer",
    ("GET", "/ai-settings/dataverify/default/prompt-model"): "bearer",
    # IR4: 중대성평가 IRO AI 설정 판 일곱(운영 관리자 Bearer). 격리는 tests/security/test_materiality_ai_settings.py
    ("GET", "/ai-settings/materiality"): "bearer",
    ("GET", "/ai-settings/materiality/default"): "bearer",
    ("GET", "/ai-settings/materiality/{setting_id}"): "bearer",
    ("POST", "/ai-settings/materiality"): "bearer",
    ("PUT", "/ai-settings/materiality/applied"): "bearer",
    ("GET", "/ai-settings/materiality/{setting_id}/prompt-model"): "bearer",
    ("GET", "/ai-settings/materiality/default/prompt-model"): "bearer",
    # RPA1: 원고작성 AI 설정 판 일곱(운영 관리자 Bearer). 격리는 tests/security/test_drafting_ai_settings.py
    ("GET", "/ai-settings/drafting"): "bearer",
    ("GET", "/ai-settings/drafting/default"): "bearer",
    ("GET", "/ai-settings/drafting/{setting_id}"): "bearer",
    ("POST", "/ai-settings/drafting"): "bearer",
    ("PUT", "/ai-settings/drafting/applied"): "bearer",
    ("GET", "/ai-settings/drafting/{setting_id}/prompt-model"): "bearer",
    ("GET", "/ai-settings/drafting/default/prompt-model"): "bearer",
    ("GET", "/me"): "session",
    ("POST", "/inventory/calc"): "compute",
    ("POST", "/inventory/scope3/classify"): "compute",
    ("POST", "/inventory/scope3/shortlist"): "compute",
    # S3K1 Scope 3 코랩 둘(플랫폼-서버 e7·테스트 6d 허락): 결과는 실행 행을 경로 id 로 읽고(회사를 고름), 빈 양식은
    # 테넌트 행을 읽지 않는 공용 파일(회사를 고르지 않는다 — NOT_CHOOSING, dataverify_edk_template 꼴).
    ("GET", "/inventory/scope3/runs/{run_id}/result"): "scope3_run_paths",
    ("GET", "/inventory/scope3/runs/{run_id}/original"): "scope3_original_paths",  # S3Q1(테스트 6d 허락)
    ("GET", "/inventory/scope3/template"): "reference",
    ("GET", "/reference/factors"): "reference",
    ("GET", "/reference/sources"): "reference",
    ("POST", "/reference/assemble"): "reference",
    ("POST", "/reference/assemble-electricity"): "reference",
    ("GET", "/documents/{document_id}"): "tenant_read",
    ("POST", "/documents/{document_id}/confirm"): "tenant_read",
    ("GET", "/sites"): "tenant_list",
    ("POST", "/sites"): "tenant_create",
    ("POST", "/documents"): "tenant_create",
    ("GET", "/documents"): "document_paths",
    ("PATCH", "/documents/{document_id}"): "document_paths",
    ("GET", "/documents/{document_id}/versions"): "tenant_read",
    ("GET", "/documents/{document_id}/file"): "tenant_read",
    ("POST", "/runs"): "run_paths",
    ("GET", "/runs"): "run_paths",
    ("GET", "/runs/{run_id}"): "run_paths",
    ("GET", "/runs/{run_id}/files/{name}"): "run_paths",
    ("GET", "/runs/{run_id}/segments"): "run_paths",  # RM1c ③ 구획 목록
    # 그린워싱 계약(밴드 GC1, 몸은 501). 실행·문서를 가리키므로 X1b 뒤의 그린워싱 밴드가 격리 단언으로 옮긴다.
    ("GET", "/greenwash/runs/{run_id}/result"): "greenwash_run_paths",
    ("GET", "/greenwash/runs/{run_id}/review"): "greenwash_run_paths",
    ("PUT", "/greenwash/runs/{run_id}/review"): "greenwash_run_paths",
    ("POST", "/greenwash/runs/{run_id}/items/{item_index}/rejudge"): "greenwash_rejudge_paths",  # GRJ1
    ("GET", "/greenwash/runs/{run_id}/result2"): "greenwash_result2_paths",  # GE1b ④(테스트 6d 허락)
    ("GET", "/greenwash/compare"): "contract_only",
    # 그린워싱 계약 보탬(밴드 GC2): 보고서 내려받기는 몸이 있다(G1b-2a), 기본 단어 목록은 테넌트 행을 읽지 않는 공용 값.
    ("GET", "/greenwash/runs/{run_id}/report"): "greenwash_run_paths",
    ("GET", "/translation/runs/{run_id}/result"): "translation_run_paths",
    ("GET", "/translation/runs/{run_id}/layout"): "translation_layout_paths",
    ("GET", "/dataverify/runs/{run_id}/result"): "dataverify_run_paths",
    ("GET", "/dataverify/runs"): "dataverify_list",
    ("GET", "/materiality/runs/{run_id}/result"): "materiality_run_paths",
    # IRS3 ② 결과 고침 둘(실행 행을 경로의 id 로 — 결과와 같은 격리, 더 깊은 것은 test_materiality.py)
    ("GET", "/materiality/runs/{run_id}/result/edits"): "materiality_run_paths",
    ("POST", "/materiality/runs/{run_id}/result/edits"): "materiality_run_paths",
    ("GET", "/materiality/runs/{run_id}/report"): "materiality_run_paths",  # IRS3 ③ 고친 판 최종 엑셀
    ("GET", "/materiality/runs"): "materiality_list",
    ("GET", "/greenwash/terms/default"): "reference",
    # 영문번역 용어집 둘(TR3a — 플랫폼-서버 22 허락): 양식은 테넌트 행을 읽지 않는 공용 파일, 읽기는 상태 없는 xlsx 풀이
    # (저장 0). 둘 다 회사를 고르지 않는다(NOT_CHOOSING).
    ("GET", "/translation/glossary/template"): "reference",
    ("POST", "/translation/glossary/read"): "compute",
    # 중대성평가 가치사슬 엑셀 읽기(IRW2): 상태 없는 xlsx 풀이(저장 0) — 용어집 읽기와 같은 꼴, 회사를 고르지 않는다.
    ("POST", "/materiality/value-chain/read"): "compute",
    # 데이터 검증 EDK 인벤토리 엑셀 둘(DVX1 — 플랫폼-서버 e7·테스트 6d 허락): 양식은 테넌트 행을 읽지 않는 공용
    # 파일, 읽기는 상태 없는 xlsx 풀이(저장 0) — 용어집 둘과 같은 꼴, 회사를 고르지 않는다(NOT_CHOOSING).
    ("GET", "/dataverify/edk/template"): "reference",
    ("POST", "/dataverify/edk/read"): "compute",
    ("GET", "/greenwash/checks"): "greenwash_list",
    # 영문번역 묶음(TR3b — 플랫폼-서버 22·테스트 73 허락): 목록·하나 보기·zip · 문서 쪽 수(TRP6).
    ("GET", "/translation/batches"): "translation_batch_paths",
    ("GET", "/translation/documents/{document_id}/batches/{batch_key}"): "translation_batch_paths",
    ("GET", "/translation/documents/{document_id}/batches/{batch_key}/archive"): "translation_batch_paths",
    ("GET", "/translation/documents/{document_id}/pages"): "translation_batch_paths",
    # 사업장(K1b-1 — 플랫폼-서버 ce·테스트 d9 허락): 만들기는 tenant_create, 나머지 다섯은 branch_paths.
    ("POST", "/branches"): "tenant_create",
    ("GET", "/branches"): "branch_paths",
    ("GET", "/branches/{branch_id}"): "branch_paths",
    ("PUT", "/branches/{branch_id}"): "branch_paths",
    ("POST", "/branches/inventory"): "branch_paths",
    ("POST", "/branches/delete"): "branch_paths",
    # 자산/시설 코드 목록(K1b-1): 읽기는 공통 목록(회사 칸 없음 — 회사를 고르지 않는다), 쓰기 넷은 운영 관리자 Bearer.
    ("GET", "/facility-codes"): "reference",
    ("GET", "/admin/facility-codes"): "bearer",
    ("POST", "/admin/facility-codes"): "bearer",
    ("PATCH", "/admin/facility-codes/{code_id}"): "bearer",
    ("POST", "/admin/facility-codes/delete"): "bearer",
    # 온실가스 인덱스 풀·계수 풀(K1b-2a): 공통 풀(회사 칸 없음 — 회사를 고르지 않는다), 열둘 다 운영 관리자 Bearer.
    ("GET", "/inventory/admin/ghg-index/nodes"): "bearer",
    ("POST", "/inventory/admin/ghg-index/nodes"): "bearer",
    ("PATCH", "/inventory/admin/ghg-index/nodes/{node_id}"): "bearer",
    ("POST", "/inventory/admin/ghg-index/nodes/delete"): "bearer",
    ("GET", "/inventory/admin/ghg-index/facilities/{node_id}"): "bearer",
    ("POST", "/inventory/admin/ghg-index/facilities"): "bearer",
    ("PUT", "/inventory/admin/ghg-index/facilities/{node_id}"): "bearer",
    ("POST", "/inventory/admin/ghg-index/facilities/{node_id}/factors"): "bearer",
    ("GET", "/inventory/admin/ghg-factors/{factor_id}"): "bearer",
    ("PUT", "/inventory/admin/ghg-factors/{factor_id}"): "bearer",
    ("POST", "/inventory/admin/ghg-factors/delete"): "bearer",
    ("GET", "/inventory/admin/ghg-options"): "bearer",
    # 고객사 인덱스 선택(K1b-2b — 플랫폼-서버 e7·테스트 6d 허락): 두 operationId 를 이름으로 — 닫힌 집합(아래 len == 2).
    ("GET", "/inventory/scope12/index-tree"): "index_selection_paths",
    ("PUT", "/inventory/scope12/index-selections/{year}"): "index_selection_paths",
    # Scope 1·2 입력(S12a — 플랫폼-서버 e7·테스트 6d 허락): 열 operationId 를 이름으로 — 닫힌 집합(아래 len == 10).
    ("GET", "/inventory/scope12/years"): "entry_paths",
    ("GET", "/inventory/scope12/rows"): "entry_paths",
    ("GET", "/inventory/scope12/years/{year}/indexes/{node_id}"): "entry_paths",
    ("PUT", "/inventory/scope12/years/{year}/indexes/{node_id}/sites/{site_id}/rows"): "entry_paths",
    ("POST", "/inventory/scope12/years/{year}/indexes/{node_id}/rows/delete"): "entry_paths",
    ("PUT", "/inventory/scope12/years/{year}/indexes/{node_id}/memo"): "entry_paths",
    ("POST", "/inventory/scope12/years/{year}/indexes/{node_id}/lock"): "entry_paths",
    ("DELETE", "/inventory/scope12/years/{year}/indexes/{node_id}/lock"): "entry_paths",
    ("PUT", "/inventory/scope12/years/{year}/decimals"): "entry_paths",
    ("GET", "/inventory/scope12/years/{year}/indexes/{node_id}/rows/{row_id}/history"): "entry_paths",
    # S12a-2 +3(테스트 6d 허락 — 닫힌 집합은 아래 len == 13): 입력주기 · 행 계수 바꿈 · 히스토리 복구.
    ("PUT", "/inventory/scope12/years/{year}/indexes/{node_id}/sites/{site_id}/period"): "entry_paths",
    ("PUT", "/inventory/scope12/years/{year}/indexes/{node_id}/rows/{row_id}/factor"): "entry_paths",
    (
        "POST",
        "/inventory/scope12/years/{year}/indexes/{node_id}/rows/{row_id}/history/{history_id}/restore",
    ): "entry_paths",
    # S12a-3 +1(테스트 6d 허락 — 닫힌 집합은 아래 len == 14): 대시보드(S1 읽기).
    ("GET", "/inventory/scope12/dashboard"): "entry_paths",
    # S12b-1 +2(테스트 6d 허락 — 닫힌 집합은 아래 len == 16): 엑셀 내려받기 둘(양식·데이터 — 읽기만).
    ("GET", "/inventory/scope12/years/{year}/template"): "entry_paths",
    ("GET", "/inventory/scope12/years/{year}/export"): "entry_paths",
    # S12b-2 +1(테스트 6d 허락 — 닫힌 집합은 아래 len == 17): 일괄 올리기(맨 바이트 본문).
    ("POST", "/inventory/scope12/years/{year}/uploads"): "entry_paths",
    # S3K2a +3(테스트 6d 허락 — 닫힌 집합은 아래 len == 3): Scope 3 연도 상태 · 카테고리 잠그기·풀기.
    ("GET", "/inventory/scope3/years/{year}"): "scope3_state_paths",
    ("POST", "/inventory/scope3/years/{year}/categories/{category}/lock"): "scope3_state_paths",
    ("DELETE", "/inventory/scope3/years/{year}/categories/{category}/lock"): "scope3_state_paths",
    ("GET", "/inventory/scope3/years/{year}/export"): "scope3_state_paths",  # S3D1
    ("POST", "/inventory/scope3/runs/{run_id}/categories/{category}/exclusions"): "scope3_edit_paths",
    ("POST", "/inventory/scope3/runs/{run_id}/categories/{category}/restorations"): "scope3_edit_paths",
    ("GET", "/inventory/scope3/runs/{run_id}/edits"): "scope3_edit_paths",
    ("GET", "/inventory/scope3/runs/{run_id}/history"): "scope3_edit_paths",
    ("POST", "/inventory/scope3/runs/{run_id}/categories/{category}/factors"): "scope3_edit_paths",
    # 원고작성(RP1 — 보고서 감독 dc·e7 알림): 다섯 다 drafting_paths(격리는 tests/security/test_drafting.py).
    ("POST", "/drafting/projects"): "drafting_paths",
    ("GET", "/drafting/projects/{project_id}"): "drafting_paths",
    ("PUT", "/drafting/projects/{project_id}/document"): "drafting_paths",
    ("PUT", "/drafting/projects/{project_id}/outline"): "drafting_paths",
    ("GET", "/drafting/runs/{run_id}/result"): "drafting_paths",
    ("GET", "/drafting/projects"): "drafting_paths",  # RP2d
    ("GET", "/drafting/runs/{run_id}/result.docx"): "drafting_paths",  # RP2d
    ("GET", "/drafting/projects/{project_id}/outline/changes"): "drafting_paths",  # RP2c
    ("GET", "/drafting/projects/{project_id}/runs"): "drafting_paths",  # RPS1
}
# 회사 경로 가운데 운영 관리자 칸(OPERATOR)인 것 — 작업 회사를 고르는 운영 관리자만(S12a 잠금 풀기, MARC-ENT-469 2).
# 고객사 Bearer 로 지나는 고리·회사 업무 고리에서 이 소속으로만 빼고(이름 하드코딩 0), 뺀 것이 재던 것(고객사 403 ·
# 운영 관리자 회사 하나 통과 · 회사 둘 400 company_ambiguous)은 tests/security/test_entries.py 가 잰다.
# S12a-2 +1: 행 계수 바꿈(MARC-ENT-469 — 계수 수정은 운영 관리자, 풀기와 같은 꼴).
# S3K2a +1: Scope 3 카테고리 잠금 풀기(469 2 — 풀기와 같은 꼴).
OPERATOR_COMPANY_OPERATIONS: Final = frozenset(
    {"inventory_scope12_unlock", "inventory_scope12_row_factor_save", "inventory_scope3_unlock"}
)

# tenant_create 의 표가 회사를 적는 칸. 둘 다 회사의 숫자 id 다(core 의 표도 K1u-b 부터 company_id).
CREATE_COMPANY_COLUMN: Final[dict[str, str]] = {"sites": "company_id", "core_documents": "company_id"}

# 요청 본문의 `id`·`…Id` 칸(스키마 이름.칸 이름)과 그것이 테넌트 행을 가리키지 않는 까닭.
ID_FIELDS: Final[dict[str, str]] = {
    "CalcIn.gwpSetId": "공용 기준정보(GWP 값의 묶음)의 이름이다. 테넌트 칸이 없다",
    "CalcRowIn.factorId": "공용 기준정보(reference_factor_records)의 id 다. 테넌트 칸이 없다",
    "CalcRowIn.id": "요청 안의 행 이름표다(답의 행을 요청의 행과 잇는다). 저장되지 않는다",
    "Scope3RowIn.rowId": "요청 안의 행 이름표다(분류 결과를 요청의 행과 잇는다). 저장되지 않는다",
    "Scope3RowEditFactorIn.rowId": "결과 본문의 줄 이름표다(회사 행 id 아님) — 경로 {run_id} 의 실행 안에서만 찾는다",
    "SiteIn.externalId": "EDK 가 준 바깥 ID 다. 만드는 행의 칸으로 쓰일 뿐 다른 행을 가리키지 않는다",
    # 아래 셋은 테넌트 행을 가리킨다. 칸이 openapi 에 남으므로 줄은 남기고 지금 사실을 적는다(X1b-1).
    "RunIn.documentId": "테넌트 행(문서)을 가리킨다 — 남의 id 는 404(test_runs.py ⓓ, 문서 없는 흐름도 ⓕ' — ND1)",
    "RunIn.resumeFromRunId": (
        "테넌트 행(실행)을 가리킨다 — 남의 id 는 404·행 그대로, tests/security/test_runs.py ⓔ 가 잰다(X1b-2b)"
    ),
    "RunRetrySegmentsIn.fromRunId": (
        "테넌트 행(실행)을 가리킨다 — 남의 회사 run 은 404·행 그대로, 구획 열쇠도 요청 회사 실행의 것만 "
        "(tests/security/test_runs.py ⓒⓓ RM1c ③)"
    ),
    "DocumentIn.previousDocumentId": (
        "만들기는 받지 않는다(422 PREVIOUS_VIA_PATCH, 읽기 0) — 앞 판은 DocumentPatchIn.previousDocumentId"
        "(남의 id 404, tests/security/test_documents_chain.py ⓐ)"
    ),
    "DocumentPatchIn.previousDocumentId": (
        "테넌트 행(문서)을 가리킨다 — 남의 id 는 404·행 그대로, "
        "tests/security/test_documents_chain.py ⓐ 가 잰다(X1b-2a)"
    ),
    "RunIn.flowId": "흐름 등록부(core.flows.REGISTRY)의 이름@판이다. 테넌트 칸이 없다",
    # 운영 관리자 전용(K2c): 회사 범위가 없는 운영 관리자가 대상 회사를 고른다.
    # 사용자는 그 회사의 for_company 로만 연다.
    "UserCreateIn.companyId": "운영 관리자가 고른 대상 회사(회사 행 자체). 격리는 tests/security/test_user_admin.py",
    "PasswordResetIn.companyId": "운영 관리자가 고른 대상 회사(회사 행 자체). 격리는 tests/security/test_user_admin.py",
    "UserUpdateIn.companyId": "운영 관리자가 고른 대상 회사(회사 행 자체). 격리는 tests/security/test_user_admin.py",
    "GreenwashAiSettingApply.id": "테넌트 행(AI 설정 판)을 가리킨다 — 남의 id 404, tests/security/test_ai_settings.py",
    "TranslationAiSettingApply.id": (
        "테넌트 행(AI 설정 판)을 가리킨다 — 남의 id 404, tests/security/test_translation_ai_settings.py"
    ),
    "DataverifyAiSettingApply.id": (
        "테넌트 행(AI 설정 판)을 가리킨다 — 남의 id 404, tests/security/test_dataverify_ai_settings.py"
    ),
    "MaterialityAiSettingApply.id": (
        "테넌트 행(AI 설정 판)을 가리킨다 — 남의 id 404, tests/security/test_materiality_ai_settings.py"
    ),
    "DraftingAiSettingApply.id": (
        "테넌트 행(AI 설정 판)을 가리킨다 — 남의 id 404, tests/security/test_drafting_ai_settings.py"
    ),
    "GreenwashCriterionRow.id": "기준표 고정 15줄의 이름표다(keyword-ghg 등 — 저장 행을 가리키지 않는다)",
    # K1b-1: 앞은 테넌트 행(그 사업장의 자산/시설 — 남의 것·삭제된 것 404), 뒤는 공통 코드 목록(회사 칸 없음).
    "BranchFacilityIn.id": "테넌트 행(사업장의 자산/시설)을 가리킨다 — 남의 id 404, tests/security/test_branches.py",
    "BranchFacilityIn.facilityCodeId": "공통 기준정보(자산/시설 코드 목록 — 전 고객사 공통)의 id 다. 테넌트 칸이 없다",
    # K1b-2a: 온실가스 풀(전 고객사 공통 — 회사 칸 없음)의 노드·코드·계수 id.
    "GhgNodeCreateIn.parentId": "공통 기준정보(온실가스 인덱스 풀 — 전 고객사 공통)의 노드 id 다. 테넌트 칸이 없다",
    "GhgFacilityCreateIn.parentId": "공통 기준정보(온실가스 인덱스 풀 — 전 고객사 공통)의 노드 id 다. 테넌트 칸이 없다",
    "GhgFacilityCreateIn.facilityCodeId": (
        "공통 기준정보(자산/시설 코드 목록 — 전 고객사 공통)의 id 다. 테넌트 칸이 없다"
    ),
    "GhgFacilitySaveIn.facilityCodeId": "공통 기준정보(자산/시설 코드 목록 — 전 고객사 공통)의 id 다. 테넌트 칸이 없다",
    "GhgFacilitySaveIn.defaultFactorId": "공통 기준정보(시설별 배출계수 풀)의 계수 id 다. 테넌트 칸이 없다",
    # S12a-2: 행 계수 바꿈의 계수 id — 판 id 는 받지 않는다(서버가 그 지금 판을 잡는다).
    "EntryRowFactorIn.factorId": (
        "공통 풀 계수(ghg_factors)의 id 다. 테넌트 칸이 없다 — 그 잎의 살아 있는 계수가 아니면 422(actions 시험)"
    ),
    # S12a: 둘 다 테넌트 행 — 그 해·잎·사업장의 것이 아니면 422 fields.rows.<i>.…(행 0).
    "EntryRowIn.rowId": "테넌트 행(입력 행)을 가리킨다 — 남의·다른 사업장 행 422·행 0, tests/security/test_entries.py",
    "EntryRowIn.siteFacilityId": (
        "테넌트 행(사업장의 자산/시설)을 가리킨다 — 남의 것 422·행 0, tests/security/test_entries.py"
    ),
    "DraftingDocumentPutIn.documentId": (
        "테넌트 행(문서)을 가리킨다 — 남의 id 는 404·행 0, tests/security/test_drafting.py ⓑ 가 잰다(RP1)"
    ),
}

# tenant_read 의 경로에 넣을 A 의 행을 만드는 법: 경로의 자리 이름 → A 의 세션으로 만든다.
TENANT_READ_PLACEHOLDER: Final = "{document_id}"
# 요청 주소 = API 의 mount 자리 + openapi 의 경로 키. 키에는 접두가 없다(servers 의 "/api" 가 말한다 — config/urls.py).
API_ROOT: Final = "/api"

# tenant_create: 본문과 그 행이 드는 표.
CREATE_BODIES: Final[dict[Operation, tuple[str, dict[str, Any]]]] = {
    ("POST", "/sites"): ("sites", {"name": "B 의 새 사업장"}),
    ("POST", "/documents"): ("core_documents", {"fileName": "b.pdf", "sizeBytes": 100}),
    ("POST", "/branches"): ("sites", {"name": "B 의 새 지점"}),  # K1b-1
}


def of_kind(*kinds: str) -> list[Operation]:
    return sorted(key for key, kind in OPERATIONS.items() if kind in kinds)


AUTHENTICATED: Final = of_kind(
    "session",
    "bearer",
    "compute",
    "reference",
    "tenant_read",
    "tenant_list",
    "tenant_create",
    "contract_only",
    "run_paths",
    "greenwash_run_paths",
    "greenwash_rejudge_paths",  # GRJ1
    "greenwash_result2_paths",  # GE1b ④
    "translation_run_paths",
    "translation_layout_paths",
    "dataverify_run_paths",
    "materiality_run_paths",
    "scope3_run_paths",  # S3K1
    "scope3_original_paths",  # S3Q1
    "greenwash_list",
    "dataverify_list",
    "materiality_list",
    "document_paths",
    "translation_batch_paths",
    "branch_paths",  # K1b-1
    "index_selection_paths",  # K1b-2b
    "entry_paths",  # S12a
    "scope3_state_paths",  # S3K2a
    "scope3_edit_paths",  # S3K2b-1
    "drafting_paths",  # RP1
)


def operation_id(operation: Operation) -> str:
    return f"{operation[0]} {operation[1]}"


def openapi() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(json.dumps(api.get_openapi_schema(path_prefix="")))
    return document


def operations(document: dict[str, Any]) -> dict[Operation, dict[str, Any]]:
    return {
        (method.upper(), path): operation
        for path, item in document["paths"].items()
        for method, operation in item.items()
    }


def schema_name(ref: str) -> str:
    return ref.rsplit("/", 1)[1]


def id_fields(document: dict[str, Any]) -> set[str]:
    """요청 본문에서 닿는 스키마(중첩·$ref 를 따라간다)의 칸 가운데 이름이 `id` 이거나 `Id` 로 끝나는 것."""
    schemas: dict[str, Any] = document["components"]["schemas"]
    found: set[str] = set()
    seen: set[str] = set()

    def walk(node: object, owner: str | None) -> None:
        if isinstance(node, list):
            for item in cast("list[object]", node):
                walk(item, owner)
            return
        if not isinstance(node, dict):
            return
        for key, value in cast("dict[str, object]", node).items():
            if key == "$ref" and isinstance(value, str):
                name = schema_name(value)
                if name not in seen:
                    seen.add(name)
                    walk(schemas[name], name)
            elif key == "properties" and isinstance(value, dict):
                for field, sub in cast("dict[str, object]", value).items():
                    if owner is not None and (field == "id" or field.endswith("Id")):
                        found.add(f"{owner}.{field}")
                    walk(sub, owner)
            else:
                walk(value, owner)

    for operation in operations(document).values():
        if "requestBody" in operation:
            walk(operation["requestBody"], None)
    return found


def a_document_url(path: str, document_id: int) -> str:
    assert TENANT_READ_PLACEHOLDER in path, f"{path}: 행을 만드는 법을 모른다. TENANT_READ_PLACEHOLDER 를 고친다"
    return API_ROOT + path.replace(TENANT_READ_PLACEHOLDER, str(document_id))


def status_of(client: Client, method: str, url: str, body: dict[str, Any] | None = None) -> int:
    """동작 하나를 보내고 상태 코드만 돌려준다. body 가 None 이면 본문 없이 보낸다."""
    if method == "GET":
        return client.get(url).status_code
    if method == "POST" and body is None:
        return client.post(url).status_code
    if method == "POST":
        return client.post(url, data=body, content_type="application/json").status_code
    if method == "PUT":
        return client.put(url, data=body or {}, content_type="application/json").status_code
    if method == "PATCH":
        return client.patch(url, data=body or {}, content_type="application/json").status_code
    if method == "DELETE":
        return client.delete(url).status_code
    raise AssertionError(f"{method}: 이 메서드를 보내는 법을 status_of 에 더한다")


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage())


# 회사 경로의 두 길(K2b — 사용자 결정 ㉠ Bearer 통일): 옛 교환 쿠키(session)와 고객사 사용자의 access(bearer).
VIA: Final = ("session", "bearer")


def b_session(via: str = "session", b: int | None = None) -> Client:
    """회사 B 의 고객사 사용자의 Client. session 은 교환 쿠키, bearer 는 비밀번호를 바꾼 고객사 사용자의 access 를
    모든 요청의 Authorization 머리에 싣는다(쿠키 0)."""
    other = Client()
    if via == "session":
        login(other, sub="edk-user-2", tenant_id="tenant-b")
        return other
    assert b is not None
    access = customer_bearer(Client(), company_id=b, subdomain="tenant-b")
    return Client(headers={"Authorization": f"Bearer {access}"})


def document_facts(owner: Owner) -> list[tuple[Any, ...]]:
    """주인 역할이 본 문서 행 전부와 그 일감(분모): (id, 회사 id, 상태, ETag, 고친 때, 일감 수)."""
    return owner.execute(
        "SELECT d.id, d.company_id, d.status, d.etag, d.updated_at, "
        "(SELECT count(*) FROM run_jobs j WHERE j.document_id = d.id) FROM core_documents d ORDER BY d.created_at"
    ).fetchall()


# ── 표 ──


def test_every_operation_is_in_the_table() -> None:
    found = operations(openapi())
    assert sorted(found) == sorted(OPERATIONS)
    # 세션을 요구하는 동작(openapi 의 security)은 public 이 아닌 것과 같다.
    assert sorted(key for key, operation in found.items() if operation.get("security")) == AUTHENTICATED
    # UA1 +1: PATCH /users/{user_id} · AU1a +1: GET /audit-logs · AU1b-1 +1: GET /audit-logs/actors
    # · AU1b-2 +2: GET /run-logs·/run-logs/metrics
    # · G1b-1 +1: GET /greenwash/checks · X1b-2a +2: PATCH /documents/{id}·GET /documents/{id}/file
    # · G2c2 +5: /ai-settings/greenwash 다섯(bearer)
    # · AS2a +2: /ai-settings/greenwash 의 prompt-model 둘(bearer)
    # · TR2 +1: GET /translation/runs/{run_id}/result
    # · AD4S +1: GET /run-logs/export(bearer)
    # · AD4D +1: GET /run-logs/{run_id}(bearer)
    # · RF1 +1: GET /run-logs/{run_id}/files/{name}(bearer)
    # · DV1e +1: GET /dataverify/runs/{run_id}/result
    # · DV1g +1: GET /dataverify/runs
    # · TR3a +2: POST /translation/glossary/read · GET /translation/glossary/template
    # · TR3b +3: GET /translation/batches · GET …/batches/{batch_key} · GET …/batches/{batch_key}/archive
    # · GE1b +1: GET /greenwash/runs/{run_id}/result2
    assert (len(OPERATIONS), len(AUTHENTICATED)) == (167, 160)  # S3Q1 +1: GET …/scope3/runs/{run_id}/original
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · IRS3 +3: GET·POST /materiality/runs/{run_id}/result/edits · GET …/report(materiality_run_paths)
    # · S3K1 +2: GET …/scope3/runs/{run_id}/result(scope3_run_paths) · GET /inventory/scope3/template(reference)
    # · K1b-1 +11: /branches 여섯(tenant_create 하나·branch_paths 다섯) · /facility-codes(reference) · admin 넷(bearer)
    # · TR4 +7: /ai-settings/translation 일곱(bearer)
    # · IR3b +1: GET /materiality/runs/{run_id}/result
    # · DVA1 +7: /ai-settings/dataverify 일곱(bearer)
    # · IR3c +1: GET /materiality/runs
    # · TRP6 +1: GET /translation/documents/{document_id}/pages
    # · TRS3 +1: GET /translation/runs/{run_id}/layout
    # · IRW2 +1: POST /materiality/value-chain/read
    # · IR4 +7: /ai-settings/materiality 일곱(bearer)
    # · K1b-2a +12: inventory_admin_ghg_* 열둘(bearer)
    # · K1b-2b +2: inventory_scope12_index_tree · inventory_scope12_index_selections_save(index_selection_paths)
    # · S12a +10: inventory_scope12_* 열(entry_paths — 풀기 하나는 OPERATOR_COMPANY_OPERATIONS 에도)
    # · DVX1 +2: POST /dataverify/edk/read · GET /dataverify/edk/template
    # · RP1 +5: /drafting 다섯(drafting_paths)
    # · RP2d +2: GET /drafting/projects · GET …/result.docx(drafting_paths)
    # · RP2c +1: GET /drafting/projects/{project_id}/outline/changes(drafting_paths)
    # · RPS1 +1: GET /drafting/projects/{project_id}/runs(drafting_paths)
    # · S12a-2 +3: 입력주기·행 계수 바꿈·복구(entry_paths — 계수 바꿈은 OPERATOR_COMPANY_OPERATIONS 에도)
    # · RPA1 +7: /ai-settings/drafting 일곱(bearer)
    # · S12a-3 +1: GET /inventory/scope12/dashboard(entry_paths)
    # · S12b-1 +2: GET …/years/{year}/template · …/export(entry_paths)
    # · S3K2a +3: Scope 3 연도 상태·잠그기·풀기(scope3_state_paths — 풀기는 OPERATOR_COMPANY_OPERATIONS 에도)
    # · S3K2b-1 +4: Scope 3 줄 덧판 넷(scope3_edit_paths) · S3K2b-2 +1: 계수 수정
    # · S3D1 +1: GET /inventory/scope3/years/{year}/export(scope3_state_paths)
    assert len(of_kind("index_selection_paths")) == 2  # 닫힌 집합(패턴·접두 맞추기 0)
    assert len(of_kind("entry_paths")) == 17  # 닫힌 집합(S12a)
    # · S12a-2 +3
    # · S12a-3 +1
    # · S12b-1 +2
    assert len(of_kind("scope3_state_paths")) == 4  # 닫힌 집합(S3K2a · S3D1 +1: 데이터 엑셀)
    assert of_kind("scope3_edit_paths") == [  # 닫힌 목록(S3K2b-1)
        ("GET", "/inventory/scope3/runs/{run_id}/edits"),
        ("GET", "/inventory/scope3/runs/{run_id}/history"),
        ("POST", "/inventory/scope3/runs/{run_id}/categories/{category}/exclusions"),
        ("POST", "/inventory/scope3/runs/{run_id}/categories/{category}/factors"),
        ("POST", "/inventory/scope3/runs/{run_id}/categories/{category}/restorations"),
    ]
    assert len(OPERATOR_COMPANY_OPERATIONS) == 3  # 닫힌 집합(S12a 풀기)
    # · S12a-2 +1: 행 계수 바꿈
    # · S3K2a +1: Scope 3 카테고리 잠금 풀기


def test_every_id_field_in_a_request_body_is_classified() -> None:
    assert id_fields(openapi()) == set(ID_FIELDS)


# ── 세션 없이 ──


@pytest.mark.parametrize("operation", AUTHENTICATED, ids=operation_id)
def test_without_a_session_it_is_401(client: Client, operation: Operation) -> None:
    """본문을 보내지 않는다: 인증이 본문 읽기보다 먼저다(django-ninja 의 Operation.run). 본문이 필요한 POST 도 401.
    bearer 두 줄은 쿠키도 머리도 없어 401 no_token 이다(나머지는 no_session — 이 층은 상태 코드만 본다)."""
    method, path = operation
    url = API_ROOT + path.replace(TENANT_READ_PLACEHOLDER, "1")
    # 글자 그대로여도 401 이다(읽는 사람을 위해). {user_id} 는 경로 변환기(int)가 글자를 받지 않아 숫자로 바꾼다(K2c)
    url = url.replace("{run_id}", "1").replace("{name}", "a.xlsx").replace("{user_id}", "1")
    url = url.replace("{branch_id}", "1").replace("{code_id}", "1")  # K1b-1
    url = url.replace("{node_id}", "1").replace("{factor_id}", "1")  # K1b-2a
    url = url.replace("{year}", "2025")  # K1b-2b 인덱스 선택 저장(경로 인자 int)
    url = url.replace("{site_id}", "1").replace("{row_id}", "1")  # S12a 입력 저장·히스토리
    url = url.replace("{project_id}", "1")  # RP1 원고작성 프로젝트(경로 인자 int)
    assert status_of(client, method, url) == 401


# ── 회사 둘 ──


def company_operations() -> list[Operation]:
    """Bearer 를 먼저 받는 회사 동작(K2b): 인증 있는 동작 가운데 security 가 CompanyScopedAuth·SessionCookie 인 것."""
    found = operations(openapi())
    return sorted(
        key for key, op in found.items() if op.get("security") == [{"CompanyScopedAuth": []}, {"SessionCookie": []}]
    )


def concrete(path: str) -> str:
    path = path.replace("{batch_key}", "run-1")  # TR3b: 묶음 열쇠의 꼴(없는 묶음 — 404)
    path = path.replace("{branch_id}", "1")  # K1b-1: 없는 사업장(404)
    path = path.replace("{year}", "2025")  # K1b-2b: 인덱스 선택 저장의 해
    path = path.replace("{node_id}", "1").replace("{site_id}", "1").replace("{row_id}", "1")  # S12a: 없는 잎·행(404)
    path = path.replace("{project_id}", str(NO_PROJECT))  # RP1: 없는 프로젝트(404 — 문서·목차를 읽지도 쓰지도 않는다)
    path = path.replace("{history_id}", "1")  # S12a-2: 없는 행의 히스토리 줄(404)
    path = path.replace("{category}", "C4")  # S3K2a: Scope 3 카테고리(회사 행 아님)
    path = path.replace("{item_index}", "0")  # GRJ1: 재판단할 문장(없는 실행이라 404)
    return API_ROOT + path.replace(TENANT_READ_PLACEHOLDER, "1").replace("{run_id}", "1").replace("{name}", "a.xlsx")


# RP1: 늘 없는 원고작성 프로젝트 id. 보안 층의 TRUNCATE 는 번호를 되돌리지 않아 1 은 다른 시험이 만든 행일 수 있다 —
# 그 행이 있으면 문서 달기가 문서(올림 미완 422)를 읽는다.
NO_PROJECT: Final = 2_000_000_000


def test_a_bad_bearer_does_not_fall_back_to_the_cookie(client: Client, companies: tuple[int, int]) -> None:
    """(K2b) 유효한 교환 쿠키가 같이 와도 틀린 Bearer 는 444 다 — 쿠키로 넘어가지 않는다. 회사 동작 28 전부."""
    targets = company_operations()
    assert len(targets) == 95  # 분모: 쿠키 인증이던 회사 동작 25 에서 GET /me 를 뺀 것 + G1b-1 목록 줄 + X1b-2a 문서 둘
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · IRS3 +3: GET·POST /materiality/runs/{run_id}/result/edits · GET …/report
    # · S3K1 +2: GET /inventory/scope3/runs/{run_id}/result · GET /inventory/scope3/template
    # · K1b-1 +7: /branches 여섯 · /facility-codes
    # · K1b-2b +2: /inventory/scope12 둘
    # · S12a +10: /inventory/scope12 열(풀기 포함 — 틀린 Bearer 는 권한보다 먼저 444)
    # · TR2 +1: GET /translation/runs/{run_id}/result
    # · DV1e +1: GET /dataverify/runs/{run_id}/result
    # · DV1g +1: GET /dataverify/runs
    # · TR3a +2: 용어집 읽기·양식
    # · TR3b +3: 묶음 목록·하나 보기·zip
    # · IR3b +1: GET /materiality/runs/{run_id}/result
    # · IR3c +1: GET /materiality/runs
    # · TRP6 +1: GET /translation/documents/{document_id}/pages
    # · TRS3 +1: GET /translation/runs/{run_id}/layout
    # · IRW2 +1: POST /materiality/value-chain/read
    # · DVX1 +2: POST /dataverify/edk/read · GET /dataverify/edk/template
    # · RP1 +5: /drafting 다섯
    # · RP2d +2: GET /drafting/projects · GET …/result.docx
    # · RP2c +1: GET /drafting/projects/{project_id}/outline/changes
    # · RPS1 +1: GET /drafting/projects/{project_id}/runs
    # · S12a-2 +3: /inventory/scope12 셋(계수 바꿈 포함 — 틀린 Bearer 는 권한보다 먼저 444)
    # · S12a-3 +1: GET /inventory/scope12/dashboard
    # · S12b-1 +2: GET /inventory/scope12/years/{year}/template · …/export
    # · S3K2a +3: GET /inventory/scope3/years/{year} · POST·DELETE …/categories/{category}/lock(풀기 포함 — 444 먼저)
    login(client, tenant_id="tenant-a")
    assert client.get("/api/sites").status_code == 200  # 분모: 쿠키만이면 지난다
    with_bad = Client(headers={"Authorization": "Bearer not-a-token"})
    with_bad.cookies = client.cookies
    for method, path in targets:
        response = (
            with_bad.get(concrete(path)) if method == "GET" else getattr(with_bad, method.lower())(concrete(path))
        )
        assert (response.status_code, response.json()["error"]["code"]) == (444, "TOKEN_NOT_VALID"), (method, path)


def test_an_operator_bearer_with_two_companies_is_400_on_the_company_work(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """(K2b·MARC-ENT-374·380) 운영 관리자의 Bearer 로 회사 업무 19: 회사가 둘이라 작업 회사를 못 고른다 — 회사를 고르는
    17 은 400 company_ambiguous, 고르지 않는 둘(비교 501·기본 단어 200)은 회사와 상관없다. 회사 행을 읽지도 쓰지도
    않는다."""
    operator = operator_bearer(owner)
    before = (count(owner, "sites"), count(owner, "core_documents"))
    found = operations(openapi())
    targets = {found[key]["operationId"]: key for key in company_operations()}
    work = {op: targets[op] for op in sorted(set(targets) - CUSTOMER_ONLY - OPERATOR_COMPANY_OPERATIONS)}
    # · S3K1 +2(고르는 쪽 — Scope 3 결과 · 고르지 않는 쪽 — Scope 3 빈 양식)
    assert len(work) == 69 + 14  # 분모: 회사를 고르는 24(DV1e +1 · TR3b +3 · DV1g +1 · IR3b +1) + 고르지 않는 4(TR3a+2)
    # · RM1c ③ +1(고르는 쪽 — 실행 구획 목록)
    # · S3Q1 +1(고르는 쪽 — Scope 3 원본)
    # · S3D1 +1(고르는 쪽 — Scope 3 데이터 엑셀)
    # · IRS3 +3(회사를 고르는 쪽 — 결과 고침 둘 · 고친 판 엑셀)
    # · IR3c +1(회사를 고르는 쪽 — GET /materiality/runs)
    # · TRP6 +1(회사를 고르는 쪽 — GET /translation/documents/{document_id}/pages)
    # · TRS3 +1(회사를 고르는 쪽 — GET /translation/runs/{run_id}/layout)
    # · IRW2 +1(고르지 않는 쪽 — POST /materiality/value-chain/read)
    # · K1b-1 +6(고르는 쪽 — /branches) · +1(고르지 않는 쪽 — /facility-codes)
    # · K1b-2b +2(고르는 쪽 — /inventory/scope12 둘)
    # · S12a +9(고르는 쪽 — /inventory/scope12 입력 아홉. 풀기는 OPERATOR_COMPANY_OPERATIONS — test_entries.py)
    # · DVX1 +2(고르지 않는 쪽 — POST /dataverify/edk/read · GET /dataverify/edk/template)
    # · RP1 +5(고르는 쪽 — /drafting 다섯)
    # · RP2d +2(고르는 쪽 — 목록·docx)
    # · RP2c +1(고르는 쪽 — 목차 차이)
    # · RPS1 +1(고르는 쪽 — 프로젝트 실행 목록)
    # · S12a-2 +2(고르는 쪽 — 입력주기·복구. 계수 바꿈은 OPERATOR_COMPANY_OPERATIONS — test_entries.py)
    # · S12a-3 +1(고르는 쪽 — 대시보드)
    # · S12b-1 +2(고르는 쪽 — 엑셀 둘)
    # · S3K2a +2(고르는 쪽 — Scope 3 연도 상태·잠그기. 풀기는 OPERATOR_COMPANY_OPERATIONS — test_scope3_state.py)
    # · S3K2b-1 +4(고르는 쪽 — Scope 3 줄 덧판 넷)
    # · S3K2b-2 +1(고르는 쪽 — Scope 3 계수 수정)
    assert set(NOT_CHOOSING) <= set(work)
    for op, (method, path) in work.items():
        response = send_passing(operator, op, method, path)
        expected = (NOT_CHOOSING[op], None) if op in NOT_CHOOSING else (400, "COMPANY_AMBIGUOUS")
        got = (response.status_code, None if op in NOT_CHOOSING else response.json()["error"]["code"])
        assert got == expected, (method, path)
        if op == "greenwash_terms_default":  # 공용 값 — 어느 회사의 이름·서브도메인·id 칸도 싣지 않는다
            text = response.content.decode()
            assert not any(word in text for word in ("가 회사", "나 회사", "tenant-a", "tenant-b", "company"))
    assert (count(owner, "sites"), count(owner, "core_documents")) == before == (0, 0)


def test_an_operator_bearer_is_403_on_every_customer_only_company_operation(
    owner: Owner, companies: tuple[int, int]
) -> None:
    """(K2b·MARC-ENT-374) 운영 관리자의 Bearer 로 고객사 전용 9(사업장·인벤토리·기준 자료): 인증은 지나고
    권한 표가 403 forbidden — 회사 행을 읽지도 쓰지도 않는다."""
    operator = operator_bearer(owner)
    before = (count(owner, "sites"), count(owner, "core_documents"))
    found = operations(openapi())
    targets = {found[key]["operationId"]: key for key in company_operations()}
    customer_only = {op: targets[op] for op in sorted(set(targets) & CUSTOMER_ONLY)}
    assert len(customer_only) == len(CUSTOMER_ONLY) == 9  # 분모
    assert len(customer_only) + 69 + 14 + len(OPERATOR_COMPANY_OPERATIONS) == len(targets) == 95  # 회사 동작 95
    # · RM1c ③ +1: GET /runs/{run_id}/segments(회사 업무 — 고르는 쪽)
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · IRS3 +3: 회사 업무 +3(결과 고침 둘 · 고친 판 엑셀 — 고르는 쪽)
    # · S3K1: 회사 업무 +2(고르는 쪽 Scope 3 결과 · 고르지 않는 쪽 Scope 3 빈 양식)
    # = 회사 업무 58 + 고객사 전용 9 + 회사를 고르는 운영 관리자 칸 1(빠짐 0)
    # · RP2d·RP2c: 회사 업무 +3 · S12a-2: 회사 업무 +2 · 회사를 고르는 운영 관리자 칸 +1(계수 바꿈) — 위 줄 = 61 + 9 + 2
    # · S12a-3: 회사 업무 +1(대시보드 — 고르는 쪽)
    # · S12b-1: 회사 업무 +2(엑셀 둘 — 고르는 쪽)
    # · S3K2a: 회사 업무 +2(연도 상태·잠그기 — 고르는 쪽) · 회사를 고르는 운영 관리자 칸 +1(풀기) — 81 = 9 + 59 + 10 + 3
    # · S3D1: 회사 업무 +1(데이터 엑셀 — 고르는 쪽)
    for op, (method, path) in customer_only.items():
        response = send_passing(operator, op, method, path)
        assert (response.status_code, response.json()["error"]["code"]) == (403, "FORBIDDEN"), (method, path)
    assert (count(owner, "sites"), count(owner, "core_documents")) == before == (0, 0)


# 회사 동작 28 가운데 운영 관리자에게 닫힌 고객사 전용 9(core/permissions.py 의 CUSTOMER 칸 — 표를 읽지 않고 글자로).
CUSTOMER_ONLY: Final = frozenset(
    {
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
)
# 회사 업무 가운데 회사를 고르지 않는 둘: 상태 코드(비교는 permitted 뒤 곧장 501, 기본 단어는 공용 값 200).
# IRS3 ② 결과 고침 저장의 유효한 본문(지어낸 값 — result2-sample 의 첫 영향 정의 칸).
EDIT_POINTER: Final = "/part2/topics/0/subtopics/0/impact/rows/0/impactDefinition"
EDIT_BODY: Final = {"baseRevision": 0, "changes": [{"pointer": EDIT_POINTER, "value": "가상 고친 정의"}]}
NOT_CHOOSING: Final[dict[str, int]] = {"greenwash_compare_get": 501, "greenwash_terms_default": 200}
# TR3a: 영문번역 용어집 둘도 회사를 고르지 않는다 — 양식은 공용 파일, 읽기는 본문 없이 보내면 200 {ok: false, not_xlsx}.
NOT_CHOOSING.update({"translation_glossary_read": 200, "translation_glossary_template": 200})
# IRW2: 중대성평가 가치사슬 엑셀 읽기도 회사를 고르지 않는다 — 본문 없이 보내면 200 {ok: false, not_xlsx}.
NOT_CHOOSING.update({"materiality_value_chain_read": 200})
# DVX1: 데이터 검증 EDK 엑셀 둘도 회사를 고르지 않는다 — 양식은 공용 파일, 읽기는 본문 없이 보내면
# 200 {ok: false, not_xlsx}.
NOT_CHOOSING.update({"dataverify_edk_read": 200, "dataverify_edk_template": 200})
# K1b-1: 자산/시설 코드 목록 읽기도 회사를 고르지 않는다 — 공통 목록(회사 칸 없음)이라 200.
NOT_CHOOSING.update({"organization_facility_codes_list": 200})
# S3K1: Scope 3 빈 양식도 회사를 고르지 않는다 — 저장소의 공용 파일(받은 v2.1)이라 200 xlsx.
NOT_CHOOSING.update({"inventory_scope3_template": 200})


def operator_bearer(owner: Owner) -> Client:
    """운영 관리자(비밀번호를 바꾼 뒤 — is_initial 끔)의 Bearer 만 실은 클라이언트."""
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    created = create_operator(username="ops", name="운영자", password="Blue-Harbor-7310")
    assert isinstance(created, UserCreated)
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login", data={"username": "ops", "password": "Blue-Harbor-7310"}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    operator = Client(headers={"Authorization": f"Bearer {logged.json()['access']}"})
    assert operator.get("/api/users/me").status_code == 200  # 분모: 토큰은 산 것이다
    return operator


def send_passing(client: Client, op: str, method: str, path: str) -> Any:
    """PASSING_REQUESTS 의 쿼리·본문으로 보낸다(몸 없이 보내면 POST·PUT·PATCH 가 꼴 검사 422)."""
    query, body = PASSING_REQUESTS[op]
    url = concrete(path) + query
    if method == "GET":
        return client.get(url)
    if body is None:
        return getattr(client, method.lower())(url)
    return getattr(client, method.lower())(url, data=body, content_type="application/json")


# 회사 동작 28 마다 꼴 검사와 권한을 지나는 가장 작은 요청: operationId → (쿼리 문자열, 본문).
# 경로는 concrete 가 채운다.
# core/tests/test_permissions_wiring.py 의 REQUESTS 와 같은 꼴을 여기 다시 적는다(업무 층 모듈을 들이지 않는다).
CALC_BODY: Final[dict[str, Any]] = {"rows": [], "gwpSetId": "kr-ets-decree-annex2"}
PASSING_REQUESTS: Final[dict[str, tuple[str, dict[str, Any] | None]]] = {
    "accounts_sites_list": ("", None),
    "accounts_sites_create": ("", {"name": "A 의 새 사업장"}),
    "core_documents_create": ("", {"fileName": "a.pdf", "sizeBytes": 1}),
    "core_documents_confirm": ("", None),
    "core_documents_get": ("", None),
    "core_documents_list": ("", None),
    "core_documents_versions": ("", None),
    # X1b-2a: 고치기는 비지 않은 바른 본문(빈 본문은 422 — NOT_PASSED), 원본은 없는 id 라 둘 다 404.
    "core_documents_update": ("", {"reportYear": 2025}),
    "core_documents_file_get": ("", None),
    "runs_create": ("", {"module": "greenwash", "documentId": 1}),
    "runs_list": ("", None),
    "runs_get": ("", None),
    "runs_file_get": ("", None),
    "runs_segments_list": ("?step=x", None),  # RM1c ③ — step 없으면 422(NOT_PASSED), 없는 실행 404
    "greenwash_result_get": ("", None),
    "greenwash_result2_get": ("", None),  # GE1b ④
    "greenwash_review_get": ("", None),
    "greenwash_review_put": ("", {"marks": []}),
    "greenwash_item_rejudge": ("", None),  # GRJ1
    "greenwash_compare_get": ("?base=1&target=2", None),
    "greenwash_report_get": ("", None),
    "greenwash_terms_default": ("", None),
    "greenwash_checks_get": ("", None),
    "translation_result_get": ("", None),
    # 용어집 읽기는 본문 없이 보낸다(200 {ok: false, kind: not_xlsx} — 회사 행을 읽지도 쓰지도 않는다).
    "translation_glossary_read": ("", None),
    "translation_glossary_template": ("", None),
    # TR3b: 목록은 빈 쪽 200, 하나 보기·zip 은 없는 묶음 404(셋 다 회사 행을 읽기만).
    "translation_batches_list": ("", None),
    "translation_batch_get": ("", None),
    "translation_batch_archive": ("", None),
    "translation_document_pages": ("", None),
    "translation_layout_get": ("", None),
    "dataverify_result_get": ("", None),
    "dataverify_runs_list": ("", None),
    # DVX1 EDK 엑셀 둘: 읽기는 본문 없이(200 {ok: false, kind: not_xlsx}) · 양식은 year 없이(200 xlsx).
    "dataverify_edk_read": ("", None),
    "dataverify_edk_template": ("", None),
    "materiality_result_get": ("", None),
    "materiality_runs_list": ("", None),
    "materiality_value_chain_read": ("", None),
    # IRS3 ② 결과 고침 둘: 없는 실행이라 404(저장은 실행을 먼저 찾아 쓰기 0)
    "materiality_result_edits_get": ("", None),
    "materiality_result_edits_post": ("", EDIT_BODY),
    "materiality_report_get": ("", None),  # IRS3 ③ 없는 실행이라 404(감사 줄 0)
    # S3K1 Scope 3 코랩 둘: 결과는 없는 실행이라 404 · 빈 양식은 200 xlsx.
    "inventory_scope3_result_get": ("", None),
    "inventory_scope3_original_get": ("", None),  # S3Q1: 없는 실행이라 404(저장소를 읽지 않는다)
    "inventory_scope3_template": ("", None),
    # K1b-1 사업장 여섯·코드 목록 읽기: 목록 200 · 하나·저장·토글·삭제는 없는 id 라 404 · 코드 목록 200.
    "organization_branches_list": ("", None),
    "organization_branches_get": ("", None),
    # 만들기는 facilities[].id 로 늘 404 — 쓰기 0(몇 번 보내도 같다). 사업장 셈(:211·:655 등) 0줄의 근거
    "organization_branches_create": (
        "",
        {"name": "A 의 새 지점", "facilities": [{"id": 1, "facilityCodeId": 1, "detailName": "x"}]},
    ),
    "organization_branches_save": (
        "",
        {"name": "A 의 새 지점", "inventoryEnabled": True, "facilities": [], "updatedAt": "2026-01-02T03:04:05+09:00"},
    ),
    "organization_branches_inventory": ("", {"ids": [1], "enabled": True}),
    "organization_branches_delete": ("", {"ids": [1]}),
    "organization_facility_codes_list": ("", None),
    "inventory_scope12_index_tree": ("?year=2025", None),
    "inventory_scope12_index_selections_save": ("", {"facilityNodeIds": []}),  # 빈 선택 — 해 행 하나만(A)
    # S12a 입력 열: 해·리스트 200 · 나머지는 없는 잎·행이라 404(쓰기 0). 풀기는 운영 관리자 칸(고리에서 소속으로 뺌).
    "inventory_scope12_years": ("", None),
    "inventory_scope12_rows": ("?year=2025", None),
    "inventory_scope12_index_detail": ("", None),
    "inventory_scope12_rows_save": ("", {"rows": []}),
    "inventory_scope12_rows_delete": ("", {"ids": [1]}),
    "inventory_scope12_memo_save": ("", {"memo": "메모"}),
    "inventory_scope12_lock": ("", None),
    "inventory_scope12_unlock": ("", None),
    "inventory_scope12_decimals_save": ("", {"decimals": 2}),
    "inventory_scope12_row_history": ("", None),
    # S12a-2: 입력주기는 없는 사업장 404 · 계수 바꿈(운영 관리자 칸)·복구는 없는 행 404 — 쓰기 0.
    "inventory_scope12_period_save": ("", {"period": "month"}),
    "inventory_scope12_row_factor_save": ("", {"factorId": 1, "reason": "사유"}),
    "inventory_scope12_history_restore": ("", {}),
    # S12a-3: 대시보드 — 읽기, 쓰기 0.
    "inventory_scope12_dashboard": ("?year=2025", None),
    # S12b-1: 엑셀 내려받기 둘 — 읽기, 쓰기 0(해가 없으면 404 — 인증·권한은 지남).
    "inventory_scope12_template": ("", None),
    "inventory_scope12_export": ("", None),
    # S12b-2: 일괄 올리기 — 본문 없이(앞 줄의 빈 선택 저장으로 선택 0 인 해 → 404 — 인증·권한은 지남, 바이트를 읽기 전).
    "inventory_scope12_upload": ("", None),
    # S3K2a: 연도 상태 — 읽기 · 잠그기는 runId 필수(실행 없음이라 409 not_computed — 인증·권한은 지남, 쓰기 0) · 풀기
    "inventory_scope3_year_get": ("", None),
    "inventory_scope3_lock": ("?runId=1", None),
    "inventory_scope3_unlock": ("", None),
    # S3D1: 데이터 엑셀 — 읽기, 쓰기 0(실행이 없어 404 — 인증·권한은 지남).
    "inventory_scope3_export": ("", None),
    # S3K2b-1·2: 줄 덧판 다섯 — 실행이 없어 404(인증·권한은 지남, 쓰기 0). 몸은 유효한 지어낸 값
    "inventory_scope3_rows_exclude": ("", {"rowIds": ["가상_C4!20"], "reason": "가상 사유"}),
    "inventory_scope3_rows_restore": ("", {"rowIds": ["가상_C4!20"], "reason": "가상 사유"}),
    "inventory_scope3_edits_get": ("", None),
    "inventory_scope3_history_get": ("", None),
    "inventory_scope3_row_factor": (
        "",
        {"rowId": "가상_C4!20", "choice": "applied", "rank": None, "custom": None, "reason": "가상 사유"},
    ),
    "inventory_calc": ("", CALC_BODY),
    "inventory_scope3_shortlist": ("", {"row": {"itemName": "합성 강판"}, "category": 1}),
    # 빈 목록은 생성 모델 쪽을 건드리지 않는다(공급사 호출 0 — 답의 묶음이 빈 것으로 본다).
    "inventory_scope3_classify": ("", {"rows": []}),
    "reference_sources": ("", None),
    "reference_factors": ("", None),
    "reference_assemble": ("", {}),
    "reference_assemble_electricity": ("", {}),
    # RP1 원고작성 다섯: 만들기는 201(회사 A 에 프로젝트 한 행 — 사업장·문서 셈 밖), 나머지는 없는 프로젝트·실행 404.
    "drafting_projects_create": ("", {"year": 2025, "name": "A 의 원고"}),
    "drafting_project_get": ("", None),
    "drafting_project_document_put": ("", {"documentId": 1}),
    "drafting_outline_put": (
        "",
        {"nodes": [{"key": "a", "parentKey": None, "depth": 1, "title": "가", "requirement": ""}]},
    ),
    "drafting_result_get": ("", None),
    "drafting_projects_list": ("", None),  # RP2d
    "drafting_result_download": ("", None),  # RP2d — 없는 실행 404
    "drafting_outline_changes": ("?baseRunId=1", None),  # RP2c — 없는 프로젝트 404
    "drafting_project_runs": ("", None),  # RPS1 — 없는 프로젝트 404
}
# 거절로 세는 상태. 422 도 든다: 본문 꼴 검사가 경로 함수(그 첫 문장이 permitted) 앞이라 422 는 권한을 재지 못한 것이다.
NOT_PASSED: Final = frozenset({400, 401, 403, 405, 422, 444})


def test_a_customer_bearer_passes_auth_and_permission_on_every_company_operation(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """(AUTHZ1) 고객사 사용자의 Bearer(쿠키 0)로 회사 동작 28 전부가 인증과 권한을 지난다 — 운영 관리자 400·403 의 짝.
    쓰기 둘(사업장·문서 만들기)은 회사 A 에 든다."""
    a, _ = companies
    found = operations(openapi())
    targets = company_operations()
    assert len(targets) == 95  # 분모: 대상이 비면 아래 고리가 아무것도 재지 않는다 · TR2 +1 · DV1e +1 · TR3a +2
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · IRS3 +3: GET·POST /materiality/runs/{run_id}/result/edits · GET …/report
    # · S3K1 +2: GET /inventory/scope3/runs/{run_id}/result · GET /inventory/scope3/template
    # · K1b-1 +7: /branches 여섯 · /facility-codes
    # · K1b-2b +2: /inventory/scope12 둘
    # · S12a +10: /inventory/scope12 열(풀기는 아래 고리에서 소속으로 뺌 — 고객사 403 은 test_entries.py)
    # · TR3b +2
    # · DV1g +1: GET /dataverify/runs
    # · IR3b +1: GET /materiality/runs/{run_id}/result
    # · IR3c +1: GET /materiality/runs
    # · TRP6 +1: GET /translation/documents/{document_id}/pages
    # · TRS3 +1: GET /translation/runs/{run_id}/layout
    # · IRW2 +1: POST /materiality/value-chain/read
    # · DVX1 +2: POST /dataverify/edk/read · GET /dataverify/edk/template
    # · RP1 +5: /drafting 다섯
    # · RP2d +2: GET /drafting/projects · GET …/result.docx
    # · RP2c +1: GET /drafting/projects/{project_id}/outline/changes
    # · RPS1 +1: GET /drafting/projects/{project_id}/runs
    # · S12a-2 +3: /inventory/scope12 셋(계수 바꿈은 아래 고리에서 소속으로 뺌 — 고객사 403 은 test_entries.py)
    # · S12a-3 +1: GET /inventory/scope12/dashboard
    # · S12b-1 +2: GET /inventory/scope12/years/{year}/template · …/export
    # · S3K2a +3: GET /inventory/scope3/years/{year} · POST·DELETE …/lock(풀기는 아래 고리에서 소속으로 뺌)
    by_id = {found[key]["operationId"]: key for key in targets}
    assert set(by_id) == set(PASSING_REQUESTS)  # 회사 동작을 더하면 여기 요청 한 줄을 더한다
    access = customer_bearer(Client(), company_id=a, subdomain="tenant-a")
    customer = Client(headers={"Authorization": f"Bearer {access}"})
    assert not customer.cookies  # 머리만 — 쿠키로 지나는 것이 아니다
    before = (count(owner, "sites"), count(owner, "core_documents"))
    statuses: dict[str, int] = {}
    for op, (method, path) in sorted(by_id.items()):
        if op in OPERATOR_COMPANY_OPERATIONS:
            continue  # 운영 관리자 칸 — 고객사 Bearer 403 은 tests/security/test_entries.py 가 잰다
        query, body = PASSING_REQUESTS[op]
        url = concrete(path) + query
        if method == "GET":
            response = customer.get(url)
        elif body is None:
            response = getattr(customer, method.lower())(url)
        else:
            response = getattr(customer, method.lower())(url, data=body, content_type="application/json")
        statuses[op] = response.status_code
        assert response.status_code not in NOT_PASSED, (op, response.status_code, response.content.decode()[:300])
        if op == "inventory_scope3_classify":
            assert response.json()["groups"] == []  # 공급사를 부르지 않았다
        if op == "inventory_scope12_upload":
            assert response.status_code == 404  # 선택 0 인 해(앞 줄의 빈 선택 저장이 해 행을 만듦) — 파일 앞에서 끊긴다
    after = (count(owner, "sites"), count(owner, "core_documents"))
    written = owner.execute(
        "SELECT (SELECT array_agg(DISTINCT company_id) FROM sites),"
        " (SELECT array_agg(DISTINCT company_id) FROM core_documents)"
    ).fetchone()
    print(f"AUTHZ1 대상 {len(statuses)} · 상태 {sorted(statuses.items())}")
    print(f"AUTHZ1 쓰기 sites {before[0]}→{after[0]} · core_documents {before[1]}→{after[1]} · 회사 {written}")
    assert before == (0, 0)
    assert after == (1, 1)  # 분모: 사업장·문서 만들기가 실제로 썼다
    assert written == ([a], [a])  # 회사 A 에


@pytest.mark.parametrize("operation", of_kind("tenant_read"), ids=operation_id)
@pytest.mark.parametrize("via", VIA)
def test_another_tenants_document_is_not_found(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage, operation: Operation, via: str
) -> None:
    method, path = operation
    a, _ = companies
    login(client, tenant_id="tenant-a")
    document_id = upload_as(client, fake, owner)
    url = a_document_url(path, document_id)
    assert client.get(a_document_url("/documents/{document_id}", document_id)).status_code == 200  # A 는 본다
    before = document_facts(owner)
    assert [(row[1], row[2], row[5]) for row in before] == [(a, "uploaded", 1)]  # 분모: A 의 문서 1, 일감 1
    head_calls = len(fake.head_calls)

    assert status_of(b_session(via, companies[1]), method, url) == 404
    assert document_facts(owner) == before  # A 의 행 그대로
    assert len(fake.head_calls) == head_calls  # 저장소에 묻지도 않았다


def document_ids(owner: Owner, company_id: int) -> set[int]:
    """주인 역할이 센 그 회사의 문서 id 전부(분모)."""
    rows = owner.execute("SELECT id FROM core_documents WHERE company_id = %s", [company_id])
    return {int(document_id) for (document_id,) in rows}


@pytest.mark.parametrize("via", VIA)
def test_numeric_neighbour_document_ids_are_not_found_for_my_session(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    """문서 id 는 숫자(식별 열)라 셀 수 있다. A 의 문서 id 전부와 B 의 문서 id ±1·±2 를 tenant_read 의 동작마다
    B 의 세션으로 넣어도 다 404 이고, A 의 행은 그대로다(sites 의 숫자 이웃 테스트와 같은 꼴).

    A·B·A·A 차례로 만들어 B 의 이웃 id 가 실제로 A 의 행이게 한다(식별 열은 한 테스트 안에서 이어진다).
    """
    reads = of_kind("tenant_read")
    assert reads  # 분모: 잴 동작이 있다
    a, b = companies
    other = b_session(via, companies[1])
    login(client, tenant_id="tenant-a")
    upload_as(client, fake, owner)
    b_document = upload_as(other, fake, owner)
    for _ in range(2):
        upload_as(client, fake, owner)

    a_ids, b_ids = document_ids(owner, a), document_ids(owner, b)
    assert (len(a_ids), b_ids) == (3, {b_document})  # 분모: 주인이 센 A 의 문서 3, B 의 문서 1
    neighbours = {b_document + step for step in (-2, -1, 1, 2) if b_document + step > 0} - b_ids
    assert neighbours & a_ids  # 이웃 id 가운데 실제로 A 의 행인 것이 있다(빈 id 만 친 것이 아니다)
    outsiders = sorted(a_ids | neighbours)
    assert not set(outsiders) & b_ids
    # 대조: B 는 제 문서를 본다(아래의 404 가 「전부 404」가 아니다).
    assert other.get(a_document_url("/documents/{document_id}", b_document)).status_code == 200

    before = document_facts(owner)
    head_calls = len(fake.head_calls)
    tried = [
        (method, path, document_id, status_of(other, method, a_document_url(path, document_id)))
        for method, path in reads
        for document_id in outsiders
    ]
    assert len(tried) == len(reads) * len(outsiders)  # 분모: 동작 × 넣은 id
    assert [entry for entry in tried if entry[3] != 404] == []
    assert document_facts(owner) == before  # A 의 행 그대로(올림 확인이 고치지 못했다)
    assert len(fake.head_calls) == head_calls  # 저장소에 묻지도 않았다


@pytest.mark.parametrize("via", VIA)
def test_a_list_shows_only_my_tenant(owner: Owner, companies: tuple[int, int], via: str) -> None:
    # 쿠키 세션의 회사로 거르는 목록은 이 하나다(그런 목록을 더하면 여기에 그 분모를 더한다).
    # /users(K2c)는 bearer 갈래 — 요청의 companyId 로 고른 회사로 거른다.
    # 격리는 test_user_admin 이 회사 A·B 분모로 잰다.
    assert of_kind("tenant_list") == [("GET", "/sites")]
    a, b = companies
    for name in ("A 본사", "A 공장"):
        add_site(owner, a, name)
    for name in ("B 본사", "B 공장", "B 창고"):
        add_site(owner, b, name)
    assert count(owner, "sites") == 5  # 분모: 주인이 센 전체

    response = b_session(via, companies[1]).get("/api/sites")
    assert response.status_code == 200
    assert sorted(site["name"] for site in response.json()["sites"]) == ["B 공장", "B 본사", "B 창고"]


def site_ids(owner: Owner, company_id: int) -> set[int]:
    """주인 역할이 센 그 회사의 사업장 id 전부(분모)."""
    return {int(site_id) for (site_id,) in owner.execute("SELECT id FROM sites WHERE company_id = %s", [company_id])}


@pytest.mark.parametrize("via", VIA)
def test_numeric_neighbour_ids_never_show_up_for_my_session(owner: Owner, companies: tuple[int, int], via: str) -> None:
    """id 가 이웃한 숫자(식별 열)라도 B 의 세션의 목록·만들기에는 B 의 것만 나온다. /me 의 회사는 세션의 것이다.

    sites 에는 id 로 닿는 경로가 없다: 목록의 id 집합이 주인이 센 B 의 id 집합과 같고, A 의 id·B 의 끝 바로 밖의
    id 가 응답 어디에도 없는 것을 잰다.
    """
    a, b = companies
    for name in ("A 본사", "A 공장"):
        add_site(owner, a, name)
    for name in ("B 본사", "B 공장"):
        add_site(owner, b, name)
    other = b_session(via, companies[1])
    me = other.get("/api/me" if via == "session" else "/api/users/me")  # GET /me 는 쿠키만(K2b) — Bearer 는 /users/me
    assert me.status_code == 200
    assert me.json()["companyId"] == b

    created = other.post("/api/sites", data={"name": "B 창고"}, content_type="application/json")
    assert created.status_code == 201
    listed = other.get("/api/sites")
    assert listed.status_code == 200

    a_ids, b_ids = site_ids(owner, a), site_ids(owner, b)
    assert (len(a_ids), len(b_ids)) == (2, 3)  # 분모: 주인이 센 A 의 행 2, B 의 행 3(만든 것 포함)
    outsiders = a_ids | {max(b_ids) + 1, min(b_ids) - 1}
    assert not outsiders & b_ids
    listed_ids = {int(site["id"]) for site in listed.json()["sites"]}
    assert listed_ids == b_ids  # B 의 것 전부, 그리고 B 의 것만
    assert int(created.json()["site"]["id"]) in b_ids
    # /users/me(Bearer 길)의 "id" 는 사용자 id 라 사업장 id 와 겹칠 수 있다 — 사업장 id 를 찾는 글은 사업장 응답 둘과
    # 쿠키 길의 /me(그 칸 이름은 userId)뿐이다.
    texts = [listed.content.decode(), created.content.decode()] + ([me.content.decode()] if via == "session" else [])
    for text in texts:
        found = {int(site_id) for site_id in re.findall(r'"id":\s*"?(-?\d+)"?', text)}
        assert not found & outsiders, text


@pytest.mark.parametrize("operation", of_kind("tenant_create"), ids=operation_id)
@pytest.mark.parametrize("via", VIA)
def test_a_create_lands_in_my_tenant(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, operation: Operation, via: str
) -> None:
    assert operation in CREATE_BODIES, f"{operation}: 본문과 표를 CREATE_BODIES 에 더한다"
    table, body = CREATE_BODIES[operation]
    method, path = operation
    # 본문에 테넌트를 실을 칸이 없다: 스키마가 모르는 칸을 막고(additionalProperties false), tenant 라는 칸이 없다.
    document = openapi()
    ref: str = operations(document)[operation]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema = document["components"]["schemas"][schema_name(ref)]
    assert schema["additionalProperties"] is False
    assert [field for field in schema["properties"] if "tenant" in field.lower()] == []
    assert [field for field in schema["properties"] if "company" in field.lower()] == []

    a, b = companies
    other = b_session(via, companies[1])
    assert (
        status_of(other, method, API_ROOT + path, {**body, "tenantId": "tenant-a"}) == 422
    )  # 본문에 테넌트를 실으면 거절
    assert status_of(other, method, API_ROOT + path, {**body, "companyId": a}) == 422  # 회사 id 를 실어도 거절
    assert count(owner, table) == 0

    assert status_of(other, method, API_ROOT + path, body) == 201
    # 표마다 회사 칸이 있다(지금 둘 다 company_id): 세션 B 의 회사 id.
    column = CREATE_COMPANY_COLUMN[table]
    rows = owner.execute(sql.SQL("SELECT {} FROM {}").format(sql.Identifier(column), sql.Identifier(table))).fetchall()
    assert rows == [(b,)]  # 분모: 주인이 센 1행


# ── 계약 먼저(contract_only) ──

# 꼴 검사를 지나는 가장 작은 요청(경로의 자리는 int 로 채운다).
CONTRACT_ONLY_BODIES: Final[dict[Operation, dict[str, Any] | None]] = {
    ("PUT", "/greenwash/runs/{run_id}/review"): {"marks": []},
}

# 꼴 검사를 지나는 가장 작은 쿼리(필수 쿼리가 있는 경로만).
CONTRACT_ONLY_QUERIES: Final[dict[Operation, str]] = {
    ("GET", "/greenwash/compare"): "?base=1&target=2",
}


@pytest.mark.parametrize("operation", of_kind("contract_only"), ids=operation_id)
def test_a_contract_only_route_is_501_and_writes_nothing(
    client: Client, owner: Owner, companies: tuple[int, int], operation: Operation
) -> None:
    """A 의 세션으로 501 이고 테넌트 표의 행 수가 그대로다. 회사 격리는 몸이 없어 재지 못한다(X1b, 머리 글)."""
    method, path = operation
    login(client, tenant_id="tenant-a")
    add_site(owner, companies[1], "B 본사")
    before = {table: count(owner, table) for table in ("core_documents", "run_jobs", "sites")}
    assert before == {"core_documents": 0, "run_jobs": 0, "sites": 1}  # 분모: B 의 사업장 1
    url = API_ROOT + path.replace("{document_id}", "1").replace("{run_id}", "1").replace("{name}", "a.xlsx")
    url += CONTRACT_ONLY_QUERIES.get(operation, "")
    assert status_of(client, method, url, CONTRACT_ONLY_BODIES.get(operation)) == 501
    assert {table: count(owner, table) for table in before} == before


# ── 그린워싱 실행 경로(greenwash_run_paths — G1b-1) ──


@pytest.mark.parametrize("operation", of_kind("greenwash_run_paths"), ids=operation_id)
@pytest.mark.parametrize("via", VIA)
def test_a_greenwash_run_path_hides_another_companys_run(
    client: Client, owner: Owner, companies: tuple[int, int], operation: Operation, via: str
) -> None:
    """A 의 끝난 그린워싱 실행(주인 역할로 심음)을 B 로: 404, 없는 id 도 404, 검토 표 행 수 그대로. 분모: A 로는 200."""
    from tests.security.test_greenwash import owner_done_run

    method, path = operation
    a, b = companies
    run_id = owner_done_run(owner, a)
    body: dict[str, Any] | None = {"marks": []} if method == "PUT" else None
    tables = ("greenwash_reviews", "greenwash_review_marks")
    before = {table: count(owner, table) for table in tables}
    other = b_session(via, b)
    for target in (run_id, run_id + 1000):
        assert status_of(other, method, API_ROOT + path.replace("{run_id}", str(target)), body) == 404
    assert {table: count(owner, table) for table in tables} == before
    login(client, tenant_id="tenant-a")
    assert status_of(client, method, API_ROOT + path.replace("{run_id}", str(run_id)), body) == 200


# ── 그린워싱 재판단 만들기(greenwash_rejudge_paths — GRJ1) ──


@pytest.mark.parametrize("operation", of_kind("greenwash_rejudge_paths"), ids=operation_id)
@pytest.mark.parametrize("via", VIA)
def test_a_greenwash_rejudge_path_hides_another_companys_run(
    client: Client, owner: Owner, companies: tuple[int, int], operation: Operation, via: str
) -> None:
    """A 의 끝난 그린워싱 실행을 B 로 재판단: 404, 없는 id 도 404, 실행·검토 표 행 수 그대로. 분모: A 로는 근거
    고침이 없어 409 NOTHING_TO_REJUDGE(실행 0)."""
    from tests.security.test_greenwash import owner_done_run

    method, path = operation
    a, b = companies
    run_id = owner_done_run(owner, a)
    path = path.replace("{item_index}", "0")
    tables = ("run_runs", "greenwash_reviews", "greenwash_review_marks")
    before = {table: count(owner, table) for table in tables}
    other = b_session(via, b)
    for target in (run_id, run_id + 1000):
        assert status_of(other, method, API_ROOT + path.replace("{run_id}", str(target))) == 404
    assert {table: count(owner, table) for table in tables} == before
    login(client, tenant_id="tenant-a")
    assert status_of(client, method, API_ROOT + path.replace("{run_id}", str(run_id))) == 409
    assert {table: count(owner, table) for table in tables} == before


# ── 영문번역 실행 경로(translation_run_paths — TR2) ──


@pytest.mark.parametrize("operation", of_kind("translation_run_paths"), ids=operation_id)
@pytest.mark.parametrize("via", VIA)
def test_a_translation_run_path_hides_another_companys_run_and_other_modules(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage, operation: Operation, via: str
) -> None:
    """A 의 끝난 영문번역 실행(주인 역할로 심음)을 B 로: 404, 없는 id 도 404. A 의 끝난 그린워싱 실행 id 는 A 로도 404.
    분모: A 로는 영문번역 실행이 200."""
    from tests.security.test_greenwash import owner_done_run
    from tests.security.test_translation import owner_done_translation

    method, path = operation
    a, b = companies
    run_id = owner_done_translation(owner, fake, a)
    green = owner_done_run(owner, a)
    other = b_session(via, b)
    for target in (run_id, run_id + 1000):
        assert status_of(other, method, API_ROOT + path.replace("{run_id}", str(target))) == 404
    login(client, tenant_id="tenant-a")
    assert status_of(client, method, API_ROOT + path.replace("{run_id}", str(green))) == 404
    assert status_of(client, method, API_ROOT + path.replace("{run_id}", str(run_id))) == 200


# ── 영문번역 layout 읽기(translation_layout_paths — TRS3) ──


@pytest.mark.parametrize("operation", of_kind("translation_layout_paths"), ids=operation_id)
@pytest.mark.parametrize("via", VIA)
def test_a_translation_layout_path_shows_only_my_pdf_run(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage, operation: Operation, via: str
) -> None:
    """A 의 끝난 PDF 영문번역 실행(주인 역할로 심음)을 B 로: 404, 없는 이웃 id 도 404. A 로도 그린워싱 실행·워드
    영문번역 실행(layout@1 없음)은 404. 분모: A 로는 PDF 실행이 200."""
    from tests.security.test_greenwash import owner_done_run
    from tests.security.test_translation import owner_done_translation, owner_pdf_translation

    assert of_kind("translation_layout_paths") == [("GET", "/translation/runs/{run_id}/layout")]
    method, path = operation
    a, b = companies
    run_id = owner_pdf_translation(owner, fake, a)
    word = owner_done_translation(owner, fake, a)
    green = owner_done_run(owner, a)
    other = b_session(via, b)
    for target in (run_id, run_id + 1000):
        assert status_of(other, method, API_ROOT + path.replace("{run_id}", str(target))) == 404
    login(client, tenant_id="tenant-a")
    for target in (green, word):
        assert status_of(client, method, API_ROOT + path.replace("{run_id}", str(target))) == 404
    assert status_of(client, method, API_ROOT + path.replace("{run_id}", str(run_id))) == 200


# ── 데이터 검증 실행 경로(dataverify_run_paths — DV1e) ──


@pytest.mark.parametrize("operation", of_kind("dataverify_run_paths"), ids=operation_id)
@pytest.mark.parametrize("via", VIA)
def test_a_dataverify_run_path_hides_another_companys_run_and_other_modules(
    client: Client, owner: Owner, companies: tuple[int, int], operation: Operation, via: str
) -> None:
    """A 의 끝난 데이터 검증 실행(주인 역할로 심음)을 B 로: 404, 없는 이웃 id 도 404. A 의 그린워싱 실행 id 는 A 로도
    404 — 끝난 것과 안 끝난 것 둘(안 끝난 것이 409 면 모듈을 안 본 것이다). 분모: A 로는 데이터 검증 실행이 200."""
    from tests.security.test_dataverify import owner_done_dataverify
    from tests.security.test_greenwash import owner_done_run

    assert of_kind("dataverify_run_paths") == [("GET", "/dataverify/runs/{run_id}/result")]
    method, path = operation
    a, b = companies
    run_id = owner_done_dataverify(owner, a)
    green = owner_done_run(owner, a)
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'greenwash', 'greenwash.probe@1', '{}', '{}', 'service', 'queued', 0, 0, 7) "
        "RETURNING id",
        [a],
    ).fetchone()
    assert row is not None
    other = b_session(via, b)
    for target in (run_id, run_id + 1000):
        assert status_of(other, method, API_ROOT + path.replace("{run_id}", str(target))) == 404
    login(client, tenant_id="tenant-a")
    for target in (green, int(row[0])):
        assert status_of(client, method, API_ROOT + path.replace("{run_id}", str(target))) == 404
    assert status_of(client, method, API_ROOT + path.replace("{run_id}", str(run_id))) == 200


# ── Scope 3 코랩 결과(scope3_run_paths — S3K1) ──

SCOPE3_REJECTED: Final[dict[str, Any]] = {
    "schemaVersion": "scope3.colab.result@1",
    "status": "rejected",
    "rejected": {"reason": "legacy_template", "detail": "가상 — 「c + 숫자」 시트 없음"},
}


def owner_done_scope3(owner: Owner, company_id: int, status: str = "done") -> int:
    """Scope 3 코랩 실행 하나와(끝났으면) 그 결과(지어낸 rejected 갈래 — 계약 꼴 그대로). 주인 역할로."""
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'inventory.scope3', 'scope3.colab@157', '{\"reportYear\": 2025}', '{}', "
        "'service', %s, 1, 0, 7) RETURNING id",
        [company_id, status],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    if status == "done":
        owner.execute(
            "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
            "VALUES (now(), %s, %s, 0, 'scope3.colab.result@1', %s::jsonb)",
            [company_id, run_id, json.dumps(SCOPE3_REJECTED, ensure_ascii=False)],
        )
    return run_id


@pytest.mark.parametrize("operation", of_kind("scope3_run_paths"), ids=operation_id)
@pytest.mark.parametrize("via", VIA)
def test_a_scope3_run_path_hides_another_companys_run_and_other_modules(
    client: Client, owner: Owner, companies: tuple[int, int], operation: Operation, via: str
) -> None:
    """A 의 끝난 Scope 3 실행(주인 역할로 심음)을 B 로: 404, 없는 이웃 id 도 404. A 의 데이터 검증 실행 id 는 A 로도
    404 — 끝난 것(결과 행 있음)과 안 끝난 것 둘(안 끝난 것이 409 면 모듈을 안 본 것이다). A 의 안 끝난 Scope 3 실행은
    409(분모 — 모듈은 보고 상태를 봤다). 분모: A 로는 Scope 3 실행이 200, 본문 = 심은 결과."""
    from tests.security.test_dataverify import owner_done_dataverify

    assert of_kind("scope3_run_paths") == [("GET", "/inventory/scope3/runs/{run_id}/result")]
    method, path = operation
    a, b = companies
    run_id = owner_done_scope3(owner, a)
    waiting = owner_done_scope3(owner, a, status="queued")
    other_done = owner_done_dataverify(owner, a)
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'dataverify', 'dataverify.colab@156', '{}', '{}', 'service', 'queued', 0, 0, "
        "7) RETURNING id",
        [a],
    ).fetchone()
    assert row is not None
    url = API_ROOT + path
    other = b_session(via, b)
    for target in (run_id, run_id + 1000):
        assert status_of(other, method, url.replace("{run_id}", str(target))) == 404
    login(client, tenant_id="tenant-a")
    for target in (other_done, int(row[0])):
        assert status_of(client, method, url.replace("{run_id}", str(target))) == 404
    assert status_of(client, method, url.replace("{run_id}", str(waiting))) == 409
    mine = client.get(url.replace("{run_id}", str(run_id)))
    assert (mine.status_code, mine.json()) == (200, SCOPE3_REJECTED)


# ── 그린워싱 2차 엔진 결과(greenwash_result2_paths — GE1b ④) ──

RESULT2_EXAMPLE: Final = (
    Path(__file__).resolve().parents[2] / "esgapi/greenwash/tests/data/contract-examples/result2/result2-normal.json"
)


def owner_g1_run(owner: Owner, company_id: int, *, flow_id: str = "greenwash.engine@G1") -> int:
    """끝난 그린워싱 실행 하나(흐름 flow_id)와 그 결과(G1 이면 계약 예시 result2-normal). 주인 역할로."""
    from tests.security.test_greenwash import EXAMPLE
    from tests.security.test_runs import owner_document

    document_id = owner_document(owner, company_id, key=flow_id.replace("@", "-"))
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, %s, 'greenwash', %s, '{}', '{}', 'service', 'done', 1, 0, 7) RETURNING id",
        [company_id, document_id, flow_id],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    g1 = flow_id == "greenwash.engine@G1"
    owner.execute(
        "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
        "VALUES (now(), %s, %s, 0, %s, %s::jsonb)",
        [
            company_id,
            run_id,
            "greenwash.result@2" if g1 else "greenwash.result@1",
            (RESULT2_EXAMPLE if g1 else EXAMPLE).read_text(encoding="utf-8"),
        ],
    )
    return run_id


@pytest.mark.parametrize("operation", of_kind("greenwash_result2_paths"), ids=operation_id)
@pytest.mark.parametrize("via", VIA)
def test_a_greenwash_result2_path_hides_another_companys_run_and_first_engine_runs(
    client: Client, owner: Owner, companies: tuple[int, int], operation: Operation, via: str
) -> None:
    """A 의 끝난 G1 실행을 B 로: 404·본문에 결과 0, 없는 이웃 id 도 404. A 로도 1차(E0) 실행 id 는 404. 세션 없이
    401. 실행·결과 표의 행 수 그대로(읽기만). 분모: A 로는 그 G1 실행 200, 본문 schemaVersion = greenwash.result@2."""
    assert of_kind("greenwash_result2_paths") == [("GET", "/greenwash/runs/{run_id}/result2")]
    method, path = operation
    a, b = companies
    run_id = owner_g1_run(owner, a)
    e0 = owner_g1_run(owner, a, flow_id="greenwash.colab@E0")
    tables = ("run_runs", "run_results")
    before = {table: count(owner, table) for table in tables}
    url = API_ROOT + path
    other = b_session(via, b)
    for target in (run_id, run_id + 1000):
        got = other.get(url.replace("{run_id}", str(target)))
        assert got.status_code == 404
        assert b"greenwash.result@2" not in got.content
    foreign, missing = (other.get(url.replace("{run_id}", str(target))).content for target in (run_id, run_id + 1000))
    assert foreign == missing  # 남의 회사 id 몸 = 없는 id 몸(있음 누설 0)
    assert Client().get(url.replace("{run_id}", str(run_id))).status_code == 401
    login(client, tenant_id="tenant-a")
    assert status_of(client, method, url.replace("{run_id}", str(e0))) == 404
    mine = client.get(url.replace("{run_id}", str(run_id)))
    assert mine.status_code == 200
    assert next(iter(mine.json())) == "schemaVersion"
    assert mine.json()["schemaVersion"] == "greenwash.result@2"
    assert {table: count(owner, table) for table in tables} == before


# ── Scope 3 올린 원본(scope3_original_paths — S3Q1) ──

ORIGINAL_BYTES: Final = b"PK\x03\x04 gaesang-scope3-original"  # 지어낸 바이트(엑셀 꼴 머리만 — 열지 않는다)


def owner_scope3_original(owner: Owner, fake: FakeStorage, company_id: int, *, document: bool = True) -> int:
    """Scope 3 실행 하나(주인 역할로 심음)와 그 실행의 올린 문서(가짜 저장소에 ORIGINAL_BYTES — ETag 같음)."""
    document_id = None
    if document:
        key = f"documents/{company_id}/s3q1-original.xlsx"
        etag = fake.put(key, ORIGINAL_BYTES)
        row = owner.execute(
            "INSERT INTO core_documents (created_at, updated_at, company_id, uploaded_by, file_name, storage_key, "
            "size_bytes, etag, status) VALUES (now(), now(), %s, '1', '가상_원본.xlsx', %s, %s, %s, 'uploaded') "
            "RETURNING id",
            [company_id, key, len(ORIGINAL_BYTES), etag],
        ).fetchone()
        assert row is not None
        document_id = int(row[0])
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, %s, 'inventory.scope3', 'scope3.colab@157', '{\"reportYear\": 2025}', '{}', "
        "'service', 'queued', 0, 0, 7) RETURNING id",
        [company_id, document_id],
    ).fetchone()
    assert row is not None
    return int(row[0])


@pytest.mark.parametrize("operation", of_kind("scope3_original_paths"), ids=operation_id)
@pytest.mark.parametrize("via", VIA)
def test_a_scope3_original_path_hides_another_companys_file_and_other_modules(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage, operation: Operation, via: str
) -> None:
    """A 의 Scope 3 실행(올린 문서 있음)을 B 로: 404·본문에 원본 바이트 0, 없는 이웃 id 도 404. A 로도 다른 모듈의 실행
    (같은 문서를 단 데이터 검증 실행)·문서 없는 Scope 3 실행은 404. 세션 없이 401. 실행·문서 표의 행 수 그대로(읽기만).
    분모: A 로는 그 실행의 원본 200, 본문 = 심은 바이트(실행 상태 queued — 상태를 보지 않는다)."""
    assert of_kind("scope3_original_paths") == [("GET", "/inventory/scope3/runs/{run_id}/original")]
    method, path = operation
    a, b = companies
    run_id = owner_scope3_original(owner, fake, a)
    bare = owner_scope3_original(owner, fake, a, document=False)
    document_id = owner.execute("SELECT document_id FROM run_runs WHERE id = %s", [run_id]).fetchone()
    assert document_id is not None
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, %s, 'dataverify', 'dataverify.colab@156', '{}', '{}', 'service', 'queued', 0, 0, "
        "7) RETURNING id",
        [a, document_id[0]],
    ).fetchone()
    assert row is not None
    before = (count(owner, "run_runs"), count(owner, "core_documents"))
    url = API_ROOT + path
    assert status_of(Client(), method, url.replace("{run_id}", str(run_id))) == 401
    other = b_session(via, b)
    for target in (run_id, run_id + 1000):
        theirs = other.get(url.replace("{run_id}", str(target)))
        assert theirs.status_code == 404
        assert ORIGINAL_BYTES not in theirs.content
    login(client, tenant_id="tenant-a")
    for target in (int(row[0]), bare):
        assert status_of(client, method, url.replace("{run_id}", str(target))) == 404
    mine = client.get(url.replace("{run_id}", str(run_id)))
    assert (mine.status_code, mine.content) == (200, ORIGINAL_BYTES)
    assert (count(owner, "run_runs"), count(owner, "core_documents")) == before


# ── 그린워싱 목록 줄(greenwash_list — G1b-1) ──


@pytest.mark.parametrize("via", VIA)
def test_the_greenwash_list_shows_only_my_company(owner: Owner, companies: tuple[int, int], via: str) -> None:
    """A 의 끝난 그린워싱 실행(주인 역할로 심음)은 B 의 목록 줄에 없다(실행·문서 0). 분모: A 로는 그 실행이 보인다."""
    from tests.security.test_greenwash import owner_done_run

    assert of_kind("greenwash_list") == [("GET", "/greenwash/checks")]
    a, b = companies
    run_id = owner_done_run(owner, a)
    theirs = b_session(via, b).get(API_ROOT + "/greenwash/checks")
    assert theirs.status_code == 200
    assert (theirs.json()["runs"], theirs.json()["documents"]) == ([], [])
    login(client := Client(), tenant_id="tenant-a")
    assert [r["runId"] for r in client.get(API_ROOT + "/greenwash/checks").json()["runs"]] == [run_id]


# ── 데이터 검증 실행 목록(dataverify_list — DV1g) ──


@pytest.mark.parametrize("via", VIA)
def test_the_dataverify_list_shows_only_my_company(owner: Owner, companies: tuple[int, int], via: str) -> None:
    """A 의 끝난 데이터 검증 실행(주인 역할로 심음)은 B 의 목록에 없다(줄 0). 분모: A 로는 그 실행이 보인다."""
    from tests.security.test_dataverify import owner_listed_dataverify

    assert of_kind("dataverify_list") == [("GET", "/dataverify/runs")]
    a, b = companies
    run_id = owner_listed_dataverify(owner, a)
    theirs = b_session(via, b).get(API_ROOT + "/dataverify/runs")
    assert theirs.status_code == 200
    assert (theirs.json()["count"], theirs.json()["results"]) == (0, [])
    login(client := Client(), tenant_id="tenant-a")
    assert [r["id"] for r in client.get(API_ROOT + "/dataverify/runs").json()["results"]] == [run_id]


# ── 중대성평가 IRO 실행 목록(materiality_list — IR3c) ──


@pytest.mark.parametrize("via", VIA)
def test_the_materiality_list_shows_only_my_company(owner: Owner, companies: tuple[int, int], via: str) -> None:
    """A 의 끝난 중대성평가 IRO 실행(주인 역할로 심음)은 B 의 목록에 없다(줄 0). 분모: A 로는 그 실행이 보인다."""
    from tests.security.test_materiality import owner_listed_materiality

    assert of_kind("materiality_list") == [("GET", "/materiality/runs")]
    a, b = companies
    run_id = owner_listed_materiality(owner, a)
    theirs = b_session(via, b).get(API_ROOT + "/materiality/runs")
    assert theirs.status_code == 200
    assert (theirs.json()["count"], theirs.json()["results"]) == (0, [])
    login(client := Client(), tenant_id="tenant-a")
    assert [r["id"] for r in client.get(API_ROOT + "/materiality/runs").json()["results"]] == [run_id]


# ── 영문번역 묶음(translation_batch_paths — TR3b) ──


@pytest.mark.parametrize("via", VIA)
def test_a_translation_batch_path_hides_another_companys_batches(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    """A 의 묶음(B 도 같은 batchId)을 B 로: 하나 보기 404(없는 묶음과 같음), 목록에 A 의 것 0. A 로도 다른 모듈 실행·
    batchId 있는 실행의 run-<id>·없는 묶음은 404. 분모: B 는 제 묶음, A 는 제 묶음이 200."""
    from tests.security.test_translation import BATCH, owner_batch_run, owner_text_document

    assert of_kind("translation_batch_paths") == [
        ("GET", "/translation/batches"),
        ("GET", "/translation/documents/{document_id}/batches/{batch_key}"),
        ("GET", "/translation/documents/{document_id}/batches/{batch_key}/archive"),
        ("GET", "/translation/documents/{document_id}/pages"),
    ]
    a, b = companies
    doc_a = owner_text_document(owner, fake, a, "paths-a")
    doc_b = owner_text_document(owner, fake, b, "paths-b")
    batched = owner_batch_run(owner, a, doc_a, BATCH)
    green = owner_batch_run(owner, a, doc_a, None, module="greenwash")
    owner_batch_run(owner, b, doc_b, BATCH)

    def one(document_id: int, key: str) -> str:
        return f"{API_ROOT}/translation/documents/{document_id}/batches/{key}"

    other = b_session(via, b)
    assert status_of(other, "GET", one(doc_a, BATCH)) == 404
    assert status_of(other, "GET", one(doc_a, BATCH) + "/archive") == 404
    assert status_of(other, "GET", one(doc_b, BATCH)) == 200  # 분모: 제 것
    assert {r["document"]["id"] for r in other.get(API_ROOT + "/translation/batches").json()["results"]} == {doc_b}
    pages = API_ROOT + "/translation/documents/{}/pages"  # TRP6: 문서 쪽 수 — B 로 A 문서·없는 문서 404, 제 문서 200
    assert status_of(other, "GET", pages.format(doc_a)) == 404
    assert status_of(other, "GET", pages.format(doc_b)) == 200  # 분모: 제 것
    assert status_of(other, "GET", pages.format(max(doc_a, doc_b) + 1_000)) == 404
    login(client := Client(), tenant_id="tenant-a")
    for key in (f"run-{batched}", f"run-{green}", "00000000-0000-4000-8000-00000000ffff"):
        assert status_of(client, "GET", one(doc_a, key)) == 404, key
    assert status_of(client, "GET", one(doc_a, BATCH)) == 200  # 분모
    assert {r["document"]["id"] for r in client.get(API_ROOT + "/translation/batches").json()["results"]} == {doc_a}


# ── 중대성평가 IRO 실행 경로(materiality_run_paths — IR3b) ──


@pytest.mark.parametrize("operation", of_kind("materiality_run_paths"), ids=operation_id)
@pytest.mark.parametrize("via", VIA)
def test_a_materiality_run_path_hides_another_companys_run_and_other_modules(
    client: Client, owner: Owner, companies: tuple[int, int], operation: Operation, via: str
) -> None:
    """A 의 끝난 중대성평가 실행(주인 역할로 심음)을 B 로: 404, 없는 이웃 id 도 404. A 의 다른 모듈 실행 id 는 A 로도
    404 — 끝난 것과 안 끝난 것 둘(안 끝난 것이 409 면 모듈을 안 본 것이다). 분모: A 로는 중대성평가 실행이 200."""
    from tests.security.test_dataverify import owner_done_dataverify
    from tests.security.test_materiality import owner_done_materiality

    assert of_kind("materiality_run_paths") == [
        ("GET", "/materiality/runs/{run_id}/report"),
        ("GET", "/materiality/runs/{run_id}/result"),
        ("GET", "/materiality/runs/{run_id}/result/edits"),
        ("POST", "/materiality/runs/{run_id}/result/edits"),
    ]
    method, path = operation
    a, b = companies
    run_id = owner_done_materiality(owner, a)
    done_other = owner_done_dataverify(owner, a)
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'dataverify', 'dataverify.colab@156', '{}', '{}', 'service', 'queued', "
        "0, 0, 7) "
        "RETURNING id",
        [a],
    ).fetchone()
    assert row is not None
    body = EDIT_BODY if method == "POST" else None  # 저장은 유효한 본문(IRS3 — 6d: 양성 대조가 2xx)
    other = b_session(via, b)
    for target in (run_id, run_id + 1000):
        assert status_of(other, method, API_ROOT + path.replace("{run_id}", str(target)), body) == 404
    assert count(owner, "materiality_result_edit_heads") == count(owner, "materiality_result_edits") == 0
    login(client, tenant_id="tenant-a")
    for target in (done_other, int(row[0])):
        assert status_of(client, method, API_ROOT + path.replace("{run_id}", str(target)), body) == 404
    assert status_of(client, method, API_ROOT + path.replace("{run_id}", str(run_id)), body) == 200
