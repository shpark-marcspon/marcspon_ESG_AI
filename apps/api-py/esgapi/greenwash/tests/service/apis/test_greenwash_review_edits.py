# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""검토 고침(review@2 의 edits — 밴드 G1b-3 ①). 업무 층: 진짜 DB, 세션은 EDK 교환(login — 회사 A 의 고객사 사용자
「김담당」)과 운영 관리자 Bearer.

    저장·응답 = GET · 정규화(strip·빈 항목 버림·AI 와 같은 칸 null) · 칸별 null · 미검토 문장 고침 → in_review
    marks·edits 갈아 넣기가 서로의 칸을 안 건드림 · 칸마다 때·사람(그 칸 값이 바뀐 PUT 에서만)
    확정 PUT 의 edits 는 저장 뒤 잠김 · 확정 뒤 edits 409·행 그대로 · 400 갈래(문장 원문)·행 0
    결과 GET 바이트가 고침 앞뒤 같음 · 고침만 PUT 감사 0(분모: 제외 하나 → exclude 한 줄)
    검토 GET 쿼리 수가 고친 문장 1·5 에서 같음
    권한 둘: 고객사 사용자의 editedBy · 운영 관리자가 작업 회사(하나뿐인 활성 회사)에서 고침·확정 · 회사 둘이면 400
    company_ambiguous·행 0 · 남의 회사 고객사 id 는 「알 수 없는 사용자」

★ 실행·결과 행은 seed(apps.get_model)로 심는다 — runs.models 를 import 하지 않는다(계약 나). 글·이름은 지은 것이다.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.apps import apps
from django.db import connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext

from esgapi.core.models import AuditEventRow
from esgapi.greenwash.contracts.review_shapes import REVIEW_SHAPES, SHAPE
from esgapi.greenwash.models import GreenwashReviewMarkRow, GreenwashReviewRow
from esgapi.greenwash.tests.service import seed
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair, login

pytestmark = pytest.mark.django_db

NORMAL = seed.example("result-normal")  # items 넷: High · Mid · Mid · Low
MANY = seed.example("result-many")  # items 서른여섯
ITEMS = NORMAL["items"]
UNKNOWN = "알 수 없는 사용자"
PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"
ADAPTER = REVIEW_SHAPES[SHAPE]
FIX = "기준연도와 목표연도를 함께 밝혀 주세요."
ONE: list[str] = ["고친 사유 한 줄."]


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


def user_id(company_id: int) -> int:
    """login 이 만든 고객사 사용자(토큰 sub edk-user-1)의 id."""
    return int(apps.get_model("user", "User").for_company(company_id).get(username="edk-user-1").pk)


def put(client: Client, run_id: int, body: dict[str, Any], **headers: Any) -> Any:
    return client.put(f"/api/greenwash/runs/{run_id}/review", data=body, content_type="application/json", **headers)


def get(client: Client, run_id: int, what: str = "review", **headers: Any) -> Any:
    return client.get(f"/api/greenwash/runs/{run_id}/{what}", **headers)


def mark(index: int, decision: str = "adopted", reason: str | None = None) -> dict[str, Any]:
    return {"itemIndex": index, "decision": decision, "excludeReason": reason}


def edit(
    index: int, level: str | None = None, bullets: list[str] | None = None, fix: str | None = None
) -> dict[str, Any]:
    return {"itemIndex": index, "level": level, "reasonBullets": bullets, "fixParagraph": fix}


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def rows(company_id: int, run_id: int) -> dict[int, tuple[Any, ...]]:
    """표시 표의 행 → (decision, 사유, 칸 셋 × 값·때·사람)."""
    found = GreenwashReviewMarkRow.for_company(company_id).filter(run_id=run_id).order_by("item_index")
    return {
        r.item_index: (
            r.decision,
            r.exclude_reason,
            r.edited_level,
            r.level_edited_at,
            r.level_edited_by_user_id,
            r.edited_reason_bullets,
            r.reasons_edited_at,
            r.reasons_edited_by_user_id,
            r.edited_fix_paragraph,
            r.fix_edited_at,
            r.fix_edited_by_user_id,
        )
        for r in found
    }


