"""문서 올리기 한 줄기를 떠 있는 컨테이너(api-py · postgres · storage)에 호스트에서 실제로 보낸다.

    교환 → POST /documents → 받은 주소로 저장소에 직접 PUT → POST …/confirm → GET …

재는 것: 서명된 주소가 로컬 저장소(Versity)에서 통하는가, 주소의 호스트가 바깥 이름인가, 크기의 서명 조건을 저장소가
지키는가, 올림 확인이 저장소의 크기와 ETag 를 적는가, **api-py 로 간 요청에 PDF 가 없었는가**, 다른 테넌트에게 안
보이는가. 그리고 컨테이너 **안에서** 제품 코드의 어댑터를 직접 불러(`docker compose exec -T api-py python -c …`.
test_parser_flow.py 의 꼴) get 과 갈래들이 떠 있는 저장소에서 도는가.

원본은 저장소에 있는 지은 PDF(data/ruled-table.pdf. 4×4 표 하나, 숫자는 지어낸 것)다. 실제 문서가 아니다.

★ 무효 조건:
  - 「서버는 바이트를 받지 않았다」는 이 테스트가 **보낸 요청의 목록**으로 단언한 것이다. 서버 쪽에서 잰 것이 아니다.
  - 저장소는 Versity Gateway v1.8.0 이다. 실제 S3 에서 같은지는 재지 않았다(404·403 의 가름, 크기의 강제).
  - 워커(worker-py)를 멈춘 채 잰다(아래 고정물): 일감은 queued 에서 멈춘다. 분해까지는 test_worker_flow.py 가 잰다.
  - 올린 객체는 저장소에 남는다(`docker compose down -v` 가 볼륨째 지운다). 표의 행은 이 테스트가 끝에서 지운다.
"""

import hashlib
import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import psycopg
import pytest

from tests_integration.conftest import API, ENV, REPO_ROOT, company_id_of, compose
from tests_integration.test_flow import exchange

Owner = psycopg.Connection[tuple[Any, ...]]
PDF = Path(__file__).resolve().parent / "data" / "ruled-table.pdf"
FILE_NAME = "ruled-table.pdf"
STORAGE_HOST = f"localhost:{ENV.get('STORAGE_PORT', '19000')}"


@pytest.fixture(scope="module", autouse=True)
def worker_stopped() -> Iterator[None]:
    """이 파일이 도는 동안 워커(worker-py)를 멈춘다. 이 파일이 재는 것은 워커 없는 올리기다(일감이 queued 로 남는다).

    워커가 살아 있으면 올림 확인 직후 일감이 processing → done 으로 가고 sha256 이 적혀 아래 단언이 흔들린다.
    꺼 둔 동안 큐에 쌓인 쪽지는 워커를 켠 뒤 JobNotFound 로 끝난다(이 파일이 행을 지웠다).
    """
    compose("stop", "worker-py")
    try:
        yield
    finally:
        compose("start", "worker-py")


@pytest.fixture
def cleanup(owner: Owner, two_tenants: tuple[str, str]) -> Iterator[tuple[str, str]]:
    """이 실행이 만든 문서·일감 행을 끝에서 주인 연결로 지운다(두 회사의 id 로 — subdomain 에서 읽는다).

    conftest 의 two_tenants 는 이 표 둘을 모른다. 그것보다 먼저 지워야 한다(고정물은 거꾸로 정리된다).
    """
    yield two_tenants
    companies = [company_id_of(owner, subdomain) for subdomain in two_tenants]
    owner.execute("DELETE FROM run_jobs WHERE company_id = ANY(%s)", [companies])
    owner.execute("DELETE FROM core_documents WHERE company_id = ANY(%s)", [companies])


