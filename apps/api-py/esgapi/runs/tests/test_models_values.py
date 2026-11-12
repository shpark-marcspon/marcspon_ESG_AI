"""실행 넷의 값(runs/models.py)과 계약 꼴·마이그레이션의 값이 같다. 순수 층(모델을 import 할 뿐 DB 에 닿지 않는다).

상태·목적의 값은 마이그레이션의 CHECK 가 문면에 굳힌다. 계약(runs/service/schemas/runs.py)의 Literal 에 값을 더하고
모델·마이그레이션을 안 고치면 여기서 빨개진다. 크기 상한은 어림이다(주석이 그렇다고 말하는지도 본다).
"""

import inspect
from importlib import import_module
from typing import Any, get_args

from django.db import models

from esgapi.core.flows import types as flow_types
from esgapi.runs import models as runs_models
from esgapi.runs.models import RunFileRow, RunResultRow, RunRow, RunSegmentRow, RunStepRow
from esgapi.runs.service.schemas.runs import RunStatus, RunStepStatus

MIGRATION = import_module("esgapi.runs.migrations.0001_initial")
DOCUMENT_OPTIONAL = import_module("esgapi.runs.migrations.0002_run_document_optional")  # ND1


def check_values(model: type[models.Model], name: str) -> tuple[str, ...]:
    found = [c for c in model._meta.constraints if c.name == name]
    assert len(found) == 1, name
    constraint = found[0]
    assert isinstance(constraint, models.CheckConstraint)
    condition: Any = constraint.condition
    ((lookup, values),) = condition.children
    assert lookup.endswith("__in"), name
    return tuple(values)


def test_the_status_values_are_the_contract_literals() -> None:
    assert get_args(RunStatus) == runs_models.RUN_ROW_STATUSES
    assert get_args(RunStepStatus) == runs_models.RUN_STEP_STATUSES
    assert check_values(RunRow, "run_runs_status_check") == runs_models.RUN_ROW_STATUSES
    assert check_values(RunStepRow, "run_steps_status_check") == runs_models.RUN_STEP_STATUSES
    assert check_values(RunRow, "run_runs_purpose_check") == runs_models.RUN_PURPOSES == ("service", "test")


def test_the_size_limits_are_the_migrations_and_are_marked_as_guesses() -> None:
    assert (
        runs_models.RUN_OPTIONS_MAX_OCTETS,
        runs_models.RUN_VERSIONS_MAX_OCTETS,
        runs_models.RUN_STEP_DATA_MAX_OCTETS,
        runs_models.RUN_RESULT_BODY_MAX_OCTETS,
    ) == (
        MIGRATION.OPTIONS_MAX_OCTETS,
        MIGRATION.VERSIONS_MAX_OCTETS,
        MIGRATION.STEP_DATA_MAX_OCTETS,
        MIGRATION.RESULT_BODY_MAX_OCTETS,
    )
    assert runs_models.RUN_RESULT_BODY_MAX_OCTETS == 8 * 1024 * 1024
    source = inspect.getsource(runs_models)
    for name in (
        "RUN_OPTIONS_MAX_OCTETS",
        "RUN_VERSIONS_MAX_OCTETS",
        "RUN_STEP_DATA_MAX_OCTETS",
        "RUN_RESULT_BODY_MAX_OCTETS",
    ):
        (line,) = [text for text in source.splitlines() if text.startswith(f"{name} =")]
        assert "어림" in line, name


def test_the_options_ceiling_is_the_0002_check_and_twice_the_widest_flow_limit() -> None:
    """ND1: options 의 DB 상한은 0002 가 문면에 굳힌 값이고, 흐름 앱 상한의 최대를 감싼 꼴로 적은 최악(두 배 + 껍데기)을
    덮는다. 문서 흐름의 앱 상한은 0001 의 16KiB 그대로다."""
    assert runs_models.RUN_OPTIONS_CEILING_OCTETS == DOCUMENT_OPTIONAL.OPTIONS_CEILING_OCTETS == 2 * 256 * 1024 + 64
    assert runs_models.RUN_OPTIONS_CEILING_OCTETS == 2 * runs_models.DOCUMENTLESS_OPTIONS_MAX_OCTETS + 64
    assert DOCUMENT_OPTIONAL.OPTIONS_MAX_OCTETS_0001 == MIGRATION.OPTIONS_MAX_OCTETS  # 되돌림은 0001 의 값


