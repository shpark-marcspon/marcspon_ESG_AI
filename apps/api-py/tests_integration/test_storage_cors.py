"""저장소(Versity)의 버킷 CORS 를 떠 있는 컨테이너에 호스트에서 잰다. 규칙은 compose 의 storage-cors 가 썼다.

    허락 출처(웹 출처 넷): preflight(OPTIONS, PUT) 200 + 그 출처의 ACAO → 서명한 PUT 200 + ACAO·Expose ETag
    목록 밖 출처: preflight 에 ACAO 없음, 서명한 PUT 에도 ACAO 없음

허락 출처는 compose 가 치환한 storage-cors 의 STORAGE_CORS_ORIGINS 값 하나만 꺼낸다(compose config 의 나머지에는
비밀이 있어 버린다). 서명한 주소는 컨테이너 **안에서** 제품 코드의 presign_upload 로 만든다(test_upload_flow.py 의 꼴).
이 파일은 버킷 규칙을 읽기만 한다(preflight·PUT). 규칙을 고치거나 지우지 않는다.

★ 무효 조건:
  - 저장소는 Versity Gateway v1.8.0 이다. 실제 S3 의 판정은 terraform 시험(envs/practice/tests/storage.tftest.hcl)의
    몫이고 여기서 재지 않는다.
  - 브라우저만 막힌다: 목록 밖 출처의 PUT 도 서명만 맞으면 저장소는 받는다.
    그래서 목록 밖은 「ACAO 없음」까지만 단언한다.
  - 올린 객체(it-cors/…)는 저장소에 남는다(`docker compose down -v` 가 볼륨째 지운다).
"""

import json
import subprocess
import uuid

import httpx
import pytest

from tests_integration.conftest import REPO_ROOT, compose

OTHER = "http://localhost:15999"
BODY = b"cors-check-bytes"  # 지은 바이트

# 컨테이너 안에서 도는 코드. 제품 코드만 import 한다. 인자는 키들, 마지막 줄에 주소 목록(JSON).
INSIDE = """
import json, sys
import django
django.setup()
from esgapi.core.service.services import documents as services

storage = services.default_storage()
size = int(sys.argv[1])
print(json.dumps([storage.presign_upload(key, content_length=size).url for key in sys.argv[2:]]))
"""


def allowed_origins() -> list[str]:
    environment = json.loads(compose("config", "--format", "json"))["services"]["storage-cors"]["environment"]
    return environment["STORAGE_CORS_ORIGINS"].split(",")


def presign(count: int) -> list[str]:
    keys = [f"it-cors/{uuid.uuid4()}.bin" for _ in range(count)]
    done = subprocess.run(
        ["docker", "compose", "exec", "-T", "api-py", "python", "-c", INSIDE, str(len(BODY)), *keys],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, f"컨테이너 안의 코드가 {done.returncode} 로 끝났다:\n{done.stderr}"
    urls: list[str] = json.loads(done.stdout.splitlines()[-1])
    assert len(urls) == count
    return urls


@pytest.fixture(scope="module")
def origins_and_urls() -> tuple[list[str], list[str]]:
    origins = allowed_origins()
    return origins, presign(len(origins) + 1)


def preflight(url: str, origin: str) -> httpx.Response:
    return httpx.options(
        url,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=10.0,
    )


def signed_put(url: str, origin: str) -> httpx.Response:
    return httpx.put(
        url, content=BODY, headers={"Origin": origin, "Content-Type": "application/octet-stream"}, timeout=10.0
    )


def test_the_web_origins_get_a_preflight_and_a_signed_put(origins_and_urls: tuple[list[str], list[str]]) -> None:
    origins, urls = origins_and_urls
    assert len(origins) == 4, origins
    for origin, url in zip(origins, urls[: len(origins)], strict=True):
        before = preflight(url, origin)
        assert before.status_code == 200, (origin, before.status_code, before.text[:200])
        assert before.headers.get("access-control-allow-origin") == origin
        assert "PUT" in before.headers.get("access-control-allow-methods", "")
        put = signed_put(url, origin)
        assert put.status_code == 200, (origin, put.status_code, put.text[:200])
        assert put.headers.get("access-control-allow-origin") == origin
        assert "etag" in put.headers.get("access-control-expose-headers", "").lower()


def test_another_origin_gets_no_cors_headers(origins_and_urls: tuple[list[str], list[str]]) -> None:
    """목록 밖 출처에는 CORS 헤더가 없다.

    PUT 의 상태는 단언하지 않는다(서명이 맞으면 저장소는 받는다 — 브라우저만 막힌다).
    """
    origins, urls = origins_and_urls
    assert OTHER not in origins
    url = urls[-1]
    before = preflight(url, OTHER)
    assert "access-control-allow-origin" not in before.headers, before.headers
    assert before.status_code == 403, before.status_code
    put = signed_put(url, OTHER)
    assert "access-control-allow-origin" not in put.headers, put.headers
