# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportArgumentType=false
"""그린워싱 AI 설정 판의 대상 단어 저장(밴드 G2d §3-1 — POST /ai-settings/greenwash 의 terms, 판 꼴 @3, PUT …/applied
의 단어 다시 받기). 업무 층: 진짜 DB(주인 역할 — 앱 역할의 칸 권한은 보안 층 tests/security/test_ai_settings.py).

    3-1-1  공백 둘린 단어 → 201, 칸 strip·차례 그대로 · 판 @3 strict 왕복 · 기본 판 terms null · 꼴 틀림 422
    3-1-2  한 번 저장 = 판 하나 — 넷 다 맞음 행 1 · 단어만 틀림 400·행 0·감사 0 · 프롬프트와 단어 둘 다 틀림 → 프롬프트
    3-1-3  거절 넷 code + fields 경로(500 아님) · 분모 100개 201 · 최악 크기 둘 201(octet_length < CHECK)
    3-1-4  같은 목록(기본 목록)은 칸 값 그대로(NULL 로 접지 않음) · 단어만 다른 새 판 · 감사 changed_fields 다섯
    3-1-5  저장 뒤 받기를 좁히면 적용 409(쓰기·감사 0), 기본 판 되돌리기 200

낱말·이름·메모는 지어낸 것이다(synthetic). 실제 AI 호출 0.
"""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.test import Client, override_settings

from esgapi.core.models import AuditEventRow
from esgapi.greenwash.contracts.ai_setting_shapes import DEFAULT_SHAPES, SETTING_SHAPE, SETTING_SHAPES
from esgapi.greenwash.engines.e0.gw1 import GREEN_TERMS
from esgapi.greenwash.engines.e0.prompts import default_prompts
from esgapi.greenwash.flows import colab_e0, terms_e0
from esgapi.greenwash.flows.criteria_e0 import default_criteria
from esgapi.greenwash.models import AI_SETTING_TERMS_MAX_OCTETS, GreenwashAiSettingRow
from esgapi.user.service.services.user import create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair

pytestmark = pytest.mark.django_db

PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"
ROOT = "/api/ai-settings/greenwash"
TITLE = "지어낸 판 이름"
FIELDS = colab_e0.PROMPT_FIELDS


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


@pytest.fixture
def ops(client: Client) -> dict[str, str]:
    created = create_operator(username="ops", name="가상 운영자", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    first = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)
    changed = client.post(
        "/api/users/me/password",
        data={"currentPassword": PASSWORD, "newPassword": CHANGED},
        content_type="application/json",
        **bearer(first["access"]),
    )
    assert changed.status_code == 200, changed.content.decode()
    return bearer(str(changed.json()["access"]))


def terms(*texts: str, off: tuple[int, ...] = ()) -> list[dict[str, Any]]:
    return [{"text": t, "enabled": i not in off} for i, t in enumerate(texts)]


GOOD = terms("초록마루", "친환경", "녹색", off=(1,))


def post(client: Client, headers: dict[str, str], company_id: int, body: dict[str, Any]) -> Any:
    data = json.dumps({"title": TITLE, **body})
    return client.post(f"{ROOT}?companyId={company_id}", data=data, content_type="application/json", **headers)


def put(client: Client, headers: dict[str, str], company_id: int, setting_id: int | None) -> Any:
    return client.put(
        f"{ROOT}/applied?companyId={company_id}", data={"id": setting_id}, content_type="application/json", **headers
    )


def error(response: Any) -> tuple[int, str, Any]:
    body = response.json()["error"]
    return response.status_code, body["code"], body["fields"]


def rows(company_id: int) -> int:
    return GreenwashAiSettingRow.for_company(company_id).count()


def lines(company_id: int) -> list[tuple[Any, ...]]:
    found = AuditEventRow.for_company(company_id).filter(action="setting_change").order_by("id")
    return [(r.event, r.target_id, r.detail) for r in found]


def row(setting_id: int, company_id: int) -> GreenwashAiSettingRow:
    return GreenwashAiSettingRow.for_company(company_id).get(id=setting_id)


def octets(setting_id: int) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT octet_length(terms::text) FROM greenwash_ai_settings WHERE id = %s", [setting_id])
        (found,) = cursor.fetchone() or (None,)
    assert isinstance(found, int)
    return found


def prompts(texts: dict[str, str]) -> dict[str, Any]:
    return {"steps": [{"key": "judge", "prompts": [{"key": k, "text": texts[k], "memo": ""} for k in FIELDS]}]}


# ── 3-1-1 저장·꼴 ──


