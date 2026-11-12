"""운영 관리자(kind admin, 회사 없음)가 작업 회사(하나뿐인 회사)로 하는 회사 업무를 앱 역할로 잰다(결정
MARC-ENT-374·380, 밴드 OP1 §3-3·OP2). 보안 층.

  ① 회사 업무 20: 회사 하나(활성)에서 운영 관리자 Bearer 가 PASSING_REQUESTS 대로 401·403·422 아님(18 + 비교 501·기본
     단어 200). 만들기는 그 회사 id 로만 행. 짝: 고객사 사용자도 같은 회사에서 지난다.
  ② 고객사 전용 9(사업장·인벤토리·기준 자료): 운영 관리자 403 forbidden, 회사 표·업무 표 읽기 0, 행 0.
     짝: 같은 요청을 고객사 사용자는 지난다.
  ③ 운영 관리자 전용 15: 고객사 사용자 403 그대로(짝: 운영 관리자는 지난다) · 자기 동작 2: 두 kind 다 지난다.
  ④ 회사를 고르는 18: 회사 둘 → 400 company_ambiguous · 0 → 400 company_not_found · 비활성 하나 → 403 company_inactive,
     행 0·감사 0. 비교·기본 단어 둘은 세 경우 다 501·200, 회사 표 읽기 0. 짝: 회사 하나(활성)면 지난다(①).
  ⑤ 질의 companyId 로 다른 회사 열기(Q1 가 — 칸 없음): 운영 관리자·고객사 사용자가 실어도 작업 회사·주체의 회사 그대로.
     본문 companyId 는 422(문서 만들기·실행 만들기).
  ⑥ 남의 회사: 회사 A 하나일 때 운영 관리자가 문서·실행·확정을 만든 뒤 회사 B 를 더하면 운영 관리자 400(보고서 포함),
     B 의 고객사 사용자는 A 의 id 404, A 의 고객사 사용자는 200·확정자 이름 = 운영 관리자 이름. 기본 단어는 어느 회사의
     것도 싣지 않는다(37 허락 조건 — 남의 회사의 보고서·대상 단어).
  ⑦ is_initial 운영 관리자: 회사 업무 20 전부 403 password_change_required(본문 꼴 검사보다 앞 — 꼴이 틀린 본문도 422 가
     아니라 403), 회사 표 읽기 0. 짝: 비밀번호를 바꾼 운영 관리자는 지난다.
  ⑧ 감사: 운영 관리자의 올림 확인·실행 만들기·검토 확정·보고서 내려받기 줄 = actor_kind admin · company_id 작업 회사 ·
     actor_user_id 운영 관리자 id(올림 확인은 경로가 actor_kind 를 넘겨야 admin — 검증 ② R1).
  ⑨ 쿠키 길: 교환 쿠키 세션은 고객사 사용자 그대로(질의 companyId 무시).
  ⑩ 영문번역(MARC-ENT-380 — TR2 의 403 을 뒤집음): 회사 하나에서 운영 관리자가 결과 200(본문 = 고객사 사용자의 것)·
     실행 만들기 module translation 201(행 company_id = 작업 회사·created_by = 운영 관리자 id·감사 run 줄 admin). 실행
     만들기는 진짜 등록부(module translation 의 기본 흐름 — 공급사는 부르지 않는다, 큐 갈고리는 버림).
  ⑪ 영문번역 남의 회사: 회사 A 하나일 때 운영 관리자가 만든 실행·A 의 끝난 결과 → 회사 B 를 더하면 운영 관리자 400
     (실행·결과 표 SELECT 0), B 의 고객사 사용자 404, A 의 고객사 사용자 200.
  ⑫ 실행 목록: 고객사 사용자의 실행 셋(inventory·translation·greenwash) — 운영 관리자 목록은 둘, 고객사 사용자는 셋.
  ⑬ 데이터 검증(MARC-ENT-390 — DV1e): 회사 하나에서 결과 200(본문 = 고객사 사용자의 것)·문서 없는 실행 만들기 201(행
     company_id = 작업 회사·created_by = 운영 관리자·감사 run 줄 admin) → 회사 B 를 더하면 결과 400(실행·결과 표
     SELECT 0), B 의 고객사 사용자 404, A 의 고객사 사용자 200.
  ⑭ 데이터 검증 결과 파일: 작업 회사면 dataverify-report.xlsx 200·감사 run_file_downloaded admin · inventory 실행의
     파일은 404(분모) · 회사 B 를 더하면 B 의 고객사 사용자 404, 운영 관리자 400.
  ⑮ 중대성평가 IRO(MARC-ENT-419 — IR3b): 회사 하나에서 결과 200(본문 = 고객사 사용자의 것)·문서 없는 실행 만들기 201
     (행 company_id = 작업 회사·created_by = 운영 관리자·감사 run 줄 admin) → 회사 B 를 더하면 결과 400(실행·결과 표
     SELECT 0), B 의 고객사 사용자 404, A 의 고객사 사용자 200.
  ⑯ 중대성평가 IRO 엑셀 둘: 작업 회사면 materiality-websearch.xlsx·materiality-final-report.xlsx 각 200·감사
     run_file_downloaded admin · inventory 실행의 파일은 404(분모) · 회사 B 를 더하면 B 의 고객사 사용자 404,
     운영 관리자 400.
  ⑰ 중대성평가 IRO 실행 목록(IR3c): 회사 하나면 목록 200(고객사 사용자가 만든 실행 듦 — 본문 = 고객사 사용자의 것) →
     회사 B 를 더하면 운영 관리자 400(실행 표 SELECT 0), B 의 고객사 사용자는 A 의 실행 0.
  ⑱ Scope 3 코랩(S3K1): 회사 하나에서 결과 200(본문 = 고객사 사용자의 것)·빈 양식 200 → 회사 B 를 더하면 결과 400
     (실행·결과 표 SELECT 0), 빈 양식은 그대로 200(회사를 고르지 않음), B 의 고객사 사용자 404, A 의 고객사 사용자 200.

회사는 이 파일 안에서 세운다(seed.add_company — 하나·비활성은 주인 연결로). Django 의 연결은 앱 역할이고 진짜로
커밋한다.
문서·이름은 전부 지어낸 것이다. 실행 만들기는 module greenwash 의 가짜 흐름(시험의 등록부 — 공급사 0, 큐 갈고리는 버림).
"""

