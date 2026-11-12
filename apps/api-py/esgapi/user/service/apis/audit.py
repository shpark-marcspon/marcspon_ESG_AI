"""user 의 감사 기록 조회 경로(AU1a — AD-05): 운영 관리자 전용. 기록은 core 의 표(core_audit_events)이고 읽기는 core 의
selector(list_audit_events — 첫 줄이 권한 검사)다. 이 경로는 회사를 고르고, 쪽을 받고, 사람 이름을 지금 값으로 푼다.

차례(/users 와 같다): 인증(Bearer) → permitted(is_initial → 표) → 회사 고르기(users.py 의 chosen_company — 같은 규칙)
→ 읽기 → 이름 풀기(user 의 selectors.names_of — 고른 회사의 고객사 사용자와 운영 관리자만). 고객사 사용자의 403 은
회사 세기·DB 읽기 0 이다. models 를 직접 import 하지 않는다(`.importlinter` 계약 라).

q(AU1b-1 처분 ①②): 사람 이름·아이디(지금 값)와 대상 글자(그때 글자)의 부분 일치, 대소문자 무시. 두 걸음 — 보는 범위에
나온 행위자(core 의 audit_actors_for_search)를 names_of 로 한 번 풀고(고객사는 고른 회사 안에서만) matching_ids 로 q 가
든 id 를 골라 core selector 가 대상 글자와 함께 한 쿼리로 거른다. 그 names 사전을 응답의 이름 풀기에 다시 쓴다(쪽의
행위자 ⊆ 행위자 전체). q 가 없으면 행위자 읽기 0(쿼리 수 그대로).
행위자 목록(GET /audit-logs/actors — AU1b-1 ②): 같은 차례로 core 의 list_audit_actors(보는 범위가 목록·q 와 같다)
→ names_of → 이름 풀린 사람 먼저 아이디·갈래·id 차례, 안 풀린 사람은 맨 뒤 id 차례.
날짜는 DATE_FLOOR~DATE_CEILING 밖이면 422(MARC-ISSUE-192 의 1 — 위 끝은 +1일·UTC 바꿈이 넘치지 않는 값).
"""

from datetime import date
from typing import Annotated

from django.http import HttpRequest
from ninja import Router
from ninja.params.functions import Query

from esgapi.core.auth.bearer import access_token_auth, permitted
from esgapi.core.calc.audit import AuditAction
from esgapi.core.exceptions import ApplicationError
from esgapi.core.service.selectors import audit as audit_selectors
from esgapi.user.service.apis.users import chosen_company, company_ports
from esgapi.user.service.schemas.audit import (
    ACTION_DESCRIPTION,
    AuditActorListOut,
    AuditActorOut,
    AuditEventOut,
    AuditPageOut,
)
from esgapi.user.service.schemas.users import USER_ADMIN_ERROR_RESPONSES
from esgapi.user.service.selectors import user as selectors

router = Router(tags=["사용자 관리"])

DATE_FLOOR = date(2000, 1, 1)
DATE_CEILING = date(2999, 12, 31)


def matching_ids(names: dict[int, tuple[str, str]], q: str) -> frozenset[int]:
    """아이디나 이름에 q 가 든(대소문자 무시 — casefold) 사람의 id."""
    needle = q.casefold()
    return frozenset(
        user_id
        for user_id, (username, name) in names.items()
        if needle in username.casefold() or needle in name.casefold()
    )


def event_out(event: audit_selectors.AuditEvent, names: dict[int, tuple[str, str]]) -> AuditEventOut:
    known = None if event.actor_user_id is None else names.get(event.actor_user_id)
    return AuditEventOut(
        id=event.id,
        at=event.at,
        companyId=event.company_id,
        actorKind=event.actor_kind,  # pyright: ignore[reportArgumentType] — DB 의 CHECK 가 네 값으로 묶는다
        actorUserId=event.actor_user_id,
        actorName=None if known is None else known[1],
        actorUsername=None if known is None else known[0],
        action=event.action,  # pyright: ignore[reportArgumentType] — DB 의 CHECK 가 아홉 값으로 묶는다
        event=event.event,
        result=event.result,  # pyright: ignore[reportArgumentType] — DB 의 CHECK 가 두 값으로 묶는다
        reason=event.reason,
        targetKind=event.target_kind,
        targetId=event.target_id,
        targetLabel=event.target_label,
        changedFields=None if event.changed_fields is None else list(event.changed_fields),
        module=event.module,
        requestId=event.request_id,
    )


