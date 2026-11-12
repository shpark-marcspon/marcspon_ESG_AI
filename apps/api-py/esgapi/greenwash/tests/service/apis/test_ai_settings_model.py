# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportArgumentType=false
"""그린워싱 AI 설정 판의 모델 설정 저장·조회(밴드 AS2b §3-2 — POST /ai-settings/greenwash 의 modelSettings,
GET …/{id}/prompt-model 의 저장 값, PUT …/applied 의 모델 다시 받기). 업무 층: 진짜 DB(주인 역할 — 앱 역할의 칸 권한은
보안 층 tests/security/test_ai_settings.py).

    3-2-1  modelSettings 없는 POST → 행 = 코드 값의 정규형, 응답 칸은 그대로(모델 칸 0 — 처분 B1)
    3-2-2  모델만 다른 새 판 v2(v1 그대로), 저장 = 정규형(0·0.0·-0.0 → 같은 값·같은 sha)
    3-2-3  받기 거절 400 AI_MODEL_*(NaN·Infinity 포함) · 꼴 틀림 422 — 둘 다 행 0·감사 0(분모: 그 칸만 고치면 201)
    3-2-4  저장 뒤 명세에서 그 경로를 빼면 적용 409(쓰기·감사 0), 기본 판 되돌리기 200
    3-2-5  prompt-model = 저장 값, editable.model True, sha == model_settings_sha256 · 좁히면 409(모델 문장)
    3-2-6  감사 ai_setting_created 의 changed_fields(Q-B4)

받기의 원천은 selectors.RunModelSource(시험 이음매 — 그 클래스의 steps). 기준 글·이름은 지어낸 것이다(synthetic).
실제 AI 호출 0.
"""

import copy
import dataclasses
import json
from collections.abc import Iterator, Sequence
from typing import Any

import pytest
from django.apps import apps
from django.test import Client, override_settings

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AiStepSpec,
    defaults,
    model_settings_sha256,
    to_input,
)
from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_V3
from esgapi.core.flows.binding import BindingRegistry
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.core.models import AuditEventRow, DocumentRow
from esgapi.greenwash.flows import colab_e0, prompt_model_e0
from esgapi.greenwash.flows.binding_e0 import GreenwashBinding
from esgapi.greenwash.flows.criteria_e0 import default_criteria
from esgapi.greenwash.models import GreenwashAiSettingRow
from esgapi.greenwash.service.selectors import ai_settings as selectors
from esgapi.runs import tasks
from esgapi.user.service.services.user import create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair, login

pytestmark = pytest.mark.django_db

PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"
ROOT = "/api/ai-settings/greenwash"
CONFIG = load_config(default_config_sources(synthetic=False))
STANDARD = {
    "key": "judge",
    "route": "standard-openai-41",
    "temperature": 0.7,
    "webSearch": False,
    "maxOutputTokens": 2000,
}
SETTING_KEYS = {
    "schemaVersion",
    "id",
    "name",
    "title",  # AS3a-2 @2
    "status",
    "createdAt",
    "createdBy",
    "memo",
    "evalPromptSha256",
    "criteria",
    "terms",  # G2d @3
}
"""판 응답(greenwash.ai-setting@3)의 칸 — AS2b 앞과 같다(모델 칸은 prompt-model 로만, 처분 B1). G2d 가 terms 를 더함."""
MISSING = object()


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


def criteria() -> dict[str, Any]:
    found: dict[str, Any] = copy.deepcopy(dict(default_criteria()))
    found["rows"][9]["text"] = "지어낸 기준 글: 근거 없이 쓴 환경 성과 주장"
    return found


def post(client: Client, headers: dict[str, str], company_id: int, body: dict[str, Any] | str) -> Any:
    data = body if isinstance(body, str) else json.dumps({"title": "지어낸 판 이름", **body})
    return client.post(f"{ROOT}?companyId={company_id}", data=data, content_type="application/json", **headers)