from typing import Any, Final

import psycopg
import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.flows.binding import BindingRegistry
from esgapi.core.flows.registry import FlowRegistry, make_flow
from esgapi.core.flows.types import Carried, FlowStep, StepContext, StepOutput
from esgapi.core.resources import queue as hooks
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.core.tests.test_permissions_wiring import OPERATOR_PASSES
from esgapi.core.tests.test_permissions_wiring import send as send_wiring
from esgapi.runs.service.actions import runs as actions
from tests.security.conftest import count
from tests.security.seed import add_company
from tests.security.test_documents import PDF
from tests.security.test_greenwash import owner_done_run
from tests.security.test_runs import ProbeAdapters, ProbeBinding, ProbeInputs, ignore
from tests.security.test_tenant_paths import (
    CUSTOMER_ONLY,
    NOT_CHOOSING,
    NOT_PASSED,
    OPERATOR_COMPANY_OPERATIONS,
    company_operations,
    openapi,
    operations,
    send_passing,
)
from tests.support.http import customer_bearer, login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
OPERATOR_NAME: Final = "운영자 한빛"
PASSWORD: Final = "Blue-Harbor-7310"
WORK_TABLES: Final = ('"company"', '"core_documents"', '"sites"', '"run_runs"', '"greenwash_reviews"')
SELF_OPERATIONS: Final = ("user_me", "user_password_change")
OPERATOR_OPERATIONS: Final = tuple(OPERATOR_PASSES)


def _only(inputs: ProbeInputs, adapters: ProbeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"results": []})


GREENWASH_PROBE: Final = make_flow(
    module="greenwash",
    id="greenwash.probe@1",
    input_shape="probe.document@1",
    inputs=ProbeInputs,
    adapters=ProbeAdapters,
    result_shapes=("probe.result@1",),
    output_files=(),
    steps=(FlowStep(name="only", run=_only),),
)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    """문서 저장소 틈에 가짜를, 실행 만들기의 등록부에 module greenwash 의 가짜 흐름을. 큐 갈고리는 버린다."""
    flows = FlowRegistry()
    flows.register(GREENWASH_PROBE)
    flows.set_default("greenwash", GREENWASH_PROBE.id)
    bindings = BindingRegistry()
    bindings.register(GREENWASH_PROBE.id, ProbeBinding())
    monkeypatch.setattr(actions, "REGISTRY", flows)
    monkeypatch.setattr(actions, "BINDINGS", bindings)
    monkeypatch.setattr(hooks, "enqueue_run", ignore)
    return plug_storage(monkeypatch, FakeStorage())


@pytest.fixture
def solo(owner: Owner) -> int:
    """회사 하나(활성, subdomain tenant-a — 교환 쿠키가 그 회사로 든다). 그 회사의 id."""
    return add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")


def operator_client(owner: Owner, *, initial: bool = False) -> tuple[Client, int]:
    """운영 관리자(이름 OPERATOR_NAME)의 Bearer 만 실은 클라이언트와 그 사용자 id. initial 이 아니면 is_initial 끔."""
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    created = create_operator(username="ops", name=OPERATOR_NAME, password=PASSWORD)
    assert isinstance(created, UserCreated)
    if not initial:
        owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login", data={"username": "ops", "password": PASSWORD}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    return Client(headers={"Authorization": f"Bearer {logged.json()['access']}"}), created.user_id


def customer_client(company_id: int, subdomain: str = "tenant-a") -> Client:
    return Client(
        headers={"Authorization": f"Bearer {customer_bearer(Client(), company_id=company_id, subdomain=subdomain)}"}
    )


def targets() -> dict[str, tuple[str, str]]:
    """회사 동작(Bearer 를 먼저 받는 회사 경로) operationId → (메서드, 경로)."""
    found = operations(openapi())
    return {found[key]["operationId"]: key for key in company_operations()}


def company_work() -> dict[str, tuple[str, str]]:
    work = {op: key for op, key in targets().items() if op not in CUSTOMER_ONLY | OPERATOR_COMPANY_OPERATIONS}
    # · S3K1 +2(고르는 쪽 — Scope 3 결과 · 고르지 않는 쪽 — Scope 3 빈 양식)
    assert len(work) == 69 + 14  # 분모: 회사를 고르는 24(DV1e +1 · TR3b +3 · DV1g +1 · IR3b +1) + 고르지 않는 4(TR3a+2)
    # · RM1c ③ +1(고르는 쪽 — 실행 구획 목록)
    # · S3Q1 +1(고르는 쪽 — Scope 3 원본)
    # · S3K2b-1 +4(고르는 쪽 — Scope 3 줄 덧판 넷)
    # · S3K2b-2 +1(고르는 쪽 — Scope 3 계수 수정)
    # · S3D1 +1(고르는 쪽 — Scope 3 데이터 엑셀)
    # · IRS3 +3(고르는 쪽 — 결과 고침 둘 · 고친 판 엑셀)
    # · IR3c +1(회사를 고르는 쪽 — GET /materiality/runs)
    # · TRP6 +1(회사를 고르는 쪽 — GET /translation/documents/{document_id}/pages)
    # · TRS3 +1(회사를 고르는 쪽 — GET /translation/runs/{run_id}/layout)
    # · IRW2 +1(고르지 않는 쪽 — POST /materiality/value-chain/read)
    # · K1b-1 +6(고르는 쪽 — /branches) · +1(고르지 않는 쪽 — /facility-codes)
    # · K1b-2b +2(고르는 쪽 — /inventory/scope12 둘)
    # · S12a +9(고르는 쪽 — /inventory/scope12 입력 아홉. 풀기는 OPERATOR_COMPANY_OPERATIONS)
    # · DVX1 +2(고르지 않는 쪽 — POST /dataverify/edk/read · GET /dataverify/edk/template)
    # · RP1 +5(고르는 쪽 — /drafting 다섯)
    # · RP2d +2(고르는 쪽 — 목록·docx)
    # · RP2c +1(고르는 쪽 — 목차 차이)
    # · RPS1 +1(고르는 쪽 — 프로젝트 실행 목록)
    # · S12a-2 +2(고르는 쪽 — 입력주기·복구. 계수 바꿈은 OPERATOR_COMPANY_OPERATIONS)
    # · S12a-3 +1(고르는 쪽 — 대시보드)
    # · S12b-1 +2(고르는 쪽 — 엑셀 내려받기 둘)
    # · S3K2a +2(고르는 쪽 — Scope 3 연도 상태·잠그기. 풀기는 OPERATOR_COMPANY_OPERATIONS)
    # · GRJ1 +1(고르는 쪽 — 그린워싱 재판단)
    return work


