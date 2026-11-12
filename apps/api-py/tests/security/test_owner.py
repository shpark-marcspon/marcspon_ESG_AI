"""주인 역할로 재는 것: 어느 표에도 행 보안(RLS)과 정책이 없고, 앱 역할의 GRANT 가 그대로다. 보안 층.

격리는 DB 의 정책이 아니라 조회의 조건(①)과 기본 매니저(②)와 같은 회사 외래 키(⑤)가 한다(core/isolation).
정책이 다시 생기면 첫 테스트가 빨개진다(그러면 이 층의 다른 테스트가 재는 것이 조건·매니저가 아니라 정책의 답이
된다).
"""

from typing import Any

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction

from tests.security.conftest import tenant_tables

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
# 표의 목록은 여기 적지 않는다. company 와 company_id 칸이 있는 표 전부를 카탈로그에서 읽는다(tenant_tables).
# 모듈이 테넌트의 표를 더하면 아래 검사가 그 표에도 저절로 걸린다. 이 열하나는 「적어도 있어야 하는」 표다
# (목록이 비어 아무것도 재지 않은 채 통과하는 일을 막는다). AU1a +1: core_audit_events. X1b-1 +4: 실행 넷.
KNOWN = {
    "company",
    "sites",
    "users",
    "core_documents",
    "run_jobs",
    "core_llm_call_logs",
    "core_audit_events",
    "run_runs",
    "run_steps",
    "run_results",
    "run_files",
    "run_segments",  # RM1a 구획 기록
    "greenwash_reviews",  # G1b 검토 둘
    "greenwash_review_marks",
    "greenwash_ai_settings",  # G2c2 AI 설정 판
    "translation_ai_settings",  # TR4 AI 설정 판
    "dataverify_ai_settings",  # DVA1 AI 설정 판
    "materiality_ai_settings",  # IR4 AI 설정 판
    "materiality_result_edit_heads",  # IRS3 결과 고침 둘
    "materiality_result_edits",
    "inventory_scope3_row_edits",  # S3K2b-1 Scope 3 줄 편집 사건
    "drafting_ai_settings",  # RPA1 AI 설정 판
    "site_facilities",  # K1b-1 사업장별 자산/시설
    "inventory_years",  # K1b-2b 인벤토리 해·고객사 인덱스 선택
    "inventory_index_selections",
    "inventory_entry_rows",  # S12a Scope 1·2 입력 셋
    "inventory_entry_values",
    "inventory_entry_history",
    "inventory_entry_periods",  # S12a-2 입력주기·직접입력 계수
    "inventory_custom_factors",
    "drafting_projects",  # RP1 원고작성 표 넷
    "drafting_project_documents",
    "drafting_outlines",
    "drafting_outline_nodes",
    "core_document_artifacts",  # RP2a ① 문서 산출물 둘
    "core_document_artifact_uses",
}
# 회사 범위 표의 앱 역할 권한(organization·user·core 의 0001). company 는 읽기만(만드는 것은 주인 역할의 seed_company).
# 호출 기록은 덧붙이기만(UPDATE 없음). 문서·일감은 읽기·만들기·고치기(지우기·보존은 아직 정하지 않았다).
PRIVILEGES = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
GRANTED = {
    "company": {"SELECT"},
    "sites": {"SELECT", "INSERT", "UPDATE"},
    "users": {"SELECT", "INSERT", "UPDATE"},
    "core_documents": {"SELECT", "INSERT", "UPDATE"},
    "run_jobs": {"SELECT", "INSERT", "UPDATE"},
    "core_llm_call_logs": {"SELECT", "INSERT"},
    "core_audit_events": {"SELECT", "INSERT"},  # AU1a: 감사 기록도 덧붙이기만
    # X1b-1: 실행·단계는 상태가 바뀐다(UPDATE). 결과·파일은 한 번 쓰고 끝(MARC-ENT-210 (1)).
    # 넷 다 지우지 않는다(MARC-ENT-208).
    "run_runs": {"SELECT", "INSERT", "UPDATE"},
    "run_steps": {"SELECT", "INSERT", "UPDATE"},
    "run_results": {"SELECT", "INSERT"},
    "run_files": {"SELECT", "INSERT"},
    # RM1a: 구획 기록은 상태가 바뀐다(UPDATE). 지우지 않는다(실행 표와 같다 — MARC-ENT-208).
    "run_segments": {"SELECT", "INSERT", "UPDATE"},
    # G1b: 검토·표시는 고친다(표시 지우기 = NULL 로 UPDATE). 지우지 않는다(DELETE 없음 — 발주서 개정 1 B2).
    "greenwash_reviews": {"SELECT", "INSERT", "UPDATE"},
    "greenwash_review_marks": {"SELECT", "INSERT", "UPDATE"},
    # G2c2: 판은 불변 행(저장 = 새 행). 표 단위 UPDATE 없음 — 칸 단위 UPDATE (applied, applied_at) 만(아래 칸 시험).
    "greenwash_ai_settings": {"SELECT", "INSERT"},
    # TR4: 영문번역 판도 불변 행(그린워싱과 같음)
    "translation_ai_settings": {"SELECT", "INSERT"},
    # DVA1: 데이터 검증 판도 불변 행(영문번역과 같음)
    "dataverify_ai_settings": {"SELECT", "INSERT"},
    # IR4: 중대성평가 IRO 판도 불변 행(데이터 검증과 같음)
    "materiality_ai_settings": {"SELECT", "INSERT"},
    # IRS3: 결과 고침의 머리는 칸 단위 UPDATE (revision, updated_at) 만(아래 칸 시험), 고침은 불변 행(저장 = 새 행)
    "materiality_result_edit_heads": {"SELECT", "INSERT"},
    "materiality_result_edits": {"SELECT", "INSERT"},
    # S3K2b-1: Scope 3 줄 편집 사건도 불변 행(복구 = 새 사건) — 칸 단위 UPDATE 0
    "inventory_scope3_row_edits": {"SELECT", "INSERT"},
    # RPA1: 원고작성 판도 불변 행(중대성평가 IRO 와 같음)
    "drafting_ai_settings": {"SELECT", "INSERT"},
    # K1b-1: 사업장별 자산/시설은 고친다(지우기 = 삭제 표시 UPDATE). DELETE 없음.
    "site_facilities": {"SELECT", "INSERT", "UPDATE"},
    # K1b-2b: 해·선택은 고친다(뺀 선택 = 삭제 표시·숨김 UPDATE). DELETE 없음.
    "inventory_years": {"SELECT", "INSERT", "UPDATE"},
    "inventory_index_selections": {"SELECT", "INSERT", "UPDATE"},
    # S12a: 입력 행·값은 고친다(지우기 = 삭제 표시 UPDATE). 히스토리는 덧붙이기만(UPDATE·DELETE 없음).
    "inventory_entry_rows": {"SELECT", "INSERT", "UPDATE"},
    "inventory_entry_values": {"SELECT", "INSERT", "UPDATE"},
    "inventory_entry_history": {"SELECT", "INSERT"},
    "inventory_entry_periods": {"SELECT", "INSERT", "UPDATE"},  # S12a-2: 주기는 고치고 지우지 않는다
    "inventory_custom_factors": {"SELECT", "INSERT"},  # S12a-2: 직접입력은 고치지 않는다(판 표 꼴)
    # RP1: 원고작성 표 넷은 불변 행(문서 달기·목차 바꿈 = 새 행). 프로젝트만 칸 단위 UPDATE(아래 칸 시험)
    "drafting_projects": {"SELECT", "INSERT"},
    "drafting_project_documents": {"SELECT", "INSERT"},
    "drafting_outlines": {"SELECT", "INSERT"},
    "drafting_outline_nodes": {"SELECT", "INSERT"},
    # RP2a ①: 문서 산출물 둘은 불변 행 — SELECT·INSERT 만(UPDATE·DELETE 0, e7 ⑫)
    "core_document_artifacts": {"SELECT", "INSERT"},
    "core_document_artifact_uses": {"SELECT", "INSERT"},
}
# 칸 단위 UPDATE 를 받은 표(G2c2): 표 → 앱 역할이 고칠 수 있는 칸 전부.
COLUMN_UPDATES = {"greenwash_ai_settings": {"applied", "applied_at"}}
COLUMN_UPDATES["translation_ai_settings"] = {"applied", "applied_at"}  # TR4
COLUMN_UPDATES["dataverify_ai_settings"] = {"applied", "applied_at"}  # DVA1
COLUMN_UPDATES["materiality_ai_settings"] = {"applied", "applied_at"}  # IR4
COLUMN_UPDATES["drafting_ai_settings"] = {"applied", "applied_at"}  # RPA1
# 앱이 읽지 않아 권한이 하나도 없는 표: AbstractUser 의 M2M 둘, auth_* 전부, django_content_type.
NO_PRIVILEGE_SQL = """
    SELECT relname FROM pg_class
    WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'
      AND (relname IN ('users_groups', 'users_user_permissions', 'django_content_type') OR relname LIKE 'auth\\_%')
    ORDER BY relname
"""