def review_lines(company_id: int) -> list[str]:
    return list(
        AuditEventRow.for_company(company_id)
        .filter(action__in=("adopt", "exclude", "confirm"))
        .order_by("id")
        .values_list("action", flat=True)
    )


@pytest.fixture
def done_run(client: Client, companies: tuple[int, int]) -> int:
    login(client)
    return seed.run(companies[0], result=NORMAL)


# ── 저장·정규화 ──


def test_an_edit_is_saved_and_the_response_is_the_get(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    a = companies[0]
    me = user_id(a)
    saved = put(client, done_run, {"marks": [], "edits": [edit(0, "Low", ONE, FIX)]})
    assert saved.status_code == 200, saved.content.decode()
    body = saved.json()
    ADAPTER.validate_python(body, strict=True)
    assert list(body) == [
        "schemaVersion",
        "runId",
        "state",
        "confirmedAt",
        "confirmedBy",
        "marks",
        "edits",
        "evidence",  # GRJ1(review@3)
        "rejudges",
    ]
    assert body["schemaVersion"] == "greenwash.review@3"
    assert (body["state"], body["marks"]) == ("in_review", [])  # 미검토 문장의 고침도 검토 활동
    (only,) = body["edits"]
    assert only["itemIndex"] == 0
    for key, value in (("level", "Low"), ("reasonBullets", ONE), ("fixParagraph", FIX)):
        assert only[key]["value"] == value
        assert only[key]["editedBy"] == {"id": me, "name": "김담당"}
        assert only[key]["editedAt"].endswith("+09:00")
    assert get(client, done_run).json() == body
    assert rows(a, done_run)[0][:3] == (None, None, "Low")  # 표시 없는 행(decision NULL)


def test_values_equal_to_the_ai_fold_to_no_edit(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """AI 와 같은 값만 보낸 PUT 은 고침 0 → 행 0·상태 그대로(정규화 뒤 판단 — 규칙 6). 앞뒤 공백도 지운 뒤 견준다."""
    a = companies[0]
    ai = ITEMS[1]
    same = edit(1, ai["level"], [f"  {b} " for b in ai["reasonBullets"]], f"\n{ai['fixParagraph']}  ")
    response = put(client, done_run, {"marks": [], "edits": [same]})
    assert response.status_code == 200, response.content.decode()
    assert (response.json()["state"], response.json()["edits"]) == ("pending", [])
    assert GreenwashReviewRow.for_company(a).count() == 0
    assert GreenwashReviewMarkRow.for_company(a).count() == 0
    # 분모: 한 칸만 달라도 그 칸만 고침
    other = put(client, done_run, {"marks": [], "edits": [{**same, "level": "High"}]}).json()
    assert other["state"] == "in_review"
    assert [(e["itemIndex"], e["level"]["value"], e["reasonBullets"], e["fixParagraph"]) for e in other["edits"]] == [
        (1, "High", None, None)
    ]


def test_bullets_and_fix_are_stripped_and_blank_bullets_dropped(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    a = companies[0]
    body = put(
        client, done_run, {"marks": [], "edits": [edit(2, None, ["  첫 줄 ", "", "   ", "둘째 줄"], "  고친 글 \n")]}
    )
    (only,) = body.json()["edits"]
    assert only["reasonBullets"]["value"] == ["첫 줄", "둘째 줄"]
    assert only["fixParagraph"]["value"] == "고친 글"
    assert only["level"] is None  # 칸별 null — 등급은 AI 그대로
    assert rows(a, done_run)[2][2:5] == (None, None, None)


# ── 갈아 넣기: marks 와 edits 는 서로의 칸을 안 건드린다 ──


def test_marks_and_edits_replace_only_their_own_columns(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    a = companies[0]
    first = put(client, done_run, {"marks": [mark(0), mark(1, "excluded", "근거 있음")], "edits": [edit(1, "Low")]})
    assert first.status_code == 200
    before = rows(a, done_run)
    # marks 만 바꾼 PUT(edits 생략) → 고침·때·사람 그대로
    marks_only = put(client, done_run, {"marks": [mark(0, "excluded", "다른 근거")]}).json()
    assert marks_only["edits"] == first.json()["edits"]
    after = rows(a, done_run)
    assert after[1][2:] == before[1][2:]
    assert after[1][:2] == (None, None)  # 보내지 않은 표시는 미검토(DELETE 없음), 고침은 남음
    # edits 만 바꾼 PUT → decision·사유 그대로
    edits_only = put(client, done_run, {"marks": [mark(0, "excluded", "다른 근거")], "edits": [edit(3, "High")]}).json()
    assert [e["itemIndex"] for e in edits_only["edits"]] == [3]
    assert rows(a, done_run)[0][:2] == ("excluded", "다른 근거")
    assert rows(a, done_run)[1][2:] == (None,) * 9  # 보내지 않은 문장의 고침 칸은 NULL(행은 남김)
    # edits [] → 고침을 다 지움, decision 그대로
    cleared = put(client, done_run, {"marks": [mark(0, "excluded", "다른 근거")], "edits": []}).json()
    assert cleared["edits"] == []
    assert cleared["marks"] == [mark(0, "excluded", "다른 근거")]
    assert all(value[2:] == (None,) * 9 for value in rows(a, done_run).values())
    assert cleared["state"] == "in_review"


def test_each_column_keeps_its_own_time_and_person(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """등급만 다시 고치면 사유 칸의 때·사람 그대로 · 같은 값 다시 보내면 editedAt 그대로 · null 로 돌리면 셋 다 NULL."""
    a = companies[0]
    put(client, done_run, {"marks": [], "edits": [edit(0, "Mid", ONE)]})
    first = rows(a, done_run)[0]
    again = put(client, done_run, {"marks": [], "edits": [edit(0, "Mid", ONE)]})
    assert again.status_code == 200
    assert rows(a, done_run)[0] == first  # 같은 값 → 칸 하나도 안 바뀜
    put(client, done_run, {"marks": [], "edits": [edit(0, "Low", ONE)]})
    after = rows(a, done_run)[0]
    assert after[2] == "Low" and after[3] > first[3]  # 등급의 때는 새로
    assert after[5:8] == first[5:8]  # 사유의 값·때·사람 그대로
    put(client, done_run, {"marks": [], "edits": [edit(0, None, ONE)]})
    assert rows(a, done_run)[0][2:5] == (None, None, None)
    assert rows(a, done_run)[0][5:8] == first[5:8]


# ── 잠금 ──


def test_edits_on_the_confirm_put_are_saved_then_locked(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    a = companies[0]
    confirmed = put(client, done_run, {"state": "confirmed", "marks": [], "edits": [edit(3, "Mid", None, FIX)]})
    assert confirmed.status_code == 200, confirmed.content.decode()
    body = confirmed.json()
    assert body["state"] == "confirmed"
    assert [(e["itemIndex"], e["level"]["value"], e["fixParagraph"]["value"]) for e in body["edits"]] == [
        (3, "Mid", FIX)
    ]
    before = rows(a, done_run)
    for late in (
        {"marks": [], "edits": [edit(0, "Low")]},
        {"marks": [], "edits": []},
        {"marks": [], "edits": [edit(9)]},
    ):
        assert code(put(client, done_run, late)) == (409, "REVIEW_LOCKED")
    assert rows(a, done_run) == before
    assert get(client, done_run).json() == body


# ── 400 ──


@pytest.mark.parametrize(
    ("edits", "message"),
    [
        ([edit(4, "Low")], "문장 번호 4은(는) 이 결과에 없어요(0부터 3까지)"),
        ([edit(1, "Low"), edit(1, None, ONE)], "고친 문장 번호 1이(가) 두 번 왔어요"),
        ([edit(0, None, ["", "  "])], "판정 사유는 한 줄 이상 있어야 해요"),
        ([edit(0, None, [])], "판정 사유는 한 줄 이상 있어야 해요"),
        ([edit(0, None, [f"줄 {n}" for n in range(11)])], "판정 사유는 10줄까지 쓸 수 있어요"),
        ([edit(0, None, ["가" * 501])], "판정 사유는 한 줄에 500자까지 쓸 수 있어요"),
        ([edit(0, None, None, "  \n ")], "수정 방향은 비워 둘 수 없어요"),
        ([edit(0, None, None, "가" * 2001)], "수정 방향은 2000자까지 쓸 수 있어요"),
    ],
    ids=["range", "twice", "blank-bullets", "no-bullets", "eleven-lines", "long-line", "blank-fix", "long-fix"],
)
def test_bad_edits_are_400_and_write_nothing(
    client: Client, companies: tuple[int, int], done_run: int, edits: list[dict[str, Any]], message: str
) -> None:
    a = companies[0]
    response = put(client, done_run, {"marks": [mark(3)], "edits": [edit(2, "High"), *edits]})
    assert code(response) == (400, "INVALID_REVIEW")
    assert response.json()["error"]["message"] == message
    assert GreenwashReviewRow.for_company(a).count() == 0
    assert GreenwashReviewMarkRow.for_company(a).count() == 0
    assert review_lines(a) == []
    # 분모: 상한 그대로는 받는다(10 줄 × 500자 · 2,000자)
    edge = edit(0, None, ["가" * 500] * 10, "가" * 2000)
    assert put(client, done_run, {"marks": [], "edits": [edge]}).status_code == 200


# ── 결과·감사·쿼리 ──


def test_the_result_body_is_the_same_before_and_after_edits(client: Client, done_run: int) -> None:
    before = get(client, done_run, "result").content
    put(client, done_run, {"marks": [], "edits": [edit(0, "Low", ONE, FIX)]})
    assert get(client, done_run, "result").content == before


def test_an_edit_only_put_writes_no_audit_line(client: Client, companies: tuple[int, int], done_run: int) -> None:
    a = companies[0]
    put(client, done_run, {"marks": [], "edits": [edit(0, "Low", ONE, FIX), edit(1, "High")]})
    put(client, done_run, {"marks": [], "edits": [edit(0, "Mid")]})
    assert review_lines(a) == []
    # 분모: 제외 하나를 더하면 exclude 한 줄
    put(client, done_run, {"marks": [mark(2, "excluded", "근거")], "edits": [edit(0, "Mid")]})
    assert review_lines(a) == ["exclude"]


def test_the_review_get_query_count_does_not_grow_with_edits(client: Client, companies: tuple[int, int]) -> None:
    """고친 사람 이름은 한 번에 푼다(N+1 없음). 고친 사람이 확정자·서로 달라도 이름 쿼리는 하나."""
    login(client)
    a = companies[0]
    run_id = seed.run(a, result=MANY)
    counted: list[int] = []
    for edits in ([edit(0, "Low")], [edit(i, None, [f"줄 {i}"]) for i in range(5)]):
        put(client, run_id, {"marks": [mark(0)], "edits": edits})
        GreenwashReviewMarkRow.for_company(a).filter(run_id=run_id, item_index=4).update(
            reasons_edited_by_user_id=424242  # 다른 사람 하나(못 푸는 id)
        )
        with CaptureQueriesContext(connection) as queries:
            assert len(get(client, run_id).json()["edits"]) == len(edits)
        counted.append(len(queries))
    assert counted[0] == counted[1], counted
    print(f"검토 GET 쿼리 = {counted[0]}(고친 문장 1·5)")


# ── 권한 둘 ──


def operator_headers(client: Client) -> tuple[int, dict[str, Any]]:
    created = create_operator(username="ops", name="운영자 한빛", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    first = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)
    changed = client.post(
        "/api/users/me/password",
        data={"currentPassword": PASSWORD, "newPassword": CHANGED},
        content_type="application/json",
        **bearer(first["access"]),
    )
    assert changed.status_code == 200, changed.content.decode()
    return created.user_id, bearer(str(changed.json()["access"]))


@pytest.fixture
def solo(db: None) -> int:
    """회사 하나(활성) — 운영 관리자의 작업 회사. 모델은 apps.get_model 로(계약 나 — 모듈끼리 models import 0)."""
    company = apps.get_model("organization", "Company")
    company.register(name="가 회사", business_licence_number="111-11-11111", subdomain="tenant-a")
    found = company.by_subdomain("tenant-a")
    assert found is not None
    return int(found.pk)


def test_an_operator_edits_and_confirms_in_the_work_company(solo: int) -> None:
    client = Client()
    admin, headers = operator_headers(client)
    run_id = seed.run(solo, result=NORMAL)
    saved = put(client, run_id, {"marks": [mark(1, "excluded", "근거")], "edits": [edit(0, "Low", ONE)]}, **headers)
    assert saved.status_code == 200, saved.content.decode()
    (only,) = saved.json()["edits"]
    assert only["level"]["editedBy"] == only["reasonBullets"]["editedBy"] == {"id": admin, "name": "운영자 한빛"}
    confirmed = put(client, run_id, {"state": "confirmed", "marks": [mark(1)]}, **headers).json()
    assert confirmed["confirmedBy"] == {"id": admin, "name": "운영자 한빛"}
    assert confirmed["edits"] == saved.json()["edits"]  # 확정은 고침을 건드리지 않는다
    adopt = AuditEventRow.for_company(solo).filter(action="adopt").values_list("actor_kind", "actor_user_id")
    assert list(adopt) == [("admin", admin)]


def test_an_operator_with_two_companies_is_400_and_writes_nothing(companies: tuple[int, int]) -> None:
    a, _ = companies
    client = Client()
    _admin, headers = operator_headers(client)
    run_id = seed.run(a, result=NORMAL)
    assert code(put(client, run_id, {"marks": [], "edits": [edit(0, "Low")]}, **headers)) == (400, "COMPANY_AMBIGUOUS")
    assert GreenwashReviewRow.unscoped.count() == 0
    assert GreenwashReviewMarkRow.unscoped.count() == 0


def test_an_editor_of_another_company_is_the_unknown_user(
    client: Client, companies: tuple[int, int], done_run: int
) -> None:
    """칸의 사람 id 가 남의 회사 고객사 사용자면 「알 수 없는 사용자」(people_of 는 그 회사 안만)."""
    a, b = companies
    stranger = create_customer_user(
        actor_kind="admin", company_id=b, username="b-kim", name="남의 김", password=PASSWORD
    )
    assert isinstance(stranger, UserCreated)
    put(client, done_run, {"marks": [], "edits": [edit(0, "Low", ONE)]})
    GreenwashReviewMarkRow.for_company(a).filter(run_id=done_run, item_index=0).update(
        level_edited_by_user_id=stranger.user_id
    )
    (only,) = get(client, done_run).json()["edits"]
    assert only["level"]["editedBy"] == {"id": stranger.user_id, "name": UNKNOWN}
    assert only["reasonBullets"]["editedBy"] == {"id": user_id(a), "name": "김담당"}  # 분모


def test_an_old_row_without_edits_reads_as_no_edit(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """고침 칸이 NULL 인 표시 행(@1 때의 행과 같은 꼴)은 edits [] 로 읽힌다."""
    a = companies[0]
    put(client, done_run, {"marks": [mark(0), mark(2, "excluded", "근거")]})
    assert get(client, done_run).json()["edits"] == []
    assert all(value[2:] == (None,) * 9 for value in rows(a, done_run).values())


def test_a_write_touches_only_my_companys_rows(client: Client, companies: tuple[int, int], done_run: int) -> None:
    """같은 run_id·itemIndex 에 남의 회사(B) 행이 있어도(손으로 심음 — run_id 는 외래 키가 아니다) A 의 PUT 은 INSERT·
    UPDATE(표시·고침)·지우기 어느 길에서도 B 의 행을 안 건드린다(services 의 for_company — 검증 1 B2)."""
    a, b = companies
    GreenwashReviewRow.for_company(b).create(company_id=b, run_id=done_run, state="in_review")
    GreenwashReviewMarkRow.for_company(b).create(
        company_id=b, run_id=done_run, item_index=0, decision="excluded", exclude_reason="B 의 사유"
    )
    theirs = rows(b, done_run)
    assert put(client, done_run, {"marks": [mark(0)], "edits": [edit(0, "Low", ONE)]}).status_code == 200  # INSERT
    changed = {"marks": [mark(0, "excluded", "A 의 사유")], "edits": [edit(0, "High", None, FIX)]}
    assert put(client, done_run, changed).status_code == 200  # 행 있음 → UPDATE
    assert put(client, done_run, {"marks": [], "edits": []}).status_code == 200  # 지우기 = NULL 로 UPDATE
    assert rows(b, done_run) == theirs
    assert rows(a, done_run)[0][:3] == (None, None, None)  # 분모: A 의 행은 바뀌었다
