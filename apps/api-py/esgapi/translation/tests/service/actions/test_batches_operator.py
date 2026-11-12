# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""운영 관리자가 보는 영문번역 묶음 목록의 companyName(밴드 TRC1 §3-2-4 — MARC-ENT-374·380·409). 업무 층.

운영 관리자에게는 회사 행이 없다 — 목록의 회사 이름은 company_of 가 고른 작업 회사(하나뿐인 활성 회사)의 이름이다.
작업 회사를 tenant-b(「나 회사」)로 남겨 첫 회사·토큰 회사로 읽는 잘못과 가른다. 회사 둘이면 고르지 못한다(400 —
그대로, test_operator_company 의 고리).
★ 실행 행은 seed(apps.get_model)로 심는다 — runs.models·organization.models 를 import 하지 않는다(계약 나). 회사 행은
SQL 로 지운다. 이름·문서는 지어낸 것이다.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.test import Client, override_settings

from esgapi.translation.tests.service import seed
from esgapi.user.service.services.user import create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair

pytestmark = pytest.mark.django_db

PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


def operator_headers(client: Client) -> dict[str, Any]:
    """운영 관리자를 만들고 비밀번호를 한 번 바꿔(is_initial 끔) Bearer 머리."""
    created = create_operator(username="ops", name="가상 운영자", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    first = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)
    changed = client.post(
        "/api/users/me/password",
        data={"currentPassword": PASSWORD, "newPassword": CHANGED},
        content_type="application/json",
        **bearer(first["access"]),
    )
    assert changed.status_code == 200, changed.content.decode()
    return bearer(str(changed.json()["access"]))


def test_the_operators_list_carries_the_work_companys_name(client: Client, companies: tuple[int, int]) -> None:
    a, b = companies
    headers = operator_headers(client)
    assert client.get("/api/translation/batches", **headers).status_code == 400  # 분모: 회사 둘이면 고르지 못함
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM company WHERE id = %s", [a])  # 남는 회사 = tenant-b 하나
    doc = seed.document(b)
    seed.run(b, doc, "story")
    listed = client.get("/api/translation/batches", **headers)
    assert listed.status_code == 200, listed.content.decode()
    body = listed.json()
    assert (body["companyName"], body["count"]) == ("나 회사", 1)
    empty = client.get(f"/api/translation/batches?documentId={doc + 1000}", **headers).json()
    assert (empty["companyName"], empty["count"]) == ("나 회사", 0)  # 빈 쪽에도
