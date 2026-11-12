"""NinjaAPI 하나. 모듈의 라우터 여덟을 모으고, 오류를 응답으로 바꾸고, 상태 확인 경로 둘을 갖는다.

★ 라우터는 경로가 있는 모듈 여덟(user·organization·inventory·reference·greenwash·translation·dataverify·
  materiality)과 core·runs 의
  것이 걸려 있다. 그 모듈에 경로를 더하는 밴드는 이 파일을 고치지 않는다: 자기 모듈의 `router` 에 경로 함수를
  더하면 그 라우터가 걸린 자리 아래에 나온다. 아직 경로가 없는 모듈(reconcile)은 라우터를 처음 만드는 밴드가
  여기에 한 줄을 더한다.
  user 와 organization 은 맨 위(/)에, inventory·reference 는 /<모듈 이름> 에 걸려 있다.
  core 의 문서 경로는 /documents 에, runs 의 실행 경로는 /runs 에, greenwash 는 /greenwash 에, translation 은
  /translation 에, dataverify 는 /dataverify 에, materiality 는 /materiality 에 걸려 있고 이 여섯에는
  세션 쿠키 인증(`session_cookie`)을 여기서 꽂는다(core 와 runs 는 user 를 import 하지 못한다).
"""

import logging
from typing import Final, Literal

from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError, InterfaceError, OperationalError, connection
from django.http import Http404, HttpRequest, HttpResponse
from ninja import NinjaAPI, Schema, Status
from ninja.errors import HttpError, ValidationError
from ninja.openapi.schema import OpenAPISchema
from ninja.types import DictStrAny

from esgapi.core.auth.bearer import company_scoped_auth_or_next, use_operator_company
from esgapi.core.exceptions import ApplicationError, ErrorKind, error_response, unavailable
from esgapi.core.service.apis.documents import router as core_router
from esgapi.dataverify.api import ai_settings_router as dataverify_ai_settings_router
from esgapi.dataverify.api import router as dataverify_router
from esgapi.drafting.api import ai_settings_router as drafting_ai_settings_router
from esgapi.drafting.api import router as drafting_router
from esgapi.greenwash.api import ai_settings_router as greenwash_ai_settings_router
from esgapi.greenwash.api import router as greenwash_router
from esgapi.inventory.api import router as inventory_router
from esgapi.materiality.api import ai_settings_router as materiality_ai_settings_router
from esgapi.materiality.api import router as materiality_router
from esgapi.organization.api import router as organization_router
from esgapi.reference.api import router as reference_router
from esgapi.runs.service.apis.runs import router as runs_router
from esgapi.translation.api import ai_settings_router as translation_ai_settings_router
from esgapi.translation.api import router as translation_router
from esgapi.user.api import router as user_router
from esgapi.user.service.apis.auth import session_cookie
from esgapi.user.service.apis.users import operator_work_company

log = logging.getLogger(__name__)


class _Api(NinjaAPI):
    """NinjaAPI 에서 하나만 바꾼다: 계약 문서의 paths 키에 mount 자리(/api)를 붙이지 않는다.

    ninja 는 문서를 내주는 뷰(/api/openapi.json)에서 path_prefix 없이 부르고, 그때 mount 자리("/api/")를 paths 키
    앞에 붙인다(ninja 1.7.1 openapi/views.py:19-20 → main.py:579-580 → openapi/schema.py:69). 우리 계약은 paths 를
    접두 없이 두고 servers 의 "/api" 하나로 접두를 말한다(sid:MARC-ENT-198) — 그래야 런타임 문서 =
    generated/openapi.json 이고 Swagger(/api/docs)가 servers + paths = /api/me 를 부른다.
    그래서 기본값만 "" 로 바꾼다(준 값은 그대로 쓴다).
    하위 클래스로 한 까닭: 메서드를 인스턴스에 덮어쓰면 pyright strict 가 막고, 뷰를 바꾸면 urls 를 손으로 짓게 된다.
    """

    def get_openapi_schema(
        self, *, path_prefix: str | None = None, path_params: DictStrAny | None = None
    ) -> OpenAPISchema:
        return super().get_openapi_schema(
            path_prefix="" if path_prefix is None else path_prefix, path_params=path_params
        )


