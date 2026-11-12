"""실행 경로 넷(core/service/apis/runs.py)과 문서의 계약 먼저 두 경로(목록·판 사슬)를 진짜 DB 로 잰다. 업무 층.

밴드 XC: 몸이 없다. 재는 것은 「인증 → 꼴 → 권한 → 501」의 차례와 「쓰는 행 0」뿐이다(상태 코드와 error.code 까지).
400 은 E2 가 422 로 바꾸므로 상태만 본다. 행 수는 <Row>.unscoped 로 센다(분모: 앞에 만든 문서 1행).
★ 순수 층에 두지 못하는 까닭: 지금 미들웨어(core/tenancy/middleware.py)가 면제 넷 밖의 모든 요청에 atomic() 을 열어
  DB 없이 HTTP 를 부르면 401 조차 못 낸다(발주서 ★4). E1b 가 병합된 뒤 순수 층으로 옮기는 것은 후속이다.
★ 실행 넷 가운데 셋(목록·단건·내려받기)과 만들기의 나머지 갈래는 X1b-1 이 몸을 채웠다 — 여기서는 401 만 잰다.
  그 동작은 esgapi/runs/tests/service/apis/test_runs.py, 회사 격리는 tests/security/test_runs.py 가 잰다.

core 는 업무 모듈을 import 하지 않는다(계약 가). 로그인은 tests.support.http.login, 테넌트는 뿌리 conftest 의 tenants.
"""

import uuid
from typing import Any

import pytest
from django.test import Client

from esgapi.core.models import DocumentRow
from esgapi.core.permissions import CUSTOMER, OPERATION_POLICY, OPERATOR
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.models import JobRow
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

RUN_BODY: dict[str, Any] = {"module": "greenwash", "documentId": 1}
# operationId → (메서드, 경로, 본문). 꼴 검사를 지나는 가장 작은 요청이다. 세션이 없으면 여섯 다 401 이다.
SESSION_REQUIRED: dict[str, tuple[str, str, dict[str, Any] | None]] = {
    "runs_create": ("POST", "/api/runs", RUN_BODY),
    "runs_list": ("GET", "/api/runs?module=greenwash&status=queued&documentId=1&limit=100&offset=0", None),
    "runs_get": ("GET", "/api/runs/1", None),
    "runs_file_get": ("GET", "/api/runs/1/files/a.xlsx", None),
    "runs_segments_list": ("GET", "/api/runs/1/segments?step=x", None),  # RM1c ③(T15)
    "core_documents_list": ("GET", "/api/documents?reportYear=2025&q=a&limit=1", None),
    "core_documents_versions": ("GET", "/api/documents/1/versions", None),
}
# 그 가운데 아직 몸이 없는(501) 것: 없다. 실행의 나머지 셋(목록·단건·내려받기)은 X1b-1 이 몸을 채웠다 — 그 동작은
# esgapi/runs/tests/service/apis/test_runs.py 가 잰다. 문서 둘(목록·versions)은 X1b-2a 가 몸을 채웠다 — 그 동작은
# esgapi/core/tests/test_documents_api.py 가 잰다. 실행 만들기의 resumeFromRunId 갈래는 X1b-2b 가 몸을 채웠다.
CONTRACT_ONLY: dict[str, tuple[str, str, dict[str, Any] | None]] = {}
# 이어 돌기의 가장 작은 요청(앞 실행 1 은 없다)
RESUME: tuple[str, str, dict[str, Any] | None] = ("POST", "/api/runs", {**RUN_BODY, "resumeFromRunId": 1})


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    """이음매(`services.default_storage`)에 가짜 저장소를 꽂는다."""
    return plug_storage(monkeypatch, FakeStorage())


def send(client: Client, method: str, path: str, body: dict[str, Any] | None) -> Any:
    if method == "GET":
        return client.get(path)
    return client.post(path, data=body, content_type="application/json")


