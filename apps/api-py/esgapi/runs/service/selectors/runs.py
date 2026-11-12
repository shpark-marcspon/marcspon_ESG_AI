"""읽기. 흐름의 실행(표 run_runs)과 그 단계·결과·파일. 쓰지 않는다.

    lock_run(company_id, run_id)                        잡기의 ①: 그 행을 FOR UPDATE 로 읽는다(ORM 행을 돌려준다)
    find_run(company_id, run_id)                        하나 읽기(Run)
    run_by_key(company_id, created_by_user_id, key)     그 사람이 그 Idempotency-Key 로 만든 실행과 본문 sha(IK1)
    run_page(company_id, module, status, document_id, limit, offset, modules, statuses, created_by_user_id)
                                                        고객사 목록 한 쪽(새 것 먼저 — created_at·id 내림).
                                                        줄은 (Run, 문서 파일 이름) — document__file_name 한 칸 join
                                                        (LEFT — 문서 없는 실행(ND1)은 이름 None)
    step_rows(company_id, run_id)                       그 실행의 단계(선언 차례)
    step_rows_of(company_id, run_ids)                   실행들의 단계(실행 id → 선언 차례 — 쿼리 하나, 목록 줄 G1b-2b)
    step_heads(company_id, run_id)                      그 실행의 단계 머리(이름·차례·상태·시각만 — data·partial 은
                                                        읽지 않는다. 운영 관리자 실행 상세 AD4D)
    step_output(company_id, run_id, step)               끝난 단계의 산출(MARC-ENT-208 — 모듈이 (실행, 단계)로 읽는다)
    run_files(company_id, run_id)                       그 실행의 파일 행(저장소 키째 — 실행기가 이어 갈 때 다시 읽는다)
    output_file(company_id, run_id, name)               흐름의 출력 파일 하나(단계 산출 파일은 이 길로 안 나온다)
    resumed_alive(company_id, run_id)                   그 실행을 이어 받은 실행 가운데 failed 아닌 것이 있는가(X1b-2b)
    run_results(company_id, run_id)                     결과(차례대로)
    results_of(company_id, run_ids)                     실행들의 결과(실행 id → 차례대로 — 쿼리 하나, 목록 줄 G1b-2b)
                                                        키워드 schema_versions 를 주면 그 꼴만(None = 전부, TR3b)
    run_keys(company_id, module, document_id, limit)    실행의 열쇠 칸(옵션의 batchId·part 투영 — 옵션 본문은 읽지
                                                        않는다. 영문번역 묶음 목록 TR3b, MARC-TICK-251)
    run_page_brief(…)                                   run_page 의 거름·차례·count + 옵션 경로 투영(본문 0, ISSUE-347)
    runs_of(company_id, run_ids)                        실행들(find_run 의 묶음 꼴 — 쿼리 하나)
    step_lines_of(company_id, run_ids)                  실행들의 단계 머리 + done·total(data·partial 은 읽지
                                                        않는다 — 쿼리 하나)
    stale_runs(company_id, now, queued_older_than_s)    임대가 지난 processing 과 오래 머문 queued(다시 넣기)
    segment_rows(company_id, run_id, step)              그 실행의 그 펼침 단계의 구획(계획 차례 — RM1a)
    segment_plan(company_id, run_id, step)              그 단계의 저장된 계획 (position, key_sha256) — 두 칸만(RM1b)
    segment_counts(company_id, run_id)                  단계 → 구획 셈·첫 시작·끝 시각(쿼리 하나, data 0 — RM1b)
    running_segments(company_id, run_id, step)          그 단계의 running 머리(임대 포함, 계획 차례 — RM1b 잡기)
    first_pending(company_id, run_id, step)             그 단계의 계획 차례 첫 pending 머리(RM1b 잡기)
    segment_head(company_id, run_id, step, key_sha256)  구획 하나의 머리(RM1b 끝냄)
    alive_segments(company_id, run_id, step, now)       그 단계의 임대 산 running 수(RM1b 이어 넣기)
    done_octets(company_id, run_id, step)               그 단계의 done 구획 data_octets 합(RM1b 합 검사)
    ended_segments(company_id, run_id)                  그 실행 안에서 끝난 구획(done·failed): 단계 → 열쇠 sha →
                                                        산출 또는 실패 code. 실행기가 이어 도는 시도에 넘긴다
    earliest_lease(company_id, run_id, step, now)       그 단계의 임대 산 running 가운데 가장 이른 임대 끝(RM1c ③′)
    segments_to_carry(company_id, run_id)               그 실행의 구획 전부(옮길 칸, 단계·계획 차례 — RM1c)
    segment_refs(company_id, run_id, step)              구획 머리(data 0): NoRows | Planned(refs) — RM1c
    segment_outputs(company_id, run_id, step, shas)     고른 열쇠 가운데 done 의 data(sha → data — RM1c)
    segment_page(company_id, run_id, step, status,      구획 한 쪽(계획 차례, data 0 — RM1c GET /runs/{id}/segments)
                 limit, offset)

★ 조회마다 회사 조건을 적는다. run_runs·run_steps 를 읽는 문은 `_runs`·`_steps` 하나씩이다
  (core/tests/test_selector_scope.py 의 GATES). 결과·파일 표는 <표>.for_company(company_id) 로 바로 연다.
★ 남의 회사 실행은 「없음」과 같다(RunNotFound·None). 둘을 구별하지 않는다.
★ step_output 의 파일은 이름·꼴·크기만 준다(FileRef). 바이트는 저장소에서 따로 읽는다(쪽 하나만 읽는 경로가 실행
  결과 전체를 메모리에 올리지 않게 — 처분 ⑧).
"""

