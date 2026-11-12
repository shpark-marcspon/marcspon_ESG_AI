# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""흐름의 실행 하나를 돌리는 태스크(`runs.execute` — X1b-1). 얇다: 잡기 → 문서 바이트 → 흐름 → 출력 쓰기 → 끝내기.
규칙은 다른 곳에 있다(runs/service/services/runs.py 의 잡기·사건·끝내기, runs/calc/ 의 판정·키·마감·오류 code,
core/flows 의 흐름과 끼움). 모델을 직접 import 하지 않는다(`.importlinter` 계약 라: `esgapi.*.tasks`).

쪽지에는 `company_id` 와 `run_id` 뿐이다(둘 다 십진 숫자 글자 — core/resources/queue.py 의 enqueue_run).

    T1  with transaction.atomic(durable=True):  claim_run           행을 잠그고 `processing` 으로. 커밋한다
        ── 트랜잭션 밖 ──  문서 get(문서 없는 흐름은 0 — ND1) → 끼움(BINDINGS) → 이어 갈 자리(끝난 단계 =
                           carried, 첫 끝나지 않은 단계의 부분 = resume, 파일은 저장소에서 다시 읽음 — 옮긴 단계의 새
                           키가 비었고 이어 돈 실행이면 앞 실행(사슬)의 키에서 옮겨 쓴다, RC1) →
                           run_flow(…, events=행 쓰는 사건) → 출력 파일 put
        사건(단계 시작·체크포인트·단계 끝남)마다  with transaction.atomic(durable=True):
                                                  단계 행 하나(+ 울타리·임대 당김)
        구획 사건(계획·구획 시작·끝·실패 — RM1a)마다 같은 꼴: 구획 행(+ 울타리·임대 당김), 닫은 뒤 울타리·마감
    T2  with transaction.atomic(durable=True):  finish_run          done·failed, 또는 queued(다시 넣기)

★ 회사는 블록마다 인자로 넘긴다. 쪽지의 두 값이 십진 숫자 글자가 아니면 조회하지 않고 「없음」으로 건너뛴다.
★ 저장소·흐름·LLM 은 트랜잭션 밖이다. 단계의 파일 put 도 그 단계의 행 블록 **앞**에서 한다(행은 쓰기가 끝난 뒤).
★ 협조 마감(runs/calc/deadline.py): 사건 받는 쪽이 자기 블록을 닫은 뒤 마감(시도 시작 + 소프트 제한 − 60초)을 지났으면
  RunYield(BaseException)를 낸다. 흐름·단계·LLM 의 `except Exception` 이 잡지 못해 run_flow 밖으로 바로 온다. 내 시도가
  울타리에서 밀려났을 때(Superseded)도 같다. 태스크가 잡아 RunDeferred 로 끝낸다(밖으로 내지 않는다).
★ 끝내는 갈래(위에서부터 — outcome_of):
    RunYield                                              RunDeferred
    잠깐 오류 — SoftTimeLimitExceeded · RunRetryLater · DB 의 OperationalError·InterfaceError · 임베딩의
      EmbeddingFailed(시간 초과·retryable 공급사 오류). 사건 쪽에서 직접, 또는 FlowStepFailed 의 __cause__   RunDeferred
    저장소 거절(StorageRefused — 파일 put 의 403)      RunFailed(None, storage_denied)
    이어 돌기의 옮김(_plan — RC1): 앞 키 get·새 키 put 에 닿지 못함   RunDeferred
                                  새 키 put 거절                     RunFailed(None, storage_denied)
                                  사슬 어디에도 바이트 없음          RunFailed(None, object_missing)
    그 밖의 FlowStepFailed                          RunFailed(그 단계, 예외 클래스의 고정 표 — runs/calc/errors.py)
    그 밖                                           RunFailed(None, 표의 code 또는 internal)
  run_flow 밖(문서 get·출력 put)의 소프트 제한·저장소에 못 닿음도 RunDeferred 다. 예외의 원문은 logger 에만 남긴다.
  ★ 소프트 제한이 LLM 호출 안에서 나면 호출 층은 그것을 다시 던진다(LH2 — core/llm/errors.soft_deadline_in, 그 시도의
    timeout 줄 하나를 쓴 뒤) — 흐름이 `except Exception` 으로 삼키면 그 흐름의 일이다. 주 길은 여전히 협조 마감이다.
★ T2 블록이 DB 오류로 되돌려지면 RunDeferred 의 T2 를 한 번 더 한다(그것도 실패하면 행은 processing — 임대가 끝난 뒤
  requeue_runs 가 메운다). RunUpdateError(행 수가 틀림)는 잡지 않는다.
★ 다시 넣기는 늘 `self.retry(countdown=…, max_retries=None)` 다(Celery 기본 3 이 시도 상한의 셈을 넷째에서 끊지 않게 —
  상한은 잡기의 Exhausted 가 진행 없이 끝난 시도만 세어 건다).
★ 한 번만 「끝난다」이지 한 번만 「돈다」가 아니다: 임대가 끝난 뒤 이어받으면 단계·LLM 이 두 번 불릴 수 있다.
★ 펼침 단계(RM1a): 이어 도는 시도는 그 실행 안에서 끝난 구획(done·failed — selectors.ended_segments)을 run_flow 의
  segments_done 으로 받아 다시 부르지 않는다. 구획의 잠깐 오류는 행을 쓰지 않고 다시 던진다(다음 시도가 그 구획을 다시
  부른다). 영구 실패는 구획 행 failed + 표의 code(step_error_code). 계획이 저장된 것과 다르면 segments_mismatch.
  이어 돈 실행·고른 다시(RM1c)는 실행 만들기가 앞 실행의 끝난 구획을 attempts 0 으로 옮겨 두므로 같은 길로 다시 부르지
  않는다(이 파일 0줄). 무효 조건: 옮긴 열쇠가 새 계획과 다르면(파서 판만 바뀐 배포) 첫 시도 segments_mismatch 다 — 그
  실행을 다시 이어 돌면 시작 단계를 처음부터 계획한다(actions/runs.py 머리말).
