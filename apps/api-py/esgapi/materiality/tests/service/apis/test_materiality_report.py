# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""고친 판 최종 엑셀 GET /materiality/runs/{run_id}/report 를 진짜 DB 로 잰다(밴드 IRS3 ③ §4, 업무 층).

    고친 칸이 2-1 Q · 2-2 S · 1-1 F 에 · RAW_JSON = 고친 판(GET result 와 같은 말) · 고침 0 이면 ★B(저장본과 시트 셋 칸
    값 같음, RAW_JSON 은 json.loads 같음 — xlsx_cell_truncated 경고 차이만) · 감사 download 한 줄(거절은 0) · 404/409
★ 실행은 실행기를 끝까지 돌린 진짜 실행이다(공급사는 모의 — 실제 호출 0). 칸 자리를 재는 시험은 결과 행의 본문을 지어낸
  본문(tests/outputs/test_edits.edit_body)으로 바꿔 끼운다.
"""

import io
import json
from typing import Any

import pytest
from django.test import Client
from openpyxl import load_workbook

from esgapi.core.models import AuditEventRow
from esgapi.materiality.outputs import final_xlsx
from esgapi.materiality.tests.flows.support import options
from esgapi.materiality.tests.flows.test_runs_materiality import World, done_run, new_run, result_body, run_of, stored
from esgapi.materiality.tests.outputs.test_edits import G1, T0, edit_body
from esgapi.materiality.tests.service.apis.test_materiality_edits import post, with_body
from tests.support.http import login

pytestmark = pytest.mark.django_db

SHEETS = [final_xlsx.SHORTLIST, final_xlsx.SOC_SHEET, final_xlsx.FIN_SHEET, final_xlsx.RAW_JSON]


def report(client: Client, run_id: int) -> Any:
    return client.get(f"/api/materiality/runs/{run_id}/report")


def book_of(content: bytes) -> dict[str, list[list[Any]]]:
    book = load_workbook(io.BytesIO(content))
    assert book.sheetnames == SHEETS
    return {ws.title: [list(row) for row in ws.iter_rows(values_only=True)] for ws in book.worksheets}


def cell(content: bytes, sheet: str, ref: str) -> Any:
    return load_workbook(io.BytesIO(content))[sheet][ref].value


def raw_json(content: bytes) -> dict[str, Any]:
    raw = load_workbook(io.BytesIO(content))[final_xlsx.RAW_JSON]
    return final_xlsx.raw_json_text([str(raw.cell(row=r, column=1).value) for r in range(1, raw.max_row + 1)])


def downloads(world: World) -> list[tuple[Any, ...]]:
    rows = AuditEventRow.for_company(world.company_a).filter(action="download").order_by("id")
    return [(r.action, r.event, r.result, r.target_kind, r.target_id, r.target_label) for r in rows]


def test_edited_cells_land_in_2_1_q_2_2_s_and_1_1_f(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P11: 엑셀은 고친 판으로 짓는다."""
    run_id = done_run(client, world, monkeypatch, options())
    with_body(monkeypatch, edit_body())
    saved = post(
        client,
        run_id,
        0,
        [
            (f"{T0}/impact/rows/0/impactDefinition", "가상 고친 정의"),
            (f"{T0}/pathway/rows/0/impactDriver", "가상 고친 동인"),
            (f"{G1}/title", "가상 고친 제목"),
        ],
    )
    assert saved.status_code == 200, saved.content.decode()
    response = report(client, run_id)
    assert response.status_code == 200, response.content.decode()
    assert response["Content-Type"] == final_xlsx.MEDIA
    assert response["Content-Disposition"] == 'attachment; filename="materiality-final-report.xlsx"'
    content = response.content
    assert cell(content, final_xlsx.SOC_SHEET, "Q6") == "가상 고친 정의"
    assert cell(content, final_xlsx.FIN_SHEET, "S6") == "가상 고친 동인"
    f5 = cell(content, final_xlsx.SHORTLIST, "F5")
    assert isinstance(f5, str)
    assert f5.startswith("1) [환경·사회·재무] 제목: 가상 고친 제목\n")
    assert "가상 규정 A" not in f5.split("\n")[0]


