"""포트 `parser`(core/resources/ports/parser.py 의 DocumentParser)의 구현을 고른다.

    make("http", base_url=주소, timeout_s=초)       떠 있는 파서(services/parser)를 부른다

부르는 쪽(reconcile 의 서비스)이 이 모듈의 make 를 직접 부른다(LLM 쪽에서 core/llm/setup.py 가 어댑터를 직접 부르는 것과
같은 꼴). 시험의 표 가짜는 제품 모듈 밖 esgapi/core/tests/resource_fakes.py 에 있다(밴드 CU2). make 는 가짜를
고르지 않는다.
어댑터는 환경을 읽지 않는다: 주소와 시간 제한은 config/env.py 가 읽어 부르는 쪽이 명시로 넘긴다.

http 의 계약(PD2 가 정했다. 2026-10-08):
    POST {base_url}/parse?file_name=<UTF-8 percent-encoding 한 파일 이름>[&layout=<n>][&charts=1]
                                         layout 은 1 이 아닐 때만 싣는다(인자 없는 요청은 밴드 TRD2 앞과 바이트 같음)
                                         charts 는 참일 때만 싣는다(밴드 CHL1 — 그 밖의 요청 바이트 그대로)
    Content-Type: application/pdf        본문은 PDF 바이트 그대로(multipart 도 JSON 도 아니다)
    200 → {"document": <문서 모델 0.1>, "charPlaces": <글자 자리 0.1>[, "chartLabels": <도표 라벨 0.1>]}
    4xx → 이 입력은 다시 해도 안 된다(rejected)    5xx → 잠깐의 문제일 수 있다(unavailable)
    오류 본문은 {"detail": {"code", "message"}} (그 꼴이 아니어도 된다)
같은 경로의 옛 갈래(application/json 으로 주소를 받아 파서가 내려받던 것)는 밴드 PX(2026-10-16)에서 걷혔다. 이제 415 다.
파서의 거절 code(밴드 PX 뒤): 413 too_large·too_many_pages, 415 unsupported_media_type, 422 empty_body·bad_file_name·
not_a_pdf·password_protected·parse_timeout·parse_failed·output_schema_invalid·bad_layout(밴드 TRD1) → rejected /
500 worker_died·503 busy → unavailable. code 는 소문자 그대로 싣는다(공개 응답에 나가지 않는다).

★ 무효 조건: 이 계약은 글자로 맞춘 것이다. 떠 있는 파서는 PD2 가 병합되기 전에는 application/pdf 갈래를 내지 않고,
  이 어댑터는 가짜 여는 함수로만 재었다. 어긋나면 고칠 자리는 둘이다: `_request`(요청 조립)와 `decode_response`(응답
  풀이).
★ 시간 제한은 두 겹이다(밴드 PX): 파서는 분해 한 건을 PARSE_TIMEOUT_SECONDS(기본 180초) 안에 끝내지 못하면 스스로 끊고
  422 parse_timeout(rejected)을 낸다. 다만 그것은 분해 한 건의 시간이고, 파서의 줄에서 기다린 시간은 세지 않는다.
  기다림까지 끊는 것은 이 어댑터의 timeout_s(PARSER_TIMEOUT_MS 기본 210초)이고 그때 unavailable 이다.
  그래서 timeout_s 없이는 http 어댑터를 만들지 않는다(줄에서 끝없이 기다릴 수 있다).
"""

import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any, Final, cast

from esgapi.core.resources.ports.parser import (
    DocumentParser,
    Parsed,
    ParseFailed,
    ParseFailureDetail,
    ParseFailureKind,
    ParseResult,
)

ADAPTERS: Final[tuple[str, ...]] = ("http",)
# 응답 본문을 이만큼까지만 읽는다. 넘으면 invalid_response.
# 근거: 가장 큰 산출(코스맥스 173쪽)의 두 JSON 이 1,840,589 + 6,083,792 = 7,924,381 B(약 8 MB, esg-lab 밴드 C1 산출의
# 파일 크기,
# 2026-10-05)다. 그 여덟 배를 잡았다. 잰 상한이 아니라 어림이다(더 큰 문서가 오면 올린다).
DEFAULT_MAX_RESPONSE_BYTES: Final = 64 * 1024 * 1024
# 오류 본문은 이만큼만 읽는다(code 하나를 꺼내는 데 쓴다).
_ERROR_BODY_BYTES: Final = 64 * 1024

# urllib.request.urlopen 의 꼴: 2xx 는 응답 객체를 돌려주고(with 로 닫는다), 그 밖은 HTTPError 를 던진다.
Opener = Callable[..., Any]


class ParserSetupError(Exception):
    """어댑터를 만들 수 없다(모르는 이름, 주소·시간 제한 없음)."""


def _failed(kind: ParseFailureKind, message: str, *, status: int | None = None, code: str | None = None) -> ParseFailed:
    return ParseFailed(kind, ParseFailureDetail(status=status, code=code, message=message))


def _error_code(body: bytes) -> str | None:
    """오류 본문이 {"detail": {"code": …}} 꼴이면 그 code."""
    try:
        parsed: Any = json.loads(body)
    except ValueError:
        return None
    detail: Any = cast("dict[str, Any]", parsed).get("detail") if isinstance(parsed, dict) else None
    code: Any = cast("dict[str, Any]", detail).get("code") if isinstance(detail, dict) else None
    return code if isinstance(code, str) else None


