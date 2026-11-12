"""올린 PDF 하나가 큐 → 워커 → 파서를 지나 일감이 끝나는지를 떠 있는 컨테이너에서 잰다.

    api-py · worker-py · queue(SQS 흉내, ElasticMQ) · storage(Versity) · parser · postgres

    교환 → POST /documents → 저장소에 PUT → POST …/confirm → (큐) → 워커 → 파서 → GET … 가 done

재는 것 일곱:
  1. 한 줄기: 일감이 `done`·attempts 1 로 끝나고 요약의 키가 굳힌 집합이며 문서의 sha256 이 올린 바이트의 것이다
  2. PDF 가 아닌 바이트: `failed`, errorCode 는 파서가 준 code, 다시 해 보지 않는다
  3. 올림 확인 뒤 같은 주소에 다른 바이트를 다시 올리면: `failed`·object_changed(파서에 보내지 않는다)
  4. 워커를 SIGKILL 로 죽인 뒤: 임대가 끝나면 다시 넣기 명령으로 다른 워커가 이어받아 `done`·attempts 2
  5. 브로커(queue)에 못 닿을 때: 올림 확인은 200 이고 일감은 `queued`. 큐가 돌아온 뒤 올림 확인을 다시 부르면 `done`
  6. 파서가 멈춰 있으면: 연결 실패가 「다시 해 본다」로 갈리고, 시도 상한에서 `failed`·attempts_exhausted·사유
     (TS 통합 tests/integration/flow.test.ts 의 「파서가 죽어 있으면 재시도 뒤 failed」를 옮김. 밴드 T1c)
  7. 워커에 SIGTERM: 하던 일을 마치고(일감 `done`·attempts 1) 종료 코드 0 으로 내려간다
     (같은 파일의 「worker 가 SIGTERM 에 하던 작업을 마친다」를 옮김. 밴드 T1c)

원본은 저장소에 있는 지은 PDF(data/ruled-table.pdf. 4×4 표 하나, 숫자는 지어낸 것)다. 실제 문서가 아니다.

★ 컨테이너를 멈추고 죽이는 것은 **이 저장소의 compose 프로젝트의 서비스**뿐이다(conftest 의 compose()).
  마무리는 전부 `finally` 에 있다(실패해도 parser 를 풀고 queue·worker-py 를 되돌린다).
★ 두 값 모두에서 초록이어야 한다: 기본 env 값(손 띄우기·지난 밴드의 section4)과, 전량 게이트가 내보내는 짧은 값
  (긴 폴링 CELERY_WAIT_TIME_SECONDS · 다시 해 보기 JOB_RETRY_DELAY_SECONDS. scripts/verify.sh). 쉼은 고정 글자가 아니라
  워커가 받은 그 값에서 끌어낸다(conftest 의 worker_value). 처음에 한 번 「시험이 쓰는 긴 폴링 = 워커가 받은 값」을
  단언한다.
  4번만 짧은 임대·시간 제한이 필요해
  **일감을 만들기 전에** 스스로 워커를 다시 띄운다: 행에 적힌 임대는 뒤에 띄운 워커가 줄이지 못한다.
★ 무효 조건:
  - 큐는 SQS 흉내(ElasticMQ 1.7.1)다. 실제 SQS 에서 같은지는 재지 않았다.
  - 4번은 **큐의 재전달에 기대지 않는다**(다시 넣기 명령으로 이어받는다). 재전달(360초 뒤)은 테스트가 끝난 뒤에 와서
    AlreadyFinished·JobNotFound 로 끝난다. 재전달 그 자체는 이 파일이 재지 않는다.
  - 하드 시간 제한이 태스크를 죽이는 모습은 재지 않는다.
  - 5번의 「걸린 시간」은 compose 망 안에서 멈춘 컨테이너의 이름을 푸는 시간을 포함한다(이 기계에서 잰 값이다).
"""

import contextlib
import hashlib
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest

from esgapi.reconcile.calc.job_summary import SUMMARY_KEYS
from tests_integration.conftest import (
    API,
    MAX_ATTEMPTS,
    RETRY_DELAY_S,
    WAIT_TIME_S,
    compose,
    container_state,
    wait_for,
)
from tests_integration.test_flow import exchange