def test_no_table_has_row_security_or_a_policy(owner: Owner) -> None:
    tables = tenant_tables(owner)
    assert set(tables) >= KNOWN  # 분모: 테넌트의 표가 적어도 이만큼 있다
    flags = owner.execute(
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE relnamespace = 'public'::regnamespace AND relkind IN ('r', 'p') ORDER BY relname"
    ).fetchall()
    assert set(tables) <= {name for name, _, _ in flags}  # 아래 검사가 테넌트의 표를 전부 훑었다
    assert [name for name, enabled, forced in flags if enabled or forced] == []
    assert owner.execute("SELECT count(*) FROM pg_policies").fetchone() == (0,)


def test_app_role_reads_every_tenant_table_and_deletes_none(owner: Owner) -> None:
    """GRANT: 앱 역할은 테넌트의 표를 전부 읽을 수 있고(빠지면 그 모듈이 일을 못 한다), 지우거나 비우지 못한다."""
    tables = tenant_tables(owner)
    assert set(tables) >= KNOWN
    rows = owner.execute(
        "SELECT t, has_table_privilege('esg_app', t, 'SELECT'), has_table_privilege('esg_app', t, 'DELETE'), "
        "has_table_privilege('esg_app', t, 'TRUNCATE') FROM unnest(%s::text[]) AS t ORDER BY t COLLATE \"C\"",
        [tables],
    ).fetchall()
    assert rows == [(table, True, False, False) for table in tables]

    # 회사 범위 표 열하나는 권한이 정확히 이만큼이다(X1b-1 +4).
    granted = owner.execute(
        "SELECT t, p FROM unnest(%s::text[]) AS t, unnest(%s::text[]) AS p "
        "WHERE has_table_privilege('esg_app', t, p) ORDER BY t, p",
        [sorted(GRANTED), PRIVILEGES],
    ).fetchall()
    assert {(table, privilege) for table, privilege in granted} == {
        (table, privilege) for table, privileges in GRANTED.items() for privilege in privileges
    }
    # 권한이 하나도 없는 표. 분모: 그 표들이 실제로 있다(M2M 둘, django_content_type, auth_* 셋 이상).
    bare = [name for (name,) in owner.execute(NO_PRIVILEGE_SQL)]
    assert {"users_groups", "users_user_permissions", "django_content_type", "auth_group", "auth_permission"} <= set(
        bare
    )
    leaked = owner.execute(
        "SELECT t, p FROM unnest(%s::text[]) AS t, unnest(%s::text[]) AS p WHERE has_table_privilege('esg_app', t, p)",
        [bare, PRIVILEGES],
    ).fetchall()
    assert leaked == []
    # 어느 표에도 DELETE·TRUNCATE 가 없다(public 의 일반 표 전부). 분모: 훑은 표에 테넌트의 표가 다 있다.
    every = owner.execute(
        "SELECT relname, has_table_privilege('esg_app', oid, 'DELETE') "
        "OR has_table_privilege('esg_app', oid, 'TRUNCATE') "
        "FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' ORDER BY relname"
    ).fetchall()
    assert set(tables) <= {name for name, _ in every}
    assert [name for name, removable in every if removable] == []
    # 스키마 public 의 USAGE(organization/0001 이 준다).
    assert owner.execute("SELECT has_schema_privilege('esg_app', 'public', 'USAGE')").fetchone() == (True,)