def decode_response(body: bytes, *, charts: bool = False) -> ParseResult:
    """200 응답의 본문을 푼다. 봉투는 {"document": {...}, "charPlaces": {...}} 이다.

    `charPlaces` 는 늘 온다(PD2 의 계약). null 이거나 키가 없으면 계약 위반이라 invalid_response 다(감독 결정
    2026-10-08:
    경고로 두고 상자 없이 넘어가지 않는다).
    `charts` 로 불렀으면 `chartLabels`(객체)도 늘 와야 한다(밴드 CHL1): 모르는 쿼리를 무시하는 옛 파서를 여기서 잡는다.
    """
    try:
        envelope: Any = json.loads(body)
    except ValueError as err:
        return _failed("invalid_response", f"응답이 JSON 이 아니다: {err}", status=200)
    if not isinstance(envelope, dict):
        return _failed("invalid_response", "응답이 객체가 아니다", status=200)
    fields = cast("dict[str, Any]", envelope)
    document: Any = fields.get("document")
    char_places: Any = fields.get("charPlaces")
    if not isinstance(document, dict):
        return _failed("invalid_response", "응답에 document(객체)가 없다", status=200)
    if not isinstance(char_places, dict):
        return _failed("invalid_response", "응답에 charPlaces(객체)가 없다", status=200)
    if not charts:
        return Parsed(document=cast("dict[str, Any]", document), char_places=cast("dict[str, Any]", char_places))
    chart_labels: Any = fields.get("chartLabels")
    if not isinstance(chart_labels, dict):
        return _failed("invalid_response", "charts 로 불렀는데 응답에 chartLabels(객체)가 없다", status=200)
    return Parsed(
        document=cast("dict[str, Any]", document),
        char_places=cast("dict[str, Any]", char_places),
        chart_labels=cast("dict[str, Any]", chart_labels),
    )


class HttpParser:
    def __init__(self, base_url: str, timeout_s: float, opener: Opener, max_response_bytes: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._opener = opener
        self._max_response_bytes = max_response_bytes

    def _request(self, pdf: bytes, file_name: str, layout: int = 1, charts: bool = False) -> urllib.request.Request:
        fields: dict[str, str | int] = {"file_name": file_name}
        if layout != 1:  # 기본 판의 요청 바이트는 그대로(대조 길 0 바뀜 — 밴드 TRD2)
            fields["layout"] = layout
        if charts:  # 참일 때만(번역·데이터 검증의 요청 바이트 그대로 — 밴드 CHL1)
            fields["charts"] = 1
        query = urllib.parse.urlencode(fields, quote_via=urllib.parse.quote)
        return urllib.request.Request(  # noqa: S310  (주소의 꼴은 make 가 http·https 로 확인했다)
            f"{self.base_url}/parse?{query}",
            data=pdf,
            method="POST",
            headers={"Content-Type": "application/pdf"},
        )

    def parse(self, pdf: bytes, *, file_name: str, layout: int = 1, charts: bool = False) -> ParseResult:
        try:
            with self._opener(self._request(pdf, file_name, layout, charts), timeout=self.timeout_s) as response:
                status: int = response.status
                body: bytes = response.read(self._max_response_bytes + 1)
        # ★ HTTPError 는 URLError 의 아래 갈래다. 먼저 잡아 상태 코드로 가른다(차례가 바뀌면 4xx 가 unavailable 이
        # 된다).
        except urllib.error.HTTPError as err:
            try:
                error_body = err.read(_ERROR_BODY_BYTES)
            except (OSError, http.client.HTTPException):
                error_body = b""
            finally:
                err.close()
            kind: ParseFailureKind = "rejected" if 400 <= err.code < 500 else "unavailable"
            return _failed(kind, f"파서가 {err.code} 를 냈다", status=err.code, code=_error_code(error_body))
        except (urllib.error.URLError, OSError, http.client.HTTPException) as err:
            # 연결 실패, 이름 풀이 실패, 시간 초과(TimeoutError 는 OSError 다), 끊긴 응답.
            return _failed("unavailable", f"파서에 닿지 못했다: {type(err).__name__}: {err}")
        if status != 200:
            return _failed("invalid_response", f"파서가 200 이 아닌 성공 코드를 냈다: {status}", status=status)
        if len(body) > self._max_response_bytes:
            return _failed("invalid_response", f"응답이 상한({self._max_response_bytes} B)을 넘는다", status=status)
        return decode_response(body, charts=charts)


def make(
    name: str,
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
    opener: Opener | None = None,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> DocumentParser:
    if name != "http":
        raise ParserSetupError(f"파서 어댑터 {name} 이 없다. 있는 것: {', '.join(ADAPTERS)}")
    if base_url is None or base_url.strip() == "":
        raise ParserSetupError(
            "파서의 주소(base_url)가 없다. http 어댑터는 주소 없이 만들 수 없다(환경 변수를 스스로 읽지 않는다)"
        )
    if not base_url.startswith(("http://", "https://")):
        raise ParserSetupError("파서의 주소는 http:// 나 https:// 로 시작해야 한다")
    if timeout_s is None or not timeout_s > 0:
        raise ParserSetupError(
            "파서의 시간 제한(timeout_s)이 없다. 파서는 스스로 끊지 않으므로 시간 제한 없이는 끝없이 기다린다"
        )
    return HttpParser(
        base_url,
        timeout_s,
        urllib.request.urlopen if opener is None else opener,
        max_response_bytes,
    )