def test_the_four_tables_and_their_json_columns() -> None:
    assert [m._meta.db_table for m in (RunRow, RunStepRow, RunResultRow, RunFileRow)] == [
        "run_runs",
        "run_steps",
        "run_results",
        "run_files",
    ]
    json = {
        model.__name__: sorted(f.name for f in model._meta.concrete_fields if isinstance(f, models.JSONField))
        for model in (RunRow, RunStepRow, RunResultRow, RunFileRow)
    }
    # 흐름마다 표를 만들지 않는다: 결과·단계 산출은 이 JSON 칸(+ 저장소의 파일)뿐이다. 파일 바이트를 담을 칸이 없다.
    assert json == {
        "RunRow": ["options", "versions"],
        "RunStepRow": ["data", "partial"],
        "RunResultRow": ["body"],
        "RunFileRow": [],
    }
    binary = [
        f"{model.__name__}.{f.name}"
        for model in (RunRow, RunStepRow, RunResultRow, RunFileRow)
        for f in model._meta.concrete_fields
        if isinstance(f, models.BinaryField | models.FileField | models.TextField)
    ]
    assert binary == []


def test_the_au1b_columns_keep_their_names() -> None:
    """§2-6 의 칸 계약(AU1b 가 믿는다): 칸 이름·NULL 여부. 바꾸면 AU1b 의 지표 시험이 거짓이 된다."""
    run = {f.attname: f.null for f in RunRow._meta.concrete_fields}
    assert {
        name: run[name]
        for name in (
            "id",
            "company_id",
            "document_id",
            "module",
            "flow_id",
            "created_by_user_id",
            "status",
            "created_at",
            "started_at",
            "finished_at",
            "failed_step",
            "error_code",
            "attempts",
            "purpose",
            "versions",
        )
    } == {
        "id": False,
        "company_id": False,
        "document_id": True,  # ND1 — 문서 없는 흐름. 지표는 문서를 읽지 않음(COHORT_FIELDS operator.py:67)
        "module": False,
        "flow_id": False,
        "created_by_user_id": False,
        "status": False,
        "created_at": False,
        "started_at": True,
        "finished_at": True,
        "failed_step": True,
        "error_code": True,
        "attempts": False,
        "purpose": False,
        "versions": False,
    }
    # 다른 앱으로 향하는 외래 키는 회사·문서 둘뿐이다(사람은 숫자 칸 — runs 는 user 를 모른다).
    assert sorted(f.name for f in RunRow._meta.concrete_fields if f.is_relation) == ["company", "document"]
    indexes = {index.name: list(index.fields) for index in RunRow._meta.indexes}
    assert indexes["run_runs_company_created"] == ["company", "created_at"]
    assert indexes["run_runs_created"] == ["created_at"]


IDEMPOTENCY = import_module("esgapi.runs.migrations.0003_run_idempotency_key")  # IK1


def test_the_idempotency_columns_and_constraints_are_the_0003_ones() -> None:
    """IK1: 칸 둘(NULL 가능, 36·64자)과 부분 유일·짝 CHECK. 모델의 제약 = 0003 의 AddConstraint(이름·칸·조건)."""
    run = {f.attname: f for f in RunRow._meta.concrete_fields}
    key, sha = run["idempotency_key"], run["idempotency_sha256"]
    assert isinstance(key, models.CharField) and isinstance(sha, models.CharField)
    assert (key.max_length, key.null, sha.max_length, sha.null) == (36, True, 64, True)
    found = {c.name: c for c in RunRow._meta.constraints}
    unique, pair = found["run_runs_idempotency_uniq"], found["run_runs_idempotency_pair_check"]
    assert isinstance(unique, models.UniqueConstraint) and isinstance(pair, models.CheckConstraint)
    assert unique.fields == ("company", "created_by_user_id", "idempotency_key")
    assert unique.condition == models.Q(idempotency_key__isnull=False)
    assert pair.condition == models.Q(idempotency_key__isnull=True, idempotency_sha256__isnull=True) | models.Q(
        idempotency_key__isnull=False, idempotency_sha256__isnull=False
    )
    added = {op.constraint.name: op.constraint for op in IDEMPOTENCY.Migration.operations if hasattr(op, "constraint")}
    assert added == {"run_runs_idempotency_uniq": unique, "run_runs_idempotency_pair_check": pair}
    assert IDEMPOTENCY.Migration.dependencies == [("runs", "0002_run_document_optional")]


