"""호출 기록의 싱크 둘(메모리, JSONL)과 기록 한 줄의 JSON 꼴. 순수 층. AD4D: 단계 칸 — 줄 꼴·행 ↔ 기록(저장 없이)."""

import json
from dataclasses import replace
from pathlib import Path

from esgapi.core.llm.log import MISSING, CallRecord, RecordBody, sha256_json, sha256_text
from esgapi.core.llm.sink_db import record_from_row, row_from_record
from esgapi.core.llm.sinks.jsonl import JsonlFileSink
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Scope

RECORD = CallRecord(
    ts="2026-10-08T00:00:00.000Z",
    call_id="call-synthetic",
    attempt=0,
    provider="mock",
    model="mock-synthetic",
    api_model_id="mock-synthetic",
    response_model_id=None,
    prompt_id="t/plain@1",
    prompt_version=1,
    template_hash="a" * 64,
    request_hash="b" * 64,
    input_tokens=60,
    output_tokens=20,
    cache_read_tokens=0,
    cache_write_tokens=0,
    cost_usd=0.0001,
    duration_ms=12,
    result_kind="success",
    tenant="tenant-a",
    module="scope3",
    warnings=("cache_not_applied",),
)
ALWAYS = [
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


def test_line_has_the_always_present_keys_in_the_original_order() -> None:
    assert list(RECORD.to_json()) == ALWAYS


def test_optional_fields_appear_only_when_present_and_in_the_original_position() -> None:
    full = replace(
        RECORD,
        thinking_tokens=0,
        error_status=503,
        retry_after_ms=7000,
        provider_retry=1,
        previous_error_status=429,
        retry_wait_ms=7000,
        body=RecordBody(request={"apiModelId": "m"}, response_text=None),
    )
    optional = ["thinkingTokens", "errorStatus", "retryAfterMs", "providerRetry", "previousErrorStatus", "retryWaitMs"]
    assert list(full.to_json()) == [*ALWAYS[:15], *optional, *ALWAYS[15:], "body"]
    # 생각 토큰 0 은 「0 이라고 보고함」이라 남는다. None(보고하지 않음)이면 칸이 없다.
    assert full.to_json()["thinkingTokens"] == 0
    assert full.to_json()["body"] == {"request": {"apiModelId": "m"}, "responseText": None}


def test_missing_and_null_are_different_for_the_two_status_fields() -> None:
    """칸 없음 = 공급사 오류가 아니다 / 재시도한 시도가 아니다.  null = 상태 코드 없이 실패했다(연결 실패 등)."""
    assert (RECORD.error_status, RECORD.previous_error_status) == (MISSING, MISSING)
    absent = RECORD.to_json()
    assert "errorStatus" not in absent
    assert "previousErrorStatus" not in absent

    no_status = replace(RECORD, error_status=None, provider_retry=1, previous_error_status=None, retry_wait_ms=1000)
    line = json.loads(json.dumps(no_status.to_json()))
    assert "errorStatus" in line
    assert line["errorStatus"] is None
    assert "previousErrorStatus" in line
    assert line["previousErrorStatus"] is None


def test_jsonl_sink_appends_one_compact_line_per_record_and_makes_the_folder(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "calls.jsonl"
    sink = JsonlFileSink(path)
    sink.record(RECORD)
    sink.record(replace(RECORD, attempt=1, tenant="테넌트-나"))
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    assert len(lines) == 3
    assert lines[2] == ""
    assert json.loads(lines[0]) == RECORD.to_json()
    assert list(json.loads(lines[0])) == ALWAYS
    # 한글은 \u 로 바꾸지 않고, 빈칸을 넣지 않는다.
    assert '"tenant":"테넌트-나"' in lines[1]
    # 다시 열어도 앞의 줄을 지우지 않는다.
    JsonlFileSink(path).record(RECORD)
    assert len(path.read_text(encoding="utf-8").strip().split("\n")) == 3


def spent_cases(sink: MemorySink | JsonlFileSink) -> None:
    sink.record(RECORD)
    sink.record(replace(RECORD, module="translate", cost_usd=0.0002))
    sink.record(replace(RECORD, tenant="tenant-b", cost_usd=0.0004))
    # 비용이 없는 줄(오류, 시간 초과, 상한에 막힌 줄)은 세지 않는다.
    sink.record(replace(RECORD, cost_usd=None, result_kind="timeout"))
    assert sink.spent(Scope()) == 0.0007
    assert sink.spent(Scope(tenant="tenant-a")) == 0.0003
    assert sink.spent(Scope(tenant="tenant-a", module="scope3")) == 0.0001
    assert sink.spent(Scope(module="translate")) == 0.0002
    assert sink.spent(Scope(tenant="nobody")) == 0


def test_memory_sink_sums_cost_by_scope() -> None:
    sink = MemorySink()
    spent_cases(sink)
    assert len(sink.records) == 4


def test_jsonl_sink_sums_only_what_this_object_wrote(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    spent_cases(JsonlFileSink(path))
    # 무효 조건을 그대로 잰다: 파일에 이미 있던 줄은 새 객체의 누적에 들지 않는다(프로세스가 다시 뜨면 0 부터).
    assert JsonlFileSink(path).spent(Scope()) == 0


def test_hash_does_not_depend_on_key_order_and_keeps_korean_as_utf8() -> None:
    assert sha256_json({"a": 1, "b": "가"}) == sha256_json({"b": "가", "a": 1})
    assert sha256_json({"a": 1}) != sha256_json({"a": 2})
    # 직렬화 규칙을 못 박는다: 열쇠 정렬, 빈칸 없음, 한글 그대로.
    assert sha256_json({"b": "가", "a": 1}) == sha256_text('{"a":1,"b":"가"}')


def test_a_run_id_is_written_last_and_only_when_present(tmp_path: Path) -> None:
    """실행 id(X1b-1)는 있을 때만 있는 칸이다. 줄 꼴은 더하기만 한다(앞 열쇠의 차례 그대로 — 읽개는 모르는
    열쇠를 버린다)."""
    assert "runId" not in RECORD.to_json()
    with_run = replace(RECORD, run_id="42", body=RecordBody(request={}, response_text=None))
    assert list(with_run.to_json()) == [*ALWAYS, "runId", "body"]
    path = tmp_path / "calls.jsonl"
    JsonlFileSink(path).record(replace(RECORD, run_id="42"))
    line = json.loads(path.read_text(encoding="utf-8"))
    assert (line["runId"], list(line)[: len(ALWAYS)]) == ("42", ALWAYS)


def test_a_step_is_written_after_the_run_id_and_only_when_present(tmp_path: Path) -> None:
    """단계 이름(AD4D)도 있을 때만 있는 칸이다: runId 뒤·body 앞. 앞 열쇠의 차례는 그대로다."""
    assert "step" not in replace(RECORD, run_id="42").to_json()
    with_step = replace(RECORD, run_id="42", step="judge", body=RecordBody(request={}, response_text=None))
    assert list(with_step.to_json()) == [*ALWAYS, "runId", "step", "body"]
    path = tmp_path / "calls.jsonl"
    JsonlFileSink(path).record(replace(RECORD, run_id="42", step="judge"))
    line = json.loads(path.read_text(encoding="utf-8"))
    assert (line["step"], list(line)[: len(ALWAYS)]) == ("judge", ALWAYS)
    memory = MemorySink()
    memory.record(replace(RECORD, step="judge"))
    assert [r.step for r in memory.records] == ["judge"]


def test_the_table_row_carries_the_step_both_ways_without_the_database() -> None:
    """행 ↔ 기록(sink_db.row_from_record·record_from_row)에 단계가 실린다 — 저장하지 않는 순수 왕복. 없으면 NULL."""
    with_step = replace(RECORD, tenant="7", run_id="42", step="judge")
    row = row_from_record(with_step, company_id=7)
    assert (row.run_id, row.step) == (42, "judge")
    assert record_from_row(row).to_json() == with_step.to_json()
    plain = row_from_record(replace(RECORD, tenant="7", run_id="42"), company_id=7)
    assert plain.step is None
    assert "step" not in record_from_row(plain).to_json()