def test_app_role_reads_inserts_and_updates_refresh_tokens_and_deletes_none(owner: Owner) -> None:
    """GRANT: refresh 토큰의 표(user/0002 — 회사 칸이 없어 tenant_tables 밖이다)는 SELECT·INSERT·UPDATE 만.
    지난 행 지우기는 2차라 DELETE·TRUNCATE 가 없다(rotate·끊기는 UPDATE 다)."""
    # 분모: 그 표가 실제로 있다
    assert owner.execute("SELECT to_regclass('public.user_refresh_tokens') IS NOT NULL").fetchone() == (True,)
    granted = owner.execute(
        "SELECT p FROM unnest(%s::text[]) AS p "
        "WHERE has_table_privilege('esg_app', 'user_refresh_tokens', p) ORDER BY p",
        [PRIVILEGES],
    ).fetchall()
    assert [privilege for (privilege,) in granted] == ["INSERT", "SELECT", "UPDATE"]


def test_app_role_updates_only_the_granted_columns(owner: Owner) -> None:
    """GRANT(G2c2): AI 설정 판 표는 칸 단위 UPDATE 가 applied·applied_at 둘뿐이다(기준표·이름·메모·sha 는 못 고친다).
    분모: 그 표의 칸이 실제로 열 개 이상이고, 칸 권한을 받지 않은 표(검토 표)는 칸마다가 아니라 표 단위로 받았다."""
    for table, columns in COLUMN_UPDATES.items():
        rows = owner.execute(
            "SELECT attname, has_column_privilege('esg_app', %s, attname, 'UPDATE') FROM pg_attribute "
            "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped ORDER BY attnum",
            [table, table],
        ).fetchall()
        assert len(rows) >= 10, table
        assert {name for name, updatable in rows if updatable} == columns, table
        assert owner.execute("SELECT has_table_privilege('esg_app', %s, 'UPDATE')", [table]).fetchone() == (False,)
    assert owner.execute("SELECT has_table_privilege('esg_app', 'greenwash_reviews', 'UPDATE')").fetchone() == (True,)