LAUNCH = import_module("esgapi.runs.migrations.0004_run_launch_key")  # LK1


def test_the_launch_key_column_and_index_are_the_0004_ones() -> None:
    """LK1: 칸 하나(NULL 가능, 36자)와 부분 색인 하나(유일 아님 — 묶음은 실행 여럿). 모델의 색인 = 0004 의 AddIndex."""
    run = {f.attname: f for f in RunRow._meta.concrete_fields}
    key = run["launch_key"]
    assert isinstance(key, models.CharField)
    assert (key.max_length, key.null) == (36, True)
    found = {index.name: index for index in RunRow._meta.indexes}
    index = found["run_runs_launch_key"]
    assert list(index.fields) == ["company", "launch_key"]
    assert index.condition == models.Q(launch_key__isnull=False)
    assert "run_runs_launch_key" not in {c.name for c in RunRow._meta.constraints}  # 유일 제약이 아니다
    added = [op.index for op in LAUNCH.Migration.operations if hasattr(op, "index")]
    assert added == [index]
    operations = LAUNCH.Migration.operations
    fields = [(op.name, op.field.max_length, op.field.null) for op in operations if hasattr(op, "field")]
    assert fields == [("launch_key", 36, True)]
    assert LAUNCH.Migration.dependencies == [("runs", "0003_run_idempotency_key")]


SEGMENTS = import_module("esgapi.runs.migrations.0005_run_segments")  # RM1a
LEASE = import_module("esgapi.runs.migrations.0006_run_segment_lease")  # RM1b


def test_the_segment_values_are_the_0005_ones_and_core_keeps_half_the_size() -> None:
    """RM1a: 구획 상태 넷 = CHECK, 구획 data DB 상한 = 0005 의 값, core 의 앱 상한 = 그 절반(감싼 꼴 최악 두 배),
    펼침 단계 data 앱 상한 = 단계 data DB 상한의 절반."""
    assert runs_models.RUN_SEGMENT_STATUSES == ("pending", "running", "done", "failed")
    assert check_values(RunSegmentRow, "run_segments_status_check") == runs_models.RUN_SEGMENT_STATUSES
    assert runs_models.RUN_SEGMENT_DATA_MAX_OCTETS == SEGMENTS.SEGMENT_DATA_MAX_OCTETS == 1024 * 1024
    assert flow_types.SEGMENT_DATA_MAX_OCTETS * 2 == runs_models.RUN_SEGMENT_DATA_MAX_OCTETS
    assert flow_types.FANOUT_DATA_MAX_OCTETS * 2 == runs_models.RUN_STEP_DATA_MAX_OCTETS
    (line,) = [t for t in inspect.getsource(runs_models).splitlines() if t.startswith("RUN_SEGMENT_DATA_MAX_OCTETS =")]
    assert "어림" in inspect.getsource(runs_models).split("RUN_SEGMENT_DATA_MAX_OCTETS =")[0].splitlines()[-1]
    created = [op for op in SEGMENTS.Migration.operations if hasattr(op, "fields")]
    assert len(created) == 1
    model_constraints = {c.name: c for c in RunSegmentRow._meta.constraints}
    migration_constraints = {c.name: c for c in created[0].options["constraints"]}
    # RM1b 0006 이 CHECK 둘을 더한다(0005 의 것은 그대로) — 모델 = 0005 ∪ 0006
    added = {op.constraint.name: op.constraint for op in LEASE.Migration.operations if hasattr(op, "constraint")}
    assert set(added) == {"run_segments_lease_running_check", "run_segments_data_octets_check"}
    assert migration_constraints.keys().isdisjoint(added)
    assert migration_constraints | added == model_constraints
    assert SEGMENTS.Migration.dependencies == [("runs", "0004_run_launch_key"), ("organization", "0001_initial")]
    kind = {f.attname: f for f in RunSegmentRow._meta.concrete_fields}["kind"]
    assert isinstance(kind, models.CharField) and kind.max_length == 32  # core SEGMENT_KIND 꼴의 상한(1~32자)
    assert line
