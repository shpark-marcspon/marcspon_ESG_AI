"""실행 묶음의 날 SQL 두 문장(PostgreSQL). 이 앱에서 날 SQL 이 있는 자리는 이 파일 하나다
(core/tests/isolation/test_static_rules.py 의 RAW_SQL_ALLOWED). 값은 매개로만 묶는다.

    read_only_snapshot()             내보내기 블록의 첫 문장: 그 트랜잭션을 REPEATABLE READ, READ ONLY 로(읽기 전부가 한
                                     스냅숏 — 실행·단계·결과·파일·문서·LLM 기록·모듈 행이 같은 때의 것)
    lock_bundle(company_id, bundle)  넣기 블록의 첫 문장: (회사, bundleId) 의 advisory 잠금(트랜잭션 끝에 풀린다).
                                     같은 묶음의 동시 넣기는 뒤의 것이 기다렸다 앞의 커밋을 보고 거절된다(Q4)

★ 전제(HD1 R7): lock_bundle 뒤 taken_keys 가 앞 넣기의 커밋을 보는 것은 넣기 블록이 READ COMMITTED(Django 기본 —
  config/settings 에 isolation_level 0)여서 문장마다 새 스냅숏을 잡기 때문이다. 넣기 블록을 REPEATABLE READ 로 바꾸면
  잠금을 기다린 뒤에도 앞 커밋 전의 스냅숏을 보아 같은 묶음이 두 번 넣힌다(내보내기의 REPEATABLE READ 는 읽기 전용이라
  상관없다).
★ 둘 다 블록 안에서만 부른다(밖이면 RuntimeError). read_only_snapshot 은 블록의 첫 문장이어야 먹는다(Postgres 는 첫
  질의 뒤의 SET TRANSACTION 을 거절한다 — 그래서 실수로 늦게 부르면 조용히 지나가지 않고 던진다).
"""

from django.db import connection


def _require_block(name: str) -> None:
    if not connection.in_atomic_block:
        raise RuntimeError(f"{name} 은 트랜잭션 블록 안에서만 부른다")


def read_only_snapshot() -> None:
    _require_block("read_only_snapshot")
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")


def lock_bundle(company_id: int, bundle_id: str) -> None:
    _require_block("lock_bundle")
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [f"runbundle:{company_id}:{bundle_id}"])