Owner = psycopg.Connection[tuple[Any, ...]]
PDF = Path(__file__).resolve().parent / "data" / "ruled-table.pdf"
# 4번이 워커에 주는 짧은 값(초). 순서: 소프트 8 < 하드 10 < 임대 12 < visibility 360(큐의 값, 기본).
# (밴드 T1c 가 12 < 15 < 20 에서 낮춤 — 연속 5회로 잼. band-reports/T1c-gate-trim.md)
# ★ 소프트 제한은 「processing 을 본 뒤 SIGKILL 이 닿기까지」보다 넉넉히 길어야 한다: 파서가 멈춰 있어 소프트 제한이
#   먼저 오면 태스크가 「다시 해 본다」로 넘어가 attempts 가 늘고 attempts_exhausted 로 끝난다.
SHORT = {
    "JOB_LEASE_SECONDS": "12",
    "CELERY_TASK_SOFT_TIME_LIMIT_SECONDS": "8",
    "CELERY_TASK_TIME_LIMIT_SECONDS": "10",
}


# 워커를 멈추거나 갈아 끼운 뒤, 쪽지를 넣기 전에 기다리는 시간(초). 워커의 긴 폴링(WaitTimeSeconds, 기본 10초)보다 길다.
# 까닭: 멈춘 워커가 걸어 둔 긴 폴링 요청이 큐 쪽에 최대 그 값만큼 남는다. 그 사이에 넣은 쪽지는 그 죽은 요청에 건네져
# visibility(360초) 동안 아무도 못 받는다(잃지는 않는다. 그 뒤에 다시 온다).
# ★ 검증자가 잼(band-reports/W1b-verify.md 의 3번. ElasticMQ 1.7.1): 워커가 죽은 직후 넣은 쪽지가 곧바로 NotVisible 1,
#   121초 뒤 새 워커가 받음. 새 워커의 준비와는 무관하다(찬 시작은 1초 안에 받는다). 이 쉼을 빼면 SIGKILL 테스트가
#   세 번에 두 번 빨갛다. 실제 SQS 는 재지 않았다.
# ★ 워커가 받은 긴 폴링에서 끌어낸다(기본 10 이면 11초, 전량 게이트의 짧은 값 2 면 3초). 다른 값으로 띄운 워커에 돌리면
#   쉼이 어긋난다 — 그래서 처음에 the_worker_has_the_long_poll_the_tests_assume 가 워커의 값을 견준다.
POLL_SETTLE_S = WAIT_TIME_S + 1
# 「다시 해 보지 않는다」를 보는 쉼(초): 다시 해 보기까지(JOB_RETRY_DELAY_SECONDS)보다 길게.
# ★ 상태 확인으로 못 바꾼다: 「아무 일도 일어나지 않음」에는 끝을 알리는 상태가 없다. 잘못 걸린 재시도가 보일 만큼
#   (지연 + 쪽지가 닿는 시간) 기다리는 수밖에 없다.
NOT_RETRIED_S = RETRY_DELAY_S + 2


@pytest.fixture(scope="session", autouse=True)
def the_worker_has_the_long_poll_the_tests_assume() -> None:
    """시험이 쉼을 끌어낸 긴 폴링 = 떠 있는 worker-py 가 받은 값(다른 셸에서 다른 값으로 띄운 워커를 잡는다)."""
    out = compose(
        "exec",
        "-T",
        "worker-py",
        "python",
        "-c",
        "from esgapi.config.celery import app; print(app.conf.broker_transport_options['wait_time_seconds'])",
    )
    got = int(out.strip().splitlines()[-1])
    assert got == WAIT_TIME_S, (
        f"worker-py 의 긴 폴링은 {got}초인데 시험은 {WAIT_TIME_S}초로 쉼을 잰다."
        " 같은 환경(CELERY_WAIT_TIME_SECONDS)으로 띄운 뒤 돌린다"
    )


# 따뜻한 종료(SIGTERM)를 받은 워커가 표준 출력에 찍는 줄. celery 5.6.3 의 apps/worker.py 의 _shutdown_handler 가
# safe_say(f'worker: {how} shutdown (MainProcess)') 로 찍는다(로그 갈고리 밖이라 JSON 이 아니다).
WARM_SHUTDOWN = "worker: Warm shutdown (MainProcess)"


def worker_logs(tail: int = 60) -> str:
    return compose("logs", "--no-color", "--tail", str(tail), "worker-py")


def wait_worker_ready() -> None:
    """지금의 worker-py 컨테이너가 큐에 붙어 「ready」 를 찍기를 기다린다."""
    wait_for("worker-py 가 ready 가 되기", lambda: " ready." in worker_logs(200) or None, timeout=60)


