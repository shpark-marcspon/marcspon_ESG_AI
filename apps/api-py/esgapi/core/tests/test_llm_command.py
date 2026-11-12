"""관리 명령 llm_call 과 실제 공급사 배선. 순수 층(DB 를 쓰지 않는다).

esg-lab 의 test/cli.test.ts(5건), test/live.test.ts(11건 가운데 probe 3건을 뺀 8건), test/gemini-routes.test.ts
(8건 가운데 probe 1건을 뺀 7건)를 옮긴 것이다.

실제 공급사로 가는 호출은 없다. SDK 클라이언트를 만드는 함수(create_*_client) 자리에 가짜를 넣어, 설정의 키 →
setup → 어댑터의 make → 어댑터까지의 배선을 본다. 키, 토큰 수, 응답은 전부 가상(synthetic) 값이다.

esg-lab 과 다른 점: `--provider` 인자가 없다(공급사는 경로의 모델이 정한다). 키는 환경 변수 LLM_*_API_KEY 에서 설정
(Config.llm)으로 읽혀 온다.
"""

import dataclasses
import io
import json
import os
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from anthropic.types import Message
from django.core.management import call_command
from django.core.management.base import CommandError
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from openai.types.responses import Response

from esgapi.config.env import LlmSettings, sdk_env_names
from esgapi.core.llm.config import ModelConfig, default_config_sources, load_config, resolve_route
from esgapi.core.llm.cost import compute_cost_usd
from esgapi.core.llm.providers import anthropic as anthropic_module
from esgapi.core.llm.providers import gemini as gemini_module
from esgapi.core.llm.providers import openai as openai_module
from esgapi.core.llm.providers.anthropic import AnthropicStream
from esgapi.core.llm.types import Usage
from esgapi.core.management.commands import llm_call

KEY_SYNTHETIC = "key-synthetic"
OTHER_KEY = "다른-키-synthetic"
CONFIG = load_config(default_config_sources(synthetic=False))
ONE_K_EACH = Usage(input_tokens=1000, output_tokens=1000, cache_read_tokens=0, cache_write_tokens=0)


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """재시도 전의 대기를 받아 적기만 한다(실제로 기다리지 않는다)."""
    sleeps: list[float] = []

    def note(seconds: float) -> None:
        sleeps.append(seconds * 1000)

    monkeypatch.setattr("esgapi.core.llm.client.time.sleep", note)
    # 재시도 대기의 흩뜨림은 0(흩뜨림 없음 — retry.default_jitter 가 이 이름을 부를 때 읽는다, LB1).
    monkeypatch.setattr("esgapi.core.llm.retry.random", SimpleNamespace(random=lambda: 0.0))
    return sleeps


def use_settings(monkeypatch: pytest.MonkeyPatch, settings: LlmSettings) -> None:
    """명령이 읽는 설정(Config.llm)을 바꾼다."""
    monkeypatch.setattr(llm_call, "app_config", lambda: SimpleNamespace(llm=settings))


def run(*args: str) -> tuple[int, str]:
    """명령을 돌려 (종료 코드, 표준 출력)을 돌려준다. 쓰는 법이 틀린 경우(코드 2)는 오류 문장이 출력 자리에 온다."""
    out = io.StringIO()
    try:
        call_command("llm_call", *args, stdout=out)
    except CommandError as error:
        return error.returncode, str(error)
    except SystemExit as exit_:
        return int(exit_.code or 0), out.getvalue()
    return 0, out.getvalue()


HELLO = ("--prompt", "core/hello@1", "--var", "name=김")


# ── cli call (esg-lab 의 cli.test.ts) ──


