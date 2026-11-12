# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportArgumentType=false, reportUnknownLambdaType=false
"""그린워싱 AI 설정 판의 프롬프트 글·칸 메모·판 이름 저장(밴드 AS3a-2 §3-1 — POST /ai-settings/greenwash 의 title·
prompts, GET …/{id}/prompt-model 의 저장 글, PUT …/applied 의 프롬프트 다시 받기, 판 꼴 @3). 업무 층: 진짜 DB(주인
역할 — 앱 역할의 칸 권한은 보안 층 tests/security/test_ai_settings.py).

    3-1-1  공백 붙은 글·메모 → 행 메모 strip·글 바이트 그대로, sha = 저장 EVAL, prompt-model 이 보임·editable.prompts
    3-1-2  한 번 저장 = 판 하나 — 셋 다 맞음 행 1, 하나씩 틀림 400·행 0·감사 0, 둘 틀림은 앞 차례 code
    3-1-3  거절 여덟 400 code·fields 경로 · 4바이트 총 크기 400(500 아님)·분모 201 · 메모 NUL 400
    3-1-4  출력절 고친 글 outputKept false · 코드 글과 같은 글은 칸 값 그대로(접지 않음)
    3-1-5  prompts·modelSettings 없음·null → 칸 NULL·코드 값 · criteria 없음 → 기본 기준표
    3-1-6  메모만 다른 새 판(같은 prompts sha) · 같은 이름 두 판
    3-1-7  저장 뒤 받기를 좁히면 적용·prompt-model 409(쓰기·감사 0), 기본 판 되돌리기 200
    3-1-8  감사 changed_fields 넷 · title 꼴 넷 422
    3-1-9  기본 판·목록 default 의 title = DEFAULT_TITLE · 옛 행(title NULL) → null

글·이름·메모는 지어낸 것이다(synthetic). 실제 AI 호출 0.
"""

import copy
import json
from collections.abc import Iterator
from typing import Any

import pytest
from django.test import Client, override_settings

from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.core.calc.ai_settings import AcceptedPrompts, prompts_sha256
from esgapi.core.llm.log import sha256_text
from esgapi.core.models import AuditEventRow
from esgapi.greenwash.contracts.ai_setting_shapes import DEFAULT_SHAPES, DEFAULT_TITLE, SETTING_SHAPE
from esgapi.greenwash.engines.e0.prompts import default_prompts
from esgapi.greenwash.flows import colab_e0, prompt_model_e0
from esgapi.greenwash.flows.criteria_e0 import default_criteria
from esgapi.greenwash.models import GreenwashAiSettingRow
from esgapi.user.service.services.user import create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair

pytestmark = pytest.mark.django_db

PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"
ROOT = "/api/ai-settings/greenwash"
TITLE = "지어낸 판 이름"
VERSION = colab_e0.judged_prompt_version(dict(colab_e0.SCAN_CONFIG))
FIELDS = colab_e0.PROMPT_FIELDS
BAD_MODEL = {"key": "judge", "route": "light-openai-41", "temperature": 7.25, "webSearch": False, "maxOutputTokens": 9}


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


def code_texts() -> dict[str, str]:
    pack = default_prompts(VERSION)
    return {key: getattr(pack, field) for key, field in FIELDS.items()}


def prompts(texts: dict[str, str] | None = None, memos: dict[str, str] | None = None) -> dict[str, Any]:
    texts = code_texts() if texts is None else texts
    memos = memos or {}
    return {
        "steps": [{"key": "judge", "prompts": [{"key": k, "text": texts[k], "memo": memos.get(k, "")} for k in FIELDS]}]
    }


def edited_texts() -> dict[str, str]:
    """넷 다 고친 글 — 출력절은 그대로 둔다(머리에 지어낸 한 줄)."""
    return {key: f"[지어낸 머리 {key}]\n{text}" for key, text in code_texts().items()}


def post(client: Client, headers: dict[str, str], company_id: int, body: dict[str, Any]) -> Any:
    data = json.dumps({"title": TITLE, **body})
    return client.post(f"{ROOT}?companyId={company_id}", data=data, content_type="application/json", **headers)


def view(client: Client, headers: dict[str, str], company_id: int, setting_id: int) -> Any:
    return client.get(f"{ROOT}/{setting_id}/prompt-model?companyId={company_id}", **headers)


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


