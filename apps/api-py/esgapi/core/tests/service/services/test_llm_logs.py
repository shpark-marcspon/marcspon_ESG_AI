"""insert_rows(실행 묶음이 넣는 LLM 기록 — RX1a)를 진짜 DB 로 잰다: 그 회사로 넣고 run_id 를 지도로 바꿈
(NULL 은 그대로), created_at 은 넣은 때, id·company_id·created_at 이 실리면 ValueError,
지도 밖 실행이면 UnknownId — 둘 다 행 0.
★ 숫자는 전부 지어낸 것이다(synthetic).
"""

from datetime import UTC, datetime

import pytest
from django.db import transaction

from esgapi.core.flows.carriers import UnknownId
from esgapi.core.models import LlmCallLogRow
from esgapi.core.service.services.llm_logs import insert_rows

pytestmark = pytest.mark.django_db
TS = datetime(2026, 10, 1, 1, 2, 3, tzinfo=UTC)


def a_row(run_id: int | None, call_id: str) -> dict[str, object]:
    return {
        "module": "probe",
        "ts": TS,
        "call_id": call_id,
        "attempt": 0,
        "prompt_id": "probe.judge",
        "prompt_version": 1,
        "template_hash": "t" * 64,
        "request_hash": "r" * 64,
        "duration_ms": 1.0,
        "result_kind": "success",
        "run_id": run_id,
    }


def test_rows_go_to_the_company_with_new_run_ids(companies: tuple[int, int]) -> None:
    a, b = companies
    before = datetime.now(UTC)
    assert insert_rows(company_id=b, rows=[a_row(7, "c1"), a_row(None, "c2")], run_map={7: 70}) == 2
    rows = list(LlmCallLogRow.for_company(b).order_by("id"))
    assert [(row.call_id, row.run_id) for row in rows] == [("c1", 70), ("c2", None)]
    assert all(row.created_at >= before and row.ts == TS for row in rows)  # 넣은 때 · 보통 시각 칸은 그대로
    assert not LlmCallLogRow.for_company(a).exists()


@pytest.mark.parametrize("extra", ["id", "company_id", "created_at"])
def test_carried_ids_and_times_are_refused(companies: tuple[int, int], extra: str) -> None:
    row = a_row(7, "c1") | {extra: 1}
    with pytest.raises(ValueError, match=extra), transaction.atomic():
        insert_rows(company_id=companies[1], rows=[row], run_map={7: 70})
    assert not LlmCallLogRow.for_company(companies[1]).exists()


def test_a_run_outside_the_map_is_refused_and_nothing_stays(companies: tuple[int, int]) -> None:
    with pytest.raises(UnknownId), transaction.atomic():
        insert_rows(company_id=companies[1], rows=[a_row(7, "c1"), a_row(8, "c2")], run_map={7: 70})
    assert not LlmCallLogRow.for_company(companies[1]).exists()