def customer_only() -> dict[str, tuple[str, str]]:
    only = {op: key for op, key in targets().items() if op in CUSTOMER_ONLY}
    assert len(only) == 9  # 분모
    return only


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def reads(captured: CaptureQueriesContext) -> list[str]:
    """갈무리한 쿼리 가운데 회사 표·업무 표를 읽거나 쓴 것."""
    return [q["sql"] for q in captured.captured_queries if any(table in q["sql"] for table in WORK_TABLES)]


def rows(owner: Owner) -> tuple[int, int, int, int]:
    return (
        count(owner, "sites"),
        count(owner, "core_documents"),
        count(owner, "run_runs"),
        count(owner, "greenwash_reviews"),
    )


def audit_lines(owner: Owner) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT actor_kind, actor_user_id, company_id, action FROM core_audit_events "
        "WHERE action IN ('upload', 'run', 'confirm', 'download') ORDER BY id"
    ).fetchall()


# ── ① 회사 업무 19 ──


def test_the_operator_does_the_company_work_in_the_sole_company(owner: Owner, solo: int, fake: FakeStorage) -> None:
    operator, _ = operator_client(owner)
    customer = customer_client(solo)
    statuses: dict[str, int] = {}
    for op, (method, path) in company_work().items():
        response = send_passing(operator, op, method, path)
        statuses[op] = response.status_code
        assert response.status_code not in NOT_PASSED, (op, response.status_code, response.content.decode()[:300])
        if op in NOT_CHOOSING:
            assert response.status_code == NOT_CHOOSING[op], op
        mine = send_passing(customer, op, method, path)  # 짝: 고객사 사용자도 같은 회사에서 지난다
        assert mine.status_code not in NOT_PASSED, (op, mine.status_code)
    written = owner.execute("SELECT array_agg(DISTINCT company_id) FROM core_documents").fetchone()
    assert written == ([solo],)  # 만들기(운영 관리자·고객사 사용자 둘)는 그 회사에만
    assert count(owner, "core_documents") == 2
    assert count(owner, "sites") == 0


# ── ② 고객사 전용 9 ──


def test_the_operator_is_403_on_the_customer_only_operations_reading_no_company(
    owner: Owner, solo: int, fake: FakeStorage
) -> None:
    operator, _ = operator_client(owner)
    customer = customer_client(solo)
    before = rows(owner)
    for op, (method, path) in customer_only().items():
        with CaptureQueriesContext(connection) as captured:
            response = send_passing(operator, op, method, path)
        assert code(response) == (403, "FORBIDDEN"), (op, response.content.decode()[:300])
        assert reads(captured) == [], op  # 회사 표·업무 표 읽기 0(회사를 고르기 전)
        mine = send_passing(customer, op, method, path)  # 짝: 고객사 사용자는 지난다
        assert mine.status_code not in NOT_PASSED, (op, mine.status_code, mine.content.decode()[:300])
    assert rows(owner)[0] == 1 and before == (0, 0, 0, 0)  # 사업장은 고객사 사용자의 만들기 하나뿐


# ── ③ 운영 관리자 전용 18 · 자기 동작 2 ──


def test_the_operator_only_cells_stay_closed_to_a_customer(owner: Owner, solo: int) -> None:
    operator, _ = operator_client(owner)
    customer = customer_client(solo)
    assert len(OPERATOR_OPERATIONS) == 65  # 분모(AD4S +1: user_run_log_export · AD4D +1: user_run_log_get)
    # · S12a +1: inventory_scope12_unlock(회사를 고르는 운영 관리자 칸)
    # · S12a-2 +1: inventory_scope12_row_factor_save(회사를 고르는 운영 관리자 칸)
    # · S3K2a +1: inventory_scope3_unlock(회사를 고르는 운영 관리자 칸)
    # RF1 +1: user_run_log_file_get · TR4 +7: translation_ai_setting_* 일곱
    # · DVA1 +7: dataverify_ai_setting_* 일곱
    # · IR4 +7: materiality_ai_setting_* 일곱
    # · K1b-1 +4: organization_admin_facility_codes_* 넷
    # · K1b-2a +12: inventory_admin_ghg_* 열둘
    # · RPA1 +7: drafting_ai_setting_* 일곱
    for op in OPERATOR_OPERATIONS:
        assert code(send_wiring(customer, op, solo)) == (403, "FORBIDDEN"), op
        if op in OPERATOR_COMPANY_OPERATIONS:
            continue  # 회사를 고르는 칸 — 운영 관리자 쪽은 test_entries.py(자)
        status, _ = OPERATOR_PASSES[op]
        assert send_wiring(operator, op, solo).status_code == status, op  # 짝: 운영 관리자는 지난다
    for op in SELF_OPERATIONS:
        for who in (operator, customer):
            response = send_wiring(who, op)
            assert response.status_code in (200, 400), (op, response.status_code)  # 바꾸기는 틀린 지금 비밀번호 400
            if response.status_code == 400:
                assert code(response) == (400, "CURRENT_PASSWORD_MISMATCH")


# ── ④ 회사가 안 정해지면 ──