# 주소: config/urls.py 가 이 api 를 /api 아래에 건다. docs_url·openapi_url 은 그 아래의 상대 자리다(바깥 주소는
# /api/docs·/api/openapi.json). servers 의 "/api" 가 계약 문서에 그 접두를 적는다.
api = _Api(
    title="esgapi",
    version="0.0.0",
    description=(
        "ESG 공시 대응 Python API: 인증은 Bearer 토큰 먼저, 머리가 없으면 옛 교환 세션 쿠키"
        " → 로그인한 회사 범위의 조회·계산"
    ),
    docs_url="/docs",
    openapi_url="/openapi.json",
    servers=[{"url": "/api"}],
)

# ── 오류를 응답으로 ───────────────────────────────────────────────────

# 오류의 종류마다의 상태 코드. 종류가 늘면 pyright 가 여기 빠진 것을 잡는다(dict 의 키 타입).
HTTP_STATUS: Final[dict[ErrorKind, int]] = {
    "invalid_input": 400,
    "unauthenticated": 401,
    "forbidden": 403,
    "not_found": 404,
    "conflict": 409,
    "unavailable": 503,
    "token_not_valid": 444,
    "validation": 422,
}

# 요청 꼴 틀림(422)과 예상 못 한 예외(500)의 code·문장은 고정이다(EDK 원문 :122-131).
VALIDATION_MESSAGE: Final = "입력값을 확인해 달라"
INTERNAL_MESSAGE: Final = "서버에서 처리하지 못했다. 잠시 뒤 다시 시도해 달라"
# loc 의 맨 앞(값이 실려 온 자리). 칸 이름이 아니라서 뗀다.
_LOCATIONS: Final = frozenset({"body", "query", "path", "header", "cookie", "form", "file"})
_BODY_LOCATIONS: Final = frozenset({"body", "form", "file"})


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def field_name(loc: tuple[object, ...]) -> str:
    """ninja ValidationError 의 loc 하나 → fields 의 칸 이름.

    ("body", "body", "rows", 0, "year") → "rows.0.year" · ("query", "record_type") → "recordType"
    · ("path", "run_id") → "runId".
    규칙: 맨 앞의 자리(body·query·path …)를 떼고, 본문(body·form·file)이면 그다음 마디(경로 함수의 인자 이름 —
    ninja 가 싣는다)도 뗀다. 남은 마디를 `.` 로 잇는다(배열 자리는 수 그대로). 본문의 칸 이름은 이미 camel 이고
    보낸 쪽이 쓴 모르는 칸 이름(extra_forbidden)은 그대로 둔다.
    쿼리·경로의 이름만 파이썬 인자 이름(snake)이라 camel 로 바꾼다.
    남는 것이 없으면 그 자리 이름이다(본문 전체가 틀림 = "body").
    """
    parts = list(loc)
    where = str(parts[0]) if parts and str(parts[0]) in _LOCATIONS else None
    if where is not None:
        parts = parts[1:]
        if where in _BODY_LOCATIONS and parts:
            parts = parts[1:]
    camel = where is not None and where not in _BODY_LOCATIONS
    names = [_camel(str(p)) if camel and not isinstance(p, int) else str(p) for p in parts]
    return ".".join(names) if names else (where or "body")


@api.exception_handler(ApplicationError)
def _on_application_error(request: HttpRequest, exc: ApplicationError) -> HttpResponse:  # pyright: ignore[reportUnusedFunction]
    return error_response(HTTP_STATUS[exc.kind], exc.code, exc.message, exc.fields)


