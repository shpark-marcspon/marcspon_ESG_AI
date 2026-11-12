"""로그인(username·비밀번호 → 토큰 짝)과 Bearer 가 회사·주체의 경계와 만나는 자리(K2a). 보안 층.

연결은 이 층 그대로다(앱 역할 esg_app, RLS 없음, 진짜 커밋, 직렬). 실패 셈·잠금이 「어느 행에 내렸는가」는 주인 연결
(owner)로 센다 — 앱 역할의 답(상태 코드)만으로는 남의 행에 셈이 내렸는지 모른다.
해시는 MD5 다(conftest 의 fast_hasher).
시계는 경로가 읽는 now(user/service/apis/login.py·core/auth/bearer.py)를 바꿔 넣는다.

★ 회사 경로(/sites·/documents …)는 K2a 에서 쿠키만 본다(Bearer 는 K2b). 그래서 Bearer 만 실은 요청은
  401 no_session 이다. K2b 가 회사 경로에 Bearer 를 열면 그 답이 403 password_change_required(is_initial)·
  company_required(운영 관리자)로 바뀐다 — 아래 단언이 빨개지면 그 밴드가 기대값을 옮긴다.
  OP1(MARC-ENT-374)이 운영 관리자를 다시 옮겼다: 사업장 403 forbidden·문서(회사 업무) 400 company_ambiguous(회사 둘).
무효 조건: 동시 실패는 스레드 다섯 + 연결 다섯으로 만든 경합이다(gunicorn 일꾼 여럿의 요청으로 잰 것이 아니다).
"""

import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import psycopg
import pytest
from django.db import connections
from django.http import HttpRequest
from django.test import Client

from esgapi.core import permissions
from esgapi.core.auth import bearer as bearer_auth
from esgapi.core.auth.bearer import permitted
from esgapi.core.auth.principal import Kind, Principal
from esgapi.core.auth.tokens import ACCESS_TTL_SECONDS, LOCK_SECONDS
from esgapi.core.exceptions import ApplicationError
from esgapi.core.tenancy.session import Session
from esgapi.greenwash.flows.criteria_e0 import default_criteria
from esgapi.user.models import User
from esgapi.user.service.apis import login as login_apis
from esgapi.user.service.selectors import user as user_selectors
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.security.conftest import count
from tests.security.seed import add_company
from tests.security.test_tenant_paths import openapi, operations
from tests.support.http import bearer, bearer_pair, login

pytestmark = [pytest.mark.security, pytest.mark.usefixtures("fast_hasher")]

Owner = psycopg.Connection[tuple[Any, ...]]
PASSWORD: Final = "Blue-Harbor-7310"
OTHER_PASSWORD: Final = "Green-Valley-4821"
WRONG: Final = "Wrong-Lantern-5932"
NOW: Final = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)
BEARER_OPERATIONS: Final = {"user_me", "user_password_change"}
# K1b-2a 온실가스 풀의 계수 본문(바른 꼴 — 지어낸 값). permitted 가 먼저 막는지만 본다.
GHG_FACTOR_BODY: Final[dict[str, Any]] = {
    "name": "x",
    "source": "x",
    "baseYear": 2024,
    "tier": 1,
    "countryCode": "KR",
    "industryCode": "other",
    "inputUnit": {"kind": "mass", "unit": "kg"},
    "gases": [],
}


# ── 심기(앱의 길 — services 로 만든다. 주인 INSERT 가 아니다: 해시·is_initial 이 제품의 것이어야 한다) ──


def customer(company_id: int, username: str = "kim", password: str = PASSWORD) -> int:
    created = create_customer_user(
        actor_kind="admin", company_id=company_id, username=username, name="김담당", password=password
    )
    assert isinstance(created, UserCreated), created
    return created.user_id


def operator(username: str = "ops", password: str = PASSWORD) -> int:
    created = create_operator(username=username, name="운영자", password=password)
    assert isinstance(created, UserCreated), created
    return created.user_id


def try_login(client: Client, username: str, password: str, subdomain: str | None) -> Any:
    body: dict[str, Any] = {"username": username, "password": password}
    if subdomain is not None:
        body["companySubdomain"] = subdomain
    return client.post("/api/auth/login", data=body, content_type="application/json")


