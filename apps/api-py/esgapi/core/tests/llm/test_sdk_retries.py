# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""SDK 숨은 재시도 0 과 호출 층 재시도(밴드 LH1 S1~S4 — MARC-ISSUE-306 m2). 순수 층.

  S1 SDK 0       만든 클라이언트의 max_retries(채팅 0·0, 임베딩 2) · 가짜 HTTP 429 → SDK 요청 1(openai·anthropic)
  S2 호출 층     openai·anthropic 이름의 모의 공급사 429 둘 뒤 성공 → 기록 줄 3·provider_retry None,1,2 · 시도마다
                 상한 확인(둘째 대기 뒤 상한이 차면 budget_exceeded 줄·공급사 호출 2) · 진짜 openai SDK + 가짜 HTTP
                 도 같은 꼴
  S3 retry-after 머리 `retry-after-ms`(ms)·`retry-after`(초)를 오류의 retry_after_ms 로 · 날짜 꼴은 None(기본 대기) ·
                 상한(60초) 넘는 요구는 다시 안 부름 · 진짜 SDK 로 대기 2000
  S4 시간 초과   openai 시간 초과 → 같은 모델 다시 0, 대체 모델로
★ 네트워크 0: 진짜 SDK 객체를 쓰는 시험은 소켓 연결·이름 풀기를 막는 고정물(no_network — runs/tests/test_context_live.py
  의 꼴)을 지나고, 시도가 있으면 빨개진다. 가짜 HTTP 는 httpx(openai)·httpx2(anthropic — legacy httpx 클라이언트를
  거부한다)의 MockTransport. 키는 지어낸 글자다.
