"""그린워싱 AI 설정 판(G2c2 — /ai-settings/greenwash, 운영 관리자)의 경계를 앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 고객사 사용자 Bearer 는 다섯 다 403 이고 판 행 0·몸에 판 0(분모: 운영 관리자의 같은 요청은 200·201)
  ⓑ 운영 관리자가 companyId=B 로 A 의 판 id 를 GET·적용 → 404, 없는 id 와 바이트 같음, 행·감사 0 변화
     (분모: 같은 함수에서 companyId=A 로 그 판 200)
  ⓒ companyId=B 의 목록에 A 의 판 0(분모: companyId=A 로 ≥1)
  ⓓ 앱 역할의 칸 권한: applied·applied_at 밖 칸 UPDATE·DELETE 는 DB 가 거절(42501 — 원문), applied UPDATE 는 됨
  ⓔ is_initial 운영 관리자 → 다섯 다 403 PASSWORD_CHANGE_REQUIRED
  ⓕ 본문의 회사·사용자 칸 → 422(저장·적용)
  ⓖ 앱 역할로 저장 → 적용 → 기본으로 되돌리기 한 바퀴가 된다(적용이 칸 권한 안 — save() 로 바꾸면 여기서 빨강)
  (401 은 tests/security/test_tenant_paths.py 의 test_without_a_session_it_is_401 매개 다섯이 잰다)

Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다(행을 심고 분모를 센다).
★ 뒤 밴드는 함수를 더하기만 한다(이 파일의 기존 함수의 단언을 바꾸지 않는다). 기준 글은 지어낸 것이다.
"""

import copy
import json
from typing import Any

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction
from django.test import Client

from esgapi.greenwash.flows.criteria_e0 import default_criteria
from tests.security.test_audit import customer_access, operator_access
from tests.security.test_login import PASSWORD, operator, try_login
from tests.support.http import bearer

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
ROOT = "/api/ai-settings/greenwash"
TABLE = "greenwash_ai_settings"


def edited(text: str = "지어낸 기준 글: 근거 없이 쓴 환경 성과 주장") -> dict[str, Any]:
    criteria: dict[str, Any] = copy.deepcopy(dict(default_criteria()))
    criteria["rows"][9]["text"] = text
    return criteria


def calls(client: Client, access: str, company_id: int, setting_id: int) -> dict[str, Any]:
    """다섯을 한 번씩 보낸다(저장은 고친 기준표, 적용은 setting_id)."""
    headers = bearer(access)
    return {
        "list": client.get(f"{ROOT}?companyId={company_id}", **headers),
        "default": client.get(f"{ROOT}/default", **headers),
        "get": client.get(f"{ROOT}/{setting_id}?companyId={company_id}", **headers),
        "create": client.post(
            f"{ROOT}?companyId={company_id}",
            data={"criteria": edited(), "title": "x"},
            content_type="application/json",
            **headers,
        ),
        "apply": client.put(
            f"{ROOT}/applied?companyId={company_id}",
            data={"id": setting_id},
            content_type="application/json",
            **headers,
        ),
    }


def save(client: Client, access: str, company_id: int, text: str = "지어낸 기준 글") -> int:
    response = client.post(
        f"{ROOT}?companyId={company_id}",
        data={"criteria": edited(text), "title": "x"},
        content_type="application/json",
        **bearer(access),
    )
    assert response.status_code == 201, response.content.decode()
    return int(response.json()["id"])


def rows(owner: Owner, company_id: int | None = None) -> list[tuple[Any, ...]]:
    where, args = ("", []) if company_id is None else (" WHERE company_id = %s", [company_id])
    return owner.execute(f"SELECT id, company_id, name, applied FROM {TABLE}{where} ORDER BY id", args).fetchall()


