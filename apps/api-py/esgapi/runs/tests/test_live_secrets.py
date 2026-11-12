# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실제 공급사를 켠 실행기(LV1)의 키 누설 0. 업무 층(test_context_live.py 의 가짜 HTTP·실행기 세계를 그대로).

지어낸 키 둘:
  SK     sk-proj-LV1SENTINEL… — 가림(providers/redact.py 의 sk- 꼴) 안. 가짜 공급사가 401 몸에 그대로 되돌린다
  PLAIN  LV1PLAINSENTINEL…    — 가림의 꼴 밖. 가림에 기대지 않는 자리(설정 실패 글·repr·기동 줄·기록·행·응답)를 잰다
찾는 낱말: 가운데 「LV1SENTINEL」·앞 8자 「LV1PLAIN」·「sk-proj-」(앞머리·뒷부분만 남아도 걸린다).
재는 자리: 설정 실패 글 · repr(설정) · 기동 줄(stderr) · caplog 전부(DEBUG — SDK·httpx 의 기록 포함) · 실행·단계 행 ·
감사 행 · core_llm_call_logs 행 · GET /run-logs/{id} · /run-logs/metrics · OpenAPI 문서.
분모: 가짜 공급사는 Authorization 머리로 키를 받았다(키가 실행기를 지나갔다) · 일부러 한 번 찍으면 잡힌다(양성 대조).
★ 공급사가 되돌린 몸은 ProviderFailed.message(메모리)에 남는다 — sk- 꼴은 가려지고 꼴 밖 글자는 그대로다. 그 글을
  기록·예외에 싣는 것은 모듈 몫이다(그린워싱 llm_bridge 는 kind 만 싣는다 — 이 가짜 흐름도 그 꼴로 던진다).
