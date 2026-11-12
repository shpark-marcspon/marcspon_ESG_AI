# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""요청 밖에서 도는 일(Celery 태스크). 지금은 하나다: 올린 PDF 를 파서에 보내 분해한다(`jobs.parse`).

얇다: 잡기 → 저장소에서 바이트 받기 → 분해 → 끝내기. 규칙은 다른 곳에 있다
(core/service/services/jobs.py 의 잡기·끝내기, reconcile/service/services/parse.py 의 분해,
reconcile/calc/job_summary.py 의 요약).
모델을 직접 import 하지 않는다(`.importlinter` 계약 라: `esgapi.*.tasks`).

쪽지에는 `company_id` 와 `job_id` 뿐이다(둘 다 십진 숫자 글자 — core/resources/queue.py). 나머지는 표에서 읽는다.

    T1  with transaction.atomic(durable=True):  claim_job(company_id, …)  행을 잠그고 `processing` 으로. 커밋한다
        ── 트랜잭션 밖 ──  storage.get → ETag 견주기 → parse_and_extract    (느리다. 행도 연결도 붙들지 않는다)
    T2  with transaction.atomic(durable=True):  finish_job(company_id, …) `done`·`failed`, 또는 임대를 당겨 두기

★ 트랜잭션이 둘이다. 회사는 블록마다 인자로 넘긴다(잡기·끝내기가 그 회사로 조건을 건다).
  company_id 가 틀리면 T1 에서 일감이 보이지 않아(회사 조건) 아무것도 하지 않는다. 쪽지의 두 값이 십진 숫자 글자
  (COMPANY_ID_TEXT — 0·음수·"01"·"1.0"·빈 글자는 아님)가 아니면 조회하지 않고 「없음」으로 건너뛴다.
★ durable=True: 잡기의 커밋이 저장소·파서보다 **먼저** 나가야 다른 워커가 `processing` 을 본다. 바깥 트랜잭션 안에서
  불리면 그 약속이 깨지므로 RuntimeError 로 거절한다(테스트: pytest-django 의 바깥 블록 바로 아래에서는 열린다).
★ 같은 쪽지가 두 번 와도, 워커가 죽어 다른 워커가 이어받아도 끝은 한 번만 적힌다(T1 의 잠금·상태·임대, T2 의 울타리).
  다만 한 번만 「도는」 것은 아니다: 임대가 끝난 뒤 이어받으면 저장소·파서가 두 번 불릴 수 있다.
★ ETag: `get` 한 번의 답에 든 ETag(그 바이트를 실은 응답의 것)를 올림 확인 때 표에 적어 둔 것과 견준다.
  다르면 파서를 부르지 않고 `failed`·object_changed 다(올림 확인 뒤 같은 주소에 다시 올린 것이다).
★ 일감이 끝나는 갈래:
    done                                 분해가 됐다. 요약(작은 숫자)과 문서의 sha256 을 적는다
    failed  <파서의 code 나 갈래 이름>     다시 해도 안 되는 것: PDF 가 아니다, 꼴이 틀렸다, 객체가 없다·바뀌었다 …
    failed  internal                     분해 중 예상 밖 예외(`logger.exception` 으로 남긴다). 다시 해 보지 않는다
    (임대를 당기고 다시 해 본다)          잠깐의 문제: 저장소에 닿지 못함, 파서 unavailable, 소프트 시간 제한
                                         → `self.retry(countdown=JOB_RETRY_DELAY_SECONDS)`. 횟수의 상한은 Celery 가
                                           아니라 잡기의 Exhausted 가 건다(시도 상한에서 `failed`·attempts_exhausted)
★ 시간 제한: 소프트 제한은 여기서 잡아 「다시 해 본다」로 넘긴다. 하드 제한은 프로세스를 죽인다 → 일감은
  `processing` 으로 남고 쪽지는 ack 된다(다시 오지 않는다). 임대가 끝난 뒤 다시 넣기 명령이 메운다.
★ JobUpdateError(갱신한 행 수가 틀렸다)는 잡지 않는다: 다시 해 보기를 청하지 않는다.

★ 테스트가 바꿔 끼우는 틈(전부 「부를 때 모듈 속성으로 읽는다」):
    services.default_storage · services.max_upload_bytes     저장소와 상한
                                                             (core/service/services/documents.py 의 틈 그대로)
    tasks.default_parser                                     monkeypatch.setattr(tasks, "default_parser", lambda: fake)
    tasks.job_settings · tasks.clock                         임대·시도의 수와 시계
  pytest 프로세스 안에서 진짜 워커를 띄우지 않는다. 태스크는 함수를 직접 불러 잰다.