import json
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.db import DataError, connection, transaction
from django.db.models import (
    Case,
    CharField,
    Count,
    F,
    Func,
    IntegerField,
    JSONField,
    Max,
    Min,
    Q,
    QuerySet,
    Sum,
    TextField,
    Value,
    When,
)
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Cast, Coalesce, StrIndex

from esgapi.core.flows.types import SegmentEnded, SegmentFailure, SegmentOutput
from esgapi.runs.calc.segments import SegmentCarry, SegmentCounts, SegmentHead, SegmentRef
from esgapi.runs.models import ORDERED_JSON_TAG, RunFileRow, RunResultRow, RunRow, RunSegmentRow, RunStepRow
from esgapi.runs.service.selectors.jobs import NotInTransactionError


@dataclass(frozen=True, slots=True)
class Run:
    id: int
    company_id: int
    document_id: int | None  # None = 문서 없는 흐름의 실행(ND1)
    module: str
    flow_id: str
    options: dict[str, object]
    versions: dict[str, object]
    purpose: str
    status: str
    attempts: int
    stalled_attempts: int
    progress_attempt: int | None
    created_by_user_id: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    failed_step: str | None
    error_code: str | None
    error_message: str | None
    resumed_from_run_id: int | None


@dataclass(frozen=True, slots=True)
class RunStep:
    name: str
    position: int
    status: str
    done: int | None
    total: int | None
    data: dict[str, object] | None
    partial: dict[str, object] | None
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class RunStepHead:
    """단계의 머리(산출 data·부분 partial 없이). started_at 은 처음 시작 한 번, finished_at 은 done·failed 때."""

    name: str
    position: int
    status: str
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class RunStepLine:
    """단계의 머리 + 진행 수(done·total). 산출 data·부분 partial 없이 — 목록이 진행 중 실행을 폴링해도 본문이
    안 실린다."""

    name: str
    position: int
    status: str
    done: int | None
    total: int | None
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class RunKey:
    """실행의 열쇠 칸(옵션 본문 없이). batch_id·part 는 옵션의 batchId·part 글자(없으면 None)."""

    id: int
    document_id: int | None
    status: str
    created_at: datetime
    finished_at: datetime | None
    created_by_user_id: int
    batch_id: str | None
    part: str | None


@dataclass(frozen=True, slots=True)
class RunFile:
    step: str | None  # None = 흐름의 출력 파일
    name: str
    media_type: str
    storage_key: str
    size_bytes: int
    sha256: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RunResult:
    position: int
    schema_version: str
    body: object


@dataclass(frozen=True, slots=True)
class FileRef:
    name: str
    media_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class StepFound:
    data: dict[str, object]
    files: tuple[FileRef, ...]


@dataclass(frozen=True, slots=True)
class StepNotDone:
    """그 단계가 없거나 아직 끝나지 않았다(실행은 있다)."""


@dataclass(frozen=True, slots=True)
class Keyed:
    """Idempotency-Key 로 찾은 실행과 그 요청의 본문 sha256(runs/calc/idempotency.py — 다시 보냄이 같은 요청인지)."""

    run: Run
    body_sha256: str


@dataclass(frozen=True, slots=True)
class RunPage:
    count: int  # 조건에 맞는 전부의 수
    runs: tuple[tuple[Run, str | None], ...]  # (실행, 문서 파일 이름 — 문서 없는 실행은 None). 이름은 목록 줄에만


@dataclass(frozen=True, slots=True)
class RunNotFound:
    """그런 실행이 없다. 다른 회사의 실행도 이 갈래다."""


def run_of(row: RunRow) -> Run:
    return Run(
        id=row.id,
        company_id=row.company_id,
        document_id=row.document_id,
        module=row.module,
        flow_id=row.flow_id,
        options=dict(row.options),
        versions=dict(row.versions),
        purpose=row.purpose,
        status=row.status,
        attempts=row.attempts,
        stalled_attempts=row.stalled_attempts,
        progress_attempt=row.progress_attempt,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        failed_step=row.failed_step,
        error_code=row.error_code,
        error_message=row.error_message,
        resumed_from_run_id=row.resumed_from_run_id,
    )