@router.get(
    "/audit-logs",
    operation_id="user_audit_list",
    response={200: AuditPageOut, **USER_ADMIN_ERROR_RESPONSES},
    auth=access_token_auth,
)
def audit_list(
    request: HttpRequest,
    # 쿼리는 Annotated 꼴(ruff B008 — Literal·date 기본값에 Query 를 부르지 않는다). 이름이 계약(camelCase).
    companyId: Annotated[int | None, Query(description="대상 고객사의 id. 없으면 하나뿐인 회사")] = None,
    action: Annotated[AuditAction | None, Query(description=ACTION_DESCRIPTION)] = None,
    actorUserId: Annotated[int | None, Query(ge=1, description="그 사람의 줄만")] = None,
    # 날짜 범위(MARC-ISSUE-192 의 1): pydantic 이 date 끼리 잰다(ninja 의 Query 는 ge·le 를 float 로 적었다)
    dateFrom: Annotated[
        date | None,
        Query(
            ge=DATE_FLOOR,  # pyright: ignore[reportArgumentType]
            le=DATE_CEILING,  # pyright: ignore[reportArgumentType]
            description="KST 그날 00:00 부터(포함). 2000-01-01~2999-12-31 밖은 422",
        ),
    ] = None,
    dateTo: Annotated[
        date | None,
        Query(
            ge=DATE_FLOOR,  # pyright: ignore[reportArgumentType]
            le=DATE_CEILING,  # pyright: ignore[reportArgumentType]
            description="KST 그날 끝까지(포함). 2000-01-01~2999-12-31 밖은 422",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=150,
            description="사람 이름·아이디(지금 값)와 대상 글자(그때 값)의 부분 일치(대소문자 무시)",
        ),
    ] = None,
) -> AuditPageOut:
    """운영 관리자만. 고른 회사의 기록과 회사가 없는 기록(운영 관리자의 로그인·명령)을 새 것 먼저. 기록은 고치거나
    지울 수 없다. 사람 이름은 지금의 이름이다."""
    principal = permitted(request, "user_audit_list")
    company_id = chosen_company(companyId, company_ports())
    searched: dict[int, tuple[str, str]] | None = None
    q_actor_ids: frozenset[int] = frozenset()
    if q is not None:
        actors = audit_selectors.audit_actors_for_search(actor_kind=principal.kind, company_id=company_id)
        if isinstance(actors, audit_selectors.AuditForbidden):
            raise ApplicationError("forbidden", "forbidden", "운영 관리자만 감사 기록을 본다")
        searched = selectors.names_of(
            company_id,
            {actor.actor_user_id for actor in actors if actor.actor_kind == "service"},
            {actor.actor_user_id for actor in actors if actor.actor_kind == "admin"},
        )
        q_actor_ids = matching_ids(searched, q)
    page = audit_selectors.list_audit_events(
        actor_kind=principal.kind,
        company_id=company_id,
        action=action,
        actor_user_id=actorUserId,
        date_from=dateFrom,
        date_to=dateTo,
        limit=limit,
        offset=offset,
        q=q,
        q_actor_ids=q_actor_ids,
    )
    if isinstance(page, audit_selectors.AuditForbidden):
        raise ApplicationError("forbidden", "forbidden", "운영 관리자만 감사 기록을 본다")
    names = searched
    if names is None:
        names = selectors.names_of(
            company_id,
            {row.actor_user_id for row in page.rows if row.actor_kind == "service" and row.actor_user_id is not None},
            {row.actor_user_id for row in page.rows if row.actor_kind == "admin" and row.actor_user_id is not None},
        )
    return AuditPageOut(
        count=page.count,
        isNext=offset + len(page.rows) < page.count,
        results=[event_out(row, names) for row in page.rows],
    )


def actor_order(actor: AuditActorOut) -> tuple[bool, str, str, int]:
    """이름 풀린 사람 먼저(아이디 → 갈래 → id — 운영 관리자와 고객사가 같은 아이디일 수 있다), 안 풀린 사람은
    맨 뒤 id 차례."""
    unresolved = actor.actorUsername is None
    return (unresolved, actor.actorUsername or "", "" if unresolved else actor.actorKind, actor.actorUserId)


@router.get(
    "/audit-logs/actors",
    operation_id="user_audit_actors",
    response={200: AuditActorListOut, **USER_ADMIN_ERROR_RESPONSES},
    auth=access_token_auth,
)
def audit_actors(
    request: HttpRequest,
    companyId: Annotated[int | None, Query(description="대상 고객사의 id. 없으면 하나뿐인 회사")] = None,
) -> AuditActorListOut:
    """운영 관리자만. 고른 회사의 감사 기록과 회사가 없는 기록에 나온 사람(관리 명령·모르는 아이디는 사람이 아니라
    빠진다). 이름은 지금의 값. 로그인 실패 줄의 행위자는 시도된 계정이다."""
    principal = permitted(request, "user_audit_actors")
    company_id = chosen_company(companyId, company_ports())
    actors = audit_selectors.list_audit_actors(actor_kind=principal.kind, company_id=company_id)
    if isinstance(actors, audit_selectors.AuditForbidden):
        raise ApplicationError("forbidden", "forbidden", "운영 관리자만 감사 기록을 본다")
    names = selectors.names_of(
        company_id,
        {actor.actor_user_id for actor in actors if actor.actor_kind == "service"},
        {actor.actor_user_id for actor in actors if actor.actor_kind == "admin"},
    )
    results: list[AuditActorOut] = []
    for actor in actors:
        known = names.get(actor.actor_user_id)
        results.append(
            AuditActorOut(
                actorKind=actor.actor_kind,  # pyright: ignore[reportArgumentType] — _actors 는 id 있는 두 갈래만 낸다
                actorUserId=actor.actor_user_id,
                actorName=None if known is None else known[1],
                actorUsername=None if known is None else known[0],
            )
        )
    return AuditActorListOut(results=sorted(results, key=actor_order))
