# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""S3R2 T4: 결과 줄의 입력 칸 `input` 을 경로 GET /inventory/scope3/runs/{id}/result 로 잰다(진짜 DB). 업무 층.

    새 실행    실행기가 끝까지 돌린 실행의 본문 — processed 줄마다 `input`(키 열여섯, 맨 끝) · 계약 꼴 strict
    옛 결과    `input` 이 없는 옛 꼴 결과 행을 직접 심은 done 실행 — 200 · 본문 바이트 = 그 행을 렌더러로 적은 바이트
               (응답 검사를 지나며 칸이 생기거나 바뀌지 않음 — 기대는 새 실행의 응답 본문에서 input 만 뗀 것)
               · `"input"` 글자 0
    옛 에너지 줄  C3 시트(에너지 줄 꼴 ColabEnergyRowJson)가 든 실행으로 같은 옛 결과 읽기(R4)
    남의 회사  B 가 A 의 옛 꼴 실행 id 로 읽으면 없는 id 와 바이트까지 같은 404
    키 열다섯  S3R3 앞(093f16c3~)에 저장된 `input` 키 열다섯(useMonths 없음) 결과 — 200 · 바이트 그대로
               (useMonths 가 생기지 않음, 감독 처분 Q3 NotRequired)
실행은 test_scope3_runs(= test_binding_157_end_to_end)의 짜임 그대로. 옛 결과는 다시 셈하지 않는다(처분 Q11).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.test import Client

from esgapi.config.api import api
from esgapi.inventory.contracts.shapes import RESULT_SHAPES
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    INPUT_KEYS,
    c3_sheet,
    energy_factor_sheets,
    sheet,
    transport_ef_sheet,
    workbook,
    xlsx_bytes,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS
from esgapi.inventory.tests.flows.test_binding_157_end_to_end import World, work_company, world
from esgapi.inventory.tests.service.apis.test_scope3_runs import done_run, result_url, runs_model, stored
from tests.support.http import login

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (world, work_company)  # 고정물을 이 모듈에서도 이름으로 찾게
SHAPE = "scope3.colab.result@1"
ENERGY_TEMPLATE = xlsx_bytes(workbook(c3_sheet(), sheet("표지", {1: ["가상"]})))
ENERGY_BOOK = xlsx_bytes(workbook(sheet("구매_USEPA", BOOK_ROWS), transport_ef_sheet(), *energy_factor_sheets()))


def without_input(body: dict[str, Any]) -> dict[str, Any]:
    sheets = [
        {**s, "rows": [{k: v for k, v in row.items() if k != "input"} for row in s["rows"]]} if "rows" in s else s
        for s in body["sheets"]
    ]
    return {**body, "sheets": sheets}


def planted_old_run(company_id: int, created_by: int, body: dict[str, Any]) -> int:
    """`input` 칸 전에 저장된 꼴의 결과 행 하나를 가진 done 실행(실행기로는 이제 만들 수 없는 꼴)."""
    at = datetime(2026, 10, 1, tzinfo=UTC)
    made = (
        runs_model("RunRow")
        .for_company(company_id)
        .create(
            company_id=company_id,
            module="inventory.scope3",
            flow_id="scope3.colab@157",
            options={},
            versions={},
            status="done",
            created_by_user_id=created_by,
            started_at=at,
            finished_at=at + timedelta(seconds=30),
        )
    )
    runs_model("RunResultRow").for_company(company_id).create(
        company_id=company_id, run_id=made.pk, position=0, schema_version=SHAPE, body=body
    )
    return int(made.pk)


def _fifteen(cells: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in cells.items() if k != "useMonths"}


def without_use_months(body: dict[str, Any]) -> dict[str, Any]:
    """S3R3 앞 꼴: 줄의 `input` 에서 useMonths 만 뗀다(키 열다섯)."""
    sheets = [
        {**s, "rows": [{**row, "input": _fifteen(row["input"])} for row in s["rows"]]} if "rows" in s else s
        for s in body["sheets"]
    ]
    return {**body, "sheets": sheets}


def processed_rows(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for s in body["sheets"] if s["status"] == "processed" for row in s["rows"]]


