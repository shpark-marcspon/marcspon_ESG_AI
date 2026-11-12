"""실행 묶음(RX1a — export_runs·import_runs)을 앱 역할 연결로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ★g 앱 역할(esg_app)의 권한: 읽는 표 SELECT · 넣는 표 INSERT · 표 T(run_runs·run_steps·core_documents) UPDATE 가 있고,
     어느 표에도 DELETE 가 없다 — 넣기는 지우기 없이 된다(MARC-ENT-208). 하나라도 모자라면 이 밴드는 멈춘다(B1)
  S15 내보내기는 그 회사 행만 싣는다: 다른 회사에 같은 run_id 값의 LLM 기록 줄이 있어도 묶음에 0(run_id 는 외래 키가
     아니다 — 회사 거름이 막는다). 넣기는 앱 역할로 커밋되고(주인이 센다) DELETE·주인 권한 없이 된다
  S16 실제 저장소(versitygw — compose `storage`): 넣은 키가 runs/<B>/<새 실행>/…·companies/<B>/documents/<새 uuid>/…,
     바이트 sha 가 같고, ★e put 이 돌려준 ETag(행의 etag) = head 의 ETag. section4 가 RUNBUNDLE_S3_* 를 넘길 때만 돈다
     (없으면 까닭을 달고 건너뛴다 — 저장소 주소를 시험이 .env 에서 스스로 읽지 않는다). ROUNDTRIP_DIFF 를
     RUNBUNDLE_ROUNDTRIP_OUT 파일에 적는다(section4 의 7). RUNBUNDLE_SAMPLE_OUT 이 있으면 묶음 견본을 그 자리에 둔다

Django 의 연결은 앱 역할이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다(분모를 센다).
무효 조건: 권한은 esg_app 역할로 잰 것이다. superuser 에게는 GRANT 가 걸리지 않는다.
★ 회사·사람·문서는 전부 지어낸 것이다(synthetic).
"""

import hashlib
import json
import os
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
from django import db as django_db
from django.db import connection
from psycopg import sql

from esgapi.core.flows.binding import BINDINGS
from esgapi.core.flows.carriers import CARRIERS
from esgapi.core.resources import storage as storage_adapter
from esgapi.core.resources.ports.storage import ObjectBytes, ObjectFound, ObjectPut, ObjectStorage
from esgapi.core.service.selectors.documents import find_document
from esgapi.core.service.services import documents as document_services
from esgapi.core.service.services import llm_logs as llm_services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.dataverify.service.services import ai_settings as dataverify_settings
from esgapi.dataverify.tests.flows.support import options as dataverify_options
from esgapi.greenwash.service.selectors import review as review_selectors
from esgapi.greenwash.service.services import ai_settings as greenwash_settings
from esgapi.greenwash.service.services import review as review_services
from esgapi.greenwash.tests.service import seed as greenwash_seed
from esgapi.materiality.service.services import ai_settings as materiality_settings
from esgapi.materiality.tests.flows.support import options as materiality_options
from esgapi.runbundle.calc import bundle as bundle_calc
from esgapi.runbundle.calc.bundle import check_bundle, loads
from esgapi.runbundle.service.actions import export, import_
from esgapi.runbundle.service.actions.export import RunIds
from esgapi.runbundle.service.actions.import_ import Imported
from esgapi.runbundle.tests.support import World, a_customer, carriers, cut_chain, flows, seed, snapshot
from esgapi.runs.service.selectors import operator as operator_selectors
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.selectors.bundle import bundle_rows
from esgapi.runs.service.selectors.runs import run_files, runs_of
from esgapi.runs.service.services import bundle as run_bundle_services
from esgapi.translation.service.services import ai_settings as translation_settings
from esgapi.translation.tests.flows.support import options as translation_options
from tests.security.conftest import count

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
READ = ("run_runs", "run_steps", "run_results", "run_files", "core_documents", "core_llm_call_logs", "company", "users")
INSERT = ("run_runs", "run_steps", "run_results", "run_files", "core_documents", "core_llm_call_logs")
UPDATE = ("run_runs", "run_steps", "core_documents")