class Recorder:
    """api-py 로 보낸 요청의 (메서드, 경로, 본문의 바이트)를 적어 둔다."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, bytes]] = []

    def __call__(self, request: httpx.Request) -> None:
        self.sent.append((request.method, request.url.path, request.read()))


@pytest.fixture
def recorded() -> Iterator[tuple[httpx.Client, Recorder]]:
    recorder = Recorder()
    with httpx.Client(base_url=API, timeout=20.0, event_hooks={"request": [recorder]}) as client:
        yield client, recorder


def rows_of(owner: Owner, company_id: int) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT d.id, d.status, d.size_bytes, d.etag, d.sha256, "
        "(SELECT count(*) FROM run_jobs j WHERE j.document_id = d.id AND j.company_id = d.company_id) "
        "FROM core_documents d WHERE d.company_id = %s",
        [company_id],
    ).fetchall()


def test_upload_goes_straight_to_the_storage_and_the_server_only_keeps_the_state(
    recorded: tuple[httpx.Client, Recorder], owner: Owner, cleanup: tuple[str, str]
) -> None:
    http, recorder = recorded
    tenant_a, tenant_b = cleanup
    company_a, company_b = company_id_of(owner, tenant_a), company_id_of(owner, tenant_b)
    pdf = PDF.read_bytes()
    assert pdf.startswith(b"%PDF-") and len(pdf) > 1000
    alice = exchange(http, tenant=tenant_a, sub="it-upload-alice")
    bob = exchange(http, tenant=tenant_b, sub="it-upload-bob")

    # 1. 만들기: 이름과 크기만 간다.
    created = http.post("/documents", headers=alice, json={"fileName": FILE_NAME, "sizeBytes": len(pdf)})
    assert created.status_code == 201, created.text
    document: dict[str, Any] = created.json()["document"]
    upload: dict[str, Any] = created.json()["upload"]
    document_id: int = document["id"]
    upload_url: str = upload["url"]
    assert (document["status"], document["sizeBytes"], document["etag"]) == ("awaiting_upload", len(pdf), None)
    assert (upload["method"], upload["expiresInSeconds"]) == ("PUT", int(ENV.get("UPLOAD_URL_TTL_SECONDS") or 300))

    # 서명된 주소: 호스트는 바깥 이름(내 컴퓨터에서 닿는 저장소의 포트), 경로는 버킷/키, 크기가 서명 조건이다.
    parts = urlsplit(upload_url)
    assert (parts.scheme, parts.netloc) == ("http", STORAGE_HOST)
    # 키: 회사 id(subdomain 이 아니다)와 따로 지은 UUID(문서 id 가 아니다).
    key = re.fullmatch(
        rf"/{re.escape(ENV['S3_BUCKET'])}/companies/{company_a}/documents/([0-9a-f-]{{36}})/original", parts.path
    )
    assert key is not None, parts.path
    assert key.group(1) != str(document_id)
    query = parse_qs(parts.query)
    assert query["X-Amz-SignedHeaders"] == ["content-length;host"]
    assert ENV["STORAGE_SECRET_KEY"] not in upload_url

    # 2. 올리기 전의 올림 확인은 409 다. 문서는 그대로다.
    early = http.post(f"/documents/{document_id}/confirm", headers=alice)
    assert (early.status_code, early.json()["error"]["code"]) == (409, "NOT_UPLOADED")

    # 3. 그 주소로 저장소에 직접 올린다. api-py 를 지나지 않는다(다른 클라이언트, 쿠키 없음).
    #    먼저 한 바이트 더 긴 본문: 크기의 서명 조건에 걸려 403 이다(저장소가 지킨다).
    too_long = httpx.put(upload_url, content=pdf + b"!", timeout=20.0)
    assert too_long.status_code == 403, too_long.text
    still_missing = http.post(f"/documents/{document_id}/confirm", headers=alice)
    assert (still_missing.status_code, still_missing.json()["error"]["code"]) == (409, "NOT_UPLOADED")
    put = httpx.put(upload_url, content=pdf, timeout=20.0)
    assert put.status_code == 200, put.text

    # 4. 올림 확인: 서버가 저장소에 물어 크기와 ETag 를 적는다. 일감 하나가 queued 로 생긴다.
    confirmed = http.post(f"/documents/{document_id}/confirm", headers=alice)
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert (body["document"]["status"], body["document"]["sizeBytes"]) == ("uploaded", len(pdf))
    etag = body["document"]["etag"]
    # Versity 의 ETag: 따옴표를 낀 본문의 md5 (34자). 저장소가 준 글자 그대로 적혔다.
    assert etag == f'"{hashlib.md5(pdf, usedforsecurity=False).hexdigest()}"'
    assert [(job["kind"], job["status"], job["attempts"]) for job in body["jobs"]] == [("parse", "queued", 0)]

    # 5. 상태 보기가 같은 답을 준다. 다시 확인해도 같은 답이고 일감은 하나다.
    assert http.get(f"/documents/{document_id}", headers=alice).json() == body
    assert http.post(f"/documents/{document_id}/confirm", headers=alice).json() == body

    # 6. 다른 테넌트의 세션에게는 없다.
    for response in (
        http.get(f"/documents/{document_id}", headers=bob),
        http.post(f"/documents/{document_id}/confirm", headers=bob),
    ):
        assert (response.status_code, response.json()["error"]["code"]) == (404, "NOT_FOUND")

    # 7. 주인이 센 행(분모): 그 테넌트의 문서 1, 일감 1. sha256 칸은 비어 있다(이 밴드는 쓰지 않는다).
    assert rows_of(owner, company_a) == [(document_id, "uploaded", len(pdf), etag, None, 1)]
    assert rows_of(owner, company_b) == []

    # 8. 서버는 바이트를 받지 않았다: api-py 로 보낸 요청 가운데 PDF 를 실은 것이 0 이다(보낸 요청의 목록으로 단언).
    to_api = recorder.sent
    assert len(to_api) == 10  # 교환 2 + 만들기 1 + 올림 확인 5 + 상태 보기 2
    assert [entry for entry in to_api if b"%PDF" in entry[2] or len(entry[2]) >= len(pdf)] == []
    creates = [entry[2] for entry in to_api if (entry[0], entry[1]) == ("POST", "/api/documents")]
    assert len(creates) == 1 and len(creates[0]) < 100  # 이름과 크기뿐인 수십 바이트
    assert json.loads(creates[0]) == {"fileName": FILE_NAME, "sizeBytes": len(pdf)}
    confirms = [entry[2] for entry in to_api if entry[1].endswith("/confirm")]
    assert len(confirms) == 5 and all(sent == b"" for sent in confirms)  # 올림 확인에는 본문이 없다


# 컨테이너 안에서 도는 코드. 제품 코드만 import 한다(이미지에 테스트는 없다). 표준 입력은 올린 PDF 의 바이트.
INSIDE = """
import dataclasses, hashlib, json, sys
import django
django.setup()  # 컨테이너의 DJANGO_SETTINGS_MODULE(base): 서버와 같은 설정을 환경 변수에서 읽는다
from esgapi.core.resources import storage as adapter
from esgapi.core.conf import app_config
from esgapi.core.service.services import documents as services