def test_dry_run_prints_the_assembled_request_and_the_estimate(monkeypatch: pytest.MonkeyPatch) -> None:
    use_settings(monkeypatch, LlmSettings())
    code, output = run(*HELLO, "--route", "mock", "--dry-run")
    assert code == 0
    report = json.loads(output)
    assert list(report) == [
        "dryRun",
        "promptId",
        "provider",
        "model",
        "request",
        "estimate",
        "fallbackModels",
        "warnings",
    ]
    assert list(report["estimate"]) == [
        "inputTokens",
        "cacheableTokens",
        "maxOutputTokens",
        "costUpperBoundUsd",
        "unestimatedParts",
        "schemaTokens",
        "maxAttempts",
        "worstCaseUsd",
    ]
    head = {key: report[key] for key in ("dryRun", "promptId", "provider", "model")}
    assert head == {"dryRun": True, "promptId": "core/hello@1", "provider": "mock", "model": "mock-synthetic"}
    assert report["request"]["user"] == [{"type": "text", "text": "김 님에게 한 문장으로 인사해 줘."}]
    assert report["estimate"]["inputTokens"] > 0
    assert report["estimate"]["cacheableTokens"] > 0
    assert report["estimate"]["maxOutputTokens"] == 4000
    assert report["estimate"]["costUpperBoundUsd"] > 0
    assert report["warnings"][0]["code"] == "cache_below_minimum"


