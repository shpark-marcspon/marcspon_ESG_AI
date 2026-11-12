# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""저장소 포트의 어댑터 둘(s3 · fake). 순수 층: DB 없음, 소켓 막힘(뿌리 conftest 의 blocked_network).

s3 어댑터는 botocore 의 Stubber 로 잰다(요청이 나가지 않는다). ★ 클라이언트에는 늘 키를 명시로 준다:
안 주면 boto3 가 인스턴스 메타데이터 주소(169.254.169.254)를 찾아 나가 소켓 막기에 걸린다.

무효 조건: 떠 있는 저장소에 보낸 것이 아니다. 실제 Versity 에서 도는지는 tests_integration/test_upload_flow.py 가 잰다.
Stubber 의 오류는 우리가 적은 상태 코드·Error.Code 그대로다(저장소가 실제로 무엇을 내는지는 탐침의 값이다.
core/resources/storage.py 의 머리말).
"""

import hashlib
import io
from typing import Any, get_type_hints
from urllib.parse import parse_qs, urlsplit

import pytest
from botocore.exceptions import EndpointConnectionError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from esgapi.core.resources import storage as adapter
from esgapi.core.resources.ports import storage as port
from esgapi.core.resources.ports.storage import (
    ObjectBytes,
    ObjectFound,
    ObjectMissing,
    ObjectPut,
    ObjectStorage,
    ObjectTooLarge,
    PresignedUpload,
    StorageDenied,
    StorageUnavailable,
)
from esgapi.core.resources.storage import S3Storage, StorageSetupError
from esgapi.core.tests.resource_fakes import FakeStorage

BUCKET = "esg-documents"
KEY = "companies/7/documents/0b0e7c1e-0000-4000-8000-000000000001/original"
SECRET = "synthetic-secret-key-0000"
INTERNAL = "http://storage:7070"
PUBLIC = "http://localhost:19000"
WHERE = {"Bucket": BUCKET, "Key": KEY}


def s3(**overrides: Any) -> S3Storage:
    options: dict[str, Any] = {
        "bucket": BUCKET,
        "region": "ap-northeast-2",
        "endpoint": INTERNAL,
        "public_endpoint": PUBLIC,
        "force_path_style": True,
        "access_key_id": "synthetic-access-key",
        "secret_access_key": SECRET,
        "upload_ttl_s": 300,
        **overrides,
    }
    made = adapter.make("s3", **options)
    assert isinstance(made, S3Storage)
    return made


class CountingBytes(io.BytesIO):
    """읽힌 바이트 수를 센다(어댑터가 본문을 어디까지 읽었는지 본다)."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.read_bytes = 0

    def read(self, size: int | None = -1) -> bytes:
        chunk = super().read(size)
        self.read_bytes += len(chunk)
        return chunk


def body_of(data: bytes, *, declared: int | None = None) -> tuple[CountingBytes, StreamingBody]:
    raw = CountingBytes(data)
    return raw, StreamingBody(raw, len(data) if declared is None else declared)


# ── 서명 주소 ─────────────────────────────────────────────────────────


def test_the_upload_url_is_signed_for_the_public_name_with_the_size_as_a_condition(
    blocked_network: list[object],
) -> None:
    storage = s3()
    upload = storage.presign_upload(KEY, content_length=5009)
    assert isinstance(upload, PresignedUpload)
    assert (upload.method, upload.expires_in_s) == ("PUT", 300)

    parts = urlsplit(upload.url)
    # 주소의 호스트는 바깥 이름이다(클라이언트가 닿는 이름). 안쪽 이름(storage:7070)이 아니다.
    assert (parts.scheme, parts.netloc) == ("http", "localhost:19000")
    assert parts.path == f"/{BUCKET}/{KEY}"  # path style
    query = parse_qs(parts.query)
    assert sorted(query) == [
        "X-Amz-Algorithm",
        "X-Amz-Credential",
        "X-Amz-Date",
        "X-Amz-Expires",
        "X-Amz-Signature",
        "X-Amz-SignedHeaders",
    ]
    assert query["X-Amz-Expires"] == ["300"]
    # 크기는 서명하고 형식(content-type)은 서명하지 않는다. 주소의 글자는 `content-length%3Bhost` 다(풀어서 견준다).
    assert query["X-Amz-SignedHeaders"] == ["content-length;host"]
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert SECRET not in upload.url
    assert blocked_network == []  # 서명은 계산일 뿐이다: 소켓을 열려 하지 않았다


