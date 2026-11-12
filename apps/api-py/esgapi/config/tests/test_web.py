"""웹 빌드의 정적 서빙과 SPA fallback(config/web.py, settings 의 WHITENOISE_*, urls.py 의 마지막 자리).

순수 층: DB 없음. 임시 dist(tmp_path)를 override_settings 로 WHITENOISE_ROOT 에 건다. 시험 클라이언트는 첫 요청 때
미들웨어 사슬을 새로 지으므로(django.test.client.ClientHandler) whitenoise 가 그 자리를 그때 훑는다 —
클라이언트는 설정을 바꾼 뒤에 만든다.
"""

import re
import subprocess
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest
from django.test import Client, override_settings

from esgapi.config.web import (
    IMMUTABLE_FILE_TEST,
    WebOff,
    WebOn,
    WebRefused,
    place_of,
    read_web_dist,
)

API_PY_DIR = Path(__file__).resolve().parents[3]
WEB_DIST = API_PY_DIR.parent / "web" / "dist"
INDEX = b"<!doctype html><title>esg</title><script type=module src=/assets/index-AbCdEf12.js></script>"
ASSET = "/assets/index-AbCdEf12.js"
FOREVER = "max-age=315360000, public, immutable"


@pytest.fixture
def dist(tmp_path: Path) -> Iterator[Path]:
    (tmp_path / "assets").mkdir()
    (tmp_path / "pdfjs").mkdir()
    (tmp_path / "index.html").write_bytes(INDEX)
    (tmp_path / "assets" / "index-AbCdEf12.js").write_text("console.log(1)")
    (tmp_path / "pdfjs" / "x.bcmap").write_bytes(b"\x00\x01")
    with override_settings(WHITENOISE_ROOT=str(tmp_path)):
        yield tmp_path


# ── 순수: 가르기 표 ───────────────────────────────────────────────────

PLACES = [
    ("/api", "api"),
    ("/api/", "api"),
    ("/api/x", "api"),
    ("/apiary", "screen"),
    ("/api-py/x", "screen"),
    ("/assets/x.js", "asset"),
    ("/healthz", "reserved"),
    ("/readyz/x", "reserved"),
    ("/", "screen"),
    ("/greenwash/runs/1/review", "screen"),
    ("/dev/viewer", "screen"),
]


@pytest.mark.parametrize(("path", "place"), PLACES)
def test_the_first_segment_decides_the_place(path: str, place: str) -> None:
    assert place_of(path) == place


def test_the_immutable_test_takes_vite_hash_names_only() -> None:
    immutable = re.compile(IMMUTABLE_FILE_TEST)
    for url in (
        "/assets/index-AbCdEf12.js",
        "/assets/PretendardVariable.subset.1-C-__qv6_.woff2",
        "/assets/a-b-12345678.css",
    ):
        assert immutable.search(url), url
    for url in (
        "/assets/index.js",
        "/assets/index-short.js",
        "/pdfjs/cmaps/x-12345678.bcmap",
        "/index.html",
        "/x-AbCdEf12.js",
    ):
        assert not immutable.search(url), url


def test_web_dist_dir_is_off_on_or_refused(tmp_path: Path) -> None:
    assert read_web_dist(None) == WebOff()
    assert read_web_dist("") == WebOff()
    assert isinstance(read_web_dist("relative/dist"), WebRefused)
    assert isinstance(read_web_dist(str(tmp_path)), WebRefused)  # index.html 없음
    (tmp_path / "index.html").write_text("x")
    assert read_web_dist(str(tmp_path)) == WebOn(tmp_path)


