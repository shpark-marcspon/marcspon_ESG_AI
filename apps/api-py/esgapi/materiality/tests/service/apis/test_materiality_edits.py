# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""결과 글 칸 고침 경로 둘과 고친 판 GET 을 진짜 DB 로 잰다(밴드 IRS3 ② §4, 업무 층).

    GET  /materiality/runs/{run_id}/result/edits    고침 없음 → revision 0 · edits [] · 지금 값·원문·때·사람
    POST /materiality/runs/{run_id}/result/edits    처음 저장(머리 만듦 revision 1) · 둘째 · 낡은 base 409 · 같은 base
                                                    두 저장(앞 것 커밋 뒤) 하나 200·하나 409 · 거절 뒤 머리 0 · 되돌림
    GET  /materiality/runs/{run_id}/result          고친 판(1-1 항목 고침이 2-1 summary·1-1 title 둘 다) · 고침 0 이면
                                                    원본 본문 그대로
    run_results·run_files 행 수와 본문(이름·크기·저장 키)은 저장 앞뒤로 같다(RESULT_ROWS_SAME).
★ 실행은 실행기를 끝까지 돌린 진짜 실행이다(공급사는 모의 — 실제 호출 0). 묶음 규칙을 재는 시험은 결과 action 이 읽는
  결과 행의 본문을 지어낸 본문(tests/outputs/test_edits.edit_body)으로 바꿔 끼운다(행은 그대로 — 실행·회사 검사는 진짜).