def setting_audit(owner: Owner) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT company_id, event, target_id FROM core_audit_events "
        "WHERE action = 'setting_change' AND target_kind = 'ai_setting' ORDER BY id"
    ).fetchall()


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def test_a_customer_bearer_is_refused_on_all_five(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓐ 다섯 다 403 FORBIDDEN, 판 행 0·몸에 판 0. 분모: 운영 관리자의 같은 요청은 200·201."""
    a, _ = companies
    access = customer_access(client, a)
    for name, response in calls(client, access, a, 1).items():
        assert code(response) == (403, "FORBIDDEN"), name
        assert {"items", "criteria", "applied", "total"} & set(response.json()) == set(), name
    assert rows(owner) == []
    ops = operator_access(Client())
    mine = save(Client(), ops, a)
    seen = {name: response.status_code for name, response in calls(Client(), ops, a, mine).items()}
    assert seen == {"list": 200, "default": 200, "get": 200, "create": 201, "apply": 200}


def test_another_companys_version_is_the_same_404(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓑ companyId=B 로 A 의 판을 GET·적용 → 404, 없는 id 와 바이트 같음, 행·감사 0 변화. 분모: A 로는 200."""
    a, b = companies
    ops = operator_access(client)
    theirs = save(client, ops, a)
    save(client, ops, b, "B 의 지어낸 글")
    before_rows, before_audit = rows(owner), setting_audit(owner)
    missing = theirs + 1000
    headers = bearer(ops)
    got = client.get(f"{ROOT}/{theirs}?companyId={b}", **headers)
    got_missing = client.get(f"{ROOT}/{missing}?companyId={b}", **headers)
    assert code(got) == (404, "NOT_FOUND")
    assert got.content == got_missing.content

    def apply(setting_id: int) -> Any:
        return client.put(
            f"{ROOT}/applied?companyId={b}", data={"id": setting_id}, content_type="application/json", **headers
        )

    applied, applied_missing = apply(theirs), apply(missing)
    assert code(applied) == (404, "NOT_FOUND")
    assert applied.content == applied_missing.content
    assert (rows(owner), setting_audit(owner)) == (before_rows, before_audit)
    assert client.get(f"{ROOT}/{theirs}?companyId={a}", **headers).status_code == 200  # 분모


def test_the_list_of_b_has_no_version_of_a(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓒ companyId=B 의 목록에 A 의 판 0. 분모: companyId=A 로 ≥1."""
    a, b = companies
    ops = operator_access(client)
    mine = {save(client, ops, a), save(client, ops, a, "둘째")}
    headers = bearer(ops)
    of_b = client.get(f"{ROOT}?companyId={b}", **headers).json()
    assert (of_b["total"], of_b["items"], of_b["companyId"]) == (0, [], b)
    of_a = client.get(f"{ROOT}?companyId={a}", **headers).json()
    assert {item["id"] for item in of_a["items"]} == mine
    assert of_a["total"] >= 1


def denied(statement: str) -> tuple[str | None, str]:
    """앱 역할로 문 하나를 보내고 (SQLSTATE, DB 의 원문 첫 줄). 된 것이면 (None, "")."""
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(statement)
    except DatabaseError as error:
        return getattr(error.__cause__, "sqlstate", None), str(error.__cause__).splitlines()[0]
    return None, ""


@pytest.mark.parametrize(
    "assignment",
    [
        "criteria = '{}'::jsonb",
        "name = 'v9'",
        "memo = '고친 메모'",
        "eval_prompt_sha256 = repeat('b', 64)",
        "created_by_user_id = 1",
        "updated_at = now()",
        "company_id = company_id",
        "model_settings = '{}'::jsonb",  # AS2b: 모델 설정 칸도 불변
        "prompts = '[]'::jsonb",  # AS3a-2: 프롬프트 글·판 이름 칸도 불변
        "title = 'x'",
        "terms = '[]'::jsonb",  # G2d: 대상 단어 칸도 불변
    ],
)
def test_app_role_cannot_rewrite_a_version(owner: Owner, companies: tuple[int, int], assignment: str) -> None:
    """ⓓ applied·applied_at 밖 칸의 UPDATE 는 DB 가 거절한다(42501 permission denied). 분모: applied 는 된다."""
    a, _ = companies
    owner.execute(
        f"INSERT INTO {TABLE} (created_at, updated_at, company_id, name, criteria, model_settings, eval_prompt_sha256, "
        "memo, created_by_user_id, applied) VALUES (now(), now(), %s, 'v1', '{}'::jsonb, '{}', %s, '', 1, false)",
        [a, "a" * 64],
    )
    state, message = denied(f"UPDATE {TABLE} SET {assignment} WHERE company_id = {a}")
    assert state == "42501", message
    assert message == f"permission denied for table {TABLE}"
    assert denied(f"UPDATE {TABLE} SET applied = true, applied_at = now() WHERE company_id = {a}") == (None, "")
    assert denied(f"DELETE FROM {TABLE} WHERE company_id = {a}")[0] == "42501"
    assert rows(owner, a) == [(rows(owner, a)[0][0], a, "v1", True)]


def test_an_initial_operator_is_refused_on_all_five(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓔ is_initial 운영 관리자(비밀번호를 안 바꿈)는 다섯 다 403 PASSWORD_CHANGE_REQUIRED."""
    a, _ = companies
    operator()
    first = try_login(client, "ops", PASSWORD, None)
    assert first.status_code == 200 and first.json()["isInitial"] is True
    for name, response in calls(client, first.json()["access"], a, 1).items():
        assert code(response) == (403, "PASSWORD_CHANGE_REQUIRED"), name
    assert rows(owner) == []


@pytest.mark.parametrize("field", ["companyId", "company_id", "createdByUserId", "userId"])
def test_a_body_with_a_company_or_user_field_is_422(
    client: Client, owner: Owner, companies: tuple[int, int], field: str
) -> None:
    """ⓕ 본문에 회사·사용자 칸을 실으면 꼴에서 거절(422) — 행 0. 대상 회사는 쿼리 companyId 하나다."""
    a, b = companies
    headers = bearer(operator_access(client))
    made = client.post(
        f"{ROOT}?companyId={a}", data={"criteria": edited(), field: b}, content_type="application/json", **headers
    )
    applied = client.put(
        f"{ROOT}/applied?companyId={a}", data={"id": None, field: b}, content_type="application/json", **headers
    )
    assert code(made) == code(applied) == (422, "VALIDATION_ERROR")
    assert rows(owner) == []


def test_the_app_role_saves_applies_and_goes_back(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓖ 앱 역할로 저장 → 적용 → 다른 판 적용 → 기본으로 한 바퀴. 감사 줄 다섯(저장 둘·적용 셋 — 같은 판 다시는 0)."""
    a, _ = companies
    access = operator_access(client)
    headers = bearer(access)
    v1, v2 = save(client, access, a), save(client, access, a, "둘째")

    def apply(setting_id: int | None) -> Any:
        return client.put(
            f"{ROOT}/applied?companyId={a}", data={"id": setting_id}, content_type="application/json", **headers
        )

    assert apply(v1).json()["applied"] == {"kind": "saved", "id": v1}
    assert apply(v1).status_code == 200  # 같은 판 다시
    assert apply(v2).json()["applied"] == {"kind": "saved", "id": v2}
    back = apply(None).json()
    assert back["applied"] == {"kind": "default"}
    assert [item["status"] for item in back["items"]] == ["past", "past"]
    assert [row[3] for row in rows(owner, a)] == [False, False]
    assert [event for _, event, _ in setting_audit(owner)] == [
        "ai_setting_created",
        "ai_setting_created",
        "ai_setting_applied",
        "ai_setting_applied",
        "ai_setting_applied",
    ]


def test_the_prompt_model_reads_keep_the_same_boundary(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """AS2a: 프롬프트·모델 읽기 둘(/default/prompt-model·/{id}/prompt-model). 고객사 Bearer 둘 다 403 FORBIDDEN(몸에
    단계 0) · is_initial 운영 관리자 둘 다 403 PASSWORD_CHANGE_REQUIRED · companyId=A 로 B 의 판 id → 404, 없는 id 와
    바이트 같고 몸에 B 판의 기준 글 0. 분모: 운영 관리자 companyId=B 로 그 판 200 이고 eval 글에 B 판의 글이 있다."""
    a, b = companies
    marker = "B 판에만 쓴 지어낸 기준 글"

    def both(access: str, company_id: int, setting_id: int) -> dict[str, Any]:
        headers = bearer(access)
        return {
            "default": client.get(f"{ROOT}/default/prompt-model", **headers),
            "one": client.get(f"{ROOT}/{setting_id}/prompt-model?companyId={company_id}", **headers),
        }

    for name, response in both(customer_access(client, a), a, 1).items():
        assert code(response) == (403, "FORBIDDEN"), name
        assert {"models", "promptGroups", "settingName"} & set(response.json()) == set(), name
    assert rows(owner) == []

    operator("ops-initial")
    first = try_login(Client(), "ops-initial", PASSWORD, None)
    assert first.status_code == 200 and first.json()["isInitial"] is True
    for name, response in both(first.json()["access"], a, 1).items():
        assert code(response) == (403, "PASSWORD_CHANGE_REQUIRED"), name

    ops = operator_access(Client())
    theirs = save(Client(), ops, b, marker)
    got = both(ops, a, theirs)["one"]
    missing = both(ops, a, theirs + 1000)["one"]
    assert code(got) == (404, "NOT_FOUND")
    assert got.content == missing.content
    assert marker not in json.dumps(got.json(), ensure_ascii=False)
    of_b = both(ops, b, theirs)
    assert {name: response.status_code for name, response in of_b.items()} == {"default": 200, "one": 200}  # 분모
    assert marker in of_b["one"].json()["promptGroups"][0]["prompts"][1]["text"]
