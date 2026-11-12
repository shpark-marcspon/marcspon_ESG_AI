"""문서 올리기의 요청과 응답의 꼴(JSON). 필드 이름은 camelCase 다.

★ 응답에 싣지 않는 것: storageKey(저장소의 자리), tenantId, uploadedBy, leaseExpiresAt, sha256.
  서명된 주소는 만들기의 응답(upload.url)에만 있다. 예외: 목록(DocumentListItemOut)에만 uploadedBy(사용자 id)가 있다
  — 「올린 사람」「내가 올린 것만」을 화면이 가른다(감독 처분, 밴드 XC).
★ reportYear·previousDocumentId·pageCount·hasText 는 표의 값이다(X1b-2a). null = 정하지 않음(연도·앞 판) 또는 모른다
  (쪽 수·글자 층 — 올림 확인이 못 쟀거나 아직 안 올라옴). 만들기는 reportYear 만 받는다: previousDocumentId 에 값을
  실으면 422 `PREVIOUS_VIA_PATCH`(앞 판은 PATCH 로만). 보고 연도의 범위는 DB CHECK 와 같다(1900~2100, 어림).
  문서·일감의 id 는 숫자다(K1u-b — DB 의 BigInt). DocumentListItemOut 은 DocumentOut 을 이어받아 id 의 꼴이 같다.
★ 요청 본문에 테넌트·사용자의 칸이 없다(세션에서만 온다). 모르는 칸은 거절한다(StrictIn).
"""

from typing import Any, Literal

from ninja import Schema
from pydantic import Field, field_validator, model_validator

from esgapi.core.calc.documents import (
    MAX_FILE_NAME_CHARS,
    NO_NUL_PATTERN,
    REPORT_YEAR_MAX,
    REPORT_YEAR_MIN,
    DocumentStatus,
    JobStatus,
    is_valid_file_name,
)
from esgapi.core.schemas import KstDateTime, LimitOffsetPage, StrictIn


class DocumentIn(StrictIn):
    """올릴 파일의 이름과 크기. 크기는 서명 조건이 된다: 내준 주소로는 이 크기의 본문만 올라간다."""

    fileName: str = Field(min_length=1, max_length=MAX_FILE_NAME_CHARS, description="표시용 이름. 저장소 키에 안 든다")
    # StrictIn 이라 true·"12" 를 정수로 받지 않는다. 상한(MAX_UPLOAD_BYTES)은 경로가 413 으로 답한다.
    sizeBytes: int = Field(ge=1, description="올릴 파일의 바이트 수")
    reportYear: int | None = Field(default=None, ge=REPORT_YEAR_MIN, le=REPORT_YEAR_MAX, description="보고 연도")
    previousDocumentId: int | None = Field(default=None, description="이 문서가 새 판인 앞 판의 문서 id")

    @field_validator("fileName")
    @classmethod
    def _no_control_characters(cls, value: str) -> str:
        if not is_valid_file_name(value):
            raise ValueError("파일 이름에 제어 글자가 있다")
        return value


class DocumentOut(Schema):
    id: int
    fileName: str
    status: DocumentStatus
    sizeBytes: int
    etag: str | None  # 저장소가 준 글자 그대로(따옴표째). null = 아직 안 올라왔다
    createdAt: KstDateTime
    uploadedAt: KstDateTime | None
    reportYear: int | None
    previousDocumentId: int | None  # 이 문서가 새 판인 앞 판. null = 첫 판
    pageCount: int | None  # 올림 확인이 잰 쪽 수. null = 모른다(못 쟀거나 아직 안 올라옴)
    hasText: bool | None  # 앞 몇 쪽(TEXT_PROBE_PAGES)에 글자 층이 있나. null = 모른다, false = 글자 없음


class DocumentPatchIn(StrictIn):
    """보낸 칸만 바꾼다(null = 지움). 둘 다 빠지면 422 — 바꿀 칸이 없다."""

    reportYear: int | None = Field(default=None, ge=REPORT_YEAR_MIN, le=REPORT_YEAR_MAX, description="보고 연도")
    previousDocumentId: int | None = Field(
        default=None, description="이 문서가 새 판인 앞 판의 문서 id(같은 회사의 올라온 문서, 한 앞 판에 뒤 판 하나)"
    )

    @model_validator(mode="after")
    def _something_to_change(self) -> "DocumentPatchIn":
        if not self.model_fields_set:
            raise ValueError("바꿀 칸이 없다")
        return self


class DocumentListItemOut(DocumentOut):
    """목록의 한 줄. 문서에 올린 사람(사용자 id)을 더한다."""

    uploadedBy: int | None


class DocumentPageOut(LimitOffsetPage[DocumentListItemOut]):
    pass


class DocumentListQuery(Schema):
    """`GET /documents` 의 조회 인자. `reportYear` 는 「같다」, `q` 는 파일 이름의 부분 일치다."""

    # (X1b-2a) uploadedBy 는 「같다」(남의 회사 사용자면 빈 쪽), latestOnly 면 판 사슬의 마지막만, q 의 NUL 은 거절.

    reportYear: int | None = Field(default=None, ge=REPORT_YEAR_MIN, le=REPORT_YEAR_MAX, description="보고 연도")
    q: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_FILE_NAME_CHARS,
        pattern=NO_NUL_PATTERN,
        description="파일 이름의 부분 일치",
    )
    uploadedBy: int | None = Field(default=None, description="올린 사용자 id(목록 줄의 uploadedBy)")
    latestOnly: bool = Field(default=False, description="true 면 올라온 뒤 판이 없는 문서(판 사슬의 마지막)만")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class JobOut(Schema):
    id: int
    kind: str
    status: JobStatus
    attempts: int
    errorCode: str | None
    errorMessage: str | None
    summary: dict[str, Any]
    createdAt: KstDateTime
    finishedAt: KstDateTime | None


class UploadOut(Schema):
    """이 주소로 `method` 요청을 보내 파일을 올린다. 본문의 크기는 만들 때 말한 sizeBytes 와 같아야 한다."""

    url: str
    method: Literal["PUT"]
    expiresInSeconds: int


class DocumentCreatedOut(Schema):
    document: DocumentOut
    upload: UploadOut


class DocumentStatusOut(Schema):
    document: DocumentOut
    jobs: list[JobOut]
