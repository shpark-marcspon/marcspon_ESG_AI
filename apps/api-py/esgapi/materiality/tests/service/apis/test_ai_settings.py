# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false, reportArgumentType=false
"""중대성평가 IRO AI 설정 판의 경로 일곱(밴드 IR4 §3-3-2~4 — /ai-settings/materiality, 운영 관리자). 업무 층:
진짜 DB(주인 역할 — 앱 역할의 경계·격리는 보안 층 tests/security/test_materiality_ai_settings.py).

    저장      칸 열넷 + 칸 둘 → 201(꼴 strict)·글 바이트 그대로·메모 strip · prompt-model 이 저장 값 · 고친 칸만
              isDefault false·출력절 고친 칸만 outputKept false · 기본 글 같은 글 접지 않음 ·
              modelSettings 생략 → 기본값
    목록      새 것 먼저·적용 판·기본 판 · 한 판 · 기본 판 · 기본 판 prompt-model · 적용 v1 → 기본
    감사      setting_change(저장·적용 — module materiality, 거절·같은 판 다시는 줄 0)
    거절      프롬프트 여덟 400 AI_PROMPT_*·fields·행 0·감사 0 · 입력 글 자리 하나씩 400 AI_PROMPT_PLACEHOLDER_MISSING
              (날 글 칸 × 자리 전부 + 규제 지시 글) · 지시 글 통째 바꿈 201 · 모델 400 AI_MODEL_*
              (research temperature null·2.5 · analysis temperature 값 · light-openai-41 · webSearch 뒤집음 ·
              위끝 40,000) · title 넷 422 · 남의 회사 판 404(같은 몸) · 받기를 좁힘 → 409 ·
              고객사 403(몸 앞 — 판 읽기 0) · companyId 없이 회사 둘 → 400 · 같은 회사 번호 경합 소진 → 409
    옛 판     칸 열일곱 행(ORM) → prompt-model 200 칸 열넷·적용 200 · 열일곱 저장 400 AI_PROMPT_KEYS_FIXED(IRA3)
    TRP1      메모 NUL·외톨이 대리 글자 → 422(제목과 같은 꼴) · 잠금 뒤 겹친 적용 → 409 AI_SETTING_APPLY_CONFLICT
              (옛 적용 판 그대로·감사 0, 옛 판 있음·없음) · 다른 IntegrityError 는 그대로 올라감

글·메모·이름은 지어낸 것이다(synthetic).
"""

import dataclasses
from collections.abc import Iterator, Sequence
from typing import Any

import pytest
from django.db import IntegrityError, connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.core.calc.ai_settings import AiModelSlotSpec, PromptRefused, defaults, to_input
from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_V3, AiPromptsIn
from esgapi.core.models import AuditEventRow
from esgapi.materiality.contracts.ai_setting_shapes import (
    DEFAULT_NAME,
    DEFAULT_SHAPES,
    DEFAULT_TITLE,
    LIST_SHAPES,
    SETTING_SHAPES,
)
from esgapi.materiality.engines.colab_155 import texts
from esgapi.materiality.engines.colab_155.texts import DEFAULT_TEXTS
from esgapi.materiality.flows import prompt_model_155 as pm
from esgapi.materiality.models import MaterialityAiSettingRow
from esgapi.materiality.service.selectors import ai_settings as selectors
from esgapi.materiality.service.services import ai_settings as services_module
from esgapi.materiality.tests.flows.test_prompt_model_155 import (
    CONFIG,
    LEGACY,
    REQUIRED_CASES,
    legacy_body,
    model_body,
    position,
    prompts_body,
)
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair

pytestmark = pytest.mark.django_db

PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"
ROOT = "/api/ai-settings/materiality"
LIST_ADAPTER = next(iter(LIST_SHAPES.values()))
SETTING_ADAPTER = next(iter(SETTING_SHAPES.values()))
DEFAULT_ADAPTER = next(iter(DEFAULT_SHAPES.values()))
STANDARD = "standard-openai-4o"
LIGHT = "light-openai-41"
SLOTS = model_body(temperature=0.3, cap=8000, analysis_cap=9000)


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
    return [(r.event, r.result, r.target_kind, r.target_id, r.target_label, r.detail) for r in rows]