@pytest.mark.parametrize("state", ["two", "none", "inactive"])
def test_without_a_usable_sole_company_the_choosing_17_write_nothing(
    owner: Owner, fake: FakeStorage, state: str
) -> None:
    expected = {
        "two": (400, "COMPANY_AMBIGUOUS"),
        "none": (400, "COMPANY_NOT_FOUND"),
        "inactive": (403, "COMPANY_INACTIVE"),
    }[state]
    if state == "two":
        add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
        add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    elif state == "inactive":
        made = add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
        owner.execute("UPDATE company SET is_active = false WHERE id = %s", [made])
    operator, _ = operator_client(owner)
    before = (rows(owner), audit_lines(owner))
    for op, (method, path) in company_work().items():
        with CaptureQueriesContext(connection) as captured:
            response = send_passing(operator, op, method, path)
        if op in NOT_CHOOSING:
            assert response.status_code == NOT_CHOOSING[op], (state, op)
            assert reads(captured) == [], (state, op)  # 회사를 고르지 않는다
        else:
            assert code(response) == expected, (state, op, response.content.decode()[:300])
    assert (rows(owner), audit_lines(owner)) == before == ((0, 0, 0, 0), [])


# ── ⑤ 질의·본문의 companyId ──


def test_a_query_company_id_does_not_move_the_work_company(owner: Owner, solo: int, fake: FakeStorage) -> None:
    operator, _ = operator_client(owner)
    upload(operator, fake, owner)
    plain = operator.get("/api/documents").json()
    assert plain["count"] == 1  # 분모: 작업 회사의 문서 하나
    for other in (solo + 1000, 0):
        assert operator.get(f"/api/documents?companyId={other}").json() == plain
        assert (
            operator.get(f"/api/greenwash/checks?companyId={other}").json()
            == operator.get("/api/greenwash/checks").json()
        )
    for who in (operator, customer_client(solo)):
        for url, body in (
            ("/api/documents", {"fileName": "b.pdf", "sizeBytes": 1, "companyId": solo + 1000}),
            ("/api/runs", {"module": "greenwash", "documentId": 1, "companyId": solo + 1000}),
        ):
            assert who.post(url, data=body, content_type="application/json").status_code == 422, url
    assert count(owner, "core_documents") == 1


def test_a_customer_query_company_id_does_not_open_another_company(owner: Owner, fake: FakeStorage) -> None:
    a = add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    theirs = customer_client(b, "tenant-b")
    upload(theirs, fake, owner)  # B 에 올린 문서 하나(목록에 든다)
    mine = customer_client(a)
    plain = mine.get("/api/documents").json()
    assert plain["count"] == 0  # 분모: 내 회사에는 없다(B 에는 하나)
    assert mine.get(f"/api/documents?companyId={b}").json() == plain


# ── ⑥ 남의 회사 ──


def test_after_a_second_company_the_operator_stops_and_each_company_sees_its_own(
    owner: Owner, solo: int, fake: FakeStorage
) -> None:
    operator, admin = operator_client(owner)
    document_id = upload(operator, fake, owner)
    run_id = owner_done_run(owner, solo)
    confirmed = operator.put(
        f"/api/greenwash/runs/{run_id}/review",
        data={"state": "confirmed", "marks": []},
        content_type="application/json",
    )
    assert confirmed.status_code == 200, confirmed.content.decode()
    assert operator.get(f"/api/greenwash/runs/{run_id}/report").status_code == 200  # 분모: 하나일 때는 연다

    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    b_run = owner_done_run(owner, b)
    for url in (
        f"/api/greenwash/runs/{run_id}/result",
        f"/api/greenwash/runs/{run_id}/report",
        f"/api/greenwash/runs/{b_run}/report",  # 남의 회사(B)의 보고서도 — 작업 회사를 못 고른다
        f"/api/documents/{document_id}",
    ):
        assert code(operator.get(url)) == (400, "COMPANY_AMBIGUOUS"), url
    terms = operator.get("/api/greenwash/terms/default")
    assert terms.status_code == 200
    assert not any(word in terms.content.decode() for word in ("가 회사", "나 회사", "tenant-a", "tenant-b", "company"))

    theirs = customer_client(b, "tenant-b")
    for url in (
        f"/api/documents/{document_id}",
        f"/api/greenwash/runs/{run_id}/review",
        f"/api/greenwash/runs/{run_id}/report",
    ):
        assert theirs.get(url).status_code == 404, url
    mine = customer_client(solo)
    for url in (f"/api/documents/{document_id}", f"/api/greenwash/runs/{run_id}/report"):
        assert mine.get(url).status_code == 200, url  # 짝: 제 회사의 고객사 사용자는 연다
    review = mine.get(f"/api/greenwash/runs/{run_id}/review").json()
    assert review["confirmedBy"] == {"id": admin, "name": OPERATOR_NAME}


def upload(client: Client, fake: FakeStorage, owner: Owner) -> int:
    created = client.post(
        "/api/documents", data={"fileName": "a.pdf", "sizeBytes": len(PDF)}, content_type="application/json"
    )
    assert created.status_code == 201, created.content.decode()
    document_id: int = created.json()["document"]["id"]
    row = owner.execute("SELECT storage_key FROM core_documents WHERE id = %s", [document_id]).fetchone()
    assert row is not None
    fake.put(row[0], PDF)
    confirmed = client.post(f"/api/documents/{document_id}/confirm")
    assert confirmed.status_code == 200, confirmed.content.decode()
    return document_id


# ── ⑦ is_initial 운영 관리자 ──


def test_an_initial_operator_is_403_on_the_company_work_before_the_body(
    owner: Owner, solo: int, fake: FakeStorage
) -> None:
    initial, _ = operator_client(owner, initial=True)
    for op, (method, path) in company_work().items():
        with CaptureQueriesContext(connection) as captured:
            response = send_passing(initial, op, method, path)
        assert code(response) == (403, "PASSWORD_CHANGE_REQUIRED"), op
        assert reads(captured) == [], op
    bad_body = initial.post("/api/documents", data={}, content_type="application/json")
    assert code(bad_body) == (403, "PASSWORD_CHANGE_REQUIRED")  # 꼴 검사(422)보다 앞 — 인증 단계
    assert rows(owner) == (0, 0, 0, 0)
    owner.execute("UPDATE users SET is_initial = false WHERE username = 'ops'")
    changed, _ = login_again()
    assert changed.get("/api/documents").status_code == 200  # 짝: 바꾼 뒤에는 지난다


