# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportArgumentType=false
"""그린워싱 AI 설정 판의 프롬프트·모델 읽기 둘(밴드 AS2a §3-2 — GET /ai-settings/greenwash/default/prompt-model ·
/{setting_id}/prompt-model, 운영 관리자). 업무 층: 진짜 DB(주인 역할 — 앱 역할의 경계는 보안 층
tests/security/test_ai_settings.py).

    기본 판 200(몸 == 순수 조립, DB 0) · 저장 판 200(eval sha == 그 행의 eval_prompt_sha256 ≠ 기본 판)
    고객사 사용자 403(판 읽기 0) · 남의 판 404(없는 id 와 같은 몸) · 숫자 아닌 id 422 · 회사 고르기 400·404
    받기 규칙이 좁아진 판 409 AI_SETTING_UNUSABLE(기본 판은 200) · /default/prompt-model 이 기본 판(422 아님)
    기준표·모델 둘 다 안 맞는 판의 409 는 기준표 문장(AS3a-1 — 적용과 같은 차례, MARC-ISSUE-257 2번)

기준 글·이름은 지어낸 것이다(synthetic). 실제 AI 호출 0.
"""

import copy
import dataclasses
import json
from collections.abc import Iterator, Sequence
from typing import Any

import pytest
from django.db import connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext

from esgapi.core.calc.ai_settings import AiStepSpec, defaults
from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_V3
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.greenwash.flows import criteria_e0, prompt_model_e0
from esgapi.greenwash.flows.criteria_e0 import DEFAULT_VERSION, default_criteria
from esgapi.greenwash.models import GreenwashAiSettingRow
from esgapi.greenwash.service.selectors import ai_settings as selectors
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair

pytestmark = pytest.mark.django_db

PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"
ROOT = "/api/ai-settings/greenwash"
TABLE = "greenwash_ai_settings"


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
def ops(client: Client) -> dict[str, str]:
    created = create_operator(username="ops", name="가상 운영자", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    return bearer(changed_access(client, username="ops", subdomain=None))


def edited(text: str = "지어낸 기준 글: 근거 없이 쓴 환경 성과 주장") -> dict[str, Any]:
    criteria: dict[str, Any] = copy.deepcopy(dict(default_criteria()))
    criteria["rows"][9]["text"] = text
    return criteria


def save(client: Client, headers: dict[str, str], company_id: int, text: str = "지어낸 기준 글") -> int:
    response = client.post(
        f"{ROOT}?companyId={company_id}",
        data={"title": "지어낸 판 이름", "criteria": edited(text)},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 201, response.content.decode()
    return int(response.json()["id"])


def one(client: Client, headers: dict[str, str], setting_id: int | str, company_id: int | None) -> Any:
    query = "" if company_id is None else f"?companyId={company_id}"
    return client.get(f"{ROOT}/{setting_id}/prompt-model{query}", **headers)


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def eval_sha(body: dict[str, Any]) -> str:
    entries = {entry["key"]: entry for entry in body["promptGroups"][0]["prompts"]}
    return str(entries["eval"]["sha256"])


def reads_table(queries: CaptureQueriesContext) -> int:
    return len([q for q in queries.captured_queries if TABLE in q["sql"]])


# ── 1. 기본 판·저장 판 ──


def test_the_default_and_a_saved_board(client: Client, companies: tuple[int, int], ops: dict[str, str]) -> None:
    a, _ = companies
    config = load_config(default_config_sources(synthetic=False))
    expected = prompt_model_e0.prompt_model(
        config,
        setting_name=DEFAULT_VERSION,
        criteria=None,
        model=defaults(config, prompt_model_e0.STEPS),
        editable_model=True,  # AS2b: 모델 설정을 새 판에 넣는다
    )
    default = client.get(f"{ROOT}/default/prompt-model", **ops)
    assert default.status_code == 200, default.content.decode()
    assert default.json() == json.loads(json.dumps(expected))
    PROMPT_MODEL_V3.validate_python(default.json(), strict=True)

    v1 = save(client, ops, a)
    saved = one(client, ops, v1, a)
    assert saved.status_code == 200, saved.content.decode()
    body = saved.json()
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    assert body["settingName"] == "v1"
    row_sha = GreenwashAiSettingRow.for_company(a).get(id=v1).eval_prompt_sha256
    assert eval_sha(body) == row_sha
    assert eval_sha(body) != eval_sha(default.json())  # 분모: 고친 판은 다른 eval 글


# ── 2. 고객사 사용자 403·기본 판 DB 0 ──


def test_a_customer_is_403_before_any_read(client: Client, companies: tuple[int, int], ops: dict[str, str]) -> None:
    a, _ = companies
    v1 = save(client, ops, a)
    created = create_customer_user(actor_kind="admin", company_id=a, username="kim", name="김담당", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    customer = bearer(changed_access(Client(), username="kim", subdomain="tenant-a"))
    with CaptureQueriesContext(connection) as queries:
        refused = one(client, customer, v1, a)
    assert code(refused) == (403, "FORBIDDEN")
    assert reads_table(queries) == 0
    assert code(client.get(f"{ROOT}/default/prompt-model", **customer)) == (403, "FORBIDDEN")
    with CaptureQueriesContext(connection) as queries:
        assert one(client, ops, v1, a).status_code == 200
    assert reads_table(queries) >= 1  # 분모: 운영 관리자의 같은 요청은 판을 읽는다
    with CaptureQueriesContext(connection) as queries:
        assert client.get(f"{ROOT}/default/prompt-model", **ops).status_code == 200
    assert reads_table(queries) == 0  # 기본 판은 DB 0


# ── 3. 남의 판 ──


def test_another_companys_board_is_the_same_404(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    a, b = companies
    theirs = save(client, ops, b, "B 의 지어낸 글")
    got = one(client, ops, theirs, a)
    missing = one(client, ops, theirs + 1000, a)
    assert code(got) == (404, "NOT_FOUND")
    assert got.content == missing.content
    assert one(client, ops, theirs, b).status_code == 200  # 분모: 제 회사로는 보인다


# ── 4. 자리·회사 고르기 ──


def test_a_non_numeric_id_and_the_company_choice(
    client: Client, companies: tuple[int, int], ops: dict[str, str]
) -> None:
    a, b = companies
    assert code(one(client, ops, "abc", a)) == (422, "VALIDATION_ERROR")
    assert code(one(client, ops, 1, None)) == (400, "COMPANY_AMBIGUOUS")  # 회사 둘
    assert code(one(client, ops, 1, a + b + 1000)) == (404, "COMPANY_NOT_FOUND")


# ── 5. 못 받는 판 ──


def test_a_board_the_rules_no_longer_take_is_409(
    client: Client, companies: tuple[int, int], ops: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    text = "지어낸 기준 글: 좁히면 받지 못할 만큼 조금 긴 글"
    v1 = save(client, ops, a, text)
    assert one(client, ops, v1, a).status_code == 200  # 분모: 좁히기 전엔 지어진다
    monkeypatch.setattr(criteria_e0, "TEXT_CHARS", max(len(r["text"]) for r in edited(text)["rows"]) - 1)
    refused = one(client, ops, v1, a)
    assert code(refused) == (409, "AI_SETTING_UNUSABLE")
    message = refused.json()["error"]["message"]
    assert message == "AI 설정 판(v1)이 지금 규칙에 맞지 않아 프롬프트를 지을 수 없어요. 판을 다시 저장해 주세요"
    assert text not in json.dumps(refused.json(), ensure_ascii=False)
    assert client.get(f"{ROOT}/{v1}?companyId={a}", **ops).status_code == 200  # 판 상세는 그대로(카드만 막힘)
    assert client.get(f"{ROOT}/default/prompt-model", **ops).status_code == 200  # 기본 판은 좁혀도 200


# ── 6. 경로 차례 ──


def test_the_default_route_is_not_taken_as_an_id(client: Client, ops: dict[str, str]) -> None:
    response = client.get(f"{ROOT}/default/prompt-model", **ops)
    assert response.status_code == 200, response.content.decode()
    assert response.json()["settingName"] == DEFAULT_VERSION


# ── 7. 409 차례(AS3a-1 §3-8): 기준표 → 모델 ──

CRITERIA_MESSAGE = "AI 설정 판(v1)이 지금 규칙에 맞지 않아 프롬프트를 지을 수 없어요. 판을 다시 저장해 주세요"
MODEL_MESSAGE = "AI 설정 판(v1)의 모델 설정이 지금 고를 수 있는 모델에 맞지 않아요. 판을 다시 저장해 주세요"


def narrow_routes(monkeypatch: pytest.MonkeyPatch, *, without: str) -> None:
    """원천 명세(RunModelSource.steps)에서 경로 하나를 뺀다 — 저장 판의 모델 설정이 받기에 안 맞게 된다."""
    steps = tuple(
        dataclasses.replace(spec, routes=tuple(r for r in spec.routes if r != without))
        for spec in prompt_model_e0.STEPS
    )

    def narrow(self: selectors.RunModelSource) -> Sequence[AiStepSpec]:
        return steps

    monkeypatch.setattr(selectors.RunModelSource, "steps", narrow)


def test_a_board_failing_both_rules_says_the_criteria_first(
    client: Client, companies: tuple[int, int], ops: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    text = "지어낸 기준 글: 좁히면 받지 못할 만큼 조금 긴 글"
    v1 = save(client, ops, a, text)  # 모델 = 기본값(light-openai-41)
    narrow_routes(monkeypatch, without="light-openai-41")
    model_only = one(client, ops, v1, a)
    assert code(model_only) == (409, "AI_SETTING_UNUSABLE")
    assert model_only.json()["error"]["message"] == MODEL_MESSAGE  # 분모: 모델만 안 맞으면 모델 문장
    monkeypatch.setattr(criteria_e0, "TEXT_CHARS", max(len(r["text"]) for r in edited(text)["rows"]) - 1)
    both = one(client, ops, v1, a)
    assert code(both) == (409, "AI_SETTING_UNUSABLE")
    assert both.json()["error"]["message"] == CRITERIA_MESSAGE


# ── AP1b 3-4. 설정에서 빠진 고르지 않은 경로(MARC-ISSUE-280) — 500 이 아니라 unavailableRoutes ──

STANDARD = "standard-openai-41"


def save_standard(client: Client, headers: dict[str, str], company_id: int) -> int:
    """고른 경로가 standard-openai-41 인 판."""
    response = client.post(
        f"{ROOT}?companyId={company_id}",
        data={
            "title": "지어낸 판 이름",
            "criteria": edited(),
            "modelSettings": {
                "steps": [
                    {"key": "judge", "route": STANDARD, "temperature": 0.7, "webSearch": False, "maxOutputTokens": 2000}
                ]
            },
        },
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 201, response.content.decode()
    return int(response.json()["id"])


def without_standard(monkeypatch: pytest.MonkeyPatch) -> None:
    """원천 설정(RunModelSource.config)에서 standard-openai-41 을 뺀다(배포로 모델 파일이 바뀐 꼴)."""
    config = load_config(default_config_sources(synthetic=False))
    missing = dataclasses.replace(config, routes={k: v for k, v in config.routes.items() if k != STANDARD})

    def config_of(self: selectors.RunModelSource) -> LlmConfig:
        return missing

    monkeypatch.setattr(selectors.RunModelSource, "config", config_of)


def unavailable_standard(response: Any) -> None:
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    (slot,) = body["models"]
    assert [choice["route"] for choice in slot["routeChoices"]] == ["light-openai-41"]
    assert slot["unavailableRoutes"] == [STANDARD]


def test_the_default_board_names_a_route_missing_from_the_config(
    client: Client, ops: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    before = client.get(f"{ROOT}/default/prompt-model", **ops).json()
    assert before["models"][0]["unavailableRoutes"] == []  # 분모: 설정에 다 있으면 빈 목록
    without_standard(monkeypatch)
    unavailable_standard(client.get(f"{ROOT}/default/prompt-model", **ops))


def test_a_saved_board_names_it_too_but_one_that_chose_it_is_409(
    client: Client, companies: tuple[int, int], ops: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    light = save(client, ops, a)  # 모델 = 기본값(light-openai-41)
    standard = save_standard(client, ops, a)
    without_standard(monkeypatch)
    unavailable_standard(one(client, ops, light, a))
    refused = one(client, ops, standard, a)
    assert code(refused) == (409, "AI_SETTING_UNUSABLE")
    assert refused.json()["error"]["message"] == MODEL_MESSAGE.replace("(v1)", "(v2)")