def with_model(*steps: dict[str, Any]) -> dict[str, Any]:
    return {"title": "지어낸 판 이름", "criteria": criteria(), "modelSettings": {"steps": list(steps)}}


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def stored(company_id: int) -> list[tuple[str, Any]]:
    return list(GreenwashAiSettingRow.for_company(company_id).order_by("id").values_list("name", "model_settings"))


def lines(company_id: int) -> list[tuple[Any, ...]]:
    rows = AuditEventRow.for_company(company_id).filter(action="setting_change").order_by("id")
    return [(r.event, r.target_id, r.detail) for r in rows]


def accepted(given: dict[str, Any]) -> AcceptedModelSettings:
    found = prompt_model_e0.accept_model(CONFIG, given)
    assert isinstance(found, AcceptedModelSettings), found
    return found


# ── 3-2-1 빠지면 코드 값 ──


def test_a_post_without_model_settings_stores_the_code_value(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    a, _ = companies
    response = post(client, ops, a, {"criteria": criteria()})
    assert response.status_code == 201, response.content.decode()
    assert set(response.json()) == SETTING_KEYS
    assert stored(a) == [("v1", to_input(defaults(CONFIG, prompt_model_e0.STEPS)))]
    with_standard = post(client, ops, a, with_model(STANDARD))
    assert with_standard.status_code == 201, with_standard.content.decode()
    assert set(with_standard.json()) == SETTING_KEYS  # 모델을 실어도 판 응답의 칸은 같다


# ── 3-2-2 모델만 다른 새 판 ──


def test_a_model_only_change_is_a_new_version(client: Client, companies: tuple[int, int], ops: dict[str, str]) -> None:
    a, _ = companies
    v1 = post(client, ops, a, {"criteria": criteria()})
    assert v1.status_code == 201
    before = stored(a)
    v2 = post(client, ops, a, with_model(STANDARD))
    assert (v2.status_code, v2.json()["name"]) == (201, "v2"), v2.content.decode()
    assert v2.json()["criteria"]["rows"] == v1.json()["criteria"]["rows"]  # 기준표는 같다
    rows = stored(a)
    assert rows[0] == before[0]  # v1 그대로
    assert rows[1] == ("v2", {"steps": [STANDARD]})
    assert rows[1][1] != rows[0][1]


def test_zero_temperatures_are_one_value(client: Client, companies: tuple[int, int], ops: dict[str, str]) -> None:
    """0 · 0.0 · -0.0 → 저장 0.0, 같은 sha(정규형)."""
    a, _ = companies
    template = json.dumps(with_model({**STANDARD, "temperature": 7.25}))
    for raw in ("0", "0.0", "-0.0"):
        response = post(client, ops, a, template.replace("7.25", raw))
        assert response.status_code == 201, (raw, response.content.decode())
    rows = [model for _, model in stored(a)]
    assert [model["steps"][0]["temperature"] for model in rows] == [0.0, 0.0, 0.0]
    assert all(str(model["steps"][0]["temperature"]) == "0.0" for model in rows)  # -0.0 아님
    assert len({model_settings_sha256(accepted(model)) for model in rows}) == 1


# ── 3-2-3 거절 ──


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        pytest.param({"route": "light-openai"}, "AI_MODEL_ROUTE_UNKNOWN", id="route-outside"),
        pytest.param({"webSearch": True}, "AI_MODEL_WEB_SEARCH_UNSUPPORTED", id="web-search"),
        pytest.param({"maxOutputTokens": 32769}, "AI_MODEL_MAX_OUTPUT_RANGE", id="max-output"),
        pytest.param({"key": "scan"}, "AI_MODEL_STEPS_FIXED", id="step-key"),
        pytest.param({"temperature": 2.5}, "AI_MODEL_TEMPERATURE_RANGE", id="temperature-above"),
    ],
)
def test_a_refused_model_is_400_and_writes_nothing(
    client: Client, companies: tuple[int, int], ops: dict[str, str], change: dict[str, Any], expected: str
) -> None:
    a, _ = companies
    refused = post(client, ops, a, with_model({**STANDARD, **change}))
    assert code(refused) == (400, expected), refused.content.decode()
    assert (stored(a), lines(a)) == ([], [])
    assert post(client, ops, a, with_model(STANDARD)).status_code == 201  # 분모: 그 칸만 고치면 된다


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity"])
def test_a_non_finite_temperature_is_400(
    client: Client, companies: tuple[int, int], ops: dict[str, str], raw: str
) -> None:
    """날 JSON 의 NaN·Infinity 는 꼴을 지나 받기가 거절한다(처분 2 — c3 웹 글 표)."""
    a, _ = companies
    template = json.dumps(with_model({**STANDARD, "temperature": 7.25}))
    refused = post(client, ops, a, template.replace("7.25", raw))
    assert code(refused) == (400, "AI_MODEL_TEMPERATURE_RANGE"), refused.content.decode()
    assert (stored(a), lines(a)) == ([], [])
    assert post(client, ops, a, template.replace("7.25", "0.7")).status_code == 201  # 분모


