"""받침 ⑤ 의 카탈로그 검사: 회사 칸이 있는 두 표 사이의 외래 키마다 같은 회사 외래 키 짝이 DB 에 있다. 보안 층.

「company_id 칸이 있는 표 → company_id 칸이 있는 표」의 한 칸 외래 키(Django 의 ForeignKey 가 만든 것) — 자기 참조
포함 — 마다 (company_id, <그 칸>) → <그 표> (company_id, id) 짝이 있고, 그 짝은 NOT DEFERRABLE 이다(문마다 잰다).
짝은 core/isolation/foreign_keys.py 의 same_company_foreign_key 로 건다. 표의 이름을 박지 않고 카탈로그에 묻는다:
K1 이 사업장·배출시설의 하위 표를 세우며, X1 이 previous_document_id 를 세우며 짝을 빠뜨리면 이 테스트가 빨개진다.
셈은 missing_same_company_pairs 하나이고, 자기 시험이 그 셈이 빠뜨림을 실제로 잡는 것을 잰다(임시 표 둘, 되돌림).

company 를 가리키는 키(users·sites·core_documents·run_jobs → company)는 뿌리라 셈 밖이다: company 에는 company_id
칸이 없어 저절로 빠진다(분모로는 센다).
★ 무효 조건: public 스키마의 일반 표(relkind 'r')만 본다. 여러 칸 외래 키(짝 자신 말고)가 생기면 그것은 이 검사가
  보지 않는다. users.company_id 는 운영 관리자 행에서 NULL 일 수 있다 — 짝은 MATCH SIMPLE 이라 회사 칸이 NULL 인
  행은 검사를 비껴간다. 지금 users 를 가리키는 회사 표의 외래 키는 0 이다(생기면 그 키의 NULL 행은 짝이 못 막는다).
"""

from typing import Any

import psycopg
import pytest

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
COMPANY = "company_id"
ROOT = "company"

# 외래 키 전부: (제약 이름, 표, 칸들(차례대로), 가리키는 표, 가리키는 칸들(차례대로), DEFERRABLE 인가)
FOREIGN_KEYS_SQL = """
    SELECT con.conname,
           src.relname,
           ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY AS k(num, pos)
                 JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.num ORDER BY k.pos)::text[],
           dst.relname,
           ARRAY(SELECT a.attname FROM unnest(con.confkey) WITH ORDINALITY AS k(num, pos)
                 JOIN pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.num ORDER BY k.pos)::text[],
           con.condeferrable
    FROM pg_constraint con
    JOIN pg_class src ON src.oid = con.conrelid
    JOIN pg_class dst ON dst.oid = con.confrelid
    WHERE con.contype = 'f'
      AND src.relnamespace = 'public'::regnamespace
      AND src.relkind = 'r'
    ORDER BY src.relname, con.conname
"""

# company_id 칸이 있는 public 의 일반 표(company 는 없다 — 그 표의 회사는 id 다).
TABLES_WITH_COMPANY_SQL = """
    SELECT c.relname FROM pg_class c
    WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
      AND EXISTS (SELECT 1 FROM pg_attribute a
                  WHERE a.attrelid = c.oid AND a.attname = %s AND NOT a.attisdropped)
    ORDER BY c.relname
"""

# 자기 시험의 임시 표 둘(이름이 겹치지 않게 접두를 둔다). 되돌린 뒤 이 접두의 표가 0 이어야 한다.
PROBE_PREFIX = "k1u_probe_"
PROBE_PARENT = f"{PROBE_PREFIX}parent"
PROBE_CHILD = f"{PROBE_PREFIX}child"
PROBE_SELF = f"{PROBE_PREFIX}self"

Key = tuple[str, str, str]  # (표, 칸, 가리키는 표)


class _RollBack(Exception):
    """자기 시험의 트랜잭션을 되돌리는 표지(psycopg 의 transaction() 블록은 예외로 나가면 ROLLBACK 한다)."""