def login_again() -> tuple[Client, None]:
    logged = Client().post(
        "/api/auth/login", data={"username": "ops", "password": PASSWORD}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    return Client(headers={"Authorization": f"Bearer {logged.json()['access']}"}), None


# ── ⑧ 감사 ──


def test_the_operators_audit_lines_name_the_admin_and_the_work_company(
    owner: Owner, solo: int, fake: FakeStorage
) -> None:
    operator, admin = operator_client(owner)
    document_id = upload(operator, fake, owner)
    made = operator.post(
        "/api/runs", data={"module": "greenwash", "documentId": document_id}, content_type="application/json"
    )
    assert made.status_code == 201, made.content.decode()
    run_id = owner_done_run(owner, solo)
    confirmed = operator.put(
        f"/api/greenwash/runs/{run_id}/review",
        data={"state": "confirmed", "marks": []},
        content_type="application/json",
    )
    assert confirmed.status_code == 200, confirmed.content.decode()
    assert operator.get(f"/api/greenwash/runs/{run_id}/report").status_code == 200
    lines = audit_lines(owner)
    assert [line[3] for line in lines] == ["upload", "run", "confirm", "download"]  # 분모: 넷 다 적혔다
    assert set(lines) == {("admin", admin, solo, action) for action in ("upload", "run", "confirm", "download")}


# ── ⑨ 쿠키 길 ──


def test_a_cookie_session_stays_a_customer_and_ignores_a_query_company_id(owner: Owner, fake: FakeStorage) -> None:
    a = add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    theirs = customer_client(b, "tenant-b")
    upload(theirs, fake, owner)  # B 에 올린 문서 하나(목록에 든다)
    cookie = Client()
    login(cookie, tenant_id="tenant-a")
    assert cookie.get("/api/me").json()["companyId"] == a
    plain = cookie.get("/api/documents").json()
    assert cookie.get(f"/api/documents?companyId={b}").json() == plain
    assert plain["count"] == 0
    assert cookie.get("/api/users").status_code == 401  # 쿠키 세션은 운영 관리자 경로에 닿지 않는다(Bearer 만)


# ── ⑩ 영문번역(MARC-ENT-380) ──


def test_the_operator_reads_and_runs_translation_in_the_work_company(
    owner: Owner, solo: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """회사 하나에서 운영 관리자가 영문번역 결과를 읽고 실행을 만든다. 거절 쪽은 회사 둘 400(test_tenant_paths·
    test_translation ⓒ)·⑪ 남의 회사가 문다. 만들기는 진짜 등록부로 — `fake` 고정물(그린워싱 가짜 등록부)을 쓰지
    않는다."""
    from tests.security.test_translation import MARKER, OPTIONS, owner_done_translation, result_url

    storage = plug_storage(monkeypatch, FakeStorage())
    monkeypatch.setattr(hooks, "enqueue_run", ignore)
    assert actions.REGISTRY.default_of("translation").module == "translation"  # 진짜 등록부에 영문번역 기본 흐름
    operator, admin = operator_client(owner)
    run_id = owner_done_translation(owner, storage, solo)
    shown = operator.get(result_url(run_id))
    assert shown.status_code == 200, shown.content.decode()
    mine = customer_client(solo).get(result_url(run_id))  # 짝: 고객사 사용자와 같은 본문
    assert (mine.status_code, shown.content) == (200, mine.content)
    assert shown.json()["variants"][0]["translatedText"].count(MARKER) == 2

    document_id = upload(operator, storage, owner)
    made = operator.post(
        "/api/runs",
        data={"module": "translation", "documentId": document_id, "options": OPTIONS},
        content_type="application/json",
    )
    assert made.status_code == 201, made.content.decode()
    row = owner.execute(
        "SELECT company_id, module, created_by_user_id FROM run_runs WHERE id = %s", [made.json()["id"]]
    ).fetchone()
    assert row == (solo, "translation", admin)
    assert [line for line in audit_lines(owner) if line[3] == "run"] == [("admin", admin, solo, "run")]


# ── ⑪ 영문번역 남의 회사(OP2 ②) ──


def test_a_translation_run_of_the_operator_is_ambiguous_after_a_second_company_and_stays_its_companys(
    owner: Owner, solo: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """회사 A 하나일 때 운영 관리자가 영문번역 실행을 만들고 결과를 읽는다 → 회사 B 를 더하면 운영 관리자는 결과·실행·
    목록이 400 company_ambiguous(실행·결과 표 SELECT 0 — 회사를 먼저 고른다, ★D), B 의 고객사 사용자는 그 id 404,
    A 의 고객사 사용자는 200(분모)."""
    from tests.security.test_translation import MARKER, OPTIONS, owner_done_translation, result_url

    storage = plug_storage(monkeypatch, FakeStorage())
    monkeypatch.setattr(hooks, "enqueue_run", ignore)
    operator, _ = operator_client(owner)
    made = operator.post(
        "/api/runs",
        data={"module": "translation", "documentId": upload(operator, storage, owner), "options": OPTIONS},
        content_type="application/json",
    )
    assert made.status_code == 201, made.content.decode()
    made_id: int = made.json()["id"]
    done_id = owner_done_translation(owner, storage, solo)
    assert operator.get(result_url(done_id)).status_code == 200  # 분모: 하나일 때는 연다

    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    for url in (result_url(done_id), f"/api/runs/{made_id}", "/api/runs"):
        with CaptureQueriesContext(connection) as captured:
            response = operator.get(url)
        assert code(response) == (400, "COMPANY_AMBIGUOUS"), url
        assert [q["sql"] for q in captured.captured_queries if '"run_' in q["sql"]] == [], url
        assert MARKER not in response.content.decode()

    theirs = customer_client(b, "tenant-b")
    for url in (result_url(done_id), f"/api/runs/{made_id}"):
        hidden = theirs.get(url)
        assert code(hidden) == (404, "NOT_FOUND"), url
        assert MARKER not in hidden.content.decode()
    mine = customer_client(solo)
    shown = mine.get(result_url(done_id))
    assert shown.status_code == 200, shown.content.decode()
    assert shown.json()["variants"][0]["translatedText"].count(MARKER) == 2
    assert mine.get(f"/api/runs/{made_id}").json()["module"] == "translation"


# ── ⑫ 실행 목록의 모듈(OP2 ②) ──


def owner_run(owner: Owner, company_id: int, document_id: int, module: str) -> int:
    """그 회사의 고객사 사용자(id 7)가 만든 실행 하나(queued). 주인 역할로."""
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, %s, %s, %s, '{}', '{}', 'service', 'queued', 0, 0, 7) RETURNING id",
        [company_id, document_id, module, f"{module}.probe@1"],
    ).fetchone()
    assert row is not None
    return int(row[0])


def test_the_operator_lists_the_operator_modules_and_a_customer_lists_every_module(
    owner: Owner, solo: int, fake: FakeStorage
) -> None:
    """회사 하나에서 고객사 사용자의 실행 셋(inventory·translation·greenwash) — 운영 관리자의 목록(질의 없음)은
    OPERATOR_RUN_MODULES 의 둘, 고객사 사용자의 목록은 셋(분모)."""
    operator, _ = operator_client(owner)
    customer = customer_client(solo)
    document_id = upload(customer, fake, owner)
    runs = {module: owner_run(owner, solo, document_id, module) for module in ("inventory", "translation", "greenwash")}

    def listed(client: Client, query: str = "") -> tuple[int, set[tuple[int, str]]]:
        body = client.get(f"/api/runs{query}").json()
        return body["count"], {(line["id"], line["module"]) for line in body["results"]}

    assert listed(operator) == (2, {(runs["translation"], "translation"), (runs["greenwash"], "greenwash")})
    assert listed(operator, "?module=translation") == (1, {(runs["translation"], "translation")})
    assert listed(operator, "?module=inventory") == (0, set())
    assert listed(customer) == (3, {(run_id, module) for module, run_id in runs.items()})  # 분모


# ── ⑬ 데이터 검증(MARC-ENT-390 — DV1e) ──


def test_the_operator_reads_and_runs_dataverify_and_stops_after_a_second_company(
    owner: Owner, solo: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """회사 하나에서 운영 관리자가 데이터 검증 결과를 읽고(본문 = 고객사 사용자의 것) 문서 없는 실행을 만든다(행 회사 =
    작업 회사·created_by = 운영 관리자·감사 run 줄 admin). 회사 B 를 더하면 운영 관리자는 결과 400 company_ambiguous
    (실행·결과 표 SELECT 0), B 의 고객사 사용자는 그 id 404, A 의 고객사 사용자는 200(분모). 만들기는 진짜 등록부로 —
    `fake` 고정물(그린워싱 가짜 등록부)을 쓰지 않는다(큐 갈고리는 버림, 공급사 0)."""
    from esgapi.dataverify.tests.flows.support import options
    from tests.security.test_dataverify import MARKER, owner_done_dataverify, result_url

    monkeypatch.setattr(hooks, "enqueue_run", ignore)
    assert actions.REGISTRY.default_of("dataverify").module == "dataverify"  # 진짜 등록부에 데이터 검증 흐름
    operator, admin = operator_client(owner)
    done_id = owner_done_dataverify(owner, solo)
    shown = operator.get(result_url(done_id))
    assert shown.status_code == 200, shown.content.decode()
    mine = customer_client(solo).get(result_url(done_id))  # 짝: 고객사 사용자와 같은 본문
    assert (mine.status_code, shown.content) == (200, mine.content)

    made = operator.post(
        "/api/runs", data={"module": "dataverify", "options": options()}, content_type="application/json"
    )
    assert made.status_code == 201, made.content.decode()
    row = owner.execute(
        "SELECT company_id, module, document_id, created_by_user_id FROM run_runs WHERE id = %s", [made.json()["id"]]
    ).fetchone()
    assert row == (solo, "dataverify", None, admin)
    assert [line for line in audit_lines(owner) if line[3] == "run"] == [("admin", admin, solo, "run")]

    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    with CaptureQueriesContext(connection) as captured:
        refused = operator.get(result_url(done_id))
    assert code(refused) == (400, "COMPANY_AMBIGUOUS")
    assert [q["sql"] for q in captured.captured_queries if '"run_' in q["sql"]] == []
    assert MARKER not in refused.content.decode()
    hidden = customer_client(b, "tenant-b").get(result_url(done_id))
    assert code(hidden) == (404, "NOT_FOUND")
    assert MARKER not in hidden.content.decode()
    assert customer_client(solo).get(result_url(done_id)).status_code == 200  # 분모


def test_the_operator_lists_dataverify_runs_of_one_company_and_stops_after_a_second(owner: Owner, solo: int) -> None:
    """목록 GET /dataverify/runs(DV1g): 회사 하나면 운영 관리자는 그 회사의 실행 목록 200(본문 = 고객사 사용자의 것).
    회사 B 를 더하면 운영 관리자는 400 company_ambiguous(실행 표 SELECT 0), B 의 고객사 사용자는 A 의 실행 0, A 의
    고객사 사용자는 그대로(분모)."""
    from tests.security.test_dataverify import LIST_COMPANY, owner_listed_dataverify

    operator, _admin = operator_client(owner)
    run_id = owner_listed_dataverify(owner, solo)
    url = "/api/dataverify/runs"
    shown = operator.get(url)
    assert shown.status_code == 200, shown.content.decode()
    assert [r["id"] for r in shown.json()["results"]] == [run_id]
    mine = customer_client(solo).get(url)
    assert (mine.status_code, mine.json()) == (200, shown.json())  # 짝: 고객사 사용자와 같은 본문

    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    with CaptureQueriesContext(connection) as captured:
        refused = operator.get(url)
    assert code(refused) == (400, "COMPANY_AMBIGUOUS")
    assert [q["sql"] for q in captured.captured_queries if '"run_' in q["sql"]] == []
    hidden = customer_client(b, "tenant-b").get(url)
    assert (hidden.status_code, hidden.json()["count"], hidden.json()["results"]) == (200, 0, [])
    assert LIST_COMPANY.encode() not in hidden.content and LIST_COMPANY not in str(hidden.json())
    assert [r["id"] for r in customer_client(solo).get(url).json()["results"]] == [run_id]  # 분모


# ── ⑭ 데이터 검증 결과 파일(DV1e — 22 요청) ──

WORKBOOK: Final = b"PK\x03\x04 synthetic dataverify workbook"


def owner_output_file(owner: Owner, storage: FakeStorage, company_id: int, run_id: int, name: str) -> None:
    """그 실행의 출력 파일 하나(단계 NULL — 바이트는 가짜 저장소에). 주인 역할로."""
    key = f"runs/{company_id}/{run_id}/out/{name}"
    storage.put(key, WORKBOOK)
    owner.execute(
        "INSERT INTO run_files (created_at, company_id, run_id, step, name, media_type, storage_key, size_bytes, "
        "sha256) VALUES (now(), %s, %s, NULL, %s, "
        "'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', %s, %s, %s)",
        [company_id, run_id, name, key, len(WORKBOOK), "0" * 64],
    )


def test_the_operator_downloads_the_dataverify_workbook_of_the_work_company_only(
    owner: Owner, solo: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """작업 회사(회사 하나)면 runs_file_get 으로 dataverify-report.xlsx 200·PK·감사 run_file_downloaded admin. 분모:
    inventory 실행의 파일은 운영 관리자에게 404(OPERATOR_RUN_MODULES 밖). 회사 B 를 더하면 B 의 고객사 사용자는 A 의
    파일 404, 운영 관리자는 400(작업 회사는 「하나뿐인 회사」라 남의 회사를 고를 길이 없다)."""
    from tests.security.test_dataverify import owner_done_dataverify

    storage = plug_storage(monkeypatch, FakeStorage())
    operator, admin = operator_client(owner)
    run_id = owner_done_dataverify(owner, solo)
    owner_output_file(owner, storage, solo, run_id, "dataverify-report.xlsx")
    url = f"/api/runs/{run_id}/files/dataverify-report.xlsx"
    got = operator.get(url)
    assert got.status_code == 200, got.content.decode()
    assert got.content == WORKBOOK and got.content[:4] == b"PK\x03\x04"
    downloads = owner.execute(
        "SELECT actor_kind, actor_user_id, company_id, event, target_label FROM core_audit_events "
        "WHERE action = 'download' ORDER BY id"
    ).fetchall()
    assert downloads == [("admin", admin, solo, "run_file_downloaded", "dataverify-report.xlsx")]

    document_id = upload(customer_client(solo), storage, owner)
    other = owner_run(owner, solo, document_id, "inventory")
    owner_output_file(owner, storage, solo, other, "inventory.xlsx")
    assert code(operator.get(f"/api/runs/{other}/files/inventory.xlsx")) == (404, "NOT_FOUND")  # 분모

    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    assert code(customer_client(b, "tenant-b").get(url)) == (404, "NOT_FOUND")
    assert code(operator.get(url)) == (400, "COMPANY_AMBIGUOUS")
    assert customer_client(solo).get(url).content == WORKBOOK  # 분모: A 의 고객사 사용자는 받는다


# ── ⑮ 중대성평가 IRO(MARC-ENT-419 — IR3b) ──


def test_the_operator_reads_and_runs_materiality_and_stops_after_a_second_company(
    owner: Owner, solo: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """회사 하나에서 운영 관리자가 중대성평가 IRO 결과를 읽고(본문 = 고객사 사용자의 것) 문서 없는 실행을
    만든다(행 회사 = 작업 회사·created_by = 운영 관리자·감사 run 줄 admin). 회사 B 를 더하면 운영 관리자는 결과 400
    company_ambiguous(실행·결과 표 SELECT 0), B 의 고객사 사용자는 그 id 404, A 의 고객사 사용자는 200(분모).
    만들기는 진짜 등록부로 — `fake` 고정물을 쓰지 않는다(큐 갈고리는 버림, 공급사 0)."""
    from esgapi.materiality.tests.flows.support import options
    from tests.security.test_materiality import MARKER, owner_done_materiality, result_url

    monkeypatch.setattr(hooks, "enqueue_run", ignore)
    assert actions.REGISTRY.default_of("materiality").module == "materiality"  # 진짜 등록부에 IRO 흐름
    operator, admin = operator_client(owner)
    done_id = owner_done_materiality(owner, solo)
    shown = operator.get(result_url(done_id))
    assert shown.status_code == 200, shown.content.decode()
    mine = customer_client(solo).get(result_url(done_id))  # 짝: 고객사 사용자와 같은 본문
    assert (mine.status_code, shown.content) == (200, mine.content)

    made = operator.post(
        "/api/runs", data={"module": "materiality", "options": options()}, content_type="application/json"
    )
    assert made.status_code == 201, made.content.decode()
    row = owner.execute(
        "SELECT company_id, module, document_id, created_by_user_id FROM run_runs WHERE id = %s", [made.json()["id"]]
    ).fetchone()
    assert row == (solo, "materiality", None, admin)
    assert [line for line in audit_lines(owner) if line[3] == "run"] == [("admin", admin, solo, "run")]

    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    with CaptureQueriesContext(connection) as captured:
        refused = operator.get(result_url(done_id))
    assert code(refused) == (400, "COMPANY_AMBIGUOUS")
    assert [q["sql"] for q in captured.captured_queries if '"run_' in q["sql"]] == []
    assert MARKER not in refused.content.decode()
    hidden = customer_client(b, "tenant-b").get(result_url(done_id))
    assert code(hidden) == (404, "NOT_FOUND")
    assert MARKER not in hidden.content.decode()
    assert customer_client(solo).get(result_url(done_id)).status_code == 200  # 분모


# ── ⑯ 중대성평가 IRO 엑셀 둘(IR3b) ──

MATERIALITY_FILES: Final = ("materiality-websearch.xlsx", "materiality-final-report.xlsx")


def test_the_operator_downloads_both_materiality_workbooks_of_the_work_company_only(
    owner: Owner, solo: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """작업 회사(회사 하나)면 runs_file_get 으로 엑셀 둘 각 200·PK·감사 run_file_downloaded admin. 분모:
    inventory 실행의 파일은 운영 관리자에게 404(OPERATOR_RUN_MODULES 밖). 회사 B 를 더하면 B 의 고객사 사용자는
    A 의 파일 404, 운영 관리자는 400."""
    from tests.security.test_materiality import owner_done_materiality

    storage = plug_storage(monkeypatch, FakeStorage())
    operator, admin = operator_client(owner)
    run_id = owner_done_materiality(owner, solo)
    for name in MATERIALITY_FILES:
        owner_output_file(owner, storage, solo, run_id, name)
    urls = [f"/api/runs/{run_id}/files/{name}" for name in MATERIALITY_FILES]
    for url in urls:
        got = operator.get(url)
        assert got.status_code == 200, got.content.decode()
        assert got.content == WORKBOOK and got.content[:4] == b"PK\x03\x04"
    downloads = owner.execute(
        "SELECT actor_kind, actor_user_id, company_id, event, target_label FROM core_audit_events "
        "WHERE action = 'download' ORDER BY id"
    ).fetchall()
    assert downloads == [("admin", admin, solo, "run_file_downloaded", name) for name in MATERIALITY_FILES]

    document_id = upload(customer_client(solo), storage, owner)
    other = owner_run(owner, solo, document_id, "inventory")
    owner_output_file(owner, storage, solo, other, "inventory.xlsx")
    assert code(operator.get(f"/api/runs/{other}/files/inventory.xlsx")) == (404, "NOT_FOUND")  # 분모

    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    for url in urls:
        assert code(customer_client(b, "tenant-b").get(url)) == (404, "NOT_FOUND")
        assert code(operator.get(url)) == (400, "COMPANY_AMBIGUOUS")
        assert customer_client(solo).get(url).content == WORKBOOK  # 분모: A 의 고객사 사용자는 받는다


# ── ⑰ 중대성평가 IRO 실행 목록(IR3c) ──


def test_the_operator_lists_materiality_runs_of_one_company_and_stops_after_a_second(owner: Owner, solo: int) -> None:
    """목록 GET /materiality/runs(IR3c): 회사 하나면 운영 관리자는 그 회사의 실행 목록 200(고객사 사용자가 만든 실행
    듦 — 본문 = 고객사 사용자의 것). 회사 B 를 더하면 운영 관리자는 400 company_ambiguous(실행 표 SELECT 0), B 의
    고객사 사용자는 A 의 실행 0, A 의 고객사 사용자는 그대로(분모)."""
    from tests.security.test_materiality import LIST_COMPANY, owner_listed_materiality

    operator, _admin = operator_client(owner)
    run_id = owner_listed_materiality(owner, solo)
    url = "/api/materiality/runs"
    shown = operator.get(url)
    assert shown.status_code == 200, shown.content.decode()
    assert [r["id"] for r in shown.json()["results"]] == [run_id]
    mine = customer_client(solo).get(url)
    assert (mine.status_code, mine.json()) == (200, shown.json())  # 짝: 고객사 사용자와 같은 본문

    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    with CaptureQueriesContext(connection) as captured:
        refused = operator.get(url)
    assert code(refused) == (400, "COMPANY_AMBIGUOUS")
    assert [q["sql"] for q in captured.captured_queries if '"run_' in q["sql"]] == []
    hidden = customer_client(b, "tenant-b").get(url)
    assert (hidden.status_code, hidden.json()["count"], hidden.json()["results"]) == (200, 0, [])
    assert LIST_COMPANY.encode() not in hidden.content and LIST_COMPANY not in str(hidden.json())
    assert [r["id"] for r in customer_client(solo).get(url).json()["results"]] == [run_id]  # 분모


# ── ⑱ Scope 3 코랩 결과·빈 양식(S3K1 — 469-4 「대신하기」 꼴, 진짜 작업 회사 고르기) ──


def test_the_operator_reads_a_scope3_result_of_one_company_and_stops_after_a_second(owner: Owner, solo: int) -> None:
    """결과 GET /inventory/scope3/runs/{id}/result: 회사 하나면 운영 관리자는 그 회사의 Scope 3 결과 200(본문 = 고객사
    사용자의 것), 빈 양식 200(같은 바이트). 회사 B 를 더하면 결과는 400 company_ambiguous(실행·결과 표 SELECT 0) —
    빈 양식은 회사를 고르지 않아 그대로 200, B 의 고객사 사용자는 404, A 의 고객사 사용자는 그대로(분모)."""
    from tests.security.test_tenant_paths import SCOPE3_REJECTED, owner_done_scope3

    operator, _admin = operator_client(owner)
    run_id = owner_done_scope3(owner, solo)
    url = f"/api/inventory/scope3/runs/{run_id}/result"
    shown = operator.get(url)
    assert (shown.status_code, shown.json()) == (200, SCOPE3_REJECTED), shown.content.decode()
    mine = customer_client(solo).get(url)
    assert (mine.status_code, mine.content) == (200, shown.content)  # 짝: 고객사 사용자와 같은 본문
    template = operator.get("/api/inventory/scope3/template")
    assert template.status_code == 200
    assert template.content == customer_client(solo).get("/api/inventory/scope3/template").content

    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    with CaptureQueriesContext(connection) as captured:
        refused = operator.get(url)
    assert code(refused) == (400, "COMPANY_AMBIGUOUS")
    assert [q["sql"] for q in captured.captured_queries if '"run_' in q["sql"]] == []
    assert operator.get("/api/inventory/scope3/template").content == template.content  # 회사를 고르지 않는다
    assert code(customer_client(b, "tenant-b").get(url)) == (404, "NOT_FOUND")
    assert customer_client(solo).get(url).status_code == 200  # 분모
