"""Django 의 테스트 클라이언트로 요청을 보내는 도구. 업무 층과 보안 층이 같이 쓴다."""

import uuid
from typing import Any

from django.test import Client

from tests.support import tokens

# customer_bearer 가 쓰는 비밀번호 둘(검사기를 지나는 값)
FIRST_PASSWORD = "Blue-Harbor-7310"
CHANGED_PASSWORD = "Green-Valley-4821"


def login(client: Client, **claim_overrides: Any) -> dict[str, Any]:
    """EDK 토큰을 만들어 교환한다. client 가 세션 쿠키를 갖게 된다."""
    response = client.post(
        "/api/auth/exchange", data={"token": tokens.edk_token(**claim_overrides)}, content_type="application/json"
    )
    assert response.status_code == 200, response.content.decode()
    body: dict[str, Any] = response.json()
    return body


def bearer_pair(client: Client, *, username: str, password: str, company_subdomain: str | None) -> dict[str, Any]:
    """/api/auth/login 으로 토큰 짝을 받는다(본문 그대로). company_subdomain 이 None 이면 운영 관리자 로그인."""
    payload: dict[str, Any] = {"username": username, "password": password}
    if company_subdomain is not None:
        payload["companySubdomain"] = company_subdomain
    response = client.post("/api/auth/login", data=payload, content_type="application/json")
    assert response.status_code == 200, response.content.decode()
    body: dict[str, Any] = response.json()
    return body


def bearer(access: str) -> dict[str, Any]:
    """테스트 클라이언트의 get·post 에 `**` 로 넘길 Authorization 머리(extra).
    값이 Any 인 까닭: str 이면 pyright 가 follow·secure·headers 인자와 맞춰 본다."""
    return {"HTTP_AUTHORIZATION": f"Bearer {access}"}


def customer_bearer(client: Client, *, company_id: int, subdomain: str) -> str:
    """고객사 사용자를 만들고 비밀번호를 한 번 바꿔(is_initial 끔) 새 access 를 돌려준다.
    core 의 테스트가 user 를 import 하지 않고 쓰는 자리(계약 가 — tests/ 는 계약 밖).
    import 는 함수 안에 둔다: 이 파일을 들이는 순수 층에 user 의 모델을 끌어오지 않는다."""
    from esgapi.user.service.services.user import create_customer_user
    from esgapi.user.service.utils.login import UserCreated

    username = f"bearer-{uuid.uuid4().hex[:12]}"
    created = create_customer_user(
        actor_kind="admin", company_id=company_id, username=username, name="김담당", password=FIRST_PASSWORD
    )
    assert isinstance(created, UserCreated), created
    first = bearer_pair(client, username=username, password=FIRST_PASSWORD, company_subdomain=subdomain)
    changed = client.post(
        "/api/users/me/password",
        data={"currentPassword": FIRST_PASSWORD, "newPassword": CHANGED_PASSWORD},
        content_type="application/json",
        **bearer(first["access"]),
    )
    assert changed.status_code == 200, changed.content.decode()
    pair: dict[str, Any] = changed.json()
    assert pair["isInitial"] is False
    access: str = pair["access"]
    return access
