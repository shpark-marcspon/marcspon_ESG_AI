"""빈 DB 에서 migrate 가 돌고, core·회사·사용자의 마이그레이션이 되돌렸다 다시 올려도 스키마가 같은가. 보안 층에 둔
까닭: 주인 역할로 DB 를 따로 만들어야 한다. (노드 이름의 「company_user」 는 옛 그대로다 — K1u-b 가 core 를 더했다.)

스키마는 카탈로그로 뜬다(칸·제약·인덱스·앱 역할의 표 권한·스키마 USAGE 를 정렬한 목록). pg_dump 를 쓰지 않는 까닭:
이 층은 호스트에서 돌고(scripts/test-security.sh 의 uv run) 호스트에 pg_dump 가 있다는 전제가 없다
(api-py 이미지에도 없다).
무효 조건: 카탈로그 목록이 보지 않는 것(함수·트리거·시퀀스의 현재 값·주석)의 차이는 못 잡는다.
옛 PY1 의 라벨 잇기(infra → accounts)는 accounts 가 없어지며 재는 대상이 사라졌다(K1u-a).
"""

import os
import subprocess
import sys
from collections.abc import Iterator
from typing import Any, LiteralString

import psycopg
import pytest
from psycopg import sql

from tests.security.conftest import API_PY_DIR

CORE_MIGRATIONS = API_PY_DIR / "esgapi" / "core" / "migrations"

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
PRIVILEGES = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]

# 스키마의 카탈로그 목록. 이름(제약·인덱스는 Django 가 짓는 결정적인 이름)과 정의 글자로 견준다. oid 는 넣지 않는다.
COLUMNS_SQL = """
    SELECT table_name, column_name, ordinal_position, data_type, character_maximum_length, is_nullable,
           coalesce(column_default, ''), is_identity, coalesce(identity_generation, '')
    FROM information_schema.columns WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position
"""
CONSTRAINTS_SQL = """
    SELECT con.conrelid::regclass::text, con.conname, con.contype::text, pg_get_constraintdef(con.oid)
    FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid
    WHERE c.relnamespace = 'public'::regnamespace
    ORDER BY 1, 2
"""
INDEXES_SQL = "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1, 2"
GRANTS_SQL = """
    SELECT c.relname, p, has_table_privilege('esg_app', c.oid, p)
    FROM pg_class c, unnest(%s::text[]) AS p
    WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
    ORDER BY 1, 2
"""


@pytest.fixture
def scratch_db() -> Iterator[str]:
    """이 테스트만의 빈 DB. 돌려주는 것은 그 DB 의 주인 주소."""
    owner_url = os.environ["TEST_DATABASE_URL_PY_OWNER"]
    name = owner_url.rsplit("/", 1)[1] + "_scratch"
    drop = sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
    with psycopg.connect(owner_url, autocommit=True) as admin:
        admin.execute(drop)
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    yield owner_url + "_scratch"
    with psycopg.connect(owner_url, autocommit=True) as admin:
        admin.execute(drop)