@pytest.mark.parametrize(
    "change",
    [
        pytest.param({"extra": 1}, id="unknown-key"),
        pytest.param({"maxOutputTokens": True}, id="max-output-bool"),
        pytest.param({"maxOutputTokens": "5"}, id="max-output-text"),
        pytest.param({"temperature": True}, id="temperature-bool"),
        pytest.param({"webSearch": 0}, id="web-search-int"),
        pytest.param({"route": MISSING}, id="route-missing"),
    ],
)
def test_a_bad_model_shape_is_422(
    client: Client, companies: tuple[int, int], ops: dict[str, str], change: dict[str, Any]
) -> None:
    a, _ = companies
    step = {key: value for key, value in {**STANDARD, **change}.items() if value is not MISSING}
    assert code(post(client, ops, a, with_model(step))) == (422, "VALIDATION_ERROR")
    assert (stored(a), lines(a)) == ([], [])
    assert post(client, ops, a, with_model(STANDARD)).status_code == 201  # 분모


# ── 3-2-4 적용 막기 ──


def narrowed(monkeypatch: pytest.MonkeyPatch, *, without: str) -> None:
    """원천 명세(RunModelSource.steps)에서 경로 하나를 뺀다 — 저장·적용·조회·실행기가 함께 본다."""
    steps = tuple(
        dataclasses.replace(spec, routes=tuple(r for r in spec.routes if r != without))
        for spec in prompt_model_e0.STEPS
    )

    def narrow(self: selectors.RunModelSource) -> Sequence[AiStepSpec]:
        return steps

    monkeypatch.setattr(selectors.RunModelSource, "steps", narrow)