"""

import dataclasses
from typing import Any

import pytest
from django.test import Client

from esgapi.materiality.contracts import shapes
from esgapi.materiality.models import MaterialityResultEditHeadRow
from esgapi.materiality.service.actions import result as result_actions
from esgapi.materiality.tests.flows.support import options
from esgapi.materiality.tests.flows.test_runs_materiality import World, done_run, new_run, result_body, run_of
from esgapi.materiality.tests.outputs.test_edits import G1, G1_MEMBERS, T0, at, edit_body
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.user.service.selectors.user import people_of
from tests.support.http import login

pytestmark = pytest.mark.django_db

DEF = f"{T0}/impact/rows/0/impactDefinition"


def edits_of(client: Client, run_id: int) -> Any:
    return client.get(f"/api/materiality/runs/{run_id}/result/edits")


def post(client: Client, run_id: int, base: int, changes: list[tuple[str, str | None]]) -> Any:
    body = {"baseRevision": base, "changes": [{"pointer": p, "value": v} for p, v in changes]}
    return client.post(f"/api/materiality/runs/{run_id}/result/edits", data=body, content_type="application/json")


def result_of(client: Client, run_id: int) -> Any:
    return client.get(f"/api/materiality/runs/{run_id}/result")


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def stored_rows(world: World, run_id: int) -> tuple[Any, ...]:
    results = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    files = run_selectors.run_files(company_id=world.company_a, run_id=run_id)
    return (
        [(r.position, r.schema_version, r.body) for r in results],
        [(f.step, f.name, f.size_bytes, f.storage_key, f.sha256) for f in files],
    )


def heads(world: World, run_id: int) -> int:
    """그 실행의 머리 행 수(주인 역할 — 거절 뒤 고아 머리 0 을 행으로 본다)."""
    return MaterialityResultEditHeadRow.for_company(world.company_a).filter(run_id=run_id).count()


def with_body(monkeypatch: pytest.MonkeyPatch, body: dict[str, Any]) -> None:
    """결과 action 이 읽는 @2 행의 본문을 지어낸 본문으로(행·실행은 진짜)."""
    real = run_selectors.run_results

    def swapped(*, company_id: int, run_id: int) -> tuple[run_selectors.RunResult, ...]:
        return tuple(
            dataclasses.replace(r, body=body) if r.schema_version == shapes.RESULT_SHAPE_V2 else r
            for r in real(company_id=company_id, run_id=run_id)
        )

    monkeypatch.setattr(result_actions.run_selectors, "run_results", swapped)


@pytest.fixture
def run_id(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> int:
    found = done_run(client, world, monkeypatch, options())
    with_body(monkeypatch, edit_body())
    return found


# ── GET edits ──


def test_no_edits_is_revision_0_and_the_result_is_the_stored_body(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    rid = done_run(client, world, monkeypatch, options())
    response = edits_of(client, rid)
    assert response.status_code == 200, response.content.decode()
    assert response.json() == {"schemaVersion": "materiality.result-edits@1", "revision": 0, "edits": []}
    assert result_of(client, rid).json() == result_body(world, rid)  # 고침 0 = 원본 본문 그대로


def test_a_real_run_edit_shows_in_the_result(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """지어낸 본문 없이 실행기의 결과 본문 그대로 — 첫 done impact 줄의 영향 정의를 고친다."""
    rid = done_run(client, world, monkeypatch, options())
    body = result_body(world, rid)
    target = next(
        f"/part2/topics/{t}/subtopics/{s}/impact/rows/0/impactDefinition"
        for t, topic in enumerate(body["part2"]["topics"])
        for s, sub in enumerate(topic["subtopics"])
        if sub["impact"]["status"] == "done" and sub["impact"]["rows"]
    )
    saved = post(client, rid, 0, [(target, "가상 고친 정의")])
    assert saved.status_code == 200, saved.content.decode()
    got = result_of(client, rid).json()
    assert at(got, target) == "가상 고친 정의"
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE_V2].validate_python(got, strict=True)


# ── POST ──


def test_first_and_second_save(client: Client, world: World, run_id: int) -> None:
    first = post(client, run_id, 0, [(DEF, "가상 첫 정의"), (f"{G1}/title", "가상 첫 제목")])
    assert first.status_code == 200, first.content.decode()
    assert first.json()["revision"] == 1
    user = run_of(world, run_id).created_by_user_id
    name = people_of(world.company_a, {user})[user][1]
    edits = first.json()["edits"]
    assert [(e["pointer"], e["value"], e["original"], e["editedBy"]) for e in edits] == [
        (DEF, "가상 첫 정의", "가상 영향 정의 하나", {"name": name}),
        (f"{G1}/title", "가상 첫 제목", "가상 규정 A", {"name": name}),
    ]
    assert all(e["editedAt"].endswith("+09:00") for e in edits)
    second = post(client, run_id, 1, [(DEF, "가상 둘째 정의")])
    assert second.status_code == 200
    assert second.json()["revision"] == 2
    assert [e["value"] for e in second.json()["edits"]] == ["가상 둘째 정의", "가상 첫 제목"]
    assert edits_of(client, run_id).json() == second.json()


def test_a_stale_base_revision_is_409_with_the_current_revision(client: Client, run_id: int) -> None:
    assert post(client, run_id, 0, [(DEF, "가")]).status_code == 200
    stale = post(client, run_id, 0, [(f"{G1}/title", "나")])
    assert code(stale) == (409, "EDIT_CONFLICT")
    assert "revision 1" in stale.json()["error"]["message"]
    ahead = post(client, run_id, 5, [(f"{G1}/title", "나")])
    assert code(ahead) == (409, "EDIT_CONFLICT")
    assert edits_of(client, run_id).json()["revision"] == 1
    assert [e["value"] for e in edits_of(client, run_id).json()["edits"]] == ["가"]


def test_two_saves_from_the_same_revision_one_wins(client: Client, run_id: int) -> None:
    """P8: 같은 baseRevision 두 저장(앞 것 커밋 뒤 둘째) → 하나 200·하나 409, 고침 행은 앞 것의 몫만."""
    other = Client()
    login(other)  # 같은 회사의 둘째 세션
    assert edits_of(other, run_id).json()["revision"] == 0
    first = post(client, run_id, 0, [(DEF, "가상 앞 저장")])
    late = post(other, run_id, 0, [(f"{G1}/summary", "가상 뒤 저장")])
    assert first.status_code == 200
    assert code(late) == (409, "EDIT_CONFLICT")
    state = edits_of(client, run_id).json()
    assert state["revision"] == 1
    assert [e["pointer"] for e in state["edits"]] == [DEF]


def test_a_first_save_with_a_nonzero_base_makes_no_head(client: Client, world: World, run_id: int) -> None:
    """P10b: 머리가 없고 base ≠ 0 이면 머리를 만들기 전에 409 — 머리 행 0(선검사·되돌림 둘 다 빠지면 고아 머리)."""
    assert code(post(client, run_id, 3, [(DEF, "가")])) == (409, "EDIT_CONFLICT")
    assert heads(world, run_id) == 0
    assert edits_of(client, run_id).json()["revision"] == 0
    assert post(client, run_id, 0, [(DEF, "가")]).json()["revision"] == 1  # 머리가 없었다 — 0 에서 시작


def test_a_refused_first_save_leaves_no_head(client: Client, world: World, run_id: int) -> None:
    refused = post(client, run_id, 0, [(DEF, "가"), (f"{T0}/impact/rows/0/impactType", "긍정")])
    assert code(refused) == (400, "INVALID_EDIT")
    assert refused.json()["error"]["message"].startswith("2번째 고침")
    assert edits_of(client, run_id).json() == {
        "schemaVersion": "materiality.result-edits@1",
        "revision": 0,
        "edits": [],
    }
    assert heads(world, run_id) == 0
    assert post(client, run_id, 1, [(DEF, "가")]).status_code == 409  # 머리 0 — base 1 은 낡음
    assert heads(world, run_id) == 0


@pytest.mark.parametrize(
    "changes",
    [
        [],
        [{"pointer": DEF}],
        [{"pointer": DEF, "value": 1}],
        [{"pointer": DEF, "value": "가", "extra": 1}],
        [{"pointer": DEF, "value": "가"}] * 201,
    ],
    ids=["none", "no-value", "number", "extra-key", "201"],
)
def test_a_body_out_of_shape_is_422(client: Client, run_id: int, changes: list[Any]) -> None:
    response = client.post(
        f"/api/materiality/runs/{run_id}/result/edits",
        data={"baseRevision": 0, "changes": changes},
        content_type="application/json",
    )
    assert response.status_code == 422, response.content.decode()
    assert edits_of(client, run_id).json()["revision"] == 0


def test_a_revert_drops_out_of_edits_but_keeps_the_row(client: Client, run_id: int) -> None:
    post(client, run_id, 0, [(DEF, "가상 고침")])
    reverted = post(client, run_id, 1, [(DEF, "가상 영향 정의 하나")])
    assert reverted.json() == {"schemaVersion": "materiality.result-edits@1", "revision": 2, "edits": []}
    assert at(result_of(client, run_id).json(), DEF) == "가상 영향 정의 하나"


def test_a_shortlist_item_edit_shows_in_the_2_1_summary_and_the_1_1_title(client: Client, run_id: int) -> None:
    """P9: GET result 는 고친 판 — 1-1 항목 하나 고침이 묶음 전부(2-1 context·재무·pathway 사본)에."""
    post(
        client,
        run_id,
        0,
        [(f"{T0}/financial/rows/0/context/regulations/0/summary", "가상 고친 요약"), (f"{G1}/title", "가상 고친 제목")],
    )
    got = result_of(client, run_id).json()
    for member in G1_MEMBERS:
        assert at(got, f"{member}/summary") == "가상 고친 요약"
        assert at(got, f"{member}/title") == "가상 고친 제목"
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE_V2].validate_python(got, strict=True)
    assert (
        got["part2"]["topics"][0]["subtopics"][0]["impact"]["parsed"]
        == edit_body()["part2"]["topics"][0]["subtopics"][0]["impact"]["parsed"]
    )


# ── 갈래 ──


def test_not_done_another_module_and_missing_runs(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    queued = new_run(client, options())
    assert code(edits_of(client, queued)) == (409, "RUN_NOT_DONE")
    assert code(post(client, queued, 0, [(DEF, "가")])) == (409, "RUN_NOT_DONE")
    rid = done_run(client, world, monkeypatch, options())
    for missing in (rid + 1000,):
        assert code(edits_of(client, missing)) == (404, "NOT_FOUND")
        assert code(post(client, missing, 0, [(DEF, "가")])) == (404, "NOT_FOUND")
    real = run_selectors.find_run

    def other_module(*, company_id: int, run_id: int) -> run_selectors.Run | None:
        run = real(company_id=company_id, run_id=run_id)
        return None if run is None else dataclasses.replace(run, module="dataverify")

    monkeypatch.setattr(result_actions.run_selectors, "find_run", other_module)
    assert code(edits_of(client, rid)) == (404, "NOT_FOUND")
    assert code(post(client, rid, 0, [(DEF, "가")])) == (404, "NOT_FOUND")


def test_another_company_cannot_edit_or_read(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """P10: 남의 회사 실행 = 없는 실행(업무 층). 저장은 회사 A 의 고침을 남기지 않는다."""
    rid = done_run(client, world, monkeypatch, options())
    with_body(monkeypatch, edit_body())
    other = Client()
    login(other, tenant_id="tenant-b")
    assert code(edits_of(other, rid)) == (404, "NOT_FOUND")
    assert code(post(other, rid, 0, [(DEF, "가상 남의 고침")])) == (404, "NOT_FOUND")
    assert edits_of(client, rid).json()["revision"] == 0
    assert at(result_of(client, rid).json(), DEF) == "가상 영향 정의 하나"


def test_saving_keeps_the_stored_results_and_files(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RESULT_ROWS_SAME: run_results 행·본문, run_files 행(이름·크기·저장 키·sha256)은 저장 앞뒤로 같다."""
    rid = done_run(client, world, monkeypatch, options())
    before = stored_rows(world, rid)
    with_body(monkeypatch, edit_body())
    post(client, rid, 0, [(DEF, "가")])
    post(client, rid, 1, [(f"{G1}/url", "https://example.com/가상/새")])
    monkeypatch.undo()
    assert stored_rows(world, rid) == before
