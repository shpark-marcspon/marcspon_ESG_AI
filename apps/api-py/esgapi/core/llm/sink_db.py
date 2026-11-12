"""호출 기록을 DB 의 표(core_llm_call_logs, 모델 LlmCallLogRow)에 쓰는 싱크. ★ Django 를 안다(순수성 계약 밖).

    LLM_LOG_SINK=db  →  setup.make_sink 가 이것을 세운다.  관리 명령은 --sink db --tenant <회사 id>.

이 파일이 sinks/ 폴더가 아니라 core/llm 바로 아래에 있는 까닭: 순수성 계약이 sinks 를 폴더째 문다(그 아래는 Django 를
모른다). Django 를 아는 파일은 이제 셋이다: setup.py, 이 파일, 관리 명령(management/commands/llm_call.py).

── 한 줄을 쓰는 법 (record) ──
  - 행의 company_id 는 **꼬리표(Tags.tenant)에 적힌 회사 id** 다(십진 숫자 글자 — COMPANY_ID_TEXT). 부르는 쪽이
    세션의 company_id(관리 명령은 --tenant)에서 꼬리표를 만든다(inventory 의 경로, management/commands/llm_call.py).
    꼬리표의 칸 이름 tenant 는 그대로다(이름 바꾸기는 C1). 기록 한 줄로 되돌릴 때 꼬리표는 str(company_id) 다.
    무효 조건: 꼬리표를 틀리게 주는 코드가 생기면 그 줄은 남의 회사의 감사 기록·상한 누계로 간다(알리는 갈래가 없다).
  - INSERT 는 제 블록 안에서 한다. 트랜잭션 밖이면 그 블록이 곧 트랜잭션이라 줄마다 커밋되고, 바깥 트랜잭션 안이면
    세이브포인트라 실패해도 바깥은 그대로 쓸 수 있다.
    record 는 예외를 밖으로 던지지 않는다: 실패는 갈래(WriteFailed)와 logging 한 줄로 남는다.
  - 본문(요청·응답 글자)은 쓰지 않는다. 칸이 없다(공시 전 고객 데이터). setup.build_client 가 db 싱크와
    store_bodies 의 조합을 LiveSetupError 로 막는다. 그 문을 지나지 않고 본문이 든 기록이 오면 본문만 버리고
    줄은 쓰며, 버렸다는 것을 logging 으로 남긴다.

── 기록 갈래 다섯 (싱크가 쥔다: `outcomes`. CallLogSink.record 는 None 을 돌려주는 프로토콜이다) ──
    Written                 썼다
    NoTenant                쓰지 않았다: 꼬리표가 회사 id 의 꼴(COMPANY_ID_TEXT)이 아니다(빈 글자·0·"01" 포함)
                            (INSERT 를 시도하지 않는다)
    BadRun                  쓰지 않았다: 실행 id(CallRecord.run_id, X1b-1)가 있는데 십진 숫자의 꼴
                            (같은 COMPANY_ID_TEXT)이 아니다. NULL 로 접어 쓰지 않는다(실행의 줄이 실행 밖 줄로
                            섞이지 않게). INSERT 를 시도하지 않는다
    BadStep                 쓰지 않았다: 단계 이름(CallRecord.step, AD4D)이 있는데 1~100자가 아니다(run_steps.name 의
                            상한과 같다). NULL 로 접어 쓰지 않는다(BadRun 과 같은 까닭). INSERT 를 시도하지 않는다
    WriteFailed             쓰려 했으나 DB 가 거절했다(제약·길이·권한·깨진 트랜잭션 등). 예외 이름과 SQLSTATE 만 남긴다
  Written 이 아닌 것마다 logger `esgapi.core.llm.sink_db` 에 한 줄(쓰지 못한 줄은 to_json() 그대로.
  본문·키·오류 문장은 싣지 않는다).

── 누적 비용 (spent) 과 「상한」의 뜻 ──
  메모리 누계: 이 객체가 본 기록 **전부**(쓰였든 아니든)의 비용을 (꼬리표, 모듈)별로 더해 쥔다.
               열쇠는 꼬리표의 글자다(행에 쓴 회사 id 의 글자와 같다).
  DB 합계    : `scope.tenant` 가 회사 id 의 꼴(COMPANY_ID_TEXT)이면 트랜잭션 안이든 밖이든 묻는다.
               LlmCallLogRow.for_company(int(scope.tenant))
               — WHERE company_id = … 가 늘 붙는다. 그때의 답은 max(DB 합계, 메모리 누계) 다.
  그 밖(전역 Scope(), 모듈만, 꼴 밖의 꼬리표)은 메모리 누계만이다: 회사를 가로지르는 합계는 묻지 않는다
  (꼴 밖의 꼬리표로는 행이 쓰이지 않으므로 DB 합계는 0 이다).

  ★ DB 합계도 메모리 누계도 실제 지출의 **하한**이고, 둘의 큰 쪽도 하한이다. 상한은 「하한이 닿으면 막는다」이고
    실제 지출은 넘을 수 있다. 「프로세스를 넘는 상한이 섰다」가 아니다. 선 것은 「커밋된 행은 일꾼을 넘어 센다」까지다.
    세지 못하는 몫:
      - 다른 일꾼의 미커밋 행(바깥 트랜잭션 안에서 쓰여 아직 커밋되지 않은 줄)
      - 다른 일꾼의, 블록 안에서 되돌려진 줄의 비용(그 비용은 그 일꾼의 메모리 누계에만 있다). 요청은 이제
        롤백하지 않는다(요청마다의 트랜잭션이 없다). 이 프로세스 안에서 되돌려진 비용은 이 객체의 메모리 누계가 잡는다
      - 전역·모듈 범위에서는 다른 일꾼의 것 전부
      - 일꾼이 죽으면(gunicorn timeout 30초 포함) 그 일꾼의 메모리 누계가 사라진다. 이미 커밋된 줄은 남지만(트랜잭션
        밖에서는 줄마다 커밋), 줄을 쓰기 전에 죽은 호출의 비용은 어디에도 세어지지 않는다
    최악은 여전히 「상한 × 일꾼 수」쯤이다(일꾼마다 다른 일꾼의 되돌려진 비용을 못 본다). 드물어질 뿐이다.
  ★ 꼬리표를 틀리게 준 호출의 비용은 꼬리표의 회사의 상한에 든다(BudgetGuard.check 도 상한을 꼬리표로 고른다 —
    budget.py). 진짜 회사의 상한은 그 비용을 못 본다. 꼬리표를 세션에서 만드는 일은 호출하는 모듈의 거리다.
  ★ 요청 트랜잭션에 기대지 않는다(별도 연결도 쓰지 않는다). LLM 호출을 트랜잭션 블록 안에서 하지 않는다: 블록이
    되돌려지면 그 줄도 사라진다(core/tests/test_transaction_rules.py 의 순수 검사가 블록 안의 `call` 을 막는다).
  ★ 잠금이 있는 것은 메모리 누계와 outcomes 뿐이다. DB 연결은 Django 가 스레드마다 따로 준다.

── 표에 칸이 없는 기록 칸 (왕복에서 사라진다) ──
  `cost_bound_usd`(상한 셈 전용)·`embedding_inputs`·`error_kind`(공급사 오류의 이름 — LB1 Q1 (가), 마이그레이션 0).
  ★ 무효 조건(error_kind): DB 줄로는 error_status 로만 가른다(429·529·5xx·상태 없음). 못 가르는 둘 — 크레딧·지출 소진
    429 ↔ 속도 429, 스트림 중 과부하(200) ↔ 다른 200 오류. 실행 층(안 B)이 DB 로 「몇 번 막혔나」를 셀 때 이것이
    모자라면 칸을 더한다(core 마이그레이션).
"""