@api.exception_handler(ValidationError)
def _on_validation_error(request: HttpRequest, exc: ValidationError) -> HttpResponse:  # pyright: ignore[reportUnusedFunction]
    """요청의 꼴이 틀렸다 → 422 VALIDATION_ERROR, fields = {칸 이름: [까닭 문장]}.

    받은 값은 되돌려 보내지 않는다(pydantic 의 msg 만 싣는다 — input·ctx 는 싣지 않는다).
    업무 거절(모듈이 던지는 invalid_input 갈래)은 400 그대로다."""
    fields: dict[str, list[str]] = {}
    for e in exc.errors:
        loc: tuple[object, ...] = tuple(e.get("loc", ()))
        fields.setdefault(field_name(loc), []).append(str(e.get("msg", "")))
    return error_response(
        HTTP_STATUS["validation"], "VALIDATION_ERROR", VALIDATION_MESSAGE, fields, legacy_code="invalid_input"
    )


# 상태 코드마다의 EDK 일반 이름. ninja·Django 가 바닥에서 내는 오류(HttpError·Http404)는 세부 이름이 없어 이것을 쓴다.
# 405 는 여기 없다: ninja 는 예외 없이 응답을 바로 돌려준다 — 바꾸는 자리는 core/observability/middleware.py 다.
GENERIC_BY_STATUS: Final[dict[int, str]] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    429: "TOO_MANY_REQUESTS",
}


@api.exception_handler(HttpError)
def _on_http_error(request: HttpRequest, exc: HttpError) -> HttpResponse:  # pyright: ignore[reportUnusedFunction]
    """ninja 가 바닥에서 던지는 것(본문이 JSON 이 아님 = ParseError 400 등).

    ninja 기본 처리기의 {"detail"} 꼴 대신 한 꼴로 낸다."""
    status = exc.status_code
    return error_response(status, GENERIC_BY_STATUS.get(status, f"HTTP_{status}"), str(exc))


@api.exception_handler(Http404)
def _on_http404(request: HttpRequest, exc: Http404) -> HttpResponse:  # pyright: ignore[reportUnusedFunction]
    return error_response(404, "NOT_FOUND", "찾을 수 없다")


@api.exception_handler(RequestDataTooBig)
def _on_body_too_large(request: HttpRequest, exc: RequestDataTooBig) -> HttpResponse:  # pyright: ignore[reportUnusedFunction]
    """본문이 상한(settings 의 DATA_UPLOAD_MAX_MEMORY_SIZE)을 넘었다. Django 가 본문을 읽다 던진다.

    받은 크기도 내용도 되돌려 보내지 않는다. 상태 코드가 HTTP_STATUS 에 없는 까닭: 오류의 종류(ErrorKind)가 아니라
    바닥이 본문을 읽기 전에 내는 답이다. 본문을 받는 경로는 413 을 선언한다(core.schemas.BODY_ERROR_RESPONSES).
    아래 Exception 처리기보다 먼저 잡힌다(ninja 는 예외 타입의 MRO 순서로 처리기를 찾는다).
    """
    return error_response(413, "body_too_large", "요청 본문이 너무 크다")


@api.exception_handler(OperationalError)
def _on_db_unreachable(request: HttpRequest, exc: OperationalError) -> HttpResponse:  # pyright: ignore[reportUnusedFunction]
    """DB 에 닿지 못함(연결 끊김·DB 멈춤) → 503 UNAVAILABLE. 예상 못 한 예외(500)와 가른다: 다시 해 볼 만한 장애다.

    /readyz 의 not_ready 와 같은 때다. 속사정은 기록에만 남긴다. InterfaceError(닫힌 연결)도 여기다."""
    log.exception("db unreachable: %s %s", request.method, request.path, exc_info=exc)
    return unavailable()


api.add_exception_handler(InterfaceError, _on_db_unreachable)  # pyright: ignore[reportArgumentType]


