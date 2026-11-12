# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실행 만들기의 Idempotency-Key 경합(밴드 IK1 §2-7 동시 10~12). 업무 층: 진짜 DB, 스레드 둘·연결 둘(transaction=True).

    10 같은 열쇠·같은 본문의 두 요청이 둘 다 「없음」을 읽은 뒤 INSERT → RunCreated 1 + RunReplayed 1·같은 id,
       실행 행 1·쪽지 1·감사 1. 이어 돌기 판(처분 m1): 뒤의 것은 lock_run 에서 기다렸다 ResumeAlready 에 닿아 다시 판정
    11 같은 꼴로 본문이 다름 → RunCreated 1 + KeyReused 1·행 1
    12 다른 제약 위반(짝 CHECK)은 IntegrityError 로 올라온다(삼키지 않는다)

장벽은 selectors.run_by_key 를 감싸 스레드마다 첫 부름에만 건다(threading.local — greenwash 의 test_ai_settings.py 꼴).
둘째 INSERT 는 유일 색인에서 첫째의 커밋을 기다렸다 23505 를 받는다(READ COMMITTED — 다음 SELECT 가 첫째를 본다).
흐름·끼움·저장소는 test_runs.py 의 world(가짜). ★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import IntegrityError, connections

from esgapi.core.models import AuditEventRow
from esgapi.runs.calc.idempotency import body_sha256
from esgapi.runs.models import RunRow
from esgapi.runs.service.actions import runs as actions
from esgapi.runs.service.selectors import runs as selectors
from esgapi.runs.tests.service.apis.test_runs import World, document, failed_run, world

pytestmark = pytest.mark.django_db(transaction=True)

__all__ = ["world"]  # 고정 장치(test_runs.py 의 것)

KEY = "0b0e6c1e-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID
NOW = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
USER = 7


def make(world: World, *, document_id: int, options: dict[str, object], resume_from: int | None = None) -> object:
    """세션의 회사 A·사람 USER 로 만들기 하나(경로가 넘기는 꼴 그대로 — 열쇠와 본문 sha)."""
    sha = body_sha256(module="probe", flow_id=None, document_id=document_id, options=options, resume_from=resume_from)
    return actions.create_run(
        company_id=world.company_a,
        actor_kind="service",
        actor_user_id=USER,
        module="probe",
        flow_id=None,
        document_id=document_id,
        options=options,
        resume_from=resume_from,
        now=NOW,
        idempotency=(KEY, sha),
    )


def both_read_then_insert(monkeypatch: pytest.MonkeyPatch, calls: dict[str, Callable[[], object]]) -> dict[str, object]:
    """두 스레드가 열쇠를 다 찾은 뒤(장벽 — 둘 다 「없음」) 만들기를 이어 간다. 이름 → 결과(또는 예외)."""
    barrier = threading.Barrier(2)
    find = selectors.run_by_key
    first = threading.local()

    def find_then_wait(**kwargs: Any) -> selectors.Keyed | None:
        found = find(**kwargs)
        if not getattr(first, "done", False):
            first.done = True
            barrier.wait(timeout=10)
        return found

    monkeypatch.setattr(selectors, "run_by_key", find_then_wait)
    results: dict[str, object] = {}
    guard = threading.Lock()

    def call(name: str) -> None:
        try:
            result: object = calls[name]()
        except BaseException as err:  # 스레드 밖으로 넘겨 단언한다
            result = err
        finally:
            connections.close_all()
        with guard:
            results[name] = result

    threads = [threading.Thread(target=call, args=(name,)) for name in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()], "장벽·잠금에서 막혔다(교착)"
    return results


def kinds(results: dict[str, object]) -> list[str]:
    return sorted(type(r).__name__ for r in results.values())


def run_lines(company_id: int) -> list[tuple[str, int | None]]:
    return [(a.event, a.target_id) for a in AuditEventRow.for_company(company_id).filter(action="run").order_by("id")]


def test_two_overlapping_posts_with_the_same_key_and_body_make_one_run(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = document(world.company_a)
    options: dict[str, object] = {"pages": "1-3"}
    results = both_read_then_insert(
        monkeypatch,
        {name: (lambda: make(world, document_id=doc, options=options)) for name in ("one", "two")},
    )
    assert kinds(results) == ["RunCreated", "RunReplayed"], results
    ids = {r.run.id for r in results.values() if isinstance(r, actions.RunCreated | actions.RunReplayed)}
    assert len(ids) == 1
    (run_id,) = ids
    assert list(RunRow.for_company(world.company_a).values_list("id", flat=True)) == [run_id]
    assert world.sent == [{"company_id": world.company_a, "run_id": run_id}]  # 쪽지 하나(되돌린 세이브포인트 0)
    assert run_lines(world.company_a) == [("run_created", run_id)]


def test_two_overlapping_resumes_with_the_same_key_return_the_same_child(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """처분 m1: 뒤의 것은 lock_run 에서 앞의 커밋을 기다렸다 ResumeAlready 에 닿고, 거기서 열쇠로 다시 판정한다."""
    doc = document(world.company_a)
    previous = failed_run(world, doc)
    results = both_read_then_insert(
        monkeypatch,
        {name: (lambda: make(world, document_id=doc, options={}, resume_from=previous)) for name in ("one", "two")},
    )
    assert kinds(results) == ["RunCreated", "RunReplayed"], results
    children = list(
        RunRow.for_company(world.company_a).filter(resumed_from_run_id=previous).values_list("id", flat=True)
    )
    assert len(children) == 1
    assert {r.run.id for r in results.values() if isinstance(r, actions.RunCreated | actions.RunReplayed)} == set(
        children
    )
    assert world.sent == [{"company_id": world.company_a, "run_id": children[0]}]
    assert run_lines(world.company_a) == [("run_created", children[0])]


def test_two_overlapping_posts_with_the_same_key_and_another_body_make_one_run_and_one_refusal(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = document(world.company_a)
    results = both_read_then_insert(
        monkeypatch,
        {
            "one": lambda: make(world, document_id=doc, options={"pages": "1-3"}),
            "two": lambda: make(world, document_id=doc, options={"pages": "4-6"}),
        },
    )
    assert kinds(results) == ["KeyReused", "RunCreated"], results
    assert RunRow.for_company(world.company_a).count() == 1
    assert len(world.sent) == 1
    assert len(run_lines(world.company_a)) == 1


def test_another_constraint_breach_is_raised_not_swallowed(world: World) -> None:
    """짝 CHECK(열쇠만 있고 sha 없음)는 유일 제약이 아니다 — IntegrityError 그대로, 행·쪽지·감사 0."""
    doc = document(world.company_a)
    with pytest.raises(IntegrityError, match="run_runs_idempotency_pair_check"):
        actions.create_run(
            company_id=world.company_a,
            actor_kind="service",
            actor_user_id=USER,
            module="probe",
            flow_id=None,
            document_id=doc,
            options={},
            resume_from=None,
            now=NOW,
            idempotency=(KEY, None),  # pyright: ignore[reportArgumentType] — 일부러 어긴 짝
        )
    assert (RunRow.unscoped.count(), world.sent, run_lines(world.company_a)) == (0, [], [])
