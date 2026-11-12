"""표 둘(core_documents·run_jobs)의 꼴을 글자로 못 박는다. 순수 층(모델을 import 할 뿐 DB 에 닿지 않는다).

★ 칸 집합 테스트는 「가지면 안 되는 것」의 기계 검사다: 분해 결과의 본문(문서 모델·글자 자리·쪽의 글), 모듈 고유의
  칸, 서명된 주소가 들어갈 칸이 없다. 칸을 더해도 빠져도 빨개진다. 칸을 더하려면 발주서와 이 표를 같이 고친다.
"""

import inspect
from importlib import import_module
from typing import Any

from django.db import models

from esgapi.core import models as core_models
from esgapi.core.calc import documents as calc
from esgapi.core.models import DocumentRow
from esgapi.core.resources import queue as hooks
from esgapi.core.service.selectors import documents as selectors
from esgapi.core.service.services import documents as services
from esgapi.runs import models as runs_models
from esgapi.runs.models import JobRow

DOCUMENT_COLUMNS = {
    "id",
    "company",
    "uploaded_by",
    "file_name",
    "storage_key",
    "size_bytes",
    "etag",
    "sha256",
    "status",
    "created_at",
    "updated_at",
    "uploaded_at",
    # X1b-1: 칸(쓰는 코드는 X1b-2a). 보고서의 해·앞 판(같은 회사 자기 참조)·쪽 수
    "report_year",
    "previous_document",
    "page_count",
    "has_text",  # X1b-2a: 앞 TEXT_PROBE_PAGES 쪽의 글자 층(NULL = 모른다)
}
JOB_COLUMNS = {
    "id",
    "company",
    "document",
    "kind",
    "status",
    "attempts",
    "error_code",
    "error_message",
    "summary",
    "lease_expires_at",
    "created_at",
    "updated_at",
    "finished_at",
}


def fields_of(model: type[models.Model]) -> dict[str, Any]:
    return {field.name: field for field in model._meta.concrete_fields}  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def check_values(model: type[models.Model], constraint_name: str) -> tuple[str, tuple[str, ...]]:
    """CheckConstraint 의 `<칸>__in` 조건에서 (조건의 이름, 값들)을 꺼낸다."""
    found = [c for c in model._meta.constraints if c.name == constraint_name]
    assert len(found) == 1, constraint_name
    constraint = found[0]
    assert isinstance(constraint, models.CheckConstraint)
    condition: Any = constraint.condition
    children: list[Any] = list(condition.children)
    assert len(children) == 1
    lookup, values = children[0]
    return lookup, tuple(values)


def test_document_columns_are_exactly_the_written_list() -> None:
    assert set(fields_of(DocumentRow)) == DOCUMENT_COLUMNS
    assert len(DOCUMENT_COLUMNS) == 16  # X1b-1 +3 · X1b-2a +1(has_text)


def test_job_columns_are_exactly_the_written_list() -> None:
    assert set(fields_of(JobRow)) == JOB_COLUMNS
    assert len(JOB_COLUMNS) == 13


def test_table_names_and_the_only_json_column() -> None:
    assert (DocumentRow._meta.db_table, JobRow._meta.db_table) == ("core_documents", "run_jobs")
    # JSON 칸은 일감의 summary 하나뿐이다(크기는 마이그레이션의 CHECK 가 막는다). 글·바이트를 통째로 담을 칸이 없다.
    for model, expected in ((DocumentRow, []), (JobRow, ["summary"])):
        loose = [
            name
            for name, field in fields_of(model).items()
            if isinstance(field, models.JSONField | models.TextField | models.BinaryField | models.FileField)
        ]
        assert loose == expected, model.__name__


def test_column_shapes() -> None:
    doc = fields_of(DocumentRow)
    assert (doc["id"].__class__, doc["uploaded_by"].max_length) == (models.BigAutoField, 64)
    assert (doc["file_name"].max_length, doc["etag"].max_length, doc["sha256"].max_length) == (255, 255, 64)
    assert doc["storage_key"].unique is True
    assert [name for name in sorted(doc) if doc[name].null] == [
        "etag",
        "has_text",  # X1b-2a +1
        "page_count",  # X1b-1 +3
        "previous_document",
        "report_year",
        "sha256",
        "uploaded_at",
    ]
    assert doc["size_bytes"].null is False
    # 회사는 organization 의 company 를 가리키는 외래 키(PROTECT. 글자 참조 — core 는 organization 을
    # import 하지 않는다).
    # 올린 사람은 외래 키가 아니다(글자 칸 — X1 의 판단).
    assert [name for name, field in doc.items() if field.is_relation] == ["company", "previous_document"]  # X1b-1 +1
    for row in (doc, fields_of(JobRow)):
        company = row["company"]
        assert (company.remote_field.model._meta.label, company.remote_field.on_delete) == (
            "organization.Company",
            models.PROTECT,
        )
        assert (company.attname, company.column, company.null) == ("company_id", "company_id", False)

    job = fields_of(JobRow)
    assert (job["id"].__class__, job["error_code"].max_length, job["error_message"].max_length) == (
        models.BigAutoField,
        64,
        500,
    )
    assert [name for name in sorted(job) if job[name].null] == [
        "error_code",
        "error_message",
        "finished_at",
        "lease_expires_at",
    ]
    assert (job["attempts"].default, job["summary"].default) == (0, dict)
    assert [name for name, field in job.items() if field.is_relation] == ["company", "document"]
    remote = job["document"].remote_field
    assert (remote.model, remote.on_delete) == (DocumentRow, models.PROTECT)