def _privilege(table: str, privilege: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user, has_table_privilege(current_user, %s, %s)", [table, privilege])
        row = cursor.fetchone()
    assert row is not None and row[0] == "esg_app"
    return bool(row[1])


def test_the_app_role_has_what_the_bundle_needs_and_no_delete(owner: Owner) -> None:
    table = {
        **{(t, "SELECT"): _privilege(t, "SELECT") for t in READ},
        **{(t, "INSERT"): _privilege(t, "INSERT") for t in INSERT},
        **{(t, "UPDATE"): _privilege(t, "UPDATE") for t in UPDATE},
    }
    assert all(table.values()), [key for key, ok in table.items() if not ok]
    assert not any(_privilege(t, "DELETE") for t in INSERT)
    assert not _privilege("run_results", "UPDATE") and not _privilege("core_llm_call_logs", "UPDATE")


def _export(tmp_path: Path, storage: ObjectStorage, world: World) -> Path:
    out = tmp_path / "bundle.zip"
    export.run(
        company_id=world.company,
        selection=RunIds((world.runs["r2"], world.runs["r4"])),
        out=out,
        app_commit="test",
        flows=flows(),
        carriers=carriers(),
        storage=storage,
    )
    return out


def _import(tmp_path: Path, storage: ObjectStorage, path: Path, company: int, user: int) -> Imported:
    return import_.run(
        path=path,
        company_id=company,
        user_id=user,
        orphans_out=tmp_path / "orphans.txt",
        flows=flows(),
        carriers=carriers(),
        storage=storage,
    )


def test_export_carries_only_that_companys_rows(tmp_path: Path, companies: tuple[int, int], owner: Owner) -> None:
    a, b = companies
    storage = FakeStorage()
    world = seed(storage, a)
    llm_services.insert_rows(
        company_id=b,
        rows=[
            {
                "module": "rxtest",
                "ts": "2026-10-01T00:00:00+00:00",
                "call_id": "b-line",
                "attempt": 0,
                "prompt_id": "rxtest.judge",
                "prompt_version": 1,
                "template_hash": "t" * 64,
                "request_hash": "r" * 64,
                "duration_ms": 1.0,
                "result_kind": "success",
                "run_id": world.runs["r2"],  # 남의 회사의 같은 run_id 값
            }
        ],
        run_map={world.runs["r2"]: world.runs["r2"]},
    )
    assert count(owner, "core_llm_call_logs") == 4  # 분모: 줄은 있다(A 셋 + B 하나)
    path = _export(tmp_path, storage, world)
    with zipfile.ZipFile(path) as bundle:
        found = check_bundle(loads(bundle.read("bundle.json")))
    calls = sorted(str(row["call_id"]) for row in found.rows["core_llm_call_logs"])
    assert calls == ["c1", "c2", "c3"]
    assert bundle_rows(company_id=b, run_ids=world.runs.values()).runs == []  # 실행 표의 문도 회사 거름(P22)


def test_import_commits_as_the_app_role_without_delete(
    tmp_path: Path, companies: tuple[int, int], owner: Owner
) -> None:
    a, b = companies
    storage = FakeStorage()
    world = seed(storage, a)
    before = count(owner, "run_runs")
    done = _import(tmp_path, storage, _export(tmp_path, storage, world), b, a_customer(b, "gasang-b"))
    assert count(owner, "run_runs") == before + 4 and len(done.runs) == 4  # 주인이 센 커밋된 행
    rows = owner.execute("SELECT count(*) FROM run_runs WHERE company_id = %s", [b]).fetchone()
    assert rows == (4,)


# ── S16 실제 저장소 ─────────────────────────────────────────────────────


def _real_storage() -> ObjectStorage:
    needed = ("ENDPOINT", "BUCKET", "REGION", "ACCESS_KEY", "SECRET_KEY")
    found = {name: os.environ.get(f"RUNBUNDLE_S3_{name}", "") for name in needed}
    if not all(found.values()):
        pytest.skip("RUNBUNDLE_S3_* 가 없다 — scripts/section4-RX1a.sh --with-containers 가 compose storage 로 돌린다")
    return storage_adapter.make(
        "s3",
        bucket=found["BUCKET"],
        region=found["REGION"],
        endpoint=found["ENDPOINT"],
        public_endpoint=found["ENDPOINT"],
        force_path_style=True,
        access_key_id=found["ACCESS_KEY"],
        secret_access_key=found["SECRET_KEY"],
    )


def _sha(storage: ObjectStorage, key: str) -> str:
    got = storage.get(key, max_bytes=10_000_000)
    assert isinstance(got, ObjectBytes), key
    return hashlib.sha256(got.data).hexdigest()


def test_a_round_trip_through_the_real_storage(tmp_path: Path, companies: tuple[int, int], owner: Owner) -> None:
    real = _real_storage()
    a, b = companies
    fake = FakeStorage()
    world = seed(fake, a)
    for key, (data, etag) in fake.objects.items():  # 심은 바이트를 실제 저장소로(같은 키 — 단일 put 의 ETag 는 md5)
        put = real.put(key, content=data, media_type="application/octet-stream")
        assert isinstance(put, ObjectPut) and put.etag == etag, key
    path = _export(tmp_path, real, world)
    sample = os.environ.get("RUNBUNDLE_SAMPLE_OUT")
    if sample:  # 크기 실측의 견본(section4 — 워크트리 밖 .out 에만, 저장소 추적 0)
        shutil.copyfile(path, sample)
    done = _import(tmp_path, real, path, b, a_customer(b, "gasang-b"))

    runs = {label: done.runs[old] for label, old in world.runs.items()}
    found = runs_of(company_id=b, run_ids=runs.values())
    documents = {
        "d1": found[runs["r4"]].document_id,
        "d2": found[runs["r2"]].document_id,
        "d3": found[runs["r3"]].document_id,
    }
    diffs = 0
    for label, document_id in documents.items():
        assert document_id is not None
        document = find_document(company_id=b, document_id=document_id)
        source = find_document(company_id=a, document_id=world.documents[label])
        assert document is not None and source is not None
        assert document.storage_key.startswith(f"companies/{b}/documents/") and document.storage_key.endswith(
            "/original"
        )
        head = real.head(document.storage_key)
        assert isinstance(head, ObjectFound) and head.etag == document.etag  # ★e: put 의 ETag = head 의 ETag
        diffs += _sha(real, document.storage_key) != _sha(real, source.storage_key)
    for label, run_id in runs.items():
        files = {(f.step, f.name): f for f in run_files(company_id=a, run_id=world.runs[label])}
        for file in run_files(company_id=b, run_id=run_id):
            assert file.storage_key.startswith(f"runs/{b}/{run_id}/")
            diffs += _sha(real, file.storage_key) != files[(file.step, file.name)].sha256
    before = snapshot(a, world.runs, {k: v for k, v in world.documents.items() if k != "d0"}, {7: "S"})
    after_settings = {int(str(found[runs["r3"]].versions["aiSettingId"])): "S"}
    after = snapshot(b, runs, {k: int(str(v)) for k, v in documents.items()}, after_settings)
    expected = cut_chain(before)
    diffs += sum(1 for key in expected.keys() | after.keys() if expected.get(key) != after.get(key))
    out = os.environ.get("RUNBUNDLE_ROUNDTRIP_OUT")
    if out:
        Path(out).write_text(f"ROUNDTRIP_DIFF={diffs}\n", encoding="utf-8")
    assert diffs == 0
    assert count(owner, "run_runs") == 8


# ── RX1b: 모듈 넷 carrier(T8 · §4-7 모듈 왕복) ─────────────────────────────────
# 실제 전역 등록부(REGISTRY·CARRIERS — 각 모듈 apps.py 가 단 것)로 내보내고 넣는다. 실행 행은 runs 의 services 로
# 심는다(실행기 없이 — 모듈 왕복의 실제 실행기 판은 각 모듈 tests/…/test_bundle_carrier.py). ★ 전부 지어낸 것이다.


WHEN = datetime(2026, 9, 2, 3, 4, 5, tzinfo=UTC)
SETTING_TABLES = {
    "greenwash": "greenwash_ai_settings",
    "translation": "translation_ai_settings",
    "dataverify": "dataverify_ai_settings",
    "materiality": "materiality_ai_settings",
}
SETTING_SERVICES: dict[str, Any] = {
    "greenwash": greenwash_settings,
    "translation": translation_settings,
    "dataverify": dataverify_settings,
    "materiality": materiality_settings,
}
FLOW_OF = {
    "greenwash": "greenwash.colab@E0",
    "translation": "translation.colab@158",
    "dataverify": "dataverify.colab@156",
    "materiality": "materiality.iro@155",
}
SHAPES = {
    "greenwash": ("greenwash.result@1",),
    "translation": ("translation.result@1", "translation.digest@1"),
    "dataverify": ("dataverify.result@2", "dataverify.digest@1"),
    "materiality": ("materiality.result@2", "materiality.digest@1"),
}
B_FIRST = {"greenwash": 1, "translation": 2, "dataverify": 3, "materiality": 0}  # §4-7: B 의 순번을 모듈마다 어긋나게


def _setting(module: str, company_id: int, user: int, title: str, *, apply: bool) -> int:
    services = SETTING_SERVICES[module]
    made = services.create_setting(company_id=company_id, created_by_user_id=user, title=title, memo="가상 메모")
    assert isinstance(made, services.Created), made
    if apply:
        assert isinstance(services.apply_setting(company_id=company_id, setting_id=made.id, now=WHEN), services.Applied)
    return int(made.id)


def _versions(module: str, given: dict[str, Any], company_id: int) -> dict[str, object]:
    flow_id = FLOW_OF[module]
    binding: Any = BINDINGS.documentless(flow_id) or BINDINGS.get(flow_id)
    return dict(binding.versions_with(given, company_id=company_id))


def _module_document(storage: ObjectStorage, company_id: int, name: str) -> int:
    content = f"%PDF-1.4 gasang {name}".encode()
    tag = hashlib.sha256(name.encode()).hexdigest()[:12]
    key = f"companies/{company_id}/documents/00000000-0000-4000-8000-{tag}/original"
    document_id = document_services.import_document(
        company_id=company_id,
        uploaded_by="1",
        storage_key=key,
        file_name=f"가상 {name}.pdf",
        size_bytes=len(content),
        sha256=None,
        status="uploaded",
        uploaded_at=WHEN,
        report_year=2025,
        previous_document_id=None,
        page_count=1,
        has_text=True,
    )
    put = storage.put(key, content=content, media_type="application/octet-stream")
    etag = put.etag if isinstance(put, ObjectPut) else put
    document_services.set_imported_etag(company_id=company_id, document_id=document_id, etag=str(etag))
    return document_id


def _module_run(
    company_id: int,
    user: int,
    module: str,
    given: dict[str, Any],
    versions: dict[str, object],
    *,
    document: int | None = None,
    retry_of: int | None = None,
) -> int:
    from esgapi.core.flows.registry import REGISTRY

    flow = REGISTRY.get(FLOW_OF[module])
    retry = None if retry_of is None else {"fromRunId": retry_of, "pages": [1]}
    run_id = run_bundle_services.insert_run(
        company_id=company_id,
        fields={
            "document_id": document,
            "module": module,
            "flow_id": flow.id,
            "options": given,
            "versions": versions,
            "status": "done",
            "created_by_user_id": user,
            "started_at": WHEN,
            "finished_at": WHEN,
        },
    )
    bodies: list[tuple[str, dict[str, object]]] = []
    for shape in SHAPES[module]:
        body: dict[str, object] = {"schemaVersion": shape, "가상": module}
        if shape == "translation.result@1":
            body["settings"] = {"retry": retry}
        bodies.append((shape, body))
    if module == "greenwash":
        bodies = [("greenwash.result@1", greenwash_seed.example("result-normal"))]
    steps: list[dict[str, object]] = []
    for position, name in enumerate(flow.steps):
        data: dict[str, object] = {"가상": name}
        if module == "translation" and name == "translate":
            data = {"result": dict(bodies[0][1])}
        if module == "translation" and name == "report":
            data = {"results": [dict(body) for _shape, body in bodies]}
        steps.append(
            {"name": name, "position": position, "status": "done", "data": data, "partial": None, "done": 1, "total": 1}
        )
    run_bundle_services.insert_steps(company_id=company_id, run_id=run_id, steps=steps)
    run_bundle_services.insert_results(
        company_id=company_id,
        run_id=run_id,
        results=[{"position": i, "schema_version": shape, "body": body} for i, (shape, body) in enumerate(bodies)],
    )
    return run_id


def _module_world(storage: ObjectStorage, owner: Owner, a: int, b: int) -> tuple[dict[str, int], int, dict[str, int]]:
    """A 의 모듈 실행(이름표 → id)·A 의 사람·A 의 판(모듈 → id). 판 표 넷의 순번을 1 로 되돌려 A 의 판 id 가 넷 다 같게
    (§4-7 — 판 지도를 한 지도로 합치면 섞이게), B 에는 모듈마다 다른 수의 판을 먼저 둔다."""
    for table in SETTING_TABLES.values():
        owner.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), 1, false)", [table])
    user = a_customer(a, "gasang-mod-a")
    settings = {module: _setting(module, a, user, "가상 판", apply=True) for module in SETTING_TABLES}
    assert len(set(settings.values())) == 1, settings  # 옛 판 id 가 모듈 넷에서 같다
    document = _module_document(storage, a, "그린워싱 보고서")
    gw = translation_options()  # 영문번역 옵션(문서 실행)
    greenwash_given = {"parts": {"ceo": [1], "company": [2], "climate": [3]}}
    runs: dict[str, int] = {}
    runs["gw1"] = _module_run(
        a, user, "greenwash", greenwash_given, _versions("greenwash", greenwash_given, a), document=document
    )
    runs["gw2"] = _module_run(
        a, user, "greenwash", greenwash_given, _versions("greenwash", greenwash_given, a), document=document
    )
    review_services.create_review(company_id=a, run_id=runs["gw1"])
    review_services.write_marks(
        company_id=a,
        run_id=runs["gw1"],
        inserts={
            0: {"decision": "adopted"},
            1: {"edited_level": "Low", "level_edited_at": WHEN, "level_edited_by_user_id": user},
            2: {
                "decision": "excluded",
                "exclude_reason": "가상 근거",
                "fix_edited_at": WHEN,
                "fix_edited_by_user_id": user,
                "edited_fix_paragraph": "가상 수정",
            },
        },
        updates={},
    )
    review_services.set_state(
        company_id=a, run_id=runs["gw1"], state="confirmed", confirmed_at=WHEN, confirmed_by_user_id=user
    )
    tr_doc = _module_document(storage, a, "영문번역 원문")
    runs["tr1"] = _module_run(a, user, "translation", gw, _versions("translation", gw, a), document=tr_doc)
    again = translation_options(retry={"fromRunId": runs["tr1"], "pages": [1]})
    runs["tr2"] = _module_run(
        a, user, "translation", again, _versions("translation", again, a), document=tr_doc, retry_of=runs["tr1"]
    )
    for module, given in (("dataverify", dataverify_options()), ("materiality", materiality_options())):
        runs[f"{module[:2]}1"] = _module_run(a, user, module, given, _versions(module, given, a))
        SETTING_SERVICES[module].apply_setting(company_id=a, setting_id=None, now=WHEN)
        runs[f"{module[:2]}0"] = _module_run(a, user, module, given, _versions(module, given, a))
    for module, n in B_FIRST.items():
        for i in range(n):
            _setting(module, b, 1, f"가상 B 판 {i}", apply=False)
    return runs, user, settings


