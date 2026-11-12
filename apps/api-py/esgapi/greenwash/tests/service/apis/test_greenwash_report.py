# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""엑셀 보고서 GET 의 몸(밴드 G1b-2a §3 업무). 진짜 DB, 세션은 EDK 교환(login — 회사 A 의 고객사 사용자).

    404   없는 실행 · 남의 회사 · 다른 모듈 · 다른 flow_id
    409   RUN_NOT_DONE(queued·processing·failed) · NO_REPORT(dry-run) · NOT_CONFIRMED(검토 없음·in_review)
    200   xlsx 바이트·Content-Disposition · 확정본은 채택 문장만 · DB 왕복 결과의 요약 파트 차례 = parts 차례(B3)
    감사  200 마다 download 한 줄(칸 원문) · 거절은 줄 0 · build 가 던지면 줄 0(R3)
    쿼리  옛 ?compareBase=2 는 무시된다(★H — 선언 밖 쿼리)
    ②    목록 줄 reportYear·previousDocumentId = 문서 칸(PATCH 로 세운 값), pageCount 는 결과에서(J2 (가)) ·
          create_review 는 검토 unique 만 넘기고 다른 제약·이름 모름은 다시 던진다(MARC-ISSUE-220 (2)) ·
          사유만 바꾼 제외는 감사 0(220 (1) 처분 Q3)

