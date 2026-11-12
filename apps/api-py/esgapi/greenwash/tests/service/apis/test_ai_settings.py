# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false, reportArgumentType=false
"""그린워싱 AI 설정 판의 경로 다섯(밴드 G2c2 ② — /ai-settings/greenwash, 운영 관리자). 업무 층: 진짜 DB(주인 역할 —
앱 역할의 경계·격리는 보안 층 tests/security/test_ai_settings.py).

    저장 → v1·v2(201, 꼴 strict) · 목록(새 것 먼저·적용 판·기본 판) · 한 판 · 기본 판 · 적용 v1 → 같은 판 다시 → 기본
    감사 setting_change(저장·적용, 같은 판 다시·거절은 줄 0, AuditRefused 여도 응답 그대로)
    거절: 받기 400 CRITERIA_* · 메모 201자·모르는 칸·숫자 아닌 id 422 · 없는 판·남의 판 404(같은 몸) · 회사 고르기
    고객사 사용자 403(몸 앞 — 판 읽기 0)
    적용 경로의 SQL 에서 기준표 칸을 싣는 문은 고른 판 한 행 읽기 하나(밴드 G2c3 §3-1-4)
    받기 규칙이 좁아져 못 받는 판의 적용 409 AI_SETTING_UNUSABLE·쓰기·감사 0, 기본 판으로 되돌리기 200(G2c3 §3-2-2)

기준 글·메모·이름은 지어낸 것이다(synthetic).
"""

import copy
from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext

from esgapi.core.models import AuditEventRow
from esgapi.core.service.services.audit import AuditRefused
from esgapi.greenwash.contracts.ai_setting_shapes import DEFAULT_SHAPES, DEFAULT_TITLE, LIST_SHAPES, SETTING_SHAPES
from esgapi.greenwash.flows import colab_e0, criteria_e0
from esgapi.greenwash.flows.criteria_e0 import DEFAULT_VERSION, default_criteria
from esgapi.greenwash.models import GreenwashAiSettingRow
from esgapi.greenwash.service.actions import ai_settings as actions
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair

pytestmark = pytest.mark.django_db

PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"
ROOT = "/api/ai-settings/greenwash"
LIST_ADAPTER = next(iter(LIST_SHAPES.values()))
SETTING_ADAPTER = next(iter(SETTING_SHAPES.values()))
DEFAULT_ADAPTER = next(iter(DEFAULT_SHAPES.values()))


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


def changed_access(client: Client, *, username: str, subdomain: str | None) -> str:
    """로그인하고 비밀번호를 한 번 바꿔(is_initial 끔) 새 access."""
    first = bearer_pair(client, username=username, password=PASSWORD, company_subdomain=subdomain)
    changed = client.post(
        "/api/users/me/password",
        data={"currentPassword": PASSWORD, "newPassword": CHANGED},
        content_type="application/json",
        **bearer(first["access"]),
    )
    assert changed.status_code == 200, changed.content.decode()
    return str(changed.json()["access"])


