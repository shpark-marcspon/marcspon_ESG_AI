"""같은 회사 외래 키(격리의 받침 ⑤)를 거는 마이그레이션 조각 둘.
하위 행이 남의 회사 행을 가리키지 못하게 DB 가 막는다.

    company_key(table)                                   UNIQUE (company_id, id) — 외래 키가 가리킬 자리
    same_company_foreign_key(table=, column=, target=)   FOREIGN KEY (company_id, <칸>) → <target> (company_id, id)

    from esgapi.core.isolation.foreign_keys import company_key, same_company_foreign_key
    operations = [
        company_key("core_documents"),
        same_company_foreign_key(table="run_jobs", column="document_id", target="core_documents"),
    ]

회사 칸(company_id)이 있는 두 표 사이의 한 칸 외래 키마다 — 자기 참조 포함 — 이 둘을 쓴다
(K1b 의 사업장·배출시설, X1 의 previous_document_id 도).
보안 층의 카탈로그 검사(tests/security/test_same_company_foreign_keys.py)가 빠뜨림을 잡는다.

Django 의 한 칸 외래 키(ForeignKey)는 그대로 둔다(모델 0줄 — RunSQL 이라 마이그레이션 상태가 안 바뀐다).
이것은 그 옆에 하나를 더 건다.

★ NOT DEFERRABLE(문마다 잰다): Django 가 만드는 한 칸 외래 키는 DEFERRABLE INITIALLY DEFERRED 라 커밋 때만 잰다.
  같은 꼴로 두면 테스트마다 롤백하는 업무 층에서는 한 번도 안 걸린다. 그래서 어기는 INSERT·UPDATE 는 그 문에서
  SQLSTATE 23503(foreign_key_violation)이다.
★ 무효 조건: 회사 칸이 NULL 인 행은 MATCH SIMPLE 이라 검사를 비껴간다(core 의 표는 company_id 가 NOT NULL. users 는
  운영 관리자 행에서 NULL 일 수 있다 — 지금 users 를 가리키는 회사 표의 외래 키는 0).
  이름은 PostgreSQL 의 식별자 한도 63자 안이어야 한다(넘으면 ValueError — 조용히 잘리면 reverse_sql 이
  엉뚱한 이름을 찾는다).
★ 이 함수를 쓰는 마이그레이션은 core 0001 하나다(K1u-b 가 core 마이그레이션을 다시 쓰며 이름을 바꿨다 — 배포된 DB 0).
  이제부터는 적용된 마이그레이션이 이 문면을 쓴다: 문면을 고치면 옛 DB 와 새 DB 의 제약이 달라진다.
  고치지 말고 새 함수를 더한다.
"""

from django.db import migrations

MAX_IDENTIFIER_CHARS = 63  # PostgreSQL 의 NAMEDATALEN - 1
COMPANY = "company_id"


def _checked_name(name: str) -> str:
    if len(name) > MAX_IDENTIFIER_CHARS:
        raise ValueError(f"제약 이름이 {MAX_IDENTIFIER_CHARS}자를 넘는다({len(name)}자): {name}")
    return name


def company_key(table: str) -> migrations.RunSQL:
    """UNIQUE (company_id, id) — 같은 회사 외래 키가 가리킬 자리. 이름 "<table>_company_id_uniq"."""
    name = _checked_name(f"{table}_company_id_uniq")
    return migrations.RunSQL(
        sql=f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" UNIQUE ({COMPANY}, id);',
        reverse_sql=f'ALTER TABLE "{table}" DROP CONSTRAINT "{name}";',
    )


def same_company_foreign_key(*, table: str, column: str, target: str) -> migrations.RunSQL:
    """FOREIGN KEY (company_id, column) REFERENCES target (company_id, id) NOT DEFERRABLE.

    이름 "<table>_<column>_same_company_fk".

    target 에 company_key(target) 가 먼저 서 있어야 한다(가리킬 UNIQUE 가 없으면 DB 가 거절한다).
    """
    name = _checked_name(f"{table}_{column}_same_company_fk")
    return migrations.RunSQL(
        sql=(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" '
            f'FOREIGN KEY ({COMPANY}, {column}) REFERENCES "{target}" ({COMPANY}, id) NOT DEFERRABLE;'
        ),
        reverse_sql=f'ALTER TABLE "{table}" DROP CONSTRAINT "{name}";',
    )