def entries(response: Any) -> dict[str, dict[str, Any]]:
    return {entry["key"]: entry for entry in response.json()["promptGroups"][0]["prompts"]}


# ── 3-1-1 저장·보기 ──


def test_saved_text_is_kept_byte_for_byte_and_the_memo_is_stripped(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    a, _ = companies
    v1 = post(client, ops, a, {}).json()["id"]  # 코드 글 판
    texts = {key: f"  {text}\n\n" for key, text in edited_texts().items()}
    memos = {key: f"  지어낸 칸 메모 {key}  " for key in FIELDS}
    saved = post(client, ops, a, {"prompts": prompts(texts, memos), "memo": "지어낸 판 메모"})
    assert saved.status_code == 201, saved.content.decode()
    body = saved.json()
    assert (body["schemaVersion"], body["name"], body["title"]) == (SETTING_SHAPE, "v2", TITLE)
    stored = row(body["id"], a)
    step = stored.prompts["steps"][0]["prompts"]  # pyright: ignore[reportOptionalSubscript, reportIndexIssue]
    assert [p["text"] for p in step] == [texts[k] for k in FIELDS]  # 글은 바이트 그대로
    assert [p["memo"] for p in step] == [memos[k].strip() for k in FIELDS]  # 메모는 strip
    assert stored.eval_prompt_sha256 == sha256_text(texts["eval"]) == body["evalPromptSha256"]
    shown = view(client, ops, a, body["id"])
    assert shown.status_code == 200
    assert shown.json()["editable"] == {"prompts": True, "model": True}
    assert {k: (e["text"], e["memo"]) for k, e in entries(shown).items()} == {
        k: (texts[k], memos[k].strip()) for k in FIELDS
    }
    assert entries(shown)["eval"]["sha256"] == stored.eval_prompt_sha256
    assert row(v1, a).prompts is None  # v1 그대로(불변 — 새 판이 생겼을 뿐)
    assert entries(view(client, ops, a, v1))["detect"]["text"] == code_texts()["detect"]


# ── 3-1-2 한 번 저장 = 판 하나, 받기 차례 기준표 → 모델 → 프롬프트 ──


def _bad_criteria() -> dict[str, Any]:
    criteria: dict[str, Any] = copy.deepcopy(dict(default_criteria()))
    criteria["rows"][9]["text"] = ""
    return criteria


def _bad_prompts() -> dict[str, Any]:
    return prompts({**code_texts(), "repair": "   "})


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        pytest.param({"criteria": "bad"}, "CRITERIA_TEXT_LENGTH", id="criteria"),
        pytest.param({"modelSettings": "bad"}, "AI_MODEL_TEMPERATURE_RANGE", id="model"),
        pytest.param({"prompts": "bad"}, "AI_PROMPT_TEXT_EMPTY", id="prompts"),
        pytest.param({"criteria": "bad", "prompts": "bad"}, "CRITERIA_TEXT_LENGTH", id="criteria-before-prompts"),
        pytest.param({"modelSettings": "bad", "prompts": "bad"}, "AI_MODEL_TEMPERATURE_RANGE", id="model-before"),
    ],
)
def test_one_refusal_writes_nothing(
    client: Client, companies: tuple[int, int], ops: dict[str, str], body: dict[str, str], expected: str
) -> None:
    a, _ = companies
    good = {"criteria": default_criteria(), "modelSettings": {"steps": [dict(prompt_model_e0.JUDGE.default)]}}
    good["prompts"] = prompts(edited_texts())
    bad = {"criteria": _bad_criteria(), "modelSettings": {"steps": [BAD_MODEL]}, "prompts": _bad_prompts()}
    refused = post(client, ops, a, {**good, **{k: bad[k] for k in body}})
    assert error(refused)[:2] == (400, expected), refused.content.decode()
    assert (rows(a), lines(a)) == (0, [])
    assert post(client, ops, a, good).status_code == 201  # 분모: 셋 다 맞으면 행 1
    assert rows(a) == 1


# ── 3-1-3 거절 여덟·크기 ──


def _with(edit: Any) -> dict[str, Any]:
    body = prompts(edited_texts())
    edit(body)
    return body