@pytest.mark.parametrize("value", ["relative/dist", "/no/such/dir"])
def test_the_settings_refuse_to_load_with_an_unusable_web_dist_dir(value: str) -> None:
    """기동 거부: 설정을 읽는 순간 실패한다(꺼짐으로 접지 않는다)."""
    code = "import esgapi.config.settings.test_business"
    done = subprocess.run(
        [sys.executable, "-c", code],
        cwd=API_PY_DIR,
        env={"PATH": "/usr/bin:/bin", "WEB_DIST_DIR": value},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode != 0
    assert "WEB_DIST_DIR" in done.stderr


@pytest.mark.parametrize("name", ["test_business", "test_security"])
def test_the_test_settings_keep_static_serving_off_even_with_web_dist_dir(name: str, tmp_path: Path) -> None:
    """셸에 쓸 수 있는 WEB_DIST_DIR 이 있어도 시험 설정의 WHITENOISE_ROOT 는 None(시험은 override_settings 로 켠다)."""
    (tmp_path / "index.html").write_text("x")
    code = f"import esgapi.config.settings.{name} as s; print(s.WHITENOISE_ROOT)"
    done = subprocess.run(
        [sys.executable, "-c", code],
        cwd=API_PY_DIR,
        env={"PATH": "/usr/bin:/bin", "WEB_DIST_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout.strip() == "None"


# ── 업무: 임시 dist 로 머리와 본문 ───────────────────────────────────


@pytest.mark.parametrize("path", ["/", "/greenwash", "/greenwash/runs/x/review", "/dev/viewer", "/me", "/apiary"])
def test_a_screen_path_gets_index_html_no_cache(dist: Path, path: str) -> None:
    response = Client().get(path)
    assert (response.status_code, response["Content-Type"], response["Cache-Control"]) == (
        200,
        "text/html; charset=utf-8",
        "no-cache",
    )
    assert response.content == INDEX
    assert not response.has_header("Access-Control-Allow-Origin")


def test_head_on_a_screen_path_is_200(dist: Path) -> None:
    assert Client().head("/greenwash").status_code == 200


def test_the_index_follows_the_setting_at_request_time(dist: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    other = tmp_path_factory.mktemp("other")
    (other / "index.html").write_bytes(b"<p>other</p>")
    with override_settings(WHITENOISE_ROOT=str(other)):
        assert Client().get("/greenwash").content == b"<p>other</p>"


def test_index_html_by_name_is_no_cache_too(dist: Path) -> None:
    response = Client().get("/index.html")
    assert (response.status_code, response["Cache-Control"]) == (200, "no-cache")
    chunks: Iterable[bytes] = getattr(response, "streaming_content")  # noqa: B009 — 파일 응답(FileResponse)의 칸
    assert b"".join(chunks) == INDEX
    response.close()  # whitenoise 의 파일 응답은 파일을 연 채로 온다(닫지 않으면 ResourceWarning)


def test_a_hashed_asset_is_immutable_without_acao(dist: Path) -> None:
    response = Client().get(ASSET)
    assert (response.status_code, response["Cache-Control"]) == (200, FOREVER)
    assert not response.has_header("Access-Control-Allow-Origin")
    response.close()


def test_other_files_are_served_for_a_minute(dist: Path) -> None:
    response = Client().get("/pdfjs/x.bcmap")
    assert (response.status_code, response["Cache-Control"]) == (200, "max-age=60, public")
    assert not response.has_header("Access-Control-Allow-Origin")
    response.close()


def error_code(response: object) -> tuple[int, str]:
    status: int = getattr(response, "status_code")  # noqa: B009
    body = getattr(response, "json")()  # noqa: B009
    return status, body["error"]["code"]


@pytest.mark.parametrize(
    "path", ["/api", "/api/", "/api/no/such", "/assets/none.js", "/assets", "/healthz", "/readyz", "/readyz/x"]
)
def test_api_assets_and_reserved_paths_are_json_404(dist: Path, path: str) -> None:
    response = Client().get(path)
    assert response["Content-Type"].startswith("application/json")
    assert error_code(response) == (404, "NOT_FOUND")


def test_an_unknown_file_outside_assets_is_index_html(dist: Path) -> None:
    """결정 글자대로(sid:MARC-ENT-198): /assets/ 만 404. /pdfjs/없는 것·/favicon.ico 는 화면 경로로 친다."""
    for path in ("/pdfjs/none.bcmap", "/favicon.ico"):
        assert Client().get(path).content == INDEX, path


def test_a_non_get_on_a_dist_file_is_whitenoise_405(dist: Path) -> None:
    """dist 에 있는 파일에 GET·HEAD 밖이 오면 whitenoise 가 405(빈 본문)로 답한다 — 오류 꼴(JSON)이 아니다.

    감독 처분(③ 경계 비블로커 ①): 받아들인다. 그 자리는 화면·API 가 아니라 정적 파일이다."""
    response = Client().post(ASSET)
    assert (response.status_code, b"".join(getattr(response, "streaming_content"))) == (405, b"")  # noqa: B009
    response.close()


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_other_methods_on_a_screen_path_are_json_404(dist: Path, method: str) -> None:
    response = getattr(Client(), method)("/greenwash")
    assert error_code(response) == (404, "NOT_FOUND")


def test_the_api_still_answers_under_api(dist: Path) -> None:
    assert Client().get("/api/healthz").json() == {"status": "ok"}
    assert error_code(Client().post("/auth/login")) == (404, "NOT_FOUND")  # 옛 자리의 POST


# ── 꺼짐(WEB_DIST_DIR 빈 값 — 시험 설정) ──────────────────────────────


@pytest.mark.parametrize("path", ["/", "/greenwash", ASSET, "/pdfjs/x.bcmap"])
def test_with_static_serving_off_everything_outside_api_is_json_404(path: str) -> None:
    response = Client().get(path)
    assert error_code(response) == (404, "NOT_FOUND")


# ── 실제 웹 빌드의 이름 ───────────────────────────────────────────────


def reserved_names(root: Path) -> list[str]:
    """dist 의 맨 위 이름 가운데 fallback 의 예약 자리와 겹치는 것. 있으면 whitenoise 가 먼저 내줘 예약이 깨진다."""
    return sorted(p.name for p in root.iterdir() if place_of("/" + p.name) in ("api", "reserved"))


def test_the_built_web_has_no_name_that_shadows_a_reserved_place() -> None:
    """apps/web/dist 가 있을 때만 잰다(빌드는 git 밖이다). 이미지 안의 dist 는 tests_integration/test_web_flow.py."""
    if not WEB_DIST.is_dir():
        pytest.skip(f"{WEB_DIST} 가 없다(웹을 빌드하지 않았다)")
    assert reserved_names(WEB_DIST) == []