★ 구획 쪽지(RM1b — `runs.segment`, execute_segment): 상한(segment_parallel — 기본 2)이 2 이상이면 지휘 시도 k 는
  펼침에 닿아 구획을 돌지 않고 RunParked(BaseException)로 나와 끝내기 블록(T2)에 주차를 적고, 커밋 뒤 쪽지
  min(상한, 끝나지 않은 수)개를 넣는다. 쪽지는 잡기 블록(U1) → 블록 밖(문서·이어 갈 자리·끼움·plan_segments·
  run_segment — 쪽지마다 다시 짓는다) → 끝냄 블록(U2) 이고, 블록이 깨우기를 만들면 커밋 뒤 지휘 쪽지 하나
  (enqueue_run), 아니면 이어 넣기 판정대로 쪽지 하나(놓음 뒤에는 retry_delay_s 뒤). 상한 1 = RM1a 직렬(쪽지 0).
  치명 여섯(runs/calc/errors.RUN_FATAL_ERRORS)은 직렬·쪽지 모두 실행 failed·failed_step = 펼침.
  끝냄 블록이 DB 오류로 되돌려지면 다시 하지 않는다(그 구획은 running 그대로 — 임대 뒤 다른 쪽지가 이어받는다).

★ 테스트가 바꿔 끼우는 틈(전부 「부를 때 모듈 속성으로 읽는다」):
    documents.default_storage · documents.max_upload_bytes   저장소와 상한(core/service/services/documents.py 의 틈)
    tasks.job_settings · tasks.clock · tasks.monotonic · tasks.soft_limit_s   임대·시도의 수, 시계, 마감
    context.call_sink · context.llm_settings                 LLM 기록 싱크의 바닥과 설정(runs/context.py)
  pytest 프로세스 안에서 진짜 워커를 띄우지 않는다. 태스크는 함수를 직접 불러 잰다.
