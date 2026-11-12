"""문턱(TR3b ★H — ① 커밋 전 · §3-2-7): 지어낸 1,000 실행(옵션 약 166KB, 끝난 실행은 주 결과 약 90KB·요약)에서
run_keys 한 번과 묶음 목록 한 쪽(limit 20)이 p95 < 1s · RSS < 200MB.
병렬 업무 층에 두지 않는다 — TR3B_THRESHOLD=1 일 때만 돈다(§4-9 의 따로 한 번 실행, 판정은 보고 표).
"""

import os
import time
import tracemalloc

import pytest
from django.db import connection

from esgapi.runs.service.selectors import runs as selectors
from esgapi.translation.service.actions import batches
from esgapi.translation.tests.service.actions import threshold_support as support

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(os.environ.get("TR3B_THRESHOLD") != "1", reason="문턱 재기는 TR3B_THRESHOLD=1 로 따로 한 번"),
]

PROJECTION = (
    "SELECT id, COALESCE(((options ->> 'ordered@1'))::jsonb ->> 'batchId', options ->> 'batchId'),"
    " COALESCE(((options ->> 'ordered@1'))::jsonb ->> 'part', options ->> 'part') FROM run_runs"
    " WHERE company_id = %s AND module = 'translation' ORDER BY created_at DESC, id DESC LIMIT 1000"
)
"""run_keys 의 투영식과 같은 꼴(EXPLAIN 으로 Postgres 쪽 비용을 보려고 — 시험만)."""


def run_keys_once(company_id: int) -> int:
    keys = selectors.run_keys(company_id=company_id, module="translation", document_id=None, limit=support.RUNS)
    return len(keys)


def test_run_keys_over_a_thousand_big_runs(companies: tuple[int, int]) -> None:
    a, _ = companies
    size = support.seed(a)
    seconds: list[float] = []
    for _ in range(20):
        start = time.perf_counter()
        assert run_keys_once(a) == support.RUNS
        seconds.append(time.perf_counter() - start)
    tracemalloc.start()
    run_keys_once(a)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    with connection.cursor() as cursor:
        cursor.execute("SELECT sum(pg_column_size(options)), avg(octet_length(options::text)) FROM run_runs")
        stored: object = cursor.fetchone()
        cursor.execute("EXPLAIN (ANALYZE, BUFFERS) " + PROJECTION, [a])
        plan = [str(row[0]) for row in cursor.fetchall()]
    call = f"s.run_keys(company_id={a}, module='translation', document_id=None, limit={{}})"
    head = "from esgapi.runs.service.selectors import runs as s\n"
    baseline = support.subprocess_maxrss(head + "list(" + call.format(1) + ")")
    measured = support.subprocess_maxrss(head + f"assert len({call.format(support.RUNS)}) == {support.RUNS}")
    report = {
        "options_raw_bytes": size,
        "stored_bytes_sum_and_avg_text": stored,
        "p50_s": sorted(seconds)[10],
        "p95_s": support.p95(seconds),
        "max_s": max(seconds),
        "tracemalloc_peak_bytes": peak,
        "subprocess_maxrss_bytes": measured,
        "subprocess_baseline_maxrss_bytes": baseline,
    }
    print("TR3B_THRESHOLD", report)
    print("\n".join(plan))
    assert support.p95(seconds) < 1.0
    assert measured < 200 * 1024 * 1024


def list_once(company_id: int) -> int:
    page = batches.batches(
        company_id=company_id, user_id=1, document_id=None, state=None, mine=False, limit=20, offset=0
    )
    return len(page["results"])


def test_the_batch_list_over_a_thousand_big_runs(companies: tuple[int, int]) -> None:
    a, _ = companies
    support.seed(a)
    seconds: list[float] = []
    for _ in range(20):
        start = time.perf_counter()
        assert list_once(a) == 20
        seconds.append(time.perf_counter() - start)
    tracemalloc.start()
    list_once(a)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    head = "from esgapi.translation.service.actions import batches as b\n"
    call = f"b.batches(company_id={a}, user_id=1, document_id=None, state=None, mine=False, limit={{}}, offset=0)"
    baseline = support.subprocess_maxrss(head + "b.RUNS_MAX = 1\n" + call.format(1))
    measured = support.subprocess_maxrss(head + f"assert len({call.format(20)}['results']) == 20")
    report = {
        "list_p50_s": sorted(seconds)[10],
        "list_p95_s": support.p95(seconds),
        "list_max_s": max(seconds),
        "list_tracemalloc_peak_bytes": peak,
        "list_subprocess_maxrss_bytes": measured,
        "list_subprocess_baseline_maxrss_bytes": baseline,
    }
    print("TR3B_THRESHOLD", report)
    assert support.p95(seconds) < 1.0
    assert measured < 200 * 1024 * 1024