def test_terms_are_stored_stripped_in_order_and_shown_at_3(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    a, _ = companies
    saved = post(client, ops, a, {"terms": terms("  초록마루 ", "친환경\t", " 녹색", off=(1,))})
    assert saved.status_code == 201, saved.content.decode()
    body = saved.json()
    assert body["schemaVersion"] == SETTING_SHAPE == "greenwash.ai-setting@3"
    assert body["terms"] == GOOD
    SETTING_SHAPES[SETTING_SHAPE].validate_python(body, strict=True)
    assert row(body["id"], a).terms == GOOD
    got = client.get(f"{ROOT}/{body['id']}?companyId={a}", **ops)
    assert got.status_code == 200 and got.json() == body  # 판 하나 읽기 = 저장 응답(왕복)
    default = client.get(f"{ROOT}/default", **ops).json()
    assert default["schemaVersion"] == "greenwash.ai-setting-default@3" and default["terms"] is None
    (adapter,) = DEFAULT_SHAPES.values()
    adapter.validate_python(default, strict=True)


@pytest.mark.parametrize(
    "given",
    [
        pytest.param([{"text": "친환경", "enabled": 1}], id="enabled-int"),
        pytest.param([{"text": "친환경", "enabled": "true"}], id="enabled-string"),
        pytest.param("친환경", id="string"),
        pytest.param([{"text": "친환경"}], id="enabled-missing"),
        pytest.param([{"text": "친환경", "enabled": True, "more": 1}], id="unknown-key"),
        pytest.param([{"text": "가" * 201, "enabled": True}], id="201-chars"),
        pytest.param([{"text": f"낱말{i}", "enabled": True} for i in range(1001)], id="1001-terms"),
    ],
)
def test_a_wrong_shape_is_422(client: Client, companies: tuple[int, int], ops: dict[str, str], given: Any) -> None:
    a, _ = companies
    status, code, _fields = error(post(client, ops, a, {"terms": given}))
    assert (status, code) == (422, "VALIDATION_ERROR")
    assert (rows(a), lines(a)) == (0, [])


@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_null_terms_mean_the_code_list(
    client: Client, companies: tuple[int, int], ops: dict[str, str], missing: bool
) -> None:
    a, _ = companies
    saved = post(client, ops, a, {} if missing else {"terms": None})
    assert saved.status_code == 201 and saved.json()["terms"] is None
    assert row(saved.json()["id"], a).terms is None


# ── 3-1-2 한 번 저장 = 판 하나 ──


def _bad_criteria() -> dict[str, Any]:
    criteria: dict[str, Any] = json.loads(json.dumps(default_criteria()))
    criteria["rows"][9]["text"] = ""
    return criteria


def _code_texts() -> dict[str, str]:
    found = default_prompts(colab_e0.judged_prompt_version(dict(colab_e0.SCAN_CONFIG)))
    return {key: getattr(found, field) for key, field in FIELDS.items()}


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        pytest.param({"terms"}, "TERMS_TEXT", id="terms"),
        pytest.param({"prompts", "terms"}, "AI_PROMPT_TEXT_EMPTY", id="prompts-before-terms"),
        pytest.param({"criteria", "terms"}, "CRITERIA_TEXT_LENGTH", id="criteria-before-terms"),
    ],
)
def test_one_refusal_writes_nothing(
    client: Client, companies: tuple[int, int], ops: dict[str, str], body: set[str], expected: str
) -> None:
    a, _ = companies
    texts = _code_texts()
    good = {"criteria": default_criteria(), "prompts": prompts(texts), "terms": GOOD}
    bad = {"criteria": _bad_criteria(), "prompts": prompts({**texts, "repair": "   "}), "terms": terms("(괄호)")}
    refused = post(client, ops, a, {**good, **{k: bad[k] for k in body}})
    assert error(refused)[:2] == (400, expected), refused.content.decode()
    assert (rows(a), lines(a)) == (0, [])
    assert post(client, ops, a, good).status_code == 201  # 분모: 넷 다 맞으면 행 1
    assert rows(a) == 1


# ── 3-1-3 거절 넷·크기 ──


REFUSALS = [
    ("empty", terms("친환경", ""), "TERMS_TEXT", "terms.1.text"),
    ("31", terms("친환경", "가" * 31), "TERMS_TEXT", "terms.1.text"),
    ("bracket", terms("녹색(가상)"), "TERMS_TEXT", "terms.0.text"),
    ("quote", terms("친환경", '"녹색"'), "TERMS_TEXT", "terms.1.text"),
    ("dot", terms("."), "TERMS_TEXT", "terms.0.text"),
    ("dash", terms("친환경", "-"), "TERMS_TEXT", "terms.1.text"),
    ("nul", terms("녹\x00색"), "TERMS_TEXT", "terms.0.text"),
    ("bell", terms("녹\u0007색"), "TERMS_TEXT", "terms.0.text"),
    ("zero-width", terms("친환경", "녹​색"), "TERMS_TEXT", "terms.1.text"),
    ("duplicate", terms("친환경", "탄소 중립", "탄소중립"), "TERMS_DUPLICATE", "terms.2.text"),
    ("count", terms(*(f"지어낸낱말{i}" for i in range(101)), off=tuple(range(60, 101))), "TERMS_COUNT", "terms"),
    ("none-enabled", terms("친환경", "녹색", off=(0, 1)), "TERMS_NONE_ENABLED", "terms"),
]


