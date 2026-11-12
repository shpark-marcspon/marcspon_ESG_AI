"""호출 감사 기록. 공급사를 한 번 부를 때마다(재시도, 대체 호출 포함) 한 줄이 남는다.

본문(요청·응답 글자)은 기본으로 남기지 않는다(공시 전 고객 데이터). 해시만 남겨 같은 입력인지 견줄 수 있게 한다.

「칸 없음」과 None 은 뜻이 다르다. `error_status`·`previous_error_status` 는
    칸 없음(MISSING) = 공급사 오류가 아니다 / 재시도한 시도가 아니다
    None            = 공급사 오류인데 상태 코드 없이 실패했다(연결 실패 등)
이라서 None 으로 접지 않고 없음 표지(MISSING)를 따로 둔다. JSON 으로 낼 때 MISSING 인 칸은 내지 않는다.
그 밖의 「있을 때만 있는 칸」(thinking_tokens 등)은 None 이 「없음」이고, 역시 JSON 에 내지 않는다.
"""

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Final, Protocol

from esgapi.core.llm.types import LlmResultKind, Scope, WarningCode


class Missing(Enum):
    MISSING = "missing"


MISSING: Final = Missing.MISSING


@dataclass(frozen=True)
class RecordBody:
    """`store_bodies` 를 켰을 때만 남는다."""

    request: dict[str, object]
    response_text: str | None


