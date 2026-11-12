"""읽기. 감사 기록의 쪽(운영 관리자의 AD-05 — 경로는 user 의 service/apis/audit.py). 쓰지 않는다.

첫 문장이 권한 검사다(core/permissions.py 의 표 — user_audit_list 는 운영 관리자만). 막히면 아무것도 읽지 않는다.
보는 범위(처분 ⑪ (가)): 고른 회사의 줄(AuditEventRow.for_company(company_id)) ∪ 회사 칸이 NULL 인 줄(이름 붙은
입구 AuditEventRow.operator_rows() — 운영 관리자의 로그인·명령, 회사를 못 찾은 모르는 아이디의 로그인).
남의 회사 줄은 0 이다.
무효 조건: 회사가 둘이 되면 운영 관리자는 회사마다 따로 본다(모든 회사의 줄을 한 번에 여는 길은 없다 — 2차).
날짜는 KST 의 하루다: date_from 그날 00:00(+09:00)부터, date_to 그날 끝(다음 날 00:00 앞)까지. 둘 다 포함.
새 것 먼저(at 내림, 같은 때면 id 내림). count 는 거른 뒤의 수다.
보는 범위의 정의는 _visible 하나다 — 목록(list_audit_events)·행위자(_actors)·q 가 같이 쓴다(AU1b-1 처분 ④).

q(AU1b-1 처분 ①⑦ — 두 걸음): core 는 user 표를 모르므로(.importlinter 계약 「가」) 사람 이름·아이디로 DB 조인을 하지
않는다. 경로가 먼저 보는 범위에 나온 행위자(audit_actors_for_search)를 user 의 names_of 로 풀어 q 가 든 id 를 고르고,
여기서는 그 id 집합과 대상 글자를 한 쿼리로 거른다: target_label 부분 일치(icontains — % _ 는 글자) 또는 actor_user_id
가 그 집합 안. 집합이 비면 대상 글자만. count·쪽은 거른 뒤의 값이다.
무효 조건: 회사의 감사 줄이 수십만이 되면 행위자 distinct 가 _visible 전체를 훑는다(행위자 칸 색인 없음 —
core/models.py) — 그때 user 쪽 검색 입구나 색인(2차). 대소문자 무시는 파이썬 casefold(이름)와 DB icontains(대상 글자)가
유니코드 끝에서 다를 수 있다(한글은 대소문자 없음 — 받아들임).
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from django.db.models import Q, QuerySet

from esgapi.core.auth.principal import Kind
from esgapi.core.models import AuditEventRow
from esgapi.core.permissions import is_allowed

KST = timezone(timedelta(hours=9))


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: int
    at: datetime
    company_id: int | None
    actor_kind: str
    actor_user_id: int | None
    action: str
    event: str
    result: str
    reason: str | None
    target_kind: str | None
    target_id: int | None
    target_label: str | None
    changed_fields: tuple[str, ...] | None
    request_id: str | None
    module: str | None  # 그 줄이 어느 모듈의 일인가(detail 의 module — AD4S). 없으면 None


@dataclass(frozen=True, slots=True)
class AuditPage:
    count: int
    rows: tuple[AuditEvent, ...]


@dataclass(frozen=True, slots=True)
class AuditForbidden:
    """운영 관리자가 아니다(아무것도 읽지 않았다)."""


@dataclass(frozen=True, slots=True)
class AuditActor:
    """보는 범위의 줄에 나온 한 사람(갈래 admin·service 와 id). 이름은 경로가 user 의 names_of 로 푼다."""

    actor_kind: str
    actor_user_id: int


def kst_day_start(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=KST)


def event_of(row: AuditEventRow) -> AuditEvent:
    changed = row.detail.get("changed_fields")
    module = row.detail.get("module")
    return AuditEvent(
        id=row.id,
        at=row.at,
        company_id=row.company_id,
        actor_kind=row.actor_kind,
        actor_user_id=row.actor_user_id,
        action=row.action,
        event=row.event,
        result=row.result,
        reason=row.reason,
        target_kind=row.target_kind,
        target_id=row.target_id,
        target_label=row.target_label,
        changed_fields=None if changed is None else tuple(changed),
        request_id=row.request_id,
        module=module if isinstance(module, str) else None,
    )


def _visible(company_id: int) -> QuerySet[AuditEventRow]:
    """보는 범위(처분 ⑪ (가)): 고른 회사의 줄 ∪ 회사 칸이 NULL 인 줄. 권한 검사를 지난 뒤에만 부른다.
    인자는 이름 company_id 하나다(core/tests/test_selector_scope.py 의 GATES 밖이라 기계 검사가 없다 —
    AU1b-1 개정 1 m4)."""
    return AuditEventRow.for_company(company_id) | AuditEventRow.operator_rows()


def list_audit_events(
    *,
    actor_kind: Kind,
    company_id: int,
    action: str | None,
    actor_user_id: int | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
    q: str | None = None,
    q_actor_ids: frozenset[int] = frozenset(),
) -> AuditPage | AuditForbidden:
    """고른 회사의 줄과 회사 없는 줄을 거르고 새 것 먼저 쪽으로. 운영 관리자만(첫 줄).
    q 가 있으면 대상 글자 부분 일치 또는 행위자 id 가 q_actor_ids 안(경로가 이름·아이디로 고른 집합).
    q 가 없으면 둘 다 무시."""
    if not is_allowed("user_audit_list", kind=actor_kind):
        return AuditForbidden()
    rows = _visible(company_id)
    if q is not None:
        matched = Q(target_label__icontains=q)
        if q_actor_ids:
            matched |= Q(actor_user_id__in=q_actor_ids)
        rows = rows.filter(matched)
    if action is not None:
        rows = rows.filter(action=action)
    if actor_user_id is not None:
        rows = rows.filter(actor_user_id=actor_user_id)
    if date_from is not None:
        rows = rows.filter(at__gte=kst_day_start(date_from))
    if date_to is not None:
        rows = rows.filter(at__lt=kst_day_start(date_to + timedelta(days=1)))
    rows = rows.order_by("-at", "-id")
    count = rows.count()
    return AuditPage(count=count, rows=tuple(event_of(row) for row in rows[offset : offset + limit]))


def _actors(company_id: int) -> tuple[AuditActor, ...]:
    """보는 범위의 줄에 나온 서로 다른 사람(command·anonymous 는 id 가 없어 빠진다). 한 쿼리. 권한 검사는 부르는 쪽.
    order_by() 를 비워 distinct 가 정렬 칸에 끌리지 않게 한다. 차례는 경로가 이름으로 정한다."""
    found = (
        _visible(company_id)
        .filter(actor_user_id__isnull=False)
        .order_by()
        .values_list("actor_kind", "actor_user_id")
        .distinct()
    )
    return tuple(AuditActor(actor_kind=kind, actor_user_id=user_id) for kind, user_id in found)


def audit_actors_for_search(*, actor_kind: Kind, company_id: int) -> tuple[AuditActor, ...] | AuditForbidden:
    """GET /audit-logs 의 q 길이 이름을 풀 사람들. 그 동작(user_audit_list)의 칸을 읽는다 — 운영 관리자만(첫 줄)."""
    if not is_allowed("user_audit_list", kind=actor_kind):
        return AuditForbidden()
    return _actors(company_id)


def list_audit_actors(*, actor_kind: Kind, company_id: int) -> tuple[AuditActor, ...] | AuditForbidden:
    """GET /audit-logs/actors 의 사람들(AU1b-1 ②). 그 동작(user_audit_actors)의 칸을 읽는다 — 운영 관리자만(첫 줄)."""
    if not is_allowed("user_audit_actors", kind=actor_kind):
        return AuditForbidden()
    return _actors(company_id)
