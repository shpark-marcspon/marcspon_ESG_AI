# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""영문번역 묶음 목록·하나 보기(service/actions/batches.py — 밴드 TR3b §3-2). 업무 층.

묶음 = (문서, batchKey). 파트 최신 실행·앞 회차·단계·digest 를 옵션·결과 본문 없이 조립하고, 거름(state·mine)은 묶은
뒤·자르기 전, count·isNext 는 거른 뒤 묶음 수다. 쿼리 수는 묶음 수와 무관하다. 경로는 HTTP 로(꼴 strict·404 넷).
★ 실행·단계·결과 행은 seed(apps.get_model)로 심는다 — runs.models 를 import 하지 않는다(계약 나). 전부 지어낸 것이다.
"""

from typing import Any

import pytest
from django.test import Client
from pydantic import TypeAdapter
from pytest_django import DjangoAssertNumQueries

from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.translation.contracts.batch_shapes import (
    BATCH_SHAPE,
    BATCH_SHAPES,
    TranslationBatchDetail,
    TranslationBatchPage,
)
from esgapi.translation.contracts.digest_shapes import DIGEST_SHAPE
from esgapi.translation.service.actions import batches
from esgapi.translation.tests.service import seed
from tests.support.http import login

pytestmark = pytest.mark.django_db

PAGE: TypeAdapter[Any] = TypeAdapter(TranslationBatchPage)
DETAIL: TypeAdapter[Any] = TypeAdapter(TranslationBatchDetail)
B1 = "00000000-0000-4000-8000-000000000001"
B2 = "00000000-0000-4000-8000-000000000002"


def page(company_id: int, *, user_id: int = 1, limit: int = 50, offset: int = 0, **kw: Any) -> dict[str, Any]:
    found: dict[str, Any] = dict(
        batches.batches(
            company_id=company_id,
            user_id=user_id,
            document_id=kw.get("document_id"),
            state=kw.get("state"),
            mine=kw.get("mine", False),
            limit=limit,
            offset=offset,
        )
    )
    PAGE.validate_python(found, strict=True)
    return found


def keys(found: dict[str, Any]) -> list[tuple[int, str]]:
    return [(b["document"]["id"], b["batchKey"]) for b in found["results"]]


# ── 3-2-1 묶음 ──


def test_three_parts_of_one_batch_id_are_one_batch_in_part_order(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = seed.document(a)
    runs = [seed.run(a, doc, part, batch_id=B1) for part in ("general", "story", "ceo_message")]
    (batch,) = page(a)["results"]
    assert batch["batchKey"] == B1 and batch["partCount"] == 3 and batch["doneParts"] == 3
    assert [p["part"] for p in batch["parts"]] == ["ceo_message", "story", "general"]
    assert [p["latest"]["runId"] for p in batch["parts"]] == [runs[2], runs[1], runs[0]]
    assert batch["state"] == "done"


def test_running_a_part_again_makes_round_two_and_the_newest_latest(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = seed.document(a)
    first = seed.run(a, doc, "story", batch_id=B1, status="failed", error_code="flow_failed", failed_step="translate")
    again = seed.run(a, doc, "story", batch_id=B1)
    (batch,) = page(a)["results"]
    (part,) = batch["parts"]
    assert (part["latest"]["runId"], part["round"]) == (again, 2)
    assert part["earlier"] == [
        {
            "runId": first,
            "status": "failed",
            "createdAt": part["earlier"][0]["createdAt"],
            "finishedAt": part["earlier"][0]["finishedAt"],
            "outcome": None,
        }
    ]
    assert batch["state"] == "done"  # 앞 회차 failed 를 다시 돌려 done


def test_runs_without_a_batch_id_are_a_batch_each_and_documents_never_mix(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc, other = seed.document(a), seed.document(a)
    one = seed.run(a, doc, "story")
    two = seed.run(a, doc, "story")
    seed.run(a, doc, "general", batch_id=B1)
    seed.run(a, other, "general", batch_id=B1)  # 다른 문서 같은 batchId
    assert keys(page(a)) == [(other, B1), (doc, B1), (doc, f"run-{two}"), (doc, f"run-{one}")]
    assert keys(page(a, document_id=doc)) == [(doc, B1), (doc, f"run-{two}"), (doc, f"run-{one}")]
    assert keys(page(a, document_id=other)) == [(other, B1)]


def test_pages_of_twenty_five_batches(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = seed.document(a)
    for _ in range(25):
        seed.run(a, doc, "story")
    sizes = [(len(p["results"]), p["count"], p["isNext"]) for p in (page(a, limit=10, offset=o) for o in (0, 10, 20))]
    assert sizes == [(10, 25, True), (10, 25, True), (5, 25, False)]
    assert page(a, limit=10, offset=30)["results"] == []


@pytest.mark.parametrize(("runs", "truncated"), [(4, False), (5, True)])
def test_truncated_only_past_the_runs_max(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch, runs: int, truncated: bool
) -> None:
    """RUNS_MAX 를 작게(4): 정확히 4 면 false, 5 면 true 이고 가장 오래된 실행이 빠진다(1,000·1,001 의 짝)."""
    a, _ = companies
    monkeypatch.setattr(batches, "RUNS_MAX", 4)
    doc = seed.document(a)
    made = [seed.run(a, doc, "story") for _ in range(runs)]
    found = page(a)
    assert found["truncated"] is truncated
    assert keys(found) == [(doc, f"run-{r}") for r in reversed(made)][:4]


# ── 3-2-2 거름 ──


def test_each_state_filters_after_grouping(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = seed.document(a)
    done = seed.run(a, doc, "story")
    active = seed.run(a, doc, "story", status="processing")
    failed = seed.run(a, doc, "story", status="failed", error_code="flow_failed")
    rejected = seed.run(a, doc, "story", digest_body=seed.digest("rejected", autofix=None))
    assert keys(page(a, state="done")) == [(doc, f"run-{done}")]
    assert keys(page(a, state="active")) == [(doc, f"run-{active}")]
    assert keys(page(a, state="failed")) == [(doc, f"run-{rejected}"), (doc, f"run-{failed}")]
    assert page(a)["count"] == 4  # 분모: 거르지 않으면 넷
    assert {page(a, state=s)["companyName"] for s in ("done", "active", "failed", None)} == {"가 회사"}  # 거름과 무관


def test_mine_is_the_documents_uploader_and_counts_after_filtering(companies: tuple[int, int]) -> None:
    a, _ = companies
    mine, theirs = seed.document(a, uploaded_by="5"), seed.document(a, uploaded_by="6")
    for _ in range(12):
        seed.run(a, mine, "story", created_by=6)  # 실행은 남이 만들어도 내 문서면 mine
    for _ in range(4):
        seed.run(a, theirs, "story", created_by=5)  # 내가 만든 실행이어도 남의 문서면 빠짐
    first = page(a, user_id=5, mine=True, limit=10)
    second = page(a, user_id=5, mine=True, limit=10, offset=10)
    assert (first["count"], first["isNext"], len(first["results"])) == (12, True, 10)
    assert (second["count"], second["isNext"], len(second["results"])) == (12, False, 2)
    assert first["companyName"] == second["companyName"] == "가 회사"  # mine·offset 과 무관
    assert {b["document"]["id"] for b in first["results"] + second["results"]} == {mine}
    assert page(a, user_id=5)["count"] == 16  # 분모


def test_state_and_mine_together(companies: tuple[int, int]) -> None:
    a, _ = companies
    mine, theirs = seed.document(a, uploaded_by="5"), seed.document(a, uploaded_by="6")
    for _ in range(12):
        seed.run(a, mine, "story", status="queued")
    seed.run(a, mine, "story")
    seed.run(a, theirs, "story", status="queued")
    first = page(a, user_id=5, mine=True, state="active", limit=10)
    second = page(a, user_id=5, mine=True, state="active", limit=10, offset=10)
    assert [(p["count"], p["isNext"], len(p["results"])) for p in (first, second)] == [(12, True, 10), (12, False, 2)]


# ── 회사 이름(TRC1 §3-2-2) ──


def test_the_list_carries_the_requests_company_name_even_on_an_empty_page(companies: tuple[int, int]) -> None:
    a, b = companies
    doc_a, doc_b = seed.document(a), seed.document(b)
    seed.run(a, doc_a, "story")
    seed.run(b, doc_b, "story", status="processing")
    assert (page(a)["companyName"], page(a)["count"]) == ("가 회사", 1)
    assert (page(b)["companyName"], page(b)["count"]) == ("나 회사", 1)
    empties = (page(b, document_id=doc_a), page(b, state="done"), page(a, document_id=doc_a + 1000))
    assert [(p["companyName"], p["count"]) for p in empties] == [("나 회사", 0), ("나 회사", 0), ("가 회사", 0)]


def test_a_company_without_runs_still_gets_its_name(companies: tuple[int, int]) -> None:
    _, b = companies
    assert page(b) == {"companyName": "나 회사", "count": 0, "isNext": False, "truncated": False, "results": []}


# ── 3-2-3 쿼리 수·넘기는 인자 ──


def mixed(company_id: int, n: int) -> None:
    """묶음 n 개 — 묶음마다 끝난 파트 둘(앞 회차 하나 포함)과 진행 중 파트 하나(같은 섞임)."""
    doc = seed.document(company_id)
    for i in range(n):
        batch = f"00000000-0000-4000-8000-{i:012x}"
        seed.run(company_id, doc, "story", batch_id=batch, status="failed")
        seed.run(company_id, doc, "story", batch_id=batch)
        seed.run(company_id, doc, "general", batch_id=batch)
        seed.run(company_id, doc, "ceo_message", batch_id=batch, status="processing")


@pytest.mark.parametrize("n", [1, 5])
def test_the_query_count_does_not_grow_with_batches(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries, n: int
) -> None:
    a, _ = companies
    mixed(a, n)
    # 회사 이름 · 실행 열쇠 · 요약 · 문서 · 실행(15 이하 하나) · 단계 · 이름 + 세이브포인트 2(실행 열쇠 읽기)
    with django_assert_num_queries(9):  # DVI1 +2: 세이브포인트
        assert len(page(a)["results"]) == n


def test_a_full_page_of_three_parts_is_at_most_ten_queries(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    """쪽 20묶음 × 파트 셋 = 최신 실행 60 → 실행 읽기 ⌈60/15⌉ = 4 — 6 + 4 = 10(상한, 회사 이름 1 포함).
    10 + DVI1 세이브포인트 2(실행 열쇠 읽기의 SAVEPOINT·RELEASE)."""
    a, _ = companies
    mixed(a, 21)
    with django_assert_num_queries(12):  # DVI1 +2: 세이브포인트
        assert len(page(a, limit=20)["results"]) == 20


def test_runs_of_gets_at_most_a_chunk_at_a_time(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    a, _ = companies
    mixed(a, 7)  # 최신 21
    sizes: list[int] = []
    real = run_selectors.runs_of

    def spy(**kw: Any) -> Any:
        sizes.append(len(kw["run_ids"]))
        return real(**kw)

    monkeypatch.setattr(run_selectors, "runs_of", spy)
    page(a)
    assert sizes == [batches.RUNS_OF_CHUNK, 21 - batches.RUNS_OF_CHUNK] == [15, 6]


@pytest.mark.parametrize("n", [15, 16, 30, 31])
def test_chunking_does_not_change_the_page(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch, n: int) -> None:
    """끊는 경계(15·16·30·31 최신 실행)에서 끊어 읽은 쪽 = 한 번에 읽은 쪽."""
    a, _ = companies
    doc = seed.document(a)
    for i in range(n):
        seed.run(a, doc, "story", status=("done", "failed", "processing")[i % 3])
    chunked = page(a)
    assert sum(len(b["parts"]) for b in chunked["results"]) == n
    monkeypatch.setattr(batches, "RUNS_OF_CHUNK", 10**6)
    assert page(a) == chunked


def test_the_list_reads_digests_only_and_steps_and_runs_of_the_page_latest_only(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """요약은 schema_versions 로 digest 만, 실행·단계는 그 쪽 묶음의 파트 최신 실행만(앞 회차·다른 쪽 0)."""
    a, _ = companies
    mixed(a, 3)
    seen: dict[str, list[Any]] = {"results": [], "steps": [], "runs": []}

    def spy(name: str, real: Any) -> Any:
        def call(**kw: Any) -> Any:
            seen[name].append(kw)
            return real(**kw)

        return call

    monkeypatch.setattr(run_selectors, "results_of", spy("results", run_selectors.results_of))
    monkeypatch.setattr(run_selectors, "step_lines_of", spy("steps", run_selectors.step_lines_of))
    monkeypatch.setattr(run_selectors, "runs_of", spy("runs", run_selectors.runs_of))
    found = page(a, limit=2)
    latest = sorted(p["latest"]["runId"] for b in found["results"] for p in b["parts"])
    assert [kw.get("schema_versions") for kw in seen["results"]] == [{DIGEST_SHAPE}]
    assert [sorted(kw["run_ids"]) for kw in seen["steps"]] == [latest]
    assert sorted(i for kw in seen["runs"] for i in kw["run_ids"]) == latest
    assert len(latest) == 2 * 3  # 분모: 쪽 둘 × 파트 셋


# ── 3-2-4 상태와 줄 ──


def test_each_run_line(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = seed.document(a)
    queued = seed.run(a, doc, "ceo_message", batch_id=B1, status="queued")
    processing = seed.run(a, doc, "story", batch_id=B1, status="processing")
    done = seed.run(a, doc, "general", batch_id=B1)
    (batch,) = page(a)["results"]
    lines = {p["part"]: p["latest"] for p in batch["parts"]}
    assert (batch["state"], batch["doneParts"], batch["partCount"]) == ("active", 1, 3)
    assert lines["ceo_message"]["runId"] == queued and lines["ceo_message"]["startedAt"] is None
    assert lines["story"]["runId"] == processing
    assert lines["story"]["steps"] == [
        {"step": "prepare", "status": "done", "done": None, "total": None},
        {"step": "translate", "status": "running", "done": 2, "total": 5},
        {"step": "report", "status": "pending", "done": None, "total": None},
    ]
    general = lines["general"]
    assert general["runId"] == done and general["digest"] == seed.digest()
    assert (general["pages"], general["style"], general["glossaryCounts"]) == (
        {"start": 3, "end": None},
        {"compareAb": True, "single": "B"},
        {"base": 2, "final": 3},
    )
    assert [s["status"] for s in general["steps"]] == ["done", "done", "done"]
    assert (general["failedStep"], general["errorCode"]) == (None, None)


def test_a_failed_line_and_a_rejected_or_partial_digest_make_the_batch_failed(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = seed.document(a)
    seed.run(a, doc, "story", batch_id=B1, status="failed", error_code="flow_failed", failed_step="translate")
    seed.run(a, doc, "general", batch_id=B2, digest_body=seed.digest("rejected", autofix=None))
    seed.run(a, doc, "story", digest_body=seed.digest("partial"))
    found = {b["batchKey"]: b for b in page(a)["results"]}
    failed = found[B1]["parts"][0]["latest"]
    assert (failed["failedStep"], failed["errorCode"], failed["digest"]) == ("translate", "flow_failed", None)
    assert [s["status"] for s in failed["steps"]] == ["done", "failed", "pending"]  # GET /runs/{id} 와 같은 단계(★D)
    assert {b["state"] for b in found.values()} == {"failed"}
    assert found[B2]["parts"][0]["latest"]["digest"]["rejectionKind"] == "over_budget"
    assert (found[B2]["doneParts"], found[B1]["doneParts"]) == (1, 0)


def test_an_old_run_without_a_digest_is_null_and_counts_as_done(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = seed.document(a)
    seed.run(a, doc, "story", batch_id=B1, digest_body=False)
    seed.run(a, doc, "story", batch_id=B1)
    (batch,) = page(a)["results"]
    (part,) = batch["parts"]
    assert part["earlier"][0]["outcome"] is None and part["latest"]["digest"] is not None
    seed.run(a, doc, "general", digest_body=False)
    old = next(b for b in page(a)["results"] if b["batchKey"] != B1)
    assert (old["parts"][0]["latest"]["digest"], old["state"]) == (None, "done")


def test_names_are_the_uploader_and_the_newest_runs_maker(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = seed.document(a, uploaded_by="77")
    seed.run(a, doc, "story", created_by=88)
    (batch,) = page(a)["results"]
    assert batch["document"]["uploadedBy"] == {"userId": 77, "name": "알 수 없는 사용자"}
    assert batch["createdBy"] == {"userId": 88, "name": "알 수 없는 사용자"}
    assert batch["document"]["uploadedAt"] is not None and batch["document"]["fileName"] == "지은 보고서.docx"


# ── 3-2-5 하나 보기(HTTP) ──


def url(document_id: int, key: str) -> str:
    return f"/api/translation/documents/{document_id}/batches/{key}"


def test_one_batch_over_http_is_the_list_line_and_truncated(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    seed.run(a, doc, "story", batch_id=B1)
    single = seed.run(a, doc, "general")
    got = client.get(url(doc, B1))
    assert got.status_code == 200, got.content.decode()
    body = got.json()
    DETAIL.validate_python(body, strict=True)
    listed = client.get(f"/api/translation/batches?documentId={doc}").json()
    PAGE.validate_python(listed, strict=True)
    line = next(b for b in listed["results"] if b["batchKey"] == B1)
    assert body == {**line, "truncated": False}
    assert listed["companyName"] == "가 회사" and "companyName" not in body  # 회사 이름은 목록 쪽에만(TRC1 §3-2-6)
    assert client.get(url(doc, f"run-{single}")).json()["batchKey"] == f"run-{single}"
    BATCH_SHAPES[BATCH_SHAPE].validate_python(line, strict=True)


def test_one_batch_is_404_for_a_bad_key_a_missing_batch_another_company_or_a_batched_runs_run_key(
    client: Client, companies: tuple[int, int]
) -> None:
    a, b = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    batched = seed.run(a, doc, "story", batch_id=B1)
    theirs = seed.document(b)
    seed.run(b, theirs, "story", batch_id=B1)
    for key, document in (("RUN-1", doc), ("run-0", doc), (B2, doc), (B1, theirs), (f"run-{batched}", doc)):
        got = client.get(url(document, key))
        assert (got.status_code, got.json()["error"]["code"]) == (404, "NOT_FOUND"), key
    assert client.get(url(doc, B1)).status_code == 200  # 분모


def test_a_greenwash_run_is_not_a_batch(client: Client, companies: tuple[int, int]) -> None:
    from django.apps import apps

    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    green = seed.run(a, doc, "story")
    apps.get_model("runs", "RunRow").for_company(a).filter(pk=green).update(module="greenwash")  # pyright: ignore[reportAttributeAccessIssue]
    assert client.get(url(doc, f"run-{green}")).status_code == 404
    assert client.get("/api/translation/batches").json()["count"] == 0


def test_earlier_rounds_are_newest_first(companies: tuple[int, int]) -> None:
    """같은 파트 셋(round 3): earlier 는 새 것 먼저(검증 권고 R4)."""
    a, _ = companies
    doc = seed.document(a)
    first = seed.run(a, doc, "story", batch_id=B1, status="failed")
    second = seed.run(a, doc, "story", batch_id=B1, digest_body=seed.digest("partial"))
    third = seed.run(a, doc, "story", batch_id=B1)
    (part,) = page(a)["results"][0]["parts"]
    assert (part["latest"]["runId"], part["round"]) == (third, 3)
    assert [(e["runId"], e["outcome"]) for e in part["earlier"]] == [(second, "partial"), (first, None)]