import logging
import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final, Literal, cast

from django.db import DatabaseError, transaction
from django.db.models import Sum

from esgapi.core.calc.documents import COMPANY_ID_TEXT
from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.log import MISSING, CallRecord, json_line
from esgapi.core.llm.types import LlmResultKind, Scope, WarningCode
from esgapi.core.models import LlmCallLogRow

logger = logging.getLogger(__name__)

_COST_PLACES: Final = Decimal("0.00000001")
# 단계 이름의 길이 상한(runs 의 RunStepRow.name 과 같다 — 여기서 runs 를 import 하지 않는다).
STEP_MAX_LENGTH: Final = 100
# `outcomes` 가 쥐는 갈래의 수. 프로세스가 오래 살아도 자라지 않게 가장 최근 것만 둔다.
OUTCOMES_KEPT: Final = 1000


@dataclass(frozen=True)
class Written:
    kind: Literal["written"] = "written"


@dataclass(frozen=True)
class NoTenant:
    kind: Literal["no_tenant"] = "no_tenant"


@dataclass(frozen=True)
class BadRun:
    kind: Literal["bad_run"] = "bad_run"


@dataclass(frozen=True)
class BadStep:
    kind: Literal["bad_step"] = "bad_step"


@dataclass(frozen=True)
class WriteFailed:
    """`error_class` 는 예외의 이름, `sqlstate` 는 DB 가 준 다섯 글자 코드(DB 까지 못 갔으면 None). 오류 문장은 없다."""

    error_class: str
    sqlstate: str | None
    kind: Literal["write_failed"] = "write_failed"