AT = "prompts.steps.0.prompts"
REFUSALS = [
    ("steps", lambda b: b["steps"].append({"key": "more", "prompts": []}), "AI_PROMPT_STEPS_FIXED", "prompts.steps"),
    ("keys", lambda b: b["steps"][0]["prompts"].reverse(), "AI_PROMPT_KEYS_FIXED", AT),
    ("empty", lambda b: b["steps"][0]["prompts"][1].update(text=" \n"), "AI_PROMPT_TEXT_EMPTY", f"{AT}.1.text"),
    (
        "duplicate",
        lambda b: b["steps"][0]["prompts"][2].update(text=b["steps"][0]["prompts"][0]["text"]),
        "AI_PROMPT_TEXT_DUPLICATE",
        f"{AT}.2.text",
    ),
    ("length", lambda b: b["steps"][0]["prompts"][3].update(text="가" * 8001), "AI_PROMPT_TEXT_LENGTH", f"{AT}.3.text"),
    ("chars", lambda b: b["steps"][0]["prompts"][0].update(text="글\x00자"), "AI_PROMPT_CHARS", f"{AT}.0.text"),
    ("memo-nul", lambda b: b["steps"][0]["prompts"][1].update(memo="메\x00모"), "AI_PROMPT_CHARS", f"{AT}.1.memo"),
    ("memo", lambda b: b["steps"][0]["prompts"][1].update(memo="가" * 501), "AI_PROMPT_MEMO_LENGTH", f"{AT}.1.memo"),
]


@pytest.mark.parametrize(("edit", "expected", "field"), [pytest.param(e, c, f, id=n) for n, e, c, f in REFUSALS])
def test_a_refused_prompt_is_400_with_the_field_path(
    client: Client, companies: tuple[int, int], ops: dict[str, str], edit: Any, expected: str, field: str
) -> None:
    a, _ = companies
    status, found, fields = error(post(client, ops, a, {"prompts": _with(edit)}))
    assert (status, found) == (400, expected)
    assert list(fields) == [field] and len(fields[field]) == 1
    assert (rows(a), lines(a)) == (0, [])


def _wide(memo_chars: int) -> dict[str, Any]:
    """넷 다 4바이트 글자 8,000자 글(서로 다름) + 4바이트 글자 메모."""
    texts = {key: "😀" * 7999 + str(i) for i, key in enumerate(FIELDS)}
    return prompts(texts, {key: "😀" * memo_chars for key in FIELDS})


