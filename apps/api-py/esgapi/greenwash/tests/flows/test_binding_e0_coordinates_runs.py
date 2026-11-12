# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""끼움의 좌표 엔진(밴드 G1b-2b ① — MARC-ISSUE-98 (4))을 진짜 DB 의 실행기로 잰다. 업무 층: 저장소는 가짜, 태스크는
함수를 직접 부른다(test_binding_e0_runs.py 의 World·대본 모의 공급사를 그대로 쓴다).

    끝까지      pdfbuild 로 지은 PDF(표본 쪽 글 넷) + 진짜 읽개(pypdf) + 대본 모의 → done, 결과 position 이 값(쪽·상자),
                단계 locate data 에 stats(문서 열기 1, 갈래 수의 합 = 판정 문장 수)
    이어 돌기   (★E) report 에서 실패한 실행을 resumeFromRunId 로 이어 돌리면 locate 단계는 done 으로 옮겨지고(data 의
                positions·stats 바이트 그대로), 새 실행은 좌표를 다시 부르지 않는다

★ 실제 공급사·키·네트워크 0. 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import json
from typing import Any

import pytest
from django.test import Client

from esgapi.core.resources import queue as hooks
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.tests.flows import test_binding_e0_runs as bound
from esgapi.greenwash.tests.flows.test_binding_e0_runs import (
    MINIMAL,
    World,
    create,
    execute,
    new_run,
    result_body,
    run_of,
)
from esgapi.greenwash.tests.tools.test_pdfium_locate import sample_pdf
from esgapi.greenwash.tools.coordinates import PdfiumCoordinates
from esgapi.runs.service.selectors import runs as run_selectors

pytestmark = pytest.mark.django_db
world = bound.world  # 픽스처(같은 World — 모의 경로 끼움·대본 모의 공급사)

PDF_NAME = "synthetic-built.pdf"
OUTCOMES = ("found_", "none_")


def locate_data(world: World, run_id: int) -> dict[str, Any]:
    (step,) = [x for x in run_selectors.step_rows(company_id=world.company_a, run_id=run_id) if x.name == "locate"]
    assert step.status == "done" and isinstance(step.data, dict)
    return step.data  # pyright: ignore[reportReturnType]


def test_a_bound_run_on_a_built_pdf_fills_positions_and_puts_the_stats_in_the_locate_step(
    client: Client, world: World
) -> None:
    run_id = new_run(client, world, MINIMAL, content=sample_pdf(), name=PDF_NAME)
    execute(world, run_id)
    assert (run_of(world, run_id).status, run_of(world, run_id).error_code) == ("done", None)
    items = result_body(world, run_id)["items"]
    assert items  # 분모: 판정 문장이 있다
    found = [i for i in items if i["position"] is not None]
    assert found  # 좌표가 실제로 채워진다(G1b-2b 앞에는 전부 null)
    assert all(i["position"]["page"] == i["page"] and i["position"]["boxes"] for i in found)
    data = locate_data(world, run_id)
    assert data["positions"] == [i["position"] for i in items]
    stats = data["stats"]
    assert stats["opened"] == 1
    assert sum(v for k, v in stats.items() if k.startswith(OUTCOMES)) == len(items)
    assert sum(v for k, v in stats.items() if k.startswith("found_")) == len(found)


def test_resuming_a_run_failed_in_report_carries_the_locate_data_and_does_not_locate_again(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """★E: 이어 돌기(X1b-2b)는 끝난 단계를 새 실행으로 옮긴다 — locate data(stats 포함)도 그대로 옮겨진다."""

    def broken_build(*args: object, **kwargs: object) -> bytes:
        raise RuntimeError("지은 엑셀 오류")

    with monkeypatch.context() as patched:
        patched.setattr(colab.xlsx, "build", broken_build)
        previous = new_run(client, world, MINIMAL, content=sample_pdf(), name=PDF_NAME)
        execute(world, previous)
    failed = run_of(world, previous)
    assert (failed.status, failed.failed_step, failed.error_code) == ("failed", "report", "step_error")
    before = locate_data(world, previous)
    assert before["stats"]["opened"] == 1 and any(p is not None for p in before["positions"])

    calls: list[int] = []
    real_locate = PdfiumCoordinates.locate

    def counted(self: PdfiumCoordinates, pdf: bytes, page: int, sentence: str) -> Any:
        calls.append(page)
        return real_locate(self, pdf, page, sentence)

    monkeypatch.setattr(PdfiumCoordinates, "locate", counted)
    sent: list[dict[str, Any]] = []

    def enqueue(**kwargs: Any) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(hooks, "enqueue_run", enqueue)
    body = {"module": "greenwash", "documentId": failed.document_id, "resumeFromRunId": previous}
    with django_capture_on_commit_callbacks(execute=True):  # 옮긴 단계 파일(index 벡터)의 바이트는 실행기가 옮긴다(RC1)
        response = create(client, body)
    assert response.status_code == 201, response.content.decode()
    resumed = int(response.json()["id"])
    assert [x["run_id"] for x in sent] == [resumed]
    carried = locate_data(world, resumed)  # 실행 전: 단계 행이 done 으로 옮겨져 있다
    assert json.dumps(carried, sort_keys=True) == json.dumps(before, sort_keys=True)
    execute(world, resumed)
    run = run_of(world, resumed)
    assert (run.status, run.error_code) == ("done", None)
    assert calls == []  # 좌표를 다시 부르지 않는다(옮긴 단계는 돌지 않는다)
    assert json.dumps(locate_data(world, resumed), sort_keys=True) == json.dumps(before, sort_keys=True)
    assert [i["position"] for i in result_body(world, resumed)["items"]] == before["positions"]