★ 실행·결과 행은 seed(apps.get_model)로 심는다 — runs.models 를 import 하지 않는다(계약 나). 자료는 지어낸 것.
"""

import io
from types import SimpleNamespace
from typing import Any

import pytest
from django.apps import apps
from django.db import IntegrityError
from django.test import Client
from openpyxl import load_workbook

from esgapi.core.models import AuditEventRow
from esgapi.greenwash.flows.colab_e0 import frequency_extras
from esgapi.greenwash.models import GreenwashReviewRow
from esgapi.greenwash.outputs import xlsx
from esgapi.greenwash.service.actions import report as report_actions
from esgapi.greenwash.service.services import review as review_services
from esgapi.greenwash.tests.service import seed
from tests.support.http import login

pytestmark = pytest.mark.django_db

NORMAL = seed.example("result-normal")  # items 넷, parts 셋


def user_id(company_id: int) -> int:
    user = apps.get_model("user", "User").for_company(company_id).get(username="edk-user-1")
    return int(user.pk)


def get(client: Client, run_id: int, query: str = "") -> Any:
    return client.get(f"/api/greenwash/runs/{run_id}/report{query}")


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def sheets(response: Any) -> dict[str, list[tuple[Any, ...]]]:
    return sheets_of(response.content)


def sheets_of(content: bytes) -> dict[str, list[tuple[Any, ...]]]:
    book = load_workbook(io.BytesIO(content), read_only=True)
    return {name: [tuple(row) for row in book[name].iter_rows(values_only=True)] for name in book.sheetnames}


def downloads(company_id: int) -> list[tuple[Any, ...]]:
    rows = AuditEventRow.for_company(company_id).filter(action="download").order_by("id")
    return [
        (r.actor_kind, r.actor_user_id, r.action, r.event, r.result, r.target_kind, r.target_id, r.target_label)
        for r in rows
    ]


def confirm(client: Client, run_id: int, marks: list[dict[str, Any]]) -> None:
    put = client.put(
        f"/api/greenwash/runs/{run_id}/review",
        data={"state": "confirmed", "marks": marks},
        content_type="application/json",
    )
    assert put.status_code == 200, put.content.decode()


@pytest.fixture
def done_run(client: Client, companies: tuple[int, int]) -> int:
    login(client)
    return seed.run(companies[0], result=NORMAL)


# ── 404 ──


def test_a_missing_or_foreign_run_is_404(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a, b = companies
    other_company = seed.run(b, result=NORMAL)
    other_module = seed.run(a, module="inventory", result=NORMAL)
    other_flow = seed.run(a, result=NORMAL, flow_id="greenwash.other@E1")
    for run_id in (done_run + 1000, other_company, other_module, other_flow):
        assert code(get(client, run_id)) == (404, "NOT_FOUND"), run_id
        assert code(get(client, run_id, "?confirmed=true")) == (404, "NOT_FOUND"), run_id
    assert downloads(a) == downloads(b) == []
    assert get(client, done_run).status_code == 200  # 분모


def test_the_flow_filter_is_the_e0_constant() -> None:
    assert report_actions.E0_FLOW == "greenwash.colab@E0"


# ── 409 ──


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_a_run_that_is_not_done_is_409(client: Client, companies: tuple[int, int], status: str) -> None:
    login(client)
    run_id = seed.run(companies[0], status=status)
    assert code(get(client, run_id)) == (409, "RUN_NOT_DONE")
    assert code(get(client, run_id, "?confirmed=true")) == (409, "RUN_NOT_DONE")
    assert downloads(companies[0]) == []


def test_a_dry_run_has_no_report(client: Client, companies: tuple[int, int]) -> None:
    login(client)
    run_id = seed.run(companies[0], result=seed.example("result-dry-run"))
    assert code(get(client, run_id)) == (409, "NO_REPORT")
    assert code(get(client, run_id, "?confirmed=true")) == (409, "NO_REPORT")  # dry-run 이 확정 검사보다 먼저
    assert downloads(companies[0]) == []


def test_the_confirmed_copy_needs_a_confirmed_review(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a = companies[0]
    assert code(get(client, done_run, "?confirmed=true")) == (409, "NOT_CONFIRMED")  # 검토 행 없음
    put = client.put(
        f"/api/greenwash/runs/{done_run}/review",
        data={"marks": [{"itemIndex": 0, "decision": "adopted", "excludeReason": None}]},
        content_type="application/json",
    )
    assert put.json()["state"] == "in_review"
    assert code(get(client, done_run, "?confirmed=true")) == (409, "NOT_CONFIRMED")
    assert downloads(a) == []
    assert get(client, done_run).status_code == 200  # 확정 전 판은 된다


# ── 200 ──


def test_the_report_is_the_xlsx_of_the_result(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a = companies[0]
    response = get(client, done_run)
    assert response.status_code == 200
    assert response["Content-Type"] == xlsx.MEDIA_TYPE
    assert response["Content-Disposition"] == 'attachment; filename="greenwash-report.xlsx"'
    book = sheets(response)
    assert tuple(book) == xlsx.SHEETS
    assert len(book["문장"]) - 1 == len(NORMAL["items"])
    assert all(row[0] != "판" for row in book["설정"])
    flow = sheets_of(xlsx.build(NORMAL, added_terms=frequency_extras(NORMAL["extraTerms"])))
    assert book["단어 빈도"] == flow["단어 빈도"]  # 흐름 report 단계의 엑셀과 같은 추가 단어 표시(검증 R1)
    assert downloads(a) == [
        ("service", user_id(a), "download", "greenwash_report_downloaded", "success", "report", done_run,
         "greenwash-report.xlsx"),
    ]  # fmt: skip
    get(client, done_run)
    assert len(downloads(a)) == 2  # 내려받을 때마다 한 줄


def test_the_confirmed_report_holds_only_the_adopted(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a = companies[0]
    confirm(client, done_run, [{"itemIndex": 1, "decision": "excluded", "excludeReason": "근거 있음"}])
    response = get(client, done_run, "?confirmed=true")
    assert response.status_code == 200, response.content
    assert response["Content-Disposition"] == 'attachment; filename="greenwash-report.xlsx"'
    book = sheets(response)
    sentences = [row[3] for row in book["문장"][1:]]
    assert sentences == [NORMAL["items"][i]["sentence"] for i in (0, 2, 3)]
    summary = dict(book["요약"][1:])
    assert (summary["전체 문장 수"], summary["등급 Mid"]) == (3, 1)
    assert book["설정"][-1] == ("판", "확정본 — 채택 3 / 전체 4")
    assert downloads(a)[-1][-1] == "greenwash-report.xlsx · 확정본"
    assert len(sheets(get(client, done_run))["문장"]) - 1 == 4  # 확정 뒤에도 확정 전 판은 전 문장


def test_the_summary_parts_follow_the_result_parts_after_the_db(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    """jsonb 는 열쇠 차례를 바꾼다(B3) — 심은 결과의 byPart 를 DB 에서 읽으면 parts 차례가 아니다(분모)."""
    a = companies[0]
    names = [p["name"] for p in NORMAL["parts"]]
    assert list(NORMAL["counts"]["byPart"]) == names
    stored = apps.get_model("runs", "RunResultRow").for_company(a).get(run_id=done_run).body
    assert list(stored["counts"]["byPart"]) != names  # DB 왕복이 차례를 바꿨다(★B 실측)
    rows = [name for name, _ in sheets(get(client, done_run))["요약"][1:] if " · " in name]
    assert list(dict.fromkeys(r.split(" · ")[0] for r in rows)) == names


def test_an_old_compare_base_query_is_ignored(client: Client, companies: tuple[int, int], done_run: int) -> None:
    plain = get(client, done_run)
    with_base = get(client, done_run, "?compareBase=2")
    assert with_base.status_code == plain.status_code == 200
    assert sheets(with_base) == sheets(plain)
    assert code(get(client, done_run, "?confirmed=true&compareBase=2")) == (409, "NOT_CONFIRMED")


def test_a_build_failure_writes_no_audit(
    companies: tuple[int, int], done_run: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object, **__: object) -> bytes:
        raise RuntimeError("심은 실패")

    monkeypatch.setattr(report_actions.xlsx, "build", broken)
    client = Client(raise_request_exception=False)
    login(client)
    assert get(client, done_run).status_code == 500
    assert downloads(companies[0]) == []


# ── ② 목록 줄 문서 칸 ──


def test_the_checks_row_reads_the_document_cells(client: Client, companies: tuple[int, int]) -> None:
    a = companies[0]
    login(client)
    first = seed.document(a, name="가상-보고서-2024.pdf")
    second = seed.document(a, name="가상-보고서-2025.pdf")
    seed.run(a, result=NORMAL, document_id=second)
    patched = client.patch(
        f"/api/documents/{second}",
        data={"reportYear": 2025, "previousDocumentId": first},
        content_type="application/json",
    )
    assert patched.status_code == 200, patched.content.decode()
    body = client.get("/api/greenwash/checks").json()
    (row,) = [d for d in body["documents"] if d["documentId"] == second]
    assert (row["reportYear"], row["previousDocumentId"]) == (2025, first)
    assert row["pageCount"] == NORMAL["source"]["pageCount"]  # 쪽 수는 그대로 실행 결과에서(J2 (가))


def test_an_unset_document_cell_is_null(client: Client, companies: tuple[int, int], done_run: int) -> None:
    (row,) = client.get("/api/greenwash/checks").json()["documents"]
    assert (row["reportYear"], row["previousDocumentId"]) == (None, None)  # 분모: 칸이 비면 null


# ── ② 검토 만들기 경합 좁힘 ──


def _raising(constraint: str | None) -> Any:
    """create 가 diag 의 제약 이름이 constraint 인 IntegrityError 를 던지는 가짜 표(다른 제약은 자연스럽게 못 만든다 —
    run_id 는 외래 키가 아니고 회사 외래 키는 뒤로 미뤄 검사하며 state 는 pending 고정이다, critic R6)."""
    cause = Exception("psycopg 의 자리")
    cause.diag = SimpleNamespace(constraint_name=constraint)  # pyright: ignore[reportAttributeAccessIssue]

    def create(**_: object) -> None:
        raise IntegrityError("심은 IntegrityError") from cause

    def for_company(_company_id: int) -> SimpleNamespace:
        return SimpleNamespace(create=create)

    return SimpleNamespace(for_company=for_company)


def test_create_review_passes_only_the_review_unique(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(review_services, "GreenwashReviewRow", _raising(review_services.REVIEW_UNIQUE))
    review_services.create_review(company_id=companies[0], run_id=1)  # 겹친 PUT 이 먼저 만들었다 — 넘김


def test_a_second_create_review_on_the_real_unique_is_passed(companies: tuple[int, int], done_run: int) -> None:
    """진짜 DB 의 unique (company_id, run_id) 가 둘째 INSERT 를 막고, 그 제약 이름을 읽어 넘긴다(검증 2 B1)."""
    a = companies[0]
    review_services.create_review(company_id=a, run_id=done_run)
    first = GreenwashReviewRow.for_company(a).get(run_id=done_run).pk
    review_services.create_review(company_id=a, run_id=done_run)  # 던지지 않는다
    assert list(GreenwashReviewRow.for_company(a).filter(run_id=done_run).values_list("pk", flat=True)) == [first]


@pytest.mark.parametrize("constraint", ["greenwash_reviews_state_check", None], ids=["other", "unknown"])
def test_create_review_reraises_another_integrity_error(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch, constraint: str | None
) -> None:
    monkeypatch.setattr(review_services, "GreenwashReviewRow", _raising(constraint))
    with pytest.raises(IntegrityError, match="심은 IntegrityError"):
        review_services.create_review(company_id=companies[0], run_id=1)
    assert GreenwashReviewRow.for_company(companies[0]).count() == 0


def test_a_reason_only_change_is_not_audited(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a = companies[0]

    def exclude(reason: str) -> None:
        put = client.put(
            f"/api/greenwash/runs/{done_run}/review",
            data={"marks": [{"itemIndex": 0, "decision": "excluded", "excludeReason": reason}]},
            content_type="application/json",
        )
        assert put.status_code == 200, put.content.decode()

    exclude("첫 사유")
    exclude("다른 사유")
    rows = AuditEventRow.for_company(a).filter(action="exclude").count()
    assert rows == 1  # 처음 제외만 한 줄(MARC-ISSUE-220 (1) 처분 Q3)