def recreate_worker() -> None:
    """worker-py 를 지금의 환경으로 새로 만들고 ready 를 기다린 뒤, 앞 워커의 긴 폴링이 끝나기를 기다린다.

    워커를 멈추거나 죽이거나 내려가게 한 시험은 끝에서 이것을 부른다: 다음 시험의 쪽지가 죽은 긴 폴링에 넘어가지 않게.
    """
    compose("up", "-d", "--no-deps", "--force-recreate", "worker-py")
    wait_worker_ready()
    time.sleep(POLL_SETTLE_S)


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=API, timeout=30.0) as client:
        yield client


@pytest.fixture
def tenant(owner: Owner, two_tenants: tuple[str, str]) -> Iterator[str]:
    """이 실행만의 테넌트 하나. 끝에서 이 실행이 만든 문서·일감 행을 주인 연결로 지운다."""
    yield two_tenants[0]
    companies = [i for (i,) in owner.execute("SELECT id FROM company WHERE subdomain = ANY(%s)", [list(two_tenants)])]
    owner.execute("DELETE FROM run_jobs WHERE company_id = ANY(%s)", [companies])
    owner.execute("DELETE FROM core_documents WHERE company_id = ANY(%s)", [companies])


def create_and_put(http: httpx.Client, headers: dict[str, str], data: bytes) -> tuple[str, str]:
    """문서를 만들고 받은 주소로 저장소에 직접 올린다. (문서 id, 올리기 주소)."""
    created = http.post("/documents", headers=headers, json={"fileName": "ruled-table.pdf", "sizeBytes": len(data)})
    assert created.status_code == 201, created.text
    document_id: str = created.json()["document"]["id"]
    url: str = created.json()["upload"]["url"]
    put = httpx.put(url, content=data, timeout=20.0)
    assert put.status_code == 200, put.text
    return document_id, url


def confirm(http: httpx.Client, headers: dict[str, str], document_id: str) -> dict[str, Any]:
    response = http.post(f"/documents/{document_id}/confirm", headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def job_of(http: httpx.Client, headers: dict[str, str], document_id: str) -> dict[str, Any]:
    response = http.get(f"/documents/{document_id}", headers=headers)
    assert response.status_code == 200, response.text
    jobs: list[dict[str, Any]] = response.json()["jobs"]
    assert len(jobs) == 1
    return jobs[0]


def wait_finished(
    http: httpx.Client, headers: dict[str, str], document_id: str, timeout: float = 60.0
) -> dict[str, Any]:
    """상태 보기를 0.5초마다 되물어 일감이 끝나기(done·failed)를 기다린다."""
    deadline = time.monotonic() + timeout
    job: dict[str, Any] = {}
    while time.monotonic() < deadline:
        job = job_of(http, headers, document_id)
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.5)
    logs = compose("logs", "--no-color", "--tail", "40", "worker-py")
    raise AssertionError(f"일감이 {timeout}초 안에 끝나지 않았다: {job}\n── worker-py 의 기록 ──\n{logs}")


def job_row(owner: Owner, document_id: str) -> tuple[Any, ...]:
    rows = owner.execute(
        "SELECT status, attempts, error_code, lease_expires_at, finished_at FROM run_jobs WHERE document_id = %s",
        [document_id],
    ).fetchall()
    assert len(rows) == 1  # 주인이 센 일감 1행
    return rows[0]


def test_an_uploaded_pdf_goes_through_the_queue_the_worker_and_the_parser_to_done(
    http: httpx.Client, owner: Owner, tenant: str
) -> None:
    pdf = PDF.read_bytes()
    headers = exchange(http, tenant=tenant, sub="it-worker-alice")
    document_id, _ = create_and_put(http, headers, pdf)
    started = time.monotonic()
    confirmed = confirm(http, headers, document_id)
    assert [job["kind"] for job in confirmed["jobs"]] == ["parse"]

    job = wait_finished(http, headers, document_id)
    elapsed = time.monotonic() - started
    assert (job["status"], job["attempts"], job["errorCode"], job["errorMessage"]) == ("done", 1, None, None)
    assert job["finishedAt"] is not None
    # 요약: 키의 집합이 굳힌 상수이고, 값은 지은 PDF 의 것이다(4×4 표 하나가 든 한 쪽).
    # (jsonb 는 키의 차례를 지키지 않는다: 집합으로 견준다)
    assert set(job["summary"]) == set(SUMMARY_KEYS) == {"pages", "tables", "facts", "has_places", "warnings"}
    assert job["summary"] == {"pages": 1, "tables": 1, "facts": 5, "has_places": True, "warnings": 0}
    # 주인 연결로: 문서의 sha256 = 올린 바이트의 sha256, 일감 1행이고 임대는 풀렸다.
    sha = owner.execute("SELECT sha256 FROM core_documents WHERE id = %s", [document_id]).fetchone()
    assert sha == (hashlib.sha256(pdf).hexdigest(),)
    status, attempts, error_code, lease, finished_at = job_row(owner, document_id)
    assert (status, attempts, error_code, lease) == ("done", 1, None, None) and finished_at is not None
    assert elapsed < 60
    print(f"\n  (한 줄기: 올림 확인에서 done 까지 {elapsed:.1f}초)")