def test_raw_json_is_the_edited_result(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """P13·Q8 가: RAW_JSON 시트 = 고친 판(GET result 와 같은 말). parsed 의 AI 원문은 남는다."""
    run_id = done_run(client, world, monkeypatch, options())
    with_body(monkeypatch, edit_body())
    post(client, run_id, 0, [(f"{T0}/impact/rows/0/impactDefinition", "가상 고친 정의")])
    content = report(client, run_id).content
    shown = client.get(f"/api/materiality/runs/{run_id}/result").json()
    got = raw_json(content)
    assert got == shown
    assert got["part2"]["topics"][0]["subtopics"][0]["impact"]["rows"][0]["impactDefinition"] == "가상 고친 정의"
    assert got["part2"]["topics"][0]["subtopics"][0]["impact"]["parsed"] == {
        "impacts": [{"impact_definition": "가상 영향 정의 하나"}]
    }
    assert next(iter(got)) == "schemaVersion"  # ★A 열쇠 차례 되살림(dump_v2)


def test_without_edits_the_report_matches_the_stored_file(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """★B: 고침 0 — 새 경로 엑셀과 실행 끝에 저장한 엑셀은 시트 셋 칸 값이 같고, RAW_JSON 은 json.loads 같음(저장본의
    RAW_JSON 은 xlsx_cell_truncated 경고 전의 판 — 경고 차이만 허락)."""
    run_id = done_run(client, world, monkeypatch, options())
    fresh = report(client, run_id).content
    saved = stored(world, run_id, step=None, name=final_xlsx.FILENAME)
    a, b = book_of(fresh), book_of(saved)
    for sheet in SHEETS[:3]:
        assert a[sheet] == b[sheet], sheet
    body = result_body(world, run_id)
    without_cut = [w for w in body["warnings"] if w["code"] != "xlsx_cell_truncated"]
    assert raw_json(saved) == {**body, "warnings": without_cut}
    assert raw_json(fresh) == body
    assert json.loads(json.dumps(raw_json(fresh))) == raw_json(fresh)


def test_one_download_audit_row_per_report(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """P12: 내려받을 때마다 감사 download 한 줄(target report · 파일 이름). 거절(404·409)은 0 줄."""
    run_id = done_run(client, world, monkeypatch, options())
    queued = new_run(client, options())
    assert report(client, run_id + 1000).status_code == 404
    assert report(client, queued).status_code == 409
    assert downloads(world) == []
    assert report(client, run_id).status_code == 200
    assert report(client, run_id).status_code == 200
    row = ("download", "materiality_report_downloaded", "success", "report", run_id, final_xlsx.FILENAME)
    assert downloads(world) == [row, row]
    actor = AuditEventRow.for_company(world.company_a).filter(action="download").first()
    assert actor is not None
    assert actor.actor_user_id == run_of(world, run_id).created_by_user_id


def test_refusals(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = done_run(client, world, monkeypatch, options())
    queued = new_run(client, options())
    response = report(client, queued)
    assert (response.status_code, response.json()["error"]["code"]) == (409, "RUN_NOT_DONE")
    other = Client()
    login(other, tenant_id="tenant-b")
    hidden, missing = report(other, run_id), report(other, run_id + 1000)
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert hidden.content == missing.content
    assert downloads(world) == []


def raw_text(content: bytes) -> str:
    raw = load_workbook(io.BytesIO(content))[final_xlsx.RAW_JSON]
    return "".join(str(raw.cell(row=r, column=1).value) for r in range(1, raw.max_row + 1))


def key_order(value: Any) -> Any:
    """dict 의 열쇠 차례를 목록으로(값 비교와 따로 차례만 견준다). parsed(모델 원문 JSON — 꼴이 없는 칸)의 안쪽은 jsonb
    차례 그대로라(발주서 ★A 「parsed 안 차례만 다른지」) 보지 않는다."""
    if isinstance(value, dict):
        return [(k, None if k == "parsed" else key_order(v)) for k, v in value.items()]
    if isinstance(value, list):
        return [key_order(v) for v in value]
    return None


def test_raw_json_keeps_the_shape_key_order_of_a_stored_run(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P14·★A(검증 ③ B2): 진짜 DB(jsonb)에 저장한 실행 본문으로 — RAW_JSON 의 열쇠 차례가 실행 끝의 AI 원본 엑셀과 같다
    (jsonb 왕복은 part1 을 앞으로 보낸다 — 받은 dict 를 그대로 덤프하면 빨강). parsed 안쪽만 jsonb 차례(★A). 고친 뒤에도
    차례는 같고 값만 바뀐다."""
    run_id = done_run(client, world, monkeypatch, options())
    body = result_body(world, run_id)
    assert next(iter(body)) != "schemaVersion"  # 분모: DB 왕복 본문은 정말 차례가 바뀌어 있다
    assert [w for w in body["warnings"] if w["code"] == "xlsx_cell_truncated"] == []  # 저장본 RAW_JSON 과 같은 판
    saved = stored(world, run_id, step=None, name=final_xlsx.FILENAME)
    fresh = report(client, run_id).content
    assert json.loads(raw_text(fresh)) == json.loads(raw_text(saved))  # 값 같음(고침 0)
    assert key_order(json.loads(raw_text(fresh))) == key_order(json.loads(raw_text(saved)))  # parsed 밖 차례 같음
    assert next(iter(json.loads(raw_text(fresh)))) == "schemaVersion"
    target = next(
        f"/part2/topics/{t}/subtopics/{s}/impact/rows/0/impactDefinition"
        for t, topic in enumerate(body["part2"]["topics"])
        for s, sub in enumerate(topic["subtopics"])
        if sub["impact"]["status"] == "done" and sub["impact"]["rows"]
    )
    assert post(client, run_id, 0, [(target, "가상 고친 정의")]).status_code == 200
    edited = report(client, run_id).content
    assert key_order(json.loads(raw_text(edited))) == key_order(json.loads(raw_text(saved)))
    assert raw_text(edited) != raw_text(saved)
    assert "가상 고친 정의" in raw_text(edited)
