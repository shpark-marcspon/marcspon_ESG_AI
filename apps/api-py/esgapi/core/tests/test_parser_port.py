"""파서 포트와 어댑터 둘(http · fake). 순수 층: 소켓을 열지 않는다(여는 함수를 가짜로 준다).

가짜 여는 함수는 **진짜 `urllib.request.urlopen` 과 같은 꼴**이다: 2xx 는 응답 객체를 돌려주고 그 밖은 `HTTPError` 를
던진다.
(상태 코드가 든 응답 객체를 돌려주는 가짜는 진짜 길과 다른 가지를 탄다.)

★ 무효 조건: 떠 있는 파서(services/parser)에 대어 본 적이 없다. 여기서 「맞다」는 계약의 글자에 대한 것이다(PD2 병합 뒤
  한 번 대어 본다).
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import ast
import hashlib
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.resources import parser as adapters
from esgapi.core.resources.parser import HttpParser, ParserSetupError, decode_response, make
from esgapi.core.resources.ports.parser import (
    PARSE_FAILURE_KINDS,
    DocumentParser,
    Parsed,
    ParseFailed,
    ParseFailureDetail,
)
from esgapi.core.tests.resource_fakes import FakeParser

DOCUMENT = {"schema_version": "0.1", "source": {"file_name": "가.pdf", "sha256": "a" * 64, "page_count": 1}}
PLACES = {
    "schema_version": "0.1",
    "source": {"file_name": "가.pdf", "sha256": "a" * 64, "page_count": 1},
    "unit": "utf16",
}
OK_BODY = json.dumps({"document": DOCUMENT, "charPlaces": PLACES}).encode()
PDF = b"%PDF-1.7 (synthetic bytes, not a real pdf)"
FILE_NAME = "2025 지속가능경영보고서 (국문).pdf"


class FakeResponse:
    """urlopen 이 2xx 에 돌려주는 것의 꼴: with 로 닫고, status 와 read(n) 이 있다."""

    def __init__(self, body: bytes, status: int = 200) -> None:
        self.status = status
        self._body = io.BytesIO(body)
        self.closed = False

    def read(self, amount: int = -1) -> bytes:
        return self._body.read(amount)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.closed = True


class Opener:
    """가짜 여는 함수. 받은 요청과 timeout 을 적어 둔다."""

    def __init__(self, *, body: bytes = OK_BODY, status: int = 200, error: BaseException | None = None) -> None:
        self.body = body
        self.status = status
        self.error = error
        self.requests: list[urllib.request.Request] = []
        self.timeouts: list[object] = []

    def __call__(self, request: urllib.request.Request, *, timeout: object = None) -> FakeResponse:
        self.requests.append(request)
        self.timeouts.append(timeout)
        if self.error is not None:
            raise self.error
        if not 200 <= self.status < 300:
            # 진짜 urlopen 은 4xx·5xx 에서 응답을 돌려주지 않고 HTTPError 를 던진다.
            raise urllib.error.HTTPError(request.full_url, self.status, "error", Message(), io.BytesIO(self.body))
        return FakeResponse(self.body, self.status)


def http(opener: Opener, **options: Any) -> DocumentParser:
    return make("http", base_url="http://parser.invalid:8000", timeout_s=7.5, opener=opener, **options)


def failed(result: object) -> ParseFailed:
    assert isinstance(result, ParseFailed)
    assert result.ok is False
    return result


# ── 고르기 ───────────────────────────────────────────────────────────────────


def test_the_product_module_has_no_fake_and_make_refuses_it() -> None:
    """가짜는 시험 도우미(core/tests/resource_fakes.py)에만 있다. 제품의 make 는 "fake" 를 고르지 않는다(밴드 CU2)."""
    assert adapters.ADAPTERS == ("http",)
    assert not hasattr(adapters, "FakeParser")
    with pytest.raises(ParserSetupError, match="파서 어댑터 fake 이 없다"):
        make("fake")


def test_the_fake_without_a_table_rejects_everything() -> None:
    fake: DocumentParser = FakeParser()  # 포트를 만족한다(pyright 가 문다)
    result = failed(fake.parse(PDF, file_name=FILE_NAME))
    assert (result.kind, result.detail.code) == ("rejected", "unknown_pdf")


def test_the_fake_returns_the_tabled_result_untouched() -> None:
    parsed = Parsed(document=DOCUMENT, char_places=PLACES)
    without_places = Parsed(document=DOCUMENT, char_places=None, warnings=("char_places_missing",))
    other = b"%PDF other"
    fake = FakeParser({hashlib.sha256(PDF).hexdigest(): parsed, hashlib.sha256(other).hexdigest(): without_places})
    assert fake.parse(PDF, file_name=FILE_NAME) is parsed
    assert fake.parse(other, file_name="b.pdf") is without_places
    assert failed(fake.parse(b"unknown", file_name="c.pdf")).kind == "rejected"
    assert [name for _, name in fake.calls] == [FILE_NAME, "b.pdf", "c.pdf"]


def test_http_needs_an_address_and_a_timeout_and_does_not_read_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARSER_URL", "http://from-env.invalid:8000")
    monkeypatch.setenv("PARSER_TIMEOUT_MS", "30000")
    with pytest.raises(ParserSetupError, match=r"주소\(base_url\)가 없다"):
        make("http")  # 환경에 주소가 있어도 어댑터는 읽지 않는다
    with pytest.raises(ParserSetupError, match=r"주소\(base_url\)가 없다"):
        make("http", base_url="  ", timeout_s=1)
    with pytest.raises(ParserSetupError, match="http:// 나 https://"):
        make("http", base_url="file:///etc/passwd", timeout_s=1)
    with pytest.raises(ParserSetupError, match="시간 제한"):
        make("http", base_url="http://parser.invalid:8000")
    with pytest.raises(ParserSetupError, match="시간 제한"):
        make("http", base_url="http://parser.invalid:8000", timeout_s=0)
    with pytest.raises(ParserSetupError, match="파서 어댑터 grpc 이 없다"):
        make("grpc")
    assert isinstance(make("http", base_url="http://parser.invalid:8000", timeout_s=1), HttpParser)


# ── 요청의 계약 ──────────────────────────────────────────────────────────────


def test_the_request_is_exactly_the_contract(blocked_network: list[object]) -> None:
    opener = Opener()
    result = http(opener).parse(PDF, file_name=FILE_NAME)
    assert isinstance(result, Parsed)
    (request,) = opener.requests
    assert request.get_method() == "POST"
    parts = urllib.parse.urlsplit(request.full_url)
    assert (parts.scheme, parts.netloc, parts.path) == ("http", "parser.invalid:8000", "/parse")
    # 파일 이름은 UTF-8 percent-encoding. 한글·빈칸·괄호가 그대로 실리지 않는다.
    assert parts.query == "file_name=" + urllib.parse.quote(FILE_NAME, safe="")
    assert parts.query.isascii()
    assert " " not in parts.query
    assert "+" not in parts.query
    assert urllib.parse.parse_qs(parts.query) == {"file_name": [FILE_NAME]}
    assert request.get_header("Content-type") == "application/pdf"  # (심은 파손 14 가 application/json 으로 바꾼다)
    assert request.data == PDF  # 본문은 준 바이트 그대로(multipart 도 JSON 도 아니다)
    assert opener.timeouts == [7.5]  # 시간 제한이 여는 함수에 그 값으로 넘어간다
    assert blocked_network == []  # 소켓 시도 0


def test_a_plus_in_the_file_name_is_sent_as_percent_2b() -> None:
    """파서는 쿼리의 `+` 를 빈칸으로 읽는다(PD2 검증에서 확인, 2026-10-08). 이름의 `+` 는 `%2B` 로 보낸다."""
    opener = Opener()
    http(opener).parse(PDF, file_name="A+B 보고서 & 부록/1.pdf")
    query = urllib.parse.urlsplit(opener.requests[0].full_url).query
    assert query.startswith("file_name=A%2BB%20")
    assert "+" not in query
    assert "&" not in query  # 이름의 & 가 쿼리를 쪼개지 않는다
    assert "/" not in query
    assert urllib.parse.parse_qs(query) == {"file_name": ["A+B 보고서 & 부록/1.pdf"]}


def test_a_trailing_slash_on_the_address_does_not_double_the_path() -> None:
    opener = Opener()
    make("http", base_url="http://parser.invalid:8000/", timeout_s=1, opener=opener).parse(PDF, file_name="a.pdf")
    assert opener.requests[0].full_url == "http://parser.invalid:8000/parse?file_name=a.pdf"


def _sent(request: urllib.request.Request) -> tuple[str, str, list[tuple[str, str]], object]:
    return (request.get_method(), request.full_url, sorted(request.header_items()), request.data)


def test_without_layout_the_request_is_the_one_before_band_trd2() -> None:
    """분해 판 인자가 없거나 1 이면 요청 바이트가 밴드 TRD2 앞과 같다(대조·그린워싱 길 0 바뀜 — 심은 파손 Q2)."""
    bare, first = Opener(), Opener()
    http(bare).parse(PDF, file_name="a.pdf")
    http(first).parse(PDF, file_name="a.pdf", layout=1)
    before = ("POST", "http://parser.invalid:8000/parse?file_name=a.pdf", [("Content-type", "application/pdf")], PDF)
    assert _sent(bare.requests[0]) == before
    assert _sent(first.requests[0]) == before


def test_layout_two_is_sent_after_the_file_name() -> None:
    opener = Opener()
    http(opener).parse(PDF, file_name=FILE_NAME, layout=2)
    query = urllib.parse.urlsplit(opener.requests[0].full_url).query
    assert query == "file_name=" + urllib.parse.quote(FILE_NAME, safe="") + "&layout=2"
    assert opener.requests[0].data == PDF


def test_an_unknown_layout_is_rejected_with_bad_layout() -> None:
    body = json.dumps({"detail": {"code": "bad_layout", "message": "layout 은 한 번, 1 또는 2 여야 한다"}}).encode()
    result = failed(http(Opener(status=422, body=body)).parse(PDF, file_name="a.pdf", layout=9))
    assert (result.kind, result.detail.status, result.detail.code) == ("rejected", 422, "bad_layout")


def test_the_fake_records_the_layout_beside_the_calls() -> None:
    fake = FakeParser()
    fake.parse(PDF, file_name="a.pdf")
    fake.parse(PDF, file_name="b.pdf", layout=2)
    assert [name for _sha, name in fake.calls] == ["a.pdf", "b.pdf"]
    assert fake.layouts == [1, 2]


# ── 응답의 갈래 ──────────────────────────────────────────────────────────────


def test_200_with_the_envelope_is_parsed_with_no_warnings() -> None:
    result = http(Opener()).parse(PDF, file_name=FILE_NAME)
    assert isinstance(result, Parsed)
    assert (result.ok, result.document, result.char_places, result.warnings) == (True, DOCUMENT, PLACES, ())


@pytest.mark.parametrize(
    "envelope",
    [
        {"document": DOCUMENT, "charPlaces": None},  # null
        {"document": DOCUMENT},  # 키 없음
        {"document": DOCUMENT, "char_places": PLACES},  # 키 이름이 다르다 (심은 파손 15 가 이 이름을 읽는다)
        {"document": DOCUMENT, "charPlaces": []},
    ],
)
def test_missing_char_places_is_an_invalid_response_not_a_warning(envelope: dict[str, Any]) -> None:
    """`charPlaces` 는 늘 온다(계약). 없으면 경고로 넘기지 않고 invalid_response 다(감독 결정 2026-10-08)."""
    result = failed(http(Opener(body=json.dumps(envelope).encode())).parse(PDF, file_name=FILE_NAME))
    assert (result.kind, result.detail.status) == ("invalid_response", 200)
    assert "charPlaces" in result.detail.message


@pytest.mark.parametrize(
    "body",
    [
        b"<html>not json</html>",
        b"",
        b"[1, 2]",
        b'"text"',
        b'{"charPlaces": {}}',
        b'{"document": "x", "charPlaces": {}}',
        b"\xff\xfe",
    ],
)
def test_200_that_is_not_the_envelope_is_an_invalid_response(body: bytes) -> None:
    result = failed(http(Opener(body=body)).parse(PDF, file_name=FILE_NAME))
    assert result.kind == "invalid_response"
    assert failed(decode_response(body)).kind == "invalid_response"


def test_a_response_over_the_cap_is_an_invalid_response() -> None:
    result = failed(http(Opener(), max_response_bytes=len(OK_BODY) - 1).parse(PDF, file_name=FILE_NAME))
    assert result.kind == "invalid_response"
    assert "상한" in result.detail.message
    assert isinstance(http(Opener(), max_response_bytes=len(OK_BODY)).parse(PDF, file_name=FILE_NAME), Parsed)
    assert adapters.DEFAULT_MAX_RESPONSE_BYTES == 64 * 1024 * 1024


def test_a_success_code_other_than_200_is_an_invalid_response() -> None:
    assert failed(http(Opener(status=204, body=b"")).parse(PDF, file_name=FILE_NAME)).kind == "invalid_response"


@pytest.mark.parametrize("status", [400, 404, 413, 415, 422])
def test_4xx_is_rejected_with_the_parsers_error_code(status: int) -> None:
    """4xx = 이 입력은 다시 해도 안 된다. 여는 함수가 `HTTPError` 를 **던진다**.

    (심은 파손 21 이 except 의 차례를 바꾼다)
    """
    body = json.dumps({"detail": {"code": "password_protected", "message": "암호가 걸린 PDF 다"}}).encode()
    result = failed(http(Opener(status=status, body=body)).parse(PDF, file_name=FILE_NAME))
    assert (result.kind, result.detail.status, result.detail.code) == ("rejected", status, "password_protected")


@pytest.mark.parametrize(
    "body", [b"Unprocessable", b'{"detail": "text only"}', b'{"detail": {"message": "no code"}}', b"[]", b""]
)
def test_4xx_without_the_error_shape_has_no_code(body: bytes) -> None:
    result = failed(http(Opener(status=422, body=body)).parse(PDF, file_name=FILE_NAME))
    assert (result.kind, result.detail.status, result.detail.code) == ("rejected", 422, None)


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_5xx_is_unavailable(status: int) -> None:
    """5xx = 잠깐의 문제일 수 있다. (심은 파손 13 이 rejected 로 바꾼다)"""
    result = failed(http(Opener(status=status, body=b"upstream")).parse(PDF, file_name=FILE_NAME))
    assert (result.kind, result.detail.status) == ("unavailable", status)


@pytest.mark.parametrize(
    ("status", "code", "kind"),
    [
        (413, "too_many_pages", "rejected"),
        (422, "parse_timeout", "rejected"),
        (422, "parse_failed", "rejected"),
        (422, "output_schema_invalid", "rejected"),
        (500, "worker_died", "unavailable"),
        (503, "busy", "unavailable"),
    ],
)
def test_the_codes_band_px_gave_the_parser_fall_on_the_agreed_side(status: int, code: str, kind: str) -> None:
    """밴드 PX 가 파서에 더하거나 옮긴 갈래(결함 D4). 4xx 는 다시 하지 않고(rejected), 5xx 는 다시 한다(unavailable).

    쪽 수 상한·시간 상한·결정적 실패는 같은 PDF 면 늘 같아 4xx, 자식이 죽음·줄이 참은 잠깐의 문제라 5xx 다.
    파서의 code 는 그대로 싣는다(소문자. 공개 응답에 나가지 않는다).
    """
    body = json.dumps({"detail": {"code": code, "message": "파서의 글"}}).encode()
    result = failed(http(Opener(status=status, body=body)).parse(PDF, file_name=FILE_NAME))
    assert (result.kind, result.detail.status, result.detail.code) == (kind, status, code)


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("connection refused"),
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
        OSError("network unreachable"),
    ],
)
def test_no_response_at_all_is_unavailable(error: BaseException) -> None:
    result = failed(http(Opener(error=error)).parse(PDF, file_name=FILE_NAME))
    assert (result.kind, result.detail.status, result.detail.code) == ("unavailable", None, None)


def test_the_real_opener_is_blocked_by_the_test_network_and_comes_back_unavailable(
    blocked_network: list[object],
) -> None:
    """여는 함수를 안 주면 진짜 urlopen 이다. 테스트에서는 소켓이 막혀 있어 연결 실패 → unavailable 갈래다."""
    result = failed(make("http", base_url="http://parser.invalid:8000", timeout_s=0.5).parse(PDF, file_name="a.pdf"))
    assert result.kind == "unavailable"
    assert blocked_network == ["parser.invalid"]


def test_the_three_failure_kinds_are_all_reachable() -> None:
    kinds = {
        failed(http(Opener(status=422, body=b"")).parse(PDF, file_name="a.pdf")).kind,
        failed(http(Opener(status=503, body=b"")).parse(PDF, file_name="a.pdf")).kind,
        failed(http(Opener(body=b"x")).parse(PDF, file_name="a.pdf")).kind,
    }
    assert kinds == set(PARSE_FAILURE_KINDS)
    assert ParseFailed("rejected", ParseFailureDetail(None, None, "x")).ok is False


# ── 순수성: import 허용 목록 ─────────────────────────────────────────────────

API_PY = Path(__file__).resolve().parents[3]
STDLIB = {
    "ast",
    "collections.abc",
    "dataclasses",
    "hashlib",
    "http.client",
    "json",
    "typing",
    "urllib.error",
    "urllib.parse",
    "urllib.request",
}
ALLOWED = {
    "esgapi/core/resources/ports/parser.py": STDLIB,
    "esgapi/core/resources/parser.py": STDLIB | {"esgapi.core.resources.ports.parser"},
    # reconcile 의 서비스는 core 의 테스트가 import 하지 않고(계약 가) 소스를 읽기만 한다.
    "esgapi/reconcile/service/services/parse.py": STDLIB
    | {
        "esgapi.core.resources.ports.parser",
        "esgapi.core.resources",
        "esgapi.core.resources.parser",
        "esgapi.config.env",
    },
}


def imports_of(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            # `from esgapi.core.resources import parser` 는 esgapi.core.resources.parser 를 읽는 것이다.
            found.update(
                f"{module}.{alias.name}" if module == "esgapi.core.resources" else module for alias in node.names
            )
    return found


@pytest.mark.parametrize("relative", sorted(ALLOWED))
def test_the_port_the_adapter_and_the_service_import_only_the_allowed_modules(relative: str) -> None:
    """금지 목록(django·ninja·psycopg)이 아니라 **허용 목록**이라 건너 닿는 길도 막힌다.

    `.importlinter` 의 계약 (다)에는 아직 없다.
    """
    path = API_PY / relative
    if not path.is_file() and relative.startswith("esgapi/reconcile/"):
        pytest.skip("reconcile 의 서비스가 아직 없다")  # pragma: no cover
    imports = imports_of(path)
    assert imports  # 빈 파일을 재고 통과하지 않는다
    for name in imports:
        allowed = name in ALLOWED[relative] or (
            relative.startswith("esgapi/reconcile/") and name.startswith("esgapi.reconcile.calc.")
        )
        assert allowed, f"{relative} 이 {name} 을 import 한다"