def test_status_checks_carry_the_same_values_as_the_pure_tuples() -> None:
    assert check_values(DocumentRow, "core_documents_status_check") == ("status__in", calc.DOCUMENT_STATUSES)
    assert check_values(JobRow, "run_jobs_status_check") == ("status__in", calc.JOB_STATUSES)
    assert core_models.DOCUMENT_ROW_STATUSES == calc.DOCUMENT_STATUSES
    assert runs_models.JOB_ROW_STATUSES == calc.JOB_STATUSES
    # kind 에는 CHECK 가 없다(값은 서비스가 JOB_KINDS 로 거른다).
    assert sorted(c.name for c in JobRow._meta.constraints) == ["run_jobs_attempts_check", "run_jobs_status_check"]
    assert sorted(c.name for c in DocumentRow._meta.constraints) == [
        "core_documents_page_count_check",  # X1b-1: 칸 셋의 범위(≥1 · 해 1900~2100 — 어림)
        "core_documents_previous_uniq",  # X1b-2a: 갈래 금지(한 문서의 뒤 판은 하나 — 부분 UNIQUE)
        "core_documents_report_year_check",
        "core_documents_size_bytes_check",
        "core_documents_status_check",
    ]


def test_the_migration_depends_on_organization_only_and_carries_the_summary_limit() -> None:
    """core 의 마이그레이션은 0001(K1u-b 가 다시 씀)·0002(AD4D). organization 0001 에만 기댄다(company 표가 먼저).

    일감 표의 몫(크기 CHECK·같은 회사 외래 키)은 X1a 때 runs 의 0001 로 옮겼다 — runs 0001 은 core 0001(문서 표와
    그 회사 키)과 organization 0001 에 기댄다.
    """
    migration = import_module("esgapi.core.migrations.0001_initial")
    runs_migration = import_module("esgapi.runs.migrations.0001_initial")
    assert migration.Migration.dependencies == [("organization", "0001_initial")]
    assert runs_migration.Migration.dependencies == [("core", "0001_initial"), ("organization", "0001_initial")]
    assert runs_migration.SUMMARY_MAX_OCTETS == 4096
    source = inspect.getsource(migration)
    runs_source = inspect.getsource(runs_migration)
    assert "CHECK (octet_length(summary::text) <= {SUMMARY_MAX_OCTETS})" in runs_source
    assert "company_key(DOCUMENTS)" in source
    assert 'same_company_foreign_key(table=JOBS, column="document_id", target=DOCUMENTS)' in runs_source
    for text in (source, runs_source):
        assert "isolate(" not in text and "tenancy.rls" not in text  # RLS 의 조각은 지웠다
        assert all(module not in text for module in ("esgapi.accounts", "esgapi.organization", "esgapi.user"))


def test_columns_this_band_stands_up_but_does_not_write() -> None:
    """임대·sha256·요약·실패 칸은 세우기만 했다: 쓰는 코드가 이 밴드의 제품 코드에 없다(워커 W1b 의 것이다).

    무효 조건: 글자를 본 것이다(모듈 셋의 소스에 그 이름이 없다). 다른 길로 쓰는 코드는 못 본다.
    예외 하나: 실행 묶음의 넣기 import_document(RX1a)는 묶음 행의 sha256 을 원래 값 그대로(NULL 이면 NULL) 넣는다.
    """
    imported = inspect.getsource(services.import_document)
    assert "sha256" in imported  # 분모: 뺀 몫이 실제로 sha256 을 쓴다(묶음 원래 값 그대로 — RX1a)
    written = "".join(inspect.getsource(module) for module in (services, hooks)).replace(imported, "")
    for column in ("sha256", "lease_expires_at", "summary", "error_code", "error_message", "finished_at"):
        assert column not in written, column
    # 읽는 쪽(selectors)은 응답에 싣는 넷을 읽는다. sha256 과 임대 기한은 읽지도 않는다.
    # 이름으로 읽지 않는다 — raw_documents(RX1a)는 values() 로 칸 전부.
    read = inspect.getsource(selectors)
    for column in ("sha256", "lease_expires_at"):
        assert column not in read, column
