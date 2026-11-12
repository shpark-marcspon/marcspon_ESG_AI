"""흐름 greenwash.engine@G1 의 문서 포트가 도표 라벨을 싣는다(밴드 GE1c ④ — T14 · T16/657). 진짜 DB·실행기·가짜 파서.
world 는 test_engine_g1_runs 의 것(스위치를 켠 world 하나 — 함정 ⑥). 문서·도표 라벨은 지어낸 것(실제 기업·보고서 0).

    T14  포트 RunG1Document.view 는 charts=True: 라벨 행 → 뷰가 라벨을 내고 실행 done · extract 「used」 · 도표 단락이
         판정 근거에 · EPOCH 2·판 2 에 라벨 칸이 빈 행 → 「unavailable」 로 done
    T16  657 잼: 지어낸 300쪽(쪽마다 도표 하나) 한 구획 몫의 포트 쿼리 수(ensure·view·file_name) == 잰 값.
         ★ 657 을 고치면(구획마다 산출물 본문·find_run 을 다시 읽는 것) 이 수가 내려간다 — 그때 이 수를 고친다.
         시간·jsonb 바이트는 보고에만(시험에 박지 않는다).
"""

import hashlib
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.documents import selectors as artifact_selectors
from esgapi.core.documents.contract import ArtifactRef
from esgapi.core.documents.view import ChartLabelsUnavailable
from esgapi.core.resources.ports.parser import Parsed
from esgapi.core.tests.artifact_fakes import block, fake_chart_labels, fake_places, parsed_for, section, table
from esgapi.core.tests.resource_fakes import FakeParser, build_pdf
from esgapi.greenwash.service.actions import engine_g1 as port
from esgapi.greenwash.tests.flows.test_engine_g1_charts import CHART_TITLE, chart_document, labels
from esgapi.greenwash.tests.service.actions import test_engine_g1_runs as runs
from esgapi.greenwash.tests.service.actions.test_engine_g1_runs import (
    PDF,
    World,
    document,
    execute,
    new_run,
    parsed,
    result2,
)
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import login

pytestmark = pytest.mark.django_db

world = runs.world  # 스위치를 켠 world 픽스처를 그대로 쓴다(함정 ⑥ — world 하나)

CHART_PDF = build_pdf(4, text="Synthetic greenwash chart report")
BIG_PAGES = 300
BIG_PDF = build_pdf(BIG_PAGES, text="Synthetic greenwash long chart report")

PORT_QUERIES = 9
"""한 구획 몫(ensure·view·file_name)의 쿼리 수 — 657 잼(GE1c ④). 657 을 고치면 내려간다 — 그때 고친다."""


def charted_parsed(content: bytes) -> Parsed:
    sha = hashlib.sha256(content).hexdigest()
    return Parsed(document=chart_document(sha), char_places=fake_places(sha, page_count=4), chart_labels=labels(sha))


def big_parsed(content: bytes) -> Parsed:
    """지어낸 300쪽: 쪽마다 문단 하나·표 하나·그 표 칸에 값 낱말을 둔 도표 하나."""
    sha = hashlib.sha256(content).hexdigest()
    blocks: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []
    for n in range(1, BIG_PAGES + 1):
        text = f"가상회사의 {n}번 사업장은 설비를 바꾸어 전력 사용량을 줄였고 그 효과를 해마다 점검합니다."
        blocks.append(block(f"p{n}-b1", text, page=n, order=1, section_id="s1"))
        blocks.append(block(f"p{n}-t", page=n, order=2, kind="table", table_id=f"t{n}", section_id="s1"))
        tables.append(table(f"t{n}", [["구분", "2025"], ["가상 설비", str(n)]], page=n))
        charts.append(
            {
                "id": f"p{n}-c1",
                "page": n,
                "bbox": [10.0, 10.0, 200.0, 200.0],
                "form": "bar",
                "orientation": "vertical",
                "title": f"가상 추이 {n}",
                "multi_series": False,
                "categories": ["2025"],
            }
        )
        words.append(
            {
                "chart": f"p{n}-c1",
                "container": f"t{n}:r1c1",
                "start": 0,
                "end": len(str(n)),
                "text": str(n),
                "bbox": [20.0, 20.0, 30.0, 30.0],
                "role": "value",
                "label": {"category": "2025", "series": None, "status": "ok"},
            }
        )
    return parsed_for(
        content,
        page_count=BIG_PAGES,
        blocks=blocks,
        tables=tables,
        sections=[section("s1", "가상 환경 경영", page_start=1, page_end=BIG_PAGES)],
        chart_labels=fake_chart_labels(sha, charts=charts, words=words, page_count=BIG_PAGES),
    )


