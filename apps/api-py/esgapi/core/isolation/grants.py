"""앱 역할(esg_app)에게 표의 권한을 주는 마이그레이션 조각. 마이그레이션만 import 한다(요청·워커는 안 부른다).

옛 RLS 조각의 grant 를 글자 그대로 옮긴 자리다(K1u-a). 옛 조각은 K1u-b 가 core 마이그레이션을 다시 쓰며 지웠다.
마이그레이션은 여기의 grant 를 쓴다(organization·core·runs·greenwash·user 의 0001, reference 0001, greenwash 0002,
user 0002).

    from esgapi.core.isolation.grants import grant
    operations = [..., grant('"my_table"', "SELECT, INSERT, UPDATE")]

DELETE 와 표 변경 권한은 주지 않는다. 전제: 앱은 esg_app 역할로 붙고, 그 역할은 표의 주인도 superuser 도 아니다.
무효 조건: superuser 인 역할에게는 GRANT 가 뜻이 없다(전부 된다). 로컬 compose 의 주인 역할이 그렇다.
"""

from django.db import migrations

APP_ROLE = "esg_app"


def grant(tables: str, privileges: str) -> migrations.RunSQL:
    """앱 역할에게 권한을 준다. tables 는 '"a", "b"' 꼴, privileges 는 'SELECT, INSERT, UPDATE' 꼴."""
    return migrations.RunSQL(
        sql=f"GRANT {privileges} ON {tables} TO {APP_ROLE};",
        reverse_sql=f"REVOKE {privileges} ON {tables} FROM {APP_ROLE};",
    )