def test_the_total_size_is_refused_by_the_rule_not_the_database(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    a, _ = companies
    refused = post(client, ops, a, {"prompts": _wide(500)})  # 약 136,000 B
    assert error(refused) == (400, "AI_PROMPT_TOTAL_SIZE", {"prompts": [refused.json()["error"]["message"]]})
    assert (rows(a), lines(a)) == (0, [])
    assert post(client, ops, a, {"prompts": _wide(0)}).status_code == 201  # 분모: 약 128,000 B 는 받는다


# ── 3-1-4 출력절·코드 글과 같은 글 ──


def test_an_edited_output_section_warns_and_a_code_text_is_not_folded(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    a, _ = companies
    texts = code_texts()
    section = prompt_model_e0.output_section(texts["detect"])
    assert section is not None
    changed = {**texts, "detect": texts["detect"].replace(section, "[지어낸 출력 형식]")}
    v1 = post(client, ops, a, {"prompts": prompts(changed)})
    assert v1.status_code == 201
    assert entries(view(client, ops, a, v1.json()["id"]))["detect"]["outputKept"] is False
    same = post(client, ops, a, {"prompts": prompts(texts)}).json()["id"]
    assert row(same, a).prompts == prompts(texts)  # 접지 않는다(NULL 아님)
    assert all(e["isDefault"] for e in entries(view(client, ops, a, same)).values())


# ── 3-1-5 빠진 칸 ──


@pytest.mark.parametrize("missing", [pytest.param(True, id="missing"), pytest.param(False, id="null")])
def test_missing_prompts_model_and_criteria_mean_the_code_values(
    client: Client, companies: tuple[int, int], ops: dict[str, str], missing: bool
) -> None:
    a, _ = companies
    body: dict[str, Any] = {} if missing else {"prompts": None, "modelSettings": None, "criteria": None}
    saved = post(client, ops, a, body)
    assert saved.status_code == 201, saved.content.decode()
    stored = row(saved.json()["id"], a)
    assert stored.prompts is None
    assert stored.model_settings == {"steps": [dict(prompt_model_e0.JUDGE.default)]}
    assert stored.criteria == {**default_criteria(), "version": "v1"}
    assert stored.eval_prompt_sha256 == colab_e0.run_versions(None)["evalPromptSha256"]


# ── 3-1-6 메모만 다른 판·같은 이름 ──


def test_a_memo_only_change_is_a_new_version_with_the_same_text_sha(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    a, _ = companies
    first = post(client, ops, a, {"prompts": prompts(edited_texts(), {"eval": "첫 메모"})}).json()
    second = post(client, ops, a, {"prompts": prompts(edited_texts(), {"eval": "둘째 메모"})}).json()
    assert (first["name"], second["name"], first["title"], second["title"]) == ("v1", "v2", TITLE, TITLE)

    def sha(setting_id: int) -> str:
        accepted = prompt_model_e0.accept_prompts(row(setting_id, a).prompts)  # pyright: ignore[reportArgumentType]
        assert isinstance(accepted, AcceptedPrompts)
        return prompts_sha256(accepted)

    assert sha(first["id"]) == sha(second["id"])


# ── 3-1-7 저장 뒤 받기를 좁힘 ──


def test_a_saved_text_the_rules_no_longer_take_is_unusable(
    client: Client, companies: tuple[int, int], ops: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    v1 = post(client, ops, a, {"prompts": prompts(edited_texts())}).json()["id"]
    before = lines(a)
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)
    assert error(put(client, ops, a, v1))[:2] == (409, "AI_SETTING_UNUSABLE")
    assert error(view(client, ops, a, v1))[:2] == (409, "AI_SETTING_UNUSABLE")
    assert "프롬프트 글" in view(client, ops, a, v1).json()["error"]["message"]
    assert (row(v1, a).applied, lines(a)) == (False, before)  # 쓰기·감사 0
    assert put(client, ops, a, None).status_code == 200  # 기본 판으로는 늘 된다


# ── 3-1-8 감사·title 꼴 ──


def test_the_created_line_names_four_fields(client: Client, companies: tuple[int, int], ops: dict[str, str]) -> None:
    a, _ = companies
    v1 = post(client, ops, a, {"prompts": prompts(edited_texts())}).json()["id"]
    assert lines(a) == [
        (
            "ai_setting_created",
            v1,
            {"changed_fields": ["criteria", "memo", "model_settings", "prompts", "terms"], "module": "greenwash"},
        )
    ]


@pytest.mark.parametrize(
    "title",
    [
        pytest.param(KeyError, id="missing"),
        pytest.param("   ", id="blank"),
        pytest.param("가" * 41, id="41"),
        pytest.param("판\x00이름", id="nul"),
    ],
)
def test_a_bad_title_is_422(client: Client, companies: tuple[int, int], ops: dict[str, str], title: object) -> None:
    a, _ = companies
    body: dict[str, Any] = {"criteria": default_criteria()}
    if title is not KeyError:
        body["title"] = title
    response = client.post(f"{ROOT}?companyId={a}", data=json.dumps(body), content_type="application/json", **ops)
    status, found, fields = error(response)
    assert (status, found, list(fields)) == (422, "VALIDATION_ERROR", ["title"])
    assert rows(a) == 0
    saved = post(client, ops, a, {"title": "  " + "가" * 40 + " "})  # 분모: strip 뒤 40자는 된다
    assert saved.status_code == 201 and saved.json()["title"] == "가" * 40


# ── 3-1-9 기본 판·옛 판의 이름 ──


def test_the_default_and_old_rows_carry_their_titles(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    a, _ = companies
    fallback = client.get(f"{ROOT}/default", **ops).json()
    DEFAULT_SHAPES[fallback["schemaVersion"]].validate_python(fallback, strict=True)
    assert fallback["title"] == DEFAULT_TITLE
    v1 = post(client, ops, a, {}).json()["id"]
    GreenwashAiSettingRow.for_company(a).filter(id=v1).update(title=None)  # 0005 앞의 옛 행(주인 역할)
    listed = client.get(f"{ROOT}?companyId={a}", **ops).json()
    assert listed["default"]["title"] == DEFAULT_TITLE
    assert [item["title"] for item in listed["items"]] == [None]
    assert client.get(f"{ROOT}/{v1}?companyId={a}", **ops).json()["title"] is None
