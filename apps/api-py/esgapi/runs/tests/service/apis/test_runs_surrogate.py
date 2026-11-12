# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""만들기(POST /runs)의 옵션에 짝 없는 서로게이트(JSON 이스케이프 `\\ud800`)가 든 몸 → 400
INVALID_OPTIONS(옵션을 적을 수 없다는 글)·행 0(밴드 LH1 — MARC-ISSUE-340). 업무 층.

  문서 있는 흐름·문서 없는 흐름 각각, 그리고 Idempotency-Key 를 붙인 같은 몸(본문 해시가 옵션 크기 셈보다 앞이다).
  분모: 정상 한글 옵션은 그대로 201.

BASE(1b7484bc)에서는 셋 다 500 이었다(옵션 크기 셈·본문 해시의 `encode("utf-8")` 이 UnicodeEncodeError).
★ 몸은 바이트로 보낸다: 파이썬 글자로는 짝 없는 서로게이트를 JSON 직렬화가 그대로 실을 수 없다(테스트 클라이언트가
  utf-8 로 바꾸다 터진다). 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

from typing import Any

import pytest
from django.test import Client

from esgapi.runs.models import RunRow
from esgapi.runs.service.actions import runs as actions
from esgapi.runs.tests.service.apis.test_runs import BARE, BareBinding, World, bare, document, error_of, world
from tests.support.http import login

pytestmark = pytest.mark.django_db

KEY = "5a1e0c1e-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID
LONE = '{"note":"\\ud800"}'  # 옵션 JSON — 짝 없는 높은 서로게이트 하나(이스케이프 꼴 그대로)

__all__ = ["bare", "world"]  # 고정 장치(test_runs.py 의 것)


def post(client: Client, raw: str, *, key: str | None = None) -> Any:
    client.raise_request_exception = False  # 500 도 응답으로 받는다(BASE 의 모양을 재려고)
    headers = {} if key is None else {"Idempotency-Key": key}
    return client.post("/api/runs", data=raw.encode("ascii"), content_type="application/json", headers=headers)


def with_document(world: World) -> str:
    return f'{{"module":"probe","documentId":{document(world.company_a)},"options":{LONE}}}'


def without_document() -> str:
    return f'{{"module":"probe","flowId":"{BARE.id}","options":{LONE}}}'


@pytest.mark.parametrize("key", [None, KEY], ids=["no-key", "idempotency-key"])
def test_a_lone_surrogate_in_options_is_400_with_a_document(client: Client, world: World, key: str | None) -> None:
    login(client)
    response = post(client, with_document(world), key=key)
    assert error_of(response) == (400, "INVALID_OPTIONS")
    assert response.json()["error"]["message"] == actions.options_unencodable()
    assert RunRow.unscoped.count() == 0


@pytest.mark.parametrize("key", [None, KEY], ids=["no-key", "idempotency-key"])
def test_a_lone_surrogate_in_options_is_400_without_a_document(
    client: Client, bare: BareBinding, key: str | None
) -> None:
    login(client)
    response = post(client, without_document(), key=key)
    assert error_of(response) == (400, "INVALID_OPTIONS")
    assert response.json()["error"]["message"] == actions.options_unencodable()
    assert (RunRow.unscoped.count(), bare.companies) == (0, [])


@pytest.mark.parametrize("key", [None, KEY], ids=["no-key", "idempotency-key"])
def test_ordinary_korean_options_still_create_a_run(client: Client, world: World, key: str | None) -> None:
    """분모: 서로게이트가 아닌 한글(이스케이프 꼴과 날 글자 둘)은 그대로 201."""
    login(client)
    raw = f'{{"module":"probe","documentId":{document(world.company_a)},"options":{{"note":"\\ud55c글"}}}}'
    response = client.post(
        "/api/runs",
        data=raw.encode("utf-8"),
        content_type="application/json",
        headers={} if key is None else {"Idempotency-Key": key},
    )
    assert response.status_code == 201, response.content.decode()
    assert RunRow.unscoped.get().options == {"note": "한글"}
