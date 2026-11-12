"""테스트 DB 의 이름 규칙. 설정(config/settings/test_security.py)과 보안 층의 conftest 가 같이 읽는다."""

# 보안 층은 원래 DB 이름 뒤에 _test 를 붙인 별도 DB 에서 돈다. 띄워 둔 서버의 자료를 건드리지 않는다.
# (업무 층의 DB 는 pytest-django 가 이름 앞에 test_ 를 붙여 만든다. 둘은 겹치지 않는다.)
TEST_DB_SUFFIX = "_test"

# 테넌트의 표: 뿌리 company 와, company_id 칸이 있는 표 전부(users·sites, core 의 셋 — 문서·일감·기록).
# 이름을 박지 않고 카탈로그에 묻는다(모듈이 표를 더해도 보안 층의 고정물과 카탈로그 검사를 고치지 않게).
# company 를 따로 적은 까닭: 그 표의 회사는 자기 id 라 칸 이름으로는 찾아지지 않는다.
# 이름(TENANT_…)은 옛 그대로다(이름 바꾸기는 C1). tenant_id 칸이 있는 표는 이제 없다(test_migrations.py 가 잰다).
TENANT_TABLES_SQL = """
    SELECT c.relname
    FROM pg_class c
    WHERE c.relnamespace = 'public'::regnamespace
      AND c.relkind = 'r'
      AND (
        c.relname = 'company'
        OR EXISTS (
          SELECT 1 FROM pg_attribute a
          WHERE a.attrelid = c.oid AND a.attname = 'company_id' AND NOT a.attisdropped
        )
      )
    ORDER BY c.relname
"""