def test_app_role_updates_no_column_of_the_scope3_row_edits(owner: Owner) -> None:
    """GRANT(S3K2b-2): 줄 편집 사건 표는 0007 로 칸이 늘어도 불변 행이다 — 표 단위 UPDATE 도, 칸 단위 UPDATE 도 0."""
    table = "inventory_scope3_row_edits"
    rows = owner.execute(
        "SELECT attname, has_column_privilege('esg_app', %s, attname, 'UPDATE') FROM pg_attribute "
        "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped ORDER BY attnum",
        [table, table],
    ).fetchall()
    assert len(rows) == 11 + 12  # 분모: S3K2b-2 +12 — 칸이 늘면 빨강(권한을 다시 본다)
    assert {name for name, updatable in rows if updatable} == set()
    assert owner.execute("SELECT has_table_privilege('esg_app', %s, 'UPDATE')", [table]).fetchone() == (False,)
    assert owner.execute("SELECT has_table_privilege('esg_app', %s, 'DELETE')", [table]).fetchone() == (False,)


def test_app_role_updates_only_the_outline_revision_of_a_drafting_project(owner: Owner) -> None:
    """GRANT(RP1, 감독 처분 10-29): 원고작성 프로젝트 표는 칸 단위 UPDATE 가 outline_revision·updated_at 둘뿐이다
    (목차 판 번호 매김의 행 잠금 — 연도·이름·회사는 못 고친다). 칸이 여덟이라 위 시험의 분모(열 이상)와 따로 잰다."""
    rows = owner.execute(
        "SELECT attname, has_column_privilege('esg_app', 'drafting_projects', attname, 'UPDATE') FROM pg_attribute "
        "WHERE attrelid = 'drafting_projects'::regclass AND attnum > 0 AND NOT attisdropped ORDER BY attnum"
    ).fetchall()
    assert len(rows) == 8  # 분모: id·때 둘·회사·연도·이름·만든 사람·판 번호
    assert {name for name, updatable in rows if updatable} == {"outline_revision", "updated_at"}
    assert owner.execute("SELECT has_table_privilege('esg_app', 'drafting_projects', 'UPDATE')").fetchone() == (False,)


