"""모듈의 schemas.py·api.py 가 같이 쓰는 바닥."""

from datetime import date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from ninja import Schema
from pydantic import ConfigDict, Field, PlainSerializer, WithJsonSchema

from esgapi.core.calc.guards import NotBool as NotBool
from esgapi.core.exceptions import ErrorBody


class Strict(Schema):
    """본문에 모르는 칸이 있으면 거절한다. tenantId·userId 를 본문에 실어 보내는 길이 없다는 것을 꼴로 보인다."""

    model_config = ConfigDict(extra="forbid")


class StrictIn(Strict):
    """모르는 칸을 거절하고(Strict), 타입을 바꿔 받지 않는다: "2025" 는 정수가 아니고 true 는 1 이 아니다.

    ★ 정수 Literal 칸은 이것만으로 불리언을 못 막는다(True == 1). `Annotated[Literal[...], NotBool]` 로 적는다.
    """

    model_config = ConfigDict(extra="forbid", strict=True)


# 경로 선언의 response= 에 펼쳐 넣는다:  response={200: SomeOut, **ERROR_RESPONSES}
# 오류로 답할 때의 본문이 전부 같은 꼴(ErrorBody)이라는 것이 OpenAPI 문서에 드러난다.
# 422 = 요청의 꼴이 틀렸다(VALIDATION_ERROR, fields 에 칸별 까닭).
# 500 = 예상 못 한 예외(INTERNAL_SERVER_ERROR, 상세 없음).
# 둘 다 바닥의 처리기(config/api.py)가 어느 경로에서나 낼 수 있어 공통 표에 든다(밴드 E2).
ERROR_RESPONSES: dict[int, type[ErrorBody]] = {
    400: ErrorBody,
    401: ErrorBody,
    403: ErrorBody,
    409: ErrorBody,
    422: ErrorBody,
    500: ErrorBody,
    503: ErrorBody,
}

# 본문을 받는 경로는 이것을 펼친다:  response={200: SomeOut, **BODY_ERROR_RESPONSES}
# 413 = 본문이 상한을 넘었다(config/api.py 의 body_too_large)거나 그 경로가 정한 행·묶음의 상한을 넘었다.
# 본문이 없는 경로(GET, 로그아웃)는 413 을 낼 길이 없으므로 ERROR_RESPONSES 를 쓴다.
# 「본문이 있다 ⇔ 413 을 선언한다」는 esgapi/config/tests/test_api_contract.py 가 잰다.
BODY_ERROR_RESPONSES: dict[int, type[ErrorBody]] = {**ERROR_RESPONSES, 413: ErrorBody}
TOKEN_ERROR_RESPONSES: dict[int, type[ErrorBody]] = {**ERROR_RESPONSES, 444: ErrorBody}  # 토큰을 받는 동작만(444)
TOKEN_BODY_ERROR_RESPONSES: dict[int, type[ErrorBody]] = {**BODY_ERROR_RESPONSES, 444: ErrorBody}


# ── 시각을 내보내는 꼴(밴드 E2 ③) ─────────────────────────────────────
# DB·로그·설정(TIME_ZONE)은 UTC 그대로다. 응답으로 내보낼 때만 Asia/Seoul(+09:00)로 바꾼다(EDK 원문 :106).
# 마이크로초는 있으면 그대로 싣는다(isoformat). OpenAPI 에는 date-time 그대로 적힌다.
SEOUL = ZoneInfo("Asia/Seoul")


def to_seoul_iso(value: datetime) -> str:
    """aware 시각 → +09:00 ISO 8601. naive 는 받지 않는다(USE_TZ 라 DB 에서 오는 값은 늘 aware 다)."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("naive datetime 은 내보내지 않는다(시간대가 없다)")
    return value.astimezone(SEOUL).isoformat()


KstDateTime = Annotated[
    datetime,
    PlainSerializer(to_seoul_iso, return_type=str, when_used="always"),
    WithJsonSchema({"type": "string", "format": "date-time"}),
]
# 날짜만 있는 값(YYYY-MM-DD). 지금 쓰는 칸은 0 이다 — 생기면 이것을 쓴다.
DateOnly = Annotated[
    date,
    PlainSerializer(date.isoformat, return_type=str, when_used="always"),
    WithJsonSchema({"type": "string", "format": "date"}),
]


# ── 목록의 꼴 셋(밴드 E2 ④, EDK 원문 :113-116 — V1 계약 그대로) ─────────────
# 경로는 응답 스키마를 이것의 하위 클래스로 둔다: `class DocumentPageOut(LimitOffsetPage[DocumentListItemOut]): pass`.
# 하위 클래스로 두는 까닭: OpenAPI 의 스키마 이름(웹의 생성 타입 이름)이 경로마다 그대로 남는다.
# 지금 쓰는 것은 limit/offset 과 page(/branches·/admin/facility-codes — K1b-1)다. cursor 는 쓰는 경로가 0.


class LimitOffsetPage[T](Schema):
    """`?limit=&offset=` 목록. isNext = offset + 실린 수 < count."""

    count: int = Field(description="조건에 맞는 전부의 수(이 쪽에 실린 수가 아니다)")
    isNext: bool
    results: list[T]


class PageNumberPage[T](Schema):
    """`?page=&pageSize=` 목록. page 는 1 부터."""

    count: int
    totalPages: int
    page: int
    pageSize: int
    hasNext: bool
    hasPrevious: bool
    results: list[T]


class CursorPage[T](Schema):
    """커서 목록. cursor 는 다음 쪽을 여는 불투명한 글자, 끝이면 null."""

    count: int
    cursor: str | None
    results: list[T]


def limit_offset_page(count: int, offset: int, results: list[Any]) -> dict[str, Any]:
    return {"count": count, "isNext": offset + len(results) < count, "results": results}


def page_number_page(count: int, page: int, page_size: int, results: list[Any]) -> dict[str, Any]:
    total_pages = (count + page_size - 1) // page_size if count else 0
    return {
        "count": count,
        "totalPages": total_pages,
        "page": page,
        "pageSize": page_size,
        "hasNext": page < total_pages,
        "hasPrevious": page > 1,
        "results": results,
    }