type RecordOutcome = Written | NoTenant | BadRun | BadStep | WriteFailed


def row_from_record(record: CallRecord, *, company_id: int) -> LlmCallLogRow:
    """기록 한 줄 → 행(저장하지 않는다). `company_id` 는 꼬리표에 적힌 회사 id 다. 본문은 옮기지 않는다."""
    return LlmCallLogRow(
        company_id=company_id,
        module=record.module,
        ts=datetime.fromisoformat(record.ts),
        call_id=record.call_id,
        attempt=record.attempt,
        provider=record.provider,
        model=record.model,
        api_model_id=record.api_model_id,
        response_model_id=record.response_model_id,
        prompt_id=record.prompt_id,
        prompt_version=record.prompt_version,
        template_hash=record.template_hash,
        request_hash=record.request_hash,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        cache_read_tokens=record.cache_read_tokens,
        cache_write_tokens=record.cache_write_tokens,
        thinking_tokens=record.thinking_tokens,
        # float 을 글자로 거쳐 Decimal 로(0.0001 이 0.000100000000000000004… 가 되지 않게). 8자리에서 맞춘다.
        cost_usd=None if record.cost_usd is None else Decimal(str(record.cost_usd)).quantize(_COST_PLACES),
        duration_ms=record.duration_ms,
        result_kind=record.result_kind,
        warnings=list(record.warnings),
        retry_after_ms=record.retry_after_ms,
        provider_retry=record.provider_retry,
        retry_wait_ms=record.retry_wait_ms,
        has_error_status=record.error_status is not MISSING,
        error_status=None if record.error_status is MISSING else record.error_status,
        has_previous_error_status=record.previous_error_status is not MISSING,
        previous_error_status=None if record.previous_error_status is MISSING else record.previous_error_status,
        run_id=None if record.run_id is None else int(record.run_id),
        step=record.step,
        segment=record.segment,  # 구획 열쇠 sha(RM1a). 64자를 넘으면 DB 가 거절한다(WriteFailed)
    )


def record_from_row(row: LlmCallLogRow) -> CallRecord:
    """행 → 기록 한 줄. `to_json()` 이 쓰기 전의 것과 같다(값으로. 아래 무효 조건).

    `tenant` 는 str(company_id) 로 돌아간다: 기록 한 줄의 tenant 는 원래 꼬리표이고,
    쓰인 꼬리표는 회사 id 의 글자뿐이다.
    무효 조건:
      - `ts` 는 밀리초까지의 UTC 글자(…Z)일 때 같은 글자로 돌아온다(client._iso 가 내는 꼴). 다른 꼴(마이크로초,
        다른 시간대 표기)은 같은 시각의 …Z 로 바뀐다.
      - `cost_usd` 는 1e-8 달러에서 반올림된 값일 때 같다(client 가 늘 round_usd 를 거친다).
      - 수는 값으로 같다. `duration_ms`·`retry_wait_ms` 는 float 칸이라 12 가 12.0 으로 돌아온다(JSON 글자는 다르다).
    """
    return CallRecord(
        ts=row.ts.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        call_id=row.call_id,
        attempt=row.attempt,
        provider=row.provider,
        model=row.model,
        api_model_id=row.api_model_id,
        response_model_id=row.response_model_id,
        prompt_id=row.prompt_id,
        prompt_version=row.prompt_version,
        template_hash=row.template_hash,
        request_hash=row.request_hash,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        cache_read_tokens=row.cache_read_tokens,
        cache_write_tokens=row.cache_write_tokens,
        cost_usd=None if row.cost_usd is None else float(row.cost_usd),
        duration_ms=row.duration_ms,
        result_kind=cast("LlmResultKind", row.result_kind),
        tenant=str(row.company_id),
        module=row.module,
        warnings=tuple(cast("list[WarningCode]", row.warnings)),
        thinking_tokens=row.thinking_tokens,
        error_status=row.error_status if row.has_error_status else MISSING,
        retry_after_ms=row.retry_after_ms,
        provider_retry=row.provider_retry,
        previous_error_status=row.previous_error_status if row.has_previous_error_status else MISSING,
        retry_wait_ms=row.retry_wait_ms,
        run_id=None if row.run_id is None else str(row.run_id),
        step=row.step,
        segment=row.segment,
    )


