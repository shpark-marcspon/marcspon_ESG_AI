"""떠 있는 api-py 컨테이너에 호스트에서 요청을 보낸다: 교환 → /me → /sites 한 줄기와, 컨테이너의 성질.

돌리기:  (저장소 맨 위에서) docker compose up -d --build --wait  뒤에  apps/api-py/scripts/test-integration.sh
전제: 컨테이너의 EDK_JWT_PUBLIC_KEY 가 apps/api-py/.dev-keys 의 키 쌍의 공개키일 것(스크립트가 맞춰 띄운다).
"""

from typing import Any

import httpx
import psycopg
import pytest
from dev_edk import make_token  # apps/api-py/scripts/dev_edk.py (EDK 인 척 토큰을 서명한다)

from tests_integration.conftest import API, AUDIENCE, ISSUER, PY_DB, compose, container_state, wait_for

Owner = psycopg.Connection[tuple[Any, ...]]


def edk_token(*, tenant: str, sub: str, role: str) -> str:
    return make_token(tenant=tenant, sub=sub, role=role, name="통합 테스트", ttl=120, audience=AUDIENCE, issuer=ISSUER)


def exchange(http: httpx.Client, *, tenant: str, sub: str, role: str = "editor") -> dict[str, str]:
    """교환하고, 이후 요청에 실을 Cookie 헤더를 돌려준다."""
    token = edk_token(tenant=tenant, sub=sub, role=role)
    response = http.post("/auth/exchange", json={"token": token})
    if response.status_code == 401 and response.json()["error"]["code"] == "BAD_SIGNATURE":
        raise AssertionError(
            "컨테이너가 다른 공개키로 떠 있다. EDK_JWT_PUBLIC_KEY 를 scripts/dev_edk.py public-key 의 출력으로 주고 "
            "다시 띄운다(scripts/verify.sh 와 apps/api-py/scripts/section4.sh 는 그렇게 한다)."
        )
    assert response.status_code == 200, response.text
    set_cookie = response.headers["set-cookie"]
    assert all(attribute in set_cookie for attribute in ("HttpOnly", "Secure", "SameSite=Lax"))
    # Secure 쿠키라 httpx 는 http:// 주소로 스스로 보내지 않는다. 테스트가 헤더에 직접 싣는다.
    return {"Cookie": f"esg_session={response.cookies['esg_session']}"}


def test_ready_and_alive(http: httpx.Client) -> None:
    assert http.get("/healthz").json() == {"status": "ok"}
    ready = http.get("/readyz")
    assert (ready.status_code, ready.json()) == (200, {"status": "ready", "checks": {"db": "ok"}})


def test_migrate_py_ran_once_and_succeeded() -> None:
    assert container_state("migrate-py") == ("exited", 0)


@pytest.mark.parametrize("service", ["worker-py", "parser"])
def test_the_worker_and_the_parser_run_as_non_root(service: str) -> None:
    """worker-py·parser 도 루트가 아닌 사용자(uid 10001 의 app, docker/*.Dockerfile)로 돈다.
    (TS 통합 tests/integration/flow.test.ts 의 「컨테이너가 루트가 아닌 사용자로 돈다」를 옮김. 밴드 T1c)"""
    assert compose("exec", "-T", service, "id", "-u").strip() == "10001"


def test_container_runs_as_non_root_and_has_no_owner_address() -> None:
    assert compose("exec", "-T", "api-py", "id", "-u").strip() == "10001"
    env = compose("exec", "-T", "api-py", "env")
    assert "DATABASE_URL_PY=" in env
    assert "OWNER" not in env  # 주인 역할의 주소·비밀번호가 요청을 처리하는 컨테이너에 없다


