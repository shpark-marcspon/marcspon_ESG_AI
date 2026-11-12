"""통합 테스트의 도구. compose 로 떠 있는 컨테이너에 호스트에서 실제로 요청을 보낸다.

TS 쪽의 tests/integration/helpers.ts 와 같은 일을 한다: compose 가 읽는 것과 같은 .env 를 읽어
주소가 테스트 코드에 박히지 않게 하고, 「실제로는 몇 행인가」는 주인 역할로 센다.
"""

import os
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest

API_PY_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = API_PY_DIR.parent.parent
sys.path.insert(0, str(API_PY_DIR / "scripts"))


def read_env_file() -> dict[str, str]:
    """저장소 맨 위의 .env 를 읽는다(KEY=VALUE 줄만). 이미 환경 변수로 준 값이 이긴다(compose 와 같은 규칙)."""
    values: dict[str, str] = {}
    for line in (REPO_ROOT / ".env").read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return {**values, **{k: v for k, v in os.environ.items() if k in values}}


ENV = read_env_file()
API = f"http://127.0.0.1:{ENV.get('API_PY_PORT', '18081')}/api"  # API 의 mount 자리(config/urls.py)
OWNER_URL = (
    f"postgres://{ENV['POSTGRES_OWNER_USER']}:{ENV['POSTGRES_OWNER_PASSWORD']}"
    f"@127.0.0.1:{ENV['POSTGRES_PORT']}/{ENV['POSTGRES_DB']}_py"
)
PY_DB = f"{ENV['POSTGRES_DB']}_py"
# 컨테이너가 받은 값과 같아야 한다: .env 에 있으면 그 값, 없으면 compose.yaml 의 기본값.
AUDIENCE = ENV.get("EDK_JWT_AUDIENCE", "esg-api")
ISSUER = ENV.get("EDK_JWT_ISSUER", "https://edk.local.invalid")


def worker_value(key: str, default: int) -> int:
    """worker-py 가 받은 수(초·횟수)를 compose 와 같은 차례로 읽는다: 이 프로세스의 환경 → .env → 설정의 기본값.

    빈 글자(빈칸뿐인 글자 포함)는 「없음」이다(compose 의 `${KEY:-}` 가 빈 값을 넘기면 설정이 기본값을 쓴다).
    ★ ENV 는 .env 에 있는 키만 환경으로 덮는다. 그래서 환경을 먼저 본다(전량 게이트는 .env 에 없는 키를 내보낸다).
    """
    for text in (os.environ.get(key, ""), ENV.get(key, "")):
        if text.strip():
            return int(text)
    return default


# 쉼이 기대는 워커의 값(기본은 esgapi/config/env.py 의 것). scripts/verify.sh 는 짧은 값을 내보낸 뒤 띄운다.
WAIT_TIME_S = worker_value("CELERY_WAIT_TIME_SECONDS", 10)  # 긴 폴링
RETRY_DELAY_S = worker_value("JOB_RETRY_DELAY_SECONDS", 5)  # 잠깐의 실패 뒤 다시 해 보기까지
MAX_ATTEMPTS = worker_value("JOB_MAX_ATTEMPTS", 3)  # 한 일감을 몇 번까지 잡는가


def compose(*args: str) -> str:
    """이 저장소의 compose 프로젝트(이름은 .env 의 COMPOSE_PROJECT_NAME)의 컨테이너만 다룬다."""
    done = subprocess.run(["docker", "compose", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return done.stdout


def container_state(service: str) -> tuple[str, int]:
    container_id = compose("ps", "-a", "-q", service).strip()
    out = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Status}} {{.State.ExitCode}}", container_id],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return out[0], int(out[1])


def wait_for[T](what: str, check: Callable[[], T | None], timeout: float = 60.0) -> T:
    """정해진 시간만큼 자지 않는다. 조건이 참이 될 때까지 짧게 되묻고, 제한 시간이 지나면 실패한다."""
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (httpx.HTTPError, psycopg.Error) as err:
            last = err  # 컨테이너가 내려가 있는 동안의 연결 오류. 다시 묻는다.
        time.sleep(0.2)
    raise AssertionError(f"기다렸지만 되지 않았다({timeout}초): {what} / 마지막 오류: {last}")


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=API, timeout=10.0) as client:
        yield client


@pytest.fixture
def owner() -> Iterator[psycopg.Connection[tuple[Any, ...]]]:
    with psycopg.connect(OWNER_URL, autocommit=True) as conn:
        yield conn


def company_id_of(owner: psycopg.Connection[tuple[Any, ...]], subdomain: str) -> int:
    """그 subdomain 의 회사 id(주인 연결로 읽는다 — 식별 열이라 박지 않는다). core 의 표는 회사 칸이 이 숫자다."""
    row = owner.execute("SELECT id FROM company WHERE subdomain = %s", [subdomain]).fetchone()
    assert row is not None, f"회사가 없다: {subdomain}"
    return int(row[0])


@pytest.fixture
def two_tenants(owner: psycopg.Connection[tuple[Any, ...]]) -> Iterator[tuple[str, str]]:
    """이 실행만의 회사 둘(쓸 수 있음)을 등록하고(관리자가 하는 일), 끝나면 이 실행이 만든 것만 지운다.
    돌려주는 것은 두 회사의 subdomain(= 토큰의 tenant_id) 글자다. 사업자번호도 subdomain 글자로 채운다(겹치지 않게)."""
    run = uuid.uuid4().hex[:8]
    a, b = f"it-{run}-a", f"it-{run}-b"
    owner.execute(
        "INSERT INTO company (name, business_licence_number, subdomain, is_active, created_at, updated_at) "
        "VALUES ('통합 가', %s, %s, true, now(), now()), ('통합 나', %s, %s, true, now(), now())",
        [a, a, b, b],
    )
    yield a, b
    # 회사에 매달린 행을 먼저(sites 의 외래 키는 PROTECT 다).
    owner.execute("DELETE FROM sites WHERE company_id IN (SELECT id FROM company WHERE subdomain = ANY(%s))", [[a, b]])
    owner.execute("DELETE FROM users WHERE company_id IN (SELECT id FROM company WHERE subdomain = ANY(%s))", [[a, b]])
    owner.execute("DELETE FROM company WHERE subdomain = ANY(%s)", [[a, b]])
