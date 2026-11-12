"""step_output(끝난 단계의 산출 — MARC-ENT-325 의 입구)를 진짜 DB 로 잰다. 업무 층(X1b-2b ㉑, sid:MARC-ISSUE-199 의 2).

재는 것: 끝난 단계는 StepFound(data 와 파일의 이름·꼴·크기), 아직 안 끝난 단계·없는 단계는 StepNotDone, 없는 실행·남의
회사 실행은 RunNotFound. 이어 돌린 실행의 옮긴 단계도 그 실행의 것으로 읽힌다(자기 행 — 앞 실행을 거치지 않는다).
run_page 의 modules(모듈 집합 거름 — 운영 관리자의 목록, OP2)는 거름·module 과 and·None 이면 그대로·쿼리 수 같음.
run_page 의 statuses(상태 집합)·created_by_user_id(만든 사람 — 데이터 검증 목록, DV1g)도 같은 네 가지를 잰다.
step_heads(AD4D — 운영 관리자 실행 상세)는 선언 차례·시각을 주고 data·partial 을 SELECT 에 싣지 않으며, 남의 회사
실행이면 빈 튜플.
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import json
import re
from collections.abc import Callable, Collection
from typing import Any

import pytest
from django.db import DataError, connection, transaction
from django.db.models import Case, CharField, F, Func, IntegerField, JSONField, Q, Value, When
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Cast, Coalesce, StrIndex
from django.test import Client
from django.test.utils import CaptureQueriesContext
from pytest_django import DjangoAssertNumQueries

from esgapi.core.models import DocumentRow
from esgapi.runs import models as run_models
from esgapi.runs.models import RunFileRow, RunRow, RunStepRow
from esgapi.runs.service.selectors import runs as selectors
from esgapi.runs.service.selectors.runs import FileRef, RunNotFound, StepFound, StepNotDone
from tests.support.http import login

pytestmark = pytest.mark.django_db


def a_run(company_id: int, *, resumed_from: int | None = None) -> int:
    document = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="1",
        file_name="지은 문서.pdf",
        storage_key=f"companies/{company_id}/documents/s-{DocumentRow.unscoped.count()}/original",
        size_bytes=1,
        status="uploaded",
    )
    run = RunRow.for_company(company_id).create(
        company_id=company_id,
        document_id=document.pk,
        module="probe",
        flow_id="probe.three@1",
        status="queued",
        created_by_user_id=1,
        resumed_from_run_id=resumed_from,
    )
    steps = (("extract", "done", {"size": 3, "name": "x"}), ("judge", "running", None), ("report", "pending", None))
    for position, (name, status, data) in enumerate(steps):
        RunStepRow.for_company(company_id).create(
            company_id=company_id, run_id=run.pk, name=name, position=position, status=status, data=data
        )
    RunFileRow.for_company(company_id).create(
        company_id=company_id,
        run_id=run.pk,
        step="extract",
        name="pages.json",
        media_type="application/json",
        storage_key=f"runs/{company_id}/{run.pk}/steps/extract/pages.json",
        size_bytes=6,
        sha256="0" * 64,
    )
    return run.pk


def test_a_finished_step_is_found_with_its_data_and_file_refs(companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = a_run(a)
    found = selectors.step_output(company_id=a, run_id=run_id, step="extract")
    assert found == StepFound(
        data={"size": 3, "name": "x"}, files=(FileRef(name="pages.json", media_type="application/json", size_bytes=6),)
    )
    assert isinstance(found, StepFound) and list(found.data) == ["size", "name"]  # 쓴 열쇠 차례(①)


def test_a_carried_step_of_a_resumed_run_is_its_own(companies: tuple[int, int]) -> None:
    a, _ = companies
    previous = a_run(a)
    resumed = a_run(a, resumed_from=previous)
    found = selectors.step_output(company_id=a, run_id=resumed, step="extract")
    assert isinstance(found, StepFound) and found.data == {"size": 3, "name": "x"}


@pytest.mark.parametrize("step", ["judge", "report", "nothing"])
def test_an_unfinished_or_unknown_step_is_not_done(companies: tuple[int, int], step: str) -> None:
    a, _ = companies
    run_id = a_run(a)
    assert selectors.step_output(company_id=a, run_id=run_id, step=step) == StepNotDone()
    assert isinstance(selectors.step_output(company_id=a, run_id=run_id, step="extract"), StepFound)  # 분모


def test_a_missing_or_another_companys_run_is_not_found(companies: tuple[int, int]) -> None:
    a, b = companies
    theirs = a_run(b)
    assert selectors.step_output(company_id=a, run_id=theirs, step="extract") == RunNotFound()
    assert selectors.step_output(company_id=a, run_id=theirs + 1000, step="extract") == RunNotFound()
    assert isinstance(selectors.step_output(company_id=b, run_id=theirs, step="extract"), StepFound)  # 분모


# ── 묶음 읽기(step_rows_of·results_of — 목록 줄 G1b-2b) ──


def test_the_batch_reads_key_by_run_in_the_declared_order(companies: tuple[int, int]) -> None:
    a, _ = companies
    first, second = a_run(a), a_run(a)
    for run_id, positions in ((first, (1, 0)), (second, (0,))):
        for position in positions:  # 차례를 거꾸로 넣어도 position 차례로 읽힌다
            run_models.RunResultRow.for_company(a).create(
                company_id=a, run_id=run_id, position=position, schema_version="probe.result@1", body={"n": position}
            )
    steps = selectors.step_rows_of(company_id=a, run_ids=[first, second])
    assert {k: [s.name for s in v] for k, v in steps.items()} == {
        first: ["extract", "judge", "report"],
        second: ["extract", "judge", "report"],
    }
    assert steps[first] == selectors.step_rows(company_id=a, run_id=first)  # 하나 읽기와 같은 값
    results = selectors.results_of(company_id=a, run_ids=[first, second])
    assert {k: [r.position for r in v] for k, v in results.items()} == {first: [0, 1], second: [0]}
    assert results[first] == selectors.run_results(company_id=a, run_id=first)
    assert selectors.step_rows_of(company_id=a, run_ids=[]) == {}
    assert selectors.results_of(company_id=a, run_ids=[]) == {}


def test_step_rows_of_leaves_out_another_tenants_runs(companies: tuple[int, int]) -> None:
    """남의 회사 id 가 섞인 입력 → 남의 것은 빠지고 제 것은 나온다(목록 줄 G1b-2b)."""
    a, b = companies
    a_id, b_id = a_run(a), a_run(b)
    got = selectors.step_rows_of(company_id=a, run_ids=[a_id, b_id])
    assert set(got) == {a_id} and len(got[a_id]) == 3  # 분모: 제 것은 나온다
    assert set(selectors.step_rows_of(company_id=b, run_ids=[a_id, b_id])) == {b_id}
    assert selectors.step_rows_of(company_id=b, run_ids=[a_id]) == {}


def test_results_of_leaves_out_another_tenants_runs(companies: tuple[int, int]) -> None:
    """남의 회사 id 가 섞인 입력 → 남의 것은 빠지고 제 것은 나온다(목록 줄 G1b-2b)."""
    a, b = companies
    a_id, b_id = a_run(a), a_run(b)
    for company_id, run_id in ((a, a_id), (b, b_id)):
        run_models.RunResultRow.for_company(company_id).create(
            company_id=company_id, run_id=run_id, position=0, schema_version="probe.result@1", body={}
        )
    got = selectors.results_of(company_id=a, run_ids=[a_id, b_id])
    assert set(got) == {a_id} and len(got[a_id]) == 1  # 분모: 제 것은 나온다
    assert set(selectors.results_of(company_id=b, run_ids=[a_id, b_id])) == {b_id}
    assert selectors.results_of(company_id=b, run_ids=[a_id]) == {}


# ── 모듈 집합으로 거르기(run_page 의 modules — 운영 관리자의 목록, MARC-ENT-380·밴드 OP2) ──


def a_module_run(company_id: int, module: str) -> int:
    """단계·파일 없는 실행 하나(목록 줄만 잰다)."""
    document = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="1",
        file_name=f"지은 {module}.pdf",
        storage_key=f"companies/{company_id}/documents/m-{DocumentRow.unscoped.count()}/original",
        size_bytes=1,
        status="uploaded",
    )
    run = RunRow.for_company(company_id).create(
        company_id=company_id,
        document_id=document.pk,
        module=module,
        flow_id=f"{module}.probe@1",
        status="queued",
        created_by_user_id=1,
    )
    return run.pk


def page_ids(company_id: int, *, module: str | None = None, modules: Collection[str] | None = None) -> list[int]:
    page = selectors.run_page(
        company_id=company_id, module=module, status=None, document_id=None, limit=20, offset=0, modules=modules
    )
    assert page.count == len(page.runs)
    return [run.id for run, _name in page.runs]


def test_run_page_filters_by_a_module_set(companies: tuple[int, int]) -> None:
    a, b = companies
    greenwash, inventory, translation = (a_module_run(a, m) for m in ("greenwash", "inventory", "translation"))
    a_module_run(b, "translation")  # 남의 회사 — 집합 안 모듈이어도 빠진다
    both = frozenset({"greenwash", "translation"})
    assert page_ids(a, modules=both) == [translation, greenwash]
    assert page_ids(a, modules=frozenset()) == []  # 빈 집합 = 아무것도
    assert page_ids(a) == [translation, inventory, greenwash]  # 분모: None 이면 거르지 않는다
    assert page_ids(a, modules=None) == page_ids(a)


def test_run_page_ands_the_module_and_the_module_set(companies: tuple[int, int]) -> None:
    a, _ = companies
    greenwash, inventory, translation = (a_module_run(a, m) for m in ("greenwash", "inventory", "translation"))
    both = frozenset({"greenwash", "translation"})
    assert page_ids(a, module="translation", modules=both) == [translation]
    assert page_ids(a, module="greenwash", modules=both) == [greenwash]
    assert page_ids(a, module="inventory", modules=both) == []  # 둘 다 거른다(and)
    assert page_ids(a, module="inventory") == [inventory]  # 분모


def test_the_module_set_adds_no_query(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    for module in ("greenwash", "inventory", "translation"):
        a_module_run(a, module)
    with django_assert_num_queries(2):  # 분모: 고객사 목록 — 셈 1 + 읽기 1(문서 이름은 같은 쿼리의 join)
        assert len(page_ids(a)) == 3
    with django_assert_num_queries(2):  # 집합 거름은 같은 쿼리의 조건이다
        assert len(page_ids(a, modules=frozenset({"greenwash", "translation"}))) == 2


def a_status_run(company_id: int, status: str, created_by: int = 1) -> int:
    """단계·파일 없는 데이터 검증 실행 하나(문서 없음 — 상태·만든 사람만 다르다)."""
    run = RunRow.for_company(company_id).create(
        company_id=company_id,
        module="dataverify",
        flow_id="dataverify.probe@1",
        status=status,
        created_by_user_id=created_by,
    )
    return run.pk


def filtered_ids(
    company_id: int, *, statuses: Collection[str] | None = None, created_by_user_id: int | None = None
) -> list[int]:
    page = selectors.run_page(
        company_id=company_id,
        module=None,
        status=None,
        document_id=None,
        limit=20,
        offset=0,
        statuses=statuses,
        created_by_user_id=created_by_user_id,
    )
    assert page.count == len(page.runs)
    return [run.id for run, _name in page.runs]


def test_run_page_filters_by_a_status_set(companies: tuple[int, int]) -> None:
    a, b = companies
    queued, processing, done, failed = (a_status_run(a, s) for s in ("queued", "processing", "done", "failed"))
    a_status_run(b, "queued")  # 남의 회사 — 집합 안 상태여도 빠진다
    assert filtered_ids(a, statuses=frozenset({"queued", "processing"})) == [processing, queued]
    assert filtered_ids(a, statuses=frozenset[str]()) == []  # 빈 집합 = 아무것도
    assert filtered_ids(a) == [failed, done, processing, queued]  # 분모: None 이면 거르지 않는다
    assert filtered_ids(a, statuses=None) == filtered_ids(a)


def test_run_page_ands_the_status_and_the_status_set(companies: tuple[int, int]) -> None:
    a, _ = companies
    queued, processing, _done = (a_status_run(a, s) for s in ("queued", "processing", "done"))
    active = frozenset({"queued", "processing"})
    page = selectors.run_page(
        company_id=a, module=None, status="queued", document_id=None, limit=20, offset=0, statuses=active
    )
    assert [run.id for run, _name in page.runs] == [queued]
    page = selectors.run_page(
        company_id=a, module=None, status="done", document_id=None, limit=20, offset=0, statuses=active
    )
    assert (page.count, page.runs) == (0, ())  # 둘 다 거른다(and)
    assert filtered_ids(a, statuses=frozenset({"processing"})) == [processing]  # 분모


def test_run_page_filters_by_the_creator(companies: tuple[int, int]) -> None:
    a, b = companies
    mine = a_status_run(a, "done", created_by=7)
    theirs = a_status_run(a, "done", created_by=8)
    a_status_run(b, "done", created_by=7)  # 남의 회사의 같은 id — 빠진다
    assert filtered_ids(a, created_by_user_id=7) == [mine]
    assert filtered_ids(a, created_by_user_id=8) == [theirs]
    assert filtered_ids(a, created_by_user_id=9) == []
    assert filtered_ids(a) == [theirs, mine]  # 분모: None 이면 거르지 않는다
    assert filtered_ids(a, created_by_user_id=7, statuses=frozenset({"queued"})) == []  # 상태 집합과 and


def test_the_status_set_and_the_creator_add_no_query(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, b = companies
    for status in ("queued", "processing", "done"):
        a_status_run(a, status, created_by=7)
    a_status_run(b, "queued", created_by=7)
    with django_assert_num_queries(2):  # 분모: 셈 1 + 읽기 1
        assert len(filtered_ids(a)) == 3
    with django_assert_num_queries(2):  # 두 거름은 같은 쿼리의 조건이다
        assert len(filtered_ids(a, statuses=frozenset({"queued", "processing"}), created_by_user_id=7)) == 2


# ── 단계 머리(AD4D) ──


def test_step_heads_are_in_the_declared_order_without_data_or_partial(companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = a_run(a)
    RunStepRow.for_company(a).filter(run_id=run_id, name="judge").update(partial={"items": [1]})
    with CaptureQueriesContext(connection) as captured:
        heads = selectors.step_heads(company_id=a, run_id=run_id)
    assert [(h.name, h.position, h.status) for h in heads] == [
        ("extract", 0, "done"),
        ("judge", 1, "running"),
        ("report", 2, "pending"),
    ]
    ((query,),) = [[q["sql"] for q in captured.captured_queries]]
    selected = query.split(" FROM ")[0]
    assert '"run_steps"."name"' in selected  # 분모: 칸 목록을 읽었다
    assert '"data"' not in selected and '"partial"' not in selected  # 산출·부분은 읽지 않는다


def test_step_heads_of_another_companys_run_are_empty(companies: tuple[int, int]) -> None:
    a, b = companies
    run_id = a_run(a)
    assert selectors.step_heads(company_id=b, run_id=run_id) == ()
    assert len(selectors.step_heads(company_id=a, run_id=run_id)) == 3  # 분모


# ── 문서 없는 실행(ND1): run_page 는 LEFT JOIN 이라 줄이 남고 이름은 None ──


def test_run_page_keeps_a_documentless_run_with_no_name_through_a_left_join(companies: tuple[int, int]) -> None:
    a, _ = companies
    with_document = a_run(a)
    bare = RunRow.for_company(a).create(
        company_id=a,
        document_id=None,
        module="probe",
        flow_id="probe.bare@1",
        status="queued",
        created_by_user_id=1,
    )
    with CaptureQueriesContext(connection) as queries:
        page = selectors.run_page(company_id=a, module=None, status=None, document_id=None, limit=10, offset=0)
    assert [(run.id, run.document_id, name) for run, name in page.runs] == [
        (bare.pk, None, None),  # 글자 "None" 이 아니다(P6)
        (with_document, page.runs[1][0].document_id, "지은 문서.pdf"),
    ]
    assert page.count == 2
    (select, _count) = (q["sql"] for q in queries.captured_queries)
    assert 'LEFT OUTER JOIN "core_documents"' in select  # NULL 허용 외래 키 — Django 가 LEFT 로 올린다


# ── 영문번역 묶음 목록의 읽기 넷(TR3b, MARC-TICK-251): run_keys·runs_of·step_lines_of·results_of 의 schema_versions ──

BATCH = "0b1c2d3e-0000-4000-8000-00000000000a"


def a_keyed_run(
    company_id: int, options: dict[str, object], *, document_id: int | None = None, status: str = "done"
) -> int:
    if document_id is None:
        document_id = (
            DocumentRow.for_company(company_id)
            .create(
                company_id=company_id,
                uploaded_by="1",
                file_name="지은 문서.docx",
                storage_key=f"companies/{company_id}/documents/k-{DocumentRow.unscoped.count()}/original",
                size_bytes=1,
                status="uploaded",
            )
            .pk
        )
    return (
        RunRow.for_company(company_id)
        .create(
            company_id=company_id,
            document_id=document_id,
            module="translation",
            flow_id="probe.keyed@1",
            options=options,
            status=status,
            created_by_user_id=7,
        )
        .pk
    )


def stored_keys(run_id: int) -> list[str]:
    """DB 에 적힌 options 의 맨 위 열쇠(ORM 은 읽을 때 감싼 꼴을 풀어 버려 날 SQL 로 본다 — 시험만)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT jsonb_object_keys(options) FROM run_runs WHERE id = %s", [run_id])
        return sorted((row[0] for row in cursor.fetchall()), key=["part", "batchId", run_models.ORDERED_JSON_TAG].index)