def test_bytes_that_are_not_a_pdf_fail_once_with_the_parsers_code(
    http: httpx.Client, owner: Owner, tenant: str
) -> None:
    headers = exchange(http, tenant=tenant, sub="it-worker-alice")
    document_id, _ = create_and_put(http, headers, b"this is not a pdf, just synthetic text " * 8)
    confirm(http, headers, document_id)
    job = wait_finished(http, headers, document_id)
    assert (job["status"], job["errorCode"], job["attempts"]) == ("failed", "not_a_pdf", 1)
    assert job["summary"] == {} and job["errorMessage"]
    # 다시 해 보지 않는다: 다시 해 보기까지(워커의 값, 기본 5초)보다 길게 기다려도 그대로다.
    time.sleep(NOT_RETRIED_S)
    assert job_of(http, headers, document_id) == job
    assert job_row(owner, document_id)[:3] == ("failed", 1, "not_a_pdf")
    assert owner.execute("SELECT sha256 FROM core_documents WHERE id = %s", [document_id]).fetchone() == (None,)


def test_an_object_swapped_after_the_confirm_is_not_parsed(http: httpx.Client, owner: Owner, tenant: str) -> None:
    """올림 확인 뒤, 주소의 수명 안에 같은 크기의 다른 바이트를 같은 주소로 다시 올린다. 워커는 ETag 가 달라 멈춘다."""
    pdf = PDF.read_bytes()
    other = pdf[:-1] + bytes([pdf[-1] ^ 0x01])  # 같은 크기, 한 바이트가 다르다(크기의 서명 조건을 지난다)
    headers = exchange(http, tenant=tenant, sub="it-worker-alice")
    compose("stop", "worker-py")  # 쪽지가 바꿔치기 **뒤에** 처리되게
    time.sleep(POLL_SETTLE_S)
    try:
        document_id, url = create_and_put(http, headers, pdf)
        confirmed = confirm(http, headers, document_id)
        again = httpx.put(url, content=other, timeout=20.0)
        assert again.status_code == 200, again.text
        assert job_row(owner, document_id)[:2] == ("queued", 0)
    finally:
        compose("start", "worker-py")
    job = wait_finished(http, headers, document_id)
    assert (job["status"], job["errorCode"], job["attempts"]) == ("failed", "object_changed", 1)
    # 표의 ETag 는 올림 확인 때의 것 그대로이고, 분해하지 않았으니 sha256 은 비어 있다.
    row = owner.execute("SELECT etag, sha256 FROM core_documents WHERE id = %s", [document_id]).fetchone()
    assert row == (confirmed["document"]["etag"], None)


@pytest.fixture
def short_worker() -> Iterator[None]:
    """워커를 짧은 임대·시간 제한으로 다시 띄운다. 끝에서(실패해도) parser 를 풀고 queue 와 기본값의 워커를 되돌린다."""
    before = {key: os.environ.get(key) for key in SHORT}
    os.environ.update(SHORT)
    try:
        recreate_worker()
        yield
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for restore in (("unpause", "parser"), ("start", "queue")):
            # 이미 풀려 있으면 unpause 가 실패한다. 그래도 나머지를 되돌린다.
            with contextlib.suppress(Exception):
                compose(*restore)
        recreate_worker()


