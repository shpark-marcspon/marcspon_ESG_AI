"""refresh 의 잇기(rotate)·재사용 탐지·로그아웃·계보 끊기(K2a). 보안 층.

연결은 이 층 그대로다(앱 역할 esg_app, RLS 없음, 진짜 커밋, 직렬). user_refresh_tokens 의 행(used_at·revoked_at)은 주인
연결(owner)로 센다 — 재사용 탐지의 계보 끊기는 「444 로 답했는데도 커밋된」 쓰기다(K-B4). 답만 보면 그것을 모른다.
계보(fam)는 refresh 토큰의 주장에서 서명 확인 없이 읽는다(테스트가 자기가 받은 토큰을 읽는 것뿐이다).
해시는 MD5 다(conftest 의 fast_hasher).

무효 조건: 동시 refresh 는 스레드 둘 + 연결 둘로 만든 경합이다(gunicorn 일꾼 둘의 요청으로 잰 것이 아니다).
"""

import threading
from collections.abc import Callable
from datetime import datetime
from io import StringIO
from typing import Any, Final
from uuid import UUID

import jwt
import psycopg
import pytest
from django.core.management import call_command
from django.db import connections
from django.test import Client

from esgapi.user.models import RefreshToken
from esgapi.user.service.selectors import user as user_selectors
from tests.security.test_login import OTHER_PASSWORD, PASSWORD, answer, customer, operator, try_login
from tests.support.http import bearer, bearer_pair

pytestmark = [pytest.mark.security, pytest.mark.usefixtures("fast_hasher")]

Owner = psycopg.Connection[tuple[Any, ...]]
REJECTED: Final = (444, "TOKEN_NOT_VALID")


def family_of(refresh: str) -> UUID:
    claims: dict[str, Any] = jwt.decode(refresh, options={"verify_signature": False})
    return UUID(str(claims["fam"]))


def jti_of(refresh: str) -> UUID:
    claims: dict[str, Any] = jwt.decode(refresh, options={"verify_signature": False})
    return UUID(str(claims["jti"]))


def rows_of_family(owner: Owner, family: UUID) -> list[tuple[UUID, datetime | None, datetime | None]]:
    """주인 역할이 본 그 계보의 행 전부: (jti, used_at, revoked_at), 넣은 차례."""
    return [
        (UUID(str(jti)), used_at, revoked_at)
        for jti, used_at, revoked_at in owner.execute(
            "SELECT jti, used_at, revoked_at FROM user_refresh_tokens WHERE family = %s ORDER BY id", [family]
        )
    ]


def revoked_by_user(owner: Owner, user_id: int) -> list[bool]:
    """주인 역할이 본 그 사용자의 행마다 끊겼는가(넣은 차례)."""
    return [
        bool(revoked)
        for (revoked,) in owner.execute(
            "SELECT revoked_at IS NOT NULL FROM user_refresh_tokens WHERE user_id = %s ORDER BY id", [user_id]
        )
    ]


def refresh(client: Client, token: str) -> Any:
    return client.post("/api/auth/refresh", data={"refresh": token}, content_type="application/json")


def kim_pair(client: Client) -> dict[str, Any]:
    return bearer_pair(client, username="kim", password=PASSWORD, company_subdomain="tenant-a")


