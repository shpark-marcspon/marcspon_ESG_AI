# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실행기의 실제 공급사를 켠(LV1 — LLM_RUN_MODE=live) 그린워싱 실행을 가짜 HTTP 로 끝까지 잰다(MARC-ISSUE-73 1번,
그린워싱 a2 허락 — MARC-TICK-249 노트). 업무 층: test_binding_e0_runs.py 의 world(저장소 가짜·태스크 직접 부름)를 쓰고,
끼움은 **실제 경로**(GreenwashBinding 기본값 — 대화 light-openai-41·임베딩 light-openai), 문맥 설정은 live(지어낸 키),
OpenAI SDK 의 HTTP 만 가짜(httpx.MockTransport)다. 쪽 글은 진짜 읽개(pypdf)가 지은 PDF(pdfbuild 의 한글 글꼴 — 표본 글
sample_text 네 쪽)에서 읽는다.

재는 것: POST /runs → 실행기 → done · 결과의 항목(items)·쪽 실패(failedPages) 0 ·
대화 요청의 몸(model gpt-4.1-mini·temperature 0.0·max_output_tokens 1300·store false) ·
임베딩 요청(model text-embedding-3-small·묶음 ≤ 50) · Bearer 는 지어낸 키 ·
호출 기록 줄의 공급사·모델·run_id · 바깥 연결 0.
가짜 대화는 받은 system·user 글로 ScriptedChat 의 대본 답을 돌려준다(scripted_provider 와 같은 꼴), 가짜 임베딩은
결정적 모의 벡터(MockEmbedding, 1536칸 — text-embedding-3-small 의 차원).
★ 실제 공급사·키·네트워크 0. 글은 지어낸 것이다(「가상상사」). 그린워싱 운영 코드·기존 시험 0줄.
"""

import json
import socket
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
from django.test import Client

from esgapi.config.env import LlmSettings
from esgapi.core.flows.binding import BindingRegistry
from esgapi.greenwash.engines.e0.ports import MockEmbedding, ScriptedChat
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.binding_e0 import GreenwashBinding
from esgapi.greenwash.tests import pdfbuild, sample_text
from esgapi.greenwash.tests.flows.settings_store import DefaultOnlyStore
from esgapi.greenwash.tests.flows.support import REAL_MODELS
from esgapi.greenwash.tests.flows.test_binding_e0_runs import (
    MINIMAL,
    World,
    execute,
    new_run,
    result_body,
    run_of,
    world,
)
from esgapi.runs import context, tasks

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (world,)  # test_binding_e0_runs 의 고정물을 이 모듈에서도 이름으로 찾게

KEY = "sk-proj-LV1SENTINEL" + "g" * 24  # 지어낸 키
DIMENSIONS = 1536


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    """소켓 연결·이름 풀기를 막고 시도를 센다. 끝에 0 이어야 한다."""
    tried: list[object] = []

    def refuse(*args: object, **kwargs: object) -> Any:
        tried.append(args[1:] if args else kwargs)
        raise OSError("LV1 시험: 바깥 연결 금지")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    yield tried
    assert tried == [], f"바깥 연결 시도 {len(tried)}"


class FakeOpenAI:
    """가짜 OpenAI(HTTP): 대화는 대본 답, 임베딩은 결정적 모의 벡터. 받은 요청을 적는다."""

    def __init__(self) -> None:
        self.script = ScriptedChat()
        self.vectors = MockEmbedding(dim=DIMENSIONS)
        self.seen: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        body = json.loads(request.content)
        if request.url.path.endswith("/embeddings"):
            texts: list[str] = body["input"]
            data = [
                {"object": "embedding", "index": i, "embedding": v}
                for i, v in enumerate(self.vectors.embed_documents(texts))
            ]
            usage = {"prompt_tokens": 10 * len(texts), "total_tokens": 10 * len(texts)}
            return httpx.Response(
                200, json={"object": "list", "data": data, "model": "text-embedding-3-small", "usage": usage}
            )
        system = str(body.get("instructions", ""))
        user = "".join(
            part["text"] for item in body["input"] for part in item["content"] if part["type"] == "input_text"
        )
        message = {
            "type": "message",
            "id": "msg_synthetic",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": self.script.respond(system, user), "annotations": []}],
        }
        usage = {
            "input_tokens": 100,
            "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
            "output_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 120,
        }
        return httpx.Response(
            200,
            json={
                "id": "resp_synthetic", "object": "response", "created_at": 0, "model": "gpt-4.1-mini-2025-04-14",
                "status": "completed", "incomplete_details": None, "output": [message], "parallel_tool_calls": False,
                "tool_choice": "auto", "tools": [], "usage": usage,
            },
        )  # fmt: skip

    def bodies(self, path: str) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.seen if r.url.path == path]


@pytest.fixture
def live(world: World, monkeypatch: pytest.MonkeyPatch) -> FakeOpenAI:
    """실제 경로의 끼움 + live 문맥 설정(지어낸 키) + openai.OpenAI 를 가짜 HTTP 를 단 진짜 SDK 클라이언트로."""
    bindings = BindingRegistry()
    bindings.register(colab.FLOW_ID, GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()))
    monkeypatch.setattr(tasks, "BINDINGS", bindings)
    settings = LlmSettings(openai_api_key=KEY, log_sink="db", run_mode="live", run_max_usd=5.0)
    monkeypatch.setattr(context, "app_config", lambda: SimpleNamespace(llm=settings))
    server = FakeOpenAI()
    real = openai.OpenAI

    def build(**kwargs: Any) -> openai.OpenAI:
        transport = httpx.MockTransport(server.handle)  # SDK 의 legacy httpx 클라이언트 길(새 의존 0)
        return real(**kwargs, http_client=httpx.Client(transport=transport))  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(openai, "OpenAI", build)
    return server


def sample_pdf() -> bytes:
    """표본 글 네 쪽을 한글 글꼴(글리프 없음·ToUnicode 있음)로 적은 PDF — 진짜 읽개가 글을 읽는다."""
    doc = pdfbuild.Doc()
    for lines in (sample_text.PAGE_1, sample_text.PAGE_2, sample_text.PAGE_3, sample_text.PAGE_4):
        page = doc.new_page(width=1600, height=40 + 12 * len(lines))
        for i, line in enumerate(lines):
            page.insert_text((20, 20 + 12 * i), line, fontsize=8, font=pdfbuild.KOREAN)
    return doc.tobytes()


def test_a_live_greenwash_run_reaches_done_through_the_fake_http(
    client: Client, world: World, live: FakeOpenAI
) -> None:
    run_id = new_run(client, world, MINIMAL, content=sample_pdf(), name="synthetic-live.pdf")
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.error_code) == ("done", None), run
    body = result_body(world, run_id)
    assert len(body["items"]) >= 1  # 분모: 판정이 실제로 났다
    assert body["candidateStats"]["failedPages"] == []
    # 대화 요청(Q7): gpt-4.1-mini · temperature 0.0 · 출력 상한 1300 · store false
    chats = live.bodies("/v1/responses")
    assert len(chats) >= 1
    assert {(c["model"], c["temperature"], c["max_output_tokens"], c["store"]) for c in chats} == {
        ("gpt-4.1-mini", 0.0, 1300, False)
    }
    # 임베딩 요청: text-embedding-3-small · 묶음 ≤ 50
    embeds = live.bodies("/v1/embeddings")
    assert len(embeds) >= 1
    assert {e["model"] for e in embeds} == {"text-embedding-3-small"}
    assert max(len(e["input"]) for e in embeds) <= 50
    assert {r.headers["authorization"] for r in live.seen} == {f"Bearer {KEY}"}
    # 호출 기록 줄: 실제 공급사·모델·이 실행
    records = world.sink.records
    assert len(records) == len(live.seen)
    assert {(r.provider, r.api_model_id) for r in records} == {
        ("openai", "gpt-4.1-mini"),
        ("openai", "text-embedding-3-small"),
    }
    assert {r.run_id for r in records} == {str(run_id)}
    assert {r.result_kind for r in records} == {"success"}
