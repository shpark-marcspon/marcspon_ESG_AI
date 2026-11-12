# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""S3Q1 ① 원본 경로 GET /inventory/scope3/runs/{id}/original(service/apis/scope3_runs.py — 발주서 Q1~Q4)를 진짜 DB 로
잰다. 업무 층.

    받기   두 역할 200 · 바이트 sha256 = 올린 바이트 · 올린 이름 그대로(한글 RFC 6266) · 꼴 xlsx·xls·그 밖 · nosniff ·
           실행 상태를 보지 않는다(queued 도 200) · 감사 줄 하나(download · document_downloaded · module)
    출처   결과 경로가 활동·에너지 줄 factor 에 sourceText 를 더한다(읽을 때 — 저장 본문은 그대로, 계약 strict)
    거절   남의 회사·없음·Scope 3 아님·문서 null·안 올라옴·저장소에 원본 없음 404(본문에 원본 0) · 저장소 없음·거부·
           닿지 못함 503 · 상한 넘음·올림 뒤 바뀜 409 · 세션 없이 401
올리기는 실제 /documents 길(가짜 저장소), 실행은 POST /runs(실행기를 돌리지 않는다 — 원본은 실행 전에도 있다).
바이트는 지어낸 것(엑셀로 열지 않는다 — 서버는 바이트를 그대로 낸다).
"""

import hashlib
from typing import Any

import pytest
from django.apps import apps
from django.test import Client

from esgapi.core.resources.ports.storage import StorageDenied, StorageUnavailable
from esgapi.core.service.services import documents as document_services
from esgapi.inventory.contracts.shapes import RESULT_SHAPES
from esgapi.inventory.service.utils import scope3_sources
from esgapi.inventory.tests.flows.test_binding_157_end_to_end import (
    World,
    body_of,
    operator,
    post_run,
    work_company,
    world,
)
from esgapi.inventory.tests.service.apis.test_scope3_runs import done_row, done_run, result_url, stored
from tests.support.http import login

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (world, work_company)

ORIGINAL = b"PK\x03\x04 gaesang-original-bytes \x00\xff"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def url(run_id: int) -> str:
    return f"/api/inventory/scope3/runs/{run_id}/original"


def model(app: str, name: str) -> Any:
    return apps.get_model(app, name)


def upload_named(client: Client, world: World, name: str, content: bytes = ORIGINAL) -> int:
    """웹의 uploadDocument 와 같은 길(이름만 고름). 문서 id."""
    made = client.post(
        "/api/documents", data={"fileName": name, "sizeBytes": len(content)}, content_type="application/json"
    )
    assert made.status_code == 201, made.content.decode()
    document_id: int = made.json()["document"]["id"]
    world.storage.put(model("core", "DocumentRow").unscoped.get(pk=document_id).storage_key, content)
    confirmed = client.post(f"/api/documents/{document_id}/confirm")
    assert confirmed.status_code == 200, confirmed.content.decode()
    return document_id


def made_run(client: Client, world: World, name: str = "가상_원본.xlsx") -> tuple[int, int]:
    """고객사 사용자가 올리고 만든 Scope 3 실행(queued — 돌리지 않음). (실행 id, 문서 id)."""
    login(client)
    document_id = upload_named(client, world, name)
    made = post_run(client, body_of(document_id, {"reportYear": 2025}))
    assert made.status_code == 201, made.content.decode()
    return int(made.json()["id"]), document_id


def downloads(company_id: int) -> list[tuple[str, int | None, str | None, Any]]:
    lines = model("core", "AuditEventRow").for_company(company_id).filter(action="download")
    return [(r.event, r.target_id, r.target_label, r.detail) for r in lines]


def storage_key(document_id: int) -> str:
    return str(model("core", "DocumentRow").unscoped.get(pk=document_id).storage_key)


# ── 받기 ──


def test_both_roles_download_the_uploaded_bytes_with_its_name_and_three_headers(
    client: Client, world: World, work_company: None
) -> None:
    run_id, document_id = made_run(client, world)
    mine = client.get(url(run_id))
    assert mine.status_code == 200, mine.content.decode()
    assert hashlib.sha256(mine.content).hexdigest() == hashlib.sha256(ORIGINAL).hexdigest()
    assert mine["Content-Type"] == XLSX
    assert mine["Content-Disposition"] == "attachment; filename*=utf-8''%EA%B0%80%EC%83%81_%EC%9B%90%EB%B3%B8.xlsx"
    assert mine["X-Content-Type-Options"] == "nosniff"
    theirs = Client().get(url(run_id), **operator())
    assert (theirs.status_code, theirs.content) == (200, ORIGINAL)
    assert (
        downloads(world.company_a)
        == [
            ("document_downloaded", document_id, "가상_원본.xlsx", {"module": "inventory.scope3"}),
        ]
        * 2
    )


@pytest.mark.parametrize(
    ("name", "media_type", "disposition"),
    [
        ("plain.XLS", "application/vnd.ms-excel", 'attachment; filename="plain.XLS"'),
        ("가상.csv", "application/octet-stream", "attachment; filename*=utf-8''%EA%B0%80%EC%83%81.csv"),
        ("noext", "application/octet-stream", 'attachment; filename="noext"'),
    ],
)
def test_the_media_type_follows_the_uploaded_name(
    client: Client, world: World, name: str, media_type: str, disposition: str
) -> None:
    run_id, _ = made_run(client, world, name)
    got = client.get(url(run_id))
    assert (got.status_code, got["Content-Type"], got["Content-Disposition"], got.content) == (
        200,
        media_type,
        disposition,
        ORIGINAL,
    )


def test_a_retried_run_on_the_same_document_gives_the_same_original(client: Client, world: World) -> None:
    run_id, document_id = made_run(client, world)
    again = post_run(client, body_of(document_id, {"reportYear": 2025}))
    assert again.status_code == 201
    assert client.get(url(int(again.json()["id"]))).content == client.get(url(run_id)).content == ORIGINAL


# ── 거절 ──


def test_another_companys_run_and_a_missing_run_are_404_without_the_bytes(client: Client, world: World) -> None:
    run_id, _ = made_run(client, world)
    login(theirs := Client(), tenant_id="tenant-b")
    for target in (run_id, run_id + 1000):
        got = theirs.get(url(target))
        assert got.status_code == 404
        assert ORIGINAL not in got.content
    assert downloads(world.company_a) == []


def test_a_run_of_another_module_on_the_same_document_is_404(client: Client, world: World) -> None:
    _, document_id = made_run(client, world)
    run = (
        model("runs", "RunRow")
        .for_company(world.company_a)
        .create(
            company_id=world.company_a,
            document_id=document_id,
            module="dataverify",
            flow_id="dataverify.colab@156",
            options={},
            versions={},
            status="queued",
            created_by_user_id=1,
        )
    )
    assert client.get(url(int(run.pk))).status_code == 404


def test_a_run_without_a_document_is_404(client: Client, world: World) -> None:
    login(client)
    run_id = done_row(world.company_a, 1, ("scope3.colab.result@1",))
    got = client.get(url(run_id))
    assert (got.status_code, got.json()["error"]["code"]) == (404, "NOT_FOUND")


def test_a_missing_object_is_404(client: Client, world: World) -> None:
    run_id, document_id = made_run(client, world)
    world.storage.objects.pop(storage_key(document_id))
    got = client.get(url(run_id))
    assert (got.status_code, got.json()["error"]["code"]) == (404, "NOT_FOUND")


def test_a_document_not_uploaded_is_404_even_with_the_object_in_storage(client: Client, world: World) -> None:
    """원본은 저장소에 그대로 두고 문서 행만 올림 전으로 — 상태를 보지 않으면 바이트가 나간다(검증 V1)."""
    run_id, document_id = made_run(client, world)
    assert client.get(url(run_id)).status_code == 200  # 분모: 같은 실행이 올림 확인 뒤엔 200
    model("core", "DocumentRow").unscoped.filter(pk=document_id).update(status="awaiting_upload")
    got = client.get(url(run_id))
    assert (got.status_code, got.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert ORIGINAL not in got.content


@pytest.mark.parametrize(
    ("broken", "code"),
    [(StorageDenied("가상 거부"), "STORAGE_DENIED"), (StorageUnavailable("가상 끊김"), "STORAGE_UNAVAILABLE")],
)
def test_a_failing_storage_is_503(client: Client, world: World, broken: Any, code: str) -> None:
    run_id, _ = made_run(client, world)
    world.storage.fail_with = broken
    got = client.get(url(run_id))
    assert (got.status_code, got.json()["error"]["code"]) == (503, code)


def test_no_storage_is_503(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id, _ = made_run(client, world)
    monkeypatch.setattr(document_services, "default_storage", lambda: None)
    got = client.get(url(run_id))
    assert (got.status_code, got.json()["error"]["code"]) == (503, "STORAGE_UNCONFIGURED")


def test_too_large_and_changed_after_confirm_are_409(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, document_id = made_run(client, world)
    world.storage.put(storage_key(document_id), ORIGINAL + b"!")  # 올림 확인 뒤 같은 키에 다시(ETag 다름)
    got = client.get(url(run_id))
    assert (got.status_code, got.json()["error"]["code"]) == (409, "OBJECT_CHANGED")
    assert ORIGINAL not in got.content
    monkeypatch.setattr(document_services, "max_upload_bytes", lambda: 3)
    got = client.get(url(run_id))
    assert (got.status_code, got.json()["error"]["code"]) == (409, "OBJECT_TOO_LARGE")
    assert downloads(world.company_a) == []


def test_without_a_session_it_is_401(client: Client, world: World) -> None:
    run_id, _ = made_run(client, world)
    assert Client().get(url(run_id)).status_code == 401


# ── 결과 경로의 출처 글(S3Q1 ③ — Q9) ──


def factor_rows(body: Any) -> list[dict[str, Any]]:
    return [
        r
        for s in body.get("sheets", [])
        if s.get("status") == "processed"
        for r in s["rows"]
        if r["kind"] != "purchase" and isinstance(r.get("factor"), dict)
    ]


def test_the_result_adds_source_text_when_read_and_keeps_the_stored_body(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = done_run(client, world)
    monkeypatch.setattr(scope3_sources, "packaged_sources", scope3_sources.SourceTexts)
    plain = client.get(result_url(run_id)).json()
    assert plain == stored(world, run_id)  # 글 표가 비면 본문 그대로
    sheets = sorted({r["factor"]["sheet"] for r in factor_rows(plain)})
    assert sheets  # 분모: 활동·에너지 줄이 있다
    texts = scope3_sources.SourceTexts({sheet: f"가상 출처 {sheet}" for sheet in sheets})
    monkeypatch.setattr(scope3_sources, "packaged_sources", lambda: texts)
    got = client.get(result_url(run_id)).json()
    RESULT_SHAPES["scope3.colab.result@1"].validate_python(got, strict=True)
    assert [r["factor"]["sourceText"] for r in factor_rows(got)] == [
        f"가상 출처 {r['factor']['sheet']}" for r in factor_rows(plain)
    ]
    assert "sourceText" not in str(stored(world, run_id))  # 저장 본문에는 없다(엔진 0줄)