pdf = sys.stdin.buffer.read()
key = sys.argv[1]
settings = app_config().storage
storage = services.default_storage()  # 경로 함수가 쓰는 바로 그 길
out = {"bytes": len(pdf), "endpoint": settings.endpoint, "publicEndpoint": settings.public_endpoint,
       "class": type(storage).__name__}

head = storage.head(key)
out["head"] = {"type": type(head).__name__, "size": getattr(head, "size_bytes", None),
               "etag": getattr(head, "etag", None)}
got = storage.get(key, max_bytes=len(pdf))
out["get"] = {"type": type(got).__name__, "etag": getattr(got, "etag", None),
              "sha256": hashlib.sha256(got.data).hexdigest() if hasattr(got, "data") else None}
out["getOneByteShort"] = type(storage.get(key, max_bytes=len(pdf) - 1)).__name__
out["headMissing"] = type(storage.head(key + ".no-such-object")).__name__
out["getMissing"] = type(storage.get(key + ".no-such-object", max_bytes=10)).__name__

def variant(**changes):
    s = dataclasses.replace(settings, **changes)
    return adapter.make("s3", bucket=s.bucket, region=s.region, endpoint=s.endpoint,
                        public_endpoint=s.public_endpoint, force_path_style=s.force_path_style,
                        access_key_id=s.access_key_id, secret_access_key=s.secret_access_key,
                        upload_ttl_s=s.upload_url_ttl_seconds)

