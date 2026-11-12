# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실행기의 실제 공급사 켜기(LV1 — runs/context.py 의 LLM_RUN_MODE). 업무 층: 실행기(test_executor.py 의 가짜 흐름
`probe.three@1`·저장소 가짜·태스크 직접 부름)를 빌려 쓰고, OpenAI SDK 의 HTTP 만 가짜(httpx.MockTransport)로 바꾼다.

재는 것:
  mock(기본)  키가 있어도 mock=True·키 None·상한 () · 실행의 결과·단계·기록 줄이 키 없는 때와 같다
  live        mock=False·키 실림·모의 경로 없음·상한 하나(LLM_RUN_MAX_USD) · 가짜 HTTP 끝까지(대화 light-openai-41 +
              임베딩 light-openai → done · 요청 경로·Bearer·몸 · 기록 줄의 공급사·모델·토큰·비용 = 단가 손셈 ·
              run_id·step)
  오류 갈래   (LH1 B1) 대화는 HTTP 시도마다 기록 줄 하나(SDK 재시도 0·호출 층 재시도) · 임베딩은 BASE 그대로 —
              429 두 번 뒤 200 · 429 계속 · 500 · 401 · 시간 초과 × 대화·임베딩
  상한        한 번보다 작은 상한 → 둘째가 공급사 전 budget_exceeded · 같은 실행의 앞 시도 줄(시드) · 대화와 임베딩이 한
              몫을 나눔 · 시드는 한 번만 읽음 · mock 은 같은 상한이어도 막지 않음
  영문번역    TR3a(경로 상수 openai) 앞이라 「꽂히는 자리」만: live 문맥의 클라이언트에 지금 경로(light-anthropic 등)는
              Anthropic 키가 없어 LiveSetupError, OpenAI 경로는 같은 클라이언트로 가짜 HTTP 에 닿는다
★ 네트워크 0: 소켓 연결·이름 풀기를 막는 고정물(no_network)이 모든 시험에 걸리고, 시도가 있으면 시험이 빨개진다.
★ 키는 지어낸 글자다. 가짜 HTTP 의 Authorization 머리만 키가 보이는 자리다.
★ 대화 SDK 의 재시도는 0, 호출 층이 다시 부른다(기다림은 가짜 응답의 retry-after-ms 1ms 를 호출 층이 따른다). 시간
  초과는 같은 모델을 다시 부르지 않는다. 임베딩 SDK 는 재시도 2(명시) — 물러섬은 SDK 의 것 그대로.