def _step_of(row: RunStepRow) -> RunStep:
    return RunStep(
        name=row.name,
        position=row.position,
        status=row.status,
        done=row.done,
        total=row.total,
        data=row.data,
        partial=row.partial,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _file_of(row: RunFileRow) -> RunFile:
    return RunFile(
        step=row.step,
        name=row.name,
        media_type=row.media_type,
        storage_key=row.storage_key,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        created_at=row.created_at,
    )


def _runs(company_id: int) -> "QuerySet[RunRow]":
    """그 회사의 실행 행. 이 파일에서 run_runs 를 읽는 문은 여기 하나다."""
    return RunRow.for_company(company_id)


def _steps(company_id: int) -> "QuerySet[RunStepRow]":
    """그 회사의 단계 행. 이 파일에서 run_steps 를 읽는 문은 여기 하나다."""
    return RunStepRow.for_company(company_id)


def lock_run(*, company_id: int, run_id: int) -> RunRow | None:
    """그 회사의 그 실행 행을 FOR UPDATE 로 읽는다. 변경 트랜잭션 안에서만 부른다(밖이면 Django 가 던진다)."""
    return _runs(company_id).select_for_update().filter(pk=run_id).first()


def find_run(*, company_id: int, run_id: int) -> Run | None:
    """그 회사의 그 실행. 없으면(남의 것이어도) None. 잠그지 않는다."""
    row = _runs(company_id).filter(pk=run_id).first()
    return None if row is None else run_of(row)


def run_by_key(*, company_id: int, created_by_user_id: int, key: str) -> Keyed | None:
    """그 회사에서 그 사람이 그 열쇠로 만든 실행(문 하나 — 유일 제약 run_runs_idempotency_uniq 라 많아야 하나). 없으면
    None. 남의 회사·같은 회사 다른 사람의 같은 열쇠는 「없음」이다. 잠그지 않는다."""
    row = _runs(company_id).filter(created_by_user_id=created_by_user_id, idempotency_key=key).first()
    if row is None or row.idempotency_sha256 is None:  # 짝 CHECK 라 열쇠가 있으면 sha 도 있다
        return None
    return Keyed(run=run_of(row), body_sha256=row.idempotency_sha256)


def run_page(
    *,
    company_id: int,
    module: str | None,
    status: str | None,
    document_id: int | None,
    limit: int,
    offset: int,
    modules: Collection[str] | None = None,
    statuses: Collection[str] | None = None,
    created_by_user_id: int | None = None,
) -> RunPage:
    """그 회사의 실행 한 쪽. 조건은 전부 「같다」(None 이면 거르지 않음).
    `modules` 는 모듈 집합으로 거른다(운영 관리자의 목록 — MARC-ENT-380. `module` 과 함께면 둘 다).
    `statuses` 는 상태 집합(대기·진행 한 탭 — DV1g. `status` 와 함께면 둘 다)·`created_by_user_id` 는 만든 사람(내 것
    — DV1g).
    새 것 먼저(created_at 내림, 같으면 id 내림)."""
    rows = _runs(company_id)
    if module is not None:
        rows = rows.filter(module=module)
    if modules is not None:
        rows = rows.filter(module__in=modules)
    if statuses is not None:
        rows = rows.filter(status__in=statuses)
    if created_by_user_id is not None:
        rows = rows.filter(created_by_user_id=created_by_user_id)
    if status is not None:
        rows = rows.filter(status=status)
    if document_id is not None:
        rows = rows.filter(document_id=document_id)
    rows = rows.order_by("-created_at", "-id")
    lines: list[tuple[Run, str | None]] = []
    for row in rows.annotate(document_name=F("document__file_name"))[offset : offset + limit]:
        # annotate 한 칸 — LEFT JOIN 이라 문서 없는 실행(ND1)은 None(str 로 바꾸면 글자 "None" 이 된다)
        name = row.document_name  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        lines.append((run_of(row), None if name is None else str(name)))  # pyright: ignore[reportUnknownArgumentType]
    return RunPage(count=rows.count(), runs=tuple(lines))


def step_rows(*, company_id: int, run_id: int) -> tuple[RunStep, ...]:
    """그 실행의 단계(선언 차례). 실행이 없으면(남의 것이어도) 빈 튜플."""
    return tuple(_step_of(row) for row in _steps(company_id).filter(run_id=run_id).order_by("position"))


def step_rows_of(*, company_id: int, run_ids: Collection[int]) -> dict[int, tuple[RunStep, ...]]:
    """실행들의 단계(실행 id → 선언 차례). step_rows 의 묶음 꼴 — 쿼리 하나(run_ids 가 비면 0). 남의 회사 실행·단계
    없는 실행은 열쇠가 없다. 입력 길이의 상한은 부르는 쪽이 지킨다."""
    found: dict[int, list[RunStep]] = {}
    for row in _steps(company_id).filter(run_id__in=run_ids).order_by("run_id", "position"):
        found.setdefault(row.run_id, []).append(_step_of(row))
    return {run_id: tuple(steps) for run_id, steps in found.items()}


def step_heads(*, company_id: int, run_id: int) -> tuple[RunStepHead, ...]:
    """그 실행의 단계 머리(선언 차례). 실행이 없으면(남의 것이어도) 빈 튜플. 쿼리 1(칸 다섯만 — data·partial 은
    SELECT 에 없다)."""
    rows = (
        _steps(company_id)
        .filter(run_id=run_id)
        .order_by("position")
        .values("name", "position", "status", "started_at", "finished_at")
    )
    return tuple(
        RunStepHead(
            name=row["name"],
            position=row["position"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )
        for row in rows
    )


def run_files(*, company_id: int, run_id: int) -> tuple[RunFile, ...]:
    """그 실행의 파일 행 전부(단계 산출 파일과 출력 파일). 만든 차례."""
    rows = RunFileRow.for_company(company_id).filter(run_id=run_id).order_by("id")
    return tuple(_file_of(row) for row in rows)


def step_output(*, company_id: int, run_id: int, step: str) -> StepFound | StepNotDone | RunNotFound:
    """끝난 단계의 산출(data 와 파일의 이름·꼴·크기). 성공한 실행의 것도 지우지 않으므로 늘 읽힌다(MARC-ENT-208)."""
    if not _runs(company_id).filter(pk=run_id).exists():
        return RunNotFound()
    row = _steps(company_id).filter(run_id=run_id, name=step, status="done").first()
    if row is None or row.data is None:
        return StepNotDone()
    files = RunFileRow.for_company(company_id).filter(run_id=run_id, step=step).order_by("id")
    return StepFound(
        data=row.data,
        files=tuple(FileRef(name=f.name, media_type=f.media_type, size_bytes=f.size_bytes) for f in files),
    )


def output_file(*, company_id: int, run_id: int, name: str) -> RunFile | None:
    """흐름의 출력 파일(step NULL) 하나. 없으면(남의 실행·단계 산출 파일의 이름이어도) None."""
    row = RunFileRow.for_company(company_id).filter(run_id=run_id, step__isnull=True, name=name).first()
    return None if row is None else _file_of(row)


# 이어 받은 실행이 이 상태면 그 앞 실행을 다시 이어 돌리지 않는다(failed 인 자식은 막지 않는다)
ALIVE_STATUSES = ("queued", "processing", "done")


def resumed_alive(*, company_id: int, run_id: int) -> bool:
    """그 회사에서 그 실행을 이어 받은(resumed_from_run_id) 실행 가운데 queued·processing·done 이 있는가."""
    return _runs(company_id).filter(resumed_from_run_id=run_id, status__in=ALIVE_STATUSES).exists()


def run_results(*, company_id: int, run_id: int) -> tuple[RunResult, ...]:
    rows = RunResultRow.for_company(company_id).filter(run_id=run_id).order_by("position")
    return tuple(RunResult(position=r.position, schema_version=r.schema_version, body=r.body) for r in rows)


def results_of(
    *, company_id: int, run_ids: Collection[int], schema_versions: Collection[str] | None = None
) -> dict[int, tuple[RunResult, ...]]:
    """실행들의 결과(실행 id → 차례대로). run_results 의 묶음 꼴 — 쿼리 하나(run_ids 가 비면 0). 남의 회사 실행·결과
    없는 실행은 열쇠가 없다. 입력 길이의 상한은 부르는 쪽이 지킨다.
    `schema_versions` 를 주면 그 꼴의 결과만 읽는다(큰 본문을 건너뛰고 요약만 — TR3b). None 이면 전부."""
    rows = RunResultRow.for_company(company_id).filter(run_id__in=run_ids).order_by("run_id", "position")
    if schema_versions is not None:
        rows = rows.filter(schema_version__in=schema_versions)
    found: dict[int, list[RunResult]] = {}
    for r in rows:
        found.setdefault(r.run_id, []).append(
            RunResult(position=r.position, schema_version=r.schema_version, body=r.body)
        )
    return {run_id: tuple(results) for run_id, results in found.items()}


# run_keys 가 옵션에서 꺼내는 열쇠(이 둘뿐 — runs/models.py OrderedJSONField 머리말의 이름 붙인 예외)
RUN_KEY_OPTIONS = ("batchId", "part")

# 감싼 글자 안의 JSON 탈출 가운데 pg 의 ::jsonb 가 받지 않는 것(unsupported Unicode escape — MARC-ISSUE-442):
# \u0000 · 뒤에 하위가 안 붙은 상위 서로게이트(\ud800~\udbff) · 바로 앞에 상위가 없는 하위(\udc00~\udfff).
# 정상 짝(이모지 \ud83d\ude00)은 pg 가 받으니 걸리지 않는다. 탈출은 \u 앞의 역슬래시가 홀수 개인 것만 —
# _REAL 이 「글 머리 또는 역슬래시 아닌 글자 + 역슬래시 짝」(글자 그대로의 \\u0000 은 탈출이 아니다).
# pg 정규식(ARE)으로 쓴다. lookbehind 를 머리에 두면 자리마다 돌아 큰 옵션(수백 KB)에서 수십 배 느려서, 하위 갈래만
# 하위를 읽은 뒤에 「앞이 진짜 상위였나」를 본다. 이 글자의 줄은 jsonb 로 풀지 않는다(run_keys·run_page_brief).
# ★ 이 정규식은 대체 길에서만 쓴다: 보통 길은 BASE 의 SQL 그대로 세이브포인트 안에서 돌고, ::jsonb 가
#   _lone_escape_error 로 떨어질 때만 정규식 판으로 다시 읽는다(보통 줄의 비용 0 — e7 조건, MARC-TICK-424 노트).
_REAL = r"(?:^|[^\\])(?:\\\\)*"
_HIGH = r"\\u[dD][89abAB][0-9a-fA-F]{2}"
_LOW = r"\\u[dD][c-fC-F][0-9a-fA-F]{2}"
LONE_ESCAPE = rf"{_REAL}(?:\\u0000|{_HIGH}(?!{_LOW})|{_LOW}(?<!{_REAL}{_HIGH}{_LOW}))"
# run_keys 에서 위 글자의 줄이 jsonb 대신 푸는 꼴 — 열쇠 값이 이 글자면 그 줄은 두 번째 쿼리로 파이썬이 센다
_LONE_PLACEHOLDER = {"dvi1": "lone escape"}
LONE_KEY_TEXT = json.dumps(_LONE_PLACEHOLDER)  # jsonb ->> 의 글자 꼴과 같다({"dvi1": "lone escape"})


def _wrapped_text() -> KeyTextTransform:
    return KeyTextTransform(ORDERED_JSON_TAG, "options")


def _lone_escape_error(error: DataError) -> bool:
    """감싼 글자의 ::jsonb 가 LONE_ESCAPE 로 떨어진 오류인가 — 22P05(unsupported Unicode escape — \\u0000)와
    json 입력 꼴 오류로 좁힌 22P02(외톨이 서로게이트). 그 밖의 DataError 는 아니다(부르는 쪽이 다시 던진다)."""
    cause = error.__cause__
    state = getattr(cause, "sqlstate", None)
    if state == "22P05":
        return True
    diag = getattr(cause, "diag", None)
    return state == "22P02" and getattr(diag, "message_primary", None) == "invalid input syntax for type json"


def _option_text(key: str, *, lone_safe: bool = False) -> Coalesce:
    """옵션 칸의 열쇠 하나를 글자로. 감싼 값({"ordered@1": "<json 글자>"})은 안쪽 글자를 jsonb 로 풀어서, 감싸지 않은
    옛 값은 그대로 읽는다(OrderedJSONField.from_db_value 와 같은 두 갈래). 없으면 NULL.
    lone_safe(대체 길)면 안쪽 글자에 LONE_ESCAPE 가 있을 때 글자 통째를 {key: _LONE_PLACEHOLDER} 로 바꿔 풀어
    (::jsonb 가 늘 받는다) 값이 LONE_KEY_TEXT 가 된다 — 옵션 칸 읽기를 열쇠마다 둘(감싼·옛)로 두려고 CASE 대신
    regexp_replace 하나로(MARC-TICK-251 의 투영 둘)."""
    inner: Any = _wrapped_text()
    if lone_safe:
        inner = Func(
            inner,
            Value(f"^.*{LONE_ESCAPE}.*$"),
            Value(json.dumps({key: _LONE_PLACEHOLDER})),
            function="regexp_replace",
            output_field=TextField(),
        )
    wrapped = KeyTextTransform(key, Cast(inner, output_field=JSONField()))
    return Coalesce(wrapped, KeyTextTransform(key, "options"))


def _key_text(value: object) -> str | None:
    """파이썬 값 하나를 jsonb ->> 의 글자로(글자는 그대로, null 은 None, 그 밖은 JSON 글자)."""
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def run_keys(*, company_id: int, module: str, document_id: int | None, limit: int) -> tuple[RunKey, ...]:
    """그 회사·모듈의 실행 열쇠 칸(새 것 먼저 — created_at·id 내림, 많아야 limit). document_id 가 None 이 아니면
    그 문서만. 쿼리 1(세이브포인트 안 — atomic 안에서 부르면 SAVEPOINT·RELEASE 둘이 쿼리로 더 잡힌다). 옵션은
    batchId·part 두 열쇠만 투영한다(옵션 본문을 SELECT 하지 않는다 — 큰 옵션 1,000 행을
    파이썬으로 올리지 않게, MARC-TICK-251). 남의 회사 실행은 나오지 않는다.
    대체 길(MARC-ISSUE-442): 감싼 글자에 LONE_ESCAPE 가 있는 줄 때문에 ::jsonb 가 떨어지면 세이브포인트로 되돌리고
    정규식 판(lone_safe)으로 다시 읽은 뒤, 표지가 나온 줄들의 옵션만 한 쿼리로 읽어 파이썬(json.loads)으로 센다."""
    rows = _runs(company_id).filter(module=module)
    if document_id is not None:
        rows = rows.filter(document_id=document_id)

    def read(*, lone_safe: bool) -> list[dict[str, Any]]:
        return list(
            rows.order_by("-created_at", "-id").values(
                "id",
                "document_id",
                "status",
                "created_at",
                "finished_at",
                "created_by_user_id",
                batch_key=_option_text(RUN_KEY_OPTIONS[0], lone_safe=lone_safe),
                part_key=_option_text(RUN_KEY_OPTIONS[1], lone_safe=lone_safe),
            )[:limit]
        )

    try:
        with transaction.atomic():  # 세이브포인트 — 떨어져도 바깥 트랜잭션은 산다
            found = read(lone_safe=False)
        lone: list[int] = []
    except DataError as error:
        if not _lone_escape_error(error):
            raise
        found = read(lone_safe=True)
        lone = [row["id"] for row in found if LONE_KEY_TEXT in (row["batch_key"], row["part_key"])]
    if lone:  # LONE_ESCAPE 줄만 — 옵션을 ORM 으로 읽어(OrderedJSONField 가 파이썬 json 으로 푼다) 열쇠를 센다
        options = dict(_runs(company_id).filter(pk__in=lone).values_list("id", "options"))
        for row in found:
            if row["id"] in options:
                given: Mapping[str, object] = options[row["id"]] or {}
                row["batch_key"], row["part_key"] = (_key_text(given.get(key)) for key in RUN_KEY_OPTIONS)
    return tuple(
        RunKey(
            id=row["id"],
            document_id=row["document_id"],
            status=row["status"],
            created_at=row["created_at"],
            finished_at=row["finished_at"],
            created_by_user_id=row["created_by_user_id"],
            batch_id=row["batch_key"],
            part=row["part_key"],
        )
        for row in found
    )


@dataclass(frozen=True, slots=True)
class BriefRun:
    """run_page_brief 의 줄: 실행 머리 + 옵션의 투영(본문 0 — LONE_ESCAPE 표시 줄만 whole 에 본문)."""

    id: int
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    created_by_user_id: int
    failed_step: str | None
    values: dict[str, object]  # 이름 → 그 경로의 JSON 값(없거나 꼴 밖이면 None)
    shapes: dict[str, tuple[str | None, int | None]]  # 이름 → (jsonb_typeof — 없으면 None, 목록이면 길이)
    whole: dict[str, object] | None  # 감싼 글자 안에 LONE_ESCAPE(\u0000·짝 없는 서로게이트)가 있는 줄만 옵션 본문


@dataclass(frozen=True, slots=True)
class BriefPage:
    count: int
    runs: tuple[BriefRun, ...]


NUL_ESCAPE = "\\u0000"  # 감싼 글자 안의 JSON 꼴 NUL — pg 의 ::jsonb 가 받지 않는다(unsupported Unicode escape)


def _nul_marked(*, lone_safe: bool = False) -> Q:
    """run_page_brief 의 표시: 보통 길은 BASE 그대로 \\u0000 만(StrIndex), 대체 길은 LONE_ESCAPE 전부(정규식)."""
    return Q(_hd1_wrapped__regex=LONE_ESCAPE) if lone_safe else Q(_hd1_nul__gt=0)


def _option_json(path: tuple[str, ...], *, lone_safe: bool = False) -> Coalesce:
    """옵션의 경로 하나를 jsonb 로. 감싼 값은 안쪽 글자를 jsonb 로 풀어서(LONE_ESCAPE 표시 줄은 풀지 않고 NULL), 감싸지
    않은 옛 값은 그대로(_option_text 와 같은 두 갈래). 없으면 NULL."""
    inner: Any = Case(
        When(_nul_marked(lone_safe=lone_safe), then=Value(None, output_field=JSONField())),
        default=Cast(_wrapped_text(), output_field=JSONField()),
        output_field=JSONField(),
    )
    outer: Any = F("options")
    for key in path:
        inner, outer = KeyTransform(key, inner), KeyTransform(key, outer)
    return Coalesce(inner, outer, output_field=JSONField())


def run_page_brief(
    *,
    company_id: int,
    module: str,
    statuses: Collection[str] | None,
    created_by_user_id: int | None,
    limit: int,
    offset: int,
    values: Mapping[str, tuple[str, ...]],
    shapes: Mapping[str, tuple[str, ...]],
) -> BriefPage:
    """run_page(module=…, status=None, document_id=None, statuses=…, created_by_user_id=…)와 같은 거름·차례
    (created_at·id 내림)·count. 옵션 본문은 SELECT 하지 않는다: values 의 경로는 그 JSON 값, shapes 의 경로는
    jsonb_typeof 와 목록 길이만 투영한다(큰 입력을 파이썬으로 올리지 않게 — MARC-ISSUE-347). 예외 하나: 감싼 글자
    안에 LONE_ESCAPE(\\u0000·짝 없는 서로게이트)가 있는 줄은 pg 가 안쪽을 jsonb 로 풀지 못해 그 줄만 본문을 whole 에
    싣는다(같은 쿼리 — 부르는 쪽이 본문으로 셈, 응답이 BASE 와 같게). 쿼리 2(줄·count — 줄은 세이브포인트 안이라
    atomic 안에서 부르면 SAVEPOINT·RELEASE 둘이 쿼리로 더 잡힌다). 남의 회사 실행은 나오지 않는다.
    보통 길은 BASE 그대로 \\u0000 만 표시하고, 짝 없는 서로게이트로 ::jsonb 가 떨어지면(_lone_escape_error)
    세이브포인트로 되돌리고 LONE_ESCAPE 표시 판으로 줄을 다시 읽는다(MARC-ISSUE-442)."""
    rows = _runs(company_id).filter(module=module)
    if statuses is not None:
        rows = rows.filter(status__in=statuses)
    if created_by_user_id is not None:
        rows = rows.filter(created_by_user_id=created_by_user_id)
    rows = rows.order_by("-created_at", "-id")
    head = ("id", "status", "created_at", "started_at", "finished_at", "created_by_user_id", "failed_step")

    def read(*, lone_safe: bool) -> list[dict[str, Any]]:
        if lone_safe:
            marked = rows.alias(_hd1_wrapped=_wrapped_text())
        else:
            marked = rows.annotate(_hd1_nul=StrIndex(_wrapped_text(), Value(NUL_ESCAPE)))
        projected: dict[str, Any] = {
            "_hd1_whole": Case(
                When(_nul_marked(lone_safe=lone_safe), then=F("options")),
                default=Value(None),
                output_field=RunRow._meta.get_field("options"),
            )
        }
        for name, path in values.items():
            projected[f"_hd1_v_{name}"] = _option_json(path, lone_safe=lone_safe)
        for name, path in shapes.items():
            found = _option_json(path, lone_safe=lone_safe)
            projected[f"_hd1_t_{name}"] = Func(found, function="jsonb_typeof", output_field=CharField())
            projected[f"_hd1_n_{name}"] = Case(
                When(**{f"_hd1_t_{name}": "array"}, then=Func(found, function="jsonb_array_length")),
                default=Value(None),
                output_field=IntegerField(),
            )
        return list(marked.annotate(**projected).values(*head, *projected)[offset : offset + limit])

    try:
        with transaction.atomic():  # 세이브포인트 — 떨어져도 바깥 트랜잭션은 산다
            lines = read(lone_safe=False)
    except DataError as error:
        if not _lone_escape_error(error):
            raise
        lines = read(lone_safe=True)
    found_runs = tuple(
        BriefRun(
            id=row["id"],
            status=row["status"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            created_by_user_id=row["created_by_user_id"],
            failed_step=row["failed_step"],
            values={name: row[f"_hd1_v_{name}"] for name in values},
            shapes={name: (row[f"_hd1_t_{name}"], row[f"_hd1_n_{name}"]) for name in shapes},
            whole=None if row["_hd1_whole"] is None else dict(row["_hd1_whole"]),
        )
        for row in lines
    )
    return BriefPage(count=rows.count(), runs=found_runs)


def runs_of(*, company_id: int, run_ids: Collection[int]) -> dict[int, Run]:
    """실행들(실행 id → Run). find_run 의 묶음 꼴 — 쿼리 하나(run_ids 가 비면 0). 남의 회사 실행·없는 id 는 열쇠가
    없다. 입력 길이의 상한은 부르는 쪽이 지킨다."""
    return {row.id: run_of(row) for row in _runs(company_id).filter(pk__in=run_ids)}


def step_lines_of(*, company_id: int, run_ids: Collection[int]) -> dict[int, tuple[RunStepLine, ...]]:
    """실행들의 단계 머리 + done·total(실행 id → 선언 차례). step_heads 의 묶음 꼴 — 쿼리 하나(run_ids 가 비면 0),
    data·partial 은 SELECT 에 없다. 남의 회사 실행·단계 없는 실행은 열쇠가 없다."""
    rows = (
        _steps(company_id)
        .filter(run_id__in=run_ids)
        .order_by("run_id", "position")
        .values("run_id", "name", "position", "status", "done", "total", "started_at", "finished_at")
    )
    found: dict[int, list[RunStepLine]] = {}
    for row in rows:
        found.setdefault(row["run_id"], []).append(
            RunStepLine(
                name=row["name"],
                position=row["position"],
                status=row["status"],
                done=row["done"],
                total=row["total"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
            )
        )
    return {run_id: tuple(lines) for run_id, lines in found.items()}


def stale_runs(*, company_id: int, now: datetime, queued_older_than_s: int) -> tuple[Run, ...]:
    """쪽지를 잃었을 수 있는 실행: 임대가 지난(또는 없는) processing 과, 그만큼 오래 머문 queued.

    고르기만 한다(잠그지 않는다). 같은 실행이 두 번 넣어져도 잡기가 거른다(stale_jobs 와 같은 꼴).
    """
    if not connection.in_atomic_block:
        raise NotInTransactionError("stale_runs 는 transaction.atomic() 안에서만 부른다")
    lapsed = Q(status="processing") & (Q(lease_expires_at__lte=now) | Q(lease_expires_at__isnull=True))
    waiting = Q(status="queued", updated_at__lte=now - timedelta(seconds=queued_older_than_s))
    return tuple(run_of(row) for row in _runs(company_id).filter(lapsed | waiting).order_by("created_at", "id"))


# ── 구획(RM1a) ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RunSegment:
    """펼침 단계의 구획 하나(표 run_segments). key 는 정규화 칸(kind·span·documentSha256·parserVersion)."""

    step: str
    position: int
    kind: str
    key: dict[str, object]
    key_sha256: str
    status: str
    attempts: int
    data: dict[str, object] | None
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None


def segment_rows(*, company_id: int, run_id: int, step: str) -> tuple[RunSegment, ...]:
    """그 실행의 그 단계의 구획(계획 차례). 계획 전이거나 실행이 없으면(남의 것이어도) 빈 튜플."""
    rows = RunSegmentRow.for_company(company_id).filter(run_id=run_id, step=step).order_by("position")
    return tuple(
        RunSegment(
            step=row.step,
            position=row.position,
            kind=row.kind,
            key=row.key,
            key_sha256=row.key_sha256,
            status=row.status,
            attempts=row.attempts,
            data=row.data,
            error_code=row.error_code,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )
        for row in rows
    )


def ended_segments(*, company_id: int, run_id: int) -> dict[str, dict[str, SegmentEnded]]:
    """그 실행 안에서 끝난 구획(done·failed 둘 다): 단계 → 열쇠 sha → SegmentOutput | SegmentFailure. 쿼리 하나.
    끝난 구획이 없는 단계는 열쇠가 없다(장벽 흐름·아직 계획 전·계획됨 0 — 셋을 가르는 것은 segment_rows 와 단계 행)."""
    found: dict[str, dict[str, SegmentEnded]] = {}
    rows = (
        RunSegmentRow.for_company(company_id)
        .filter(run_id=run_id, status__in=("done", "failed"))
        .order_by("step", "position")
    )
    for row in rows:
        ended: SegmentEnded
        if row.status == "done":
            if row.data is None:  # CHECK(run_segments_status_fields_check)가 막는다 — 방어
                raise ValueError(f"run_segments 의 done 행에 data 가 없다: {row.pk}")
            ended = SegmentOutput(data=row.data)
        else:
            if row.error_code is None:  # 위와 같다
                raise ValueError(f"run_segments 의 failed 행에 error_code 가 없다: {row.pk}")
            ended = SegmentFailure(error_code=row.error_code)
        found.setdefault(row.step, {})[row.key_sha256] = ended
    return found


# ── 구획 쪽지(RM1b) ───────────────────────────────────────────────────


def segment_plan(*, company_id: int, run_id: int, step: str) -> list[tuple[int, str]]:
    """그 단계의 저장된 계획 (position, key_sha256)(계획 차례). 두 칸만 읽는다(data·key 0 — 635-2). 계획 전이면 []."""
    rows = (
        RunSegmentRow.for_company(company_id)
        .filter(run_id=run_id, step=step)
        .order_by("position")
        .values_list("position", "key_sha256")
    )
    return [(position, sha) for position, sha in rows]


def segment_counts(*, company_id: int, run_id: int) -> dict[str, SegmentCounts]:
    """그 실행의 펼침 단계마다 구획 셈(pending·running·done·failed)과 첫 시작·마지막 끝 시각. 쿼리 하나(data 0).
    구획 행이 없는 단계(장벽·계획 전·계획됨 0)는 열쇠가 없다. 남의 회사 실행이면 빈 사전."""
    rows = (
        RunSegmentRow.for_company(company_id)
        .filter(run_id=run_id)
        .values("step")
        .annotate(
            pending=Count("id", filter=Q(status="pending")),
            running=Count("id", filter=Q(status="running")),
            done=Count("id", filter=Q(status="done")),
            failed=Count("id", filter=Q(status="failed")),
            first_started_at=Min("started_at"),
            last_finished_at=Max("finished_at"),
        )
        .order_by("step")
    )
    return {
        row["step"]: SegmentCounts(
            pending=row["pending"],
            running=row["running"],
            done=row["done"],
            failed=row["failed"],
            first_started_at=row["first_started_at"],
            last_finished_at=row["last_finished_at"],
        )
        for row in rows
    }


_HEAD_FIELDS = ("position", "key_sha256", "status", "attempts", "lease_expires_at")


def _head_of(row: Mapping[str, Any]) -> SegmentHead:
    return SegmentHead(
        position=row["position"],
        key_sha256=row["key_sha256"],
        status=row["status"],
        attempts=row["attempts"],
        lease_expires_at=row["lease_expires_at"],
    )


def running_segments(*, company_id: int, run_id: int, step: str) -> tuple[SegmentHead, ...]:
    """그 단계의 running 구획 머리(계획 차례 — 임대 산 것·잡을 수 있는 것 둘 다)."""
    rows = (
        RunSegmentRow.for_company(company_id)
        .filter(run_id=run_id, step=step, status="running")
        .order_by("position")
        .values(*_HEAD_FIELDS)
    )
    return tuple(_head_of(row) for row in rows)


def first_pending(*, company_id: int, run_id: int, step: str) -> SegmentHead | None:
    """그 단계의 계획 차례 첫 pending 구획 머리. 없으면 None."""
    row = (
        RunSegmentRow.for_company(company_id)
        .filter(run_id=run_id, step=step, status="pending")
        .order_by("position")
        .values(*_HEAD_FIELDS)
        .first()
    )
    return None if row is None else _head_of(row)


def segment_head(*, company_id: int, run_id: int, step: str, key_sha256: str) -> SegmentHead | None:
    """구획 하나의 머리(data 0). 없으면 None."""
    row = (
        RunSegmentRow.for_company(company_id)
        .filter(run_id=run_id, step=step, key_sha256=key_sha256)
        .values(*_HEAD_FIELDS)
        .first()
    )
    return None if row is None else _head_of(row)


def alive_segments(*, company_id: int, run_id: int, step: str, now: datetime) -> int:
    """그 단계에서 임대가 남은 running 구획 수(다른 쪽지가 돌고 있는 것)."""
    return (
        RunSegmentRow.for_company(company_id)
        .filter(run_id=run_id, step=step, status="running", lease_expires_at__gt=now)
        .count()
    )


def done_octets(*, company_id: int, run_id: int, step: str) -> int:
    """그 단계의 done 구획 data_octets 합(병렬 끝냄이 적은 것 — 직렬의 done 은 NULL 이라 0 으로 센다)."""
    found = (
        RunSegmentRow.for_company(company_id)
        .filter(run_id=run_id, step=step, status="done")
        .aggregate(total=Coalesce(Sum("data_octets"), 0))
    )
    return int(found["total"])


def earliest_lease(*, company_id: int, run_id: int, step: str, now: datetime) -> datetime | None:
    """그 단계에서 임대가 남은 running 구획 가운데 가장 이른 lease_expires_at. 없으면 None(RM1c ③′ M1)."""
    found = (
        RunSegmentRow.for_company(company_id)
        .filter(run_id=run_id, step=step, status="running", lease_expires_at__gt=now)
        .aggregate(earliest=Min("lease_expires_at"))
    )
    earliest = found["earliest"]
    return earliest if isinstance(earliest, datetime) else None


# ── 구획 옮김·짝짓기(RM1c) ────────────────────────────────────────────


def segments_to_carry(*, company_id: int, run_id: int) -> tuple[SegmentCarry, ...]:
    """그 실행의 구획 행 전부(단계·계획 차례) — 새 실행이 옮길 칸(attempts·임대는 싣지 않는다). 쿼리 하나. 남의 회사
    실행이면 빈 튜플(부르는 쪽은 앞 실행을 이미 잠가 읽었다)."""
    rows = RunSegmentRow.for_company(company_id).filter(run_id=run_id).order_by("step", "position")
    return tuple(
        SegmentCarry(
            step=row.step,
            position=row.position,
            kind=row.kind,
            key=row.key,
            key_sha256=row.key_sha256,
            status=row.status,
            data=row.data,
            data_octets=row.data_octets,
            error_code=row.error_code,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )
        for row in rows
    )


@dataclass(frozen=True, slots=True)
class NoRows:
    """그 단계의 구획 행이 없다: 「계획 전」·「계획됨 0」·장벽 단계·없는(남의) 실행.
    가르는 것은 부르는 쪽(단계 상태)."""


@dataclass(frozen=True, slots=True)
class Planned:
    """그 단계의 구획 머리(계획 차례 — 하나 이상)."""

    refs: tuple[SegmentRef, ...]


def segment_refs(*, company_id: int, run_id: int, step: str) -> NoRows | Planned:
    """그 실행의 그 단계의 구획 머리(data 0, 계획 차례). 행이 없으면 NoRows. 같은 회사만(남의 실행은 NoRows)."""
    rows = (
        RunSegmentRow.for_company(company_id)
        .filter(run_id=run_id, step=step)
        .order_by("position")
        .values("position", "key_sha256", "key", "status", "error_code")
    )
    refs = tuple(
        SegmentRef(
            position=row["position"],
            key_sha256=row["key_sha256"],
            key=row["key"],
            status=row["status"],
            error_code=row["error_code"],
        )
        for row in rows
    )
    return Planned(refs) if refs else NoRows()


@dataclass(frozen=True, slots=True)
class SegmentLine:
    """구획 목록의 한 줄(RM1c — GET /runs/{run_id}/segments). data 0."""

    position: int
    key_sha256: str
    key: dict[str, object]
    status: str
    attempts: int
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class SegmentPage:
    count: int
    lines: tuple[SegmentLine, ...]


def segment_page(
    *, company_id: int, run_id: int, step: str, status: str | None, limit: int, offset: int
) -> SegmentPage:
    """그 실행의 그 단계의 구획 한 쪽(계획 차례, data 0). status 는 「같다」(None 이면 거르지 않음). 같은 회사만(남의
    실행은 count 0 — 부르는 쪽이 실행을 먼저 본다)."""
    rows = RunSegmentRow.for_company(company_id).filter(run_id=run_id, step=step)
    if status is not None:
        rows = rows.filter(status=status)
    found = rows.order_by("position").values(
        "position", "key_sha256", "key", "status", "attempts", "error_code", "started_at", "finished_at"
    )[offset : offset + limit]
    lines = tuple(
        SegmentLine(
            position=row["position"],
            key_sha256=row["key_sha256"],
            key=row["key"],
            status=row["status"],
            attempts=row["attempts"],
            error_code=row["error_code"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )
        for row in found
    )
    return SegmentPage(count=rows.count(), lines=lines)


def segment_outputs(*, company_id: int, run_id: int, step: str, shas: Collection[str]) -> dict[str, dict[str, object]]:
    """그 단계의 구획 가운데 열쇠 sha 가 shas 에 든 done 의 data(sha → data). done 아닌 것·없는 sha 는 빠진다. 같은
    회사만."""
    rows = (
        RunSegmentRow.for_company(company_id)
        .filter(run_id=run_id, step=step, status="done", key_sha256__in=list(shas))
        .order_by("position")
        .values_list("key_sha256", "data")
    )
    return {sha: data for sha, data in rows if data is not None}