def test_real_route_dry_run_assembles_the_request_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """실제 공급사도 --dry-run 은 요청 조립까지 한다(키 없이). Haiku 4.5 의 캐시 최소 길이 경고 포함."""
    use_settings(monkeypatch, LlmSettings())
    code, output = run(*HELLO, "--route", "light", "--dry-run")
    assert code == 0
    report = json.loads(output)
    assert report["model"] == "claude-haiku-4-5"
    assert report["request"]["model"] == "claude-haiku-4-5-20251001"
    assert report["request"]["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert report["fallbackModels"] == ["gpt-6-luna"]
    assert "4096" in report["warnings"][0]["message"]


def test_real_route_without_dry_run_and_without_a_limit_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    use_settings(monkeypatch, LlmSettings(anthropic_api_key=KEY_SYNTHETIC))
    code, output = run(*HELLO, "--route", "light-anthropic")
    assert code == 2
    assert "--limit-usd" in output


def test_mock_route_returns_the_planted_text_and_fails_without_one(monkeypatch: pytest.MonkeyPatch) -> None:
    use_settings(monkeypatch, LlmSettings())
    code, output = run(*HELLO, "--route", "mock", "--mock-text", "안녕하세요")
    assert code == 0
    result = json.loads(output)
    assert (result["kind"], result["data"], result["text"]) == ("success", "안녕하세요", "안녕하세요")
    assert result["meta"]["attempts"][0]["usage"] == {
        "inputTokens": 100,
        "outputTokens": 20,
        "cacheReadTokens": 0,
        "cacheWriteTokens": 0,
    }

    empty_code, empty_output = run(*HELLO, "--route", "mock")
    assert empty_code == 1
    assert json.loads(empty_output)["kind"] == "provider_error"


def test_missing_or_malformed_arguments_are_usage_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    use_settings(monkeypatch, LlmSettings())
    assert run("--route", "mock")[0] != 0  # --prompt 가 없다(argparse 가 막는다)
    assert run(*HELLO, "--route", "mock", "--var", "값만")[0] == 2
    assert run("--prompt", "core/hello", "--route", "mock")[0] == 2  # 판이 없는 id
    assert run("--prompt", "core/hello@1", "--route", "mock")[0] == 2  # 변수 name 이 없다
    assert run(*HELLO, "--route", "nope")[0] == 2


# ── 가짜 SDK 클라이언트 ──


def openai_reply(body: dict[str, Any], text: str = "pong") -> Response:
    """입력 1000 + 출력 1000 토큰짜리 가상 응답."""
    message: dict[str, Any] = {
        "type": "message",
        "id": "msg",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }
    return Response.model_validate(
        {
            "id": "resp_synthetic",
            "object": "response",
            "created_at": 0,
            "model": f"{body['model']}-snapshot-synthetic",
            "status": "completed",
            "output": [message],
            "parallel_tool_calls": False,
            "tool_choice": "auto",
            "tools": [],
            "usage": {
                "input_tokens": 1000,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens": 1000,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 2000,
            },
        }
    )


def gemini_reply(body: dict[str, Any], thoughts: int | None = None) -> genai_types.GenerateContentResponse:
    """입력 1000, 답 1000 토큰에 생각 토큰을 `thoughts` 만큼 얹은 가상 응답. 주지 않으면 그 칸이 없다."""
    usage: dict[str, int] = {"promptTokenCount": 1000, "candidatesTokenCount": 1000}
    if thoughts is not None:
        usage["thoughtsTokenCount"] = thoughts
    usage["totalTokenCount"] = 2000 + (thoughts or 0)
    candidate = {"finishReason": "STOP", "content": {"role": "model", "parts": [{"text": "pong"}]}}
    return genai_types.GenerateContentResponse.model_validate(
        {"modelVersion": f"{body['model']}-snapshot-synthetic", "candidates": [candidate], "usageMetadata": usage}
    )


def anthropic_reply(body: dict[str, Any]) -> Message:
    return Message.model_validate(
        {
            "id": "msg_synthetic",
            "type": "message",
            "role": "assistant",
            "model": f"{body['model']}-snapshot-synthetic",
            "content": [{"type": "text", "text": "pong", "citations": None}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 1000,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        }
    )


type GeminiScript = Callable[[dict[str, Any]], genai_types.GenerateContentResponse | Exception]


class FakeSdks:
    """SDK 클라이언트를 만드는 함수 셋의 자리에 들어가, 받은 키와 요청 본문을 적는다."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, gemini: GeminiScript = gemini_reply) -> None:
        self.keys: list[tuple[str, str]] = []
        self.bodies: list[dict[str, Any]] = []
        self._gemini = gemini
        self._last: dict[str, Any] = {}
        self.responses = self
        self.models = self
        self.messages = self
        monkeypatch.setattr(openai_module, "create_openai_client", self._make("openai"))
        monkeypatch.setattr(anthropic_module, "create_anthropic_client", self._make("anthropic"))
        monkeypatch.setattr(gemini_module, "create_gemini_client", self._make("gemini"))

    def _make(self, provider: str) -> Callable[[str], "FakeSdks"]:
        def create(api_key: str) -> FakeSdks:
            self.keys.append((provider, api_key))
            return self

        return create

    def create(self, **kwargs: Any) -> Response:
        self.bodies.append(kwargs)
        return openai_reply(kwargs)

    def generate_content(self, **kwargs: Any) -> genai_types.GenerateContentResponse:
        self.bodies.append(kwargs)
        reply = self._gemini(kwargs)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def stream(self, **kwargs: Any) -> "FakeSdks":
        self.bodies.append(kwargs)
        self._last = kwargs
        return self

    def __enter__(self) -> AnthropicStream:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get_final_message(self) -> Message:
        return anthropic_reply(self._last)


def with_keys(base: LlmSettings | None = None, /, **keys: str) -> LlmSettings:
    """키 칸의 이름을 글자로 받아 설정을 만든다(공급사마다 같은 테스트를 돌리려고)."""
    return dataclasses.replace(base or LlmSettings(), **keys)


def records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").strip().split("\n")]


def jsonl(tmp_path: Path, **keys: str) -> tuple[LlmSettings, Path]:
    path = tmp_path / "log" / "calls.jsonl"
    return with_keys(LlmSettings(log_sink="jsonl", jsonl_path=str(path)), **keys), path


def lead_model(route: str) -> ModelConfig:
    return resolve_route(CONFIG, route)[0]


VENDORS = [
    ("openai", "light-openai", "openai_api_key"),
    ("gemini", "light-gemini", "gemini_api_key"),
    ("anthropic", "light-anthropic", "anthropic_api_key"),
]
OTHERS = {"openai": "anthropic_api_key", "gemini": "openai_api_key", "anthropic": "openai_api_key"}


# ── 실제 공급사 배선 (esg-lab 의 live.test.ts) ──


@pytest.mark.parametrize(("provider", "route", "key_field"), VENDORS)
@pytest.mark.parametrize("case", ["없음", "빈칸뿐", "다른 공급사의 키만"])
def test_without_a_key_no_sdk_client_is_made_and_the_error_names_the_provider(
    monkeypatch: pytest.MonkeyPatch, provider: str, route: str, key_field: str, case: str
) -> None:
    """키가 없으면 SDK 클라이언트를 만들지 않고 이름 있는 오류로 끝난다. 다른 공급사의 키는 쓰지 않는다."""
    settings = {
        "없음": LlmSettings(),
        "빈칸뿐": with_keys(**{key_field: "  "}),
        "다른 공급사의 키만": with_keys(**{OTHERS[provider]: KEY_SYNTHETIC}),
    }[case]
    use_settings(monkeypatch, settings)
    fake = FakeSdks(monkeypatch)

    code, output = run(*HELLO, "--route", route, "--limit-usd", "0.1")

    assert code == 2
    assert "LiveSetupError" in output
    assert provider in output
    assert fake.keys == []
    assert fake.bodies == []


@pytest.mark.parametrize(("provider", "route", "key_field"), VENDORS)
def test_with_a_key_the_client_is_made_with_that_key_and_the_route_model_is_called(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, provider: str, route: str, key_field: str
) -> None:
    """그 공급사의 키로 클라이언트를 만들고 경로의 모델로 부른다. 기록에 응답 모델 ID 와 설정 단가의 비용이 남는다."""
    settings, log = jsonl(tmp_path, **{key_field: KEY_SYNTHETIC, OTHERS[provider]: OTHER_KEY})
    use_settings(monkeypatch, settings)
    fake = FakeSdks(monkeypatch)

    code, output = run(*HELLO, "--route", route, "--limit-usd", "0.1")

    assert code == 0
    assert fake.keys == [(provider, KEY_SYNTHETIC)]
    model = lead_model(route)
    assert model.provider == provider
    assert [body["model"] for body in fake.bodies] == [model.api_model_id]
    assert KEY_SYNTHETIC not in output
    (record,) = records(log)
    expected = {
        "provider": provider,
        "model": model.key,
        "apiModelId": model.api_model_id,
        "responseModelId": f"{model.api_model_id}-snapshot-synthetic",
        "resultKind": "success",
        "costUsd": compute_cost_usd(ONE_K_EACH, model.pricing),
    }
    assert {key: record[key] for key in expected} == expected
    assert record["costUsd"] > 0
    assert "body" not in record
    assert KEY_SYNTHETIC not in log.read_text(encoding="utf-8")


def test_openai_cost_of_the_synthetic_call_matches_the_hand_calculation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # gpt-6-luna 단가(data/models.json: 입력 0.1, 출력 0.5 USD/100만 토큰): 1000×0.1 + 1000×0.5 = 600 → 0.0006.
    settings, log = jsonl(tmp_path, openai_api_key=KEY_SYNTHETIC)
    use_settings(monkeypatch, settings)
    FakeSdks(monkeypatch)
    assert run(*HELLO, "--route", "light-openai", "--limit-usd", "0.1")[0] == 0
    assert records(log)[0]["costUsd"] == 0.0006


@pytest.mark.parametrize(("provider", "route", "key_field"), VENDORS)
def test_real_route_needs_an_explicit_positive_limit(
    monkeypatch: pytest.MonkeyPatch, provider: str, route: str, key_field: str
) -> None:
    """상한을 명시하지 않으면 부르지 않는다. (경로는 이 명령에서 늘 필수라 esg-lab 의 「--route 없음」은 argparse 가
    막는다)
    """
    use_settings(monkeypatch, with_keys(**{key_field: KEY_SYNTHETIC}))
    fake = FakeSdks(monkeypatch)
    for extra in ((), ("--limit-usd", "0"), ("--limit-usd", "-1"), ("--limit-usd", "많이"), ("--limit-usd", "inf")):
        code, output = run(*HELLO, "--route", route, *extra)
        assert code == 2, extra
        assert "--limit-usd" in output
    assert run("--prompt", "core/hello@1", "--var", "name=김", "--limit-usd", "0.1")[0] != 0  # --route 가 없다
    assert fake.keys == []
    assert fake.bodies == []


def test_a_route_whose_fallback_provider_has_no_key_is_refused_before_the_first_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """뜻이 바뀐 것: esg-lab 은 다른 공급사가 섞인 경로를 통째로 거부했다. 여기서는 섞인 경로가 정상이다(대체 호출).

    다만 경로의 모델 가운데 키 없는 공급사가 하나라도 있으면 주 모델을 부르기 전에 거부한다. 경로 light 는
    claude-haiku-4-5 → gpt-6-luna 다.
    """
    use_settings(monkeypatch, LlmSettings(anthropic_api_key=KEY_SYNTHETIC))
    fake = FakeSdks(monkeypatch)
    code, output = run(*HELLO, "--route", "light", "--limit-usd", "0.1")
    assert code == 2
    assert "openai" in output
    assert fake.bodies == []

    use_settings(monkeypatch, LlmSettings(anthropic_api_key=KEY_SYNTHETIC, openai_api_key=OTHER_KEY))
    both = FakeSdks(monkeypatch)
    assert run(*HELLO, "--route", "light", "--limit-usd", "0.1")[0] == 0
    assert [body["model"] for body in both.bodies] == ["claude-haiku-4-5-20251001"]


def test_budget_limit_reaches_the_call_layer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """esg-lab 은 이것을 probe 로 쟀다(안 옮김). 같은 뜻을 클라이언트로 잰다: 상한에 닿은 뒤로는 공급사를 부르지
    않는다.
    """
    from esgapi.core.llm.budget import BudgetLimit
    from esgapi.core.llm.client import CallRequest
    from esgapi.core.llm.setup import build_client
    from esgapi.core.llm.types import Scope, Tags

    settings, _ = jsonl(tmp_path, openai_api_key=KEY_SYNTHETIC)
    fake = FakeSdks(monkeypatch)
    # 한 번에 0.0006 USD 이므로 상한 0.0005 는 첫 호출 뒤에 닿는다.
    client = build_client(settings, limits=[BudgetLimit(scope=Scope(), limit_usd=0.0005)])
    request = CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="light-openai", tags=Tags("t", "m"))
    assert [client.call(request).kind for _ in range(3)] == ["success", "budget_exceeded", "budget_exceeded"]
    assert len(fake.bodies) == 1


# ── Gemini 경로들 (esg-lab 의 gemini-routes.test.ts) ──

GEMINI_ROUTES = [("light-gemini", "gemini-3.1-flash-lite"), ("light-gemini-35", "gemini-3.5-flash-lite")]
ROUTE_35 = "light-gemini-35"


@pytest.mark.parametrize(("route", "api_model_id"), GEMINI_ROUTES)
def test_gemini_route_points_at_one_model_with_prices_limits_and_sources(route: str, api_model_id: str) -> None:
    (model,) = resolve_route(CONFIG, route)
    assert (model.provider, model.api_model_id) == ("gemini", api_model_id)
    assert model.pricing.input > 0
    assert model.pricing.output > model.pricing.input
    assert model.pricing.cache_read < model.pricing.input
    assert model.max_output_tokens > 0
    assert model.structured_output is True
    assert "gemini_pricing" in model.entry.source_refs


def gemini_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, route: str, script: GeminiScript = gemini_reply
) -> tuple[int, list[dict[str, Any]], FakeSdks]:
    settings, log = jsonl(tmp_path, gemini_api_key=KEY_SYNTHETIC)
    use_settings(monkeypatch, settings)
    fake = FakeSdks(monkeypatch, script)
    code, _ = run(*HELLO, "--route", route, "--limit-usd", "0.1")
    return code, records(log), fake


@pytest.mark.parametrize(("route", "api_model_id"), GEMINI_ROUTES)
def test_command_calls_that_model_and_the_logged_cost_uses_its_price(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, route: str, api_model_id: str
) -> None:
    code, (record,), fake = gemini_call(monkeypatch, tmp_path, route)
    assert code == 0
    assert [body["model"] for body in fake.bodies] == [api_model_id]
    assert (record["provider"], record["apiModelId"], record["resultKind"]) == ("gemini", api_model_id, "success")
    assert record["costUsd"] == compute_cost_usd(ONE_K_EACH, lead_model(route).pricing)


def test_routes_have_different_models_so_the_same_usage_costs_differently() -> None:
    costs = {compute_cost_usd(ONE_K_EACH, lead_model(route).pricing) for route, _ in GEMINI_ROUTES}
    assert len(costs) == len(GEMINI_ROUTES)


def test_thinking_tokens_are_billed_as_output_and_also_logged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, (record,), _ = gemini_call(monkeypatch, tmp_path, ROUTE_35, lambda body: gemini_reply(body, 40))
    assert (record["outputTokens"], record["thinkingTokens"]) == (1040, 40)
    billed = Usage(input_tokens=1000, output_tokens=1040, cache_read_tokens=0, cache_write_tokens=0)
    assert record["costUsd"] == compute_cost_usd(billed, lead_model(ROUTE_35).pricing)
    assert "errorStatus" not in record


@pytest.mark.parametrize(("thoughts", "logged"), [(None, None), (0, 0)])
def test_unreported_thinking_tokens_leave_no_field_and_reported_zero_is_logged_as_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, thoughts: int | None, logged: int | None
) -> None:
    _, (record,), _ = gemini_call(monkeypatch, tmp_path, ROUTE_35, lambda body: gemini_reply(body, thoughts))
    assert record["outputTokens"] == 1000
    if logged is None:
        assert "thinkingTokens" not in record
    else:
        assert record["thinkingTokens"] == logged


def api_error(status: int) -> genai_errors.APIError:
    return genai_errors.APIError(status, {"error": {"code": status, "message": "synthetic"}})


@pytest.mark.parametrize(
    ("error", "status", "attempts"),
    [
        (api_error(503), 503, 3),
        # 429(한도 초과)는 대기 예산 갈래(LB1): 1+2+4+8 = 15초 뒤 다음 대기 16초가 예산 30초를 넘어 멈춘다 — 5번.
        (api_error(429), 429, 5),
        (httpx.ConnectError("connect failed"), None, 3),
        (api_error(404), 404, 1),
    ],
)
def test_error_status_is_logged_null_without_a_status_and_transient_errors_are_retried_twice(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    no_real_sleep: list[float],
    error: Exception,
    status: int | None,
    attempts: int,
) -> None:
    """공급사 오류의 상태 코드가 errorStatus 에 남는다. 상태 없이 실패하면 null 이다(「칸 없음」과 다르다).

    일시 오류(503, 연결 실패)는 같은 모델로 2회 다시 부르고 시도마다 기록을 남긴다. 429 는 대기 예산까지(LB1). 404 는
    한 번만 부른다.
    """
    code, logged, fake = gemini_call(monkeypatch, tmp_path, ROUTE_35, lambda _body: error)
    assert code == 1
    assert len(fake.bodies) == attempts
    assert no_real_sleep == [1_000, 2_000, 4_000, 8_000][: attempts - 1]
    first = logged[0]
    assert (first["resultKind"], first["inputTokens"], first["costUsd"]) == ("provider_error", None, None)
    # errorStatus 칸은 있고(공급사 오류다), 상태 없이 실패했으면 그 값이 null 이다.
    assert all("errorStatus" in record for record in logged)
    rows = [
        (r["attempt"], r["errorStatus"], r.get("providerRetry"), r.get("previousErrorStatus", "칸 없음"))
        for r in logged
    ]
    assert rows == [(0, status, None, "칸 없음"), *((n, status, n, status) for n in range(1, attempts))]


def test_transient_error_then_success_is_logged_as_a_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sent: list[int] = []

    def flaky(body: dict[str, Any]) -> genai_types.GenerateContentResponse | Exception:
        sent.append(1)
        return api_error(503) if len(sent) == 1 else gemini_reply(body)

    code, logged, _ = gemini_call(monkeypatch, tmp_path, ROUTE_35, flaky)
    assert code == 0
    assert [(r["resultKind"], r.get("providerRetry")) for r in logged] == [("provider_error", None), ("success", 1)]


# ── 실공급사 경로의 SDK 환경 변수(밴드 LH2 Q2 — MARC-ISSUE-411 S1) ──


@pytest.fixture(autouse=True)
def no_sdk_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """셸에 SDK 가 읽는 이름(OPENAI_BASE_URL·GOOGLE_API_KEY 등 — ENVX 밖)이 있어도 이 파일의 시험이 같게 돈다."""
    for name in sdk_env_names(os.environ):
        monkeypatch.delenv(name, raising=False)


SDK_VALUE = "http://127.0.0.1:9/sdk-env-synthetic"


@pytest.mark.parametrize("name", ["OPENAI_BASE_URL", "ANTHROPIC_BASE_URL", "GOOGLE_API_KEY"])
def test_real_route_with_an_sdk_variable_is_refused_by_name_before_any_provider(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    fake = FakeSdks(monkeypatch)
    use_settings(monkeypatch, LlmSettings(openai_api_key=KEY_SYNTHETIC))
    monkeypatch.setenv(name, SDK_VALUE)
    code, output = run(*HELLO, "--route", "light-openai", "--limit-usd", "0.1")
    assert code == 2
    assert name in output
    assert "env -u" in output
    assert SDK_VALUE not in output
    assert KEY_SYNTHETIC not in output
    assert (fake.keys, fake.bodies) == ([], [])


def test_the_same_sdk_variable_does_not_stop_a_dry_run_or_the_mock_route(monkeypatch: pytest.MonkeyPatch) -> None:
    use_settings(monkeypatch, LlmSettings())
    monkeypatch.setenv("OPENAI_BASE_URL", SDK_VALUE)
    assert run(*HELLO, "--route", "light-openai", "--dry-run")[0] == 0
    assert run(*HELLO, "--route", "mock", "--mock-text", "pong")[0] == 0


def test_without_sdk_variables_a_real_route_still_goes_to_the_limit_check(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSdks(monkeypatch)
    use_settings(monkeypatch, LlmSettings(openai_api_key=KEY_SYNTHETIC))
    code, output = run(*HELLO, "--route", "light-openai")
    assert code == 2
    assert "--limit-usd" in output
    assert run(*HELLO, "--route", "light-openai", "--limit-usd", "0.1")[0] == 0
    assert len(fake.bodies) == 1


# ── LH3 T5: live 판단이 클라이언트와 같은 모델 파일(LLM_MODELS_FILE)을 읽는다(MARC-ISSUE-413 I5) ──


def models_file(tmp_path: Path, routes: dict[str, list[str]]) -> str:
    """패키지의 models.json 에 경로를 더한 사용자 모델 파일(모의 경로는 없다 — mock 이면 가상 파일이 뒤에 붙는다)."""
    data = json.loads(default_config_sources(synthetic=False)[0].read_text(encoding="utf-8"))
    data["routes"] = {**data["routes"], **routes}
    path = tmp_path / "models.user.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_lh3_a_real_route_only_in_the_models_file_is_judged_live(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSdks(monkeypatch)
    path = models_file(tmp_path, {"lh3-real": ["gpt-4.1-mini"]})
    use_settings(monkeypatch, LlmSettings(openai_api_key=KEY_SYNTHETIC, models_file=path))
    # BASE: 판단이 패키지 파일만 읽어 「경로 lh3-real 가 설정에 없다」로 거절했다(대조)
    code, output = run(*HELLO, "--route", "lh3-real")
    assert code == 2
    assert "--limit-usd" in output
    assert fake.bodies == []
    monkeypatch.setenv("OPENAI_BASE_URL", SDK_VALUE)
    code, output = run(*HELLO, "--route", "lh3-real", "--limit-usd", "0.1")
    assert (code, "OPENAI_BASE_URL" in output, SDK_VALUE in output) == (2, True, False)
    assert fake.bodies == []
    assert run(*HELLO, "--route", "lh3-real", "--dry-run")[0] == 0
    monkeypatch.delenv("OPENAI_BASE_URL")
    assert run(*HELLO, "--route", "lh3-real", "--limit-usd", "0.1")[0] == 0
    assert len(fake.bodies) == 1


def test_lh3_the_mock_route_still_works_with_a_models_file_that_has_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use_settings(monkeypatch, LlmSettings(models_file=models_file(tmp_path, {})))
    assert run(*HELLO, "--route", "mock", "--mock-text", "pong")[0] == 0


def test_lh3_a_models_file_that_renames_the_mock_route_is_refused_before_any_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSdks(monkeypatch)
    path = models_file(tmp_path, {"mock": ["gpt-4.1-mini"]})
    use_settings(monkeypatch, LlmSettings(openai_api_key=KEY_SYNTHETIC, models_file=path))
    code, output = run(*HELLO, "--route", "mock", "--mock-text", "pong")
    assert code == 2
    assert "중복" in output  # 경로 이름이 가상 파일과 겹친다(load_config) — BASE 도 같다
    assert (fake.keys, fake.bodies) == ([], [])