@pytest.fixture
def ops(client: Client) -> tuple[int, dict[str, str]]:
    created = create_operator(username="ops", name="가상 운영자", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    return created.user_id, bearer(changed_access(client, username="ops", subdomain=None))


def edited(text: str = "지어낸 기준 글: 근거 없이 쓴 환경 성과 주장") -> dict[str, Any]:
    criteria: dict[str, Any] = copy.deepcopy(dict(default_criteria()))
    criteria["version"] = "draft-from-web"
    criteria["rows"][9]["text"] = text
    return criteria


def post(client: Client, headers: dict[str, str], company_id: int | None, body: dict[str, Any]) -> Any:
    query = "" if company_id is None else f"?companyId={company_id}"
    return client.post(
        ROOT + query, data={"title": "지어낸 판 이름", **body}, content_type="application/json", **headers
    )


def put(client: Client, headers: dict[str, str], company_id: int, setting_id: int | None) -> Any:
    return client.put(
        f"{ROOT}/applied?companyId={company_id}", data={"id": setting_id}, content_type="application/json", **headers
    )


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def lines(company_id: int) -> list[tuple[Any, ...]]:
    rows = AuditEventRow.for_company(company_id).filter(action="setting_change").order_by("id")
    return [
        (r.actor_kind, r.actor_user_id, r.event, r.result, r.target_kind, r.target_id, r.target_label, r.detail)
        for r in rows
    ]


# ── 저장·목록·한 판·기본 판 ──


def test_save_list_get_and_default(client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]) -> None:
    a, _ = companies
    who, headers = ops
    first = post(client, headers, a, {"criteria": edited(), "memo": "첫 판(지어낸 메모)"})
    assert first.status_code == 201, first.content.decode()
    body = first.json()
    SETTING_ADAPTER.validate_python(body, strict=True)
    assert (body["name"], body["status"], body["memo"], body["createdBy"]) == (
        "v1",
        "testing",
        "첫 판(지어낸 메모)",
        {"id": who, "name": "가상 운영자"},
    )
    assert body["criteria"]["version"] == "v1"
    assert body["evalPromptSha256"] == colab_e0.run_versions(body["criteria"])["evalPromptSha256"]
    assert body["createdAt"].endswith("+09:00")
    second = post(client, headers, a, {"criteria": edited("지어낸 둘째 글")})
    assert (second.status_code, second.json()["name"], second.json()["memo"]) == (201, "v2", "")

    listed = client.get(f"{ROOT}?companyId={a}", **headers)
    assert listed.status_code == 200
    page = listed.json()
    LIST_ADAPTER.validate_python(page, strict=True)
    assert (page["companyId"], page["applied"], page["total"]) == (a, {"kind": "default"}, 2)
    assert [item["name"] for item in page["items"]] == ["v2", "v1"]
    assert page["default"] == {
        "name": DEFAULT_VERSION,
        "title": DEFAULT_TITLE,
        "evalPromptSha256": colab_e0.run_versions(None)["evalPromptSha256"],
    }
    cut = client.get(f"{ROOT}?companyId={a}&limit=1&offset=1", **headers).json()
    assert ([item["name"] for item in cut["items"]], cut["total"]) == (["v1"], 2)

    one = client.get(f"{ROOT}/{body['id']}?companyId={a}", **headers)
    assert (one.status_code, one.json()) == (200, body)

    default = client.get(f"{ROOT}/default", **headers)
    assert default.status_code == 200
    DEFAULT_ADAPTER.validate_python(default.json(), strict=True)
    assert (default.json()["name"], default.json()["criteria"]) == (DEFAULT_VERSION, default_criteria())