def test_app_role_updates_only_the_revision_of_a_materiality_edit_head(
    owner: Owner, companies: tuple[int, int]
) -> None:
    """GRANT(IRS3 — 7a 허락 11-03, 6d 조건): 중대성평가 결과 고침 머리 표는 칸 단위 UPDATE 가
    revision·updated_at 둘뿐이다(낙관 잠금의 조건부 UPDATE — 회사·실행·만든 때는 못 고친다). 고침 표는
    UPDATE·DELETE 0(불변 행). 칸이 여섯이라 위 시험의 분모(열 이상)와 따로 잰다(원고작성 프로젝트 꼴).
    분모 = information_schema 의 칸 수, 양성 대조 = 앱 역할의 revision·updated_at UPDATE 가 실제로 되고 그 밖
    칸은 42501."""
    heads, edits = "materiality_result_edit_heads", "materiality_result_edits"
    columns = owner.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
        [heads],
    ).fetchall()
    assert len(columns) == 6  # 분모: id·때 둘·회사·실행·revision — 칸이 늘면 빨강(권한을 다시 본다)
    rows = owner.execute(
        "SELECT attname, has_column_privilege('esg_app', %s, attname, 'UPDATE') FROM pg_attribute "
        "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped ORDER BY attnum",
        [heads, heads],
    ).fetchall()
    assert {name for name, updatable in rows if updatable} == {"revision", "updated_at"}
    for table in (heads, edits):
        assert owner.execute("SELECT has_table_privilege('esg_app', %s, 'UPDATE')", [table]).fetchone() == (False,)

    a, _ = companies
    owner.execute(
        f"INSERT INTO {heads} (created_at, updated_at, company_id, run_id, revision) "
        "VALUES (now(), now(), %s, 9001, 0)",
        [a],
    )
    owner.execute(
        f"INSERT INTO {edits} (created_at, updated_at, company_id, run_id, revision, pointer, value, "
        "edited_by_user_id) VALUES (now(), now(), %s, 9001, 1, %s, '가상', 1)",
        [a, "/part2/topics/0/subtopics/0/impact/rows/0/impactDefinition"],
    )

    def denied(statement: str) -> str | None:  # 앱 역할(Django 연결)로 돌린 문의 SQLSTATE(되면 None)
        try:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(statement)
        except DatabaseError as error:
            return getattr(error.__cause__, "sqlstate", None)
        return None

    where = f"WHERE company_id = {a} AND run_id = 9001"
    assert denied(f"UPDATE {heads} SET revision = revision + 1, updated_at = now() {where} AND revision = 0") is None
    for assignment in ("run_id = 9002", "company_id = company_id", "created_at = now()", "id = id"):
        assert denied(f"UPDATE {heads} SET {assignment} {where}") == "42501", assignment
    assert denied(f"DELETE FROM {heads} {where}") == "42501"
    assert denied(f"UPDATE {edits} SET value = '고침' {where}") == "42501"
    assert denied(f"DELETE FROM {edits} {where}") == "42501"
    ran = "SELECT revision FROM materiality_result_edit_heads WHERE company_id = %s AND run_id = 9001"
    assert owner.execute(ran, [a]).fetchall() == [(1,)]  # 양성 대조가 실제로 썼다
    kept = "SELECT value FROM materiality_result_edits WHERE company_id = %s AND run_id = 9001"
    assert owner.execute(kept, [a]).fetchall() == [("가상",)]