def test_signing_falls_back_to_the_endpoint_when_there_is_no_public_one() -> None:
    upload = s3(public_endpoint=None).presign_upload(KEY, content_length=1)
    assert urlsplit(upload.url).netloc == "storage:7070"


def test_the_ttl_given_to_make_is_the_ttl_of_the_url() -> None:
    upload = s3(upload_ttl_s=42).presign_upload(KEY, content_length=1)
    assert upload.expires_in_s == 42
    assert parse_qs(urlsplit(upload.url).query)["X-Amz-Expires"] == ["42"]


def test_two_clients_one_per_name_with_the_written_down_config() -> None:
    storage = s3()
    assert storage.internal.meta.endpoint_url == INTERNAL
    assert storage.external.meta.endpoint_url == PUBLIC
    for client in (storage.internal, storage.external):
        config = client.meta.config
        assert config.signature_version == "s3v4"
        assert config.request_checksum_calculation == "when_required"
        assert config.response_checksum_validation == "when_required"
        assert config.s3["addressing_style"] == "path"
        assert (config.connect_timeout, config.read_timeout) == (adapter.CONNECT_TIMEOUT_S, adapter.READ_TIMEOUT_S)
        assert config.retries == {"total_max_attempts": adapter.TOTAL_MAX_ATTEMPTS, "mode": "standard"}
    # 최악의 합(어림)이 gunicorn 의 timeout 30초보다 한참 짧다: (2 + 5) × 2 = 14초.
    assert (adapter.CONNECT_TIMEOUT_S + adapter.READ_TIMEOUT_S) * adapter.TOTAL_MAX_ATTEMPTS == 14
    assert s3(force_path_style=False).internal.meta.config.s3["addressing_style"] == "auto"


# ── head ──────────────────────────────────────────────────────────────


def test_head_goes_to_the_internal_client_and_keeps_the_etag_as_given(blocked_network: list[object]) -> None:
    storage = s3()
    etag = '"0755d5630000000000000000aaaa7203"'  # 저장소가 주는 꼴: 따옴표를 낀 32자(34자)
    with Stubber(storage.internal) as stub:
        stub.add_response("head_object", {"ContentLength": 5009, "ETag": etag}, WHERE)
        result = storage.head(KEY)
        stub.assert_no_pending_responses()
    # external 에는 응답을 심지 않았다. head 가 그리로 갔다면 소켓을 열려다 막혀 StorageUnavailable 이다.
    assert result == ObjectFound(size_bytes=5009, etag=etag)
    assert len(etag) == 34
    assert blocked_network == []


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (404, "404", ObjectMissing),
        (404, "NoSuchKey", ObjectMissing),
        (404, "NoSuchBucket", ObjectMissing),
        (403, "403", StorageDenied),
        (403, "SignatureDoesNotMatch", StorageDenied),
        (403, "AccessDenied", StorageDenied),
        (500, "InternalError", StorageUnavailable),
        (503, "SlowDown", StorageUnavailable),
        (
            400,
            "404",
            StorageUnavailable,
        ),  # 가름은 상태 코드다: Error.Code 가 "404" 여도 상태가 400 이면 「없다」가 아니다
    ],
)
def test_head_and_get_sort_failures_by_http_status_only(status: int, code: str, expected: type) -> None:
    storage = s3()
    with Stubber(storage.internal) as stub:
        stub.add_client_error("head_object", service_error_code=code, http_status_code=status)
        stub.add_client_error("get_object", service_error_code=code, http_status_code=status)
        assert type(storage.head(KEY)) is expected
        assert type(storage.get(KEY, max_bytes=10)) is expected


def test_unreachable_storage_is_unavailable_not_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = s3()

    def unreachable(**kwargs: Any) -> Any:
        raise EndpointConnectionError(endpoint_url=INTERNAL)

    monkeypatch.setattr(storage.internal, "head_object", unreachable)
    monkeypatch.setattr(storage.internal, "get_object", unreachable)
    head = storage.head(KEY)
    assert isinstance(head, StorageUnavailable)
    assert INTERNAL not in head.detail  # 속사정(주소)은 갈래에 싣지 않는다
    assert isinstance(storage.get(KEY, max_bytes=10), StorageUnavailable)


# ── get ───────────────────────────────────────────────────────────────