def with_parser(world: World) -> None:
    world.parser = FakeParser(
        {
            hashlib.sha256(PDF).hexdigest(): parsed(PDF),
            hashlib.sha256(CHART_PDF).hexdigest(): charted_parsed(CHART_PDF),
            hashlib.sha256(BIG_PDF).hexdigest(): big_parsed(BIG_PDF),
        }
    )


def extract_data(world: World, run_id: int) -> dict[str, Any]:
    found = run_selectors.step_output(company_id=world.company_a, run_id=run_id, step="extract")
    assert isinstance(found, run_selectors.StepFound)
    return dict(found.data)


# ── T14 포트가 라벨을 싣는다 ──


def test_t14_a_labelled_artifact_runs_with_the_chart_unit(client: Client, world: World) -> None:
    with_parser(world)
    login(client)
    run_id = new_run(client, document(world, world.company_a, CHART_PDF))
    execute(world, run_id)
    body = result2(world, run_id)
    data = extract_data(world, run_id)
    assert data["chartLabels"] == "used"
    assert data["stat"]["a 도표 단위"] == 1
    assert data["evidenceBudget"] == 12000
    assert world.parser.charts == [True]  # 판 2 는 짓는 때 라벨을 받는다(core — 이 밴드 0줄)
    assert any(f"도표: {CHART_TITLE}" in t for t in world.chat.judged)
    assert body["segments"] and all(s["status"] == "done" for s in body["segments"])


def test_t14_an_epoch_2_artifact_with_an_empty_label_field_is_unavailable_and_done(
    client: Client, world: World
) -> None:
    login(client)
    run_id = new_run(client, document(world, world.company_a))
    mine = port.RunG1Documents(parser=lambda: world.parser).for_run(world.company_a, run_id)
    ref = mine.ensure()
    assert isinstance(ref, ArtifactRef)
    with pytest.raises(ChartLabelsUnavailable):  # charts=False 였다면 ChartLabelsNotLoaded
        mine.view(ref).chart_labels()
    execute(world, run_id)
    result2(world, run_id)
    assert extract_data(world, run_id)["chartLabels"] == "unavailable"


# ── T16 657 잼 ──


def test_t16_the_port_queries_of_one_segment_are_pinned_for_657(client: Client, world: World) -> None:
    """657 잼(고침 0): 지어낸 300쪽 한 구획 몫의 포트 쿼리 수 == PORT_QUERIES. 라벨을 싣든(charts=True) 안 싣든
    뷰 하나의 쿼리 수는 같다(칸만 더 읽는다)."""
    with_parser(world)
    login(client)
    document_id = document(world, world.company_a, BIG_PDF)
    run_id = new_run(client, document_id)
    mine = port.RunG1Documents(parser=lambda: world.parser).for_run(world.company_a, run_id)
    ref = mine.ensure()  # 짓기 한 번(구획은 찾기만)
    assert isinstance(ref, ArtifactRef)
    with CaptureQueriesContext(connection) as seen:
        again = mine.ensure()
        assert isinstance(again, ArtifactRef)
        got = mine.view(again)
        mine.file_name()
    assert len(seen.captured_queries) == PORT_QUERIES
    labels_ = got.chart_labels()
    assert labels_ is not None and len(labels_.charts) == BIG_PAGES
    counts: dict[bool, int] = {}
    for charts in (False, True):
        with CaptureQueriesContext(connection) as one:
            artifact_selectors.artifact_view(
                company_id=world.company_a, document_id=document_id, artifact_id=ref.id, charts=charts
            )
        counts[charts] = len(one.captured_queries)
    assert counts[False] == counts[True]
