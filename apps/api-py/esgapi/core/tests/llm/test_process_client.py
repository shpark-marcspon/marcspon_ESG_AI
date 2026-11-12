"""서버 요청 길의 클라이언트 `llm_client()` 는 실제 공급사 키를 싣지 않는다(밴드 LH2 S1~S3 — MARC-ISSUE-411).
순수 층.

  S1 키 없음      설정에 키 셋 + run_mode mock·live 둘 다: openai·anthropic·gemini 경로의 dry_run·call 이
                  LiveSetupError, 어댑터의 make 가 받은 키는 None, SDK 생성 함수 부름 0, 소켓 시도 0.
                  조립(assemble_only)은 따로 된다
  S2 Scope 3 그대로  `llm_client()` 에는 경로 mock 이 없다(LlmConfigError) — inventory 시험이 503 을 따로 잰다
  S3 SDK 변수     OPENAI_BASE_URL·ANTHROPIC_BASE_URL 을 둔 셸에서도 어떤 경로로든 요청 0
★ 설정은 `setup.app_config` 이음매로 바꾼다(`llm_client` 는 @cache — 시험 앞뒤로 cache_clear). 키는 지어낸 글자다.
★ 네트워크 0: 소켓 연결·이름 풀기를 막는 고정물(no_network — runs/tests/test_context_live.py 의 꼴).
"""

import socket
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from esgapi.config.env import LlmSettings
from esgapi.core.llm import setup
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.errors import LiveSetupError, LlmConfigError
from esgapi.core.llm.providers import anthropic as anthropic_module
from esgapi.core.llm.providers import gemini as gemini_module
from esgapi.core.llm.providers import openai as openai_module
from esgapi.core.llm.types import Tags
from esgapi.core.resources import llm as llm_adapters

TAGS = Tags(tenant="tenant-synthetic", module="core")
ROUTES = {"openai": "light-openai", "anthropic": "light-anthropic", "gemini": "light-gemini"}


def keyed(run_mode: Literal["mock", "live"]) -> LlmSettings:
    return LlmSettings(
        openai_api_key="openai-key-synthetic",
        anthropic_api_key="anthropic-key-synthetic",
        gemini_api_key="gemini-key-synthetic",
        run_mode=run_mode,
    )


def request(route: str) -> CallRequest[str]:
    return CallRequest(prompt="core/hello@1", vars={"name": "합성"}, route=route, tags=TAGS)


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    tried: list[object] = []

    def refuse(*args: object, **kwargs: object) -> Any:
        tried.append(args)
        raise OSError("시험 중 네트워크 금지")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    yield tried
    assert tried == [], "소켓 시도가 있었다"


@pytest.fixture(autouse=True)
def fresh_client() -> Iterator[None]:
    setup.llm_client.cache_clear()
    yield
    setup.llm_client.cache_clear()


@pytest.fixture
def made(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str | None]]:
    """어댑터의 make 가 받은 (공급사, 키). 진짜 make 를 그대로 부른다."""
    seen: list[tuple[str, str | None]] = []
    real = llm_adapters.make

    def spy(name: str, *, api_key: str | None = None, assemble_only: bool = False) -> Any:
        seen.append((name, api_key))
        return real(name, api_key=api_key, assemble_only=assemble_only)

    monkeypatch.setattr(llm_adapters, "make", spy)
    return seen


@pytest.fixture
def sdk_built(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """SDK 클라이언트를 만드는 함수 셋의 부름. 하나라도 불리면 키가 SDK 에 닿은 것이다."""
    built: list[str] = []
    for module, name in (
        (openai_module, "create_openai_client"),
        (anthropic_module, "create_anthropic_client"),
        (gemini_module, "create_gemini_client"),
    ):

        def fake(api_key: str, _name: str = name) -> Any:
            built.append(_name)
            raise AssertionError("SDK 클라이언트를 만들면 안 된다")

        monkeypatch.setattr(module, name, fake)
    return built


def use(monkeypatch: pytest.MonkeyPatch, settings: LlmSettings) -> None:
    monkeypatch.setattr(setup, "app_config", lambda: SimpleNamespace(llm=settings))


@pytest.mark.parametrize("run_mode", ["mock", "live"])
@pytest.mark.parametrize("provider", sorted(ROUTES))
def test_s1_the_process_client_carries_no_key_in_either_run_mode(
    monkeypatch: pytest.MonkeyPatch,
    no_network: list[object],
    made: list[tuple[str, str | None]],
    sdk_built: list[str],
    provider: str,
    run_mode: Literal["mock", "live"],
) -> None:
    use(monkeypatch, keyed(run_mode))
    client = setup.llm_client()
    with pytest.raises(LiveSetupError):
        client.dry_run(request(ROUTES[provider]))
    with pytest.raises(LiveSetupError):
        client.call(request(ROUTES[provider]))
    assert made, "make 가 불리지 않았다"
    assert all(name == provider and key is None for name, key in made)
    assert sdk_built == []


def test_s1_the_same_keyless_settings_still_assemble_for_dry_run(
    no_network: list[object], sdk_built: list[str]
) -> None:
    """키를 비운 설정으로도 조립(assemble_only)은 된다 — 막힌 것은 키뿐이다."""
    keyless = LlmSettings(run_mode="live")
    for route in ROUTES.values():
        report = setup.build_client(keyless, assemble_only=True).dry_run(request(route))
        assert report.request
    assert sdk_built == []


def test_s2_the_process_client_has_no_mock_route(monkeypatch: pytest.MonkeyPatch, no_network: list[object]) -> None:
    use(monkeypatch, keyed("mock"))
    with pytest.raises(LlmConfigError):
        setup.llm_client().call(request("mock"))


def test_s2_the_process_client_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, keyed("mock"))
    assert setup.llm_client() is setup.llm_client()


@pytest.mark.parametrize("run_mode", ["mock", "live"])
def test_s3_sdk_variables_in_the_shell_send_nothing(
    monkeypatch: pytest.MonkeyPatch,
    no_network: list[object],
    made: list[tuple[str, str | None]],
    sdk_built: list[str],
    run_mode: Literal["mock", "live"],
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9/elsewhere")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9/elsewhere")
    use(monkeypatch, keyed(run_mode))
    client = setup.llm_client()
    for route in (*ROUTES.values(), "light", "standard"):
        with pytest.raises(LiveSetupError):
            client.call(request(route))
    assert all(key is None for _, key in made)
    assert sdk_built == []
