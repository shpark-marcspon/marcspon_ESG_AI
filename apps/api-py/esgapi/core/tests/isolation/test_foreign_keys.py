"""같은 회사 외래 키의 마이그레이션 조각(받침 ⑤, core/isolation/foreign_keys.py)이 내는 SQL 의 글자. 순수(DB 없음).

재는 것: 칸의 차례 (company_id, <칸>) 와 REFERENCES "<표>" (company_id, id), NOT DEFERRABLE, reverse_sql 이 같은 이름의
DROP CONSTRAINT 인가, 이름이 63자 안인가(넘으면 ValueError).
★ 무효 조건: 글자만 잰다. DB 가 그 글을 받아 제약을 세우는지·거절하는지는 보안 층이 잰다
  (test_same_company_foreign_keys.py 의 카탈로그 검사, test_documents.py 의 23503).
"""

import inspect

import pytest

from esgapi.core.isolation.foreign_keys import MAX_IDENTIFIER_CHARS, company_key, same_company_foreign_key


def test_company_key_is_a_unique_on_company_then_id_with_a_matching_drop() -> None:
    operation = company_key("core_documents")
    assert operation.sql == (
        'ALTER TABLE "core_documents" ADD CONSTRAINT "core_documents_company_id_uniq" UNIQUE (company_id, id);'
    )
    assert operation.reverse_sql == 'ALTER TABLE "core_documents" DROP CONSTRAINT "core_documents_company_id_uniq";'


def test_same_company_foreign_key_names_the_company_first_and_is_checked_per_statement() -> None:
    operation = same_company_foreign_key(table="run_jobs", column="document_id", target="core_documents")
    assert operation.sql == (
        'ALTER TABLE "run_jobs" ADD CONSTRAINT "run_jobs_document_id_same_company_fk" '
        'FOREIGN KEY (company_id, document_id) REFERENCES "core_documents" (company_id, id) NOT DEFERRABLE;'
    )
    assert operation.reverse_sql == 'ALTER TABLE "run_jobs" DROP CONSTRAINT "run_jobs_document_id_same_company_fk";'
    assert "INITIALLY DEFERRED" not in str(operation.sql)


def test_the_company_column_is_fixed_on_both_sides() -> None:
    """회사 칸은 인자가 아니다: 칸 차례 양쪽(이 표·가리키는 표)에 company_id 가 든다(K1b 의 사업장·배출시설의 꼴)."""
    assert list(inspect.signature(company_key).parameters) == ["table"]
    assert list(inspect.signature(same_company_foreign_key).parameters) == ["table", "column", "target"]
    key = company_key("sites")
    assert key.sql == 'ALTER TABLE "sites" ADD CONSTRAINT "sites_company_id_uniq" UNIQUE (company_id, id);'
    fk = same_company_foreign_key(table="facilities", column="site_id", target="sites")
    assert 'FOREIGN KEY (company_id, site_id) REFERENCES "sites" (company_id, id) NOT DEFERRABLE' in str(fk.sql)
    assert "tenant" not in str(key.sql) + str(fk.sql)


def test_names_fit_postgres_identifiers_and_longer_ones_are_refused() -> None:
    assert len("run_jobs_document_id_same_company_fk") == 36
    assert MAX_IDENTIFIER_CHARS == 63
    fits = "t" * (MAX_IDENTIFIER_CHARS - len("_c_same_company_fk"))  # 이름이 정확히 63자
    assert f'"{fits}_c_same_company_fk"' in str(same_company_foreign_key(table=fits, column="c", target="x").sql)
    with pytest.raises(ValueError, match="63"):
        same_company_foreign_key(table=fits + "t", column="c", target="x")
    with pytest.raises(ValueError, match="63"):
        company_key("t" * (MAX_IDENTIFIER_CHARS - len("_company_id_uniq") + 1))
    assert '"' + "t" * 47 + '_company_id_uniq"' in str(company_key("t" * 47).sql)