@api.exception_handler(Exception)
def _on_unexpected(request: HttpRequest, exc: Exception) -> HttpResponse:  # pyright: ignore[reportUnusedFunction]
    """예상하지 못한 예외 → 500 INTERNAL_SERVER_ERROR.

    예외의 글자·경로는 로그에만 남기고 본문은 고정 문장이다(원문 :131).

    503 은 업무로 정한 자리(저장소·LLM 의 unavailable 갈래, /readyz, 테넌트 미들웨어의 DB 닿지 못함)에만 남는다."""
    log.exception("unhandled error: %s %s", request.method, request.path, exc_info=exc)
    return error_response(500, "INTERNAL_SERVER_ERROR", INTERNAL_MESSAGE)


def server_error(request: HttpRequest) -> HttpResponse:
    """ninja 밖에서 난 예외(미들웨어 안 등)의 500(urls.py 의 handler500). Django 의 기본은 HTML 이다.

    예외의 글자는 Django 가 로거 django.request 에 남긴다. 본문은 _on_unexpected 와 같은 고정 문장이다."""
    return error_response(500, "INTERNAL_SERVER_ERROR", INTERNAL_MESSAGE)


def not_found(request: HttpRequest, exception: Exception) -> HttpResponse:
    """없는 경로(urls.py 의 handler404). ninja 밖에서 나는 404 다."""
    return error_response(HTTP_STATUS["not_found"], "not_found", "그런 경로가 없다")


# ── 상태 확인 ─────────────────────────────────────────────────────────


class HealthOut(Schema):
    status: Literal["ok"]


class ReadyOut(Schema):
    status: Literal["ready", "not_ready"]
    checks: dict[str, str]


@api.get("/healthz", operation_id="config_healthz", response=HealthOut, tags=["상태 확인"])
def healthz(request: HttpRequest) -> HealthOut:
    """살아 있음: 프로세스가 요청을 받을 수 있는가만 본다. DB 가 죽어도 200 이다."""
    return HealthOut(status="ok")


@api.get("/readyz", operation_id="config_readyz", response={200: ReadyOut, 503: ReadyOut}, tags=["상태 확인"])
def readyz(request: HttpRequest) -> Status[ReadyOut]:
    """준비됨: 지금 요청을 처리할 수 있는가. DB 에 실제로 닿아 본다."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError as err:
        return Status(503, ReadyOut(status="not_ready", checks={"db": f"fail: {type(err).__name__}"}))
    return Status(200, ReadyOut(status="ready", checks={"db": "ok"}))


# ── 모듈의 라우터 ─────────────────────────────────────────────────────

api.add_router("", user_router)
api.add_router("", organization_router)
api.add_router("/inventory", inventory_router)
api.add_router("/reference", reference_router)
use_operator_company(operator_work_company)  # 운영 관리자의 작업 회사(MARC-ENT-374)
api.add_router("/documents", core_router, auth=[company_scoped_auth_or_next, session_cookie])
api.add_router("/runs", runs_router, auth=[company_scoped_auth_or_next, session_cookie])
api.add_router("/greenwash", greenwash_router, auth=[company_scoped_auth_or_next, session_cookie])
api.add_router("/translation", translation_router, auth=[company_scoped_auth_or_next, session_cookie])
api.add_router("/dataverify", dataverify_router, auth=[company_scoped_auth_or_next, session_cookie])
api.add_router("/materiality", materiality_router, auth=[company_scoped_auth_or_next, session_cookie])
api.add_router("/drafting", drafting_router, auth=[company_scoped_auth_or_next, session_cookie])
api.add_router("/ai-settings/greenwash", greenwash_ai_settings_router)  # 운영 관리자 Bearer(라우터의 auth — G2c2)
api.add_router("/ai-settings/translation", translation_ai_settings_router)  # 운영 관리자 Bearer(라우터의 auth — TR4)
api.add_router("/ai-settings/dataverify", dataverify_ai_settings_router)  # 운영 관리자 Bearer(라우터의 auth — DVA1)
api.add_router("/ai-settings/materiality", materiality_ai_settings_router)  # 운영 관리자 Bearer(라우터의 auth — IR4)
api.add_router("/ai-settings/drafting", drafting_ai_settings_router)  # 운영 관리자 Bearer(라우터의 auth — RPA1)
