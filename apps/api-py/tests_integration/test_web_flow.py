"""이미지 안의 실제 웹 빌드(/app/web)를 떠 있는 api-py 가 같은 출처에서 낸다(sid:MARC-ENT-198, 밴드 SW1).

잰다: 화면 경로는 실제 index.html(no-cache) · 그 안의 해시 자산은 immutable·ACAO 없음·gzip 판 ·
상태 확인은 /api 아래만 · dist 의 맨 위 이름이 예약 자리(api·healthz·readyz)를 가리지 않음 · 소스맵 0 ·
데모 자료(sample/)는 실림.
DB 를 내린 동안 /readyz 가 200 이 아님은 test_flow.py 가 잰다.
"""

import re
from collections.abc import Iterator

import httpx
import pytest

from tests_integration.conftest import API, compose

ROOT = API.removesuffix("/api")
FOREVER = "max-age=315360000, public, immutable"


@pytest.fixture
def web() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=ROOT, timeout=10.0) as client:
        yield client


def in_image(*command: str) -> str:
    return compose("exec", "-T", "api-py", *command)


def test_a_screen_path_gets_the_built_index_html(web: httpx.Client) -> None:
    built = in_image("cat", "/app/web/index.html").encode()
    for path in ("/", "/greenwash", "/greenwash/runs/1/review"):
        response = web.get(path)
        assert (response.status_code, response.headers["cache-control"]) == (200, "no-cache"), path
        assert response.headers["content-type"] == "text/html; charset=utf-8", path
        assert response.content == built, path


def test_an_asset_named_in_the_index_is_immutable_and_gzipped(web: httpx.Client) -> None:
    index = web.get("/").text
    assets = re.findall(r'"(/assets/[^"]+\.js)"', index)
    assert assets, index[:300]  # 분모: index.html 이 자산을 부른다
    plain = web.get(assets[0], headers={"Accept-Encoding": "identity"})
    assert (plain.status_code, plain.headers["cache-control"]) == (200, FOREVER)
    assert "access-control-allow-origin" not in plain.headers
    zipped = web.get(assets[0], headers={"Accept-Encoding": "gzip"})
    assert zipped.headers.get("content-encoding") == "gzip"
    assert zipped.content == plain.content  # httpx 가 풀어 준 본문이 같다


def test_health_lives_under_api_only(web: httpx.Client, http: httpx.Client) -> None:
    assert http.get("/readyz").status_code == 200
    assert http.get("/healthz").json() == {"status": "ok"}
    for path in ("/readyz", "/healthz", "/api", "/api/no/such", "/assets/none.js"):
        response = web.get(path)
        assert (response.status_code, response.headers["content-type"]) == (404, "application/json"), path


def test_the_image_carries_the_dist_and_nothing_more() -> None:
    top = set(in_image("ls", "-1", "/app/web").split())
    assert {"index.html", "assets", "pdfjs", "sample"} <= top
    assert not {name for name in top if name in {"api", "healthz", "readyz"}}  # 예약 자리를 가리는 이름 0
    assert in_image("find", "/app/web", "-name", "*.map").strip() == ""  # 소스맵 0
    assert in_image("find", "/app", "-maxdepth", "3", "-name", "node_modules").strip() == ""
    assert in_image("sh", "-c", "command -v node || true").strip() == ""