def test_a_board_whose_model_is_no_longer_taken_cannot_be_applied(
    client: Client, companies: tuple[int, int], ops: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    v1 = post(client, ops, a, with_model(STANDARD)).json()["id"]
    before = (stored(a), lines(a))
    narrowed(monkeypatch, without="standard-openai-41")
    refused = client.put(f"{ROOT}/applied?companyId={a}", data={"id": v1}, content_type="application/json", **ops)
    assert code(refused) == (409, "AI_SETTING_UNUSABLE"), refused.content.decode()
    assert not GreenwashAiSettingRow.for_company(a).get(id=v1).applied
    assert (stored(a), lines(a)) == before  # 쓰기·감사 0
    back = client.put(f"{ROOT}/applied?companyId={a}", data={"id": None}, content_type="application/json", **ops)
    assert back.status_code == 200  # 기본 판 되돌리기는 늘 된다
    monkeypatch.undo()
    applied = client.put(f"{ROOT}/applied?companyId={a}", data={"id": v1}, content_type="application/json", **ops)
    assert applied.status_code == 200  # 분모: 좁히기 전 명세면 적용된다


# ── 3-2-5 prompt-model 의 저장 값 ──


def test_prompt_model_shows_the_stored_model(
    client: Client, companies: tuple[int, int], ops: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    v1 = post(client, ops, a, with_model(STANDARD)).json()["id"]
    response = client.get(f"{ROOT}/{v1}/prompt-model?companyId={a}", **ops)
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    model = body["models"][0]["model"]
    assert (model["route"], model["temperature"], model["maxOutputTokens"]) == ("standard-openai-41", 0.7, 2000)
    assert body["editable"]["model"] is True
    assert body["modelSettingsSha256"] == model_settings_sha256(accepted({"steps": [STANDARD]}))
    default = client.get(f"{ROOT}/default/prompt-model", **ops).json()
    assert body["modelSettingsSha256"] != default["modelSettingsSha256"]  # 분모: 기본 판은 코드 값

    narrowed(monkeypatch, without="standard-openai-41")
    refused = client.get(f"{ROOT}/{v1}/prompt-model?companyId={a}", **ops)
    assert code(refused) == (409, "AI_SETTING_UNUSABLE")
    message = refused.json()["error"]["message"]
    assert message == "AI 설정 판(v1)의 모델 설정이 지금 고를 수 있는 모델에 맞지 않아요. 판을 다시 저장해 주세요"


# ── CO1(MARC-ISSUE-248 ⓐ): 모델 파일에서 경로가 빠지면 거절이지 500 이 아니다 ──


def test_a_route_missing_from_the_models_file_is_refused_not_500(
    client: Client, companies: tuple[int, int], ops: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """원천 설정(RunModelSource.config)에서 standard-openai-41 을 뺀다(배포로 모델 파일이 바뀐 꼴). 기본 경로는 그대로라
    기본 판·기본 실행은 산다. 판 POST 400 · 적용 409 · 그 판이 적용된 회사의 실행 만들기 409 — 행·감사 0."""
    a, _ = companies
    v1 = post(client, ops, a, with_model(STANDARD)).json()["id"]  # 분모: 빼기 전엔 201
    applied = client.put(f"{ROOT}/applied?companyId={a}", data={"id": v1}, content_type="application/json", **ops)
    assert applied.status_code == 200, applied.content.decode()
    bindings = BindingRegistry()
    bindings.register(
        colab_e0.FLOW_ID,
        GreenwashBinding(
            store=selectors.RunSettingStore(),
            models=selectors.RunModelSource(),
            chat_route="mock",
            embedding_route="mock-gw1",
        ),
    )
    monkeypatch.setattr(tasks, "BINDINGS", bindings)
    document = DocumentRow.for_company(a).create(
        company_id=a,
        uploaded_by="1",
        file_name="synthetic.pdf",
        storage_key=f"companies/{a}/documents/co1/original",
        size_bytes=1,
        etag="synthetic",
        status="uploaded",
    )
    customer = Client()
    login(customer)
    run_body = {
        "module": "greenwash",
        "documentId": document.pk,
        "options": {"parts": {"ceo": [1], "company": [2], "climate": [3]}},
    }
    before = (stored(a), lines(a))
    missing = dataclasses.replace(CONFIG, routes={k: v for k, v in CONFIG.routes.items() if k != "standard-openai-41"})

    def without_the_route(self: selectors.RunModelSource) -> LlmConfig:
        return missing

    monkeypatch.setattr(selectors.RunModelSource, "config", without_the_route)

    refused = post(client, ops, a, with_model(STANDARD))
    assert code(refused) == (400, "AI_MODEL_ROUTE_UNAVAILABLE"), refused.content.decode()
    again = client.put(f"{ROOT}/applied?companyId={a}", data={"id": v1}, content_type="application/json", **ops)
    assert code(again) == (409, "AI_SETTING_UNUSABLE"), again.content.decode()
    run = customer.post("/api/runs", data=run_body, content_type="application/json")
    assert code(run) == (409, "AI_SETTING_UNUSABLE"), run.content.decode()
    assert (stored(a), lines(a)) == before  # 쓰기·감사 0
    assert apps.get_model("runs", "RunRow").for_company(a).count() == 0  # pyright: ignore[reportAttributeAccessIssue]


# ── 3-2-6 감사 ──


def test_the_created_line_names_the_model_settings(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    a, _ = companies
    v1 = post(client, ops, a, with_model(STANDARD)).json()["id"]
    assert lines(a) == [
        (
            "ai_setting_created",
            v1,
            {"changed_fields": ["criteria", "memo", "model_settings", "prompts", "terms"], "module": "greenwash"},
        )
    ]