def _body(given: list[dict[str, Any]]) -> str:
    """짝 없는 서로게이트는 json.dumps 가 \\ud800 으로 쓴다(그대로 보낸다 — 서버가 받아 푼다)."""
    return json.dumps({"title": TITLE, "terms": given})


@pytest.mark.parametrize(("given", "expected", "field"), [pytest.param(g, c, f, id=n) for n, g, c, f in REFUSALS])
def test_a_refused_term_is_400_with_the_field_path(
    client: Client, companies: tuple[int, int], ops: dict[str, str], given: Any, expected: str, field: str
) -> None:
    a, _ = companies
    response = client.post(f"{ROOT}?companyId={a}", data=_body(given), content_type="application/json", **ops)
    status, found, fields = error(response)
    assert (status, found) == (400, expected), response.content.decode()
    assert list(fields) == [field] and len(fields[field]) == 1
    assert (rows(a), lines(a)) == (0, [])


def test_a_lone_surrogate_is_422_at_the_shape_not_500(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    """짝 없는 서로게이트(JSON 의 \\ud800)는 본문 꼴(pydantic str)이 먼저 422 로 막는다 — 받기의 TERMS_TEXT 는 저장 칸을
    다시 받을 때의 그물(tests/flows/test_terms_e0.py 의 lone-surrogate). 500 은 아니다."""
    a, _ = companies
    given = terms("친환경", "녹\ud800색")
    response = client.post(f"{ROOT}?companyId={a}", data=_body(given), content_type="application/json", **ops)
    status, found, fields = error(response)
    assert (status, found, list(fields)) == (422, "VALIDATION_ERROR", ["terms.1.text"])
    assert (rows(a), lines(a)) == (0, [])


def test_a_hundred_terms_are_fine(client: Client, companies: tuple[int, int], ops: dict[str, str]) -> None:
    a, _ = companies
    given = terms(*(f"지어낸낱말{i}" for i in range(100)), off=tuple(range(60, 100)))
    saved = post(client, ops, a, {"terms": given})
    assert saved.status_code == 201 and len(saved.json()["terms"]) == 100


WORST = {
    # 글자 하나 + `\` 29자 — jsonb 글은 `\` 마다 두 바이트(이스케이프), 키가 서로 다른 100개(N4)
    "backslash": [{"text": chr(0xAC00 + i) + "\\" * 29, "enabled": False} for i in range(99)]
    + [{"text": "가가" + "\\" * 28, "enabled": True}],
    # CJK 확장 B(Lo, 4바이트) 30자, 키가 서로 다른 100개
    "four-byte": [{"text": chr(0x20000 + i) * 30, "enabled": i == 0} for i in range(100)],
}


@pytest.mark.parametrize("case", sorted(WORST))
def test_the_worst_sizes_pass_the_rule_and_stay_under_the_check(
    client: Client, companies: tuple[int, int], ops: dict[str, str], case: str
) -> None:
    a, _ = companies
    saved = post(client, ops, a, {"terms": WORST[case]})
    assert saved.status_code == 201, saved.content.decode()
    found = octets(saved.json()["id"])
    print(f"G2D_WORST_OCTETS {case}={found}")  # 보고의 K6 실측(-s 로 본다)
    assert found < AI_SETTING_TERMS_MAX_OCTETS


# ── 3-1-4 접지 않음·새 판·감사 ──


def test_the_default_list_is_kept_as_a_value_and_a_terms_only_change_is_a_new_version(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    a, _ = companies
    same = terms(*GREEN_TERMS)
    v1 = post(client, ops, a, {"terms": same}).json()
    assert v1["terms"] == same and row(v1["id"], a).terms == same  # NULL 로 접지 않는다
    v2 = post(client, ops, a, {"terms": terms(*GREEN_TERMS, off=(0,))}).json()
    assert (v1["name"], v2["name"]) == ("v1", "v2")
    assert v1["evalPromptSha256"] == v2["evalPromptSha256"]  # 판정 프롬프트는 그대로 — 단어만 다른 새 판
    assert lines(a) == [
        (
            "ai_setting_created",
            v["id"],
            {"changed_fields": ["criteria", "memo", "model_settings", "prompts", "terms"], "module": "greenwash"},
        )
        for v in (v1, v2)
    ]


# ── 3-1-5 저장 뒤 받기를 좁힘 ──


def test_saved_terms_the_rules_no_longer_take_are_unusable(
    client: Client, companies: tuple[int, int], ops: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    v1 = post(client, ops, a, {"terms": GOOD}).json()["id"]
    before = lines(a)
    monkeypatch.setattr(terms_e0, "TERM_CHARS", 3)  # 「초록마루」 4자가 이제 거절된다
    assert error(put(client, ops, a, v1))[:2] == (409, "AI_SETTING_UNUSABLE")
    assert (row(v1, a).applied, lines(a)) == (False, before)  # 쓰기·감사 0
    assert put(client, ops, a, None).status_code == 200  # 기본 판으로는 늘 된다
    monkeypatch.undo()
    assert put(client, ops, a, v1).status_code == 200  # 분모: 받기가 그대로면 적용된다
