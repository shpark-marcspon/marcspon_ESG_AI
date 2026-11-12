"""일감(표 run_jobs)을 워커가 잡는 순수 규칙: 잡아도 되는가, 임대가 언제 끝나는가, 태스크의 이름, 오류 code 의 목록.

순수하다(django·ninja·psycopg·celery 를 모른다. `.importlinter` 계약 다). DB 없이 테스트된다.
상태와 전이표는 core/calc/documents.py 에 있다. 표를 실제로 고치는 것은 core/documents/jobs.py 다.

★ 중복은 큐가 아니라 **표**에서 막는다. 같은 일감의 쪽지는 여러 번 올 수 있다(올림 확인을 다시 부름, 다시 넣기 명령,
  큐의 재전달). 쪽지를 받은 워커는 행을 잠그고 이 판정을 묻는다:

      queued                      잡는다
      processing · 임대가 지났다   잡는다(이어받기). 임대가 NULL 인 processing 도 지난 것으로 본다
      processing · 임대가 남았다   안 잡는다(LeaseHeld). 다른 워커가 쥐고 있다
      done · failed               안 잡는다(AlreadyFinished)
      잡으면 시도가 상한을 넘는다   안 잡는다(Exhausted). 부른 쪽이 `failed`·attempts_exhausted 로 끝낸다

  ★ 「임대가 지금과 같으면 지난 것」이다(`lease_expires_at <= now`). 잠깐의 실패(Deferred)는 임대를 **지금으로** 당겨
    두므로, 같은 시각에 다시 온 쪽지가 잡을 수 있어야 한다.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from esgapi.core.calc.documents import JOB_KINDS, JobStatus


@dataclass(frozen=True, slots=True)
class Take:
    """잡는다. `attempt` 는 이번 시도의 번호(1부터)이고 행의 `attempts` 가 이 값이 된다."""

    attempt: int


@dataclass(frozen=True, slots=True)
class AlreadyFinished:
    pass


@dataclass(frozen=True, slots=True)
class LeaseHeld:
    until: datetime


@dataclass(frozen=True, slots=True)
class Exhausted:
    """시도를 다 썼다. 행의 `attempts` 는 그대로 두고 `failed` 로 끝낸다."""


ClaimDecision = Take | AlreadyFinished | LeaseHeld | Exhausted


def claim_decision(
    status: JobStatus, lease_expires_at: datetime | None, attempts: int, now: datetime, max_attempts: int
) -> ClaimDecision:
    if status == "done" or status == "failed":
        return AlreadyFinished()
    if status == "processing" and lease_expires_at is not None and lease_expires_at > now:
        return LeaseHeld(lease_expires_at)
    if attempts >= max_attempts:
        return Exhausted()
    return Take(attempts + 1)


def lease_until(now: datetime, lease_s: int) -> datetime:
    return now + timedelta(seconds=lease_s)


def task_name(kind: str) -> str:
    """일감의 종류 → 태스크의 이름(`jobs.<kind>`). 갈고리는 태스크를 import 하지 않고 이 이름으로 보낸다.

    JOB_KINDS 밖의 종류면 던진다(호출이 틀린 것이다. 모르는 이름의 쪽지를 큐에 넣지 않는다).
    """
    if kind not in JOB_KINDS:
        raise ValueError(f"모르는 일감의 종류다: {kind}")
    return f"jobs.{kind}"


# 흐름의 실행(표 run_runs — X1b-1)을 돌리는 태스크의 이름. 갈고리(core/resources/queue.py 의 enqueue_run)는
# 태스크를 import 하지 않고 이 이름으로 보낸다. 정의는 esgapi/runs/tasks.py(core 는 runs 를 모른다 — 계약 가).
RUN_TASK_NAME: Final = "runs.execute"
# 펼침 구획 하나를 쥐고 도는 쪽지의 태스크 이름(RM1b — queue.py 의 enqueue_segment). 정의는 runs/tasks.py.
SEGMENT_TASK_NAME: Final = "runs.segment"


# 일감이 `failed` 로 끝날 때 `error_code` 에 적히는 값. 워커가 스스로 정한 것 여덟과, 파서의 실패는 파서가 준 code
# (`not_a_pdf` …)가 있으면 그것, 없으면 분해의 갈래 이름(reconcile/services/parse.py 의 PARSE_PROBLEM_KINDS)이다.
JOB_ERROR_CODES: Final[tuple[str, ...]] = (
    "object_changed",  # 저장소의 객체가 올림 확인 때의 것과 다르다(ETag). 파서를 부르지 않았다
    "object_missing",  # 저장소에 그 키의 객체가 없다
    "object_too_large",  # 객체가 상한(MAX_UPLOAD_BYTES)보다 크다
    "storage_denied",  # 저장소가 거절했다(403)
    "storage_unconfigured",  # 이 프로세스에 저장소 설정이 없다
    "parser_unconfigured",  # 이 프로세스에 파서 주소가 없다
    "document_missing",  # 일감이 가리키는 문서가 이 테넌트에 보이지 않는다
    "attempts_exhausted",  # 시도를 다 썼다(잠깐의 실패가 되풀이됐거나 워커가 거듭 죽었다)
)
MAX_ERROR_CODE_CHARS: Final = 64  # 표의 칸 길이(runs/models.py 의 JobRow.error_code)
MAX_ERROR_MESSAGE_CHARS: Final = 500  # 위와 같다(error_message)