def migrate(owner_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    """migrate-py 컨테이너가 하는 것과 같은 명령, 같은 설정. args 는 `user zero` 꼴(앱과 대상)."""
    return subprocess.run(
        [sys.executable, "manage.py", "migrate", *args, "--no-input"],
        cwd=API_PY_DIR,
        env={
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "esgapi.config.settings.migrate",
            "DATABASE_URL_PY_OWNER": owner_url,
        },
        capture_output=True,
        text=True,
    )


def schema(owner_url: str) -> dict[str, list[tuple[Any, ...]]]:
    """스키마의 카탈로그 목록(pg_dump --schema-only 의 자리)."""
    with psycopg.connect(owner_url, autocommit=True) as conn:
        return {
            "columns": conn.execute(COLUMNS_SQL).fetchall(),
            "constraints": conn.execute(CONSTRAINTS_SQL).fetchall(),
            "indexes": conn.execute(INDEXES_SQL).fetchall(),
            "grants": conn.execute(GRANTS_SQL, [PRIVILEGES]).fetchall(),
            "usage": conn.execute("SELECT has_schema_privilege('esg_app', 'public', 'USAGE')").fetchall(),
        }


def facts(owner_url: str, sql_text: LiteralString) -> list[tuple[Any, ...]]:
    """주인 연결로 묻는 한 문의 답."""
    with psycopg.connect(owner_url, autocommit=True) as conn:
        return conn.execute(sql_text).fetchall()


def test_migrate_runs_on_an_empty_db_and_the_company_user_migrations_round_trip(scratch_db: str) -> None:
    # 1. 빈 DB: 처음부터 돈다.
    first = migrate(scratch_db)
    assert first.returncode == 0, first.stderr
    d1 = schema(scratch_db)

    # 2. 기대한 제약이 이름으로 있다(카탈로그). 조건부 UNIQUE 는 제약이 아니라 인덱스다(pg_indexes, WHERE 까지).
    constraints = {(table, name, kind) for table, name, kind, _ in d1["constraints"]}
    assert {
        ("company", "company_subdomain_format", "c"),
        ("users", "users_kind_company_check", "c"),
        ("users", "users_level_values_check", "c"),
    } <= constraints  # 포함: PostgreSQL 이 칸 CHECK(양의 정수 칸의 >= 0)에 지은 이름(users_level_check 등)도 같이 있다
    company_unique = sorted(
        definition for table, _, kind, definition in d1["constraints"] if (table, kind) == ("company", "u")
    )
    assert company_unique == ["UNIQUE (business_licence_number)", "UNIQUE (subdomain)"]
    indexes = {name: definition for _, name, definition in d1["indexes"]}
    admin_unique = indexes["users_admin_username_uniq"]
    company_username_unique = indexes["users_company_username_uniq"]
    assert admin_unique.startswith("CREATE UNIQUE INDEX users_admin_username_uniq ON public.users")
    assert "(username) WHERE" in admin_unique and "'admin'" in admin_unique
    assert company_username_unique.startswith("CREATE UNIQUE INDEX users_company_username_uniq ON public.users")
    assert "(company_id, username) WHERE" in company_username_unique and "'service'" in company_username_unique
    # 옛 이름은 없다: tenants 표, (발급자, 외부 ID) 유니크.
    assert {table for table, *_ in d1["columns"]} >= {"company", "sites", "users"}
    assert "tenants" not in {table for table, *_ in d1["columns"]}
    assert "users_issuer_external_id_uniq" not in {name for _, name, _ in constraints} | set(indexes)
    # refresh 토큰의 표(user/0002): 앱 역할은 SELECT·INSERT·UPDATE 만(DELETE·TRUNCATE 없음 — 지난 행 지우기는 2차).
    refresh_grants = {privilege for table, privilege, held in d1["grants"] if table == "user_refresh_tokens" and held}
    assert {table for table, _, _ in d1["grants"]} >= {"user_refresh_tokens"}  # 분모: 그 표를 훑었다
    assert refresh_grants == {"SELECT", "INSERT", "UPDATE"}

    # 2b. core 의 세 표(K1u-b): 숫자 id·회사 칸. 같은 회사 외래 키 짝과 그것이 가리킬 UNIQUE.
    definitions = {(table, name): definition for table, name, _, definition in d1["constraints"]}
    assert definitions[("core_documents", "core_documents_company_id_uniq")] == "UNIQUE (company_id, id)"
    assert definitions[("run_jobs", "run_jobs_document_id_same_company_fk")] == (
        "FOREIGN KEY (company_id, document_id) REFERENCES core_documents(company_id, id)"
    )
    pair_deferrable = facts(
        scratch_db, "SELECT condeferrable FROM pg_constraint WHERE conname = 'run_jobs_document_id_same_company_fk'"
    )
    assert pair_deferrable == [(False,)]  # NOT DEFERRABLE: 그 문에서 23503
    # X1b-1: 실행 넷의 같은 회사 외래 키 짝 넷과 그것이 가리킬 UNIQUE, 문서의 앞 판(자기 참조) 짝 하나.
    assert definitions[("run_runs", "run_runs_company_id_uniq")] == "UNIQUE (company_id, id)"
    assert definitions[("run_runs", "run_runs_document_id_same_company_fk")] == (
        "FOREIGN KEY (company_id, document_id) REFERENCES core_documents(company_id, id)"
    )
    for child in ("run_steps", "run_results", "run_files", "run_segments"):  # RM1a +1: 구획 기록
        assert definitions[(child, f"{child}_run_id_same_company_fk")] == (
            "FOREIGN KEY (company_id, run_id) REFERENCES run_runs(company_id, id)"
        ), child
    assert definitions[("core_documents", "core_documents_previous_document_id_same_company_fk")] == (
        "FOREIGN KEY (company_id, previous_document_id) REFERENCES core_documents(company_id, id)"
    )
    # K1b-1: 사업장의 짝이 가리킬 UNIQUE · 자산/시설 → 사업장 짝 · 본사 CHECK 둘 · 조건부 UNIQUE 넷(인덱스).
    assert definitions[("sites", "sites_company_id_uniq")] == "UNIQUE (company_id, id)"
    assert definitions[("site_facilities", "site_facilities_company_id_uniq")] == "UNIQUE (company_id, id)"  # L2
    assert definitions[("site_facilities", "site_facilities_site_id_same_company_fk")] == (
        "FOREIGN KEY (company_id, site_id) REFERENCES sites(company_id, id)"
    )
    assert {
        ("sites", "sites_headquarters_alive", "c"),
        ("sites", "sites_headquarters_inventory_on", "c"),
    } <= constraints
    for name, where in (
        ("sites_one_headquarters_per_company", "(company_id) WHERE is_headquarters"),
        ("sites_name_unique_alive", "(company_id, name) WHERE (deleted_at IS NULL)"),
        ("facility_codes_name_unique_alive", "(name) WHERE (deleted_at IS NULL)"),
        ("site_facilities_unique_alive", "(site_id, facility_code_id, detail_name) WHERE (deleted_at IS NULL)"),
    ):
        assert indexes[name].startswith(f"CREATE UNIQUE INDEX {name} ON public."), name
        assert indexes[name].endswith(where), (name, indexes[name])
    # K1b-2a: 온실가스 풀(공통 — 회사 칸 없음, 같은 회사 짝 없음). CHECK 열하나 · 조건부 UNIQUE 여섯(인덱스).
    assert {
        ("ghg_index_nodes", "ghg_nodes_level_check", "c"),
        ("ghg_index_nodes", "ghg_nodes_root_is_scope", "c"),
        ("ghg_index_nodes", "ghg_nodes_leaf_fields", "c"),
        ("ghg_factors", "ghg_factors_default_alive", "c"),
        ("ghg_factors", "ghg_factors_version_positive", "c"),
        ("ghg_factor_versions", "ghg_factor_versions_unique", "u"),
        ("ghg_factor_versions", "ghg_factor_versions_version_positive", "c"),
        ("ghg_factor_versions", "ghg_factor_versions_tier_check", "c"),
        ("ghg_factor_versions", "ghg_factor_versions_base_year_range", "c"),
        ("ghg_factor_versions", "ghg_factor_versions_ncv_consistent", "c"),
        ("ghg_factor_versions", "ghg_factor_versions_ncv_positive", "c"),
        ("ghg_factor_gases", "ghg_factor_gases_unique", "u"),
        ("ghg_factor_gases", "ghg_factor_gases_gas_check", "c"),
        ("ghg_factor_gases", "ghg_factor_gases_enabled_values", "c"),
    } <= constraints
    for name, where in (
        ("ghg_nodes_name_unique_alive", "WHERE ((deleted_at IS NULL) AND (NOT ((level)::text = 'facility'::text)))"),
        ("ghg_nodes_root_name_unique_alive", "(name) WHERE ((deleted_at IS NULL) AND (parent_id IS NULL))"),
        ("ghg_nodes_code_unique_alive", "(parent_id, facility_code_id) WHERE (deleted_at IS NULL)"),
        ("ghg_nodes_seed_key_unique", "(seed_key) WHERE (seed_key IS NOT NULL)"),
        ("ghg_factors_one_default_alive", "(facility_node_id) WHERE ((deleted_at IS NULL) AND is_default)"),
        ("ghg_factors_seed_key_unique", "(seed_key) WHERE (seed_key IS NOT NULL)"),
    ):
        assert indexes[name].startswith(f"CREATE UNIQUE INDEX {name} ON public."), name
        assert indexes[name].endswith(where), (name, indexes[name])
    # K1b-2b: 인벤토리 해·고객사 인덱스 선택(회사 범위 표 둘). 같은 회사 키 셋 · UNIQUE · CHECK 셋 · 조건부 UNIQUE
    assert definitions[("inventory_years", "inventory_years_company_id_uniq")] == "UNIQUE (company_id, id)"
    assert (
        definitions[("inventory_index_selections", "inventory_index_selections_company_id_uniq")]
        == "UNIQUE (company_id, id)"
    )
    assert definitions[
        ("inventory_index_selections", "inventory_index_selections_inventory_year_id_same_company_fk")
    ] == ("FOREIGN KEY (company_id, inventory_year_id) REFERENCES inventory_years(company_id, id)")
    assert {
        ("inventory_years", "inventory_years_company_year_unique", "u"),
        ("inventory_years", "inventory_years_decimals_range", "c"),
        ("inventory_years", "inventory_years_year_range", "c"),
        ("inventory_index_selections", "inventory_selections_hidden_alive", "c"),
    } <= constraints
    alive = indexes["inventory_selections_node_unique_alive"]
    assert alive.startswith("CREATE UNIQUE INDEX inventory_selections_node_unique_alive ON public.")
    assert alive.endswith("(inventory_year_id, facility_node_id) WHERE (deleted_at IS NULL)"), alive
    # S12a: Scope 1·2 입력 셋(회사 범위). 같은 회사 키 셋 · 같은 회사 짝 넷 · UNIQUE · CHECK 넷(잠금 짝 포함) · 조건부
    # UNIQUE 하나(인덱스).
    for table in ("inventory_entry_rows", "inventory_entry_values", "inventory_entry_history"):
        assert definitions[(table, f"{table}_company_id_uniq")] == "UNIQUE (company_id, id)", table
    for table, column, target in (
        ("inventory_entry_rows", "selection_id", "inventory_index_selections"),
        ("inventory_entry_rows", "site_facility_id", "site_facilities"),
        ("inventory_entry_values", "row_id", "inventory_entry_rows"),
        ("inventory_entry_history", "row_id", "inventory_entry_rows"),
    ):
        assert definitions[(table, f"{table}_{column}_same_company_fk")] == (
            f"FOREIGN KEY (company_id, {column}) REFERENCES {target}(company_id, id)"
        ), (table, column)
    assert {
        ("inventory_entry_values", "inventory_entry_values_unique", "u"),
        ("inventory_entry_values", "inventory_entry_values_amount_nonneg", "c"),
        ("inventory_entry_values", "inventory_entry_values_slot_format", "c"),
        ("inventory_entry_history", "inventory_entry_history_kind_check", "c"),
        ("inventory_index_selections", "inventory_selections_lock_pair", "c"),
    } <= constraints
    rows_alive = indexes["inventory_entry_rows_unique_alive"]
    assert rows_alive.startswith("CREATE UNIQUE INDEX inventory_entry_rows_unique_alive ON public.")
    assert rows_alive.endswith("(selection_id, site_facility_id) WHERE (deleted_at IS NULL)"), rows_alive
    # S12a-2: 입력주기·직접입력 계수(회사 범위 둘). 같은 회사 키 둘 · 같은 회사 짝 다섯 · UNIQUE · CHECK 여덟
    # (주기 · 직접입력 넷 · 행 하나 · 히스토리 하나 + 넓힌 slot·kind 는 위 이름 그대로).
    for table in ("inventory_entry_periods", "inventory_custom_factors"):
        assert definitions[(table, f"{table}_company_id_uniq")] == "UNIQUE (company_id, id)", table
    for table, column, target in (
        ("inventory_entry_periods", "selection_id", "inventory_index_selections"),
        ("inventory_entry_periods", "site_id", "sites"),
        ("inventory_entry_rows", "custom_factor_id", "inventory_custom_factors"),
        ("inventory_entry_history", "before_custom_id", "inventory_custom_factors"),
        ("inventory_entry_history", "after_custom_id", "inventory_custom_factors"),
    ):
        assert definitions[(table, f"{table}_{column}_same_company_fk")] == (
            f"FOREIGN KEY (company_id, {column}) REFERENCES {target}(company_id, id)"
        ), (table, column)
    assert {
        ("inventory_entry_periods", "inventory_entry_periods_unique", "u"),
        ("inventory_entry_periods", "inventory_entry_periods_period_check", "c"),
        ("inventory_custom_factors", "inventory_custom_factors_tier_check", "c"),
        ("inventory_custom_factors", "inventory_custom_factors_base_year_range", "c"),
        ("inventory_custom_factors", "inventory_custom_factors_ncv_consistent", "c"),
        ("inventory_custom_factors", "inventory_custom_factors_ncv_positive", "c"),
        ("inventory_entry_rows", "inventory_entry_rows_one_factor", "c"),
        ("inventory_entry_history", "inventory_entry_history_factor_refs", "c"),
    } <= constraints
    # S3K2a: Scope 3 카테고리 잠금(회사 범위 하나). 같은 회사 키 하나 · UNIQUE · CHECK 셋. 같은 회사 짝 0(runs FK 0).
    assert (
        definitions[("inventory_scope3_categories", "inventory_scope3_categories_company_id_uniq")]
        == "UNIQUE (company_id, id)"
    )
    assert {
        ("inventory_scope3_categories", "inventory_scope3_categories_unique", "u"),
        ("inventory_scope3_categories", "inventory_scope3_categories_year_range", "c"),
        ("inventory_scope3_categories", "inventory_scope3_categories_category_check", "c"),
        ("inventory_scope3_categories", "inventory_scope3_categories_lock_triple", "c"),
    } <= constraints
    # S3K2b-1: Scope 3 줄 편집 사건(회사 범위 하나). 같은 회사 키 하나 · CHECK 넷. 같은 회사 짝 0(run_id 는 FK 아님).
    assert (
        definitions[("inventory_scope3_row_edits", "inventory_scope3_row_edits_company_id_uniq")]
        == "UNIQUE (company_id, id)"
    )
    assert {
        ("inventory_scope3_row_edits", "inventory_scope3_row_edits_category_check", "c"),
        ("inventory_scope3_row_edits", "inventory_scope3_row_edits_kind_check", "c"),
        ("inventory_scope3_row_edits", "inventory_scope3_row_edits_row_id_check", "c"),
        ("inventory_scope3_row_edits", "inventory_scope3_row_edits_reason_check", "c"),
        ("inventory_scope3_row_edits", "inventory_scope3_row_edits_factor_choice_check", "c"),
        ("inventory_scope3_row_edits", "inventory_scope3_row_edits_factor_rank_check", "c"),
        ("inventory_scope3_row_edits", "inventory_scope3_row_edits_factor_shape", "c"),
    } <= constraints
    # 뿌리 키: 문서·일감의 company_id 는 company(id) 를 가리키는 한 칸 외래 키(Django 의 것 — DEFERRABLE).
    # 기록의 company_id 는 외래 키가 아니다.
    root_keys = sorted(
        table
        for table, _, kind, definition in d1["constraints"]
        if kind == "f" and definition.startswith("FOREIGN KEY (company_id) REFERENCES company(id)")
    )
    assert {"core_documents", "run_jobs"} <= set(root_keys)
    assert {"run_runs", "run_steps", "run_results", "run_files"} <= set(root_keys)  # X1b-1
    assert "run_segments" in root_keys  # RM1a
    assert "core_llm_call_logs" not in root_keys
    assert [name for table, name, kind, _ in d1["constraints"] if table == "core_llm_call_logs" and kind == "f"] == []
    # 세 표의 id 는 bigint 식별 열, 회사 칸은 bigint NOT NULL.
    core_columns = {
        (table, column): (data_type, nullable, identity)
        for table, column, _, data_type, _, nullable, _, identity, _ in d1["columns"]
        if table in {"core_documents", "run_jobs", "core_llm_call_logs"}
    }
    for table in ("core_documents", "run_jobs", "core_llm_call_logs"):
        assert core_columns[(table, "id")] == ("bigint", "NO", "YES"), table
        assert core_columns[(table, "company_id")] == ("bigint", "NO", "NO"), table
    assert core_columns[("core_llm_call_logs", "step")] == ("character varying", "YES", "NO")  # AD4D: NULL 허용
    runs = {(t, c): (kind, null, ident) for t, c, _, kind, _, null, _, ident, _ in d1["columns"] if t == "run_runs"}
    assert runs[("run_runs", "document_id")] == ("bigint", "YES", "NO")  # ND1: 문서 없는 흐름의 실행(회사 FK 는 :144)
    assert runs[("run_runs", "company_id")] == ("bigint", "NO", "NO")  # 회사 칸은 그대로 NOT NULL
    assert runs[("run_runs", "launch_key")] == ("character varying", "YES", "NO")  # LK1: NULL = 묶음 없이 만든 실행
    assert [(table, column) for table, column in core_columns if "tenant" in column] == []  # 기록의 옛 꼬리표 칸도
    # 옛 테넌트 이름은 없다: tenant_id 칸이 있는 표 0, 이름에 tenant 가 든 표·제약·인덱스 0(same_tenant·tenants 포함).
    assert [(table, column) for table, column, *_ in d1["columns"] if column == "tenant_id"] == []
    named = {table for table, *_ in d1["columns"]} | {name for _, name, _ in constraints} | set(indexes)
    assert sorted(name for name in named if "tenant" in name) == []
    # 정책·행 보안 0.
    assert facts(scratch_db, "SELECT count(*) FROM pg_policies") == [(0,)]
    assert (
        facts(
            scratch_db,
            "SELECT relname FROM pg_class WHERE relnamespace = 'public'::regnamespace "
            "AND (relrowsecurity OR relforcerowsecurity)",
        )
        == []
    )
    # core 의 마이그레이션은 0001_initial·0002_llm_call_log_step(AD4D) 둘이다(파일과 적용 기록 둘 다).
    assert sorted(path.name for path in CORE_MIGRATIONS.glob("*.py")) == [
        "0001_initial.py",
        "0002_llm_call_log_step.py",
        "0003_document_artifacts.py",  # RP2a ① 문서 산출물 둘
        "0004_llm_call_log_segment.py",  # RM1a ② 호출 기록 구획 칸
        "0005_document_artifact_chart_labels.py",  # CHL1 ② 산출물 도표 라벨 칸
        "__init__.py",
    ]
    core_records = "SELECT name FROM django_migrations WHERE app = 'core' ORDER BY name"
    assert facts(scratch_db, core_records) == [
        ("0001_initial",),
        ("0002_llm_call_log_step",),
        ("0003_document_artifacts",),  # RP2a ①
        ("0004_llm_call_log_segment",),  # RM1a ②
        ("0005_document_artifact_chart_labels",),  # CHL1
    ]
    # runs 의 마이그레이션 수는 6 이다(X1a·ND1 0002·IK1 0003·LK1 0004 launchKey·RM1a 0005 구획·RM1b 0006 구획 임대 —
    # 파일과 적용 기록).
    # 생기면 고친다.
    runs_count = "SELECT count(*) FROM django_migrations WHERE app = 'runs'"
    assert (
        len(list((CORE_MIGRATIONS.parents[1] / "runs" / "migrations").glob("0*.py"))),
        facts(scratch_db, runs_count),
    ) == (6, [(6,)])
    # organization 의 마이그레이션은 셋이다(0001 · K1b-1 의 0002 스키마·0003 본사 씨앗 — 파일과 적용 기록).
    organization_records = "SELECT name FROM django_migrations WHERE app = 'organization' ORDER BY name"
    assert facts(scratch_db, organization_records) == [
        ("0001_initial",),
        ("0002_branches_facilities",),
        ("0003_headquarters_seed",),
    ]
    # inventory 의 마이그레이션은 넷이다(K1b-2a 의 0001 풀 표 넷 · K1b-2b 의 0002 회사 범위 표 둘 · S12a 의 0003 입력
    # 표 셋 · S12a-2 의 0004 입력주기·직접입력 표 둘 — 적용 기록).
    inventory_records = "SELECT name FROM django_migrations WHERE app = 'inventory' ORDER BY name"
    assert facts(scratch_db, inventory_records) == [
        ("0001_ghg_pool",),
        ("0002_index_selections",),
        ("0003_entries",),
        ("0004_entry_periods_factors",),
        ("0005_scope3_categories",),  # S3K2a Scope 3 카테고리 잠금 표
        ("0006_scope3_row_edits",),  # S3K2b-1 Scope 3 줄 편집 사건 표
        ("0007_scope3_row_factors",),  # S3K2b-2 그 표에 계수 사건 칸
    ]

    # 3. 왕복: runs 를 먼저(core 의 문서를 가리킨다), 그다음 core(organization 의 company 를 가리킨다), 그다음
    #    user(organization 을 가리킨다), 그다음 organization 을 0 으로 → 다시 올린다 → 같은 스키마.
    #    K1b-2a: 그보다 앞에 inventory(풀 잎이 organization 의 코드 목록을 가리킨다).
    for app in ("inventory", "runs", "core", "user", "organization"):
        down = migrate(scratch_db, app, "zero")
        assert down.returncode == 0, down.stderr
    gone = schema(scratch_db)
    tables_gone = {
        "company",
        "sites",
        "users",
        "user_refresh_tokens",
        "core_documents",
        "run_jobs",
        "core_llm_call_logs",
        "run_runs",  # X1b-1
        "run_steps",
        "run_results",
        "run_files",
        "run_segments",  # RM1a
        "organization_facility_codes",  # K1b-1
        "site_facilities",
        "ghg_index_nodes",  # K1b-2a
        "ghg_factors",
        "ghg_factor_versions",
        "ghg_factor_gases",
        "inventory_years",  # K1b-2b
        "inventory_index_selections",
        "inventory_entry_rows",  # S12a
        "inventory_entry_values",
        "inventory_entry_history",
        "inventory_entry_periods",  # S12a-2
        "inventory_custom_factors",
        "inventory_scope3_categories",  # S3K2a
        "inventory_scope3_row_edits",  # S3K2b-1
    }
    assert not tables_gone & {table for table, *_ in gone["columns"]}  # 정말 내려갔다
    assert facts(scratch_db, core_records) == []
    again = migrate(scratch_db)
    assert again.returncode == 0, again.stderr
    d2 = schema(scratch_db)
    assert d1 == d2
    assert facts(scratch_db, core_records) == [
        ("0001_initial",),
        ("0002_llm_call_log_step",),
        ("0003_document_artifacts",),  # RP2a ①
        ("0004_llm_call_log_segment",),  # RM1a ②
        ("0005_document_artifact_chart_labels",),  # CHL1
    ]
