"""읽기. 운영 관리자의 실행 기록(AD-04 — AU1b-2. 경로는 user 의 service/apis/run_logs.py). 쓰지 않는다.

    operator_run_page(actor_kind, company_id, module, status, date_from, date_to, q, limit, offset, review)
                                    고른 회사의 실행 한 쪽(모든 모듈, 새 것 먼저 — created_at·id 내림, 문서 이름째,
                                    검토·AI 설정 칸째)
    operator_run_export(actor_kind, company_id, module, status, date_from, date_to, q, review, cap)
                                    같은 거르기의 전부(쪽 없음, 같은 차례). cap 을 넘으면 셈만 하고 읽지 않는다
    operator_run_cohort(actor_kind, company_id, start, end)
                                    created_at 이 [start, end) 인 실행 무리(지표 다섯 — core/calc/run_metrics.py)
    operator_run_detail(actor_kind, company_id, run_id)
                                    실행 하나의 줄 칸 + 실패 단계·오류 코드 + 단계 머리 + 파일(AD4D — AD-04a)
    operator_run_file(actor_kind, company_id, run_id, name)
                                    실행 하나(모든 모듈)의 출력 파일(step NULL) 한 행(RF1 — 바이트는 경로가 runs 의
                                    services/files.py 로 읽는다). 단계 산출 파일의 이름은 RunFileMissing

공개 함수 다섯의 첫 문장이 자기 동작 칸의 권한 검사다(core/permissions.py 의 표 — user_run_log_list·
user_run_log_export·user_run_log_metrics·user_run_log_get·user_run_log_file_get 은 운영 관리자만).
막히면 아무것도 읽지 않는다(core/tests/test_permissions.py 의 ALSO_INSIDE).
보는 범위(처분 ①): 경로가 고른 회사 하나(user 의 chosen_company). run_runs 를 읽는 문은 `_runs` 하나다(runs.py 와 같은
이름·몸). 문서 이름은 같은 회사 복합 FK(run_runs.document)를 따라 같은 쿼리에서 읽는다(남의 회사 문서로 닿는 길 0).
문서 없는 실행(ND1 — 문서 칸 NULL)은 두 칸 None 이다(NULL 허용 FK 라 LEFT JOIN — 줄이 빠지지 않는다). q(문서 이름)로
거르면 빠진다.
날짜는 KST 의 하루다: date_from 그날 00:00(+09:00)부터, date_to 그날 끝(다음 날 00:00 앞)까지. 둘 다 포함.
q 는 문서 이름의 부분 일치(icontains — % _ 는 글자), 대소문자 무시. count 는 거른 뒤의 수다.
검토·AI 설정 칸(AD4S)은 모듈의 원천(runs/extras.py 의 EXTRAS — 규칙은 그 머리말)이 채운다. review 거르기도 원천의
술어·검토 행으로 count·쪽 앞에서 거른다(부분 쿼리 — 결과 join 으로 줄이 불지 않게). 원천이 없는 모듈은 두 칸 null 이고
review 거르기에 걸리지 않는다.

믿는 칸만 읽는다(X1b-1 의 runs/models.py RunRow 머리글): module·flow_id·document·status·purpose·created_by_user_id·
created_at·started_at·finished_at·versions·launch_key·resumed_from_run_id(뒤 둘은 만들 때 한 번 — LK1). versions 는
만들 때 한 번 적힌다(runs/models.py RunRow 머리글) — 판 열쇠만 원천이 읽는다. 믿지 않는 칸(stalled_attempts·
progress_attempt)과 비밀이 될 수 있는 칸(options·error_message·단계 data·partial)은 읽지 않는다. purpose 는 거르지
않고 칸으로 읽는다(지표에서 빼는 자리는 순수 metrics 하나 — 처분 ⑤ ㉧).
상세(AD4D)는 failed_step·error_code(runs 의 오류 코드 글자)와 단계 시각을 읽는다(고객사 runs_get 이 이미 내는 칸).
단계 시각의 뜻: started_at 은 처음 시작 한 번(runs/service/services/runs.py 의 Coalesce — 마감·다시 넣기 대기를 품는다),
finished_at 은 done·failed 때. 그래서 단계의 처리 시간도 다시 넣기 대기를 품는다.
무효 조건: 회사가 둘이 되면 운영 관리자는 회사마다 따로 본다(모든 회사 입구는 2차 — 처분 ① (나)).
이어서 재실행(resumed_from_run_id — X1b-2)이 채워지면 이어 돈 실행도 따로 한 줄이다.
같이 시작한 묶음(LK1 — launch_key)의 첫 id·차례·수는 저장하지 않고 읽을 때 센다(_launches): 쪽(또는 상세)에 실린 줄의
열쇠들로 같은 회사의 묶음 전체를 한 쿼리로 읽어 (만든 사람, 열쇠)마다 id 오름으로 센다 — 거르기·쪽과 무관하다(「실패만」
거른 쪽에서도 2/3 은 2/3). 열쇠 있는 줄이 쪽에 없으면 쿼리 0. 열쇠 없는 줄은 네 칸 None(1/1 이 아니다). 내보내기는 세지
않는다(엑셀이 칸을 안 쓴다 — 쿼리 0).
★ 무효 조건: 묶음은 사람 동작 한 번이라 작다고 본다(파트 수 — 추정). 묶음이 커지면 그 크기만큼 더 읽는다.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, cast

from django.db.models import Q, QuerySet

from esgapi.core.auth.principal import Kind
from esgapi.core.calc.run_metrics import KST
from esgapi.core.permissions import is_allowed
from esgapi.runs.extras import EXTRAS
from esgapi.runs.models import RunRow
from esgapi.runs.service.selectors import runs as run_selectors

# 검토 상태 셋(원천의 검토 표 CHECK 와 같은 값 — 그린워싱 tests/service/selectors/test_run_extras.py 가 견준다)
REVIEW_STATES = ("pending", "in_review", "confirmed")

PAGE_FIELDS = (
    "id",
    "module",
    "flow_id",
    "document_id",
    "document__file_name",
    "status",
    "purpose",
    "created_by_user_id",
    "created_at",
    "started_at",
    "finished_at",
    "versions",
    "launch_key",
    "resumed_from_run_id",
)
COHORT_FIELDS = ("id", "status", "purpose", "created_at", "finished_at")


@dataclass(frozen=True, slots=True)
class OperatorRun:
    id: int
    module: str
    flow_id: str
    document_id: int | None  # None = 문서 없는 흐름의 실행(ND1)
    document_name: str | None  # 위와 같다
    status: str
    purpose: str
    created_by_user_id: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    review: str | None  # REVIEW_STATES 하나. 원천이 검토를 보이지 않는 실행이면 None
    ai_setting: tuple[int | None, str] | None  # (판 id — 기본 판은 None, 판 이름). 못 읽으면 None
    launch_key: str | None  # 같이 시작한 묶음의 열쇠(LK1). None = 묶음 없이 만든 실행
    launch_first_run_id: int | None  # 묶음의 첫 실행 id(id 가 가장 작은 것). 열쇠 없거나 세지 않았으면 None
    launch_index: int | None  # 묶음 안 차례(1부터, id 오름). 위와 같다
    launch_size: int | None  # 묶음의 실행 수(거르기·쪽과 무관). 위와 같다
    resumed_from_run_id: int | None  # 이어서 돌린 앞 실행의 id. None = 처음부터 돈 실행


@dataclass(frozen=True, slots=True)
class OperatorRunPage:
    count: int  # 조건에 맞는 전부의 수
    runs: tuple[OperatorRun, ...]


@dataclass(frozen=True, slots=True)
class OperatorRunExport:
    runs: tuple[OperatorRun, ...]  # 거른 전부(새 것 먼저)


@dataclass(frozen=True, slots=True)
class ExportTooLarge:
    """거른 수가 상한을 넘는다(행을 읽지 않았다)."""

    count: int


@dataclass(frozen=True, slots=True)
class CohortRun:
    id: int
    status: str
    purpose: str
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class OperatorRunDetail:
    run: OperatorRun
    failed_step: str | None
    error_code: str | None
    steps: tuple[run_selectors.RunStepHead, ...]  # 선언 차례
    files: tuple[run_selectors.RunFile, ...]  # 만든 차례(step None = 흐름의 출력 파일)


@dataclass(frozen=True, slots=True)
class RunLogForbidden:
    """운영 관리자가 아니다(아무것도 읽지 않았다)."""


@dataclass(frozen=True, slots=True)
class RunFileMissing:
    """실행은 있으나 그 이름의 출력 파일(step NULL)이 없다."""


def kst_day_start(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=KST)


def _runs(company_id: int) -> "QuerySet[RunRow]":
    """그 회사의 실행 행. 이 파일에서 run_runs 를 읽는 문은 여기 하나다."""
    return RunRow.for_company(company_id)


def _review_q(company_id: int, review: str) -> Q | None:
    """review 거르기의 조건(원천이 있는 모듈마다 OR). 원천이 없으면 None(빈 결과)."""
    if review not in REVIEW_STATES:
        raise ValueError(f"모르는 검토 상태: {review}")
    found: Q | None = None
    for module in EXTRAS.modules():
        source = EXTRAS.get(module)
        if source is None:
            continue
        reviewable = Q(module=module) & Q(id__in=_runs(company_id).filter(source.reviewable_q()).values("id"))
        if review == "pending":  # 검토 행이 없거나 pending
            one = reviewable & ~Q(id__in=source.run_ids_in(company_id, {"in_review", "confirmed"}))
        else:
            one = reviewable & Q(id__in=source.run_ids_in(company_id, {review}))
        found = one if found is None else found | one
    return found


def _filtered(
    company_id: int,
    *,
    module: str | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
    review: str | None,
) -> "QuerySet[RunRow]":
    """고른 회사의 실행을 거른 것(전부 AND, None 이면 거르지 않음). 쪽·내보내기가 같은 함수를 쓴다."""
    rows = _runs(company_id)
    if module is not None:
        rows = rows.filter(module=module)
    if status is not None:
        rows = rows.filter(status=status)
    if date_from is not None:
        rows = rows.filter(created_at__gte=kst_day_start(date_from))
    if date_to is not None:
        rows = rows.filter(created_at__lt=kst_day_start(date_to + timedelta(days=1)))
    if q is not None:
        rows = rows.filter(document__file_name__icontains=q)
    if review is not None:
        condition = _review_q(company_id, review)
        rows = rows.none() if condition is None else rows.filter(condition)
    return rows.order_by("-created_at", "-id")


def _extras(company_id: int, rows: list[dict[str, Any]]) -> dict[int, tuple[str | None, tuple[int | None, str] | None]]:
    """읽은 줄의 (검토, AI 설정). 원천이 있는 모듈마다 검토 가능 id 한 번 + (비지 않으면) 검토 상태 한 번."""
    found: dict[int, tuple[str | None, tuple[int | None, str] | None]] = {}
    for module in EXTRAS.modules():
        source = EXTRAS.get(module)
        if source is None:
            continue
        mine = [row for row in rows if row["module"] == module]
        if not mine:
            continue
        reviewable = set(
            _runs(company_id)
            .filter(id__in=[row["id"] for row in mine])
            .filter(source.reviewable_q())
            .values_list("id", flat=True)
        )
        states: Mapping[int, str] = source.states(company_id, reviewable) if reviewable else {}
        for row in mine:
            versions: object = row["versions"]
            setting = source.ai_setting(cast("dict[str, object]", versions)) if isinstance(versions, dict) else None
            review = states.get(row["id"], "pending") if row["id"] in reviewable else None
            found[row["id"]] = (review, setting)
    return found


def _launches(company_id: int, rows: list[dict[str, Any]]) -> dict[int, tuple[int, int, int]]:
    """읽은 줄의 같이 시작한 묶음(run id → (첫 id, 차례, 수)). 묶음 = 같은 회사·같은 만든 사람·같은 열쇠의 실행 전부
    (거르기 무관), 차례는 id 오름. 열쇠 있는 줄이 없으면 쿼리 0, 있으면 1."""
    keys = {row["launch_key"] for row in rows if row["launch_key"] is not None}
    if not keys:
        return {}
    members: dict[tuple[int, str], list[int]] = {}
    for person, key, run_id in (
        _runs(company_id)
        .filter(launch_key__in=sorted(keys))
        .order_by("id")
        .values_list("created_by_user_id", "launch_key", "id")
    ):
        members.setdefault((person, key), []).append(run_id)
    return {run_id: (ids[0], index, len(ids)) for ids in members.values() for index, run_id in enumerate(ids, start=1)}


def _operator_runs(
    company_id: int, rows: Iterable[dict[str, Any]], *, launches: bool = True
) -> tuple[OperatorRun, ...]:
    """거른 실행 행(rows.values(*PAGE_FIELDS) — 쪽이든 전부든)을 읽어 OperatorRun 으로.
    쿼리 = 읽기 1 + 원천 모듈마다 ≤2 + 묶음 ≤1(launches=False 면 0 — 묶음 네 칸 None)."""
    found = list(rows)
    extras = _extras(company_id, found)
    launched = _launches(company_id, found) if launches else {}
    return tuple(
        OperatorRun(
            id=row["id"],
            module=row["module"],
            flow_id=row["flow_id"],
            document_id=row["document_id"],
            document_name=row["document__file_name"],
            status=row["status"],
            purpose=row["purpose"],
            created_by_user_id=row["created_by_user_id"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            review=extras.get(row["id"], (None, None))[0],
            ai_setting=extras.get(row["id"], (None, None))[1],
            launch_key=row["launch_key"],
            launch_first_run_id=launched[row["id"]][0] if row["id"] in launched else None,
            launch_index=launched[row["id"]][1] if row["id"] in launched else None,
            launch_size=launched[row["id"]][2] if row["id"] in launched else None,
            resumed_from_run_id=row["resumed_from_run_id"],
        )
        for row in found
    )


def operator_run_page(
    *,
    actor_kind: Kind,
    company_id: int,
    module: str | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
    limit: int,
    offset: int,
    review: str | None = None,
) -> OperatorRunPage | RunLogForbidden:
    """고른 회사의 실행을 거르고 새 것 먼저 쪽으로. 운영 관리자만(첫 줄). 조건은 전부 AND(None 이면 거르지 않음).
    쿼리 = 셈 1 + 읽기 1 + 원천 모듈마다 ≤2(그 모듈 줄이 쪽에 없으면 0) + 묶음 1(열쇠 있는 줄이 쪽에 없으면 0)."""
    if not is_allowed("user_run_log_list", kind=actor_kind):
        return RunLogForbidden()
    rows = _filtered(company_id, module=module, status=status, date_from=date_from, date_to=date_to, q=q, review=review)
    count = rows.count()
    page = rows.values(*PAGE_FIELDS)[offset : offset + limit]
    return OperatorRunPage(count=count, runs=_operator_runs(company_id, page))


def operator_run_export(
    *,
    actor_kind: Kind,
    company_id: int,
    module: str | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
    review: str | None,
    cap: int,
) -> OperatorRunExport | ExportTooLarge | RunLogForbidden:
    """operator_run_page 와 같은 거르기·차례의 전부. 운영 관리자만(첫 줄). 수가 cap 을 넘으면
    ExportTooLarge(셈 1, 행 읽기 0). 쿼리 = 셈 1 + 읽기 1 + 원천 모듈마다 ≤2.
    셈과 읽기 사이에 실행이 늘면 cap 을 조금 넘겨 읽을 수 있다(무해). 묶음은 세지 않는다(네 칸 None — 엑셀이 안
    쓴다)."""
    if not is_allowed("user_run_log_export", kind=actor_kind):
        return RunLogForbidden()
    rows = _filtered(company_id, module=module, status=status, date_from=date_from, date_to=date_to, q=q, review=review)
    count = rows.count()
    if count > cap:
        return ExportTooLarge(count)
    return OperatorRunExport(runs=_operator_runs(company_id, rows.values(*PAGE_FIELDS), launches=False))


def operator_run_cohort(
    *, actor_kind: Kind, company_id: int, start: datetime, end: datetime
) -> tuple[CohortRun, ...] | RunLogForbidden:
    """고른 회사에서 created_at 이 [start, end) 인 실행 전부(purpose 를 거르지 않는다). 운영 관리자만(첫 줄). 쿼리 1."""
    if not is_allowed("user_run_log_metrics", kind=actor_kind):
        return RunLogForbidden()
    rows = _runs(company_id).filter(created_at__gte=start, created_at__lt=end).order_by("id")
    return tuple(
        CohortRun(
            id=row["id"],
            status=row["status"],
            purpose=row["purpose"],
            created_at=row["created_at"],
            finished_at=row["finished_at"],
        )
        for row in rows.values(*COHORT_FIELDS)
    )


def operator_run_detail(
    *, actor_kind: Kind, company_id: int, run_id: int
) -> OperatorRunDetail | RunLogForbidden | None:
    """고른 회사의 실행 하나. 운영 관리자만(첫 줄). 없거나 남의 회사 실행이면 None(둘을 가르지 않는다).
    쿼리 = 실행 1 + 원천 모듈마다 ≤2 + 묶음 ≤1(열쇠 있을 때) + 단계 1 + 파일 1(없으면 실행 1)."""
    if not is_allowed("user_run_log_get", kind=actor_kind):
        return RunLogForbidden()
    row = _runs(company_id).filter(id=run_id).values(*PAGE_FIELDS, "failed_step", "error_code").first()
    if row is None:
        return None
    (run,) = _operator_runs(company_id, [row])
    return OperatorRunDetail(
        run=run,
        failed_step=row["failed_step"],
        error_code=row["error_code"],
        steps=run_selectors.step_heads(company_id=company_id, run_id=run_id),
        files=run_selectors.run_files(company_id=company_id, run_id=run_id),
    )


def operator_run_file(
    *, actor_kind: Kind, company_id: int, run_id: int, name: str
) -> run_selectors.RunFile | RunFileMissing | RunLogForbidden | None:
    """고른 회사의 실행 하나의 출력 파일(step NULL) 한 행. 운영 관리자만(첫 줄). 모듈을 거르지 않는다(상세와 같다).
    없거나 남의 회사 실행이면 None(둘을 가르지 않는다), 그 이름의 출력 파일이 없으면 RunFileMissing.
    쿼리 = 실행 1 + 파일 1(없으면 실행 1)."""
    if not is_allowed("user_run_log_file_get", kind=actor_kind):
        return RunLogForbidden()
    if not _runs(company_id).filter(id=run_id).exists():
        return None
    found = run_selectors.output_file(company_id=company_id, run_id=run_id, name=name)
    return RunFileMissing() if found is None else found