def _module_snapshot(company: int, runs: dict[str, int]) -> dict[str, object]:
    """그 회사의 모듈 실행을 selector 로 읽어 실행 id·판 id·판 이름·사람을 이름표로 바꾼 꼴(§4-7 의 정규형)."""
    label = {run_id: name for name, run_id in runs.items()}
    names: dict[tuple[str, object], str] = {}

    def setting_label(module: str, versions: dict[str, Any]) -> dict[str, Any]:
        if isinstance(versions.get("aiSettingId"), int):
            tag = names.setdefault((module, versions["aiSettingId"]), f"{module}:S")
            return {**versions, "aiSettingId": tag, "aiSetting": tag}
        return versions

    def runs_out(value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            fields: dict[str, Any] = value  # pyright: ignore[reportUnknownVariableType]
            return {k: runs_out(v, k) for k, v in fields.items()}
        if isinstance(value, list):
            items: list[Any] = value  # pyright: ignore[reportUnknownVariableType]
            return [runs_out(v) for v in items]
        if key == "fromRunId" and isinstance(value, int):
            return label.get(value, f"밖:{value}")
        return value

    found: dict[str, object] = {}
    for name, run_id in sorted(runs.items()):
        run = run_selectors.find_run(company_id=company, run_id=run_id)
        assert run is not None, name
        detail = operator_selectors.operator_run_detail(actor_kind="admin", company_id=company, run_id=run_id)
        assert isinstance(detail, operator_selectors.OperatorRunDetail)
        ai = detail.run.ai_setting
        found[f"{name}.versions"] = setting_label(run.module, dict(run.versions))
        found[f"{name}.operator"] = (
            None if ai is None else (None if ai[0] is None else f"{run.module}:S", ai[1] if ai[0] is None else "S")
        )
        found[f"{name}.options"] = runs_out(run.options)
        found[f"{name}.results"] = [
            (r.schema_version, runs_out(r.body)) for r in run_selectors.run_results(company_id=company, run_id=run_id)
        ]
        found[f"{name}.steps"] = [
            (s.name, runs_out(s.data), s.partial) for s in run_selectors.step_rows(company_id=company, run_id=run_id)
        ]
        if run.module == "greenwash":
            review = review_selectors.find_review(company_id=company, run_id=run_id)
            found[f"{name}.review"] = (
                None if review is None else (review.state, review.confirmed_at, review.confirmed_by_user_id is not None)
            )
            found[f"{name}.marks"] = {
                i: (
                    m.decision,
                    m.exclude_reason,
                    m.edited_level,
                    m.level_edited_at,
                    m.fix_edited_at,
                    m.edited_fix_paragraph,
                )
                for i, m in review_selectors.mark_rows(company_id=company, run_id=run_id).items()
            }
            found[f"{name}.tally"] = review_selectors.mark_tallies(company_id=company, run_ids=[run_id]).get(run_id)
    return found


def _setting_rows(owner: Owner, table: str, company: int) -> list[tuple[Any, ...]]:
    query = sql.SQL("SELECT id, name, applied FROM {} WHERE company_id = %s ORDER BY id").format(sql.Identifier(table))
    return owner.execute(query, [company]).fetchall()


def test_module_runs_round_trip_through_the_real_storage(
    tmp_path: Path, companies: tuple[int, int], owner: Owner
) -> None:
    """§4-7(RX1b): 모듈 넷 — 그린워싱 문서 실행 둘(같은 문서·검토·고침·저장 판), 영문번역 재번역 짝(저장 판), 데이터
    검증·중대성평가 저장 판 하나·기본 판 하나 → 실제 저장소로 내보내 B 에 넣으면 정규형이 같고(ROUNDTRIP_DIFF), 같은
    묶음 둘째 넣기는 거절. RUNBUNDLE_MODULE_ROUNDTRIP_OUT 에 줄을 적는다(section4-RX1b 의 7)."""
    real = _real_storage()
    a, b = companies
    runs, _user, _settings = _module_world(real, owner, a, b)
    path = tmp_path / "modules.zip"
    export.run(company_id=a, selection=RunIds(tuple(runs.values())), out=path, app_commit="test", storage=real)
    sample = os.environ.get("RUNBUNDLE_MODULE_SAMPLE_OUT")
    if sample:
        shutil.copyfile(path, sample)
    user_b = a_customer(b, "gasang-mod-b")
    done = import_.run(path=path, company_id=b, user_id=user_b, orphans_out=tmp_path / "o.txt", storage=real)
    assert sorted(done.runs) == sorted(runs.values())
    new = {name: done.runs[old] for name, old in runs.items()}
    before, after = _module_snapshot(a, runs), _module_snapshot(b, new)
    diffs = sum(1 for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    for module, table in SETTING_TABLES.items():  # 판 지도가 모듈마다: B 에 새 판 하나, 그 id 를 그 모듈 실행만 가리킴
        rows = _setting_rows(owner, table, b)
        diffs += len(rows) != B_FIRST[module] + 1
        (new_id, new_name, applied) = rows[-1]
        diffs += new_name != f"v{B_FIRST[module] + 1}" or applied
        for run_id in new.values():
            run = run_selectors.find_run(company_id=b, run_id=run_id)
            if run is not None and run.module == module and isinstance(run.versions.get("aiSettingId"), int):
                diffs += run.versions["aiSettingId"] != new_id or run.versions["aiSetting"] != new_name
    out = os.environ.get("RUNBUNDLE_MODULE_ROUNDTRIP_OUT")
    if out:
        Path(out).write_text(f"ROUNDTRIP_DIFF={diffs}\n", encoding="utf-8")
    assert diffs == 0, [k for k in before.keys() | after.keys() if before.get(k) != after.get(k)]
    with pytest.raises(bundle_calc.Refused, match="이미"):
        import_.run(path=path, company_id=b, user_id=user_b, orphans_out=tmp_path / "o2.txt", storage=real)


def test_module_rows_stay_in_their_company(tmp_path: Path, companies: tuple[int, int], owner: Owner) -> None:
    """T8: 앱 역할로 넣은 뒤 — A 의 검토는 B 의 회사 범위에서 안 보이고(같은 run_id 값으로 물어도), A 쪽은 앞 = 뒤,
    B 의 판 표 넷에 A 의 판 행 0, B 의 표시는 A 의 실행 id 로 넣을 수 없다(복합 외래 키 (company_id, run_id))."""
    a, b = companies
    storage = FakeStorage()
    runs, _user, settings = _module_world(storage, owner, a, b)
    path = tmp_path / "modules.zip"
    export.run(company_id=a, selection=RunIds(tuple(runs.values())), out=path, app_commit="test", storage=storage)
    before_a = _module_snapshot(a, runs)
    a_rows = {table: _setting_rows(owner, table, a) for table in SETTING_TABLES.values()}
    user_b = a_customer(b, "gasang-mod-b")
    done = import_.run(path=path, company_id=b, user_id=user_b, orphans_out=tmp_path / "o.txt", storage=storage)
    assert count(owner, "greenwash_reviews") == 2 and count(owner, "greenwash_review_marks") == 6  # 분모: A·B 하나씩
    assert _module_snapshot(a, runs) == before_a  # 남의 회사(A) 쪽 앞 = 뒤
    assert {table: _setting_rows(owner, table, a) for table in SETTING_TABLES.values()} == a_rows
    assert review_selectors.find_review(company_id=b, run_id=runs["gw1"]) is None  # A 의 run_id 값으로 B 에서 물음
    assert review_selectors.bundle_review_rows(company_id=b, run_ids=[runs["gw1"], runs["gw2"]]).reviews == []
    assert review_selectors.find_review(company_id=a, run_id=done.runs[runs["gw1"]]) is None
    for module, table in SETTING_TABLES.items():
        ids_b = {row[0] for row in _setting_rows(owner, table, b)}
        assert settings[module] not in ids_b and len(ids_b) == B_FIRST[module] + 1
    marks_b = count(owner, "greenwash_review_marks")
    with pytest.raises(django_db.IntegrityError):  # B 에 (B, A 의 실행) 검토가 없다 — 복합 외래 키
        review_services.import_marks(
            company_id=b,
            rows=(
                {
                    **dict.fromkeys(review_selectors.MARK_BUNDLE_FIELDS),
                    "run_id": runs["gw2"],
                    "item_index": 0,
                    "decision": "adopted",
                    "created_at": WHEN,
                    "updated_at": WHEN,
                },
            ),
            user_id=user_b,
        )
    assert count(owner, "greenwash_review_marks") == marks_b


def test_a_forged_bundle_with_a_person_column_is_refused_as_the_app_role(
    tmp_path: Path, companies: tuple[int, int], owner: Owner
) -> None:
    """T8: 앱 역할로 꾸민 묶음(그린워싱 검토 행에 confirmed_by_user_id) 넣기 → 거절, 주인이 센 쓰기 0."""
    a, b = companies
    storage = FakeStorage()
    runs, _user, _settings = _module_world(storage, owner, a, b)
    path = tmp_path / "modules.zip"
    export.run(company_id=a, selection=RunIds((runs["gw1"],)), out=path, app_commit="test", storage=storage)
    forged = tmp_path / "forged.zip"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(forged, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "bundle.json":
                header = json.loads(data)
                header["rows"]["modules"]["greenwash"]["greenwash_reviews"][0]["confirmed_by_user_id"] = 5
                data = json.dumps(header, ensure_ascii=False).encode()
            target.writestr(info.filename, data)
    tables = ("run_runs", "greenwash_reviews", "greenwash_review_marks", "greenwash_ai_settings", "core_documents")
    before = {table: count(owner, table) for table in tables}
    assert before["greenwash_reviews"] == 1  # 분모: A 의 검토가 있다
    with pytest.raises(bundle_calc.Refused, match="사람·회사·id 칸"):
        import_.run(
            path=forged,
            company_id=b,
            user_id=a_customer(b, "gasang-mod-b"),
            orphans_out=tmp_path / "o.txt",
            storage=storage,
        )
    assert {table: count(owner, table) for table in tables} == before
    assert "greenwash" in CARRIERS.modules()
