# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""묶음 줄의 흐름 종류(service/actions/batches.py — 밴드 TRS3 B1). 업무 층.

파트 최신 실행 줄 `latest.flowId` = 그 실행의 흐름 id 그대로, 묶음 `inputKind` = 묶음 차례를 정한 가장 새 실행의 흐름
id 가 translation.pdf@ 로 시작하면 pdf, 아니면 word. 쿼리 수는 칸을 더하기 전(test_batches.py 의 7·10)과 같다.
★ 실행 행은 seed 로 심는다(runs.models import 0). 전부 지어낸 것이다.
"""

from typing import Any

import pytest
from django.test import Client
from pydantic import TypeAdapter
from pytest_django import DjangoAssertNumQueries

from esgapi.translation.contracts.batch_shapes import TranslationBatchDetail, TranslationBatchPage
from esgapi.translation.flows import colab_158, pdf_158
from esgapi.translation.service.actions import batches
from esgapi.translation.tests.service import seed
from tests.support.http import login

pytestmark = pytest.mark.django_db

PAGE: TypeAdapter[Any] = TypeAdapter(TranslationBatchPage)
DETAIL: TypeAdapter[Any] = TypeAdapter(TranslationBatchDetail)
WORD = colab_158.FLOW_ID
PDF = pdf_158.FLOW_ID
B1 = "00000000-0000-4000-8000-000000000001"


def page(company_id: int, *, limit: int = 50) -> list[dict[str, Any]]:
    found: dict[str, Any] = dict(
        batches.batches(
            company_id=company_id, user_id=1, document_id=None, state=None, mine=False, limit=limit, offset=0
        )
    )
    PAGE.validate_python(found, strict=True)
    return found["results"]


def test_word_runs_are_a_word_batch_with_their_flow_id(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = seed.document(a)
    seed.run(a, doc, "story", batch_id=B1, flow_id=WORD)
    seed.run(a, doc, "general", batch_id=B1, flow_id=WORD)
    (batch,) = page(a)
    assert batch["inputKind"] == "word"
    assert [p["latest"]["flowId"] for p in batch["parts"]] == [WORD, WORD]


def test_pdf_runs_are_a_pdf_batch_with_their_flow_id(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = seed.document(a, name="지은 보고서.pdf")
    seed.run(a, doc, "story", batch_id=B1, flow_id=PDF, status="failed", error_code="no_text_layer")
    seed.run(a, doc, "general", batch_id=B1, flow_id=PDF, status="processing")
    (batch,) = page(a)
    assert batch["inputKind"] == "pdf"
    assert [p["latest"]["flowId"] for p in batch["parts"]] == [PDF, PDF]


def test_an_old_flow_id_is_word(companies: tuple[int, int]) -> None:
    """옛 실행(seed 기본 흐름 id — translation.pdf@ 앞머리 아님)도 word 다."""
    a, _ = companies
    seed.run(a, seed.document(a), "story")
    (batch,) = page(a)
    assert (batch["inputKind"], batch["parts"][0]["latest"]["flowId"]) == ("word", "translation.colab_158@1")


@pytest.mark.parametrize(("older", "newer", "kind"), [(WORD, PDF, "pdf"), (PDF, WORD, "word")])
def test_two_parts_on_different_flows_follow_the_newest_run(
    companies: tuple[int, int], older: str, newer: str, kind: str
) -> None:
    """지어낸 꼴(웹은 한 묶음을 한 흐름으로 시작한다): 파트 둘이 다른 흐름이면 가장 새 실행 기준, 파트 줄은 제 흐름."""
    a, _ = companies
    doc = seed.document(a)
    seed.run(a, doc, "story", batch_id=B1, flow_id=older)
    seed.run(a, doc, "general", batch_id=B1, flow_id=newer)
    (batch,) = page(a)
    assert batch["inputKind"] == kind
    assert {p["part"]: p["latest"]["flowId"] for p in batch["parts"]} == {"story": older, "general": newer}


def test_a_newer_round_of_the_same_part_decides(companies: tuple[int, int]) -> None:
    """같은 파트를 다른 흐름으로 다시 돌리면(지어낸 꼴) 새 회차가 latest 이고 묶음 종류도 그것을 따른다."""
    a, _ = companies
    doc = seed.document(a)
    seed.run(a, doc, "story", batch_id=B1, flow_id=PDF)
    seed.run(a, doc, "story", batch_id=B1, flow_id=WORD)
    (batch,) = page(a)
    (part,) = batch["parts"]
    assert (batch["inputKind"], part["latest"]["flowId"], part["round"]) == ("word", WORD, 2)
    assert "flowId" not in part["earlier"][0]  # earlier 줄 0 바뀜


def pdf_mixed(company_id: int, n: int) -> None:
    """test_batches.py 의 mixed 와 같은 꼴 — 흐름만 PDF."""
    doc = seed.document(company_id)
    for i in range(n):
        batch = f"00000000-0000-4000-8000-{i:012x}"
        seed.run(company_id, doc, "story", batch_id=batch, status="failed", flow_id=PDF)
        seed.run(company_id, doc, "story", batch_id=batch, flow_id=PDF)
        seed.run(company_id, doc, "general", batch_id=batch, flow_id=PDF)
        seed.run(company_id, doc, "ceo_message", batch_id=batch, status="processing", flow_id=PDF)


@pytest.mark.parametrize("n", [1, 5])
def test_the_query_count_is_unchanged(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries, n: int
) -> None:
    a, _ = companies
    pdf_mixed(a, n)
    # test_batches.py 와 같은 9 — inputKind 는 이미 읽은 줄에서 셈
    with django_assert_num_queries(9):  # DVI1 +2: 세이브포인트
        found = page(a)
    assert [b["inputKind"] for b in found] == ["pdf"] * n


def test_a_full_page_is_still_at_most_ten_queries(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    pdf_mixed(a, 21)
    with django_assert_num_queries(12):  # 10 + DVI1 세이브포인트 2 · DVI1 +2: 세이브포인트
        assert len(page(a, limit=20)) == 20


def test_one_batch_over_http_carries_both_fields(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = seed.document(a)
    run = seed.run(a, doc, "general", batch_id=B1, flow_id=PDF)
    got = client.get(f"/api/translation/documents/{doc}/batches/{B1}")
    assert got.status_code == 200, got.content.decode()
    body = got.json()
    DETAIL.validate_python(body, strict=True)
    assert body["inputKind"] == "pdf"
    assert body["parts"][0]["latest"]["runId"] == run and body["parts"][0]["latest"]["flowId"] == PDF
    listed = client.get("/api/translation/batches")
    assert listed.status_code == 200
    (line,) = listed.json()["results"]
    assert (line["inputKind"], line["parts"][0]["latest"]["flowId"]) == ("pdf", PDF)