def test_exchange_then_me_then_sites(http: httpx.Client, owner: Owner, two_tenants: tuple[str, str]) -> None:
    tenant_a, tenant_b = two_tenants
    alice = exchange(http, tenant=tenant_a, sub="it-alice")
    bob = exchange(http, tenant=tenant_b, sub="it-bob")

    me = http.get("/me", headers=alice).json()
    assert (me["tenantId"], me["role"]) == (tenant_a, "editor")

    assert http.post("/sites", headers=alice, json={"name": "A 본사"}).status_code == 201
    assert http.post("/sites", headers=alice, json={"name": "A 공장", "externalId": "edk-1"}).status_code == 201
    assert http.post("/sites", headers=bob, json={"name": "B 본사"}).status_code == 201

    assert [s["name"] for s in http.get("/sites", headers=alice).json()["sites"]] == ["A 본사", "A 공장"]
    assert [s["name"] for s in http.get("/sites", headers=bob).json()["sites"]] == ["B 본사"]
    # 분모: 실제로는 두 테넌트의 행이 다 있다.
    rows = owner.execute(
        "SELECT c.subdomain, count(*) FROM sites s JOIN company c ON c.id = s.company_id "
        "WHERE c.subdomain = ANY(%s) GROUP BY 1 ORDER BY 1",
        [[tenant_a, tenant_b]],
    ).fetchall()
    assert rows == [(tenant_a, 2), (tenant_b, 1)]

    # 세션이 없으면 401. 일꾼 프로세스가 둘이고 연결을 다시 쓰므로, 여러 번 물어 앞 요청의 테넌트가 남지 않았는지 본다.
    for _ in range(8):
        assert http.get("/sites").status_code == 401
        assert len(http.get("/sites", headers=bob).json()["sites"]) == 1
        assert len(http.get("/sites", headers=alice).json()["sites"]) == 2

    # 열람자 세션도 고객사 사용자라 만든다(K2a 가2 — 역할 둘). 등록되지 않은 테넌트는 교환부터 거절된다.
    viewer = exchange(http, tenant=tenant_a, sub="it-viewer", role="viewer")
    assert http.post("/sites", headers=viewer, json={"name": "열람자도 만듦"}).status_code == 201
    unknown = http.post("/auth/exchange", json={"token": edk_token(tenant="it-nobody", sub="x", role="admin")})
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (403, "UNKNOWN_TENANT")

    # 컨테이너는 앱 역할로만 DB 에 붙어 있다.
    users = owner.execute(
        "SELECT DISTINCT usename FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()", [PY_DB]
    ).fetchall()
    assert users == [("esg_app",)]


def test_readyz_is_503_while_the_db_is_down_and_recovers(http: httpx.Client) -> None:
    # 요청마다의 트랜잭션이 없어 미들웨어는 DB 에 닿지 않는다: DB 를 쓰는 경로만 경로 안에서 503 이고, DB 에 닿기 전에
    # 끝나는 응답(세션 없는 401, DB 를 안 쓰는 /me)은 DB 가 살아 있을 때와 같다.
    # 주인 연결은 짧게 두 번 맺는다(고정물의 연결은 postgres 재시작 너머로 살아남지 못한다).
    import uuid

    from tests_integration.conftest import OWNER_URL

    tenant = f"it-{uuid.uuid4().hex[:8]}-down"
    with psycopg.connect(OWNER_URL, autocommit=True) as owner:
        owner.execute(
            "INSERT INTO company (name, business_licence_number, subdomain, is_active, created_at, updated_at) "
            "VALUES ('통합 장애', %s, %s, true, now(), now())",
            [tenant, tenant],
        )
    try:
        cookie = exchange(http, tenant=tenant, sub="it-down")
        compose("stop", "postgres")
        try:
            wait_for("/readyz 가 503 이 되기", lambda: http.get("/readyz").status_code == 503)
            assert http.get("/readyz").json()["status"] == "not_ready"
            # 접두 없는 /readyz 는 상태 확인이 아니다(예약어 404 — 화면의 index.html 200 이 「준비됨」이면 안 된다)
            bare = httpx.get(API.removesuffix("/api") + "/readyz", timeout=10.0)
            assert bare.status_code != 200
            assert http.get("/healthz").status_code == 200  # 살아 있음은 DB 와 무관하다
            down = http.get("/sites", headers=cookie)
            assert (down.status_code, down.json()["error"]["code"]) == (503, "UNAVAILABLE")
            assert http.get("/me", headers=cookie).status_code == 200  # DB 를 쓰지 않는다
            assert http.get("/sites").status_code == 401  # 세션 없음: 인증이 DB 앞에서 끊는다
        finally:
            compose("start", "postgres")
            wait_for("/readyz 가 다시 200 이 되기", lambda: http.get("/readyz").status_code == 200)
    finally:
        with psycopg.connect(OWNER_URL, autocommit=True) as owner:
            owner.execute(
                "DELETE FROM users WHERE company_id IN (SELECT id FROM company WHERE subdomain = %s)", [tenant]
            )
            owner.execute("DELETE FROM company WHERE subdomain = %s", [tenant])


def test_sigterm_stops_gracefully(http: httpx.Client) -> None:
    """SIGTERM 에 gunicorn 이 스스로 내려간다(종료 코드 0). 강제 종료(SIGKILL)면 137 이다."""
    compose("stop", "api-py")
    try:
        assert container_state("api-py") == ("exited", 0)
    finally:
        # up 이 아니라 start: 같은 컨테이너를 그대로 다시 켠다(up 은 설정이 달라 보이면 새로 만든다).
        compose("start", "api-py")
        wait_for("/readyz 가 다시 200 이 되기", lambda: http.get("/readyz").status_code == 200)