out["headWrongSecret"] = type(variant(secret_access_key="wrong-" + settings.secret_access_key).head(key)).__name__
out["headNoSuchBucket"] = type(variant(bucket=settings.bucket + "-no-such-bucket").head(key)).__name__
out["headUnreachable"] = type(variant(endpoint="http://127.0.0.1:9").head(key)).__name__
print(json.dumps(out))
"""


def run_inside(pdf: bytes, key: str) -> dict[str, Any]:
    done = subprocess.run(
        ["docker", "compose", "exec", "-T", "api-py", "python", "-c", INSIDE, key],
        cwd=REPO_ROOT,
        input=pdf,
        capture_output=True,
        check=False,
    )
    assert done.returncode == 0, f"컨테이너 안의 코드가 {done.returncode} 로 끝났다:\n{done.stderr.decode('utf-8')}"
    # 마지막 줄이 그 JSON 이다(앞에 기록 줄이 섞여도 된다: 서버의 설정은 기록을 표준 출력으로 낸다).
    lines = done.stdout.decode("utf-8").splitlines()
    assert lines, done.stderr.decode("utf-8")
    out: dict[str, Any] = json.loads(lines[-1])
    return out


def test_the_adapter_works_against_the_running_storage(
    http: httpx.Client, owner: Owner, cleanup: tuple[str, str]
) -> None:
    """제품 코드의 어댑터를 컨테이너 안에서 직접 부른다(경로를 거치지 않는다: get 을 부르는 경로가 아직 없다)."""
    tenant_a, _tenant_b = cleanup
    pdf = PDF.read_bytes()
    alice = exchange(http, tenant=tenant_a, sub="it-adapter-alice")
    created = http.post("/documents", headers=alice, json={"fileName": FILE_NAME, "sizeBytes": len(pdf)}).json()
    assert httpx.put(created["upload"]["url"], content=pdf, timeout=20.0).status_code == 200
    row = owner.execute("SELECT storage_key FROM core_documents WHERE id = %s", [created["document"]["id"]]).fetchone()
    assert row is not None
    key: str = row[0]

    out = run_inside(pdf, key)
    md5 = hashlib.md5(pdf, usedforsecurity=False).hexdigest()
    # 컨테이너는 안쪽 이름으로 저장소에 묻고, 바깥 이름으로 서명한다.
    assert (out["bytes"], out["class"]) == (len(pdf), "S3Storage")
    assert (out["endpoint"], out["publicEndpoint"]) == ("http://storage:7070", f"http://{STORAGE_HOST}")
    assert out["head"] == {"type": "ObjectFound", "size": len(pdf), "etag": f'"{md5}"'}
    # get: 상한이 바이트 수와 같으면 바이트 그대로(sha256 일치), 1 작으면 ObjectTooLarge.
    assert out["get"] == {"type": "ObjectBytes", "sha256": hashlib.sha256(pdf).hexdigest(), "etag": f'"{md5}"'}
    assert out["getOneByteShort"] == "ObjectTooLarge"
    # 「없다」와 「권한 없다」가 다른 갈래다.
    assert (out["headMissing"], out["getMissing"]) == ("ObjectMissing", "ObjectMissing")
    assert out["headWrongSecret"] == "StorageDenied"  # 틀린 **비밀** 키 → 403
    # ★ 무효 조건을 사실로 적어 두는 단언: Versity 에서 없는 버킷은 404 라 「안 올라옴」과 같은 갈래로 읽힌다.
    assert out["headNoSuchBucket"] == "ObjectMissing"
    assert out["headUnreachable"] == "StorageUnavailable"