def entries(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["key"]: p for group in body["promptGroups"] for p in group["prompts"]}


# ── 저장·보기 ──


def test_a_full_save_is_kept_and_shown(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, _ = companies
    who, headers = ops
    marks = {
        key: f"⟦IR4-{key}⟧ 지어낸 글\r\n" + "".join(texts.REQUIRED.get(key, ()))
        for _, keys in pm.LAYOUT
        for key in keys
    }
    body = prompts_body(**marks)
    body["steps"][0]["prompts"][1]["memo"] = "  지어낸 메모  "
    saved = post(client, headers, a, {"modelSettings": SLOTS, "prompts": body, "memo": " 첫 판 "})
    assert saved.status_code == 201, saved.content.decode()
    one = saved.json()
    SETTING_ADAPTER.validate_python(one, strict=True)
    assert (one["name"], one["title"], one["status"], one["memo"], one["createdBy"]) == (
        "v1",
        "지어낸 판 이름",
        "testing",
        " 첫 판 ",
        {"id": who, "name": "가상 운영자"},
    )
    row = MaterialityAiSettingRow.for_company(a).get(id=one["id"])
    stored: Any = row.prompts
    assert [p["text"] for step in stored["steps"] for p in step["prompts"]] == list(marks.values())  # 바이트 그대로
    assert stored["steps"][0]["prompts"][1]["memo"] == "지어낸 메모"  # strip
    shown = client.get(f"{ROOT}/{one['id']}/prompt-model?companyId={a}", **headers)
    assert shown.status_code == 200, shown.content.decode()
    view = shown.json()
    PROMPT_MODEL_V3.validate_python(view, strict=True)
    assert view["settingName"] == "v1"
    assert [
        (s["key"], s["model"]["route"], s["model"]["maxOutputTokens"], s["model"]["temperature"])
        for s in view["models"]
    ] == [("research", STANDARD, 8000, 0.3), ("analysis", "standard-openai-41", 9000, None)]
    assert {key: e["text"] for key, e in entries(view).items()} == marks
    assert not [key for key, e in entries(view).items() if e["isDefault"]]
    assert {key for key, e in entries(view).items() if not e["outputKept"]} == set(pm.OUTPUT_MARKS)
    assert entries(view)["regulation_prefix"]["memo"] == "지어낸 메모"  # 저장 판의 칸 메모(strip 뒤)


def test_only_the_changed_texts_are_marked(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, _ = companies
    _, headers = ops
    kept = DEFAULT_TEXTS.impact_system.replace("You are", "You (지어낸 고침) are", 1)
    broken = DEFAULT_TEXTS.pathway_system.replace("[FINAL OUTPUT — JSON ONLY]", "[결과 꼴]")
    saved = post(client, headers, a, {"prompts": prompts_body(impact_system=kept, pathway_system=broken)})
    assert saved.status_code == 201, saved.content.decode()
    view = client.get(f"{ROOT}/{saved.json()['id']}/prompt-model?companyId={a}", **headers).json()
    found = entries(view)
    assert sorted(key for key, e in found.items() if not e["isDefault"]) == ["impact_system", "pathway_system"]
    assert [key for key, e in found.items() if not e["outputKept"]] == ["pathway_system"]


def test_the_default_texts_are_not_folded(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, _ = companies
    _, headers = ops
    saved = post(client, headers, a, {"prompts": prompts_body()})
    assert saved.status_code == 201
    assert MaterialityAiSettingRow.for_company(a).get(id=saved.json()["id"]).prompts == prompts_body()
    view = client.get(f"{ROOT}/{saved.json()['id']}/prompt-model?companyId={a}", **headers).json()
    assert all(e["isDefault"] for e in entries(view).values())


def test_an_omitted_model_is_the_default(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, _ = companies
    _, headers = ops
    saved = post(client, headers, a, {})
    assert saved.status_code == 201
    row = MaterialityAiSettingRow.for_company(a).get(id=saved.json()["id"])
    assert (row.model_settings, row.prompts) == (to_input(defaults(CONFIG, pm.MODELS)), None)
    view = client.get(f"{ROOT}/{row.id}/prompt-model?companyId={a}", **headers).json()
    default = client.get(f"{ROOT}/default/prompt-model", **headers).json()
    assert view["modelSettingsSha256"] == default["modelSettingsSha256"]
    assert view["promptGroups"] == default["promptGroups"]


def test_list_get_default_and_apply(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, b = companies
    _, headers = ops
    v1 = post(client, headers, a, {"memo": "하나"}).json()
    v2 = post(client, headers, a, {"memo": "둘"}).json()
    assert post(client, headers, b, {}).status_code == 201
    listed = client.get(f"{ROOT}?companyId={a}", **headers).json()
    LIST_ADAPTER.validate_python(listed, strict=True)
    assert (listed["companyId"], listed["applied"], listed["default"], listed["total"]) == (
        a,
        {"kind": "default"},
        {"name": DEFAULT_NAME, "title": DEFAULT_TITLE},
        2,
    )
    assert [item["name"] for item in listed["items"]] == ["v2", "v1"]
    got = client.get(f"{ROOT}/{v1['id']}?companyId={a}", **headers).json()
    assert got == v1
    default = client.get(f"{ROOT}/default", **headers).json()
    DEFAULT_ADAPTER.validate_python(default, strict=True)
    assert default == {
        "schemaVersion": "materiality.ai-setting-default@1",
        "name": DEFAULT_NAME,
        "title": DEFAULT_TITLE,
    }
    default_model = client.get(f"{ROOT}/default/prompt-model", **headers).json()
    PROMPT_MODEL_V3.validate_python(default_model, strict=True)
    assert default_model["settingName"] == DEFAULT_NAME

    applied = put(client, headers, a, v1["id"])
    assert applied.status_code == 200, applied.content.decode()
    assert applied.json()["applied"] == {"kind": "saved", "id": v1["id"]}
    assert put(client, headers, a, v1["id"]).status_code == 200  # 같은 판 다시 — 감사 0
    assert put(client, headers, a, None).json()["applied"] == {"kind": "default"}
    statuses = {i["name"]: i["status"] for i in client.get(f"{ROOT}?companyId={a}", **headers).json()["items"]}
    assert statuses == {"v1": "past", "v2": "testing"}
    created = {"changed_fields": ["memo", "model_settings", "prompts"], "module": "materiality"}
    applied_detail = {"changed_fields": ["applied"], "module": "materiality"}
    assert lines(a) == [
        ("ai_setting_created", "success", "ai_setting", v1["id"], "v1", created),
        ("ai_setting_created", "success", "ai_setting", v2["id"], "v2", created),
        ("ai_setting_applied", "success", "ai_setting", v1["id"], "v1", applied_detail),
        ("ai_setting_applied", "success", "ai_setting", None, DEFAULT_NAME, applied_detail),
    ]


# ── 거절 ──


def _long_texts() -> AiPromptsIn:
    """글 열일곱이 다 8,000자(국문·서로 다름 — 날 글 칸은 자리 글자를 품음)·메모가 다 500자(국문) — 정규형이 131,072
    바이트를 넘는다."""
    keys = [k for _, ks in pm.LAYOUT for k in ks]
    body = prompts_body(
        **{
            key: "".join(texts.REQUIRED.get(key, ()))
            + chr(0xAC00 + i) * (8000 - len("".join(texts.REQUIRED.get(key, ()))))
            for i, key in enumerate(keys)
        }
    )
    for step in body["steps"]:
        for prompt in step["prompts"]:
            prompt["memo"] = "가" * 500
    return body


def _with(edit: Any) -> AiPromptsIn:
    body = prompts_body()
    edit(body)
    return body


PROMPT_REFUSALS = [
    pytest.param(_with(lambda b: b["steps"].pop()), "AI_PROMPT_STEPS_FIXED", "prompts.steps", id="steps"),
    pytest.param(
        _with(lambda b: b["steps"][0]["prompts"].reverse()),
        "AI_PROMPT_KEYS_FIXED",
        "prompts.steps.0.prompts",
        id="keys",
    ),
    pytest.param(
        prompts_body(keywords_system=" \n "), "AI_PROMPT_TEXT_EMPTY", "prompts.steps.1.prompts.0.text", id="empty"
    ),
    pytest.param(
        prompts_body(regulation_prefix=pm.default_text("regulation_system")),
        "AI_PROMPT_TEXT_DUPLICATE",
        "prompts.steps.0.prompts.1.text",
        id="duplicate",
    ),
    pytest.param(
        prompts_body(impact_system="가" * 9000), "AI_PROMPT_TEXT_LENGTH", "prompts.steps.2.prompts.0.text", id="9000"
    ),
    pytest.param(
        prompts_body(regulation_system="지어낸\x00글"), "AI_PROMPT_CHARS", "prompts.steps.0.prompts.0.text", id="nul"
    ),
    pytest.param(
        _with(lambda b: b["steps"][2]["prompts"][0].update(memo="가" * 501)),
        "AI_PROMPT_MEMO_LENGTH",
        "prompts.steps.2.prompts.0.memo",
        id="memo",
    ),
    pytest.param(_long_texts(), "AI_PROMPT_TOTAL_SIZE", "prompts", id="total"),
]


@pytest.mark.parametrize(("body", "expected", "field"), PROMPT_REFUSALS)
def test_a_refused_prompt_writes_nothing(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], body: Any, expected: str, field: str
) -> None:
    a, _ = companies
    _, headers = ops
    response = post(client, headers, a, {"prompts": body})
    assert code(response) == (400, expected), response.content.decode()
    assert list(response.json()["error"]["fields"]) == [field]
    assert MaterialityAiSettingRow.for_company(a).count() == 0
    assert lines(a) == []


MODEL_REFUSALS = [
    pytest.param(model_body(temperature=None), "AI_MODEL_TEMPERATURE_RANGE", id="temperature-null"),
    pytest.param(model_body(temperature=2.5), "AI_MODEL_TEMPERATURE_RANGE", id="temperature-2.5"),
    pytest.param(model_body(route=LIGHT), "AI_MODEL_ROUTE_UNKNOWN", id="light"),
    pytest.param(model_body(web_search=False), "AI_MODEL_WEB_SEARCH_FIXED", id="web-search-off"),
    pytest.param(model_body(cap=40000), "AI_MODEL_MAX_OUTPUT_RANGE", id="cap-40000"),
    pytest.param(model_body(analysis_temperature=0.3), "AI_MODEL_TEMPERATURE_UNSUPPORTED", id="analysis-temperature"),
]


@pytest.mark.parametrize(("model", "expected"), MODEL_REFUSALS)
def test_a_refused_model_writes_nothing(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], model: Any, expected: str
) -> None:
    a, _ = companies
    _, headers = ops
    assert code(post(client, headers, a, {"modelSettings": model, "prompts": prompts_body()})) == (400, expected)
    assert MaterialityAiSettingRow.for_company(a).count() == 0
    assert lines(a) == []


@pytest.mark.parametrize(("key", "slot"), REQUIRED_CASES)
def test_a_guarded_text_without_a_slot_is_400(
    client: Client,
    companies: tuple[int, int],
    ops: tuple[int, dict[str, str]],
    key: str,
    slot: str,
) -> None:
    a, _ = companies
    _, headers = ops
    body = prompts_body(**{key: pm.default_text(key).replace(slot, "(지운 자리)")})
    response = post(client, headers, a, {"prompts": body})
    assert code(response) == (400, "AI_PROMPT_PLACEHOLDER_MISSING"), response.content.decode()
    assert response.json()["error"]["fields"] == {
        "prompts.steps.{}.prompts.{}.text".format(*position(key)): [
            f"{pm.LABELS[key]}에서 {slot} 자리를 지우면 안 돼요"
        ]
    }
    assert MaterialityAiSettingRow.for_company(a).count() == 0
    assert lines(a) == []


def test_a_system_text_without_the_step_slots_is_201(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, _ = companies
    _, headers = ops
    text = "⟦지어낸 지시 글 — 자리 없음⟧"
    assert post(client, headers, a, {"prompts": prompts_body(keywords_system=text)}).status_code == 201


def test_the_step_of_a_refused_slot_is_its_key() -> None:
    found = pm.accept_model(CONFIG, model_body(temperature=None))
    assert getattr(found, "step", None) == "research"
    found = pm.accept_model(CONFIG, model_body(analysis_temperature=0.3))
    assert (getattr(found, "code", None), getattr(found, "step", None)) == (
        "ai_model_temperature_unsupported",
        "analysis",
    )


@pytest.mark.parametrize(
    "title",
    [
        pytest.param(None, id="missing"),
        pytest.param("   ", id="blank"),
        pytest.param("가" * 41, id="41"),
        pytest.param("지어낸\x00", id="nul"),
    ],
)
def test_a_bad_title_is_422(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], title: str | None
) -> None:
    a, _ = companies
    _, headers = ops
    body: dict[str, Any] = {} if title is None else {"title": title}
    response = client.post(f"{ROOT}?companyId={a}", data=body, content_type="application/json", **headers)
    assert code(response) == (422, "VALIDATION_ERROR")
    assert "title" in response.json()["error"]["fields"]
    assert MaterialityAiSettingRow.for_company(a).count() == 0


def test_another_companys_version_is_the_same_404(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, b = companies
    _, headers = ops
    theirs = post(client, headers, b, {}).json()["id"]
    missing = theirs + 1000
    for setting_id in (theirs, missing):
        got = client.get(f"{ROOT}/{setting_id}?companyId={a}", **headers)
        model = client.get(f"{ROOT}/{setting_id}/prompt-model?companyId={a}", **headers)
        applied = put(client, headers, a, setting_id)
        assert code(got) == code(model) == code(applied) == (404, "NOT_FOUND")
    first = client.get(f"{ROOT}/{theirs}?companyId={a}", **headers).json()
    assert first == client.get(f"{ROOT}/{missing}?companyId={a}", **headers).json()  # 같은 몸
    assert client.get(f"{ROOT}?companyId={a}", **headers).json()["items"] == []


def narrowed(self: object) -> Sequence[AiModelSlotSpec]:
    return tuple(dataclasses.replace(slot, routes=(LIGHT,)) for slot in pm.MODELS)


def test_a_version_the_rules_no_longer_take_is_409(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    _, headers = ops
    saved = post(client, headers, a, {"modelSettings": model_body(temperature=0.3)}).json()
    monkeypatch.setattr(selectors.RunModelSource, "steps", narrowed)
    assert code(put(client, headers, a, saved["id"])) == (409, "AI_SETTING_UNUSABLE")
    assert code(client.get(f"{ROOT}/{saved['id']}/prompt-model?companyId={a}", **headers)) == (
        409,
        "AI_SETTING_UNUSABLE",
    )
    assert client.get(f"{ROOT}/{saved['id']}?companyId={a}", **headers).status_code == 200  # 판 상세는 그대로
    assert put(client, headers, a, None).status_code == 200  # 기본 판으로 되돌리기는 된다
    assert not MaterialityAiSettingRow.for_company(a).filter(applied=True).exists()
    assert [line[0] for line in lines(a)] == ["ai_setting_created"]


def test_a_saved_text_the_narrowed_rules_refuse_is_409(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """저장 글도 다시 받는다(TR4 ③ 검증 B1): 글 상한을 10자로 좁히면 적용·prompt-model 둘 다 409."""
    a, _ = companies
    _, headers = ops
    saved = post(
        client, headers, a, {"prompts": prompts_body(keywords_system="지어낸 키워드 지침 — 열 글자보다 길다")}
    ).json()
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)
    assert code(put(client, headers, a, saved["id"])) == (409, "AI_SETTING_UNUSABLE")
    assert code(client.get(f"{ROOT}/{saved['id']}/prompt-model?companyId={a}", **headers)) == (
        409,
        "AI_SETTING_UNUSABLE",
    )
    assert not MaterialityAiSettingRow.for_company(a).filter(applied=True).exists()


def test_the_company_is_chosen_like_the_other_operator_paths(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, b = companies
    _, headers = ops
    assert code(client.get(ROOT, **headers)) == (400, "COMPANY_AMBIGUOUS")  # 회사 둘
    assert code(client.get(f"{ROOT}?companyId={a + b + 1000}", **headers)) == (404, "COMPANY_NOT_FOUND")
    assert code(post(client, headers, None, {})) == (400, "COMPANY_AMBIGUOUS")
    assert MaterialityAiSettingRow.for_company(a).count() == MaterialityAiSettingRow.for_company(b).count() == 0


def test_a_customer_is_403_before_any_read(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    created = create_customer_user(actor_kind="admin", company_id=a, username="kim", name="김담당", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    headers = bearer(changed_access(client, username="kim", subdomain="tenant-a"))
    sent = {
        "list": lambda: client.get(f"{ROOT}?companyId={a}", **headers),
        "default": lambda: client.get(f"{ROOT}/default", **headers),
        "default-prompt-model": lambda: client.get(f"{ROOT}/default/prompt-model", **headers),
        "get": lambda: client.get(f"{ROOT}/1?companyId={a}", **headers),
        "prompt-model": lambda: client.get(f"{ROOT}/1/prompt-model?companyId={a}", **headers),
        "create": lambda: post(client, headers, a, {}),
        "apply": lambda: put(client, headers, a, None),
    }
    for name, send in sent.items():
        with CaptureQueriesContext(connection) as queries:
            response = send()
        assert code(response) == (403, "FORBIDDEN"), name
        assert not [q for q in queries.captured_queries if "materiality_ai_settings" in q["sql"]], name
        assert not [q for q in queries.captured_queries if "company" in q["sql"].lower()], name
    assert MaterialityAiSettingRow.for_company(a).count() == 0


def test_a_name_conflict_past_the_retries_is_409(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    _, headers = ops
    assert post(client, headers, a, {}).status_code == 201
    monkeypatch.setattr(selectors, "setting_names", lambda company_id: ())  # 늘 v1 을 센다
    assert code(post(client, headers, a, {})) == (409, "NAME_CONFLICT")
    assert MaterialityAiSettingRow.for_company(a).count() == 1
    assert len(lines(a)) == 1


# ── 메모 글자·적용 경쟁(밴드 TRP1 S1·S2) ──


@pytest.mark.parametrize(
    "memo", [pytest.param("지어낸\x00메모", id="nul"), pytest.param("지어낸\ud800메모", id="lone-surrogate")]
)
def test_a_bad_memo_is_422_like_the_title(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]], memo: str
) -> None:
    a, _ = companies
    _, headers = ops
    response = post(client, headers, a, {"memo": memo})
    assert code(response) == (422, "VALIDATION_ERROR")
    assert "memo" in response.json()["error"]["fields"]
    assert MaterialityAiSettingRow.for_company(a).count() == 0
    assert lines(a) == []


def _racing_rows(monkeypatch: pytest.MonkeyPatch, company_id: int) -> None:
    """잠금(lock_settings) 뒤 적용 판을 올리기 직전에, 잠금이 못 본 적용 행 하나가 생긴다(겹친 적용의 흉내)."""
    real = MaterialityAiSettingRow

    class Filtered:
        def __init__(self, rows: Any) -> None:
            self.rows = rows

        def update(self, **changes: Any) -> int:
            if changes.get("applied") is True:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO materiality_ai_settings (created_at, updated_at, company_id, name, title,"
                        " model_settings, prompts, memo, created_by_user_id, applied, applied_at)"
                        " VALUES (now(), now(), %s, 'v99', '지어낸 겹친 판', '{}'::jsonb, NULL, '', 1, true, now())",
                        [company_id],
                    )
            return int(self.rows.update(**changes))

    class Racing:
        @staticmethod
        def for_company(cid: int) -> Any:
            rows = real.for_company(cid)

            class Scoped:
                def filter(self, **lookup: Any) -> Filtered:
                    return Filtered(rows.filter(**lookup))

            return Scoped()

    monkeypatch.setattr(services_module, "MaterialityAiSettingRow", Racing)


@pytest.mark.parametrize("before", [pytest.param(True, id="with-applied"), pytest.param(False, id="from-default")])
def test_a_racing_apply_is_409_and_writes_nothing(
    client: Client,
    companies: tuple[int, int],
    ops: tuple[int, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    before: bool,
) -> None:
    a, _ = companies
    _, headers = ops
    v1 = post(client, headers, a, {}).json()
    v2 = post(client, headers, a, {}).json()
    if before:
        assert put(client, headers, a, v1["id"]).status_code == 200
    audit = lines(a)
    _racing_rows(monkeypatch, a)
    assert code(put(client, headers, a, v2["id"])) == (409, "AI_SETTING_APPLY_CONFLICT")
    rows = dict(MaterialityAiSettingRow.for_company(a).values_list("name", "applied"))
    assert rows == {"v1": before, "v2": False}  # 옛 적용 판을 내린 것도 되돌렸다(겹친 행도 이 블록 안이라 같이)
    assert lines(a) == audit


def test_another_integrity_error_on_apply_is_not_caught(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    created = services_module.create_setting(company_id=a, created_by_user_id=1, title="지어낸 판", memo="")
    assert isinstance(created, services_module.Created)

    class Refusing:
        @staticmethod
        def for_company(cid: int) -> Any:
            class Scoped:
                def filter(self, **lookup: Any) -> Any:
                    class Filtered:
                        def update(self, **changes: Any) -> int:
                            raise IntegrityError("지어낸 다른 제약")

                    return Filtered()

            return Scoped()

    monkeypatch.setattr(services_module, "MaterialityAiSettingRow", Refusing)
    with pytest.raises(IntegrityError, match="지어낸 다른 제약"):
        services_module.apply_setting(company_id=a, setting_id=created.id, now=timezone.now())


def legacy_row(company_id: int, *, name: str = "v1") -> int:
    """옛 판(IRA3 앞 — 칸 열일곱) 행을 ORM 으로 바로 짓는다(시험 DB 주인 역할 — import_setting 길과 같은 꼴)."""
    return (
        MaterialityAiSettingRow.for_company(company_id)
        .create(
            company_id=company_id,
            name=name,
            title="⟦지어낸 옛 판⟧",
            model_settings=to_input(defaults(CONFIG, pm.MODELS)),
            prompts=legacy_body(),
            memo="",
            created_by_user_id=9,
        )
        .id
    )


# ── 옛 판(칸 열일곱 — IRA3, MARC-ENT-569) ──


def test_the_guarded_cases_leave_the_old_three_to_the_engine_defaults() -> None:
    """옛 셋은 판 칸이 아니라 자리 지킴 case 가 없다 — 셋은 늘 엔진 기본 글(자리는 엔진 test_texts.py 가 본다)."""
    assert {key for key, _ in REQUIRED_CASES}.isdisjoint(LEGACY)
    assert set(pm.LABELS).isdisjoint(LEGACY)
    read = pm.accept_stored(legacy_body())
    assert not isinstance(read, PromptRefused), read
    assert {key: getattr(pm.texts_from(read), key) for key in LEGACY} == {
        key: getattr(DEFAULT_TEXTS, key) for key in LEGACY
    }


def test_a_legacy_version_is_shown_as_fourteen_and_applied(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, _ = companies
    _, headers = ops
    setting_id = legacy_row(a)
    shown = client.get(f"{ROOT}/{setting_id}/prompt-model?companyId={a}", **headers)
    assert shown.status_code == 200, shown.content.decode()
    view = shown.json()
    PROMPT_MODEL_V3.validate_python(view, strict=True)
    assert [len(g["prompts"]) for g in view["promptGroups"]] == [2, 4, 2, 2, 2, 2]
    stored = {p["key"]: p["text"] for s in legacy_body()["steps"] for p in s["prompts"]}
    assert {key: e["text"] for key, e in entries(view).items()} == {k: stored[k] for k in pm.LABELS}
    applied = put(client, headers, a, setting_id)
    assert applied.status_code == 200, applied.content.decode()
    assert applied.json()["applied"] == {"kind": "saved", "id": setting_id}


def test_a_seventeen_save_is_400_keys_fixed(
    client: Client, companies: tuple[int, int], ops: tuple[int, dict[str, str]]
) -> None:
    a, _ = companies
    _, headers = ops
    response = post(client, headers, a, {"prompts": legacy_body()})
    assert code(response) == (400, "AI_PROMPT_KEYS_FIXED"), response.content.decode()
    assert MaterialityAiSettingRow.for_company(a).count() == 0
