"""원본 내려받기의 왕복과 올림 확인의 쪽 수·글자 층을 떠 있는 컨테이너(api-py · postgres · storage)에 호스트에서
실제로 보낸다(X1b-2a).

    교환 → POST /documents → 받은 주소로 저장소에 직접 PUT → POST …/confirm → GET …/file

재는 것: 서명 PUT → 서버의 저장소 get → 이진 응답의 바이트가 올린 것과 같은가(가짜 저장소는 같은 객체를 돌려줘
이것을 못 잰다). 올림 확인 응답의 pageCount·hasText 가 시험이 지은 PDF 의 값인가 — 컨테이너 안의 실제 자식
프로세스·실제 RLIMIT_AS 아래에서(「실패는 null」이 조용히 모든 값을 null 로 만드는 것을 잡는다).

PDF 는 시험이 짓는다(esgapi/core/tests/resource_fakes.build_pdf — 쪽 7·글 있음). 실제 문서가 아니다.

★ 무효 조건:
  - 저장소는 Versity Gateway 다. 실제 S3 에서 같은지는 재지 않았다.
  - 워커(worker-py)를 멈춘 채 잰다(test_upload_flow.py 와 같은 까닭 — 분해 일감이 queued 에 머문다).
  - 올린 객체는 저장소에 남는다(`docker compose down -v` 가 볼륨째 지운다). 표의 행은 이 테스트가 끝에서 지운다.
"""

from collections.abc import Iterator
from typing import Any

import httpx
import psycopg
import pytest

from esgapi.core.tests.resource_fakes import build_pdf
from tests_integration.conftest import company_id_of, compose
from tests_integration.test_flow import exchange

Owner = psycopg.Connection[tuple[Any, ...]]
PAGES = 7
FILE_NAME = "보고서 원본.pdf"


@pytest.fixture(scope="module", autouse=True)
def worker_stopped() -> Iterator[None]:
    compose("stop", "worker-py")
    try:
        yield
    finally:
        compose("start", "worker-py")


@pytest.fixture
def cleanup(owner: Owner, two_tenants: tuple[str, str]) -> Iterator[tuple[str, str]]:
    """이 실행이 만든 문서·일감·감사 행을 끝에서 주인 연결로 지운다(two_tenants 보다 먼저)."""
    yield two_tenants
    companies = [company_id_of(owner, subdomain) for subdomain in two_tenants]
    owner.execute("DELETE FROM run_jobs WHERE company_id = ANY(%s)", [companies])
    owner.execute("DELETE FROM core_documents WHERE company_id = ANY(%s)", [companies])
    owner.execute("DELETE FROM core_audit_events WHERE company_id = ANY(%s)", [companies])


def test_the_original_round_trips_through_the_server_and_the_confirm_measures_it(
    http: httpx.Client, owner: Owner, cleanup: tuple[str, str]
) -> None:
    tenant_a, tenant_b = cleanup
    company_a = company_id_of(owner, tenant_a)
    pdf = build_pdf(PAGES, text="Integration")
    alice = exchange(http, tenant=tenant_a, sub="it-file-alice")
    bob = exchange(http, tenant=tenant_b, sub="it-file-bob")

    created = http.post("/documents", headers=alice, json={"fileName": FILE_NAME, "sizeBytes": len(pdf)})
    assert created.status_code == 201, created.text
    document_id: int = created.json()["document"]["id"]
    put = httpx.put(created.json()["upload"]["url"], content=pdf, timeout=20.0)
    assert put.status_code == 200, put.text

    # 올림 확인: 컨테이너 안의 자식 프로세스가 잰 값(쪽 7·글자 있음). null 이면 재기가 조용히 실패한 것이다.
    confirmed = http.post(f"/documents/{document_id}/confirm", headers=alice, timeout=20.0)
    assert confirmed.status_code == 200, confirmed.text
    document = confirmed.json()["document"]
    assert (document["status"], document["pageCount"], document["hasText"]) == ("uploaded", PAGES, True)
    assert http.get(f"/documents/{document_id}", headers=alice).json()["document"]["hasText"] is True

    # 원본 내려받기: 서버가 저장소에서 읽어 그 바이트를 그대로 낸다.
    got = http.get(f"/documents/{document_id}/file", headers=alice, timeout=20.0)
    assert got.status_code == 200, got.text
    assert got.content == pdf
    assert (got.headers["content-type"], got.headers["x-content-type-options"]) == ("application/pdf", "nosniff")
    assert got.headers["content-disposition"].startswith("attachment; filename*=utf-8''")
    lines = owner.execute(
        "SELECT action, target_id FROM core_audit_events WHERE company_id = %s AND action = 'download'", [company_a]
    ).fetchall()
    assert lines == [("download", document_id)]

    # 다른 회사에게는 없다(저장소에 닿기 전 404).
    theirs = http.get(f"/documents/{document_id}/file", headers=bob)
    assert (theirs.status_code, theirs.json()["error"]["code"]) == (404, "NOT_FOUND")