"""

import json
import socket
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from esgapi.config.env import LlmSettings
from esgapi.core.llm.client import CallRequest, LlmResult
from esgapi.core.llm.embedding import ClientEmbeddingPort, EmbeddingFailed
from esgapi.core.llm.errors import LiveSetupError
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.sink_db import DbSink
from esgapi.core.llm.types import Tags
from esgapi.core.models import LlmCallLogRow
from esgapi.runs import context
from esgapi.runs.tests import test_executor
from esgapi.runs.tests.test_executor import ProbeAdapters, World, execute, new_run, row

pytestmark = pytest.mark.django_db

SK = "sk-proj-LV1SENTINEL" + "k" * 24  # 지어낸 키(가림 꼴 안)
CHAT_ROUTE = "light-openai-41"  # gpt-4.1-mini (models.json — MARC-ENT-249)
EMBED_ROUTE = "light-openai"  # text-embedding-3-small
DIMENSIONS = 1536
# 가짜 응답의 사용량과 models.json 단가(USD/MTok — gpt-4.1-mini 입력 0.40·출력 1.60, text-embedding-3-small 0.02)로 손셈
CHAT_IN, CHAT_OUT, EMBED_IN = 1000, 200, 500
CHAT_USD = (CHAT_IN * 0.40 + CHAT_OUT * 1.60) / 1_000_000  # 0.00072
EMBED_USD = EMBED_IN * 0.02 / 1_000_000  # 0.00001


executor_world = test_executor.world  # 픽스처(이 이름으로 선다) — 아래 world 가 받는다


@pytest.fixture
def world(executor_world: World) -> World:
    """test_executor.py 의 실행기 세계(가짜 흐름·저장소 가짜·태스크 이음매)를 그대로."""
    return executor_world


# ── 네트워크 0 ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    """소켓 연결·이름 풀기를 막고 시도를 센다. 끝에 0 이어야 한다(DB 는 libpq 의 C 소켓이라 걸리지 않는다)."""
    tried: list[object] = []

    def refuse(*args: object, **kwargs: object) -> Any:
        tried.append(args[1:] if args else kwargs)
        raise OSError("LV1 시험: 바깥 연결 금지")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    yield tried
    assert tried == [], f"바깥 연결 시도 {len(tried)}"


def test_the_guard_catches_a_real_connection(no_network: list[object]) -> None:
    """분모: 고정물이 실제 SDK 의 연결 시도를 잡는다(가짜 HTTP 없이 지은 클라이언트 — 재시도 0)."""
    client = openai.OpenAI(api_key=SK, max_retries=0, base_url="https://api.openai.com/v1")
    with pytest.raises(openai.APIConnectionError):
        client.embeddings.create(model="text-embedding-3-small", input=["x"])
    assert len(no_network) >= 1
    no_network.clear()


# ── 가짜 OpenAI(HTTP) ───────────────────────────────────────────────


def responses_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": "resp_synthetic",
        "object": "response",
        "created_at": 0,
        "model": "gpt-4.1-mini-2025-04-14",
        "status": "completed",
        "incomplete_details": None,
        "output": [
            {
                "type": "message",
                "id": "msg_synthetic",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "지어낸 판정", "annotations": []}],
            }
        ],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "usage": {
            "input_tokens": CHAT_IN,
            "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
            "output_tokens": CHAT_OUT,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": CHAT_IN + CHAT_OUT,
        },
    }
    return body | overrides


def embeddings_body(count: int) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": [0.001 * (i + 1)] * DIMENSIONS} for i in range(count)
        ],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": EMBED_IN, "total_tokens": EMBED_IN},
    }


Reply = Callable[[httpx.Request, int], httpx.Response]  # (요청, 그 경로의 몇 번째(0부터)) → 응답(예외를 던져도 된다)


def ok(request: httpx.Request, _: int) -> httpx.Response:
    if request.url.path.endswith("/embeddings"):
        return httpx.Response(200, json=embeddings_body(len(json.loads(request.content)["input"])))
    return httpx.Response(200, json=responses_body())


def status(code: int, *, times: int | None = None, body: dict[str, Any] | None = None) -> Reply:
    """처음 times 번(None 이면 늘) code 로 답하고 그 뒤는 ok. retry-after-ms 1 — SDK 의 기다림을 짧게."""

    def reply(request: httpx.Request, n: int) -> httpx.Response:
        if times is not None and n >= times:
            return ok(request, n)
        payload = body if body is not None else {"error": {"message": f"synthetic {code}", "type": "synthetic"}}
        return httpx.Response(code, headers={"retry-after-ms": "1"}, json=payload)

    return reply


def timeout(request: httpx.Request, _: int) -> httpx.Response:
    raise httpx.ReadTimeout("synthetic timeout", request=request)


@dataclass
class FakeOpenAI:
    """가짜 HTTP 의 답(경로마다)과 받은 요청."""

    chat: Reply = ok
    embed: Reply = ok
    seen: list[httpx.Request] = field(default_factory=list[httpx.Request])

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        embeds = request.url.path.endswith("/embeddings")
        n = sum(1 for r in self.seen if r.url.path == request.url.path) - 1
        return (self.embed if embeds else self.chat)(request, n)

    def paths(self) -> list[str]:
        return [r.url.path for r in self.seen]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeOpenAI:
    """openai.OpenAI 를 가짜 HTTP 를 단 진짜 SDK 클라이언트로 갈아 끼운다(어댑터·SDK·재시도는 진짜)."""
    server = FakeOpenAI()
    real = openai.OpenAI

    def build(**kwargs: Any) -> openai.OpenAI:
        # SDK 3.26 의 기본 전송은 httpx2 다. 시험은 SDK 가 받는 legacy httpx 클라이언트 길로 탄다(새 의존 0 — 보고)
        transport = httpx.MockTransport(server.handle)
        return real(**kwargs, http_client=httpx.Client(transport=transport))  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(openai, "OpenAI", build)
    return server


def live_settings(**overrides: Any) -> LlmSettings:
    values: dict[str, Any] = {"openai_api_key": SK, "log_sink": "db", "run_mode": "live", "run_max_usd": 5.0}
    return LlmSettings(**(values | overrides))


def use(monkeypatch: pytest.MonkeyPatch, world: World, settings: LlmSettings) -> None:
    """이 프로세스의 설정을 settings 로(context.app_config 이음매), 바닥 싱크는 DB."""
    monkeypatch.setattr(context, "app_config", lambda: SimpleNamespace(llm=settings))
    world.sink = DbSink()


def tags(world: World) -> Tags:
    return Tags(str(world.company_id), "probe")


def chat(adapters: ProbeAdapters, world: World, route: str = CHAT_ROUTE) -> LlmResult[str]:
    return adapters.ctx.llm().call(
        CallRequest(prompt="core/hello@1", vars={"name": "김"}, route=route, tags=tags(world))
    )


def embed(adapters: ProbeAdapters, world: World) -> list[list[float]]:
    port = ClientEmbeddingPort(adapters.ctx.embedding(), route=EMBED_ROUTE, tags=tags(world))
    return port.embed_documents(["지어낸 문장 하나", "지어낸 문장 둘"])


def at_first_item(world: World, act: Callable[[ProbeAdapters], object]) -> list[Any]:
    """judge 의 첫 항목 전에 act 를 한 번(그 시도의 단계 judge 안). 돌려준 것을 모은다."""
    got: list[Any] = []

    def hook(i: int, adapters: ProbeAdapters) -> None:
        if i == 0:
            got.append(act(adapters))

    world.script.before_item = hook
    return got


def lines(world: World, run_id: int) -> list[LlmCallLogRow]:
    return list(LlmCallLogRow.for_company(world.company_id).filter(run_id=run_id).order_by("id"))


# ── mock(기본) ─────────────────────────────────────────────────────


def spy_builds(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    asked: list[dict[str, Any]] = []
    for name in ("build_client", "build_embedding_client"):
        real = getattr(context, name)

        def spy(settings: LlmSettings, _real: Any = real, _name: str = name, **kwargs: Any) -> Any:
            asked.append({"name": _name, "settings": settings, **kwargs})
            return _real(settings, **kwargs)

        monkeypatch.setattr(context, name, spy)
    return asked


@pytest.mark.parametrize("max_usd", [5.0, 0.000001])
def test_mock_carries_no_key_and_no_limit_even_with_keys(
    world: World, monkeypatch: pytest.MonkeyPatch, max_usd: float
) -> None:
    """mock 은 키가 있어도 비우고 mock=True·상한 () — 대화·임베딩 둘 다(P10 의 짝, 상한이 아주 작아도)."""
    settings = live_settings(run_mode="mock", run_max_usd=max_usd, anthropic_api_key=SK, gemini_api_key=SK)
    use(monkeypatch, world, settings)
    asked = spy_builds(monkeypatch)
    ctx = context.ExecutorContext(
        company_id=world.company_id,
        run_id=1,
        module="probe",
        flow_id="f",
        attempt=1,
        sink=context.RunCallSink(world.sink, 1),
    )
    ctx.llm()
    ctx.embedding()
    assert [a["name"] for a in asked] == ["build_client", "build_embedding_client"]
    for a in asked:
        keys = (a["settings"].openai_api_key, a["settings"].anthropic_api_key, a["settings"].gemini_api_key)
        assert (a["mock"], keys, a["limits"]) == (True, (None, None, None), ())


def run_mock_world(
    world: World, monkeypatch: pytest.MonkeyPatch, settings: LlmSettings, *, seed: str | None = None
) -> dict[str, Any]:
    """모의 경로 대화 한 번을 하는 실행 하나 → 실행·단계·기록 줄(id·시각 뺌). seed = 그 실행의 앞 시도 줄."""
    use(monkeypatch, world, settings)

    def act(adapters: ProbeAdapters) -> object:
        client = adapters.ctx.llm()
        mock = client.provider("mock")
        assert isinstance(mock, MockProvider)
        mock.enqueue_text("판정")
        return client.call(CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=tags(world)))

    at_first_item(world, act)
    run_id = new_run(world)
    if seed is not None:
        seeded(world, run_id, seed)
    execute(world, run_id)
    run = row(world, run_id)
    return {
        "run": (run.status, run.error_code, run.error_message, run.failed_step, run.attempts),
        "lines": [
            (r.provider, r.model, r.api_model_id, r.input_tokens, r.output_tokens, r.cost_usd, r.result_kind, r.step)
            for r in lines(world, run_id)
        ],
    }


def test_mock_with_keys_runs_exactly_like_mock_without_keys(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    without = run_mock_world(world, monkeypatch, LlmSettings(log_sink="db"))
    with_keys = run_mock_world(world, monkeypatch, live_settings(run_mode="mock", anthropic_api_key=SK))
    assert without["run"][0] == "done"
    assert len(without["lines"]) == 1  # 분모
    assert with_keys == without


def test_mock_does_not_reach_a_real_route(world: World, monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAI) -> None:
    """mock 에서 실제 경로를 부르면 키가 없어 LiveSetupError → 단계 setup_error(BASE 그대로). 가짜 HTTP 요청 0."""
    use(monkeypatch, world, live_settings(run_mode="mock"))
    at_first_item(world, lambda adapters: chat(adapters, world))
    run_id = new_run(world)
    execute(world, run_id)
    assert (row(world, run_id).status, row(world, run_id).error_code) == ("failed", "setup_error")
    assert fake.seen == []


# ── live ──────────────────────────────────────────────────────────


def test_live_carries_the_keys_with_one_run_limit_and_no_mock_route(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    use(monkeypatch, world, live_settings(run_max_usd=0.3))
    asked = spy_builds(monkeypatch)
    ctx = context.ExecutorContext(
        company_id=world.company_id,
        run_id=1,
        module="probe",
        flow_id="f",
        attempt=1,
        sink=context.RunCallSink(world.sink, 1),
    )
    client = ctx.llm()
    ctx.embedding()
    for a in asked:
        assert (a["mock"], a["settings"].openai_api_key == SK, a["sink"] is ctx.sink) == (False, True, True)
        (limit,) = a["limits"]
        assert (limit.scope.tenant, limit.scope.module, limit.limit_usd) == (None, None, 0.3)
    assert client.provider("mock") is None
    assert isinstance(client.provider("openai"), OpenAIProvider)


def test_live_goes_through_the_fake_http_to_done(
    world: World, monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAI
) -> None:
    use(monkeypatch, world, live_settings())
    got = at_first_item(world, lambda adapters: (chat(adapters, world), embed(adapters, world)))
    run_id = new_run(world)
    execute(world, run_id)
    assert row(world, run_id).status == "done"
    (result, vectors), *_ = got
    assert (result.kind, len(vectors), len(vectors[0])) == ("success", 2, DIMENSIONS)
    # 요청: 경로·키(가짜 HTTP 의 머리만)·몸
    assert fake.paths() == ["/v1/responses", "/v1/embeddings"]
    assert {r.headers["authorization"] for r in fake.seen} == {f"Bearer {SK}"}
    sent_chat, sent_embed = (json.loads(r.content) for r in fake.seen)
    assert (sent_chat["model"], sent_chat["store"]) == ("gpt-4.1-mini", False)
    assert (sent_embed["model"], sent_embed["input"], sent_embed["encoding_format"]) == (
        "text-embedding-3-small",
        ["지어낸 문장 하나", "지어낸 문장 둘"],
        "float",
    )
    # 기록 줄: 공급사·모델·응답 모델·토큰·비용(손셈)·run_id·step
    got_lines = [
        (r.provider, r.api_model_id, r.response_model_id, r.input_tokens, r.output_tokens, r.cost_usd, r.result_kind)
        for r in lines(world, run_id)
    ]
    assert got_lines == [
        ("openai", "gpt-4.1-mini", "gpt-4.1-mini-2025-04-14", CHAT_IN, CHAT_OUT, Decimal(str(CHAT_USD)), "success"),
        (
            "openai",
            "text-embedding-3-small",
            "text-embedding-3-small",
            EMBED_IN,
            0,
            Decimal(str(EMBED_USD)),
            "success",
        ),
    ]
    assert {(r.run_id, r.step) for r in lines(world, run_id)} == {(run_id, "judge")}


# ── 오류 갈래(대화 LH1 B1 · 임베딩 BASE 그대로) ─────────────────────────


Line = tuple[str, int | None, int | None]  # 기록 줄의 (result_kind, error_status, provider_retry)
# 429(한도 초과)는 대기 예산 갈래(LB1 — core/llm/retry.py): retry-after-ms 1 이 이어지면 천장 8 까지 — 줄 9.
FAILED_429: list[Line] = [("provider_error", 429, None), *(("provider_error", 429, n) for n in range(1, 9))]
FAILED_500: list[Line] = [("provider_error", 500, None), ("provider_error", 500, 1), ("provider_error", 500, 2)]


@pytest.mark.parametrize(
    ("reply", "kind", "error_status", "retryable", "requests", "want_lines"),
    [
        pytest.param(
            status(429, times=2),
            "success",
            None,
            None,
            3,
            [("provider_error", 429, None), ("provider_error", 429, 1), ("success", None, 2)],
            id="429-twice-then-200",
        ),
        pytest.param(status(429), "provider_error", 429, True, 9, FAILED_429, id="429-always"),
        pytest.param(status(500), "provider_error", 500, True, 3, FAILED_500, id="500-always"),
        pytest.param(status(401), "provider_error", 401, False, 1, [("provider_error", 401, None)], id="401"),
        pytest.param(timeout, "timeout", None, None, 1, [("timeout", None, None)], id="timeout"),
    ],
)
def test_chat_failures_are_recorded_and_left_to_the_module(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeOpenAI,
    reply: Reply,
    kind: str,
    error_status: int | None,
    retryable: bool | None,
    requests: int,
    want_lines: list[Line],
) -> None:
    """대화의 실패는 결과 갈래로 돌아온다(단계가 정함 — 이 흐름은 계속해 done). HTTP 시도마다 기록 줄 하나
    (provider_retry 차례) — 요청 수 = 줄 수."""
    use(monkeypatch, world, live_settings())
    fake.chat = reply
    got = at_first_item(world, lambda adapters: chat(adapters, world))
    run_id = new_run(world)
    execute(world, run_id)
    (result,) = got
    assert result.kind == kind
    if kind == "provider_error":
        assert (result.status, result.retryable) == (error_status, retryable)
    assert len(fake.seen) == requests
    got_lines = lines(world, run_id)
    assert [(r.result_kind, r.error_status, r.provider_retry) for r in got_lines] == want_lines
    assert [r.cost_usd for r in got_lines] == [
        Decimal(str(CHAT_USD)) if r.result_kind == "success" else None for r in got_lines
    ]
    assert row(world, run_id).status == "done"


@pytest.mark.parametrize(
    ("reply", "status_after", "code", "deferred", "want_lines"),
    [
        # 임베딩도 호출 층이 다시 부른다(LB1): 429 는 대기 예산 갈래 천장 8(줄 9), 500 은 횟수 갈래 2(줄 3).
        pytest.param(status(429), "queued", None, True, 9, id="429-always-defers"),
        pytest.param(status(500), "queued", None, True, 3, id="500-always-defers"),
        pytest.param(timeout, "queued", None, True, 1, id="timeout-defers"),
        pytest.param(status(401), "failed", "embedding_failed", False, 1, id="401-fails"),
    ],
)
def test_embedding_failures_end_the_attempt_like_base(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeOpenAI,
    reply: Reply,
    status_after: str,
    code: str | None,
    deferred: bool,
    want_lines: int,
) -> None:
    """임베딩의 재시도 가능한 실패는 실행을 미룬다(RunDeferred — queued·다시 넣기 청 하나), 401 은 embedding_failed."""
    use(monkeypatch, world, live_settings())
    fake.embed = reply
    at_first_item(world, lambda adapters: embed(adapters, world))
    run_id = new_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.error_code, len(world.retries)) == (status_after, code, 1 if deferred else 0)
    assert len(lines(world, run_id)) == want_lines


# ── 상한(실행 하나의 누적) ────────────────────────────────────────────


def test_a_limit_below_one_call_stops_the_second_before_the_provider(
    world: World, monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAI
) -> None:
    use(monkeypatch, world, live_settings(run_max_usd=CHAT_USD / 2))
    got = at_first_item(world, lambda adapters: (chat(adapters, world), chat(adapters, world)))
    run_id = new_run(world)
    execute(world, run_id)
    (first, second), *_ = got
    assert (first.kind, second.kind) == ("success", "budget_exceeded")
    assert second.spent_usd == CHAT_USD
    assert fake.paths() == ["/v1/responses"]  # 둘째는 공급사에 가지 않았다
    assert [r.result_kind for r in lines(world, run_id)] == ["success", "budget_exceeded"]


def test_an_earlier_attempt_of_the_same_run_counts_from_the_first_call(
    world: World, monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAI
) -> None:
    """시드: DB 에 같은 실행의 앞 시도 줄이 상한만큼 있으면 이 시도의 첫 호출부터 막힌다. 남의 실행 줄은 빠진다."""
    use(monkeypatch, world, live_settings(run_max_usd=0.001))
    run_id = new_run(world)
    other = new_run(world)
    seeded(world, run_id, "0.001")
    seeded(world, other, "5")
    got = at_first_item(world, lambda adapters: chat(adapters, world))
    execute(world, run_id)
    (result,) = got
    assert (result.kind, result.spent_usd) == ("budget_exceeded", 0.001)
    assert fake.seen == []


def seeded(world: World, run_id: int, cost: str) -> None:
    LlmCallLogRow.for_company(world.company_id).create(
        company_id=world.company_id, module="probe", ts="2026-10-19T11:00:00Z", call_id="earlier", attempt=1,
        prompt_id="p", prompt_version=1, template_hash="t", request_hash="r", duration_ms=1.0,
        result_kind="success", run_id=run_id, cost_usd=Decimal(cost),
    )  # fmt: skip


@pytest.mark.parametrize("first", ["chat", "embed"])
def test_chat_and_embedding_share_one_run_limit(
    world: World, monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAI, first: str
) -> None:
    """대화의 비용이 임베딩의 상한 검사에 들고, 반대도 그렇다(같은 싱크·같은 몫)."""
    limit = min(CHAT_USD, EMBED_USD) / 2
    use(monkeypatch, world, live_settings(run_max_usd=limit))

    def act(adapters: ProbeAdapters) -> object:
        if first == "chat":
            chat(adapters, world)
            return embed(adapters, world)
        embed(adapters, world)
        return chat(adapters, world)

    got = at_first_item(world, act)
    run_id = new_run(world)
    execute(world, run_id)
    if first == "chat":  # 임베딩이 막혀 EmbeddingFailed(budget_exceeded — 미루지 않음) → embedding_failed
        assert (row(world, run_id).status, row(world, run_id).error_code) == ("failed", "embedding_failed")
        assert fake.paths() == ["/v1/responses"]
    else:
        assert got[0].kind == "budget_exceeded"
        assert fake.paths() == ["/v1/embeddings"]
    assert [r.result_kind for r in lines(world, run_id)] == ["success", "budget_exceeded"]


def test_the_seed_is_read_once_per_attempt(world: World, monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAI) -> None:
    use(monkeypatch, world, live_settings())
    reads: list[object] = []
    real = context.llm_usage.usage_by_run

    def counted(**kwargs: Any) -> Any:
        reads.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(context.llm_usage, "usage_by_run", counted)
    at_first_item(world, lambda adapters: [chat(adapters, world) for _ in range(3)] + [embed(adapters, world)])
    run_id = new_run(world)
    execute(world, run_id)
    assert len(fake.seen) == 4  # 분모: 상한 검사 넷
    assert reads == [{"company_id": world.company_id, "run_ids": frozenset({run_id})}]


def test_mock_is_not_limited_even_with_a_spent_run(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """mock 은 같은 상한·같은 시드여도 막지 않는다(상한 () — BASE 그대로)."""
    out = run_mock_world(world, monkeypatch, live_settings(run_mode="mock", run_max_usd=0.000001), seed="1")
    assert out["run"][0] == "done"
    # 심은 앞 시도 줄(공급사 없음) 다음에 이 시도의 모의 호출이 막히지 않고 성공했다
    assert [(line[0], line[-2]) for line in out["lines"]] == [(None, "success"), ("mock", "success")]


# ── 영문번역의 꽂힘(MARC-ENT-401·402 — TR3a 앞) ────────────────────────────


@pytest.mark.parametrize("route", ["light-anthropic", "standard"])
def test_the_translation_routes_of_today_still_need_an_anthropic_key_in_live(
    world: World, monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAI, route: str
) -> None:
    """영문번역의 지금 경로 상수(translation/tools/llm_bridge.py — light-anthropic·standard)는 live 문맥에서도
    OpenAI 키만이면 공급사 전 LiveSetupError(→ setup_error). 같은 클라이언트의 OpenAI 경로는 가짜 HTTP 에 닿는다 —
    TR3a 가 경로 상수를 openai 로 바꾸면 그 자리에 꽂힌다."""
    use(monkeypatch, world, live_settings())
    ctx = context.ExecutorContext(
        company_id=world.company_id, run_id=1, module="translation", flow_id="translation.colab@158", attempt=1,
        sink=context.RunCallSink(world.sink, 1),
    )  # fmt: skip
    client = ctx.llm()
    request = CallRequest(prompt="core/hello@1", vars={"name": "김"}, route=route, tags=tags(world))
    with pytest.raises(LiveSetupError):
        client.call(request)
    assert fake.seen == []
    assert (
        client.call(CallRequest(prompt="core/hello@1", vars={"name": "김"}, route=CHAT_ROUTE, tags=tags(world))).kind
        == "success"
    )
    assert fake.paths() == ["/v1/responses"]


def test_an_embedding_failure_is_still_the_embedding_failed_exception(
    world: World, monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAI
) -> None:
    """분모: 임베딩 401 은 포트가 EmbeddingFailed 로 던진다(위 표의 failed 가 그 예외에서 왔다)."""
    use(monkeypatch, world, live_settings())
    fake.embed = status(401)
    ctx = context.ExecutorContext(
        company_id=world.company_id,
        run_id=1,
        module="probe",
        flow_id="f",
        attempt=1,
        sink=context.RunCallSink(world.sink, 1),
    )
    with pytest.raises(EmbeddingFailed):
        ClientEmbeddingPort(ctx.embedding(), route=EMBED_ROUTE, tags=tags(world)).embed_documents(["지어낸 글"])
