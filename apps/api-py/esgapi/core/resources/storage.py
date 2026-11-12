# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""포트 `storage`(core/resources/ports/storage.py 의 ObjectStorage)의 구현을 고른다.

    make("s3", bucket=…, region=…, endpoint=…, public_endpoint=…, force_path_style=…,
         access_key_id=…, secret_access_key=…, upload_ttl_s=…)
                                 S3 와 S3 호환 저장소(로컬 compose 의 Versity)를 boto3 로 부른다

어댑터는 환경을 읽지 않는다: 값은 config/env.py 가 읽어 부르는 쪽이 명시로 넘긴다(core/resources/parser.py 와 같은 꼴).
시험의 메모리 가짜는 제품 모듈 밖 esgapi/core/tests/resource_fakes.py 에 있다(밴드 CU2). make 는 가짜를 고르지 않는다.

★ 클라이언트가 둘이다(TS 뼈대의 apps/server/src/adapters.ts 와 같다):
    internal  `endpoint` 로 head·get·put 을 보낸다(서버가 저장소에 닿는 이름. compose 에서는 http://storage:7070)
    external  `public_endpoint` 로 **서명만** 한다(주소를 받을 클라이언트가 저장소에 닿는 이름. 없으면 endpoint)
  서명에는 호스트 이름이 들어간다. 안쪽 이름으로 서명한 주소는 바깥에서 403 이다(2026-10-08 탐침, 아래).
  실제 S3 에서는 둘 다 비어 같은 AWS 주소가 된다.

★ 가름은 HTTP 상태 코드로만 한다(`response["ResponseMetadata"]["HTTPStatusCode"]`). `Error.Code` 는 보지 않는다:
  같은 404 가 head 에서는 "404", get 에서는 "NoSuchKey" 다.
    404 → ObjectMissing    403 → StorageDenied    그 밖의 ClientError·BotoCoreError → StorageUnavailable
  403 을 「아직 안 올라왔다」로 읽지 않는다.

SDK 의 타입: boto3·botocore 에는 타입 정보가 없고 스텁도 들이지 않았다. 이 파일 머리에서 pyright 의 규칙 넷을 끄고
SDK 의 값은 이 파일 안에서 Any 로 받아 포트의 dataclass 로만 내보낸다.

탐침으로 본 것(critic-W1a 2026-10-08, versity/versitygw:v1.8.0 × boto3 1.43.101, band-handoffs/W1a-order-review.md):
  서명 주소 PUT 200 · ETag 는 따옴표를 낀 글자 · 없는 키 404 · 틀린 비밀 키 403 · 다른 호스트 이름으로 서명 403 ·
  ContentLength 를 서명하면 다른 크기의 본문은 403.

무효 조건:
  - **없는 버킷과 틀린 접근 키(없는 계정)는 Versity 에서 404 다** → ObjectMissing 으로 읽힌다(「안 올라옴」과 같은 답).
  - Versity 의 404·403 가름이 실제 S3 와 같은지는 재지 않았다. 실제 S3 는 ListBucket 권한이 없으면 없는 키의 head 가
    403 이다(그때 이 어댑터는 StorageDenied 를 낸다). 크기의 서명 조건을 실제 S3 가 강제하는지도 재지 않았다.
  - 키 둘을 다 안 주면 boto3 의 기본 순서에 맡긴다(ECS 의 태스크 역할). 로컬에서 키 없이 서명하면 boto3 가 인스턴스
    메타데이터 주소를 찾다 NoCredentialsError 를 낸다 → 그때는 StorageSetupError 다.
  - boto3 는 스스로 읽는 환경 변수·파일이 있다(AWS_PROFILE, ~/.aws/config …). 아래에서 명시한 값이 이기지만
    그것까지 막지는 않았다.
"""

from typing import Any, Final

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from esgapi.core.resources.ports.storage import (
    GetResult,
    HeadResult,
    ObjectBytes,
    ObjectFound,
    ObjectMissing,
    ObjectPut,
    ObjectStorage,
    ObjectTooLarge,
    PresignedUpload,
    PutResult,
    StorageDenied,
    StorageUnavailable,
)

ADAPTERS: Final[tuple[str, ...]] = ("s3",)

# 시간 제한과 시도 횟수. ★ 셋 다 어림이다(잰 값이 아니다).
# 까닭: head 는 트랜잭션 밖(연결은 쥔다)이고 gunicorn timeout 이 30초다(gunicorn.conf.py). 최악의 합이 그보다 한참
# 짧아야 한다: (연결 2 + 읽기 5) × 시도 2 = 14초에 다시 시도 사이의 기다림.
# total_max_attempts 는 「첫 시도를 넣은 합」이다({"max_attempts": 2} 는 기본 방식에서 합 3번이라 그렇게 적지 않는다).
CONNECT_TIMEOUT_S: Final = 2
READ_TIMEOUT_S: Final = 5
TOTAL_MAX_ATTEMPTS: Final = 2
# 서명한 주소의 수명(초)의 기본값. config/env.py 의 UPLOAD_URL_TTL_SECONDS 기본값과 같다.
DEFAULT_UPLOAD_TTL_S: Final = 300


class StorageSetupError(Exception):
    """어댑터를 만들 수 없거나(모르는 이름, 버킷·리전 없음, 키가 하나뿐) 서명할 자격 증명을 찾지 못했다."""


def _status_of(err: ClientError) -> int | None:
    response: Any = err.response
    status: Any = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return status if isinstance(status, int) else None


def _failed(err: ClientError) -> ObjectMissing | StorageDenied | StorageUnavailable:
    """ClientError → 갈래. HTTP 상태 코드로만 가른다(머리말)."""
    status = _status_of(err)
    if status == 404:
        return ObjectMissing()
    if status == 403:
        return StorageDenied(f"저장소가 403 을 냈다: {type(err).__name__}")
    return StorageUnavailable(f"저장소가 {status} 를 냈다: {type(err).__name__}")


def _unreachable(err: BotoCoreError) -> StorageUnavailable:
    # 연결 실패, 이름 풀이 실패, 시간 초과, 끊긴 본문. 속사정(주소 등)은 싣지 않고 갈래의 이름만.
    return StorageUnavailable(f"저장소에 닿지 못했다: {type(err).__name__}")


class S3Storage:
    def __init__(self, *, internal: Any, external: Any, bucket: str, upload_ttl_s: int) -> None:
        self.internal = internal  # head·get·put
        self.external = external  # 서명만
        self.bucket = bucket
        self.upload_ttl_s = upload_ttl_s

    def presign_upload(self, key: str, *, content_length: int) -> PresignedUpload:
        try:
            # ★ external 로 서명한다(머리말). ContentLength 를 넣으면 서명한 헤더가 content-length;host 가 된다.
            #   ContentType 은 넣지 않는다: 서명하면 그 헤더를 안 보낸 클라이언트가 403 이다. 형식은 파서가 본다.
            url: Any = self.external.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": key, "ContentLength": content_length},
                ExpiresIn=self.upload_ttl_s,
                HttpMethod="PUT",
            )
        except BotoCoreError as err:
            raise StorageSetupError(f"올리기 주소를 서명하지 못했다: {type(err).__name__}") from err
        return PresignedUpload(url=str(url), expires_in_s=self.upload_ttl_s)

    def head(self, key: str) -> HeadResult:
        try:
            response: Any = self.internal.head_object(Bucket=self.bucket, Key=key)
        except ClientError as err:
            return _failed(err)
        except BotoCoreError as err:
            return _unreachable(err)
        # ETag 는 저장소가 준 글자 그대로(따옴표째) 둔다. 벗기면 나중에 IfMatch 로 되돌려 보낼 때 다시 붙여야 한다.
        return ObjectFound(size_bytes=int(response["ContentLength"]), etag=str(response["ETag"]))

    def get(self, key: str, *, max_bytes: int) -> GetResult:
        try:
            response: Any = self.internal.get_object(Bucket=self.bucket, Key=key)
            body: Any = response["Body"]
            try:
                declared: Any = response.get("ContentLength")
                if isinstance(declared, int) and declared > max_bytes:
                    return ObjectTooLarge(max_bytes)  # 본문을 읽지 않았다
                # 헤더가 없거나 거짓이어도 max_bytes + 1 바이트까지만 읽는다.
                chunks: list[bytes] = []
                total = 0
                while total <= max_bytes:
                    chunk: bytes = body.read(max_bytes + 1 - total)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
            finally:
                body.close()
        except ClientError as err:
            return _failed(err)
        except BotoCoreError as err:
            return _unreachable(err)
        if total > max_bytes:
            return ObjectTooLarge(max_bytes)
        return ObjectBytes(data=b"".join(chunks), etag=str(response["ETag"]))

    def put(self, key: str, *, content: bytes, media_type: str) -> PutResult:
        try:
            response: Any = self.internal.put_object(
                Bucket=self.bucket, Key=key, Body=content, ContentType=media_type, ContentLength=len(content)
            )
        except ClientError as err:
            failed = _failed(err)
            if isinstance(failed, ObjectMissing):
                # 쓰기의 404 는 「객체가 없다」가 아니라 버킷이 없다는 뜻이다(Versity 는 틀린 접근 키도 404 — 머리말).
                return StorageUnavailable(f"저장소가 404 를 냈다: {type(err).__name__}")
            return failed
        except BotoCoreError as err:
            return _unreachable(err)
        return ObjectPut(etag=str(response["ETag"]))


def _client(*, region: str, endpoint: str | None, config: Any, access_key_id: str | None, secret: str | None) -> Any:
    if access_key_id is None:
        # 키를 넘기지 않는다: boto3 의 기본 순서(ECS 의 태스크 역할 …)가 찾는다. 찾는 일은 처음 서명·요청할 때 일어난다.
        return boto3.client("s3", region_name=region, endpoint_url=endpoint, config=config)
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint,
        config=config,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret,
    )


def make(
    name: str,
    *,
    bucket: str | None = None,
    region: str | None = None,
    endpoint: str | None = None,
    public_endpoint: str | None = None,
    force_path_style: bool = False,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
    upload_ttl_s: int = DEFAULT_UPLOAD_TTL_S,
) -> ObjectStorage:
    if name != "s3":
        raise StorageSetupError(f"저장소 어댑터 {name} 이 없다. 있는 것: {', '.join(ADAPTERS)}")
    if not bucket or not region:
        raise StorageSetupError("버킷(bucket)과 리전(region)이 없다. s3 어댑터는 환경 변수를 스스로 읽지 않는다")
    if (access_key_id is None) != (secret_access_key is None):
        raise StorageSetupError("접근 키와 비밀 키는 둘 다 주거나 둘 다 주지 않는다")
    if upload_ttl_s <= 0:
        raise StorageSetupError("서명한 주소의 수명(upload_ttl_s)은 0보다 커야 한다")
    config = BotoConfig(
        signature_version="s3v4",
        # 판이 오르면 바뀔 수 있는 기본값(when_supported)에 기대지 않고 둘 다 명시한다. TS 어댑터와 같다.
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
        s3={"addressing_style": "path" if force_path_style else "auto"},
        connect_timeout=CONNECT_TIMEOUT_S,
        read_timeout=READ_TIMEOUT_S,
        retries={"total_max_attempts": TOTAL_MAX_ATTEMPTS, "mode": "standard"},
    )
    internal = _client(
        region=region, endpoint=endpoint, config=config, access_key_id=access_key_id, secret=secret_access_key
    )
    external = _client(
        region=region,
        endpoint=public_endpoint or endpoint,
        config=config,
        access_key_id=access_key_id,
        secret=secret_access_key,
    )
    return S3Storage(internal=internal, external=external, bucket=bucket, upload_ttl_s=upload_ttl_s)