def test_the_save_and_apply_audit_lines(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, b = companies
    who, headers = ops
    v1 = post(client, headers, a, {"criteria": edited()}).json()["id"]
    assert lines(a) == [
        (
            "admin",
            who,
            "ai_setting_created",
            "success",
            "ai_setting",
            v1,
            "v1",
            {"changed_fields": ["criteria", "memo", "model_settings", "prompts", "terms"], "module": "greenwash"},
        )
    ]
    applied = put(client, headers, a, v1)
    assert applied.status_code == 200
    LIST_ADAPTER.validate_python(applied.json(), strict=True)
    assert applied.json()["applied"] == {"kind": "saved", "id": v1}
    assert applied.json()["items"][0]["status"] == "applied"
    assert put(client, headers, a, v1).status_code == 200  # 같은 판 다시 — 줄 0
    back = put(client, headers, a, None)
    assert (back.status_code, back.json()["applied"], back.json()["items"][0]["status"]) == (
        200,
        {"kind": "default"},
        "past",
    )
    assert [line[2:] for line in lines(a)[1:]] == [
        (
            "ai_setting_applied",
            "success",
            "ai_setting",
            v1,
            "v1",
            {"changed_fields": ["applied"], "module": "greenwash"},
        ),
        (
            "ai_setting_applied",
            "success",
            "ai_setting",
            None,
            DEFAULT_VERSION,
            {"changed_fields": ["applied"], "module": "greenwash"},
        ),
    ]
    assert lines(b) == []  # 다른 회사의 줄 0


def test_a_refused_audit_line_still_saves(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    _, headers = ops
    monkeypatch.setattr(actions, "record_event", lambda **kwargs: AuditRefused("db_error"))
    saved = post(client, headers, a, {"criteria": edited()})
    assert saved.status_code == 201
    assert put(client, headers, a, saved.json()["id"]).json()["applied"] == {"kind": "saved", "id": saved.json()["id"]}
    assert lines(a) == []


def test_a_name_conflict_past_the_retries_is_409(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    from esgapi.greenwash.service.selectors import ai_settings as selectors

    a, _ = companies
    _, headers = ops
    assert post(client, headers, a, {"criteria": edited()}).status_code == 201
    monkeypatch.setattr(selectors, "setting_names", lambda company_id: ())  # 늘 v1 을 센다 — 다시 시도를 다 쓴다
    assert code(post(client, headers, a, {"criteria": edited()})) == (409, "NAME_CONFLICT")
    assert GreenwashAiSettingRow.for_company(a).count() == 1
    assert len(lines(a)) == 1  # 감사도 첫 저장 하나뿐


def test_the_apply_path_never_reads_the_criteria(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    """G2c3 §3-1-4: 적용 한 번(잠금·바꾸기·목록 첫 쪽)에서 기준표 칸을 싣는 문은 고른 판 한 행의 받기 검사 하나다
    (MARC-ISSUE-229 — 목록·잠금은 싣지 않는다)."""
    a, _ = companies
    _, headers = ops
    v1 = post(client, headers, a, {"criteria": edited()}).json()["id"]
    post(client, headers, a, {"criteria": edited("지어낸 둘째 글")})
    with CaptureQueriesContext(connection) as queries:
        response = put(client, headers, a, v1)
    assert response.status_code == 200, response.content.decode()
    sqls = [q["sql"] for q in queries.captured_queries]
    assert [q for q in sqls if "FOR UPDATE" in q and "greenwash_ai_settings" in q]  # 분모: 잠금이 잡혔다
    loaded = [q for q in sqls if '"criteria"' in q]
    assert len(loaded) == 1 and "FOR UPDATE" not in loaded[0], loaded
    assert f'"id" = {v1}' in loaded[0]  # 그 id 한 행


def test_a_version_the_rules_no_longer_take_cannot_be_applied(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """G2c3 §3-2-2: 받기 규칙이 좁아지면 그 판의 적용은 409(쓰기·감사 0), 기본 판으로 되돌리기는 된다(출구)."""
    a, _ = companies
    _, headers = ops
    text = "지어낸 기준 글: 좁히면 받지 못할 만큼 조금 긴 글"
    v1 = post(client, headers, a, {"criteria": edited(text)}).json()["id"]
    v2 = post(client, headers, a, {"criteria": edited("지어낸 짧은 글")}).json()["id"]
    assert put(client, headers, a, v1).status_code == 200  # 분모: 좁히기 전엔 적용된다
    before = lines(a)
    monkeypatch.setattr(criteria_e0, "TEXT_CHARS", max(len(r["text"]) for r in edited(text)["rows"]) - 1)
    for target in (v2, v1):  # 새로 적용하려는 판·이미 적용된 그 판을 다시 — 둘 다 못 받는다
        refused = put(client, headers, a, target)
        assert code(refused) == (409, "AI_SETTING_UNUSABLE"), target
        message = refused.json()["error"]["message"]
        # 글 전문을 박는다 — 판 이름 하나뿐이고 회사 id·기준 글은 없다
        # (조각 검사는 회사 id 가 한 자리면 「(v1)」 에 걸린다)
        name = "v1" if target == v1 else "v2"
        assert message == f"AI 설정 판({name})이 지금 규칙에 맞지 않아 적용할 수 없어요. 판을 다시 저장해 적용해 주세요"
    applied = list(GreenwashAiSettingRow.for_company(a).order_by("id").values_list("id", "applied"))
    assert applied == [(v1, True), (v2, False)]  # 그대로
    assert lines(a) == before  # 감사 0
    back = put(client, headers, a, None)
    assert (back.status_code, back.json()["applied"]) == (200, {"kind": "default"})


# ── 거절 ──


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        pytest.param(lambda c: c.update(rows=c["rows"][:14]), (400, "CRITERIA_ROWS_FIXED"), id="fourteen-rows"),
        pytest.param(lambda c: c["rows"][9].update(text="가" * 301), (400, "CRITERIA_TEXT_LENGTH"), id="long-text"),
        pytest.param(lambda c: c["rows"][0].update(terms=[]), (400, "CRITERIA_TERMS_COUNT"), id="no-terms"),
        pytest.param(lambda c: c["rows"][0].update(extra=1), (422, "VALIDATION_ERROR"), id="unknown-row-key"),
        pytest.param(lambda c: c["rows"][0].update(order="1"), (422, "VALIDATION_ERROR"), id="order-text"),
    ],
)
def test_a_refused_criteria_writes_nothing(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], edit: Any, expected: tuple[int, str]
) -> None:
    a, _ = companies
    _, headers = ops
    criteria = edited()
    edit(criteria)
    refused = post(client, headers, a, {"criteria": criteria})
    assert code(refused) == expected, refused.content.decode()
    assert GreenwashAiSettingRow.for_company(a).count() == 0
    assert lines(a) == []


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"memo": "가" * 201}, id="memo-201"),
        pytest.param({"companyId": 1}, id="company-in-body"),
        pytest.param({"createdByUserId": 1}, id="user-in-body"),
        pytest.param({"memo": 3}, id="memo-number"),
    ],
)
def test_a_bad_save_body_is_422(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], body: dict[str, Any]
) -> None:
    a, _ = companies
    _, headers = ops
    assert code(post(client, headers, a, {"criteria": edited(), **body})) == (422, "VALIDATION_ERROR")
    assert GreenwashAiSettingRow.for_company(a).count() == 0
    assert post(client, headers, a, {"criteria": edited(), "memo": "가" * 200}).status_code == 201  # 분모: 200자는 됨