def error_of(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def rows() -> tuple[int, int]:
    return DocumentRow.unscoped.count(), JobRow.unscoped.count()


def one_document(client: Client) -> None:
    """분모: 문서 1행을 만들어 둔다(일감은 0)."""
    response = client.post(
        "/api/documents", data={"fileName": "a.pdf", "sizeBytes": 1}, content_type="application/json"
    )
    assert response.status_code == 201
    assert rows() == (1, 0)


def test_resuming_a_missing_run_is_404_after_auth(client: Client, tenants: None, fake: FakeStorage) -> None:
    """X1b-2b: 옛 「만들기의 resumeFromRunId 는 501」의 짝 — 몸이 서서 없는 문서·실행은 404 다(쓰는 행 0)."""
    assert login(client)["role"] == "editor"
    one_document(client)
    presigned = len(fake.presigned)
    assert error_of(send(client, *RESUME)) == (404, "NOT_FOUND")
    assert rows() == (1, 0)  # 쓰는 행 0(분모 1)
    assert (len(fake.presigned), fake.head_calls, fake.get_calls) == (presigned, [], [])


@pytest.mark.parametrize("operation_id", sorted(SESSION_REQUIRED))
def test_without_a_session_it_is_401(client: Client, tenants: None, operation_id: str) -> None:
    assert error_of(send(client, *SESSION_REQUIRED[operation_id])) == (401, "NO_SESSION")
    assert rows() == (0, 0)


def test_a_customer_cannot_create_a_run_when_the_cell_is_operator_only(
    client: Client, tenants: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """꼴이 맞는 본문을 보낸다: ninja 는 본문 검사(400)를 경로 함수(첫 문장의 권한)보다 먼저 한다.
    쿠키 세션은 역할과 무관하게 고객사 사용자다(가2) — 막힘은 칸을 운영 관리자 몫으로 옮겨 잰다."""
    login(client, role="viewer")
    monkeypatch.setitem(OPERATION_POLICY, "runs_create", OPERATOR)
    assert error_of(send(client, *RESUME)) == (403, "FORBIDDEN")
    # 꼴이 틀린 본문이면 400 이다(차례: 401 → 400 → 403 → 404).
    body = {"module": "greenwash", "documentId": "x"}  # ND1: documentId 빠짐은 꼴 오류가 아니다 — 타입을 틀린다
    assert client.post("/api/runs", data=body, content_type="application/json").status_code == 422
    assert rows() == (0, 0)
    monkeypatch.setitem(OPERATION_POLICY, "runs_create", CUSTOMER)
    assert error_of(send(client, *RESUME)) == (404, "NOT_FOUND")  # 분모: 옮기기 전에는 몸(404)까지 간다
    assert rows() == (0, 0)


def test_the_document_id_types_are_checked_per_route(client: Client, tenants: None, fake: FakeStorage) -> None:
    """같은 접두 /documents/{document_id} 의 세 경로(get·confirm·versions)는 모두 숫자 id 다(K1u-b — 처분 1 ㉠).

    ninja 는 `{document_id}` 를 Django 의 글자 무늬로 걸고 타입은 인자 검사가 본다:
    숫자면 경로 함수까지 가고(없는 문서는 404 — versions 도 X1b-2a 부터 몸이 있다), 숫자가 아니면(옛 uuid 글자
    포함) 400 이다.
    """
    login(client)
    some = uuid.uuid4()
    assert error_of(client.get("/api/documents/7")) == (404, "NOT_FOUND")
    assert error_of(client.post("/api/documents/7/confirm")) == (404, "NOT_FOUND")
    assert error_of(client.get("/api/documents/7/versions")) == (404, "NOT_FOUND")  # X1b-2a, 감독 c1 허락
    assert client.get(f"/api/documents/{some}").status_code == 422
    assert client.post(f"/api/documents/{some}/confirm").status_code == 422
    assert client.get(f"/api/documents/{some}/versions").status_code == 422
    assert rows() == (0, 0)


@pytest.mark.parametrize(
    "body",
    [
        {**RUN_BODY, "flowId": "greenwash"},  # @판 이 없다
        {**RUN_BODY, "flowId": "Greenwash.colab@1"},  # 대문자
        {**RUN_BODY, "tenantId": "tenant-b"},  # 모르는 칸
        {**RUN_BODY, "documentId": "1"},  # 글자를 정수로 받지 않는다
        {"module": "Greenwash", "documentId": 1},
    ],
)
def test_a_bad_run_body_is_422(client: Client, tenants: None, body: dict[str, Any]) -> None:
    login(client)
    assert client.post("/api/runs", data=body, content_type="application/json").status_code == 422
    assert rows() == (0, 0)