"""

import socket
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import anthropic
import httpx
import httpx2
import openai
import pytest

from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.providers.anthropic import AnthropicProvider, create_anthropic_client
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.openai import OpenAIProvider, create_openai_client, create_openai_embedding_client
from esgapi.core.llm.types import ProviderError, ProviderTimeout, Scope, Success
from esgapi.core.tests.llm_support import TAGS, harness, synthetic_config
from esgapi.core.tests.test_llm_adapters import OPTIONS, PLAIN, FakeAnthropic, FakeOpenAI

SK = "sk-LH1-synthetic"
BASE = CallRequest(prompt="t/plain@1", vars={"question": "분류해 줘"}, route="light-openai", tags=TAGS)
HTTP_REQUEST = httpx2.Request("POST", "https://provider.invalid/v1")


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    """소켓 연결·이름 풀기를 막고 시도를 센다. 끝에 0 이어야 한다."""
    tried: list[object] = []

    def refuse(*args: object, **kwargs: object) -> Any:
        tried.append(args[1:] if args else kwargs)
        raise OSError("LH1 시험: 바깥 연결 금지")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    yield tried
    assert tried == [], f"바깥 연결 시도 {len(tried)}"


# ── 가짜 HTTP ───────────────────────────────────────────────────────


def responses_body() -> dict[str, Any]:
    return {
        "id": "resp_synthetic",
        "object": "response",
        "created_at": 0,
        "model": "model-synthetic",
        "status": "completed",
        "incomplete_details": None,
        "output": [
            {
                "type": "message",
                "id": "msg_synthetic",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "지어낸 답", "annotations": []}],
            }
        ],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "usage": {
            "input_tokens": 10,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 5,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 15,
        },
    }


Reply = Callable[[int], tuple[int, dict[str, str]] | None]  # 몇 번째 요청(0부터) → (상태, 머리) · None 이면 200


def always_429(_: int) -> tuple[int, dict[str, str]]:
    return 429, {"retry-after-ms": "1"}


ALWAYS_429: Reply = always_429


class Server:
    def __init__(self, reply: Reply) -> None:
        self.reply = reply
        self.seen = 0

    def openai(self, request: httpx.Request) -> httpx.Response:
        got = self.reply(self._next())
        if got is not None:
            return httpx.Response(got[0], headers=got[1], json={"error": {"message": "synthetic", "type": "synthetic"}})
        return httpx.Response(200, json=responses_body())

    def anthropic(self, request: httpx2.Request) -> httpx2.Response:
        got = self.reply(self._next())
        assert got is not None, "anthropic 의 성공 응답(SSE)은 이 시험이 짓지 않는다"
        body = {"type": "error", "error": {"type": "rate_limit_error", "message": "synthetic"}}
        return httpx2.Response(got[0], headers=got[1], json=body)

    def _next(self) -> int:
        self.seen += 1
        return self.seen - 1


def fake_openai_http(monkeypatch: pytest.MonkeyPatch, server: Server) -> None:
    """openai.OpenAI 를 가짜 HTTP 를 단 진짜 SDK 클라이언트로(만드는 인자 — max_retries 포함 — 는 그대로)."""
    real = openai.OpenAI

    def build(**kwargs: Any) -> openai.OpenAI:
        return real(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(server.openai)))  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(openai, "OpenAI", build)


def fake_anthropic_http(monkeypatch: pytest.MonkeyPatch, server: Server) -> None:
    real = anthropic.Anthropic

    def build(**kwargs: Any) -> anthropic.Anthropic:
        return real(**kwargs, http_client=httpx2.Client(transport=httpx2.MockTransport(server.anthropic)))

    monkeypatch.setattr(anthropic, "Anthropic", build)


# ── S1 SDK 0 ─────────────────────────────────────────────────────────


def test_chat_and_embedding_clients_turn_sdk_retries_off() -> None:
    """임베딩도 0(LB1 Q5 — 호출 층이 다시 부른다)."""
    made: list[Any] = [create_openai_client(SK), create_anthropic_client(SK), create_openai_embedding_client(SK)]
    assert [client.max_retries for client in made] == [0, 0, 0]


def test_openai_sdk_sends_one_request_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    server = Server(ALWAYS_429)
    fake_openai_http(monkeypatch, server)
    result = OpenAIProvider(create_openai_client(SK)).invoke(PLAIN, OPTIONS)
    assert isinstance(result, ProviderError) and (result.status, result.retryable) == (429, True)
    assert server.seen == 1


def test_anthropic_sdk_sends_one_request_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    server = Server(ALWAYS_429)
    fake_anthropic_http(monkeypatch, server)
    result = AnthropicProvider(create_anthropic_client(SK)).invoke(PLAIN, OPTIONS)
    assert isinstance(result, ProviderError) and (result.status, result.retryable) == (429, True)
    assert server.seen == 1


# ── S2 호출 층 재시도 ───────────────────────────────────────────────────


LIMITED = ProviderError(status=429, retryable=True, message="모의 한도")


@pytest.mark.parametrize(("name", "route"), [("openai", "light-openai"), ("anthropic", "light-anthropic")])
def test_the_call_layer_retries_twice_and_logs_every_attempt(prompt_root: Path, name: str, route: str) -> None:
    provider = MockProvider(name).enqueue(LIMITED).enqueue(LIMITED).enqueue_text("ok")
    h = harness(prompt_root, providers={name: provider})
    result = h.client.call(replace(BASE, route=route))
    assert isinstance(result, Success)
    assert len(provider.calls) == 3
    assert [(r.result_kind, r.provider_retry) for r in h.log.records] == [
        ("provider_error", None),
        ("provider_error", 1),
        ("success", 2),
    ]
    assert h.sleeps == [1000, 2000]


@pytest.mark.parametrize(("name", "route"), [("openai", "light-openai"), ("anthropic", "light-anthropic")])
def test_the_limit_is_checked_before_every_retry(prompt_root: Path, name: str, route: str) -> None:
    """둘째 대기 동안 다른 호출이 상한을 채우면 셋째는 공급사 전에 막힌다(줄 3: 오류·오류·budget_exceeded, 호출 2)."""
    provider = MockProvider(name).enqueue(LIMITED).enqueue(LIMITED).enqueue_text("ok")
    limits = [BudgetLimit(scope=Scope(tenant=TAGS.tenant), limit_usd=0.0001)]
    waits: list[float] = []

    def sleep(ms: float) -> None:
        waits.append(ms)
        if len(waits) == 2:
            h.log.add_spent(TAGS, 0.0002)

    h = harness(prompt_root, providers={name: provider}, limits=limits, sleep=sleep)
    assert h.client.call(replace(BASE, route=route)).kind == "budget_exceeded"
    assert len(provider.calls) == 2
    assert [r.result_kind for r in h.log.records] == ["provider_error", "provider_error", "budget_exceeded"]


def test_real_openai_sdk_429_twice_then_200_is_three_requests_and_three_lines(
    prompt_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = Server(lambda n: (429, {"retry-after-ms": "1"}) if n < 2 else None)
    fake_openai_http(monkeypatch, server)
    h = harness(prompt_root, providers={"openai": OpenAIProvider(create_openai_client(SK))})
    assert isinstance(h.client.call(BASE), Success)
    assert server.seen == 3
    assert [(r.result_kind, r.provider_retry, r.retry_after_ms) for r in h.log.records] == [
        ("provider_error", None, 1.0),
        ("provider_error", 1, 1.0),
        ("success", 2, None),
    ]
    assert h.sleeps == [1.0, 1.0]


# ── S3 retry-after ──────────────────────────────────────────────────


def status_error(sdk: Any, status: int, headers: dict[str, str]) -> Exception:
    response = httpx2.Response(status, headers=headers, request=HTTP_REQUEST)
    return sdk.APIStatusError("synthetic", response=response, body=None)


HEADER_CASES = [
    pytest.param(429, {"retry-after-ms": "5"}, 5.0, id="ms"),
    pytest.param(429, {"retry-after": "2"}, 2000.0, id="seconds"),
    pytest.param(503, {"retry-after-ms": "5", "retry-after": "2"}, 5.0, id="ms-wins"),
    # 지난 HTTP 날짜는 0(LB1 — 날짜 꼴을 읽는다. 미래·못 읽음은 test_retry_wait 의 고정 시계 시험).
    pytest.param(429, {"retry-after": "Wed, 28 Oct 2026 07:28:00 GMT"}, 0, id="http-date-past"),
    pytest.param(429, {}, None, id="none"),
    pytest.param(400, {"retry-after-ms": "5"}, None, id="not-retryable"),
]


@pytest.mark.parametrize(("status", "headers", "want"), HEADER_CASES)
def test_openai_reads_retry_after_headers(status: int, headers: dict[str, str], want: float | None) -> None:
    result = OpenAIProvider(FakeOpenAI(status_error(openai, status, headers))).invoke(PLAIN, OPTIONS)
    assert isinstance(result, ProviderError) and result.retry_after_ms == want


@pytest.mark.parametrize(("status", "headers", "want"), HEADER_CASES)
def test_anthropic_reads_retry_after_headers(status: int, headers: dict[str, str], want: float | None) -> None:
    result = AnthropicProvider(FakeAnthropic(status_error(anthropic, status, headers))).invoke(PLAIN, OPTIONS)
    assert isinstance(result, ProviderError) and result.retry_after_ms == want


def test_a_wait_over_the_cap_is_not_retried_and_a_date_falls_back_to_the_default(prompt_root: Path) -> None:
    over = MockProvider("openai").enqueue(replace(LIMITED, retry_after_ms=61_000)).enqueue_text("ok")
    h = harness(prompt_root, providers={"openai": over})
    assert h.client.call(BASE).kind == "provider_error"
    assert (len(over.calls), h.sleeps) == (1, [])
    dated = MockProvider("openai").enqueue(replace(LIMITED, retry_after_ms=None)).enqueue_text("ok")
    h = harness(prompt_root, providers={"openai": dated})
    assert isinstance(h.client.call(BASE), Success)
    assert h.sleeps == [1000]


def test_real_openai_sdk_retry_after_seconds_becomes_the_call_layer_wait(
    prompt_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = Server(lambda n: (429, {"retry-after": "2"}) if n < 1 else None)
    fake_openai_http(monkeypatch, server)
    h = harness(prompt_root, providers={"openai": OpenAIProvider(create_openai_client(SK))})
    assert isinstance(h.client.call(BASE), Success)
    assert (server.seen, h.sleeps) == (2, [2000.0])


# ── S4 시간 초과 ─────────────────────────────────────────────────────


def test_an_openai_timeout_is_not_retried_on_the_same_model_but_falls_back(
    prompt_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        server.seen += 1
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    server = Server(ALWAYS_429)
    real = openai.OpenAI

    def build(**kwargs: Any) -> openai.OpenAI:
        return real(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(timeout)))  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(openai, "OpenAI", build)
    config = synthetic_config()
    config = replace(config, routes={**config.routes, "openai-then-mock": ("gpt-4.1-mini", "mock-synthetic")})
    mock = MockProvider().enqueue_text("ok")
    h = harness(
        prompt_root, config=config, providers={"openai": OpenAIProvider(create_openai_client(SK)), "mock": mock}
    )
    result = h.client.call(replace(BASE, route="openai-then-mock"))
    assert isinstance(result, Success)
    assert server.seen == 1
    assert [(r.provider, r.result_kind) for r in h.log.records] == [("openai", "timeout"), ("mock", "success")]
    assert h.sleeps == []
    assert isinstance(OpenAIProvider(create_openai_client(SK)).invoke(PLAIN, OPTIONS), ProviderTimeout)
    assert server.seen == 2
