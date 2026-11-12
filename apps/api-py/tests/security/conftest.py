"""보안 층의 고정물. 이 층은 RLS 없는 앱 역할 연결에서 ①②③⑤ 가 남의 행을 막는 것을 잰다.
  ① selector·service 의 회사 조건  ② 회사 범위 표의 기본 매니저(core/isolation)  ③ 경로 표(test_tenant_paths.py)
  ⑤ 같은 회사 외래 키. 그 밖에 앱 역할의 권한(GRANT)과 연결에 남는 상태를 잰다.

돌리기:  scripts/test-security.sh  (= uv run pytest --ds=esgapi.config.settings.test_security -m security)
직렬로만 돈다.
설정 모듈이 그것이 아니거나 pytest-xdist 의 워커 안이면 첫 고정물이 까닭을 말하고 멈춘다.

DB 연결은 둘이다. 섞이지 않게 길을 갈랐다.
  - 앱 역할(esg_app): Django 의 연결. 테스트하려는 코드(요청, ORM)는 전부 이 역할로 돈다.
    정책(RLS)은 없고 GRANT 만 걸린다.
  - 주인 역할: psycopg 로 직접 맺은 연결(owner 고정물). 테스트 DB 만들기, 마이그레이션, 자료 심기(seed.py),
    「실제로는 몇 행이 있는가」(분모) 세기에만 쓴다.

pytest-django 의 테스트 DB 만들기를 쓰지 않는 까닭(업무 층은 그것을 쓴다): 그것은 Django 의 연결(= 앱 역할)로
DB 를 만들려 하는데 앱 역할에는 그럴 권한이 없다(없어야 한다). 또 테스트를 큰 트랜잭션 하나로 감싸 되돌리는데,
그러면 커밋 뒤의 일(갈고리, 다른 연결이 보는 행, durable 블록, 연결 재사용)을 잴 수 없다.
그래서 여기서는 진짜로 커밋하고, 테스트마다 주인 연결로 표를 비운다. 느리고 병렬이 안 되므로 이 층은 작게 둔다.
"""

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from django.conf import settings
from django.db import connections
from django.test import Client, override_settings
from psycopg import sql

from tests.security.seed import add_companies
from tests.support.db import TENANT_TABLES_SQL, TEST_DB_SUFFIX

API_PY_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def test_database() -> Iterator[str]:
    """테스트 DB 를 주인 역할로 만들고 마이그레이션한다. 돌려주는 것은 그 DB 의 주인 주소."""
    if settings.SETTINGS_MODULE != "esgapi.config.settings.test_security":
        pytest.fail(
            "보안 층은 --ds=esgapi.config.settings.test_security 로 돌린다(Django 가 앱 역할로 붙어야 한다). "
            f"지금 설정: {settings.SETTINGS_MODULE}. scripts/test-security.sh 를 쓴다.",
            pytrace=False,
        )
    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.fail(
            "보안 층은 직렬로만 돈다(테스트마다 진짜 커밋을 하고 표를 비운다. DB 가 하나다). -n 을 뺀다.", pytrace=False
        )
    owner_url = os.environ.get("TEST_DATABASE_URL_PY_OWNER", "")
    if not owner_url or not os.environ.get("TEST_DATABASE_URL_PY"):
        pytest.fail(
            "보안 층에는 TEST_DATABASE_URL_PY(앱 역할)와 TEST_DATABASE_URL_PY_OWNER(주인 역할)가 있어야 한다. "
            "scripts/test-security.sh 가 compose 의 Postgres 주소로 채워 돌린다.",
            pytrace=False,
        )
    test_name = owner_url.rsplit("/", 1)[1] + TEST_DB_SUFFIX
    owner_test_url = owner_url + TEST_DB_SUFFIX

    with psycopg.connect(owner_url, autocommit=True) as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(test_name)))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test_name)))
    # migrate-py 컨테이너가 하는 것과 같은 명령, 같은 설정으로 마이그레이션한다.
    subprocess.run(
        [sys.executable, "manage.py", "migrate", "--no-input", "-v", "0"],
        cwd=API_PY_DIR,
        env={
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "esgapi.config.settings.migrate",
            "DATABASE_URL_PY_OWNER": owner_test_url,
        },
        check=True,
    )
    yield owner_test_url
    connections.close_all()
    with psycopg.connect(owner_url, autocommit=True) as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(test_name)))


def tenant_tables(conn: psycopg.Connection[tuple[Any, ...]]) -> list[str]:
    """테넌트의 표: company 와, company_id 칸이 있는 표 전부(카탈로그에서 읽는다 — core 의 세 표도 든다)."""
    return [name for (name,) in conn.execute(TENANT_TABLES_SQL)]


@pytest.fixture
def owner(test_database: str) -> Iterator[psycopg.Connection[tuple[Any, ...]]]:
    """주인 역할의 연결. 테스트마다 표를 비운 채로 시작한다."""
    with psycopg.connect(test_database, autocommit=True) as conn:
        # 표의 이름을 여기 적지 않는다: 모듈이 테넌트의 표를 더해도 이 파일을 고치지 않게 카탈로그에 묻는다.
        # CASCADE: 이 표들을 외래 키로 가리키는 다른 표가 있으면 그것도 같이 비운다(차례를 따질 필요가 없다).
        # 식별 열(company·sites·users·core 세 표의 id)은 되돌리지 않는다: id 를 박지 말고 고정물·seed 가 돌려준
        # 값을 쓴다.
        tables = tenant_tables(conn)
        conn.execute(sql.SQL("TRUNCATE {} CASCADE").format(sql.SQL(", ").join(map(sql.Identifier, tables))))
        yield conn


@pytest.fixture(autouse=True)
def _app_role_db(request: pytest.FixtureRequest) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """@pytest.mark.security 가 붙은 테스트에서만 Django 의 DB 연결(앱 역할)을 풀어 준다. 나머지는 닿으면 실패한다."""
    if "security" not in request.keywords:
        yield
        return
    request.getfixturevalue("owner")
    blocker: Any = request.getfixturevalue("django_db_blocker")
    with blocker.unblock():
        yield
        # 다음 테스트가 이 테스트의 연결 상태(남은 설정 등)를 물려받지 않게 끊는다.
        connections.close_all()


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.fixture
def fast_hasher() -> Iterator[None]:
    """비밀번호 해시를 MD5 로 바꿔 빠르게 돈다(로그인·refresh 의 테스트가 usefixtures 로 건다 — 제품 설정은 그대로다).
    요청은 이 프로세스의 테스트 클라이언트로 가므로 설정 덮기가 그대로 닿는다(스레드에도 — 설정은 프로세스 하나다).
    user_refresh_tokens 는 users 를 외래 키로 가리켜 owner 의 TRUNCATE … CASCADE 가 같이 비운다."""
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


@pytest.fixture
def companies(owner: psycopg.Connection[tuple[Any, ...]]) -> tuple[int, int]:
    """회사 둘(subdomain tenant-a·tenant-b, 쓸 수 있음)을 등록한다(마크스폰 관리자가 하는 일. 앱에는 이 길이 없다).
    A·B 의 id 를 돌려준다(식별 열이라 테스트마다 다르다 — 박지 않는다)."""
    return add_companies(owner)


@pytest.fixture
def tenants(companies: tuple[int, int]) -> None:
    """옛 이름 그대로의 고정물(id 가 필요 없는 테스트가 쓴다). 몸은 companies 다."""


def count(owner: psycopg.Connection[tuple[Any, ...]], table: str) -> int:
    """주인 역할로 센 실제 행 수(분모)."""
    row = owner.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()
    assert row is not None
    return int(row[0])