@dataclass(frozen=True)
class CallRecord:
    ts: str
    call_id: str
    attempt: int
    provider: str | None
    model: str | None
    api_model_id: str | None
    # 공급사가 응답에 적은 모델 ID. 응답을 못 받았거나 공급사가 적지 않았으면 None.
    response_model_id: str | None
    prompt_id: str
    prompt_version: int
    template_hash: str
    # 조립된 요청 본문의 sha256. 본문을 저장하지 않아도 같은 입력인지 견줄 수 있다.
    request_hash: str
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    cost_usd: float | None
    duration_ms: float
    result_kind: LlmResultKind
    tenant: str
    module: str
    warnings: tuple[WarningCode, ...]
    # ── 있을 때만 있는 칸 ──
    # 공급사가 생각·추론 토큰 수를 보고했을 때만. `output_tokens` 에 이미 든 몫이다.
    thinking_tokens: int | None = None
    # 공급사 오류(provider_error)일 때만: HTTP 상태 코드. 상태 없이 실패했으면 None.
    error_status: int | Missing | None = MISSING
    # 공급사 오류에 공급사가 「이만큼 뒤에 다시」를 알려 줬을 때만(ms).
    retry_after_ms: int | None = None
    # 공급사 오류 뒤에 같은 모델을 다시 부른 시도일 때만(재시도 도중 상한에 막힌 줄 포함).
    # provider_retry 는 몇 번째 재시도인지(1부터), previous_error_status 는 바로 앞 시도의 오류 상태 코드,
    # retry_wait_ms 는 이 시도 전에 기다린 시간이다. 기다린 시간은 duration_ms 에 들어 있지 않다.
    provider_retry: int | None = None
    previous_error_status: int | Missing | None = MISSING
    retry_wait_ms: float | None = None
    body: RecordBody | None = None
    # 임베딩 호출일 때만: 이 요청(묶음)에 실은 입력 수. 임베딩 줄의 prompt_id 는 "embedding" 이다(embedding.py).
    embedding_inputs: int | None = None
    # 실행기가 지은 클라이언트의 호출일 때만: 그 실행의 id(십진 숫자 글자 — X1b-1). 실행 하나의 싱크가 기록마다 덮어
    # 적는다(꼬리표 Tags 와 무관). 그 밖(동기 계산·관리 명령)은 None.
    run_id: str | None = None
    # 실행기가 지은 클라이언트의 호출일 때만: 그 호출이 일어난 단계 이름(AD4D — 실행의 싱크가 run_id 와 함께 덮어
    # 적는다). 단계 사이·실행 밖의 호출과 AD4D 앞의 기록은 None.
    step: str | None = None
    # 실행기가 지은 클라이언트의 호출이 펼침 단계의 구획 안에서 일어났을 때만: 그 구획 열쇠의 sha256(16진 64자 —
    # core/flows/types.segment_key_sha256, RM1a). 실행의 싱크가 step 과 함께 덮어 적는다. 장벽 단계·구획 밖은 None.
    segment: str | None = None
    # 공급사가 과금했을 수 있는 실패 시도(시간 초과·상태 없는 실패·2xx 스트림 오류)의 보수 어림(USD — LH2,
    # MARC-ISSUE-411 S2). 그 시도의 한 번 최악(client.py·embedding.py). **상한 셈 전용**: cost_usd(장부 — 실비만)와
    # 따로이고 to_json·DB(sink_db.py)에 싣지 않는다. 그래서 DB 왕복에서 사라진다(sink_db.record_from_row 가 되살린
    # 줄에는 없다). 실행기의 싱크(runs/context.RunCallSink)가 그 시도의 live 상한 셈에만 더한다. 성공·HTTP 상태로
    # 거절된 실패는 None.
    cost_bound_usd: float | None = None
    # 공급사 오류(provider_error) 줄일 때만: 그 오류의 이름(types.ErrorKind — LB1). to_json 에는 있을 때만 `errorKind`
    # (`errorStatus` 바로 뒤). ★ DB(sink_db.py)에는 칸이 없어 왕복에서 사라진다(LB1 Q1 (가)) — DB 줄에서 되읽는 것은
    # error_status 뿐이라 크레딧 소진 429 ↔ 속도 429, 스트림 중 과부하(200) ↔ 다른 200 오류는 DB 로 가르지 못한다.
    error_kind: str | None = None

    def to_json(self) -> dict[str, object]:
        """기록 한 줄의 JSON 꼴. 열쇠의 이름과 순서, 「칸 없음」은 esg-lab 의 CallRecord 와 같다."""
        out: dict[str, object] = {
            "ts": self.ts,
            "callId": self.call_id,
            "attempt": self.attempt,
            "provider": self.provider,
            "model": self.model,
            "apiModelId": self.api_model_id,
            "responseModelId": self.response_model_id,
            "promptId": self.prompt_id,
            "promptVersion": self.prompt_version,
            "templateHash": self.template_hash,
            "requestHash": self.request_hash,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "cacheReadTokens": self.cache_read_tokens,
            "cacheWriteTokens": self.cache_write_tokens,
        }
        if self.thinking_tokens is not None:
            out["thinkingTokens"] = self.thinking_tokens
        if self.error_status is not MISSING:
            out["errorStatus"] = self.error_status
        if self.error_kind is not None:
            out["errorKind"] = self.error_kind
        if self.retry_after_ms is not None:
            out["retryAfterMs"] = self.retry_after_ms
        if self.provider_retry is not None:
            out["providerRetry"] = self.provider_retry
        if self.previous_error_status is not MISSING:
            out["previousErrorStatus"] = self.previous_error_status
        if self.retry_wait_ms is not None:
            out["retryWaitMs"] = self.retry_wait_ms
        out.update(
            {
                "costUsd": self.cost_usd,
                "durationMs": self.duration_ms,
                "resultKind": self.result_kind,
                "tenant": self.tenant,
                "module": self.module,
                "warnings": list(self.warnings),
            }
        )
        if self.embedding_inputs is not None:
            out["embeddingInputs"] = self.embedding_inputs
        if self.run_id is not None:
            out["runId"] = self.run_id
        if self.step is not None:
            out["step"] = self.step
        if self.segment is not None:  # 장벽 흐름의 줄은 바이트 그대로(칸 없음)
            out["segment"] = self.segment
        if self.body is not None:
            out["body"] = {"request": self.body.request, "responseText": self.body.response_text}
        return out


class CallLogSink(Protocol):
    def record(self, record: CallRecord) -> None:
        """기록 한 줄을 남긴다."""
        ...

    def spent(self, scope: Scope) -> float:
        """`scope` 에 드는 호출의 누적 비용(USD). 예산 상한이 호출 직전에 이것을 읽는다."""
        ...


def json_line(value: object) -> str:
    """한 줄 JSON. 한글을 \\u 로 바꾸지 않고, 빈칸을 넣지 않는다."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(value: object) -> str:
    """값의 sha256. 직렬화 규칙: 열쇠를 정렬하고 빈칸 없이, 한글은 그대로, UTF-8.

    esg-lab 의 `JSON.stringify` 와 같은 바이트를 내지는 않는다(거기는 열쇠를 넣은 순서대로 낸다).
    해시는 한 기록 안에서 「같은 입력인가」를 견주는 데만 쓰고, esg-lab 의 기록과 견주지 않는다.
    """
    return sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