def missing_same_company_pairs(owner: Owner) -> tuple[list[Key], list[Key], list[Key]]:
    """(셈에 든 한 칸 외래 키, 그 가운데 짝이 없는 것, 짝이 DEFERRABLE 인 것). 표 이름을 박지 않는다.

    셈: 「company_id 칸이 있는 표 → company_id 칸이 있는 표」의 한 칸 외래 키. 자기 참조도 센다.
    """
    with_company = {name for (name,) in owner.execute(TABLES_WITH_COMPANY_SQL, [COMPANY])}
    keys: list[tuple[str, str, list[str], str, list[str], bool]] = [
        (name, table, list(columns), target, list(target_columns), deferrable)
        for name, table, columns, target, target_columns, deferrable in owner.execute(FOREIGN_KEYS_SQL)
    ]
    single = sorted(
        (table, columns[0], target)
        for _, table, columns, target, _, _ in keys
        if len(columns) == 1 and table in with_company and target in with_company
    )
    pairs = {
        (table, columns[1], target): deferrable
        for _, table, columns, target, target_columns, deferrable in keys
        if len(columns) == 2 and columns[0] == COMPANY and target_columns == [COMPANY, "id"]
    }
    missing = [key for key in single if key not in pairs]
    deferrable_pairs = [key for key in single if pairs.get(key) is True]
    return single, missing, deferrable_pairs


def test_every_foreign_key_between_company_tables_names_the_company(owner: Owner) -> None:
    with_company = {name for (name,) in owner.execute(TABLES_WITH_COMPANY_SQL, [COMPANY])}
    # 분모: 회사 칸이 있는 표가 실제로 이만큼 잡혔다.
    assert {"users", "sites", "core_documents", "run_jobs", "core_llm_call_logs"} <= with_company
    assert {"run_runs", "run_steps", "run_results", "run_files"} <= with_company  # X1b-1 실행 넷
    assert "run_segments" in with_company  # RM1a 구획 기록

    # 뿌리: company 에는 company_id 칸이 없다 → company 를 가리키는 키는 아래 셈에 저절로 안 든다.
    assert ROOT not in with_company
    to_company = {
        table
        for _, table, columns, target, _, _ in owner.execute(FOREIGN_KEYS_SQL)
        if target == ROOT and list(columns) == [COMPANY]
    }
    assert {"users", "sites", "core_documents", "run_jobs"} <= to_company  # 분모: 뿌리 키가 실제로 있었고 빠졌다
    assert {"run_runs", "run_steps", "run_results", "run_files"} <= to_company  # X1b-1 실행 넷의 뿌리 키
    assert "run_segments" in to_company  # RM1a

    single, missing, deferrable = missing_same_company_pairs(owner)
    assert not [key for key in single if key[2] == ROOT]
    assert ("run_jobs", "document_id", "core_documents") in single  # 분모 ≥ 1: 그 자리를 실제로 찾았다
    # X1b-1 새 키 다섯(실행 → 문서, 하위 셋 → 실행, 문서의 앞 판 → 문서 — 자기 참조)이 셈에 든다
    # (짝은 아래 missing 이 본다).
    assert {
        ("run_runs", "document_id", "core_documents"),
        ("run_steps", "run_id", "run_runs"),
        ("run_results", "run_id", "run_runs"),
        ("run_files", "run_id", "run_runs"),
        ("run_segments", "run_id", "run_runs"),  # RM1a 구획 → 실행
        ("core_documents", "previous_document_id", "core_documents"),
    } <= set(single)
    # K1b-1: 사업장별 자산/시설 → 사업장(코드 목록은 회사 칸이 없어 셈 밖 — 짝 없음).
    assert ("site_facilities", "site_id", "sites") in single
    assert ("site_facilities", "facility_code_id", "organization_facility_codes") not in single
    # K1b-2a: 온실가스 풀 표 넷은 회사 칸이 없다(공통) — 풀 표 짝 없음, 셈 밖.
    assert not [key for key in single if key[0].startswith("ghg_")]
    # K1b-2b: 고객사 인덱스 선택 → 인벤토리 해(같은 회사 짝). 선택 → 풀 잎·판은 공통 표라 셈 밖.
    assert ("inventory_index_selections", "inventory_year_id", "inventory_years") in single
    assert not [key for key in single if key[0] == "inventory_index_selections" and key[2].startswith("ghg_")]
    # S12a: 입력 행 → 선택·자산/시설, 값·히스토리 → 행(같은 회사 짝 넷).
    assert {
        ("inventory_entry_rows", "selection_id", "inventory_index_selections"),
        ("inventory_entry_rows", "site_facility_id", "site_facilities"),
        ("inventory_entry_values", "row_id", "inventory_entry_rows"),
        ("inventory_entry_history", "row_id", "inventory_entry_rows"),
    } <= set(single)
    # S12a-2: 주기 → 선택·사업장, 행·히스토리 앞뒤 → 직접입력(같은 회사 짝 다섯). 행·히스토리 → 풀 판은 공통 표라 셈 밖.
    assert {
        ("inventory_entry_periods", "selection_id", "inventory_index_selections"),
        ("inventory_entry_periods", "site_id", "sites"),
        ("inventory_entry_rows", "custom_factor_id", "inventory_custom_factors"),
        ("inventory_entry_history", "before_custom_id", "inventory_custom_factors"),
        ("inventory_entry_history", "after_custom_id", "inventory_custom_factors"),
    } <= set(single)
    assert not [key for key in single if key[0].startswith("inventory_entry_") and key[2].startswith("ghg_")]
    assert (missing, deferrable) == ([], [])
    # G1b: 표시 → 검토의 같은 회사 복합 외래 키 하나(대상 (company_id, run_id) — 위 셈 밖의 여러 칸 키, NOT DEFERRABLE).
    # 검토 표의 run_id 는 외래 키가 아니다(MARC-ENT-210 (1)).
    composite = [
        (table, list(columns), target, list(target_columns), deferrable)
        for _, table, columns, target, target_columns, deferrable in owner.execute(FOREIGN_KEYS_SQL)
        if table == "greenwash_review_marks" and len(columns) == 2
    ]
    pair = [COMPANY, "run_id"]
    assert composite == [("greenwash_review_marks", pair, "greenwash_reviews", pair, False)]