def answer(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def lock_state(owner: Owner, user_id: int) -> tuple[int, datetime | None]:
    """주인 역할이 본 그 행의 (실패 셈, 잠금 끝)."""
    row = owner.execute("SELECT login_failed_count, login_expiry_at FROM users WHERE id = %s", [user_id]).fetchone()
    assert row is not None
    return int(row[0]), row[1]


def failures(owner: Owner) -> dict[int, int]:
    """주인 역할이 본 사용자 행 전부의 실패 셈(id → 셈)."""
    return {int(user_id): int(n) for user_id, n in owner.execute("SELECT id, login_failed_count FROM users")}


class Clock:
    """경로가 읽는 now 를 갈아 끼운다. at 을 옮기면 다음 요청부터 그 시각이다."""

    def __init__(self, at: datetime) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at


# ── 회사의 경계 ──


def test_a_user_of_another_company_cannot_log_in(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    alice = customer(a, "alice")
    assert answer(try_login(client, "alice", PASSWORD, "tenant-b")) == (401, "INVALID_CREDENTIALS")
    assert answer(try_login(client, "alice", WRONG, "tenant-b")) == (401, "INVALID_CREDENTIALS")
    # 셈이 A 의 행에 내리지 않았다(B 에는 alice 가 없다 — 행이 하나뿐이다)
    assert count(owner, "users") == 1
    assert lock_state(owner, alice) == (0, None)
    # 분모: 같은 글자로 A 를 거치면 들어간다
    response = try_login(client, "alice", PASSWORD, "tenant-a")
    assert response.status_code == 200, response.content.decode()
    assert response.json()["kind"] == "service"


def test_the_lock_holds_at_five_and_six(
    client: Client, owner: Owner, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """다섯째 실패에 잠근다(잠금 끝 = 그때 + 10분). 여섯째는 맞는 비밀번호여도 account_locked 이고 셈이 그대로다.
    잠금 끝과 같은 초는 아직 잠김(K-B1), 그 1초 뒤에는 풀려 맞는 비밀번호가 들어가고 셈이 0 이다."""
    a, _ = companies
    kim = customer(a)
    clock = Clock(NOW)
    monkeypatch.setattr(login_apis, "now", clock)

    for n in range(1, 5):
        assert answer(try_login(client, "kim", WRONG, "tenant-a")) == (401, "INVALID_CREDENTIALS")
        assert lock_state(owner, kim) == (n, None)
    assert answer(try_login(client, "kim", WRONG, "tenant-a")) == (401, "INVALID_CREDENTIALS")
    until = NOW + timedelta(seconds=LOCK_SECONDS)
    assert lock_state(owner, kim) == (5, until)

    assert answer(try_login(client, "kim", PASSWORD, "tenant-a")) == (401, "ACCOUNT_LOCKED")  # 여섯째, 맞는 비밀번호
    assert answer(try_login(client, "kim", WRONG, "tenant-a")) == (401, "ACCOUNT_LOCKED")
    assert lock_state(owner, kim) == (5, until)  # 잠긴 동안은 셈도 끝도 그대로

    clock.at = until  # 같은 초 = 아직 잠김
    assert answer(try_login(client, "kim", PASSWORD, "tenant-a")) == (401, "ACCOUNT_LOCKED")
    clock.at = until + timedelta(seconds=1)
    assert try_login(client, "kim", PASSWORD, "tenant-a").status_code == 200
    assert lock_state(owner, kim) == (0, None)


def test_concurrent_failures_are_all_counted(
    owner: Owner, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """틀린 비밀번호 다섯이 겹쳐도 다섯 다 센다(행 잠금 뒤 다시 읽기 — 잃어버린 갱신 0). 다섯째에 잠긴다.
    장벽: 다섯 요청이 다 자기 블록 안에서 행 잠금 앞에 닿아야 지나간다(겹침이 실제로 만들어진다)."""
    a, _ = companies
    kim = customer(a)
    parties = 5
    barrier = threading.Barrier(parties)
    original: Callable[[int | None, int], User | None] = user_selectors.lock_account

    def lock_after_all_arrive(company_id: int | None, user_id: int) -> User | None:
        barrier.wait(timeout=10)
        return original(company_id, user_id)

    monkeypatch.setattr(user_selectors, "lock_account", lock_after_all_arrive)

    answers: list[tuple[int, str]] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def fail_once() -> None:
        try:
            response = try_login(Client(), "kim", WRONG, "tenant-a")
            with lock:
                answers.append(answer(response))
        except BaseException as err:
            with lock:
                errors.append(err)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=fail_once) for _ in range(parties)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]

    assert errors == []
    assert answers == [(401, "INVALID_CREDENTIALS")] * parties  # 다섯 다 잠금 전에 셈에 닿았다
    failed, until = lock_state(owner, kim)
    assert failed == parties
    assert until is not None  # 잠겼다
    # 분모: 잠금 뒤에는 맞는 비밀번호도 막힌다
    assert answer(try_login(Client(), "kim", PASSWORD, "tenant-a")) == (401, "ACCOUNT_LOCKED")


# ── 토큰이 틀리면 444 ──


def test_an_expired_access_token_is_444(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    customer(a)
    access = bearer_pair(client, username="kim", password=PASSWORD, company_subdomain="tenant-a")["access"]
    assert client.get("/api/users/me", **bearer(access)).status_code == 200  # 분모: 지금은 지난다
    later = datetime.now(UTC) + timedelta(seconds=ACCESS_TTL_SECONDS)
    monkeypatch.setattr(bearer_auth, "now", lambda: later)
    assert answer(client.get("/api/users/me", **bearer(access))) == (444, "TOKEN_NOT_VALID")


def test_a_refresh_token_as_bearer_is_444(client: Client, companies: tuple[int, int]) -> None:
    """서명은 같은 비밀이다. 칸막이는 aud 하나다(refresh 는 esgapi-refresh)."""
    a, _ = companies
    customer(a)
    pair = bearer_pair(client, username="kim", password=PASSWORD, company_subdomain="tenant-a")
    assert client.get("/api/users/me", **bearer(pair["access"])).status_code == 200  # 분모
    assert answer(client.get("/api/users/me", **bearer(pair["refresh"]))) == (444, "TOKEN_NOT_VALID")
    change = {"currentPassword": PASSWORD, "newPassword": OTHER_PASSWORD}
    response = client.post(
        "/api/users/me/password", data=change, content_type="application/json", **bearer(pair["refresh"])
    )
    assert answer(response) == (444, "TOKEN_NOT_VALID")


def test_a_session_cookie_value_as_bearer_is_444(tenants: None) -> None:
    """쿠키 세션도 같은 비밀로 서명한 JWT 다(aud esgapi-session). Bearer 로 실으면 444, 쿠키로는 세션 경로가 열린다."""
    cookie_client = Client()
    login(cookie_client, tenant_id="tenant-a")
    value = cookie_client.cookies["esg_session"].value
    assert cookie_client.get("/api/me").status_code == 200  # 분모: 쿠키로는 산 세션이다
    assert answer(Client().get("/api/users/me", **bearer(value))) == (444, "TOKEN_NOT_VALID")


# ── is_initial ──


class AuthedRequest(HttpRequest):
    """permitted 가 보는 것은 request.auth 하나다. HttpRequest 의 선언에 그 칸이 없어 칸을 선언한 요청을 쓴다."""

    auth: Principal | Session


def authed(principal: Principal) -> HttpRequest:
    request = AuthedRequest()
    request.auth = principal
    return request


def initial(kind: Kind) -> Principal:
    company_id = None if kind == "admin" else 7
    return Principal(user_id="42", company_id=company_id, kind=kind, is_initial=True, via="bearer")


def url_of(path: str) -> str:
    """openapi 의 경로 키 → 요청 주소(API 의 mount 자리 /api 를 붙인다 — 키에는 접두가 없다)."""
    url = "/api" + path.replace("{document_id}", str(uuid.uuid4())).replace("{run_id}", "1").replace("{name}", "a.xlsx")
    url = url.replace("{setting_id}", "1")  # G2c2 AI 설정 판(경로 인자 int)
    url = url.replace("{node_id}", "1").replace("{factor_id}", "1")  # K1b-2a 온실가스 풀(경로 인자 int)
    url = url.replace("{year}", "2025")  # K1b-2b 인덱스 선택 저장(경로 인자 int)
    url = url.replace("{site_id}", "1").replace("{row_id}", "1")  # S12a 입력 저장·히스토리(경로 인자 int)
    return (
        url.replace("{user_id}", "1").replace("{branch_id}", "1").replace("{code_id}", "1")
    )  # 사용자 관리의 초기화(K2c — 경로 변환기가 int 라 숫자로)


def send(client: Client, method: str, url: str, headers: dict[str, Any]) -> Any:
    """본문 없이 보낸다: 인증이 본문 읽기보다 먼저다(django-ninja 의 Operation.run)."""
    if method == "GET":
        return client.get(url, **headers)
    if method == "POST":
        return client.post(url, **headers)
    if method == "PUT":
        return client.put(url, **headers)
    if method == "PATCH":  # 수정(UA1)은 빈 본문이면 꼴 검사(422)가 permitted 보다 먼저라 바른 본문 하나를 싣는다
        return client.patch(url, data={"name": "엑스"}, content_type="application/json", **headers)
    if method == "DELETE":  # S12a 잠금 풀기
        return client.delete(url, **headers)
    raise AssertionError(f"{method}: 이 메서드를 보내는 법을 send 에 더한다")


def test_an_initial_user_reaches_only_the_allowed_operations(client: Client, companies: tuple[int, int]) -> None:
    """인증 있는 동작 전부(openapi 의 security)를 두 길로 잰다.
    ① HTTP: is_initial 고객사 사용자의 Bearer 만 실어 보낸다. 자기 계정 둘은 지나고(200·400 mismatch), 나머지는 2xx 가
      아니다(K2b — 회사 경로 24·사용자 관리 셋은 403 password_change_required, 쿠키만 받는 GET /me 는 401 no_session).
    ② 권한 검사 함수 permitted: is_initial 주체(두 kind)로 INITIAL_ALLOWED 밖은 전부 403 password_change_required 다."""
    found = operations(openapi())
    authenticated = {key: str(op["operationId"]) for key, op in found.items() if op.get("security")}
    names = set(authenticated.values())
    assert len(authenticated) == 160  # 분모: test_tenant_paths 의 표와 같은 수(UA1 +1: PATCH /users/{user_id})
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · S3K2b-1 +4: Scope 3 줄 덧판 넷
    # · S3K2b-2 +1: Scope 3 계수 수정
    # · S3D1 +1: GET /inventory/scope3/years/{year}/export
    # · IRS3 +3: 결과 고침 둘 · 고친 판 엑셀
    # · AU1a +1: GET /audit-logs · AU1b-1 +1: GET /audit-logs/actors · AU1b-2 +2: GET /run-logs·/run-logs/metrics
    # · G1b-1 +1: GET /greenwash/checks
    # · X1b-2a +2: PATCH /documents/{id}·GET /documents/{id}/file
    # · G2c2 +5: /ai-settings/greenwash 다섯 · AS2a +2: prompt-model 둘
    # · TR2 +1: GET /translation/runs/{run_id}/result
    # · AD4S +1: GET /run-logs/export
    # · AD4D +1: GET /run-logs/{run_id}
    # · RF1 +1: GET /run-logs/{run_id}/files/{name}
    # · DV1e +1: GET /dataverify/runs/{run_id}/result
    # · DV1g +1: GET /dataverify/runs
    # · TR3a +2: POST /translation/glossary/read · GET /translation/glossary/template
    # · TR3b +3: GET /translation/batches · GET …/batches/{batch_key} · GET …/batches/{batch_key}/archive
    # · TR4 +7: /ai-settings/translation 일곱
    # · IR3b +1: GET /materiality/runs/{run_id}/result
    # · DVA1 +7: /ai-settings/dataverify 일곱
    # · IR3c +1: GET /materiality/runs
    # · TRP6 +1: GET /translation/documents/{document_id}/pages
    # · TRS3 +1: GET /translation/runs/{run_id}/layout
    # · IRW2 +1: POST /materiality/value-chain/read
    # · IR4 +7: /ai-settings/materiality 일곱
    # · K1b-1 +11: /branches 여섯 · /facility-codes · /admin/facility-codes 넷
    # · K1b-2a +12: inventory_admin_ghg_* 열둘(bearer)
    # · K1b-2b +2: /inventory/scope12 둘
    # · S12a +10: /inventory/scope12 열(Scope 1·2 입력)
    # · DVX1 +2: POST /dataverify/edk/read · GET /dataverify/edk/template
    # · RP1 +5: /drafting 다섯
    # · RP2d +2: GET /drafting/projects · GET …/result.docx
    # · RP2c +1: GET /drafting/projects/{project_id}/outline/changes
    # · RPS1 +1: GET /drafting/projects/{project_id}/runs
    # · S12a-2 +3: /inventory/scope12 입력주기·행 계수 바꿈·복구
    # · RPA1 +7: /ai-settings/drafting 일곱
    # · S3K1 +2: GET /inventory/scope3/runs/{run_id}/result · GET /inventory/scope3/template
    # · S12a-3 +1: GET /inventory/scope12/dashboard
    # · S12b-1 +2: GET /inventory/scope12/years/{year}/template · …/export
    # · S3K2a +3: GET /inventory/scope3/years/{year} · POST·DELETE …/categories/{category}/lock
    # · GRJ1 +1: POST /greenwash/runs/{run_id}/items/{item_index}/rejudge
    assert names >= permissions.INITIAL_ALLOWED == BEARER_OPERATIONS
    assert names <= set(permissions.OPERATION_POLICY)  # 표에 없는 동작이 없다(아래 ② 가 전부를 훑는다)

    a, _ = companies
    customer(a)
    pair = bearer_pair(client, username="kim", password=PASSWORD, company_subdomain="tenant-a")
    assert pair["isInitial"] is True
    headers = bearer(pair["access"])

    # ① HTTP
    me = client.get("/api/users/me", **headers)
    assert me.status_code == 200 and me.json()["isInitial"] is True
    mismatch = client.post(
        "/api/users/me/password",
        data={"currentPassword": WRONG, "newPassword": OTHER_PASSWORD},
        content_type="application/json",
        **headers,
    )
    assert answer(mismatch) == (400, "CURRENT_PASSWORD_MISMATCH")  # 바꾸기까지 갔다(권한에서 막히지 않았다)
    closed = sorted(key for key, name in authenticated.items() if name not in BEARER_OPERATIONS)
    assert len(closed) == 158  # IRS3 +3 · UA1 +1: PATCH /users/{user_id} · AU1a +1: GET /audit-logs · AU1b-1 +1
    # · RM1c ③ +1: GET /runs/{run_id}/segments
    # · S3Q1 +1: GET /inventory/scope3/runs/{run_id}/original
    # · S3K2b-1 +4: Scope 3 줄 덧판 넷
    # · S3K2b-2 +1: Scope 3 계수 수정
    # · S3D1 +1: GET /inventory/scope3/years/{year}/export
    # · AU1b-2 +2: GET /run-logs·/run-logs/metrics
    # · G1b-1 +1: GET /greenwash/checks
    # · X1b-2a +2: 문서 고치기·원본
    # · G2c2 +5: AI 설정 판 다섯(Bearer — permitted 가 먼저 막는다. 저장·적용 둘은 바른 본문을 싣는다)
    # · AS2a +2: prompt-model 둘(GET — 본문 없음)
    # · TR2 +1: 영문번역 결과(GET — 본문 없음)
    # · AD4S +1: GET /run-logs/export
    # · AD4D +1: GET /run-logs/{run_id}
    # · RF1 +1: GET /run-logs/{run_id}/files/{name}
    # · DV1e +1: 데이터 검증 결과(GET — 본문 없음)
    # · DV1g +1: 데이터 검증 목록(GET — 본문 없음)
    # · TR3a +2: 용어집 읽기(POST — 본문 없이 보내도 회사 경로 인증이 먼저 막는다)·양식(GET)
    # · TR3b +3: 묶음 목록·하나 보기·zip(GET — 본문 없음)
    # · TR4 +7: 영문번역 AI 설정 판 일곱(Bearer — 저장·적용 둘은 바른 본문을 싣는다)
    # · IR3b +1: 중대성평가 IRO 결과(GET — 본문 없음)
    # · DVA1 +7: 데이터 검증 AI 설정 판 일곱(영문번역과 같은 꼴)
    # · IR3c +1: 중대성평가 IRO 목록
    # · TRP6 +1: 영문번역 문서 쪽 수(GET — 본문 없음)
    # · TRS3 +1: 영문번역 layout 읽기(GET — 본문 없음)
    # · IRW2 +1: 중대성평가 가치사슬 엑셀 읽기(POST — 맨 바이트 본문, 비어도 permitted 가 먼저)
    # · IR4 +7: 중대성평가 IRO AI 설정 판 일곱(데이터 검증과 같은 꼴)
    # · K1b-1 +11: 회사 경로 일곱(인증이 먼저 막는다 — 본문 없음) · 코드 목록 넷(Bearer — 본문 셋은 바른 꼴로)
    # · K1b-2a +12: 온실가스 풀 열둘(Bearer — 본문 여덟은 바른 꼴로)
    # · K1b-2b +2: 인덱스 선택 둘(회사 경로 — 초기 사용자는 인증이 본문 꼴 검사보다 먼저 403)
    # · S12a +10: Scope 1·2 입력 열(회사 경로 — 같은 까닭으로 403)
    # · DVX1 +2: EDK 엑셀 읽기(POST — 맨 바이트 본문, 비어도 permitted 가 먼저)·양식(GET)
    # · RP1 +5: 원고작성 다섯(회사 경로)
    # · RP2d +2: 원고작성 목록·docx(회사 경로)
    # · RP2c +1: 원고작성 목차 차이(회사 경로)
    # · RPS1 +1: 원고작성 프로젝트 실행 목록(회사 경로)
    # · S12a-2 +3: /inventory/scope12 셋(회사 경로)
    # · RPA1 +7: 원고작성 AI 설정 판 일곱(중대성평가 IRO 와 같은 꼴)
    # · S3K1 +2: /inventory/scope3 결과·빈 양식(회사 경로)
    # · S12a-3 +1: GET /inventory/scope12/dashboard(회사 경로)
    # · S12b-1 +2: 엑셀 내려받기 둘(회사 경로)
    # · S3K2a +3: Scope 3 연도 상태·잠그기·풀기(회사 경로)
    # · GRJ1 +1: 그린워싱 재판단(회사 경로 — 인증이 먼저 막는다, 본문 없음)
    # 회사 경로 24 는 Bearer 를 먼저 받는다(K2b). 사용자 관리 셋(K2c)은 Bearer 라 permitted 가 먼저 막는다(c-0-3).
    # 셋의 POST 둘은 바른 본문을 싣는다(본문 꼴 검사가 경로 함수의 permitted 보다 먼저다 — 빈 본문이면 400).
    user_admin = {
        key for key, name in authenticated.items() if name in {"user_list", "user_create", "user_password_reset"}
    }
    assert len(user_admin) == 3
    bodies = {
        ("POST", "/users"): {"companyId": a, "username": "x", "name": "엑스", "password": OTHER_PASSWORD},
        ("POST", "/users/{user_id}/password-reset"): {"companyId": a, "password": OTHER_PASSWORD},
        ("POST", "/ai-settings/greenwash"): {"criteria": default_criteria(), "title": "x"},
        ("PUT", "/ai-settings/greenwash/applied"): {"id": None},
        ("POST", "/ai-settings/translation"): {"title": "x"},
        ("PUT", "/ai-settings/translation/applied"): {"id": None},
        ("POST", "/ai-settings/dataverify"): {"title": "x"},
        ("PUT", "/ai-settings/dataverify/applied"): {"id": None},
        ("POST", "/ai-settings/materiality"): {"title": "x"},
        ("PUT", "/ai-settings/materiality/applied"): {"id": None},
        ("POST", "/ai-settings/drafting"): {"title": "x"},  # RPA1
        ("PUT", "/ai-settings/drafting/applied"): {"id": None},
        ("POST", "/admin/facility-codes"): {"name": "x"},  # K1b-1
        ("PATCH", "/admin/facility-codes/{code_id}"): {"name": "x"},
        ("POST", "/admin/facility-codes/delete"): {"ids": [1]},
        ("POST", "/inventory/admin/ghg-index/nodes"): {"level": "scope", "name": "x"},  # K1b-2a
        ("PATCH", "/inventory/admin/ghg-index/nodes/{node_id}"): {"name": "x"},
        ("POST", "/inventory/admin/ghg-index/nodes/delete"): {"ids": [1]},
        ("POST", "/inventory/admin/ghg-index/facilities"): {
            "parentId": 1,
            "facilityCodeId": 1,
            "unit": {"kind": "mass", "unit": "kg"},
        },
        ("PUT", "/inventory/admin/ghg-index/facilities/{node_id}"): {
            "facilityCodeId": 1,
            "unit": {"kind": "mass", "unit": "kg"},
        },
        ("POST", "/inventory/admin/ghg-index/facilities/{node_id}/factors"): GHG_FACTOR_BODY,
        ("PUT", "/inventory/admin/ghg-factors/{factor_id}"): GHG_FACTOR_BODY,
        ("POST", "/inventory/admin/ghg-factors/delete"): {"ids": [1]},
    }
    seen = {
        key: answer(
            getattr(Client(), key[0].lower())(
                url_of(key[1]), data=bodies[key], content_type="application/json", **headers
            )
            if key in bodies
            else send(Client(), key[0], url_of(key[1]), headers)
        )
        for key in closed
    }
    # K2b: 회사 경로 24 는 Bearer 를 먼저 받아 CompanyScopedAuth 가 403 으로 막는다(본문 꼴 검사보다 먼저).
    # GET /me 하나는 쿠키만 받는다(교환 세션의 것) — 쿠키가 없으니 401 no_session.
    me = ("GET", "/me")
    assert me in closed
    assert seen == {me: (401, "NO_SESSION")} | dict.fromkeys(
        sorted(set(closed) - {me}), (403, "PASSWORD_CHANGE_REQUIRED")
    )

    # ② permitted
    for kind in ("service", "admin"):
        principal = initial(kind)
        for name in sorted(names):
            request = authed(principal)
            if name in permissions.INITIAL_ALLOWED:
                assert permitted(request, name) == principal
                continue
            with pytest.raises(ApplicationError) as raised:
                permitted(request, name)
            assert (raised.value.kind, raised.value.code) == ("forbidden", "password_change_required"), name


# ── 운영 관리자 ──


def test_an_operator_logs_in_without_a_company(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    ops = operator()
    response = try_login(client, "ops", PASSWORD, None)
    assert response.status_code == 200, response.content.decode()
    assert (response.json()["kind"], response.json()["isInitial"]) == ("admin", True)
    me = client.get("/api/users/me", **bearer(response.json()["access"])).json()
    assert (me["id"], me["kind"], me["companyId"]) == (ops, "admin", None)
    # 회사를 실으면 고객사 사용자의 길이다: 그 회사에 ops 가 없다 → 401, 운영 관리자의 행에 셈이 내리지 않는다
    for subdomain in ("tenant-a", "tenant-b"):
        assert answer(try_login(client, "ops", PASSWORD, subdomain)) == (401, "INVALID_CREDENTIALS")
    row = owner.execute("SELECT kind, company_id, login_failed_count FROM users WHERE id = %s", [ops]).fetchone()
    assert row == ("admin", None, 0)


def test_an_operator_and_a_customer_with_the_same_username_do_not_cross(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """같은 username 의 운영 관리자(비밀번호 P)와 A 의 고객사 사용자(비밀번호 Q). 남의 비밀번호로는 어느 길도 401 이고,
    실패 셈은 고른 길의 행에만 내린다."""
    a, _ = companies
    kim = customer(a, "kim", OTHER_PASSWORD)  # 고객사를 먼저(UA1 — 겹침 막기는 고객사 만들기 쪽뿐)
    ops = operator("kim", PASSWORD)
    # 분모: 제 길·제 비밀번호로는 둘 다 들어가고 kind 가 갈린다
    assert try_login(client, "kim", PASSWORD, None).json()["kind"] == "admin"
    assert try_login(client, "kim", OTHER_PASSWORD, "tenant-a").json()["kind"] == "service"
    assert failures(owner) == {ops: 0, kim: 0}

    assert answer(try_login(client, "kim", PASSWORD, "tenant-a")) == (401, "INVALID_CREDENTIALS")
    assert failures(owner) == {ops: 0, kim: 1}  # 고객사 사용자의 길 → 그 행에만
    assert answer(try_login(client, "kim", OTHER_PASSWORD, None)) == (401, "INVALID_CREDENTIALS")
    assert failures(owner) == {ops: 1, kim: 1}  # 운영 관리자의 길 → 그 행에만


def test_an_operator_bearer_does_not_open_company_paths(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """(K2b·OP1) 운영 관리자의 Bearer 로 회사 경로: 사업장(고객사 전용) 403 forbidden, 문서(회사 업무)는 회사가 둘이라
    400 company_ambiguous — 회사 행을 읽지도 쓰지도 않는다(행 0).
    쿠키만 받는 GET /me 는 401 no_session."""
    operator()
    owner.execute("UPDATE users SET is_initial = false WHERE username = 'ops'")
    access = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)["access"]
    assert client.get("/api/users/me", **bearer(access)).status_code == 200  # 분모: 토큰은 산 것이다
    assert answer(client.get("/api/sites", **bearer(access))) == (403, "FORBIDDEN")
    created = client.post(
        "/api/sites", data={"name": "운영자의 사업장"}, content_type="application/json", **bearer(access)
    )
    assert answer(created) == (403, "FORBIDDEN")
    assert answer(client.get("/api/documents", **bearer(access))) == (400, "COMPANY_AMBIGUOUS")
    assert answer(client.get("/api/me", **bearer(access))) == (401, "NO_SESSION")
    assert count(owner, "sites") == 0


# ── 회사 칸 없는 고객사 로그인(UA1 — MARC-ENT-283, 처분 ⑩ ㄱ 운영 관리자 먼저) ──


def test_with_one_company_a_customer_logs_in_without_a_subdomain_and_only_that_row_counts(
    client: Client, owner: Owner
) -> None:
    """(UA1 ⓐ) 회사가 하나뿐(쓸 수 있음)이면 서브도메인 없이 그 회사의 고객사 사용자로 들어간다. 틀린 비밀번호의 셈은
    그 행에만 내린다(주인 연결). 분모: 회사 표에 정확히 한 행."""
    solo = add_company(owner, "solo")
    assert count(owner, "company") == 1
    kim, lee = customer(solo, "kim"), customer(solo, "lee")
    ok = try_login(client, "kim", PASSWORD, None)
    assert ok.status_code == 200, ok.content.decode()
    assert ok.json()["kind"] == "service"
    assert answer(try_login(client, "kim", OTHER_PASSWORD, None)) == (401, "INVALID_CREDENTIALS")
    assert failures(owner) == {kim: 1, lee: 0}
    owned = owner.execute("SELECT DISTINCT user_id FROM user_refresh_tokens").fetchall()
    assert owned == [(kim,)]


def test_with_one_company_the_operator_of_the_same_username_comes_first(client: Client, owner: Owner) -> None:
    """(UA1 ⓑ) 같은 아이디의 운영 관리자가 있으면 서브도메인 없는 로그인은 운영 관리자 길이다(고객사 행 셈 0).
    고객사를 먼저 만들고 운영 관리자를 나중에(명령 create_user --admin 은 겹침을 막지 않는다 — 처분 ⑩)."""
    solo = add_company(owner, "solo")
    kim = customer(solo, "kim", OTHER_PASSWORD)
    ops = operator("kim", PASSWORD)
    assert answer(try_login(client, "kim", OTHER_PASSWORD, None)) == (401, "INVALID_CREDENTIALS")  # 고객사 비밀번호
    assert failures(owner) == {ops: 1, kim: 0}
    assert try_login(client, "kim", PASSWORD, None).json()["kind"] == "admin"
    assert try_login(client, "kim", OTHER_PASSWORD, "solo").json()["kind"] == "service"  # 분모: 서브도메인이면 고객사


def test_with_one_inactive_company_a_customer_without_a_subdomain_is_401(client: Client, owner: Owner) -> None:
    """(UA1 ⓒ) 하나뿐인 회사가 꺼져 있으면 서브도메인 없는 고객사 길은 닫힌다(401, 셈 0). 분모: 켜면 들어간다."""
    solo = add_company(owner, "solo")
    kim = customer(solo, "kim")
    owner.execute("UPDATE company SET is_active = false WHERE id = %s", [solo])
    assert answer(try_login(client, "kim", PASSWORD, None)) == (401, "INVALID_CREDENTIALS")
    assert failures(owner) == {kim: 0}
    owner.execute("UPDATE company SET is_active = true WHERE id = %s", [solo])
    assert try_login(client, "kim", PASSWORD, None).status_code == 200


def test_with_two_companies_a_customer_without_a_subdomain_is_401(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """(UA1 ⓓ) 회사가 둘이면 서브도메인 없는 로그인은 운영 관리자만이다(지금 동작 — 고객사 아이디는 401, 셈 0)."""
    a, b = companies
    kim, park = customer(a, "kim"), customer(b, "park")
    for username in ("kim", "park"):
        assert answer(try_login(client, username, PASSWORD, None)) == (401, "INVALID_CREDENTIALS")
    assert failures(owner) == {kim: 0, park: 0}
    assert try_login(client, "kim", PASSWORD, "tenant-a").status_code == 200  # 분모: 서브도메인이면 들어간다