def test_get_returns_the_bytes_when_within_the_limit() -> None:
    storage = s3()
    data = b"%PDF-synthetic " * 10
    for max_bytes in (len(data), len(data) + 1):
        _raw, body = body_of(data)
        with Stubber(storage.internal) as stub:
            stub.add_response("get_object", {"Body": body, "ContentLength": len(data), "ETag": '"e"'}, WHERE)
            result = storage.get(KEY, max_bytes=max_bytes)
        assert isinstance(result, ObjectBytes)
        assert result == ObjectBytes(data=data, etag='"e"')
        assert hashlib.sha256(result.data).hexdigest() == hashlib.sha256(data).hexdigest()


def test_get_does_not_read_the_body_when_the_declared_length_is_over_the_limit() -> None:
    storage = s3()
    data = b"x" * 100
    raw, body = body_of(data)
    with Stubber(storage.internal) as stub:
        stub.add_response("get_object", {"Body": body, "ContentLength": 100, "ETag": '"e"'}, WHERE)
        result = storage.get(KEY, max_bytes=99)
    assert result == ObjectTooLarge(max_bytes=99)
    assert raw.read_bytes == 0  # 본문을 읽지 않았다
    assert raw.closed


def test_get_stops_at_the_limit_even_when_the_declared_length_lies() -> None:
    """ContentLength 가 거짓으로 작아도(10) 본문 100바이트를 다 읽지 않는다: max_bytes + 1 에서 끊는다."""
    storage = s3()
    raw, body = body_of(b"x" * 100, declared=10)
    with Stubber(storage.internal) as stub:
        stub.add_response("get_object", {"Body": body, "ContentLength": 10, "ETag": '"e"'}, WHERE)
        result = storage.get(KEY, max_bytes=50)
    assert result == ObjectTooLarge(max_bytes=50)
    assert raw.read_bytes == 51


def test_get_without_a_declared_length_also_stops_at_the_limit() -> None:
    storage = s3()
    raw, body = body_of(b"x" * 100)
    with Stubber(storage.internal) as stub:
        stub.add_response("get_object", {"Body": body, "ETag": '"e"'}, WHERE)
        result = storage.get(KEY, max_bytes=50)
    assert result == ObjectTooLarge(max_bytes=50)
    assert raw.read_bytes == 51


# ── put(X1b-1 — 실행기의 출력·단계 파일) ─────────────────────────────


def test_put_goes_to_the_internal_client_with_the_type_and_length() -> None:
    storage = s3()
    etag = '"0755d5630000000000000000aaaa7203"'
    expected = {**WHERE, "Body": b"xlsx-bytes", "ContentType": "application/x-synthetic", "ContentLength": 10}
    with Stubber(storage.internal) as stub:
        stub.add_response("put_object", {"ETag": etag}, expected)
        result = storage.put(KEY, content=b"xlsx-bytes", media_type="application/x-synthetic")
        stub.assert_no_pending_responses()
    assert result == ObjectPut(etag=etag)


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (404, "NoSuchBucket", StorageUnavailable),  # 쓰기의 404 는 「없다」가 아니다(버킷이 없다)
        (403, "AccessDenied", StorageDenied),
        (500, "InternalError", StorageUnavailable),
    ],
)
def test_put_sorts_failures_by_http_status_and_never_answers_missing(status: int, code: str, expected: type) -> None:
    storage = s3()
    with Stubber(storage.internal) as stub:
        stub.add_client_error("put_object", service_error_code=code, http_status_code=status)
        assert type(storage.put(KEY, content=b"x", media_type="text/plain")) is expected


def test_put_to_an_unreachable_storage_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = s3()

    def unreachable(**kwargs: Any) -> Any:
        raise EndpointConnectionError(endpoint_url=INTERNAL)

    monkeypatch.setattr(storage.internal, "put_object", unreachable)
    result = storage.put(KEY, content=b"x", media_type="text/plain")
    assert isinstance(result, StorageUnavailable)
    assert INTERNAL not in result.detail


# ── 포트의 꼴 ─────────────────────────────────────────────────────────