def test_a_new_run_carries_input_on_every_row(client: Client, world: World, work_company: None) -> None:
    run_id = done_run(client, world)
    shown = client.get(result_url(run_id))
    assert shown.status_code == 200, shown.content.decode()
    body = shown.json()
    assert body == stored(world, run_id)
    rows = processed_rows(body)
    assert rows
    assert all(list(row)[-1] == "input" and list(row["input"]) == list(INPUT_KEYS) for row in rows)
    assert any(value is not None for row in rows for value in row["input"].values())
    RESULT_SHAPES[SHAPE].validate_python(body, strict=True)


def test_an_old_result_without_input_reads_as_stored_bytes(client: Client, world: World, work_company: None) -> None:
    new_id = done_run(client, world)
    # 응답 본문(계약 꼴의 키 차례 — 저장 행은 jsonb 라 차례가 다르다)에서 input 만 뗀 것 = input 칸 전의 응답
    new_body = client.get(result_url(new_id)).json()
    old = without_input(new_body)
    assert processed_rows(old) and all("input" not in row for row in processed_rows(old))
    created_by = int(login(client)["user"]["id"])
    old_id = planted_old_run(world.company_a, created_by, old)
    shown = client.get(result_url(old_id))
    assert shown.status_code == 200, shown.content.decode()
    assert shown.content == api.renderer.render(shown.wsgi_request, old, response_status=200).encode()
    assert b'"input"' not in shown.content
    assert shown.json() == old


def test_an_old_energy_result_without_input_reads_as_stored_bytes(
    client: Client, world: World, work_company: None
) -> None:
    """R4: 에너지 줄 꼴(ColabEnergyRowJson)의 옛 결과 — C3 시트가 든 실행의 응답에서 input 만 뗀 본문."""
    world.book = ENERGY_BOOK
    new_id = done_run(client, world, content=ENERGY_TEMPLATE)
    new_body = client.get(result_url(new_id)).json()
    energy = [row for row in processed_rows(new_body) if row["kind"] == "fuel_energy"]
    assert energy and all(list(row)[-1] == "input" for row in energy)
    old = without_input(new_body)
    created_by = int(login(client)["user"]["id"])
    old_id = planted_old_run(world.company_a, created_by, old)
    shown = client.get(result_url(old_id))
    assert shown.status_code == 200, shown.content.decode()
    assert shown.content == api.renderer.render(shown.wsgi_request, old, response_status=200).encode()
    assert b'"input"' not in shown.content


def test_another_company_reading_an_old_result_is_the_same_404_as_a_missing_id(
    client: Client, world: World, work_company: None
) -> None:
    new_id = done_run(client, world)
    created_by = int(login(client)["user"]["id"])
    old_id = planted_old_run(world.company_a, created_by, without_input(stored(world, new_id)))
    assert client.get(result_url(old_id)).status_code == 200
    theirs = Client()
    login(theirs, sub="b-user", tenant_id="tenant-b")
    hidden = theirs.get(result_url(old_id))
    missing = theirs.get(result_url(old_id + 1000))
    assert (hidden.status_code, missing.status_code) == (404, 404)
    assert hidden.content == missing.content


def test_a_fifteen_key_input_result_saved_before_s3r3_reads_as_stored_bytes(
    client: Client, world: World, work_company: None
) -> None:
    """S3R3(감독 처분 Q3): `input` 키 열다섯으로 저장된 결과 — 응답 검사를 지나 200, useMonths 가 생기지 않고
    바이트 그대로."""
    new_id = done_run(client, world)
    new_body = client.get(result_url(new_id)).json()
    assert all(list(row["input"])[-1] == "useMonths" for row in processed_rows(new_body))
    fifteen = without_use_months(new_body)
    assert processed_rows(fifteen) and all(len(row["input"]) == 15 for row in processed_rows(fifteen))
    created_by = int(login(client)["user"]["id"])
    old_id = planted_old_run(world.company_a, created_by, fifteen)
    shown = client.get(result_url(old_id))
    assert shown.status_code == 200, shown.content.decode()
    assert shown.content == api.renderer.render(shown.wsgi_request, fifteen, response_status=200).encode()
    assert b'"useMonths"' not in shown.content
    assert shown.json() == fifteen
