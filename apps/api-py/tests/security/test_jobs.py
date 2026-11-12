# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""워커의 일감 잡기·끝내기와 분해 태스크, 다시 넣기 명령을 앱 역할로 잰다(RLS 없음. 진짜 커밋).

재는 것:
  - 다른 회사의 인자로 잡으면 그 일감이 안 보인다(JobNotFound). 틀린 company_id 의 쪽지는 아무것도 하지 않는다
  - 태스크의 트랜잭션이 둘이다: 저장소·파서가 불린 순간 트랜잭션 밖이고, 다른 연결이 `processing` 을 본다
  - 두 연결이 같은 일감의 쪽지를 같이 받아도 파서는 한 번, 끝은 한 번이다(행 잠금)
  - 다시 넣기 명령은 그 회사의 일감만 넣고, 갈고리는 트랜잭션 밖에서 불린다
  - 태스크의 블록(durable)은 다른 트랜잭션 안에서 열리지 않는다

Django 의 연결은 앱 역할(esg_app)이다. `owner` 는 주인 역할의 연결이다(분모를 세고 자료를 심는다).
★ 브로커가 없다. 태스크는 함수를 직접 부른다. 갈고리에는 가짜 앱을 끼운다(이 층은 소켓 막기 밖이다:
  진짜 celery_app() 으로 send_task 를 부르지 않는다).
