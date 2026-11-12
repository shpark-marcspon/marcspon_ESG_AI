"""실행 넷의 표를 진짜 DB 로 잰다(업무 층 — 주인 역할이라 권한은 재지 못한다: 그것은 tests/security/test_runs.py).

재는 것: 같은 회사 복합 FK 가 남의 회사 문서·실행을 거절한다(NOT DEFERRABLE — 그 문에서), CHECK(상태·목적·크기·이름 꼴),
UNIQUE(단계 이름·차례, 결과 차례, 출력 파일 이름 — 단계 NULL 도 같은 값으로), 표는 for_company 로만 열린다.
"""

import json
from typing import Any, cast

import pytest
from django.db import IntegrityError, connection, transaction

from esgapi.core.isolation.managers import CompanyScopedManager, UnscopedQueryError
from esgapi.core.models import DocumentRow
from esgapi.runs.models import RUN_OPTIONS_CEILING_OCTETS, RunFileRow, RunResultRow, RunRow, RunStepRow

pytestmark = pytest.mark.django_db


def document(company_id: int, key: str = "a") -> DocumentRow:
    return DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="1",
        file_name=f"{key}.pdf",
        storage_key=f"documents/{company_id}/{key}.pdf",
        size_bytes=1,
        status="uploaded",
    )


def run(company_id: int, document_id: int, **extra: Any) -> RunRow:
    values: dict[str, Any] = {
        "module": "greenwash",
        "flow_id": "greenwash.colab@E0",
        "status": "queued",
        "created_by_user_id": 7,
        **extra,
    }
    return RunRow.for_company(company_id).create(company_id=company_id, document_id=document_id, **values)


def refused(make: Any) -> str:
    """세이브포인트 안에서 만들어 보고, DB 가 거절한 제약 이름(psycopg 의 diag)을 돌려준다."""
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        make()
    cause: Any = caught.value.__cause__
    return str(cause.diag.constraint_name)


def test_a_run_cannot_point_at_another_companys_document(companies: tuple[int, int]) -> None:
    a, b = companies
    b_doc = document(b, "b")
    assert refused(lambda: run(a, b_doc.pk)) == "run_runs_document_id_same_company_fk"
    assert run(b, b_doc.pk).company_id == b  # 분모: 같은 회사면 들어간다


@pytest.mark.parametrize("model", [RunStepRow, RunResultRow, RunFileRow], ids=lambda m: m.__name__)
def test_a_child_row_cannot_point_at_another_companys_run(companies: tuple[int, int], model: type[Any]) -> None:
    a, b = companies
    b_run = run(b, document(b, "b").pk)
    by_model: dict[type[Any], dict[str, Any]] = {
        RunStepRow: {"name": "extract", "position": 0, "status": "pending"},
        RunResultRow: {"position": 0, "schema_version": "greenwash.result@1", "body": {}},
        RunFileRow: {
            "name": "r.xlsx",
            "media_type": "application/x",
            "storage_key": "k",
            "size_bytes": 1,
            "sha256": "0" * 64,
        },
    }
    values = by_model[model]
    table = model._meta.db_table
    assert refused(lambda: model.for_company(a).create(company_id=a, run_id=b_run.pk, **values)) == (
        f"{table}_run_id_same_company_fk"
    )
    assert model.for_company(b).create(company_id=b, run_id=b_run.pk, **values).company_id == b  # 분모