@pytest.mark.parametrize("memo", [pytest.param("메\x00모", id="nul"), pytest.param("메\ud800모", id="lone-surrogate")])
def test_a_bad_character_in_the_memo_is_422(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], memo: str
) -> None:
    """메모의 NUL·짝 없는 서로게이트는 판 이름과 같은 422 fields.memo(GWB1 — NUL 은 Postgres DataError 500 이었음)."""
    a, _ = companies
    _, headers = ops
    refused = post(client, headers, a, {"criteria": edited(), "memo": memo})
    assert (*code(refused), list(refused.json()["error"]["fields"])) == (422, "VALIDATION_ERROR", ["memo"])
    assert GreenwashAiSettingRow.for_company(a).count() == 0
    assert lines(a) == []


def _guideline(c: dict[str, Any], text: str) -> None:
    c["rows"][9]["guideline"] = {"text": text, "status": "draft"}


@pytest.mark.parametrize("bad", [pytest.param("\x00", id="nul"), pytest.param("\ud800", id="lone-surrogate")])
@pytest.mark.parametrize(
    "put_in",
    [
        pytest.param(lambda c, bad: c["rows"][9].update(text=f"지어낸{bad}기준 글"), id="row-text"),
        pytest.param(lambda c, bad: c["rows"][0].update(terms=[f"지어낸{bad}낱말"]), id="keyword-term"),
        pytest.param(lambda c, bad: _guideline(c, f"지어낸{bad}지침"), id="guideline"),
    ],
)
def test_a_bad_character_in_the_criteria_is_400_not_500(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], put_in: Any, bad: str
) -> None:
    """기준표 글의 NUL·짝 없는 서로게이트는 받기(criteria_e0 의 한 줄 검사)가 400 으로 막는다 — 500·쓰기 0(GWB1)."""
    a, _ = companies
    _, headers = ops
    criteria = edited()
    put_in(criteria, bad)
    refused = post(client, headers, a, {"criteria": criteria})
    assert code(refused) == (400, "CRITERIA_TEXT_MULTILINE"), refused.content.decode()
    assert GreenwashAiSettingRow.for_company(a).count() == 0
    assert lines(a) == []