def _sqlstate(error: BaseException) -> str | None:
    """Django 의 DB 예외는 psycopg 의 예외를 __cause__ 로 품는다. 거기의 SQLSTATE."""
    for candidate in (error, error.__cause__):
        code = cast("object", getattr(candidate, "sqlstate", None))
        if isinstance(code, str):
            return code
    return None


class DbSink:
    """`CallLogSink` 의 DB 구현. 프로세스마다 하나를 세워 다시 쓴다(메모리 누계가 이 객체에 있다)."""

    # 본문을 받지 않는다. setup.build_client 가 이것을 보고 store_bodies 와의 조합을 막는다.
    accepts_bodies: Final = False

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ledger: dict[tuple[str, str], float] = {}
        self._outcomes: deque[RecordOutcome] = deque(maxlen=OUTCOMES_KEPT)

    @property
    def outcomes(self) -> tuple[RecordOutcome, ...]:
        """이 객체가 본 기록의 갈래(오래된 것부터, 가장 최근 OUTCOMES_KEPT 개)."""
        with self._lock:
            return tuple(self._outcomes)

    def record(self, record: CallRecord) -> None:
        outcome = self._write(record)
        with self._lock:
            self._outcomes.append(outcome)
            if record.cost_usd is not None:
                key = (record.tenant, record.module)
                self._ledger[key] = self._ledger.get(key, 0.0) + record.cost_usd
        if record.body is not None:
            logger.warning("LLM 호출 기록의 본문을 버렸다(DB 싱크는 본문을 쓰지 않는다) callId=%s", record.call_id)
        if not isinstance(outcome, Written):
            logger.warning(
                "LLM 호출 기록 %s: %s %s",
                outcome.kind,
                outcome,
                # 쓰지 못한 줄은 여기에만 남는다. 본문은 싣지 않는다.
                json_line(_without_body(record)),
            )

    def _write(self, record: CallRecord) -> RecordOutcome:
        """던지지 않는다."""
        if not COMPANY_ID_TEXT.match(record.tenant):
            return NoTenant()
        if record.run_id is not None and not COMPANY_ID_TEXT.match(record.run_id):
            return BadRun()
        if record.step is not None and not 1 <= len(record.step) <= STEP_MAX_LENGTH:
            return BadStep()
        try:
            # 트랜잭션 밖이면 이 블록이 곧 트랜잭션이다(나가면 커밋). 안이면 세이브포인트(바깥은 이어 쓸 수 있다.
            # 바깥이 이미 깨져 있으면 이 블록이 던진다).
            with transaction.atomic():
                row_from_record(record, company_id=int(record.tenant)).save(force_insert=True)
        except (DatabaseError, ValueError, ArithmeticError) as error:
            # 예외는 세이브포인트 블록 **밖에서** 잡는다(안에서 잡으면 Django 가 되돌리지 않아 바깥이 깨진 채 남는다).
            # ValueError·ArithmeticError: DB 에 가기 전에 값을 바꾸다 난 것(ts 의 꼴, 비용이 수가 아님).
            return WriteFailed(error_class=type(error).__name__, sqlstate=_sqlstate(error))
        return Written()

    def spent(self, scope: Scope) -> float:
        """`scope` 의 누적 비용(USD)의 **하한**. 머리말의 「상한의 뜻」. 던지지 않는다."""
        with self._lock:
            memory = round_usd(
                sum(cost for (tenant, module), cost in self._ledger.items() if scope.matches(tenant, module))
            )
        if scope.tenant is None or not COMPANY_ID_TEXT.match(scope.tenant):
            return memory  # 빈 글자·꼴 밖도 여기서 돌아간다(for_company 는 양의 정수만 받아 아래가 못 잡는다)
        try:
            with transaction.atomic():
                rows = LlmCallLogRow.for_company(int(scope.tenant))
                if scope.module is not None:
                    rows = rows.filter(module=scope.module)
                total = cast("Decimal | None", rows.aggregate(total=Sum("cost_usd"))["total"])
        except DatabaseError:
            return memory
        return max(round_usd(float(total or 0)), memory)


def _without_body(record: CallRecord) -> dict[str, object]:
    line = record.to_json()
    line.pop("body", None)
    return line