★ 무효 조건: 경합은 스레드 둘 + 연결 둘로 만든 것이다. 워커 프로세스 둘·큐의 재전달로 잰 것이 아니다.
"""

import contextlib
import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.db import connection, connections, transaction
from django.test import Client

from esgapi.config.env import BrokerSettings, JobSettings
from esgapi.core.calc import jobs as job_rules
from esgapi.core.resources import queue as hooks
from esgapi.core.resources.ports.parser import Parsed, ParseResult
from esgapi.core.resources.ports.storage import GetResult
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.reconcile import tasks
from esgapi.runs.service.selectors import jobs as job_selectors
from esgapi.runs.service.selectors.jobs import NotInTransactionError
from esgapi.runs.service.services.jobs import Claimed, Done, JobNotFound, claim_job, finish_job
from tests.security.conftest import count
from tests.security.test_documents import PDF, Owner, upload_as
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.security

SYNTHETIC = Path(__file__).resolve().parents[2] / "esgapi" / "reconcile" / "tests" / "golden" / "synthetic"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
RACE_ROUNDS = 20  # 장벽 없이 두 연결을 같이 놓아 보는 횟수(분모)
BROKER = BrokerSettings(
    url="sqs://queue:9324",
    region="ap-northeast-2",
    queue_name="esg-jobs",
    queue_url="http://queue:9324/000000000000/esg-jobs",
    secure=False,
)


def good() -> Parsed:
    def load(name: str) -> Any:
        return json.loads((SYNTHETIC / name).read_text(encoding="utf-8"))

    return Parsed(load("document.json"), load("char-places.json"))


@dataclass
class World:
    """가짜 저장소·가짜 파서. 불린 순간의 「트랜잭션 안인가」와, 다른 연결(주인)이 본 일감의 상태를 적어 둔다."""

    owner: Owner
    storage: FakeStorage = field(default_factory=FakeStorage)
    now: datetime = NOW
    parsed: list[bytes] = field(default_factory=list[bytes])
    got: list[str] = field(default_factory=list[str])
    in_atomic: list[tuple[str, bool]] = field(default_factory=list[tuple[str, bool]])
    seen_by_owner: list[tuple[Any, ...] | None] = field(default_factory=list[tuple[Any, ...] | None])
    retries: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    lock: threading.Lock = field(default_factory=threading.Lock)
    watch_job: str | None = None

    def get(self, key: str, *, max_bytes: int) -> GetResult:
        with self.lock:
            self.got.append(key)
            self.in_atomic.append(("storage", connection.in_atomic_block))
            if self.watch_job is not None:
                self.seen_by_owner.append(
                    self.owner.execute(
                        "SELECT status, attempts FROM run_jobs WHERE id = %s", [int(self.watch_job)]
                    ).fetchone()
                )
        return self.storage.get(key, max_bytes=max_bytes)

    def parse(self, pdf: bytes, *, file_name: str) -> ParseResult:
        with self.lock:
            self.parsed.append(pdf)
            self.in_atomic.append(("parser", connection.in_atomic_block))
        return good()


class StorageSpy:
    """services.default_storage 의 자리에 끼운다: get 만 World 를 거치고 나머지는 가짜 저장소 그대로다."""

    def __init__(self, world: World) -> None:
        self.world = world

    def __getattr__(self, name: str) -> Any:
        return getattr(self.world.storage, name)

    def get(self, key: str, *, max_bytes: int) -> GetResult:
        return self.world.get(key, max_bytes=max_bytes)


@pytest.fixture
def world(owner: Owner, monkeypatch: pytest.MonkeyPatch) -> World:
    made = World(owner)
    spy = StorageSpy(made)
    plug_storage(monkeypatch, spy)
    monkeypatch.setattr(tasks, "default_parser", lambda: made)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "clock", lambda: made.now)

    def retry(**kwargs: Any) -> Exception:
        made.retries.append(kwargs)
        return RuntimeError("retry 가 청해졌다")

    monkeypatch.setattr(tasks.parse_job, "retry", retry)
    return made


def uploaded(client: Client, world: World, tenant_id: str = "tenant-a") -> tuple[int, str]:
    """그 테넌트(subdomain)의 세션으로 문서 하나를 올리고 확인한다. (문서 id, 일감 id — 쪽지의 꼴인 십진 글자).
    큐에는 넣지 않는다(브로커 설정이 없다)."""
    login(client, tenant_id=tenant_id, sub=f"user-of-{tenant_id}")
    seen = (len(world.in_atomic), len(world.got))
    document_id = upload_as(client, world.storage, world.owner)
    found = world.owner.execute(
        "SELECT j.id FROM run_jobs j JOIN company c ON c.id = j.company_id "
        "WHERE j.document_id = %s AND c.subdomain = %s",
        [document_id, tenant_id],
    ).fetchone()
    assert found is not None
    # 올림 확인이 원본을 한 번 읽는다(X1b-2a D6 — 쪽 수·글자 층, 블록 밖). 못 박고 비운다(일감 태스크의 셈이 아니다)
    # 테스트 감독 marcspon-39 허락 — sid:MARC-TICK-71 노트 oJ2FcsO8AFWijcAClVNUm
    key = world.owner.execute("SELECT storage_key FROM core_documents WHERE id = %s", [document_id]).fetchone()
    assert key is not None and world.got[seen[1] :] == [key[0]]
    assert world.in_atomic[seen[0] :] == [("storage", False)]
    world.got.clear()
    world.in_atomic.clear()
    return document_id, str(found[0])


def job_facts(owner: Owner, job_id: str) -> tuple[Any, ...] | None:
    """(회사 id, 상태, 시도 수, 오류 code, 임대 없음, 끝 없음)."""
    return owner.execute(
        "SELECT company_id, status, attempts, error_code, lease_expires_at IS NULL, finished_at IS NULL "
        "FROM run_jobs WHERE id = %s",
        [int(job_id)],
    ).fetchone()


def claim(job_id: str, company_id: int) -> Any:
    return claim_job(company_id=company_id, job_id=int(job_id), now=NOW, lease_s=90, max_attempts=3)


# ── 다른 테넌트의 인자로 0행 ──


def test_with_another_tenant_the_claim_sees_no_job(
    client: Client, owner: Owner, companies: tuple[int, int], world: World
) -> None:
    a, b = companies
    _, job_id = uploaded(client, world)
    before = job_facts(owner, job_id)
    assert before == (a, "queued", 0, None, True, True)

    with transaction.atomic(durable=True):  # 워커의 블록과 같은 꼴, B 의 인자
        assert claim(job_id, b) == JobNotFound()
        assert job_selectors.find_job(company_id=b, job_id=int(job_id)) is None
    assert job_facts(owner, job_id) == before
    assert count(owner, "run_jobs") == 1  # 분모: 주인이 센 그 일감 1

    with transaction.atomic(durable=True):
        assert isinstance(claim(job_id, a), Claimed)
    assert job_facts(owner, job_id) == (a, "processing", 1, None, False, True)


def test_the_claim_must_be_called_inside_a_transaction(
    client: Client, owner: Owner, companies: tuple[int, int], world: World
) -> None:
    a, _ = companies
    _, job_id = uploaded(client, world)
    with pytest.raises(NotInTransactionError, match="claim_job"):
        claim(job_id, a)
    with pytest.raises(NotInTransactionError, match="finish_job"):
        finish_job(company_id=a, job_id=int(job_id), attempt=1, now=NOW, outcome=Done({}, "a" * 64))
    with pytest.raises(NotInTransactionError, match="stale_jobs"):
        job_selectors.stale_jobs(company_id=a, now=NOW, queued_older_than_s=1)
    assert job_facts(owner, job_id) == (a, "queued", 0, None, True, True)


def test_a_note_with_the_wrong_tenant_does_nothing(
    client: Client, owner: Owner, companies: tuple[int, int], world: World
) -> None:
    _, job_id = uploaded(client, world)
    before = job_facts(owner, job_id)
    tasks.parse_job(company_id=str(companies[1]), job_id=job_id)
    assert (world.got, world.parsed) == ([], [])  # 저장소 get 0번, 파서 0번
    assert job_facts(owner, job_id) == before
    assert owner.execute("SELECT sha256 FROM core_documents").fetchall() == [(None,)]


# ── 끝까지, 트랜잭션 둘 ──


def test_the_task_runs_to_done_in_two_transactions_with_the_work_outside(
    client: Client, owner: Owner, companies: tuple[int, int], world: World
) -> None:
    a, _ = companies
    document_id, job_id = uploaded(client, world)
    world.watch_job = job_id
    tasks.parse_job(company_id=str(a), job_id=job_id)

    assert job_facts(owner, job_id) == (a, "done", 1, None, True, False)
    summary = owner.execute("SELECT summary FROM run_jobs WHERE id = %s", [int(job_id)]).fetchone()
    assert summary == ({"pages": 3, "tables": 5, "facts": 99, "has_places": True, "warnings": 0},)
    assert owner.execute("SELECT sha256 FROM core_documents WHERE id = %s", [document_id]).fetchone() == ("5" * 64,)
    assert world.parsed == [PDF]
    # 저장소와 파서가 불린 순간: 트랜잭션 밖이다.
    assert world.in_atomic == [("storage", False), ("parser", False)]
    # T1 을 나온 뒤다: 다른 연결(주인)이 그 일감을 `processing`·attempts 1 로 본다(커밋됐다).
    assert world.seen_by_owner == [("processing", 1)]
    assert not connection.in_atomic_block


def test_task_blocks_are_durable(client: Client, owner: Owner, companies: tuple[int, int], world: World) -> None:
    """durable: 잡기의 커밋이 저장소·파서보다 먼저 나가야 다른 워커가 `processing` 을 본다. 바깥 트랜잭션 안에서
    태스크를 부르면 그 약속이 깨지므로 T1 이 RuntimeError 로 거절한다(잡지도, 저장소에 묻지도 않는다).
    """
    _, job_id = uploaded(client, world)
    before = job_facts(owner, job_id)
    with transaction.atomic(), pytest.raises(RuntimeError, match="durable"):
        tasks.run_parse_job(None, company_id=str(companies[0]), job_id=job_id)
    assert (world.got, world.parsed) == ([], [])
    assert job_facts(owner, job_id) == before
    # 같은 블록을 직접 열어도 같다(바깥이 durable 이어도).
    with transaction.atomic(), pytest.raises(RuntimeError, match="durable"), transaction.atomic(durable=True):
        pass
    with (
        transaction.atomic(durable=True),
        pytest.raises(RuntimeError, match="durable"),
        transaction.atomic(durable=True),
    ):
        pass


# ── 두 연결의 경합 ──


def race(world: World, company_id: int, job_id: str) -> list[BaseException]:
    """스레드 둘이 각자의 연결로 같은 쪽지를 같이 돌린다. 스레드에서 난 예외를 돌려준다."""
    errors: list[BaseException] = []
    start = threading.Barrier(2)

    def worker() -> None:
        try:
            start.wait(timeout=10)
            tasks.parse_job(company_id=str(company_id), job_id=job_id)
        except BaseException as err:
            errors.append(err)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not [thread for thread in threads if thread.is_alive()]
    return errors


def test_two_connections_reading_the_same_queued_job_end_it_once(
    client: Client, owner: Owner, companies: tuple[int, int], world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """판정에 장벽을 둔다: 둘 다 행을 읽은 뒤에야 지나간다. 잠금이 있으면 둘째는 못 읽고 기다린다(장벽은 1초 뒤 풀린다).

    잠금이 없으면 둘 다 `queued` 를 읽고 지나가 둘째의 갱신이 0행이 된다(JobUpdateError).
    """
    _, job_id = uploaded(client, world)
    barrier = threading.Barrier(2)
    real = job_rules.claim_decision
    read: list[str] = []

    def held(status: Any, *args: Any) -> Any:
        read.append(status)
        with contextlib.suppress(threading.BrokenBarrierError):
            barrier.wait(timeout=1.0)
        return real(status, *args)

    monkeypatch.setattr(job_rules, "claim_decision", held)
    errors = race(world, companies[0], job_id)
    assert errors == []
    assert sorted(read) == ["processing", "queued"]  # 둘째는 첫째가 커밋한 뒤에야 읽었다
    assert len(world.parsed) == 1
    assert job_facts(owner, job_id) == (companies[0], "done", 1, None, True, False)


def test_two_connections_racing_freely_run_the_parser_once_every_time(
    client: Client, owner: Owner, companies: tuple[int, int], world: World
) -> None:
    a, _ = companies
    done = 0
    for round_number in range(RACE_ROUNDS):
        _, job_id = uploaded(client, world)
        before = len(world.parsed)
        errors = race(world, a, job_id)
        assert errors == [], round_number
        assert len(world.parsed) - before == 1, round_number  # 파서 호출 1
        assert job_facts(owner, job_id) == (a, "done", 1, None, True, False), round_number
        done += 1
    assert (done, count(owner, "run_jobs")) == (RACE_ROUNDS, RACE_ROUNDS)  # 스무 번 돌려 스무 번


# ── 다시 넣기 명령 ──


def test_requeue_sends_only_that_tenants_jobs_and_outside_the_transaction(
    client: Client, owner: Owner, companies: tuple[int, int], world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    _, a_job = uploaded(client, world, "tenant-a")
    _, b_job = uploaded(Client(), world, "tenant-b")
    # 둘 다 워커가 죽은 꼴로 만든다: processing 이고 임대가 지났다.
    owner.execute(
        "UPDATE run_jobs SET status = 'processing', attempts = 1, lease_expires_at = now() - interval '1 second'"
    )
    assert count(owner, "run_jobs") == 2  # 분모: A 의 것 1, B 의 것 1

    sent: list[tuple[dict[str, Any], bool]] = []
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    monkeypatch.setattr(hooks, "enqueue_job", lambda **kwargs: sent.append((kwargs, connection.in_atomic_block)))  # pyright: ignore[reportUnknownLambdaType]
    out = StringIO()
    call_command("requeue_jobs", "--tenant", str(a), stdout=out)

    assert [(call["company_id"], call["job_id"], call["kind"]) for call, _ in sent] == [(a, int(a_job), "parse")]
    lines = out.getvalue().splitlines()
    assert [line for line in lines if line.startswith("넣음 ")] == [f"넣음 {a_job} processing attempts=1"]
    assert not [line for line in lines if line.split(" ")[1:2] == [b_job]]  # B 의 일감은 어느 줄에도 없다
    assert [in_atomic for _, in_atomic in sent] == [False]  # 갈고리가 불린 순간 트랜잭션 밖이다
    assert out.getvalue().splitlines()[-1] == "고른 수 1 · 넣은 수 1 · 실패한 수 0"
    # 행은 건드리지 않았다.
    assert job_facts(owner, a_job) == (a, "processing", 1, None, False, True)


# ── 갈고리의 때 (진짜 갈고리 + 가짜 앱) ──


def test_the_real_hook_sends_after_the_commit(
    client: Client, owner: Owner, companies: tuple[int, int], world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """올림 확인이 건 진짜 갈고리가 가짜 앱의 send_task 를 부른 순간: 트랜잭션 밖이고 주인 연결이 그 일감을 본다.

    (W1a 의 같은 이름 테스트는 갈고리를 통째로 바꿔 끼웠다. 여기서는 갈고리가 진짜이고 앱만 가짜다.)
    """
    seen: list[tuple[Any, ...]] = []

    class FakeApp:
        def send_task(self, name: str, **options: Any) -> None:
            job_id = options["kwargs"]["job_id"]
            visible = owner.execute("SELECT status, company_id FROM run_jobs WHERE id = %s", [int(job_id)]).fetchone()
            seen.append((name, connection.in_atomic_block, visible, options))

    monkeypatch.setattr(hooks, "celery_app", lambda: FakeApp())
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    _, job_id = uploaded(client, world)

    assert len(seen) == 1
    name, in_atomic, visible, options = seen[0]
    assert (name, in_atomic, visible) == ("jobs.parse", False, ("queued", companies[0]))
    # 쪽지의 값은 십진 숫자 글자다(core/resources/queue.py 의 머리말).
    assert options == {
        "kwargs": {"company_id": str(companies[0]), "job_id": job_id},
        "queue": "esg-jobs",
        "retry": False,
    }