@pytest.mark.parametrize(
    "body", [pytest.param({}, id="no-id"), pytest.param({"id": True}, id="bool"), pytest.param({"id": "1"}, id="text")]
)
def test_a_bad_apply_body_is_422(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], body: dict[str, Any]
) -> None:
    a, _ = companies
    _, headers = ops
    sent = client.put(f"{ROOT}/applied?companyId={a}", data=body, content_type="application/json", **headers)
    assert code(sent) == (422, "VALIDATION_ERROR")


def test_missing_and_foreign_versions_are_the_same_404(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, b = companies
    _, headers = ops
    theirs = post(client, headers, b, {"criteria": edited()}).json()["id"]
    missing = theirs + 1000
    got_theirs = client.get(f"{ROOT}/{theirs}?companyId={a}", **headers)
    got_missing = client.get(f"{ROOT}/{missing}?companyId={a}", **headers)
    assert code(got_theirs) == (404, "NOT_FOUND")
    assert got_theirs.content == got_missing.content
    put_theirs, put_missing = put(client, headers, a, theirs), put(client, headers, a, missing)
    assert code(put_theirs) == (404, "NOT_FOUND")
    assert put_theirs.content == put_missing.content
    assert list(GreenwashAiSettingRow.for_company(b).values_list("applied", flat=True)) == [False]
    assert lines(a) == []
    assert client.get(f"{ROOT}/{theirs}?companyId={b}", **headers).status_code == 200  # 분모: 제 회사로는 보인다


def test_a_non_numeric_id_is_422(client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]) -> None:
    a, _ = companies
    _, headers = ops
    assert code(client.get(f"{ROOT}/abc?companyId={a}", **headers)) == (422, "VALIDATION_ERROR")


def test_the_company_is_chosen_like_the_other_operator_paths(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, b = companies
    _, headers = ops
    assert code(client.get(ROOT, **headers)) == (400, "COMPANY_AMBIGUOUS")  # 회사 둘
    assert code(client.get(f"{ROOT}?companyId={a + b + 1000}", **headers)) == (404, "COMPANY_NOT_FOUND")
    assert code(post(client, headers, None, {"criteria": edited()})) == (400, "COMPANY_AMBIGUOUS")
    assert GreenwashAiSettingRow.for_company(a).count() == GreenwashAiSettingRow.for_company(b).count() == 0


def test_a_customer_is_403_before_any_read(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    created = create_customer_user(actor_kind="admin", company_id=a, username="kim", name="김담당", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    headers = bearer(changed_access(client, username="kim", subdomain="tenant-a"))
    sent = {
        "list": lambda: client.get(f"{ROOT}?companyId={a}", **headers),
        "default": lambda: client.get(f"{ROOT}/default", **headers),
        "get": lambda: client.get(f"{ROOT}/1?companyId={a}", **headers),
        "create": lambda: post(client, headers, a, {"criteria": edited()}),
        "apply": lambda: put(client, headers, a, None),
    }
    for name, send in sent.items():
        with CaptureQueriesContext(connection) as queries:
            response = send()
        assert code(response) == (403, "FORBIDDEN"), name
        assert not [q for q in queries.captured_queries if "greenwash_ai_settings" in q["sql"]], name
        assert not [q for q in queries.captured_queries if "company" in q["sql"].lower()], name
    assert GreenwashAiSettingRow.for_company(a).count() == 0