def test_a_killed_workers_job_is_taken_over_after_the_lease_and_ends_once(
    http: httpx.Client, owner: Owner, tenant: str, short_worker: None
) -> None:
    pdf = PDF.read_bytes()
    headers = exchange(http, tenant=tenant, sub="it-worker-alice")
    compose("pause", "parser")  # 워커가 파서의 답을 기다리며 멈춰 있게
    paused = True
    try:
        document_id, _ = create_and_put(http, headers, pdf)
        confirm(http, headers, document_id)
        # 워커가 잡았다(T1 이 커밋됐다): 주인 연결이 processing·attempts 1 을 본다.
        try:
            wait_for(
                "일감이 processing·attempts 1 이 되기",
                lambda: job_row(owner, document_id)[:2] == ("processing", 1) or None,
                timeout=30,
            )
        except AssertionError as err:
            raise AssertionError(
                f"{err}\n행: {job_row(owner, document_id)}\n── worker-py ──\n{worker_logs()}"
            ) from None
        compose("kill", "-s", "SIGKILL", "worker-py")
        compose("unpause", "parser")
        paused = False
        assert job_row(owner, document_id)[:2] == ("processing", 1)  # 죽은 워커가 쥔 채다
        # 같은 짧은 값으로 워커를 다시 띄운다(환경은 short_worker 가 준 그대로다).
        # `start` 가 아니라 `up --no-deps` 다: SIGKILL 로 죽은 컨테이너에 `compose start` 는 0 이 아닌 코드로 끝났다.
        compose("up", "-d", "--no-deps", "worker-py")
        wait_worker_ready()

        # 행의 임대가 지나기를 주인 연결로 기다린다(짧은 값 12초).
        def lease_passed() -> bool | None:
            found = owner.execute(
                "SELECT lease_expires_at < now() FROM run_jobs WHERE document_id = %s", [document_id]
            ).fetchone()
            return True if found is not None and found[0] else None

        wait_for("임대가 지나기", lease_passed, timeout=40)
        assert job_row(owner, document_id)[:2] == ("processing", 1)  # 스스로 돌아오지 않았다(재전달은 360초 뒤다)

        [(company,)] = owner.execute("SELECT id::text FROM company WHERE subdomain = %s", [tenant]).fetchall()
        out = compose("exec", "-T", "api-py", "python", "manage.py", "requeue_jobs", "--tenant", company)
        assert out.strip().splitlines()[-1] == "고른 수 1 · 넣은 수 1 · 실패한 수 0"
        job = wait_finished(http, headers, document_id)
        assert (job["status"], job["attempts"], job["errorCode"]) == ("done", 2, None)
        status, attempts, _, lease, finished_at = job_row(owner, document_id)  # 일감 1행(끝이 한 번 적혔다)
        assert (status, attempts, lease) == ("done", 2, None) and finished_at is not None
        sha = owner.execute("SELECT sha256 FROM core_documents WHERE id = %s", [document_id]).fetchone()
        assert sha == (hashlib.sha256(pdf).hexdigest(),)
    finally:
        if paused:
            compose("unpause", "parser")


def queue_health() -> str:
    import subprocess

    container_id = compose("ps", "-a", "-q", "queue").strip()
    return subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_id],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_when_the_broker_is_down_the_confirm_still_answers_and_a_second_confirm_recovers(
    http: httpx.Client, owner: Owner, tenant: str
) -> None:
    pdf = PDF.read_bytes()
    headers = exchange(http, tenant=tenant, sub="it-worker-alice")
    document_id, _ = create_and_put(http, headers, pdf)
    compose("stop", "queue")
    try:
        started = time.monotonic()
        confirmed = confirm(http, headers, document_id)  # 200 (confirm 이 단언한다)
        elapsed = time.monotonic() - started
        assert [(job["status"], job["attempts"]) for job in confirmed["jobs"]] == [("queued", 0)]
        assert elapsed < 20, elapsed
        print(f"\n  (브로커가 멈춘 채의 올림 확인: {elapsed:.1f}초)")
        time.sleep(2)
        assert job_row(owner, document_id)[:2] == ("queued", 0)  # 쪽지가 없다: 머문다
    finally:
        compose("start", "queue")
    wait_for("queue 가 healthy 가 되기", lambda: queue_health() == "healthy" or None, timeout=60)

    # 다시 넣는 길: 올림 확인을 다시 부른다(끝나지 않은 일감마다 커밋 뒤에 다시 넣는다).
    again = confirm(http, headers, document_id)
    assert [job["id"] for job in again["jobs"]] == [job["id"] for job in confirmed["jobs"]]  # 일감은 하나 그대로
    job = wait_finished(http, headers, document_id, timeout=90)
    assert (job["status"], job["attempts"]) == ("done", 1)
    assert job_row(owner, document_id)[:2] == ("done", 1)


