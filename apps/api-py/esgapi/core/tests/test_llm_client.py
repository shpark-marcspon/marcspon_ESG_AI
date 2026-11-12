"""LlmClient.call / dry_run. 순수 층. esg-lab 의 test/client.test.ts(27건)를 옮긴 것이다.

공급사는 전부 모의 공급사다. 토큰 수와 단가는 가상(synthetic) 값이다.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel

from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.types import (
    BudgetExceeded,
    Completed,
    CutOff,
    ProviderError,
    ProviderFailed,
    Refusal,
    Refused,
    SchemaMismatch,
    Scope,
    Success,
    SystemSegment,
    Tags,
    TimedOut,
    Truncated,
    Usage,
)
from esgapi.core.tests.llm_support import TAGS, USAGE_SYNTHETIC, config_with, harness


class Answer(BaseModel):
    category: str
    confidence: float


BASE = CallRequest(prompt="t/plain@1", vars={"question": "분류해 줘"}, route="mock", tags=TAGS)
WITH_SCHEMA = CallRequest(prompt="t/plain@1", vars={"question": "분류해 줘"}, route="mock", tags=TAGS, schema=Answer)
GOOD = json.dumps({"category": "cat-1", "confidence": 0.9})
BAD = json.dumps({"category": "cat-1"})


# ── LlmClient.call ──


def test_success_returns_validated_data_and_cost(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text(GOOD, USAGE_SYNTHETIC)

    result = h.client.call(WITH_SCHEMA)

    assert isinstance(result, Success)
    assert result.data == Answer(category="cat-1", confidence=0.9)
    assert result.meta.total_cost_usd == 0.0001
    assert [attempt.kind for attempt in result.meta.attempts] == ["success"]
    sent = h.mock.calls[0].json_schema
    assert sent is not None
    assert sent.schema["type"] == "object"
    assert sent.schema["required"] == ["category", "confidence"]
    # 공급사에 나가는 스키마는 닫힌 객체다(OpenAI strict 가 요구한다).
    assert sent.schema["additionalProperties"] is False
    assert len(h.log.records) == 1


def test_call_without_schema_returns_text_as_is(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("안녕하세요")
    result = h.client.call(BASE)
    assert isinstance(result, Success)
    assert result.data == "안녕하세요"
    assert h.mock.calls[0].json_schema is None


def test_schema_mismatch_then_success_on_retry(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text(BAD, USAGE_SYNTHETIC).enqueue_text("JSON 아님", USAGE_SYNTHETIC).enqueue_text(
        GOOD, USAGE_SYNTHETIC
    )

    result = h.client.call(WITH_SCHEMA)

    assert result.kind == "success"
    assert [attempt.kind for attempt in result.meta.attempts] == ["schema_mismatch", "schema_mismatch", "success"]
    # 실패한 시도의 토큰도 과금되므로 비용에 들어간다.
    assert result.meta.total_cost_usd == 0.0003
    assert [record.result_kind for record in h.log.records] == ["schema_mismatch", "schema_mismatch", "success"]


def test_default_is_two_schema_retries_then_schema_mismatch(prompt_root: Path) -> None:
    """기본값: 스키마가 어긋나면 같은 모델을 2회 더 부르고(모두 3번), 그래도 어긋나면 schema_mismatch 다."""
    h = harness(prompt_root)
    for _ in range(4):
        h.mock.enqueue_text(BAD, USAGE_SYNTHETIC)

    result = h.client.call(WITH_SCHEMA)

    assert isinstance(result, SchemaMismatch)
    assert len(h.mock.calls) == 3
    assert h.mock.pending == 1
    # 마지막 결과의 meta 는 세 시도를 다 담는다.
    assert [attempt.kind for attempt in result.meta.attempts] == ["schema_mismatch"] * 3
    assert result.meta.total_cost_usd == 0.0003


def test_exhausted_retries_end_as_schema_mismatch_not_empty_success(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text(BAD).enqueue_text(BAD)

    result = h.client.call(replace(WITH_SCHEMA, max_schema_retries=1))

    assert isinstance(result, SchemaMismatch)
    assert result.issues[0].path == "confidence"
    assert result.raw_text == BAD
    assert len(h.mock.calls) == 2
    assert not hasattr(result, "data")


def test_text_that_is_not_json_is_a_schema_issue_at_the_root(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("JSON 아님")
    result = h.client.call(replace(WITH_SCHEMA, max_schema_retries=0))
    assert isinstance(result, SchemaMismatch)
    assert result.issues[0].path == ""
    assert "JSON 으로 읽을 수 없다" in result.issues[0].message


def test_validation_does_not_coerce_types(prompt_root: Path) -> None:
    """글자 "0.9" 를 수로 바꿔 읽지 않는다(JSON 의 타입 그대로 본다)."""
    h = harness(prompt_root)
    h.mock.enqueue_text(json.dumps({"category": "cat-1", "confidence": "0.9"}))
    result = h.client.call(replace(WITH_SCHEMA, max_schema_retries=0))
    assert isinstance(result, SchemaMismatch)
    assert result.issues[0].path == "confidence"


def test_schema_mismatch_does_not_fall_back(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text(BAD)
    h.mock_b.enqueue_text(GOOD)

    result = h.client.call(replace(WITH_SCHEMA, route="mock-with-fallback", max_schema_retries=0))

    assert result.kind == "schema_mismatch"
    assert len(h.mock_b.calls) == 0


def test_refusal_is_returned_and_not_retried(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue(Refusal(text="답할 수 없다", category="synthetic", usage=USAGE_SYNTHETIC))

    result = h.client.call(replace(WITH_SCHEMA, route="mock-with-fallback"))

    assert isinstance(result, Refused)
    assert (result.text, result.category) == ("답할 수 없다", "synthetic")
    assert len(h.mock.calls) == 1
    assert len(h.mock_b.calls) == 0


def test_truncated_output_is_returned_and_not_validated(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue(Truncated(text='{"category":"ca', usage=USAGE_SYNTHETIC))

    result = h.client.call(WITH_SCHEMA)

    assert isinstance(result, CutOff)
    assert result.partial_text == '{"category":"ca'
    assert len(h.mock.calls) == 1
    assert result.meta.total_cost_usd == 0.0001


def test_timeout_is_returned_as_timeout(prompt_root: Path) -> None:
    """뜻이 바뀐 것: esg-lab 은 호출 층이 시계를 걸어 끊었다. 여기서는 어댑터(모의 공급사)가 시간 초과 갈래로 답한다."""
    h = harness(prompt_root)
    h.mock.enqueue(Completed(text=GOOD, usage=USAGE_SYNTHETIC), delay_ms=500)

    result = h.client.call(replace(WITH_SCHEMA, timeout_ms=20))

    assert isinstance(result, TimedOut)
    first = result.meta.attempts[0]
    assert (first.kind, first.usage, first.cost_usd) == ("timeout", None, None)
    record = h.log.records[0]
    assert (record.result_kind, record.input_tokens, record.cost_usd) == ("timeout", None, None)


def test_provider_error_is_returned_when_no_fallback(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue(ProviderError(status=503, retryable=True, message="과부하"))

    result = h.client.call(BASE)

    assert isinstance(result, ProviderFailed)
    assert (result.status, result.retryable, result.message) == (503, True, "과부하")


def test_empty_mock_queue_does_not_invent_success(prompt_root: Path) -> None:
    h = harness(prompt_root)
    assert h.client.call(BASE).kind == "provider_error"


def test_adapter_that_raises_becomes_provider_error_with_keys_redacted(prompt_root: Path) -> None:
    """어댑터는 던지지 않기로 했지만, 던지면 삼키지 않고 공급사 오류로 돌린다. 오류 문장의 키 모양 글자는 가린다."""

    def explode(_request: object) -> Completed:
        raise RuntimeError("boom sk-synthetic-0000aaaa")

    h = harness(prompt_root)
    h.mock.enqueue(explode)
    result = h.client.call(BASE)
    assert isinstance(result, ProviderFailed)
    assert (result.status, result.retryable) == (None, False)
    assert result.message == "어댑터가 예외를 던졌다: boom sk-[가림]"


def test_fallback_on_primary_provider_error(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue(ProviderError(status=500, retryable=True, message="서버 오류"))
    h.mock_b.enqueue_text(GOOD, USAGE_SYNTHETIC)

    result = h.client.call(replace(WITH_SCHEMA, route="mock-with-fallback"))

    assert result.kind == "success"
    assert [(attempt.provider, attempt.kind) for attempt in result.meta.attempts] == [
        ("mock", "provider_error"),
        ("mock-b", "success"),
    ]
    # 대체 모델(mock-b-synthetic)의 단가로 계산한다: 60×2 + 20×4 = 200 → 0.0002.
    assert result.meta.total_cost_usd == 0.0002
    assert [record.model for record in h.log.records] == ["mock-synthetic", "mock-b-synthetic"]


def test_no_fallback_on_non_retryable_error(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue(ProviderError(status=400, retryable=False, message="잘못된 요청"))
    h.mock_b.enqueue_text(GOOD, USAGE_SYNTHETIC)

    result = h.client.call(replace(WITH_SCHEMA, route="mock-with-fallback"))

    assert isinstance(result, ProviderFailed)
    assert (result.status, result.retryable) == (400, False)
    assert len(h.mock_b.calls) == 0


def test_fallback_on_timeout_and_last_failure_is_returned(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue(Completed(text=GOOD, usage=USAGE_SYNTHETIC), delay_ms=500)
    h.mock_b.enqueue(ProviderError(status=429, retryable=True, message="한도"))

    result = h.client.call(replace(BASE, route="mock-with-fallback", timeout_ms=20))

    assert isinstance(result, ProviderFailed)
    assert result.status == 429
    assert [attempt.kind for attempt in result.meta.attempts] == ["timeout", "provider_error"]


# ── 비용 상한 ──


def test_budget_blocks_before_calling_provider_once_limit_is_reached(prompt_root: Path) -> None:
    scope = Scope(tenant=TAGS.tenant)
    h = harness(prompt_root, limits=[BudgetLimit(scope=scope, limit_usd=0.0002)])
    h.mock.enqueue_text("1", USAGE_SYNTHETIC).enqueue_text("2", USAGE_SYNTHETIC).enqueue_text("3", USAGE_SYNTHETIC)

    # 누적 0.0001 은 상한 0.0002 에 못 미친다: 넘기 직전의 호출은 지나간다.
    assert h.client.call(BASE).kind == "success"
    assert h.client.call(BASE).kind == "success"
    third = h.client.call(BASE)

    assert isinstance(third, BudgetExceeded)
    assert (third.limit_usd, third.spent_usd, third.scope) == (0.0002, 0.0002, scope)
    assert len(h.mock.calls) == 2
    assert h.mock.pending == 1
    assert h.client.budget.spent(scope) == 0.0002
    last = h.log.records[-1]
    assert (last.result_kind, last.provider, last.cost_usd) == ("budget_exceeded", None, None)


def test_budget_does_not_block_other_tags(prompt_root: Path) -> None:
    limit = BudgetLimit(scope=Scope(tenant=TAGS.tenant, module="scope3"), limit_usd=0.0001)
    h = harness(prompt_root, limits=[limit])
    h.mock.enqueue_text("1", USAGE_SYNTHETIC).enqueue_text("2", USAGE_SYNTHETIC)

    assert h.client.call(BASE).kind == "success"
    assert h.client.call(BASE).kind == "budget_exceeded"
    other = replace(BASE, tags=Tags(tenant=TAGS.tenant, module="translate"))
    assert h.client.call(other).kind == "success"


def test_budget_is_checked_between_schema_retries(prompt_root: Path) -> None:
    h = harness(prompt_root, limits=[BudgetLimit(scope=Scope(), limit_usd=0.0001)])
    h.mock.enqueue_text(BAD, USAGE_SYNTHETIC).enqueue_text(GOOD, USAGE_SYNTHETIC)

    result = h.client.call(WITH_SCHEMA)

    assert result.kind == "budget_exceeded"
    assert len(h.mock.calls) == 1


# ── 출력 상한과 추론 여유분 ──


def test_request_limit_goes_out_as_is_without_reserve(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("ok")
    request = replace(BASE, max_output_tokens=400)
    h.client.call(request)
    assert h.mock.calls[0].max_output_tokens == 400
    assert h.client.dry_run(request).estimate.max_output_tokens == 400


def test_reserve_is_added_and_dry_run_counts_it(prompt_root: Path) -> None:
    h = harness(prompt_root, config=config_with(reasoning_output_reserve_tokens=1500), store_bodies=True)
    h.mock.enqueue_text("ok")
    request = replace(BASE, max_output_tokens=400)
    h.client.call(request)
    assert h.mock.calls[0].max_output_tokens == 1900
    body = h.log.records[0].body
    assert body is not None
    assert body.request["maxOutputTokens"] == 1900
    plain = harness(prompt_root).client.dry_run(request)
    reserved = h.client.dry_run(request)
    assert reserved.estimate.max_output_tokens == 1900
    # 모의 단가: 출력 2 USD/100만 토큰. 여유분 1500 토큰만큼 상한이 오른다.
    difference = reserved.estimate.cost_upper_bound_usd - plain.estimate.cost_upper_bound_usd
    assert difference == pytest.approx((1500 * 2) / 1e6, abs=1e-12)


def test_reserve_applies_to_default_limit_and_stops_at_model_limit(prompt_root: Path) -> None:
    h = harness(prompt_root, config=config_with(reasoning_output_reserve_tokens=1500))
    # 모의 모델의 출력 상한은 4000 이다. 기본 답 상한 min(4096, 4000) + 1500 → 4000.
    assert h.client.dry_run(BASE).estimate.max_output_tokens == 4000
    assert h.client.dry_run(replace(BASE, max_output_tokens=3000)).estimate.max_output_tokens == 4000
    # 답의 상한 자체가 모델 상한을 넘으면 여전히 설정 오류다.
    with pytest.raises(LlmConfigError, match="상한"):
        h.client.dry_run(replace(BASE, max_output_tokens=4001))


# ── 프롬프트 캐싱 경고 ──


def test_cache_below_minimum_warns_before_calling(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("ok", USAGE_SYNTHETIC)
    request = replace(BASE, prompt="t/cached-short@1")

    dry = h.client.dry_run(request)
    assert [warning.code for warning in dry.warnings] == ["cache_below_minimum"]
    assert len(h.mock.calls) == 0

    result = h.client.call(request)
    assert "cache_below_minimum" in [warning.code for warning in result.meta.warnings]
    assert h.mock.calls[0].system == (SystemSegment(text="짧은 지침.", cache=True),)


def test_no_warning_above_minimum_and_no_check_without_cache_mark(prompt_root: Path) -> None:
    h = harness(prompt_root)
    assert h.client.dry_run(replace(BASE, prompt="t/cached-long@1")).warnings == ()
    assert h.client.dry_run(BASE).warnings == ()


def test_cache_marked_but_zero_cache_tokens_is_reported(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("ok", USAGE_SYNTHETIC)
    result = h.client.call(replace(BASE, prompt="t/cached-long@1"))
    assert [warning.code for warning in result.meta.warnings] == ["cache_not_applied"]


def test_unreported_cache_tokens_are_told_apart_from_zero(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("ok", replace(USAGE_SYNTHETIC, cache_read_tokens=None, cache_write_tokens=None))
    result = h.client.call(replace(BASE, prompt="t/cached-long@1"))
    assert [warning.code for warning in result.meta.warnings] == ["usage_unreported"]


# ── 호출 기록 ──

RECORD_KEYS = [
    "ts",
    "callId",
    "attempt",
    "provider",
    "model",
    "apiModelId",
    "responseModelId",
    "promptId",
    "promptVersion",
    "templateHash",
    "requestHash",
    "inputTokens",
    "outputTokens",
    "cacheReadTokens",
    "cacheWriteTokens",
    "costUsd",
    "durationMs",
    "resultKind",
    "tenant",
    "module",
    "warnings",
]


def test_record_has_every_field_and_no_body_by_default(prompt_root: Path) -> None:
    h = harness(prompt_root)
    usage = Usage(input_tokens=60, output_tokens=20, cache_read_tokens=7, cache_write_tokens=3)
    h.mock.enqueue_text("비밀 응답", usage)

    h.client.call(replace(BASE, vars={"question": "비밀 질문"}))

    line = h.log.records[0].to_json()
    # 늘 있는 칸 스물하나. 「있을 때만 있는 칸」(thinkingTokens, errorStatus, retry…, body)은 이 호출에 없다.
    assert list(line) == RECORD_KEYS
    expected: dict[str, object] = {
        "provider": "mock",
        "model": "mock-synthetic",
        "apiModelId": "mock-synthetic",
        "responseModelId": None,
        "promptId": "t/plain@1",
        "promptVersion": 1,
        "attempt": 0,
        "inputTokens": 60,
        "outputTokens": 20,
        "cacheReadTokens": 7,
        "cacheWriteTokens": 3,
        "resultKind": "success",
        "tenant": TAGS.tenant,
        "module": TAGS.module,
        "warnings": [],
    }
    assert {key: line[key] for key in expected} == expected
    for key in ("requestHash", "templateHash"):
        value = cast("str", line[key])
        assert len(value) == 64
        assert set(value) <= set("0123456789abcdef")
    assert cast("str", line["ts"]).endswith("Z")
    assert "body" not in line
    assert "비밀" not in json.dumps(line, ensure_ascii=False)


def test_store_bodies_keeps_request_and_response(prompt_root: Path) -> None:
    h = harness(prompt_root, store_bodies=True)
    h.mock.enqueue_text("비밀 응답")
    h.client.call(replace(BASE, vars={"question": "비밀 질문"}))
    body = cast("dict[str, Any]", h.log.records[0].to_json()["body"])
    assert body["responseText"] == "비밀 응답"
    assert "비밀 질문" in json.dumps(body["request"], ensure_ascii=False)


def test_same_input_same_request_hash(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("a").enqueue_text("b").enqueue_text("c")
    h.client.call(BASE)
    h.client.call(BASE)
    h.client.call(replace(BASE, vars={"question": "다른 질문"}))
    first, second, third = (record.request_hash for record in h.log.records)
    assert first == second
    assert third != first


# ── 설정 오류는 결과가 아니라 예외다 ──


def test_config_errors_are_exceptions_not_results(prompt_root: Path) -> None:
    h = harness(prompt_root)
    with pytest.raises(LlmConfigError, match="경로 nope"):
        h.client.call(replace(BASE, route="nope"))
    with pytest.raises(LlmConfigError, match="어댑터가 등록되지 않았다"):
        h.client.call(replace(BASE, route="light"))
    with pytest.raises(LlmConfigError, match="상한 4000"):
        h.client.call(replace(BASE, max_output_tokens=4001))
    with pytest.raises(LlmConfigError, match="0 이상의 정수"):
        h.client.call(replace(BASE, max_schema_retries=-1))
    with pytest.raises(LlmConfigError, match="0 이상의 정수"):
        h.client.call(replace(BASE, max_schema_retries=cast("int", 1.5)))
    # 예외가 난 호출은 공급사를 부르지 않았고 기록도 남기지 않았다.
    assert len(h.mock.calls) == 0
    assert h.log.records == []


def test_fallback_provider_is_resolved_before_the_first_attempt(prompt_root: Path) -> None:
    """대체 모델의 어댑터가 없으면 주 모델을 부르기 전에 예외가 난다(돈을 쓴 뒤에 알게 되지 않는다)."""
    h = harness(prompt_root)
    only_primary = harness(prompt_root, providers={"mock": h.mock})
    h.mock.enqueue_text("ok")
    with pytest.raises(LlmConfigError, match="mock-b"):
        only_primary.client.call(replace(BASE, route="mock-with-fallback"))
    assert len(h.mock.calls) == 0
