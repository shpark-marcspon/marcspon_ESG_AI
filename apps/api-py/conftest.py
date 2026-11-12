"""세 층이 다 읽는 뿌리 고정물. 모듈들이 같이 쓴다. 준비물 자체(키 쌍·토큰·login)는 tests/support/ 에 있다.

pytest 설정이 하나(pyproject.toml)라 보안 층(tests/security)도 이 파일을 읽는다. 다만 보안 층은 자기
conftest(tests/security/conftest.py)에서 같은 이름의 고정물(tenants, client)을 덮어쓴다: 거기의 tenants 는
ORM 이 아니라 주인 역할의 연결로 심는다(Django 의 연결이 앱 역할이라 tenants 표에 쓸 권한이 없다).

    client           pytest-django 가 준다(Django 의 테스트 클라이언트). 여기 적지 않아도 인자 이름으로 받는다.
    tenants          회사 둘(tenant-a, tenant-b)을 심는다.
    companies        tenants 의 두 회사의 숫자 id (A, B). 회사 칸(company_id)에 넣을 값은 여기서 받는다
                     (박아 두지 않는다).
    blocked_network  ★ 순수 층의 테스트 전부에서 소켓을 막는다(autouse). 아래.

★ 업무 층의 연결은 주인 역할이다. 자료를 심을 때 회사를 늘 명시한다
  (회사 범위 표는 <Row>.for_company·unscoped 로 심는다).

★ 소켓 막기(blocked_network). 순수 층의 테스트는 네트워크로 나가지 않는다는 것을 말이 아니라 기계로 지킨다:
  이름 풀이(getaddrinfo)와 연결(connect·connect_ex)을 시도하면 NetworkBlockedError 가 나고, 시도한 주소가
  `blocked_network` 에 적힌다. PY3 에서는 esgapi/core/tests 에만 걸려 있었다. 여기로 올려 모듈 전부에 건다
  (어느 모듈의 순수 테스트가 공급사 SDK 를 실수로 불러도 요청이 나가지 않는다).
  걸지 않는 것 둘: `django_db` 표시(업무 층. DB 연결이 소켓이다)와 `security` 표시(보안 층. 같은 까닭).
  무효 조건:
    - 통합 테스트(tests_integration)는 이 파일을 읽지 않는다(scripts/test-integration.sh 가
      -c tests_integration/pytest.ini 로 돌려 rootdir 가 그 폴더다). 떠 있는 서버를 httpx 로 부르는 층이다.
    - 업무·보안 층의 테스트가 공급사를 부르는 것은 이 고정물이 못 막는다(그 층은 모의 공급사만 쓴다는 규율로 지킨다).
    - 막는 것은 파이썬의 socket 모듈을 거치는 길이다. C 확장이 직접 여는 소켓과 하위 프로세스는 못 막는다.
  ★ 안쪽 함수의 이름(blocked_connect·blocked_getaddrinfo)을 바꾸지 않는다:
    esgapi/core/tests/test_llm_gemini.py 의 문지기가 `socket.getaddrinfo.__name__` 을 보고 진짜 SDK 클라이언트를
    부를지 정한다. 이름이 바뀌면 그 테스트가 멈춘다(멈추는 쪽이 안전한 쪽이다).
"""

import socket
from typing import Any, cast

import pytest


class NetworkBlockedError(ConnectionError):
    """테스트가 네트워크로 나가려 했다."""


@pytest.fixture(autouse=True)
def blocked_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """막힌 시도의 주소 목록을 돌려준다(시도가 없었으면 빈 목록)."""
    attempts: list[object] = []
    node = cast("pytest.Item", getattr(request, "node"))  # noqa: B009  (request.node 의 타입이 알려져 있지 않다)
    if node.get_closest_marker("django_db") is not None or node.get_closest_marker("security") is not None:
        return attempts

    def blocked_connect(self: socket.socket, address: object, *args: Any) -> None:
        attempts.append(address)
        raise NetworkBlockedError(f"테스트에서 소켓 연결을 시도했다: {address}")

    def blocked_getaddrinfo(host: object, *args: Any, **kwargs: Any) -> list[Any]:
        attempts.append(host)
        raise NetworkBlockedError(f"테스트에서 이름 풀이를 시도했다: {host}")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked_connect)
    monkeypatch.setattr(socket, "getaddrinfo", blocked_getaddrinfo)
    return attempts


@pytest.fixture
def tenants(db: None) -> None:
    """회사 둘을 등록한다(마크스폰 관리자가 하는 일. 앱에는 이 길이 없다)."""
    from esgapi.organization.models import Company

    Company.register(name="가 회사", business_licence_number="111-11-11111", subdomain="tenant-a")
    Company.register(name="나 회사", business_licence_number="222-22-22222", subdomain="tenant-b")


@pytest.fixture
def companies(tenants: None) -> tuple[int, int]:
    """tenants 가 심은 두 회사의 id: (tenant-a 의 것, tenant-b 의 것)."""
    from esgapi.organization.models import Company

    a, b = Company.by_subdomain("tenant-a"), Company.by_subdomain("tenant-b")
    assert a is not None and b is not None
    return a.pk, b.pk