def test_app_role_reads_inserts_and_updates_the_shared_facility_codes_and_deletes_none(owner: Owner) -> None:
    """GRANT(K1b-1): 자산/시설 코드 목록(organization_facility_codes — 모든 고객사 공통, 회사 칸이 없어 tenant_tables
    밖이다)은 SELECT·INSERT·UPDATE 만. 지우기는 삭제 표시라 DELETE·TRUNCATE 가 없다(쓰기 권한은 운영 관리자 경로만 —
    core/permissions.py)."""
    # 분모: 그 표가 실제로 있고 회사 칸이 없다
    assert owner.execute("SELECT to_regclass('public.organization_facility_codes') IS NOT NULL").fetchone() == (True,)
    assert "organization_facility_codes" not in tenant_tables(owner)
    granted = owner.execute(
        "SELECT p FROM unnest(%s::text[]) AS p "
        "WHERE has_table_privilege('esg_app', 'organization_facility_codes', p) ORDER BY p",
        [PRIVILEGES],
    ).fetchall()
    assert [privilege for (privilege,) in granted] == ["INSERT", "SELECT", "UPDATE"]


def test_app_role_inserts_the_ghg_pool_and_never_rewrites_a_factor_version(owner: Owner) -> None:
    """GRANT(K1b-2a): 온실가스 인덱스 풀·계수 풀(표 넷 — 모든 고객사 공통, 회사 칸이 없어 tenant_tables 밖이다).
    노드·계수는 SELECT·INSERT·UPDATE(지우기는 삭제 표시). 판·가스는 SELECT·INSERT 만 — 넣고 나면 고치지 않는다
    (고치기는 새 판, 회사 선택이 판을 잡는다). 실제 거절(42501)은 tests/security/test_ghg_pool.py 가 앱 역할로 잰다."""
    expected = {
        "ghg_index_nodes": ["INSERT", "SELECT", "UPDATE"],
        "ghg_factors": ["INSERT", "SELECT", "UPDATE"],
        "ghg_factor_versions": ["INSERT", "SELECT"],
        "ghg_factor_gases": ["INSERT", "SELECT"],
    }
    tenant = tenant_tables(owner)
    for table, privileges in expected.items():
        # 분모: 그 표가 실제로 있고 회사 칸이 없다
        assert owner.execute("SELECT to_regclass(%s) IS NOT NULL", [f"public.{table}"]).fetchone() == (True,), table
        assert table not in tenant, table
        granted = owner.execute(
            "SELECT p FROM unnest(%s::text[]) AS p WHERE has_table_privilege('esg_app', %s, p) ORDER BY p",
            [PRIVILEGES, table],
        ).fetchall()
        assert [privilege for (privilege,) in granted] == privileges, table
    for table in ("ghg_factor_versions", "ghg_factor_gases"):
        for privilege in ("UPDATE", "DELETE"):
            assert owner.execute("SELECT has_table_privilege('esg_app', %s, %s)", [table, privilege]).fetchone() == (
                False,
            ), (table, privilege)
