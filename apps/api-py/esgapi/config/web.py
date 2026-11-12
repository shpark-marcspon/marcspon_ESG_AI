"""웹 빌드(apps/web/dist)의 정적 서빙 곁: dist 자리 검사, whitenoise 의 불변 판정·머리 함수, SPA fallback 뷰.

같은 출처 한 프로세스가 셋을 낸다(sid:MARC-ENT-198):
  /api/…            API(config/urls.py 가 ninja 를 건 자리)
  dist 에 있는 파일   whitenoise 미들웨어가 URL 뿌리에서 먼저 내준다(settings 의 WHITENOISE_ROOT)
  그 밖의 GET·HEAD   이 파일의 spa_fallback — 화면 경로면 index.html, API·자산·예약어 자리면 JSON 404
화면 경로를 가르는 것은 경로의 첫 마디다(글자 앞부분이 아니다): /apiary·/api-py 는 화면 경로다.
dist 안에 api/·healthz·readyz 로 시작하는 파일이 있으면 whitenoise 가 fallback 보다 먼저 내줘 예약이 깨진다
(웹 빌드에 그런 이름이 없다는 것을 시험이 잰다).

이 파일은 settings(base.py)가 import 한다 → django 의 앱·모델과 config.api 를 import 하지 않는다.
무효 조건: 웹을 S3+CloudFront 로 옮기면 이 파일과 MIDDLEWARE 의 whitenoise 한 줄을 뺀다(sid:MARC-ENT-198).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal
from wsgiref.headers import Headers

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse

# ── dist 자리(환경 변수 WEB_DIST_DIR) ─────────────────────────────────


@dataclass(frozen=True)
class WebOff:
    """WEB_DIST_DIR 이 비었다: 정적 서빙 꺼짐(시험 설정·호스트 개발). 화면 경로도 지금처럼 JSON 404."""

    kind: Literal["off"] = "off"


@dataclass(frozen=True)
class WebOn:
    """절대 경로이고 그 안에 index.html 이 있다."""

    root: Path
    kind: Literal["on"] = "on"


@dataclass(frozen=True)
class WebRefused:
    """값은 있는데 쓸 수 없다(상대 경로·index.html 없음). 기동을 거부한다 — 꺼짐으로 접지 않는다."""

    reason: str
    kind: Literal["refused"] = "refused"


WebDist = WebOff | WebOn | WebRefused


def read_web_dist(value: str | None) -> WebDist:
    """WEB_DIST_DIR 의 값 하나 → 셋 가운데 하나. 파일 시스템은 index.html 하나만 본다."""
    if not value:
        return WebOff()
    root = Path(value)
    if not root.is_absolute():
        return WebRefused(f"WEB_DIST_DIR 는 절대 경로여야 한다(받은 값 {value!r})")
    if not (root / "index.html").is_file():
        return WebRefused(f"WEB_DIST_DIR 에 index.html 이 없다({value})")
    return WebOn(root)


# ── whitenoise 에 넘기는 것 ───────────────────────────────────────────

# Vite 가 지은 해시 이름(/assets/<이름>-<해시 8자>.<확장자>)만 불변으로 친다 → max-age=315360000, public, immutable.
# whitenoise 의 기본 판정은 Django 의 해시 꼴(name.<hash>.ext)이라 Vite 꼴을 못 잡는다. 해시 8자는 실제 dist 로 확인했다
# (apps/web/dist/assets 111개 전부, 2026-10-16). 그 밖(pdfjs·sample)은 max-age=60.
IMMUTABLE_FILE_TEST: Final = r"^/assets/.+-[A-Za-z0-9_-]{8}\.[A-Za-z0-9]+$"


def add_headers(headers: Headers, path: str, url: str) -> None:
    """whitenoise 가 dist 의 파일마다 기동 때 한 번 부른다. /index.html 을 그대로 받아도 매번 새로 묻게 한다."""
    if url == "/index.html":
        headers["Cache-Control"] = "no-cache"


# ── SPA fallback ──────────────────────────────────────────────────────

Place = Literal["api", "asset", "reserved", "screen"]

# 접두 없는 상태 확인 자리. 화면 경로로 index.html 200 을 내면 옛 상태 확인(/readyz)이 DB 가 죽어도 「준비됨」이 된다.
RESERVED: Final = frozenset({"healthz", "readyz"})


def place_of(path: str) -> Place:
    """경로의 첫 마디로 가른다. /api·/api/… 는 API, /assets/… 는 자산, /healthz·/readyz(그 아래 포함)는 예약어."""
    head = path.lstrip("/").split("/", 1)[0]
    if head == "api":
        return "api"
    if head == "assets":
        return "asset"
    if head in RESERVED:
        return "reserved"
    return "screen"


def spa_fallback(request: HttpRequest, path: str = "") -> HttpResponse:
    """주소표의 마지막 자리. 화면 경로의 GET·HEAD 에만 index.html 을 낸다.

    그 밖(다른 메서드·API·자산·예약어, 정적 서빙 꺼짐)은 Http404 → handler404(config/api.py 의 not_found)의 JSON 404.
    index.html 의 자리는 요청 때 설정에서 읽는다(override_settings 를 따라오게)."""
    root: str | None = settings.WHITENOISE_ROOT
    if request.method not in ("GET", "HEAD") or place_of(request.path_info) != "screen" or not root:
        raise Http404
    response = HttpResponse((Path(root) / "index.html").read_bytes(), content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response
