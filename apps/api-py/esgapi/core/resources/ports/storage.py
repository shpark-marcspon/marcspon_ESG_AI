"""포트: 원본 파일 저장소. 「키 → 올릴 주소 / 있는가 / 바이트」.

구현은 core/resources/storage.py 의 make(name) 이 고른다(s3). 시험의 가짜는 core/tests/resource_fakes.py.
표준 라이브러리만 쓴다.

    presign_upload(key, content_length=)   클라이언트가 직접 올릴 서명된 주소. 계산일 뿐 저장소에 요청을 보내지 않는다
    head(key)                              올라와 있는가, 크기와 ETag
    get(key, max_bytes=)                   바이트. max_bytes 를 넘으면 끊는다
    put(key, content=, media_type=)        서버가 지은 바이트를 그 키에 쓴다(실행기의 출력·단계 파일 — X1b-1)

실패는 던지지 않고 갈래로 돌려준다(파서 포트와 같은 꼴):
  ObjectMissing       그 키에 객체가 없다(저장소의 404)
  StorageDenied       저장소가 거절했다(403). ★ 「아직 안 올라왔다」가 아니다. 둘을 섞지 않는다
  StorageUnavailable  닿지 못했거나 그 밖의 오류. 다시 해 볼 수 있다
  ObjectTooLarge      get 에서만: 객체가 max_bytes 보다 크다. 본문을 끝까지 읽지 않았다
  put 은 ObjectPut · StorageDenied · StorageUnavailable 셋뿐이다(버킷이 없어 404 면 StorageUnavailable)

★ 일부러 없는 것:
  presign_download  파서에는 주소가 아니라 바이트가 간다(core/resources/ports/parser.py 의 계약)
  delete            지우기·보존은 아직 정하지 않았다(실행의 파일도 지우지 않는다 — MARC-ENT-208)
  ★ put 은 사용자가 올린 바이트를 받는 길이 아니다(올리는 것은 여전히 클라이언트다). 실행기가 흐름의 산출을 쓴다.
"""

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    """이 주소로 `method` 요청을 보내면 본문이 그 키에 올라간다. `expires_in_s` 초 동안만 통한다.

    주소 자체가 권한이다(서명이 들어 있다). 표에도 기록(log)에도 남기지 않는다.
    """

    url: str
    expires_in_s: int
    method: Literal["PUT"] = "PUT"


@dataclass(frozen=True, slots=True)
class ObjectFound:
    size_bytes: int
    etag: str  # 저장소가 준 글자 그대로(따옴표째)


@dataclass(frozen=True, slots=True)
class ObjectBytes:
    data: bytes
    etag: str  # 저장소가 준 글자 그대로(따옴표째)


@dataclass(frozen=True, slots=True)
class ObjectMissing:
    pass


@dataclass(frozen=True, slots=True)
class ObjectTooLarge:
    max_bytes: int


@dataclass(frozen=True, slots=True)
class StorageDenied:
    detail: str


@dataclass(frozen=True, slots=True)
class StorageUnavailable:
    detail: str


@dataclass(frozen=True, slots=True)
class ObjectPut:
    etag: str  # 저장소가 준 글자 그대로(따옴표째)


HeadResult = ObjectFound | ObjectMissing | StorageDenied | StorageUnavailable
GetResult = ObjectBytes | ObjectMissing | ObjectTooLarge | StorageDenied | StorageUnavailable
PutResult = ObjectPut | StorageDenied | StorageUnavailable


class ObjectStorage(Protocol):
    def presign_upload(self, key: str, *, content_length: int) -> PresignedUpload:
        """`content_length` 바이트의 본문만 받는 올리기 주소. 크기는 서명 조건이다."""
        ...

    def head(self, key: str) -> HeadResult:
        """객체가 있는가. 실패를 던지지 않고 갈래로 돌려준다."""
        ...

    def get(self, key: str, *, max_bytes: int) -> GetResult:
        """객체의 바이트. `max_bytes` 를 넘으면 끝까지 읽지 않고 `ObjectTooLarge` 다."""
        ...

    def put(self, key: str, *, content: bytes, media_type: str) -> PutResult:
        """바이트를 그 키에 쓴다(같은 키면 덮어쓴다). 실패를 던지지 않고 갈래로 돌려준다."""
        ...