def test_the_check_catches_a_single_column_key_between_company_tables(owner: Owner) -> None:
    """자기 시험: 짝 없이 한 칸 외래 키만 둔 company_id 표 둘(부모·자식)과 자기 참조 표 하나를 세우면 셈이 그 키들을
    missing 에 낸다(자기 참조도 센다 — X1 의 previous_document_id 같은 칸). 그리고 되돌린다.

    주인 연결은 autocommit 이다 — transaction() 블록이 BEGIN 을 열고, 표지 예외로 나가며 ROLLBACK 한다.
    """
    key = (PROBE_CHILD, "parent_id", PROBE_PARENT)
    self_key = (PROBE_SELF, "prev_id", PROBE_SELF)
    seen: tuple[list[Key], list[Key], list[Key]] | None = None
    with pytest.raises(_RollBack), owner.transaction():
        owner.execute(f'CREATE TABLE "{PROBE_PARENT}" (id bigint PRIMARY KEY, {COMPANY} bigint NOT NULL)')
        owner.execute(
            f'CREATE TABLE "{PROBE_CHILD}" (id bigint PRIMARY KEY, {COMPANY} bigint NOT NULL, '
            f'parent_id bigint NOT NULL REFERENCES "{PROBE_PARENT}" (id))'
        )
        owner.execute(
            f'CREATE TABLE "{PROBE_SELF}" (id bigint PRIMARY KEY, {COMPANY} bigint NOT NULL, '
            f'prev_id bigint REFERENCES "{PROBE_SELF}" (id))'
        )
        seen = missing_same_company_pairs(owner)
        raise _RollBack
    assert seen is not None
    single, missing, deferrable = seen
    assert {key, self_key} <= set(single)  # 셈에 들었다(분모). 자기 참조도 빠지지 않는다
    assert {key, self_key} <= set(missing)  # 짝이 없다고 냈다
    assert key not in deferrable and self_key not in deferrable
    assert ("run_jobs", "document_id", "core_documents") not in missing  # 짝이 있는 키는 그대로 초록이다

    # 되돌렸다: 그 접두의 표가 카탈로그에 0, 셈도 원래대로.
    left = owner.execute(
        "SELECT count(*) FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relname LIKE %s",
        [PROBE_PREFIX.replace("_", "\\_") + "%"],
    ).fetchone()
    assert left == (0,)
    after = missing_same_company_pairs(owner)[0]
    assert key not in after and self_key not in after