"""

import hashlib
import logging
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, NoReturn, cast

from celery.exceptions import SoftTimeLimitExceeded
from django.db import DatabaseError, InterfaceError, OperationalError, transaction

from esgapi.config.celery import app
from esgapi.config.env import BrokerSettings, JobSettings
from esgapi.core.calc.documents import COMPANY_ID_TEXT
from esgapi.core.calc.jobs import RUN_TASK_NAME, SEGMENT_TASK_NAME
from esgapi.core.conf import app_config, now
from esgapi.core.flows import binding as flow_ports  # G2c2: 둘째 꼴 RunFactsBinding(isinstance 갈래)
from esgapi.core.flows.binding import BINDINGS, DocumentInput, NoBinding, RunRetryLater
from esgapi.core.flows.registry import REGISTRY
from esgapi.core.flows.run import plan_segments, run_flow, run_segment
from esgapi.core.flows.types import (
    Flow,
    FlowOutput,
    FlowRegistryError,
    FlowStepFailed,
    OutputFile,
    SegmentEnded,
    SegmentFatal,
    SegmentKey,
    SegmentOutput,
    SegmentPlanMismatch,
    StepOutput,
    segment_key_sha256,
)
from esgapi.core.llm.embedding import EmbeddingFailed, EmbedProviderFailed, EmbedTimedOut
from esgapi.core.resources import queue
from esgapi.core.resources.ports.storage import (
    ObjectBytes,
    ObjectMissing,
    ObjectStorage,
    ObjectTooLarge,
    StorageDenied,
    StorageUnavailable,
)
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.core.service.services import documents
from esgapi.runs import context
from esgapi.runs.calc.deadline import RunYield, deadline_of
from esgapi.runs.calc.errors import RUN_ERROR_MESSAGES, run_fatal, step_error_code
from esgapi.runs.calc.keys import file_key
from esgapi.runs.calc.segments import SEGMENT_PARALLEL_DEFAULT
from esgapi.runs.context import ExecutorContext, RunCallSink, StepCursor
from esgapi.runs.service.selectors import runs as selectors
from esgapi.runs.service.selectors.runs import Run, RunFile, RunNotFound
from esgapi.runs.service.services import resume
from esgapi.runs.service.services import runs as services
from esgapi.runs.service.services.runs import (
    Claimed,
    EndDone,
    Ended,
    EndFailed,
    EndFatal,
    EndReleased,
    Finished,
    NothingToClaim,
    PlanMismatch,
    RunDeferred,
    RunDone,
    RunFailed,
    RunOutcome,
    RunParkedOutcome,
    SegmentAlreadyEnded,
    SegmentClaimed,
    SegmentEndOutcome,
    StoredFile,
    Superseded,
)

logger = logging.getLogger(__name__)

# 문서의 꼴. 올림은 PDF 만 받는다(core 의 문서 표에 꼴 칸이 없다 — 추정, 꼴 칸이 서면 그 값으로).
DOCUMENT_MEDIA_TYPE: Final = "application/pdf"


def job_settings() -> JobSettings:
    """임대·시도 상한·다시 넣기까지의 수(일감과 같은 설정). ★ 이음매다."""
    return app_config().jobs


def clock() -> datetime:
    """지금(행에 적는 시각). ★ 이음매다."""
    return now()


def monotonic() -> float:
    """시도의 마감을 재는 시계. ★ 이음매다."""
    return time.monotonic()


def segment_parallel() -> int:
    """실행 하나의 동시 구획 상한(RM1b — runs/calc/segments.py 의 기본). 1 이면 RM1a 직렬(쪽지 0). ★ 이음매다."""
    return SEGMENT_PARALLEL_DEFAULT


def soft_limit_s() -> int:
    """워커의 소프트 시간 제한(초). 브로커 설정이 없으면 그 기본값. ★ 이음매다."""
    broker = app_config().broker
    return BrokerSettings.task_soft_time_limit_s if broker is None else broker.task_soft_time_limit_s


class StorageRefused(Exception):
    """파일을 저장소에 쓰려 했는데 거절됐다(403). 다시 해도 안 된다 — 실행 failed·storage_denied."""


def _failed(code: str, step: str | None = None) -> RunFailed:
    return RunFailed(step=step, code=code, message=RUN_ERROR_MESSAGES[code])


def _transient(err: BaseException) -> bool:
    if isinstance(err, SoftTimeLimitExceeded | RunRetryLater | OperationalError | InterfaceError):
        return True
    if isinstance(err, EmbeddingFailed):
        result = err.result
        return isinstance(result, EmbedTimedOut) or (isinstance(result, EmbedProviderFailed) and result.retryable)
    return False


def outcome_of(err: Exception, *, run_id: int) -> RunOutcome:
    """시도 중에 난 예외 → 끝내는 갈래(머리말의 표). 원문은 로그에만."""
    if isinstance(err, FlowStepFailed):
        cause = err.__cause__
        if cause is not None and _transient(cause):
            logger.info("run_deferred run_id=%s step=%s cause=%s", run_id, err.step, type(cause).__name__)
            return RunDeferred()
        code = step_error_code(type(cause)) if cause is not None else "step_error"
        logger.error("run_step_failed run_id=%s step=%s code=%s", run_id, err.step, code, exc_info=err)
        return _failed(code, err.step)
    if _transient(err):
        logger.info("run_deferred run_id=%s cause=%s", run_id, type(err).__name__)
        return RunDeferred()
    if isinstance(err, StorageRefused):
        return _failed("storage_denied")
    code = step_error_code(type(err), default="internal")
    logger.error("run_crashed run_id=%s code=%s error=%s", run_id, code, type(err).__name__, exc_info=err)
    return _failed(code)


def _put_files(
    storage: ObjectStorage, *, company_id: int, run_id: int, step: str | None, files: tuple[OutputFile, ...]
) -> tuple[StoredFile, ...]:
    """파일을 저장소에 쓴다(트랜잭션 밖). 닿지 못하면 RunRetryLater, 거절이면 StorageRefused."""
    stored: list[StoredFile] = []
    for file in files:
        key = file_key(company_id=company_id, run_id=run_id, step=step, name=file.name)
        written = storage.put(key, content=file.content, media_type=file.media_type)
        if isinstance(written, StorageUnavailable):
            raise RunRetryLater(written.detail)
        if isinstance(written, StorageDenied):
            raise StorageRefused(written.detail)
        stored.append(
            StoredFile(
                name=file.name,
                media_type=file.media_type,
                storage_key=key,
                size_bytes=len(file.content),
                sha256=hashlib.sha256(file.content).hexdigest(),
            )
        )
    return tuple(stored)


class RowEvents:
    """흐름의 사건을 받아 단계 행에 쓴다(FlowEvents). 사건마다 durable 블록 하나, 닫은 뒤 울타리·마감을 본다.
    펼침 단계의 구획 사건(SegmentEvents — RM1a)도 같은 꼴로 구획 행에 쓴다.

    step_failed 는 행을 쓰지 않는다(메모리에만 — 단계 행 failed 는 끝내기 RunFailed 가 쓴다).
    """

    def __init__(
        self,
        *,
        company_id: int,
        run_id: int,
        attempt: int,
        deadline: float,
        lease_s: int,
        storage: ObjectStorage,
        cursor: StepCursor | None = None,
    ) -> None:
        self.company_id = company_id
        self.run_id = run_id
        self.attempt = attempt
        self.deadline = deadline
        self.lease_s = lease_s
        self.storage = storage
        self.failed: tuple[str, str] | None = None  # (단계, "<예외 클래스>: <글>") — 로그용
        # 이 시도의 LLM 싱크가 읽는 지금 단계(AD4D). 단계 본문 앞에 적고 끝·실패에 비운다.
        self.cursor = StepCursor() if cursor is None else cursor

    def _after(self, written: services.Recorded | Superseded) -> None:
        """블록을 닫은 뒤: 내 시도가 아니거나 마감을 지났으면 이 시도를 접는다."""
        if isinstance(written, Superseded):
            raise RunYield("내 시도가 더는 이 실행의 주인이 아니다")
        if monotonic() > self.deadline:
            raise RunYield("협조 마감을 지났다")

    def step_started(self, flow_id: str, step: str) -> None:
        self.cursor.current = step
        with transaction.atomic(durable=True):
            written = services.step_started(
                company_id=self.company_id,
                run_id=self.run_id,
                attempt=self.attempt,
                step=step,
                now=clock(),
                lease_s=self.lease_s,
            )
        self._after(written)

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        with transaction.atomic(durable=True):
            written = services.step_progress(
                company_id=self.company_id,
                run_id=self.run_id,
                attempt=self.attempt,
                step=step,
                done=done,
                total=total,
                partial=partial,
                now=clock(),
                lease_s=self.lease_s,
            )
        self._after(written)

    def step_finished(self, flow_id: str, step: str, output: StepOutput) -> None:
        self.cursor.current = None
        files = _put_files(
            self.storage, company_id=self.company_id, run_id=self.run_id, step=step, files=output.files
        )  # 블록 앞(트랜잭션 밖)
        with transaction.atomic(durable=True):
            written = services.step_finished(
                company_id=self.company_id,
                run_id=self.run_id,
                attempt=self.attempt,
                step=step,
                data=output.data,
                files=files,
                now=clock(),
                lease_s=self.lease_s,
            )
        if isinstance(written, Superseded):
            raise RunYield("내 시도가 더는 이 실행의 주인이 아니다")

    def step_failed(self, flow_id: str, step: str, reason: str) -> None:
        self.cursor.current = None
        self.cursor.segment = None
        self.failed = (step, reason)

    # ── 구획 사건(SegmentEvents — RM1a) ──

    def segments_planned(self, flow_id: str, step: str, keys: tuple[SegmentKey, ...]) -> None:
        with transaction.atomic(durable=True):
            written = services.segments_planned(
                company_id=self.company_id,
                run_id=self.run_id,
                attempt=self.attempt,
                step=step,
                keys=keys,
                now=clock(),
                lease_s=self.lease_s,
            )
        if isinstance(written, PlanMismatch):
            raise SegmentPlanMismatch(f"단계 {step} 의 계획 {written.planned}개가 저장된 {written.stored}개와 다르다")
        self._after(written)

    def segment_started(self, flow_id: str, step: str, key: SegmentKey) -> None:
        sha = segment_key_sha256(key)
        self.cursor.segment = sha  # 이 구획 안의 LLM 호출이 이 sha 를 싣는다
        try:
            with transaction.atomic(durable=True):
                written = services.segment_started(
                    company_id=self.company_id,
                    run_id=self.run_id,
                    attempt=self.attempt,
                    step=step,
                    key_sha256=sha,
                    now=clock(),
                    lease_s=self.lease_s,
                )
        except services.RunUpdateError:
            self.cursor.segment = None  # 구획이 시작되지 않았다(그 시도는 이 예외로 끝난다)
            raise
        self._after(written)

    def segment_finished(self, flow_id: str, step: str, key: SegmentKey, output: SegmentOutput) -> None:
        self.cursor.segment = None
        with transaction.atomic(durable=True):
            written = services.segment_finished(
                company_id=self.company_id,
                run_id=self.run_id,
                attempt=self.attempt,
                step=step,
                key_sha256=segment_key_sha256(key),
                data=output.data,
                now=clock(),
                lease_s=self.lease_s,
            )
        self._after(written)

    def segment_failed(self, flow_id: str, step: str, key: SegmentKey, err: Exception) -> str:
        """잠깐 오류면 행을 쓰지 않고 다시 던진다(다음 시도가 그 구획을 다시 부른다 — outcome_of 가 RunDeferred).
        실행 치명(runs/calc/errors.RUN_FATAL_ERRORS — RM1b)이면 행을 쓰지 않고 SegmentFatal(run_flow 가 펼침 단계의
        실패로 접는다 — outcome_of 가 원래 클래스로 code). 영구 실패면 구획 행 failed 와 표의 code 를 적고 그 code 를
        돌려준다. ★ SegmentFatal 을 던지는 받는 쪽은 이것 하나다."""
        self.cursor.segment = None
        if _transient(err):
            raise err
        if run_fatal(type(err)):  # RM1b 635-1: 실행의 치명 — 행을 쓰지 않는다(끝내기 RunFailed{펼침}가 단계 행을 쓴다)
            raise SegmentFatal(err) from err
        code = step_error_code(type(err))
        with transaction.atomic(durable=True):
            written = services.segment_failed(
                company_id=self.company_id,
                run_id=self.run_id,
                attempt=self.attempt,
                step=step,
                key_sha256=segment_key_sha256(key),
                error_code=code,
                now=clock(),
                lease_s=self.lease_s,
            )
        self._after(written)
        return code


@dataclass(frozen=True, slots=True)
class Plan:
    """이어 갈 자리. start_at 이 None 이면 단계가 전부 끝났다(assembled 가 끝 산출물)."""

    carried: dict[str, StepOutput]
    start_at: str | None
    resume: dict[str, object] | None
    assembled: FlowOutput | None
    segments_done: dict[str, dict[str, SegmentEnded]] | None = None  # 펼침 단계 → 끝난 구획(RM1a). 장벽 흐름은 None


def _flow(flow_id: str) -> Flow | None:
    try:
        return REGISTRY.get(flow_id)
    except FlowRegistryError:
        return None


def _document(storage: ObjectStorage, *, company_id: int, document_id: int) -> DocumentInput | RunFailed | RunDeferred:
    """실행의 문서를 저장소에서 읽는다(트랜잭션 밖)."""
    document = document_selectors.find_document(company_id=company_id, document_id=document_id)
    if document is None:
        return _failed("document_missing")
    got = storage.get(document.storage_key, max_bytes=documents.max_upload_bytes())
    if isinstance(got, ObjectMissing):
        return _failed("object_missing")
    if isinstance(got, ObjectTooLarge):
        return _failed("object_too_large")
    if isinstance(got, StorageDenied):
        return _failed("storage_denied")
    if isinstance(got, StorageUnavailable):
        return RunDeferred()
    if document.etag is not None and got.etag != document.etag:
        return _failed("object_changed")
    return DocumentInput(content=got.data, media_type=DOCUMENT_MEDIA_TYPE, file_name=document.file_name)


def _ancestors(*, company_id: int, run_id: int, resumed_from: int, step: str, name: str) -> Iterator[tuple[int, str]]:
    """이어 돈 사슬을 거슬러 가며 같은 (단계, 이름) 파일 행의 (앞 run id, 키)를 가까운 것부터 낸다. id 가 줄지 않으면
    멈춘다(앞 실행은 늘 먼저 만들어진다 — 고리 방어). 회사는 인자 하나(남의 회사의 실행은 selectors 가 「없음」)."""
    current: int | None = resumed_from
    below = run_id
    while current is not None and current < below:
        for file in selectors.run_files(company_id=company_id, run_id=current):
            if file.step == step and file.name == name:
                yield current, file.storage_key
        found = selectors.find_run(company_id=company_id, run_id=current)
        below, current = current, None if found is None else found.resumed_from_run_id


def _carry(
    storage: ObjectStorage, *, company_id: int, run_id: int, resumed_from: int, file: RunFile
) -> bytes | RunFailed | RunDeferred:
    """옮긴 단계의 새 키가 비었다: 앞 실행(사슬)의 키에서 옮겨 쓴다(resume.carry). 갈래마다 로그 한 줄(키·바이트 0)."""
    carried = resume.carry(
        storage,
        company_id=company_id,
        target_key=file.storage_key,
        sources=_ancestors(
            company_id=company_id, run_id=run_id, resumed_from=resumed_from, step=file.step or "", name=file.name
        ),
        size_bytes=file.size_bytes,
        media_type=file.media_type,
    )
    line = "run_resume_copy run_id=%s step=%s name=%s from_run=%s result=%s"
    if isinstance(carried, resume.Carried):
        logger.info(line, run_id, file.step, file.name, carried.from_run, "copied")
        return carried.data
    if isinstance(carried, resume.CarryUnavailable):
        logger.warning(line, run_id, file.step, file.name, resumed_from, "unavailable")
        return RunDeferred()
    if isinstance(carried, resume.CarryRefused):
        logger.warning(line, run_id, file.step, file.name, resumed_from, "refused")
        return _failed("storage_denied")
    logger.warning(line, run_id, file.step, file.name, resumed_from, "missing")
    return _failed("object_missing")


def _plan(
    storage: ObjectStorage, *, company_id: int, run_id: int, flow: Flow, resumed_from: int | None
) -> Plan | RunFailed | RunDeferred:
    """단계 행에서 이어 갈 자리를 읽는다. 끝난 단계(앞에서부터 이어진 것)의 data 와 파일(저장소에서 다시 읽음)이
    carried, 첫 끝나지 않은 단계가 start_at, 그 단계의 partial 이 resume 이다. 이어 돈 실행(resumed_from)의 새 키가
    비었으면 앞 실행(사슬)의 키에서 옮겨 쓴다(RC1 — _carry)."""
    steps = selectors.step_rows(company_id=company_id, run_id=run_id)
    if tuple(s.name for s in steps) != flow.steps:
        logger.error("run_steps_mismatch run_id=%s flow=%s", run_id, flow.id)
        return _failed("internal")
    files = selectors.run_files(company_id=company_id, run_id=run_id)
    carried: dict[str, StepOutput] = {}
    for step in steps:
        if step.status != "done" or step.data is None:
            ended = (
                None
                if step.name not in flow.fanouts
                else selectors.ended_segments(company_id=company_id, run_id=run_id).get(step.name, {})
            )
            # 펼침 단계에는 단계 안 부분 산출이 없다(진행 셈의 partial {} 는 resume 으로 넘기지 않는다)
            resume_at = None if step.name in flow.fanouts else step.partial
            return Plan(
                carried=carried,
                start_at=step.name,
                resume=resume_at,
                assembled=None,
                segments_done=None if ended is None else {step.name: ended},
            )
        loaded: list[OutputFile] = []
        for file in files:
            if file.step != step.name:
                continue
            got = storage.get(file.storage_key, max_bytes=file.size_bytes)
            if isinstance(got, StorageUnavailable):
                return RunDeferred()
            if isinstance(got, ObjectBytes):
                content = got.data
            elif isinstance(got, ObjectMissing) and resumed_from is not None:
                moved = _carry(storage, company_id=company_id, run_id=run_id, resumed_from=resumed_from, file=file)
                if not isinstance(moved, bytes):
                    return moved
                content = moved
            else:
                return _failed("object_missing")
            loaded.append(OutputFile(name=file.name, media_type=file.media_type, content=content))
        carried[step.name] = StepOutput(data=step.data, files=tuple(loaded))
    # 단계가 전부 끝났다(앞 시도가 끝내기 없이 죽었다): 끝 산출물은 마지막 단계의 것이다(run_flow 가 이미 검사했다).
    last = carried[flow.steps[-1]]
    results = tuple(cast("list[dict[str, object]]", last.data["results"]))
    return Plan(carried=carried, start_at=None, resume=None, assembled=FlowOutput(results=results, files=last.files))


def _bound(
    found: Run,
    *,
    company_id: int,
    bare: flow_ports.DocumentlessBinding | None,
    binding: flow_ports.RunBinding | NoBinding,
    document: DocumentInput | RunFailed | RunDeferred | None,
    ctx: ExecutorContext,
) -> tuple[object, object]:
    """끼움으로 흐름의 입력과 어댑터를 짓는다(트랜잭션 밖). 문서 없는 흐름(ND1)은 옵션과 실행의 회사로."""
    if bare is not None:
        inputs = (
            bare.inputs_with(found.options, company_id=company_id, versions=found.versions)
            if isinstance(bare, flow_ports.DocumentlessFactsBinding)
            else bare.inputs(found.options, company_id=company_id)
        )
        return inputs, bare.adapters(ctx)
    assert isinstance(document, DocumentInput)  # noqa: S101  (위 갈래가 문서를 읽었다)
    assert not isinstance(binding, NoBinding)  # noqa: S101  (위 갈래가 flow_not_runnable 로 걸렀다)
    inputs = (
        binding.inputs_with(document, found.options, company_id=company_id, versions=found.versions)
        if isinstance(binding, flow_ports.RunFactsBinding)
        else binding.inputs(document, found.options)
    )
    return inputs, binding.adapters(ctx)


class RunParked(BaseException):
    """지휘 시도가 펼침 구획을 쪽지에 맡긴다(RM1b). RunYield 처럼 BaseException 이라 흐름·단계의 `except Exception` 이
    잡지 못하고 run_flow 밖으로 바로 온다. 실행기만 잡는다(execute_run — 주차)."""

    def __init__(self, step: str, pending: int) -> None:
        super().__init__(f"펼침 단계 {step} 의 끝나지 않은 구획 {pending}개를 쪽지에 맡긴다")
        self.step = step
        self.pending = pending


class _ParkDispatch:
    """run_flow 의 SegmentDispatch(RM1b): 끝나지 않은 구획 수를 쥐고 RunParked 로 나간다(돌아오지 않는다)."""

    def dispatch(self, flow_id: str, step: str, pending: tuple[SegmentKey, ...]) -> NoReturn:
        raise RunParked(step, len(pending))


_PARK: Final = _ParkDispatch()


def _send_run(*, company_id: int, run_id: int) -> None:
    """커밋 뒤 지휘 쪽지 하나(구획 블록이 깨웠다). 못 보내면 기록만 — 실행은 processing·임대 NULL 로 남아
    requeue_runs 가 메운다."""
    try:
        queue.enqueue_run(company_id=company_id, run_id=run_id)
    except Exception as err:
        logger.error("run_wake_send_failed run_id=%s error=%s", run_id, type(err).__name__)


def _send_segment(*, company_id: int, run_id: int, run_attempt: int, countdown: int) -> None:
    """커밋 뒤 구획 쪽지 하나. 못 보내면 기록만(다른 쪽지의 끝냄이 이어 넣거나, 남은 것이 없으면 requeue_runs)."""
    try:
        queue.enqueue_segment(company_id=company_id, run_id=run_id, run_attempt=run_attempt, countdown=countdown)
    except Exception as err:
        logger.error("segment_send_failed run_id=%s error=%s", run_id, type(err).__name__)


def _finish(
    *, company_id: int, run_id: int, attempt: int, outcome: RunOutcome | RunParkedOutcome
) -> Finished | Superseded:
    with transaction.atomic(durable=True):  # T2
        return services.finish_run(company_id=company_id, run_id=run_id, attempt=attempt, now=clock(), outcome=outcome)


def execute_run(self: Any, *, company_id: str, run_id: str) -> None:
    """`runs.execute` 의 몸. `self` 는 Celery 의 태스크다(다시 넣기를 청할 때만 쓴다)."""
    settings = job_settings()
    if COMPANY_ID_TEXT.match(company_id) is None or COMPANY_ID_TEXT.match(run_id) is None:
        # 꼴 밖의 쪽지는 조회하지 않는다(실행 표의 매니저는 양의 정수가 아닌 회사를 거절한다 — core/isolation).
        logger.info("run_skipped run_id=%s reason=%s", run_id, RunNotFound.__name__)
        return
    company = int(company_id)
    run = int(run_id)
    started = monotonic()
    parallel = segment_parallel()
    notes = 0  # 주차 뒤 넣을 구획 쪽지 수(RM1b)

    with transaction.atomic(durable=True):  # T1
        claimed = services.claim_run(
            company_id=company, run_id=run, now=clock(), lease_s=settings.lease_s, max_attempts=settings.max_attempts
        )
    if not isinstance(claimed, Claimed):
        logger.info("run_skipped run_id=%s reason=%s", run_id, type(claimed).__name__)
        return
    attempt = claimed.attempt
    storage = documents.default_storage()

    outcome: RunOutcome | RunParkedOutcome
    try:  # 트랜잭션 밖
        flow = _flow(claimed.run.flow_id)
        # 문서 없는 흐름(ND1)인지는 어느 사전에 달렸는가로 먼저 가른다(RunFactsBinding isinstance 는 이름만 본다)
        bare = BINDINGS.documentless(claimed.run.flow_id)
        binding = BINDINGS.get(claimed.run.flow_id)
        if flow is None or (bare is None and isinstance(binding, NoBinding)):
            outcome = _failed("flow_not_runnable")
        elif storage is None:
            outcome = _failed("storage_unconfigured")
        else:
            # 문서 없는 흐름은 문서를 읽지 않는다(None). 문서 흐름인데 문서 칸이 비었으면 실패(만들기가 막는다 — 방어)
            document: DocumentInput | RunFailed | RunDeferred | None = None
            if bare is None:
                document = (
                    _failed("document_missing")
                    if claimed.run.document_id is None
                    else _document(storage, company_id=company, document_id=claimed.run.document_id)
                )
            plan = (
                _plan(
                    storage,
                    company_id=company,
                    run_id=run,
                    flow=flow,
                    resumed_from=claimed.run.resumed_from_run_id,
                )
                if document is None or isinstance(document, DocumentInput)
                else None
            )
            if document is not None and not isinstance(document, DocumentInput):
                outcome = document
            elif not isinstance(plan, Plan):
                assert plan is not None  # noqa: S101  (문서가 있거나 문서 없는 흐름이면 자리를 읽었다)
                outcome = plan
            else:
                cursor = StepCursor()  # 이 시도의 지금 단계 — 사건이 적고 싱크가 읽는다(AD4D)
                ctx = ExecutorContext(
                    company_id=company,
                    run_id=run,
                    module=claimed.run.module,
                    flow_id=flow.id,
                    attempt=attempt,
                    sink=RunCallSink(context.call_sink(), run, cursor),
                )
                inputs, adapters = _bound(
                    claimed.run, company_id=company, bare=bare, binding=binding, document=document, ctx=ctx
                )
                output = plan.assembled
                if output is None:
                    events = RowEvents(
                        company_id=company,
                        run_id=run,
                        attempt=attempt,
                        deadline=deadline_of(started=started, soft_limit_s=soft_limit_s()),
                        lease_s=settings.lease_s,
                        storage=storage,
                        cursor=cursor,
                    )
                    output = run_flow(
                        flow,
                        inputs,
                        adapters,
                        start_at=plan.start_at,
                        carried=plan.carried,
                        resume=plan.resume,
                        events=events,
                        segment_events=events,
                        segments_done=plan.segments_done,
                        dispatch=None if parallel < 2 else _PARK,  # RM1b: 상한 ≥2 면 구획을 쪽지에 맡기고 주차
                    ).output
                files = _put_files(storage, company_id=company, run_id=run, step=None, files=output.files)
                outcome = RunDone(results=output.results, files=files)
    except RunYield:
        outcome = RunDeferred()
    except RunParked as parked:  # RM1b: 펼침 구획을 쪽지에 맡겼다 — 기존 끝내기 블록(T2)으로 주차를 적는다
        outcome = RunParkedOutcome(lease_s=settings.lease_s)
        notes = min(parallel, parked.pending)
        logger.info("run_parking run_id=%s step=%s pending=%s notes=%s", run_id, parked.step, parked.pending, notes)
    except Exception as err:
        outcome = outcome_of(err, run_id=run)

    try:
        finished = _finish(company_id=company, run_id=run, attempt=attempt, outcome=outcome)
    except DatabaseError as err:
        # 끝내기 블록이 되돌려졌다(크기 CHECK·연결 끊김 …). 다시 넣기로 한 번 더 적는다.
        logger.error("run_finish_failed run_id=%s error=%s", run_id, type(err).__name__, exc_info=err)
        outcome = RunDeferred()
        finished = _finish(company_id=company, run_id=run, attempt=attempt, outcome=outcome)
    logger.info(
        "run_finished run_id=%s attempt=%s outcome=%s%s written=%s",
        run_id,
        attempt,
        type(outcome).__name__,
        f" code={outcome.code}" if isinstance(outcome, RunFailed) else "",
        type(finished).__name__,
    )
    if isinstance(outcome, RunParkedOutcome) and isinstance(finished, Finished):
        # 커밋 뒤(블록 밖) 구획 쪽지 min(상한, 끝나지 않은 수)개. 보내기 실패는 기록하고 다음으로
        for _ in range(notes):
            _send_segment(company_id=company, run_id=run, run_attempt=attempt, countdown=0)
    if isinstance(outcome, RunDeferred) and isinstance(finished, Finished):
        # 쪽지를 새로 넣는다(countdown 뒤). 횟수의 상한은 잡기가 건다(max_retries=None).
        raise self.retry(countdown=settings.retry_delay_s, max_retries=None)


# 태스크로 등록한다. 이름은 갈고리가 보내는 이름과 같다(core/calc/jobs.py 의 RUN_TASK_NAME).
# (`@app.task` 꾸밈 꼴을 쓰지 않은 까닭은 reconcile/tasks.py 와 같다: celery 에 타입 정보가 없다.)
execute_task: Any = app.task(name=RUN_TASK_NAME, bind=True)(execute_run)


# ── 구획 쪽지(`runs.segment` — RM1b) ──────────────────────────────────


def _policies(flow: Flow | None) -> dict[str, str]:
    """펼침 단계 → 실패 정책(흐름의 선언). 흐름을 모르면 빈 사전(잡기는 pass_to_gather 로 읽는다)."""
    return {} if flow is None else {name: step.on_failure for name, step in flow.fanouts.items()}


def _segment_outcome(
    found: Run, claimed: SegmentClaimed, *, company_id: int, run_attempt: int, flow: Flow | None
) -> SegmentEndOutcome:
    """잡은 구획 하나를 돌아 끝냄의 갈래를 짓는다(트랜잭션 밖 — 발주서 §2-3 앞 갈래 표). 지휘와 같은 함수로 문서·
    이어 갈 자리·끼움을 다시 짓는다(쪽지마다 — 무효 조건은 머리말)."""
    run_id, step = found.id, claimed.step
    bare = BINDINGS.documentless(found.flow_id)
    binding = BINDINGS.get(found.flow_id)
    if flow is None or (bare is None and isinstance(binding, NoBinding)):
        return EndFatal(code="flow_not_runnable", step=None)
    storage = documents.default_storage()
    if storage is None:
        return EndFatal(code="storage_unconfigured", step=None)
    document: DocumentInput | RunFailed | RunDeferred | None = None
    if bare is None:
        document = (
            _failed("document_missing")
            if found.document_id is None
            else _document(storage, company_id=company_id, document_id=found.document_id)
        )
    if isinstance(document, RunFailed):
        return EndFatal(code=document.code, step=None)
    if isinstance(document, RunDeferred):
        return EndReleased()
    plan = _plan(storage, company_id=company_id, run_id=run_id, flow=flow, resumed_from=found.resumed_from_run_id)
    if isinstance(plan, RunFailed):
        return EndFatal(code=plan.code, step=None)
    if isinstance(plan, RunDeferred):
        return EndReleased()
    if plan.start_at != step:
        logger.warning("segment_released run_id=%s step=%s start_at=%s", run_id, step, plan.start_at)
        return EndReleased()
    cursor = StepCursor()
    cursor.current, cursor.segment = step, claimed.key_sha256  # 이 구획 안의 LLM 호출이 펼침 단계와 sha 를 싣는다(R4)
    try:
        ctx = ExecutorContext(
            company_id=company_id,
            run_id=run_id,
            module=found.module,
            flow_id=flow.id,
            attempt=run_attempt,
            sink=RunCallSink(context.call_sink(), run_id, cursor),
        )
        inputs, adapters = _bound(found, company_id=company_id, bare=bare, binding=binding, document=document, ctx=ctx)
    except (flow_ports.RunOptionsRejected, flow_ports.RunVersionsMismatch) as err:
        return EndFatal(code=step_error_code(type(err)), step=None)
    except Exception as err:
        if not run_fatal(type(err)):
            raise
        # 리뷰 M3(감독 처분 11-10): 끼움·싱크 짓기의 키 없음·설정 오류도 치명(감독 답 Q2) — 놓아 시도 셋 헛돌지 않게
        logger.error("segment_fatal run_id=%s step=%s code=%s", run_id, step, step_error_code(type(err)))
        return EndFatal(code=step_error_code(type(err)), step=step)
    try:
        segments = plan_segments(flow, step, inputs, plan.carried)
    except Exception as err:
        if _transient(err):
            return EndReleased()
        logger.error("segment_plan_failed run_id=%s step=%s error=%s", run_id, step, type(err).__name__)
        return EndFatal(code=step_error_code(type(err)), step=step)
    segment = next((s for s in segments if segment_key_sha256(s.key) == claimed.key_sha256), None)
    if segment is None:
        logger.error("segment_not_in_plan run_id=%s step=%s position=%s", run_id, step, claimed.position)
        return EndFatal(code="segments_mismatch", step=step)
    try:
        output = run_segment(flow, step, inputs, adapters, plan.carried, segment)
    except RunYield:
        return EndReleased()
    except Exception as err:
        if _transient(err):
            logger.info("segment_released run_id=%s position=%s cause=%s", run_id, claimed.position, type(err).__name__)
            return EndReleased()
        code = step_error_code(type(err))
        if run_fatal(type(err)):
            logger.error("segment_fatal run_id=%s step=%s code=%s", run_id, step, code, exc_info=err)
            return EndFatal(code=code, step=step)
        logger.error("segment_failed run_id=%s position=%s code=%s", run_id, claimed.position, code, exc_info=err)
        return EndFailed(code=code)
    return EndDone(data=output.data)


def execute_segment(self: Any, *, company_id: str, run_id: str, run_attempt: str) -> None:
    """`runs.segment` 의 몸(RM1b): 구획 하나를 잡아(블록) 돌고(블록 밖) 끝낸다(블록). 다시 넣기(self.retry)는 없다 —
    이어 넣기는 끝냄 블록의 판정(successor)이, 깨우기는 구획 상태를 바꾼 블록의 판정(wake)이 정한다(커밋 뒤 쪽지).

        U1  with transaction.atomic(durable=True):  segment_claim   첫 문 lock_run · 상한 · 소진 · 잡기
        ── 트랜잭션 밖 ──  문서 get · 이어 갈 자리(_plan) · 끼움 · plan_segments · run_segment
        U2  with transaction.atomic(durable=True):  segment_end     Done·Failed·Fatal·Released + 깨우기·이어 넣기 판정
    """
    settings = job_settings()
    if any(COMPANY_ID_TEXT.match(value) is None for value in (company_id, run_id, run_attempt)):
        logger.info("segment_skipped run_id=%s reason=%s", run_id, RunNotFound.__name__)
        return
    company, run, attempt = int(company_id), int(run_id), int(run_attempt)
    parallel = max(segment_parallel(), 1)
    found = selectors.find_run(company_id=company, run_id=run)
    if found is None:
        logger.info("segment_skipped run_id=%s reason=%s", run_id, RunNotFound.__name__)
        return
    flow = _flow(found.flow_id)
    policies = _policies(flow)

    with transaction.atomic(durable=True):  # U1
        claimed = services.segment_claim(
            company_id=company,
            run_id=run,
            run_attempt=attempt,
            now=clock(),
            lease_s=settings.lease_s,
            parallel_max=parallel,
            max_attempts=settings.max_attempts,
            on_failure=policies,
        )
    if not isinstance(claimed, SegmentClaimed):
        if claimed.wake:  # NothingToClaim.wake = 소진 깨움 · Superseded.wake = 다시 깨움(RM1c ③′ M2)
            _send_run(company_id=company, run_id=run)
        elif isinstance(claimed, NothingToClaim) and claimed.delay is not None:  # 미룬 쪽지(RM1c ③′ M1)
            _send_segment(company_id=company, run_id=run, run_attempt=attempt, countdown=claimed.delay)
        logger.info("segment_skipped run_id=%s reason=%s", run_id, type(claimed).__name__)
        return

    outcome: SegmentEndOutcome
    try:  # 트랜잭션 밖
        outcome = _segment_outcome(found, claimed, company_id=company, run_attempt=attempt, flow=flow)
    except RunYield:
        outcome = EndReleased()
    except Exception as err:  # 표 밖 — 실행기의 결함. 놓고(구획 시도 상한이 끝낸다) 기록(Qn1)
        # 리뷰 N3: 블록 밖의 잠깐 오류(소프트 제한·DB 끊김)는 warning, 그 밖은 error
        log = logger.warning if _transient(err) else logger.error
        log("segment_crashed run_id=%s position=%s error=%s", run_id, claimed.position, type(err).__name__)
        outcome = EndReleased()

    try:
        with transaction.atomic(durable=True):  # U2
            ended = services.segment_end(
                company_id=company,
                run_id=run,
                run_attempt=attempt,
                step=claimed.step,
                key_sha256=claimed.key_sha256,
                attempt=claimed.attempt,
                outcome=outcome,
                now=clock(),
                lease_s=settings.lease_s,
                parallel_max=parallel,
                on_failure=policies.get(claimed.step, "pass_to_gather"),
            )
    except SegmentAlreadyEnded as late:  # 감독 처분 D2: 늦은 쪽지의 정상 경합 — 쓰기 0·쪽지 0·다시 하기 0
        logger.info("segment_already_ended run_id=%s position=%s attempt=%s", run_id, late.position, late.attempt)
        return
    logger.info(
        "segment_finished run_id=%s position=%s attempt=%s outcome=%s%s written=%s",
        run_id,
        claimed.position,
        claimed.attempt,
        type(outcome).__name__,
        f" code={outcome.code}" if isinstance(outcome, EndFailed | EndFatal) else "",
        type(ended).__name__,
    )
    if not isinstance(ended, Ended):
        return
    if ended.wake:
        _send_run(company_id=company, run_id=run)
    elif ended.successor:
        delay = settings.retry_delay_s if isinstance(outcome, EndReleased) else 0
        _send_segment(company_id=company, run_id=run, run_attempt=attempt, countdown=delay)
    elif ended.delay is not None:  # 미룬 쪽지(RM1c ③′ M1 — 남은 것이 전부 임대 산 running)
        _send_segment(company_id=company, run_id=run, run_attempt=attempt, countdown=ended.delay)


# 이름은 큐 넣기가 보내는 이름과 같다(core/calc/jobs.py 의 SEGMENT_TASK_NAME). autodiscover 가 이 파일을 읽는다.
segment_task: Any = app.task(name=SEGMENT_TASK_NAME, bind=True)(execute_segment)