def keys_of(
    company_id: int, *, document_id: int | None = None, limit: int = 100
) -> list[tuple[int, str | None, str | None]]:
    found = selectors.run_keys(company_id=company_id, module="translation", document_id=document_id, limit=limit)
    return [(k.id, k.batch_id, k.part) for k in found]


def test_run_keys_project_batch_id_and_part_from_the_wrapped_options(companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = a_keyed_run(a, {"part": "story", "batchId": BATCH, "style": "A", "note": "x" * 2000})
    assert stored_keys(run_id) == [run_models.ORDERED_JSON_TAG]  # 분모: 행은 감싼 꼴로 들어갔다(OrderedJSONField)
    (key,) = selectors.run_keys(company_id=a, module="translation", document_id=None, limit=10)
    assert (key.id, key.batch_id, key.part, key.status, key.created_by_user_id) == (run_id, BATCH, "story", "done", 7)
    assert key.document_id is not None and key.created_at is not None and key.finished_at is None


def test_run_keys_read_an_old_unwrapped_options_value(companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = a_keyed_run(a, {"part": "general"})
    # 감싸기 전(X1b-2b ㉔ 앞)에 쓴 행 — 맨 JSONField 값으로 바로 적는다
    RunRow.for_company(a).filter(pk=run_id).update(
        options=Value({"part": "ceo_message", "batchId": BATCH}, output_field=JSONField())
    )
    assert stored_keys(run_id) == ["part", "batchId"]  # 분모: 감싸지 않은 값이다
    assert keys_of(a) == [(run_id, BATCH, "ceo_message")]


def test_run_keys_give_none_for_a_missing_key(companies: tuple[int, int]) -> None:
    a, _ = companies
    bare = a_keyed_run(a, {"part": "story"})
    empty = a_keyed_run(a, {})
    assert keys_of(a) == [(empty, None, None), (bare, None, "story")]


def test_run_keys_are_newest_first_limited_and_filtered(companies: tuple[int, int]) -> None:
    a, b = companies
    first = a_keyed_run(a, {"part": "story"})
    document_id = RunRow.unscoped.get(pk=first).document_id
    second = a_keyed_run(a, {"part": "general"}, document_id=document_id)
    other_document = a_keyed_run(a, {"part": "story"})
    a_keyed_run(b, {"part": "story", "batchId": BATCH})  # 남의 회사
    a_module_run(a, "greenwash")  # 다른 모듈
    assert [k[0] for k in keys_of(a)] == [other_document, second, first]
    assert [k[0] for k in keys_of(a, limit=2)] == [other_document, second]
    assert [k[0] for k in keys_of(a, document_id=document_id)] == [second, first]
    assert len(keys_of(b)) == 1  # 분모: B 에는 제 것이 있다


def test_run_keys_select_only_the_two_projections_of_the_options(companies: tuple[int, int]) -> None:
    a, _ = companies
    a_keyed_run(a, {"part": "story", "batchId": BATCH, "glossary": {"base": [["가", "A"]]}})
    with CaptureQueriesContext(connection) as captured:
        found = selectors.run_keys(company_id=a, module="translation", document_id=None, limit=10)
    ((savepoint, query, release),) = [[q["sql"] for q in captured.captured_queries]]  # DVI1 +2: 세이브포인트
    assert savepoint.startswith("SAVEPOINT") and release.startswith("RELEASE SAVEPOINT")  # DVI1: 앞뒤 둘뿐
    selected = query.split(" FROM ")[0]
    reads = re.findall(r'"run_runs"\."options"(\s*\S+)', selected)
    assert len(reads) == 2 * len(selectors.RUN_KEY_OPTIONS)  # 열쇠마다 감싼 갈래·옛 갈래 둘
    assert all(after.strip().startswith("->") for after in reads), reads  # 칸 통째로 읽는 자리 0
    assert '"run_runs"."id"' in selected  # 분모: 칸 목록을 읽었다
    assert all(not hasattr(key, "options") for key in found)  # 다른 옵션 칸은 결과에 실리지 않는다
    assert selectors.RUN_KEY_OPTIONS == ("batchId", "part")


def test_runs_of_reads_the_runs_in_one_query_and_leaves_out_another_companys(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, b = companies
    ours = [a_keyed_run(a, {"part": "story"}), a_keyed_run(a, {"part": "general", "batchId": BATCH})]
    theirs = a_keyed_run(b, {"part": "story"})
    with django_assert_num_queries(1):
        found = selectors.runs_of(company_id=a, run_ids=[*ours, theirs, theirs + 1000])
    assert sorted(found) == sorted(ours)
    assert found[ours[1]] == selectors.find_run(company_id=a, run_id=ours[1])  # 하나 읽기와 같은 값
    assert list(found[ours[1]].options) == ["part", "batchId"]  # 쓴 차례
    with django_assert_num_queries(0):
        assert selectors.runs_of(company_id=a, run_ids=[]) == {}


def test_step_lines_of_read_heads_and_counts_without_data_or_partial(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, b = companies
    run_id = a_run(a)
    theirs = a_run(b)
    RunStepRow.for_company(a).filter(run_id=run_id, name="judge").update(partial={"items": [1]}, done=2, total=5)
    with CaptureQueriesContext(connection) as captured:
        lines = selectors.step_lines_of(company_id=a, run_ids=[run_id, theirs])
    assert list(lines) == [run_id]  # 남의 회사 실행은 열쇠가 없다
    assert [(s.name, s.position, s.status, s.done, s.total) for s in lines[run_id]] == [
        ("extract", 0, "done", None, None),
        ("judge", 1, "running", 2, 5),
        ("report", 2, "pending", None, None),
    ]
    ((query,),) = [[q["sql"] for q in captured.captured_queries]]
    selected = query.split(" FROM ")[0]
    assert '"run_steps"."done"' in selected and '"run_steps"."total"' in selected  # 분모
    assert '"data"' not in selected and '"partial"' not in selected
    with django_assert_num_queries(0):
        assert selectors.step_lines_of(company_id=a, run_ids=[]) == {}


def test_results_of_reads_only_the_named_schema_versions(companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = a_run(a)
    for position, version in enumerate(("probe.result@1", "probe.digest@1")):
        run_models.RunResultRow.for_company(a).create(
            company_id=a, run_id=run_id, position=position, schema_version=version, body={"n": position}
        )
    with CaptureQueriesContext(connection) as captured:
        digests = selectors.results_of(company_id=a, run_ids=[run_id], schema_versions={"probe.digest@1"})
    assert [(r.position, r.schema_version) for r in digests[run_id]] == [(1, "probe.digest@1")]
    ((query,),) = [[q["sql"] for q in captured.captured_queries]]
    assert '"run_results"."schema_version" IN' in query  # 거름은 DB 에서(본문을 올리지 않는다)
    everything = selectors.results_of(company_id=a, run_ids=[run_id])
    assert [r.schema_version for r in everything[run_id]] == ["probe.result@1", "probe.digest@1"]  # None 은 그대로
    assert selectors.results_of(company_id=a, run_ids=[run_id], schema_versions=()) == {}


# ── HD1 347 ①: run_page_brief — 옵션 본문 대신 경로 투영(T11) ─────────────────────────────

BRIEF_VALUES = {"name": ("input", "company", "name"), "source": ("source",)}
BRIEF_SHAPES = {"data": ("input", "data"), "theme": ("input", "data", "환경")}


def brief(company_id: int, **changes: object) -> "selectors.BriefPage":
    given: dict[str, object] = {
        "company_id": company_id,
        "module": "dataverify",
        "statuses": None,
        "created_by_user_id": None,
        "limit": 10,
        "offset": 0,
        "values": BRIEF_VALUES,
        "shapes": BRIEF_SHAPES,
        **changes,
    }
    return selectors.run_page_brief(**given)  # pyright: ignore[reportArgumentType]


def dv_run(company_id: int, options: dict[str, object], *, status: str = "done") -> int:
    run = RunRow.for_company(company_id).create(
        company_id=company_id,
        module="dataverify",
        flow_id="dataverify.probe@1",
        options=options,
        versions={},
        status=status,
        created_by_user_id=1,
    )
    return run.pk


def test_run_page_brief_never_selects_the_whole_options_outside_the_nul_branch(companies: tuple[int, int]) -> None:
    """T11: SELECT 안 "run_runs"."options" 뒤는 늘 -> ->> #> #>> — 통째는 \\u0000 표시 CASE 갈래(THEN) 하나뿐."""
    a, _ = companies
    dv_run(a, {"source": {"kind": "paste"}, "input": {"company": {"name": "지은기업"}, "data": {"환경": [1, 2]}}})
    with CaptureQueriesContext(connection) as captured:
        found = brief(a)
    query = captured.captured_queries[1]["sql"]  # DVI1 +2: 세이브포인트
    savepoint, release = captured.captured_queries[0]["sql"], captured.captured_queries[2]["sql"]
    assert savepoint.startswith("SAVEPOINT") and release.startswith("RELEASE SAVEPOINT")  # DVI1: 줄 쿼리의 앞뒤
    selected = query.split(" FROM ")[0]
    reads = re.findall(r'(\S+\s+)?"run_runs"\."options"(\s*\S+)', selected)
    assert reads  # 분모: 옵션 경로를 읽었다
    whole = [(before, after) for before, after in reads if not after.strip().startswith(("->", "#>"))]
    assert [before.strip() for before, _after in whole] == ["THEN"], whole
    assert len(captured.captured_queries) == 4  # 줄·count · DVI1 +2: 세이브포인트
    (line,) = found.runs
    assert line.values == {"name": "지은기업", "source": {"kind": "paste"}}
    assert line.shapes == {"data": ("object", None), "theme": ("array", 2)}
    assert line.whole is None


def test_run_page_brief_filters_orders_and_counts_like_run_page(companies: tuple[int, int]) -> None:
    a, b = companies
    first = dv_run(a, {"input": {}})
    failed = dv_run(a, {"input": {}}, status="failed")
    dv_run(b, {"input": {}})  # 남의 회사
    a_module_run(a, "greenwash")  # 다른 모듈
    page = brief(a)
    old = selectors.run_page(company_id=a, module="dataverify", status=None, document_id=None, limit=10, offset=0)
    assert [r.id for r in page.runs] == [r.id for r, _name in old.runs] == [failed, first]
    assert page.count == old.count == 2
    assert [r.id for r in brief(a, statuses=["failed"]).runs] == [failed]
    assert brief(a, limit=1, offset=1).count == 2 and [r.id for r in brief(a, limit=1, offset=1).runs] == [first]
    assert brief(b).count == 1


def test_run_page_brief_carries_the_whole_options_only_for_a_nul_row(companies: tuple[int, int]) -> None:
    a, _ = companies
    plain = dv_run(a, {"input": {"company": {"name": "보통"}}})
    nul = dv_run(a, {"input": {"company": {"name": "가\x00나"}}})
    rows = {r.id: r for r in brief(a).runs}
    assert rows[plain].whole is None and rows[plain].values["name"] == "보통"
    assert rows[nul].whole == {"input": {"company": {"name": "가\x00나"}}}
    assert rows[nul].values == {"name": None, "source": None}  # 투영은 그 줄을 풀지 않는다(부르는 쪽이 whole 로 셈)


# ── DVI1 442: 감싼 글자의 \u0000·짝 없는 서로게이트 — jsonb 로 풀지 않는 표시(LONE_ESCAPE) ──────────────────

LONE_CASES: dict[str, tuple[str, bool]] = {  # 이름 → (파이썬 값, 표시되는가)
    "nul": ("가\x00나", True),
    "lone_high": ("가\ud800나", True),
    "lone_low": ("가\udc00나", True),
    "high_then_other": ("가\udbffA", True),
    "high_high_low": ("\ud800\ud800\udc00", True),
    "high_low_low": ("\ud800\udc00\udc00", True),
    "odd_backslash_nul": ("가\\\x00", True),  # 글자 그대로의 역슬래시 + 진짜 NUL(감싼 글자 \\\u0000)
    "fake_high_real_low": ("\\ud800\udc00", True),  # 글자 그대로의 \ud800 + 진짜 외톨이 하위
    "pair": ("😀", False),
    "pair_twice": ("😀😀", False),
    "literal_backslash_u0000": ("가\\u0000나", False),
    "plain": ("보통", False),
}


def wrapped_text(options: dict[str, object], *, pairs: bool) -> str:
    """OrderedJSONField 가 감쌀 안쪽 글자(json.dumps ensure_ascii=False). 서로게이트는 JSON 탈출로 적는다 — 날 글자로는
    psycopg·pg 가 받지 않는다. pairs 면 BMP 밖 글자(이모지)도 탈출 짝(\\ud83d\\ude00)으로."""
    text = json.dumps(options, ensure_ascii=False)

    def escape(found: re.Match[str]) -> str:
        code = ord(found.group())
        if code > 0xFFFF:
            code -= 0x10000
            return f"\\u{0xD800 + (code >> 10):04x}\\u{0xDC00 + (code & 0x3FF):04x}"
        return f"\\u{code:04x}"

    return re.sub("[\ud800-\udfff\U00010000-\U0010ffff]" if pairs else "[\ud800-\udfff]", escape, text)


def fallback_heads(after: int) -> list[str]:
    """대체 길의 쿼리 머리: 세이브포인트 · 떨어진 BASE SELECT · 되돌림(ROLLBACK TO·RELEASE) · 그 뒤 SELECT after 개."""
    return ["SAVEPOINT", "SELECT", "ROLLBACK", "RELEASE", *["SELECT"] * after]


def store_wrapped(
    company_id: int, run_id: int, options: dict[str, object], *, pairs: bool = False
) -> dict[str, object]:
    """감싼 꼴을 DB 에 바로 적는다(짝 없는 서로게이트는 ORM 의 save 로는 들어가지 않는다 — 쓰기 경로 밖에서 생긴 행).
    돌려주는 것은 파이썬 셈(OrderedJSONField.from_db_value 의 json.loads — 붙은 상위·하위 탈출은 글자 하나로 합친다)."""
    text = wrapped_text(options, pairs=pairs)
    wrapped = {run_models.ORDERED_JSON_TAG: text}
    RunRow.for_company(company_id).filter(pk=run_id).update(options=Value(wrapped, output_field=JSONField()))
    assert stored_keys(run_id) == [run_models.ORDERED_JSON_TAG]  # 분모: 감싼 꼴이다
    loaded: dict[str, object] = json.loads(text)
    assert RunRow.unscoped.get(pk=run_id).options == loaded  # 분모: ORM 읽기와 같은 셈
    return loaded


@pytest.mark.parametrize("pairs", [False, True], ids=["raw_pair", "escaped_pair"])
def test_run_keys_count_a_lone_escape_row_like_python(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries, pairs: bool
) -> None:
    a, _ = companies
    made: dict[str, tuple[int, dict[str, object]]] = {}
    for case, (text, _marked) in LONE_CASES.items():
        run_id = a_keyed_run(a, {"part": "story"})
        made[case] = (run_id, store_wrapped(a, run_id, {"part": text, "batchId": BATCH, "note": "x"}, pairs=pairs))
    with CaptureQueriesContext(connection) as captured:
        found = {k[0]: k for k in keys_of(a)}
    heads = [q["sql"].split(" ")[0] for q in captured.captured_queries]
    assert heads == fallback_heads(2)  # 다시 읽기 + 표시 줄의 옵션
    for case, (run_id, loaded) in made.items():
        assert found[run_id] == (run_id, BATCH, loaded["part"]), case
    assert found[made["nul"][0]][2] == "가\x00나" and found[made["pair"][0]][2] == "😀"  # 분모: 셈이 비지 않았다


def test_run_keys_read_the_batch_id_of_a_lone_escape_row(companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = a_keyed_run(a, {"part": "story"})
    store_wrapped(a, run_id, {"batchId": "가\ud800", "style": "\udc00"})
    assert keys_of(a) == [(run_id, "가\ud800", None)]


@pytest.mark.parametrize("pairs", [False, True], ids=["raw_pair", "escaped_pair"])
def test_run_page_brief_marks_only_a_lone_escape_row(companies: tuple[int, int], pairs: bool) -> None:
    a, _ = companies
    made: dict[str, tuple[int, dict[str, object]]] = {}
    for case, (text, _marked) in LONE_CASES.items():
        options: dict[str, object] = {"source": "가상", "input": {"company": {"name": text}, "data": {"환경": [1]}}}
        run_id = dv_run(a, {"input": {}})
        made[case] = (run_id, store_wrapped(a, run_id, options, pairs=pairs))
    with CaptureQueriesContext(connection) as captured:
        rows = {r.id: r for r in brief(a, limit=50).runs}
    assert [q["sql"].split(" ")[0] for q in captured.captured_queries] == fallback_heads(2)  # 다시 읽기 + count
    for case, (run_id, options) in made.items():
        line, marked = rows[run_id], LONE_CASES[case][1]
        if marked:
            assert line.whole == options, case
            assert line.values == {"name": None, "source": None}, case
        else:
            assert line.whole is None, case  # 보통 갈래 — 투영이 그 값을 낸다
            assert (
                line.values
                == {"name": LONE_CASES[case][0], "source": "가상"}
                == {
                    "name": options["input"]["company"]["name"],  # pyright: ignore[reportIndexIssue]
                    "source": options["source"],
                }
            ), case
            assert line.shapes == {"data": ("object", None), "theme": ("array", 1)}, case


def test_the_dataverify_run_list_is_200_with_a_lone_surrogate_row(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    login(client)  # 가상 「김담당」 — tenant-a(companies 의 첫째)
    plain = dv_run(a, {"source": "가상", "input": {"company": {"name": "보통"}}})
    lone = dv_run(a, {"input": {}})
    store_wrapped(a, lone, {"source": "가상", "input": {"company": {"name": "가\ud800나"}}})
    response = client.get("/api/dataverify/runs")
    assert response.status_code == 200, response.content.decode()
    names = {row["id"]: row["companyName"] for row in response.json()["results"]}
    assert names == {plain: "보통", lone: "가\ud800나"}


# ── DVI1 e7 조건: 보통 길은 BASE SQL 그대로 · 대체 길은 떨어질 때만 · 바깥 트랜잭션은 산다 ────────────────────────


def base_option_text(key: str) -> Coalesce:
    """BASE(298f13ce) 의 run_keys 투영 그대로(시험 안 사본 — 보통 길 SQL 글자 대조의 정답)."""
    wrapped = KeyTextTransform(
        key, Cast(KeyTextTransform(run_models.ORDERED_JSON_TAG, "options"), output_field=JSONField())
    )
    return Coalesce(wrapped, KeyTextTransform(key, "options"))


def base_brief_lines(company_id: int) -> list[dict[str, object]]:
    """BASE(298f13ce) 의 run_page_brief 줄 쿼리 그대로(brief() 의 기본 인자 — 시험 안 사본)."""
    wrapped = KeyTextTransform(run_models.ORDERED_JSON_TAG, "options")
    marked_q = Q(_hd1_nul__gt=0)

    def option_json(path: tuple[str, ...]) -> Coalesce:
        inner: Any = Case(
            When(marked_q, then=Value(None, output_field=JSONField())),
            default=Cast(wrapped, output_field=JSONField()),
            output_field=JSONField(),
        )
        outer: Any = F("options")
        for key in path:
            inner, outer = KeyTransform(key, inner), KeyTransform(key, outer)
        return Coalesce(inner, outer, output_field=JSONField())

    rows = RunRow.for_company(company_id).filter(module="dataverify").order_by("-created_at", "-id")
    marked = rows.annotate(_hd1_nul=StrIndex(wrapped, Value("\\u0000")))
    projected: dict[str, Any] = {
        "_hd1_whole": Case(
            When(marked_q, then=F("options")), default=Value(None), output_field=RunRow._meta.get_field("options")
        )
    }
    for name, path in BRIEF_VALUES.items():
        projected[f"_hd1_v_{name}"] = option_json(path)
    for name, path in BRIEF_SHAPES.items():
        found = option_json(path)
        projected[f"_hd1_t_{name}"] = Func(found, function="jsonb_typeof", output_field=CharField())
        projected[f"_hd1_n_{name}"] = Case(
            When(**{f"_hd1_t_{name}": "array"}, then=Func(found, function="jsonb_array_length")),
            default=Value(None),
            output_field=IntegerField(),
        )
    head = ("id", "status", "created_at", "started_at", "finished_at", "created_by_user_id", "failed_step")
    return list(marked.annotate(**projected).values(*head, *projected)[0:10])


def sql_of(read: Callable[[], object]) -> list[str]:
    with CaptureQueriesContext(connection) as captured:
        read()
    return [q["sql"] for q in captured.captured_queries]


def test_run_keys_plain_path_sends_the_base_select_text(companies: tuple[int, int]) -> None:
    a, _ = companies
    a_keyed_run(a, {"part": "story", "batchId": BATCH})
    columns = ("id", "document_id", "status", "created_at", "finished_at", "created_by_user_id")
    (base,) = sql_of(
        lambda: list(
            RunRow.for_company(a)
            .filter(module="translation")
            .order_by("-created_at", "-id")
            .values(*columns, batch_key=base_option_text("batchId"), part_key=base_option_text("part"))[:10]
        )
    )
    savepoint, select, release = sql_of(lambda: keys_of(a, limit=10))
    assert select == base  # 한 글자도 그대로
    assert savepoint.startswith("SAVEPOINT") and release.startswith("RELEASE SAVEPOINT")
    assert "regexp_replace" not in select  # 분모: 정규식 판이 아니다


def test_run_page_brief_plain_path_sends_the_base_select_text(companies: tuple[int, int]) -> None:
    a, _ = companies
    dv_run(a, {"source": "가상", "input": {"company": {"name": "보통"}, "data": {"환경": [1]}}})
    dv_run(a, {"input": {"company": {"name": "가\x00나"}}})  # \u0000 은 BASE 길이 그대로 받는다(대체 길 아님)
    (base,) = sql_of(lambda: base_brief_lines(a))
    savepoint, select, release, count = sql_of(lambda: brief(a))
    assert select == base  # 한 글자도 그대로
    assert savepoint.startswith("SAVEPOINT") and release.startswith("RELEASE SAVEPOINT")
    assert count.startswith("SELECT COUNT(*)") and " ~ " not in select  # 분모: 정규식 판이 아니다


def test_a_mixed_page_takes_the_fallback_and_answers_like_python(companies: tuple[int, int]) -> None:
    a, _ = companies
    plain = a_keyed_run(a, {"part": "story", "batchId": BATCH})
    nul = a_keyed_run(a, {"part": "가\x00나"})
    lone = a_keyed_run(a, {"part": "story"})
    loaded = store_wrapped(a, lone, {"part": "가\udc00", "batchId": BATCH})
    heads = [q.split(" ")[0] for q in sql_of(lambda: keys_of(a))]
    assert heads == fallback_heads(2)  # 다시 읽기 + 표시 줄(nul·lone)의 옵션
    assert keys_of(a) == [(lone, BATCH, loaded["part"]), (nul, None, "가\x00나"), (plain, BATCH, "story")]
    plain_dv = dv_run(a, {"source": "가상", "input": {"company": {"name": "보통"}}})
    lone_dv = dv_run(a, {"input": {}})
    body = store_wrapped(a, lone_dv, {"source": "가상", "input": {"company": {"name": "가\ud800"}}})
    rows = {r.id: r for r in brief(a).runs}
    assert rows[plain_dv].whole is None and rows[plain_dv].values == {"name": "보통", "source": "가상"}
    assert rows[lone_dv].whole == body and rows[lone_dv].values == {"name": None, "source": None}


def test_the_outer_transaction_lives_after_the_fallback(companies: tuple[int, int]) -> None:
    a, _ = companies
    lone = a_keyed_run(a, {"part": "story"})
    store_wrapped(a, lone, {"part": "\ud800"})
    lone_dv = dv_run(a, {"input": {}})
    store_wrapped(a, lone_dv, {"input": {"company": {"name": "\udc00"}}})
    with transaction.atomic():  # 부르는 쪽이 트랜잭션 안에서 부를 때
        assert keys_of(a) == [(lone, None, "\ud800")]
        assert [r.id for r in brief(a).runs] == [lone_dv]
        assert RunRow.for_company(a).filter(pk=lone).exists()  # 다음 쿼리가 된다(깨진 트랜잭션 아님)
        RunRow.for_company(a).filter(pk=lone).update(status="failed")
    assert RunRow.for_company(a).get(pk=lone).status == "failed"  # 바깥은 그대로 이어 쓴다


def test_another_data_error_is_raised_not_taken_by_the_fallback(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    lone = a_keyed_run(a, {"part": "story"})
    store_wrapped(a, lone, {"part": "\ud800"})

    def not_ours(_error: DataError) -> bool:
        return False

    monkeypatch.setattr(selectors, "_lone_escape_error", not_ours)  # 「다른 DataError」로 본다
    with pytest.raises(DataError):
        keys_of(a)
    with pytest.raises(DataError):
        brief(a, module="translation")


@pytest.mark.parametrize(
    ("sql", "given", "taken"),
    [
        ("SELECT %s::jsonb", '"\\u0000"', True),  # 22P05 unsupported Unicode escape
        ("SELECT %s::jsonb", '"\\ud800"', True),  # 22P02 invalid input syntax for type json
        ("SELECT %s::jsonb", '"\\udc00"', True),
        ("SELECT %s::integer", "가", False),  # 22P02 이지만 json 이 아님
        ("SELECT %s::numeric(2, 0)", "1000", False),  # 22003 수 넘침
    ],
    ids=["nul", "lone_high", "lone_low", "integer_text", "numeric_overflow"],
)
def test_the_fallback_takes_only_the_lone_escape_errors(
    companies: tuple[int, int], sql: str, given: str, taken: bool
) -> None:
    del companies
    with pytest.raises(DataError) as raised, transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, [given])
    assert selectors._lone_escape_error(raised.value) is taken  # pyright: ignore[reportPrivateUsage]