def test_rotate_then_the_old_refresh_is_rejected(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    customer(companies[0])
    old = kim_pair(client)["refresh"]
    rotated = refresh(client, old)
    assert rotated.status_code == 200, rotated.content.decode()
    new = rotated.json()["refresh"]
    assert family_of(new) == family_of(old)  # 같은 계보를 잇는다
    rows = rows_of_family(owner, family_of(old))
    assert [jti for jti, _, _ in rows] == [jti_of(old), jti_of(new)]  # 분모: 행 둘
    assert [(used is not None, revoked is not None) for _, used, revoked in rows] == [(True, False), (False, False)]
    assert answer(refresh(client, old)) == REJECTED


def test_reusing_a_refresh_revokes_the_whole_family(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """이미 쓴 refresh 를 다시 내면 444 이고 그 계보의 행 전부에 revoked_at 이 적혀 커밋된다(오류로 답했는데도).
    다른 계보(다른 기기의 로그인)는 그대로다."""
    customer(companies[0])
    old = kim_pair(client)["refresh"]
    other = kim_pair(Client())["refresh"]
    new = refresh(client, old).json()["refresh"]
    assert answer(refresh(client, old)) == REJECTED  # 재사용

    rows = rows_of_family(owner, family_of(old))
    assert len(rows) == 2  # 분모: 옛 행과 rotate 로 넣은 행
    assert all(revoked is not None for _, _, revoked in rows)
    assert [revoked for _, _, revoked in rows_of_family(owner, family_of(other))] == [None]
    assert answer(refresh(client, new)) == REJECTED  # 이은 토큰도 죽었다
    assert refresh(client, other).status_code == 200  # 분모: 다른 계보는 산다


def test_two_concurrent_refreshes_issue_one_pair(
    owner: Owner, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """같은 refresh 둘이 겹치면 짝은 하나만 나간다(행 잠금). 진 쪽은 재사용으로 보아 계보를 끊으므로(처분 B3)
    이긴 쪽이 받은 새 refresh 도 444 다. 장벽: 둘 다 자기 블록 안에서 행 잠금 앞에 닿아야 지나간다."""
    customer(companies[0])
    token = kim_pair(Client())["refresh"]
    barrier = threading.Barrier(2)
    original: Callable[[UUID], RefreshToken | None] = user_selectors.lock_refresh

    def lock_after_both_arrive(jti: UUID) -> RefreshToken | None:
        barrier.wait(timeout=10)
        return original(jti)

    monkeypatch.setattr(user_selectors, "lock_refresh", lock_after_both_arrive)

    responses: list[Any] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def send() -> None:
        try:
            response = refresh(Client(), token)
            with lock:
                responses.append(response)
        except BaseException as err:
            with lock:
                errors.append(err)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=send) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]

    assert errors == []
    winners = [response for response in responses if response.status_code == 200]
    losers = [answer(response) for response in responses if response.status_code != 200]
    assert (len(winners), losers) == (1, [REJECTED])
    rows = rows_of_family(owner, family_of(token))
    assert len(rows) == 2  # 분모: 처음 행과 이긴 쪽이 넣은 행 하나(짝 하나)
    assert all(revoked is not None for _, _, revoked in rows)
    monkeypatch.setattr(user_selectors, "lock_refresh", original)  # 장벽을 걷는다(아래는 혼자 보내는 요청 하나)
    assert answer(refresh(Client(), winners[0].json()["refresh"])) == REJECTED


def test_an_operator_refresh_reads_the_operator(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """운영 관리자의 refresh 는 회사가 없고(company_id null) 운영 관리자의 입구로 다시 읽는다. 같은 username 의
    고객사 사용자가 있어도 그 행으로 건너가지 않는다."""
    customer(companies[0], "kim", OTHER_PASSWORD)  # 고객사를 먼저(UA1 — 겹침 막기는 고객사 만들기 쪽뿐)
    ops = operator("kim", PASSWORD)
    pair = bearer_pair(client, username="kim", password=PASSWORD, company_subdomain=None)
    claims: dict[str, Any] = jwt.decode(pair["refresh"], options={"verify_signature": False})
    assert (claims["sub"], claims["company_id"]) == (str(ops), None)
    rotated = refresh(client, pair["refresh"])
    assert rotated.status_code == 200, rotated.content.decode()
    assert rotated.json()["kind"] == "admin"
    me = client.get("/api/users/me", **bearer(rotated.json()["access"])).json()
    assert (me["id"], me["kind"], me["companyId"]) == (ops, "admin", None)
    owned = owner.execute("SELECT DISTINCT user_id FROM user_refresh_tokens").fetchall()
    assert owned == [(ops,)]  # 행은 전부 운영 관리자의 것


def test_revoke_then_refresh_is_444(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    customer(companies[0])
    token = kim_pair(client)["refresh"]
    assert rows_of_family(owner, family_of(token))[0][2] is None  # 분모: 끊기 전
    assert client.post("/api/auth/revoke", data={"refresh": token}, content_type="application/json").status_code == 204
    assert all(revoked is not None for _, _, revoked in rows_of_family(owner, family_of(token)))
    assert answer(refresh(client, token)) == REJECTED


def test_a_password_change_revokes_other_families(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """기기 둘(계보 둘)에서 로그인한 뒤 한 기기에서 비밀번호를 바꾸면 두 계보가 다 끊기고 새 계보 하나만 산다."""
    kim = customer(companies[0])
    first = kim_pair(client)
    second = kim_pair(Client())
    assert revoked_by_user(owner, kim) == [False, False]  # 분모: 계보 둘, 산 채
    changed = client.post(
        "/api/users/me/password",
        data={"currentPassword": PASSWORD, "newPassword": OTHER_PASSWORD},
        content_type="application/json",
        **bearer(first["access"]),
    )
    assert changed.status_code == 200, changed.content.decode()
    assert revoked_by_user(owner, kim) == [True, True, False]  # 옛 둘 끊김, 새 짝의 행 하나
    assert answer(refresh(Client(), second["refresh"])) == REJECTED
    assert answer(refresh(client, first["refresh"])) == REJECTED
    assert refresh(client, changed.json()["refresh"]).status_code == 200


def test_a_reset_by_the_command_revokes_the_users_families_and_is_committed(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """부트스트랩 명령 reset_password: 그 사용자의 계보 전부를 끊고 is_initial 을 켜고 셈을 0 으로 — 주인 연결이 본다
    (커밋됐다). 남의 사용자(B 의 같은 username)의 행은 그대로다."""
    a, b = companies
    kim = customer(a)
    other = customer(b)
    pairs = [kim_pair(client), kim_pair(Client())]
    other_pair = bearer_pair(Client(), username="kim", password=PASSWORD, company_subdomain="tenant-b")
    assert answer(try_login(client, "kim", "x", "tenant-a")) == (401, "INVALID_CREDENTIALS")  # 셈 1
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [kim])  # 바꾼 뒤인 셈
    before = owner.execute("SELECT is_initial, login_failed_count FROM users WHERE id = %s", [kim]).fetchone()
    assert before == (False, 1)  # 분모: 초기화 앞
    assert revoked_by_user(owner, kim) == [False, False]

    out = StringIO()
    call_command(
        "reset_password",
        "--company",
        "tenant-a",
        "--username",
        "kim",
        "--password-stdin",
        stdin=StringIO(OTHER_PASSWORD + "\n"),
        stdout=out,
    )
    assert out.getvalue().split() == [str(kim), "service", "tenant-a"]

    assert revoked_by_user(owner, kim) == [True, True]
    assert owner.execute("SELECT is_initial, login_failed_count FROM users WHERE id = %s", [kim]).fetchone() == (
        True,
        0,
    )
    assert revoked_by_user(owner, other) == [False]  # B 의 kim 은 그대로
    for pair in pairs:
        assert answer(refresh(Client(), pair["refresh"])) == REJECTED
    assert refresh(Client(), other_pair["refresh"]).status_code == 200
    # 새 비밀번호로 들어가고 다시 바꿔야 한다
    fresh = bearer_pair(Client(), username="kim", password=OTHER_PASSWORD, company_subdomain="tenant-a")
    assert fresh["isInitial"] is True