def test_the_checks_refuse_what_the_runner_would_not_write(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = document(a)
    assert refused(lambda: run(a, doc.pk, status="paused")) == "run_runs_status_check"
    assert refused(lambda: run(a, doc.pk, purpose="demo")) == "run_runs_purpose_check"
    assert refused(lambda: run(a, doc.pk, stalled_attempts=-1)) == "run_runs_stalled_attempts_check"
    assert refused(lambda: run(a, doc.pk, progress_attempt=0)) == "run_runs_progress_attempt_check"
    # ND1: options 는 감싼 꼴의 DB 상한(0002) — 한글 3바이트라 CEILING // 3 + 1 자면 넘는다
    assert refused(lambda: run(a, doc.pk, options={"x": "가" * (RUN_OPTIONS_CEILING_OCTETS // 3 + 1)})) == (
        "run_runs_options_size_check"
    )
    assert refused(lambda: run(a, doc.pk, versions={"x": "a" * 16400})) == "run_runs_versions_size_check"
    one = run(a, doc.pk, options={"x": "a" * 16000}, progress_attempt=1)  # 분모: 상한 안은 들어간다
    assert (
        refused(
            lambda: RunStepRow.for_company(a).create(
                company_id=a, run_id=one.pk, name="s", position=0, status="waiting"
            )
        )
        == "run_steps_status_check"
    )
    assert (
        refused(
            lambda: RunFileRow.for_company(a).create(
                company_id=a, run_id=one.pk, name="../x", media_type="m", storage_key="k1", size_bytes=1, sha256="0"
            )
        )
        == "run_files_name_check"
    )


def test_the_unique_keys(companies: tuple[int, int]) -> None:
    a, _ = companies
    one = run(a, document(a).pk)
    steps = RunStepRow.for_company(a)
    steps.create(company_id=a, run_id=one.pk, name="extract", position=0, status="pending")
    assert (
        refused(lambda: steps.create(company_id=a, run_id=one.pk, name="extract", position=1, status="pending"))
        == "run_steps_run_name_uniq"
    )
    assert (
        refused(lambda: steps.create(company_id=a, run_id=one.pk, name="judge", position=0, status="pending"))
        == "run_steps_run_position_uniq"
    )
    results = RunResultRow.for_company(a)
    results.create(company_id=a, run_id=one.pk, position=0, schema_version="x.y@1", body={})
    assert (
        refused(lambda: results.create(company_id=a, run_id=one.pk, position=0, schema_version="x.z@1", body={}))
        == "run_results_run_position_uniq"
    )
    files = RunFileRow.for_company(a)

    def file(step: str | None, key: str) -> RunFileRow:
        return files.create(
            company_id=a,
            run_id=one.pk,
            step=step,
            name="r.xlsx",
            media_type="m",
            storage_key=key,
            size_bytes=1,
            sha256="0",
        )

    file(None, "k-out")
    file("report", "k-step")  # 분모: 단계 산출 파일은 같은 이름이어도 된다
    assert refused(lambda: file(None, "k-out-2")) == "run_files_run_step_name_uniq"  # 출력 파일(NULL)끼리 겹침
    assert refused(lambda: file("report", "k-step-2")) == "run_files_run_step_name_uniq"
    assert refused(lambda: file("other", "k-out")).startswith("run_files_storage_key")  # 이름의 꼬리는 Django 의 해시


@pytest.mark.parametrize("model", [RunRow, RunStepRow, RunResultRow, RunFileRow], ids=lambda m: m.__name__)
def test_the_tables_open_only_through_for_company(companies: tuple[int, int], model: type[Any]) -> None:
    a, b = companies
    assert isinstance(model._default_manager, CompanyScopedManager)
    with pytest.raises(UnscopedQueryError):  # 회사 없이 열면 거절한다
        model.objects.all()
    run(a, document(a).pk)
    assert (RunRow.for_company(a).count(), RunRow.for_company(b).count()) == (1, 0)


# ── 단계 산출의 열쇠 차례(X1b-2b ㉔ — OrderedJSONField) ─────────────────────

# jsonb 는 열쇠를 길이 → 바이트 차례로 다시 늘어세운다: 이 값은 {"ceo", "climate", "company": {"a", "zz"}} 로 읽힌다
SHUFFLED: dict[str, object] = {"climate": 1, "ceo": 2, "company": {"zz": 1, "a": 2}}


def keys_deep(value: object) -> list[object]:
    """dict 의 열쇠 차례를 겹친 것까지 늘어놓는다."""
    if isinstance(value, dict):
        return [(k, keys_deep(v)) for k, v in cast("dict[str, object]", value).items()]
    return []


def step_row(company_id: int, key: str = "s", **extra: object) -> RunStepRow:
    one = run(company_id, document(company_id, key).pk)
    return RunStepRow.for_company(company_id).create(
        company_id=company_id, run_id=one.pk, name="extract", position=0, status="done", **extra
    )


def stored(step_id: int, column: str) -> Any:
    """DB 안의 그 칸을 날 SQL 로(필드를 거치지 않고) 읽는다."""
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {column}::text, {column} IS NULL FROM run_steps WHERE id = %s", [step_id])
        return cursor.fetchone()


@pytest.mark.parametrize("column", ["data", "partial"])
def test_step_data_and_partial_come_back_in_the_written_key_order(companies: tuple[int, int], column: str) -> None:
    a, _ = companies
    values: dict[str, object] = {column: SHUFFLED}
    made = step_row(a, "s", **values)
    again = RunStepRow.for_company(a).get(pk=made.pk)
    assert keys_deep(getattr(again, column)) == keys_deep(SHUFFLED)
    assert getattr(again, column) == SHUFFLED
    # 분모: 같은 값을 맨 JSONField(RunRow.versions)에 쓰면 jsonb 가 차례를 바꾼다(options 는 ND1 부터 감싼 꼴)
    plain = run(a, document(a, "p").pk, versions=SHUFFLED)
    plain_again = RunRow.for_company(a).get(pk=plain.pk)
    assert plain_again.versions == SHUFFLED
    assert keys_deep(plain_again.versions) != keys_deep(SHUFFLED)
    assert keys_deep(plain_again.versions) == [("ceo", []), ("climate", []), ("company", [("a", []), ("zz", [])])]
    # DB 안은 감싼 글자 하나다(스키마는 맨 jsonb)
    text, _ = stored(made.pk, column)
    assert text.startswith('{"ordered@1": "{\\"climate\\"')


def test_run_options_come_back_in_the_written_key_order_and_a_null_document_is_a_run(
    companies: tuple[int, int],
) -> None:
    """ND1(Q12): 실행의 options 도 쓴 차례로 읽힌다(흐름이 입력 차례로 읽는다). 문서 칸은 비어도 된다(문서 없는
    흐름)."""
    a, _ = companies
    made = RunRow.for_company(a).create(
        company_id=a,
        document_id=None,
        module="probe",
        flow_id="probe.bare@1",
        status="queued",
        created_by_user_id=7,
        options=SHUFFLED,
    )
    again = RunRow.for_company(a).get(pk=made.pk)
    assert (again.document_id, again.options) == (None, SHUFFLED)
    assert keys_deep(again.options) == keys_deep(SHUFFLED)
    with connection.cursor() as cursor:
        cursor.execute("SELECT options::text FROM run_runs WHERE id = %s", [made.pk])
        (text,) = cursor.fetchone() or ("",)
    assert text.startswith('{"ordered@1": "{\\"climate\\"')  # DB 안은 감싼 글자 하나


def test_an_unwrapped_old_value_reads_as_it_is(companies: tuple[int, int]) -> None:
    """옛 값(감싸기 전에 쓴 행)은 그대로 읽힌다. 넣는 길: 필드를 거치지 않는 날 SQL(이 시험 안에서만)."""
    a, _ = companies
    made = step_row(a)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE run_steps SET data = %s::jsonb, partial = %s::jsonb WHERE id = %s",
            ['{"size": 3, "name": "x"}', '{"items": [0, 1]}', made.pk],
        )
    again = RunStepRow.for_company(a).get(pk=made.pk)
    assert again.data == {"size": 3, "name": "x"}
    assert list(again.data or {}) == ["name", "size"]  # jsonb 의 차례 그대로(옛 값은 차례를 갖지 않았다)
    assert again.partial == {"items": [0, 1]}


def test_none_is_sql_null(companies: tuple[int, int]) -> None:
    a, _ = companies
    made = step_row(a, data=None, partial=None)
    assert stored(made.pk, "data") == (None, True)
    assert stored(made.pk, "partial") == (None, True)
    again = RunStepRow.for_company(a).get(pk=made.pk)
    assert (again.data, again.partial) == (None, None)
    filled = step_row(a, "t", data={"k": 1})
    assert stored(filled.pk, "data")[1] is False  # 분모: 값이 있으면 NULL 이 아니다


def test_the_wrapped_size_next_to_the_plain_one(companies: tuple[int, int]) -> None:
    """감싼 꼴의 octet_length 를 맨 꼴 옆에 잰다(§4-10 — 크기 CHECK 는 감싼 글자를 잰다)."""
    a, _ = companies
    value: dict[str, object] = {"items": [{"sentence": "지어낸 문장 " * 20, "score": 0.5, "tags": ["x", "y"]}] * 50}
    made = step_row(a, data=value)
    with connection.cursor() as cursor:
        cursor.execute("SELECT octet_length(data::text) FROM run_steps WHERE id = %s", [made.pk])
        wrapped = int(cast("tuple[int]", cursor.fetchone())[0])
        cursor.execute("SELECT octet_length(%s::jsonb::text)", [json.dumps(value, ensure_ascii=False)])
        bare = int(cast("tuple[int]", cursor.fetchone())[0])
    print(f"OCTETS plain={bare} wrapped={wrapped} ratio={wrapped / bare:.3f}")
    assert bare < wrapped < bare * 2


def test_nan_in_step_data_is_refused_at_the_write(companies: tuple[int, int]) -> None:
    """감싼 글자 안의 NaN 은 jsonb 가 막지 못한다 — 필드가 쓰기에서 ValueError 로 거절한다.
    분모: 보통 float 은 지난다."""
    a, _ = companies
    made = step_row(a)
    steps = RunStepRow.for_company(a).filter(pk=made.pk)
    with pytest.raises(ValueError, match="Out of range float values are not JSON compliant"), transaction.atomic():
        steps.update(data={"score": float("nan")})
    steps.update(data={"score": 0.5})
    assert RunStepRow.for_company(a).get(pk=made.pk).data == {"score": 0.5}