"""

import logging
from datetime import datetime
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction

from esgapi.config.celery import app
from esgapi.config.env import JobSettings
from esgapi.core.calc.documents import COMPANY_ID_TEXT
from esgapi.core.calc.jobs import task_name
from esgapi.core.conf import app_config, now
from esgapi.core.resources.ports.parser import DocumentParser
from esgapi.core.resources.ports.storage import ObjectMissing, ObjectTooLarge, StorageDenied, StorageUnavailable
from esgapi.core.service.selectors.documents import Document
from esgapi.core.service.services import documents as services
from esgapi.reconcile.calc.job_summary import parse_summary, problem_code
from esgapi.reconcile.service.services import parse as parse_service
from esgapi.reconcile.service.services.parse import ParseProblem, ParserNotConfiguredError, parse_and_extract
from esgapi.runs.service.services.jobs import (
    Claimed,
    Deferred,
    Done,
    Failed,
    Finished,
    JobNotFound,
    Outcome,
    claim_job,
    finish_job,
)

logger = logging.getLogger(__name__)


def default_parser() -> DocumentParser:
    """이 프로세스의 파서. 주소가 없으면 ParserNotConfiguredError. ★ 이음매다."""
    return parse_service.default_parser(app_config())


def job_settings() -> JobSettings:
    """임대·시도 상한·다시 해 보기까지의 수. ★ 이음매다."""
    return app_config().jobs


def clock() -> datetime:
    """지금. ★ 이음매다."""
    return now()


def parse_document(document: Document) -> Outcome:
    """트랜잭션 **밖**에서 부른다: 저장소에서 바이트를 받아 ETag 를 견주고 분해한다. 끝을 갈래로 돌려준다."""
    storage = services.default_storage()
    if storage is None:
        return Failed("storage_unconfigured", "이 프로세스에 저장소 설정이 없다(S3_BUCKET)")
    try:
        parser = default_parser()
    except ParserNotConfiguredError:
        return Failed("parser_unconfigured", "이 프로세스에 파서 주소가 없다(PARSER_URL)")

    got = storage.get(document.storage_key, max_bytes=services.max_upload_bytes())
    if isinstance(got, ObjectMissing):
        return Failed("object_missing", "저장소에 원본이 없다")
    if isinstance(got, ObjectTooLarge):
        return Failed("object_too_large", f"원본이 상한({got.max_bytes} B)보다 크다")
    if isinstance(got, StorageDenied):
        return Failed("storage_denied", got.detail)
    if isinstance(got, StorageUnavailable):
        return Deferred()
    if got.etag != document.etag:
        # 올림 확인 뒤에 같은 주소로 다시 올린 것이다. 확인한 것과 다른 바이트를 분해하지 않는다.
        return Failed("object_changed", "저장소의 원본이 올림 확인 때의 것과 다르다(ETag)")

    result = parse_and_extract(got.data, file_name=document.file_name, parser=parser, doc_id=str(document.id))
    if isinstance(result, ParseProblem):
        if result.kind == "unavailable":
            return Deferred()
        return Failed(*problem_code(result))
    return Done(parse_summary(result), result.document.source.sha256)


def run_parse_job(self: Any, *, company_id: str, job_id: str) -> None:
    """`jobs.parse` 의 몸. `self` 는 Celery 의 태스크다(다시 해 보기를 청할 때만 쓴다)."""
    settings = job_settings()
    if COMPANY_ID_TEXT.match(company_id) is None or COMPANY_ID_TEXT.match(job_id) is None:
        # 꼴 밖의 쪽지는 조회하지 않고 「없음」으로 건너뛴다(기준의 0행 → JobNotFound 와 같은 끝).
        # 일감 표의 매니저는 양의 정수가 아닌 회사를 거절한다(core/isolation).
        # 그 예외가 워커까지 가지 않게 입구에서 거른다.
        logger.info("job_skipped job_id=%s kind=parse reason=%s", job_id, JobNotFound.__name__)
        return
    company = int(company_id)
    job = int(job_id)

    with transaction.atomic(durable=True):  # T1
        claimed = claim_job(
            company_id=company,
            job_id=job,
            now=clock(),
            lease_s=settings.lease_s,
            max_attempts=settings.max_attempts,
        )
    if not isinstance(claimed, Claimed):
        logger.info("job_skipped job_id=%s kind=parse reason=%s", job_id, type(claimed).__name__)
        return

    try:
        outcome = parse_document(claimed.document)  # 트랜잭션 밖
    except SoftTimeLimitExceeded:
        outcome = Deferred()
    except Exception as exc:
        # 예상 밖 예외. 그대로 올리면 쪽지는 ack 되고(task_acks_on_failure_or_timeout) 일감은 `processing` 에 묶인다.
        # 예외의 글은 표에 싣지 않는다(문서 글이 섞일 수 있다). 줄에는 일감 id 와 예외 이름만 적는다.
        logger.exception("job_crashed job_id=%s kind=parse error=%s", job_id, type(exc).__name__)
        outcome = Failed("internal", "분해 중 예상 밖 오류가 났다(워커 로그)")

    with transaction.atomic(durable=True):  # T2
        finished = finish_job(company_id=company, job_id=job, attempt=claimed.attempt, now=clock(), outcome=outcome)
    logger.info(
        "job_finished job_id=%s kind=parse attempt=%s outcome=%s%s written=%s",
        job_id,
        claimed.attempt,
        type(outcome).__name__,
        f" code={outcome.code}" if isinstance(outcome, Failed) else "",
        type(finished).__name__,
    )
    if isinstance(outcome, Deferred) and isinstance(finished, Finished):
        # 쪽지를 새로 넣는다(countdown 뒤). 횟수의 상한은 잡기가 건다(max_retries=None).
        raise self.retry(countdown=settings.retry_delay_s, max_retries=None)


# 태스크로 등록한다. 이름은 갈고리가 보내는 이름과 같다(core/calc/jobs.py 의 task_name).
# (`@app.task` 꾸밈 꼴을 쓰지 않은 까닭: celery 에 타입 정보가 없어 꾸민 함수의 타입이 가려진다.)
parse_job: Any = app.task(name=task_name("parse"), bind=True)(run_parse_job)
