"""감사 기록 쓰기(core/service/services/audit.py 의 record_event — AU1a)를 진짜 DB 로 잰다. 업무 층(주인 역할,
테스트마다 되돌린다).

재는 것: 칸 그대로 한 줄 · 회사 없는 줄(이름 붙은 입구) · 꼴 밖은 행 0 의 값 · 업무 블록 안에서 불러도 던지지 않음 ·
DB 가 거절해도(처분 ⑱) 값으로 돌아오고 바깥 블록의 업무 쓰기는 남음 · 그 경고 줄에 값·예외 글이 없음(개정 2).
"""

import logging
from datetime import UTC, datetime

import pytest
from django.db import transaction

from esgapi.core.models import AuditEventRow, DocumentRow
from esgapi.core.observability.context import bind_request_id, unbind_request_id
from esgapi.core.service.services import audit as services
from esgapi.core.service.services.audit import AuditRecorded, AuditRefused, record_event

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 19, 3, 0, tzinfo=UTC)


def rows() -> list[AuditEventRow]:
    return list(AuditEventRow.unscoped.order_by("id"))


def a_document(company_id: int) -> None:
    DocumentRow.for_company(company_id).create(
        company_id=company_id, uploaded_by="1", file_name="a.pdf", storage_key=f"k-{company_id}", size_bytes=1,
        status="awaiting_upload",
    )  # fmt: skip


def test_a_company_line_keeps_every_field(companies: tuple[int, int]) -> None:
    a, _ = companies
    token = bind_request_id("req-1")
    try:
        done = record_event(
            at=NOW,
            company_id=a,
            actor_kind="admin",
            actor_user_id=3,
            action="setting_change",
            event="user_updated",
            result="success",
            target_kind="user",
            target_id=8,
            target_label="kim",
            changed_fields=("name",),
        )
    finally:
        unbind_request_id(token)
    assert isinstance(done, AuditRecorded)
    [row] = rows()
    assert row.id == done.id
    assert (row.company_id, row.at, row.actor_kind, row.actor_user_id) == (a, NOW, "admin", 3)
    assert (row.action, row.event, row.result, row.reason) == ("setting_change", "user_updated", "success", None)
    assert (row.target_kind, row.target_id, row.target_label) == ("user", 8, "kim")
    assert (row.detail, row.request_id) == ({"changed_fields": ["name"]}, "req-1")


def test_a_line_without_a_company_goes_through_the_operator_entrance(companies: tuple[int, int]) -> None:
    done = record_event(
        at=NOW, company_id=None, actor_kind="anonymous", actor_user_id=None, action="login", event="login_failed",
        result="failure", reason="unknown_user",
    )  # fmt: skip
    assert isinstance(done, AuditRecorded)
    [row] = rows()
    assert (row.company_id, row.actor_kind, row.actor_user_id, row.reason) == (None, "anonymous", None, "unknown_user")
    assert (row.target_kind, row.target_id, row.target_label, row.detail, row.request_id) == (
        None,
        None,
        None,
        {},
        None,
    )
    assert list(AuditEventRow.operator_rows()) == [row]  # 입구가 그 줄을 연다


def test_a_line_outside_the_shape_is_a_value_and_writes_nothing(
    companies: tuple[int, int], caplog: pytest.LogCaptureFixture
) -> None:
    a, _ = companies
    with caplog.at_level(logging.WARNING, logger="esgapi.audit"):
        refused = record_event(
            at=NOW, company_id=a, actor_kind="service", actor_user_id=1, action="export", event="x_done",
            result="success", target_label="hidden-label-value",
        )  # fmt: skip
    assert refused == AuditRefused("action")
    assert rows() == []
    assert [r.getMessage() for r in caplog.records] == ["audit_refused field=action"]
    assert "hidden-label-value" not in caplog.text


def test_called_inside_a_business_block_it_does_not_throw(companies: tuple[int, int]) -> None:
    a, _ = companies
    with transaction.atomic():
        a_document(a)
        bad = record_event(
            at=NOW, company_id=None, actor_kind="service", actor_user_id=1, action="upload", event="document_uploaded",
            result="success",
        )  # fmt: skip
        good = record_event(
            at=NOW, company_id=a, actor_kind="service", actor_user_id=1, action="upload", event="document_uploaded",
            result="success",
        )  # fmt: skip
    assert bad == AuditRefused("company_id")  # 고객사 사람의 줄인데 회사 없음(N2) — 던지지 않는다
    assert isinstance(good, AuditRecorded)
    assert DocumentRow.for_company(a).count() == 1 and len(rows()) == 1


def test_a_db_refusal_rolls_back_only_the_audit_savepoint(
    companies: tuple[int, int], caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """check_event 를 비켜(⑱ 의 시험) CHECK 에 걸리는 값을 넣으면 AuditRefused("db_error") 이고 업무 줄은 남는다.
    경고 줄에는 예외의 클래스 이름과 SQLSTATE 만 — exc_info 0, 넣은 글자 0(개정 2)."""
    a, _ = companies

    def no_check(**_: object) -> None:
        return None

    monkeypatch.setattr(services, "check_event", no_check)
    secret_label = "ghost-label-0f3a9c"
    with caplog.at_level(logging.WARNING, logger="esgapi.audit"), transaction.atomic():
        a_document(a)
        refused = record_event(
            at=NOW, company_id=a, actor_kind="service", actor_user_id=1, action="export", event="x_done",
            result="success", target_label=secret_label,
        )  # fmt: skip
        assert DocumentRow.for_company(a).count() == 1  # 바깥 트랜잭션은 깨지지 않았다(이어 읽힌다)
    assert refused == AuditRefused("db_error")
    assert rows() == []
    assert DocumentRow.for_company(a).count() == 1  # 업무 줄은 남는다
    [record] = caplog.records
    assert record.getMessage() == "audit_refused error_class=IntegrityError sqlstate=23514"  # check_violation
    assert record.exc_info is None
    assert secret_label not in caplog.text and "Failing row" not in caplog.text


def test_a_module_line_keeps_its_module_in_the_detail(companies: tuple[int, int]) -> None:
    """AD4S ③: module 은 detail 의 이름 있는 칸으로 들어간다. 꼴 밖이면 쓰지 않는다(행 0)."""
    a, _ = companies
    done = record_event(
        at=NOW, company_id=a, actor_kind="admin", actor_user_id=3, action="setting_change",
        event="ai_setting_applied", result="success", changed_fields=("applied",), module="greenwash",
    )  # fmt: skip
    assert isinstance(done, AuditRecorded)
    [row] = rows()
    assert row.detail == {"changed_fields": ["applied"], "module": "greenwash"}
    refused = record_event(
        at=NOW, company_id=a, actor_kind="admin", actor_user_id=3, action="setting_change",
        event="ai_setting_applied", result="success", module="Bad",
    )  # fmt: skip
    assert refused == AuditRefused("module")
    assert len(rows()) == 1