def test_the_port_has_exactly_three_methods_and_no_download_url_put_or_delete() -> None:
    # 이름은 X1b-1 앞의 것이다(노드 id 를 지키려고 그대로 — 감독 처분 sid:MARC-TICK-179): 실행기가 put 을 세워 넷이다.
    methods = {name for name in vars(ObjectStorage) if not name.startswith("_")}
    assert methods == {"presign_upload", "head", "get", "put"}
    for cls in (ObjectStorage, S3Storage):
        for absent in ("presign_download", "delete"):
            assert not hasattr(cls, absent), (cls.__name__, absent)
    # 갈래의 합이 글자로 적은 것과 같다.
    assert get_type_hints(port.ObjectStorage.head)["return"] == port.HeadResult
    assert set(port.HeadResult.__args__) == {ObjectFound, ObjectMissing, StorageDenied, StorageUnavailable}
    assert set(port.GetResult.__args__) == {
        ObjectBytes,
        ObjectMissing,
        ObjectTooLarge,
        StorageDenied,
        StorageUnavailable,
    }
    assert set(port.PutResult.__args__) == {ObjectPut, StorageDenied, StorageUnavailable}


# ── 만들기 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "overrides",
    [
        {"bucket": None},
        {"bucket": ""},
        {"region": None},
        {"secret_access_key": None},  # 키가 하나뿐
        {"access_key_id": None},
        {"upload_ttl_s": 0},
    ],
)
def test_s3_is_not_made_from_half_a_setup(overrides: dict[str, Any]) -> None:
    with pytest.raises(StorageSetupError):
        s3(**overrides)


def test_unknown_adapter_name_is_a_named_error() -> None:
    with pytest.raises(StorageSetupError, match=r"있는 것: s3$"):
        adapter.make("gcs")


def test_the_product_module_has_no_fake_and_make_refuses_it() -> None:
    """가짜는 시험 도우미(core/tests/resource_fakes.py)에만 있다. 제품의 make 는 "fake" 를 고르지 않는다(밴드 CU2)."""
    assert adapter.ADAPTERS == ("s3",)
    assert not hasattr(adapter, "FakeStorage")
    with pytest.raises(StorageSetupError, match="저장소 어댑터 fake 이 없다"):
        adapter.make("fake")


# ── 가짜 ──────────────────────────────────────────────────────────────


def test_the_fake_gives_the_same_branches() -> None:
    fake = FakeStorage(upload_ttl_s=120)
    as_port: ObjectStorage = fake  # 포트를 만족한다(pyright 가 문다)
    assert as_port is fake
    upload = fake.presign_upload(KEY, content_length=7)
    assert (upload.method, upload.expires_in_s, fake.presigned) == ("PUT", 120, [(KEY, 7)])
    assert urlsplit(upload.url).hostname == "fake-storage.invalid"

    assert fake.head(KEY) == ObjectMissing()
    assert fake.get(KEY, max_bytes=10) == ObjectMissing()

    etag = fake.put(KEY, b"1234567")
    # 저장소와 같은 꼴: 따옴표를 낀 md5 (34자)
    assert etag == f'"{hashlib.md5(b"1234567", usedforsecurity=False).hexdigest()}"'
    assert fake.head(KEY) == ObjectFound(size_bytes=7, etag=etag)
    assert fake.get(KEY, max_bytes=7) == ObjectBytes(data=b"1234567", etag=etag)
    assert fake.get(KEY, max_bytes=6) == ObjectTooLarge(max_bytes=6)

    fake.fail_with = StorageDenied("가짜 403")
    assert fake.head(KEY) == StorageDenied("가짜 403")
    assert fake.get(KEY, max_bytes=7) == StorageDenied("가짜 403")
    fake.fail_with = StorageUnavailable("가짜 닿지 못함")
    assert fake.head(KEY) == StorageUnavailable("가짜 닿지 못함")
    assert (len(fake.head_calls), len(fake.get_calls)) == (4, 4)

    # 포트의 쓰기(실행기): 읽기의 fail_with 와 따로 실패시킨다.
    fake.fail_with = None
    written = fake.put("out/r.bin", content=b"abc", media_type="application/x-synthetic")
    assert written == ObjectPut(etag=f'"{hashlib.md5(b"abc", usedforsecurity=False).hexdigest()}"')
    assert isinstance(written, ObjectPut)
    assert fake.get("out/r.bin", max_bytes=3) == ObjectBytes(data=b"abc", etag=written.etag)
    assert (fake.put_calls, fake.media_types) == (["out/r.bin"], {"out/r.bin": "application/x-synthetic"})
    fake.put_fail_with = StorageUnavailable("가짜 쓰기 실패")
    assert fake.put("out/s.bin", content=b"z", media_type="text/plain") == StorageUnavailable("가짜 쓰기 실패")
    assert "out/s.bin" not in fake.objects
