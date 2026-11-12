# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""목록 줄 GET /greenwash/checks 의 묶음 읽기·잘림·실패 쪽 수(밴드 G1b-2b ② — MARC-ISSUE-219, 감독 처분 Q4·Q5 (가)).
업무 층: 진짜 DB, 세션은 EDK 교환(login — 회사 A).

    쿼리 수      실행 1개와 5개(단계 행 든 것)에서 같은 k(django_assert_num_queries 두 번)
    truncated    실행 수 > RUNS_MAX 면 true(새 것 먼저 RUNS_MAX 까지) · 같으면 false(시험에서 RUNS_MAX 를 작게)
    failedPageCount  실패 쪽 둘 → 2 · 빈 목록 → 0 · dry-run(candidateStats null) → null · 끝나지 않음 → null ·
                     결과 행 없는 끝난 실행 → null
    문서 칸      묶음 읽기 뒤에도 reportYear·previousDocumentId·pageCount 가 문서·결과의 값

★ 실행·결과·단계 행은 seed(apps.get_model)로 심는다 — runs.models 를 import 하지 않는다(계약 나). 이름·글은 지은 것.
"""

import copy
from typing import Any

import pytest
from django.test import Client

from esgapi.core.models import DocumentRow
from esgapi.greenwash.service.actions import checks as checks_action
from esgapi.greenwash.tests.service import seed
from esgapi.greenwash.tests.service.apis.test_greenwash_checks import FIXED_QUERIES, NORMAL, checks
from tests.support.http import login

pytestmark = pytest.mark.django_db

DRY = seed.example("result-dry-run")


def with_failed_pages(pages: list[int]) -> dict[str, Any]:
    body = copy.deepcopy(NORMAL)
    body["candidateStats"]["failedPages"] = [{"page": p, "error": "지은 오류"} for p in pages]
    return body


def stepped_run(company_id: int, **kwargs: Any) -> int:
    run_id = seed.run(company_id, **kwargs)
    seed.step(company_id, run_id, "extract", 0, "done")
    seed.step(company_id, run_id, "judge", 1, "done", 4, 4)
    return run_id


def test_the_query_count_is_the_same_for_one_run_and_five(
    client: Client, companies: tuple[int, int], django_assert_num_queries: Any
) -> None:
    login(client)
    a = companies[0]
    stepped_run(a, result=NORMAL)
    with django_assert_num_queries(FIXED_QUERIES):
        one = checks(client)
    for _ in range(3):
        stepped_run(a, result=with_failed_pages([2, 3]))  # 끝난 실행 — 각자 문서
    stepped_run(a, status="failed")
    with django_assert_num_queries(FIXED_QUERIES):
        five = checks(client)
    assert (len(one["runs"]), len(five["runs"])) == (1, 5)  # 분모
    assert (len(one["documents"]), len(five["documents"])) == (1, 5)
    assert all(len(r["steps"]) == 2 for r in five["runs"])  # 단계도 묶음에서 실행마다 제자리
    print(f"목록 줄 쿼리 k = {FIXED_QUERIES}(실행 1·5)")


def test_truncated_is_true_only_past_runs_max(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    login(client)
    a = companies[0]
    monkeypatch.setattr(checks_action, "RUNS_MAX", 2)
    older = seed.run(a, status="queued")
    seed.run(a, status="queued")
    at_max = checks(client)
    assert (at_max["truncated"], len(at_max["runs"])) == (False, 2)  # 같으면 잘리지 않음
    seed.run(a, status="queued")
    past = checks(client)
    assert (past["truncated"], len(past["runs"])) == (True, 2)
    assert older not in {r["runId"] for r in past["runs"]}  # 오래된 것이 빠진다


def test_the_failed_page_count_comes_from_the_done_result(client: Client, companies: tuple[int, int]) -> None:
    login(client)
    a = companies[0]
    two = seed.run(a, result=with_failed_pages([3, 7]))
    none = seed.run(a, result=with_failed_pages([]))
    dry = seed.run(a, result=DRY)
    running = seed.run(a, status="processing", result=with_failed_pages([1]))  # 남은 결과 행이 있어도 끝나지 않음
    failed = seed.run(a, status="failed", error_code="step_error", failed_step="judge")
    no_result = seed.run(a)  # 끝났는데 결과 행 없음
    runs = {r["runId"]: r["failedPageCount"] for r in checks(client)["runs"]}
    assert runs == {two: 2, none: 0, dry: None, running: None, failed: None, no_result: None}


def test_the_document_cells_keep_their_values_after_the_batch_read(client: Client, companies: tuple[int, int]) -> None:
    login(client)
    a = companies[0]
    first = seed.document(a, name="가상-보고서-2024.pdf")
    second = seed.document(a, name="가상-보고서-2025.pdf")
    DocumentRow.for_company(a).filter(pk=second).update(report_year=2025, previous_document_id=first)
    seed.run(a, result=NORMAL, document_id=first)
    seed.run(a, result=NORMAL, document_id=second)
    documents = {d["documentId"]: d for d in checks(client)["documents"]}
    assert set(documents) == {first, second}
    assert (documents[second]["reportYear"], documents[second]["previousDocumentId"]) == (2025, first)
    assert (documents[first]["reportYear"], documents[first]["previousDocumentId"]) == (None, None)
    assert documents[second]["pageCount"] == NORMAL["source"]["pageCount"]