"""

import logging
from collections.abc import Iterable
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from esgapi.config.env import ConfigError, LlmSettings, load_config, run_mode_notice
from esgapi.core.models import AuditEventRow, LlmCallLogRow
from esgapi.runs.models import RunRow, RunStepRow
from esgapi.runs.tests import test_context_live, test_executor
from esgapi.runs.tests.test_context_live import SK, FakeOpenAI, chat, embed, live_settings, status, use
from esgapi.runs.tests.test_executor import ProbeAdapters, World, execute, new_run, row
from tests.support.http import bearer, bearer_pair

pytestmark = pytest.mark.django_db

# 픽스처(이 이름들로 선다): 실행기 세계·가짜 OpenAI·네트워크 0(autouse)
executor_world = test_executor.world
world = test_context_live.world
fake = test_context_live.fake
no_network = test_context_live.no_network

PLAIN = "LV1PLAINSENTINEL" + "p" * 24
NEEDLES = ("LV1SENTINEL", "LV1PLAIN", "sk-proj-")  # 가운데 낱말 둘 + 앞머리(앞 8자만 새도 걸린다)
ENV = {
    "DATABASE_URL_PY": "postgres://esg_app:pw@postgres:5432/esg_py",
    "EDK_JWT_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\\nabc\\n-----END PUBLIC KEY-----\\n",
    "EDK_JWT_AUDIENCE": "esg-api",
    "EDK_JWT_ISSUER": "https://edk.example",
    "SESSION_SECRET": "x" * 32,
    "SESSION_TTL_SECONDS": "3600",
}
PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"


def found(texts: Iterable[str]) -> list[str]:
    """글들 가운데 지어낸 키의 가운데 낱말이 든 것(앞 80자)."""
    return [text[:80] for text in texts if any(needle in text for needle in NEEDLES)]


def test_the_scan_catches_a_key_printed_once(caplog: pytest.LogCaptureFixture) -> None:
    """양성 대조: 기록에 키를 일부러 한 번 찍으면 found 가 잡는다(둘 다, 앞 8자만이어도)."""
    caplog.set_level(logging.DEBUG)
    logging.getLogger("esgapi.runs.tasks").warning("planted %s", PLAIN)
    logging.getLogger("esgapi.runs.tasks").warning("planted %s", SK[:20])
    logging.getLogger("esgapi.runs.tasks").warning("planted %s", PLAIN[:8])
    logging.getLogger("esgapi.runs.tasks").warning("planted %s", SK[:8])
    assert len(found([r.getMessage() for r in caplog.records])) == 4
    assert found(["sk-[가림]", "no key here"]) == []


# ── 설정 ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("key", [SK, PLAIN])
def test_settings_failures_repr_and_the_notice_carry_no_key(key: str, capsys: pytest.CaptureFixture[str]) -> None:
    live = {**ENV, "LLM_RUN_MODE": "live", "LLM_LOG_SINK": "db", "LLM_RUN_MAX_USD": "0.3"}
    texts: list[str] = []
    for env in (
        {**live, "LLM_RUN_MODE": key, "LLM_OPENAI_API_KEY": key},  # 모드 자리에 키를 잘못 넣음
        {**live, "LLM_RUN_MAX_USD": key, "LLM_OPENAI_API_KEY": key},  # 상한 자리에 키
        {**live, "LLM_LOG_SINK": "memory", "LLM_ANTHROPIC_API_KEY": key},  # 조건 실패(키는 있음)
        {**live, "LLM_LOG_SINK": key, "LLM_GEMINI_API_KEY": key},  # 싱크 자리에 키
    ):
        with pytest.raises(ConfigError) as caught:
            load_config(env)
        texts.append(str(caught.value))
    config = load_config({**live, "LLM_OPENAI_API_KEY": key, "LLM_ANTHROPIC_API_KEY": key, "LLM_GEMINI_API_KEY": key})
    assert config.llm.openai_api_key == key  # 분모: 키는 설정에 있다
    texts += [
        repr(config),
        repr(config.llm),
        str(config.llm),
        run_mode_notice(config.llm) or "",
        capsys.readouterr().err,
    ]
    assert "llm_run_mode mode=live" in texts[-1]  # 분모: 기동 줄은 찍혔다
    assert found(texts) == []
    assert found([repr(LlmSettings(openai_api_key=key, run_mode="live"))]) == []


# ── 실행: 공급사가 키를 되돌린 실패 ─────────────────────────────────────


def operator_access(client: Client) -> str:
    """운영 관리자 하나(명령 create_user — runs 시험은 user 를 import 않음, 계약 차)의 access."""
    call_command("create_user", "--admin", "--username", "ops", "--name", "운영자", "--password-stdin",
                 stdin=StringIO(PASSWORD + "\n"), stdout=StringIO())  # fmt: skip
    first = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)
    changed = client.post(
        "/api/users/me/password",
        data={"currentPassword": PASSWORD, "newPassword": CHANGED},
        content_type="application/json",
        **bearer(first["access"]),
    )
    assert changed.status_code == 200, changed.content.decode()
    return str(changed.json()["access"])


def echo(key: str) -> dict[str, Any]:
    """키를 몸에 그대로 되돌리는 공급사의 오류(가장 나쁜 꼴 — 실제 OpenAI 는 가린 꼴로 되돌린다)."""
    return {"error": {"message": f"Incorrect API key provided: {key}", "type": "invalid_request_error", "code": key}}


def raise_like_the_modules(adapters: ProbeAdapters, world: World) -> None:
    """대화가 성공하지 못하면 kind 만 실어 던진다(greenwash/tools/llm_bridge.py 의 꼴) → 단계 step_error."""
    result = chat(adapters, world)
    if result.kind != "success":
        raise RuntimeError(f"대화 호출이 성공하지 못했다: {result.kind}")


def rows_text(world: World) -> list[str]:
    company = world.company_id
    return [
        str(values)
        for query in (
            RunRow.for_company(company).values(),
            RunStepRow.for_company(company).values(),
            AuditEventRow.for_company(company).values(),
            LlmCallLogRow.for_company(company).values(),
        )
        for values in query
    ]


@pytest.mark.parametrize("key", [SK, PLAIN])
def test_a_live_run_whose_provider_echoes_the_key_leaves_no_key(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeOpenAI,
    caplog: pytest.LogCaptureFixture,
    client: Client,
    key: str,
) -> None:
    caplog.set_level(logging.DEBUG)
    use(monkeypatch, world, live_settings(openai_api_key=key, anthropic_api_key=PLAIN, gemini_api_key=SK))
    fake.chat = status(401, body=echo(key))
    fake.embed = status(401, body=echo(key))

    # 실행 A: 대화 401(키를 되돌림) → 단계 step_error / 실행 B: 임베딩 401 → embedding_failed
    def chat_first(i: int, adapters: ProbeAdapters) -> None:
        if i == 0:
            raise_like_the_modules(adapters, world)

    def embed_first(i: int, adapters: ProbeAdapters) -> None:
        if i == 0:
            embed(adapters, world)

    world.script.before_item = chat_first
    chat_run = new_run(world)
    execute(world, chat_run)
    world.script.before_item = embed_first
    embed_run = new_run(world)
    execute(world, embed_run)
    # 분모: 키가 실행기를 지나 공급사에 닿았고, 공급사가 몸에 되돌렸고, 실행은 실패로 끝났다
    assert {r.headers["authorization"] for r in fake.seen} == {f"Bearer {key}"}
    assert all(key in r.decode() for r in [fake_reply_bytes(key)])
    assert (row(world, chat_run).error_code, row(world, embed_run).error_code) == ("step_error", "embedding_failed")
    assert LlmCallLogRow.for_company(world.company_id).count() == 2
    # 겉 응답(운영 관리자)
    access = operator_access(client)
    company = world.company_id
    responses = [
        client.get(f"/api/run-logs/{run_id}?companyId={company}", **bearer(access)) for run_id in (chat_run, embed_run)
    ] + [
        client.get(f"/api/run-logs/metrics?companyId={company}", **bearer(access)),
        client.get(f"/api/run-logs?companyId={company}", **bearer(access)),
        client.get("/api/openapi.json"),
    ]
    assert [r.status_code for r in responses] == [200] * 5
    texts = rows_text(world) + [r.content.decode() for r in responses]
    texts += [r.getMessage() for r in caplog.records] + [caplog.text]
    assert len(caplog.records) >= 1  # 분모: 실패 기록이 남았다(run_step_failed 등)
    assert found(texts) == []


def fake_reply_bytes(key: str) -> bytes:
    """가짜 공급사가 되돌리는 몸의 바이트(분모 — 몸에 키가 실려 있다)."""
    return str(echo(key)).encode()