def test_when_the_parser_is_down_the_job_fails_at_the_attempt_limit_with_a_reason(
    http: httpx.Client, owner: Owner, tenant: str
) -> None:
    """파서를 멈추면 워커의 호출이 연결 실패(unavailable → Deferred, 「다시 해 본다」)로 갈린다. 다시 해 보기를 되풀이해
    시도 상한(JOB_MAX_ATTEMPTS)에 닿으면 잡기가 `failed`·attempts_exhausted 로 끝낸다. 업무 층은 같은 끝을 가짜 파서로
    재고(reconcile/tests/test_tasks_parse.py), 이것은 멈춘 파서 컨테이너에서 끝에서 끝까지 잰다."""
    pdf = PDF.read_bytes()
    headers = exchange(http, tenant=tenant, sub="it-worker-alice")
    compose("stop", "parser")
    try:
        document_id, _ = create_and_put(http, headers, pdf)
        confirm(http, headers, document_id)
        job = wait_finished(http, headers, document_id, timeout=60 + MAX_ATTEMPTS * RETRY_DELAY_S)
    finally:
        compose("up", "-d", "--no-deps", "--wait", "parser")
    assert (job["status"], job["errorCode"], job["attempts"]) == ("failed", "attempts_exhausted", MAX_ATTEMPTS)
    assert job["summary"] == {} and job["errorMessage"]
    assert job_row(owner, document_id)[:3] == ("failed", MAX_ATTEMPTS, "attempts_exhausted")
    # 시도마다 파서에 못 닿아 「다시 해 본다」로 끝났다(워커의 기록: 시도 1..상한이 전부 outcome=Deferred).
    lines = [line for line in worker_logs(400).splitlines() if f"job_id={job['id']}" in line and "job_finished" in line]
    assert [f"attempt={n} outcome=Deferred" in line for n, line in enumerate(lines, start=1)] == [True] * MAX_ATTEMPTS


def test_a_worker_given_sigterm_finishes_the_job_in_hand_and_exits_0(
    http: httpx.Client, owner: Owner, tenant: str
) -> None:
    """파서를 멈춰 일감을 손에 쥔 워커에 SIGTERM 을 보낸다. 신호 뒤에도 워커는 떠 있고 일감은 processing 이다.
    파서를 풀면 그 일을 마치고(done·attempts 1) 종료 코드 0 으로 내려간다(따뜻한 종료). 끝에서 워커를 다시 만든다.
    신호 기록은 kill 앞에서 센 수보다 늘기를 기다린다: 같은 컨테이너의 지난 줄에 속지 않게(MARC-ISSUE-90 의 1)."""
    pdf = PDF.read_bytes()
    headers = exchange(http, tenant=tenant, sub="it-worker-alice")
    compose("pause", "parser")  # 워커가 파서의 답을 기다리며 멈춰 있게
    paused = True
    try:
        document_id, _ = create_and_put(http, headers, pdf)
        confirm(http, headers, document_id)
        wait_for(
            "일감이 processing·attempts 1 이 되기",
            lambda: job_row(owner, document_id)[:2] == ("processing", 1) or None,
            timeout=30,
        )
        # `stop` 이 아니라 `kill -s SIGTERM`: stop 은 내려갈 때까지 막혀 파서를 풀 수 없다.
        # 기록 전체(--tail 없음)에서 센다: 창을 자르면 지난 줄이 밀려 나가 셈이 줄 수 있다.
        seen = compose("logs", "--no-color", "worker-py").count(WARM_SHUTDOWN)
        compose("kill", "-s", "SIGTERM", "worker-py")
        wait_for(
            "워커가 신호를 받았다고 적기",
            lambda: compose("logs", "--no-color", "worker-py").count(WARM_SHUTDOWN) > seen or None,
            timeout=15,
        )
        assert container_state("worker-py")[0] == "running"  # 하던 일이 있어 아직 내려가지 않았다
        assert job_row(owner, document_id)[:2] == ("processing", 1)
        compose("unpause", "parser")
        paused = False
        wait_for("worker-py 가 내려가기", lambda: container_state("worker-py")[0] == "exited" or None, timeout=60)
        assert container_state("worker-py") == ("exited", 0)
        # 워커가 하나도 없는 지금 일감이 끝나 있다: 내려간 워커가 마친 것이다.
        job = job_of(http, headers, document_id)
        assert (job["status"], job["attempts"], job["errorCode"]) == ("done", 1, None)
        assert job_row(owner, document_id)[:2] == ("done", 1)
    finally:
        if paused:
            compose("unpause", "parser")
        recreate_worker()
